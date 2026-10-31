"""The Start menu's pictures (the game's main page and second page), driven by the ported
menu logic in engine/menu.py: which page is up, where every window is while it slides,
the cursor slot, the typing counters all live in g.mem exactly as in the game.  This module
only draws them (and runs the presentation routines the logic calls: the typing of names and
descriptions, the cursor's animation, the portrait), from the game's own art:
  windows   the layout tables in ALUN_CD.EXE (assets/ui/layouts) over WIND.TX (palettes 0-15)
  cursor    the pointing glove, 4 frames of 10 (WIND u 176/192/208/224, v 160, 16x16), nudged by
            0x800AA130 / 0x800AA140
  frames    the 24x32 corner brackets (WIND u 48, v 152) on the weapon / item in use
  digits    WIND u 8*d, v 40 (8x16)
  icons     the item pictures (global sprite record item + 0x1E)
  text      the menu font (FONT3), item names / descriptions from the disc's text (ETC_USA)."""
import json
from pathlib import Path
import pygame
from engine import menu as M, rodata as R

from home import ASSETS


class InventoryUI:
    def __init__(self, g):
        self.g = g
        self.sheets = {}; self.windows = {}
        lay = ASSETS / 'ui' / 'layouts' / 'layouts.json'
        self.layouts = {d['name']: d for d in json.loads(lay.read_text())} if lay.exists() else {}
        self.cursor_count = {}                       # cursor record -> its animation counter (+4)
        self.cursor_pos = {}
        et = ASSETS / 'text' / 'etc_usa.json'
        self.items = json.loads(et.read_text(encoding='utf-8')).get('items', {}) if et.exists() else {}
        self.reveal = {}                             # (page, line) -> pixels shown
        self.delay = {}
        self.portrait = None
        self.shaded = {}
        self.drawn = set()                           # pages whose windows the logic drew this frame

    def set_lang(self, lang):
        """Options > Dialogue & font: the item names / descriptions and the window texture (the JP
        WIND.TX / CL: its "more" marker and some palettes differ; its palettes 8-14 are empty, the
        JP code uses palette 0 where the US one used 8)."""
        self.lang = lang; self.sheets = {}; self.windows = {}; self.shaded = {}
        et = ASSETS / 'text' / 'etc_usa.json'
        self.items = json.loads(et.read_text(encoding='utf-8')).get('items', {}) if et.exists() else {}
        eu = getattr(self.g, 'eu_texts', lambda l: None)(lang) if lang not in ('us', 'jp') else None
        if eu:
            etc = eu['etc']['etc']
            self.items = {str(i): {'name': etc.get(str(0x200 + i), ''), 'description': etc.get(str(0x280 + i), ''),
                                   'description2': etc.get(str(0x300 + i), '')} for i in range(0x62)}
        if lang == 'jp':
            jt = getattr(self.g, 'jp_texts', lambda: None)()
            if jt:
                etc = jt['etc']['etc']
                self.items = {str(i): {'name': etc.get(str(0x200 + i), ''), 'description': etc.get(str(0x280 + i), ''),
                                       'description2': etc.get(str(0x300 + i), '')} for i in range(0x62)}

    # ------------------------------------------------------------------ art
    def sheet_us(self, pal):
        """The US texture whatever the language (the remake's own Options pages)."""
        k = ('us', pal)
        if k not in self.sheets:
            f = ASSETS / 'ui' / f'WIND_pal{pal:02d}.png'
            self.sheets[k] = pygame.image.load(str(f)).convert_alpha() if f.exists() else None
        return self.sheets[k]

    def sheet(self, pal):
        if pal not in self.sheets:
            jp = getattr(self, 'lang', 'us') == 'jp' and (ASSETS / 'ui' / 'jp' / 'WIND_pal00.png').exists()
            if jp and 8 <= pal <= 14: self.sheets[pal] = self.sheet(0); return self.sheets[pal]
            f = ASSETS / 'ui' / ('jp' if jp else '') / f'WIND_pal{pal:02d}.png'
            self.sheets[pal] = pygame.image.load(str(f)).convert_alpha() if f.exists() else None
        return self.sheets[pal]

    def window(self, cfg):
        """The window of config cfg (its layout table follows the x, y words) as a surface."""
        if cfg in self.windows: return self.windows[cfg]
        lay = self.layouts.get(f'{cfg + 4:08X}')
        surf = None
        if lay and lay['cells']:
            x0 = min(c['x'] for c in lay['cells']); y0 = min(c['y'] for c in lay['cells'])
            w = max(c['x'] + c['w'] for c in lay['cells']) - x0; h = max(c['y'] + c['h'] for c in lay['cells']) - y0
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            for c in lay['cells']:
                sh = self.sheet(c['pal'])
                if sh is not None: surf.blit(sh, (c['x'] - x0, c['y'] - y0), (c['u'], c['v'], c['w'], c['h']))
        self.windows[cfg] = surf
        return surf

    def pos(self, cfg):
        return self.g.mem.s16(cfg), self.g.mem.s16(cfg + 2)

    def draw_window(self, v, cfg):
        s = self.window(cfg)
        if s is not None: v.blit(s, self.pos(cfg))

    def digits(self, v, value, n, x, y, shade=0x80):
        sh = self.sheet(5)
        if sh is None: return
        if shade != 0x80: sh = self.shade_surface(('digits', shade), sh, shade)
        d = 10 ** (n - 1)
        for i in range(n):
            v.blit(sh, (x + 8 * i, y), (8 * ((value // d) % 10), 40, 8, 16)); d //= 10

    def icon(self, item):
        """0x8004F05C: the picture is image 0x80059958(item record +8) - a global sprite record's
        first image (-1 / an empty record: none)."""
        return self.g.hud.icon(item) if item and item > 0 else None

    def draw_icon(self, v, item, x, y, shade=0x80):
        """0x8004F05C: the picture's top left corner at (x, y).  shade: the sprite's colour (0x80 =
        as drawn; the main page sets 0x90, an eighth brighter, clamped like the PS1's GPU)."""
        img = self.icon(item)
        if img is None: return
        if shade != 0x80: img = self.shade_surface((item, shade), img, shade)
        v.blit(img, (x, y))

    def shade_surface(self, key, img, shade):
        """A sprite drawn with colour (shade, shade, shade): texel * shade / 0x80 per 5-bit channel,
        clamped at 31 (the GPU's texture modulation)."""
        out = self.shaded.get(key)
        if out is None:
            out = img.copy()
            try:
                import numpy as np
                a = pygame.surfarray.pixels3d(out)
                c5 = np.minimum(31, (a.astype(np.int32) >> 3) * shade >> 7)
                a[...] = (c5 << 3 | c5 >> 2).astype(np.uint8)
                del a
            except ImportError:
                pass
            self.shaded[key] = out
        return out

    def bracket(self, v, x, y):
        sh = self.sheet(5)
        if sh is not None: v.blit(sh, (x, y), (48, 152, 24, 32))

    def text(self, v, s, x, y, width=None):
        gf = self.g.game_font
        if not gf.ok or not s: return
        if width is None: gf.draw(v, s, x, y); return
        if width <= 0: return
        clip = v.get_clip(); v.set_clip(pygame.Rect(x, y, width, 16).clip(clip) if clip else pygame.Rect(x, y, width, 16))
        gf.draw(v, s, x, y); v.set_clip(clip)

    def name(self, item, part='name'):
        if item is None or item < 0: return ''
        return (self.items.get(str(item)) or {}).get(part, '') or ''

    # ------------------------------------------------------------------ which page
    def active(self):
        return bool(M.task_running(self.g, 6) or M.task_running(self.g, 4))

    def slot_item(self, k):
        """The item a main-page slot shows (0x80057D30 / the icons): -1 none."""
        g = self.g; it = g.mem.s32(M.SLOT_ITEM + 4 * k)
        if it == 0: return -1
        if it == -1:
            from engine import calls
            best = calls.call(g, g.mem.u32(M.SLOT_FN + 4 * k))
            return self._picked(k, best)
        return it if M.has_item(g, it) else -1

    def _picked(self, k, best):
        """(the remake's Mods > Magic & Weapon Swap) A group's slot shows the weapon / magic picked
        in that group instead of the group's best, so its picture and frame follow the choice."""
        g = self.g
        if best is None or best < 0 or not g.settings.get('magic_swap'): return best
        grp = lambda n: g.mem.s16(M.ITEM_REC + 10 * n)
        if k < 6:                                                   # weapons: the equipped group's pick
            w = M.equipped_kind(g)
            return w if w is not None and w >= 0 and grp(w) == grp(best) else best
        ch = g.mem.s16(g.mem.u32(M.STATS_PTR) + 0xC)                # items: the chosen one, if in this group
        return ch if ch >= 0 and M.has_item(g, ch) and grp(ch) == grp(best) else best

    def sub_item(self, k):
        """The item a second-page slot shows (0x800B6198: crests, armour / boots groups, key items)."""
        g = self.g; v = g.mem.s32(0x800B6198 + 4 * k)
        if v >= 0: return v if M.has_item(g, v) else -1
        if v >= -2: return M.best_of_group(g, g.mem.s32(0x800B6358 + 4 * (~v)))
        return getattr(self, 'key_items', [-1] * 5)[-3 - v]

    # ------------------------------------------------------------------ presentation routines
    def ui(self, addr, *args):
        g = self.g
        if addr == 0x80057A98: self.drawn.add('main')      # a main-page window put in this frame's list
        elif addr == 0x80054BF0: self.drawn.add('sub')     # a second-page window
        if addr == 0x80052070:                         # cursor at x, y
            rec, x, y = args[0], args[1], args[2]
            f = self.cursor_count.get(rec, 0) // 10
            self.cursor_pos[rec] = (x + R.s32(0x800AA130 + 4 * f), y + R.s32(0x800AA140 + 4 * f), f)
        elif addr == 0x800521D0:                       # its animation: 40 frames, 4 pictures
            rec = args[0]; c = self.cursor_count.get(rec, 0) + 1
            self.cursor_count[rec] = 0 if c == 0x28 else c
        elif addr == 0x80057D30: self.typing('main')
        elif addr == 0x80055AFC: self.typing('sub')
        elif addr == 0x800545E8:                       # second page: the first five key items (group 0x1C)
            ks = []; n = 0
            for i in range(5):
                if n != -1: n = M.next_in_group(g, n + 1, 0x1C)
                ks.append(n)
            self.key_items = ks
        elif addr == 0x80059958: return 0
        return 0

    def typing(self, page):
        """0x80057D30 / 0x80055AFC: the slot's name types in (one letter every 3 frames), stays
        60 frames, then the description's two lines type in.  The counter is the game's
        (0x801531B4 / 0x801E68D8), reset by the logic when the cursor moves."""
        g = self.g; m = g.mem
        cnt, dly = (M.INV_TEXT, 0x801531B8) if page == 'main' else (0x801E68D8, 0x801E68DC)
        item = self.slot_item(m.s32(M.INV_SLOT)) if page == 'main' else self.sub_item(m.s32(M.SUB_SLOT))
        self.cur_item = item; self.cur_page = page
        if item is None or item < 0: self.lines = None; return
        c = m.s32(cnt)
        name, d1, d2 = self.name(item), self.name(item, 'description'), self.name(item, 'description2')
        def advance(line, ch):
            if m.s32(dly): m.w32(dly, m.s32(dly) - 1); return
            m.w32(dly, 2); m.w32(cnt, m.s32(cnt) + 1)
            self.reveal[line] = self.reveal.get(line, 0) + self.g.game_font.width(ch)
        if c == 0:
            self.lines = [name, None]; m.w32(dly, 0); self.reveal = {0: 0, 1: 0}; m.w32(cnt, 1); return
        if 1 <= c <= 0x10:
            if c - 1 >= len(name): m.w32(cnt, 0x11)
            else: advance(0, name[c - 1])
            self.lines = [name, None]; return
        if 0x11 <= c < 0x4D:
            m.w32(cnt, c + 1)
            if page == 'sub': self.reveal[0] = len(name) * 8          # the second page shows the whole name
            self.lines = [name, None]; return
        if c == 0x4D:
            self.lines = [d1, None]; m.w32(dly, 0); self.reveal = {0: 0, 1: 0}; m.w32(cnt, c + 1); return
        if 0x4E <= c < 0x8E:
            if c - 0x4E >= len(d1): m.w32(cnt, 0x8E)
            else: advance(0, d1[c - 0x4E])
            self.lines = [d1, None]; return
        if c == 0x8E:
            self.lines = [d1, d2]; m.w32(dly, 0); self.reveal[1] = 0; m.w32(cnt, c + 1); return
        if 0x8F <= c < 0xCF:
            k = c - 0x8F if page == 'main' else c - 0x90 + 1
            if c - 0x8F >= len(d2): m.w32(cnt, 0xCF)
            else: advance(1, d2[c - 0x8F])
            self.lines = [d1, d2]; return
        self.lines = [d1, d2]

    # ------------------------------------------------------------------ drawing
    def draw(self, v):
        """Only what the page's frame routine drew this frame (the game shows its windows through
        the sprite lists that routine fills; the frame a page starts it fills none yet)."""
        if M.task_running(self.g, 6) and 'main' in self.drawn: self.draw_main(v)
        elif M.task_running(self.g, 4) and 'sub' in self.drawn: self.draw_sub(v)

    def draw_cursor(self, v, rec):
        p = self.cursor_pos.get(rec)
        sh = self.sheet(0)
        if p is None or sh is None: return
        x, y, f = p
        v.blit(sh, (x, y), (176 + 16 * f, 160, 16, 16))

    def draw_text_lines(self, v):
        lines = getattr(self, 'lines', None)
        if not lines: return
        x, y = self.pos(0x8009EE24)
        for i, s in enumerate(lines):
            if s: self.text(v, s, x + 0x10, y + 12 + 16 * i, self.reveal.get(i, 0))

    def draw_main(self, v):
        g = self.g; m = g.mem
        for cfg in (0x800B7710, 0x800BA1C8, 0x800BAD18, 0x800BB868, 0x800BBCC0, 0x8009EE24):
            self.draw_window(v, cfg)
        ox, oy = self.pos(0x800B7710)
        weapon = M.equipped_kind(g); chosen = M.selected_item(g)
        for k in range(24):
            it = self.slot_item(k)
            if it < 0: continue
            x, y = ox + R.s32(0x800BBD90 + 4 * k), oy + R.s32(0x800BBDF0 + 4 * k)
            if (k < 6 and it == weapon) or (k >= 6 and it == chosen): self.bracket(v, x, y)
            self.draw_icon(v, it, x, y, 0x90)
            if k == 6:                                              # herbs: how many
                self.digits(v, M.has_item(g, it) % 10, 1, x + 0x10, y + 0x10, 0x90)
        bx, by = self.pos(0x800BAD18); self.text(v, self.name(weapon), bx + 0x10, by + 8)
        ix, iy = self.pos(0x800BB868); self.text(v, self.name(chosen), ix + 0x10, iy + 8)
        nx, ny = self.pos(0x800BBCC0)
        self.digits(v, max(0, g.gilder), 4, nx + 0x18, ny + 4)
        self.digits(v, max(0, (self._stat(0x10) + self._stat(0xE))) % 100, 2, nx + 0x28, ny + 0x1C)
        self.digits(v, M.has_item(g, 0x3D) % 100, 2, nx + 0x28, ny + 0x34)
        self.draw_text_lines(v)
        if not m.s32(M.INV_FLAGS) & 6: self.draw_cursor(v, 0x801531C0)

    def _stat(self, off): return self.g.mem.s16(self.g.mem.u32(M.STATS_PTR) + off)

    def draw_sub(self, v):
        g = self.g; m = g.mem
        for cfg in (0x800B14CC, 0x800B2544, 0x800B3094, 0x800B3BE4, 0x800B46E4, 0x8009EE24, 0x800BBCC0):
            self.draw_window(v, cfg)
        wx, wy = self.pos(0x800B14CC)
        for i in range(7):                                          # the crests
            it = m.s32(0x800B6144 + 4 * i)
            if M.has_item(g, it):
                self.draw_icon(v, it, wx + R.s32(0x800B6160 + 4 * i), wy + R.s32(0x800B617C + 4 * i))
        kx, ky = self.pos(0x800B2544)
        for i, it in enumerate(getattr(self, 'key_items', [])):     # key items
            if it is not None and it >= 0: self.draw_icon(v, it, kx + 32 * i + 8, ky + 4)
        ex, ey = self.pos(0x800B46E4)
        for i, cfg in enumerate((0x800B3094, 0x800B3BE4)):          # armour, boots
            it = M.best_of_group(g, m.s32(0x800B6358 + 4 * i))
            if it != -1:                                            # 0x80054938: picture and frame
                self.bracket(v, ex + 8, ey + 0x18 + 0x28 * i)
                self.draw_icon(v, it, ex + 8, ey + 0x18 + 0x28 * i)
                nx, ny = self.pos(cfg); self.text(v, self.name(it), nx + 0x10, ny + 8)
        nx, ny = self.pos(0x800BBCC0)
        self.digits(v, max(0, g.gilder), 4, nx + 0x18, ny + 4)
        self.digits(v, max(0, (self._stat(0x10) + self._stat(0xE))) % 100, 2, nx + 0x28, ny + 0x1C)
        self.digits(v, M.has_item(g, 0x3D) % 100, 2, nx + 0x28, ny + 0x34)
        self.draw_text_lines(v)
        if not m.s32(M.SUB_FLAGS) & 6: self.draw_cursor(v, 0x801E6854)

    def tick(self):
        """Once a game frame (not a drawn frame): the portrait's 15-step flight."""
        pt = self.portrait
        if pt is None: return
        if pt['step'] > 0: pt['step'] -= 1
        elif pt['state'] == 'out': self.portrait = None

    def draw_portrait(self, v):
        """Alundra's portrait in the menu's corner (0xF8, 0x68), flying in / out over 15 frames
        (0x80059A78 / 0x800599A4)."""
        pt = self.portrait
        if pt is None: return
        img = self.g.__dict__.get('_alundra_portrait')
        if img is None:
            f = ASSETS / 'sprites' / 'global' / '000' / 'portrait.png'
            img = pygame.image.load(str(f)).convert_alpha() if f.exists() else False
            self.g.__dict__['_alundra_portrait'] = img
        if not img: return
        k = pt['step']
        p = self.g.player; cam = self.g.camera()
        sx = int(p.wx) + 2 - cam[0]; sy = int(p.wy) + self.g.map.margin - int(p.z) - cam[1] - 32
        if pt['state'] == 'in': t = 0xF - k; x = 0xF8 + (sx - 0xF8) * k // 0xF; y = 0x68 + (sy - 0x68) * k // 0xF
        else: t = k; x = sx + (0xF8 - sx) * k // 0xF; y = sy + (0x68 - sy) * k // 0xF
        w, h = 0x30 * t // 0xF, 0x38 * t // 0xF
        if w > 0 and h > 0:
            v.blit(img if (w, h) == img.get_size() else pygame.transform.scale(img, (w, h)), (x, y))
