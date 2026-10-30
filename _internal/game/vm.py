"""The game's event-script machine: program state, the opcode table and the editor's own opcode.
Every game opcode is written from the US v1.1 ALUN_CD.EXE handlers (table 0x8009B814) in vm_game_00,
_30, _60, _80, _A0 and vm_game_rest.py; the run loop is RunEntityProgram 0x80042BB8 (vm_game_30
run_faithful) and the entity selection 0x8003D374 (vm_game_00 select_faithful), installed below.

Model (as the game): every handler returns a byte advance; 0 = stay on this instruction next frame,
opcode 00 = stop for this frame and continue after it next frame, FF = program ended.  The context's
+8 (params[1]) holds the pc a waiting instruction started on.  logic = the entity commands act on
(+0x230), owner = the entity running the program.
"""
import math, random

TW, TH = 24, 16
CARDINAL = (0, 16, 8, 24)        # s32[4] at 0x80023644: down, up, left, right
SLOTS = 'ABCDEF'                 # A load, B map, C tick, D touch, E deactivate, F interact

# ------------------------------------------------------------------ docs --
# One line per command, used by the remake debug view and EVENT_REFERENCE.md.
DOC = {
    0x00: 'Stop here for this frame (continue after it next frame)',
    0x01: 'No operation',
    0x02: 'Jump (signed 16-bit offset from this command)',
    0x03: 'Jump if Result is not 0',
    0x04: 'Jump if Result is 0',
    0x05: 'Set game flag',
    0x06: 'Clear game flag',
    0x07: 'Result = any selected entity inside tile box (x1,x2,y1,y2,z1,z2)',
    0x08: 'Turn by n (32 directions)',
    0x09: 'Face direction n (0 down, 8 left, 16 up, 24 right)',
    0x0A: 'Turn around',
    0x0B: 'Play animation and wait until moved n pixels from start',
    0x0C: 'Face a random cardinal direction',
    0x0D: 'Show message (portrait + name of this entity); waits if a box is busy',
    0x10: 'Lock player control',
    0x11: 'Unlock player control',
    0x12: 'Play sound effect (8-bit id)',
    0x13: 'No operation',
    0x14: 'Halt (yields forever)',
    0x15: 'Put entity back on its record height',
    0x16: 'Gravity on',
    0x17: 'Gravity off',
    0x18: 'No operation',
    0x19: 'Deactivate this entity',
    0x1A: 'Set animation',
    0x1B: 'Set vertical force (jump/fall speed)',
    0x1C: 'Wait until the animation finished n times',
    0x1D: 'Wait until the animation finished n times or blocked',
    0x1E: 'Wait until moved n pixels',
    0x1F: 'Wait until moved n pixels or blocked',
    0x20: 'Wait until height changed by n pixels',
    0x21: 'Wait until height changed by n or landed on something',
    0x22: 'Move up/down to the record height',
    0x23: 'Move to record height or until landed on something',
    0x24: 'Wait until blocked',
    0x25: 'Wait until on ground or landed on something',
    0x26: 'Wait until blocked or landed on something',
    0x27: 'Face Alundra',
    0x28: 'Set class B flag', 0x29: 'Clear class B flag',
    0x2A: 'Set class A flag', 0x2B: 'Clear class A flag',
    0x2C: 'Result = no entity matches selector',
    0x2D: 'Spawn entity from template',
    0x2E: 'Destroy selected entities (Result = any destroyed)',
    0x2F: 'Result = pad buttons (mask, 0 held 1 pressed 2 released 3 repeat)',
    0x30: 'Jump if flag set', 0x31: 'Jump if flag clear', 0x32: 'Toggle flag',
    0x33: 'Result = all 4 flags set', 0x34: 'Result = all 4 flags clear',
    0x35: 'Wait until flag clear', 0x36: 'Wait until flag set',
    0x37: 'Wait n frames',
    0x38: 'Set save map remap entry',
    0x39: 'Wait until message box closed',
    0x3A: 'Face cardinal direction (0-3)',
    0x3B: 'Result = Alundra inside tile box',
    0x3C: 'Result = loose object inside tile box',
    0x3D: 'Result = any entity inside tile box',
    0x3E: 'Result = Alundra standing on this entity',
    0x3F: 'Result = anything standing on this entity',
    0x40: 'Change program n of this entity (restarts it)',
    0x41: 'Change sprite program n',
    0x42: 'Logic context = Alundra',
    0x43: 'Logic context = selected entity (Result = found)',
    0x44: 'Ask Yes/No (Result = yes)',
    0x45: 'Allow sliding round obstacles', 0x46: 'No sliding round obstacles',
    0x47: 'Wait until hit or blocked', 0x48: 'Wait until hit or landed',
    0x49: 'Restart program', 0x4A: 'Restart program if Result', 0x4B: 'Restart program if not Result',
    0x4C: 'Text flags', 0x4D: 'Text auto advance', 0x4E: 'Debug flag', 0x4F: 'Debug text auto advance',
    0x50: 'Menu animation mode', 0x51: 'Text hold',
    0x52: 'Use activated warp portal',
    0x53: 'Change map (map, x, y, z, effect, sound)',
    0x54: 'Add tile walk/ground bits', 0x55: 'Remove tile walk/ground bits',
    0x56: 'Apply map tile copy n', 0x57: 'Jump by Alundra facing (4 offsets)', 0x58: 'Jump by own facing (4 offsets)',
    0x59: 'Set animation of selected', 0x5A: 'Set direction of selected', 0x5B: 'Set animation + direction of selected',
    0x5C: 'Show message spoken by selected entity',
    0x5D: 'Deactivate selected', 0x5E: 'Set vertical force of selected',
    0x5F: 'Wait for animation count / frames / distance',
    0x60: 'Result = selected stands on this', 0x61: 'Result = this stands on selected',
    0x62: 'Set entity flags of selected', 0x63: 'Clear entity flags of selected',
    0x64: 'Place selected at pixel x,y,z', 0x65: 'Move selected by pixels',
    0x66: 'Copy logic state and jump',
    0x67: 'Camera follows selected', 0x68: 'Camera stops following', 0x69: 'Camera looks at point',
    0x6A: 'Remember position', 0x6B: 'Result = moved n in X', 0x6C: 'Result = moved n in Y', 0x6D: 'Result = moved n in Z',
    0x6E: 'Result = blocked', 0x6F: 'Result = landed on something', 0x70: 'Result = on ground', 0x71: 'Result = hit count',
    0x72: 'Remember animation/direction', 0x73: 'Loop counter = n', 0x74: 'Loop: decrement and jump while > 0',
    0x75: 'Play sound', 0x76: 'Halt', 0x77: 'Halt',
    0x78: 'Call local routine', 0x79: 'Call if Result', 0x7A: 'Call if not Result',
    0x7B: 'Call if flag set', 0x7C: 'Call if flag clear',
    0x7D: 'Return', 0x7E: 'Return if Result', 0x7F: 'Return if not Result',
    0x80: 'Return if flag set', 0x81: 'Return if flag clear',
    0x82: 'Give item (Result = success)', 0x83: 'Result = have n of item', 0x84: 'Use item (Result = had it)',
    0x85: 'Copy map area (x,y,w,h to x,y)', 0x86: 'Set damage timer of selected',
    0x87: 'Result = selected touched by attack element', 0x88: 'Set status of selected',
    0x89: 'Place selected relative to another', 0x8A: 'Spawn template at pixel x,y,z', 0x8B: 'Spawn template relative to selected',
    0x8C: 'Result = random (chance n/256 of 0)', 0x8D: 'Result = selected on ground',
    0x8E: 'Scroll background', 0x8F: 'Stop background scroll',
    0x90: 'Spawn map effect', 0x91: 'Remove map effect', 0x92: 'Map effect animation',
    0x93: 'Map effect position', 0x94: 'Map effect force', 0x95: 'Result = attack of element inside box',
    0x96: 'Heal selected (amount = the selector byte)', 0x97: 'Add magic (clamped to max)', 0x98: 'Add gilder', 0x99: 'Pay gilder (Result = could pay)', 0x9A: 'Result = have gilder',
    0x9B: 'Disable warps', 0x9C: 'Enable warps', 0x9E: 'Result = count of raised tiles in area', 0x9F: 'Result = chest of selected already opened',
    0xA0: 'Move map effect', 0xA1: 'Map effect at Alundra', 0xA2: 'Spawn map effect at x,y,z', 0xA3: 'Spawn map effect at selected',
    0xA4: 'Scrolling mode', 0xA5: 'Stop all sound', 0xA6: 'Load music', 0xA7: 'Music control', 0xA8: 'Result = sound loading',
    0xA9: 'Result = bumped into selected', 0xAA: 'Result = selected bumped into this', 0xAB: 'Play sound with tone/volume',
    0xAC: 'Shadow size of selected', 0xAD: 'Result = selected inside box around another',
    0xAF: 'Fade to colour', 0xB0: 'Warp fade colour', 0xB1: 'Result = fade finished', 0xB2: 'Result = groups share an entity',
    0xB4: 'Result = selected rising', 0xB5: 'Result = selected falling', 0xB6: 'Result = selected vertical force 0',
    0xB7: 'Result = target animation is n', 0xB8: 'Result = current animation is n',
    0xB9: 'Start CD stream (movie/voice)', 0xBA: 'Result = CD stream busy', 0xBB: 'Game over / retry',
    0xBC: 'Raise max life', 0xBD: 'Play sound (16-bit id)', 0xBE: 'Play sound (16-bit id)', 0xBF: 'Play sound with tone/volume',
    0xC0: 'Force weapon', 0xC1: 'Release forced weapon', 0xC2: 'Result = save slot', 0xC3: 'Restore life and magic',
    0xC4: 'Show message with chosen speaker',
    0xB3: 'Simulate pad buttons (held, pressed, released, repeat)',
    0xE9: 'Editor custom AI: Result = Alundra within range',
    0xFF: 'End program',
}


