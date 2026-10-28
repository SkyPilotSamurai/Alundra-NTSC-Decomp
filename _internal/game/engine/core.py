"""Shared helpers of the game code: the random generator, effect records, sounds."""
from .registry import port

M32 = 0xFFFFFFFF


def s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def u16(v): return v & 0xFFFF


def u8(v): return v & 0xFF


def s8(v):
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v


class S16List(list):
    """Entity+0x280 ai[10]: halfwords, stored wrapped and read signed (lh) like the game."""
    def __setitem__(self, i, v):
        list.__setitem__(self, i, [s16(x) for x in v] if isinstance(i, slice) else s16(v))


class U8List(list):
    """Entity+0x274 bytes[4]: stored wrapped to a byte (sb / lbu)."""
    def __setitem__(self, i, v):
        list.__setitem__(self, i, [x & 0xFF for x in v] if isinstance(i, slice) else v & 0xFF)


def next_seed(g):
    """seed = seed * 0x7D2B89DD + 0xE06A02E7 (inlined everywhere)."""
    g.rng_seed = (g.rng_seed * 0x7D2B89DD + 0xE06A02E7) & M32
    return g.rng_seed


def rnd(g, n):
    """(new seed * n) >> 32, unsigned (multu / mfhi)."""
    return (next_seed(g) * (n & M32)) >> 32


def hi(x, n):
    """multu x, n; mfhi."""
    return ((x & M32) * (n & M32)) >> 32


@port(0x8002FC94, ret=True)
def approach(v, target, step):
    """Move v toward target by at most step (unsigned compare of the distance)."""
    d = s32(target - v)
    if (abs(d) & M32) >= (step & M32):
        return s32(v + step) if d > 0 else s32(v - step)
    return target


# ---- effects (0x80133990: 128 records of 0x80 bytes, free when .state == 0)
@port(0x8003C31C, ret='ptr')
def alloc_effect(g):
    for e in g.fx:
        if e.state == 0: return e
    return None


def _effect_fields():
    from .layout import EFFECT
    return [n for n in EFFECT if n != 'slot']


@port(0x8003C46C)
def init_effect(g, e, is_map, anim, mode, bank_map, index, sub, x, y, z):
    """Copies the blank record (0x801C4740, zeros) over e keeping its slot word, then
    fills it.  (is_map, anim): a sprite animation instead of an effect bank entry."""
    reset_effect(e)
    e.is_map = is_map
    e.spr_anim = anim if is_map else -1
    e.state = 2
    e.nindex = (~index) & 0xFF
    e.mode = mode
    e.b6c = 1 if bank_map else 0
    e.b6d = 0 if bank_map else 1
    e.index = index & 0xFF
    e.b70 = sub & 0xFF
    e.b71 = (~sub) & 0xFF
    e.x, e.y, e.z = s32(x), s32(y), s32(z)
    hook = getattr(g, 'effect_started', None)
    if hook: hook(e)                   # the remake: picture bank and first frame


def reset_effect(e):
    for n in _effect_fields(): setattr(e, n, None if n == 'entity' else 0)


@port(0x8003C760, ret='ptr')
def spawn_effect(g, bank_map, index, sub, x, y, z):
    """CreateEffectEntity: a free effect record playing effect `index` of the global
    (bank_map 0) or map bank, at x, y, z (16.16)."""
    e = alloc_effect(g)
    if e is not None:
        init_effect(g, e, 0, -1, 0, bank_map, index, sub, x, y, z)
    return e


@port(0x8003C80C, ret='ptr')
def spawn_effect_on(g, bank_map, index, sub, ent, mode60, ox, oy, oz):
    """An effect that follows an entity (mode 1) at an offset."""
    e = alloc_effect(g)
    if e is not None:
        init_effect(g, e, 0, -1, 1, bank_map, index, sub, ent.px, ent.py, ent.pz)
        e.entity = ent; e.arg60 = mode60; e.ox = ox; e.oy = oy; e.oz = oz
        hook = getattr(g, 'effect_started', None)
        if hook: hook(e)
    return e


@port(0x80039A84)
def random_poofs(g, x, y, z):
    """CreateRandomPoofs: three puffs (global effect 9) at a hit, each flying off at a random
    velocity of -1 .. +1 pixel a frame on x, y and z (the game's random numbers)."""
    for _ in range(3):
        e = spawn_effect(g, 0, 9, 0, x, y, z)
        if e is not None:
            e.vx = s32(rnd(g, 0x20001) - 0x10000)
            e.vy = s32(rnd(g, 0x20001) - 0x10000)
            e.vz = s32(rnd(g, 0x20001) - 0x10000)


def confirm_bit(g):
    """The menus' confirm button: Cross (0x40) as the US / EU game, or Square (0x80) with the
    remake's Controls > Confirm button = JP."""
    s = getattr(g, 'settings', None)
    return 0x80 if s and s.get('confirm') == 'jp' else 0x40


def close_bits(g):
    """The inventory pages' close buttons: Start, L2, R2 and Triangle as the US / EU game, or
    Cross in place of Triangle with the remake's Controls > Confirm button = JP."""
    s = getattr(g, 'settings', None)
    return 0x843 if s and s.get('confirm') == 'jp' else 0x813


@port(0x8004A128, mock_always=True)
def play_sound(g, n):
    """PlaySound: presentation only (no game state).  The remake hooks g.sound."""
    snd = getattr(g, 'sound', None)
    if snd is not None and not hasattr(g, 'ram'): snd(n)
