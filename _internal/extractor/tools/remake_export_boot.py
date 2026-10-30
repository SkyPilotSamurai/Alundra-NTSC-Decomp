"""The boot program's data for the remake's History Book (remake/history_book.py):
SLUS_005.53's image (load address 0x80020000) with its code (0x80021610 .. 0x80042DDC) zeroed -
the texts, the glyph table, the picture archive (TIMs at 0x800438A8), the scene tables - into
remake/assets/boot/slus_data.bin.  The remake runs its own ports of the routines over it.
Run: python tools/remake_export_boot.py"""
import json, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / 'private-inputs' / 'disc' / 'SLUS_005.53'
OUT = ROOT / 'remake' / 'assets' / 'boot'
CODE = (0x80021610, 0x80042DDC)


def main():
    d = EXE.read_bytes()
    base, size = struct.unpack_from('<II', d, 0x18)
    img = bytearray(d[0x800:0x800 + size])
    img[CODE[0] - base:CODE[1] - base] = bytes(CODE[1] - CODE[0])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'slus_data.bin').write_bytes(bytes(img))
    (OUT / 'slus_data.json').write_text(json.dumps({'base': base, 'size': size, 'code_zeroed': list(CODE),
                                                    'source': 'SLUS_005.53 (boot program), data only'}, indent=1))
    print('wrote', OUT / 'slus_data.bin', hex(base), hex(size))


if __name__ == '__main__':
    main()
