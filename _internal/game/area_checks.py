"""Randomizer > Preset > Show area checks: how many of the current area's tracked checks are left, on the HUD under the
Gilder.  What counts and how maps group into areas are the Alundra Rando Tracker's (its item keywords, every option on;
its BizHawk script's map names and areas: tracker_link).  A check is done when its flag is set: the Archipelago
connector's flag (check_flags.json), else its chest's own flag (Lake Shrine, nightmares).  Shops and the Tarn's Manor
table have none (they can be taken again): as the tracker does, one is done once its item's count goes up while
Alundra is in its area (kept in the seed folder).  While a nightmare's door text is shown in Inoa (its question, or
what it needs), the number is that nightmare's checks left."""
import json, re
from pathlib import Path
import tracker_link as TL
from lua_tables import MAP_NAMES, ADDRESSES

KEYWORDS = ("Crest", "Bean", "Glove", "Cape", "Bomb", "Boots", "Bouquet", "Gem", "Bow", "Flail", "Fire Wand", "Ice Wand",
            "Broken Armor", "Small Key", "Secret Pass", "Earth", "Water", "Fire Magic", "Wind", "Ring", "Armlet", "Charm",
            "Sword", "Armor upgrade", "Magic Seed")
FLAGS = 0x801DD334
SUBS = {'overworld d2': ['d2 (cavern)'], "olen's house": ['house basement'], 'circle of fishes': ['cave before fire'],
        'burning pillars': ['(sluice key)']}
TIERS = {'sword upgrade': ('sword', 'fiend_blade', 'holy_sword', 'legend_sword'), 'flail upgrade': ('iron_flail', 'steel_flail'),
         'bow upgrade': ('hunters_bow', 'willow_bow'), 'armor upgrade': ('leather_armor', 'ancient_armor', 'silver_armor'),
         'earth magic upgrade': ('earth_scroll', 'earth_book'), 'water magic upgrade': ('water_scroll', 'water_book'),
         'fire magic upgrade': ('fire_scroll', 'fire_book'), 'wind magic upgrade': ('wind_scroll', 'wind_book'),
         "nava's charm": ('charm',)}

state = None
shown, asked = True, 0


def flag_bit(n): return FLAGS + ((n & 0x7FFF) >> 3), 1 << (n & 7)


def item_addresses(item):
    low = item.lower()
    if low in TIERS: return [ADDRESSES[k] for k in TIERS[low] if k in ADDRESSES]
    k = re.sub(r"[^a-z0-9]+", '_', low.replace("'", '')).strip('_')
    return [ADDRESSES[k]] if k in ADDRESSES else []


