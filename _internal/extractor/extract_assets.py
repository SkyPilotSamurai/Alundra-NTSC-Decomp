"""Builds the remake's assets/ folder from your own Alundra (USA) v1.1 disc image.

    python extractor/extract_assets.py [path to the .cue or .bin]

Without a path a file dialog asks for it.  Nothing from the game is in this repository: every
map, sprite, sound and text the remake uses is read from your disc here, with the same tools
that made the original export (extractor/tools).  Those tools find their input and output
relative to this folder (extractor/private-inputs/disc, extractor/remake/assets); when all
steps are done the result is moved to ../assets.

Needs: Python with numpy and Pillow (installed into the remake's .venv on first use) and
ffmpeg on the PATH (sounds, music, movies).  Takes about 30-60 minutes.  A log is written to
extractor/extract.log."""
import hashlib, json, os, shutil, struct, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent                  # = the tools' ROOT
REMAKE = HERE.parent
TOOLS = HERE / 'tools'
DISC = HERE / 'private-inputs' / 'disc'
WORK = HERE / 'remake' / 'assets'                        # where the tools write
FINAL = Path(os.environ.get('ALUNDRA_FINAL') or REMAKE / 'assets')   # (override: development trials)
LOG = HERE / 'extract.log'
BIN_NAME = 'Alundra (USA) (Rev 1).bin'                   # the name the tools read raw sectors from

# Alundra (USA) v1.1 (SLUS-00553, Rev 1): the files the tools read, by SHA-256
KNOWN = {
    'SYSTEM.CNF': '6ae97af40470fdd87f04272d811d29b3d0df257fa499fa2444af6abec265ce55',
    'SLUS_005.53': '02f5a675bfb72a849fa18ece27be1131301007cd0f4be9bf717d2f0ee20807b4',
    'ALUN_CD.EXE': '12f12eafa3e34dac6aca40b52f4f85f95811d40de7e48db77c52a35aa18833a3',
    'CLOSING.EXE': '0006905c510d65b649cf579c086812d3b6fa7836449222d9d9edb4da440dccba',
    'END.EXE': 'e663e6ce24a824981ea4ec37fd42e9c84e8238de808b07dd9ef96ca98b15761b',
    'DATA/BALANCE.BIN': '6c3f125fc7a8709e75539df9b62f1cbeeec6bc48e7140c2e6d1575d4c642a9b2',
    'DATA/DATAS.BIN': '327c5226195991a385250b54f6d7adbd019e45fb0963c62a22268f866ebf25ce',
    'DATA/ETC_USA.R': '6a561dc19076a6825bb55a38c8d189db91fb4807f1d7221a04edec20a3cde7e6',
    'DATA/SOUND.BIN': 'dad81faaa9257c088215faae5142e00007c287ba9395bd10e197a0d396d14948',
}


PROGRESS = None                                         # the exe's window: PROGRESS(step, steps, label)


