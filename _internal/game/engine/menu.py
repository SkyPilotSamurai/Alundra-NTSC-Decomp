"""Inventory, equipment and the Start menu (the game's menu module), ported from the US
ALUN_CD.EXE.  The data lives where the game keeps it (g.mem):
  *(0x80119AE8) -> stats (s16): +0 life, +2 life max, +4 magic, +6 magic max, +8 gilder,
                   +0xA equipped weapon group (1..6), +0xC chosen item (Circle), +0xE, +0x10
  *(0x80119AEC) -> item records, 4 bytes each, count (s16) at +2; 0x8012E234 = record count (99)
  0x800BBE50 + 10 * item: group (s16), flags (bit 0: the best of the group by rank wins), rank,
                   max count (+6), ...
Menu state: 0x801531BC main inventory window flags (1 open, 2 closing, 4 opening), 0x801531F0
its cursor (0-23: a 6 x 4 grid, row 0 the weapons), 0x801531B4 the name / description typing
counter; 0x801E6760.. the second page (key items and equipment, 14 slots), cursor 0x801E6884;
0x8012E284: 1 = open the second page / 2 = the first when the closing page has gone."""
from .registry import port
from . import core, calls

STATS_PTR, INV_PTR, ITEM_COUNT = 0x80119AE8, 0x80119AEC, 0x8012E234
ITEM_REC = 0x800BBE50
PAD_REPEAT = 0x801DDA4E                      # pad 1 "pressed or auto-repeating" (0x8002E5BC)
INV_FLAGS, INV_SLOT, INV_TEXT = 0x801531BC, 0x801531F0, 0x801531B4
SUB_FLAGS, SUB_SLOT = 0x801E6490, 0x801E6884
SWITCH = 0x8012E284
SLOT_ITEM = 0x800BBD30                       # s32[24]: the item a main-menu slot shows (-1: a group's best, 0: none)
SLOT_FN = 0x800BBCD0                         # the accessor per slot (best of a group / has_item)
SUB_NEXT = {'R': 0x800B6240, 'L': 0x800B6278, 'U': 0x800B62B0, 'D': 0x800B62E8}   # second page: s32[14] each


def _stats(g): return g.mem.u32(STATS_PTR)
def _inv(g): return g.mem.u32(INV_PTR)


@port(0x8004F204, mock_always=True)
def debug_print(g, fmt, n=0):
    """Prints a debug message (bad item number...): nothing in the game itself."""


@port(0x8004FAC4, ret=True)
def has_item(g, n):
    """How many of item n Alundra has (0 for an item number out of range)."""
    if n < 0 or not n < g.mem.s32(ITEM_COUNT):
        debug_print(g, 0x8002660C, n); return 0
    return g.mem.s16(_inv(g) + 4 * n + 2)


@port(0x8004FBE4, ret=True)
def give_item(g, n):
    """One more of item n, up to its maximum (item record +6); returns the count."""
    if n < 0 or not n < g.mem.s32(ITEM_COUNT):
        debug_print(g, 0x80026664, n); return 0
    a = _inv(g) + 4 * n + 2
    c = g.mem.s16(a)
    if c != g.mem.s16(ITEM_REC + 10 * n + 6):
        g.mem.w16(a, c + 1); return core.s16(c + 1)
    return c


@port(0x8004F810, ret=True)
def best_of_group(g, grp):
    """The item of group grp Alundra uses: the first one he has, or (flag bit 0) the one of
    the highest rank; -1 when he has none.  Looks at the first 0x80 item records."""
    if (grp & 0xFFFFFFFF) >= 0x20:
        debug_print(g, 0x800265EC, grp); return -1
    best = -1; inv = _inv(g)
    for k in range(0x80):
        r = ITEM_REC + 10 * k
        if g.mem.s16(r) == grp and g.mem.s16(inv + 4 * k + 2) > 0:
            if best == -1:
                best = k
                if not g.mem.u16(r + 2) & 1: return best
            elif g.mem.s16(ITEM_REC + 10 * best + 4) < g.mem.s16(r + 4):
                best = k
    return best


@port(0x8004FD08, ret=True)
def next_in_group(g, start, grp):
    """The first item number >= start of group grp that Alundra has, -1 if none."""
    if (grp & 0xFFFFFFFF) >= 0x20:
        debug_print(g, 0x80026684, start); return -1
    n = g.mem.s32(ITEM_COUNT); inv = _inv(g)
    for k in range(start, n):
        if g.mem.s16(ITEM_REC + 10 * k) == grp and g.mem.s16(inv + 4 * k + 2) > 0: return k
    return -1


