"""Built-in sprite programs, group 2: C5-C25 (US ALUN_CD.EXE 0x80068F50-0x8006DE14)."""
from .registry import port
from .core import s32, s16, next_seed, hi
from . import aihelp, core, entity, player, calls

M32 = 0xFFFFFFFF
TURN = 0x80028AD8           # u8[32]: the direction turned away
QDIR = 0x80028AF8           # u8[4]: the direction of each facing quadrant (0 down, 1 up, 2 left, 3 right)


def ai_word(e, k):
    """lw Entity+0x280+2k: ai[k] (low half) and ai[k+1] (high half)."""
    return s32((e.ai[k] & 0xFFFF) | (e.ai[k + 1] << 16))


def set_ai_word(e, k, v):
    """sw Entity+0x280+2k."""
    e.ai[k] = v; e.ai[k + 1] = (v & M32) >> 16


def dir_to_player(g, e):
    p = g.ent[0]
    return player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))


def player_swinging(g):
    """Alundra's attack is on with a weapon record whose first byte is set."""
    p = g.ent[0]
    return p.atk_on and p.attack_addr and g.mem.u8(p.attack_addr)


@port(0x80068F50)
def ai_c5(g, e):
    """C5: wander (or walk toward Alundra when he is in front); next to him it faces him and
    attacks (animation 3), a hit on it (Alundra's touch) making it pause; after being hit
    (6 / 11) it turns around and makes up to four attacks in a row (bytes[1] 3..6)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        if not e.on_ground: return
        if ((e.bytes[1] - 3) & M32) < 5:
            t = e.ai[1] & 0xFFFF
            if t:
                e.ai[1] = t - 1
                if e.ai[1] & 0xFFFF: return
            e.target_dir = dir_to_player(g, e)
            k = e.bytes[1]
            e.target_anim = 3
            e.delay = 0
            if k == 6:
                e.bytes[1] = 0
                return
            e.bytes[1] = k + 1
            return
        e.ai[1] = 0
        e.bytes[1] = 0
        _c5_walk(g, e, r)
    elif a == 1:
        _c5_walk(g, e, r)
    elif a == 3:
        if g.ent[0].touching is e: e.delay = 1
        if e.anim_done:
            if e.delay:
                e.target_anim = 0; e.ai[1] = 0x1E; e.delay = 0
                return
            aihelp.start_moving_half(g, e, 1, 0x78)
            e.item_state = e.ai[1] & 0xFFFF
    elif a in (6, 11):
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 7; e.flags = s32(e.flags | 0x40)
                return
            e.ai[1] = 0xA
            e.target_anim = 0
            e.target_dir = (e.target_dir + 0x10) & 0x1F
            if not ((e.bytes[1] - 3) & M32) < 4: e.bytes[1] = 3


def _c5_walk(g, e, r):
    """C5 animations 0 / 1: walk; item_state = frames before it may attack again."""
    if e.item_state: e.item_state = s32(e.item_state - 1)
    t = e.ai[1] & 0xFFFF
    if t == 0:
        e.target_anim = 1; e.ai[1] = 0xF0
        if aihelp.near_in_front(g, e, r, 6, 0x100000):
            e.target_dir = dir_to_player(g, e)
            e.bytes[1] = 1
        else:
            aihelp.start_moving(g, e, 1, 0xB4, 0x14)
            e.bytes[1] = 2
        return
    e.ai[1] = t - 1
    if e.force_adjusted:
        aihelp.step_or_turn(g, e, 1, 4, 0x100000)
        return
    if e.item_state == 0 and r[0] < 3 and r[1] < 3 and not 0x100000 < r[2]:
        e.target_dir = dir_to_player(g, e)
        k = e.bytes[1]
        if k == 1:
            e.target_anim = 3; e.delay = 0
        elif k == 2:
            e.bytes[1] = 7; e.ai[1] = 0x3C; e.target_anim = 0


@port(0x8006928C)
def ai_c6(g, e):
    """C6: walk around (new direction every 240+ frames, half the time toward Alundra; a pause
    at walls); waiting (4) it pops up (3) when Alundra is close in front, then chases him for
    300 frames; when hurt (6) it may drop its contents (1 in 4, SpawnEntityContents)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t == 0:
            e.target_anim = 1; e.ai[1] = 1
            return
        e.ai[1] = t - 1
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            aihelp.start_moving_half(g, e, 1, 0xF0)
            return
        if e.force_adjusted:
            aihelp.step_or_turn(g, e, 1, 2, 0x100000)
            if e.target_anim == 1: e.target_anim = 0
            e.ai[1] = 0x3C
    elif a == 4:
        if aihelp.near_in_front(g, e, r, 4, 0x100000): e.target_anim = 3
    elif a == 3:
        if e.anim_done:
            e.target_anim = 1
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x12C
    elif a == 6:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 7; e.flags = s32(e.flags | 0x40)
                return
            if hi(next_seed(g), 4) == 0: calls.call(g, 0x800332A8, e)
            e.target_anim = 0; e.ai[1] = 0x1E
    elif a == 2:
        if e.on_ground: e.target_anim = 1


