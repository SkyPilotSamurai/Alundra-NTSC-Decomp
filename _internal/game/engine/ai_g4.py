"""Built-in sprite programs, group 4 (US ALUN_CD.EXE 0x8007318C-0x8007947C): C41, C43-C49,
C77, C80-C82, C85, C87 (boss programs and the things they spawn) and their local helpers."""
from .registry import port
from .core import s32, s16, next_seed, hi
from . import aihelp, core, entity, player, calls
from . import layout as L

M32 = 0xFFFFFFFF
TURN = 0x80028AD8           # u8[32]: the direction turned away (wall / ledge)
QDIR = 0x80028AF8           # u8[4]: the direction of each facing quadrant
FLAGS_6378 = 0x801E6378     # word: bit 0 set = every C45 / C87 stops (scene over)


class _MemArr:
    """bytes[] / ai[] of a _RawEnt: u8 / s16 elements in memory."""
    def __init__(self, g, a, sz): self._g, self._a, self._sz = g, a, sz
    def __getitem__(self, i):
        return self._g.mem.u8(self._a + i) if self._sz == 1 else self._g.mem.s16(self._a + 2 * i)
    def __setitem__(self, i, v):
        if self._sz == 1: self._g.mem.w8(self._a + i, v)
        else: self._g.mem.w16(self._a + 2 * i, v)


class _RawEnt:
    """What the game reads and writes through an Entity pointer that is not an entity
    record: NULL (low RAM, address 0 + field offset) or some other value.  Only reached when
    a program runs without the parent / partner / child it expects (or on garbage the checks
    put in its fields); a misaligned pointer into the entity table is not modelled (on the
    PlayStation the unaligned loads would crash anyway)."""
    def __init__(self, g, base=0):
        object.__setattr__(self, '_g', g); object.__setattr__(self, '_b', base & M32)
        object.__setattr__(self, 'bytes', _MemArr(g, (base + 0x274) & M32, 1))
        object.__setattr__(self, 'ai', _MemArr(g, (base + 0x280) & M32, 2))

    def __getattr__(self, n):
        if n not in L.ENTITY: raise AttributeError(n)
        o, t = L.ENTITY[n]; m = self._g.mem; a = (self._b + o) & M32
        if t == 'ptr': return _ent_ptr(self._g, m.u32(a)) if m.u32(a) else None
        return m.u32(a) if t in ('u32', 'addr', 'fxptr') else m.s32(a)

    def __setattr__(self, n, v):
        o, t = L.ENTITY[n]
        if v is None: v = 0
        elif not isinstance(v, int): v = entity.ent_addr(v)
        self._g.mem.w32((self._b + o) & M32, v)


def _ent(g, e):
    """An Entity pointer field the game dereferences without testing it."""
    return e if e is not None else _RawEnt(g)


def _ent_ptr(g, a):
    """The Entity a pointer word points at (an entity, or memory for NULL / other values)."""
    a &= M32
    if L.ENT_BASE <= a < L.ENT_BASE + L.ENT_SIZE * L.ENT_COUNT and (a - L.ENT_BASE) % L.ENT_SIZE == 0:
        return g.ent[(a - L.ENT_BASE) // L.ENT_SIZE]
    return _RawEnt(g, a)


def _arg(e):
    """An Entity pointer passed on to a game function (the address for a _RawEnt)."""
    return e._b if isinstance(e, _RawEnt) else e


def _face(g, e):
    """Turn toward Alundra."""
    p = g.ent[0]
    e.target_dir = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))


def _spawn(g, parent, index, x, y, z, d):
    """SpawnWarpEntity(parent, 1 (map sprite), index, x, y, z, direction)."""
    return entity.spawn_warp_entity(g, _arg(parent), 1, index, s32(x), s32(y), s32(z), d)


# ---------------------------------------------------------------- C41
@port(0x8007318C)
def ai_c41(g, e):
    """C41 (shot emitter of a boss): copies the pattern number of its parent (bytes[1]) and
    walks while dropping sprite 0xF2 (fire) behind it: straight lines that bounce off walls,
    a homing line, a spiral, or bursts; when done it vanishes and clears parent bytes[2]."""
    par = _ent(g, e.parent)
    aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 0:
        e.target_anim = 1
        e.bytes[1] = par.bytes[1]
        par.bytes[2] = 1
        k = e.bytes[1]
        if k in (1, 4): e.bytes[2] = 0x14
        elif k == 2:
            _face(g, e); e.bytes[2] = 0xF; e.ai[1] = 0xB4
        elif k == 3:
            v = g.mem.u8(QDIR + par.anim_quadrant)
            e.ai[1] = 0x14; e.bytes[0] = 0
            e.target_dir = (v + 8) & 0x1F
        elif k == 5: e.bytes[2] = 1
        elif k in (6, 7): e.bytes[2] = 6
        return
    if a != 1: return
    k = e.bytes[1]
    if k in (1, 4):
        if (e.ai[1] & 0xFFFF) == 0: e.ai[1] = 0xF
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF:
            if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
                e.target_dir = g.mem.u8(TURN + e.target_dir)
            return
        _spawn(g, e, 0xF2, e.px, e.py, e.pz + 0xA00000, e.target_dir)
        e.bytes[2] = e.bytes[2] - 1
        if e.bytes[2] == 0: return _c41_end(g, e, par)
        e.target_dir = hi(next_seed(g), 0x20)
    elif k == 2:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF; e.ai[1] = t
        if t in (0x78, 0x3C): _face(g, e)
        if (e.ai[1] & 0xFFFF) == 0 or e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
            return _c41_end(g, e, par)
        e.bytes[2] = e.bytes[2] - 1
        if e.bytes[2]: return
        _spawn(g, e, 0xF2, e.px, e.py, e.pz + 0xA00000, e.target_dir)
        e.bytes[2] = 0xF
    elif k == 3:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF: return _c41_wall(g, e, par)
        n = e.bytes[0]; e.bytes[0] = n + 1
        if n >= 0x13: return
        if n == 0 or n == 17:                       # a quarter turn and a shot
            e.ai[1] = 5 if n == 0 else 0x14
            e.target_dir = (e.target_dir - 8) & 0x1F
            _spawn(g, e, 0xF2, e.px, e.py, e.pz + 0xA00000, e.target_dir)
        elif n == 18:
            _c41_end(g, e, par)
        else:                                       # spiral: a shot every other step
            if not n & 1: _spawn(g, e, 0xF2, e.px, e.py, e.pz + 0xA00000, e.target_dir)
            e.ai[1] = 5
            e.target_dir = (e.target_dir - 1) & 0x1F
    elif k in (5, 6, 7):
        if (e.ai[1] & 0xFFFF) == 0: e.ai[1] = 0x14
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF: return _c41_wall(g, e, par)
        _spawn(g, e, 0xF2, e.px, e.py, e.pz + 0xA00000, e.target_dir)
        e.bytes[2] = e.bytes[2] - 1
        if e.bytes[2] == 0: _c41_end(g, e, par)


def _c41_wall(g, e, par):
    if e.force_adjusted or aihelp.ledge_ahead(g, e, 0): _c41_end(g, e, par)


def _c41_end(g, e, par):
    player.remove_entity(g, e)
    par.bytes[2] = 0


# ---------------------------------------------------------------- C77
@port(0x80073674)
def ai_c77(g, e):
    """C77: in animation 0 it sinks faster (Z force -0x4000 a frame down to -0x80000)."""
    if e.target_anim == 0 and not e.fz < -0x80000:
        e.fz = s32(e.fz - 0x4000)


# ---------------------------------------------------------------- C43
BOSS_LOCK = 0x801F94D0      # word cleared when the boss's lock timer (item_state) runs out
C43_RING = 0x800277FC       # (x, y) words: the 4 points where C43 drops sprite 0xFC


def _c43_wander(g, e):
    """Walk 60 frames in the direction of the next seed, three legs (pattern 6)."""
    s = next_seed(g)
    e.target_anim = 1; e.ai[1] = 0x3C; e.bytes[1] = 6; e.bytes[2] = 3
    e.target_dir = hi(s, 0x20)


