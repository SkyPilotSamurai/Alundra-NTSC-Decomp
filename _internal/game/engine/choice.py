"""The two-answer window (UI task 3): YES / NO under a question, ported from the US ALUN_CD.EXE.
Script command 44 (0x8003F334) opens it with the texts 0x43 / 0x44 of the 'etc' table
(0x80083FC4); the save point opens it with 0x41 / 0x42.  Everything lives where the game keeps it:

  0x80121B7C / 80  the two texts' addresses (0x80052310's arguments)
  0x80121B78       where the answer goes (1 = the first, 2 = the second): 0x80104828 for command 44
  0x8013D7F4       s16: how many answers less one (1);  0x8013D7F8 the routine that takes the answer
  0x8013D7FC       the first text (6 letters at most), 0x8013D803 the second
  0x8013D590       the cursor: +0 the answer when one is taken, +4 its animation clock (0-39),
                   +8 its sprite in each buffer (0x14 bytes each; the hand of WIND u 176-224, v 56)
  0x8013D5C0       the answer under the cursor (0 / 1)
  0x8013D5C4       the text sprites: buffer * 0x78 + answer * 0x3C + 0x14 * part (three per answer)
  0x8013D80C       the window's slide record (menu.slide): +0 tick, +4 frames (15), +8 count,
                   +C from, +10 to, +18 the window's own place, put back when it has gone
  0x800A6E54       the window (x 176, y 144, 16 x 4 cells of 8)

The frame routines: 0x800519A0 (the first frame: the texts into VRAM 0x3C0 / 0x3E0, 0x1D0, the
sprites set up, the slide in from x 320), 0x8005193C (sliding in), 0x80051710 (Left / Right move
the cursor with sound 1; Cross takes the answer: sounds 5 and 2 (first) or 3 (second), the
window slides back out to x 320), 0x8005165C (sliding out; then the window goes back to its own
place, the task ends and the answer is handed over).  0x800513F4 places the cursor over the
middle of the answer (x + 0x30 * answer + 4 * letters - 8, y - 16) and the texts (16 pixels a
sprite, every second letter)."""
from .registry import port
from . import core, calls
from .menu import task_start, task_end, slide

ARGS, ANSWER_AT = 0x80121B7C, 0x80121B78
COUNT, TAKER, TEXTS = 0x8013D7F4, 0x8013D7F8, 0x8013D7FC
CURSOR, SEL, PRIMS, SL = 0x8013D590, 0x8013D5C0, 0x8013D5C4, 0x8013D80C
CFG = 0x800A6E54
BUFI, OT = 0x801E5F38, 0x801F53B4
ETC = 0x8012B9E0                          # the 'etc' text table (ETC_USA.R): u16 offsets, then texts


# ------------------------------------------------------------------ library routines
@port(0x80084838, ret=True)
def strlen(g, a):
    m = g.mem; n = 0
    while m.u8(a + n): n += 1
    return n


@port(0x80084868, ret=True)
def strncpy(g, d, s, n):
    """C strncpy: up to n letters, the rest of the n filled with 0.  Returns d (0 when d or s is 0)."""
    if d == 0 or s == 0: return 0
    m = g.mem; i = 0; a = d
    while i < n:
        c = m.u8(s); s += 1
        m.w8(a, c); a += 1; i += 1
        if c == 0:
            while i < n: m.w8(a, 0); a += 1; i += 1
            break
    return d


@port(0x80083FC4, ret=True)
def etc_text(g, n):
    """Text n of the 'etc' table (menu and save texts)."""
    g.mem.w32(0x8012E280, ETC)
    return ETC + g.mem.u16(ETC + 2 * n)


def _link(m, prim, ot):
    m.w32(prim, (m.u32(prim) & 0xFF000000) | (m.u32(ot) & 0xFFFFFF))
    m.w32(ot, (m.u32(ot) & 0xFF000000) | (prim & 0xFFFFFF))


def _sprite(g, p):
    calls.call(g, 0x80086C7C, p); calls.call(g, 0x80086B64, p, 0); calls.call(g, 0x80086B8C, p, 1)


# ------------------------------------------------------------------ the cursor (the pointing hand)
@port(0x80051E48)
def cursor_place(g, base, x, y, buf):
    r = base + buf * 0x14
    g.mem.w16(r + 0x10, x); g.mem.w16(r + 0x12, y)


@port(0x80051E64)
def cursor_init(g, base):
    """Its two sprites (16 x 16, frame 0 of the hand, opaque, unshaded, palette 0x80142B70) at 0, 0."""
    m = g.mem
    for i in range(2):
        r = base + 0x14 * i; p = base + 8 + 0x14 * i
        m.w16(r + 0x18, 0x10); m.w16(r + 0x1A, 0x10)
        m.w8(r + 0x14, m.u8(0x800A7740)); m.w8(r + 0x15, m.u8(0x800A7741))
        _sprite(g, p)
        cursor_place(g, base, 0, 0, i)
        m.w16(r + 0x16, m.u16(0x80142B70))


