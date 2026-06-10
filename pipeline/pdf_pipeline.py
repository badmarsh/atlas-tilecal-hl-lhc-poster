import os
import glob
import shutil
import unicodedata
import fitz  # PyMuPDF
import re

# --- Significance filter ----------------------------------------------------
# Keep only real figures / graphs / tables. Drop icons, logos, crests, author
# headshots, decorative title bars / rules, and degenerate 0-area or sliver
# boxes. Thresholds are page-relative so they work for both normal slides and
# large posters. Tune here.
MIN_AREA_FRAC = 0.004    # region must cover >= 0.4% of the page area
MIN_SIDE_FRAC = 0.04     # both sides must be >= 4% of the shorter page side
MAX_ASPECT    = 10.0     # reject extreme strips (banners, rules)
MERGE_TOLERANCE = 20     # vector-merge proximity in pt (coalesces split diagrams)
RASTER_FALLBACK_DPI = 200  # DPI used when a vector crop can't be saved as PDF


def is_significant(rect, page_rect):
    """True if `rect` looks like real content rather than a small/decorative asset."""
    w, h = rect.width, rect.height
    if w <= 1 or h <= 1:
        return False
    short_page = min(page_rect.width, page_rect.height)
    if min(w, h) < MIN_SIDE_FRAC * short_page:
        return False
    if rect.get_area() < MIN_AREA_FRAC * page_rect.get_area():
        return False
    if max(w, h) / min(w, h) > MAX_ASPECT:
        return False
    return True


# The ten TeX special characters.
_LATEX_SPECIALS = {
    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
    '{': r'\{', '}': r'\}',
    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    '\\': r'\textbackslash{}',
}

# Latin accents -> LaTeX accent commands (preserve author names etc.).
_LATIN = {
    'á': r"\'a", 'é': r"\'e", 'í': r"\'i", 'ó': r"\'o", 'ú': r"\'u",
    'à': r"\`a", 'è': r"\`e", 'ì': r"\`i", 'ò': r"\`o", 'ù': r"\`u",
    'â': r"\^a", 'ê': r"\^e", 'î': r"\^i", 'ô': r"\^o", 'û': r"\^u",
    'ä': r'\"a', 'ë': r'\"e', 'ï': r'\"i', 'ö': r'\"o', 'ü': r'\"u',
    'ñ': r"\~n", 'ç': r"\c{c}", 'å': r"\aa{}", 'ø': r"\o{}", 'ß': r"\ss{}",
    'Á': r"\'A", 'É': r"\'E", 'Í': r"\'I", 'Ó': r"\'O", 'Ú': r"\'U",
    'Ä': r'\"A', 'Ö': r'\"O', 'Ü': r'\"U', 'Ñ': r"\~N", 'Ç': r"\c{C}",
}

# Common scientific symbols -> math-mode LaTeX or ASCII.
_SYMBOLS = {
    '∗': '*', '−': '-', '·': r'$\cdot$', '×': r'$\times$', '÷': r'$\div$',
    '±': r'$\pm$', '∓': r'$\mp$', '≈': r'$\approx$', '≃': r'$\simeq$',
    '∼': r'$\sim$', '≤': r'$\leq$', '≥': r'$\geq$', '≠': r'$\neq$',
    '≪': r'$\ll$', '≫': r'$\gg$', '→': r'$\rightarrow$', '←': r'$\leftarrow$',
    '↔': r'$\leftrightarrow$', '⇒': r'$\Rightarrow$', '∞': r'$\infty$',
    '∝': r'$\propto$', '∈': r'$\in$', '∉': r'$\notin$', '∑': r'$\sum$',
    '∏': r'$\prod$', '∫': r'$\int$', '∂': r'$\partial$', '∇': r'$\nabla$',
    '√': r'$\sqrt{}$', '°': r'$^{\circ}$', 'µ': r'$\mu$', 'Ω': r'$\Omega$',
    '…': r'\ldots{}', '–': '--', '—': '---', '‰': r'\textperthousand{}',
    '’': "'", '‘': "`", '“': "``", '”': "''", '′': "'", '″': "''",
    ' ': ' ', ' ': ' ', ' ': ' ', 'ﬁ': 'fi', 'ﬂ': 'fl',
}

