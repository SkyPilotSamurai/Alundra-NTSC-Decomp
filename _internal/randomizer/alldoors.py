"""Random Door & Warps: All Doors.  Going through a
door lands where another door's far side would have landed him, and that door leads back.  A layout is kept only
when the door-level logic below proves the randomizer's placement can still be played through (every item of
its playthrough reached); otherwise another layout is made (same seed: same layouts, in the same order).

Logic: tables/alldoors.json.gz, packed from the static room research (extras/game edits/tools/reachability,
rooms_out.json + door-table remaps; never from running the game).  Nodes are (map, warp id): having arrived at
that warp.  Inside a map, 'links' give W -> W' with needs (OR of ANDs of item names, 'flag:0xNNNN', key counts).
A warp lands at the entry its far side names; scripted warps ('S:...') land at 'script ...' entries; portals go
through the door table (op 0x38 remaps).  User rules (2026-11-08): switches / platforms / puzzles count as doable
unless they need an item; shops sell from the counter (Merrick: Gilded Falcons); single locations: SOURCE_EXTRA.

Every screen is randomly connected (user 2026-11-09): every two-way door / warp / screen edge, Inoa (the
randomizer's copy, 241) and the casino included, pairs with a random other one, two-way.  One-way warps (holes,
drops, teleport pads) and scripted warps to another map (op 53: boss exits, puzzle teleports, the desert maze's way
out) each take a random one-way / scripted landing.  Left alone: dreams, unused / debug / cutscene / ending maps,
Inoa's story copies, a scripted warp inside its own map.  A one-way must lead on and loop back (loops_back)."""
import collections, gzip, json, random, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPGRADES = {'Sword upgrade': ('Sword', 'Fiend Blade', 'Holy Sword', 'Legend Sword'), 'Flail upgrade': ('Iron Flail', 'Steel Flail'),
            'Bow upgrade': ("Hunter's Bow", 'Willow Bow'), 'Armor upgrade': ('Leather Armor', 'Ancient Armor', 'Silver Armor'),
            'Earth Magic upgrade': ('Earth Scroll', 'Earth Book'), 'Water Magic upgrade': ('Water Scroll', 'Water Book'),
            'Fire Magic upgrade': ('Fire Scroll', 'Fire Book'), 'Wind Magic upgrade': ('Wind Scroll', 'Wind Book')}
DEBUG = False
START_MAP = 242                     # Jess's house: a new game starts there
LEFT_OUT = ('dream', 'unused', 'debug', 'cutscene', 'inoa village', 'sybill', 'yustel', 'melzas', 'final')
# The randomizer's Inoa: Jess's house (242) remaps the village (162 -> 241) as a new game starts, and the village's
# south part (166) is only ever reached as 245 from 241.  Only that copy is used (user 2026-11-09); the story copies
# of Inoa stay out.
INOA_ALIAS = {162: 241, 166: 245}
RANDO_INOA = {241, 243, 244, 245, 246, 247, 258}


def plain(loc): return re.sub(r' \([^()]*\)$', '', loc)


# Nightmare mode: the dreamers' front doors in Inoa (map 241; build_seed apply_dream_gates / apply_dream_doors) ask
# for the dream; (door square, dream map, landing square, gate).  Read from the randomizer's dream edits (B 8-B 13).
CRESTS = ['Garnet Crest', 'Agate Crest', 'Diamond Crest', 'Ruby Crest', 'Sapphire Crest', 'Topaz Crest', 'Emerald Crest']
FLAIL = [['Iron Flail'], ['Steel Flail']]
def _and(*dnfs):
    out = [[]]
    for d in dnfs: out = [a + b for a in out for b in d]
    return out
DREAM_DOORS = [((5, 33), 44, (6, 58), [['flag:0x006C']]),                                  # Wendell: Tarn's Manor cleared
               ((5, 33), 109, (12, 20), [[a, b] for i, a in enumerate(CRESTS) for b in CRESTS[i + 1:]]),   # twins: 2 crests
               ((15, 52), 41, (6, 58), [['Bomb']]),                                         # Bonaire
               ((12, 33), 100, (5, 54), _and(FLAIL, [['Bomb']])),                           # Giles
               ((46, 52), 123, (10, 54), [[c] for c in CRESTS]),                            # Kline: a crest
               ((47, 35), 53, (12, 19), _and(FLAIL, [['Bomb', 'Merman Boots', 'Sand Cape', 'Long Boots']])),  # Elene
               ((26, 54), 440, (36, 59), _and(FLAIL, [['Merman Boots']]))]                  # Meia
DREAM_CHEST = re.compile(r'^Dream (\w+) - map (\d+) chest \d+$')
# A dream's chests: got once its first map is entered (dreams are not shuffled; inside them the randomizer's own
# dream rules hold).  Olen's: from his house (303).
DREAM_ENTRY = {'wendell': 44, 'twins': 109, 'bonaire': 41, 'giles': 100, 'kline': 123, 'elene': 53, 'meia': 440, 'olen': 303}


def load():
    return json.loads(gzip.decompress((HERE / 'tables' / 'alldoors.json.gz').read_bytes()))


def _murgg_woods_4():
    """Map 385's links (see World.MAP_LINKS): the three corridors, the bridge ends, and what lowered blocks open."""
    H = {'L': ('W20', 'W21', 'W22', 'W23'), 'M': ('W28', 'W29', 'W16', 'W17'), 'R': ('W18', 'W19', 'W14', 'W15'),
         'BW': ('W24', 'W25'), 'BE': ('W12', 'W13')}
    L, M = 'node:385:W20', 'node:385:W28'
    down = {'L': [L], 'R': [M], 'LM': [L], 'MR': [M, L], 'LMR': [M, L]}
    out = {}
    for ws in H.values():                                           # one corridor / bridge end: one place
        for a in ws: out[a] = [(b, [[]]) for b in ws if b != a]
    for end, steps in (('BW', (('L', 'L'), ('LM', 'M'), ('LMR', 'R'), ('LMR', 'BE'))),
                       ('BE', (('R', 'R'), ('MR', 'M'), ('LMR', 'L'), ('LMR', 'BW')))):
        for a in H[end]:
            for d, h in steps: out[a] += [(b, [list(down[d])]) for b in H[h]]
    return out