@port(0x80069490)
def ai_c7(g, e):
    """C7 (hiding critters): idle and look around (bytes[1] counts 10..22: turn, wander, hide);
    Alundra in front makes it walk (1) at him and bite (3, repeated while it keeps getting
    touched); hidden (5, 2) it pops out (4) when he is close.  Hit (7): 1 in 4 hides, else it
    throws a map sprite 0x91; dying (8) four 0x91 fly out; 10 / 11: a thrown one, gone after 60 frames."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32

    def bite():
        e.target_dir = dir_to_player(g, e)
        e.target_anim = 3
        e.bytes[1] = 0

    def stop_turn(d):
        e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
        e.ai[1] = 0x28
        e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) + d) & 0x1F

    if a == 2:
        t = e.ai[1] & 0xFFFF
        if t: e.ai[1] = t - 1
        if e.bytes[1]: return
        if r[0] < 3 and r[1] < 3 and not r[2] > 0:
            e.target_anim = 4; e.bytes[1] = 0xA
            return
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 4; e.bytes[1] = 0x14
    elif a == 4:
        if e.anim_done and e.bytes[1] in (0xA, 0x14):
            d = dir_to_player(g, e)
            s = next_seed(g)
            e.target_dir = d; e.target_anim = 0
            e.ai[1] = hi(s, 0x10) + 0x14
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; return
        if e.force_adjusted:
            d = g.mem.u8((TURN + e.target_dir) & M32)
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = d
        else:
            h = s32(e.floor - g.ent[0].floor)
            if h >= 0: aihelp.ledge_turn(g, e, 1, h)
        if e.bytes[1] and aihelp.sees_player(g, e, r, 1, 2, 0): bite()
    elif a == 0:
        if e.bytes[1] == 0: e.bytes[1] = 0xA
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if e.ai[1] & 0xFFFF: return
        if e.bytes[1] == 0xA and aihelp.sees_player(g, e, r, 1, 2, 0):
            bite(); return
        k = e.bytes[1]
        if not (((k - 0xA) & M32) < 7 or ((k - 0x14) & M32) < 2): return
        if aihelp.sees_player(g, e, r, 2, 6, 0):
            e.target_dir = dir_to_player(g, e)
            e.target_anim = 1; e.ai[1] = 0x78
            return
        e.bytes[1] = k + 1
        n = e.bytes[1]
        if n in (11, 14): stop_turn(-8)
        elif n in (12, 15, 21): stop_turn(0x10)
        elif n == 13: aihelp.start_moving(g, e, 1, 0x78, 0x1E)
        elif n in (16, 22): e.target_anim = 5
    elif a == 5:
        if e.anim_done:
            e.target_anim = 2
            e.bytes[1] = 0; e.ai[1] = 0x78
    elif a == 3:
        if g.ent[0].touching is e: e.bytes[1] = e.bytes[1] + 1
        if not e.anim_done: return
        if e.bytes[1] & 0xF:
            d = dir_to_player(g, e)
            s = next_seed(g)
            e.target_dir = d; e.target_anim = 0
            e.bytes[1] = 0xA
            e.ai[1] = hi(s, 8) + 0x14
            return
        if aihelp.sees_player(g, e, r, 1, 1, 0):
            e.target_dir = dir_to_player(g, e)
            if e.bytes[1] == 0:
                e.target_anim = 3; e.bytes[1] = 0x80
                return
            e.target_anim = 1
            e.bytes[1] = 0; e.ai[1] = 0x14
            return
        s = next_seed(g)
        e.target_anim = 0
        e.bytes[1] = 0xA
        e.ai[1] = hi(s, 0x10) + 0x14
    elif a == 7:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 8; e.ai[1] = 8
            e.flags = s32(e.flags | 0x40)
            return
        if hi(next_seed(g), 4) == 1:
            e.target_anim = 5; return
        e.bytes[1] = 0; e.ai[1] = 0
        s = next_seed(g)
        e.target_anim = 0
        c = entity.spawn_warp_entity(g, e, 1, 0x91, e.px, e.py, s32(e.pz + 0x100000),
                                     g.mem.u8((QDIR + hi(s, 5)) & M32))
        if c is not None:
            c.bi_a = 0; c.target_anim = 0xB; c.contents_item = 0
    elif a == 8:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            for d in (4, 0xC, 0x14, 0x1C):
                c = entity.spawn_warp_entity(g, e, 1, 0x91, e.px, e.py, s32(e.pz + 0x100000), d)
                if c is not None:
                    c.bi_a = 0; c.target_anim = 0xB; c.contents_item = 0
    elif a == 11:
        if e.on_ground:
            e.target_anim = 0xA; e.ai[1] = 0x3C
    elif a == 10:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            core.play_sound(g, 0x40)
            entity.destroy_entity(g, e, -1)


@port(0x80069C78)
def ai_c8(g, e):
    """C8: walk (1) / rest (4, 2); Alundra within 4 squares makes it rise (3) and charge him
    (11 then 6 for 120 frames, raising dust); within 2 squares, or 1 in 5 after being hit (8),
    it bursts (5): after 94 frames four map sprites 0x8B fly out diagonally (sound 0x2D);
    animation 10 (falling) is destroyed on landing."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32

    def burst():
        e.bytes[0] = 0; e.ai[1] = 0x5E
        e.flags = s32(e.flags | 0x40)

    if a in (0, 1):
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 4; return
        if r[0] < 3 and r[1] < 3 and not 0x100000 < r[2]:
            e.target_anim = 5; burst(); return
        if e.force_adjusted:
            d = g.mem.u8((TURN + e.target_dir) & M32)
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = d
            return
        aihelp.ledge_turn(g, e, 1, 0)
    elif a == 2:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if r[0] < 5 and r[1] < 5 and not 0x100000 < r[2]:
                e.target_anim = 3; e.bytes[1] = 3
            else:
                e.bytes[1] = 0
            return
        e.target_anim = 3
    elif a == 3:
        if e.anim_done:
            if e.bytes[1] == 3:
                e.target_anim = 0xB; e.bytes[1] = 0; e.ai[1] = 0x28
                return
            aihelp.start_moving(g, e, 1, 0x78, 0x1E)
    elif a == 4:
        if e.anim_done:
            s = next_seed(g)
            e.target_anim = 2
            e.ai[1] = hi(s, 0x15) + 0x78
    elif a == 11:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 6
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x78
            set_ai_word(e, 6, 0)
    elif a == 6:
        n = s32(ai_word(e, 6) + 1)
        set_ai_word(e, 6, n)
        if (n & 7) == 0:
            core.spawn_effect(g, 0, g.mem.u8(g.tile_effects_addr + 0xA), 0, e.px, e.py, e.floor)
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0: e.target_anim = 4
    elif a == 8:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 9; e.flags = s32(e.flags | 0x40)
                return
            if hi(next_seed(g), 5) == 2:
                e.target_anim = 5; burst(); return
            e.target_anim = 4; e.ai[1] = 0x1E
    elif a == 5:
        if e.bytes[0] == 0:
            e.ai[1] = (e.ai[1] & 0xFFFF) - 1
            if (e.ai[1] & 0xFFFF) == 0:
                e.bytes[0] = 1
                core.play_sound(g, 0x2D)
                for d in (4, 0xC, 0x14, 0x1C):
                    c = entity.spawn_warp_entity(g, e, 1, 0x8B, e.px, e.py, s32(e.pz + 0x100000), d)
                    if c is not None:
                        c.bi_a = 0; c.target_anim = 0xA; c.contents_item = 0
    elif a == 10:
        if e.on_ground: entity.destroy_entity(g, e, -1)


