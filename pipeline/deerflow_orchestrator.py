#!/usr/bin/env python3
"""
deerflow_orchestrator.py -- End-to-End orchestration for the poster pipeline in DeerFlow.

This script orchestrates the 4 stages of the poster extraction and QA pipeline:
1. pdf_pipeline.py       (Extracts PDFs to raw assets and mapped TeX)
2. prep_vision_qa.py     (Generates ground truth images and scratch prep data)
3. create_stitched.py    (Creates stitched images for debugging/eyeball checks)
4. qa_verifier.py        (Runs Gemini Vision QA on the extracted assets)

Run using your DeerFlow environment (after resolving onyx dependencies).
"""

import os
import subprocess
import logging

try:
    from deerflow import task, flow
except ImportError:
    # Fallback to simple decorators if deerflow isn't available in this environment yet
    # or to allow running without the framework installed.
    def task(func):
        return func
    def flow(name):
        def decorator(func):
            return func
        return decorator

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Base directory for the pipeline scripts
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
# Base directory where PDFs are located (parent of pipeline dir)
ROOT_DIR = os.path.dirname(PIPELINE_DIR)


@task
def run_pdf_pipeline():
    """Stage 1: Extract PDFs to slides and assets."""
    logger.info("=== STAGE 1: Running pdf_pipeline.py ===")
    script = os.path.join(PIPELINE_DIR, "pdf_pipeline.py")
    subprocess.run(["python3", script], cwd=ROOT_DIR, check=True)


@task
def run_prep_vision_qa():
    """Stage 2: Prepare scratch QA files."""
    logger.info("=== STAGE 2: Running prep_vision_qa.py ===")
    script = os.path.join(PIPELINE_DIR, "prep_vision_qa.py")
    subprocess.run(["python3", script, "--cwd", "."], cwd=ROOT_DIR, check=True)


@task
def run_create_stitched():
    """Stage 3: Stitch assets for eyeball QA."""
    logger.info("=== STAGE 3: Running create_stitched.py ===")
    script = os.path.join(PIPELINE_DIR, "create_stitched.py")
    subprocess.run(["python3", script], cwd=ROOT_DIR, check=True)


@task
def run_qa_verifier():
    """Stage 4: Run Gemini Vision verification."""
    logger.info("=== STAGE 4: Running qa_verifier.py ===")
    script = os.path.join(PIPELINE_DIR, "qa_verifier.py")
    subprocess.run(["python3", script], cwd=ROOT_DIR, check=True)


@task
def run_poster_generation():
    """Stage 5: Generate the TeX poster using LLM."""
    logger.info("=== STAGE 5: Running generate_poster.py ===")
    script = os.path.join(PIPELINE_DIR, "generate_poster.py")
    subprocess.run(["python3", script], cwd=ROOT_DIR, check=True)


@task
def run_poster_compilation():
    """Stage 6: Compile the generated poster into a PDF."""
    logger.info("=== STAGE 6: Compiling Poster PDF ===")
    build_dir = os.path.join(ROOT_DIR, "build")
    # Using the existing build.sh to compile the draft and verify fit
    subprocess.run(["./build.sh", "drafts/auto_generated_poster.tex"], cwd=build_dir, check=True)


@flow(name="Poster-Extraction-and-QA-Pipeline")
def poster_pipeline_flow():
    """End-to-End execution of the Poster QA pipeline."""
    logger.info("Starting End-to-End Poster Pipeline in DeerFlow.")
    
    try:
        run_pdf_pipeline()
        run_prep_vision_qa()
        run_create_stitched()
        run_qa_verifier()
        run_poster_generation()
        run_poster_compilation()
        logger.info("Pipeline completed successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"Pipeline failed at stage execution. Command returned {e.returncode}.")
        raise e


if __name__ == "__main__":
    # Standard entrypoint for local execution
    poster_pipeline_flow()
