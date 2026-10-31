"""Draws the message window and the speaker's name plate from the state the ported logic
(engine/message.py) keeps in g.mem - the way the game's sprites show it:
  * the window: layout 0x8009EE28 over WIND.TX at the window's current place (it slides);
  * the text: three 256 x 16 line pictures (the VRAM rows 0x120 + 16 * ring that 0x80048780
    writes letter by letter, palette 8), each at its sprite's x / y (0x8010748C), clipped to
    the window's text area (0x80047EC0);
  * the "more" marker (0x80107504, WIND u / v from 0x800A7740, palette 8);
  * the name plate: layout 0x800A7728 and the name centred in it (0x8005C588)."""
import pygame
from engine import message as M, menu as EM

ROWS = (0x120, 0x130, 0x140)
JP_ROWS = (0x140, 0x150)                         # JP: two line rows (ring of 2); the name plate 0x160


class MessageUI:
    def __init__(self, g, inv):
        self.g = g; self.inv = inv
        self.buf = pygame.Surface((256, 16), pygame.SRCALPHA)
        self.rows = {y: pygame.Surface((256, 16), pygame.SRCALPHA) for y in (0x120, 0x130, 0x140, 0x150, 0x160, 0x170)}
        self.kanji = None
        self.name = None
        self.vrows = {}                              # VRAM text rows 0x120 + 16 * row (by the sprites' v)

    # ---- the drawing calls the logic makes (g.ui)
    def glyph(self, surf, ch, x):
        gf = self.g.game_font
        if not gf.ok: return
        w = gf.glyph_width(chr(ch))
        surf.fill((0, 0, 0, 0), pygame.Rect(x, 0, w, 16))
        info = gf.chars.get(ch)
        if info is not None and w > 0:
            surf.blit(gf.sheet, (x, 0), (info['u'], info['v'], w, 16))

    def jp(self): return getattr(self.g, 'lang', 'us') == 'jp'

    def font_jp(self):
        if self.kanji is None:
            from jp_text import KanjiFont
            self.kanji = KanjiFont()
        return self.kanji

    def ui(self, addr, *args):
        if addr == 'jp_glyphs':                      # JP 0x80051614: glyphs into a VRAM row
            data, vx, vy = args[:3]
            row = self.rows.get(vy)
            if row is not None:
                kf = self.font_jp(); codes = kf.pairs(bytes(data))
                x = (vx - 0x3C0) * 4
                row.fill((0, 0, 0, 0), pygame.Rect(x, 0, 16 * len(codes), 16))
                row.blit(kf.mask(codes), (x, 0))
            return 0
        if addr == 0x80048780:                       # a letter into the line buffer, then uploaded
            s, _buf, _vx, vy, pen = args[:5]
            ch = s.data[0] if hasattr(s, 'data') and s.data else 0x20
            self.glyph(self.buf, ch, pen)
            row = self.rows.get(vy)
            if row is not None: row.fill((0, 0, 0, 0)); row.blit(self.buf, (0, 0))
            return 0
        if addr == 0x800845E8:                       # the line buffer cleared
            if args and args[0] == M.LINEBUF: self.buf.fill((0, 0, 0, 0))
            return 0
        if addr == 0x80087764:                       # ClearImage of text rows
            r = getattr(args[0], 'rect', None) if args else None
            if r:
                for y, s in self.rows.items():
                    if r[1] <= y < r[1] + r[3]: s.fill((0, 0, 0, 0))
            return 0
        if addr == 0x800482A0:                       # a whole string into a VRAM text row (draw_text)
            prims, ptr = args[0], args[1]; m = self.g.mem
            row = args[5] if len(args) > 5 else 0
            if row >= 4: row += 1                    # (row 4 is kept for something else)
            text = bytearray()
            while m.u8(ptr + len(text)) and len(text) < 0x80: text.append(m.u8(ptr + len(text)))
            if self.jp():                            # JP 0x80049048: padded with "　" to 16, cut to n
                kf = self.font_jp(); n = args[2] if len(args) > 2 else 16
                codes = kf.pairs(bytes(text))
                codes += [0x8140] * max(0, 16 - len(codes))
                codes = codes[:n if 0 < n < 16 else 16]
                surf = kf.bake(kf.mask(codes))
                self.vrows[(row * 16 + 0x20) & 0xFF] = surf
                if prims == M.NAME_PRIMS: self.name = surf
                return 0
            surf = pygame.Surface((256, 16), pygame.SRCALPHA); x = 0
            for c in text:
                self.glyph(surf, c, x); x += self.g.game_font.glyph_width(chr(c)) + M.gap(self.g)
            self.vrows[(row * 16 + 0x20) & 0xFF] = surf
            if prims == M.NAME_PRIMS: self.name = surf
            return 0
        return 0

    # ---- every drawn frame
    def draw(self, v):
        g = self.g; m = g.mem
        b = m.s32(M.BUFI) & 1
        if self.jp(): return self.draw_jp(v, b)
        if EM.task_running(g, 0):
            cfg = M.CFG
            self.inv.draw_window(v, cfg)
            cx, cy = m.s16(cfg), m.s16(cfg + 2)
            y0 = min(cy + 5 - 1, 0xEF); h = min(6 * 8 + 2, 0xF0 - y0)
            clip = pygame.Rect(cx + 16, y0, 0x20 * 8 + 2, h)
            linked = getattr(g, 'sw_linked', None)
            if m.s32(M.ARROW) and (linked is None or 'arrow' in linked):
                p = M.ARROWP + b * 0x14
                sh = self.inv.sheet(8)
                if sh is not None:
                    v.blit(sh, (m.s16(p + 8), m.s16(p + 0xA)), (m.u8(p + 0xC), m.u8(p + 0xD), 16, 16))
            old = v.get_clip(); v.set_clip(clip.clip(old) if old else clip)
            for r in range(3):
                p = M.PRIMS + b * 0x14 + r * 0x28
                v.blit(self.rows[ROWS[r]], (m.s16(p + 8), m.s16(p + 0xA)))
            v.set_clip(old)
        if EM.task_running(g, 0xC):
            cfg = M.NAME_CFG
            self.inv.draw_window(v, cfg)
            if self.name is not None:
                cx, cy = m.s16(cfg), m.s16(cfg + 2)
                x0 = min(cx + 0x10, 0x140); w = 0x20 * 8 + 2
                if x0 + w >= 0x140: w = 0x140 - x0
                clip = pygame.Rect(x0, cy + 8, max(0, w), 4 * 8 + 2)
                p = M.NAME_PRIMS + b * 0x14
                old = v.get_clip(); v.set_clip(clip.clip(old) if old else clip)
                v.blit(self.name, (m.s16(p + 8), m.s16(p + 0xA)))
                v.set_clip(old)

    def draw_jp(self, v, b):
        """JP: the window, its two lines (each drawn twice: palette 0 one pixel up, then palette 1;
        clip (cfg.x + 16, cfg.y + 11, 258, 34): JP 0x80048C60 with the task record (16, 12, 32,
        4)), the marker (palette 0) and the name plate (the same two copies, left-aligned)."""
        g = self.g; m = g.mem; kf = self.font_jp()
        if EM.task_running(g, 0):
            cfg = M.CFG
            self.inv.draw_window(v, cfg)
            cx, cy = m.s16(cfg), m.s16(cfg + 2)
            rx, ry, rw, rh = M.JP_REC
            y0 = min(cy + ry - 1, 0xEF); h = min(rh * 8 + 2, 0xF0 - y0)
            clip = pygame.Rect(cx + rx, y0, rw * 8 + 2, max(0, h))
            linked = getattr(g, 'sw_linked', None)
            if m.s32(M.ARROW) and (linked is None or 'arrow' in linked):
                p = M.ARROWP + b * 0x14
                sh = self.inv.sheet(0)
                if sh is not None:
                    v.blit(sh, (m.s16(p + 8), m.s16(p + 0xA)), (m.u8(p + 0xC), m.u8(p + 0xD), 16, 16))
            old = v.get_clip(); v.set_clip(clip.clip(old) if old else clip)
            for ring in range(2):
                p = M.PRIMS + b * 0x14 + ring * 0x28
                v.blit(kf.bake(self.rows[JP_ROWS[ring]]), (m.s16(p + 8), m.s16(p + 0xA) - 1))
            v.set_clip(old)
        if EM.task_running(g, 0xC):
            cfg = M.NAME_CFG
            self.inv.draw_window(v, cfg)
            if self.name is not None:
                cx, cy = m.s16(cfg), m.s16(cfg + 2)
                x0 = min(cx + 0x10, 0x140); w = 0x20 * 8 + 2
                if x0 + w >= 0x140: w = 0x140 - x0
                clip = pygame.Rect(x0, cy + 8, max(0, w), 4 * 8 + 2)
                p = M.NAME_PRIMS + b * 0x14
                old = v.get_clip(); v.set_clip(clip.clip(old) if old else clip)
                v.blit(self.name, (m.s16(p + 8), m.s16(p + 0xA) - 1))
                v.set_clip(old)

    def text_sprite(self, v, p):
        """A draw_text sprite (SPRT 255 x 16: +8 x, +0xA y, +0xD the row's v) as the logic left it."""
        m = self.g.mem
        surf = self.vrows.get(m.u8(p + 0xD))
        if surf is not None: v.blit(surf, (m.s16(p + 8), m.s16(p + 0xA) - (1 if self.jp() else 0)))
