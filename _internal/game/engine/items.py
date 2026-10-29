"""Items used with Circle (0x8003514C) and their start / per-frame / ending routines,
ported from ALUN_CD.EXE (2026-10-17)."""
from .registry import port
from . import core, menu


# ---- ported from ALUN_CD.EXE (2026-10-17).  Alundra is Entity slot 0 (0x801AC6F8);
# 0x801DDA6C (g.item_dda6c) is the item's phase, 0x801D7B38 (g.item_frames) its frame.
from .core import s32, next_seed, hi
from . import calls

SHAKE, SHAKE_SAVE = 0x801F94D0, 0x8012E238       # the screen shake words (9) and the Fire Book's copy
SIN, COS = 0x80023654, 0x80023694                # s16[32]: x / y of 32 directions (radius 768 / 512)


def _spawn(g, index, x, y, z, d=0):
    """0x8003A860(Alundra, global, index, x, y, z, direction)."""
    return calls.call(g, 0x8003A860, g.player, 0, index, s32(x), s32(y), s32(z), d & 0xFF)


def _fx(g, index, sub, x, y, z):
    return calls.call(g, 0x8003C760, 0, index, sub, s32(x), s32(y), s32(z))


def _remove(g, e): calls.call(g, 0x8003B0C8, e)


def _rom16(g, a): return g.mem.s16(a)


def _word(e, off, v):
    """A word the game stores at Entity+off (0x274 bytes, 0x278 delay, 0x27C item_state,
    0x280.. the ai halfwords in pairs)."""
    v = s32(v)
    if off == 0x274: e.bytes[0:4] = [v & 0xFF, v >> 8 & 0xFF, v >> 16 & 0xFF, v >> 24 & 0xFF]
    elif off == 0x278: e.delay = v
    elif off == 0x27C: e.item_state = v
    else:
        k = (off - 0x280) // 2
        e.ai[k] = v & 0xFFFF; e.ai[k + 1] = v >> 16 & 0xFFFF


def _rword(e, off):
    k = (off - 0x280) // 2
    return s32((e.ai[k] & 0xFFFF) | (e.ai[k + 1] & 0xFFFF) << 16)


def _slots(g):
    for k in range(1, g.ent_count + 1):
        if k < 64: yield g.ent[k]


def _attr(e, n): return getattr(e, n, 0) or 0


def _carry_start(g, index, ok):
    """Spring Bean / Bomb: one made at Alundra's feet and held over him."""
    p = g.player
    if p.carried is not None or _attr(p, 'slope_now') == 4 or g.item_use != 0 or not ok:
        core.play_sound(g, 3); return 1
    e = _spawn(g, index, p.px, p.py, p.pz, 0)
    if e is None: return 1
    if index == 2: e.bytes[0:4] = [0xF0, 0, 0, 0]        # the fuse: 240 frames
    p.carried = e; e.holder = p
    p.target_anim = 5 if p.on_ground else 0xB
    p.carry_dx = s32(e.px - p.px); p.carry_dy = s32(e.py - p.py); p.carry_dz = s32(e.pz - p.pz)
    return 0


@port(0x80034948, ret=True)
def start31(g, it):
    """Spring Bean: a bean (global sprite 1) in Alundra's hands."""
    return _carry_start(g, 1, True)


@port(0x80034CC0, ret=True)
def start35(g, it):
    """Bomb: fewer than 3 bombs (sprite 2) about; a bomb with a 240-frame fuse in his hands."""
    n = sum(1 for k in range(64) if g.ent[k] is not None and _attr(g.ent[k], 'sprite_index') == 2)
    return _carry_start(g, 2, n < 3)


def _box_clear(g):
    """No solid entity (flags 0x80, not anim flag 0x80, status 2-3, not frozen or held)
    overlaps Alundra's box."""
    p = g.player
    for t in _slots(g):
        if not ((_attr(t, 'estatus') - 2) & 0xFFFFFFFF) < 2 or _attr(t, 'frozen'): continue
        if not _attr(t, 'flags') & 0x80 or _attr(t, 'anim_flags') & 0x80 or t.holder is not None: continue
        ok = True
        for a, b in (('mpx', 'sizex'), ('mpy', 'sizey'), ('mpz', 'sizez')):
            d = s32(_attr(p, a) - _attr(t, a))
            if d >= 0: inside = d < _attr(t, b) + 1
            else: inside = -d < _attr(p, b) + 1
            if not inside: ok = False; break
        if ok: return False
    return True


