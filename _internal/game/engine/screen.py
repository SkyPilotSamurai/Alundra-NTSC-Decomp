"""The screen: fades, the clear colour, the drawing box and the map-change transitions
(US ALUN_CD.EXE 0x80043554-0x800452E0, GameFrame 0x8002BC18, the main loop 0x8002C598-0x8002C7D4).

Two colour fades share one state (16.16 per channel R G B):
  fade_bg  0x801F9438 on, 0x801F943C cur, 0x801F9448 target, 0x801F9454 step.  Its colour is
           the DRAWENV clear colour (0x801D7CC4..CC, r0 g0 b0): the colour the picture starts
           from every frame.  A map's own colour is map info +0x0C..+0x0E times 8.
  fade_ov  0x801F9460 on, 0x801F9464 keep, 0x801F9468 cur, 0x801F9474 target, 0x801F9480 step:
           a full-screen semi-transparent TILE (0x801F5368, OT 0x80133208 + 0xC) over the map,
           the sprites and the effects but under the message windows, the HUD and the portrait,
           blended by abr (DR_MODE 0x801F39C0 from the tpage table 0x801F2E10[abr]):
           0 = B/2 + F/2, 1 = B + F, 2 = B - F, 3 = B + F/4.

The drawing box (0x801D7CD0 x, 0x801D7CD4 y, 0x801D7CD8 w, 0x801D7CDC h) is the DRAWENV clip:
only it is cleared and drawn, what lies outside keeps the last picture.  Every GameFrame it
grows 8 / 6 pixels a side (0x8002BC18); arrivals 5 and 6 start it at the centre.

A map change (main loop): the frame that asks for it is shown, then 0x8004B0F0 (sounds and
music), 0x80045264(effect) copies the shown picture (MoveImage to x 320) and sets the effect
up; until 0x80045388(effect) returns 0 only the pad, the transition and the sound manager run,
each frame drawn from that copy (DR_MOVE rectangles) with the fade TILE over it - the HUD and
the windows fade with the picture because they are in it.  Then 0x80043488 shows it once more,
0x8004B1D8 waits for the music fade, then for every sound effect to end, then 3 frames; the map
is read from the CD and set up, 0x80044FB8 starts the arrival fade, GameFrame(1) runs unseen
and one VSync passes (0x80043324) before the first new frame."""
import pygame
from .registry import port
from . import core
from . import rodata as R

M32 = 0xFFFFFFFF
W, H = 320, 240


def _s32(x):
    x &= M32
    return x - 0x100000000 if x & 0x80000000 else x


def _s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def _div(a, b):
    """MIPS div: truncates toward zero."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


# ------------------------------------------------------------------- fade state --
class _Words:
    """Three words in RAM (R G B, 16.16) read and written as a list."""
    __slots__ = ('g', 'a')

    def __init__(self, g, a): self.g, self.a = g, a
    def __getitem__(self, i): return self.g.mem.s32(self.a + 4 * i)
    def __setitem__(self, i, v): self.g.mem.w32(self.a + 4 * i, v & M32)
    def __iter__(self): return iter([self[i] for i in range(3)])
    def __len__(self): return 3
    def __eq__(self, o): return list(self) == list(o)
    def __repr__(self): return repr(list(self))


class FadeState:
    """One of the two fades, kept in the game's own words (so the checks and the ports that
    read them see the same state): on, keep (overlay only), cur[3], target[3], step[3]."""
    def __init__(self, g, base, keep):
        self.g = g; self.base = base; self._keep = keep
        self._abr = 2                                   # the overlay's blend (DR_MODE 0x801F39C0)

    def _w(self, k): return _Words(self.g, self.base + k)
    on = property(lambda s: s.g.mem.s32(s.base), lambda s, v: s.g.mem.w32(s.base, v & M32))
    keep = property(lambda s: s.g.mem.s32(s._keep) if s._keep else 0,
                    lambda s, v: s.g.mem.w32(s._keep, v & M32) if s._keep else None)
    cur = property(lambda s: s._w(s._cur), lambda s, v: s._set(s._cur, v))
    target = property(lambda s: s._w(s._tgt), lambda s, v: s._set(s._tgt, v))
    step = property(lambda s: s._w(s._stp), lambda s, v: s._set(s._stp, v))

    def _set(self, k, vals):
        w = self._w(k)
        for i, v in enumerate(list(vals)[:3]): w[i] = v

    @property
    def abr(self):
        """The overlay's blend: bits 5-6 of its DR_MODE tpage word (0x801F39C4, E1 command)."""
        v = self.g.mem.u32(0x801F39C4)
        if v >> 24 == 0xE1: return (v >> 5) & 3
        return self._abr

    @abr.setter
    def abr(self, v): self._abr = v & 3


