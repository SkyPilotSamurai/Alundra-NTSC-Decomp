"""The game's sound manager over pygame.

Sound effects follow PlaySound (0x8004A128), StopSound (0x8004A7B4), the volume command
(0x8004A928) and the per-frame manager (0x8004C454):
  * nothing starts while the music fade timer (0x801EFBFC) runs;
  * a sound id asked for twice in one frame plays once (64-entry list 0x801392D0, cleared each frame);
  * a record of the map's own bank (bank != -1) follows its chain (+0x0C) to the record made for
    the bank the current map loaded (0x800C8B90[map]); with no such record nothing plays;
  * a record plays only while fewer than its voice limit (+0x10) of its own voices still sound
    (counted by the id it was asked for, like the game - a chained record is never counted).
    A voice sounds until the SPU voice itself ends (0x80049FDC: SpuGetAllKeysStatus says off),
    which is the sound's dry length (index.json 'dry', tools/audio/sfx_dry.py) - not the length
    of the rendered file, which also holds the reverb's tail (Melzas's talk sound 82: 23 frames
    of voice, 1.9 s of file; counting the tail refused most of his letters);
  * a record with no tones (+0x14 <= 0: 58, 59, 71, 256-259) keys nothing on;
  * a sequence record (+0x0A != -1) plays once at a time (flag 2) until its sequence ends
    (SsIsEos, 0x80049CD4: index.json 'eos', from the game's own sequencer in sfx_render_vm.py);
    StopSound clears the flag of the record asked for and leaves the sequence playing;
  * the volume command scales every tone of the first copy of n by ((l+1)^2-1)/16383 per side (a
    sequence's notes are not in the voice table: untouched).
Stopping is a key-off, never a cut (StopSound 0x8004A7B4, stop-all 0x80049E4C, the fade's
SpuSetKey(OFF)): the tone's ADSR release runs and the reverb rings on - NNN_off.ogg, rendered
from the key-off (tools/audio/sfx_release.py).  StopSound clears the voice's id at once;
stop-all and the fade leave it until the envelope is at 0 ('release' frames), so it still counts
for the voice limit and for idle (the warp's wait).
The music fade (A6 1): 120 frames; from 119 to 61 the main volume falls (T-61)*127/60, at 60
the music stops and every voice is keyed off, at 3 the volume comes back.

Files: assets/audio/sfx/NNN.ogg (+ NNN_loop.ogg for sounds that loop until stopped), rendered
from the game's sound banks at the game's levels (tools/audio/sfx_render.py; the sequence sounds
by the game's own PlaySound in tools/audio/sfx_render_vm.py);
assets/audio/music_game/NN.ogg, the game's sequencer output (tools/audio/music_render_vm.py),
looping by their LOOPSTART / LOOPLENGTH tags."""
import json, os, threading
from pathlib import Path
import pygame
from engine import rodata as R

SOUND_REC = 0x800AA150
SOUND_COUNT = 0x80026848
MAP_BANK = 0x800C8B90
FADE_FRAMES = 120


def record(n):
    a = SOUND_REC + 0x16 * n
    f = [R.s16(a + 2 * k) for k in range(11)]
    return dict(bank=f[0], prog=f[1], tone=f[2], note=f[3], seq=f[5], next=f[6], voices=f[8], count=f[10])


def map_bank(m):
    try: return R.s32(MAP_BANK + 4 * m)
    except Exception: return -1


OUTPUT = 0.5                                # the console's output level against the rendered files: every
                                            # sound effect and the music measure 0.75 x (-2.5 dB) in BizHawk's
                                            # PS1 core (docs/2026-10-22-sound-levels-bizhawk-vs-remake.txt);
                                            # the files keep the SPU's own levels, so the balance is untouched
SAMPLES_PER_FRAME = 44100 / 59.826          # the files' rate over the console's frame rate


# SsIsEos frames of the sequence sounds (the game's sequencer, sfx_render_vm.py): extraction's index lacks them
SEQ_EOS = {73: 180, 74: 73, 76: 82, 77: 180, 174: 146, 206: 21, 657: 146, 675: 21, 866: 21}


class Voice:
    __slots__ = ('n', 'm', 'ch', 'snd', 'loop', 'lr', 'on_loop', 'left', 'seq', 'rel', 'book', 'parts', 'age')

    def __init__(self, n, m, ch, snd, loop, left=None, seq=False):
        self.n, self.m, self.ch, self.snd, self.loop, self.lr = n, m, ch, snd, loop, (1.0, 1.0)
        self.on_loop = False
        self.left = left                            # frames until the SPU voice ends (None: until the file ends)
        self.seq = seq                              # a sequence sound's notes (not in the voice table)
        self.rel = False                            # keyed off by stop-all / the fade: releasing
        self.book = False                           # played from a bNNN render (the boot program's first tone only)
        self.parts = []                             # tones looping on their own: [channel, pad, sound, loops, on_loop]
        self.age = 0                                # frames since the key-on (a save state puts it back)


