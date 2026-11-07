"""Built-in sprite programs, group 3: C26-C40, C42, C79 (US ALUN_CD.EXE 0x8006E154-0x80073188)."""
from .registry import port
from .core import s32, next_seed, hi
from . import aihelp, core, entity, player, calls

M32 = 0xFFFFFFFF

TURN = 0x80028AD8           # u8[32]: the direction turned away (a wall stopped it)
SHOT_X, SHOT_Y = 0x800273FC, 0x80027400     # s32 pairs [quadrant]: where the shot starts
QUAD_DIR = 0x80028AF8                       # u8[4]: direction of each facing quadrant
SHOT28_X, SHOT28_Y = 0x8002745C, 0x80027460 # s32 pairs [quadrant]
SHOT29 = 0x800274A4                         # s32 x, y, z [quadrant]
SHOT31 = 0x80027520                         # s32 x, y, z [quadrant]
SHOT32_X, SHOT32_Y = 0x80027550, 0x80027554 # s32 pairs [quadrant] (C32's shot)
SHOT34_X, SHOT34_Y = 0x80027570, 0x80027574 # (C34's)
SHOT33_X, SHOT33_Y = 0x800275C0, 0x800275C4 # s32 pairs [quadrant]
SHOT35_X, SHOT35_Y = 0x800275E0, 0x800275E4 # s32 pairs [quadrant]
SPOTS38 = 0x80027600                        # s16[12][4]: directions from each of 12 spots
COS, SIN = 0x800282D8, 0x800286D8           # s16 tables, 16 per direction (index ((d ^ 31) + 1) * 16)
GRID38 = 0x80124760                         # u8[6][6]: squares taken by the rain of rocks
QUAKE = 0x801F94D0                          # s32[5]: the screen shake the stomp starts (C39)
BOSS_FLAGS = 0x801E6378                     # bit 0 set when C39 is beaten


def _face_player(g, e):
    p = g.ent[0]
    return player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))


def _wall_turn(g, e, anim):
    """Pushed against something: stop, turn away (TURN table) and play anim."""
    e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
    e.target_anim = anim
    e.target_dir = g.mem.u8(TURN + e.target_dir)


def _spawn_fz(g, t, fz):
    """Stores fz into the new entity; the game does it through the pointer without a test, so
    a full entity table writes to address 0xB8 (low RAM)."""
    if t is None: g.mem.w32(0xB8, fz)
    else: t.fz = fz


def _away_player(g, e):
    p = g.ent[0]
    return player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))


def _flee(g, e):
    e.target_anim = 2
    e.target_dir = _away_player(g, e)


def _aim(g, e):
    e.target_dir = _face_player(g, e)
    e.ai[1] = 0x21


def _c35_react(g, e, r):
    """Alundra seen: back away (anim 9, bytes[1] 1) when he is within 2 squares, else turn to
    him and shoot (anim 5; sound 0xCD one time in 5)."""
    if r[0] < 3 and r[1] < 3:
        e.target_anim = 9
        e.target_dir = _away_player(g, e)
        e.ai[1] = 0x3C
        e.bytes[1] = 1
        return
    if hi(next_seed(g), 5) == 0: core.play_sound(g, 0xCD)
    e.target_anim = 5
    e.target_dir = _face_player(g, e)
    e.ai[1] = 0x12


def _byte_of(g, t, i):
    """t.bytes[i]; through a null entity pointer the game reads low RAM (0x274 + i)."""
    return t.bytes[i] if t is not None else g.mem.u8(0x274 + i)


def _anim_of(g, t):
    return t.target_anim if t is not None else g.mem.s32(0x88)


def _circle(d):
    """Byte offset into the COS / SIN tables for direction d (the game's ((d ^ 0x1F) + 1) << 5)."""
    return s32(((d ^ 0x1F) + 1) << 5)


def _div(a, b):
    """MIPS div (and the compiler's multiply-by-reciprocal): truncates toward zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _death_check(g, e, anim):
    """Bosses: dying (bytes[3] 1-3) while in anim 0 -> the puffs and flash (0x80083394),
    else (4+) the death animation anim, flag 0x40.  True when it handled the frame."""
    k3 = e.bytes[3]
    if k3 and e.target_anim == 0:
        if k3 < 4:
            calls.call(g, 0x80083394, e)
            return True
        e.target_anim = anim
        e.flags = s32(e.flags | 0x40)
        return True
    return False


def _c40_charge(g, e, b1):
    """Turn to Alundra and charge (anim 0xC, 60 frames); bytes[1] = what follows."""
    e.bytes[1] = b1
    e.target_anim = 0xC
    e.target_dir = _face_player(g, e)
    e.ai[1] = 0x3C


def _c40_stomp(g, e):
    e.target_anim = 2
    e.target_dir = 0
    e.ai[1] = 0x3C


@port(0x8006E154)
def ai_c26(g, e):
    """C26: wanders like C1; when Alundra comes within 2 squares it turns to him and
    (anim 3) throws map sprite 0x4A from its front 55 frames later, then wanders off."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a >= 8: return
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        if r[0] < 3 and r[1] < 3 and not (0x200000 < r[2]) and e.bytes[1] == 0:
            e.target_dir = _face_player(g, e)
            e.target_anim = 3
            e.bytes[1] = 1
            e.ai[1] = 0x37
            return
        s = next_seed(g)
        e.target_anim = 1
        e.ai[1] = hi(s, 0x3D) + 0x3C
        if r[0] < 4 and r[1] < 4:
            e.target_dir = _face_player(g, e)
        e.bytes[1] = 0
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t: return
        if e.force_adjusted:
            s = next_seed(g)
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = g.mem.u8(TURN + e.target_dir)
            e.ai[1] = hi(s, 0x1F) + 0x1E
            return
        s = next_seed(g)
        e.target_anim = 0
        e.ai[1] = (s >> 19) & 0x7F
        e.target_dir = s >> 27
    elif a == 2:
        if r[0] < 4 and r[1] < 4: e.target_anim = 4
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                q = e.anim_quadrant
                n = entity.spawn_warp_entity(g, e, 1, 0x4A, s32(e.px + g.mem.s32(SHOT_X + q * 8)),
                                             s32(e.py + g.mem.s32(SHOT_Y + q * 8)), s32(e.pz + 0xA0000),
                                             g.mem.u8(QUAD_DIR + q))
                _spawn_fz(g, n, 0x20000)
        if e.anim_done:
            aihelp.start_moving(g, e, 1, 0x28, 0x1E)
            e.bytes[1] = 0
    elif a == 7:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 6
            e.flags = s32(e.flags | 0x40)
            return
        e.target_anim = 0
        e.ai[1] = 0x28
    elif a == 4:
        if e.anim_done:
            e.target_anim = 0
            e.ai[1] = 0x1E


