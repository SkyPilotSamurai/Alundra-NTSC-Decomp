"""Animated map tiles (water, lava, waterfalls), as the game runs them.

Map info +0x420 holds 6 pairs {frames log2, ticks per frame}, one per tile page
(160 tiles = 10 x 16 each). An enabled page shows 2^n frames, each 160/2^n tiles
long; every `ticks` frames the game adds frame*tiles_per_frame to the tile number of
every tile drawn from that page (EXE 0x8002CC58 InitializeMapSpriteTable,
0x8002CFD8 update; xcasadio GraphicManager.GetAnimatedTileId).

Adds data.json 'tile_animations' and the extra frames to tiles.png / tiles.json."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from remake_export import OUT, session


def animations(s, m):
    base, h = s.layout(m); i = base + h[0] + 0x420; d = s.data
    out = []
    for page in range(6):
        n, ticks = d[i + 2 * page], d[i + 2 * page + 1]
        if n and ticks:
            frames = 1 << (n & 31)
            out.append({'page': page, 'frames': frames, 'ticks': ticks, 'tiles_per_frame': 160 // frames})
    return out


def frame_codes(code, anims):
    tile = code & 1023
    for a in anims:
        if a['page'] == tile // 160:
            return [code + k * a['tiles_per_frame'] for k in range(1, a['frames'])]
    return []


def update_map(s, m):
    from PIL import Image
    from area_map import MapRenderer
    folder = OUT / 'maps' / f'{m:03d}'
    anims = animations(s, m)
    df = folder / 'data.json'
    if df.exists():
        data = json.loads(df.read_text()); data['tile_animations'] = anims; df.write_text(json.dumps(data))
    if not anims or not (folder / 'tiles.json').exists():
        return 0
    index = {int(k): v for k, v in json.loads((folder / 'tiles.json').read_text()).items()}
    extra = sorted({c for code in index for c in frame_codes(code, anims)} - set(index))
    if not extra:
        return 0
    atlas = Image.open(folder / 'tiles.png').convert('RGBA'); r = MapRenderer(s, m)
    n = len(index); total = n + len(extra)
    big = Image.new('RGBA', (32 * 24, (total + 31) // 32 * 16), (0, 0, 0, 0)); big.alpha_composite(atlas, (0, 0))
    for i, code in enumerate(extra, n):
        big.alpha_composite(r.tile(code), (i % 32 * 24, i // 32 * 16)); index[code] = i
    big.save(folder / 'tiles.png')
    (folder / 'tiles.json').write_text(json.dumps({str(c): i for c, i in index.items()}))
    return len(extra)


if __name__ == '__main__':
    s = session(); a, b = int(sys.argv[1]), int(sys.argv[2])
    for m in range(a, b):
        try: print(m, update_map(s, m), end='; ', flush=True)
        except Exception as e: print(m, 'failed', e)
