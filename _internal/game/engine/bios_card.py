"""The PlayStation BIOS memory card services the game calls, over standard raw card images
(128 KB .mcd / .mcr files, the format emulators use: 16 blocks of 8 KB, block 0 the directory).

This is the BIOS, not the game: ALUN_CD.EXE reaches it through the A0 / B0 call stubs
  B0:0B TestEvent 0x8008423C   B0:32 open 0x8008428C    B0:34 read 0x8008429C
  B0:35 write 0x800842AC       B0:36 close 0x800842BC   B0:41 format 0x800842CC
  B0:42 firstfile 0x800842DC   B0:43 nextfile 0x800842EC B0:45 erase 0x800842FC
  B0:4E _card_write 0x80085AE4 B0:4F _card_read 0x80085A8C B0:50 _new_card 0x80085A9C
  A0:AB _card_info 0x80085A2C  A0:AC _card_load 0x80085A3C
and the game's own code (engine/card.py) waits on the events they deliver.  The checks run the
original game code against this same emulation (tools/us_decomp/tests_card.py).

Events (the handles boot opens; OpenEvent numbers them 0xF1000001 on):
  0x801DD2CC / D0 / D4 / 0x801DDA30   SwCARD: IOE, ERROR, TIMEOUT, NEW (_card_info, _card_load)
  0x801E6350 / 54 / 58 / 5C           HwCARD: IOE, ERROR, TIMEOUT, NEW (_card_read, _card_write)
A slot without a card answers TIMEOUT; a card seen for the first time since power-on (or since
it was put in) answers NEW to _card_info until _new_card + a sector write clear its flag;
_card_load answers ERROR when the card is not formatted ("MC" missing)."""
import os, struct

SW = (0x801DD2CC, 0x801DD2D0, 0x801DD2D4, 0x801DDA30)
HW = (0x801E6350, 0x801E6354, 0x801E6358, 0x801E635C)
HANDLES = dict(zip(SW + HW, range(0xF1000001, 0xF1000009)))
IOE, ERROR, TIMEOUT, NEW = range(4)
CARD = 0x20000
FREE, FIRST, MIDDLE, LAST = 0xA0, 0x51, 0x52, 0x53


def blank_formatted():
    """A freshly formatted card: the header frame "MC", 15 free directory frames, 20 unused
    broken-sector frames, and the write-test frame."""
    c = bytearray(CARD)
    c[0:2] = b'MC'; c[0x7F] = _xor(c[0:0x7F])
    for i in range(1, 16):
        f = bytearray(0x80); struct.pack_into('<IIH', f, 0, 0xA0, 0, 0xFFFF); f[0x7F] = _xor(f[:0x7F])
        c[i * 0x80:(i + 1) * 0x80] = f
    for i in range(16, 36):
        f = bytearray(0x80); struct.pack_into('<IIH', f, 0, 0xFFFFFFFF, 0, 0xFFFF); f[0x7F] = _xor(f[:0x7F])
        c[i * 0x80:(i + 1) * 0x80] = f
    c[63 * 0x80:64 * 0x80] = c[0:0x80]
    return c


def _xor(b):
    x = 0
    for v in b: x ^= v
    return x


