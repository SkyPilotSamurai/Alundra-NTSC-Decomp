"""Makes a seed from the exported game alone: alundra-randomizer.exe chooses the placements (it reads no game
file), and everything else is edits to copies of the files in assets/.  tables/ holds the edits and the numbers
the randomizer's patches need.  A seed folder keeps the files it changed; merge() links the rest."""
import gzip, json, re, shutil, struct, subprocess, tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
NO_WINDOW = 0x08000000


def tables():
    return json.loads(gzip.decompress((HERE / 'tables' / 'tables.json.gz').read_bytes()))


def edits():
    return json.loads(gzip.decompress((HERE / 'tables' / 'edits.json.gz').read_bytes()))


def run_logic(args, work):
    """Placements, hints and settings: the randomizer's --only-logic reads no game file.  --preset-edit=<json> (the
    menu's preset rows) is not the randomizer's: it is applied to a copy of the preset (edit_preset)."""
    work = Path(work); shutil.copytree(HERE / 'presets', work / 'presets', dirs_exist_ok=True)
    own = next((a.split('=', 1)[1] for a in args if a.startswith('--user-presets=')), None)   # (the player's saved presets)
    args = [a for a in args if not a.startswith(('--user-presets=', '--vessel-heal=', '--drops=', '--shop=', '--boss-resist=', '--weapon-balance=', '--twin-puzzles=', '--balance=', '--stat-chance='))]   # (the remake's: build)
    if own:
        for f in Path(own).glob('*.json'): shutil.copyfile(f, work / 'presets' / f.name)
    edit = next((json.loads(a.split('=', 1)[1]) for a in args if a.startswith('--preset-edit=')), None)
    args = [a for a in args if not a.startswith('--preset-edit=')]
    if edit and edit.get('startWeapon') in START_WEAPONS:      # (Preset > Weapon Start: a random one chosen once, here)
        import random
        edit['startWeapon'] = random.SystemRandom().choice(START_WEAPONS[edit['startWeapon']])
    if edit is not None:
        name = next((a.split('=', 1)[1] for a in args if a.startswith('--preset=')), 'default')
        p = edit_preset(read_preset(work / 'presets' / f'{name}.json'), edit)
        (work / 'presets' / '_seed.json').write_text(json.dumps(p, indent=1), encoding='utf-8')
        args = [a for a in args if not a.startswith('--preset=')] + ['--preset=_seed']
    for _ in range(20):        # (money drops off: a world the found money cannot pay for is made again, another seed)
        r = subprocess.run([str(HERE / 'alundra-randomizer.exe'), '--pause=false', '--only-logic', *args, '--outputlog=spoiler.json'], cwd=str(work),
                           creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        unsolved = 'Not enough money' in r.stdout or '--doors=Y' in args    # (Random Door & Warps: a layout the items cannot open, another)
        if r.returncode == 0 or not unsolved or any(a.startswith('--permalink=') for a in args): break
    if r.returncode != 0:
        why = [l[7:].strip() for l in r.stdout.splitlines() if l.startswith('ERROR:')]
        raise RuntimeError(why[-1] if why else r.stdout[-400:])
    global LAST_PRESET
    name = next((a.split('=', 1)[1] for a in args if a.startswith('--preset=')), None)
    LAST_PRESET = read_preset(work / 'presets' / f'{name}.json') if name and (work / 'presets' / f'{name}.json').exists() else None
    return json.loads((work / 'spoiler.json').read_text(encoding='utf-8'))


LAST_PRESET = None             # the preset the last run_logic used, as the randomizer read it (seedgen's share codes)


def read_preset(path):
    """A preset file: JSON with // comment lines (and the commas they leave before a closing bracket)."""
    t = re.sub(r'^\s*//.*$', '', Path(path).read_text(encoding='utf-8'), flags=re.M)
    return json.loads(re.sub(r',(\s*[}\]])', r'\1', t))


START_WEAPONS = {'sfb': ('Dagger', 'Iron Flail', "Hunter's Bow"),
                 'random': ('Dagger', 'Iron Flail', "Hunter's Bow", 'Ice Wand', 'Fire Wand')}
START_WEAPONS.update({k + '-ns': tuple(w for w in v if w != 'Dagger') for k, v in list(START_WEAPONS.items())})   # (No sword start)   # (a type, its first tier;
                                                                                                # never the Spirit Wand)
def start_weapon(p, name):
    """Preset > Weapon Start: the weapon owned at the start instead of the Dagger (a bow or a wand too: the shoulder
    dash hits ground switches); one fewer in the pool, and a fixed source of it given up when the pool no longer has it."""
    rs = p.setdefault('randomizerSettings', {}); inv = rs.setdefault('startingInventory', ['Dagger', 'Cloth Armor', 'Short Boots'])
    if name == 'Dagger' or name in inv: return
    inv[:] = [x for x in inv if x != 'Dagger'] + [name]
    dist = rs.setdefault('itemsDistribution', {})
    if dist.get(name, 0) > 0: dist[name] -= 1
    fixed = rs.get('fixedItemSources', {})
    for src in [k for k, v in fixed.items() if v == name][dist.get(name, 0):]: del fixed[src]


FILLER = ('Herbs', '1 Gilder', '5 Gilder', '10 Gilder', '30 Gilder', 'Strength Tonic', 'Wonder Essence', 'Magic Elixyr',
          'Strength Elixyr', 'Gilded Falcon')     # (never Life Vessels, Magic Seeds or gear)


def edit_preset(p, edit):
    """The menu's edits: game settings, and item pool counts.  The pool keeps the preset's size (the randomizer
    needs one item per chest): what the counts add is taken from the filler the menu did not set, in FILLER's order,
    until enough is free; what they take is added to the first of those."""
    gs = p.setdefault('gameSettings', {}); rs = p.setdefault('randomizerSettings', {})
    for k in ('progressiveItems', 'startingHealth', 'startingMana', 'startingGold', 'moneyDrops'):
        if k in edit: gs[k] = edit[k]
    if edit.get('itemGilderValues'): rs['itemGilderValues'] = {**rs.get('itemGilderValues', {}), **edit['itemGilderValues']}
    dist = rs.setdefault('itemsDistribution', {}); before = sum(dist.values())
    for item, n in edit.get('pool', {}).items(): dist[item] = n
    if edit.get('startWeapon') and edit['startWeapon'] not in START_WEAPONS: start_weapon(p, edit['startWeapon'])
    over = sum(dist.values()) - before
    free = [f for f in FILLER if f not in edit.get('pool', {})]
    for f in free:
        if over <= 0: break
        take = min(over, dist.get(f, 0)); dist[f] = dist.get(f, 0) - take; over -= take
    if over < 0 and free: dist[free[0]] = dist.get(free[0], 0) - over
    elif over > 0: raise RuntimeError(f'The item pool has {over} more items than there are chests.')
    return p


def permalink_seed(link):
    """The permalink's seed: after the prefix and option markers, base64 of a version number (a zero count, a one,
    that many bits) and then the 32-bit seed, low byte first."""
    import base64
    body = re.sub(r'^.(?:~\d|!|\^|-|\*\d|%\d|&\d|#\d|@\d)*', '', link)[:-1]
    bits = ''.join(f'{x:08b}' for x in base64.b64decode(body + '=' * (-len(body) % 4))[:12])
    n = bits.index('1')
    return int.from_bytes(int(bits[2 * n + 1:2 * n + 33], 2).to_bytes(4, 'big'), 'little')


class Files:
    """The seed's copies of exported files, read when first changed and written at the end."""
    def __init__(self, stock):
        self.stock = Path(stock); self.docs = {}; self.raw = {}; self.texture_growth = {}; self.block_size = {}

    def doc(self, rel):
        d = self.docs.get(rel)
        if d is None: d = self.docs[rel] = json.loads((self.stock / rel).read_text(encoding='utf-8'))
        return d

    def bin(self, rel):
        d = self.raw.get(rel)
        if d is None: d = self.raw[rel] = bytearray((self.stock / rel).read_bytes())
        return d

    def map(self, m): return self.doc(f'maps/{m:03d}/map.json')
    def data(self, m): return self.doc(f'maps/{m:03d}/data.json')
    def info(self, m): return self.bin(f'maps/{m:03d}/sprite_info.bin')

    def write(self, out):
        from concurrent.futures import ThreadPoolExecutor
        out = Path(out)
        def text(f, t): f.parent.mkdir(parents=True, exist_ok=True); f.write_text(t, encoding='utf-8')
        def data(f, b): f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b)
        with ThreadPoolExecutor(8) as pool:      # (file system waits: on threads; a file in both is written as raw, as before)
            done = [pool.submit(text, out / rel, json.dumps(d, separators=(',', ':'))) for rel, d in self.docs.items() if rel not in self.raw]
            done += [pool.submit(data, out / rel, d) for rel, d in self.raw.items()]
            for x in done: x.result()


def set_path(d, path, *value):
    for k in path[:-1]: d = d[k]
    if value: d[path[-1]] = value[0]
    else: del d[path[-1]]


def apply_bytes(b, runs):
    for run in runs:
        raw = bytes.fromhex(run[1]); at = run[0]
        if len(run) > 2:
            del b[run[2]:]
            if len(b) < at: b.extend(bytes(at - len(b)))
        b[at:at + len(raw)] = raw