class World:
    SHOPS = {"Merrick's Shop: ": "Merrick's Shop: Item traded for 20 Gilded Falcons",
             "Lurvy's Shop: ": "Lurvy's Shop: Item #1", "Naomi's Shop: ": "Naomi's Shop: Item #1"}
    SOURCE_EXTRA = {   # (user 2026-11-08) Magyscar 2 (map 87): needs a wand or bombs
        "Magyscar: Chest behind vines in switchable platforms room": [['Fire Wand'], ['Ice Wand'], ['Bomb']]}

    # User rules for single links (2026-11-08): (map, from, to, needs) added to the research's links.
    # Nirude's Lair 1 (map 421): the elevated arena (many faces fight -> both falling chests -> elevator) is doable
    # from the lower area.
    EXTRA_LINKS = [(421, w, 'W1', [[]]) for w in ('W0', 'W2', 'W5', 'W7')]
    # Murgg Woods 1 (map 382, 2026-11-09): the wall switch at (3,36) (C 20) sets temp flag 0x80C8 for ~13 s
    # (3x240+60 frames), which lowers the stairway cover at (21-22,41-42) (C 9) flush with the h3 shelves: the
    # low floor (W5, W6 - behind the bomb rock) reaches the west shelf (W3, W8).  Switch puzzle = free (user rule);
    # the randomizer's own logic has the bridge cave, the west A2 chests and A1 all in one node behind the bomb.
    EXTRA_LINKS += [(382, a, b, [[]]) for a in ('W5', 'W6') for b in ('W3', 'W8')]
    # Maps whose insides are all puzzles / fights / platforms with no item needs (user rule; the randomizer's own
    # logic has Nirude's Lair as one node with nothing needed inside): every way in reaches every warp, chest and
    # flag of the map.
    FREE_MAPS = {421, 422, 423, 424, 425, 426}
    # Murgg Woods 4 (map 385) block puzzle, from its scripts (2026-11-09; user: "all the blocks need to be lowered
    # to get through", a wrong switch sends him back).  Three 2x2 stairway covers (entities 6/7/8, C 7/8/9) stand where
    # the h4 bridge (y46-47) crosses the three h2 corridors; each is down while its flag is set (L 0x0268, M 0x0269,
    # R 0x026A).  Up (as found) its top is 2 units above the bridge and its underside 32 px above the corridor floor,
    # so the corridor runs under it (as the research has it); down, its top is flush with the bridge and it parts the
    # corridor.  A lowered block lets him off the bridge into its corridor.  Six floor switches (C 1-6): top-left
    # clears L, toggles M; top-middle clears M, sets R; top-right clears L, toggles M, clears R; bottom-left toggles L;
    # bottom-middle clears all; bottom-right toggles L, clears M.  From all up: L = bottom-left; L+M = top-left,
    # bottom-left; M+R = top-middle, top-left; all = top-middle, top-left, bottom-left (L and M only meet in the
    # bottom-left toggle, so the left corridor's south half is needed - it is entered by its own panels or, block up,
    # from its north half).  Bottom-middle resets.  So the bridge needs the corridors whose switches it uses.
    MAP_LINKS = {385: _murgg_woods_4()}
    # Overworld E1 after Nirude (map 439): its lair doors W4-W9 open once the faces / Mini-Nirudes are beaten - the
    # Spring Bean is needed for those, and the top-left head only from E1's top-left entrance (W1, from D1) (user;
    # randomizer logic: e1_left <-> nirude_lair needs e1_top_left and e1_behind_spring).
    LINK_EXTRA = {(439, 'W%d' % i): ['Spring Bean', 'node:439:W1'] for i in range(4, 10)}

    def __init__(self, data):
        self.maps = data['maps']
        for m in self.maps.values():
            for w in m['warps'] + m['script_warps']:
                w['to_map0'] = w['to_map']; w['to_map'] = INOA_ALIAS.get(w['to_map'], w['to_map'])
        def left(mi): return mi not in RANDO_INOA and any(x in self.maps[str(mi)]['name'].lower() for x in LEFT_OUT)
        self.left_out = {int(k) for k in self.maps if left(int(k))}
        self.remaps = {int(k): [r for r in v if r[1] not in self.left_out and r[0] not in self.left_out]
                       for k, v in data.get('remaps', {}).items() if int(k) not in INOA_ALIAS and int(k) not in self.left_out}
        self.remaps = {k: v for k, v in self.remaps.items() if v}
        self._land = {}
        self.links = collections.defaultdict(list); self.dest = {}; self.entry = {}
        # (2026-11-09) what standing at a landing needs (its squares' needs: deep water - boots, an object's box): by
        # warp (to map, from map, how) and by node (none when any landing on it needs nothing)
        self.entry_need = {}; nn = collections.defaultdict(list); free = set()
        self.sources = []; self.flag_setters = collections.defaultdict(list); self.keys = []
        for k, m in self.maps.items():
            mi = int(k)
            for l in m['links']: self.links[(mi, l['from'])].append((l['to'], l['needs']))
            for w in m['warps']: self.dest[(mi, w['id'])] = (w['to_map'], tuple(w['to'][:2]), w['kind'], 'warp ' + w['id'][1:])
            for sw in m['script_warps']: self.dest[(mi, sw['id'])] = (sw['to_map'], tuple(sw['to'][:2]), 'script', 'script ' + sw['id'][2:])
            for e in m['entries']:
                at = e['at'] or e['id']; self.entry[(mi, e['from_map'], e['from'])] = at
                if e.get('need'):
                    self.entry_need[(mi, e['from_map'], e['from'])] = e['need']
                    nn[(mi, at)] += [x for x in e['need'] if x not in nn[(mi, at)]]
                else: free.add((mi, at))
            for s in m['item_sources']: self.sources.append((s['name'], mi, s['needs']))
            for f in m['flags_set']: self.flag_setters[f['flag']].append((mi, f['needs']))
            for ks in m['key_sources']: self.keys.append((mi, ks.get('needs', {})))
        self.node_need = {n: v for n, v in nn.items() if n not in free}
        for m, frm, to, needs in self.EXTRA_LINKS: self.links[(m, frm)].append((to, needs))
        for (m, frm), lst in list(self.links.items()):
            self.links[(m, frm)] = [(to, [list(alt) + self.LINK_EXTRA[(m, to)] for alt in needs]) if (m, to) in self.LINK_EXTRA
                                    else (to, needs) for to, needs in lst]
        for m, table in self.MAP_LINKS.items():
            for frm, lst in table.items(): self.links[(m, frm)] = list(lst)
        for m in self.FREE_MAPS:
            mm = self.maps.get(str(m))
            if mm is None: continue
            ins = [w['id'] for w in mm['warps']] + [e['id'] for e in mm['entries'] if not e['at']]
            outs = [w['id'] for w in mm['warps']] + [w['id'] for w in mm['script_warps']]
            for a_ in ins: self.links[(m, a_)] = [(b_, [[]]) for b_ in outs if b_ != a_]
            every = {a_: [[]] for a_ in ins}
            self.sources = [(n, mi, every if mi == m else pw) for n, mi, pw in self.sources]
            for f, setters in self.flag_setters.items():
                self.flag_setters[f] = [(mi, every if mi == m else pw) for mi, pw in setters]
            self.keys = [(mi, every if mi == m else pw) for mi, pw in self.keys]
        out = []
        for name, m, pw in self.sources:
            for pre, anchor in self.SHOPS.items():
                if name.startswith(pre) and name != anchor:
                    a = next((x for x in self.sources if x[0] == anchor), None)
                    if a is not None:
                        f = re.search(r'traded for (\d+) Gilded Falcons', name)
                        extra = ['falcons:' + f.group(1)] if f else []
                        pw = {w: [list(alt) + extra for alt in n] for w, n in a[2].items()}; m = a[1]
                    break
            extra = self.SOURCE_EXTRA.get(name)
            if extra: pw = {w: [list(alt) + list(e) for alt in n for e in extra] for w, n in pw.items()}
            out.append((name, m, pw))
        self.sources = out

    def land(self, m, sq):
        k = (m, sq); c = self._land.get(k, 0)
        if c == 0: c = self._land[k] = self._land_(m, sq)
        return c

    def _land_(self, m, sq):
        mm = self.maps.get(str(m))
        if mm is None: return None
        x, y = sq; best = None
        for w in mm['warps']:
            x1, y1, x2, y2 = w['rect']
            d = max(x1 - x, x - x2, 0) + max(y1 - y, y - y2, 0)
            if d <= 2 and (best is None or d < best[0]): best = (d, w['id'])
        if best: return best[1]
        for e in mm['entries']:
            if any(abs(a - x) + abs(b - y) <= 1 for a, b in e['squares']): return e['at'] or e['id']
        return None

    def warps(self, m): return [w['id'] for w in self.maps[str(m)]['warps']]