class Checks:
    def __init__(self, root, assets):
        self.root = root; sp = json.loads((root / 'spoiler.json').read_text(encoding='utf-8'))
        flags = json.loads((Path(__file__).resolve().parent / 'check_flags.json').read_text(encoding='utf-8'))
        T = None
        try:
            import gzip
            T = json.loads(gzip.decompress((Path(__file__).resolve().parent.parent / 'randomizer' / 'tables' / 'tables.json.gz').read_bytes()))
        except OSError: pass
        places = (T or {}).get('places', {}); ents = {}
        def entity_flag(m, i):
            if m not in ents:
                try: ents[m] = json.loads((assets / 'maps' / f'{m:03d}' / 'map.json').read_text(encoding='utf-8'))['entities']
                except OSError: ents[m] = []
            f = ents[m][i].get('collection_flag', 0) if i < len(ents[m]) else 0
            return flag_bit(f) if f else None
        try: self.taken = set(json.loads((root / 'area_checks.json').read_text(encoding='utf-8')))
        except (OSError, ValueError): self.taken = set()
        self.checks = []                                       # (line, (address, mask) or None, item addresses)
        self.dreams = {}                                       # nightmare id -> its checks
        self.door_texts = {}                                   # Inoa text index -> nightmare id
        try: strings = json.loads((assets / 'maps' / '241' / 'data.json').read_text(encoding='utf-8'))['strings']
        except (OSError, ValueError, KeyError): strings = {}
        for k, t in strings.items():
            d = re.match(r"Enter (?:the )?(\w+)'s? (?:nightmare|dream)\?|(?:The )?(\w+) (?:is|are) lost in a nightmare", t)
            if d: self.door_texts[int(k)] = (d.group(1) or d.group(2)).lower()
        for region in sp.get('itemSources', {}).values():
            for src, item in region.items():
                if not any(k in item for k in KEYWORDS): continue
                base = re.sub(r' \([^()]*\)$', '', src); bit = None
                if base in flags: bit = tuple(flags[base])
                else:
                    d = re.match(r'Dream \w+ - map (\d+) chest (\d+)', src)
                    if d: bit = entity_flag(int(d.group(1)), int(d.group(2)))
                    else:
                        a = next((a for a in places.get(base, {}).get('address', ()) if a['kind'] == 'entity'), None)
                        if a: bit = entity_flag(a['map'], a['index'])
                self.checks.append((f"{item} found in '{src}'", bit, item_addresses(item)))
                d = re.match(r'Dream (\w+) - ', src)
                if d: self.dreams.setdefault(d.group(1), []).append(self.checks[-1])
        self.area = None; self.keys = (); self.prev = {}; self.count = None

    def keywords(self, m):
        loc = MAP_NAMES[m - 1] if 1 <= m <= len(MAP_NAMES) else None
        loc = {'Inoa Village': 'Inoa', 'Top-Left Cave': 'Left Cave', 'Burning Pillars': '(Sluice Key)'}.get(loc, loc)
        loc = TL.check_location(loc).lower()
        return tuple([loc] + SUBS.get(loc, []))

    def frame(self, g):
        if g.cur_map != self.area:
            self.area = g.cur_map; self.keys = self.keywords(g.cur_map)
            self.here = [c for c in self.checks if any(k in c[0].lower() for k in self.keys)]
            self.prev = {a: g.mem.u8(0x80000000 | a) for c in self.here if c[1] is None for a in c[2]}
        n = 0; save = False
        for line, bit, addrs in self.here:
            if bit is not None:
                if not g.mem.u8(0x80000000 | bit[0]) & bit[1]: n += 1
                continue
            if line in self.taken: continue
            rose = False
            for a in addrs:
                v = g.mem.u8(0x80000000 | a)
                if v > self.prev.get(a, v): rose = True
                self.prev[a] = v
            if rose: self.taken.add(line); save = True
            else: n += 1
        if save:
            try: (self.root / 'area_checks.json').write_text(json.dumps(sorted(self.taken)), encoding='utf-8')
            except OSError: pass
        self.count = min(n, 99)

    def dream_left(self, g):
        """A nightmare's door text on screen in Inoa: that nightmare's checks left (else None)."""
        from engine import message as emsg
        n = getattr(g, '_text_num', None)
        if g.cur_map != 241 or n is None or not n & 0x80 or not emsg.msg_busy(g): return None
        d = self.door_texts.get(n & 0x7F)
        if d is None: return None
        return min(sum(1 for line, bit, addrs in self.dreams.get(d, ()) if bit is not None and not g.mem.u8(0x80000000 | bit[0]) & bit[1]), 99)


def count(g):
    """The number for the HUD (None: hidden - the option is off, no seed, or an Archipelago seed)."""
    global state
    import seedgen
    global shown, asked
    asked = (asked + 1) % 120
    if asked == 1: shown = seedgen.load_options().get('area-checks', 0) % 2 == 0    # (the menu's choice, read now and then)
    if seedgen.active is None or seedgen.active.get('archipelago') or not shown: state = None; return None
    try:
        if state is None or state.root != seedgen.root:
            state = Checks(seedgen.root, seedgen.root / 'assets')
        state.frame(g)
        d = state.dream_left(g)
        return state.count if d is None else d
    except Exception:
        return None