def apply_layer(files, layer):
    for m, e in layer.get('maps', {}).items():
        for key, name in (('map', 'map.json'), ('data', 'data.json'), ('warps', 'warps.json')):
            for x in e.get(key, ()): set_path(files.doc(f'maps/{m}/{name}'), x[0], *x[1:])
        if 'info' in e: apply_bytes(files.bin(f'maps/{m}/sprite_info.bin'), e['info'])
        if e.get('map'): split_injected(files, m)
    for rel, runs in layer.get('files', {}).items():
        if rel.endswith('.json'):
            for x in runs: set_path(files.doc(rel), x[0], *x[1:])
        else: apply_bytes(files.bin(rel), runs)


def entity_from_record(e, row):
    e.update(rect=list(row[:4]), enabled=row[4], flags=row[5], catalogue=row[6] + (256 if row[5] & 128 else 0), x=row[7], y=row[8], z=row[9],
             programs=dict(zip('ABCDEF', row[10:16])), collection_flag=struct.unpack_from('<H', row, 16)[0], contents=struct.unpack_from('<H', row, 18)[0])


def poke_row(files, p, value, size):
    """The operand's bytes, wherever the map's listings show them (the edits can re-cut a listing's rows)."""
    at = p['offset'] + p['byte']; new = value.to_bytes(size, 'little')
    for rows in files.map(p['map'])['scripts'].values():
        for r in rows:
            n = len(r['bytes']) // 2
            if r['offset'] <= at and at + size <= r['offset'] + n:
                b = bytearray.fromhex(r['bytes']); b[at - r['offset']:at - r['offset'] + size] = new; r['bytes'] = b.hex()
    files.info(p['map'])[p['rel']:p['rel'] + size] = new


def poke_entity(files, p, set_bytes):
    info = files.info(p['map'])
    for at, v in set_bytes: info[p['rel'] + at] = v
    first = struct.unpack_from('<I', info, 0)[0]
    rec = (p['rel'] - first) // 20
    entity_from_record(files.map(p['map'])['entities'][rec], info[first + rec * 20:first + rec * 20 + 20])


ARCHERY = 'Lake Shrine Interior (1F): Chest inside archery trial with 9 orbs'


def source_items(spoiler, items=None):
    """{source name: item name}; the spoiler adds the vanilla item to a name, the tables have both.  Early Lake
    Shrine's archery chest is in a node of its own that the spoiler does not list: it holds the one item of the
    pool left over.  The spoiler's distribution is the one before the world's changes to it: progressive seeds place
    an upgrade for each tier, no-armor seeds Herbs for each armor, and each nightmare chest adds its own item (in its
    name).  Crests are placed apart from the distribution."""
    placed = {name: item for region in spoiler['itemSources'].values() for name, item in region.items()}
    if not spoiler['gameSettings'].get('lakeShrineEarly') or any(n.startswith(ARCHERY) for n in placed): return placed
    items = items or json.loads((HERE / 'item.json').read_text(encoding='utf-8'))
    slots = {x['name']: x.get('slot') for x in items}
    upgrade = {x.get('slot'): x['name'] for x in items if x['name'].endswith(' upgrade')} if spoiler['gameSettings'].get('progressiveItems') else {}
    if spoiler['gameSettings'].get('splitBootsEffects'): upgrade = {k: v for k, v in upgrade.items() if v != 'Boots upgrade'}
    no_armor = spoiler['gameSettings'].get('removeArmor')
    left = Counter()
    for name, n in spoiler['randomizerSettings']['itemsDistributions'].items():
        name = upgrade.get(slots.get(name), name)
        if no_armor and name in ('Leather Armor', 'Ancient Armor', 'Silver Armor', 'Armor upgrade'): name = 'Herbs'
        left[name] += n
    for name in placed:
        if name.startswith('Dream '): left[name[name.rindex('(') + 1:-1]] += 1
    left.subtract(Counter(placed.values()))
    rest = [i for i, n in left.items() for _ in range(n) if n > 0 and not i.endswith(' Crest')]
    if len(rest) != 1: raise RuntimeError(f'Lake Shrine archery chest: {sorted(rest)} left over')
    placed[ARCHERY] = rest[0]
    return placed


UPGRADE_LOOK = {'Sword upgrade': 'Sword', 'Flail upgrade': 'Iron Flail', 'Bow upgrade': "Hunter's Bow", 'Armor upgrade': 'Silver Armor',
                'Earth Magic upgrade': 'Earth Scroll', 'Water Magic upgrade': 'Water Scroll', 'Fire Magic upgrade': 'Fire Scroll',
                'Wind Magic upgrade': 'Wind Scroll'}   # (an upgrade shows its first tier's picture, user 2026-11-03)


def look(items, i):
    """The item whose picture item i shows."""
    t = UPGRADE_LOOK.get(items[i]['name'])
    return next(k for k, x in enumerate(items) if x['name'] == t) if t else i


def upgrade_pictures(files, items):
    """The upgrades' item records (+8: the picture, global sprite record n; exe_data 0x9BE58 + id * 10) take their
    first tier's."""
    exe = files.bin('exe_data.bin')
    for i, x in enumerate(items):
        if x['name'] in UPGRADE_LOOK:
            at = 0x9BE58 + i * 10; struct.pack_into('<h', exe, at, struct.unpack_from('<h', exe, 0x9BE58 + look(items, i) * 10)[0])


def apply_placements(files, spoiler, T, items):
    ids = {x['name']: i for i, x in enumerate(items)}
    places = T['places']
    for name, item in source_items(spoiler, items).items():
        i = ids[item]
        chest = re.match(r'Dream \w+ - map (\d+) chest (\d+)', name)
        if chest:                                   # (a nightmare's chest: the record's item byte)
            m, n = int(chest[1]), int(chest[2]); info = files.info(m); first = struct.unpack_from('<I', info, 0)[0]
            flag = files.map(m)['entities'][n]['collection_flag']
            for k, rec in enumerate(files.map(m)['entities']):
                if k == n or (rec['collection_flag'] == flag and [m, k] in T['dream_chests']):
                    info[first + k * 20 + 18] = i; rec['contents'] = i
            continue
        e = places.get(name) or places[re.sub(r' \([^()]*\)$', '', name)]
        for p in e.get('address', ()):
            if p['kind'] == 'entity': poke_entity(files, p, [(0, i)])
            else: poke_row(files, p, i, 1)
        for p in e.get('spriteAddress', ()):
            poke_entity(files, p, ([(k, 0) for k in range(4, 14)] if i == 0 else []) + [(0, (look(items, i) + 0x1E) & 255)])
        for p in e.get('priceAddress', ()):
            poke_row(files, p, items[i].get('goldValue', 0), 2)
        if 'merrick' in e:
            struct.pack_into('<I', files.bin('exe_data.bin'), e['merrick'], 0x800C7DE4 + 8 * i)


# ---------------------------------------------------------------- text --
WIDTHS = {'w': 24, 'm': 24, 'n': 18, 'H': 18, 'h': 16, 'a': 16, 'A': 16, 'p': 16, 'i': 10, 'I': 10, 't': 10, 'l': 10, ' ': 10, '!': 8, '.': 6, ',': 6, '\\': 0}


def text_words(s):
    words, cur, i = [], '', 0
    while i < len(s):
        c = s[i]
        if cur and c in ' \\\n\r': words.append(cur); cur = ''
        if c == '\\':
            cur = '\\' + s[i + 1]; i += 1
            if cur == '\\W': cur += s[i + 1]; i += 1
            if cur == '\\0':
                end = s.index('\\Y', i + 1); cur += s[i + 1:end + 2]; i = end + 1
            words.append(cur); cur = ''
        elif c in '\n\r':
            if c == '\r' and s[i + 1:i + 2] == '\n': i += 1
            words.append('\\N')
        elif c != ' ': cur += c
        i += 1
    if cur: words.append(cur)
    return words


def format_text(s):
    """TextboxFormatter: 500 pixels wide, three lines."""
    out, width, lines, spaced = [], 0, 0, False
    def newline():
        nonlocal width, lines
        if lines < 2: out.append('\\N'); lines += 1
        else: out.append('\\A'); lines = 0
        width = 0
    size = lambda w: sum(WIDTHS.get(c, 14) for c in w)
    for word in text_words(s):
        if word.startswith('\\'):
            if word[1] == 'N': newline()
            elif word[1] == 'A': out.append('\\A'); lines = 0; width = 0
            else: out.append(word)
            spaced = False; continue
        n = size(word); m = n + (10 if spaced else 0)
        if width + m <= 500:
            if spaced: out.append(' ')
            out.append(word); width += m
        elif n <= 500:
            newline(); out.append(word); width += n
        else:
            if width: newline()
            for c in word:
                if width + WIDTHS.get(c, 14) > 500: newline()
                out.append(c); width += WIDTHS.get(c, 14)
        spaced = True
    return ''.join(out)