@port(0x8006A10C)
def ai_c9(g, e):
    """C9 (hopping on levels): wander or walk toward Alundra (1 in 3 when he is within 6 squares),
    jumping up / down ledges (animation 9, ai[1] = frames of rise / fall); next to him it plays
    animation 3 (sound 0x1CD after 110 frames)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        e.bytes[0] = 0
        if (e.ai[1] & 0xFFFF) == 0: e.ai[1] = 0x78
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if e.ai[1] & 0xFFFF:
            if r[0] < 3 and r[1] < 3:
                e.target_anim = 3
                e.target_dir = dir_to_player(g, e)
                e.ai[1] = 0x6E
                e.bytes[2] = 0; e.bytes[0] = 1
            return
        if aihelp.sees_player(g, e, r, 1, 3, 0x800000):
            d = s32(e.pz - g.ent[0].floor)
            if 0x100000 < d:                        # Alundra below: drop to him
                e.target_anim = 9; e.ai[1] = d >> 15; e.fz = -0x8000
                return
            if d < -0x100000:                       # above: jump up
                e.target_anim = 9; e.ai[1] = s32(-d) >> 15; e.fz = 0x8000
                return
        if r[0] < 7 and r[1] < 7 and hi(next_seed(g), 3) == 0:
            e.target_anim = 1
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x28; e.bytes[1] = 1
            return
        aihelp.start_moving(g, e, 1, 0x1E, 0x28)
        e.bytes[1] = 0
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; return
        if not e.force_adjusted: return
        e.ai[1] = 0
        if e.bytes[1]:                              # walking at Alundra: climb (9) if it can
            h = aihelp.step_or_turn(g, e, 1, 9, 0x500000)
            if e.target_anim == 9: e.ai[1] = h >> 15
            else: e.target_anim = 0
            return
        d = g.mem.u8((TURN + e.target_dir) & M32)
        e.target_anim = 0
        e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
        e.target_dir = d
    elif a == 3:
        t = e.ai[1] & 0xFFFF
        if t and e.bytes[2] == 0:
            e.ai[1] = t - 1
            if (e.ai[1] & 0xFFFF) == 0:
                core.play_sound(g, 0x1CD)
                e.bytes[2] = 1; e.ai[1] = 1
    elif a == 9:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            aihelp.start_moving_half(g, e, 1, 0x78)
            e.bytes[1] = 0; e.fz = 0
    elif a in (5, 7):
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 2; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.ai[1] = 0x1E


@port(0x8006A4C4)
def ai_c10(g, e):
    """C10 (on map 0x99 it dies with its parent): turns in place watching (bytes[0] 0); when Alundra
    comes in front it keeps him in sight and reacts by distance and chance: lunge (3, when he
    swings), jump back (12), attack (7, 8) or sidestep (4), sometimes crying (sound 0xCD).  Its
    facing always ends rounded to the 8 main directions."""
    if g.cur_map == 0x99 and e.parent.bytes[3]:
        entity.destroy_entity(g, e, -1)
        return
    r = aihelp.rel_tile(g, e)
    _c10(g, e, r, e.target_anim & M32)
    e.target_dir = (e.target_dir + 2) & 0x1C


def _c10(g, e, r, a):
    def jump_back(t):
        e.target_anim = 0xC; e.ai[1] = t

    def back_off():                     # target_dir turned around
        e.target_dir = (e.target_dir - 0x10) & 0x1F

    def calm():
        e.target_anim = 0; e.ai[1] = 0x1E; e.bytes[1] = 0

    if a == 0:
        if e.bytes[0] == 0:
            if aihelp.sees_player(g, e, r, 2, 6, 0x100000):
                e.bytes[0] = 1; e.ai[1] = 0
                return
            t = e.ai[1] & 0xFFFF
            if t:
                e.ai[1] = t - 1
                return
            if e.bytes[1] == 0 and hi(next_seed(g), 4) != 1: return
            b = e.bytes[1]
            e.bytes[1] = b + 1
            if b < 3:                       # look at Alundra
                if hi(next_seed(g), 4) == 0: core.play_sound(g, 0xCD)
                e.target_anim = 8
                e.target_dir = dir_to_player(g, e)
            elif b == 3:                    # stop, face a random main direction
                s = next_seed(g)
                e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
                d = g.mem.u8((QDIR + hi(s, 4)) & M32)
                e.ai[1] = 0x14; e.target_dir = d
            elif b == 4:                    # stop, turn away
                e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
                d = g.mem.u8((TURN + e.target_dir) & M32)
                e.ai[1] = 0x14; e.target_dir = d
            elif b == 5:
                jump_back(0x78)
            else:
                e.bytes[1] = 0; e.ai[1] = 0
            return
        if not (aihelp.sees_player(g, e, r, 2, 6, 0x100000) or
                aihelp.sees_player_q(g, e, r, (e.anim_quadrant & 0xFF) ^ 1, 2, 3, 0x100000)):
            e.bytes[1] = 0; e.bytes[0] = 0; e.ai[1] = 0x1E
            return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        e.target_dir = dir_to_player(g, e)
        if player_swinging(g) and r[0] < 5 and r[1] < 5:
            if hi(next_seed(g), 4) == 0: core.play_sound(g, 0xCD)
            e.target_anim = 3
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x1E; e.bytes[1] = 0
        elif r[0] < 3 and r[1] < 3:
            k = hi(next_seed(g), 8)
            if k == 0: jump_back(0x14)
            elif k == 1: jump_back(0x3C); back_off()
            elif k < 4: jump_back(0x64); back_off()
            elif k < 6:
                if hi(next_seed(g), 4) == 0: core.play_sound(g, 0xCD)
                e.target_anim = 7
            else:
                e.target_anim = 4; back_off()
        elif r[0] < 5 and r[1] < 5:
            k = hi(next_seed(g), 5)
            if k < 2: e.target_anim = 8
            else:
                if k < 4: e.ai[1] = 0x14
                jump_back(0x1E)
        elif r[0] < 7 and r[1] < 7:
            k = hi(next_seed(g), 8)
            if k < 3: jump_back(0x3C)
            elif k == 3: jump_back(0x1E)
            elif k < 6: e.target_anim = 4
            else: e.target_anim = 8
    elif a == 12:
        if e.bytes[0] == 0 and aihelp.sees_player(g, e, r, 2, 6, 0x100000):
            e.bytes[0] = 1; calm()
            return
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0 or e.force_adjusted:
            e.target_anim = 0
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            calm()
            return
        if aihelp.ledge_turn(g, e, 0xC, 0x400000): calm()
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 6; e.flags = s32(e.flags | 0x40)
                return
            e.bytes[0] = 1; calm()
    elif a in (9, 10):
        if e.on_ground:
            e.target_anim = 0; e.ai[1] = 0x14


@port(0x8006ACCC)
def ai_c11(g, e):
    """C11: wander; when Alundra is within 5 squares it runs away from him (animation 1, 300
    frames), but if he swings his weapon it fights back: animation 3 then up to ten lunges
    toward him (4, slightly random aim), then rests (5)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if e.ai[1] & 0xFFFF: return
        if r[0] < 6 and r[1] < 6 and not 0x100000 < r[2]:
            if player_swinging(g):
                e.target_anim = 3; e.bytes[1] = 0xA
                return
            p = g.ent[0]
            e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
            e.target_anim = 1; e.ai[1] = 0x12C
            return
        aihelp.start_moving_half(g, e, 1, 0x12C)
    elif a == 3:
        if e.anim_done:
            e.target_anim = 4
            d = dir_to_player(g, e)
            s = next_seed(g)
            e.ai[1] = 0x3C
            e.bytes[1] = e.bytes[1] - 1
            e.target_dir = (d + hi(s, 9) - 4) & 0x1F
    elif a == 4:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0 or e.force_adjusted or aihelp.ledge_turn(g, e, 4, 0x200000):
            e.bytes[1] = e.bytes[1] - 1
            if e.bytes[1]:
                aihelp.start_moving(g, e, 4, 0x28, 0x1E)
                return
            e.target_anim = 5
    elif a == 5:
        if e.anim_done:
            e.target_anim = 0; e.ai[1] = 0x1E
    elif a == 1:
        if r[0] < 6 and r[1] < 6 and not 0x100000 < r[2] and player_swinging(g):
            e.target_anim = 3; e.bytes[1] = 0xA
            return
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0 or e.force_adjusted or aihelp.ledge_turn(g, e, 1, 0x200000):
            e.target_anim = 0; e.ai[1] = 0x3C
    elif a == 7:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 2; e.flags = s32(e.flags | 0x40)
                return
            if e.bytes[1] == 0: e.bytes[1] = 0xA
            e.target_anim = 3


