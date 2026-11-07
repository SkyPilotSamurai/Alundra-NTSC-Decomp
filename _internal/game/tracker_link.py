"""The Alundra Rando Tracker's BizHawk script (Alundra_Rando_Tracker_Bizhawk.lua), run by the game itself: the same
reads every frame and the same files in the script's folder (log.txt, location.txt, tracker.txt), so the tracker app
works with this game as with BizHawk.  Randomizer > Seeds > Connect tracker picks the tracker (its exe or this script;
kept in tracker.json); the script's map names and item addresses are read from it.  Seeds > Tracker turns it on or
off; on, a seed that starts also starts the tracker with the seed's file loaded (its --json).  Item counts and the play check are the same RAM words; a boss's life is
its entity slot's (the script's slot +0x14)."""
import json, re, time
from pathlib import Path
from home import HOME, ASSETS

CONFIG = HOME / 'tracker.json'
BUILTIN = ASSETS / 'tracker'                     # the tracker that comes with the game (Seeds > Use built-in tracker)

LOCATIONS = {
    "Overworld (Indoors)": ["Watermill", "Left Cave", "Upper Mines", "D2 (Cavern)", "Olen's House", "Lutas's House", "Blue Chest",
                            "House Near Coal", "Cave Next To Underground", "Cave To Lake", "Cabin", "House Basement", "Mimics Cave",
                            "Circle Of Fishes", "Cave Before Fire", "Well"],
    "Overworld": ["A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C4", "D1", "D2", "D3", "D4"],
    "Tarn's Manor": "Tarn's Manor", "Coal Mine": "Coal Mine:", "Lars Crypt": "Lars Crypt", "Cliffs of Madness": "E4",
    "Desert": ["E3", "E2"], "Ancient Shrine": "Ancient Shrine", "Coastal Cave": "Coastal Cave", "Reptile Lair": "Reptile Lair",
    "Magyscar": "Magyscar", "Fire-Ice Manor": ["Fire Manor", "Ice Manor"], "Underground Waterway": "Underground Waterway",
    "Nirude's Lair-Site": ["Nirude's Lair", "E1"], "Murgg Woods": "A2", "Murgg Tree": "Great Tree", "Fairy Pond": "Fairy Pond",
    "Torla Mountain": "Torla Mountain", "Nava's Keep": "Nava's Keep", "Shops": ["Naomi's Shop", "Merrick's Shop", "Lurvy's Shop"],
    "Lake Shrine": "Lake Shrine", "Casino": "Casino"}
BOSS_SLOT, WATCHER_SLOT, WORM_SLOT = 1, 4, 2          # 0x1AC9A0, 0x1AD15C, 0x1ACC34: slot +0x14 of 0x1AC6F8 + slot * 0x294
HINTS = ('Ruby Hint', 'Sapphire Hint', 'Topaz Hint', 'Agate Hint', 'Garnet Hint', 'Emerald Hint', 'Diamond Hint', 'Fire Wand Hint')

link = None
MAP_NAMES, ADDRESSES = [], {}


SCRIPT, EXE = 'Alundra_Rando_Tracker_Bizhawk.lua', 'Alundra_Rando_Tracker.exe'
started = None                                    # the tracker this game started (Popen)
on, asked = True, 0