@port(0x8006E530)
def ai_c27(g, e):
    """C27: waits (anim 4) until Alundra is within 2 squares, rises (2) and fires map sprite
    0xCE four ways (3), then runs away from him (1); seeing him ahead while wandering makes
    it fire again."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a >= 7: return
    if a == 4:
        if r[0] < 3 and r[1] < 3 and not (0x100000 < r[2]):
            e.target_anim = 2
    elif a == 2:
        if e.anim_done:
            e.target_anim = 3
            e.target_dir = _face_player(g, e)
            e.ai[1] = 0x15
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                z = s32(e.pz + 0x200000)
                d = e.target_dir - 6                 # the first one is not masked
                for _ in range(4):
                    n = entity.spawn_warp_entity(g, e, 1, 0xCE, e.px, e.py, z, d)
                    d = (d + 4) & 0x1F
                    _spawn_fz(g, n, 0x40000)
        if e.anim_done:
            d = _away_player(g, e)
            s1 = next_seed(g)
            s2 = next_seed(g)
            e.target_anim = 1
            e.target_dir = (d + hi(s1, 5) - 2) & 0x1F
            e.bytes[0] = 1
            e.ai[1] = (s2 >> 27) + 0x78
    elif a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        aihelp.start_moving_half(g, e, 1, 0x78)
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t:
            if e.bytes[0] == 1:
                if not e.force_adjusted and not aihelp.ledge_ahead(g, e, 0): return
            else:
                if aihelp.sees_player(g, e, r, 2, 4, 0x100000):
                    e.target_anim = 3
                    e.ai[1] = 0x15
                    return
                if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
                    e.target_dir = next_seed(g) >> 27
                return
        e.target_dir = _face_player(g, e)
        s = next_seed(g)
        e.bytes[0] = 0
        e.ai[1] = (s >> 27) + 0x78
    elif a == 6:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 7
            e.flags = s32(e.flags | 0x40)
            return
        s = next_seed(g)
        e.target_anim = 0
        e.ai[1] = (s >> 28) + 0x20


@port(0x8006EA1C)
def ai_c28(g, e):
    """C28: hops about in 4 directions (always snapped to a quarter turn); when Alundra is
    straight ahead it fires map sprite 0xD4 at him (anim 4), or jumps at him when close (3),
    landing (8) and leaping back (9)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        if e.on_ground:
            if not e.ai[1] & 0xFFFF: e.ai[1] = 0x3C
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t:
                if e.bytes[1]:
                    s = next_seed(g)
                    e.target_anim = 1
                    e.target_dir = s >> 27
                else:
                    s = next_seed(g)
                    e.target_dir = (e.target_dir + hi(s, 0x1F) + 1) & 0x1F
                    if e.bytes[0] == 3:
                        e.target_anim = 9
                        e.bytes[0] = 0
                    else:
                        e.target_anim = 1
                        e.bytes[1] = 4
    elif a == 1:
        if e.anim_done:
            e.bytes[1] -= 1
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = (s >> 28) + 0x1E
            if e.bytes[1] == 0: e.bytes[0] += 1
        elif aihelp.sees_player(g, e, r, 2, 3, 0x300000):
            e.target_anim = 3
            e.target_dir = _face_player(g, e)
            e.bytes[2] = 1
        elif aihelp.sees_player(g, e, r, 1, 6, 0x300000):
            e.target_anim = 4
            e.ai[1] = 0x18
        elif e.force_adjusted:
            aihelp.step_or_turn(g, e, 1, 9, 0x300000)
        else:
            aihelp.ledge_turn(g, e, 1, 0x300000)
    elif a == 4:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                x, y, z = e.px, e.py, e.pz
                q = e.anim_quadrant
                p = g.ent[0]
                d = player.dir_from_delta(s32(p.px - x), s32(p.py - y))
                n = entity.spawn_warp_entity(g, e, 1, 0xD4, s32(x + g.mem.s32(SHOT28_X + q * 8)),
                                             s32(y + g.mem.s32(SHOT28_Y + q * 8)), z, (d + 2) & 0x1C)
                if n is not None: n.anim_quadrant = e.anim_quadrant
    elif a == 8:
        if e.on_ground:
            if e.bytes[2] == 0:
                e.target_anim = 0
                e.ai[1] = 0x28
            else:
                e.target_anim = 9
                e.target_dir = _away_player(g, e)
                e.bytes[2] = 0
    elif a == 6:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 7
                e.flags = s32(e.flags | 0x40)
            else:
                s = next_seed(g)
                e.target_anim = 0
                e.bytes[2] = 0
                e.ai[1] = (s >> 28) + 0x20
    e.target_dir = (e.target_dir + 2) & 0x1C        # always a quarter turn


