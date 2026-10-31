"""VM opcodes 0x80-0x9F: faithful replacements for remake/vm.py (US ALUN_CD.EXE, SLUS-00553).

Every handler here replaces the remake handler with the same opcode (WRONG in audit_80_9F.md)
or adds it (MISSING).  0x80 0x81 0x83 0x8E 0x8F 0x91 0x92 are OK in vm.py and are not repeated.
Use: paste into remake/vm.py below the existing handlers, or import this module after vm with
remake/ on sys.path (the @op decorator overwrites the HANDLERS entries).

The remake has no stats struct yet; these names stand for the game's memory:
  stats *(0x80119AE8): +4 magic -> g.player.mp, +6 magic max -> g.player.mp_max,
                       +8 gilder -> g.gilder, +0xE Gilded Falcons -> g.falcons
  inventory *(0x80119AEC): 99 records of 4 bytes, count s16 at +2 -> g.inventory {item: count}
"""
import sys
from pathlib import Path

try:
    from vm import op
except ImportError:                                   # run from research/us_decomp/vm_ops
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'remake'))
    from vm import op
from engine import rodata, core
from gamerng import rnd

GRID_W = 52                      # map squares per RAM row: *(0x801AC6C4) + 0x604 + y * 0x1A0 + x * 8
ITEM_LIMIT = 0x63                # 0x8012E234, set to 99 by the inventory reset 0x8004F150
ITEM_MAX = 0x800BBE56            # s16 max count of item n at + n * 10 (10-byte item records at 0x800BBE50)
ELEMENT = 0x8009B80C             # u8 [1, 2, 3, 4, 5, 5, 6, 7]: script element -> attack attribute & 15
STATUS = 0x80023D2C              # s32 [2, 3, 4]: opcode 88 status values
DX, DY = 0x80023654, 0x80023694  # s16 32-direction tables
FALCON_FLAG = 0x5AA              # word 0x801DD3E8 bit 0x400, set by every Gilded Falcon


def _s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def _u16(v, i): return v[i] | v[i + 1] << 8


def _fatal(vm, what):
    """The game prints `what` and stops (0x8003D23C / 0x8002CC94 -> 0x80085A1C = BIOS B0 call 38h).
    The handler then returns 0, so the program never gets past this instruction."""
    f = getattr(vm.g, 'fatal', None)          # same hook name as audit_00_2F.py
    if f is not None: f(what)
    else: vm.note('fatal: ' + what)


# ------------------------------------------------------------ entity selection --
def _live(e): return e is not None and e.estatus in (1, 2, 3)


def select_game(vm, lg, sel):
    """0x8003D374: the selected entities in slot order (the list at 0x8013D488).  Handlers that
    act on all of them walk it from the last entry down; 'the first entry' is the lowest slot.
    g.slots[0..g.count] is the game's table (free slots are None: a freed slot gets the blank
    record, ref_id -1, which no selector matches)."""
    g = vm.g
    slots = g.slots[:g.count + 1]
    if not sel & 0x80:
        recs = g.map.doc['entities']                       # 0x8003D330 -> 0x8003A4C0
        if not (sel < len(recs) and recs[sel]['enabled']):
            _fatal(vm, 'Illegal InitData Number!!')
            return []
        if lg.estatus not in (1, 2, 3): return []          # tests the LOGIC entity's status, not the candidates'
        return [e for e in slots[1:] if e is not None and e.ref_id == sel]
    f = sel & 0x7F
    if f == 0: return [lg]
    if f == 1: return [slots[0]]
    if f == 2: return [e for e in slots if _live(e)]
    if f == 3: return [e for e in slots[1:] if _live(e)]
    if f == 4:
        if lg.estatus not in (1, 2, 3): return []          # the logic entity's status again
        return [e for e in slots if e is not None and e.flags & 0x80
                and not getattr(e, 'anim_flags', 0) & 0x80 and getattr(e, 'holder', None) is None]
    if f == 5: return [e for e in slots[1:] if _live(e) and lg.riding is e]
    if f == 6: return [e for e in slots[1:] if _live(e) and e.riding is lg]
    if f == 7: return [e for e in slots[1:] if _live(e) and lg.x_collision is e]
    if f == 8: return [e for e in slots[1:] if _live(e) and e.x_collision is lg]
    if f == 9: return [e for e in slots[1:] if _live(e) and e.parent is lg]
    if f == 10: return [e for e in slots[1:] if _live(e) and lg.parent is e]
    if f == 11: return [e for e in slots[1:] if _live(e) and getattr(e, 'holder', None) is not None]
    _fatal(vm, 'Illegal Distination!')                      # 0x8C..0xFF
    return []


