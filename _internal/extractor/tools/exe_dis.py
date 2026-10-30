"""Small helpers to read ALUN_CD.EXE code: disassemble, find address references
(lui+addiu/ori/lw/sw pairs) and callers. python exe_dis.py dis 0x8002DEAC 40"""
import struct, sys
from pathlib import Path
import os as _os
EXE = Path(_os.environ.get('ALUN_EXE') or Path(__file__).resolve().parents[1] / 'private-inputs/disc/ALUN_CD.EXE')   # ALUN_EXE: another EXE of the disc
D = EXE.read_bytes()
BASE = struct.unpack_from('<I', D, 0x18)[0]; SIZE = struct.unpack_from('<I', D, 0x1C)[0]
_MD = None


def _md():
    """The MIPS disassembler (capstone), loaded only when something disassembles: the extractor
    only reads bytes and words, and the remake's exe has no capstone."""
    global _MD
    if _MD is None:
        import capstone
        _MD = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 + capstone.CS_MODE_LITTLE_ENDIAN)
    return _MD


def off(a): return a - BASE + 0x800
def word(a): return struct.unpack_from('<I', D, off(a))[0]


def dis(a, n=40):
    out = []
    for i in _md().disasm(D[off(a):off(a) + n * 4], a):
        out.append(f'{i.address:08X}  {i.mnemonic:8s} {i.op_str}')
    return out


def refs(target):
    """pcs where a lui/low16 pair makes `target` (same register, within 12 instructions)."""
    hi = (target + 0x8000) >> 16; lo = target & 0xFFFF; out = []
    for p in range(BASE, BASE + SIZE, 4):
        w = word(p)
        if w >> 26 == 0x0F and w & 0xFFFF == hi:
            rt = (w >> 16) & 31
            for q in range(p + 4, min(p + 52, BASE + SIZE), 4):
                v = word(q)
                if (v >> 21) & 31 == rt and v & 0xFFFF == lo and v >> 26 in (0x09, 0x0D, 0x23, 0x2B, 0x21, 0x25, 0x20, 0x24, 0x28, 0x29, 0x0F):
                    out.append(q); break
    return out


def callers(target):
    t = (target >> 2) & 0x03FFFFFF
    return [p for p in range(BASE, BASE + SIZE, 4) if word(p) == (3 << 26 | t) or word(p) == (2 << 26 | t)]


def func_start(a):
    """walk back to the 'addiu sp,sp,-N' that opens the function."""
    p = a
    while p > BASE:
        w = word(p)
        if w >> 16 == 0x27BD and (w & 0x8000): return p
        p -= 4
    return a


if __name__ == '__main__':
    cmd = sys.argv[1]; a = int(sys.argv[2], 0)
    if cmd == 'dis': print('\n'.join(dis(a, int(sys.argv[3]) if len(sys.argv) > 3 else 40)))
    elif cmd == 'refs': print([hex(x) for x in refs(a)])
    elif cmd == 'callers': print([hex(x) for x in callers(a)])
    elif cmd == 'start': print(hex(func_start(a)))