@port(0x80034A7C, ret=True)
def start32(g, it):
    """Sand Cape: on sand (slope kind 3) and standing: animation 0x20; already in use and
    gliding (0x22), still and on the ground with room: 0x21 (land)."""
    p = g.player
    if g.item_use == 0:
        if _attr(p, 'slope_now') == 3 and (p.target_anim & 0xFFFFFFFF) < 2:
            p.target_anim = 0x20; return 0
    elif p.target_anim == 0x22 and not _attr(p, 'ffx') and not _attr(p, 'ffy') and p.on_ground and _box_clear(g):
        p.target_anim = 0x21; return 0
    core.play_sound(g, 3); return 1


XA_CLIP = {43: 0, 44: 1, 45: 6, 46: 6, 47: 2, 48: 3, 49: 4, 50: 5}   # byte table 0x80023365


@port(0x80035094, ret=True)
def start_magic(g, it):
    """Scrolls and Books: standing, nothing held; one magic point (none with item 7 equipped);
    the spell's XA clip; animation 0x32."""
    from . import drops
    p = g.player
    if p.carried is not None or not (p.target_anim & 0xFFFFFFFF) < 2 or g.item_use != 0:
        core.play_sound(g, 3); return 1
    if menu.equipped_kind(g) != 7:
        st = menu._stats(g); mp = g.mem.s16(st + 4)
        if mp == 0:
            core.play_sound(g, 3); return 1
        g.mem.w16(st + 4, max(0, mp - 1) & 0xFFFF)      # 0x8004F5C8(1)
    calls.call(g, 0x8005CB94, XA_CLIP.get(it, 0))
    p.target_anim = 0x32
    return 0


@port(0x80035944, ret=True)
def magic_stop(g):
    """A spell stops (1) in water (slope kind 4) or when Alundra left animations 0x32 / 0x33."""
    p = g.player
    if _attr(p, 'slope_now') != 4 and ((p.target_anim - 0x32) & 0xFFFFFFFF) < 2: return 0
    item_end(g); return 1


def _held_tick(g, index):
    c = g.player.carried
    if c is None: return 1
    if _attr(c, 'sprite_index') != index: return 1
    if _attr(g.player, 'slope_now') != 4: return 0
    item_end(g); return 1


@port(0x80035990, ret=True)
def tick31(g, it): return _held_tick(g, 1)


@port(0x80035A5C, ret=True)
def tick35(g, it): return _held_tick(g, 2)


@port(0x800359E4, ret=True)
def tick32(g, it):
    p = g.player; a = p.target_anim
    if not (((a - 0x20) & 0xFFFFFFFF) < 2 or ((a - 0x22) & 0xFFFFFFFF) < 2 or a == 0x24): return 1
    if p.on_ground and _attr(p, 'slope_now') != 4: return 0
    item_end(g); return 1


def _next_phase(g):
    g.player.target_anim = 0x34; g.item_dda6c += 1


def _finish(g):
    return 0 if g.player.target_anim == 0x34 else 1


@port(0x80035AB0, ret=True)
def tick43(g, it):
    """Earth Scroll: rocks (sprite 0x10) around Alundra on the frames of table 0x8002343C."""
    ph = g.item_dda6c
    if ph == 0:
        if magic_stop(g): return 1
        p = g.player; a = 0x8002343C
        while g.mem.u16(a) <= g.item_frames:
            if g.mem.u16(a) == g.item_frames:
                e = _spawn(g, 0x10, p.px, p.py, p.pz, (p.target_dir + _rom16(g, a + 4)) & 0x1F)
                if e is not None: e.fz = s32(_rom16(g, a + 2) << 8)
            a += 6
        if g.mem.u16(a) == 0xFFFF: g.item_dda6c += 1
        return 0
    if ph == 1:
        if magic_stop(g): return 1
        if g.item_frames < 100: return 0
        _next_phase(g); return 0
    if ph == 2: return _finish(g)
    return 0


@port(0x80035C68, ret=True)
def tick44(g, it):
    """Earth Book: boulders (sprite 0x11) falling round Alundra (table 0x80023504)."""
    ph = g.item_dda6c
    if ph == 0:
        if magic_stop(g): return 1
        p = g.player; a = 0x80023504
        while g.mem.u16(a) <= g.item_frames:
            if g.mem.u16(a) == g.item_frames:
                k = hi(next_seed(g), 0x20); r = _rom16(g, a + 2) + 0xA00
                d = hi(next_seed(g), 0x20)
                x = p.px + s32(_rom16(g, SIN + 2 * k) * r); y = p.py + s32(_rom16(g, COS + 2 * k) * r)
                z = s32(p.pz + 0x1000000)
                e = _spawn(g, 0x11, x, y, z, d)
                if e is not None:
                    if z < _attr(e, 'terrain'): _remove(g, e)
                    else: e.fz = -0x80000
            a += 4
        if g.mem.u16(a) == 0xFFFF: g.item_dda6c += 1
        return 0
    if ph == 1:
        if magic_stop(g): return 1
        if g.item_frames < 0x118: return 0
        _next_phase(g); return 0
    if ph == 2: return _finish(g)
    return 0


