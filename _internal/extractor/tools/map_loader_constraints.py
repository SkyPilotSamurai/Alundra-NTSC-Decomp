"""Conservative stock-loader map table checks; not gameplay certification.

Native evidence: data/2026-10-04-agent-map-loader.json. The CD reader loops
forever for a start offset not aligned to2048. Map size ceiling is the largest
original stock map, not a proved general-purpose allocator capacity.
"""
import struct
STOCK_MAX_MAP_BYTES=0x58800
MAP_BUFFER_ADDRESS=0x801536c0

def validate_layout(data):
    if len(data)<0x7b8:raise ValueError('Missing complete484-entry map table')
    from map_slots import offsets as map_offsets,table_end
    offsets=map_offsets(data)  # stock maps, new slots 483-499, expanded maps 500+
    if offsets[-1]!=table_end(data):raise ValueError('Map table end must equal the end of map data')
    if offsets[0]<0x800:raise ValueError('Map overlaps resource header')
    if any(p&0x7ff for p in offsets):raise ValueError('Native CD reader requires2048-byte-aligned offsets')
    sizes=[b-a for a,b in zip(offsets,offsets[1:])]
    if min(sizes)<=0:raise ValueError('Map offsets must increase strictly')
    if max(sizes)>STOCK_MAX_MAP_BYTES:raise ValueError('Map exceeds conservative largest-stock-map bound')
    return dict(map_count=len(sizes),maximum_map_bytes=max(sizes),
                map427_bytes=sizes[427],map427_buffer_end=hex(MAP_BUFFER_ADDRESS+sizes[427]),
                stock_maximum_buffer_end=hex(MAP_BUFFER_ADDRESS+STOCK_MAX_MAP_BYTES),
                alignment=2048,gameplay_verified=False)