def solve(world, placement, start, inventory=(), redirect=None, dreams=False, init=None, stop=None):
    """Fixed point: nodes reached, items had, flags set (temporary ones per map), locations got.  dreams: Nightmare
    mode - the dream doors of Inoa 241 lead into the dreams (DREAM_DOORS); a dream chest is got once its map is.
    stop: a set of nodes - return as soon as one is reached (loops_back only asks whether he gets home)."""
    have = collections.Counter(inventory); flags = set(); got = set(); reached = set(start); keys_got = 0
    if init is not None:                           # (a one-way spot's state when he first got there: traps())
        have = collections.Counter(init[0]); flags = set(init[1]); keys_got = init[2]; got = set(init[3])
    door_w = {}
    if dreams:
        for sq, dm, land, gate in DREAM_DOORS:
            door_w.setdefault(sq, [w['id'] for w in world.maps['241']['warps'] if w['rect'][0] <= sq[0] <= w['rect'][2] and w['rect'][1] <= sq[1] <= w['rect'][3]])
    known_flags = set(world.flag_setters)
    key_doors = set()      # (keys are one counter in the game and each door uses one: a key door counts as open only
                           #  while the keys got cover every key door met so far - no key is trusted twice)
    def tok_ok(t, m=None):
        if isinstance(t, dict):
            key_doors.add(tuple(t.get('doors') or ()) or id(t))
            return keys_got >= len(key_doors) - 1 + t.get('quantity', 1)
        if t.startswith('falcons:'): return have['Gilded Falcon'] >= int(t[8:])
        if t.startswith('node:'): _, nm, nw = t.split(':'); return (int(nm), nw) in reached
        if t.startswith('flag:'):
            f = t[5:]
            if int(f, 16) & 0x8000: return (m, f) in flags
            return f in flags or f not in known_flags
        if have[t]: return True
        for up, tiers in UPGRADES.items():
            if t in tiers: return have[up] > tiers.index(t)
        return False
    def ok(needs, m=None): return any(all(tok_ok(t, m) for t in alt) for alt in needs)
    def from_here(m, per_w): return any(ok(n, m) for w, n in per_w.items() if (m, w) in reached)
    byname = {plain(k): v for k, v in placement.items()}
    keys_done = set(); changed = True
    rounds = []                                    # (snapshot, nodes first reached in that round) - for traps()
    maps_in = {mm for mm, _ in reached}
    stranded = {}                                  # (landing: the door into it, taken before he can stand there)
    order = {n: 0 for n in reached}                # (the order nodes are first reached in: locked_landings)
    parent = {}                                    # (the node each was first reached from: loops_back's way in)
    def arrive_ok(src, n, need):
        # (a damage floor - lava, spikes: Charm Boots alone - hurts but does not hold him: not stranded)
        if not need or ok(need, n[0]) or (['Charm Boots'] in need and not any('Merman Boots' in a_ for a_ in need)): return True
        stranded.setdefault(n, src); pending.add(src); return False
    done = set(); pending = set()                  # (nodes walked; nodes with a way out not open yet: walked again
    while changed:                                 #  each round - everything else only once, as nothing closes)
        changed = False
        snap = (collections.Counter(have), set(flags), keys_got, set(maps_in), set(got))
        before = set(reached)
        todo = sorted((reached - done) | pending, reverse=True); pending = set()     # (sorted: key doors are met in one order)
        while todo:
            node = todo.pop(); m, w = node; nxt = []; done.add(node)
            for w2, needs in world.links.get(node, ()):
                if ok(needs, m): nxt.append((m, w2))
                else: pending.add(node)
            d = redirect.get(node) if redirect else None
            if d is not None:
                for n, cm in d:
                    if cm is None or cm in maps_in:
                        if arrive_ok(node, n, world.node_need.get(n)): nxt.append(n)
                    else: pending.add(node)
            elif node in world.dest:
                tm, sq, kind, how = world.dest[node]
                maps_ = [tm]
                if kind != 'script':
                    for v, cm, key in world.remaps.get(tm, ()):
                        if cm in maps_in: maps_.append(v)
                        else: pending.add(node)
                for tm2 in maps_:
                    at = world.entry.get((tm2, m, how))
                    nd = world.entry_need.get((tm2, m, how))
                    if at is None and (tm2 != tm or tm in RANDO_INOA): at = world.land(tm2, sq); nd = world.node_need.get((tm2, at))
                    if at is not None and arrive_ok(node, (tm2, at), nd): nxt.append((tm2, at))
            for n in nxt:
                if n not in reached:
                    reached.add(n); maps_in.add(n[0]); todo.append(n); changed = True; order[n] = len(order); parent[n] = node
                    if stop is not None and n in stop: return reached, have, flags, got
        rounds.append((snap, reached - before))
        for name, m, per_w in world.sources:
            if name not in got and from_here(m, per_w):
                got.add(name); item = byname.get(name)
                if item: have[item] += 1
                changed = True
        if dreams:
            in_241 = sorted(w for (mm, w) in reached if mm == 241)
            for sq, dm, land, gate in DREAM_DOORS:
                if not ok(gate): continue
                ws = door_w[sq]                    # (he can stand at the door: a link to its square's portal, or on it)
                if not any(w in ws or any(w2 in ws and ok(n, 241) for w2, n in world.links.get((241, w), ())) for w in in_241):
                    continue
                at = world.land(dm, land)
                nodes = [(dm, at)] if at else [(dm, w['id']) for w in world.maps[str(dm)]['warps']]
                for n in nodes:
                    if n not in reached: reached.add(n); maps_in.add(n[0]); changed = True; order[n] = len(order)
            for name, item in byname.items():
                mo = DREAM_CHEST.match(name)
                if mo and name not in got and any(mm == DREAM_ENTRY.get(mo.group(1).lower(), int(mo.group(2))) for mm, _ in reached):
                    got.add(name); have[item] += 1; changed = True
        for f, setters in world.flag_setters.items():
            if int(f, 16) & 0x8000:
                for m, pw in setters:
                    if (m, f) not in flags and from_here(m, pw): flags.add((m, f)); changed = True
            elif f not in flags and any(from_here(m, pw) for m, pw in setters): flags.add(f); changed = True
        for i, (m, pw) in enumerate(world.keys):
            if i not in keys_done and (not pw or from_here(m, pw)) and any((m, w) in reached for w in world.warps(m)):
                keys_done.add(i); keys_got += 1; changed = True
    solve.rounds = rounds
    solve.stranded = stranded; solve.order = order; solve.parent = parent
    return reached, have, flags, got