@port(0x800736A4)
def ai_c43(g, e):
    """C43 (boss): picks one of four moves at random every time its timer runs out
    (rush at Alundra, walk away, wander, bounce around the arena, throw sprite 0xFB at him);
    when worn down to a quarter of its HP it calls sprite 0xFC down on four points."""
    t = e.item_state
    if t != 0:
        e.item_state = t - 1
        if t - 1 == 0: g.mem.w32(BOSS_LOCK, 0)
    b3 = e.bytes[3]
    if b3 and e.target_anim == 0:
        if b3 < 4:
            calls.call(g, 0x80083394, e)
            return
        e.target_anim = 9; e.flags = s32(e.flags | 0x40)
        return
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        if r[0] < 5 and r[1] < 5 and not 0x100000 < r[2]:
            k = hi(next_seed(g), 4)
            if k == 0:                              # rush at him
                e.target_anim = 5; _face(g, e)
                e.ai[1] = 0x3C; e.bytes[1] = 1; e.bytes[2] = 0xA
            elif k == 1:                            # walk up
                e.target_dir = 0x10; e.target_anim = 1; e.bytes[1] = 3
            elif k == 2:
                _c43_wander(g, e)
            else:                                   # throw at him
                e.target_anim = 3; e.ai[1] = 0x22
        else:
            k = hi(next_seed(g), 4)
            if k == 0:                              # walk away from him
                e.target_anim = 1
                p = g.ent[0]
                e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
                e.ai[1] = 0x50; e.bytes[1] = 5
            elif k == 2:                            # bounce around the arena (diagonals)
                s = next_seed(g)
                e.target_anim = 5; e.ai[1] = 0x1E; e.bytes[1] = 7; e.bytes[2] = 5
                e.target_dir = hi(s, 4) * 8 + 4
            else:
                _c43_wander(g, e)
    elif a == 1:
        b = e.bytes[1]
        if b == 3:
            t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF; e.ai[1] = t
            if t < 0x1E or not e.force_adjusted: return
            e.target_anim = 3; e.ai[1] = 0x22
        elif b == 5:
            t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
            if t & 0xFFFF and not e.force_adjusted: return
            _face(g, e)
            if r[0] < 9 and r[1] < 9:
                e.target_anim = 3; e.ai[1] = 0x22; e.bytes[1] = 4
                return
            e.target_anim = 0; e.ai[1] = 0x28
        elif b == 6:
            t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
            if t & 0xFFFF and not e.force_adjusted: return
            e.bytes[2] = e.bytes[2] - 1
            if e.bytes[2]: e.target_dir = hi(next_seed(g), 0x20)
            else: e.target_anim = 0
            e.ai[1] = hi(next_seed(g), 0x10) + 0x28
        else:
            t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
            if t & 0xFFFF: return
            e.target_anim = 0; e.ai[1] = 0x28
    elif a == 2:
        if not e.anim_done: return
        b = e.bytes[1]
        if b == 3:                                  # call sprite 0xFC down on the 4 points
            for k in range(4):
                _spawn(g, e, 0xFC, g.mem.s32(C43_RING + 8 * k), g.mem.s32(C43_RING + 8 * k + 4),
                       e.pz + 0xF00000, 0)
            e.target_anim = 0; e.ai[1] = 0xB4
            e.delay = s32(e.delay + 4)
            return
        e.bytes[1] = b + 1
        e.cur_anim = -1
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t == 0: return
        e.ai[1] = t - 1
        if (t - 1) & 0xFFFF: return
        p = g.ent[0]
        d = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
        c = _spawn(g, e, 0xFB, e.px, e.py, e.pz + 0x300000, d)
        if c is None: return
        if r[0] < 6 and r[1] < 6: c.target_anim = 2
        elif r[0] < 9 and r[1] < 9: c.target_anim = 3
        else: c.target_anim = 4
    elif a == 4:
        if e.on_ground:
            e.target_anim = 0; _face(g, e); e.ai[1] = 0x14
    elif a == 5:
        if e.anim_done: e.target_anim = 0xA if e.bytes[1] == 1 else 6
    elif a in (6, 10):
        b = e.bytes[1]
        if b == 1: e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        elif b != 7: return
        if e.ai[1] & 0xFFFF and not e.force_adjusted: return
        e.bytes[2] = e.bytes[2] - 1
        if e.bytes[2] == 0:
            e.target_anim = 0; e.ai[1] = 0x3C
            return
        e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
        if e.bytes[1] == 7:                         # bounce off the arena's edges
            x0 = s32(e.mpx - 0x10000); x1 = s32(e.mpx + e.sizex + 0x10001)
            if not 0x1080000 < x0 or 0x287FFFF < x1:
                e.target_dir = (0x20 - e.target_dir) & 0x1F
                return
            y0 = s32(e.mpy - 0x10000); y1 = s32(e.mpy + e.sizey + 0x10001)
            if not 0x1000000 < y0 or 0x1FFFFFF < y1:
                e.target_dir = (0x10 - e.target_dir) & 0x1F
            return
        _face(g, e)
        if hi(next_seed(g), 3) == 0:
            e.target_dir = (e.target_dir + hi(next_seed(g), 9) - 4) & 0x1F
        e.ai[1] = 0x1E
    elif a == 8:
        if not e.anim_done: return
        if e.bytes[3]:
            e.ai[1] = 0x12C; e.ai[5] = 0x1E; e.target_anim = 0
            e.flags = s32(e.flags & ~3)
            g.mem.w32(BOSS_LOCK, 0)
            return
        e.damaged_tick = 0x5A
        q = e.hp_max
        if q < 0: q += 3
        if not (q >> 2) < e.hp and e.delay < 4:
            e.target_anim = 2; e.bytes[1] = 0
            return
        if hi(next_seed(g), 4) == 0:
            e.target_anim = 3; e.ai[1] = 0x22          # (overwritten at once)
        e.target_anim = 0; e.ai[1] = 0x28


# ---------------------------------------------------------------- C44
C44_DROPS = 0x8002784C      # (x, y) words: where C44 calls sprite 0xFF down (5 points in turn)
C44_RINGS = 0x80027874      # 3 patterns of 9 (dx, dy, timer) words: sprite 0xFE around Alundra
C44_RADIUS = 0x80124784     # word: radius step of the 0xD5 rain (+8 per drop, cleared on anim 5)
DX, DY = 0x80023654, 0x80023694     # s16[32]: unit vector of each direction


@port(0x80074160)
def ai_c44(g, e):
    """C44 (boss): every 300 frames calls sprite 0xFF down on the next of 5 points (5 times);
    hops around, jumps away or at Alundra, rings him with sprite 0xFE (3 patterns), and after
    a roar (anim 5) rains sprite 0xD5 in a widening spiral for 256 frames.  Stops while
    0x801E6378 bit 0 is set; when beaten (anim 9 with bytes[3]) it sets that bit."""
    if g.mem.u32(FLAGS_6378) & 1: return
    if e.bytes[2] < 5:
        e.delay = s32(e.delay + 1)
        if e.delay == 0x12C:
            k = e.bytes[1] * 8
            c = _spawn(g, e, 0xFF, g.mem.s32(C44_DROPS + k), g.mem.s32(C44_DROPS + k + 4), 0x1500000, 0)
            _ent(g, c).target_anim = 4
            n2 = e.bytes[2]; n1 = e.bytes[1]
            e.delay = 0
            e.bytes[1] = n1 + 1
            e.bytes[2] = n2 + 1
            if e.bytes[1] >= 5: e.bytes[1] = 0
    t = e.item_state
    if t != 0:
        t = s32(t - 1); e.item_state = t
        if (t & 0xF) == 0:                          # rain: one 0xD5 every 16 frames
            s1 = (g.rng_seed * 0x7D2B89DD + 0xE06A02E7) & M32
            k = hi(s1, 0x20) * 2
            rad = s32((g.mem.s32(C44_RADIUS) << 6) + 0xA00)
            dx = s32(g.mem.s16(DX + k) * rad)
            dy = s32(g.mem.s16(DY + k) * rad)
            g.rng_seed = s1
            s2 = next_seed(g)
            c = _spawn(g, e, 0xD5, e.px + dx, e.py + dy, e.pz + 0x1000000, hi(s2, 0x20))
            if c is not None:
                if s32(e.pz + 0x1000000) < c.terrain: player.remove_entity(g, c)
                else:
                    core.play_sound(g, 0xB7)
                    c.fz = -0x80000
            g.mem.w32(C44_RADIUS, g.mem.s32(C44_RADIUS) + 8)
    r = aihelp.rel_tile_z(g, e)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        if r[0] < 3 and r[1] < 3 and not 0x200000 < r[2]:
            e.target_anim = 6
            return
        if r[0] < 6 and r[1] < 6 and not 0x200000 < r[2]:
            e.target_anim = 3; _face(g, e); e.ai[1] = 0x3A
            return
        if hi(next_seed(g), 3) or e.item_state:
            e.target_anim = 6
            return
        e.target_anim = 4; _face(g, e)
    elif a == 1:
        t = (e.ai[1] & 0xFFFF) - 1
        b = e.bytes[0]
        e.ai[1] = t
        if b:
            if (t & 0xFFFF) == 0 or e.force_adjusted:
                e.bytes[0] = b - 1
                if e.bytes[0]:
                    aihelp.start_moving(g, e, 1, 0x32, 0x32)
                    return
                s = next_seed(g)
                e.target_anim = 7
                if hi(s, 3) == 0: return
                p = g.ent[0]
                e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
                return
            if r[0] < 4 and r[1] < 4:
                s = next_seed(g)
                e.target_anim = 7
                if hi(s, 3) == 0:
                    _face(g, e)
                    return
                e.target_dir = hi(next_seed(g), 0x20)
            return
        if t & 0xFFFF and not e.force_adjusted: return
        if hi(next_seed(g), 4) == 0:
            e.target_anim = 7
            return
        s = next_seed(g)
        e.target_dir = 0; e.target_anim = 2
        e.ai[1] = hi(s, 0x10) + 0x1E
    elif a == 2:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        if r[0] < 6 and r[1] < 6 and not 0x600000 < (r[5] & M32):
            e.bytes[0] = 3; e.target_anim = 1; _face(g, e); e.ai[1] = 0x3C
        else:
            e.bytes[0] = 0
            aihelp.start_moving_half(g, e, 1, 0x3C)
        if 0x600000 < s32(e.pz - e.terrain): e.bytes[0] = 1
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF == 0:               # ring Alundra with 9 x sprite 0xFE
                core.play_sound(g, 0xB9)
                k = hi(next_seed(g), 3) * 0x6C
                p = g.ent[0]
                for i in range(9):
                    o = C44_RINGS + k + 12 * i
                    c = _spawn(g, e, 0xFE, p.px + g.mem.s32(o), p.py + g.mem.s32(o + 4), p.terrain, 0)
                    c = _ent(g, c)
                    c.target_anim = 4
                    c.ai[1] = g.mem.s32(o + 8)
        if e.anim_done: e.target_anim = 6
    elif a == 4:
        if e.anim_done:
            e.target_anim = 5; e.ai[1] = 0x1C
    elif a == 5:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF == 0:               # start the rain
                e.item_state = 0x100
                g.mem.w32(C44_RADIUS, 0)
                calls.call(g, 0x800832B0)
        if e.anim_done: e.target_anim = 6
    elif a == 6:
        if 0x4FFFFF < s32(e.pz - e.terrain):
            s = next_seed(g)
            e.fz = 0; e.target_anim = 2
            e.ai[1] = hi(s, 0x10) + 0x3C
    elif a == 7:
        if e.on_ground:
            e.fz = 0; e.target_anim = 0; e.ai[1] = 0xF
    elif a == 9:
        if not e.anim_done: return
        if e.bytes[3]:
            g.mem.w32(FLAGS_6378, g.mem.u32(FLAGS_6378) | 1)
            e.target_anim = 0; e.fz = 0
            return
        e.target_anim = 6; e.damaged_tick = 0x5A


