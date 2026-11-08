"""The ending's credits (CLOSING.EXE) for the remake: remake/assets/ending/.

CLOSING.EXE holds its own pictures and texts:
  0x8003041C  21 picture records, 12 bytes {u32 frames (unused), u32 TIM, u16 layout}; the TIMs are
              256x240 16 bpp (two 128x240 portraits each; THE END is 256x256 at 0x8015C64C)
  0x8002F9CC  credit pages, 0x58 bytes {u32 type, u32 hold, 10 x {s16 style, pad, u32 text}}
              (type 0 ends the list)
  0x8017C668  the gothic font, 4 bpp 256x256 (palette row 0 is the one used)
  0x8002EFCC  its glyphs, 20 bytes {w, h, u, v, y offset}
  0x80030524  the ENDING.XA song {start sector, channel, length / 8}
Run: python tools/remake_export_ending.py"""
import json, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / 'private-inputs/disc/CLOSING.EXE'
OUT = ROOT / 'remake' / 'assets' / 'ending'
import sys
sys.path.insert(0, str(ROOT / 'tools'))
from remake_export_title import tim_image


def off(a): return a - 0x80020000 + 0x800


def main():
    d = EXE.read_bytes()
    w32 = lambda a: struct.unpack_from('<I', d, off(a))[0]
    s = lambda a: d[off(a):d.index(b'\0', off(a))].decode('latin-1') if a else None
    OUT.mkdir(parents=True, exist_ok=True)
    pictures = []; saved = set()
    a = 0x8003041C
    while True:
        frames, tim, layout = struct.unpack_from('<iIH', d, off(a))
        if tim == 0: break
        name = f'{tim:08X}.png'
        if tim not in saved:
            img = tim_image(d[off(tim):])
            img.save(OUT / name); saved.add(tim)
        pictures.append({'image': name, 'layout': layout, 'frames': frames})
        a += 12
    pages = []
    a = 0x8002F9CC
    while True:
        t, hold = w32(a), w32(a + 4)
        lines = []
        for k in range(10):
            style = struct.unpack_from('<h', d, off(a + 8 + 8 * k))[0]
            p = w32(a + 0xC + 8 * k)
            if not p: break
            lines.append({'style': style, 'text': s(p)})
        pages.append({'type': t, 'hold': hold, 'lines': lines})
        if t == 0: break
        a += 0x58
    font = tim_image(d[off(0x8017C668):])
    font.save(OUT / 'font.png')
    glyphs = {c: dict(zip(('w', 'h', 'u', 'v', 'y'), struct.unpack_from('<5i', d, off(0x8002EFCC) + 0x14 * c)))
              for c in range(0x80)}
    song = struct.unpack_from('<3I', d, off(0x80030524))
    (OUT / 'credits.json').write_text(json.dumps({'pictures': pictures, 'pages': pages, 'glyphs': glyphs,
                                                  'song': {'start': song[0], 'channel': song[1], 'length': song[2]}}, indent=1))
    print('pictures', len(pictures), 'pages', len(pages))


if __name__ == '__main__':
    main()
