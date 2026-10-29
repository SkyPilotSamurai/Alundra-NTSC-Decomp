"""The message window (UI task 0) and the speaker's name plate (UI task 12), ported from the
US ALUN_CD.EXE.  Everything lives where the game keeps it (g.mem):

  0x80106AFC  window flags: 1 sliding in, 2 sliding out, 4 open (0x80045F8C: busy)
  0x80104840  its slide record (menu.slide): +0 tick, +4 frames (15), +8 count, +C from, +10 to,
              +18 the window's own place, put back when it has gone
  0x80106B00  the text (0x960 bytes, codes after a backslash)
  0x80107460  print mode: bit 0 a letter every frame while Square is held, bit 1 one every
              0x80107468 (4) frames, bit 2 one per script request (0x80107464), bit 3 paused at
              \\A until Square is pressed
  0x8010746C  frames to the next letter       0x80107470  the line ring's first row (0-2)
  0x80107474  the line being written (0-2)    0x80107478  the next character
  0x8010747C  letters on this line (the talk sound plays on every other one)
  0x80107480  per line: its width when centred (\\H), else 0
  0x8010748C  the three line sprites (2 buffers each)     0x80107504  the "more" marker sprite
  0x8010752C  scrolling (one line, 0x80107538 = 8 frames; 0x80107534 counts down)
  0x8010753C  scroll mode: bit 0 after 0x80107544 (10) frames, bit 1 on Square, bit 2 on a
              script request (0x80107530), bit 3 at once (after \\A)
  0x80107548  close mode at the end: bit 0 after 0x80107554 (360) frames, bit 1 on Square,
              bit 2 on a script request (0x80107558)
  0x8010754C  the text has ended                0x8010755C / 60  the "more" marker and its clock
  0x80107568  talk sound (-1 none, 0-3 = sound 0x4F + n, 4 none)
  0x80153334  where the next letter goes on its line (pixels)
Letters are drawn into a 256 x 16 line buffer (0x801D07F8) and uploaded to VRAM rows 0x120 +
16 * ring (0x80048780); the drawing itself is the remake's (g.ui hooks)."""
from .registry import port
from . import core, calls
from .menu import task_start, task_end, slide, _norm

FLAGS, SLIDE, TEXT, CFG = 0x80106AFC, 0x80104840, 0x80106B00, 0x8009EE24
PMODE, PREQ, INTERVAL, CD = 0x80107460, 0x80107464, 0x80107468, 0x8010746C
TOP, LINE, POS, NCH, CENTRE, PRIMS, ARROWP = 0x80107470, 0x80107474, 0x80107478, 0x8010747C, 0x80107480, 0x8010748C, 0x80107504
SCROLLING, SREQ, ST, SLEN, SMODE, SCD, SWAIT = 0x8010752C, 0x80107530, 0x80107534, 0x80107538, 0x8010753C, 0x80107540, 0x80107544
CMODE, ENDED, CCD, CWAIT, CREQ = 0x80107548, 0x8010754C, 0x80107550, 0x80107554, 0x80107558
ARROW, ARROW_T, FALK, VOICE = 0x8010755C, 0x80107560, 0x80107564, 0x80107568
PEN, LINEBUF, BUFI = 0x80153334, 0x801D07F8, 0x801E5F38
CHARS = 0x8009BC2C                       # per character: width, rows, u, v, y offset (s32 each)
DIGITS = 0x8009C654                      # pointers to "0".."9"
NAME_FLAGS, NAME_SLIDE, NAME_PRIMS, NAME_CFG, NAME_WHO = 0x801EFE08, 0x801EFE0C, 0x801EFE28, 0x800A7724, 0x801EFE50
NAMES = 0x800C5E74                       # sprite index -> its name (sprites 0x100-0x1FF)
SPEAKER_TEXT, GLOBAL_TEXT = 0x801F3150, 0x801F4050

# ---- Japanese mode (Options > Dialogue & font: JP), from the JP ALUN_CD.EXE (SCPS-10035).  The
# state stays at the US addresses above; what differs (JP addresses in brackets):
#   * every character is a 2-byte Shift-JIS glyph from the BIOS kanji ROM, 16 px wide, drawn at
#     line pixel 16 * NCH (msg_print 0x80047F70, glyph 0x80051614); no \H, no \W, no letter widths;
#   * two text lines in a ring of 2 (VRAM rows 0x140 + 16 * ring): a new line scrolls once the
#     second line is done (0x80048BC4); the text sits at (cfg.x + 16, cfg.y + 12 + 16 * k);
#   * the "more" marker blinks over 41 frames (the 41st blank) at (cfg.x + 4 * cfg.w - 8,
#     cfg.y + 16 * LINE + 24) (msg_draw 0x8004770C);
#   * the close wait is 180 frames (msg_boot 0x80047080);
#   * \V / \X numbers are full-width digits, \X2 / \X4 the JP reward names (0x8009D134);
#   * the name plate: the name padded / cut to 6 glyphs, left-aligned at (cfg.x + 16, cfg.y + 8),
#     its window 4 px lower (0x800A81D8: y 144) (0x8005D534 / 0x8005D6F0, draw_text 0x80049048).
JP_REC = (16, 12, 32, 4)                 # the JP message task's text rectangle (0x800A9C38)
JP_DIGITS = [('０１２３４５６７８９'[i]).encode('shift_jis') for i in range(10)]
JP_REWARDS = ['命の器', 'オーガの指輪', '命の器', '銀の腕輪', '命の器', '回復の輪', '命の器', '魔道の杖']


def jp(g): return getattr(g, 'lang', 'us') == 'jp'


def _cdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _cmod(a, b): return a - _cdiv(a, b) * b


def _half(v):
    """(v + (v >> 31)) >> 1: halves towards zero."""
    return _cdiv(v, 2)


def _width(g, c):
    t = getattr(type(getattr(g, 'game_font', None)), '_widths', None)   # European: its disc's 256 records
    if t is not None: return t[c & 0xFF]
    return g.mem.s32(CHARS + 0x14 * (c & 0xFF))


