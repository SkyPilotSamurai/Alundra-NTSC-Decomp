"""BALANCE.BIN for the remake: remake/assets/balance.json.

Index = sprite table index (global sprites 0-255; 0x1F-0x7F are the items' slots,
items use index item+0x1E).  Each index has a chain of records by balance level
{level, hp, responses[11], attacks[[attribute, power], ...]}; an entity uses the
first record whose level >= the map's balance level (0x80044550).  attacks[a+1] is
the attack of animation a (attacks[0] when out of range).  Damage taken (0x8004464C):
r = responses[(attribute & 15) - 1]; r & 0xC0 == 0 -> max(1, power * r >> 4)
(power + equipped items' power when attribute & 0x80), 0x40 -> dies, 0x80 -> no effect."""
import json, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def chains(d):
    first = struct.unpack_from('<h', d, 0)[0]
    offs = [struct.unpack_from('<h', d, 2 * i)[0] for i in range(first // 2)]
    out = []
    for o in offs:
        chain = []
        while 0 <= o < len(d) - 3 and len(chain) < 64:
            level, size, hp = d[o], d[o + 1], d[o + 2]
            resp = list(d[o + 3:o + 14]); n = d[o + 14]
            attacks = [list(d[o + 15 + 2 * k:o + 17 + 2 * k]) for k in range(n)]
            chain.append({'level': level, 'hp': hp, 'responses': resp, 'attacks': attacks})
            if level >= 255 or size == 0: break
            o += size
        out.append(chain)
    return out


if __name__ == '__main__':
    d = (ROOT / 'private-inputs/disc/DATA/BALANCE.BIN').read_bytes()
    c = chains(d)
    (ROOT / 'remake/assets/balance.json').write_text(json.dumps(c))
    print(len(c), c[0][:1], c[1][:1])