def apply_text(files, spoiler, T, items):
    placed = source_items(spoiler, items); gold = {x['name']: x.get('goldValue', 0) for x in items}
    hints = {T['hint_ids'][k]: v for k, v in spoiler.get('hints', {}).items() if k in T['hint_ids']}
    def part(p):
        if isinstance(p, str): return p
        if p[0] == 'hint': return hints.get(p[1], '')
        return placed[p[1]] if p[0] == 'name' else str(gold[placed[p[1]]])
    for op in T['text_ops']:
        if any(isinstance(p, list) and p[0] != 'hint' and p[1] not in placed for p in op['parts']): continue
        strings = files.data(op['map'])['strings']; k = str(op['str'])
        text = ''.join(part(p) for p in op['parts'])
        if op['format']: text = format_text(text)
        strings[k] = strings[k].replace(op['find'], text, 1) if 'find' in op else text


# Nightmare mode: each nightmare's completion program and the hint Septimus gives once it is over (the randomizer's
# "Septimus (after ...)" hint sources).  The program's change of map (op 53) becomes a jump to a few added commands:
# Septimus' text box with the hint, wait for it to close, then that same change of map.  With the nightmare's own
# scenes kept the box comes after them; with them removed it is the only one.
DREAM_ENDS = {"Wendell's Dream": [(44, 'B 5')], "Bonaire's Dream": [(47, 'B 1')], "Giles' Dream": [(449, 'B 1'), (107, 'B 2')],
              "Kline's Dream": [(123, 'B 1')], "Twins' Dream": [(109, 'B 1')],
              "Elene's Dream": [(435, 'B 2'), (436, 'B 2'), (437, 'B 2'), (438, 'B 2')], "Meia's Dream": [(442, 'B 6')],
              "Olen's Dream": [(362, 'B 2')]}


def split_rows(rows):
    """A listing row holding several commands (an edit's bytes after an injected one) as one row per command, by the
    game's command lengths (C5 / C6: the injected 5- and 3-byte ones); an unknown length keeps the rest as it was."""
    sizes = {int(k): v for k, v in json.loads((HERE.parent / 'extractor' / 'data' / 'event-instruction-lengths.json')
                                              .read_text(encoding='utf-8'))['sizes'].items() if v}
    sizes.update({0xC5: 5, 0xC6: 3}); split_rows.sizes = sizes
    out = []
    for r in rows:
        b = bytes.fromhex(r['bytes']); at = 0
        while at < len(b):
            n = sizes.get(b[at])
            if at == 0 and (n is None or n >= len(b)): out.append(r); at = len(b); break
            if n is None or at + n > len(b): n = len(b) - at
            out.append({'offset': r['offset'] + at, 'op': b[at], 'bytes': b[at:at + n].hex()}); at += n
    return out


