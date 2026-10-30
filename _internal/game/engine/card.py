"""Saving: the save point's menu (0x80031AC4) and the memory card manager, ported from the US
ALUN_CD.EXE.  Everything lives where the game keeps it (g.mem); the BIOS card services are
engine/bios_card.py (g.card_bios).

The save point (C72, engine/ai_g6.py) calls 0x80031AC4: the respawn point is noted
(0x801DD2DC..E8 = map, x, y, z of the last arrival), the block's title lines are written
(0x800314F8: the chapter name, then "  HP nn       TIME hh:mm:ss   "), and 0x80060E14 hands the
manager the block 0x801DD2D8 (0x758 bytes) in mode 1.  Every frame 0x8002BEAC runs 0x80060E6C,
which runs 0x8006167C while a state is set:

  0x800C67E8  state          0x800C67E0  frame counter     0x800C67E4  busy (a request is taken)
  0x800C67EC  the message window's answer (0 open, -1 gone, 0x3E8 none was opened)
  0x800C67F0  the YES / NO answer (1 / 2)     0x800C67F4  step within a state
  0x800C67F8  the list window's answer (-1 choosing, -2 cancelled, else the entry)
  0x800C67B0  -> the file name "BASLUS-00553ALUNDRA "     0x800C67B4  the card (0 = slot 1)
  0x801B6C50 / 54  _card_info result per card (0 IOE, 1 ERROR, 2 TIMEOUT, 3 NEW)
  0x801B6BF8 / FC  _card_load result per card      0x801B6C58  files in the directory
  0x80122418  directory entries (0x28 each)        0x80122390  list entries (two text pointers)
  0x80122698  the file (0x2000 bytes): 'SC' 0x13 1, title, palette +0x60, icon +0x80..+0x200,
              4 records of 0x76C at +0x200 (the block, its index at +4), 0x24 random bytes,
              the maker's string, CRC-32 (0x04C11DB7) of the first 0x1FFC bytes at +0x1FFC

The states (each waits 20 frames on a message unless said otherwise):
  0x2710 "Examining the parchment..." (busy, mode flag 8) -> 0x2711 -> 1: card 1 there (IOE or
  NEW) -> 0x3EC -> 4; else 0x3EA -> 2: card 2 there -> 0x3FA (slot 2 message) else 0x3EB -> 3 ->
  0x3F9 (no card).  4: loaded -> 0x3F0 -> 8, unformatted -> 0x3ED -> 5: "The book pages are not
  conditioned yet. / Shall I take care of this task now?" YES / NO (NO first) -> 0x69: YES ->
  0x3EE ("Condition (erase) the book...", 29 + 20 frames) -> 6: format -> 0x3F3 / 0x3FC; NO ->
  0x3EF (Square) -> 7: "The tale cannot be saved. Is this understood?" -> 0x6B: YES -> 0x3F5,
  NO -> 0x3ED again.  8: the file is there -> 0x3F4, else 0x3F1 -> 9: room for one block (14 or
  fewer used) -> 0x3FF ("Reserving one volume...") -> 0x17 -> 0x3F3 -> 0xB: create -> 0x3F4 /
  0x3FD; full -> "Not enough parchment" 0x3F2 (any of Square / Cross / Circle / Triangle) -> 0xA:
  the files listed ("What tale shall be forgotten?") -> 0x3F7 -> 0xF: erased -> 0x3FF.
  0x3F4: the file read -> 0xC: its 4 records listed ("Where shall we record this tale?") ->
  0x3F8: "Inscribing the tale..." -> 0x10: written -> 0x3FE -> 0x16 "Tale successfully
  inscribed." -> 0x3F5 (Square) -> 0xD -> 0x3F6 -> 0xE (the HUD back) -> 0x44B (12 frames) ->
  0x63: done.  The list's NO / cancel (-2) goes straight to 0x3F6.  Errors: 0x3F9 / 0x11 "Please
  insert a book (card) in Slot 1 and try again.", 0x3FA / 0x12 "... in Slot 1.", 0x3FB / 0x13
  "The book has been changed.", 0x3FC / 0x14 "The parchment could not be conditioned.", 0x3FD /
  0x15 "The inscription was not legible.", all -> 0x3F5.
Mode 3 (0x80060F04) and the second manager 0x800610AC are never reached in the US game."""
from .registry import port
from . import calls
from .core import s32

E0, E4, E8, EC, F0, F4, F8 = 0x800C67E0, 0x800C67E4, 0x800C67E8, 0x800C67EC, 0x800C67F0, 0x800C67F4, 0x800C67F8
NAME_PTR, CARD = 0x800C67B0, 0x800C67B4
ST, ST2, NDIR, DIR, LIST, LTEXT = 0x801B6C50, 0x801B6BF8, 0x801B6C58, 0x80122418, 0x80122390, 0x80122410
FILE = 0x80122698
MODE, DATA_PTR, DATA_SIZE = 0x801F3A0C, 0x801D93E8, 0x80152BDC
PAD_PRESSED = 0x801DDA4A
SW_EV = (0x801DD2CC, 0x801DD2D0, 0x801DD2D4, 0x801DDA30)
HW_EV = (0x801E6350, 0x801E6354, 0x801E6358, 0x801E635C)
RAND_SEED = 0x80124908


