import os
import glob
import json
import re
import time
import io
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
from pathlib import Path
from typing import List, Optional

try:
    import fitz  # PyMuPDF
    import PIL.Image
    from google import genai
    from google.genai import types
    from pydantic import BaseModel, Field
except ImportError as e:
    sys.exit(f"ERROR: a required dependency is missing ({e.name}).\n"
             "       This QA verifier needs PyMuPDF, Pillow, google-genai and pydantic:\n"
             "       pip install -r requirements.txt google-genai pydantic")

# Network robustness for the Gemini call.
MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
RETRY_BACKOFF_S = float(os.environ.get("GEMINI_RETRY_BACKOFF", "2.0"))

# --- Pydantic Schema for structured output ---
class Dimension(BaseModel):
    passed: bool = Field(alias="pass")
    note: str

class Dimensions(BaseModel):
    text_fidelity: Dimension
    asset_match: Dimension
    completeness: Dimension
    no_junk: Dimension
    placement_order: Dimension

class Issue(BaseModel):
    dimension: str
    severity: str
    description: str
    evidence: str
    asset: Optional[str] = None

class SlideQA(BaseModel):
    pdf: str
    slide: int
    verdict: str
    confidence: float
    dimensions: Dimensions
    issues: List[Issue] = Field(default_factory=list)
    missing_visuals: List[str] = Field(default_factory=list)
    junk_assets: List[str] = Field(default_factory=list)
    summary: str

# --- Configuration ---
# Override with:  GEMINI_MODEL=<id> python qa_verifier.py
MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro")
RENDER_DPI = 150

# Self-contained system instruction (the rubric). Does not depend on the .md,
# which is now an agent task-brief rather than an API system prompt.
SYSTEM_INSTRUCTION = r"""
You are a meticulous multimodal QA verifier for a PDF-to-LaTeX extraction
pipeline. The pipeline bursts presentation/paper PDFs into single slides,
extracts the text into LaTeX, extracts real figures/graphs/tables/photos as
image assets, and links each asset with \includegraphics. Judge, for ONE slide
at a time, whether the generated LaTeX text and the linked image assets
faithfully represent the original slide shown to you as an image.

You receive: SLIDE_IMAGE (rendered original slide = GROUND TRUTH), then 0+
ASSET_IMAGES (the figures linked by this slide, in document order), then a text
block with the slide's TEX_SECTION.

Evaluate exactly these five dimensions; pass/fail + a specific note each:
  A. TEXT_FIDELITY  - Does TEX_SECTION capture the slide's meaningful text
     accurately? FAIL if substantive text is missing, garbled, characters wrong,
     math/symbols semantically wrong, or words merged/split so meaning changes.
     Reading-order changes that preserve meaning, reformatting and LaTeX escaping
     are FINE.
  B. ASSET_MATCH    - Does each linked asset visually correspond to a real
     figure/graph/table/diagram/photo actually on this slide? FAIL for an asset
     matching nothing (wrong crop/hallucinated), badly cut off, or wrong figure
     for its position.
  C. COMPLETENESS   - Is every SUBSTANTIVE visual on the slide represented by at
     least one asset? FAIL and list each MISSING visual.
  D. NO_JUNK        - Are all assets genuine content, not decoration? FAIL if an
     asset is a logo, crest, author headshot, icon, bullet, title banner, rule,
     or tiny sliver/fragment.
  E. PLACEMENT_ORDER- Do figures appear in the TeX at a position roughly
     consistent with the slide's top-to-bottom, left-to-right reading order?
     Minor reordering is FINE; FAIL only if clearly scrambled.

PIPELINE-SPECIFIC RULES (avoid false alarms):
  - Decorative elements are INTENTIONALLY excluded; do NOT report missing logos,
    crests, headshots, page numbers, banner-image titles, icons, or rules.
  - Vector figures are saved as cropped regions and MAY over-include adjacent
    text or a neighbouring photo; if the intended figure is present, treat
    over-inclusion as at most MINOR, never critical.
  - The same photo may appear BOTH as a standalone raster asset AND inside a
    vector crop; duplication is MINOR, not a failure.
  - Non-ASCII text was converted to LaTeX (x -> $\times$, math-italic -> ascii,
    accents -> \'e). Judge SEMANTIC correctness, not glyph identity. A dropped
    rare symbol is MINOR unless it changes a quantity or unit.
  - Title/divider slides with little text and no figures should PASS if the TeX
    reflects that.

SEVERITY: critical = a real figure/table/graph missing, an asset that is the
wrong/hallucinated image, or text so wrong a reader is misled. major = a real
visual only partially captured, a meaningful text block missing, or a junk asset
clearly not content. minor = over-inclusion, duplication, dropped rare symbol,
slight reorder.

verdict is "pass" only if all five dimensions pass (minor notes allowed); any
major/critical issue -> "issues". Be precise and conservative: only report what
you can actually see; when unsure, lower confidence rather than invent an issue.
Output strictly matches the provided response schema.
""".strip()


