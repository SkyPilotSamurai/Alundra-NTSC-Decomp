"""Read-only tables of ALUN_CD.EXE (assets/exe_data.bin, made by tools/us_decomp/dump_rodata.py):
directions, per-animation flags, weapon records, sound / dust tables...  Read by address."""
import struct
from pathlib import Path

_IMG = None
BASE = 0x80020000


def _img():
    global _IMG
    if _IMG is None:
        import sys                                              # (home.py: the code may be in game/ or the exe)
        code = Path(__file__).resolve().parents[1]
        home = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else (code.parent if code.name == 'game' else code)
        f = home / 'assets' / 'exe_data.bin'
        _IMG = f.read_bytes()
    return _IMG


def u8(a): return _img()[a - BASE]
def s8(a): v = _img()[a - BASE]; return v - 256 if v & 0x80 else v
def u16(a): return struct.unpack_from('<H', _img(), a - BASE)[0]
def s16(a): return struct.unpack_from('<h', _img(), a - BASE)[0]
def u32(a): return struct.unpack_from('<I', _img(), a - BASE)[0]
def s32(a): return struct.unpack_from('<i', _img(), a - BASE)[0]
