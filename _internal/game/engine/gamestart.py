"""Starting, continuing and retrying a game, ported from the US ALUN_CD.EXE.

The game's state is one block, 0x801DD2D8 .. 0x801DDA30 (0x758 bytes): +0 / +4 the record's
word and slot, +8 / +0x28 the two title lines a save shows, +0x48 the play time, +0x4C.. the
respawn point (map, tile x, y, z), +0x5C the flags (0x801DD334, 64 words), +0x15C the door table
(0x801DD434, s16[500]), +0x544 the stats (0x801DD81C), +0x556 the items (0x801DD82E, 4 bytes
each), +0x756 a byte that counts the retries.
The boot program and ALUN_CD.EXE hand it over at 0x80010000 (*(0x80029B68)): ALUN_CD starts
with 0x80031CBC, which looks at its first word - 1: a game continued (the History Book put a
saved record there), 0: a new game, else the debug start.  A new game stores its starting
block there (0x80083E34), and so does every save (0x8006343C: the record written); a game
over's retry (0x80031B50) takes it back (0x80083DE0)."""
from .registry import port
from . import calls, menu
from .core import s32

BLOCK, BLOCK_END = 0x801DD2D8, 0x801DDA30
HANDOFF_PTR = 0x80029B68


def handoff(g): return g.mem.u32(HANDOFF_PTR)


@port(0x8004F114)
def stats_reset(g):
    """The stats and item pointers, life 1 / 1, the rest 0, the 128 item records cleared and
    99 records in use."""
    m = g.mem
    m.w32(0x80119AEC, 0x801DD82E); m.w32(0x80119AE8, 0x801DD81C)
    m.w16(0x801DD81E, 1); m.w16(0x801DD81C, 1)
    for a in (0x801DD822, 0x801DD820, 0x801DD824, 0x801DD82A, 0x801DD82C): m.w16(a, 0)
    n = 0
    while n < 0x80 and m.u8(m.u32(0x800C7DE4 + 8 * n)) != 0: n += 1
    if n == 0x80: calls.call(g, 0x80083EE4, 0x8002655C)
    inv = m.u32(0x80119AEC)
    m.w32(0x8012E234, 0x63)
    for k in range(0x80): m.w16(inv + 4 * k, 0); m.w16(inv + 4 * k + 2, 0)


@port(0x80083DA0)
def flags_reset(g):
    """A new game: the flags (0x801DD334, 64 words) cleared, the door table made 0, 1, 2 ..."""
    m = g.mem
    for k in range(0x40): m.w32(0x801DD334 + 4 * k, 0)
    for k in range(0x1F4): m.w16(0x801DD434 + 2 * k, k)


@port(0x80083DE0)
def block_restore(g):
    m = g.mem; src = handoff(g)
    for i in range(0x758): m.w8(BLOCK + i, m.u8(src + i))


@port(0x80083E34)
def block_store(g):
    m = g.mem; dst = handoff(g)
    for i in range(0x758): m.w8(dst + i, m.u8(BLOCK + i))
    m.w32(dst, 1)


def _arrive(g, x, y, z):
    m = g.mem
    g.warp_anim = 0x36
    m.w32(0x801D7B40, ((x * 0x18 + 0xC) << 16) & 0xFFFFFFFF)
    m.w32(0x801D7B90, ((y * 0x10 + 8) << 16) & 0xFFFFFFFF)
    m.w32(0x801D7B94, (z << 20) & 0xFFFFFFFF)


