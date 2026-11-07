"""Lossless native event view and graphics links, never guessed actor identities."""
from event_editor import reachable_instructions as instructions, script_roots
from map_inspector import inspect_map
from entity_preview import cached_preview

HOOKS = [('A', 'On load'), ('B', 'Map trigger'), ('C', 'On update'),
         ('D', 'On touch'), ('E', 'On deactivate'), ('F', 'On interact')]


def event_hooks(session, map_id, kind, index, info=None):
    info = info or inspect_map(session.data, map_id)
    record = info[kind][index]; offset = int(record['offset'], 16)
    roots = script_roots(session, map_id)
    result = []
    for bank, label in HOOKS if kind == 'entities' else [('B', 'Map trigger')]:
        value = session.data[offset + (10 + ord(bank)-65 if kind == 'entities' else 4)]
        key = f'{bank} {value & 127}'
        result.append({'bank': bank, 'label': label,
                       'key': key if value & 128 and key in roots else None,
                       'raw_hook': value})
    return result


def graphic_entities(session, map_id, kind, index, info=None):
    """Regions have no intrinsic sprite. Link only explicit spawn-template operands."""
    info = info or inspect_map(session.data, map_id)
    if kind == 'entities': return [index], 'Event graphic'
    linked = []
    for hook in event_hooks(session, map_id, kind, index, info):
        if hook['key'] is None: continue
        for offset, opcode, size in instructions(session, map_id, hook['key']):
            if opcode == 0x8A and size == 8:
                template = session.data[offset+1]
                if template < len(info['entities']) and template not in linked:
                    linked.append(template)
    return linked, 'Spawned object preview'


def event_graphic(session, map_id, kind, index, info=None):
    info = info or inspect_map(session.data, map_id)
    candidates, basis = graphic_entities(session, map_id, kind, index, info)
    for entity in candidates:
        offset = int(info['entities'][entity]['offset'], 16)
        # Entity direction bit7 selects the local bank. Clear means shared
        # global graphics, which must not be looked up in a map's sprite table.
        decoder = cached_preview(session, map_id,not bool(session.data[offset+5]&128))
        preview = decoder.representative_frame(session.data[offset+6], session.data[offset+5])
        if preview is None: continue
        image = preview[0].convert('RGBA'); bounds = image.getbbox()
        if bounds:
            return image.crop(bounds), basis, entity
    return None, ('No graphic — map trigger' if kind == 'events' else 'Unknown event graphic'), None
