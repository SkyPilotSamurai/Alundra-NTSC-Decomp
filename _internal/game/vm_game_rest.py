"""Event-script opcodes written from the US v1.1 ALUN_CD.EXE handlers (table 0x8009B814; decompiled
C in research/us_decomp/vm_ops/h_<address>.c): the opcodes the other vm_game_*.py files do not
already cover.  Same convention as vm.py: handler(vm, lg, ow, v, st, row) -> byte advance (0 = stay
on this instruction next frame).  lg = the logic entity (a0), ow = the running entity (a1), v = the
instruction bytes (v[0] the opcode), st = the program context a3: st.params[0] = +0 (program start),
st.params[1] = +8 (the pc a waiting instruction started on), st.params[2] / [3] = +0xC / +0x10,
st.result = +0x2C, st.r30 = +0x30 (loop count), st.r34 = +0x34 (return pc).
Game flags: operand n -> word (n >> 5) of 0x801DD334 (n < 0x8000) or 0x801E6378 (n & 0x8000), bit
n & 31 (Game.flag / Game.set_flag)."""
M32 = 0xFFFFFFFF
QUAD_DIR = (0, 16, 8, 24)                   # s32[4] at 0x80023644: down, up, left, right

HANDLERS = {}


def op(*codes):
    def deco(fn):
        for c in codes: HANDLERS[c] = fn
        return fn
    return deco


def _u16(v, i): return v[i] | v[i + 1] << 8


def _s16(v, i):
    x = _u16(v, i)
    return x - 0x10000 if x & 0x8000 else x


def _s32(x):
    x &= M32
    return x - 0x100000000 if x & 0x80000000 else x


def _flag(vm, v, i=1): return bool(vm.g.flag(_u16(v, i)))


def _sel(vm, lg, s): return vm.select(lg, s)        # 0x8003D374 (vm_game_00.select_faithful): slot order


def _started(st):
    """ctx+8 != pc: a waiting instruction's first frame (ctx+8 = pc)."""
    if st.params[1] != st.ci:
        st.params[1] = st.ci; return True
    return False


# --------------------------------------------------------------------------- jumps, flags
@op(0x02)                                   # 0x8003DBF8
def _jump(vm, lg, ow, v, st, row): return _s16(v, 1)

@op(0x03)                                   # 0x8003DC1C
def _jump_t(vm, lg, ow, v, st, row): return _s16(v, 1) if st.result else 3

@op(0x04)                                   # 0x8003DC54
def _jump_f(vm, lg, ow, v, st, row): return 3 if st.result else _s16(v, 1)

@op(0x05)                                   # 0x8003DC8C
def _flag_set(vm, lg, ow, v, st, row): vm.g.set_flag(_u16(v, 1), True); return 3

@op(0x06)                                   # 0x8003DD04
def _flag_clear(vm, lg, ow, v, st, row): vm.g.set_flag(_u16(v, 1), False); return 3

@op(0x30)                                   # 0x8003E864
def _jump_flag_set(vm, lg, ow, v, st, row): return _s16(v, 3) if _flag(vm, v) else 5

@op(0x31)                                   # 0x8003E8F4
def _jump_flag_clear(vm, lg, ow, v, st, row): return 5 if _flag(vm, v) else _s16(v, 3)

@op(0x32)                                   # 0x8003E984
def _flag_toggle(vm, lg, ow, v, st, row):
    n = _u16(v, 1); vm.g.set_flag(n, not vm.g.flag(n)); return 3

@op(0x33)                                   # 0x8003E9FC: all four flags set
def _flags_all(vm, lg, ow, v, st, row):
    st.result = int(all(_flag(vm, v, 1 + 2 * k) for k in range(4))); return 9

@op(0x34)                                   # 0x8003EBB0: all four flags clear
def _flags_none(vm, lg, ow, v, st, row):
    st.result = int(not any(_flag(vm, v, 1 + 2 * k) for k in range(4))); return 9

@op(0x35)                                   # 0x8003ED64
def _wait_flag_clear(vm, lg, ow, v, st, row): return 0 if _flag(vm, v) else 3

@op(0x36)                                   # 0x8003EDE0
def _wait_flag_set(vm, lg, ow, v, st, row): return 3 if _flag(vm, v) else 0

@op(0x49)                                   # 0x8003F480: back to the program's start
def _restart(vm, lg, ow, v, st, row): return st.params[0] - st.ci

@op(0x4A)                                   # 0x8003F490
def _restart_t(vm, lg, ow, v, st, row): return st.params[0] - st.ci if st.result else 1