@port(0x8006B068)
def ai_c12(g, e):
    """C12 (jumping creature, sound 0x7D at each jump): its moves run as a little script, bytes[0]
    the mode and bytes[1] the step: 1 walk / hop up ledges (jump 4, airborne 9, land 5) and turn
    at corners, 3 hop about at random, 4 pounce on Alundra three times; Alundra swinging at it
    close by makes it jump away (4, mode 3).  Hit (7): it flees (mode 3) or keeps pouncing."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 6: return
    if a == 7:
        if not e.anim_done: return
        if e.bytes[3]:
            core.play_sound(g, 0x40)
            e.target_anim = 2; e.flags = s32(e.flags | 0x40)
            return
        core.play_sound(g, 0x7D)
        b2 = e.bytes[2]
        e.target_anim = 4; e.delay = 0
        if b2 == 0:
            e.bytes[0] = 3; e.bytes[1] = 0
            return
        e.bytes[0] = 4; e.bytes[1] = 7
        return
    if ((a & M32) < 2 or a == 5) and player_swinging(g) and r[0] < 3 and r[1] < 3:
        core.play_sound(g, 0x7D)
        e.target_anim = 4
        e.bytes[0] = 3; e.bytes[1] = 0
        return
    b0 = e.bytes[0]
    if b0 == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        e.bytes[1] = 0
        if hi(next_seed(g), 4):
            e.bytes[0] = 3
            core.play_sound(g, 0x7D)
            e.target_anim = 4
            return
        e.bytes[0] = 1
        s = next_seed(g)
        e.target_anim = 1; e.ai[1] = 0x78
        e.target_dir = hi(s, 0x20)
    elif b0 == 1:
        _c12_walk(g, e, r)
    elif b0 == 3:
        b1 = e.bytes[1]
        if b1 == 1:
            e.ai[1] = (e.ai[1] & 0xFFFF) - 1
            if (e.ai[1] & 0xFFFF) == 0:
                core.play_sound(g, 0x7D)
                e.target_anim = 5; e.bytes[1] = 2
                return
            if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
                _c12_turn(g, e); return
            if aihelp.sees_player(g, e, r, 2, 5, 0):
                e.bytes[0] = 4; e.bytes[1] = 2
        elif b1 == 0:
            if e.anim_done:
                aihelp.start_moving(g, e, 9, 0x50, 0x46)
                e.bytes[1] = 1
        elif b1 == 2:
            if e.anim_done:
                s = next_seed(g)
                e.target_anim = 0; e.bytes[0] = 0
                e.ai[1] = hi(s, 0x10) + 0x1E
    elif b0 == 4:
        _c12_pounce(g, e, r)


def _c12_turn(g, e):
    """Stop and turn away (0x80028AD8)."""
    d = g.mem.u8((TURN + e.target_dir) & M32)
    e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
    e.target_dir = d


def _c12_walk(g, e, r):
    """C12 mode 1: walk, hop onto ledges up to 3 levels (steps 1-3), turn at corners (4-6)."""
    b1 = e.bytes[1]
    if b1 == 0:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; e.bytes[1] = 4; e.ai[1] = 0x3C
            e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) + 8) & 0x1F
            return
        if e.force_adjusted:
            h = s32(aihelp.height_ahead(g, e, 9, e.target_dir) - e.floor)
            if 0x300000 < h:
                _c12_turn(g, e); return
            core.play_sound(g, 0x7D)
            e.target_anim = 4
            e.delay = h; e.bytes[1] = 1
            e.item_state = e.ai[1] & 0xFFFF
            return
        if aihelp.ledge_ahead(g, e, 0x300000):
            _c12_turn(g, e); return
        if aihelp.sees_player(g, e, r, 2, 4, 0):
            e.bytes[0] = 4; e.bytes[1] = 0
    elif b1 == 1:
        if e.anim_done:
            e.ai[1] = 0xF; e.target_anim = 9; e.bytes[1] = 2
            e.pz = s32(e.pz + e.delay)
    elif b1 == 2:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            core.play_sound(g, 0x7D)
            e.target_anim = 5; e.bytes[1] = 3
            e.ai[1] = e.item_state
    elif b1 == 3:
        if e.anim_done:
            e.target_anim = 1; e.bytes[1] = 0
    elif b1 in (4, 5, 6):
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if e.ai[1] & 0xFFFF:
            if aihelp.sees_player(g, e, r, 2, 5, 0):
                e.bytes[0] = 4; e.bytes[1] = 0
            return
        e.ai[1] = 0x28
        if e.bytes[1] == 4: e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) + 0x10) & 0x1F
        if e.bytes[1] == 5: e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) - 8) & 0x1F
        if e.bytes[1] == 6:
            e.bytes[0] = 0
            s = next_seed(g)
            e.ai[1] = hi(s, 0x21) + (e.ai[1] & 0xFFFF)
        e.bytes[1] = e.bytes[1] + 1


def _c12_pounce(g, e, r):
    """C12 mode 4: jump at Alundra up to three times (bytes[2]), biting (5) when it lands next to him."""
    b1 = e.bytes[1]
    if b1 == 0:
        core.play_sound(g, 0x7D)
        e.target_anim = 4; e.bytes[1] = 1
    elif b1 in (1, 2):
        if e.anim_done or e.bytes[1] == 2:
            e.target_anim = 9
            d = dir_to_player(g, e)
            s = next_seed(g)
            e.delay = 0; e.ai[1] = 0x50
            e.bytes[2] = 3; e.bytes[1] = 3
            e.target_dir = (d + hi(s, 9) - 4) & 0x1F
    elif b1 == 3:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0 or e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
            e.bytes[2] = e.bytes[2] - 1
            if e.bytes[2] == 0:
                core.play_sound(g, 0x7D)
                e.target_anim = 5; e.bytes[1] = 6
                return
            e.target_anim = 9
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x3C
            return
        v = e.delay
        if v:
            e.delay = v = s32(v - 1)
            if v: return
        if r[0] < 3 and r[1] < 3 and r[2] == 0 and (e.ai[1] & 0xFFFF) < 0x28:
            core.play_sound(g, 0x7D)
            e.target_anim = 5
            e.target_dir = dir_to_player(g, e)
            e.bytes[1] = 4
    elif b1 == 4:
        if e.anim_done:
            e.target_anim = 3; e.bytes[1] = 5
    elif b1 == 5:
        if e.anim_done or e.target_anim == 0:
            if e.bytes[2] == 1:
                e.target_anim = 0; e.bytes[1] = 6
                return
            core.play_sound(g, 0x7D)
            e.target_anim = 4; e.bytes[1] = 7; e.delay = 0x1E
    elif b1 == 6:
        if e.anim_done or e.target_anim == 0:
            e.bytes[0] = 0
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = hi(s, 0x10) + 0x1E
    elif b1 == 7:
        if e.anim_done:
            e.target_anim = 9; e.ai[1] = 1; e.bytes[1] = 3


@port(0x8006BA1C)
def ai_c13(g, e):
    """C13: wander (start_moving every 180+ frames); Alundra close or in front makes it face him
    and then rush (animation 3 after 30 frames, or a 180-frame charge, animation 9) that stops at
    walls (animation 8) and ledges; after a hop (7) it backs away from him."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32

    def face():                         # Alundra close: face him, animation 3 in 30 frames
        e.bytes[1] = 1
        e.target_dir = dir_to_player(g, e)
        e.ai[1] = 0x1E

    def charge():
        e.target_anim = 9
        e.target_dir = dir_to_player(g, e)
        e.ai[1] = 0xB4

    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (e.ai[1] & 0xFFFF) == 0 and e.bytes[1] == 1: e.target_anim = 3
            return
        if r[0] < 5 and r[1] < 5 and not 0x200000 < r[2]:
            face(); return
        if aihelp.sees_player(g, e, r, 1, 0xA, 0x200000):
            charge(); return
        aihelp.start_moving(g, e, 1, 0xB4, 0x46)
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; return
        if aihelp.sees_player(g, e, r, 2, 3, 0x300000):
            face(); return
        if aihelp.sees_player(g, e, r, 1, 5, 0x200000):
            charge(); return
        if e.force_adjusted:
            aihelp.step_or_turn(g, e, 1, 2, 0x300000); return
        aihelp.ledge_turn(g, e, 1, 0x300000)
    elif a == 9:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; return
        if e.force_adjusted:
            e.target_anim = 8
            e.target_dir = (e.target_dir - 0x10) & 0x1F
            return
        d = e.target_dir & 0xFF
        if aihelp.ledge_turn(g, e, 1, 0):
            e.target_dir = d
            e.target_anim = 0; e.ai[1] = 0x1E
    elif a == 7:
        if e.on_ground:
            if e.bytes[1] == 1:
                e.target_anim = 9
                p = g.ent[0]
                e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
                e.ai[1] = 0x78
                e.bytes[1] = 0
            else:
                e.target_anim = 0; e.ai[1] = 0
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 6; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.ai[1] = 0
            e.bytes[1] = 0


