"""Alundra's controls: MovePlayer (0x80032174) and the routines it calls, ported from the
US ALUN_CD.EXE decompilation (research/us_decomp).  g is the game state: g.ent[0] is
Alundra, globals are attributes (engine/layout.py), map data through g.cell8 / g.portals."""
from .registry import port
from . import core, menu, items, entity
from . import rodata as R
from .core import s32, rnd, next_seed

M32 = 0xFFFFFFFF

# pad bits (the game's byte-swapped layout)
TRIANGLE, CIRCLE, CROSS, SQUARE = 0x10, 0x20, 0x40, 0x80

PAD_DIR = 0x80022C6C        # s32[16]: direction 0-31 for (held >> 12), -1 none
PAD_DIR4 = 0x80022CAC       # s32[16]: the same, cardinal directions only (sprint)
SPRINT_TURN = 0x80022CEC    # s32[4][3]: directions that keep a sprint going, by facing quadrant
QUAD_DIR = 0x80023644       # s32[4]: quadrant -> direction (0, 8, 16, 24)
WEAPON_CLASS = 0x80028BB8   # u8[]: weapon kind -> class (record of 13 bytes at 0x80028C1D)
ANIM_FLAGS = 0x80028CB8     # u8[2] per animation: [0] can charge, [1] attack spawns its record


def tile_of_x(x_px):
    """The game's x -> column table (0x80137990, x / 24 for 0..1247)."""
    if x_px < 0: return 0
    if x_px >= 1248: return 51
    return x_px // 24


# ---------------------------------------------------------------- doors and exits
@port(0x80031C28, ret='ptr')
def find_portal(g):
    """The map's portal record (64 at map info + 0x42C) whose rectangle holds Alundra's square."""
    p = g.ent[0]; tx, ty = p.tile_x, p.tile_y
    for rec in g.portals:
        if tx < rec.x1 or rec.x2 < tx or ty < rec.y1 or rec.y2 < ty: continue
        return rec
    return None


@port(0x80031898)
def use_portal(g, rec, anim, direction):
    """Ask for the map change (or, effect 3 on the same map, move him there at once).  The
    arrival keeps his place inside the door: x / y relative to the record's rectangle."""
    if g.warp_busy != 0: return
    p = g.ent[0]
    eff = (rec.flags & 0x70) >> 4
    g.warp_effect = eff
    dest = g.portal_map(rec)
    g.warp_map = dest
    vx = s32((rec.x * 24 + (p.px >> 16) - rec.x1 * 24) << 16)
    vy = s32((rec.y * 16 + s16(p.py >> 16) - rec.y1 * 16) << 16)
    y = ((((vy >> 20) * 16) + 8) << 16)
    x = ((tile_of_x(vx >> 16) * 24 + 12) << 16)
    g.warp_sound = R.s32(0x80028D70 + (rec.flags & 0xF) * 4)
    z = rec.z << 20
    if eff == 3:
        if dest == g.cur_map:
            c = p.carried
            if c is not None:
                c.px = s32(c.px + x - p.px); c.py = s32(c.py + y - p.py); c.pz = s32(c.pz + z - p.pz)
            p.px, p.py, p.pz = s32(x), s32(y), s32(z)
            return
        g.warp_effect = 0
    g.warp_request = 1; g.warp_anim = anim; g.warp_dir = direction
    g.warp_x, g.warp_y, g.warp_z = s32(x), s32(y), s32(z)


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


@port(0x8002F534)
def check_portals(g):
    """Warp squares (tile attribute 4) take him at once; door squares (0x8000) when he
    pushes toward the door's side while facing it.  (The debug-menu display path only
    prints.)"""
    p = g.ent[0]
    a = p.vram_and
    if not (g.debug_mode >= 0 or not (g.debug_flags & 4) or (g.debug_flags & 0x08000004) == 0x08000004):
        g.portal_debug_count = s32(g.portal_debug_count + 1)
        return
    if a & 4:
        rec = find_portal(g)
        if rec is not None:
            use_portal(g, rec, 0x36, R.s32(QUAD_DIR + ((rec.flags & 0x3000) >> 10)))
    elif a & 0x8000 and g.mode_flags == 0:
        rec = find_portal(g)
        if rec is not None:
            q = rec.flags >> 14
            if g.pad_held & R.u16(0x80022778 + q * 2) and p.anim_quadrant == q:
                use_portal(g, rec, 0x36, R.s32(QUAD_DIR + ((rec.flags & 0x3000) >> 10)))


