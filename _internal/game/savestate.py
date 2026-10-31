"""Exact save states: the whole running game copied at one frame and put back (speedrun.py's slots).

snapshot(g) deep-copies the game's own state - g.mem (the game's 2 MB of RAM), the entities and free
slots, effects, the event VM, physics, the camera, fades, message windows, menus - plus the
module-level RNG (gamerng.state) and Game.VBLANKS.  The player's settings, controls, the window,
the sound mixer, the fonts and the front end are live objects (SKIP): shared wherever the state
points at them, never copied.  Pictures, sounds, functions and modules are shared too.  restore(g,
snap) copies the snapshot back in (the snapshot stays reusable), points it at the running game's live
objects, stops the sound effects and puts the restored game's music on.  Replaying the same input
after a restore matches the first run frame for frame (RAM, every entity, the RNG, the drawn picture),
also after a map change or a continue in between (docs/2026-10-22-exact-save-states.txt).

save_file / load_file write a snapshot to disk and read it back in another run of the remake
(pickle, zlib).  What the state shares with the running game is written as a name and found again
on load: the game and its live objects ('skip'), sprites and effect banks (their asset folder),
closures (their attribute path in the running game); the map is written without its pictures and
rebuilt from its map number; other small pictures (message rows, the transition copy) go in by value.
"""
import copy, types, pickle, zlib, io
from pathlib import Path
import pygame
import gamerng

SHARE = [pygame.Surface, pygame.mixer.Sound, pygame.mixer.Channel, pygame.font.Font, pygame.time.Clock,
         types.ModuleType, types.FunctionType, types.BuiltinFunctionType, type]
try: SHARE.append(pygame.joystick.JoystickType)
except AttributeError: pass
SKIP = ('settings', 'controls', 'settings_screen', 'controls_screen', 'screen', 'snd', 'pacer', 'clock',
        'font', 'game_font', 'front', '_backdrop', 'toasts', 'sfx_cache', 'view')
MAGIC, VERSION = b'ARXS', 1


def _same(x, memo): return x


def _free(x, memo):
    """A free entity slot (Game.EntView.Free reads every missing word as 0, __deepcopy__ too): only its
    AI words and state bytes are state."""
    y = object.__new__(type(x)); memo[id(x)] = y
    d = x.__dict__
    object.__setattr__(y, 'slot', d['slot'])
    object.__setattr__(y, 'ai', copy.deepcopy(d['ai'], memo))
    object.__setattr__(y, 'bytes', copy.deepcopy(d['bytes'], memo))
    return y


_ready = False


def _setup(g):
    global _ready
    if _ready: return
    for t in SHARE: copy._deepcopy_dispatch[t] = _same
    copy._deepcopy_dispatch[type(g).EntView.Free] = _free
    _ready = True


def _live(g): return {k: g.__dict__[k] for k in SKIP if k in g.__dict__}


def snapshot(g):
    _setup(g)
    live = _live(g)
    state = {k: v for k, v in g.__dict__.items() if k not in live}
    memo = {id(g): g}
    for o in live.values(): memo[id(o)] = o                 # live objects stay shared
    snap = copy.deepcopy(state, memo)
    snap['__rng'] = list(gamerng.state); snap['__vblanks'] = type(g).VBLANKS
    snap['__live'] = live                                   # (references: which objects were the live ones)
    snap['__audio'] = g.snd.state()                         # music position, fade, sounds playing
    return snap


def restore(g, snap):
    _setup(g)
    memo = {id(g): g}
    now = _live(g)
    for k, o in snap.get('__live', {}).items():             # the snapshot's live objects -> today's
        if k in now: memo[id(o)] = now[k]
    for o in now.values(): memo[id(o)] = o
    s = {k: v for k, v in snap.items() if k != '__live'}
    s = copy.deepcopy(s, memo)
    audio = s.pop('__audio', None)
    gamerng.state[:] = s.pop('__rng'); type(g).VBLANKS = s.pop('__vblanks')
    g.__dict__.update(s)
    if hasattr(g, 'world'): g.world.game = g
    try:                                                    # (the state's map, as a map change does: no first-use stalls)
        g.preload_map(); g.snd.preload_thread.join()
    except Exception: pass
    g.front = None                                          # (a state is always of play, whatever screen loads it)
    for i, f in enumerate(g.ent.free): object.__setattr__(f, 'slot', i)
    snd = g.snd
    if audio is not None:
        try:
            snd.set_state(audio); g.pad_held = g.controls.held(pygame.key.get_pressed()) & 0xFFFF
            return
        except Exception: g.log_error('save state audio')
    try: snd.stop_all()
    except Exception: pass
    snd.set_map(g.map.id)                                   # the restored map's sound bank (0x8004B0D8)
    mid = g.music                                           # the restored game's music
    try:
        if not mid: snd.music_stop(False)
        elif mid != snd.music or not snd.music_on: snd.music_load_now(mid, True)
    except Exception: pass
    g.pad_held = g.controls.held(pygame.key.get_pressed()) & 0xFFFF   # buttons down now are no fresh press


# ---------------------------------------------------------------- files
def _has_surface(v, depth=0):
    if isinstance(v, pygame.Surface): return True
    if depth > 2: return False
    if isinstance(v, dict): return any(_has_surface(x, depth + 1) for x in v.values())
    if isinstance(v, (list, tuple)): return any(_has_surface(x, depth + 1) for x in v)
    return type(v).__name__ == 'Lining'


