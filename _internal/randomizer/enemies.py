"""Random enemies and random stats on exported files.  The choices follow the randomizer's own rules and random
numbers (enemy_randomizer.hpp, random_stats.hpp), so a permalink makes the same enemies as ever."""
import io, json, math, struct
from concurrent.futures import ThreadPoolExecutor


class MT:
    """std::mt19937, raw output."""
    def __init__(self, seed):
        s = [seed & 0xFFFFFFFF]
        for i in range(1, 624): s.append((1812433253 * (s[-1] ^ (s[-1] >> 30)) + i) & 0xFFFFFFFF)
        self.s = s; self.i = 624

    def __call__(self):
        if self.i == 624:
            s = self.s
            for k in range(624):
                y = (s[k] & 0x80000000) | (s[(k + 1) % 624] & 0x7FFFFFFF)
                s[k] = s[(k + 397) % 624] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
            self.i = 0
        y = self.s[self.i]; self.i += 1
        y ^= y >> 11; y ^= (y << 7) & 0x9D2C5680; y ^= (y << 15) & 0xEFC60000
        return y ^ (y >> 18)


def bits(m): return bin(m).count('1')


def fits(T, m, shown):
    t = T['targets'].get(str(m))
    if t is None: return False
    kept, palettes, pages = t['pinned'], t['palettes'], 0
    for c, mask in t['own'].items():
        if int(c) in shown: kept |= mask
    pool = T['pools'][str(m)]
    for c in shown:
        if c in pool: continue
        i = t['incoming'].get(str(c))
        if i is None: return False
        palettes += i['palettes']
        pages += bits(T['donors'][f"{c}:{i['donor']}"]['pages']) - len(i['shared'])
    return palettes <= 41 and pages + bits(kept & 31) <= 5


FLYING = {428, 455, 473}     # Ghost, Wasp, Firebird: no 0x100 in their sprite headers' flags, they never land


def landing(files, T):
    """{(map, record)} of the enemies whose own map programs wait until on the ground (op 25: Tarn's Manor's falling
    templates, C 7 / C 25 of map 115); a type that never lands would hang there, out of reach (user 2026-11-03)."""
    out = set(); docs = {}
    for m, i, _ in T['records']:
        rel = f'maps/{m:03d}/map.json'                   # (read, not taken into the seed's files)
        doc = docs.get(m) or docs.setdefault(m, files.docs.get(rel) or json.loads((files.stock / rel).read_text(encoding='utf-8')))
        progs = doc['entities'][i]['programs']
        if any(r['op'] == 0x25 for slot, v in progs.items() if v >= 128 for r in doc['scripts'].get(f'{slot} {v - 128}', ())):
            out.add((m, i))
    return out


def plan(T, seed, mode, lands=frozenset()):
    """[(map, record, from type, to type)]."""
    rng = MT((seed ^ 0x454E454D) & 0xFFFFFFFF)
    below = lambda n: rng() % n
    records = T['records']; types = [0] * len(records); order = list(range(len(records))); shown = {}
    def able(k, c): return able_type(T, records[k], c, lands)
    def can(m, c):
        s = shown.setdefault(m, set())
        if c in s: return True
        return fits(T, m, s | {c})
    def shuffle(v):
        for k in range(len(v), 1, -1):
            j = below(k); v[k - 1], v[j] = v[j], v[k - 1]
    if mode == 'switch':
        shuffle(order)
        for k in order:
            m = records[k][0]
            ok = [c for c in T['types'] if able(k, c) and can(m, c)]
            types[k] = ok[below(len(ok))] if ok else records[k][2]
            shown.setdefault(m, set()).add(types[k])
    elif mode == 'swap':
        types = [c if able_type(T, r, c, lands) else r[2] for r, c in zip(records, swap_types(T, records, below))]
    else:
        bag = [r[2] for r in records]
        shuffle(bag); shuffle(order)
        def room(m):
            t = T['targets'].get(str(m))
            if t is None: return 0
            own = 0
            for mask in t['own'].values(): own |= mask
            return 5 - bits(t['pinned'] & ~own & 31) if t['incoming'] else 0
        order.sort(key=lambda k: room(records[k][0]))
        taken = [False] * len(bag)
        for k in order:
            m = records[k][0]; types[k] = 0
            for b, c in enumerate(bag):
                if not taken[b] and able(k, c) and can(m, c): taken[b] = True; types[k] = c; break
            if not types[k]:
                types[k] = records[k][2]
                if not can(m, types[k]) and shown.get(m):
                    types[k] = min((c for c in shown[m] if c not in FLYING or (m, records[k][1]) not in lands), default=types[k])
            shown.setdefault(m, set()).add(types[k])
    return [(r[0], r[1], r[2], types[k]) for k, r in enumerate(records)]


