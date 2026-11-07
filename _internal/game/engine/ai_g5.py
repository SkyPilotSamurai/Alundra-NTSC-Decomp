"""Built-in sprite programs, group 5 (US ALUN_CD.EXE 0x8007947C-0x8007D6CC): C50-C64, C83, C86
(boss programs and the things they spawn)."""
from .registry import port
from .core import s32, s16, next_seed, hi
from . import aihelp, core, entity, player, calls
from . import layout as L

M32 = 0xFFFFFFFF


@port(0x80079D54)
def ai_c83(g, e):
    """C83 (things C50 drops): fall until it lands, then lie; when hit (anim 3 done) break and
    tell its parent (ai[4] -= 1); anim 5 waits ai[1] frames before falling."""
    a = e.target_anim
    if a == 3:
        if not e.anim_done: return
        if e.bytes[3]:
            e.target_anim = 4
            e.flags = s32(e.flags | 0x40)
            par = _ptr(g, e.parent)
            par.ai[4] = (par.ai[4] & 0xFFFF) - 1
            return
        if e.collided_z:
            e.target_anim = 0
            return
        e.target_anim = 1
    elif a < 4:
        if a == 1:
            if not s32(e.terrain + 1) < e.pz:
                e.target_anim = 2
                e.flags = s32((e.flags & ~0x4000) | 0x100)
    elif a == 5:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            return
        e.target_anim = 1


@port(0x8007B204)
def ai_c52(g, e):
    """C52: anim 0 plays out then switches to anim bytes[0] (bytes[1] == 1: a random upward
    push); other anims puff a smoke effect every 16 frames."""
    if e.target_anim == 0:
        if not e.anim_done: return
        e.target_anim = e.bytes[0]
        if e.bytes[1] == 1:
            s = next_seed(g)
            e.fz = s32((hi(s, 9) << 11) + 0xFFFE8000)
    else:
        t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
        e.ai[1] = t
        if t & 0xF: return
        f = core.spawn_effect(g, 1, 0, 0, e.px, e.py, e.pz)
        if f is not None: f.vz = 0x10000


@port(0x8007CCDC)
def ai_c57(g, e):
    """C57: does nothing."""
    return


@port(0x8007D0D4)
def ai_c60(g, e):
    """C60 (map 309): every 4th frame an effect (0x11 for sprites 11-12, raised 8 px, else 0x12)
    flying opposite to the entity's own force."""
    if e.frame_counter & 3: return
    k = 1 if ((e.sprite_index - 0xB) & M32) < 2 else 0
    f = core.spawn_effect(g, 0, 0x11 if k else 0x12, 0, e.px, e.py, s32(e.pz + (k << 19)))
    if f is not None:
        f.vx = s32(-e.fx); f.vy = s32(-e.fy); f.vz = s32(-e.fz)


@port(0x8007D18C)
def ai_c61(g, e):
    """C61: breaks the breakable blocks its attack box touches."""
    player.break_blocks(g, e)


# ---- shared bits
INIT = 0x801F0074           # word: the boss program set itself up (cleared on map load)
SHAKE = 0x801F94D0          # screen shake: on, amplitude x / y (0x801F94D4 / D8), 0x801F94DC / E0
EVFLAGS = 0x801E6378        # event flags the boss programs raise (1: defeated ...)
DX, DY = 0x80023654, 0x80023694     # s16[32]: direction -> unit step x / y


def _fx_addr(f):
    if f is None: return 0
    if isinstance(f, _AtFx): return f.addr
    return L.FX_BASE + f.slot * L.FX_SIZE


