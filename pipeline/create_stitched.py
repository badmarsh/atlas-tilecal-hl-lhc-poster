import os
import json
import PIL.Image
from PIL import ImageDraw, ImageFont

scratch_dir = ".verify_scratch"
info_file = os.path.join(scratch_dir, "prep_info.json")

with open(info_file, "r", encoding="utf-8") as f:
    report = json.load(f)

for base_name, pdf_info in report.items():
    stitched_dir = os.path.join(scratch_dir, f"{base_name}_stitched")
    os.makedirs(stitched_dir, exist_ok=True)
    
    for slide in pdf_info["slides"]:
        slide_num = slide["slide_num"]
        tex = slide["tex"]
        gt_png = slide["gt_png"]
        assets = slide["assets"]
        
        images = []
        if os.path.exists(gt_png):
            gt_img = PIL.Image.open(gt_png).convert("RGB")
            # resize to width 1000
            w, h = gt_img.size
            new_h = int(1000 * h / w)
            gt_img = gt_img.resize((1000, new_h))
            images.append(("GROUND TRUTH", gt_img))
            
        for i, asset in enumerate(assets):
            if os.path.exists(asset):
                a_img = PIL.Image.open(asset).convert("RGB")
                w, h = a_img.size
                if w > 800:
                    new_h = int(800 * h / w)
                    a_img = a_img.resize((800, new_h))
                images.append((f"ASSET {i+1}: {os.path.basename(asset)}", a_img))
                
        if not images:
            continue
            
        # create a big image
        total_height = sum(img.size[1] + 40 for _, img in images) + 100
        max_width = max(img.size[0] for _, img in images)
        if max_width < 1000:
            max_width = 1000
            
        # calculate text height roughly
        char_w, char_h = 7, 15
        lines = tex.split('\n')
        text_height = len(lines) * char_h + 50
        
        final_img = PIL.Image.new("RGB", (max_width + 50, total_height + text_height), "white")
        draw = ImageDraw.Draw(final_img)
        
        y_offset = 20
        for title, img in images:
            draw.text((20, y_offset), title, fill="red")
            y_offset += 20
            final_img.paste(img, (20, y_offset))
            y_offset += img.size[1] + 20
            
        draw.text((20, y_offset), "TEX SECTION:\n" + tex, fill="black")
        
        out_path = os.path.join(stitched_dir, f"slide_{slide_num:02d}.png")
        final_img.save(out_path)

print("Stitched images created.")
