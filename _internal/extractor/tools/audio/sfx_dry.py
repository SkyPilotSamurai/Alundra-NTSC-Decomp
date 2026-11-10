"""How long each sound effect's voices sound, without the reverb (index.json 'dry', samples at
44.1 kHz; absent for looping sounds, which sound until stopped).

PlaySound 0x8004A128 refuses a sound when its record's voice limit (+0x10) of voices still
sound.  'Still sound' is the voice table 0x801EFE68: 0x80049FDC clears an entry when
SpuGetAllKeysStatus (0x8009AE74) says the voice is off with its envelope at 0, i.e. when the
voice itself ends (sample end or envelope at 0).  The rendered files (sfx_render.py) carry
the reverb's tail as well, often far longer (sound 82, Melzas's talk sound: 0.25 s of voice,
1.9 s with the tail), so the remake counts a voice as sounding only for its dry length.
    python3 sfx_dry.py [first last]"""
import json, sys
import numpy as np
import libsnd as L
from spu_replay import render, base_regs
from sfx_render import OUT, RATE, sound_events, ram_for


def dry_length(vab, rec, ram):
    evs, kon, _eon, loops, _ = sound_events(vab, rec)
    if not kon or loops: return None
    ev = [(0, a, v) for a, v in base_regs(0)] + evs + [(1, 0x1F801D88, kon & 0xFFFF), (1, 0x1F801D8A, kon >> 16)]
    pcm = render(ram, ev, RATE * 8)
    nz = np.nonzero(np.abs(pcm.astype(np.int32)).max(axis=1) > 0)[0]
    return int(nz[-1] + 1) if len(nz) else 0


def main(first=1, last=None):
    last = L.SOUND_COUNT if last is None else last
    idx_path = OUT / 'index.json'
    index = json.loads(idx_path.read_text())
    vabs = {}; rams = {}
    for n in range(first, last + 1):
        e = index.get(str(n))
        if not e or e.get('loop') or 'seq' in e: continue
        rec = L.sound_record(n); b = rec['bank']
        try:
            if b not in vabs:
                vabs[b] = L.global_vab() if b == -1 else L.bank_vab(b)
                rams[b] = ram_for(vabs[b])
            d = dry_length(vabs[b], rec, rams[b])
        except Exception as ex:
            print(n, 'failed', ex); continue
        if d is None: continue
        e['dry'] = d
        if n % 50 == 0: print(n, d, e.get('frames'), flush=True)
    idx_path.write_text(json.dumps(index, indent=0))


if __name__ == '__main__':
    main(*[int(x) for x in sys.argv[1:3]])