def _fx_at(g, a):
    """The effect record at RAM address a (None for 0 or anything else)."""
    a &= M32
    if L.FX_BASE <= a < L.FX_BASE + L.FX_SIZE * L.FX_COUNT and not (a - L.FX_BASE) % L.FX_SIZE:
        return g.fx[(a - L.FX_BASE) // L.FX_SIZE]
    return None


def _fx_pos(g, a, x, y, z):
    """Stores x, y, z into the effect record whose address the game keeps at a word."""
    f = _fx_at(g, a)
    if f is not None:
        f.x, f.y, f.z = x, y, z
    else:                                       # no record (0): the game writes there anyway
        g.mem.w32(a + 0x3C, x); g.mem.w32(a + 0x40, y); g.mem.w32(a + 0x44, z)


def _shake(g, ax, ay):
    """Screen shake on with amplitudes ax, ay."""
    g.mem.w32(SHAKE + 4, ax); g.mem.w32(SHAKE + 8, ay)
    g.mem.w32(SHAKE, 1); g.mem.w32(SHAKE + 0xC, 1); g.mem.w32(SHAKE + 0x10, 1)


# ---- C50
C50_FX = 0x801247D8         # effect address (the glow that follows the boss)
C50_T1, C50_T2 = 0x801247DC, 0x801247E0     # s16 countdowns to the next shake


@port(0x8007947C)
def ai_c50(g, e):
    """C50 (a boss that comes down the map after Alundra): reaching tile rows 25 / 53 switches
    it to anims 10 / 11 (11 raises event flag 1); its moves (anims 2-7, picked from tables,
    the fastest when Alundra is 15+ rows ahead) shake the screen on table timers, dust flies
    and rubble (effect 0x16) falls; every 180 frames (120 when he is far) a row of rocks
    (C83, map sprites of 0x80027CEC) drops ahead, at most 13 alive (ai[4]).  A light effect
    follows it.  Pushing against Alundra stops it."""
    m = g.mem; p = g.ent[0]
    if m.s32(INIT) == 0:
        f = core.spawn_effect(g, 1, 1, 0, e.px, e.py, e.pz)
        m.w32(C50_FX, _fx_addr(f))
        m.w32(INIT, 1)
        e.item_state = 0x78
        m.w16(C50_T2, 0); m.w16(C50_T1, 0)
    _fx_pos(g, m.u32(C50_FX), e.px, e.py, s32(e.pz + 0x400000))
    if e.bytes[0] == 0 and not e.tile_y < 0x19:
        e.bytes[0] = 1; e.target_anim = 0xA; e.ai[1] = 0x1E
    if e.bytes[0] == 1 and not e.tile_y < 0x35:
        e.bytes[0] = 2; e.target_anim = 0xB
        m.w32(SHAKE, 0); e.delay = 0
    d = e.delay
    if d:
        d = s32(d - 1); e.delay = d
        if d == 0: m.w32(SHAKE, 0)
    t1 = m.s16(C50_T1)
    if t1 or m.s16(C50_T2):
        go = 0
        if t1:
            m.w16(C50_T1, t1 - 1)
            go = 1 if ((t1 - 1) & 0xFFFF) == 0 else 0
        else:
            t2 = m.s16(C50_T2)
            if t2:
                m.w16(C50_T2, t2 - 1)
                if ((t2 - 1) & 0xFFFF) == 0: go = 1
        if go:
            _shake(g, 2, 2)
            e.delay = 0x1E
    if e.delay in (0x1E, 0x19, 0x14):           # falling rubble, two columns
        for i in range(2):
            x0 = 0xF00000 if i & 1 else 0x1E00000
            s1 = next_seed(g); s2 = next_seed(g)
            f = core.spawn_effect(g, 0, 0x16, 1, s32(x0 + hi(s1, 0xB) * 0xC0000),
                                  s32(p.py + (hi(s2, 0x13) << 19) + 0xFFC00000), 0xA00000)
            if f is not None:
                f.vz = s32((hi(next_seed(g), 5) << 14) + 0xFFFC0000)
    if (e.ai[4] & 0xFFFF) < 0xD and e.target_anim != 8:
        t = s32(e.item_state - 1); e.item_state = t
        if t == 0:
            e.item_state = 0xB4
            if not s32(p.tile_y - e.tile_y) < 0xF: e.item_state = 0x78
            row = 0x80027CEC + hi(next_seed(g), 9) * 0x18
            k = 0; wait = 0
            while True:                        # up to 4 rocks of the row (x, y, sprite)
                if s32(p.tile_y - e.tile_y) < 5 and not (e.ai[4] & 0xFFFF) < 4: break
                if k == 0xC: break
                x = m.s16(row); spr = m.s16(row + 4); y = m.s16(row + 2)
                if spr == 0: break
                x = s32(x * 0x180000 + 0x1500000)
                y = s32(p.py + (y << 20))
                if spr != 0x1F0:
                    x = s32(x + 0xC0000); y = s32(y + 0x80000)
                if 0x33FFFFF < y: break
                c = entity.spawn_warp_entity(g, e, 1, spr - 0x100, x, y, s32(e.pz + 0xA00000), 0)
                if c is not None:
                    c.target_anim = 5; c.ai[1] = wait
                    e.ai[4] = (e.ai[4] & 0xFFFF) + 1
                row += 6; k += 3; wait += 0x14
    rel = aihelp.rel_tile(g, e)
    a = e.target_anim & M32
    dust = 0
    nxt = None                                 # where the switch goes on
    if a < 12:
        if a in (2, 3, 4):
            if e.force_adjusted and e.x_collision is p:
                e.target_anim = 0; e.ai[1] = 0x8C
            else:
                dust = 1
                if e.anim_done: nxt = 0
        elif a in (5, 6, 7):
            if e.force_adjusted and e.x_collision is p:
                e.target_anim = 1; e.ai[1] = 0x8C
            else:
                dust = 1
                if e.anim_done: nxt = 1
        elif a in (0, 1):
            nxt = a
        elif a == 8:
            if aihelp.sees_player(g, e, rel, 3, 0xA, 0x100000):
                e.target_anim = 0; e.ai[1] = 0x28
        elif a == 9:
            m.w32(EVFLAGS, m.u32(EVFLAGS) | 2)
        elif a == 10:
            dust = 1
        elif a == 11:
            m.w32(EVFLAGS, m.u32(EVFLAGS) | 1)
            dust = 1
    if nxt is not None:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
        else:
            far = not s32(p.tile_y - e.tile_y) < 0xF
            if nxt == 0:
                v = 4 if far else m.s16(0x80027CD4 + hi(next_seed(g), 5) * 2)
            else:
                v = 7 if far else m.s16(0x80027CE0 + hi(next_seed(g), 5) * 2)
            e.target_anim = v
            v = e.target_anim
            e.cur_anim = -1
            if v == nxt:                       # rest again
                e.ai[1] = 0x1E
            else:                              # a roll: shake timers from the table
                o = 0x80027DC4 + (v - 2) * 4
                m.w16(C50_T1, m.u16(o)); m.w16(C50_T2, m.u16(o + 2))
    if dust:
        if e.bytes[2] == 0:
            s1 = next_seed(g); s2 = next_seed(g)
            core.spawn_effect(g, 1, 0, 0, s32(e.px + (hi(s1, 0x79) << 16) + 0xFFC40000),
                              s32(e.py + 0x200000), s32(e.pz + (hi(s2, 0x15) << 16)))
            core.play_sound(g, 0x2E)
            e.bytes[2] = 8
        e.bytes[2] = e.bytes[2] - 1


# ---- entity pointers kept in words (ai[2..3], globals)
class _At:
    """An entity record at an address that is no slot of the table (0 or a stale word): the game
    reads and writes through it anyway, and so does the port (through g.mem)."""
    _TAB = L.ENTITY

    def __init__(self, g, a):
        object.__setattr__(self, '_g', g); object.__setattr__(self, 'addr', a & M32)

    def __getattr__(self, n):
        g, a = self._g, self.addr
        if n == 'ai': return _AtList(g, a + 0x280, 2)
        if n == 'bytes': return _AtList(g, a + 0x274, 1)
        o, t = self._TAB[n]
        m = g.mem; guard = m.guard; m.guard = False       # a wild pointer reads whatever is there
        try:
            if t == 'u8': return m.u8(a + o)
            v = m.s32(a + o) if t == 'i32' else m.u32(a + o)
        finally:
            m.guard = guard
        return entity.ent_at(g, v) if t == 'ptr' else v

    def __setattr__(self, n, v):
        o, t = self._TAB[n]
        if t in ('ptr', 'fxptr'): v = _addr(v) if t == 'ptr' else _fx_addr(v)
        m = self._g.mem; guard = m.guard; m.guard = False
        try:
            if t == 'u8': m.w8(self.addr + o, v)
            else: m.w32(self.addr + o, v)
        finally:
            m.guard = guard


class _AtFx(_At):
    """The same for an effect record."""
    _TAB = L.EFFECT


def _fxp(g, a):
    """The effect record a word points at, as the game dereferences it (no NULL check)."""
    f = _fx_at(g, a)
    return f if f is not None else _AtFx(g, a)


def _fxref(g, a):
    """The effect whose address a word holds: None for 0, an _AtFx for a non-record address."""
    a &= M32
    if a == 0: return None
    f = _fx_at(g, a)
    return f if f is not None else _AtFx(g, a)


class _AtList:
    def __init__(self, g, a, sz): self.g, self.a, self.sz = g, a, sz
    def __getitem__(self, i):
        return self.g.mem.s16(self.a + 2 * i) if self.sz == 2 else self.g.mem.u8(self.a + i)
    def __setitem__(self, i, v):
        if self.sz == 2: self.g.mem.w16(self.a + 2 * i, v)
        else: self.g.mem.w8(self.a + i, v)


def _addr(x):
    """Entity -> its RAM address (None -> 0)."""
    if x is None: return 0
    if isinstance(x, _At): return x.addr
    return entity.ent_addr(x)


def _eref(g, a):
    """The entity whose address a word holds (an _At for anything that is not a table slot)."""
    a &= M32
    if L.ENT_BASE <= a < L.ENT_BASE + L.ENT_SIZE * L.ENT_COUNT and not (a - L.ENT_BASE) % L.ENT_SIZE:
        return g.ent[(a - L.ENT_BASE) // L.ENT_SIZE]
    return _At(g, a)


def _ai_word(e, k):
    """lw of ai[k], ai[k + 1] (an address kept in two AI halfwords)."""
    return (e.ai[k] & 0xFFFF) | (e.ai[k + 1] & 0xFFFF) << 16


def _arg(x):
    """An entity for calls.call: the object, or the raw address of an _At."""
    return x.addr if isinstance(x, _At) else x


def _release(g, word):
    """The entity whose address is kept at word (C51's grabbing hand): anim 2, flag 0x40, forgotten."""
    a = g.mem.u32(word)
    if a:
        t = _eref(g, a)
        f = t.flags
        t.target_anim = 2
        g.mem.w32(word, 0)
        t.flags = s32(f | 0x40)


# ---- C51
C51_N = 0x801247F4          # s16: attacks since the last special one
C51_SIDE = 0x801247F0       # s16: wind direction pick (0: choose, else the opposite next)
C51_ROW = 0x801247E4        # s16: which side the bubble row comes from
C51_KIND = 0x801247E8       # s16: kind (bytes[0]) of the next bubble
C51_CNT = 0x801247EC        # s16: bubbles spawned in this volley
C51_HAND = 0x801247F8       # entity address: the hand it holds out (0 none)
C51_FLAGS = 0x801E6384      # bit 0x10: the fight is on


@port(0x80079E4C)
def ai_c51(g, e):
    """C51 (boss of map 325): while event flag 0x10 is up, runs an attack loop chosen at random
    (bubble volleys, a grabbing hand, falling debris, wind that pushes Alundra); hurt (anim 8)
    it counts its partner's hits (ai[2..3] = the partner entity) and finally plays its death."""
    m = g.mem; p = g.ent[0]
    if m.s32(INIT) == 0:
        m.w32(C51_HAND, 0); m.w32(INIT, 1)
        m.w16(C51_N, 0); m.w16(C51_SIDE, 0)
    if e.target_anim == 0 and e.anim_done: e.cur_anim = 0xFF
    if e.target_anim == 1 and e.anim_done: e.cur_anim = 0xFF
    if not m.u32(C51_FLAGS) & 0x10: return
    fp = 0
    d = e.delay
    if d:                                   # quake: shake ends, every 32 frames a new push
        d = s32(d - 1); e.delay = d
        if d == 0:
            m.w32(SHAKE, 0)
        elif not d & 0x1F:
            s = next_seed(g)
            e.ai[4] = 6
            e.bytes[2] = hi(s, 0x20)
        t = e.ai[4] & 0xFFFF
        if t:
            e.ai[4] = t - 1
            if p.on_ground and not p.anim_flags & 0x40:
                p.pafx = m.s16(DX + e.bytes[2] * 2) * 0xC0
                p.pafy = m.s16(DY + e.bytes[2] * 2) * 0xC0
    if e.target_anim == 8:                  # hurt
        _release(g, C51_HAND)
        if not e.anim_done: return
        if e.bytes[3]:                      # beaten: the partner takes over
            q = _eref(g, _ai_word(e, 2))
            e.target_anim = 9
            q.target_anim = 1
            b3 = e.bytes[3]
            q.ai[1] = 0x12C; q.ai[5] = 0x1E; q.bytes[3] = b3
            e.bytes[0] = 5; e.bytes[1] = 0; e.ai[1] = 0
            m.w32(SHAKE, 0)
            return
        if (e.ai[5] & 0xFFFF) == 0 and hi(next_seed(g), 3):
            e.ai[5] = 1; e.target_anim = 6
            if hi(next_seed(g), 2):
                e.bytes[0] = 2; e.bytes[1] = 2
            else:
                e.bytes[0] = 9; e.bytes[1] = 2
        else:
            e.target_anim = 3; e.bytes[0] = 4; e.bytes[1] = 0; e.ai[5] = 0
        e.damaged_tick = 0x5A
        return
    st = e.bytes[0]
    if st == 0:                             # rest, then pick the next attack
        t = e.ai[1] & 0xFFFF
        e.target_anim = 0; e.bytes[1] = 0
        if t:
            e.ai[1] = t - 1
        elif e.anim_done:
            n = (m.u16(C51_N) + 1) & 0xFFFF
            m.w16(C51_N, n)
            if s16(n) < 4:
                k = hi(next_seed(g), 9)
            else:
                s = next_seed(g); m.w16(C51_N, 0)
                k = hi(s, 3) + 4
            if k in (0, 6): e.bytes[0] = 2
            elif k in (1, 8): e.bytes[0] = 1
            elif k in (2, 7): e.bytes[0] = 9
            elif k == 3: e.bytes[0] = 3
            elif k == 4:
                if e.delay == 0:
                    e.bytes[0] = 7; e.target_anim = 0xB; e.ai[1] = 0xA
                else:
                    e.bytes[0] = 1
            elif k == 5:                    # wind
                e.bytes[0] = 8; e.ai[1] = 0x30
                w = m.s16(C51_SIDE)
                if w == 0:
                    k = hi(next_seed(g), 4)
                    e.bytes[1] = m.u8(0x80028AF8 + k)
                    m.w16(C51_SIDE, k + 1)
                else:
                    e.bytes[1] = (m.u8(0x80028AF7 + w) + 0x10) & 0x1F
                    m.w16(C51_SIDE, 0)
    elif st == 1:                           # a volley of bubbles in a fan
        b = e.bytes[1]
        if b == 0:
            e.ai[1] = 0x4E
            s = next_seed(g)
            m.w16(C51_CNT, 0)
            k = hi(s, 3)
            m.w16(C51_ROW, k); m.w16(C51_KIND, k + 2)
            e.target_anim = 4; e.bytes[1] = b + 1
        elif b == 1:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t:
                e.ai[1] = 1; e.bytes[1] = b + 1
        elif b == 2:
            t = e.ai[1] & 0xFFFF
            if t:
                e.ai[1] = t - 1
                if not (t - 1) & 0xFFFF:
                    n = m.s16(C51_CNT)
                    if n < 5: dr = 0xC - n * 2
                    elif n < 0xA: dr = n * 2 - 6
                    else: dr = 0xC - (n - 0xA) * 2
                    c = entity.spawn_warp_entity(g, e, 1, 0x9F, s32(e.px + 0xFFB80000), e.py,
                                                 s32(e.pz + 0x300000), dr)
                    if c is not None:
                        k = m.u16(C51_KIND)
                        c.bytes[1] = 1; c.bytes[0] = k
                    n = (m.u16(C51_CNT) + 1) & 0xFFFF
                    m.w16(C51_CNT, n)
                    n = s16(n)
                    if n == 5:
                        m.w16(C51_KIND, 2 if m.s16(C51_ROW) == 1 else 3)
                    elif n in (0xA, 0xF):
                        m.w16(C51_KIND, 2 if m.s16(C51_ROW) == 2 else 4)
                    else:
                        e.ai[1] = 0xF
            if e.anim_done:
                if m.s16(C51_CNT) == 0xF:
                    b = e.bytes[1]; e.target_anim = 0; e.bytes[1] = b + 1
                else:
                    e.target_anim = 4; e.ai[1] = 0x4E; e.bytes[1] = 1
        elif b == 3:
            if e.anim_done:
                e.bytes[1] = 0
                if not hi(next_seed(g), 2):
                    e.bytes[0] = 2
                else:
                    e.bytes[0] = 0
                    e.ai[1] = hi(next_seed(g), 0x10) + 0x1E
    elif st == 2:                           # the hand, then a shower of rocks (global sprite 0xEC)
        b = e.bytes[1]
        if b == 0:
            e.target_anim = 2; e.bytes[1] = b + 1
        elif b == 1:
            if e.anim_done: e.bytes[1] = b + 1
        elif b == 2:
            e.target_anim = 6; e.ai[1] = 0x14; e.bytes[1] = b + 1
        elif b == 3:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            fp = 0x40
            if not t:
                c = entity.spawn_warp_entity(g, e, 1, 0x9E, s32(e.px + 0xFF600000), s32(e.py + 0x300000),
                                             s32(e.pz + 0xFFF00000), e.target_dir)
                m.w32(C51_HAND, _addr(c))
                e.item_state = 0
                e.bytes[1] = e.bytes[1] + 1
        elif b == 4:
            t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
            e.ai[1] = t
            fp = 0xA0
            if not t & 3:
                n = hi(next_seed(g), 2) + 2
                for _ in range(n):
                    s1 = next_seed(g); s2 = next_seed(g)
                    i = e.item_state
                    o = (i << 3) & M32
                    e.item_state = s32(i + 1)
                    x = s32(m.s32((0x80027E90 + o) & M32) + (hi(s1, 0x19) << 18))
                    y = s32(m.s32((0x80027E94 + o) & M32) + (hi(s2, 0x19) << 17))
                    if not s32(i + 1) < 6: e.item_state = 0
                    c = entity.spawn_warp_entity(g, e, 0, 0xEC, x, y, 0x30000, 0)
                    if c is None: m.w32(0xB8, 0x8000)          # (no NULL check in the game)
                    else: c.fz = 0x8000
            if e.anim_done:
                e.cur_anim = -1; e.bytes[1] = e.bytes[1] + 1
        elif b == 5:
            fp = 0xA0
            if e.anim_done:
                e.bytes[1] = e.bytes[1] + 1
                a = m.u32(C51_HAND)
                e.target_anim = 1
                if a:
                    _release(g, C51_HAND)
        elif b == 6:
            if e.anim_done:
                if (e.ai[5] & 0xFFFF) == 0 and not hi(next_seed(g), 2):
                    e.bytes[1] = 2; e.ai[5] = 1
                else:
                    e.bytes[1] = e.bytes[1] + 1
        elif b == 7:
            if e.anim_done:
                e.target_anim = 3; e.bytes[1] = e.bytes[1] + 1
        elif b == 8:
            if e.anim_done:
                e.bytes[0] = 0; e.ai[1] = 0x1E; e.ai[5] = 0
    elif st == 3:
        b = e.bytes[1]
        if b == 0:
            e.target_anim = 2; e.bytes[1] = 1
        elif b == 1:
            if e.anim_done:
                e.target_anim = 3; e.bytes[1] = 2
        elif b == 2:
            if e.anim_done:
                e.bytes[0] = 0; e.ai[1] = 0x28
    elif st == 4:
        if e.anim_done:
            e.bytes[0] = 0; e.ai[1] = 0x1E
    elif st == 5:                           # dying
        a = e.target_anim
        if a == 9 and e.anim_done:
            f = m.u32(EVFLAGS)
            if not f & 1:
                m.w32(EVFLAGS, f | 1)
                f = m.u32(EVFLAGS)
            if f & 0x20:
                q = _eref(g, _ai_word(e, 2))
                if q.bytes[3] < 2:          # puffs on the partner, 80 px further
                    y0, z0 = q.mpy, q.mpz
                    q.mpy = s32(y0 + 0x500000)
                    q.mpz = s32(q.mpz + 0x500000)
                    calls.call(g, 0x80083394, _arg(q))
                    q.mpy = y0; q.mpz = z0
                elif not f & 0x40:
                    m.w32(EVFLAGS, f | 0x40)
                    e.target_anim = 0xA; e.ai[1] = 0
        elif a == 0xA:
            t = e.ai[1] & 0xFFFF
            if t == 0:
                e.ai[1] = m.s32(0x80027E10 + e.bytes[1] * 4) - 1
            else:
                e.ai[1] = t - 1
                if not (t - 1) & 0xFFFF:    # 6 explosions along the body
                    o = e.bytes[1] * 12
                    x = s32(e.px + m.s32(0x80027E28 + o))
                    y = s32(s32(e.py + m.s32(0x80027E2C + o)) + 0x500000)
                    z = s32(s32(e.pz + m.s32(0x80027E30 + o)) + 0x500000)
                    core.play_sound(g, 0xC4)
                    core.spawn_effect(g, 0, 8, 0, x, y, z)
                    e.bytes[1] = e.bytes[1] + 1
                    if e.bytes[1] == 6: e.bytes[0] = 6
    elif st == 7:                           # quake: debris falls on four spots
        b = e.bytes[1]
        if b == 0:
            t = e.ai[1] & 0xFFFF
            if t:
                e.ai[1] = t - 1
                if not (t - 1) & 0xFFFF:
                    _shake(g, 4, 2)
                    e.bytes[1] = 1; e.ai[1] = 0x1E
        elif b == 1:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t: e.bytes[1] = 2
        elif b == 2:
            t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
            e.ai[1] = t
            if not t & 0xF:
                for k in range(4):
                    s1 = next_seed(g); s2 = next_seed(g)
                    x = s32(m.s32(0x80027E70 + 8 * k) + hi(s1, 0xF) * 0xC0000)
                    y = s32(m.s32(0x80027E74 + 8 * k) + (hi(s2, 0x13) << 19))
                    f = core.spawn_effect(g, 0, 0x16, 1, x, y, 0x1100000)
                    if f is not None:
                        f.vz = s32((hi(next_seed(g), 5) << 14) + 0xFFFC0000)
            if e.anim_done:
                m.w32(SHAKE + 4, 2)
                e.bytes[0] = 0
                s = next_seed(g)
                e.delay = 0x258
                e.ai[1] = hi(s, 0x10) + 0x1E
    elif st == 8:                           # slide (with the partner) in direction bytes[1]
        q = _eref(g, _ai_word(e, 2))
        v = m.s16(DX + e.bytes[1] * 2) * 0x30
        q.pafx = v
        e.pafx = v
        v = m.s16(DY + e.bytes[1] * 2) * 0x30
        q.pafy = v
        e.pafy = v
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            e.bytes[0] = 0; e.ai[1] = 0x1E
    elif st == 9:                           # a straight row of bubbles
        b = e.bytes[1]
        if b == 0:
            e.target_anim = 2; e.bytes[1] = b + 1
        elif b == 1:
            if e.anim_done: e.bytes[1] = b + 1
        elif b == 2:
            e.target_anim = 6; e.ai[1] = 0x14; e.bytes[1] = b + 1
            m.w16(C51_CNT, 0)
            m.w16(C51_ROW, 1 if 0x12FFFFF < p.py else 0)
        elif b == 3:
            n = m.s16(C51_CNT)
            if n != 6:
                t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
                e.ai[1] = t
                if not t:
                    x = s32(e.px + 0xFF880000); z = e.pz; y = s32(e.py + 0x100000)
                    dr = 0xF - n * 2 if m.s16(C51_ROW) == 0 else n * 2 + 1
                    c = entity.spawn_warp_entity(g, e, 1, 0x9F, x, y, z, dr)
                    if c is not None:
                        c.bytes[0] = 4; c.bytes[1] = 9
                    e.ai[1] = 0xA
                    m.w16(C51_CNT, m.u16(C51_CNT) + 1)
            if e.anim_done:
                e.target_anim = 3; e.bytes[1] = e.bytes[1] + 1
        elif b == 4:
            if e.anim_done:
                e.bytes[0] = 0; e.ai[1] = 0x1E; e.ai[5] = 0
    if fp:                                  # the suction: Alundra, sprites 2 and resting 0xEC pulled
        k8 = m.s16(DX + 0x10)
        for k in range(64):
            t = g.ent[k]
            if k == 0 or t.sprite_index == 2 or (t.sprite_index == 0xEC and t.target_anim == 0):
                t.pafx = s32(k8 * fp)


def _ptr(g, x):
    """An entity pointer field as the game uses it: the object, or an _At for 0 / non-slot values."""
    if x is None: return _At(g, 0)
    if isinstance(x, int): return _At(g, x)
    return x


def _abs32(v):
    """bgez / negu: |v| as a signed word (-2^31 stays negative)."""
    return s32(-v) if v < 0 else v


def _face_player(g, e):
    p = g.ent[0]
    e.target_dir = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))


