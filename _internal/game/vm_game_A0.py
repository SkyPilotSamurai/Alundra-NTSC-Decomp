"""Event script opcodes 0xA0-0xC4 and 0xFF: faithful replacements for the handlers remake/vm.py
gets WRONG or lacks (see audit_A0_C4.md).  Game: US ALUN_CD.EXE (SLUS-00553).

Convention (remake/vm.py): handler(vm, lg, ow, v, st, row) -> byte advance, 0 = yield.
lg = logic entity (game a0), ow = owner (a1), v = instruction bytes (v[0] = opcode),
st = ProgState (the game's ctx, a3).  Importing this module after vm re-registers the opcodes
(@op overwrites the vm.HANDLERS entries) and corrects their DOC lines; or paste the functions
over the old ones in vm.py.

ctx words used here: +0x08 = st.params[1] (pc a waiting instruction started on, zeroed by
VM.run on every advance), +0x0C = st.params[2], +0x2C = st.result.
Positions are the remake's 16.16 integers (px py pz, effect x y z), never the float views.
Engine routines that are not ported are called through clearly named vm.g methods (_hook);
when one is missing the call is logged with vm.note('needs g.<name>') and skipped.
"""
import sys
from pathlib import Path

try:
    from vm import op, DOC
except ImportError:                                   # run from research/us_decomp/vm_ops
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'remake'))
    from vm import op, DOC

M32 = 0xFFFFFFFF


# ------------------------------------------------------------------ helpers --
def _s32(x):
    """A 32-bit register value (wrap + sign)."""
    x &= M32
    return x - 0x100000000 if x & 0x80000000 else x


def _u16(v, i):
    """Little-endian operand v[i] | v[i+1] << 8 (the handlers' lbu + sll 8 + addu/or)."""
    return v[i] | v[i + 1] << 8


