"""Built-in sprite programs, group 1 (US ALUN_CD.EXE 0x80063930-0x80068F50): A0-A255, C2-C4, C88-C102."""
from .registry import port
from .core import s32, s16, next_seed, hi
from . import aihelp, core, entity, player, calls
from . import layout as L

M32 = 0xFFFFFFFF
TURN = 0x80028AD8           # u8[32]: the direction turned away (wall / ledge)
SPAWN_LOCK = 0x801F0074     # word the A programs clear once they have run


def _put(g, t, name, v):
    """t.name = v; t None (a spawn that failed): the game's store lands at address 0 + the
    field offset (low RAM), as it does on the console."""
    if t is None: g.mem.w32(L.ENTITY[name][0], v)
    else: setattr(t, name, v)


def _w(e, k):
    """lw Entity+0x280+2k: ai[k] | ai[k+1] << 16 (unsigned)."""
    return ((e.ai[k] & 0xFFFF) | (e.ai[k + 1] << 16)) & M32


def _setw(e, k, v, g=None):
    """sw Entity+0x280+2k (v an entity, None or a number); e None: low RAM (see _put)."""
    v = entity.ent_addr(v) if hasattr(v, 'slot') else (0 if v is None else v)
    if e is None: g.mem.w32(0x280 + 2 * k, v); return
    e.ai[k] = v & 0xFFFF; e.ai[k + 1] = (v >> 16) & 0xFFFF


def _bw(e):
    """lw Entity+0x274 (bytes[0..3])."""
    b = e.bytes
    return b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24


def _setbw(e, v):
    """sw Entity+0x274."""
    v &= M32
    e.bytes[0] = v; e.bytes[1] = v >> 8; e.bytes[2] = v >> 16; e.bytes[3] = v >> 24


def _spawn(g, parent, index, x, y, z, d):
    """SpawnWarpEntity(parent, 1 (map sprite), index, x, y, z, direction)."""
    return entity.spawn_warp_entity(g, parent, 1, index, s32(x), s32(y), s32(z), d)


# ---------------------------------------------------------------- A programs (one-shot set-ups)
@port(0x80063930)
def ai_a0(g, e):
    """A0: AI word 0 = the integer part of its height (PosZ >> 16)."""
    e.ai[0] = e.pz >> 16


@port(0x8006393C)
def ai_a1(g, e):
    """A1: start in animation 2."""
    e.target_anim = 2


@port(0x80063948)
def ai_a2(g, e):
    """A2: animation 4 with a random 180-210 frame timer (AI word 1)."""
    s = next_seed(g)
    e.target_anim = 4
    e.ai[1] = hi(s, 0x1F) + 0xB4


@port(0x800639A0)
def ai_a3(g, e):
    """A3: start in animation 4."""
    e.target_anim = 4


@port(0x800639AC)
def ai_a4(g, e):
    """A4: start in animation 9."""
    e.target_anim = 9


@port(0x800639B8)
def ai_a5(g, e):
    """A5: start in animation 7."""
    e.target_anim = 7


@port(0x800639C4)
def ai_a6(g, e):
    """A6: start in animation 3."""
    e.target_anim = 3


@port(0x800639D0)
def ai_a7(g, e):
    """A7: start in animation 9."""
    e.target_anim = 9


@port(0x800639DC)
def ai_a8(g, e):
    """A8: animation 8, byte 0 = 3."""
    e.target_anim = 8
    e.bytes[0] = 3


@port(0x800639F0)
def ai_a9(g, e):
    """A9: start in animation 10."""
    e.target_anim = 0xA


@port(0x800639FC)
def ai_a10(g, e):
    """A10: start in animation 6."""
    e.target_anim = 6


@port(0x80063A08)
def ai_a11(g, e):
    """A11 (map 109): spawns map sprite 0xF5 15 px to the right, linked through AI word 2-3;
    itself animation 3, the new one animation 0."""
    t = _spawn(g, e, 0xF5, e.px + 0xF00000, e.py, e.pz, e.target_dir)
    _setw(e, 2, t)
    _setw(t, 2, 0, g)
    e.target_anim = 3
    _put(g, t, 'target_anim', 0)


@port(0x80063A70)
def ai_a12(g, e):
    """A12 (maps 95, 322): removes the entity in the next slot (15 times over: the game passes
    the same one), clears the three 256-halfword tables at 0x801534C0 / 0x801B6C60 /
    0x801B6E60 and the word 0x801F0074."""
    nxt = g.ent[e.slot + 1]
    for _ in range(15):
        player.remove_entity(g, nxt)
    for i in range(0x100):
        g.mem.w16(0x801534C0 + 2 * i, 0)
        g.mem.w16(0x801B6C60 + 2 * i, 0)
        g.mem.w16(0x801B6E60 + 2 * i, 0)
    g.mem.w32(SPAWN_LOCK, 0)


@port(0x80063B04)
def ai_a14(g, e):
    """A14 (map 324): animation 8; clears 0x801F0074."""
    e.target_anim = 8
    g.mem.w32(SPAWN_LOCK, 0)


@port(0x80063B1C)
def ai_a15(g, e):
    """A15 (map 325): spawns map sprite 0x9D 3.5 px right and 32 below, kept in AI word 2-3;
    clears 0x801F0074."""
    t = _spawn(g, e, 0x9D, e.px + 0x380000, e.py, e.pz - 0x200000, e.target_dir)
    _setw(e, 2, t)
    g.mem.w32(SPAWN_LOCK, 0)


@port(0x80063B84)
def ai_a16(g, e):
    """A16 (map 326): animation 0; clears 0x801F0074."""
    e.target_anim = 0
    g.mem.w32(SPAWN_LOCK, 0)


@port(0x80063B98)
def ai_a17(g, e):
    """A17 (maps 327, 347, 415): animation 14; clears 0x801F0074 and AI word 2-3."""
    e.target_anim = 0xE
    g.mem.w32(SPAWN_LOCK, 0)
    _setw(e, 2, 0)


@port(0x80063BB0)
def ai_a18(g, e):
    """A18: animation 14; clears AI word 2-3."""
    e.target_anim = 0xE
    _setw(e, 2, 0)


@port(0x80063BC0)
def ai_a19(g, e):
    """A19: byte 1 = its program C value (low byte)."""
    e.bytes[1] = e.prog_c


@port(0x80063BCC)
def ai_a20(g, e):
    """A20: bytes 0-3 = its PosZ (the starting height, kept)."""
    _setbw(e, e.pz)


@port(0x80063BD8)
def ai_a21(g, e):
    """A21 (maps 435-438): spawns map sprite 0xD8 on itself in animation 5; itself animation 3,
    moved 16 px up the screen and 48 px higher."""
    t = _spawn(g, e, 0xD8, e.px, e.py, e.pz, e.target_dir)
    _put(g, t, 'target_anim', 5)
    e.target_anim = 3
    e.py = s32(e.py - 0x100000)
    e.pz = s32(e.pz + 0x300000)


@port(0x80063C5C)
def ai_a22(g, e):
    """A22 (map 471): builds two chains of 8 map sprites 0xD1 (x 0x240 / 0x2D0, y 0x260, z 0xF4
    down by 12 each), each linked to the next through AI word 2-3, the head's byte 0 = 0 / 1,
    the others animation 7; sound 0x19C; clears 0x801F0074."""
    e.item_state = 1
    e.delay = 1
    for x, b in ((0x2400000, 0), (0x2D00000, 1)):
        z = 0xF40000
        t = _spawn(g, e, 0xD1, x, 0x2600000, z, 0)
        if t is None: g.mem.w8(0x274, b)
        else: t.bytes[0] = b
        for _ in range(7):
            z = s32(z - 0xC0000)
            n = _spawn(g, e, 0xD1, x, 0x2600000, z, 0)
            _put(g, n, 'target_anim', 7)
            _setw(t, 2, n, g)
            t = n
    core.play_sound(g, 0x19C)
    g.mem.w32(SPAWN_LOCK, 0)


@port(0x80063DBC)
def ai_a254(g, e):
    """A254: nothing."""


@port(0x80063DC4)
def ai_a255(g, e):
    """A255 (the default program of most map objects): sprite 0x1E (chest) opens (animation 1)
    when empty; byte word 2: a follower (AI word 0-1) whose leader left animation 1 falls back
    to status 1, else event 0xB while AI word 4-5 is set; otherwise not collidable, and removed
    when its contents flag is not set; else AI words = -1 / 0 and the delay = the flag."""
    if e.sprite_index == 0x1E:
        if e.contents_item == 0: e.target_anim = 1
        return
    v = _bw(e)
    if v == 1: return
    if v == 2:
        if entity.ent_at(g, _w(e, 0)).target_anim != 1:
            e.estatus = 1
            return
        if _w(e, 4): calls.call(g, 0x8005CB94, 0xB, e)
        return
    e.flags = s32(e.flags & ~0x80)
    f = e.contents_flag
    if f:
        base = 0x801E6378 if f & 0x8000 else 0x801DD334
        word = g.mem.u32(base + (((f & M32) >> 3) & 0xFFC))
        if not word & (1 << (f & 31)):
            player.remove_entity(g, e)
            return
    f = e.contents_flag
    e.item_state = 0
    _setw(e, 0, M32)
    _setw(e, 2, 0)
    e.delay = f


# ---------------------------------------------------------------- C programs
def _get(g, t, name):
    """t.name (a word field); t None: the game reads address 0 + the offset (low RAM)."""
    return g.mem.s32(L.ENTITY[name][0]) if t is None else getattr(t, name)


def _aiu(g, t, k):
    """lhu Entity+0x280+2k of t (t None: low RAM, see _get)."""
    return g.mem.u16(0x280 + 2 * k) if t is None else t.ai[k] & 0xFFFF


