"""Speedrun runs: save states for practice, on the F5 / Select page's Speedrun tab and on two
bindable inputs (default F6 save, F7 load).  Only in a game started from the title's SPEEDRUN page
(start_run; it lasts through state loads, and a new game or a History Book continue ends it).

A state is the game's own continue record (the block 0x801DD2D8..0x801DDA30 as 0x80083E34
stores it, 0x76C bytes like the History Book hands over) with the respawn point moved to where
Alundra stands, so loading it is a CONTINUE (Game.begin_continue) that arrives on that map and
tile.  That file is the fallback: a save also keeps the exact moment (savestate.py: position,
enemies, timers, RNG) in memory and in slot<N>.xstate, and a load puts that back instead, also after
a restart of the remake.  The block's real respawn point is kept in the file and put back after the load, so a game
over still returns to the last save point.  Map entities restart as on any arrival: a state is
taken at map granularity, not frame-exact.

Files: HOME/speedrun_states/<us|jp>/slot<N>.state (the player's own slots) and the route's
presets, the speedrun starts the title's SPEEDRUN page lists (assets/speedrun/<us|jp>/*.bin, raw
continue records made from the user's BizHawk states by tools/speedrun_states.py).
"""
import struct
from home import HOME, ASSETS

ROOT = HOME / 'speedrun_states'
PRESETS = ASSETS / 'speedrun'
MAGIC, VERSION = b'ARSS', 1
BLOCK = 0x801DD2D8
BLOCK_LEN, RECORD_LEN = 0x758, 0x76C
RESPAWN = 0x801DD324                       # map, tile x, tile y, z (4 words)
RESPAWN_OFF = RESPAWN - BLOCK
ROUTES = ('us', 'jp')
DEFAULT_BINDS = {'save': {'k': ['f6'], 'p': []}, 'load': {'k': ['f7'], 'p': []}}


LAST = {}                                  # route -> the last preset loaded (this run of the remake only)
RUN = None                                 # 'us' / 'jp' while the game came from a SPEEDRUN start
                                           # (module level: Game.begin_continue re-runs Game.__init__)


def pretty(name):
    """A preset's file name as the menu shows it: '28 - Magyscar - Boss Corpse Worm.bin' ->
    '28  Magyscar - Boss Corpse Worm'."""
    import re
    for ext in ('.bin', '.State', '.state'):
        if name.endswith(ext): name = name[:-len(ext)]
    return re.sub(r'^(\d+)\s*-\s*', r'\1  ', name)


def start_run(g, route, name=None):
    """The title's front end hands over a game: a SPEEDRUN start (its version's folder name) or a
    History Book continue / new game (None).  A speedrun start also points the tab at its version,
    with that version's Balance and Dialogue & font, as choosing the Route does."""
    global RUN
    RUN = route if route in ROUTES else None
    if RUN is not None and name: LAST[RUN] = name          # the Preset row opens on the start picked
    if RUN is not None:
        from settings_screen import save_settings
        s = g.settings
        s['sr_route'] = s['balance'] = s['text_lang'] = RUN; s['sr_preset'] = ''   # (preset_sel: LAST)
        save_settings(s)                       # (begin_continue reads settings.json again)


def active(): return RUN is not None


def norm_binds(b):
    out = {n: {'k': list(v['k']), 'p': list(v['p'])} for n, v in DEFAULT_BINDS.items()}
    if isinstance(b, dict):
        for n in out:
            d = b.get(n)
            if isinstance(d, dict):
                for kind in ('k', 'p'):
                    if isinstance(d.get(kind), list): out[n][kind] = [t for t in d[kind] if isinstance(t, str)]
    return out


def slot_path(route, slot): return ROOT / route / f'slot{slot}.state'


def exact_path(path): return path.with_suffix('.xstate')   # the exact snapshot (savestate.save_file)


def has_state(path): return str(path) in EXACT or exact_path(path).is_file() or path.is_file()


def presets(route):
    try: return sorted((p.name for p in [*(PRESETS / route).glob('*.bin'), *(PRESETS / route).glob('*.State')]), key=str.lower)
    except OSError: return []


def preset_path(route, name): return PRESETS / route / name


EXACT = {}                                 # slot path -> savestate.snapshot (this run of the remake only)
KIND = None                                # what the last load was: 'exact' / 'room' (the file's continue record)


