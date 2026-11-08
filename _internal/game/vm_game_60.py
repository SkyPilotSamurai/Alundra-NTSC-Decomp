"""Event script opcodes 0x60-0x7F: faithful replacements for the handlers remake/vm.py gets
WRONG or lacks (see audit_60_7F.md).  Game: US ALUN_CD.EXE (SLUS-00553).

Convention (remake/vm.py): handler(vm, lg, ow, v, st, row) -> byte advance, 0 = yield.
lg = logic entity (game a0), ow = owner (a1), v = instruction bytes (v[0] = opcode),
st = ProgState (the game's ctx, a3).  Importing this module after vm re-registers the opcodes
(@op overwrites the vm.HANDLERS entries); or paste the functions over the old ones in vm.py.

ctx words used here (ProgState): +0 start = params[0], +4 pc = ci, +8 = params[1],
+0xC / +0x10 / +0x14 = params[2] / [3] / [4] (raw 16.16 as the game stores them),
+0x2C = result, +0x30 = r30 (loop counter), +0x34 = r34 (return address, absolute ci).
"""
import sys
from pathlib import Path

try:
    from vm import op, s16, ProgState, DOC
except ImportError:                                   # run from research/us_decomp/vm_ops
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'remake'))
    from vm import op, s16, ProgState, DOC


def _s32(x):
    """A 32-bit register value (wrap + sign)."""
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _u16(v, i):
    return v[i] | v[i + 1] << 8


def _game_list(vm, lg, sel):
    """0x8003D374's list (0x8013D488..) in the game's order: ascending slot, Alundra = slot 0.
    Handlers walk it from the last entry down to the first.  The game never clears the list,
    so 0x8013D488 keeps the first entry of the last non-empty selection (vm.sel_first)."""
    g = vm.g
    lst = sorted(vm.select(lg, sel), key=lambda e: 0 if e is g.player else getattr(e, 'slot', 0))
    if lst:
        vm.sel_first = lst[0]
    return lst


# ------------------------------------------------------------- positions --
@op(0x64)
def _place(vm, lg, ow, v, st, row):          # 0x800400E0
    x = _s32(_u16(v, 2) << 16)
    y = _s32(_u16(v, 4) << 16)
    z = _s32((_u16(v, 6) << 16) + 1)           # PosZ = (z << 16) + 1
    for e in reversed(_game_list(vm, lg, v[1])):
        e.px, e.py, e.pz = x, y, z
    return 8


# --------------------------------------------------- context -> C program --
def _copy_ctx(dst, src):
    """0x80040264 copies all 14 ctx words (+0..+0x34); +0 and +4 are overwritten afterwards."""
    if src is None:                            # the shared context is zeroed BSS at boot
        dst.params[1:] = [0] * (len(dst.params) - 1)
        dst.result = dst.r30 = dst.r34 = 0
    else:
        dst.params[1:] = list(src.params[1:])
        dst.result, dst.r30, dst.r34 = src.result, src.r30, src.r34


@op(0x66)
def _to_c(vm, lg, ow, v, st, row):           # 0x80040264
    """owner C context (Entity+0x234) = the shared A/D/E/F context (0x80153340, 0x38 bytes);
    logic +0x26C/+0x270 = logic target anim/dir; C start = C pc = *a2 + s16(v1 | v2 << 8)."""
    lg.saved_c = (lg.target_anim, lg.target_dir)
    if vm.cur_slot in 'ADEF':                  # running in the shared context: *a2 is untouched
        tgt = st.ci + s16(v[1], v[2])
        c = ProgState(st.code, tgt)
        _copy_ctx(c, st)
        c.params[0] = tgt
        c.ci = tgt
        ow.states['C'] = c
        return 3
    # B / C: the running context IS owner+0x234, so the copy replaces this pc before the
    # handler reads *a2: the jump is computed from the shared context's pc and its bytes.
    tmp = getattr(vm, 'temp_state', None)      # needs: VM.run keeps the last A/D/E/F ProgState
    if tmp is None:
        vm.note('66 in B/C without a shared context')
        return 3
    ins = tmp.code.get(tmp.ci)
    b = (list(ins[1]) if ins else []) + [0, 0, 0]
    tgt = tmp.ci + s16(b[1], b[2])
    _copy_ctx(st, tmp)
    st.code = tmp.code
    st.params[0] = tgt
    st.ci = tgt
    return 3                                   # the engine continues at tgt + 3


