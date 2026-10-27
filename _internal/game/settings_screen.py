"""The remake's settings page (F5, or Select), drawn like the game's own
windows: the message parchment (layout 0x8009EE28, stretched), name-plate tabs (0x800A7728),
the game font, the menu's pointing glove (WIND u 176.., v 160, its 40-frame bob from
0x800AA130 / 0x800AA140) and the menu sounds (1 move, 2 confirm, 3 refuse, 4 open, 5 close).
Three tabs:
  Controls  every pad action with its keyboard keys and controller inputs: pick a cell and
            press Enter / A to bind (Esc cancels the capture), Insert adds a second input,
            Delete / Backspace clears; an input used by two actions is marked with '!'.  Confirm
            button: US & EU (menus confirm with Cross) or JP (Square, as dialogue already does).
  Options   music / sound volume, window size, fullscreen, vsync, filter, scanlines, brightness compensation, balance,
            dialogue & font.
  Speedrun  (only in a game started from the title's SPEEDRUN page) save / load states: route (US or JP: also sets
            Balance and Dialogue & font), slot, the Save / Load state inputs (keys and pad, used
            in game) and the route's speedrun starts as presets (speedrun.py).
  Mods      changes to how the game plays: text speed (Normal, 1.5x, 2x), instant text,
            Rare Item Jingle (Original, PS2 FDS, Regular Item), Loading pauses (Original, PS2 FDS,
            Instant, Custom with its own Load delay in frames), L / R swapping (L1 / R1 weapons,
            L2 / R2 items: lr_swap.py), Magic & weapon swapping (Circle in the menu: scroll <-> book,
            the weapons of a group; L1 / R1 every weapon), Fixed casino RNG
            (the roulette lands Red, Blue, Green, ... from entering the room; off by default).
Opened with F5 or Select (whatever it is bound to, keys or controller).
Navigation: arrows / d-pad / stick (held keys repeat), Tab or Q/E or LB/RB switch tabs,
Enter or A to change, Esc, Triangle or Circle (as bound on the pad) or Start to save and close; the mouse works too (hover,
click, wheel).  Options are saved to settings.json, bindings to controls.json."""
import json
from pathlib import Path
import pygame
from controls import ACTIONS, BIT, Controls, key_code
import video_filter as VF
import speedrun as SR

from home import HOME
FILE = HOME / 'settings.json'
DEFAULTS = {'music_volume': 100, 'sfx_volume': 100, 'scale': 3, 'fullscreen': False, 'integer_scale': False,
            'text_speed': 1, 'swap_lr': False, 'magic_swap': False, 'load_pauses': 1, 'load_delay': 30, 'vsync': True, 'instant_text': False,
            'rare_jingle': 1, 'floor_clip': 0, 'shadow_clip': 0, 'feet_clip': 0, 'balance': 'us', 'text_lang': 'us', 'intro': 'us',
            'filter': 'sharp', 'scanlines': 0, 'brightness': 0, 'casino_fixed_rng': False, 'confirm': 'us', 'sprite_set': 'new',
            'display_lag': 'pc', 'level_top_fix': False, 'sr_route': 'us', 'sr_slot': 1, 'sr_binds': SR.DEFAULT_BINDS, 'sr_preset': ''}
TABS = ('Controls', 'Options', 'Mods', 'Speedrun')        # Speedrun: only in a SPEEDRUN start's game
MOD_KEYS = ('text_speed', 'instant_text', 'rare_jingle', 'swap_lr', 'magic_swap', 'load_pauses', 'load_delay', 'display_lag',
            'shadow_clip', 'feet_clip', 'casino_fixed_rng')
# Options > Dialogue & font: US, JP (assets/text_jp) and the European discs (assets/text_<lang> and
# assets/ui/<lang>, tools/remake_export_eu.py); only the exported ones are offered.
TEXT_LANGS = {'us': 'English', 'jp': 'Japanese', 'fr': 'French', 'de': 'German', 'it': 'Italian', 'es': 'Spanish'}


def text_lang_ready(lang):
    if lang == 'us': return True
    a = HOME / 'assets'
    if lang == 'jp': return (a / 'text_jp' / 'maps.json').exists()
    return (a / f'text_{lang}' / 'ETC.R').exists() and (a / 'ui' / lang / 'chars.bin').exists()


SR_KEYS = ('sr_route', 'sr_slot', 'sr_binds', 'sr_preset')
CONTROL_KEYS = ('confirm',)                # (reset with the controls, not the options)
# Mods > Shadow clipping / Character clipping (hidden rows, shown by Ctrl+Shift+0):
# CLIP_NEVER (the default) = the remake's own pass that lays shadows / sprites' feet again over
# the floor tiles of later rows; CLIP_ORIGINAL = the game's ordering table (that floor covers them)
CLIP_NEVER, CLIP_ORIGINAL = 0, 1
LOAD_ORIGINAL, LOAD_INSTANT, LOAD_CUSTOM, LOAD_FDS = 1, 0, 2, 3   # Mods > Loading pauses
FDS_READ = 0.43         # PS2 FDS: share of the original's CD read time left (docs/2026-10-22-ps2-fds-loads-and-jingle.txt)
FDS_MUSIC = 0.0         # PS2 FDS: new music's read; its fade wait is skipped too (docs/2026-10-22-ps2-fds-music-and-magic.txt)
AUDIO_REV = 2           # 2: music and sound rendered at the game's levels (100% = the console)
TEXT_SPEEDS = [1, 2, 3]             # 1 = the game's (a letter every 4 frames), 2 = 1.5x, 3 = 2x
EXTRA_PRINTS = {1: 0.0, 2: 0.5, 3: 1.0}     # extra printing steps per frame for each speed


