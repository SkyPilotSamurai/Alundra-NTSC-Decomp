"""Tick (C) programs of creatures and enemies, ported from the MIT xcasadio
AlundraEngine FunctionTypeC / EntityGameplayManager (addresses are the US EXE's
where checked).  Entity fields: anim_quadrant = AnimationDirection (0 down, 1 up,
2 left, 3 right), anim.done = ForceResetAnimationFlag, ai = AIValues, bytes = Bytes,
delay = DelayOrAngleOrEntityId, item_state = ItemState."""
import random
from combat import direction_to

GRAVITY, COLLIDABLE, ON_ANIM_END = 0x100, 0x80, 0x40
# 0x80028AD8 (US) g_directionFlipTable: a direction turned back from a ledge / wall
FLIP = [24, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 8, 8, 8, 8, 8, 8, 16, 16, 16, 16, 16, 16, 16, 16, 24, 24, 24, 24, 24, 24, 24]
CARDINAL = [0, 16, 8, 24]
OFFSET_X = [0x0, -0x96, -0x126, -0x1a6, -0x21f, -0x27f, -0x2c6, -0x2f1, -0x300, -0x2f1, -0x2c6, -0x27f, -0x21f, -0x1a6, -0x126, -0x96,
            0x0, 0x96, 0x126, 0x1a6, 0x21f, 0x27f, 0x2c6, 0x2f1, 0x300, 0x2f1, 0x2c6, 0x27f, 0x21f, 0x1a6, 0x126, 0x96]
OFFSET_Y = [0x200, 0x1f6, 0x1d9, 0x1aa, 0x16a, 0x11c, 0xc4, 0x64, 0x0, -0x64, -0xc4, -0x11c, -0x16a, -0x1aa, -0x1d9, -0x1f6,
            -0x200, -0x1f6, -0x1d9, -0x1aa, -0x16a, -0x11c, -0xc4, -0x64, 0x0, 0x64, 0xc4, 0x11c, 0x16a, 0x1aa, 0x1d9, 0x1f6]


from gamerng import rnd                      # the game's own generator (seed 0x8009AF70)


def s16(v): return ((v + 0x8000) & 0xFFFF) - 0x8000


# ----------------------------------------------------------------------------- helpers
def rel_pos(a, p):
    """ScriptHelper.CalculateEntityRelativePosition: tile deltas (|dx|, |dy|, |dz|, dx, dy, dz)."""
    ax, ay, _ = a.tile(); px, py, _ = p.tile()
    dx, dy, dz = ax - px, ay - py, getattr(a, 'terrain', 0) - getattr(p, 'terrain', 0)
    return [abs(dx), abs(dy), abs(dz), dx, dy, dz]


def to_player(g, a):
    p = g.player
    return direction_to(p.px - a.px, p.py - a.py)


def stop(a):
    a.sfx = a.sfy = a.fx = a.fy = a.tfx = a.tfy = 0


def try_attack2(rp, direction, xt, yt, zt):
    """TryAttackPlayer2 0x8008048C: is Alundra in the strip in front of `direction`?"""
    if zt < rp[2]: return False
    if direction == 1:
        if xt < rp[0] or rp[4] < 0: return False
        return not yt < rp[1]
    if direction == 0:
        if xt < rp[0] or 0 < rp[4]: return False
        return not yt < rp[1]
    if direction == 2:
        if xt < rp[1] or rp[3] < 0: return False
        return rp[0] <= yt
    if direction == 3:
        if xt < rp[1] or 0 < rp[3]: return False
        return not yt < rp[0]
    return False


def try_front(a, rp, xt, yt, zt):
    return try_attack2(rp, a.anim_quadrant or 0, xt, yt, zt)


def start_flying(g, a, anim, base_delay, chance):
    """StartFlying 0x8007FEF8."""
    a.target_dir = to_player(g, a) if rnd(0x65) < (chance & 0xFF) else rnd(32)
    a.target_anim = anim & 0xFF
    if base_delay: a.ai[1] = rnd(16) + base_delay


def handle_ledge(a, new_anim, z):
    """HandleAnimationDirection: turns back (FLIP) before a drop of more than z."""
    t = getattr(a, 'terrain', 0); mh = getattr(a, 'map_heights', [t, t, t, t])
    zt = z + 1
    tl, tr, bl, br = t - mh[0], t - mh[1], t - mh[2], t - mh[3]
    need_handle = need_skip = need_update = False; ret = 0; d = a.target_dir
    if zt < tl:
        if tr <= zt: need_handle = True
        d = a.target_dir
        if 0xE < ((d - 9) & 0xFFFFFFFF): need_skip = True
        need_update = True
    else:
        need_skip = True
    if need_skip:
        if zt < tr:
            if zt < br:
                d = a.target_dir
                if ((d - 0x11) & 0xFFFFFFFF) < 0xF: need_update = True
                need_handle = True
        else:
            need_handle = True
        if zt < bl:
            if tl <= zt: return 0
            d = a.target_dir
            if d < 0x10: need_update = True
        ret = 0
    if need_update:
        ret = 1
        a.target_anim = new_anim & 0xFF; stop(a); a.target_dir = FLIP[d & 31]
    return ret


def try_attack(a, rp, hrange, vrange):
    """TryAttackPlayer: Alundra within hrange squares in front, on the same line."""
    if vrange < rp[2]: return False
    d = a.anim_quadrant or 0
    if d == 1:
        if rp[0] < 2 and -1 < rp[4] and rp[1] <= hrange: return True
        if 1 < rp[1]: return False
        return not hrange < rp[0]
    if d == 0:
        if rp[0] < 2 and rp[4] < 1 and rp[1] <= hrange: return True
        if 1 < rp[1]: return False
        return not hrange < rp[0]
    if d == 2:
        if rp[1] < 2 and -1 < rp[3] and rp[0] <= hrange: return True
        if 1 < rp[0]: return False
        return rp[1] <= hrange
    if d == 3:
        if rp[1] < 2 and rp[3] < 1 and rp[0] <= hrange: return True
        if 1 < rp[0]: return False
        return not hrange < rp[1]
    return False


def speed_of(a, anim):
    st = a.anim_set(anim) if hasattr(a, 'anim_set') else {}
    return st.get('speed', 0) or 0


def tile_height_ahead(g, a, anim, d):
    """GetEntityTileHeight 0x8003AB54: highest square one animation-step ahead."""
    sp = speed_of(a, anim)
    return g.world.tile_height_at(a, OFFSET_X[d & 31] * sp, OFFSET_Y[d & 31] * sp)


def direction_forced(g, a, new_anim, fallback_anim, zt):
    """UpdateDirectionForced: blocked; turn back if the way ahead is a wall or a drop."""
    diff = tile_height_ahead(g, a, new_anim & 0xFF, a.target_dir) - getattr(a, 'terrain', 0)
    if zt < diff or diff < 1:
        a.target_anim = new_anim & 0xFF; stop(a); a.target_dir = FLIP[a.target_dir & 31]
    else:
        a.target_anim = fallback_anim & 0xFF
    return diff


def boxes_touch(a, p):
    """Entity box against Alundra's attack box (used by IdleLookAround)."""
    if p.box is None: return False
    ox, oy, oz, w, d, h = p.box
    hx, hy, hz = p.px + (ox << 16), p.py + (oy << 16), p.pz + (oz << 16)
    cw, cd, ch = (w << 16) - 1, (d << 16) - 1, (h << 16) - 1
    v = a.mpx - hx
    if (v < 0 and a.size[0] + 1 <= hx - a.mpx) or (v >= 0 and cw + 1 <= v): return False
    v = a.mpy - hy
    if (v < 0 and a.size[1] + 1 <= hy - a.mpy) or (v >= 0 and cd + 1 <= v): return False
    v = a.mpz - hz
    return (v < 0 and hz - a.mpz < a.size[2] + 1) or v < ch + 1


# ----------------------------------------------------------------------------- AIs
def curious_flying(ai, a):
    """C2 AI_UpdateEntityAI_CuriousFlying: hover about, swoop at Alundra in front of it,
    peck (anim 3), flee when he hits back."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        if a.ai[1]: a.ai[1] -= 1; return
        a.ai[1] = 0x50; a.target_anim = 1
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            start_flying(g, a, 1, 0x50, 0x1E); a.bytes[0] = 0
        elif a.bytes[0] == 0 and try_attack(a, rp, 2, 0x100000):
            a.target_anim = 0xD; a.target_dir = to_player(g, a); a.ai[6] = 0; a.ai[7] = 0
        elif not a.force_adjusted:
            handle_ledge(a, 1, 0x200000)
        else:
            direction_forced(g, a, 1, 4, 0x200000)
    elif c == 3:
        a.ai[6] = s16(a.ai[6] + 1)
        if p.touching is a:
            if rnd(3) == 0:
                a.target_anim = 1; a.target_dir = direction_to(a.px - p.px, a.py - p.py)
                a.ai[1] = 0x3C; a.bytes[0] = 1
            else:
                a.target_anim = 0; a.ai[1] = 0x14
        if a.anim.done: a.target_anim = 0; a.ai[1] = 10
    elif c == 6:
        if a.on_ground: a.target_anim = 0; a.ai[1] = rnd(0x29) + 10
    elif c in (7, 0xC):
        if a.anim.done:
            if a.bytes[3] == 0:
                if c == 0xC: a.target_dir = (a.target_dir + 0x10) & 0x1F
                a.target_anim = 0; a.ai[1] = 0x1E; a.bytes[0] = 0
            else:
                a.target_anim = 8; a.flags |= ON_ANIM_END
    elif c == 0xB:
        if a.anim.anim != a.target_anim or not a.on_ground: return
        a.target_anim = 10


def trigger_warp(ai, a):
    """C92 AI_UpdateEntityTriggerWarpBehavior (butterflies and such): flutter up and
    away (sound 0x1D4) when Alundra comes within 3 squares on its level."""
    g = ai.g; rp = rel_pos(a, g.player)
    if a.target_anim == 0:
        if rp[0] < 4 and rp[1] < 4 and rp[5] < 1:
            if not g.player_locked: g.sound(0x1D4)
            a.target_anim = 1; a.target_dir = rnd(7) + 5
    elif a.pz > 0x3BFFFFF:
        ai.destroy(a, 0)


def idle_look_around(ai, a):
    """C91 AI_UpdateEntityAI_IdleLookAround (chickens, cats...): wander, cluck (0x1D6),
    run off for 10 s when Alundra's swing touches it."""
    g = ai.g; p = g.player; rp = rel_pos(a, p)
    if a.target_anim != 2 and boxes_touch(a, p):
        g.sound(0x1D6); a.bytes[0] = 2; a.target_anim = 2
        a.target_dir = direction_to(a.px - p.px, a.py - p.py); a.ai[1] = 600; return
    r = s16(a.ai[4] - 1)
    if a.ai[4] == 0:
        if rp[0] < 9 and rp[1] < 9 and not g.player_locked: g.sound(0x1D6)
        if a.ai[5] == 0: a.ai[5] = 1; r = rnd(0xB) + 0x19
        else: a.ai[5] = 0; r = rnd(0x3D) + 100
    a.ai[4] = r
    c = a.target_anim
    if c == 0:
        if a.ai[1] == 0:
            a.bytes[0] = 1; a.ai[1] = 0x78; a.target_anim = 1
            if rnd(3) == 0: a.target_dir = rnd(32)
        else:
            a.ai[1] = s16(a.ai[1] - 1)
    elif c in (1, 2):
        old = a.ai[1]; a.ai[1] = s16(old - 1); u = a.ai[1] & 0xFFFF
        if old == 1:
            a.target_anim = 0; a.ai[1] = 0x50
        else:
            if (u & 0x3F) == 0 and rnd(3) == 0:
                a.target_dir = (a.target_dir + rnd(0xD) - 6) & 0x1F
            if a.force_adjusted:
                a.bytes[0] = a.target_anim
                direction_forced(g, a, a.bytes[0], 3, 0x200000)
                if a.target_anim == a.bytes[0]:
                    if rnd(2): a.target_dir = (a.target_dir + 0x10) & 0x1F
                else:
                    handle_ledge(a, a.bytes[0], 0x400000)
    elif c == 3 and a.on_ground:
        a.target_anim = a.bytes[0]
