"""Item tables for the remake: remake/assets/items.json.

random: 0x80028E0C-style table (found by pattern in the US EXE): contents id with bit 0x80
picks one of 16 entries of row (id & 0x7F) (ChooseRandomlyAnItem).
props[item] = [timed (field1: dropped copies vanish after 600 frames), pickup sound, kind
(field3 & 0x7F: 1 weapon, 2 armour, 3 ring), field4] (g_itemDropProperties 0x800C5F7C,
values from the MIT xcasadio project)."""
import json, struct
from pathlib import Path
from exe_dis import D
ROOT = Path(__file__).resolve().parents[1]
pat = bytes([0x24, 0x25, 0x45, 0x46, 0x47, 0x48, 0x4F, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56])
i = D.find(pat) - 16
table = list(D[i:i + 128 * 16])
props = json.loads((ROOT / 'tools/item_props_raw.json').read_text())
out = {'random': table, 'props': [[p[1], p[2], p[3] & 0x7F, p[4]] for p in props]}
(ROOT / 'remake/assets/items.json').write_text(json.dumps(out))
print(hex(i - 0x800 + 0x80020000), table[16:40])