@port(0x8006EEA8)
def ai_c29(g, e):
    """C29: looks left and right, then wanders; when Alundra is straight ahead (within 5
    squares) it fires map sprite 0x9B at him (anim 3) and hides (5 -> 2 for 120 frames -> 4)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 2:
        if not e.ai[1] & 0xFFFF: e.ai[1] = 0x78
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t: e.target_anim = 4
    elif a == 4:
        if e.anim_done:
            e.target_anim = 0
            e.ai[1] = 0x14
            e.bytes[0] = 0
    elif a == 0:
        if e.bytes[2] == 0 and aihelp.sees_player(g, e, r, 1, 5, 0x200000):
            e.target_anim = 3
            e.target_dir = _face_player(g, e)
            e.ai[1] = 0x3B
            return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        k = e.bytes[0]
        e.bytes[0] = k + 1
        if k == 0:                               # look one way...
            e.ai[1] = 0x14
            e.target_dir = (g.mem.u8(QUAD_DIR + e.anim_quadrant) + 8) & 0x1F
        elif k == 1:                             # ...then the other
            e.ai[1] = 0x14
            e.target_dir = (g.mem.u8(QUAD_DIR + e.anim_quadrant) + 0x10) & 0x1F
        elif k == 2:
            aihelp.start_moving(g, e, 1, 0x78, 0x14)
            e.bytes[2] = 0
            e.bytes[0] = 0
        else:
            e.bytes[0] = 0
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.target_anim = 5
            return
        if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
            s = next_seed(g)
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = (e.target_dir + hi(s, 0x18) + 1) & 0x1F
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                o = SHOT29 + e.anim_quadrant * 12
                entity.spawn_warp_entity(g, e, 1, 0x9B, s32(e.px + g.mem.s32(o)), s32(e.py + g.mem.s32(o + 4)),
                                         s32(e.pz + g.mem.s32(o + 8)), e.target_dir)
        if e.anim_done:
            e.target_anim = 5
            e.bytes[2] = 1
    elif a == 5:
        if e.anim_done:
            if e.bytes[1]:
                e.bytes[1] = 0
                e.px = s32(e.px + e.delay)
                e.py = s32(e.py + e.item_state)
            e.target_anim = 2
    elif a == 7:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 8
            e.flags = s32(e.flags | 0x40)
            return
        e.target_anim = 5
        e.ai[1] = 0
        e.bytes[1] = 0


@port(0x8006F278)
def ai_c30(g, e):
    """C30: dormant (anim 9) until Alundra comes within 4 squares (sound 0x171), then flies
    about between its home height (ai[0]) and 5 levels above it, diving at him when he is
    ahead and below: 4 shots of map sprite 0xDA dropped 50 frames apart, then a 50-frame rest."""
    r = aihelp.rel_tile_z(g, e)
    a = e.target_anim & M32
    if a >= 10: return
    if a == 9:
        if r[0] < 5 and r[1] < 5 and not (0x200000 < r[2]):
            core.play_sound(g, 0x171)
            e.target_anim = 2
            e.bytes[0] = 1
    elif a == 2:
        if e.anim_done and e.bytes[0] == 1:
            s = next_seed(g)
            e.target_anim = 7
            e.ai[1] = (s >> 28) + 0x12C
    elif a == 0:
        s1 = next_seed(g)
        s2 = next_seed(g)
        e.target_anim = 1
        e.target_dir = s1 >> 27
        e.ai[1] = (s2 >> 27) + 0x50
    elif a in (1, 7, 8):
        d = e.delay
        go = True
        if d:
            e.delay = d - 1
            go = (d - 1) == 0
        if go and e.bytes[1] == 0 and e.bytes[2] == 0 and r[5] >= 0 \
                and aihelp.sees_player(g, e, r, 2, 5, 0x400000):
            e.target_anim = 1
            e.target_dir = _face_player(g, e)
            e.ai[1] = 0x32
            e.bytes[2] = 4                       # 4 shots
            return
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            if e.bytes[2]:
                if hi(next_seed(g), 3) == 0: core.play_sound(g, 0x171)
                n = entity.spawn_warp_entity(g, e, 1, 0xDA, e.px, e.py, s32(e.pz + 0x100000), e.target_dir)
                if n is not None:
                    n.fz = -0x10000
                    n.flags = s32(n.flags & ~0x100)
                s = next_seed(g)
                e.bytes[2] -= 1
                e.ai[1] = (s >> 28) + 0x32
                if e.bytes[2] == 0:
                    s = next_seed(g)
                    e.delay = 0x32
                    e.target_dir = s >> 27
                    return
                e.target_dir = _face_player(g, e)
                return
            if e.on_ground:
                s = next_seed(g)
                e.target_anim = 7
                e.ai[1] = (s >> 27) + 0x28
                return
            if hi(next_seed(g), 3) == 0:
                e.target_anim = 8
                e.ai[1] = 0x1E
                return
            s = next_seed(g)
            e.target_anim = 1
            e.ai[1] = 0x64
            e.bytes[1] = 0
            e.target_dir = s >> 27
            return
        h = s32(e.pz - s32((e.ai[0] & 0xFFFF) << 16))    # height above home
        if a == 7:                                       # rising
            if 0x4FFFFF < h:
                e.target_anim = 8 if 0x200000 < s32(e.pz - e.terrain) else 1
                s = next_seed(g)
                e.bytes[0] = 0
                e.bytes[1] = 0
                e.ai[1] = (s >> 27) + 0x28
        elif a == 8:                                     # sinking
            if -0x600000 < h:
                if not e.on_ground: return
                if 0x200000 < h:
                    s = next_seed(g)
                    e.target_anim = 1
                    e.ai[1] = 0x3C
                    e.target_dir = s >> 27
                    return
            s = next_seed(g)
            e.target_anim = 7
            e.bytes[0] = 1
            e.ai[1] = hi(s, 0x11) + 0x28
        else:                                            # 1: flying level
            if e.force_adjusted:
                s = next_seed(g)
                e.ai[1] = 0x28
                e.target_dir = s >> 27
                e.target_anim = 7 if e.bytes[0] == 1 else 8
    elif a == 5:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 6
            e.flags = s32(e.flags | 0x40)
            return
        e.target_anim = 7
        e.target_dir = _away_player(g, e)
        e.ai[1] = 0x78
        e.bytes[1] = 1


@port(0x8006F9F8)
def ai_c31(g, e):
    """C31: wanders, backing off from ledges (looks back, then aside); when Alundra comes
    within 3 squares it faces him and spits map sprite 0xB0 (anim 3, 32 frames); hurt (5) it
    runs from him."""
    r = aihelp.rel_tile(g, e)
    if (e.target_anim & M32) < 2 and r[0] < 4 and r[1] < 4 and not (0x100000 < r[2]):
        e.target_anim = 3
        e.cur_anim = -1
        e.target_dir = _face_player(g, e)
        e.ai[1] = 0x20
        return
    a = e.target_anim
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        if not e.bytes[1]:
            aihelp.start_moving(g, e, 1, 0x50, 0x1E)
            return
        k = e.bytes[1]
        e.ai[1] = 0x3C
        e.bytes[1] = k - 1
        if k == 1:                                   # turn around
            e.target_dir = (e.target_dir + 0x10) & 0x1F
        elif k == 2:                                 # look to one side (not masked)
            e.target_dir = (8 if hi(next_seed(g), 2) else 0xF8) + g.mem.u8(QUAD_DIR + e.anim_quadrant)
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = (s >> 27) + 0x1E
            return
        if e.force_adjusted:
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = (g.mem.u8(TURN + e.target_dir) + 0x10) & 0x1F
            return
        if aihelp.ledge_ahead(g, e, 0):
            e.target_anim = 0
            e.ai[1] = 0
            e.bytes[1] = 2
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                o = SHOT31 + e.anim_quadrant * 12
                n = entity.spawn_warp_entity(g, e, 1, 0xB0, s32(e.px + g.mem.s32(o)), s32(e.py + g.mem.s32(o + 4)),
                                             s32(e.pz + g.mem.s32(o + 8)), e.target_dir)
                if n is not None: n.fz = 0x20000
                e.bytes[0] = 0
        if e.anim_done:
            e.target_anim = 0
            e.ai[1] = 0x1E
    elif a == 5:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 2
            e.flags = s32(e.flags | 0x40)
            return
        if hi(next_seed(g), 5) == 0: core.play_sound(g, 0x9E)
        e.target_anim = 1
        e.target_dir = _away_player(g, e)
        e.ai[1] = 0x28
        e.bytes[0] = 1
        e.bytes[1] = 0


@port(0x8006FE54)
def ai_c32(g, e, prog=0):
    """C32 / C34: wanders toward Alundra and runs off when he is ahead or close; jumping
    (5 -> 3) it throws map sprite 0x6E (prog 32) or 0x74 with a random animation 0/2/3 (C34).
    prog: the program number, which the game's dispatcher (0x800391FC) leaves in a1."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a >= 12: return
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        s = next_seed(g)
        e.target_anim = 1
        e.ai[1] = (s >> 27) + 0x78
        if (r[0] >= 0xF and r[1] >= 0xF) or 0x6FFFFF < r[2]:
            e.target_dir = next_seed(g) >> 27
            return
        e.target_dir = _face_player(g, e)
        e.ai[1] = (e.ai[1] & 0xFFFF) + 0x28
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = (s >> 28) + 0x3C
            return
        if aihelp.sees_player(g, e, r, 1, 4, 0x100000) or (r[0] < 3 and r[1] < 3 and not (0x10000 < r[2])):
            _flee(g, e)
        elif e.force_adjusted:
            aihelp.step_or_turn(g, e, 1, 4, 0x200000)
        else:
            aihelp.ledge_turn(g, e, 1, 0x200000)
    elif a == 5:
        if e.on_ground:
            e.target_anim = 3
            e.ai[1] = 0xF
            e.target_dir = (e.target_dir + 0x10) & 0x1F
    elif a == 6:
        if e.on_ground: e.target_anim = 1
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                z = s32(e.pz + 0xA0000)
                q = e.anim_quadrant * 8
                if (prog & M32) == 0x20:
                    entity.spawn_warp_entity(g, e, 1, 0x6E, s32(e.px + g.mem.s32(SHOT32_X + q)),
                                             s32(e.py + g.mem.s32(SHOT32_Y + q)), z, e.target_dir)
                else:
                    n = entity.spawn_warp_entity(g, e, 1, 0x74, s32(e.px + g.mem.s32(SHOT34_X + q)),
                                                 s32(e.py + g.mem.s32(SHOT34_Y + q)), z, e.target_dir)
                    if n is not None:
                        k = hi(next_seed(g), 3)
                        n.target_anim = k + 1 if k else 0
                        n.fz = 0x38000
        if e.anim_done:
            e.target_anim = 0
            e.ai[1] = 0x78
    elif a == 10:
        if e.anim_done:
            e.target_anim = 0
            e.ai[1] = 0x1E
            e.target_dir = (e.target_dir + 0x10) & 0x1F
    elif a == 9:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 8
            e.flags = s32(e.flags | 0x40)
            return
        _flee(g, e)
    elif a == 11:
        if e.target_anim == e.cur_anim and e.on_ground:
            e.target_anim = 0xA