def log(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')


# ------------------------------------------------------------------ the disc
def pick_disc():
    if len(sys.argv) > 1: return Path(sys.argv[1])
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        p = filedialog.askopenfilename(title='Your Alundra (USA) disc image (.cue or .bin)',
                                       filetypes=[('Disc image', '*.cue *.bin'), ('All files', '*.*')])
        root.destroy()
        return Path(p) if p else None
    except Exception:
        p = input('Path to your Alundra (USA) .cue or .bin: ').strip().strip('"')
        return Path(p) if p else None


def bin_of(path):
    """A .cue's (first) data track file, or the .bin itself."""
    if path.suffix.lower() != '.cue': return path
    for line in path.read_text(errors='replace').splitlines():
        line = line.strip()
        if line.upper().startswith('FILE'):
            name = line[line.index('"') + 1:line.rindex('"')] if '"' in line else line.split()[1]
            return path.parent / name
    raise SystemExit('The .cue file names no data track.')


class Iso:
    """ISO 9660 on a raw MODE2/2352 track (the data starts 24 bytes into each sector)."""
    def __init__(self, path):
        self.f = open(path, 'rb')
        if self.sector(16)[1:6] != b'CD001': raise SystemExit(f'{path.name} is not a raw (2352-byte sector) PlayStation disc image.')
        root = self.sector(16)[156:190]
        self.files = {}
        self._walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')

    def sector(self, n):
        self.f.seek(n * 2352 + 24); return self.f.read(2048)

    def _walk(self, ext, size, prefix):
        data = b''.join(self.sector(ext + i) for i in range((size + 2047) // 2048)); i = 0
        while i < len(data):
            l = data[i]
            if l == 0: i = (i // 2048 + 1) * 2048; continue
            e, s = struct.unpack_from('<I', data, i + 2)[0], struct.unpack_from('<I', data, i + 10)[0]
            fl, nl = data[i + 25], data[i + 32]; name = data[i + 33:i + 33 + nl]
            if name not in (b'\0', b'\1'):
                n = name.decode('latin1').split(';')[0]
                if fl & 2: self._walk(e, s, prefix + n + '/')
                else: self.files[prefix + n] = (e, s)
            i += l

    def read(self, name):
        lba, size = self.files[name]
        out = bytearray()
        for i in range((size + 2047) // 2048): out += self.sector(lba + i)
        return bytes(out[:size])


def _disc_files(image):
    """The disc's files the tools read ({name: bytes}) and what is wrong with them (list)."""
    b = bin_of(image)
    if not b.exists(): raise SystemExit(f'Cannot find {b}')
    iso = Iso(b)
    files, bad = {}, []
    for name, want in KNOWN.items():
        if name not in iso.files: bad.append(f'{name} missing'); continue
        data = iso.read(name)
        if hashlib.sha256(data).hexdigest() != want: bad.append(f'{name} differs')
        files[name] = data
    return b, files, bad


def check_disc(image):
    """None when image is Alundra (USA) v1.1, else why not (one line or a few).  Writes nothing."""
    try:
        _, _, bad = _disc_files(Path(image))
    except SystemExit as e:
        return str(e.code)
    except (OSError, ValueError, struct.error) as e:
        return f'{Path(image).name} could not be read as a PlayStation disc image ({e}).'
    if bad:
        return ('This is not Alundra (USA) v1.1 (SLUS-00553, Rev 1), the version the remake is built on:\n  '
                + '\n  '.join(bad))
    return None


def unpack_disc(image):
    b = bin_of(image)
    log(f'Reading {b.name}')
    b, files, bad = _disc_files(image)
    if bad:
        raise SystemExit('This is not Alundra (USA) v1.1 (SLUS-00553, Rev 1), the version the remake is built on:\n  '
                         + '\n  '.join(bad))
    (DISC / 'DATA').mkdir(parents=True, exist_ok=True)
    for name, data in files.items(): (DISC / name).write_bytes(data)
    target = DISC / BIN_NAME                                  # the movies and XA streams read raw sectors from it
    if target.exists(): target.unlink()
    try: os.link(b, target)
    except OSError: log('Copying the disc image (no hard link possible)...'); shutil.copyfile(b, target)
    (DISC / 'Alundra (USA) (Rev 1).cue').write_text(f'FILE "{BIN_NAME}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
    log('Disc checked: Alundra (USA) v1.1')


# ------------------------------------------------------------------ the steps
TRACE = os.environ.get('ALUNDRA_TRACE')                 # development: list every file the steps open


def _trace_hook():
    if not TRACE: return
    here = str(HERE).lower()
    def hook(ev, a):
        if ev == 'open' and a and isinstance(a[0], (str, bytes, os.PathLike)):
            p = os.path.abspath(os.fsdecode(a[0]))
            if p.lower().startswith(here):
                with open(TRACE, 'a', encoding='utf-8') as f: f.write(p + '\n')
    sys.addaudithook(hook)


FROZEN = getattr(sys, 'frozen', False)                 # inside Alundra Remake.exe (launcher/exe_main.py)
PY = [sys.executable, '--run-script'] if FROZEN else [sys.executable, '-u']   # the exe runs a tool script itself


def run(script, *args, name=None):
    t = time.time()
    log(f'{name or script} ...')
    cmd = [*PY, str(TOOLS / script), *map(str, args)]
    if TRACE and not FROZEN:
        cmd = [sys.executable, '-u', '-c', 'import sys,runpy; sys.path.insert(0, sys.argv[1]); import extract_assets as E; '
               'E._trace_hook(); s = sys.argv[2]; sys.argv = sys.argv[2:]; sys.path.insert(0, str(__import__("pathlib").Path(s).parent)); '
               'runpy.run_path(s, run_name="__main__")', str(HERE), str(TOOLS / script), *map(str, args)]
    p = subprocess.run(cmd, cwd=HERE,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    with open(LOG, 'a', encoding='utf-8') as f: f.write(p.stdout[-20000:] + '\n')
    if p.returncode != 0:
        tail = '\n'.join(p.stdout.strip().splitlines()[-6:])
        raise SystemExit(f'{name or script} failed (exit {p.returncode}):\n{tail}\nFull output: {LOG}')
    log(f'{name or script} done ({time.time() - t:.0f} s)')


def _maps_worker(first, last):
    """One process: maps first..last (export_map, tiles, warps) - each writes only its own folder."""
    sys.path.insert(0, str(TOOLS))
    os.chdir(HERE); _trace_hook()
    from remake_export import export_map, session
    import remake_export_all as A
    s = session(); s.data_frozen = True
    done, failed = {}, []
    for m in range(first, last + 1):
        try:
            export_map(s, m, {}, force=True); A.export_tiles(s, m); A.export_warps(s, m)
            done[m] = json.loads((A.OUT / 'maps' / f'{m:03d}' / 'map.json').read_text())['name']
        except Exception as e:
            failed.append((m, f'{type(e).__name__}: {e}'))
    return done, failed


def export_maps(workers):
    sys.path.insert(0, str(TOOLS))
    from remake_export import export_sprite, session
    import remake_export_all as A
    t = time.time(); log('Global sprites ...')
    s = session()
    for cat in range(256):
        try: export_sprite(s, A.GLOBAL_SOURCE_MAP, cat, A.OUT / 'sprites' / 'global' / f'{cat:03d}', None)
        except Exception: pass                                 # not every number is a sprite
    total = A.map_count(s); del s
    log(f'Global sprites done ({time.time() - t:.0f} s); {total} maps on {workers} processes ...')
    t = time.time()
    chunks = [(a, min(total - 1, a + 7)) for a in range(0, total, 8)]
    names, failed, n = {}, [], 0
    with ProcessPoolExecutor(workers) as ex:
        for fut in as_completed([ex.submit(_maps_worker, a, b) for a, b in chunks]):
            d, f = fut.result(); names.update(d); failed += f; n += len(d) + len(f)
            log(f'  maps {n} of {total}')
    sprite_names = {}
    for folder in sorted((A.OUT / 'sprites' / 'global').glob('[0-9][0-9][0-9]')):
        try: sprite_names[int(folder.name)] = json.loads((folder / 'animations.json').read_text()).get('name')
        except (OSError, ValueError): pass
    (A.OUT / 'names.json').write_text(json.dumps({'maps': dict(sorted(names.items())), 'sprites': sprite_names}, indent=1), encoding='utf-8')
    if failed:
        (A.OUT / 'export_failures.txt').write_text('\n'.join(f'map {m}: {e}' for m, e in sorted(failed)))
        log(f'{len(failed)} maps failed, see assets/export_failures.txt')
        raise SystemExit(f'{len(failed)} of {total} maps failed, first: map {failed[0][0]}: {failed[0][1]}')
    log(f'Maps done ({time.time() - t:.0f} s)')


STEPS = [
    # (label, function or (script, args...))
    # first the window graphics and the font (disc only, a few seconds): the exe's progress window
    # is drawn with them (the message scroll, the game font)
    ('window graphics', ('remake_extract_disc.py', 'ui')),
    ('fonts and HUD', ('remake_ui_export.py',)),
    ('maps', None),
    ('map data', ('remake_extract_data.py', 0, 482)),
    ('shared sprite info', 'global_info'),
    ('map sprite info', 'map_sprite_info'),
    ('spawned sprites', 'spawned_sprites'),
    ('tile animations', ('remake_tile_anims.py', 0, 482)),
    ('background layers', ('remake_export_lining.py', 0, 482)),
    ('sprite blending (shared)', ('blend_frames.py', 'global')),
    ('sprite blending (maps)', ('blend_frames.py', 0, 482)),
    ('sprite sort keys (shared)', ('blend_frames.py', 'sort', 'global')),
    ('sprite sort keys (maps)', ('blend_frames.py', 'sort', 0, 482)),
    ('effects (shared)', ('export_effects.py', 'global')),
    ('effects (maps)', ('export_effects.py', 0, 482)),
    ('effect sort keys (shared)', ('export_effects.py', 'sort', 'global')),
    ('effect sort keys (maps)', ('export_effects.py', 'sort', 0, 482)),
    ('animation physics (shared)', ('anim_tails.py', 'global')),
    ('animation physics (maps)', ('anim_tails.py', 0, 482)),
    ('overflow animations (shared)', ('remake_overflow_anims.py', 'global')),
    ('overflow animations (maps)', ('remake_overflow_anims.py', 0, 482)),
    ('attack boxes (shared)', ('remake_attack_boxes.py', 'global')),
    ('attack boxes (maps)', ('remake_attack_boxes.py', 'maps', 0, 483)),
    ('portraits', ('remake_export_portraits.py', 0, 482)),
    ('menu icons', ('remake_export_menu_icons.py',)),
    ('menu text',('remake_extract_disc.py', 'text')),
    ('item text table', ('remake_export_etc.py',)),
    ('shared strings', ('remake_export_texts.py',)),
    ('items', ('remake_export_items.py',)),
    ('balance', ('remake_export_balance.py',)),
    ('map sizes', ('remake_export_map_sizes.py',)),
    ('boot program', ('remake_export_boot.py',)),
    ('title screen', ('remake_export_title.py',)),
    ('ending', ('remake_export_ending.py',)),
    ('executable tables', ('us_decomp/dump_rodata.py',)),
    ('sound effects', ('audio/sfx_render_vm.py', 'remake/assets/audio/sfx')),
    ('sounds the game sequencer leaves silent', 'sfx_gaps'),
    ('sound lengths', ('audio/sfx_dry.py',)),
    ('sound releases', ('audio/sfx_release.py',)),
    ('music', ('audio/music_render_vm.py', 'remake/assets/audio/music_game')),
    ('ending music', ('remake_extract_disc.py', 'xa')),
    ('voice and jingle clips', ('remake_extract_xa.py', DISC / BIN_NAME)),
    ('movie streams', 'movie_streams'),
    ('movies', ('remake_export_movies.py',)),
    ('cleanup', 'cleanup'),
]


def global_info():
    """The shared sprites' info block the game loads at boot (0x800CBF58): DATAS.BIN's first
    header block."""
    d = (DISC / 'DATA' / 'DATAS.BIN').read_bytes()
    a, b = struct.unpack_from('<2I', d, 0)
    (WORK / 'sprites').mkdir(parents=True, exist_ok=True)
    (WORK / 'sprites' / 'global_info.bin').write_bytes(d[a:b])


MAP_LOAD = 0x801536C0                                     # where the game loads a map's block


def _session():
    sys.path.insert(0, str(TOOLS))
    from remake_export import session
    s = session(); s.data_frozen = True
    return s


def map_sprite_info():
    """Each map's sprite-info block (its sprite section, maps/NNN/sprite_info.bin) and the RAM
    addresses of that block and of the map's strings (data.json sprite_info_addr / strings_addr)."""
    s = _session(); d = s.data
    for m in range(483):
        base, h = s.layout(m)
        folder = WORK / 'maps' / f'{m:03d}'; df = folder / 'data.json'
        if not df.exists(): continue
        spr = h[3]
        later = [o for o in h if o not in (0, -1) and o > spr]
        end = base + (min(later) if later else s.layout(m + 1)[0] - base if m < 482 else len(d) - base)
        (folder / 'sprite_info.bin').write_bytes(bytes(d[base + spr:end]))
        doc = json.loads(df.read_text())
        doc['sprite_info_addr'] = MAP_LOAD + spr
        if h[6] not in (0, -1): doc['strings_addr'] = MAP_LOAD + h[6]
        df.write_text(json.dumps(doc))


def spawned_sprites():
    """Map sprites that no entity places (scripts spawn them by number): every entry of the
    map's sprite table gets its folder, as the remake looks them up by catalogue number."""
    s = _session()
    from remake_export import export_sprite
    n = 0
    for m in range(483):
        df = WORK / 'maps' / f'{m:03d}' / 'data.json'
        if not df.exists(): continue
        for k in json.loads(df.read_text()).get('sprite_headers', {}):
            cat = int(k); folder = WORK / 'maps' / f'{m:03d}' / 'sprites' / f'{cat:03d}'
            if cat < 256 or folder.exists(): continue
            try: export_sprite(s, m, cat, folder, None); n += 1
            except Exception: pass
    log(f'  {n} spawned sprites')


def sfx_gaps():
    """Sounds the game's own sequencer (sfx_render_vm) leaves silent are rendered by the
    register-level path (sfx_render.py), one record each."""
    sys.path.insert(0, str(TOOLS / 'audio'))
    import libsnd as L
    idx = json.loads((WORK / 'audio' / 'sfx' / 'index.json').read_text())
    gaps = [n for n in range(1, L.SOUND_COUNT + 1) if str(n) not in idx and L.sound_record(n)['bank'] != -2]
    log(f'  {len(gaps)} sounds')
    for n in gaps: run('audio/sfx_render.py', n, n, name=f'sound {n}')


def movie_streams():
    """MOVIE/*.MOV as RIFF/CDXA .str files for the movie step (remake_extract_disc's do_movies
    without its .mp4 copies, which the remake does not use)."""
    sys.path.insert(0, str(TOOLS))
    import remake_extract_disc as D
    d = WORK / 'movies'; d.mkdir(parents=True, exist_ok=True)
    for name in [n for n in D.iso_files() if n.startswith('MOVIE/')]:
        (d / (Path(name).stem + '.str')).write_bytes(D.riff_cdxa(D.read_file(name, raw=True)))
        log(f'  {name}')


def cleanup():
    """Intermediate files the remake does not read."""
    for pat in ('movies/*.str', 'movies/*.mp4', 'audio/xa/*.xa'):
        for f in WORK.glob(pat): f.unlink()


def check_tools():
    missing = []
    try: import numpy  # noqa: F401
    except ImportError: missing.append('numpy')
    try: import PIL  # noqa: F401
    except ImportError: missing.append('pillow')
    if missing and FROZEN:
        raise SystemExit(f'This build is missing {", ".join(missing)}.')
    if missing:
        log(f'Installing {", ".join(missing)} ...')
        subprocess.run([sys.executable, '-m', 'pip', 'install', *missing], check=True)
    if not shutil.which('ffmpeg'):
        raise SystemExit('ffmpeg was not found.  Install it (for example: winget install Gyan.FFmpeg), '
                         'open a new window and run the extraction again.')


def main(image=None):
    """image: the disc image (asked for when None).  The exe passes the one it already checked."""
    LOG.write_text(''); _trace_hook()
    check_tools()
    image = Path(image) if image else pick_disc()
    if not image: raise SystemExit('No disc image chosen.')
    started = time.time()
    if WORK.exists(): shutil.rmtree(WORK)
    for d in ('text', 'audio/sfx', 'audio/music_game', 'audio/xa', 'movies', 'ui', 'boot', 'title', 'ending', 'maps', 'sprites/global'):
        (WORK / d).mkdir(parents=True, exist_ok=True)
    unpack_disc(image)
    workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    for i, (label, step) in enumerate(STEPS, 1):
        log(f'[{i}/{len(STEPS)}] {label}')
        if PROGRESS: PROGRESS(i, len(STEPS), label)
        if step is None: export_maps(workers)
        elif isinstance(step, str): globals()[step]()
        else: run(*step, name=label)
    log('Moving the result to assets/ ...')                 # (over an existing assets/: files it does not make are kept)
    if FINAL.exists():
        shutil.copytree(WORK, FINAL, dirs_exist_ok=True); shutil.rmtree(WORK)
    else: shutil.move(str(WORK), str(FINAL))
    shutil.rmtree(DISC, ignore_errors=True)                 # the disc's files are not kept here
    log(f'Done in {(time.time() - started) / 60:.0f} minutes: {FINAL}')


if __name__ == '__main__':
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0): log(f'STOPPED: {e.code}')
        if os.environ.get('ALUNDRA_PAUSE'): input('Press Enter to close.')
        raise
    if os.environ.get('ALUNDRA_PAUSE'): input('Press Enter to close.')