@port(0x8006BD58)
def ai_c14(g, e):
    """C14: walk back and forth (180+ frames), checking every 32 frames: dodge away (animation 8)
    when Alundra swings at it within 4 squares, or charge him (animation 3) when he is in front."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    p = g.ent[0]
    if a == 0:
        s = next_seed(g)
        e.target_anim = 1
        e.ai[1] = hi(s, 0x10) + 0xB4
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0x1F) == 0:
            if r[0] < 5 and r[1] < 5 and p.atk_on and p.attack_addr and g.mem.u8(p.attack_addr):
                e.target_anim = 8
                e.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
                return
            if aihelp.sees_player(g, e, r, 1, 8, 0x100000):
                e.target_dir = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
                e.target_anim = 3
                e.ai[1] = 0xB4
                return
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) - 8) & 0x1F
            return
        if e.force_adjusted:
            aihelp.step_or_turn(g, e, 1, 2, 0x300000)
            return
        aihelp.ledge_turn(g, e, 1, 0x300000)
    elif a == 3:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0
        elif e.force_adjusted:
            e.target_anim = 8
            e.target_dir = (e.target_dir - 0x10) & 0x1F
    elif a in (7, 9):
        if e.on_ground: e.target_anim = 0
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 6; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0


@port(0x8006C028)
def ai_c15(g, e):
    """C15: patrol along its facing line, turning back at walls; when Alundra comes in front
    (2 squares) it sometimes cries (sound 0x94) and plays animation 3 three times facing him."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a in (0, 1):
        if e.bytes[0]:
            e.target_anim = 3
            e.target_dir = player.dir_from_delta(s32(g.ent[0].px - e.px), s32(g.ent[0].py - e.py))
            return
        if e.bytes[1] == 0:
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.bytes[1] = 4
            e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) - 8) & 0x1F
        t = e.ai[1] & 0xFFFF
        e.target_anim = 1
        if t == 0:
            e.ai[1] = 0x1E
            if aihelp.sees_player(g, e, r, 2, 2, 0):
                if hi(next_seed(g), 5) == 0: core.play_sound(g, 0x94)
                e.bytes[0] = 3
            return
        e.ai[1] = t - 1
        if e.force_adjusted:
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.bytes[1] = e.bytes[1] - 1
            e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) - 0x10) & 0x1F
    elif a == 3:
        if e.anim_done:
            e.bytes[0] = e.bytes[0] - 1
            if e.bytes[0] == 0:
                s = next_seed(g)
                e.target_anim = 0
                e.ai[1] = 0; e.bytes[1] = 0
                e.target_dir = hi(s, 4) << 3
                return
            e.cur_anim = -1
    elif a in (5, 6):
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 2; e.flags = s32(e.flags | 0x40)
                return
            if r[0] < 2 and r[1] < 2: e.bytes[0] = 3
            e.target_anim = 0