@port(0x8007033C)
def ai_c33(g, e):
    """C33: walks straight (anim 6), turning at walls and ledges; when Alundra is within 6
    squares it shoots map sprite 0x5F at him (anim 2) as long as he stays in range, backing
    away first (bytes[0] 1) when he is within 2."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        e.target_anim = 6
        e.target_dir = g.mem.u8(QUAD_DIR + e.anim_quadrant)
    elif a == 6:
        k = e.bytes[0]
        if k == 0:
            if r[0] < 7 and r[1] < 7 and not (0x200000 < r[2]):
                if r[0] < 3 and r[1] < 3:
                    e.bytes[0] = 1                   # too close: back off first
                    e.target_dir = _away_player(g, e)
                    e.ai[1] = 0x1E
                    return
                e.target_anim = 2
                _aim(g, e)
                return
            if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
                e.bytes[2] += 1
                s = next_seed(g)
                e.target_anim = 0
                e.ai[1] = (s >> 27) + 0x3C
                qd = g.mem.u8(QUAD_DIR + e.anim_quadrant)
                if e.bytes[2] >= 3:
                    e.bytes[2] = 0
                    d = qd + 8 if e.ai[1] & 1 else qd - 8
                else:
                    d = qd - 0x10
                e.target_dir = d & 0x1F
        elif k == 1:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if t and not e.force_adjusted and not aihelp.ledge_ahead(g, e, 0): return
            if hi(next_seed(g), 5) == 0: core.play_sound(g, 0xCD)
            e.target_anim = 2
            _aim(g, e)
    elif a == 2:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                q = e.anim_quadrant * 8
                n = entity.spawn_warp_entity(g, e, 1, 0x5F, s32(e.px + g.mem.s32(SHOT33_X + q)),
                                             s32(e.py + g.mem.s32(SHOT33_Y + q)), s32(e.pz + 0x100000), e.target_dir)
                if n is not None: n.anim_quadrant = e.anim_quadrant
        if e.anim_done:
            if r[0] < 7 and r[1] < 7 and not (0x200000 < r[2]):
                e.cur_anim = -1                      # shoot again
                _aim(g, e)
                return
            e.target_anim = 0
            e.ai[1] = 0xA
            e.bytes[0] = 0
    elif a == 4:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 5
            e.flags = s32(e.flags | 0x40)
            return
        e.target_anim = 2
        _aim(g, e)
        e.bytes[0] = 0


@port(0x800707AC)
def ai_c35(g, e):
    """C35: stands looking around (left, back) then walks (anim 9); when Alundra is straight
    ahead within 6 squares it fires map sprite 0x65 at him (anim 5), or backs away first when
    he is within 2; it faces only the 4 main directions while shooting."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 0:
        if e.on_ground:
            if e.bytes[2]:
                e.bytes[2] -= 1                      # pause after a shot
            else:
                t = e.ai[1] & 0xFFFF
                if t: e.ai[1] = t - 1
                if e.bytes[1] == 2 or aihelp.sees_player(g, e, r, 1, 6, 0x200000):
                    e.bytes[1] = 0
                    _c35_react(g, e, r)
                elif not e.ai[1] & 0xFFFF:
                    k = e.bytes[0]
                    e.bytes[0] = k + 1
                    if k == 0:
                        e.ai[1] = 0x3C
                        e.target_dir = (g.mem.u8(QUAD_DIR + e.anim_quadrant) + 8) & 0x1F
                    elif k == 1:
                        e.ai[1] = 0x3C
                        e.target_dir = (g.mem.u8(QUAD_DIR + e.anim_quadrant) + 0x10) & 0x1F
                    elif k == 2:
                        s1 = next_seed(g)
                        s2 = next_seed(g)
                        e.target_anim = 9
                        e.target_dir = s1 >> 27
                        e.bytes[1] = 0
                        e.ai[1] = (s2 >> 28) + 0x3C
                    else:
                        e.bytes[0] = 0
    elif a == 9:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if e.bytes[1] == 1 and (not t or e.force_adjusted or aihelp.ledge_ahead(g, e, 0)):
            e.target_anim = 5                        # backed off: turn and shoot
            e.target_dir = _face_player(g, e)
            e.ai[1] = 0x12
        elif not e.ai[1] & 0xFFFF:
            e.target_anim = 0
            e.ai[1] = 0x3C
        elif aihelp.sees_player(g, e, r, 1, 6, 0x200000):
            _c35_react(g, e, r)
        elif e.force_adjusted:
            aihelp.step_or_turn(g, e, 9, 3, 0x300000)
        else:
            aihelp.ledge_turn(g, e, 9, 0x300000)
    elif a == 5:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                q = e.anim_quadrant * 8
                entity.spawn_warp_entity(g, e, 1, 0x65, s32(e.px + g.mem.s32(SHOT35_X + q)),
                                         s32(e.py + g.mem.s32(SHOT35_Y + q)), s32(e.pz + 0xA0000),
                                         (e.target_dir - 7) & 0x1F)
                e.bytes[2] = 0x1E
    elif a == 7:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 8
                e.flags = s32(e.flags | 0x40)
            else:
                e.target_anim = 0
                e.bytes[2] = 0
                e.bytes[0] = 0
                e.bytes[1] = 2                       # react at once
    if e.target_anim in (3, 5):
        e.target_dir = (e.target_dir + 2) & 0x1C