_FADES = {'fade_bg': (0x801F9438, 0, 4, 0x10, 0x1C), 'fade_ov': (0x801F9460, 0x801F9464, 8, 0x14, 0x20)}


def fade_state(g, name):
    f = getattr(g, name, None)
    if f is None:
        base, keep, cur, tgt, stp = _FADES[name]
        f = FadeState(g, base, keep); f._cur, f._tgt, f._stp = cur, tgt, stp
        setattr(g, name, f)
    return f


@port(0x800874B8, ret=True)
def graph_type(g):
    """libgpu GetGraphType: the GPU version byte."""
    return g.mem.u8(0x800C9F9C)


@port(0x80086DB8)
def set_draw_mode(g, prim, dfe, dtd, tpage):
    """libgpu SetDrawMode (no texture window): the primitive's length 1 and its E1 word."""
    g.mem.w8(prim + 3, 1)
    if graph_type(g) == 1 or graph_type(g) == 2:
        v = 0xE1000000 | (0x800 if dtd else 0) | (tpage & 0x27FF) | (0x1000 if dfe else 0)
    else:
        v = 0xE1000000 | (0x200 if dtd else 0) | (tpage & 0x9FF) | (0x400 if dfe else 0)
    g.mem.w32(prim + 4, v)


def _note(g, text):
    vm = getattr(g, 'vm', None)
    if vm is not None and hasattr(vm, 'note'): vm.note(text)


@port(0x80043554, ret=True)
def approach(c, t, s):
    n = _s32(c + s)
    if (s >= 0 and t < n) or (s < 0 and n < t): n = t
    return n


@port(0x80043628)
def ov_steps(g, abr, frames):
    """The overlay's blend and per-frame steps toward its target; when it is off it takes the
    target at once (and keeps its old blend)."""
    ov = fade_state(g, 'fade_ov')
    if ov.on:
        if frames == 0:
            _note(g, 'fade with 0 frames (the game crashes)'); frames = 1
        tpage = g.mem.u16(0x801F2E10 + (abr & M32) * 0x2C)       # the page table's entry for the blend
        if tpage == 0 and abr < 4: tpage = abr << 5               # (the remake has no page table: its abr
        ov.abr = (tpage >> 5) & 3                                 # bits; past its 4 rows the game reads a
                                                                  # zero word there: blend 0, a 50% mix)
        set_draw_mode(g, 0x801F39C0, 0, 0, tpage)
        set_draw_mode(g, 0x801F39C8, 0, 0, tpage)
        ov.step = [_div(_s32(t - c), frames) for t, c in zip(ov.target, ov.cur)]
    else:
        ov.step = [0, 0, 0]; ov.cur = list(ov.target)


@port(0x800437F4)
def bg_steps(g, frames):
    bg = fade_state(g, 'fade_bg')
    if bg.on:
        if frames == 0:
            _note(g, 'fade with 0 frames (the game crashes)'); frames = 1
        bg.step = [_div(_s32(t - c), frames) for t, c in zip(bg.target, bg.cur)]
    else:
        bg.step = [0, 0, 0]; bg.cur = list(bg.target)


@port(0x80043944)
def fade_begin(g, abr, frames):
    ov_steps(g, abr, frames)
    bg_steps(g, frames)


@port(0x80043974, ret=True)
def fade_tick(g):
    """Once a frame (0x8002BEAC, after the effects, before the windows; in a transition from its
    step): both fades move one step.  Sets g.clear_colour and g.fade_overlay ((r, g, b, abr), or
    None when the TILE is not drawn).  Returns bg.on | ov.on."""
    bg = fade_state(g, 'fade_bg'); ov = fade_state(g, 'fade_ov')
    if bg.on:
        bg.cur = [approach(c, t, s) for c, t, s in zip(bg.cur, bg.target, bg.step)]
        if bg.cur == bg.target: bg.on = 0
    g.clear_colour = tuple((c >> 16) & 0xFF for c in bg.cur)
    draw = False
    if ov.on:
        ov.cur = [approach(c, t, s) for c, t, s in zip(ov.cur, ov.target, ov.step)]
        if ov.cur == ov.target: ov.on = 0
        draw = True
    elif ov.keep:
        draw = True
    g.fade_overlay = tuple((c >> 16) & 0xFF for c in ov.cur) + (ov.abr,) if draw else None
    return bg.on | ov.on


