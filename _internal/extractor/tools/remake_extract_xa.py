"""The XA audio clips the game streams from ARAN_XA.XA (script command B9 and the rare-item
jingle, both through 0x8005CB94): table 0x800C6680 in ALUN_CD.EXE, 12 bytes a clip - first
sector (from the file's start), channel, length in groups of 8 sectors; the drive reads
sector .. sector + 8 * length - 1 and the clip's channel plays (file number 1, 0x80121EC8).
Decoded here from the disc image's raw sectors (XA ADPCM, as the CD-ROM decoder does) to
    remake/assets/audio/xa/clip_NN.ogg (+ clip_11_2x.ogg, the jingle at double speed)
    remake/assets/audio/xa/clips.json  {n: {rate, stereo, seconds, frames}}
    python tools/remake_extract_xa.py [path to the .bin]"""
import json, struct, subprocess, sys, tempfile, wave
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'remake' / 'assets' / 'audio' / 'xa'
BIN = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/home/claude/disc/Alundra (USA) (Rev 1).bin')
FPS = 53_693_175 / (3413 * 263)                 # the console's frame rate
K0, K1 = (0, 60, 115, 98, 122), (0, 0, -52, -55, -60)


def raw_sector(f, n):
    f.seek(n * 2352); return f.read(2352)


def iso_file(f, path):
    """(first sector, size) of a file in the image's ISO 9660 tree."""
    def entries(lba, size):
        for k in range((size + 2047) // 2048):
            d = raw_sector(f, lba + k)[24:24 + 2048]; i = 0
            while i < 2048 and d[i]:
                L = d[i]; ext, sz = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0]
                yield d[i + 33:i + 33 + d[i + 32]].decode('latin-1').split(';')[0], ext, sz
                i += L
    pvd = raw_sector(f, 16)[24:24 + 2048]
    lba, size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
    for part in path.split('/'):
        lba, size = next((e, s) for n, e, s in entries(lba, size) if n == part)
    return lba, size


class Decoder:
    def __init__(self): self.old = [0, 0]; self.older = [0, 0]

    def unit(self, grp, blk, ch, out, bits8):
        h = grp[4 + blk]; shift = h & 0xF; filt = min(4, (h >> 4) & 3)
        for i in range(28):
            if bits8: v = struct.unpack('b', bytes([grp[16 + i * 4 + blk]]))[0] << 8
            else:
                n = (grp[16 + i * 4 + (blk >> 1)] >> ((blk & 1) * 4)) & 0xF
                v = (n << 12) - (0x10000 if n & 8 else 0)
            s = (v >> shift) + ((self.old[ch] * K0[filt] + self.older[ch] * K1[filt] + 32) >> 6)
            s = max(-32768, min(32767, s))
            self.older[ch] = self.old[ch]; self.old[ch] = s
            out.append(s)

    def sector(self, data, stereo, bits8):
        L, R = [], []
        for g in range(18):
            grp = data[g * 128:(g + 1) * 128]
            units = 4 if bits8 else 8
            for blk in range(units):
                if stereo: self.unit(grp, blk, blk & 1, L if not blk & 1 else R, bits8)
                else: self.unit(grp, blk, 0, L, bits8)
        return L, R


def main():
    exe = (ROOT / 'private-inputs' / 'disc' / 'ALUN_CD.EXE').read_bytes()
    base = struct.unpack_from('<I', exe, 0x18)[0]
    table = [struct.unpack_from('<3i', exe, 0x800 + 0x800C6680 - base + 12 * i) for i in range(13)]
    OUT.mkdir(parents=True, exist_ok=True)
    info = {}
    with open(BIN, 'rb') as f:
        lba, size = iso_file(f, 'ARAN_XA.XA')
        for n, (sec, ch, ln) in enumerate(table):
            if ln <= 0: continue
            dec = Decoder(); left, right = [], []; fmt = None
            for s in range(sec, sec + 8 * ln):
                r = raw_sector(f, lba + s)
                fn, chan, sub, coding = r[16:20]
                if chan != ch or not sub & 4 or fn != 1: continue
                stereo, rate_bit, bits8 = coding & 1, (coding >> 2) & 1, (coding >> 4) & 1
                fmt = (stereo, 18900 if rate_bit else 37800, bits8)
                l, rr = dec.sector(r[24:24 + 2304], stereo, bits8)
                left += l; right += (rr if stereo else l)
            if fmt is None: continue
            rate = fmt[1]
            with tempfile.TemporaryDirectory() as td:
                w = Path(td) / 'c.wav'
                with wave.open(str(w), 'wb') as wf:
                    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(rate)
                    wf.writeframes(b''.join(struct.pack('<hh', a, b) for a, b in zip(left, right)))
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(w), '-c:a', 'libvorbis', '-q:a', '8',
                                str(OUT / f'clip_{n:02d}.ogg')], check=True)
                if n == 11:
                    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(w), '-filter:a', 'atempo=2.0',
                                    '-c:a', 'libvorbis', '-q:a', '8', str(OUT / f'clip_{n:02d}_2x.ogg')], check=True)
            secs = len(left) / rate
            info[n] = {'sector': sec, 'channel': ch, 'groups': ln, 'rate': rate, 'stereo': bool(fmt[0]),
                       'seconds': round(secs, 3), 'frames': round(secs * FPS)}
            print(n, info[n], flush=True)
    (OUT / 'clips.json').write_text(json.dumps(info, indent=1))


if __name__ == '__main__':
    main()
