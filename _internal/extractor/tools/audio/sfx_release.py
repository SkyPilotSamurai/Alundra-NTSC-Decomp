"""What a sound effect does after it is keyed off (StopSound 0x8004A7B4 / stop-all 0x80049E4C /
the fade's SpuSetKey(OFF): SsUtKeyOffV or a key-off, never a cut): the tone's ADSR release runs
and the reverb rings on.  For every sound that can be stopped while it still sounds (the
looping ones, and one-shots longer than half a second) this renders, through the same SPU as
sfx_render.py, the sound keyed on, then keyed off part-way:
  remake/assets/audio/sfx/NNN_off.ogg   from the key-off until silence (release + reverb tail)
and adds to index.json
  'release'  game frames from the key-off until the voices' envelopes reach 0 (dry render, no
             reverb): how long the game's voice table still holds the id after a stop-all /
             fade key-off (0x80049FDC clears it only at envelope 0)
  'off'      the key-off point used (samples after the key-on).
    python3 sfx_release.py [first last]"""
import json, sys
import numpy as np
import libsnd as L
from spu_replay import render, base_regs
from sfx_render import OUT, RATE, sound_events, ram_for, write_wav

SPF = RATE / 59.826                                 # samples per game frame


def renders(vab, rec, ram, koff):
    evs, kon, eon, loops, _ = sound_events(vab, rec)
    if not kon: return None
    keys = [(1, 0x1F801D88, kon & 0xFFFF), (1, 0x1F801D8A, kon >> 16),
            (koff, 0x1F801D8C, kon & 0xFFFF), (koff, 0x1F801D8E, kon >> 16)]
    wet = render(ram, [(0, a, v) for a, v in base_regs(eon)] + evs + keys, koff + RATE * 8)
    dry = render(ram, [(0, a, v) for a, v in base_regs(0)] + evs + keys, koff + RATE * 4)
    return wet, dry, loops


def main(first=1, last=None):
    last = L.SOUND_COUNT if last is None else last
    idx_path = OUT / 'index.json'
    index = json.loads(idx_path.read_text())
    vabs = {}; rams = {}
    for n in range(first, last + 1):
        e = index.get(str(n))
        if not e or e.get('seq', -1) != -1 or 'missing' in e: continue
        rec = L.sound_record(n)
        if rec['count'] <= 0: continue
        loops = bool(e.get('loop'))
        dry_len = e.get('dry') or 0
        if not loops and dry_len < RATE // 2: continue
        koff = RATE * 2 + RATE // 2 if loops else dry_len // 2
        b = rec['bank']
        if b not in vabs:
            vabs[b] = L.global_vab() if b == -1 else L.bank_vab(b); rams[b] = ram_for(vabs[b])
        r = renders(vabs[b], rec, rams[b], koff)
        if r is None: continue
        wet, dry, _ = r
        tail = wet[koff:]
        nz = np.nonzero(np.abs(tail.astype(np.int32)).max(axis=1) > 16)[0]
        tail = tail[:(nz[-1] + 64) if len(nz) else 0]
        dz = np.nonzero(np.abs(dry[koff:].astype(np.int32)).max(axis=1) > 0)[0]
        rel = int(dz[-1] + 1) if len(dz) else 0
        if len(tail): write_wav(OUT / f'{n:03d}_off.wav', tail)
        e['release'] = int(-(-rel // SPF)); e['off'] = koff
        print(n, 'release', e['release'], 'frames, tail', round(len(tail) / RATE, 2), 's', flush=True)
    idx_path.write_text(json.dumps(index, indent=0))


if __name__ == '__main__':
    main(*[int(x) for x in sys.argv[1:3]])
