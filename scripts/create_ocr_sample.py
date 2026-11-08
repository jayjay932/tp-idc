"""Régénère l'image OCR lisible (Pillow facultatif hors développement)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datapipeline.generator import A, B
line=f'2026-09-12T14:30:00+00:00 | {A} | FR | BanqueA | {B} | DE | 6200.00'
try:
    font=ImageFont.truetype('DejaVuSansMono.ttf',24)
except OSError:
    font=ImageFont.load_default(size=24)
bbox=font.getbbox(line)
image=Image.new('RGB',(bbox[2]+80,100),'white')
ImageDraw.Draw(image).text((30,30),line,font=font,fill='black')
path=Path(__file__).resolve().parents[1]/'examples/transaction.png'
image.save(path)
print(path)
