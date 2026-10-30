"""Write a sprite frame the way the game draws it (sprite_blend):
<id>.png  the frame (opaque pixels; 50% blends as half alpha)
<id>_add.png / <id>_sub.png  glow / shadow layers to add / subtract on top.

Also re-does every already exported sprite folder:  python tools/blend_frames.py [first_map last_map | global]
python tools/blend_frames.py sort [first_map last_map | global] only adds each frame's 'sort': the
image set's first byte, the sort bias UpdateAnimation (ALUN_CD.EXE 0x800393A4) copies to the
entity (+0x1A8); its drawing key (0x8003A0B0, +0x1BC) is its y + that many rows of a pixel.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets'


def save_frame(preview, sprite, image_id, folder):
    """Returns the extra layer names written (e.g. ['add'])."""
    import sprite_blend
    layers, left, top = sprite_blend.image_set_layers(preview, sprite, image_id)
    layers['normal'].save(folder / f'{image_id}.png')
    extra = []
    for name in ('add', 'sub'):
        p = folder / f'{image_id}_{name}.png'
        if name in layers: layers[name].save(p); extra.append(name)
        elif p.exists(): p.unlink()
    return extra


def redo_folder(s, map_id, catalogue, folder):
    from animation_preview import animation_reader
    meta_path = folder / 'animations.json'
    meta = json.loads(meta_path.read_text())
    preview, _ = animation_reader(s, map_id, catalogue)
    ids = sorted({f['image'] for a in meta['animations'] for d in a['directions'] if d for f in d['frames'] if f['image'] is not None})
    blend = {}
    for i in ids:
        try:
            extra = save_frame(preview, catalogue & 255, i, folder)
            if extra: blend[str(i)] = extra
        except Exception:
            pass
    meta['blend'] = blend
    meta_path.write_text(json.dumps(meta), encoding='utf-8')
    return len(ids), len(blend)


def image_sort(preview, sprite, image_set_index):
    """The image set's first byte (the frame's sort bias)."""
    table = preview.header[3]
    pointer = preview.read('i', preview.start + table + sprite * 4)[0]
    if pointer <= 0: return 0
    frames = preview.read('4I', preview.start + pointer)[3]
    return preview.read('B', preview.start + frames + image_set_index * 2)[0]


def sort_folder(s, map_id, catalogue, folder):
    from animation_preview import animation_reader
    meta_path = folder / 'animations.json'
    meta = json.loads(meta_path.read_text())
    preview, _ = animation_reader(s, map_id, catalogue)
    n = 0
    for a in meta['animations']:
        for d in a['directions']:
            for f in (d or {}).get('frames', []) if isinstance(d, dict) else []:
                try: f['sort'] = image_sort(preview, catalogue & 255, f['image']) if f['image'] is not None else 0
                except Exception: f['sort'] = 0
                n += 1
    meta_path.write_text(json.dumps(meta), encoding='utf-8')
    return n


def main():
    from remake_export import session
    s = session()
    if sys.argv[1:2] == ['sort']:
        args = sys.argv[2:]
        if args[:1] == ['global']:
            for folder in sorted((OUT / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
                if (folder / 'animations.json').exists():
                    try: print(folder.name, sort_folder(s, 4, int(folder.name), folder), flush=True)
                    except Exception as exc: print(folder.name, 'failed', exc, flush=True)
            return
        for m in range(int(args[0]), int(args[1]) + 1):
            base = OUT / 'maps' / f'{m:03d}' / 'sprites'
            n = 0
            for folder in sorted(base.glob('[0-9][0-9][0-9]')) if base.exists() else []:
                if (folder / 'animations.json').exists():
                    try: sort_folder(s, m, int(folder.name), folder); n += 1
                    except Exception as exc: print('map', m, folder.name, 'failed', exc, flush=True)
            print('map', m, n, flush=True)
        return
    if sys.argv[1:2] == ['global']:
        for folder in sorted((OUT / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
            if (folder / 'animations.json').exists():
                print(folder.name, *redo_folder(s, 4, int(folder.name), folder), flush=True)
        return
    first, last = int(sys.argv[1]), int(sys.argv[2])
    for m in range(first, last + 1):
        base = OUT / 'maps' / f'{m:03d}' / 'sprites'
        n = 0
        for folder in sorted(base.glob('[0-9][0-9][0-9]')) if base.exists() else []:
            if (folder / 'animations.json').exists():
                if '"blend"' in (folder / 'animations.json').read_text(): continue
                try: redo_folder(s, m, int(folder.name), folder); n += 1
                except Exception as exc: print('map', m, folder.name, 'failed', exc)
        print('map', m, n, flush=True)


if __name__ == '__main__':
    main()