# ---------------------------------------------------------------- being hit
@port(0x8002EBA0, ret=True)
def dir_from_delta(dx, dy):
    """Direction 0-31 (0 down, 8 left, 16 up, 24 right) of the vector (dx, dy)."""
    k = 2 if dy < 1 else 0
    if dx < 0: k += 1
    ax = abs(dx) & M32; ay = abs(dy) & M32
    m = ax if ax >= ay else ay
    sh = 0; t = 0x80022688
    while R.u32(t) < m:
        t += 4; sh += 1
    v = R.s16(0x80022488 + (((ay >> sh) * 16) + (ax >> sh)) * 2)
    if k == 0: v += 0x18
    elif k == 1: v = 8 - v
    elif k == 2: v = 0x18 - v
    else: v += 8
    return v & 0x1F


@port(0x8003ACAC, ret=True, replay=True)
def take_hit(g, e):
    """e.hp = 0x80045598(the touching attack's record +0x1C8, e's responses: Alundra's
    0x801E70B8 or its balance record +0x1C4, e.hp); 1 when that left it at 0 (it dies).
    The remake's combat.py works it out (g.take_hit); the checks replay the original's."""
    return g.take_hit(e)


@port(0x8003207C, ret=True)
def hit_check(g):
    """Direction to face when hurt this frame (-1 not hurt): touched by an attack, or
    standing on a harmful floor (tile attribute bits 7-8) without the boots against it."""
    p = g.ent[0]
    t = p.touching
    if t is not None:
        take_hit(g, p)
        return dir_from_delta(s32(p.px - t.px), s32(p.py - t.py))
    if p.damaged_tick != 0: return -1
    if g.floor_damage_lock >= 3: return -1
    k = (p.vram_or & 0x180) >> 7
    if k == 0: return -1
    dmg = R.s16(0x80028B30 + k * 2)
    p.hp = p.hp - dmg if dmg < p.hp else 0
    return (p.target_dir + 0x10) & 0x1F


# ---------------------------------------------------------------- talking, lifting
@port(0x8002EC98, ret=True)
def find_talk(g):
    """Someone with a talk program (F) in front of him: 1 talk at once, 2 when it needs
    Square (flag 0x8000, e.g. examine), 0 none.  The last one bumped stays chosen while
    nothing moves."""
    p = g.ent[0]
    t = p.x_collision
    if t is not None:
        if t.flags & 0x8000:
            g.talk_lock = t; g.talk_serial = t.serial
            g.talk_ex, g.talk_ey, g.talk_ez = t.px, t.py, t.pz
            g.talk_px, g.talk_py, g.talk_pz = p.px, p.py, p.pz
            g.talk_dir = p.target_dir
        else:
            g.talk_lock = None
    else:
        t0 = g.talk_lock
        if t0 is not None:
            if (t0.serial == g.talk_serial and t0.px == g.talk_ex and t0.py == g.talk_ey and t0.pz == g.talk_ez
                    and p.px == g.talk_px and p.py == g.talk_py and p.pz == g.talk_pz and p.target_dir == g.talk_dir):
                t = t0
            else:
                g.talk_lock = None
    if t is not None and (t.prog_f != 0 or t.bi_f != 0):
        if t.flags & 0x8000:
            if g.pad_pressed & SQUARE:
                g.talk_target = t; return 2
            return 0
        g.talk_target = t
        return 1
    return 0


@port(0x8002F19C, ret=True)
def lift(g, e):
    """Pick e up if it can be lifted (flags bits 9-10: 1 always, 2-3 with the Lifting
    Gloves (item 0x3B))."""
    k = (e.flags & 0x600) >> 9
    if k == 0: return 0
    if k != 1 and not (k < 4 and menu.has_item(g, 0x3B) != 0): return 0
    p = g.ent[0]
    p.carried = e; e.holder = p
    if e.riding is p: p.target_anim = 0x0C if p.on_ground else 0x30
    else: p.target_anim = 0x05 if p.on_ground else 0x0B
    p.carry_dx = s32(e.px - p.px); p.carry_dy = s32(e.py - p.py); p.carry_dz = s32(e.pz - p.pz)
    return 1


@port(0x8002F2C0, ret=True)
def holding_or_lift(g):
    """1 when he holds something (keeps the holding animation) or Square lifts what he
    bumped or what stands on him."""
    p = g.ent[0]
    if p.carried is not None:
        p.target_anim = 0x0C if p.on_ground else 0x30
        return 1
    if p.x_collision is not None and g.pad_pressed & SQUARE:
        return lift(g, p.x_collision)
    for i in range(0, g.ent_count + 1):
        e = g.ent[i]
        if e is None: continue
        if not (2 <= e.estatus <= 3) or e.frozen != 0 or e.riding is not p: continue
        if lift(g, e): return 1
    return 0