def traps(world, start, redirect=None, dreams=False):
    """After solve(): nodes he can reach but not leave - no way back to the start with only what he had when he
    first got there (a one-way drop, Overworld E1's ledges ...).  Dream maps are left out (a dream ends in its own
    warp home).  Uses solve.rounds."""
    known_flags = set(world.flag_setters)
    dream_maps = {dm for _, dm, _, _ in DREAM_DOORS} | {int(k) for k, m in world.maps.items() if 'dream' in m['name'].lower()}
    seen_all = set(); out = []
    back = collections.defaultdict(set)            # reverse edges among the nodes known so far (only ever grows: the
    pend = []                                      #  state does - an edge not open yet waits in pend)
    def arrive_need(m, tm2, at, how):
        return world.entry_need[(tm2, m, how)] if world.entry.get((tm2, m, how)) == at and (tm2, m, how) in world.entry_need             else world.node_need.get((tm2, at))
    def arrive(m, w, tm2, tm, sq, how):
        at = world.entry.get((tm2, m, how))
        if at is None and (tm2 != tm or tm in RANDO_INOA): at = world.land(tm2, sq)
        return at
    for i, ((have, flags, keys_got, maps_r, got_r), new) in enumerate(solve.rounds):
        if i == 0: new = set(new) | set(start)    # (the start's own ways out: a door of Jess's house can lead to a trap)
        seen_all |= new
        def tok_ok(t, m=None):
            if isinstance(t, dict): return keys_got >= t.get('quantity', 1)
            if t.startswith('falcons:'): return have['Gilded Falcon'] >= int(t[8:])
            if t.startswith('node:'): _, nm, nw = t.split(':'); return (int(nm), nw) in seen_all
            if t.startswith('flag:'):
                f = t[5:]
                if int(f, 16) & 0x8000: return (m, f) in flags
                return f in flags or f not in known_flags
            if have[t]: return True
            for up, tiers in UPGRADES.items():
                if t in tiers: return have[up] > tiers.index(t)
            return False
        def ok(needs, m=None): return any(all(tok_ok(t, m) for t in alt) for alt in needs)
        for (m, w) in new:
            for w2, needs in world.links.get((m, w), ()): pend.append(((m, w), (m, w2), needs, None))
            d = redirect.get((m, w)) if redirect else None
            if d is not None:
                for n, cm in d: pend.append(((m, w), n, world.node_need.get(n), cm))
            elif (m, w) in world.dest:
                tm, sq, kind, how = world.dest[(m, w)]
                at = arrive(m, w, tm, tm, sq, how)
                if at is not None: pend.append(((m, w), (tm, at), arrive_need(m, tm, at, how), None))
                if kind != 'script':
                    for v, cm, key in world.remaps.get(tm, ()):
                        at = arrive(m, w, v, tm, sq, how)
                        if at is not None: pend.append(((m, w), (v, at), arrive_need(m, v, at, how), cm))
        left = []
        for e in pend:
            src, dst, needs, cm = e
            if (needs is None or ok(needs, dst[0])) and (cm is None or cm in maps_r): back[dst].add(src)
            else: left.append(e)
        pend = left
        home = set(start); todo = list(start)
        while todo:
            n = todo.pop()
            for p in back.get(n, ()):
                if p not in home: home.add(p); todo.append(p)
        out += [(n, (have, flags, keys_got, got_r), {n: set(back.get(n, ()))}, home)    # (its own way in as of now:
                for n in new if n not in home and n[0] not in dream_maps]                 #  back keeps growing)
    return out


