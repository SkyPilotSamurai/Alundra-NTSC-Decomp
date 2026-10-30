"""Append a rebuilt script/record cluster without rebasing opaque sprite assets.

Source-derived DATAS layout, not a generic revision claim. Existing code and
asset payload bytes are preserved; only native header and table roots change.
"""
import struct, hashlib
from entity_records import read_entities
from map_events import read_map_events
from map_block_repack import pointers, sections, replace_section
from map_loader_constraints import validate_layout


def script_tables(section):
    if len(section) < 48:
        raise ValueError("Truncated native sprite-info header")
    header = list(struct.unpack_from("<12I", section))
    a, f, end = header[6], header[11], header[0]
    if not 48 <= a <= f <= end <= len(section) or any(p % 2 for p in header[6:]):
        raise ValueError("Unsupported native script table bounds")
    if any(x > y for x, y in zip(header[6:], header[7:])):
        raise ValueError("Script banks must be ordered A through F")
    candidates = [struct.unpack_from("<h", section, pos)[0] for pos in range(a, f, 2)]
    candidates = [value for value in candidates if f - a <= value < end - a and value > 0]
    # F can own the earliest code even when A-E point at later appended code.
    # Stop at the earliest proven root, tightening that boundary while reading
    # actual F table entries; never interpret the code itself as more roots.
    boundary = a + min(candidates) if candidates else end
    pos = f
    while pos + 2 <= min(boundary, end, f + 256):
        value = struct.unpack_from("<h", section, pos)[0]
        if value > 0 and pos + 2 <= a + value < end:
            candidates.append(value)
            boundary = min(boundary, a + value)
        pos += 2
    if not candidates and not any(section[a:end]):
        code_start = end  # Every native bank is inactive; no code payload.
    elif candidates:
        code_start = a + min(candidates)
    else:
        raise ValueError("Cannot prove the native F table/code boundary")
    if code_start % 2 or code_start < f:
        raise ValueError("Unaligned script table/code boundary")
    stops = header[7:] + [code_start]
    tables = []
    for start, stop in zip(header[6:], stops):
        if not start <= stop <= code_start or (stop - start) % 2:
            raise ValueError("Unsupported script bank size/alignment")
        table = list(struct.unpack_from("<" + "h" * ((stop - start) // 2), section, start))
        if any(value > 0 and not code_start <= a + value < end for value in table):
            raise ValueError("Script root is outside existing code storage")
        tables.append(table)
    return header, tables, bytes(section[code_start:end]), code_start


def append_native_process(datas, map_id, bank, code):
    """Return (rebuilt DATAS, report); no source/session mutation.

    The reported root index can be installed in an entity's A-F hook or a B
    map-event record by native_class_placement. Neither unused padding nor a
    disabled entity is treated as automatically safe/free storage.
    """
    if type(map_id) is not int or not 0 <= map_id < 2547:
        raise ValueError("Map outside native table")
    if not isinstance(bank, str) or bank not in "ABCDEF" or len(bank) != 1:
        raise ValueError("Native process bank must be A through F")
    code = bytes(code)
    if not code or code[-1] != 255:
        raise ValueError("Authored native process must end with FF End process")
    table = pointers(datas)
    block = datas[table[map_id]:table[map_id + 1]]
    boundaries = sections(block)
    original = bytes(block[boundaries[3]:boundaries[4]])
    header, tables, old_code, code_start = script_tables(original)
    if any(value < 0 for values in tables for value in values):
        raise ValueError("Negative native roots use unresolved semantics; this map cannot be safely relocated")
    if not header[0] <= header[1] <= header[2] <= len(original):
        raise ValueError("Native entity/effect/map-event tables must be ordered")
    entities, entity_end = read_entities(original, header[0], header[1])
    events, event_end = read_map_events(original, header[2], len(original))
    entity_bytes = original[header[0]:entity_end]
    effect_bytes = original[header[1]:header[2]]
    event_bytes = original[header[2]:event_end]
    if any(len(raw) % 4 for raw in (entity_bytes, effect_bytes, event_bytes)):
        raise ValueError("Native record cluster is not four-byte aligned")
    index = ord(bank) - ord("A")
    target = tables[index]
    old_length = sum(len(values) * 2 for values in tables)
    if not target:
        target.append(0)  # Hook zero is reserved/inactive.
    root_index = len(target)
    if not 1 <= root_index <= 127:
        raise ValueError("Selected native bank has no remaining hook indices")
    target.append(0)
    new_length = sum(len(values) * 2 for values in tables)
    growth = new_length - old_length
    for values in tables:
        for i, value in enumerate(values):
            if value > 0:
                values[i] = value + growth
                if values[i] > 32767:
                    raise ValueError("Native signed root displacement overflow")
    target[root_index] = new_length + len(old_code)
    if target[root_index] > 32767:
        raise ValueError("New native process exceeds signed root displacement")
    # Keep the palette table immediately adjacent to script bank A. Importers
    # and recolouring use these explicit header bounds, never sentinel scans:
    # real palettes may start with four zero bytes. Repointing A alone made a
    # second sprite import interpret stale assets/code as palette entries.
    palette_bytes = original[header[5]:header[6]]
    palette_count, palette_remainder = divmod(len(palette_bytes), 32)
    if palette_count > 41 or palette_remainder != 4 or palette_bytes[-4:] != bytes(4):
        raise ValueError("Palette/script adjacency is unsupported; preserve original palette bounds")
    # A previous allocation left the palette + script cluster + records as the
    # section's last bytes. Rebuild that tail in place instead of appending a
    # second copy: every append used to keep the old copy as dead bytes, so a
    # map grew by its whole script cluster per allocation (22 signs overflowed
    # a new map, 2026-10-15). Only when nothing else lives in that tail.
    base = original
    sprite_roots = [struct.unpack_from('<i', original, pos)[0] for pos in range(header[3], header[4] - 3, 4)] if header[3] <= header[4] <= len(original) else [len(original)]
    if (header[5] < header[6] and entity_end == header[1] and event_end == len(original)
            and code_start <= header[0] and max(header[3], header[4]) <= header[5]
            and all(r in (0, -1) or 0 <= r < header[5] for r in sprite_roots)):
        base = original[:header[5]]
    palette_start = len(base)
    cluster_start = palette_start + len(palette_bytes)
    header[5] = palette_start
    cluster = bytearray()
    for i, values in enumerate(tables):
        header[6 + i] = cluster_start + len(cluster)
        cluster.extend(struct.pack("<" + "h" * len(values), *values))
    cluster.extend(old_code)
    cluster.extend(code)
    cluster.extend(b"\xff" * (-len(cluster) % 4))
    header[0] = cluster_start + len(cluster)
    cluster.extend(entity_bytes)
    header[1] = cluster_start + len(cluster)
    cluster.extend(effect_bytes)
    header[2] = cluster_start + len(cluster)
    cluster.extend(event_bytes)
    rebuilt = bytearray(base) + palette_bytes + cluster
    struct.pack_into("<12I", rebuilt, 0, *header)
    result = replace_section(datas, map_id, 3, rebuilt)
    validate_layout(result)
    # Verify table semantics and every original code byte in its new location.
    _, check_tables, check_code, _ = script_tables(rebuilt)
    if check_code[:len(old_code)] != old_code or check_tables[index][root_index] != target[root_index]:
        raise ValueError("Native cluster round-trip verification failed")
    return result, {"map_id": map_id, "bank": bank, "root_index": root_index,
                    "hook_value": 0x80 | root_index, "code_bytes": len(code),
                    "code_sha256": hashlib.sha256(code).hexdigest(),
                    "preserved_code_bytes": len(old_code), "existing_entities": len(entities),
                    "existing_map_events": len(events), "sprite_info_growth": len(palette_bytes) + len(cluster),
                    "palette_bytes_preserved": len(palette_bytes),
                    "gameplay_verified": False}
