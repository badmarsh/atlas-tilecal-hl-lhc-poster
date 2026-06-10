# Vision QA Verification Report

## Summary
- **Total PDFs Evaluated**: 6
- **Total Slides Checked**: 39
- **PDFs with Major Issues**: 2
- **Overall Verdict**: Needs Tuning

## PDF Level Breakdown

### 1. `ATL-TILECAL-SLIDE-2025-552.pdf`
- **Slides**: 21
- **Verdict**: Major Issues
- **Issues**:
  - Major Issue: Junk assets. The UT Arlington logo was extracted as a junk asset on almost every slide. Slide 1 also had the ATLAS logo extracted as junk.
  - Minor Issue: Minor duplication of graphical elements across some slides.

### 2. `atlas-eps-converted-to.pdf`
- **Slides**: 1
- **Verdict**: Pass
- **Issues**: None. The pipeline correctly extracted the single giant graphical asset.

### 3. `Eduardo_IEEE_NSS_MIC_RTSD2025_Summary.pdf`
- **Slides**: 2
- **Verdict**: Pass
- **Issues**: None. Pipeline successfully recognized text-only dense two-column pages and extracted no assets, as expected.

### 4. `Eduardo_IEEE_NSS_MIC_RTSD_Poster-2.pdf`
- **Slides**: 1
- **Verdict**: Major Issues
- **Issues**:
  - Major Issue: Junk assets. Text blocks (e.g., "Radiation requirements for DB Production" and "High Luminosity TileCal on-detector read-out system") were incorrectly extracted as image assets.
  - Minor Issue: Duplication/Merging. Some graphical elements were extracted individually but also merged into a giant composite asset that contained other plots.

### 5. `paper_ATL-TILECAL-PROC-2022-017.pdf`
- **Slides**: 6
- **Verdict**: Pass
- **Issues**: None. Figures and plots (including multi-part figures) were perfectly extracted without junk or duplicates.

### 6. `paper_Valdes_Santurio_2023_J._Inst._18_C04011.pdf`
- **Slides**: 8
- **Verdict**: Pass
- **Issues**: None. Figures were correctly extracted and mapped; text-only pages correctly yielded no assets.