@port(0x8003B0C8)
def remove_entity(g, e):
    """Status 4 without contents or break effect; its shadow and its holder let go.  (An int
    is a record at that address, as the game writes through any pointer it holds.)"""
    if isinstance(e, int):
        from . import ai_g5
        e = ai_g5._At(g, e)
    e.estatus = 4; e.action = -1
    sh = getattr(e, 'shadow', None)
    if sh is not None and sh != 0:
        if hasattr(sh, 'state'): sh.state = 0
        elif isinstance(sh, int): g.mem.w32(sh + 0x68, 0)
        e.shadow = None
    if e.holder is not None: e.holder.carried = None


@port(0x8002FCC4)
def carry(g, mode):
    """The object over his head: 0 rises 1 px a frame to 32 px up and centres; 1 (items
    whose balance record byte 0xE is set) is pulled into him and vanishes; 2 drops it."""
    p = g.ent[0]; c = p.carried
    if c is None:
        g.carry_timer = 0; return
    if g.balance_byte(c, 0xE) == 0 and mode == 1: mode = 0
    if mode == 0:
        dx = s32(c.px - p.px); dy = s32(c.py - p.py); dz = s32(c.pz - p.pz)
        ax, ay = abs(dx), abs(dy)
        az = dz - 0x200000 if dz - 0x200000 >= 0 else 0x200000 - dz
        far = (ay < az) if ax < ay else (ax < az)
        if not far:
            dx = core.approach(dx, 0, 0x10000); dy = core.approach(dy, 0, 0x10000)
        dz = core.approach(dz, 0x200000, 0x10000)
        p.carry_dx, p.carry_dy, p.carry_dz = dx, dy, dz
        g.carry_timer = 0
    elif mode == 1:
        if g.carry_timer < 5:
            g.carry_timer += 1; return
        dx = s32(c.px - p.px); dy = s32(c.py - p.py); dz = s32(c.pz - p.pz)
        if abs(dx) <= 0x1FFFF and abs(dy) <= 0x1FFFF and abs(dz) <= 0x1FFFF:
            remove_entity(g, c); return
        p.carry_dx = core.approach(dx, 0, 0x20000)
        p.carry_dy = core.approach(dy, 0, 0x20000)
        p.carry_dz = core.approach(dz, 0, 0x20000)
    else:
        c.flags2 = -1; c.target_dir = p.target_dir
        c.px, c.py, c.pz = p.px, p.py, s32(p.pz + 0x200000)
        g.carry_timer = 0


# ---------------------------------------------------------------- weapon
@port(0x8002F8A8, ret=True)
def charge_update(g):
    """Square held during an animation that allows it: the charge counts to 60 (11+
    shows the glow, 60 sparkles and hums)."""
    p = g.ent[0]
    if ((g.pad_held & SQUARE) or (g.pad_released & SQUARE)) and R.u8(0x80028C1C + g.weapon_class * 13) != 0 \
            and R.u8(ANIM_FLAGS + p.target_anim * 2) != 0:
        if g.charge < 0x3C: g.charge += 1
    else:
        g.charge = 0
    if g.charge >= 0xB:
        fx = g.charge_fx
        if fx is None or fx.b7d != 0:
            g.charge_fx = core.spawn_effect_on(g, 0, 3, 0, p, 1, 0, 0, 0x100000)
        if not (p.frame_counter & 3):
            if g.charge >= 0x3C:
                e = core.spawn_effect(g, 0, 0x10, 0, p.px, p.py, s32(p.pz + 0x100000))
                if e is not None:
                    core.play_sound(g, 0x1AD if not (p.frame_counter & 7) else 0x1AC)
                    a = rnd(g, 0x60001)
                    e.x = s32(e.x + s32(a + 0xFFFD0000) * 0x14)
                    b = next_seed(g) >> 14
                    e.y = s32(e.y + s32(b + 0xFFFE0000) * 0x14)
                    e.vx = s32(p.fx - s32(a + 0xFFFD0000))
                    e.vy = s32(p.fy - s32(b + 0xFFFE0000))
            else:
                core.play_sound(g, 0x2A)
    else:
        fx = g.charge_fx
        if fx is not None:
            fx.state = 0; g.charge_fx = None
    return g.charge


@port(0x8002FB98, ret=True)
def attack_spawn(g):
    """A weapon swing whose record names a projectile (bow arrows, wand bolts...) shoots
    it after the record's delay, in the swing animations that allow it."""
    rec = g.attack_rec
    if rec:
        p = g.ent[0]
        kind = R.u8(rec + 1)
        if kind != 0 and R.u8(ANIM_FLAGS + p.target_anim * 2 + 1) != 0:
            if g.attack_timer >= R.u8(rec + 2):
                entity.spawn_warp_entity(g, p, 0, kind, p.px, p.py, s32(p.pz + (R.u8(rec + 3) << 16)),
                                         R.s32(QUAD_DIR + p.anim_quadrant * 4))
                g.attack_rec = 0
                return 1
            g.attack_timer += 1
            return 0
        g.attack_rec = 0
    return 0