# ------------------------------------------------------- stats and inventory --
def _gilder_set(g, v):                       # 0x8004F60C
    g.gilder = 9999 if v >= 10000 else (0 if v < 0 else v)
    return g.gilder


# Magic lives in the stats halfwords +4 / +6 (g.mem), which the HUD (magic_pair) and the
# engine ports read; the old g.player.mp / mp_max attributes were never read (2026-10-21 fix).
def _mp(g):                                  # 0x8004F528: magic
    from engine import menu as emenu
    return g.mem.s16(emenu._stats(g) + 4)


def _mp_max(g):                              # 0x8004F45C: most magic
    from engine import menu as emenu
    return g.mem.s16(emenu._stats(g) + 6)


def _magic_set(g, v):                        # 0x8004F540
    from engine import menu as emenu
    return emenu.magic_set(g, v)


def _magic_max_set(g, v):                    # 0x8004F474
    from engine import menu as emenu
    return emenu.magic_set_max(g, v)


def _item_count(g, n):                       # 0x8004FAC4
    return g.inventory.get(n, 0) if 0 <= n < ITEM_LIMIT else 0


def _item_add(g, n):                         # 0x8004FBE4: +1 unless already at the item's max
    if not 0 <= n < ITEM_LIMIT: return 0
    c = g.inventory.get(n, 0)
    if c != rodata.s16(ITEM_MAX + n * 10):
        c = _s16(c + 1)
        g.inventory[n] = c
    return c


def _item_take(g, n):                        # 0x8004FC80: -1 when there was none
    if not 0 <= n < ITEM_LIMIT: return 0
    c = g.inventory.get(n, 0)
    if c == 0: return -1
    c = _s16(c - 1)
    g.inventory[n] = c
    return c


def _sparkle(g, sub, dz):                    # 0x8003C760(0, 0xE, sub, Alundra x, y, z + dz)
    p = g.player
    return core.spawn_effect(g, 0, 0xE, sub, p.px, p.py, _s32(p.pz + dz))


def _ring(g, sub):                           # 8 sparkles converging on Alundra (seed, vessel)
    for i in range(8):
        e = _sparkle(g, sub, 0x100000)
        if e is not None:
            dx = rodata.s16(DX + 8 * i); dy = rodata.s16(DY + 8 * i)
            e.x = _s32(e.x + (dx << 13)); e.vx = _s32(-dx << 9)
            e.y = _s32(e.y + (dy << 13)); e.vy = _s32(-dy << 9)


def _rain(g, sub, vz):                       # 4 sparkles with random speeds (2 game RNG draws each)
    for i in range(4):
        e = _sparkle(g, sub, 0x100000)
        if e is not None:
            e.vz = vz
            e.vx = _s32(rnd(0x20001) - 0x10000)
            e.vy = _s32(rnd(0x30001) - 0x18000)


def _big_ring(g):                            # 0x80033DF0 (Large Crystal)
    for i in range(8):
        e = _sparkle(g, 2, 0x80000)
        if e is not None:
            k = (8 + 4 * i) & 31
            e.vz = 0x30000
            e.x = _s32(e.x + (rodata.s16(DX + 8 * i) << 11)); e.vx = rodata.s16(DX + 2 * k) * 0x1C0
            e.y = _s32(e.y + (rodata.s16(DY + 8 * i) << 11)); e.vy = rodata.s16(DY + 2 * k) * 0x1C0