@port(0x80065F44)
def ai_c92(g, e):
    """C92: waits (animation 0) until Alundra is within 3 squares and not above it, then
    (sound 0x1D4 unless mode flag 4) animation 1 in direction 5-11; once moving, removed
    when its height passes 0x3BF."""
    r = aihelp.rel_tile(g, e)
    if e.target_anim == 0:
        if r[0] < 4 and r[1] < 4 and r[5] <= 0:
            if not g.mode_flags & 4: core.play_sound(g, 0x1D4)
            s = next_seed(g)
            e.target_anim = 1
            e.target_dir = hi(s, 7) + 5
    elif 0x3BFFFFF < e.pz:
        player.remove_entity(g, e)


@port(0x80066A88)
def ai_c96(g, e):
    """C96 (spawned by its parent): not solid once the parent's AI word 4 is 0; after the first
    frame, stopped by a wall: sprite 0x125 bounces back (direction + 16, speed negated) while
    the parent's word 4 is set, else it is removed; x push = the speed in its delay word."""
    p = e.parent
    if _aiu(g, p, 4) == 0: e.flags = s32(e.flags & ~1)
    if e.bytes[0]:
        if e.force_adjusted:
            if e.sprite_index == 0x125 and _aiu(g, p, 4):
                e.target_dir = (e.target_dir + 0x10) & 0x1F
                e.delay = s32(-e.delay)
            else:
                player.remove_entity(g, e)
        if not e.bytes[0]: e.bytes[0] = 1
    else:
        e.bytes[0] = 1
    e.pafx = e.delay


@port(0x80067400)
def ai_c99(g, e):
    """C99: while game flag bit 0 of 0x801E6378 is clear it goes to animation 16 (and is
    removed when that ends); else waits (anim 0, timer AI word 1) -> anim 16; anim 17 counts
    word 1 down then anim 18 with word 1 = word 4; anim 18 ends -> anim 0."""
    if not g.mem.s32(0x801E6378) & 1 and e.target_anim != 0x10:
        e.target_anim = 0x10
        return
    a = e.target_anim
    if a == 0x10:
        if e.anim_done: player.remove_entity(g, e)
    elif a < 0x11:
        if a == 0:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t: e.target_anim = 0x10
    elif a == 0x11:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            v = e.ai[4]
            e.target_anim = 0x12
            e.ai[1] = v
    elif a == 0x12:
        if e.anim_done: e.target_anim = 0


def _setb(g, t, k, v):
    """t.bytes[k] = v (t None: low RAM, see _put)."""
    if t is None: g.mem.w8(0x274 + k, v)
    else: t.bytes[k] = v


@port(0x80063F08)
def ai_c88(g, e):
    """C88 (map 471, the boss controller): with byte 3 set it finishes the fight (byte 3 = 1:
    death puffs 0x80083394, else game flag bit 0 of 0x801E6378); otherwise in animation 0 two
    countdowns (delay, item_state) each spawn a map sprite 0xD0 at (0xF0, 0xA0) in animation 8
    (byte 0 = 0 facing down / 1 facing left); any other animation, when it ends: byte 3 set ->
    animation 0, timers 300 / 30, not solid, sound 0x55 and the 0x801F94D0 words; else
    animation 0 with 90 frames of damage immunity."""
    b3 = e.bytes[3]
    if b3:
        if e.target_anim == 0:
            if b3 < 2: calls.call(g, 0x80083394, e)
            else: g.mem.w32(0x801E6378, g.mem.u32(0x801E6378) | 1)
            return
    elif e.target_anim == 0:
        if e.delay:
            e.delay = s32(e.delay - 1)
            if not e.delay:
                t = _spawn(g, e, 0xD0, 0xF00000, 0xA00000, 0, 0)
                _setb(g, t, 0, 0); _setb(g, t, 1, 0)
                _put(g, t, 'target_anim', 8)
        if e.item_state:
            e.item_state = s32(e.item_state - 1)
            if not e.item_state:
                t = _spawn(g, e, 0xD0, 0xF00000, 0xA00000, 0, 8)
                _setb(g, t, 0, 1); _setb(g, t, 1, 0)
                _put(g, t, 'target_anim', 8)
        return
    if not e.anim_done: return
    if e.bytes[3]:
        e.ai[1] = 0x12C
        e.ai[5] = 0x1E
        e.target_anim = 0
        e.flags = s32(e.flags & ~3)
        core.play_sound(g, 0x55)
        g.mem.w32(0x801F94D0, 1)
        g.mem.w32(0x801F94DC, 1)
        g.mem.w32(0x801F94E0, 1)
        g.mem.w32(0x801F94D4, 2)
        g.mem.w32(0x801F94D8, 2)
        return
    e.target_anim = 0
    e.damaged_tick = 0x5A


def _cells(e):
    return (e.cell0, e.cell1, e.cell2, e.cell3)


@port(0x80068CE0)
def ai_c4(g, e):
    """C4 (pots, barrels... things Alundra lifts and throws): when its holder lets go
    (flags2 -1: thrown, animation 3 (bi_e 2: flags | 0x10, not collidable); else the
    animation of the table at 0x8002707C) it drops the holder; thrown and stopped by a wall:
    in the air it bounces back once (dust effect 9), on the ground it lands (status 3 over a
    pit / water corner 0x1001); landing (ground or hit): sound 0x18, animation 0 unless a
    corner is 0x1001.  Sprite 0x175 rolls (animation 5) on slope 4."""
    if e.holder is not None:
        f = e.flags2
        if f == 0:
            e.target_anim = 0
            return
        if f == -1:
            e.target_anim = 3
            if e.bi_e == 2: e.flags = s32((e.flags | 0x10) & ~0x80)
        else:
            e.target_anim = g.mem.s32((0x8002707C + (f << 2)) & M32)
        h = e.holder
        e.flags2 = 0
        if h is not None: h.carried = None
        e.holder = None
        return
    a = e.target_anim
    if a != 0 and not (e.sprite_index == 0x175 and a == 5):
        if e.force_adjusted:
            if not e.on_ground:
                if e.fz > 0 and e.delay == 0:
                    e.delay = 1
                    e.target_dir = (e.target_dir + 0x10) & 0x1F
                    core.spawn_effect(g, 0, 9, 0, e.px, e.py, s32(e.pz + 0x80000))
            else:
                for c in _cells(e):
                    if (g.mem.u16(c) & 0x1001) == 0x1001: e.estatus = 3
                e.target_anim = 0
        elif e.on_ground or e.hits:
            core.play_sound(g, 0x18)
            e.delay = 0
            k = 0
            for c in _cells(e):
                if (g.mem.u16(c) & 0x1001) == 0x1001: break
                k += 1
            if k == 4: e.target_anim = 0
    if e.sprite_index == 0x175:
        if e.target_anim == 0 and e.slope_now == 4:
            e.target_anim = 5
            return
        if e.target_anim == 5 and e.slope_now != 4: e.target_anim = 0


def _face_player(g, e):
    """target_dir toward Alundra (dir_from_delta of Alundra - e)."""
    p = g.ent[0]
    e.target_dir = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))


def _turn_back(g, e):
    """Stopped by a wall: forces cleared, direction turned away (table 0x80028AD8)."""
    d = g.mem.u8(TURN + e.target_dir)
    e.sfy = 0; e.sfx = 0; e.fy = 0; e.fx = 0; e.tfy = 0; e.tfx = 0
    e.target_dir = d


@port(0x800685A4)
def ai_c2(g, e):
    """C2 (wandering animals, maps 16, 43, 80-84...): rests (anim 0, 80 frames) then wanders
    (anim 1, turning at walls / ledges); spotting Alundra close in front it stops to look at
    him (anim 13); anim 3 (eating?) puffs dust every 8 frames and, touched by Alundra, runs
    away from him (1 in 3) or rests; landing from anim 6 rests 10-50 frames; anims 7 / 12
    (thrown / hit) end in anim 8 when byte 3 is set, else a rest; anim 11 lands into 10."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    p = g.ent[0]
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t == 0:
            e.ai[1] = 0x50
            e.target_anim = 1
        else:
            e.ai[1] = t - 1
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            aihelp.start_moving(g, e, 1, 0x50, 0x1E)
            e.bytes[0] = 0
            return
        if e.bytes[0] == 0 and aihelp.near_in_front(g, e, r, 2, 0x100000):
            e.target_anim = 0xD
            _face_player(g, e)
            _setw(e, 6, 0)
            return
        if e.force_adjusted: aihelp.step_or_turn(g, e, 1, 4, 0x200000)
        else: aihelp.ledge_turn(g, e, 1, 0x200000)
    elif a == 3:
        n = s32(_w(e, 6) + 1)
        _setw(e, 6, n)
        if not n & 7:
            core.spawn_effect(g, 0, g.mem.u8(g.tile_effects_addr + 0xA), 0, e.px, e.py, e.floor)
        if p.touching is e:
            s = next_seed(g)
            if hi(s, 3) == 0:
                e.target_anim = 1
                e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
                e.ai[1] = 0x3C
                e.bytes[0] = 1
            else:
                e.target_anim = 0
                e.ai[1] = 0x14
        if e.anim_done:
            e.target_anim = 0
            e.ai[1] = 0xA
    elif a == 6:
        if e.on_ground:
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = hi(s, 0x29) + 0xA
    elif a == 7 or a == 12:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 8
                e.flags = s32(e.flags | 0x40)
                return
            if e.target_anim == 0xC: e.target_dir = (e.target_dir + 0x10) & 0x1F
            e.target_anim = 0
            e.ai[1] = 0x1E
            e.bytes[0] = 0
    elif a == 11:
        if e.target_anim == e.cur_anim and e.on_ground: e.target_anim = 0xA


@port(0x800688F8)
def ai_c3(g, e):
    """C3 (hiding creatures, maps 3, 8, 12, 52...): wanders (anims 0 / 1, turning at walls and
    ledges) and when Alundra comes within 2 squares (not just after a turn) faces him
    (anim 3) for 120 frames; touched meanwhile it hides (anim 6, 180-210 frames), else it
    walks on (1 in 3 turning back) for 60; hidden (anim 4) it peeks out (anim 5) on its
    timer or when he is near, then faces him or wanders; anim 8 (hit) ends in anim 2 when
    byte 3 is set, else facing him."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    p = g.ent[0]
    if a == 4:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t: e.target_anim = 5
        if r[0] < 3 and r[1] < 3 and not 0x100000 < r[2]:
            e.target_anim = 5
            e.bytes[1] = 3
    elif a == 5:
        if e.anim_done:
            if e.bytes[1] == 3:
                e.target_anim = 3
                _face_player(g, e)
                e.ai[1] = 0x78
                e.bytes[2] = 0
                e.bytes[1] = 0
            else:
                aihelp.start_moving(g, e, 1, 0x78, 0x14)
    elif a == 0 or a == 1:
        t = e.ai[1] & 0xFFFF
        if t: e.ai[1] = t - 1
        if e.delay: e.delay = s32(e.delay - 1)
        if (e.ai[1] & 0xFFFF) == 0:
            s = next_seed(g)
            e.target_anim = 6
            e.ai[1] = hi(s, 0x1F) + 0xB4
        if e.delay == 0 and r[0] < 3 and r[1] < 3 and not 0x100000 < r[2]:
            _c3_face(g, e)
        elif e.force_adjusted:
            _turn_back(g, e)
        else:
            aihelp.ledge_turn(g, e, 1, 0)
    elif a == 3:
        if p.touching is e: e.bytes[2] = 1
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t: return
        if e.bytes[2]:
            s = next_seed(g)
            e.delay = 0
            e.target_anim = 6
            e.ai[1] = hi(s, 0x1F) + 0xB4
        else:
            s = next_seed(g)
            e.target_anim = 1
            if hi(s, 3) == 0: e.target_dir = (e.target_dir + 0x10) & 0x1F
            e.ai[1] = 0x3C
            e.delay = 0x3C
    elif a == 8:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 2
                e.flags = s32(e.flags | 0x40)
            else:
                _c3_face(g, e)