@op(0x4B)                                   # 0x8003F4B8
def _restart_f(vm, lg, ow, v, st, row): return 1 if st.result else st.params[0] - st.ci

@op(0x73)                                   # 0x80040518
def _loop_count(vm, lg, ow, v, st, row): st.r30 = v[1]; return 2

@op(0x74)                                   # 0x80040534
def _loop(vm, lg, ow, v, st, row):
    st.r30 -= 1
    return 3 if st.r30 <= 0 else _s16(v, 1)

@op(0x78)                                   # 0x800405F4
def _call(vm, lg, ow, v, st, row): st.r34 = st.ci + 3; return _s16(v, 1)

@op(0x79)                                   # 0x80040628
def _call_t(vm, lg, ow, v, st, row):
    if not st.result: return 3
    st.r34 = st.ci + 3; return _s16(v, 1)

@op(0x7A)                                   # 0x80040670
def _call_f(vm, lg, ow, v, st, row):
    if st.result: return 3
    st.r34 = st.ci + 3; return _s16(v, 1)

@op(0x7B)                                   # 0x800406B8
def _call_flag_set(vm, lg, ow, v, st, row):
    if not _flag(vm, v): return 5
    st.r34 = st.ci + 5; return _s16(v, 3)

@op(0x7C)                                   # 0x8004075C
def _call_flag_clear(vm, lg, ow, v, st, row):
    if _flag(vm, v): return 5
    st.r34 = st.ci + 5; return _s16(v, 3)

@op(0x7D)                                   # 0x800407FC
def _return(vm, lg, ow, v, st, row): return st.r34 - st.ci

@op(0x7E)                                   # 0x8004080C
def _return_t(vm, lg, ow, v, st, row): return st.r34 - st.ci if st.result else 1

@op(0x7F)                                   # 0x80040834
def _return_f(vm, lg, ow, v, st, row): return 1 if st.result else st.r34 - st.ci

@op(0x80)                                   # 0x8004085C
def _return_flag_set(vm, lg, ow, v, st, row): return st.r34 - st.ci if _flag(vm, v) else 3

@op(0x81)                                   # 0x800408E0
def _return_flag_clear(vm, lg, ow, v, st, row): return 3 if _flag(vm, v) else st.r34 - st.ci


# --------------------------------------------------------------------------- the logic entity
@op(0x08)                                   # 0x8003DE80
def _turn_by(vm, lg, ow, v, st, row): lg.target_dir = (lg.target_dir + v[1]) & 31; return 2

@op(0x09)                                   # 0x8003DEA8
def _face(vm, lg, ow, v, st, row): lg.target_dir = v[1] & 31; return 2

@op(0x0A)                                   # 0x8003DEC8
def _about_face(vm, lg, ow, v, st, row): lg.target_dir = (lg.target_dir + 16) & 31; return 1

@op(0x3A)                                   # 0x8003EF10
def _face_quadrant(vm, lg, ow, v, st, row): lg.target_dir = QUAD_DIR[v[1] & 3]; return 2

@op(0x1A)                                   # 0x8003E230
def _anim(vm, lg, ow, v, st, row): lg.target_anim = v[1]; return 2

@op(0x1B)                                   # 0x8003E24C: +0xB8 = (s16 << 16) >> 8
def _zforce(vm, lg, ow, v, st, row): lg.fz = _s32(_s16(v, 1) << 16) >> 8; return 3


def _moved(vm, lg, st, dist):
    """0x8003DEE4 / 0x8003E354: on the first frame keep +0x114 / +0x118; then True once either has
    moved by dist pixels or more (|a - b| >> 16, signed compare)."""
    if _started(st):
        st.params[2], st.params[3] = lg.px, lg.py; return False
    dx = abs(_s32(st.params[2] - lg.px)) >> 16; dy = abs(_s32(st.params[3] - lg.py)) >> 16
    return dx >= dist or dy >= dist

@op(0x0B)                                   # 0x8003DEE4: animation, then wait until moved
def _walk(vm, lg, ow, v, st, row):
    lg.target_anim = v[1]
    return 4 if _moved(vm, lg, st, _u16(v, 2)) else 0

@op(0x1E)                                   # 0x8003E354
def _wait_moved(vm, lg, ow, v, st, row): return 3 if _moved(vm, lg, st, _u16(v, 1)) else 0