def gap(g):
    """Pixels after each letter: 1 (US), 0 on the European discs (DE 0x800463A0 / 0x800478A0: width only)."""
    return 0 if getattr(g, 'lang', 'us') in ('en_eu', 'fr', 'de', 'it', 'es') else 1


# ------------------------------------------------------------------ small library routines
@port(0x80084838, ret=True)
def strlen(g, a):
    if a == 0: return 0
    n = 0
    while g.mem.u8(a + n): n += 1
    return n


def _cstr(g, a):
    out = bytearray()
    while True:
        c = g.mem.u8(a + len(out))
        if c == 0: return bytes(out)
        out.append(c)


def _write_str(g, a, data):
    for i, c in enumerate(data + b'\0'): g.mem.w8(a + i, c)


@port(0x800847F4, ret=True)
def strcpy(g, a, b):
    if a == 0 or b == 0: return 0
    _write_str(g, a, _cstr(g, b)); return a


@port(0x800846E8, ret=True)
def strcat(g, a, b):
    if a == 0 or b == 0: return 0
    if a + strlen(g, a) == b + strlen(g, b): return 0
    _write_str(g, a + strlen(g, a), _cstr(g, b)); return a


@port(0x80084868, ret=True)
def strncpy(g, a, b, n):
    if a == 0 or b == 0: return 0
    src = _cstr(g, b)[:max(n, 0)]
    data = src + bytes(max(n, 0) - len(src))
    for i, c in enumerate(data): g.mem.w8(a + i, c)
    return a


@port(0x800845E8, ret=True)
def memzero(g, a, n):
    """bzero: n bytes at a (the line buffer: the remake clears its picture of it too)."""
    if a == 0 or n <= 0: return 0
    for i in range(n): g.mem.w8(a + i, 0)
    ui = getattr(g, 'ui', None)
    if ui is not None and not hasattr(g, 'ram'): ui(0x800845E8, a, n)
    return a


@port(0x80084494, ret=True)
def strtol(g, s, *rest):
    """The digit string after a backslash: always decimal here (leading zeros were blanked)."""
    data = s.data if isinstance(s, calls.Buf) else _cstr(g, s)
    t = data.split(b'\0')[0].strip()
    try: return int(t) if t else 0
    except ValueError: return 0


@port(0x80083F74)
def text_log(g, n, addr):
    """Debug hook (empty in the shipped game)."""


@port(0x80050984, ret=True, mock_always=True)
def is_two_byte(g, a):
    """BIOS Krom2RawAdd(two bytes) != -1: a Shift-JIS character (never in the US texts)."""
    if not gap(g): return 0                             # European texts are Windows-1252 (0x80-0x9F are letters)
    code = g.mem.u8(a) << 8 | g.mem.u8(a + 1)
    return int(0x8140 <= code <= 0x84BE or 0x889F <= code <= 0x9872)


# ------------------------------------------------------------------ primitives (libgpu)
@port(0x80086C7C)
def set_sprt(g, p): g.mem.w8(p + 3, 4); g.mem.w8(p + 7, 0x64)


@port(0x80086B64)
def set_semi_trans(g, p, on, *_):
    v = g.mem.u8(p + 7); g.mem.w8(p + 7, v | 2 if on else v & 0xFD)


@port(0x80086B8C)
def set_shade_tex(g, p, on, *_):
    v = g.mem.u8(p + 7); g.mem.w8(p + 7, v | 1 if on else v & 0xFE)


def _link(m, prim, ot):
    m.w32(prim, (m.u32(prim) & 0xFF000000) | (m.u32(ot) & 0xFFFFFF))
    m.w32(ot, (m.u32(ot) & 0xFF000000) | (prim & 0xFFFFFF))


def _ui(addr, name, doc):
    def f(g, *args):
        hook = getattr(g, 'ui', None)
        if hook is not None and not hasattr(g, 'ram'): return hook(addr, *args)
        return 0
    f.__name__ = name; f.__doc__ = doc
    globals()[name] = port(addr, mock_always=True)(f)


for _a, _n, _d in (
        (0x80048780, 'draw_letter', 'One character into the line buffer at the pen, uploaded to its VRAM row.'),
        (0x800482A0, 'draw_text', 'A whole string into a VRAM text row and its sprites (the name plate).'),
        (0x80087764, 'clear_image', 'GPU ClearImage: a VRAM rectangle (a text row) to 0.'),
        (0x80083EE4, 'debug_text', 'Debug output.')):
    _ui(_a, _n, _d)

JP_GLYPHS = 'jp_glyphs'                 # the remake's hook name for JP 0x80051614 (no US address)


def jp_glyphs(g, data, vx, vy):
    """JP 0x80051614: a Shift-JIS string's glyphs (BIOS kanji ROM, 16 x 15, ink = index 1) into
    VRAM from (vx, vy) (halfwords), 16 px apart."""
    hook = getattr(g, 'ui', None)
    if hook is not None and not hasattr(g, 'ram'): hook(JP_GLYPHS, data, vx, vy)


@port(0x80049280)
def window_init(g, task):
    """A window's cell sprites (both buffers): sprite, opaque, unshaded, palette 0x80142B60."""
    m = g.mem; cfg = m.u32(m.u32(task) + 4)
    for b in range(2):
        prims = m.u32(cfg + 8 + 4 * b)
        for r in range(m.s16(cfg + 6)):
            for c in range(m.s16(cfg + 4)):
                p = prims + (r * m.s16(cfg + 4) + c) * 0x14
                set_sprt(g, p); set_semi_trans(g, p, 0); set_shade_tex(g, p, 1)
                m.w16(p + 0xE, m.u16(0x80142B60))


# ------------------------------------------------------------------ boot
@port(0x80045F00)
def msg_boot(g):
    """At boot: scroll 8 frames, scroll wait 10, close wait 360 frames; the font file loads
    (0x80083F04 - the remake has the font as a picture)."""
    m = g.mem
    m.w16(0x80106968, 4); m.w32(SLEN, 8); m.w32(SWAIT, 10)
    m.w32(0x8010695C, 0); m.w32(0x80106960, 0); m.w16(0x80106964, 0); m.w16(0x80106966, 0); m.w16(0x8010696A, 0)
    m.w32(CWAIT, 0xB4 if jp(g) else 0x168)
    calls.call(g, 0x80083F04, 0x80023F60, 0x801DDD10, 0, 0x8220)


