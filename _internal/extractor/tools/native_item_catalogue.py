"""Retail resource display names and native selector groups; no progressive aliases."""
import hashlib,struct
from pathlib import Path
from functools import lru_cache
from item_categories import native_properties
ROOT=Path(__file__).resolve().parents[1]

def decode_names(raw,count=98):
    if len(raw)<0x800:raise ValueError('Item name resource table is truncated')
    names=[]
    for identity in range(count):
        offset=struct.unpack_from('<h',raw,2*(0x200+identity))[0]
        if offset==-1:names.append(None);continue
        if not 0x800<=offset<len(raw):raise ValueError('Item name resource pointer is outside strings')
        try:end=raw.index(0,offset)
        except ValueError:raise ValueError('Item name is not terminated')
        names.append(raw[offset:end].decode('latin1').replace('{B',"'") or None)
    return names

@lru_cache(maxsize=4)
def _rows(resource,exe):
    names=decode_names(resource);digest=hashlib.sha256(resource).hexdigest();rows=[]
    for identity,name in enumerate(names):
        metadata=native_properties(exe,identity)
        rows.append(dict(name=name or f'Unnamed item {identity:02X}',slot=metadata['menu_group'],
            maxQuantity=metadata['max_quantity'],native_metadata=metadata,
            label_basis='retail ETC_USA.R item name table; native EXE selector group',
            resource_sha256=digest,unnamed=name is None))
    return tuple(rows)

def native_items():
    resource=ROOT/'private-inputs/disc/DATA/ETC_USA.R';exe=ROOT/'private-inputs/disc/ALUN_CD.EXE'
    if not resource.is_file() or not exe.is_file():return None
    # File contents are part of the cache key, so replacing a local base cannot
    # reuse stale labels or pretend the old executable metadata is current.
    return [dict(row) for row in _rows(resource.read_bytes(),exe.read_bytes())]

def generated_default(row,info,legacy=None):
    source=row.get('source',{})
    if row.get('clone_of') or source.get('user_named'):return False
    previous=source.get('item_default_name');name=row['name']
    generated=name.startswith(('Item definition','Unnamed item ')) or name==previous
    legacy_default=legacy is not None and name==legacy['name'] and source.get('item_label_basis')=='local randomizer item.json; progressive labels may differ from vanilla'
    current_default=name==info['name'] and source.get('item_label_basis') in (None,info['label_basis'])
    return generated or legacy_default or current_default

def apply_default(row,info,legacy=None):
    """Refresh only recognized generated defaults; preserve custom/imported names."""
    if not generated_default(row,info,legacy):return
    source=row.setdefault('source',{})
    legacy_default=legacy is not None and row['name']==legacy['name'] and source.get('item_label_basis')=='local randomizer item.json; progressive labels may differ from vanilla'
    row['name']=info['name']
    source['item_default_name']=info['name']
    source['item_label_basis']=info['label_basis']
    source['item_resource_sha256']=info['resource_sha256']
    source['item_metadata_native']=dict(info['native_metadata'])
    current=row['data'].get('slot')
    if current is None or legacy_default and current==legacy.get('slot'):
        row['data']['slot']=info['slot']
        baseline=source.get('native_data_baseline',{})
        if legacy_default and baseline.get('slot')==legacy.get('slot'):baseline['slot']=info['slot']
