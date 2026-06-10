#!/usr/bin/env python3
"""
check_fit.py -- deterministic overflow detector for the A0 tikzposter.

WHY THIS EXISTS
    tikzposter does NOT auto-fit content. Blocks stack top-down inside each
    column; if a column's content is taller than the page, the last card runs
    straight OFF the bottom edge -- its rounded bottom border and (often) its
    figure caption are clipped. LaTeX reports NO error for this. The PDF
    compiles "successfully" and looks fine unless you inspect the very bottom of
    each column. Eyeballing a downscaled preview is unreliable (we got it wrong
    twice). This script measures it instead.

WHAT IT CHECKS
    For each of the 3 columns it finds the lowest "content" pixel row (any
    non-white pixel: red border, pink card body, or dark text/figure). A
    properly closed card ends with its red bottom border followed by a white
    page margin, so the lowest content row sits clearly above the page edge. A
    clipped card has body/border running to the last pixel row.

    Resolution-independent: thresholds are fractions of image height, so it
    works whatever DPI the preview was rendered at.

USAGE
    python3 check_fit.py [preview.png]
        default preview: ./_prev/irradiation_poster-1.png
    Exit code 0 = all columns fit, 1 = at least one column clipped/too tight.
"""
import sys
import numpy as np
from PIL import Image

# Column x-ranges as fractions of image width. Generous so the card's vertical
# side-borders are included -- a clipped card's verticals run to the page edge,
# which is exactly what we want to catch.
COLUMNS = {
    "col1 (left)":   (0.02, 0.32),
    "col2 (middle)": (0.35, 0.65),
    "col3 (right)":  (0.68, 0.98),
}

# Verdict thresholds, as fraction of page height measured from the top.
# A fitting card's lowest content row is above FAIL_AT; a clipped one is below.
FAIL_AT = 0.992   # lowest content below this => border is off-page (CLIPPED)
WARN_AT = 0.978   # below this => fits but margin is tight, rebalance soon


def lowest_content_row(rgb, x0, x1):
    """Lowest row index (0=top) that has >3 non-white pixels in [x0,x1)."""
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    nonwhite = ~((r > 240) & (g > 240) & (b > 240))
    counts = nonwhite[:, x0:x1].sum(axis=1)
    rows = np.where(counts > 3)[0]
    return int(rows[-1]) if len(rows) else -1


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "./_prev/irradiation_poster-1.png"
    try:
        rgb = np.array(Image.open(path).convert("RGB")).astype(int)
    except FileNotFoundError:
        print(f"ERROR: preview not found: {path}\n"
              f"       Build first (./build.sh), then re-run.", file=sys.stderr)
        return 2
    H, W, _ = rgb.shape
    print(f"preview: {path}  ({W}x{H})")
    print(f"thresholds: FAIL below y={int(FAIL_AT*H)}, WARN below y={int(WARN_AT*H)} "
          f"(page height {H})\n")

    any_fail = False
    for name, (fx0, fx1) in COLUMNS.items():
        y = lowest_content_row(rgb, int(W * fx0), int(W * fx1))
        frac = y / H if y >= 0 else 0.0
        margin = H - y if y >= 0 else H
        if y < 0:
            verdict = "EMPTY?"
        elif frac >= FAIL_AT:
            verdict = "FAIL (clipped -- bottom border off-page)"
            any_fail = True
        elif frac >= WARN_AT:
            verdict = "WARN (fits, but margin tight)"
        else:
            verdict = "PASS"
        print(f"  {name:14s} lowest content y={y:5d}  margin={margin:4d}px "
              f"({frac*100:5.1f}% down)  -> {verdict}")

    print()
    if any_fail:
        print("RESULT: FAIL -- at least one card overflows the page. "
              "Reclaim vertical space in the offending column (see AGENTS.md).")
        return 1
    print("RESULT: PASS -- every card closes inside the page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