_ui(0x80083F04, 'load_file', 'A file from the disc into RAM (the font at boot).')


# ------------------------------------------------------------------ opening / closing
@port(0x80045F8C, ret=True)
def msg_busy(g):
    return int(g.mem.s32(FLAGS) & 4 != 0)


@port(0x80045FA4)
def msg_gone(g, task):
    task_end(g, task); g.mem.w32(FLAGS, 0); g.mode_flags &= ~0x18


def _slide_setup(m, sl, frm, to):
    m.w32(sl + 8, 2); m.w32(sl, 0); m.w32(sl + 4, 0xF)
    m.w16(sl + 0xC, frm[0]); m.w16(sl + 0xE, frm[1]); m.w16(sl + 0x10, to[0]); m.w16(sl + 0x12, to[1])


@port(0x8004608C, ret=True)
def msg_open(g, text, mode):
    """The window opens (task 0) with this text: it slides up from the bottom over 15 frames,
    mode 1 sets mode flag 0x10 (Alundra waits), else 8 (the world stops); sound 6."""
    m = g.mem
    if not task_start(g, 0): return 0
    if strlen(g, text) >= 0x960:
        for i in range(0x1B): m.w8(TEXT + i, m.u8(0x80023F78 + i))
    else:
        _write_str(g, TEXT, _cstr(g, text))
    m.w32(SLIDE + 8, 2); m.w32(SLIDE, 0); m.w32(SLIDE + 4, 0xF)
    x = m.s16(CFG)
    m.w16(SLIDE + 0xC, x - m.s16(CFG + 4) * 8 if x < 0 else x)
    m.w16(SLIDE + 0xE, 0xF0)
    m.w16(SLIDE + 0x10, x - m.s16(CFG + 4) * 8 if x < 0 else x)
    y = m.s16(CFG + 2)
    m.w16(SLIDE + 0x12, y - m.s16(CFG + 6) * 8 if y < 0 else y)
    m.w32(FLAGS, 5)
    m.w16(SLIDE + 0x18, m.u16(CFG)); m.w16(SLIDE + 0x1A, m.u16(CFG + 2))
    g.mode_flags |= 0x10 if mode == 1 else 8
    # No game stop when a window opens (BizHawk 2026-10-23: the Fire Manor guardian's windows, no
    # name plate, play time runs on; the 2026-10-19 3-frame stop belongs to the name plate: name_open).
    for a in (0x8010754C, 0x80107558, 0x8010752C, 0x80107530, 0x80107464): m.w32(a, 0)
    m.w32(VOICE, -1)
    for a in (0x80107470, 0x80107474, 0x80107478, 0x8010747C): m.w32(a, 0)
    for r in range(3):
        m.w32(CENTRE + 4 * r, 0)
        for b in range(2):
            p = PRIMS + r * 0x28 + b * 0x14
            m.w16(p + 0x10, 0xFF); m.w16(p + 0x12, 0x10); m.w8(p + 0xC, 0); m.w8(p + 0xD, r * 0x10 + 0x20)
            set_sprt(g, p); set_semi_trans(g, p, 0); set_shade_tex(g, p, 1)
            m.w16(p + 0xE, m.u16(0x80142B70))
    for b in range(2):
        p = ARROWP + b * 0x14
        m.w16(p + 0x10, 0x10); m.w16(p + 0x12, 0x10)
        m.w8(p + 0xC, m.u8(0x800A7740)); m.w8(p + 0xD, m.u8(0x800A7741))
        set_sprt(g, p); set_semi_trans(g, p, 0); set_shade_tex(g, p, 1)
        m.w16(p + 8, 0); m.w16(p + 0xA, 0)
        m.w16(p + 0xE, m.u16(0x80142B70))
    m.w32(ARROW, 0); m.w32(ARROW_T, 0)
    calls.call(g, 0x80087764, calls.Buf(rect=(0x3C0, 0x140, 0x40, 0x20) if jp(g) else (0x3C0, 0x120, 0x40, 0x30)), 0, 0, 0)
    m.w32(INTERVAL, 4); m.w32(PMODE, 3); m.w32(CD, 1); m.w32(SMODE, 3); m.w32(CMODE, 3)
    memzero(g, LINEBUF, 0x800)
    m.w32(PEN, 0)
    core.play_sound(g, 6)
    return 1


@port(0x80042F74, ret=True)
def msg_start(g, n, mode):
    """Script text n (bit 7: the map's own texts *(0x801F3150), else the shared ones
    *(0x801F4050); a table of u16 offsets) in the window, unless one is already open."""
    m = g.mem
    if msg_busy(g): return 0
    tab = m.u32(SPEAKER_TEXT if n & 0x80 else GLOBAL_TEXT)
    s = (tab + m.u16(tab + 2 * (n & 0x7F))) & 0xFFFFFFFF
    calls.call(g, 0x80083F74, n, s)
    g._text_num = n                                    # (the remake's: which text, for message_tick)
    msg_open(g, s, mode)
    return 1


# ------------------------------------------------------------------ every frame
def _task_cfg(m, task):
    rec = m.u32(task)
    return rec, m.u32(rec + 4)


@port(0x80047EC0, ret=True)
def msg_frame(g, task):
    """Task 0's frame: the slide, else the end wait, else a scrolling step, else the text."""
    m = g.mem
    calls.call(g, 0x80088230, calls.STACK)
    b = m.s32(BUFI)
    calls.call(g, 0x800882D8, 0x801F39A8 + b * 0xC, calls.STACK)
    if m.s32(FLAGS) & 3:
        rec, cfg = _task_cfg(m, task)
        if slide(g, cfg, SLIDE) == 1:
            f = m.s32(FLAGS)
            if f & 1: m.w32(FLAGS, f & ~1)
            if m.s32(FLAGS) & 2:
                m.w16(CFG, m.u16(SLIDE + 0x18)); m.w16(CFG + 2, m.u16(SLIDE + 0x1A))
                msg_gone(g, task)
                return 0
    elif m.s32(ENDED):
        msg_end(g)
    elif m.s32(SCROLLING):
        msg_scroll(g, task)
        return 1
    else:
        msg_print(g)
    msg_draw(g, task)
    return 1