# ---------------------------------------------------------------- camera --
def _camera_point(g):
    """The game's camera point (0x801D7B40 / 0x801D7B90 / 0x801D7B94, pixels).  EntityFrame
    (0x8003BD6C) copies the followed entity's PosX/Y/Z >> 16 into it after every frame while
    0x801EFE54 != 0 and that entity's status is 1..3; while 0x801EFE54 == 0 it stays."""
    pt = getattr(g, 'camera_point', None)
    if pt is not None:
        return tuple(pt)
    if g.camera_at:
        return tuple(g.camera_at)
    f = g.camera_follow or g.player
    return (f.px >> 16, f.py >> 16, f.pz >> 16)


@op(0x67)
def _cam(vm, lg, ow, v, st, row):            # 0x800402FC
    lst = _game_list(vm, lg, v[1])
    vm.g.camera_follow = lst[0] if lst else getattr(vm, 'sel_first', None)   # = *(0x8013D488)
    vm.g.camera_at = None                      # the point follows the entity again
    return 2


@op(0x68)
def _camoff(vm, lg, ow, v, st, row):         # 0x80040338
    g = vm.g
    g.camera_at = _camera_point(g)             # 0x801EFE54 = 0: the camera stays where it is
    g.camera_follow = None
    return 1


# ------------------------------------------------- remembered position --
@op(0x6A)
def _rempos(vm, lg, ow, v, st, row):         # 0x800403B8
    st.params[2], st.params[3], st.params[4] = lg.px, lg.py, lg.pz    # ctx+0xC/+0x10/+0x14
    return 1


def _moved(st, k, pos, v):
    d = _s32(st.params[k] - pos)               # subu
    if d < 0:
        d = _s32(-d)                           # negu (0x80000000 stays negative)
    return int(d >= _s32(_u16(v, 1) << 16))    # slt: signed, n >= 0x8000 gives a negative limit


@op(0x6B)
def _mx(vm, lg, ow, v, st, row):             # 0x800403E4
    st.result = _moved(st, 2, lg.px, v)
    return 3


@op(0x6C)
def _my(vm, lg, ow, v, st, row):             # 0x80040428
    st.result = _moved(st, 3, lg.py, v)
    return 3


@op(0x6D)
def _mz(vm, lg, ow, v, st, row):             # 0x8004046C
    st.result = _moved(st, 4, lg.pz, v)
    return 3


# ------------------------------------------------------- logic entity --
@op(0x71)
def _rhit(vm, lg, ow, v, st, row):           # 0x800404EC
    st.result = getattr(lg, 'hits', 0)         # Entity+0x220 (raw), combat.py keeps it as .hits
    return 1


@op(0x72)
def _keepanim(vm, lg, ow, v, st, row):       # 0x80040500
    lg.saved_c = (lg.target_anim, lg.target_dir)   # +0x26C/+0x270 = +0x88/+0x8C
    return 1


# ----------------------------------------------------------------- sound --
@op(0x75)
def _sfxstop(vm, lg, ow, v, st, row):        # 0x80040578 -> 0x8004A7B4(v[1])
    vm.g.stop_sound(v[1])                      # needs: stop every voice playing sfx n (n = 0: nothing)
    return 2


DOC.update({
    0x66: 'Point own C program at offset (copies this context, keeps anim/dir)',
    0x68: 'Camera stops following (stays where it is)',
    0x71: 'Result = hit count (Entity+0x220)',
    0x72: 'Keep current animation/direction for the C program',
    0x75: 'Stop sound effect',
    0x76: 'Unfinished command (debug stop)', 0x77: 'Unfinished command (debug stop)',
})
