"""Bounded, source-derived DATAS map-event reader; no native/runtime claim.
xcasadio 242b09a20ae1186c90278ba5f15f0f9a84104ef4:
DatasBin/SiMapEventRecord.cs:5-25, SpriteInfoMapEvents.cs:9-28;
GameEngine.cs:1667-1718 (all under AlundraTools/AlundraEngine).
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class MapEvent:
    offset: int
    rectangle: tuple
    program: int
    unknown: bytes

    @property
    def bank_b_index(self):
        return self.program & 0x7f

    def encode(self):
        return bytes((*self.rectangle, self.program)) + self.unknown

def read_map_events(data, offset, end):
    """Return (records, consumed_end); end is an exclusive caller-owned bound.
    A four-byte zero rectangle terminates, not an eight-byte zero record.
    The format allows at most 64 records; trailing bytes are never free space.
    """
    if not 0 <= offset <= end <= len(data):
        raise ValueError("Invalid map-event bounds")
    records = []
    for _ in range(64):
        if offset + 4 > end:
            raise ValueError("Missing map-event terminator")
        if data[offset:offset+4] == b"\0" * 4:
            return records, offset + 4
        if offset + 8 > end:
            raise ValueError("Truncated map-event record")
        records.append(MapEvent(offset, tuple(data[offset:offset+4]),
                                data[offset+4], bytes(data[offset+5:offset+8])))
        offset += 8
    return records, offset