@port(0x8002EEB4, ret=True)
def attack_start(g):
    """Square: the swing of the weapon class (ground or jump), or on release of a full
    charge the charged attack with its ring of sparks.  1 when an attack started."""
    p = g.ent[0]
    if p.vram_or & 0x2000: return 0
    if g.pad_released & SQUARE:
        if g.charge < 0x3C: return 0
        if not p.on_ground: return 0
        for k in range(0x10):
            e = core.spawn_effect(g, 0, 0x10, 0, p.px, p.py, s32(p.pz + 0x100000))
            if e is not None:
                d = (0x18 + 2 * k) & 0x1F
                e.x = s32(e.x + R.s16(0x80023654 + 4 * k) * 0xC00)
                e.y = s32(e.y + R.s16(0x80023694 + 4 * k) * 0xC00)
                e.vx = R.s16(0x80023654 + 2 * d) * 0x1C0
                e.vy = R.s16(0x80023694 + 2 * d) * 0x1C0
        core.play_sound(g, 0x2B)
        g.attack_timer = 0
        rec = 0x80028C1D + g.weapon_class * 13
        g.attack_rec = rec + 8
        p.target_anim = R.u8(rec + 8)
        return 1
    if g.pad_pressed & SQUARE:
        rec = 0x80028C1D + g.weapon_class * 13 + (0 if p.on_ground else 4)
        a = R.u8(rec)
        if a != 0:
            p.target_anim = a; g.attack_rec = rec; g.attack_timer = 0
            return 1
        core.play_sound(g, 3)
    return 0


@port(0x8002F144, ret=True)
def circle_item(g):
    """Circle uses the chosen item (0 when it started: nothing else this frame)."""
    if g.pad_pressed & CIRCLE:
        if g.mode_flags == 0: return items.use_item(g)
        core.play_sound(g, 3)
    return 1


# ---------------------------------------------------------------- map squares
def _clamp_cell(x, y):
    x = 0 if x <= 0 else (0x33 if x >= 0x34 else x)
    y = 0 if y <= 0 else (0x3B if y >= 0x3C else y)
    return x, y


@port(0x8003B334, ret=True)
def tile_height_above(g, e, ox, oy):
    """Highest floor under e's box moved by (ox, oy), or 0x07800000 when a square there
    blocks it (entity class flags 8 / 1 against square bits 1 / 0x1000)."""
    x = s32(e.px + e.modx + ox); y = s32(e.py + e.mody + oy)
    xs = (tile_of_x(x >> 16), tile_of_x(s32(x + e.sizex) >> 16))
    ys = (y >> 20, s32(y + e.sizey) >> 20)
    mask = 1 if e.flags & 8 else 0
    if e.flags & 1: mask |= 0x1000
    h = 0
    for cx, cy in ((xs[0], ys[0]), (xs[1], ys[0]), (xs[0], ys[1]), (xs[1], ys[1])):
        c = g.cell8(*_clamp_cell(cx, cy))
        if c.flags & mask: return 0x07800000
        if c.height > h: h = c.height
    return h << 20


def break_drop(g, item, x, y, z):
    """What a broken block leaves (0x80033390, engine/drops.py)."""
    from . import drops
    return drops.block_drop(g, item, x, y, z)


def _attack_corners(e):
    x0 = tile_of_x(s16(e.atk_x >> 16)); x1 = tile_of_x(s32(e.atk_x + e.atk_w) >> 16)
    y0 = e.atk_y >> 20; y1 = s32(e.atk_y + e.atk_h) >> 20
    return ((x0, y0), (x1, y0), (x0, y1), (x1, y1))


@port(0x8003B104)
def break_blocks(g, e):
    """Breakable squares (bit 2) whose middle height the weapon box reaches break: the
    square loses the bit, the map's break effect plays, sound 0x1F."""
    if e.atk_on == 0: return
    z = e.atk_z; d = e.atk_d
    for cx, cy in _attack_corners(e):
        c = g.cell8(*_clamp_cell(cx, cy))
        if not (c.flags & 2): continue
        hz = c.height << 20; mid = hz + 0x80000
        if mid >= z and s32(z + d) >= mid:
            c.flags &= 0xFFFD; c.f6 = 0xFFFF
            x = s32(cx * 0x180000 + 0xC0000); y = s32((cy << 20) + 0x80000)
            core.spawn_effect(g, 0, g.map_info_byte(9), 0, x, y, hz)
            break_drop(g, 0xFF, x, y, hz)
            core.play_sound(g, 0x1F)


# ---------------------------------------------------------------- steps, dust, splashes
def _dust_table(g, p):
    if p.slope_now in (1, 2, 4): return 0x80022864, 6
    return 0x80022824, g.map_info_byte(0xA)


