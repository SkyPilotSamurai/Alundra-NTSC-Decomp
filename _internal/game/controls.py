"""Keyboard and controller bindings for the remake (saved in controls.json).

Every action is one PlayStation pad bit, so the game's own scripts (command 2F)
see the same buttons the player uses.  Controller bindings are tokens:
'button:N', 'axis:N:+' / 'axis:N:-' (stick past half way), 'hat:N:up|down|left|right'.
"""
import json
from pathlib import Path
import pygame

from home import HOME
FILE = HOME / 'controls.json'

# action, label, PSX pad bit
ACTIONS = [
    ('up', 'Up', 0x1000), ('down', 'Down', 0x4000), ('left', 'Left', 0x8000), ('right', 'Right', 0x2000),
    ('jump', 'Jump (Cross)', 0x40), ('attack', 'Attack / Talk (Square)', 0x80),
    ('item', 'Item (Circle)', 0x20), ('dash', 'Dash (Triangle)', 0x10),
    ('l1', 'L1', 0x04), ('r1', 'R1', 0x08), ('l2', 'L2', 0x01), ('r2', 'R2', 0x02),
    ('select', 'Select', 0x100), ('start', 'Start', 0x800),
    ('menu', 'Menu shortcut', 0x10000),      # the remake's settings page (not a pad button of the game)
]
MENU_BIT = 0x10000
BIT = {a: b for a, _, b in ACTIONS}

DEFAULT_KEYS = {
    'up': ['up'], 'down': ['down'], 'left': ['left'], 'right': ['right'],
    'jump': ['x', 'space'], 'attack': ['z', 'return', 'a'], 'item': ['s'], 'dash': ['c', 'left shift'],
    'l1': ['q'], 'r1': ['w'], 'l2': ['1'], 'r2': ['2'], 'select': ['backspace'], 'start': ['tab'],
    'menu': ['backspace'],
}
# Xbox-style layout as SDL numbers it (works for most PlayStation pads too)
DEFAULT_PAD = {
    'up': ['hat:0:up', 'axis:1:-'], 'down': ['hat:0:down', 'axis:1:+'],
    'left': ['hat:0:left', 'axis:0:-'], 'right': ['hat:0:right', 'axis:0:+'],
    'jump': ['button:0'], 'item': ['button:1'], 'attack': ['button:2'], 'dash': ['button:3'],
    'l1': ['button:4'], 'r1': ['button:5'], 'l2': ['axis:4:+'], 'r2': ['axis:5:+'],
    'select': ['button:6'], 'start': ['button:7'],
    'menu': ['button:6'],
}
DEADZONE = 0.5


_CODES = {}


def key_code(name):
    """A key name's code, asked of SDL once per name (SDL's name lookup crashed natively on
    Windows when asked every frame while the system was busy - another program loading)."""
    try: return _CODES[name]
    except KeyError: pass
    try: c = pygame.key.key_code(name)
    except (ValueError, AttributeError, pygame.error): c = None
    _CODES[name] = c
    return c


