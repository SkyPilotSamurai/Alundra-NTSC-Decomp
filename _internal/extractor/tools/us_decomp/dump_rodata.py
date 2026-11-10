"""Copy the data parts of the US ALUN_CD.EXE (tables the gameplay code reads: directions,
animation flags, weapon records, sound and dust tables, program tables...) from the
user's own disc files into remake/assets/exe_data.bin.  Code is left out (zeroed).
python3 dump_rodata.py"""
import os, sys, json, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
import exe_dis as E

FIRST_CODE = 0x8002ABE8          # first function
LAST_CODE = 0x8009AA10 + 0x200   # PsyQ code ends just after the last prologue (checked below)


def code_end():
    """End of the code: the last 'jr ra' near the last prologue."""
    p = 0x8009AA10
    while p < E.BASE + E.SIZE:
        if E.word(p) == 0x03E00008: last = p + 8
        if p > 0x8009AA10 + 0x2000: break
        p += 4
    return last


def main():
    end = code_end()
    img = bytearray(E.D[0x800:0x800 + E.SIZE])
    for a in range(FIRST_CODE, end): img[a - E.BASE] = 0
    out = os.path.join(ROOT, 'remake', 'assets', 'exe_data.bin')
    open(out, 'wb').write(bytes(img))
    meta = {'base': E.BASE, 'size': E.SIZE, 'code': [FIRST_CODE, end],
            'source': 'ALUN_CD.EXE (SLUS-00553), data only'}
    open(out.replace('.bin', '.json'), 'w').write(json.dumps(meta, indent=1))
    print('wrote', out, hex(E.BASE), hex(E.SIZE), 'code', hex(FIRST_CODE), hex(end))


if __name__ == '__main__':
    main()
