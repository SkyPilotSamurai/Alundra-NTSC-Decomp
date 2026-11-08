"""Helpers the built-in sprite programs share (US ALUN_CD.EXE 0x80082xxx-0x800833xx).
rel = rel_tile(g, e): [|dx|, |dy|, |dz|, dx, dy, dz] (squares; dz in 16.16) of e against Alundra,
the struct the game's AIs keep on the stack."""
from .registry import port
from . import core, player, rodata as R
from .core import s32

M32 = 0xFFFFFFFF
TURN = 0x80028AD8           # u8[32]: the direction turned away (used when a wall stops it)
DX, DY = 0x80023654, 0x80023694


def _rel(dx, dy, dz):
    return [abs(dx), abs(dy), abs(dz), dx, dy, dz]


@port(0x800826F0)
def rel_tile(g, e):
    """Squares between e and Alundra, and floor heights (Entity+0x134)."""
    p = g.ent[0]
    return _rel(e.tile_x - p.tile_x, e.tile_y - p.tile_y, s32(e.floor - p.floor))


@port(0x80082760)
def rel_tile_z(g, e):
    """The same with e's PosZ instead of its floor."""
    p = g.ent[0]
    return _rel(e.tile_x - p.tile_x, e.tile_y - p.tile_y, s32(e.pz - p.floor))


def _hi(seed, n): return (seed * (n & M32)) >> 32


@port(0x800827D0)
def start_moving(g, e, anim, timer, chance):
    """Animation anim (byte), facing Alundra with probability chance/101 (else a random
    direction); timer != 0: AI word 1 = rnd(16) + timer."""
    c = chance & 0xFF
    s = core.next_seed(g)
    if _hi(s, 0x65) < c:
        e.target_dir = player.dir_from_delta(s32(g.ent[0].px - e.px), s32(g.ent[0].py - e.py))
    else:
        e.target_dir = core.next_seed(g) >> 27
    e.target_anim = anim & 0xFF
    if (timer << 16) & M32:
        e.ai[1] = _s16(_hi(core.next_seed(g), 16) + timer)


def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


@port(0x80082914)
def start_moving_half(g, e, anim, timer):
    """Like start_moving with a 1-in-2 chance (bit 19 of the new seed) to face Alundra."""
    s = core.next_seed(g)
    if (s >> 19) & 1:
        e.target_dir = player.dir_from_delta(s32(g.ent[0].px - e.px), s32(g.ent[0].py - e.py))
    else:
        e.target_dir = s >> 27
    e.target_anim = anim & 0xFF
    if (timer << 16) & M32:
        e.ai[1] = _s16(_hi(core.next_seed(g), 16) + timer)


def _turn_back(e, anim):
    e.target_anim = anim & 0xFF
    e.sfy = e.sfx = 0; e.fy = e.fx = 0; e.tfy = e.tfx = 0
    e.target_dir = R.u8(TURN + e.target_dir)


@port(0x80082A30, ret=True)
def ledge_turn(g, e, anim, drop):
    """A floor corner more than drop + 1 below e's floor on the side it faces: stop, turn
    away, play anim; 1 when it turned."""
    a = drop + 1; f = e.floor
    h0, h1, h2, h3 = s32(f - e.mh0), s32(f - e.mh1), s32(f - e.mh2), s32(f - e.mh3)
    d = e.target_dir
    if a < h0 and a < h1 and not ((d - 9) & M32) >= 0xF: _turn_back(e, anim); return 1
    if a < h1 and a < h3 and not ((d - 0x11) & M32) >= 0xF: _turn_back(e, anim); return 1
    if a < h3 and a < h2 and ((d - 8) & M32) >= 0x11: _turn_back(e, anim); return 1
    if a < h2 and a < h0 and d < 0x10: _turn_back(e, anim); return 1
    return 0


@port(0x80082B48, ret=True)
def ledge_ahead(g, e, drop):
    """The test of ledge_turn without acting on it."""
    a = drop + 1; f = e.floor
    h0, h1, h2, h3 = s32(f - e.mh0), s32(f - e.mh1), s32(f - e.mh2), s32(f - e.mh3)
    d = e.target_dir
    if a < h0 and a < h1 and not ((d - 9) & M32) >= 0xF: return 1
    if a < h1 and a < h3 and not ((d - 0x11) & M32) >= 0xF: return 1
    if a < h3 and a < h2 and ((d - 8) & M32) >= 0x11: return 1
    if a < h2 and a < h0 and d < 0x10: return 1
    return 0


def _facing_test(q, rel, near, far, zmax):
    """0x80082E88 / 0x80082D58 body: Alundra within (near, far) squares in front for facing
    quadrant q (0 down, 1 up, 2 left, 3 right) and within zmax height."""
    if zmax < rel[2]: return 0
    if q == 0:
        if near < rel[0] or rel[4] > 0: return 0
        return 0 if far < rel[1] else 1
    if q == 1:
        if near < rel[0] or rel[4] < 0: return 0
        return 0 if far < rel[1] else 1
    if q == 3:
        if near < rel[1] or rel[3] > 0: return 0
        return 0 if far < rel[0] else 1
    if q == 2:
        if near < rel[1] or rel[3] < 0: return 0
        return 0 if far < rel[0] else 1
    return 0


@port(0x80082E88, ret=True)
def sees_player(g, e, rel, near, far, zmax):
    """Alundra in front of e (by its facing quadrant Entity+0x98) within near squares
    sideways and far squares ahead, and within zmax height."""
    return _facing_test(e.anim_quadrant, rel, near, far, zmax)


@port(0x80082D58, ret=True)
def sees_player_q(g, e, rel, q, near, far, zmax):
    """sees_player for a given quadrant."""
    return _facing_test(q & 0xFF, rel, near, far, zmax)


@port(0x80082FB4, ret=True)
def near_in_front(g, e, rel, far, zmax):
    """Alundra close in front of e: within 1 square sideways and far ahead, or adjacent."""
    if zmax < rel[2]: return 0
    q = e.anim_quadrant
    ax, ay, az, dx, dy, dz = rel
    if q == 0:
        if ax >= 2 or dy > 0 or far < ay:
            return 0 if ay >= 2 else (0 if far < ax else 1)
        return 1
    if q == 1:
        if ax >= 2 or dy < 0 or far < ay:
            return 0 if ay >= 2 else (0 if far < ax else 1)
        return 1
    if q == 3:
        if ay < 2 and dx <= 0 and not far < ax: return 1
        return 0 if ax >= 2 else (0 if far < ay else 1)
    if q == 2:
        if ay < 2 and dx >= 0 and not far < ax: return 1
        return 0 if ax >= 2 else (0 if far < ay else 1)
    return 0


@port(0x8003B4A8, ret=True)
def height_ahead(g, e, anim, d):
    """Floor height one step of animation anim ahead in direction d (tile_height_above)."""
    sp = g.anim_speed(e, anim)
    return player.tile_height_above(g, e, R.s16(DX + d * 2) * sp, R.s16(DY + d * 2) * sp)


@port(0x80083154, ret=True)
def step_or_turn(g, e, anim_ok, anim_turn, climb):
    """If the floor one step ahead rises by more than climb (or not at all...): stop and turn
    away with anim_ok; else play anim_turn.  Returns the height difference."""
    a = anim_ok & 0xFF
    h = s32(height_ahead(g, e, a, e.target_dir) - e.floor)
    if climb < h or h <= 0:
        _turn_back(e, a)
    else:
        e.target_anim = anim_turn & 0xFF
    return h