@port(0x8007B300)
def ai_c53(g, e):
    """C53 (the shots of C54's boss): rises to 160 px above its parent (anim 4), then flies a
    pattern chosen by the parent's bytes[0] (at Alundra's spot, homing, fixed directions...)
    until it gets there, hits something or times out; vanishes when the parent is beaten."""
    par = _ptr(g, e.parent); p = g.ent[0]
    if par.bytes[3]:
        e.target_anim = 2
        e.flags = s32(e.flags | 0x40)
    a = e.target_anim
    if a == 4:
        if e.pz < s32(par.pz + 0xA00000): return
        e.fz = 0
        e.target_anim = 5
        k = par.bytes[0]
        if k >= 6: return
        if k in (0, 1):                     # at the spot where Alundra stands now
            if k == 1:
                e.bytes[1] = 0x1E; e.ai[1] = 0xF0
            _face_player(g, e)
            e.delay = p.px
            e.item_state = p.py
        elif k == 2:
            v = g.mem.s32(0x80027F4C + e.bytes[0] * 4)
            e.ai[1] = 0x3C; e.target_dir = v
        elif k in (3, 4):
            e.target_dir = 2 if k == 3 else 0x1E
            e.ai[1] = (e.bytes[0] + 1) * 0x18
        else:
            v = g.mem.s32(0x80027F64 + e.bytes[0] * 4)
            e.ai[1] = 0x5A; e.target_dir = v
    elif a in (3, 5):
        stop = 1 if e.force_adjusted else 0
        k = par.bytes[0]
        if k == 0 or k == 1:
            if k == 1:                          # homing: turns to Alundra every 10 frames
                b = (e.bytes[1] - 1) & 0xFF
                e.bytes[1] = b
                if not b:
                    _face_player(g, e)
                    e.bytes[1] = 0xA
                t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
                e.ai[1] = t
                if not t: stop = 1
            dx = s32(e.px - e.delay); dy = s32(e.py - e.item_state)
            if not 0x100000 < _abs32(dx) and not 0x100000 < _abs32(dy): stop = 1
        else:
            t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
            e.ai[1] = t
            if not t: stop = 1
        if stop:
            f = e.flags
            e.target_anim = 1
            e.flags = s32(f | 0x100)
    elif a == 1:
        if e.on_ground:
            f = e.flags
            e.target_anim = 2
            e.flags = s32(f | 0x40)