@port(0x800832B0)
def flash(g):
    """A white flash: the overlay adds 0 -> 255 in 8 frames, then goes (keep 0)."""
    ov = fade_state(g, 'fade_ov')
    ov.target = [0xFF0000] * 3; ov.cur = [0, 0, 0]
    ov.on = 1; ov.keep = 0
    ov_steps(g, 1, 8)


@port(0x80083324)
def trigger(g, level, frames, keep, reset):
    """TriggerScreenEffect: the overlay adds toward grey `level` (16.16, the same for R G B) in
    `frames` frames; reset starts it from 0; keep leaves it drawn once there."""
    ov = fade_state(g, 'fade_ov')
    if reset: ov.cur = [0, 0, 0]
    ov.target = [_s32(level)] * 3
    ov.on = 1; ov.keep = keep
    ov_steps(g, 1, frames)


# ------------------------------------------------------------------- drawing box --
def box(g):
    d = getattr(g, 'disp', None)
    if d is None: d = g.disp = [0, 0, W, H]
    return d


def box_step(g):
    """The start of GameFrame (0x8002BC18)."""
    d = box(g)
    d[0] = max(0, d[0] - 8); d[2] = W - d[0] * 2
    d[1] = max(0, d[1] - 6); d[3] = H - d[1] * 2


def clip_rect(g):
    d = box(g)
    return pygame.Rect(d[0], d[1], max(0, d[2]), max(0, d[3]))


def blend_fill(surf, rgb, abr, rect=None):
    """A semi-transparent untextured TILE of colour rgb (abr 0..3)."""
    r, gg, b = rgb[:3]
    if abr == 2:
        surf.fill((r, gg, b), rect, special_flags=pygame.BLEND_RGB_SUB)
    elif abr == 1:
        surf.fill((r, gg, b), rect, special_flags=pygame.BLEND_RGB_ADD)
    elif abr == 3:
        surf.fill((r >> 2, gg >> 2, b >> 2), rect, special_flags=pygame.BLEND_RGB_ADD)
    else:
        rect = pygame.Rect(rect) if rect is not None else surf.get_rect()
        t = pygame.Surface(rect.size); t.fill((r, gg, b)); t.set_alpha(128)
        surf.blit(t, rect.topleft)


def draw_overlay(g, surf):
    o = getattr(g, 'fade_overlay', None)
    if o is not None: blend_fill(surf, o[:3], o[3])


# ------------------------------------------------------------------- transitions --
class Transition:
    """0x801F00B0: the effect's work area (20 x 15 squares of 16 x 16, 8 bytes each, or a word)."""
    def __init__(self, eff):
        self.eff = eff
        self.t = [[None] * 20 for _ in range(15)]
        self.word = 0             # 0x801F00B0 as one word (effect 5: the shake)
        self.line = 0             # 0x801F00B6 (effect 11)
        self.ops = []             # this frame's copies: (src x, src y, w, h, dst x, dst y), drawn in order


