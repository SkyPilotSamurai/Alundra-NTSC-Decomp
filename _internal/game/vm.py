"""Alundra event script machine (remake).

A port of the game's event interpreter (ALUN_CD.EXE 0x80041xxx, as decoded in
the MIT xcasadio AlundraEngine EntityEventHandlers.cs) onto the remake's
actors.  Where that reference has no answer the closest sensible behaviour is
used and marked GUESS so it can be checked against the real game.

Model (same as the game):
* every handler returns a byte delta; 0 = yield (retry this instruction next
  frame), opcode 00 = stop for this frame and continue after it next frame,
  FF = program ended.
* Parameters[1] holds the code index a waiting instruction started on, so it
  can tell "first time" from "still waiting".
* logic = the entity commands act on ("logic context"), owner = the entity
  that runs the program.  Selector bytes: <0x80 template number, 0x80 the
  logic entity, 0x81 Alundra, 0x82 every live entity.
"""
import math, random

TW, TH = 24, 16
CARDINAL = (0, 16, 8, 24)        # g_cardinalDirectionTable: down, up, left, right (matches walk routes on map 389)
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


def dir_to(dx, dy):
    """GetDirectionToTarget: 32 directions, 0 down, 8 left, 16 up, 24 right."""
    if dx == 0 and dy == 0: return 0
    return int(round(math.atan2(-dx, dy) / (2 * math.pi) * 32)) & 31


def dir_vec(d):
    a = (d & 31) / 32 * 2 * math.pi
    return -math.sin(a), math.cos(a)


class ProgState:
    def __init__(self, code, start):
        self.code = code; self.ci = start; self.params = [start, 0, 0, 0, 0, 0, 0, 0]
        self.result = 0; self.r30 = 0; self.r34 = 0; self.ended = False


class VM:
    def __init__(self, game):
        self.g = game; self.trace = None
        self.unknown = game.unknown_ops

    # ---- program lookup
    def make_state(self, slot, hook):
        mp = self.g.map
        if not hook or not hook & 0x80 or hook == 0xFF: return None   # GUESS: global (<0x80) programs not exported
        key = f'{slot} {hook - 128}'
        code = mp.scripts.get(key)
        if not code: return None
        return ProgState(getattr(mp, 'code', None) or code, mp.roots[key])   # the map's whole block

    # ---- entity selection (GetMatchingEntityBySearchType)
    def select(self, logic, sel):
        g = self.g
        if not sel & 0x80:
            return [a for a in g.actors if a.ref_id == sel and a.alive]
        f = sel & 0x7F
        if f == 0: return [logic] if logic else []
        if f == 1: return [g.player]
        live = [a for a in g.actors if a.alive]
        if f == 2: return [g.player] + live
        if f == 3: return live
        if f == 4: return [a for a in [g.player] + live if a.solid and a.visible]
        if f == 5: return [a for a in live if logic.riding is a]
        if f == 6: return [a for a in live if a.riding is logic]
        if f == 7: return [a for a in live if logic.bumped is a]
        if f == 8: return [a for a in live if a.bumped is logic]
        if f == 9: return [a for a in live if a.parent is logic]
        if f == 10: return [a for a in live if logic.parent is a]
        if f == 11: return []          # nothing rides moving platforms yet
        self.note(f'selector {sel:02X}')
        return []

    def note(self, what):
        self.unknown[what] = self.unknown.get(what, 0) + 1

    def resolve_dir(self, e, enc):
        r = enc & 31; mode = enc >> 5
        if mode == 0: return r
        if mode == 1: return (e.target_dir + r) & 31
        if mode == 2: return CARDINAL[enc & 3]
        if mode == 3:
            p = self.g.player
            return (dir_to(p.wx - e.wx, p.wy - e.wy) + enc) & 31
        self.note(f'direction mode {mode}')
        return r

    # ---- run one program slot of an entity for this frame
    def run(self, owner, slot, st, logic=None, budget=600):
        """Runs until it yields.  Returns False once the program has ended."""
        if st is None or st.ended: return False
        self.cur_owner = owner; self.cur_slot = slot; self.clear = False
        while budget > 0:
            budget -= 1
            ins = st.code.get(st.ci)
            if ins is None: st.ended = True; return False
            op, raw, row = ins
            if op == 0xFF: st.ended = True; return False
            if op == 0x00:
                st.params[1] = 0; st.ci += len(raw) if raw else 1; return True
            v = list(raw) + [0] * (12 - len(raw))
            lg = owner.logic_ctx or owner if logic is None else logic
            h = HANDLERS.get(op)
            if h is None:
                self.note(f'{op:02X}')
                d = len(raw) or 1
            else:
                d = h(self, lg, owner, v, st, row)
            if self.trace is not None: self.trace.append((slot, st.ci, op, d))
            if self.clear:
                self.clear = False
                if lg is owner: return 'restart'
            if d == 0: return True
            st.params[1] = 0; st.ci += d
        return True