def load_settings():
    s = dict(DEFAULTS)
    try:
        d = json.loads(FILE.read_text())
        if isinstance(d.get('load_pauses'), bool):    # older settings: on (Original) / off (Instant)
            d['load_pauses'] = LOAD_ORIGINAL if d['load_pauses'] else LOAD_INSTANT
        for k, v in d.items():
            if k in s and type(v) is type(s[k]): s[k] = v
        if s['balance'] not in ('us', 'jp'): s['balance'] = 'us'
        if s['text_lang'] not in TEXT_LANGS: s['text_lang'] = 'us'
        if s['intro'] not in ('us', 'jp'): s['intro'] = 'us'
        if s['confirm'] not in ('us', 'jp'): s['confirm'] = 'us'
        if s['sprite_set'] not in ('new', 'old'): s['sprite_set'] = 'new'
        if s['display_lag'] == 'ps1': s['display_lag'] = 'bizhawk'   # (its first name)
        if s['display_lag'] not in ('pc', 'ossc', 'bizhawk'): s['display_lag'] = 'pc'
        if d.get('audio_rev', 0) < AUDIO_REV:          # older settings: the game's own levels again
            s['music_volume'] = s['sfx_volume'] = 100
    except (OSError, ValueError):
        pass
    s['scale'] = max(1, min(6, s['scale']))
    s['music_volume'] = max(0, min(100, s['music_volume'])); s['sfx_volume'] = max(0, min(100, s['sfx_volume']))
    if s['text_speed'] == 0:                           # older settings: Instant was a text speed
        s['text_speed'] = 1; s['instant_text'] = True
    if s['text_speed'] not in TEXT_SPEEDS: s['text_speed'] = 1
    if s['rare_jingle'] == 2: s['rare_jingle'] = 4                # (2x was removed: PS2 FDS, the nearest)
    if s['rare_jingle'] not in (1, 3, 4): s['rare_jingle'] = 1
    s['floor_clip'] = 0                                    # floor clipping: always Less (no longer an option)
    for k in ('shadow_clip', 'feet_clip'):
        if s[k] not in (CLIP_NEVER, CLIP_ORIGINAL): s[k] = CLIP_NEVER
    s['filter'] = VF.norm_filter(s['filter'])               # (Crisp was removed: Sharp)
    if s['scanlines'] not in VF.SCANLINES: s['scanlines'] = 0
    if s['brightness'] not in VF.BRIGHTNESS: s['brightness'] = 0
    if s['load_pauses'] not in (LOAD_ORIGINAL, LOAD_INSTANT, LOAD_CUSTOM, LOAD_FDS): s['load_pauses'] = LOAD_ORIGINAL
    s['load_delay'] = max(0, min(600, s['load_delay']))
    s['sr_preset'] = ''                                # (not kept between runs: speedrun.LAST remembers the last load)
    if s['sr_route'] not in SR.ROUTES: s['sr_route'] = 'us'
    s['sr_slot'] = max(1, min(10, s['sr_slot'])); s['sr_binds'] = SR.norm_binds(s['sr_binds'])
    return s


def load_pause(settings, original, read=0, fds=None):
    """Frames of black while the disc is read: the original's estimate, none (Instant), the
    player's own number (Custom) or a PS2 with Fast Disc Speed (PS2 FDS: of the original, the
    `read` frames that are the CD's seek and transfer shrink to FDS_READ, or `fds`, of themselves)."""
    mode = settings.get('load_pauses', LOAD_ORIGINAL)
    if mode is True: mode = LOAD_ORIGINAL
    elif mode is False: mode = LOAD_INSTANT
    if mode == LOAD_INSTANT: return 0
    if mode == LOAD_CUSTOM: return max(0, int(settings.get('load_delay', 30)))
    if mode == LOAD_FDS: return max(0, original - read + round(read * (FDS_READ if fds is None else fds)))
    return original


def save_settings(s):
    s = {k: v for k, v in s.items() if k != 'sr_preset'}   # the preset picked is remembered only while the remake runs
    try: FILE.write_text(json.dumps(dict(s, audio_rev=AUDIO_REV), indent=1))
    except OSError: pass


def key_label(name):
    """pygame key names as people write them."""
    n = {'return': 'Enter', 'escape': 'Esc', 'backspace': 'Backspace', 'tab': 'Tab', 'space': 'Space',
         'left shift': 'Left Shift', 'right shift': 'Right Shift', 'left ctrl': 'Left Ctrl', 'right ctrl': 'Right Ctrl',
         'up': 'Up', 'down': 'Down', 'left': 'Left', 'right': 'Right'}.get(name)
    return n or (name.upper() if len(name) == 1 else name.title())


