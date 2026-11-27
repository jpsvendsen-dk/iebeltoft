"""Pack the generated 4x4 cutout sheet for the browser's 2D skeleton.

Usage: python scripts/build_elf_assets.py PATH_TO_GENERATED_PNG
Only crops and scales the generated cutouts; no drawn replacement artwork.
"""
import json
import sys
from pathlib import Path
from PIL import Image

source = Path(sys.argv[1])
destination = Path(__file__).resolve().parents[1] / 'static' / 'jul2026'
parts = []
atlas = Image.new('RGBA', (1024, 1024))
with Image.open(source) as sheet:
    sheet = sheet.convert('RGBA')
    for i in range(16):
        col, row = i % 4, i // 4
        tile = sheet.crop((round(col*sheet.width/4), round(row*sheet.height/4), round((col+1)*sheet.width/4), round((row+1)*sheet.height/4)))
        # Ignore nearly transparent pixels when locating each generated cutout.
        bounds = tile.getchannel('A').point(lambda alpha: 255 if alpha > 100 else 0).getbbox()
        if not bounds:
            raise ValueError(f'Cutout {i} is missing')
        piece = tile.crop(bounds)
        piece.thumbnail((244,244), Image.Resampling.LANCZOS)
        x, y = col*256+(256-piece.width)//2, row*256+(256-piece.height)//2
        atlas.paste(piece, (x,y))
        parts.append({'x':x,'y':y,'w':piece.width,'h':piece.height})
atlas.save(destination / 'elf-atlas-v1.webp', 'WEBP', lossless=True, method=6, exact=True)
(destination / 'elf-atlas-v1.json').write_text(json.dumps({'version':1,'parts':parts},indent=2)+'\n',encoding='utf-8')
print(f'Packed 16 parts: {(destination / "elf-atlas-v1.webp").stat().st_size} bytes')
