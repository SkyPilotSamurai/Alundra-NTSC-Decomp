"""Export the dialogue portraits for the remake: a sprite whose header has flag 0x800000
(HasPortrait) shows image set 0 of its frames (SpriteRecord.GetPortraitImageset) in the
message window.  Writes remake/assets/maps/<map>/sprites/<catalogue>/portrait.png (and for
global sprites remake/assets/sprites/global/<n>/portrait.png).
    python tools/remake_export_portraits.py [first last]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets'


def save(s, map_id, cat, folder):
    import sprite_blend
    from animation_preview import animation_reader
    preview = animation_reader(s, map_id, cat)[0]
    table = preview.header[3]
    pointer = preview.read('i', preview.start + table + (cat & 255) * 4)[0]
    if pointer <= 0: raise ValueError('sprite unavailable')
    frames = preview.read('4I', preview.start + pointer)[3]
    layers, left, top = sprite_blend.compose(preview, preview.start + frames, 1)   # one image (isPortrait)
    folder.mkdir(parents=True, exist_ok=True)
    layers['normal'].save(folder / 'portrait.png')
    (folder / 'portrait.json').write_text(json.dumps({'left': left, 'top': top}))


def main():
    from remake_export import session
    s = session()
    lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, 482)
    G = json.loads((OUT / 'sprites' / 'global_headers.json').read_text())['sprite_headers']
    n = 0
    if lo == 0:
        try: save(s, 0, 0, OUT / 'sprites' / 'global' / '000'); n += 1     # Alundra: the menu's portrait
        except Exception as ex: print('global 0', ex)
        for k, h in G.items():
            if h['flags'] & 0x800000 and int(k) != 0:
                try: save(s, 0, int(k), OUT / 'sprites' / 'global' / f'{int(k):03d}'); n += 1
                except Exception as ex: print('global', k, ex)
    for m in range(lo, hi + 1):
        f = OUT / 'maps' / f'{m:03d}' / 'data.json'
        if not f.exists(): continue
        d = json.loads(f.read_text())
        for k, h in d.get('sprite_headers', {}).items():
            if not h['flags'] & 0x800000 or int(k) < 256: continue
            try: save(s, m, int(k), OUT / 'maps' / f'{m:03d}' / 'sprites' / k); n += 1
            except Exception as ex: print('map', m, k, ex)
    print('portraits', n)


if __name__ == '__main__':
    main()