# ---------------------------------------------------------------- C45, C87
@port(0x80074AC8)
def ai_c45(g, e):
    """C45 (C44's dropping things' source): waits, then faces Alundra and every 8 frames of
    48 shoots sprite 0xFF (anim 3, bi_e 0x19) the way it faces; stops when 0x801E6378 bit 0
    is set."""
    if g.mem.u32(FLAGS_6378) & 1:
        e.target_anim = 1; e.flags = s32(e.flags | 0x40)
        return
    a = e.target_anim
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        e.target_anim = 2; _face(g, e)
    elif a == 2:
        t = e.ai[1] & 0xFFFF
        if t == 0:
            e.ai[1] = 0x30
            return
        e.ai[1] = t - 1
        if ((t - 1) & 7) == 0:
            c = _spawn(g, e, 0xFF, e.px, e.py, e.pz, g.mem.u8(QDIR + e.anim_quadrant))
            if c is not None: c.target_anim = 3; c.bi_e = 0x19
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; e.ai[1] = 0x1E


@port(0x80074C18)
def ai_c87(g, e):
    """C87: anim 4 counts ai[1] down to anim 2 (ai[1] 32), which counts down to a sound
    (0xB6); stops when 0x801E6378 bit 0 is set."""
    if g.mem.u32(FLAGS_6378) & 1:
        e.target_anim = 1; e.flags = s32(e.flags | 0x40)
        return
    a = e.target_anim
    if a == 4:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF: return
        e.target_anim = 2; e.ai[1] = 0x20
    elif a == 2:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF == 0: core.play_sound(g, 0xB6)


# ---------------------------------------------------------------- C85
@port(0x80075CFC)
def ai_c85(g, e):
    """C85 (part of a C46 boss): follows its parent's Y; vanishes (anim 2) when the parent is
    in anim 6 or 9, or when its 180-frame timer (restarted after anim 1) runs out."""
    par = _ent(g, e.parent)
    e.py = par.py
    if par.target_anim in (9, 6):
        e.target_anim = 2; e.flags = s32(e.flags | 0x40)
    a = e.target_anim
    if a == 1:
        if e.anim_done: e.target_anim = 0; e.ai[1] = 0xB4
    elif a == 0:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF == 0:
            e.target_anim = 2; e.flags = s32(e.flags | 0x40)


# ---------------------------------------------------------------- C46
C46_MIRROR = 0x800279E0     # s16[22]: the animation the other half plays for each animation


@port(0x80082C30, ret=True)
def facing_range(g, e, rel, q, near, dmax, dmin):
    """Alundra in front of facing quadrant q (0 down, 1 up, 2 left, 3 right): within near
    squares sideways and between dmin and dmax squares ahead (e is not used)."""
    q &= 0xFF
    ax, ay, az, dx, dy, dz = rel
    if q == 0:
        if near < ax or dy > 0: return 0
        d = ay
    elif q == 1:
        if near < ax or dy < 0: return 0
        d = ay
    elif q == 3:
        if near < ay or dx > 0: return 0
        d = ax
    elif q == 2:
        if near < ay or dx < 0: return 0
        d = ax
    else:
        return 0
    if dmax < d or d < dmin: return 0
    return 1


def _c46_side(r):
    """Up (0x10) when Alundra is not below it, else down (0)."""
    return 0 if r[4] < 0 else 0x10


@port(0x80074CC0)
def ai_c46(g, e):
    """C46 (twin boss, two halves facing each other across the arena): e drives, its partner
    (Entity address in ai[2..3]) mirrors its animation (table 0x800279E0), direction and
    speed.  Moves up and down, charges, fires sprite 0xF4 bursts and 0xD6 when Alundra is
    between the halves; dies with the partner."""
    s6 = _ent_ptr(g, (e.ai[2] & 0xFFFF) | (e.ai[3] << 16))
    r_e = aihelp.rel_tile(g, e)
    r_6 = aihelp.rel_tile(g, s6)
    if e.px < s6.px:
        e.bytes[2] = 0; s2, s3, r2, r3 = e, s6, r_e, r_6
    else:
        e.bytes[2] = 1; s2, s3, r2, r3 = s6, e, r_6, r_e
    b3 = e.bytes[3]
    a = e.target_anim & M32
    if b3 and a in (0, 3):
        if b3 < 4:
            calls.call(g, 0x80083394, e)
            calls.call(g, 0x80083394, _arg(s6))
            return
        e.target_anim = 0xB; e.flags = s32(e.flags | 0x40)
        s6.anim_done = 0; s6.flags = s32(s6.flags | 0x40)
        return
    fp = 0
    if a in (0, 3):
        t = e.ai[1] & 0xFFFF
        e.target_anim = 3
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return _c46_end(g, e, s6, fp)
        e.target_anim = 2
        if not 0x480000 < s32(s3.px - s2.px) and hi(next_seed(g), 2):
            s = next_seed(g)
            e.target_dir = hi(s, 9) + (4 if s2 is e else 0x14)
            e.bytes[0] = 1; e.ai[1] = 0x50; e.bytes[1] = 7
            return _c46_end(g, e, s6, fp)
        k = hi(next_seed(g), 6)
        if k == 0:
            e.bytes[0] = 1
            s1 = next_seed(g); s = next_seed(g)
            e.bytes[1] = 1
            e.target_dir = g.mem.u8(QDIR + hi(s1, 2))
            e.ai[1] = hi(s, 0x15) + 0x64
        elif k == 1:
            e.bytes[0] = 2
            s = next_seed(g)
            e.bytes[1] = 2
            e.target_dir = hi(s, 0x20)
        elif k in (3, 5):
            e.bytes[0] = 5; _face(g, e); e.ai[1] = 0x3C; e.bytes[1] = 4
        else:
            e.bytes[0] = 5
            if hi(next_seed(g), 2): e.target_dir = hi(next_seed(g), 0x20)
            else: e.target_dir = _c46_side(r_e)
            e.ai[1] = 0x3C; e.bytes[1] = 5
    elif a in (1, 2):
        e.target_anim = 2
        for s, r, q in ((s2, r2, 2), (s3, r3, 3)):
            if facing_range(g, s, r, q, 4, 6, 2):     # Alundra 2-6 squares in front: charge
                e.target_anim = 0x15; e.bytes[0] = 1; e.ai[1] = 0x3C
                p = g.ent[0]
                d = player.dir_from_delta(s32(p.px - s.px), s32(p.py - s.py))
                e.target_dir = d if s is e else (0x20 - d) & 0x1F
                return _c46_end(g, e, s6, fp)
        b = e.bytes[1]
        if b in (0, 7):
            t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
            if (t & 0xFFFF) == 0 or e.force_adjusted or s6.force_adjusted:
                fp = 1; e.target_anim = 3; e.ai[1] = 0x28
        elif b == 2:
            if e.force_adjusted or s6.force_adjusted:
                e.bytes[0] = e.bytes[0] - 1
                if e.bytes[0] == 0:
                    e.target_anim = 3; e.ai[1] = 0x1E
                else:
                    e.target_dir = (e.target_dir + hi(next_seed(g), 7) + 9) & 0x1F
                fp = 1
        elif b in (1, 4, 5):
            if s2.tile_x == s32(s3.tile_x - 0xA) and facing_range(g, s2, r2, 3, 6, 8, 1) \
                    and facing_range(g, s3, r3, 2, 6, 8, 1):
                e.target_anim = 0xF; e.target_dir = _c46_side(r_e)
                return _c46_end(g, e, s6, fp)
            t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
            if (t & 0xFFFF) == 0:
                e.bytes[0] = e.bytes[0] - 1
                if e.bytes[0] == 0:
                    e.target_anim = 3; e.ai[1] = 0x1E
                    return _c46_end(g, e, s6, fp)
                if e.bytes[1] == 4: _face(g, e)
                else:
                    if hi(next_seed(g), 3) and not s32(s3.tile_x - s2.tile_x) < 0xB:
                        v = hi(next_seed(g), 0xF)
                        e.target_dir = v + 0x11 if s2 is e else v + 1
                    else:
                        e.target_dir = hi(next_seed(g), 0x20)
                e.ai[1] = 0x3C; fp = 1
            elif aihelp.sees_player_q(g, s2, r2, 3, 1, 5, 0x100000) or \
                    aihelp.sees_player_q(g, s3, r3, 2, 1, 5, 0x100000):
                e.target_anim = 5; _face(g, e)
            elif not s32(s3.tile_x - s2.tile_x) < 4 and facing_range(g, s2, r2, 3, 4, 5, 2) \
                    and facing_range(g, s3, r3, 2, 4, 5, 2):
                e.target_anim = 0x15
                p = g.ent[0]
                d = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
                s = next_seed(g)
                e.target_dir = d; e.ai[1] = 0x28; e.bytes[0] = hi(s, 3) + 1
            elif e.force_adjusted or s6.force_adjusted:
                fp = 1; e.target_dir = (e.target_dir + 0x10) & 0x1F
    elif a in (4, 5):
        e.target_anim = 5
        if e.anim_done:
            aihelp.start_moving(g, e, 2, 0x1E, 0x3C)
            e.bytes[1] = 0
    elif a in (12, 15):
        e.target_anim = 0xF
        if e.anim_done:                             # both halves fire sprite 0xD6 at each other
            e.target_anim = 0x10; e.ai[1] = 0xB4
            c = _spawn(g, s2, 0xD6, s2.px + 0x300000, s2.py, s2.pz + 0xC0000, 0x18)
            if c is not None: c.target_anim = 1
            c = _spawn(g, s3, 0xD6, s3.px - 0x300000, s3.py, s3.pz + 0xC0000, 0)
            if c is not None: c.target_anim = 1
    elif a in (13, 16):
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.target_anim = 0x10; e.ai[1] = t
        if t % 60 == 0: e.target_dir = _c46_side(r_e)
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 3; e.ai[1] = 0x28
    elif a in (20, 21):
        e.target_anim = 0x15
        if e.anim_done: e.target_anim = 0x13
    elif a in (18, 19):
        e.target_anim = 0x13
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if (t & 7) == 0:                            # a 0xF4 shot from each half
            for s, d, an in ((s2, 0x18, 0x11), (s3, 8, 0xE)):
                c = _spawn(g, s, 0xF4, s.px, s.py, s.pz, d)
                if c is not None:
                    c.bi_e = 0x19; c.bi_a = 0; c.bi_c = 0; c.target_anim = an
                    c.flags = s32(c.flags | 0x40)
        if e.ai[1] & 0xFFFF and not e.force_adjusted: return _c46_end(g, e, s6, fp)
        e.bytes[0] = e.bytes[0] - 1
        if e.bytes[0] and aihelp.sees_player_q(g, s2, r2, 3, 4, 5, 0x100000) and \
                aihelp.sees_player_q(g, s3, r3, 2, 4, 5, 0x100000):
            p = g.ent[0]
            e.target_dir = (player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py)) + 2) & 0x1C
            e.ai[1] = 0x3C
            return _c46_end(g, e, s6, fp)
        e.target_anim = 2
        s = next_seed(g)
        e.target_dir = hi(s, 9) + (4 if s2 is e else 0x14)
        e.ai[1] = 0x3C; e.bytes[1] = 0
    elif a in (6, 9):
        e.target_anim = 9
    elif a in (8, 11):
        e.target_anim = 0xB
    elif a in (7, 10):
        e.target_anim = 0xA
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 3
                e.flags = s32(e.flags & ~3); s6.flags = s32(s6.flags & ~3)
                e.ai[1] = 0x12C; s6.ai[1] = 0x12C; e.ai[5] = 0x1E; s6.ai[5] = 0x1E
            else:
                e.damaged_tick = 0x5A; s6.damaged_tick = 0x5A
                if not s32(s3.tile_x - s2.tile_x) < 0xE and (r2[0] < 3 or r3[0] < 3):
                    e.target_anim = 0x15; e.target_dir = _c46_side(r_e)
                    e.bytes[0] = 1; e.ai[1] = 0x28
                else:
                    e.target_anim = 3; e.ai[1] = 0xA; e.bytes[1] = 0; e.bytes[0] = 0
    _c46_end(g, e, s6, fp)


