"""The save menu's windows, ported from the US ALUN_CD.EXE: the two-line message window (UI
task 9) and the list window (UI task 10, the save records / the files to erase).  The state is
where the game keeps it (g.mem); the remake draws from it (alundra_remake.draw_save_windows).

Task 9 (0x80052400 opens it, 0x80052660 each frame, 0x800523D8 asks it to close):
  0x80121C00 / 0x80121C81  the two lines (up to 128 letters each)
  0x80121B84  -> where the answer goes: 0 while it is up, -1 once it has gone
  0x80121D84  its slide record (menu.slide), +0x18 / +0x1A the window's own place
  0x80121DA0  flags: 1 sliding in, 2 sliding out, 4 up, 8 asked to close
  0x80121B88 / 0x80121BB0  the two text sprites (2 buffers of 0x14 each), drawn 16 / 32 pixels
              below the window's top (the window: config 0x8009EE24, the task's +8 / +0xA offset)

Task 10 (0x8005AA94 opens it with the list, its two texts and where the answer goes; 0x8005A2D4
starts it; 0x8005AF04 each frame): a heading window (0x8009EE24, the first text; after Cross the
second) under four entry windows that scroll (0x800C6004 + 0x74 * k: +0 shown, +4 -> its window
config, +8 its slide record, +0x24 / +0x4C its two text sprites; 0x800C61D8 their rows' y: 0,
64, 128, 240) with colour fades (0x80121DD0 + 0x30 * k, 0x8005BF04 / 0x8005BF48: 0x40 grey, the
middle one 0x80 bright).
  0x800C5FF8  the entry window that takes the next text   0x800C5FFC  the next list entry
  0x800C6000  flags: 1 coming in, 2 going, 4 scrolling, 8 the YES / NO asked
  0x80121DA8  the entry under the cursor       0x80121DAC  the YES / NO answer
  0x80152BE0  -> the list (two text pointers per entry, ended by 0)
  0x80153338  -> the two texts           0x80121DB0  -> where the answer goes
Down / Up (pad repeat) scroll, Cross asks "YES / NO"; YES ends the task with the entry, NO with
-2.  Opening it slides the HUD out (0x8004D1B8)."""
from .registry import port
from . import calls, core
from .menu import task_start, task_end, slide
from .mem import Mem as _Mem
import struct as _struct
_U32 = _struct.Struct('<I')

MSG_TEXT1, MSG_TEXT2, MSG_RES, MSG_SL, MSG_FLAGS = 0x80121C00, 0x80121C81, 0x80121B84, 0x80121D84, 0x80121DA0
MSG_PRIM1, MSG_PRIM2 = 0x80121B88, 0x80121BB0
WIN = 0x8009EE24                       # the heading / message window's config
CUR_TASK, BUFI = 0x801533B4, 0x801E5F38
OT = 0x801F53A0

ENT, ENT_SIZE, ROWS_Y, ROWS_Y0 = 0x800C6004, 0x74, 0x800C61D8, 0x800C61D4
NEXT_WIN, NEXT_ENTRY, LFLAGS = 0x800C5FF8, 0x800C5FFC, 0x800C6000
CURSOR, ANSWER, RES_AT, LIST_AT, TEXTS_AT = 0x80121DA8, 0x80121DAC, 0x80121DB0, 0x80152BE0, 0x80153338
WIN_SL = 0x80121DB4                    # the heading window's slide record
FADES = 0x80121DD0
HEAD_PRIM = 0x80121E90


def _edge(m, cfg, i):
    v = m.s16(cfg + 2 * i)
    return core.s16(v - m.s16(cfg + 4 + 2 * i) * 8) if v < 0 else v


def _link(m, prim, ot):
    m.w32(prim, (m.u32(prim) & 0xFF000000) | (m.u32(ot) & 0xFFFFFF))
    m.w32(ot, (m.u32(ot) & 0xFF000000) | (prim & 0xFFFFFF))


def _fast(g):
    """The remake's quick way through a window's sprites (the same bytes written): only on the
    plain memory and while setSprt is the port's own (the checks replace it to see each call)."""
    from . import message
    return type(g.mem) is _Mem and calls.resolve(0x80086C7C) is message.set_sprt and not hasattr(g, 'ram')