class Slot:
    def __init__(self, path=None, data=None):
        self.path = path
        self.data = bytearray(data) if data is not None else None
        if self.data is None and path and os.path.exists(path):
            raw = open(path, 'rb').read()
            if raw[:11] == b'123-456-STD':                       # .mcd variants with a 128-byte head
                raw = raw[0x80:]
            self.data = bytearray(raw[:CARD].ljust(CARD, b'\0'))
        self.new = True                                          # the card's "new" flag (power-on)

    present = property(lambda s: s.data is not None)

    def flush(self):
        if self.path and self.data is not None:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'wb') as f: f.write(self.data)
            os.replace(tmp, self.path)

    def formatted(self):
        return self.present and self.data[0:2] == b'MC'

    # ---- the directory
    def frame(self, i): return self.data[i * 0x80:(i + 1) * 0x80]

    def set_frame(self, i, f):
        f = bytearray(f); f[0x7F] = _xor(f[:0x7F]); self.data[i * 0x80:(i + 1) * 0x80] = f

    def files(self):
        """(name, first block, blocks) of every file, in directory order."""
        out = []
        for i in range(1, 16):
            f = self.frame(i)
            if struct.unpack_from('<I', f)[0] != FIRST: continue
            name = bytes(f[0xA:0xA + 20]).split(b'\0')[0]
            n, b = 0, i
            while 1 <= b <= 15 and n < 15:
                n += 1
                nx = struct.unpack_from('<H', self.frame(b), 8)[0]
                if nx == 0xFFFF: break
                b = nx + 1
            out.append((name, i, n))
        return out

    def find(self, name):
        for nm, b, n in self.files():
            if nm == name: return b, n
        return None

    def chain(self, b):
        out = []
        while 1 <= b <= 15 and len(out) < 15:
            out.append(b)
            nx = struct.unpack_from('<H', self.frame(b), 8)[0]
            if nx == 0xFFFF: break
            b = nx + 1
        return out

    def create(self, name, blocks):
        free = [i for i in range(1, 16) if struct.unpack_from('<I', self.frame(i))[0] & 0xF0 == 0xA0]
        if len(free) < blocks or self.find(name) is not None: return False
        use = free[:blocks]
        for k, b in enumerate(use):
            f = bytearray(0x80)
            state = FIRST if k == 0 else (LAST if k == blocks - 1 else MIDDLE)
            nxt = use[k + 1] - 1 if k + 1 < blocks else 0xFFFF
            struct.pack_into('<IIH', f, 0, state, blocks * 0x2000 if k == 0 else 0, nxt)
            if k == 0: f[0xA:0xA + len(name)] = name
            self.set_frame(b, f)
            self.data[b * 0x2000:(b + 1) * 0x2000] = bytes(0x2000)
        return True

    def erase(self, name):
        r = self.find(name)
        if r is None: return False
        for b in self.chain(r[0]):
            f = bytearray(self.frame(b))
            st = struct.unpack_from('<I', f)[0]
            struct.pack_into('<I', f, 0, (st & 0x0F) | 0xA0)
            self.set_frame(b, f)
        return True


