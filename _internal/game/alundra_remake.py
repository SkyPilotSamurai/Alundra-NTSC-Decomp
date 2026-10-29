import os
"""Alundra remake (Windows / any PC).

Runs entirely from the uncompressed export in remake/assets (made from your
own disc by tools/remake_export.py and tools/remake_export_tiles.py).

Controls: arrows move, X (or Space) jump (Cross), Z / Enter / A attack, talk and read
(Square), S item (Circle), C / Left Shift dash (Triangle),
Esc quit, F1 debug overlay, F2/F3 next/previous map, F4 write script trace,
F5 (or Select, keyboard or controller) controls settings for keyboard and controller.

The game's own event scripts run on remake/vm.py, a port of the original
event interpreter (see PROGRESS.md and EVENT_REFERENCE.md).
"""
import json, os, re, sys, math
from pathlib import Path
if sys.platform == 'win32':
    # The crash logs show the main thread in plain Python when the access violation hits, so the
    # fault is in one of SDL's own threads - the audio one: SDL's WASAPI output dies when the
    # sound device stalls or changes (another program loading, opening a device).  DirectSound
    # does not; set SDL_AUDIODRIVER yourself to choose another.
    os.environ.setdefault('SDL_AUDIODRIVER', 'directsound')
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent))
from home import HOME as ROOT                         # assets, saves, settings, logs (home.py: the code may be in game/)
import vm as eventvm
import physics, gamerng, pacing, video_filter, speedrun, lr_swap, packs
from engine import player as eplayer, core as ecore, layout as elayout, registry as eregistry
from engine import shadows as eshadows
from engine.core import S16List, U8List
from engine import rodata as R
eregistry.load_all()
from controls import Controls, ControlsScreen
import controls as controls_mod

ASSETS = ROOT / 'assets'
SCALE = 3
VIEW_W, VIEW_H = 320, 240
TW, TH = 24, 16
FPS = 60
GRAVITY = 0.375         # used only when a map has no data.json (map info Gravity<<8 per frame)
TERMINAL = 6.0          # GUESS: map info ZViscosity
SPEED_UNIT = 128.0
AUDIO = False
_et = ASSETS / 'text' / 'etc_usa.json'
ITEMS = json.loads(_et.read_text(encoding='utf-8')).get('items', {}) if _et.exists() else {}
_gh = ASSETS / 'sprites' / 'global_headers.json'
GLOBAL_HEADERS = json.loads(_gh.read_text()).get('sprite_headers', {}) if _gh.exists() else {}      # animation speed 208 -> 1.6 px per frame (walk)
_ms = ASSETS / 'maps' / 'map_sizes.json'                 # each map's DATAS.BIN block (the CD read of a map change)
MAP_SIZES = {int(k): v for k, v in json.loads(_ms.read_text()).items()} if _ms.exists() else {}


# ---------------------------------------------------------------- sprites --
class Sprite:
    """One sprite's animations as exported (frames are PNG files).  Options > Sprite Graphics = Old
    (Sprite.OLD) takes a frame's picture from assets/sprites_prev (the export before the 2026-10-22
    GPU texel rule, only the pictures that changed) when it has one."""
    cache = {}
    OLD = False
    PREV = ASSETS / 'sprites_prev'

    def _file(self, name):
        if Sprite.OLD:
            try: alt = Sprite.PREV / self.folder.relative_to(ASSETS) / name
            except ValueError: alt = None
            if alt is not None and packs.exists(alt): return alt
        return self.folder / name

    @classmethod
    def use_old(cls, old):
        """Options > Sprite Graphics: switch the picture set; every loaded picture is dropped."""
        if cls.OLD == bool(old): return False
        cls.OLD = bool(old)
        for sp in cls.cache.values():
            if sp is not None: sp.images = {}
        return True

    def __init__(self, folder):
        self.folder = folder
        self.meta = json.loads((folder / 'animations.json').read_text())
        self.images = {}

    @classmethod
    def get(cls, folder):
        if folder not in cls.cache:
            cls.cache[folder] = Sprite(folder) if (folder / 'animations.json').exists() else None
        return cls.cache[folder]

    def image(self, index):
        if index not in self.images:
            p = self._file(f'{index}.png')
            img = packs.load(p)
            self.images[index] = img.convert_alpha() if img is not None else None
        return self.images[index]

    def layers(self, index):
        """Glow / shadow layers drawn with the PlayStation's add / subtract blending."""
        key = ('layers', index)
        if key not in self.images:
            out = []
            for name in self.meta.get('blend', {}).get(str(index), []):
                p = self._file(f'{index}_{name}.png')
                img = packs.load(p)
                if img is not None:
                    out.append((img.convert_alpha(),
                                pygame.BLEND_RGB_ADD if name == 'add' else pygame.BLEND_RGB_SUB))
            self.images[key] = out
        return self.images[key]

    def preload(self):
        """Every frame picture and its blend layers now (no load the first time one is drawn);
        returns the sound ids the animations play."""
        sounds = set()
        for a in self.meta.get('animations', []):
            if a.get('sfx'): sounds.update((a['sfx'], a['sfx'] | 0x100))
            for d in a.get('directions') or []:
                for f in (d or {}).get('frames', []) if isinstance(d, dict) else (d or []):
                    i = f.get('image') if isinstance(f, dict) else None
                    if i is not None: self.image(i); self.layers(i)
        return sounds

    def stream(self, anim, direction):
        anims = self.meta['animations']
        if not anims: return None
        if not 0 <= anim < len(anims): anim = 0
        dirs = anims[anim]['directions']
        st = dirs[direction] if direction < len(dirs) else None
        if st is None: st = next((d for d in dirs if d), None)
        return st

    def speed(self, anim):
        anims = self.meta['animations']
        return anims[anim]['speed'] if 0 <= anim < len(anims) else 0


class Animator:
    def __init__(self, sprite):
        self.sprite = sprite; self.anim = 0; self.frame = 0; self.tick = 0; self.done = False
        self.pos = 0; self.q = 0                      # next frame entry, stream (facing quadrant)

    def play(self, anim, restart=False):
        if anim != self.anim or restart:
            self.anim = anim; self.frame = 0; self.tick = 0; self.done = False

    def update(self, direction):
        """Advances one frame; returns True when the animation completed a cycle."""
        st = self.sprite.stream(self.anim, direction) if self.sprite else None
        if not st or not st['frames']: return True
        self.tick += 1
        f = st['frames'][self.frame % len(st['frames'])]
        if self.tick < max(1, f['ticks']): return False
        self.tick = 0; self.frame += 1
        if self.frame < len(st['frames']): return False
        nxt = st.get('next')
        if st['end'] in ('stop', 'hold'):              # 'hold': frame transform 0x80, ForceResetAnimationFlag
            self.frame = len(st['frames']) - 1; self.done = True
        elif isinstance(nxt, int) and st['end'] not in ('loop', None):
            self.play(nxt, True)
        else:
            self.frame = 0
        return True

    def frame_info(self, direction):
        st = self.sprite.stream(self.anim, direction) if self.sprite else None
        if not st or not st['frames']: return None
        return st['frames'][self.frame % len(st['frames'])]

    def current(self, direction):
        st = self.sprite.stream(self.anim, direction) if self.sprite else None
        if not st or not st['frames']: return None
        f = st['frames'][self.frame % len(st['frames'])]
        img = self.sprite.image(f['image']) if f['image'] is not None else None
        return (img, f['left'], f['top'], self.sprite.layers(f['image'])) if img else None


# 0x800237F4 g_animationDirectionTable: row = facing now (0 down, 1 up, 2 left, 3 right),
# column = ((direction + 2) & 0x1C) >> 2; diagonals keep the current axis.
ANIM_DIR_TABLE = [0, 0, 2, 1, 1, 1, 3, 0, 0, 0, 2, 1, 1, 1, 3, 0, 0, 2, 2, 2, 1, 3, 3, 3, 0, 2, 2, 2, 1, 3, 3, 3]


# US 0x80022CEC: directions a sprint may keep for each facing (down, up, left, right):
# straight on or 45 degrees either side
SPRINT_TURN = ((0x1C, 0x00, 0x04), (0x0C, 0x10, 0x14), (0x04, 0x08, 0x0C), (0x14, 0x18, 0x1C))


def anim_direction(current, d):
    return ANIM_DIR_TABLE[(current or 0) * 8 + (((d + 2) & 0x1C) >> 2)]


def dir32_to_sprite(d):
    """32-direction value to the exported sprite stream order (down, up, left, right)."""
    d &= 31
    return 0 if d < 4 or d >= 28 else (2 if d < 12 else (1 if d < 20 else 3))


