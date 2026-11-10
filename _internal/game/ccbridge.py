"""CROWD CONTROL (Randomizer > Seeds > Crowd Control): runs Alundra_CC_Bizhawk.lua, the script BizHawk runs, unchanged.
The chat bot (Alundra_Crowd_Control.py) writes a command to _internal/command.txt; the script reads it each frame,
acts on the game's memory and draws its text.  It sees the BizHawk functions it uses (memory, joypad, gui, emu) on
the port's memory and objects; one emu.frameadvance is one game frame, run where the Archipelago connector runs
(before the game frame reads the pad), as BizHawk runs it between frames.  With a Twitch channel the chat bot runs
alongside (ccbot.py), and the Points Display window when it is on; both stop with the seed."""
import atexit, subprocess, sys
from home import HOME, CODE

TOOL = CODE.parent / 'randomizer'
CC = TOOL / 'crowd_control'                     # the CC bot's own folder: its programs, the BizHawk script, item_sprites


def cc_text(t, lang):
    """randomizer/lang_text.py's CC line in this language (loaded once)."""
    global _lang
    if _lang is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location('lang_text', TOOL / 'lang_text.py'); _lang = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_lang)
    return _lang.cc_text(t, lang)


_lang = None
SCRIPT = 'Alundra_CC_Bizhawk.lua'
ENT0 = 0x1AC6F8                                  # the Entity table's slot 0: Alundra (engine/layout.py)
HP_X = 152                                       # the HP pips and '/NN' (x 0x78-0xB8, Hud.draw_life): their centre
TOP_Y = 1                                        # the script's top-row texts (y 0; 1 keeps the outline on screen)
VBLANK = 0x0CB54C                               # the VSync count (u32; the port's Game.VBLANKS)

SETUP = r'''
local py = ...
memory = {readbyte = py.r8, read_u8 = py.r8, writebyte = py.w8, write_u8 = py.w8,
          write_u16_be = function(a, v) py.w8(a, (v >> 8) & 0xFF); py.w8(a + 1, v & 0xFF) end}
mainmemory = memory
emu = {framecount = py.frames, frameadvance = coroutine.yield, message = function() end, getsystemid = function() return "PSX" end}
gui = {drawText = py.text}
alundra_pc = {spawn_enemy = py.spawn}       -- (the port's own commands: not in BizHawk)
joypad = {get = py.pad}
print = function() end
local open = io.open
io.open = function(name, mode) return open(py.path(name), mode) end
'''


def command_file():
    return CC / '_internal' / 'command.txt'            # (where the bot writes it: its folder's _internal/command.txt)