class Bios:
    """The card services for both slots ("bu00:" = slot 1, "bu10:" = slot 2)."""

    def __init__(self, slot1=None, slot2=None):
        self.slots = [slot1 or Slot(), slot2 or Slot()]
        self.pending = set()                    # event handles delivered and not yet tested
        self.fds = {}                           # fd -> [port, name, pos, mode]
        self.dir_iter = None                    # firstfile / nextfile: (port, names left)
        self.dirty = set()

    # ---- events
    def _fire(self, mem, table, which):
        self.pending.add(mem.u32(table[which]))

    def test_event(self, mem, h):
        if h in self.pending:
            self.pending.discard(h); return 1
        return 0

    # ---- A0 / B0 card level
    def _port(self, chan): return 0 if chan < 0x10 else 1

    def card_info(self, mem, chan):
        s = self.slots[self._port(chan)]
        self._fire(mem, SW, TIMEOUT if not s.present else NEW if s.new else IOE)
        return 1

    def card_load(self, mem, chan):
        s = self.slots[self._port(chan)]
        self._fire(mem, SW, TIMEOUT if not s.present else IOE if s.formatted() else ERROR)
        return 1

    def new_card(self, mem):
        self._new_ack = True

    def card_read(self, mem, chan, sector, buf):
        s = self.slots[self._port(chan)]
        if not s.present: self._fire(mem, HW, TIMEOUT); return 1
        a = (sector & 0x3FF) * 0x80
        for i in range(0x80): mem.w8(buf + i, s.data[a + i])
        self._fire(mem, HW, IOE)
        return 1

    def card_write(self, mem, chan, sector, buf):
        s = self.slots[self._port(chan)]
        if not s.present: self._fire(mem, HW, TIMEOUT); return 1
        if buf:
            a = (sector & 0x3FF) * 0x80
            for i in range(0x80): s.data[a + i] = mem.u8(buf + i)
            self.dirty.add(self._port(chan))
        s.new = False
        self._fire(mem, HW, IOE)
        return 1

    # ---- B0 file system ("bu00:NAME")
    def _split(self, mem, a):
        raw = bytearray()
        while len(raw) < 64:
            c = mem.u8(a + len(raw))
            if c == 0: break
            raw.append(c)
        raw = bytes(raw)
        if not (raw[:2] == b'bu' and len(raw) >= 5 and raw[4:5] == b':'): return None, None
        port = 0 if raw[2:3] == b'0' else 1
        return port, raw[5:5 + 20]

    def open(self, mem, name, mode):
        port, nm = self._split(mem, name)
        if port is None: return -1
        s = self.slots[port]
        if not s.formatted(): return -1
        if mode & 0x200:
            blocks = (mode >> 16) or 1
            if not s.create(nm, blocks): return -1
            self.dirty.add(port)
        elif s.find(nm) is None: return -1
        fd = 2
        while fd in self.fds: fd += 1
        self.fds[fd] = [port, nm, 0, mode]
        return fd

    def _io(self, mem, fd, buf, n, write):
        f = self.fds.get(fd)
        if f is None or n < 0 or n % 0x80: return -1
        port, nm, pos, mode = f
        s = self.slots[port]
        r = s.find(nm)
        if r is None: return -1
        blocks = s.chain(r[0])
        if pos + n > len(blocks) * 0x2000: return -1
        raw = getattr(mem, 'b', None)
        if isinstance(raw, bytearray):                          # whole runs within a block at once
            i = 0
            while i < n:
                p = pos + i
                a = blocks[p // 0x2000] * 0x2000 + p % 0x2000
                k = min(n - i, 0x2000 - p % 0x2000)
                if write: s.data[a:a + k] = mem.bytes(buf + i, k)
                else:
                    o = mem._chk(buf + i, k); raw[o:o + k] = s.data[a:a + k]
                i += k
        else:
            for i in range(n):
                p = pos + i
                a = blocks[p // 0x2000] * 0x2000 + p % 0x2000
                if write: s.data[a] = mem.u8(buf + i)
                else: mem.w8(buf + i, s.data[a])
        f[2] = pos + n
        if write: self.dirty.add(port)
        return n

    def read(self, mem, fd, buf, n): return self._io(mem, fd, buf, n, False)
    def write(self, mem, fd, buf, n): return self._io(mem, fd, buf, n, True)

    def close(self, mem, fd):
        if self.fds.pop(fd, None) is None: return -1
        self.flush()
        return fd

    def format(self, mem, dev):
        port, _ = self._split(mem, dev)
        if port is None or not self.slots[port].present: return 0
        self.slots[port].data[:] = blank_formatted()
        self.dirty.add(port); self.flush()
        return 1

    def erase(self, mem, name):
        port, nm = self._split(mem, name)
        if port is None or not self.slots[port].formatted(): return 0
        ok = self.slots[port].erase(nm)
        if ok: self.dirty.add(port); self.flush()
        return 1 if ok else 0

    def _dirent(self, mem, d):
        port, names = self.dir_iter
        if not names: self.dir_iter = None; return 0
        nm, head, n = names.pop(0)
        for i in range(20): mem.w8(d + i, nm[i] if i < len(nm) else 0)
        mem.w32(d + 0x14, 0); mem.w32(d + 0x18, n * 0x2000)            # (attr 0: a 20-letter name still
        mem.w32(d + 0x1C, 0); mem.w32(d + 0x20, head * 0x40); mem.w32(d + 0x24, 0)   # compares equal; head: its sector)
        return d

    def firstfile(self, mem, pattern, d):
        port, pat = self._split(mem, pattern)
        if port is None or not self.slots[port].formatted(): self.dir_iter = None; return 0
        names = [f for f in self.slots[port].files() if _match(pat, f[0])]
        self.dir_iter = (port, names)
        return self._dirent(mem, d)

    def nextfile(self, mem, d):
        if self.dir_iter is None: return 0
        return self._dirent(mem, d)

    def flush(self):
        for p in sorted(self.dirty): self.slots[p].flush()
        self.dirty.clear()


def _match(pat, name):
    """The BIOS name match: '?' any one letter, '*' the rest."""
    for i, c in enumerate(pat):
        if c == 0x2A: return True
        if i >= len(name): return False
        if c != 0x3F and c != name[i]: return False
    return len(pat) == len(name)
