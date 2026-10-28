"""Source-derived 20-byte DATAS entity records; positions remain raw bytes.
Reference: xcasadio 242b09a20ae1186c90278ba5f15f0f9a84104ef4,
AlundraTools/AlundraEngine/DatasBin/SiEntityRecord.cs:8-54 and
SpriteInfoEntities.cs:9-26. Not independently runtime verified.
"""
from dataclasses import dataclass
import struct

@dataclass(frozen=True)
class EntityRecord:
    offset: int
    raw: bytes

    @property
    def rectangle(self):
        return tuple(self.raw[:4])

    @property
    def position_raw(self):
        return tuple(self.raw[7:10])

    @property
    def programs(self):
        return dict(zip("ABCDEF", self.raw[10:16]))

    @property
    def contents(self):
        return struct.unpack_from("<H", self.raw, 18)[0]

    def encode(self):
        return self.raw

def read_entities(data, offset, end):
    if not 0 <= offset <= end <= len(data):
        raise ValueError("Invalid entity bounds")
    records = []
    for _ in range(128):
        if offset + 4 > end:
            raise ValueError("Missing entity terminator")
        if data[offset+2:offset+4] == bytes(2):
            return records, offset + 4
        if offset + 20 > end:
            raise ValueError("Truncated entity")
        records.append(EntityRecord(offset, bytes(data[offset:offset+20])))
        offset += 20
    return records, offset