def _line_xy(m, rec, cfg, k):
    w = m.s32(CENTRE + 4 * k)
    if w: x = m.s16(cfg) + _half(m.s16(cfg + 4) * 8 - w)
    else: x = m.s16(cfg) + m.s16(rec + 8)
    return x, m.s16(rec + 0xA) + m.s16(cfg + 2) + 0x10 * k


def _place_lines(g, task, shift=0):
    m = g.mem; rec, cfg = _task_cfg(m, task); b = m.s32(BUFI)
    ot = 0x801F53A8 + b * 0x28
    if jp(g):                                           # 0x8004770C: 2 lines, no centring
        for k in range(2):
            p = PRIMS + b * 0x14 + ((m.s32(TOP) + k) & 1) * 0x28
            m.w16(p + 8, m.s16(cfg) + JP_REC[0]); m.w16(p + 0xA, m.s16(cfg + 2) + JP_REC[1] + 0x10 * k - shift)
            _link(m, p, ot)
        _link(m, 0x801F39A8 + b * 0xC, ot)
        return rec, cfg, b
    for k in range(3):
        p = PRIMS + b * 0x14 + _cmod(m.s32(TOP) + k, 3) * 0x28
        x, y = _line_xy(m, rec, cfg, k)
        m.w16(p + 8, x); m.w16(p + 0xA, y - shift)
        _link(m, p, ot)
    _link(m, 0x801F39A8 + b * 0xC, ot)
    return rec, cfg, b


@port(0x800465BC)
def msg_draw(g, task):
    """The three lines where they belong, and the blinking "more" marker while it waits."""
    m = g.mem
    rec, cfg, b = _place_lines(g, task)
    if m.s32(ARROW) and jp(g):                          # 41 frames, the last one blank (u / v 0, 0)
        t = m.s32(ARROW_T) + 1
        m.w32(ARROW_T, 0 if t >= 0x29 else t)
        f = _cdiv(m.s32(ARROW_T), 10)
        p = ARROWP + b * 0x14
        uv = (m.u8(0x800A7740 + f * 0x28), m.u8(0x800A7741 + f * 0x28)) if f < 4 else (0, 0)
        m.w8(p + 0xC, uv[0]); m.w8(p + 0xD, uv[1])
        m.w16(p + 8, m.s16(cfg) + m.s16(cfg + 4) * 4 - 8)
        m.w16(p + 0xA, m.s16(cfg + 2) + 0x10 * m.s32(LINE) + 0x18)
        _link(m, p, 0x801F53A0 + b * 0x28)
        s = getattr(g, 'sw_linked', None)
        if s is not None: s.add('arrow')
    elif m.s32(ARROW):
        t = m.s32(ARROW_T) + 1
        m.w32(ARROW_T, 0 if t >= 0x28 else t)
        f = _cdiv(m.s32(ARROW_T), 10) * 0x28
        p = ARROWP + b * 0x14
        m.w8(p + 0xC, m.u8(0x800A7740 + f)); m.w8(p + 0xD, m.u8(0x800A7741 + f))
        m.w16(p + 8, m.s16(cfg) + m.s16(cfg + 4) * 8 - 0x10)
        m.w16(p + 0xA, m.s16(cfg + 2) + m.s16(cfg + 6) * 8 - 0x18)
        _link(m, p, 0x801F53A0 + b * 0x28)
        s = getattr(g, 'sw_linked', None)
        if s is not None: s.add('arrow')                 # (the remake draws it only when placed)


@port(0x8004696C)
def msg_scroll(g, task):
    """One line up: it waits for its trigger (scroll mode), then 8 frames of 2 pixels."""
    m = g.mem
    if m.s32(ST) == m.s32(SLEN):
        go = 0
        sm = m.s32(SMODE)
        if sm & 8: go = 1; m.w32(SMODE, sm & ~8)
        if m.s32(SMODE) & 2 and g.pad_pressed & 0x80: go = 1
        if m.s32(SMODE) & 1:
            m.w32(SCD, m.s32(SCD) - 1)
            if m.s32(SCD) == 0: go = 1
        if m.s32(SMODE) & 4 and m.s32(SREQ) == 1: go = 1; m.w32(SREQ, 0)
        if go: m.w32(ST, m.s32(ST) - 1)
        else: m.w32(ARROW, 0)
    else:
        m.w32(ST, m.s32(ST) - 1)
    shift = _cdiv((m.s32(SLEN) - m.s32(ST)) * 0x10, m.s32(SLEN))
    _place_lines(g, task, shift)
    if m.s32(ST) == 0 and jp(g):                       # 0x80047A34: ring of 2
        top = (m.s32(TOP) + 1) & 1
        m.w32(SCROLLING, 0); m.w32(TOP, top)
        calls.call(g, 0x80087764, calls.Buf(rect=(0x3C0, 0x140 + 0x10 * (top ^ 1), 0x40, 0x10)), 0, 0, 0)
    elif m.s32(ST) == 0:
        top = _cmod(m.s32(TOP) + 1, 3)
        m.w32(SCROLLING, 0); m.w32(TOP, top)
        calls.call(g, 0x80087764, calls.Buf(rect=(0x3C0, _cmod(top + 2, 3) * 0x10 + 0x120, 0x40, 0x10)), 0, 0, 0)


