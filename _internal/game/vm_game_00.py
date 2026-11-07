"""Event-script opcodes 0x00-0x2F (US ALUN_CD.EXE, SLUS-00553): faithful replacements for the
remake/vm.py handlers marked WRONG in audit_00_2F.md, and select_faithful(), a replacement for
VM.select that does what the game's selection function 0x8003D374 does.

Convention (as remake/vm.py): handler(vm, lg, ow, v, st, row) -> byte advance, 0 = yield.
lg = logic entity (Entity+0x230 of the runner), ow = running entity, v = instruction bytes
(v[0] = opcode, operands from v[1]), st = ProgState.  Context words used here:
    st.params[1] = ctx+0x08 (pc a waiting instruction started on; zeroed by vm.run on advance)
    st.params[2] = ctx+0x0C, st.params[3] = ctx+0x10, st.result = ctx+0x2C (Result)
Entity values are the remake's 16.16 integers (px py pz fz), never the float views wx/wy/z/vz.
install(vm_module) puts these handlers and select_faithful into a loaded remake/vm.py.
"""

M32 = 0xFFFFFFFF
QUAD_DIR = (0x00, 0x10, 0x08, 0x18)          # s32[4] at 0x80023644 (down, up, left, right)
PAD_REPEAT_DELAY, PAD_REPEAT_INTERVAL = 20, 0  # 0x801DDA38 / 0x801DDA3C as set by 0x8002E6C4

HANDLERS = {}


def op(*codes):
    def deco(fn):
        for c in codes: HANDLERS[c] = fn
        return fn
    return deco


def _s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def _abs_px(a, b):
    """subu, abs (negu), sra 16 as the wait handlers do: |a - b| in whole pixels (signed)."""
    d = _s32(a - b)
    if d < 0: d = _s32(-d)
    return d >> 16


def _fatal(vm, msg):
    """0x8003D23C: prints map / entity / command, then BIOS exit(1): the game stops."""
    f = getattr(vm.g, 'fatal', None)
    if f is not None: f(msg)
    else: vm.note('fatal: ' + msg)


def _hook(g, name, *args):
    f = getattr(g, name, None)
    return f(*args) if f is not None else None


def _first(st):
    """ctx+8 != pc: first run of a waiting instruction; ctx+8 = pc."""
    if st.params[1] != st.ci:
        st.params[1] = st.ci
        return True
    return False


# ------------------------------------------------------------ entity selection --
def _st123(e):
    return e is not None and 1 <= e.estatus <= 3          # (status - 1) < 2 unsigned, or == 3


def _record_ok(g, ref):
    """0x8003A4C0: ref < record count (0x801F2ED4) and record byte 4 ('enabled') != 0."""
    recs = g.map.doc.get('entities', [])
    return 0 <= ref < len(recs) and recs[ref].get('enabled', 1) != 0


def select_faithful(vm, logic, sel):
    """0x8003D374(logic, sel): the entities in slot order (the list at 0x8013D488).
    Handlers that loop over it walk from the LAST entry down to the first."""
    g = vm.g; ent = g.slots; n = g.count                    # g_ent_count 0x801D93EC
    sel &= 0xFF
    if not sel & 0x80:                                      # map record (ref_id) number
        if not _record_ok(g, sel):                          # 0x8003D330
            _fatal(vm, 'Illegal InitData Number!!'); return []
        if not _st123(logic): return []                     # the game tests the LOGIC entity's status
        return [e for e in ent[1:n + 1] if e is not None and e.ref_id == sel]
    f = sel & 0x7F
    if f == 0: return [logic]
    if f == 1: return [ent[0]]
    if f == 2: return [e for e in ent[0:n + 1] if _st123(e)]
    if f == 3: return [e for e in ent[1:n + 1] if _st123(e)]
    if f == 4:                                              # again the LOGIC entity's status
        if not _st123(logic): return []
        return [e for e in ent[0:n + 1] if e is not None and e.flags & 0x80
                and not e.anim_flags & 0x80 and e.holder is None]
    if f > 0x0B:
        _fatal(vm, 'Illegal Distination!'); return []
    test = {
        5: lambda e: logic.riding is e,                     # +0x12C
        6: lambda e: e.riding is logic,
        7: lambda e: logic.x_collision is e,                # +0x130
        8: lambda e: e.x_collision is logic,
        9: lambda e: e.parent is logic,                     # +0x0C
        10: lambda e: logic.parent is e,
        11: lambda e: e.holder is not None,                 # +0x28 (being carried)
    }[f]
    return [e for e in ent[1:n + 1] if _st123(e) and test(e)]