class Pad:
    """A pad SDL's game controller layer knows, read like a joystick in the Xbox layout
    DEFAULT_PAD uses: buttons A B X Y LB RB Back Start LS RS Guide, hat 0 the d-pad, axes left
    x / y, right x / y, LT, RT (the triggers from -1 at rest to 1, as XInput's)."""
    BUTTONS = (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_X,
               pygame.CONTROLLER_BUTTON_Y, pygame.CONTROLLER_BUTTON_LEFTSHOULDER, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
               pygame.CONTROLLER_BUTTON_BACK, pygame.CONTROLLER_BUTTON_START, pygame.CONTROLLER_BUTTON_LEFTSTICK,
               pygame.CONTROLLER_BUTTON_RIGHTSTICK, pygame.CONTROLLER_BUTTON_GUIDE)
    DPAD = (pygame.CONTROLLER_BUTTON_DPAD_UP, pygame.CONTROLLER_BUTTON_DPAD_DOWN,
            pygame.CONTROLLER_BUTTON_DPAD_LEFT, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
    AXES = (pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY, pygame.CONTROLLER_AXIS_RIGHTX,
            pygame.CONTROLLER_AXIS_RIGHTY, pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT)
    OWN = (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION, pygame.JOYHATMOTION, pygame.JOYBALLMOTION,
           pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP, pygame.CONTROLLERAXISMOTION)

    def __init__(self, c):
        self.c = c; self.j = c.as_joystick()

    def get_instance_id(self): return self.j.get_instance_id()
    def get_name(self): return self.c.name
    def get_numbuttons(self): return len(self.BUTTONS)
    def get_numaxes(self): return len(self.AXES)
    def get_numhats(self): return 1
    def get_button(self, n): return self.c.get_button(self.BUTTONS[n])

    def get_axis(self, n):
        v = max(-1.0, min(1.0, self.c.get_axis(self.AXES[n]) / 32767))
        return v * 2 - 1 if n >= 4 else v

    def get_hat(self, n):
        b = self.c.get_button
        return (b(pygame.CONTROLLER_BUTTON_DPAD_RIGHT) - b(pygame.CONTROLLER_BUTTON_DPAD_LEFT),
                b(pygame.CONTROLLER_BUTTON_DPAD_UP) - b(pygame.CONTROLLER_BUTTON_DPAD_DOWN))


class Controls:
    def __init__(self):
        self.keys = {a: list(v) for a, v in DEFAULT_KEYS.items()}
        self.pad = {a: list(v) for a, v in DEFAULT_PAD.items()}
        self.deadzone = DEADZONE
        self.load()
        self.sticks = {}
        self.refresh_pads()

    # ---- file
    def load(self):
        try:
            d = json.loads(FILE.read_text())
            if 'talk' in d.get('keyboard', {}) or 'talk' in d.get('controller', {}):
                return                              # the old layout (talk on Circle): start from the defaults
            for a in BIT:
                if isinstance(d.get('keyboard', {}).get(a), list): self.keys[a] = d['keyboard'][a]
                if isinstance(d.get('controller', {}).get(a), list): self.pad[a] = d['controller'][a]
            if 'menu' not in d.get('keyboard', {}): self.keys['menu'] = list(self.keys.get('select', []))   # (older files:
            if 'menu' not in d.get('controller', {}): self.pad['menu'] = list(self.pad.get('select', []))   # Select opened it)
            self.deadzone = float(d.get('deadzone', DEADZONE))
        except (OSError, ValueError):
            pass

    def save(self):
        FILE.write_text(json.dumps({'keyboard': self.keys, 'controller': self.pad, 'deadzone': self.deadzone}, indent=1))

    def reset(self):
        self.keys = {a: list(v) for a, v in DEFAULT_KEYS.items()}
        self.pad = {a: list(v) for a, v in DEFAULT_PAD.items()}

    # ---- controllers
    def refresh_pads(self):
        """Every pad SDL knows (PlayStation, Xbox, Switch...) is read through SDL's game controller
        layer in the Xbox layout DEFAULT_PAD numbers (Pad below); an unknown one as it is."""
        pygame.joystick.init()
        self.sticks = {}
        try:
            from pygame._sdl2 import controller as gc
            gc.init()
        except (ImportError, pygame.error):
            gc = None
        for i in range(pygame.joystick.get_count()):
            try:
                if gc is not None and gc.is_controller(i):
                    p = Pad(gc.Controller(i)); self.sticks[p.get_instance_id()] = p; continue
            except pygame.error:
                pass
            j = pygame.joystick.Joystick(i); j.init(); self.sticks[j.get_instance_id()] = j

    def events(self, evs):
        """The frame's events with each known pad's own events in the Xbox layout (a PS4 pad's raw
        numbers differ: Options would be button 6, L3 button 7, the d-pad buttons, not a hat)."""
        out = []
        for e in evs:
            pad = self.sticks.get(getattr(e, 'instance_id', None))
            if not isinstance(pad, Pad) or e.type not in Pad.OWN:
                if e.type not in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP, pygame.CONTROLLERAXISMOTION):
                    out.append(e)                     # (an unknown pad's own events stay as they are)
                continue
            if e.type in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP):
                if e.button in Pad.DPAD:
                    out.append(pygame.event.Event(pygame.JOYHATMOTION, instance_id=e.instance_id, joy=0, hat=0, value=pad.get_hat(0)))
                elif e.button in Pad.BUTTONS:
                    t = pygame.JOYBUTTONDOWN if e.type == pygame.CONTROLLERBUTTONDOWN else pygame.JOYBUTTONUP
                    out.append(pygame.event.Event(t, instance_id=e.instance_id, joy=0, button=Pad.BUTTONS.index(e.button)))
            elif e.type == pygame.CONTROLLERAXISMOTION and e.axis in Pad.AXES:
                n = Pad.AXES.index(e.axis)
                out.append(pygame.event.Event(pygame.JOYAXISMOTION, instance_id=e.instance_id, joy=0, axis=n, value=pad.get_axis(n)))
        return out

    def pad_name(self):
        return next((j.get_name() for j in self.sticks.values()), None)

    def token_active(self, tok):
        kind, *rest = tok.split(':')
        for j in self.sticks.values():
            try:
                if kind == 'button':
                    n = int(rest[0])
                    if n < j.get_numbuttons() and j.get_button(n): return True
                elif kind == 'axis':
                    n = int(rest[0])
                    if n < j.get_numaxes():
                        v = j.get_axis(n)
                        if (v > self.deadzone) if rest[1] == '+' else (v < -self.deadzone): return True
                elif kind == 'hat':
                    n = int(rest[0])
                    if n < j.get_numhats():
                        x, y = j.get_hat(n)
                        if {'up': y > 0, 'down': y < 0, 'left': x < 0, 'right': x > 0}[rest[1]]: return True
            except (ValueError, IndexError, KeyError, pygame.error):
                pass
        return False

    # ---- state
    def held(self, keys):
        bits = 0
        for a, bit in BIT.items():
            for name in self.keys.get(a, ()):
                c = key_code(name)
                try:
                    if c is not None and keys[c]: bits |= bit; break
                except IndexError: pass
            else:
                if any(self.token_active(t) for t in self.pad.get(a, ())): bits |= bit
        return bits

    @staticmethod
    def token_from_event(e, deadzone=DEADZONE):
        """A controller event as a binding token (None if not a binding)."""
        if e.type == pygame.JOYBUTTONDOWN: return f'button:{e.button}'
        if e.type == pygame.JOYAXISMOTION and abs(e.value) > 0.75: return f'axis:{e.axis}:{"+" if e.value > 0 else "-"}'
        if e.type == pygame.JOYHATMOTION and e.value != (0, 0):
            x, y = e.value
            return f'hat:{e.hat}:' + ('up' if y > 0 else 'down' if y < 0 else 'left' if x < 0 else 'right')
        return None

    @staticmethod
    def describe(tok):
        kind, *rest = tok.split(':')
        if kind == 'button': return f'Button {rest[0]}'
        if kind == 'axis': return f'Axis {rest[0]}{rest[1]}'
        if kind == 'hat': return f'D-pad {rest[1]}'
        return tok


