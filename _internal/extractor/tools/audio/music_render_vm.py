"""Renders every music track exactly as the game plays it: the game's own sound code runs in sndvm
(R3000 interpreter over ALUN_CD.EXE) against the runtime SPU, at the console's NTSC frame
rate (59.826 Hz ticks, 44.1 kHz output), master volume as the game sets it (no normalising).

Looping tracks become one OGG holding the start and one full pass of the loop, tagged
LOOPSTART / LOOPLENGTH (samples) so SDL_mixer loops it seamlessly; the loop is cut at the
sequencer's own loop-end jumps, so the reverb and release tails that carry over are the ones the
game has at that point.  One-shot tracks end when the sound has died away.
    python3 music_render_vm.py OUTDIR [ids...]"""
import json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_vm

QUALITY = '7'


def analyse(mid, frames):
    pcm, tr = music_vm.run(mid, frames)
    cnt = tr[:, 3].astype(np.int64)
    s = np.concatenate([[0], np.cumsum(cnt)])           # sample index at the start of each frame
    jumps = [i for i in range(1, len(tr)) if tr[i, 0] < tr[i - 1, 0]]
    ended = bool((tr[:, 1] == 0).any())
    return pcm, tr, s, jumps, ended


def write_ogg(path, pcm, tags):
    meta = []
    for k, v in tags.items(): meta += ['-metadata', f'{k}={v}']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', '44100', '-ac', '2', '-i', '-',
                    '-c:a', 'libvorbis', '-q:a', QUALITY] + meta + [path],
                   input=pcm.astype('<i2').tobytes(), check=True)


def render(mid, out):
    pcm, tr, s, jumps, ended = analyse(mid, 16000)
    if not ended and len(jumps) < 3:
        pcm, tr, s, jumps, ended = analyse(mid, 48000)
    info = dict(id=mid, peak=int(np.abs(pcm).max()))
    if ended:
        stop = int(np.argmax(tr[:, 1] == 0))
        a = np.abs(pcm.astype(np.int32)).max(axis=1)
        loud = np.nonzero(a[:s[stop] + 44100 * 20] > 2)[0]
        n = int(loud[-1]) + 1 + 441 if len(loud) else 0
        n = max(n, int(s[stop]))
        write_ogg(f'{out}/{mid:02d}.ogg', pcm[:n], {})
        info.update(kind='once', samples=n, end_frame=stop)
    elif len(jumps) >= 2:
        j1, j2 = jumps[0], jumps[1]
        a, b = int(s[j1]), int(s[j2])
        n = min(b - a, len(pcm) - b)
        err = float(np.sqrt(((pcm[b:b + n].astype(float) - pcm[a:a + n]) ** 2).mean())) if n > 0 else -1
        write_ogg(f'{out}/{mid:02d}.ogg', pcm[:b], {'LOOPSTART': a, 'LOOPLENGTH': b - a})
        info.update(kind='loop', samples=b, loop_start=a, loop_length=b - a, loop_frames=[j1, j2],
                    pass_frames=[int(x) for x in np.diff(jumps)], next_pass_rms_diff=round(err, 1))
    else:
        info.update(kind='unknown', jumps=jumps)
    return info


if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    ids = [int(x) for x in sys.argv[2:]] or list(range(1, 47))
    idx_path = f'{out}/index.json'
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    for mid in ids:
        info = render(mid, out)
        idx[str(mid)] = info
        json.dump(idx, open(idx_path, 'w'), indent=1)
        print(json.dumps(info), flush=True)
