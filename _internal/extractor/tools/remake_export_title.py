"""The boot program's pictures and texts (SLUS_005.53: the title screen, the memory-card scroll and
its font, the "Now Loading" screen) for the remake: remake/assets/title/.

The pictures are TIMs in the archive at 0x800438A8 (entries {u32 'TIM'/'ANM' + index << 24,
u32 size, data}, ended by 'END\\xff'; 0x80027540 finds one):
  TIM 0  320x240 8 bpp: the title, START / CONTINUE, the copyright lines, the TM mark
  ANM 1-9  320x160 8 bpp: the burning logo, each with its own palette (0x80021CB8 uploads one
           every 9 frames, cycling 4..9 after 1..3 are skipped - D_80042DDC starts at 3)
  TIM 3  the memory-card scroll pieces (4 bpp)     TIM 4  the gothic font (4 bpp)
  TIM 6  320x240 16 bpp: Now Loading (0x800252E0, shown while ALUN_CD.EXE loads)
  TIM 1, 2, 5: the library scene of the History Book (saved games): remake/history_book.py
           draws them from the program image itself (tools/remake_export_boot.py).
Glyphs: 0x80042DF8, 20 bytes per character {w, h, u, v, y offset} (0x80022718: advance w + 1).
Texel 0x0000 is see-through, as on the GPU.
Run: python tools/remake_export_title.py"""
import json, struct
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / 'private-inputs/disc/SLUS_005.53'
OUT = ROOT / 'remake' / 'assets' / 'title'
BASE = 0x80020000


def off(a): return a - BASE + 0x800


def colour(v): return ((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3, 0 if v == 0 else 255)


def archive(d):
    p = off(0x800438A8); out = {}
    while True:
        tag = struct.unpack_from('<I', d, p)[0]
        if tag == 0xFF444E45: return out
        size = struct.unpack_from('<I', d, p + 4)[0]
        out[(d[p:p + 3].decode(), d[p + 3])] = d[p + 8:p + 8 + size]
        p += 8 + size


def tim_image(t):
    fl = struct.unpack_from('<I', t, 4)[0]; q = 8; clut = None
    if fl & 8:
        n = struct.unpack_from('<I', t, q)[0]; cw, ch = struct.unpack_from('<2H', t, q + 8)
        clut = struct.unpack_from(f'<{cw * ch}H', t, q + 12); q += n
    n = struct.unpack_from('<I', t, q)[0]; iw, ih = struct.unpack_from('<2H', t, q + 8); pix = t[q + 12:q + n]
    bpp = fl & 7; w = {0: iw * 4, 1: iw * 2}.get(bpp, iw)
    img = Image.new('RGBA', (w, ih)); px = img.load()
    for y in range(ih):
        for x in range(w):
            if bpp == 1: v = clut[pix[y * w + x]]
            elif bpp == 0:
                b = pix[(y * w + x) // 2]; v = clut[(b >> 4) if x & 1 else b & 15]
            else: v = struct.unpack_from('<H', pix, (y * w + x) * 2)[0]
            px[x, y] = colour(v)
    return img


def text(d, a):
    o = off(a); return d[o:d.index(b'\0', o)].decode('latin-1')


def main():
    d = EXE.read_bytes(); arc = archive(d)
    OUT.mkdir(parents=True, exist_ok=True)
    tim_image(arc[('TIM', 0)]).save(OUT / 'title.png')
    for i in range(1, 10): tim_image(arc[('ANM', i)]).save(OUT / f'logo{i}.png')
    tim_image(arc[('TIM', 3)]).save(OUT / 'scroll.png')
    tim_image(arc[('TIM', 4)]).save(OUT / 'font.png')
    img = tim_image(arc[('TIM', 6)]); img.putalpha(255); img.save(OUT / 'loading.png')
    glyphs = {}
    for c in range(0x80):
        w, h, u, v, y = struct.unpack_from('<5i', d, off(0x80042DF8) + 0x14 * c)
        glyphs[c] = {'w': w, 'h': h, 'u': u, 'v': v, 'y': y}
    texts = {k: text(d, a) for k, a in (('insert', 0x8002010C), ('no_card', 0x80020144), ('no_record', 0x80020190),
                                          ('broken', 0x800201C4), ('no_save', 0x8002020C), ('using', 0x80020258))}
    (OUT / 'title.json').write_text(json.dumps({'glyphs': glyphs, 'texts': texts}, indent=1))
    print('title assets', sorted(p.name for p in OUT.iterdir()))


if __name__ == '__main__':
    main()
