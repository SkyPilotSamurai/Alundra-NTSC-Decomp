"""The programs around the game: the boot program SLUS_005.53 (movies, title screen, the History
Book check, Now Loading), the ending END.EXE (the closing movie) and CLOSING.EXE (the credits),
ported from the US disc.  Research notes: research/slus, research/end, research/closing.

Boot (SLUS_005.53 main 0x800255B0), for ever:
    movie USA_OP  (0x80027F5C(0, 0x28, ..., 0xA4C frames, skip Start / Cross))
    title         (0x8002536C(1) -> 0x80021F2C(1800 frames, music 1))
    movie ARAN_OP (0x80027F5C(8, 0x10, ..., 0xEAB frames, skip Start / Cross))
    title
  The title gives 0 (START: Now Loading, then ALUN_CD.EXE starts a new game), 1 (CONTINUE: the
  History Book, history_book.py - a record picked: Now Loading, then ALUN_CD.EXE continues it;
  none: the title again) or -1 (30 seconds without a button: on to the next movie).
Ending (ALUN_CD.EXE warp effect 9 -> END.EXE 0x800212EC): movie ARAN_END (0x80023CC4(0, 0x28, ...,
  0x19C5 frames, skip Start), then CLOSING.EXE: the credits to ENDING.XA, ending on THE END - the
  program then waits for ever (there is no way back to the title in it).

Each scene is updated and drawn once a frame (60 Hz) by Game.run while Game.front is set."""
import io, json, math, zipfile
from pathlib import Path
import pygame
from sound_system import OUTPUT          # the console's output level (sound_system.py)

from home import HOME as ROOT
ASSETS = ROOT / 'assets'
W, H = 320, 240
UP, DOWN, START, CROSS = 0x1000, 0x4000, 0x800, 0x40
CIRCLE, TRIANGLE, LEFT, RIGHT = 0x20, 0x10, 0x8000, 0x2000
L1, R1 = 0x04, 0x08
SPEEDRUN = ASSETS / 'speedrun'   # the speedrun starts, us/ and jp/ (tools/speedrun_states.py: continue records)
EXE_SIZES = {'ALUN_CD.EXE': 706560, 'END.EXE': 245760, 'CLOSING.EXE': 1626112, 'SLUS_005.53': 1241088}


NOW_LOADING_MIN = 120          # the Now Loading picture stays at least 2 seconds, whatever Mods > Loading pauses