@port(0x80046DF4)
def msg_end(g):
    """The text has ended: the window closes on its trigger (close mode) - sound 7, the name
    plate and the portrait go back, the window slides down over 15 frames."""
    m = g.mem
    go = 0
    cm = m.s32(CMODE)
    if cm & 2: go = int(g.pad_pressed & 0x80 != 0)
    if cm & 1:
        m.w32(CCD, m.s32(CCD) - 1)
        if m.s32(CCD) == 0: go = 1
    if m.s32(CMODE) & 4 and m.s32(CREQ) == 1: go = 1; m.w32(CREQ, 0)
    if go:
        m.w32(FLAGS, m.s32(FLAGS) | 2)
        core.play_sound(g, 7)
        name_close(g)
        calls.call(g, 0x800599A4)
        x = m.s16(CFG); y = m.s16(CFG + 2)
        nx = x - m.s16(CFG + 4) * 8 if x < 0 else x
        ny = y - m.s16(CFG + 6) * 8 if y < 0 else y
        m.w32(SLIDE + 8, 2); m.w32(SLIDE, 0); m.w32(SLIDE + 4, 0xF)
        m.w16(SLIDE + 0xC, nx); m.w16(SLIDE + 0xE, ny); m.w16(SLIDE + 0x10, nx); m.w16(SLIDE + 0x12, 0xF0)


def _newline(g):
    m = g.mem
    if jp(g):                                           # 0x80048BC4: two lines, then scroll
        m.w32(NCH, 0)
        if m.s32(LINE) == 1:
            m.w32(SCROLLING, 1); m.w32(ST, m.s32(SLEN))
            if m.s32(SMODE) & 1: m.w32(SCD, m.s32(SWAIT))
        else: m.w32(LINE, 1)
        return
    m.w32(NCH, 0); m.w32(PEN, 0)
    memzero(g, LINEBUF, 0x800)
    ln = m.s32(LINE)
    if ln == 2:
        m.w32(SCROLLING, 1); m.w32(ST, m.s32(SLEN))
        if m.s32(SMODE) & 1: m.w32(SCD, m.s32(SWAIT))
        m.w32(CENTRE + 8, 0)
        return
    m.w32(LINE, ln + 1 if ln + 1 != 3 else ln)
    m.w32(CENTRE + 4 * m.s32(LINE), 0)


def _put(g, c):
    """A character on the current line (0x80048780) and the pen moves on by its width + 1."""
    m = g.mem
    row = _cmod(m.s32(TOP) + m.s32(LINE), 3) * 0x10 + 0x120
    calls.call(g, 0x80048780, calls.Buf(bytes([c, 0])), LINEBUF, 0x3C0, row, m.s16(PEN), 0, 0x100, 0x10)
    m.w32(PEN, m.s32(PEN) + gap(g) + _width(g, c))


def _digit(g, d):
    if jp(g): return JP_DIGITS[d]
    return _cstr(g, g.mem.u32(DIGITS + 4 * d))


def _splice(g, at, insert):
    """TEXT[:at] + insert + TEXT[at:] (strncpy / strcat / strcpy through a stack buffer)."""
    head = g.mem.bytes(TEXT, at).split(b'\0')[0] if at else b''
    if len(head) < at: head = head                      # a NUL inside: strcat stops there
    tail = _cstr(g, TEXT + at)
    _write_str(g, TEXT, head + insert + tail)


@port(0x8004FE5C, ret=True)
def falcons_total(g): return g.mem.s16(g.mem.u32(0x80119AE8) + 0x10)


@port(0x8004FE74, ret=True)
def falcons_new(g): return g.mem.s16(g.mem.u32(0x80119AE8) + 0xE)


@port(0x8004FE04)
def falcons_count_in(g):
    """The falcons found since the last visit are added to the total (at most 50)."""
    m = g.mem; st = m.u32(0x80119AE8)
    m.w16(st + 0x10, m.u16(st + 0x10) + m.u16(st + 0xE)); m.w16(st + 0xE, 0)
    if m.s16(st + 0x10) >= 0x33: m.w16(st + 0x10, 0x32)
    m.w32(0x801DD3E8, m.u32(0x801DD3E8) & ~0x400)


@port(0x80048450)
def falcon_reward(g):
    """Which reward the falcon total has reached (0x801DD3E4 bits -> 0x80107564 and the
    0x801DD3E8 flags; 0x800 when the total reaches the next reward's count)."""
    m = g.mem
    a = m.s32(0x801DD3E4)
    v = m.u32(0x801DD3E8) & ~(2 | 4 | 8 | 0x10 | 0x20 | 0x40 | 0x80 | 0x100) & 0xFFFFFFFF
    m.w32(0x801DD3E8, v)
    for bit, f, k in ((None, 0x100, 7), (0x40000000, 0x80, 6), (0x20000000, 0x40, 5), (0x10000000, 0x20, 4),
                      (0x08000000, 0x10, 3), (0x04000000, 8, 2), (0x02000000, 4, 1)):
        if (a < 0) if bit is None else (a & bit):
            m.w32(0x801DD3E8, v | f); m.w32(FALK, k); break
    else:
        m.w32(0x801DD3E8, v | 2); m.w32(FALK, 0)
    need = m.s32(0x8009C69C + 4 * m.s32(FALK))
    if falcons_total(g) >= need: m.w32(0x801DD3E8, m.u32(0x801DD3E8) | 0x800)
    else: m.w32(0x801DD3E8, m.u32(0x801DD3E8) & ~0x800)


def _num2(g, v, always_tens=False):
    out = b''
    if _cdiv(v, 10) != 0 or always_tens: out += _digit(g, _cdiv(v, 10))
    return out + _digit(g, _cmod(v, 10))


