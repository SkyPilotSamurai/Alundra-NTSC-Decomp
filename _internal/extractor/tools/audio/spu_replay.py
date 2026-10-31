"""Replays a recorded SPU capture (oracle t_spucap.py) through the offline SPU (spurender) and
compares the result with the game's own audio.
    python3 spu_replay.py NAME"""
import json, os, struct, subprocess, sys, wave
import numpy as np
HOME = os.path.expanduser('~'); D = HOME + '/us/audio/'; SPU = HOME + '/us/spurender/spurender'
_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sndvm', 'spurender.exe' if os.name == 'nt' else 'spurender')
if os.path.exists(_LOCAL): SPU = _LOCAL          # (built from sndvm/spurender.c: same runtime SPU)
REVERB_STUDIO_LARGE = [0xe3, 0xa9, 0x6f60, 0x4fa8, 0xbce0, 0x4510, 0xbef0, 0xa680, 0x5680, 0x52c0, 0xdfb, 0xb58, 0xd09, 0xa3c,
                       0xbd9, 0x973, 0xb59, 0x8da, 0x8d9, 0x5e9, 0x7ec, 0x4b0, 0x6ef, 0x3d2, 0x5ea, 0x31d, 0x31c, 0x238, 0x154, 0xaa,
                       0x8000, 0x8000]


def base_regs(eon=0xFFFFFF, depth=0x2A00, mbase=0x79020):
    """What the game sets at boot (0x8004946C): reverb Studio Large, depth 0x2A00, main 0x3FFF."""
    w = [(0x1F801DAA, 0xC083), (0x1F801D80, 0x3FFF), (0x1F801D82, 0x3FFF), (0x1F801DB0, 0x7FFF), (0x1F801DB2, 0x7FFF),
         (0x1F801DA2, mbase >> 3), (0x1F801D84, depth), (0x1F801D86, depth),
         (0x1F801D98, eon & 0xFFFF), (0x1F801D9A, eon >> 16)]
    w += [(0x1F801DC0 + 2 * i, v) for i, v in enumerate(REVERB_STUDIO_LARGE)]
    return w


def render(ram, events, frames, out=None, voices=None):
    """events: [(sample, addr, value)] -> int16 stereo array.  voices: states to resume
    (24 x [active, start, cur, repeat, sample_idx, phase, env, adsr_phase])."""
    import tempfile
    tmp = out or os.path.join(tempfile.gettempdir(), 'spu_r')
    open(tmp + '.ram', 'wb').write(ram)
    args = []
    if voices is not None:
        with open(tmp + '.vs', 'wb') as f:
            for r in voices: f.write(struct.pack('<8I', *[x & 0xFFFFFFFF for x in r]))
        args = [tmp + '.vs']
    with open(tmp + '.ev', 'wb') as f:
        for t, a, v in sorted(events, key=lambda e: e[0]):   # stable: same-sample writes keep their order
            f.write(struct.pack('<QII', t, a, v))
    subprocess.run([SPU, tmp + '.ram', tmp + '.ev', str(frames), tmp + '.raw'] + args, check=True)
    return np.fromfile(tmp + '.raw', dtype='<i2').reshape(-1, 2)


def read_wav(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, w.getnchannels())


def replay(name):
    cap = json.load(open(D + name + '_cap.json'))
    ram = open(D + name + '_spuram.bin', 'rb').read()
    st = cap['status']
    ev = [(0, a, v) for a, v in base_regs(int(st['eon'], 16), mbase=int(st['reverb_mbase'], 16))]
    states = []
    for vs in cap['voices']['voices']:
        r = 0x1F801C00 + vs['v'] * 16
        for o, k in ((0, 'vol_l'), (2, 'vol_r'), (4, 'pitch'), (6, 'start'), (8, 'adsr_lo'), (10, 'adsr_hi'), (14, 'loop')):
            v = int(vs[k], 16)
            ev.append((0, r + o, v >> 3 if k in ('start', 'loop') else v))
        states.append([vs['active'], int(vs['start'], 16), int(vs['cur_addr'], 16), int(vs['repeat_addr'], 16),
                       vs['sample_idx'], int(vs['phase'], 16), int(vs['env'], 16), vs['env_phase']])
    a0 = cap['a0']
    ev += [(max(0, e[-4] - a0), e[-2], e[-1]) for e in sorted(cap['events'])]
    n = cap['b0'] - a0
    return render(ram, ev, n, voices=states), read_wav(D + name + '.wav')[:n]


if __name__ == '__main__':
    mine, game = replay(sys.argv[1])
    n = min(len(mine), len(game)); mine, game = mine[:n].astype(float), game[:n].astype(float)
    W = 22050
    for i in range(0, n - W, W):
        a, b = mine[i:i + W], game[i:i + W]
        ra, rb = np.sqrt((a ** 2).mean()), np.sqrt((b ** 2).mean())
        c = np.corrcoef(a[:, 0], b[:, 0])[0, 1] if ra and rb else 0
        print(f'{i / 44100:5.1f}s  rms mine {ra:7.1f}  game {rb:7.1f}  corr {c:+.3f}')
