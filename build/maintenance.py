#!/usr/bin/env python3
"""
maintenance.py -- housekeeping for the A0 tikzposter build outputs.

WHY THIS EXISTS
    Every build leaves LaTeX aux litter (.aux/.log/.out/...) behind and produces
    a PDF whose name (newest-poster.pdf / irradiation_poster.pdf) is overwritten
    on the next build. Without housekeeping, draft versions pile up under ad-hoc
    names (poster_1, poster_v3_final, ...) and the build tree fills with temp
    files. This tool gives one deterministic way to:

      * archive a freshly built PDF into build/drafts/ under a uniform, sortable
        name  ->  poster_<NNN>_<YYYYMMDD-HHMMSS>.<ext>
      * remove LaTeX temp / scratch files
      * migrate the pre-existing inconsistently-named drafts into the scheme
      * prune old archives so build/drafts/ does not grow without bound

    Stdlib only (os/shutil/re/argparse/datetime/pathlib) so it runs in a bare
    environment -- no Pillow/numpy needed (unlike check_fit.py).

NAMING SCHEME
    poster_<NNN>_<YYYYMMDD-HHMMSS>   (3-digit monotonic index + build timestamp)
    A "bundle" shares one base name across:
        drafts/<base>.pdf            the built poster
        drafts/<base>.tex            a snapshot of the source it was built from
        drafts/_prev/<base>-1.png    the preview PNG

USAGE
    python3 maintenance.py archive <pdf> [--preview PNG] [--tex SRC]
                                         [--drafts-dir DIR] [--move]
                                         [--prune-keep N] [--dry-run]
    python3 maintenance.py clean   [--root DIR ...] [--dry-run]
    python3 maintenance.py migrate [--drafts-dir DIR] [--dry-run]
    python3 maintenance.py prune   --keep N [--drafts-dir DIR] [--dry-run]

    Exit code 0 on success, 1 on error.
"""
import argparse
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Canonical archive name:  poster_<NNN>_<YYYYMMDD-HHMMSS>
ARCHIVE_RE = re.compile(r"^poster_(\d{3,})_(\d{8}-\d{6})$")

# LaTeX temp / aux extensions removed by `clean`. Deliberately excludes .tex,
# .pdf, .png -- those are real outputs or sources.
TEMP_EXTS = (
    ".aux", ".log", ".out", ".fls", ".fdb_latexmk",
    ".synctex.gz", ".nav", ".snm", ".toc", ".vrb", ".bbl", ".blg",
)

PREVIEW_SUFFIX = "-1.png"   # pdftoppm names previews <base>-1.png


# ---------------------------------------------------------------------------
#  Naming helpers
# ---------------------------------------------------------------------------
def timestamp(when=None):
    """Return a YYYYMMDD-HHMMSS stamp for `when` (a datetime) or now."""
    return (when or datetime.now()).strftime("%Y%m%d-%H%M%S")


def _iter_archives(drafts_dir):
    """Yield (index, base_name, Path) for every poster_<NNN>_<ts>.pdf bundle.

    Keyed on the .pdf because that is the artifact an archive always has; the
    .tex snapshot and preview are companions that may or may not be present.
    """
    d = Path(drafts_dir)
    if not d.is_dir():
        return
    for p in sorted(d.glob("poster_*.pdf")):
        m = ARCHIVE_RE.match(p.stem)
        if m:
            yield int(m.group(1)), p.stem, p


def next_index(drafts_dir):
    """Lowest unused 3-digit archive index in `drafts_dir` (max existing + 1)."""
    indices = [idx for idx, _, _ in _iter_archives(drafts_dir)]
    return (max(indices) + 1) if indices else 1


def _base_name(index, when=None):
    return f"poster_{index:03d}_{timestamp(when)}"