def _hi(seed, n): return (seed * (n & M32)) >> 32


def _div4(v): return (v + 3 if v < 0 else v) >> 2


@port(0x8002FF84)
def player_effects(g, locked):
    """Footsteps, sprint dust, water splashes, landing puffs, the low-life beep and the
    flail bouncing off walls (locked=1 while the game has taken control)."""
    p = g.ent[0]; a = p.target_anim; fc = p.frame_counter
    if a == 0x29:                                                     # PrepareSprint: dust kicks
        if not (fc & 7): core.play_sound(g, R.s16(0x80022814 + p.slope_now * 2))
        t, eff = _dust_table(g, p)
        k = p.anim_complete - 1
        if k >= 0:
            if k >= 4: k = 3
            if not (R.s16(t + 2 * k) & fc):
                e = core.spawn_effect(g, 0, eff, 0, p.px, p.py, p.floor) if eff else None
                if e is not None:
                    t5 = R.s16(t + 8 + 2 * k); v = t + p.anim_quadrant * 4
                    s1 = next_seed(g); e.vx = s32(s32(R.s16(v + 0x12) * t5) + _hi(s1, s32(R.s16(v + 0x10) * t5) + 1))
                    s2 = next_seed(g); e.vy = s32(s32(R.s16(v + 0x26) * t5) + _hi(s2, s32(R.s16(v + 0x24) * t5) + 1))
                    s3 = next_seed(g); e.vz = s32(s32(R.s16(t + 0x32) * t5) + _hi(s3, s32(R.s16(t + 0x30) * t5) + 1))
    elif a in (0x04, 0x10, 0x12, 0x14, 0x16, 0x18, 0x19, 0x3F, 0x40, 0x41, 0x42, 0x44, 0x46, 0x49, 0x4B):
        break_blocks(g, p)
    if p.fx != 0 or p.fy != 0:
        dust = None
        if a in (0x01, 0x07):
            if not (fc & 0xF): core.play_sound(g, R.s16(0x800227F4 + p.slope_now * 2))
        elif a == 0x03:
            if not (fc & 7): core.play_sound(g, R.s16(0x80022814 + p.slope_now * 2))
            dust = 0
        elif a in (0x04, 0x2A):
            dust = 1
        elif a == 0x28:                                               # SwimmingDash
            if not (fc & 7):
                e = core.spawn_effect(g, 0, 6, 0, p.px, p.py, p.floor)
                if e is not None:
                    e.vx = _div4(-p.fx); e.vy = _div4(-p.fy)
        elif a in (0x23, 0x24):                                       # moving / dashing in sand
            if not (fc & (7 if a == 0x23 else 3)):
                e = core.spawn_effect(g, 0, g.map_info_byte(0xA), 0, p.px, p.py, p.floor)
                if e is not None:
                    s1 = next_seed(g); s2 = next_seed(g); s3 = next_seed(g)
                    e.x = s32(e.x + 0xFFF40000 + _hi(s1, 0x180001))
                    e.y = s32(e.y + 0xFFF80000 + _hi(s2, 0x100001))
                    e.vz = s32(e.vz + 0x10000 + _hi(s3, 0x10001))
        if dust is not None:
            t, eff = _dust_table(g, p)
            if not (R.s16(t + 0x34) & fc):
                e = core.spawn_effect(g, 0, eff, 0, p.px, p.py, p.floor) if eff else None
                if e is not None:
                    t5 = R.s16(t + 0x36 + 2 * dust)
                    s1 = next_seed(g)
                    e.vx = s32(p.fx * t5) >> 8
                    e.vz = s32(R.s16(t + 0x3C) + _hi(s1, R.s16(t + 0x3A) + 1))
                    e.vy = s32(p.fy * t5) >> 8
    if a in (0x02, 0x06, 0x0A, 0x0B, 0x14, 0x15, 0x16, 0x17, 0x1F, 0x26, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30,
             0x41, 0x42, 0x46, 0x4B):                                 # jumping: landing
        if (locked == 0 or g.land_sound_done == 0) and p.on_ground != 0 and p.fz <= 0:
            core.play_sound(g, R.s16(0x80022804 + p.slope_now * 2))
            sl = p.slope_now
            if sl > 0 and (sl < 3 or sl == 4):
                core.spawn_effect(g, 0, 6, 0, p.px, p.py, p.floor)
            else:
                for _ in range(3):
                    eff = g.map_info_byte(0xA)
                    e = core.spawn_effect(g, 0, eff, 0, p.px, p.py, p.floor) if eff else None
                    if e is not None:
                        s1 = next_seed(g); s2 = next_seed(g)
                        e.vx = s32(_hi(s1, 0x30001) + 0xFFFE8000)
                        e.vy = s32(_hi(s2, 0x20001) + 0xFFFF0000)
            g.land_sound_done = 1
    else:
        g.land_sound_done = 0
    if locked != 0: return
    if p.hp != 0 and p.hp_max >= p.hp * 5:                            # low life beep
        g.low_hp_timer -= 1
        if g.low_hp_timer == -1:
            core.play_sound(g, 0x190); g.low_hp_timer = 0x2D
    if a in (0x12, 0x16): k = 0
    elif a in (0x40, 0x42): k = 1
    else: return
    hit = p.hits != 0
    if not hit:
        if p.atk_on == 0: return
        for cx, cy in _attack_corners(p):
            c = g.cell8(*_clamp_cell(cx, cy))
            if p.atk_z < (c.height << 20) or c.flags & 0x40:
                hit = True; break
    if hit:                                                           # flail bounces off
        p.target_anim = R.u8(0x800228A4 + 2 * k + (0 if p.on_ground else 1))


