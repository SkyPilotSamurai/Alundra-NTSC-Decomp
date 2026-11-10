"""The shared script texts (DATAS.BIN block 0x59800-0x5B000: 128 u16 offsets, then the strings;
the game keeps it at *(0x801F4050)) -> remake/assets/text/global_strings.json.
Map texts are in maps/NNN/data.json 'strings' (tools/remake_extract_data.py).
    python tools/remake_export_texts.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from remake_export import session
from remake_extract_data import strings

BLOCK = 0x59800


def main():
    s = session()
    out = strings(s.data, BLOCK)
    f = ROOT / 'remake' / 'assets' / 'text' / 'global_strings.json'
    f.write_text(json.dumps({str(k): v for k, v in out.items()}, ensure_ascii=False, indent=0), encoding='utf-8')
    print('global strings', len(out))


if __name__ == '__main__':
    main()
