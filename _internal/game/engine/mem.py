"""The game's memory for everything that is not an Entity / effect record or a named global
(layout.py): EXE tables, loaded map and sprite data, and the globals not named yet.
Ported code reads data through pointers exactly as the game does: g.mem.u8(e.header_addr + 5).
In the checks g.mem is the RAM snapshot itself; in the remake it starts as the EXE image
(assets/exe_data.bin) and the data loaders fill it like the game's."""
import struct
from pathlib import Path
from . import layout as L

SIZE = 0x200000
_ENT = (L.ENT_BASE & 0x1FFFFF, (L.ENT_BASE + L.ENT_SIZE * L.ENT_COUNT) & 0x1FFFFF)
_FX = (L.FX_BASE & 0x1FFFFF, (L.FX_BASE + L.FX_SIZE * L.FX_COUNT) & 0x1FFFFF)
_SZ = {'i32': 4, 'u32': 4, 'i16': 2, 'u16': 2, 'i8': 1, 'u8': 1, 'ptr': 4, 'fxptr': 4, 'addr': 4}
_GLOB = {}
for _n, (_a, _t) in L.GLOBALS.items():
    for _k in range(_SZ[_t]): _GLOB[(_a + _k) & 0x1FFFFF] = _n

_hu, _hs, _iu, _is = struct.Struct('<H'), struct.Struct('<h'), struct.Struct('<I'), struct.Struct('<i')


class ModelledAddress(Exception):
    pass


class Mem:
    """Byte memory addressed like the PlayStation (0x80xxxxxx, KSEG0; 2 MB)."""
    guard = True                         # stop on reads/writes of fields the port keeps as objects

    def __init__(self, data=None):
        self.b = data if data is not None else bytearray(SIZE)

    def _chk(self, a, n):
        a &= 0x1FFFFF
        if self.guard and (_ENT[0] <= a < _ENT[1] or _FX[0] <= a < _FX[1] or a in _GLOB or a + n - 1 in _GLOB):
            raise ModelledAddress(f'{a | 0x80000000:08X}: use the entity / effect object or g.{_GLOB.get(a, "ent / fx")}')
        return a

    def u8(self, a): return self.b[self._chk(a, 1)]
    def s8(self, a): v = self.b[self._chk(a, 1)]; return v - 0x100 if v & 0x80 else v
    def u16(self, a): return _hu.unpack_from(self.b, self._chk(a, 2))[0]
    def s16(self, a): return _hs.unpack_from(self.b, self._chk(a, 2))[0]
    def u32(self, a): return _iu.unpack_from(self.b, self._chk(a, 4))[0]
    def s32(self, a): return _is.unpack_from(self.b, self._chk(a, 4))[0]
    def w8(self, a, v): self.b[self._chk(a, 1)] = v & 0xFF
    def w16(self, a, v): _hu.pack_into(self.b, self._chk(a, 2), v & 0xFFFF)
    def w32(self, a, v): _iu.pack_into(self.b, self._chk(a, 4), v & 0xFFFFFFFF)
    def bytes(self, a, n): a = self._chk(a, n); return bytes(self.b[a:a + n])


def exe_image():
    """2 MB with the EXE's data (assets/exe_data.bin at 0x80020000) in place."""
    m = bytearray(SIZE)
    import sys                                                  # (home.py: the code may be in game/ or the exe)
    code = Path(__file__).resolve().parents[1]
    home = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else (code.parent if code.name == 'game' else code)
    img = (home / 'assets' / 'exe_data.bin').read_bytes()
    m[0x20000:0x20000 + len(img)] = img
    return Mem(m)