def _fn_paths(g):
    """Where each function / lambda the game made can be found: 'attr' or 'attr.attr'."""
    out = {}
    for k, v in g.__dict__.items():
        if isinstance(v, (types.FunctionType, types.MethodType)): out[id(v)] = k
        elif hasattr(v, '__dict__') and not isinstance(v, (type, types.ModuleType)):
            for k2, v2 in vars(v).items():
                if isinstance(v2, (types.FunctionType, types.MethodType)): out[id(v2)] = f'{k}.{k2}'
    return out


def _get_path(g, path):
    o = g
    for p in path.split('.'): o = getattr(o, p)
    return o


_LOAD_G = None


def _map_rebuild(map_id, state):
    """A map from its number with the saved state over it (cells, events, scripts...); its pictures
    and fog layer come from the map files again."""
    g = _LOAD_G
    gm = type(g).__module__
    import sys
    GameMap = sys.modules[gm].GameMap
    m = GameMap(map_id)
    m.__dict__.update(state)
    if getattr(m, 'lining', None) is not None:
        m.lining.clock = lambda: type(g).VBLANKS           # (load_map's sway clock)
    return m


def _free_rebuild(cls, slot, ai, bytes_):
    y = object.__new__(cls)
    object.__setattr__(y, 'slot', slot); object.__setattr__(y, 'ai', ai); object.__setattr__(y, 'bytes', bytes_)
    return y


def _surface(size, flags, data):
    s = pygame.image.frombytes(data, size, 'RGBA')
    return s.convert_alpha() if flags & pygame.SRCALPHA and pygame.display.get_surface() is not None else s


class _Pickler(pickle.Pickler):
    def __init__(self, f, g, live):
        super().__init__(f, protocol=5)
        self.g = g; self.live = {id(o): k for k, o in live.items()}; self.fns = _fn_paths(g)
        import sys; mod = sys.modules[type(g).__module__]
        import effects
        self.Sprite = mod.Sprite; self.GameMap = mod.GameMap; self.Bank = effects.Bank; self.Free = type(g).EntView.Free

    def persistent_id(self, o):
        if o is None: return None                           # (g.front is None in play: not a reference to it)
        if o is self.g: return ('game',)
        k = self.live.get(id(o))
        if k is not None: return ('live', k)
        if isinstance(o, self.Sprite): return ('sprite', str(o.folder))
        if isinstance(o, self.Bank): return ('bank', str(o.folder))
        if isinstance(o, (types.FunctionType, types.MethodType)) and id(o) in self.fns: return ('fn', self.fns[id(o)])
        if isinstance(o, pygame.mixer.Sound) or isinstance(o, pygame.mixer.Channel): return ('none',)
        return None

    def reducer_override(self, o):
        if type(o) is self.Free:                            # (its __getattr__ answers 0 to __setstate__ too)
            d = o.__dict__; return _free_rebuild, (self.Free, d['slot'], d['ai'], d['bytes'])
        if isinstance(o, self.GameMap):
            return _map_rebuild, (o.id, {k: v for k, v in vars(o).items() if not _has_surface(v)})
        if isinstance(o, pygame.Surface):
            return _surface, (o.get_size(), o.get_flags(), pygame.image.tobytes(o, 'RGBA'))
        return NotImplemented


class _Unpickler(pickle.Unpickler):
    def __init__(self, f, g, live):
        super().__init__(f); self.g = g; self.live = live
        import sys; mod = sys.modules[type(g).__module__]
        import effects
        self.Sprite = mod.Sprite; self.Bank = effects.Bank; self.mod = mod

    def find_class(self, module, name):
        # the game's classes are the running module's, whichever name the file was saved under
        if module in ('__main__', 'alundra_remake'): module = self.mod.__name__
        return super().find_class(module, name)

    def persistent_load(self, pid):
        kind = pid[0]
        if kind == 'game': return self.g
        if kind == 'live':                                  # (older files stored every None as 'front')
            return None if pid[1] == 'front' else self.live.get(pid[1])
        if kind == 'sprite': return self.Sprite.get(Path(pid[1]))
        if kind == 'bank': return self.Bank.get(Path(pid[1]))
        if kind == 'fn': return _get_path(self.g, pid[1])
        if kind == 'none': return None
        raise pickle.UnpicklingError(f'unknown reference {pid!r}')


def save_file(g, snap, path):
    """A snapshot (from snapshot(g)) to a file."""
    live = snap.get('__live', {})
    body = {k: v for k, v in snap.items() if k != '__live'}
    buf = io.BytesIO(); _Pickler(buf, g, live).dump(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(MAGIC + VERSION.to_bytes(4, 'little') + zlib.compress(buf.getvalue(), 6))
    tmp.replace(path)


def load_file(g, path):
    """A snapshot written by save_file, read in this run of the remake (restore(g, it) puts it in)."""
    global _LOAD_G
    data = path.read_bytes()
    if data[:4] != MAGIC or int.from_bytes(data[4:8], 'little') != VERSION: raise ValueError('not an exact state file')
    _setup(g); _LOAD_G = g
    try:
        snap = _Unpickler(io.BytesIO(zlib.decompress(data[8:])), g, _live(g)).load()
    finally:
        _LOAD_G = None
    snap['__live'] = _live(g)
    return snap