class ControlsScreen:
    """In-game settings page: pick an action, then press the key or controller
    input to bind it (Enter / Circle-button to start, Esc / Delete to clear)."""

    def __init__(self, controls, font):
        self.c = controls; self.font = font; self.row = 0; self.col = 0; self.waiting = False; self.open = False
        self.msg = ''

    def rows(self):
        return [(a, label) for a, label, _ in ACTIONS] + [('__reset', 'Reset to defaults'), ('__close', 'Save and close')]

    def handle(self, e):
        """Returns True while the screen uses the event."""
        if not self.open: return False
        rows = self.rows()
        if self.waiting:
            action = rows[self.row][0]
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: self.waiting = False; self.msg = 'Cancelled'; return True
                name = pygame.key.name(e.key)
                if self.col == 0:
                    if e.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and action != 'select': self.c.keys[action] = []
                    else: self.c.keys[action] = [name]
                    self.waiting = False; self.msg = f'{action}: {name}'
                elif e.key == pygame.K_DELETE:
                    self.c.pad[action] = []; self.waiting = False
                return True
            if self.col == 1:
                tok = Controls.token_from_event(e)
                if tok:
                    self.c.pad[action] = [tok]; self.waiting = False; self.msg = f'{action}: {Controls.describe(tok)}'
            return True
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE: self.close(); return True
            if k == pygame.K_UP: self.row = (self.row - 1) % len(rows)
            if k == pygame.K_DOWN: self.row = (self.row + 1) % len(rows)
            if k in (pygame.K_LEFT, pygame.K_RIGHT): self.col ^= 1
            if k in (pygame.K_RETURN, pygame.K_z): self.activate()
            if k == pygame.K_DELETE and rows[self.row][0] in BIT:
                (self.c.keys if self.col == 0 else self.c.pad)[rows[self.row][0]] = []
        elif e.type == pygame.JOYHATMOTION and e.value != (0, 0):
            x, y = e.value
            if y: self.row = (self.row - y) % len(rows)
            if x: self.col ^= 1
        elif e.type == pygame.JOYBUTTONDOWN:
            if e.button in (0, 1): self.activate()
            if e.button == 7: self.close()
        return True

    def activate(self):
        a = self.rows()[self.row][0]
        if a == '__reset': self.c.reset(); self.msg = 'Defaults restored'
        elif a == '__close': self.close()
        else: self.waiting = True; self.msg = 'Press a key' if self.col == 0 else 'Press a controller button, stick or d-pad'

    def close(self):
        self.c.save(); self.open = False; self.waiting = False

    def draw(self, surf):
        W, H = surf.get_size()
        ov = pygame.Surface((W, H)); ov.fill((8, 10, 30)); ov.set_alpha(235); surf.blit(ov, (0, 0))
        f = self.font; white = (240, 240, 240); dim = (150, 150, 170); hi = (255, 220, 110)
        surf.blit(f.render('Controls', True, hi), (8, 4))
        pad = self.c.pad_name()
        surf.blit(f.render(f'Controller: {pad}' if pad else 'No controller found (plug one in any time)', True, dim), (8, 16))
        surf.blit(f.render('Keyboard', True, hi if self.col == 0 else dim), (128, 30))
        surf.blit(f.render('Controller', True, hi if self.col == 1 else dim), (224, 30))
        rows = self.rows()
        top = max(0, min(self.row - 7, len(rows) - 14))
        for i, (a, label) in enumerate(rows[top:top + 14]):
            r = top + i; y = 44 + i * 12; sel = r == self.row
            surf.blit(f.render(('> ' if sel else '  ') + label, True, hi if sel else white), (4, y))
            if a in BIT:
                kb = ', '.join(self.c.keys.get(a, [])) or '-'
                jp = ', '.join(Controls.describe(t) for t in self.c.pad.get(a, [])) or '-'
                if sel and self.waiting: kb, jp = ('...', jp) if self.col == 0 else (kb, '...')
                surf.blit(f.render(kb[:16], True, hi if sel and self.col == 0 else white), (128, y))
                surf.blit(f.render(jp[:18], True, hi if sel and self.col == 1 else white), (224, y))
        help_ = self.msg or 'Arrows pick, Enter binds, Delete clears, Esc saves and closes'
        surf.blit(f.render(help_, True, dim), (8, H - 14))