def _link_run(m, s, n, ot, rgb=None):
    """n sprites of 0x14 bytes from s, each linked at the head of the list ot as _link does
    (with rgb: each first made a sprite - setSprt - and given that colour)."""
    b = m.b; o = ot & 0x1FFFFF
    head = _U32.unpack_from(b, o)[0]
    for _ in range(n):
        a = s & 0x1FFFFF
        if rgb is not None:
            b[a + 3] = 4; b[a + 7] = 0x64
            b[a + 4], b[a + 5], b[a + 6] = rgb
        _U32.pack_into(b, a, (_U32.unpack_from(b, a)[0] & 0xFF000000) | (head & 0xFFFFFF))
        head = (head & 0xFF000000) | (s & 0xFFFFFF)
        s += 0x14
    _U32.pack_into(b, o, head)


def _linked(g, task):
    """The remake's note that the task put its window in this frame's drawing lists (the picture
    shows only what was linked: not on the frame a window is opened, nor once it has gone)."""
    s = getattr(g, 'sw_linked', None)
    if s is not None: s.add(task)


def _slide_in_from_below(m, sl, win):
    """A slide record: from the window's x, y 240 to its own place (which is kept at +0x18)."""
    m.w32(sl + 8, 2); m.w32(sl, 0); m.w32(sl + 4, 0xF)
    m.w16(sl + 0xC, _edge(m, win, 0)); m.w16(sl + 0xE, 0xF0)
    m.w16(sl + 0x10, _edge(m, win, 0)); m.w16(sl + 0x12, _edge(m, win, 1))


def _slide_out_below(m, sl, win):
    m.w32(sl + 8, 2); m.w32(sl, 0); m.w32(sl + 4, 0xF)
    m.w16(sl + 0xC, _edge(m, win, 0)); m.w16(sl + 0xE, _edge(m, win, 1))
    m.w16(sl + 0x10, _edge(m, win, 0)); m.w16(sl + 0x12, 0xF0)


# ------------------------------------------------------------------ task 9: the message window
@port(0x80052400, ret=True)
def msg_window_open(g, a, b, res):
    m = g.mem
    m.w32(MSG_RES, res); m.w32(res, 0)
    for dst, src in ((MSG_TEXT1, a), (MSG_TEXT2, b)):
        i = 0
        while True:
            c = m.u8(src + i); m.w8(dst + i, c)
            if c == 0: break
            i += 1
            if not i < 0x80: break
        m.w8(dst + i, 0)
    if calls.call(g, 0x80048EBC, 9) == 0: return 0
    _slide_in_from_below(m, MSG_SL, WIN)
    m.w16(MSG_SL + 0x18, m.u16(WIN)); m.w16(MSG_SL + 0x1A, m.u16(WIN + 2))
    t = m.u32(CUR_TASK)
    m.w32(MSG_FLAGS, 5)
    w = m.u32(t + 4)
    calls.call(g, 0x800482A0, MSG_PRIM1, MSG_TEXT1, 0x40, m.s16(w) + m.s16(t + 8), m.s16(w + 2) + m.s16(t + 0xA), 1)
    t = m.u32(CUR_TASK); w = m.u32(t + 4)
    calls.call(g, 0x800482A0, MSG_PRIM2, MSG_TEXT2, 0x40, m.s16(w) + m.s16(t + 8), m.s16(w + 2) + m.s16(t + 0xA) + 0x10, 2)
    return 1


@port(0x800523D8)
def msg_window_close(g):
    f = g.mem.s32(MSG_FLAGS)
    if f & 4: g.mem.w32(MSG_FLAGS, f | 8)