@op(0x15)                                   # 0x8003E188: height from the map record (byte 9 * 8 px)
def _record_z(vm, lg, ow, v, st, row):
    rec = getattr(lg, 'record', None)
    if rec is None: vm.note('15: no map record (0x8003D23C)'); return 0
    lg.pz = _s32((rec['z'] * 8) << 16)      # (z * 8 - +0x1EC) << 16: a whole-pixel +0x1EC drops out
    return 1

@op(0x16)                                   # 0x8003E1F0
def _gravity_on(vm, lg, ow, v, st, row): lg.flags |= 0x100; return 1

@op(0x17)                                   # 0x8003E208
def _gravity_off(vm, lg, ow, v, st, row): lg.flags &= ~0x100; return 1

@op(0x28)                                   # 0x8003E6A4
def _class_b_on(vm, lg, ow, v, st, row): lg.flags |= 8; return 1

@op(0x29)                                   # 0x8003E6BC
def _class_b_off(vm, lg, ow, v, st, row): lg.flags &= ~8; return 1

@op(0x2A)                                   # 0x8003E6D4
def _class_a_on(vm, lg, ow, v, st, row): lg.flags |= 1; return 1

@op(0x2B)                                   # 0x8003E6EC
def _class_a_off(vm, lg, ow, v, st, row): lg.flags &= ~1; return 1

@op(0x45)                                   # 0x8003F3F8
def _slide_on(vm, lg, ow, v, st, row): lg.flags &= ~0x2000; return 1

@op(0x46)                                   # 0x8003F410
def _slide_off(vm, lg, ow, v, st, row): lg.flags |= 0x2000; return 1

@op(0x24)                                   # 0x8003E5F0: +0x13C
def _wait_blocked(vm, lg, ow, v, st, row): return 1 if lg.force_adjusted else 0

@op(0x25)                                   # 0x8003E5FC: +0x140 or +0x144
def _wait_landed(vm, lg, ow, v, st, row): return 1 if lg.collided_z or lg.on_ground else 0

@op(0x26)                                   # 0x8003E628: +0x13C or +0x140
def _wait_blocked_z(vm, lg, ow, v, st, row): return 1 if lg.force_adjusted or lg.collided_z else 0

@op(0x6E)                                   # 0x800404B0
def _is_blocked(vm, lg, ow, v, st, row): st.result = int(bool(lg.force_adjusted)); return 1

@op(0x6F)                                   # 0x800404C4
def _is_landed_z(vm, lg, ow, v, st, row): st.result = int(bool(lg.collided_z)); return 1

@op(0x70)                                   # 0x800404D8
def _is_on_ground(vm, lg, ow, v, st, row): st.result = int(bool(lg.on_ground)); return 1

@op(0x3E)                                   # 0x8003F1B4: Alundra stands on the logic entity
def _player_rides(vm, lg, ow, v, st, row): st.result = int(vm.g.player.riding is lg); return 1

@op(0x42)                                   # 0x8003F2B4: the runner's logic entity = Alundra
def _logic_player(vm, lg, ow, v, st, row): ow.logic_ctx = vm.g.player; return 1


# --------------------------------------------------------------------------- selections
@op(0x2C)                                   # 0x8003E704
def _none_selected(vm, lg, ow, v, st, row): st.result = int(not _sel(vm, lg, v[1])); return 2

@op(0x43)                                   # 0x8003F2C8: the runner's logic entity = the last selected
def _logic_selected(vm, lg, ow, v, st, row):
    s = _sel(vm, lg, v[1])
    if not s: st.result = 0; return 2
    ow.logic_ctx = s[-1]; st.result = 1; return 2

@op(0x59)                                   # 0x8003F960
def _sel_anim(vm, lg, ow, v, st, row):
    for e in reversed(_sel(vm, lg, v[1])): e.target_anim = v[2]
    return 3

@op(0x5E)                                   # 0x8003FC70
def _sel_zforce(vm, lg, ow, v, st, row):
    f = _s32(_s16(v, 2) << 16) >> 8
    for e in reversed(_sel(vm, lg, v[1])): e.fz = f
    return 4

@op(0x60)                                   # 0x8003FEC8: one selected stands on the logic entity
def _sel_rides_me(vm, lg, ow, v, st, row):
    st.result = int(any(e.riding is lg for e in _sel(vm, lg, v[1]))); return 2

@op(0x61)                                   # 0x8003FF58: the logic entity stands on one selected
def _i_ride_sel(vm, lg, ow, v, st, row):
    st.result = int(any(lg.riding is e for e in _sel(vm, lg, v[1]))); return 2

