"""What every native event command does, decoded from the game's own interpreter
(ALUN_CD.EXE event handlers, via the MIT xcasadio EntityEventHandlers.cs) and
checked by running the shipped scripts in the remake (remake/vm.py).

KNOWLEDGE[op] = (group, name, fields, help)
fields: list of (label, kind); kinds read these bytes after the opcode:
  sel   1 byte  entity selector      u8   1 byte number      s8 1 byte signed
  u16   2 bytes number               s16  2 bytes signed     flag 2 bytes game flag
  jump  2 bytes signed jump offset   dir  1 byte direction   anim 1 byte animation
  item  1 byte item                  map  2 bytes map        tile 1 byte tile coordinate
  sfx16 2 bytes sound                force 2 bytes vertical force (1/256 px per frame)
"""
import struct

SEL = 'sel'
DIRS = {0: 'down', 4: 'down-left', 8: 'left', 12: 'up-left', 16: 'up', 20: 'up-right', 24: 'right', 28: 'down-right'}

F, C, M, G, CA, A, MP, P, E, S = ('Flow control', 'Characters / objects', 'Message', 'Game progression', 'Camera',
                                   'Audio', 'Map', 'Player', 'Effects', 'Screen')
W = 'Wait until'
BOX = [('X from', 'tile'), ('X to', 'tile'), ('Y from', 'tile'), ('Y to', 'tile'), ('Height from', 'u8'), ('Height to', 'u8')]
XYZ = [('X (pixels)', 'u16'), ('Y (pixels)', 'u16'), ('Height (pixels)', 'u16')]
DXYZ = [('X offset', 's16'), ('Y offset', 's16'), ('Height offset', 's16')]