class CrowdControl:
    def __init__(self, border=False, channel='', points=False, buffed=False, free=False, earn=0, **_):
        import lupa.lua54 as L
        from engine import layout, mem
        self.border = bool(border); self.g = None; self.frame = 0; self.lines = []; self.failed = None
        self.file = command_file()
        self.file.parent.mkdir(exist_ok=True)
        if not self.file.exists(): self.file.write_text('', encoding='utf-8')   # (the script stops when it cannot open it)
        self.ent = {}                                                         # byte offset -> (name, base, size, signed)
        for name, (o, t) in layout.ENTITY.items():
            n = mem._SZ.get(t, 4)
            for k in range(n): self.ent.setdefault(o + k, (name, o, n, t.startswith('i')))
        self.glob = {}
        for name, (a, t) in layout.GLOBALS.items():
            a &= 0x1FFFFF; n = mem._SZ.get(t, 4)
            for k in range(n): self.glob.setdefault(a + k, (name, a, n, t.startswith('i')))
        self.lua = L.LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
        py = self.lua.table_from({
            'r8': self.read, 'w8': self.write, 'frames': lambda: self.frame, 'pad': self.pad,
            'text': lambda x, y, t, *a: self.lines.append((x, y, t, a[0] if a else 'white')),
            'spawn': self.spawn_enemy,
            'path': lambda n: str(self.file if str(n).replace('\\', '/').endswith('command.txt') else HOME / str(n))})
        self.lua.execute(SETUP, py)
        src = (CC / SCRIPT).read_text(encoding='utf-8')
        self.resume = self.lua.execute(f'local src = ...; local co = coroutine.create(load(src, "{SCRIPT}")); '
                                       'return function() return coroutine.resume(co) end', src)
        self.procs = []
        if channel: self.procs.append(_start('--bot', channel, '--buffed' if buffed else '--no-buffed', *(['--free'] if free else []), f'--earn={int(earn)}'))
        if points: self.procs.append(start_points())
        atexit.register(self.stop)

    # ---- the script's memory: plain RAM from g.mem, what the port keeps on objects from there
    def _field(self, a):
        a &= 0x1FFFFF
        if ENT0 <= a < ENT0 + 0x294 and (a - ENT0) in self.ent: return (self.g.player,) + self.ent[a - ENT0], a - ENT0
        if a in self.glob: return (self.g,) + self.glob[a], a
        return None, a

    def read(self, a):
        g = self.g; a = a or 0                         # (BizHawk takes nil as 0: the script reads an undefined menu_check2)
        if VBLANK <= (a & 0x1FFFFF) < VBLANK + 4: return (type(g).VBLANKS >> 8 * ((a & 0x1FFFFF) - VBLANK)) & 0xFF
        f, off = self._field(a)
        if f is not None:
            obj, name, base, n, _ = f
            return ((getattr(obj, name, 0) or 0) >> 8 * (off - base)) & 0xFF
        try: return g.mem.u8(0x80000000 | (a & 0x1FFFFF))
        except Exception: return 0

    def write(self, a, v):
        g = self.g; a = a or 0; v = (v or 0) & 0xFF
        if VBLANK <= (a & 0x1FFFFF) < VBLANK + 4:
            self.slow = True                             # (Slow Motion: the script holds the VSync count)
            sh = 8 * ((a & 0x1FFFFF) - VBLANK); t = type(g); t.VBLANKS = (t.VBLANKS & ~(0xFF << sh) & 0xFFFFFFFF) | (v << sh); return
        f, off = self._field(a)
        if f is not None:
            obj, name, base, n, signed = f
            full = (1 << 8 * n) - 1; sh = 8 * (off - base)
            new = ((getattr(obj, name, 0) or 0) & full & ~(0xFF << sh)) | (v << sh)
            if signed and new >> (8 * n - 1): new -= 1 << 8 * n
            setattr(obj, name, new); return
        try: g.mem.w8(0x80000000 | (a & 0x1FFFFF), v)
        except Exception: pass

    def pad(self):
        h = self.g.pad_held
        return self.lua.table_from({'P1 L1': bool(h & 0x4), 'P1 R1': bool(h & 0x8), 'P1 L2': bool(h & 0x1), 'P1 R2': bool(h & 0x2),
                                    'P1 Select': bool(h & 0x100), 'P1 Start': bool(h & 0x800)})

    def tick(self, g):
        """One game frame of the script (up to its next emu.frameadvance); BizHawk clears its text each frame."""
        if self.failed: return
        self.g = g; self.frame += 1; self.lines = []; self.slow = False
        r = self.resume()
        ok = r[0] if isinstance(r, tuple) else r
        if not ok:
            self.failed = str(r[1]) if isinstance(r, tuple) else 'stopped'
            (HOME / '_internal' / 'crowd_control_error.txt').write_text(self.failed, encoding='utf-8')

    # ---- the script's text, in the game's font
    def texts(self, g):
        """[(x, y, text)]: the script's white letters (its black ones are the outline it draws around them)."""
        lang = getattr(g, 'lang', 'us')
        if lang == 'jp' and not getattr(g.game_font, 'jp', False): lang = 'us'   # (the game font has no kana: English, as the Options screen)
        return [(x, y, cc_text(t, lang)) for x, y, t, c in self.lines if c == 'white' and t]

    def boxed(self):
        """Use border: the script's Obtained / Lost lines (as it writes them, before translation)."""
        return {(x, y) for x, y, t, c in self.lines if c == 'white' and t and ('Obtained' in t or 'Lost' in t)}

    def draw(self, g, surf):
        gf = g.game_font
        if not gf.ok: return
        shown = self.texts(g)
        if not shown: return
        fit = lambda t, w: t if gf.width(t) <= w else fit(t[:-1], w)
        ss = getattr(g, 'settings_screen', None)
        box = self.boxed()                               # (Obtained / Lost: in the box's place, boxed or not)
        parch = self.border and ss is not None
        top = sorted((s for s in shown if s[1] < 120), key=lambda s: s[0])
        bottom = sorted((s for s in shown if s[1] >= 120), key=lambda s: s[1])
        end = 0                                          # lock text at the script's x; poison / regen centred over the HP
        for x, y, t in top:                              # (moved past the lock text when both would overlap)
            if x < 100: t = fit(t, 316 - x); self.outlined(gf, surf, t, x, TOP_Y); end = x + gf.width(t)
            else:
                t = fit(t, 316); cx = max(4, min(316 - gf.width(t), HP_X - gf.width(t) // 2))
                if end and cx < end + 8: cx = end + 8; t = fit(t, 316 - cx)
                self.outlined(gf, surf, t, cx, TOP_Y)
        def wrap(t):                                     # (at 272 px: the bot may add " (username)")
            out, line = [], ''
            for word in t.split(' '):
                if line and gf.width(line + ' ' + word) > 272: out.append(fit(line, 272)); line = word
                else: line = (line + ' ' + word) if line else word
            return out + [fit(line, 272)]
        plain = [(x, s) for x, y, t in bottom if (x, y) not in box for s in wrap(t)]
        boxed = [s for x, y, t in bottom if (x, y) in box for s in wrap(t)]
        y1 = 224
        if boxed:                                        # Use border: the menus' parchment, as the Archipelago messages
            w = max(64, max(gf.width(t) for t in boxed) + 32); h = 16 + 16 * len(boxed); x0, y1 = 8, 236 - h
            if parch: surf.blit(ss.parchment(w, h), (x0, y1))
            for i, t in enumerate(boxed):
                if parch: gf.draw(surf, t, x0 + 16, y1 + 8 + 16 * i)
                else: self.outlined(gf, surf, t, x0 + 16, y1 + 8 + 16 * i)
            y1 -= 2
        for i, (x, t) in enumerate(plain): self.outlined(gf, surf, t, x, y1 - 16 * (len(plain) - i))

    @staticmethod
    def outlined(gf, surf, t, x, y):
        """White letters outlined in the HUD check count's dark brown, eight-way."""
        import pygame
        ink = pygame.Surface((320, 16), pygame.SRCALPHA); gf.draw(ink, t, 0, 0)
        white = ink.copy(); white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        black = pygame.mask.from_surface(ink).to_surface(setcolor=(48, 40, 32, 255), unsetcolor=(0, 0, 0, 0))   # (the HUD check count's outline)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)): surf.blit(black, (x + dx, y + dy))
        surf.blit(white, (x, y))

    def skip_frame(self):
        """Slow Motion (the script wrote the VSync count this frame): the port runs gameplay at half speed, every
        other frame skipped (on the console the speed depends on the scene's load: 271 game frames in 600 vblanks
        on map 401, BizHawk 2026-11-08)."""
        self.odd = self.slow and not getattr(self, 'odd', False)
        return self.odd

    # ---- Spawn Enemy (the port only): a copy of one of this map's enemies, on open floor Alundra can see
    def spawn_enemy(self, kind='Enemy', buffed=False):
        """'' when spawned, else why not ('not here' / 'no room').  The enemy (any of ENEMIES, or of the family `kind`:
        FAMILIES) is a copy of a placement of that enemy - this map's own when it has one, else one of another map's
        (DONORS: that map's sprite, header and sound bank go with it, and with what it spawns: Actor.cc_donor /
        cc_bank, Game.cc_home, sound_system.resolve); its map programs are left off (a copy runs no room events).
        The spot (spots): open floor on screen below the HUD, reachable from Alundra.  buffed (Buffed spawns): its
        stats raised and its colours tinted (buff)."""
        import random
        import packs
        g = self.g; mp = g.map
        cats = [c for c in (FAMILIES[kind] if kind in FAMILIES else ENEMIES) if c in DONORS]
        if not cats: return 'not here'
        cat = random.choice(cats)
        own = [e for e in mp.doc['entities'] if e.get('catalogue') == cat]
        home = donor = None
        if own: rec = random.choice(own)
        else:                                                    # (another map's: the first donor whose map has it -
            rec = None                                           # a seed's Random enemies may have changed some)
            for donor in random.sample(DONORS[cat], len(DONORS[cat])):
                f = mp.folder.parent / f'{donor:03d}'
                recs = [e for e in (packs.read_json(f / 'map.json', {}) or {}).get('entities', ()) if e.get('catalogue') == cat]
                hdr = (packs.read_json(f / 'data.json', {}) or {}).get('sprite_headers', {}).get(str(cat))
                if recs and hdr and (f / 'sprites' / f'{cat:03d}').is_dir():
                    rec = dict(random.choice(recs), index=-1); home = (f / 'sprites' / f'{cat:03d}', hdr); break
            if rec is None: return 'not here'
        hdr = home[1] if home else g.header(cat)
        spots = self.spots(hdr)
        if not spots: return 'no room'
        tx, ty, h = random.choice(spots)
        rec = dict(rec); rec.update(x=tx * 2, y=ty * 2, z=h * 2, programs={k: 0 for k in rec['programs']}, collection_flag=0, contents=0)
        a = g.make_actor(rec, home)
        if home:
            import sound_system
            a.cc_donor = donor; a.cc_bank = sound_system.map_bank(donor)
        if buffed: buff(a, random.random())
        if g.take_slot(a) is None: return 'no room'
        g.actors.append(a)
        if home and a.anim.sprite is not None:                   # (its animations' sounds decoded now, from its map's bank)
            g.snd.preload({x for an in a.anim.sprite.meta.get('animations', ()) if an.get('sfx') for x in (an['sfx'], an['sfx'] | 0x100)})
        return ''

    def spots(self, hdr):
        """Where an enemy with this sprite header can appear: squares on screen (x 24-296, below the HUD) that
        Alundra can walk to at his own height (4-way from his square, so never a pit, a ledge's foot or a closed
        area), whose every square under the enemy's box is open floor (walls as physics.collision_flags: walk
        0x40, 0x01 for class B, ground 0x10 for class A - Alundra's for the way, the enemy's under it; sand and
        shallow water are floor), not deep water (floor type 4) or a bed (ground 0x60); not
        Alundra's square or the 8 around it, nor touching a solid entity.  [(x, y, height)]"""
        g = self.g; w = g.world; p = g.player
        ptx, pty = int(p.wx // 24), int(p.wy // 16); h0 = w.tile(ptx, pty).height
        cx, cy = g.cam if g.cam is not None else g.camera()
        flags = (hdr or {}).get('flags', 0)
        (ox, oy, _), (sx, sy, _) = (hdr or {}).get('hitbox_offset', (-9, -6, 0)), (hdr or {}).get('hitbox_size', (18, 12, 32))
        wall = lambda f: 0x40 | (0x01 if f & 0x8 else 0) | (0x1000 if f & 0x1 else 0)   # (physics.collision_flags)
        mine, his = wall(flags), wall(p.flags)
        x0, x1 = max(0, cx // 24 - 1), min(w.w - 1, (cx + 320) // 24 + 1)
        y0, y1 = max(0, cy // 16 - 1), min(w.h - 1, (cy + 240) // 16 + h0 + 1)
        def floor(tx, ty, block):
            t = w.tile(tx, ty)
            return t.cell is not None and t.height == h0 and not (t.walk | t.ground << 8) & block and (t.ground >> 1 & 7) != 4 and not t.ground & 0x60
        reach = {(ptx, pty)}; todo = [(ptx, pty)]
        while todo:
            tx, ty = todo.pop()
            for nx, ny in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
                if x0 <= nx <= x1 and y0 <= ny <= y1 and (nx, ny) not in reach and floor(nx, ny, his):
                    reach.add((nx, ny)); todo.append((nx, ny))
        solid = [(a.mpx >> 16, a.mpy >> 16, (a.mpx + a.size[0]) >> 16, (a.mpy + a.size[1]) >> 16)
                 for a in g.actors if a.alive and a.solid and a is not p]
        out = []
        for tx, ty in reach:
            if max(abs(tx - ptx), abs(ty - pty)) <= 1: continue
            x, y = tx * 24 + 12, ty * 16 + 8
            if not (24 <= x - cx <= 296 and 64 <= y - h0 * 16 - cy <= 224): continue
            bx, by = x + ox, y + oy
            if not all((ux, uy) in reach and floor(ux, uy, mine) for ux in range(bx // 24, (bx + max(1, sx) - 1) // 24 + 1)
                       for uy in range(by // 16, (by + max(1, sy) - 1) // 16 + 1)): continue
            if any(x1_ - 12 <= x <= x2_ + 12 and y1_ - 8 <= y <= y2_ + 8 for x1_, y1_, x2_, y2_ in solid): continue
            out.append((tx, ty, h0))
        return sorted(out)

    def stop(self):
        for p in getattr(self, 'procs', ()):
            if p is not None and p.poll() is None: p.kill()
        self.procs = []


_ENEMY_CODE = None


def _enemy_code():
    """randomizer/enemies.py (Random stats' buff rules and tint), loaded once."""
    global _ENEMY_CODE
    if _ENEMY_CODE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location('cc_enemies', TOOL / 'enemies.py'); _ENEMY_CODE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ENEMY_CODE)
    return _ENEMY_CODE


def buff(a, hue):
    """A spawned enemy as Random stats' Buffs makes a type (enemies.apply_balance / apply_speed / tint), for this
    one enemy: hit points and attack powers x1.5 (a 1-damage attack 3, a 2-damage 4), its animations' movement
    x1.5 and frame delays / 1.5, and its pictures tinted toward a random hue."""
    import copy
    E = _enemy_code(); pct = 150
    scale = lambda v: max(1, min(255, (v * pct + 50) // 100)) if v else 0
    b = copy.deepcopy(a.balance) if a.balance else None
    if b:
        b['hp'] = scale(b['hp'])
        b['attacks'] = [[x[0], {1: 3, 2: 4}[x[1]] if x[1] in (1, 2) else scale(x[1])] for x in b['attacks']]
        a.balance = b; a.hp = a.hp_max = b['hp']
    if a.anim.sprite is not None: a.anim.sprite = TintedSprite(a.anim.sprite, hue, pct)


class TintedSprite:
    """A buffed spawn's own copy of its sprite: the same frames tinted (enemies.tint), its animations faster."""
    def __init__(self, base, hue, pct):
        import copy
        E = _enemy_code()
        self.base = base; self.hue = hue; self.images = {}; self.colours = {}
        self.folder = base.folder; self.meta = copy.deepcopy(base.meta)
        for an in self.meta.get('animations', ()):
            if an.get('speed'): an['speed'] = max(1, min(0xFFFF, (an['speed'] * pct + 50) // 100))
            for way in an.get('directions', ()) or ():
                for fr in (way or {}).get('frames', ()):
                    if fr.get('ticks'): fr['ticks'] = E.speed_ticks(fr['ticks'], pct)

    def __getattr__(self, name):                       # (everything else as the sprite's: its streams, layers...)
        if name.startswith('__') or 'base' not in self.__dict__: raise AttributeError(name)   # (a save state's copy)
        attr = getattr(type(self.base), name)
        return attr.__get__(self) if hasattr(attr, '__get__') else attr

    def layers(self, index): return self.base.layers(index)

    def image(self, index):
        if index not in self.images:
            img = self.base.image(index)
            self.images[index] = None if img is None else self._tint(img)
        return self.images[index]

    def _tint(self, img):
        import pygame, numpy as np
        out = img.copy(); rgb = pygame.surfarray.pixels3d(out); alpha = pygame.surfarray.pixels_alpha(out)
        E = _enemy_code(); ex = lambda v: v * 255 // 31
        keys = np.unique(rgb[alpha > 0].reshape(-1, 3), axis=0)
        for r, gg, b in keys:
            key = (int(r), int(gg), int(b))
            n = self.colours.get(key)
            if n is None:
                w = round(key[0] * 31 / 255) | round(key[1] * 31 / 255) << 5 | round(key[2] * 31 / 255) << 10
                t = E.tint(w, self.hue)
                n = self.colours[key] = (ex(t & 31), ex(t >> 5 & 31), ex(t >> 10 & 31))
            m = (rgb[..., 0] == r) & (rgb[..., 1] == gg) & (rgb[..., 2] == b) & (alpha > 0)
            rgb[m] = n
        del rgb, alpha
        return out
# The Alundra editor's enemies (Alundra_Maker object library, kind 'enemy').
ENEMIES = frozenset((329, 335, 338, 341, 344, 347, 350, 356, 362, 365, 371, 377, 386, 389, 392, 395, 401, 404, 410, 425, 428,
                     431, 437, 440, 441, 443, 449, 453, 454, 455, 456, 458, 461, 467, 473, 478, 508))
# Maps with a placement of each enemy (stock maps; 458 Fly, 478 Soul Leech Slime, 508 Zazan's Underling have none).
DONORS = {329: (9, 13, 22, 41, 42, 61), 335: (7, 9, 12, 14, 24, 40), 338: (4, 5, 18, 19, 119, 121), 341: (3, 7, 11, 15, 48, 69), 344: (3,), 347: (1, 2, 15, 61, 64, 110), 350: (148, 149, 150, 151, 152, 155), 356: (2, 111, 114, 148, 151, 154), 362: (16, 43, 80, 81, 82, 83), 365: (80, 82, 83, 409, 410), 371: (80, 81, 82, 83, 84, 408), 377: (17, 35, 38, 40, 78, 388), 386: (38, 39, 40, 426), 389: (50, 54), 392: (4, 8, 12, 14, 79, 139), 395: (78,), 401: (86, 87, 88, 89, 92, 93), 404: (5, 101, 139, 146, 149, 150), 410: (18, 19, 26, 27, 28, 32), 425: (27, 29, 30, 31, 32, 33), 428: (21, 351, 353), 431: (16, 70, 72, 74), 437: (3, 8, 12, 52, 58, 61), 440: (100, 101, 102, 103, 106, 125), 441: (443, 445, 446), 443: (2, 382, 383, 384, 386), 449: (21, 22, 24, 41), 453: (338, 339, 341, 344, 346, 351), 454: (339, 340, 341, 343, 345), 455: (12, 14, 30, 32), 456: (337, 338, 351, 352), 461: (4, 13), 467: (88, 90, 92, 94, 429, 430), 473: (59, 444, 445, 447, 448)}
FAMILIES = {'Puku': (329,), 'Slime': (335,), 'Wasp': (455,), 'Killer': (392,), 'Roach': (467,), 'Murgg': (347, 350, 356), 'Gragg': (338, 341, 344), 'SandWorm': (410,), 'Sludge': (431,), 'Miming': (377, 386), 'Reaper': (428,), 'Shadow': (440,), 'Lizardman': (362, 365, 371), 'Zombie': (449,), 'Turtle': (437,), 'Mimic': (404,), 'MudMan': (401,), 'Mushroom': (443,), 'Mummy': (425,), 'RedTurtle': (441,), 'RockFace': (395,), 'Treant': (461,), 'Firebird': (473,), 'ShrineMummy': (454,), 'Roper': (389, 456), 'ShrineDemon': (453,)}   # (Spawn <family>: the editor's names)


POINTS = None                                   # the Points Display window (one, whether Generate or the seed started it)


def start_points():
    """The Points Display window (Points_Display.pyw: viewers' points), started unless it is already open."""
    global POINTS
    if POINTS is None or POINTS.poll() is not None:
        POINTS = _start('--points')
        if POINTS is not None: atexit.register(lambda p=POINTS: p.poll() is None and p.kill())
    return POINTS


def _start(*args):
    """ccbot.py in its own process (the exe runs it itself), no console window."""
    cmd = [sys.executable, '--run-script'] if getattr(sys, 'frozen', False) else [sys.executable, '-u']
    try: return subprocess.Popen([*cmd, str(CODE / 'ccbot.py'), *args], cwd=str(CC), creationflags=0x08000000,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError: return None
