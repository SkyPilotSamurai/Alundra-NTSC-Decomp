"""A folder's small pictures read from one file, _pack.bin, instead of one file each (thousands
of tiny files are slow to open the first time after a start of Windows).  The extractor writes
the packs (extract_assets.py picture_packs); a folder without one is read file by file.
_pack.bin: u32 index length, the index (JSON {name: [offset, length]}), then the files."""
import io, json, os, struct
import pygame

NAME = '_pack.bin'
MAP = '_map.bin'          # a map folder's files, every depth (sprite / effect packs included), in one file
_packs = {}
_maps = {}                # the last few map packs read


def _index(data):
    n = struct.unpack_from('<I', data, 0)[0]
    base = 4 + n
    return {k: (base + o, l) for k, (o, l) in json.loads(data[4:base]).items()}, data


def _map_of(path):
    for d in path.parents:
        if d.parent.name == 'maps' and d.name.isdigit(): return d
    return None


def _mappack(folder):
    p = _maps.get(folder)
    if p is None:
        p = False
        try:
            # a pack older than a file beside it (a map edited after it was packed) is not used
            ents = {e.name: e.stat().st_mtime for e in os.scandir(folder) if e.is_file()}
            if MAP in ents and ents[MAP] >= max(t for n, t in ents.items() if n != MAP):
                p = _index((folder / MAP).read_bytes())
        except (OSError, ValueError, struct.error): pass
        if len(_maps) >= 4: _maps.pop(next(iter(_maps)))
        _maps[folder] = p
    return p


def read(path):
    """path's bytes (from its map's pack when there is one), None when missing."""
    m = _map_of(path)
    p = _mappack(m) if m is not None else False
    if p:
        at = p[0].get(path.relative_to(m).as_posix())
        return None if at is None else p[1][at[0]:at[0] + at[1]]
    try: return path.read_bytes()
    except OSError: return None


def has(path):
    m = _map_of(path)
    p = _mappack(m) if m is not None else False
    return path.relative_to(m).as_posix() in p[0] if p else path.exists()


def read_json(path, default=None):
    b = read(path)
    return default if b is None else json.loads(b)


def _pack(folder):
    p = _packs.get(folder)
    if p is None:
        p = False
        try: p = _index(read(folder / NAME))
        except (TypeError, ValueError, struct.error): pass
        _packs[folder] = p
    return p


def exists(path):
    p = _pack(path.parent)
    return path.name in p[0] if p else has(path)


def load(path):
    """pygame.image.load of path (from its folder's pack when there is one), None when missing."""
    p = _pack(path.parent)
    if p:
        at = p[0].get(path.name)
        if at is None: return None
        return pygame.image.load(io.BytesIO(p[1][at[0]:at[0] + at[1]]), path.name)
    b = read(path)
    return None if b is None else pygame.image.load(io.BytesIO(b), path.name)


def make(folder):
    """Writes folder's pack from its .png files (True when it wrote one)."""
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() == '.png' and f.is_file())
    if not files: return False
    index, blobs, at = {}, [], 0
    for f in files:
        b = f.read_bytes(); index[f.name] = [at, len(b)]; blobs.append(b); at += len(b)
    head = json.dumps(index, separators=(',', ':')).encode()
    tmp = folder / (NAME + '.tmp')
    tmp.write_bytes(struct.pack('<I', len(head)) + head + b''.join(blobs))
    tmp.replace(folder / NAME)
    return True


def make_map(folder):
    """Writes the map folder's _map.bin from its files (the pictures of a folder with a pack: its pack)."""
    index, blobs, at = {}, [], 0
    for f in sorted(folder.rglob('*')):
        if not f.is_file() or f.name in (MAP, MAP + '.tmp'): continue
        if f.suffix.lower() == '.png' and f.parent != folder and (f.parent / NAME).exists(): continue
        b = f.read_bytes(); index[f.relative_to(folder).as_posix()] = [at, len(b)]; blobs.append(b); at += len(b)
    head = json.dumps(index, separators=(',', ':')).encode()
    tmp = folder / (MAP + '.tmp')
    tmp.write_bytes(struct.pack('<I', len(head)) + head + b''.join(blobs))
    tmp.replace(folder / MAP)
    _maps.pop(folder, None)


def make_maps(assets):
    n = 0
    for d in sorted((assets / 'maps').iterdir()) if (assets / 'maps').is_dir() else ():
        if d.is_dir() and d.name.isdigit(): make_map(d); n += 1
    return n


def make_all(assets):
    """Packs for every sprite and effect folder under assets (sprites/, effects/, the maps')."""
    n = 0
    for top in ('sprites', 'sprites_prev', 'effects', 'maps'):
        root = assets / top
        if not root.is_dir(): continue
        for d in root.rglob('*'):
            rel = d.relative_to(assets).parts
            if top == 'maps' and 'sprites' not in rel and 'effects' not in rel: continue
            if d.is_dir() and make(d): n += 1
    return n
