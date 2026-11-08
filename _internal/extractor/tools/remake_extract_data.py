"""Game data (not pictures) the remake's logic needs, read the way the game reads it
(record layouts from the MIT xcasadio AlundraEngine DatasBin/*.cs).

Writes remake/assets:
  maps/NNN/data.json   map info (gravity, Z viscosity, slide effect, balance level...),
                       the 256 map-copy records (doors/bridges for commands 56/85),
                       sprite headers of the map's own sprites, the map's 128 text
                       strings and its music track.
  sprites/global_headers.json  headers of the shared sprites (Alundra, items, effects...)
Sprite header = entity flags (gravity, classes, pickup, shadow, portrait), the built-in
sprite programs (load/tick/touch/deactivate/interact AI), hit box offset/size, break
effect and contents.
Run: python tools/remake_extract_data.py [first last]
"""
import json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from remake_export import OUT, session


def sprite_header(d, o):
    ao, ap, fc, fp = struct.unpack_from('<4i', d, o)
    b = d[o + 16:o + 32]
    flags = b[0] | b[1] << 8 | b[2] << 16
    return {'flags': flags, 'more_flags': b[0], 'can_pickup': b[1], 'portrait_shadow': b[2],
            'sprite_programs': {'A': b[3], 'C': b[4], 'D': b[5], 'E': b[6], 'F': b[7]},
            'hitbox_offset': [struct.unpack_from('b', b, 8 + i)[0] for i in range(3)],
            'hitbox_size': list(b[11:14]), 'break_effect': b[14], 'contents': b[15],
            'animation_sets': (ap - ao) // 14 if ap > ao else 0}


def sprite_info(d, base):
    """Headers of every sprite in one sprite-info block (SpriteInfo.cs)."""
    h = struct.unpack_from('<12i', d, base)
    table_ptr, effects_ptr = h[3], h[4]
    out = {}
    for i in range(max(0, (effects_ptr - table_ptr) // 4)):
        p = struct.unpack_from('<i', d, base + table_ptr + i * 4)[0]
        if p in (0, -1): continue
        try: out[i] = sprite_header(d, base + p)
        except struct.error: pass
    effects = []
    for i in range(255):
        p = struct.unpack_from('<i', d, base + effects_ptr + i * 4)[0]
        if p == 0: break
        effects.append(p)
    map_effects = []
    me_ptr, me_end = h[1], h[2]
    for i in range(max(0, (me_end - me_ptr) // 12)):
        map_effects.append(d[base + me_ptr + i * 12: base + me_ptr + i * 12 + 12].hex())
    return out, len(effects), map_effects


def strings(d, start):
    offs = struct.unpack_from('<128h', d, start)
    out = {}
    for i, o in enumerate(offs):
        if o == -1: continue
        end = d.index(b'\0', start + o)
        out[i] = d[start + o:end].decode('latin-1')
    return out


def map_data(s, m, music=None):
    d = s.data; base, h = s.layout(m)
    info_off, map_off, tiles_off, spr_off, sheet_off, scroll_off, str_off = h
    i = base + info_off
    mid, grav, visc = struct.unpack_from('<Ihh', d, i)
    raw = d[i + 8:i + 16]
    info = {'map_id': mid, 'gravity': grav, 'z_viscosity': visc, 'slide_effect': raw[0], 'anim_delete_wall': raw[1],
            'c': raw[2], 'balance_level': raw[3], 'e': raw[4], 'f': raw[5], 'anim_land_floor': raw[6], 'h11': raw[7],
            'gravity_px_per_frame2': grav * 256 / 65536, 'terminal_px_per_frame': visc * 256 / 65536}
    mb = base + map_off
    w, hh = d[mb], d[mb + 1]
    copies = []
    for k in range(256):
        fx, fy, cw, ch, tx, ty = struct.unpack_from('<bbBBBB', d, mb + 4 + k * 6)
        if cw and ch: copies.append({'index': k, 'from_x': fx, 'from_y': fy, 'width': cw, 'height': ch, 'to_x': tx, 'to_y': ty})
    headers, n_effects, map_effects = sprite_info(d, base + spr_off)
    out = {'map': m, 'info': info, 'size': [w, hh], 'map_copies': copies,
           'sprite_headers': {str(k + 256): v for k, v in headers.items()},
           'sprite_effects': n_effects, 'map_effect_records': map_effects,
           'strings': strings(d, base + str_off) if str_off not in (0, -1) and base + str_off < len(d) else {},
           'music': music}
    return out


def global_data(s):
    d = s.data
    spr = struct.unpack_from('<I', d, 0)[0]
    headers, n_effects, _ = sprite_info(d, spr)
    return {'sprite_headers': {str(k): v for k, v in headers.items()}, 'sprite_effects': n_effects}


def main(a=0, b=482):
    s = session()
    try:
        from music_database import map_music_values
        exe = (ROOT / 'private-inputs/disc/ALUN_CD.EXE').read_bytes(); music = map_music_values(exe)
    except Exception as exc:
        print('music table', exc); music = [None] * 483
    if a == 0:
        g = global_data(s); (OUT / 'sprites').mkdir(parents=True, exist_ok=True)
        (OUT / 'sprites' / 'global_headers.json').write_text(json.dumps(g, indent=0)); print('global sprites', len(g['sprite_headers']))
    for m in range(a, b + 1):
        try:
            doc = map_data(s, m, music[m] if m < len(music) else None)
            folder = OUT / 'maps' / f'{m:03d}'; folder.mkdir(parents=True, exist_ok=True)
            (folder / 'data.json').write_text(json.dumps(doc))
        except Exception as exc:
            print('map', m, 'failed', exc)
    print('done', a, b)


if __name__ == '__main__':
    main(*[int(x) for x in sys.argv[1:3]])