def give_item(g, n):
    """0x80034814 (its only caller is opcode 82): 1 = given."""
    p = g.player
    if n == 0: return 0
    if n in (0x45, 0x46, 0x47, 0x48):                      # 1 / 5 / 10 / 30 Gilder (0x8004F668)
        _gilder_set(g, g.gilder + {0x45: 1, 0x46: 5, 0x47: 10, 0x48: 30}[n])
        return 1
    if n == 0x4F:                                           # Gilded Falcon (0x8004FDB4(1))
        f = (getattr(g, 'falcons', 0) + 1) & 0xFFFF
        g.falcons = 0x32 if _s16(f) >= 0x33 else f
        g.set_flag(FALCON_FLAG, True)
        return 1
    if n == 0x50:                                           # Magic Seed (0x80033F24)
        _magic_max_set(g, _mp_max(g) + 1)
        _magic_set(g, _mp_max(g))
        core.play_sound(g, 0x36)
        _ring(g, 2); _rain(g, 2, 0x40000)
        return 1
    if n == 0x51:                                           # Small Crystal (0x80033CB0)
        _magic_set(g, _mp(g) + 1)
        _rain(g, 2, 0x20000)
        return 1
    if n == 0x52:                                           # Large Crystal (0x80033DF0)
        _magic_set(g, _mp_max(g))
        _big_ring(g)
        return 1
    if n == 0x53:                                           # Life Vessel (0x80033AB0): no cap on max life
        p.hp_max += 1; p.hp = p.hp_max
        core.play_sound(g, 0x31)
        _ring(g, 0); _rain(g, 0, 0x40000)
        return 1
    if n == 0x54:                                           # Dew of Life (0x8003353C)
        p.hp = min(p.hp + 2, p.hp_max)
        return 1
    if n == 0x55:                                           # Drop of Life (0x800335FC)
        m = p.hp_max
        q = (m + 3 if m < 0 else m) >> 2
        if q <= 0: q = 1
        p.hp = min(p.hp + q, m)
        e = _sparkle(g, 0, 0x100000)
        if e is not None: e.vz = 0x20000
        return 1
    if n == 0x56:                                           # Water of Life (0x80033698)
        m = p.hp_max
        q = (m + 1 if m < 0 else m) >> 1
        if q < 5: q = 5
        p.hp = min(p.hp + q, m)
        _rain(g, 0, 0x20000)
        return 1
    before = _item_count(g, n)                              # 0x800345DC: did the count go up?
    return 1 if before < _item_add(g, n) else 0


# ------------------------------------------------------------------ handlers --
@op(0x82)
def _give(vm, lg, ow, v, st, row):           # 0x80040964
    st.result = give_item(vm.g, v[1])
    return 2


@op(0x84)
def _use(vm, lg, ow, v, st, row):            # 0x80040A1C (item >= 99: count 0 returned -> Result 1)
    st.result = 0 if _item_take(vm.g, v[1]) == -1 else 1
    return 2


@op(0x85)
def _areacopy(vm, lg, ow, v, st, row):       # 0x80040A6C -> 0x8002D96C(x, y, w, h, to x, to y)
    x, y, w, h, dx, dy = v[1:7]
    if x + w >= 0x35 or y + h >= 0x3D or dx + w >= 0x35 or dy + h >= 0x3D:
        _fatal(vm, f'map copy out of range {x},{y} {w}x{h} -> {dx},{dy}')   # 0x8002CC94
        return 0
    m = vm.g.map
    cells = m.cells
    for r in range(h):                       # in place, row by row, left to right (no buffer)
        for c in range(w):
            s = cells[(y + r) * GRID_W + x + c]
            cells[(dy + r) * GRID_W + dx + c] = [s[0], s[1], s[2], s[3], s[4], list(s[5]), s[6]]
    m.build_pieces()
    return 7


@op(0x86)
def _dmgtimer(vm, lg, ow, v, st, row):       # 0x80040ABC: Entity+0x1CC = u16
    t = _u16(v, 2)
    for e in reversed(select_game(vm, lg, v[1])): e.damaged_tick = t
    return 4


@op(0x87)
def _elemhit(vm, lg, ow, v, st, row):        # 0x80040B30
    elem = rodata.u8(ELEMENT + v[2])
    for e in reversed(select_game(vm, lg, v[1])):
        t = e.touching                       # Entity+0x224: the attacker that reached it
        if t is not None and t.atk_on:       # +0x1D4
            a = t.cur_attack                 # +0x1C8: attack record, byte 0 = attribute
            if a and a[0] and (a[0] & 0xF) == elem:
                st.result = 1
                return 3
    st.result = 0
    return 3


