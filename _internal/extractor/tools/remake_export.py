"""Export the game's data uncompressed for the Windows remake (remake/).

Reads the original disc's DATAS.BIN (private-inputs/disc/DATA) and writes,
per map: map.json (tile grid, heights, walls, entities, decoded event
scripts with plain descriptions), map.png (the map drawn as in game) and
the sprites the map uses (frame PNGs + animations.json). Global sprites
(Alundra, items...) go to sprites/global. Run:  python tools/remake_export.py [first last]
"""
import json, sys, struct, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets'


def session():
    from editor_session import EditSession
    p = ROOT / 'private-inputs/disc/DATA/DATAS.BIN'
    return EditSession.open_data(p.read_bytes(), p)


def export_sprite(s, map_id, catalogue, folder, name=None):
    """Every animation (4 directions) of one sprite: frames as PNG + JSON."""
    from animation_preview import available_animations, load_animation
    folder.mkdir(parents=True, exist_ok=True)
    meta = {'catalogue': catalogue, 'name': name or f'Sprite {catalogue}', 'animations': []}
    saved = set(); blend = {}
    from animation_preview import animation_reader
    from blend_frames import save_frame, image_sort
    preview = animation_reader(s, map_id, catalogue)[0]
    for r in available_animations(s, map_id, catalogue):
        anim = {'index': r['index'], 'speed': r['native_speed_raw'], 'directions': []}
        for d in range(4):
            try: clip = load_animation(s, map_id, catalogue, r['index'], d, fallback_direction=False)
            except ValueError: anim['directions'].append(None); continue
            frames = []
            for f in clip.frames:
                if f.image is not None and f.image_set_index not in saved:
                    try:
                        extra = save_frame(preview, catalogue & 255, f.image_set_index, folder)   # drawn as in game
                        if extra: blend[str(f.image_set_index)] = extra
                    except Exception:
                        f.image.save(folder / f'{f.image_set_index}.png')
                    saved.add(f.image_set_index)
                try: sort = image_sort(preview, catalogue & 255, f.image_set_index) if f.image is not None else 0
                except Exception: sort = 0                                  # the drawing order's bias (0x800393A4)
                frames.append({'image': f.image_set_index if f.image is not None else None,
                               'left': f.left, 'top': f.top, 'ticks': f.ticks, 'collision': f.collision_raw,
                               'sort': sort})
            anim['directions'].append({'frames': frames, 'end': clip.terminal_kind, 'next': clip.next_animation})
        meta['animations'].append(anim)
    meta['blend'] = blend
    try:
        from anim_tails import tails, apply
        apply(meta, tails(s, map_id, catalogue))      # speed, jump force, acceleration, sound per animation
    except Exception:
        pass
    (folder / 'animations.json').write_text(json.dumps(meta), encoding='utf-8')


def export_map(s, m, names=None, force=False):
    from area_map import grid, MapRenderer
    from native_class_placement import record_cluster
    from event_editor import script_roots, instructions
    from native_event_presentation import present
    folder = OUT / 'maps' / f'{m:03d}'; folder.mkdir(parents=True, exist_ok=True)
    w, h, cells = grid(s, m)
    image, _, margin = MapRenderer(s, m).render(True)
    image.save(folder / 'map.png')
    cluster = record_cluster(s.data, m)
    entities = []
    for i, row in enumerate(cluster['entities']):
        cat = row[6] + (256 if row[5] & 128 else 0)
        entities.append({'index': i, 'catalogue': cat, 'rect': list(row[:4]), 'enabled': row[4], 'flags': row[5],
                         'x': row[7], 'y': row[8], 'z': row[9], 'programs': dict(zip('ABCDEF', row[10:16])),
                         'collection_flag': struct.unpack_from('<H', row, 16)[0], 'contents': struct.unpack_from('<H', row, 18)[0]})
    events = [{'rect': list(e[:4]), 'program': e[4]} for e in cluster['events']]
    scripts = {}
    try:
        for key in script_roots(s, m):
            try:
                rows = instructions(s, m, key)
                lines = {o: i + 1 for i, (o, op, size) in enumerate(rows)}
                out = []
                for o, op, size in rows:
                    p = present(s, m, o, op, size, lines)
                    out.append({'offset': o, 'op': op, 'bytes': bytes(s.data[o:o + size]).hex(),
                                'group': p.get('group'), 'action': p.get('action'), 'settings': str(p.get('settings'))})
                scripts[str(key)] = out
            except Exception as exc:
                scripts[str(key)] = {'error': str(exc)}
    except Exception as exc:
        scripts = {'error': str(exc)}
    try:
        from map_names import map_label; label = map_label(m)
    except Exception: label = f'Map {m}'
    doc = {'map': m, 'name': label, 'width': w, 'height': h, 'margin': margin,
           'cells': [[*c['values'][:4], c['values'][4], [cd for _, cd, _, _ in c['walls']], (c['walls'][0][2] if c['walls'] else 0)] for c in cells],
           'entities': entities, 'events': events, 'scripts': scripts}
    (folder / 'map.json').write_text(json.dumps(doc), encoding='utf-8')
    for cat in sorted({e['catalogue'] for e in entities}):
        target = (OUT / 'sprites' / 'global' / f'{cat:03d}') if cat < 256 else (folder / 'sprites' / f'{cat:03d}')
        if target.exists() and cat < 256 and not force: continue
        nm = (names or {}).get(cat) if cat < 256 else f'Map {m} sprite {cat - 256}'
        try: export_sprite(s, m, cat, target, nm)
        except Exception as exc: (folder / f'sprite_{cat}_error.txt').write_text(str(exc))


def main():
    s = session()
    first, last = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, 482)
    if first == 0 and not (OUT / 'sprites/global/000').exists():
        export_sprite(s, 4, 0, OUT / 'sprites' / 'global' / '000')   # Alundra
    for m in range(first, last + 1):
        try: export_map(s, m); print('map', m, flush=True)
        except Exception: print('map', m, 'FAILED', traceback.format_exc().splitlines()[-1], flush=True)


if __name__ == '__main__':
    main()
