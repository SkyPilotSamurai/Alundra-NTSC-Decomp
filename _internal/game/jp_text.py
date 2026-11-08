"""The Japanese release's text drawing (Options > Dialogue & font: JP).

The JP game has no font file: every character is a Shift-JIS code drawn from the PS1 BIOS kanji
ROM (Krom2RawAdd), 16 x 15 pixels at one bit, expanded to 4 bpp with ink = palette index 1 (JP
0x80051594 / 0x80051614); a code the ROM lacks prints "？" (0x8148).  tools/remake_export_jp.py
writes the ROM's glyphs to assets/ui/jp/kanji.png.  Each text sprite is drawn twice (JP msg_draw
0x8004770C, draw_text 0x80049048): palette 0 index 1 one pixel higher, behind, then palette 1
index 1 on top - JP WIND.CL 0x10C8 and 0x258F - so the letters get a dark top edge."""
import json
from pathlib import Path
import pygame

from home import ASSETS
INK = (120, 96, 72)                     # JP WIND.CL palette 1 index 1 = 0x258F
EDGE = (64, 48, 32)                     # JP WIND.CL palette 0 index 1 = 0x10C8
QUESTION = 0x8148                       # "？": what a missing code prints
SPACE = '　'


class KanjiFont:
    def __init__(self):
        d = ASSETS / 'ui' / 'jp'
        self.ok = (d / 'kanji.png').exists() and (d / 'kanji.json').exists()
        self.cache = {}
        if not self.ok: return
        meta = json.loads((d / 'kanji.json').read_text())
        self.cols = meta['columns']; self.codes = {int(k, 16): v for k, v in meta['codes'].items()}
        self.sheet = pygame.image.load(str(d / 'kanji.png'))
        try: self.sheet = self.sheet.convert_alpha()
        except pygame.error: pass

    @staticmethod
    def pairs(data):
        """A Shift-JIS byte string as 2-byte codes, as the JP code steps through it (no single-byte
        characters: every character is two bytes)."""
        out = []; i = 0
        while i < len(data) and data[i]:
            out.append(data[i] << 8 | (data[i + 1] if i + 1 < len(data) else 0)); i += 2
        return out

    def mask(self, codes):
        """White glyphs (16 px apart) on a transparent strip, 16 high."""
        surf = pygame.Surface((max(1, 16 * len(codes)), 16), pygame.SRCALPHA)
        if not self.ok: return surf
        for i, c in enumerate(codes):
            n = self.codes.get(c, self.codes.get(QUESTION))
            if n is None: continue
            surf.blit(self.sheet, (16 * i, 0), ((n % self.cols) * 16, (n // self.cols) * 16, 16, 16))
        return surf

    @staticmethod
    def tint(mask, colour):
        s = mask.copy(); s.fill(colour + (255,), special_flags=pygame.BLEND_RGBA_MULT); return s

    def bake(self, mask):
        """The two copies the JP code draws: EDGE one pixel up, INK over it.  The surface is one
        pixel taller and is blitted at (x, y - 1)."""
        w, h = mask.get_size()
        out = pygame.Surface((w, h + 1), pygame.SRCALPHA)
        out.blit(self.tint(mask, EDGE), (0, 0)); out.blit(self.tint(mask, INK), (0, 1))
        return out

    def text(self, s):
        """A Python string as a baked strip (cached)."""
        hit = self.cache.get(s)
        if hit is None:
            wide = ''.join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else SPACE if c == ' ' else c for c in s)
            data = b''.join(c.encode('shift_jis') if self._sjis(c) else b'\x81\x48' for c in wide)
            hit = self.bake(self.mask(self.pairs(data)))
            if len(self.cache) > 512: self.cache.clear()
            self.cache[s] = hit
        return hit

    @staticmethod
    def _sjis(c):
        try: return len(c.encode('shift_jis')) == 2
        except UnicodeEncodeError: return False

    def draw(self, surf, s, x, y):
        surf.blit(self.text(s), (x, y - 1))

    @staticmethod
    def width(s): return 16 * len(s)


def is_jp_text(s):
    return any(ord(c) > 0xFF for c in s)