# ------------------------------------------------------------------- handlers --
@op(0x07)
def _boxsel(vm, lg, ow, v, st, row):        # 0x8003DD84
    x1, x2, y1, y2, z1, z2 = v[2:8]
    for e in reversed(select_faithful(vm, lg, v[1])):     # last entry first, stops at a hit
        if x1 <= e.tile_x <= x2 and y1 <= e.tile_y <= y2 and z1 <= e.tile_z <= z2:   # +0x120/124/128
            st.result = 1
            return 8
    st.result = 0
    return 8


@op(0x0C)
def _rnddir(vm, lg, ow, v, st, row):        # 0x8003DF90
    import gamerng
    lg.target_dir = QUAD_DIR[gamerng.rnd(4)]               # seed advances; (seed * 4) >> 32
    return 1


@op(0x0D)
def _msg(vm, lg, ow, v, st, row):           # 0x8003DFF0
    g = vm.g
    if lg.flags & 0x800000:
        _hook(g, 'msg_speaker', lg)                         # 0x80059AE4 (runs again while waiting)
    _hook(g, 'msg_voice', getattr(lg, 'sprite_index', None) if getattr(lg, 'sprite_index', None) is not None else getattr(lg, 'balance_index', -1))  # 0x8005C0A8(Entity+0x68)
    start = getattr(g, 'msg_start', None)                   # 0x80042F74(v1, v2)
    if start is not None:
        return 3 if start(v[1], v[2]) else 0
    return 3 if g.open_message(row, lg, v[2]) else 0             # remake text path until ported


@op(0x10)
def _lock(vm, lg, ow, v, st, row):          # 0x8003E0F4
    vm.g.mode_flags |= 4                                    # g_mode_flags 0x801F0060
    vm.g.player_locked = True                               # remake mirror (its own checks)
    return 1


@op(0x11)
def _unlock(vm, lg, ow, v, st, row):        # 0x8003E114
    vm.g.mode_flags &= ~4
    vm.g.player_locked = False
    return 1


@op(0x19)
def _deact(vm, lg, ow, v, st, row):         # 0x8003E220: Entity+0x10 = 3, nothing else
    if lg.estatus == 4:                                     # destroyed this frame: no longer freed
        lg.alive = True; lg.active = True; lg.visible = True
    lg.estatus = 3; lg.status = 'deactivated'
    return 1


def _restart_anim(lg):
    """Entity+0x90 cur_anim = ~target_anim: UpdateAnimation 0x800393A4 restarts the animation.
    The remake's animate() compares Animator.anim with target_anim, so set that too."""
    lg.cur_anim = ~lg.target_anim
    a = getattr(lg, 'anim', None)
    if a is not None: a.anim = ~lg.target_anim


def _anim_count(lg, st, n):                 # 0x8003E278 (op 1C, called by 1D)
    if _first(st):
        st.params[2] = 0; lg.anim_complete = 0
        return 0
    if lg.anim_done:                                        # +0xAC: a 'stop' animation ended
        _restart_anim(lg)
        st.params[2] += 1; lg.anim_complete = 0
    elif lg.anim_complete:                                  # +0xB0: loop / chain completed
        st.params[2] += 1; lg.anim_complete = 0
    return 2 if st.params[2] >= n else 0


@op(0x1C)
def _wanim(vm, lg, ow, v, st, row):         # 0x8003E278
    return _anim_count(lg, st, v[1])


@op(0x1D)
def _wanimb(vm, lg, ow, v, st, row):        # 0x8003E30C
    r = _anim_count(lg, st, v[1])
    if r == 0 and lg.force_adjusted: r = 2                  # tested on the first run too
    return r


def _moved_xy(lg, st, thr):                 # 0x8003E354 (op 1E, called by 1F)
    if _first(st):
        st.params[2] = lg.px; st.params[3] = lg.py
        return 0
    if _abs_px(st.params[2], lg.px) >= thr or _abs_px(st.params[3], lg.py) >= thr: return 3
    return 0


@op(0x1F)
def _wmoveb(vm, lg, ow, v, st, row):        # 0x8003E3F0
    r = _moved_xy(lg, st, v[1] | v[2] << 8)
    if r == 0 and lg.force_adjusted: r = 3                  # first run too
    return r


def _moved_z(lg, st, thr):                  # 0x8003E438 (op 20, called by 21)
    if _first(st):
        st.params[2] = lg.pz
        return 0
    return 3 if _abs_px(st.params[2], lg.pz) >= thr else 0


@op(0x21)
def _wzc(vm, lg, ow, v, st, row):           # 0x8003E4A0
    r = _moved_z(lg, st, v[1] | v[2] << 8)
    if r == 0 and lg.collided_z: r = 3                      # first run too
    return r