# ------------------------------------------------------------------ actors --
class Actor(physics.Body):
    """A live entity (the game's Entity): Alundra, characters, objects."""

    def __init__(self, sprite, wx, wy, z, direction=0):
        self.init_body()
        self.anim = Animator(sprite); self.wx = wx; self.wy = wy; self.z = z; self.vz = 0.0
        self.visible = True; self.alive = True; self.active = True; self.solid = True
        self.record = None; self.ref_id = -1; self.programs = {}; self.states = {}
        self.target_anim = 0; self.target_dir = direction; self.last_anim = 0; self.last_dir = direction
        self.flags = 0; self.logic_ctx = None
        self.hit_counter = 0; self.anim_complete = 0
        self.bumped = None; self.anim_quadrant = 0
        self.hp = self.hp_max = 10; self.contents_flag = 0; self.parent = None
        self.hitbox = ([-9, -6, 0], [18, 12, 32]); self.sprite_programs = {}; self.break_effect = 0
        self.ai = S16List([0] * 10); self.bytes = U8List([0, 0, 0, 0]); self.status = 'normal'; self.a_done = False
        self.contents_item = 0; self.item_state = 0; self.item_flag = 0; self.delay = 0; self.bounce = 0
        self.flags2 = 0; self.carried = None
        self.estatus = 1; self.action = 'A'; self.slot = -1; self.frozen = 0   # Entity+0x10, +0x228, +0x20
        self.serial = 0; self.frame_counter = 0; self.cur_anim = -1
        self.last_action = None; self.saved_c = (0, 0)                         # +0x22C, +0x26C/+0x270
        self.sprite_index = 0                                                   # +0x68: the sprite (catalogue) number

    def set_hitbox(self, offset, size):
        """EntityManager.SetEntityDimensions: the sprite header's box drives all collision."""
        self.hitbox = (list(offset), list(size))
        ox, oy, oz = offset; sx, sy, sz = size
        self.mod = (ox << 16, oy << 16, oz << 16)
        self.size = tuple(((v << 16) - 1) if v else 0 for v in (sx, sy, sz))

    def anim_set(self, index):
        anims = self.anim.sprite.meta['animations'] if self.anim.sprite else []
        return anims[index] if 0 <= index < len(anims) else {}

    def tile(self):
        return (self.px >> 16) // TW, (self.py >> 16) // TH, self.pz >> 20        # PhysicsEngine.UpdateTileAttributes

    def anim_dir(self):
        return ((self.target_dir + 4) // 8) & 3        # 0 down, 1 left, 2 up, 3 right

    def __getattr__(self, n):
        if n.startswith('f_'): return 0                    # record words not identified yet
        raise AttributeError(n)

    @property
    def header_addr(self):
        """Entity+0x64: its sprite header in the sprite-info blocks (0x8003A424's lookup)."""
        from engine import spriteinfo as _si
        return _si.header_addr(Actor.game, self.sprite_index) if Actor.game is not None else 0

    # the game's record fields the engine reads, from the remake's own state
    def _prog(k):
        def get(s): return s.programs.get(k, 0)
        def put(s, v):
            if v: s.programs[k] = v
            else: s.programs.pop(k, None)
        return property(get, put)
    def _bi(k):
        def get(s): return (s.sprite_programs or {}).get(k, 0)
        def put(s, v):                                     # (the dict is the sprite header's, shared by
            d = dict(s.sprite_programs) if isinstance(s.sprite_programs, dict) else {}   # every entity of
            d[k] = v; s.sprite_programs = d                # the sprite: copy before writing this one's)
        return property(get, put)
    prog_a, prog_b, prog_c, prog_d, prog_e, prog_f = _prog('A'), _prog('B'), _prog('C'), _prog('D'), _prog('E'), _prog('F')
    bi_a, bi_b, bi_c, bi_d, bi_e, bi_f = _bi('A'), _bi('B'), _bi('C'), _bi('D'), _bi('E'), _bi('F')
    del _prog, _bi
    index = property(lambda s: s.__dict__.get('_index', s.slot))       # +0x00 (0 for a slot re-made by 0x8003A964)
    saved_anim = property(lambda s: s.saved_c[0], lambda s, v: setattr(s, 'saved_c', (v, s.saved_c[1])))   # +0x26C
    saved_dir = property(lambda s: s.saved_c[1], lambda s, v: setattr(s, 'saved_c', (s.saved_c[0], v)))    # +0x270
    anim_done = property(lambda s: 1 if s.anim.done else 0, lambda s, v: setattr(s.anim, 'done', bool(v)))
    holder = property(lambda s: s.platform, lambda s, v: setattr(s, 'platform', v))
    f_190 = property(lambda s: s.slope_prev, lambda s, v: setattr(s, 'slope_prev', v))     # +0x190: the floor kind a frame before
    f_1BC = property(lambda s: s.sort_key, lambda s, v: setattr(s, 'sort_key', v))       # +0x1BC: the drawing key
    tile_flags = property(lambda s: s.tile_attr)
    CELL_SCRATCH = 0x801FE300                                          # 64 slots x 4 corners x 8 bytes
    game = None                                                        # (set by Game: the RAM the cells go to)

    def _cell(self, k):
        """+0x148.. the map square record under corner k of the box (8 bytes: walk, ground,
        slope, height, ...), as the game keeps a pointer into the map's table: the square's
        bytes are put in a scratch record and its address returned."""
        g = Actor.game
        a = self.CELL_SCRATCH + ((max(0, self.slot) & 63) * 4 + k) * 8
        if g is not None:
            t = self.map_tiles[k] if k < len(self.map_tiles) else physics.Tile(None)
            g.mem.w8(a, t.walk); g.mem.w8(a + 1, t.ground); g.mem.w8(a + 2, t.slope); g.mem.w8(a + 3, t.height)
        return a
    cell0 = property(lambda s: s._cell(0)); cell1 = property(lambda s: s._cell(1))
    cell2 = property(lambda s: s._cell(2)); cell3 = property(lambda s: s._cell(3))
    mh0 = property(lambda s: s.map_heights[0] if len(s.map_heights) > 0 else 0)
    mh1 = property(lambda s: s.map_heights[1] if len(s.map_heights) > 1 else 0)
    mh2 = property(lambda s: s.map_heights[2] if len(s.map_heights) > 2 else 0)
    mh3 = property(lambda s: s.map_heights[3] if len(s.map_heights) > 3 else 0)
    atk_on = property(lambda s: 1 if getattr(s, 'box', None) else 0)
    atk_x = property(lambda s: s.px + (s.box[0] << 16) if getattr(s, 'box', None) else 0)
    atk_y = property(lambda s: s.py + (s.box[1] << 16) if getattr(s, 'box', None) else 0)
    atk_z = property(lambda s: s.pz + (s.box[2] << 16) if getattr(s, 'box', None) else 0)
    atk_w = property(lambda s: (s.box[3] << 16) - 1 if getattr(s, 'box', None) else 0)
    atk_h = property(lambda s: (s.box[4] << 16) - 1 if getattr(s, 'box', None) else 0)
    atk_d = property(lambda s: (s.box[5] << 16) - 1 if getattr(s, 'box', None) else 0)

    _estatus = 0
    shadow = None                                                      # +0x1B8: its shadow's effect record
    sort_key = 0                                                       # +0x1BC: its drawing key (0 until it is listed)
    top_z = 0                                                          # +0x1C0: box z + size z, of the last frame it was listed
    attack_addr = 0                                                    # +0x1C8: its attack record (0: none)

    @property
    def estatus(self): return self._estatus

    @estatus.setter
    def estatus(self, s):
        """Entity+0x10.  Status 4 (destroyed) from any routine (DestroyEntity 0x8003AEE4, the
        ports' remove_entity ...) takes the entity off at once: not drawn, no action, and its
        slot freed at the start of the next frame (0x80038F24)."""
        self._estatus = s
        if s == 4 and getattr(self, 'alive', False):
            self.alive = False; self.visible = False; self.active = False; self.action = None

    def set_status(self, s):
        """Entity+0x10: 1 loaded (A next), 2 normal (C/D), 3 deactivated (E every frame),
        4 destroyed (the slot is freed at the start of the next frame)."""
        if not self.alive: return
        self.estatus = s
        self.status = 'deactivated' if s == 3 else 'normal'
        if s == 4: self.alive = False; self.visible = False; self.active = False; self.action = None

    def deactivate(self): self.set_status(3)          # command 19 (0x8003E220): status 3

    def activate(self): self.set_status(2); self.active = True; self.visible = True

    def ground_row(self):
        return int(self.wy // TH)

    def draw(self, surf, cam, margin):
        if not self.visible: return
        if (getattr(self, 'damaged_tick', 0) & 3) == 3: return      # UpdateEntityLists: blink while hurt
        cur = self.anim.current(self.anim_quadrant if self.anim_quadrant is not None else dir32_to_sprite(self.target_dir))
        sx = self.wx - cam[0]; sy = self.wy + margin - self.z - cam[1]
        if cur:
            img, left, top, layers = cur
            surf.blit(img, (sx + left, sy + top))
            for layer, mode in layers: surf.blit(layer, (sx + left, sy + top), special_flags=mode)
        else:
            pygame.draw.rect(surf, (255, 0, 255), (sx - 4, sy - 12, 8, 12), 1)


# ---------------------------------------------------------------- game font --
EU_LANGS = ('en_eu', 'fr', 'de', 'it', 'es')        # the European discs (tools/remake_export_eu.py)
CHAR_TABLE = 0x8009BC2C                              # 128 character records (width, rows, u, v, y offset)
CHAR_RECORDS = 0x80                                   # (US: other tables follow at 0x8009C62C; the European 256 stay in GameFont._widths)


class GameFont:
    """The game's own menu font (FONT3.TIM in palette 8) and message window.  A European language
    swaps in its disc's font and character records (assets/ui/<lang>: every Windows-1252 code
    0x20-0xFF has a glyph there; the texts are Windows-1252)."""
    _widths = None                                   # the European records' widths (None: the US EXE's)

    def __init__(self):
        ui = ASSETS / 'ui'
        self.ok = (ui / 'font.png').exists() and (ui / 'font.json').exists()
        self.eu = False
        if not self.ok: return
        self.sheet = pygame.image.load(str(ui / 'font.png')).convert_alpha()
        self.chars = {int(k): v for k, v in json.loads((ui / 'font.json').read_text()).items()}
        self.us = (self.sheet, self.chars)
        box = ui / 'text_box.png'
        self.box = pygame.image.load(str(box)).convert_alpha() if box.exists() else None

    @staticmethod
    def eu_font_ok(lang):
        d = ASSETS / 'ui' / lang
        return all((d / f).exists() for f in ('font.png', 'font.json', 'chars.bin'))

    def set_lang(self, g, lang):
        """The font and the character records at 0x8009BC2C (the message code measures with them)
        for this language: the European disc's, or back to the US EXE's."""
        if not self.ok: return
        if lang in EU_LANGS and self.eu_font_ok(lang):
            d = ASSETS / 'ui' / lang
            self.sheet = pygame.image.load(str(d / 'font.png')).convert_alpha()
            self.chars = {int(k): v for k, v in json.loads((d / 'font.json').read_text()).items()}
            table = (d / 'chars.bin').read_bytes()
            GameFont._widths = [int.from_bytes(table[0x14 * c:0x14 * c + 4], 'little', signed=True) for c in range(256)]
            self.eu = True
        else:
            self.sheet, self.chars = self.us
            table = bytes(R.u8(CHAR_TABLE + i) for i in range(0x14 * CHAR_RECORDS))
            GameFont._widths = None; self.eu = False
        for i, b in enumerate(table[:0x14 * CHAR_RECORDS]): g.mem.w8(CHAR_TABLE + i, b)

    @staticmethod
    def glyph_width(c):
        """The character record's width (0x8009BC2C + 0x14 * c: width, rows, u, v, y offset)."""
        if GameFont._widths is not None: return GameFont._widths[ord(c) & 255]
        return R.s32(CHAR_TABLE + 0x14 * (ord(c) & 255))

    def _bytes(self, text):
        """A European text's characters as their Windows-1252 codes (one per character)."""
        return text.encode('cp1252', 'replace').decode('latin-1')

    _kanji = None

    @classmethod
    def kanji(cls):
        if cls._kanji is None:
            from jp_text import KanjiFont
            cls._kanji = KanjiFont()
        return cls._kanji

    def width(self, text):
        """0x80048780 puts each character width + 1 pixels after the last (JP text: 16 a glyph)."""
        if self.eu: text = self._bytes(text)
        elif any(ord(c) > 0xFF for c in text): return 16 * len(text)
        return sum(self.glyph_width(c) + (0 if self.eu else 1) for c in text)   # (European discs: width only)

    def draw(self, surf, text, x, y):
        """0x80048780: each character's width x 16 pixels from the font, then width + 1 on.  Text
        with Japanese in it is drawn the JP game's way (jp_text.py)."""
        if self.eu: text = self._bytes(text)
        elif any(ord(c) > 0xFF for c in text): return self.kanji().draw(surf, text, x, y)
        for c in text:
            w = self.glyph_width(c); g = self.chars.get(ord(c) & 255)
            if g is not None and c != ' ': surf.blit(self.sheet, (x, y), (g['u'], g['v'], w, 16))
            x += w + (0 if self.eu else 1)


class Hud:
    """The game's HUD (EXE 0x8004B770 / xcasadio HudManager): drawn from WIND.TX in
    palette 5 at y=16. Life: one 16x16 gem per full 10 (slots at x 0x50+8i, right to
    left), 10 small 8x8 pips (2 rows of 5 at x 0x78) for the rest; max life as
    '/NN' at x 0x90; magic crystals 8x16 at x 0xD8; gilder 4 digits at x 0x100."""
    Y = 16

    def __init__(self):
        f = ASSETS / 'ui' / 'WIND_pal05.png'; g = ASSETS / 'ui' / 'wind_ingame.png'
        self.sheet = pygame.image.load(str(f)).convert_alpha() if f.exists() else None
        if self.sheet is not None and g.exists():
            # cells the game's own HUD/menu tables draw keep that cell's palette (5 or 7)
            pal = json.loads((ASSETS / 'ui' / 'wind_ingame_palettes.json').read_text())
            ing = pygame.image.load(str(g)).convert_alpha()
            for key in pal:
                cx, cy = map(int, key.split(','))
                r = pygame.Rect(cx * 8, cy * 8, 8, 8)
                self.sheet.fill((0, 0, 0, 0), r); self.sheet.blit(ing, r, r)
        self.ticks = 0
        self.shown_gilder = None                # 0x800AA0FC: the gilder the HUD shows (counts toward the real one)
        self.bag = 0                            # 0x800AA110: the money bag's frame while it counts
        self.state = 0                          # 0x8012E3E0: 1 shown, |2 sliding out, |4 sliding in, 0 hidden
                                                # (0 at boot: only 0x8004D24C brings it in, and only while
                                                #  flag 0x67E is set)
        self.slide = None                       # 0x80119510: [tick, length, steps, start y, end y]
        self.shown = [10, 10, 0, 0]             # 0x800AA0EC / F0 / F4 / F8: the life, most life, magic and
                                                # most magic the HUD shows (they count toward the real ones);
                                                # the EXE's own initial values (it is loaded at each game start)
        self.timers = [0, 0, 0, 0]              # 0x800AA100 / 104 / 108 / 10C
        self.started = False                    # task 1's start-up 0x8004CA74 has run

    # ---- task 1's window (0x800AA0C0: x 0, y 16, 5 rows) slides away under the menu
    ROWS = 5

    def hide(self):
        """0x8004D1B8: the HUD slides up out of the screen (15 frames)."""
        if self.state & 3 == 1:
            self.slide = [0, 0xF, 2, 0x10, ~(self.ROWS * 8)]; self.state |= 2

    def show(self):
        """0x8004D24C: it slides back down."""
        if self.state == 0:
            self.slide = [0, 0xF, 2, ~(self.ROWS * 8), 0x10]; self.state = 5
            self.Y = ~(self.ROWS * 8)

    def start(self, hp_max, mp_max):
        """Task 1's start-up 0x8004CA74: the shown most life and most magic are the real ones; the
        shown life and magic keep their values (from the EXE: 10 and 0) and count from there."""
        self.shown[1] = hp_max; self.shown[3] = mp_max; self.started = True

    def sync(self, hp_max, mp_max):
        """0x8004CA2C (script command C3, the debug start): life and magic shown full."""
        self.shown[:] = [hp_max, hp_max, mp_max, mp_max]

    def count(self, hp, hp_max, mp, mp_max, sound=None):
        """0x8004D6C8-0x8004D9A4, every other frame: the shown life steps one point toward the real
        life every 4th time (sound 8 for each point gained); when they are equal it grows the shown
        most life the same way (the shown life follows it).  Magic the same, sound 9."""
        sh, tm = self.shown, self.timers
        for k, real, most, snd in ((0, hp, hp_max, 8), (2, mp, mp_max, 9)):
            v = min(real, sh[k + 1])
            if v < sh[k] or (sh[k] == v and tm[k]):
                if tm[k] == 0: sh[k] -= 1
                tm[k] += 1
                if tm[k] >= 4: tm[k] = 0
            elif sh[k] < v:
                tm[k] -= 1
                if tm[k] < 0: tm[k] = 3
                elif tm[k] == 0:
                    sh[k] += 1
                    if sound: sound(snd)
            elif sh[k + 1] < most:
                t = k + 1
                tm[t] -= 1
                if tm[t] < 0: tm[t] = 3
                elif tm[t] == 0: sh[k + 1] += 1; sh[k] = sh[k + 1]
            elif sh[k + 1] > most: sh[k + 1] = most                  # (the game never lowers it)

    def frame(self, gilder, stats=None, sound=None):
        """Task 1's frame routine 0x8004D2F4: the slide, then the gilder counter (10 a frame while
        far off, else 1; the bag turns every 6 frames while it counts)."""
        if self.state == 0: return
        if self.state & 6 and self.slide is not None:
            sl = self.slide
            if sl[2] == 0:
                if self.state & 2: self.state = 0
                if self.state & 4: self.state &= ~4
            elif sl[0] != sl[1]:
                d = (sl[4] - sl[3]) * sl[0]; q = abs(d) // sl[1]
                self.Y = sl[3] + (q if d >= 0 else -q); sl[0] += 1
            else:
                self.Y = sl[4]; sl[2] -= 1
        self.ticks += 1
        if stats is not None:
            if not self.started: self.start(stats[1], stats[3])
            elif not self.ticks & 1: self.count(*stats, sound=sound)
        g = max(0, gilder)
        if self.shown_gilder is None: self.shown_gilder = g
        sg = self.shown_gilder
        if g < sg or (sg == g and self.bag):
            if g < sg - 10: sg -= 10
            elif g < sg: sg -= 1
            counting = True
        elif sg < g:
            sg = sg + 10 if sg + 10 < g else sg + 1
            counting = True
        else:
            counting = False; self.bag = 0
        if counting and self.ticks % 6 == 0:
            self.bag += 1
            if self.bag >= 4: self.bag = 0
        self.shown_gilder = sg

    def piece(self, surf, x, y, u, v, w, h):
        surf.blit(self.sheet, (x, y), (u, v, w, h))

    def box(self):
        """HudManager: weapon / item background, a 24x32 POLY_G4 (corners black, yellow,
        cyan, blue) drawn half transparent at x 0x10 and 0x30."""
        if getattr(self, '_box', None) is None:
            b = pygame.Surface((24, 32), pygame.SRCALPHA)
            c = ((0, 0, 0), (255, 255, 0), (0, 255, 255), (0, 0, 255))
            for y in range(32):
                for x in range(24):
                    u, v = x / 23, y / 31
                    col = [int(c[0][i] * (1 - u) * (1 - v) + c[1][i] * u * (1 - v) + c[2][i] * (1 - u) * v + c[3][i] * u * v) for i in range(3)]
                    b.set_at((x, y), (*col, 128))
            self._box = b
        return self._box

    def icon(self, item):
        """The item's picture (0x8004F05C): image 0x80059958(n), n = the item record's +8 (0x800BBE58
        + 10 * item; item + 0x1E for every item that has one) = global sprite record n's first image."""
        if not item or not 0 < item < 99: return None
        n = R.s16(0x800BBE58 + 10 * item)
        if n < 0: return None
        sp = Sprite.get(ASSETS / 'sprites' / 'global' / f'{n:03d}')
        if sp is None: return None
        try: fr = sp.meta['animations'][0]['directions'][0]['frames'][0]
        except (KeyError, IndexError): return None
        return sp.image(fr['image'])

    BIG, BIG_EMPTY, PIP, PIP_EMPTY = 0x800A2BC8, 0x800A2C40, 0x800A3E98, 0x800A3ED4   # u, v per frame
    CRYSTAL, CRYSTAL_EMPTY, SHIMMER = 0x800A50A0, 0x800A517C, 0x800AA0E8

    def _uv(self, table, frame, stride):
        return R.u8(table + frame * stride), R.u8(table + frame * stride + 1)

    def draw_life(self, surf, Y, real_max):
        """0x8004E100: the shown life as big gems (10 each, slots right to left from x 0x50) and pips
        (2 rows of 5 at x 0x78).  While a point is counted in or out (timer 0x800AA100) or the most
        life grows (0x800AA104) one point more is drawn and that pip - and its big gem when it is the
        first pip after a full ten - shows frame `timer` (growing: 4 + timer) of the gem / pip
        animation.  Empty gems go up to the real most life."""
        sh, tm = self.shown, self.timers
        n = sh[0] + (1 if tm[0] or tm[1] else 0)
        big, small = n // 10, n % 10
        if n >= 10 and small == 0: big -= 1; small = 10
        slots = {}
        for i in range(big): slots[3 - i] = self._uv(self.BIG, 0, 40)
        i = big
        while i < (real_max - 1) // 10:
            slots[3 - i] = self._uv(self.BIG_EMPTY, 0, 40); i += 1
        pips = [self._uv(self.PIP, 0, 20) if k < small else self._uv(self.PIP_EMPTY, 0, 20) for k in range(10)]
        frame = tm[0] if tm[0] else (4 + tm[1] if tm[1] else None)
        if frame is not None:
            if small == 1: slots[4 - big] = self._uv(self.BIG, frame, 40)
            pips[(n - 1) % 10] = self._uv(self.PIP, frame, 20)
        for slot, (u, v) in slots.items():
            if 0 <= slot <= 3: self.piece(surf, 0x50 + slot * 8, Y, u, v, 16, 16)
        for k, (u, v) in enumerate(pips):
            self.piece(surf, 0x78 + k % 5 * 8, Y + k // 5 * 8, u, v, 8, 8)
        most = sh[1]                                     # '/NN': the shown most life (cell 10 = '/')
        for i, d in enumerate((10, (most // 10) % 10, most % 10)):
            self.piece(surf, 0x90 + (i + 2) * 8, Y, d * 8, 0x28, 8, 16)

    def draw_magic(self, surf, Y):
        """0x8004EA14: the shown magic as crystals from x 0xD8, each shimmering through its own order
        (table *(0x800AA0E8), a step every 5 frames of the counter 0x800AA0E4); the one counted in or
        out shows frame 4 + timer (0x800AA108), growing 8 + timer (0x800AA10C); empty ones up to the
        shown most magic."""
        sh, tm = self.shown, self.timers
        n = sh[2] + (1 if tm[2] or tm[3] else 0)
        seq = R.u32(self.SHIMMER); phase = (self.ticks // 5) % 4
        for i in range(max(n, sh[3])):
            if i < n: frame = R.u8(seq + i * 4 + phase)
            else: frame = None
            if i == n - 1 and tm[2]: frame = 4 + tm[2]
            elif i == n - 1 and tm[3]: frame = 8 + tm[3]
            u, v = self._uv(self.CRYSTAL, frame, 20) if frame is not None else self._uv(self.CRYSTAL_EMPTY, 0, 20)
            self.piece(surf, 0xD8 + i * 8, Y, u, v, 8, 16)

    def draw(self, surf, hp, hp_max, mp, mp_max, gilder, weapon=0, item=0):
        if self.sheet is None: return False
        if self.state == 0: return True
        Y = self.Y
        for x, it in ((0x10, weapon), (0x30, item)):      # DisplayHudWeaponAndItem
            surf.blit(self.box(), (x, Y))
            img = self.icon(it)
            if img is not None: surf.blit(img, (x + (24 - img.get_width()) // 2, Y + (32 - img.get_height()) // 2))
        self.draw_life(surf, Y, hp_max)
        self.draw_magic(surf, Y)
        g = max(0, min(9999, gilder if self.shown_gilder is None else self.shown_gilder))
        for i, d in enumerate((g // 1000, g // 100 % 10, g // 10 % 10, g % 10)):   # 0x8004DD54
            self.piece(surf, 0x100 + i * 8, Y, d * 8, 0x28, 8, 16)
        self.piece(surf, 0x120, Y, 0x90 + 8 * self.bag, 0x38, 8, 16)   # the money bag (layout 0x800A19D0)
        return True


# --------------------------------------------------------------------- map --
class GameMap:
    def __init__(self, map_id):
        folder = ASSETS / 'maps' / f'{map_id:03d}'
        self.id = map_id; self.folder = folder
        self.doc = json.loads((folder / 'map.json').read_text())
        self.w, self.h, self.margin = self.doc['width'], self.doc['height'], self.doc['margin']
        self.cells = [list(c) for c in self.doc['cells']]
        atlas = folder / 'tiles.png'
        self.atlas = pygame.image.load(str(atlas)).convert_alpha() if atlas.exists() else None
        self.tiles = {int(k): v for k, v in json.loads((folder / 'tiles.json').read_text()).items()} if (folder / 'tiles.json').exists() else {}
        self.build_pieces()
        self.scripts = {}
        for key, rows in self.doc.get('scripts', {}).items():
            if isinstance(rows, list):
                self.scripts[key] = {r['offset']: (r['op'], bytes.fromhex(r['bytes']), r) for r in rows}
        self.roots = {key: min(code) for key, code in self.scripts.items() if code}
        # the map's programs are one block of bytes in the game: a call (op 78..7C) or jump may
        # land in another program's listing (map 476's B4 calls B1..B3's routines), so every
        # program runs on the whole block
        self.code = {}
        for code in self.scripts.values(): self.code.update(code)
        df = folder / 'data.json'
        self.data = json.loads(df.read_text()) if df.exists() else {}
        self.copies = {c['index']: c for c in self.data.get('map_copies', [])}
        self.tile_anims = [dict(a) for a in self.data.get('tile_animations', [])]; self.anim_shift = {}
        from lining import Lining
        self.lining = Lining(folder)
        info = self.data.get('info', {})
        self.gravity = info.get('gravity', GRAVITY * 256) / 256.0          # PhysicsEngine: ForceZ -= Gravity << 8
        self.terminal = info.get('z_viscosity', TERMINAL * 256) / 256.0    # terminal fall speed ZViscosity << 8
        self.sprite_headers = self.data.get('sprite_headers', {})
        wf = folder / 'warps.json'
        self.warps = json.loads(wf.read_text()) if wf.exists() else []

    def build_pieces(self):
        """Per map row: (tile code, x, y on the map picture, wall?, the square's height in pixels
        when it is floor, else None)."""
        self.pieces_by_row = {}
        for i, (walk, ground, slope, height, code, walls, shift) in enumerate(self.cells):
            x, y = i % self.w, i // self.w
            py = y * TH + self.margin - height * TH
            row = self.pieces_by_row.setdefault(y, [])
            # floor (for Options > clipping Never): a square nobody is blocked from (walk bits 0x41)
            # and not a bed (ground bits 0x60: the mattress squares of every house's bed); a
            # blocked square's top is furniture, a crate, a ledge - never floor
            floor = not (walk & 0x41) and not (ground & 0x60)
            if code != 0xFFFF: row.append((code, x * TW, py, False, height * TH if floor else None))
            for j, wc in enumerate(walls):
                if wc != 0xFFFF: row.append((wc, x * TW, py + (j + 1 - shift) * TH, True, None))
        # the highest / lowest piece of each row: render() skips a row's tiles when none can be on screen
        self.row_span = {y: (min(q[2] for q in r), max(q[2] for q in r)) for y, r in self.pieces_by_row.items() if r}

    def cell(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h: return self.cells[ty * self.w + tx]
        return None

    def copy_area(self, sx, sy, w, h, dx, dy):
        """ChangeAreaTileProperties: copies a block of map squares (doors, bridges, switches)."""
        src = [[list(self.cell(sx + x, sy + y) or []) for x in range(w)] for y in range(h)]
        for y in range(h):
            for x in range(w):
                c = src[y][x]
                if c and self.cell(dx + x, dy + y) is not None:
                    self.cells[(dy + y) * self.w + dx + x] = [c[0], c[1], c[2], c[3], c[4], list(c[5]), c[6]]
        self.build_pieces()

    def apply_copy(self, n):
        if n in self.copies:
            c = self.copies[n]; self.copy_area(c['from_x'], c['from_y'], c['width'], c['height'], c['to_x'], c['to_y'])
            return True
        return False

    def animate_tiles(self):
        """Water/lava pages: every `ticks` frames the next frame's tiles are drawn
        (EXE 0x8002CFD8; tile number + frame * tiles_per_frame)."""
        for a in self.tile_anims:
            a['tick'] = a.get('tick', 0) + 1
            if a['tick'] >= a['ticks']:
                a['tick'] = 0; a['frame'] = (a.get('frame', 0) + 1) % a['frames']
        self.anim_shift = {a['page']: a.get('frame', 0) * a['tiles_per_frame'] for a in self.tile_anims}

    def tile_rect(self, code):
        cache = self.__dict__.get('_rects')
        if cache is None or cache[0] is not self.anim_shift or cache[1] is not self.atlas:
            cache = self._rects = (self.anim_shift, self.atlas, {})   # (anim_shift is a new dict per animation step)
        r = cache[2].get(code, False)
        if r is not False: return r
        c = code
        if self.anim_shift and c != 0xFFFF:
            c += self.anim_shift.get((c & 1023) // 160, 0)
        i = self.tiles.get(c)
        r = None if i is None or self.atlas is None else pygame.Rect(i % 32 * TW, i // 32 * TH, TW, TH)
        cache[2][code] = r
        return r

    def sprite_folder(self, catalogue):
        if catalogue < 256: return ASSETS / 'sprites' / 'global' / f'{catalogue:03d}'
        return self.folder / 'sprites' / f'{catalogue:03d}'


class MapEvent:
    def __init__(self, rec):
        self.rect = rec['rect']; self.prog = self.prog0 = rec['program']; self.state = None; self.ctx = None


# PSX pad bits as the scripts test them (command 2F)
# pad bits come from controls.py (keyboard and controller bindings, controls.json)


# -------------------------------------------------------------------- game --
class InventoryView:
    """g.inventory: the game's item records (count s16 at *(0x80119AEC) + n * 4 + 2) as a dict."""
    def __init__(self, g): self.g = g
    def _a(self, n): return self.g.mem.u32(0x80119AEC) + 4 * n + 2
    def _ok(self, n): return isinstance(n, int) and 0 <= n < 99
    def get(self, n, default=0):
        if not self._ok(n): return default
        c = self.g.mem.s16(self._a(n)); return c if c else default
    def __getitem__(self, n):
        c = self.get(n, 0)
        if not c: raise KeyError(n)
        return c
    def __setitem__(self, n, v):
        if self._ok(n): self.g.mem.w16(self._a(n), v)
    def __delitem__(self, n): self[n] = 0
    def __contains__(self, n): return bool(self.get(n, 0))
    def __iter__(self): return iter([n for n in range(99) if self.get(n, 0)])
    def keys(self): return list(self)
    def items(self): return [(n, self.get(n)) for n in self]
    def __len__(self): return len(list(self))


class Game:
    def __init__(self, map_id, start=None, boot=False, new_game=False, handoff=None):
        global AUDIO
        pygame.mixer.pre_init(44100, buffer=1024)               # (pygame.init opens the mixer)
        pygame.init()
        try: pygame.mixer.init(44100, buffer=1024); AUDIO = True
        except pygame.error:
            AUDIO = False
            if os.environ.get('SDL_AUDIODRIVER') == 'directsound':     # (no DirectSound: SDL's default)
                del os.environ['SDL_AUDIODRIVER']
                try: pygame.mixer.init(44100, buffer=1024); AUDIO = True
                except pygame.error: pass
        if AUDIO: pygame.mixer.set_num_channels(48); pygame.mixer.set_reserved(1)   # the SPU's 24 voices,
                                                                 # each followed by its reverb tail
        self.sfx_cache = {}
        from settings_screen import load_settings
        self.settings = load_settings()
        Sprite.use_old(self.settings.get('sprite_set') == 'old')          # Options > Sprite Graphics
        from sound_system import SoundSystem
        self.snd = SoundSystem(ASSETS, self.settings, AUDIO)      # PlaySound / music (sound_system.py)
        self.screen = None; self.set_display()
        pygame.display.set_caption('Alundra PC')
        self.view = pygame.Surface((VIEW_W, VIEW_H))
        self.font = pygame.font.SysFont('arial', 11)
        self.game_font = GameFont(); self.hud = Hud()
        self.clock = pygame.time.Clock()
        from engine import mem as emem
        self.mem = emem.exe_image()                              # the game's memory (EXE tables, loaded data)
        self.inventory = InventoryView(self)                     # the game's item records (g.mem)
        self.pages = []; self.choice = False; self.choice_result = 0; self.choice_sel = 0
        self.toasts = []; self.unknown_ops = {}; self.debug = False
        self.player_locked = False; self.pending_warp = None; self.warps_disabled = False
        self.trans = None                                        # a map change in progress (warp_frame)
        self.snapshot = None; self.transition = None             # engine/screen.py: the copied picture, the effect
        self.clear_colour = (0, 0, 0); self.fade_overlay = None; self.disp = [0, 0, VIEW_W, VIEW_H]
        self.respawn_save = None                                 # the last save point's game state (0x80031AC4)
        self.music = None; self.last_sound = None; self.sfx_voices = {}
        self.camera_follow = None; self.camera_at = None
        self.fade_color = (0, 0, 0); self.fade_frames = 0; self.fade_total = 1
        self.pad_held = 0; self.pad_pressed = 0; self.pad_released = 0; self.pad_forced = None
        for n, (addr, t) in elayout.GLOBALS.items():
            if n in ('rng_seed', 'ent_count') or hasattr(self, n): continue
            setattr(self, n, None if t in ('ptr', 'fxptr') else 0)
        self.debug_mode = 0; self.serial_counter = 0
        self.new_game_state(handoff)
        if handoff is not None:                                  # a continued game arrives at its respawn point
            map_id = self.warp_map
            start = (self.warp_x / 65536, self.warp_y / 65536, self.warp_z / 65536)
            if bytes(handoff[0x76C:0x770]) == b'XPOS':           # a BizHawk state's exact place (bizhawk_state.py)
                import struct
                start = tuple(c / 65536 for c in struct.unpack_from('<iii', bytes(handoff), 0x770))
                if len(handoff) >= 0x780 and struct.unpack_from('<i', bytes(handoff), 0x77C)[0] == 0:
                    self._hud_hidden_state = True                # the state had the HUD away: no slide in
        self.vm = eventvm.VM(self)
        self.controls = Controls()
        from settings_screen import SettingsScreen
        self.settings_screen = SettingsScreen(self); self.controls_screen = self.settings_screen
        from inventory_ui import InventoryUI
        self.inventory_ui = InventoryUI(self)
        from message_ui import MessageUI
        self.message_ui = MessageUI(self, self.inventory_ui)
        Actor.game = self
        from engine import spriteinfo as _si                     # the shared sprites' info block, as the
        _gi = ASSETS / 'sprites' / 'global_info.bin'             # game loads it at boot (0x800CBF58 ->
        if _gi.exists(): _si.load_block(self, _si.GLOBAL_INFO, 0x800CBF58, _gi.read_bytes())   # 0x801F3958)
        self.ui = self.ui_call
        self.keeps_scroll = lambda n: lr_swap.keeps_scroll(self, n)    # Mods > Magic & weapon swapping
        self.inv_circle = lambda: lr_swap.menu_circle(self)
        self.picked_weapon = lambda grp: lr_swap.picked_weapon(self, grp)
        self.lang = self.pick_lang(self.settings.get('text_lang', 'us'))        # Options > Dialogue & font
        self.game_font.set_lang(self, self.lang)
        self.inventory_ui.set_lang(self.lang)
        self.install_texts()
        from engine import message as _emsg
        _emsg.msg_boot(self)                                     # 0x80045F00 at boot
        if self.lang == 'jp': self.mem.w16(_emsg.NAME_CFG + 2, 144)   # JP 0x800A81D8: the plate 4 px lower
        alundra = Sprite.get(ASSETS / 'sprites' / 'global' / '000')
        self.player = Actor(alundra, 0, 0, 0); self.player.estatus = 2; self.player.slot = 0
        self.player.flags = GLOBAL_HEADERS.get('0', {}).get('flags', 0x188) | 0x100   # Alundra's sprite header (always gravity)
        h0 = GLOBAL_HEADERS.get('0', {})
        if h0.get('hitbox_size'): self.player.set_hitbox(h0['hitbox_offset'], h0['hitbox_size'])
        import combat as _combat
        self.combat = _combat.Combat(ASSETS); self.combat.player = self.player
        self.combat.set_balance(self.settings.get('balance', 'us'))      # Options > Balance
        self.combat.attach(self.player, 0)
        self.combat.equip_power_fn = lambda anim: self.combat.equip_power(
            self.weapon_item(), self.ring_item(),
            next((i for i in (20, 19, 18, 17) if self.inventory.get(i)), 0), anim)
        import sprite_ai as _sai
        self.sprite_ai = _sai.SpriteAI(self, ASSETS)
        self.player.hp_max = emenu_life_max(self); self.player.hp = emenu_life(self)   # 0x80031F74
        self.talk = None
        pf = Game.PRESET_FLAGS                                   # (tests: the story flags a recording of
        if pf:                                                   # the original was made with, before the
            for i, b in enumerate(pf): self.mem.w8(0x801DD334 + i, b)   # map loads)
        self.load_map(map_id, start)
        from engine import screen as _escreen
        info = self.map.data.get('info', {})                     # the first map comes in like any other (effect 0)
        _escreen.arrival(self, info.get('e', 0) * 8 & 0xFF, info.get('f', 0) * 8 & 0xFF,
                         info.get('anim_land_floor', 0) * 8 & 0xFF, 0)
        if not new_game: self.set_flag(0x67E, True)              # a start mid-game (a map number, --wake-up):
                                                                 # the HUD is allowed, as after the shipwreck
        self.hud_show()                                          # 0x8002C568: 0x8004D24C after the first arrival
        if not new_game and handoff is None: self.dev_respawn()   # a start mid-game: its map is the respawn point
        self.front = None                                        # frontend.py: the boot / ending programs
        if boot:
            import frontend
            self.front = frontend.FrontEnd(self, 'boot')

    # ---- the engine's view of the game (engine/*.py reads these)
    rng_seed = property(lambda s: gamerng.state[0], lambda s, v: gamerng.state.__setitem__(0, v & 0xFFFFFFFF))
    class EntView:
        """g.ent[i] as the engine sees the table: a free slot reads as a blank record."""
        class Free:
            """A free slot's record.  Its words read as 0, except the AI words (+0x248..) and the
            state bytes (+0x274), which are memory like any other: the game's routines still count
            and mark in them (C47's death runs 0x80083394 on slot head + 8 whatever is there), and
            they hold what the last entity in the slot left.  Its map record number is -1:
            0x80038F24 copies the blank record 0x801DDA78 over a freed slot and 0x8003BB4C sets
            that record's +0x48 to -1, so a script / AI naming record 0 (C66-C68 waiting for the
            Coastal Cave pillar to break) does not find the freed slot."""
            estatus = 0; frozen = 0; flags = 0; ref_id = -1; holder = None; parent = None; riding = None
            x_collision = None; touching = None; carried = None; logic = None; alive = False
            def __init__(self, i):
                object.__setattr__(self, 'slot', i)                         # which slot (0x8003A964 fills it)
                object.__setattr__(self, 'ai', S16List([0] * 10)); object.__setattr__(self, 'bytes', U8List([0, 0, 0, 0]))
            def __getattr__(self, n): return 0
            def __setattr__(self, n, v): pass
        def __init__(self, g): self.g = g; self.free = [self.Free(i) for i in range(64)]; self.last = [None] * 64
        def __getitem__(self, i):
            a = self.g.slots[i]
            if a is not None:
                self.last[i] = a; return a
            f = self.free[i]; prev = self.last[i]
            if prev is not None:                                            # the slot was just vacated:
                if isinstance(getattr(prev, 'ai', None), list): object.__setattr__(f, 'ai', prev.ai)   # its words
                if isinstance(getattr(prev, 'bytes', None), list): object.__setattr__(f, 'bytes', prev.bytes)   # stay
                self.last[i] = None
            return f
        def __len__(self): return 64
        def __iter__(self): return (self[i] for i in range(64))

    @property
    def ent(self):
        v = self.__dict__.get('_entview')                    # (setdefault built a new 64-slot view on
        if v is None: v = self.__dict__['_entview'] = Game.EntView(self)   # every access, then dropped it)
        return v
    ent_count = property(lambda s: s.count)
    fx = property(lambda s: s.effects.fx)

    def effect_started(self, e): self.effects.started(e)

    class Cell8:
        """A map square as the engine reads it (8 bytes: walk, ground, slope, height, +4 the top
        tile, +6 the index of its list of upright pieces - -1 none): flags = walk | ground << 8,
        height, f6 (+6).  A cut bush (0x8003B104) sets +6 to -1: its upright pieces (the bush)
        go, the floor tile stays."""
        def __init__(self, game, c): self.__dict__['g'] = game; self.__dict__['c'] = c
        flags = property(lambda s: s.c[0] | s.c[1] << 8 if s.c else 0x40)
        height = property(lambda s: s.c[3] if s.c else 0)
        f6 = property(lambda s: (0 if s.c[5] else 0xFFFF) if s.c else 0xFFFF)
        def __setattr__(self, n, v):
            c = self.c
            if c is None: return
            if n == 'flags': c[0] = v & 0xFF; c[1] = (v >> 8) & 0xFF
            elif n == 'height': c[3] = v & 0xFF
            elif n == 'f6' and (v & 0xFFFF) == 0xFFFF: c[5] = []; c[6] = 0; self.g.map.build_pieces()

    def cell8(self, x, y): return Game.Cell8(self, self.map.cell(x, y))

    def map_info_byte(self, off):
        info = self.map.data.get('info', {})
        return {9: info.get('anim_delete_wall', 0), 0xA: info.get('c', 0), 0xB: info.get('balance_level', 0),
                8: info.get('slide_effect', 0), 0xC: info.get('e', 0), 0xD: info.get('f', 0),
                0xE: info.get('anim_land_floor', 0), 0xF: info.get('h11', 0)}.get(off, 0)

    class Portal:
        def __init__(self, w):
            self.x1, self.y1, self.x2, self.y2 = [v - 256 if v > 127 else v for v in w['rect']]
            self.x, self.y, self.z = w['x'], w['y'], w['z']; self.flags = w['flags']; self.map = w['map']

    def portal_map(self, rec):
        """0x800318FC: the door's map number through the destination table 0x801DD434 (op 38)."""
        import vm_game_30
        return vm_game_30.portal_map(self, rec)

    def balance_byte(self, e, off):
        b = getattr(e, 'balance', None)
        if off == 0xE: return len(b['attacks']) if b else 0
        return 0

    def item_count(self, n):
        from engine import menu as emenu
        return emenu.has_item(self, n)

    def equipped_weapon_kind(self): return self.weapon_item()

    def selected_item(self):
        from engine import menu as emenu
        return emenu.selected_item(self)

    def take_hit(self, e):
        """0x8003ACAC: life lost to the attack that touched e; 1 when it died."""
        if e is self.player:
            self.drop_carried_hit = True
            self.combat.damage(e, self.player_responses())
        else:
            self.combat.damage(e, e.balance['responses'] if e.balance else [0x80] * 11)
        return 1 if e.hp == 0 else 0

    # ---- flags: numbers with bit 15 are the per-map temporary bank
    FLAGS, MAP_FLAGS = 0x801DD334, 0x801E6378

    def _flag_word(self, n):
        """Game flag n is bit n & 31 of the word at 0x801DD334 (0x801E6378 for n & 0x8000) +
        ((n >> 3) & 0xFFC) (0x80084060 / 0x800840B8 / 0x80084118).  The first bank is inside the
        block a save holds (0x801DD2D8 + 0x758); the second is not saved."""
        n &= 0xFFFF
        return (self.MAP_FLAGS if n & 0x8000 else self.FLAGS) + ((n >> 3) & 0xFFC), n & 31

    def flag(self, n):
        a, b = self._flag_word(n)
        return bool(self.mem.u32(a) >> b & 1)

    def set_flag(self, n, on):
        a, b = self._flag_word(n)
        v = self.mem.u32(a)
        self.mem.w32(a, (v | 1 << b) if on else (v & ~(1 << b) & 0xFFFFFFFF))

    # ---- the message window (engine/message.py keeps its state in g.mem)
    MSG_UI = (0x80048780, 0x800845E8, 0x80087764, 0x800482A0, 0x80083EE4, 'jp_glyphs')
    GLOBAL_TEXT_AT, MAP_TEXT_AT, NAMES_AT, SCRATCH_TEXT = 0x8013A280, 0x8018EEBC, 0x8012CEA2, 0x8018E000
    ATTACK_RECS = 0x801FE000                                 # 65 x 4 bytes: each slot's attack record (+0x1C8)
    MAP_INFO_BLOCK = 0x801FE200                              # the loaded map's 16-byte info (*(0x801F0070))

    def ui_call(self, addr, *args):
        if addr == 0x80048780 and len(args) > 1 and args[1] == 0x801D7F40: return 0   # YES / NO texts (drawn from 0x8013D7FC)
        if addr in self.MSG_UI: return self.message_ui.ui(addr, *args)
        if addr == 0x8004D1B8: self.hud.hide(); return 0       # the menu opens: the HUD slides out
        if addr == 0x8004D24C: self.hud_show(); return 0       # ... and back in when it closes
        if addr == 0x8004AD18: self.music_stop(bool(args and args[0])); return 0   # music stop / fade
        if addr == 0x8004AC90: self.music_play(); return 0     # music (re)start
        if addr == 0x8005CB94: self.xa_play(args[0]); return 0 # an XA clip (the rare-item jingle)
        if addr == 0x8005C990: return int(self.xa_busy())      # ... still streaming
        if addr == 0x8005C8DC: self.snd.xa_stop(); return 0
        return self.inventory_ui.ui(addr, *args)

    @staticmethod
    def _text_table(strings, enc='latin-1'):
        """128 u16 offsets, then the strings (as the game loads a text block)."""
        head = bytearray(256); body = bytearray()
        for i in range(128):
            t = strings.get(str(i))
            if t is None: off = 0xFFFF
            else:
                off = 256 + len(body); body += t.encode(enc, 'replace') + b'\0'
            head[2 * i:2 * i + 2] = off.to_bytes(2, 'little')
        return bytes(head + body)

    def install_texts(self):
        """The shared texts at *(0x801F4050) and the speakers' names (0x800C5E74 + 4 * sprite,
        sprites 0x100-0x1FF; ETC_USA.R's name table) where the game keeps them."""
        m = self.mem
        if getattr(self, 'lang', 'us') == 'jp' and self.install_texts_jp(): return
        if getattr(self, 'lang', 'us') in EU_LANGS and self.install_texts_eu(): return
        f = ASSETS / 'text' / 'global_strings.json'
        if f.exists():
            data = self._text_table(json.loads(f.read_text(encoding='utf-8')))
            for i, c in enumerate(data): m.w8(self.GLOBAL_TEXT_AT + i, c)
            m.w32(0x801F4050, self.GLOBAL_TEXT_AT)
        from engine import choice as _choice
        raw = ASSETS / 'text' / 'ETC_USA.R'                      # tools: the disc's DATA/ETC_USA.R
        if raw.exists():
            _choice.install_etc_file(self, raw.read_bytes())    # 0x8002C810 at boot: the file at 0x8012B9E0,
            _choice.boot_names(self)                            # then the item / chapter / speaker names
            return
        et = ASSETS / 'text' / 'etc_usa.json'                    # (an older export: the texts only)
        etc = json.loads(et.read_text(encoding='utf-8')) if et.exists() else {}
        _choice.install_etc(self, {int(k): v for k, v in etc.get('etc', {}).items()})    # 0x8012B9E0
        names = etc.get('table', {})
        a = self.NAMES_AT
        for i in range(0x100):
            nm = names.get(str(i))
            if nm is None: m.w32(0x800C5E74 + 4 * (0x100 + i), 0); continue
            m.w32(0x800C5E74 + 4 * (0x100 + i), a)
            for c in nm.encode('latin-1', 'replace') + b'\0': m.w8(a, c); a += 1

    _JP_MAPS = None

    def jp_texts(self):
        """assets/text_jp (tools/remake_export_jp.py): the JP disc's texts."""
        if Game._JP_MAPS is None:
            d = ASSETS / 'text_jp'
            if not (d / 'maps.json').exists(): Game._JP_MAPS = {}; return None
            Game._JP_MAPS = {'maps': json.loads((d / 'maps.json').read_text(encoding='utf-8')),
                             'global': json.loads((d / 'global_strings.json').read_text(encoding='utf-8')),
                             'etc': json.loads((d / 'etc.json').read_text(encoding='utf-8'))}
        return Game._JP_MAPS or None

    def install_texts_jp(self):
        """The JP texts where the US build keeps its own (the JP game has them in its EXE; the
        remake's logic is the US one, so they go where ETC_USA.R's would): the shared texts,
        the 'etc' table in the US numbering, then the item / chapter / speaker names from it."""
        t = self.jp_texts()
        if not t: return False
        m = self.mem
        data = self._text_table(t['global'], 'shift_jis')
        for i, c in enumerate(data): m.w8(self.GLOBAL_TEXT_AT + i, c)
        m.w32(0x801F4050, self.GLOBAL_TEXT_AT)
        from engine import choice as _choice
        _choice.install_etc(self, {int(k): v for k, v in t['etc']['etc'].items()}, 'shift_jis')
        _choice.boot_names(self)
        return True

    _EU = {}

    def eu_texts(self, lang):
        """assets/text_<lang> (tools/remake_export_eu.py): a European disc's texts (Windows-1252)."""
        if lang not in Game._EU:
            d = ASSETS / f'text_{lang}'
            if not all((d / f).exists() for f in ('maps.json', 'global_strings.json', 'ETC.R', 'etc.json')): Game._EU[lang] = None
            else:
                Game._EU[lang] = {'maps': json.loads((d / 'maps.json').read_text(encoding='utf-8')),
                                  'global': json.loads((d / 'global_strings.json').read_text(encoding='utf-8')),
                                  'etc': json.loads((d / 'etc.json').read_text(encoding='utf-8')),
                                  'etc_file': (d / 'ETC.R').read_bytes()}
        return Game._EU[lang]

    def install_texts_eu(self):
        """A European disc's texts where the US build keeps its own: the shared texts, its
        ETC_RES.R (the same numbering as ETC_USA.R) at 0x8012B9E0, then the item / chapter /
        speaker names from it."""
        t = self.eu_texts(self.lang)
        if not t: return False
        m = self.mem
        data = self._text_table(t['global'], 'cp1252')
        for i, c in enumerate(data): m.w8(self.GLOBAL_TEXT_AT + i, c)
        m.w32(0x801F4050, self.GLOBAL_TEXT_AT)
        from engine import choice as _choice
        _choice.install_etc_file(self, t['etc_file'])
        _choice.boot_names(self)
        return True

    def pick_lang(self, lang):
        """The language asked for if its texts (and, for Europe, its font) were exported, else US."""
        if lang == 'jp' and self.jp_texts(): return 'jp'
        if lang in EU_LANGS and self.eu_texts(lang) and GameFont.eu_font_ok(lang): return lang
        return 'us'

    def text_enc(self):
        lang = getattr(self, 'lang', 'us')
        return 'shift_jis' if lang == 'jp' else 'cp1252' if lang in EU_LANGS else 'latin-1'

    def set_lang(self, lang):
        """Options > Dialogue & font: the texts, the font (Europe), the message window's JP rules
        and the JP window art.  Waits while a message, the name plate or a choice is up (their
        text is in the old language)."""
        lang = self.pick_lang(lang)
        if lang == getattr(self, 'lang', 'us'): return True
        from engine import message as _emsg, menu as _em
        if self.mem.s32(_emsg.FLAGS) or any(_em.task_running(self, t) for t in (0, 3, 9, 10, 0xC)): return False
        self.lang = lang
        self.game_font.set_lang(self, lang)
        self.inventory_ui.set_lang(lang)
        self.install_texts()
        if getattr(self, 'map', None) is not None: self.install_map_texts()
        self.mem.w32(_emsg.CWAIT, 0xB4 if lang == 'jp' else 0x168)
        self.mem.w16(_emsg.NAME_CFG + 2, 144 if lang == 'jp' else 140)      # JP 0x800A81D8: 4 px lower
        return True

    def install_map_texts(self):
        if getattr(self, 'lang', 'us') == 'jp' and self.jp_texts():
            data = self._text_table(self.jp_texts()['maps'].get(str(self.map.id), {}), 'shift_jis')
            for i, c in enumerate(data): self.mem.w8(self.MAP_TEXT_AT + i, c)
            self.mem.w32(0x801F3150, self.MAP_TEXT_AT)
            return
        lang = getattr(self, 'lang', 'us')
        if lang in EU_LANGS and self.eu_texts(lang):
            data = self._text_table(self.eu_texts(lang)['maps'].get(str(self.map.id), {}), 'cp1252')
            for i, c in enumerate(data): self.mem.w8(self.MAP_TEXT_AT + i, c)
            self.mem.w32(0x801F3150, self.MAP_TEXT_AT)
            return
        data = self._text_table(self.map.data.get('strings', {}))
        for i, c in enumerate(data): self.mem.w8(self.MAP_TEXT_AT + i, c)
        self.mem.w32(0x801F3150, self.MAP_TEXT_AT)

    def _get_dialogue(self):
        """The open message's text (None once the window has gone: 0x80106AFC == 0)."""
        from engine import message as emsg
        if self.mem.s32(emsg.FLAGS) == 0: return None
        return emsg._cstr(self, emsg.TEXT).decode('latin-1')

    def _set_dialogue(self, v):
        if v is not None: return
        from engine import message as emsg, menu as emenu
        m = self.mem
        if m.s32(emsg.FLAGS):
            m.w16(emsg.CFG, m.u16(emsg.SLIDE + 0x18))
            m.w16(emsg.CFG + 2, m.u16(emsg.SLIDE + 0x1A))
        m.w32(emsg.FLAGS, 0)
        for n in (0, 0xC): m.w16(emenu.TASKS + 0x1C * n, 0)
        if m.u16(emsg.NAME_FLAGS):
            m.w16(emsg.NAME_CFG, m.u16(emsg.NAME_SLIDE + 0x18)); m.w16(emsg.NAME_CFG + 2, m.u16(emsg.NAME_SLIDE + 0x1A))
        m.w16(emsg.NAME_FLAGS, 0)
        self.mode_flags &= ~0x18

    dialogue = property(_get_dialogue, _set_dialogue)

    def msg_start(self, n, mode):
        """Script op 0D / 5C / C4: 0x80042F74 (text n, lock mode); the speaker's portrait goes up
        when the window opens."""
        from engine import message as emsg
        return emsg.msg_start(self, n, mode)

    def msg_name(self, who):
        from engine import message as emsg
        if who is not None and who >= 0: emsg.name_open(self, who)
    msg_voice = message_name = msg_name

    TALK_EVERY = 8                       # frames between talk sounds at the game's pace (2 letters x 4 frames)

    def talk_gate(self, v):
        """engine/message.py asks before each talk sound (every other letter, voice v).  At Normal
        speed, and whenever Square speeds the text up (print mode bit 0, the game's own fast
        printing), the game's own.  With Mods > Text speed / Instant text the letters come
        faster than the game ever prints them by itself, so the voice keeps the Normal pace:
        a sound at most every 8 frames, and only while letters are being printed (one that
        comes too early waits for its turn; if the text pauses or stops, it is dropped)."""
        from engine import message as emsg
        if not self._text_mod_on: return True
        if self.mem.s32(emsg.PMODE) & 1 and self.pad_held & 0x80: return True
        self._talk_letter = self._talk_clock
        if self._talk_clock - self._talk_last >= self.TALK_EVERY:
            self._talk_last = self._talk_clock; self._talk_wait = None
            return True
        self._talk_wait = v                                  # (one at most: no backlog)
        return False

    def _talk_pace(self):
        v = self._talk_wait
        if v is None: return
        if self._talk_clock - self._talk_letter > 4:          # no letter for longer than a Normal letter
            self._talk_wait = None; return                    # takes: the text paused, the voice stops
        if self._talk_clock - self._talk_last < self.TALK_EVERY: return
        self._talk_last = self._talk_clock; self._talk_wait = None
        ecore.play_sound(self, v + 0x4F)

    _text_mod_on = False
    _talk_clock = 0                      # counts UI frames (message_tick)
    _talk_last = -99
    _talk_letter = -99
    _talk_wait = None

    def message_tick(self):
        """F5 > Mods > Text speed: 1.5x / 2x run the printing step an extra half / whole time
        a frame; F5 > Mods > Instant text prints up to the next stop (a wait, a scroll or the
        end) at once.  Wherever the text prints by itself (print mode bit 1, 0x80107460): the
        ordinary windows (mode 3) and cutscenes that only stop Square from speeding it (op 4C 2,
        the Lars and Melzas dream and the like - their scripts wait for a flag the text sets at
        its last letter, so the scene follows the faster text).  Not where the script hands out
        the letters itself (mode 4, op 4D)."""
        from engine import message as emsg, menu as emenu
        from settings_screen import EXTRA_PRINTS
        st = self.settings
        sp = 0 if st.get('instant_text') else st.get('text_speed', 1)
        if getattr(self, 'cur_map', None) == 440 and getattr(self, '_text_num', None) in range(0x83, 0x8A):
            sp = 1                                           # Meia's dream "I spy a cutie guy" game (map 440
                                                             # texts 3-9): its flags are timed by the printing
        m = self.mem
        running = emenu.task_running(self, 0)
        if not running: self._talk_wait = None               # the window has gone: the voice stops
        self._text_mod_on = sp != 1 and running and bool(m.s32(emsg.PMODE) & 2)
        if not self._text_mod_on:
            self._text_extra = 0.0; self._talk_pace(); return
        def printing():
            return not (m.s32(emsg.FLAGS) & 3 or m.s32(emsg.ENDED) or m.s32(emsg.SCROLLING) or m.s32(emsg.PMODE) & 8)
        arrow_before = m.s32(emsg.ARROW)
        if sp == 0:                                          # instant
            for _ in range(0x960):
                if not printing() or not m.s32(emsg.PMODE) & 2: break
                pos = m.s32(emsg.POS); m.w32(emsg.CD, 1)
                emsg.msg_print(self)
                if m.s32(emsg.POS) == pos and m.s32(emsg.CD) != 1: pass
        else:
            self._text_extra = getattr(self, '_text_extra', 0.0) + EXTRA_PRINTS.get(sp, 0.0)
            while self._text_extra >= 1.0:
                self._text_extra -= 1.0
                if printing(): emsg.msg_print(self)
        if not m.s32(emsg.FLAGS) & 3:
            # the extra prints came after the task's frame placed the line sprites (or before it
            # ever did, the frame the window finished sliding in): place them again, else this
            # frame shows the lines where the last window had them
            m.w32(emenu.CUR_TASK, emenu.TASKS)
            if m.s32(emsg.ARROW) and not arrow_before:
                emsg.msg_draw(self, emenu.CUR_TASK)          # a stop reached: the "more" marker placed too,
            else:                                            # as at 1x (print, then draw, the same frame)
                emsg._place_lines(self, emenu.CUR_TASK)      # (task 0)
        self._talk_pace()

    # ---- services used by the script machine
    def open_message(self, row, speaker, mode=0):
        """0x80042F74 / 0x8004608C: the window opens (when none is open) and sets mode flag
        0x10 when mode == 1 (Alundra waits, the world goes on) else 8 (everything stops:
        RunMapEvents and EntityFrame skip while mode_flags & 0x48) until it closes."""
        """A script row's text (the remake's own path when the text index is not known): the
        same window, opened by 0x8004608C."""
        from engine import message as emsg
        if self.dialogue is not None: return False
        text = (row or {}).get('settings') or ''
        if ' · ' in text: text = text.split(' · ', 1)[1]
        data = text.encode('latin-1', 'replace')[:0x900] + b'\0'
        for i, c in enumerate(data): self.mem.w8(self.SCRATCH_TEXT + i, c)
        self._text_num = None
        return bool(emsg.msg_open(self, self.SCRATCH_TEXT, mode))

    def close_message(self):
        """The window closed: mode flags 8 / 0x10 off, the portrait flies back."""
        from engine import portrait as eport
        self.mode_flags &= ~0x18
        eport.portrait_back(self)

    # ---- the HUD portrait (engine/portrait.py: the game's quad at 0x801EF384 and its flight)
    def _portrait_file(self, sp):
        f = sp.folder / 'portrait.png'
        if not f.exists(): return None
        cache = self.__dict__.setdefault('_portraits', {})
        if f not in cache: cache[f] = pygame.image.load(str(f)).convert_alpha()
        return cache[f]

    def message_portrait(self, e):
        """0x80059AE4 (script ops 0D / 5C / C4, every frame they run): the speaker's face (sprite
        flag 0x800000: image set 0 of its sprite) flies to (8, 0x74) unless one is up."""
        from engine import portrait as eport, entity as eent
        sp = getattr(getattr(e, 'anim', None), 'sprite', None)
        img = self._portrait_file(sp) if sp is not None else None
        if img is None or getattr(e, 'slot', None) is None: return
        a = eent.ent_addr(e)
        eport.portrait_speaker(self, a + 0x114, a + 0x118, a + 0x11C, 0x801EF434, 0x801EF438,
                               0, 0, 0x30, 0x38, 0, 0, img=img)
    msg_speaker = message_portrait

    def portrait_set(self, img):
        """The picture of the quad that has just started (None: Alundra's, the menu's)."""
        if img is None:
            sp = Sprite.get(ASSETS / 'sprites' / 'global' / '000')
            img = self._portrait_file(sp) if sp is not None else None
        self.portrait_img = img

    def draw_portrait(self, v):
        """The quad as 0x80059D5C left it: its corners and its colour (0x80 = as drawn; above
        that whiter, as the PS1 modulates)."""
        from engine import portrait as eport
        if not getattr(self, 'portrait_shown', False): return
        img = getattr(self, 'portrait_img', None)
        if img is None: return
        m = self.mem; pr = eport.PRIM + m.s32(eport.BUFI) * 0x28
        x0, y0, x3, y3 = m.s16(pr + 8), m.s16(pr + 0xA), m.s16(pr + 0x20), m.s16(pr + 0x22)
        w, h, c = x3 - x0, y3 - y0, m.u8(pr + 4)
        if w <= 0 or h <= 0 or c == 0: return
        pic = img if (w, h) == img.get_size() else pygame.transform.scale(img, (w, h))
        if c != 0x80:
            pic = pic.copy()
            try:
                import numpy as np
                a = pygame.surfarray.pixels3d(pic)
                c5 = np.minimum(31, (a.astype(np.int32) >> 3) * c >> 7)
                a[...] = (c5 << 3 | c5 >> 2).astype(np.uint8); del a
            except ImportError: pass
        v.blit(pic, (x0, y0))

    def toast(self, text, game=False): self.toasts.append([text, 150, game])   # game: in the game's font

    # ---- the game's stats and items (g.mem, laid out as the game keeps them; engine/menu.py)
    def new_game_state(self, handoff=None):
        """What boot and 0x80031CBC leave: the boot words (no debug shortcuts on Start, the pad
        repeat delay of 20 frames, the event handles the card services answer on, the memory
        card), then the game's start - a new game (0x80010000 = 0: life 10, the starting items, the
        sword) or a continued one (the History Book's record handed over at 0x80010000)."""
        from engine import gamestart as egs, bios_card as ebios
        m = self.mem
        m.w32(0x800AA118, 1)                                    # set at boot: no debug shortcuts on Start
        m.w32(0x801DDA38, 20); m.w32(0x801DDA3C, 0)             # pad 1: first repeat after 20 frames, then every frame
        for a, h in ebios.HANDLES.items(): m.w32(a, h)          # OpenEvent at boot: SwCARD / HwCARD
        self.card_bios = card_slots(self.settings)
        m.w32(0x80119AE8, 0x801DD81C); m.w16(0x801DD81C + 0xC, -1 & 0xFFFF)
        h = egs.handoff(self)
        if handoff is not None:
            for i, c in enumerate(handoff[:0x76C]): m.w8(h + i, c)
            m.w32(h, 1)
        else:
            m.w32(h, 0)
        egs.game_start(self)

    def _stat(self, off): return self.mem.s16(self.mem.u32(0x80119AE8) + off)
    def _set_stat(self, off, v): self.mem.w16(self.mem.u32(0x80119AE8) + off, v)
    gilder = property(lambda s: s._stat(8), lambda s, v: s._set_stat(8, v))
    falcons = property(lambda s: s._stat(0xE), lambda s, v: s._set_stat(0xE, v))

    def anim_speed(self, e, anim):
        """An animation's speed (the sprite header's animation table, +8 of entry anim)."""
        sp = e.anim.sprite if getattr(e, 'anim', None) is not None else None
        return sp.speed(anim) if sp is not None else 0

    def unported(self, addr, *args):
        """A game routine the engine calls that the remake has no port of (presentation, mostly)."""
        f = getattr(self, 'ui', None)
        return f(addr, *args) if f is not None else 0

    # ---- settings (settings.json, F5 page)
    def set_display(self):
        """The window (or fullscreen), flipped on the monitor's refresh when VSync is on (pygame
        only offers vsync on its SCALED renderer; the window is then set back to the chosen size,
        so the picture is not scaled twice).  pacing.py times the game frames."""
        s = self.settings
        key = (s['scale'], s.get('fullscreen'), s.get('vsync', True))
        cur = pygame.display.get_surface()
        if cur is not None and getattr(Game, '_shown_key', None) == key:
            self.screen = cur; self._display_key = key                  # (a new game keeps the window)
            self.vsync = getattr(Game, '_shown_vsync', False); return
        if cur is not None and (getattr(Game, '_shown_vsync', False) or s.get('vsync', True)):
            if not getattr(pygame, 'IS_CE', False):
                # pygame 2.6's event queue crashes natively (a freed Event type) on the first event
                # after display.quit / init - the Options crash.  pygame-ce does not; with plain
                # pygame the new window settings wait for the next start.
                self.screen = cur
                if not getattr(self, '_restart_told', False):
                    self._restart_told = True
                    try: self.toast('window settings apply on the next start')
                    except Exception: pass
                return
            cap = pygame.display.get_caption()                         # SDL cannot give a window that had
            pygame.display.quit(); pygame.display.init()              # a renderer a plain surface (or back):
            if cap: pygame.display.set_caption(*cap)                  # make the window again
        try: pygame.display.set_icon(pygame.image.load(str(Path(__file__).resolve().parent / 'alundra_icon.png')))
        except (pygame.error, OSError, NameError): pass               # the window's corner icon
        fs = s.get('fullscreen')
        flags = pygame.FULLSCREEN if fs else 0
        size = (0, 0) if fs else (VIEW_W * s['scale'], VIEW_H * s['scale'])
        self.vsync = False
        if s.get('vsync', True):
            try:
                vsize = pygame.display.get_desktop_sizes()[0] if fs else size
                self.screen = pygame.display.set_mode(vsize, flags | pygame.SCALED, vsync=1)
                if not fs:
                    try:
                        from pygame._sdl2.video import Window
                        Window.from_display_module().size = vsize            # SCALED may have enlarged it
                    except Exception:
                        pass
                self.vsync = True
            except Exception:
                self.vsync = False
        if not self.vsync:
            try: self.screen = pygame.display.set_mode(size, flags)
            except pygame.error: self.screen = pygame.display.set_mode((VIEW_W * SCALE, VIEW_H * SCALE))
        self._display_key = key; Game._shown_key = key; Game._shown_vsync = self.vsync
        if getattr(self, 'pacer', None) is not None: self.pacer.reset(self.vsync)

    def apply_settings(self):
        if Sprite.use_old(self.settings.get('sprite_set') == 'old'):          # Options > Sprite Graphics
            ui = getattr(self, 'inventory_ui', None)
            if ui is not None and hasattr(ui, 'shaded'): ui.shaded.clear()   # (tinted copies of the old set)
        self.combat.set_balance(self.settings.get('balance', 'us'), getattr(self, 'actors', ()))
        self._lang_wanted = self.settings.get('text_lang', 'us')
        if self.set_lang(self._lang_wanted): self._lang_wanted = None
        if self._display_key != (self.settings['scale'], self.settings.get('fullscreen'), self.settings.get('vsync', True)):
            self.set_display()
        self.apply_volume()

    def apply_volume(self):
        self.snd.apply_volume()

    def view_rect(self):
        """Where the 320x240 picture goes in the window (kept 4:3, centred in fullscreen)."""
        W, H = self.screen.get_size()
        k = min(W / VIEW_W, H / VIEW_H)
        if self.settings.get('integer_scale') and k >= 1: k = int(k)   # Options > Integer Scaling: whole multiples only
        w, h = int(VIEW_W * k), int(VIEW_H * k)
        return pygame.Rect((W - w) // 2, (H - h) // 2, w, h)

    # ---- audio: the game's sound manager (sound_system.py)
    def debug_dump(self):
        """F6: what the renderer used this frame, for bug reports - debug_dumps/<time>/ with the
        picture, the map's squares as they are now, the tile pieces per row (and the rows the
        renderer skips), camera, map, Alundra and every object."""
        import time
        folder = ROOT / 'debug_dumps' / time.strftime('%Y%m%d-%H%M%S')
        try:
            folder.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.view, str(folder / 'view.png'))
            mp = self.map; cam = self.camera(); p = self.player
            top, bottom = cam[1] - TH, cam[1] + VIEW_H
            spans = getattr(mp, 'row_span', {})
            rows = {}
            for y, pieces in mp.pieces_by_row.items():
                sp = spans.get(y)
                rows[y] = {'span': sp, 'drawn': sp is None or (sp[1] > top and sp[0] < bottom),
                           'pieces': [[c, px, py, w, th, bool(mp.tile_rect(c))] for c, px, py, w, th in pieces]}
            actors = [{'sprite': getattr(a, 'sprite_index', None), 'slot': getattr(a, 'slot', None),
                       'pos': [a.px / 65536, a.py / 65536, a.pz / 65536], 'anim': a.target_anim,
                       'alive': getattr(a, 'alive', None), 'status': getattr(a, 'estatus', None)} for a in self.actors]
            doc = {'map': self.cur_map, 'camera': list(cam), 'margin': mp.margin, 'size': [mp.w, mp.h],
                   'player': [p.px / 65536, p.py / 65536, p.pz / 65536, p.target_anim],
                   'mode_flags': self.mode_flags, 'settings': dict(self.settings),
                   'cells': mp.cells, 'rows': rows, 'actors': actors,
                   'effects': [[e.index, e.b70, e.x / 65536, e.y / 65536, e.z / 65536] for e in self.effects.list]}
            (folder / 'state.json').write_text(json.dumps(doc, default=str))
            self.mem_dump = folder / 'ram.bin'
            try: (folder / 'ram.bin').write_bytes(bytes(self.mem.b))
            except Exception: pass
            self.toast(f'saved {folder.name} (debug_dumps)')
        except Exception as exc:
            self.toast(f'dump failed: {exc}')

    def magic_pair(self):
        """Magic and most magic: the stats halfwords +4 / +6 (0x8004F528 / 0x8004F45C)."""
        from engine import menu as emenu
        st = emenu._stats(self)
        return max(0, self.mem.s16(st + 4)), max(0, self.mem.s16(st + 6))

    def sound(self, n):
        """PlaySound 0x8004A128."""
        self.last_sound = n
        self.snd.play(n)

    def stop_sound(self, n): self.snd.stop(n)                  # 0x8004A7B4 (commands 75 / BE)
    def sound_volume(self, n, l, r): self.snd.volume(n, l, r)  # 0x8004A928 (commands AB / BF)
    def music_load(self, track, play): self.snd.music_load(track, play); self.music = self.snd.music   # A7
    def music_unload(self): self.snd.music_unload(); self.music = 0
    def music_play(self): self.snd.music_play()                # A5
    def music_stop(self, fade): self.snd.music_stop(fade)      # A6
    def music_loading(self): return self.snd.music_loading()  # A8

    def play_music(self, track):
        """A map's own music (map table): loaded and played when it differs from the current one."""
        if track is None or track < 0 or track == self.snd.music: return
        if track == 0: self.music_unload(); return
        self.music_load(track, True)

    def music_tick(self):
        self.snd.tick()                                        # 0x8004C454: the sound manager, every frame

    def effect(self, n, at=None):
        """Commands 90 / A2 / A3: SpawnSpriteEffect(n, 1): the record's effect, no area test."""
        e = self.effects.spawn_record(n, True, None)
        if e is not None and at is not None:
            e.x, e.y, e.z = int(at[0]) << 16, int(at[1]) << 16, (int(at[2]) << 16) + 1
        return e
    def warp(self, m, x, y, z): self.pending_warp = (m, x, y, z)

    def give_item(self, n):
        self.inventory[n] = self.inventory.get(n, 0) + 1
        name = ITEMS.get(str(n), {}).get('name') or f'item {n}'
        self.toast(f'Got {name}!'); return True

    def pad(self, mode):
        if self.pad_forced: return self.pad_forced[min(mode, 3)]
        return (self.pad_held, self.pad_pressed, self.pad_released, self.pad_pressed)[min(mode, 3)]

    def start_fade(self, color, frames, mode):
        """The old script fade hook: the overlay toward color in frames (abr 2 when mode 0, else 1)."""
        from engine import screen
        ov = screen.fade_state(self, 'fade_ov')
        ov.target = [c << 16 for c in color]; ov.on = 1; ov.keep = 0
        screen.ov_steps(self, 1 if mode else 2, max(1, frames))

    # ---- entities
    def make_actor(self, rec):
        mp = self.map
        sp = Sprite.get(mp.sprite_folder(rec['catalogue']))
        d = eventvm.CARDINAL[rec['flags'] & 3]
        a = Actor(sp, rec['x'] * 12 + 12, rec['y'] * 8 + 8, rec['z'] * 8, d)
        hdr = self.header(rec['catalogue'])
        if hdr:     # EntityManager.SpawnEntity: flags from the sprite header, hit box, built-in programs
            a.flags = hdr['flags']; a.set_hitbox(hdr['hitbox_offset'], hdr['hitbox_size'])
            a.sprite_programs = hdr['sprite_programs']; a.break_effect = hdr['break_effect']
        a.solid = bool(a.flags & 0x80)
        self.place(a, rec['z'] * 8 << 16)
        a.record = rec; a.ref_id = rec['index']; a.sprite_index = rec['catalogue']
        a.programs = {k: v for k, v in rec['programs'].items() if v}
        a.contents_flag = rec.get('collection_flag', 0)
        self.combat.attach(a, rec['catalogue'])
        self.sprite_ai.init_contents(a, rec, hdr)
        return a

    def take_slot(self, a):
        """AllocEntity 0x8003A3C8 + InitializeEntity 0x8003A5F8: the lowest free slot,
        status 1.  Its action word is the blank record's 0 (= A) unless this frame's
        dispatch already visited the slot (then -1): so an entity spawned by a program
        past the old entity count runs A at once, and every new entity runs A again on
        the next frame when it becomes status 2."""
        for i in range(1, 64):
            if self.slots[i] is None:
                self.slots[i] = a; a.slot = i; a.estatus = 1
                a.frame_counter = self.slot_fc[i]                      # AllocEntity clears nothing: the slot's
                self.serial_counter += 1; a.serial = self.serial_counter   # counter (+0x1C) went on while free
                a.cur_anim = ~a.target_anim; self.animate(a)          # InitializeEntity 0x8003A7A4
                a.action = None if i <= self.sel_count else 'A'
                if i > self.count: self.count = i                      # InitializeEntity: the count takes the
                if i > getattr(self, 'count0', 0): self.count0 = i     # record's index (its slot) at once
                return a
        a.slot = -1; a.alive = False
        return None

    def spawn_global(self, catalogue, px, py, pz, direction=0, owner=None):
        """SpawnWarpEntity with a global sprite (dropped items, effects with bodies).
        InitializeEntity 0x8003A5F8 stores the spawner at Entity+0x0C for global sprites
        too, so e.g. the Wind Scroll's whirlwinds are Alundra's children (script selector
        0x89, docs/2026-10-21-sanctuary-wind-scroll.txt)."""
        sp = Sprite.get(ASSETS / 'sprites' / 'global' / f'{catalogue:03d}')
        if sp is None: return None
        a = Actor(sp, 0, 0, 0, direction); a.px, a.py = px, py
        hdr = GLOBAL_HEADERS.get(str(catalogue))
        if hdr:
            a.flags = hdr['flags']; a.set_hitbox(hdr['hitbox_offset'], hdr['hitbox_size'])
            a.sprite_programs = hdr['sprite_programs']; a.break_effect = hdr['break_effect']
        a.solid = bool(a.flags & 0x80); a.programs = {}; a.parent = owner; a.sprite_index = catalogue
        self.place(a, pz)
        self.combat.attach(a, catalogue)
        self.sprite_ai.init_contents(a, None, hdr)                 # (InitializeEntity: every entity)
        if self.take_slot(a) is None: return None
        self.actors.append(a)
        return a

    def spawn_sprite(self, owner, is_map, index, px, py, pz, direction=0):
        """SpawnWarpEntity 0x80039B28: a sprite of this map (0x100 + index) or a global one."""
        cat = (0x100 + index) if is_map else index
        if not is_map: return self.spawn_global(cat, px, py, pz, direction, owner)
        sp = Sprite.get(self.map.sprite_folder(cat))
        if sp is None: return None
        a = Actor(sp, 0, 0, 0, direction); a.px, a.py = px, py
        hdr = self.header(cat)
        if hdr:
            a.flags = hdr['flags']; a.set_hitbox(hdr['hitbox_offset'], hdr['hitbox_size'])
            a.sprite_programs = hdr['sprite_programs']; a.break_effect = hdr['break_effect']
        a.solid = bool(a.flags & 0x80); a.programs = {}; a.parent = owner; a.sprite_index = cat
        self.place(a, pz)
        self.combat.attach(a, cat)
        self.sprite_ai.init_contents(a, None, hdr)
        if self.take_slot(a) is None: return None
        self.actors.append(a)
        return a

    def collect(self, item):
        """PlayerManager 0x80033F00: what picking up an item does."""
        p = self.player
        if item in (0x45, 0x46, 0x47, 0x48): self.gilder = min(9999, self.gilder + {0x45: 1, 0x46: 5, 0x47: 10, 0x48: 30}[item]); return
        if item == 0x54: p.hp = min(p.hp_max, p.hp + 2); return                       # small heart
        if item == 0x55: p.hp = min(p.hp_max, p.hp + max(1, p.hp_max >> 2)); return   # medium heart
        if item == 0x56: p.hp = min(p.hp_max, p.hp + max(5, p.hp_max // 2)); return   # large heart
        if item == 0x53: p.hp_max += 1; p.hp = p.hp_max; return                       # life vessel
        self.give_item(item)

    def load_sprite_info(self, m):
        """The map's sprite-info block (its sprite headers, animation sets, entity records,
        effect tables) where the game keeps it, relocated into the info struct 0x801F2EC0
        (0x8002DB6C), so ported code reads headers and records through the game's pointers."""
        from engine import spriteinfo as _si
        f = self.map.folder / 'sprite_info.bin'; at = self.map.data.get('sprite_info_addr')
        if not f.exists() or not at:
            self.mem.w32(_si.MAP_INFO + 0xC, 0); self.mem.w32(_si.MAP_INFO + 0x10, 0); return
        _si.load_block(self, _si.MAP_INFO, at, f.read_bytes())

    def header(self, catalogue):
        if catalogue >= 256: return self.map.sprite_headers.get(str(catalogue))
        return GLOBAL_HEADERS.get(str(catalogue))

    def spawn(self, index):
        recs = self.map.doc['entities']
        if not 0 <= index < len(recs): self.vm.note(f'spawn {index}'); return None
        a = self.make_actor(recs[index])
        if self.take_slot(a) is None: return None
        self.actors.append(a)
        a.parent = self.vm.cur_owner if hasattr(self.vm, 'cur_owner') else None
        return a

    def start_program(self, a, slot):
        a.states[slot] = self.vm.make_state(slot, a.programs.get(slot))
        return a.states[slot]

    def run_slot(self, a, slot, logic=None):
        st = a.states.get(slot)
        if st is None: return False
        r = self.vm.run(a, slot, st, logic)
        if r == 'restart': self.start_program(a, slot)
        return r

    # ---- map
    def load_map(self, m, start=None, music=True, keep=False):
        """keep: a map change to the map already loaded (main loop 0x8002C464) - the game does
        not read it again, so its squares, walls and records stay as the scripts left them."""
        self.snd.set_map(m)                                       # the map's sound bank (0x8004B0D8)
        same = keep and getattr(self, 'map', None) is not None and self.map.id == m
        if not same:
            self.snd.xa_stop()                                    # the CD read stops the XA stream (0x80050248)
            self.map = GameMap(m)
        self.map.lining.clock = lambda: Game.VBLANKS             # (the fog layers' sway: VSync count)
        if not same: self.load_sprite_info(m)
        self.actors = []; self.talk = None
        self.slots = [None] * 64; self.slots[0] = self.player; self.count = 0; self.sel_count = 0; self.slot_fc = [0] * 64
        self.camera_follow = None; self.camera_at = None; self.cam = None
        self.mem.w16(0x801EF380, 0); self.dialogue = None; self.pages = []; self.choice = False; self.mode_flags &= ~0x18
        if not same: self.install_map_texts()
        mp = self.map; p = self.player
        from effects import Effects
        self.effects = Effects(ASSETS, mp.folder); self.frame_no = 0
        p.shadow = None                                          # (a fresh shadow record in the new table)
        for i in range(64): self.mem.w32(self.MAP_FLAGS + 4 * i, 0)   # 0x80083E98 (main loop 0x8002C518, every map
                                                                  # load, same map too): map flags 0x8000-0x87FF off
        self.mem.w32(0x801F94D0, 0); self.mem.w32(0x801D7B3C, 1)   # 0x8002D030 (main loop 0x8002C520, every map
        self.mem.w32(0x801B6C4C, 0); self.mem.w32(0x801B6C48, 0)     # load, same map too): the screen shake stops,
                                                                  # the camera snaps at the next draw
        self.effects.load_records(mp.data.get('map_effect_records', []))
        info = mp.data.get('info', {})                             # the map's info block (16 bytes) in RAM for
        blk = self.MAP_INFO_BLOCK; mm = self.mem                   # the ports that read *(0x801F0070) + n
        mm.w32(blk, info.get('map_id', m)); mm.w16(blk + 4, info.get('gravity', 128) & 0xFFFF)
        mm.w16(blk + 6, info.get('z_viscosity', 4096) & 0xFFFF)
        for i, k in enumerate(('slide_effect', 'anim_delete_wall', 'c', 'balance_level', 'e', 'f', 'anim_land_floor', 'h11')):
            mm.w8(blk + 8 + i, info.get(k, 0) & 0xFF)
        self.tile_effects_addr = blk
        self.combat.level = mp.data.get('info', {}).get('balance_level', 0)
        if start is None:
            best = None
            for i, c in enumerate(mp.cells):
                if c[4] != 0xFFFF and not c[0] & 1:
                    x, y = i % mp.w, i // mp.w
                    dd = (x - mp.w / 2) ** 2 + (y - mp.h / 2) ** 2
                    if best is None or dd < best[0]: best = (dd, x, y, c[3])
            start = (best[1] * TW + 12, best[2] * TH + 8, best[3] * 16) if best else (12, 8, 0)
        p.wx, p.wy, p.z = start; p.vz = 0; p.logic_ctx = None; p.fx = p.fy = 0; p.platform = None
        p.force_adjusted = 0; p.collided_z = 0     # last map's collision results (a cutscene's 'walk until blocked'
                                                   # into the door would pass at once on arrival: map 135 after Wendell)
        p.frame_counter = 0                                      # +0x1C restarts with the map (the player's
                                                                 # record is re-initialised on every load)
        info = mp.data.get('info', {})
        self.world = physics.World(mp.cells, mp.w, mp.h, info.get('gravity', 128), info.get('z_viscosity', 4096), info.get('slide_effect', 0))
        self.world.player = p
        self.place(p, int(start[2] * 65536))
        floor = p.floor
        if not hasattr(self.world, 'coll'): self.world.coll = []
        self.world.tile_attributes(p)                             # InitializeEntity's 0x80038948: his square, its
        self.effects.spawn_initial((int(p.wx // TW), int(p.wy // TH)))   # 0x8003CB88: the map's effects in his area
        p.floor = floor                                           # attributes (no door taken twice from stale ones)
        ptx, pty = int(p.wx // TW), int(p.wy // TH)
        for rec in mp.doc['entities']:
            if not rec['enabled'] or not rec['flags'] & 0x40: continue
            x1, y1, x2, y2 = rec.get('rect', [0, 0, 255, 255])
            if not (x1 <= ptx <= x2 and y1 <= pty <= y2): continue      # spawn zone
            a = self.make_actor(rec)
            if self.take_slot(a) is not None: self.actors.append(a)
        self.events = [MapEvent(ev) for ev in mp.doc['events']]
        self.portals = [Game.Portal(w) for w in mp.warps]
        self.cur_map = m
        if self.warp_request:                                     # arrival: the door's animation and facing
            p.target_anim = self.warp_anim; p.target_dir = self.warp_dir
        self.warp_request = 0
        # InitializeEntity rebuilds his record (nothing held) and ends with 0x80033074: no item in
        # use (0x801F121C = 0).  Without this a bomb carried through a door left him in the
        # holding animation for good (user report, Bonaire's dream).
        if p.carried is not None or self.item_use:
            p.carried = None; self.item_use = 0
            if p.target_anim in (5, 6, 7, 0xB, 0xC, 0x2E, 0x2F, 0x30): p.target_anim = 0
        p.cur_anim = ~p.target_anim; self.animate(p)              # the player's InitializeEntity (0x80031F74)
        p.hp_max = emenu_life_max(self); p.hp = emenu_life(self)     # ... and his life from the stats
        if self.debug and mp.doc.get('name') and not same: self.toast(mp.doc['name'])   # F1 debug only
        if music: self.map_music(m)

    # ---- physics (physics.py is the game's PhysicsEngine)
    def place(self, a, z):
        """InitializeEntity: PosZ = z - ModZ + 1, lifted onto the ground under the box."""
        a.pz = z - a.mod[2] + 1
        physics.World.modded(a)
        h = self.world.ground_height(a) if hasattr(self, 'world') else 0
        a.terrain = h
        if a.pz <= h + 1: a.pz = h + 1
        a.floor = h + 1                       # FloorHeight is known from the first frame (AIs read it)
        physics.World.modded(a)
        if hasattr(self, 'world'): self.world.tile_attributes(a)   # ... then 0x80038948: its square (+0x120..),
                                                                   # floor, slope kind and VRAM bits

    def floor_at(self, wx, wy):
        c = self.map.cell(int(wx // TW), int(wy // TH))
        return c[3] * 16 if c else 0

    def animate(self, a, init=False):
        """UpdateAnimation 0x800393A4: a new animation (or a new facing quadrant) starts at
        its first frame entry; otherwise the frame delay counts down and the next entry is
        read when it reaches 0.  Entries: frames (delay | 0x80, attack box, picture), or an
        end: hold (anim_done, delay 0x7FFFFFFF), change to animation n (anim_complete + 1),
        loop (anim_complete + 1).  init: called from InitializeEntity (spawn)."""
        q = anim_direction(a.anim_quadrant, a.target_dir)
        a.zforce_applied = 0
        if a.target_anim != a.cur_anim or q != a.anim_quadrant:
            self._anim_start(a, a.target_anim, q)
        else:
            a.next_frame_delay -= 1
            if a.next_frame_delay == 0: self._anim_read(a)
        st = a.anim_set(a.cur_anim)
        a.speed = st.get('speed', 0); a.accel = st.get('accel', 0)

    def _anim_start(self, a, anim, q):
        a.anim_quadrant = q; a.next_frame_delay = 0; a.cur_anim = anim
        an = a.anim; an.anim = anim; an.frame = 0; an.pos = 0; an.done = False; an.q = q
        st = a.anim_set(anim)
        a.zforce_applied = st.get('z_force', 0)
        a.anim_flags = st.get('anim_flags', 0)
        a.cur_attack = self.combat.attack_for(getattr(a, 'balance', None), anim)
        atk = a.cur_attack                                    # +0x1C8: the attack record (attribute, power)
        if atk:                                               # the remake keeps a copy per slot in RAM no
            sl = a.slot if a.slot is not None and a.slot >= 0 else 64
            at = self.ATTACK_RECS + 4 * sl                    # port uses (the PSX stack area)
            self.mem.w8(at, atk[0] & 0xFF); self.mem.w8(at + 1, atk[1] & 0xFF)
            a.attack_addr = at
        else:
            a.attack_addr = 0
        snd = st.get('sfx', 0) | (0x100 if a.anim_flags & 0x20 else 0)
        if snd: ecore.play_sound(self, snd)
        self._anim_read(a)

    def _anim_read(self, a):
        an = a.anim
        for _ in range(64):
            stream = an.sprite.stream(an.anim, an.q) if an.sprite else None
            frames = stream['frames'] if stream else []
            if an.pos < len(frames):
                f = frames[an.pos]
                a.next_frame_delay = f['ticks'] & 0x7F
                a.sort_bias = f.get('sort', 0)                   # +0x1A8: the image set's first byte
                an.frame = an.pos; an.pos += 1
                self.combat.animated(a, False, f)
                return
            end = stream.get('end') if stream else 'hold'
            if end in ('stop', 'hold', None):
                a.next_frame_delay = 0x7FFFFFFF; an.done = True; return
            if end == 'change':
                a.target_anim = stream.get('next', 0); a.anim_complete += 1
                self._anim_start(a, a.target_anim, a.anim_quadrant); return
            an.pos = 0; a.anim_complete += 1                     # loop

    def started(self, a):
        pass

    def update_player(self, keys):
        """MovePlayer (0x80032174) is engine/player.py, the game's own code.  The remake's
        locks (dialogue, scripted control) stand for the game's mode flag 0x10."""
        busy = self.player_locked or self.dialogue is not None or self.talk is not None
        inv = self.inventory                      # UpdateItemEffectState: boots set g_gravityFlag
        self.world.gravity_flag = 3 if inv.get(0x1C) else 2 if inv.get(0x1B) else 1 if inv.get(0x1A) else 0
        self.world.level_top_fix = bool(self.settings.get('level_top_fix', False))   # Options > Level Top Fix
        saved = (self.pad_held, self.pad_pressed, self.mode_flags)
        if self.pad_forced:
            self.pad_held, self.pad_pressed = self.pad_forced[0], self.pad_forced[1]
            busy = False; self.pad_forced = None
        if busy: self.mode_flags |= 0x10
        eplayer.move_player(self)
        self.pad_held, self.pad_pressed = saved[0], saved[1]
        if busy: self.mode_flags = saved[2]

    def weapon_item(self):
        """The weapon in use: the best item Alundra has of the equipped group (0x8004F6C0)."""
        from engine import menu as emenu
        return emenu.equipped_kind(self)

    def hit_effects(self, attacker, target, kind, response, x, y, z):
        """0x80039C00 on a hit: a target that is not immune gets the fire (attack kinds 6, 10:
        global effect 4) or ice (7, 9: effect 5) effect on it, then three puffs fly off the
        middle of the overlap (CreateRandomPoofs)."""
        from engine import core
        if response & 0xC0 != 0x80:
            if kind in (6, 10): core.spawn_effect_on(self, 0, 4, 0, target, 1, 0, 0, 0)
            if kind in (7, 9): core.spawn_effect_on(self, 0, 5, 0, target, 1, 0, 0, 0)
        core.random_poofs(self, x, y, z)

    def ring_item(self):
        """The ring in use (0x80030E20): the item picked on Circle (0x8004F784) when it is a ring
        (item group 3, 0x33-0x38) and Alundra has it, else none."""
        from engine import menu as emenu
        n = self.mem.s16(emenu._stats(self) + 0xC)
        return n if 0x33 <= n <= 0x38 and emenu.has_item(self, n) else 0

    def player_responses(self):
        rings = self.ring_item()
        return self.combat.player_responses(self.inventory, self.weapon_item(), rings)

    def player_hit(self, p):
        """MovePlayer's damage check (0x80031B50 / FindWarpFacingDirection): a hit costs life
        by the balance rules, turns him toward the attacker and plays DamageTaken; 120 frames
        of blinking safety follow."""
        t = p.touching
        if t is None: return False
        self.drop_carried(p)
        import combat as _c
        armour = next((i for i in (20, 19, 18, 17) if self.inventory.get(i)), 0)
        rings = self.ring_item()
        self.combat.damage(p, self.player_responses())
        p.target_anim = 0x3A if p.slope_now == 4 else 0x31
        p.damaged_tick = 0x78
        p.target_dir = _c.direction_to(p.px - t.px, p.py - t.py)
        return True

    def game_over(self):
        """MovePlayer, Hp 0 and Dead finished: without a Wonder Essence (0x27) the game goes
        to map 0x1DD (the game-over screen); with one, it is used and he gets up."""
        p = self.player
        if self.inventory.get(0x27):
            self.inventory[0x27] -= 1; p.hp = p.hp_max; p.target_anim = 0x00; return
        if self.pending_warp is None:
            p.hp = p.hp_max
            self.pending_warp = (0x1DD, None, None, None)

    # ---- lifting and throwing (PlayerTryAction 0x8002EEAC, UpdatePlayerCarriedEntity 0x8002F884)
    def try_lift(self, p, pressed):
        if p.carried is not None: return False
        e = p.x_collision
        if e is None or not pressed & 0x80 or not getattr(e, 'alive', False): return False
        kind = (e.flags & 0x600) >> 9                 # 0 no, 1 always, 2-3 only without item 0x3B
        if kind == 0 or (kind >= 2 and self.inventory.get(0x3B)): return False
        p.carried = e; e.platform = p; e.flags2 = 0
        p.target_anim = 0x05 if p.on_ground else 0x0B
        p.carry = (e.px - p.px, e.py - p.py, e.pz - p.pz)
        return True

    @staticmethod
    def _toward(v, target, step):
        if v < target: return min(target, v + step)
        return max(target, v - step)

    def carry_step(self, p):
        """Mode 0: the held object rises to 32 px over his head, then centres."""
        e = p.carried
        if e is None: return
        dx, dy, dz = p.carry
        if max(abs(dx), abs(dy)) > abs(dz - 0x200000):
            dx = self._toward(dx, 0, 0x10000); dy = self._toward(dy, 0, 0x10000)
        dz = self._toward(dz, 0x200000, 0x10000)
        p.carry = (dx, dy, dz)

    def throw(self, p, moving):
        e = p.carried
        e.target_dir = (0, 8, 16, 24)[p.anim_dir()]
        e.px, e.py, e.pz = p.px, p.py, p.pz + 0x200000
        if not p.on_ground:
            p.target_anim = 0x0A; e.flags2 = 3 if moving else 2
        else:
            p.target_anim = 0x09; e.flags2 = 2 if moving else 1

    def drop_carried(self, p):
        """Mode 2 (hit while holding): it falls from over his head."""
        e = p.carried
        if e is None: return
        e.flags2 = -1; e.target_dir = p.target_dir
        e.px, e.py, e.pz = p.px, p.py, p.pz + 0x200000

    def jump(self):
        pass                                                     # jumping is part of update_player

    def confirm(self):
        """The message window takes Square (pad_pressed & 0x80, 0x800469F0...) to go on."""
        if self.choice:
            self.choice = False; self.choice_result = 1 if self.choice_sel == 0 else 2
            if self.dialogue is None: self.close_message()
            return True
        return False

    # ---- frame
    def update(self, keys):
        held = self.controls.held(keys) & 0xFFFF                 # (the game's pad word: no Menu shortcut bit)
        Game.VBLANKS += 1                                        # the console's VSync count since power-on
        if getattr(self, '_lang_wanted', None) is not None and self.set_lang(self._lang_wanted): self._lang_wanted = None
        self.sw_linked = set()                                   # the save windows linked this frame
        if self.front is not None:                               # the boot program / the ending (frontend.py)
            self.front.update(held)
            self.snd.tick()                                      # its sound manager runs every frame too
                                                                 # (else a sound asked once stays 'asked')
            if self.front.action == 'continue':                  # the History Book's record (or a SPEEDRUN start)
                speedrun.start_run(self, self.front.speedrun_route, self.front.speedrun_name)
                self.begin_continue(self.front.record)
            elif self.front.action != 'new_game': return
            else: speedrun.start_run(self, None); self.begin_new_game()   # ALUN_CD.EXE is in: this frame is the
                                                                 # game's first (the map comes in from black)
        from engine import menu as emenu, screen as escreen
        if getattr(self, 'ui_stall', 0) > 0:                   # a name plate just went up (engine/message.py)
            self.ui_stall -= 1; return
        if self.trans is not None:
            if self.trans['phase'] != 'vsync':
                self.warp_frame(held)                            # the main loop's map change (no game frame)
            if self.trans['phase'] != 'vsync': return
            # 0x80043324 passed: GameFrame(1) runs in the frame the map comes in, without the play
            # time counting (BizHawk 2026-10-23, Fire Manor door and same-map warps: every entity's
            # frame counter +0x1C is 1 and Alundra's animation timer has ticked on the arrival frame;
            # the play time first counts the frame after).
            self.trans = None; self._arrival_frame = True; self._no_play_tick = True
        if self.cam is not None or self.player.frame_counter:   # 0x8002BEAC draws (camera eased toward the
            self.step_camera()                                   # state so far; snaps after GameFrame(1))
        escreen.box_step(self)                                   # state so far) before GameFrame 0x8002BC18
        self.map.animate_tiles()                                 # runs: the drawing box grows.  (After a load
                                                                 # the first draw snaps, after GameFrame(1).)
        emenu.pad_update(self, 0x801DDA38, held)                 # held / pressed / released / auto-repeat (0x8002E5BC)
        lr_swap.play_frame(self)                                 # Mods > L / R swapping (lr_swap.py)
        # (no Square filtering here: the window's task reads the pad after the game frame, as
        #  0x8002BEAC does, and mode flag 8 / 0x10 already keeps Alundra from acting on it)
        pr = self.pad_pressed
        if self.choice and pr & 0xA000: self.choice_sel ^= 1
        if pr & 0x40: self.jump()
        if pr & 0x80 and self.choice:
            if self.confirm(): self.pad_pressed &= ~0x80               # the window used the press
        p = self.player
        if not self.mode_flags & 0x48:
            self.run_map_events()                                # 0x8003D058 (before the entities; both it
        if self.mode_flags & 0x48:                               # and EntityFrame 0x8003BCCC check the flags
            self.sort_keys()                                     # 0x8003A2C0 (runs while frozen too)
            self.effects.update(self.mode_flags); self.frame_no += 1
            for t in self.toasts: t[1] -= 1
            self.toasts = [t for t in self.toasts if t[1] > 0]
            self.music_tick(); gamerng.tick()
            self.ui_frame()
            emenu.start_check(self)
            self.arrival_frame_end()
            self.warp_check()
            return
        self.entity_dispatch(keys)                               # 0x80038F24 + 0x80038FC4
        # UpdateEntitiesCounters, UpdateEntitiesAnimation, then UpdateEntitiesPhysics
        # UpdateEntitiesCounters 0x8003927C, then the lists 0x80038DCC: status 2 and 3 move and show
        for i, a in enumerate(self.slots[:getattr(self, 'count0', self.count) + 1]):   # UpdateEntitiesCounters: every
            if a is not None: a.frame_counter += 1                   # slot up to the count, free ones too
            else: self.slot_fc[i] += 1
        live = [p] + [a for a in self.slots[1:self.count + 1] if a is not None and a.alive and a.estatus in (2, 3) and not a.frozen]
        self.combat.counters(live)
        for a in live:
            self.animate(a)
            if a.hit_counter: a.hit_counter -= 1
        self.world.entities = live
        self.world.coll_source = [p] + [a for a in self.slots[1:self.count + 1] if a is not None and a.alive]   # solid even when frozen (0x80038DCC)
        self.world.step()
        eshadows.update_shadows(self)                            # 0x80039788: shadows, water splashes
        self.combat.resolve(live, self.player_responses(), self.hit_effects)    # 0x80039C00: the hit checks
        for a in live: a.bumped = a.x_collision
        self.sort_keys()                                         # 0x8003A2C0: each entity's drawing key
        self.effects.update(self.mode_flags); self.frame_no += 1
        self.actors = [a for a in self.actors if a.alive]
        if self.pending_warp: self.do_pending_warp()
        for t in self.toasts: t[1] -= 1
        self.toasts = [t for t in self.toasts if t[1] > 0]
        self.music_tick()
        gamerng.tick()                                       # 0x8002BE58: once per game frame
        self.ui_frame()
        emenu.start_check(self)                              # Start / L2 / R2: the menu (end of GameFrame)
        self.arrival_frame_end()
        self.warp_check()                                    # main loop 0x8002C5F8, after the frame is shown

    def arrival_frame_end(self):
        """GameFrame(1), the first frame after a map change, ends by dropping any map-change
        request made during it (0x8002BE84-0x8002BE90: if the argument is set, the request word
        0x801F11F4 = 0).  So a warp square under the arrival point does not fire then: the Twin's
        Dream switches (map 112) land Alundra on map 109's save-room door (12,14) and its script
        B3 moves him off it (BizHawk 2026-10-22: request cleared, B3 / B5 run, back to map 112)."""
        if self.__dict__.pop('_arrival_frame', False): self.warp_request = 0

    def draw_choice(self, v):
        """The YES / NO window as 0x800513F4 left it this frame: the scroll (window 0x800A6E54 at
        its sliding place), each answer's text sprites and the pointing hand (WIND u 176 + 16 *
        picture, v 56, palette of the menu cursor)."""
        from engine import menu as emenu, choice as ch
        if not emenu.task_running(self, 3) or not self.__dict__.pop('choice_drawn', False): return
        ui = self.inventory_ui; m = self.mem
        ui.draw_window(v, ch.CFG)
        b = m.s32(ch.BUFI)
        for k in range(2):
            txt = bytearray(); a = ch.TEXTS + 7 * k
            while m.u8(a + len(txt)) and len(txt) < 6: txt.append(m.u8(a + len(txt)))
            if not txt: continue
            p = ch.PRIMS + b * 0x78 + k * 0x3C
            ui.text(v, txt.decode(self.text_enc(), 'replace'), m.s16(p + 8), m.s16(p + 0xA))
        r = ch.CURSOR + b * 0x14
        sh = ui.sheet(8)                                     # palette 0x80142B70 (as the "more" marker)
        if sh is not None:
            v.blit(sh, (m.s16(r + 0x10), m.s16(r + 0x12)), (m.u8(r + 0x14), m.u8(r + 0x15), 16, 16))

    def draw_save_windows(self, v):
        """The save menu's windows where the logic left them: the list (task 10: its four entry
        windows tinted by their colour fades, 0x40 dim / 0x80 bright, each with its two text rows,
        then the heading window and its text) and the two-line message window (task 9).  Order:
        the drawing lists 0x801F53A0 (entry windows), A8 (texts), B4 (heading), B8 (its text)."""
        from engine import menu as emenu, savewin as sw
        m = self.mem; ui = self.inventory_ui; mu = self.message_ui
        b = m.s32(sw.BUFI) & 1
        linked = getattr(self, 'sw_linked', None)
        if linked is None: linked = {9, 10}
        if 10 in linked and emenu.task_running(self, 10):
            for k in range(4):
                e = sw.ENT + sw.ENT_SIZE * k
                if not m.s32(e) & 1: continue
                cfg = m.u32(e + 4); f = sw.FADES + 0x30 * k
                win = ui.window(cfg)
                if win is not None:
                    rgb = tuple(m.u32(f + o) & 0xFF for o in (0x18, 0x1C, 0x20))
                    v.blit(tint_rgb(ui, ('save', cfg, rgb), win, rgb), ui.pos(cfg))
            for k in range(4):
                e = sw.ENT + sw.ENT_SIZE * k
                if not m.s32(e) & 1: continue
                mu.text_sprite(v, e + 0x24 + b * 0x14); mu.text_sprite(v, e + 0x4C + b * 0x14)
            ui.draw_window(v, sw.WIN)
            mu.text_sprite(v, sw.HEAD_PRIM + b * 0x14)
        if 9 in linked and emenu.task_running(self, 9):
            ui.draw_window(v, sw.WIN)
            mu.text_sprite(v, sw.MSG_PRIM1 + b * 0x14); mu.text_sprite(v, sw.MSG_PRIM2 + b * 0x14)

    def xa_enabled(self):
        """0x8005CB94 / 0x8005C990 play or report an XA clip only when 0x8009C6C0 is set, or
        0x800AA118 is set with 0x800C667C clear.  The US game runs with 0x800AA118 = 1 and
        0x800C667C = 0 (RAM of the recompiled game), so its clips play."""
        m = self.mem
        return bool(m.u32(0x8009C6C0) or (m.u32(0x800AA118) and not m.u32(0x800C667C)))

    XA_CLIPS = None
    VBLANKS = 0                                                  # vertical blanks since the program started
    PRESET_FLAGS = None                                          # (tests) game flag bytes 0x801DD334.. at start

    def xa_play(self, n):
        """Command B9 and the rare-item jingle (clip 11): 0x8005CB94 streams clip n of
        ARAN_XA.XA (table 0x800C6680; tools/remake_extract_xa.py), unless a music load is
        pending.  F5 > Mods > Rare Item Jingle: 2x plays clip 11 at double speed (same pitch)
        and halves the time the world waits for it; Regular Item Sound plays the common pick-up
        sound (52) instead and nothing waits (engine/ai_g6.py takes rare items as common ones)."""
        if not self.xa_enabled() or self.music_loading(): return
        if Game.XA_CLIPS is None:
            try: Game.XA_CLIPS = json.loads((ASSETS / 'audio' / 'xa' / 'clips.json').read_text())
            except (OSError, ValueError): Game.XA_CLIPS = {}
        info = Game.XA_CLIPS.get(str(n))
        if not info: return
        if n == 11 and self.settings.get('rare_jingle', 1) == 3:    # Regular Item Sound: no jingle
            self.sound(52); return
        mode = self.settings.get('rare_jingle', 1) if n == 11 else 1
        fast = mode == 4                                         # PS2 FDS: the stream skips, same pitch,
        frames = info['frames']                                  # ~2.2x as fast (JP FDS video, 5 pick-ups)
        if fast: frames = round(frames / FDS_JINGLE)
        path = ASSETS / 'audio' / 'xa' / (f'clip_{n:02d}_2x.ogg' if fast else f'clip_{n:02d}.ogg')
        self.snd.xa_start(path, frames)

    def xa_busy(self):                                           # command BA (0x8005C990)
        return self.xa_enabled() and self.snd.xa_left > 0

    def hud_sync(self):
        from engine import calls
        calls.call(self, 0x8004CA2C)

    def hud_show(self):
        """0x8004D24C: the HUD slides in - only while flag 0x67E ('HUD allowed') is set and it is
        hidden.  A new game has the flag off until the shipwreck (map 393's B1 sets it)."""
        if self.__dict__.pop('_hud_hidden_state', False): return   # (a BizHawk state with the HUD away)
        if self.flag(0x67E): self.hud.show()

    def hud_flags(self):
        """The start of 0x80048FB0 (game flags 0x67E, 0x715..0x717 = words 0x801DD400 / 0x801DD414):
        0x717 reloads picture 7 (0x8005CD9C); without 0x67E the HUD slides out every frame;
        0x715 sets 0x67E and slides it in; 0x716 (the game over's last square gone) takes it away
        at once (0x8004D23C) and clears 0x67E."""
        if self.flag(0x717):
            self.unported(0x8005CD9C, 7); self.set_flag(0x717, False)
        if not self.flag(0x67E): self.hud.hide()                 # 0x8004D1B8
        if self.flag(0x715):
            self.set_flag(0x715, False); self.set_flag(0x67E, True); self.hud_show()
        if self.flag(0x716):
            self.hud.state = 0; self.hud.slide = None            # 0x8004D23C
            self.set_flag(0x67E, False); self.set_flag(0x716, False)

    def ui_frame(self):
        """0x8002BEAC after GameFrameBody: the UI tasks (0x80048FB0: message window, name plate,
        the Start menu's pages) and the HUD portrait (0x80045BD0) run after the scripts and the
        entities of the same frame - a window a script opens this frame is placed by its task
        before it is first drawn."""
        from engine import menu as emenu, portrait as _eport, screen as escreen
        escreen.fade_tick(self)                                # 0x80043974: the fades (before the windows)
        from engine import card as ecard
        ecard.card_frame(self)                                 # 0x80060E6C: the memory card manager (saving)
        self.inventory_ui.drawn.clear()
        self.hud_flags()                                       # 0x80048FB0: the HUD's flags, then the tasks
        self._talk_clock += 1                                  # (one clock for the voice: the window's
        emenu.run_tasks(self)                                  # own prints and the Mods' extra ones)
        p0 = self.player
        self.hud.frame(self.gilder, (p0.hp, p0.hp_max, *self.magic_pair()),
                       self.sound)                             # task 1 (0x8004D2F4)
        self.message_tick()
        self.inventory_ui.tick()
        self.portrait_shown = _eport.portrait_draw(self, 0x801F53AC)
        if not self.__dict__.pop('_no_play_tick', False):
            ecard.play_tick(self)                              # 0x80043380: the picture is shown, the play time counts

    def sort_keys(self):
        """0x8003A2C0 / 0x8003A0B0: the key that places an entity in the drawing order (+0x1BC).
        The entities of the draw list (0x80038DCC: status 2 or 3, not in a blink frame of a hit)
        get key 0 and their top (+0x1C0 = box z + size z); each then takes its y (16.16) + its
        frame's sort bias in rows of a pixel (+0x1A8); one that rests on others (flag 0x80, no
        anim flag 0x80) takes the larger key of its holder or of any solid entity (the solid
        list: flag 0x80, no anim flag 0x80, nobody holds it - whatever its status) whose top is
        lower and whose box overlaps its own in x and y; a key still 0 is computed on demand.
        Finally the low 16 bits become the height in pixels.  Entities not listed keep their
        last key and top (a blinking one is not drawn, but what stands on it still reads it)."""
        slots = [a for a in self.slots[:self.count + 1] if a is not None]
        listed = [a for a in [self.player] + self.actors if a.alive and a.estatus in (2, 3) and (a.damaged_tick & 3) != 3]
        solid = [a for a in slots if (a.flags & 0x80) and not (getattr(a, 'anim_flags', 0) & 0x80) and a.holder is None]
        for a in listed:
            a.sort_key = 0
            a.top_z = ecore.s32(a.mpz + a.size[2])
        def key(a, depth=0):
            v = a.sort_key
            if v != 0: return v
            v = ecore.s32(a.py + (getattr(a, 'sort_bias', 0) << 16))
            if (a.flags & 0x80) and not (getattr(a, 'anim_flags', 0) & 0x80) and depth < 16:
                h = a.holder
                if h is not None:
                    hv = key(h, depth + 1)
                    if v < hv:
                        a.sort_key = hv; return hv
                else:
                    ax, ay, aw, ah = a.mpx, a.mpy, a.size[0], a.size[1]
                    for o in solid:
                        if o is a or getattr(o, 'top_z', 0) >= a.top_z: continue
                        ox = ecore.s32(o.px + o.mod[0]); d = ecore.s32(ox - ax)
                        if not ((d >= 0 and d < aw + 1) or (d < 0 and ecore.s32(ax - ox) < o.size[0] + 1)): continue
                        oy = ecore.s32(o.py + o.mod[1]); d = ecore.s32(oy - ay)
                        if not ((d >= 0 and d < ah + 1) or (d < 0 and ecore.s32(ay - oy) < o.size[1] + 1)): continue
                        ov = key(o, depth + 1)
                        if v < ov: v = ov
            a.sort_key = v
            return v
        for a in listed: key(a)
        for a in listed: a.sort_key = (a.sort_key & ~0xFFFF) + ((a.pz >> 16) & 0xFFFF)

    def do_pending_warp(self):
        """g.warp(): a map change with no transition (the old script hook)."""
        m, x, y, z = self.pending_warp; self.pending_warp = None
        self.portal_armed = False
        try: self.load_map(m, (x, y, z) if x is not None else None)
        except FileNotFoundError: self.toast(f'Map {m} not exported yet'); self.warp_request = 0

    # ---- map changes: the main loop 0x8002C5F8-0x8002C7D4 (engine/screen.py has the picture)
    def warp_check(self):
        """After a game frame is shown: a door, a script, the menu or the game over asked for
        a map change.  The transition starts next frame from the picture just shown."""
        if self.warp_request and self.trans is None:
            self.trans = {'phase': 'start', 'n': 0}

    def music_for_map(self, m):
        """0x8004AEF8: a map's music - the first matching (map, flag set) of 0x800AA04C, else
        the table 0x800C8404.  0 keeps whatever plays."""
        from engine import rodata as R
        a = 0x800AA04C
        while True:
            mm = R.s32(a)
            if mm == 0: break
            if mm == m and self.flag(R.s32(a + 4) & 0xFFFF): return R.s32(a + 8)
            a += 12
        try: return R.s32(0x800C8404 + 4 * m)
        except Exception: return self.map.data.get('music') or 0

    def warp_sound_and_music(self, m, n):
        """0x8004B0F0: every sound effect stops; with new music and no door sound the music
        fades out (120 frames); with new music and a door sound it stops at once; then the
        door sound."""
        import sound_system as _ss
        self.snd.stop_all()
        if n:
            try:
                rec = _ss.record(n)
                if rec['seq'] == -1 and rec['voices'] == 0: n = 0
            except Exception: n = 0
        new = self.music_for_map(m) or (self.snd.music or 0)
        if (self.snd.music or 0) != new:
            if n == 0:
                self.snd.music_stop(True); return
            self.snd.music_stop(False)
        if n: self.sound(n)

    SOUND_OPS = {0x12: 1, 0x75: 1, 0xAB: 1, 0xBD: 2, 0xBE: 2, 0xBF: 2}   # script commands that play a sound

    def preload_map(self):
        """Everything this map can draw or play, loaded during its loading pause (user: no stalls
        the first time a picture or sound is used): its sprites' and effect banks' pictures, the
        global ones once, and the sound files its scripts and sprite animations play."""
        import effects as fx, time
        t = time.perf_counter()
        sounds = set()
        if not getattr(Game, '_globals_loaded', False):
            for d in sorted((ASSETS / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
                sp = Sprite.get(d)
                if sp is not None: sounds |= sp.preload()
            for d in sorted((ASSETS / 'effects' / 'global').glob('[0-9][0-9][0-9]')):
                fx.Bank.get(d).preload()
            Game._globals_loaded = True
            Game._global_sounds = sounds
        sounds = set(Game._global_sounds)
        mp = self.map
        for d in sorted((mp.folder / 'sprites').glob('[0-9][0-9][0-9]')):
            sp = Sprite.get(d)
            if sp is not None: sounds |= sp.preload()
        for d in sorted((mp.folder / 'effects').glob('[0-9][0-9][0-9]')):
            fx.Bank.get(d).preload()
        for rows in mp.scripts.values():
            for op, raw, _ in rows.values():
                n = self.SOUND_OPS.get(op)
                if n and len(raw) > n: sounds.add(raw[1] if n == 1 else raw[1] | raw[2] << 8)
        self.snd.preload(sounds)
        self.preload_ms = (time.perf_counter() - t) * 1000

    def map_music(self, m):
        """0x8004B278 after a map is set up: new music replaces the old (loaded, then played by
        the next sound tick, 0x8013A158); 0x2D only stops it; 0 keeps it."""
        new = self.music_for_map(m)
        if new and new != (self.snd.music or 0):
            if new == 0x2D:
                self.snd.music_close()                           # closed; 0x801D7B98 keeps the old number
            else:
                self.snd.music_load_now(new, False)              # (0x8004AD80: read with the map)
            self.music = self.snd.music
        try: self.preload_map()
        except Exception: pass                                   # (a preload problem must not stop the game)

    def load_frames(self, m):
        """The CD read of the new map (0x80083F04: its whole DATAS.BIN block) at double speed,
        150 sectors (300 KB) a second, after a seek: an estimate of the original's black pause."""
        from settings_screen import load_pause
        size = MAP_SIZES.get(m)
        if not size: return load_pause(self.settings, SAME_MAP_SETUP)
        # BizHawk 2026-10-19 (map 163 door -> 162, 145 sectors): 112 frames from the map number
        # changing to the arrival = the set-up a same-map warp also pays + MAP_SEEK + ceil(sectors / 2)
        read = MAP_SEEK + -(-(-(-size // 2048)) // 2)
        return load_pause(self.settings, SAME_MAP_SETUP + read, read)   # Mods > Loading pauses

    def warp_frame(self, held):
        """One frame of the map change.  'out': the transition (pad, 0x80045388, sound manager);
        'sync': 0x80043488 shows it once more; 'music' / 'sound' / 'post': 0x8004B1D8 waits for
        the music fade, for every sound to end, then 3 frames; 'load': the CD; then the map is
        set up, 0x80044FB8, GameFrame(1) is next and one VSync (0x80043324) passes first."""
        from engine import menu as emenu, screen as escreen
        t = self.trans; ph = t['phase']
        if ph == 'start':
            self.snapshot = self.view.copy()                     # MoveImage of the shown picture to x 320
            self.warp_sound_and_music(self.warp_map, self.warp_sound)
            self.warp_sound = 0
            eff = self.warp_effect
            t['eff'] = eff
            escreen.transition_start(self, eff)
            ph = t['phase'] = 'out'
        if ph == 'out':
            emenu.pad_update(self, 0x801DDA38, held)             # 0x8002E710
            busy = escreen.transition_step(self, t['eff'])
            self.music_tick()
            t['show'] = True
            from engine import card as ecard
            ecard.play_tick(self)                                # 0x80043380
            if not busy: t['phase'] = 'sync'
            return
        if ph == 'sync':
            from engine import card as ecard
            ecard.play_tick(self)                                # 0x80043488
            t['phase'] = 'music'; return
        if ph == 'music':
            if self.snd.fade and self.settings.get('load_pauses') != 3:   # PS2 FDS: no wait for the fade (JP FDS video)
                self.music_tick(); return
            ph = t['phase'] = 'sound'
        if ph == 'sound':
            self.music_tick()
            if self.snd.idle(): t['phase'] = 'post'; t['n'] = 0
            return
        if ph == 'post':
            self.music_tick(); t['n'] += 1
            if t['n'] >= 3:
                t['phase'] = 'load'
                self.snd.cut_sfx()                               # the read: the effects fall silent
                if t['eff'] in (9, 0xB): t['n'] = 0
                elif self.warp_map != self.cur_map:
                    t['n'] = max(0, self.load_frames(self.warp_map) + self.load_correction(self.warp_map)); t['map_read'] = True
                else:                                        # same map: no map read, but the set-up after
                    from settings_screen import load_pause   # it (0x8002C510-0x8002C558) still takes time
                    t['n'] = load_pause(self.settings, SAME_MAP_SETUP_BY_MAP.get(self.cur_map, SAME_MAP_SETUP))
            return
        if ph == 'load':
            if t['n'] > 0:
                t['n'] -= 1; return
            self.warp_arrive(t['eff']); return
        if ph == 'music_read':                                   # 0x8004B278 -> 0x8004AD80 reads the new
            t['n'] -= 1                                          # music from the CD before GameFrame(1)
            if t['n'] <= 0: t['phase'] = 'vsync'
            return

    def warp_arrive(self, eff):
        """0x8002C6A8: the effect's own step, then the map (0x8002C448), the arrival fade."""
        from engine import screen as escreen
        bank_before = self.snd.bank                              # (load_map sets the new map's bank)
        if eff in (9, 0xB):                                      # LoadExec END.EXE (the ending) / the title
            import frontend
            self.snd.music_stop(False); self.snd.stop_all()
            self.trans = None
            self.front = frontend.FrontEnd(self, 'ending' if eff == 9 else 'title')
            return
        if eff == 8:                                             # the game over: flag 0x67E off
            self.set_flag(0x67E, False)
        elif eff == 0xA:                                         # retry: back to the last save
            self.snd.music_stop(False)
            self.retry()
        m = self.warp_map
        try:
            self.load_map(m, (self.warp_x / 65536, self.warp_y / 65536, self.warp_z / 65536), music=False,
                          keep=eff != 0xA)                       # (a retry reads the map again)
        except FileNotFoundError:
            self.toast(f'Map {m} not exported yet'); self.warp_request = 0
        info = self.map.data.get('info', {})
        escreen.arrival(self, info.get('e', 0) * 8 & 0xFF, info.get('f', 0) * 8 & 0xFF,
                        info.get('anim_land_floor', 0) * 8 & 0xFF, eff)
        self.hud_show()                                          # 0x8004D24C
        before = self.snd.music or 0
        self.map_music(m)                                        # 0x8004B278
        self.trans['phase'] = 'vsync'                            # one VSync with nothing new shown
        now = self.snd.music or 0
        music = self.music_read_frames(now) if now and now != before and now != 0x2D else 0
        # Approximations fitted on 40 BizHawk different-map loads (2026-10-23, docs/2026-10-23-map-
        # load-timing.txt; mean error 7 frames, the drive's seek distance is not modelled): a music
        # read right after a map read takes MUSIC_AFTER_MAP longer (the 163 same-map case, no map
        # read, matched without it); a new sound bank (0x800499AC: VAB header + body from the table
        # 0x800A9B9C) is read after the music: BANK_SEEK + ceil(sectors / 2).
        if music and self.trans.get('map_read'): music += MUSIC_AFTER_MAP
        import sound_system as _ss
        bank = _ss.map_bank(m)
        bank_read = self.bank_read_frames(bank) if bank != bank_before and bank >= 0 else 0
        wait = music + bank_read
        # 0x8005CE4C (from 0x8004B278, every arrival): with Earth Scroll / Earth Book / Fire Scroll /
        # Fire Book chosen, the CD is sought to that spell's XA clip (0x8005CCC8) and the game waits
        # for the seek.  BizHawk 2026-10-19: door 163 -> 162 with the Earth Book, 27 frames frozen.
        from engine import menu as emenu
        if emenu.selected_item(self) in XA_SEEK_ITEMS: wait += XA_SEEK
        if wait:
            from settings_screen import load_pause, FDS_MUSIC
            n = load_pause(self.settings, wait - bank_read, music, FDS_MUSIC)   # PS2 FDS: the music read goes, the XA seek stays
            if bank_read: n += load_pause(self.settings, bank_read, bank_read)  # the bank: an ordinary read (FDS_READ)
            if n > 0: self.trans['phase'] = 'music_read'; self.trans['n'] = n

    _LOAD_TIMING = None

    def load_correction(self, m):
        """Measured frames the original's load into map m takes beyond the model (load_frames, the
        music read, the bank read), by kind of load - the music changes or not, the sound bank
        changes or not: that map's average for the kind when it was measured, else the average of
        the kind over every measured map (assets/load_timing.json, tools/build_load_timing.py,
        BizHawk 2026-10-23).  Loading Pauses applies as to any read (Instant: none)."""
        import sound_system as _ss
        from settings_screen import load_pause
        if Game._LOAD_TIMING is None:
            try: Game._LOAD_TIMING = json.loads((ASSETS / 'load_timing.json').read_text())
            except (OSError, ValueError): Game._LOAD_TIMING = {}
        lt = Game._LOAD_TIMING
        new = self.music_for_map(m) or 0
        mc = int(bool(new) and new != (self.snd.music or 0) and new != 0x2D)
        bc = int(_ss.map_bank(m) != self.snd.bank)
        k = f'm{mc}b{bc}'
        c = (lt.get('maps', {}).get(str(m), {}).get(k) or lt.get('kinds', {}).get(k) or [0])[0]
        n = load_pause(self.settings, abs(c), abs(c))
        return n if c >= 0 else -n

    def bank_read_frames(self, b):
        """Frames for reading sound bank b (0x80049820): BANK_SEEK + ceil(sectors / 2) of its VAB
        header and body (table 0x800A9B9C: header start, body start; the next entry ends it)."""
        from engine import rodata as R
        try:
            t = 0x800A9B9C + 8 * b
            h, body, nxt = R.u32(t), R.u32(t + 4), R.u32(t + 8)
            sec = -(-(body - h) // 2048) + -(-(nxt - body) // 2048)
        except Exception:
            return 0
        return BANK_SEEK + -(-sec // 2)

    def music_read_frames(self, mid):
        """Frames the game stands still after a map change while 0x8004AD80 reads new music (VAB
        header, body, SEQ).  Measured in BizHawk (2026-10-19, map 163 stairs, music 2 -> 16, 89
        sectors): 65 frames with the game's frame counter stopped; modelled as MUSIC_SEEK +
        ceil(sectors / 2) (the recompiled game's read rate), calibrated on that one track."""
        try:
            sec = sum(-(-n // 2048) for _, n in self.snd._music_sizes(mid))
        except Exception:
            return 0
        return MUSIC_SEEK + -(-sec // 2)

    def begin_new_game(self):
        """START on the title: ALUN_CD.EXE runs with 0x80010000 = 0 - 0x80031CBC sets up a new game
        (map 389 at 0x21, 0x23, respawn at 0x21, 0x3B) and the first map comes in from black."""
        try: pygame.mixer.music.stop()
        except pygame.error: pass
        self.snd.stop_all()
        m, start = new_game_start()
        self.__init__(m, start, new_game=True)

    def begin_continue(self, record):
        """CONTINUE: ALUN_CD.EXE runs with the record at 0x80010000 ([0] = 1) - 0x80031CBC takes the
        game block from it and Alundra arrives at its respawn point."""
        try: pygame.mixer.music.stop()
        except pygame.error: pass
        self.snd.stop_all()
        self.__init__(0, None, new_game=True, handoff=record)

    def dev_respawn(self):
        """A start the game itself never makes (a map number, --wake-up): the respawn point is
        that map and tile, and the retry block (0x80010000) is this state."""
        from engine import gamestart as egs
        p = self.player; m = self.mem
        m.w32(0x801DD324, self.cur_map)
        m.w32(0x801DD328, int(p.wx // TW)); m.w32(0x801DD32C, int(p.wy // TH)); m.w32(0x801DD330, p.pz >> 20)
        egs.block_store(self)

    def retry(self):
        """0x80031B50: the last saved state (0x80010000) comes back and Alundra arrives at its
        respawn point, anim 0x36, facing down."""
        from engine import gamestart as egs
        egs.retry(self)

    def run_map_events(self):
        """RunMapEvents 0x8003D058: each map event's B program runs on Alundra while he
        stands in its rectangle (with the event's own saved context); leaving the
        rectangle resets the context and puts back the record's program."""
        p = self.player
        ptx, pty = int(p.wx // TW), int(p.wy // TH)
        for ev in self.events:
            if not ev.prog & 0x7F: continue
            x1, y1, x2, y2 = ev.rect
            if not (x1 <= ptx <= x2 and y1 <= pty <= y2):
                ev.state = None; ev.prog = ev.prog0; continue
            if ev.state is None:
                ev.state = self.vm.make_state('B', ev.prog)
                if ev.state is None: continue
            p.programs['B'] = ev.prog; saved_ctx = p.logic_ctx; p.logic_ctx = ev.ctx
            r = self.vm.run(p, 'B', ev.state)
            ev.ctx = p.logic_ctx; p.logic_ctx = saved_ctx
            if p.programs.get('B') != ev.prog or r == 'restart':
                ev.prog = p.programs.get('B', 0); ev.state = None

    def choose_action(self, a):
        """0x80038FC4 first pass: Entity+0x228 from the status word."""
        if a.frozen: return None
        s = a.estatus
        if s == 1: a.set_status(2); return 'A'
        if s == 3: return 'E'
        if s != 2: return None
        f = a.flags
        if f & 0x100000 and getattr(a, 'slope_now', 0) == 4:
            self.sprite_ai.destroy(a, 6); return None
        if f & 0x200000 and getattr(a, 'vram_or', 0) & 0x8004:
            self.sprite_ai.destroy(a, -1); return None
        if (f & 0x10 and (a.force_adjusted or a.on_ground)) or (f & 0x20 and a.hits) or \
           (f & 0x40 and a.anim.done):
            a.set_status(3); return 'E'                          # DeactivateOnImpact / OnHit / OnAnimationEnd
        if a.touching is not None: return 'D'                    # +0x224: an attack reached it last frame
        if self.talk_target is a and (a.bi_f or a.prog_f): return 'F'
        return 'C'

    def run_action(self, a, slot):
        """One entity's program for this frame (_run_action); an error in it is written to
        crash.log and only this action is skipped, so one broken program cannot close the game."""
        try:
            self._run_action(a, slot)
        except Exception:
            self.log_error(f'entity {getattr(a, "slot", "?")} sprite {getattr(a, "sprite_index", "?")} program {slot}')

    _logged = set()

    def log_error(self, where):
        """Writes the current exception to crash.log (each distinct one once per run) and goes on."""
        import traceback, time
        tb = traceback.format_exc()
        sig = (where.split(' frame')[0], tb.strip().splitlines()[-1], tb.strip().splitlines()[-3] if tb.count('\n') > 2 else '')
        if sig in Game._logged: return
        Game._logged.add(sig)
        try:
            with open(ROOT / 'crash.log', 'a', encoding='utf-8') as f:
                f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} map {getattr(getattr(self, 'map', None), 'id', '?')} "
                        f"(kept running: {where}) ===\n{tb}")
        except OSError:
            pass
        if os.environ.get('REMAKE_STRICT'): raise

    def _run_action(self, a, slot):
        """0x80039198: the map record's program for the slot (0x80042BB8) or else the
        sprite's built-in one.  A, D, E, F programs start from the top on every call;
        B and C keep their place, and C gets back the animation / facing it had when
        another program interrupted it.  A, D, E and F share one scratch context
        (0x80153340) that 0x80042A40 sets to the program's start on every call, so they
        run once, up to their first stop (op 00), wait or end, and are never resumed: an
        F program runs from its top on each talk, and an 00 after a message is where
        that talk ends (the sailors on the ship, map 389)."""
        if a.programs.get(slot, 0) & 0x7F:
            if slot == 'F':                                      # 0x80042CA0: Alundra stops
                p = self.player; p.fx = p.fy = 0; p.sfx = p.sfy = 0   # (+0xC4 +0xC8 +0xD4 +0xD8)
            if slot == 'C':
                st = a.states.get('C')
                if st is None:
                    st = self.start_program(a, 'C')
                elif a.last_action != 'C':
                    a.target_anim, a.target_dir = a.saved_c
            else:
                if a.last_action == 'C': a.saved_c = (a.target_anim, a.target_dir)
                st = self.start_program(a, slot)
            a.last_action = slot
            if st is None: return
            r = self.vm.run(a, slot, st)
            if r == 'restart': a.states[slot] = None if slot == 'C' else a.states.get(slot)
        else:
            self.sprite_ai.run(a, slot)

    def entity_dispatch(self, keys):
        """0x80038F24 frees the slots destroyed last frame and counts the table; then
        0x80038FC4: MovePlayer, every entity's action, and the actions run in slot order
        (passes repeat while anything ran, so entities spawned past the count start now)."""
        for i in range(1, 64):
            a = self.slots[i]
            if a is not None and not a.alive: self.slots[i] = None; self.slot_fc[i] = 0   # the blank record
        self.count = max((i for i in range(64) if self.slots[i] is not None), default=0)
        self.count0 = self.count                                 # 0x801D93EC as counted now (the counters
        self.update_player(keys)                                 # loop uses it: a slot taken past it waits)
        self.sel_count = self.count
        for i in range(1, self.count + 1):
            a = self.slots[i]
            if a is not None: a.action = self.choose_action(a) if a.alive else None
        ran = True
        while ran:
            ran = False; i = 1
            while i <= self.count:
                a = self.slots[i]
                if a is not None and a.alive and a.action is not None:
                    act = a.action
                    self.run_action(a, act)
                    a.action = None; ran = True
                i += 1
        self.sel_count = 64

    def check_portals(self):
        """Doors and exits (portal records): walk into the area facing the door's way."""
        p = self.player
        if self.warps_disabled or self.player_locked or self.talk is not None or self.dialogue is not None: return
        tx, ty, _ = p.tile()
        inside = [w for w in self.map.warps if w['rect'][0] <= tx <= w['rect'][2] and w['rect'][1] <= ty <= w['rect'][3]]
        if not inside: self.portal_armed = True; return
        if not getattr(self, 'portal_armed', True): return
        held = self.pad_held
        for w in inside:
            want = (0x4000, 0x1000, 0x8000, 0x2000)[w['facing']]       # down, up, left, right
            if held & want:
                self.portal_armed = False
                self.pending_warp = (w['map'], w['x'] * TW + TW // 2, w['y'] * TH + TH // 2, w['z'] * 16)
                p.target_dir = (0, 16, 8, 24)[w['arrive_facing']]
                return

    SHAKE = 0x801F94D0          # s32[9]: on, limit x, limit y, step x, step y, offset x, offset y, xmin, ymin

    def _shake_step(self):
        """0x8002CAD0 (first thing the tile draw 0x8002D080 does): the screen shake offsets
        walk between -limit and +limit by the step each frame; off clears the words."""
        m = self.mem; S = self.SHAKE
        if not m.s32(S):
            for o in (4, 8, 0xC, 0x10, 0x14, 0x18): m.w32(S + o, 0)
            return
        for lim, step, off, mn in ((4, 0xC, 0x14, 0x1C), (8, 0x10, 0x18, 0x20)):
            a = m.s32(S + lim); st = m.s32(S + step)
            if not a or (off == 0x14 and not st): m.w32(S + off, 0); continue   # (y ignores a 0 step)
            if m.s32(S + mn):
                v = m.s32(S + off) + st
                if v >= a: v = a; m.w32(S + mn, 0)
            else:
                v = m.s32(S + off) - st
                if -a >= v: v = -a; m.w32(S + mn, 1)
            m.w32(S + off, v)

    def _camera_target(self):
        if self.camera_at: x, y, z = self.camera_at
        else:
            f = self.camera_follow or self.player
            x, y, z = f.wx, f.wy, f.z
        return int(x), int(y), int(z)

    def step_camera(self):
        """RenderTiles 0x8002D080: the shake steps, then the camera snaps to the followed
        sprite (word 0x801D7B3C, set by every map load) or eases 1/16 of the way to the
        target (followed x - 0xA0, y - z - 0x88) plus the shake offset and the one-frame
        jolt words; it stays within 0..0x39F, 0..0x2CF (game pixels, no margin)."""
        self._shake_step()
        x, y, z = self._camera_target()
        if self.cam is None or self.mem.s32(0x801D7B3C):
            cx, cy = x - 0xA0, y - z - 0x88; self.mem.w32(0x801D7B3C, 0)
        else:
            cx, cy = self.cam
            cx += ((x - (cx + 0xA0)) >> 4) + self.mem.s32(self.SHAKE + 0x14) + self.mem.s32(0x801B6C48)
            cy += ((y - z - (cy + 0x88)) >> 4) + self.mem.s32(self.SHAKE + 0x18) + self.mem.s32(0x801B6C4C)
        self.mem.w32(0x801B6C48, 0); self.mem.w32(0x801B6C4C, 0)               # (0x8002D080 clears them)
        self.cam = (max(0, min(0x39F, cx)), max(0, min(0x2CF, cy)))
        self.mem.w32(0x801EF434, self.cam[0]); self.mem.w32(0x801EF438, self.cam[1])   # the game's camera words

    def camera(self):
        if getattr(self, 'cam', None) is None:                # drawn before the first camera step of the new
            x, y, z = self._camera_target()                   # map: where it will snap (no shake step spent)
            return max(0, min(0x39F, x - 0xA0)), max(0, min(0x2CF, y - z - 0x88)) + self.map.margin
        return self.cam[0], self.cam[1] + self.map.margin

    FEET = 16                            # Feet clipping Never: the sprite's lowest pixels kept above the floor

    def render(self):
        from engine import screen as escreen
        v = self.view; mp = self.map; p = self.player
        if self.front is not None:
            v.set_clip(None); self.front.draw(v); return
        t = self.trans
        if t is not None:                                    # a map change: only its picture (OT + 0xC)
            if t.get('show'):
                escreen.draw_transition(self, v); t['show'] = False
            return                                           # the last picture stays up while it waits
        v.set_clip(escreen.clip_rect(self))                  # the drawing box (DRAWENV clip)
        v.fill(self.clear_colour)                            # ... cleared with the clear colour
        cam = self.camera()
        gcam = (cam[0], cam[1] - mp.margin)                  # the game's camera has no margin
        mp.lining.draw(v, gcam[0], gcam[1], front=False)
        # the game's ordering table (0x8002D080 tiles, 0x8002E498 sprites): 16 slots per map row -
        # 0..5 the row's floor tops, 6 its sprites and effects (sorted by key, smallest first; a
        # shadow is its entity's key - 1), 7..12 the row's walls.  Rows in map order.
        items = {}
        def put(key, kind, obj):
            row = max(0, min(mp.h - 1, min(59, key >> 20)))
            items.setdefault(row, []).append((key, kind, obj))
        # Mods > Character clipping (Shift+0; Never by default): Original as the game (the floor tiles of the rows in front, drawn
        # after a sprite, cover whatever of it reaches into them - feet on stairs, by bushes and
        # ledges); Never lays the sprite's lowest FEET pixels again on each such tile, right
        # after the tile is drawn (the rest of the body keeps the game's covering).  Only floor:
        # floor squares (not blocked, not a bed - build_pieces) no higher than where the sprite
        # stands (+ FLOOR_SLACK); beds, furniture, ledges and walls still cover it as in the game
        feet_never = self.settings.get('feet_clip', 0) == 0
        feet = []
        clip0 = v.get_clip()
        for a in [p] + self.actors:
            if not a.alive or a.estatus not in (2, 3): continue   # 0x80038DCC: the draw list holds status 2 and 3
            key = getattr(a, 'sort_key', None)
            if key is None: key = (a.py & ~0xFFFF) + ((a.pz >> 16) & 0xFFFF)
            put(key, 1, a)
            if feet_never:
                fy = ((a.py - a.pz) >> 16) + mp.margin - cam[1]      # the feet line on screen
                band = pygame.Rect((a.px >> 16) - cam[0] - 64, fy - self.FEET, 128, self.FEET + 8)
                if band.colliderect(clip0):
                    feet.append((band, a, max(0, min(mp.h - 1, min(59, key >> 20))), (a.pz >> 16) + FLOOR_SLACK))
        # Mods > Shadow clipping (Shift+0; Never by default): Original draws a shadow where the game's ordering table puts
        # it (its entity's key - 1), so the floor tiles of the rows after it, drawn later, cover
        # its lower part.  Never draws it there too, then lays it again on each floor tile of a
        # later row that it overlaps, right after that tile is drawn: no floor covers it
        never = self.settings.get('shadow_clip', 0) == 0
        shadows = []
        if never:
            owned = {id(a.shadow) for a in [p] + self.actors if a.shadow is not None and not isinstance(a.shadow, int)}
        for e in self.effects.list:                          # 0x8003CDF4: the records in use (state 2); an
            if e.state != 2: continue                        # entity's shadow is one, keyed just before it
            put(e.f64, 2, e)
            if never and id(e) in owned:
                r = e.screen_rect(cam, mp.margin)
                if r is not None and r.colliderect(clip0):
                    shadows.append((r, e, max(0, min(mp.h - 1, min(59, e.f64 >> 20))), (e.z >> 16) + FLOOR_SLACK))
        top, bottom = cam[1] - TH, cam[1] + VIEW_H                # a piece is drawn when top < py < bottom
        spans = getattr(mp, 'row_span', {})
        for y in range(0, mp.h):
            walls = []
            sp = spans.get(y)
            row = mp.pieces_by_row.get(y, ()) if sp is None or (sp[1] > top and sp[0] < bottom) else ()
            for code, px, py, wall, th in row:
                if wall: walls.append((code, px, py)); continue
                sx, sy = px - cam[0], py - cam[1]
                if -TW < sx < VIEW_W and -TH < sy < VIEW_H:
                    r = mp.tile_rect(code)
                    if r:
                        v.blit(mp.atlas, (sx, sy), r)
                        if shadows or feet:
                            tile = pygame.Rect(sx, sy, r[2], r[3])
                            # (own names for the heights: reusing `top` here overwrote the row cull
                            # bound above, so a falling sprite's height made the later rows of the
                            # screen vanish - Wendell's dream walls going black as the slimes drop)
                            for sr, e, srow, s_top in shadows:           # shadows first, then the feet on them
                                if y > srow and th is not None and th <= s_top and sr.colliderect(tile):
                                    v.set_clip(tile.clip(clip0)); e.draw(v, cam, mp.margin)
                            for band, a, arow, f_top in feet:
                                if y > arow and th is not None and th <= f_top and band.colliderect(tile):
                                    v.set_clip(tile.clip(band).clip(clip0)); a.draw(v, cam, mp.margin)
                            v.set_clip(clip0)
            for key, kind, o in sorted(items.get(y, ()), key=lambda t: t[0]):
                o.draw(v, cam, mp.margin)
            for code, px, py in walls:
                sx, sy = px - cam[0], py - cam[1]
                if -TW < sx < VIEW_W and -TH < sy < VIEW_H:
                    r = mp.tile_rect(code)
                    if r: v.blit(mp.atlas, (sx, sy), r)
        mp.lining.draw(v, gcam[0], gcam[1], front=True)
        escreen.draw_overlay(self, v)                       # the fade TILE (0x801F5368), under the windows
        gf = self.game_font
        self.message_ui.draw(v)                              # tasks 0 / 12 (engine/message.py)
        self.draw_save_windows(v)                            # the save menu (tasks 9 / 10, engine/savewin.py)
        self.draw_choice(v)                                  # YES / NO (task 3, engine/choice.py)
        if not self.hud.draw(v, p.hp, p.hp_max, *self.magic_pair(), self.gilder,
                             max(0, self.weapon_item()), max(0, self.selected_item())):
            hud = f'Life {p.hp}/{p.hp_max}   Gilder {self.gilder}'
            v.blit(self.font.render(hud, True, (255, 255, 255)), (VIEW_W - 130, 2))
        if self.inventory_ui.active(): self.inventory_ui.draw(v)
        self.draw_portrait(v)                                # the HUD portrait (OT 0x801F53AC, over the windows)
        v.set_clip(None)
        gy = VIEW_H - 28                                         # game-font messages (speedrun states): low, centred
        for i, (t, _, *game) in enumerate(self.toasts):
            if game and game[0] and self.game_font.ok:          # on the menus' parchment (the font is dark)
                w = self.game_font.width(t) + 32; x = (VIEW_W - w) // 2
                v.blit(self.settings_screen.parchment(w, 32), (x, gy - 8))
                self.game_font.draw(v, t, x + 16, gy); gy -= 34
            else:
                v.blit(self.font.render(t, True, (255, 230, 120)), (8, 16 + i * 12))
        if self.debug:
            tx, ty, tz = p.tile()
            info = f'map {mp.id} tile {tx},{ty} z{tz} actors {len(self.actors)} flags 0x{self.mem.u32(self.FLAGS):08X}'
            v.blit(self.font.render(info, True, (120, 255, 120)), (2, 2))
            unk = ' '.join(f'{k}x{n}' for k, n in sorted(self.unknown_ops.items())[:14])
            v.blit(self.font.render('not decoded: ' + unk, True, (255, 160, 120)), (2, 14))

    BIZHAWK_DELAY = 3        # game frames: the stock game in BizHawk draws a frame's picture after the VSync and
                             # shows it at the next buffer swap (2026-10-24, emulated GPU VRAM: logic frame 1,
                             # drawn by frame 3, shown at frame 4; docs/2026-10-23-input-latency-compare.txt).
                             # Real hardware side by side with the remake's PC setting: no frames
                             # apart (user, 2026-10-24) - the delay is BizHawk's, not the console's.

    OSSC_DELAY = 1           # game frames (user, 2026-10-26)

    def shown_view(self):
        """Mods > Delay: PC & CRT shows the frame just drawn; OSSC & RetroTink the one drawn
        OSSC_DELAY game frames earlier, BizHawk BIZHAWK_DELAY.  Input is read once a game frame (59.826 a second, the PS1's rate) and the game
        logic is the same either way."""
        lag = {'ossc': self.OSSC_DELAY, 'bizhawk': self.BIZHAWK_DELAY}.get(self.settings.get('display_lag'), 0)
        if not lag:
            self.__dict__.pop('_lag_frames', None); return self.view
        q = self.__dict__.setdefault('_lag_frames', [])
        if not q or q[-1][0] != self.frame_no: q.append((self.frame_no, self.view.copy()))
        else: q[-1] = (self.frame_no, self.view.copy())
        del q[:-8]
        want = self.frame_no - lag
        old = [v for f, v in q if f <= want]
        return old[-1] if old else q[0][1]

    def present(self):
        dst = self.view_rect()
        if dst.size != self.screen.get_size():                   # only the borders are black
            W, H = self.screen.get_size(); fill = self.screen.fill
            if dst.x: fill((0, 0, 0), (0, 0, dst.x, H)); fill((0, 0, 0), (dst.right, 0, W - dst.right, H))
            if dst.y: fill((0, 0, 0), (0, 0, W, dst.y)); fill((0, 0, 0), (0, dst.bottom, W, H - dst.bottom))
        try: sub = self.screen.subsurface(dst)                  # scaled straight into the window
        except (ValueError, pygame.error): sub = None
        out = video_filter.upscale(self.shown_view(), dst.size, self.settings, sub)
        if out is not sub: self.screen.blit(out, dst.topleft)
        pygame.display.flip()

    def draw(self):
        self.render(); self.present()

    def write_trace(self):
        out = ROOT / 'script_trace.txt'
        lines = [f'{slot} @{ci:X} op {op:02X} {eventvm.DOC.get(op, "?")} -> {d}' for slot, ci, op, d in (self.vm.trace or [])[-4000:]]
        out.write_text('\n'.join(lines)); self.toast(f'trace written to {out.name}')

    def run(self, frames=None):
        n = 0; self._backdrop = None
        if not hasattr(self, '_combo_held'): self._combo_held = False
        self.pacer = pacing.Pacer(getattr(self, 'vsync', False))
        while frames is None or n < frames:
            for e in self.controls.events(pygame.event.get()):
                if e.type == pygame.QUIT: return
                if e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED): self.controls.refresh_pads()
                if self.controls_screen.handle(e): continue
                if speedrun.active() and speedrun.hotkey(self, e): continue   # Speedrun > Save / Load button
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE: return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_F5: self.settings_screen.show(); continue
                if (e.type == pygame.KEYDOWN and e.key in (pygame.K_0, pygame.K_KP0)
                        and e.mod & pygame.KMOD_CTRL and e.mod & pygame.KMOD_SHIFT):
                    self.settings_screen.show_clip_mods(); continue     # Mods > Shadow / Character clipping
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F1: self.debug = not self.debug
                    if e.key == pygame.K_F6: self.debug_dump()
                    if e.key == pygame.K_F4:
                        if self.vm.trace is None: self.vm.trace = []; self.toast('tracing scripts (F4 again to save)')
                        else: self.write_trace(); self.vm.trace = None
                    if e.key in (pygame.K_F2, pygame.K_F3):
                        m = self.map.id + (1 if e.key == pygame.K_F2 else -1)
                        try: self.load_map(m)
                        except FileNotFoundError: pass
            combo = bool(self.controls.held(pygame.key.get_pressed()) & controls_mod.MENU_BIT)   # Controls > Menu shortcut
            if combo and not self._combo_held and not self.settings_screen.open:
                self.settings_screen.show()                     # Select (as bound, keys or pad) opens it
            self._combo_held = combo
            due = self.pacer.due()                              # game frames to run now (pacing.py)
            if self.settings_screen.open:                       # the game stays paused under the page
                if self._backdrop is None:
                    self.render(); self._backdrop = self.view.copy()       # the paused frame, 320 x 240
                if due:
                    self.settings_screen.draw(self.screen, self._backdrop); pygame.display.flip()
                    self.snd.tick()                             # (update() ticks it while the game runs)
            else:
                self._backdrop = None
                if due:
                    keys = pygame.key.get_pressed()
                    for _ in range(due):
                        try: self.update(keys)
                        except Exception: self.log_error('game frame')
                    try: self.draw()
                    except Exception: self.log_error('drawing')
                elif self.pacer.lockstep:                       # a refresh with no game frame due (pacing.py):
                    try: self.present()                         # the same picture again, still on the refresh
                    except Exception: self.log_error('drawing')
            self.pacer.wait(); n += 1
        self.save_unknown()

    def save_unknown(self):
        (ROOT / 'not_decoded.txt').write_text('\n'.join(f'{k}\t{n}' for k, n in sorted(self.unknown_ops.items(), key=lambda x: -x[1])))


SAME_MAP_SETUP = 27                   # warp within the map: frames the original spends after the skipped map
                                      # read (BizHawk 2026-10-19, map 163 stairs up: 48 frames trigger -> arrival
                                      # against the remake's 22; Options > Loading pauses Instant skips it)
SAME_MAP_SETUP_BY_MAP = {140: 24, 115: 23, 21: 27, 69: 28, 80: 28, 86: 25, 304: 22, 163: 28}
                                      # measured per map (BizHawk 2026-10-23, tools/run_samemap_warp.py: the
                                      # game's own same-map warp request; play time resumes 22 + these + 2 frames
                                      # after it; 140 also matches the Fire Manor door walked into).  The set-up
                                      # time does not follow map size, objects or scripts; unmeasured maps: 27
MUSIC_AFTER_MAP = 18                  # see Game.warp_arrive (fitted, 2026-10-23)
BANK_SEEK = 23                        # see Game.bank_read_frames (fitted, 2026-10-23)
MUSIC_SEEK = 20                       # see Game.music_read_frames
MAP_SEEK = 12                         # see Game.load_frames
FDS_JINGLE = 2.18                     # Rare Item Jingle PS2 FDS: tempo (docs/2026-10-22-ps2-fds-loads-and-jingle.txt)
XA_SEEK_ITEMS, XA_SEEK = (43, 44, 47, 48), 26   # see Game.warp_arrive (one measured seek; real seeks vary)
FLOOR_SLACK = 4                       # Options > clipping Never: a floor tile up to this many pixels above
                                      # the sprite's height still counts as its floor (slopes)
NEW_GAME = (389, 0x21, 0x23, 0)      # stock new game: ship (ALUN_CD.EXE 0x80031D4C..58)
WAKE_UP = (163, 40, 9, 2)             # Jess's house, first wake (intro skipped)

def tint_rgb(ui, key, img, rgb):
    """A sprite drawn with colour (r, g, b): texel * c / 0x80 per channel, clamped at 31 (the
    GPU's texture modulation); cached in ui.shaded."""
    if rgb == (0x80, 0x80, 0x80): return img
    out = ui.shaded.get(key)
    if out is None:
        out = img.copy()
        try:
            import numpy as np
            a = pygame.surfarray.pixels3d(out)
            for i, c in enumerate(rgb):
                c5 = np.minimum(31, (a[..., i].astype(np.int32) >> 3) * c >> 7)
                a[..., i] = (c5 << 3 | c5 >> 2).astype(np.uint8)
            del a
        except ImportError:
            pass
        ui.shaded[key] = out
    return out


def emenu_life_max(g):
    from engine import menu as _m
    return _m.life_max(g)


def emenu_life(g):
    from engine import menu as _m
    return _m.life(g)


SAVES = ROOT / 'saves'


def card_slots(settings=None):
    """The memory cards: slot 1 is saves/card1.mcd (a raw 128 KB card image, the kind emulators
    keep - one can be copied in); without one, a new formatted card that is written on the first
    save.  Slot 2 holds saves/card2.mcd when there is one, else nothing."""
    from engine import bios_card as B
    s1 = B.Slot(str(SAVES / 'card1.mcd'))
    if not s1.present: s1 = B.Slot(str(SAVES / 'card1.mcd'), data=B.blank_formatted())
    p2 = SAVES / 'card2.mcd'
    s2 = B.Slot(str(p2)) if p2.exists() else B.Slot()
    return B.Bios(s1, s2)


def new_game_start():
    m, x, y, z = NEW_GAME
    return m, (x * TW + TW // 2, y * TH + TH // 2, z * 16)


if __name__ == '__main__':
    import faulthandler                                  # a crash inside pygame / SDL (no Python exception)
    _fault = open(ROOT / 'crash.log', 'a', encoding='utf-8')   # still leaves where it happened
    import platform, time as _time
    _fault.write(f"\n=== {_time.strftime('%Y-%m-%d %H:%M:%S')} start: Python {platform.python_version()}, "
                 f"pygame {pygame.version.ver}, SDL {'.'.join(map(str, pygame.get_sdl_version()))}, "
                 f"audio {os.environ.get('SDL_AUDIODRIVER', 'default')} ===\n"); _fault.flush()
    faulthandler.enable(_fault, all_threads=True)
    # no arguments: the disc's boot program (movies, title screen); --new-game: straight onto the
    # ship; --wake-up: Jess's house; map [x y height]: that map
    args = sys.argv[1:]
    m, x, y, z = NEW_GAME if '--new-game' in args else WAKE_UP
    nums = [int(a) for a in args if a.lstrip('-').isdigit()]
    if nums: m, x, y, z = (nums + [None, None, 0])[:4] if len(nums) > 1 else (nums[0], None, None, 0)
    start = None if x is None else (x * TW + TW // 2, y * TH + TH // 2, z * 16)
    boot = not args
    if boot: m, start = new_game_start()
    g = Game(m, start, boot=boot, new_game=boot or '--new-game' in args)
    try: g.run()
    except Exception:
        import traceback, time
        with open(ROOT / 'crash.log', 'a', encoding='utf-8') as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} map {getattr(getattr(g, 'map', None), 'id', '?')} ===\n")
            traceback.print_exc(file=f)
        raise
    finally: g.save_unknown()