@port(0x80035F1C, ret=True)
def tick45(g, it):
    """Water Scroll / Book: water (sprite 0x13) rising round Alundra (tables 0x80023544 /
    0x8002357C, 14 bytes a row); at frame 30 of the next phase life (scroll: 0x80033698,
    book: all of it); it ends when no water is left."""
    ph = g.item_dda6c; p = g.player
    if ph == 0:
        if magic_stop(g): return 1
        a = 0x80023544 if it == 0x2D else 0x8002357C
        while g.mem.u16(a) <= g.item_frames:
            if g.mem.u16(a) == g.item_frames:
                e = _spawn(g, 0x13, p.px, p.py, p.pz + 0x80000, 0)
                if e is not None:
                    f = g.item_frames
                    _word(e, 0x280, _rom16(g, a + 8)); _word(e, 0x288, 0); e.bi_a = 0xFE
                    _word(e, 0x284, 1); _word(e, 0x278, _rom16(g, a + 4)); _word(e, 0x27C, _rom16(g, a + 6))
                    _word(e, 0x274, _rom16(g, a + 2))
                    v = s32(_rom16(g, a + 0xA) + s32(_rword(e, 0x280) * f))
                    _word(e, 0x28C, v - int(v / 256) * 256)
                    _word(e, 0x290, _rom16(g, a + 0xC) - f)
            a += 0xE
        if g.mem.u16(a) == 0xFFFF:
            g.mem.w32(0x80104808, 0); g.item_dda6c += 1
        return 0
    if ph == 1:
        if magic_stop(g): return 1
        n = g.mem.s32(0x80104808) + 1; g.mem.w32(0x80104808, n)
        if n == 30:
            if it == 0x2D: calls.call(g, 0x80033698, p); core.play_sound(g, 0x31)
            else: calls.call(g, 0x80033980, p); core.play_sound(g, 0x30)
        if n < 60: return 0
        _next_phase(g); return 0
    if ph == 2:
        if p.target_anim == 0x34: return 0
        for t in _slots(g):
            if _attr(t, 'sprite_index') == 0x13 and _rword(t, 0x290) > 0: return 0
        return 1
    return 0


def _summon(g, index, z_up=0):
    p = g.player
    return _spawn(g, index, p.px, p.py, p.pz + z_up, 0)


@port(0x80036204, ret=True)
def tick47(g, it):
    """Fire Scroll: a fire (sprite 0x14); while it lasts, sparks (0x17) every 8 frames."""
    ph = g.item_dda6c; p = g.player
    if ph == 0:
        if magic_stop(g): return 1
        if p.target_anim != 0x33: return 0
        e = _summon(g, 0x14); g._item_ent = e
        if e is None: return 1
        g._item_serial = e.serial; g.item_dda6c = ph = 1
    if ph == 1:
        if magic_stop(g): return 1
        e = getattr(g, '_item_ent', None)
        if e is not None and e.serial == g._item_serial and e.alive:
            if g.item_frames & 7: return 0
            d = hi(next_seed(g), 0x20)
            s = _spawn(g, 0x17, p.px, p.py, p.pz + 0x100000, d)
            if s is not None:
                s.fz = 0x80000; _word(s, 0x274, 0x10); s.delay = 0
            return 0
        _next_phase(g); return 0
    if ph == 2: return _finish(g)
    return 0


def _shake_copy(g, src, dst):
    for i in range(9): g.mem.w32(dst + 4 * i, g.mem.u32(src + 4 * i))


@port(0x80036424, ret=True)
def tick48(g, it):
    """Fire Book: a fire storm (sprite 0x15) with the screen shaking harder as it goes."""
    ph = g.item_dda6c; p = g.player
    if ph == 0:
        if magic_stop(g): return 1
        if p.target_anim != 0x33: return 0
        e = _summon(g, 0x15); g._item_ent = e
        if e is None: return 1
        _shake_copy(g, SHAKE, SHAKE_SAVE)
        g._item_serial = e.serial; g.item_dda6c = ph = 1
    if ph == 1:
        if magic_stop(g):
            _shake_copy(g, SHAKE_SAVE, SHAKE); return 1
        e = getattr(g, '_item_ent', None)
        if e is not None and e.serial == g._item_serial and e.alive:
            f = g.item_frames; m = g.mem
            m.w32(SHAKE, 1); m.w32(SHAKE + 8, f >> 4); m.w32(SHAKE + 0x10, f >> 4)
            m.w32(SHAKE + 4, f >> 6); m.w32(SHAKE + 0xC, f >> 6)
            return 0
        _shake_copy(g, SHAKE_SAVE, SHAKE)
        _next_phase(g); return 0
    if ph == 2: return _finish(g)
    return 0