def able_type(T, record, c, lands=frozenset()):
    """Can type c replace this enemy?  A scripted one only becomes a type with every animation its scripts play (needs);
    one whose program waits until on the ground (lands) never a flying type."""
    if c in FLYING and (record[0], record[1]) in lands: return False
    need = T.get('needs', {}).get(f'{record[0]}:{record[1]}')
    return need is None or T['anims'][str(c)] > need


def spoiler_lines(T, changes):
    """The spoiler's 'enemies': per map, '#record Old -> New' for each enemy that changed."""
    out = {}
    for m, i, old, new in changes:
        if new != old: out.setdefault(f'Map {m}', []).append(f"#{i} {T['names'][str(old)]} -> {T['names'][str(new)]}")
    return out


def swap_types(T, records, below):
    """Mode::SWAP: one type-for-type mapping for the whole game, the one of 12 random starts (each improved by 600
    random two-type exchanges, kept when no fewer enemies change) that changes the most enemies; in a map without
    room for a new type its enemies keep their own.  The same steps and random numbers as enemy_randomizer.hpp
    (a map's part of the count is kept by the new types of its own types, so each exchange recounts only what moved)."""
    per_map = {}
    for m, _, c in records:
        v = per_map.setdefault(m, [])
        if c not in v: v.append(c)
    per_map = dict(sorted(per_map.items()))
    count = {}           # (enemy_randomizer.hpp keys it map << 16 | type in a std::map<uint16_t, ...>: the map is cut off,
    for m, _, c in records: count[c] = count.get(c, 0) + 1    # so it counts a type's enemies in the whole game; the same here)
    frm = sorted({c for _, _, c in records})
    def allowed_in(m, own, to):
        if fits(T, m, {to[c] for c in own}): return set(own)
        ok = set()
        for c in own:
            if fits(T, m, {to[d] if (d in ok or d == c) else d for d in own}): ok.add(c)
        return ok
    memo = {}
    def part(m, own, to):
        key = (m,) + tuple(to[c] for c in own)
        v = memo.get(key)
        if v is None: v = memo[key] = sum(count[c] for c in allowed_in(m, own, to) if to[c] != c)
        return v
    def changed(to): return sum(part(m, own, to) for m, own in per_map.items())
    best, best_score = None, 0
    for _ in range(12):
        target = list(frm)
        for k in range(len(target), 1, -1):
            j = below(k); target[k - 1], target[j] = target[j], target[k - 1]
        to = dict(zip(frm, target)); score = changed(to)
        for _ in range(600):
            x = frm[below(len(frm))]; y = frm[below(len(frm))]
            if x == y: continue
            to[x], to[y] = to[y], to[x]
            v = changed(to)
            if v >= score: score = v
            else: to[x], to[y] = to[y], to[x]
        if best is None or score > best_score: best_score, best = score, dict(to)
    allowed = {m: allowed_in(m, own, best) for m, own in per_map.items()}
    return [best[c] if c in allowed[m] else c for m, _, c in records]


def header(block):
    return list(struct.unpack_from('<12I', block, 0))


def rebuild_block(s, th, out, palettes, slots):
    """The block's lists again after new sprite records and palettes (enemy_import.hpp): palettes, then the script
    tables and code as one piece, the entity, effect and event lists; the roots and slots point at them."""
    trailer = s[th[6] - 4:th[6]]; roots = list(th)
    roots[5] = len(out)
    for p in palettes: out += p
    out += trailer
    shift = len(out) - th[6]
    out += s[th[6]:th[0]]
    for i in range(6, 12): roots[i] = th[i] + shift
    ee = th[0]
    while not (s[ee + 2] == 0 and s[ee + 3] == 0): ee += 20
    ee += 4
    roots[0] = len(out); out += s[th[0]:ee]
    roots[1] = len(out); out += s[th[1]:th[2]]
    ev = th[2]
    while struct.unpack_from('<I', s, ev)[0]: ev += 8
    ev += 4
    roots[2] = len(out); out += s[th[2]:ev]
    while len(out) % 4: out.append(0)
    struct.pack_into('<12I', out, 0, *roots)
    for slot, at in slots: struct.pack_into('<I', out, th[3] + slot * 4, at)
    return out