@port(0x80070D14)
def ai_c36(g, e):
    """C36: while idle, turns one step (1/32) every 5 frames, 64 steps in all, then stays."""
    if e.target_anim != 0: return
    b = e.bytes[0]
    if b == 0x40: return
    t = e.ai[1] & 0xFFFF
    if t:
        e.ai[1] = t - 1
        return
    e.bytes[0] = b + 1
    e.ai[1] = 4
    e.target_dir = (e.target_dir + 1) & 0x1F


@port(0x80070D78)
def ai_c37(g, e):
    """C37: faces Alundra and hops toward him 1-2 (+1) times, leaving a dust puff (global effect 7)
    every 10 frames of each 25-frame hop; when hurt (anim 5) it rests 90 frames, or dies."""
    aihelp.rel_tile(g, e)                    # result unused
    a = e.target_anim
    if a == 0:
        s = next_seed(g)
        r = hi(s, 3)
        if r < 2: e.bytes[0] += 1
        elif r == 2: e.bytes[0] += 2
        e.target_anim = 2
        e.bytes[2] = e.bytes[0]
        e.target_dir = _face_player(g, e)
        e.ai[1] = 0
    elif a == 2:
        if not e.anim_done: return
        if e.bytes[2]:
            e.cur_anim = 0                   # replay the windup
            e.target_dir = _face_player(g, e)
            e.bytes[2] -= 1
            return
        e.target_anim = 1
        if e.ai[1] & 0xFFFF: return
        e.ai[1] = 0x19
        e.target_dir = _face_player(g, e)
        e.bytes[0] -= 1
    elif a == 1:
        if e.bytes[1] == 0:
            core.spawn_effect(g, 0, 7, 0, e.px, e.py, e.pz)
            e.bytes[1] = 0xA
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        e.bytes[1] -= 1
        if t == 0:
            e.target_anim = 2 if e.bytes[0] else 0
            e.target_dir = _face_player(g, e)
            return
        if e.force_adjusted: _wall_turn(g, e, 2)
    elif a == 5:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 6
            e.flags = s32(e.flags | 0x40)
            return
        e.target_anim = 0
        e.damaged_tick = 0x5A
        e.bytes[1] = 0
        e.bytes[0] = 0