# ---------------------------------------------------------------- MovePlayer
LAND_GROUPS = {}
def _grp(anims, name):
    for a in anims: LAND_GROUPS[a] = name
_grp((0x00, 0x01), 'idle'); _grp((0x02, 0x2B, 0x2C, 0x2D), 'jump'); _grp((0x03,), 'sprint')
_grp((0x04, 0x08, 0x09, 0x10, 0x11, 0x12, 0x13, 0x18, 0x19, 0x25, 0x3F, 0x40, 0x44, 0x49), 'ground_attack')
_grp((0x05,), 'pickup'); _grp((0x06, 0x07, 0x0C, 0x2E, 0x2F, 0x30), 'holding')
_grp((0x0A, 0x14, 0x15, 0x16, 0x17, 0x1F, 0x26, 0x41, 0x42, 0x46, 0x4B), 'air_attack')
_grp((0x0B,), 'pickup_air'); _grp((0x0E, 0x35), 'ladder')
_grp((0x0F, 0x1D, 0x28, 0x39, 0x3C, 0x4E, 0x4F), 'to_land'); _grp((0x3A, 0x3B), 'to_land_turn')
_grp((0x1C, 0x3E), 'knocked'); _grp((0x20, 0x24), 'sand_edge'); _grp((0x21, 0x31, 0x34), 'item_only')
_grp((0x22, 0x23), 'sand'); _grp((0x29,), 'prepare_sprint'); _grp((0x2A,), 'stop_sprint')
_grp((0x32, 0x33), 'spell'); _grp((0x36,), 'loading')


def _land_or_jump(p): return 0 if p.on_ground else 0x2D


@port(0x80032174)
def move_player(g):
    p = g.ent[0]
    g.talk_target = None
    slope = p.slope_now
    g.weapon_class = R.u8(WEAPON_CLASS + menu.equipped_kind(g))
    check_portals(g)
    if p.frozen != 0:
        g.charge = 0; g.attack_rec = 0
    elif g.mode_flags & 0x34:                       # a cutscene / the game holds him
        player_effects(g, 1)
        g.charge = 0; g.attack_rec = 0
        carry(g, 1)
        items.item_end(g)
        if g.mode_flags == 0x20 and hit_check(g) != -1:
            p.damaged_tick = 0x78
    else:
        p.flags |= 0x100
        player_effects(g, 0)
        d = hit_check(g)
        if d != -1:                                 # hurt: DamageTaken (swimming: 0x3A)
            g.charge = 0; g.attack_rec = 0
            carry(g, 2)
            items.item_tick(g)
            p.target_anim = 0x3A if slope == 4 else 0x31
            p.target_dir = d
            p.damaged_tick = 0x78
        elif p.hp != 0:
            if not (p.tile_flags & 0x80):
                items.item_tick(g)
                held = g.pad_held & 0xFFFF; bits = held >> 12
                d = R.s32(PAD_DIR + bits * 4)
                if d == -1: d = p.target_dir
                if slope in (0, 1, 2, 3, 5, 6, 7):
                    _move_land(g, p, slope, bits, d)
                elif slope == 4:
                    _move_swim(g, p, bits, d)
            else:                                   # a square that takes control (0x80)
                g.charge = 0; g.attack_rec = 0
                items.item_end(g)
                carry(g, 1)
                if slope != 4: p.target_anim = _land_or_jump(p)
                else: p.target_anim = 0x1D
        else:                                       # no life left
            g.charge = 0; g.attack_rec = 0
            carry(g, 2)
            items.item_end(g)
            _dying(g, p, slope)
    menu.update_equipment(g)
    menu.hud_set_max(g, p.hp_max)
    menu.hud_set_hp(g, p.hp)