def _set_ai_word(e, k, v):
    """sw to ai[k], ai[k + 1]."""
    e.ai[k] = v & 0xFFFF; e.ai[k + 1] = (v >> 16) & 0xFFFF


def _drop(g, word):
    """The entity kept at word: anim 1, flag 0x40, forgotten (no NULL check in the game)."""
    t = _eref(g, g.mem.u32(word))
    f = t.flags
    t.target_anim = 1
    t.flags = s32(f | 0x40)
    g.mem.w32(word, 0)


# ---- C54
C54_CHAIN = 0x801247FC      # 12 entity addresses: the segments of the chain it throws
C54_N = 0x8012482C          # attacks made (0..6)
C54_STEP = 0x80124830       # step in the throw pattern
C54_ROW = 0x80124834        # throw pattern (row of 0x80027F98: 6 directions, -1 ends)
C54_WAIT = 0x80124838       # frames before it may cast again
C54_NEXT = 0x8012483C       # 1: throw next, 2: cast next, 0: choose
C54_DX, C54_DY = 0x80124840, 0x80124844     # offset of each chain segment from the last
C54_IDLE = 0x80124848       # frames Alundra kept out of its reach (0x708: the guard comes)
C54_PAT = 0x80027F98


def _c54_dir(g):
    m = g.mem
    return m.s32((C54_PAT + m.s32(C54_ROW) * 0x18 + m.s32(C54_STEP) * 4) & M32)


