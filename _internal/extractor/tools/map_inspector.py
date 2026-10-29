"""Read-only map structure inspection for the fingerprinted local DATAS build."""
import hashlib
import struct
from entity_records import read_entities
from map_events import read_map_events
KNOWN_DATAS = "327c5226195991a385250b54f6d7adbd019e45fb0963c62a22268f866ebf25ce"

def verify_datas(data):
    if hashlib.sha256(data).hexdigest() != KNOWN_DATAS:
        raise ValueError("Unknown DATAS.BIN build; map decoding disabled")

def verify_compatible_datas(data):
    """Validate the native fixed-table/container shape without claiming revision.

    This is intended for user's modified US 1.1 data. Passing means the editor's
    current decoders can walk the map blocks; it does not prove US 1.1 identity,
    runtime safety, or that an injected executable understands edited content.
    """
    from map_block_repack import pointers, sections
    from map_loader_constraints import validate_layout
    validate_layout(data)
    table = pointers(data)
    for map_id in range(483):
        block = data[table[map_id]:table[map_id + 1]]
        sections(block)
        inspect_map(data, map_id)
    return dict(format="Alundra DATAS compatible structure", revision_confirmed=False,
                maps_checked=483, gameplay_verified=False)

def inspect_map(data, map_id):
    from map_slots import map_exists, is_new_slot
    if not isinstance(map_id, int) or not map_exists(data, map_id):
        raise ValueError(f"Map {map_id} has not been created yet" if isinstance(map_id, int) and is_new_slot(map_id)
                         else "Map number is out of range")
    from map_slots import map_base
    base = map_base(data, map_id)
    sections = struct.unpack_from("<7I", data, base)
    sprite = base + sections[3]
    header = struct.unpack_from("<12I", data, sprite)
    def bound(start):
        return min([sprite+x for x in header if sprite+x > start] +
                   [base+x for x in sections if base+x > start] + [len(data)])
    entities, _ = read_entities(data, sprite+header[0], bound(sprite+header[0]))
    events, _ = read_map_events(data, sprite+header[2], bound(sprite+header[2]))
    return dict(map=map_id, note="Source-derived fields; raw positions, unknown entity identities. No game edits.",
        entities=[dict(index=i,offset=hex(e.offset),rectangle=e.rectangle,
            position_raw=e.position_raw,programs=e.programs,contents=e.contents)
            for i,e in enumerate(entities)],
        events=[dict(offset=hex(e.offset),rectangle=e.rectangle,program=e.program,
            bank_b_index=e.bank_b_index,unknown=e.unknown.hex()) for e in events])