def _bios(g):
    b = getattr(g, 'card_bios', None)
    if b is None:
        from .bios_card import Bios
        b = g.card_bios = Bios()
    return b


# ------------------------------------------------------------------ BIOS stubs (A0 / B0 calls)
@port(0x8008423C, ret=True)
def test_event(g, h): return _bios(g).test_event(g.mem, h & 0xFFFFFFFF)
@port(0x8008428C, ret=True)
def bios_open(g, name, mode): return _bios(g).open(g.mem, name, mode)
@port(0x8008429C, ret=True)
def bios_read(g, fd, buf, n): return _bios(g).read(g.mem, fd, buf, n)
@port(0x800842AC, ret=True)
def bios_write(g, fd, buf, n): return _bios(g).write(g.mem, fd, buf, n)
@port(0x800842BC, ret=True)
def bios_close(g, fd): return _bios(g).close(g.mem, fd)
@port(0x800842CC, ret=True)
def bios_format(g, dev): return _bios(g).format(g.mem, dev)
@port(0x800842DC, ret=True)
def bios_firstfile(g, pat, d): return _bios(g).firstfile(g.mem, pat, d)
@port(0x800842EC, ret=True)
def bios_nextfile(g, d): return _bios(g).nextfile(g.mem, d)
@port(0x800842FC, ret=True)
def bios_erase(g, name): return _bios(g).erase(g.mem, name)
@port(0x80085AE4, ret=True)
def card_write(g, chan, sector, buf): return _bios(g).card_write(g.mem, chan, sector, buf)
@port(0x80085A8C, ret=True)
def card_read(g, chan, sector, buf): return _bios(g).card_read(g.mem, chan, sector, buf)
@port(0x80085A9C)
def new_card(g): _bios(g).new_card(g.mem)
@port(0x80085A2C, ret=True)
def card_info(g, chan): return _bios(g).card_info(g.mem, chan)
@port(0x80085A3C, ret=True)
def card_load(g, chan): return _bios(g).card_load(g.mem, chan)


@port(0x80085AAC)
def card_clear_new(g, chan):
    """_new_card, then a write of sector 0x3F (the card's "new" flag goes)."""
    calls.call(g, 0x80085A9C)
    calls.call(g, 0x80085AE4, chan, 0x3F, 0)


# ------------------------------------------------------------------ the C library
@port(0x80084790, ret=True)
def strcmp(g, a, b):
    if a == 0 or b == 0:
        return 0 if a == b else (1 if a else -1)
    m = g.mem
    while True:
        x = m.u8(a); y = m.u8(b)
        if x != y: return x - y
        if x == 0: return 0
        a += 1; b += 1


@port(0x80084674, ret=True)
def memcpy(g, d, s, n):
    if d == 0: return 0
    m = g.mem
    n = max(n, 0)
    if n and isinstance(getattr(m, 'b', None), bytearray) and not s < d < s + n:   # (forward copy = a slice)
        src = m.bytes(s, n); o = m._chk(d, n); m.b[o:o + n] = src
        return d
    for i in range(n): m.w8(d + i, m.u8(s + i))
    return d