def split_injected(files, m):
    """An edit's row of an injected C5 / C6 holds the program's next commands after it (the boss rooms' map remaps made
    no-ops: Lars Crypt 5's B 2 "c5a200c100055c016781a511ff"), cut at 32 bytes with the rows after it dropped (Bonaire's
    room 30 B 3).  The port runs the listing, where those commands start no row, so the program ended at the C5 (Lars
    Crypt: flag 0x15C, the camera back on Alundra and his control never came).  From the C5 to the end of the stock
    program, one row per command, read from sprite_info.bin (what the game runs) by the game's command lengths."""
    doc = files.doc(f'maps/{m}/map.json'); blob = files.bin(f'maps/{m}/sprite_info.bin'); stock = None
    for key, rows in doc.get('scripts', {}).items():
        if not isinstance(rows, list): continue
        for r in [r for r in rows if r['op'] in (0xC5, 0xC6) and len(r['bytes']) // 2 > (5 if r['op'] == 0xC5 else 3)]:
            o = r['offset']; before = b''; at = o
            for q in sorted((q for q in rows if q['offset'] < o), key=lambda q: -q['offset']):
                if q['offset'] + len(q['bytes']) // 2 != at or len(before) >= 64: break
                before = bytes.fromhex(q['bytes']) + before; at = q['offset']
            head = before + bytes.fromhex(r['bytes'])[:5 if r['op'] == 0xC5 else 3]
            rel = blob.find(head); assert rel >= 0 and blob.find(head, rel + 1) < 0, ('injected row', m, key, o)
            rel += len(before)
            if stock is None: stock = json.loads((files.stock / f'maps/{m}/map.json').read_text(encoding='utf-8'))['scripts']
            end = max([q['offset'] + len(q['bytes']) // 2 for q in stock.get(key, ())] + [o + len(r['bytes']) // 2])
            if not hasattr(split_rows, 'sizes'): split_rows([])     # (the game's command lengths)
            sizes = split_rows.sizes
            out = []; at = o
            while at < end:
                op = blob[rel + at - o]; n = sizes.get(op)
                assert n, ('injected row: command length', m, key, at, op)
                out.append({'offset': at, 'op': op, 'bytes': bytes(blob[rel + at - o:rel + at - o + n]).hex()}); at += n
            assert ''.join(x['bytes'] for x in out).startswith(r['bytes'][:2 * min(len(r['bytes']) // 2, at - o)]), ('injected row bytes', m, key, o)
            rows[:] = [q for q in rows if not o <= q['offset'] < end] + out
            rows.sort(key=lambda q: q['offset'])


def apply_dream_hints(files, spoiler):
    hints = spoiler.get('hints', {})
    for dream, programs in DREAM_ENDS.items():
        hint = hints.get(f'Septimus (after {dream})')
        if not hint: continue                                  # (a nightmare left out of the seed)
        for m, key in programs:
            doc = files.map(m); rows = doc['scripts'][key] = split_rows(doc['scripts'][key])
            warp = next(r for r in rows if r['op'] == 0x53)
            strings = files.data(m)['strings']
            free = next(k for k in sorted(strings, key=int) if not strings[k])
            strings[free] = format_text(f'\\CAlundra, it is I, Septimus. Listen well: {hint}.')
            files.__dict__.setdefault('new_lines', {})[(m, int(free))] = ('septimus', hint)
            new = max(r['offset'] + len(bytes.fromhex(r['bytes'])) for rr in doc['scripts'].values() for r in rr) + 16
            text_id = 0x180 + int(free)
            added = [(0x00, '00'), (0x0D, '0d' + text_id.to_bytes(2, 'little').hex()), (0x39, '39'), (0x53, warp['bytes']),
                     (0x00, '00'), (0x00, '00'), (0xFF, 'ff')]
            at = new
            for op, b in added:
                rows.append({'offset': at, 'op': op, 'bytes': b}); at += len(bytes.fromhex(b))
            jump = new - warp['offset']
            warp.update(op=0x02, bytes='02' + (jump & 0xFFFF).to_bytes(2, 'little').hex())
            for k in ('group', 'action', 'settings'): warp.pop(k, None)


# Nightmare mode: the door Wendell's and the twins' nightmares share (Inoa 241, square 5,33; its program's first rows
# are listed, the twins' question follows in sprite_info.bin) is asked again with a gate on each (user 2026-11-03):
# Wendell's needs Tarn's Manor cleared (flag 0x6C: set by Melzas' scene in its final room, map 117, after the
# basement), the twins' any crest.  The program's first command becomes a jump to the new one; a gate not met shows
# what is needed, as the other nightmares' doors do.
CRESTS = (0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44)
SHARED_DOOR = '3b0505212100ff'


def apply_dream_gates(files):
    doc = files.map(241); key = next((k for k, rows in doc['scripts'].items() if len(rows) > 1 and rows[1]['bytes'] == SHARED_DOOR), None)
    if key is None: return
    rows = doc['scripts'][key] = split_rows(doc['scripts'][key]); info = files.info(241)
    old = b''.join(bytes.fromhex(r['bytes']) for r in rows); at = info.find(old)
    assert at >= 0, 'shared nightmare door'
    choices = []
    p = at + sum(len(bytes.fromhex(r['bytes'])) for r in rows[:rows.index(next(r for r in rows if r['bytes'] == '06de83'))])
    while info[p:p + 4] == bytes.fromhex('06de830d'):
        choices.append((bytes(info[p + 3:p + 6]), bytes(info[p + 21:p + 29]))); p += 30
    strings = files.data(241)['strings']
    def text(t):
        k = next(k for k in sorted(strings, key=int) if not strings[k]); strings[k] = format_text(t)
        files.__dict__.setdefault('new_lines', {})[(241, int(k))] = ('gate', 'Wendell' if t.startswith('Wendell') else 'twins')
        return int(k)
    gates = {0x8501: ('flag', 0x6C, "Wendell is lost in a nightmare, but you are not ready to enter it. You need to clear the basement of Tarn's Manor."),
             0x8601: ('items', CRESTS, "The twins are lost in a nightmare, but you are not ready to enter it. You need a crest.")}
    code, fix = [], []                                         # commands (bytes); (command index, target label, where its offset is)
    labels = {}
    def add(b, target=None, at=1):
        if target is not None: fix.append((len(code), target, at))
        code.append(bytearray(b))
    labels['wait'] = 0; add(b'\x00'); add(bytes.fromhex(SHARED_DOOR)); add(b'\x04\x00\x00', 'off')
    add(b'\x6e'); add(b'\x04\x00\x00', 'wait'); add(bytes.fromhex('2f001000')); add(b'\x04\x00\x00', 'wait')
    add(b'\x10'); add(b'\x1a\x00')
    for n, (q, warp) in enumerate(choices):
        gate = gates.get(int.from_bytes(q[1:], 'big'))
        if gate and gate[0] == 'flag': add(b'\x31' + gate[1].to_bytes(2, 'little') + b'\x00\x00', f'refused{n}', 3)
        if gate and gate[0] == 'items':
            for item in gate[1]: add(bytes((0x83, item, 1))); add(b'\x03\x00\x00', f'ask{n}')
            add(b'\x02\x00\x00', f'refused{n}')
        labels[f'ask{n}'] = len(code)
        for b in ('06de83', q.hex(), '5004', '36de83', '06de83', '44', '51', '39'): add(bytes.fromhex(b))
        add(b'\x04\x00\x00', f'no{n}'); add(b'\x11'); add(warp); add(b'\xff')
        labels[f'refused{n}'] = len(code)
        if gate: add(bytes((0x0D, 0x80 | text(gate[2]), 0x00))); add(b'\x39')
        labels[f'no{n}'] = len(code)
    add(b'\x11'); labels['release'] = len(code); add(b'\x00'); add(bytes.fromhex('2f001000'))
    add(b'\x03\x00\x00', 'release'); add(b'\x02\x00\x00', 'wait'); labels['off'] = len(code); add(b'\xff')
    new = max(r['offset'] + len(bytes.fromhex(r['bytes'])) for rr in doc['scripts'].values() for r in rr) + 16
    offs = [new]
    for c in code: offs.append(offs[-1] + len(c))
    for i, target, at in fix: code[i][at:at + 2] =((offs[labels[target]] - offs[i]) & 0xFFFF).to_bytes(2, 'little')
    start = rows[0]['offset']
    rows[:] = [{'offset': start, 'op': 0x02, 'bytes': '02' + ((new - start) & 0xFFFF).to_bytes(2, 'little').hex()}]
    rows += [{'offset': o, 'op': c[0], 'bytes': c.hex()} for o, c in zip(offs, code)]


# Dreams > Twins' puzzles: Random.  Each puzzle's answer in one twin's room is shown by the other room's demo at the
# mirrored place (x -> 102 - x); both change together.  (map, slot, entities in answer order, first program id)
TWIN_ORDERS = ((110, 'CD', (20, 21, 22, 23), 149), (111, 'C', (11, 12, 13, 14), 140))
TWIN_DEMOS = ((111, 'C 1', (10, 12, 14, 16, 19, 21, 23, 25), (0, 1, 2, 3)), (110, 'C 25', (8, 10, 12, 14), (24, 25, 26, 27)))
TWIN_STEPS, TWIN_STEP_DEMO, TWIN_STEP_PAIR = (111, 'C 6', range(1, 10), (20, 26)), (110, 'C 5', range(9, 61, 6)), (33, 19)


def set_rows(files, m, key, change):
    """change(rows) edits some rows' bytes (same lengths); the program's bytes are changed in sprite_info.bin too,
    at every copy of it (the game's listing falls back to that file)."""
    rows = files.map(m)['scripts'][key]
    old = b''.join(bytes.fromhex(r['bytes']) for r in rows)
    change(rows)
    new = b''.join(bytes.fromhex(r['bytes']) for r in rows)
    info = files.info(m); at = info.find(old)
    assert at >= 0 and len(new) == len(old), (m, key)
    while at >= 0: info[at:at + len(new)] = new; at = info.find(old, at + 1)


def set_programs(files, m, i, programs):
    info = files.info(m); first = struct.unpack_from('<I', info, 0)[0]
    for slot, v in programs.items(): info[first + i * 20 + 10 + 'ABCDEF'.index(slot)] = v
    entity_from_record(files.map(m)['entities'][i], info[first + i * 20:first + i * 20 + 20])


def apply_twin_puzzles(files, seed):
    """New answers: the order of the hit pillars (map 110) and of the floor switches (map 111), and the 9 presses
    of map 111's two switches; their demos in the other room show the same.  Returns the answers for the spoiler."""
    import random
    rnd = random.Random(seed ^ 0x7417); out = {}
    for (m, slots, ents, first), (dm, key, lines, shown) in zip(TWIN_ORDERS, TWIN_DEMOS):
        order = list(range(4)); rnd.shuffle(order)               # answer step j: entity ents[order[j]]
        for j, k in enumerate(order): set_programs(files, m, ents[k], {s: first + j for s in slots})
        def demo(rows):
            for n, line in enumerate(lines):
                b = bytearray.fromhex(rows[line]['bytes']); b[1] = shown[order[n % 4]]; rows[line]['bytes'] = b.hex()
        set_rows(files, dm, key, demo)
        out[f'Map {m}'] = [ents[k] for k in order]
    m, key, lines, targets = TWIN_STEPS; dm, dkey, dlines = TWIN_STEP_DEMO
    presses = [rnd.randrange(2) for _ in lines]
    def steps(rows):
        for n, line in zip(presses, lines):
            r = rows[line]; rel = rows[targets[n]]['offset'] - (r['offset'] + 1)
            r['bytes'] = '78' + (rel & 0xFFFF).to_bytes(2, 'little').hex()
    def step_demo(rows):
        for n, line in zip(presses, dlines):
            for at in (line, line + 3):
                b = bytearray.fromhex(rows[at]['bytes']); b[1] = TWIN_STEP_PAIR[n]; rows[at]['bytes'] = b.hex()
    set_rows(files, m, key, steps); set_rows(files, dm, dkey, step_demo)
    out['Map 111 presses'] = [(25, 26)[n] for n in presses]
    return out


# Story changes for every seed (user 2026-11-03).
# * Coal Mine: leaving it no longer plays the cave-in (map 6 B 9: its first command now jumps to its end), so flag
#   0x21D is never set and map 6 B 10 (as the base layer has it: 0x21D clear -> line 11) never spawns the rocks on
#   the two mine entrances.  Only these two programs use 0x21D.  The villagers' talk outside the mine afterwards (map 6
#   B 2: in seeds it waits for 0x30D, set at the mine's end) is skipped too: once it may run, it only sets 0x678, which
#   removes the boulder on Overworld B3 (map 7 C 4) as the talk did.
# * Nirude's Lair: after Nirude, the scene (map 451 C 9) remapped Overworld E1 439 (the one with the lair's doors) to
#   17 and warped to 17; it now keeps 17 -> 439 and warps to 439, so the lair can be entered again.
# * Nava's Keep needs Bomb and Merman Boots (the logic's ap_nava_s_keep): Nava's cabin (map 144) program B 1, which
#   places Nava beside the passage to the keep, ends in a loop instead.  Without both, the warps are off while
#   Alundra is next to the passage (op 9B; on again, 9C, when he steps away).
#   Nava says the line when Alundra talks to him (user 2026-11-07): while one is lacking B 1 places him beside the
#   passage (template 1, the stock spot), and his talk (C 1) has only the line.
# * Torla Mountain: once Wilda is beaten (flag 0xDE: only her end scene, map 325 B 2, sets it; clear at a seed's start)
#   her room (map 325) sends Alundra out to the mountain's entrance on Overworld D1 (map 13, 42,14: where leaving the
#   mountain, map 443 warp 10, puts him).  Its load program's first command (B 1) jumps to the added check.
NAVA_LINE = '\\CYou need Bomb and Merman Boots if you hope to enter my keep.'


def row_jump(rows, i, target):
    """Row i (5 bytes) becomes a jump to the row at offset target, then two yields (same length)."""
    r = rows[i]; o = r['offset']; assert len(bytes.fromhex(r['bytes'])) == 5
    rows[i:i + 1] = [{'offset': o, 'op': 0x02, 'bytes': '02' + ((target - o) & 0xFFFF).to_bytes(2, 'little').hex()},
                     {'offset': o + 3, 'op': 0x00, 'bytes': '00'}, {'offset': o + 4, 'op': 0x00, 'bytes': '00'}]


def apply_story_edits(files):
    def coal(rows):
        assert rows[0]['bytes'].startswith('301d02') and rows[-1]['bytes'] == 'ff', rows[0]['bytes']
        row_jump(rows, 0, rows[-1]['offset'])
    set_rows(files, 6, 'B 9', coal)
    def talk(rows):
        assert rows[4]['bytes'].startswith('3b') and rows[29]['bytes'] == '057806', 'Coal Mine talk'
        r = rows[4]; o = r['offset']
        rows[4:5] = [{'offset': o, 'op': 0x02, 'bytes': '02' + ((rows[29]['offset'] - o) & 0xFFFF).to_bytes(2, 'little').hex()}] + \
                    [{'offset': o + k, 'op': 0x00, 'bytes': '00'} for k in range(3, 7)]
    set_rows(files, 6, 'B 2', talk)
    def nirude(rows):
        new = {'3811001100': '381100b701', '38b7011100': '38b701b701', '531100192825054a': '53b701192825054a'}
        for r in rows[72:76]:
            if r['bytes'] in new: r['bytes'] = new[r['bytes']]; r['op'] = int(r['bytes'][:2], 16)
        assert [r['bytes'] for r in rows[73:76]] == list(new.values()), 'Nirude scene'
    set_rows(files, 451, 'C 9', nirude)
    doc = files.map(325); rows = doc['scripts']['B 1']; first = rows[0]
    assert first['bytes'] == '30a2062b00' and rows[1]['offset'] == first['offset'] + 5, 'Wilda room B 1'
    new = max(r['offset'] + len(bytes.fromhex(r['bytes'])) for rr in doc['scripts'].values() for r in rr) + 16
    block = [bytes.fromhex('31de000e00'),                       # Wilda not beaten: on to the room's own first command
             bytes.fromhex('530d002a0e000000'), b'\xff',      # beaten: out to the mountain's entrance
             bytes.fromhex('30a206') + bytes(2), bytes(3), b'\xff']
    offs = [new]
    for b in block: offs.append(offs[-1] + len(b))
    block[3] = block[3][:3] + ((offs[5] - offs[3]) & 0xFFFF).to_bytes(2, 'little')                 # 0x6A2 set: its end
    block[4] = b'\x02' + ((rows[1]['offset'] - offs[4]) & 0xFFFF).to_bytes(2, 'little')          # else line 1
    o = first['offset']
    rows[0:1] = [{'offset': o, 'op': 0x02, 'bytes': '02' + ((new - o) & 0xFFFF).to_bytes(2, 'little').hex()},
                 {'offset': o + 3, 'op': 0x00, 'bytes': '00'}, {'offset': o + 4, 'op': 0x00, 'bytes': '00'}]
    rows += [{'offset': a, 'op': b[0], 'bytes': b.hex()} for a, b in zip(offs, block)]
    nava_cabin(files)


def nava_cabin(files):
    doc = files.map(144); rows = doc['scripts']['B 1']; end = rows[-1]
    assert end['bytes'] == 'ff', 'Nava cabin B 1'
    strings = files.data(144)['strings']; k = next(k for k in sorted(strings, key=int) if not strings[k])
    strings[k] = format_text(NAVA_LINE); files.__dict__.setdefault('new_lines', {})[(144, int(k))] = ('nava',)
    near = bytes((0x3B, 9, 10, 6, 9, 0, 255))
    code, fix, labels = [], [], {}
    def add(b, target=None):
        if target is not None: fix.append((len(code), target))
        code.append(bytearray(b))
    add(bytes((0x83, 0x23, 1))); add(b'\x04\x00\x00', 'spawn')         # Nava beside the passage (stock template 1, where
    add(bytes((0x83, 0x1B, 1))); add(b'\x04\x00\x00', 'spawn')         # B 1's stages put him) while one is lacking
    add(b'\x02\x00\x00', 'loop')
    labels['spawn'] = len(code); add(bytes.fromhex('8a01b40088001000'))
    labels['loop'] = len(code); add(b'\x00')
    add(bytes((0x83, 0x23, 1))); add(b'\x04\x00\x00', 'lacking')       # Bomb
    add(bytes((0x83, 0x1B, 1))); add(b'\x04\x00\x00', 'lacking')       # Merman Boots
    add(b'\x02\x00\x00', 'loop')
    labels['lacking'] = len(code); add(near); add(b'\x04\x00\x00', 'loop')
    add(b'\x9b')
    labels['near'] = len(code); add(b'\x00'); add(near); add(b'\x04\x00\x00', 'leave')
    add(b'\x02\x00\x00', 'near')                                   # (off while he is there; Nava's line: talk to him)
    labels['leave'] = len(code); add(b'\x9c'); add(b'\x02\x00\x00', 'loop')
    new = max(r['offset'] + len(bytes.fromhex(r['bytes'])) for rr in doc['scripts'].values() for r in rr) + 16
    offs = [new]
    for c in code: offs.append(offs[-1] + len(c))
    for i, target in fix: code[i][1:3] = ((offs[labels[target]] - offs[i]) & 0xFFFF).to_bytes(2, 'little')
    end.update(op=0x02, bytes='02' + ((new - end['offset']) & 0xFFFF).to_bytes(2, 'little').hex())
    for key in ('group', 'action', 'settings'): end.pop(key, None)
    rows += [{'offset': o, 'op': c[0], 'bytes': c.hex()} for o, c in zip(offs, code)]
    talk = doc['scripts']['C 1']; b = [r['bytes'] for r in talk]               # Nava says only the line: his first message
    assert b[12:16] == ['30af050900', '0d8001', '39', '0d8101'], 'Nava C 1'      # is it, the 0x5AF skip and the second go
    talk[12].update(op=0xC5, bytes='c500000000'); talk[13].update(bytes='0d' + (0x180 + int(k)).to_bytes(2, 'little').hex())
    talk[15].update(op=0x02, bytes='020400')                                  # (a jump over itself and its wait)


# Map changes for every seed (user 2026-11-03; places from the user's editor screenshots).
# * Magyscar 1 (map 86): a torch (a copy of the map's own torches, catalogue 393) on the upper-left floor above the
#   vines, square (5,23) height 10; and a ladder on the cliff face of (15,29) (height 8 down to 5, left of the stone
#   statue): that square's wall column becomes the ladder tiles the map's other ladders use (33318 top, 33328, 33358
#   foot - as (24,23)), and the square at its foot (15,30) gets the ladders' ground bits 0x0C (as (24,24), (50,23)).
#   The ladder tiles are see-through, so the column gets new tiles: each ladder tile over the cliff tile it replaces
#   (ladder_on_cliff).
# * Overworld A3 (map 3): the two fence pieces (16,26) and (17,26), right of the ruin with the chest, become the plain
#   grass floor around them (height 3, not blocked, tile 37170).
# * Despair Desert Cave (map 402): a Rock (catalogue 293, the liftable rock; Maker's "Rock 0058") at the end of the
#   upper-right ledge, square (13,11) height 1.  The map has no sprite of its own, so 293 comes from map 404 (another
#   desert cave) as the randomizer brings enemies in: its 252-byte sprite record (slot 37) and its one palette into the
#   map's block, its header into data.json, its folder linked; the object's 20-byte record goes at the end of the
#   block's entity list (index 2) and into map.json.
ROCK_DONOR, ROCK = 404, 293
#   And a stone floor in the sand below the ledge: those squares (height 1) get the map's own stone walkway tile 12687
#   with the walkway's bits (walk 0, ground 16 - as (8,12), (8,13)) instead of sand (walk 24, ground 6).
STONE_FLOOR = ((12, 13), (13, 13), (11, 14), (12, 14), (13, 14), (11, 15), (12, 15), (13, 15), (12, 16), (13, 16))
def ladder_on_cliff(files, m, cliff, ladder):
    """New tiles in the map's tiles.png / tiles.json: each ladder tile drawn over the cliff tile it replaces (the
    ladder tiles are see-through, user 2026-11-07: the cliff behind the ladder was black).  Codes from 0xF000 up,
    unused and outside the animated pages; their codes for the wall column."""
    import io
    from PIL import Image
    tiles = files.doc(f'maps/{m:03d}/tiles.json'); raw = files.bin(f'maps/{m:03d}/tiles.png')
    im = Image.open(io.BytesIO(bytes(raw))).convert('RGBA')
    pages = {a['page'] for a in files.data(m).get('tile_animations', [])}
    def box(i): return (i % 32 * 24, i // 32 * 16, i % 32 * 24 + 24, i // 32 * 16 + 16)
    nxt = max(tiles.values()) + 1; code = 0xF000; out = []
    for c, l in zip(cliff, ladder):
        while str(code) in tiles or (code & 1023) // 160 in pages: code += 1
        if box(nxt)[3] > im.height:
            grown = Image.new('RGBA', (im.width, box(nxt)[3]), (0, 0, 0, 0)); grown.paste(im, (0, 0)); im = grown
        t = im.crop(box(tiles[str(c)])); t.alpha_composite(im.crop(box(tiles[str(l)])))
        im.paste(t, box(nxt)[:2]); tiles[str(code)] = nxt; out.append(code); nxt += 1; code += 1
    b = io.BytesIO(); im.save(b, 'PNG'); files.raw[f'maps/{m:03d}/tiles.png'] = bytearray(b.getvalue())
    return out


def apply_map_edits(files):
    doc = files.map(86); W = doc['width']; cells = doc['cells']
    top, foot = cells[29 * W + 15], cells[30 * W + 15]
    assert top[3] == 8 and len(top[5]) == 3 and foot[3] == 5, 'Magyscar 1 cliff'
    top[5] = ladder_on_cliff(files, 86, top[5], [33318, 33328, 33358]); foot[1] |= 0x0C
    torch = dict(next(e for e in doc['entities'] if e['catalogue'] == 393), programs=dict.fromkeys('ABCDEF', 0))
    torch.update(index=len(doc['entities']), x=10, y=46, z=20)
    doc['entities'].append(torch)
    doc = files.map(3); W = doc['width']; cells = doc['cells']
    for x in (16, 17):
        c = cells[26 * W + x]
        assert c[3] == 5 and c[4] == 0xFFFF and c[0] & 1, 'Overworld A3 fence'
        cells[26 * W + x] = [0, 0, 4, 3, 37088 if x == 16 else 37170, [], 0]   # (16: grass with the wall's shadow, as (16,25), user 2026-11-07)
    import enemies
    m, slot = 402, ROCK - 256
    W = files.map(m)['width']; cells = files.map(m)['cells']
    for x, y in STONE_FLOOR:
        c = cells[y * W + x]; assert c[3] == 1 and c[4] in (776, 777, 786, 787, 796, 797), ('Despair Desert Cave sand', x, y)
        c[0], c[1], c[4] = 0, 16, 12687
    ds = (files.stock / f'maps/{ROCK_DONOR:03d}/sprite_info.bin').read_bytes(); dh = enemies.header(ds)
    rel = struct.unpack_from('<i', ds, dh[3] + slot * 4)[0]
    ends = sorted(p for p in {struct.unpack_from('<i', ds, dh[3] + i * 4)[0] for i in range(257)} if p > rel)
    payload = bytearray(ds[rel:ends[0] if ends else len(ds)])
    s = bytes(files.info(m)); th = enemies.header(s)
    assert (th[6] - th[5]) // 32 == 0 and struct.unpack_from('<i', s, th[3] + slot * 4)[0] < 48, 'Despair Desert Cave block'
    ee = th[0]
    while not (s[ee + 2] == 0 and s[ee + 3] == 0): ee += 20
    doc = files.map(m); index = len(doc['entities']); assert (ee - th[0]) // 20 == index
    record = bytes((0, 0, 0x33, 0x3B, 1, 0xC0, slot, 26, 22, 2)) + bytes(10)
    s = s[:ee] + record + s[ee:]; th = [v + 20 if v > ee else v for v in th]
    out = bytearray(s)
    while len(out) % 4: out.append(0)
    start = len(out)
    for k in range(4): struct.pack_into('<I', payload, k * 4, struct.unpack_from('<I', payload, k * 4)[0] - rel + start)
    out += payload
    while len(out) % 4: out.append(0)
    files.raw[f'maps/{m:03d}/sprite_info.bin'] = enemies.rebuild_block(s, th, out, [ds[dh[5]:dh[5] + 32]], [(slot, start)])
    enemies.room_for_block(files, m); grown_maps(files, files.stock)          # (the load pause reads the grown block)
    files.data(m).setdefault('sprite_headers', {})[str(ROCK)] = enemies._donor_data(files.stock, ROCK_DONOR)['sprite_headers'][str(ROCK)]
    rock = {'index': index, 'rect': [0, 0, 0x33, 0x3B]}
    entity_from_record(rock, record)
    doc['entities'].append(rock)
    files.map_folders = {m: {ROCK: ROCK_DONOR}}


# ---------------------------------------------------------------- Lars Crypt's door --
# The crypt shuts behind him the first time only (user 2026-11-05): 0x2C6 (the grave opened: the bouquet scene's own
# flag, never set in seeds) is set when Lars Crypt 1's door shuts (map 21 B 12).  Once it is set the door stays open
# when he comes in from outside, and Overworld C2's rocks (map 10 and its copy 331, B 5: the scene closing them behind
# him, then entities 8 and 23) stay away, so its door square (warp 12) takes him in.  The added commands are after
# every program in the listing (what the port runs, as apply_dream_hints), reached by a jump in a command's place.
# 0x15C (Lars Crypt 5's boss scene done) counts as 0x2C6: a crypt beaten without coming in by the grave stays open
# too (user 2026-11-06: the rocks closed behind him on the way out).
def _rel(o, to): return ((to - o) & 0xFFFF).to_bytes(2, 'little').hex()


def _branch(doc, rows, i, cmds):
    """rows[i] becomes a jump to cmds [(bytes, jump target or None)] added after every program (the rest of the
    command's bytes: 00, never reached)."""
    at = max(r['offset'] + len(r['bytes']) // 2 for rr in doc['scripts'].values() for r in rr) + 16
    r = rows[i]; o = r['offset']; n = len(r['bytes']) // 2
    rows[i:i + 1] = [{'offset': o, 'op': 0x02, 'bytes': '02' + _rel(o, at)}] + [{'offset': o + k, 'op': 0, 'bytes': '00'} for k in range(3, n)]
    for b, to in cmds:
        h = b + (_rel(at, to) if to is not None else '')
        rows.append({'offset': at, 'op': int(h[:2], 16), 'bytes': h}); at += len(h) // 2


def apply_crypt_door(files):
    for m in (10, 331):
        doc = files.map(m); rows = doc['scripts']['B 5']
        assert [r['bytes'] for r in rows[:3] + rows[-3:]] == ['31d0004500', '3b2b2c0f0f0303', '043900', '2d08', '2d17', 'ff'], ('Overworld C2 rocks', m)
        box, spawn, end = rows[1]['offset'], rows[-3]['offset'], rows[-1]['offset']
        _branch(doc, rows, 0, [('30c602', end), ('305c01', end), ('31d000', spawn), ('02', box)])
    doc = files.map(21); rows = doc['scripts']['B 12']; at = {r['bytes']: r['offset'] for r in rows}
    assert rows[1]['bytes'] == '3b05060f100a0a' and rows[2]['bytes'] == '043d00' and '021100' in at and '31d0000c00' in at, 'Lars Crypt 1 door'
    after, opened, end = rows[2]['offset'], at['31d0000c00'], rows[-1]['offset']
    _branch(doc, rows, 1, [('30c602', opened), ('305c01', opened), ('3b05060f100a0a', None), ('02', after)])
    _branch(doc, rows, next(i for i, r in enumerate(rows) if r['bytes'] == '021100'), [('05c602', None), ('02', end)])
    rows.sort(key=lambda r: r['offset'])


# ---------------------------------------------------------------- Random Door & Warps --
# The randomizer's spoiler "doors" (shuffle_doors): {"doors": {door: area behind it}, "bossWarps": {boss: landing}}.
# A door is its way in from the overworld (portal records of warps.json, and a scene's op 53 for Lars Crypt's
# bouquet) and the area's way out (portal records).  Door A to area B: A's ways in take B's arrival (map, x, y, z,
# arrival facing: what B's own first way in had), and B's way out takes A's (where A's area let him out), so he
# leaves by the door he came in.  A portal keeps its own rectangle, facing and flags (the transition and sound).
# Boss warps (op 53 after the fight) land where the landing door's area lets him out, or at Jess's house as before;
# Wilda's beaten-room warp (apply_story_edits) lands with hers.  The boulder on Overworld B3 (map 7 C 4: removed when
# 0x678 is set, after the Coal Mine) is gone from the start: its flag check becomes no-ops (user 2026-11-03).
# Lars Crypt's way in on Overworld C2 is the bouquet scene (map 10, and its copy 331: entity 8's C 7, after talking
# to the grave): in seeds its 0x2C6 (op C6, a no-op) is never set, so the scene and its op 53 can be used again.
DOORS = {   # area: (ways in: (map, warp index) or (map, script, old op-53 destination)), (ways out: (map, warp index))
    'lars_crypt': (((10, 12), (10, 'C 7', (21, 5, 16, 10)), (331, 3), (331, 'C 7', (21, 5, 16, 10))), ((21, 0),)),
    'tarn_s_manor': (((15, 0),), ((115, 0),)),
    'coastal_cave': (((407, 5),), ((69, 29),)),
    'torla_mountain': (((13, 8),), ((443, 10),)),
    'ice_manor': (((13, 4),), ((304, 0),)),
    'nava_s_keep': (((8, 11),), ((144, 8),)),
    'coal_mine': (((6, 11),), ((61, 5),)),
    'mimics_cave': (((3, 9),), ((380, 0),)),
}
BOSS_WARPS = {   # boss: (map, script, old op-53 destination)
    'magyscar': ((95, 'B 2', (242, 39, 9, 2)),),
    'wilda': ((325, 'B 2', (242, 39, 9, 2)), (325, 'B 1', (13, 42, 14, 0))),
    'nirude': ((324, 'B 1', (17, 25, 40, 0)), (451, 'C 9', (439, 25, 40, 37))),
}
JESS_HOUSE = (242, 39, 9, 2, 0)


def warp_record(files, m, i):
    return next(w for w in files.doc(f'maps/{m:03d}/warps.json') if w['index'] == i)


def retarget_op53(files, m, key, old, new):
    """The program's op 53 to old (map, x, y, z) now goes to new; its effect and sound stay."""
    a = ('53' + old[0].to_bytes(2, 'little').hex() + bytes(old[1:4]).hex())
    b = ('53' + new[0].to_bytes(2, 'little').hex() + bytes(new[1:4]).hex())
    hits = []
    def change(rows):
        for r in rows:
            h = r['bytes']; at = h.find(a)
            while at >= 0:
                if at % 2 == 0: h = h[:at] + b + h[at + len(b):]; hits.append(at)
                at = h.find(a, at + 2)
            r['bytes'] = h
    rows = files.map(m)['scripts'][key]
    if files.info(m).find(b''.join(bytes.fromhex(r['bytes']) for r in rows)) >= 0: set_rows(files, m, key, change)
    else: change(rows)                     # (a program with code added after it, as Wilda's room: the listing only)
    assert hits, ('no op 53', m, key, old)


def apply_doors(files, plan):
    def arrival(w): return (w['map'], w['x'], w['y'], w['z'], w['arrive_facing'])
    inside = {a: arrival(warp_record(files, *ins[0])) for a, (ins, outs) in DOORS.items()}     # (before any change)
    outside = {a: arrival(warp_record(files, *outs[0])) for a, (ins, outs) in DOORS.items()}
    for door, area in plan['doors'].items():
        ins, _ = DOORS[door]; _, outs = DOORS[area]
        to = inside[area]
        for way in ins:
            if len(way) == 2:
                w = warp_record(files, *way); w.update(map=to[0], x=to[1], y=to[2], z=to[3], arrive_facing=to[4])
            else: retarget_op53(files, way[0], way[1], way[2], to[:4])
        back = outside[door]
        for way in outs:
            w = warp_record(files, *way); w.update(map=back[0], x=back[1], y=back[2], z=back[3], arrive_facing=back[4])
    def boulder(rows):
        assert rows[0]['bytes'] == '3178060700' and rows[1]['bytes'] == '2e80', 'Overworld B3 boulder'
        o = rows[0]['offset']; rows[0:1] = [{'offset': o + k, 'op': 0x00, 'bytes': '00'} for k in range(5)]
    set_rows(files, 7, 'C 4', boulder)
    for boss, landing in plan['bossWarps'].items():
        to = JESS_HOUSE if landing == 'inoa' else outside[landing]
        for m, key, old in BOSS_WARPS[boss]: retarget_op53(files, m, key, old, to[:4])


# ---------------------------------------------------------------- build --
def layers_for(gs):
    names = ['base']
    if gs.get('lakeShrineEarly'): names.append('lake')
    if gs.get('armorStrength') in ('half', 'quarter'): names.append('armor_' + gs['armorStrength'])
    if gs.get('removeArmor'): names.append('no_armor')
    if gs.get('dreamDungeonMode'):
        names.append(('dream_cut' if gs.get('removeDreamCutscenes') else 'dream') + ('_olen' if gs.get('olenDream') else ''))
    return names


def chest_names(stock, names):
    """{collection flag: "Player's Item"}: an other player's item in a chest, from the exported records."""
    T = tables(); out = {}
    for loc, text in names.items():
        for p in T['places'].get(loc, {}).get('address', ()):
            if p['kind'] == 'entity':
                doc = json.loads((Path(stock) / f"maps/{p['map']:03d}/map.json").read_text(encoding='utf-8'))
                out[str(doc['entities'][p['index']]['collection_flag'])] = text
    return out


def apply_random(files, spoiler, T, stock, out, colours, chance=100):
    """Random enemies and stats: what gs asks for; {map: {sprite: donor}} for the folders to bring in."""
    import enemies
    gs = spoiler['gameSettings']; seed = permalink_seed(spoiler['permalink']); folders = {}
    mode = gs.get('enemyRandomization', 'off')
    files.block_size = {rel: len(b) for rel, b in files.raw.items()}
    if mode and mode != 'off':
        folders, changes = enemies.apply_enemies(files, Path(stock), T, seed, mode)
        spoiler['enemies'] = enemies.spoiler_lines(T, changes)      # (what this build placed: more than the exe's own list)
        grown_maps(files, stock)
    stats = gs.get('randomStats', 'off')
    if stats and stats != 'off':
        types = sum(b for n, b in (('hp', 1), ('atk', 2), ('spd', 4)) if n in gs.get('statTypes', ()))
        roll = enemies.rolls(T, stats, seed, gs.get('statChanges') == 'buffs', chance)
        enemies.apply_balance(files, T, roll, types)
        if types & 4: enemies.apply_speed(files, Path(stock), T, roll, range(483), folders)
        if colours in ('changed', 'random'):
            enemies.apply_colours(files, Path(stock), T, roll, seed, colours == 'random', folders, Path(out))
            grown_maps(files, stock)
    return folders


def grown_maps(files, stock):
    """A map's block on the disc is what its load pause reads.  Each patch that grows a block writes it back in whole
    sectors, so each step here rounds up what that step added (the edits' own growth is in their map_sizes)."""
    for rel, new in list(files.raw.items()):
        if not rel.endswith('sprite_info.bin'): continue
        m = int(rel.split('/')[1])
        last = files.block_size.get(rel)
        if last is None: last = (Path(stock) / rel).stat().st_size
        files.block_size[rel] = len(new)
        grew = len(new) - last + files.texture_growth.pop(m, 0)
        if not grew: continue
        sizes = files.doc('maps/map_sizes.json')
        if str(m) in sizes: sizes[str(m)] = -(-(sizes[str(m)] + grew) // 2048) * 2048


SKIP_LAST_DUNGEON = ((0xD3B2, 7), (0xD3C1, 7), (0xD3C2, 0), (0xD3C2, 6), (0xD3B3, 2), (0xD3B3, 3), (0xD3B3, 4), (0xD3B3, 5),
                     (0xD3B3, 6), (0xD3B3, 7), (0xD3B4, 0), (0xD3B4, 1))   # (GameData::apply_options: gates, buttons, scenes, seals)


def new_game(files, spoiler, seed, items):
    """PatchNewGame's preset values: starting HP / MP / Gilders, the items owned at start (the 0x80 bit of each
    item's second info record, EXE 0xA85EA + id * 8 = exe_data 0xA7DEA + id * 8), and without skipLastDungeon
    (nor an early Lake Shrine) none of the Lake Shrine starting flags."""
    gs = spoiler['gameSettings']
    for k, g in (('hp', 'startingHealth'), ('mp', 'startingMana'), ('gold', 'startingGold')):
        if g in gs: seed[k] = gs[g]
    owned = set(spoiler.get('randomizerSettings', {}).get('startingInventory', ('Dagger', 'Cloth Armor', 'Short Boots')))
    exe = None
    for i, x in enumerate(items[1:], 1):
        at = 0xA7DEA + i * 8
        if exe is None: exe = files.bin('exe_data.bin')
        if at >= len(exe): break
        v = exe[at] & 0x7F | (0x80 if x['name'] in owned else 0)
        if v != exe[at]: exe[at] = v
    if not gs.get('skipLastDungeon', True) and not gs.get('lakeShrineEarly'):
        writes = {a: v for a, v in seed['writes']}
        for off, bit in SKIP_LAST_DUNGEON:
            a = 0x801D0000 + (off & ~1)
            if a in writes: writes[a] &= ~(1 << (bit + 8 * (off & 1)))
        seed['writes'] = [[a, v] for a, v in writes.items() if v]


SHOP_MODEL, SHOP_ITEMS = 113, range(31, 120)


def _stream(gi, base, rel):
    """One direction's frame stream (5-byte frames while bit 7 is set, then the end code), as the extractor reads it."""
    if rel < 0:
        if rel == -1: return None
        raise ValueError('negative stream offset')
    p = base + rel; frames = []
    while True:
        b = gi[p]
        if b & 0x80:
            frames.append((b, struct.unpack_from('<h', gi, p + 1)[0], struct.unpack_from('<H', gi, p + 3)[0])); p += 5; continue
        end = gi[p:p + 2] if b == 0 else gi[p:p + 1]
        if not frames: raise ValueError('empty stream')
        if end == b'\x01': return frames, 'loop', None
        if len(end) == 2 and end[0] == 0: return (frames, 'hold', None) if end[1] & 128 else (frames, 'change', end[1])
        if len(end) == 1 and 1 < end[0] < 128: return frames, 'change', 0
        return frames, 'unknown', None


def _sets(gi, sets_off, streams_off):
    """A sprite's animation sets (14 bytes each) and the 8 the game can read past them (remake_overflow_anims)."""
    count = (streams_off - sets_off) // 14; out = []
    for i in range(count + 8):
        o = sets_off + i * 14
        if o + 14 > len(gi): break
        dirs = struct.unpack_from('<4h', gi, o); speed = struct.unpack_from('<H', gi, o + 8)[0]; unk, flags, sfx, accel = gi[o + 10:o + 14]
        st = []
        for d in dirs:
            try: st.append(_stream(gi, streams_off, d))
            except (ValueError, IndexError): st.append(None)
        if i >= count and all(s is None for s in st): break
        z = (flags << 8) | unk; z -= 0x10000 if z & 0x8000 else 0
        out.append((i, i >= count, speed, st, {'z_force': z, 'set_flags': flags, 'sfx': sfx + (0x100 if flags & 0x20 else 0), 'accel': accel & 15, 'anim_flags': accel}))
    return out


def shop_items(files, stock):
    """PatchNewGame's copy of a shop item's animation sets and streams (header +0, +4: sprite 113's) into every item
    object's header (sprites 31-119): items no shop sells can then be carried as shop items are.  The game does it
    in RAM (seedgen.after_flags_reset); the remake animates sprites from animations.json, so each item's is made
    again with those sets, its own pictures (frame table, header +0xC) and its own boxes (collision area, +8)."""
    gi = (Path(stock) / 'sprites/global_info.bin').read_bytes()
    u32 = lambda o: struct.unpack_from('<I', gi, o)[0]
    tab = u32(0xC); h = u32(tab + 4 * SHOP_MODEL); model = (u32(h), u32(h + 4))
    sets = _sets(gi, *model)
    for c in SHOP_ITEMS:
        v = u32(tab + 4 * c)
        if v in (0, 0xFFFFFFFF) or (u32(v), u32(v + 4)) == model: continue
        rel = f'sprites/global/{c:03d}/animations.json'
        if not (Path(stock) / rel).exists(): continue
        meta = files.doc(rel)
        own = {fr['image']: (fr['left'], fr['top'], fr['sort']) for a in meta['animations'] for d in a['directions'] if d for fr in d['frames'] if fr['image'] is not None}
        anims = []
        for i, overflow, speed, st, tail in sets:
            a = {'index': i, 'speed': speed, 'directions': []}
            if overflow: a['overflow'] = True
            for s in st:
                if s is None: a['directions'].append(None); continue
                frames = []
                for b, col, key in s[0]:
                    left, top, sort = own.get(key, (0, 0, 0))
                    frames.append({'image': key if key in own else None, 'left': left, 'top': top, 'ticks': max(1, b & 127), 'collision': col, 'sort': sort})
                a['directions'].append({'frames': frames, 'end': s[1], 'next': s[2]})
            a.update(tail); anims.append(a)
        meta['animations'] = anims
        coll = u32(v + 8)
        raws = sorted({fr['collision'] for a in anims for d in a['directions'] if d for fr in d['frames'] if fr['collision'] not in (-1, None, 0xFFFF)})
        meta['boxes'] = {str(r): list(struct.unpack_from('<3b3B', gi, coll + r)) for r in raws}


SHOP_RESTOCK = {"Naomi's Shop: Item #4": 0x2C4}      # (a one-time slot's own sold flag, cleared for Can repurchase all)
MERRICK_TABLE = ((15, 0x599), (25, 0x59B), (35, 0x59D), (45, 0x59F))   # (the trades his table's entity 17 stands for)


def shop_slots(files, T, spoiler, items, mode):
    """seed.json 'shop' (seedgen.shop_given / on_spawn / shop_map): Naomi's and Lurvy's slots that sell (their
    display entity, the offset of their script's give row in the seed's map.json - the VM's position there -,
    repeatable or not) and Item > Shop Restock; 'merrick_table': (flag, sprite) for Merrick's table, trade by trade."""
    src = {s['name']: s for s in json.loads((HERE / 'item_source.json').read_text(encoding='utf-8'))}
    slots = []
    for name, e in T['places'].items():
        if not name.startswith(("Naomi's Shop: Item #", "Lurvy's Shop: Item #")): continue
        a = e['address'][0]; at = a['offset'] + a['byte']
        rows = files.map(a['map'])['scripts'][a['script']]
        give = next(r['offset'] for r in rows if r['offset'] <= at < r['offset'] + len(r['bytes']) // 2)
        slots.append({'name': name, 'map': a['map'], 'entity': e['spriteAddress'][0]['index'], 'give': give,
                      'repeatable': bool(src.get(name, {}).get('forbidPreciousItems')), 'restock': SHOP_RESTOCK.get(name),
                      'restock_maps': [298, 302] if name in SHOP_RESTOCK else []})   # (Naomi's shop later: the same flag 0x2C4)
    slots.sort(key=lambda s: s['name'])
    placed = source_items(spoiler, items); ids = {x['name']: i for i, x in enumerate(items)}
    table = []
    for falcons, flag in MERRICK_TABLE:
        item = next((v for k, v in placed.items() if k.startswith(f"Merrick's Shop: Item traded for {falcons} Gilded Falcons")), None)
        if item is not None: table.append([flag, (look(items, ids.get(item, 0)) + 0x1E) & 255])
    return {'mode': mode, 'slots': slots}, table


def link_folders(folders, stock, out):
    """A sprite brought in from another map: its folder is a junction to that map's (real, with links, when the
    seed changed a file in it)."""
    import _winapi, os
    stock, out = Path(stock), Path(out)
    for m, cats in folders.items():
        for cat, donor in cats.items():
            src = stock / f'maps/{donor:03d}/sprites/{cat}'; t = out / f'maps/{m:03d}/sprites/{cat}'
            if not src.exists(): continue
            if t.exists():
                packed = (src / '_pack.bin').exists()
                for e in src.iterdir():
                    if not (t / e.name).exists() and not (packed and e.suffix == '.png' and e.name[0].isdigit()): os.link(e, t / e.name)
            else:
                t.parent.mkdir(parents=True, exist_ok=True); _winapi.CreateJunction(str(src), str(t))


def changed_strings(files):
    """{(map, string): line} of every US map string the build changed or added."""
    out = {}
    for rel, d in files.docs.items():
        if not (rel.startswith('maps/') and rel.endswith('/data.json')) or 'strings' not in d: continue
        old = json.loads((files.stock / rel).read_text(encoding='utf-8')).get('strings', {})
        for k, v in d['strings'].items():
            if old.get(k) != v: out[(int(rel[5:8]), int(k))] = v
    return out


def apply_languages(files, spoiler, T, items):
    """The randomizer's lines in every Dialogue & font language (lang_text.py, user 2026-11-07)."""
    import lang_text
    lang_text.apply(files, spoiler, T, items, source_items(spoiler, items), {x['name']: x.get('goldValue', 0) for x in items},
                    format_text, changed_strings(files), getattr(files, 'new_lines', {}))


def build(args, stock, out, say=lambda t: None):
    """Writes the seed's changed files into out; returns (spoiler, seed dict)."""
    with tempfile.TemporaryDirectory() as work:
        say('Randomizing the world')
        spoiler = run_logic(args, work)
    say('Writing the seed')
    gs = spoiler['gameSettings']; T = tables(); E = edits()
    prices = spoiler.get('randomizerSettings', {}).get('itemGilderValues', {})     # (Shop prices: the shops' prices and texts)
    items = [dict(x, goldValue=prices.get(x['name'], x.get('goldValue', 0))) for x in json.loads((HERE / 'item.json').read_text(encoding='utf-8'))]
    files = Files(stock); seed = {}
    for name in layers_for(gs):
        layer = E[name]; apply_layer(files, layer); seed.update(layer.get('seed', {}))
        w = layer.get('writes')
        if w: seed['writes'] = [x for x in seed['writes'] if x not in w['drop']] + w['add']
    seed['balance'] = 'us' if '--balance=us' in args else 'jp'   # (Enemies > Balance: the layers' records are JP; US & EU: the disc's)
    if seed['balance'] == 'us': files.docs['balance.json'] = json.loads((Path(stock) / 'balance.json').read_text(encoding='utf-8'))
    new_game(files, spoiler, seed, items)
    upgrade_pictures(files, items)
    shop_items(files, stock)
    apply_placements(files, spoiler, T, items)
    apply_text(files, spoiler, T, items)
    apply_story_edits(files)
    apply_map_edits(files)
    apply_crypt_door(files)
    if spoiler.get('doors'): apply_doors(files, spoiler['doors'])
    if spoiler['gameSettings'].get('dreamDungeonMode'): apply_dream_hints(files, spoiler); apply_dream_gates(files)
    if spoiler['gameSettings'].get('dreamDungeonMode') and '--twin-puzzles=Y' in args:
        spoiler['twinPuzzles'] = apply_twin_puzzles(files, permalink_seed(spoiler['permalink']))
    colours = next((a.split('=', 1)[1] for a in args if a.startswith('--stat-colors=')), 'no-change')
    chance = int(next((a.split('=', 1)[1] for a in args if a.startswith('--stat-chance=')), '100'))   # (Enemies > Stat chance)
    folders = apply_random(files, spoiler, T, stock, out, colours, chance)
    for m, cats in getattr(files, 'map_folders', {}).items(): folders.setdefault(m, {}).update(cats)
    apply_languages(files, spoiler, T, items)
    files.write(out)
    link_folders(folders, stock, out)
    seed['donors'] = {str(m): sorted(set(cats.values())) for m, cats in folders.items() if cats}   # (their sounds: sound_system.resolve)
    seed.update(foreign={}, name=spoiler['hashSentence'], progressive=gs.get('progressiveItems'), split_boots=gs.get('splitBootsEffects'), dreams=gs.get('dreamDungeonMode'),
                instant_text=gs.get('instantText'), archipelago=False, vessel_heal='--vessel-heal=N' not in args)
    on = next((a.split('=', 1)[1].split(',') for a in args if a.startswith('--drops=')), ('healing', 'magic', 'money'))
    seed['drops'] = {k: k in on for k in ('healing', 'magic', 'money')}
    inv = spoiler.get('randomizerSettings', {}).get('startingInventory', [])
    weapons = [x for x in inv if x in START_WEAPONS['random'] + START_WEAPONS['sfb'] and x != 'Dagger'] or ['Dagger']
    seed['weapon_group'] = next((x.get('slot', 1) for x in items if x['name'] == weapons[0]), 1)   # (new game equips it)
    seed['boss_resist'] = '--boss-resist=Y' in args            # (Late Game Boss Resistance: Adjusted, combat.seed_adjust)
    seed['weapon_balance'] = '--weapon-balance=Y' in args      # (Preset > Weapon Balance: Adjusted, seedgen.weapon_power / weapon_hit)
    shop = next((a.split('=', 1)[1] for a in args if a.startswith('--shop=')), 'consume')
    seed['shop'], seed['merrick_table'] = shop_slots(files, T, spoiler, items, shop)
    return spoiler, seed