def idle_curious(ai, a):
    """C93 AI_UpdateEntityAI_IdleCurious (birds and small creatures): peck about near
    home, chirp now and then, fly off (up to 60 px) when Alundra comes within 3 squares,
    come back when he has gone."""
    g = ai.g; rp = rel_pos(a, g.player)
    if a.target_anim < 10:
        a.target_anim = 10
        a.flags = ((a.flags & ~COLLIDABLE) & ~0x70000) | (1 << 16)
        a.item_state = a.py; a.delay = a.px
        return
    if a.target_anim - 10 < 2:
        r = s16(a.ai[4] - 1)
        if a.ai[4] == 0:
            if rp[0] < 9 and rp[1] < 9 and not g.player_locked: g.sound(0x192)
            if a.ai[5] == 0: a.ai[5] = 1; r = rnd(0xB) + 0xF
            else: a.ai[5] = 0; r = rnd(0x3D) + 100
        a.ai[4] = r
    c = a.target_anim
    if c == 0xB:
        if a.anim.done:
            a.target_anim = 10; a.bytes[0] = (a.bytes[0] - 1) & 0xFF
            a.ai[1] = 100 if a.bytes[0] == 0 else 0x14
    elif c == 10:
        if a.ai[1] == 0:
            n = 0; a.target_anim = 0xB
            if a.bytes[0] == 0: a.bytes[0] = rnd(3) + 3
            else: n = rnd(4)
            if n == 0: a.target_dir = rnd(32)
            dx, dy = abs(a.px - a.delay), abs(a.py - a.item_state)
            if dx < 0x900000 and dy < 0x600000: return
            a.target_dir = direction_to(a.delay - a.px, a.item_state - a.py)
        else:
            if rnd(5) == 0 and 0x31 < (a.ai[1] & 0xFFFF) < 0x3D and rp[0] < 9 and rp[1] < 9: g.sound(0x192)
            a.ai[1] = s16(a.ai[1] - 1)
            if rp[0] > 3 or rp[1] > 3 or rp[5] > 3: return
            a.target_anim = 0xC; a.flags &= ~GRAVITY
            a.target_dir = direction_to(a.px - g.player.px, a.py - g.player.py)
    elif c == 0xC:
        if a.pz > 0x3BFFFFF:
            a.target_anim = 0xD; a.fz = 0; a.px = a.delay; a.py = a.item_state
    elif c == 0xD and rp[0] > 0xD:
        a.target_anim = 10; a.pz = 0; a.flags |= GRAVITY


def idle_skittish(ai, a):
    """C1 AI_UpdateEntityAI_IdleSkittish (small animals): wander, startle and hop away
    when Alundra comes close, die by the shared hurt ending."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        dur = a.ai[1]
        if dur:
            a.ai[1] = s16(dur - 1)
            if dur != 1: return
        if rp[0] < 3 and rp[1] < 3 and rp[2] < 0x200001 and a.bytes[1] == 0:
            a.target_dir = to_player(g, a); a.target_anim = 3; a.bytes[1] = 1; return
        a.target_anim = 1; a.ai[1] = rnd(0x3D) + 0x3C
        if rp[0] < 4 and rp[1] < 4: a.target_dir = to_player(g, a)
        a.bytes[1] = 0
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        if not a.force_adjusted:
            a.target_anim = 0; a.ai[1] = rnd(0x80); a.target_dir = rnd(32); return
        d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = d
        a.target_anim = 0; a.ai[1] = rnd(0x1F) + 0x1E
    elif c == 2:
        if rp[0] < 4 and rp[1] < 4: a.target_anim = 4
    elif c == 3:
        if not a.anim.done: return
        start_flying(g, a, 1, 0x28, 0x14); a.bytes[1] = 0
    elif c == 4:
        if not a.anim.done: return
        a.target_anim = 0; a.ai[1] = 0x1E
    elif c == 7:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 6; a.flags |= ON_ANIM_END; return
        a.target_anim = 0; a.ai[1] = 0x28
    elif 8 <= c <= 14:
        if a.on_ground: a.target_anim = 2
    elif c == 19:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        a.target_anim = 0; a.ai[1] = 0x1E


def ai_6_2(ai, a):
    """C10 AI_UpdateEntityAI_6_2 (0x800685CC, sword-and-shield fighters): guard, step
    around Alundra, strike when he is in front, back off when he swings."""
    g = ai.g; p = g.player
    if g.map.id == 0x99 and a.parent is not None and getattr(a.parent, 'bytes', [0] * 4)[3]:
        ai.destroy(a, -1); return
    rp = rel_pos(a, p); c = a.target_anim

    def end_tail():
        a.target_dir = (a.target_dir + 2) & 0x1C

    def common_reset():
        a.ai[1] = 0x1E; a.bytes[1] = 0; end_tail()

    if c == 0:
        if a.bytes[0] == 0:
            if try_front(a, rp, 2, 6, 0x100000):
                a.bytes[0] = 1; a.ai[1] = 0; return end_tail()
            if a.ai[1] != 0:
                a.ai[1] = s16(a.ai[1] - 1); return end_tail()
            if a.bytes[1] == 0 and rnd(4) != 1: return end_tail()
            state = a.bytes[1]; a.bytes[1] = (state + 1) & 0xFF
            if state in (0, 1, 2):
                if rnd(4) == 0: g.sound(0xCD)
                a.target_anim = 8; a.target_dir = to_player(g, a); return end_tail()
            if state == 3: d = [0, 0x10, 8, 0x18][rnd(4)]
            elif state == 4: d = FLIP[a.target_dir & 31]
            elif state == 5:
                a.target_anim = 0xC; a.ai[1] = 0x78; return end_tail()
            else:
                a.bytes[1] = 0; a.ai[1] = 0; return end_tail()
            a.ai[1] = 0x14; stop(a); a.target_dir = d; return end_tail()
        if not try_front(a, rp, 2, 6, 0x100000):
            if not try_attack2(rp, (a.anim_quadrant or 0) ^ 1, 2, 3, 0x100000):
                a.bytes[1] = 0; a.bytes[0] = 0; a.ai[1] = 0x1E; return end_tail()
        if a.ai[1] != 0:
            a.ai[1] = s16(a.ai[1] - 1); return end_tail()
        a.target_dir = to_player(g, a)
        if p.box is not None and p.cur_attack and p.cur_attack[0] and rp[0] < 5 and rp[1] < 5:
            if rnd(4) == 0: g.sound(0xCD)
            a.target_anim = 3; a.target_dir = to_player(g, a); return common_reset()
        if rp[0] > 2 or rp[1] > 2:
            if rp[0] < 5 and rp[1] < 5:
                k = rnd(5)
                if k in (0, 1): a.target_anim = 8; return end_tail()
                if k in (2, 3): a.ai[1] = 0x14; a.target_anim = 0xC; a.ai[1] = 0x1E; return end_tail()
                a.target_anim = 0xC; a.ai[1] = 0x1E; return end_tail()
            if rp[0] > 6 or rp[1] > 6: return end_tail()
            k = rnd(8)
            if k <= 2: a.target_anim = 0xC; a.ai[1] = 0x3C
            elif k == 3: a.target_anim = 0xC; a.ai[1] = 0x1E
            elif k <= 5: a.target_anim = 4
            else: a.target_anim = 8
            return end_tail()
        k = rnd(8)
        if k == 0: a.target_anim = 0xC; a.ai[1] = 0x14; return end_tail()
        if k == 1: a.target_anim = 0xC; d = a.target_dir; a.ai[1] = 0x3C
        elif k in (2, 3): a.target_anim = 0xC; d = a.target_dir; a.ai[1] = 100
        elif k in (4, 5):
            if rnd(4) == 0: g.sound(0xCD)
            a.target_anim = 7; return end_tail()
        else: d = a.target_dir; a.target_anim = 4
        a.target_dir = (d - 0x10) & 0x1F; return end_tail()
    if c == 5:
        if not a.anim.done: return end_tail()
        if a.bytes[3]:
            a.target_anim = 6; a.flags |= ON_ANIM_END; return end_tail()
        a.bytes[0] = 1; a.target_anim = 0; return common_reset()
    if c in (9, 10):
        if not a.on_ground: return end_tail()
        a.target_anim = 0; a.ai[1] = 0x14; return end_tail()
    if c == 0xC:
        if a.bytes[0] == 0 and try_front(a, rp, 2, 6, 0x100000):
            a.bytes[0] = 1; a.target_anim = 0; return common_reset()
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0 or a.force_adjusted:
            a.target_anim = 0; stop(a)
        else:
            if handle_ledge(a, 0xC, 0x400000) == 0: return end_tail()
            a.target_anim = 0
        return common_reset()
    a.target_dir = (a.target_dir + 2) & 0x1C
    return common_reset()


def ai_1(ai, a):
    """C3 AI_UpdateEntityAI_1 (critters that charge): roam, rest (anim 6), wake when
    Alundra comes within 2 squares and lunge at him (anim 3)."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim

    def lunge():
        a.target_anim = 3; a.target_dir = to_player(g, a); a.ai[1] = 0x78; a.bytes[2] = 0

    if c in (0, 1):
        if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1)
        if a.delay: a.delay -= 1
        if a.ai[1] == 0:
            a.target_anim = 6; a.ai[1] = rnd(0x1F) + 0xB4
        if a.delay or rp[0] > 2 or rp[1] > 2 or rp[2] > 0x100000:
            if a.force_adjusted:
                d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = d; return
            handle_ledge(a, 1, 0); return
        lunge()
    elif c == 3:
        if p.touching is a: a.bytes[2] = 1
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            if a.bytes[2] == 0:
                a.target_anim = 1
                if rnd(3) == 0: a.target_dir = (a.target_dir + 0x10) & 0x1F
                a.ai[1] = 0x3C; a.delay = 0x3C
            else:
                a.delay = 0; a.target_anim = 6; a.ai[1] = rnd(0x1F) + 0xB4
    elif c == 4:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 5
        if rp[0] < 3 and rp[1] < 3 and rp[2] < 0x100001: a.target_anim = 5; a.bytes[1] = 3
    elif c == 5:
        if a.anim.done:
            if a.bytes[1] == 3:
                a.target_anim = 3; a.target_dir = to_player(g, a); a.ai[1] = 0x78; a.bytes[2] = 0; a.bytes[1] = 0
            else:
                start_flying(g, a, 1, 0x78, 0x14)
    elif c == 8:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 2; a.flags |= ON_ANIM_END; return
        lunge()