def loops_back(world, placement, start, inv, redirect, dreams, stuck, known):
    """[] when every new one-way loops back, else the failing spots.  User rule (2026-11-08): a one-way is fine when it leads on and loops back round - from each new dead-end
    spot, with what he had there and whatever he collects from it, he must get back to the start.  Spots that can
    walk to another stuck spot share its answer, so only the last spots of each chain are checked.  'Back' is any place
    that connects to the rest of the world (Jess's house is only where that is measured from)."""
    # (a spot the research gives no way out at all - no link, no warp: a cutscene landing, a boss room's scripted
    #  exit - is a gap in the data, not a trap the shuffle made)
    def exits(n): return bool(world.links.get(n)) or n in world.dest or (redirect and n in redirect)
    # (overworld maps only: a shuffled door is two-way and lands beside its way back, so the shuffle's own risk is the
    #  overworld's one-way drops - Overworld E1's ledges; inside dungeons the research's gaps cannot be told from traps)
    def overworld(n): return world.maps[str(n[0])]['name'].startswith('Overworld')
    # (a spot in a map the shuffle leaves alone - a cutscene, a story copy of Inoa - keeps its own way out)
    new = [(n, st, back, home) for n, st, back, home in stuck if n not in known and exits(n) and n[0] not in world.left_out]
    if not new: return []
    nodes = {n for n, _, _, _ in new}; state = {n: st for n, st, _, _ in new}; homes = {n: h for n, _, _, h in new}
    back_of = {n: back.get(n, ()) for n, _, back, _ in new}
    fwd = collections.defaultdict(set)
    for n, st, back, _ in new:
        for p in back.get(n, ()):
            if p in nodes and p != n: fwd[p].add(n)
    sinks = sorted(n for n in nodes if not fwd[n])  # (no stuck spot further on: the chain's end; sorted - seed codes repeat)
    bad = []                                       # [(sink, what it reaches, what reached it)] - empty: every one loops back
    for n in sinks:
        have, flags, keys_got, got = state[n]
        reached = solve(world, placement, [n], list(have.elements()), redirect, dreams, init=(have, flags, keys_got, got), stop=homes[n])[0]
        if not reached & homes[n]: bad.append((n, reached, set(back_of[n])))   # (back into the part that connects to the rest)
    return bad


def locked_landings(world, first):
    """(2026-11-09, user: 'warping into an area with a (inside) a locked door should be avoided') Landing nodes inside an
    area closed by a locked door - a key door, boss / progression block, iron gate, Tree Gem door, crest barrier (room
    research sections: regions joined by everything but lock squares; lock_pairs: two sections one lock parts).  Of two
    such sections the one first reached later in the original layout (solve.rounds of a solve without redirects) is
    the inside (first: solve.order of a solve without redirects); a section never reached: left alone."""
    out = set()
    for k, m in world.maps.items():
        if not m.get('lock_pairs'): continue
        mi = int(k); sec_nodes = collections.defaultdict(set)
        for e in m['entries']:
            for sc in e.get('sections', ()): sec_nodes[sc].add((mi, e['at'] or e['id']))
        for w in m['warps']:
            if not any(e['at'] == w['id'] for e in m['entries']):
                for sc in w.get('sections', ()): sec_nodes[sc].add((mi, w['id']))
        when = {sc: min((first[n] for n in ns if n in first), default=None) for sc, ns in sec_nodes.items()}
        inside = set(); grew = True
        while grew:                                # (a section behind an inside section's lock is inside too)
            grew = False
            for a, b in m['lock_pairs']:
                for x, y in ((a, b), (b, a)):
                    if y in inside or when.get(x) is None or when.get(y) is None: continue
                    if when[y] > when[x] or (x in inside and when[y] >= when[x]): inside.add(y); grew = True
        for sc in inside: out |= sec_nodes[sc]
    return out


def door_pairs(world):
    """([(a, b)], twins): two-way pairs (map, warp id) among the shuffled maps - a door, and the door near its landing
    that leads back to it - and {end: [the same door in the map's story copies]} (Overworld E1 before / after Nirude,
    C4, B1, E2: one door, one destination, in both copies; a copy's own extra doors pair as usual)."""
    ok = {int(k) for k in world.maps if int(k) not in world.left_out}
    base_of = {}
    for b_, vs in world.remaps.items():
        for v, _, _ in vs:
            if v != b_ and v in ok and b_ in ok and (b_ < v or v not in world.remaps): base_of[v] = b_
    def fam(m): return base_of.get(m, m)
    twins, skip = collections.defaultdict(list), set()
    for v, b_ in base_of.items():
        bw = {tuple(x['rect']): x['id'] for x in world.maps[str(b_)]['warps']}
        for x in world.maps[str(v)]['warps']:
            t = bw.get(tuple(x['rect']))
            if t: twins[(b_, t)].append((v, x['id'])); skip.add((v, x['id']))
    def near(rect, x, y, r=2):
        x1, y1, x2, y2 = rect
        return max(x1 - x, x - x2, 0) + max(y1 - y, y - y2, 0) <= r
    pairs, seen = [], set(skip)
    for m in sorted(ok):
        for w in world.maps[str(m)]['warps']:
            a = (m, w['id'])
            if a in seen or w['to_map'] not in ok: continue
            x, y = w['to'][:2]
            back = [v for v in world.maps[str(w['to_map'])]['warps']
                    if fam(v['to_map']) == fam(m) and (w['to_map'], v['id']) not in seen and (w['to_map'], v['id']) != a
                    and near(v['rect'], x, y) and near(w['rect'], *v['to'][:2])]
            if back:
                b = (w['to_map'], back[0]['id']); pairs.append((a, b)); seen |= {a, b}
    rec = {(m, w['id']): w for m in ok for w in world.maps[str(m)]['warps']}
    ends = {e for p in pairs for e in p}
    def rd(p, q): return max(p[0] - q[2], q[0] - p[2], 0) + max(p[1] - q[3], q[1] - p[3], 0)
    for e, w in sorted(rec.items()):               # (a door made of several records: the others go with the first)
        if e in seen or w['to_map'] not in ok: continue
        a = next((a for a in sorted(ends) if a[0] == e[0] and fam(rec[a]['to_map']) == fam(w['to_map'])
                  and rd(rec[a]['rect'], w['rect']) <= 2
                  and abs(rec[a]['to'][0] - w['to'][0]) + abs(rec[a]['to'][1] - w['to'][1]) <= 4), None)
        if a: twins[a].append(e); seen.add(e)
    oneways = sorted(e for e, w in rec.items() if e not in seen and w['to_map'] in ok)
    oneways += sorted((m, sw['id']) for m in ok for sw in world.maps[str(m)]['script_warps']     # (op 53: scripted)
                      if sw['to_map'] in ok and sw['to_map'] != m)
    return pairs, dict(twins), base_of, oneways


