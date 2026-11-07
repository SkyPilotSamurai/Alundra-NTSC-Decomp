"""BizHawk savestates (.State, any version / PS1 core) as speedrun starts.

A .State is a zip; its Core.bin is the core's savestate, Zstandard- (BizHawk 2.x), gzip- or not
compressed.  The PS1 main RAM (2 MB) lies somewhere inside it, by core and version; it is found by
code bytes of ALUN_CD.EXE that are always at one RAM address (assets/speedrun/bizhawk_sigs.json,
made from the user's discs by tools/bizhawk_state_sigs.py), which also tells US from JP.  From
it: the game block, the map, Alundra's position and the play time, made into a continue record
exactly as tools/speedrun_states.py does (the JP block has the US layout), then EXACT and his exact
position (the record's tile alone would start him at the tile's centre).
"""
import gzip, io, json, struct, zipfile
from home import ASSETS

BLOCK_N, REC_N = 0x758, 0x76C
EXACT = b'XPOS'                     # after the record: Alundra's exact x, y, z (16.16) and the HUD state
RAM = 0x200000
_SIGS = None


def _sigs():
    global _SIGS
    if _SIGS is None:
        try: _SIGS = json.loads((ASSETS / 'speedrun' / 'bizhawk_sigs.json').read_text())
        except (OSError, ValueError): _SIGS = {}
    return _SIGS


def _core(path):
    data = path.read_bytes()
    if data[:2] == b'PK':                                   # the BizHawk zip
        z = zipfile.ZipFile(io.BytesIO(data))
        name = next((n for n in z.namelist() if n.lower().startswith('core')), None)
        data = z.read(name) if name else b''
    if data[:4] == b'\x28\xb5\x2f\xfd':                     # Zstandard (BizHawk 2.x)
        import zstandard
        data = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)).read()
    elif data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    return data


def ram_of(path):
    """(version, 2 MB RAM) of a BizHawk state, or (None, None)."""
    core = _core(path)
    for v, s in _sigs().items():
        i = core.find(bytes.fromhex(s['sig']))
        while i >= 0:
            base = i - s['sig_at']
            if base >= 0 and base + RAM <= len(core): return v, core[base:base + RAM]
            i = core.find(bytes.fromhex(s['sig']), i + 1)
    return None, None


def record(path):
    """(version, continue record) of a BizHawk state (raises ValueError if it is not Alundra)."""
    v, ram = ram_of(path)
    if ram is None: raise ValueError('Not an Alundra BizHawk state')
    s = _sigs()[v]
    m = struct.unpack_from('<I', ram, s['map'])[0]
    px, py, pz = struct.unpack_from('<iii', ram, s['ent_x'])
    rec = bytearray(REC_N); rec[:BLOCK_N] = ram[s['block']:s['block'] + BLOCK_N]
    def w32(o, val): rec[o:o + 4] = (val & 0xFFFFFFFF).to_bytes(4, 'little')
    w32(0, 1); w32(0x48, struct.unpack_from('<I', ram, s['time'])[0])
    w32(0x4C, m); w32(0x50, (px >> 16) // 0x18); w32(0x54, (py >> 16) // 0x10); w32(0x58, pz >> 20)
    # the record keeps only the tile: Alundra's exact place follows it (Game.__init__ puts him there)
    hud = struct.unpack_from('<i', ram, 0x12E3E0)[0]      # the HUD's state 0x8012E3E0 (0 hidden, 1 shown, ...)
    return v, bytes(rec) + EXACT + struct.pack('<iii', px, py, pz) + struct.pack('<i', hud)