def import_steps(T, m, shown, classes):
    """enemy_import::swap_entry: each type's records and which of the map's free texture pages their quads get."""
    t = T['targets'][str(m)]; kept = t['pinned']; steps = []
    for c, mask in t['own'].items():
        if int(c) in shown: kept |= mask
    for c in sorted(shown):
        i = t['incoming'].get(str(c))
        if i is None: continue
        d = T['donors'][f"{c}:{i['donor']}"]
        pages = {a: b for a, b in i['shared']}
        for frm in range(8):
            if d['pages'] & (1 << frm) and frm not in pages:
                to = 0
                while to < 5 and kept & (1 << to): to += 1
                kept |= 1 << to; pages[frm] = to
        if c in classes: steps += [(c, st, pages) for st in d['steps']]
    return steps


def import_sprites(files, stock, T, m, steps):
    """The donors' sprite records into their slots of this map's block, with their palettes; returns {sprite: donor}."""
    s = files.info(m); th = header(s)
    tcount = (th[6] - th[5]) // 32
    palettes = [bytes(s[th[5] + i * 32:th[5] + i * 32 + 32]) for i in range(tcount)]
    out = bytearray(s)
    while len(out) % 4: out.append(0)
    slots = []; folders = {}; data = files.data(m)
    for c, (slot, donor, rel, size, quads, mask), pages in steps:
        ds = (stock / f'maps/{donor:03d}/sprite_info.bin').read_bytes(); dh = header(ds)
        payload = bytearray(ds[rel:rel + size]); start = len(out)
        for k in range(4):
            struct.pack_into('<I', payload, k * 4, struct.unpack_from('<I', payload, k * 4)[0] - rel + start)
        for q in quads:
            page, pal = payload[q] & 7, payload[q + 1]
            colours = ds[dh[5] + pal * 32:dh[5] + pal * 32 + 32]
            if colours not in palettes: palettes.append(colours)
            payload[q] = (payload[q] & 0xF8) | pages[page]; payload[q + 1] = palettes.index(colours)
        out += payload
        while len(out) % 4: out.append(0)
        slots.append((slot, start))
        cat = 256 + slot; head = _donor_data(stock, donor)['sprite_headers'].get(str(cat))
        if head is not None: data['sprite_headers'][str(cat)] = head
        folders[cat] = donor
    new = rebuild_block(s, th, out, palettes, slots)
    files.raw[f'maps/{m:03d}/sprite_info.bin'] = new
    # the texture pages they bring: the block's size on the disc, for the load pause (the pictures are in the folders)
    sizes = T['page_sizes']; to_page = {}
    for c, (slot, donor, rel, size, quads, mask), pages in steps:
        for frm, to in pages.items():
            if mask & (1 << frm): to_page[to] = (donor, frm)
    old = sizes.get(str(m), [])
    files.texture_growth[m] = sum(sizes[str(d)][frm] - (old[to] if to < len(old) else 0) for to, (d, frm) in to_page.items())
    return folders


_donors = {}


def _donor_data(stock, donor):
    d = _donors.get(donor)
    if d is None:
        d = _donors[donor] = json.loads((stock / f'maps/{donor:03d}/data.json').read_text(encoding='utf-8'))
    return d