for _a, _grp in ((0x8004F904, 1), (0x8004F924, 2), (0x8004F944, 3), (0x8004F964, 4), (0x8004F984, 5),
                 (0x8004F9A4, 6), (0x8004F9C4, 0xB), (0x8004F9E4, 0x14), (0x8004FA04, 0x15), (0x8004FA24, 0x16),
                 (0x8004FA44, 0x10), (0x8004FA64, 0x11), (0x8004FA84, 0x12), (0x8004FAA4, 0x13)):
    def _f(g, _grp=_grp): return best_of_group(g, _grp)
    _f.__name__ = f'best_group_{_grp:02x}'
    globals()[_f.__name__] = port(_a, ret=True)(_f)


@port(0x8004FB28)
def equip(g, grp):
    """Equips weapon group grp (1 swords, 2 flails, 3 wands, 4 bows, 5 iron flails?, 6 ...)."""
    if grp == -1 or ((grp - 1) & 0xFFFFFFFF) < 6:
        g.mem.w16(_stats(g) + 0xA, grp)
    else:
        debug_print(g, 0x80026620, grp)
    equipped_kind(g)


@port(0x8004FB84)
def choose_item(g, n):
    """The item Circle uses."""
    if n < 0 or not n < g.mem.s32(ITEM_COUNT):
        debug_print(g, 0x80026648, n); return
    g.mem.w16(_stats(g) + 0xC, n)


@port(0x8004F6C0, ret=True)
def equipped_kind(g):
    """The weapon ITEM in use (the best Alundra has of the equipped group), -1 none.  (It
    indexes the weapon class table 0x80028BB8 by item number.)"""
    grp = g.mem.s16(_stats(g) + 0xA)
    if grp == -1 or not ((grp - 1) & 0xFFFFFFFF) < 6: return -1
    pick = getattr(g, 'picked_weapon', None)               # (the remake's Mods > Magic & weapon swapping)
    k = pick(grp) if pick is not None else None
    return best_of_group(g, grp) if k is None else k


@port(0x8004F784, ret=True)
def selected_item(g):
    """The item Circle uses, -1 if Alundra has none of it.  (It also moves the choice to the
    best item of that item's group.)"""
    n = g.mem.s16(_stats(g) + 0xC)
    keep = getattr(g, 'keeps_scroll', None)                 # (the remake's Mods > Magic & weapon swapping)
    if keep is not None and keep(n): return n
    if has_item(g, n) != 0:
        choose_item(g, best_of_group(g, g.mem.s16(ITEM_REC + 10 * n)))
        return n
    return -1


@port(0x8004F5F4, ret=True)
def gilder(g): return g.mem.s16(_stats(g) + 8)


@port(0x8004F60C, ret=True)
def set_gilder(g, v):
    g.mem.w16(_stats(g) + 8, 0x270F if v >= 0x2710 else 0 if v < 0 else v)
    return g.mem.s16(_stats(g) + 8)


@port(0x8004F2C4, ret=True)
def life_max(g): return g.mem.s16(_stats(g) + 2)


@port(0x8004F2DC, ret=True)
def hud_set_max(g, v):
    """Life maximum (stats +2), kept within 0..50 (MovePlayer sets it from Alundra every frame)."""
    g.mem.w16(_stats(g) + 2, 0x32 if not v < 0x33 else 0 if v < 0 else v)
    return g.mem.s16(_stats(g) + 2)


@port(0x8004F390, ret=True)
def life(g): return g.mem.s16(_stats(g))


@port(0x8004F3A8, ret=True)
def hud_set_hp(g, v):
    """Life (stats +0), kept within 0..the maximum."""
    m = g.mem; st = _stats(g); mx = m.s16(st + 2)
    m.w16(st, mx if mx < v else 0 if v < 0 else v)
    return m.s16(_stats(g))


@port(0x8004F474, ret=True)
def magic_set_max(g, v):
    g.mem.w16(_stats(g) + 6, 4 if not v < 5 else 0 if v < 0 else v)
    return g.mem.s16(_stats(g) + 6)


@port(0x8004F540, ret=True)
def magic_set(g, v):
    m = g.mem; st = _stats(g); mx = m.s16(st + 6)
    m.w16(st + 4, mx if mx < v else 0 if v < 0 else v)
    return m.s16(_stats(g) + 4)