def plan(spoiler, seed_text, tries=400, say=lambda t: None):
    """{door end: far end whose landing it takes} for a layout the logic proves, or raises RuntimeError."""
    world = World(load())
    pairs, twins, base_of, oneways = door_pairs(world)
    partner = {a: b for a, b in pairs}; partner.update({b: a for a, b in pairs})
    ends = sorted(partner)
    rec = {(int(k), w['id']): w for k, m in world.maps.items() for w in m['warps'] + m['script_warps']}
    cond = collections.defaultdict(list)           # story copy -> the maps whose reaching turns its base into it
    for b_, vs in world.remaps.items():
        for v, cm, _ in vs:
            if base_of.get(v) == b_: cond[v].append(cm)
    def arrival(e):                                # [(node, map reached first)] coming in through e's far side
        pm, pw = partner[e]; r_ = rec[partner[e]]; tm = r_['to_map']; sq = tuple(r_['to'][:2])
        at = world.entry.get((tm, pm, 'warp ' + pw[1:])) or world.land(tm, sq)
        out = [((tm, at), None)] if at is not None else []
        for v, t in twins.get(e, ()):
            out += [((v, t), cm) for cm in cond[v]]
        return out
    arr = {e: arrival(e) for e in ends}
    def landing(o):                                # [(node, map reached first)] where one-way o drops him
        r_ = rec[o]; tm = r_['to_map']; sq = tuple(r_['to'][:2]); script = o[1].startswith('S:')
        if script and not any(r_['to']): return []           # (op 53 to 0,0,0: a boss room's 'back to the save', no landing)
        how = 'script ' + o[1][2:] if script else 'warp ' + o[1][1:]
        at = world.entry.get((tm, o[0], how)) or world.land(tm, sq)
        out = [((tm, at), None)] if at is not None else []
        for v, cm, _ in ([] if script else world.remaps.get(tm, ())):
            at2 = world.land(v, sq)
            if at2 is not None: out.append(((v, at2), cm))
        return out
    drop = {o: landing(o) for o in oneways}
    # (2026-11-09) class of a door end / drop: what standing at its landing needs (deep water: boots; inside an
    # object's box: its item).  Doors pair and drops take landings only within one class, so a door is never taken
    # from dry land into the river (the user's softlock); the strand check below catches the rest.
    def ncls(nodes):
        nd = world.node_need.get(nodes[0][0]) if nodes else None
        return tuple(sorted(tuple(sorted(a)) for a in nd)) if nd else ()
    cls = {e: ncls(arr[e]) for e in ends}; ocls = {o: ncls(drop[o]) for o in oneways}
    # (a one-sided pair - outside needs X, inside Y: a cave behind a bomb rock, a glove rock, a river landing - is
    #  reached inside only through that door; it swaps with pairs of its own kind, outside to inside, so each inside
    #  stays behind an X door.  A kind of one pair keeps its own partner.)
    kinds = collections.defaultdict(list)
    for a, b in pairs:
        if cls[a] != cls[b]:
            x, y = (a, b) if (cls[a], cls[b]) <= (cls[b], cls[a]) else (b, a)
            kinds[(cls[x], cls[y])].append((x, y))
    # (2026-11-10, user: 'if I can't leave an area that's a real issue') a kind of one pair has nothing to swap with:
    # its two ends pair within their own classes instead (Lake Shrine 351 W11, dry, never into 433's dive shaft)
    kinds = {k: v for k, v in kinds.items() if len(v) > 1}
    locked = {e for k in kinds.values() for p_ in k for e in p_}
    by_cls = collections.defaultdict(list)
    for e in ends:
        if e not in locked: by_cls[cls[e]].append(e)
    def mate(e, pool=None):                        # a random end of e's class (from pool when given)
        if e in locked or e in home: return None
        xs = [f for f in (pool if pool is not None else by_cls[cls[e]]) if cls[f] == cls[e] and f not in locked and f not in home]
        return rng.choice(xs) if xs else None
    def aim_at(o, ls):                             # a landing for drop o: free, wide enough (a drop whose own landing
        if ocls[o]: return o                       #  needs something - Magyscar 5's lava ledge - keeps its own)
        xs = [l for l in ls if can(o, l) and not ocls[l]]
        return rng.choice(xs) if xs else o
    def dims(o):
        if o[1].startswith('S:'): return (1, 1)
        x1, y1, x2, y2 = rec[o]['rect']; return (x2 - x1 + 1, y2 - y1 + 1)
    def can(o, l):                                 # (a wide drop onto a small landing is split per square: 4 at most)
        a_, b_ = dims(o), dims(l); return (a_[0] <= b_[0] and a_[1] <= b_[1]) or a_[0] * a_[1] <= 4
    placement = {k: v for g in spoiler['itemSources'].values() for k, v in g.items()}
    need = [plain(k) for k in spoiler.get('playthrough', {})]
    start = [(START_MAP, w) for w in world.warps(START_MAP)]
    inv = spoiler.get('randomizerSettings', {}).get('startingInventory', [])
    dreams = bool(spoiler.get('gameSettings', {}).get('dreamDungeonMode'))
    solve(world, placement, start, inv, None, dreams)
    known_traps = {n for n, _, _, _ in traps(world, start, None, dreams)}   # (the research's own gaps: in the original layout too)
    known_strand = set(solve.stranded)
    rng = random.Random('alldoors:' + str(seed_text))
    endset = set(ends)
    def swap(to, e, f):                            # e <-> f; their old far ends pair up (every door stays two-way)
        pe, pf = to[e], to[f]
        if f in (e, pe): return
        to[e], to[f] = f, e
        if pe == f: return
        to[pe], to[pf] = pf, pe
    to = None; fall = None                         # fall: one-way -> the one-way whose landing it takes
    home = set(); home_kinds = set(); tried = collections.Counter()   # (doors kept as in the original: strand repair)
    # (a landing inside a locked area is no destination: its door keeps its own partner, a drop onto it keeps its own
    #  landing and no other drop takes it)
    inside = locked_landings(world, solve.order)
    # (2026-11-10, user: a landing right inside a locked gate 'still stops progress, unless a key could do the job') a
    # landing on a gate that only an event opens - iron gate, progression / boss block, switch gate (entries'
    # nudge_need: 'gate:' / 'flag:' tokens only) - is no destination either; a key door's or an item obstacle's is
    # (the key / item opens it, the logic asks for it), moved to the side of the door he came by
    def event_gate(nd):
        return isinstance(nd, list) and bool(nd) and all(
            a_ and all(isinstance(t, str) and t.startswith(('gate:', 'flag:', '@')) for t in a_) for a_ in nd)
    gates = {(int(k), e['at'] or e['id']) for k, m in world.maps.items() for e in m['entries']
             if e.get('nudge') and event_gate(e.get('nudge_need'))}
    inside = inside | gates
    for e in ends:
        if any(nd in inside for nd, _ in arr[e]) and e not in locked: home.update((e, partner[e]))
    for o in oneways:
        if any(nd in inside for nd, _ in drop[o]): ocls[o] = ocls[o] or ('locked area',)
    # (2026-11-10, user: 'putting Alundra on rails he can't walk, also bridge warps ... should remain as they are') a warp
    # landing on mine-cart rails (table 'rails') and a bridge warp - one that hops at most 3 squares within its own map
    # (A4 W16 (11,41) -> (11,38), under a 2-square bridge) - keep their own partner / landing, and no other takes theirs
    def bridge(n):
        r_ = rec[n]
        if n[1].startswith('S:') or r_.get('to_map0', r_['to_map']) != n[0]: return False
        x1, y1, x2, y2 = r_['rect']; tx, ty = r_['to'][:2]
        return max(x1 - tx, tx - x2, 0) + max(y1 - ty, ty - y2, 0) <= 3
    fixed = {n for n in list(partner) + list(oneways) if rec[n].get('rails') or bridge(n)}
    for e in ends:
        if e in fixed:
            if e in locked: home_kinds.add(next(k for k, v in kinds.items() if any(e in p_ for p_ in v)))
            else: home.update((e, partner[e]))
    for o in oneways:
        if o in fixed: ocls[o] = ocls[o] or ('rails / bridge',)
    plan.fixed = (sum(1 for n in fixed if rec[n].get('rails')), sum(1 for n in fixed if bridge(n)))
    for k, v in kinds.items():
        if any(nd in inside for p_ in v for e in p_ for nd, _ in arr[e]): home_kinds.add(k)
    plan.gates = (len(gates), sum(1 for e in ends if any(nd in gates for nd, _ in arr[e])),
                  sum(1 for o in oneways if any(nd in gates for nd, _ in drop[o])))
    plan.locked = (len(inside), len(home), sum(1 for o in oneways if ocls[o] == ('locked area',)))
    accepted = set(); best = [10 ** 9, 0]
    owset = set(oneways)
    for n in range(tries):
        if n % 40 == 0:                            # (a fresh shuffle now and then; in between, repair the last one)
            to = {}; left = []
            for k in sorted(kinds):
                ys = [y for _, y in kinds[k]]
                if k not in home_kinds: rng.shuffle(ys)
                for (x, _), y in zip(kinds[k], ys): to[x] = y; to[y] = x
            for e in sorted(home): to[e] = partner[e]
            for c_ in sorted(by_cls):
                es = [e for e in by_cls[c_] if e not in home]; rng.shuffle(es)
                if len(es) % 2: left.append(es.pop())
                for a, b in zip(es[0::2], es[1::2]): to[a] = b; to[b] = a
            for a, b in zip(left[0::2], left[1::2]): to[a] = b; to[b] = a
            if len(left) % 2: to[left[-1]] = partner[left[-1]] if partner[left[-1]] not in to else left[-1]
            ls_ = [o for o in oneways if drop[o]]; rng.shuffle(ls_); os_ = oneways[:]; rng.shuffle(os_)
            fall = {}; free = ls_[:]
            for o in sorted(os_, key=lambda o: -dims(o)[0] * dims(o)[1]):      # (the widest drops choose first)
                l = o if ocls[o] else next((l for l in free if can(o, l) and not ocls[l]), None)
                if l is None: l = aim_at(o, ls_)
                elif l in free: free.remove(l)
                fall[o] = l
        redirect = {}
        for a, b in to.items():
            if arr[b]:
                for k in [a] + twins.get(a, []): redirect[k] = arr[b]
        for o, l in fall.items(): redirect[o] = drop[l]
        r = solve(world, placement, start, inv, redirect, dreams); par = solve.parent
        nmiss = sum(1 for l in need if l not in r[3])
        def progress(score):                       # (no better score - items missed, then strandings / dead ends - in
            if score < best[0]: best[:] = [score, n]   #  60 tries: this item placement is given up, the build makes a
            elif tries <= 200 and n - best[1] >= 60:   #  new one)
                raise RuntimeError('All Doors: no progress for this placement after %d tries.' % (n + 1))
        if nmiss: progress(nmiss * 10000)
        if nmiss:                                  # (join a reached door / drop to a place the logic never got to)
            if DEBUG: print('try', n, 'missing', [l for l in need if l not in r[3]][:4], flush=True)
            miss = {l for l in need if l not in r[3]}
            spots = {(m, w) for nm, m, pw in world.sources if nm in miss for w in pw}   # (where the missing ones are got)
            mmaps = {m for m, _ in spots}
            def aim(xs, at): return ([x for x in xs if at(x) & spots] or [x for x in xs if {m for m, _ in at(x)} & mmaps] or xs)
            near = sorted(e for e in endset if e in r[0] and e not in locked and e not in home)
            far = aim(sorted(e for e in endset if e not in r[0]), lambda e: {n for n, _ in arr[e]} | {e})
            onear = sorted(o for o in owset if o in r[0])
            ofar = aim(sorted(o for o in owset if not any(nd in r[0] for nd, _ in drop[fall[o]])), lambda o: {n for n, _ in drop[fall[o]]})
            if onear and ofar and (rng.random() < 0.5 or not (near and far)):
                x, y = rng.choice(onear), rng.choice(ofar)
                fx, fy = fall[x], fall[y]
                if ocls[x] or ocls[fy]: pass
                elif can(x, fy) and can(y, fx) and not ocls[y] and not ocls[fx]: fall[x], fall[y] = fy, fx
                elif can(x, fy): fall[x] = fy
            elif near and far:
                x = rng.choice(near); y = mate(x, far)
                if y is not None: swap(to, x, y)
            continue
        # (2026-11-09) a door he can take before he can stand where it lands (deep water without boots, inside a rock's
        # box): stuck on arrival, not even the door behind him - re-pair that door / re-aim that drop
        strand = []
        for n_, src in sorted(solve.stranded.items()):
            if n_ in known_strand: continue
            if src in endset and to[src] == partner[src] and src in home:   # (an original pair a rule keeps - rails, a
                known_strand.add(n_); accepted.add((src, n_)); continue       #  bridge, a locked area: listed)
            strand.append(src)
        if strand: progress(5000 + len(strand))
        if strand:
            if DEBUG: print('try', n, 'stranded', strand[:4], flush=True)
            for c_ in strand:
                if c_ in endset:
                    tried[c_] += 1
                    if c_ in locked:                         # (its inside is not reached through it alone - Lake Shrine
                        k = next(k for k, v in kinds.items() if any(c_ in p_ for p_ in v))   # 351 W11: the pair leaves its
                        p_ = next(p_ for p_ in kinds[k] if c_ in p_); kinds[k].remove(p_)    # kind, its ends pair within
                        for e in p_: locked.discard(e); by_cls[cls[e]].append(e)          # their own classes)
                        if not kinds[k]: del kinds[k]
                    y = mate(c_)                             # (2026-11-10, user: 'if I can't leave an area that's a real
                    if y is not None: swap(to, c_, y)        #  issue' - another partner of its class, never accepted)
                elif c_ in owset: fall[c_] = aim_at(c_, ls_)
            continue
        bad = loops_back(world, placement, start, inv, redirect, dreams, traps(world, start, redirect, dreams), known_traps)
        if bad: progress(len(bad))
        if not bad:
            say('All Doors: layout %d' % (n + 1))
            scripts = {o: (rec[o]['to_map0'],) + tuple(rec[o]['to'][:3]) for o in oneways if o[1].startswith('S:')}
            return {'to': to, 'partner': partner, 'twins': twins, 'fall': fall, 'scripts': scripts, 'tries': n + 1,
                    'kept': sorted(e for e in ends if to[e] == partner[e]), 'stranding_kept': sorted(accepted)}
        if DEBUG: print('try', n, 'loop fail', len(bad), [(world.maps[str(b[0][0])]['name'][:24], b[0][1]) for b in bad[:4]], flush=True)
        if DEBUG:
            for sink, reached, came in bad:
                print('   sink', sink, 'parent', par.get(sink), (par.get(sink) in redirect, redirect.get(par.get(sink)), world.links.get(par.get(sink)) and [t for t, _ in world.links[par.get(sink)]][:5]), 'came', sorted(came)[:6], 'fixed?', [(c, ocls.get(c), c in home, c in locked) for c in sorted(came)[:6]], flush=True)
        for sink, reached, came in bad:             # (each dead end: re-pair a door of it or of the way in, or re-aim a drop)
            cand = sorted(e for e in (reached | came | {sink}) if e in endset and e not in locked and e not in home)
            ocand = sorted(o for o in (reached | came | {sink}) if o in owset)
            if ocand and (not cand or rng.random() < 0.5):      # (a drop onto a dead end gets another landing)
                c_ = rng.choice(ocand); fall[c_] = aim_at(c_, ls_)
            elif cand:
                x = rng.choice(cand); y = mate(x)
                if y is not None: swap(to, x, y)
    raise RuntimeError('All Doors: no door layout the logic could prove in %d tries.' % tries)