@port(0x8006C2E8)
def ai_c16(g, e):
    """C16: wander (start_moving every 120+ frames, picking a new random direction at walls up to
    three times, then resting); when Alundra is in front within 3 squares it may cry (sound 0x94)
    and charges him (animation 7); dashing (3) raises dust every 8 frames."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t == 0:
            aihelp.start_moving(g, e, 1, 0x78, 0x46)
            e.bytes[1] = 0
            return
        e.ai[1] = t - 1
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            if e.bytes[1]:
                e.bytes[1] = e.bytes[1] - 1
                s = next_seed(g)
                e.ai[1] = 0x78
                e.target_dir = hi(s, 0x20)
                return
            e.target_anim = 0; e.ai[1] = 0x14; e.bytes[0] = 0
            return
        if aihelp.sees_player(g, e, r, 3, 3, 0):
            if hi(next_seed(g), 5) == 0: core.play_sound(g, 0x94)
            _c16_charge(g, e)
            return
        if not e.force_adjusted: return
        if e.bytes[1]:
            e.bytes[1] = e.bytes[1] - 1
            s = next_seed(g)
            e.ai[1] = 0x78
            e.target_dir = hi(s, 0x20)
            return
        e.bytes[0] = e.bytes[0] + 1
        if e.bytes[0] < 4:
            e.target_anim = 0
            return
        e.bytes[0] = 0
        s = next_seed(g)
        e.ai[1] = 0x78
        e.bytes[1] = 3
        e.target_dir = hi(s, 0x20)
    elif a == 3:
        n = s32(ai_word(e, 6) + 1)
        set_ai_word(e, 6, n)
        if (n & 7) == 0:
            core.spawn_effect(g, 0, g.mem.u8(g.tile_effects_addr + 0xA), 0, e.px, e.py, e.floor)
        if e.anim_done:
            e.target_anim = 0; e.ai[1] = 0x1E
    elif a == 6:
        if e.anim_done:
            e.target_anim = 0; e.ai[1] = 0x14
            e.target_dir = (e.target_dir + 0x10) & 0x1F
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 2; e.flags = s32(e.flags | 0x40)
                return
            _c16_charge(g, e)


def _c16_charge(g, e):
    e.target_anim = 7
    e.target_dir = dir_to_player(g, e)
    set_ai_word(e, 6, 0)


@port(0x8006C654)
def ai_c17(g, e):
    """C17: stand still, then walk a random direction for 120+ frames (turning back at walls,
    stopping at ledges); when Alundra is close below it (up to 4 squares), play animation 2 / 3 / 4
    facing down or left (attack or reaction by distance)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 0:
        if (e.ai[1] & 0xFFFF) == 0:
            s = next_seed(g)
            e.ai[1] = 0x3C
            e.target_dir = hi(s, 0x20)
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if e.ai[1] & 0xFFFF: return
        s = next_seed(g)
        e.target_anim = 1
        e.ai[1] = hi(s, 0x20) + 0x78
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0
            return
        dx, dy = r[3], r[4]
        if not dy > 0 and r[0] < 4 and not 0x100000 < r[2]:
            n = None
            if r[0] == 0 and not dy < -4: n, d = 4, 0
            elif not dy < -1: n = 2
            elif not dy < -4: n = 3
            if n is not None:
                if n != 4: d = 0x18 if dx < -1 else 0
                e.target_anim = n; e.target_dir = d
                return
        if e.force_adjusted:
            e.target_dir = (e.target_dir - 0x10) & 0x1F
            e.ai[1] = 0xF0 if e.anim_quadrant == 0 else 0x78
            e.target_anim = 1
            return
        if aihelp.ledge_ahead(g, e, 0):
            e.target_anim = 0; e.ai[1] = 0
    elif a in (2, 3, 4):
        if e.anim_done:
            e.target_anim = 0; e.ai[1] = 0
    elif a == 6:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 7; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 1
            e.target_dir = player.dir_from_delta(s32(g.ent[0].px - e.px), s32(g.ent[0].py - e.py))
            e.ai[1] = 0x78


@port(0x8006C924)
def ai_c18(g, e):
    """C18 (flying, home height ai[0] squares): drift in random directions (animation 1 level,
    2 rising, 3 sinking, chosen from its height against Alundra's floor and its home height);
    when Alundra is in front it turns to him and follows his height for ten moves."""
    r = aihelp.rel_tile_z(g, e)
    a = e.target_anim & M32

    def by_height():                    # 2 below him, 1 up to 1.5 squares above, 3 higher
        dz = r[5]
        if not 0xFFFFF < dz: e.target_anim = 2
        elif 0x180000 < dz and not e.on_ground: e.target_anim = 3
        else: e.target_anim = 1

    def spotted():
        e.target_anim = 0
        e.target_dir = dir_to_player(g, e)
        e.ai[1] = 0; e.bytes[0] = 0xA

    if a == 0:
        if e.bytes[0]:
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x3C
            e.bytes[0] = e.bytes[0] - 1
            dz = r[5]
            if not 0xFFFFF < dz: e.target_anim = 2
            elif 0x180000 < dz: e.target_anim = 3
            else: e.target_anim = 1
            return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if e.ai[1] & 0xFFFF: return
            e.ai[1] = 0x78
            by_height()
            return
        if r[0] < 3 and r[1] < 3 and not 0x200000 < r[2]:
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x3C
            return
        s1 = next_seed(g); s2 = next_seed(g)
        e.target_dir = hi(s1, 0x20)
        h = s32(e.pz - ((e.ai[0] & 0xFFFF) << 16))      # height above its home level
        e.ai[1] = hi(s2, 0x29) + 0x50
        if 0x4FFFFF < h: e.target_anim = 3
        elif not -0x500000 < h: e.target_anim = 2
        else: e.target_anim = hi(next_seed(g), 3) + 1
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0: e.target_anim = 0
        if e.bytes[0]: return
        if aihelp.sees_player(g, e, r, 1, 4, 0x200000):
            spotted(); return
        if e.force_adjusted:
            e.target_anim = 0
            e.target_dir = (e.target_dir + 4) & 0x1F
    elif a in (2, 3):
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0 or (a == 3 and e.on_ground): e.target_anim = 0
        if e.bytes[0] == 0 and aihelp.sees_player(g, e, r, 1, 4, 0x200000):
            spotted()
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 6; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.bytes[0] = 0; e.ai[1] = 0


