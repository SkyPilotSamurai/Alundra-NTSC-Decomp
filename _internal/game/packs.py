"""A folder's small pictures read from one file, _pack.bin, instead of one file each (thousands
of tiny files are slow to open the first time after a start of Windows).  The extractor writes
the packs (extract_assets.py picture_packs); a folder without one is read file by file.
_pack.bin: u32 index length, the index (JSON {name: [offset, length]}), then the files."""
import io, json, struct
import pygame

NAME = '_pack.bin'
_packs = {}


def _pack(folder):
    p = _packs.get(folder)
    if p is None:
        p = False
        try:
            data = (folder / NAME).read_bytes()
            n = struct.unpack_from('<I', data, 0)[0]
            base = 4 + n
            p = {k: (base + o, l) for k, (o, l) in json.loads(data[4:base]).items()}, data
        except (OSError, ValueError, struct.error):
            pass
        _packs[folder] = p
    return p


def exists(path):
    p = _pack(path.parent)
    return path.name in p[0] if p else path.exists()


def load(path):
    """pygame.image.load of path (from its folder's pack when there is one), None when missing."""
    p = _pack(path.parent)
    if p:
        at = p[0].get(path.name)
        if at is None: return None
        return pygame.image.load(io.BytesIO(p[1][at[0]:at[0] + at[1]]), path.name)
    return pygame.image.load(str(path)) if path.exists() else None


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
