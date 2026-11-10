"""Lossless portal record codec. Source-derived format, not runtime validation.
Reference: xcasadio 242b09a20ae1186c90278ba5f15f0f9a84104ef4,
AlundraTools/AlundraEngine/DatasBin/Portal.cs lines 5-16.
All offsets accepted here are DATAS.BIN offsets, never raw disc offsets.
"""
import struct
from dataclasses import dataclass

FORMAT = struct.Struct("<4BhBBhH")

@dataclass(frozen=True)
class Portal:
    x1: int
    y1: int
    x2: int
    y2: int
    destination_map: int
    destination_x: int
    destination_y: int
    z: int
    flags: int

    @classmethod
    def read(cls, data, offset=0):
        if offset < 0 or offset + FORMAT.size > len(data):
            raise ValueError("Portal lies outside input")
        return cls(*FORMAT.unpack_from(data, offset))

    def encode(self):
        try:
            return FORMAT.pack(self.x1, self.y1, self.x2, self.y2,
                self.destination_map, self.destination_x, self.destination_y,
                self.z, self.flags)
        except struct.error as error:
            raise ValueError("Portal field out of native range") from error


def replace_portal(data, offset, expected, replacement):
    """Return a new byte string after checking the exact original record.
    No file writes and no claim that a structurally valid warp is playable.
    """
    old = Portal.read(data, offset)
    if old != expected:
        raise ValueError("Original portal does not match expected record")
    encoded = replacement.encode()
    return bytes(data[:offset]) + encoded + bytes(data[offset + FORMAT.size:])