def apply(files, layout, warp_record, split_portal, size, retarget=None):
    """Door a takes b's landing: a's record gets the destination fields of b's partner's record (where coming
    through b's far side lands), and a wider door than that landing's own is split (build_seed.split_portal)."""
    # (2026-11-09) a landing on an object's squares (a bomb rock / glove rock / gate over the doorway) moves to the free
    # square beside it that the room research picked (entries' 'nudge'): he is never set down inside an object's box
    nudges = {}
    for k, m in load()['maps'].items():
        for e in m['entries']:
            if e.get('nudge'): (x0, y0), (x1, y1) = e['nudge']; nudges[(int(k), x0, y0)] = (x1 - x0, y1 - y0)
    def moved(mp, x, y):
        dx, dy = nudges.get((mp, x, y), (0, 0)); return x + dx, y + dy
    # (2026-11-10, user: 'warping into a bombable blocked entrance blocks entry to that area'; a landing 'right inside
    # a locked gate') a landing inside an object - a Bombable Rock on the doorway (B2 6, D2 14, Coal Mine 61/64/67,
    # Reptile Lair 80, Murgg Woods 382), a glove rock, thorns, a key door, a gate or block - moves to the free square on
    # the side of its door even for a warp kept in its original pair: with the object still there he would be set down
    # inside it.  Other kept records (rails, bridges, water landings) stay as they are.
    bombs = set()
    for k, m in load()['maps'].items():
        for e in m['entries']:
            nd = e.get('nudge_need')
            if e.get('nudge') and isinstance(nd, list) and nd != [[]]: bombs.add((int(k),) + tuple(e['nudge'][0]))
    def unseal(w):
        if (w['map'], w['x'], w['y']) in bombs: w['x'], w['y'] = moved(w['map'], w['x'], w['y'])
    old = {}
    for e in layout['partner']:
        w = warp_record(files, e[0], int(e[1][1:]))
        old[e] = (dict(w), size(w))
    later = []
    for a, b in layout['to'].items():
        if layout['partner'][a] == b:                      # (an original pair - kept: its records stay as they are,
            for m, wid in [a] + layout.get('twins', {}).get(a, []):   #  but never inside a bomb rock)
                unseal(warp_record(files, m, int(wid[1:])))
            continue
        src, src_size = old[layout['partner'][b]]          # (the record that leads onto b)
        for m, wid in [a] + layout.get('twins', {}).get(a, []):    # (and the same door in the map's story copy)
            w = warp_record(files, m, int(wid[1:]))
            nx, ny = moved(src['map'], src['x'], src['y'])
            w.update(map=src['map'], x=nx, y=ny, z=src['z'], arrive_facing=src['arrive_facing'])
            later.append((m, w, src_size))
    sc = layout.get('scripts', {})
    def spot(l):                                       # (map, x, y, z, facing or None), size of what lands there
        if l in sc: return sc[l] + (None,), (1, 1)
        w0 = warp_record(files, l[0], int(l[1][1:]))
        return (w0['map'], w0['x'], w0['y'], w0['z'], w0['arrive_facing']), size(w0)
    spots = {l: spot(l) for l in set(layout.get('fall', {}).values())}   # (all read before any change)
    for o, l in sorted(layout.get('fall', {}).items()):  # (a one-way / scripted warp takes another one's landing)
        if o == l:                                         # (its own landing: unchanged - out of a bomb rock)
            if o not in sc: unseal(warp_record(files, o[0], int(o[1][1:])))
            continue
        (mp, x, y, z, face), fits = spots[l]
        x, y = moved(mp, x, y)
        if o in sc:
            retarget(files, o[0], o[1][2:].rsplit(':', 1)[0], int(o[1].rsplit(':', 1)[1]), sc[o], (mp, x, y, z))
            continue
        w = warp_record(files, o[0], int(o[1][1:]))
        w.update(map=mp, x=x, y=y, z=z)
        if face is not None: w['arrive_facing'] = face
        later.append((o[0], w, fits))
    for m, w, fits in later: split_portal(files, m, w, fits)