KNOWLEDGE = {
    0x00: (F, 'Yield until next frame', [], 'Stops this process for the current frame; it continues after this line next frame.'),
    0x01: (F, 'Do nothing', [], ''),
    0x02: (F, 'Jump to line', [('Target', 'jump')], ''),
    0x03: (F, 'Jump if condition true', [('Target', 'jump')], 'Uses the condition set by the last test command.'),
    0x04: (F, 'Jump if condition false', [('Target', 'jump')], 'Uses the condition set by the last test command.'),
    0x05: (G, 'Set flag', [('Flag', 'flag')], 'Flags 0x8000 and up are temporary: they reset when the map changes.'),
    0x06: (G, 'Clear flag', [('Flag', 'flag')], ''),
    0x07: (C, 'Test: character inside tile box', [('Character', SEL)] + BOX, 'Condition = true when any selected character stands inside the box (height in 16-pixel steps).'),
    0x08: (C, 'Turn by', [('Steps (32 = full turn)', 'u8')], ''),
    0x09: (C, 'Face direction', [('Direction', 'dir')], ''),
    0x0A: (C, 'Turn around', [], ''),
    0x0B: (C, 'Walk with animation until moved', [('Animation', 'anim'), ('Distance (pixels)', 'u16')], 'Plays the animation (its speed moves the character in its facing) and waits until it has moved the distance on X or Y. Blocked movement keeps waiting.'),
    0x0C: (C, 'Face random direction', [], 'Down, up, left or right.'),
    0x0D: (M, 'Show text', [('Message', 'u16')], "Shows the message with this character's portrait and name. Waits if a box is already open."),
    0x10: (P, 'Lock player movement', [], ''),
    0x11: (P, 'Unlock player movement', [], ''),
    0x12: (A, 'Play sound', [('Sound', 'u8')], ''),
    0x13: (F, 'Do nothing', [], ''),
    0x14: (F, 'Halt (wait forever)', [], ''),
    0x15: (C, 'Put back at placed height', [], ''),
    0x16: (C, 'Gravity on', [], 'The character falls and lands on terrain and on other solid characters.'),
    0x17: (C, 'Gravity off', [], 'The character floats; vertical force keeps moving it.'),
    0x18: (F, 'Do nothing', [], ''),
    0x19: (C, 'Deactivate this character', [], 'Hides it and runs its deactivate program.'),
    0x1A: (C, 'Change animation', [('Animation', 'anim')], 'Animations with a speed move the character in its facing direction.'),
    0x1B: (C, 'Set vertical force', [('Force', 'force')], 'Positive rises, negative falls (1/256 pixel per frame).'),
    0x1C: (C, W + ' animation played N times', [('Times', 'u8')], ''),
    0x1D: (C, W + ' animation played N times or blocked', [('Times', 'u8')], ''),
    0x1E: (C, W + ' moved N pixels', [('Distance', 'u16')], 'Blocked movement keeps waiting.'),
    0x1F: (C, W + ' moved N pixels or blocked', [('Distance', 'u16')], ''),
    0x20: (C, W + ' height changed by N', [('Pixels', 'u16')], ''),
    0x21: (C, W + ' height changed by N or landed', [('Pixels', 'u16')], ''),
    0x22: (C, 'Move to placed height', [], ''),
    0x23: (C, 'Move to placed height or until landed', [], ''),
    0x24: (C, W + ' blocked', [], ''),
    0x25: (C, W + ' on the ground', [], ''),
    0x26: (C, W + ' blocked or landed', [], ''),
    0x27: (C, 'Face the player', [], ''),
    0x28: (C, 'Set class B (stopped by no-walk tiles, hit by B attacks)', [], ''),
    0x29: (C, 'Clear class B', [], ''),
    0x2A: (C, 'Set class A (stopped by pits, hit by A attacks)', [], ''),
    0x2B: (C, 'Clear class A', [], ''),
    0x2C: (C, 'Test: no character matches', [('Character', SEL)], 'Condition = true when nothing matches (for example a spawned template is gone).'),
    0x2D: (C, 'Spawn map template', [('Template', 'u8')], 'Creates the template at its placed position and runs its load program.'),
    0x2E: (C, 'Remove characters', [('Character', SEL)], 'Condition = true if anything was removed.'),
    0x2F: (P, 'Test: buttons', [('Buttons', 'u16'), ('Mode (0 held, 1 pressed, 2 released, 3 repeat)', 'u8')], 'PlayStation button bits: 0x10 Triangle, 0x20 Circle, 0x40 Cross, 0x80 Square, 0x1000 Up, 0x2000 Right, 0x4000 Down, 0x8000 Left, 0x800 Start.'),
    0x30: (F, 'Jump if flag set', [('Flag', 'flag'), ('Target', 'jump')], ''),
    0x31: (F, 'Jump if flag clear', [('Flag', 'flag'), ('Target', 'jump')], ''),
    0x32: (G, 'Toggle flag', [('Flag', 'flag')], ''),
    0x33: (G, 'Test: all four flags set', [('Flag 1', 'flag'), ('Flag 2', 'flag'), ('Flag 3', 'flag'), ('Flag 4', 'flag')], ''),
    0x34: (G, 'Test: all four flags clear', [('Flag 1', 'flag'), ('Flag 2', 'flag'), ('Flag 3', 'flag'), ('Flag 4', 'flag')], ''),
    0x35: (G, W + ' flag clear', [('Flag', 'flag')], ''),
    0x36: (G, W + ' flag set', [('Flag', 'flag')], ''),
    0x37: (F, 'Wait', [('Frames', 'u8')], 'Counts frames (60 per second).'),
    0x38: (MP, 'Set save-map remap', [('Map', 'u16'), ('Saved as map', 'u16')], 'Which map a save made here returns to.'),
    0x39: (M, 'Wait for text box to close', [], ''),
    0x3A: (C, 'Face down/up/left/right', [('Direction (0 down 1 up 2 left 3 right)', 'u8')], ''),
    0x3B: (P, 'Test: player inside tile box', BOX, ''),
    0x3C: (C, 'Test: loose object inside tile box', BOX, ''),
    0x3D: (C, 'Test: anything inside tile box', BOX, ''),
    0x3E: (P, 'Test: player standing on this', [], ''),
    0x3F: (C, 'Test: anything standing on this', [], ''),
    0x40: (C, "Change this character's program", [('Slot (0 load 1 map 2 tick 3 touch 4 deactivate 5 talk)', 'u8'), ('Program', 'u8')], 'Restarts that program slot; program 0 turns it off.'),
    0x41: (C, 'Change built-in AI program', [('Slot', 'u8'), ('Program', 'u8')], ''),
    0x42: (C, 'Act on the player from now on', [], 'Following commands that say "this character" act on Alundra.'),
    0x43: (C, 'Act on selected character from now on', [('Character', SEL)], 'Condition = true if one was found.'),
    0x44: (M, 'Ask Yes / No', [], 'Condition = true for Yes.'),
    0x45: (C, 'Slide round obstacles', [], ''),
    0x46: (C, 'Stop dead at obstacles', [], ''),
    0x47: (C, W + ' hit or blocked', [], ''),
    0x48: (C, W + ' hit or landed', [], ''),
    0x49: (F, 'Restart process', [], ''),
    0x4A: (F, 'Restart process if condition true', [], ''),
    0x4B: (F, 'Restart process if condition false', [], ''),
    0x4C: (M, 'Text options', [('Options', 'u8')], ''),
    0x4D: (M, 'Text advances by itself', [], ''),
    0x4E: (F, 'Debug flag', [('Value', 'u8')], ''),
    0x4F: (M, 'Text advances by itself (debug)', [], ''),
    0x50: (S, 'Menu animation mode', [('Mode', 'u8')], ''),
    0x51: (M, 'Hold text box', [], ''),
    0x52: (MP, 'Use the activated warp portal', [], 'Condition = true if a portal was active.'),
    0x53: (MP, 'Change map', [('Map', 'map'), ('X', 'tile'), ('Y', 'tile'), ('Height', 'u8'), ('Transition', 'u8'), ('Sound', 'u8')], 'Transition 3 on the same map teleports without a fade.'),
    0x54: (MP, 'Add tile walk bits', [('X', 'tile'), ('Y', 'tile'), ('Walk bits', 'u8'), ('Ground bits', 'u8')], 'Walk bit 0x01 blocks the player, 0x40 blocks everyone.'),
    0x55: (MP, 'Remove tile walk bits', [('X', 'tile'), ('Y', 'tile'), ('Walk bits', 'u8'), ('Ground bits', 'u8')], ''),
    0x56: (MP, 'Apply map tile copy', [('Copy number', 'u8')], 'Copies a stored block of squares (doors opening, bridges).'),
    0x57: (F, 'Jump by player facing', [('If down', 's16'), ('If left', 's16'), ('If up', 's16'), ('If right', 's16')], ''),
    0x58: (F, 'Jump by own facing', [('If down', 's16'), ('If left', 's16'), ('If up', 's16'), ('If right', 's16')], ''),
    0x59: (C, 'Change animation of characters', [('Character', SEL), ('Animation', 'anim')], ''),
    0x5A: (C, 'Face direction (characters)', [('Character', SEL), ('Direction', 'dirmode')], ''),
    0x5B: (C, 'Change animation and direction (characters)', [('Character', SEL), ('Animation', 'anim'), ('Direction', 'dirmode')], 'With a walking animation this starts the character walking that way.'),
    0x5C: (M, 'Show text spoken by character', [('Speaker', SEL), ('Message', 'u16')], ''),
    0x5D: (C, 'Deactivate characters', [('Character', SEL)], ''),
    0x5E: (C, 'Set vertical force (characters)', [('Character', SEL), ('Force', 'force')], ''),
    0x5F: (C, W + ' animation/frames/distance', [('X tiles', 'u8'), ('Y tiles', 'u8'), ('Height', 'u8'), ('Animation loops', 'u8'), ('Frames', 'u8'), ('Also needs (1 blocked 2 landed 4 hit)', 'u8')], ''),
    0x60: (C, 'Test: character stands on this', [('Character', SEL)], ''),
    0x61: (C, 'Test: this stands on character', [('Character', SEL)], ''),
    0x62: (C, 'Set character flags', [('Character', SEL), ('Flags', 'eflags')], ''),
    0x63: (C, 'Clear character flags', [('Character', SEL), ('Flags', 'eflags')], ''),
    0x64: (C, 'Place characters at', [('Character', SEL)] + XYZ, ''),
    0x65: (C, 'Move characters by', [('Character', SEL)] + DXYZ, ''),
    0x66: (C, 'Copy logic state and jump', [('Index', 'u16')], ''),
    0x67: (CA, 'Camera follows character', [('Character', SEL)], ''),
    0x68: (CA, 'Camera stops following', [], ''),
    0x69: (CA, 'Camera looks at point', XYZ, ''),
    0x6A: (C, 'Remember position', [], ''),
    0x6B: (C, 'Test: moved on X since remembered', [('Pixels', 'u16')], ''),
    0x6C: (C, 'Test: moved on Y since remembered', [('Pixels', 'u16')], ''),
    0x6D: (C, 'Test: moved in height since remembered', [('Pixels', 'u16')], ''),
    0x6E: (C, 'Test: blocked', [], ''),
    0x6F: (C, 'Test: landed on something', [], ''),
    0x70: (C, 'Test: on the ground', [], ''),
    0x71: (C, 'Test: was hit', [], ''),
    0x72: (C, 'Remember animation and direction', [], ''),
    0x73: (F, 'Set repeat counter', [('Count', 'u8')], 'One counter per process.'),
    0x74: (F, 'Repeat (count down and jump)', [('Target', 'jump')], ''),
    0x75: (A, 'Play sound', [('Sound', 'u8')], ''),
    0x76: (F, 'Halt (wait forever)', [], ''),
    0x77: (F, 'Halt (wait forever)', [], ''),
    0x78: (F, 'Call local routine', [('Target', 'jump')], 'Return comes back after this line. One return address per process.'),
    0x79: (F, 'Call if condition true', [('Target', 'jump')], ''),
    0x7A: (F, 'Call if condition false', [('Target', 'jump')], ''),
    0x7B: (F, 'Call if flag set', [('Flag', 'flag'), ('Target', 'jump')], ''),
    0x7C: (F, 'Call if flag clear', [('Flag', 'flag'), ('Target', 'jump')], ''),
    0x7D: (F, 'Return from routine', [], ''),
    0x7E: (F, 'Return if condition true', [], ''),
    0x7F: (F, 'Return if condition false', [], ''),
    0x80: (F, 'Return if flag set', [('Flag', 'flag')], ''),
    0x81: (F, 'Return if flag clear', [('Flag', 'flag')], ''),
    0x82: (G, 'Give item', [('Item', 'item')], 'Condition = true if it could be given.'),
    0x83: (G, 'Test: have item count', [('Item', 'item'), ('At least', 'u8')], ''),
    0x84: (G, 'Use up item', [('Item', 'item')], 'Condition = true if the player had it.'),
    0x85: (MP, 'Copy map area', [('From X', 'tile'), ('From Y', 'tile'), ('Width', 'u8'), ('Height', 'u8'), ('To X', 'tile'), ('To Y', 'tile')], 'Copies squares (pictures, heights and walk bits).'),
    0x86: (C, 'Set damage flash timer', [('Character', SEL), ('Frames', 'u16')], ''),
    0x87: (C, 'Test: touched by attack element', [('Character', SEL), ('Element', 'u8')], ''),
    0x88: (C, 'Set status of characters', [('Character', SEL), ('Status', 'u8')], ''),
    0x89: (C, 'Place characters relative to another', [('Reference', SEL), ('Character', SEL)] + DXYZ, ''),
    0x8A: (C, 'Spawn template at', [('Template', 'u8')] + XYZ, ''),
    0x8B: (C, 'Spawn template relative to character', [('Reference', SEL), ('Template', 'u8')] + DXYZ, ''),
    0x8C: (F, 'Test: random', [('Chance of false (of 256)', 'u8')], ''),
    0x8D: (C, 'Test: character on the ground', [('Character', SEL)], ''),
    0x8E: (S, 'Scroll background', [('Speed X', 's8'), ('Speed Y', 's8'), ('Limit X', 'u8'), ('Limit Y', 'u8')], ''),
    0x8F: (S, 'Stop background scroll', [], ''),
    0x90: (E, 'Start map effect', [('Effect', 'u8')], ''),
    0x91: (E, 'Remove map effect', [('Effect', 'u8')], ''),
    0x92: (E, 'Map effect animation', [('Effect', 'u8'), ('Animation', 'u8')], ''),
    0x93: (E, 'Place map effect', [('Effect', 'u8')] + XYZ, ''),
    0x94: (E, 'Map effect force', [('Effect', 'u8')] + DXYZ, ''),
    0x95: (C, 'Test: attack element inside box', [('X', 'u8'), ('Y', 'u8'), ('Height', 'u8'), ('Size X', 'u8'), ('Size Y', 'u8'), ('Unused', 'u8'), ('Flags', 'u16'), ('Element', 'u8')], ''),
    0x96: (C, 'Heal characters', [('Character', SEL), ('Amount', 'u8')], ''),
    0x97: (C, 'Add magic (up to the maximum)', [('Amount', 'u8')], 'Save room magic tile: 97 32.'),
    0x98: (G, 'Add gilder', [('Amount', 'u16')], ''),
    0x99: (G, 'Pay gilder', [('Amount', 'u16')], 'Condition = true if paid.'),
    0x9A: (G, 'Test: have gilder', [('Amount', 'u16')], ''),
    0x9B: (MP, 'Disable warps', [], ''),
    0x9C: (MP, 'Enable warps', [], ''),
    0x9D: (F, 'Stop the game (debug)', [], ''),
    0x9E: (MP, 'Test: raised tiles in area', [('X', 'tile'), ('Y', 'tile'), ('Width', 'u8'), ('Height', 'u8'), ('At least', 'u8')], ''),
    0x9F: (G, 'Test: chest of character already opened', [('Character', SEL)], ''),
    0xA0: (E, 'Move map effect', [('Effect', 'u8')] + DXYZ, ''),
    0xA1: (E, 'Map effect at player', [('Effect', 'u8'), ('Character', SEL)] + DXYZ, ''),
    0xA2: (E, 'Start map effect at', [('Effect', 'u8')] + XYZ, ''),
    0xA3: (E, 'Start map effect at character', [('Effect', 'u8'), ('Character', SEL)] + DXYZ, ''),
    0xA4: (S, 'Scrolling mode', [('Mode', 'u8'), ('Value', 'u8')], ''),
    0xA5: (A, 'Stop all sound', [], ''),
    0xA6: (A, 'Load music', [('Track', 'u8')], ''),
    0xA7: (A, 'Music control', [('Track', 'u8'), ('Mode', 'u8')], ''),
    0xA8: (A, 'Test: sound still loading', [], ''),
    0xA9: (C, 'Test: bumped into character', [('Character', SEL)], ''),
    0xAA: (C, 'Test: character bumped into this', [('Character', SEL)], ''),
    0xAB: (A, 'Play sound with tone and volume', [('Sound', 'u8'), ('Tone', 'u8'), ('Volume', 'u8')], ''),
    0xAC: (C, 'Shadow size', [('Character', SEL), ('Size', 'u8'), ('Unused', 'u8')], ''),
    0xAD: (C, 'Test: character in box around another', [('Reference', SEL), ('Character', SEL), ('X start', 's8'), ('Y start', 's8'), ('Height start', 's8'), ('Width', 'u8'), ('Depth', 'u8'), ('Height', 'u8')], ''),
    0xAF: (S, 'Fade screen', [('Blue', 'u8'), ('Green', 'u8'), ('Red', 'u8'), ('Mode', 'u8'), ('Speed', 'u8'), ('Frames', 'u8')], ''),
    0xB0: (S, 'Warp fade colour', [('Red', 'u8'), ('Green', 'u8'), ('Blue', 'u8'), ('Frames', 'u8')], ''),
    0xB1: (S, 'Test: fade finished', [], ''),
    0xB2: (C, 'Test: two selections share a character', [('First', SEL), ('Second', SEL)], ''),
    0xB3: (P, 'Simulate buttons', [('Held', 'u16'), ('Pressed', 'u16'), ('Released', 'u16'), ('Repeat', 'u16')], 'Drives Alundra in demos and cutscenes.'),
    0xB4: (C, 'Test: character rising', [('Character', SEL)], ''),
    0xB5: (C, 'Test: character falling', [('Character', SEL)], ''),
    0xB6: (C, 'Test: character not moving vertically', [('Character', SEL)], ''),
    0xB7: (C, 'Test: character set to animation', [('Character', SEL), ('Animation', 'anim')], ''),
    0xB8: (C, 'Test: character playing animation', [('Character', SEL), ('Animation', 'anim')], ''),
    0xB9: (A, 'Start CD stream (voice / movie)', [('Stream', 'u8')], ''),
    0xBA: (A, 'Test: CD stream playing', [], ''),
    0xBB: (G, 'Game over / retry', [], ''),
    0xBC: (G, 'Raise maximum life', [('Amount', 'u8')], 'Capped at 50.'),
    0xBD: (A, 'Play sound', [('Sound', 'sfx16')], ''),
    0xBE: (A, 'Play sound', [('Sound', 'sfx16')], ''),
    0xBF: (A, 'Play sound with tone and volume', [('Sound', 'sfx16'), ('Tone', 'u8'), ('Volume', 'u8')], ''),
    0xC0: (P, 'Force weapon', [('Weapon', 'u8')], ''),
    0xC1: (P, 'Release forced weapon', [], ''),
    0xC2: (G, 'Test: save slot', [('Slot', 'u16')], ''),
    0xC3: (P, 'Restore life and magic', [], ''),
    0xC4: (M, 'Show text with chosen speaker', [('Portrait from', SEL), ('Speaker name', 'u16'), ('Message', 'u16')], ''),
    0xE9: (C, 'Test: player within range (editor AI)', [('Range', 'u8'), ('Unused', 'u8')], "Added by the editor's custom AI."),
    0xEA: (P, 'Raise maximum magic (editor)', [('Amount', 'u8')], "Added by the editor; native setter clamps 0..4."),
    0xFF: (F, 'End process', [], ''),
}