def push_side(e1, e2):
    """FUN_80080990: which side of e2 is e1 on (0 down, 1 up, 2 left, 3 right; -1 none)."""
    if e1.mpx < e2.mpx: val, d = e1.size[0], e2.mpx - e1.mpx
    else: val, d = e2.size[0], e1.mpx - e2.mpx
    if val >= d: return 1 if e2.py < e1.py else 0
    if e1.mpy < e2.mpy: val, d = e1.size[1], e2.mpy - e1.mpy
    else: val, d = e2.size[1], e1.mpy - e2.mpy
    if d <= val: return 3 if e1.px <= e2.px else 2
    return -1


def pushable(ai, a):
    """C69 AI_FUN_8007B6EC (ice pillars, blocks): pushed against for 20 frames it slides
    one way until it is blocked."""
    p = ai.g.player
    if a.target_anim == 0:
        if a.x_collision is p or p.x_collision is a:
            a.delay += 1
            if a.delay != 0x14: return
            a.delay = 0; a.target_anim = 1
            i = push_side(p, a)
            a.target_dir = 0x18 if i == -1 else [0, 0x10, 8, 0x18][i]
            return
        a.delay = 0
    elif a.target_anim == 1 and a.force_adjusted:
        a.target_anim = 0


def carried_hits(ai, a):
    """C70 AI_FUN_8007B7B0: a carried object that hurts enemies when thrown."""
    if a.platform is None: return
    if a.flags2 == 0: a.target_anim = 0; return
    a.target_anim = 3 if a.flags2 == -1 else [0, 3, 1, 4][a.flags2 & 3]
    if getattr(a.platform, 'carried', None) is a: a.platform.carried = None
    a.platform = None; a.flags2 = 0
    a.flags = (a.flags | 0x4 | 0x10 | 0x20) & ~COLLIDABLE


SPAWN_OFF = [(0, 0x40000), (0, -0x40000), (-0x70000, 0), (0x70000, 0)]   # 0x80027440 per facing


def can_move_forward(a, z):
    """CanMoveForward: 1 when the next step would go off a ledge higher than z."""
    zt = z + 1; f = getattr(a, 'floor', a.pz); mh = getattr(a, 'map_heights', [f, f, f, f])
    h0, h1, h2, h3 = f - mh[0], f - mh[1], f - mh[2], f - mh[3]
    d = a.target_dir & 31; u = lambda x: x & 0xFFFFFFFF
    south = True
    if zt < h0:
        south = False
        if zt < h1:
            if u(d - 9) < 0xF: return 1
            south = True
    skip = False
    if south and zt < h1:
        if h3 <= zt: skip = True
        elif u(d - 0x11) < 0xF: return 1
    if not skip and zt < h3:
        if h2 <= zt: return 0
        if 0x10 < u(d - 8): return 1
    r = 0
    if h2 <= zt or zt < h0:
        r = 0 if 0xF < d else 1
    return r


def ai_17(ai, a):
    """C26 AI_UpdateEntityAI_17 (spore plants / spitters): wander; when Alundra comes
    within 2 squares turn and spit a projectile (map sprite 0x4A) at him."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        st = a.ai[1]; a.ai[1] = s16(st - 1)
        if st > 0: return
        if rp[0] < 3 and rp[1] < 3 and rp[2] < 0x200001 and a.bytes[1] == 0:
            a.target_dir = to_player(g, a); a.target_anim = 3; a.bytes[1] = 1; a.ai[1] = 0x37; return
        a.target_anim = 1; a.ai[1] = rnd(0x3D) + 0x3C
        if rp[0] < 4 and rp[1] < 4: a.target_dir = to_player(g, a)
        a.bytes[1] = 0
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        if not a.force_adjusted:
            a.target_anim = 0; a.ai[1] = rnd(0x80); a.target_dir = rnd(32); return
        d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = d; a.ai[1] = rnd(0x1F) + 0x1E
    elif c == 2:
        if rp[0] <= 3 and rp[1] <= 3: a.target_anim = 4
    elif c == 3:
        st = a.ai[1]; a.ai[1] = s16(st - 1)
        if st == 0:
            q = a.anim_quadrant or 0; ox, oy = SPAWN_OFF[q]
            e = g.spawn_sprite(a, True, 0x4A, a.px + ox, a.py + oy, a.pz + 0xA0000, [0, 0x10, 8, 0x18][q])
            if e is not None: e.fz = 0x20000
        if not a.anim.done: return
        start_flying(g, a, 1, 0x28, 0x1E); a.bytes[1] = 0
    elif c == 4:
        if not a.anim.done: return
        a.target_anim = 0; a.ai[1] = 0x1E
    elif c == 7:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 6; a.flags |= ON_ANIM_END; return
        a.target_anim = 0; a.ai[1] = 0x28


def ai_20(ai, a):
    """C29 AI_UpdateEntityAI_20 (archers / spear throwers): look about; when Alundra is
    in front within 5 squares, shoot (map sprite 0x9B) then burrow / reposition."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        if a.bytes[2] == 0 and try_front(a, rp, 1, 5, 0x200000):
            a.target_anim = 3; a.target_dir = to_player(g, a); a.ai[1] = 0x3B; return
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl != 1: return
        ph = a.bytes[0]; a.bytes[0] = (ph + 1) & 0xFF
        q = a.anim_quadrant or 0
        if ph == 0: a.ai[1] = 0x14; a.target_dir = ([0, 0x10, 8, 0x18][q] + 8) & 0x1F
        elif ph == 1: a.ai[1] = 0x14; a.target_dir = ([0, 0x10, 8, 0x18][q] + 0x10) & 0x1F
        elif ph == 2: start_flying(g, a, 1, 0x78, 0x14); a.bytes[2] = 0; a.bytes[0] = 0
        else: a.bytes[0] = 0
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 5; return
        if not a.force_adjusted and can_move_forward(a, 0) == 0: return
        stop(a); a.target_dir = (a.target_dir + rnd(0x18) + 1) & 0x1F
    elif c == 2:
        if a.ai[1] == 0: a.ai[1] = 0x78
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 4
    elif c == 3:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl == 1:
                off = {0: (0, 0x60000), 1: (0, -0x60000), 2: (-0xC0000, 0), 3: (0xC0000, 0)}[a.anim_quadrant or 0]
                g.spawn_sprite(a, True, 0x9B, a.px + off[0], a.py + off[1], a.pz + 0x140000, a.target_dir)
        if a.anim.done: a.target_anim = 5; a.bytes[2] = 1
    elif c == 4:
        if not a.anim.done: return
        a.target_anim = 0; a.ai[1] = 0x14; a.bytes[0] = 0
    elif c == 5:
        if a.anim.done:
            if a.bytes[1]:
                a.bytes[1] = 0; a.px += a.delay; a.py += a.item_state
            a.target_anim = 2
    elif c == 7:
        if a.anim.done:
            if a.bytes[3] == 0: a.target_anim = 5; a.ai[1] = 0; a.bytes[1] = 0
            else: a.target_anim = 8; a.flags |= ON_ANIM_END


def set_random_direction(g, a, anim, delay):
    """SetEntityRandomDirection 0x80080030: half the time toward Alundra."""
    a.target_dir = rnd(32) if rnd(2) == 0 else to_player(g, a)
    a.target_anim = anim & 0xFF
    if delay: a.ai[1] = rnd(16) + delay


def ai_0(ai, a):
    """C5 AI_UpdateEntityAI_0 (hopping biters): wander for 4 s, bite (anim 3) when
    Alundra is within 2 squares or in a line up to 6 squares ahead, rest after a bite."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    phase = None
    if c == 0:
        if not a.on_ground: return
        if ((a.bytes[1] - 3) & 0xFF) > 4:
            a.ai[1] = 0; a.bytes[1] = 0; c = 1
        else:
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1] > 0: return
            a.target_dir = to_player(g, a); a.target_anim = 3; a.delay = 0
            if a.bytes[1] == 6: a.bytes[1] = 0; return
            a.bytes[1] = (a.bytes[1] + 1) & 0xFF; return
    if c == 1:
        if a.item_state: a.item_state -= 1
        if a.ai[1]:
            a.ai[1] = s16(a.ai[1] - 1)
            if a.force_adjusted: direction_forced(g, a, 1, 4, 0x100000); return
            if a.item_state or rp[0] > 2 or rp[1] > 2 or rp[2] > 0x100000: return
            a.target_dir = to_player(g, a)
            if a.bytes[1] == 1: a.target_anim = 3; a.delay = 0; return
            if a.bytes[1] != 2: return
            a.bytes[1] = 7; a.ai[1] = 0x3C; a.target_anim = 0; return
        a.target_anim = 1; a.ai[1] = 0xF0
        if try_attack(a, rp, 6, 0x100000):
            a.target_dir = to_player(g, a); a.bytes[1] = 1; return
        start_flying(g, a, 1, 0xB4, 0x14); a.bytes[1] = 2; return
    if c == 3:
        if p.touching is a: a.delay = 1
        if not a.anim.done: return
        if a.delay:
            a.target_anim = 0; a.ai[1] = 0x1E; a.delay = 0; return
        set_random_direction(g, a, 1, 0x78); a.item_state = a.ai[1]; return
    if c in (6, 0xB):
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 7; a.flags |= ON_ANIM_END; return
        a.ai[1] = 10; a.target_anim = 0; a.target_dir = (a.target_dir + 0x10) & 0x1F
        if ((a.bytes[1] - 3) & 0xFF) < 4: return
        a.bytes[1] = 3


def ai_10(ai, a):
    """C15 AI_UpdateEntityAI_10 (patrollers): walk a square path, turning when blocked;
    attack three times (anim 3) when Alundra is right in front."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    card = [0, 0x10, 8, 0x18]; q = a.anim_quadrant or 0
    if c in (0, 1):
        if a.bytes[0] == 0:
            if a.bytes[1] == 0:
                a.bytes[1] = 4; stop(a); a.target_dir = (card[q] - 8) & 0x1F
            dl = a.ai[1]; a.target_anim = 1
            if dl == 0:
                a.ai[1] = 0x1E
                if try_front(a, rp, 2, 2, 0):
                    if rnd(5) == 0: g.sound(0x94)
                    a.bytes[0] = 3
            else:
                a.ai[1] = s16(dl - 1)
                if a.force_adjusted:
                    b1 = a.bytes[1]; stop(a); a.bytes[1] = (b1 - 1) & 0xFF
                    a.target_dir = (card[q] - 0x10) & 0x1F
        else:
            a.target_anim = 3; a.target_dir = to_player(g, a)
    elif c == 3:
        if a.anim.done:
            a.bytes[0] = (a.bytes[0] - 1) & 0xFF
            if a.bytes[0] == 0:
                a.target_anim = 0; a.ai[1] = 0; a.bytes[1] = 0; a.target_dir = rnd(4) << 3
            else:
                a.cur_anim = -1                         # CurrentAnimationId = -1: play it again
    elif c in (5, 6):
        if a.anim.done:
            if a.bytes[3] == 0:
                if rp[0] < 2 and rp[1] < 2: a.bytes[0] = 3
                a.target_anim = 0
            else:
                a.target_anim = 2; a.flags |= ON_ANIM_END


