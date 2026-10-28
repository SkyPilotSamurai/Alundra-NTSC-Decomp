"""Built-in sprite programs, group 6: C65-C78, C84, C94, C255, D1-D46, E0-E28, F1, F255
(US ALUN_CD.EXE 0x8007D778-0x80082554), and the entity helpers only they call."""
from .registry import port
from .core import s32, s16, next_seed, hi
from . import aihelp, core, entity, player, calls

M32 = 0xFFFFFFFF
TURN = 0x80028AD8           # u8[32]: the direction turned away
SIN, COS = 0x800282D8, 0x800286D8   # s16[512] circle tables (C66-C68)
DX, DY = 0x80023654, 0x80023694     # s16 step per direction
TARGETS, TDISTS = 0x80142B80, 0x80142C80   # find_targets() result arrays
MSG = 0x80124858            # text buffer of the item message (C255)
NULL = 0x80000000           # where stores through a NULL Entity * land (kernel RAM 0x0...)


def _par(g, e):
    """e's parent as the game dereferences it: the record at NULL when it has none."""
    return _deref(g, e.parent)


def _deref(g, x):
    """An entity pointer as the game dereferences it: None (NULL) is the record at 0."""
    if x is None:
        from .ai_g5 import _At
        return _At(g, 0)
    return x


def _leader(g):
    return _deref(g, entity.ent_at(g, g.mem.u32(LEADER)))


def _abs(v):
    """negu of a negative s32 (0x80000000 stays negative, like the game)."""
    return s32(-v) if v < 0 else v


def _hurt(g, e):
    """take_hit; bytes[3] = 1 when the hit killed it (the D programs' common step)."""
    if player.take_hit(g, e) != 0:
        e.bytes[3] = 1


def _away(g, e):
    """Direction from Alundra to e."""
    p = g.ent[0]
    return player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))


def _atk_kind(g, e):
    """Low nibble of the first byte of the touching attacker's attack record."""
    t = e.touching                        # (no attacker: the game reads through NULL, low RAM)
    a = t.attack_addr if t is not None else g.mem.u32(NULL + 0x1C8)
    return g.mem.u8(a) & 0xF


def _w274(e):
    b = e.bytes
    return s32(b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24)


def _set_w274(e, v):
    v &= M32
    e.bytes[0] = v; e.bytes[1] = v >> 8; e.bytes[2] = v >> 16; e.bytes[3] = v >> 24


def _wai(e, k):
    """Word at Entity+0x280+2k (ai[k], ai[k+1])."""
    return s32((e.ai[k] & 0xFFFF) | (e.ai[k + 1] & 0xFFFF) << 16)


def _set_wai(e, k, v):
    e.ai[k] = v & 0xFFFF; e.ai[k + 1] = (v >> 16) & 0xFFFF


def _die_anim(e, a):
    """The E programs' death animation: anim a, collidable bits 0x30 off, 0x40 on."""
    e.target_anim = a
    e.flags = (e.flags | 0x40) & ~0x30


# ====================================================================== C programs
@port(0x8007D778)
def ai_c65(g, e):
    """C65 (wind / whirlpool): pushes the first entity its attack can hurt (nearest first)
    that is within 0x140 x 0xF0 pixels of it, sideways around it (direction from it + 0x14;
    push Entity+0xCC / +0xD0)."""
    n = entity.find_targets(g, e, 1, g.mem.u8(e.attack_addr) & 0xF, TARGETS, TDISTS)
    i = 0
    while i < n:
        t = entity.ent_at(g, g.mem.u32(TARGETS + 4 * i))
        dx = s32(t.px - e.px); dy = s32(t.py - e.py)
        i += 1
        if 0x1400000 < _abs(dx) or 0xF00000 < _abs(dy): continue
        k = ((player.dir_from_delta(dx, dy) + 0x14) & 0x1F) * 16
        t.pafx = s32(g.mem.s16(0x800206F0 + k) * 0x300)
        t.pafy = s32(g.mem.s16(0x800204F0 + k) << 9)
        return


def _orbit_pos(g, e, t, scale):
    e.px = s32(e.delay + s32(g.mem.s16(SIN + t * 2) * scale))
    e.py = s32(e.item_state + s32(g.mem.s16(COS + (e.ai[1] & 0xFFFF) * 2) * scale))


def _orbit(g, e, scale, step3):
    """C66-C68 body: circles around the point (Entity+0x278, +0x27C) (angle ai[1], 512
    steps, radius scale); while the map record before its own (ref_id - 1) has no entity
    left it goes on to the next phase."""
    b0 = e.bytes[0]
    if b0 == 0 or b0 == 1:
        if b0 == 0:
            e.bytes[0] = 1
            e.ai[1] = 0x180
            e.delay = s32(e.px - s32(g.mem.s16(SIN + 0x300) * scale))
            e.item_state = s32(e.py - s32(g.mem.s16(COS + 0x300) * scale))
        t = ((e.ai[1] & 0xFFFF) + 4) & 0x1FF
        e.ai[1] = t
        _orbit_pos(g, e, t, scale)
        if len(entity.select(g, e, s32(e.ref_id - 1))) == 0:
            step3(g, e)
        return
    if b0 == 2:
        t = ((e.ai[1] & 0xFFFF) + 4) & 0x1FF
        c = (e.bytes[1] - 1) & 0xFF
        e.bytes[1] = c
        e.ai[1] = t
        _orbit_pos(g, e, t, scale)
        return c


def _next_4(g, e):
    e.bytes[1] = 4
    e.bytes[0] += 1


@port(0x8007D894)
def ai_c66(g, e):
    """C66: circles (radius 0x800 per unit) until its record's predecessors are gone, then
    after 4 more frames status 3 and sound 0xE1."""
    if _orbit(g, e, 0x800, _next_4) == 0:
        e.estatus = 3
        core.play_sound(g, 0xE1)


@port(0x8007DA28)
def ai_c67(g, e):
    """C67: C66 with radius 0xC00."""
    if _orbit(g, e, 0xC00, _next_4) == 0:
        e.estatus = 3
        core.play_sound(g, 0xE1)


def _c68_next(g, e):
    e.bytes[1] = 2
    e.bytes[0] += 1
    core.play_sound(g, 0x78)


@port(0x8007DBF0)
def ai_c68(g, e):
    """C68: circles (radius 0x1400) until its record's predecessors are gone (sound 0x78),
    flies off outward (anim 3) until it hits a wall or 80 frames pass (sound 0xE1, anim 2,
    solid), waits until Alundra is 3 x 2 squares away (then collidable 0x81), and with
    bytes[2] >= 4 at the end of anim 4 it is destroyed (sound 0x2E, effect 0xA)."""
    b0 = e.bytes[0]
    if b0 < 3:
        if _orbit(g, e, 0x1400, _c68_next) == 0:
            e.target_anim = 3
            e.bytes[1] = 0x50
            e.bytes[0] += 1
            e.target_dir = (0x18 - ((e.ai[1] & 0xFFFF) >> 4)) & 0x1F
    elif b0 == 3:
        c = (e.bytes[1] - 1) & 0xFF
        e.bytes[1] = c
        if e.force_adjusted != 0 or c == 0:
            core.play_sound(g, 0xE1)
            e.target_anim = 2
            e.flags |= 0x100
            e.bytes[0] += 1
    elif b0 == 4:
        p = g.ent[0]
        if 0x2FFFFF < _abs(s32(e.px - p.px)) or 0x1FFFFF < _abs(s32(e.py - p.py)):
            e.flags = (e.flags & ~2) | 0x81
            e.bytes[0] += 1
    elif b0 == 5:
        if e.target_anim == 4 and e.anim_done != 0:
            if e.bytes[2] >= 4:
                core.play_sound(g, 0x2E)
                entity.destroy_entity(g, e, 0xA)
                return
            e.target_anim = 2


@port(0x80083204, ret=True)
def bump_side(g, a, b):
    """Where b touches a: 0 / 1 = below / above (b's x within the wider box), 2 / 3 = left /
    right of it (y within), -1 neither."""
    x0, x1 = a.mpx, b.mpx
    if x0 < x1: w, d = a.sizex, s32(x1 - x0)
    else: w, d = b.sizex, s32(x0 - x1)
    if not w < d:
        return 1 if b.py < a.py else 0
    y0, y1 = a.mpy, b.mpy
    if y0 < y1: w, d = a.sizey, s32(y1 - y0)
    else: w, d = b.sizey, s32(y0 - y1)
    if not w < d:
        return 2 if b.px < a.px else 3
    return -1


PUSH_DIR = 0x80028AF8       # u8[4]: direction of a push from bump_side 0-3


@port(0x8007DEFC)
def ai_c69(g, e):
    """C69 (pushable block): after Alundra pushes against it for 20 frames it slides
    (anim 1) away from him until it hits something (anim 0)."""
    a = e.target_anim
    if a == 0:
        p = g.ent[0]
        if e.x_collision is p or p.x_collision is e:
            e.delay = s32(e.delay + 1)
            if e.delay == 0x14:
                e.delay = 0
                e.target_anim = 1
                e.target_dir = g.mem.u8(PUSH_DIR + bump_side(g, p, e))
            return
        e.delay = 0
    elif a == 1:
        if e.force_adjusted != 0:
            e.target_anim = 0


