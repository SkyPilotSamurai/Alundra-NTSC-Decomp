"""The CD drive's part of the loading pauses: where the read head is and what each read the game makes costs,
timed as BizHawk's PS1 core (Mednafen's CD timing) times them, on the US v1.1 disc's layout (DATA/DATAS.BIN
at sector 24, DATA/SOUND.BIN at 53222, ARAN_XA.XA at 59172).
A read (0x80083F04 -> 0x80050220): Setloc + ReadN of the whole sectors, then the last part sector as a read of
its own; the drive pauses after each, so the next one seeks again (a short seek from pause costs as much as
a long one under 2250 sectors).  docs/2026-11-04-transition-sound-bizhawk-vs-pc.txt."""
from engine import rodata as R

DATAS, SOUND, ARAN_XA = 24, 53222, 59172
FIRST_MAP = 724992                     # DATAS.BIN: map 0's block; the blocks follow each other in map order
CPS = 33868800                         # CPU cycles a second
FRAME = CPS / 59.826                   # cycles a frame
SECTOR = CPS / 150                     # double speed: 150 sectors a second
MUSIC_TABLE = 0x800A9DF8               # per track: SEQ, VAB header, VAB body (SOUND.BIN bytes)
BANK_TABLE = 0x800A9B9C                # per bank: VAB header, VAB body
CHUNK = 0x10000                        # VAB bodies are read and sent to the SPU 64 KB at a time

head = None                            # the sector after the last one read (None: not known yet)


def seek(a, b):
    """Mednafen PS_CDC::CalcSeekTime with the motor on, from pause (its random 0..25000 cycles left out)."""
    d = abs(a - b)
    t = max(d * CPS * 1000 // (72 * 60 * 75) // 1000, 20000)
    return t + (CPS * 300 // 1000 if d >= 2250 else 1237952)


def _read(lba, n, out):
    global head
    out[0] += (seek(head, lba) if head is not None else seek(lba, lba)) + n * SECTOR
    out[1] += 1
    head = lba + n


def file_read(lba0, off, size, out):
    """0x80083F04 (off is whole sectors): out = [cycles, reads, chunks] added to."""
    n = size // 2048
    if n: _read(lba0 + off // 2048, n, out)
    if size % 2048: _read(lba0 + off // 2048 + n, 1, out)


def _vab(hdr, body, end, out):
    file_read(SOUND, hdr, body - hdr, out)
    p = body
    while p < end:
        k = min(CHUNK, end - p); file_read(SOUND, p, k, out); p += k; out[2] += 1


def map_reads(m, sizes):
    """The new map's DATAS.BIN block: [cycles, reads, chunks]."""
    out = [0, 0, 0]
    if m in sizes: file_read(DATAS, FIRST_MAP + sum(sizes.get(k, 0) for k in range(m)), sizes[m], out)
    return out


def music_reads(mid):
    """0x8004AD80: the track's VAB header, body (64 KB chunks), SEQ."""
    out = [0, 0, 0]
    try:
        t = MUSIC_TABLE + 12 * mid
        seq, hdr, body, nxt = R.u32(t), R.u32(t + 4), R.u32(t + 8), R.u32(t + 12)
    except Exception: return out
    _vab(hdr, body, nxt, out)
    file_read(SOUND, seq, hdr - seq, out)
    return out


def bank_reads(b):
    """0x800499AC -> 0x80049820: the bank's VAB header and body."""
    out = [0, 0, 0]
    try:
        t = BANK_TABLE + 8 * b
        hdr, body, nxt = R.u32(t), R.u32(t + 4), R.u32(t + 8)
    except Exception: return out
    _vab(hdr, body, nxt, out)
    return out


def xa_seek():
    """0x8005CCC8: SeekL to the spell's clip (channels 0-3 of ARAN_XA's first sectors), waited for."""
    global head
    c = seek(head, ARAN_XA) if head is not None else seek(ARAN_XA, ARAN_XA)
    head = ARAN_XA
    return c
