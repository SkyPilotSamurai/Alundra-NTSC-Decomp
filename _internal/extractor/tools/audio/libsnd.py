"""The parts of Sony's libsnd the game's sounds go through, ported from ALUN_CD.EXE, plus VAB
bank access.  Everything here produces SPU register values; tools/audio/spu_replay.render (the
runtime's SPU, compiled as ~/us/spurender) turns them into sound.

  key-on volume (0x800934C0): v = vel * vab.mvol * 0x3FFF / 16129 * prog.mvol * tone.vol / 16129,
      times seq volume L / R / 127 (sequences only); then tone pan, program pan and the
      voice / channel pan: pan < 64 scales R by pan / 63, else L by (127 - pan) / 63;
      the register gets v * v / 0x3FFF (a squared law).
  sequence velocity (0x80095D20): vel = note velocity * channel volume / 127.
  pitch (0x80094480): table 0x800CB600 [semitone][1/16], octave shifts around note 60 + centre.
  ADSR: the tone's two words (+0x10, +0x12); reverb send when tone mode & 4."""
import struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
EXE = (ROOT / 'private-inputs/disc/ALUN_CD.EXE').read_bytes()
SOUND = (ROOT / 'private-inputs/disc/DATA/SOUND.BIN').read_bytes()
LOAD = struct.unpack_from('<I', EXE, 0x18)[0]


def exe_u16(a): return struct.unpack_from('<H', EXE, a - LOAD + 0x800)[0]
def exe_s16(a): return struct.unpack_from('<h', EXE, a - LOAD + 0x800)[0]
def exe_s32(a): return struct.unpack_from('<i', EXE, a - LOAD + 0x800)[0]


PITCH_TABLE = [exe_u16(0x800CB600 + 2 * i) for i in range(12 * 16)]


class Vab:
    def __init__(self, data, hdr, body, body_end=None):
        self.d = data; self.hdr = hdr; self.body = body
        assert data[hdr:hdr + 4] == b'pBAV', hex(hdr)
        self.nprog, self.ntone, self.nvag = struct.unpack_from('<3H', data, hdr + 0x12)
        self.mvol = data[hdr + 0x18]; self.pan = data[hdr + 0x19]
        tbl = hdr + 0x20 + 128 * 16 + self.nprog * 16 * 32
        self.sizes = struct.unpack_from('<256H', data, tbl)
        self.body_end = body_end or len(data)

    def prog(self, p):
        a = self.hdr + 0x20 + p * 16; b = self.d[a:a + 16]
        return dict(tones=b[0], mvol=b[1], prior=b[2], mode=b[3], mpan=b[4])

    def tone(self, p, t):
        a = self.hdr + 0x20 + 128 * 16 + (p * 16 + t) * 32; b = self.d[a:a + 32]
        return dict(prior=b[0], mode=b[1], vol=b[2], pan=b[3], center=b[4], shift=b[5], min=b[6], max=b[7],
                    adsr1=struct.unpack_from('<H', b, 0x10)[0], adsr2=struct.unpack_from('<H', b, 0x12)[0],
                    prog=struct.unpack_from('<h', b, 0x14)[0], vag=struct.unpack_from('<h', b, 0x16)[0])

    def vag_offset(self, n):
        """Byte offset of VAG n (1-based) inside the body."""
        return sum(self.sizes[:n]) * 8

    def vag(self, n):
        o = self.body + self.vag_offset(n); return self.d[o:o + self.sizes[n] * 8]

    def body_bytes(self):
        return self.d[self.body:self.body + sum(self.sizes[:self.nvag + 1]) * 8]


def global_vab():
    return Vab(SOUND, exe_s32(0x800A9B94), exe_s32(0x800A9B98))


def bank_vab(n):
    hdr, body = exe_s32(0x800A9B9C + 8 * n), exe_s32(0x800A9B9C + 8 * n + 4)
    return Vab(SOUND, hdr, body)


def note_pitch(note, fine, tone):
    """0x80094480."""
    v = (fine & 0xFFFF) + tone['shift']
    v = v >> 3 if v >= 0 else (v + 7) >> 3
    carry = 0
    if v >= 0x10: carry = 1; v -= 0x10
    n = carry + note + 0x3C - tone['center']
    n = ((n + 0x8000) & 0xFFFF) - 0x8000
    q = int(n / 12) if n >= 0 else -int(-n / 12)
    r = n - q * 12
    octave = q - 5
    p = PITCH_TABLE[r * 16 + v]
    if octave > 0: p = (p << octave) & 0xFFFF
    elif octave < 0: p = p >> -octave
    return p & 0xFFFF


def key_volume(vel, vab, prog, tone, voice_pan=0x40, seq_l=None, seq_r=None):
    """0x800934C0: the voice's L / R volume registers."""
    v = (vel * (vab.mvol * 0x3FFF)) // 16129 * prog['mvol'] * tone['vol'] // 16129
    l = r = v
    if seq_l is not None:
        l = v * seq_l // 127; r = v * seq_r // 127
    for pan in (tone['pan'], prog['mpan'], voice_pan):
        if pan < 0x40: r = r * pan // 63
        else: l = l * (0x7F - pan) // 63
    return (l * l) // 0x3FFF, (r * r) // 0x3FFF


SOUND_REC = 0x800AA150
SOUND_COUNT = exe_s32(0x80026848)


def sound_record(n):
    a = SOUND_REC + 0x16 * n
    r = [exe_s16(a + 2 * k) for k in range(11)]
    return dict(bank=r[0], prog=r[1], tone=r[2], note=r[3], flags=r[4], seq=r[5], next=r[6], voices=r[8], count=r[10])


def map_bank(m):
    """0x8004B0D8: the sound-effect bank a map loads (table 0x800C8B90)."""
    return exe_s32(0x800C8B90 + 4 * m)