SIZES = {'sel': 1, 'u8': 1, 's8': 1, 'tile': 1, 'dir': 1, 'dirmode': 1, 'anim': 1, 'item': 1,
         'u16': 2, 's16': 2, 'flag': 2, 'jump': 2, 'map': 2, 'sfx16': 2, 'force': 2, 'eflags': 2}

EFLAGS = {0x1: 'class A', 0x2: 'hits B', 0x4: 'hits A', 0x8: 'class B', 0x10: 'deactivate on impact', 0x20: 'deactivate on hit',
          0x40: 'deactivate at animation end', 0x80: 'solid', 0x100: 'gravity', 0x800: 'class C', 0x1000: 'hits C',
          0x2000: 'no sliding', 0x4000: 'no riders', 0x8000: 'needs button'}


def selector_text(v):
    if v < 0x80: return f'template {v}'
    return {0x80: 'this character', 0x81: 'the player', 0x82: 'everyone', 0x83: 'everyone but the player',
            0x84: 'everything solid', 0x85: 'what this stands on', 0x86: 'what stands on this',
            0x87: 'what this bumped into', 0x88: 'what bumped into this', 0x89: 'what this spawned',
            0x8A: 'what spawned this', 0x8B: 'things on platforms'}.get(v, f'selector {v:#x}')