@port(0x80052660, ret=True)
def msg_window_frame(g, task):
    m = g.mem
    f = m.s32(MSG_FLAGS)
    if f & 3:
        if calls.call(g, 0x80048CF8, m.u32(m.u32(task) + 4), MSG_SL) == 1:
            f = m.s32(MSG_FLAGS)
            if f & 1: m.w32(MSG_FLAGS, f & ~1)
            if m.s32(MSG_FLAGS) & 2:
                m.w16(WIN + 2, m.u16(MSG_SL + 0x1A)); m.w16(WIN, m.u16(MSG_SL + 0x18))
                m.w32(m.u32(MSG_RES), -1)
                calls.call(g, 0x80048BD0, task)
                return 0
    elif f & 8:
        m.w32(MSG_FLAGS, (f & ~8) | 2)
        _slide_out_below(m, MSG_SL, WIN)
        core.play_sound(g, 5)
    b = m.s32(BUFI)
    o = b * 0x14
    for p in (MSG_PRIM1, MSG_PRIM2):
        m.w16(p + o + 0x10, 0xFF); m.w16(p + o + 0x12, 0x10)
    t = m.u32(task); w = m.u32(t + 4)
    m.w16(MSG_PRIM1 + o + 8, m.u16(w) + m.u16(t + 8))
    m.w16(MSG_PRIM1 + o + 0xA, m.u16(w + 2) + m.u16(t + 0xA))
    m.w16(MSG_PRIM2 + o + 8, m.u16(w) + m.u16(t + 8))
    m.w16(MSG_PRIM2 + o + 0xA, m.u16(w + 2) + m.u16(t + 0xA) + 0x10)
    ot = 0x801F53A8 + b * 0x28
    _link(m, MSG_PRIM1 + o, ot); _link(m, MSG_PRIM2 + o, ot)
    _linked(g, 9)
    return 1


@port(0x8005236C, ret=True)
def yes_no_open_default(g, first, second, answer_at):
    """The YES / NO window with the cursor on *answer_at - 1 (then 0 until answered)."""
    m = g.mem
    m.w32(0x80121B7C, first); m.w32(0x80121B80, second)
    calls.call(g, 0x80051D64, 0x80052300, 1, 0x80121B7C)
    m.w32(0x80121B78, answer_at)
    m.w32(0x8013D5C0, m.s32(answer_at) - 1)
    m.w32(answer_at, 0)
    return 1


# ------------------------------------------------------------------ task 10: the list window
@port(0x8005BF04)
def fade_set(g, r, a, b, c, d, e, f, n):
    m = g.mem
    m.w32(r, a); m.w32(r + 4, b); m.w32(r + 8, c)
    m.w32(r + 0x18, a); m.w32(r + 0x1C, b); m.w32(r + 0x20, c)
    m.w32(r + 0x24, 0); m.w32(r + 0x2C, 0)
    m.w32(r + 0xC, d); m.w32(r + 0x10, e); m.w32(r + 0x14, f)
    m.w32(r + 0x28, n)


def _div(a, b):
    if b == 0: raise ZeroDivisionError('0x8005BF48')
    q = abs(a) // abs(b)
    return core.s32(q if (a >= 0) == (b >= 0) else -q)


@port(0x8005BF48, ret=True)
def fade_step(g, r):
    """One step of a colour fade (+0 / +4 / +8 from, +0xC / +0x10 / +0x14 to, +0x18.. now, +0x24
    tick, +0x28 length): the green and blue steps are measured from the red start, and the end
    takes red's and blue's target for green - as the game does."""
    m = g.mem
    t = m.s32(r + 0x24) + 1; n = m.s32(r + 0x28)
    m.w32(r + 0x24, t)
    if t == n:
        m.w32(r + 0x18, m.s32(r + 0xC)); m.w32(r + 0x1C, m.s32(r + 0x14)); m.w32(r + 0x20, m.s32(r + 0x14))
        if m.s32(r + 0x2C) == 0:
            m.w32(r + 0x2C, 1); return 0
        return -1
    a0 = m.s32(r)
    x = _div(core.s32((m.s32(r + 0xC) - a0) * t), n)
    y = _div(core.s32((m.s32(r + 0x10) - m.s32(r + 4)) * m.s32(r + 0x24)), m.s32(r + 0x28))
    z = _div(core.s32((m.s32(r + 0x14) - m.s32(r + 8)) * m.s32(r + 0x24)), m.s32(r + 0x28))
    m.w32(r + 0x18, x + a0); m.w32(r + 0x1C, y + m.s32(r)); m.w32(r + 0x20, z + m.s32(r))
    return 0