def extract_system_prompt() -> str:
    """Return the system instruction.

    Prefers a fenced block under a heading containing 'SYSTEM PROMPT' in the
    companion .md (back-compat); otherwise uses the embedded rubric above.
    """
    prompt_file = "gemini_slide_verifier_prompt.md"
    if os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r"#+\s*[^\n]*SYSTEM PROMPT[^\n]*\n+```\n(.*?)```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
    return SYSTEM_INSTRUCTION

def render_pdf_to_png(pdf_path: str, dpi: int = RENDER_DPI) -> PIL.Image.Image:
    """Renders the first page of a PDF to a PIL Image at the given DPI."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    img_data = pix.tobytes("png")
    doc.close()
    return PIL.Image.open(io.BytesIO(img_data))

def rasterize_asset(asset_path: str) -> PIL.Image.Image:
    """Loads an asset (PNG/JPG/PDF). If it's a PDF, rasterizes it."""
    ext = os.path.splitext(asset_path)[1].lower()
    if ext == ".pdf":
        return render_pdf_to_png(asset_path)
    else:
        return PIL.Image.open(asset_path).convert("RGB")

def split_tex_into_slides(tex_content: str):
    """Splits mapped tex content into per-slide sections."""
    # Find all slide sections
    # Matches \section*{Slide N} ... up to next \section*{ or \end{document}
    pattern = re.compile(r"(\\section\*\{Slide (\d+)\}.*?)(?=\\section\*\{Slide |\\end\{document\})", re.DOTALL)
    slides = []
    for match in pattern.finditer(tex_content):
        slide_tex = match.group(1).strip()
        slide_num = int(match.group(2))
        slides.append({
            "slide_num": slide_num,
            "tex": slide_tex
        })
    return slides

def extract_includegraphics(slide_tex: str) -> List[str]:
    r"""Finds all \includegraphics{...} paths in the slide tex."""
    return re.findall(r"\\includegraphics(?:\[.*?\])?\{([^}]+)\}", slide_tex)

def verify_slide(client: genai.Client, system_instruction: str, base_name: str, slide_num: int, total_slides: int, slide_tex: str, slide_image: PIL.Image.Image, asset_paths: List[str]):
    """Calls Gemini to verify a single slide."""
    
    # Construct the User prompt parts
    user_prompt_text = f"PDF: {base_name}.pdf\nSLIDE: {slide_num} of {total_slides}\nASSET_FILES (in document order):\n"
    
    contents = [slide_image]
    
    if not asset_paths:
        user_prompt_text += "  (none — text-only slide)\n"
    else:
        for idx, asset_path in enumerate(asset_paths):
            basename = os.path.basename(asset_path)
            item_label = f"(item {idx + 1})"
            user_prompt_text += f"  - {basename}   {item_label}\n"
            try:
                asset_img = rasterize_asset(asset_path)
                contents.append(asset_img)
            except Exception as e:
                logger.warning(f"    Warning: Could not load asset {asset_path}: {e}")
                
    user_prompt_text += "\nTEX_SECTION:\n<<<\n"
    user_prompt_text += slide_tex
    user_prompt_text += "\n>>>\n\nReturn the JSON object for THIS slide using the schema you were given."
    
    contents.append(user_prompt_text)
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=SlideQA,
        temperature=0.0,
    )
    
    # Retry transient API/network failures with exponential backoff.
    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=config
            )
            break
        except Exception as e:
            if attempt >= MAX_RETRIES:
                print(f"    Error: Gemini call failed for slide {slide_num} "
                      f"after {MAX_RETRIES} attempts: {e}")
                return None
            wait = RETRY_BACKOFF_S * attempt
            print(f"    Warning: Gemini call failed (attempt {attempt}/{MAX_RETRIES}); "
                  f"retrying in {wait:.0f}s: {e}")
            time.sleep(wait)

    if response is None or not getattr(response, "text", None):
        logger.info(f"Empty response for slide {slide_num}.")
        return None

    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        logger.info(f"Failed to parse JSON response for slide {slide_num}:\n{response.text}")
        return None

