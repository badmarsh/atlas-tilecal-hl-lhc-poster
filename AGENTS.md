# AGENTS.md — Working rules for the ATLAS TileCal irradiation poster

> Read this fully before touching the poster. It is written for any agent
> (Claude 4.7, Gemini 3.1 Pro / Antigravity, future Claude) picking up this
> repo. It encodes hard-won lessons — following it avoids the two failure modes
> that already bit us: **silent overflow** and **stale previews**.

---

## 0. Agent bootstrap (run this first)

If you are a coding agent starting a session in this repo for the first time,
run the setup script before anything else:

```bash
bash setup.sh
```

It detects macOS (Homebrew) or Debian/Ubuntu (apt), installs `texlive`,
`poppler`, `imagemagick`, and `Pillow`, then runs a build to confirm the
environment is working. If it exits with `RESULT: PASS` you are ready. If it
fails, check the error and consult §1 of the README for manual steps.

**Prompt you can paste into a new agent session to bootstrap it:**

```
You are working on the ATLAS TileCal HL-LHC irradiation poster repo.

Before making any changes:
1. Read AGENTS.md in full.
2. Run `bash setup.sh` from the repo root to install dependencies and verify
   the build. Wait for it to print "RESULT: PASS" before proceeding.
3. Every edit to build/irradiation_poster.tex must be followed by
   `cd build && ./build.sh`. The change is not done until check_fit.py
   prints "RESULT: PASS".
```

---

## 1. What this repo is

An A0 **portrait** LaTeX poster built with the `tikzposter` class:

> *Irradiation Studies and Design Optimization of the ATLAS Tile Calorimeter
> for the High-Luminosity LHC.*

The poster is **3 equal columns** (`\column{0.333}` each). Content is grouped
into `\block{Title}{ body }` "cards". Most user requests will be **editing the
text/figures inside a card** — the wording changes often, so the layout must be
re-checked after *every* content edit.

### File map (only these matter day-to-day)

| Path | What it is |
|---|---|
| `build/irradiation_poster.tex` | Original poster (stable reference). |
| `build/newest-poster.tex` | **Actively developed poster. This is the file you edit.** |
| `build/assets/` | Figures referenced by the poster (`.png` and `.pdf`). |
| `build/logos/` | Title-bar logo (`atlas_transparent.png`). |
| `build/build.sh` | **Compile + preview + overflow check, one command.** Use this. |
| `build/check_fit.py` | Deterministic overflow detector (called by `build.sh`). |
| `build/_prev/<name>-1.png` | Latest rendered preview (regenerated each build). |
| `template/tile_calibration_poster.tex` | Reusable style template (calibration poster). Can be edited and compiled; figure assets are not present so figures render as placeholders. |
| `sources/` | Original source PDFs + their extracted text/figures. The factual ground truth for card content. |
| `qa/` | Vision-QA reports on extraction fidelity. |

Everything else (`venv/`, `.verify_scratch/`, `pipeline/`) is the one-time
PDF→LaTeX extraction toolchain. **You almost never need it.** Do not run or
modify it for a normal "change the wording / fix the layout" request.

---

## 2. The build loop — do this every time

```bash
cd build
./build.sh           # compiles, renders _prev/irradiation_poster-1.png, runs check_fit.py
```

Then **read the preview image** `build/_prev/irradiation_poster-1.png` and trust
the `check_fit.py` verdict it prints. A change is not done until:

1. `build.sh` prints `RESULT: PASS`, **and**
2. you have visually looked at the preview (or the relevant column crop).

If you only have `pdflatex`/`pdftoppm` (no PAI skill), `build.sh` falls back to
them automatically — it is portable.

### Use your LaTeX tooling/skill
- **Claude Code / PAI agents:** invoke the **`latex-document-skill`** for any
  non-trivial LaTeX work (compiling, debugging compile errors, adding figures,
  tables, TikZ, fonts). `build.sh` already calls that skill's `compile_latex.sh`
  under the hood, but load the skill yourself when you need its reference guides
  (poster design, debugging, packages) or its helper scripts — don't hand-roll
  LaTeX you're unsure about. Don't reach for an image/art skill to "fix" the
  poster; this is a LaTeX document, edited as LaTeX.
- **Gemini 3.1 Pro / Antigravity (no skill system):** use `build.sh`'s built-in
  `pdflatex` path and the reference material in this file. The build loop and
  `check_fit.py` are identical for you.

Either way the rule is the same: edit `irradiation_poster.tex`, build with
`build.sh`, and don't call it done until `check_fit.py` prints `PASS`.

---

## 3. Gotchas (these already cost us time — do not relearn them)

