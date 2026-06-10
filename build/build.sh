#!/usr/bin/env bash
# build.sh -- one command to compile a poster, render a preview, and run the
# deterministic overflow check.  Use this instead of calling pdflatex by hand.
#
#   ./build.sh                          # builds newest-poster.tex (the canonical poster)
#   ./build.sh irradiation_poster.tex   # builds the stable reference poster
#   ./build.sh drafts/my_draft.tex      # builds a draft; outputs stay in drafts/
#
# Output conventions:
#   newest-poster.tex, irradiation_poster.tex  → build/         (root outputs)
#   drafts/*.tex                               → build/drafts/  (contained)
#   Previews always land in:  build/_prev/     (root) or build/drafts/_prev/ (drafts)
#
# It does three things that matter (see AGENTS.md §3):
#   1. Deletes any stale/locked PDF FIRST to avoid the "stale preview" trap.
#   2. Compiles twice (tikzposter + references need two passes).
#   3. Renders a fixed-size PNG preview and runs check_fit.py.
#      A change is NOT done until check_fit.py prints "RESULT: PASS".
set -eu

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

TEX="${1:-newest-poster.tex}"
FILENAME="$(basename "$TEX")"
BASENAME="${FILENAME%.tex}"
DIRNAME="$(dirname "$TEX")"    # "." for root files, "drafts" for draft files

# ---------------------------------------------------------------------------
#  Determine output directory and preview directory
#  Drafts stay self-contained in build/drafts/.
# ---------------------------------------------------------------------------
if [ "$DIRNAME" = "." ]; then
    OUTDIR="."
    PREVDIR="./_prev"
else
    OUTDIR="$DIRNAME"
    PREVDIR="${DIRNAME}/_prev"
fi

mkdir -p "$PREVDIR"

echo ":: removing any stale/locked ${OUTDIR}/${BASENAME}.pdf"
rm -f "${OUTDIR}/${BASENAME}.pdf"

# ---------------------------------------------------------------------------
#  Compilation
#  Prefer Antigravity/Claude latex-document-skill wrapper if installed;
#  fall back to plain pdflatex so this script also works in bare environments.
# ---------------------------------------------------------------------------
SKILL="$HOME/.claude/skills/latex-document-skill/scripts/compile_latex.sh"
if [ -x "$SKILL" ] || [ -f "$SKILL" ]; then
    echo ":: compiling via latex-document-skill"
    bash "$SKILL" "$TEX" --preview --preview-dir "$PREVDIR"
else
    echo ":: compiling via pdflatex (x2)"
    pdflatex -interaction=nonstopmode -halt-on-error "$TEX" >/dev/null
    pdflatex -interaction=nonstopmode -halt-on-error "$TEX" >/dev/null

    # pdflatex writes outputs to the CWD (build/). Move them to OUTDIR when
    # the source is in a subdirectory (e.g. drafts/).
    if [ "$OUTDIR" != "." ]; then
        mv "${BASENAME}.pdf" "${BASENAME}.log" "${BASENAME}.aux" \
           "${BASENAME}.out" "$OUTDIR/" 2>/dev/null || true
    fi

    # Render PNG preview: longest side = 1200 px → ~849×1200 for A0 portrait.
    pdftoppm -png -scale-to 1200 "${OUTDIR}/${BASENAME}.pdf" "${PREVDIR}/${BASENAME}"
    # pdftoppm names files BASE-1.png; normalise if padding was added.
    [ -f "${PREVDIR}/${BASENAME}-1.png" ] || \
        mv "${PREVDIR}/${BASENAME}"-*.png "${PREVDIR}/${BASENAME}-1.png" 2>/dev/null || true
fi

echo
echo ":: fit check (preview: ${PREVDIR}/${BASENAME}-1.png)"

# Use the venv (created by setup.sh) when available for Pillow/numpy support.
VENV="$HERE/venv"
if   [ -x "$VENV/bin/python3" ]; then PY="$VENV/bin/python3"
elif [ -x "$VENV/bin/python"  ]; then PY="$VENV/bin/python"
else                                   PY="python3"
fi

# check_fit.py is always in the build root. Run it WITHOUT aborting (set +e) so
# the maintenance step below still archives + cleans even on a FAIL verdict; the
# fit verdict is preserved and used as this script's exit code.
set +e
"$PY" check_fit.py "${PREVDIR}/${BASENAME}-1.png"
FIT=$?
set -e

# ---------------------------------------------------------------------------
#  Maintenance (see maintenance.py): archive the built poster into drafts/ under
#  a uniform poster_<NNN>_<datetime> name, then remove LaTeX temp/aux litter.
#
#  Auto-archive fires only for ROOT builds (newest-poster / irradiation_poster);
#  draft builds already live in drafts/ so re-archiving them would duplicate.
#    ARCHIVE=0        disable auto-archiving for this build
#    ARCHIVE_KEEP=N   keep only the newest N archives (default 20)
# ---------------------------------------------------------------------------
echo
if [ "$DIRNAME" = "." ] && [ "${ARCHIVE:-1}" != "0" ]; then
    echo ":: archiving build into ${OUTDIR}/drafts/"
    "$PY" maintenance.py archive "${OUTDIR}/${BASENAME}.pdf" \
        --preview "${PREVDIR}/${BASENAME}-1.png" --tex "$TEX" \
        --drafts-dir drafts --prune-keep "${ARCHIVE_KEEP:-20}" || true
fi
"$PY" maintenance.py clean || true

exit $FIT
