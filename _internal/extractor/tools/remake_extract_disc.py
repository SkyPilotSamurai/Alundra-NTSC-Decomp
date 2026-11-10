"""Everything outside DATAS.BIN, straight from the disc image, for the remake.

  ui/FONT3.png, ui/WIND_pal*.png   the menu font and window/HUD texture (TIM / raw 4bpp + CLUT)
  text/etc_usa.json                the 1024-entry menu/item text table (ETC_USA.R)
  text/maps.json                   (made by remake_extract_data.py, per map in data.json)
  movies/*.mp4                     the FMV movies (PlayStation STR in MOVIE/*.MOV) via ffmpeg
  audio/xa/*.ogg                   XA streams (one file per interleaved channel) (ARAN_XA.XA voices/jingles, ENDING.XA) via ffmpeg
  audio/music/NN.wav               every music track rendered from SOUND.BIN (sequence + VAB)
  audio/sfx/NNN.wav                every global sound effect from SOUND.BIN
Run: python tools/remake_extract_disc.py [ui|text|movies|xa|music|sfx|all]
"""
import json, struct, subprocess, sys, wave
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
DISC = ROOT / 'private-inputs/disc/Alundra (USA) (Rev 1).bin'
OUT = ROOT / 'remake' / 'assets'


def iso_files(path=DISC):
    f = open(path, 'rb')
    def sec(n): f.seek(n * 2352 + 24); return f.read(2048)
    root = sec(16)[156:190]; out = {}
    def walk(ext, size, prefix):
        data = b''.join(sec(ext + i) for i in range((size + 2047) // 2048)); i = 0
        while i < len(data):
            l = data[i]
            if l == 0: i = (i // 2048 + 1) * 2048; continue
            e, s = struct.unpack_from('<I', data, i + 2)[0], struct.unpack_from('<I', data, i + 10)[0]
            fl, nl = data[i + 25], data[i + 32]; name = data[i + 33:i + 33 + nl]
            if name not in (b'\0', b'\1'):
                n = name.decode('latin1').split(';')[0]
                if fl & 2: walk(e, s, prefix + n + '/')
                else: out[prefix + n] = (e, s)
            i += l
    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
    return out


def read_file(name, raw=False):
    """raw=True keeps whole 2336-byte Mode 2 sectors (needed for STR/XA streams)."""
    lba, size = iso_files()[name]
    n = (size + 2047) // 2048
    with open(DISC, 'rb') as f:
        if raw:
            out = bytearray()
            for i in range(n if not name.endswith(('.MOV', '.XA')) else size // 2048):
                f.seek((lba + i) * 2352 + 16); out += f.read(2336)
            return bytes(out)
        out = bytearray()
        for i in range(n): f.seek((lba + i) * 2352 + 24); out += f.read(2048)
        return bytes(out[:size])


def psx_color(v, stp_black=False):
    r, g, b = (v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3
    return (r, g, b, 0 if v == 0 else 255)


def image_4bpp(pixels, w, h, clut):
    from PIL import Image
    img = Image.new('RGBA', (w, h)); px = img.load()
    for y in range(h):
        for x in range(w):
            b = pixels[(y * w + x) // 2]
            px[x, y] = clut[(b >> 4) if x & 1 else (b & 15)]
    return img


def tim(data):
    """PlayStation TIM -> list of (name, PIL image)."""
    from PIL import Image
    flags = struct.unpack_from('<I', data, 4)[0]; bpp = flags & 3; o = 8; cluts = []
    if flags & 8:
        n = struct.unpack_from('<I', data, o)[0]; cw, ch = struct.unpack_from('<HH', data, o + 8)
        vals = struct.unpack_from(f'<{cw * ch}H', data, o + 12)
        cluts = [[psx_color(v) for v in vals[i * cw:(i + 1) * cw]] for i in range(ch)]; o += n
    n = struct.unpack_from('<I', data, o)[0]; w, h = struct.unpack_from('<HH', data, o + 8); pix = data[o + 12:o + n]
    if bpp == 0:
        return [(f'pal{i}', image_4bpp(pix, w * 4, h, c)) for i, c in enumerate(cluts[:16] or [[(i * 17,) * 3 + (255,) for i in range(16)]])]
    if bpp == 1:
        img = Image.new('RGBA', (w * 2, h)); px = img.load(); c = cluts[0]
        for y in range(h):
            for x in range(w * 2): px[x, y] = c[pix[y * w * 2 + x]]
        return [('pal0', img)]
    img = Image.new('RGBA', (w, h)); px = img.load()
    for y in range(h):
        for x in range(w): px[x, y] = psx_color(struct.unpack_from('<H', pix, (y * w + x) * 2)[0])
    return [('rgb', img)]


def do_ui():
    d = OUT / 'ui'; d.mkdir(parents=True, exist_ok=True)
    for name, img in tim(read_file('TAKI/SCREEN/FONT3.TIM')): img.save(d / f'FONT3_{name}.png')
    tx = read_file('TAKI/SCREEN/WIND.TX'); cl = read_file('TAKI/SCREEN/WIND.CL')
    vals = struct.unpack_from('<256H', cl)
    for p in range(16):
        clut = [psx_color(v) for v in vals[p * 16:p * 16 + 16]]
        image_4bpp(tx, 256, len(tx) * 2 // 256, clut).save(d / f'WIND_pal{p:02d}.png')
    print('ui done')


def do_text():
    """ETC_USA.R (EtcResUsa.cs): 1024 offsets, then strings. 0x000 menu/etc strings (GetEtcString),
    0x100 string table, 0x200 item names, 0x280 item descriptions, 0x300 description second lines."""
    data = read_file('DATA/ETC_USA.R'); idx = struct.unpack_from('<1024h', data)
    def at(o):
        if o is None or o < 0 or o >= len(data): return None
        return data[o:data.find(b'\0', o)].decode('latin-1').rstrip()
    out = {'etc': {i: at(idx[i]) for i in range(256) if at(idx[i])},
           'table': {i: at(idx[0x100 + i]) for i in range(256) if at(idx[0x100 + i])},
           'items': {i: {'name': at(idx[0x200 + i]), 'description': at(idx[0x280 + i]), 'description2': at(idx[0x300 + i])}
                     for i in range(0x62) if at(idx[0x200 + i])}}
    d = OUT / 'text'; d.mkdir(parents=True, exist_ok=True)
    (d / 'etc_usa.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print('text', len(out['etc']), len(out['table']), len(out['items']))


def ffmpeg(src, dst, args):
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'psxstr', '-i', str(src)] + args + [str(dst)], capture_output=True, text=True)
    return r.returncode == 0, r.stderr[-300:]


def do_movies():
    d = OUT / 'movies'; d.mkdir(parents=True, exist_ok=True)
    for name in [n for n in iso_files() if n.startswith('MOVIE/')]:
        raw = d / (Path(name).stem + '.str')
        if not raw.exists(): raw.write_bytes(riff_cdxa(read_file(name, raw=True)))
        ok, err = ffmpeg(raw, d / (Path(name).stem + '.mp4'), ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac'])
        print(name, 'ok' if ok else err)


def riff_cdxa(raw):
    """Wrap 2336-byte sectors (with the 16-byte header added back) as RIFF/CDXA so ffmpeg's psxstr reader accepts them."""
    sectors = bytearray()
    sync = b'\x00' + b'\xff' * 10 + b'\x00'
    for i in range(len(raw) // 2336):
        sectors += sync + b'\0\0\0\x02' + raw[i * 2336:(i + 1) * 2336]
    hdr = b'RIFF' + struct.pack('<I', len(sectors) + 36) + b'CDXAfmt ' + struct.pack('<I', 16) + bytes(16) + b'data' + struct.pack('<I', len(sectors))
    return hdr + sectors


def do_xa():
    d = OUT / 'audio' / 'xa'; d.mkdir(parents=True, exist_ok=True)
    for name in ('ARAN_XA.XA', 'ENDING.XA'):
        raw = d / (Path(name).stem + '.xa')
        if not raw.exists(): raw.write_bytes(riff_cdxa(read_file(name, raw=True)))
        # every XA file holds several interleaved channels; export each one that has audio
        for ch in range(32):
            out = d / f'{Path(name).stem}_ch{ch:02d}.ogg'
            r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'psxstr', '-i', str(raw), '-map', f'0:a:{ch}',
                                '-c:a', 'libvorbis', '-q:a', '5', str(out)], capture_output=True, text=True)
            if r.returncode != 0: break
        print(name, 'channels', ch)


def sound_files():
    sound = (ROOT / 'private-inputs/disc/DATA/SOUND.BIN').read_bytes(); exe = (ROOT / 'private-inputs/disc/ALUN_CD.EXE').read_bytes()
    return sound, exe


def do_music(first=0, last=999, seconds=180.0):
    import music_preview
    from music_database import music_rows
    sound, exe = sound_files(); d = OUT / 'audio' / 'music'; d.mkdir(parents=True, exist_ok=True)
    rows = music_rows(exe, sound)
    for r in rows[first:last + 1]:
        out = d / f"{r['id']:02d}.wav"
        if out.exists(): continue
        try:
            rate, stereo = music_preview.render(sound[r['sequence_offset']:r['header_offset']], sound[r['header_offset']:r['body_offset']],
                                                sound[r['body_offset']:r['end_offset']], seconds)
            out.write_bytes(music_preview.to_wav(rate, stereo, 1.0)); print('music', r['id'], flush=True)
        except Exception as exc:
            print('music', r['id'], 'failed', exc, flush=True)
    try:
        from game_audio_names import music_default_name
        (d / 'names.json').write_text(json.dumps({r['id']: music_default_name(r['id']) for r in rows}, indent=0))
    except Exception: pass


def do_sfx():
    from sound_database import SoundLibrary
    sound, exe = sound_files(); lib = SoundLibrary(sound, exe); d = OUT / 'audio' / 'sfx'; d.mkdir(parents=True, exist_ok=True)
    n = 0; names = {}
    for r in lib.rows():
        try:
            (d / f"{r['id']:03d}.wav").write_bytes(lib.wav(r['id'], 1.0)); n += 1
        except Exception: pass
    try:
        from game_audio_names import sound_default_name
        names = {r['id']: sound_default_name(r['id']) for r in lib.rows()}
        (d / 'names.json').write_text(json.dumps(names, indent=0))
    except Exception: pass
    print('sfx', n)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    for step, fn in [('ui', do_ui), ('text', do_text), ('sfx', do_sfx), ('movies', do_movies), ('xa', do_xa), ('music', do_music)]:
        if what in (step, 'all'):
            fn(*[int(x) for x in sys.argv[2:4]]) if step == 'music' and len(sys.argv) > 3 else fn()