# Greek letters -> math-mode LaTeX.
_GREEK = {
    'α': r'$\alpha$', 'β': r'$\beta$', 'γ': r'$\gamma$', 'δ': r'$\delta$',
    'ε': r'$\epsilon$', 'ζ': r'$\zeta$', 'η': r'$\eta$', 'θ': r'$\theta$',
    'ι': r'$\iota$', 'κ': r'$\kappa$', 'λ': r'$\lambda$', 'μ': r'$\mu$',
    'ν': r'$\nu$', 'ξ': r'$\xi$', 'π': r'$\pi$', 'ρ': r'$\rho$',
    'σ': r'$\sigma$', 'τ': r'$\tau$', 'υ': r'$\upsilon$', 'φ': r'$\phi$',
    'χ': r'$\chi$', 'ψ': r'$\psi$', 'ω': r'$\omega$',
    'Γ': r'$\Gamma$', 'Δ': r'$\Delta$', 'Θ': r'$\Theta$', 'Λ': r'$\Lambda$',
    'Ξ': r'$\Xi$', 'Π': r'$\Pi$', 'Σ': r'$\Sigma$', 'Φ': r'$\Phi$',
    'Ψ': r'$\Psi$', 'Ω': r'$\Omega$',
}


def escape_latex(text, stats=None):
    """Escape TeX specials and convert Unicode to pdflatex-safe LaTeX.

    Handles the physics PDFs' Unicode math (e.g. mathematical-italic letters,
    operators, Greek). `stats`, if given, accumulates a 'stripped' count of
    characters that had no representation and were dropped.
    """
    out = []
    for ch in text:
        if ch in _LATEX_SPECIALS:
            out.append(_LATEX_SPECIALS[ch])
        elif ord(ch) < 128:
            out.append(ch)
        elif ch in _LATIN:
            out.append(_LATIN[ch])
        elif ch in _SYMBOLS:
            out.append(_SYMBOLS[ch])
        elif ch in _GREEK:
            out.append(_GREEK[ch])
        else:
            # Fold compatibility forms (math-italic/bold letters, ﬁ, etc.) to ASCII.
            folded = unicodedata.normalize('NFKD', ch)
            folded = ''.join(c for c in folded if not unicodedata.combining(c))
            if folded and all(ord(c) < 128 for c in folded):
                out.append("".join(_LATEX_SPECIALS.get(c, c) for c in folded))
            else:
                # No safe representation: drop it so compilation can't fail.
                if stats is not None:
                    stats['stripped'] = stats.get('stripped', 0) + 1
    return "".join(out)

def merge_rects(rects, page_rect, tolerance=10):
    if not rects:
        return []

    # Filter out rects that cover almost the whole page
    page_area = page_rect.get_area()
    valid_rects = []
    for r in rects:
        if r.get_area() > 0.8 * page_area:
            continue
        valid_rects.append(r)

    if not valid_rects:
        return []

    # Merge intersecting or very close rects
    merged = []
    for r in valid_rects:
        # expand slightly to merge nearby drawings
        r_exp = r + (-tolerance, -tolerance, tolerance, tolerance)
        found = False
        for i, m in enumerate(merged):
            if r_exp.intersects(m):
                merged[i] = m | r
                found = True
                break
        if not found:
            merged.append(r)

    # Iterate a few times to ensure all overlapping are merged
    for _ in range(3):
        new_merged = []
        for r in merged:
            found = False
            for i, m in enumerate(new_merged):
                if r.intersects(m):
                    new_merged[i] = m | r
                    found = True
                    break
            if not found:
                new_merged.append(r)
        merged = new_merged

    return merged

