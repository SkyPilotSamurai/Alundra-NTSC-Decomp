"""Export every map's portals (doors / exits) for the remake: remake/assets/maps/NNN/warps.json.
Record format: tools/portal_records.py (xcasadio DatasBin/Portal.cs). Run: python tools/remake_export_warps.py [first last]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from remake_export import session, OUT
from portal_records import Portal

def warps(session, m):
    # same reading as warp_editor.warps (kept here so tkinter is not needed)
    base, h = session.layout(m); start = base + h[0] + 0x42c
    out = []
    for i in range(64):
        o = start + i * 12; p = Portal.read(session.data, o)
        if (p.x1, p.y1, p.x2, p.y2) == (0, 0, 255, 255) or p.destination_map < 0: continue
        out.append((i, o, p))
    return out

def main(a=0, b=483):
    s = session(); n = 0
    for m in range(a, b):
        folder = OUT / 'maps' / f'{m:03d}'
        if not folder.exists(): continue
        try: rows = warps(s, m)
        except Exception as exc: rows = []; print(m, exc)
        out = [{'index': i, 'rect': [p.x1, p.y1, p.x2, p.y2], 'map': p.destination_map, 'x': p.destination_x,
                'y': p.destination_y, 'z': p.z, 'flags': p.flags,
                'facing': (p.flags >> 14) & 3, 'arrive_facing': (p.flags >> 12) & 3} for i, o, p in rows]
        (folder / 'warps.json').write_text(json.dumps(out)); n += 1
    print('maps', n)

if __name__ == '__main__':
    main(*[int(x) for x in sys.argv[1:3]])
