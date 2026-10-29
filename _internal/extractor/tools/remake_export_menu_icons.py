"""The pictures the menus draw (0x8004F05C: image 0x80059958(item record +8) = the first image of
image set 0 of that global sprite record) for every global sprite record: writes
remake/assets/sprites/global/<n>/image0.png (+ image0.json with the image's offsets).
    python tools/remake_export_menu_icons.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets' / 'sprites' / 'global'


def main():
    from remake_export import session
    import sprite_blend
    from animation_preview import animation_reader
    s = session(); n = 0
    for k in range(256):
        try:
            preview = animation_reader(s, 0, k)[0]
            table = preview.header[3]
            pointer = preview.read('i', preview.start + table + k * 4)[0]
            if pointer <= 0: continue
            frames = preview.read('4I', preview.start + pointer)[3]
            layers, left, top = sprite_blend.compose(preview, preview.start + frames, 1)
            d = OUT / f'{k:03d}'; d.mkdir(parents=True, exist_ok=True)
            layers['normal'].save(d / 'image0.png'); (d / 'image0.json').write_text(json.dumps({'left': left, 'top': top}))
            n += 1
        except Exception as ex:
            pass
    print('images', n)


if __name__ == '__main__':
    main()