THROWN_ANIM = 0x80028198    # s32[]: animation when thrown, by throw kind (Entity+0x24)


@port(0x8007DFC0)
def ai_c70(g, e):
    """C70 (things Alundra lifts): held: anim 0; let go: thrown animation, collidable
    0x34 on, 0x80 off, holder link dropped."""
    if e.holder is None: return
    k = e.flags2
    if k == 0:
        e.target_anim = 0
        return
    e.target_anim = 3 if k == -1 else g.mem.s32((THROWN_ANIM + (k << 2)) & M32)
    h = e.holder
    e.flags2 = 0
    if h is not None: h.carried = None
    e.holder = None
    e.flags = (e.flags | 0x34) & ~0x80


@port(0x8007E040)
def ai_c71(g, e):
    """C71 (map 92 platform): waits 40 frames, rises (anim 1) until it lands (anim 2),
    then frees sprite 0x189 riding it or held by Alundra on it (status 3, bytes[0] 1), and
    at the end of the animation resets: program C <- bytes[1], 0xA0 (16.16) higher,
    sets the word at 0x801E5F40."""
    b0 = e.bytes[0]
    if b0 == 0:
        e.bytes[0] = 1
        e.ai[1] = 0x28
    elif b0 == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t == 0:
            e.target_anim = 1
            e.bytes[0] = 2
            e.flags |= 0x100
    elif b0 == 2:
        if e.collided_z != 0 or e.on_ground != 0:
            e.target_anim = 2
            e.bytes[0] = 3
    elif b0 == 3:
        e.bytes[0] = 4
        e.flags &= ~0x80
        t = e.riding
        if t is g.ent[0]: t = g.ent[0].carried
        if t is not None and t.sprite_index == 0x189:
            t.estatus = 3
            t.bytes[0] = 1
    elif b0 == 4:
        if e.anim_done != 0:
            c = e.bytes[1]
            e.bytes[0] = 0
            g.mem.w32(0x801E5F40, 1)
            e.target_anim = 0
            e.fz = 0
            e.flags = (e.flags & ~0x100) | 0x80
            e.prog_c = c
            e.pz = s32(e.pz + 0xA00000)


ANSWER = 0x80124854         # the yes / no box writes its answer here (C72)


@port(0x8007E1A4)
def ai_c72(g, e):
    """C72 (save point / question, started by F-program word Entity+0x274 = 1): message
    0x40, then after 60 frames the yes / no question (texts 0x41, 0x42) and on yes after
    60 more frames 0x80031AC4 (the save menu); ends by clearing mode flag 4."""
    w = _w274(e)
    if w == 2:
        d = s32(e.delay - 1)
        e.delay = d
        if d != -1: return
        g.mem.w32(ANSWER, 0)
        a = calls.call(g, 0x80083FC4, 0x41)
        b = calls.call(g, 0x80083FC4, 0x42)
        if calls.call(g, 0x80052310, a, b, ANSWER) != 0:
            _set_w274(e, _w274(e) + 1)
        _set_w274(e, _w274(e) + 1)
        return
    if w == 1:
        if calls.call(g, 0x80045F8C) != 0:
            _c72_end(g, e)
            return
        calls.call(g, 0x8004608C, calls.call(g, 0x80083FC4, 0x40), 1)
        calls.call(g, 0x8004600C, 4)
        e.delay = 0x3C
        _set_w274(e, _w274(e) + 1)
    elif w == 4:
        if g.mem.s32(ANSWER) == 0: return
        calls.call(g, 0x80045FE4)
        if g.mem.s32(ANSWER) != 1:
            _c72_end(g, e)
            return
        e.delay = 0x3C
        _set_w274(e, _w274(e) + 1)
    elif w == 5:
        d = s32(e.delay - 1)
        e.delay = d
        if d == -1:
            calls.call(g, 0x80031AC4)
            _c72_end(g, e)


def _c72_end(g, e):
    _set_w274(e, 0)
    g.mode_flags &= ~4


@port(0x8007E330)
def ai_c73(g, e):
    """C73 (lifted things that vanish when they land): held: anim 0; let go: anim 2, flag
    0x10 on, holder link dropped; on the ground: status 3."""
    if e.holder is not None:
        if e.flags2 != 0:
            h = e.holder
            e.target_anim = 2
            e.flags2 = 0
            if h is not None: h.carried = None
            e.holder = None
            e.flags |= 0x10
            return
        e.target_anim = 0
        return
    if e.on_ground != 0:
        e.estatus = 3


@port(0x8007E39C)
def ai_c74(g, e):
    """C74 (floating platform / geyser): anim 1 throws spray (effect 0xE) every 4 frames;
    anims 2 / 5 float toward height word Entity+0x274; Alundra standing on it in anim 2
    sinks it (anim 3, back to 2 when he leaves); anim 4 launches him (z force 0x98000)
    when he jumps off upward (anim 5)."""
    a = e.target_anim
    p = g.ent[0]
    if a == 1:
        if e.frame_counter & 3: return
        f = core.spawn_effect(g, 0, 0xE, 0, e.px, e.py, e.pz)
        if f is None: return
        r1 = next_seed(g); r2 = next_seed(g)
        f.vz = 0x20000
        f.vx = s32(hi(r1, 0x30001) + 0xFFFE8000)
        f.vy = s32(hi(r2, 0x20001) + 0xFFFF0000)
    elif a == 2:
        e.fz = s32(_w274(e) - e.pz) >> 1
        if p.riding is e:
            e.fz = -0x8000
            e.target_anim = 3
    elif a == 3:
        if p.riding is not e:
            e.target_anim = 2
    elif a == 4:
        if p.riding is not e:
            if p.fz > 0:
                p.fz = 0x98000
                e.target_anim = 5
                return
            e.target_anim = 2
    elif a == 5:
        e.fz = s32(_w274(e) - e.pz) >> 1