# ======================================================== the handlers ==
HANDLERS = {}


def op(*codes):
    def deco(fn):
        for c in codes: HANDLERS[c] = fn
        return fn
    return deco


def flagno(v): return v[1] | v[2] << 8


@op(0x01, 0x13, 0x18)
def _nop(vm, lg, ow, v, st, row): return 1

@op(0x14, 0x76, 0x77)
def _halt(vm, lg, ow, v, st, row): return 0

@op(0x02)
def _jmp(vm, lg, ow, v, st, row): return s16(v[1], v[2])

@op(0x03)
def _jt(vm, lg, ow, v, st, row): return s16(v[1], v[2]) if st.result else 3

@op(0x04)
def _jf(vm, lg, ow, v, st, row): return s16(v[1], v[2]) if not st.result else 3

@op(0x05)
def _setf(vm, lg, ow, v, st, row): vm.g.set_flag(flagno(v), True); return 3

@op(0x06)
def _clrf(vm, lg, ow, v, st, row): vm.g.set_flag(flagno(v), False); return 3

@op(0x32)
def _xorf(vm, lg, ow, v, st, row): n = flagno(v); vm.g.set_flag(n, not vm.g.flag(n)); return 3

@op(0x30)
def _jfs(vm, lg, ow, v, st, row): return s16(v[3], v[4]) if vm.g.flag(flagno(v)) else 5

@op(0x31)
def _jfc(vm, lg, ow, v, st, row): return s16(v[3], v[4]) if not vm.g.flag(flagno(v)) else 5

@op(0x33)
def _all4(vm, lg, ow, v, st, row):
    st.result = int(all(vm.g.flag(v[i * 2 + 1] | v[i * 2 + 2] << 8) for i in range(4))); return 9

@op(0x34)
def _none4(vm, lg, ow, v, st, row):
    st.result = int(not any(vm.g.flag(v[i * 2 + 1] | v[i * 2 + 2] << 8) for i in range(4))); return 9

@op(0x35)
def _wclr(vm, lg, ow, v, st, row): return 3 if not vm.g.flag(flagno(v)) else 0

@op(0x36)
def _wset(vm, lg, ow, v, st, row): return 3 if vm.g.flag(flagno(v)) else 0

def in_box(e, x1, x2, y1, y2, z1, z2):
    tx, ty, tz = e.tile()
    return x1 <= tx <= x2 and y1 <= ty <= y2 and z1 <= tz <= z2

@op(0x07)
def _boxsel(vm, lg, ow, v, st, row):
    st.result = int(any(in_box(e, *v[2:8]) for e in vm.select(lg, v[1]))); return 8

@op(0x3B)
def _pbox(vm, lg, ow, v, st, row): st.result = int(in_box(vm.g.player, *v[1:7])); return 7

@op(0x3C, 0x3D)
def _ebox(vm, lg, ow, v, st, row):
    st.result = int(any(in_box(e, *v[1:7]) for e in vm.g.actors if e.alive)); return 7

@op(0x08)
def _turn(vm, lg, ow, v, st, row): lg.target_dir = (lg.target_dir + v[1]) & 31; return 2

@op(0x09)
def _face(vm, lg, ow, v, st, row): lg.target_dir = v[1] & 31; return 2

@op(0x0A)
def _about(vm, lg, ow, v, st, row): lg.target_dir = (lg.target_dir + 16) & 31; return 1

@op(0x0C)
def _rnddir(vm, lg, ow, v, st, row): lg.target_dir = random.choice(CARDINAL); return 1

@op(0x3A)
def _card(vm, lg, ow, v, st, row): lg.target_dir = CARDINAL[v[1] & 3]; return 2

@op(0x27)
def _faceP(vm, lg, ow, v, st, row):
    p = vm.g.player; lg.target_dir = dir_to(p.wx - lg.wx, p.wy - lg.wy); return 1

def first_time(st):
    if st.params[1] != st.ci:
        st.params[1] = st.ci; return True
    return False

def moved_beyond(lg, st, thr):
    if first_time(st):
        st.params[2], st.params[3] = lg.wx, lg.wy; return None
    return thr <= abs(st.params[2] - lg.wx) or thr <= abs(st.params[3] - lg.wy)

