"""Each map's DATAS.BIN block size (what the game reads from the CD on a map change, 0x80083F04
in the main loop 0x8002C494) for the remake's loading pause: remake/assets/maps/map_sizes.json.
Run: python tools/remake_export_map_sizes.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from remake_export import session, OUT
from map_slots import block_range, map_count


def main():
    s = session(); out = {}
    for m in range(map_count(s.data)):
        a, b = block_range(s.data, m); out[str(m)] = b - a
    (OUT / 'maps').mkdir(parents=True, exist_ok=True)
    (OUT / 'maps' / 'map_sizes.json').write_text(json.dumps(out))
    print('maps', len(out))


if __name__ == '__main__':
    main()