@port(0x800366B0, ret=True)
def tick49(g, it):
    """Wind Scroll: a whirlwind (sprite 0x16) on the frames of table 0x800235E0, on the
    nearest enemy within 100 pixels (not the last one hit), else at random near Alundra."""
    ph = g.item_dda6c; p = g.player
    if ph == 0:
        g._wind_last = None; g.item_dda6c = ph = 1
    if ph == 1:
        if magic_stop(g): return 1
        if p.target_anim != 0x33: return 0
        from .entity import ent_at
        a = 0x800235E0
        while g.mem.u16(a) <= g.item_frames:
            if g.mem.u16(a) == g.item_frames:
                ents, dists = 0x80142B80, 0x80142C80
                n = calls.call(g, 0x8003B8B0, p, 1, 0xB, ents, dists)
                target = None
                for i in range(n):
                    t = ent_at(g, g.mem.u32(ents + 4 * i))
                    if t is None or s32(p.pz + 0x500000) < t.pz or t is g._wind_last: continue
                    if g.mem.s32(dists + 4 * i) < 0x6401: target = t
                    break
                if target is not None:
                    e = _spawn(g, 0x16, target.px, target.py, target.pz + 0x800000, 0)
                    if e is not None: e.fz = -0x80000
                    g._wind_last = target
                else:
                    r1 = next_seed(g); r2 = next_seed(g)
                    e = _spawn(g, 0x16, p.px + hi(r1, 0xC00001) - 0x600000,
                               p.py + hi(r2, 0x800001) - 0x400000, p.pz + 0x800000, 0)
                    if e is not None:
                        if e.on_ground: _remove(g, e)
                        else: e.fz = -0x80000
                    g._wind_last = None
            a += 2
        if g.mem.u16(a) == 0xFFFF: _next_phase(g)
        return 0
    if ph == 2: return _finish(g)
    return 0


@port(0x80036A48, ret=True)
def tick50(g, it):
    """Wind Book: a tornado (sprite 0x18) that lasts as long as its entity."""
    ph = g.item_dda6c; p = g.player
    if ph == 0:
        if magic_stop(g): return 1
        if p.target_anim != 0x33: return 0
        e = _summon(g, 0x18); g._item_ent = e
        if e is None: return 1
        g._item_serial = e.serial; g.item_dda6c = 1; return 0
    if ph == 1:
        if magic_stop(g): return 1
        e = getattr(g, '_item_ent', None)
        if e is not None and e.serial == g._item_serial and e.alive: return 0
        _next_phase(g); return 0
    if ph == 2: return _finish(g)
    return 0


def _drop_held(g, index, effect):
    p = g.player; c = p.carried
    if c is None or _attr(c, 'sprite_index') != index or _attr(c, 'flags2'): return
    p.carried = None
    _fx(g, effect, 0, c.px, c.py, c.pz)
    _remove(g, c)


@port(0x8003527C)
def end31(g, it): _drop_held(g, 1, 8)


@port(0x80035300)
def end35(g, it): _drop_held(g, 2, 0xC)


@port(0x80035384)
def end44(g, it):
    for t in _slots(g):
        if _attr(t, 'sprite_index') == 0x11 and t.estatus == 2:
            t.estatus = 3; t.frozen = 0; t.target_anim = 1


@port(0x800353F8)
def end45(g, it):
    for t in _slots(g):
        if _attr(t, 'sprite_index') == 0x13 and t.estatus == 2:
            _fx(g, 0x1A, 0, t.px, t.py, t.pz); _remove(g, t)


@port(0x800354C8)
def end47(g, it):
    for t in _slots(g):
        if t.estatus != 2: continue
        if _attr(t, 'sprite_index') == 0x14:
            _fx(g, 0x13, 2, t.px, t.py, t.pz); _remove(g, t)
        if _attr(t, 'sprite_index') == 0x17:
            t.estatus = 3; t.frozen = 0


@port(0x800355A4)
def end48(g, it):
    _shake_copy(g, SHAKE_SAVE, SHAKE)
    for t in _slots(g):
        if _attr(t, 'sprite_index') == 0x15 and t.estatus == 2:
            t.estatus = 3; t.frozen = 0


