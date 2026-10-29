"""Event-script opcodes 0x30-0x5F (US ALUN_CD.EXE, SLUS-00553): faithful replacements for the
remake/vm.py handlers marked WRONG or MISSING in audit_30_5F.md, plus run_faithful(), a VM.run
with RunEntityProgram's g_vm_clear handling (0x80042BB8), which opcode 0x40 relies on.

Convention (as remake/vm.py): handler(vm, lg, ow, v, st, row) -> byte advance, 0 = yield.
lg = logic entity (game a0), ow = running entity (a1), v = instruction bytes (v[0] = opcode),
st = ProgState (the game's ctx, a3):
    params[0] = +0x00 start, ci = +0x04 pc, params[1] = +0x08 (pc a waiting op started on),
    params[2..6] = +0x0C..+0x1C, result = +0x2C.
Entity values are the remake's 16.16 integers (px py pz fz), never the float views wx/wy/z/vz.
Selections go through vm.select, which must be audit_00_2F.select_faithful (0x8003D374: slot
order, Alundra = slot 0); the game's handlers walk that list from the LAST entry to the first.
install(vm_module) puts these handlers (and, by default, run_faithful) into a loaded vm.py.
Routines that are not ported are called as vm.g methods when present (see "Needs" in the .md).
"""
import sys

M32 = 0xFFFFFFFF
SLOTS = 'ABCDEF'                             # action / program index 0-5
QUAD_DIR = (0x00, 0x10, 0x08, 0x18)          # s32[4] at 0x80023644 (down, up, left, right)
QUAD_ROW0 = (0, 0, 2, 1, 1, 1, 3, 0)         # 0x800237F4 quadrant table, row 0 (UpdateAnimation)
MAP_INDEX_COUNT = 500                        # s16 table at 0x801DD434

HANDLERS = {}


def op(*codes):
    def deco(fn):
        for c in codes: HANDLERS[c] = fn
        return fn
    return deco


def _s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def _s16(lo, hi):
    v = lo | hi << 8
    return v - 0x10000 if v & 0x8000 else v


def _abs32(x):
    """bgez / negu: |x| of a 32-bit register (0x80000000 stays negative)."""
    x = _s32(x)
    return x if x >= 0 else _s32(-x)


def _hook(g, name, *args):
    f = getattr(g, name, None)
    return f(*args) if f is not None else None


def _first(st):
    """ctx+8 != pc: first run of a waiting instruction; ctx+8 = pc."""
    if st.params[1] != st.ci:
        st.params[1] = st.ci
        return True
    return False


def _status(g, e):
    """Entity+0x10.  Alundra is set to 2 at map start (0x80031F74); the remake leaves 1."""
    s = e.estatus
    return 2 if (e is g.player and s == 1) else s


# ------------------------------------------------------------------ run loop --
def run_faithful(self, owner, slot, st, logic=None, budget=600):
    """VM.run with the game's clear handling.  After a handler, if g_vm_clear (only 0x40 sets
    it in this range): logic != owner -> the logic entity's B/C context (Entity+0x234/+0x238)
    is zeroed at once, so its C program restarts from the top; logic == owner -> the run goes
    ON (the next instructions still run this frame) and the running context is zeroed when the
    run stops (returned as 'restart', which the callers already handle)."""
    if st is None or st.ended: return False
    handlers = sys.modules[type(self).__module__].HANDLERS
    self.cur_owner = owner; self.cur_slot = slot; self.clear = False
    reset = False; out = True
    while budget > 0:
        budget -= 1
        ins = st.code.get(st.ci)
        if ins is None: st.ended = True; out = False; break
        code, raw, row = ins
        if code == 0xFF: st.ended = True; out = False; break
        if code == 0x00:
            st.params[1] = 0; st.ci += len(raw) if raw else 1; break
        v = list(raw) + [0] * (12 - len(raw))
        lg = (owner.logic_ctx or owner) if logic is None else logic   # +0x230, read every op
        h = handlers.get(code)
        if h is None:
            self.note(f'{code:02X}'); d = len(raw) or 1
        else:
            d = h(self, lg, owner, v, st, row)
        if self.trace is not None: self.trace.append((slot, st.ci, code, d))
        if self.clear:
            self.clear = False
            if lg is not owner: lg.states['C'] = None
            else: reset = True
        if d == 0: break
        st.params[1] = 0; st.ci += d
    return 'restart' if reset else out