def _div(a, b):
    """MIPS div / C '/': truncates toward zero (Python // floors)."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _hook(vm, name, *args, default=None):
    f = getattr(vm.g, name, None)
    if f is None:
        vm.note(f'needs g.{name}')
        return default
    return f(*args)


def _fatal(vm, msg):
    """0x8003D23C / BIOS SystemErrorExit(1): the game stops."""
    f = getattr(vm.g, 'fatal', None)
    if f is not None: f(msg)
    else: vm.note('fatal: ' + msg)


def _st123(e):
    return e is not None and 1 <= getattr(e, 'estatus', 0) <= 3     # (status-1) < 2u || == 3


def _record_ok(g, ref):
    """0x8003A4C0: ref < record count (0x801F2ED4) and record byte 4 != 0."""
    recs = g.map.doc.get('entities', [])
    return 0 <= ref < len(recs) and recs[ref].get('enabled', 1) != 0


def _sel(vm, lg, sel):
    """0x8003D374(logic, sel): the list at 0x8013D488 in the game's order (ascending slot,
    Alundra = slot 0).  'First selected' = [0]; 'any' loops walk it from the end (order is
    irrelevant for a pure test).  Same rules as audit_00_2F.select_faithful."""
    g = vm.g; ent = g.slots; n = g.count                 # g_ent_count 0x801D93EC
    sel &= 0xFF
    if not sel & 0x80:                                   # map record (ref_id) number
        if not _record_ok(g, sel):                       # 0x8003D330
            _fatal(vm, 'Illegal InitData Number!!'); return []
        if not _st123(lg): return []                     # tests the LOGIC entity's status
        return [e for e in ent[1:n + 1] if e is not None and e.ref_id == sel]
    f = sel & 0x7F
    if f == 0: return [lg]
    if f == 1: return [ent[0]]
    if f == 2: return [e for e in ent[0:n + 1] if _st123(e)]
    if f == 3: return [e for e in ent[1:n + 1] if _st123(e)]
    if f == 4:                                           # again the LOGIC entity's status
        if not _st123(lg): return []
        return [e for e in ent[0:n + 1] if e is not None and e.flags & 0x80
                and not getattr(e, 'anim_flags', 0) & 0x80 and getattr(e, 'holder', None) is None]
    if f > 0x0B:
        _fatal(vm, 'Illegal Distination!'); return []
    test = {
        5: lambda e: lg.riding is e,                     # +0x12C
        6: lambda e: e.riding is lg,
        7: lambda e: lg.x_collision is e,                # +0x130
        8: lambda e: e.x_collision is lg,
        9: lambda e: e.parent is lg,                     # +0x0C
        10: lambda e: lg.parent is e,
        11: lambda e: getattr(e, 'holder', None) is not None,   # +0x28
    }[f]
    return [e for e in ent[1:n + 1] if _st123(e) and test(e)]


# ------------------------------------------------------------ map effects --
def _fx_by_id(g, n):
    """Effect records (0x80133990, 128 x 0x80) with +0x68 != 0 and +0x30 == n.
    The remake keeps +0x30 (map effect record number) in Effect.map_id."""
    return [e for e in g.effects.fx if e.state and getattr(e, 'map_id', -1) == n]


def _spawn_map_effect(g, n, force):
    """0x8003CA78(n, force): map effect record n (12 bytes at 0x801F2ED8:
    x1 y1 x2 y2 flags effect x y z anim) into the lowest free effect record.
    force == 0: only if Alundra's tile (Entity+0x120/+0x124) is inside x1..x2, y1..y2 AND
    flags & 0x40.  force != 0 (all calls in this range): no test at all."""
    fx = g.effects
    recs = getattr(fx, 'records', [])
    if not 0 <= n < len(recs): return None               # 0x8003C3C8: n < 0x801F2EE4
    r = recs[n]
    if not force:
        p = g.player
        tx = getattr(p, 'tile_x', (p.px >> 16) // 24); ty = getattr(p, 'tile_y', (p.py >> 16) // 16)
        if not (r['x1'] <= tx <= r['x2'] and r['y1'] <= ty <= r['y2']): return None
        if not r['flags'] & 0x40: return None
    # 0x8003C46C(e, rec, n, mode 0, bank = flags & 0x80, effect, anim, x, y, z)
    e = fx.create(bool(r['flags'] & 0x80), r['effect'], r['anim'],
                  (r['x'] * 12 + 12) << 16, (r['y'] * 8 + 8) << 16, r['z'] << 19)
    if e is not None:
        e.map_id = n; e.spr_anim = n                     # +0x30 = n (+0x04 = record pointer)
    return e


@op(0xA1)
def _fx_to_sel(vm, lg, ow, v, st, row):       # 0x8004190C
    """Every effect of map record v1 -> first selected entity (v2) + (u16 << 16) offsets."""
    s = _sel(vm, lg, v[2])
    if s:
        t = s[0]
        x = _s32(t.px + (_u16(v, 3) << 16))
        y = _s32(t.py + (_u16(v, 5) << 16))
        z = _s32(t.pz + (_u16(v, 7) << 16))
        for e in _fx_by_id(vm.g, v[1]):
            e.x, e.y, e.z = x, y, z
    return 9


@op(0xA2)
def _fx_spawn_at(vm, lg, ow, v, st, row):     # 0x800419FC
    e = _spawn_map_effect(vm.g, v[1], 1)
    if e is not None:
        e.x = _s32(_u16(v, 2) << 16)
        e.y = _s32(_u16(v, 4) << 16)
        e.z = _s32((_u16(v, 6) << 16) + 1)
    return 8


@op(0xA3)
def _fx_spawn_sel(vm, lg, ow, v, st, row):    # 0x80041AA8
    s = _sel(vm, lg, v[2])
    if s:
        t = s[0]                                         # read before the spawn
        e = _spawn_map_effect(vm.g, v[1], 1)
        if e is not None:
            e.x = _s32(t.px + (_u16(v, 3) << 16))
            e.y = _s32(t.py + (_u16(v, 5) << 16))
            e.z = _s32(t.pz + (_u16(v, 7) << 16))        # no +1 here
    return 9


# ------------------------------------------------------------- map lining --
class LiningSeq:
    """Lining draw mask and palette sequence (0x8005F814 / 0x8005D988 globals)."""
    def __init__(self):
        self.mask = 3        # 0x801E5F30: bit 0 draws lining layer 0, bit 1 layer 1
        self.seq = 0         # 0x80152BD8: palette sequence 1..n, 0 = none
        self.step = 1        # 0x800C6770: entry 1..16
        self.pal_add = 0     # 0x800C6774: added to every lining piece's palette (CLUT row)
        self.timer = 2       # 0x800C6778
        self.pos = 0         # 0x801E634C as an index into the table


def lining_seq(g):
    s = getattr(g, 'lining_seq', None)
    if s is None:
        s = g.lining_seq = LiningSeq()
    return s


def lining_reset(g):
    """Map load 0x8005D818: 0x8005F814(3, 0), pal_add = 0, timer = 2."""
    s = lining_seq(g)
    s.mask, s.seq, s.step, s.pal_add, s.timer = 3, 0, 1, 0, 2


def lining_palette_tick(g, table):
    """0x8005D988, once per drawn frame while the lining is enabled (header +0x1C) and seq != 0.
    table = bytes of the lining section at its u32 +0x14 offset (16 bytes per sequence;
    byte: palette add << 5 | hold).  Not exported yet (tools/remake_export_lining.py 'overlay_ext')."""
    s = lining_seq(g)
    if not s.seq: return 0
    b = table[s.pos] if s.pos < len(table) else 0
    t = s.timer; s.timer = t + 1
    s.pal_add = b >> 5
    if (b & 0x1F) < t:
        s.pos += 1; s.timer = 2
        old = s.step; s.step = old + 1
        if old >= 0x10:
            s.step = 1; s.pos = (s.seq - 1) * 16
    return s.pal_add


@op(0xA4)
def _lining_mode(vm, lg, ow, v, st, row):     # 0x80041B94 -> 0x8005F814(v1, v2)
    g = vm.g
    s = lining_seq(g)
    s.mask = v[1]
    s.seq = v[2]
    s.step = 1
    s.pal_add = 0
    if v[2] > 0:
        s.pos = (v[2] - 1) * 16
    ln = getattr(g.map, 'lining', None)
    if ln is not None and getattr(ln, 'ok', False):
        ln.mode_mask = v[1]
    return 3


# ------------------------------------------------------------ sound / music --
@op(0xA5)
def _music_play(vm, lg, ow, v, st, row):      # 0x80041BC4 -> 0x8004AC90
    """Start the loaded music at full volume (cancels a running fade-out)."""
    _hook(vm, 'music_play')
    return 1


@op(0xA6)
def _music_stop(vm, lg, ow, v, st, row):      # 0x80041BE4 -> 0x8004AD18(v1)
    """v1 != 0: 120-frame fade timer (fade out, stop at 60, volume back at 3; no new sound
    effects start while it runs); v1 == 0: SsSeqStop now.  Both cancel a pending auto-play."""
    _hook(vm, 'music_stop', v[1] != 0)
    return 2


@op(0xA7)
def _music_load(vm, lg, ow, v, st, row):      # 0x80041C10 -> 0x8004C380(v1, v2)
    """v1 == 0: stop + close the sequence and its VAB (music id = 0).
    v1 != 0: load track v1 (VAB + SEQ, 0x8004AD80); v2 != 0 also starts it (0x8004AC90).
    While an XA stream is active the load is deferred and A8 reports it pending."""
    if v[1] == 0:
        _hook(vm, 'music_unload')
    else:
        _hook(vm, 'music_load', v[1], v[2] != 0)
    return 3


@op(0xA8)
def _music_loading(vm, lg, ow, v, st, row):   # 0x80041C40 -> 0x8004C370
    st.result = 1 if getattr(vm.g, 'music_loading', None) and vm.g.music_loading() else 0
    return 1


@op(0xAB)
def _sfx_volume8(vm, lg, ow, v, st, row):     # 0x80041D8C -> 0x8004A928(v1, v2, v3)
    """Volume of the voices already playing sound effect v1: left v2, right v3 (0..127)."""
    _hook(vm, 'sound_volume', v[1], v[2], v[3])
    return 4


@op(0xBE)
def _sfx_stop16(vm, lg, ow, v, st, row):      # 0x800427C0 -> 0x8004A7B4(u16)
    _hook(vm, 'stop_sound', _u16(v, 1))
    return 3


@op(0xBF)
def _sfx_volume16(vm, lg, ow, v, st, row):    # 0x800427F4 -> 0x8004A928(u16, v3, v4)
    _hook(vm, 'sound_volume', _u16(v, 1), v[3], v[4])
    return 5


@op(0xB9)
def _xa_play(vm, lg, ow, v, st, row):         # 0x8004255C -> 0x8005CB94(v1)
    """XA audio clip v1 (table 0x800C6680, 12 bytes: sector, channel, length); ignored when
    XA is off or a music load is pending."""
    _hook(vm, 'xa_play', v[1])
    return 2


@op(0xBA)
def _xa_busy(vm, lg, ow, v, st, row):         # 0x80042588 -> 0x8005C990
    st.result = 1 if getattr(vm.g, 'xa_busy', None) and vm.g.xa_busy() else 0
    return 1


# ------------------------------------------------------------------ shadow --
@op(0xAC)
def _shadow(vm, lg, ow, v, st, row):          # 0x80041DC0
    """First selected entity: flags bits 16-18 (shadow size) = v2 & 7."""
    s = _sel(vm, lg, v[1])
    if s:
        e = s[0]
        e.flags = (e.flags & ~0x70000) | ((v[2] << 16) & 0x70000)
    return 4


@op(0xAE)
def _unimplemented(vm, lg, ow, v, st, row):   # 0x80041FBC
    _fatal(vm, 'No.171 is not implemented yet.')   # printf, then SystemErrorExit(1)
    return 0


# ------------------------------------------------------------------- fades --
# the fade state, its steps and its tick are engine/screen.py's (0x80043554-0x80043974)
from engine.screen import FadeState, fade_state, approach as _approach, fade_tick   # noqa: F401


def _fade_steps(vm, f, frames):
    if frames == 0:                                   # div by zero: break 7 on the PS1
        vm.note('fade with 0 frames (the game crashes)'); frames = 1
    f.step = [_div(_s32(t - c), frames) for t, c in zip(f.target, f.cur)]


@op(0xAF)
def _fade(vm, lg, ow, v, st, row):            # 0x80041FEC -> 0x80043628(v4, v5)
    """Overlay from its current colour to (v1, v2, v3) in v5 frames, blend abr v4
    (0 = B/2+F/2, 1 = B+F, 2 = B-F, 3 = B+F/4); v6 != 0 keeps drawing it once reached."""
    f = fade_state(vm.g, 'fade_ov')
    f.target = [v[1] << 16, v[2] << 16, v[3] << 16]
    f.on = 1
    f.keep = v[6]
    # 0x80043628(v4, v5): the overlay's DR_MODE from the page table 0x801F2E10[v4 * 0x2C] (so
    # its blend), and its steps.  Scripts also pass blends past the table's 4 rows (the ship
    # dream's flashes: 0x64), which read a zero word there: a 50% mix, a pale flash
    from engine.screen import ov_steps
    ov_steps(vm.g, v[4], v[5])
    return 7


@op(0xB0)
def _bg_fade(vm, lg, ow, v, st, row):         # 0x80042090 -> 0x800437F4(v4)
    """Screen clear (background) colour from its current value to (v1, v2, v3) in v4 frames."""
    f = fade_state(vm.g, 'fade_bg')
    f.target = [v[1] << 16, v[2] << 16, v[3] << 16]
    f.on = 1
    _fade_steps(vm, f, v[4])
    return 5


@op(0xB1)
def _fade_done(vm, lg, ow, v, st, row):       # 0x80042118
    g = vm.g
    busy = fade_state(g, 'fade_ov').on or fade_state(g, 'fade_bg').on
    st.result = 0 if busy else 1
    return 1


# --------------------------------------------------------------------- pad --
@op(0xB3)
def _pad_set(vm, lg, ow, v, st, row):         # 0x8004227C
    """Overwrites pad 1 (0x801DDA38 +0x10..+0x16) for the rest of this frame; the next read
    (0x8002E5BC) takes this 'held' as the previous state for its pressed/released edges."""
    g = vm.g
    g.pad_held = _u16(v, 1)                           # 0x801DDA48
    g.pad_pressed = _u16(v, 3)                        # 0x801DDA4A
    g.pad_released = _u16(v, 5)                       # 0x801DDA4C
    g.pad_repeat = _u16(v, 7)                         # 0x801DDA4E
    g.pad_forced = None
    return 9


# --------------------------------------------------------------- game over --
def revive_burst(g, e):
    """0x80034124(e): e.hp = e.hp_max, MP = max, sparkles (global effect 0xE) around slot 0.
    Uses the game RNG (2 numbers per random sparkle that got an effect record)."""
    from engine import core
    import physics
    e.hp = e.hp_max                                   # Entity+0x14 = +0x18
    _mp_full(g)                                       # 0x8004F540(0x8004F45C())
    p = g.slots[0]
    tx, ty = physics.OFFSET_X, physics.OFFSET_Y       # s16[32] at 0x80023654 / 0x80023694
    d = 8
    for i in range(8):
        fx = core.spawn_effect(g, 0, 0xE, 2 if (i & 1) == 0 else 0, p.px, p.py, _s32(p.pz + 0x80000))
        if fx is not None:
            k = d & 0x1F
            fx.vz = 0x30000
            fx.x = _s32(fx.x + (tx[4 * i] << 11)); fx.y = _s32(fx.y + (ty[4 * i] << 11))
            fx.vx = tx[k] * 0x1C0; fx.vy = ty[k] * 0x1C0
        d += 4
    for i in range(4):
        for sub, vz in ((0, 0x40000), (2, 0x20000)):
            fx = core.spawn_effect(g, 0, 0xE, sub, p.px, p.py, _s32(p.pz + 0x100000))
            if fx is not None:
                fx.vz = vz
                fx.vx = _s32(core.rnd(g, 0x20001) - 0x10000)
                fx.vy = _s32(core.rnd(g, 0x30001) - 0x18000)


@op(0xBB)
def _game_over(vm, lg, ow, v, st, row):       # 0x800425B8
    g = vm.g
    if getattr(g, 'cur_map', g.map.id) != 0x1DD:      # not map 477: the ending
        g.warp_request = 1; g.warp_effect = 9; g.warp_sound = 0       # LoadExec END.EXE
        return 1
    if g.flag(0x8001):                                # word 0x801E6378 bit 1
        g.warp_request = 1; g.warp_sound = 0; g.warp_effect = 0xB     # LoadExec title
        return 1
    if st.params[1] != st.ci:                         # ctx+8 != pc: first frame
        revive_burst(g, g.slots[0])
        _hook(vm, 'sound', 0x31)                      # 0x8004A128(0x31)
        st.params[2] = 0                              # ctx+0xC
        st.params[1] = st.ci
        return 0
    n = st.params[2]; st.params[2] = n + 1            # debug text 'Retry = %d' skipped
    if n >= 0x3C:
        g.warp_request = 1; g.warp_effect = 0xA; g.warp_sound = 0; g.warp_map = 0xB   # retry
        return 1
    return 0


# ----------------------------------------------------- player / equipment --
def _mp_full(g):
    """0x8004F540(0x8004F45C()): stats magic (+4) = most magic (+6), 0 if that is negative.
    Writes g.mem (what the HUD and engine read), not the unused g.player.mp (2026-10-21)."""
    from engine import menu as emenu
    emenu.magic_set(g, g.mem.s16(emenu._stats(g) + 6))


@op(0xC0)
def _weapon_force(vm, lg, ow, v, st, row):    # 0x80042830
    k = v[1] + 1                                      # 0x8004FB28(v1 + 1)
    if 1 <= k <= 6:
        vm.g.weapon_kind = k                          # resource +0xA (0x801DD826)
    else:
        vm.note(f'C0 weapon kind {k} rejected')       # game prints an error, +0xA unchanged
    vm.g.mode_flags |= 0x80
    return 2


@op(0xC1)
def _weapon_release(vm, lg, ow, v, st, row):  # 0x80042874
    vm.g.mode_flags &= ~0x80
    return 1


@op(0xC2)
def _retries(vm, lg, ow, v, st, row):         # 0x80042894
    """Result = retry count (u8 0x801DDA2E = saved block 0x801DD2D8 + 0x756) >= v1."""
    st.result = 1 if vm.g.mem.u8(0x801DDA2E) >= v[1] else 0   # (counted by the retry, 0x80031B50)
    if (getattr(vm.g, 'settings', None) or {}).get('no_death_lsword'): st.result = 1   # Mods > No Death L.Sword (King Snow, map 7)
    return 2


@op(0xC3)
def _restore(vm, lg, ow, v, st, row):         # 0x800428D0
    p = vm.g.player
    p.hp = p.hp_max                                   # slot 0: +0x14 = +0x18
    _mp_full(vm.g)
    if getattr(vm.g, 'hud_sync', None): vm.g.hud_sync()   # 0x8004CA2C (HUD counters = max)
    return 1


# ----------------------------------------------------------------- message --
@op(0xC4)
def _msg_named(vm, lg, ow, v, st, row):       # 0x80042910
    """v1 speaker selector, v2|v3<<8 name (catalogue 0x100-0x1FF), v4 text (bit 7 = map bank),
    v5 == 1: the box freezes Alundra (mode flag 0x10), else mode flag 8.  Yields while a box is open
    (portrait and name are set up again every frame)."""
    g = vm.g
    s = _sel(vm, lg, v[1])
    sp = s[0] if s else None
    if sp is not None:
        if sp.flags & 0x800000 and getattr(g, 'message_portrait', None):
            g.message_portrait(sp)                    # 0x80059AE4
        if getattr(g, 'message_name', None):
            g.message_name(_u16(v, 2))                # 0x8005C0A8
    start = getattr(g, 'msg_start', None)
    if start is not None: return 6 if start(v[4], v[5]) else 0   # 0x80042F74(v4, v5)
    return 6 if g.open_message(row, sp, v[5]) else 0


# ------------------------------------------------------------------- docs --
DOC_FIX = {
    0xA1: 'Move map effect to first selected entity + offset',
    0xA2: 'Spawn map effect record at x,y,z (no area test)',
    0xA3: 'Spawn map effect record at first selected + offset (no area test)',
    0xA4: 'Lining layers shown (mask) and palette sequence',
    0xA5: 'Play loaded music at full volume',
    0xA6: 'Stop music (1 = fade out, 0 = now)',
    0xA7: 'Load music track (0 = unload; 2nd byte: play now)',
    0xA8: 'Result = music load pending',
    0xAB: 'Set volume of a playing sound (8-bit id, left, right)',
    0xAC: 'Shadow size of first selected',
    0xAD: 'Result = selected inside box around first of another',
    0xAE: 'Unimplemented (game halts)',
    0xAF: 'Fade screen overlay to colour (r,g,b, blend, frames, keep)',
    0xB0: 'Fade background clear colour (r,g,b, frames)',
    0xB1: 'Result = both colour fades finished',
    0xB4: 'Result = first selected rising', 0xB5: 'Result = first selected falling',
    0xB6: 'Result = first selected vertical force 0',
    0xB9: 'Play XA audio clip', 0xBA: 'Result = XA clip playing',
    0xBB: 'Ending / game over retry (map 477)',
    0xBC: 'Raise max life (max 50)',
    0xBD: 'Play sound (16-bit id)', 0xBE: 'Stop sound (16-bit id)',
    0xBF: 'Set volume of a playing sound (16-bit id, left, right)',
    0xC0: 'Force weapon kind', 0xC1: 'Release forced weapon',
    0xC2: 'Result = retry count >= n', 0xC3: 'Restore life and magic',
    0xC4: 'Show message with chosen speaker and name',
}
DOC.update(DOC_FIX)