def _raw_status(e, s):
    """Entity+0x10 = s, as the game's plain store (a status-4 entity can be brought back
    before the next frame frees its slot)."""
    e.estatus = s
    if s == 4:
        e.alive = False; e.visible = False; e.active = False; e.action = None
    elif s in (2, 3):
        if not e.alive: e.alive = True; e.visible = True; e.active = True
        e.status = 'deactivated' if s == 3 else 'normal'
        if s == 2: e.active = True; e.visible = True


@op(0x88)
def _status(vm, lg, ow, v, st, row):         # 0x80040C04
    s = rodata.s32(STATUS + 4 * v[2])        # 2, 3, 4; v[2] >= 3 reads past the table (the game does too)
    for e in reversed(select_game(vm, lg, v[1])): _raw_status(e, s)
    return 3


@op(0x89)
def _placerel(vm, lg, ow, v, st, row):       # 0x80040C7C
    ref = select_game(vm, lg, v[1])
    if ref:
        r = ref[0]                           # first entry; the target is computed once
        x = _s32(r.px + (_u16(v, 3) << 16))
        y = _s32(r.py + (_u16(v, 5) << 16))
        z = _s32(r.pz + (_u16(v, 7) << 16))
        for e in reversed(select_game(vm, lg, v[2])): e.px, e.py, e.pz = x, y, z
    return 9


def _spawn_map(vm, lg, ref):
    """SpawnMapEntity(logic, ref, 1) 0x8003AAE8: forced (no zone / 0x40 test), parent = logic.
    NULL (bad or disabled record, no free slot) -> 0x8003D23C fatal."""
    recs = vm.g.map.doc['entities']
    e = vm.g.spawn(ref) if ref < len(recs) and recs[ref]['enabled'] else None
    if e is None:
        _fatal(vm, 'Illigal InitData Number!!')
        return None
    e.parent = lg
    return e


@op(0x8A)
def _spawnat(vm, lg, ow, v, st, row):        # 0x80040D78
    e = _spawn_map(vm, lg, v[1])
    if e is None: return 0
    e.px = _s32(_u16(v, 2) << 16)
    e.py = _s32(_u16(v, 4) << 16)
    e.pz = _s32((_u16(v, 6) << 16) + 1)      # plain store after the spawn: no ModZ
    return 8


@op(0x8B)
def _spawnrel(vm, lg, ow, v, st, row):       # 0x80040E38: spawn first, then select
    e = _spawn_map(vm, lg, v[2])
    if e is None: return 0
    ref = select_game(vm, lg, v[1])
    if ref:
        r = ref[0]
        e.px = _s32(r.px + (_u16(v, 3) << 16))
        e.py = _s32(r.py + (_u16(v, 5) << 16))
        e.pz = _s32(r.pz + (_u16(v, 7) << 16))
    return 9


@op(0x8C)
def _rand(vm, lg, ow, v, st, row):           # 0x80040F38: game RNG, Result 0 with chance n/256
    st.result = 1 if rnd(0x100) >= v[1] else 0
    return 2


@op(0x8D)
def _selgnd(vm, lg, ow, v, st, row):         # 0x80040FAC: PosZ <= floor height + 1
    for e in reversed(select_game(vm, lg, v[1])):
        if _s32(e.terrain + 1) >= e.pz:
            st.result = 1
            return 2
    st.result = 0
    return 2


@op(0x90)
def _fx(vm, lg, ow, v, st, row):             # 0x800410AC -> 0x8003CA78(n, 1): forced, no area test
    vm.g.effects.spawn_record(v[1], True, None)
    return 2


@op(0x93)
def _fxpos(vm, lg, ow, v, st, row):          # 0x8004117C
    x = _s32(_u16(v, 2) << 16); y = _s32(_u16(v, 4) << 16); z = _s32((_u16(v, 6) << 16) + 1)
    for e in vm.g.effects.by_id(v[1]): e.x, e.y, e.z = x, y, z
    return 8