@port(0x80045264)
def transition_start(g, eff):
    """The copy of the shown picture is g.snapshot (taken by the caller)."""
    box(g)[:] = [0, 0, W, H]
    ov = fade_state(g, 'fade_ov'); bg = fade_state(g, 'fade_bg')
    ov.keep = 0; ov.on = 0; bg.on = 0
    tr = g.transition = Transition(eff)
    if eff in (0, 9, 2, 10):                                      # 0x80043CA0 / 0x80043D04
        ov.target = [0xFF0000] * 3; ov.cur = [0, 0, 0]; ov.on = 1
        fade_begin(g, 2 if eff in (0, 9) else 1, 16)
    elif eff == 4:                                                # 0x80043D68: squares fly off
        sy = -0x70
        for row in range(15):
            sx = -0x98
            for col in range(20):
                r1 = core.rnd(g, 21); r2 = core.rnd(g, 21); r3 = core.rnd(g, 304); r4 = core.rnd(g, 224)
                tr.t[row][col] = [_s16(-((sx * sx + sy * sy) >> 10) - r1), _s16(r2 + 0x14), r3, r4]
                sx += 0x10
            sy += 0x10
        ov.target = [0x200000, 0x400000, 0x400000]; ov.keep = 1; ov.on = 1; ov.cur = [0, 0, 0]
        bg.target = [0xFF0000] * 3
        fade_begin(g, 1, 0x50)
    elif eff == 5:                                                # 0x80043FCC: lines shake
        tr.word = 0
        ov.target = [0xFF0000] * 3; ov.cur = [0, 0, 0]; ov.keep = 1; ov.on = 1
        bg.target = [0, 0, 0]
        fade_begin(g, 2, 0x1E)
    elif eff == 6:                                                # 0x800440A4: squares fall
        for row in range(15):
            for col in range(20):
                v = col + 7 if col < 10 else 0x1A - col
                v = v - 7 + row if 7 - row >= 0 else v + 7 - row
                r1 = core.rnd(g, 129); r2 = core.rnd(g, 65)
                tr.t[row][col] = [-(v * 2), _s16(0x40 - r1), _s16(-r2 - 0x10)]
        bg.cur = [0xFF0000, 0xFF0000, 0]; bg.target = [0, 0, 0]; bg.on = 1
        ov.cur = [0, 0, 0]; ov.target = [0xFF0000, 0xFF0000, 0]; ov.keep = 1; ov.on = 1
        fade_begin(g, 2, 0x64)
    elif eff == 8:                                                # 0x8004428C: game over
        order = [R.u8(0x8009BC10 + i) for i in range(20)]
        for row in range(15):
            for col in range(20):
                tr.t[row][col] = [(row * 2 if col & 1 else (0xE - row) * 2) + order[col], 0]
        ov.target = [0, 0xF00000, 0xF00000]; ov.cur = [0, 0, 0]; ov.keep = 1; ov.on = 1
        bg.target = [0, 0, 0]
        fade_begin(g, 2, 0xB4)
    elif eff == 11:                                               # 0x80044394: to the title
        tr.line = 0xEF
        ov.target = [0xFF0000] * 3; ov.cur = [0, 0, 0]; ov.on = 1
        fade_begin(g, 2, 0x12C)
    else:                                                         # 0x80043C7C: none
        fade_begin(g, 2, 1)
    return tr


def _full(tr):
    tr.ops.append((0, 0, W, H, 0, 0))


@port(0x80045388, ret=True)
def transition_step(g, eff):
    """One frame of the transition; fills g.transition.ops (back to front).  Returns non-zero
    while it runs."""
    tr = g.transition; tr.ops = []
    if eff == 4: return _step4(g, tr)
    if eff == 5: return _step5(g, tr)
    if eff == 6: return _step6(g, tr)
    if eff == 8: return _step8(g, tr)
    if eff == 11: return _step11(g, tr)
    busy = fade_tick(g)                                           # 0x80044470
    _full(tr)
    return busy if eff in (0, 2, 9, 10) else 0


def _step4(g, tr):
    fade_tick(g)
    drawn = 0; ops = []
    for row in range(15):
        y0 = row * 16
        for col in range(20):
            x0 = col * 16
            s = tr.t[row][col]
            s[0] = _s16(s[0] + 1); timer = s[0]; t0 = 0
            if timer > 0:
                left = s[1] - timer
                if left <= 0: continue
                lo = (left << 16) // s[1]
                t0 = 8 - ((lo * 8) >> 16)
                if t0 >= 8: continue
                ax = ((lo * (s[2] - 0x98)) >> 16) + 0x98
                ay = ((lo * (s[3] - 0x70)) >> 16) + 0x70
                dx = ax + ((lo * (x0 - ax)) >> 16) + t0
                dy = ay + ((lo * (y0 - ay)) >> 16) + t0
            else:
                dx, dy = x0, y0
            n = 16 - t0 * 2
            ops.append((x0 + t0, y0 + t0, n, n, dx, dy)); drawn = 1
    tr.ops = ops[::-1]                                            # each was put in front of the last
    return drawn