@port(0x80071080)
def ai_c38(g, e):
    """C38 (boss): hops between 12 spots of the room (anim 4, leaving map sprite 0xE4 dust and
    dropping 0xE6 rocks near Alundra every 64 frames), then attacks from where it lands (anim 8,
    bytes[2] = attack): 4 bursts of 4 sparks (0xE4), 12 falling rocks over the room (0xE6/0xE7,
    anim 0), 4 rocks round Alundra, or a ring of 8; dying (bytes[3]) it flashes / falls."""
    if _death_check(g, e, 7): return
    a = e.target_anim & M32
    if a == 8:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        k = e.bytes[2]
        if k == 0:                               # choose how many hops
            e.bytes[2] = 1
            s = next_seed(g)
            e.ai[1] = 0x3C
            e.bytes[1] = hi(s, 3) + 1
        elif k == 1:
            n = e.bytes[1]
            if n:                                # hop to a neighbouring spot
                e.bytes[1] = n - 1
                e.bytes[2] = 1
                e.ai[1] = 0x40
                s = next_seed(g)
                e.target_anim = 4
                d0 = e.target_dir
                row = SPOTS38 + e.bytes[0] * 8
                i = hi(s, 4)
                for _ in range(4):
                    d = g.mem.s16(row + i * 2)
                    i = (i + 1) & 3
                    if d0 != d: break
                else:
                    raise RuntimeError('C38: no way out of this spot (the game hangs here)')
                e.target_dir = d
                if d == 4: e.bytes[0] -= 3
                elif d == 12: e.bytes[0] += 2
                elif d == 20: e.bytes[0] += 3
                else: e.bytes[0] -= 2
                return
            b = e.bytes[0]
            if b == 3 or ((b - 5) & M32) < 2 or b == 8:
                if hi(next_seed(g), 3) == 0:
                    e.bytes[2] = 5
                    return
            r = next_seed(g) >> 29
            if r in (0, 2, 4):
                e.bytes[2] = 2
                e.ai[4] = 8
                e.delay = next_seed(g) >> 27
            elif r in (1, 3, 5):
                e.bytes[2] = 4
            else:
                e.bytes[2] = 3
        elif k == 2:                             # sparks: 4 bursts of 4
            t = e.ai[4] & 0xFFFF
            if not t:
                e.bytes[2] = 0
                return
            d = e.delay
            e.ai[4] = t - 1
            e.ai[1] = 0xC
            e.delay = (d + 2) & 0x1F
            core.play_sound(g, 0xBE)
            w = 0
            for _ in range(4):
                o = _circle(d)
                n = entity.spawn_warp_entity(g, e, 1, 0xE4, s32(e.px + (g.mem.s16(COS + o) << 11)),
                                             s32(e.py + (g.mem.s16(SIN + o) << 11)), e.pz, d)
                if n is not None:
                    n.target_anim = 3
                    n.ai[1] = w
                d = (d + 8) & 0x1F
                w += 3
        elif k == 3:
            e.target_anim = 2
            e.ai[1] = 0x14
        elif k == 4:
            e.target_anim = 2
        elif k == 5:                             # ring of 8
            e.target_anim = 2
            e.ai[1] = 0x78
            d = 0
            for i in range(8):
                n = entity.spawn_warp_entity(g, e, 1, (i & 1) | 0xE6, s32(e.px + (g.mem.s16(COS + i * 0x80) << 12)),
                                             s32(e.py + (g.mem.s16(SIN + (i << 7)) << 12)), e.pz, d)
                if n is not None:
                    n.target_anim = 2
                    n.bytes[2] = 5
                    n.ai[1] = 0x5A
                d = (d - 4) & 0x1F
    elif a == 4:                                 # hopping
        t = e.ai[1] & 0xFFFF
        if t: e.ai[1] = t - 1
        if not e.ai[1] & 7:
            n = entity.spawn_warp_entity(g, e, 1, 0xE4, e.px, s32(e.py - 0x10000), e.pz, 0)
            if n is not None:
                n.target_anim = 2
                n.flags = s32((n.flags & ~3) | 0x40)
        if not e.ai[1] & 0x3F:                   # a rock near Alundra, kept in the room
            p = g.ent[0]
            s1 = next_seed(g)
            s2 = next_seed(g)
            x = s32(p.px + (hi(s1, 0xD) << 19) - 0x300000)
            y = s32(p.py + (hi(s2, 0x11) << 18) - 0x200000)
            if not 0x137FFFF < x: x = 0x12C0000
            if 0x2580000 < x: x = 0x2640000
            if not 0x17FFFFF < y: y = 0x1780000
            if 0x2500000 < y: y = 0x2580000
            n = entity.spawn_warp_entity(g, e, 1, 0xE6, x, y, p.pz, 0)
            if n is not None:
                n.target_anim = 2
                n.bytes[2] = 1
        if not e.ai[1] & 0xFFFF:
            e.target_anim = 8
            e.ai[1] = 0x28
            e.target_dir = (e.target_dir + 0x10) & 0x1F
    elif a == 2:
        if e.anim_done: e.target_anim = 0
    elif a == 0:
        k = e.bytes[2]
        if k == 3:                               # 12 rocks over the room, one per free square
            t = e.ai[1] & 0xFFFF
            if t:
                e.ai[1] = t - 1
                if (t - 1) & 0xFFFF: return
            e.ai[1] = 0xB4
            for i in range(0x24): g.mem.w8(GRID38 + i, 0)
            for i in range(12):
                sa = next_seed(g)
                sb = next_seed(g)
                cx = hi(sa, 6)
                cy = hi(sb, 4)
                if 0x1F7FFFF < g.ent[0].py: cy += 2
                row = cy * 6
                if g.mem.u8(GRID38 + row + cx):
                    cx += 2
                    while True:
                        if cx >= 6:
                            cx -= 6
                            cy += 1
                            row += 6
                            if cy >= 6: row = 0; cy = 0
                        if not g.mem.u8(GRID38 + row + cx): break
                        cx += 2
                g.mem.w8(GRID38 + cy * 6 + cx, 1)
                sc = next_seed(g)
                sd = next_seed(g)
                n = entity.spawn_warp_entity(g, e, 1, (i & 1) | 0xE6,
                                             s32(cx * 0x300000 + (hi(sc, 0x19) << 16) + 0x1500000),
                                             s32(cy * 0x280000 + (hi(sd, 0x15) << 16) + 0x1800000), e.pz, 0)
                if n is not None:
                    s = next_seed(g)
                    n.target_anim = 8
                    n.bytes[2] = 3
                    n.ai[1] = hi(s, 0x1F) + i * 2 + 0xA
        elif k == 4:                             # 4 rocks round Alundra
            t = e.ai[1] & 0xFFFF
            if t:
                e.ai[1] = t - 1
                return
            e.ai[1] = 0xC8
            d = hi(next_seed(g), 4) * 8 + 4
            w = 0xA
            p = g.ent[0]
            for i in range(4):
                o = _circle(d)
                x = s32(p.px + ((g.mem.s16(COS + o) * 3) << 11))
                y = s32(p.py + ((g.mem.s16(SIN + o) * 3) << 11))
                if ((x - 0x1380000) & M32) <= 0x1200000 and ((y - 0x1800000) & M32) <= 0xD00000:
                    n = entity.spawn_warp_entity(g, e, 1, (i & 1) | 0xE6, x, y, p.pz, d)
                    if n is not None:
                        s = next_seed(g)
                        n.target_anim = 4
                        n.delay = w
                        n.bytes[2] = 4
                        n.ai[1] = hi(s, 0x15) + 0x1E
                        if (n.pz >> 16) != (e.pz >> 16):       # not on its level
                            player.remove_entity(g, n)
                d = (d + 8) & 0x1F
                w += 0x1E
        elif k == 5:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t: e.target_anim = 3
    elif a == 6:
        if not e.anim_done: return
        if e.bytes[3]:
            e.ai[1] = 0x12C
            e.ai[5] = 0x1E
            e.target_anim = 0
            e.flags = s32(e.flags & ~3)
            return
        e.target_anim = 3
    elif a == 3:
        if e.anim_done:
            e.target_anim = 8
            e.bytes[2] = 0
            e.ai[1] = 0x3C


@port(0x80071D48)
def ai_c79(g, e):
    """C79: anim 0 until its animation ends, it is pushed or Alundra's attack touches it:
    then anim 1 and flag 0x40; anim 3 counts ai[1] down and goes back to 0."""
    a = e.target_anim
    if a == 0:
        if e.anim_done or e.force_adjusted or g.ent[0].touching is e:
            e.target_anim = 1
            e.flags = s32(e.flags | 0x40)
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        e.target_anim = 0