def _ent(k): return ENT + ENT_SIZE * (k & 3)


@port(0x8005AB08, ret=True)
def list_entry_text(g, k, i):
    """Entry window k shows list entry i (its two texts), or is marked empty past the list."""
    m = g.mem
    p = m.u32(LIST_AT) + 8 * i
    e = ENT + ENT_SIZE * k
    if m.u32(p) == 0:
        m.w32(e, 0); return 0
    m.w32(e, 1)
    w = m.u32(e + 4)
    calls.call(g, 0x800482A0, e + 0x24, m.u32(p), 0x10, m.s16(w), m.s16(w + 2), 2 * k + 1)
    w = m.u32(e + 4)
    p = m.u32(LIST_AT) + 8 * i
    calls.call(g, 0x800482A0, e + 0x4C, m.u32(p + 4), 0x10, m.s16(w), m.s16(w + 2), 2 * k + 2)
    return 1


@port(0x8005AC2C)
def list_entry_draw(g, e, fade):
    m = g.mem
    w = m.u32(e + 4)
    n = core.s32(m.s16(w + 6) * m.s16(w + 4))
    b = m.s32(BUFI)
    s = m.u32(w + 8 + 4 * b)
    if _fast(g):
        rgb = (m.u32(fade + 0x18) & 0xFF, m.u32(fade + 0x1C) & 0xFF, m.u32(fade + 0x20) & 0xFF)
        _link_run(m, s, max(n, 0), OT + m.s32(BUFI) * 0x28, rgb)
        s += 0x14 * max(n, 0)
    else:
        for _ in range(max(n, 0)):
            calls.call(g, 0x80086C7C, s)
            m.w8(s + 4, m.u32(fade + 0x18)); m.w8(s + 5, m.u32(fade + 0x1C)); m.w8(s + 6, m.u32(fade + 0x20))
            _link(m, s, OT + m.s32(BUFI) * 0x28)
            s += 0x14
    b = m.s32(BUFI); o = b * 0x14
    w = m.u32(e + 4)
    m.w16(e + o + 0x2C, m.u16(w) + 0x10); m.w16(e + o + 0x2E, m.u16(w + 2) + 8)
    m.w16(e + o + 0x54, m.u16(w) + 0x10); m.w16(e + o + 0x56, m.u16(w + 2) + 0x20)
    ot = 0x801F53A8 + b * 0x28
    _link(m, e + o + 0x24, ot); _link(m, e + o + 0x4C, ot)


@port(0x8005AE4C)
def window_link(g, win):
    m = g.mem
    b = m.s32(BUFI)
    s = m.u32(win + 8 + 4 * b)
    ot = 0x801F53B4 + b * 0x28
    if _fast(g):
        _link_run(m, s, max(m.s16(win + 6), 0) * max(m.s16(win + 4), 0), ot)
        return
    r = 0
    while r < m.s16(win + 6):
        c = 0
        while c < m.s16(win + 4):
            c += 1
            _link(m, s, ot); s += 0x14
        r += 1


@port(0x8005AA94, ret=True)
def list_open(g, lst, texts, res):
    calls.call(g, 0x8004D1B8)
    m = g.mem
    m.w32(LIST_AT, lst); m.w32(TEXTS_AT, texts); m.w32(RES_AT, res)
    m.w32(res, -1)
    calls.call(g, 0x80048EBC, 0xA)
    return 1


def _head_slide_in(m):
    _slide_in_from_below(m, WIN_SL, WIN)