@op(0x0B)
def _walk(vm, lg, ow, v, st, row):
    lg.target_anim = v[1]
    r = moved_beyond(lg, st, v[2] | v[3] << 8)
    return 4 if r else 0

@op(0x1E)
def _wmove(vm, lg, ow, v, st, row):
    r = moved_beyond(lg, st, v[1] | v[2] << 8); return 3 if r else 0

@op(0x1F)
def _wmoveb(vm, lg, ow, v, st, row):
    r = moved_beyond(lg, st, v[1] | v[2] << 8)
    return 3 if r or (r is not None and lg.force_adjusted) else 0

def anim_count(lg, st, n):
    if first_time(st):
        st.params[2] = 0; lg.anim_complete = 0; return False
    if lg.anim_complete:
        st.params[2] += 1; lg.anim_complete = 0
    return st.params[2] >= n

@op(0x1C)
def _wanim(vm, lg, ow, v, st, row): return 2 if anim_count(lg, st, v[1]) else 0

@op(0x1D)
def _wanimb(vm, lg, ow, v, st, row):
    first = st.params[1] != st.ci
    r = anim_count(lg, st, v[1])
    return 2 if r or (not first and lg.force_adjusted) else 0

@op(0x20, 0x21)
def _wz(vm, lg, ow, v, st, row):
    if first_time(st): st.params[2] = lg.z; return 0
    if abs(st.params[2] - lg.z) >= (v[1] | v[2] << 8): return 3
    if row and v[0] == 0x21 and lg.collided_z: return 3
    return 0

@op(0x22, 0x23)
def _tozrec(vm, lg, ow, v, st, row):
    if first_time(st):
        st.params[2] = (lg.record['z'] * 8) if lg.record else lg.z; return 0
    if abs(st.params[2] - lg.z) < 0.5: return 1
    dz = st.params[2] - lg.z                          # Script_34_022: ForceZ limited to what is left
    if (dz <= 0 and lg.vz < dz) or (dz > 0 and dz < lg.vz): lg.vz = dz
    if v[0] == 0x23 and lg.collided_z: return 1
    return 0

@op(0x24)
def _wblk(vm, lg, ow, v, st, row): return 1 if lg.force_adjusted else 0

@op(0x25)
def _wgnd(vm, lg, ow, v, st, row): return 1 if lg.collided_z or lg.on_ground else 0

@op(0x26)
def _wblkz(vm, lg, ow, v, st, row): return 1 if lg.force_adjusted or lg.collided_z else 0

@op(0x47)
def _whit(vm, lg, ow, v, st, row): return 1 if lg.hit_counter or lg.force_adjusted else 0

@op(0x48)
def _whitz(vm, lg, ow, v, st, row): return 1 if lg.hit_counter or lg.collided_z else 0

@op(0x37)
def _wait(vm, lg, ow, v, st, row):
    if first_time(st): st.params[2] = 0; return 0
    st.params[2] += 1
    return 2 if st.params[2] - 1 >= v[1] else 0

@op(0x10)
def _lock(vm, lg, ow, v, st, row): vm.g.player_locked = True; return 1

@op(0x11)
def _unlock(vm, lg, ow, v, st, row): vm.g.player_locked = False; return 1

@op(0x12, 0x75)
def _sfx8(vm, lg, ow, v, st, row): vm.g.sound(v[1]); return 2

@op(0xBD, 0xBE)
def _sfx16(vm, lg, ow, v, st, row): vm.g.sound(v[1] | v[2] << 8); return 3

@op(0xBF)
def _sfxmix(vm, lg, ow, v, st, row): vm.g.sound(v[1] | v[2] << 8); return 5

@op(0xAB)
def _sfxmix2(vm, lg, ow, v, st, row): vm.g.sound(v[1]); return 4

@op(0xA5)
def _stopsnd(vm, lg, ow, v, st, row): return 1

@op(0xA6)
def _bgm(vm, lg, ow, v, st, row): vm.g.play_music(v[1]); return 2

@op(0xA7)
def _bgmc(vm, lg, ow, v, st, row): return 3

@op(0xA8)
def _sndload(vm, lg, ow, v, st, row): st.result = 0; return 1

@op(0xB9)
def _cd(vm, lg, ow, v, st, row): return 2

@op(0xBA)
def _cdbusy(vm, lg, ow, v, st, row): st.result = 0; return 1

@op(0x15)
def _recz(vm, lg, ow, v, st, row):
    if lg.record: lg.z = lg.record['z'] * 8
    return 1

@op(0x16)
def _grav(vm, lg, ow, v, st, row): lg.flags |= 0x100; return 1