def process_pdf(pdf_path):
    pdf_name = os.path.basename(pdf_path)
    base_name = os.path.splitext(pdf_name)[0]
    out_dir = f"Output_{base_name}"

    slides_dir = os.path.join(out_dir, "slides")
    assets_dir = os.path.join(out_dir, "assets")

    # Start fresh so stale assets/slides from a previous run can't accumulate
    # or shadow the current mapping.
    for d in (slides_dir, assets_dir):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)

    # Status record returned to the batch summary in main()
    result = {"name": pdf_name, "pages": 0, "assets": 0, "mapped": 0,
              "missing": 0, "stray": 0, "balanced": True, "error": None}

    print(f"\nProcessing {pdf_name}...")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  [ERROR] Failed to open {pdf_path}: {e}")
        result["error"] = f"open failed: {e}"
        return result

    tex_path_raw = os.path.join(out_dir, f"{base_name}_raw.tex")
    asset_count = 0
    text_stats = {}  # accumulates count of dropped (unrepresentable) Unicode chars

    try:
        with open(tex_path_raw, 'w', encoding='utf-8') as f_tex:
            f_tex.write(r"\documentclass{article}" + "\n")
            f_tex.write(r"\usepackage[utf8]{inputenc}" + "\n")
            f_tex.write(r"\usepackage[T1]{fontenc}" + "\n")
            f_tex.write(r"\usepackage{graphicx}" + "\n")
            f_tex.write(r"\usepackage{float}" + "\n")  # enables [H] = place here, no float queue
            f_tex.write(r"\begin{document}" + "\n\n")

            # Phase 1, 2, 3
            for page_num in range(len(doc)):
                print(f"  Page {page_num + 1}/{len(doc)}")
                page = doc[page_num]

                # Phase 1: Pagination
                slide_pdf_path = os.path.join(slides_dir, f"slide_{page_num+1:02d}.pdf")
                slide_doc = fitz.open()
                try:
                    slide_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    slide_doc.save(slide_pdf_path)
                finally:
                    slide_doc.close()

                # Extract elements for Phase 2 & 3
                blocks = page.get_text("dict").get("blocks", [])
                images = []
                texts = []

                for b in blocks:
                    if b["type"] == 0:  # text
                        rect = fitz.Rect(b["bbox"])
                        text_content = ""
                        for line in b.get("lines", []):
                            for span in line.get("spans", []):
                                text_content += span["text"] + " "
                            text_content += "\n"
                        texts.append({"type": "text", "rect": rect, "content": text_content.strip()})
                    elif b["type"] == 1:  # image
                        rect = fitz.Rect(b["bbox"])
                        # Skip small/decorative raster images (icons, logos, headshots, slivers)
                        if not is_significant(rect, page.rect):
                            continue
                        images.append({"type": "image", "rect": rect, "image_data": b.get("image", None), "ext": b.get("ext", "png")})

                drawings = page.get_drawings()
                drawing_rects = [d["rect"] for d in drawings]
                vector_rects = merge_rects(drawing_rects, page.rect, tolerance=MERGE_TOLERANCE)
                # Keep only substantial vector regions (drops shattered fragments / rules)
                vectors = [{"type": "vector", "rect": r} for r in vector_rects if is_significant(r, page.rect)]

                # Remove text blocks that fall inside vector regions (they are likely axis labels, etc.)
                filtered_texts = []
                for t in texts:
                    inside_vector = False
                    for v in vectors:
                        if t["rect"].intersects(v["rect"]) and v["rect"].get_area() > t["rect"].get_area():
                            # If a text box is completely or largely inside a vector graphic, ignore it
                            if v["rect"].contains(t["rect"].tl) or v["rect"].contains(t["rect"].br):
                                inside_vector = True
                                break
                    if not inside_vector:
                        filtered_texts.append(t)

                texts = filtered_texts

                # Combine and sort all elements vertically
                all_elements = texts + images + vectors
                all_elements.sort(key=lambda e: (e["rect"].y0, e["rect"].x0))

                f_tex.write(f"\\section*{{Slide {page_num+1}}}\n\n")

                item_num = 1
                for el in all_elements:
                    if el["type"] == "text":
                        escaped = escape_latex(el["content"], stats=text_stats)
                        if escaped:
                            f_tex.write(escaped + "\n\n")
                    elif el["type"] == "image":
                        placeholder = f"PLACEHOLDER_SLIDE_{page_num+1}_ITEM_{item_num}"
                        f_tex.write("\\begin{figure}[H]\n\\centering\n")
                        f_tex.write(f"\\includegraphics[width=0.8\\linewidth]{{{placeholder}}}\n")
                        f_tex.write("\\end{figure}\n\n")

                        # Extract image (native format; pdflatex accepts png/jpg/jpeg/pdf)
                        if el["image_data"]:
                            ext = (el["ext"] or "png").lower()
                            img_filename = f"{base_name}_slide_{page_num+1}_item_{item_num}.{ext}"
                            img_path = os.path.join(assets_dir, img_filename)
                            with open(img_path, "wb") as f_img:
                                f_img.write(el["image_data"])
                            asset_count += 1

                        # Always advance the item counter so numbering stays unique even if
                        # extraction fails (the unmapped placeholder is cleaned up in Phase 5).
                        item_num += 1
                    elif el["type"] == "vector":
                        placeholder = f"PLACEHOLDER_SLIDE_{page_num+1}_ITEM_{item_num}"
                        f_tex.write("\\begin{figure}[H]\n\\centering\n")
                        f_tex.write(f"\\includegraphics[width=0.8\\linewidth]{{{placeholder}}}\n")
                        f_tex.write("\\end{figure}\n\n")

                        # Crop the vector region. Work on an in-memory copy of the single
                        # page (no per-vector disk re-open, no mutation of the shared `doc`).
                        vec_filename = f"{base_name}_slide_{page_num+1}_item_{item_num}.pdf"
                        vec_path = os.path.join(assets_dir, vec_filename)

                        crop_doc = fitz.open()
                        try:
                            crop_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                            crop_page = crop_doc[0]
                            # Intersect with the MediaBox so an out-of-bounds bbox is safe.
                            # `&` returns a new Rect (does not mutate el["rect"] in place).
                            clip = el["rect"] & crop_page.mediabox
                            if not clip.is_empty and clip.get_area() > 0:
                                try:
                                    crop_page.set_cropbox(clip)
                                    crop_doc.save(vec_path)
                                    asset_count += 1
                                except (ValueError, RuntimeError) as e:
                                    # Fallback: rasterize the region to PNG (always renders,
                                    # even when set_cropbox rejects the box).
                                    print(f"      [INFO] PDF crop failed ({e}); rasterizing region instead.")
                                    try:
                                        z = RASTER_FALLBACK_DPI / 72.0
                                        pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(z, z), clip=clip)
                                        pix.save(vec_path[:-4] + ".png")
                                        asset_count += 1
                                    except Exception as e2:
                                        print(f"      [WARNING] Raster fallback also failed: {e2}")
                        finally:
                            crop_doc.close()

                        item_num += 1

            f_tex.write(r"\end{document}" + "\n")

        result["pages"] = len(doc)
    finally:
        # Guaranteed close even if an exception is raised mid-processing.
        doc.close()

    result["assets"] = asset_count

    # Phase 4: LaTeX Mapping
    print("  Mapping placeholders...")
    with open(tex_path_raw, 'r', encoding='utf-8') as f:
        tex_content = f.read()

    # Build map of assets (accept ANY extension so nothing is silently dropped)
    asset_map = {}
    for af in os.listdir(assets_dir):
        m = re.match(r".+_slide_(\d+)_item_(\d+)\.([A-Za-z0-9]+)$", af)
        if m:
            slide_n, item_n = m.group(1), m.group(2)
            asset_map[f"PLACEHOLDER_SLIDE_{int(slide_n)}_ITEM_{int(item_n)}"] = f"assets/{af}"

    def replace_placeholder(match):
        opt = match.group(1) or ""          # preserve the [width=...] optional argument
        placeholder = match.group(2)
        if placeholder in asset_map:
            return f"\\includegraphics{opt}{{{asset_map[placeholder]}}}"
        return match.group(0)               # leave untouched if not found

    # Single pass handles both bracketed and bare placeholder forms.
    mapped_tex_content = re.sub(
        r"\\includegraphics(\[[^\]]*\])?\{(PLACEHOLDER_[A-Z0-9_]+)\}",
        replace_placeholder, tex_content)

    mapped_tex_path = os.path.join(out_dir, f"{base_name}_mapped.tex")
    with open(mapped_tex_path, 'w', encoding='utf-8') as f:
        f.write(mapped_tex_content)
    result["mapped"] = len(asset_map)

    # Phase 5: Verification Pass 1 (Sanity Check)
    print("  Verification Pass 1...")
    missing_files = []
    # Pull every path referenced by \includegraphics{...} or \input{...}
    refs = re.findall(r"\\(?:includegraphics(?:\[[^\]]*\])?|input)\{([^}]+)\}", mapped_tex_content)
    for ref in refs:
        if ref.startswith("PLACEHOLDER_"):
            missing_files.append(ref)
        elif not os.path.exists(os.path.join(out_dir, ref)):
            missing_files.append(ref)

    if missing_files:
        print("    [WARNING] Missing or unmapped files:", set(missing_files))
        print("    [INFO] Attempting to fix dynamically by removing unmapped figure blocks...")

        for placeholder in set(missing_files):
            if placeholder.startswith("PLACEHOLDER_"):
                # Whole figure block containing this placeholder
                pattern = (r"\\begin\{figure\}\[H\]\n\\centering\n"
                           r"\\includegraphics\[[^\]]*\]\{" + re.escape(placeholder) +
                           r"\}\n\\end\{figure\}\n\n?")
                mapped_tex_content = re.sub(pattern, "", mapped_tex_content)
                # Fallback: any remaining inline reference (with or without optional arg)
                pattern2 = (r"\\includegraphics(?:\[[^\]]*\])?\{" +
                            re.escape(placeholder) + r"\}")
                mapped_tex_content = re.sub(pattern2, "", mapped_tex_content)

        with open(mapped_tex_path, 'w', encoding='utf-8') as f:
            f.write(mapped_tex_content)
    else:
        print("    [OK] All referenced files exist in assets/")
    result["missing"] = len(set(missing_files))

    # Phase 6: Verification Pass 2 (Compilation Check)
    print("  Verification Pass 2...")
    stray_placeholders = re.findall(r"PLACEHOLDER_SLIDE_\d+_ITEM_\d+", mapped_tex_content)
    if stray_placeholders:
        print("    [ERROR] Stray placeholders found:", set(stray_placeholders))
    else:
        print("    [OK] No stray placeholders.")
    result["stray"] = len(set(stray_placeholders))

    # Check syntax (basic figure matching)
    begin_figs = mapped_tex_content.count(r"\begin{figure}")
    end_figs = mapped_tex_content.count(r"\end{figure}")
    if begin_figs != end_figs:
        print(f"    [ERROR] Unmatched figure environments: {begin_figs} begins vs {end_figs} ends.")
        result["balanced"] = False
    else:
        print("    [OK] LaTeX figure structure visually sound.")

    if text_stats.get('stripped'):
        print(f"    [INFO] Dropped {text_stats['stripped']} unrepresentable Unicode char(s) from text.")
    result["stripped"] = text_stats.get('stripped', 0)

    # Remove the raw intermediate .tex now that the mapped file is final.
    if os.path.exists(tex_path_raw):
        os.remove(tex_path_raw)

    print(f"  Done. Mapped file saved to {mapped_tex_path}")
    return result