@port(0x8006CD44)
def ai_c19(g, e):
    """C19: walk until a wall or a ledge, then wait 60 frames and pick a random direction;
    when Alundra comes within 2 squares it stops, then turns to him (animation 3)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
        elif e.bytes[0]:
            e.target_dir = player.dir_from_delta(s32(g.ent[0].px - e.px), s32(g.ent[0].py - e.py))
            e.target_anim = 3
            e.bytes[0] = 0
        else:
            e.target_anim = 1
    elif a == 1:
        if r[0] < 3 and r[1] < 3 and not 0x100000 < r[2]:
            e.bytes[0] = 1
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = hi(s, 16) + 0x3C
            return
        if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = 0x3C
            e.target_dir = hi(s, 0x20)
    elif a == 5:
        if e.on_ground:
            e.target_anim = 0; e.ai[1] = 0x14
            core.play_sound(g, 0x96)
    elif a == 7:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 8; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.ai[1] = 0x14
            e.bytes[0] = 0


NO_FLOOR = 0x07800000       # height_ahead: no floor there (off the map)


@port(0x8006CF90)
def ai_c20(g, e):
    """C20 (burrowing): hidden (9) until Alundra is within 30 squares, then it tunnels after him
    underground (10, following the floor ahead) until it is under him; out (0) it hops around him
    or lunges (3 then 2: dive, 4: out) and burrows again (5) when he gets 5 squares away."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 9:
        if r[0] < 0x1F and r[1] < 0x1F:
            e.target_anim = 0xA
            e.target_dir = dir_to_player(g, e)
    elif a == 10:
        if e.bytes[0] == 3:
            e.ai[1] = (e.ai[1] & 0xFFFF) - 1
            if (e.ai[1] & 0xFFFF) == 0: e.bytes[0] = 0
            return
        if r[0] == 0 and r[1] == 0 and r[2] == 0:
            e.target_anim = 0; e.ai[1] = 0x78
            return
        d = dir_to_player(g, e)
        e.target_dir = d
        if e.force_adjusted:
            h = aihelp.height_ahead(g, e, 0xA, d)
            if h != NO_FLOOR:                   # climb / drop to the floor ahead
                dh = s32(h - e.floor)
                e.terrain = s32(e.terrain + dh)
                e.floor = s32(e.floor + dh)
                e.pz = s32(e.pz + dh)
    elif a == 0:
        if e.bytes[0] == 3:
            e.target_anim = 0xA; e.ai[1] = 0x3C
            return
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        if r[0] < 4 and r[1] < 4 and not r[2] > 0:
            k = hi(next_seed(g), 4)
            if k == 0:
                e.target_anim = 3
                e.target_dir = dir_to_player(g, e)
                e.bytes[0] = 1
            else:
                e.target_anim = 1
                d = dir_to_player(g, e)
                e.target_dir = d if k == 1 else (d + (4 if k == 2 else -4)) & 0x1F
                e.ai[1] = 0x28
            return
        if r[0] < 5 and r[1] < 5 and not r[2] > 0:
            if hi(next_seed(g), 2) == 0:
                e.target_anim = 1
                d = dir_to_player(g, e)
                s = next_seed(g)
                e.target_dir = d
                e.ai[1] = hi(s, 0x10) + 0x14
            else:
                e.target_anim = 3
                e.target_dir = dir_to_player(g, e)
                e.bytes[0] = 2
            return
        e.target_anim = 9; e.ai[1] = 0
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0; return
        if not (r[0] < 5 and r[1] < 5):
            e.target_anim = 9; e.ai[1] = 0
            return
        if not (e.force_adjusted or aihelp.ledge_ahead(g, e, 0)): return
        if aihelp.height_ahead(g, e, 0xA, e.target_dir) == NO_FLOOR: return
        if r[2] == 0:
            e.target_anim = 0
            e.target_dir = dir_to_player(g, e)
            return
        e.target_anim = 3
        e.target_dir = dir_to_player(g, e)
        e.bytes[0] = 3
    elif a == 3:
        if not e.anim_done: return
        b = e.bytes[0]
        if b == 2:
            e.target_anim = 2
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0xA; e.bytes[0] = 0
        elif b == 1:
            e.target_anim = 4; e.bytes[0] = 0
        elif b == 3:
            e.target_anim = 5; e.ai[1] = 0
    elif a == 2:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0: e.target_anim = 5
    elif a == 4:
        if e.anim_done:
            e.target_anim = 5; e.ai[1] = 0x3C
    elif a == 5:
        if e.anim_done:
            e.target_anim = 0; e.ai[1] = 0x1E
    elif a == 7:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 8; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.ai[1] = 0x14; e.bytes[0] = 0