@port(0x8005A2D4, ret=True)
def list_start(g, task):
    m = g.mem
    m.w32(m.u32(task) + 0x14, 0x8005AF04)
    for k in range(4):
        e = ENT + ENT_SIZE * k
        m.w16(m.u32(e + 4) + 2, m.u32(ROWS_Y + 4 * k))
        m.w32(e, 0)
    m.w32(NEXT_WIN, 1); m.w32(NEXT_ENTRY, 0); m.w32(LFLAGS, 0)
    for k in range(4):
        e = ENT + ENT_SIZE * k; w = m.u32(e + 4)
        _slide_in_from_below(m, e + 8, w)
        w = m.u32(e + 4)
        m.w16(e + 0x20, m.u16(w)); m.w16(e + 0x22, m.u16(w + 2))
    for k, v in enumerate((0x40, 0x80, 0x40, 0x40)):
        calls.call(g, 0x8005BF04, FADES + 0x30 * k, 0, 0, 0, v, v, v, 0xF)
    _head_slide_in(m)
    m.w16(WIN_SL + 0x1A, m.u16(WIN + 2)); m.w16(WIN_SL + 0x18, m.u16(WIN))
    calls.call(g, 0x800482A0, HEAD_PRIM, m.u32(m.u32(TEXTS_AT)), 0x40, m.s16(WIN), m.s16(WIN + 2), 0)
    lst = m.u32(LIST_AT)
    m.w32(LFLAGS, m.s32(LFLAGS) | 1)
    if m.u32(lst) != 0:
        o = 0
        while True:
            calls.call(g, 0x80083EE4, m.u32(m.u32(LIST_AT) + o)); o += 4
            calls.call(g, 0x80083EE4, 0x80026970)
            if m.u32(m.u32(LIST_AT) + o) == 0: break
    if calls.call(g, 0x8005AB08, m.s32(NEXT_WIN), m.s32(NEXT_ENTRY)) != 0: m.w32(NEXT_ENTRY, m.s32(NEXT_ENTRY) + 1)
    m.w32(NEXT_WIN, (m.s32(NEXT_WIN) + 1) & 3)
    if calls.call(g, 0x8005AB08, m.s32(NEXT_WIN), m.s32(NEXT_ENTRY)) != 0: m.w32(NEXT_ENTRY, m.s32(NEXT_ENTRY) + 1)
    m.w32(CURSOR, 0)
    m.w32(NEXT_WIN, (m.s32(NEXT_WIN) + 1) & 3)
    return 1


