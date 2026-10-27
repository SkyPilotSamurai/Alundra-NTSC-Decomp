"""Breaking things, what they leave, and picking it up (US ALUN_CD.EXE).

Contents: every entity gets them when it is set up (InitializeEntity 0x8003A5F8 ends with
0x80033154): its map record's item (+0x12) unless the record's collection flag (+0x10) is
already set, else its sprite header's (+0x1F); 0x80..0xFF pick one of the 16 items of a row of
the random table 0x80028DB0.  DestroyEntity (0x8003AEE4) drops them (0x800332A8): the item
sprite (global sprite item + 0x1E) pops up at 10 px a frame (+0xB8 and its bounce speed word
+0x284), uncollidable, with the source's collection flag (word +0x280), a 600-frame life for
items whose record +4 is set, and sound 0x54.  Its C255 program (ai_g6.ai_c255) then bounces,
blinks and is picked up: 0x80034614 gives it (gilder, falcons, hearts, life vessel, magic
seeds, or the inventory, which uses some at once when full)."""
from .registry import port
from . import core, menu
from .core import s32, M32

ITEMS = 0x800C7DE4              # 8-byte item records: +0 name, +4 timed, +5 sound, +7 most you can hold
RAND_TABLE = 0x80028DB0         # u8[0x80][16]: the random item rows
DIR_X, DIR_Y = 0x80023654, 0x80023694     # s16[32]: the 32 directions
SPARKLE = 0xE                   # global effect 0xE: the pick-up sparkles


def _rec(g, e):
    """The map record's (collection flag u16 +0x10, contents u8 +0x12), or None for an entity
    with no record.  The remake keeps the record as a dict (maps/NNN/map.json)."""
    a = getattr(e, 'record_addr', 0) or 0
    if a: return g.mem.u16(a + 0x10), g.mem.u8(a + 0x12)
    r = getattr(e, 'record', None)
    if not r: return None
    return r.get('collection_flag', 0) & 0xFFFF, r.get('contents', 0) & 0xFF


def _hdr(g, e, off, name):
    """A byte of the entity's sprite header (+0x1E break effect, +0x1F contents)."""
    a = getattr(e, 'header_addr', 0) or 0
    if a: return g.mem.u8(a + off)
    return getattr(e, name, 0) or 0


def _flag_word(n):
    return ((0x801E6378 if n & 0x8000 else 0x801DD334) + ((n >> 3) & 0xFFC)) & M32


@port(0x80033084, ret=True)
def choose_item(g, n):
    """An item number (1..0x61, else 0); 0x80 + row: one of the 16 items of that row of the
    random table, picked with the game's generator (and again while it names a row)."""
    while n < 0x100:
        if not n & 0x80:
            return n if n < 0x62 else 0
        k = core.rnd(g, 16)
        n = g.mem.u8(RAND_TABLE + (n & 0x7F) * 16 + k)
    return 0


@port(0x8004F45C, ret=True)
def magic_max(g):
    return g.mem.s16(menu._stats(g) + 6)


@port(0x80033118, ret=True)
def item_useless(g, n):
    """Magic items (0x26 and the seeds 0x51 / 0x52) are not dropped before Alundra has magic."""
    if n == 0x26 or ((n - 0x51) & M32) < 2:
        return int(magic_max(g) == 0)
    return 0


@port(0x80033154)
def init_contents(g, e):
    """InitializeContents: Entity+0x40 = the record's collection flag (0 if it is 0x800 or
    more, bit 15 aside), Entity+0x3C = the chosen item."""
    r = _rec(g, e)
    if r is None:
        e.contents_flag = 0
        n = _hdr(g, e, 0x1F, 'header_contents')
    else:
        flag, item = r
        if (flag & 0x7FFF) >= 0x800: flag = 0
        e.contents_flag = flag
        if flag and g.mem.u32(_flag_word(flag)) & (1 << (flag & 31)):
            n = 0
        elif item:
            n = item
        else:
            n = _hdr(g, e, 0x1F, 'header_contents')
    e.contents_item = choose_item(g, n)


@port(0x80033240)
def set_flag(g, n):
    """A collection flag is set (game flags, or map flags with bit 15)."""
    n &= M32
    if n == 0: return
    sn = s32(n)
    v = sn if sn >= 0 else sn + 31
    bit = (sn - ((v >> 5) << 5)) & 31
    a = _flag_word(n)
    g.mem.w32(a, g.mem.u32(a) | (1 << bit))