def _c46_end(g, e, s6, fp):
    """Stop if asked; the partner plays the mirrored animation, faces and moves the mirror way."""
    if fp: e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
    if e.bytes[2] == 0:
        s6.target_anim = g.mem.s16((C46_MIRROR + (e.target_anim << 1)) & M32)
    else:
        s6.target_anim = e.target_anim
        e.target_anim = g.mem.s16((C46_MIRROR + (e.target_anim << 1)) & M32)
    s6.target_dir = (0x20 - e.target_dir) & 0x1F
    s6.py = e.py
    s6.tfy = e.tfy; s6.fy = e.fy; s6.sfy = e.sfy
    s6.tfx = s32(-e.tfx); s6.fx = s32(-e.fx); s6.sfx = s32(-e.sfx)


# ---------------------------------------------------------------- C47 (a 15-segment boss)
C47_INIT = 0x801F0074       # word: 0 = the C47 globals below are cleared on its first frame
C47_POS = 0x80124788        # word: write index of the head's track (0..255)
C47_PHASE = 0x8012478C      # word: phase speed of the coiled body's wave
C47_TX, C47_TY = 0x80124790, 0x80124794     # words: where the head dives back in
C47_TDIR = 0x80124798       # word: the head's direction when it dived (0 = from below)
C47_FROZEN = 0x8012479C     # word: 1 = the body does not follow the track
HIST_DIR = 0x801534C0       # s16[256] direction, s16[256] x and y (16.16 >> 16) of the head's track
HIST_X, HIST_Y = 0x801B6C60, 0x801B6E60
SIN, COS = 0x800282D8, 0x800286D8           # s16[512] wave tables


def _slot(g, k):
    """Entity slot k counted from the table start (past the table: the memory there)."""
    if 0 <= k < L.ENT_COUNT: return g.ent[k]
    return _RawEnt(g, L.ENT_BASE + k * L.ENT_SIZE)


def _abs32(v):
    return s32(-v) if v < 0 else v


@port(0x800762E8)
def ai_c47(g, e):
    """C47 (boss, head of a 15-segment body in slots e.slot..e.slot+14; slots 3-16 follow the
    head's track): roams, coils up and waves, dives under (to 0x80124790) and comes up again
    rebuilding its segments (0x800761C0), drops sprite 0xF9 / 0xF8, and when beaten the
    segments break one by one."""
    m = g.mem
    if m.s32(C47_INIT) == 0:
        for a in (C47_FROZEN, C47_TDIR, C47_TY, C47_TX, C47_PHASE, C47_POS): m.w32(a, 0)
        m.w32(C47_INIT, 1)
    aihelp.rel_tile(g, e)
    if e.ffx or e.ffy:                              # record the head's track
        k = m.s32(C47_POS); o = k * 2
        m.w16((HIST_DIR + o) & M32, e.target_dir)
        m.w16((HIST_X + o) & M32, e.px >> 16)
        m.w32(C47_POS, (k + 1) & 0xFF)
        m.w16((HIST_Y + o) & M32, e.py >> 16)
    i = (m.s32(C47_POS) - 0x54) & 0xFF
    if m.s32(C47_FROZEN) == 0:                      # the body (slots 16..3) follows it
        for k in range(14):
            x = g.ent[16 - k]
            if x.estatus == 2:
                x.target_dir = m.s16(HIST_DIR + i * 2)
                x.px = s32(m.s16(HIST_X + i * 2) << 16)
                x.py = s32(m.s16(HIST_Y + i * 2) << 16)
            i = (i + 6) & 0xFF
    _c47_state(g, e)
    c47_segments(g, e)
    b3 = e.bytes[3]
    if b3 == 0 or not (e.target_anim & M32) < 2: return
    if b3 < 4:
        calls.call(g, 0x80083394, e)
        calls.call(g, 0x80083394, _arg(_slot(g, e.slot + 8)))
        return
    e.delay = s32(e.delay + 1)                      # beaten: a segment (slot bytes[1]) breaks
    if e.delay != 0xA: return                       # every 10 frames
    e.delay = 0
    _slot(g, e.bytes[1]).target_anim = 8
    x = _slot(g, e.bytes[1]); x.flags = s32(x.flags | 0x40)
    e.bytes[1] = e.bytes[1] - 1


def _c47_state(g, e):
    m = g.mem
    a = e.target_anim & M32
    if a in (0, 1):
        e.target_anim = 0
        if e.bytes[3]: return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        if e.bytes[0] == 0:                         # wait for the signal to dive
            if not m.u32(FLAGS_6378) & 1: return
            d = e.target_dir; m.w32(C47_TDIR, d)
            m.w32(C47_TY, s32(e.py + (-0x700000 if d else 0x700000)))
            e.target_anim = 2; m.w32(C47_TX, e.px); e.bytes[0] = 1; e.ai[1] = 6
            return
        b = e.bytes[1]
        if b in (0, 1, 2):
            s = next_seed(g)
            e.target_anim = 2
            e.target_dir = (e.target_dir + hi(s, 9) + 8) & 0x1F
        elif b == 3:                                # head for the dive point
            e.target_anim = 2
            d = player.dir_from_delta(s32(m.s32(C47_TX) - e.px), s32(m.s32(C47_TY) - e.py))
            s = next_seed(g)
            e.target_dir = d
            e.bytes[2] = (1, 3, 0, 1, 3)[hi(s, 5)]
        elif b == 4:
            s = next_seed(g)
            e.target_anim = 2
            if hi(s, 4) == 0: _face(g, e)
            else: e.target_dir = (e.target_dir + (hi(next_seed(g), 9) - 4)) & 0x1F
        elif b == 5:
            _c47_coil(g, e)
        elif b == 7:                                # the segments' sprites recover a quarter HP
            for k in range(14):
                x = _slot(g, e.slot + 1 + k)
                if x.sprite_index in (0x1E9, 0x1EC):
                    hm = x.hp_max
                    x.target_anim = 0xE; x.bytes[3] = 0
                    x.hp = (hm + 3 if hm < 0 else hm) >> 2
            e.bytes[1] = 8; e.ai[1] = 0x40
        elif b == 8:
            e.bytes[1] = 4; e.ai[1] = 0x28
    elif a in (2, 3):
        b0 = e.bytes[0]
        e.target_anim = 2
        if b0 != 0xF:
            c47_rise(g, e, m.s32(C47_TY), m.s32(C47_TDIR))
            return
        b = e.bytes[1]
        if b == 6:                                  # turning round toward delay
            t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
            if t & 0xFFFF: return
            e.target_dir = (e.target_dir + e.item_state) & 0x1F
            e.ai[1] = 4
            if e.target_dir != e.delay: return
            e.ai[1] = 0x3C; e.target_anim = 0; e.bytes[1] = 7
        elif b == 3:                                # going to the dive point
            x0, tx, y0, ty = e.px, m.s32(C47_TX), e.py, m.s32(C47_TY)
            if 0x180000 < _abs32(s32(x0 - tx)) or 0x100000 < _abs32(s32(y0 - ty)):
                e.target_dir = player.dir_from_delta(s32(tx - x0), s32(ty - y0))
                return
            v = e.bytes[2]
            e.target_anim = 0
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            if v == 1:
                m.w32(C47_PHASE, 0); m.w32(C47_FROZEN, v)
            c47_pick(g, e)
        else:
            if not e.force_adjusted: return
            hx, hy = g.ent[16].px, g.ent[16].py
            if ((b - 1) & M32) < 2 and hi(next_seed(g), 3) == 0 and (e.ai[4] & 0xFFFF) < 5:
                _spawn(g, e, 0xF9, hx, hy, e.pz, 0)
            e.ai[1] = 0x3C; e.target_anim = 0
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.bytes[1] = 1 if b == 4 else b + 1
    elif a in (6, 7):
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 0; m.w32(C47_FROZEN, 1)
            for k in range(15):
                x = _slot(g, e.slot + k)
                f = x.flags; x.ai[1] = 0x12C; x.ai[5] = 0x1E; x.flags = s32(f & ~3)
            return
        e.damaged_tick = 0x5A
        b = e.bytes[1]
        e.target_anim = 2
        if b == 6 or (b == 3 and e.bytes[2] == 2): return
        if hi(next_seed(g), 3): e.bytes[1] = 1
        else: e.bytes[1] = 3; e.bytes[2] = 2