@port(0x8005AF04, ret=True)
def list_frame(g, task):
    m = g.mem
    nw = m.s32(NEXT_WIN)
    a1 = (nw + 2) & 3
    f = m.s32(LFLAGS)
    if f & 5:
        calls.call(g, 0x80048CF8, WIN, WIN_SL)
        for k in range(4): calls.call(g, 0x8005BF48, FADES + 0x30 * k)
        calls.call(g, 0x80048CF8, m.u32(_ent(0) + 4), _ent(0) + 8)
        calls.call(g, 0x80048CF8, m.u32(_ent(1) + 4), _ent(1) + 8)
        calls.call(g, 0x80048CF8, m.u32(_ent(3) + 4), _ent(3) + 8)
        if calls.call(g, 0x80048CF8, m.u32(_ent(2) + 4), _ent(2) + 8) != 0:
            f = m.s32(LFLAGS)
            if f & 1: m.w32(LFLAGS, f & ~1)
            f = m.s32(LFLAGS)
            if f & 4:
                m.w32(LFLAGS, f & ~4)
                m.w32(ENT + ENT_SIZE * m.s32(NEXT_WIN), 0)
    elif f & 2:
        for k in range(4): calls.call(g, 0x8005BF48, FADES + 0x30 * k)
        for k in (0, 1, 2, 3): calls.call(g, 0x80048CF8, m.u32(_ent(k) + 4), _ent(k) + 8)
        if calls.call(g, 0x80048CF8, WIN, WIN_SL) != 0:
            m.w32(LFLAGS, m.s32(LFLAGS) & ~2)
            m.w16(WIN, m.u16(WIN_SL + 0x18)); m.w16(WIN + 2, m.u16(WIN_SL + 0x1A))
            calls.call(g, 0x80048BD0, task)
            v = -2 if m.s32(ANSWER) == 2 else m.s32(CURSOR)
            m.w32(m.u32(RES_AT), v)
            return 1
    elif f & 8:
        if (m.s32(ANSWER) - 1) & 0xFFFFFFFF < 2:
            m.w32(LFLAGS, 2)
            k = (nw + 1) & 3
            for i in range(3):
                e = ENT + ENT_SIZE * k; sl = e + 8
                m.w16(m.u32(e + 4) + 2, -1)
                m.w32(sl + 8, 2); m.w32(sl, 0); m.w32(sl + 4, 0xF)
                w = m.u32(e + 4)
                m.w16(sl + 0xC, _edge(m, w, 0))
                y = m.s32(ROWS_Y + 4 * i)
                w = m.u32(e + 4)
                m.w16(sl + 0xE, core.s16(y - m.s16(w + 6) * 8) if y < 0 else y)
                w = m.u32(e + 4); m.w16(sl + 0x10, _edge(m, w, 0))
                w = m.u32(e + 4); m.w16(sl + 0x12, _edge(m, w, 1))
                w = m.u32(e + 4); m.w16(sl + 0x18, m.u16(w)); m.w16(sl + 0x1A, m.u16(w + 2))
                calls.call(g, 0x80048CF8, m.u32(e + 4), sl)
                k = (k + 1) & 3
            nw = m.s32(NEXT_WIN)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((nw + 1) & 3), 0x40, 0x40, 0x40, 0, 0, 0, 0xF)
            nw = m.s32(NEXT_WIN)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((nw + 2) & 3), 0x80, 0x80, 0x80, 0, 0, 0, 0xF)
            nw = m.s32(NEXT_WIN)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((nw + 3) & 3), 0x40, 0x40, 0x40, 0, 0, 0, 0xF)
            _slide_out_below(m, WIN_SL, WIN)
    elif g.pad_repeat & core.confirm_bit(g):              # Cross (JP confirm: Square)
        m.w32(ANSWER, 0)
        a = calls.call(g, 0x80083FC4, 0x4A); b = calls.call(g, 0x80083FC4, 0x4B)
        calls.call(g, 0x80052310, a, b, ANSWER)
        calls.call(g, 0x800482A0, HEAD_PRIM, m.u32(m.u32(TEXTS_AT) + 4), 0x40, m.s16(WIN), m.s16(WIN + 2), 0)
        m.w32(LFLAGS, 8)
    else:
        if g.pad_repeat & 0x4000 and m.s32(_ent((a1 + 1) & 3)) & 1:
            k = (m.s32(NEXT_WIN) + 1) & 3
            for i in range(4):
                e = ENT + ENT_SIZE * k; sl = e + 8
                m.w16(m.u32(e + 4) + 2, m.u32(ROWS_Y0 + 4 * i))
                _move(g, e, m.s32(ROWS_Y + 4 * i))
                k = (k + 1) & 3
            nw = m.s32(NEXT_WIN)
            calls.call(g, 0x8005BF04, FADES + 0x30 * nw, 0, 0, 0, 0x40, 0x40, 0x40, 0xF)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((m.s32(NEXT_WIN) + 1) & 3), 0x40, 0x40, 0x40, 0, 0, 0, 0xF)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((m.s32(NEXT_WIN) + 2) & 3), 0x80, 0x80, 0x80, 0x40, 0x40, 0x40, 0xF)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((m.s32(NEXT_WIN) + 3) & 3), 0x40, 0x40, 0x40, 0x80, 0x80, 0x80, 0xF)
            m.w32(LFLAGS, m.s32(LFLAGS) | 4)
            if calls.call(g, 0x8005AB08, m.s32(NEXT_WIN), m.s32(NEXT_ENTRY)) != 0: m.w32(NEXT_ENTRY, m.s32(NEXT_ENTRY) + 1)
            m.w32(NEXT_WIN, (m.s32(NEXT_WIN) + 1) & 3)
            m.w32(CURSOR, m.s32(CURSOR) + 1)
        if g.pad_repeat & 0x1000 and m.s32(CURSOR) != 0:
            k = m.s32(NEXT_WIN)
            m.w32(LFLAGS, m.s32(LFLAGS) | 4)
            for i in range(4):
                e = ENT + ENT_SIZE * k
                m.w16(m.u32(e + 4) + 2, m.u32(ROWS_Y + 4 * i))
                _move(g, e, m.s32(ROWS_Y0 + 4 * i))
                k = (k + 1) & 3
            c = m.s32(CURSOR)
            if c >= 2: calls.call(g, 0x8005AB08, m.s32(NEXT_WIN), c - 2)
            calls.call(g, 0x8005BF04, FADES + 0x30 * m.s32(NEXT_WIN), 0, 0, 0, 0x40, 0x40, 0x40, 0xF)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((m.s32(NEXT_WIN) + 1) & 3), 0x40, 0x40, 0x40, 0x80, 0x80, 0x80, 0xF)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((m.s32(NEXT_WIN) + 2) & 3), 0x80, 0x80, 0x80, 0x40, 0x40, 0x40, 0xF)
            calls.call(g, 0x8005BF04, FADES + 0x30 * ((m.s32(NEXT_WIN) + 3) & 3), 0x40, 0x40, 0x40, 0, 0, 0, 0xF)
            c = m.s32(CURSOR); m.w32(CURSOR, c - 1)
            if m.u32(m.u32(LIST_AT) + 8 * (c - 1) + 8) == 0: m.w32(NEXT_ENTRY, c)
            else: m.w32(NEXT_ENTRY, c + 1)
            m.w32(NEXT_WIN, (m.s32(NEXT_WIN) - 1) & 3)
    calls.call(g, 0x8005AE4C, WIN)
    for k in range(4):
        if m.s32(ENT + ENT_SIZE * k) & 1: calls.call(g, 0x8005AC2C, ENT + ENT_SIZE * k, FADES + 0x30 * k)
    b = m.s32(BUFI); o = b * 0x14
    m.w16(HEAD_PRIM + o + 8, m.u16(WIN) + 0x10); m.w16(HEAD_PRIM + o + 0xA, m.u16(WIN + 2) + 0x10)
    _link(m, HEAD_PRIM + o, 0x801F53B8 + b * 0x28)
    _linked(g, 10)
    return 1