def s16(lo, hi):
    v = lo | hi << 8
    return v - 0x10000 if v & 0x8000 else v


class ProgState:
    def __init__(self, code, start):
        self.code = code; self.ci = start; self.params = [start, 0, 0, 0, 0, 0, 0, 0]
        self.result = 0; self.r30 = 0; self.r34 = 0; self.ended = False


class _MemCode:
    """A program in the game's memory (the global block): instructions read at their address,
    as many bytes as the opcode's length (12 when it is not known; the handlers return their own)."""
    _SIZES = None

    def __init__(self, mem): self.m = mem

    def get(self, a, default=None):
        if _MemCode._SIZES is None:
            from pathlib import Path
            import json
            f = Path(__file__).resolve().parent.parent / 'extractor' / 'data' / 'event-instruction-lengths.json'
            try: _MemCode._SIZES = {int(k): v for k, v in json.loads(f.read_text())['sizes'].items()}
            except (OSError, ValueError, KeyError): _MemCode._SIZES = {0: 1}
        b = self.m.b; a &= 0x1FFFFF
        if a >= len(b): return default
        op = b[a]
        return (op, bytes(b[a:a + (_MemCode._SIZES.get(op) or 12)]), None)


class VM:
    def __init__(self, game):
        self.g = game; self.trace = None
        self.unknown = game.unknown_ops

    # ---- program lookup
    def make_state(self, slot, hook):
        mp = self.g.map
        if not hook or hook == 0xFF: return None
        if not hook & 0x80: return self.global_state(slot, hook)
        key = f'{slot} {hook - 128}'
        code = mp.scripts.get(key)
        if not code: return None
        return ProgState(getattr(mp, 'code', None) or code, mp.roots[key])   # the map's whole block

    def global_state(self, slot, hook):
        """0x80042A40 with hook < 0x80: the shared info struct 0x801F3958, start = *(+0x30) +
        u16 (*(+0x34 + 4 * slot))[hook & 0x7F], read from the game's memory as the game does."""
        m = self.g.mem; info = 0x801F3958
        base = m.u32(info + 0x30)
        if not base: return None                                   # (no global_info.bin loaded)
        tab = m.u32(info + 0x34 + 4 * SLOTS.index(slot))
        start = (base + m.u16(tab + 2 * (hook & 0x7F))) & 0xFFFFFFFF
        return ProgState(_MemCode(m), start)

    def note(self, what):
        self.unknown[what] = self.unknown.get(what, 0) + 1

    # run (0x80042BB8) and select (0x8003D374) are set by _install_game_ops below


# ======================================================== the handlers ==
HANDLERS = {}


def op(*codes):
    def deco(fn):
        for c in codes: HANDLERS[c] = fn
        return fn
    return deco


@op(0xE9)
def _range(vm, lg, ow, v, st, row):
    p = vm.g.player
    st.result = int(math.hypot(p.wx - lg.wx, p.wy - lg.wy) <= v[1] * 8); return 3   # GUESS on unit (editor op)


# ---------------------------------------------------------------- the game's own handlers --
# vm_game_*.py: every game opcode, written from the US ALUN_CD.EXE handlers (research/us_decomp/vm_ops),
# the entity selection 0x8003D374 and the run loop 0x80042BB8.
def _install_game_ops():
    import sys as _sys
    me = _sys.modules[__name__]
    import vm_game_00, vm_game_30, vm_game_60, vm_game_80, vm_game_A0   # noqa: F401 (60/80/A0 register on import)
    vm_game_00.install(me)
    vm_game_30.install(me)
    for m in (vm_game_60, vm_game_80, vm_game_A0):
        inst = getattr(m, 'install', None)
        if inst: inst(me)
    import vm_game_rest
    vm_game_rest.install(me)                     # the remaining opcodes, written from the US handlers


_install_game_ops()