def apply_enemies(files, stock, T, seed, mode):
    """Returns {map: {sprite number: donor map}}: the sprite folders the seed's map takes from other maps."""
    from build_seed import entity_from_record
    changes = plan(T, seed, mode, landing(files, T))
    shown, needed = {}, {}
    for m, i, old, new in changes:
        shown.setdefault(m, set()).add(new)
        if new not in T['pools'][str(m)]: needed.setdefault(m, set()).add(new)
    for m, i, old, new in changes:
        if new == old: continue
        info = files.info(m); first = struct.unpack_from('<I', info, 0)[0]
        info[first + i * 20 + 6] = (new - 256) & 255
        entity_from_record(files.map(m)['entities'][i], info[first + i * 20:first + i * 20 + 20])
    folders = {}
    for m, classes in sorted(needed.items()):
        folders[m] = import_sprites(files, stock, T, m, import_steps(T, m, shown[m], classes))
        room_for_block(files, m)
    return folders, changes


def room_for_block(files, m):
    """A grown block must not reach the map's strings in the game's memory."""
    d = files.data(m); end = d['sprite_info_addr'] + len(files.info(m))
    if d.get('strings_addr') and end > d['strings_addr']: d['strings_addr'] = (end + 3) & ~3


# ---------------------------------------------------------------- stats --
def rolls(T, mode, seed, buffs_only, chance=100):
    """{entry: (percent, what a buffed 1-damage attack becomes)}; the exe's uniform_int_distribution (libc++) takes
    the low bits of each number: one bit for down / up, one for 2 or 3.
    chance (Enemies > Stat chance): the odds, in percent, of a type's stat change, from numbers of its own; Mixed
    then halves or raises by half, a half each (Buffs raises)."""
    rng = MT((seed ^ 0x5A17B055) & 0xFFFFFFFF)
    chosen = (T['stat_enemies'] if mode in ('enemies', 'both') else []) + (T['stat_bosses'] if mode in ('bosses', 'both') else [])
    owner = {int(k): v for k, v in T['boss_owner'].items()}; out = {}
    keep = MT((seed ^ 0x3C6EF372) & 0xFFFFFFFF)
    for e in chosen:
        if e not in owner:
            p = 2 if buffs_only or rng() & 1 else 0                  # (Buffs: every one goes up, user 2026-11-03)
            out[e] = (50 + 50 * p if keep() % 100 < chance else 100, 2 + (rng() & 1))   # (Stat chance: the odds of a change, user 2026-11-03)
    for e in chosen:
        if e in owner: out[e] = out[owner[e]]
    return out