def _move(g, e, to_y):
    """An entry window's slide: from where it now is (its y just set) to row y to_y."""
    m = g.mem; sl = e + 8
    m.w32(sl + 8, 2); m.w32(sl, 0); m.w32(sl + 4, 0xF)
    w = m.u32(e + 4)
    m.w16(sl + 0xC, _edge(m, w, 0))
    w = m.u32(e + 4)
    m.w16(sl + 0xE, core.s16(to_y - m.s16(w + 6) * 8) if to_y < 0 else to_y)
    w = m.u32(e + 4); m.w16(sl + 0x10, _edge(m, w, 0))
    w = m.u32(e + 4); m.w16(sl + 0x12, _edge(m, w, 1))
    w = m.u32(e + 4); m.w16(sl + 0x18, m.u16(w)); m.w16(sl + 0x1A, m.u16(w + 2))
    calls.call(g, 0x80048CF8, m.u32(e + 4), sl)


# ------------------------------------------------------------------ text into a VRAM row
@port(0x800482A0)
def draw_text(g, prims, text, _a2, x, y, row):
    """A whole string (padded with spaces to 128 letters) drawn into VRAM text row row (0x120 +
    16 * row; rows from 4 on are one lower, 14 and over refused) by 0x80048780, and the two
    buffers' sprites of prims set up for it: 255 x 16, u 0 v 0x20 + 16 * row, palette
    0x80142B70, at x, y.  The letters themselves are the remake's drawing (g.ui)."""
    m = g.mem
    calls.call(g, 0x800845E8, 0x801D07F8, 0x800)
    if not row < 4: row += 1
    if not row < 0xE:
        calls.call(g, 0x80083EE4, 0x80024068); return
    ui = getattr(g, 'ui', None)
    if ui is not None and not hasattr(g, 'ram'): ui(0x800482A0, prims, text, _a2, x, y, row - (1 if row > 4 else 0))
    v = (row * 16 + 0x20) & 0xFF
    for k in range(2):
        p = prims + 0x14 * k
        m.w16(p + 0x10, 0xFF); m.w16(p + 0x12, 0x10)
        m.w8(p + 0xC, 0); m.w8(p + 0xD, v)
        calls.call(g, 0x80086C7C, p)
        calls.call(g, 0x80086B64, p, 0)
        calls.call(g, 0x80086B8C, p, 1)
        m.w16(p + 0xE, m.u16(0x80142B70))
        m.w16(p + 0xA, y); m.w16(p + 8, x)
