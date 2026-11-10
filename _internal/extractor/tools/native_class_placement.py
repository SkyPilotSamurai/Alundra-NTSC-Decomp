"""Native same-map donor placement, without moving opaque sprite asset pointers.

Source record layout: xcasadio 242b09a20ae1186c90278ba5f15f0f9a84104ef4,
AlundraTools/AlundraEngine/DatasBin/{SiEntityRecord,SpriteInfoHeader}.cs.
This is structural compilation, not emulator certification. Donor scripts may
reference other entities/flags; a duplicated chest retains its collection bit.
"""
import hashlib
import struct
from entity_records import read_entities
from map_events import read_map_events
from map_block_repack import pointers, sections, replace_section
from map_loader_constraints import validate_layout


def record_cluster(data, map_id):
    """Return preserved native lists and their exact bounded byte payloads."""
    if type(map_id) is not int or not 0 <= map_id < 2547:
        raise ValueError('Map outside native table')
    table = pointers(data)
    base = table[map_id]
    h = sections(data[base:table[map_id+1]])
    sp, end = base+h[3], base+h[4]
    sh = struct.unpack_from('<12I', data, sp)
    if any(p < 48 or sp+p > end for p in sh):
        raise ValueError('Sprite-info pointer outside section')
    if not sh[0] < sh[1] <= sh[2]:
        raise ValueError('Unsupported entity/effect/event list order')
    entities, consumed = read_entities(data, sp+sh[0], sp+sh[1])
    if consumed > sp+sh[1] or data[consumed-2:consumed] != bytes(2):
        raise ValueError('Explicit entity terminator required')
    bound = min([sp+p for p in sh if p > sh[2]] + [end])
    events, event_end = read_map_events(data, sp+sh[2], bound)
    if data[event_end-4:event_end] != bytes(4):
        raise ValueError('Explicit map-event terminator required')
    return dict(map_id=map_id, sprite_start=sp, sprite_end=end,
                header=sh, entities=[e.raw for e in entities],
                entity_terminator=bytes(data[consumed-4:consumed]),
                effects=bytes(data[sp+sh[1]:sp+sh[2]]),
                events=[e.encode() for e in events])


def donor_record(data, map_id, entity_index, x, y, height=None, *,
                 programs=None, contents=None):
    """Copy all 20 bytes, changing only explicit native fields.

    x/y and optional height are tile units, multiplied by two by the native
    record. Keep activation rectangle, direction/high sprite bank and unknown
    fields. An explicit callbacks dictionary can replace A..F independently.
    """
    cluster = record_cluster(data, map_id)
    if type(entity_index) is not int or not 0 <= entity_index < len(cluster['entities']):
        raise ValueError('Donor entity outside map')
    def doubled(value, name):
        if type(value) is not int or not 0 <= value <= 127:
            raise ValueError(name+' must be an integer tile coordinate0..127')
        return value*2
    row = bytearray(cluster['entities'][entity_index])
    row[7:9] = bytes((doubled(x,'X'), doubled(y,'Y')))
    if height is not None:
        row[9] = doubled(height,'Height')
    if programs is not None:
        if not isinstance(programs, dict) or any(k not in 'ABCDEF' or len(k)!=1 for k in programs):
            raise ValueError('Callbacks must use banks A..F')
        for key, value in programs.items():
            if type(value) is not int or not 0 <= value <= 255:
                raise ValueError('Callback index outside byte range')
            row[10+'ABCDEF'.index(key)] = value
    if contents is not None:
        if type(contents) is not int or not 0 <= contents <= 65535:
            raise ValueError('Contents outside native halfword')
        struct.pack_into('<H',row,18,contents)
    return bytes(row)


def class_donors(data, map_id, catalogue_index):
    """Find concrete same-map instances for a bank-specific database class.

    A low sprite ID alone is not identity: entity direction bit7 selects the
    second native catalogue bank. Results identify real donor records, allowing
    the UI to offer only placements with their native behavior/assets present.
    """
    if type(catalogue_index) is not int or not 0 <= catalogue_index < 512:
        raise ValueError('Catalogue index outside two native banks')
    cluster=record_cluster(data,map_id)
    return [dict(entity_index=i,programs=dict(zip('ABCDEF',row[10:16])),
                 contents=struct.unpack_from('<H',row,18)[0],
                 position_raw=list(row[7:10]),record_hex=row.hex())
            for i,row in enumerate(cluster['entities'])
            if row[6]+(256 if row[5]&128 else 0)==catalogue_index]