@op(0x17)
def _nograv(vm, lg, ow, v, st, row): lg.flags &= ~0x100; return 1

@op(0x19)
def _deact(vm, lg, ow, v, st, row): lg.deactivate(); return 1

@op(0x1A)
def _anim(vm, lg, ow, v, st, row): lg.target_anim = v[1]; return 2

def force_from(lo, hi): return s16(lo, hi) / 256.0   # (v<<16)>>8 in 16.16 = v/256 px per frame

@op(0x1B)
def _fz(vm, lg, ow, v, st, row): lg.vz = force_from(v[1], v[2]); return 3

@op(0x5E)
def _fzsel(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.vz = force_from(v[2], v[3])
    return 4

@op(0x28)
def _sb(vm, lg, ow, v, st, row): lg.flags |= 8; return 1

@op(0x29)
def _cb(vm, lg, ow, v, st, row): lg.flags &= ~8; return 1

@op(0x2A)
def _sa(vm, lg, ow, v, st, row): lg.flags |= 1; return 1

@op(0x2B)
def _ca(vm, lg, ow, v, st, row): lg.flags &= ~1; return 1

@op(0x45)
def _slide(vm, lg, ow, v, st, row): lg.flags &= ~0x2000; return 1

@op(0x46)
def _noslide(vm, lg, ow, v, st, row): lg.flags |= 0x2000; return 1

@op(0x62)
def _setef(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.flags |= v[2] | v[3] << 8
    return 4

@op(0x63)
def _clref(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.flags &= ~(v[2] | v[3] << 8)
    return 4

@op(0x2C)
def _none(vm, lg, ow, v, st, row): st.result = int(not vm.select(lg, v[1])); return 2

@op(0x2D)
def _spawn(vm, lg, ow, v, st, row): vm.g.spawn(v[1]); return 2

@op(0x8A)
def _spawnat(vm, lg, ow, v, st, row):
    e = vm.g.spawn(v[1])
    if e:                                     # InitializeEntity: PosZ = z - ModZ + 1
        e.px, e.py = (v[2] | v[3] << 8) << 16, (v[4] | v[5] << 8) << 16
        e.pz = ((v[6] | v[7] << 8) << 16) - e.modz + 1
    return 8

@op(0x8B)
def _spawnrel(vm, lg, ow, v, st, row):
    e = vm.g.spawn(v[2]); ref = vm.select(lg, v[1])
    if e and ref:
        r = ref[0]; e.wx = r.wx + s16(v[3], v[4]); e.wy = r.wy + s16(v[5], v[6]); e.z = r.z + s16(v[7], v[8])
    return 9

@op(0x2E)
def _destroy(vm, lg, ow, v, st, row):
    sel = vm.select(lg, v[1]); st.result = 0
    for e in sel:
        if e is not vm.g.player: e.set_status(4); st.result = 1
    return 2

@op(0x2F)
def _pad(vm, lg, ow, v, st, row):
    st.result = int(bool(vm.g.pad(v[3]) & (v[1] | v[2] << 8))); return 4

@op(0x38)
def _remap(vm, lg, ow, v, st, row): return 5

@op(0x0D)
def _msg(vm, lg, ow, v, st, row):
    return 3 if vm.g.open_message(row, lg) else 0

@op(0x5C)
def _msgsel(vm, lg, ow, v, st, row):
    sp = vm.select(lg, v[1])
    return 4 if vm.g.open_message(row, sp[0] if sp else None) else 0

@op(0xC4)
def _msgc4(vm, lg, ow, v, st, row):
    sp = vm.select(lg, v[1])
    return 6 if vm.g.open_message(row, sp[0] if sp else None) else 0

@op(0x39)
def _wmsg(vm, lg, ow, v, st, row): return 1 if vm.g.dialogue is None else 0

@op(0x44)
def _yesno(vm, lg, ow, v, st, row):
    g = vm.g
    if st.params[1] == st.ci:
        if g.choice_result:
            st.result = int(g.choice_result == 1); return 1
        return 0
    if g.dialogue is not None and not g.choice: return 0
    g.choice_result = 0; g.choice = True; st.params[1] = st.ci
    return 0

@op(0x4C, 0x4E)
def _txtf(vm, lg, ow, v, st, row): return 2

@op(0x4D, 0x4F, 0x51)
def _txt1(vm, lg, ow, v, st, row): return 1

@op(0x50)
def _etc(vm, lg, ow, v, st, row): return 2

@op(0x3E)
def _ridesP(vm, lg, ow, v, st, row): st.result = int(vm.g.player.riding is lg); return 1

@op(0x3F)
def _anyrides(vm, lg, ow, v, st, row):
    st.result = int(any(e.riding is lg for e in vm.g.actors + [vm.g.player])); return 1

@op(0x60)
def _selrides(vm, lg, ow, v, st, row): st.result = int(any(e.riding is lg for e in vm.select(lg, v[1]))); return 2

@op(0x61)
def _ridesel(vm, lg, ow, v, st, row): st.result = int(lg.riding in vm.select(lg, v[1])); return 2

@op(0x40)
def _setprog(vm, lg, ow, v, st, row):
    slot = SLOTS[v[1]] if v[1] < 6 else None
    if slot:
        lg.programs[slot] = v[2]; lg.states[slot] = None
        if lg is ow and slot == vm.cur_slot: vm.clear = True
    return 3

@op(0x41)
def _setsprog(vm, lg, ow, v, st, row): return 3

@op(0x42)
def _ctxP(vm, lg, ow, v, st, row): ow.logic_ctx = vm.g.player; return 1

@op(0x43)
def _ctx(vm, lg, ow, v, st, row):
    sel = vm.select(lg, v[1])
    if sel: ow.logic_ctx = sel[-1]; st.result = 1
    else: st.result = 0
    return 2

@op(0x49)
def _restart(vm, lg, ow, v, st, row): return st.params[0] - st.ci

@op(0x4A)
def _restartT(vm, lg, ow, v, st, row): return st.params[0] - st.ci if st.result else 1

@op(0x4B)
def _restartF(vm, lg, ow, v, st, row): return st.params[0] - st.ci if not st.result else 1

@op(0x52)
def _portal(vm, lg, ow, v, st, row): st.result = 0; return 1

@op(0x53)
def _warp(vm, lg, ow, v, st, row):
    g = vm.g; m = v[1] | v[2] << 8
    x, y, z = v[3] * TW + TW // 2, v[4] * TH + TH // 2, v[5] * 16
    if v[6] == 3 and m == g.map.id:
        g.player.wx, g.player.wy, g.player.z = x, y, z; return 8
    g.warp(m, x, y, z); return 8

@op(0x54)
def _tileor(vm, lg, ow, v, st, row):
    c = vm.g.map.cell(min(v[1], 0x33), min(v[2], 0x3B))
    if c: c[0] |= v[3]; c[1] |= v[4]
    return 5

@op(0x55)
def _tileand(vm, lg, ow, v, st, row):
    c = vm.g.map.cell(min(v[1], 0x33), min(v[2], 0x3B))
    if c: c[0] &= ~v[3] & 0xFF; c[1] &= ~v[4] & 0xFF
    return 5

@op(0x56)
def _mapcopy(vm, lg, ow, v, st, row): vm.g.map.apply_copy(v[1]); return 2

@op(0x85)
def _areacopy(vm, lg, ow, v, st, row): vm.g.map.copy_area(*v[1:7]); return 7

@op(0x57)
def _jpdir(vm, lg, ow, v, st, row):
    d = vm.g.player.anim_dir(); return s16(v[d * 2 + 1], v[d * 2 + 2])

@op(0x58)
def _jodir(vm, lg, ow, v, st, row):
    d = lg.anim_dir(); return s16(v[d * 2 + 1], v[d * 2 + 2])

@op(0x59)
def _selanim(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.target_anim = v[2]
    return 3

@op(0x5A)
def _seldir(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.target_dir = vm.resolve_dir(e, v[2])
    return 3

@op(0x5B)
def _selanimdir(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.target_anim = v[2]; e.target_dir = vm.resolve_dir(e, v[3])
    return 4

@op(0x5D)
def _seldeact(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.deactivate()
    return 2

@op(0x5F)
def _wcombo(vm, lg, ow, v, st, row):
    e = ow
    if first_time(st):
        st.params[2:7] = [e.wx, e.wy, e.z, 0, 0]; e.anim_complete = 0; return 0
    if e.anim_complete: st.params[5] += 1; e.anim_complete = 0
    st.params[6] += 1
    if st.params[5] < v[4] or st.params[6] < v[5]: return 0
    if v[6] & 1 and not e.force_adjusted: return 0
    if v[6] & 2 and not e.collided_z: return 0
    if v[6] & 4 and not (e.on_ground and e.hit_counter): return 0
    if abs(st.params[2] - e.wx) < v[1] * 24: return 0
    if abs(st.params[3] - e.wy) < v[2] * 16: return 0
    return 8 if abs(st.params[4] - e.z) >= v[3] * 16 else 0

@op(0x64)
def _place(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.wx, e.wy, e.z = v[2] | v[3] << 8, v[4] | v[5] << 8, v[6] | v[7] << 8
    return 8

@op(0x65)
def _nudge(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]): e.wx += s16(v[2], v[3]); e.wy += s16(v[4], v[5]); e.z += s16(v[6], v[7])
    return 8

@op(0x89)
def _placerel(vm, lg, ow, v, st, row):
    ref = vm.select(lg, v[1])
    if ref:
        r = ref[0]
        for e in vm.select(lg, v[2]): e.wx = r.wx + s16(v[3], v[4]); e.wy = r.wy + s16(v[5], v[6]); e.z = r.z + s16(v[7], v[8])
    return 9

@op(0x66)
def _copyctx(vm, lg, ow, v, st, row):
    vm.note('66'); return 3

@op(0x67)
def _cam(vm, lg, ow, v, st, row):
    sel = vm.select(lg, v[1]); vm.g.camera_follow = sel[0] if sel else None; return 2

@op(0x68)
def _camoff(vm, lg, ow, v, st, row): vm.g.camera_follow = False; return 1

@op(0x69)
def _camat(vm, lg, ow, v, st, row):
    vm.g.camera_follow = False; vm.g.camera_at = (v[1] | v[2] << 8, v[3] | v[4] << 8, v[5] | v[6] << 8); return 7

@op(0x6A)
def _rempos(vm, lg, ow, v, st, row): st.params[2:5] = [lg.wx, lg.wy, lg.z]; return 1

@op(0x6B)
def _mx(vm, lg, ow, v, st, row): st.result = int(abs(st.params[2] - lg.wx) >= (v[1] | v[2] << 8)); return 3

@op(0x6C)
def _my(vm, lg, ow, v, st, row): st.result = int(abs(st.params[3] - lg.wy) >= (v[1] | v[2] << 8)); return 3

@op(0x6D)
def _mz(vm, lg, ow, v, st, row): st.result = int(abs(st.params[4] - lg.z) >= (v[1] | v[2] << 8)); return 3

@op(0x6E)
def _rblk(vm, lg, ow, v, st, row): st.result = int(lg.force_adjusted); return 1

@op(0x6F)
def _rcz(vm, lg, ow, v, st, row): st.result = int(lg.collided_z); return 1

@op(0x70)
def _rgnd(vm, lg, ow, v, st, row): st.result = int(lg.on_ground); return 1

@op(0x71)
def _rhit(vm, lg, ow, v, st, row): st.result = lg.hit_counter; return 1

@op(0x72)
def _remember(vm, lg, ow, v, st, row): lg.last_anim, lg.last_dir = lg.target_anim, lg.target_dir; return 1

@op(0x73)
def _loopn(vm, lg, ow, v, st, row): st.r30 = v[1]; return 2

@op(0x74)
def _loop(vm, lg, ow, v, st, row):
    st.r30 -= 1
    return 3 if st.r30 < 1 else s16(v[1], v[2])

@op(0x78)
def _call(vm, lg, ow, v, st, row): st.r34 = st.ci + 3; return s16(v[1], v[2])

@op(0x79)
def _callT(vm, lg, ow, v, st, row):
    if st.result: st.r34 = st.ci + 3; return s16(v[1], v[2])
    return 3

@op(0x7A)
def _callF(vm, lg, ow, v, st, row):
    if not st.result: st.r34 = st.ci + 3; return s16(v[1], v[2])
    return 3

@op(0x7B)
def _callFS(vm, lg, ow, v, st, row):
    if vm.g.flag(flagno(v)): st.r34 = st.ci + 5; return s16(v[3], v[4])
    return 5

@op(0x7C)
def _callFC(vm, lg, ow, v, st, row):
    if not vm.g.flag(flagno(v)): st.r34 = st.ci + 5; return s16(v[3], v[4])
    return 5

@op(0x7D)
def _ret(vm, lg, ow, v, st, row): return st.r34 - st.ci

@op(0x7E)
def _retT(vm, lg, ow, v, st, row): return st.r34 - st.ci if st.result else 1

@op(0x7F)
def _retF(vm, lg, ow, v, st, row): return st.r34 - st.ci if not st.result else 1

@op(0x80)
def _retFS(vm, lg, ow, v, st, row): return st.r34 - st.ci if vm.g.flag(flagno(v)) else 3

@op(0x81)
def _retFC(vm, lg, ow, v, st, row): return st.r34 - st.ci if not vm.g.flag(flagno(v)) else 3

@op(0x82)
def _give(vm, lg, ow, v, st, row): st.result = int(vm.g.give_item(v[1])); return 2

@op(0x83)
def _haveN(vm, lg, ow, v, st, row): st.result = int(vm.g.inventory.get(v[1], 0) >= v[2]); return 3

@op(0x84)
def _use(vm, lg, ow, v, st, row):
    inv = vm.g.inventory
    if inv.get(v[1], 0) > 0: inv[v[1]] -= 1; st.result = 1
    else: st.result = 0
    return 2

@op(0x86)
def _dmgtimer(vm, lg, ow, v, st, row): return 4

@op(0x87)
def _elemhit(vm, lg, ow, v, st, row): st.result = 0; return 3      # needs combat

@op(0x95)
def _elembox(vm, lg, ow, v, st, row): st.result = 0; return 10     # needs combat

@op(0x88)
def _status(vm, lg, ow, v, st, row):
    for e in vm.select(lg, v[1]):                 # 0x80040C04: status from the table 0x80023D2C = 2, 3, 4
        if v[2] == 0: e.activate()
        elif v[2] == 1: e.deactivate()
        elif v[2] == 2: e.set_status(4)
    return 3

@op(0x8C)
def _rand(vm, lg, ow, v, st, row): st.result = 0 if random.randrange(256) < v[1] else 1; return 2

@op(0x8D)
def _selgnd(vm, lg, ow, v, st, row): st.result = int(any(e.on_ground for e in vm.select(lg, v[1]))); return 2

@op(0x8E)
def _scroll(vm, lg, ow, v, st, row):
    """0x80041034: screen shake on (step x, step y, limit x, limit y)."""
    m = vm.g.mem; S = 0x801F94D0
    m.w32(S, 1); m.w32(S + 0xC, v[1]); m.w32(S + 0x10, v[2]); m.w32(S + 4, v[3]); m.w32(S + 8, v[4]); return 5

@op(0x8F)
def _scrolloff(vm, lg, ow, v, st, row): vm.g.mem.w32(0x801F94D0, 0); return 1

def _w16(v, i):
    """unsigned 16-bit value << 16 as the game's 32-bit register (wraps to negative)."""
    x = ((v[i + 1] << 8) | v[i]) << 16
    return x - (1 << 32) if x & 0x80000000 else x


@op(0x90)
def _fx(vm, lg, ow, v, st, row): vm.g.effect(v[1]); return 2


@op(0x91)
def _fxoff(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): e.dead = True
    return 2


@op(0x92)
def _fxanim(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): vm.g.effects.set_anim(e, v[2])
    return 3


@op(0x93)
def _fxpos(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): e.x, e.y, e.z = _w16(v, 2), _w16(v, 4), _w16(v, 6)
    return 8


@op(0x94)
def _fxforce(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): e.vx, e.vy, e.vz = _w16(v, 2), _w16(v, 4), _w16(v, 6)
    return 8


@op(0xA0)
def _fxmove(vm, lg, ow, v, st, row):
    for e in vm.g.effects.by_id(v[1]): e.x += _w16(v, 2); e.y += _w16(v, 4); e.z += _w16(v, 6)
    return 8


@op(0xA1)
def _fxP(vm, lg, ow, v, st, row):
    if vm.select(lg, v[2]):
        p = vm.g.player
        for e in vm.g.effects.by_id(v[1]): e.x, e.y, e.z = p.px + _w16(v, 3), p.py + _w16(v, 5), p.pz + _w16(v, 7)
    return 9


@op(0xA2)
def _fxat(vm, lg, ow, v, st, row):
    e = vm.g.effect(v[1])
    if e is not None: e.x, e.y, e.z = _w16(v, 2), _w16(v, 4), _w16(v, 6) + 1
    return 8


@op(0xA3)
def _fxsel(vm, lg, ow, v, st, row):
    sel = vm.select(lg, v[2])
    if sel:
        t = sel[0]; e = vm.g.effect(v[1])
        if e is not None: e.x, e.y, e.z = t.px + _w16(v, 3), t.py + _w16(v, 5), t.pz + _w16(v, 7)
    return 9


@op(0xA4)
def _scrollmode(vm, lg, ow, v, st, row):
    # SetScrollingMode 0x8005D668: bit 0/1 = draw background layer 0/1 (the map load sets 3)
    ln = getattr(vm.g.map, 'lining', None)
    if ln is not None and ln.ok: ln.mode_mask = v[1]
    return 3

@op(0xA9)
def _bumped(vm, lg, ow, v, st, row): st.result = int(lg.bumped in vm.select(lg, v[1])); return 2

@op(0xAA)
def _bumpedby(vm, lg, ow, v, st, row): st.result = int(any(e.bumped is lg for e in vm.select(lg, v[1]))); return 2

@op(0xAC)
def _shadow(vm, lg, ow, v, st, row): return 4

@op(0xAD)
def _boxaround(vm, lg, ow, v, st, row):
    base = vm.select(lg, v[1]); st.result = 0
    if not base: return 9
    b = base[0]
    sb = lambda x: x - 256 if x > 127 else x
    x0, y0, z0 = b.wx + sb(v[3]) * 24, b.wy + sb(v[4]) * 16, b.z + sb(v[5]) * 16
    x1, y1, z1 = x0 + v[6] * 24, y0 + v[7] * 16, z0 + v[8] * 16
    st.result = int(any(x0 <= e.wx <= x1 and y0 <= e.wy <= y1 and z0 <= e.z <= z1 for e in vm.select(lg, v[2])))
    return 9

@op(0xAF)
def _fade(vm, lg, ow, v, st, row):
    vm.g.start_fade((v[3], v[2], v[1]), v[6] or v[5] or 30, v[4]); return 7

@op(0xB0)
def _wfade(vm, lg, ow, v, st, row): vm.g.start_fade((v[1], v[2], v[3]), v[4] or 30, 1); return 5

@op(0xB1)
def _fadedone(vm, lg, ow, v, st, row): st.result = int(vm.g.fade_frames <= 0); return 1

@op(0xB2)
def _groups(vm, lg, ow, v, st, row):
    a = vm.select(lg, v[1]); b = vm.select(lg, v[2]); st.result = int(any(e in a for e in b)); return 3

@op(0xB4)
def _rising(vm, lg, ow, v, st, row): s = vm.select(lg, v[1]); st.result = int(bool(s) and s[0].vz > 0); return 2

@op(0xB5)
def _falling(vm, lg, ow, v, st, row): s = vm.select(lg, v[1]); st.result = int(bool(s) and s[0].vz < 0); return 2

@op(0xB6)
def _still(vm, lg, ow, v, st, row): s = vm.select(lg, v[1]); st.result = int(bool(s) and s[0].vz == 0); return 2

@op(0xB7)
def _isanim(vm, lg, ow, v, st, row): st.result = int(any(e.target_anim == v[2] for e in vm.select(lg, v[1]))); return 3

@op(0xB8)
def _curanim(vm, lg, ow, v, st, row): st.result = int(any(e.anim.anim == v[2] for e in vm.select(lg, v[1]))); return 3

@op(0xBB)
def _gameover(vm, lg, ow, v, st, row): vm.g.toast('Game over'); return 1

@op(0xBC)
def _maxlife(vm, lg, ow, v, st, row): p = vm.g.player; p.hp_max = min(50, p.hp_max + v[1]); return 2

@op(0xC0)
def _forceweap(vm, lg, ow, v, st, row): return 2

@op(0xC1)
def _relweap(vm, lg, ow, v, st, row): return 1

@op(0xC2)
def _slot(vm, lg, ow, v, st, row): st.result = 1; return 2

@op(0xC3)
def _restore(vm, lg, ow, v, st, row): p = vm.g.player; p.hp = p.hp_max; return 1

@op(0xE9)
def _range(vm, lg, ow, v, st, row):
    p = vm.g.player
    st.result = int(math.hypot(p.wx - lg.wx, p.wy - lg.wy) <= v[1] * 8); return 3   # GUESS on unit (editor op)


@op(0xB3)
def _padset(vm, lg, ow, v, st, row):
    vm.g.pad_forced = (v[1] | v[2] << 8, v[3] | v[4] << 8, v[5] | v[6] << 8, v[7] | v[8] << 8); return 9


# ---------------------------------------------------------------- the game's own handlers --
# vm_game_*.py: every opcode checked against the US ALUN_CD.EXE handlers (research/us_decomp/vm_ops,
# audit_*.md).  They replace the handlers above where those differ from the game, plus the game's
# entity selection (0x8003D374) and run loop (clear handling of 0x40).
def _install_game_ops():
    import sys as _sys
    me = _sys.modules[__name__]
    import vm_game_00, vm_game_30, vm_game_60, vm_game_80, vm_game_A0   # noqa: F401 (60/80/A0 register on import)
    vm_game_00.install(me)
    vm_game_30.install(me)
    for m in (vm_game_60, vm_game_80, vm_game_A0):
        inst = getattr(m, 'install', None)
        if inst: inst(me)


_install_game_ops()