def ai_69f44(ai, a):
    """C16 AI_FUN_80069F44 (scuttlers): roam in bursts, charge (anim 7) when Alundra is
    3 squares in front, kick up dust (map effect C) while running."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim

    def charge():
        a.target_anim = 7; a.target_dir = to_player(g, a); a.ai[6] = 0; a.ai[7] = 0

    if c == 0:
        if a.ai[1] == 0: start_flying(g, a, 1, 0x78, 0x46); a.bytes[1] = 0
        else: a.ai[1] = s16(a.ai[1] - 1)
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            if a.bytes[1] == 0:
                a.target_anim = 0; a.ai[1] = 0x14; a.bytes[0] = 0; return
            a.bytes[1] = (a.bytes[1] - 1) & 0xFF; a.ai[1] = 0x78; a.target_dir = rnd(32)
            return
        if try_front(a, rp, 3, 3, 0):
            if rnd(5) == 0: g.sound(0x94)
            return charge()
        if not a.force_adjusted: return
        if a.bytes[1] == 0:
            a.bytes[0] = (a.bytes[0] + 1) & 0xFF
            if a.bytes[0] < 4: a.target_anim = 0; return
            a.bytes[0] = 0; a.ai[1] = 0x78; a.bytes[1] = 3
        else:
            a.bytes[1] = (a.bytes[1] - 1) & 0xFF; a.ai[1] = 0x78
        a.target_dir = rnd(32)
    elif c == 3:
        a.ai[6] = s16(a.ai[6] + 1)
        if (a.ai[6] & 7) == 0:
            eff = g.map.data.get('info', {}).get('c', 0)
            if eff: g.effects.create(False, eff, 0, a.px, a.py, getattr(a, 'floor', a.pz))
        if a.anim.done: a.target_anim = 0; a.ai[1] = 0x1E
    elif c == 5:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 2; a.flags |= ON_ANIM_END; return
        charge()
    elif c == 6:
        if a.anim.done:
            a.target_anim = 0; a.ai[1] = 0x14; a.target_dir = (a.target_dir + 0x10) & 0x1F


def magic_pot(ai, a):
    """C74 MagicPotTick (bounce pads): steam while idle; sinks under Alundra and launches
    him at 9.5 px/frame when he jumps off it."""
    g = ai.g; p = g.player; c = a.target_anim
    rest = getattr(a, 'rest_z', a.pz)
    if c == 1:
        if (g.frame_no & 3) == 0:
            e = g.effects.create(False, 0x0E, 0, a.px, a.py, a.pz)
            if e: e.vx = rnd(0x30001) - 0x18000; e.vy = rnd(0x20001) - 0x10000; e.vz = 0x20000
    elif c == 2:
        a.fz = (rest - a.pz) >> 1
        if p.riding is a: a.fz = -0x8000; a.target_anim = 3
    elif c == 3:
        if p.riding is not a: a.target_anim = 2
    elif c == 4:
        if p.riding is a: return
        if p.fz > 0: p.fz = 0x98000; a.target_anim = 5
        else: a.target_anim = 2
    elif c == 5:
        a.fz = (rest - a.pz) >> 1


def ai_12(ai, a):
    """C19 AI_UpdateEntityAI_12 (jumpers): wander; when Alundra is near, pause then
    leap at him (anim 3); thud on landing (0x96)."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 1:
        if rp[0] < 3 and rp[1] < 3 and rp[2] < 0x100001:
            a.bytes[0] = 1; a.target_anim = 0; a.ai[1] = rnd(16) + 0x3C; return
        if not a.force_adjusted and can_move_forward(a, 0) == 0: return
        a.target_anim = 0; a.ai[1] = 0x3C; a.target_dir = rnd(32); return
    if c == 0:
        if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1); return
        if a.bytes[0] == 0: a.target_anim = 1; return
        a.target_dir = to_player(g, a); a.target_anim = 3
    elif c == 5:
        if not a.on_ground: return
        a.target_anim = 0; a.ai[1] = 0x14; g.sound(0x96); return
    elif c == 7:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 8; a.flags |= ON_ANIM_END; return
        a.target_anim = 0; a.ai[1] = 0x14
    else:
        return
    a.bytes[0] = 0


def ai_4(ai, a):
    """C7 AI_UpdateEntityAI_4 (slimes that split): patrol, chase when Alundra is in
    front, burrow (anim 5/2), strike (anim 3); on death burst into four small ones
    (map sprite 0x91)."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    card = [0, 0x10, 8, 0x18]; q = a.anim_quadrant or 0
    if c == 0:
        if a.bytes[1] == 0: a.bytes[1] = 10
        if a.ai[1]:
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1]: return
        if a.bytes[1] == 10 and try_front(a, rp, 1, 2, 0):
            a.target_dir = to_player(g, a); a.target_anim = 3; a.bytes[1] = 0; return
        b = a.bytes[1]
        if not (10 <= b < 17 or b in (0x14, 0x15)): return
        if try_front(a, rp, 2, 6, 0):
            a.target_dir = to_player(g, a); a.target_anim = 1; a.ai[1] = 0x78; return
        a.bytes[1] = (b + 1) & 0xFF; b = a.bytes[1]
        if b in (0x0B, 0x0E):
            a.ai[1] = 0x28; stop(a); a.target_dir = (card[q] - 8) & 0x1F
        elif b in (0x0C, 0x0F, 0x15):
            a.ai[1] = 0x28; stop(a); a.target_dir = (card[q] + 0x10) & 0x1F
        elif b == 0x0D:
            start_flying(g, a, 1, 0x78, 0x1E)
        elif b in (0x10, 0x16):
            a.target_anim = 5
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 0; return
        if a.force_adjusted:
            d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = d
        else:
            z = getattr(a, 'floor', 0) - getattr(p, 'floor', 0)
            if z >= 0: handle_ledge(a, 1, z)
        if a.bytes[1]: return
        if try_front(a, rp, 1, 2, 0):
            a.target_dir = to_player(g, a); a.target_anim = 3; a.bytes[1] = 0
    elif c == 2:
        if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1)
        if a.bytes[1]: return
        if rp[0] < 3 and rp[1] < 3 and rp[2] <= 0:
            a.target_anim = 4; a.bytes[1] = 10; return
        if a.ai[1] == 0: a.target_anim = 4; a.bytes[1] = 0x14
    elif c == 3:
        if p.touching is a: a.bytes[1] = (a.bytes[1] + 1) & 0xFF
        if not a.anim.done: return
        if a.bytes[1] & 0xF:
            a.target_dir = to_player(g, a); a.target_anim = 0; a.bytes[1] = 10; a.ai[1] = rnd(8) + 0x14; return
        if try_front(a, rp, 1, 1, 0):
            a.target_dir = to_player(g, a)
            if a.bytes[1] == 0: a.target_anim = 3; a.cur_anim = -1; a.bytes[1] = 0x80
            else: a.target_anim = 1; a.bytes[1] = 0; a.ai[1] = 0x14
            return
        a.target_anim = 0; a.bytes[1] = 10; a.ai[1] = rnd(16) + 0x14
    elif c == 4:
        if not a.anim.done or a.bytes[1] not in (10, 0x14): return
        a.target_dir = to_player(g, a); a.target_anim = 0; a.ai[1] = rnd(16) + 0x14
    elif c == 5:
        if a.anim.done: a.target_anim = 2; a.bytes[1] = 0; a.ai[1] = 0x78
    elif c == 7:
        if not a.anim.done: return
        if a.bytes[3]:
            a.target_anim = 8; a.ai[1] = 8; a.flags |= ON_ANIM_END; return
        if rnd(4) == 1: a.target_anim = 5; return
        a.bytes[1] = 0; a.ai[1] = 0; a.target_anim = 0
        e = g.spawn_sprite(a, True, 0x91, a.px, a.py, a.pz + 0x1000000, card[rnd(4)])
        if e is not None:
            e.sprite_programs = dict(e.sprite_programs); e.sprite_programs['A'] = 0
            e.target_anim = 0xB; e.contents_item = 0
    elif c == 8:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        for k in range(4):
            e = g.spawn_sprite(a, True, 0x91, a.px, a.py, a.pz + 0x1000000, 4 + 8 * k)
            if e is not None:
                e.sprite_programs = dict(e.sprite_programs); e.sprite_programs['A'] = 0
                e.target_anim = 0xB; e.contents_item = 0
    elif c == 10:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: g.sound(0x40); ai.destroy(a, -1)
    elif c == 11:
        if a.on_ground: a.target_anim = 10; a.ai[1] = 0x3C


def ai_21(ai, a):
    """C32/C34 AI_UpdateEntityAI_21 (hammer / boulder throwers): roam toward Alundra;
    when he is in front or close, rear back (anim 2) and throw (map sprite 0x6E for C32,
    0x74 bouncing rocks otherwise)."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    tick = (getattr(a, 'sprite_programs', {}) or {}).get('C', 0)
    if c == 0:
        if a.ai[1] == 0:
            a.target_anim = 1; a.ai[1] = rnd(0x20) + 0x78
            if (rp[0] < 0xF or rp[1] < 0xF) and rp[2] < 0x700000:
                a.target_dir = to_player(g, a); a.ai[1] = s16(a.ai[1] + 0x28)
            else:
                a.target_dir = rnd(32)
        else:
            a.ai[1] = s16(a.ai[1] - 1)
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 0; a.ai[1] = rnd(16) + 0x3C; return
        if not try_front(a, rp, 1, 4, 0x100000) and (rp[0] > 2 or rp[1] > 2 or rp[2] > 0x10000):
            if a.force_adjusted: direction_forced(g, a, 1, 4, 0x200000)
            else: handle_ledge(a, 1, 0x200000)
            return
        a.target_anim = 2; a.target_dir = direction_to(a.px - p.px, a.py - p.py)
    elif c == 3:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl == 1:
                q = a.anim_quadrant or 0
                if tick == 0x20:
                    ox, oy = [(0, -0x40000), (0, 0x40000), (-0xE0000, 0), (0xE0000, 0)][q]
                    g.spawn_sprite(a, True, 0x6E, a.px + ox, a.py + oy, a.pz + 0xA0000, a.target_dir)
                else:
                    ox, oy = [(0, 0xE0000), (0, -0xE0000), (-0x150000, 0), (0x150000, 0)][q]
                    e = g.spawn_sprite(a, True, 0x74, a.px + ox, a.py + oy, a.pz + 0xA0000, a.target_dir)
                    if e is not None:
                        d = rnd(3)
                        e.target_anim = d + 1 if d else 0; e.fz = 0x38000
        if a.anim.done: a.target_anim = 0; a.ai[1] = 0x78
    elif c == 5:
        if not a.on_ground: return
        a.target_anim = 3; a.ai[1] = 0xF; a.target_dir = (a.target_dir + 0x10) & 0x1F
    elif c == 6:
        if a.on_ground: a.target_anim = 1
    elif c == 9:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 8; a.flags |= ON_ANIM_END; return
        a.target_anim = 2; a.target_dir = direction_to(a.px - p.px, a.py - p.py)
    elif c == 10:
        if not a.anim.done: return
        a.target_anim = 0; a.ai[1] = 0x1E; a.target_dir = (a.target_dir + 0x10) & 0x1F
    elif c == 11:
        if a.anim.anim == a.target_anim and a.on_ground: a.target_anim = 10