@port(0x8007B5F0)
def ai_c54(g, e):
    """C54 (a boss): throws a chain of 12 segments (sprite 0xBF) along patterns of
    0x80027F98 or casts shots (C53, sprite 0xC0) / a ring of 8 orbs (sprite 0xC2, ai[4] = 8);
    while the orbs live it keeps a field (item_state) that grows when Alundra stays near and
    calls a guard (global sprite 0x19) if he keeps away for 0x708 frames.  Beaten (bytes[3])
    it plays the death puffs (< 4) or anim 7."""
    m = g.mem; p = g.ent[0]
    if m.s32(INIT) == 0:
        for k in range(12): m.w32(C54_CHAIN + 4 * k, 0)
        m.w32(C54_NEXT, 0); m.w32(C54_WAIT, 0); m.w32(C54_ROW, 0); m.w32(C54_STEP, 0); m.w32(C54_N, 0)
        m.w32(INIT, 1)
    b3 = e.bytes[3]
    if b3 and e.target_anim == 0:
        if b3 < 4:
            calls.call(g, 0x80083394, e)
        else:
            f = e.flags
            e.target_anim = 7
            e.flags = s32(f | 0x40)
        return
    w = m.s32(C54_WAIT)
    if w: m.w32(C54_WAIT, w - 1)
    rel = aihelp.rel_tile(g, e)
    n = e.ai[4] & 0xFFFF
    if n:                                   # orbs out: they turn around it (delay = angle)
        e.delay = (e.delay - n + 0xC) & 0x1FF
        if _ai_word(e, 2) == 0:
            if m.s32(C54_IDLE) == 0x708:
                c = _ptr(g, entity.spawn_warp_entity(g, e, 0, 0x19, e.px, e.py, e.pz, 0))
                _set_ai_word(e, 2, _addr(c))
                c.target_anim = 4
                c.flags = s32(c.flags & ~0x80)
            else:
                r = s32(e.item_state + 0x1000)
                ox = s32(rel[0] * 0x180000 - r * 0x300)
                oy = s32((rel[1] << 20) - (r << 9))
                inside = 1 if ox < 0 and oy < 0 else 0
                if not inside and rel[0] < 6 and rel[1] < 6:
                    m.w32(C54_IDLE, 0)
                    v = s32(e.item_state + 0x16)
                    e.item_state = v
                    if not v < 0x1001: e.item_state = 0x1000
                else:
                    v = e.item_state
                    if v or inside:
                        v = s32(v - 0x16)
                        e.item_state = v
                        if v < 0: e.item_state = 0
                    else:
                        m.w32(C54_IDLE, m.s32(C54_IDLE) + 1)
    else:
        a = _ai_word(e, 2)
        if a:
            q = _eref(g, a)
            player.remove_entity(g, _arg(q))
            _set_ai_word(e, 2, 0)
    a = e.target_anim & M32
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1; return
        if (e.ai[4] & 0xFFFF) == 0:         # no orbs: cast the ring
            e.target_anim = 4; e.bytes[0] = 0xFF; e.ai[1] = 0x17
            return
        d = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
        nx = m.s32(C54_NEXT)
        throw = nx == 1
        if not throw and nx != 2 and rel[1] < 7 and not ((d - 7) & M32) < 0x13:
            throw = hi(next_seed(g), 3) == 0
        if throw:
            k = m.s32(C54_N)
            e.target_anim = 8
            m.w32(C54_NEXT, 0); m.w32(C54_STEP, 0)
            if k == 0: v = hi(next_seed(g), 3)
            elif k == 6: v = 9
            else: v = hi(next_seed(g), 9)
            m.w32(C54_ROW, v)
            if m.s32(C54_ROW) < 3 and hi(next_seed(g), 3):
                if not ((d - 2) & M32) < 0x1D: m.w32(C54_ROW, 0)
                else: m.w32(C54_ROW, 1 if d < 7 else 2)
            k = s32(m.s32(C54_N) + 1)
            m.w32(C54_N, k)
            if k == 7: m.w32(C54_N, 0)
            e.target_dir = _c54_dir(g)
            return
        if m.s32(C54_WAIT): return
        m.w32(C54_NEXT, 0)
        s = next_seed(g)
        e.bytes[0] = hi(s, 2) if not rel[1] < 5 else hi(s, 6)
        e.target_anim = 4; e.ai[1] = 0x17; e.bytes[1] = 0
    elif a == 4:                            # casting
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if not (t - 1) & 0xFFFF:
                if e.bytes[0] == 0xFF:      # the ring of 8 orbs
                    z = s32(e.pz + 0xC0000)
                    e.ai[4] = 8; e.item_state = 0; e.delay = 0
                    m.w32(C54_IDLE, 0)
                    for k in range(8):
                        c = _ptr(g, entity.spawn_warp_entity(g, e, 1, 0xC2, 0, 0, z, 0))
                        c.delay = k << 6
                        c.target_anim = 1
                else:                       # two shots, kinds bytes[1] * 2 (+1)
                    y = e.py; z = s32(e.pz + 0x200000)
                    c = entity.spawn_warp_entity(g, e, 1, 0xC0, s32(e.px + 0xFFF60000), y, z, 0)
                    if c is not None: c.bytes[0] = e.bytes[1] * 2
                    c = entity.spawn_warp_entity(g, e, 1, 0xC0, s32(e.px + 0xA0000), y, z, 0)
                    if c is not None: c.bytes[0] = e.bytes[1] * 2 + 1
                    b = (e.bytes[1] + 1) & 0xFF
                    e.bytes[1] = b
                    if b != 3: e.ai[1] = 0x1E
        if e.anim_done:
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = hi(s, 0x20) + 0x1E
            m.w32(C54_WAIT, 0xF0)
    elif a == 8:
        if e.anim_done:
            v = _c54_dir(g)
            e.target_anim = 1; e.target_dir = v
    elif a == 1:                            # throw: the first segment, a flash
        if e.anim_done:
            m.w32(C54_STEP, m.s32(C54_STEP) + 1)
            d = e.target_dir
            if d == 0:
                ox, oy = 0x150000, 0x260000
                m.w32(C54_DX, 0); v = 0x100000
            elif d == 0x10:
                ox, oy = 0xFFE90000, 0x170000
                m.w32(C54_DX, 0xFFEA0000); v = 0x160000
            else:
                ox, oy = 0x3F0000, 0x170000
                v = 0x160000; m.w32(C54_DX, 0x160000)
            m.w32(C54_DY, v)
            calls.call(g, 0x800832B0)
            c = entity.spawn_warp_entity(g, e, 1, 0xBF, s32(ox + e.px), s32(oy + e.py), e.pz, e.target_dir)
            m.w32(C54_CHAIN, _addr(c))
            if c is not None:
                e.bytes[2] = 1; e.target_anim = 2; e.ai[1] = 0x12
    elif a == 2:                            # the chain grows a segment a frame
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            for k in range(12): _drop(g, C54_CHAIN + 4 * k)
            e.target_anim = 3; e.bytes[2] = 0
            return
        k = e.bytes[2]
        if k == 0xC: return
        q = _eref(g, m.u32(C54_CHAIN - 4 + k * 4))
        c = entity.spawn_warp_entity(g, e, 1, 0xBF, s32(q.px + m.s32(C54_DX)), s32(q.py + m.s32(C54_DY)),
                                     q.pz, e.target_dir)
        m.w32(C54_CHAIN + k * 4, _addr(c))
        if c is not None: e.bytes[2] = e.bytes[2] + 1
    elif a == 3:
        if e.anim_done:
            v = _c54_dir(g)
            if v == -1:
                e.target_anim = 9
            else:
                e.target_anim = 1; e.target_dir = v
    elif a == 9:
        if e.anim_done:
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = hi(s, 0x20) + 0x3C
    elif a == 6:                            # hurt: the chain goes
        for k in range(12):
            w = C54_CHAIN + 4 * k
            if m.u32(w): _drop(g, w)
        if e.anim_done:
            if e.bytes[3]:
                e.ai[1] = 0x12C; e.ai[5] = 0x1E
                f = e.flags
                e.target_anim = 0
                e.flags = s32(f & ~3)
                return
            k = m.s32(C54_N)
            m.w32(C54_NEXT, 1 if k == 0 or k == 6 else 2)
            e.damaged_tick = 0x5A
            e.target_anim = 0; e.ai[1] = 0x14


