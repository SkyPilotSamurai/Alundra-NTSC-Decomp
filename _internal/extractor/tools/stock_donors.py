"""Game objects keep the original game's behaviour, whatever the project does to
the stock maps (user rule, 2026-10-14).

Every object, NPC, enemy and boss taken from the original game is built from a
copy of it on a stock map (its record, scripts and sprite on that map: the
"donor", e.g. Red Block = map 41 entity 9). Projects blank, erase or rework
stock maps, so the donor is always read from the ORIGINAL game data, never from
the project's edited copy of that map:

* stock maps the project changed and that this build does not place events on
  are swapped back to the original for the build and put back afterwards;
* a changed stock map that the build places events on AND that is a donor map
  is built in a temporary map slot holding the project's version, while the map
  itself holds the original for the donors; the result goes back to the map and
  the slot is removed.

Database references (map, entity) therefore always mean the original game's
map, and keep working when that map is gone from the project. The original
data is the object library (private-inputs/object-library, tools/object_library.py:
every original map block and every game object, taken out of the disc data), or the
session's base (session.original, the disc's DATAS.BIN) when there is no library;
the block fingerprints are cached in private-inputs/editor-cache.
"""
import hashlib, json
from pathlib import Path

from map_slots import offsets, serialize, STOCK_MAPS

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'private-inputs/editor-cache'
# Maps the build reads donors from by number (heal / warp panel 452, floor switch
# 1, pattern plates 29 / 400, Red / Blue Block 41, recovered objects).
DONOR_MAPS = {1, 21, 24, 29, 37, 39, 40, 41, 42, 52, 55, 58, 67, 69, 126, 306, 400, 452}


def _pad(block):
    return bytes(block) + bytes((-len(block)) % 2048)


def stock_fingerprints(stock):
    """sha1 of each original map block (cached per original data)."""
    key = hashlib.sha1(memoryview(stock)[:0x800]).hexdigest()[:12] + f'-{len(stock)}'
    path = CACHE / f'stock-map-fingerprints-{key}.json'
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        pass
    o = offsets(stock)
    prints = [hashlib.sha1(memoryview(stock)[o[m]:o[m + 1]]).hexdigest() for m in range(STOCK_MAPS)]
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prints))
    except OSError:
        pass
    return prints


# The build compiles map by map; it tells prepare() which stock maps differ from
# the original (worked out once per build, plus the stock maps each compiled map
# group changed) instead of hashing all 483 blocks again for every group.
import threading as _threading
_KNOWN = _threading.local()   # per thread: the editor may warm a build while you build


def set_known_changed(maps):
    _KNOWN.value = None if maps is None else set(maps)


def changed_stock_maps(data, stock):
    """Stock maps whose block in data is not the original's."""
    known = getattr(_KNOWN, 'value', None)
    if known is not None:
        return set(known)
    prints = stock_fingerprints(stock)
    o = offsets(data)
    return {m for m in range(STOCK_MAPS)
            if hashlib.sha1(memoryview(data)[o[m]:o[m + 1]]).hexdigest() != prints[m]}


def _library_matches(stock):
    """The object library holds this original data (same map fingerprints)."""
    import object_library
    ix = object_library.index()
    return bool(ix and ix.get('complete') and ix.get('map_fingerprints') == stock_fingerprints(stock))


def stock_block(stock, m):
    """Original map m: from the object library when it holds this original data,
    else from the original data itself."""
    if _library_matches(stock):
        import object_library
        block = object_library.map_block(m)
        if block is not None:
            return block
    o = offsets(stock)
    return bytes(memoryview(stock)[o[m]:o[m + 1]])


def map_block(data, m):
    o = offsets(data)
    return bytes(memoryview(data)[o[m]:o[m + 1]])


def replace_blocks(data, blocks, append=(), owned=False):
    """data with the maps in blocks {map: block} replaced and the blocks in
    append added as new slots at the end, in one pass. owned: the result is a
    fresh OwnedData the event compiler may take over without another copy."""
    o = offsets(data)
    view = memoryview(data)
    if owned:
        from map_block_repack import OwnedData
        out = OwnedData(view[:o[0]])
    else:
        out = bytearray(view[:o[0]])
    values = []
    for m in range(len(o) - 1):
        values.append(len(out))
        out += _pad(blocks[m]) if m in blocks else view[o[m]:o[m + 1]]
    for block in append:
        values.append(len(out))
        out += _pad(block)
    values.append(len(out))
    out = serialize(out, values)
    if owned:
        out.fresh = True
    return out


def drop_last_slots(data, count):
    if count <= 0:
        return data
    o = offsets(data)
    return serialize(bytearray(memoryview(data)[:o[-1 - count]]), o[:-count])