def _ent_word(e, idx):
    """lw (Entity+0x274 + 4 idx): the words the C75 swing keeps there (0: +0x274, 1: delay)."""
    off = 0x274 + 4 * idx
    if off == 0x274: return _w274(e)
    if off == 0x278: return e.delay
    if off == 0x27C: return e.item_state
    if 0x280 <= off <= 0x290: return _wai(e, (off - 0x280) // 2)
    raise NotImplementedError(f'C75 word index {idx}')


@port(0x8007E594)
def ai_c75(g, e):
    """C75 (thrown chain ball / boomerang): while its timer (word +0x290, frozen while
    Square is held) runs, it swings around Alundra (radius word +0x288 growing / shrinking
    between the bounds in +0x274 / +0x278 by +0x27C per frame, angle +0x28C stepping by
    +0x280); when it runs out it flies off toward the nearest target it can hurt (within
    0x3840 squared pixels) or in a random direction (speed 0x100 per step)."""
    if not g.pad_held & 0x20:
        _set_wai(e, 8, _wai(e, 8) - 1)
    v = _wai(e, 8)
    if v > 0:
        k = _wai(e, 2)
        r = _wai(e, 4)
        lim = _ent_word(e, k)
        if not lim < r:
            r = s32(r + s32(e.item_state + ((1 if r < _w274(e) else 0) << 6)))
            ok = r < lim
        else:
            r = s32(r - e.item_state)
            ok = lim < r
        if not ok:
            r = lim
            _set_wai(e, 2, k ^ 1)
        ang = (_wai(e, 6) + _wai(e, 0)) & 0xFF
        sn = g.mem.s16(0x800204F0 + ang * 2)
        cs = g.mem.s16(0x800206F0 + ang * 2)
        _set_wai(e, 4, r)
        _set_wai(e, 6, ang)
        p = g.ent[0]
        e.pafx = s32(p.px + s32(s32(sn * r) * 3) + p.fx - e.px)
        e.pafy = s32(p.py + s32(s32(cs * r) * 2) + p.fy - e.py)
        e.fz = s32(s32(p.pz - e.pz) + 0x80000)
        return
    if v == 0:
        n = entity.find_targets(g, e, 1, g.mem.u8(e.attack_addr) & 0xF, TARGETS, TDISTS)
        if n != 0 and g.mem.s32(TDISTS) < 0x3840:
            t = entity.ent_at(g, g.mem.u32(TARGETS))
            k = player.dir_from_delta(s32(t.px - e.px), s32(t.py - e.py)) * 2
        else:
            k = hi(next_seed(g), 0x20) * 2
        e.fz = 0xA0000
        _set_w274(e, g.mem.s16(DX + k) << 8)
        e.flags |= 0x2130
        e.delay = g.mem.s16(DY + k) << 8
    e.pafx = _w274(e)
    e.pafy = e.delay


@port(0x8003B5E8, ret=True)
def push_dir(g, e, p):
    """Direction p pushes e from, when p bumped into e (else -1): 0 / 16 from below / above
    when their x boxes overlap, else 24 / 8 from the right / left."""
    if p.x_collision is not e: return -1
    d = s32(p.mpx - e.mpx)
    if d >= 0: inside = not e.sizex < d
    else: inside = not p.sizex < s32(-d)
    if inside:
        return (1 if p.py < e.py else 0) << 4
    return 8 if p.px < e.px else 0x18


@port(0x8007E820)
def ai_c76(g, e):
    """C76 (heavy block / lever): pushed by Alundra for 31 frames it moves (anim 1, sound
    0x19) away from him; when he lets go it stops (sound 0x19 stopped)."""
    if g.ent[0].x_collision is e:
        w = _w274(e)
        if not w < 0x1F:
            core.play_sound(g, 0x19)
            e.target_anim = 1
            d = push_dir(g, e, g.ent[0])
            if d != -1:
                e.target_dir = (d + 0x10) & 0x1F
                return
        else:
            _set_w274(e, w + 1)
            return
    if e.target_anim == 1:
        calls.call(g, 0x8004A7B4, 0x19)
    _set_w274(e, 0)
    e.target_anim = 0


@port(0x8007E8C8)
def ai_c94(g, e):
    """C94 (rolling boulder): breaks blocks it touches; dust (effect 0x19, sub = facing
    quadrant) every 4 frames thrown back at half its speed."""
    player.break_blocks(g, e)
    if e.frame_counter & 3: return
    f = core.spawn_effect(g, 0, 0x19, e.anim_quadrant, e.px, e.py, s32(e.pz + 0x80000))
    if f is not None:
        f.vx = s32(-e.fx) >> 1
        f.vy = s32(-e.fy) >> 1


# ---------------------------------------------------------------------- C78
LEADER = 0x801248D8         # Entity * of the C78 boss that leads the circle dance
CX, CY = 0x801248DC, 0x801248E0     # centre of the circle (16.16)
CANG, CRAD = 0x801248E4, 0x801248E8  # its angle (0-0x1FF) and radius
NFAKE, NCOPY, ROW = 0x801248EC, 0x801248F0, 0x801248F4   # copies wanted / alive, table row
ORBIT = 0x800281D4          # u32[3][8]: start angles of the 8 dancers per row
SPOTS = 0x80028234          # u32[2][3]: directions of the 3 copies thrown at Alundra


@port(0x8003A534)
def set_box(g, e, ox, oy, oz, w, h, d):
    """Collision box of an entity: offset (ox, oy, oz) and size (w, h, d) in pixels."""
    e.f_108 = s32(-(ox << 16)); e.f_10C = s32(-(oy << 16))
    e.modx = s32(ox << 16); e.mody = s32(oy << 16); e.modz = s32(oz << 16)
    e.f_0FC = s32(0x04E00000 - s32((ox + w) << 16))
    e.f_100 = s32(0x03C00000 - s32((oy + h) << 16))
    e.f_104 = s32(0x07800000 - s32((oz + d) << 16))
    e.sizex = s32((w << 16) - 1) if w != 0 else 0
    e.sizey = s32((h << 16) - 1) if h != 0 else 0
    e.sizez = s32((d << 16) - 1) if d != 0 else 0


def _copy_box(g, t, hb):
    """C78: a thrown copy gets Alundra's box (his sprite header + 0x18) with its own z."""
    th = t.header_addr
    set_box(g, t, g.mem.s8(hb), g.mem.s8(hb + 1), g.mem.s8(th + 0x1A),
            g.mem.u8(hb + 3), g.mem.u8(hb + 4), g.mem.u8(th + 0x1D))


def _spawn_c4(g, e, x, y, z, d):
    return entity.spawn_warp_entity(g, e, 1, 0xC4, x, y, z, d)


@port(0x8007EF70)
def ai_c78(g, e):
    """C78 (the mirror-image boss of map sprite 0xC4): the leader (bytes[0] 0) and its 7
    look-alikes (bytes[0] 1) dance on a circle (state bytes[1] 1-2, centre / radius in the
    globals at 0x801248DC); only the real one can be hurt; it also appears at random spots,
    throws copies at Alundra (bytes[0] 2: falling, 3: shadows that chase him on the floor)."""
    p = g.ent[0]
    hb = (p.header_addr + 0x18) & M32
    if e.bytes[0] == 1 and _leader(g).bytes[1] == 2:
        if e.target_anim == 8: player.remove_entity(g, e)
        a = e.target_anim
        if a == 0 or a == 5:
            core.play_sound(g, 0x120)
            e.target_anim = 4
    a = e.target_anim & M32
    if a == 8:
        v = e.ai[1] & 0xFFFF
        if v != 0:
            e.ai[1] = v - 1
        elif ((e.bytes[0] - 2) & M32) < 2:
            core.play_sound(g, 0x121)
            e.target_anim = 0xD
            t = _spawn_c4(g, e, e.px, s32(e.py + 0x10000), e.pz, 0)
            if t is not None:
                t.target_anim = 0xC
                t.contents_item = 0
                t.bi_c = 0x4E
        else:
            b1 = e.bytes[1]
            if b1 == 1:
                core.play_sound(g, 0x122)
                e.target_anim = 5
            elif b1 == 9 and g.mem.s32(NCOPY) == 0:
                e.bytes[1] = 0
                e.ai[1] = 0x78
            elif e.bytes[1] == 0xA:
                _c78_throw(g, e, hb)
            elif e.bytes[1] == 0:
                _c78_start(g, e)
    elif a == 9:
        if ((e.bytes[0] - 2) & M32) < 2:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if t == 0:
                e.target_anim = 8
                e.ai[1] = 1
                e.target_dir = (e.target_dir + 0x10) & 0x1F
            elif e.force_adjusted != 0:
                player.remove_entity(g, e)
                g.mem.w32(NCOPY, g.mem.s32(NCOPY) - 1)
    elif a == 0:
        v = e.ai[1] & 0xFFFF
        if v != 0:
            e.ai[1] = v - 1
        else:
            b1 = e.bytes[1]
            if b1 == 0:
                core.play_sound(g, 0x120)
                e.target_anim = 4
            elif 3 <= b1 <= 7:
                if b1 == 3:
                    e.target_dir = g.mem.u8(0x80028AF8 + hi(next_seed(g), 4))
                k = hi(next_seed(g), 2)
                d = e.target_dir
                if d == 0 or d == 0x10:
                    e.target_dir = 0x18 if k else 8
                else:
                    e.target_dir = 0 if k else 0x10
                e.bytes[1] += 1
                core.play_sound(g, 0x11F)
                e.target_anim = 0xF
                e.ai[1] = 0x1E
            elif b1 == 8:
                e.bytes[1] = 0
    elif a == 4:
        if e.anim_done != 0:
            if e.bytes[0] == 0:
                e.target_anim = 8
                e.ai[1] = 0x78
                e.bytes[1] = 0xA
            else:
                player.remove_entity(g, e)
    elif a == 3 or a == 5:
        if e.anim_done != 0:
            e.target_anim = 0
    elif a == 7:
        if e.anim_done != 0:
            if e.bytes[1] == 1:
                e.bytes[1] = 2
            if e.bytes[3] != 0:
                e.contents_item = 0
                e.target_anim = 2
                e.flags |= 0x40
            else:
                core.play_sound(g, 0x120)
                e.target_anim = 4
    elif a == 15:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t & 3:
            c = _spawn_c4(g, e, e.px, e.py, e.pz, e.target_dir)
            if c is not None:
                c.target_anim = 0xB
                c.bi_c = 0x4E
        if (e.ai[1] & 0xFFFF) == 0 or e.force_adjusted != 0:
            e.target_anim = 0
            e.ai[1] = 0xA
    elif a == 11 or a == 12 or a == 14:
        if e.anim_done != 0:
            player.remove_entity(g, e)
    elif a == 13:
        if e.anim_done != 0:
            e.target_anim = 0x10
            if e.bytes[0] == 2:
                e.target_dir = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
    elif a == 16:
        t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
        e.ai[1] = t
        if not t & 7:
            c = _spawn_c4(g, e, e.px, e.py, e.pz, e.target_dir)
            if c is not None:
                c.target_anim = 0xE
                c.bi_c = 0x4E
                _copy_box(g, c, hb)
                c.pz = p.floor
        if e.force_adjusted != 0 or p.touching is e:
            g.mem.w32(NCOPY, g.mem.s32(NCOPY) - 1)
            entity.destroy_entity(g, e, -1)
    _c78_dance(g, e)


def _c78_throw(g, e, hb):
    """bytes[1] 0xA: 3 copies fall at random squares (2/3) or 3 shadows appear around
    Alundra (1/3)."""
    e.bytes[1] = 9
    r = next_seed(g)
    g.mem.w32(NCOPY, 0)
    if hi(r, 3) != 0:
        tm = 0xA
        for _ in range(3):
            r1 = next_seed(g); r2 = next_seed(g)
            t = _spawn_c4(g, e, s32(hi(r1, 7) * 0x180000 + 0xC00000), s32((hi(r2, 7) << 20) + 0xB00000), e.pz, 0)
            if t is not None:
                t.target_anim = 8
                t.bi_c = 0x4E
                t.bytes[0] = 2
                t.ai[1] = tm
                t.contents_item = 0
                t.flags |= 0x2000
                g.mem.w32(NCOPY, g.mem.s32(NCOPY) + 1)
            tm += 0x28
    else:
        tab = SPOTS + hi(next_seed(g), 2) * 12
        p = g.ent[0]
        for k in range(3):
            t = _spawn_c4(g, e, p.px, p.py, p.floor, g.mem.s32(tab + 4 * k))
            if t is not None:
                _copy_box(g, t, hb)
                t.target_anim = 9
                t.bi_c = 0x4E
                t.ai[1] = 0x1E
                t.bytes[0] = 3
                t.contents_item = 0
                t.pz = p.floor
                t.flags |= 0x2000
                g.mem.w32(NCOPY, g.mem.s32(NCOPY) + 1)


def _c78_start(g, e):
    """bytes[1] 0: half the time jump to a random spot (anim 5, sound 0x122, then the
    turns of bytes[1] 3-7); else start the circle dance with 1-8 look-alikes."""
    r = next_seed(g)
    if hi(r, 2) != 0:
        r1 = next_seed(g); r2 = next_seed(g)
        e.px = s32(hi(r1, 5) * 0x180000 + 0xD80000)
        e.py = s32((hi(r2, 5) << 20) + 0xC00000)
        core.play_sound(g, 0x122)
        e.bytes[1] = 3
        e.target_anim = 5
        e.target_dir = 0
        e.ai[1] = 2
        return
    g.mem.w32(CANG, 0)
    g.mem.w32(CRAD, 0x2800)
    e.bytes[2] = 0
    e.ai[4] = 0
    r1 = next_seed(g); r2 = next_seed(g); r3 = next_seed(g)
    g.mem.w32(LEADER, entity.ent_addr(e))
    g.mem.w32(NCOPY, 0)
    g.mem.w32(NFAKE, hi(r1, 8))
    g.mem.w32(ROW, hi(r2, 3))
    e.item_state = hi(r3, 2) + 1
    while True:
        n = g.mem.s32(NFAKE); c = g.mem.s32(NCOPY)
        row = (g.mem.s32(ROW) << 5) + ORBIT
        if n != c:
            t = _spawn_c4(g, e, e.px, e.py, e.pz, 0)
            v = g.mem.u32((c * 4 + row) & M32) & 0x1FF
            if t is None:       # the game does not test the spawn: the stores go to RAM 0x0
                m = g.mem
                m.w8(NULL + 0x274, 1); m.w8(NULL + 0x275, 1); m.w32(NULL + 0x78, 0x4E)
                m.w32(NULL + 0x88, 8); m.w32(NULL + 0x7C, 0x23); m.w32(NULL + 0x278, v)
                m.w16(NULL + 0x282, c << 4)
            else:
                t.bytes[0] = 1
                t.bytes[1] = 1
                t.bi_c = 0x4E
                t.target_anim = 8
                t.bi_d = 0x23
                t.delay = v
                t.ai[1] = c << 4
        else:
            e.bytes[1] = 1
            e.ai[1] = c << 4
            e.delay = g.mem.u32((c * 4 + row) & M32) & 0x1FF
        c = s32(g.mem.s32(NCOPY) + 1)
        g.mem.w32(NCOPY, c)
        if c == 8: return


def _c78_dance(g, e):
    """Every frame while dancing (bytes[1] 1-2): the leader turns the circle (and after
    item_state turns makes it shrink to 0x1200 and grow back); each dancer sits on it at
    its angle (Entity+0x278) and faces along it."""
    if not ((e.bytes[1] - 1) & M32) < 2: return
    L = _leader(g)
    if (L.ai[4] & 0xFFFF) == 3:
        core.play_sound(g, 0x120)
        e.target_anim = 4
    if L is e:
        a = (g.mem.s32(CANG) - 4) & 0x1FF
        g.mem.w32(CANG, a)
        if a == 0: e.ai[4] = (e.ai[4] & 0xFFFF) + 1
        a = g.mem.s32(CANG)
        g.mem.w32(CX, (g.mem.s16(SIN + a * 2) << 11) + 0x1080000)
        g.mem.w32(CY, (g.mem.s16(COS + a * 2) << 11) + 0xE00000)
        go = True
        if e.bytes[2] == 0:
            if (e.ai[4] & 0xFFFF) == e.item_state:
                core.play_sound(g, 0x122)
                e.bytes[2] = 1
            go = e.bytes[2] != 0
        if go:
            r = g.mem.s32(CRAD)
            g.mem.w32(CRAD, r - 0x80 if e.bytes[2] == 1 else r + 0x80)
            if g.mem.s32(CRAD) == 0x1200: e.bytes[2] = 2
            if g.mem.s32(CRAD) == 0x2800: e.bytes[2] = 0
    r = g.mem.s32(CRAD)
    d = (e.delay + 2) & 0x1FF
    e.delay = d
    e.px = s32(g.mem.s32(CX) + s32(g.mem.s16(SIN + d * 2) * r))
    a = e.target_anim
    e.py = s32(g.mem.s32(CY) + s32(g.mem.s16(COS + e.delay * 2) * r))
    if a == 0 or a == 8:
        d = e.delay
        q = (d + 0xF if d < 0 else d) >> 4
        if ((q - 4) & M32) < 8: e.target_dir = 8
        elif ((q - 0xC) & M32) < 8: e.target_dir = 0
        elif ((q - 0x14) & M32) < 8: e.target_dir = 0x18
        else: e.target_dir = 0x10


# ---------------------------------------------------------------------- C84
@port(0x8007FDC0)
def ai_c84(g, e):
    """C84 (the walker carrying a rider, parent = the rider sprite): keeps the rider on
    its back (bobbing by the rider's bytes), wanders (start_moving), turns away from a
    sprite 0x1D8 it touches (anim 1), and on hits (anim 3) throws the rider off or dies:
    bytes[3] 1-3 runs the boss death 0x80083394, 4+ removes the rider."""
    q = e.parent
    if (q.ai[4] & 0xFFFF) != 0:
        q.ai[4] = 0
        e.target_anim = 3
    b0 = q.bytes[0]
    q.px = e.px
    q.py = s32(e.py - 0x100000)
    if b0 != q.bytes[2]:
        q.pz = s32(q.pz - 0x8000)
        q.bytes[2] += 1
    else:
        b1 = q.bytes[1]
        if b1 != 0:
            q.bytes[1] = b1 - 1
        elif q.pz != s32(e.pz + 0x300000):
            q.pz = s32(q.pz + 0x8000)
            q.bytes[0] -= 1
            q.bytes[2] -= 1
    b3 = e.bytes[3]
    if b3 != 0 and e.target_anim == 0:
        if b3 < 4:
            calls.call(g, 0x80083394, e)
            return
        e.target_anim = 4
        e.flags |= 0x40
        player.remove_entity(g, q)
        e.bi_c = 0
        return
    a = e.target_anim & M32
    if a == 0:
        found = None
        for i in range(0x40):
            t = g.ent[i]
            if ((t.estatus - 2) & M32) < 2 and t.frozen == 0 and t is not e and t.sprite_index == 0x1D8:
                found = t
                break
        if found is not None and _overlap(found.mpx, e.mpx, e.sizex, found.sizex) \
                and _overlap(found.mpy, e.mpy, e.sizey, found.sizey):
            e.target_anim = 1
            e.target_dir = player.dir_from_delta(s32(e.px - found.px), s32(e.py - found.py))
            e.ai[1] = 0x1E
            return
        v = e.ai[1] & 0xFFFF
        if v != 0:
            e.ai[1] = v - 1
            return
        aihelp.start_moving(g, e, 1, 0x3C, 0x46)
        if e.bytes[0] != 0:
            e.bytes[0] = 0
            p = g.ent[0]
            e.target_dir = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
    elif a == 1:
        v = e.ai[1] & 0xFFFF
        if v != 0:
            e.ai[1] = v - 1
        else:
            e.target_anim = 0
            e.ai[1] = hi(next_seed(g), 0x1F) + 0x3C
    elif a == 2:
        if e.anim_done != 0:
            e.target_anim = 0
    elif a == 3:
        if e.anim_done != 0:
            if q.bytes[3] != 0:
                e.ai[1] = 0x12C
                e.ai[5] = 0x1E
                e.bytes[3] = 1
                e.target_anim = 0
                e.flags &= ~3
                return
            r = next_seed(g)
            e.target_anim = 0
            q.target_anim = 0
            e.damaged_tick = 0x5A
            q.damaged_tick = 0x5A
            e.bytes[0] = 1
            e.ai[1] = hi(r, 0x1F) + 0x14
    elif a == 5:
        if e.anim_done != 0:
            e.target_anim = 0
            q.target_anim = 0
            e.ai[1] = 0x3C


# ---------------------------------------------------------------------- C255 / F255 (treasure)
ITEMS = 0x800C7DE4          # 8-byte item records: +0 name (char *), +5 pick-up sound


@port(0x8003B67C, ret=True)
def freeze_all(g, e):
    """Every other live (status 2-3) entity not frozen yet is frozen by e (Entity+0x20 =
    e); returns how many."""
    n = 0; a = s32(entity.ent_addr(e)); cnt = g.ent_count
    for i in range(0, cnt + 1):
        t = g.ent[i]
        if t is e: continue
        if ((t.estatus - 2) & M32) < 2 and t.frozen == 0:
            t.frozen = a
            n += 1
    return n


@port(0x8003B6F4, ret=True)
def unfreeze_all(g, e):
    """Entities frozen by e are let go; returns how many."""
    n = 0; a = s32(entity.ent_addr(e)) if e is not None else 0; cnt = g.ent_count
    for i in range(0, cnt + 1):
        t = g.ent[i]
        if t.frozen == a:
            t.frozen = 0
            n += 1
    return n


def _msg_item(g, n, pre, post):
    """MSG = text pre + item name + text post."""
    calls.call(g, 0x800847F4, MSG, calls.call(g, 0x80083FC4, pre))
    calls.call(g, 0x800846E8, MSG, g.mem.u32(ITEMS + n * 8))
    calls.call(g, 0x800846E8, MSG, calls.call(g, 0x80083FC4, post))


def _cd_music(g):
    """The pick-up jingle needs the CD player (0x80029B70 / 0x8009C6C0)."""
    return g.mem.s32(0x80029B70) != 0 or g.mem.s32(0x8009C6C0) != 0


REGULAR_ITEM_SOUND = 52                         # the pick-up sound of herbs, keys, elixirs ...


def _regular(g):
    """Remake option F5 > Mods > Rare Item Jingle = Regular Item Sound (value 3): a rare item
    (pick-up sound 0) is taken like a common one, with sound 52, no jingle and no wait.  Off
    in the original game (and wherever there are no settings, as in the checks)."""
    s = getattr(g, 'settings', None)
    return isinstance(s, dict) and s.get('rare_jingle', 1) == 3


@port(0x8007E964)
def ai_c255(g, e):
    """C255 (an item: global sprite 0x1E + item number): dropped ones bounce (word +0x284
    = z speed, damped), blink out after word +0x278 frames and are picked up when Alundra
    touches them (gain via 0x80034614, message "<name> ..." 0x45, flag word +0x280,
    jingle or sound); from a chest (word +0x274 = 2, +0x280 = the chest) it rises for 64
    frames, then the "got / already have" message and the item (0x800344D4) or the chest
    closes again.  The world stays frozen while the jingle plays."""
    n = s32(e.sprite_index - 0x1E)
    if _w274(e) == 2:
        d = e.delay
        if d != 0:
            e.delay = s32(d - 1)
            return
        st = e.item_state
        if st == 1:
            _c255_wait_music(g, e)
        elif st == 0:
            e.fz = 0
            if calls.call(g, 0x80045F8C) != 0: return
            if _wai(e, 2) != 0:
                _msg_item(g, n, 0x4C, 0x4D)
                if _wai(e, 4) != 0:
                    e.item_state = s32(e.item_state + 1)
                    calls.call(g, 0x8004608C, MSG, 1)
                    calls.call(g, 0x8004600C, 4)
                    return
                e.item_state = s32(e.item_state + 2)
                snd = g.mem.u8(ITEMS + 5 + n * 8)
                if snd == 0 and _regular(g): snd = REGULAR_ITEM_SOUND
                if snd == 0:
                    calls.call(g, 0x800846E8, MSG, calls.call(g, 0x80083FC4, 0x46))
                core.play_sound(g, snd)
            else:
                e.item_state = s32(e.item_state + 2)
                _msg_item(g, n, 0x4E, 0x4F)
            calls.call(g, 0x8004608C, MSG, 1)
        elif st == 2:
            if calls.call(g, 0x80045F8C) != 0: return
            chest = entity.ent_at(g, _wai(e, 0))
            if _wai(e, 2) != 0:
                calls.call(g, 0x800344D4, g.ent[0], n)
                calls.call(g, 0x80033240, chest.contents_flag)
            else:
                chest.target_anim = 0
            unfreeze_all(g, entity.ent_at(g, _wai(e, 0)))
            player.remove_entity(g, e)
        return
    if e.on_ground != 0:
        v = _wai(e, 2)
        if v != 0:
            v = s32(v * 12) >> 4
            _set_wai(e, 2, v)
            if not (g.mem.u16(g.tile_effects_addr + 4) << 8) < v:
                _set_wai(e, 2, 0)
            e.fz = _wai(e, 2)
    d = e.delay
    if ((d + 1) & M32) >= 2:
        d = s32(d - 1)
        e.delay = d
        if d == 0:
            player.remove_entity(g, e)
            return
        if d == 0x78:
            e.damaged_tick = 0x78
    st = e.item_state
    if st == 0:
        if e.fz <= 0:
            e.item_state = 1
    elif st == 1:
        _c255_pick(g, e, n)
    elif st == 2:
        _c255_wait_music(g, e)
    elif st == 3:
        if calls.call(g, 0x80045F8C) != 0: return
        unfreeze_all(g, e)
        player.remove_entity(g, e)


def _c255_wait_music(g, e):
    if calls.call(g, 0x8005C990) != 0: return
    e.item_state = s32(e.item_state + 1)
    calls.call(g, 0x8004600C, 3)
    calls.call(g, 0x8004AC90)


def _c255_pick(g, e, n):
    if calls.call(g, 0x80045F8C) != 0: return
    p = g.ent[0]
    if not (_overlap(e.mpx, p.mpx, p.sizex, e.sizex) and _overlap(e.mpy, p.mpy, p.sizey, e.sizey)
            and _overlap(e.mpz, p.mpz, p.sizez, e.sizez)):
        return
    if calls.call(g, 0x80034614, p, n) != 0 or _w274(e) == 0:
        calls.call(g, 0x800847F4, MSG, g.mem.u32(ITEMS + n * 8))
        calls.call(g, 0x800846E8, MSG, calls.call(g, 0x80083FC4, 0x45))
    else:
        g.mem.w8(MSG, 0)
    calls.call(g, 0x80033240, _wai(e, 0))
    snd = g.mem.u8(ITEMS + 5 + n * 8)
    if snd == 0 and _regular(g): snd = REGULAR_ITEM_SOUND
    if snd == 0:
        if _cd_music(g):
            e.item_state = s32(e.item_state + 1)
            freeze_all(g, e)
            calls.call(g, 0x8004AD18, 0)
            calls.call(g, 0x8005CB94, 0xB)
            if g.mem.u8(MSG) != 0:
                calls.call(g, 0x8004608C, MSG, 1)
            calls.call(g, 0x8004600C, 4)
            return
        calls.call(g, 0x800846E8, MSG, calls.call(g, 0x80083FC4, 0x46))
    else:
        core.play_sound(g, snd)
    if g.mem.u8(MSG) != 0:
        calls.call(g, 0x8004608C, MSG, 0)
    e.item_state = s32(e.item_state + 2)


# ====================================================================== D: hurt programs
def _d_simple(anim, face=True):
    def f(g, e):
        _hurt(g, e)
        e.target_anim = anim
        if face: e.target_dir = _away(g, e)
    return f


@port(0x80080218)
def ai_d1(g, e):
    """D1: hurt, animation 5, face away from Alundra."""
    _d_simple(5)(g, e)


@port(0x8008027C)
def ai_d2(g, e):
    """D2: face away; a sword/whip-class hit (kind 1-3) on sprite 0x16A in anim 0-1 / 0xD
    is blocked (anim 0xC); on sprite 0x16D in anim 0-1 blocked half the time (anim 0xA);
    else hurt, anim 7."""
    k = _atk_kind(g, e)
    e.target_dir = _away(g, e)
    if ((k - 1) & M32) < 2 or k == 3:
        a = e.target_anim & M32
        if e.sprite_index == 0x16A and (a < 2 or a == 0xD):
            e.target_anim = 0xC
            return
        if e.sprite_index == 0x16D and (e.target_anim & M32) < 2:
            if not hi(next_seed(g), 100) < 0x32:
                e.target_anim = 0xA
                return
    _hurt(g, e)
    e.target_anim = 7


@port(0x800803BC)
def ai_d3(g, e):
    """D3: sprites 0x1B5 / 0x1B9 in anim 4-6 are stunned (anim 9, 120 frames); else hurt,
    anim 7; face away."""
    s = e.sprite_index
    a = e.target_anim
    if (s == 0x1B5 or s == 0x1B9) and (((a - 4) & M32) < 2 or a == 6):
        e.target_anim = 9
        e.ai[1] = 0x78
    else:
        _hurt(g, e)
        e.target_anim = 7
    e.target_dir = _away(g, e)


@port(0x80080470)
def ai_d5(g, e):
    """D5: face away; sprite 0x1A9 in anim 0-1 blocks a kind 1-3 hit 40% of the time
    (anim 0xB); else hurt, anim 5."""
    k = _atk_kind(g, e)
    e.target_dir = _away(g, e)
    if (((k - 1) & M32) < 2 or k == 3) and e.sprite_index == 0x1A9 and (e.target_anim & M32) < 2:
        if not hi(next_seed(g), 100) < 0x3C:
            e.target_anim = 0xB
            return
    _hurt(g, e)
    e.target_anim = 5


@port(0x80080578)
def ai_d6(g, e):
    """D6: hurt, anim 6, face away."""
    _d_simple(6)(g, e)


@port(0x800805DC)
def ai_d7(g, e):
    """D7: hurt, anim 7, face away."""
    _d_simple(7)(g, e)


@port(0x80080640)
def ai_d8(g, e):
    """D8: hurt, anim 4, face away."""
    _d_simple(4)(g, e)


@port(0x800806A4)
def ai_d9(g, e):
    """D9: hurt, anim 2, face away."""
    _d_simple(2)(g, e)


@port(0x80080708)
def ai_d10(g, e):
    """D10: hurt, anim 6, face away; sprites 0x1C4-0x1C5 cry (sound 0x41)."""
    _d_simple(6)(g, e)
    if ((e.sprite_index - 0x1C4) & M32) < 2:
        core.play_sound(g, 0x41)


@port(0x80080788)
def ai_d11(g, e):
    """D11: hurt, anim 4, face away."""
    _d_simple(4)(g, e)


@port(0x800807EC)
def ai_d12(g, e):
    """D12: face away; a kind 1-3 hit is blocked 30% of the time (anim 6) by sprite 0x152
    in anim 0-1 or sprite 0x155 in anim 0-1 / 7; else hurt, anim 4."""
    k = _atk_kind(g, e)
    e.target_dir = _away(g, e)
    if ((k - 1) & M32) < 2 or k == 3:
        if not hi(next_seed(g), 100) < 0x46:
            s = e.sprite_index
            if s == 0x152 and (e.target_anim & M32) < 2:
                e.target_anim = 6
                return
            if s == 0x155:
                a = e.target_anim
                if (a & M32) < 2 or a == 7:
                    e.target_anim = 6
                    return
    _hurt(g, e)
    e.target_anim = 4


@port(0x80080924)
def ai_d13(g, e):
    """D13: hurt, anim 3, face away."""
    _d_simple(3)(g, e)


@port(0x80080988)
def ai_d14(g, e):
    """D14: hurt, anim 5."""
    _d_simple(5, False)(g, e)


@port(0x800809C4)
def ai_d15(g, e):
    """D15: no damage; anim 2 -> 9, anim 1 -> 0xA, else 3."""
    a = e.target_anim
    e.target_anim = 9 if a == 2 else (0xA if a == 1 else 3)


@port(0x800809F0)
def ai_d16(g, e):
    """D16: guarding (bytes[1]) -> anim 0x10; else hurt, anim 8, face away."""
    e.bytes[2] = 0
    if e.bytes[1] == 0:
        _d_simple(8)(g, e)
        return
    e.target_anim = 0x10


@port(0x80080A74)
def ai_d17(g, e):
    """D17: hurt, anim 8, face away."""
    _d_simple(8)(g, e)


@port(0x80080AD8)
def ai_d18(g, e):
    """D18: hurt (the parent's counter Entity+0x278 drops when it survives), anim 2, face away."""
    if player.take_hit(g, e) != 0:
        t = _par(g, e)
        e.bytes[3] = 1
        t.delay = s32(t.delay - 1)
    e.target_anim = 2
    e.target_dir = _away(g, e)


@port(0x80080B50)
def ai_d19(g, e):
    """D19: hurt, anim 8, face away."""
    _d_simple(8)(g, e)


@port(0x80080BB4)
def ai_d20(g, e):
    """D20 (two-part monster: the head keeps its other half in word Entity+0x284, the
    other half has it as parent): both face away (mirrored), the head takes the hit and
    shares its life; anims 9 / 6 by the head's bytes[2]."""
    t = entity.ent_at(g, _wai(e, 2))
    if t is not None:
        a, b = e, t
        d = _away(g, a)
        a.target_dir = d
        b.target_dir = (0x20 - d) & 0x1F
        if player.take_hit(g, a) != 0: a.bytes[3] = 1
        b.hp = a.hp
    else:
        b = e; a = _par(g, e)
        d = _away(g, b)
        b.target_dir = d
        a.target_dir = (0x20 - d) & 0x1F
        if player.take_hit(g, b) != 0: a.bytes[3] = 1
        a.hp = b.hp
    if a.bytes[2] == 0:
        a.target_anim = 9; b.target_anim = 6
    else:
        a.target_anim = 6; b.target_anim = 9


C47_PTR = 0x800C6E58        # the C47 entry of the C program table


@port(0x80080CD4, calls=(0x800762E8,))
def ai_d21(g, e):
    """D21 (C47 boss in slot 2 and its 13 parts): while the boss (ent[2]) is in phase 0xF
    and not in states 5 / 7 / 8, a part is hurt (anim 4) and runs 0x80075F18; the boss is
    hurt only when 6 of slots 2-15 have bytes[3] set.  The boss then runs its C program."""
    b = g.ent[2]
    b1 = b.bytes[1]
    if b1 == 5 or ((b1 - 7) & M32) < 2 or b.bytes[0] != 0xF:
        if e is not b: return
    else:
        if e is not b:
            _hurt(g, e)
            e.target_anim = 4
            calls.call(g, 0x80075F18, e)
            return
        n = 0
        for i in range(2, 16):
            if g.ent[i].bytes[3] != 0: n += 1
        if n == 6:
            if player.take_hit(g, e) != 0:
                e.bytes[3] = 1; e.delay = 0; e.bytes[1] = 0x10
            e.target_anim = 4
    calls.call(g, g.mem.u32(C47_PTR), e)        # jalr (the game also passes its a1 along)


@port(0x80080E00)
def ai_d22(g, e):
    """D22: hurt (not on map 0x7B), anim 6, bytes[1] and bytes[0] count the hits."""
    if g.cur_map != 0x7B and player.take_hit(g, e) != 0:
        e.bytes[3] = 1
    e.target_anim = 6
    e.bytes[1] += 1
    e.bytes[0] += 1


@port(0x80080E68)
def ai_d23(g, e):
    """D23: hurt (the parent's bytes[2] drops when it survives), anim 5, face away."""
    if player.take_hit(g, e) != 0:
        t = _par(g, e)
        e.bytes[3] = 1
        t.bytes[2] -= 1
    e.target_anim = 5
    e.target_dir = _away(g, e)


@port(0x80080EE0)
def ai_d24(g, e):
    """D24: hurt, anim 7, face away."""
    _d_simple(7)(g, e)


@port(0x80080F44)
def ai_d25(g, e):
    """D25: ignores hits."""
    return


@port(0x80080F4C)
def ai_d26(g, e):
    """D26: only attack kinds 7 / 9 hurt it (anim 8)."""
    k = _atk_kind(g, e)
    if k == 7 or k == 9:
        _hurt(g, e)
        e.target_anim = 8


@port(0x80080FBC)
def ai_d27(g, e):
    """D27: hurt (anim 6) unless in anim 4."""
    if e.target_anim != 4:
        _hurt(g, e)
        e.target_anim = 6


@port(0x8008100C)
def ai_d28(g, e):
    """D28: hurt, anim 7."""
    _d_simple(7, False)(g, e)


@port(0x80081048)
def ai_d29(g, e):
    """D29: anim 0xD."""
    e.target_anim = 0xD


@port(0x80081054)
def ai_d30(g, e):
    """D30: attack kinds 4 / 6 / 0xA put it in status 3."""
    k = _atk_kind(g, e)
    if k == 4 or k == 6 or k == 0xA:
        e.estatus = 3


@port(0x8008109C)
def ai_d31(g, e):
    """D31: attack kind 2: next animation, flag 0x40."""
    if _atk_kind(g, e) == 2:
        e.target_anim = s32(e.target_anim + 1)
        e.flags |= 0x40


@port(0x800810E0)
def ai_d32(g, e):
    """D32: attack kind 4: next animation, flag 0x40."""
    if _atk_kind(g, e) == 4:
        e.target_anim = s32(e.target_anim + 1)
        e.flags |= 0x40


@port(0x80081124)
def ai_d33(g, e):
    """D33: attack kind 2: anim 2, flag 0x40."""
    k = _atk_kind(g, e)
    if k == 2:
        e.target_anim = k
        e.flags |= 0x40


@port(0x80081164)
def ai_d34(g, e):
    """D34: attack kind 6: anim 1, flags 0x46 on, 0x80 off."""
    if _atk_kind(g, e) == 6:
        e.target_anim = 1
        e.flags = (e.flags | 0x46) & ~0x80


@port(0x800811A8)
def ai_d35(g, e):
    """D35: armoured (bytes[0]): sound 0x120, anim 4; else hurt (sound 0x123 / 0x11E when
    it dies), anim 6, face away."""
    if e.bytes[0] == 0:
        if player.take_hit(g, e) != 0:
            core.play_sound(g, 0x123)
            e.bytes[3] = 1
        else:
            core.play_sound(g, 0x11E)
        e.target_anim = 6
        e.target_dir = _away(g, e)
        return
    core.play_sound(g, 0x120)
    e.target_anim = 4


@port(0x8008124C)
def ai_d36(g, e):
    """D36: anim 1, flag 0x40."""
    e.target_anim = 1
    e.flags |= 0x40


@port(0x80081264)
def ai_d37(g, e):
    """D37: hurt, anim 1."""
    _d_simple(1, False)(g, e)


@port(0x800812A0)
def ai_d38(g, e):
    """D38: hurt, anim 2."""
    _d_simple(2, False)(g, e)


@port(0x800812DC)
def ai_d39(g, e):
    """D39: hurt, anim 3; hit by sprite 0x1EF it is marked hit (bytes[3]) even if it died."""
    t = e.touching
    if player.take_hit(g, e) != 0 or (t.sprite_index if t is not None else g.mem.s32(NULL + 0x68)) == 0x1EF:
        e.bytes[3] = 1
    e.target_anim = 3


@port(0x8008133C)
def ai_d40(g, e):
    """D40: sprite 0x1D7 is hurt (anim 2, ai[4] = 1); others (anim 2) add 0x20 (max 0x60)
    to the parent's bytes[0] and set its bytes[1] to 0x10."""
    if e.sprite_index == 0x1D7:
        _hurt(g, e)
        e.target_anim = 2
        e.ai[4] = 1
        return
    t = _par(g, e)
    e.target_anim = 2
    v = t.bytes[0]
    if v < 0x60:
        t.bytes[0] = v + 0x20
        t.bytes[1] = 0x10
        if t.bytes[0] >= 0x61: t.bytes[0] = 0x60


@port(0x800813D4)
def ai_d41(g, e):
    """D41: hurt, anim 3."""
    _d_simple(3, False)(g, e)


@port(0x80081410)
def ai_d42(g, e):
    """D42: hurt (anim 1) while it has life."""
    if e.hp != 0:
        _hurt(g, e)
        e.target_anim = 1


@port(0x80081460)
def ai_d43(g, e):
    """D43: stop (z force, push), hurt, anim 6."""
    e.fz = 0; e.pafy = 0; e.pafx = 0
    _hurt(g, e)
    e.target_anim = 6


@port(0x800814A8)
def ai_d44(g, e):
    """D44: counted in the parent (sprite 0x14F: bytes[2] and sound 2, else bytes[0] and
    sound 3) and destroyed (effect 8)."""
    t = _par(g, e)
    if e.sprite_index == 0x14F:
        n = 2; t.bytes[2] += 1
    else:
        n = 3; t.bytes[0] += 1
    core.play_sound(g, n)
    entity.destroy_entity(g, e, 8)


@port(0x80081518)
def ai_d45(g, e):
    """D45: attack kind 2: anim 4, bytes[2] counts it."""
    if _atk_kind(g, e) == 2:
        e.target_anim = 4
        e.bytes[2] += 1


@port(0x80081554)
def ai_d46(g, e):
    """D46: hurt, anim 2 (sprite 0x1CB: 3), face away."""
    _hurt(g, e)
    e.target_anim = 3 if e.sprite_index == 0x1CB else 2
    e.target_dir = _away(g, e)


# ====================================================================== E: death programs
@port(0x800815C8)
def ai_e0(g, e):
    """E0, E1: destroyed at once (its sprite's break effect)."""
    entity.destroy_entity(g, e, -1)


def _die_then_destroy(anim):
    def f(g, e):
        if (e.target_anim == anim and e.anim_done == 1) or e.vram_and & 4:
            entity.destroy_entity(g, e, -1)
            return
        _die_anim(e, anim)
    return f


@port(0x800815E8)
def ai_e2(g, e):
    """E2: death animation 2, then destroyed (at once on a floor with bit 2 of +0x184)."""
    _die_then_destroy(2)(g, e)


@port(0x80081658)
def ai_e3(g, e):
    """E3: death animation 1, then destroyed."""
    a = e.target_anim
    if a == 1 and e.anim_done == a:
        entity.destroy_entity(g, e, -1)
        return
    _die_anim(e, 1)


@port(0x800816BC)
def ai_e4(g, e):
    """E4: death animation 4, then destroyed."""
    if e.target_anim == 4 and e.anim_done == 1:
        entity.destroy_entity(g, e, -1)
        return
    _die_anim(e, 4)


@port(0x80081720)
def ai_e5(g, e):
    """E5: death animation 1 with effect 8 at its feet, then destroyed."""
    if e.target_anim == 1:
        if e.anim_done == 1:
            entity.destroy_entity(g, e, -1)
        return
    _die_anim(e, 1)
    core.spawn_effect(g, 0, 8, 0, e.px, e.py, e.pz)


@port(0x800817A8)
def ai_e6(g, e):
    """E6: destroyed at once."""
    entity.destroy_entity(g, e, -1)


@port(0x800817C8)
def ai_e7(g, e):
    """E7: destroyed at once."""
    entity.destroy_entity(g, e, -1)


@port(0x800817E8)
def ai_e8(g, e):
    """E8: destroyed at once."""
    entity.destroy_entity(g, e, -1)


@port(0x80081808)
def ai_e9(g, e):
    """E9 (burning things): five flying sparks (effect 0x12, sprites 0xB-0xC 0x11), then
    death animation 1 throwing a spark every 8 frames; on water / lava floors (slope 1 or
    4) destroyed with effect 6."""
    if e.target_anim == 1:
        s = e.slope_now
        if s == 1 or s == 4:
            entity.destroy_entity(g, e, 6)
        if e.anim_done == 1:
            entity.destroy_entity(g, e, -1)
            return
        if e.frame_counter & 7: return
        k = 1 if ((e.sprite_index - 0xB) & M32) < 2 else 0
        f = core.spawn_effect(g, 0, 0x11 if k else 0x12, 0, e.px, e.py, s32(e.pz + (k << 19)))
        if f is None: return
        a = next_seed(g); b = next_seed(g)
        f.vz = 0x20000
        f.vx = s32(hi(a, 0x30001) + 0xFFFE8000)
        f.vy = s32(hi(b, 0x20001) + 0xFFFF0000)
        return
    n = 0x11 if ((e.sprite_index - 0xB) & M32) < 2 else 0x12
    s = e.slope_now
    if s == 1 or s == 4:
        entity.destroy_entity(g, e, 6)
        return
    for _ in range(5):
        f = core.spawn_effect(g, 0, n, 0, e.px, e.py, e.pz)
        if f is not None:
            a = next_seed(g); b = next_seed(g)
            f.vx = s32(hi(a, 0x60001) + 0xFFFD0000)
            f.vy = s32(hi(b, 0x40001) + 0xFFFE0000)
    _die_anim(e, 1)


@port(0x80081AFC)
def ai_e10(g, e):
    """E10: destroyed at once."""
    entity.destroy_entity(g, e, -1)


@port(0x8003AF90)
def destroy_tree(g, e, effect):
    """DestroyEntity of e and (first, recursively) of every entity whose parent it is,
    while e itself is alive (status 1-3)."""
    i = 0
    while g.ent_count >= i:
        t = g.ent[i]
        s = e.estatus
        if (((s - 1) & M32) < 2 or s == 3) and t.parent is e:
            destroy_tree(g, t, effect)
        i += 1
    calls.call(g, 0x800332A8, e)                  # what it carries drops (SpawnEntityContents)
    e.estatus = 4
    e.action = -1
    if e.shadow is not None:
        e.shadow.state = 0
        e.shadow = None
    if effect == -1:
        effect = g.mem.u8(e.header_addr + 0x1E)
    if effect != 0:
        core.spawn_effect_on(g, 0, effect, 0, e, 1, 0, 0, 0)
    if e.holder is not None:
        e.holder.carried = None


@port(0x80081B1C)
def ai_e11(g, e):
    """E11: destroyed together with all its children."""
    destroy_tree(g, e, -1)


@port(0x80081B3C)
def ai_e12(g, e):
    """E12: death animation 1 breaking blocks around it, then destroyed."""
    if (e.target_anim == 1 and e.anim_done == 1) or e.vram_and & 4:
        entity.destroy_entity(g, e, -1)
        return
    player.break_blocks(g, e)
    _die_anim(e, 1)


@port(0x80081BCC)
def ai_e13(g, e):
    """E13: death animation 1 (sets the word at 0x801B6C4C to 2), then destroyed."""
    if e.target_anim == 1:
        if e.anim_done == 1:
            entity.destroy_entity(g, e, -1)
        return
    g.mem.w32(0x801B6C4C, 2)
    _die_anim(e, 1)


@port(0x80081C34)
def ai_e14(g, e):
    """E14: sound 0x2D, destroyed."""
    core.play_sound(g, 0x2D)
    entity.destroy_entity(g, e, -1)


@port(0x80081C6C)
def ai_e15(g, e):
    """E15: sound 0x2E, destroyed."""
    core.play_sound(g, 0x2E)
    entity.destroy_entity(g, e, -1)


@port(0x80081CA4)
def ai_e16(g, e):
    """E16: sound 0x2F, destroyed."""
    core.play_sound(g, 0x2F)
    entity.destroy_entity(g, e, -1)


def _overlap(a, b, size_b, size_a):
    """The game's box test on one axis: a - b in [0, size_b] or b - a in [1, size_a]."""
    d = s32(a - b)
    if d >= 0: return d < s32(size_b + 1)
    return s32(b - a) < s32(size_a + 1)


@port(0x80081CDC)
def ai_e17(g, e):
    """E17 (bombs and the like): when it hit something (Entity+0x220) and its attack box
    still overlaps a solid entity (class bits from flags 2 / 4 / 0x1000) other than sprite
    0x1AD, it is destroyed; if nothing is there it goes back to status 2.  Then anim 1,
    turned around."""
    if e.target_anim == 1:
        if e.anim_done == 1:
            entity.destroy_entity(g, e, -1)
        return
    if e.hits != 0:
        fl = e.flags
        ax, ay, az = e.atk_x, e.atk_y, e.atk_z
        mask = (fl << 2) & 8
        if fl & 4: mask |= 1
        if fl & 0x1000: mask |= 0x800
        free = 1
        if mask != 0:
            i = 0
            while g.ent_count >= i:
                t = g.ent[i]
                i += 1
                if t is e or t.anim_flags & 0x40 or t.damaged_tick != 0 or not (t.flags & mask): continue
                if not _overlap(ax, t.mpx, t.sizex, e.atk_w): continue
                if not _overlap(ay, t.mpy, t.sizey, e.atk_h): continue
                if not _overlap(az, t.mpz, t.sizez, e.atk_d): continue
                if t.sprite_index != 0x1AD:
                    free = 0
                    break
            if free:
                e.estatus = 2
                return
        entity.destroy_entity(g, e, -1)
    e.target_anim = 1
    e.target_dir = (e.target_dir + 0x10) & 0x1F
    e.flags = (e.flags | 0x140) & ~0x30


@port(0x80081F18)
def ai_e18(g, e):
    """E18: sound 0xE1, destroyed."""
    core.play_sound(g, 0xE1)
    entity.destroy_entity(g, e, -1)


@port(0x80081F50)
def ai_e19(g, e):
    """E19: sound 0xE6, destroyed."""
    core.play_sound(g, 0xE6)
    entity.destroy_entity(g, e, -1)


@port(0x80081F88)
def ai_e20(g, e):
    """E20: death animation 2; if it bumped sprite 0x187 meanwhile (bytes[0]) nothing more,
    else at the end it leaves global sprite 0xC (anim 3, flag 2 on, 0x10 off) before it is
    destroyed."""
    if e.target_anim == 2 and e.anim_done == 1:
        if e.bytes[0] == 0:
            t = entity.spawn_warp_entity(g, e, 0, 0xC, e.px, e.py, e.pz, e.target_dir)
            if t is None:       # the game does not test the spawn: the stores go to RAM 0x0
                m = g.mem
                for o in range(0x84, 0x6C, -4): m.w32(NULL + o, 0)
                m.w32(NULL + 0x88, 3)
                m.w32(NULL + 0x6C, (m.s32(NULL + 0x6C) & ~0x10) | 2)
            else:
                t.bi_f = t.bi_e = t.bi_d = t.bi_c = t.bi_b = t.bi_a = 0
                t.target_anim = 3
                t.flags = (t.flags & ~0x10) | 2
        entity.destroy_entity(g, e, -1)
        return
    _die_anim(e, 2)
    c = e.x_collision
    if c is not None and c.sprite_index == 0x187:
        e.bytes[0] = 1


@port(0x80082090)
def ai_e21(g, e):
    """E21: standing on sprite 0x199 in anim 0 starts it (anim 1) and removes itself;
    else death animation 1, then destroyed."""
    r = e.riding
    if r is not None and r.sprite_index == 0x199 and r.target_anim == 0:
        r.target_anim = 1
        player.remove_entity(g, e)
    a = e.target_anim
    if a == 1 and e.anim_done == a:
        entity.destroy_entity(g, e, -1)
        return
    _die_anim(e, 1)


@port(0x8008213C)
def ai_e22(g, e):
    """E22: destroyed with effect 0xD (8 when bytes[3] is set)."""
    entity.destroy_entity(g, e, 8 if e.bytes[3] != 0 else 0xD)


@port(0x80082170)
def ai_e23(g, e):
    """E23: sprites 0x1F0 (two, the second 1 square higher) and 0x1F6-0x1F7 leave effect
    0xB; removed."""
    x, y, z = e.px, e.py, e.pz
    s = e.sprite_index
    if s == 0x1F0:
        core.spawn_effect(g, 0, 0xB, 0, x, y, z)
        core.spawn_effect(g, 0, 0xB, 0, x, y, s32(z + 0x100000))
    elif ((s - 0x1F6) & M32) < 2:
        core.spawn_effect(g, 0, 0xB, 0, x, y, z)
    player.remove_entity(g, e)


@port(0x80082238)
def ai_e24(g, e):
    """E24: four map sprites 0xE3 thrown diagonally (directions 4, 12, 20, 28) in its
    animation; if the parent has not been hit (bytes[3]) it sets the five words at
    0x801F94D0 and the parent's Entity+0x27C to 0x1E; death animation 1, then destroyed."""
    if e.target_anim == 1:
        if e.anim_done == 1:
            entity.destroy_entity(g, e, -1)
        return
    d = 4
    for _ in range(4):
        t = entity.spawn_warp_entity(g, e, 1, 0xE3, e.px, e.py, s32(e.pz + 0x20000), d)
        if t is not None:
            t.target_anim = e.target_anim
        d += 8
    p = _par(g, e)
    if p.bytes[3] == 0:
        g.mem.w32(0x801F94D0, 1); g.mem.w32(0x801F94DC, 1); g.mem.w32(0x801F94E0, 1)
        g.mem.w32(0x801F94D4, 2); g.mem.w32(0x801F94D8, 2)
        p.item_state = 0x1E
    e.target_anim = 1
    e.flags = (e.flags | 0x40) & ~0x30


@port(0x80082370)
def ai_e25(g, e):
    """E25: removed."""
    player.remove_entity(g, e)


@port(0x80082390)
def ai_e26(g, e):
    """E26: death animation 1, then destroyed (the parent's bytes[2] counts it)."""
    a = e.target_anim
    t = _par(g, e)
    if a == 1 and e.anim_done == a:
        t.bytes[2] -= 1
        entity.destroy_entity(g, e, -1)
        return
    _die_anim(e, 1)


@port(0x80082408)
def ai_e27(g, e):
    """E27: destroyed at once."""
    entity.destroy_entity(g, e, -1)


@port(0x80082428)
def ai_e28(g, e):
    """E28: eight effects 0x13 (sub 2) in a ring of random radius around it, destroyed."""
    for k in range(8):
        r = hi(next_seed(g), 0x1801) + 0x320
        y = s32(e.py + s32(g.mem.s16(DY + k * 8) * r))
        x = s32(e.px + s32(g.mem.s16(DX + k * 8) * r))
        core.spawn_effect(g, 0, 0x13, 2, x, y, e.pz)
    entity.destroy_entity(g, e, -1)


# ====================================================================== F
@port(0x80082528)
def ai_f1(g, e):
    """F1: talked to: word Entity+0x274 = 1, Alundra stands (anim 0), mode flag 4."""
    _set_w274(e, 1)
    g.ent[0].target_anim = 0
    g.mode_flags |= 4


@port(0x80082554)
def ai_f255(g, e):
    """F255 (treasure chest, examined with Square): when nothing else is going on, an
    unopened chest (contents_item, anim 0) opens (anim 2) and lets its item rise (C255,
    world frozen); else the message "empty" (0x48) / "no room" (0x49)."""
    if g.mode_flags != 0 or g.warp_request != 0 or g.ent[0].carried is not None: return
    if calls.call(g, 0x80045F8C) != 0: return
    n = e.contents_item
    m = 0x48
    if n != 0 and e.target_anim == 0:
        e.target_anim = 2
        t = entity.spawn_warp_entity(g, e, 0, s32(n + 0x1E), e.px, e.py, s32(e.pz + 0x100000), 0)
        m = 0x49
        if t is not None:
            freeze_all(g, e)
            t.fz = 0x8000
            t.delay = 0x40
            t.frozen = 0
            _set_w274(t, 2)
            t.item_state = 0
            _set_wai(t, 0, entity.ent_addr(e))
            t.flags &= ~0x180
            v = calls.call(g, 0x80034458, n)
            _set_wai(t, 2, v)
            if v != 0 and g.mem.u8((ITEMS + 5 + n * 8) & M32) == 0 and _cd_music(g) and not _regular(g):
                _set_wai(t, 4, 1)
                calls.call(g, 0x8004AD18, 0)
                return
            _set_wai(t, 4, 0)
            return
    calls.call(g, 0x8004608C, calls.call(g, 0x80083FC4, m), 0)