@port(0x8003565C)
def end50(g, it):
    for t in _slots(g):
        if _attr(t, 'sprite_index') != 0x18 or t.estatus != 2: continue
        t.estatus = 3; t.frozen = 0
        for _ in range(16):
            a = next_seed(g); b = next_seed(g)
            k = hi(a, 0x20)
            fx = _fx(g, 0x12, 0, t.px, t.py, t.pz + hi(b, 0x600001))
            if fx is not None:
                fx.vx = s32(_rom16(g, SIN + 2 * k) << 9); fx.vy = s32(_rom16(g, COS + 2 * k) << 9)
                fx.vz = s32(hi(next_seed(g), 0x10001) - 0x8000)


# ---- items used at once (Herbs, the elixirs, Wonder Essence, Strength Tonic):
# the effect on Alundra (Entity 0x801AC6F8), its sound, one taken from the
# inventory (0x8004FC80); with nothing to restore, the "no" sound 3.
def _life_short(g):
    p = g.player
    return p.hp < p.hp_max


def _magic_short(g):
    from . import drops
    st = menu._stats(g)
    return g.mem.s16(st + 4) < drops.magic_max(g)        # 0x8004F528 < 0x8004F45C


def _use_once(g, it, ok, effect, sound):
    if not ok:
        core.play_sound(g, 3); return 1
    from . import calls
    calls.call(g, effect, g.player)
    core.play_sound(g, sound)
    _take(g, it)
    return 1


def _take(g, it):                                       # 0x8004FC80
    inv = getattr(g, 'inventory', None)
    if inv is not None and inv.get(it, 0) > 0: inv[it] = inv[it] - 1


@port(0x80034E38, ret=True)
def use36(g, it):
    """Herbs: life short of the most -> 0x80033560, sound 0x31."""
    return _use_once(g, it, _life_short(g), 0x80033560, 0x31)


@port(0x80034EA8, ret=True)
def use37(g, it):
    """Strength Elixyr: life short -> all life (0x80033980), sound 0x32."""
    return _use_once(g, it, _life_short(g), 0x80033980, 0x32)


@port(0x80034F18, ret=True)
def use38(g, it):
    """Magic Elixyr: magic short of its most -> 0x80033DF0, sound 0x30."""
    return _use_once(g, it, _magic_short(g), 0x80033DF0, 0x30)


@port(0x80034F90, ret=True)
def use39(g, it):
    """Wonder Essence: life or magic short -> both full (0x80034124), sound 0x30."""
    return _use_once(g, it, _life_short(g) or _magic_short(g), 0x80034124, 0x30)


@port(0x80035024, ret=True)
def use41(g, it):
    """Strength Tonic: life short -> 0x8003380C, sound 0x31."""
    return _use_once(g, it, _life_short(g), 0x8003380C, 0x31)


@port(0x8003514C, ret=True)
def use_item(g):
    """Circle: start the chosen item.  0 = it started (MovePlayer stops for this frame)."""
    it = menu.selected_item(g)
    if (it & 0xFFFFFFFF) < 0x62 and (g.item_use == 0 or g.item_use == it):
        start = {31: start31, 32: start32, 35: start35}.get(it)
        if start is None and 43 <= it <= 50: start = start_magic
        if start is not None:
            r = start(g, it)
            if r == 0:
                g.item_use = it; g.item_frames = 0; g.item_dda6c = 0
            return r
        once = {36: use36, 37: use37, 38: use38, 39: use39, 41: use41}.get(it)
        if once is not None:
            once(g, it); return 1
    core.play_sound(g, 3)
    return 1


TICKS = {31: 'tick31', 32: 'tick32', 35: 'tick35', 43: 'tick43', 44: 'tick44', 45: 'tick45', 46: 'tick45',
         47: 'tick47', 48: 'tick48', 49: 'tick49', 50: 'tick50'}
ENDS = {31: 'end31', 35: 'end35', 44: 'end44', 45: 'end45', 46: 'end45', 47: 'end47', 48: 'end48', 50: 'end50'}


@port(0x80036BB0, ret=True)
def item_tick(g):
    """The item in use, once a frame; it ends when its routine returns non-zero."""
    u = g.item_use
    if u == 0: return 1
    fn = TICKS.get(u)
    r = globals()[fn](g, u) if fn else 1
    if g.item_frames <= 0x7FFFFFFE: g.item_frames += 1
    if r != 0: g.item_use = 0
    return r


@port(0x80035850)
def item_end(g):
    """Stops the item in use (hit, carried, dying...)."""
    fn = ENDS.get(g.item_use)
    if fn: globals()[fn](g, g.item_use)
    g.item_use = 0