@port(0x80031CBC)
def game_start(g):
    """ALUN_CD.EXE's start: a continued game takes the handed-over block, a new one starts on
    the ship (map 389, respawn 0x21, 0x3B) with life 10, the starting items and the sword;
    either way Alundra arrives at the respawn point (anim 0x36) with the play time kept."""
    m = g.mem
    g.warp_anim = 0; g.floor_damage_lock = 0
    calls.call(g, 0x8004F114)
    h = handoff(g)
    if m.s32(h) == 1:
        calls.call(g, 0x80083DE0)
        x, y, z = m.s32(0x801DD328), m.s32(0x801DD32C), m.s32(0x801DD330)
    else:
        calls.call(g, 0x80083DA0)
        if m.s32(h) == 0:
            x, y, z = 0x21, 0x23, 0
            m.w32(0x801DD324, 0x185); m.w32(0x801DD328, 0x21); m.w32(0x801DD32C, 0x3B); m.w32(0x801DD330, 0)
            g.warp_dir = 0
            calls.call(g, 0x8004F2DC, 0xA); calls.call(g, 0x8004F3A8, 0xA)
            calls.call(g, 0x8004F474, 0); calls.call(g, 0x8004F540, 0); calls.call(g, 0x8004F60C, 0)
        else:                                                       # the debug start
            x, y, z = 0x16, 0x1D, 0xA
            m.w32(0x801DD324, 0xB); m.w32(0x801DD328, x); m.w32(0x801DD32C, y); m.w32(0x801DD330, z)
            g.warp_dir = 0
            calls.call(g, 0x8004F2DC, 0x2D); calls.call(g, 0x8004F3A8, 0x26)
            calls.call(g, 0x8004F474, 3); calls.call(g, 0x8004F540, 2); calls.call(g, 0x8004F60C, 0x873)
            calls.call(g, 0x8004CA2C)
        m.w32(0x801DD2DC, -1); m.w8(0x801DDA2E, 0); m.w32(0x801DD320, 0)
        for n in range(0x62):
            if m.u8(0x800C7DEA + 8 * n) & 0x80: calls.call(g, 0x8004FBE4, n)
        calls.call(g, 0x8004FB28, 1)
        calls.call(g, 0x80083E34)
    _arrive(g, x, y, z)
    g.warp_x = s32((m.s32(0x801DD328) * 0x18 + 0xC) << 16)
    g.warp_effect = 0; g.warp_dir = 0
    g.warp_map = m.s32(0x801DD324)
    g.warp_y = s32((m.s32(0x801DD32C) * 0x10 + 8) << 16)
    g.warp_z = s32(m.s32(0x801DD330) << 20)
    m.w32(0x801D7CB4, m.u32(0x801DD320))


@port(0x80031B50)
def retry(g):
    """A game over's retry: the retry counter of the handed-over record goes up (to 255), the
    block comes back from it and Alundra arrives at its respawn point (anim 0x36, facing 0)."""
    m = g.mem; h = handoff(g)
    c = m.u8(h + 0x756)
    if c < 0xFF: m.w8(h + 0x756, c + 1)
    calls.call(g, 0x8004F114)
    calls.call(g, 0x80083DE0)
    g.warp_anim = 0x36
    x = ((m.s32(0x801DD328) * 0x18 + 0xC) << 16) & 0xFFFFFFFF
    m.w32(0x801D7B40, x); g.warp_x = s32(x)
    g.warp_dir = 0
    g.warp_map = m.s32(0x801DD324)
    y = ((m.s32(0x801DD32C) * 0x10 + 8) << 16) & 0xFFFFFFFF
    m.w32(0x801D7B90, y); g.warp_y = s32(y)
    z = (m.s32(0x801DD330) << 20) & 0xFFFFFFFF
    m.w32(0x801D7B94, z); g.warp_z = s32(z)


@port(0x8004CA2C)
def hud_counters_full(g):
    """The HUD shows full life and magic at once: shown life = shown most life = the most life,
    the same for magic (script command C3 after it fills both, and the debug start)."""
    from . import menu
    st = menu._stats(g)
    hud = getattr(g, 'hud', None)
    if hud is not None and hasattr(hud, 'sync'):
        hud.sync(max(0, g.mem.s16(st + 2)), max(0, g.mem.s16(st + 6)))