@port(0x80030CA4)
def update_equipment(g):
    """Boots, armour / rings resistances and Life regeneration (0x80030CA4).  Ported: the boots
    level 0x801D8740 (Charm Boots 0x1C = 3, 0x1B = 2, 0x1A = 1, none 0) and the Life regeneration
    (0x80031110): with no mode flag 0x7C, not frozen, no button held and 0 < Life < max, each of
    the armour / weapon / ring records with a byte +2 (balance 'hp', Recovery Ring 200) counts
    frames and gives 1 Life when the count passes it.  The resistances are combat.py's."""
    g.floor_damage_lock = 3 if has_item(g, 0x1C) else 2 if has_item(g, 0x1B) else 1 if has_item(g, 0x1A) else 0
    p = g.player; cnt = g.__dict__.setdefault('regen_counts', [0, 0, 0])
    if not g.mode_flags & 0x7C and not p.frozen and not g.pad_held and p.hp and p.hp < p.hp_max:
        armour = next((i for i in (20, 19, 18, 17) if has_item(g, i)), 0)
        hp = p.hp
        for k, it in enumerate((armour, g.weapon_item(), g.ring_item())):
            r = g.combat.item_record(it) if it and it > 0 else None
            if r and r['hp']:
                cnt[k] += 1
                if r['hp'] < cnt[k]: cnt[k] = 0; hp += 1
            else: cnt[k] = 0
        p.hp = min(hp, p.hp_max)
    else: cnt[:] = [0, 0, 0]
    hook = getattr(g, 'update_equipment', None)
    if hook: hook()


# ------------------------------------------------------------------ the pad's auto-repeat
@port(0x8002E5BC)
def pad_update(g, pad, buttons):
    """A pad record (0x801DDA38 for pad 1: +0 first repeat delay 20, +4 repeat interval 0,
    +8 repeating, +0xC counter, +0x10 held, +0x12 pressed, +0x14 released, +0x16 repeat):
    the repeat word is the pressed buttons, then after 21 frames of the same buttons held
    the held buttons every frame (+4 = 0).  Pad 1's held / pressed / released / repeat are
    g.pad_held, g.pad_pressed, g.pad_released, g.pad_repeat."""
    m = g.mem; buttons &= 0xFFFF
    one = (pad & 0x1FFFFF) == 0x1DDA38
    def get(o): return getattr(g, {0x10: 'pad_held', 0x12: 'pad_pressed', 0x14: 'pad_released', 0x16: 'pad_repeat'}[o]) if one else m.u16(pad + o)
    def put(o, v):
        if one: setattr(g, {0x10: 'pad_held', 0x12: 'pad_pressed', 0x14: 'pad_released', 0x16: 'pad_repeat'}[o], v & 0xFFFF)
        else: m.w16(pad + o, v)
    held = get(0x10)
    put(0x12, buttons & (buttons ^ held))
    put(0x14, held & (buttons ^ held))
    if held != buttons or held == 0:
        m.w32(pad + 8, 0); m.w32(pad + 0xC, 0); put(0x16, get(0x12))
    else:
        c = m.u32(pad + 0xC)
        if m.u32(pad + 8) == 0:
            if c >= m.u32(pad):
                m.w32(pad + 8, 1); m.w32(pad + 0xC, 0); put(0x16, buttons)
            else:
                m.w32(pad + 0xC, c + 1); put(0x16, 0)
        elif c >= m.u32(pad + 4):
            m.w32(pad + 0xC, 0); put(0x16, buttons)
        else:
            m.w32(pad + 0xC, c + 1); put(0x16, 0)
    put(0x10, buttons)


# ------------------------------------------------------------------ what the menus draw
# (presentation: the remake's menu screen draws these itself; the checks replay them)
def _ui(addr, name, doc):
    def f(g, *args):
        hook = getattr(g, 'ui', None)
        if hook is not None: return hook(addr, *args)
        return 0
    f.__name__ = name; f.__doc__ = doc
    globals()[name] = port(addr, mock_always=True)(f)


