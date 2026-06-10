# Task: Vision QA of PDF→LaTeX Slide Extraction (Gemini 3.1 Pro · Antigravity)

You are an autonomous agent with terminal, filesystem, and native vision. Verify,
**slide-by-slide for every PDF**, that the extraction pipeline (`pdf_pipeline.py`)
produced a `*_mapped.tex` whose **text** and **linked image assets** faithfully
represent the original slide. You will render the source slides and the extracted
assets to images yourself, **look at them with your own vision**, compare against
the generated LaTeX, and write a verification report.

This is **read-only QA**. Do NOT modify `pdf_pipeline.py`, any `*_mapped.tex`, or
anything under `Output_*/`. The only files you create are the report
(`verification_report.json`, `verification_report.md`) and throwaway PNGs in a
scratch dir (`.verify_scratch/`).

---

## Environment

Working directory contains:
- `<base>.pdf` — the source PDFs (6 of them).
- `Output_<base>/` for each, with:
  - `<base>_mapped.tex` — LaTeX: text + `\includegraphics{assets/...}` links.
  - `slides/slide_<NN>.pdf` — each source page burst to a single-page PDF (ground truth).
  - `assets/<base>_slide_<N>_item_<m>.{png|jpeg|pdf}` — extracted figures.

Tooling: Python is available. If `import fitz` (PyMuPDF) fails, install it
(`pip install pymupdf`) or fall back to `pdftoppm`/ImageMagick for rendering.
`pdfinfo` and `pdflatex` (TeX Live) are present.

The pipeline already guarantees, in code: every `\includegraphics` path exists,
no stray `PLACEHOLDER_` remains, `figure` environments are balanced, and all six
`*_mapped.tex` compile. **Your job is the visual/semantic layer those checks
cannot see** — do not re-verify them except to note if something contradicts.

---

## Workflow

Do this for **all 6 PDFs**, every slide:

1. **Enumerate.** List `Output_*/` dirs. For each, read `<base>_mapped.tex` and
   split it on `\section*{Slide ` into per-slide sections. Get the source page
   count from `slides/` (or `pdfinfo <base>.pdf`).

2. **Map assets to slides.** For each slide section, collect the asset paths from
   its `\includegraphics{...}` lines, in document order.

3. **Render to PNG** into `.verify_scratch/`:
   - each `slides/slide_<NN>.pdf` → `slide_<NN>.png` at ~150 DPI (the GROUND TRUTH image);
   - each referenced asset: `.pdf` assets → PNG at ~150 DPI; copy `.png`/`.jpeg` as-is.

4. **Verify with vision.** For each slide, OPEN and actually look at the slide
   image and its asset images, read the slide's `TEX_SECTION`, and evaluate the
   five dimensions in the rubric below. Be specific: quote text, name figures,
   give locations ("bottom-left schematic", "top-right photo").

5. **Record** one JSON object per slide (schema in §Output). Aggregate per PDF,
   then overall. Write `verification_report.json` (full detail) and
   `verification_report.md` (human summary: a table of slides-pass / issues per
   PDF, then every critical/major issue with its slide and one-line description).

6. **Clean up** `.verify_scratch/` when done (or leave it if it aids review — say which).

Process slides in batches; keep going until all 39-ish slides across all 6 PDFs
are done. Do not stop early or sample — cover every slide.

---

## Rubric — five dimensions, pass/fail + note each

- **A. TEXT_FIDELITY** — Does `TEX_SECTION` capture the slide's meaningful text
  accurately? FAIL if substantive text on the slide is missing from the TeX, or
  text is garbled, characters are wrong, math/symbols are semantically wrong, or
  words merged/split so meaning changes. Reading-order changes that preserve
  meaning, reformatting, line-wrapping, and LaTeX escaping are FINE.

- **B. ASSET_MATCH** — Does each linked asset visually correspond to a real
  figure/graph/table/diagram/photo actually on this slide? FAIL for an asset that
  matches nothing (wrong crop / hallucinated), is badly cut off, or is the wrong
  figure for its position.