def config():
    try: return json.loads(CONFIG.read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def builtin(o=None):
    import seedgen
    return (seedgen.load_options() if o is None else o).get('builtin-tracker', 0) == 0


def chosen(o=None):
    """The tracker script in use: the built-in one, or the linked one (None: none linked, or it is gone)."""
    p = BUILTIN / SCRIPT if builtin(o) else config().get('lua')
    return Path(p) if p and Path(p).is_file() else None


def choose(path):
    """The menu's pick (the tracker's exe or its script): checks the script has what the link reads, keeps both."""
    global link
    path = Path(path); folder = path.parent
    lua = path if path.suffix.lower() == '.lua' else folder / SCRIPT
    if not lua.is_file(): raise ValueError(f'No {SCRIPT} next to it.')
    read_script(lua)
    exe = path if path.suffix.lower() == '.exe' else folder / EXE
    CONFIG.write_text(json.dumps({'lua': str(lua), 'exe': str(exe) if exe.is_file() else None}), encoding='utf-8')
    link = None


def enabled():
    import seedgen
    return chosen() is not None and seedgen.load_options().get('tracker', 0) % 2 == 0


def exe_path(o=None):
    """The tracker's exe in use (None: none linked, or it is gone)."""
    p = BUILTIN / EXE if builtin(o) else config().get('exe')
    return Path(p) if p and Path(p).is_file() else None


def open_tracker(json_path=None):
    """Starts the linked tracker (with a seed's file: --json); one already open is left as it is.  True: started."""
    global started
    exe = exe_path()
    if exe is None or running(exe.name): return False
    for name in ('log.txt', 'tracker.txt', 'location.txt'):          # (the tracker reads them before it writes them)
        if not (exe.parent / name).exists(): (exe.parent / name).write_text('', encoding='utf-8')
    import subprocess
    started = subprocess.Popen([str(exe)] + (['--json', str(json_path)] if json_path else []), cwd=str(exe.parent))
    return True


def start(root):
    """A seed starts (seedgen.activate): with the tracker linked and on, its file goes to the tracker - pc_seed.txt in
    the tracker's folder, which an open tracker loads (unless it has that file loaded); a closed one starts with it."""
    try:
        exe = exe_path()
        sp = Path(root) / 'spoiler.json'
        if exe is None or not enabled() or 'itemSources' not in json.loads(sp.read_text(encoding='utf-8')): return
        (exe.parent / 'pc_seed.txt').write_text(str(sp), encoding='utf-8')
        open_tracker(sp)
    except Exception:
        pass


def running(name):
    import subprocess
    r = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {name}', '/NH'], capture_output=True, text=True, creationflags=0x08000000)
    return name.lower() in r.stdout.lower()


def read_script(path):
    """map_IDs (map n is entry n, as Lua's 1-based array) and memory_addresses (a repeated name: the last address)."""
    global MAP_NAMES, ADDRESSES
    s = path.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'map_IDs\s*=\s*\{(.*?)\}\s*\n', s, re.S); a = re.search(r'memory_addresses\s*=\s*\{(.*?)\n\}', s, re.S)
    if not m or not a: raise ValueError('That is not the tracker script (no map_IDs / memory_addresses).')
    MAP_NAMES = re.findall(r'"([^"]*)"', m.group(1))
    ADDRESSES = {}
    for k, v in re.findall(r'(\w+)\s*=\s*(0x[0-9A-Fa-f]+)', a.group(1)): ADDRESSES[k] = int(v, 16)


def tick(g):
    """Once a frame (Game.update): the script's loop body.  Never stops the game: a failure turns the link off."""
    global link, on, asked
    asked = (asked + 1) % 120
    if asked == 1:
        now = chosen()                               # (linked: the script's files are written; Auto boot only starts it)
        if now != on: on = now; link = None
    if link is False or not on: return
    try:
        if link is None:
            lua = chosen()
            if lua is None: link = False; return
            read_script(lua); link = Link(lua.parent)
        link.frame(g)
    except Exception:
        link = False


def format_item(name):
    name = re.sub(r'_\d', '', name).replace('_', ' ')
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    return name[:1].upper() + name[1:]


def camel(s):
    return re.sub(r"([A-Za-z])([A-Za-z0-9']*)", lambda m: m.group(1).upper() + m.group(2).lower(), s)


def check_location(loc):
    if not loc: return 'Unknown Location'
    loc = loc.replace(':', '').lower()
    for value in LOCATIONS.values():
        for sub in (value if isinstance(value, list) else [value]):
            if sub.replace(':', '').lower() in loc: return sub
    return loc