for _a, _n, _d in (
        (0x800579D0, 'names_refresh', 'The equipped weapon / chosen item names (HUD and menu).'),
        (0x8005CE4C, 'magic_item_hint', 'Magic items 0x2B-0x30: their pictures (debug / special mode).'),
        (0x80052070, 'cursor_place', 'The menu cursor sprite at x, y.'),
        (0x800521D0, 'cursor_draw', 'The menu cursor (animated).'),
        (0x8005887C, 'inv_numbers', 'Main page: gilder, falcons, keys.'),
        (0x80058DB0, 'inv_icons', 'Main page: the weapon and item pictures (shade 0x90), the frames on the ones in use, the herb count.'),
        (0x80057A98, 'inv_window', 'Main page: one window frame.'),
        (0x80058030, 'inv_names', 'Main page: the equipped weapon / chosen item names in their windows.'),
        (0x80057D30, 'inv_typing', 'Main page: types the name, then the description, of the slot under the cursor (advances 0x801531B4).'),
        (0x8004D24C, 'hud_show', 'The HUD slides back in.'),
        (0x8004D1B8, 'hud_hide', 'The HUD slides out.'),
        (0x800548B0, 'sub_text_init', 'Second page: the text lines set up.'),
        (0x80054AC0, 'sub_equipment', 'Second page: armour / boots names.'),
        (0x80054938, 'sub_equipment_icons', 'Second page: armour / boots pictures.'),
        (0x80054768, 'sub_crests', 'Second page: the seven key items Alundra has.'),
        (0x800545E8, 'sub_key_items', 'Second page: the first five items of group 0x1C.'),
        (0x80054BF0, 'sub_window', 'Second page: one window frame.'),
        (0x80055AFC, 'sub_text', 'Second page: name / description of the slot under the cursor.'),
        (0x80055EA4, 'sub_numbers', 'Second page: gilder, item 0x3D, stats +0xE / +0x10.'),
        (0x80088230, 'gpu_draw_env', 'GPU: the drawing environment (presentation).'),
        (0x800882D8, 'gpu_draw_env_set', 'GPU: the drawing environment of a buffer.'),
        (0x80059958, 'portrait_image', "Alundra's portrait picture record (an address).")):
    _ui(_a, _n, _d)


# ------------------------------------------------------------------ the main inventory page
@port(0x80059794)
def inv_pick_weapon(g):
    """Cross on the weapon row: equip that weapon group (sound 2), or the refusal (sound 3)
    when Alundra has none of it; nothing when it is already in use."""
    slot = g.mem.s32(INV_SLOT)
    groups = {0: (0x8004F904, 1), 2: (0x8004F924, 2), 1: (0x8004F944, 3), 3: (0x8004F964, 4), 4: (0x8004F984, 5)}
    if (slot & 0xFFFFFFFF) < 6:
        if slot in groups:
            fa, grp = groups[slot]
            best = calls.call(g, fa)
            if equipped_kind(g) != best:
                if best == -1: core.play_sound(g, 3)
                elif slot in (0, 2): equip(g, grp); core.play_sound(g, 2)
                else: core.play_sound(g, 2); equip(g, grp)
        else:                                               # slot 5: item 7, group 6
            it = g.mem.s32(SLOT_ITEM + 4 * slot)
            n = has_item(g, it)
            if equipped_kind(g) != g.mem.s32(SLOT_ITEM + 4 * g.mem.s32(INV_SLOT)):
                if n == 0: core.play_sound(g, 3)
                else: core.play_sound(g, 2); equip(g, 6)
    calls.call(g, 0x800579D0)                               # the weapon / item names


@port(0x80059694)
def inv_pick_item(g):
    """Cross on an item: it becomes the Circle item (sound 2), refusal (sound 3) when
    Alundra has none; nothing when it is already chosen."""
    slot = g.mem.s32(INV_SLOT)
    it = g.mem.s32(SLOT_ITEM + 4 * slot)
    if it == 0:
        calls.call(g, 0x800579D0); calls.call(g, 0x8005CE4C); return
    if it == -1:
        best = calls.call(g, g.mem.u32(SLOT_FN + 4 * slot))
        if best == it: core.play_sound(g, 3); return
        if selected_item(g) == best: return
        choose_item(g, best)
    else:
        if has_item(g, it) == 0: core.play_sound(g, 3); return
        if selected_item(g) == g.mem.s32(SLOT_ITEM + 4 * g.mem.s32(INV_SLOT)): return
        choose_item(g, g.mem.s32(SLOT_ITEM + 4 * g.mem.s32(INV_SLOT)))
    core.play_sound(g, 2)
    calls.call(g, 0x800579D0); calls.call(g, 0x8005CE4C)