@port(0x80046FB4)
def msg_print(g):
    """The text moves on by one character when the print mode allows (Square held: every frame;
    else every 4 frames).  Codes: \\N new line, \\A wait for Square then a new line, \\T a
    pause, \\H centre the line, \\B-\\G talk sound, \\W special letter, \\V number variable,
    \\X falcon numbers, \\MCE script-driven printing, \\<digits> sets that map flag."""
    m = g.mem
    if jp(g): return _msg_print_jp(g)
    pm = m.s32(PMODE)
    if pm & 8:
        if g.pad_pressed & 0x80:
            m.w32(ARROW, 0); m.w32(PMODE, pm & ~8); m.w32(SMODE, m.s32(SMODE) | 8)
            _newline(g)
        return
    go = 0
    if pm & 2:
        m.w32(CD, m.s32(CD) - 1)
        if m.s32(CD) == 0: go = 1; m.w32(CD, m.s32(INTERVAL))
    if m.s32(PMODE) & 1 and g.pad_held & 0x80: go = 1
    if m.s32(PMODE) & 4 and m.s32(PREQ) == 1: go = 1; m.w32(PREQ, 0)
    if not go: return
    while True:
        p = m.s32(POS); c = m.u8(TEXT + p)
        if c == 0:
            m.w32(ENDED, 1)
            if m.s32(CMODE) & 1: m.w32(CCD, m.s32(CWAIT))
            return
        if c == 0x0A:
            m.w32(POS, p + 1); continue
        if c == 0x5C:
            m.w32(POS, p + 1); p += 1
            d = m.u8(TEXT + p)
            if d == 0x57:                                    # \W: a special letter
                p += 1; x = m.u8(TEXT + p)
                ch = (x - 0x20 if x < 0x41 else x + 0xD9) & 0xFF
                m.w32(POS, p + 1)
                _put(g, ch)
                return
            if d == 0x59:
                m.w32(POS, p + 1); return
            if d == 0x56:                                    # \Vn: number variable n
                n = m.u8(TEXT + p + 1) - 0x30
                p += 2; m.w32(POS, p)
                v = m.s32(0x801D7F00 + 4 * n)
                if v == 0: s = _digit(g, 0)
                else:
                    s = b''
                    while v != 0:
                        s = _digit(g, _cmod(v, 10)) + s; v = _cdiv(v, 10)
                _splice(g, p, s)
                continue
            if d == 0x58:                                    # \Xn: falcons
                p += 1; m.w32(POS, p); e = m.u8(TEXT + p)
                if e == 0x30:
                    p += 1; m.w32(POS, p)
                    _splice(g, p, _num2(g, falcons_new(g)))
                    falcons_count_in(g); falcon_reward(g)
                elif e == 0x31:
                    p += 1; m.w32(POS, p)
                    falcons_count_in(g); falcon_reward(g)
                    _splice(g, p, _num2(g, falcons_total(g)))
                elif e in (0x32, 0x34):
                    p += 1; m.w32(POS, p)
                    if jp(g): _splice(g, p, JP_REWARDS[m.s32(FALK) & 7].encode('shift_jis'))
                    else: _splice(g, p, _cstr(g, m.u32(m.u32(0x8009C67C + 4 * m.s32(FALK)))))
                    falcons_count_in(g); falcon_reward(g)
                elif e == 0x33:
                    p += 1; m.w32(POS, p)
                    falcons_count_in(g); falcon_reward(g)
                    _splice(g, p, _num2(g, m.s32(0x8009C69C + 4 * m.s32(FALK)), True))
                elif e == 0x35:
                    p += 1; m.w32(POS, p)
                    falcons_count_in(g); falcon_reward(g)
                    diff = m.s32(0x8009C69C + 4 * m.s32(FALK)) - falcons_total(g)
                    s = (_digit(g, _cdiv(diff, 10)) if diff >= 10 else b'') + _digit(g, _cmod(diff, 10))
                    _splice(g, p, s)
                continue
            if d == 0x54:                                    # \T: a pause (two letters' time)
                m.w32(POS, p + 1); m.w32(CD, m.s32(INTERVAL) * 2); return
            if d == 0x48:                                    # \H: centre this line
                m.w32(POS, p + 1)
                m.w32(CENTRE + 4 * m.s32(LINE), text_width(g, TEXT + p + 1))
                continue
            if d == 0x4E:                                    # \N
                m.w32(POS, p + 1); _newline(g); return
            if d == 0x41:                                    # \A: wait for Square
                m.w32(ARROW, 1); m.w32(PMODE, m.s32(PMODE) | 8); m.w32(POS, p + 1); return
            if d in (0x42, 0x43, 0x44, 0x45, 0x46, 0x47):    # \B..\G: talk sound
                m.w32(VOICE, d - 0x43); m.w32(POS, p + 1); continue
            if d == 0x4D:                                    # \MCE: printing by script request
                m.w32(POS, p + 1)
                if m.u8(TEXT + p + 1) == 0x43:
                    m.w32(POS, p + 2)
                    if m.u8(TEXT + p + 2) == 0x45:
                        m.w32(POS, p + 3); m.w32(PMODE, 4)
                continue
            if 0x30 <= d <= 0x39:                            # \<digits>: map flag on
                digits = b''
                while 0x30 <= m.u8(TEXT + m.s32(POS)) <= 0x39:
                    digits += bytes([m.u8(TEXT + m.s32(POS))]); m.w32(POS, m.s32(POS) + 1)
                buf = bytearray(digits)
                if len(buf) - 1 > 0:
                    i = 0
                    while i < len(buf) and buf[i] == 0x30: buf[i] = 0x20; i += 1
                n = (strtol(g, calls.Buf(bytes(buf))) | 0x8000) & 0xFFFFFFFF
                a = 0x801E6378 + ((n >> 3) & 0xFFC)
                m.w32(a, m.u32(a) | 1 << (n & 31))
                sf = getattr(g, 'set_flag', None)
                if sf is not None and not hasattr(g, 'ram'): sf(n & 0xFFFF, True)
                continue
            p = m.s32(POS)                                   # any other code: its letter is printed
        # an ordinary character
        if is_two_byte(g, TEXT + p):
            calls.call(g, 0x80083EE4, 0x80023F94); calls.call(g, 0x80083EE4, TEXT + p); calls.call(g, 0x80083EE4, 0x80023FA4)
            ch = 0x3F; m.w32(POS, p + 2)
        else:
            ch = m.u8(TEXT + p); m.w32(POS, p + 1)
        _put(g, ch)
        if not m.s32(NCH) & 1:
            v = m.s32(VOICE)
            gate = getattr(g, 'talk_gate', None)            # remake: Mods text speed keeps the voice's pace
            if v != 4 and v >= 0 and (gate is None or gate(v)): core.play_sound(g, v + 0x4F)
        m.w32(NCH, m.s32(NCH) + 1)
        return