class Link:
    def __init__(self, folder):
        self.dir = folder; self.prev = None; self.frames = 0; self.counter = 0; self.saved = 0; self.shown = None
        self.formatted = ''; self.loc = 'location'
        self.flags = dict.fromkeys(('LarsGolem', 'Watcher', 'Worm', 'Maximus', 'Nirude', 'Zazan', 'Wilda', 'Zorgia'), False)
        self.hints = dict.fromkeys(HINTS, False)

    def path(self, name): return self.dir / name

    def read(self, name):
        try: return self.path(name).read_text(encoding='utf-8').splitlines()
        except OSError: return None

    def write(self, name, text, mode='w'):
        with open(self.path(name), mode, encoding='utf-8') as f: f.write(text)

    # -- the RAM reads ------------------------------------------------------------
    def byte(self, g, a): return g.mem.u8(0x80000000 | a)

    def playing(self, g): return g.mem.u16(0x801DD810) == 0x1EE

    def boss(self, g, slot):
        e = g.ent[slot] if slot < len(g.ent) else None
        return max(0, getattr(e, 'hp', 0) or 0) & 0xFF if e is not None else 0

    # -- the script's functions ---------------------------------------------------
    def log(self, text):
        loc = 'Bean Cave' if self.formatted == 'Bean Cave & Magyscar Alter' else self.formatted
        self.write('log.txt', f"{time.strftime('[%Y-%m-%d %H:%M:%S]')} [Location: {loc}] Obtained: {text}\n", 'a')

    def unlog(self, item):
        lines = self.read('log.txt')
        if lines is None: return
        low = format_item(item).lower(); found = False; out = []
        protected = any(k in low for k in ('crest', 'gem', 'bouquet', 'small key', 'broken armor'))
        for line in lines:
            if not found and low in line.lower() and not protected: found = True; continue
            out.append(line)
        self.write('log.txt', ''.join(l + '\n' for l in out))

    def remove_obtained(self, item):
        lines = self.read('tracker.txt')
        self.loc = check_location(self.loc)
        if lines is None: return
        name = format_item(item).lower() + ' '
        if re.match(r'^charm\s*$', name): name = "nava's charm "
        if name == 'olgas ring ': name = "olga's ring "
        if self.loc == 'Top-Left Cave': self.loc = 'Left Cave'
        cur = self.loc.lower(); keep = []; hit = None
        for line in lines:
            low = line.lower()
            if hit is None and name in low and (cur in low or (cur == "olen's house" and 'house basement' in low)
                                               or (cur == 'circle of fishes' and 'cave before fire' in low)
                                               or (cur == 'burning pillars' and '(sluice key)' in low)
                                               or (cur == 'd2 (cavern)' and 'd2 (cavern)' in low)):
                hit = line
            elif line != hit: keep.append(line)
        self.write('tracker.txt', '\n'.join(keep) + '\n')

    def check_items(self, g):
        if not self.playing(g): return
        for item, a in ADDRESSES.items():
            v = self.byte(g, a)
            if v > self.prev[item]: self.remove_obtained(item); self.log(format_item(item))
            if v < self.prev[item] and item != 'gilded_falcon': self.unlog(item)          # (falcons: Merrick zeroes the carried count)
            self.prev[item] = v

    def count_lines(self, loc):
        lines = self.read('tracker.txt')
        if lines is None: return 0
        main = loc.lower(); keys = [main] + {'overworld d2': ['d2 (cavern)'], "olen's house": ['house basement'],
                                            'circle of fishes': ['cave before fire'], 'burning pillars': ['(sluice key)']}.get(main, [])
        seen = set(); n = 0
        for line in lines:
            low = line.lower()
            if line not in seen and any(k in low for k in keys): seen.add(line); n += 1
        return n

    def display_location(self):
        loc = self.loc
        loc = {'Inoa Village': 'Inoa', 'Top-Left Cave': 'Left Cave', 'Burning Pillars': '(Sluice Key)'}.get(loc, loc)
        loc = check_location(loc)
        count = self.count_lines(loc)
        loc = camel(loc)
        loc = {'Inoa': 'Inoa Village', 'Blue Chest': "Jess's House", "Olen's House": "Olen's House - Cephas's Basement",
               'Cabin': "Nava's Cabin", 'Left Cave': 'Bean Cave & Magyscar Alter', 'House Near Coal': 'House Near Coal Mine',
               'Well': "Lurvy's Well", 'Cave (Sand Cape)': 'Sand Cape Cave', 'Great Tree': 'Murgg Tree', 'A2': 'Murgg Woods',
               'E1': 'Nirude Site', 'E2': 'Desert (Upper)', 'E3': 'Desert (Lower)', 'E4': 'Cliffs of Madness',
               'Circle Of Fishes': 'Beach Caves', '(Sluice Key)': 'Burning Pillar Cave'}.get(loc, loc)
        if len(loc) == 2: loc = 'Overworld ' + loc
        self.loc = loc; self.formatted = loc
        text = f'{loc} ({count})\n'
        if text != self.shown or self.frames - self.saved >= 30:      # (a change at once, as the Lua's every frame)
            self.write('location.txt', text); self.saved = self.frames; self.shown = text

    def frame(self, g):
        self.frames += 1
        if self.prev is None: self.prev = {item: self.byte(g, a) for item, a in ADDRESSES.items()}
        m = g.cur_map
        self.loc = MAP_NAMES[m - 1] if 1 <= m <= len(MAP_NAMES) else None
        loc = self.loc; f = self.flags; h = self.hints
        boss = self.boss(g, BOSS_SLOT)
        if self.counter == 20: self.check_items(g); self.counter = 0
        def log_has_entries(): return bool(self.read('log.txt'))
        if loc == 'Lars Crypt 5':
            if boss > 0: f['LarsGolem'] = True
            if f['LarsGolem'] and boss == 0: h['Ruby Hint'] = True
        if loc == 'Ancient Shrine 5': h['Fire Wand Hint'] = h['Topaz Hint'] = True
        if loc == 'Coastal Cave 8':
            boss = self.boss(g, WATCHER_SLOT)
            if boss > 0: f['Watcher'] = True
            if f['Watcher'] and boss == 0:
                if not log_has_entries(): h['Fire Wand Hint'] = True
                if log_has_entries(): h['Agate Hint'] = True
        if loc == 'Reptile Lair 6':
            if boss > 0: f['Maximus'] = True
            if f['Maximus'] and boss == 0: h['Sapphire Hint'] = True
        if loc in ('Corpse Worm Boss Room', 'Magyscar 10'):
            boss = self.boss(g, WORM_SLOT)
            if boss > 0: f['Worm'] = True
            if f['Worm'] and boss == 0:
                if not log_has_entries(): h['Fire Wand Hint'] = True
                if log_has_entries(): h['Garnet Hint'] = True
        if loc == 'Nirude Boss Room': f['Nirude'] = True
        if f['Nirude'] and loc == 'Overworld E1 (Nirude sector)': h['Topaz Hint'] = True
        if loc == 'Great Tree 6':
            if boss > 0: f['Zazan'] = True
            if f['Zazan'] and boss == 0: h['Agate Hint'] = h['Garnet Hint'] = True
        if loc == 'Wilda Boss Room':
            if boss > 0: f['Wilda'] = True
            if f['Wilda'] and boss == 0: h['Emerald Hint'] = True
        if loc == 'Zorgia Boss Room':
            if boss > 0: f['Zorgia'] = True
            if f['Zazan'] and boss == 0: h['Diamond Hint'] = True
        if any(h.values()):
            for k in HINTS:
                if h[k]: self.log(k)
            for k in f: f[k] = False
            for k in h: h[k] = False
        self.display_location()
        self.counter += 1