def _to_record_z(vm, lg, st):               # 0x8003E4E8 (op 22, called by 23); None = halted
    if _first(st):
        rec = lg.record
        if not rec:
            st.params[1] = 0                                # the game stops here ("No InitData.")
            _fatal(vm, 'No InitData.'); return None
        st.params[2] = _s32((rec['z'] & 0xFF) << 19)       # record byte 9 * 8 px, no modz
        return 0
    t = st.params[2]
    if t == lg.pz: return 1                                 # exact 16.16 equality
    d = _s32(t - lg.pz)
    if (d > 0 and d < lg.fz) or (d <= 0 and lg.fz < d):
        lg.fz = d                                           # do not overshoot this frame
    return 0


@op(0x22)
def _tozrec(vm, lg, ow, v, st, row):        # 0x8003E4E8
    return _to_record_z(vm, lg, st) or 0


@op(0x23)
def _tozrecc(vm, lg, ow, v, st, row):       # 0x8003E5A8
    r = _to_record_z(vm, lg, st)
    if r is None: return 0
    if r == 0 and lg.collided_z: r = 1                      # first run too
    return r


@op(0x27)
def _faceP(vm, lg, ow, v, st, row):         # 0x8003E654
    from engine.player import dir_from_delta               # port of 0x8002EBA0
    p = vm.g.slots[0]
    lg.target_dir = dir_from_delta(_s32(p.px - lg.px), _s32(p.py - lg.py))
    return 1


@op(0x2D)
def _spawn(vm, lg, ow, v, st, row):         # 0x8003E744: SpawnMapEntity(logic, v1, force 1)
    g = vm.g
    e = g.spawn(v[1]) if _record_ok(g, v[1]) else None      # 0x8003AAE8 -> 0x8003A4C0 check
    if e is None:
        _fatal(vm, 'Illigal InitData Number!!')
    else:
        e.parent = lg                                       # InitializeEntity: parent = logic entity
    return 2


def _remove(g, e):                          # 0x8003B0C8
    if e.alive: e.set_status(4)                             # remake: alive/visible/active off
    e.estatus = 4                                           # (+0x228 action = -1: remake None)
    sh = getattr(e, 'shadow', None)                         # +0x1B8 shadow effect freed
    if sh is not None:
        sh.state = 0; e.shadow = None
    h = e.holder                                            # +0x28: the holder lets go
    if h is not None: h.carried = None


@op(0x2E)
def _destroy(vm, lg, ow, v, st, row):       # 0x8003E788
    st.result = 0
    for e in reversed(select_faithful(vm, lg, v[1])):      # last entry first; Alundra not excluded
        _remove(vm.g, e)
        st.result = 1
    return 2


def pad_word(g, i):
    """u16 at 0x801DDA48 + 2*i: 0 held, 1 pressed, 2 released, 3 auto-repeat (0x8002E5BC)."""
    if i > 3:                                               # reads past the block; unused by the data
        return 0
    f = getattr(g, 'pad_forced', None)                      # remake stand-in for op B3's writes
    if f: return f[i] & 0xFFFF
    w = (g.pad_held, g.pad_pressed, g.pad_released, getattr(g, 'pad_repeat', g.pad_pressed))
    return w[i] & 0xFFFF


@op(0x2F)
def _pad(vm, lg, ow, v, st, row):           # 0x8003E814
    st.result = 1 if pad_word(vm.g, v[3]) & (v[1] | v[2] << 8) else 0
    return 4


def pad_repeat_step(g, raw):
    """0x8002E5BC on pad 1 (block 0x801DDA38), once per frame with the new held mask:
    sets pad_pressed, pad_released, pad_repeat (0x801DDA4E) and pad_held."""
    raw &= 0xFFFF; old = g.pad_held & 0xFFFF
    g.pad_pressed = raw & (raw ^ old)
    g.pad_released = old & (raw ^ old)
    rep = getattr(g, 'pad_rep_on', 0); cnt = getattr(g, 'pad_rep_count', 0)
    if old != raw or old == 0:
        rep = 0; cnt = 0; g.pad_repeat = g.pad_pressed
    elif cnt >= (PAD_REPEAT_INTERVAL if rep else PAD_REPEAT_DELAY):
        rep = 1; cnt = 0; g.pad_repeat = raw
    else:
        cnt += 1; g.pad_repeat = 0
    g.pad_rep_on, g.pad_rep_count = rep, cnt
    g.pad_held = raw


def install(vm_module):
    """Use these handlers and select_faithful in a loaded remake/vm.py."""
    vm_module.HANDLERS.update(HANDLERS)
    vm_module.VM.select = select_faithful