def ai_19(ai, a):
    """C28 AI_UpdateEntityAI_19 (lizard men / spear fighters): hop about; stab (anim 3)
    when Alundra is 2 squares in front, throw (map sprite 0xD4) from up to 6."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        if a.on_ground:
            if a.ai[1] == 0: a.ai[1] = 0x3C
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1] == 0:
                if a.bytes[1] == 0:
                    a.target_dir = (a.target_dir + rnd(0x1F) + 1) & 0x1F
                    if a.bytes[0] == 3: a.target_anim = 9; a.bytes[0] = 0
                    else: a.target_anim = 1; a.bytes[1] = 4
                else:
                    a.target_anim = 1; a.target_dir = rnd(32)
    elif c == 1:
        if a.anim.done:
            a.bytes[1] = (a.bytes[1] - 1) & 0xFF
            a.target_anim = 0; a.ai[1] = rnd(16) + 0x1E
            if a.bytes[1] == 0: a.bytes[0] = (a.bytes[0] + 1) & 0xFF
        elif try_front(a, rp, 2, 3, 0x300000):
            a.target_anim = 3; a.target_dir = to_player(g, a); a.bytes[2] = 1
        elif try_front(a, rp, 1, 6, 0x300000):
            a.target_anim = 4; a.ai[1] = 0x18
        elif not a.force_adjusted: handle_ledge(a, 1, 0x300000)
        else: direction_forced(g, a, 1, 9, 0x300000)
    elif c == 4:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl == 1:
                ox, oy = [(0, 0x40000), (0, -0x40000), (-0x40000, 0), (0x40000, 0)][a.anim_quadrant or 0]
                e = g.spawn_sprite(a, True, 0xD4, a.px + ox, a.py + oy, a.pz, (to_player(g, a) + 2) & 0x1C)
                if e is not None: e.anim_quadrant = a.anim_quadrant
    elif c == 6:
        if a.anim.done:
            if a.bytes[3]: a.target_anim = 7; a.flags |= ON_ANIM_END
            else: a.target_anim = 0; a.bytes[2] = 0; a.ai[1] = rnd(16) + 0x20
    elif c == 8:
        if a.on_ground:
            if a.bytes[2]:
                a.target_anim = 9; a.target_dir = direction_to(a.px - p.px, a.py - p.py); a.bytes[2] = 0
            else:
                a.target_anim = 0; a.ai[1] = 0x28
    a.target_dir = (a.target_dir + 2) & 0x1C


def player_swinging(p):
    return p.box is not None and p.cur_attack and p.cur_attack[0]


def ai_3(ai, a):
    """C6 AI_UpdateEntityAI_3 (grazing creatures): wander; turn back at walls/ledges;
    rush (anim 3) when Alundra is up to 4 squares ahead; sometimes drop something when
    hurt but not killed."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        if a.ai[1] == 0: a.target_anim = 1; a.ai[1] = 1
        else: a.ai[1] = s16(a.ai[1] - 1)
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: set_random_direction(g, a, 1, 0xF0)
        elif a.force_adjusted:
            direction_forced(g, a, 1, 2, 0x100000)
            if a.target_anim == 1: a.target_anim = 0
            a.ai[1] = 0x3C
    elif c == 2:
        if a.on_ground: a.target_anim = 1
    elif c == 3:
        if a.anim.done: a.target_anim = 1; a.target_dir = to_player(g, a); a.ai[1] = 300
    elif c == 4:
        if try_attack(a, rp, 4, 0x100000): a.target_anim = 3
    elif c == 6:
        if a.anim.done:
            if a.bytes[3] == 0:
                if rnd(4) == 0: ai.drop_contents(a)
                a.target_anim = 0; a.ai[1] = 0x1E
            else:
                a.target_anim = 7; a.flags |= ON_ANIM_END


def ai_7(ai, a):
    """C11 AI_UpdateEntityAI_7 (skittish fliers): keep away from Alundra while he is
    within 5 squares; when he swings, dodge (anim 3) and dart off (anim 4) up to 10 times."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    near = not (rp[0] > 5 or rp[1] > 5 or rp[2] > 0x100000)

    def dodge(): a.target_anim = 3; a.bytes[1] = 10

    if c == 0:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl != 1: return
        if not near: set_random_direction(g, a, 1, 300); return
        if not player_swinging(p):
            a.target_dir = direction_to(a.px - p.px, a.py - p.py); a.target_anim = 1; a.ai[1] = 300; return
        dodge()
    elif c == 1:
        if not near or not player_swinging(p):
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1] != 0 and not a.force_adjusted:
                if handle_ledge(a, 1, 0x200000) == 0: return
            a.target_anim = 0; a.ai[1] = 0x3C; return
        dodge()
    elif c == 3:
        if a.anim.done:
            d = to_player(g, a); off = rnd(9) - 4
            a.target_anim = 4; a.ai[1] = 0x3C; a.bytes[1] = (a.bytes[1] - 1) & 0xFF
            a.target_dir = (d + off) & 0x1F
    elif c == 4:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] != 0 and not a.force_adjusted:
            if handle_ledge(a, 4, 0x200000) == 0: return
        a.bytes[1] = (a.bytes[1] - 1) & 0xFF
        if a.bytes[1]: start_flying(g, a, 4, 0x28, 0x1E); return
        a.target_anim = 5
    elif c == 5:
        if a.anim.done: a.target_anim = 0; a.ai[1] = 0x1E
    elif c == 7:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 2; a.flags |= ON_ANIM_END; return
        if a.bytes[1] == 0: a.bytes[1] = 10
        a.target_anim = 3


def ai_15(ai, a):
    """C25 AI_UpdateEntityAI_15 (spore flowers): wander; close to Alundra, puff spores in
    four directions (map sprite 0xBC); rest (anim 10/3) after a while."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim

    def puff_start():
        a.ai[1] = 0x10; a.bytes[1] = 0

    if c == 0:
        if a.ai[1] != 0: a.ai[1] = s16(a.ai[1] - 1); return
        if rp[0] > 2 or rp[1] > 2: start_flying(g, a, 1, 0x3C, 100); return
        a.target_anim = 5; a.target_dir = to_player(g, a); puff_start()
    elif c == 1:
        st = a.item_state - 1
        if a.item_state != 0:
            a.item_state = st
            if st != 0 or rp[0] > 2 or rp[1] > 2:
                a.ai[1] = s16(a.ai[1] - 1)
                if a.ai[1] != 0:
                    if a.force_adjusted:
                        a.bytes[0] = (a.bytes[0] + 1) & 0xFF; direction_forced(g, a, 1, 2, 0x100000); return
                    handle_ledge(a, 1, 0x100000); return
                v0 = a.bytes[0]; a.bytes[1] = (a.bytes[1] + 1) & 0xFF
                if v0 < 3 and a.bytes[1] < 5: set_random_direction(g, a, 1, 0x3C); return
                a.target_anim = 10; a.bytes[1] = 0; a.bytes[0] = 0; return
        a.target_anim = 5; puff_start()
    elif c == 3:
        if rp[0] < 5 and rp[1] < 5 and rp[2] < 0x100001: a.target_anim = 4
    elif c == 4:
        if a.anim.done: a.target_anim = 0
    elif c == 5:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl == 1:
                z = a.pz + 0x200000
                for k in range(4): g.spawn_sprite(a, True, 0xBC, a.px, a.py, z, (a.target_dir + 8 * k) & 0x1F)
        if not a.anim.done: return
        if a.delay == 0 and rnd(4) == 0:
            a.cur_anim = -1; a.ai[1] = 0x10; a.delay = 1; return
        a.delay = 0; a.target_anim = 1; a.item_state = 0x1E; a.ai[1] = rnd(16) + 0x1E
    elif c == 7:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 8; a.flags |= ON_ANIM_END; return
        a.target_anim = 0; a.ai[1] = 0x28
    elif c == 10:
        if a.anim.done: a.target_anim = 3


def rel_floor(a, p):
    """FUN_8007FE8C: like rel_pos but with floor heights (flying things)."""
    ax, ay, _ = a.tile(); px, py, _ = p.tile()
    dx, dy, dz = ax - px, ay - py, getattr(a, 'floor', 0) - getattr(p, 'floor', 0)
    return [abs(dx), abs(dy), abs(dz), dx, dy, dz]


def ai_6(ai, a):
    """C9 AI_UpdateEntityAI_6 (bats / hovering things): flit about; dive to Alundra's
    height when he is in front (anim 9); swoop (anim 3, sound 0x1CD) when he is close."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    if c == 0:
        a.bytes[0] = 0
        if a.ai[1] == 0: a.ai[1] = 0x78
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            if try_front(a, rp, 1, 3, 0x800000):
                z = a.pz - getattr(p, 'floor', p.pz)
                if z > 0x100000:
                    a.target_anim = 9; a.ai[1] = s16(z >> 15); a.fz = -0x8000; return
                if z < -0x100000:
                    a.target_anim = 9; a.ai[1] = s16(abs(z) >> 15); a.fz = 0x8000; return
            if rp[0] < 7 and rp[1] < 7 and rnd(3) == 0:
                a.target_anim = 1; a.target_dir = to_player(g, a); a.ai[1] = 0x28; a.bytes[1] = 1
            else:
                start_flying(g, a, 1, 0x1E, 0x28); a.bytes[1] = 0
        elif rp[0] < 3 and rp[1] < 3:
            a.target_anim = 3; a.target_dir = to_player(g, a); a.ai[1] = 0x6E; a.bytes[2] = 0; a.bytes[0] = 1
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] != 0:
            if not a.force_adjusted: return
            b = a.bytes[1]; a.ai[1] = 0
            if b == 0:
                a.target_anim = 0; d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = d; return
            z = direction_forced(g, a, 1, 9, 0x500000)
            if a.target_anim == 9: a.ai[1] = s16(z >> 15); return
        a.target_anim = 0
    elif c == 3:
        v = a.ai[1]
        if v == 0 or a.bytes[2]: return
        a.ai[1] = s16(v - 1)
        if v != 1: return
        g.sound(0x1CD); a.bytes[2] = 1; a.ai[1] = 1
    elif c in (5, 7):
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 2; a.flags |= ON_ANIM_END; return
        a.target_anim = 0; a.ai[1] = 0x1E
    elif c == 9:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: set_random_direction(g, a, 1, 0x78); a.bytes[1] = 0; a.fz = 0


def ai_a564(ai, a):
    """C18 AI_FUN_8006A564 (floating eyes / wisps): drift at their own height band
    (anims 1-3 up/level/down), turn to face Alundra and charge when he is in front."""
    g = ai.g; p = g.player; rp = rel_floor(a, p); c = a.target_anim

    def lock_on():
        a.target_anim = 0; a.target_dir = to_player(g, a); a.ai[1] = 0; a.bytes[0] = 10

    if c == 0:
        if a.bytes[0] == 0:
            v = a.ai[1]
            if v == 0:
                if rp[0] < 3 and rp[1] < 3 and rp[2] < 0x200001:
                    a.target_dir = to_player(g, a); a.ai[1] = 0x3C; return
                a.target_dir = rnd(32)
                z = a.pz - a.ai[0] * 0x10000
                a.ai[1] = rnd(0x29) + 0x50
                if z > 0x4FFFFF: a.target_anim = 3; return
                if z > -0x500000: a.target_anim = rnd(3) + 1; return
            else:
                a.ai[1] = s16(v - 1)
                if v != 1: return
                a.ai[1] = 0x78
                if rp[5] > 0xFFFFF:
                    a.target_anim = 1 if (rp[5] < 0x180001 or a.on_ground) else 3; return
        else:
            a.target_dir = to_player(g, a); a.ai[1] = 0x3C; a.bytes[0] = (a.bytes[0] - 1) & 0xFF
            if rp[5] > 0xFFFFF:
                a.target_anim = 1 if rp[5] < 0x180001 else 3; return
        a.target_anim = 2
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 0
        if a.bytes[0]: return
        if not try_front(a, rp, 1, 4, 0x200000):
            if not a.force_adjusted: return
            a.target_dir = (a.target_dir + 4) & 0x1F
        lock_on()
    elif c in (2, 3):
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0 or (c == 3 and a.on_ground): a.target_anim = 0
        if a.bytes[0] == 0 and try_front(a, rp, 1, 4, 0x200000): lock_on()
    elif c == 5:
        if a.anim.done:
            if a.bytes[3] == 0: a.target_anim = 0; a.bytes[0] = 0; a.ai[1] = 0
            else: a.target_anim = 6; a.flags |= ON_ANIM_END


def ai_9(ai, a):
    """C14 AI_UpdateEntityAI_9 (chargers): patrol; dodge back (anim 8) when Alundra
    swings nearby; charge (anim 3) when he is up to 8 squares straight ahead."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim
    card = [0, 0x10, 8, 0x18]
    if c == 0:
        a.target_anim = 1; a.ai[1] = rnd(16) + 0xB4
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if (a.ai[1] & 0x1F) == 0:
            if rp[0] < 5 and rp[1] < 5 and player_swinging(p):
                a.target_anim = 8; a.target_dir = direction_to(a.px - p.px, a.py - p.py); return
            if try_front(a, rp, 1, 8, 0x100000):
                a.target_dir = to_player(g, a); a.target_anim = 3; a.ai[1] = 0xB4; return
        if a.ai[1] != 0:
            if a.force_adjusted: direction_forced(g, a, 1, 2, 0x300000); return
            handle_ledge(a, 1, 0x300000); return
        a.target_anim = 0; stop(a); a.target_dir = (card[a.anim_quadrant or 0] - 8) & 0x1F
    elif c == 3:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 0; return
        if not a.force_adjusted: return
        a.target_anim = 8; a.target_dir = (a.target_dir - 0x10) & 0x1F
    elif c == 5:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 6; a.flags |= ON_ANIM_END; return
        a.target_anim = 0
    elif c in (7, 9):
        if a.on_ground: a.target_anim = 0