def direction_text(v, mode=False):
    if not mode or v < 32: return DIRS.get(v & 31, f'{v & 31}/32')
    m = v >> 5
    if m == 1: return f'turn by {v & 31}/32'
    if m == 2: return ('down', 'up', 'left', 'right')[v & 3]
    if m == 3: return 'toward the player' + (f' + {v & 31}/32' if v & 31 else '')
    return str(v)


def describe(op, raw, item_name=None, map_name=None, line_of=None, offset=0):
    """(group, action, settings text, help) or None when the command is unknown/truncated."""
    k = KNOWLEDGE.get(op)
    if not k: return None
    group, name, fields, help_ = k
    need = 1 + sum(SIZES[kind] for _, kind in fields)
    if len(raw) < need: return None
    o = 1; parts = []
    for label, kind in fields:
        n = SIZES[kind]
        v = raw[o] if n == 1 else struct.unpack_from('<H', raw, o)[0]
        sv = v - 0x10000 if n == 2 and v >= 0x8000 else (v - 256 if n == 1 and v >= 128 else v)
        o += n
        if kind == 'sel': t = selector_text(v)
        elif kind == 'dir': t = direction_text(v)
        elif kind == 'dirmode': t = direction_text(v, True)
        elif kind in ('s16', 's8'): t = f'{sv:+d}'
        elif kind == 'force': t = f'{sv / 256:+.2f} px/frame'
        elif kind == 'flag':
            from native_flag_index import flag_label
            t = flag_label(v)
        elif kind == 'jump':
            line = line_of(offset + sv) if line_of else None
            t = f'line {line}' if line else f'{sv:+d} bytes'
        elif kind == 'item':
            nm = item_name(v) if item_name else None
            t = f'{v}' + (f' · {nm}' if nm else '')
        elif kind == 'map': t = map_name(v) if map_name else str(v)
        elif kind == 'eflags': t = ', '.join(n2 for b, n2 in EFLAGS.items() if v & b) or f'{v:#x}'
        else: t = str(v)
        parts.append(f'{label}: {t}')
    return group, name, '; '.join(parts) or 'No settings', help_