@port(0x80051F40)
def cursor_frame(g, base):
    """The hand's clock (40 frames, a picture every 10) and its sprite into this frame's list."""
    m = g.mem
    c = m.s32(base + 4) + 1; m.w32(base + 4, c)
    if c == 0x28: m.w32(base + 4, 0)
    c = m.s32(base + 4); f = -((-c) // 10) if c < 0 else c // 10          # (mult 0x66666667: towards 0)
    b = m.s32(BUFI)
    m.w8(base + b * 0x14 + 0x14, m.u8(0x800A7740 + f * 0x28))
    b = m.s32(BUFI)
    m.w8(base + b * 0x14 + 0x15, m.u8(0x800A7741 + f * 0x28))
    b = m.s32(BUFI)
    _link(m, base + b * 0x14 + 8, OT + b * 0x28)


# ------------------------------------------------------------------ opening
@port(0x80052300)
def yes_no_taken(g, answer):
    """0x80052310's answer routine: the answer to where it was asked for."""
    g.mem.w32(g.mem.u32(ANSWER_AT), answer)


@port(0x80051D64)
def choice_open(g, taker, count, texts):
    m = g.mem
    m.w32(TAKER, taker); m.w16(COUNT, count)
    calls.call(g, 0x80084868, TEXTS, m.u32(texts), 6)
    calls.call(g, 0x80084868, TEXTS + 7, m.u32(texts + 4), 6)
    calls.call(g, 0x80051E64, CURSOR)
    core.play_sound(g, 4)
    task_start(g, 3)


@port(0x80052310, ret=True)
def yes_no_open(g, first, second, answer_at):
    m = g.mem
    m.w32(ARGS, first); m.w32(ARGS + 4, second)
    calls.call(g, 0x80051D64, 0x80052300, 1, ARGS)
    m.w32(ANSWER_AT, answer_at); m.w32(SEL, 0)
    return 1


# ------------------------------------------------------------------ the frame routines
def _edge(m, cfg, i):
    v = m.s16(cfg + 2 * i)
    return core.s16(v - m.s16(cfg + 4 + 2 * i) * 8) if v < 0 else v


@port(0x800519A0, ret=True)
def choice_start(g, task):
    m = g.mem
    calls.call(g, 0x80048780, TEXTS, 0x801D7F40, 0x3C0, 0x1D0, 0, 0, 0x100, 0x10)
    calls.call(g, 0x80048780, TEXTS + 7, 0x801D7F40, 0x3E0, 0x1D0, 0, 0, 0x100, 0x10)
    for o in range(2):                                     # buffer
        for k in range(2):                                 # answer
            for j in range(3):                             # part
                w = calls.call(g, 0x8004864C, TEXTS + 7 * k)
                p = PRIMS + o * 0x78 + k * 0x3C + j * 0x14
                m.w16(p + 0x10, w); m.w16(p + 0x12, 0x10)
                m.w8(p + 0xC, (k << 7) + 0x10 * j); m.w8(p + 0xD, 0xD0)
                _sprite(g, p)
                m.w16(p + 0xE, m.u16(0x80142B70))
    m.w32(SL + 8, 2); m.w32(SL + 4, 0xF); m.w32(SL, 0)
    m.w16(SL + 0xC, 0x140)
    cfg = m.u32(m.u32(task) + 4)
    m.w16(SL + 0xE, _edge(m, cfg, 1))
    m.w16(SL + 0x10, _edge(m, cfg, 0))
    m.w16(SL + 0x12, _edge(m, cfg, 1))
    m.w16(SL + 0x18, m.u16(cfg)); m.w16(SL + 0x1A, m.u16(cfg + 2))
    slide(g, cfg, SL)
    m.w32(m.u32(task) + 0x14, 0x8005193C)
    calls.call(g, 0x80049280, task)
    return 0


@port(0x800513F4)
def choice_draw(g, task):
    m = g.mem
    sel = m.s32(SEL); rec = m.u32(task); cfg = m.u32(rec + 4)
    x = m.s16(rec + 8) + m.s16(cfg) + sel * 0x30
    x += calls.call(g, 0x80084838, TEXTS + sel * 7) * 4
    rec = m.u32(task); cfg = m.u32(rec + 4)
    calls.call(g, 0x80051E48, CURSOR, x - 8, m.s16(rec + 0xA) + m.s16(cfg + 2) - 0x10, m.s32(BUFI))
    calls.call(g, 0x80051F40, CURSOR)
    for k in range(2):
        i = 0
        while True:
            n = calls.call(g, 0x80084838, TEXTS + 7 * k)
            if not i < (n >> 1): break                       # (a length is never negative)
            b = m.s32(BUFI)
            p = PRIMS + b * 0x78 + k * 0x3C + i * 0x14
            rec = m.u32(task); cfg = m.u32(rec + 4)
            m.w16(p + 8, m.u16(rec + 8) + m.u16(cfg) + i * 16 + k * 0x30)
            rec = m.u32(task); cfg = m.u32(rec + 4)
            m.w16(p + 0xA, m.u16(rec + 0xA) + m.u16(cfg + 2))
            b = m.s32(BUFI)
            _link(m, PRIMS + b * 0x78 + k * 0x3C + i * 0x14, OT + 4 + b * 0x28)
            i += 1
    g.__dict__['choice_drawn'] = True                     # (the remake draws what this placed)


@port(0x8005193C, ret=True)
def choice_slide_in(g, task):
    m = g.mem
    if slide(g, m.u32(m.u32(task) + 4), SL) != 0:
        m.w32(m.u32(task) + 0x14, 0x80051710)
    choice_draw(g, task)
    return 0


@port(0x80051710, ret=True)
def choice_input(g, task):
    m = g.mem
    slide(g, m.u32(m.u32(task) + 4), SL)
    if g.pad_pressed & core.confirm_bit(g):                # Cross (JP confirm: Square): this answer
        m.w32(SL + 8, 2); m.w32(SL, 0); m.w32(SL + 4, 0xF)
        m.w32(CURSOR, m.s32(SEL) + 1)
        cfg = m.u32(m.u32(task) + 4)
        m.w16(SL + 0xC, _edge(m, cfg, 0))
        m.w16(SL + 0xE, _edge(m, cfg, 1))
        m.w16(SL + 0x10, 0x140)
        m.w16(SL + 0x12, _edge(m, cfg, 1))
        core.play_sound(g, 5)
        core.play_sound(g, 2 if m.s32(CURSOR) == 1 else 3)
        m.w32(m.u32(task) + 0x14, 0x8005165C)
    if g.pad_repeat & 0x8000:                              # Left
        if m.s32(SEL) == 1: core.play_sound(g, 1)
        m.w32(SEL, 0)
    if g.pad_repeat & 0x2000:                              # Right
        if m.s32(SEL) == 0: core.play_sound(g, 1)
        m.w32(SEL, 1)
    choice_draw(g, task)
    return 0


@port(0x8005165C, ret=True)
def choice_slide_out(g, task):
    m = g.mem
    if slide(g, m.u32(m.u32(task) + 4), SL) != 1:
        choice_draw(g, task)
        return 1
    cfg = m.u32(m.u32(task) + 4)
    m.w16(cfg, m.u16(SL + 0x18))
    cfg = m.u32(m.u32(task) + 4)
    m.w16(cfg + 2, m.u16(SL + 0x1A))
    task_end(g, task)
    calls.call(g, m.u32(TAKER), m.s32(CURSOR))
    return 1


def install_etc_file(g, data):
    """ETC_USA.R as the game loads it at boot (0x8002C810: 0x80083F04 reads it to 0x8012B9E0)."""
    m = g.mem
    for i, c in enumerate(data): m.w8(ETC + i, c)


@port(0x8002C810)
def boot_names(g):
    """The rest of 0x8002C810 (after the file is in): the item records' name and two description
    pointers (texts 0x200 / 0x280 / 0x300 + item, 0x62 items: 0x800C7DE4 + 8 * item and
    0x800C80F4 / F8 + 8 * item), the chapter names (32 bytes of text k into the table 0x800295B0
    + 0x22 * k + 2, while the entry's flag is not -1) and the speakers' names (text 0x100 + k at
    0x800C6274 + 4 * k)."""
    m = g.mem
    for k in range(0x62):
        m.w32(0x800C7DE4 + 8 * k, calls.call(g, 0x80083FC4, k + 0x200))
        a = calls.call(g, 0x80083FC4, k + 0x280)
        b = calls.call(g, 0x80083FC4, k + 0x300)
        m.w32(0x800C80F4 + 8 * k, a); m.w32(0x800C80F8 + 8 * k, b)
    k = 0
    while True:
        src = calls.call(g, 0x80083FC4, k)
        for i in range(0x20): m.w8(0x800295B2 + 0x22 * k + i, m.u8(src + i))
        if m.s16(0x800295B0 + 0x22 * k) == -1: break
        k += 1
    for k in range(0x100):
        m.w32(0x800C6274 + 4 * k, calls.call(g, 0x80083FC4, k + 0x100))


def install_etc(g, texts, enc='latin-1'):
    """The 'etc' texts where the game keeps them (ETC_USA.R at 0x8012B9E0: u16 offsets, then the
    texts, each ending with 0)."""
    m = g.mem; n = max(texts) + 1 if texts else 0
    a = ETC + 2 * n
    for i in range(n):
        m.w16(ETC + 2 * i, a - ETC)
        for c in texts.get(i, '').encode(enc, 'replace') + b'\0': m.w8(a, c); a += 1