def _dying(g, p, slope):
    a = p.target_anim
    if a in (0x4E, 0x4F):                           # Dead finished: Wonder Essence or game over
        if p.anim_done != 0:
            if menu.has_item(g, 0x27) != 0:
                items.use39(g, 0x27)
                p.target_anim = 0x1D if slope == 4 else 0
            else:
                g.warp_request = 1; g.warp_effect = 8; g.warp_sound = 0
                g.warp_map = 0x1DD; g.warp_anim = 0
                g.mode_flags |= 4
    elif a in (0x31, 0x39):
        if slope == 4: p.target_anim = 0x3C
    elif a in (0x3A, 0x3C):
        if slope != 4: p.target_anim = 0x39
    elif a == 0x1C:
        if slope == 4: p.target_anim = 0x3C
        elif p.anim_done != 0: p.target_anim = 0x39
    elif a == 0x3B:
        if slope != 4: p.target_anim = 0x39
        elif p.anim_done != 0: p.target_anim = 0x3C
    else:
        p.target_anim = 0x3C if slope == 4 else 0x39


def _move_swim(g, p, bits, d):
    g.charge = 0; g.attack_rec = 0
    carry(g, 2)
    a = p.target_anim
    if a in (0x1C, 0x31, 0x3E):
        p.target_dir = (p.target_dir + 0x10) & 0x1F
        p.target_anim = 0x1D; circle_item(g); return
    if a in (0x0F, 0x1D):
        p.target_dir = d
        if circle_item(g) != 0:
            r = find_talk(g)
            if r != 0:
                if r == 2: p.target_anim = 0x1D
            else:
                p.target_anim = 0x28 if g.pad_pressed & 0xD0 else (0x0F if bits != 0 else 0x1D)
        return
    if a in (0x28, 0x3A):
        circle_item(g); return
    if a == 0x3B:
        if circle_item(g) == 0:
            p.target_dir = (p.target_dir + 0x10) & 0x1F
        elif p.anim_done == 1:
            p.target_anim = 0x1D; p.target_dir = (p.target_dir + 0x10) & 0x1F
        return
    if a < 0x50 and a not in SWIM_NOTHING:          # everything else: back to floating
        p.target_anim = 0x1D; circle_item(g); return
    items.item_end(g)


SWIM_NOTHING = (0x0D, 0x1A, 0x1B, 0x1E, 0x27, 0x37, 0x38, 0x3D, 0x43, 0x45, 0x47, 0x48, 0x4A, 0x4C, 0x4D)