@port(0x80071DD0)
def ai_c42(g, e):
    """C42: a child of another program (its parent's bytes[2] says the phase): leaves a trail
    of map sprite 0xE4 every 8 frames while moving (anim 1), chasing Alundra in phase 4 or
    circling in phase 5; it disappears when the phase changes or its parent dies."""
    p = e.parent
    if _byte_of(g, p, 3):                        # the parent is dying
        a = e.target_anim
        if a != 8 and a != 4:
            e.target_anim = 7
            e.flags = s32(e.flags | 0x40)
            return
        player.remove_entity(g, e)
        return
    aihelp.rel_tile(g, e)                        # result unused
    a = e.target_anim & M32
    if a == 8:
        if _byte_of(g, p, 2) != e.bytes[2]:
            player.remove_entity(g, e)
            return
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t: e.target_anim = 2
    elif a == 4:
        k = _byte_of(g, p, 2)
        if k != e.bytes[2]:
            player.remove_entity(g, e)
            return
        if k != 4: return
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t and not e.force_adjusted: return
        e.target_anim = 8
        e.ai[1] = e.delay
    elif a == 2:
        if not e.anim_done: return
        if e.bytes[2] in (3, 1): e.target_anim = 3
        if e.bytes[2] == 5:
            core.play_sound(g, 0x6E)
            e.target_anim = 1
            e.bytes[0] = 6
        if e.bytes[2] == 4:
            e.target_anim = 1
            e.target_dir = _face_player(g, e)
    elif a == 1:
        e.delay = s32(e.delay + 1)
        if not e.delay & 7:                      # trail
            n = entity.spawn_warp_entity(g, e, 1, 0xE4, e.px, s32(e.py - 0x10000), e.pz, 0)
            if n is not None:
                n.target_anim = 2
                n.flags = s32((n.flags & ~3) | 0x40)
        k = e.bytes[2]
        if k == 4:                               # chase Alundra
            if _anim_of(g, p) == 3:
                e.target_anim = 0xA
            elif e.bytes[0] == 5:
                if e.force_adjusted: e.target_anim = 0xA
            else:
                t = e.ai[1] & 0xFFFF
                if t:
                    e.ai[1] = t - 1
                    if (t - 1) & 0xFFFF: return
                e.ai[1] = 8
                e.target_dir = _face_player(g, e)
                e.bytes[0] += 1
        elif k == 5:                             # circle
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t or e.force_adjusted:
                e.target_anim = 0xA
                return
            e.bytes[0] -= 1
            if e.bytes[0] == 0:
                e.bytes[0] = 6
                e.target_dir = (e.target_dir + 1) & 0x1F
    elif a == 3 or a == 10:
        if e.anim_done: e.target_anim = 9
    elif a == 9:
        if e.anim_done: player.remove_entity(g, e)


@port(0x80072164)
def ai_c39(g, e):
    """C39 (boss): walks about, jumping (anim 0x12/0x13 -> 14) toward or near Alundra; a
    stomp (5 -> 6) shakes the screen and knocks him and sprites 0x16A / 0x173 down (0x5A /
    0xB); weak (hp <= hp_max / 5) it heals itself in anim 10 (4 x hp_max / 10, effect 0xE)."""
    d = e.delay
    if d:
        e.delay = d - 1
        if d - 1 == 0:                           # the shake ends
            g.mem.w32(QUAKE, 0)
            calls.call(g, 0x8004A7B4, 0x55)
    p = g.ent[0]
    if p.cur_anim == 0x5A and p.on_ground: p.target_anim = 0x59     # knocked down: get up
    if p.cur_anim == 0x59 and p.anim_done: p.target_anim = 0
    if _death_check(g, e, 7): return
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 10:                                  # heal, or wait for Alundra in front
        if e.bytes[1]:
            if not e.ai[1] & 0xFFFF: e.ai[1] = 0x3C
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if t: return
            e.hp = s32(e.hp + _div(e.hp_max, 10))
            core.play_sound(g, 0x31)
            for ox, oz in ((-0x140000, 0x200000), (-0x100000, 0x3C0000), (0, 0x460000),
                           (0x100000, 0x400000), (0x140000, 0x1C0000)):
                core.spawn_effect(g, 0, 0xE, 0, s32(e.px + ox), e.py, s32(e.pz + oz))
            e.bytes[1] -= 1
            if e.bytes[1] == 0: e.target_anim = 2
        elif aihelp.sees_player(g, e, r, 2, 6, 0x300000):
            e.target_anim = 2
    elif a == 2:
        if e.anim_done: e.target_anim = 0
    elif a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if e.item_state: return
            if ((t - 1) & 0xFFFF) < 0x10 and r[0] < 5 and r[1] < 5:
                s = next_seed(g)
                e.target_anim = 3
                e.item_state = hi(s, 3) + 3
            return
        if e.item_state: e.item_state = s32(e.item_state - 1)
        e.ai[4] = 0
        if r[0] < 3 and r[1] < 3 and not (0x100000 < r[2]):
            if hi(next_seed(g), 3) == 0:
                e.target_dir = next_seed(g) >> 27
            else:
                e.target_dir = _face_player(g, e)
            e.target_anim = 0x12
            return
        if not _div(e.hp_max, 5) < e.hp:
            e.target_anim = 0xF                  # weak: go and heal
            return
        e.bytes[0] = hi(next_seed(g), 4) + 2     # jumps
        s = next_seed(g)
        e.target_anim = 0x13
        if hi(s, 3) == 0:
            e.target_dir = next_seed(g) >> 27
            return
        e.target_dir = _face_player(g, e)
        e.ai[4] = 1
    elif a == 19:
        if e.anim_done: e.target_anim = 0xD
    elif a == 18:
        if e.anim_done: e.target_anim = 0xB
    elif a == 3:
        if e.anim_done: e.target_anim = 4
    elif a == 14:                                # landed
        if not e.on_ground: return
        b = e.bytes[0]
        if b:
            e.bytes[0] = b - 1
            if b - 1:
                e.target_anim = 0x13
                if e.ai[4] & 0xFFFF:
                    e.target_dir = _face_player(g, e)
                    return
                e.target_dir = s32(e.target_dir + 8)    # not masked
                if e.force_adjusted and hi(next_seed(g), 4) == 0:
                    e.target_dir = (e.target_dir + 8) & 0x18
                return
        e.target_anim = 6
    elif a == 5:                                 # stomp
        if e.on_ground:
            e.target_anim = 6
            e.bytes[2] = 5
            e.delay = 0x32
            core.play_sound(g, 0x55)
            g.mem.w32(QUAKE, 1)
            g.mem.w32(QUAKE + 0xC, 1)
            g.mem.w32(QUAKE + 0x10, 1)
            g.mem.w32(QUAKE + 4, 2)
            g.mem.w32(QUAKE + 8, 2)
    elif a == 12:
        if e.on_ground: e.target_anim = 6
    elif a == 6:
        if e.bytes[2]:
            e.bytes[2] -= 1
            p = g.ent[0]
            for t in g.ent[:0x40]:               # every slot, live or not
                if (t is p or t.sprite_index in (0x16A, 0x173)) and t.on_ground \
                        and not t.anim_flags & 0x40 and t.damaged_tick == 0:
                    t.sfy = t.sfx = t.fy = t.fx = t.tfy = t.tfx = 0
                    if t is p: p.target_anim = 0x5A
                    else: t.target_anim = 0xB
        if e.anim_done:
            e.ai[1] = 0x3C
            s = next_seed(g)
            e.target_anim = 0
            if hi(s, 4) == 0: e.target_dir = _face_player(g, e)
    elif a == 15:
        if e.anim_done:
            e.target_anim = 0xA
            e.bytes[1] = 4
            e.ai[1] = 0
    elif a == 9:
        if not e.anim_done: return
        if e.bytes[3]:
            g.mem.w32(BOSS_FLAGS, g.mem.u32(BOSS_FLAGS) | 1)
            e.ai[1] = 0x12C
            e.ai[5] = 0x1E
            e.target_anim = 0
            e.flags = s32(e.flags & ~3)
            return
        e.damaged_tick = 0x5A
        e.target_anim = 0
        e.ai[1] = 0x1E
        e.bytes[2] = 0
    elif a == 17:
        if e.anim_done:
            e.target_anim = 0xA
            e.bytes[1] = 0