def _step5(g, tr):
    busy = fade_tick(g)
    _full(tr)
    lines = []
    for y in range(H):
        off = ((core.rnd(g, 513) - 0x100) * tr.word) >> 16
        if 0 <= off < W: lines.append((0, y, W - off, 1, off, y))
        elif -W < off < 0: lines.append((-off, y, W + off, 1, 0, y))
    tr.ops += lines[::-1]
    tr.word = _s32(tr.word + 0x80)
    return busy


def _step6(g, tr):
    fade_tick(g)
    drawn = 0; ops = []
    for row in range(15):
        for col in range(20):
            s = tr.t[row][col]
            dx, dy = col * 16, row * 16
            sx, sy, w, h = dx, dy, 16, 16
            timer = s[0]
            if timer > 0:
                dy = sy + (_s16(s[2]) >> 4)
                dx += (s[1] * timer) >> 4
                if dx < 0:
                    if dx < -15: continue
                    w = dx + 16; sx -= dx; dx = 0
                elif dx + 16 >= W + 1:
                    if dx >= W: continue
                    w = W - dx
                if dy < 0:
                    if dy < -15: continue
                    h = dy + 16; sy -= dy; dy = 0
                elif dy + 16 >= H + 1:
                    if dy >= H: continue
                    h = H - dy
                s[2] = _s16(s[2] + timer * 4)
            s[0] = timer + 1
            ops.append((sx, sy, w, h, dx, dy)); drawn = 1
    tr.ops = ops[::-1]
    return drawn


def _step8(g, tr):
    if fade_tick(g) != 0:
        _full(tr)
        return 1
    drawn = 0; ops = []
    for row in range(15):
        for col in range(20):
            s = tr.t[row][col]
            if s[0] == 0:
                a = _s16(s[1] + 0x80)
                if a >= 0x800: continue
                s[1] = a; k = a >> 8
            else:
                s[0] -= 1; k = 0
            x, y, n = col * 16 + k, row * 16 + k, 16 - k * 2
            ops.append((x, y, n, n, x, y)); drawn = 1
    tr.ops = ops[::-1]
    if not drawn: g.game_over_done = 1; g.set_flag(0x716, True)  # 0x801DD414 |= 0x400000 (flag 0x716)
    return drawn


def _step11(g, tr):
    busy = fade_tick(g)
    lines = [(0, min(tr.line, y), W, 1, 0, y) for y in range(H)]
    tr.ops = lines[::-1]
    if tr.line: tr.line -= 1
    return busy


def draw_transition(g, surf):
    """The transition frame: cleared with the clear colour, the copies, then the TILE."""
    surf.set_clip(None)
    surf.fill(getattr(g, 'clear_colour', (0, 0, 0)))
    snap = g.snapshot
    for sx, sy, w, h, dx, dy in g.transition.ops:
        if w > 0 and h > 0: surf.blit(snap, (dx, dy), (sx, sy, w, h))
    draw_overlay(g, surf)


# ---------------------------------------------------------------------- arrival --
@port(0x80044FB8)
def arrival(g, r, gg, b, eff):
    """After the new map is set up: its clear colour, the menu held off for 10 frames, and the
    way the picture comes back."""
    g.mem.w32(0x801EFBF8, 0xA)
    bg = fade_state(g, 'fade_bg'); ov = fade_state(g, 'fade_ov')
    bg.target = [r << 16, gg << 16, b << 16]
    ov.keep = 0; ov.on = 0; bg.on = 0
    d = box(g); d[0] = 0; d[1] = 0
    def from_full():
        ov.cur = [0xFF0000] * 3; ov.target = [0, 0, 0]; ov.on = 1
    if eff == 0:
        from_full(); fade_begin(g, 2, 0x10)
    elif eff in (2, 10):
        from_full(); fade_begin(g, 1, 0x10)
    elif eff == 4:
        from_full(); fade_begin(g, 1, 8)
        ov.step[0] >>= 1; ov.step[1] >>= 1
    elif eff == 5:
        d[0] = 0xA0; d[1] = 0x78
        fade_begin(g, 2, 1)
    elif eff == 6:
        d[0] = 0xA0; d[1] = 0x78
        from_full(); fade_begin(g, 1, 0x18)
    elif eff == 8:
        from_full(); fade_begin(g, 2, 0x3C)
        ov.step[0] = _s32(ov.step[2] * 4)
    else:
        fade_begin(g, 2, 1)