# ------------------------------------------------------------- map index table --
class _DoorTable:
    """0x801DD434: s16[500] door destination table in the game's memory (part of the saved block;
    a new game makes entry i = i, 0x80083DA0).  Indexing past 499 reaches the next fields, as in
    the game."""
    BASE = 0x801DD434

    def __init__(self, g): self.g = g
    def __len__(self): return MAP_INDEX_COUNT
    def __getitem__(self, i): return self.g.mem.s16(self.BASE + 2 * i)
    def __setitem__(self, i, v): self.g.mem.w16(self.BASE + 2 * i, v & 0xFFFF)
    def __iter__(self): return (self[i] for i in range(MAP_INDEX_COUNT))


def map_index(g):
    return _DoorTable(g)


def portal_map(g, rec):
    """What Game.portal_map(rec) must return: 0x800318FC lh table[record map] (u16 index)."""
    t = map_index(g)
    return t[rec.map] if 0 <= rec.map < len(t) else rec.map


@op(0x38)
def _mapindex(vm, lg, ow, v, st, row):      # 0x8003EEB0
    i = v[1] | v[2] << 8
    t = map_index(vm.g)
    if i >= len(t): vm.note(f'38 index {i}')                # past entry 499 (no bound in the game)
    t[i] = _s16(v[3], v[4])                                 # sh; read back with lh
    return 5


# ----------------------------------------------------------------- tile boxes --
def _in_tiles(e, b):
    """tile_x/tile_y/tile_z (+0x120/+0x124/+0x128, kept by the tile update 0x80038948) in
    x1..x2, y1..y2, z1..z2 (u8 operands, inclusive, signed compare)."""
    return b[0] <= e.tile_x <= b[1] and b[2] <= e.tile_y <= b[3] and b[4] <= e.tile_z <= b[5]


@op(0x3B)
def _pbox(vm, lg, ow, v, st, row):          # 0x8003EF44: Alundra
    st.result = 1 if _in_tiles(vm.g.player, v[1:7]) else 0
    return 7


@op(0x3C)
def _objbox(vm, lg, ow, v, st, row):        # 0x8003EFEC
    g = vm.g; st.result = 0
    for e in g.slots[0:g.count + 1]:                        # slot 0 first, stops at the first hit
        if e is None or not 1 <= _status(g, e) <= 3: continue
        if not e.flags & 0x80 or e.anim_flags & 0x80 or e.holder is not None: continue
        if _in_tiles(e, v[1:7]):
            st.result = 1; break
    return 7


@op(0x3D)
def _anybox(vm, lg, ow, v, st, row):        # 0x8003F0EC
    g = vm.g; st.result = 0
    for e in g.slots[0:g.count + 1]:
        if e is not None and 1 <= _status(g, e) <= 3 and _in_tiles(e, v[1:7]):
            st.result = 1; break
    return 7


@op(0x3F)
def _anyrides(vm, lg, ow, v, st, row):      # 0x8003F1E0
    g = vm.g; st.result = 0
    for e in g.slots[0:g.count + 1]:                        # status 2-3 only, not frozen (+0x20)
        if e is not None and 2 <= _status(g, e) <= 3 and not e.frozen and e.riding is lg:
            st.result = 1; break
    return 1


# ------------------------------------------------------------------- programs --
def _set_builtin(e, i, val):
    """Entity+0x70 + 4i: the sprite's native program for slot i.  The header dicts are shared
    between entities of one sprite: copy before writing."""
    sp = dict(getattr(e, 'sprite_programs', None) or {})
    sp[SLOTS[i]] = val
    e.sprite_programs = sp