def global_sprite_available(data, sprite_id):
    """Check the dedicated global DATAS sprite bank, never a local fallback.

    Source-reported selector: GameEngine.cs720-784 at the pinned commit above.
    Direction bit7 clear uses the DATAS roots at file words0/4 on every map.
    """
    if type(sprite_id) is not int or not 0 <= sprite_id <256:
        return False
    start,end=struct.unpack_from('<2I',data,0)
    if not 0x800 <= start <= start+48 <= end <= len(data):
        raise ValueError('Unsupported global sprite bank bounds')
    header=struct.unpack_from('<12I',data,start)
    table,stop=header[3:5]
    if not 48 <= table <= stop <= end-start or (stop-table)%4:
        raise ValueError('Invalid global sprite table bounds')
    if sprite_id >= (stop-table)//4:return False
    pointer=struct.unpack_from('<i',data,start+table+4*sprite_id)[0]
    if pointer in (0,-1):return False
    if not 48 <= pointer <= end-start-32:
        raise ValueError('Global sprite target outside bank')
    return True


def class_preview(session,map_id,catalogue_index,direction=0):
    """Decode a class from its correct global/map-local texture bank.

    This uses the existing static first-frame decoder, not invented/fetched art.
    None means its animation/frame format is not supported by that decoder.
    """
    if type(catalogue_index) is not int or not 0<=catalogue_index<512:
        raise ValueError('Catalogue index outside two native banks')
    from entity_preview import EntityPreview,cached_preview
    from types import SimpleNamespace
    if catalogue_index<256:
        if not global_sprite_available(session.data,catalogue_index):return None
        start,sheet=struct.unpack_from('<2I',session.data)
        end=struct.unpack_from('<I',session.data,0x14)[0]
        if not sheet<end<=len(session.data):raise ValueError('Global texture bank bounds invalid')
        view=SimpleNamespace(data=session.data,
            layout=lambda ignored:(0,(0,0,0,start,sheet,end,0)))
        return cached_preview(session,0,True).representative_frame(catalogue_index,direction)
    return cached_preview(session,map_id).representative_frame(catalogue_index&255,direction)


def donor_record_for_map(data,target_map,donor_map,entity_index,x,y,height=None,*,
                         programs=None,contents=None):
    """Place a global donor on another map with independent authored hooks.

    Same-map donors retain their exact original semantics. A foreign-map donor
    is accepted ONLY from the global bank (catalogue0..255), with a proved
    positive global sprite pointer. Foreign local A-F callbacks and collection
    flag word16 are cleared, activation is target-wide and record enabled.
    Global sprite header built-in callbacks still execute normally. No NPC
    dialogue/event process is silently copied across maps.
    """
    row=bytearray(donor_record(data,donor_map,entity_index,x,y,height,
                              contents=contents))
    if target_map!=donor_map:
        if row[5]&128:
            raise ValueError('Foreign map-local sprite requires asset import; choose a global donor')
        if not global_sprite_available(data,row[6]):
            raise ValueError('Donor global sprite asset is unavailable')
        pp=pointers(data)
        if type(target_map) is not int or not 0<=target_map<2547:
            raise ValueError('Target map outside native table')
        h=sections(data[pp[target_map]:pp[target_map+1]])
        width,tall=data[pp[target_map]+h[1]:pp[target_map]+h[1]+2]
        if not width or not tall or not 0<=x<width or not 0<=y<tall:
            raise ValueError('Placement outside target tile grid')
        row[:4]=bytes((0,0,width-1,tall-1));row[4]=1
        row[5]=(row[5]&3)|0x40
        row[10:18]=bytes(8)
    if programs is not None:
        if not isinstance(programs,dict) or any(k not in 'ABCDEF' or len(k)!=1 for k in programs):
            raise ValueError('Callbacks must use banks A..F')
        for key,value in programs.items():
            if type(value) is not int or not 0<=value<=255:
                raise ValueError('Callback index outside byte range')
            row[10+'ABCDEF'.index(key)]=value
    return bytes(row)


def resolve_class_donor(data,target_map,catalogue_index):
    """Prefer a real target-map donor; otherwise find a global-bank donor.

    The descriptor can be stored as native_placement.donor_map_id plus
    donor_entity_index. Foreign local assets are deliberately not resolved.
    """
    same=class_donors(data,target_map,catalogue_index)
    if same:
        return dict(donor_map_id=target_map,donor_entity_index=same[0]['entity_index'],
                    catalogue_index=catalogue_index,global_asset=catalogue_index<256,
                    foreign_local_hooks_cleared=False)
    if catalogue_index>=256 or not global_sprite_available(data,catalogue_index):return None
    for map_id in range(483):
        if map_id==target_map:continue
        donors=class_donors(data,map_id,catalogue_index)
        if donors:
            preferred=min(donors,key=lambda row:sum(bool(v) for v in row['programs'].values()))
            return dict(donor_map_id=map_id,donor_entity_index=preferred['entity_index'],
                        catalogue_index=catalogue_index,global_asset=True,
                        foreign_local_hooks_cleared=True,source_collection_flag_cleared=True)
    return None


