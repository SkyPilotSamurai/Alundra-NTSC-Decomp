"""Renders a music track with the game's own sound code: sndvm runs ALUN_CD.EXE's libsnd start-up,
music load (script command A7) and vsync tick in an R3000 interpreter against the runtime SPU.
    python3 music_vm.py ID FRAMES [out.wav]"""
import os, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXE = ROOT / 'private-inputs/disc/ALUN_CD.EXE'
SOUND = ROOT / 'private-inputs/disc/DATA/SOUND.BIN'
VM = HERE / 'sndvm' / ('sndvm.exe' if os.name == 'nt' else 'sndvm')
TMP = Path(tempfile.gettempdir()) / 'alundra_sndvm'


def run(mid, frames, ntsc=1, log=False):
    """-> (pcm int16 [n,2], trace u32 [frames,4]: read pointer, seq flags, voices sounding, samples)"""
    if not VM.exists(): subprocess.run([str(HERE / 'sndvm' / 'build.sh')], check=True)
    TMP.mkdir(exist_ok=True)
    p = TMP / f'm{mid}'
    subprocess.run([str(VM), str(EXE), str(SOUND), str(mid), str(frames), f'{p}.raw', f'{p}.trace',
                    f'{p}.log' if log else '-', str(ntsc)], check=True)
    pcm = np.fromfile(f'{p}.raw', dtype='<i2').reshape(-1, 2)
    tr = np.fromfile(f'{p}.trace', dtype='<u4').reshape(-1, 4)
    os.remove(f'{p}.raw'); os.remove(f'{p}.trace')
    return pcm, tr


def write_wav(path, pcm):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100); w.writeframes(pcm.astype('<i2').tobytes())


if __name__ == '__main__':
    mid, frames = int(sys.argv[1]), int(sys.argv[2])
    pcm, tr = run(mid, frames)
    jumps = [i for i in range(1, len(tr)) if tr[i, 0] < tr[i - 1, 0]]
    print('samples', len(pcm), 'peak', int(np.abs(pcm).max()), 'loop jumps at frames', jumps[:8])
    if len(sys.argv) > 3: write_wav(sys.argv[3], pcm)
