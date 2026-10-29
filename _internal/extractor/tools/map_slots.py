"""Map numbers beyond the game's own 483.

1. New map slots 483-499 (17 maps)
   The save data's map index table has 500 entries (identity-initialised by
   the new-game loop at 80083DBC), and the DATAS offset table at 0x28 has room
   up to 0x7FC: entries 484..500 hold the offsets of maps 483-499. Their blocks
   are appended after the original file in slot order.

2. Expanded maps 500 and up ("Expand Maps")
   * The index table is only used by doors (portal warps, 800318FC); event
     transfers (opcode 53, 8003F67C) store the map number directly. The build
     patches the door lookup so numbers >= 500 skip the table, so no save-data
     change is needed.
   * DATAS: the word at 0x7FC = extended table offset | number of expanded maps
     (offset 2048-aligned, count < 2048). The extended table holds the offsets
     of maps 501..N (the end of map N last; map 500 starts at entry 500, the end
     of map 499). It sits after the last map block, sector padded. At boot the
     build's hook reads the 0x800 header and then this table right behind
     entry 500 (header buffer + 0x7FC), giving one contiguous offset list.

Every map stays under the largest original map (0x58800 bytes).
"""
import struct

STOCK_MAPS = 483
SLOT_MAPS = 500                 # maps 0..499 live in the header table
MAX_MAPS = SLOT_MAPS + 2047     # 0x7FC word: 11-bit count of expanded maps
EXTRA_SLOTS = SLOT_MAPS - STOCK_MAPS
TABLE = 0x28
ENTRIES = SLOT_MAPS + 1         # header offsets 0..500
EXT_WORD = 0x7FC
MAX_MAP_BYTES = 0x58800


def header(data):
    return list(struct.unpack_from(f'<{ENTRIES}I', data, TABLE))


def extra_count(data):
    """New slots 483-499 in use (contiguous from 483)."""
    t = header(data); k = 0
    while k < EXTRA_SLOTS and t[STOCK_MAPS + k + 1] > t[STOCK_MAPS + k] > 0:
        k += 1
    return k


def ext_info(data):
    """(extended table offset, number of maps from 500 up)."""
    if len(data) < 0x800:
        return 0, 0
    word = struct.unpack_from('<I', data, EXT_WORD)[0]
    if not word or extra_count(data) < EXTRA_SLOTS:
        return 0, 0
    offset, count = word & ~0x7FF, word & 0x7FF
    if not count or offset + 4 * count > len(data):
        return 0, 0
    return offset, count


_OFFSETS_MEMO = {}


def _offsets_key(data):
    """Everything offsets() reads: the data length, the header (0x28..0x800) and
    the extended table it points at."""
    if len(data) < 0x800:
        return None
    head = bytes(memoryview(data)[TABLE:0x800])
    word = struct.unpack_from('<I', head, EXT_WORD - TABLE)[0]
    ext = b''
    if word:
        o, c = word & ~0x7FF, word & 0x7FF
        if c and o + 4 * c <= len(data):
            ext = bytes(memoryview(data)[o:o + 4 * c])
    return (len(data), head, ext)


def offsets(data):
    """Start offsets of every existing map plus the end of the last one
    (remembered per header: the build asks for them tens of thousands of times)."""
    key = _offsets_key(data)
    if key is not None:
        hit = _OFFSETS_MEMO.get(key)
        if hit is not None:
            return list(hit)
    values = _offsets(data)
    if key is not None:
        if len(_OFFSETS_MEMO) > 256:
            _OFFSETS_MEMO.clear()
        _OFFSETS_MEMO[key] = tuple(values)
    return values


def _offsets(data):
    t = header(data); k = extra_count(data)
    values = t[:STOCK_MAPS + k + 1]
    offset, count = ext_info(data)
    if count:
        values += list(struct.unpack_from(f'<{count}I', data, offset))
    return values


def map_count(data):
    return len(offsets(data)) - 1


def is_new_slot(m):
    return STOCK_MAPS <= m < MAX_MAPS


def map_exists(data, m):
    return type(m) is int and 0 <= m < map_count(data)


def block_range(data, m):
    if not map_exists(data, m):
        raise ValueError(f'Map {m} has not been created yet' if type(m) is int and is_new_slot(m) else f'Map must be 0-{MAX_MAPS - 1}')
    values = offsets(data)
    return values[m], values[m + 1]


def map_base(data, m):
    return block_range(data, m)[0]


def table_end(data):
    """Where map data ends (the extended table, if any, follows)."""
    offset, count = ext_info(data)
    return offset if count else len(data)


def ext_table_bytes(values):
    """Sector-padded extended table for an offset list longer than 501 entries."""
    rows = values[SLOT_MAPS + 1:]
    raw = struct.pack(f'<{len(rows)}I', *rows)
    return raw + bytes((-len(raw)) % 2048)


def serialize(data, values):
    """Write an offset list (len = maps + 1) into data: header entries, and for
    maps 500+ the extended table, appended at values[-1] (data is resized)."""
    if isinstance(data, bytearray) and len(data) == values[-1]:
        pass                      # already exact: write in place (no 100 MB copy)
    elif isinstance(data, bytearray) and len(data) > values[-1]:
        del data[values[-1]:]
    else:
        data = bytearray(memoryview(data)[:values[-1]])
    head = values[:ENTRIES] + [0] * (ENTRIES - min(len(values), ENTRIES))
    struct.pack_into(f'<{ENTRIES}I', data, TABLE, *head)
    if len(values) > ENTRIES:
        count = len(values) - ENTRIES
        if count >= 2048:
            raise ValueError('At most 2047 expanded maps')
        if values[-1] % 2048:
            raise ValueError('Map data end must be 2048-aligned')
        struct.pack_into('<I', data, EXT_WORD, values[-1] | count)
        data += ext_table_bytes(values)
    else:
        struct.pack_into('<I', data, EXT_WORD, 0)
    return data


def new_slot_label(m):
    return f'New Map {m - STOCK_MAPS + 1}'
