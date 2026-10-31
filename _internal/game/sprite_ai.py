"""Built-in sprite programs: the A/C/D/E/F program a sprite header names when the map record
gives no script for that slot.  0x80039198 calls (*(table[slot]))[Entity.builtin[slot]](entity);
the tables are A 0x800C699C, C 0x800C6D9C, D 0x800C719C, E 0x800C759C, F 0x800C799C (US v1.1
ALUN_CD.EXE) and every entry is ported in engine/ai_g*.py.  Contents and destroying go through
engine/drops.py (0x80033154, 0x8003AEE4)."""
import json
from pathlib import Path

try:                                     # ported programs that passed tools/us_decomp/check_ai.py
    VERIFIED = set(json.loads((Path(__file__).resolve().parent / 'engine' / 'ai_verified.json').read_text()))
except Exception:
    VERIFIED = None
BUILTIN_TABLES = {'A': 0x800C699C, 'C': 0x800C6D9C, 'D': 0x800C719C, 'E': 0x800C759C, 'F': 0x800C799C}


class SpriteAI:
    def __init__(self, game, assets):
        self.g = game

    def init_contents(self, a, rec, header):
        """InitializeContents 0x80033154 (engine/drops.py): the record's contents unless its
        collection flag is set, else the sprite header's."""
        from engine import drops
        a.record = rec; a.header_contents = (header or {}).get('contents', 0)
        drops.init_contents(self.g, a)

    def destroy(self, a, effect=-1):
        """DestroyEntity 0x8003AEE4 (engine/drops.py): contents, status 4, the break effect."""
        from engine import drops
        drops.destroy_entity(self.g, a, effect)

    def builtin(self, a, slot):
        return 0 if (a.programs.get(slot, 0) & 0x7F) else (getattr(a, 'sprite_programs', {}) or {}).get(slot, 0)

    def ported(self, slot, n):
        """The port of table entry n of a slot (None if not checked against the game yet)."""
        t = BUILTIN_TABLES.get(slot)
        if t is None or not (0 <= n < 256): return None
        from engine import rodata, calls
        a = rodata.u32(t + 4 * n)
        if VERIFIED is not None and f'{a:08X}' not in VERIFIED: return None
        return calls.resolve(a)

    def has(self, a, slot):
        return not (a.programs.get(slot, 0) & 0x7F) and self.ported(slot, self.builtin(a, slot)) is not None

    def run(self, a, slot):
        if a.programs.get(slot, 0) & 0x7F: return False
        f = self.ported(slot, self.builtin(a, slot))
        if f is None: return False
        f(self.g, a); return True
