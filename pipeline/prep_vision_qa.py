#!/usr/bin/env python3
"""
prep_vision_qa.py -- build the per-slide QA scratch tree.

For every Output_<name>/ produced by pdf_pipeline.py, this renders each source
slide to a ground-truth PNG, rasterizes/copies the linked assets, and records
the per-slide TeX section into .verify_scratch/prep_info.json. create_stitched.py
and qa_verifier.py consume that file.

Run from the directory that contains the Output_* folders (e.g. sources/pdf/):

    python3 ../../pipeline/prep_vision_qa.py [--cwd DIR] [--scratch-dir DIR] [--dpi N]
"""
import argparse
import json
import os
import re
import shutil
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("ERROR: PyMuPDF (fitz) is not installed.\n"
             "       This extraction-QA tool needs it: pip install -r requirements.txt\n"
             "       (only required to re-run the PDF->LaTeX pipeline; not for poster builds).")


def render_pdf_first_page(pdf_path, dpi):
    """Render page 0 of a PDF to a PNG path-agnostic PIL-free pixmap save."""
    doc = fitz.open(pdf_path)
    try:
        pix = doc[0].get_pixmap(dpi=dpi)
        return pix
    finally:
        doc.close()


def process_output_dir(out_dir, cwd, scratch_dir, dpi):
    """Build the scratch record for a single Output_<name>/ dir. Returns dict or None."""
    base_name = out_dir.replace("Output_", "")
    tex_file = os.path.join(out_dir, f"{base_name}_mapped.tex")
    if not os.path.exists(tex_file):
        print(f"  [skip] {out_dir}: no {base_name}_mapped.tex")
        return None

    with open(tex_file, "r", encoding="utf-8") as f:
        tex_content = f.read()

    slides_dir = os.path.join(out_dir, "slides")
    if os.path.isdir(slides_dir):
        slide_pdfs = [f for f in os.listdir(slides_dir)
                      if f.startswith("slide_") and f.endswith(".pdf")]
        total_slides = len(slide_pdfs)
    else:
        main_pdf = f"{base_name}.pdf"
        total_slides = 0
        if os.path.exists(main_pdf):
            doc = fitz.open(main_pdf)
            total_slides = len(doc)
            doc.close()

    slide_matches = list(re.finditer(r"\\section\*\{Slide\s+(\d+)\}", tex_content))

    pdf_info = {"base_name": base_name, "total_slides": total_slides, "slides": []}

    scratch_pdf_dir = os.path.join(scratch_dir, base_name)
    os.makedirs(scratch_pdf_dir, exist_ok=True)

    for i, match in enumerate(slide_matches):
        slide_num = int(match.group(1))
        start_idx = match.end()
        end_idx = slide_matches[i + 1].start() if i + 1 < len(slide_matches) else len(tex_content)
        slide_tex = tex_content[start_idx:end_idx].strip()

        assets = re.findall(r"\\includegraphics(?:\[.*?\])?\{([^}]+)\}", slide_tex)

        # Render the ground-truth slide.
        source_slide = os.path.join(out_dir, "slides", f"slide_{slide_num:02d}.pdf")
        alt_slide = os.path.join(out_dir, "slides", f"slide_{slide_num}.pdf")
        if not os.path.exists(source_slide) and os.path.exists(alt_slide):
            source_slide = alt_slide

        gt_png = os.path.join(scratch_pdf_dir, f"slide_{slide_num:02d}.png")
        if os.path.exists(source_slide):
            try:
                render_pdf_first_page(source_slide, dpi).save(gt_png)
            except Exception as e:
                print(f"    [WARN] render failed for {source_slide}: {e}")

        asset_pngs = []
        for asset in assets:
            asset_path = os.path.join(out_dir, asset)
            if not os.path.exists(asset_path):
                asset_path = os.path.join(cwd, asset)
            if not os.path.exists(asset_path):
                asset_pngs.append(f"MISSING: {asset}")
                continue
            try:
                ext = os.path.splitext(asset_path)[1].lower()
                scratch_asset_path = os.path.join(scratch_pdf_dir, os.path.basename(asset_path))
                if ext == ".pdf":
                    scratch_asset_path = os.path.splitext(scratch_asset_path)[0] + ".png"
                    render_pdf_first_page(asset_path, dpi).save(scratch_asset_path)
                elif ext in (".png", ".jpeg", ".jpg"):
                    shutil.copy2(asset_path, scratch_asset_path)
                else:
                    asset_pngs.append(f"UNSUPPORTED: {asset}")
                    continue
                asset_pngs.append(scratch_asset_path)
            except Exception as e:
                print(f"    [WARN] asset prep failed for {asset_path}: {e}")
                asset_pngs.append(f"ERROR: {asset}")

        pdf_info["slides"].append({
            "slide_num": slide_num,
            "tex": slide_tex,
            "assets": asset_pngs,
            "gt_png": gt_png if os.path.exists(gt_png) else "MISSING",
        })

    return pdf_info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", default=os.getcwd(),
                        help="directory containing the Output_* folders (default: cwd)")
    parser.add_argument("--scratch-dir", default=None,
                        help="scratch output dir (default: <cwd>/.verify_scratch)")
    parser.add_argument("--dpi", type=int, default=150, help="render DPI (default 150)")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd)
    scratch_dir = args.scratch_dir or os.path.join(cwd, ".verify_scratch")
    os.makedirs(scratch_dir, exist_ok=True)

    output_dirs = [d for d in os.listdir(cwd)
                   if d.startswith("Output_") and os.path.isdir(os.path.join(cwd, d))]
    if not output_dirs:
        print(f"No Output_* directories found in {cwd}. Run pdf_pipeline.py first.",
              file=sys.stderr)
        return 1

    report = {}
    for out_dir in sorted(output_dirs):
        print(f"Preparing {out_dir}...")
        try:
            info = process_output_dir(os.path.join(cwd, out_dir), cwd, scratch_dir, args.dpi)
        except Exception as e:
            # Isolate failures: one bad source must not abort the batch.
            print(f"  [ERROR] {out_dir}: {e}", file=sys.stderr)
            info = None
        if info is not None:
            report[info["base_name"]] = info

    info_path = os.path.join(scratch_dir, "prep_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Prep complete. {len(report)} source(s) -> {info_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