@op(0x62)                                   # 0x8003FFE4
def _sel_flags_on(vm, lg, ow, v, st, row):
    for e in reversed(_sel(vm, lg, v[1])): e.flags |= _u16(v, 2)
    return 4

@op(0x63)                                   # 0x80040060: & (~u16 | 0xFFFF0000)
def _sel_flags_off(vm, lg, ow, v, st, row):
    for e in reversed(_sel(vm, lg, v[1])): e.flags &= ~_u16(v, 2)
    return 4

@op(0x65)                                   # 0x80040198: += operand << 16
def _sel_move(vm, lg, ow, v, st, row):
    dx, dy, dz = _s32(_u16(v, 2) << 16), _s32(_u16(v, 4) << 16), _s32(_u16(v, 6) << 16)
    for e in reversed(_sel(vm, lg, v[1])):
        e.px = _s32(e.px + dx); e.pz = _s32(e.pz + dz); e.py = _s32(e.py + dy)
    return 8

@op(0xA9)                                   # 0x80041C70: the logic entity bumped one selected (+0x130)
def _i_bumped_sel(vm, lg, ow, v, st, row):
    st.result = int(any(lg.bumped is e for e in _sel(vm, lg, v[1]))); return 2

@op(0xAA)                                   # 0x80041CFC: one selected bumped the logic entity
def _sel_bumped_me(vm, lg, ow, v, st, row):
    st.result = int(any(e.bumped is lg for e in _sel(vm, lg, v[1]))); return 2

@op(0xAD)                                   # 0x80041E44: one of group 2 inside the box (signed
def _sel_in_box(vm, lg, ow, v, st, row):    # squares from the first of group 1, then a size)
    base = _sel(vm, lg, v[1])
    if not base: st.result = 0; return 9
    b = base[0]; sb = lambda x: x - 256 if x & 0x80 else x
    x0 = b.px + sb(v[3]) * 0x180000; y0 = b.py + (sb(v[4]) << 20); z0 = b.pz + (sb(v[5]) << 20)
    x1 = x0 + v[6] * 0x180000; y1 = y0 + (v[7] << 20); z1 = z0 + (v[8] << 20)
    st.result = int(any(x0 <= e.px <= x1 and y0 <= e.py <= y1 and z0 <= e.pz <= z1
                        for e in _sel(vm, lg, v[2])))
    return 9

@op(0xB2)                                   # 0x80042154: an entity in both selections
def _sel_overlap(vm, lg, ow, v, st, row):
    a = _sel(vm, lg, v[1])
    if not a: st.result = 0; return 3
    st.result = int(any(e in a for e in _sel(vm, lg, v[2]))); return 3

@op(0xB4)                                   # 0x80042304: the first selected rises (+0xB8 > 0)
def _sel_rising(vm, lg, ow, v, st, row):
    s = _sel(vm, lg, v[1]); st.result = int(bool(s) and s[0].fz > 0); return 2

@op(0xB5)                                   # 0x8004236C
def _sel_falling(vm, lg, ow, v, st, row):
    s = _sel(vm, lg, v[1]); st.result = int(bool(s) and s[0].fz < 0); return 2

@op(0xB6)                                   # 0x800423D4
def _sel_still(vm, lg, ow, v, st, row):
    s = _sel(vm, lg, v[1]); st.result = int(bool(s) and s[0].fz == 0); return 2

@op(0xB7)                                   # 0x8004243C: +0x88
def _sel_target_anim(vm, lg, ow, v, st, row):
    st.result = int(any(e.target_anim == v[2] for e in _sel(vm, lg, v[1]))); return 3

@op(0xB8)                                   # 0x800424CC: +0x90
def _sel_cur_anim(vm, lg, ow, v, st, row):
    st.result = int(any(e.anim.anim == v[2] for e in _sel(vm, lg, v[1]))); return 3


# --------------------------------------------------------------------------- the map, the camera
def _clamp_square(x, y): return (0 if x <= 0 else min(x, 0x33)), (0 if y <= 0 else min(y, 0x3B))

@op(0x54)                                   # 0x8003F788: square word |= u16
def _square_or(vm, lg, ow, v, st, row):
    c = vm.g.map.cell(*_clamp_square(v[1], v[2]))
    if c: c[0] |= v[3]; c[1] |= v[4]
    return 5

@op(0x55)                                   # 0x8003F82C: square word &= ~u16
def _square_andnot(vm, lg, ow, v, st, row):
    c = vm.g.map.cell(*_clamp_square(v[1], v[2]))
    if c: c[0] &= ~v[3] & 0xFF; c[1] &= ~v[4] & 0xFF
    return 5