VW, VH = 320, 240
PANEL = pygame.Rect(8, 40, 304, 160)          # the parchment the rows sit on
FOOT = pygame.Rect(8, 204, 304, 32)           # the strip with help / messages
ROW_H, ROW_Y = 16, 54
SPEED_NAME = {1: 'Normal', 2: '1.5x', 3: '2x'}
SR_BIND = {'sr:save': 'Save state button', 'sr:load': 'Load state button'}
SHORT = {'jump': 'Jump', 'attack': 'Attack / Talk', 'item': 'Item', 'dash': 'Dash', 'menu': 'Menu Shortcut'}


class SettingsScreen:
    def __init__(self, game):
        self.g = game; self.c = game.controls
        self.open = False; self.tab = 0; self.row = 0; self.col = 0
        self.capture = None             # (action, 'key' | 'pad', add) while waiting for an input
        self.msg = ''; self.msg_t = 0; self.scroll = 0
        self.hover = None; self._rects = []; self.display_at = None
        self.stick_dir = (0, 0); self.stick_t = 0
        self.canvas = pygame.Surface((VW, VH)); self.glove_t = 0; self._parch = {}; self.ignore = set()
        self.clip_rows = False          # hidden rows shown (Ctrl+Shift+0): Mods > Shadow / Character clipping,
                                        # Options > Sprite Graphics (New / Old, kept in settings.json either way),
                                        # Options > Level Top Fix (physics.py collide_down; On by default)

    def show_clip_mods(self):
        """Ctrl+Shift+0: the page opens on Mods with the Shadow clipping and Character clipping
        rows (Never = the remake's pass over the floor, the default; Original = the game)."""
        self.clip_rows = True
        if not self.open: self.show()
        self.tab = 2; self.col = 0; self.scroll = 0; self.hover = None
        self._rects = [r for r in self._rects if r[1][0] == 'tab']
        rows = self.rows()
        self.row = next((i for i, r in enumerate(rows) if r[1] == 'shadow_clip'), 0)

    def tabs(self): return TABS if SR.active() else TABS[:3]

    def bind_list(self, action, key_col):
        """The inputs of an action: a pad action's (controls.json) or a speedrun one's (settings)."""
        if action.startswith('sr:'):
            return self.g.settings['sr_binds'][action[3:]].setdefault('k' if key_col else 'p', [])
        return (self.c.keys if key_col else self.c.pad).setdefault(action, [])

    def set_binds(self, action, key_col, lst):
        if action.startswith('sr:'): self.g.settings['sr_binds'][action[3:]]['k' if key_col else 'p'] = lst
        else: (self.c.keys if key_col else self.c.pad)[action] = lst

    def sound(self, n):
        snd = getattr(self.g, 'sound', None)
        if snd is not None: snd(n)

    # ---------------------------------------------------------------- open / close
    def show(self):
        self.open = True; self.capture = None; self.msg = ''
        keys = pygame.key.get_pressed()                 # keys held while opening (Select + Start on
        codes = (key_code(n) for a in self.c.keys for n in self.c.keys[a])   # the keyboard) act once released
        self.ignore = {c for c in codes if c is not None and keys[c]}
        pygame.key.set_repeat(260, 55); self.sound(4)

    def close(self):
        if self.display_at is not None: self.display_at = None
        self.c.save(); save_settings(self.g.settings); self.g.apply_settings()
        self.open = False; self.capture = None
        pygame.key.set_repeat(); self.sound(5)
        self.g.pad_held |= self.c.held(pygame.key.get_pressed()) & 0xFFFF   # buttons still down are no fresh press

    # ---------------------------------------------------------------- rows
    def rows(self):
        if self.tab == 3:
            rows = [('choice', 'sr_route', 'Route'), ('int', 'sr_slot', 'Slot'),
                    ('do', 'load', 'Load State'), ('do', 'save', 'Save State'),
                    ('bind', 'sr:load', 'Load Button'), ('bind', 'sr:save', 'Save Button')]
            if SR.presets(self.g.settings['sr_route']):
                rows += [('do', 'preset', 'Load Preset'), ('choice', 'sr_preset', 'Preset')]
            return rows
        if self.tab == 0:
            return [('bind', a, SHORT.get(a, label)) for a, label, _ in ACTIONS] + \
                   [('choice', 'confirm', 'Confirm Button'), ('reset_keys', None, 'Reset Controls')]
        return [('int', 'music_volume', 'Music Volume'),
                ('int', 'sfx_volume', 'Sound Volume'),
                ('int', 'scale', 'Window Size'),
                ('toggle', 'fullscreen', 'Fullscreen'),
                ('toggle', 'integer_scale', 'Integer Scaling'),
                ('toggle', 'vsync', 'VSync'),
                ('choice', 'filter', 'Filter'),
                ('choice', 'scanlines', 'Scanlines'),
            ] + ([('choice', 'brightness', 'Brightness Comp.')] if VF.masks_on(self.g.settings) else []) + [
                ('choice', 'balance', 'Balance'),
                ('choice', 'text_lang', 'Language'),
                ('choice', 'intro', 'Intro Movie'),
            ] + ([('choice', 'sprite_set', 'Sprite Graphics'),
                  ('toggle', 'level_top_fix', 'Level Top Fix')] if self.clip_rows else []) + [   # hidden: Ctrl+Shift+0
                ('reset_opts', None, 'Reset Options')] if self.tab == 1 else \
               [('choice', 'text_speed', 'Text Speed'),          # text
                ('toggle', 'instant_text', 'Instant Text'),
                ('choice', 'rare_jingle', 'Rare Item Jingle'),     # sound
                ('choice', 'load_pauses', 'Loading Pauses'),     # map changes
            ] + ([('int', 'load_delay', 'Load Delay')] if self.g.settings.get('load_pauses') == LOAD_CUSTOM else []) + [
                ('choice', 'display_lag', 'Delay'),              # PC & HW: the picture at once; Hardware +1: 1 frame later; BizHawk: 3 frames later
                ('toggle', 'swap_lr', 'L / R Swapping'),
                ('toggle', 'magic_swap', 'Magic & Weapon Swap'),
                ('toggle', 'casino_fixed_rng', 'Fixed Casino RNG'),   # roulette: Red, Blue, Green...
            ] + ([('choice', 'shadow_clip', 'Shadow Clipping'),      # hidden: Ctrl+Shift+0
                  ('choice', 'feet_clip', 'Character Clipping')] if self.clip_rows else []) + [
                ('reset_opts', None, 'Reset Mods')]

    LIMITS = {'music_volume': (0, 100, 5), 'sfx_volume': (0, 100, 5), 'scale': (1, 6, 1), 'load_delay': (0, 600, 1),
              'sr_slot': (1, 10, 1)}
    CHOICES = {'text_speed': TEXT_SPEEDS, 'rare_jingle': [1, 4, 3],     # Original, PS2 FDS, Regular Item
               'load_pauses': [LOAD_ORIGINAL, LOAD_FDS, LOAD_INSTANT, LOAD_CUSTOM], 'filter': VF.FILTERS, 'scanlines': VF.SCANLINES,
               'brightness': VF.BRIGHTNESS, 'shadow_clip': [CLIP_NEVER, CLIP_ORIGINAL], 'feet_clip': [CLIP_NEVER, CLIP_ORIGINAL],
               'balance': ['us', 'jp'], 'text_lang': list(TEXT_LANGS), 'intro': ['us', 'jp'], 'sr_route': list(SR.ROUTES), 'confirm': ['us', 'jp'], 'sprite_set': ['new', 'old'], 'display_lag': ['pc', 'ossc', 'bizhawk']}

    def choices(self, key):
        if key == 'sr_preset': return SR.presets(self.g.settings['sr_route']) or ['']
        if key == 'text_lang': return [l for l in TEXT_LANGS if text_lang_ready(l)]
        return self.CHOICES[key]

    def preset_sel(self):
        """The Preset row's file: the one picked here, else the route's last loaded (speedrun.LAST),
        else the first."""
        s = self.g.settings; ch = self.choices('sr_preset')
        v = s.get('sr_preset') or SR.LAST.get(s['sr_route'], '')
        return v if v in ch else ch[0]

    def value_text(self, key):
        s = self.g.settings; v = s[key]
        if key in ('fullscreen', 'integer_scale', 'swap_lr', 'magic_swap', 'vsync', 'instant_text', 'casino_fixed_rng', 'level_top_fix'): return 'On' if v else 'Off'
        if key == 'sprite_set': return {'new': 'New', 'old': 'Old'}.get(v, str(v))
        if key == 'confirm': return {'us': 'US & EU (Cross)', 'jp': 'JP (Square)'}.get(v, str(v))
        if key == 'sr_route': return v.upper()
        if key == 'sr_slot': return str(v)
        if key == 'sr_preset': return SR.pretty(self.preset_sel())
        if key == 'load_pauses': return {LOAD_ORIGINAL: 'Original', LOAD_INSTANT: 'Instant', LOAD_CUSTOM: 'Custom', LOAD_FDS: 'PS2 FDS'}.get(v, str(v))
        if key == 'load_delay': return f'{v} frames'
        if key == 'text_speed': return SPEED_NAME.get(v, str(v))
        if key == 'filter': return VF.FILTER_NAME.get(v, str(v))
        if key == 'scanlines': return VF.SCANLINE_NAME.get(v, str(v))
        if key == 'brightness': return VF.BRIGHTNESS_NAME.get(v, str(v))
        if key == 'balance': return {'us': 'US & EU', 'jp': 'JP'}.get(v, str(v))
        if key == 'intro': return {'us': 'US', 'jp': 'JP'}.get(v, str(v))
        if key == 'text_lang': return TEXT_LANGS.get(v, str(v))
        if key == 'rare_jingle': return {1: 'Original', 3: 'Regular Item', 4: 'PS2 FDS'}.get(v, str(v))
        if key == 'display_lag': return {'pc': 'PC & HW', 'ossc': 'Hardware +1', 'bizhawk': 'BizHawk +3'}.get(v, str(v))
        if key in ('shadow_clip', 'feet_clip'): return {CLIP_ORIGINAL: 'Original', CLIP_NEVER: 'Never'}.get(v, str(v))
        if key in ('music_volume', 'sfx_volume'): return f'{v}%'
        if key == 'scale': return f'x{v}'
        return str(v)

    def conflicts(self):
        """Keys / inputs bound to more than one action."""
        seen = {}; bad = set()
        for kind, table in (('k', self.c.keys), ('p', self.c.pad)):
            for a, toks in table.items():
                for t in toks:
                    o = seen.get((kind, t))
                    if o is not None and o != a and {o, a} != {'menu', 'select'}:   # (the menu shortcut may share
                        bad.add((a, kind)); bad.add((o, kind))                      # the game's Select button)
                    seen[(kind, t)] = a
        return bad

    # ---------------------------------------------------------------- input
    def say(self, text): self.msg = text; self.msg_t = pygame.time.get_ticks()

    def move(self, dy=0, dx=0):
        rows = self.rows()
        if dy:
            self.row = (self.row + dy) % len(rows); self.sound(1)
        if dx:
            kind, key, _ = rows[self.row]
            s = self.g.settings
            if kind == 'bind': self.col ^= 1; self.sound(1)
            elif kind == 'int':
                lo, hi, st = self.LIMITS[key]; old = s[key]
                if key == 'load_delay':                 # frame by frame near 0, faster further up
                    v = s[key] + (dx if dx < 0 else 0)
                    st = 1 if v < 60 else 5 if v < 300 else 10
                s[key] = max(lo, min(hi, s[key] + dx * st)); self.live(key)
                self.sound(1 if s[key] != old else 3)
            elif kind == 'choice':
                if key == 'sr_preset': s[key] = self.preset_sel()
                ch = self.choices(key); i = ch.index(s[key]) if s[key] in ch else 0
                s[key] = ch[(i + dx) % len(ch)]; self.sound(1)
                if key == 'sr_route':                    # a route plays by its own version's rules
                    s['balance'] = s['text_lang'] = s[key]; s['sr_preset'] = SR.LAST.get(s[key], ''); self.say(f'Balance & text: {s[key].upper()}')
                if key in ('load_pauses', 'sr_route'): self._rects = [r for r in self._rects if r[1][0] == 'tab']
            elif kind == 'toggle':
                s[key] = not s[key]; self.live(key); self.sound(1)

    def live(self, key):
        """Options that show their effect at once."""
        if key in ('music_volume', 'sfx_volume'): self.g.apply_volume()
        if key in ('scale', 'fullscreen', 'vsync'):     # the window changes at once (after a short pause,
            self.display_at = pygame.time.get_ticks() + 200   # so holding a direction does not remake it each step)

    def apply_display(self):
        self.display_at = None
        try: self.g.set_display()
        except pygame.error as e: self.say(f'Window: {e}'[:40]); return
        pygame.key.set_repeat(260, 55)                  # (a new window loses the menu's key repeat)
        self.hover = None

    def switch_tab(self, d):
        self.tab = (self.tab + d) % len(self.tabs()); self.row = 0; self.col = 0; self.capture = None; self.scroll = 0
        self._rects = [r for r in self._rects if r[1][0] == 'tab']; self.hover = None   # the old tab's rows are gone
        self.sound(1)

    def activate(self):
        rows = self.rows(); self.row = min(self.row, len(rows) - 1)
        kind, key, _ = rows[self.row]
        if kind == 'bind': self.start_capture(key, add=False); self.sound(2)
        elif kind == 'toggle':
            self.g.settings[key] = not self.g.settings[key]; self.live(key); self.sound(2)
        elif kind == 'do': self.speedrun_do(key)
        elif kind in ('int', 'choice'): self.move(dx=1)
        elif kind == 'reset_keys':
            self.c.reset(); self.g.settings['confirm'] = DEFAULTS['confirm']; self.say('Controls reset'); self.sound(2)
        elif kind == 'reset_opts':
            s = self.g.settings; sc = s['scale']
            keys = MOD_KEYS if self.tab == 2 else [k for k in DEFAULTS if k not in MOD_KEYS + SR_KEYS + CONTROL_KEYS]
            for k in keys: s[k] = DEFAULTS[k]
            self.g.apply_volume(); self.sound(2)
            if self.tab == 2: self.say('Mods reset')
            else:
                self.say('Options reset')
                self.live('scale')

    def speedrun_do(self, what):
        s = self.g.settings; route, slot = s['sr_route'], s['sr_slot']
        if what == 'save':
            err = SR.save_state(self.g, SR.slot_path(route, slot))
            self.say(err or SR.message('save', route, slot)); self.sound(3 if err else 2); return
        if what == 'load': path, name = SR.slot_path(route, slot), f'Slot {slot}'
        else:
            p = self.preset_sel(); path, name = SR.preset_path(route, p), SR.pretty(p)
            SR.LAST[route] = p                                 # the Preset row opens on it next time (this run only)
        if not (SR.has_state(path) if what == 'load' else path.is_file()): self.say('No state there'); self.sound(3); return
        self.close()
        err = SR.load_state(self.g, path)
        self.g.toast(err or (SR.message('load', route, slot) if what == 'load' else f'Loaded {name}'), game=True)

    def start_capture(self, action, add):
        self.capture = (action, 'key' if self.col == 0 else 'pad', add)
        self.say('Press a key (Esc cancels)' if self.col == 0 else 'Press a button or stick (Esc cancels)')

    def clear(self):
        kind, key, _ = self.rows()[self.row]
        if kind != 'bind': self.sound(3); return
        if key == 'menu' and self.col == 0 and len(self.c.keys.get('menu', [])) <= 1:
            self.say('Menu shortcut keeps one key'); self.sound(3); return
        self.set_binds(key, self.col == 0, []); self.say('Cleared'); self.sound(5)

    def to_canvas(self, pos):
        r = self.g.view_rect()
        if not r.collidepoint(pos): return None
        return ((pos[0] - r.x) * VW // r.w, (pos[1] - r.y) * VH // r.h)

    def handle(self, e):
        """Takes every event while the page is open."""
        if not self.open: return False
        self.row = max(0, min(self.row, len(self.rows()) - 1))   # rows come and go (Load delay)
        if e.type == pygame.KEYUP: self.ignore.discard(e.key)
        if e.type == pygame.KEYDOWN and e.key in self.ignore: return True
        if self.capture is not None:
            action, kind, add = self.capture
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: self.capture = None; self.say('Cancelled'); self.sound(3); return True
                if kind == 'key':
                    name = pygame.key.name(e.key)
                    lst = self.bind_list(action, True)
                    self.set_binds(action, True, lst + [name] if add and name not in lst else [name])
                    self.capture = None; self.say(', '.join(key_label(t) for t in self.bind_list(action, True))); self.sound(2)
                return True
            if kind == 'pad':
                tok = Controls.token_from_event(e)
                if tok:
                    lst = self.bind_list(action, False)
                    self.set_binds(action, False, lst + [tok] if add and tok not in lst else [tok])
                    self.capture = None; self.say(', '.join(Controls.describe(t) for t in self.bind_list(action, False))); self.sound(2)
            return True
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_0, pygame.K_KP0) and e.mod & pygame.KMOD_CTRL and e.mod & pygame.KMOD_SHIFT:
                self.show_clip_mods(); self.sound(1)
            elif k == pygame.K_ESCAPE or k == pygame.K_F5 or pygame.key.name(k) in self.c.keys.get('dash', []): self.close()   # (Triangle's keys)
            elif k in (pygame.K_UP, pygame.K_w): self.move(dy=-1)
            elif k in (pygame.K_DOWN, pygame.K_s): self.move(dy=1)
            elif k in (pygame.K_LEFT, pygame.K_a): self.move(dx=-1)
            elif k in (pygame.K_RIGHT, pygame.K_d): self.move(dx=1)
            elif k == pygame.K_TAB: self.switch_tab(-1 if e.mod & pygame.KMOD_SHIFT else 1)
            elif k in (pygame.K_q, pygame.K_PAGEUP): self.switch_tab(-1)
            elif k in (pygame.K_e, pygame.K_PAGEDOWN): self.switch_tab(1)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_z): self.activate()
            elif k == pygame.K_INSERT and self.rows()[self.row][0] == 'bind':
                self.start_capture(self.rows()[self.row][1], add=True); self.sound(2)
            elif k in (pygame.K_DELETE, pygame.K_BACKSPACE): self.clear()
            elif pygame.key.name(k) in self.c.keys.get('item', []): self.close()   # Item's keys back out (after the page's own keys)
        elif e.type == pygame.JOYHATMOTION and e.value != (0, 0):
            x, y = e.value
            if y: self.move(dy=-y)
            elif x: self.move(dx=x)
        elif e.type == pygame.JOYAXISMOTION and e.axis in (0, 1):
            d = (1 if e.value > 0.6 else -1 if e.value < -0.6 else 0)
            v = (d, 0) if e.axis == 0 else (0, d)
            if d and v != self.stick_dir:
                self.stick_dir = v; self.stick_t = pygame.time.get_ticks() + 260
                self.move(dy=v[1]) if v[1] else self.move(dx=v[0])
            elif not d and ((e.axis == 0 and self.stick_dir[0]) or (e.axis == 1 and self.stick_dir[1])):
                self.stick_dir = (0, 0)
        elif e.type == pygame.JOYBUTTONDOWN:
            tok = f'button:{e.button}'
            if tok in self.c.pad.get('dash', []) or tok in self.c.pad.get('item', []): self.close()   # Triangle / Circle (as bound) back out
            elif e.button == 0: self.activate()
            elif e.button == 2: self.clear()
            elif e.button == 4: self.switch_tab(-1)
            elif e.button == 5: self.switch_tab(1)
            elif e.button == 7: self.close()
        elif e.type == pygame.MOUSEMOTION:
            pos = self.to_canvas(e.pos); self.hover = self.hit(pos) if pos else None
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button in (4, 5): self.move(dy=-1 if e.button == 4 else 1); return True
            pos = self.to_canvas(e.pos)
            h = self.hit(pos) if pos else None
            if h is None: return True
            if h[0] == 'tab':
                if h[1] != self.tab: self.switch_tab(h[1] - self.tab)
            elif h[0] == 'col':
                self.col ^= 1; self.sound(1)
            elif h[0] == 'row':
                if h[1] >= len(self.rows()): return True          # a row that has just gone (Load delay)
                if h[1] != self.row: self.row = h[1]; self.sound(1)
                if len(h) > 2 and h[2] != self.col: self.col = h[2]
                if e.button == 3: self.clear()
                else:
                    kind = self.rows()[self.row][0]
                    if kind in ('int', 'choice'): self.move(dx=-1 if (len(h) > 3 and h[3] < 0) else 1)
                    else: self.activate()
        elif e.type == pygame.MOUSEWHEEL:
            self.move(dy=-e.y)
        return True

    def tick(self):
        """Held stick repeats like held keys; a changed window size is applied."""
        if self.display_at is not None and pygame.time.get_ticks() >= self.display_at: self.apply_display()
        if self.stick_dir != (0, 0) and pygame.time.get_ticks() >= self.stick_t:
            self.stick_t = pygame.time.get_ticks() + 55
            self.move(dy=self.stick_dir[1]) if self.stick_dir[1] else self.move(dx=self.stick_dir[0])

    def hit(self, pos):
        for r, what in self._rects:
            if r.collidepoint(pos): return what
        return None

    # ---------------------------------------------------------------- the game's art
    def parchment(self, w, h):
        """The message scroll (288 x 56) stretched to w x h: its rolled ends and edges kept, the
        middle repeated."""
        k = (w, h)
        if k in self._parch: return self._parch[k]
        src = self.g.inventory_ui.window(0x8009EE24)
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        if src is None:
            out.fill((150, 150, 120)); self._parch[k] = out; return out
        SW, SH = src.get_size(); E = 16; MW, MH = SW - 2 * E, SH - 2 * E
        def cols():
            x = 0
            yield (0, 0, E)
            x = E
            while x < w - E:
                n = min(MW, w - E - x); yield (x, E, n); x += n
            yield (w - E, SW - E, E)
        rows = [(0, 0, E)]
        y = E
        while y < h - E:
            n = min(MH, h - E - y); rows.append((y, E, n)); y += n
        rows.append((h - E, SH - E, E))
        for dy, sy, hh in rows:
            for dx, sx, ww in cols():
                out.blit(src, (dx, dy), (sx, sy, ww, hh))
        self._parch[k] = out
        return out

    PLATE_END = 13          # the name plate's rolled ends (columns 0-12 and 99-111 of the 112 px art)

    def plate(self, dim, w=112, ends=False):
        """The tab name plate at width w. ends=True (four tabs) keeps the rolled ends at native size
        and scales only the light middle; otherwise the whole image is scaled."""
        k = ('plate', dim, w, ends)
        if k not in self._parch:
            src = self.g.inventory_ui.window(0x800A7724)
            s = src.copy() if src is not None else pygame.Surface((112, 32), pygame.SRCALPHA)
            if dim: s.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
            SW, SH = s.get_size(); E = self.PLATE_END
            if ends and w != SW and w > 2 * E:
                out = pygame.Surface((w, SH), pygame.SRCALPHA)
                out.blit(s, (0, 0), (0, 0, E, SH))
                out.blit(pygame.transform.scale(s.subsurface((E, 0, SW - 2 * E, SH)), (w - 2 * E, SH)), (E, 0))
                out.blit(s, (w - E, 0), (SW - E, 0, E, SH))
                s = out
            elif w != SW: s = pygame.transform.scale(s, (w, SH))
            self._parch[k] = s
        return self._parch[k]

    def tab_layout(self, tabs):
        """[(x, width)] of each tab plate. Three tabs: 112 px plates every 96 px. Four tabs: each plate
        sized to its name (native rolled ends + name + 4 px each side), overlapping only at the rolled
        ends so the whole row fits the 8..320 px span."""
        if len(tabs) <= 3: return [(8 + 96 * i, 112) for i in range(len(tabs))]
        gf = self.g.game_font; E = self.PLATE_END
        ws = [(gf.width(self.tr(n)) if gf.ok else 60) + 8 + 2 * E for n in tabs]
        ov = max(0, -(-(sum(ws) - (VW - 8)) // (len(ws) - 1)))   # ceil: the overlap between plates
        out = []; x = 8
        for w in ws: out.append((x, w)); x += w - ov
        return out

    def glove(self, v, x, y):
        """The menu's pointing glove at (x, y), bobbing like 0x80052070 / 0x800521D0."""
        from engine import rodata as R
        sh = self.g.inventory_ui.sheet_us(0)
        if sh is None: return
        f = (self.glove_t // 10) % 4; y -= 6              # its point level with the top half of the text
        v.blit(sh, (x + R.s32(0x800AA130 + 4 * f), y + R.s32(0x800AA140 + 4 * f)), (176 + 16 * f, 160, 16, 16))

    def tr(self, s):
        """Options > Language: French / German / Italian / Spanish words (options_text.py); else English."""
        from options_text import tr
        return tr(getattr(self.g, 'lang', 'us'), s)

    def text(self, v, s, x, y, width=None):
        gf = self.g.game_font
        if not gf.ok: return
        s = self.tr(s)
        if width is not None:
            while s and gf.width(s) > width: s = s[:-1]
        gf.draw(v, s, x, y)

    # ---------------------------------------------------------------- drawing
    def draw(self, screen, backdrop):
        """screen: the window; backdrop: the paused game frame (320 x 240)."""
        self.tick(); self.glove_t += 1
        screen = self.g.screen                          # (tick may have made a new window)
        v = self.canvas; gf = self.g.game_font
        v.blit(backdrop, (0, 0))
        shade = pygame.Surface((VW, VH), pygame.SRCALPHA); shade.fill((0, 0, 0, 200)); v.blit(shade, (0, 0))
        self._rects = []
        tabs = self.tabs(); self.tab = min(self.tab, len(tabs) - 1)
        lay = self.tab_layout(tabs); four = len(tabs) > 3
        order = [i for i in range(len(tabs)) if i != self.tab] + [self.tab]   # tabs: the chosen one on top
        for i in order:
            x, pw = lay[i]; pl = self.plate(i != self.tab, pw, four); name = tabs[i]
            v.blit(pl, (x, 4))
            if gf.ok: self.text(v, name, x + (pw - gf.width(self.tr(name))) // 2, 4 + 8)
        for i in range(len(tabs)):
            x, pw = lay[i]
            self._rects.append((pygame.Rect(x, 4, lay[i + 1][0] - x if i < len(tabs) - 1 else pw, 32), ('tab', i)))
        v.blit(self.parchment(PANEL.w, PANEL.h), PANEL.topleft)
        rows = self.rows(); bad = self.conflicts()
        self.row = min(self.row, len(rows) - 1)           # (Load delay comes and goes with Custom)
        LX, CX = 40, 172                  # labels / the binding column; the glove sits 20 px before either
        if self.tab not in (0, 3) and gf.ok:   # Options / Mods: labels further left, the glove just after the
            LX = 22                       # longest name, the values right after it (room for long values)
            GX = LX + max(gf.width(self.tr(r[2])) for r in rows if r[0] in ('int', 'choice', 'toggle')) + 2
        else:
            GX = CX - 28
        y0 = ROW_Y
        if self.tab == 3: LX = 22
        if self.tab in (0, 3):
            head = 'Keyboard' if self.col == 0 else 'Controller'
            self.text(v, '<', CX - 14, PANEL.y + 6); self.text(v, head, CX, PANEL.y + 6)
            self.text(v, '>', CX + (gf.width(self.tr(head)) if gf.ok else 60) + 4, PANEL.y + 6)
            self._rects.append((pygame.Rect(CX - 16, PANEL.y + 4, 120, ROW_H), ('col',)))
            y0 = ROW_Y + 8
        visible = (PANEL.bottom - 12 - y0) // ROW_H
        if self.row < self.scroll: self.scroll = self.row
        if self.row >= self.scroll + visible: self.scroll = self.row - visible + 1
        self.scroll = max(0, min(self.scroll, max(0, len(rows) - visible)))
        for i in range(self.scroll, min(len(rows), self.scroll + visible)):
            kind, key, label = rows[i]; y = y0 + (i - self.scroll) * ROW_H
            rr = pygame.Rect(PANEL.x + 16, y, PANEL.w - 32, ROW_H)
            sel = i == self.row
            if kind == 'bind':
                self.text(v, label, LX, y, CX - 22 - LX)
                ci = self.col; kk = 'k' if ci == 0 else 'p'
                toks = self.bind_list(key, ci == 0)
                names = [key_label(t) if ci == 0 else Controls.describe(t) for t in toks]
                txt = ', '.join(names)
                if gf.ok and gf.width(txt) > PANEL.right - 16 - CX and names: txt = names[0] + ' +'
                if self.capture is not None and sel: txt = '...'
                elif not txt: txt = '-'
                if (key, kk) in bad: txt = '!' + txt
                self.text(v, txt, CX, y, PANEL.right - 16 - CX)
                if sel: self.glove(v, CX - 20, y)
            else:
                self.text(v, label, LX, y)
                gx = GX if key != 'sr_preset' or not gf.ok else LX + gf.width(self.tr(label)) + 4   # (the preset's name: all the room)
                if sel: self.glove(v, gx, y)                   # after the names, before the value
                if kind in ('int', 'choice', 'toggle'):
                    vx = gx + 20; val = self.value_text(key)
                    if kind in ('int', 'choice'):
                        self.text(v, '<', vx, y); self.text(v, val, vx + 10, y, PANEL.right - 24 - vx)
                        rx = vx + 10 + (gf.width(self.tr(val)) if gf.ok else 40) + 3
                        self.text(v, '>', rx, y)
                        self._rects.append((pygame.Rect(vx - 4, y, 14, ROW_H), ('row', i, self.col, -1)))
                        self._rects.append((pygame.Rect(rx - 2, y, 14, ROW_H), ('row', i, self.col, 1)))
                    else:
                        self.text(v, val, vx + 10, y)
            self._rects.append((rr, ('row', i)))
        sh8 = self.g.inventory_ui.sheet_us(8)
        if sh8 is not None and self.scroll + visible < len(rows):              # more below: the "more" marker
            v.blit(sh8, (PANEL.centerx - 8, PANEL.bottom - 18), (176 + 16 * ((self.glove_t // 10) % 4), 56, 16, 16))
        if sh8 is not None and self.scroll > 0:
            up = pygame.Surface((16, 16), pygame.SRCALPHA); up.blit(sh8, (0, 0), (176, 56, 16, 16))
            v.blit(pygame.transform.flip(up, False, True), (PANEL.right - 40, PANEL.y + 2))
        v.blit(self.parchment(FOOT.w, FOOT.h), FOOT.topleft)
        recent = self.msg and pygame.time.get_ticks() - self.msg_t < 4000
        if recent: help_ = self.msg
        elif self.tab == 0: help_ = 'Enter bind  Del clear  < > keys / pad'
        elif self.tab == 3 and rows[self.row][1] == 'sr_preset': help_ = self.value_text('sr_preset')   # the whole name
        elif self.tab == 3: help_ = 'Enter do / bind  Del clear  < > keys / pad'
        else: help_ = 'Left / Right change    Esc back'
        self.text(v, help_, FOOT.x + 16, FOOT.y + 8, FOOT.w - 32)
        screen.fill((0, 0, 0))
        dst = self.g.view_rect()
        screen.blit(VF.upscale(v, dst.size, self.g.settings), dst.topleft)
