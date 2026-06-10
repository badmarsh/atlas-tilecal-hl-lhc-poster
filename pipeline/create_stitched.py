#!/usr/bin/env python3
"""
create_stitched.py -- stitch each slide's ground-truth render, its extracted
assets, and its TeX section into one tall PNG for eyeball QA.

Consumes .verify_scratch/prep_info.json produced by prep_vision_qa.py and writes
.verify_scratch/<base>_stitched/slide_NN.png.

    python3 ../../pipeline/create_stitched.py [--scratch-dir DIR]
"""
import argparse
import json
import os
import sys

import PIL.Image
from PIL import ImageDraw, ImageFont


def load_font(size=14):
    """A truetype font if one is findable, else PIL's bitmap default.

    The default font ignores size and is small, but it always exists -- so the
    stitcher never crashes on a headless box with no fonts installed.
    """
    for name in ("DejaVuSansMono.ttf", "DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def stitch_slide(slide, font):
    """Build one stitched PIL image for a slide, or None if nothing to show."""
    tex = slide.get("tex", "")
    gt_png = slide.get("gt_png", "")
    assets = slide.get("assets", [])

    images = []
    if gt_png and os.path.exists(gt_png):
        gt_img = PIL.Image.open(gt_png).convert("RGB")
        w, h = gt_img.size
        gt_img = gt_img.resize((1000, max(1, int(1000 * h / w))))
        images.append(("GROUND TRUTH", gt_img))

    for i, asset in enumerate(assets):
        if not isinstance(asset, str) or not os.path.exists(asset):
            continue

        try:
            # verify() must run on a fresh, unloaded handle; it leaves the image
            # unusable, so reopen for the actual decode.
            PIL.Image.open(asset).verify()
            a_img = PIL.Image.open(asset).convert("RGB")
        except Exception:
            continue
        w, h = a_img.size
        if w > 800:
            a_img = a_img.resize((800, max(1, int(800 * h / w))))
        images.append((f"ASSET {i + 1}: {os.path.basename(asset)}", a_img))

    if not images:
        return None

    total_height = sum(img.size[1] + 40 for _, img in images) + 100
    max_width = max(img.size[0] for _, img in images)
    max_width = max(max_width, 1000)

    char_h = 15
    text_height = len(tex.split("\n")) * char_h + 50

    final_img = PIL.Image.new("RGB", (max_width + 50, total_height + text_height), "white")
    draw = ImageDraw.Draw(final_img)

    y_offset = 20
    for title, img in images:
        draw.text((20, y_offset), title, fill="red", font=font)
        y_offset += 20
        final_img.paste(img, (20, y_offset))
        y_offset += img.size[1] + 20

    draw.multiline_text((20, y_offset), "TEX SECTION:\n" + tex, fill="black", font=font)
    return final_img


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scratch-dir", default=".verify_scratch",
                        help="scratch dir holding prep_info.json (default: .verify_scratch)")
    args = parser.parse_args(argv)

    info_file = os.path.join(args.scratch_dir, "prep_info.json")
    if not os.path.exists(info_file):
        print(f"ERROR: {info_file} not found. Run prep_vision_qa.py first.",
              file=sys.stderr)
        return 1

    with open(info_file, "r", encoding="utf-8") as f:
        report = json.load(f)

    font = load_font()
    made = 0
    for base_name, pdf_info in report.items():
        stitched_dir = os.path.join(args.scratch_dir, f"{base_name}_stitched")
        os.makedirs(stitched_dir, exist_ok=True)
        for slide in pdf_info.get("slides", []):
            slide_num = slide.get("slide_num", 0)
            try:
                img = stitch_slide(slide, font)
            except Exception as e:
                print(f"  [WARN] {base_name} slide {slide_num}: {e}", file=sys.stderr)
                continue
            if img is None:
                continue
            img.save(os.path.join(stitched_dir, f"slide_{slide_num:02d}.png"))
            made += 1

    print(f"Stitched images created ({made}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