def _move_land(g, p, slope, bits, d):
    if slope == 6 and bits != 0 and d == 0x10 and p.target_dir == d and p.force_adjusted != 0 and p.carried is None:
        p.target_anim = 0x0E                         # ladder: pushing up into it
    charge_update(g)
    attack_spawn(g)
    carry(g, 0)
    a = p.target_anim
    grp = LAND_GROUPS.get(a) if a < 0x50 else None
    if grp is None:
        items.item_end(g); return
    if grp == 'to_land_turn':
        p.target_dir = (p.target_dir + 0x10) & 0x1F; grp = 'to_land'
    if grp == 'to_land':
        p.target_anim = _land_or_jump(p); circle_item(g); return
    if grp == 'air_attack':
        if p.on_ground: p.target_anim = 0
        circle_item(g); return
    if grp == 'ground_attack':
        if not p.on_ground: p.target_anim = 0x2D
        circle_item(g); return
    if grp == 'item_only':
        circle_item(g); return
    if grp in ('idle', 'jump'):
        p.target_dir = d
        if circle_item(g) == 0 or holding_or_lift(g) != 0: return
        if grp == 'idle':
            r = find_talk(g)
            if r != 0:
                if r == 2: p.target_anim = 0
                return
        if attack_start(g) != 0: return
        if not p.on_ground:
            p.target_anim = 0x2C if bits != 0 else 0x2D
        elif g.pad_pressed & CROSS:
            if not (p.vram_or & 0x4000): p.target_anim = 2 if bits != 0 else 0x2B
        elif g.pad_held & TRIANGLE:
            p.target_anim = 0x29; p.anim_complete = 0
        else:
            p.target_anim = 1 if bits != 0 else 0
        return
    if grp == 'prepare_sprint':
        if circle_item(g) == 0 or holding_or_lift(g) != 0 or attack_start(g) != 0: return
        p.target_dir = d
        if not p.on_ground: p.target_anim = 0x2D; return
        if not (g.pad_held & TRIANGLE): p.target_anim = 0; return
        if p.anim_complete != 0:
            d4 = R.s32(PAD_DIR4 + bits * 4)
            if d4 != -1:
                p.target_dir = d4; p.target_anim = 3
        return
    if grp == 'sprint':
        if holding_or_lift(g) != 0: return
        if not p.on_ground: p.target_anim = 0x2D; return
        if p.force_adjusted != 0:                    # ran into a wall
            core.spawn_effect(g, 0, 9, 0, p.px, p.py, s32(p.pz + 0x100000))
            p.target_anim = 0x3E; p.target_dir = (p.target_dir + 0x10) & 0x1F; return
        if bits == 0:
            p.target_anim = 0x2A; g.sprint_resume = 1; return
        q = p.anim_quadrant * 12
        if not (g.pad_held & TRIANGLE) or (d != R.s32(SPRINT_TURN + q) and d != R.s32(SPRINT_TURN + q + 4)
                                          and d != R.s32(SPRINT_TURN + q + 8)):
            p.target_anim = 0x2A; g.sprint_resume = 0; return
        if g.pad_held & 0xE0: p.target_anim = 4
        return
    if grp == 'stop_sprint':
        if circle_item(g) == 0 or holding_or_lift(g) != 0: return
        if not p.on_ground: p.target_anim = 0x2D; return
        r = g.sprint_resume
        if r != 0:
            if p.force_adjusted == 0 and (g.pad_held & TRIANGLE):
                g.sprint_resume = r + 1
                if r + 1 >= 0xB:
                    d4 = R.s32(PAD_DIR4 + bits * 4)
                    if d4 != -1:
                        p.target_dir = d4; p.target_anim = 3
                    return
                if bits == 0: return
            g.sprint_resume = 0
        return
    if grp == 'ladder':
        if circle_item(g) == 0 or holding_or_lift(g) != 0: return
        if not (bits == 0 or d == 0 or d == 0x10):
            p.target_anim = 0x2D; return
        p.target_dir = 0x10
        if bits == 0:
            p.target_anim = 0x35; p.fz = 0; p.flags &= ~0x100; return
        if d == 0:
            if p.floor + 1 < p.pz:
                p.target_anim = 0x0E; p.fz = -0x10000; p.flags &= ~0x100
            else: p.target_anim = 0
            return
        if tile_height_above(g, p, 0, -0x10000) >= p.pz:
            p.target_anim = 0x0E; p.fz = 0x10000; p.flags &= ~0x100
        else: p.target_anim = 0
        return
    if grp == 'pickup_air':
        if circle_item(g) != 0:
            if p.carried is not None:
                if p.on_ground: p.target_anim = 0x0C
            else: p.target_anim = 0
        return
    if grp == 'pickup':
        if circle_item(g) != 0:
            if p.carried is not None:
                if not p.on_ground: p.target_anim = 0x30
            else: p.target_anim = 0x2D
        return
    if grp == 'holding':
        p.target_dir = d
        if circle_item(g) == 0: return
        c = p.carried
        if c is None:
            if not p.on_ground: p.target_anim = 0x2D
            else: p.target_anim = 0
            return
        if g.pad_pressed & SQUARE:
            if not (p.vram_or & 0x2000):            # throw
                c.target_dir = R.s32(QUAD_DIR + p.anim_quadrant * 4)
                c.px, c.py, c.pz = p.px, p.py, s32(p.pz + 0x200000)
                if p.on_ground:
                    p.target_anim = 9; c.flags2 = 1 if bits == 0 else 2
                else:
                    p.target_anim = 0xA; c.flags2 = 3 if bits != 0 else 2
            return
        if (c.flags & 0x600) == 0x600:
            p.target_anim = 0x0C if p.on_ground else 0x30; return
        if p.on_ground:
            if g.pad_pressed & CROSS:
                if not (p.vram_or & 0x4000): p.target_anim = 6 if bits != 0 else 0x2E
            else:
                p.target_anim = 7 if bits != 0 else 0x0C
        else:
            p.target_anim = 0x2F if bits != 0 else 0x30
        return
    if grp == 'sand':
        p.target_dir = d
        if circle_item(g) == 0: return
        if g.item_use == 0x20:
            p.target_anim = 0x24 if g.pad_pressed & 0xD0 else (0x23 if bits != 0 else 0x22)
        else:
            p.target_anim = _land_or_jump(p)
        return
    if grp == 'sand_edge':
        if circle_item(g) != 0 and g.item_use != 0x20:
            p.target_anim = _land_or_jump(p)
        return
    if grp == 'knocked':
        if circle_item(g) == 0:
            p.target_dir = (p.target_dir + 0x10) & 0x1F; return
        if p.anim_done == 1:
            p.target_dir = (p.target_dir + 0x10) & 0x1F
            p.target_anim = 0 if p.on_ground else 1
        return
    if grp == 'spell':
        if circle_item(g) != 0 and ((g.item_use - 0x2B) & M32) >= 8:
            p.target_anim = _land_or_jump(p)
        return
    if grp == 'loading':
        if not p.on_ground: p.target_anim = 0x2D
        return