@port(0x80072AC8)
def ai_c40(g, e):
    """C40 (boss): hidden (anim 6) until Alundra is right in front, then drops down (0xB -> 7);
    wanders or runs (1 / 0xD, rumbling sound 0x1CF), charges him when he is ahead (0xC, map
    sprite 0xF3 shot at the end), and stomps (2: screen shake, 1 or 8 shots of 0xF3)."""
    d = e.delay
    if d:
        e.delay = d - 1
        if d - 1 == 0:
            g.mem.w32(QUAKE, 0)
            calls.call(g, 0x8004A7B4, 0x55)
    if _death_check(g, e, 0xA): return
    if e.target_anim != 1 and e.target_anim != 0xD: e.item_state = 0
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 6:
        if aihelp.sees_player(g, e, r, 3, 3, 0):
            e.target_anim = 0xB
            e.ai[1] = 0x78
            e.flags = s32(e.flags & ~0x100)
    elif a == 11:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.target_anim = 7
            e.flags = s32(e.flags | 0x100)
    elif a == 7:
        if e.on_ground:
            e.target_anim = 0
            core.play_sound(g, 0x65)
    elif a == 0:
        if e.bytes[2]: return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        if e.ai[4] & 0xFFFF:                     # after being hurt: stomp, 1 time in ai[4] + 1
            if hi(next_seed(g), (e.ai[4] & 0xFFFF) + 1) == 0:
                _c40_stomp(g, e)
                return
        e.ai[4] = 0
        if e.bytes[1]:
            aihelp.start_moving(g, e, 1, 0x3C, 0x46)
            e.bytes[0] = 2
            return
        if r[0] < 3 and r[1] < 3 and not (0x100000 < r[2]):
            e.target_anim = 1                    # too close: run off
            e.target_dir = _away_player(g, e)
            e.ai[1] = 0x78
            e.bytes[0] = 1
            return
        aihelp.start_moving(g, e, 1, 0x78, 0x14)
        e.bytes[0] = 0
    elif a == 1 or a == 13:
        if not _div(e.hp_max, 4) < e.hp: e.target_anim = 0xD     # weak: faster
        if e.item_state == 0:
            core.play_sound(g, 0x1CF)
            e.item_state = 0x1A if e.target_anim == 1 else 0x10
        e.bytes[1] = 0
        e.item_state = s32(e.item_state - 1)
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        k = e.bytes[0]
        t = e.ai[1] & 0xFFFF
        if k == 0:
            if not t:
                _c40_stomp(g, e)
            elif aihelp.sees_player(g, e, r, 1, 5, 0x100000):
                _c40_charge(g, e, 2)
            elif e.force_adjusted:
                e.target_dir = (e.target_dir + 8) & 0x1F
        elif k == 1:
            if not t or e.force_adjusted: _c40_charge(g, e, 3)
        elif k == 2:
            if not t or e.force_adjusted:
                e.target_anim = 0
                e.ai[1] = 0x28
    elif a == 2:                                 # stomp
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                core.play_sound(g, 0x55)
                g.mem.w32(QUAKE, 1)
                g.mem.w32(QUAKE + 0xC, 1)
                g.mem.w32(QUAKE + 0x10, 1)
                g.mem.w32(QUAKE + 4, 2)
                g.mem.w32(QUAKE + 8, 2)
                e.delay = 0x28
        if e.anim_done:
            e.ai[1] = 0x3C
            s = next_seed(g)
            e.target_anim = 0
            e.bytes[1] = hi(s, 4) + 4
            if e.bytes[1] == 4:
                entity.spawn_warp_entity(g, e, 1, 0xF3, e.px, e.py, e.pz, e.target_dir)
                return
            d = hi(next_seed(g), 4)
            while d < 0x20:                      # 8 shots all round
                entity.spawn_warp_entity(g, e, 1, 0xF3, e.px, e.py, e.pz, d)
                d += 4
    elif a == 12:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.target_anim = 0
            e.ai[1] = 0xF
            entity.spawn_warp_entity(g, e, 1, 0xF3, e.px, e.py, e.pz, e.target_dir)
    elif a == 9:
        if not e.anim_done: return
        if e.bytes[3]:
            e.ai[1] = 0x12C
            e.ai[5] = 0x1E
            e.target_anim = 0
            e.flags = s32(e.flags & ~3)
            return
        e.target_anim = 0
        e.damaged_tick = 0x5A
        e.ai[4] = 0
        if e.bytes[2] == 0:
            e.ai[1] = 0x14
            e.ai[4] = 1 if not _div(e.hp_max, 4) < e.hp else 2