- **C. COMPLETENESS** — Is every SUBSTANTIVE visual on the slide (figure, graph,
  plot, table, diagram, photo, schematic) represented by at least one asset? FAIL
  and list each MISSING visual.

- **D. NO_JUNK** — Are all assets genuine content, not decoration? FAIL if an
  asset is a logo, institutional crest, author headshot, icon, bullet glyph,
  title banner, horizontal rule, or a tiny sliver/fragment.

- **E. PLACEMENT_ORDER** — Do figures appear in the TeX at a position roughly
  consistent with the slide's top-to-bottom, left-to-right reading order? Minor
  reordering is FINE; FAIL only if clearly scrambled enough to confuse a reader.

### Pipeline-specific rules (apply so you don't raise false alarms)
- Decorative elements are **intentionally excluded**. Do NOT report missing logos,
  university crests, author headshots, page numbers, banner-image titles, icons,
  or rules under COMPLETENESS.
- Vector figures are saved as cropped regions and MAY over-include adjacent text
  or a neighbouring photo. If the intended figure is present, over-inclusion is at
  most MINOR, never critical.
- The same photo may appear BOTH as a standalone raster asset AND inside a vector
  crop. Duplication is MINOR, not a failure.
- Non-ASCII text was converted to LaTeX (× → `$\times$`, 𝑎 → `a`, accents →
  `\'e`). Judge SEMANTIC correctness, not glyph identity. A dropped rare symbol is
  MINOR unless it changes a quantity or unit.
- Title/divider slides with little text and no figures should PASS if the TeX
  reflects that.

### Severity
- **critical** — a real figure/table/graph is missing; an asset is the wrong/
  hallucinated image; or text is so wrong a reader would be misled.
- **major** — a real visual only partially captured; a meaningful text block
  missing; or a junk asset that is clearly not content.
- **minor** — over-inclusion, duplication, dropped rare symbol, slight reorder.

Be precise and conservative: only report problems you can actually see. When
unsure, lower `confidence` rather than inventing an issue.

---

## Output

### Per slide (collect into `verification_report.json`)
```json
{
  "pdf": "ATL-TILECAL-SLIDE-2025-552",
  "slide": 4,
  "verdict": "pass | issues",
  "confidence": 0.0,
  "dimensions": {
    "text_fidelity":   { "pass": true, "note": "" },
    "asset_match":     { "pass": true, "note": "" },
    "completeness":    { "pass": true, "note": "" },
    "no_junk":         { "pass": true, "note": "" },
    "placement_order": { "pass": true, "note": "" }
  },
  "issues": [
    { "dimension": "completeness", "severity": "critical|major|minor",
      "description": "...", "evidence": "...", "asset": "<filename|null>" }
  ],
  "missing_visuals": [],
  "junk_assets": [],
  "summary": "One-line verdict for this slide."
}
```
`verdict` is `"pass"` only if all five dimensions pass (minor notes allowed);
any major/critical issue ⇒ `"issues"`.

### Per PDF + overall (also in the JSON, and rendered in the `.md`)
```json
{
  "pdf": "<base>", "slides_total": 21, "slides_pass": 18, "slides_with_issues": 3,
  "critical": 1, "major": 2, "minor": 5,
  "worst_slides": [ { "slide": 4, "severity": "critical", "summary": "..." } ],
  "overall": "pass | needs_review | fail"
}
```
`overall`: `fail` if any critical; `needs_review` if any major; else `pass`.

The top of `verification_report.json` must hold a `batch` object: total PDFs,
total slides, counts of pass / needs_review / fail PDFs, and total
critical/major/minor across everything.

---

## Run settings
- Model: `gemini-3.1-pro`, vision enabled. Keep temperature low (0–0.2) for
  consistent JSON. Emit strict JSON for the report (no markdown fences inside it).
- One slide's images in focus at a time keeps judgments accurate; don't try to
  reason over a whole PDF's images at once.