def process_pdf(client: genai.Client, system_prompt: str, output_dir: str):
    base_name = os.path.basename(output_dir).replace("Output_", "")
    mapped_tex_path = os.path.join(output_dir, f"{base_name}_mapped.tex")
    
    if not os.path.exists(mapped_tex_path):
        logger.info(f"Skipping {output_dir}: no {base_name}_mapped.tex found.")
        return
        
    logger.info(f"Processing PDF: {base_name}")
    with open(mapped_tex_path, "r", encoding="utf-8") as f:
        tex_content = f.read()
        
    slides = split_tex_into_slides(tex_content)
    total_slides = len(slides)
    logger.info(f"  Found {total_slides} slides.")
    results = []
    
    for slide in slides:
        slide_num = slide["slide_num"]
        logger.info(f"  Verifying Slide {slide_num}/{total_slides}...")
        slide_img_path = os.path.join(output_dir, "slides", f"slide_{slide_num:02d}.pdf")
        if not os.path.exists(slide_img_path):
            logger.warning(f"    Warning: Missing slide ground truth at {slide_img_path}")
            continue
            
        try:
            slide_image = render_pdf_to_png(slide_img_path)
        except Exception as e:
            logger.warning(f"    Warning: Failed to render {slide_img_path}: {e}")
            continue
            
        # Extract assets
        asset_rel_paths = extract_includegraphics(slide["tex"])
        # Resolve to absolute/full paths relative to output_dir
        asset_paths = [os.path.join(output_dir, p) for p in asset_rel_paths]
        
        result_json = verify_slide(client, system_prompt, base_name, slide_num, total_slides, slide["tex"], slide_image, asset_paths)
        if result_json:
            results.append(result_json)
            logger.info(f"    Verdict: {result_json.get('verdict', 'unknown')} (Confidence: {result_json.get('confidence', 0.0)})")
    # Aggregate
    slides_total = len(results)
    if slides_total == 0:
        return
        
    slides_pass = sum(1 for r in results if r.get("verdict") == "pass")
    slides_with_issues = slides_total - slides_pass
    
    critical = 0
    major = 0
    minor = 0
    worst_slides = []
    
    for r in results:
        issues = r.get("issues", [])
        if not issues and r.get("verdict") == "issues":
            # If marked as issues but no specific issue block, we'll assume minor
            minor += 1
            worst_slides.append({"slide": r.get("slide"), "severity": "minor", "summary": r.get("summary")})
            continue
            
        slide_worst_severity = None
        for i in issues:
            sev = i.get("severity")
            if sev == "critical": critical += 1
            elif sev == "major": major += 1
            elif sev == "minor": minor += 1
            
            if sev == "critical": slide_worst_severity = "critical"
            elif sev == "major" and slide_worst_severity != "critical": slide_worst_severity = "major"
            elif sev == "minor" and not slide_worst_severity: slide_worst_severity = "minor"
            
        if slide_worst_severity:
            worst_slides.append({
                "slide": r.get("slide"), 
                "severity": slide_worst_severity, 
                "summary": r.get("summary")
            })
            
    overall = "pass"
    if critical > 0: overall = "fail"
    elif major > 0: overall = "needs_review"
    
    aggregation = {
        "pdf": base_name,
        "slides_total": slides_total,
        "slides_pass": slides_pass,
        "slides_with_issues": slides_with_issues,
        "critical": critical,
        "major": major,
        "minor": minor,
        "worst_slides": worst_slides,
        "overall": overall,
        "slide_details": results
    }
    
    out_file = f"qa_report_{base_name}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(aggregation, f, indent=2)
        
    logger.info(f"  => Finished {base_name}. Overall: {overall}. Report written to {out_file}\n")
def main():
    try:
        client = genai.Client()
    except Exception as e:
        logger.info(f"Error initializing Google GenAI Client: {e}")
        logger.info("Make sure GOOGLE_API_KEY is set in your environment.")
        return
        
    try:
        system_prompt = extract_system_prompt()
    except Exception as e:
        logger.info(f"Error loading system prompt: {e}")
        return

    output_dirs = glob.glob("Output_*")
    if not output_dirs:
        logger.info("No Output_* directories found.")
        return
        
    for d in output_dirs:
        if os.path.isdir(d):
            process_pdf(client, system_prompt, d)

if __name__ == "__main__":
    main()