@op(0x40)
def _setprog(vm, lg, ow, v, st, row):       # 0x8003F260
    n, p = v[1], v[2]
    if n < 6: lg.programs[SLOTS[n]] = p                     # Entity+0x4C + 4n (u8)
    elif n == 8: lg.flags = p                               # +0x6C (no bound check in the game)
    elif 9 <= n <= 14: _set_builtin(lg, n - 9, p)           # +0x70..+0x84
    else: vm.note(f'40 writes Entity+0x{0x4C + 4 * n:X}')   # 6 header ptr, 7 sprite index, ...
    vm.clear = True                                         # g_vm_clear: needs run_faithful
    return 3


@op(0x41)
def _setsprog(vm, lg, ow, v, st, row):      # 0x8003F290 (no clear)
    n, p = v[1], v[2]
    if n < 6: _set_builtin(lg, n, p)                        # Entity+0x70 + 4n
    elif n == 6: lg.target_anim = p                         # +0x88
    elif n == 7: lg.target_dir = p                          # +0x8C (stored as is)
    else: vm.note(f'41 writes Entity+0x{0x70 + 4 * n:X}')
    return 3


# ------------------------------------------------------------------- messages --
@op(0x44)
def _yesno(vm, lg, ow, v, st, row):         # 0x8003F334
    """YES / NO (engine/choice.py, UI task 3): the answer arrives at 0x80104828 (1 YES, 2 NO);
    Result = 1 for YES."""
    from engine import choice
    g = vm.g; m = g.mem
    if st.params[1] != st.ci:
        m.w32(0x80104828, 0)
        a = choice.etc_text(g, 0x43)
        if choice.yes_no_open(g, a, choice.etc_text(g, 0x44), 0x80104828) != 0:
            st.params[1] = st.ci
        return 0
    r = m.s32(0x80104828)
    if r == 0: return 0
    st.result = 1 if r == 1 else 0
    return 1


def _msg_set(vm, i, m):
    """Ops 4C / 4E / 50: the message window's print / scroll / close mode words
    (0x80046044 / 0x8004607C / 0x8004600C; engine/message.py)."""
    from engine import message as M
    (M.set_print_mode, M.set_scroll_mode, M.set_close_mode)[i](vm.g, m)


def _msg_request(vm, i):
    """Ops 4D / 4F / 51: a script request (only when that mode has bit 2)."""
    from engine import message as M
    (M.print_request, M.scroll_request, M.close_request)[i](vm.g)


@op(0x4C)
def _txtmode(vm, lg, ow, v, st, row):       # 0x8003F4E0 -> 0x80046044
    _msg_set(vm, 0, v[1]); return 2


@op(0x4D)
def _txtreq(vm, lg, ow, v, st, row):        # 0x8003F50C -> 0x8004601C
    _msg_request(vm, 0); return 1


@op(0x4E)
def _scrmode(vm, lg, ow, v, st, row):       # 0x8003F52C -> 0x8004607C
    _msg_set(vm, 1, v[1]); return 2


@op(0x4F)
def _scrreq(vm, lg, ow, v, st, row):        # 0x8003F558 -> 0x80046054
    _msg_request(vm, 1); return 1


@op(0x50)
def _closemode(vm, lg, ow, v, st, row):     # 0x8003F578 -> 0x8004600C
    _msg_set(vm, 2, v[1]); return 2


@op(0x51)
def _closereq(vm, lg, ow, v, st, row):      # 0x8003F5A4 -> 0x80045FE4
    _msg_request(vm, 2); return 1


def _sprite_index(e):
    """Entity+0x68 (sprite catalogue; map sprites 0x100-0x1FF)."""
    n = getattr(e, 'sprite_index', None)
    return getattr(e, 'balance_index', -1) if n is None else n


