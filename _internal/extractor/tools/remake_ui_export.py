"""Menu font, text box and HUD pieces as the game draws them.

* ui/font.png: FONT3.TIM (16x16 cells) in WIND.CL palette 8, the palette the text
  sprites use; ui/font.json: per character byte {advance, u, v} (glyph widths:
  g_fontCharWidthTable 0x800993C4 in RAM, values from the MIT xcasadio project,
  v is relative to the TIM).
* ui/layouts/*.png: the 24 window/HUD layouts with each cell's own palette.
* ui/text_box.png: the message window (layout 0x8009EE28, drawn at 16,168).
* ui/wind_ingame.png: WIND sheet with each cell in the palette the game uses."""
import json, struct
from pathlib import Path
from remake_extract_disc import read_file, psx_color, image_4bpp
import ui_layouts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'remake/assets/ui'


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    cl = read_file('TAKI/SCREEN/WIND.CL'); d = read_file('TAKI/SCREEN/FONT3.TIM')
    o = 8 + struct.unpack_from('<I', d, 8)[0]
    n, x, y, w, h = struct.unpack_from('<I4H', d, o)
    pal = [psx_color(v) for v in struct.unpack_from('<16H', cl, 32 * 8)]
    image_4bpp(d[o + 12:o + n], w * 4, h, pal).save(OUT / 'font.png')
    raw = json.loads((ROOT / 'tools/font_widths_raw.json').read_text())
    chars = {c: {'advance': raw[c * 5], 'u': raw[c * 5 + 2], 'v': raw[c * 5 + 3] - 16} for c in range(256) if raw[c * 5]}
    (OUT / 'font.json').write_text(json.dumps(chars))
    ui_layouts.export(OUT)
    from PIL import Image
    box = Image.open(OUT / 'layouts' / '8009EE28.png').crop((16, 168, 16 + 36 * 8, 168 + 7 * 8))
    box.save(OUT / 'text_box.png')
    return len(chars)


if __name__ == '__main__':
    print(export())
