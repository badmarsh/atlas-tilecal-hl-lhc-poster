# ATLAS TileCal HL-LHC Irradiation Poster

Working directory for building an A0 LaTeX poster:
**"Irradiation Studies and Design Optimization of the ATLAS Tile Calorimeter for the High-Luminosity LHC"**

> **Editing the poster?** Read **[AGENTS.md](AGENTS.md)** first. Build with
> `cd build && ./build.sh` — it compiles, renders a preview, and runs
> `check_fit.py` to catch the silent column-overflow that `tikzposter` does not
> report. The layout is only "done" when `check_fit.py` prints `PASS`.

---

## Agent / new-contributor setup

These steps get a fresh environment to a state where `build/build.sh` succeeds
and `check_fit.py` prints `PASS`. Run them once after cloning.

### 1. Install system dependencies

**Debian/Ubuntu (including WSL)**

```bash
sudo apt-get update
sudo apt-get install -y texlive-latex-extra texlive-science texlive-fonts-extra \
    poppler-utils python3 python3-pip imagemagick
```

**macOS (Homebrew)**

```bash
brew install --cask mactex-no-gui   # ~4 GB; provides pdflatex + tikzposter
brew install poppler imagemagick python
```

`mactex-no-gui` installs the full MacTeX distribution without the GUI apps
(`TeXShop`, etc.). If you already have a partial TeX Live install and want a
lighter option, `brew install basictex` works too, but you'll need to add the
missing packages manually:

```bash
sudo tlmgr update --self
sudo tlmgr install tikzposter collection-latexextra collection-science \
    collection-fontsrecommended
```

After either route, ensure `pdflatex` is on your PATH (open a new terminal or
run `eval "$(/usr/libexec/path_helper)"` if it isn't).

---

`texlive-latex-extra` / MacTeX provides `tikzposter`. `poppler-utils` / `poppler`
provides `pdftoppm` (used by `build.sh` to render the PNG preview when the PAI
`latex-document-skill` is not present). `imagemagick` is optional — only needed
for `convert` crop-and-zoom debugging (§6 of AGENTS.md).

### 2. Install Python dependency for the fit checker

```bash
pip3 install Pillow
```

`build/check_fit.py` requires `Pillow` (PIL) and `numpy`.

### 3. (PAI / Claude Code environment only) latex-document-skill

If you are running inside PAI, `build.sh` auto-detects and uses
`~/.claude/skills/latex-document-skill/scripts/compile_latex.sh` when present.
No extra setup needed — the skill handles `texlive` installation and log
filtering. In bare environments the script falls back to plain `pdflatex`
automatically.

### 4. Build and verify

```bash
cd build
./build.sh
```

Expected last lines:

```
  col1 (left)    lowest content y= ...  -> PASS
  col2 (middle)  lowest content y= ...  -> PASS
  col3 (right)   lowest content y= ...  -> PASS

RESULT: PASS -- every card closes inside the page.
```

If you see `RESULT: FAIL`, the poster content overflows a column. Follow §4 of
[AGENTS.md](AGENTS.md) to reclaim vertical space.

### 5. (Optional) Re-run the PDF→LaTeX extraction pipeline

The extraction is already done and its output lives in `sources/converted/`.
You only need this if you add new source PDFs.

```bash
pip3 install -r requirements.txt   # heavy OCR deps — takes a while
cd sources/pdf
python3 ../../pipeline/pdf_pipeline.py
```

---

## Directory layout

| Folder | Contents |
|--------|----------|
| `build/` | The poster being produced. `build/*.tex` is compiled here; `build/assets/` holds figures selected for the poster; `build/logos/` holds title-bar logos (ATLAS, university). |
| `sources/pdf/` | The 6 original source PDFs (presentations + papers). |
| `sources/converted/` | One `Output_<name>/` per source PDF — output of the PDF→LaTeX pipeline. Each holds `<name>_mapped.tex` (extracted text + `\includegraphics` links), `assets/` (extracted figures: png/jpeg/pdf), and `slides/` (each source page burst to a single-page PDF = ground truth). |
| `template/` | `tile_calibration_poster.tex` — the **style/dimension reference** (tikzposter, A0 portrait, ATLAS colour scheme). Not compiled; its own plot/logo assets are not present. |
| `pipeline/` | PDF→LaTeX conversion + QA tooling (`pdf_pipeline.py` and helpers). |
| `qa/` | Vision-QA reports on extraction fidelity (`verification_report.md/.json`). |

## Source-by-source relevance (focus: irradiation studies)

- **`Eduardo_IEEE_NSS_MIC_RTSD_Poster-2`** — richest single source. Full TID/NIEL/SEE/SEL qualification of the **Link & Control Daughterboard (DB6)** + production-component radiation tests (MOSFETs, INA333, SFP+, FLASH, oscillators). *Its `_mapped.tex` text is garbled (scanned poster); read content from the rendered slide image / the two Valdes papers instead.*
- **`ATL-TILECAL-SLIDE-2025-552`** (Moayedi) — **LVPS front-end power-supply bricks**: radiation tests on diodes, LT1681, LTC6241, LT3080, IR2110, SIHFS9N60A MOSFET, SI8920/HCPL7800 isolation amps, CHARM system-level tests, and **design optimization** (MOSFET swap: efficiency 58%→72%). Clean text + figures.
- **`paper_Valdes_Santurio_2023_J._Inst._18_C04011`** + **`paper_ATL-TILECAL-PROC-2022-017`** — peer-reviewed DB6 radiation-study detail (exact doses, fluences, SEL tests). Clean extraction.
- **`atlas-eps-converted-to`** — ATLAS logo for the title bar.

## Re-running the conversion pipeline

`pipeline/pdf_pipeline.py` globs `*.pdf` in its **current working directory** and writes `Output_<name>/` there. The conversion is already done; to re-run, copy the PDFs from `sources/pdf/` next to where you invoke the script.

## Extraction caveats (from `qa/verification_report.md`)

- `ATL-TILECAL-SLIDE-2025-552`: per-slide UT-Arlington/ATLAS **logos extracted as junk assets**; minor cross-slide duplication.
- `Eduardo_..._Poster-2`: **text blocks mis-extracted as image assets**; some figures both individual and merged into a composite.
- The 4 papers/summary extracted cleanly.