@port(0x8006D640)
def ai_c21(g, e):
    """C21: stand, then walk 120 frames (turning back at walls and ledges); when Alundra comes
    within 2 squares on its level it stops 10 frames, then dashes at him (animation 3) leaving
    dust (the map's tile dust effect every 8 frames) until the end of the animation or a wall."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim
    if a == 0:
        if (e.ai[1] & 0xFFFF) == 0:
            s = next_seed(g)
            e.ai[1] = 0x3C
            e.target_dir = hi(s, 0x20)
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if e.ai[1] & 0xFFFF: return
        if e.bytes[0]:
            e.target_anim = 3
            e.target_dir = dir_to_player(g, e)
            e.bytes[0] = 0
            set_ai_word(e, 6, 0)
            return
        e.target_anim = 1; e.ai[1] = 0x78
    elif a == 1:
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.target_anim = 0
            return
        if r[0] < 3 and r[1] < 3 and r[2] == 0:
            e.bytes[0] = 1
            e.target_anim = 0
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0xA
            return
        if e.force_adjusted or aihelp.ledge_ahead(g, e, 0):
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = (g.mem.u8((QDIR + e.anim_quadrant) & M32) - 0x10) & 0x1F
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 2; e.flags = s32(e.flags | 0x40)
                return
            e.bytes[0] = 1
            e.target_anim = 0; e.ai[1] = 0x1E
    elif a == 3:
        n = s32(ai_word(e, 6) + 1)
        set_ai_word(e, 6, n)
        if (n & 7) == 0:
            core.spawn_effect(g, 0, g.mem.u8(g.tile_effects_addr + 0xA), 0, e.px, e.py, e.floor)
        if e.anim_done or e.force_adjusted:
            e.target_anim = 0


@port(0x8006D928)
def ai_c22(g, e):
    """C22 (hopping critters; on map 0x5F counted by their spawner, parent ai[4]): idle (7) until
    Alundra comes within 2 squares, then hop away from him / at random (animations 1-3) ten
    times, then vanish (8): removed on map 0x5F, else reset to its map record (0x8003B518)."""
    r = aihelp.rel_tile_z(g, e)
    a = e.target_anim & M32
    if a == 7:
        if r[0] < 3 and r[1] < 3:
            e.target_anim = 0; e.ai[1] = 0; e.bytes[1] = 1
    elif a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if e.ai[1] & 0xFFFF: return
        if e.bytes[0] == 0: e.bytes[0] = 0xA
        if e.bytes[1] == 1:
            n = 2 if e.on_ground else hi(next_seed(g), 3) + 1
            e.target_anim = n
            e.target_dir = hi(next_seed(g), 0x20)
            return
        if e.force_adjusted:
            d = g.mem.u8((TURN + e.target_dir) & M32)
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
        else:
            p = g.ent[0]
            d = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))
        e.target_dir = d
        e.target_anim = 2
    elif a in (1, 2, 3):
        if e.anim_done or (e.on_ground and e.target_anim == 3) or e.force_adjusted:
            e.ai[1] = 0xA
            e.target_anim = 0
            e.bytes[0] = e.bytes[0] - 1
            if e.bytes[0] == 0:
                if e.bytes[1] == 1: e.bytes[1] = 2
                else: e.target_anim = 8
    elif a == 5:
        if e.anim_done:
            if e.bytes[3]:
                if g.cur_map == 0x5F:
                    e.parent.ai[4] = (e.parent.ai[4] & 0xFFFF) - 1
                e.target_anim = 6; e.flags = s32(e.flags | 0x40)
                return
            if e.bytes[1] == 1: e.bytes[0] = 0
            e.target_anim = 0
    elif a == 8:
        if e.anim_done:
            if g.cur_map == 0x5F:
                e.parent.ai[4] = (e.parent.ai[4] & 0xFFFF) - 1
                player.remove_entity(g, e)
                return
            calls.call(g, 0x8003B518, e)


@port(0x8006DC6C)
def ai_c23(g, e):
    """C23 (things Alundra can lift): when it is let go, fall with the throw animation (thrown kind
    Entity+0x24 -> 0x800273BC[kind], -1: 3) and drop the holder link; held: animation 0."""
    if e.holder is None: return
    k = e.flags2
    if k == 0:
        e.target_anim = 0
        return
    e.target_anim = 3 if k == -1 else g.mem.s32((0x800273BC + (k << 2)) & M32)
    h = e.holder
    e.flags2 = 0
    if h is not None: h.carried = None
    e.holder = None
    e.flags = s32((e.flags | 0x30) & ~0x80)


@port(0x8006DCEC)
def ai_c24(g, e):
    """C24: does nothing (scenery that only plays its animation)."""
    return


@port(0x8006DCF4)
def ai_c25(g, e):
    """C25: wander (60+ frames per move; after 5 moves or 3 wall bumps it rests: 10, 3 hidden,
    4 when Alundra comes within 4 squares); next to Alundra it faces him and casts (animation 5):
    after 16 frames four map sprites 0xBC fly out in a cross (sometimes cast twice)."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    if a == 3:
        if r[0] < 5 and r[1] < 5 and not 0x100000 < r[2]: e.target_anim = 4
    elif a == 4:
        if e.anim_done: e.target_anim = 0
    elif a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        if r[0] < 3 and r[1] < 3:
            e.target_anim = 5
            e.target_dir = dir_to_player(g, e)
            e.ai[1] = 0x10; e.bytes[1] = 0
            return
        aihelp.start_moving(g, e, 1, 0x3C, 0x64)
    elif a == 1:
        v = e.item_state
        if v: e.item_state = v = s32(v - 1)
        if v == 0 and r[0] < 3 and r[1] < 3:
            e.target_anim = 5
            e.ai[1] = 0x10; e.bytes[1] = 0
            return
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
        if (e.ai[1] & 0xFFFF) == 0:
            e.bytes[1] = e.bytes[1] + 1
            if not e.bytes[0] < 3 or not e.bytes[1] < 5:
                e.target_anim = 0xA
                e.bytes[1] = 0; e.bytes[0] = 0
                return
            aihelp.start_moving_half(g, e, 1, 0x3C)
            return
        if e.force_adjusted:
            e.bytes[0] = e.bytes[0] + 1
            aihelp.step_or_turn(g, e, 1, 2, 0x100000)
            return
        aihelp.ledge_turn(g, e, 1, 0x100000)
    elif a == 10:
        if e.anim_done: e.target_anim = 3
    elif a == 5:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (e.ai[1] & 0xFFFF) == 0:
                z = s32(e.pz + 0x200000)
                for k in (0, 8, 0x10, 0x18):
                    entity.spawn_warp_entity(g, e, 1, 0xBC, e.px, e.py, z, (e.target_dir + k) & 0x1F if k else e.target_dir)
        if e.anim_done:
            if e.delay == 0 and hi(next_seed(g), 4) == 0:
                e.cur_anim = -1; e.ai[1] = 0x10; e.delay = 1
                return
            s = next_seed(g)
            e.delay = 0
            e.target_anim = 1
            e.item_state = 0x1E
            e.ai[1] = hi(s, 0x10) + 0x1E
    elif a == 7:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 8; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.ai[1] = 0x28
