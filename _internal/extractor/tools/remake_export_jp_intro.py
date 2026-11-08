"""The Japanese disc's opening movie for the remake (Options > Intro Movie: JP).
Lists MOVIE/*.MOV on Alundra (Japan).bin, takes the opening (the one that is not ARAN_OP /
ARAN_END / MATRIX - or the name given), dumps it as remake/assets/movies/JP_OP.str and exports
it with remake_export_movies.py (frames, ogg, movies.json 'JP_OP').
Run: python extractor/tools/remake_export_jp_intro.py [path to Japan .bin] [MOV name]"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent                 # remake/extractor/tools
REMAKE = HERE.parents[1]
sys.path.insert(0, str(HERE))
import remake_extract_disc as X, remake_export_movies as M
M.DIR = REMAKE / 'assets' / 'movies'

disc = Path(sys.argv[1]) if len(sys.argv) > 1 else REMAKE.parent / 'Alundra (Japan).bin'
X.DISC = disc
movs = [n for n in X.iso_files(disc) if n.upper().startswith('MOVIE/')]
print('JP disc movies:', movs)
want = sys.argv[2].upper() if len(sys.argv) > 2 else None
pick = [n for n in movs if (want and Path(n).stem.upper() == want) or
        (not want and Path(n).stem.upper() not in ('ARAN_OP', 'ARAN_END', 'MATRIX'))]
if not pick: sys.exit('no opening movie found; give its name as the 2nd argument')
name = pick[0]; print('opening:', name)
M.DIR.mkdir(parents=True, exist_ok=True)
(M.DIR / 'JP_OP.str').write_bytes(X.riff_cdxa(X.read_file(name, raw=True)))
M.main(['JP_OP'])
