"""Per-frame attack boxes for every exported sprite (animations.json 'boxes').

A frame's collision offset (frame bytes 1-2, -1 = none) points into the sprite's
frame-collision area (sprite record header +8); each box is 6 bytes
{s8 x, s8 y, s8 z, u8 width, u8 depth, u8 height} relative to the entity's position
(xcasadio FrameCollisionData / EntityManager.UpdateAnimation).  While a frame with a
box is showing, the entity's current attack (balance record) can hit others."""
import json, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from remake_export import OUT, session
from animation_preview import animation_reader


def boxes_for(s, map_id, catalogue, raws):
    preview, _ = animation_reader(s, map_id, catalogue)
    d = s.data; start = preview.start
    table = start + preview.header[3]
    rel = struct.unpack_from('<i', d, table + (catalogue & 255) * 4)[0]
    rec = start + rel
    coll = struct.unpack_from('<I', d, rec + 8)[0]
    out = {}
    for r in raws:
        ox, oy, oz, w, dp, h = struct.unpack_from('<3b3B', d, start + coll + r)
        out[str(r)] = [ox, oy, oz, w, dp, h]
    return out


def update(folder, s, map_id, catalogue):
    f = folder / 'animations.json'
    if not f.exists(): return 0
    meta = json.loads(f.read_text())
    raws = sorted({fr['collision'] for a in meta['animations'] for dd in a['directions'] if dd for fr in dd['frames']
                   if fr.get('collision', -1) not in (-1, None, 0xFFFF)})
    meta['boxes'] = boxes_for(s, map_id, catalogue, raws) if raws else {}
    f.write_text(json.dumps(meta))
    return len(raws)


if __name__ == '__main__':
    s = session(); what = sys.argv[1]
    if what == 'global':
        n = 0
        for d in sorted((OUT / 'sprites' / 'global').iterdir()):
            if d.is_dir():
                try: n += update(d, s, 4, int(d.name))
                except Exception as e: print(d.name, 'failed', e)
        print('global boxes', n)
    else:
        a, b = int(sys.argv[2]), int(sys.argv[3]); n = 0
        for m in range(a, b):
            sd = OUT / 'maps' / f'{m:03d}' / 'sprites'
            if not sd.exists(): continue
            for d in sorted(sd.iterdir()):
                if d.is_dir():
                    try: n += update(d, s, m, int(d.name))
                    except Exception as e: print(m, d.name, 'failed', e)
        print('map boxes', n)