@port(0x800846A8, ret=True)
def rand(g):
    v = (g.mem.u32(RAND_SEED) * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
    g.mem.w32(RAND_SEED, v)
    return (v >> 16) & 0x7FFF


# ------------------------------------------------------------------ events
def _wait(g, table):
    """0x80060C5C (software) / 0x80060CE0 (hardware): the index of the first event delivered."""
    while True:
        for i, a in enumerate(table):
            if calls.call(g, 0x8008423C, g.mem.u32(a)) == 1: return i


@port(0x80060C5C, ret=True)
def wait_sw(g): return _wait(g, SW_EV)


@port(0x80060CE0, ret=True)
def wait_hw(g): return _wait(g, HW_EV)


@port(0x80060D64)
def clear_sw(g):
    for a in SW_EV: calls.call(g, 0x8008423C, g.mem.u32(a))


@port(0x80060DBC)
def clear_hw(g):
    for a in HW_EV: calls.call(g, 0x8008423C, g.mem.u32(a))


# ------------------------------------------------------------------ card helpers
@port(0x8005FE3C)
def card_check(g, card, st, st2):
    """_card_info (st = the event: 0 ready, 3 a new card: its flag is cleared), then _card_load
    (st2: 0 = a formatted card)."""
    chan = card << 4
    calls.call(g, 0x80085A2C, chan)
    v = calls.call(g, 0x80060C5C)
    g.mem.w32(st, v)
    calls.call(g, 0x80060D64)
    if g.mem.s32(st) == 3: calls.call(g, 0x800609D4, card)
    calls.call(g, 0x80085A3C, chan)
    v = calls.call(g, 0x80060C5C)
    g.mem.w32(st2, v)
    calls.call(g, 0x80060D64)


@port(0x800609D4)
def card_clear_flag(g, card):
    calls.call(g, 0x80060DBC)
    calls.call(g, 0x80085AAC, card << 4)
    calls.call(g, 0x80060CE0)


def _path(g, buf, card, name, n=0x15):
    """"bu00:" / "bu10:" and n bytes of the name at buf (other cards: the prefix is not set)."""
    m = g.mem
    if card in (0, 1):
        for i, c in enumerate(b'bu' + (b'0' if card == 0 else b'1') + b'0:'): m.w8(buf + i, c)
    for i in range(n): m.w8(buf + 5 + i, m.u8(name + i))
    return buf


SCRATCH = 0x801FFE00          # where the ports keep the routines' stack buffers (the game: its stack)


@port(0x8005FECC)
def card_dir(g, card, d, count):
    """The directory of a card into d (0x28 per entry), the count into *count."""
    m = g.mem; pat = SCRATCH; pre = SCRATCH + 0x80
    if card in (0, 1):
        for i, c in enumerate(b'bu' + (b'0' if card == 0 else b'1') + b'0:\0'): m.w8(pre + i, c)
    calls.call(g, 0x800847F4, pat, pre)
    calls.call(g, 0x800846E8, pat, 0x80026B24)
    m.w32(count, 0)
    if calls.call(g, 0x800842DC, pat, d) != d: return
    e = d + 0x28
    while True:
        m.w32(count, m.s32(count) + 1)
        if calls.call(g, 0x800842EC, e) != e: return
        e += 0x28


def _file_io(g, card, name, buf, fn):
    p = _path(g, SCRATCH, card, name)
    fd = calls.call(g, 0x8008428C, p, 3)
    if fd == -1: return -1
    r = calls.call(g, fn, fd, buf, 0x2000)
    calls.call(g, 0x800842BC, fd)
    return r if r != -1 else -1


@port(0x8005FFA8, ret=True)
def file_read(g, card, name, buf): return _file_io(g, card, name, buf, 0x8008429C)


@port(0x800600A8, ret=True)
def file_write(g, card, name, buf): return _file_io(g, card, name, buf, 0x800842AC)


@port(0x800601A8, ret=True)
def card_format(g, card):
    if card == 0: calls.call(g, 0x800842CC, 0x80026B28)
    elif card == 1: calls.call(g, 0x800842CC, 0x80026B30)
    return calls.call(g, 0x8006020C, card)


@port(0x8006020C, ret=True)
def card_is_formatted(g, card):
    """Sector 0 read: 1 when it starts "MC" (-1: the read failed)."""
    buf = SCRATCH + 0x100
    calls.call(g, 0x800845E8, buf, 0x80)
    calls.call(g, 0x80060DBC)
    calls.call(g, 0x80085A9C)
    calls.call(g, 0x80085A8C, card, 0, buf)
    if calls.call(g, 0x80060CE0) != 0: return -1
    return 1 if g.mem.u8(buf) == 0x4D and g.mem.u8(buf + 1) == 0x43 else 0


@port(0x80060294, ret=True)
def file_create(g, card, name):
    p = _path(g, SCRATCH, card, name)
    fd = calls.call(g, 0x8008428C, p, 0x10200)
    if fd == -1: return -1
    calls.call(g, 0x800842BC, fd)
    return 1


@port(0x80060354)
def file_erase(g, card, name):
    calls.call(g, 0x800842FC, _path(g, SCRATCH, card, name))


def _in_double(g, s, n):
    """0x800603F0 (inlined in 0x80060604): the kind of the byte at n - 1 of string s: 0 a single
    byte, 1 the first of a Shift-JIS pair, 2 its second."""
    if n <= 0 or calls.call(g, 0x80084838, s) < n: return 0
    k = 0; m = g.mem
    for a in range(s, s + n):
        if k == 1:
            c = m.u8(a); k = 0
            if (c - 0x40) & 0xFF < 0xBD: k = 2 if c != 0x7F else 0
        else:
            if k == 2: k = 0
            c = m.u8(a)
            if (c + 0x7F) & 0xFF < 0x1F or (c + 0x20) & 0xFF < 0x1D: k = 1
    return k


@port(0x800603F0, ret=True)
def sjis_kind(g, s, n): return _in_double(g, s, n)


@port(0x800604FC, ret=True)
def ascii_to_sjis(g, c):
    """A one-byte letter as its Shift-JIS twin (letters, digits, the punctuation of the tables
    0x80026B38 / 0x80026B94); others unchanged."""
    m = g.mem
    if c < 0x1A or (c - 0x80) & 0xFFFFFFFF < 0x21: return c & 0xFFFF
    if c >= 0xE0: return c & 0xFFFF
    t = m.u8(0x800C9335 + (c & 0xFF))
    if t & 1: return (c - 0x7DE1) & 0xFFFF
    if t & 2: return (c - 0x7DE0) & 0xFFFF
    if t & 4: return (c - 0x7DE1) & 0xFFFF
    for base, tab in ((-0x7EC0, 0x80026B38), (-0x7CC0, 0x80026B94)):
        i = 0
        while m.u8(tab + i):
            if m.u8(tab + i) == c: return (i + base) & 0xFFFF
            i += 1
    return c & 0xFFFF


TITLES = 0x80121EE0


@port(0x80060604, ret=True)
def file_titles(g, card, d, n, lst):
    """The titles of the n files of directory d (each file's header: 64 bytes of Shift-JIS from
    +4, one-byte letters made two-byte) as two 32-byte lines at 0x80121EE0 + 0x42 * k, and the
    list of their pointers at lst, ended by two zero words.  -1 when a file cannot be read."""
    m = g.mem
    for r in range(0x20):
        for i in range(0x21): m.w8(TITLES + 0x21 * r + i, 0)
    hdr = SCRATCH + 0x100; txt = SCRATCH + 0x180
    for i in range(0x41): m.w8(txt + i, 0)
    line1 = TITLES; off = 0; out = 0
    for k in range(max(n, 0)):
        p = _path(g, SCRATCH, card, d + 0x28 * k)
        fd = calls.call(g, 0x8008428C, p, 1)
        if fd == -1: return -1
        if calls.call(g, 0x8008429C, fd, hdr, 0x80) == -1:
            calls.call(g, 0x800842BC, fd); return -1
        calls.call(g, 0x800842BC, fd)
        calls.call(g, 0x80084868, txt, hdr + 4, 0x40)
        m.w8(txt + 0x40, 0)
        i = 0; src = txt
        while i < calls.call(g, 0x80084838, txt):
            kind = _in_double(g, txt, i + 1)
            if kind == 0:
                v = calls.call(g, 0x800604FC, m.u8(src))
                if out < 0x20: m.w8(line1 + out, v >> 8); m.w8(line1 + out + 1, v)
                else:
                    a = 0x80121F01 + off + out
                    m.w8(a - 0x20, v >> 8); m.w8(a - 0x1F, v)
                out += 2
            else:
                if out < 0x20: m.w8(line1 + out, m.u8(src))
                else: m.w8(0x80121F01 + off + out - 0x20, m.u8(src))
                out += 1
            src += 1; i += 1
        out = 0
        line2 = TITLES + 0x21 + off
        m.w32(lst + 8 * k, line1); m.w8(line1 + 0x20, 0)
        m.w32(lst + 8 * k + 4, line2); m.w8(line2 + 0x20, 0)
        off += 0x42; line1 += 0x42
    m.w32(lst + 8 * n, 0); m.w32(lst + 8 * n + 4, 0)
    return lst + 8 * n


# ------------------------------------------------------------------ the file
def _crc_table():
    t = []
    for i in range(256):
        v = i << 24
        for _ in range(8):
            v = ((v << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if v & 0x80000000 else (v << 1) & 0xFFFFFFFF
        t.append(v)
    return t


_CRC = _crc_table()


@port(0x800638C0, ret=True)
def crc(g, n):
    """CRC-32 (0x04C11DB7, most significant bit first, from all ones, inverted) of the file's
    first n bytes - the game shifts bit by bit; a byte table gives the same value."""
    m = g.mem
    data = m.bytes(FILE, n) if n > 0 and hasattr(m, 'bytes') else bytes(m.u8(a) for a in range(FILE, FILE + max(n, 0)))
    v = 0xFFFFFFFF; t = _CRC
    for c in data:
        v = ((v << 8) & 0xFFFFFFFF) ^ t[(v >> 24) ^ c]
    return (~v) & 0xFFFFFFFF


def _header(g):
    m = g.mem
    for i, c in enumerate((0x53, 0x43, 0x13, 1)): m.w8(FILE + i, c)
    calls.call(g, 0x800847F4, FILE + 4, calls.call(g, 0x80083FC4, 0x80))
    for i in range(0x20): m.w8(0x801226F8 + i, m.u8(0x800C697C + i))          # the icon's palette
    for k, src in enumerate((0x800C67FC, 0x800C687C, 0x800C68FC)):          # its three pictures
        for i in range(0x80): m.w8(FILE + 0x80 * (k + 1) + i, m.u8(src + i))


def _fill0(g, a, n):
    m = g.mem
    if isinstance(getattr(m, 'b', None), bytearray):
        o = m._chk(a, n); m.b[o:o + n] = bytes(n)
    else:
        for i in range(n): m.w8(a + i, 0)


def _tail(g):
    m = g.mem
    for i in range(0x24):
        v = calls.call(g, 0x800846A8)
        m.w8(0x80124648 + i, v - ((v >> 8) << 8))
    for i in range(0x28): m.w8(0x8012466C + i, m.u8(0x800C67B8 + i))
    m.w32(0x80124694, calls.call(g, 0x800638C0, 0x1FFC))


@port(0x80063064, ret=True)
def file_new(g, card, name):
    """A new file: created, the header and four empty records, written."""
    m = g.mem
    calls.call(g, 0x80060294, card, name)
    _header(g)
    _fill0(g, 0x80122898, 0x80124648 - 0x80122898)
    _tail(g)
    return -1 if calls.call(g, 0x800600A8, card, name, FILE) == -1 else 1


@port(0x8006343C, ret=True)
def file_save(g, card, name, k):
    """Record k := the block (0x801D93E8 -> 0x758 bytes, its index at +4), then the file
    written; the record is also copied to 0x80010000 (0x76C bytes)."""
    m = g.mem
    _header(g)
    rec = 0x80122898 + k * 0x76C
    calls.call(g, 0x80084674, rec, m.u32(DATA_PTR), m.s32(DATA_SIZE))
    m.w32(rec + 4, k)
    _tail(g)
    r = -1 if calls.call(g, 0x800600A8, card, name, FILE) == -1 else 1
    _copy(g, 0x80010000, rec, 0x76C)
    return r


def _copy(g, d, s, n):
    """(the remake's) n bytes from s to d, as a byte loop does."""
    m = g.mem
    if isinstance(getattr(m, 'b', None), bytearray) and not s < d < s + n:
        src = m.bytes(s, n); o = m._chk(d, n); m.b[o:o + n] = src
    else:
        for i in range(n): m.w8(d + i, m.u8(s + i))


# ------------------------------------------------------------------ messages
@port(0x80062F3C)
def msg_open(g, a, b, res):
    """The two-line message window (UI task 9), unless both texts are empty: then no window,
    the counter set to 17 and the answer to 0x3E8."""
    if calls.call(g, 0x80084790, a, 0x80026C14) == 0 and calls.call(g, 0x80084790, b, 0x80026C14) == 0:
        g.mem.w32(E0, 0x11); g.mem.w32(res, 0x3E8); return
    calls.call(g, 0x80052400, a, b, res)


def _msg(g, n):
    a = calls.call(g, 0x80083FC4, n); b = calls.call(g, 0x80083FC4, n + 1)
    calls.call(g, 0x80062F3C, a, b, EC)


def _close(g): calls.call(g, 0x800523D8)


# ------------------------------------------------------------------ the manager
@port(0x80060E14, ret=True)
def card_request(g, data, size, mode):
    """A save (mode 1) of size bytes at data: 1, or -1 (nothing taken) while busy or when size
    is over 0x76C."""
    m = g.mem
    if m.s32(E4) != 0: return -1
    m.w32(E8, 0x2710)
    m.w32(DATA_PTR, data); m.w32(DATA_SIZE, size); m.w32(MODE, mode)
    if size < 0x76D: return 1
    m.w32(E8, 0)
    return -1


@port(0x80060E6C)
def card_frame(g):
    m = g.mem
    if m.s32(E8) == 0: return
    mode = m.s32(MODE)
    if mode in (1, 2): calls.call(g, 0x8006167C)
    elif mode == 3: calls.call(g, 0x80060F04)


def _check(g):
    """0x8005FE3C on the chosen card; returns its _card_info result."""
    c = g.mem.s32(CARD)
    calls.call(g, 0x8005FE3C, c, ST + 4 * c, ST2 + 4 * c)
    return g.mem.s32(ST + 4 * g.mem.s32(CARD))


def _err(st): return 0x3FB if st == 3 else 0x3F9


@port(0x80062D80)
def state_4(g):
    st = _check(g)
    c = g.mem.s32(CARD)
    if st == 0: v = 0x3F0 if g.mem.s32(ST2 + 4 * c) == 0 else 0x3ED
    else: v = _err(st)
    g.mem.w32(E8, v)


@port(0x80062E24)
def state_8(g):
    m = g.mem
    st = _check(g)
    if st != 0: m.w32(E8, _err(st)); return
    calls.call(g, 0x8005FECC, m.s32(CARD), DIR, NDIR)
    found = 0; i = 0; e = DIR
    while i < m.s32(NDIR):
        if calls.call(g, 0x80084790, e, m.u32(NAME_PTR)) == 0: found = 1
        i += 1; e += 0x28
    m.w32(E8, 0x3F4 if found == 1 else 0x3F1)


@port(0x8006167C)
def card_manager(g):
    m = g.mem
    st = m.s32(E8)

    def go(v): m.w32(E8, v)                                    # 0x80062D54
    def go0(v): m.w32(E0, 0); m.w32(E8, v)                     # 0x80062D4C
    def go00(v): m.w32(F4, 0); m.w32(E0, 0); m.w32(E8, v)      # 0x80062D44

    def tick(n=0x13):
        """E0 counts; True once it had reached n."""
        t = m.s32(E0); m.w32(E0, t + 1)
        return not t < n

    def close_once():
        if m.s32(F4) == 0: _close(g); m.w32(F4, 1)

    if st == 0x6B:
        a = m.s32(F0)
        if a == 1: v = 0x3F5
        elif a >= 2 and a == 2: v = 0x3ED
        else: return
        m.w32(F0, 0); m.w32(E8, v); _close(g); m.w32(F4, 1); return
    if st == 1:
        m.w32(F4, 0)
        calls.call(g, 0x8005FE3C, 0, ST, ST2)
        r = m.s32(ST)
        if r == 0 or r == 3: m.w32(CARD, 0); go(0x3EC)
        else: go(0x3EA)
        return
    if st == 2:
        m.w32(F4, 0)
        calls.call(g, 0x8005FE3C, 1, ST + 4, ST2 + 4)
        r = m.s32(ST + 4)
        if r == 0 or r == 3: m.w32(CARD, 1); go(0x3FA)
        else: go(0x3EB)
        return
    if st == 3: m.w32(F4, 0); go(0x3F9); return
    if st == 4: m.w32(F4, 0); calls.call(g, 0x80062D80); return
    if st == 5:
        m.w32(F4, 0)
        _msg(g, 0x8F)
        m.w32(F0, 2)
        calls.call(g, 0x8005236C, calls.call(g, 0x80083FC4, 0x81), calls.call(g, 0x80083FC4, 0x82), F0)
        go(0x69); return
    if st == 6:
        m.w32(F4, 0)
        r = _check(g)
        if r == 0: go0(0x3F3 if calls.call(g, 0x800601A8, m.s32(CARD)) == 1 else 0x3FC)
        else: go(_err(r))
        return
    if st == 7:
        m.w32(F4, 0)
        _msg(g, 0x93)
        calls.call(g, 0x80052310, calls.call(g, 0x80083FC4, 0x81), calls.call(g, 0x80083FC4, 0x82), F0)
        m.w32(E8, 0x6B); return
    if st == 8: m.w32(F4, 0); calls.call(g, 0x80062E24); return
    if st == 9:
        m.w32(F4, 0)
        r = _check(g)
        if r != 0: go(_err(r)); return
        calls.call(g, 0x8005FECC, m.s32(CARD), DIR, NDIR)
        used = 0
        for i in range(m.s32(NDIR)): used = s32(used + m.s32(DIR + 0x28 * i + 0x18))
        if not 0x1C000 < used: go(0x3FF); return
        _msg(g, 0x97); go(0x3F2); return
    if st == 0xA:
        m.w32(F4, 0)
        r = _check(g)
        if r != 0: go(_err(r)); return
        calls.call(g, 0x80060604, m.s32(CARD), DIR, m.s32(NDIR), LIST)
        m.w32(LTEXT, calls.call(g, 0x80083FC4, 0x85))
        m.w32(LTEXT + 4, calls.call(g, 0x80083FC4, 0x86))
        calls.call(g, 0x8005AA94, LIST, LTEXT, F8)
        go(0x3F7); return
    if st == 0xB:
        c = m.s32(CARD)
        r = m.s32(ST + 4 * c)
        m.w32(F4, 0)
        if r != 0: go(_err(r)); return
        go(0x3FD if calls.call(g, 0x80063064, c, m.u32(NAME_PTR)) == -1 else 0x3F4); return
    if st == 0xC:
        m.w32(F4, 0)
        for k in range(4):
            m.w32(LIST + 8 * k, 0x801228A0 + 0x76C * k)
            m.w32(LIST + 8 * k + 4, 0x801228C0 + 0x76C * k)
        m.w32(0x801223B0, 0); m.w32(0x801223B4, 0)
        m.w32(LTEXT, calls.call(g, 0x80083FC4, 0x83))
        m.w32(LTEXT + 4, calls.call(g, 0x80083FC4, 0x84))
        calls.call(g, 0x8005AA94, LIST, LTEXT, F8)
        go0(0x3F8); return
    if st == 0xD:
        m.w32(F4, 0); m.w32(E0, 0)
        _msg(g, 0x9F); go(0x3F6); return
    if st == 0xE:
        m.w32(F4, 0); m.w32(E0, 0)
        calls.call(g, 0x8004D24C)
        go(0x44B); return
    if st == 0xF or st == 0x10:
        if not tick(): return
        if m.s32(F8) == -2: m.w32(F4, 1); go0(0x3F6); return
        r = _check(g)
        c = m.s32(CARD)
        if r == 0:
            if st == 0xF:
                calls.call(g, 0x80060354, c, DIR + 0x28 * m.s32(F8))
                go00(0x3FF); return
            if calls.call(g, 0x8006343C, c, m.u32(NAME_PTR), m.s32(F8)) == -1: go(0x3FD)
            else: go00(0x3FE)
            return
        m.w32(E0, 0); go(_err(m.s32(ST + 4 * c))); return
    if 0x11 <= st <= 0x16:
        m.w32(F4, 0); m.w32(E0, 0)
        _msg(g, {0x11: 0xA7, 0x12: 0xA9, 0x13: 0xAB, 0x14: 0xAD, 0x15: 0xAF, 0x16: 0xB1}[st])
        go(0x3F5); return
    if st == 0x17: go00(0x3F3); return
    if st == 0x63:
        m.w32(F4, 0); m.w32(E0, 0); m.w32(E8, 0); m.w32(E4, 0)
        g.mode_flags &= ~8
        return
    if st == 0x69:
        a = m.s32(F0)
        if a == 1: v = 0x3EE
        elif a == 2: v = 0x3EF
        else: return
        m.w32(F0, 0); m.w32(E8, v); m.w32(E0, 0)
        _close(g); m.w32(F4, 1); return
    if st == 0x3EA: go(2); return
    if st == 0x3EB: go(3); return
    if st == 0x3EC: go(4); return
    if st == 0x3ED:
        close_once()
        if tick(): go0(5)
        return
    if st == 0x3EE:
        if m.s32(F4) == 1:
            t = m.s32(E0); m.w32(E0, t + 1)
            if not t < 0x1C: m.w32(E0, 0); m.w32(F4, 2)
        if m.s32(F4) == 2:
            _msg(g, 0x91); m.w32(F4, 3)
        if m.s32(F4) == 3 and tick(): go0(6)
        return
    if st in (0x3EF, 0x3F5, 0x3F2):
        if m.s32(EC) == 0x3E8: m.w32(F4, 1)
        mask = 0xF0 if st == 0x3F2 else 0x80
        if g.pad_pressed & mask: _close(g); m.w32(F4, 1)
        if m.s32(F4) != 0 and tick(): go0({0x3EF: 7, 0x3F5: 0xD, 0x3F2: 0xA}[st])
        return
    if st == 0x3F0: go(8); return
    if st == 0x3F1:
        if m.s32(EC) == 0x3E8: m.w32(F4, 1)
        _close(g); m.w32(F4, 1)
        if tick(): go0(9)
        return
    if st == 0x3F3:
        if m.s32(F4) == 0:
            c = m.s32(CARD)
            calls.call(g, 0x8005FE3C, c, ST + 4 * c, ST2 + 4 * c)
            m.w32(F4, 1)
        if m.s32(F4) == 1: _close(g); m.w32(F4, 2)
        if m.s32(F4) == 2 and tick(): go0(0xB)
        return
    if st == 0x3F4:
        if m.s32(F4) == 0:
            calls.call(g, 0x8005FFA8, m.s32(CARD), m.u32(NAME_PTR), FILE)
            _close(g); m.w32(F4, 1)
        if tick(): go0(0xC)
        return
    if st == 0x3F6:
        close_once()
        if tick(): go0(0xE)
        return
    if st == 0x3F7:
        f = m.s32(F8)
        if f == -1: return
        if f == -2: m.w32(E8, 0xF); m.w32(E0, 0); return
        m.w32(E8, 0xF); _msg(g, 0xA3); m.w32(E0, 0); return
    if st == 0x3F8:
        f = m.s32(F8)
        if f == -1: return
        if not tick(): return
        if f != -2: _msg(g, 0xA5)
        m.w32(E8, 0x10); m.w32(E0, 0); return
    if st in (0x3F9, 0x3FA, 0x3FB, 0x3FC, 0x3FD, 0x3FE):
        close_once()
        if tick() and m.s32(F8) != -1:
            go0({0x3F9: 0x11, 0x3FA: 0x12, 0x3FB: 0x13, 0x3FC: 0x14, 0x3FD: 0x15, 0x3FE: 0x16}[st])
        return
    if st == 0x3FF:
        close_once()
        if m.s32(F4) == 1:
            if tick() and m.s32(F8) != -1:
                m.w32(E0, 0); _msg(g, 0xB3); m.w32(F4, 2)
        if m.s32(F4) == 2:
            if tick() and m.s32(F8) != -1: go0(0x17)
        return
    if st == 0x44B:
        close_once()
        if tick(0xB): go0(0x63)
        return
    if st == 0x2710:
        m.w32(E4, 1); m.w32(E0, 0)
        g.mode_flags |= 8
        _msg(g, 0x87); go(0x2711); return
    if st == 0x2711:
        if tick(): go0(1)
        return


# ------------------------------------------------------------------ the save point
@port(0x800314F8)
def save_title(g):
    """The block's two title lines: the chapter (0x80083CC4: the last of the table 0x800295D2
    whose flag is set) at 0x801DD2E0, and "  HP nn       TIME hh:mm:ss   " at 0x801DD300 with
    Alundra's life maximum and the play time (0x801D7CB4, frames at 60 a second)."""
    m = g.mem
    calls.call(g, 0x80083CC4, 0x801DD2E0)
    for src, n in ((0x80022BF8, 0x1D), (0x80022C18, 0x1F), (0x80022C38, 0x1F)):
        for i in range(n): m.w8(0x801DD300 + i, m.u8(src + i))
    t = m.s32(0x801D7CB4)
    hp = g.ent[0].hp_max                                            # 0x801AC710
    h = _q(t, 216000); hh = h - _q(h, 100) * 100
    mm = _q(t, 3600) - h * 60
    ss = _q(t, 60) - _q(t, 3600) * 60
    m.w8(0x801DD31E, 0)
    m.w8(0x801DD305, _q(hp, 10) + 0x30); m.w8(0x801DD306, hp - _q(hp, 10) * 10 + 0x30)
    m.w8(0x801DD31F, 0)
    m.w8(0x801DD316, _q(mm, 10) + 0x30); m.w8(0x801DD317, mm - _q(mm, 10) * 10 + 0x30)
    m.w8(0x801DD319, _q(ss, 10) + 0x30); m.w8(0x801DD31A, ss - _q(ss, 10) * 10 + 0x30)
    m.w8(0x801DD313, _q(hh, 10) + 0x30); m.w8(0x801DD314, hh - _q(hh, 10) * 10 + 0x30)


def _q(a, b):
    """C division (towards 0)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


@port(0x80083CC4, ret=True)
def chapter(g, dst):
    """The chapter: the table at 0x800295D2 (0x22 bytes: s16 flag, 32 bytes of name) is walked
    while each entry's flag is set (an entry with flag 0 counts as set); the last one passed is
    copied to dst (when dst != 0).  Returns its index."""
    m = g.mem; n = 1; a = 0x800295D2
    while True:
        f = m.s16(a)
        if f != 0:
            if f < 0: break
            if not m.u32(0x801DD334 + ((f >> 3) & 0xFFC)) >> (f & 31) & 1: break
        a += 0x22; n += 1
    n -= 1
    if dst: calls.call(g, 0x800847F4, dst, 0x800295B2 + n * 0x22)
    return n


@port(0x80031AC4)
def save_menu(g):
    """The save point's menu: the respawn point (the map, Alundra's tile x / y / z), the title
    lines, the play time kept (0x801DD320 = 0x801D7CB4) and the request."""
    m = g.mem; p = g.ent[0]
    m.w32(0x801DD324, g.cur_map)
    m.w32(0x801DD328, p.tile_x); m.w32(0x801DD32C, p.tile_y); m.w32(0x801DD330, p.tile_z)
    file_name(g)
    if getattr(g, 'lang', 'us') == 'jp': save_title_jp(g)
    else: calls.call(g, 0x800314F8)
    m.w32(0x801DD320, m.u32(0x801D7CB4))
    calls.call(g, 0x80060E14, 0x801DD2D8, 0x758, 1)


US_NAME = b'BASLUS-00553ALUNDRA '      # US ALUN_CD.EXE (the string 0x800C67B0 points to)
JP_NAME = b'BISCPS-10035ALUNDRA '      # JP ALUN_CD.EXE file +0x738C, SCPS_100.35 file +0xB58
EU_NAMES = {'en_eu': b'BESLES-01135ALUNDRA ', 'fr': b'BESLES-01198ALUNDRA ', 'de': b'BESLES-01256ALUNDRA ',
            'it': b'BESLES-01258ALUNDRA ', 'es': b'BESLES-01257ALUNDRA '}   # (end of each disc's ETC_RES.R)


def file_name(g):
    """(the remake's) The save file's name by Options > Dialogue & font: JP saves as the JP game
    does (BISCPS-10035ALUNDRA), else as the US one.  The file itself is the same in both (JP
    0x80064244 / 0x80064624 = US 0x80063064 / 0x8006343C: 'SC' 0x13 1, title +4, palette +0x60,
    icon +0x80, 4 records of 0x76C at +0x200, 0x24 random bytes and the maker's string at
    +0x1FB0, CRC-32 at +0x1FFC; icon, palette and maker byte-identical); only the JP header's
    title is fixed bytes (JP 0x80026EF0, "アランドラ" and full-width spaces) where the US one is
    text 0x80 - in the remake's JP mode that text is the same 64 bytes.  The name is written
    over the US string in place (both 20 letters)."""
    m = g.mem; a = m.u32(NAME_PTR)
    cur = bytes(m.u8(a + i) for i in range(20))
    if cur not in (US_NAME, JP_NAME, *EU_NAMES.values()): return
    lang = getattr(g, 'lang', 'us')
    want = JP_NAME if lang == 'jp' else EU_NAMES.get(lang, US_NAME)   # (a European language: its disc's name)
    if cur != want:
        for i, c in enumerate(want): m.w8(a + i, c)


def save_title_jp(g):
    """JP 0x80032710 (the JP save_title): the chapter (as 0x80083CC4) at block +8, then at
    block +0x28 the 0x1D bytes of JP 0x80022BE8 (14 full-width spaces) with, in full-width
    Shift-JIS, 0x819E (+6), Alundra's life maximum (+8, +0xA), the hours mod 60 (+0x12, +0x14),
    "：" (+0x16) and the minutes (+0x18, +0x1A); no seconds.  (JP block 0x801DE05C = US
    0x801DD2D8, play time JP 0x801D91D0 = US 0x801D7CB4, life JP 0x801AE440 = US 0x801AC710.)"""
    m = g.mem
    calls.call(g, 0x80083CC4, 0x801DD2E0)
    L = 0x801DD300
    for i in range(14): m.w8(L + 2 * i, 0x81); m.w8(L + 2 * i + 1, 0x40)
    m.w8(L + 0x1C, 0)
    t = m.s32(0x801D7CB4)
    hp = g.ent[0].hp_max
    h = _q(t, 216000); hh = h - _q(h, 60) * 60
    mm = _q(t, 3600) - h * 60
    m.w8(L + 6, 0x81); m.w8(L + 7, 0x9E)
    for off, v in ((8, _q(hp, 10)), (0xA, hp - _q(hp, 10) * 10), (0x12, _q(hh, 10)),
                   (0x14, hh - _q(hh, 10) * 10), (0x18, _q(mm, 10)), (0x1A, mm - _q(mm, 10) * 10)):
        m.w8(L + off, 0x82); m.w8(L + off + 1, (v + 0x4F) & 0xFF)
    m.w8(L + 0x16, 0x81); m.w8(L + 0x17, 0x46)


def play_tick(g):
    """0x80043380 / 0x80043488 (each picture shown): the play time counts frames up to 100 hours."""
    t = g.mem.s32(0x801D7CB4)
    if not 0x14996C3 < t: g.mem.w32(0x801D7CB4, t + 1)