def can_save(g):
    return g.front is None and getattr(g, 'map', None) is not None


def _room_ok(g): return g.trans is None and g.pending_warp is None


def save_state(g, path):
    """The exact moment: savestate.snapshot, kept in memory and written to slot<N>.xstate; and the
    fallback file slot<N>.state, the continue record of the game as it stands at Alundra's map and
    tile (not written in the middle of a map change)."""
    from engine import gamestart as egs
    import sys, savestate
    if not can_save(g): return 'Cannot save here'
    snap = EXACT[str(path)] = savestate.snapshot(g)
    try: savestate.save_file(g, snap, exact_path(path))
    except Exception: g.log_error('exact save state file')   # (memory still has it)
    if not _room_ok(g): return None
    TW, TH = (getattr(sys.modules[type(g).__module__], n) for n in ('TW', 'TH'))
    m = g.mem; h = egs.handoff(g)
    rec = bytearray(m.u8(h + i) for i in range(RECORD_LEN))       # the tail past the block as handed over
    rec[:BLOCK_LEN] = bytes(m.u8(BLOCK + i) for i in range(BLOCK_LEN))
    respawn = bytes(rec[RESPAWN_OFF:RESPAWN_OFF + 16])
    p = g.player
    struct.pack_into('<iiii', rec, RESPAWN_OFF, g.cur_map, int(p.wx // TW), int(p.wy // TH), p.pz >> 20)
    struct.pack_into('<i', rec, 0, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MAGIC + struct.pack('<I', VERSION) + respawn + bytes(rec))
    return None


def load_state(g, path):
    """A slot: its exact snapshot (memory, else slot<N>.xstate), else the .state file (a
    continue at the saved tile, the respawn point put back afterwards); or a speedrun start (.bin:
    a continue record as the title's SPEEDRUN page loads it)."""
    global KIND
    from engine import gamestart as egs
    import savestate
    snap = EXACT.get(str(path))
    if snap is None and exact_path(path).is_file():
        try: snap = EXACT[str(path)] = savestate.load_file(g, exact_path(path))
        except Exception: g.log_error('exact save state file'); snap = None   # (then the continue record)
    if snap is not None:
        savestate.restore(g, snap); KIND = 'exact'; return None
    KIND = 'room'
    try: data = path.read_bytes()
    except OSError: return 'No state there'
    if path.suffix == '.bin':
        if len(data) < RECORD_LEN: return 'Not a speedrun start'
        g.begin_continue(data[:RECORD_LEN]); return None
    if path.suffix.lower() == '.state':                       # a BizHawk savestate (bizhawk_state.py)
        import bizhawk_state
        try: g.begin_continue(bizhawk_state.record(path)[1])
        except Exception: return 'Not an Alundra BizHawk state'
        return None
    if data[:4] != MAGIC or len(data) < 24 + RECORD_LEN: return 'Not a state file'
    respawn = data[8:24]; rec = data[24:24 + RECORD_LEN]
    g.begin_continue(rec)
    m = g.mem; h = egs.handoff(g)                                  # the real respawn point back
    for i, c in enumerate(respawn): m.w8(RESPAWN + i, c); m.w8(h + RESPAWN_OFF + i, c)
    return None


def message(what, route, slot):
    if what == 'save': return f'Saved Slot {slot}'
    return f'Loaded Slot {slot}' + (' (start of room)' if KIND == 'room' else '')


def hotkey(g, e):
    """A bound Save / Load state input (keyboard or controller); True if it was one."""
    s = g.settings
    if not active(): return False
    import pygame
    from controls import Controls
    if e.type == pygame.KEYDOWN: kind, tok = 'k', pygame.key.name(e.key)
    else: kind, tok = 'p', Controls.token_from_event(e)
    if not tok: return False
    binds = norm_binds(s.get('sr_binds'))
    for name in ('save', 'load'):
        if tok in binds[name][kind]:
            route = s.get('sr_route', 'us'); slot = s.get('sr_slot', 1)
            if name == 'save': err = save_state(g, slot_path(route, slot))
            else: err = load_state(g, slot_path(route, slot))
            g.toast(err or message(name, route, slot), game=True)
            return True
    return False
