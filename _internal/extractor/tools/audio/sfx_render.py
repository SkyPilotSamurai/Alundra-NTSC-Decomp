"""Every sound-effect record (0x800AA150, 963 of them) rendered through the game's own path:
libsnd key-on values (libsnd.py) into the runtime's SPU (spurender), with the game's main
volume and reverb, so a WAV played at full volume is as loud as the game plays it.
Writes remake/assets/audio/sfx/NNN.ogg (record NNN; the global bank's and the 70 map banks'),
NNN_loop.ogg for sounds that loop until stopped (the first file is then the part before the loop),
and index.json {id: {bank, loop, voices, frames}}.
    python3 sfx_render.py [first last]"""
import json, struct, sys, wave
from pathlib import Path
import numpy as np
import libsnd as L
from spu_replay import render, base_regs

OUT = L.ROOT / 'remake' / 'assets' / 'audio' / 'sfx'
BASE = 0x1010                      # where the bank's samples go in SPU RAM (below the reverb area)
RATE = 44100


def vag_loops(data):
    for o in range(0, len(data) - 15, 16):
        f = data[o + 1]
        if f & 1: return bool(f & 2), o
    return False, len(data)


def loop_region(data):
    """(loop start sample, loop end sample) of a looping VAG (source samples)."""
    start = 0
    for o in range(0, len(data) - 15, 16):
        f = data[o + 1]
        if f & 4: start = o // 16 * 28
        if f & 1: return start, (o // 16 + 1) * 28
    return 0, len(data) // 16 * 28


def write_wav(path, pcm):
    """Written as Ogg Vorbis (quality 6) next to where a .wav would go."""
    import subprocess
    path = Path(path).with_suffix('.ogg')
    raw = np.ascontiguousarray(np.clip(pcm, -32768, 32767).astype('<i2')).tobytes()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(RATE), '-ac', '2', '-i', '-',
                    '-c:a', 'libvorbis', '-q:a', '6', str(path)], input=raw, check=True)


def sound_events(vab, rec):
    prog = vab.prog(rec['prog']); evs = []; kon = 0; eon = 0; loops = False; tones = []
    for k in range(max(1, rec['count'])):
        t = vab.tone(rec['prog'], rec['tone'] + k)
        if t['vag'] <= 0 or t['vag'] > vab.nvag: continue
        v = k
        vl, vr = L.key_volume(127, vab, prog, t)
        pitch = L.note_pitch(rec['note'], 0, t)
        addr = BASE + vab.vag_offset(t['vag'])
        r = 0x1F801C00 + v * 16
        evs += [(0, r, vl), (0, r + 2, vr), (0, r + 4, pitch), (0, r + 6, addr >> 3), (0, r + 8, t['adsr1']), (0, r + 10, t['adsr2'])]
        kon |= 1 << v
        if t['mode'] & 4: eon |= 1 << v
        lp, _ = vag_loops(vab.vag(t['vag']))
        loops |= lp
        tones.append((t, pitch, vab.vag(t['vag'])))
    return evs, kon, eon, loops, tones


def ram_for(vab):
    ram = bytearray(0x80000)
    body = vab.body_bytes()
    ram[BASE:BASE + len(body)] = body
    return bytes(ram)


def render_sound(vab, rec, ram):
    evs, kon, eon, loops, tones = sound_events(vab, rec)
    if not kon: return None
    ev = [(0, a, v) for a, v in base_regs(eon)] + evs + [(1, 0x1F801D88, kon & 0xFFFF), (1, 0x1F801D8A, kon >> 16)]
    if not loops:
        pcm = render(ram, ev, RATE * 8)
        mag = np.abs(pcm.astype(np.int32)).max(axis=1)
        nz = np.nonzero(mag > 16)[0]
        end = (nz[-1] + 64) if len(nz) else 0
        return {'pcm': pcm[:end], 'loop': None}
    T0 = RATE * 2
    if len(tones) == 1:
        t, pitch, data = tones[0]
        a, b = loop_region(data)
        P = (b - a) * 4096 / max(1, pitch)
        k = 1
        while k * P < RATE * 2 or abs(k * P - round(k * P)) > 0.02: k += 1
        if k > 400: k = max(1, int(RATE * 4 / P))
        Lp = int(round(k * P))
    else:
        Lp = RATE * 6
    X = 2048
    pcm = render(ram, ev, T0 + Lp + X).astype(np.float64)
    intro = pcm[:T0]
    loop = pcm[T0:T0 + Lp].copy()
    tail = pcm[T0 + Lp:T0 + Lp + X]
    w = np.linspace(0, 1, X)[:, None]
    loop[:X] = loop[:X] * w + tail * (1 - w)          # the loop's start blends with what follows its end
    return {'pcm': intro, 'loop': loop}


def main(first=1, last=None):
    OUT.mkdir(parents=True, exist_ok=True)
    last = L.SOUND_COUNT if last is None else last
    idx_path = OUT / 'index.json'
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    vabs = {}; rams = {}
    for n in range(first, last + 1):
        rec = L.sound_record(n)
        if rec['bank'] == -2: continue
        if rec['seq'] != -1:
            index[str(n)] = dict(bank=rec['bank'], seq=rec['seq'], next=rec['next'], voices=rec['voices'], missing='sequence'); continue
        b = rec['bank']
        try:
            if b not in vabs:
                vabs[b] = L.global_vab() if b == -1 else L.bank_vab(b)
                rams[b] = ram_for(vabs[b])
            res = render_sound(vabs[b], rec, rams[b])
        except Exception as ex:
            print(n, 'failed', ex); continue
        if res is None: continue
        write_wav(OUT / f'{n:03d}.wav', np.clip(res['pcm'], -32768, 32767))
        if res['loop'] is not None: write_wav(OUT / f'{n:03d}_loop.wav', np.clip(res['loop'], -32768, 32767))
        index[str(n)] = dict(bank=b, next=rec['next'], voices=rec['voices'], loop=res['loop'] is not None,
                             frames=int(len(res['pcm'])))
        print(n, 'bank', b, 'loop' if res['loop'] is not None else '', len(res['pcm']), flush=True)
    idx_path.write_text(json.dumps(index, indent=0))


if __name__ == '__main__':
    a = [int(x) for x in sys.argv[1:3]]
    main(*a)