def _msg_print_jp(g):
    """msg_print as the JP ALUN_CD.EXE has it (0x80047F70): the same gate and codes as the US
    one, except that every character is one 2-byte Shift-JIS glyph (16 px, at line pixel
    16 * NCH: 0x80051614 into VRAM (0x3C0 + 4 * NCH, 0x140 + 16 * ((TOP + LINE) & 1))), and an
    unknown code (\\H, \\W, ...) prints the code letter and the byte after it as one glyph."""
    m = g.mem
    pm = m.s32(PMODE)
    if pm & 8:
        if g.pad_pressed & 0x80:
            m.w32(ARROW, 0); m.w32(PMODE, pm & ~8); m.w32(SMODE, m.s32(SMODE) | 8)
            _newline(g)
        return
    go = 0
    if pm & 2:
        m.w32(CD, m.s32(CD) - 1)
        if m.s32(CD) == 0: go = 1; m.w32(CD, m.s32(INTERVAL))
    if m.s32(PMODE) & 1 and g.pad_held & 0x80: go = 1
    if m.s32(PMODE) & 4 and m.s32(PREQ) == 1: go = 1; m.w32(PREQ, 0)
    if not go: return
    while True:
        p = m.s32(POS); c = m.u8(TEXT + p)
        if c == 0:
            m.w32(ENDED, 1)
            if m.s32(CMODE) & 1: m.w32(CCD, m.s32(CWAIT))
            return
        if c == 0x0A:
            m.w32(POS, p + 1); continue
        if c == 0x5C:
            m.w32(POS, p + 1); p += 1
            d = m.u8(TEXT + p)
            if d == 0x59:
                m.w32(POS, p + 1); return
            if d == 0x56:                                    # \Vn
                n = m.u8(TEXT + p + 1) - 0x30
                p += 2; m.w32(POS, p)
                v = m.s32(0x801D7F00 + 4 * n)
                if v == 0: s = _digit(g, 0)
                else:
                    s = b''
                    while v != 0:
                        s = _digit(g, _cmod(v, 10)) + s; v = _cdiv(v, 10)
                _splice(g, p, s)
                continue
            if d == 0x58:                                    # \Xn
                p += 1; m.w32(POS, p); e = m.u8(TEXT + p)
                if not 0x30 <= e <= 0x35: continue
                p += 1; m.w32(POS, p)
                if e == 0x30:
                    _splice(g, p, _num2(g, falcons_new(g)))
                    falcons_count_in(g); falcon_reward(g)
                elif e == 0x31:
                    falcons_count_in(g); falcon_reward(g)
                    _splice(g, p, _num2(g, falcons_total(g)))
                elif e in (0x32, 0x34):
                    _splice(g, p, JP_REWARDS[m.s32(FALK) & 7].encode('shift_jis'))
                    falcons_count_in(g); falcon_reward(g)
                elif e == 0x33:
                    falcons_count_in(g); falcon_reward(g)
                    _splice(g, p, _num2(g, m.s32(0x8009C69C + 4 * m.s32(FALK)), True))
                else:
                    falcons_count_in(g); falcon_reward(g)
                    diff = m.s32(0x8009C69C + 4 * m.s32(FALK)) - falcons_total(g)
                    _splice(g, p, (_digit(g, _cdiv(diff, 10)) if diff >= 10 else b'') + _digit(g, _cmod(diff, 10)))
                continue
            if d == 0x54:
                m.w32(POS, p + 1); m.w32(CD, m.s32(INTERVAL) * 2); return
            if d == 0x4E:
                m.w32(POS, p + 1); _newline(g); return
            if d == 0x41:
                m.w32(ARROW, 1); m.w32(PMODE, m.s32(PMODE) | 8); m.w32(POS, p + 1); return
            if d in (0x42, 0x43, 0x44, 0x45, 0x46, 0x47):
                m.w32(VOICE, d - 0x43); m.w32(POS, p + 1); continue
            if d == 0x4D:
                m.w32(POS, p + 1)
                if m.u8(TEXT + p + 1) == 0x43:
                    m.w32(POS, p + 2)
                    if m.u8(TEXT + p + 2) == 0x45:
                        m.w32(POS, p + 3); m.w32(PMODE, 4)
                continue
            if 0x30 <= d <= 0x39:
                digits = b''
                while 0x30 <= m.u8(TEXT + m.s32(POS)) <= 0x39:
                    digits += bytes([m.u8(TEXT + m.s32(POS))]); m.w32(POS, m.s32(POS) + 1)
                buf = bytearray(digits)
                if len(buf) - 1 > 0:
                    i = 0
                    while i < len(buf) and buf[i] == 0x30: buf[i] = 0x20; i += 1
                n = (strtol(g, calls.Buf(bytes(buf))) | 0x8000) & 0xFFFFFFFF
                a = 0x801E6378 + ((n >> 3) & 0xFFC)
                m.w32(a, m.u32(a) | 1 << (n & 31))
                sf = getattr(g, 'set_flag', None)
                if sf is not None and not hasattr(g, 'ram'): sf(n & 0xFFFF, True)
                continue
            p = m.s32(POS)                                   # any other code: (it, next byte) as a glyph
        pair = bytes([m.u8(TEXT + p), m.u8(TEXT + p + 1)])
        m.w32(POS, p + 2)
        nch = m.s32(NCH)
        jp_glyphs(g, pair, 0x3C0 + 4 * nch, 0x140 + 0x10 * ((m.s32(TOP) + m.s32(LINE)) & 1))
        if not nch & 1:
            v = m.s32(VOICE)
            gate = getattr(g, 'talk_gate', None)
            if v != 4 and v >= 0 and (gate is None or gate(v)): core.play_sound(g, v + 0x4F)
        m.w32(NCH, nch + 1)
        return