def ai_ce08(ai, a):
    """C30 AI_FUN_8006CE08 (fire birds): soar between a ceiling band (spawn height + 80 px)
    and the ground; when Alundra is in front and below, hover and drop four fireballs
    (map sprite 0xDA, sound 0x171)."""
    g = ai.g; p = g.player; rp = rel_floor(a, p); c = a.target_anim
    if c == 0:
        a.target_anim = 1; a.target_dir = rnd(32); a.ai[1] = rnd(32) + 0x50
    elif c in (1, 7, 8):
        i4 = a.delay - 1
        if i4 >= 0: a.delay = i4
        if (a.delay == 0 or i4 == 0) and a.bytes[1] == 0 and a.bytes[2] == 0 and rp[5] > -1 \
                and try_front(a, rp, 2, 5, 0x400000):
            a.target_anim = 1; a.target_dir = to_player(g, a); a.ai[1] = 0x32; a.bytes[2] = 4; return
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            if a.bytes[2] == 0:
                if a.on_ground: a.target_anim = 7; a.ai[1] = rnd(32) + 0x28; return
                if rnd(3) == 0: a.target_anim = 8; a.ai[1] = 0x1E; return
                d = rnd(32); a.target_anim = 1; a.ai[1] = 100; a.bytes[1] = 0
            else:
                if rnd(3) == 0: g.sound(0x171)
                e = g.spawn_sprite(a, True, 0xDA, a.px, a.py, a.pz + 0x100000, a.target_dir)
                if e is not None: e.fz = -0x10000; e.flags &= ~GRAVITY
                a.bytes[2] = (a.bytes[2] - 1) & 0xFF; a.ai[1] = rnd(16) + 0x32
                if a.bytes[2]: a.target_dir = to_player(g, a); return
                d = rnd(32); a.delay = 0x32
            a.target_dir = d; return
        if c == 7:
            if a.pz - (a.ai[0] & 0xFFFF) * 0x10000 < 0x500000: return
            a.target_anim = 8 if a.pz - getattr(a, 'terrain', 0) > 0x200000 else 1
            a.bytes[0] = 0; a.bytes[1] = 0; a.ai[1] = rnd(32) + 0x28
        elif c == 1:
            if not a.force_adjusted: return
            b = a.bytes[0]; a.ai[1] = 0x28; a.target_dir = rnd(32)
            a.target_anim = 7 if b == 1 else 8
        else:
            z = a.pz - s16(a.ai[0]) * 0x10000
            if z > -0x600000:
                if not a.on_ground: return
                if z > 0x200000:
                    a.target_dir = rnd(32); a.target_anim = 1; a.ai[1] = 0x3C; return
            a.target_anim = 7; a.bytes[0] = 1; a.ai[1] = rnd(0x11) + 0x28
    elif c == 2:
        if a.anim.done and a.bytes[0] == 1: a.target_anim = 7; a.ai[1] = rnd(16) + 300
    elif c == 5:
        if a.anim.done:
            if a.bytes[3] == 0:
                a.target_anim = 7; a.target_dir = direction_to(a.px - p.px, a.py - p.py)
                a.ai[1] = 0x78; a.bytes[1] = 1
            else:
                a.target_anim = 6; a.flags |= ON_ANIM_END
    elif c == 9:
        if rp[0] < 5 and rp[1] < 5 and rp[2] < 0x200001:
            g.sound(0x171); a.target_anim = 2; a.bytes[0] = 1


def ai_8(ai, a):
    """C12 AI_UpdateEntityAI_8 (armoured knights / shield bearers): wander and climb
    ledges (jump anim 9) in phase 1; when Alundra swings close, raise the guard
    (anim 4, sound 0x7D); phase 3/4: guard, then several lunges (anim 9) and a strike
    (anim 5) at him."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); u = a.target_anim; card = [0, 0x10, 8, 0x18]

    def set_b0(v): a.bytes[0] = v; a.bytes[1] = 0

    def flip(): d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = d

    def rest(sv): a.ai[1] = s16(sv + 0x1E)

    if u == 6: return
    if u == 7:
        if not a.anim.done: return
        if a.bytes[3]:
            g.sound(0x40); a.target_anim = 2; a.flags |= ON_ANIM_END; return
        g.sound(0x7D); a.target_anim = 4; a.delay = 0
        if a.bytes[2]: a.bytes[0] = 4; a.bytes[1] = 7; return
        return set_b0(3)
    if (u < 2 or u == 5) and player_swinging(p) and rp[0] < 3 and rp[1] < 3:
        g.sound(0x7D); a.target_anim = 4; return set_b0(3)
    b = a.bytes[0]
    if b != 1:
        if b == 0:
            if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1); return
            a.bytes[1] = 0
            if rnd(4) != 0:
                a.bytes[0] = 3; g.sound(0x7D); a.target_anim = 4; return
            a.bytes[0] = 1; a.target_anim = 1; a.ai[1] = 0x78; a.target_dir = rnd(32); return
        if b == 3:
            b1 = a.bytes[1]
            if b1 == 0:
                if not a.anim.done: return
                start_flying(g, a, 9, 0x50, 0x46); a.bytes[1] = 1; return
            if b1 == 2:
                if not a.anim.done: return
                a.target_anim = 0; a.bytes[0] = 0; return rest(rnd(16))
            if b1 != 1: return
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1] == 0:
                g.sound(0x7D); a.target_anim = 5; a.bytes[1] = 2; return
            if a.force_adjusted or can_move_forward(a, 0): return flip()
            if not try_front(a, rp, 2, 5, 0): return
            a.bytes[0] = 4; a.bytes[1] = 2; return
        if b != 4: return
        b1 = a.bytes[1]
        if b1 == 0:
            g.sound(0x7D); a.target_anim = 4; a.bytes[1] = 1; return
        if b1 in (1, 2):
            if not a.anim.done and b1 != 2: return
            a.target_anim = 9; d = to_player(g, a)
            a.delay = 0; a.ai[1] = 0x50; a.bytes[2] = 3; a.bytes[1] = 3
            a.target_dir = (d + rnd(9) - 4) & 0x1F; return
        if b1 == 3:
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1] == 0 or a.force_adjusted or can_move_forward(a, 0):
                a.bytes[2] = (a.bytes[2] - 1) & 0xFF
                if a.bytes[2]:
                    a.target_anim = 9; a.target_dir = to_player(g, a); a.ai[1] = 0x3C; return
                g.sound(0x7D); a.target_anim = 5; a.bytes[1] = 6; return
            dl = a.delay
            if dl:
                a.delay = dl - 1
                if a.delay: return
            if rp[0] > 2 or rp[1] > 2 or rp[2] != 0: return
            if (a.ai[1] & 0xFFFF) > 0x27: return
            g.sound(0x7D); a.target_anim = 5; a.target_dir = to_player(g, a); a.bytes[1] = 4; return
        if b1 == 4:
            if not a.anim.done: return
            a.target_anim = 3; a.bytes[1] = 5; return
        if b1 == 5:
            if not a.anim.done and a.target_anim != 0: return
            if a.bytes[2] != 1:
                g.sound(0x7D); a.target_anim = 4; a.bytes[1] = 7; a.delay = 0x1E; return
            a.target_anim = 0; a.bytes[1] = 6; return
        if b1 == 6:
            if not a.anim.done and a.target_anim != 0: return
            a.bytes[0] = 0; a.target_anim = 0; return rest(rnd(16))
        if b1 == 7:
            if not a.anim.done: return
            a.target_anim = 9; a.ai[1] = 1; a.bytes[1] = 3; return
        return
    b1 = a.bytes[1]
    if b1 == 0:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            a.target_anim = 0; a.bytes[1] = 4; a.ai[1] = 0x3C
            a.target_dir = (card[a.anim_quadrant or 0] + 8) & 0x1F; return
        if a.force_adjusted:
            h = tile_height_ahead(g, a, 9, a.target_dir) - getattr(a, 'floor', 0)
            if h < 0x300001:
                g.sound(0x7D); a.target_anim = 4; a.delay = h; a.bytes[1] = 1; a.item_state = a.ai[1] & 0xFFFF; return
            return flip()
        if can_move_forward(a, 0x300000): return flip()
        rng = 4
    elif b1 == 1:
        if not a.anim.done: return
        a.ai[1] = 0xF; a.target_anim = 9; a.bytes[1] = 2; a.pz += a.delay; return
    elif b1 == 2:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        g.sound(0x7D); a.target_anim = 5; a.bytes[1] = 3; a.ai[1] = s16(a.item_state); return
    elif b1 == 3:
        if not a.anim.done: return
        a.target_anim = 1; a.bytes[1] = 0; return
    elif b1 in (4, 5, 6):
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            a.ai[1] = 0x28; q = a.anim_quadrant or 0
            if a.bytes[1] == 4: a.target_dir = (card[q] + 0x10) & 0x1F
            if a.bytes[1] == 5: a.target_dir = (card[q] - 8) & 0x1F
            if a.bytes[1] == 6: a.bytes[0] = 0; a.ai[1] = s16(a.ai[1] + rnd(0x21))
            a.bytes[1] = (a.bytes[1] + 1) & 0xFF; return
        rng = 5
    else:
        return
    if try_front(a, rp, 2, rng, 0): set_b0(4)


def ai_13(ai, a):
    """C20 AI_UpdateEntityAI_13 (shadow men): circle and strike when Alundra is close on
    its level; otherwise sink into the floor (anim 9) and glide under him as a shadow
    (anim 10), rising where he stands."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim

    def face(): a.target_dir = to_player(g, a)

    def lab_b0b0(b4): face(); a.bytes[0] = b4

    def lab_b160(anim): a.target_anim = anim; a.ai[1] = 0

    def lab_b1c0(v): a.target_anim = 0; a.ai[1] = s16(v)

    def lab_b208(v): a.ai[1] = s16(v); a.bytes[0] = 0

    if c == 0:
        if a.bytes[0] == 3:
            a.target_anim = 10; a.ai[1] = 0x3C; return
        if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1); return
        if rp[0] < 4 and rp[1] < 4 and rp[2] == 0:
            k = rnd(4)
            if k == 0: a.target_anim = 3; return lab_b0b0(1)
            a.target_anim = 1; d = to_player(g, a)
            a.target_dir = d if k == 1 else ((d + 4) & 0x1F if k == 2 else (d - 4) & 0x1F)
            a.ai[1] = 0x28; return
        if rp[0] < 5 and rp[1] < 5 and rp[2] == 0:
            if rnd(2) == 0:
                a.target_anim = 1; face(); a.ai[1] = rnd(16) + 0x14; return
            a.target_anim = 3; face(); a.bytes[0] = 2; return
        return lab_b160(9)
    if c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 0; return
        if rp[0] > 4 or rp[1] > 4: return lab_b160(9)
        if not a.force_adjusted and can_move_forward(a, 0) == 0: return
        if tile_height_ahead(g, a, 10, a.target_dir) == 0x7800000: return
        if rp[2] != 0: a.target_anim = 3; return lab_b0b0(3)
        a.target_anim = 0; face(); return
    if c == 2:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 5
        return
    if c == 3:
        if not a.anim.done: return
        b = a.bytes[0]
        if b == 2:
            a.target_anim = 2; face(); return lab_b208(10)
        if b == 3: return lab_b160(5)
        if b == 1: a.target_anim = 4; a.bytes[0] = 0
        return
    if c == 4:
        if not a.anim.done: return
        a.target_anim = 5; a.ai[1] = 0x3C; return
    if c == 5:
        if a.anim.done: lab_b1c0(0x1E)
        return
    if c == 7:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 8; a.flags |= ON_ANIM_END; return
        a.target_anim = 0; return lab_b208(0x14)
    if c == 9:
        if rp[0] > 0x1E or rp[1] > 0x1E: return
        a.target_anim = 10; face(); return
    if c == 10:
        if a.bytes[0] == 3:
            a.ai[1] = s16(a.ai[1] - 1)
            if a.ai[1] == 0: a.bytes[0] = 0
            return
        if rp[0] or rp[1] or rp[2]:
            d = to_player(g, a); a.target_dir = d
            if not a.force_adjusted: return
            h = tile_height_ahead(g, a, 10, d)
            if h == 0x7800000: return
            h -= getattr(a, 'floor', 0); a.pz += h
            return
        lab_b1c0(0x78)


