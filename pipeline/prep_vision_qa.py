import os
import re
import fitz  # PyMuPDF
import json
import shutil

cwd = os.getcwd()
scratch_dir = os.path.join(cwd, ".verify_scratch")
os.makedirs(scratch_dir, exist_ok=True)

# Find all Output directories
output_dirs = [d for d in os.listdir(cwd) if d.startswith("Output_") and os.path.isdir(d)]

report = {}

for out_dir in output_dirs:
    base_name = out_dir.replace("Output_", "")
    tex_file = os.path.join(out_dir, f"{base_name}_mapped.tex")
    if not os.path.exists(tex_file):
        continue
        
    with open(tex_file, 'r', encoding='utf-8') as f:
        tex_content = f.read()
        
    slides_dir = os.path.join(out_dir, "slides")
    if not os.path.exists(slides_dir):
        # find number of slides from main pdf
        main_pdf = f"{base_name}.pdf"
        if os.path.exists(main_pdf):
            doc = fitz.open(main_pdf)
            total_slides = len(doc)
            doc.close()
        else:
            total_slides = 0
    else:
        slide_pdfs = [f for f in os.listdir(slides_dir) if f.startswith("slide_") and f.endswith(".pdf")]
        total_slides = len(slide_pdfs)
        
    slide_matches = list(re.finditer(r'\\section\*\{Slide\s+(\d+)\}', tex_content))
    
    pdf_info = {
        "base_name": base_name,
        "total_slides": total_slides,
        "slides": []
    }
    
    scratch_pdf_dir = os.path.join(scratch_dir, base_name)
    os.makedirs(scratch_pdf_dir, exist_ok=True)
    
    for i, match in enumerate(slide_matches):
        slide_num = int(match.group(1))
        start_idx = match.end()
        end_idx = slide_matches[i+1].start() if i+1 < len(slide_matches) else len(tex_content)
        
        slide_tex = tex_content[start_idx:end_idx].strip()
        
        # Find graphics
        assets = re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', slide_tex)
        
        # Render the ground truth slide
        source_slide = os.path.join(out_dir, "slides", f"slide_{slide_num:02d}.pdf")
        if not os.path.exists(source_slide) and os.path.exists(os.path.join(out_dir, "slides", f"slide_{slide_num}.pdf")):
            source_slide = os.path.join(out_dir, "slides", f"slide_{slide_num}.pdf")
            
        gt_png = os.path.join(scratch_pdf_dir, f"slide_{slide_num:02d}.png")
        if os.path.exists(source_slide):
            doc = fitz.open(source_slide)
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            pix.save(gt_png)
            doc.close()
            
        asset_pngs = []
        for asset in assets:
            # asset path in tex might be relative to out_dir or just assets/...
            asset_path = os.path.join(out_dir, asset)
            if not os.path.exists(asset_path):
                asset_path = os.path.join(cwd, asset)
                
            if os.path.exists(asset_path):
                ext = os.path.splitext(asset_path)[1].lower()
                asset_basename = os.path.basename(asset_path)
                scratch_asset_path = os.path.join(scratch_pdf_dir, asset_basename)
                if ext == '.pdf':
                    scratch_asset_path = os.path.splitext(scratch_asset_path)[0] + ".png"
                    doc = fitz.open(asset_path)
                    page = doc[0]
                    pix = page.get_pixmap(dpi=150)
                    pix.save(scratch_asset_path)
                    doc.close()
                elif ext in ['.png', '.jpeg', '.jpg']:
                    shutil.copy2(asset_path, scratch_asset_path)
                asset_pngs.append(scratch_asset_path)
            else:
                asset_pngs.append(f"MISSING: {asset}")
                
        pdf_info["slides"].append({
            "slide_num": slide_num,
            "tex": slide_tex,
            "assets": asset_pngs,
            "gt_png": gt_png if os.path.exists(gt_png) else "MISSING"
        })
        
    report[base_name] = pdf_info

with open(os.path.join(scratch_dir, "prep_info.json"), "w", encoding='utf-8') as f:
    json.dump(report, f, indent=2)

print("Prep complete.")
