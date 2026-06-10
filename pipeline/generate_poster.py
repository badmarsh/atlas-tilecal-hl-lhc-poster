#!/usr/bin/env python3
"""
generate_poster.py -- Auto-generates a LaTeX poster using the Gemini API.
Reads all Output_*_mapped.tex files, constructs the AGENTS.md prompt template,
and saves the output to build/drafts/auto_generated_poster.tex.
"""

import os
import glob
import sys
import logging

try:
    from google import genai
    from google.genai import types
except ImportError:
    sys.exit("ERROR: google-genai missing. pip install google-genai")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro")

SYSTEM_INSTRUCTION = """
You are working in the ATLAS TileCal HL-LHC irradiation poster repository.
The build loop and overflow rules are mandatory.

## Your task
Write a complete, content-rich A0 poster. Output ONLY the raw LaTeX code for the poster. Do not use Markdown code blocks (```latex ... ```), just output the raw code.

Title: Auto-Generated ATLAS Tile Calorimeter Poster
Author: Automatically Generated
Institution: ATLAS Collaboration

Target layout: 3 columns x 3+ rows. Every card must be filled with real content from the provided source text. 

Language rules:
- Scientific register throughout. No layman explanations.
- State results with units and uncertainties.

Style rules:
- Copy the preamble from an existing poster or use standard tikzposter layout.
- Use \looseitems for col1/col3 bullets, \tightitems for col2 bullets.
- Radiation-effect terms: \textcolor{tid}{TID}, \textcolor{niel}{NIEL}, \textcolor{see}{SEE}, \textcolor{sel}{SEL}.
- Figures: ALWAYS width 1.0\linewidth. Use \captiontext{...} for all captions.
- Enforce blockverticalspace=3em or 4em.
"""

def gather_sources():
    sources = []
    output_dirs = glob.glob("Output_*")
    for d in output_dirs:
        if os.path.isdir(d):
            base_name = os.path.basename(d).replace("Output_", "")
            mapped_tex = os.path.join(d, f"{base_name}_mapped.tex")
            if os.path.exists(mapped_tex):
                with open(mapped_tex, "r", encoding="utf-8") as f:
                    content = f.read()
                    sources.append(f"--- Source: {base_name} ---\n{content}\n")
    return "\n".join(sources)


def main():
    try:
        client = genai.Client()
    except Exception as e:
        logger.error(f"Error initializing Google GenAI Client: {e}")
        return 1

    logger.info("Gathering extracted PDF sources...")
    source_content = gather_sources()
    if not source_content:
        logger.warning("No extracted sources found in Output_* directories.")
        return 1

    prompt = (
        "Below are the extracted text and figure placeholders from the source PDFs.\n"
        "Synthesize this into a cohesive scientific poster using the tikzposter class.\n\n"
        f"{source_content}"
    )

    logger.info(f"Generating poster via Gemini API ({MODEL_ID}). This may take a minute...")
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.2, # Low temperature for more factual extraction
    )
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[prompt],
            config=config
        )
        latex_code = response.text
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return 1

    # Clean up markdown code blocks if the model accidentally included them
    if latex_code.startswith("```latex"):
        latex_code = latex_code[8:]
    if latex_code.startswith("```"):
        latex_code = latex_code[3:]
    if latex_code.endswith("```"):
        latex_code = latex_code[:-3]
    
    latex_code = latex_code.strip()

    # Save to build/drafts/
    out_dir = os.path.join("build", "drafts")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "auto_generated_poster.tex")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(latex_code)
        
    logger.info(f"Poster generation complete! Saved to: {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
