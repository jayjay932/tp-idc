"""Visualise les journaux réels ; ne fabrique pas de captures GitHub."""
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]
font=ImageFont.truetype("DejaVuSansMono.ttf",15)
title=ImageFont.truetype("DejaVuSans.ttf",22)
for name in ("01-invalid-csv", "02-corrected", "04-db-retry"):
    path=root/"docs/evidence"/(name+".log")
    lines=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        lines.extend(textwrap.wrap(line,width=128,replace_whitespace=False) or [""])
    image=Image.new("RGB",(1240,110+len(lines)*22),(17,24,39))
    draw=ImageDraw.Draw(image)
    draw.text((24,18),"Sortie exécutée — visualisation du journal",font=title,fill=(240,245,255))
    draw.text((24,53),name+" | Ce visuel n'est pas une capture GitHub Actions",font=font,fill=(160,180,205))
    for i,line in enumerate(lines):
        color=(248,150,150) if "Error" in line or "ÉCHEC" in line else (210,225,240)
        draw.text((24,92+i*22),line,font=font,fill=color)
    image.save(path.with_suffix(".png"))