def main():
    root_dir = "."
    pdfs = glob.glob(os.path.join(root_dir, "*.pdf"))

    # glob *.pdf is non-recursive, so it won't descend into Output_* folders;
    # this filter is a belt-and-braces guard.
    pdfs = [p for p in pdfs if "Output_" not in p]

    if not pdfs:
        print("No PDFs found in the root directory.")
        return

    print(f"Found {len(pdfs)} PDFs to process.")

    results = []
    for pdf in pdfs:
        try:
            results.append(process_pdf(pdf))
        except Exception as e:
            # Isolate failures: one bad PDF must not abort the whole batch.
            print(f"  [ERROR] Unhandled failure on {pdf}: {e}")
            results.append({"name": os.path.basename(pdf), "pages": 0, "assets": 0,
                            "mapped": 0, "missing": 0, "stray": 0,
                            "balanced": False, "error": str(e)})

    # Final summary report: succeeded vs. persistent errors
    print("\n" + "=" * 64)
    print("BATCH SUMMARY")
    print("=" * 64)
    ok = [r for r in results if not r["error"] and r["stray"] == 0 and r["balanced"]]
    bad = [r for r in results if r not in ok]
    for r in results:
        status = "OK  " if r in ok else "FAIL"
        line = (f"  [{status}] {r['name']}: {r['pages']} pages, {r['assets']} assets, "
                f"{r['mapped']} mapped, {r['missing']} missing, {r['stray']} stray")
        if r["error"]:
            line += f"  | error: {r['error']}"
        print(line)
    print("-" * 64)
    print(f"  Succeeded: {len(ok)}/{len(results)}    Failed: {len(bad)}/{len(results)}")
    if bad:
        print("  Persistent errors in:", ", ".join(r["name"] for r in bad))

if __name__ == "__main__":
    main()