SIN, COS = 0x800282D8, 0x800286D8      # s16[512]: circle tables (x, y), 0x1000 = 1


@port(0x8007C16C)
def ai_c86(g, e):
    """C86 (C54's ring of orbs): circles its parent (or the parent's guard, ai[2..3]) at angle
    parent.delay + delay and radius parent.item_state + 0x1000; goes (anim 2) when the parent
    is beaten or the guard is low on the map, and then tells the parent (ai[4] -= 1)."""
    par = _ptr(g, e.parent)
    if e.target_anim != 2:
        if par.bytes[3]:
            e.target_anim = 2; return
        a = _ai_word(par, 2)
        if a and 0x1DFFFFF < _eref(g, a).py:
            e.target_anim = 2; return
    a = _ai_word(par, 2)
    if a == 0:
        cx, cy = par.px, par.py
    else:
        c = _eref(g, a); cx, cy = c.px, c.py
    i = ((par.delay + e.delay) & 0x1FF) * 2
    e.px = s32(cx + s32(g.mem.s16(SIN + i) * s32(par.item_state + 0x1000)))
    e.py = s32(cy - s32(g.mem.s16(COS + i) * s32(par.item_state + 0x1000)))
    a = e.target_anim
    if a == 1:
        if e.anim_done: e.target_anim = 0
    elif a == 2:
        if e.anim_done:
            par.ai[4] = (par.ai[4] & 0xFFFF) - 1
            entity.destroy_entity(g, e, -1)
    elif a == 3:
        if e.anim_done:
            e.target_anim = 2 if e.bytes[3] else 0


@port(0x8007C2EC)
def fx_release(g, f):
    """C55 / C56: an effect that is still playing (b70 0) but flagged by its frames (b7d):
    state 2, b7d 0, b70 1 (the boss programs wait for b70 == 1)."""
    if f is None: return
    if f.b70: return
    if not f.b7d: return
    f.state = 2; f.b7d = 0; f.b70 = 1


# ---- C55
C55_FX = 0x80124850         # effect address: the big spell at the middle of the room
C55_N = 0x8012484C          # how many copies it makes (2 or 3)
C55_POS2, C55_POS3 = 0x800280B0, 0x800280C8     # x, y words: the 3 / 4 places it appears at