@op(0x5C)
def _msgsel(vm, lg, ow, v, st, row):        # 0x8003FAF0
    g = vm.g
    sel = vm.select(lg, v[1])
    sp = sel[0] if sel else None                            # FIRST entry (0x8013D488)
    if sp is not None:                                      # runs again on every waiting frame
        if sp.flags & 0x800000: _hook(g, 'msg_speaker', sp) # 0x80059AE4 speaker marker
        _hook(g, 'msg_name', _sprite_index(sp))             # 0x8005C0A8 name plate
    start = getattr(g, 'msg_start', None)                   # 0x80042F74(message, lock mode)
    if start is not None:
        return 4 if start(v[2], v[3]) else 0
    return 4 if g.open_message(row, sp, v[3]) else 0              # remake text path until ported


# --------------------------------------------------------------- hits / waits --
@op(0x47)
def _whit(vm, lg, ow, v, st, row):          # 0x8003F428
    return 1 if lg.hits or lg.force_adjusted else 0         # +0x220, +0x13C


@op(0x48)
def _whitz(vm, lg, ow, v, st, row):         # 0x8003F454
    return 1 if lg.hits or lg.collided_z else 0             # +0x220, +0x140


def _restart_anim(e):
    """Entity+0x90 cur_anim = ~target_anim: UpdateAnimation 0x800393A4 restarts the animation.
    The remake's animate() compares Animator.anim with target_anim, so set that too."""
    e.cur_anim = ~e.target_anim
    a = getattr(e, 'anim', None)
    if a is not None: a.anim = ~e.target_anim


@op(0x5F)
def _wcombo(vm, lg, ow, v, st, row):        # 0x8003FCE8 (the LOGIC entity)
    e = lg
    if _first(st):
        st.params[2], st.params[3], st.params[4] = e.px, e.py, e.pz     # +0xC +0x10 +0x14
        st.params[5] = 0; st.params[6] = 0                              # +0x18 anims, +0x1C frames
        e.anim_complete = 0
        return 0
    if e.anim_done:                                         # +0xAC
        _restart_anim(e)
        st.params[5] += 1; e.anim_complete = 0
    elif e.anim_complete:                                   # +0xB0
        st.params[5] += 1; e.anim_complete = 0
    st.params[6] += 1
    if st.params[5] < v[4] or st.params[6] < v[5]: return 0
    f = v[6]
    if f & 1 and not e.force_adjusted: return 0
    if f & 2 and not e.collided_z: return 0
    if f & 3 and not e.on_ground: return 0                  # sic: on_ground for bit 0 or 1
    if f & 4 and not e.hits: return 0
    if _abs32(st.params[2] - e.px) < v[1] * 0x180000: return 0
    if _abs32(st.params[3] - e.py) < v[2] << 20: return 0
    return 8 if _abs32(st.params[4] - e.pz) >= v[3] << 20 else 0


# ------------------------------------------------------------ doors and warps --
@op(0x52)
def _portal(vm, lg, ow, v, st, row):        # 0x8003F5C4
    from engine.player import find_portal, use_portal
    g = vm.g
    rec = find_portal(g)                                    # 0x80031C28
    if rec is None:
        vm.note('52 no portal')                             # debug text 0x80023CDC
        st.result = 0
        return 1
    p = g.player
    use_portal(g, rec, p.target_anim, p.target_dir)         # 0x80031898
    st.result = 1
    return 1


@op(0x53)
def _warp(vm, lg, ow, v, st, row):          # 0x8003F630
    g = vm.g; p = g.player
    eff = v[6]; m = v[1] | v[2] << 8                        # map number as is (no 0x801DD434 table)
    g.warp_effect = eff; g.warp_map = m; g.warp_sound = v[7]
    x = (v[3] * 24 + 12) << 16
    y = (v[4] * 16 + 8) << 16
    z = v[5] << 20
    if eff == 3:
        if m == g.cur_map:                                  # same map: move him now, no request
            p.px, p.py, p.pz = x, y, z + 1
            return 8
        vm.note('53 effect 3 to another map')               # debug text 0x80023CF4
        g.warp_effect = 0
    g.warp_request = 1                                      # no warp_busy test (doors have one)
    g.warp_x, g.warp_y, g.warp_z = x, y, z
    g.warp_anim = p.target_anim; g.warp_dir = p.target_dir
    return 8