def donor_maps(graphs, definitions):
    """Stock maps the build reads donors from by number."""
    maps = set(DONOR_MAPS)
    for g in graphs:
        m = (g.get('native_placement') or {}).get('donor_map_id')
        if type(m) is int:
            maps.add(m)
    for d in (definitions or {}).values():
        for key, value in (d.get('source') or {}).items():
            if 'donor' in key and isinstance(value, (list, tuple)) and value and type(value[0]) is int:
                maps.add(value[0])
            elif 'donor_map' in key and type(value) is int:
                maps.add(value)
    return {m for m in maps if 0 <= m < STOCK_MAPS}


class Plan:
    def __init__(self):
        self.swapped = {}     # map: the project's block (not built on)
        self.slots = []       # (map, temporary slot) built in a slot


def prepare(session, graphs, definitions):
    """(data, graphs, plan) for the build, or None when every stock map the build
    can read donors from is the original."""
    stock = getattr(session, 'original', None)
    if not stock:
        import object_library
        stock = object_library.original_data() if object_library.available() else None
    try:
        if not stock or len(offsets(stock)) - 1 < STOCK_MAPS or len(offsets(session.data)) - 1 < STOCK_MAPS:
            return None
    except Exception:   # not full game data (tests use tiny stand-ins)
        return None
    data = session.data
    changed = changed_stock_maps(data, stock)
    if not changed:
        return None
    targets = {g.get('map_id') for g in graphs}
    plan = Plan()
    blocks = {}
    for m in sorted(changed - targets):
        plan.swapped[m] = map_block(data, m)
        blocks[m] = stock_block(stock, m)
    slot_maps = sorted(changed & targets & donor_maps(graphs, definitions))
    first = len(offsets(data)) - 1
    append = []
    for i, m in enumerate(slot_maps):
        plan.slots.append((m, first + i))
        append.append(map_block(data, m))
        blocks[m] = stock_block(stock, m)
    if not blocks and not append:
        return None
    new_data = replace_blocks(data, blocks, append, owned=True)   # the compile takes it over (no copy)
    remap = {m: s for m, s in plan.slots}
    if remap:
        graphs = [dict(g, map_id=remap.get(g.get('map_id'), g.get('map_id'))) for g in graphs]
    return new_data, graphs, plan


def finish(data, plan, stock):
    """The built data with the project's maps back in place."""
    blocks = {}
    for m, slot in plan.slots:
        blocks[m] = map_block(data, slot)
    data = drop_last_slots(data, len(plan.slots))
    prints = stock_fingerprints(stock)
    for m, block in plan.swapped.items():
        if hashlib.sha1(map_block(data, m)).hexdigest() != prints[m]:
            raise ValueError(f'The build changed map {m}, which it only reads game objects from')
        blocks[m] = block
    for m, slot in plan.slots:
        if hashlib.sha1(map_block(data, m)).hexdigest() != prints[m]:
            raise ValueError(f'The build changed the original copy of map {m}')
    return replace_blocks(data, blocks) if blocks else data


def stock_view(session):
    """A read-only session over the original game data (for pictures of game
    objects: they never depend on the project's edits of the stock maps)."""
    from stock_source import local_stock
    stock = local_stock() or getattr(session, 'original', None)   # this computer's original game first (2026-10-16)
    if not stock:
        import object_library   # no original data in this session: the library's copy
        stock = object_library.original_data() if object_library.available() else None
    if not stock or getattr(session, '_is_stock_view', False):
        return session
    view = session.__dict__.get('_stock_view')
    if view is not None and (view.data is stock or not getattr(session, 'original', None)):
        return view
    from copy import copy
    view = copy(session)
    view.__dict__.pop('_stock_view', None)
    view.data = stock
    view._pending_textures = {}
    view._pending_palettes = {}
    view._is_stock_view = True
    session._stock_view = view
    return view


def source_for(session, map_id):
    """The session to read map map_id's game objects from: the original game for
    stock maps, the project for its own new maps."""
    if session is None or type(map_id) is not int or not 0 <= map_id < STOCK_MAPS:
        return session
    return stock_view(session)


def _stock_key(stock):
    return hashlib.sha1(memoryview(stock)[:0x800]).hexdigest()[:12] + f'-{len(stock)}'


def behaviour_variants(session, catalogue, cache=None):
    """The class's distinct behaviours in the original game (behavior_transplant),
    read from the original data and kept on disk: they never change."""
    import object_library
    listed = object_library.variants(catalogue) if object_library.available() else None
    if listed is not None:
        return listed
    from behavior_transplant import behaviour_variants as scan
    stock = getattr(session, 'original', None) or session.data
    path = CACHE / f'behaviour-variants-{_stock_key(stock)}.json'
    memo = cache.setdefault('_stock_disk', None) if cache is not None else None
    if memo is None:
        try:
            memo = json.loads(path.read_text())
        except (OSError, ValueError):
            memo = {}
        if cache is not None:
            cache['_stock_disk'] = memo
    if str(catalogue) in memo:
        return memo[str(catalogue)]
    result = scan(stock, catalogue)
    memo[str(catalogue)] = result
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memo))
    except OSError:
        pass
    return result