@port(0x8007C32C)
def ai_c55(g, e):
    """C55 (a boss that splits): appears at one of 3 or 4 places with copies (sprite 0xA8) at
    the others; when its spell effect finishes it either rains a line of fire (sprite 0xA3)
    toward Alundra three times, or summons a ring of 8 orbs (0xA4, ai[4] counts them) or
    3 runners (0xA7).  Beaten (anim 7 + bytes[3]) it raises event flag 1 and Alundra faces it."""
    m = g.mem; p = g.ent[0]
    if m.s32(INIT) == 0:
        m.w32(C55_FX, 0); m.w32(C55_N, 0); m.w32(INIT, 1)
    fx_release(g, _fxref(g, m.u32(C55_FX)))
    fx_release(g, _fxref(g, _ai_word(e, 2)))
    a = e.target_anim
    if a == 14:                             # hidden: reappear somewhere
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1; return
        if e.ai[4] & 0xFFFF: return
        b = e.bytes[0]
        if b == 1:
            core.play_sound(g, 0x12A)
            f = core.spawn_effect(g, 1, 0, 0, e.px, e.py, e.pz)
            b = e.bytes[0]
            _set_ai_word(e, 2, _fx_addr(f))
            e.bytes[0] = b + 1
            return
        if b == 2:
            k = _fxp(g, _ai_word(e, 2)).b70
            if k == 1: e.target_anim = k
        if e.bytes[0]: return
        k = hi(next_seed(g), 3)
        e.bytes[1] = k
        if not k & 0xFF:
            tab = C55_POS2; m.w32(C55_N, 2)
        else:
            if e.bytes[2]: e.bytes[1] = 2
            tab = C55_POS3; m.w32(C55_N, 3)
        n = m.s32(C55_N)
        k = hi(next_seed(g), n + 1)
        i = 0; j = k * 2
        if n:
            wait = 0; row = tab + k * 8
            while True:
                c = entity.spawn_warp_entity(g, e, 1, 0xA8, m.s32(row), m.s32(row + 4), e.pz, e.target_dir)
                if c is not None:
                    c.target_anim = 0xE; c.bytes[0] = 1; c.ai[1] = wait
                n = m.s32(C55_N)
                j += 2; row += 8
                if s32((n + 1) * 2) == j:
                    row = tab; j = 0
                i += 1; wait += 0xB
                if i == n: break
        r = (tab + j * 4) & M32
        e.bytes[0] = 1
        e.ai[1] = i * 0xB
        e.px = m.s32(r); e.py = m.s32(r + 4)
    elif a == 1:
        if e.anim_done:
            if e.bytes[1] == 0:
                e.target_anim = 4
            else:
                core.play_sound(g, 0x128)
                e.target_anim = 3; e.ai[1] = 0x1E; e.bytes[0] = 0
    elif a == 3:                            # the spell in the middle of the room
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
            if e.bytes[0]:
                e.target_anim = 2; return
            core.play_sound(g, 0x12A)
            f = core.spawn_effect(g, 1, 0, 0, 0x1500000, 0x3100000, 0x1400000)
            m.w32(C55_FX, _fx_addr(f))
            e.bytes[0] = 1
            return
        k = _fxp(g, m.u32(C55_FX)).b70
        if k != 1: return
        calls.call(g, 0x800832B0)
        if e.bytes[1] == k:                 # 3 runners
            core.play_sound(g, 0x129)
            e.target_anim = 2
            for d in range(4, 0x28, 0xC):
                c = entity.spawn_warp_entity(g, e, 1, 0xA7, 0x1500000, 0x3100000, 0x1480000, d)
                if c is not None:
                    c.bytes[0] = 4; c.ai[1] = 0x78; c.target_anim = 1
                    e.bytes[2] = 3
            return
        s = next_seed(g)                    # a ring of 8 orbs, radius (1..3) << 9
        e.target_anim = 2
        r = hi(s, 3) + 1
        ang = r << 4
        core.play_sound(g, 0x127)
        for _ in range(8):
            c = entity.spawn_warp_entity(g, e, 1, 0xA4, 0x1500000, 0x3100000, 0x1480000, 0)
            if c is not None:
                c.target_anim = 0; c.item_state = r << 9; c.ai[4] = ang
                ang = (ang + 0x40) & 0x1FF
                e.ai[4] = (e.ai[4] & 0xFFFF) + 1
    elif a == 4:
        if e.anim_done:
            e.target_anim = 5; e.ai[1] = 0xB4
    elif a == 5:                            # three lines of fire toward Alundra
        t = e.ai[1] & 0xFFFF
        if t == 0:
            e.target_anim = 6; return
        if t in (0xB4, 0x78, 0x3C):
            core.play_sound(g, 0x125)
            k = 0
            calls.call(g, 0x800832B0)
            d = player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
            sx = m.s16(DX + d * 2)
            z = s32(e.pz + 0x80000)
            while True:
                x = s32(e.px + s32(sx * k))
                y = s32(e.py + s32(m.s16(DY + d * 2) * k))
                if 0x17FFFFE < ((x + 0xFF6FFFFF) & M32): break
                if 0x13FFFFE < ((y + 0xFD8FFFFF) & M32): break
                s = next_seed(g)
                dr = m.u8(0x80028AF8 + hi(s, 4))
                k += 0xC00
                entity.spawn_warp_entity(g, e, 1, 0xA3, x, y, z, dr)
        e.ai[1] = (e.ai[1] & 0xFFFF) - 1
    elif a == 6:
        if e.anim_done: e.target_anim = 2
    elif a == 2:                            # vanish: the effects end
        if e.anim_done:
            e.bytes[0] = 0; e.ai[1] = 0xB4
            f = m.u32(C55_FX)
            e.target_anim = 0xE
            if f:
                _fxp(g, f).b70 = 2
                m.w32(C55_FX, 0)
            _fxp(g, _ai_word(e, 2)).b70 = 2     # (no NULL check in the game)
            _set_ai_word(e, 2, 0)
    elif a == 7:                            # hurt
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 0xF; e.ai[1] = 0x3C
                fl = e.flags
                f = m.u32(C55_FX)
                e.flags = s32(fl & ~3)
                if f:
                    _fxp(g, f).b70 = 2
                    m.w32(C55_FX, 0)
            else:
                e.target_anim = 2
    elif a == 15:                           # dying
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t:
            m.w32(EVFLAGS, m.u32(EVFLAGS) | 1)
            p.target_dir = player.dir_from_delta(s32(e.px - p.px), s32(e.py - p.py))


@port(0x8007CB30)
def ai_c56(g, e):
    """C56 (C55's copies): appear with their own spell effect, play along with the parent
    (same attack anims) and vanish (anim 13) when it vanishes or is hurt."""
    fx_release(g, _fxref(g, _ai_word(e, 2)))
    par = _ptr(g, e.parent)
    if par.target_anim == 7:
        e.target_anim = 0xD; return
    a = e.target_anim
    if a == 14:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1; return
        if e.bytes[0]:
            core.play_sound(g, 0x12A)
            f = core.spawn_effect(g, 1, 0, 0, e.px, e.py, e.pz)
            _set_ai_word(e, 2, _fx_addr(f))
            e.bytes[0] = 0
            return
        k = _fxp(g, _ai_word(e, 2)).b70
        if k == 1: e.target_anim = k
    elif a == 1:
        if e.anim_done:
            e.target_anim = 4 if par.bytes[1] == 0 else 3
    elif a == 3:
        if par.target_anim == 2: e.target_anim = 0xD
    elif a == 4:
        if e.anim_done: e.target_anim = 5
    elif a == 5:
        k = par.target_anim
        if k == 6: e.target_anim = k
    elif a == 6:
        if e.anim_done: e.target_anim = 0xD
    elif a == 13:
        if e.anim_done:
            e.flags = s32(e.flags | 0x40)
            _fxp(g, _ai_word(e, 2)).b70 = 2
            _set_ai_word(e, 2, 0)


@port(0x8007CCE4)
def ai_c58(g, e):
    """C58 (C55's orbs): spiral out from the middle of the room (radius delay up to 0x1800,
    angle ai[4]) trailing sparks, then after item_state / 8 frames fly off outward (anim 2);
    hitting something (anim 3) tells the parent (ai[4] -= 1); all go when it is beaten."""
    par = _ptr(g, e.parent)
    if par.bytes[3]:
        f = e.flags
        e.target_anim = 3; e.flags = s32(f | 0x40)
        return
    if ((e.target_anim - 1) & M32) < 2:
        t = ((e.ai[1] & 0xFFFF) + 1) & 0xFFFF
        e.ai[1] = t
        if not t & 3: core.spawn_effect(g, 1, 1, 0, e.px, e.py, e.pz)
    a = e.target_anim
    if a == 1:
        d = e.delay
        if d < 0x1800: e.delay = s32(d + 0x40)
        else: e.item_state = s32(e.item_state - 8)
        i = ((e.ai[4] & 0xFFFF) + 0xA) & 0x1FF
        x = s32(g.mem.s16(SIN + i * 2) * e.delay)
        e.ai[4] = i
        y = s32(g.mem.s16(COS + (e.ai[4] & 0xFFFF) * 2) * e.delay)
        e.px = s32(x + 0x1500000)
        e.py = s32(y + 0x3100000)
        if e.item_state == 0:
            core.play_sound(g, 0x127)
            e.target_anim = 2
            e.target_dir = (0x20 - ((e.ai[4] & 0xFFFF) >> 4)) & 0x1F
    elif a == 2:
        if e.force_adjusted:
            f = e.flags
            e.target_anim = 3; e.flags = s32(f | 0x40)
            par.ai[4] = (par.ai[4] & 0xFFFF) - 1