### 3a. tikzposter does NOT auto-fit — overflow is SILENT
Blocks stack top-down. If a column's content is taller than the page, the last
card **runs off the bottom edge** — its rounded bottom border and figure caption
get clipped. **LaTeX reports no error.** The PDF "compiles successfully" and the
top 90% looks perfect. The only way to catch it is to inspect the *bottom* of
each column → that is exactly what `check_fit.py` automates. **Never declare the
layout done without a `PASS`.**

### 3b. The middle column (col2) is the tight one
- `col1` (left) usually has large slack (~150px margin).
- `col3` (right) is moderately full.
- `col2` (middle) has 3 dense cards + 3 figures and overflows first.

So: **put new/longer content in col1 when you have the choice**, and after *any*
col2 edit, assume it overflowed until `check_fit.py` says otherwise.

### 3c. A locked PDF causes STALE previews (insidious)
If `irradiation_poster.pdf` is open in a viewer (Acrobat, browser, SumatraPDF on
Windows), `pdflatex` fails with `! I can't write on file ... .pdf` →
`Fatal error occurred, no output PDF file produced`. The **old** preview stays
on disk, so you "fix" things and see no change and conclude you're blind. You're
not — the build never ran. `build.sh` deletes the PDF first to prevent this, but
if you compile by hand, **`rm -f irradiation_poster.pdf` before every build**,
and keep the PDF closed in viewers while iterating.

### 3d. Don't eyeball a downscaled A0 at a glance
The preview is ~849×1200 for a ~841×1189 mm page — a rounded card border vs. a
clip is a few pixels. We wrongly called it "fixed" twice by eye. **Measure**
(`check_fit.py`) or crop-and-zoom the exact region (see §6) before concluding.

### 3e. Paths to assets and logos
Always use `assets/fig_name.png` and `logos/atlas_transparent.png`. Do NOT use relative paths like `../../assets/` or `../logos/`. You are building from the `build/` directory, where these folders are directly available.

### 3f. Isolated Workspaces
If you are running in an isolated subagent workspace, `sources/converted/` may not exist in your branch. Use absolute paths to read files from the parent workspace, or use standard read tools (`view_file`, `cat`) instead of directory listing tools inside the branched `sources/` folder.

---

## 4. Fixing overflow — reclaim vertical space in this order

Apply to the **offending column only** (almost always col2). Prefer the earlier,
less destructive levers first; stop as soon as `check_fit.py` returns `PASS`
with a comfortable margin (aim for WARN-free, i.e. lowest content < ~97.5% down).

1. **Tighten item spacing.** In that column's blocks change
   `\setlength{\itemsep}{0.3em}` → `0.15em`. Cheap, invisible, big payoff.
2. **Reduce inter-figure / pre-caption space.** `\vspace{0.12cm}` before a
   figure → `0.08cm` or `0cm`; make the post-figure `\vspace{-0.2cm}` more
   negative (`-0.3cm`).
3. **Trim prose.** Preserve the physics facts; cut filler words, not numbers/units.
4. **Move content between columns or rows** to rebalance the layout.
   *(Note: Do NOT change `blockverticalspace` to fix overflow, as top/bottom margins between cards are absolute. Do NOT shrink figures—images must ALWAYS be `1.0\linewidth`.)*

### Figure aspect ratios (height per unit width — who hogs vertical space)
| Figure | px | height/width | Note |
|---|---|---|---|
| `fig_db6_blockdiagram.png` | 904×553 | **0.61** | tallest in col2; shrink this first |
| `fig_minidrawer_blockdiagram.png` | 992×336 | 0.34 | col1 |
| `fig_mosfet_threshold.png` | 1160×367 | 0.32 | col2 bottom |
| `fig_db6_tid_test.png` | 1091×299 | 0.27 | col2 middle; very wide/short |

A wide-and-short figure costs little height even at large width; a near-square
one costs a lot. Trim by **height impact**, not apparent size.

### Figure widths (1.0 design rule)
Images must ALWAYS be set to `1.0\linewidth` to maximize readability. If a content edit makes col2 overflow, tighten prose first (§4 steps 1–2) or move content. Do not shrink figure widths below `1.0\linewidth`.

---

## 5. Editing card contents (the common request)

When the user asks to change what a card says:

1. **Find the card** by its `\block{Title}{...}` title in
   `build/irradiation_poster.tex`.
2. **Keep the physics correct.** Cross-check dose/fluence/efficiency numbers
   against `sources/` (the papers/slides), not from memory. Units use
   `\,` thin spaces (e.g. `40\,MHz`, `108\,Gy`).