class SoundSystem:
    def __init__(self, assets, settings, enabled=True):
        self.on = enabled
        self.settings = settings
        self.sfx_dir = Path(assets) / 'audio' / 'sfx'
        self.pending = 0; self.pending_play = False; self.read_left = 0; self.body_left = 0; self.b8 = 0
        self.music_dirs = [Path(assets) / 'audio' / 'music_game', Path(assets) / 'audio' / 'music']
        try: self.music_index = json.loads((self.music_dirs[0] / 'index.json').read_text())
        except (OSError, ValueError): self.music_index = {}
        try: self.sfx_index = json.loads((self.sfx_dir / 'index.json').read_text())
        except (OSError, ValueError): self.sfx_index = {}
        try: self.count = R.s32(SOUND_COUNT)
        except Exception: self.count = 962
        self.cache = {}
        self._names_of = {}             # directory -> the names in it (os.listdir once: the assets do not
                                        # change while running; .exists() per file was 4956 stats, 0.26 s,
                                        # at start and up to 1.3 ms a sound start)
        self._tones = {}                # _tone_files' answer per sound name
        self.voices = []
        self.asked = set()              # 0x801392D0: ids asked for this frame
        self.seq_busy = {}              # record -> frames left (sequence sounds, flag 2)
        self.fade = 0                   # 0x801EFBFC
        self.master = 1.0               # SsSetMVol during the fade
        self.bank = None                # *(0x801D7DC4)
        self.music = None               # music id loaded (0x801D7B98)
        self.music_on = False
        self.music_auto = False         # 0x8013A158: start the loaded music next frame
        self.last = None
        self.xa_left = 0                # frames until the XA clip's last sector is read (0x800C6674)
        self.xa_sound = None
        self._xa_decode = None          # (thread, [result]) decoding the clip asked for, until _xa_begin
        self.music_closed = False       # 0x8004B278 for map music 0x2D: SsSeqClose, the id kept
        self.music_from = 0.0           # where the file was started (a save state's music position)
        self.emu = None                 # sndlive.dll: the game's sound code on an emulated SPU (music so far)
        self.emu_tried = False
        self.emu_next = None            # the engine taking over once it has caught up
        self.set_engine()

    # ------------------------------------------------------------------ emulated engine
    def _emu_lib(self):
        """The DLL, started once, on the player's own disc data (assets/audio/emu); None if unavailable."""
        if self.emu_tried: return SoundSystem._emu_dll
        self.emu_tried = True
        if SoundSystem._emu_dll is not None: return SoundSystem._emu_dll
        try:
            import ctypes
            d = self.sfx_dir.parent / 'emu'
            lib = ctypes.CDLL(str(Path(__file__).resolve().parent / 'sndlive.dll'))
            sdl = ctypes.WinDLL('SDL2.dll')
            lib.snd_init.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
            lib.snd_gain.argtypes = [ctypes.c_float]; lib.snd_busy_ms.restype = ctypes.c_double
            if lib.snd_init(str(d / 'ALUN_CD.EXE').encode('mbcs'), str(d / 'SOUND.BIN').encode('mbcs'), sdl._handle) == 0:
                SoundSystem._emu_dll = lib
        except (OSError, AttributeError, ImportError): pass
        return SoundSystem._emu_dll

    _emu_dll = None

    def set_engine(self):
        """Options > Sound Engine, at once: the music goes on the chosen engine from its start."""
        want = self.on and self.settings.get('sound_engine') == 'emulated'
        lib = self._emu_lib() if want else None
        if self.emu_next is not None:                    # changed back before the hand-over: Rendered stays
            self.emu_next.snd_reset(); self.emu_next = None
        if lib is self.emu: return
        if not self.music_on:
            self.emu = lib; self.apply_volume(); return
        pos = self._music_pos()
        if lib is not None:                              # Rendered plays on until the sequence has caught up
            lib.snd_gain(0.0); lib.snd_seek(self.music, int(pos * 59.826)); self.emu_next = lib
        else:
            old = self.emu; self.emu = None; old.snd_reset()
            self._file_at(self.music, pos)

    def _music_pos(self):
        """Seconds into the music file (a loop's later passes counted as its one pass)."""
        info = self.music_index.get(str(self.music), {})
        try: pos = self.emu.snd_ticks() / 59.826 if self.emu is not None else max(0, pygame.mixer.music.get_pos()) / 1000 + self.music_from
        except pygame.error: pos = 0.0
        ls, ll = info.get('loop_start'), info.get('loop_length')
        if ls and ll and pos * 44100 > ls + ll: pos = (ls + (pos * 44100 - ls) % ll) / 44100
        return pos

    def _file_at(self, mid, pos):
        f = self._music_file(mid)
        info = self.music_index.get(str(mid), {})
        if f is None or (info.get('kind') == 'once' and pos * 44100 >= info.get('samples', 0)):
            self.music_on = False; return
        try:
            pygame.mixer.music.stop(); pygame.mixer.music.load(str(f))
            pygame.mixer.music.play(0 if info.get('kind') == 'once' else -1, start=pos)
            self.music_on = True; self.music_from = pos
        except pygame.error: self.music_on = False
        self.apply_volume()

    def _hand_over(self):
        """The sequence has caught up: it takes over from the file."""
        lib, self.emu_next = self.emu_next, None
        try: pygame.mixer.music.stop()
        except pygame.error: pass
        self.emu = lib; self.apply_volume()

    # ------------------------------------------------------------------ helpers
    def _names(self, d):
        """The file names in directory d (empty when it does not exist)."""
        s = self._names_of.get(d)
        if s is None:
            try: s = set(os.listdir(d))
            except OSError: s = set()
            self._names_of[d] = s
        return s

    def _load(self, name):
        s = self.cache.get(name, 0)
        if s == 0:
            f = self.sfx_dir / name
            try: s = pygame.mixer.Sound(str(f)) if name in self._names(self.sfx_dir) else None
            except pygame.error: s = None
            self.cache[name] = s
        return s

    _silent = None

    def _unqueue(self, ch):
        """Drop the channel's queued sound.  pygame starts a channel's queued sound whenever the
        channel finishes - also when it is stopped or faded out - so a looping sound keyed off
        (warps, StopSound, stop-all) played its whole loop file again after the fade: the sound
        that came back while leaving an area, and the moving blocks in Wendell's dream sounding
        on for seconds after they stopped.  pygame has no unqueue: a 1-sample silence replaces it."""
        try:
            if ch.get_queue() is None: return
            if SoundSystem._silent is None:
                import array
                f = pygame.mixer.get_init() or (44100, -16, 2)
                SoundSystem._silent = pygame.mixer.Sound(buffer=array.array('h', [0] * max(1, f[2])).tobytes())
            ch.queue(SoundSystem._silent)
        except (pygame.error, TypeError, ValueError): pass

    def _play(self, snd, lr=(1.0, 1.0), fade_ms=0):
        """Starts snd on a channel already at its level.  Sound.play() puts the channel at full
        volume and the level only came after, so a quiet sound (a map's 25% river, a 0% one)
        sounded at 100% for the mixer's next block: the loud blip as a sound was keyed off and its
        release started (user report: louder for a split second as the screen fades).
        Channel.play keeps the volume set before it."""
        if snd.get_length() == 0:                    # an empty part (all of the sound is in its tone files):
            snd = self._silence()                    # SDL crashes playing a 0-sample sound
        ch = pygame.mixer.find_channel()
        if ch is None:                               # every channel busy: take the one playing longest
            ch = pygame.mixer.find_channel(True)    # (mostly reverb tails by then)
            if ch is None: return None
            self._unqueue(ch)
        g = self._gain(); l, r = lr[0] * g, lr[1] * g
        if l == r: ch.set_volume(l)
        else: ch.set_volume(l, r)
        ch.play(snd, fade_ms=fade_ms)
        return ch

    @staticmethod
    def _silence():
        if SoundSystem._silent is None:
            import array
            f = pygame.mixer.get_init() or (44100, -16, 2)
            SoundSystem._silent = pygame.mixer.Sound(buffer=array.array('h', [0] * max(1, f[2])).tobytes())
        return SoundSystem._silent

    def _gain(self):
        return self.settings.get('sfx_volume', 100) / 100 * self.master * OUTPUT

    def _apply(self, v):
        """The voice's level.  pygame's two-value Channel.set_volume is a panning effect that SDL
        drops when the channel moves on to its queued sound (the loop part), so equal sides use
        the channel volume (which stays) and unequal ones are set again when the loop starts."""
        g = self._gain()
        l, r = v.lr[0] * g, v.lr[1] * g
        for ch in [v.ch] + [p[0] for p in v.parts]:
            try:
                if l == r: ch.set_volume(l)
                else: ch.set_volume(l, r)
            except pygame.error: pass
        v.on_loop = False
        for p in v.parts: p[4] = False

    def apply_volume(self):
        if not self.on: return
        for v in self.voices: self._apply(v)
        if self.emu is not None: self.emu.snd_gain(self.settings.get('music_volume', 100) / 100 * self.master * OUTPUT)
        try: pygame.mixer.music.set_volume(self.settings.get('music_volume', 100) / 100 * self.master * OUTPUT)
        except pygame.error: pass
        if self.xa_sound is not None:
            try: pygame.mixer.Channel(self.XA_CHANNEL).set_volume(self.settings.get('music_volume', 100) / 100 * OUTPUT)
            except pygame.error: pass

    def _alive(self, v):
        """The file still plays on its channel (voice or reverb tail).  A looping sound lives until
        it is stopped or its channel is taken: between its first part and the queued loop (or
        while the mixer thread is late handing the queue over) the channel is briefly idle with
        the loop still queued - counting that as the end lost the voice, so StopSound never
        reached it (the waves, moving blocks and machines that went on) and the scripts that
        start a sound when theirs is gone started a second copy."""
        if v.parts:                                  # tones looping on their own: alive while one plays
            return any(self._part_alive(p) for p in v.parts)
        try:
            cur = v.ch.get_sound()
            if v.loop is not None:
                if cur is v.loop or (cur is v.snd and v.ch.get_queue() is v.loop): return True
                if cur is v.snd and v.ch.get_busy(): return True
                return False
            return v.ch.get_busy() and cur is v.snd
        except pygame.error: return False

    @staticmethod
    def _part_alive(p):
        ch, pad, snd, loops = p[0], p[1], p[2], p[3]
        try:
            cur = ch.get_sound()
            if cur is snd and ch.get_busy(): return True
            if cur is pad and (ch.get_busy() or ch.get_queue() is snd): return True
            return loops and ch.get_queue() is snd
        except pygame.error: return False

    def _pad(self, snd):
        """Silence as long as snd (a tone's channel waits out the intro with it)."""
        key = ('pad', id(snd))
        s = self.cache.get(key)
        if s is None:
            s = pygame.mixer.Sound(buffer=bytes(len(snd.get_raw())))
            self.cache[key] = s
        return s

    def _sounding(self, v):
        """The SPU voice still sounds (the game's voice table 0x801EFE68)."""
        if v.seq: return False
        if v.left is not None and v.loop is None and not v.parts: return v.left > 0 and self._alive(v)
        return self._alive(v)

    # ------------------------------------------------------------------ map bank
    def set_map(self, m):
        """The map's sound bank (0x8004B0D8).  A new bank keys every sound effect off (0x80049E4C)."""
        b = map_bank(m)
        if b != self.bank:
            self.stop_all()
            self.bank = b

    def resolve(self, n):
        rec = record(n)
        if rec['bank'] == -1: return n, rec
        m = n
        while rec['bank'] != self.bank:
            m = rec['next']
            if m == 0: return None, None
            rec = record(m)
        return m, rec

    def preload(self, ids):
        """Decodes the files of these sound ids (as the current bank resolves them) ahead of use."""
        if not self.on: return
        # (decoding lets Python's lock go: on a thread it does not hold up the map's set-up; a sound
        # asked for before its turn is decoded where it is asked, as it always was)
        self.preload_thread = threading.Thread(target=self._preload, args=(list(ids),), name='sfx_preload', daemon=True); self.preload_thread.start()

    def _preload(self, ids):
        for n in ids:
            try:
                if not 0 < n <= self.count: continue
                m, rec = self.resolve(n)
            except Exception: continue
            if m is None: continue
            names = self._names(self.sfx_dir)
            for name in (f'{m:03d}.ogg', f'{m:03d}_loop.ogg', f'{m:03d}_off.ogg'):
                if name in names: self._load(name)
            for name, _ in self._tone_files(f'{m:03d}'): self._load(name)

    def _tone_files(self, name):
        """NNN_tone<k>.ogg / NNN_tone<k>_once.ogg (tools/audio/sfx_render.py render_tones): the
        tones of a sound that loop with different periods, each looping (or ending) on its own."""
        out = self._tones.get(name)
        if out is None:
            out = []; names = self._names(self.sfx_dir)
            for k in range(24):
                if f'{name}_tone{k}.ogg' in names: out.append((f'{name}_tone{k}.ogg', True))
                elif f'{name}_tone{k}_once.ogg' in names: out.append((f'{name}_tone{k}_once.ogg', False))
                else: break
            self._tones[name] = out
        return out

    # ------------------------------------------------------------------ PlaySound
    def play(self, n, book=False):
        """book: the boot program's PlaySound (SLUS 0x800289D8), which keys on the record's first
        tone only (SsUtKeyOn) where the game's keys on all `count` of them; such sounds have a
        bNNN render."""
        self.last = n
        if self.fade or n <= 0 or n > self.count: return
        if n in self.asked: return
        if len(self.asked) < 64: self.asked.add(n)
        if record(n)['bank'] == -2: return
        self.voices = [v for v in self.voices if self._alive(v)]
        m, rec = self.resolve(n)
        if m is None: return
        if rec['seq'] != -1:
            if m in self.seq_busy: return
            e = self.sfx_index.get(str(m), {})
            eos = e.get('eos') or SEQ_EOS.get(m) or -(-e.get('frames', 0) // 735)
            self.seq_busy[m] = max(1, eos)                       # until SsIsEos
            self._start(n, m, book, seq=True)
            return
        if rec['count'] <= 0 and not book: return              # no tones to key on
        busy = sum(1 for v in self.voices if v.n == m and v.m == m and self._sounding(v))
        if busy >= rec['voices']: return
        self._start(n, m, book)

    def _start(self, n, m, book=False, seq=False):
        if not self.on: return
        name = f'{m:03d}'
        if book and f'b{name}.ogg' in self._names(self.sfx_dir): name = 'b' + name
        snd = self._load(f'{name}.ogg')
        if snd is None: return
        tones = [] if seq else [(self._load(f), lp) for f, lp in self._tone_files(name)]
        tones = [(s, lp) for s, lp in tones if s is not None]
        loop = None if tones else self._load(f'{name}_loop.ogg')
        ch = self._play(snd)
        if ch is None: return
        if loop is not None: ch.queue(loop)
        parts = []
        if tones:                                   # each tone on its own channel, after the intro's length
            pad = self._pad(snd)
            for s, lp in tones:
                c = self._play(pad)
                if c is None: continue
                c.queue(s)
                parts.append([c, pad, s, lp, False])
        dry = self.sfx_index.get(str(m), {}).get('dry')
        v = Voice(n, m, ch, snd, loop, None if dry is None else -(-dry // SAMPLES_PER_FRAME), seq)
        v.parts = parts
        v.book = name.startswith('b')
        self._apply(v)
        self.voices.append(v)

    def _keyoff(self, v):
        """The voice's key-off: its release and the reverb tail play on.  Returns the voice that
        stands for the release (its id still in the table), or None."""
        if v.rel: return v
        self._unqueue(v.ch)                         # (or the loop part plays again after the fade)
        if v.parts:                                 # tones on their own channels (render_tones)
            sounding = self._sounding(v)
            e = self.sfx_index.get(str(v.m), {})
            off = self._load(f'{v.m:03d}_off.ogg') if sounding and 'release' in e else None
            rel = e.get('release', 8)
            ms = 12 if off is not None or not sounding else max(20, int(rel * 1000 / 59.826))
            for c in [v.ch] + [p[0] for p in v.parts]:
                self._unqueue(c)
                try: c.fadeout(ms)
                except pygame.error: pass
            if not sounding: return None
            try:
                if off is not None:                 # NNN_off: the release of all the tones
                    ch = self._play(off, v.lr, 12)
                    if ch is None: return None
                    r = Voice(v.n, v.m, ch, off, None, rel)
                else:
                    p = v.parts[0]
                    r = Voice(v.n, v.m, p[0], p[0].get_sound(), None, rel)
            except pygame.error:
                return None
            r.lr = v.lr; r.rel = True
            self._apply(r)
            return r
        if v.seq:                                   # SsSeqStop: the notes release
            try: v.ch.fadeout(300)
            except pygame.error: pass
            return None
        if not self._sounding(v): return None       # the voice had ended: only the reverb rings on
        e = self.sfx_index.get(str(v.m), {})
        # a bNNN voice releases with bNNN_off when there is one, else by fading itself: NNN_off is
        # the full sound's (all tones) release - louder than the first tone it follows (the History
        # Book's 0x193 on leaving the room)
        off = self._load(f'{"b" if v.book else ""}{v.m:03d}_off.ogg') if 'release' in e else None
        rel = e.get('release', 8)
        try:
            if off is None:
                v.ch.fadeout(max(20, int(rel * 1000 / 59.826)))
                r = Voice(v.n, v.m, v.ch, v.snd, None, rel)
            else:
                v.ch.fadeout(12)
                ch = self._play(off, v.lr, 12)              # (at the voice's own level from the start)
                if ch is None: return None
                r = Voice(v.n, v.m, ch, off, None, rel)
        except pygame.error:
            return None
        r.lr = v.lr; r.rel = True
        # The id leaves the table no later than the voice would have ended anyway: BizHawk
        # 2026-10-23, Fire Manor door (map 140), 0x1DD keyed off by the warp 4 frames before
        # its end was gone from 0x801EFE80 at that end, not after its 26-frame release.
        if v.left is not None and v.loop is None: r.left = min(rel, max(0, v.left))
        self._apply(r)
        return r

    def stop(self, n):
        """StopSound 0x8004A7B4: keys off every voice whose id is n and clears the id.  For a
        sequence record it clears flag 2 of record n itself (set on the record that played:
        a chained one stays busy) and the sequence plays on (its notes are not in the table)."""
        if n == 0: return
        self.seq_busy.pop(n, None)
        keep = []
        for v in self.voices:
            if v.n == n and not v.seq: self._keyoff(v)
            else: keep.append(v)
        self.voices = keep

    def stop_all(self):
        """0x80049E4C: every voice keyed off (ids kept until the release ends), the flagged
        sequence sounds stopped."""
        keep = []
        for v in self.voices:
            if v.seq and v.m not in self.seq_busy: keep.append(v); continue   # unflagged: plays on
            r = self._keyoff(v)
            if r is not None: keep.append(r)
        self.voices = keep
        self.seq_busy.clear()

    def cut_sfx(self):
        """The map read of a map change: every sound effect is silent at once, the music plays
        on.  BizHawk 2026-10-20 (map 19's tornado to map 403, music already stopped by A6 00):
        the wind, keyed off at the warp and still at full level, is cut to exact silence on the
        frame the map number changes; the remake's release render (650_off.ogg, 141 frames with
        its tail) sounded on through the black pause."""
        for v in self.voices:
            if v.seq: continue
            for c in [v.ch] + [p[0] for p in v.parts]:
                try: self._unqueue(c); c.stop()
                except pygame.error: pass
        self.voices = [v for v in self.voices if v.seq]

    def idle(self):
        """0x8004AFE8: no sound effect voice still sounds and no sequence sound still runs."""
        self.voices = [v for v in self.voices if self._alive(v)]
        return not any(self._sounding(v) for v in self.voices) and not self.seq_busy

    def volume(self, n, l, r):
        """0x8004A928: left / right 0..127 on every tone of the first sounding copy of id n (a loop over
        the record's tones, 0x8004AA10-0x8004AC58; 0x8004A8D4 finds each tone's voice): the whole file here."""
        f = lambda x: max(0, ((x & 0xFF) + 1) ** 2 - 1) / 16383
        for v in self.voices:                       # (a stopped voice's tail is not in the table:
            if v.n == n and not v.seq and self._sounding(v):   # the deck's sea fading out took the
                v.lr = (min(1.0, f(l)), min(1.0, f(r))); self._apply(v)   # cabin's 64/64, its new
                return                              # loop stayed at full volume)

    # ------------------------------------------------------------------ music
    def _music_file(self, mid):
        for d in self.music_dirs:
            names = self._names(d)
            for name in (f'{mid:02d}.ogg', f'{mid:02d}.wav'):
                if name in names: return d / name
        return None

    MUSIC_TABLE = 0x800A9DF8            # per track: VAB header start, SEQ start, VAB body start (bytes, 3 x u32)

    def music_load(self, mid, play):
        """0x8004C380: with the XA stream on (0x800AA118 = 1, always in play) the load is deferred
        to the sound manager (0x8004C454): the old sequence stops now, 0x800AA0B4 = 1, and the
        VAB header, its body (16-sector chunks) and the SEQ are read from the disc over the
        following frames; A8 (0x8004C370) reports the load pending until the sequence is open.
        Read times are the recompiled game's: a read of n sectors takes ceil(n / 2) frames."""
        self.xa_stop()                                   # 0x8004C418: the XA stream stops first
        self.music_stop(False); self.music_closed = False
        self.music = mid
        if not mid:
            self.pending = 0; self.music_auto = False; return
        self.pending = 1; self.pending_play = bool(play)
        self.music_auto = False

    def _music_sizes(self, mid):
        try:
            b = self.MUSIC_TABLE + mid * 12
            s0, h0, b0 = R.u32(b), R.u32(b + 4), R.u32(b + 8)     # SEQ, VAB header, VAB body starts
            n0 = R.u32(b + 12)                                    # (the next track's SEQ ends the body)
            return (h0, b0 - h0), (b0, n0 - b0), (s0, h0 - s0)    # (start, bytes) of header, body, seq
        except Exception:
            return (0, 0x2000), (0, 0x8000), (0, 0x2000)

    @staticmethod
    def _read_frames(sectors):
        """Sound ticks until a CD read of n sectors after a seek is in, as the recompiled game
        does them (measured for every track: 2-3 sectors 3, 4-6 4, 7-8 5, 9 6, 12-13 7, 14 8,
        18 9, 20 10 = ceil(0.4 n + 1.5)); a 16-sector chunk read in place takes 8."""
        return (4 * sectors + 15 + 9) // 10

    def _music_pending_tick(self):
        """0x8004C454's load states, one a sound tick (the end of every game frame): 1 the VAB
        header read is issued (state 2 at once); 2 header in -> 3; 3 the first 16-sector body
        chunk read is issued (state 4); 4 a chunk in: SsVabTransBody (b8 = 1), the tick after
        the next chunk read, or the SEQ read when the body is in (state 5); 5 SEQ in: open,
        played when asked, state 0."""
        st = self.pending
        if not st: return
        hdr, body, seq = self._music_sizes(self.music)
        if st == 1:                                       # the VAB header
            self.read_left = self._read_frames(hdr[1] // 2048 + 1); self.pending = 2
        elif st == 2:
            self.read_left -= 1
            if self.read_left <= 0: self.pending = 3
        elif st == 3:                                     # the body: the first 16-sector chunk
            self.body_left = body[1]; self.read_left = 8; self.b8 = 0; self.pending = 4
        elif st == 4:
            if self.b8 == 1:                              # the chunk is in: the next read
                if self.body_left <= 0:
                    self.read_left = self._read_frames(seq[1] // 2048 + 1); self.pending = 5
                else: self.read_left = 8; self.b8 = 0
            else:
                self.read_left -= 1
                if self.read_left <= 0: self.b8 = 1; self.body_left -= 0x8000
        elif st == 5:
            self.read_left -= 1
            if self.read_left <= 0:                       # the sequence is open: played if asked
                self.pending = 0
                if self.pending_play: self.music_play()

    def music_load_now(self, mid, play):
        """0x8004AD80 (map loads 0x8004B2C0, the title 0x80028D48): the VAB and the SEQ are read
        at once (the CD is already busy with the map); the music starts at the next sound
        tick (0x8013A158 = 1), now too when asked."""
        self.xa_stop()                                   # the CD read stops the XA stream (0x80050248)
        self.music_stop(False); self.music_closed = False
        self.music = mid; self.pending = 0; self.pending_play = False
        if mid and play: self.music_play()
        self.music_auto = bool(mid)

    def music_loading(self):
        return self.pending != 0

    def music_unload(self):
        self.music_stop(False); self.music = 0; self.music_auto = False; self.music_closed = False

    def music_close(self):
        """0x8004B278 for map music 0x2D: SsSeqStop + SsSeqClose; the id (0x801D7B98) stays, and a
        later SsSeqPlay (A5) on the closed access is silent."""
        self.music_stop(False); self.music_closed = True

    def music_play(self):
        """0x8004AC90: cancels a fade (every voice keyed off), full volume, SsSeqPlay - which does
        not rewind: before the fade's T=60 SsSeqStop the music goes on from where it is."""
        self.music_auto = False
        if self.fade:
            early = self.fade > 60
            self.stop_all()
            if not early: self.music_stop(False)
            self.fade = 0; self.master = 1.0; self.apply_volume()
        if not self.on or not self.music or self.music_on or self.music_closed: return
        if self.emu is not None:                         # 0x8004C380: the sequence reads, opens and plays
            self.emu.snd_music_load(self.music, 1); self.music_on = True; self.music_from = 0.0
            self.apply_volume(); return
        f = self._music_file(self.music)
        if f is None: return
        info = self.music_index.get(str(self.music), {})
        try:
            # The old track's 250 ms fade-out (music_stop) is still running here mostly: load's
            # Mix_FreeMusic then waits for it in 100 ms sleeps - 304 ms frozen, the game's worst
            # stall (1 ms after stop()).  The original starts the new sequence at the next sound
            # tick anyway; the fading notes are not heard under it.
            try: pygame.mixer.music.stop()
            except pygame.error: pass
            pygame.mixer.music.load(str(f))
            pygame.mixer.music.play(0 if info.get('kind') == 'once' else -1)
            self.music_on = True; self.music_from = 0.0
        except pygame.error:
            return
        self.apply_volume()

    def music_stop(self, fade):
        """0x8004AD18: with fade the 120-frame fade timer starts, else SsSeqStop now."""
        self.music_auto = False
        if fade:
            self.fade = FADE_FRAMES
            return
        if self.emu_next is not None: self._hand_over()
        if self.emu is not None:
            if self.music_on: self.emu.snd_music_stop()  # SsSeqStop: the notes release, the reverb rings
        elif self.on and self.music_on:
            try: pygame.mixer.music.fadeout(250)   # SsSeqStop keys the notes off: they release
            except pygame.error: pass
        self.music_on = False

    # ------------------------------------------------------------------ XA (CD audio)
    XA_CHANNEL = 0                      # reserved for the CD's audio (pygame.mixer.set_reserved(1))

    XA_LEAD = 35                        # frames from the call to the first sound: the drive seeks
                                        # to the clip and the stream starts (measured on the recompiled
                                        # game: clip 9 counts as playing 1534 frames for 1499 of sound,
                                        # clip 10 at least 31 more than its own)

    def xa_start(self, path, frames):
        """0x8005CB94: the drive seeks and streams the clip; it counts as playing (0x800C6674)
        until its last sector is read: XA_LEAD + frames game frames from now.  The sound starts
        once the stream does."""
        self.xa_stop()
        self.xa_left = max(1, frames) + self.XA_LEAD
        self.xa_lead = self.XA_LEAD
        if not self.on: return
        # The clip (up to 900 KB of ogg, ~70 ms a MB) is decoded on a thread - pygame lets the GIL
        # go in Sound() - and wanted only XA_LEAD frames on, in _xa_begin, like the seeking drive.
        # The thread writes its own box; xa_stop drops the pair, so a clip stopped before it began
        # never plays.  (snd is a live object to savestate: never copied.)
        box = [None]
        def decode(p=str(path)):
            try: box[0] = pygame.mixer.Sound(p)
            except Exception: box[0] = None         # (pygame raises FileNotFoundError, not pygame.error,
                                                    # for a missing clip: nothing escapes the thread)
        t = threading.Thread(target=decode, name='xa_decode', daemon=True)
        self._xa_decode = (t, box)
        t.start()

    def _xa_begin(self):
        if self._xa_decode is not None:             # the stream starts: the clip, decoded by now mostly
            t, box = self._xa_decode; self._xa_decode = None
            t.join()
            self.xa_sound = box[0]
        if self.xa_sound is None or not self.on: return
        try:
            ch = pygame.mixer.Channel(self.XA_CHANNEL)
            ch.play(self.xa_sound)
            ch.set_volume(self.settings.get('music_volume', 100) / 100 * OUTPUT)
        except pygame.error:
            self.xa_sound = None

    def xa_stop(self):
        """0x8005C8DC: the stream stops (CdlPause)."""
        self.xa_left = 0; self.xa_lead = 0
        self._xa_decode = None                      # a clip still decoding is dropped unheard
        if self.xa_sound is not None and self.on:
            try: pygame.mixer.Channel(self.XA_CHANNEL).stop()
            except pygame.error: pass
        self.xa_sound = None

    # ------------------------------------------------------------------ save states
    def state(self):
        """What a save state keeps of the sound: plain numbers (the mixer's objects stay live)."""
        pos = self._music_pos() if self.music_on else 0.0
        return dict(pos=pos, on=self.music_on, music=self.music, fade=self.fade, master=self.master,
                    seq=dict(self.seq_busy), bank=self.bank, closed=self.music_closed,
                    voices=[(v.n, v.m, v.age, v.left, v.lr) for v in self.voices if not v.rel and not v.seq])

    def _at(self, snd, frames):
        """snd from `frames` game frames on (None past its end)."""
        raw = snd.get_raw(); o = int(frames * SAMPLES_PER_FRAME) * 4
        return pygame.mixer.Sound(buffer=raw[o:]) if o < len(raw) else None

    def set_state(self, st):
        self.stop_all(); self.cut_sfx(); self.bank = st['bank']; self.seq_busy = dict(st['seq'])
        self.fade = st['fade']; self.master = st['master']; self.music_closed = st['closed']
        if not self.on: return
        for n, m, age, left, lr in st['voices']:
            name = f'{m:03d}'
            if self._tone_files(name):
                self._start(n, m); continue                     # (several channels: from their start)
            snd, loop = self._load(f'{name}.ogg'), self._load(f'{name}_loop.ogg')
            if snd is None: continue
            part = self._at(snd, age)
            if part is None and loop is not None:
                over = age - snd.get_length() * 59.826
                part = self._at(loop, over % (loop.get_length() * 59.826))
            if part is None: continue
            ch = self._play(part)
            if ch is None: continue
            if loop is not None: ch.queue(loop)
            v = Voice(n, m, ch, part, loop, left); v.age = age; v.lr = lr
            self._apply(v); self.voices.append(v)
        self.music_stop(False); self.music = st['music']
        if not st['music'] or not st['on'] or st['closed']: return
        if self.emu is not None:                         # the sequence runs ahead to the position
            self.emu.snd_seek(st['music'], int(st['pos'] * 59.826)); self.music_on = True; self.apply_volume(); return
        f = self._music_file(st['music'])
        if f is None: return
        info = self.music_index.get(str(st['music']), {}); pos = st['pos']
        ls, ll = info.get('loop_start'), info.get('loop_length')
        if ls and ll and pos * 44100 > ls + ll: pos = (ls + (pos * 44100 - ls) % ll) / 44100
        pygame.mixer.music.stop(); pygame.mixer.music.load(str(f))
        pygame.mixer.music.play(0 if info.get('kind') == 'once' else -1, start=pos)
        self.music_on = True; self.music_from = pos
        self.apply_volume()

    # ------------------------------------------------------------------ per frame
    def tick(self):
        """0x8004C454, once per frame."""
        self.asked.clear()
        self._music_pending_tick()
        if self.xa_left > 0:
            self.xa_left -= 1
            if getattr(self, 'xa_lead', 0) > 0:
                self.xa_lead -= 1
                if self.xa_lead == 0: self._xa_begin()
        for v in self.voices:
            v.age += 1
            if v.left is not None and v.left > 0: v.left -= 1
        for k in list(self.seq_busy):
            self.seq_busy[k] -= 1
            if self.seq_busy[k] <= 0: del self.seq_busy[k]
        if self.music_auto: self.music_play()
        for v in self.voices:                       # a looping sound keeps its loop queued
            if v.loop is not None:
                try:
                    if v.ch.get_busy() and v.ch.get_sound() is v.loop:
                        if not v.on_loop and v.lr[0] != v.lr[1]:
                            self._apply(v)          # its panning again (SDL dropped it)
                        v.on_loop = True
                        if v.ch.get_queue() is None: v.ch.queue(v.loop)
                except pygame.error: pass
            for p in v.parts:                       # each tone keeps its own loop queued
                if not p[3]: continue
                try:
                    if p[0].get_busy() and p[0].get_sound() is p[2]:
                        if not p[4] and v.lr[0] != v.lr[1]:
                            g = self._gain(); p[0].set_volume(v.lr[0] * g, v.lr[1] * g)
                        p[4] = True
                        if p[0].get_queue() is None: p[0].queue(p[2])
                except pygame.error: pass
        if self.fade:                               # 0x8004C964
            t = self.fade; self.fade -= 1
            if self.fade == 3:
                # the voices keyed off at 60 have released by now on the console (the golem's
                # scream, keyed off 139 frames in: RMS ~100 of ~5000 left when the volume comes
                # back, BizHawk dump); the release renders (NNN_off.ogg) still sound here, and
                # came back at full volume before the victory piece
                for v in self.voices:
                    if v.rel:
                        try: v.ch.stop()
                        except pygame.error: pass
                self.master = 1.0
            elif self.fade == 60:
                self.master = 0.0
                self.music_stop(False); self.stop_all()
            elif self.fade > 60:
                self.master = (t - 61) * 127 // 60 / 127
            self.apply_volume()
        if self.emu_next is not None and self.emu_next.snd_seek_done(): self._hand_over()
        if self.emu is not None and self.music_on:       # a one-shot track has ended
            info = self.music_index.get(str(self.music), {})
            if info.get('kind') == 'once' and self.emu.snd_ticks() / 59.826 * 44100 >= info.get('samples', 0): self.music_on = False
        if self.music_on and self.on and self.emu is None:
            try:
                if not pygame.mixer.music.get_busy(): self.music_on = False
            except pygame.error: pass
