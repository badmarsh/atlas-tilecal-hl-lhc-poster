#!/usr/bin/env python3
"""
pptx_export.py -- PPTX export pipeline step (PPT Master integration).

Bridges this poster repo to the vendored PPT Master skill
(`skills/ppt-master/`) so the poster's source PDFs can become a natively
editable PowerPoint deck.

IMPORTANT -- this is a *prepare + export* wrapper, NOT a one-shot converter.
PPT Master's SKILL.md (rule 9) forbids script-generated SVG pages: every slide
SVG is hand-authored by the main agent with full upstream context. So the flow
is three stages, and the middle one is yours/the agent's:

    1. prepare  -> PDFs -> Markdown + an empty project skeleton  (this script)
    2. author   -> agent writes slide SVGs into <project>/svg_final/  (ppt-master skill)
    3. export   -> SVGs -> editable .pptx in <project>/exports/  (this script)

Usage:
    python pipeline/pptx_export.py prepare [--source sources/pdf] [--name poster]
    # ... invoke the `ppt-master` skill to author SVGs into build/pptx/<name>/svg_final/ ...
    python pipeline/pptx_export.py export [--name poster] [--stage final]

Outputs land under build/pptx/<name>/ (git-ignored, regenerable).
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "ppt-master"
PDF_TO_MD = SKILL_DIR / "scripts" / "source_to_md" / "pdf_to_md.py"
SVG_TO_PPTX = SKILL_DIR / "scripts" / "svg_to_pptx.py"
DEFAULT_SOURCE = REPO_ROOT / "sources" / "pdf"
OUT_ROOT = REPO_ROOT / "build" / "pptx"


def _require(path: Path, hint: str) -> None:
    """Fail fast with an actionable message if a vendored script is missing."""
    if not path.exists():
        sys.exit(
            f"ERROR: missing {path}.\n"
            f"       {hint}"
        )


def _run(cmd: list[str]) -> None:
    """Run a subprocess, streaming output, aborting the step on failure."""
    logger.info("RUN: %s", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        sys.exit(f"ERROR: command failed (exit {result.returncode}): {cmd[0]}")


def prepare(source: Path, name: str) -> Path:
    """Convert source PDFs to Markdown and scaffold a PPT Master project."""
    _require(PDF_TO_MD, "Vendor the ppt-master skill into skills/ppt-master/ first.")
    if not source.exists():
        sys.exit(f"ERROR: source not found: {source}")

    project = OUT_ROOT / name
    markdown_dir = project / "markdown"
    svg_final = project / "svg_final"
    notes = project / "notes"
    for d in (markdown_dir, svg_final, notes):
        d.mkdir(parents=True, exist_ok=True)

    # pdf_to_md.py accepts a file or a directory of PDFs.
    _run([sys.executable, str(PDF_TO_MD), str(source), "-o", str(markdown_dir)])

    readme = project / "PROJECT.md"
    readme.write_text(
        f"# PPT Master project: {name}\n\n"
        f"Source Markdown: `markdown/`  (from {source})\n\n"
        "## Next step (agent-driven, NOT scripted)\n\n"
        "Invoke the `ppt-master` skill to author slide SVGs into `svg_final/`,\n"
        "one page at a time (SKILL.md rule 9 forbids batch/script generation).\n"
        "Optionally add per-slide speaker notes as `notes/<NN>_<name>.md`.\n\n"
        "## Then export\n\n"
        f"    python pipeline/pptx_export.py export --name {name}\n\n"
        "The editable .pptx is written to `exports/`.\n",
        encoding="utf-8",
    )

    logger.info("Prepared project at %s", project)
    logger.info("Markdown written to %s", markdown_dir)
    logger.info(
        "NEXT: use the ppt-master skill to author SVGs into %s, then run "
        "`python pipeline/pptx_export.py export --name %s`",
        svg_final, name,
    )
    return project


def export(name: str, stage: str) -> Path:
    """Convert authored SVGs in <project>/svg_<stage> to an editable .pptx."""
    _require(SVG_TO_PPTX, "Vendor the ppt-master skill into skills/ppt-master/ first.")
    project = OUT_ROOT / name
    if not project.exists():
        sys.exit(f"ERROR: project not found: {project}. Run `prepare` first.")

    svg_dir = project / f"svg_{stage}" if stage in ("final", "output") else project / stage
    svgs = sorted(svg_dir.glob("*.svg")) if svg_dir.exists() else []
    if not svgs:
        sys.exit(
            f"ERROR: no SVGs in {svg_dir}.\n"
            "       Author slide SVGs with the ppt-master skill before exporting."
        )

    _run([sys.executable, str(SVG_TO_PPTX), str(project), "-s", stage])

    exports = project / "exports"
    produced = sorted(exports.glob("*.pptx")) if exports.exists() else []
    if produced:
        logger.info("Exported: %s", produced[-1])
    else:
        logger.warning("Export ran but no .pptx found under %s", exports)
    return exports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PPTX export pipeline step (PPT Master integration).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="PDFs -> Markdown + project skeleton")
    p_prep.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help=f"PDF file or directory (default: {DEFAULT_SOURCE})")
    p_prep.add_argument("--name", default="poster", help="Project name (default: poster)")

    p_exp = sub.add_parser("export", help="Authored SVGs -> editable .pptx")
    p_exp.add_argument("--name", default="poster", help="Project name (default: poster)")
    p_exp.add_argument("--stage", default="final", choices=["final", "output"],
                       help="SVG source stage: final=svg_final, output=svg_output")

    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source.resolve(), args.name)
    elif args.command == "export":
        export(args.name, args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