def _c3_face(g, e):
    e.target_anim = 3
    _face_player(g, e)
    e.ai[1] = 0x78
    e.bytes[2] = 0


FLAGS = 0x801E6378          # game flag words (bit n of word n >> 5); word 0 bits used by the arena


def _ent_ret(g, v):
    """An entity pointer returned by a call (an object, None or a RAM address)."""
    if v is None or hasattr(v, 'slot'): return v
    return entity.ent_at(g, v & M32)


def _seth(g, t, k, v):
    """sh Entity+0x280+2k (t None: low RAM, see _put)."""
    if t is None: g.mem.w16(0x280 + 2 * k, v)
    else: t.ai[k] = v


def _flag_or(g, m): g.mem.w32(FLAGS, g.mem.u32(FLAGS) | m)
def _flag_and(g, m): g.mem.w32(FLAGS, g.mem.u32(FLAGS) & m)


C98_WAVES = 0x80026E28      # s16[20] per round (0x28 bytes): group kinds, 0 = end
C98_GOAL = 0x80026E0C       # s16 per round: kills needed (flag bit 8 when reached)
C98_PICK = 0x80026E18       # (s16 range, s16 base) per random pick (ref & 0x80: base + rnd(range + 1))
C98_GROUPS = {1: (0x80026EF0, 0), 2: (0x80026EF8, 2), 3: (0x80026F1C, 1), 4: (0x80026F40, 1), 6: (0x80026F70, 1)}


@port(0x80067088)
def ai_c98(g, e):
    """C98 (the arena's wave master): while game flag bit 0 runs a round of 1800 frames (round =
    byte 1, reset by flag bit 7): when no map-record entity 4-12 is left alive, after 20 frames
    it spawns the next group of the round (group kind from the wave list 0x80124738: n
    entities from one of the variants of that kind, each a map record 0x8003AAE8 with AI words
    1 and 4 set); at the end of the round the kill count (byte 2) goes to 0x801D7F00, flag
    bit 8 = goal reached, next round, flag bit 0 cleared."""
    f = g.mem.u32(FLAGS)
    if not f & 1: return
    if (e.ai[4] & 0xFFFF) == 0:
        if f & 0x80:
            e.bytes[1] = 0
            _flag_and(g, ~0x80)
        b1 = e.bytes[1]
        e.bytes[2] = 0
        e.item_state = 0
        e.ai[1] = 0
        g.mem.w32(0x80124738, C98_WAVES + b1 * 0x28)
        _flag_and(g, ~0x100)
        e.ai[4] = 1
    t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
    e.ai[1] = t
    if t >= 0x708:
        g.mem.w32(0x801D7F00, e.bytes[2])
        if not e.bytes[2] < g.mem.s16(C98_GOAL + e.bytes[1] * 2): _flag_or(g, 0x100)
        e.ai[4] = 0
        e.bytes[1] = e.bytes[1] + 1
        _flag_and(g, ~1)
        return
    n = g.ent_count
    for i in range(0, n + 1):
        if ((g.ent[i].ref_id - 4) & M32) < 9: return
    if e.delay:
        e.delay = s32(e.delay - 1)
        return
    i = e.item_state
    k = g.mem.s16((g.mem.u32(0x80124738) + (i << 1)) & M32)
    e.item_state = s32(i + 1)
    grp = C98_GROUPS.get(k)
    if grp is None:
        e.item_state = s32(e.item_state - 1)
        return
    rec, m = grp
    s = next_seed(g)
    rec = (rec + s32(k * hi(s, m + 1)) * 6) & M32
    while k:
        ref = g.mem.s16(rec + 2)
        if ref & 0x80:
            s = next_seed(g)
            j = (ref & 0xF) * 4
            ref = s32(g.mem.s16(C98_PICK + 2 + j) + hi(s, g.mem.s16(C98_PICK + j) + 1))
        t = _ent_ret(g, calls.call(g, 0x8003AAE8, e, ref, 1))
        a4 = g.mem.u16(rec + 4)
        a1 = g.mem.u16(rec)
        rec += 6
        k -= 1
        _put(g, t, 'contents_item', 0)
        _seth(g, t, 1, a1)
        _seth(g, t, 4, a4)
    e.delay = 0x14


@port(0x80067A80)
def ai_c101(g, e):
    """C101: wanders around its starting square (kept in AI words 4 / 5 on the first frame;
    flags: | 8, & ~0x2000): rests (anim 0), then walks 300 frames, or 240 back toward home
    (+-4 directions) when 8 squares away; walking it turns to Alundra within 4 squares and
    stops facing him within 2 (anim 0, 80 frames, sound 0xCA at 70 unless mode flag 4);
    walls / ledges turn it, every 64 frames 1 in 3 a random veer; anim 5 lands into 1."""
    if e.bytes[1] == 0:
        x, y = e.tile_x, e.tile_y
        e.bytes[1] = 1
        e.ai[4] = x
        e.ai[5] = y
        e.flags = s32((e.flags & ~0x2000) | 8)
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if e.bytes[0] and ((t - 1) & 0xFFFF) == 0x46 and not g.mode_flags & 4:
                core.play_sound(g, 0xCA)
            return
        dx = s32((e.ai[4] & 0xFFFF) - e.tile_x)
        dy = s32((e.ai[5] & 0xFFFF) - e.tile_y)
        if abs(dx) < 8 and abs(dy) < 8:
            aihelp.start_moving(g, e, 1, 0x12C, 0x14)
            return
        e.target_anim = 1
        d = player.dir_from_delta(s32((dx * 3) << 19), s32(dy << 20))
        s = next_seed(g)
        e.ai[1] = 0xF0
        e.target_dir = (d + hi(s, 9) - 4) & 0x1F
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.target_anim = 0
            e.ai[1] = 0x78
            e.bytes[0] = 0
            return
        if e.bytes[0] == 0 and not 0x200000 < r[2]:
            if r[0] < 3 and r[1] < 3:
                e.target_anim = 0
                _face_player(g, e)
                e.ai[1] = 0x50
                e.bytes[0] = 1
                return
            if r[0] < 5 and r[1] < 5:
                _face_player(g, e)
                return
        if e.force_adjusted:
            aihelp.step_or_turn(g, e, 1, 3, 0x100000)
            return
        if aihelp.ledge_turn(g, e, 1, 0x100000): return
        if e.ai[1] & 0x3F: return
        s = next_seed(g)
        if hi(s, 3): return
        s = next_seed(g)
        e.target_dir = (e.target_dir + hi(s, 9) - 4) & 0x1F
    elif a == 5:
        if e.on_ground: e.target_anim = 1


def _c102_split(g, e, ref, anim, timer, bi_a):
    """Four map records ref (0x8003AAE8) on e, directions 4 / 12 / 20 / 28; byte 1 = 1."""
    d = 4
    for _ in range(4):
        t = _ent_ret(g, calls.call(g, 0x8003AAE8, e, ref, 1))
        if t is not None:
            t.target_anim = anim
            t.px = e.px
            t.py = e.py
            t.target_dir = d
            if bi_a: t.bi_a = 0
            t.ai[1] = timer
            t.pz = e.pz
        d += 8
    e.bytes[1] = 1


