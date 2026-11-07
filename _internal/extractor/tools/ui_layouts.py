"""Menu / HUD window layouts in ALUN_CD.EXE, drawn with the palette each 8x8 cell uses.

The EXE holds 24 layout headers {s16 columns, s16 rows, ptr cells, ptr end}; each
cell is 20 bytes {u32, u32, s16 x, s16 y, u8 u, u8 v, u16 palette, u16 w, u16 h}
into the WIND.TX texture (VRAM 0x380,0x100, 4bpp 256x256) with one of WIND.CL's 16
palettes (VRAM 0x120,0x1E0+n, EXE 0x80045ABC)."""
import struct
from exe_dis import D, BASE, SIZE, off


def layouts():
    out = []
    for a in range(BASE, BASE + SIZE - 12, 4):
        w, h, p, e = struct.unpack_from('<hhII', D, off(a))
        if 0 < w <= 64 and 0 < h <= 64 and BASE <= p < BASE + SIZE and e - p == w * h * 20:
            cells = []
            for i in range(w * h):
                _, _, x, y, u, v, pal, cw, ch = struct.unpack_from('<IIhhBBHHH', D, off(p) + 20 * i)
                cells.append(dict(x=x, y=y, u=u, v=v, pal=pal, w=cw, h=ch))
            out.append(dict(address=a, columns=w, rows=h, cells=cells))
    return out


def render(layout, tx, cl, psx_color):
    from PIL import Image
    pals = [[psx_color(v) for v in struct.unpack_from('<16H', cl, 32 * n)] for n in range(len(cl) // 32)]
    xs = [c['x'] + c['w'] for c in layout['cells']]; ys = [c['y'] + c['h'] for c in layout['cells']]
    img = Image.new('RGBA', (max(xs), max(ys)), (0, 0, 0, 0)); px = img.load()
    for c in layout['cells']:
        pal = pals[c['pal'] % len(pals)]
        for j in range(c['h']):
            for i in range(c['w']):
                X, Y = c['u'] + i, c['v'] + j
                b = tx[Y * 128 + X // 2]
                px[c['x'] + i, c['y'] + j] = pal[(b >> 4) if X & 1 else (b & 15)]
    return img


def export(out_dir):
    """ui/layouts/<address>.png + layouts.json, and wind_ingame.png: the WIND sheet with
    every 8x8 cell in the palette the game draws it with."""
    import json
    from collections import Counter
    from PIL import Image
    from remake_extract_disc import read_file, psx_color
    tx = read_file('TAKI/SCREEN/WIND.TX'); cl = read_file('TAKI/SCREEN/WIND.CL')
    d = out_dir / 'layouts'; d.mkdir(parents=True, exist_ok=True)
    rows = []; use = {}
    for L in layouts():
        name = f"{L['address']:08X}"
        render(L, tx, cl, psx_color).save(d / f'{name}.png')
        rows.append(dict(name=name, columns=L['columns'], rows=L['rows'], cells=L['cells']))
        for c in L['cells']:
            for j in range(0, c['h'], 8):
                for i in range(0, c['w'], 8):
                    use.setdefault(((c['u'] + i) // 8, (c['v'] + j) // 8), Counter())[c['pal']] += 1
    (d / 'layouts.json').write_text(json.dumps(rows))
    pals = [[psx_color(v) for v in struct.unpack_from('<16H', cl, 32 * n)] for n in range(16)]
    sheet = Image.new('RGBA', (256, 256), (0, 0, 0, 0)); px = sheet.load()
    for (cx, cy), cnt in use.items():
        pal = pals[cnt.most_common(1)[0][0]]
        for y in range(cy * 8, cy * 8 + 8):
            for x in range(cx * 8, cx * 8 + 8):
                b = tx[y * 128 + x // 2]; px[x, y] = pal[(b >> 4) if x & 1 else (b & 15)]
    sheet.save(out_dir / 'wind_ingame.png')
    json.dump({f'{k[0]},{k[1]}': v.most_common(1)[0][0] for k, v in use.items()}, (out_dir / 'wind_ingame_palettes.json').open('w'))
    return len(rows)