def _pop(g, n, x, y, z, flag):
    """The item entity both drops make (0x800332A8 / 0x80033390)."""
    from . import entity
    t = entity.spawn_warp_entity(g, None, 0, n + 0x1E, x, y, z, 0)
    if t is None: return 0
    t.fz = 0xA0000
    t.bytes[0] = 1; t.bytes[1] = 0; t.bytes[2] = 0; t.bytes[3] = 0     # word +0x274 = 1: dropped
    t.flags = s32(t.flags & ~0x80)
    t.delay = 600 if g.mem.u8(ITEMS + 4 + n * 8) else -1               # +0x278: timed items vanish
    t.item_state = 0                                                    # +0x27C
    if flag is not None:
        _wai_set(t, 0, flag)                                            # +0x280: the collection flag
    _wai_set(t, 2, 0xA0000)                                             # +0x284: the bounce speed
    if flag is None:
        _wai_set(t, 0, 0)
    core.play_sound(g, 0x54)
    return 1


def _wai_set(e, k, v):
    e.ai[k] = v & 0xFFFF; e.ai[k + 1] = (v >> 16) & 0xFFFF


@port(0x800332A8, ret=True)
def spawn_contents(g, e):
    """SpawnEntityContents: the entity's contents pop out where it is (1 = something came out)."""
    n = e.contents_item
    if n == 0 or item_useless(g, n): return 0
    return _pop(g, n, e.px, e.py, e.pz, e.contents_flag)


@port(0x80033390, ret=True)
def block_drop(g, n, x, y, z):
    """What a broken block leaves (called with 0xFF: row 0x7F of the random table) at x, y, z."""
    n = choose_item(g, n)
    if n == 0 or item_useless(g, n): return 0
    return _pop(g, n, x, y, z, None)


def _end_destroy(g, e, effect):
    e.estatus = 4
    e.action = -1
    sh = getattr(e, 'shadow', None)
    if sh is not None:
        if hasattr(sh, 'state'): sh.state = 0
        e.shadow = None
    if effect == -1:
        effect = _hdr(g, e, 0x1E, 'break_effect')
    if effect:
        core.spawn_effect_on(g, 0, effect, 0, e, 1, 0, 0, 0)
    h = getattr(e, 'holder', None)
    if h is not None: h.carried = None


@port(0x8003AEE4)
def destroy_entity(g, e, effect):
    """DestroyEntity: its contents drop, status 4 (gone next frame), action -1, its shadow is
    freed, the break effect plays on it (effect -1: the sprite header's +0x1E), and whoever
    held it lets go."""
    spawn_contents(g, e)
    _end_destroy(g, e, s32(effect))


@port(0x8003AF90)
def destroy_tree(g, e, effect):
    """DestroyEntity for e and, first, every entity (status 1-3) whose parent it is."""
    n = g.ent_count
    if n >= 0:
        for i in range(0, n + 1):
            c = g.ent[i]
            st = c.estatus
            if (((st - 1) & M32) < 2 or st == 3) and getattr(c, 'parent', None) is e:
                destroy_tree(g, c, effect)
    spawn_contents(g, e)
    _end_destroy(g, e, s32(effect))


# ------------------------------------------------------------------ picking up
@port(0x80034458, ret=True)
def can_take(g, n):
    """A chest's item can be taken: 1 for most; herbs .. elixirs (0x24-0x27, 0x29) only while
    Alundra holds fewer than the most (item record +7)."""
    if n < 0x28:
        if n < 0x24:
            return 1 if n != 0 else 0
    elif n != 0x29:
        return 1
    return int(menu.has_item(g, n) < g.mem.u8(ITEMS + 7 + n * 8))


@port(0x800345DC, ret=True)
def stored(g, n):
    """One more of item n in the inventory: 1 when the count went up."""
    before = menu.has_item(g, n)
    return int(before < menu.give_item(g, n))


@port(0x8004F668)
def gilder_add(g, n):
    menu.set_gilder(g, n + g.mem.s16(menu._stats(g) + 8))


@port(0x8004FDB4)
def falcon_add(g, n):
    st = menu._stats(g)
    v = (g.mem.u16(st + 0xE) + n) & 0xFFFF
    g.mem.w16(st + 0xE, v)
    if core.s16(v) >= 0x33: g.mem.w16(st + 0xE, 0x32)
    g.mem.w32(0x801DD3E8, g.mem.u32(0x801DD3E8) | 0x400)                # (flag 0x55A: a falcon was found)


