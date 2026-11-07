"""Adds each animation's physics fields to the exported animations.json files.

An animation set record (14 bytes) is 4 stream offsets, u16 Speed, then
Unknown, Flags, Sfx, Acceleration (xcasadio AnimationSet.cs). The game uses them
(EntityManager.UpdateAnimation 0x80038AB4, PhysicsEngine 0x80036614):
  speed      walking speed: target force = direction table x speed
  accel      low nibble: force step = |target - force| >> accel; the whole byte
             becomes the entity's AnimFlags (0x10 no shadow, 0x40 invulnerable,
             0x80 no entity collision)
  z_force    signed (Flags << 8 | Unknown): on the first frame of the animation
             ForceZ = z_force << 8 (a jump impulse); -0x8000 = hold still in Z
  sfx        sound played when the animation starts (+0x100 if Flags & 0x20)
python tools/anim_tails.py [global | first last]
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets'


def tails(s, map_id, catalogue):
    from animation_preview import animation_reader
    _, sets = animation_reader(s, map_id, catalogue)
    out = []
    for st in sets:
        unknown, flags, sfx, accel = st.tail
        z = (flags << 8) | unknown
        if z & 0x8000: z -= 0x10000
        out.append({'speed': st.speed_raw, 'z_force': z, 'set_flags': flags, 'sfx': sfx + (0x100 if flags & 0x20 else 0),
                    'accel': accel & 15, 'anim_flags': accel})
    return out


def apply(meta, rows):
    by_index = {r_i: r for r_i, r in enumerate(rows)}
    for a in meta['animations']:
        r = by_index.get(a['index'])
        if r: a.update(r)
    meta['physics'] = True
    return meta


def redo(s, map_id, catalogue, folder):
    p = folder / 'animations.json'
    meta = json.loads(p.read_text())
    if meta.get('physics'): return
    p.write_text(json.dumps(apply(meta, tails(s, map_id, catalogue))), encoding='utf-8')


def main():
    from remake_export import session
    s = session()
    if sys.argv[1:2] == ['global']:
        for folder in sorted((OUT / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
            if (folder / 'animations.json').exists(): redo(s, 4, int(folder.name), folder)
        print('global done'); return
    for m in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
        base = OUT / 'maps' / f'{m:03d}' / 'sprites'
        for folder in sorted(base.glob('[0-9][0-9][0-9]')) if base.exists() else []:
            if (folder / 'animations.json').exists():
                try: redo(s, m, int(folder.name), folder)
                except Exception as exc: print('map', m, folder.name, exc)
        print('map', m, flush=True)


if __name__ == '__main__':
    main()