# ---------------------------------------------------------------------------
#  Small filesystem helpers (dry-run aware)
# ---------------------------------------------------------------------------
def _do(action, src, dst, dry_run, move=False):
    """Copy or move `src` -> `dst`, honouring --dry-run. Returns True if acted."""
    verb, past = ("move", "moved") if move else ("copy", "copied")
    if dry_run:
        print(f"  [dry-run] {verb} {src} -> {dst}")
        return True
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    if move:
        shutil.move(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
    print(f"  {past} {src} -> {dst}")
    return True


def _remove(path, dry_run):
    if dry_run:
        print(f"  [dry-run] remove {path}")
        return True
    try:
        os.remove(path)
        print(f"  removed {path}")
        return True
    except OSError as e:
        print(f"  [WARN] could not remove {path}: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
#  archive
# ---------------------------------------------------------------------------
def archive(pdf, drafts_dir="drafts", preview=None, tex=None,
            move=False, prune_keep=None, dry_run=False):
    """Archive a built PDF (+ optional preview + source snapshot) into drafts/.

    The PDF is moved or copied; the .tex source is always COPIED (it stays the
    live working file); the preview is moved or copied alongside the PDF.
    """
    pdf = Path(pdf)
    if not pdf.is_file():
        print(f"ERROR: PDF not found: {pdf}", file=sys.stderr)
        return 1

    drafts = Path(drafts_dir)
    prev_dir = drafts / "_prev"
    base = _base_name(next_index(drafts))

    print(f":: archiving {pdf.name} -> {drafts}/{base}.pdf"
          + (" (move)" if move else " (copy)"))

    _do("pdf", pdf, drafts / f"{base}.pdf", dry_run, move=move)

    if tex:
        tex = Path(tex)
        if tex.is_file():
            # Source snapshot is always a copy -- the original keeps being edited.
            _do("tex", tex, drafts / f"{base}.tex", dry_run, move=False)
        else:
            print(f"  [WARN] --tex {tex} not found; skipping source snapshot",
                  file=sys.stderr)

    if preview:
        preview = Path(preview)
        if preview.is_file():
            _do("png", preview, prev_dir / f"{base}{PREVIEW_SUFFIX}",
                dry_run, move=move)
        else:
            print(f"  [WARN] --preview {preview} not found; skipping",
                  file=sys.stderr)

    print(f":: archived as {base}")

    if prune_keep is not None:
        prune(drafts_dir, keep=prune_keep, dry_run=dry_run)
    return 0


# ---------------------------------------------------------------------------
#  clean
# ---------------------------------------------------------------------------
def _is_preview(path):
    """True for files living in a _prev/ directory (real previews -- keep)."""
    return "_prev" in Path(path).parts


def clean(roots=None, dry_run=False):
    """Remove LaTeX temp/aux files and scratch crops under each root.

    Scope per root (non-recursive except for the explicit temp scan): files with
    a TEMP_EXTS extension, plus scratch crops matching `_*.png` and `tmp_*` at
    the root. Never deletes anything inside a _prev/ dir, nor .tex/.pdf/assets.
    """
    here = Path(__file__).resolve().parent
    if not roots:
        roots = [here, here / "drafts"]

    removed = 0
    print(":: cleaning temp/aux files")
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        candidates = []
        for ext in TEMP_EXTS:
            candidates.extend(root.glob(f"*{ext}"))
        # Scratch crops at the root (NOT previews in _prev/).
        candidates.extend(root.glob("_*.png"))
        candidates.extend(root.glob("tmp_*"))
        for c in candidates:
            if not c.is_file() or _is_preview(c):
                continue
            if _remove(c, dry_run):
                removed += 1
    if removed == 0 and not dry_run:
        print("  nothing to clean")
    return 0


# ---------------------------------------------------------------------------
#  prune
# ---------------------------------------------------------------------------
def prune(drafts_dir="drafts", keep=20, dry_run=False):
    """Keep only the `keep` highest-indexed archives; delete older bundles."""
    archives = sorted(_iter_archives(drafts_dir), key=lambda t: t[0])
    excess = archives[:-keep] if keep > 0 else archives
    if not excess:
        return 0
    drafts = Path(drafts_dir)
    prev_dir = drafts / "_prev"
    print(f":: pruning {len(excess)} archive(s), keeping newest {keep}")
    for _idx, base, pdf_path in excess:
        for companion in (pdf_path,
                          drafts / f"{base}.tex",
                          prev_dir / f"{base}{PREVIEW_SUFFIX}"):
            if companion.exists():
                _remove(companion, dry_run)
    return 0


# ---------------------------------------------------------------------------
#  migrate -- one-time rename of the legacy ad-hoc drafts into the scheme
# ---------------------------------------------------------------------------
def migrate(drafts_dir="drafts", dry_run=False):
    """Rename pre-existing poster_N / poster_vN_final drafts into the scheme.

    Groups each legacy base (.tex/.pdf + _prev/<base>-1.png) under one new
    poster_<NNN>_<ts> name. Timestamp comes from the file's mtime; indices are
    assigned in a stable version order. Files already in the new scheme are
    skipped.
    """
    drafts = Path(drafts_dir)
    if not drafts.is_dir():
        print(f"ERROR: drafts dir not found: {drafts}", file=sys.stderr)
        return 1
    prev_dir = drafts / "_prev"

    # Collect legacy bases from .tex and .pdf files, skipping the new scheme.
    legacy = set()
    for p in list(drafts.glob("*.tex")) + list(drafts.glob("*.pdf")):
        if ARCHIVE_RE.match(p.stem):
            continue
        legacy.add(p.stem)

    if not legacy:
        print(":: migrate: no legacy drafts to rename")
        return 0

    def sort_key(stem):
        """Stable version order: numeric suffix first, then lexical."""
        nums = re.findall(r"\d+", stem)
        return (int(nums[-1]) if nums else 0, stem)

    idx = next_index(drafts)
    print(f":: migrating {len(legacy)} legacy draft(s) starting at index {idx:03d}")
    for stem in sorted(legacy, key=sort_key):
        # Anchor the timestamp on whichever artifact exists (prefer .pdf).
        src_pdf = drafts / f"{stem}.pdf"
        src_tex = drafts / f"{stem}.tex"
        src_png = prev_dir / f"{stem}{PREVIEW_SUFFIX}"
        anchor = src_pdf if src_pdf.exists() else (src_tex if src_tex.exists() else None)
        if anchor is None:
            continue
        when = datetime.fromtimestamp(anchor.stat().st_mtime)
        base = _base_name(idx, when)
        print(f"  {stem}  ->  {base}")
        for src, dst in ((src_pdf, drafts / f"{base}.pdf"),
                         (src_tex, drafts / f"{base}.tex"),
                         (src_png, prev_dir / f"{base}{PREVIEW_SUFFIX}")):
            if src.exists():
                _do("rename", src, dst, dry_run, move=True)
        idx += 1
    return 0


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="maintenance.py",
        description="Archive built posters, clean temp files, migrate/prune drafts.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("archive", help="archive a built PDF into drafts/")
    a.add_argument("pdf", help="path to the built PDF")
    a.add_argument("--preview", help="preview PNG to carry alongside")
    a.add_argument("--tex", help="source .tex to snapshot alongside")
    a.add_argument("--drafts-dir", default="drafts")
    a.add_argument("--move", action="store_true",
                   help="move the PDF/preview instead of copying")
    a.add_argument("--prune-keep", type=int, default=None,
                   help="after archiving, keep only the newest N archives")
    a.add_argument("--dry-run", action="store_true")

    c = sub.add_parser("clean", help="remove LaTeX temp/aux + scratch files")
    c.add_argument("--root", action="append", default=None,
                   help="directory to clean (repeatable; default build/ + drafts/)")
    c.add_argument("--dry-run", action="store_true")

    m = sub.add_parser("migrate", help="rename legacy drafts into the scheme")
    m.add_argument("--drafts-dir", default="drafts")
    m.add_argument("--dry-run", action="store_true")

    pr = sub.add_parser("prune", help="keep only the newest N archives")
    pr.add_argument("--keep", type=int, required=True)
    pr.add_argument("--drafts-dir", default="drafts")
    pr.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "archive":
        return archive(args.pdf, drafts_dir=args.drafts_dir,
                       preview=args.preview, tex=args.tex, move=args.move,
                       prune_keep=args.prune_keep, dry_run=args.dry_run)
    if args.cmd == "clean":
        return clean(roots=args.root, dry_run=args.dry_run)
    if args.cmd == "migrate":
        return migrate(drafts_dir=args.drafts_dir, dry_run=args.dry_run)
    if args.cmd == "prune":
        return prune(drafts_dir=args.drafts_dir, keep=args.keep,
                     dry_run=args.dry_run)
    return 1


if __name__ == "__main__":
    sys.exit(main())