@port(0x8004F59C)
def magic_add(g, n):
    menu.magic_set(g, n + g.mem.s16(menu._stats(g) + 4))


@port(0x8004F4D0)
def magic_max_add(g, n):
    menu.magic_set_max(g, n + g.mem.s16(menu._stats(g) + 6))


def _player_fx(g, sub, dz):
    p = g.ent[0]
    return core.spawn_effect(g, 0, SPARKLE, sub, p.px, p.py, s32(p.pz + dz))


def _sparkles(g, sub, vz, n=4):
    """n sparkles at random speeds (x: -1..+1 px, y: -1.5..+1.5 px a frame) rising at vz."""
    for _ in range(n):
        fx = _player_fx(g, sub, 0x100000)
        if fx is None: continue
        r1 = core.next_seed(g)
        r2 = core.next_seed(g)
        fx.vz = vz
        fx.vx = s32(core.hi(r1, 0x20001) + 0xFFFF0000)
        fx.vy = s32(core.hi(r2, 0x30001) + 0xFFFE8000)


def _ring(g, sub_of, dz):
    """Eight sparkles in a ring a little out from Alundra, flying outward (0x80033980)."""
    d = 8
    for i in range(8):
        fx = _player_fx(g, sub_of(i), dz)
        if fx is not None:
            k = d & 0x1F
            fx.vz = 0x30000
            fx.x = s32(fx.x + (g_s16(g, DIR_X + 8 * i) << 11))
            fx.vx = s32(g_s16(g, DIR_X + 2 * k) * 0x1C0)
            fx.y = s32(fx.y + (g_s16(g, DIR_Y + 8 * i) << 11))
            fx.vy = s32(g_s16(g, DIR_Y + 2 * k) * 0x1C0)
        d += 4


def _burst(g, sub):
    """Eight sparkles further out, flying inward (0x80033AB0 / 0x80033F24)."""
    for i in range(8):
        fx = _player_fx(g, sub, 0x100000)
        if fx is not None:
            dx = g_s16(g, DIR_X + 8 * i); dy = g_s16(g, DIR_Y + 8 * i)
            fx.x = s32(fx.x + (dx << 13)); fx.vx = s32(dx * -0x200)
            fx.y = s32(fx.y + (dy << 13)); fx.vy = s32(dy * -0x200)


def g_s16(g, a):
    from . import rodata
    return rodata.s16(a)


def _heal(e, add):
    mx = e.hp_max
    e.hp = mx if mx < e.hp + add else e.hp + add


@port(0x8003353C)
def heart_small(g, e):
    """Small heart (0x54): +2 life."""
    _heal(e, 2)


@port(0x80033560)
def herb(g, e):
    """Herbs used at once (0x24): + a quarter of the most life, at least 5; sparkle."""
    _heal(e, max(5, _q(e.hp_max)))
    fx = _player_fx(g, 0, 0x100000)
    if fx is not None: fx.vz = 0x20000


@port(0x800335FC)
def heart_medium(g, e):
    """Medium heart (0x55): + a quarter of the most life, at least 1; sparkle."""
    _heal(e, max(1, _q(e.hp_max)))
    fx = _player_fx(g, 0, 0x100000)
    if fx is not None: fx.vz = 0x20000


def _q(v):
    return (v + 3 if v < 0 else v) >> 2


def _h(v):
    return int(v / 2) if v < 0 else v >> 1


@port(0x80033698)
def heart_large(g, e):
    """Large heart (0x56): + half the most life, at least 5; four sparkles."""
    _heal(e, max(5, _h(e.hp_max)))
    _sparkles(g, 0, 0x20000)


@port(0x8003380C)
def strength_tonic(g, e):
    """Strength elixir used at once (0x29): + half the most life, at least 10; four sparkles."""
    _heal(e, max(10, _h(e.hp_max)))
    _sparkles(g, 0, 0x20000)


@port(0x80033980)
def full_life(g, e):
    """Life to the most (0x25 used at once): a ring of sparkles."""
    e.hp = e.hp_max
    _ring(g, lambda i: 0, 0x80000)


@port(0x80033AB0)
def life_vessel(g, e):
    """Life vessel (0x53): one more life and all of it; sound 0x31, a burst and sparkles."""
    v = s32(e.hp_max + 1)
    e.hp_max = v; e.hp = v
    core.play_sound(g, 0x31)
    _burst(g, 0)
    _sparkles(g, 0, 0x40000)


