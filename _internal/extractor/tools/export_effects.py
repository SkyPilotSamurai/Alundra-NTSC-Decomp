"""Export the effect sprites (shadows, splashes, sparkles, explosions, warps...).

Each sprite bank (the global one and every map's) has, after its sprite table, a
table of effect records (SpriteInfoHeader.SpriteEffectsPointer, header[4]; i32 offsets
up to the first 0). An effect record is a list of u16 animation offsets (the first
one / 2 = how many); an animation is 3-byte frames (delay | 0x80, u16 image set / 2)
ending in a byte without bit 7 (0 = then play animation <next byte>). Image sets
are the same 14-byte pieces as sprites, drawn with the bank's texture and palettes
(xcasadio SpriteEffectRecord / SiEffectAnimation / SiEffectFrame).  An image set starts
with two bytes: a sort bias and the piece count.  ALUN_CD.EXE 0x8003C548 copies them to
the effect record (+0x20, +0x24) with each frame; a free effect's drawing key (0x8003CC64,
+0x64) is its y + bias rows of a pixel (exported as the frame's 'sort').

Writes remake/assets/effects/global/NNN/ and maps/MMM/effects/NNN/:
<image>.png (+ _add / _sub blend layers) and animations.json.
python tools/export_effects.py [sort] [global | first last]   ('sort': only add the sort bytes)
"""
import json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets'


def effect_records(pv):
    table = pv.start + pv.header[4]; stop = pv.start + pv.header[5]
    out = []
    p = table
    while p + 4 <= stop and len(out) < 255:
        off = pv.read('i', p)[0]
        if off == 0: break
        out.append(off); p += 4
    return out


def parse_effect(pv, off):
    base = pv.start + off
    first = pv.read('h', base)[0]
    if first <= 0 or first > 512: raise ValueError('bad effect record')
    count = first // 2
    anims = []
    for a in range(count):
        ao = pv.read('h', base + a * 2)[0]
        frames = []; p = base + ao; end = ('stop', None)
        for _ in range(256):
            b = pv.read('B', p)[0]
            if not b & 0x80:
                end = ('change', pv.read('B', p + 1)[0]) if b == 0 else ('hold', b)
                break
            img = pv.read('H', p + 1)[0] * 2
            frames.append({'image': img, 'ticks': max(1, b & 0x7F)}); p += 3
        anims.append({'index': a, 'frames': frames, 'end': end[0], 'next': end[1]})
    return base, anims


def frame_sort(pv, base, k):
    """The image set's first byte (0 for the 'no picture' image 0xFFFF)."""
    if k == 0xFFFF * 2: return 0
    try: return pv.read('B', base + k)[0]
    except Exception: return 0


def add_sort(pv, folder):
    """Only the 'sort' bytes, into animations.json files already exported."""
    n = 0
    for i, off in enumerate(effect_records(pv)):
        d = folder / f'{i:03d}' / 'animations.json'
        if off == -1 or not d.exists(): continue
        try: base, anims = parse_effect(pv, off)
        except Exception: continue
        meta = json.loads(d.read_text())
        for a, src in zip(meta['animations'], anims):
            for f, g in zip(a['frames'], src['frames']):
                f['sort'] = frame_sort(pv, base, g['image'])
        d.write_text(json.dumps(meta), encoding='utf-8'); n += 1
    return n


def export_bank(pv, folder):
    import sprite_blend
    n = 0
    for i, off in enumerate(effect_records(pv)):
        if off == -1: continue
        try: base, anims = parse_effect(pv, off)
        except Exception: continue
        d = folder / f'{i:03d}'; d.mkdir(parents=True, exist_ok=True)
        saved = {}; blend = {}
        for a in anims:
            for f in a['frames']:
                k = f['image']
                if k not in saved:
                    try:
                        pos = base + k; _, cnt = pv.read('2B', pos)
                        layers, left, top = sprite_blend.compose(pv, pos, cnt)
                        layers['normal'].save(d / f'{k}.png')
                        extra = [name for name in ('add', 'sub') if name in layers]
                        for name in extra: layers[name].save(d / f'{k}_{name}.png')
                        if extra: blend[str(k)] = extra
                        saved[k] = (left, top)
                    except Exception:
                        saved[k] = None
                pos = saved[k]
                f['sort'] = frame_sort(pv, base, k)
                f['left'], f['top'] = pos if pos else (0, 0)
                if pos is None: f['image'] = None
        (d / 'animations.json').write_text(json.dumps({'effect': i, 'animations': anims, 'blend': blend}), encoding='utf-8')
        n += 1
    return n


def main():
    from remake_export import session
    from entity_preview import cached_preview
    s = session()
    args = sys.argv[1:]
    job = export_bank
    if args[:1] == ['sort']: job = add_sort; args = args[1:]
    if args[:1] == ['global']:
        pv = cached_preview(s, 0, True)
        print('global effects', job(pv, OUT / 'effects' / 'global')); return
    for m in range(int(args[0]), int(args[1]) + 1):
        try:
            pv = cached_preview(s, m)
            print('map', m, job(pv, OUT / 'maps' / f'{m:03d}' / 'effects'), flush=True)
        except Exception as exc:
            print('map', m, 'failed', exc, flush=True)


if __name__ == '__main__':
    main()
