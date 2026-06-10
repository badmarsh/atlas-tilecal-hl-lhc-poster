#!/usr/bin/env bash
# build.sh -- one command to compile the poster, render a preview, and run the
# deterministic overflow check. Use this instead of calling pdflatex by hand.
#
#   ./build.sh                      # builds irradiation_poster.tex
#   ./build.sh some_other.tex       # builds a different .tex in this dir
#
# It does three things that matter (see AGENTS.md "Gotchas"):
#   1. Deletes any stale/locked PDF FIRST. If the PDF is open in a viewer the
#      compile fails with "I can't write on file" and you silently keep looking
#      at an OLD preview. Removing it up front prevents that trap.
#   2. Compiles twice (tikzposter + references need two passes).
#   3. Renders a fixed-size PNG preview and runs check_fit.py.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
TEX="${1:-irradiation_poster.tex}"
BASE="${TEX%.tex}"
PREVDIR="./_prev"

echo ":: removing any stale/locked ${BASE}.pdf"
rm -f "${BASE}.pdf"

# Prefer Marek's latex-document-skill compiler if present (auto-installs
# texlive/poppler, filters logs); otherwise fall back to plain pdflatex so this
# script also works for Gemini/Antigravity and bare environments.
SKILL="/home/ubuntu/.claude/skills/latex-document-skill/scripts/compile_latex.sh"
if [ -x "$SKILL" ] || [ -f "$SKILL" ]; then
    echo ":: compiling via latex-document-skill"
    bash "$SKILL" "$TEX" --preview --preview-dir "$PREVDIR"
else
    echo ":: compiling via pdflatex (x2)"
    pdflatex -interaction=nonstopmode -halt-on-error "$TEX" >/dev/null
    pdflatex -interaction=nonstopmode -halt-on-error "$TEX" >/dev/null
    mkdir -p "$PREVDIR"
    # -scale-to 1200 => longest side 1200px => ~849x1200 for A0 portrait,
    # the resolution check_fit.py was calibrated against (though it is
    # resolution-independent anyway).
    pdftoppm -png -scale-to 1200 "${BASE}.pdf" "${PREVDIR}/${BASE}"
    # pdftoppm names files BASE-1.png already; normalise if it added padding.
    [ -f "${PREVDIR}/${BASE}-1.png" ] || mv "${PREVDIR}/${BASE}"-*.png "${PREVDIR}/${BASE}-1.png" 2>/dev/null || true
fi

echo
echo ":: fit check"
python3 check_fit.py "${PREVDIR}/${BASE}-1.png"
