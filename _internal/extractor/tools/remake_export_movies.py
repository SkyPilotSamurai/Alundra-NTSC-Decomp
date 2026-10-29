"""The four FMV movies (MOVIE/*.MOV, PlayStation STR: MDEC video at 15 frames a second with
interleaved XA audio) for the remake's own player, decoded with ffmpeg's psxstr reader:

  remake/assets/movies/NAME_K.zip  frames/00000.jpg ... (every MDEC frame, its native size, in packs
                                   of at most 24 MB; movies.json 'packs' = [first, end) per pack)
  remake/assets/movies/NAME.ogg   the XA audio (37.8 kHz stereo, resampled to 44.1 kHz)
  remake/assets/movies/movies.json  per movie: frames, width, height, fps

The STR sector dumps (NAME.str) come from tools/remake_extract_disc.py movies.  Where and how
long each movie plays is the game's own (remake/movie.py: the calls of the movie player
SLUS_005.53 0x80027F5C and END.EXE 0x80023CC4).
Run: python tools/remake_export_movies.py [NAME ...]"""
import io, json, subprocess, sys, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'remake' / 'assets' / 'movies'


def frames(src):
    """JPEG frames of the MDEC stream, one per decoded frame (no frame-rate conversion).
    -fps_mode is ffmpeg 5.1+; older builds (e.g. 4.2) take -vsync 0 for the same thing."""
    for sync in (['-fps_mode', 'passthrough'], ['-vsync', '0']):
        p = subprocess.Popen(['ffmpeg', '-v', 'error', '-f', 'psxstr', '-i', str(src), '-map', '0:v',
                              *sync, '-f', 'image2pipe', '-c:v', 'mjpeg', '-q:v', '3', '-'],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        data = p.stdout.read(); p.wait()
        if data.find(bytes([0xFF, 0xD8])) >= 0: break
    out = []; i = 0
    while True:
        a = data.find(b'\xff\xd8', i)
        if a < 0: break
        b = data.find(b'\xff\xd9', a)
        if b < 0: break
        out.append(data[a:b + 2]); i = b + 2
    return out


def export(name):
    src = DIR / f'{name}.str'
    if not src.exists(): print(name, 'no', src.name); return None
    jpgs = frames(src)
    from PIL import Image
    w, h = Image.open(io.BytesIO(jpgs[0])).size
    for old in DIR.glob(f'{name}*.zip'): old.unlink()
    parts = []; i = 0
    while i < len(jpgs):                                  # packs of at most ~24 MB (the frames in order)
        k = len(parts); size = 0; first = i
        with zipfile.ZipFile(DIR / f'{name}_{k}.zip', 'w', zipfile.ZIP_STORED) as z:
            while i < len(jpgs) and size + len(jpgs[i]) < 24_000_000:
                z.writestr(f'frames/{i:05d}.jpg', jpgs[i]); size += len(jpgs[i]); i += 1
        parts.append([first, i])
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'psxstr', '-i', str(src), '-map', '0:a', '-ar', '44100',
                    '-c:a', 'libvorbis', '-q:a', '6', str(DIR / f'{name}.ogg')], check=True)
    info = {'frames': len(jpgs), 'width': w, 'height': h, 'fps': 15, 'packs': parts}
    print(name, info, flush=True)
    return info


def main(names):
    f = DIR / 'movies.json'
    meta = json.loads(f.read_text()) if f.exists() else {}
    for n in names or [p.stem for p in sorted(DIR.glob('*.str'))]:
        info = export(n)
        if info: meta[n] = info
    f.write_text(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
