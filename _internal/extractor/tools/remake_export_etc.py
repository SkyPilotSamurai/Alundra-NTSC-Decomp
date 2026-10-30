"""Copy DATA/ETC_USA.R (the US texts: chapter names, the save menu, item and speaker names)
from the disc image into remake/assets/text/ETC_USA.R, which the remake loads at 0x8012B9E0 as
the game's boot does (0x8002C810).  The disc image is the .bin next to this folder's root (a
MODE2/2352 track) or private-inputs/disc/DATA/ETC_USA.R when the files are already extracted.
Run: python tools/remake_export_etc.py [path/to/disc.bin]"""
import struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'remake' / 'assets' / 'text' / 'ETC_USA.R'


class Iso:
    def __init__(self, path): self.f = open(path, 'rb')

    def sector(self, n):
        self.f.seek(n * 2352); return self.f.read(2352)[24:24 + 2048]

    def extent(self, lba, size):
        out = bytearray()
        for i in range((size + 2047) // 2048): out += self.sector(lba + i)
        return bytes(out[:size])

    def entries(self, lba, size):
        d = self.extent(lba, size); i = 0
        while i < len(d):
            n = d[i]
            if n == 0: i = (i // 2048 + 1) * 2048; continue
            e = d[i:i + n]
            yield e[33:33 + e[32]].split(b';')[0].decode(errors='replace'), struct.unpack_from('<I', e, 2)[0], struct.unpack_from('<I', e, 10)[0]
            i += n

    def read(self, path):
        root = self.sector(16)[156:156 + 34]
        lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
        for part in path.split('/'):
            for name, l, s in self.entries(lba, size):
                if name.upper() == part.upper(): lba, size = l, s; break
            else: raise FileNotFoundError(path)
        return self.extent(lba, size)


def main():
    src = ROOT / 'private-inputs' / 'disc' / 'DATA' / 'ETC_USA.R'
    if len(sys.argv) > 1: data = Iso(sys.argv[1]).read('DATA/ETC_USA.R')
    elif src.exists(): data = src.read_bytes()
    else:
        bins = sorted(ROOT.glob('*.bin'))
        if not bins: sys.exit('no disc image found')
        data = Iso(bins[0]).read('DATA/ETC_USA.R')
    OUT.write_bytes(data)
    print('wrote', OUT, len(data), 'bytes')


if __name__ == '__main__':
    main()