def cd_frames(g, size):
    """A file read from the CD at double speed (5120 bytes a frame) after a seek - the black or
    Now Loading pause while an EXE loads.  Mods > Loading pauses: Instant none, Custom the
    player's own number of frames."""
    from settings_screen import load_pause
    return max(1, load_pause(g.settings, 6 + -(-size // 5120), -(-size // 5120)))   # Mods > Loading pauses


def tint(img, c):
    """A textured sprite of colour (c, c, c): texel * c / 128 (0x80 = as drawn), as the GPU does."""
    if c == 128: return img
    out = img.copy()
    if c < 128:
        out.fill((min(255, c * 2),) * 3 + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    else:
        add = img.copy()
        add.fill((min(255, (c - 128) * 2),) * 3 + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(add, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    return out


def fade_tile(surf, v):
    """The full-screen TILE: subtract -v when v < 0, add v when v > 0."""
    if v < 0: surf.fill((-v,) * 3, special_flags=pygame.BLEND_RGB_SUB)
    elif v > 0: surf.fill((v,) * 3, special_flags=pygame.BLEND_RGB_ADD)


def rsin(a):
    """0x8003081C: sine of a (4096 a turn) in 4096ths."""
    return int(round(math.sin((a & 0xFFF) * math.pi / 2048) * 4096))


def _div(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def load(path):
    return pygame.image.load(str(path)).convert_alpha()


# ------------------------------------------------------------------------- scenes --
class Scene:
    done = False
    result = None

    def update(self, g, held): pass

    def draw(self, g, surf): pass


class Black(Scene):
    """Nothing drawn (an EXE loading, or the frames between two programs)."""
    def __init__(self, frames):
        self.n = frames
        if frames <= 0: self.done = True

    def update(self, g, held):
        self.n -= 1
        if self.n <= 0: self.done = True

    def draw(self, g, surf): surf.fill((0, 0, 0))


class Picture(Scene):
    """A still picture shown while something loads (TIM 6, Now Loading, 0x800252E0)."""
    def __init__(self, img, frames): self.img = img; self.n = frames

    def update(self, g, held):
        self.n -= 1
        if self.n <= 0: self.done = True

    def draw(self, g, surf): surf.fill((0, 0, 0)); surf.blit(self.img, (0, 0))


class Movie(Scene):
    """The MDEC movie player (SLUS 0x80027F5C / END 0x80023CC4): the frames at 15 a second in the
    display area at (x, y), the XA audio at full volume.  A press of only the skip buttons (mask)
    lowers the volume by 0x400 a frame; the movie ends when it reaches 0, or at frame `end`
    (where the volume has been going down since frame end - 15)."""
    def __init__(self, g, name, x, y, end, mask):
        self.name, self.x, self.y, self.end, self.mask = name, x, y, end, mask
        meta = json.loads((ASSETS / 'movies' / 'movies.json').read_text()).get(name, {})
        self.packs = [(a, b, ASSETS / 'movies' / f'{name}_{k}.zip') for k, (a, b) in enumerate(meta.get('packs', []))]
        self.frames = meta.get('frames', 0); self.end = min(end, self.frames) if self.frames else 0
        self.zip = None; self.zip_range = (0, 0); self.cur = -1; self.img = None
        self.state = 1; self.vol = 0x7FFF; self.ticks = 0; self.started = False; self.skip = False
        self.audio = ASSETS / 'movies' / f'{name}.ogg'
        if not self.packs or not self.end: self.done = True

    def _frame(self, i):
        if not (self.zip_range[0] <= i < self.zip_range[1]):
            for a, b, p in self.packs:
                if a <= i < b:
                    if self.zip: self.zip.close()
                    self.zip = zipfile.ZipFile(p); self.zip_range = (a, b); break
            else:
                return None
        try: return pygame.image.load(io.BytesIO(self.zip.read(f'frames/{i:05d}.jpg')), 'f.jpg').convert()
        except (KeyError, pygame.error): return None

    def _volume(self, g):
        try: pygame.mixer.music.set_volume(self.vol / 0x7FFF * g.settings.get('music_volume', 100) / 100 * OUTPUT)
        except pygame.error: pass

    def start(self, g):
        self.started = True
        g.snd.music_stop(False); g.snd.stop_all()
        try:
            pygame.mixer.music.load(str(self.audio)); pygame.mixer.music.play(0)
            self.audio_on = True
        except pygame.error:
            self.audio_on = False
        self._volume(g)

    def update(self, g, held):
        if self.done: return
        if not self.started: self.start(g)
        self.ticks += 1
        pos = -1
        if self.audio_on:
            try: pos = pygame.mixer.music.get_pos()
            except pygame.error: pos = -1
        if pos != getattr(self, '_last_pos', None): self._last_pos = pos; self._pos_tick = self.ticks
        stalled = self.ticks - getattr(self, '_pos_tick', 0) > 30      # the sound device stopped moving:
        if pos >= 0 and pygame.mixer.music.get_busy() and not stalled:   # the movie keeps its own time
            want = pos * 15 // 1000; self._pos_frame = want; self._pos_at = self.ticks
        else:
            want = max(self.ticks // 4, getattr(self, '_pos_frame', 0) + (self.ticks - getattr(self, '_pos_at', 0)) // 4)
        if (held | self.mask) == self.mask and held & self.mask: self.skip = True   # (a tap between two
        while self.cur < want and not self.done:           # movie frames still counts) - one pass of the
            self.cur += 1                                  # player's loop per movie frame
            img = self._frame(self.cur)
            if img is not None: self.img = img
            if self.skip: self.state = 2
            if self.end - 15 < self.cur: self.vol = max(0, self.vol - 0x400)
            if not (self.cur < self.end and (self.state == 1 or self.vol - 0x400 > 0)):
                self.finish(g); return
            if self.state == 2: self.vol = max(0, self.vol - 0x400)
            self._volume(g)

    def finish(self, g):
        self.done = True
        try: pygame.mixer.music.stop()
        except pygame.error: pass
        if self.zip: self.zip.close(); self.zip = None
        g.snd.apply_volume()

    def draw(self, g, surf):
        surf.fill((0, 0, 0))
        if self.img is not None: surf.blit(self.img, (self.x, self.y))


class TitleArt:
    """The title's pictures (tools/remake_export_title.py) and the logo upload state that
    lives on in VRAM between visits (D_80042DDC / D_80042DE0)."""
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None: cls._inst = cls()
        return cls._inst

    def __init__(self):
        d = ASSETS / 'title'
        self.title = load(d / 'title.png')
        self.logos = {i: load(d / f'logo{i}.png') for i in range(1, 10)}
        self.loading = load(d / 'loading.png')
        self.scroll = load(d / 'scroll.png'); self.font = load(d / 'font.png')
        meta = json.loads((d / 'title.json').read_text())
        self.glyphs = {int(k): v for k, v in meta['glyphs'].items()}; self.texts = meta['texts']
        self.logo = None                       # the logo frame in VRAM (none before the first upload)
        self.ddc = 3; self.de0 = 0
        self.bottom = self.title.subsurface((0, 200, 320, 40)).copy()
        self.items = [self.title.subsurface((96, 160, 128, 16)).copy(), self.title.subsurface((96, 176, 128, 16)).copy(),
                      self._speedrun_word(), self._options_word()]
        self.tm = self.title.subsurface((0, 160, 32, 16)).copy()
        self.us = (self.logos, self.bottom, self.items[:2], self.tm); self.lang = 'us'; self.wrap = 9
        self.layout = (0xB8 + 16, 0x88)        # (the copyright lines' y, the first word's y)

    def set_lang(self, lang):
        """A European language: its disc's title picture (the menu words, the copyright lines, the TM;
        assets/title_eu/<lang>/title.png) and the European logo (ANM 1-8, DE 0x80021A1C cycles 4-8);
        else the US ones.  The remake's SPEEDRUN / OPTIONS words stay the US letters."""
        if lang == self.lang: return
        eu = ASSETS / 'title_eu'; f = eu / lang / 'title.png'
        if lang in ('en_eu', 'fr', 'de', 'it', 'es') and f.exists() and (eu / 'logo8.png').exists():
            t = load(f)
            self.logos = {i: load(eu / f'logo{i}.png') for i in range(1, 9)}; self.wrap = 8
            self.bottom = t.subsurface((0, 192, 320, 48)).copy()    # DE 0x80021788: rows 192-239, drawn at y 192
            self.items[:2] = [t.subsurface((96, 160, 128, 16)).copy(), t.subsurface((96, 176, 128, 16)).copy()]
            self.tm = None                                           # (the European logo frames carry the TM)
            self.layout = (0xC0, 0x80)
        else:
            self.logos, self.bottom, items, self.tm = self.us; self.items[:2] = items; self.wrap = 9
            self.layout = (0xB8 + 16, 0x88)
        self.lang = lang; self.logo = None; self.ddc = 3; self.de0 = 0


    def loading_for(self, g):
        """Now Loading: the European discs' picture (assets/title_eu, tools/remake_export_title_eu.py)
        for a European language, else the US one."""
        if getattr(g, 'lang', 'us') in ('en_eu', 'fr', 'de', 'it', 'es'):
            if not hasattr(self, '_eu_loading'):
                f = ASSETS / 'title_eu' / 'loading.png'
                self._eu_loading = load(f) if f.exists() else None
            if self._eu_loading is not None: return self._eu_loading
        return self.loading

    def _options_word(self):
        """The remake's OPTIONS: assets/title/options.png (128 x 16 like START / CONTINUE: the
        letters lifted from START's and CONTINUE's own (P is START's R without its leg), on one
        box with their row shading, 1 pixel apart), else pieced from title.png as before."""
        f = ASSETS / 'title' / 'options.png'
        if f.exists():
            try: return load(f)
            except Exception: pass
        O = self._cut(127, 140, 176); N = self._cut(140, 151, 176); I = self._cut(162, 168, 176)
        T = self._cut(140, 152, 160); S = self._cut(131, 140, 160)
        return self._word([O, self._p(), T, I, O, N, S])

    def _cut(self, x0, x1, y): return self.title.subsurface((x0, y, x1 - x0, 16)).copy()

    def _p(self):
        P = self._cut(161, 172, 160)
        for y in range(11, 15):                        # the R's leg: rows 11-14, right of the stem,
            fill = P.get_at((1, y))                    # and the A's foot left of it
            for x in range(6, P.get_width()): P.set_at((x, y), fill)
            P.set_at((0, y), fill)
        return P

    def _speedrun_word(self):
        """The remake's SPEEDRUN: assets/title/speedrun.png (128 x 16, like OPTIONS) when there is one,
        else from START's and CONTINUE's letters (D: R's stem and O's right side)."""
        f = ASSETS / 'title' / 'speedrun.png'
        if f.exists():
            try: return load(f)
            except Exception: pass
        R = self._cut(161, 172, 160); E = self._cut(190, 201, 176)
        D = pygame.Surface((12, 16), pygame.SRCALPHA); D.blit(self._cut(161, 166, 160), (0, 0)); D.blit(self._cut(133, 140, 176), (5, 0))
        return self._word([self._cut(131, 140, 160), self._p(), E, E, D, R, self._cut(179, 190, 176), self._cut(168, 179, 176)])

    def _word(self, letters):
        w = sum(l.get_width() for l in letters)
        out = pygame.Surface((128, 16), pygame.SRCALPHA); x = (128 - w) // 2
        for l in letters: out.blit(l, (x, 0)); x += l.get_width()
        return out


class Title(Scene):
    """0x80021F2C: the title screen.  Fades in from black (+4 a frame from -255; buttons count only
    once it is up), Up / Down pick START / CONTINUE (sound 1, only after all buttons were let go),
    Start or Cross confirm (sound 2); 1800 frames with no button held give up (-1).  The picked
    word brightens to 255 (+4 a frame), then everything fades out (-2 a frame) and two empty
    frames follow.  The music (1) starts with it and fades over 120 frames from the choice."""
    def __init__(self, g, timeout=0x708):
        self.a = TitleArt.get(); self.a.set_lang(getattr(g, 'lang', 'us'))
        self.timeout = timeout
        self.s2 = timeout; self.s1 = 1; self.s4 = 0; self.s6 = 0xA0; self.s5 = 0x40
        self.de4 = 0; self.sel = 0; self.fade = -0xFF
        self.rgb = [0x80] * len(self.a.items)
        self.phase = 'menu'; self.started = False; self.empty = 0
        self.music_fade = None

    def _music(self, g):
        g.snd.stop_all()
        g.snd.music_load_now(1, True)               # 0x80028D48(1): SEQ 1 and its VAB, played at once
        self.started = True

    def _music_tick(self, g):
        if self.music_fade is not None and self.music_fade > 0:     # SsSeqSetDecrescendo(seq, 127, 120)
            self.music_fade -= 1
            try:
                pygame.mixer.music.set_volume(self.music_fade / 120 * g.settings.get('music_volume', 100) / 100 * OUTPUT)
                if g.snd.emu is not None: g.snd.emu.snd_gain(self.music_fade / 120 * g.settings.get('music_volume', 100) / 100 * OUTPUT)
            except pygame.error: pass

    def _logo_step(self):
        a = self.a                                  # 0x80021CB8: a new logo frame every 9 frames
        if a.de0 < 8: a.de0 += 1
        else:
            a.de0 = 0
            a.logo = a.logos[a.ddc + 1]
            a.ddc += 1
            if a.ddc == a.wrap: a.ddc = 3               # (US 9: ANM 4-9; Europe 8: ANM 4-8)

    def update(self, g, held):
        if not self.started: self._music(g)
        self._music_tick(g)
        if self.phase == 'menu':
            self.fade = self.fade + 4 if self.fade < 0 else 0
            if self.fade > 0: self.fade = 0
            s0 = 0 if self.fade < 0 else held
            if self.s1 != 1:                       # (the remake adds OPTIONS under CONTINUE: the
                if s0 & UP and self.sel > 0:           # settings page; START / CONTINUE as the game)
                    self.sel -= 1; self.s4 = self.sel; g.snd.play(1); self.s1 = 1
                if s0 & DOWN and self.sel < len(self.a.items) - 1:
                    self.sel += 1; self.s4 = self.sel; g.snd.play(1); self.s1 = 1
                if s0 & (START | CROSS):
                    g.snd.play(2)
                    if self.sel == 3:
                        self.s1 = 1; self.s2 = self.timeout
                        ss = getattr(g, 'settings_screen', None)
                        if ss is not None: ss.show()
                    else:
                        self._chosen(); return
            if s0: self.s2 = self.timeout
            else: self.s1 = 0
            self.rgb = [0xA0 if i == self.sel else 0x40 for i in range(len(self.a.items))]
            self.de4 += 0x58
            if self.de4 >= 0x1000: self.de4 = 0
            self.s2 -= 1
            self._logo_step()
            if self.s2 == 0:
                self.s4 = -1; self._chosen()
        elif self.phase == 'brighten':
            c = self.rgb[self.s4] + 4
            if c >= 0xFF: c = 0xFF
            self.rgb[self.s4] = c
            self._logo_step()
            if c == 0xFF: self.phase = 'fadeout'
        elif self.phase == 'fadeout':
            self._logo_step()
            self.fade -= 2
            if self.fade < -0xFE: self.phase = 'empty'
        elif self.phase == 'empty':
            self.empty += 1
            if self.empty >= 2: self.done = True; self.result = self.s4

    def _chosen(self):
        self.music_fade = 120                         # 0x80028D00(1)
        self.phase = 'brighten' if self.s4 != -1 else 'fadeout'
        if self.phase == 'fadeout' and self.fade < -0xFE: self.phase = 'empty'

    def draw(self, g, surf):
        a = self.a
        surf.fill((0, 0, 0))
        if self.phase == 'empty': return
        if a.logo is not None: surf.blit(a.logo, (0, 0))            # layer 0: the logo (CLUT 0x1E3)
        surf.blit(a.bottom, (0, a.layout[0]))                        # ... and the copyright lines (US: 16 lower:
                                                                     # room for the remake's SPEEDRUN / OPTIONS)
        base = self.rgb[self.sel]                                    # the picked word pulses
        c = base + _div(rsin(self.de4), 64)
        c = 255 if c >= 0x101 else max(0, c)
        for i, img in enumerate(a.items):                            # layer 1: START / CONTINUE (/ SPEEDRUN / OPTIONS, 8 higher)
            surf.blit(tint(img, c if i == self.sel else self.rgb[i]), (0x60, a.layout[1] + 0x10 * i))
        if a.tm is not None: surf.blit(a.tm, (0x11D, 0x1D))       # (Europe: 0x80 - the words 16 higher, above its copyright)
        fade_tile(surf, self.fade)                                   # layer 200: the fade


class HistoryBook(Scene):
    """CONTINUE (0x80025124): the History Book, the boot program's own code ported in
    history_book.py and run here one frame at a time.  Its result is the record picked (0..3)
    or -1."""
    def __init__(self, g, machine):
        self.b = machine; self.b.g = g
        self.gen = None; self.pic = None

    def update(self, g, held):
        import history_book as H
        snd = getattr(g, 'snd', None)
        if self.gen is None:
            if snd is not None: snd.bank = 37               # the sound bank the boot program loaded (0x801EFE20)
            self.gen = H.book_main(self.b)
        self.b.held = held
        try:
            next(self.gen)
            self.pic = self.b.gpu.picture()
        except StopIteration as e:
            self.done = True; self.result = e.value

    def draw(self, g, surf):
        if self.pic is not None: surf.blit(self.pic, (0, 0))
        else: surf.fill((0, 0, 0))


class Credits(Scene):
    """CLOSING.EXE (0x80022038): ENDING.XA plays; credit pages rise on the right (0x80021780) while
    portraits fade in and out on the left (0x80021CE4 / 0x800216CC), then THE END stays."""
    TABLE = [0, -0x30, 0x50, 0x48, 0x40, 0x38, 0x30, 0x28, 0x20, 0x10, 0]          # 0x80020510

    def __init__(self, g):
        d = ASSETS / 'ending'
        meta = json.loads((d / 'credits.json').read_text())
        self.pages = meta['pages']; self.pics = meta['pictures']
        self.glyphs = {int(k): v for k, v in meta['glyphs'].items()}
        self.font = load(d / 'font.png'); self.images = {}
        self.d = d
        # text state 0x801C4688
        self.timer = 0; self.page = 0; self.x = 0; self.y = 0; self.hold = 0; self.lines = 0
        self.height = 0; self.sub = 0; self.type = 0
        self.text = pygame.Surface((256, 240), pygame.SRCALPHA)
        # picture state 0x801B2D48
        self.active = 0; self.step = 0; self.bright = 0; self.layout = 0; self.next_pic = 0; self.pic = None
        self.end = 0; self.started = False

    def _image(self, name):
        if name not in self.images: self.images[name] = load(self.d / name)
        return self.images[name]

    def _next_picture(self):                                  # 0x800216CC
        if self.next_pic >= len(self.pics): return
        r = self.pics[self.next_pic]; self.next_pic += 1
        self.pic = self._image(r['image']); self.layout = r['layout']
        self.step = 2; self.bright = 0; self.active = 1

    def _render(self, rec):                                   # 0x8002134C for each line
        self.text.fill((0, 0, 0, 0))
        y = 0; n = 0
        for ln in rec['lines'][:10]:
            if ln['style'] == 0: x = 0; y += 0x18
            else: x = 0x18; y += 0x10
            for ch in ln['text'].encode('latin-1', 'replace'):
                gl = self.glyphs.get(ch & 0x7F)
                if gl is None: continue
                if x < 0x100: self.text.blit(self.font, (x, y + gl['y']), (gl['u'], gl['v'], gl['w'], gl['h']))
                x += gl['w'] + 1
            n += 1
        return y, n

    def _text_frame(self):                                    # 0x80021780
        if self.timer == 0:
            rec = self.pages[self.page] if self.page < len(self.pages) else {'type': 0}
            if rec['type'] != 0:
                self.timer = 0x200
                s1, n = self._render(rec)
                self.x = 0x64 if self.page == 0 else 0x90
                self.y = 0xF0; self.height = s1 + 0x10; self.lines = n; self.sub = 0
                self.hold = rec['hold']; self.page += 1; self.type = rec['type']
            elif self.sub != 4:
                self.sub = 4; self.timer = 0xB4
            return
        self.timer -= 1
        if self.sub == 0:
            self.y -= 1
            if self.y == 0xE0 and self.type in (1, 3): self._next_picture()
            if self.y == self.TABLE[self.lines]:
                self.sub += 1
                self.timer = 0xAA if self.hold else 0
        elif self.sub == 1:
            if self.timer == 0:
                self.sub += 1; self.timer = self.height + self.TABLE[self.lines] + 0x24
        elif self.sub == 2:
            self.y -= 1
            if self.timer == 0x50 and self.type in (2, 3): self.step = -2
        elif self.sub == 3:
            if self.timer == 0: self._next_picture()
        elif self.sub == 4:
            if self.timer == 0: self._next_picture(); self.end = 1

    def _picture_frame(self):                                 # 0x80021CE4 (the brightness part)
        if not self.active: return
        if self.step > 0:
            self.bright += self.step
            if self.bright == 0x80: self.step = 0
        elif self.step < 0:
            self.bright += self.step
            if self.bright == 0: self.active = 0

    def update(self, g, held):
        if not self.started:
            self.started = True
            g.snd.music_stop(False); g.snd.stop_all()
            try:
                pygame.mixer.music.load(str(ASSETS / 'audio' / 'xa' / 'ENDING_ch00.ogg')); pygame.mixer.music.play(0)
                pygame.mixer.music.set_volume(g.settings.get('music_volume', 100) / 100 * OUTPUT)
            except pygame.error: pass
        self._picture_frame()
        self._text_frame()

    # layouts of 0x80021CE4: screen x0, x1, y0, y1 and texture u0, u1, v0, v1
    LAYOUT = {0: (0xC, 0x7C, 0x10, 0xF0, 0, 0x7F, 0, 0xF0), 1: (0xC, 0x7C, 0x10, 0xF0, 0x80, 0xFF, 0, 0xF0),
              2: (8, 0x8A, 0x10, 0xF0, 0, 0x8D, 0, 0xF0), 3: (0xC, 0x6E, 0x10, 0xF0, 0x8E, 0xFF, 0, 0xF0),
              4: (0xC, 0x5C, 0x10, 0xF0, 0, 0x5F, 0, 0xF0), 5: (8, 0x9C, 0x10, 0xF0, 0x60, 0xFF, 0, 0xF0),
              6: (0x20, 0x120, 8, 0xE8, 0, 0xFF, 0, 0xF0)}

    def draw(self, g, surf):
        surf.fill((0, 0, 0))
        if self.page:                                         # 0x80021B18: the page, 176 x 240 at (x, y)
            surf.blit(self.text, (self.x, self.y), (0, 0, 0xB0, 0xF0))
        if self.active and self.pic is not None:              # the portrait (drawn over the text)
            x0, x1, y0, y1, u0, u1, v0, v1 = self.LAYOUT.get(self.layout, self.LAYOUT[0])
            src = self.pic.subsurface((u0, v0, min(self.pic.get_width(), u1 + 1) - u0, min(self.pic.get_height(), v1) - v0))
            img = pygame.transform.scale(src, (x1 - x0, y1 - y0))
            surf.blit(tint(img, self.bright), (x0, y0))


class SpeedrunList(Scene):
    """The remake's SPEEDRUN page: the starts in assets/speedrun (one continue record each,
    made from save states by tools/speedrun_states.py), on the options page's parchment with
    the game font and the menu's glove.  Left / Right: the JP (first) or US states; Up / Down
    pick (wrapping round), L1 / R1 a page up / down, Start or Cross go (result: the file), Circle or Triangle go back (None)."""
    VERSIONS = ('JP', 'US')
    PANEL = pygame.Rect(8, 8, 304, 224); ROW_Y, ROW_H = 36, 16

    def __init__(self, g):
        self.version = 0; self._load()
        self.prev = -1                                    # -1: buttons held on arrival count only once let go

    def _load(self):
        d = SPEEDRUN / self.VERSIONS[self.version].lower()
        self.files = sorted([*d.glob('*.bin'), *d.glob('*.State')], key=lambda p: p.name.lower()) if d.is_dir() else []   # (.State: BizHawk, bizhawk_state.py)
        self.sel = 0; self.top = 0

    def update(self, g, held):
        new = held & ~self.prev if self.prev != -1 else 0
        if self.prev == -1 and held: return
        self.prev = held
        if new & (LEFT | RIGHT):
            self.version ^= 1; self._load(); g.snd.play(1)
        n = len(self.files)
        if n and new & UP: self.sel = (self.sel - 1) % n; g.snd.play(1)      # (round from the first to the last)
        if n and new & DOWN: self.sel = (self.sel + 1) % n; g.snd.play(1)    # (and from the last to the first)
        page = (self.PANEL.bottom - 10 - self.ROW_Y) // self.ROW_H
        if n and new & L1 and self.sel > 0: self.sel = max(0, self.sel - page); g.snd.play(1)
        if n and new & R1 and self.sel < n - 1: self.sel = min(n - 1, self.sel + page); g.snd.play(1)
        if new & (START | CROSS) and n:
            g.snd.play(2); self.result = self.files[self.sel]; self.done = True
        elif new & (CIRCLE | TRIANGLE):
            g.snd.play(2); self.result = None; self.done = True

    def draw(self, g, surf):
        surf.fill((0, 0, 0))
        ss = getattr(g, 'settings_screen', None); gf = g.game_font; P = self.PANEL
        if ss is not None:
            surf.blit(ss.parchment(P.w, P.h), P.topleft); ss.glove_t += 1
        if not gf.ok: return
        head = f'Speedrun   < {self.VERSIONS[self.version]} >'; gf.draw(surf, head, P.centerx - gf.width(head) // 2, P.y + 8)
        if not self.files:
            for i, t in enumerate(('No speedrun starts yet.', 'Make them with', 'tools/speedrun_states.py')):
                gf.draw(surf, t.replace('starts yet', f'{self.VERSIONS[self.version]} starts yet'), P.x + 20, self.ROW_Y + 8 + i * self.ROW_H)
            return
        rows = (P.bottom - 10 - self.ROW_Y) // self.ROW_H
        self.top = max(min(self.top, self.sel), self.sel - rows + 1)
        for i in range(self.top, min(len(self.files), self.top + rows)):
            y = self.ROW_Y + (i - self.top) * self.ROW_H; name = self.files[i].stem
            while name and gf.width(name) > P.w - 60: name = name[:-1]
            gf.draw(surf, name, P.x + 20, y)
            if i == self.sel and ss is not None: ss.glove(surf, P.x + 24 + gf.width(name), y)


# ------------------------------------------------------------------------- flows --
class FrontEnd:
    """The scene sequence of a program.  'boot': SLUS_005.53's main loop; 'ending': the END.EXE
    load, its movie, the CLOSING.EXE load and the credits.  `action` is set when the game should
    take over: 'new_game', or 'continue' with `record` (the History Book's pick)."""
    def __init__(self, g, mode):
        self.g = g; self.mode = mode; self.action = None
        self.speedrun_route = None                            # 'us' / 'jp' when the record came from SPEEDRUN
        self.speedrun_name = None
        self.queue = []; self.scene = None
        if mode in ('boot', 'title'):                         # 'title': ALUN_CD.EXE LoadExecs SLUS_005.53
            self.movie = 0
            self.queue = [self._movie_step]
            if mode == 'title': self.queue.insert(0, lambda: Black(cd_frames(g, EXE_SIZES['SLUS_005.53'])))
        else:
            self.queue = [lambda: Black(cd_frames(g, EXE_SIZES['END.EXE'])),
                          lambda: Movie(g, 'ARAN_END', 0, 0x28, 0x19C5, START),
                          lambda: Black(cd_frames(g, EXE_SIZES['CLOSING.EXE'])),
                          lambda: Credits(g)]
        self._next()

    def _movie_step(self):
        name, x, y, end = (('USA_OP', 0, 0x28, 0xA4C), ('ARAN_OP', 8, 0x10, 0xEAB))[self.movie]
        if name == 'USA_OP' and self.g.settings.get('intro') == 'jp':   # Options > Intro Movie: JP
            name, x, y, end = 'ARAN_OP', 8, 0x10, 0xEAB                 # the title screen's wait movie instead
        self.movie ^= 1
        self.queue.insert(0, self._title_step)
        return Movie(self.g, name, x, y, end, START | CROSS)

    def _title_step(self):
        self.queue.insert(0, self._title_done)
        return Sequence([Black(2), Title(self.g)])           # 0x8002536C: two blank frames first

    def _title_done(self):
        r = self.last.result if self.last is not None else -1
        if r == 0:                                            # START: Now Loading while ALUN_CD loads
            self.queue = [lambda: Picture(TitleArt.get().loading_for(self.g),
                                          max(NOW_LOADING_MIN, cd_frames(self.g, EXE_SIZES['ALUN_CD.EXE'] + 200_000))), self._start_game]
            return Black(0)
        if r == 1:                                            # CONTINUE: the History Book
            self.queue.insert(0, self._book_done)
            return HistoryBook(self.g, self._book_machine())
        if r == 2:                                            # SPEEDRUN (the remake's): a start to pick
            self.queue.insert(0, self._speedrun_done)
            return SpeedrunList(self.g)
        self.g.snd.music_unload()                             # -1: 0x800287D0, on to the next movie
        self.queue.insert(0, self._movie_step)
        return Black(0)

    def _book_machine(self):
        """The boot program's state: set up once, at boot (0x8002536C: the room, the texts, the
        actors), before the first title."""
        if getattr(self, 'book', None) is None:
            import history_book as H
            from alundra_remake import card_slots
            self.book = H.Book(self.g, card_slots(self.g.settings)); H.boot(self.book)
        return self.book

    def _book_done(self):
        k = self.last.result if self.last is not None else -1
        if k is not None and k >= 0:                          # a record: it goes to ALUN_CD.EXE at
            import history_book as H                          # 0x80010000 ([0] = 1, [1] = k), Now Loading
            rec = bytearray(H.record(self.book, k))
            rec[0:4] = (1).to_bytes(4, 'little'); rec[4:8] = k.to_bytes(4, 'little')
            self.record = bytes(rec)
            self.queue = [lambda: Picture(TitleArt.get().loading_for(self.g),
                                          max(NOW_LOADING_MIN, cd_frames(self.g, EXE_SIZES['ALUN_CD.EXE'] + 200_000))), self._continue_game]
            return Black(0)
        self.queue.insert(0, self._title_done)                # -1: the title again
        return Title(self.g)

    def _speedrun_done(self):
        path = self.last.result if self.last is not None else None
        if path is not None:                                  # its record goes in as a continue does
            if path.suffix.lower() == '.state':                # a BizHawk savestate: read its RAM
                import bizhawk_state
                try: self.record = bizhawk_state.record(path)[1]
                except Exception: self.queue.insert(0, self._title_done); return Title(self.g)
            else: self.record = path.read_bytes()
            self.speedrun_route = path.parent.name            # (the game shows its Speedrun tab: speedrun.py)
            self.speedrun_name = path.name
            self.queue = [lambda: Picture(TitleArt.get().loading_for(self.g),
                                          max(NOW_LOADING_MIN, cd_frames(self.g, EXE_SIZES['ALUN_CD.EXE'] + 200_000))), self._continue_game]
            return Black(0)
        self.queue.insert(0, self._title_done)                # back: the title again
        return Title(self.g)

    def _continue_game(self):
        self.action = 'continue'
        return Black(0)

    def _start_game(self):
        self.action = 'new_game'
        return Black(0)

    def _next(self):
        self.last = self.scene
        while self.queue:
            self.scene = self.queue.pop(0)()
            if not self.scene.done: return
            self.last = self.scene
        self.scene = None

    def update(self, held):
        if self.scene is None or self.action: return
        self.scene.update(self.g, held)
        if self.scene.done: self._next()

    def draw(self, surf):
        if self.scene is not None: self.scene.draw(self.g, surf)
        else: surf.fill((0, 0, 0))


class Sequence(Scene):
    """Scenes one after another; its result is the last one's."""
    def __init__(self, scenes):
        self.scenes = [s for s in scenes if not s.done]; self.result = None
        if not self.scenes: self.done = True

    def update(self, g, held):
        s = self.scenes[0]
        s.update(g, held)
        if s.done:
            self.result = s.result; self.scenes.pop(0)
            if not self.scenes: self.done = True

    def draw(self, g, surf):
        if self.scenes: self.scenes[0].draw(g, surf)