def _c47_coil(g, e):
    """bytes[1] 5: the body coils into a ring (bytes[2] 0), then waves (1-4); when the wave
    has died down the track is rewritten as a straight line behind the head."""
    m = g.mem
    if e.bytes[2] == 0:
        same = 0
        for k in range(14):
            prev, cur = _slot(g, e.slot + k), _slot(g, e.slot + 1 + k)
            v1, v0 = prev.delay, cur.delay
            if v1 == v0:
                same += 1
                continue
            d = s32(v1 - v0)
            step = 4 if ((d - 1) & M32) < 0xFF or d < -0x100 else -4
            v = (cur.delay + step) & 0x1FF
            cur.delay = v
            t = m.s16(SIN + cur.delay * 2)
            cur.target_dir = v >> 4
            cur.px = s32(prev.px + t * 0x500)
            u = m.s16(COS + cur.delay * 2)
            cur.py = s32(prev.py - u * 0x500)
        if same == 14: e.bytes[2] = e.bytes[2] + 1
        return
    ph = 0
    for k in range(14):
        prev, cur = _slot(g, e.slot + k), _slot(g, e.slot + 1 + k)
        d = player.dir_from_delta(s32(prev.px - cur.px), s32(prev.py - cur.py))
        ph = m.s32(C47_PHASE)
        mul = s32(ph * (k // 2 + 1))
        cur.target_dir = d
        n = (e.delay + mul) & 0x1FF
        amp = 0x500 + 4 * k
        dx = s32(m.s16(SIN + n * 2) * amp); dy = s32(m.s16(COS + n * 2) * amp)
        cur.px = s32(prev.px + dx)
        cur.py = s32(prev.py - dy)
    b2 = e.bytes[2]
    if b2 == 1:
        v = s32(ph + 1); m.w32(C47_PHASE, v)
        if v == 0x20:
            e.bytes[2] = e.bytes[2] + 1
            core.play_sound(g, 0x10A)
    elif b2 == 2:
        v = s32(ph - 4); m.w32(C47_PHASE, v)
        if v == -0x20: e.bytes[2] = e.bytes[2] + 1
    elif b2 == 3:
        v = s32(ph + 4); m.w32(C47_PHASE, v)
        if v == 0x14: e.bytes[2] = e.bytes[2] + 1
    elif b2 == 4:
        v = s32(ph - 1); m.w32(C47_PHASE, v)
        if v: return
        e.bytes[1] = 4
        td = e.target_dir
        e.ai[1] = 0x28
        m.w32(C47_FROZEN, 0)
        t2 = m.s16((SIN + (td << 5)) & M32); t1 = m.s16((COS + (td << 5)) & M32)
        for j in range(0x55):                       # a straight track behind the head
            k = 0x54 - j; mul = 0xD5 * j
            m.w16(HIST_DIR + 2 * j, e.target_dir)
            m.w16(HIST_X + 2 * k, s32(e.px + s32(t2 * mul)) >> 16)
            m.w16(HIST_Y + 2 * k, s32(e.py - s32(t1 * mul)) >> 16)
        m.w32(C47_POS, 0x55)
        k = e.slot                                  # slots e.slot..16 face its way
        while k != 17:
            if k >= 0x400: raise RuntimeError('C47 above slot 17: the game writes through memory')
            _slot(g, k).target_dir = e.target_dir
            k += 1


@port(0x800761C0)
def c47_rise(g, e, y, flag):
    """C47 coming up from a dive: every 6 frames the next segment (slot e.slot + bytes[0])
    is re-made as map sprite 0xE9-0xEC at (e.px, y +- 0x700000); the 7th also sets
    0x801E6378 bit 1."""
    t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
    if t & 0xFFFF: return
    y2 = s32(y + (0x700000 if flag else -0x700000))
    n = e.bytes[0]
    e.ai[1] = 6
    e.bytes[0] = n + 1
    k = (n - 1) & M32
    if k >= 0xE: return
    if k == 6: g.mem.w32(FLAGS_6378, g.mem.u32(FLAGS_6378) | 2)
    idx = (0xEB, 0xEC, 0xEB, 0xE9, 0xEB, 0xEC, 0xEB, 0xE9, 0xEB, 0xEC, 0xEB, 0xE9, 0xEB, 0xEA)[k]
    x = _slot(g, e.slot + e.bytes[0] - 1)
    calls.call(g, 0x8003A964, _arg(x), e, 1, idx, e.px, y2, e.pz, flag)


@port(0x80075DA4)
def c47_pick(g, e):
    """C47 at its dive point picks what comes next by bytes[2]: 0 roam, 1 coil (segments'
    phase = direction * 16), 2 turn round (bytes[1] 6), 3 drop sprite 0xF8 (ai[1] 0x230)."""
    b = e.bytes[2]
    if b == 1:
        for k in range(15):
            x = _slot(g, e.slot + k)
            x.delay = s32(x.target_dir << 4)
        e.ai[1] = 0x3C; e.bytes[1] = 5; e.bytes[2] = 0
    elif b == 0:
        e.ai[1] = 0x1E; e.bytes[1] = 4
    elif b == 2:
        e.target_anim = 2
        d = e.target_dir
        e.ai[1] = 4; e.bytes[1] = 6
        if d < 8: e.delay = 0; e.target_dir = 0; e.item_state = 1
        elif d < 0x10: e.delay = 0x10; e.target_dir = 0x10; e.item_state = -1
        elif d < 0x18: e.delay = 0x10; e.target_dir = 0x10; e.item_state = 1
        else: e.delay = 0; e.target_dir = 0; e.item_state = -1
    elif b == 3:
        c = _spawn(g, e, 0xF8, e.px, e.py, e.pz, e.target_dir)
        if c is not None: c.ai[1] = 0x230
        e.ai[1] = 0x3C; e.bytes[1] = 4


# per direction band of the segments: (first dir, facing quadrant, +1 to the animation)
_SEG_BANDS = ((2, 0, 1), (6, 2, 0), (10, 2, 1), (14, 1, 0), (18, 1, 1), (22, 3, 0), (26, 3, 1))


@port(0x80075F18)
def c47_segments(g, e):
    """The animations of C47's segments (slots e.slot..e.slot+14, sprites 0x1E8-0x1EC):
    even animation + 1 on diagonal directions, facing quadrant from the direction (the
    animation restarts when the quadrant changes); hit segments (anim 6/7 done) go back to
    anim 0, or 0xA when they are beaten."""
    for i in range(15):
        x = _slot(g, e.slot + i)
        if x.estatus != 2: continue
        if not ((x.sprite_index - 0x1E8) & M32) < 5: continue
        if ((x.target_anim - 6) & M32) < 2 and x.anim_done and i:
            x.target_anim = 0xA if x.bytes[3] else 0
        x.target_anim = x.target_anim & 0xFE
        d = x.target_dir & M32
        if d >= 0x20: continue
        if d < 2 or d >= 30:
            if x.anim_quadrant != 0 or ((x.cur_dir - 2) & M32) < 0x1C: x.cur_anim = -1
            x.anim_quadrant = 0
            continue
        lo, q, odd = _SEG_BANDS[(d - 2) >> 2]
        c = x.cur_dir                               # (the game's cur_dir test here never holds)
        if x.anim_quadrant != q or (c < lo and not c < lo + 4): x.cur_anim = -1
        x.anim_quadrant = q
        if odd: x.target_anim = x.target_anim + 1


# ---------------------------------------------------------------- C81, C82
@port(0x80076F78)
def ai_c81(g, e):
    """C81: bounces around the arena (x 0x78-0x1F8, y 0xA0-0x1E0 px) until its timer runs
    out, then vanishes (anim 2); also vanishes when its parent is beaten (bytes[3])."""
    par = _ent(g, e.parent)
    if par.bytes[3] == 0:
        a = e.target_anim
        if a == 0:
            t = e.ai[1] & 0xFFFF
            if t: e.ai[1] = t - 1
            if not e.force_adjusted: return
            x0 = s32(e.mpx - 0x10000); x1 = s32(e.mpx + e.sizex + 0x10001)
            if not 0x780000 < x0 or 0x1F7FFFF < x1:
                e.target_dir = (0x20 - e.target_dir) & 0x1F
            else:
                y0 = s32(e.mpy - 0x10000); y1 = s32(e.mpy + e.sizey + 0x10001)
                if not 0xA00000 < y0 or 0x1DFFFFF < y1:
                    e.target_dir = (0x10 - e.target_dir) & 0x1F
            if e.ai[1] & 0xFFFF: return
        elif a == 1:
            if not e.anim_done: return
            if not e.bytes[3]:
                e.target_anim = 0
                return
        else:
            return
    e.target_anim = 2; e.flags = s32(e.flags | 0x40)


@port(0x800770BC)
def ai_c82(g, e):
    """C82 (spawner a boss counts in its ai[4]): adds 3 to its parent's ai[4] every 600
    frames; when hit and beaten takes 3 off and goes (anim 3); after anim 4 it throws three
    sprite 0xCA (children of its parent) around itself and is gone (status 3)."""
    a = e.target_anim
    if a == 1:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF == 0: e.target_anim = 4
    elif a == 0:
        if e.ai[1] & 0xFFFF: return
        par = _ent(g, e.parent)
        e.ai[1] = 0x258
        par.ai[4] = (par.ai[4] & 0xFFFF) + 3
    elif a == 2:
        if not e.anim_done: return
        if not e.bytes[3]:
            e.target_anim = 1
            return
        par = _ent(g, e.parent)
        e.target_anim = 3; e.flags = s32(e.flags | 0x40)
        par.ai[4] = (par.ai[4] & 0xFFFF) - 3
    elif a == 4:
        if not e.anim_done: return
        par = e.parent
        e.estatus = 3
        for k in range(3):
            s1 = next_seed(g); s2 = next_seed(g)
            dy = hi(s2, 0x11) << 16; dx = hi(s1, 0x19) << 16
            _spawn(g, par, 0xCA, e.px + dx - 0xC0000, e.py + dy - 0xC0000, e.pz, 0)


# ---------------------------------------------------------------- C48 (the boss with the pit)
C48_ORB = 0x801247A0        # Entity *: the sprite 0xDD it raises (anim 2 + flag 0x40 when done)
C48_PIT = 0x801247A4        # Entity *: global sprite 0xEC at the pit (removed when done)
C48_DROPS = 0x80027BD8      # 9 (x, y) words: where the falling 0xEC land (+ random)
C48_FAN = 0x80027BB4        # 3 x 6 s16: the directions of its 0xDE shots
PIT_X, PIT_Y = 0x3D80000, 0x1380000


def _fx_at(g, a):
    a &= M32
    if L.FX_BASE <= a < L.FX_BASE + L.FX_SIZE * L.FX_COUNT and (a - L.FX_BASE) % L.FX_SIZE == 0:
        return g.fx[(a - L.FX_BASE) // L.FX_SIZE]
    return None


def _remove(g, x):
    """RemoveEntity (0x8003B0C8) on what an Entity pointer word holds (memory when it is
    not an entity record)."""
    if not isinstance(x, _RawEnt): return player.remove_entity(g, x)
    m = g.mem; a = x._b
    sh = m.u32(a + 0x1B8)
    m.w32(a + 0x10, 4); m.w32(a + 0x228, -1)
    if sh:
        f = _fx_at(g, sh)
        if f is not None: f.state = 0
        else: m.w32(sh + 0x68, 0)
        m.w32(a + 0x1B8, 0)
    h = m.u32(a + 0x28)
    if h: _ent_ptr(g, h).carried = None


@port(0x800772D4)
def ai_c48(g, e):
    """C48 (boss): rises (sprite 0xDD) and opens a pit (global sprite 0xEC at 0x3D8, 0x138)
    that sucks Alundra and some sprites (0x1DE, 2, 0xEC, 0x1B2, 0x112) toward it for 1800
    frames while 0xEC rocks fall; whoever reaches the pit is thrown back up (Alundra: anim
    0x56 / 0x58, mode flag 0x20); fires fans of sprite 0xDE.  Stops once e.delay is set."""
    if e.delay != 0: return
    s6 = 0
    mf = g.mode_flags
    p = g.ent[0]
    if mf & 0x20:                                   # Alundra thrown out of the pit
        if p.touching is not None:
            p.target_anim = 0x58; p.target_dir = 0
        elif p.target_anim == 0x58 and p.on_ground:
            p.damaged_tick = 0x78; p.target_anim = 0
            g.mode_flags = mf & ~0x20
    b3 = e.bytes[3]
    if b3 and e.target_anim == 0:
        if b3 < 4:
            calls.call(g, 0x80083394, e)
            return
        e.target_anim = 7
        e.flags = s32((e.flags | 0x40) & ~0x100)
        e.pz = s32(e.pz + 0x200000)
        return
    aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t: e.ai[1] = t - 1
        elif hi(next_seed(g), 2) or e.bytes[2]: e.target_anim = 1
        else: e.target_anim = 5; e.ai[1] = 0x1E
    elif a == 1:
        if e.anim_done:                             # open the pit
            e.target_anim = 2; e.ai[1] = 0x708
            c = _spawn(g, e, 0xDD, e.px, e.py, e.pz, 0)
            g.mem.w32(C48_ORB, entity.ent_addr(c) if c is not None else 0)
            c = entity.spawn_warp_entity(g, e, 0, 0xEC, PIT_X, 0x1480000, e.pz, 0)
            g.mem.w32(C48_PIT, entity.ent_addr(c) if c is not None else 0)
            if c is not None:
                c.target_anim = 2; c.flags = s32(c.flags | 4)
    elif a == 2:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if (t & 3) == 0:                            # 2-3 rocks (global sprite 0xEC) fall
            n = hi(next_seed(g), 2) + 2
            for k in range(n):
                s1 = next_seed(g); s2 = next_seed(g)
                i = e.item_state
                e.item_state = s32(i + 1)
                x = s32(g.mem.s32((C48_DROPS + i * 8) & M32) + (hi(s1, 0x31) << 16))
                y = s32(g.mem.s32((C48_DROPS + 4 + i * 8) & M32) + (hi(s2, 0x21) << 16))
                if not e.item_state < 9: e.item_state = 0
                c = entity.spawn_warp_entity(g, e, 0, 0xEC, x, y, e.pz, 0)
                _ent(g, c).fz = 0x8000
        if e.ai[1] & 0xFFFF == 0:
            e.target_anim = 3; s6 = 1
        else:
            pull = 0xA0 if g.cur_map == 0x7B else 0xB0
            for x in g.ent:                         # the pull of the pit
                si = x.sprite_index
                if not (x is p or si in (0x1DE, 2) or (si == 0xEC and x.target_anim == 0) or si in (0x1B2, 0x112)):
                    continue
                ax, ay = x.px, x.py
                if 0x300000 < _abs32(s32(ax - PIT_X)) or 0x100000 < _abs32(s32(ay - PIT_Y)):
                    d = player.dir_from_delta(s32(PIT_X - ax), s32(PIT_Y - ay)) * 2
                    x.pafx = s32(g.mem.s16(DX + d) * pull)
                    x.pafy = s32(g.mem.s16(DY + d) * pull)
                    continue
                if e.target_anim == 4: continue     # in the pit
                if x is p and not p.anim_flags & 0x40 and p.damaged_tick == 0:
                    s6 = 1
                    p.target_anim = 0x56; e.target_anim = 4
                    g.mode_flags = g.mode_flags | 0x20
                    e.ai[1] = 0x9A; e.ai[4] = 1
                    p.sfy = p.sfx = p.fy = p.fx = p.tfy = p.tfx = 0
                if x.sprite_index in (0x1B2, 0x112):
                    s6 = 1
                    x.target_anim = 0x12; e.target_anim = 4; e.ai[1] = 0x9A; e.ai[4] = 2
    elif a == 3:
        if e.anim_done:
            e.target_anim = 0; e.ai[1] = 0x78; e.bytes[0] = 0
    elif a == 4:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF == 0:               # throw what fell in back up
                core.play_sound(g, 0xB2)
                c = entity.spawn_warp_entity(g, e, 0, 0xEC, p.px, s32(p.py - 0x10000), p.pz, 0)
                if c is not None:
                    c.target_anim = 1; c.flags = s32(c.flags | 2)
                    k = e.ai[4] & 0xFFFF
                    if k == 1:
                        z = e.pz; x0 = p.px
                        p.target_dir = 0x10; p.target_anim = 0; p.pz = z
                        c.px = x0; c.py = p.py; c.pz = p.pz
                    elif k == 2:
                        if g.cur_map == 0x7B: entity.select(g, e, 7)
                        else:
                            entity.select(g, e, 1)
                            c.target_anim = 3
                        x = _ent_ptr(g, g.mem.u32(entity.SEL_LIST))
                        x.pz = e.pz; x.target_anim = 0x10; x.ai[1] = 0x1E; x.target_dir = 0
                        x.bytes[2] = 1
                    e.ai[4] = 0
                else:
                    e.ai[1] = 1
        if e.anim_done:
            e.target_anim = 3; e.ai[1] = 0x78
    elif a == 5:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF == 0:               # a fan of 6 x sprite 0xDE
                core.play_sound(g, 0xB2)
                f = C48_FAN + hi(next_seed(g), 3) * 12
                for k in range(6):
                    c = _spawn(g, e, 0xDE, e.px, e.py + 0x1E0000, e.pz + 0xA0000, g.mem.s16(f + 2 * k))
                    if c is not None:
                        e.bytes[2] = e.bytes[2] + 1
                        c.target_anim = k + 9
        elif e.anim_done:
            s = next_seed(g)
            e.target_anim = 0; e.ai[1] = hi(s, 0x3D) + 0x3C
    elif a == 6:
        if not e.anim_done: pass
        elif e.bytes[3]:
            s6 = 1
            e.ai[1] = 0x12C; e.ai[5] = 0x1E; e.target_anim = 0
            e.flags = s32(e.flags & ~3)
        elif e.bytes[0] < (2 if g.cur_map == 0x7B else 3):
            e.target_anim = 2
        else:
            e.target_anim = 3; s6 = 1
            if g.cur_map == 0x7B and not e.bytes[1] < 0x14:
                entity.select(g, e, 6)
                _remove(g, _ent_ptr(g, g.mem.u32(entity.SEL_LIST)))
                e.delay = 1
    if s6:                                          # close the pit
        o = _ent_ptr(g, g.mem.u32(C48_ORB))
        f = o.flags
        o.target_anim = 2; o.flags = s32(f | 0x40)
        _remove(g, _ent_ptr(g, g.mem.u32(C48_PIT)))


# ---------------------------------------------------------------- C80
@port(0x80077D40)
def ai_c80(g, e):
    """C80 (helper of the boss that is map record 0): wanders, keeping to the lower part of
    the room (y 0x190-0x1B0 px) unless the boss is in anim 2; stops (anim 0) once the boss
    is done (delay) or beaten (bytes[3]); anim 0x10 falls until it lands."""
    entity.select(g, e, 0)
    b = _ent_ptr(g, g.mem.u32(entity.SEL_LIST))
    if b.delay != 0 or b.bytes[3] != 0:
        e.target_anim = 0
        return
    if e.bytes[2] == 0:
        if e.bytes[1]:
            if b.target_anim != 2 and 0x1AFFFFF < e.py:
                e.bytes[1] = 0; e.ai[1] = 0x1E
        elif b.target_anim == 2 or not 0x1900000 < e.py:
            e.bytes[1] = 1
            s = next_seed(g)
            e.target_anim = 0; e.ai[1] = hi(s, 0x20) + 0x14
            return
    a = e.target_anim
    if a == 1:
        if e.bytes[1]: return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF and not e.force_adjusted: return
        s = next_seed(g)
        e.target_anim = 0; e.ai[1] = hi(s, 0x1F) + 0x1E
    elif a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        if e.bytes[1]:
            e.target_anim = 1; e.target_dir = 0
            return
        if e.bytes[0]:
            e.bytes[0] = 0
            s = next_seed(g)
            e.target_anim = 1; e.ai[1] = hi(s, 0x3D) + 0x3C
            return
        s = next_seed(g)
        e.ai[1] = 0x3C
        e.target_dir = g.mem.u8(QDIR + hi(s, 4)); e.bytes[0] = 1
    elif a == 0x10:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF: return
        if e.on_ground: e.target_anim = 0x11
    elif a == 0x11:
        if e.anim_done:
            e.target_anim = 0; e.bytes[2] = 0


# ---------------------------------------------------------------- C49 (the boss that circles)
C49_CX, C49_CY = 0x801247A8, 0x801247AC     # words: centre of the circle it moves on
C49_ANG, C49_END = 0x801247B0, 0x801247B4   # words: angle on the circle (0-0x1FF), last angle
C49_CORNER = 0x801247C0     # word: which of its points (0x80027C3C (x, y) words) it heads for
C49_AIM = 0x801247C4        # word: direction of its breath (toward Alundra)
C49_VX, C49_VY = 0x801247C8, 0x801247CC     # words: push while it leaps at him
C49_LOCK = 0x801247D0       # word: frames until BOSS_LOCK is cleared
C49_FIRE = 0x801247D4       # Entity *: its breath (map sprite 0xE0)
C49_POINTS = 0x80027C3C


def _c49_stop_fire(g):
    calls.call(g, 0x8004A7B4, 0x62)
    c = _ent_ptr(g, g.mem.u32(C49_FIRE))
    f = c.flags
    g.mem.w32(C49_FIRE, 0)
    c.target_anim = 2; c.flags = s32(f | 0x40)


@port(0x800780A4)
def ai_c49(g, e):
    """C49 (boss): walks circles and figure-eights between its points, breathes fire at
    Alundra (sprite 0xE0 while bytes[0] is 6, 0xE1 bursts), leaps at him and lands with a
    quake (0x801F94D0..E0), jumps up and down; dies through 0x80083394."""
    m = g.mem
    if e.delay == 0:
        e.delay = 1
        for a in (0x801247B4, 0x801247B0, 0x801247AC, 0x801247A8, 0x801247C4, 0x801247C0,
                  0x801247BC, 0x801247B8, 0x801247D0, 0x801247CC, 0x801247C8, 0x801247D4):
            m.w32(a, 0)
    t = m.s32(C49_LOCK)
    if t:
        m.w32(C49_LOCK, t - 1)
        if t - 1 == 0: m.w32(BOSS_LOCK, 0)
    p = g.ent[0]
    if e.bytes[0] == 6:                             # breathing fire
        e.item_state = s32(e.item_state + 1)
        if e.item_state & 0xF == 0:
            c = m.u32(C49_FIRE)
            src = _ent_ptr(g, c) if c else e
            m.w32(C49_AIM, player.dir_from_delta(s32(p.px - src.px), s32(p.py - src.py)))
            if e.item_state & 0xF == 0 and e.target_anim == 5:
                n = _spawn(g, e, 0xE0, e.px - 0x1E0000, e.py + 0x200000, e.terrain, 0)
                if n is not None:
                    n.target_anim = 4; n.flags = s32(n.flags | 0x40)
        k = m.s32(C49_AIM) * 2
        vx = m.s16((DX + k) & M32) * 0xA0
        if not (vx < 0 and not 0x900000 < s32(e.mpx - 0x10000)) and \
                not (vx > 0 and 0x20FFFFF < s32(e.mpx + e.sizex + 0x10001)):
            e.pafx = s32(vx)
        k = m.s32(C49_AIM) * 2
        vy = m.s16((DY + k) & M32) * 0xA0
        if not (vy < 0 and not 0x2700000 < s32(e.mpy - 0x10000)) and \
                not (vy > 0 and 0x38FFFFF < s32(e.mpy + e.sizey + 0x10001)):
            e.pafy = s32(vy)
        c = m.u32(C49_FIRE)
        if c:
            f = _ent_ptr(g, c)
            f.px = s32(e.px - 0x1E0000); f.py = s32(e.py + 0x1A0000)
    b3 = e.bytes[3]
    if b3 and e.target_anim == 0:
        if b3 < 4:
            calls.call(g, 0x80083394, e)
            return
        e.target_anim = 8; e.flags = s32(e.flags | 0x40)
        return
    r = aihelp.rel_tile_z(g, e)
    a = e.target_anim & M32
    if a == 0: _c49_idle(g, e, r)
    elif a == 1: _c49_walk(g, e, r)
    elif a == 2:                                    # jumping
        h = s32(e.pz - e.terrain)
        e.ai[1] = ((e.ai[1] & 0xFFFF) + 1) & 0xF
        if 0x9FFFFF < h if e.bytes[0] == 8 else 0x3FFFFF < h:
            e.flags = s32(e.flags & ~0x100)
            b0 = e.bytes[0]
            e.fz = 0
            if b0 == 5:
                s = next_seed(g)
                e.target_anim = 1; m.w32(C49_CORNER, hi(s, 7))
            elif b0 == 8:
                core.play_sound(g, 0x63)
                e.ai[1] = 0x28; e.target_anim = 0
            else:
                e.target_anim = 0; e.ai[1] = 0x3C
            return
        if 0x2FFFFF < h or e.ai[1] & 0xFFFF or e.bytes[0] == 7:
            e.flags = s32(e.flags & ~0x100)
        else:
            e.flags = s32(e.flags | 0x100)
    elif a == 3:                                    # leaping / falling
        if e.bytes[0] == 8:
            n = e.item_state
            if not n < 8:
                qy = _div(s32(r[1] << 20), n)
                qx = _div(s32(r[0] * 3 << 19), e.item_state)
                m.w32(C49_VY, qy); m.w32(C49_VX, qx)
                if not r[3] < 0: m.w32(C49_VX, s32(-qx))
                if not r[4] < 0: m.w32(C49_VY, s32(-qy))
                e.item_state = s32(e.item_state - 1)
            if not 0x900000 < s32(e.mpx - 0x10000) or 0x20FFFFF < s32(e.mpx + e.sizex + 0x10001):
                m.w32(C49_VX, 0)
            elif not 0x2700000 < s32(e.mpy - 0x10000) or 0x3AFFFFF < s32(e.mpy + e.sizey + 0x10001):
                m.w32(C49_VY, 0)
            e.pafx = m.s32(C49_VX); e.pafy = m.s32(C49_VY)
        if e.ai[1] & 0xFFFF == 0 and not 0x200000 < s32(e.pz - e.terrain):
            e.ai[1] = 1
            e.fz = e.fz >> 1
            if e.bytes[0] == 8: e.flags = s32(e.flags & ~0x100)
        if e.on_ground:
            e.ai[1] = 0; e.target_anim = 0
            if e.bytes[0] == 5:
                e.bytes[1] = 0
                e.bytes[0] = 2 if m.s32(C49_CORNER) < 3 else 1
            if e.bytes[0] == 8:                     # landed: quake
                m.w32(C49_VY, 0); m.w32(C49_VX, 0)
                e.ai[1] = 0x1E
                m.w32(C49_LOCK, 0x14)
                m.w32(BOSS_LOCK, 1); m.w32(0x801F94DC, 1); m.w32(0x801F94E0, 1)
                m.w32(0x801F94D4, 2); m.w32(0x801F94D8, 2)
    elif a == 4:
        if not e.anim_done: return
        e.target_anim = 5
        if e.on_ground:
            e.ai[1] = 1; e.bytes[2] = 0
            return
        core.play_sound(g, 0x62)
        c = _spawn(g, e, 0xE0, e.px - 0x1E0000, e.py + 0x1A0000, e.pz - 0x3C0000, 0)
        m.w32(C49_FIRE, entity.ent_addr(c) if c is not None else 0)
        e.ai[1] = 0xF0
    elif a == 5:
        t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
        if t & 0xFFFF: return
        if not e.on_ground:                         # in the air: the breath stops
            calls.call(g, 0x8004A7B4, 0x62)
            c = _ent_ptr(g, m.u32(C49_FIRE))
            e.target_anim = 6
            f = c.flags
            m.w32(C49_FIRE, 0)
            c.target_anim = 2; c.flags = s32(f | 0x40)
            return
        core.play_sound(g, 0x61)
        d = 0x1D
        while True:                                 # a fan of 7 x sprite 0xE1
            c = _spawn(g, e, 0xE1, e.px - 0x1C0000, e.py + 0x200000, e.pz + 0x100000, d)
            if c is not None: c.target_anim = 1
            d = (d + 1) & 0x1F
            if d == 4: break
        e.ai[1] = 0x19
        e.bytes[2] = e.bytes[2] + 1
        if e.bytes[2] == 3: e.target_anim = 6
    elif a == 6:
        if e.anim_done:
            e.target_anim = 0
            if e.on_ground: e.bytes[2] = 0x28
            else: e.bytes[0] = 0
    elif a == 7:
        if m.u32(C49_FIRE): _c49_stop_fire(g)
        if not e.anim_done: return
        if e.bytes[3]:
            e.ai[1] = 0x12C; e.ai[5] = 0x1E; e.target_anim = 0
            e.flags = s32(e.flags & ~3)
            m.w32(BOSS_LOCK, 0)
            e.fz = 0
            return
        e.damaged_tick = 0x5A
        if ((e.bytes[0] - 1) & M32) < 2:
            e.target_anim = 0; e.bytes[2] = 0x28
        else:
            e.target_anim = 2; e.bytes[0] = 0
    elif a == 9:
        if e.anim_done: e.target_anim = 2
    elif a == 10:
        if e.on_ground:
            e.ai[1] = 0
            s = next_seed(g)
            e.flags = s32(e.flags & ~0x100)
            e.target_anim = 2 if hi(s, 3) else 9


def _div(a, b):
    """div: signed, truncated toward zero."""
    q = abs(a) // abs(b)
    return s32(-q if (a < 0) != (b < 0) else q)


def _c49_circle(g, e, mul):
    m = g.mem
    k = m.s32(C49_ANG) * 2
    e.px = s32(m.s32(C49_CX) + s32(m.s16((SIN + k) & M32) * mul))
    e.py = s32(m.s32(C49_CY) - s32(m.s16((COS + k) & M32) * mul))


def _c49_idle(g, e, r):
    m = g.mem
    t = e.ai[1] & 0xFFFF
    if t:
        e.ai[1] = t - 1
        return
    if e.bytes[0] == 8:                             # coming down after the leap
        if 0x9FFFFF < s32(e.pz - e.terrain):
            e.target_anim = 3; e.ai[1] = 0; e.item_state = 0x1C
            e.flags = s32(e.flags | 0x100)
            return
        e.target_anim = 2; e.bytes[0] = 0
        return
    b = e.bytes[2]
    if b:
        e.bytes[2] = b - 1
        b = e.bytes[2]
    if b == 0 and e.on_ground and (r[3] & M32) < 2 and r[4] < 0:
        e.target_anim = 4                           # Alundra just below: breathe
        return
    b0 = e.bytes[0]
    if b0 == 1:                                     # a full circle
        if e.bytes[1] == 0:
            v = s32((m.s32(C49_CORNER) - 3) << 7)
            m.w32(C49_END, v); m.w32(C49_ANG, v)
            e.bytes[1] = 1
            k = m.s32(C49_CORNER) * 8
            m.w32(C49_CX, s32(e.px - m.s32((C49_POINTS + k) & M32) + 0x1500000))
            m.w32(C49_CY, s32(e.py - m.s32((C49_POINTS + 4 + k) & M32) + 0x3100000))
        end = m.s32(C49_END)
        v = (m.s32(C49_ANG) + 2) & 0x1FF
        m.w32(C49_ANG, v)
        if v == end:
            e.bytes[0] = 0; e.target_anim = 2
        _c49_circle(g, e, 0x3000)
        return
    if b0 == 2:                                     # a figure of eight
        b1 = e.bytes[1]
        if b1 == 0:
            c = m.s32(C49_CORNER)
            e.bytes[1] = c + 1
            c = m.s32(C49_CORNER); k = c * 8
            m.w32(C49_CY, s32(e.py - m.s32((C49_POINTS + 4 + k) & M32) + 0x2C00000))
            if c == 0:
                x = m.s32(C49_POINTS); m.w32(C49_ANG, 0x180); add = 0x1080000
            elif c == 1:
                x = m.s32(C49_POINTS + 8); m.w32(C49_ANG, 0x180); add = 0x1980000
            else:
                x = m.s32((C49_POINTS + k) & M32); m.w32(C49_ANG, 0x80); add = 0x1980000
            m.w32(C49_CX, s32(e.px - x + add))
        elif b1 == 1:
            v = (m.s32(C49_ANG) + 4) & 0x1FF; m.w32(C49_ANG, v)
            if v == 0x80:
                if m.s32(C49_CORNER) == 1: e.bytes[0] = 0x80
                m.w32(C49_ANG, 0x180)
                m.w32(C49_CX, s32(m.s32(C49_CX) + 0x900000))
                e.bytes[1] = 2
        elif b1 == 2:
            v = (m.s32(C49_ANG) - 4) & 0x1FF; m.w32(C49_ANG, v)
            if v == 0x80:
                if m.s32(C49_CORNER) == 2: e.bytes[0] = 0x80
                e.bytes[1] = 3
        elif b1 == 3:
            v = (m.s32(C49_ANG) - 4) & 0x1FF; m.w32(C49_ANG, v)
            if v == 0x180:
                m.w32(C49_ANG, 0x80)
                m.w32(C49_CX, s32(m.s32(C49_CX) - 0x900000))
                e.bytes[1] = 4
        elif b1 == 4:
            v = (m.s32(C49_ANG) + 4) & 0x1FF; m.w32(C49_ANG, v)
            if v == 0x180:
                if m.s32(C49_CORNER) == 0: e.bytes[0] = 0x80
                e.bytes[1] = 1
        _c49_circle(g, e, 0x1800)
        if e.bytes[0] == 0x80:
            e.bytes[0] = 0; e.target_anim = 2
        return
    e.bytes[0] = 0                                  # pick a move
    if e.ai[4] & 0xFFFF: k = hi(next_seed(g), 4)
    else: k = 4
    if k in (0, 3):                                 # walk at him
        e.bytes[0] = 4; e.bytes[1] = 5
        n = e.ai[4] & 0xFFFF
        e.target_anim = 1; e.ai[4] = n - 1
        _face(g, e); e.ai[1] = 0x3C
    elif k == 1:                                    # walk about
        e.bytes[0] = 3; e.bytes[1] = 5
        e.ai[4] = (e.ai[4] & 0xFFFF) - 1
        s = next_seed(g)
        e.target_anim = 1; e.ai[1] = 0x3C; e.target_dir = hi(s, 0x20)
    elif k == 2:                                    # go to point 3 and leap
        e.bytes[0] = 8
        n = e.ai[4] & 0xFFFF
        e.target_anim = 1; e.ai[4] = n - 1
        m.w32(C49_CORNER, 3)
    else:                                           # jump, 2-4 moves to come
        s = next_seed(g)
        e.target_anim = 2; e.bytes[0] = 5; e.ai[4] = hi(s, 3) + 2


def _c49_walk(g, e, r):
    m = g.mem
    b0 = e.bytes[0]
    if b0 in (5, 8):                                # heading for a point
        k = m.s32(C49_CORNER) * 8
        dx = s32(e.px - m.s32((C49_POINTS + k) & M32)); dy = s32(e.py - m.s32((C49_POINTS + 4 + k) & M32))
        if 0x60000 < _abs32(dx) or 0x60000 < _abs32(dy):
            e.target_dir = player.dir_from_delta(s32(-dx), s32(-dy))
        elif b0 == 5: e.target_anim = 3
        else: e.target_anim = 2
        return
    t = (e.ai[1] & 0xFFFF) - 1; e.ai[1] = t
    if t & 0xFFFF == 0:
        e.bytes[1] = e.bytes[1] - 1
        if e.bytes[1] == 0:
            e.target_anim = 0; e.ai[1] = 0x3C; e.bytes[0] = 0
            return
        if e.bytes[0] == 3: e.target_dir = hi(next_seed(g), 0x20)
        else: _face(g, e)
        e.ai[1] = 0x3C
        return
    if e.force_adjusted or ((e.px - 0x900000) & M32) > 0x1680000 or ((e.py - 0x2700000) & M32) > 0x1300000:
        d = g.mem.u8(TURN + e.target_dir)
        e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
        e.target_dir = d
        return
    if r[0] < 3 and r[1] < 3:                       # snap at him
        e.target_anim = 0xA
        _face(g, e)
        e.flags = s32(e.flags | 0x100)
        return
    if 0x35FFFFF < e.py: return
    if aihelp.sees_player_q(g, e, r, 0, 3, 5, 0x500000):
        e.bytes[0] = 6; e.item_state = 0; e.target_anim = 4
        p = g.ent[0]
        d = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
        m.w32(C49_AIM, d); e.target_dir = d