def inv_input(g):
    """The input part of the main page's frame (0x80058308 when no window is moving):
    the cursor wraps round the 6 x 4 grid (sound 1, the typing restarts), Cross picks,
    Start / Triangle / L2 / R2 close, L1 / R1 close and open the second page."""
    m = g.mem
    if g.pad_repeat & 0x4000:                               # down
        s = m.s32(INV_SLOT); m.w32(INV_SLOT, s + 6)
        if s + 6 >= 0x18: m.w32(INV_SLOT, s - 0x12)
        core.play_sound(g, 1); m.w32(INV_TEXT, 0)
    if g.pad_repeat & 0x1000:                          # up
        s = m.s32(INV_SLOT); m.w32(INV_SLOT, s - 6)
        if s - 6 < 0: m.w32(INV_SLOT, s + 0x12)
        core.play_sound(g, 1); m.w32(INV_TEXT, 0)
    if g.pad_repeat & 0x2000:                          # right
        s = m.s32(INV_SLOT); m.w32(INV_SLOT, s + 1)
        if s + 1 == ((s + 1) // 6) * 6: m.w32(INV_SLOT, s - 5)
        core.play_sound(g, 1); m.w32(INV_TEXT, 0)
    if g.pad_repeat & 0x8000:                          # left
        s = m.s32(INV_SLOT)
        m.w32(INV_SLOT, s + 5 if s == (s // 6) * 6 else s - 1)
        core.play_sound(g, 1); m.w32(INV_TEXT, 0)
    if g.pad_repeat & core.confirm_bit(g):             # Cross (JP confirm: Square)
        if m.s32(INV_SLOT) >= 6: inv_pick_item(g)
        else: inv_pick_weapon(g)
    hook = getattr(g, 'inv_circle', None)              # (the remake's Mods > Magic & weapon swapping: Circle)
    if hook is not None: hook()
    if g.pad_repeat & core.close_bits(g):                           # Start, Triangle (JP confirm: Cross), L2, R2
        calls.call(g, 0x80057344); calls.call(g, 0x800599A4); calls.call(g, 0x8004D24C)
    if g.pad_repeat & 0xC:                             # L1, R1: the second page
        calls.call(g, 0x80057344); g.mode_flags |= 8; calls.call(g, 0x800599A4); m.w32(SWITCH, 1)


def sub_input(g):
    """The input part of the second page's frame (0x80054CA8): the cursor follows the
    neighbour tables (sound 1); Start / Triangle / L2 / R2 close; L1 / R1 back to the first page."""
    m = g.mem
    for bit, k in ((0x2000, 'R'), (0x8000, 'L'), (0x1000, 'U'), (0x4000, 'D')):
        if g.pad_repeat & bit:
            m.w32(0x801E68D8, 0)
            m.w32(0x801E6884, m.s32(SUB_NEXT[k] + 4 * m.s32(0x801E6884)))
            core.play_sound(g, 1)
    if g.pad_repeat & core.close_bits(g):
        calls.call(g, 0x80053F5C); calls.call(g, 0x800599A4); calls.call(g, 0x8004D24C)
    if g.pad_repeat & 0xC:
        calls.call(g, 0x80053F5C); g.mode_flags |= 8; calls.call(g, 0x800599A4); m.w32(SWITCH, 2)


# ------------------------------------------------------------------ windows sliding in and out
def _cdiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


@port(0x80048CF8, ret=True)
def slide(g, win, sl):
    """One frame of a window's slide (sl: +0 tick, +4 length 15, +8 steps left (2), +0xC start
    x / y, +0x10 end x / y): moves the window config win (x, y at +0 / +2, columns / rows at
    +4 / +6, the sprite list of this frame's buffer at +8 / +0xC) and its 8x8 cells.
    Returns 1 once it has finished (tick = length gives the end position twice first)."""
    m = g.mem
    if m.s32(sl + 8) == 0: return 1
    t = m.s32(sl); sp = m.s32(sl + 4)
    if t != sp:
        sx = m.s16(sl + 0xC)
        m.w16(win, sx + _cdiv(core.s32((m.s16(sl + 0x10) - sx) * t), sp))
        sy = m.s16(sl + 0xE); t = m.s32(sl); sp = m.s32(sl + 4)
        m.w16(win + 2, sy + _cdiv(core.s32((m.s16(sl + 0x12) - sy) * t), sp))
        m.w32(sl, m.s32(sl) + 1)
    else:
        m.w16(win, m.u16(sl + 0x10)); m.w16(win + 2, m.u16(sl + 0x12))
        m.w32(sl + 8, m.s32(sl + 8) - 1)
    prim = m.u32(win + 8 + 4 * m.s32(0x801E5F38))
    y = m.s16(win + 2)
    while y < m.s16(win + 6) * 8 + m.s16(win + 2):
        x = m.s16(win)
        while x < m.s16(win + 4) * 8 + m.s16(win):
            m.w16(prim + 8, x); m.w16(prim + 0xA, y)
            prim += 0x14; x += 8
        y += 8
    return 0


def _norm(m, win, i):
    """A window coordinate as the slides use it (a negative one is counted from the far side)."""
    v = m.s16(win + 2 * i)
    return core.s16(v - m.s16(win + 4 + 2 * i) * 8) if v < 0 else v


# the main page's windows (slide records from 0x80152BE8) and the second page's (from 0x801E6494):
# (window config, where it comes from / goes to: 'L' left, 'R' right (x 0x140), 'B' bottom (y 0xF0))
MAIN_WINDOWS = [(0x800B7710, 'L'), (0x800BA1C8, 'L'), (0x800BAD18, 'R'), (0x800BB868, 'R'),
                (0x800BB878, 'R'), (0x800BBCC0, 'R'), (0x8009EE24, 'B')]
SUB_WINDOWS = [(0x800B14CC, 'L'), (0x800B2544, 'L'), (0x800B3094, 'R'), (0x800B3BE4, 'R'),
               (0x800B46E4, 'R'), (0x8009EE24, 'B'), (0x800BBCC0, 'R')]
MAIN_SLIDES, SUB_SLIDES = 0x80152BE8, 0x801E6494


def _away(m, win, side):
    if side == 'L': return core.s16(~(m.s16(win + 4) * 8)), _norm(m, win, 1)
    if side == 'R': return 0x140, _norm(m, win, 1)
    return _norm(m, win, 0), 0xF0


def _slides_in(g, windows, base):
    m = g.mem
    for i, (win, side) in enumerate(windows):
        sl = base + 0x1C * i
        m.w32(sl + 8, 2); m.w32(sl + 4, 0xF); m.w32(sl, 0)
        ax, ay = _away(m, win, side)
        m.w16(sl + 0xC, ax); m.w16(sl + 0xE, ay)
        m.w16(sl + 0x10, _norm(m, win, 0)); m.w16(sl + 0x12, _norm(m, win, 1))
        m.w16(sl + 0x18, m.u16(win)); m.w16(sl + 0x1A, m.u16(win + 2))


def _slides_out(g, windows, base):
    m = g.mem
    for i, (win, side) in enumerate(windows):
        sl = base + 0x1C * i
        m.w32(sl + 8, 2); m.w32(sl, 0); m.w32(sl + 4, 0xF)
        m.w16(sl + 0xC, _norm(m, win, 0)); m.w16(sl + 0xE, _norm(m, win, 1))
        ax, ay = _away(m, win, side)
        m.w16(sl + 0x10, ax); m.w16(sl + 0x12, ay)


@port(0x80056A38, ret=True)
def inv_open(g, task):
    """Task 6 starts (the main page): the windows slide in from the sides over 15 frames,
    the world stops (mode flag 8); then 0x80058308 runs every frame."""
    m = g.mem
    m.w32(INV_FLAGS, 5); m.w32(INV_TEXT, 0)
    g.mode_flags |= 8
    _slides_in(g, MAIN_WINDOWS, MAIN_SLIDES)
    m.w32(m.u32(task) + 0x14, 0x80058308)
    return 1


@port(0x80057344, ret=True)
def inv_close(g):
    """The main page's windows slide out (sound 5)."""
    g.mem.w32(INV_FLAGS, g.mem.s32(INV_FLAGS) | 2)
    core.play_sound(g, 5)
    _slides_out(g, MAIN_WINDOWS, MAIN_SLIDES)
    return 1


@port(0x800551B0, ret=True)
def sub_open(g, task=0):
    """Task 4 starts (the second page: key items, armour, boots, rings)."""
    m = g.mem
    m.w32(SUB_FLAGS, 5); m.w32(0x801E68D8, 0)
    g.mode_flags |= 8
    _slides_in(g, SUB_WINDOWS, SUB_SLIDES)
    calls.call(g, 0x800548B0, 0, m.s16(0x8009EE24)); calls.call(g, 0x800548B0, 1)
    return 1


@port(0x80053F5C, ret=True)
def sub_close(g):
    core.play_sound(g, 5)
    g.mem.w32(SUB_FLAGS, g.mem.s32(SUB_FLAGS) | 2)
    _slides_out(g, SUB_WINDOWS, SUB_SLIDES)
    return 1


def _page_frame(g, task, flags_addr, windows, base, order, switch_bit, inputs, draw, pre=None):
    """The shared shape of 0x80058308 / 0x80054CA8."""
    m = g.mem
    if pre: pre(g)
    if m.s32(flags_addr) & 6:
        r = 0
        for i in order: r = slide(g, windows[i][0], base + 0x1C * i)
        if r == 1:
            f = m.s32(flags_addr)
            if f & 4: m.w32(flags_addr, f & ~4)
            if m.s32(flags_addr) & 2:
                m.w32(flags_addr, 0)
                for i, (win, side) in enumerate(windows):
                    m.w16(win, m.u16(base + 0x1C * i + 0x18)); m.w16(win + 2, m.u16(base + 0x1C * i + 0x1A))
                if not (m.s32(SWITCH) & switch_bit): g.mode_flags &= ~8
                task_end(g, task)
                return 1
    else:
        inputs(g)
    draw(g)
    return 1


@port(0x80048BD0, ret=True)
def task_end(g, task):
    """The running UI task stops (its flags word cleared)."""
    g.mem.w16(g.mem.u32(task), 0)
    return 1


def _inv_draw(g):
    m = g.mem; k = 4 * m.s32(INV_SLOT)
    calls.call(g, 0x80052070, 0x801531C0, m.s16(0x800B7710) + m.s32(0x800BBD90 + k) + 0x12,
               m.s16(0x800B7712) + m.s32(0x800BBDF0 + k) - 8, m.s32(0x801E5F38))       # the cursor
    calls.call(g, 0x800521D0, 0x801531C0)
    calls.call(g, 0x8005887C); calls.call(g, 0x80058DB0)
    for w in (0x800B7710, 0x800BA1C8, 0x800BAD18, 0x800BB868, 0x800BB878, 0x800BBCC0, 0x8009EE24):
        calls.call(g, 0x80057A98, w)
    calls.call(g, 0x80058030); calls.call(g, 0x80057D30)


def _sub_draw(g):
    m = g.mem; k = 4 * m.s32(SUB_SLOT)
    w = m.u32(0x800B6320 + k)
    calls.call(g, 0x80052070, 0x801E6854, m.s16(w) + m.s32(0x800B61D0 + k), m.s16(w + 2) + m.s32(0x800B6208 + k), m.s32(0x801E5F38))
    calls.call(g, 0x800521D0, 0x801E6854)
    calls.call(g, 0x80054AC0, 0, 0x800B3094); calls.call(g, 0x80054AC0, 1, 0x800B3BE4)
    calls.call(g, 0x80054938, 0, 0x800B46E4); calls.call(g, 0x80054938, 1, 0x800B46E4)
    calls.call(g, 0x80054768, 0x800B14CC); calls.call(g, 0x800545E8, 0x800B2544)
    for w in (0x800B14CC, 0x800B2544, 0x800B3094, 0x800B3BE4, 0x800B46E4, 0x8009EE24, 0x800BBCC0):
        calls.call(g, 0x80054BF0, w)
    calls.call(g, 0x80055AFC); calls.call(g, 0x80055EA4)


@port(0x80058308, ret=True)
def inv_frame(g, task):
    """Task 6, every frame: the slides, else the input; then the cursor, icons, names, windows."""
    return _page_frame(g, task, INV_FLAGS, MAIN_WINDOWS, MAIN_SLIDES, (0, 1, 2, 3, 4, 6, 5), 1, inv_input, _inv_draw)


@port(0x80054CA8, ret=True)
def sub_frame(g, task):
    """Task 4, every frame (the second page)."""
    def gpu(g):                                             # the draw environment of this frame's buffer
        calls.call(g, 0x80088230, calls.STACK)
        calls.call(g, 0x800882D8, 0x801E6760 + 0xC * g.mem.s32(0x801E5F38), calls.STACK)
    return _page_frame(g, task, SUB_FLAGS, SUB_WINDOWS, SUB_SLIDES, (1, 2, 3, 4, 5, 6, 0), 2, sub_input, _sub_draw, gpu)


# ------------------------------------------------------------------ the UI tasks
TASKS, TASK_TEMPLATES, CUR_TASK = 0x80107570, 0x800A9184, 0x801533B4


@port(0x80048EBC, ret=True)
def task_start(g, n):
    """UI task n (0-12; 4 = the menu's second page, 6 = its main page) starts: its record
    (0x1C bytes at 0x80107570 + n * 0x1C: +0 flags (bit 0 running), +0x10 start routine,
    +0x14 frame routine) is copied from the template table 0x800A9184 and its start routine
    runs."""
    m = g.mem
    if not n < 0xD: return 0
    rec = TASKS + 0x1C * n
    m.w32(0x8012E298, n); m.w32(CUR_TASK, rec)
    for k in range(7): m.w32(rec + 4 * k, m.u32(TASK_TEMPLATES + 0x1C * n + 4 * k))
    t = m.u32(CUR_TASK)
    m.w16(t, m.u16(t) | 1)
    fn = m.u32(t + 0x10)
    if fn: calls.call(g, fn, CUR_TASK)
    return 1


@port(0x80048BB0, ret=True)
def task_running(g, n):
    """Bit 0 of task n's flags."""
    return g.mem.u16(TASKS + 0x1C * n) & 1


def run_tasks(g):
    """The task part of 0x80048FB0: every running task's frame routine, then the switch
    between the menu's pages once the closing one has gone."""
    m = g.mem
    for n in range(0xD):
        rec = TASKS + 0x1C * n
        m.w32(CUR_TASK, rec)
        if m.u16(rec) & 1:
            fn = m.u32(rec + 0x14)
            if fn and calls.resolve(fn) is not None: calls.call(g, fn, CUR_TASK)
    s = m.s32(SWITCH)
    if s:
        if s == 1 and m.u16(TASKS + 0x1C * 6) == 0:
            m.w32(SWITCH, 0); open_second_page(g)
        if m.s32(SWITCH) == 2 and m.u16(TASKS + 0x1C * 4) == 0:
            m.w32(SWITCH, 0); open_inventory(g)


def _portrait_fly_in(g):
    """Alundra's portrait (image record 0x80059958(0): +0 palette bits, +1 frame, +2 / +3 u, v)
    flies from him to the corner the menu keeps it in."""
    img = calls.call(g, 0x80059958, 0)
    m = g.mem; p = 0x801AC6F8 + 0x114
    calls.call(g, 0x80059A78, p, p + 4, p + 8, 0x801EF434, 0x801EF438, m.u8(img + 2), m.u8(img + 3),
               m.u16(0x8012E360 + 2 * m.u8(img + 1)), m.u16(0x801F2E10 + 2 * ((g.ent[0].f_1B0 + (m.u8(img) & 7)) & 0xFFFFFFFF)))


@port(0x80053EA8, ret=True)
def open_second_page(g):
    calls.call(g, 0x8004D1B8)
    task_start(g, 4)
    _portrait_fly_in(g)
    core.play_sound(g, 4)
    return 1


@port(0x800571D4, ret=True)
def open_inventory(g):
    """Start: the menu opens (unless it is open, or a message / yes-no window is: tasks 0 and
    0xB) - the HUD slides away, Alundra's portrait flies to the corner, sound 4.  (The debug
    build's direction + Start shortcuts are not reachable: 0x800AA118 is 0.)  Returns 1; 0
    would ask for a map change."""
    m = g.mem
    if m.s32(INV_FLAGS) != 0: return 1
    if task_running(g, 0) or task_running(g, 0xB): return 1
    calls.call(g, 0x8004D1B8)
    task_start(g, 6)
    _portrait_fly_in(g)
    calls.call(g, 0x800579D0)
    core.play_sound(g, 4)
    return 1


def start_check(g):
    """The end of GameFrame (0x8002BD9C): the menu timer counts down; Start / L2 / R2 open the
    menu when nothing holds Alundra (mode flags 0, not frozen, no item in use, timer 0, Select
    not held)."""
    m = g.mem
    t = m.s32(0x801EFBF8)
    if t: m.w32(0x801EFBF8, t - 1)
    if g.mode_flags != 0 or g.ent[0].frozen or g.item_use != 0: return
    if not g.pad_pressed & 0x803: return
    if m.s32(0x801EFBF8) != 0 or g.pad_held & 0x100: return
    if open_inventory(g) == 0: g.warp_request = 1