def ai_23(ai, a):
    """C35 AI_UpdateEntityAI_23 (archers): look about; shoot (anim 5, map sprite 0x65)
    when Alundra is in front within 6 squares; back off (anim 9) when he is within 2."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim; card = [0, 0x10, 8, 0x18]

    def shoot():
        if rnd(5) == 0: g.sound(0xCD)
        a.target_anim = 5; a.target_dir = to_player(g, a); a.ai[1] = 0x12

    def back_off():
        a.target_anim = 9; a.target_dir = direction_to(a.px - p.px, a.py - p.py); a.ai[1] = 0x3C; a.bytes[1] = 1

    if c == 5:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl == 1:
                ox, oy = [(0, -0x80000), (0, 0x80000), (-0xA0000, 0), (0xA0000, 0)][a.anim_quadrant or 0]
                g.spawn_sprite(a, True, 0x65, a.px + ox, a.py + oy, a.pz + 0xA0000, (a.target_dir - 7) & 0x1F)
                a.bytes[2] = 0x1E
    elif c < 6:
        if c == 0 and a.on_ground:
            if a.bytes[2] == 0:
                if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1)
                if a.bytes[1] == 2 or try_front(a, rp, 1, 6, 0x200000):
                    a.bytes[1] = 0
                    if rp[0] < 3 and rp[1] < 3: back_off()
                    else: shoot()
                elif a.ai[1] == 0:
                    ph = a.bytes[0]; a.bytes[0] = (ph + 1) & 0xFF; q = a.anim_quadrant or 0
                    if ph == 0: a.ai[1] = 0x3C; a.target_dir = (card[q] + 8) & 0x1F
                    elif ph == 1: a.ai[1] = 0x3C; a.target_dir = (card[q] + 0x10) & 0x1F
                    elif ph == 2:
                        a.target_anim = 9; a.target_dir = rnd(32); a.bytes[1] = 0; a.ai[1] = rnd(16) + 0x3C
                    else: a.bytes[0] = 0
            else:
                a.bytes[2] = (a.bytes[2] - 1) & 0xFF
    elif c == 7:
        if a.anim.done:
            if a.bytes[3] == 0: a.target_anim = 0; a.bytes[2] = 0; a.bytes[0] = 0; a.bytes[1] = 2
            else: a.target_anim = 8; a.flags |= ON_ANIM_END
    elif c == 9:
        mode = a.bytes[1]; a.ai[1] = s16(a.ai[1] - 1)
        if mode == 1 and (a.ai[1] == 0 or a.force_adjusted or can_move_forward(a, 0)): shoot()
        elif a.ai[1] == 0: a.target_anim = 0; a.ai[1] = 0x3C
        elif try_front(a, rp, 1, 6, 0x200000):
            if rp[0] > 2 or rp[1] > 2: shoot()
            else: back_off()
        elif not a.force_adjusted: handle_ledge(a, 9, 0x300000)
        else: direction_forced(g, a, 9, 3, 0x300000)
    if a.target_anim in (3, 5): a.target_dir = (a.target_dir + 2) & 0x1C


def ai_20_2(ai, a):
    """C31 AI_UpdateEntityAI_20_2 (bomb throwers): wander; when Alundra comes within 3
    squares, lob a bomb (map sprite 0xB0) at him, then run off."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim; card = [0, 0x10, 8, 0x18]
    if c < 2 and rp[0] < 4 and rp[1] < 4 and rp[2] < 0x100001:
        a.target_anim = 3; a.cur_anim = -1; a.target_dir = to_player(g, a); a.ai[1] = 0x20; return
    if c == 0:
        if a.ai[1]: a.ai[1] = s16(a.ai[1] - 1); return
        if a.bytes[1] == 0: start_flying(g, a, 1, 0x50, 0x1E); return
        ph = a.bytes[1]; a.ai[1] = 0x3C; a.bytes[1] = (ph - 1) & 0xFF
        if ph == 1: a.target_dir = (a.target_dir + 0x10) & 0x1F
        elif ph == 2:
            q = a.anim_quadrant or 0
            a.target_dir = (card[q] - 8) & 0x1F if rnd(2) == 0 else (card[q] + 8) & 0x1F
    elif c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 0; a.ai[1] = rnd(32) + 0x1E; return
        if not a.force_adjusted:
            if can_move_forward(a, 0) == 0: return
            a.target_anim = 0; a.ai[1] = 0; a.bytes[1] = 2; return
        d = FLIP[a.target_dir & 31]; stop(a); a.target_dir = (d + 0x10) & 0x1F
    elif c == 3:
        dl = a.ai[1]
        if dl:
            a.ai[1] = s16(dl - 1)
            if dl == 1:
                ox, oy = [(0, 0x40000), (0, -0x40000), (-0x80000, 0), (0x80000, 0)][a.anim_quadrant or 0]
                e = g.spawn_sprite(a, True, 0xB0, a.px + ox, a.py + oy, a.pz + 0x120000, a.target_dir)
                if e is not None: e.fz = 0x20000
                a.bytes[0] = 0
        if a.anim.done: a.target_anim = 0; a.ai[1] = 0x1E
    elif c == 5:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 2; a.flags |= ON_ANIM_END; return
        if rnd(5) == 0: g.sound(0x9E)
        a.target_anim = 1; a.target_dir = direction_to(a.px - p.px, a.py - p.py)
        a.ai[1] = 0x28; a.bytes[0] = 1; a.bytes[1] = 0


def pillar_side(e1, p):
    """GetPushablePillarPushDirection: the direction Alundra pushes from."""
    if p.x_collision is not e1: return -1
    d = p.mpx - e1.mpx
    if d < 0:
        if -d <= p.size[0]: return (1 if p.py < e1.py else 0) << 4
    elif d <= e1.size[0]:
        return (1 if p.py < e1.py else 0) << 4
    return 8 if p.px < e1.px else 0x18


def pushable_pillar(ai, a):
    """C76 AI_UpdatePushablePillarPushState (pillars, crates): pushed against for 32
    frames it slides (sound 0x19) away from Alundra while he keeps pushing."""
    g = ai.g; p = g.player
    if p.x_collision is a:
        if a.bytes[0] < 0x1F: a.bytes[0] += 1; return
        g.sound(0x19); a.target_anim = 1
        r = pillar_side(a, p)
        if r != -1: a.target_dir = (r + 0x10) & 0x1F; return
    if a.target_anim == 1: g.sound(0x19)
    a.bytes[0] = 0; a.target_anim = 0


def ai_14(ai, a):
    """C21 AI_UpdateEntityAI_14 (rushers): wander; notice Alundra within 2 squares on
    its level, then charge him (anim 3) kicking up dust."""
    g = ai.g; p = g.player; rp = rel_pos(a, p); c = a.target_anim; card = [0, 0x10, 8, 0x18]
    if c == 1:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] != 0:
            if rp[0] < 3 and rp[1] < 3 and rp[2] == 0:
                a.bytes[0] = 1; a.target_anim = 0; a.target_dir = to_player(g, a); a.ai[1] = 10; return
            if not a.force_adjusted and can_move_forward(a, 0) == 0: return
            stop(a); a.target_dir = (card[a.anim_quadrant or 0] - 0x10) & 0x1F; return
        a.target_anim = 0; return
    if c == 0:
        if a.ai[1] == 0: a.ai[1] = 0x3C; a.target_dir = rnd(32)
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        if a.bytes[0]:
            a.target_anim = 3; a.target_dir = to_player(g, a); a.bytes[0] = 0; a.ai[6] = 0; a.ai[7] = 0; return
        a.target_anim = 1; a.ai[1] = 0x78; return
    if c == 5:
        if not a.anim.done: return
        if a.bytes[3]: a.target_anim = 2; a.flags |= ON_ANIM_END; return
        a.bytes[0] = 1; a.target_anim = 0; a.ai[1] = 0x1E; return
    if c == 3:
        a.ai[6] = s16(a.ai[6] + 1)
        if (a.ai[6] & 7) == 0:
            eff = g.map.data.get('info', {}).get('c', 0)
            if eff: g.effects.create(False, eff, 0, a.px, a.py, getattr(a, 'floor', a.pz))
        if not a.anim.done and not a.force_adjusted: return
        a.target_anim = 0