@port(0x80033CB0)
def magic_seed(g, e=None):
    """Magic seed (0x51 / 0x26 used at once): one more magic; four sparkles."""
    magic_add(g, 1)
    _sparkles2(g)


def _sparkles2(g):
    for _ in range(4):
        fx = _player_fx(g, 2, 0x100000)
        if fx is None: continue
        r1 = core.next_seed(g); r2 = core.next_seed(g)
        fx.vz = 0x20000
        fx.vx = s32(core.hi(r1, 0x20001) + 0xFFFF0000)
        fx.vy = s32(core.hi(r2, 0x30001) + 0xFFFE8000)


@port(0x80033DF0)
def magic_full(g, e=None):
    """Magic to the most (0x52): a ring of sparkles."""
    magic_set_full(g)
    _ring(g, lambda i: 2, 0x80000)


def magic_set_full(g):
    menu.magic_set(g, magic_max(g))


@port(0x80033F24)
def magic_vessel(g, e=None):
    """Magic vessel (0x50): one more magic and all of it; sound 0x36, a burst and sparkles."""
    magic_max_add(g, 1)
    magic_set_full(g)
    core.play_sound(g, 0x36)
    _burst(g, 2)
    for _ in range(4):
        fx = _player_fx(g, 2, 0x100000)
        if fx is None: continue
        r1 = core.next_seed(g); r2 = core.next_seed(g)
        fx.vz = 0x40000
        fx.vx = s32(core.hi(r1, 0x20001) + 0xFFFF0000)
        fx.vy = s32(core.hi(r2, 0x30001) + 0xFFFE8000)


@port(0x80034124)
def wonder_essence(g, e):
    """Wonder essence used at once (0x27): life and magic to the most; a ring and sparkles."""
    e.hp = e.hp_max
    magic_set_full(g)
    _ring(g, lambda i: 2 if not i & 1 else 0, 0x80000)
    for _ in range(4):
        for sub, vz in ((0, 0x40000), (2, 0x20000)):
            fx = _player_fx(g, sub, 0x100000)
            if fx is None: continue
            r1 = core.next_seed(g); r2 = core.next_seed(g)
            fx.vz = vz
            fx.vx = s32(core.hi(r1, 0x20001) + 0xFFFF0000)
            fx.vy = s32(core.hi(r2, 0x30001) + 0xFFFE8000)


@port(0x80034614, ret=True)
def pick_up(g, p, n):
    """Alundra touches dropped item n: its gain.  Herbs .. elixirs go to the inventory, or
    are used at once when it is full.  Returns 1 when the item has no 'timed' mark (record +4
    = 0: a message is shown), else 0."""
    use = {0x24: herb, 0x25: full_life, 0x26: magic_seed, 0x27: wonder_essence, 0x29: strength_tonic}
    if n == 0: return 0
    if n in use:
        if stored(g, n) == 0: use[n](g, p)
    elif n in (0x45, 0x46, 0x47, 0x48):
        gilder_add(g, {0x45: 1, 0x46: 5, 0x47: 10, 0x48: 30}[n])
    elif n == 0x4F: falcon_add(g, 1)
    elif n == 0x50: magic_vessel(g, p)
    elif n == 0x51: magic_seed(g, p)
    elif n == 0x52: magic_full(g, p)
    elif n == 0x53: life_vessel(g, p)
    elif n == 0x54: heart_small(g, p)
    elif n == 0x55: heart_medium(g, p)
    elif n == 0x56: heart_large(g, p)
    else: menu.give_item(g, n)
    return int(g.mem.u8(ITEMS + 4 + n * 8) == 0)


@port(0x800344D4)
def chest_gain(g, p, n):
    """An item from a chest: as pick_up, but every other item goes to the inventory."""
    if n in (0x45, 0x46, 0x47, 0x48): gilder_add(g, {0x45: 1, 0x46: 5, 0x47: 10, 0x48: 30}[n])
    elif n == 0x4F: falcon_add(g, 1)
    elif n == 0x50: magic_vessel(g, p)
    elif n == 0x51: magic_seed(g, p)
    elif n == 0x52: magic_full(g, p)
    elif n == 0x53: life_vessel(g, p)
    elif n == 0x54: heart_small(g, p)
    elif n == 0x55: heart_medium(g, p)
    elif n == 0x56: heart_large(g, p)
    else: menu.give_item(g, n)
