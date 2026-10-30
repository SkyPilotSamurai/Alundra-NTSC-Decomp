"""Mods > L / R swapping and Magic & weapon swapping, after the BizHawk script Alundra_LR_Swap_US.lua
(Alundra Code/Alundra MW and Tracker).

L / R swapping (in play, menu closed): L1 / R1 equip the previous / next weapon group Alundra
has, L2 / R2 choose the previous / next item he has (so L2 / R2 no longer open the menu; Start
still does).  Orders are the script's: weapons sword, bow, flail, ice wand, fire wand, spirit wand
(the menu's weapon row); items as listed in ITEMS.

Magic swapping: the game always uses the best item of a group (0x8004F784 moves the choice to
it), so with a book a scroll can never be chosen; the script hid the book to get round that.
Here a chosen scroll stays chosen (engine/menu.py selected_item), and Circle on a magic slot of
the main menu page switches that magic between scroll and book.  Weapons the same way: the
game always uses a group's best (0x8004F6C0), here a chosen weapon of the group (g.weapon_pick,
group -> item) is used while Alundra has it; Circle on a weapon slot steps through the group's
weapons he has.  L1 / R1 and L2 / R2 cycle the loadout: weapon groups with their picked weapon,
scroll / book pairs as one stop with their picked one (g.magic_last).  The swaps are silent.
"""
from engine import menu as emenu, core

WEAPONS = (1, 3, 2, 4, 5, 6)                 # stats +0xA groups, R1 order (L1 the reverse)
ITEMS = (0x24, 0x29, 0x25, 0x26, 0x27, 0x23,  # herbs, strength tonic / elixir, magic elixir, wonder essence, bomb
         0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32,   # earth, water, fire, wind: scroll, book
         0x20, 0x28, 0x36, 0x3B, 0x1F, 0x34, 0x33, 0x35, 0x37, 0x38)   # capes, charm, glove, bean, rings, refresher
SCROLLS = (0x2B, 0x2D, 0x2F, 0x31)           # each book is its scroll + 1
L1, R1, L2, R2, CIRCLE = 0x4, 0x8, 0x1, 0x2, 0x20


def _stat(g, off): return g.mem.s16(g.mem.u32(emenu.STATS_PTR) + off)


def magic_partner(n):
    """The other magic item of n's pair (scroll <-> book), None if n is not magic."""
    if n in SCROLLS: return n + 1
    if n - 1 in SCROLLS: return n - 1
    return None


def keeps_scroll(g, n):
    """Magic swapping: a chosen scroll is used as itself even with the book."""
    return n in SCROLLS and getattr(g, 'settings', {}).get('magic_swap', False) and emenu.has_item(g, n)


def group_items(g, grp):
    """The weapons (items) of a group Alundra has, in item order."""
    n = g.mem.s32(emenu.ITEM_COUNT)
    return [k for k in range(min(n, 0x80)) if g.mem.s16(emenu.ITEM_REC + 10 * k) == grp and emenu.has_item(g, k)]


def picked_weapon(g, grp):
    """Magic & weapon swapping: the weapon chosen in group grp, None for the game's best."""
    if not getattr(g, 'settings', {}).get('magic_swap', False): return None
    k = getattr(g, 'weapon_pick', {}).get(grp)
    return k if k is not None and emenu.has_item(g, k) else None


def _pick(g, grp, k):
    if not hasattr(g, 'weapon_pick'): g.weapon_pick = {}
    g.weapon_pick[grp] = k
    if _stat(g, 0xA) != grp: emenu.equip(g, grp)
    core.play_sound(g, 1); emenu.names_refresh(g)


def cycle_weapon(g, d):
    """L1 / R1: the previous / next weapon group Alundra has, as loaded out: the weapon picked in
    that group (Magic & Weapon Swap) or its best.  Silent."""
    cur = _stat(g, 0xA); i = WEAPONS.index(cur) if cur in WEAPONS else 0
    for k in range(1, len(WEAPONS) + 1):
        grp = WEAPONS[(i + d * k) % len(WEAPONS)]
        if emenu.best_of_group(g, grp) != -1:
            if grp != cur: emenu.equip(g, grp); emenu.names_refresh(g)   # (equipped_kind keeps the group's pick)
            return


