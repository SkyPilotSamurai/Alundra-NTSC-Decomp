"""Item grouping and bounded native inventory-selection metadata edits."""
import struct,json
from copy import deepcopy
from pathlib import Path
from alundra_memory import parse_exe,runtime_to_offset

CATEGORIES=('Consume','Accessory','Key item')
CONSUMED_IDS={36,37,38,39,41}
ACCESSORY_IDS={31,32,33,35,40,*range(43,57),59}
TABLE=0x800BBE50
ROOT=Path(__file__).resolve().parents[1]


def item_id(row):
    value=row.get('source',{}).get('item_id')
    if value is None:
        index=row.get('source',{}).get('catalogue_index',row.get('source',{}).get('balance_entry'))
        if type(index) is int and 30<=index<128:value=index-30
    if type(value) is not int or not 0<=value<98:raise ValueError('Item has no bounded native item identity')
    return value


def category_for(row):
    saved=row.get('data',{}).get('item_category')
    if saved in CATEGORIES:return saved
    try:identity=item_id(row)
    except ValueError:return 'Key item'
    return 'Consume' if identity in CONSUMED_IDS else 'Accessory' if identity in ACCESSORY_IDS else 'Key item'


def native_properties(exe,identity):
    if type(identity) is not int or not 0<=identity<98:raise ValueError('Native item identity must be0..97')
    header=parse_exe(exe);off=runtime_to_offset(header,TABLE+identity*10)
    if off+10>0x800+header['load_size']:raise ValueError('Item metadata lies outside executable payload')
    group,flags,priority,maximum,icon=struct.unpack_from('<hHhhH',exe,off)
    return dict(item_id=identity,menu_group=group,highest_priority=bool(flags&1),
        priority=priority,max_quantity=maximum,icon_id=icon,flags_raw=flags,
        virtual_address=TABLE+identity*10,raw=exe[off:off+10].hex())


def apply(row,category,*,menu_group=None,highest_priority=None,priority=None,max_quantity=None,exe=None):
    if category not in CATEGORIES:raise ValueError('Choose Consume, Accessory or Key item')
    result=deepcopy(row);data=result.setdefault('data',{})
    if 'item_category' in data or category!=category_for(row):
        data['item_category']=category
        data['item_category_basis']='Editor grouping; not an automatic use-handler/passive-effect conversion'
    # else: still the automatic category -- just looking at an item changes nothing
    fields={key:value for key,value in dict(menu_group=menu_group,highest_priority=highest_priority,
        priority=priority,max_quantity=max_quantity).items() if value is not None}
    if fields:
        if 'menu_group' in fields and (type(menu_group) is not int or not 0<=menu_group<32):raise ValueError('Menu group must be0..31')
        if 'highest_priority' in fields and type(highest_priority) is not bool:raise ValueError('Highest-priority selection must be ON/OFF')
        if 'priority' in fields and (type(priority) is not int or not -32768<=priority<=32767):raise ValueError('Priority must be signed16')
        if 'max_quantity' in fields and (type(max_quantity) is not int or not 0<=max_quantity<=32767):raise ValueError('Max quantity must be0..32767')
        if exe is None:raise ValueError('Load executable metadata before changing native item properties')
        if result.get('clone_of'):raise ValueError('Cloned items cannot independently reuse the stock native metadata identity')
        identity=item_id(result)
        result.setdefault('source',{}).setdefault('item_metadata_native',native_properties(exe,identity))
        data.setdefault('item_native_properties',{}).update(fields)
    return result


def patch_native_properties(exe,rows):
    pending=[row for row in rows if row.get('data',{}).get('item_native_properties')]
    if not pending:return bytes(exe),dict(changes=[],category_changes_native=False)
    header=parse_exe(exe)
    # This native selector establishes group/flag/rank widths and routing.
    evidence=json.loads((ROOT/'data/2026-10-03-1534-inventory-selection.json').read_text())
    pc=int(evidence['entry'],16);off=runtime_to_offset(header,pc)
    words=tuple(int(word,16) for word in evidence['words'])
    raw=struct.pack('<'+'I'*len(words),*words)
    if exe[off:off+len(raw)]!=raw:raise ValueError('Native item selector signature changed; metadata export refused')
    output=bytearray(exe);changes=[];claimed={}
    for row in pending:
        if row.get('clone_of'):raise ValueError('Independent cloned item metadata allocation is not supported')
        identity=item_id(row);baseline=row.get('source',{}).get('item_metadata_native')
        if not baseline or baseline.get('item_id')!=identity:raise ValueError('Item native metadata preimage missing')
        before=bytes.fromhex(baseline['raw'])
        if len(before)!=10:raise ValueError('Item native metadata preimage needs10bytes')
        request=row['data']['item_native_properties']
        # Reuse validation without replacing the captured source baseline.
        checked=apply(row,category_for(row),exe=exe,**request)
        group,flags,rank,maximum,icon=struct.unpack('<hHhhH',before)
        if 'menu_group' in request:group=request['menu_group']
        if 'highest_priority' in request:flags=(flags&~1)|int(request['highest_priority'])
        rank=request.get('priority',rank);maximum=request.get('max_quantity',maximum)
        after=struct.pack('<hHhhH',group,flags,rank,maximum,icon)
        offset=runtime_to_offset(header,TABLE+identity*10)
        if identity in claimed and claimed[identity]!=after:raise ValueError('Conflicting definitions edit the same native item')
        claimed[identity]=after
        if bytes(exe[offset:offset+10]) not in (before,after):raise ValueError('Imported item metadata changed since selection')
        output[offset:offset+10]=after
        if before!=after:changes.append(dict(item_id=identity,offset=offset,before=before.hex(),after=after.hex()))
    return bytes(output),dict(changes=changes,category_changes_native=False,
        limitation='Category alone is grouping; consumption/use callbacks and passive effects retain native identity behavior',
        quantity_note='Native pickup limit tests equality only; changing a maximum does not clamp existing quantities')
