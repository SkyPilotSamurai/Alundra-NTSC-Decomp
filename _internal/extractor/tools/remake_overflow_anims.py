"""Animation sets past a sprite's own count ('overflow').  The game indexes the set table
with no bound (UpdateAnimation 0x800393A4): a script's `1A n` with n >= the count reads
the 14 bytes after the table (the first animation streams) as a set record.  Map 38's
C program 136 plays animation 9 of sprite 319 (9 sets): z force 15, frames from whatever
the record's stream offsets point at.  This adds those sets (indices count..count+7, as
far as they decode) to animations.json so the remake does what the game does.
python tools/remake_overflow_anims.py [global | first last]"""
import json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'remake' / 'assets'
EXTRA = 8


def overflow_sets(s, map_id, catalogue):
    from animation_preview import animation_reader
    from entity_animation import _read_stream, AnimationSet, _bounded_read
    preview, sets = animation_reader(s, map_id, catalogue)
    if not sets: return []
    first = sets[0]
    data = s.data; start = preview.start; end = preview.end
    sets_abs = first.offset if hasattr(first, 'offset') else None
    # the set table starts at the first set's record address; the streams base is the
    # record header's animations_offset: both are recoverable from the sprite record
    table = start + preview.header[3]
    rel = struct.unpack_from('<i', data, table + (catalogue & 255) * 4)[0]
    rec = start + rel
    sets_offset, animations_offset = struct.unpack_from('<2I', data, rec)
    out = []
    for index in range(len(sets), len(sets) + EXTRA):
        local = start + sets_offset + index * 14
        try:
            raw = _bounded_read(data, local, 14, start, end)
        except Exception:
            break
        directions = struct.unpack_from('<4h', raw, 0)
        speed = struct.unpack_from('<H', raw, 8)[0]
        tail = raw[10:14]
        streams = []
        for slot in range(4):
            try: streams.append(_read_stream(data, start + animations_offset, end, directions[slot], slot))
            except Exception: streams.append(None)
        if all(st is None for st in streams): break
        out.append(AnimationSet(index, local, speed, tuple(directions), tail, tuple(streams)))
    return out


def export_overflow(s, map_id, catalogue, folder):
    from animation_preview import animation_reader, terminal_meaning, PreviewFrame
    from blend_frames import save_frame, image_sort
    f = folder / 'animations.json'
    if not f.exists(): return 0
    meta = json.loads(f.read_text())
    meta['animations'] = [a for a in meta['animations'] if not a.get('overflow')]
    preview = animation_reader(s, map_id, catalogue)[0]
    saved = {int(p.stem) for p in folder.glob('[0-9]*.png') if p.stem.isdigit()}
    blend = meta.setdefault('blend', {})
    n = 0
    for st in overflow_sets(s, map_id, catalogue):
        anim = {'index': st.index, 'speed': st.speed_raw if hasattr(st, 'speed_raw') else st.speed, 'directions': [], 'overflow': True}
        unknown, flags, sfx, accel = st.tail
        z = (flags << 8) | unknown
        if z & 0x8000: z -= 0x10000
        anim.update({'z_force': z, 'set_flags': flags, 'sfx': sfx + (0x100 if flags & 0x20 else 0), 'accel': accel & 15, 'anim_flags': accel})
        for slot in range(4):
            stream = st.streams[slot]
            if stream is None: anim['directions'].append(None); continue
            frames = []
            for fr in stream.frames:
                key = fr.image_set_index
                img = None
                try:
                    img, left, top = preview.image_set(catalogue & 255, key)
                except Exception:
                    left = top = 0
                if img is not None and key not in saved:
                    try:
                        extra = save_frame(preview, catalogue & 255, key, folder)
                        if extra: blend[str(key)] = extra
                    except Exception:
                        img.save(folder / f'{key}.png')
                    saved.add(key)
                try: sort = image_sort(preview, catalogue & 255, key) if img is not None else 0
                except Exception: sort = 0
                frames.append({'image': key if img is not None else None, 'left': left, 'top': top,
                               'ticks': max(1, fr.delay_raw & 127), 'collision': fr.collision_raw, 'sort': sort})
            kind, nxt = terminal_meaning(stream.terminator)
            anim['directions'].append({'frames': frames, 'end': kind, 'next': nxt})
        meta['animations'].append(anim); n += 1
    if n:
        f.write_text(json.dumps(meta), encoding='utf-8')
    return n


def main():
    from remake_export import session
    s = session()
    if sys.argv[1:2] == ['global']:
        t = 0
        for folder in sorted((OUT / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
            try: t += export_overflow(s, 4, int(folder.name), folder)
            except Exception as e: print('global', folder.name, e)
        print('global overflow sets', t); return
    for m in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
        base = OUT / 'maps' / f'{m:03d}' / 'sprites'
        t = 0
        for folder in sorted(base.glob('[0-9][0-9][0-9]')) if base.exists() else []:
            try: t += export_overflow(s, m, int(folder.name), folder)
            except Exception as e: print('map', m, folder.name, e)
        print('map', m, t, flush=True)


if __name__ == '__main__':
    main()