def magic_pick(g, n):
    """The one of a scroll / book pair the loadout holds: the last chosen of the pair if still had,
    else the pair's best (the book)."""
    p = magic_partner(n)
    if p is None: return n
    last = getattr(g, 'magic_last', {}).get(min(n, p))
    if last in (n, p) and emenu.has_item(g, last) and g.settings.get('magic_swap'): return last
    book = max(n, p)
    return book if emenu.has_item(g, book) else min(n, p)


def cycle_item(g, d):
    """L2 / R2: the previous / next item Alundra has; a scroll and its book are one stop, as loaded
    out (magic_pick).  Silent."""
    cur = _stat(g, 0xC)
    stops = []
    for n in ITEMS:
        if not emenu.has_item(g, n): continue
        p = magic_partner(n)
        if p is not None and emenu.has_item(g, p) and n != min(n, p): continue   # (the pair: one stop)
        stops.append(n)
    if not stops: return
    key = lambda n: min(n, magic_partner(n)) if magic_partner(n) is not None and emenu.has_item(g, magic_partner(n)) else n
    keys = [key(n) for n in stops]
    i = keys.index(key(cur)) if cur in ITEMS and emenu.has_item(g, cur) and key(cur) in keys else (-1 if d > 0 else 0)
    n = magic_pick(g, stops[(i + d) % len(stops)])
    if n != cur: emenu.choose_item(g, n); emenu.names_refresh(g)


def play_frame(g):
    """After the pad is read: L1 / R1 / L2 / R2 swap while Alundra is free and the menu shut."""
    if not g.settings.get('swap_lr'): return
    pr = g.pad_pressed & (L1 | R1 | L2 | R2)
    if not pr: return
    g.pad_pressed &= ~(L1 | R1 | L2 | R2)        # (L2 / R2 would open the menu)
    m = g.mem
    if g.mode_flags or g.choice or m.s32(emenu.INV_FLAGS) or g.item_use: return
    if pr & L1: cycle_weapon(g, -1)
    if pr & R1: cycle_weapon(g, 1)
    if pr & L2: cycle_item(g, -1)
    if pr & R2: cycle_item(g, 1)


def menu_circle(g):
    """Magic swapping: Circle on a main-page slot holding magic switches scroll <-> book."""
    if not g.settings.get('magic_swap') or not g.pad_repeat & CIRCLE: return
    m = g.mem; slot = m.s32(emenu.INV_SLOT)
    if slot < 6:                                     # a weapon slot: the next weapon of its group
        grp = {0: 1, 1: 3, 2: 2, 3: 4, 4: 5, 5: 6}[slot]
        ks = group_items(g, grp)
        if not ks: core.play_sound(g, 3); return
        cur = emenu.equipped_kind(g) if _stat(g, 0xA) == grp else None
        _pick(g, grp, ks[(ks.index(cur) + 1) % len(ks)] if cur in ks else ks[0])
        emenu.magic_item_hint(g)
        return
    it = m.s32(emenu.SLOT_ITEM + 4 * slot)
    if it == -1:
        from engine import calls
        it = calls.call(g, m.u32(emenu.SLOT_FN + 4 * slot))
    cur = _stat(g, 0xC)
    if magic_partner(it) is None: return
    pair = {it, magic_partner(it)}
    want = magic_partner(cur) if cur in pair else it
    if want is None or not emenu.has_item(g, want): core.play_sound(g, 3); return
    emenu.choose_item(g, want); core.play_sound(g, 2)
    if not hasattr(g, 'magic_last'): g.magic_last = {}
    g.magic_last[min(want, magic_partner(want))] = want            # (L2 / R2 come back to it)
    emenu.names_refresh(g); emenu.magic_item_hint(g)