@port(0x80067E50)
def ai_c102(g, e):
    """C102 (map 44, slimes that split): rests (anim 0, 60 frames) and crawls (anim 1, veering
    at walls); sprite 0x1CB when its hit animation 3 ends: anim 6 if byte 3 (killed), which
    splits into four map records 0x24 (anim 1); other sprites: hit anim 2 -> anim 3 (killed),
    which splits into four records 0x25 (anim 19); the second split of a piece removes it.
    A hit that does not kill: 90 frames immune, rest 40 frames."""
    if e.bytes[0] == 0:
        e.ai[1] = 0x3C
        e.bytes[0] = 1
    a = e.target_anim
    big = e.sprite_index == 0x1CB
    if a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.target_anim = 0
            e.ai[1] = 0x3C
            return
        if e.force_adjusted:
            s = next_seed(g)
            e.target_dir = (e.target_dir + hi(s, 5) - 0x14) & 0x1F
    elif a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        aihelp.start_moving(g, e, 1, 0x3C, 0x64 if big else 0x14)
    elif (big and a == 3) or (not big and a == 2):
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 6 if big else 3
            return
        e.damaged_tick = 0x5A
        e.target_anim = 0
        e.ai[1] = 0x28
    elif (big and a == 6) or (not big and a == 3):
        if not e.anim_done: return
        if e.bytes[1]:
            player.remove_entity(g, e)
            return
        if big: _c102_split(g, e, 0x24, 1, 0x3C, False)
        else: _c102_split(g, e, 0x25, 0x13, 0x1E, True)


def _abs32(v):
    """bgez / negu: |v| of a 32-bit value (-0x80000000 stays negative)."""
    v = s32(v)
    return s32(-v) if v < 0 else v


@port(0x8006604C)
def ai_c93(g, e):
    """C93 (flying creatures, maps 162-371...): set up on the first frame (anim 10, home =
    delay / item_state = its position, flags | 0x10000, & ~0x80, & ~0x70000 ...); a cry
    (sound 0x192) on a 15-25 / 100-160 frame cycle; hovers (anim 10) and flaps (anim 11, 3-5
    times, new direction 1 in 4, back toward home when 9 / 6 px away); swoops at Alundra
    (anim 12) within 3 squares, returns home when high (anim 13), reappears when he is 14
    squares away."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a < 0xA:
        e.target_anim = 0xA
        e.flags = s32(((e.flags & ~0x80) & 0xFFF8FFFF) | 0x10000)
        e.item_state = e.py
        e.delay = e.px
        return
    if ((a - 0xA) & M32) < 2:
        t = e.ai[4] & 0xFFFF
        if t == 0:
            if r[0] < 9 and r[1] < 9 and not g.mode_flags & 4: core.play_sound(g, 0x192)
            if e.ai[5] & 0xFFFF:
                s = next_seed(g)
                e.ai[5] = 0
                v = hi(s, 0x3D) + 0x64
            else:
                s = next_seed(g)
                e.ai[5] = 1
                v = hi(s, 0xB) + 0xF
        else:
            v = t - 1
        e.ai[4] = v
    a = e.target_anim
    p = g.ent[0]
    if a == 0xA:
        if e.ai[1] & 0xFFFF:
            s = next_seed(g)
            if hi(s, 5) == 0 and (((e.ai[1] & 0xFFFF) - 0x32) & M32) < 0xB and r[0] < 9 and r[1] < 9:
                core.play_sound(g, 0x192)
            e.ai[1] = (e.ai[1] & 0xFFFF) - 1
            if r[0] < 4 and r[1] < 4 and r[5] < 4:
                e.target_anim = 0xC
                e.flags = s32(e.flags & ~0x100)
                e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
            return
        k = 0
        e.target_anim = 0xB
        if e.bytes[0]:
            s = next_seed(g)
            k = hi(s, 4)
        else:
            s = next_seed(g)
            e.bytes[0] = hi(s, 3) + 3
        if k == 0:
            s = next_seed(g)
            e.target_dir = hi(s, 0x20)
        x, hx, y, hy = e.px, e.delay, e.py, e.item_state
        if 0x8FFFFF < _abs32(x - hx) or 0x5FFFFF < _abs32(y - hy):
            e.target_dir = player.dir_from_delta(s32(hx - x), s32(hy - y))
    elif a == 0xB:
        if e.anim_done:
            e.target_anim = 0xA
            b = (e.bytes[0] - 1) & 0xFF
            e.bytes[0] = b
            e.ai[1] = 0x14 if b else 0x64
    elif a == 0xC:
        if 0x3BFFFFF < e.pz:
            hx, hy = e.delay, e.item_state
            e.target_anim = 0xD
            e.fz = 0
            e.px = hx
            e.py = hy
    elif a == 0xD:
        if not r[0] < 0xE:
            e.target_anim = 0xA
            e.pz = 0
            e.flags = s32(e.flags | 0x100)


def _in_attack(g, e):
    """Alundra's attack box (Entity+0x1FC.. / +0x214..) overlaps e's box (+0x1D8.. / +0x1F0..)."""
    p = g.ent[0]
    for m, a, w, sz in ((e.mpx, p.atk_x, p.atk_w, e.sizex), (e.mpy, p.atk_y, p.atk_h, e.sizey),
                        (e.mpz, p.atk_z, p.atk_d, e.sizez)):
        d = s32(m - a)
        if d >= 0:
            if not d < s32(w + 1): return False
        elif not s32(a - m) < s32(sz + 1): return False
    return True


@port(0x80065A38)
def ai_c91(g, e):
    """C91 (critters, maps 162-473...): struck by Alundra's swing (attack box overlap) it cries
    (0x1D6) and flees from him (anim 2, 600 frames); a cry on a 25-35 / 100-160 frame cycle;
    rests (anim 0) and walks (anims 1 / 2: veers 1 in 3 every 64 frames, at walls turns or
    (1 in 2) turns around, ledges of 4); anim 3 lands back into the walk it was in (byte 0)."""
    r = aihelp.rel_tile(g, e)
    if e.target_anim != 2 and _in_attack(g, e):
        core.play_sound(g, 0x1D6)
        e.bytes[0] = 2
        e.target_anim = 2
        p = g.ent[0]
        e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
        e.ai[1] = 0x258
        return
    t = e.ai[4] & 0xFFFF
    if t == 0:
        if r[0] < 9 and r[1] < 9 and not g.mode_flags & 4: core.play_sound(g, 0x1D6)
        if e.ai[5] & 0xFFFF:
            s = next_seed(g)
            e.ai[5] = 0
            v = hi(s, 0x3D) + 0x64
        else:
            s = next_seed(g)
            e.ai[5] = 1
            v = hi(s, 0xB) + 0x19
    else:
        v = t - 1
    e.ai[4] = v
    a = e.target_anim
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        e.bytes[0] = 1
        e.ai[1] = 0x78
        s = next_seed(g)
        e.target_anim = 1
        if hi(s, 3) == 0:
            s = next_seed(g)
            e.target_dir = hi(s, 0x20)
    elif a == 1 or a == 2:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.target_anim = 0
            e.ai[1] = 0x50
            return
        if not t & 0x3F:
            s = next_seed(g)
            if hi(s, 3) == 0:
                s = next_seed(g)
                e.target_dir = (e.target_dir + hi(s, 0xD) - 6) & 0x1F
        if not e.force_adjusted: return
        a = e.target_anim
        e.bytes[0] = a
        aihelp.step_or_turn(g, e, a & 0xFF, 3, 0x200000)
        if e.target_anim == e.bytes[0]:
            s = next_seed(g)
            if hi(s, 2):
                e.target_dir = (e.target_dir + 0x10) & 0x1F
                return
        aihelp.ledge_turn(g, e, e.bytes[0], 0x400000)
    elif a == 3:
        if e.on_ground: e.target_anim = e.bytes[0]


def _ptr(g, v):
    """A pointer a call returned (entity / effect object, None or a RAM address) as an address."""
    if v is None: return 0
    if isinstance(v, int): return v & M32
    for i, f in enumerate(g.fx):
        if f is v: return L.FX_BASE + i * L.FX_SIZE
    return entity.ent_addr(v)


def _fx_obj(g, addr):
    """The effect record at RAM address addr, or None when addr is not one."""
    o = (addr - L.FX_BASE) & M32
    if o < L.FX_SIZE * L.FX_COUNT and o % L.FX_SIZE == 0: return g.fx[o // L.FX_SIZE]
    return None


def _fx_put(g, addr, name, v):
    """Store to field name of the effect record at addr (a pointer kept in RAM / AI words); not
    an effect record (0...): the game's store lands at addr + the offset."""
    f = _fx_obj(g, addr)
    if f is not None: setattr(f, name, v)
    elif L.EFFECT[name][1] == 'u8': g.mem.w8(addr + L.EFFECT[name][0], v)
    else: g.mem.w32(addr + L.EFFECT[name][0], v)


def _fx_get(g, addr, name):
    """Load of field name (a signed word) of the effect record at addr (see _fx_put)."""
    f = _fx_obj(g, addr)
    return getattr(f, name) if f is not None else g.mem.s32(addr + L.EFFECT[name][0])


C97_FLAG = 0x80026D4C       # u32[16]: game flag number of each of the 16 lamps
C97_XY = 0x80026D8C         # (s32 x, s32 y)[16]: where the marker effect goes for each


def _c97_lit(g, k):
    """Game flag C97_FLAG[k] set (flag f: word ((f - 0x8000) >> 5) of 0x801E6378 when bit 15 of
    f - 0x8000 is set, else of 0x801DD334)."""
    f = g.mem.u32((C97_FLAG + (k << 2)) & M32)
    v = (f - 0x8000) & M32
    w = g.mem.u32(((v >> 3) & 0xFFC) + (0x801E6378 if v & 0x8000 else 0x801DD334))
    return w & (1 << ((f + 0x8000) & 31))


# Remake mod "Fixed casino RNG" (not in the game): the wheel lands Red, Blue, Green, Red...
# Lamp colours = the game flag in C97_FLAG (map flags 0x800A red, 0x8014 blue, 0x801E green:
# the switches' scripts on map 474 set them); lamp 0 (flag 0) has no colour.
C97_FIXED_SEQ = (0x0A, 0x14, 0x1E)


