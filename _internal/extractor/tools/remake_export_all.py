"""Export every graphic and map the remake uses, with names, from the editor's
current data (so your mod's edits and new classes come along).

Writes remake/assets:  maps/NNN/{map.json, map.png, tiles.png, tiles.json,
warps.json, sprites/...}, sprites/global/NNN/ (frame PNGs + animations.json
with the class name) and names.json (map and sprite names).
Used by the Database window's "Export all graphics" button; also runs alone:
python tools/remake_export_all.py
"""
import json, sys, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from remake_export import OUT, export_map, export_sprite, session as disc_session
from remake_export_warps import warps

GLOBAL_SOURCE_MAP = 4      # a map whose sprite set holds the global (shared) sprites


def export_tiles(s, m):
    from PIL import Image
    from area_map import grid, MapRenderer
    w, h, cells = grid(s, m); r = MapRenderer(s, m)
    codes = sorted(({c['values'][4] for c in cells} | {cd for c in cells for _, cd, _, _ in c['walls']}) - {0xFFFF})
    atlas = Image.new('RGBA', (32 * 24, max(1, (len(codes) + 31) // 32) * 16), (0, 0, 0, 0))
    for i, code in enumerate(codes): atlas.alpha_composite(r.tile(code), (i % 32 * 24, i // 32 * 16))
    folder = OUT / 'maps' / f'{m:03d}'; folder.mkdir(parents=True, exist_ok=True)
    atlas.save(folder / 'tiles.png')
    (folder / 'tiles.json').write_text(json.dumps({str(c): i for i, c in enumerate(codes)}))


def export_warps(s, m):
    rows = warps(s, m)
    out = [{'index': i, 'rect': [p.x1, p.y1, p.x2, p.y2], 'map': p.destination_map, 'x': p.destination_x,
            'y': p.destination_y, 'z': p.z, 'flags': p.flags, 'facing': (p.flags >> 14) & 3,
            'arrive_facing': (p.flags >> 12) & 3} for i, o, p in rows]
    (OUT / 'maps' / f'{m:03d}' / 'warps.json').write_text(json.dumps(out))


def map_count(s):
    from map_slots import map_exists
    n = 483
    while n < 2547:
        try:
            if not map_exists(s.data, n): break
        except Exception: break
        n += 1
    return n


def export_all(s, names=None, progress=print, stop=lambda: False):
    """names: {global sprite number: class name}. Returns (done, failed list)."""
    names = names or {}
    OUT.mkdir(parents=True, exist_ok=True)
    total = map_count(s); failed = []
    for cat in range(256):
        if stop(): break
        progress(f'global sprite {cat + 1} of 256...')
        try: export_sprite(s, GLOBAL_SOURCE_MAP, cat, OUT / 'sprites' / 'global' / f'{cat:03d}', names.get(cat))
        except Exception: pass                                    # not every number is a sprite
    map_names = {}
    for m in range(total):
        if stop(): break
        progress(f'Map {m + 1} of {total}...')
        try:
            export_map(s, m, names, force=True)
            export_tiles(s, m)
            export_warps(s, m)
            map_names[m] = json.loads((OUT / 'maps' / f'{m:03d}' / 'map.json').read_text())['name']
        except Exception:
            failed.append((m, traceback.format_exc().splitlines()[-1]))
    sprite_names = {}
    for folder in sorted((OUT / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
        try: sprite_names[int(folder.name)] = json.loads((folder / 'animations.json').read_text()).get('name')
        except (OSError, ValueError): pass
    (OUT / 'names.json').write_text(json.dumps({'maps': map_names, 'sprites': sprite_names}, indent=1), encoding='utf-8')
    (OUT / 'export_failures.txt').write_text('\n'.join(f'map {m}: {e}' for m, e in failed))
    progress(f'Exported {total - len(failed)} maps and the global sprites to {OUT}' + (f' ({len(failed)} failed, see export_failures.txt)' if failed else ''))
    return total - len(failed), failed


def database_names(document):
    """Global sprite number -> class name from the editor's database."""
    out = {}
    for row in (document or {}).get('definitions', []) if isinstance(document, dict) else []:
        src = row.get('source', {})
        cat = src.get('catalogue_index')
        if type(cat) is int and 0 <= cat < 256 and not row.get('clone_of') and row.get('name'):
            out.setdefault(cat, row['name'])
    return out


if __name__ == '__main__':
    s = disc_session(); s.data_frozen = True              # nothing edits the data here
    export_all(s)