def apply_balance(files, T, roll, types):
    """HP and attack powers of every level tier; a record shared by entries changes once, for all of them."""
    if not types & 3: return
    doc = files.doc('balance.json'); chains = T['chains']; where = {}
    for e, offs in chains.items():
        for tier, off in zip(doc[int(e)], offs): where.setdefault(off, []).append(tier)
    def scale(v, pct):
        return max(1, min(255, (v * pct + 50) // 100)) if v else 0
    done = set()
    for e in sorted(roll):
        pct, one = roll[e]; hp, atk = (pct if types & 1 else 100), (pct if types & 2 else 100)
        for off in chains[str(e)]:
            if off in done: continue
            done.add(off)
            first = where[off][0]; new_hp = scale(first['hp'], hp)
            new_attacks = [[a[0], {1: 3, 2: 4}[a[1]] if a[1] in (1, 2) and atk > 100 else scale(a[1], atk)]   # (buffed 1 -> 3, 2 -> 4: user 2026-11-03)
                           for a in first['attacks']]
            for tier in where[off]: tier['hp'] = new_hp; tier['attacks'] = [list(a) for a in new_attacks]


# Maps whose cutscenes have Murggs (scripted entities of types 347 / 350 / 356): those types keep their stock speed
# there, user 2026-11-05.  (154, 382, 383, 386: the fought Murggs share the sprite record, so they keep it too.)
MURGG_SCENE_MAPS, MURGG_TYPES = (1, 2, 15, 154, 293, 368, 369, 382, 383, 386), (347, 350, 356)


def speed_ticks(v, pct):
    return max(1, min(127, (v * 100 + pct // 2) // pct))


def apply_speed(files, stock, T, roll, maps, folders):
    """Movement speed and frame delays of each changed type, in each map's sprite record and its animations.json."""
    for m in maps:
        name = f'maps/{m:03d}/sprite_info.bin'; info = files.raw.get(name)
        if info is None:
            if not (stock / name).exists(): continue
            info = bytearray((stock / name).read_bytes())
        if len(info) < 48: continue
        table = struct.unpack_from('<I', info, 0xC)[0]; end = struct.unpack_from('<I', info, 0x10)[0]
        for cls, (pct, _) in roll.items():
            layout = T['speed'].get(str(cls))
            if pct == 100 or layout is None or (m in MURGG_SCENE_MAPS and cls in MURGG_TYPES): continue
            slot = cls & 255
            if table + slot * 4 + 4 > end: continue
            ptr = struct.unpack_from('<i', info, table + slot * 4)[0]
            if ptr < 48: continue
            words, delays = layout
            if any(ptr + r + 2 > len(info) or struct.unpack_from('<H', info, ptr + r)[0] != v for r, v in words): continue
            if any(ptr + r + 1 > len(info) or info[ptr + r] != v for r, v in delays): continue
            files.raw[name] = info
            for r, v in words: struct.pack_into('<H', info, ptr + r, max(1, min(0xFFFF, (v * pct + 50) // 100)))
            for r, v in delays: info[ptr + r] = (v & 0x80) | speed_ticks(v & 0x7F, pct)
            rel = f'maps/{m:03d}/sprites/{cls}/animations.json'
            donor = folders.get(m, {}).get(cls)
            src = stock / f'maps/{donor:03d}/sprites/{cls}/animations.json' if donor is not None else stock / rel
            if rel not in files.docs and src.exists(): files.docs[rel] = __import__('json').loads(src.read_text(encoding='utf-8'))
            d = files.docs.get(rel)
            if d is None: continue
            for a in d.get('animations', ()):
                if a.get('speed'): a['speed'] = max(1, min(0xFFFF, (a['speed'] * pct + 50) // 100))
                for way in a.get('directions', ()):
                    for fr in (way or {}).get('frames', ()):
                        if fr.get('ticks'): fr['ticks'] = speed_ticks(fr['ticks'], pct)


# ---------------------------------------------------------------- colours --
def random_hue(cls, seed, T):
    cls = T['boss_owner'].get(str(cls), cls)
    h = (seed ^ 0x7A1C0B5D ^ (cls * 2654435761)) & 0xFFFFFFFF
    h ^= h >> 16; h = h * 0x85EBCA6B & 0xFFFFFFFF; h ^= h >> 13; h = h * 0xC2B2AE35 & 0xFFFFFFFF; h ^= h >> 16
    return (h % 1000) / 1000.0


def tint(word, target):
    """PatchStatColors::tint: a 15-bit colour pulled toward a hue, keeping its brightness."""
    if not word & 0x7FFF: return word
    r, g, b = (word & 31) / 31.0, ((word >> 5) & 31) / 31.0, ((word >> 10) & 31) / 31.0
    mx, mn = max(r, g, b), min(r, g, b); d = mx - mn; s = d / mx if mx > 0 else 0; h = 0.0
    if d > 0:
        h = math.fmod((g - b) / d, 6.0) if mx == r else (b - r) / d + 2 if mx == g else (r - g) / d + 4
        h /= 6
        if h < 0: h += 1
    amount = 0.6
    h = math.fmod(h + (math.fmod(target - h + 1.5, 1.0) - 0.5) * amount + 1.0, 1.0)
    s = min(1.0, s + (max(0.75, s) - s) * amount)
    c = mx * s; x = c * (1 - abs(math.fmod(h * 6, 2.0) - 1)); m = mx - c
    rr, gg, bb = ((c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x))[int(h * 6) % 6]
    q = lambda f: max(0, min(31, math.floor(f * 31 + 0.5)))
    out = (word & 0x8000) | q(rr + m) | q(gg + m) << 5 | q(bb + m) << 10
    return out | 1 if not out & 0x7FFF else out


def tint_block(s, roll, T, hue):
    """New palettes in a map's block for its buffed types; (new block, [types]) or None when the map stays as it is."""
    th = header(s); slots = (th[4] - th[3]) // 4; tcount = (th[6] - th[5]) // 32
    if th[5] + tcount * 32 + 4 != th[6]: return None
    palettes = [bytes(s[th[5] + i * 32:th[5] + i * 32 + 32]) for i in range(tcount)]
    out = bytearray(s)
    while len(out) % 4: out.append(0)
    done = []
    for cls in sorted(roll):
        if roll[cls][0] <= 100: continue
        target = hue(cls)
        layout = T['quads'].get(str(cls))
        if target is None or layout is None or (cls & 255) >= slots: continue
        ptr = struct.unpack_from('<i', s, th[3] + (cls & 255) * 4)[0]
        size, quads = layout
        if ptr < 48 or ptr + size > len(s): continue
        if any(q + 2 > size or s[ptr + q + 1] >= tcount for q in quads): continue
        remap = {}
        for q in quads:
            pal = s[ptr + q + 1]
            if pal not in remap:
                words = struct.unpack('<16H', palettes[pal])
                colours = struct.pack('<16H', *(tint(w, target) for w in words))
                if colours not in palettes: palettes.append(colours)
                remap[pal] = palettes.index(colours)
            out[ptr + q + 1] = remap[pal]
        done.append(cls)
    if not done or len(palettes) > 41: return None
    return rebuild_block(s, th, out, palettes, []), done


def expand(v): return v * 255 // 31


def tint_picture(raw, target, cache):
    """cache: {RGBA as a little-endian u32: its tinted u32}, each colour worked out once (transparent: unchanged)."""
    from PIL import Image
    from array import array
    im = Image.open(io.BytesIO(raw)).convert('RGBA'); px = array('I'); px.frombytes(im.tobytes())
    for v in set(px).difference(cache):
        if not v >> 24: cache[v] = v; continue
        w = round((v & 255) * 31 / 255) | round((v >> 8 & 255) * 31 / 255) << 5 | round((v >> 16 & 255) * 31 / 255) << 10
        t = tint(w, target)
        cache[v] = expand(t & 31) | expand(t >> 5 & 31) << 8 | expand(t >> 10 & 31) << 16 | (v & 0xFF000000)
    im.frombytes(array('I', map(cache.__getitem__, px)).tobytes()); b = io.BytesIO(); im.save(b, 'PNG', compress_level=1)
    return b.getvalue()


def tint_pack(raw, target):
    """A sprite folder's _pack.bin with each picture tinted (the pack's format: game/packs.py)."""
    n = struct.unpack_from('<I', raw, 0)[0]; index = json.loads(raw[4:4 + n]); cache = {}
    new, blobs, at = {}, [], 0
    for name, (o, l) in index.items():
        b = tint_picture(raw[4 + n + o:4 + n + o + l], target, cache)
        new[name] = [at, len(b)]; blobs.append(b); at += len(b)
    head = json.dumps(new, separators=(',', ':')).encode()
    return struct.pack('<I', len(head)) + head + b''.join(blobs)


def apply_colours(files, stock, T, roll, seed, random, folders, out):
    """Each map's block and the buffed types' pictures.  Pictures that start the same are tinted once."""
    hue = (lambda c: random_hue(c, seed, T)) if random else (lambda c: T['hues'].get(str(c)))
    jobs, faces = {}, {}
    for m in range(483):
        name = f'maps/{m:03d}/sprite_info.bin'; s = files.raw.get(name)
        if s is None:
            if not (stock / name).exists(): continue
            s = (stock / name).read_bytes()
        if len(s) < 48: continue
        r = tint_block(s, roll, T, hue)
        if r is None: continue
        files.raw[name] = r[0]
        for cls in r[1]:
            donor = folders.get(m, {}).get(cls, m)
            src = stock / f'maps/{donor:03d}/sprites/{cls}/_pack.bin'
            if src.exists(): jobs.setdefault((src.read_bytes(), hue(cls)), []).append((m, cls))
            face = src.with_name('portrait.png')    # (the game reads a portrait outside the pack)
            if face.exists(): faces.setdefault((face.read_bytes(), hue(cls)), []).append((m, cls))
    def run(key):
        b = tint_pack(*key)
        for m, cls in jobs[key]:
            f = out / f'maps/{m:03d}/sprites/{cls}/_pack.bin'; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b)
    def run_face(key):
        b = tint_picture(key[0], key[1], {})
        for m, cls in faces[key]:
            f = out / f'maps/{m:03d}/sprites/{cls}/portrait.png'; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b)
    with ThreadPoolExecutor(8) as pool: list(pool.map(run, jobs)); list(pool.map(run_face, faces))
    return len(jobs)