def _casino_fixed(g):
    s = getattr(g, 'settings', None)
    return bool(s and s.get('casino_fixed_rng'))


def _c97_fixed_pick(g, e, start):
    """Mod: after the game's own draws (the seed advances exactly as without the mod), the
    round's target becomes the next colour of C97_FIXED_SEQ: the first lamp of that colour at
    least 70 steps (the game's minimum) on from the start lamp.  The position in the sequence
    lives on the loaded map object, so it starts at Red again each time the room is entered."""
    holder = getattr(g, 'map', None) or g
    i = getattr(holder, 'casino_fixed_i', 0)
    holder.casino_fixed_i = i + 1
    want = C97_FIXED_SEQ[i % 3]
    v = 0x46
    while g.mem.u32((C97_FLAG + (((start + v) & 0xF) << 2)) & M32) != want and v < 0x46 + 16:
        v += 1
    e.item_state = v
    e.delay = (start + v) & 0xF
    return 1 if e.delay and _c97_lit(g, e.delay) else 0


@port(0x80066B5C)
def ai_c97(g, e):
    """C97 (a roulette game): owns a map effect record (0x8003CA78(0, 1), kept in AI words 2-3).
    While game flag bit 0 runs: on the first frame of a round it picks a spin length
    (70-74 steps from lamp `delay`, landing on lamp (delay + steps) & 15; from round 4 1 in 3
    a near-miss is nudged, rounds 0-1 1 in 3 helped onto a lit lamp), flag bit 8 = it stops
    on a lamp whose game flag is set; each step moves the effect to the next lamp (sound 0x1C8)
    slowing down near the end; at the end flag bit 0 is cleared, sound 0x1C6 (win) / 0x1C7."""
    if _w(e, 2) == 0:
        _setw(e, 2, _ptr(g, calls.call(g, 0x8003CA78, 0, 1)))
    f = g.mem.u32(FLAGS)
    if not f & 1: return
    if e.bytes[2] == 0:
        if f & 0x80:
            e.bytes[1] = 0
            _flag_and(g, ~0x80)
        s1 = next_seed(g)
        s2 = next_seed(g)
        start = e.delay
        g.mem.w32(0x80124730, e.delay)
        g.mem.w32(0x80124734, hi(s1, 3) + 3)
        e.ai[1] = 0x3C
        e.ai[4] = 0
        v = hi(s2, 5) + 0x46
        e.item_state = v
        e.delay = (e.delay + v) & 0xF
        if e.bytes[1] >= 4:
            s = next_seed(g)
            if hi(s, 3) == 0:
                if e.delay == 1:
                    e.delay = 0
                    e.item_state = s32(e.item_state - 1)
                if e.delay == 0xF:
                    e.delay = 0
                    e.item_state = s32(e.item_state + 1)
        lit = 0
        if e.delay and _c97_lit(g, e.delay):
            lit = 1
        elif e.bytes[1] < 2:
            s = next_seed(g)
            if hi(s, 3) == 0:
                n = (e.delay + 1) & 0xF
                if n and _c97_lit(g, n):
                    lit = 1
                    e.delay = n
                    e.item_state = s32(e.item_state + 1)
        if _casino_fixed(g):                       # F5 > Mods > Fixed casino RNG (remake mod)
            lit = _c97_fixed_pick(g, e, start)
        if lit: _flag_or(g, 0x100)
        else: _flag_and(g, ~0x100)
        e.bytes[2] = 1
    t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
    e.ai[1] = t
    if t: return
    if e.item_state == 0:
        e.bytes[2] = 0
        e.bytes[1] = e.bytes[1] + 1
        f = g.mem.u32(FLAGS)
        g.mem.w32(FLAGS, f & ~1)
        core.play_sound(g, 0x1C6 if f & 0x100 else 0x1C7)
        return
    k = (g.mem.s32(0x80124730) + 1) & 0xF
    fxa = _w(e, 2)
    g.mem.w32(0x80124730, k)
    e.item_state = s32(e.item_state - 1)
    x = g.mem.s32(C97_XY + k * 8)
    y = g.mem.s32(C97_XY + 4 + k * 8)
    e.ai[4] = (e.ai[4] & 0xFFFF) + 1
    _fx_put(g, fxa, 'x', x)
    _fx_put(g, _w(e, 2), 'y', y)
    core.play_sound(g, 0x1C8)
    n = e.item_state
    lim = g.mem.s32(0x80124734)
    c = e.ai[4] & 0xFFFF
    if lim < n and c >= 5: v = 6
    elif c < 5: v = 0x24 - c * 6
    else: v = s32((lim - n) * 8 + 8)
    e.ai[1] = v


class _Raw:
    """An entity pointer that is not an entity record (NULL from a spawn used unchecked, an
    unset link...): the game's word loads / stores land at that address + the field offset,
    as on the console."""
    def __init__(self, g, a):
        object.__setattr__(self, '_g', g); object.__setattr__(self, '_a', a & M32)
    def __getattr__(self, n): return self._g.mem.s32(self._a + L.ENTITY[n][0])
    def __setattr__(self, n, v): self._g.mem.w32(self._a + L.ENTITY[n][0], v)
    def word(self, off): return self._g.mem.u32(self._a + off)