def trigger_record(rectangle, program):
    """Create a no-graphic native bank-B region trigger; caller allocates code."""
    if len(rectangle)!=4 or any(type(v) is not int or not 0 <= v <=255 for v in rectangle):
        raise ValueError('Trigger rectangle requires four native byte coordinates')
    x1,y1,x2,y2=rectangle
    if x1>x2 or y1>y2 or not any(rectangle):
        raise ValueError('Empty/reversed native trigger rectangle')
    if type(program) is not int or not 0 < program < 128:
        raise ValueError('A nonzero allocated local bank-B index1..127 is required')
    return bytes((*rectangle,program,0,0,0))


def append_record_cluster(data, map_id, *, entities=None, map_events=None, effects=None):
    """Append complete replacement native lists; preserve original assets/code.

    No original pointer target is moved. The only rewritten sprite-info words
    are its three list roots. The outer native section/map table is rebuilt at
    four-byte/2048-byte alignment. Original donor identity semantics survive.
    """
    old = record_cluster(data,map_id)
    from map_block_repack import pointers as _ptr
    _o = _ptr(data); base_block_sha = hashlib.sha256(memoryview(data)[_o[map_id]:_o[map_id+1]]).hexdigest()
    erows = old['entities'] if entities is None else list(entities)
    mrows = old['events'] if map_events is None else list(map_events)
    # Preserve room for a terminator; native readers have hard iteration caps.
    if len(erows)>=128 or len(mrows)>=64:
        raise ValueError('Native entity/map-event capacity exhausted')
    if any(len(r)!=20 or bytes(r)[2:4]==bytes(2) for r in erows):
        raise ValueError('Invalid entity record or premature terminator')
    if any(len(r)!=8 or bytes(r)[:4]==bytes(4) for r in mrows):
        raise ValueError('Invalid map-event record or premature terminator')
    sp,end = old['sprite_start'],old['sprite_end']
    section=bytearray(data[sp:end]);section.extend(bytes((-len(section))%4))
    sh=list(old['header']);sh[0]=len(section)
    section.extend(b''.join(bytes(r) for r in erows)+old['entity_terminator'])
    effect_bytes=old['effects'] if effects is None else bytes(effects)
    if effects is not None and (len(effect_bytes)<4 or (len(effect_bytes)-4)%12 or effect_bytes[-4:]!=bytes(4)):
        raise ValueError('Invalid map effect table')
    sh[1]=len(section);section.extend(effect_bytes)
    sh[2]=len(section);section.extend(b''.join(bytes(r) for r in mrows)+bytes(4))
    section.extend(bytes((-len(section))%4))
    struct.pack_into('<12I',section,0,*sh)
    result=replace_section(data,map_id,3,section)
    validate_layout(result)
    check=record_cluster(result,map_id)
    if check['entities']!=[bytes(r) for r in erows] or check['events']!=[bytes(r) for r in mrows] or check['effects']!=effect_bytes:
        raise ValueError('Native placement roundtrip failed')
    return result,dict(map_id=map_id,entity_count=len(erows),event_count=len(mrows),
        previous_entity_count=len(old['entities']),previous_event_count=len(old['events']),
        base_sha256=base_block_sha,result_sha256=hashlib.sha256(memoryview(result)[_ptr(result)[map_id]:_ptr(result)[map_id+1]]).hexdigest(),   # of this map's block (the whole data took 10 s per build)
        original_sprite_payload_preserved=True,gameplay_verified=False,
        limitations=['Donor callbacks/collection flags retain their original semantics',
                    'Cross-map sprite assets are not imported by this API',
                    'Structural checks do not certify emulator/hardware behavior'])


def duplicate_entity(data,map_id,entity_index,x,y,height=None,**fields):
    cluster=record_cluster(data,map_id)
    row=donor_record(data,map_id,entity_index,x,y,height,**fields)
    result,metadata=append_record_cluster(data,map_id,entities=cluster['entities']+[row])
    metadata.update(entity_index=len(cluster['entities']),donor_entity_index=entity_index)
    return result,metadata


def add_map_trigger(data,map_id,rectangle,program):
    cluster=record_cluster(data,map_id)
    return append_record_cluster(data,map_id,
        map_events=cluster['events']+[trigger_record(rectangle,program)])