@port(0x8004864C, ret=True)
def text_width(g, a):
    """Pixels of the text from a up to \\N or its end (each letter width + 1; codes skipped)."""
    m = g.mem; w = 0
    c = m.u8(a)
    if c == 0: return 0
    while True:
        if c != 0x5C:
            w += _width(g, c) + gap(g); a += 1
        else:
            a += 1; d = m.u8(a)
            k = d - 0x30
            if 0 <= k < 0x2A:
                if 0 <= k <= 9:
                    if 0x30 <= m.u8(a) <= 0x39:
                        a += 1
                        while True:
                            dd = m.u8(a); a += 1
                            if not 0x30 <= dd <= 0x39: break
                        a -= 1
                elif d == 0x57:
                    a += 1; x = m.u8(a)
                    x = x - 0x20 if x < 0x41 else x - 0x27
                    a += 1
                    w += _width(g, x) + gap(g)
                elif d == 0x58: a += 2
                elif d in (0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x54, 0x59): a += 1
                elif d == 0x4E: return w
        c = m.u8(a)
        if c == 0: return w


# ------------------------------------------------------------------ the speaker's name plate
@port(0x8005C0A8)
def name_open(g, who):
    """Task 12: the name of sprite `who` (0x100-0x1FF, table 0x800C5E74) over the window."""
    m = g.mem
    if m.u16(NAME_FLAGS) & 4: return
    if not ((who - 0x100) & 0xFFFFFFFF) < 0x100: return
    p = m.u32(NAMES + 4 * who)
    if p == 0 or m.u8(p) == 0: return
    m.w32(NAME_WHO, who)
    task_start(g, 0xC)
    # The game frame that puts up a speaker's name plate lasts 4 vsyncs in the original: its play
    # time stops 3 frames before the window shows (BizHawk 2026-10-23, Jess's wake-up texts; the
    # Fire Manor guardian's texts have no name plate and no stop).
    from settings_screen import load_pause
    g.ui_stall = load_pause(getattr(g, 'settings', {}), 3)


@port(0x8005C3DC, ret=True)
def name_init(g, task):
    m = g.mem; rec, cfg = _task_cfg(m, task)
    m.w32(NAME_SLIDE + 8, 2); m.w32(NAME_SLIDE + 4, 0xF); m.w32(NAME_SLIDE, 0)
    m.w16(NAME_SLIDE + 0xC, 0x140)
    m.w16(NAME_SLIDE + 0xE, _norm(m, cfg, 1))
    m.w16(NAME_SLIDE + 0x10, _norm(m, cfg, 0))
    m.w16(NAME_SLIDE + 0x12, _norm(m, cfg, 1))
    m.w16(NAME_SLIDE + 0x18, m.u16(cfg))
    m.w16(NAME_FLAGS, 5)
    m.w16(NAME_SLIDE + 0x1A, m.u16(cfg + 2))
    if jp(g):                                           # 0x80049048: 6 glyphs at (cfg.x + 16, cfg.y + 8)
        calls.call(g, 0x800482A0, NAME_PRIMS, m.u32(NAMES + 4 * m.s32(NAME_WHO)), 6, m.s16(cfg) + 0x10,
                   m.s16(cfg + 2) + 8, 2)
    else:
        calls.call(g, 0x800482A0, NAME_PRIMS, m.u32(NAMES + 4 * m.s32(NAME_WHO)), 6, 0,
                   m.s16(rec + 0xA) + m.s16(cfg + 2), 3)
    return 1


@port(0x8005C3B4)
def name_gone(g, task):
    task_end(g, task); g.mem.w16(NAME_FLAGS, 0)


@port(0x8005C118)
def name_close(g):
    m = g.mem
    if m.u16(NAME_FLAGS) & 4: m.w16(NAME_FLAGS, 6)
    m.w32(NAME_SLIDE + 8, 2); m.w32(NAME_SLIDE, 0); m.w32(NAME_SLIDE + 4, 0xF)
    m.w16(NAME_SLIDE + 0xC, _norm(m, NAME_CFG, 0)); m.w16(NAME_SLIDE + 0xE, _norm(m, NAME_CFG, 1))
    m.w16(NAME_SLIDE + 0x10, 0x140); m.w16(NAME_SLIDE + 0x12, _norm(m, NAME_CFG, 1))


@port(0x8005C588, ret=True)
def name_frame(g, task):
    m = g.mem; rec, cfg = _task_cfg(m, task)
    if m.u16(NAME_FLAGS) & 3 and slide(g, cfg, NAME_SLIDE) == 1:
        f = m.u16(NAME_FLAGS)
        if f & 1: m.w16(NAME_FLAGS, f & 0xFFFE)
        if m.u16(NAME_FLAGS) & 2:
            m.w16(cfg, m.u16(NAME_SLIDE + 0x18)); m.w16(cfg + 2, m.u16(NAME_SLIDE + 0x1A))
            name_gone(g, task)
            return 0
    b = m.s32(BUFI)
    p = NAME_PRIMS + b * 0x14
    if jp(g):                                           # 0x8005D6F0: left-aligned
        m.w16(p + 8, m.s16(cfg) + 0x10); m.w16(p + 0xA, m.s16(cfg + 2) + 8)
    else:
        w = text_width(g, m.u32(NAMES + 4 * m.s32(NAME_WHO)))
        m.w16(p + 8, m.s16(cfg) + _half(m.s16(cfg + 4) * 8 - w))
        m.w16(p + 0xA, m.s16(rec + 0xA) + m.s16(cfg + 2))
    _link(m, p, 0x801F53B8 + b * 0x28)
    calls.call(g, 0x80088230, calls.STACK)
    calls.call(g, 0x800882D8, 0x801F2DF8 + b * 0xC, calls.STACK)
    _link(m, 0x801F2DF8 + b * 0xC, 0x801F53B8 + b * 0x28)
    return 1


# ------------------------------------------------------------------ script controls (ops 4C-51)
@port(0x80046044)
def set_print_mode(g, v): g.mem.w32(PMODE, v)


@port(0x8004601C)
def print_request(g):
    if g.mem.s32(PMODE) & 4: g.mem.w32(PREQ, 1)


@port(0x8004607C)
def set_scroll_mode(g, v): g.mem.w32(SMODE, v)


@port(0x80046054)
def scroll_request(g):
    if g.mem.s32(SMODE) & 4: g.mem.w32(SREQ, 1)


@port(0x8004600C)
def set_close_mode(g, v): g.mem.w32(CMODE, v)


@port(0x80045FE4)
def close_request(g):
    if g.mem.s32(CMODE) & 4: g.mem.w32(CREQ, 1)