def _as_ent(g, v):
    """An entity pointer (object, None or address) as something to read / write fields of."""
    if v is None: return _Raw(g, 0)
    if not isinstance(v, int): return v
    o = (v - L.ENT_BASE) & M32
    if o < L.ENT_SIZE * L.ENT_COUNT and o % L.ENT_SIZE == 0: return g.ent[o // L.ENT_SIZE]
    return _Raw(g, v)


def _link(g, t):
    """lw Entity+0x284 (the next one of a chain) of t."""
    return _as_ent(g, t.word(0x284) if isinstance(t, _Raw) else _w(t, 2))


def _spawn_rec(g, e, ref):
    """SpawnMapEntity(e, ref, 1) (0x8003AAE8, not ported): the map record ref as a child of e,
    used unchecked (NULL: _Raw)."""
    return _as_ent(g, calls.call(g, 0x8003AAE8, e, ref, 1))


C95_LANES = 0x80026CFC      # s16[4] per pattern (6 patterns): bit 0 upper lane, bit 1 from the right
C95_SPEED = 0x80026D2C      # s32 per round: base speed of the targets
C95_GOAL = 0x80026D40       # s16 per round: hits needed


@port(0x80066544)
def ai_c95(g, e):
    """C95 (the shooting gallery master): while game flag bit 0 runs a round of 0x744 frames
    (round = byte 1): it sends targets (map record 2, every 120 / 100 / 120 / 80 frames as the
    round goes on) along lanes from the pattern table (a new random pattern of 4 every 4
    targets), rounds 1-2 also a moving record 0 at the start, from round 3 extra record-1
    targets every 140-160 (180-200 in round 3) frames; at the end the hits (byte 2) minus
    misses (byte 0) go to 0x801D7F00.. and flag bit 8 = the round's goal was reached; next
    round, flag bit 0 cleared."""
    if not g.mem.u32(FLAGS) & 1: return
    if (e.ai[4] & 0xFFFF) == 0:
        b1 = e.bytes[1]
        e.ai[1] = 0
        e.bytes[2] = 0
        e.bytes[0] = 0
        v = g.mem.u32((C95_SPEED + (b1 << 2)) & M32)
        e.ai[4] = 1
        g.mem.w32(0x80124728, 0)
        g.mem.w32(0x80124724, v)
        e.delay = 0x64
        if ((e.bytes[1] - 1) & M32) < 2:
            t = _spawn_rec(g, e, 0)
            t.target_dir = 0x18
            t.delay = 0x20000 if e.bytes[1] == 1 else 0x28000
        _flag_and(g, ~0x100)
    kind = 0
    e.ai[1] = (e.ai[1] & 0xFFFF) + 1
    d = s32(e.delay + 1)
    c = e.ai[1] & 0xFFFF
    e.delay = d
    if c < 0x258:
        kind = 0 if d < 0x78 else 2
    else:
        if c < 0x3C0: early = d < 0x64
        elif c < 0x4EC: early = d < 0x78
        elif c < 0x744: early = d < 0x50
        else:
            b2 = e.bytes[2]
            g.mem.w32(0x801D7F00, b2)
            b0 = e.bytes[0]
            n = b2 - b0
            g.mem.w32(0x801D7F04, b0)
            if n < 0: n = 0
            g.mem.w32(0x801D7F08, n)
            if not n < g.mem.s16(C95_GOAL + e.bytes[1] * 2): _flag_or(g, 0x100)
            e.ai[4] = 0
            e.bytes[1] = e.bytes[1] + 1
            _flag_and(g, ~1)
            return
        if not early: kind = 2
    if kind:
        t = _spawn_rec(g, e, kind)
        t.contents_item = 0
        t.flags = s32((t.flags & 0xFFF8FFFF) | 0x30000)
        k = g.mem.s32(0x80124728)
        e.delay = 0
        if k == 0:
            s = next_seed(g)
            g.mem.w32(0x80124728, 3)
            g.mem.w32(0x8012472C, hi(s, 6))
        else:
            g.mem.w32(0x80124728, k - 1)
        lane = g.mem.s16((C95_LANES + (g.mem.s32(0x8012472C) << 3) + (g.mem.s32(0x80124728) << 1)) & M32)
        if lane & 1:
            t.pz = s32(t.pz + 0x180000)
            t.delay = s32(g.mem.s32(0x80124724) + 0x14000)
            if not lane & 2: t.target_dir = 0x18
            else:
                t.target_dir = 8
                t.py = s32(t.py - 0x100000)
        else:
            t.delay = s32(g.mem.s32(0x80124724) + 0x12000)
            if not lane & 2: t.target_dir = 8
            else:
                t.target_dir = 0x18
                t.py = s32(t.py - 0x100000)
        if t.target_dir == 8:
            t.px = s32(t.px + 0xF00000)
            t.delay = s32(-t.delay)
    if e.bytes[1] < 3 or (e.ai[1] & 0xFFFF) < 0x3C: return
    if e.item_state:
        e.item_state = s32(e.item_state - 1)
        return
    s = next_seed(g)
    a = hi(s, 0xB) * 2
    e.item_state = a + 0x8C
    if e.bytes[1] == 3: e.item_state = a + 0xB4
    t = _spawn_rec(g, e, 1)
    s = next_seed(g)
    t.contents_item = 0
    lane = g.mem.s16((C95_LANES + (g.mem.s32(0x8012472C) << 3)
                      + (((g.mem.s32(0x80124728) + hi(s, 4)) & 3) << 1)) & M32)
    t.flags = s32((t.flags & 0xFFF8FFFF) | 0x30000)
    if lane & 1: t.pz = s32(t.pz + 0x180000)
    if lane & 2: t.target_dir = 8
    t.delay = 0x22000
    if t.target_dir == 8:
        t.px = s32(t.px + 0xF00000)
        t.delay = s32(-t.delay)


C100_GATES = 0x8012473C     # Effect *[4]: the four gate effects C100 creates
C100_SRC = 0x8012474C       # Effect *[4]: the map's effects playing sprite animations 0-3


@port(0x80067504)
def ai_c100(g, e):
    """C100 (a scrolling sequence): on the first frame finds the map effects playing sprite
    animations 0-3 (0x8012474C..), creates four map effects 4 (x 0x1E0, y 0xA8 + 0x70 k,
    z 0x30) and becomes not collidable; while game flag bit 0 runs: the first time anim 1,
    then every frame the vertical scroll change (0x801EF438, << 16) moves all other live
    effects (flag bit 1 when it moved), the gates open (byte 0x70) at frame 0x130 and at 0x180
    flag bit 2, anim 0, byte 1 = 1; 7 frames in 8 it puffs a pair of map effects 5 (every
    6th time 6, flying sideways) near effects 0 / 2 and 1 / 3."""
    if e.bytes[0] == 0:
        e.bytes[0] = 1
        for k in range(L.FX_COUNT):
            f = g.fx[k]
            if f.state != 2: continue
            a = L.FX_BASE + k * L.FX_SIZE
            if f.spr_anim == 0: g.mem.w32(C100_SRC, a)
            if f.spr_anim == 1: g.mem.w32(C100_SRC + 4, a)
            if f.spr_anim == 2: g.mem.w32(C100_SRC + 8, a)
            if f.spr_anim == 3: g.mem.w32(C100_SRC + 12, a)
        y = 0xA80000
        for k in range(4):
            a = _ptr(g, calls.call(g, 0x8003CA78, 4, 1))
            if a:
                g.mem.w32(C100_GATES + 4 * k, a)
                _fx_put(g, a, 'y', y)
                y = s32(y + 0x700000)
                _fx_put(g, a, 'x', 0x1E00000)
                _fx_put(g, a, 'z', 0x300001)
        g.mem.w32(0x8012475C, 0)
        e.flags = s32(e.flags & ~0x80)
    f0 = g.mem.u32(FLAGS)
    if not f0 & 1: return
    if e.bytes[1] == 0:
        if e.target_anim == 0:
            e.target_anim = 1
            e.target_dir = 0
            g.mem.w32(0x8012475C, g.mem.u32(0x801EF438))
        else:
            v = g.mem.u32(0x801EF438)
            dy = s32((v - g.mem.u32(0x8012475C)) << 16)
            g.mem.w32(0x8012475C, v)
            if dy: g.mem.w32(FLAGS, f0 | 2)
            for k in range(L.FX_COUNT):
                f = g.fx[k]
                if f.state != 2: continue
                a = L.FX_BASE + k * L.FX_SIZE
                if a in (g.mem.u32(C100_GATES), g.mem.u32(C100_GATES + 4), g.mem.u32(C100_GATES + 8),
                         g.mem.u32(C100_GATES + 12)): continue
                f.y = s32(f.y + dy)
            t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
            e.ai[1] = t
            if t == 0x130:
                for k in range(4): _fx_put(g, g.mem.u32(C100_GATES + 4 * k), 'b70', 1)
            if (e.ai[1] & 0xFFFF) == 0x180:
                _flag_or(g, 4)
                e.target_anim = 0
                e.bytes[1] = 1
                e.ai[1] = 0
    e.delay = s32(e.delay + 1)
    if not e.delay & 7: return
    kind = 5
    if e.item_state == 0:
        kind = 6
        e.item_state = 6
    e.item_state = s32(e.item_state - 1)
    for k in range(2):
        for src, ox, vx in ((C100_SRC, 0x400000, -0x4000), (C100_SRC + 8, -0x580000, 0x4000)):
            a = _ptr(g, calls.call(g, 0x8003CA78, kind, 1))
            if not a: continue
            s1 = next_seed(g)
            s2 = next_seed(g)
            p = g.mem.u32(src + 4 * k)
            _fx_put(g, a, 'x', s32(_fx_get(g, p, 'x') + ((hi(s1, 5) << 19) + ox)))
            _fx_put(g, a, 'y', s32(_fx_get(g, p, 'y') - (hi(s2, 0xF) << 19) + 0xA00000))
            _fx_put(g, a, 'z', s32(_fx_get(g, p, 'z') + 0xA00000))
            if kind == 6:
                _fx_put(g, a, 'vz', 0x4000)
                _fx_put(g, a, 'vx', vx)


ARMS = 0x801246E4           # the boss's two arms, 0x20 bytes each (C90, byte 0 = which):
#   +0 s32 x swing, +4 s32 y swing, +8 s32 z reach, +0xC/+0xE/+0x10 s16 wave phases (x / y / z),
#   +0x14 s32 x offset, +0x18 s32 y offset, +0x1C s16 state (2: sweeping)
ARM_X0 = 0x80026CEC         # s32[2]: x of each arm's root
ARM_BX = 0x80026CF4         # s32[2]: resting x offset of each arm
WAVE_X = 0x800282D8         # s16[512] wave tables
WAVE_Y = 0x800286D8


def _d128(v):
    """bgez / addiu 0x7F / sra 7: v / 128 rounded toward zero."""
    return (v + 0x7F if v < 0 else v) >> 7


def _c90_next(g, e, boss):
    """Next step; its timer 70 frames when the boss is below half its life, else 100."""
    e.bytes[2] = e.bytes[2] + 1
    m = boss.hp_max
    e.ai[1] = 0x46 if boss.hp < (s32(m + ((m & M32) >> 31)) >> 1) else 0x64


def _c90_pull(g, e, rec, side, v):
    """Timer = v; the arm pulls in (x offset toward 0, y offset up, x swing down)."""
    m = g.mem
    e.ai[1] = v
    x = m.s32(rec + 0x14)
    if x: m.w32(rec + 0x14, x + (-0x10000 if side else 0x10000))
    y = m.s32(rec + 0x18)
    if y: m.w32(rec + 0x18, y - 0x40000)
    w = m.s32(rec)
    if w: m.w32(rec, w - 0x80)


def _c90_rest(g, rec, side):
    """The arm moves back toward its resting shape."""
    m = g.mem
    x = m.s32(rec + 0x14); b = m.s32((ARM_BX + (side << 2)) & M32)
    if x != b: m.w32(rec + 0x14, x + (0x40000 if x < b else -0x40000))
    y = m.s32(rec + 0x18)
    if y != 0x200000: m.w32(rec + 0x18, y + 0x20000)
    w = m.s32(rec)
    if w != 0x600: m.w32(rec, w + 0x80)


def _c90_fold(g, e, dz):
    """Segment AI word 4 of the chain plays animation 8, then 7; when the last one is done:
    next step, effect 0 of the global bank dz above e."""
    t = e
    for _ in range(e.ai[4] & 0xFFFF): t = _link(g, t)
    if t.target_anim != 8:
        t.target_anim = 8
        return
    if not t.anim_done: return
    t.target_anim = 7
    n = ((e.ai[4] & 0xFFFF) - 1) & 0xFFFF
    e.ai[4] = n
    if n: return
    e.bytes[2] = e.bytes[2] + 1
    core.spawn_effect(g, 1, 0, 0, e.px, e.py, s32(e.pz + dz))


@port(0x80064E14)
def ai_c90(g, e):
    """C90 (map 471 boss, its two arms: a chain of 8 segments linked through AI word 2-3, the
    first one running this): the first one to run sets up both arm records (0x801246E4); each
    frame it lays the 8 segments out along the arm's waves (x / y / z tables, tapering toward
    the tip); it turns its hand toward Alundra.  When the boss's life is 0 the segments
    become harmless.  When game flag bit 1 is set it attacks (byte 1): 1 grab (Alundra close
    in front: reach toward him, slam with screen shake), 2 sweep (he is below it and the
    other arm is not sweeping: fold up, fire 10 shots 0xD0), 3 (close but not in front: fold,
    fire 5 spread shots); then the arm returns to rest (byte 1 = 0)."""
    m = g.mem
    if m.s32(SPAWN_LOCK) == 0:
        for k in range(2):
            r = ARMS + 0x20 * k
            m.w32(r, 0x600); m.w32(r + 4, 0); m.w32(r + 8, 0x2200)
            m.w16(r + 0xC, 0); m.w16(r + 0xE, 0); m.w16(r + 0x10, 0)
            m.w32(r + 0x18, 0x200000); m.w16(r + 0x1C, 0)
            m.w32(r + 0x14, m.s32(ARM_BX + 4 * k))
        m.w32(SPAWN_LOCK, 1)
    if ((e.target_anim - 7) & M32) < 2: return
    side = e.bytes[0]
    rec = (ARMS + (side << 5)) & M32
    x0 = m.s32((ARM_X0 + (side << 2)) & M32)
    ph = m.s16(rec + 0xC)
    wy = (WAVE_Y + (m.s16(rec + 0xE) << 1)) & M32
    wz = (WAVE_Y + (m.s16(rec + 0x10) << 1)) & M32
    t = e
    for k in range(8):
        q = ((7 - k) << 7) // 7
        v = s32(m.s32(rec + 0x14) + s32(m.s16((WAVE_X + (ph << 1)) & M32) * m.s32(rec)))
        t.px = s32(x0 + _d128(s32(v * q)))
        v = s32(m.s32(rec + 0x18) + s32(m.s16(wy) * m.s32(rec + 4)))
        t.py = s32(0x2600000 + _d128(s32(v * q)))
        v = _d128(s32(m.s32(rec + 8) * q))
        ph = (ph + 0x40) & 0x1FF
        t.pz = s32(0xA00000 + s32(m.s16(wz) * v))
        t = _link(g, t)
    turn = 0; reset = 0
    m.w16(rec + 0xC, (m.u16(rec + 0xC) + 2) & 0x1FF)
    par = e.parent
    boss = _as_ent(g, par)
    p = g.ent[0]
    d = player.dir_from_delta(s32(p.px - x0), s32(s32(p.py + 0x80000) - 0x2600000))
    if boss.hp == 0:
        t = e
        for _ in range(8):
            t.flags = s32(t.flags & ~3)
            t = _link(g, t)
        return
    behind = ((d - 6) & M32) < 0x15        # Alundra not in front of the hand (directions 6-26)
    b1 = e.bytes[1]
    if b1 == 0:
        r = aihelp.rel_tile(g, e)
        turn = 1
        if not g.mode_flags & 0x20 and m.u32(FLAGS) & 2:
            if not behind and r[1] < 5 and r[0] < 5:
                e.bytes[1] = 1
                dx = m.s16((0x80023654 + (d << 1)) & M32)
                e.bytes[2] = 0
                e.ai[1] = 0x18
                e.delay = s32(((dx * 9) << 10) & 0xFFF80000)
            elif not behind and r[0] < 7 and r[1] < 7:
                e.bytes[1] = 3
                e.bytes[2] = 0
                e.ai[1] = 0x18
            elif r[4] < 0 and m.s16((ARMS + 0x1C + ((side ^ 1) << 5)) & M32) != 2:
                e.bytes[1] = 2
                m.w16(rec + 0x1C, 2)
                e.bytes[2] = 0
                e.ai[1] = 0x18
    elif b1 == 1:
        b2 = e.bytes[2]
        if b2 == 1:
            n = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = n
            if n == 0:
                e.ai[1] = 0x14
                e.bytes[2] = b2 + 1
                m.w32(0x801F94D0, 1); m.w32(0x801F94DC, 1); m.w32(0x801F94E0, 1)
                m.w32(0x801F94D4, 2); m.w32(0x801F94D8, 2)
            else:
                x = m.s32(rec + 0x14)
                if x < e.delay:
                    m.w32(rec + 0x14, x + 0x80000)
                    x = m.s32(rec + 0x14)
                if e.delay < x: m.w32(rec + 0x14, x - 0x80000)
                v = m.s16(rec + 0xE)
                if v: m.w16(rec + 0xE, (v + 8) & 0x1FF)
                v = m.s16(rec + 0x10)
                if v != 0x80: m.w16(rec + 0x10, (v + 8) & 0x1FF)
        elif b2 == 0:
            n = e.ai[1] & 0xFFFF
            if n: _c90_pull(g, e, rec, side, n - 1)
            else:
                core.play_sound(g, 0x19E)
                e.ai[1] = 0x1A
                e.bytes[2] = e.bytes[2] + 1
                m.w16(rec + 0xE, 0x180); m.w32(rec + 4, 0x3000); m.w16(rec + 0x10, 0)
        elif b2 == 2:
            n = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = n
            if n == 0:
                m.w32(0x801F94D0, 0)
                _c90_next(g, e, boss)
        elif b2 == 3:
            n = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = n
            if n == 0: reset = 1
            else:
                v = m.s16(rec + 0xE)
                if v != 0x180: m.w16(rec + 0xE, (v - 4) & 0x1FF)
                v = m.s16(rec + 0x10)
                if v: m.w16(rec + 0x10, (v - 4) & 0x1FF)
                _c90_rest(g, rec, side)
    elif b1 == 2:
        b2 = e.bytes[2]
        if b2 == 1: _c90_fold(g, e, 0x100000)
        elif b2 == 0:
            n = e.ai[1] & 0xFFFF
            if n: _c90_pull(g, e, rec, side, n - 1)
            else:
                a = e.target_anim
                e.bytes[2] = b2 + 1
                e.ai[4] = 7
                e.delay = 0
                e.target_anim = 6 if a == 0 else 5
        elif b2 == 2:
            n = e.ai[1] & 0xFFFF
            if n: e.ai[1] = n - 1
            else:
                e.ai[1] = 0x14
                core.play_sound(g, 0x19F)
                c = entity.spawn_warp_entity(g, par, 1, 0xD0, e.px, e.py, e.pz, e.target_dir)
                core.spawn_effect(g, 1, 0, 1, e.px, e.py, s32(e.pz + 0x100000))
                if c is not None:
                    c.target_anim = 0xF
                    c.fz = 0x40000
                    c.bytes[0] = 1
                    c.flags = s32(c.flags & ~1)
                    e.delay = s32(e.delay + 1)
                    if e.delay == 0xA: _c90_next(g, e, boss)
        elif b2 == 3:
            n = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = n
            if n == 0: reset = 1
            else:
                turn = 1
                _c90_rest(g, rec, side)
    elif b1 == 3:
        b2 = e.bytes[2]
        if b2 == 1: _c90_fold(g, e, 0)
        elif b2 == 0:
            e.ai[4] = 7
            e.bytes[2] = e.bytes[2] + 1
        elif b2 == 2:
            turn = 1
            n = e.ai[1] & 0xFFFF
            if n: e.ai[1] = n - 1
            else:
                e.ai[1] = 0xF
                y = s32(e.py + 0x80000); z = s32(e.pz - 0x80000)
                core.play_sound(g, 0x19F)
                c = entity.spawn_warp_entity(g, par, 1, 0xD0, e.px, y, z, e.target_dir)
                core.spawn_effect(g, 1, 0, 1, e.px, e.py, e.pz)
                if c is not None:
                    c.bytes[0] = 2
                    c.target_anim = s32(e.target_anim + 0xA)
                    c.flags = s32((c.flags & ~1) | 0x100)
                    c.bytes[1] = (e.ai[4] & 0xFF) + 2
                    n = ((e.ai[4] & 0xFFFF) + 1) & 0xFFFF
                    e.ai[4] = n
                    if n == 5: _c90_next(g, e, boss)
        elif b2 == 3:
            n = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = n
            if n == 0: reset = 1
    if turn:
        if not behind: e.target_dir = d
        if d < 2 or d == 0x1F: e.target_anim = 0
        elif d < 4: e.target_anim = 1
        elif d < 0x10: e.target_anim = 2
        elif d >= 0x1D: e.target_anim = 3
        elif d >= 0x11: e.target_anim = 4
    if reset:
        m.w32(rec + 0x18, 0x200000)
        b = m.s32((ARM_BX + (side << 2)) & M32)
        m.w32(rec, 0x600); m.w32(rec + 4, 0)
        m.w16(rec + 0xE, 0); m.w16(rec + 0x10, 0)
        m.w32(rec + 0x14, b)
        e.bytes[1] = 0
        m.w16(rec + 0x1C, 0)


HANDS = 0x80124698          # the boss's two hands, 0x24 bytes each (C89, byte 0 = which):
#   +0 s32 x push, +4 s32 y push, +8 / +0xC s32 home (circle centre) x / y, +0x10 / +0x14 s32
#   position x / y, +0x18 s32 grab state (1 grabbing Alundra, 2 holding him), +0x1C / +0x20
#   s32 where Alundra was when it lunged
HAND_X = 0x80026C98         # s32[2]: home x of each hand
HAND_STEP = 0x80026CA0      # s32[2]: circling speed (wave phase step) of each hand
DX, DY = 0x80023654, 0x80023694     # s16[32]: unit vector of each direction
GRABBED = 0x801246E0        # Entity *: the copy of the hand shown holding Alundra


def _d16(v):
    """bgez / addiu 0xF / sra 4: v / 16 rounded toward zero."""
    return (v + 0xF if v < 0 else v) >> 4


def _d32(v):
    return (v + 0x1F if v < 0 else v) >> 5


def _div(a, b):
    """div: a / b truncated toward zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _remove(g, t):
    """RemoveEntity (0x8003B0C8) of an entity pointer that may not be an entity record."""
    if not isinstance(t, _Raw):
        player.remove_entity(g, t)
        return
    t.estatus = 4; t.action = -1
    sh = t.shadow & M32
    if sh:
        _fx_put(g, sh, 'state', 0)
        t.shadow = 0
    h = t.holder & M32
    if h: g.mem.w32(h + L.ENTITY['carried'][0], 0)


def _boxes_touch(g, e, p):
    """Alundra's body box (+0x1D8.. / +0x1F0..) overlaps e's."""
    for a, b, wb, wa in ((p.mpx, e.mpx, e.sizex, p.sizex), (p.mpy, e.mpy, e.sizey, p.sizey),
                         (p.mpz, e.mpz, e.sizez, p.sizez)):
        d = s32(a - b)
        if d >= 0:
            if not d < s32(wb + 1): return False
        elif not s32(b - a) < s32(wa + 1): return False
    return True


def _c89_back(g, e, rec, fz):
    """fz; push toward its last circling position (/16)."""
    m = g.mem
    e.fz = fz
    m.w32(rec, _d16(s32(m.s32(rec + 0x10) - e.px)))
    m.w32(rec + 4, _d16(s32(m.s32(rec + 0x14) - e.py)))


@port(0x800640C4)
def ai_c89(g, e):
    """C89 (map 471 boss, its two hands): animations 10-15 are its shots (falling rocks: one
    landing shakes the screen (0x80083324) and stops (anim 9); byte 0 = 1 ones re-drop at a
    random spot once high enough; byte 0 = 2 ones fly in their direction); the hands circle
    their home (anim 0) and when game flag bit 1 is set and Alundra is within 2 squares lunge
    (16 -> 3) at him: touching him (and the other hand is not holding him) they grab him
    (anim 4, Alundra anim 0x56, mode flag 0x20), carry him home and hold him (anim 5, Alundra
    anim 0x31), crushing (anim 0x1C, a copy of the hand 0x801246E0 shown) until he breaks free
    by hurting it; anims 2 / 6 fly back; the boss dead: anim 7, Alundra let go."""
    m = g.mem
    p = g.ent[0]
    a = e.target_anim
    boss = _as_ent(g, e.parent)
    if a == 9: return
    if ((a - 0xA) & M32) < 6:
        if boss.hp == 0:
            entity.destroy_entity(g, e, -1)
            return
        if e.on_ground:
            core.play_sound(g, 0x19D)
            e.target_anim = 9
            e.flags = s32(e.flags | 0x40)
            calls.call(g, 0x80083324, 0x600000, 2, 0, 1)
            return
        if e.bytes[0] == 1 and a == 0xF and not e.pz < s32(boss.pz + 0x1000000):
            s1 = next_seed(g); s2 = next_seed(g); s3 = next_seed(g); s4 = next_seed(g)
            e.target_anim = 0xA
            e.flags = s32(e.flags | 0x100)
            e.px = s32(hi(s1, 0x18) * 0xC0000 + ((hi(s2, 7) << 16) + 0x1E00000))
            e.py = s32((hi(s3, 0x10) << 19) + ((hi(s4, 5) << 16) + 0x2800000))
        if e.bytes[0] == 2:
            k = e.bytes[1] << 11
            e.pafx = _div(s32(m.s16((DX + (e.target_dir << 1)) & M32) * k), 11)
            e.pafy = _div(s32(m.s16((DY + (e.target_dir << 1)) & M32) * k), 11)
        return
    r = aihelp.rel_tile(g, e)
    side = e.bytes[0]
    rec = (HANDS + side * 0x24) & M32
    other = (HANDS + 0x18 + (side ^ 1) * 0x24) & M32
    if boss.hp == 0:
        e.target_anim = 7
        e.flags = s32(e.flags | 0x40)
        if m.s32(rec + 0x18):
            y = e.py
            p.px = e.px
            p.target_anim = 0
            g.mode_flags = s32(g.mode_flags & ~0x20)
            p.py = y
            m.w32(rec + 0x18, 0)
        return
    st = m.s32(rec + 0x18)
    if st == 2 and p.on_ground:
        if p.target_anim == 0x1C:
            if p.anim_done:
                if e.bytes[2] == 0:
                    m.w32(0x801F94D0, 1); m.w32(0x801F94DC, 1); m.w32(0x801F94E0, 1)
                    m.w32(0x801F94D4, st); m.w32(0x801F94D8, st)
                    c = entity.spawn_warp_entity(g, e, 1, s32(e.sprite_index - 0x100), p.px, p.py, p.pz, 0)
                    t = _as_ent(g, c)
                    f = t.flags
                    t.target_anim = 0x11
                    m.w32(GRABBED, _ptr(g, c))
                    t.bi_c = 0
                    t.flags = s32((f | 2) & ~0x80)
                    p.anim_flags = s32(p.anim_flags & ~0x40)
                    e.bytes[2] = 1
                elif p.damaged_tick:
                    _remove(g, _as_ent(g, m.u32(GRABBED)))
                    e.bytes[2] = 0
                    p.target_anim = 0x39
                    p.target_dir = 0x10
        elif p.target_anim == 0x4E and p.anim_done:
            hp = p.hp
            m.w32(0x801F94D0, 0)
            g.mode_flags = s32(g.mode_flags & ~0x20)
            if hp: p.target_anim = 0
            m.w32(rec + 0x18, 0)
    if e.bytes[1] == 0:
        x = m.s32((HAND_X + (side << 2)) & M32)
        m.w32(rec + 0xC, 0x2A00000)
        m.w32(rec + 8, x)
        e.bytes[1] = 1
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t: e.ai[1] = t - 1
        d = (e.delay + m.s32((HAND_STEP + (side << 2)) & M32)) & 0x1FF
        sx = m.s16(WAVE_X + d * 2)
        e.delay = d
        e.px = s32(m.s32(rec + 8) + s32((sx * 9) << 9))
        sy = m.s16(WAVE_Y + e.delay * 2)
        x = e.px
        e.py = s32(m.s32(rec + 0xC) + s32((sy * 9) << 9))
        m.w32(rec + 0x10, x)
        m.w32(rec + 0x14, e.py)
        if (m.u32(FLAGS) & 2 and r[1] < 3 and r[0] < 3 and (e.ai[1] & 0xFFFF) == 0
                and m.s32(other) == 0):
            e.target_anim = 0x10
            m.w32(rec + 0x1C, p.px)
            m.w32(rec + 0x20, p.py)
    elif a == 0x10:
        if e.anim_done:
            e.target_anim = 3
            m.w32(rec, _d16(s32(m.s32(rec + 0x1C) - e.px)))
            m.w32(rec + 4, _d16(s32(m.s32(rec + 0x20) - e.py)))
            e.fz = -0x40000
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            t = (t - 1) & 0xFFFF
            e.ai[1] = t
            if not t:
                e.target_anim = 2
                _c89_back(g, e, rec, 0x20000)
        elif (_boxes_touch(g, e, p) and not p.anim_flags & 0x40 and p.damaged_tick == 0
                and m.s32(other) == 0):
            e.target_anim = 4
            e.fz = 0x20000
            e.flags = s32(e.flags & ~1)
            m.w32(rec, _d32(s32(m.s32(rec + 8) - e.px)))
            m.w32(rec + 4, _d32(s32(m.s32(rec + 0xC) - e.py)))
            p.target_anim = 0x56
            g.mode_flags = s32(g.mode_flags | 0x20)
            p.flags = s32(p.flags & ~0x108)
            m.w32(rec + 0x18, 1)
        elif e.collided_z or not 0xA00000 < e.pz:
            e.ai[1] = 0x14
            e.fz = 0
            m.w32(rec + 4, 0)
            m.w32(rec, 0)
    elif a == 2:
        if ((e.pz - 0xE00000) & M32) <= 0x80000: e.fz = 0
        dx = s32(e.px - m.s32(rec + 0x10)); dy = s32(e.py - m.s32(rec + 0x14))
        if not 0xBFFFF < _abs32(dx): m.w32(rec, 0)
        if not 0x7FFFF < _abs32(dy): m.w32(rec + 4, 0)
        if e.fz == 0 and m.s32(rec) == 0 and m.s32(rec + 4) == 0:
            x = e.px
            e.ai[1] = 0x78
            e.target_anim = 0
            m.w32(rec + 8, s32(m.s32((HAND_X + (side << 2)) & M32) + s32(x - m.s32(rec + 0x10))))
            m.w32(rec + 0xC, s32(s32(e.py - m.s32(rec + 0x14)) + 0x2A00000))
    elif a == 4:
        if 0x18FFFFF < e.pz: e.fz = 0
        dx = s32(e.px - m.s32(rec + 8)); dy = s32(e.py - m.s32(rec + 0xC))
        if not 0xBFFFF < _abs32(dx): m.w32(rec, 0)
        if not 0x7FFFF < _abs32(dy): m.w32(rec + 4, 0)
        if e.fz == 0 and m.s32(rec) == 0 and m.s32(rec + 4) == 0:
            e.target_anim = 5
            e.flags = s32(e.flags | 1)
            m.w32(rec + 0x18, 2)
            pf = p.flags
            p.target_anim = 0x31
            p.target_dir = 0
            p.flags = s32(pf | 0x108)
            p.px = e.px
            p.py = e.py
        p.pafx = m.s32(rec)
        p.pafy = m.s32(rec + 4)
        p.fz = e.fz
    elif a == 5:
        if e.anim_done:
            e.target_anim = 2
            _c89_back(g, e, rec, -0x40000)
    elif a == 6:
        m.w32(rec + 4, 0)
        m.w32(rec, 0)
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 7
                e.flags = s32(e.flags | 0x40)
                if side == 0: boss.delay = 0x708
                else: boss.item_state = 0x708
            else:
                m.w32(rec, _d16(s32(m.s32(rec + 0x10) - e.px)))
                m.w32(rec + 4, _d16(s32(m.s32(rec + 0x14) - e.py)))
                z = e.pz
                e.target_anim = 2
                if not 0xDFFFFF < z: e.fz = 0x20000
                if 0xE7FFFF < e.pz: e.fz = -0x40000
    elif a == 8:
        d = e.delay
        sx = m.s16((WAVE_X + (d << 1)) & M32)
        sy = m.s16((WAVE_Y + (d << 1)) & M32)
        e.px = s32(m.s32(rec + 8) + s32((sx * 9) << 9))
        e.pz = 0xE00000
        e.py = s32(m.s32(rec + 0xC) + s32((sy * 9) << 9))
        if e.anim_done: e.target_anim = 0
    v = m.s32(rec)
    if v: e.pafx = v
    v = m.s32(rec + 4)
    if v: e.pafy = v
