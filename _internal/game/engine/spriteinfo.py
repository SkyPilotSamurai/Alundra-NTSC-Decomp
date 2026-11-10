"""Sprite-info blocks (the shared sprites' at 0x800CBF58, the map's at 0x801536C0 + its
section offset) and their info structs (0x801F3958 / 0x801F2EC0), as the game sets them up.

A block begins with 12 offsets: +0 entity records, +4 map effect records, +8 ?, +0xC the
256-entry sprite table, +0x10 the effect table, +0x14 .. +0x2C more tables.  Each sprite
header starts with 4 offsets (animation sets, frames ...), then +0x10 flags (3 bytes),
+0x13..0x17 the built-in programs A C D E F, +0x18 hit box, +0x1E break effect, +0x1F
contents.  The remake writes the raw block (assets/.../sprite_info.bin) at the game's
address and relocates it with the ported 0x8002DB6C, so ported code reads headers and
records through the same pointers as the original (Entity +0x44 / +0x64)."""
from .registry import port
from .core import M32

GLOBAL_INFO, MAP_INFO = 0x801F3958, 0x801F2EC0
GLOBAL_BLOCK, MAP_BLOCK = 0x800CBF58, 0x801536C0


@port(0x8002DB6C)
def relocate(g, info, block):
    """0x8002DB6C: turns the block's offsets into pointers and fills the info struct:
    +0 block, +4 block + [0x14], +8 entity records (+0x14 their count: up to 0x80 until a
    zero word), +0xC the sprite table (+0x10 its entries: up to 0x100 until a zero; each
    valid entry and its header's 4 offsets get the block added), +0x1C the effect table
    (+0x20 entries, relocated the same way), +0x18 map effect records (+0x24 count, 12 bytes
    each), +0x28 [8] records (+0x2C count, 8 bytes each), +0x30 and +0x34..+0x48 the
    pointers at [0x18]..[0x2C]."""
    m = g.mem
    add = lambda v: (block + v) & M32
    m.w32(info, block)
    m.w32(info + 4, add(m.s32(block + 0x14)))
    tab = add(m.s32(block + 0xC)); m.w32(info + 0xC, tab)
    n = 0
    while True:
        v = m.u32(tab + 4 * n)
        if v == 0: break
        if v != 0xFFFFFFFF:
            h = add(v); m.w32(tab + 4 * n, h)
            for k in range(4): m.w32(h + 4 * k, add(m.u32(h + 4 * k)))
        n += 1
        if n >= 0x100: break
    m.w32(info + 0x10, n)
    o = m.s32(block)
    if o:
        recs = add(o); m.w32(info + 8, recs)
        n = 0
        while m.u32(recs + 0x14 * n) != 0:
            n += 1
            if n >= 0x80: break
        m.w32(info + 0x14, n)
    else:
        m.w32(info + 8, 0); m.w32(info + 0x14, 0)
    eff = add(m.s32(block + 0x10)); m.w32(info + 0x1C, eff)
    n = 0
    while True:
        v = m.u32(eff + 4 * n)
        if v == 0: break
        if v != 0xFFFFFFFF: m.w32(eff + 4 * n, add(v))
        n += 1
        if n >= 0x100: break
    m.w32(info + 0x20, n)
    o = m.s32(block + 4)
    if o:
        p = add(o); m.w32(info + 0x18, p)
        n = 0
        while m.u32(p + 0xC * n) != 0:
            n += 1
            if n >= 0x80: break
        m.w32(info + 0x24, n)
    else:
        m.w32(info + 0x18, 0); m.w32(info + 0x24, 0)
    o = m.s32(block + 8)
    if o:
        p = add(o); m.w32(info + 0x28, p)
        n = 0
        while m.u32(p + 8 * n) != 0:
            n += 1
            if n >= 0x80: break
        m.w32(info + 0x2C, n)
    else:
        m.w32(info + 0x28, 0); m.w32(info + 0x2C, 0)
    m.w32(info + 0x30, add(m.s32(block + 0x18)))
    for i in range(6):
        m.w32(info + 0x34 + 4 * i, add(m.s32(block + 0x18 + 4 * i)))


def load_block(g, info, block, data):
    """Writes a raw sprite-info block at its address and relocates it."""
    m = g.mem
    m.b[block & 0x1FFFFF: (block & 0x1FFFFF) + len(data)] = data
    relocate(g, info, block)


def header_addr(g, catalogue):
    """The sprite header of catalogue n (0x100 + i: the map's sprite i), as 0x8003A424
    looks it up; 0 when the table has none."""
    m = g.mem
    if catalogue >= 0x100:
        info, i = MAP_INFO, catalogue - 0x100
    else:
        info, i = GLOBAL_INFO, catalogue
    if not 0 <= i < m.s32(info + 0x10): return 0
    v = m.u32(m.u32(info + 0xC) + 4 * i)
    return 0 if ((v - 0x80000000) & M32) > 0x1FFFFF else v


def record_addr(g, ref):
    """Map entity record ref (20 bytes), 0 when out of range."""
    m = g.mem
    if not 0 <= ref < m.s32(MAP_INFO + 0x14): return 0
    return (m.u32(MAP_INFO + 8) + ref * 0x14) & M32