3. **Preserve the visual grammar:**
   - Radiation-effect terms use the defined colour macros:
     `\textcolor{tid}{...}` (orange), `\textcolor{niel}{...}` (green),
     `\textcolor{see}{...}` / `\textcolor{sel}{...}` (red/blue). Reuse them;
     don't invent new colours.
   - Bullet lists use `\looseitems` (col1/col3) or `\tightitems` (col2),
     both defined in the preamble LAYOUT PARAMETERS section.
   - Each figure sits in a `\begin{center}...\end{center}` followed by
     `\captiontext{caption text}`. Image width must ALWAYS be `1.0\linewidth`.
4. **Escape LaTeX specials in prose:** `%`→`\%`, `&`→`\&`, `_`→`\_`, `#`→`\#`,
   `$`→`\$`. Angle brackets need math mode: `<5\%` → `$<5\%$`, `≥` → `$\geq$`.
   These compile silently wrong otherwise (inverted `¿` glyphs).
5. **Rebuild and check** (`./build.sh`). If the edit lengthened a col2 card →
   it likely overflowed → §4.
6. If a card grew a lot, consider **moving a card between columns** to rebalance
   rather than shrinking everything (col1 has the most room).

---

## 6. Verifying a specific region by eye

`check_fit.py` tells you *whether* it fits. To *see* a region, crop the preview
(don't squint at the whole A0):

```bash
cd build
# bottom of the middle column, zoomed 2.5x:
convert _prev/irradiation_poster-1.png -crop 320x180+265+1030 -resize 250% /tmp/crop.png
# columns are roughly: col1 x≈0..283, col2 x≈283..566, col3 x≈566..849 (of 849 wide)
```

A correctly closed card shows: caption text → a solid rounded **red** bottom
border → white margin → page edge. A clipped card shows pink body / border
running to the last pixel row with no margin.

---

## 7. House rules

- **Edit only `.tex` files in `build/`** (like `build/drafts/<poster>.tex`) for content/layout. Leave
  `template/`, `sources/`, `pipeline/`, `venv/` untouched unless explicitly
  asked to re-run extraction.
- **Do NOT redefine standard macros.** If copying a preamble, do not duplicate `\looseitems` or `\tightitems`. Ensure `\begin{document}` is included.
- **`pdflatex` engine** (the poster uses `\documentclass{tikzposter}` + plain
  `graphicx`; no fontspec). Two passes. `build.sh` handles it.
- **Keep the PDF closed in viewers while iterating** (see §3c).
- **One source of truth for "does it fit": `check_fit.py` → `PASS`.** Don't
  declare success on a green LaTeX compile alone.
- Don't commit/regenerate `venv/`, `_prev/`, or LaTeX aux files — see
  `.gitignore`.

---

## 8. Creating a new poster version

Copy `build/newest-poster.tex` to a new name (e.g. `build/poster_v2.tex`),
clear the block bodies, fill in new content, then build with
`./build.sh poster_v2.tex`. The existing poster has the full preamble,
LAYOUT PARAMETERS section, all macros, and title-bar setup already wired — it
is the best starting point for any new poster in this repo.

**Lesson learned**: a minimal "skeleton passes PASS" is not success. An agent
that stops as soon as the layout compiles clean has done nothing useful — every
block must contain real content drawn from the source files before the task is
done.

**Prompt template — paste this to any agent to commission a new poster:**

```
You are working in the ATLAS TileCal HL-LHC irradiation poster repository.
Read AGENTS.md fully before touching anything. The build loop and overflow
rules in that file are mandatory — do not skip them.

## Your task

Write a complete, content-rich A0 poster as `build/<FILENAME>.tex`.
Title:       <POSTER TITLE>
Author:      <NAME>, on behalf of the ATLAS Tile Calorimeter System
Institution: <INSTITUTION>

## Step 1 — Study the sources and assets FIRST (do not skip)

Before writing a single line of LaTeX, read and analyse all relevant source
material to understand what content and figures are available:

1. Read all source tex files listed below. Extract concrete facts: numbers,
   component names, dose values, test results, efficiencies, fluences.
2. List every figure file present in `build/assets/` and note its aspect
   ratio (px width × height). Figures are the visual anchor of each card —
   plan which figure belongs to which card before writing.
3. **The poster MUST be at least 90% covered vertically.** If a column is sparse and ends too high, you MUST make cards longer or add cards into additional rows. It does NOT have to be a symmetrical 3x3 grid (e.g., you can have 4 cards in col1, 3 in col2, 5 in col3) as long as the 90% vertical coverage threshold is met across all 3 columns.
4. Include more graphs and tables. You are scientifically competent enough to choose card topics that are important and have fitting visual assets.

Source files (read all that are relevant to the poster topic):
  sources\converted\Output_Eduardo_IEEE_NSS_MIC_RTSD_Poster-2\Eduardo_IEEE_NSS_MIC_RTSD_Poster-2_mapped.tex
  sources\converted\Output_ATL-TILECAL-SLIDE-2025-552\ATL-TILECAL-SLIDE-2025-552_mapped.tex

The rest of the files are more information for your context.  Read all files to know the problematics. 
sources\converted\Output_Eduardo_IEEE_NSS_MIC_RTSD2025_Summary\Eduardo_IEEE_NSS_MIC_RTSD2025_Summary_mapped.tex  sources/converted/Output_paper_Valdes_Santurio_2023_J._Inst._18_C04011/paper_Valdes_Santurio_2023_J._Inst._18_C04011_mapped.tex
sources\converted\Output_paper_ATL-TILECAL-PROC-2022-017\paper_ATL-TILECAL-PROC-2022-017_mapped.tex
sources\converted\Output_paper_Valdes_Santurio_2023_J._Inst._18_C04011\paper_Valdes_Santurio_2023_J._Inst._18_C04011_mapped.tex

## Step 2 — Respect user-specified card content

If the user has specified a topic, section title, or content for one or more
cards, those specifications take priority and must be implemented exactly as
requested. Cards not specified by the user are filled by the agent using the
best content selected from the source material in Step 1.

User card specifications (fill in or leave blank):
  Card <column>/<row>: <user specification, or "agent choice">
  ...

## Step 3 — Write the poster

Target layout: **3 columns × 3+ rows = 9+ cards** (can be asymmetrical rows like 4x3x5). Every card must be filled
with real, substantive content. The poster must feel uniformly dense and be **at least 90% covered**. Top and bottom margins between cards are absolute, so fill space by making cards longer or adding more cards, rather than inflating `blockverticalspace`.

Column 1 (left) — has the most vertical slack, put longer blocks here:
  - Block: "<SECTION A>" — <what this block covers>
  - Block: "<SECTION B>" — <what this block covers>
  - Block: References

Column 2 (middle) — overflows first; use \tightitems, keep figures at 1.0\linewidth:
  - Block: "<SECTION C>"
  - Block: "<SECTION D>"
  - Block: "<SECTION E>"

Column 3 (right):
  - Block: "<SECTION F>"
  - Block: "<SECTION G>"
  - Block: Conclusions & Outlook

## Language rules (non-negotiable)

- **Scientific register throughout.** The audience is physicists. Write as you
  would in a conference proceedings paper: concise, precise, terminology-dense.
- **No layman explanations.** Do not define what a calorimeter, PMT, ADC, or
  FPGA is. Do not use phrases like "in simple terms", "basically", or
  "this means that". Every sentence must add physical or technical information.
- State results with units and uncertainties where known.
  Use thin spaces: `40\,MHz`, `108\,Gy`, `13\times10^{12}\,n_\text{eq}/cm^2`.
- **Use Tables for Data:** Component test results, pass/fail matrices, and numerical parameter sets MUST be formatted as LaTeX tables (`\begin{tabular}`) to elevate the poster visually. Do not use bulleted lists for tabular data.

## Style rules (non-negotiable)

- Copy the preamble from build/new_poster.tex — do not invent a new one.
- Use \looseitems for col1/col3 bullets, \tightitems for col2 bullets.
- Radiation-effect terms: \textcolor{tid}{TID}, \textcolor{niel}{NIEL},
  \textcolor{see}{SEE}, \textcolor{sel}{SEL}.
- Figures: ALWAYS width 1.0\linewidth. Use \captiontext{...} for all captions.
- Visual Anchors: You must aggressively utilize ALL relevant graphical assets in `build/assets/` to visually anchor columns. Do not produce walls of text.
- Standard Spacing: Enforce a standard `blockverticalspace=3em` (or `4em` max) in `\documentclass`. Do not inflate this to mask a lack of content.
- Only reference figures that physically exist in build/assets/.

## Completion criteria — do NOT stop until ALL of these are true

1. `cd build && ./build.sh drafts/<FILENAME>.tex` prints `RESULT: PASS`.
2. All cards contain real content from the source files. Placeholder text
   ("TBD", "insert here", "lorem ipsum", single-word bullets) is a failure
   condition, not a draft.
3. Every card that has a matching figure in build/assets/ uses it with a
   \captiontext{} caption.
4. No card is visibly sparse. **The entire poster MUST be at least 90% covered.** If a column ends high, make cards longer or add more cards into additional rows. Do NOT artificially increase `blockverticalspace` to fill the page; always use `blockverticalspace=4em` strictly.
5. The poster reads as a self-contained scientific summary. A physicist
   unfamiliar with this specific work can learn the key results from the poster
   alone, without referring to the papers.
```