@op(0x94)
def _fxforce(vm, lg, ow, v, st, row):        # 0x80041214: (s32)(u16 << 16) >> 8
    vx = _s16(_u16(v, 2)) << 8; vy = _s16(_u16(v, 4)) << 8; vz = _s16(_u16(v, 6)) << 8
    for e in vm.g.effects.by_id(v[1]): e.vx, e.vy, e.vz = vx, vy, vz
    return 8


def _within(p, base, ext, size):
    d = _s32(p - base)
    if d >= 0: return d < ext
    return _s32(base - p) < _s32(size + 1)


@op(0x95)
def _elembox(vm, lg, ow, v, st, row):        # 0x800412B4
    x0 = v[1] * 24 << 16; y0 = v[2] << 20; z0 = v[3] << 20
    wx = v[4] * 24 << 16                     # width; also used as the Z extent (byte 6 is never read)
    hy = v[5] << 20
    mask = v[7] | v[8] << 8
    elem = rodata.u8(ELEMENT + v[9])
    if mask:
        g = vm.g
        for e in g.slots[:g.count + 1]:      # slot 0 (Alundra) upwards, no selector
            if e is None or e.estatus not in (2, 3) or e.frozen or not e.atk_on: continue
            a = e.cur_attack
            if not a or not a[0] or not e.flags & mask or (a[0] & 0xF) != elem: continue
            if _within(e.atk_x, x0, wx, e.atk_w) and _within(e.atk_y, y0, hy, e.atk_h) \
                    and _within(e.atk_z, z0, wx, e.atk_d):
                st.result = 1
                return 10
    st.result = 0
    return 10


@op(0x96)
def _heal(vm, lg, ow, v, st, row):           # 0x800414A0: the amount is the selector byte itself
    n = v[1]                                 # byte 2 is never read
    for e in reversed(select_game(vm, lg, n)):
        h = _s32(e.hp + n)
        e.hp = e.hp_max if e.hp_max < h else h
    return 3


@op(0x97)
def _magic(vm, lg, ow, v, st, row):          # 0x80041524 -> 0x8004F59C: magic + n, 0..max
    _magic_set(vm.g, _mp(vm.g) + v[1])
    return 2


@op(0x98)
def _gilder_add(vm, lg, ow, v, st, row):     # 0x80041550 -> 0x8004F668
    _gilder_set(vm.g, vm.g.gilder + _u16(v, 1))
    return 3


@op(0x99)
def _gilder_pay(vm, lg, ow, v, st, row):     # 0x80041584
    g = vm.g; n = _u16(v, 1)
    if g.gilder >= n:
        _gilder_set(g, g.gilder - n)         # 0x8004F694
        st.result = 1
    else:
        st.result = 0
    return 3


@op(0x9A)
def _gilder_have(vm, lg, ow, v, st, row):    # 0x800415F8
    st.result = 1 if vm.g.gilder >= _u16(v, 1) else 0
    return 3


@op(0x9B)
def _warps_off(vm, lg, ow, v, st, row):      # 0x80041660: 0x801F11F0 = 1
    vm.g.warp_busy = 1
    vm.g.warps_disabled = True               # the remake's own door check reads this one
    return 1


@op(0x9C)
def _warps_on(vm, lg, ow, v, st, row):       # 0x80041674: 0x801F11F0 = 0
    vm.g.warp_busy = 0
    vm.g.warps_disabled = False
    return 1


@op(0x9D)
def _no157(vm, lg, ow, v, st, row):          # 0x80041684: prints 'No.157 ...' (SJIS) and stops
    _fatal(vm, 'No.157 is not implemented yet.')
    return 0


@op(0x9E)
def _count_cut(vm, lg, ow, v, st, row):      # 0x800416B4: squares with flags bit 0x02 in x, y, w, h
    cells = vm.g.map.cells
    n = 0
    for r in range(v[4]):
        for c in range(v[3]):
            i = (v[2] + r) * GRID_W + v[1] + c          # no bounds test in the game
            if i < len(cells) and cells[i][0] & 2: n += 1
    st.result = 1 if n >= v[5] else 0
    return 6


@op(0x9F)
def _contents_taken(vm, lg, ow, v, st, row): # 0x80041788: flag of the first entry's Entity+0x40
    sel = select_game(vm, lg, v[1])
    f = sel[0].contents_flag if sel else 0
    st.result = 1 if f and vm.g.flag(f) else 0
    return 2