HANDLERS = {21: ai_14, 76: pushable_pillar, 31: ai_20_2, 35: ai_23, 20: ai_13, 12: ai_8, 30: ai_ce08, 9: ai_6, 14: ai_9, 18: ai_a564, 6: ai_3, 11: ai_7, 25: ai_15, 28: ai_19, 32: ai_21, 34: ai_21, 7: ai_4, 19: ai_12, 16: ai_69f44, 74: magic_pot, 5: ai_0, 15: ai_10, 26: ai_17, 29: ai_20, 1: idle_skittish, 2: curious_flying, 3: ai_1, 69: pushable, 70: carried_hits, 10: ai_6_2, 91: idle_look_around, 92: trigger_warp, 93: idle_curious}


# ----------------------------------------------------------------------------- bosses
def screen_effect(g, level, duration, keep, reset):
    """TriggerScreenEffect 0x80083324: the overlay adds toward grey `level` (16.16, the same for
    R G B: 0xFF0000 = white) in `duration` frames (engine/screen.py)."""
    from engine import screen
    screen.trigger(g, level, duration, keep, reset)


def boss_explode(ai, a):
    """UpdateEntityAI_BossExplode 0x80080AE0: bursts every 8 frames, red flash, then gone
    (bytes[3] counts the phases 1-3; 4 = finished)."""
    g = ai.g
    a.ai[1] = s16(a.ai[1] - 1); ph = a.bytes[3]
    if ph < 3 and (a.ai[1] & 7) == 0:
        g.sound(0x2E)
        sx, sy, sz = a.size; mx, my, mz = a.mod
        xo = ((rnd((sx >> 0x14) + 1) * 0x10) + rnd(0x11)) * 0x10000
        zo = rnd((sz >> 0x14) + 1) * 0x10 * 0x10000 + rnd(0x11) * 0x10000
        g.effects.create(0, 0x1B, 0, a.px + mx + xo, a.py + my + sy, a.pz + mz + zo)
    if ph == 2:
        if a.ai[1] & 0xFFFF == 0:
            screen_effect(g, 0, 0x1E, 0, 0); a.ai[1] = 0x1E; a.bytes[3] = 3
    elif ph == 1:
        if a.ai[1] & 0xFFFF == 0:
            screen_effect(g, 0xFF0000, 0x1E, 1, 1); a.ai[1] = 0x1E; a.bytes[3] = 2
        else:
            a.ai[5] = (a.ai[5] - 1) & 0xFFFF
            if a.ai[5] == 0:
                screen_effect(g, 0xFF0000, 4, 0, 1); a.ai[5] = (rnd(5) << 3) + 0x1E
    elif ph == 3:
        if a.ai[1] & 0xFFFF == 0: a.bytes[3] = 4


def guardian_gravity(ai, a):
    """C 77, 0x80071134 (falling element rock): a little gravity while idle."""
    if a.target_anim == 0 and -0x80001 < a.fz: a.fz -= 0x4000


def _shake(g, on, sx=0, sy=0, lx=0, ly=0):
    m = g.mem; S = 0x801F94D0
    m.w32(S, on); m.w32(S + 0xC, sx); m.w32(S + 0x10, sy); m.w32(S + 4, lx); m.w32(S + 8, ly)


def ancient_guardian(ai, a):
    """C 40, AncientGuardian 0x80070598 (Ancient Guardian / element boss)."""
    g = ai.g; p = g.player
    if a.delay > 0:
        a.delay -= 1
        if a.delay == 0: _shake(g, 0); g.sound(0x55)
    if a.bytes[3] and a.target_anim == 0:
        if a.bytes[3] < 4: return boss_explode(ai, a)
        a.target_anim = 10; a.flags |= ON_ANIM_END; return
    if a.target_anim not in (1, 0xD): a.item_state = 0
    rp = rel_pos(a, p); c = a.target_anim

    def fire():                     # LAB_80070B70: ◆ element watcher (map sprite 0xF3)
        g.spawn_sprite(a, 1, 0xF3, a.px, a.py, a.pz, a.target_dir)

    def stomp():                    # LAB_80070914
        a.target_anim = 2; a.target_dir = 0; a.ai[1] = 0x3C

    if c == 0:
        if a.bytes[2]: return
        if a.ai[1]: a.ai[1] -= 1; return
        if a.ai[4] == 0 or rnd(a.ai[4] + 1) != 0:
            v = a.bytes[1]; a.ai[4] = 0
            if v:
                start_flying(g, a, 1, 0x3C, 0x46); a.bytes[0] = 2; return
            if rp[0] < 3 and rp[1] < 3 and rp[2] < 0x100001:
                a.target_anim = 1; a.target_dir = direction_to(a.px - p.px, a.py - p.py)   # backs away
                a.ai[1] = 0x78; a.bytes[0] = 1; return
            start_flying(g, a, 1, 0x78, 0x14); a.bytes[0] = 0; return
        return stomp()
    if c in (1, 0xD):
        if a.hp <= (a.hp_max // 4 if a.hp_max >= 0 else (a.hp_max + 3) >> 2): a.target_anim = 0xD
        d = a.item_state
        if d == 0:
            g.sound(0x1CF); d = 0x1A if a.target_anim == 1 else 0x10; a.item_state = d
        a.bytes[1] = 0; a.ai[1] = s16(a.ai[1] - 1); v = a.bytes[0]; a.item_state = d - 1
        if v == 1:
            val = 3
            if a.ai[1] and not a.force_adjusted: return
        elif v == 2:
            if a.ai[1] and not a.force_adjusted: return
            a.target_anim = 0; a.ai[1] = 0x28; return
        elif v == 0:
            if a.ai[1] == 0: return stomp()
            val = 2
            if not try_front(a, rp, 1, 5, 0x100000):
                if a.force_adjusted: a.target_dir = (a.target_dir + 8) & 31
                return
        else:
            return
        a.bytes[1] = val; a.target_anim = 0xC
        a.target_dir = direction_to(p.px - a.px, p.py - a.py); a.ai[1] = 0x3C
        return
    if c == 2:
        v = a.ai[1]
        if v:
            a.ai[1] = v - 1
            if v == 1:
                g.sound(0x55); _shake(g, 1, 1, 1, 2, 2); a.delay = 0x28
        if not (a.anim.done or a.anim_complete): return
        a.ai[1] = 0x3C; a.target_anim = 0
        n = rnd(4) + 4; a.bytes[1] = n
        if n != 4:
            d = rnd(4)
            while d < 0x20:       # a ring of watchers, one every 4 directions
                g.spawn_sprite(a, 1, 0xF3, a.px, a.py, a.pz, d); d += 4
            return
        return fire()
    if c == 6:
        if not try_front(a, rp, 3, 3, 0): return
        a.target_anim = 0xB; a.ai[1] = 0x78; a.flags &= 0xFFFFFEFF; return
    if c == 7:
        if a.on_ground: a.target_anim = 0; g.sound(0x65)
        return
    if c == 9:
        if not (a.anim.done or a.anim_complete): return
        if a.bytes[3] == 0:
            a.target_anim = 0; a.damaged_tick = 0x5A; a.ai[4] = 0
            if a.bytes[2]: return
            a.ai[1] = 0x14
            a.ai[4] = 1 if a.hp <= (a.hp_max // 4) else 2
            return
        a.ai[1] = 300; a.ai[5] = 0x1E; a.target_anim = 0; a.flags &= 0xFFFFFFFC; return
    if c == 0xB:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0: a.target_anim = 7; a.flags |= GRAVITY
        return
    if c == 0xC:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1]: return
        a.target_anim = 0; a.ai[1] = 0xF
        return fire()


def guardian_watcher(ai, a):
    """C 41, AncientGuardian 0x80070C40 (◆ element watcher): moves in the pattern its
    parent picked (bytes[1]) and drops element rocks (map sprite 0xF2)."""
    g = ai.g; p = g.player; par = a.parent

    def drop():
        g.spawn_sprite(a, 1, 0xF2, a.px, a.py, a.pz + 0xA00000, a.target_dir)

    def finish():
        ai.destroy(a, -1)
        if par is not None: par.bytes[2] = 0

    if a.target_anim == 0:
        st = par.bytes[1] if par is not None else 0
        a.target_anim = 1; a.bytes[1] = st
        if par is not None: par.bytes[2] = 1
        if st in (1, 4): a.bytes[2] = 0x14
        elif st == 2:
            a.target_dir = direction_to(p.px - a.px, p.py - a.py); a.bytes[2] = 0xF; a.ai[1] = 0xB4
        elif st == 3:
            q = par.anim_quadrant or 0 if par is not None else 0
            a.ai[1] = 0x14; a.bytes[0] = 0; a.target_dir = (CARDINAL_FACING[q] + 8) & 31
        elif st == 5: a.bytes[2] = 1
        elif st in (6, 7): a.bytes[2] = 6
        return
    if a.target_anim != 1: return
    st = a.bytes[1]
    if st in (1, 4):
        if a.ai[1] == 0: a.ai[1] = 0xF
        a.ai[1] -= 1
        if a.ai[1]:
            if a.force_adjusted or can_move_forward(a, 0): a.target_dir = FLIP[a.target_dir]
            return
        drop(); a.bytes[2] = (a.bytes[2] - 1) & 0xFF
        if a.bytes[2]: a.target_dir = rnd(32); return
        return finish()
    if st == 2:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] in (0x78, 0x3C): a.target_dir = direction_to(p.px - a.px, p.py - a.py)
        if a.ai[1] and not a.force_adjusted and not can_move_forward(a, 0):
            a.bytes[2] = (a.bytes[2] - 1) & 0xFF
            if a.bytes[2]: return
            drop(); a.bytes[2] = 0xF; return
        return finish()
    if st == 3:
        a.ai[1] = s16(a.ai[1] - 1)
        if a.ai[1] == 0:
            k = a.bytes[0]; a.bytes[0] = k + 1
            if k in (0, 0x11):
                a.ai[1] = 5 if k == 0 else 0x14
                a.target_dir = (a.target_dir - 8) & 31; drop(); return
            if k in (2, 4, 6, 8, 10, 0xC, 0xE, 0x10): drop()
            if 1 <= k <= 0x10:
                a.ai[1] = 5; a.target_dir = (a.target_dir - 1) & 31; return
            if k == 0x12: return finish()
            return
        if a.force_adjusted or can_move_forward(a, 0): return finish()
        return
    if st in (5, 6, 7):
        if a.ai[1] == 0: a.ai[1] = 0x14
        a.ai[1] -= 1
        if a.ai[1]:
            if a.force_adjusted or can_move_forward(a, 0): return finish()
            return
        drop(); a.bytes[2] = (a.bytes[2] - 1) & 0xFF
        if a.bytes[2]: return
        return finish()


# 0x80028B54: direction a facing (down, up, left, right) points
CARDINAL_FACING = [0, 16, 8, 24]
HANDLERS.update({40: ancient_guardian, 41: guardian_watcher, 77: guardian_gravity})
