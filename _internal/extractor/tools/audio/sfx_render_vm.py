"""Every sound-effect record played through the game's own PlaySound (0x8004A128) in sndvm:
ALUN_CD.EXE's sound start-up, the record's map bank loaded by the game's loader (0x80049820),
PlaySound(n), then the libsnd vsync tick and the sound manager's upkeep every frame, into the
runtime SPU.  Sequence sounds (records with a SEQ, e.g. 73, 74, 962) play their sequence.
Writes OUT/NNN.ogg, OUT/NNN_loop.ogg for sounds still sounding after 8 s (the first file is then
the 2 s before the loop) and OUT/index.json {id: {bank, next, voices, loop, frames, seq}}.
    python3 sfx_render_vm.py OUT [first last]"""
import json, math, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import libsnd as L
from music_vm import VM, EXE, SOUND
import sfx_render as SR

RATE = 44100
SPF = 44100.0 * 3413.0 * 263.0 / 53693181.818
TMP = Path(tempfile.gettempdir()) / 'alundra_sfxvm'


def play(n, bank, frames):
    TMP.mkdir(exist_ok=True)
    tag = f's{n}' + (f'@{bank}' if bank >= 0 else '')
    raw, tr = TMP / f'{n}.raw', TMP / f'{n}.tr'
    subprocess.run([str(VM), str(EXE), str(SOUND), tag, str(frames), str(raw), str(tr), '-', '1'], check=True)
    pcm = np.fromfile(raw, dtype='<i2').reshape(-1, 2); t = np.fromfile(tr, dtype='<u4').reshape(-1, 4)
    raw.unlink(); tr.unlink()
    return pcm, t


def loop_length(n, rec):
    """Output samples for a seamless loop: a whole number of the looping sample's periods (as
    sfx_render.py), or 6 s when several tones loop."""
    try:
        vab = L.global_vab() if rec['bank'] == -1 else L.bank_vab(rec['bank'])
        _, _, _, _, tones = SR.sound_events(vab, rec)
    except Exception:
        tones = []
    looping = [(t, p, d) for t, p, d in tones if SR.vag_loops(d)[0]]
    if len(looping) != 1: return RATE * 6
    t, pitch, data = looping[0]
    a, b = SR.loop_region(data)
    P = (b - a) * 4096 / max(1, pitch)
    k = 1
    while k * P < RATE * 2 or abs(k * P - round(k * P)) > 0.02:
        k += 1
        if k > 400: return int(round(max(1, int(RATE * 4 / P)) * P))
    return int(round(k * P))


def render(n, out):
    rec = L.sound_record(n)
    if rec['bank'] == -2: return None
    bank = rec['bank']
    seq = rec['seq'] != -1
    pcm, tr = play(n, bank, int(15 * 60 if seq else 8 * 60))
    if not np.abs(pcm).any(): return None
    info = dict(bank=bank, next=rec['next'], voices=rec['voices'])
    if seq: info['seq'] = rec['seq']
    still = tr[-1, 2] != 0
    if not still:
        mag = np.abs(pcm.astype(np.int32)).max(axis=1)
        nz = np.nonzero(mag > 16)[0]
        end = int(nz[-1]) + 64 if len(nz) else 0
        SR.write_wav(out / f'{n:03d}.wav', pcm[:end])
        info.update(loop=False, frames=end)
        return info
    T0 = RATE * 2; X = 2048
    Lp = loop_length(n, rec)
    need = T0 + Lp + X
    pcm, tr = play(n, bank, int(math.ceil(need / SPF)) + 2)
    pcm = pcm[:need].astype(np.float64)
    intro = pcm[:T0]; loop = pcm[T0:T0 + Lp].copy(); tail = pcm[T0 + Lp:T0 + Lp + X]
    w = np.linspace(0, 1, X)[:, None]
    loop[:X] = loop[:X] * w + tail * (1 - w)
    SR.write_wav(out / f'{n:03d}.wav', np.clip(intro, -32768, 32767))
    SR.write_wav(out / f'{n:03d}_loop.wav', np.clip(loop, -32768, 32767))
    info.update(loop=True, frames=T0)
    return info


if __name__ == '__main__':
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    first, last = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1, L.SOUND_COUNT)
    idx_path = out / 'index.json'
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    for n in range(first, last + 1):
        try: info = render(n, out)
        except subprocess.CalledProcessError as e: print(n, 'failed', e); continue
        if info is None: index.pop(str(n), None); continue
        index[str(n)] = info
        print(n, info, flush=True)
    idx_path.write_text(json.dumps(index, indent=0))