@op(0x56)                                   # 0x8003F8D0 -> 0x8002DB14: a map area copy record
def _map_copy(vm, lg, ow, v, st, row): vm.g.map.apply_copy(v[1]); return 2

@op(0x69)                                   # 0x80040348: 0x801EFE54 = 0, look at (x, y, z)
def _camera_at(vm, lg, ow, v, st, row):
    vm.g.camera_follow = False; vm.g.camera_at = (_u16(v, 1), _u16(v, 3), _u16(v, 5)); return 7

@op(0x8E)                                   # 0x80041038: shake on (+0xC, +0x10 steps, +4, +8 limits)
def _shake_on(vm, lg, ow, v, st, row):
    m = vm.g.mem; S = 0x801F94D0
    m.w32(S, 1); m.w32(S + 0xC, v[1]); m.w32(S + 0x10, v[2]); m.w32(S + 4, v[3]); m.w32(S + 8, v[4]); return 5

@op(0x8F)                                   # 0x8004109C
def _shake_off(vm, lg, ow, v, st, row): vm.g.mem.w32(0x801F94D0, 0); return 1


# --------------------------------------------------------------------------- effects (128 records)
@op(0x91)                                   # 0x800410D8: records with this map id end
def _effect_end(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): e.dead = True
    return 2

@op(0x92)                                   # 0x80041128: their animation byte
def _effect_anim(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): vm.g.effects.set_anim(e, v[2])
    return 3

@op(0xA0)                                   # 0x80041860: += operand << 16
def _effect_move(vm, lg, ow, v, st, row):
    dx, dy, dz = _s32(_u16(v, 2) << 16), _s32(_u16(v, 4) << 16), _s32(_u16(v, 6) << 16)
    for e in vm.g.effects.by_id(v[1]): e.x += dx; e.y += dy; e.z += dz
    return 8


# --------------------------------------------------------------------------- waits, items, life
@op(0x37)                                   # 0x8003EE5C: wait v1 frames
def _wait(vm, lg, ow, v, st, row):
    if _started(st): st.params[2] = 0; return 0
    n = st.params[2]; st.params[2] = n + 1
    return 2 if n >= v[1] else 0

@op(0x39)                                   # 0x8003EEF0: until 0x80043008 (a message open) is 0
def _wait_message(vm, lg, ow, v, st, row): return 1 if vm.g.dialogue is None else 0

@op(0x83)                                   # 0x800409B0: 0x8004FAC4(item) >= count
def _have_items(vm, lg, ow, v, st, row): st.result = int(vm.g.inventory.get(v[1], 0) >= v[2]); return 3

@op(0xBC)                                   # 0x80042750: Life maximum + n, at most 50
def _life_max_up(vm, lg, ow, v, st, row):
    p = vm.g.player; p.hp_max = min(0x32, p.hp_max + v[1]); return 2


# --------------------------------------------------------------------------- sounds, script errors
@op(0x12)                                   # 0x8003E134: 0x8004A128(u8)
def _sound8(vm, lg, ow, v, st, row): vm.g.sound(v[1]); return 2

@op(0xBD)                                   # 0x8004278C: 0x8004A128(u16)
def _sound16(vm, lg, ow, v, st, row): vm.g.sound(_u16(v, 1)); return 3

@op(0x20)                                   # 0x8003E438: until +0x11C has moved by v pixels
def _wait_z(vm, lg, ow, v, st, row):
    if _started(st): st.params[2] = lg.pz; return 0
    return 3 if abs(_s32(st.params[2] - lg.pz)) >> 16 >= _u16(v, 1) else 0


def _script_error(code, msg):
    def f(vm, lg, ow, v, st, row):
        fatal = getattr(vm.g, 'fatal', None)
        if fatal: fatal(msg)
        else: vm.note(f'{code:02X}: {msg}')
        return 0                            # 0x8003D23C stops the console; the program stays here
    return f

for _c, _a, _m in ((0x01, 0x8003DBD0, 'invalid command'), (0x13, 0x8003DBD0, 'invalid command'),
                   (0x18, 0x8003DBD0, 'invalid command'), (0x14, 0x8003E160, 'script error'),
                   (0x76, 0x800405A4, 'script error'), (0x77, 0x800405CC, 'script error')):
    HANDLERS[_c] = _script_error(_c, f'{_m} ({_a:#010x} -> 0x8003D23C)')


def install(vm_module):
    vm_module.HANDLERS.update(HANDLERS)
