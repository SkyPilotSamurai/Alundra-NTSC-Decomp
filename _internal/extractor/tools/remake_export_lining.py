"""Map background layers ("lining": the sea, sky, clouds, fog, rain behind or over
the map) exported for the remake.  Format from the MIT xcasadio project
(DatasBin/ScrollScreen.cs; EXE RenderAllTileLayers 0x8005B670, RenderLayerToBuffer
0x8005B848, RenderTileOverlayLayer 0x8005BA40).

Section (map header offset 5):  u32 graphics, layer0, layer1, script, overlay,
overlay_ext, wave_lut; info {enabled, anim_num, mode0, mode1, r, g, b, overlay_flag}.
graphics: 8 palettes x 16 colours, then a 256x256 4bpp sheet (EZ-compressed or raw
0x8000 bytes); mode-1 layers read a 40x30 map of {tile, palette} at graphics+0x8100
(+0x960 for the second layer when both are mode 1).  layer: {_, anim_timer, blend,
ground} then a scrollar {fx_num, fx_den, fy_num, fy_den, dx, period_x, dy, period_y}
or a cellular {count, a_wave_y, a_wave_phase, a_wave_amp, b_wave_y, b_wave_phase,
b_wave_weight, divisions} + 20-byte cells.

Writes maps/NNN/lining.json and lining.png (8 palettes stacked: 256 x 2048; pixels
whose colour has the semi-transparent bit go to lining_st.png when the layer blends)."""
import json, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from remake_export import OUT, session


def unzip(src):
    if len(src) < 2 or (src[0] | src[1] << 8) != 0x5A45:
        return bytes(src[:0x8000]).ljust(0x8000, b'\0')
    r = 6; out = bytearray()
    while r < len(src):
        cur = src[r]; r += 1
        if cur == 0xAD:
            if r >= len(src): break
            dist = src[r]; r += 1
            if dist == 0: out.append(cur); continue
            if r >= len(src): break
            ln = src[r]; r += 1
            if dist == 0xFF and ln == 0: break
            seek = len(out) - dist
            for _ in range(ln): out.append(out[seek]); seek += 1
        else:
            out.append(cur)
    return bytes(out)


def section(s, m):
    base, h = s.layout(m)
    so = h[5]
    if so in (0, -1) or so >= 0x7FFFFFFF: return None
    nxt = min([x for x in h if x > so] or [so])
    if nxt - so < 0x24: return None
    return s.data[base + so:base + nxt]


def parse(d):
    g, l0, l1, script, ovl, ovx, wave = struct.unpack_from('<7I', d, 0)
    en, anim_num, m0, m1, r, gg, b, flag = d[28:36]
    if not en: return None
    out = {'anim_num': anim_num, 'modes': [m0, m1], 'overlay_flag': flag, 'layers': [], 'wave_lut': [], 'overlay': []}
    has_gfx = g < len(d) and len(d) - g > 256
    out['has_graphics'] = has_gfx
    if wave and wave + 1024 <= len(d):
        out['wave_lut'] = list(struct.unpack_from('<256i', d, wave))
    for k, (lo, mode) in enumerate(((l0, m0), (l1, m1))):
        lay = {'mode': mode}
        if mode and 0 <= lo and lo + 12 <= len(d):
            _, anim_timer, blend, ground = d[lo:lo + 4]
            lay.update(anim_timer=anim_timer, blend=blend, ground=ground)
            if mode == 1:
                lay['scroll'] = list(struct.unpack_from('<8b', d, lo + 4))
                second = k == 1 and m0 == 1 and m1 == 1
                mo = g + 0x8100 + (0x960 if second else 0)
                lay['map'] = list(d[mo:mo + 0x960]) if mo + 0x960 <= len(d) else []
            elif mode == 2:
                cel = list(d[lo + 4:lo + 12]); lay['cellular'] = cel
                n = min(200, cel[0] + cel[7]); cells = []
                for i in range(n):
                    o = lo + 12 + 20 * i
                    if o + 20 > len(d): break
                    pal, u0, v0, u1, v1, typ, x0, y0, cxn, cxd, cyn, cyd, dx, px, dy, py = struct.unpack_from('<6B2h8b', d, o)
                    cells.append(dict(pal=pal, u0=u0, v0=v0, u1=u1, v1=v1, type=typ, x0=x0, y0=y0,
                                      cam=[cxn, cxd, cyn, cyd], dx=dx, px=px, dy=dy, py=py))
                lay['cells'] = cells
        out['layers'].append(lay)
    if flag:
        ext = flag >= 0x65; ptr = ovx if ext else ovl; size = 16 if ext else 4
        o = ptr; frames = []
        while ptr and o + size <= len(d) and len(frames) < 256:
            fr = list(d[o:o + size]); frames.append(fr); o += size
            if (fr[12] if ext else fr[3]) == 0: break
        out['overlay'] = frames; out['overlay_ext'] = ext
    return out, g


def export_map(s, m):
    from PIL import Image
    d = section(s, m)
    folder = OUT / 'maps' / f'{m:03d}'
    if d is None: return 0
    res = parse(d)
    if res is None: return 0
    info, g = res
    if info['has_graphics']:
        words = [struct.unpack_from('<16H', d, g + 32 * p) for p in range(8)]
        sheet = unzip(d[g + 256:g + 256 + min(0x8000, len(d) - g - 256)])
        blend_any = any(l.get('blend') in (1, 2, 3, 4) for l in info['layers'])
        op = Image.new('RGBA', (256, 256 * 8), (0, 0, 0, 0)); st = Image.new('RGBA', (256, 256 * 8), (0, 0, 0, 0)) if blend_any else None
        po = op.load(); ps = st.load() if st else None
        for p in range(8):
            cols = [((w & 31) * 255 // 31, (w >> 5 & 31) * 255 // 31, (w >> 10 & 31) * 255 // 31, 255) for w in words[p]]
            for y in range(256):
                row = sheet[y * 128:(y + 1) * 128]
                for xb, b in enumerate(row):
                    for half, idx in ((0, b & 15), (1, b >> 4)):
                        w = words[p][idx]
                        if w & 0x7FFF == 0 and not w & 0x8000: continue
                        if ps is not None and w & 0x8000: ps[xb * 2 + half, p * 256 + y] = cols[idx]
                        else: po[xb * 2 + half, p * 256 + y] = cols[idx]
        folder.mkdir(parents=True, exist_ok=True)
        op.save(folder / 'lining.png')
        if st: st.save(folder / 'lining_st.png')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'lining.json').write_text(json.dumps(info))
    return 1


if __name__ == '__main__':
    s = session(); a, b = int(sys.argv[1]), int(sys.argv[2]); n = 0
    for m in range(a, b):
        try: n += export_map(s, m)
        except Exception as e: print(m, 'failed', e)
    print('lining maps', n)