# ----------------------------------------------------- jumps by facing --
def _quadrant(e):
    """Entity+0x98 (0 down, 1 up, 2 left, 3 right).  None in the remake before the first
    animate(); the game's spawn already ran UpdateAnimation from quadrant 0."""
    q = getattr(e, 'anim_quadrant', None)
    return QUAD_ROW0[((e.target_dir + 2) & 0x1C) >> 2] if q is None else q


@op(0x57)
def _jpdir(vm, lg, ow, v, st, row):         # 0x8003F8FC: Alundra's quadrant
    q = _quadrant(vm.g.player)
    return _s16(v[2 * q + 1], v[2 * q + 2])


@op(0x58)
def _jodir(vm, lg, ow, v, st, row):         # 0x8003F930: the logic entity's quadrant
    q = _quadrant(lg)
    return _s16(v[2 * q + 1], v[2 * q + 2])


# --------------------------------------------------------- selected entities --
def _talk_side(g, e):
    """0x8003D9B0: -1 unless e is the talk target (0x801EFE5C); else the side Alundra is on:
    0 / 16 (below / above) when the x boxes overlap, else 8 / 24 (left / right)."""
    if getattr(g, 'talk_target', None) is not e: return -1
    p = g.player
    d = _s32(p.mpx - e.mpx)
    horiz = (e.sizex < d) if d >= 0 else (p.sizex < _s32(-d))
    if not horiz: return 0x10 if p.py < e.py else 0
    return 8 if p.px < e.px else 0x18


def resolve_dir(vm, e, enc):
    """0x8003DA58(e, enc): mode enc >> 5, r = enc & 31."""
    import gamerng
    g = vm.g; r = enc & 31; mode = (enc & 0xFF) >> 5
    if mode == 0: return r
    if mode == 1: return (e.target_dir + r) & 31
    if mode == 2: return QUAD_DIR[r & 3]
    if mode == 3:
        from engine.player import dir_from_delta            # 0x8002EBA0 (tables, 16.16 deltas)
        p = g.player
        return (dir_from_delta(_s32(p.px - e.px), _s32(p.py - e.py)) + r) & 31
    if mode == 4: return QUAD_DIR[gamerng.rnd(4)]
    if mode == 5: return gamerng.rnd(32)
    if mode == 6: return (g.player.target_dir + r) & 31
    t = _talk_side(g, e)                                    # mode 7
    return r if t == -1 else (t + r) & 31


@op(0x5A)
def _seldir(vm, lg, ow, v, st, row):        # 0x8003F9C8
    for e in reversed(vm.select(lg, v[1])):                # last entry first (RNG order, modes 4/5)
        e.target_dir = resolve_dir(vm, e, v[2])
    return 3


@op(0x5B)
def _selanimdir(vm, lg, ow, v, st, row):    # 0x8003FA54
    for e in reversed(vm.select(lg, v[1])):
        e.target_anim = v[2]                                # stored before the direction call
        e.target_dir = resolve_dir(vm, e, v[3])
    return 4


@op(0x5D)
def _seldeact(vm, lg, ow, v, st, row):      # 0x8003FC14: Entity+0x10 = 3, nothing else
    for e in reversed(vm.select(lg, v[1])):
        if e.estatus == 4:                                  # destroyed this frame: no longer freed
            e.alive = True; e.active = True; e.visible = True
        e.estatus = 3; e.status = 'deactivated'
    return 2


def install(vm_module, run_patch=True):
    """Use these handlers (and run_faithful) in a loaded remake/vm.py.  VM.select must be
    audit_00_2F.select_faithful; Game.portal_map should return portal_map(g, rec)."""
    vm_module.HANDLERS.update(HANDLERS)
    if run_patch: vm_module.VM.run = run_faithful