@port(0x8007CEB0)
def ai_c59(g, e):
    """C59 (C55's runners): rest (anim 0, 40 frames) / pause (anim 1, 20 frames) then run in
    gait bytes[0]; while running (anims 4-7, faster each) turn toward Alundra every few
    frames, by 1 or 2 steps; hit (anim 3) step up a gait, or die (bytes[3]: parent
    bytes[2] -= 1); all go when the parent is beaten."""
    par = _ptr(g, e.parent)
    if par.bytes[3]:
        f = e.flags
        e.target_anim = 2; e.flags = s32(f | 0x40)
        return
    a = e.target_anim & M32
    if a in (0, 1):
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t: return
        k = e.bytes[0]
        e.ai[1] = 0x28 if a == 0 else 0x14
        e.target_anim = k
    elif 4 <= a <= 7:
        t = e.ai[1] & 0xFFFF
        if not t: return
        e.ai[1] = t - 1
        if (t - 1) & 0xFFFF: return
        p = g.ent[0]
        v = s32(e.target_dir - player.dir_from_delta(s32(p.px - e.px), s32(p.py - e.py)))
        if not v < 0x10 or ((v + 0x10) & M32) < 0x10:
            e.bytes[1] = 1
        if ((v - 1) & M32) < 0xF or v < -0x10:
            e.bytes[1] = 0xFF
        if not _abs32(v) < 8:
            e.bytes[1] = e.bytes[1] * 2
        e.target_dir = (e.target_dir + e.bytes[1]) & 0x1F
        e.ai[1] = 0x12 - (e.target_anim - 4) * 4
    elif a == 3:
        if not e.anim_done: return
        if e.bytes[3]:
            f = e.flags
            e.target_anim = 2; e.flags = s32(f | 0x40)
            par.bytes[2] = par.bytes[2] - 1
            return
        k = e.bytes[0]
        e.ai[1] = 0x1E
        e.target_anim = 0
        if k != 7: e.bytes[0] = k + 1


def _bytes_word(e):
    """lw 0x274: the four bytes as a signed word."""
    b = e.bytes
    return s32(b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24)


def _set_bytes_word(e, v):
    v &= M32
    e.bytes[0] = v; e.bytes[1] = v >> 8; e.bytes[2] = v >> 16; e.bytes[3] = v >> 24


def _cell_hole(g, e, k):
    """Floor square k under e (Entity+0x148 + 4k) has both bits 0x1001 (a pit)."""
    return (g.mem.u16(getattr(e, 'cell%d' % k)) & 0x1001) == 0x1001


@port(0x8007D1AC)
def ai_c62(g, e):
    """C62 (a bomb / lit object Alundra can carry): the fuse (word at bytes[0..3]) counts
    down sparking for its last 60 frames, then it goes off (status 3) and is dropped; thrown
    (anim != 0) it bounces back once off walls, lands with sound 0x18, falls into pits."""
    if e.vram_and & 4:
        player.remove_entity(g, e); return
    t = _bytes_word(e)
    _set_bytes_word(e, t - 1)
    held = 1
    if t:
        if t < 0x3C and not t & 7:
            f = core.spawn_effect(g, 0, 9, 0, e.px, e.py, s32(e.pz + 0x80000))
            if f is not None:
                s1 = next_seed(g); s2 = next_seed(g)
                f.vx = s32(hi(s1, 0x30001) + 0xFFFE8000)
                f.vy = s32(hi(s2, 0x20001) + 0xFFFF0000)
    else:                                   # it goes off: dropped
        h = e.holder
        e.estatus = 3
        if h is None: held = 0
        else: h.carried = None; e.holder = None
    if held and e.holder is not None:       # carried: thrown when the holder lets go
        if not e.flags2:
            e.target_anim = 0; return
        h = e.holder
        e.target_anim = 2; e.flags2 = 0
        if h is not None: h.carried = None
        e.holder = None
        return
    if e.target_anim == 0: return
    if e.force_adjusted:
        if not e.on_ground:
            if not e.fz > 0 or e.delay: return
            e.delay = 1
            e.target_dir = (e.target_dir + 0x10) & 0x1F
            core.spawn_effect(g, 0, 9, 0, e.px, e.py, s32(e.pz + 0x80000))
        else:
            for k in range(4):
                if _cell_hole(g, e, k): e.estatus = 3
            e.target_anim = 0
    else:
        if not e.on_ground and not e.hits: return
        core.play_sound(g, 0x18)
        e.delay = 0
        for k in range(4):
            if _cell_hole(g, e, k): return
        e.target_anim = 0


TGT_ENTS, TGT_DISTS = 0x80142B80, 0x80142C80   # find_targets' result arrays


@port(0x8007D498)
def ai_c63(g, e):
    """C63 (a homing shot): every few frames (fuse word bytes[0..3]) picks the nearest thing
    its attack can hurt (entity address in delay, its serial in item_state) and turns toward
    it by up to 4 steps; pushed up (fz -3) whenever it looks; drops the target when it dies."""
    w = _bytes_word(e)
    if w:
        _set_bytes_word(e, w - 1); return
    a = e.delay
    e.fz = s32(0xFFFD0000)
    if a == 0:
        n = entity.find_targets(g, e, 1, g.mem.u8(e.attack_addr) & 0xF, TGT_ENTS, TGT_DISTS)
        if not n:
            _set_bytes_word(e, hi(next_seed(g), 9)); return
        a = g.mem.u32(TGT_ENTS)
        e.delay = a
        e.item_state = _eref(g, a).serial
    else:
        t = _eref(g, a)
        if t.estatus != 2 or t.serial != e.item_state:
            e.delay = 0; return
    t = _eref(g, a)
    d0 = e.target_dir
    d = player.dir_from_delta(s32(t.px - e.px), s32(t.py - e.py))
    if d0 == d: return
    if d < d0:
        if s32(d0 - d) < 4: e.target_dir = d
        else: e.target_dir = s32(e.target_dir - 4)
    else:
        if s32(d - d0) < 4: e.target_dir = d
        else: e.target_dir = s32(e.target_dir + 4)
    _set_bytes_word(e, 2)


@port(0x8007D61C)
def ai_c64(g, e):
    """C64 (a mirror image): copies the height of the entity of map record 10 and moves
    opposite to it (to Alundra's motion while he carries it, falling then switched off)."""
    sel = entity.select(g, e, 0xA)
    if not len(sel): return
    t = sel[0]; p = g.ent[0]
    if p.carried is t:
        f = e.flags
        e.fz = 0
        e.flags = s32(f & ~0x100)
        e.pz = t.pz
        e.tfx = s32(-p.tfx); e.tfy = s32(-p.tfy); e.fx = s32(-p.fx); e.fy = s32(-p.fy)
        e.sfx = s32(-p.sfx); e.sfy = s32(-p.sfy)
    else:
        e.flags = s32(e.flags | 0x100)
        e.pz = t.pz
        e.tfx = s32(-t.tfx); e.tfy = s32(-t.tfy); e.fx = s32(-t.fx); e.fy = s32(-t.fy)
        e.sfx = s32(-t.sfx); e.sfy = s32(-t.sfy)
