"""The RANDOMIZER page: a seed made from the exported game by _internal/randomizer (build_seed.py) into
seeds/<hash sentence>/assets (the changed files; everything else is a junction or link to assets/), and
what the randomizer's injected code does, as hooks for the engine.  Nothing here runs unless a seed is active.
Worker:  seedgen.py --worker <options.json>"""
import json, os, shutil, struct, subprocess, sys, threading, time, traceback
from pathlib import Path
from home import HOME, CODE

SEEDS = HOME / 'seeds'
TOOL = CODE.parent / 'randomizer' if (CODE.parent / 'randomizer').is_dir() else HOME / '_internal' / 'randomizer'
OPTIONS = SEEDS / 'options.json'
CURRENT = SEEDS / 'current.txt'
PROGRESS = SEEDS / 'progress.txt'
STOCK = HOME / 'assets'
NO_WINDOW = 0x08000000

active = None                                   # the running seed's seed.json, or None
root = None                                     # its folder
bridge = None                                   # ARCHIPELAGO: the running connector (apbridge.py)
cc = None                                       # CROWD CONTROL: the running CC script (ccbridge.py)


BROKEN_PRESETS = {'archB', 'archC', 'archD'}     # (the randomizer stops on them: more fixed Gilded Falcons than the pool, no solution)
USER_PRESETS = SEEDS / 'presets'                 # the player's own: <name>.json (a randomizer preset) + <name>.menu (every menu setting)


def preset_names():
    shipped = sorted((p.stem for p in (TOOL / 'presets').glob('*.json') if p.stem not in BROKEN_PRESETS), key=lambda s: (s != 'default', s.lower()))
    own = sorted((p.stem for p in USER_PRESETS.glob('*.json') if (USER_PRESETS / f'{p.stem}.menu').exists()), key=str.lower) if USER_PRESETS.is_dir() else []
    return shipped + [n for n in own if n not in shipped]


def is_user_preset(name): return name != 'default' and (USER_PRESETS / f'{name}.menu').exists()   # (Default is never deleted or saved over)


PRESETS = preset_names()

def _counts(*values): return ('Preset',) + tuple(str(v) for v in values), (None,) + values
SMALL = tuple(range(11)); BIG = SMALL + tuple(range(15, 101, 5)); HUGE = BIG + tuple(range(110, 201, 10))
# the preset's own value unless set: (pool item, label, counts); the upgrades count a slot's tiers, first to last
POOL = (('Life Vessel', 'Life Vessels', BIG), ('Magic Seed', 'Magic Seeds', SMALL + (15, 20)), ('Gilded Falcon', 'Gilded Falcons', HUGE),
        ('Herbs', 'Herbs', BIG), ('Strength Tonic', 'Strength Tonics', BIG), ('Strength Elixyr', 'Strength Elixyrs', BIG),
        ('Magic Elixyr', 'Magic Elixyrs', BIG), ('Wonder Essence', 'Wonder Essences', BIG))
UPGRADES = (('sword', 'Sword upgrades', ('Sword', 'Fiend Blade', 'Holy Sword', 'Legend Sword')), ('flail', 'Flail upgrades', ('Iron Flail', 'Steel Flail')),
            ('bow', 'Bow upgrades', ("Hunter's Bow", 'Willow Bow')), ('armor', 'Armor upgrades', ('Leather Armor', 'Ancient Armor', 'Silver Armor')),
            ('earth', 'Earth magic upgrades', ('Earth Scroll', 'Earth Book')), ('water', 'Water magic upgrades', ('Water Scroll', 'Water Book')),
            ('fire', 'Fire magic upgrades', ('Fire Scroll', 'Fire Book')), ('wind', 'Wind magic upgrades', ('Wind Scroll', 'Wind Book')))
BOOTS = ('Long Boots', 'Merman Boots', 'Charm Boots')
ARMORS = ('Leather Armor', 'Ancient Armor', 'Silver Armor')

# tab, label, flag, values shown, values passed (None: the shown ones in lower case); 'start-', 'pool:', 'up:' and
# 'item:' rows (and 'progressive') edit the preset (build_seed.run_logic), 'action:' rows are buttons (the menu's),
# the rest are the randomizer's options
def _tabs(): return (
    ('Preset', (
        ('Mode', 'mode', ('Classic(Dreams Off)', 'Nightmare(Dreams On)'), ('classic', 'nightmare')),
        ('Early Lake Shrine', 'lake-shrine', ('No', 'Yes'), ('N', 'Y')),
        ('Random Door & Warps', 'doors', ('Off', 'On'), ('N', 'Y')),
        ('Preset', 'preset', tuple('Default' if p == 'default' else p for p in PRESETS), tuple(PRESETS)),
        ('Load preset', 'action:load', ('',), None),
        ('Save preset', 'action:save', ('',), None),
        ('Delete preset', 'action:delete', ('',), None),
        ('Starting HP', 'start-hp', *_counts(*range(1, 51))),
        ('Starting MP', 'start-mp', *_counts(*range(0, 5))),
        ('Starting Gilder', 'start-gold', *_counts(*range(0, 1001, 50))),
        ('Weapon Start', 'start-weapon', ('Sword', 'Sword Flail or Bow', 'Random'), ('Dagger', 'sfb', 'random')),
        ('No sword start', 'no-sword', ('No', 'Yes'), ('N', 'Y')),
        ('Weapon Balance', 'weapon-balance', ('Original', 'Adjusted'), ('original', 'adjusted')),
        ('View weapon damage', 'action:damage', ('',), None),
        ('Armor in item pool', 'remove-armor', ('Yes', 'No'), ('N', 'Y')),
        ('Armor strength', 'armor-strength', ('Full', 'Half', 'Quarter'), None),
        ('Show area checks', 'area-checks', ('Yes', 'No'), ('Y', 'N')),
        ('Reset to default', 'action:reset', ('',), None),
    )),
    ('Enemies', (
        ('Balance', 'seed-balance', ('JP', 'US & EU'), ('jp', 'us')),
        ('Random Enemies', 'enemies', ('Off', 'Shuffle', 'Random', 'Switch'), ('off', 'shuffle', 'switch', 'swap')),
        ('Random stats', 'random-stats', ('Enemies', 'Enemies & Bosses', 'Off'), ('enemies', 'both', 'off')),
        ('Stat changes', 'stat-changes', ('Mixed', 'Buffs'), None),
        ('Stat chance', 'stat-chance', tuple(f'{v}%' for v in range(0, 101, 10)), tuple(str(v) for v in range(0, 101, 10))),
        ('Stat types', 'stat-types', ('HP, ATK, SPD', 'HP, ATK', 'HP', 'ATK', 'SPD', 'None'), ('hp,atk,spd', 'hp,atk', 'hp', 'atk', 'spd', 'none')),
        ('Stat colors', 'stat-colors', ('No Change', 'Changed', 'Random'), ('no-change', 'changed', 'random')),
        ('Late Game Boss Resistance', 'boss-resist', ('Original', 'Adjusted'), ('original', 'adjusted')),
    )),
    ('Item', (
        ('Progressive items', 'progressive', ('Yes', 'No'), ('Y', 'N')),
        ('Life Vessels heal', 'vessel-heal', ('Yes', 'No'), ('Y', 'N')),
        ('Healing drops', 'healing-drops', ('Yes', 'No'), ('Y', 'N')),
        ('Magic drops', 'magic-drops', ('Yes', 'No'), ('Y', 'N')),
        ('Money drops', 'money-drops', ('Yes', 'No'), ('Y', 'N')),
        ('Shop prices', 'prices', ('Default', "Dinopony's Costs"), ('default', 'dinopony')),
        ('Shop Restock', 'shop-items', ('Consumables Only', 'All', 'None'), ('consume', 'all', 'once')),
        ('Edit item costs', 'action:costs', ('',), None),
        ('Edit item counts', 'action:counts', ('',), None),
    )),
    ('Dreams', (
        ('Dream priority', 'dream-priority', ('Low', 'Default', 'High'), None),
        ('Remove cutscenes', 'dream-cutscenes', ('No', 'Yes'), ('N', 'Y')),
        ("Olen's dream", 'olen-dream', ('Yes', 'No'), ('Y', 'N')),
        ("Twins' puzzles", 'twin-puzzles', ('Original', 'Random'), None),
    )),
    ('Seeds', (
        ('Load seed', 'action:seeds', ('',), None),
        ('Share seed', 'action:share', ('',), None),
        ('Enter seed code', 'action:code', ('',), None),
        ('Use built in tracker', 'builtin-tracker', ('Yes', 'No'), None),
        ('Connect tracker', 'action:tracker', ('',), None),
        ('Open tracker', 'action:open-tracker', ('',), None),
        ('Auto boot tracker & json', 'tracker', ('On', 'Off'), None),
        ('Crowd Control', 'crowd-control', ('Off', 'On'), None),
        ('Twitch channel', 'action:cc-channel', ('',), None),
        ('Use border', 'cc-border', ('No', 'Yes'), None),
        ('Points Display', 'cc-points', ('Off', 'On'), None),
        ('Buffed spawns', 'cc-buffed', ('Off', 'On'), None),
    )),
)
TABS = _tabs()
# Item > Edit item counts' page: consumables, gear, then progression
_POOL = {item: (label, n) for item, label, n in POOL}
COUNT_ROWS = (
    *((_POOL[i][0], f'pool:{i}', *_counts(*_POOL[i][1])) for i in ('Herbs', 'Strength Tonic', 'Strength Elixyr', 'Magic Elixyr', 'Wonder Essence')),
    *((label, f'up:{k}', *_counts(*range(len(tiers) + 1))) for k, label, tiers in UPGRADES),
    *((name, f'item:{name}', *_counts(0, 1)) for _, _, tiers in UPGRADES for name in tiers),
    *((name, f'item:{name}', *_counts(0, 1)) for name in BOOTS),
    *((_POOL[i][0], f'pool:{i}', *_counts(*_POOL[i][1])) for i in ('Life Vessel', 'Magic Seed', 'Gilded Falcon')))
def all_tabs(): return TABS + (('Item counts', COUNT_ROWS),)
DEFAULTS = {'remove-armor': 0, 'armor-strength': 0, 'enemies': 0, 'random-stats': 2, 'stat-changes': 1, 'stat-types': 0,
            'stat-colors': 0, 'mode': 0, 'dream-priority': 1, 'dream-cutscenes': 1, 'olen-dream': 1, 'preset': 0, 'progressive': 0, 'start-mp': 2, 'stat-chance': 3, 'builtin-tracker': 1}   # (Randomizer/randomizer_ui.ini)


ABOUT = {'lake-shrine': 'Bridge up, in logic with its gear.', 'doors': 'Shuffles dungeon doors and boss warps.', 'mode': 'Whether nightmares hold shuffled items.', 'dream-priority': 'Share of key items in dream chests.',
         'dream-cutscenes': 'Removes the scenes inside nightmares.', 'olen-dream': "Includes Olen's nightmare in the seed.",
         'preset': 'The base settings for the seed.', 'progressive': 'Gear is found in tier order.', 'remove-armor': 'Armor can be found, or Herbs instead.',
         'armor-strength': 'How much armor reduces damage.', 'enemies': 'How enemies are randomized.',
         'random-stats': 'Who gets changed stats.', 'stat-changes': 'Mixed can weaken; Buffs only boost.',
         'stat-types': 'Which stats can change.', 'stat-chance': 'The odds of a stat change.', 'stat-colors': 'The tint of buffed enemies.',
         'seed-balance': "Enemy and boss values for this seed."}
ABOUT.update({'start-hp': 'HP at the start.', 'start-mp': 'MP at the start.', 'start-gold': 'Gilder at the start.',
              'action:load': 'Puts back the preset and its settings.', 'action:save': 'Saves every setting as a preset.',
              'action:delete': 'Deletes this saved preset.', 'action:reset': 'Every setting back to its default.',
              'vessel-heal': 'No: a vessel adds health, heals none.',
              'healing-drops': 'No: nothing dropped heals.', 'magic-drops': 'No: no magic is dropped.',
              'money-drops': 'No: no money is dropped; shops in logic.', 'prices': "The prices items have in shops.",
              'action:costs': 'Sets the shop price of each item.', 'action:seeds': 'Plays a past seed, with its own saves.', 'action:share': "Copies the current seed's code to share.", 'action:code': 'Makes the seed from a shared code.', 'action:tracker': 'Links a tracker (its exe or script).', 'action:open-tracker': 'Starts the linked tracker.', 'action:counts': "Sets each item's count in the pool.", 'action:damage': 'Damage per hit with this balance.', 'action:cc-channel': 'The Twitch channel whose chat is read.'})
for _f in (r[1] for _, rows in all_tabs() for r in rows):
    if _f.startswith('pool:'): ABOUT[_f] = 'How many are in the item pool.'
    elif _f.startswith('up:'): ABOUT[_f] = 'How many upgrades are in the pool.'
    elif _f.startswith('item:'): ABOUT[_f] = 'Whether it is in the item pool.'
GENERATE_ABOUT = 'Makes the seed.'
# The line below the rows for the value shown (the row's ABOUT when it has none here)
VALUE_ABOUT = {
    'mode': ('No nightmares, the classic randomizer.', 'Nightmares are active full randomizer.'),
    'lake-shrine': ('Lake Shrine opens as in the game.', 'Bridge up, in logic with its gear.'),
    'enemies': ('Enemies as in the game.', 'Every enemy trades places with another.', 'Each enemy becomes a random enemy.',
                'Enemy types switch places.'),
    'random-stats': ('Enemies get changed stats.', 'Enemies and bosses get changed stats.', 'Stats as in the game.'),
    'stat-changes': ('Stats may go up or down.', 'Stats only go up.'),
    'stat-colors': ('Buffed enemies keep their colors.', 'Buffed enemies are tinted.', 'Buffed enemies get random tints.'),
    'progressive': ('Gear is found in tier order.', 'Each gear item is found as itself.'),
    'vessel-heal': ('A Life Vessel fills your health.', 'A Life Vessel adds health, heals none.'),
    'no-sword': ('The Dagger can still be the start weapon.', 'The start weapon is never the Dagger.'),
    'area-checks': ('The HUD shows the locations checks.', 'No area check count on the HUD.'),
    'tracker': ('A seed opens the tracker with its file.', 'The game does not open the tracker.'),
    'builtin-tracker': ("Uses the game's own tracker.", 'Uses the tracker you connect.'),
    'healing-drops': ('Enemies and pots drop healing.', 'No healing drops.'),
    'magic-drops': ('Enemies and pots drop magic.', 'No magic drops.'),
    'money-drops': ('Enemies and pots drop money.', 'No money drops.'),
    'prices': ('The Default prices.', "The original randomizer's prices."),
    'boss-resist': ('Bosses their default resistance.', 'Bosses take more damage to weapons.'),
    'seed-balance': ("The Japanese release's enemy values.", 'The US and European enemy values.'),
    'weapon-balance': ('Weapons hit as in the game.', 'Nerf Wands, Buff Steel, Holy Charge 32.'),
    'start-weapon': ('You start with the Dagger.', 'A Dagger, Iron Flail or Hunter\'s Bow.', 'Starts with a random weapon type.'),
    'shop-items': ('Only consumable items restock.', 'Every shop item can be bought again.', 'Each shop item can be bought once.'),
    'remove-armor': ('Armor can be found.', 'Herbs instead of armor.'),
    'armor-strength': ('Armor blocks as in the game.', 'Armor blocks half as much.', 'Armor blocks a quarter.'),
    'dream-priority': ('Few key items in dream chests.', 'Some key items in dream chests.', 'Many key items in dream chests.'),
    'dream-cutscenes': ('Scenes in nightmares kept.', 'Scenes in nightmares removed.'),
    'olen-dream': ("Olen's nightmare is in the seed.", "Olen's nightmare is left out."),
    'doors': ('Doors and warps are unchanged.', 'Doors lead to random areas.'),
    'twin-puzzles': ("The twins' puzzles keep their answers.", "New answers, in the other twin's room."),
    'crowd-control': ('Chat commands do nothing.', 'Chat bot commands act in game.'),
    'cc-border': ('Bottom text is outlined.', 'Most text is displayed in a text box.'),
    'cc-points': ('No points window.', 'Opens the points window with the game.'),
    'cc-buffed': ('Chat spawns only normal enemies.', 'Buffed enemies cost double.'),
}


def about(flag, o):
    """The line for a row: its value's (VALUE_ABOUT), else the row's."""
    v = VALUE_ABOUT.get(flag)
    return v[o.get(flag, 0) % len(v)] if v else ABOUT[flag]
EDITS = ('progressive', 'start-', 'pool:', 'up:', 'item:')
PORT_ONLY = ('builtin-tracker', 'seed-balance', 'twin-puzzles', 'no-sword', 'tracker', 'area-checks', 'vessel-heal', 'healing-drops', 'magic-drops', 'money-drops', 'prices', 'shop-items', 'boss-resist', 'weapon-balance', 'stat-chance', 'crowd-control', 'cc-border', 'cc-points', 'cc-buffed')   # the remake's own (seed.json / build_seed)


def vessel_heals():
    """Life Vessels heal unless the running seed says not (Items > Life Vessels heal: No)."""
    return active is None or active.get('vessel_heal', True)


# Item > Shop Restock (seed.json 'shop', build_seed.shop_slots): a slot that sells out is remembered in game flag
# SHOP_FLAG + its number (0x7E0-0x7EF: no script, no part of the game uses them) and comes back deactivated, as
# the game deactivates Naomi's Life Vessel (op 5D) once bought.
SHOP_FLAG = 0x7E0
RESTOCKS = {i for i, x in enumerate(json.loads((TOOL / 'item.json').read_text(encoding='utf-8')))
            if x['name'] in ('Herbs', 'Strength Tonic', 'Strength Elixyr', 'Magic Elixyr', 'Wonder Essence')}   # (Consumables Only)


def shop_given(g, st, item):
    """Event op 82 in a shop slot's script (matched by the instruction's place): Consumables Only sells out a
    repeatable slot that sold anything but Herbs, Tonics, Elixyrs and Wonder Essences; One time items every one."""
    shop = active and active.get('shop')
    if not shop: return
    for i, s in enumerate(shop['slots']):
        if s['map'] != g.map.id or s['give'] != st.ci: continue
        if shop['mode'] == 'all':
            if s.get('restock'): g.set_flag(SHOP_FLAG + i, True)     # (only remembered: the other shop maps' own flag)
            return
        if s['repeatable'] and (shop['mode'] == 'once' or (shop['mode'] == 'consume' and item not in RESTOCKS)):
            g.set_flag(SHOP_FLAG + i, True)
            for e in g.slots:
                if e is not None and getattr(e, 'ref_id', None) == s['entity']: e.estatus = 3; e.status = 'deactivated'
        return


def shop_map(g, m):
    """A shop's map coming in: Can repurchase all puts a one-time slot's item back (its own sold flag cleared:
    Naomi's slot 4; Lurvy's slot 5 keeps its flags, which bring its two replacement slots)."""
    shop = active and active.get('shop')
    if not shop or shop['mode'] != 'all': return
    for i, s in enumerate(shop['slots']):
        if not s.get('restock'): continue
        if s['map'] == m: g.set_flag(s['restock'], False)
        elif m in s.get('restock_maps', ()): g.set_flag(s['restock'], g.flag(SHOP_FLAG + i))   # (the shop's later maps: as bought)


def on_spawn(g, a):
    """A map entity taking its slot: a sold-out shop slot's item comes back deactivated."""
    shop = active and active.get('shop')
    if not shop or shop['mode'] == 'all' or getattr(a, 'record', None) is None: return
    for i, s in enumerate(shop['slots']):
        if s['map'] == g.map.id and s['entity'] == a.ref_id and g.flag(SHOP_FLAG + i):
            a.estatus = 3; a.status = 'deactivated'


def merrick_record(g, rec):
    """Merrick's table (map 134, entity 17) stands for his 15 / 25 / 35 / 45 falcon trades: it shows the item of the
    first of them not yet made (their flags 0x599 / 0x59B / 0x59D / 0x59F), as the game shows its Life Vessel."""
    t = active and active.get('merrick_table')
    if not t or g.map.id != 134 or rec.get('index') != 17: return
    for flag, catalogue in t:
        if not g.flag(flag):
            rec['catalogue'] = catalogue; return


starting = False                                 # (gamestart.py: the new game's own items going in)

# Enemies > Late Game Boss Resistance (combat.Combat.seed_adjust): Melzas, Ronan, Melzas's Brain, the Dark Dragon and
# Zorgia (their sprites' balance chains)
LATE_BOSSES = (418, 446, 463, 479, 509)


def boss_hit(combat, target, n):
    """Adjusted: Alundra's own swing with the Legend Sword (item 8) does 3/4 of its damage to a late boss."""
    if not (active and active.get('boss_resist')) or getattr(target, 'balance_index', None) not in LATE_BOSSES: return n
    p = getattr(combat, 'player', None)
    if p is None or target.touching is not p: return n
    from alundra_remake import Actor
    from engine import menu
    g = Actor.game
    return n * 3 // 4 if g is not None and menu.equipped_kind(g) == 8 else n


# Preset > Weapon Balance: the Fire Wand's (11, 12) and Ice Wand's (14, 15) shots' balance chains
WAND_SHOTS = (11, 12, 14, 15)
WAND_CHARGED = (12, 15)


def weapon_power(combat, target, p):
    """Adjusted: Alundra's own Steel Flail swing (item 10, animations 64 / 66) gets the Fiend Blade's power (+2), his
    charged Holy Sword swing (item 4, animation 24) 32 before the ring (+16)."""
    if not (active and active.get('weapon_balance')): return p
    pl = getattr(combat, 'player', None)
    if pl is None or target.touching is not pl: return p
    from alundra_remake import Actor
    from engine import menu
    g = Actor.game
    kind = menu.equipped_kind(g) if g is not None else None
    anim = getattr(combat, 'anim_b0', pl.target_anim)
    return p + 2 if kind == 10 and anim in (64, 66) else p + 16 if kind == 4 and anim == 24 else p


def weapon_hit(target, n):
    """Adjusted: a wand shot does half its damage, a charged one (chains 12, 15) a third (6 -> 4, user 2026-11-08)."""
    i = getattr(target.touching, 'balance_index', None)
    if not (active and active.get('weapon_balance')) or i not in WAND_SHOTS: return n
    return n // 3 if i in WAND_CHARGED else n // 2


# Preset > View weapon damage: the attacks Adjusted changes (name, weapon item, Alundra's animation, shot chain)
WEAPON_VIEW = (('Steel Flail', 10, 64, None), ('Holy Sword charged', 4, 24, None), ('Fire Wand', 16, 17, 11),
               ('Fire Wand charged', 16, 17, 12), ('Ice Wand', 14, 17, 14), ('Ice Wand charged', 14, 17, 15))


def weapon_view(combat):
    """Per attack, damage per hit at 16/16 in the balance in use (Cloth Armor): (name, Original, Adjusted, and the
    same with Olga's Ring)."""
    out = []
    for name, item, anim, chain in WEAPON_VIEW:
        rec = combat.record(0 if chain is None else chain)
        atk = combat.attack_for(rec, anim) if chain is None else next((a for a in rec['attacks'] if a[0]), [0, 0])
        vals = []
        for ring in (None, 51):
            p = atk[1] + (combat.equip_power(item, ring, 17, anim) if atk[0] & 0x80 else 0)
            vals += [p, max(1, p // (3 if chain in WAND_CHARGED else 2)) if chain is not None else p + (2 if item == 10 else 16)]
        out.append((name, *vals))
    return out



# Preset > View weapon damage: every weapon Alundra swings or shoots (name, weapon item)
WEAPONS = (('Dagger', 1), ('Sword', 2), ('Fiend Blade', 3), ('Holy Sword', 4), ('Legend Sword', 8), ('Iron Flail', 9),
           ('Steel Flail', 10), ("Hunter's Bow", 5), ('Willow Bow', 6), ('Fire Wand', 16), ('Ice Wand', 14))


def weapon_damage(combat, adjusted):
    """Per weapon, damage per hit at 16/16 (Cloth Armor, no ring) with Weapon Balance Original or Adjusted:
    (name, normal, charged or None)."""
    import combat as C
    def hit(item, anim, chain):
        rec = combat.record(0 if chain is None else chain)
        atk = combat.attack_for(rec, anim) if chain is None else next((a for a in rec['attacks'] if a[0]), [0, 0])
        p = atk[1] + (combat.equip_power(item, None, 17, anim) if atk[0] & 0x80 else 0)
        if not adjusted: return p
        if chain is not None: return max(1, p // 2) if chain in WAND_SHOTS else p
        return p + 2 if item == 10 and anim in (64, 66) else p + 16 if item == 4 and anim == 24 else p
    out = []
    for name, item in WEAPONS:
        w = C.WEAPON_INIT[C.WEAPON_BY_ITEM[item]]
        shot = w[2] != 0
        out.append((name, hit(item, w[1], w[2] if shot else None),
                    hit(item, w[9], w[10] if shot else None) if w[0] else None))
    return out

def boss_responses(resp):
    """Adjusted, from a balance's own responses: the weapon hits a late boss resists (1/16) take 6/16, the wands'
    (types 6 Fire, 7 Ice) 5/16; its weakness (2-5/16: Melzas's Fire Wand, 5) 8/16; each magic (8-11) it is immune to
    takes its lowest other magic response.  Original: as given."""
    if not (active and active.get('boss_resist')): return list(resp)
    r = list(resp)
    for i in range(7):
        if r[i] == 1: r[i] = 5 if i in (5, 6) else 6
        elif 2 <= r[i] <= 5: r[i] = 8
    magic = [v for v in r[7:] if not v & 0xC0]
    for i in range(7, 11):
        if r[i] & 0xC0 == 0x80: r[i] = min(magic) if magic else 16
    return r


def start_weapon_group():
    """The weapon group a new game equips: swords (1), or a seed's Weapon Start weapon's (seed.json 'weapon_group')."""
    return (active or {}).get('weapon_group', 1)


def drops(kind):
    """Dropped items of a kind ('healing', 'magic', 'money': engine/drops.DROP_KINDS) unless the running seed says not."""
    return active is None or active.get('drops', {}).get(kind, True)


# Items > Shop prices: Default (the Archipelago randomizer's itemGilderValues, Alundra Arch's presets/default.json) or
# Dinopony's Costs (the items' own values, the original randomizer's)
ARCH_PRICES = {'Life Vessel': 250, 'Magic Seed': 500, 'Ruby Crest': 300, 'Sapphire Crest': 350, 'Topaz Crest': 400,
               'Agate Crest': 450, 'Garnet Crest': 500, 'Emerald Crest': 550, 'Diamond Crest': 600, 'Charm Boots': 150,
               'Sluice Key': 25, 'Gilded Falcon': 50, 'Sword upgrade': 200, 'Bow upgrade': 150, 'Flail upgrade': 100,
               'Sword': 150, 'Fiend Blade': 300, 'Holy Sword': 500, 'Legend Sword': 800, "Hunter's Bow": 100, 'Willow Bow': 200,
               'Iron Flail': 100, 'Steel Flail': 200,   # (the weapons: the user's prices)
               'Armor upgrade': 150, 'Boots upgrade': 150, 'Earth Magic upgrade': 200, 'Water Magic upgrade': 200,
               'Fire Magic upgrade': 200, 'Wind Magic upgrade': 200}
_ITEMS = json.loads((TOOL / 'item.json').read_text(encoding='utf-8'))
OWN_PRICES = {x['name']: x['goldValue'] for x in _ITEMS if x.get('goldValue')}
COST_ITEMS = tuple(OWN_PRICES) + tuple(n for n in ARCH_PRICES if n not in OWN_PRICES)
PRICE_STEPS = (0, 5, 10, 15, 20, 25, 30, 40, 50) + tuple(range(75, 1001, 25)) + tuple(range(1100, 3001, 100))
# Edit item costs (the menu's page): an item's price in shops, the Shop prices row's unless set
COST_ROWS = tuple((n, f'cost:{n}', *_counts(*PRICE_STEPS)) for n in COST_ITEMS)
ABOUT.update({r[1]: 'Its price in shops.' for r in COST_ROWS})


def base_price(o, name):
    """An item's shop price before the Edit item costs page: Default's (ARCH_PRICES) or its own (Dinopony's Costs)."""
    own = OWN_PRICES.get(name, 0)
    return ARCH_PRICES.get(name, own) if o.get('prices', 0) % 2 == 0 else own


def prices(o):
    """Every price that is not the item's own (itemGilderValues for the randomizer): Shop prices, then the page."""
    out = {}; steps = (None,) + PRICE_STEPS
    for n in COST_ITEMS:
        v = steps[o.get(f'cost:{n}', 0) % len(steps)]
        p = base_price(o, n) if v is None else v
        if p != OWN_PRICES.get(n): out[n] = p
    return out


def load_options():
    o = dict(DEFAULTS)
    try: o.update(json.loads(OPTIONS.read_text()))
    except (OSError, ValueError): pass
    o.pop('appatch', None)
    return o


def save_options(o):
    SEEDS.mkdir(exist_ok=True); OPTIONS.write_text(json.dumps(o))


def shown(flag, o):
    """A row that needs another row's choice is there only with that choice (as Options' Load Delay)."""
    if flag in ('stat-changes', 'stat-chance', 'stat-types'): return o.get('random-stats', 0) != 2
    if flag == 'armor-strength': return o.get('remove-armor', 0) == 0
    if flag in ('olen-dream', 'twin-puzzles'): return o.get('mode', 0) == 1
    if flag == 'no-sword': return o.get('start-weapon', 0) % 3 != 0
    if flag == 'action:tracker': return o.get('builtin-tracker', 1) == 1
    if flag in ('action:cc-channel', 'cc-border', 'cc-points', 'cc-buffed'): return o.get('crowd-control', 0) % 2 == 1
    if flag == 'tracker': return __import__('tracker_link').chosen(o) is not None   # (once a tracker is linked)
    if flag == 'action:open-tracker': return __import__('tracker_link').exe_path(o) is not None
    if flag == 'action:delete': return is_user_preset(current_preset(o))
    armor = o.get('remove-armor', 0) == 0
    if flag.startswith('up:'): return o.get('progressive', 0) == 0 and (flag != 'up:armor' or armor)
    if flag.startswith('item:') and flag[5:] not in BOOTS: return o.get('progressive', 0) == 1 and (flag[5:] not in ARMORS or armor)
    return True


def preset_edit(o):
    """The rows that edit the preset, as build_seed.run_logic takes them: settings and item pool counts (None: the
    preset's).  Only the rows shown count (upgrades with progressive items, single items without)."""
    e = {'progressiveItems': o.get('progressive', 0) == 0, 'pool': {}, 'moneyDrops': o.get('money-drops', 0) % 2 == 0,
         'itemGilderValues': prices(o)}
    for _, rows in all_tabs():
        for _, flag, shown_, passed in rows:
            if not flag.startswith(EDITS[1:]) or not shown(flag, o): continue
            v = passed[o.get(flag, 0) % len(shown_)]
            if v is None: continue
            if flag == 'start-weapon':
                if v != 'Dagger':                                # (sfb / random: chosen by build_seed.run_logic;
                    e['startWeapon'] = v + ('-ns' if o.get('no-sword', 0) % 2 else '')   # No sword start: never the Dagger)
            elif flag.startswith('start-'): e[{'start-hp': 'startingHealth', 'start-mp': 'startingMana', 'start-gold': 'startingGold'}[flag]] = v
            elif flag.startswith('pool:') or flag.startswith('item:'): e['pool'][flag.split(':', 1)[1]] = v
            else:
                tiers = next(t for k, _, t in UPGRADES if k == flag[3:])
                for i, name in enumerate(tiers): e['pool'][name] = 1 if i < v else 0
    return e


def flags(o):
    out = []
    for _, rows in all_tabs():
        for _, flag, shown_, passed in rows:
            if flag.startswith(EDITS + ('action:', 'cost:')) or flag in PORT_ONLY: continue
            i = o.get(flag, 0) % len(shown_) if flag != 'armor-strength' or o.get('remove-armor', 0) == 0 else 0
            out.append(f'--{flag}={(passed or [s.lower() for s in shown_])[i]}')
    if is_user_preset(current_preset(o)): out.append(f'--user-presets={USER_PRESETS}')
    out.append(f"--vessel-heal={'YN'[o.get('vessel-heal', 0) % 2]}")
    out.append('--drops=' + ','.join(k for k in ('healing', 'magic', 'money') if o.get(f'{k}-drops', 0) % 2 == 0))
    out.append('--shop=' + ('consume', 'all', 'once')[o.get('shop-items', 0) % 3])
    out.append(f"--boss-resist={'NY'[o.get('boss-resist', 0) % 2]}")
    out.append(f"--balance={('jp', 'us')[o.get('seed-balance', 0) % 2]}")
    out.append(f"--weapon-balance={'NY'[o.get('weapon-balance', 0) % 2]}")
    out.append(f"--stat-chance={10 * (o.get('stat-chance', 3) % 11)}")
    out.append(f"--twin-puzzles={'NY'[o.get('twin-puzzles', 0) % 2 if o.get('mode', 0) == 1 else 0]}")
    return out +['--instant-text=N', '--fast-loads=N', '--preset-edit=' + json.dumps(preset_edit(o), separators=(',', ':'))]


# ------------------------------------------------------------------- the player's presets --
def current_preset(o): return PRESETS[o.get('preset', 0) % len(PRESETS)]


def refresh_presets():
    global PRESETS, TABS
    PRESETS = preset_names(); TABS = _tabs(); _PRESET_DATA.clear()


_PRESET_DATA = {}


def preset_data(name):
    """A preset's settings (read once)."""
    if name not in _PRESET_DATA:
        sys.path.insert(0, str(TOOL)); import build_seed
        _PRESET_DATA[name] = build_seed.read_preset(USER_PRESETS / f'{name}.json' if is_user_preset(name) else TOOL / 'presets' / f'{name}.json')
    return _PRESET_DATA[name]


def effective(o):
    """The preset as the seed will use it: the menu's edits made, the pool balanced (as build_seed.edit_preset);
    the preset alone when the edits cannot fit."""
    import copy
    sys.path.insert(0, str(TOOL)); import build_seed
    p = preset_data(current_preset(o))
    try: return build_seed.edit_preset(copy.deepcopy(p), preset_edit(o))
    except RuntimeError: return p


def row_value(eff, flag, o=None):
    """What an edit row's 'the preset's' stands for: its number in the preset as used (effective); a cost row's,
    the price before the page (base_price)."""
    if flag.startswith('cost:'): return base_price(o or {}, flag[5:])
    gs = eff.get('gameSettings', {}); dist = eff.get('randomizerSettings', {}).get('itemsDistribution', {})
    if flag.startswith('start-'): return gs.get({'start-hp': 'startingHealth', 'start-mp': 'startingMana', 'start-gold': 'startingGold'}[flag], 0)
    if flag.startswith('up:'): return sum(dist.get(t, 0) for k, _, tiers in UPGRADES if k == flag[3:] for t in tiers)
    return dist.get(flag.split(':', 1)[1], 0)


def save_preset(o):
    """Every setting under a name: a preset of its own playing the randomizer (the chosen preset with the menu's edits,
    the pool kept one item a chest: build_seed.edit_preset) and the menu's settings.  A saved preset is saved over;
    otherwise the next free 'Custom n'.  Returns the name."""
    sys.path.insert(0, str(TOOL)); import build_seed
    base = current_preset(o)
    name = base if is_user_preset(base) else next(f'Custom {n}' for n in range(1, 1000) if f'Custom {n}' not in PRESETS)
    src = USER_PRESETS / f'{base}.json' if is_user_preset(base) else TOOL / 'presets' / f'{base}.json'
    p = build_seed.edit_preset(build_seed.read_preset(src), preset_edit(o))
    USER_PRESETS.mkdir(parents=True, exist_ok=True)
    (USER_PRESETS / f'{name}.json').write_text(json.dumps(p, indent=1), encoding='utf-8')
    (USER_PRESETS / f'{name}.menu').write_text(json.dumps({**o, 'preset': name}), encoding='utf-8')
    refresh_presets(); o['preset'] = PRESETS.index(name)
    return name


def load_preset(o):
    """A saved preset: every setting back as it was saved.  One of the randomizer's: its own values (the edits back
    to Preset)."""
    name = current_preset(o)
    if is_user_preset(name):
        m = json.loads((USER_PRESETS / f'{name}.menu').read_text(encoding='utf-8'))
        o.clear(); o.update(DEFAULTS); o.update(m)
    else:
        for k in [k for k in o if k.startswith(EDITS[1:])]: o[k] = 0
    o['preset'] = PRESETS.index(name)
    return name


def reset_options(o):
    """Every setting as on first start: the Default preset, its own values, the default options."""
    o.clear(); o.update(DEFAULTS)
    return 'Default'


def delete_preset(o):
    name = current_preset(o)
    if not is_user_preset(name): return None
    for ext in ('json', 'menu'): (USER_PRESETS / f'{name}.{ext}').unlink(missing_ok=True)
    refresh_presets(); o['preset'] = 0
    return name


# ------------------------------------------------------------------- the game side --
def latest():
    try:
        d = SEEDS / CURRENT.read_text(encoding='utf-8').strip()
        return d if (d / 'seed.json').exists() else None
    except OSError:
        return None


def _modules():
    return [m for n, m in list(sys.modules.items()) if m is not None and (n in ('__main__', 'alundra_remake', 'frontend', 'history_book', 'speedrun', 'combat', 'inventory_ui', 'jp_text', 'bizhawk_state', 'home') or n.startswith('engine.'))]


def _point_at(base, saves):
    from engine import rodata
    rodata._IMG = None
    for m in _modules():
        if hasattr(m, 'ASSETS'): m.ASSETS = base
        if hasattr(m, 'SAVES'): m.SAVES = saves
        sp = getattr(m, 'Sprite', None)
        if sp is not None and hasattr(sp, 'cache'): sp.cache.clear()
        if hasattr(m, 'GLOBAL_HEADERS'):
            m.GLOBAL_HEADERS = json.loads((base / 'sprites' / 'global_headers.json').read_text()).get('sprite_headers', {})
        if hasattr(m, 'MAP_SIZES'):
            m.MAP_SIZES = {int(k): v for k, v in json.loads((base / 'maps' / 'map_sizes.json').read_text()).items()}
        if isinstance(getattr(m, 'ITEMS', None), dict) and (base / 'text' / 'etc_usa.json').exists():
            m.ITEMS = json.loads((base / 'text' / 'etc_usa.json').read_text(encoding='utf-8')).get('items', {})
        game = getattr(m, 'Game', None)
        if game is not None and hasattr(game, '_EU'): game._EU = {}
        if game is not None and hasattr(game, '_JP_MAPS'): game._JP_MAPS = None   # (a seed's own JP lines: lang_text.py)


def activate(folder):
    global active, root
    root = Path(folder); active = json.loads((root / 'seed.json').read_text(encoding='utf-8'))
    (root / 'saves').mkdir(exist_ok=True)
    _point_at(root / 'assets', root / 'saves')
    __import__('tracker_link').start(root)          # (Seeds > Tracker: on, the linked tracker starts with this seed)
    global bridge
    if bridge is not None: bridge.stop(); bridge = None
    if active.get('archipelago'):
        import apbridge
        bridge = apbridge.Bridge(root)
    start_cc()


def start_cc():
    """Seeds > Crowd Control: on, a randomizer seed (not Archipelago) runs the CC script."""
    global cc
    if cc is not None: cc.stop()
    cc = None
    o = load_options()
    if active is None or active.get('archipelago') or o.get('crowd-control', 0) % 2 == 0: return
    import ccbridge
    cc = ccbridge.CrowdControl(border=o.get('cc-border', 0) % 2 == 1, channel=str(o.get('cc-channel', '') or ''),
                               points=o.get('cc-points', 0) % 2 == 1, buffed=o.get('cc-buffed', 0) % 2 == 1)


def deactivate():
    global active, root
    global bridge, cc
    if bridge is not None: bridge.stop(); bridge = None
    if cc is not None: cc.stop()
    cc = None
    if active is None: return
    active = root = None
    _point_at(STOCK, HOME / 'saves')


def exe_data():
    return (root / 'assets' if active else STOCK) / 'exe_data.bin'


def new_game_start():
    TW, TH = 24, 16
    return active['map'], (active['x'] * TW + TW // 2, active['y'] * TH + TH // 2, 0)


def after_flags_reset(g):
    """The injected init (PatchNewGame): the starting flags, the map variants, the item objects' physics."""
    if active is None: return
    m = g.mem
    for a, v in active['writes']: m.w16(a, v)
    for a in range(0x800CC004, 0x800CC168, 4):
        p = m.u32(a)
        if p != 0xFFFFFFFF and 0x80000000 <= p < 0x801FFFF8:
            m.w32(p, 0x800FEFB4); m.w32(p + 4, 0x800FEFFC)


def new_game(g, calls, x, y, z):
    """A new game's map, respawn point and starting stats (the patched immediates)."""
    if active is None: return x, y, z
    m = g.mem; c = active
    m.w32(0x801DD324, c['map']); m.w32(0x801DD328, c['x']); m.w32(0x801DD32C, c['y']); m.w32(0x801DD330, 0)
    calls.call(g, 0x8004F2DC, c['hp']); calls.call(g, 0x8004F3A8, c['hp'])
    calls.call(g, 0x8004F474, c['mp']); calls.call(g, 0x8004F540, c['mp']); calls.call(g, 0x8004F60C, c['gold'])
    return c['x'], c['y'], 0


def progressive(g, n):
    """PatchProgressiveItems' injected function: an upgrade gives the next tier of its slot.  (Not for the items a new
    game starts with, gamestart.py: the game obtains those without it.)"""
    if active is None or not active.get('progressive') or starting: return n
    if active.get('split_boots'):
        if n > 0x18 or 0x19 <= n <= 0x1C: return n
    elif n > 0x1D: return n
    from engine import rodata as R, menu
    REC = 0x800BBE50
    slot = g.mem.s16(REC + 10 * n)
    best = menu.best_of_group(g, slot)
    tier = 0 if best < 0 else g.mem.s16(REC + 10 * best + 4) + 1
    for k in range(61):
        if g.mem.s16(REC + 10 * k) == slot and g.mem.s16(REC + 10 * k + 4) == tier: return k
    return n


DREAM_ROOMS = {r: i for i, rooms in enumerate(((44, 45, 46), (41, 42, 43, 47), (100, 101, 102, 103, 104, 105, 106, 107, 108, 449),
               (123, 124, 125, 126, 127, 128), (109, 110, 111, 112, 113, 114), (48, 49, 50, 51, 52, 53, 54, 435, 436, 437, 438, 469),
               (308, 309, 310, 440, 441, 442, 468), (362, 363))) for r in rooms}
DREAM_TARGETS = {179: 0, 196: 1, 240: 2, 229: 3, 147: 4, 270: 5, 393: 6, 366: 7}
DREAM_DOORS = ((5, 33), (15, 52), (12, 33), (46, 52), (5, 33), (47, 35), (26, 54), (20, 18))


def dream_warp(g):
    """PatchDreamDungeon's wrapper of op 53: a nightmare's completion warp lands outside its door in
    Inoa (map 241) with movement unlocked."""
    if active is None or not active.get('dreams'): return
    i = DREAM_ROOMS.get(g.cur_map)
    if i is None or DREAM_TARGETS.get(g.warp_map) != i: return
    x, y = DREAM_DOORS[i]
    g.warp_map = 241; g.warp_x = (x * 24 + 12) << 16; g.warp_y = ((y + 1) * 16 + 8) << 16; g.warp_z = 0
    g.mode_flags &= ~4                                   # (the movement lock, 0x801F0060 bit 2)
    g.player_locked = False                              # (the port's mirror of it, what MovePlayer reads)


def install_ops(handlers):
    """The injected event instructions: C5 (5 bytes) and C6 (3 bytes) do nothing."""
    stock5, stock6 = handlers.get(0xC5), handlers.get(0xC6)
    def c5(vm, lg, ow, v, st, row): return 5 if active is not None else stock5(vm, lg, ow, v, st, row)
    def c6(vm, lg, ow, v, st, row): return 3 if active is not None else stock6(vm, lg, ow, v, st, row)
    def c7(vm, lg, ow, v, st, row):                     # (a seed's door to Melzas: has all of these items)
        from engine import menu
        st.result = int(all(menu.has_item(vm.g, i) > 0 for i in v[1:10] if i))
        return 10
    handlers[0xC5] = c5; handlers[0xC6] = c6; handlers[0xC7] = c7


class Generator:
    """The worker process, seen from the menu."""
    def __init__(self, options):
        SEEDS.mkdir(exist_ok=True)
        OPTIONS.write_text(json.dumps(options)); PROGRESS.write_text('Starting')
        cmd = [sys.executable, '--run-script'] if getattr(sys, 'frozen', False) else [sys.executable, '-u']
        self.p = subprocess.Popen([*cmd, str(Path(__file__).resolve()), '--worker'], cwd=str(SEEDS), creationflags=NO_WINDOW,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def status(self):
        try: return PROGRESS.read_text(encoding='utf-8')
        except OSError: return ''

    def finished(self): return self.p.poll() is not None


def find_patch():
    import tkinter as tk
    from tkinter import filedialog
    r = tk.Tk(); r.withdraw()
    p = filedialog.askopenfilename(title='Your Archipelago patch', filetypes=[('Alundra patch', '*.apalundra')])
    r.destroy()
    return Path(p) if p else None


# --------------------------------------------------------------------- the worker --
def say(t):
    PROGRESS.write_text(t, encoding='utf-8')


def merge(stock, over, pool=None, todo=None):
    """Whatever the seed did not keep comes from assets/: junctions for folders it lacks, hard links for
    files, at every depth (a folder's frames are read from its pack when it has one: game/packs.py).
    pool: the folders below are merged on its threads, their futures added to todo."""
    import _winapi
    packed = (stock / '_pack.bin').exists()
    for e in stock.iterdir():
        if packed and e.suffix == '.png' and e.name[0].isdigit(): continue
        t = over / e.name
        if e.is_dir():
            if not t.exists(): _winapi.CreateJunction(str(e), str(t))
            elif not os.stat(t, follow_symlinks=False).st_reparse_tag:
                if pool is None: merge(e, t)
                else: todo.append(pool.submit(merge, e, t, pool, todo))
        elif not t.exists():
            try: os.link(e, t)
            except OSError: shutil.copyfile(e, t)


def worker():
    sys.path.insert(0, str(TOOL))
    import build_seed
    patch = json.loads(OPTIONS.read_text()).get('appatch')
    work = SEEDS / 'work'; shutil.rmtree(work, ignore_errors=True); (work / 'out').mkdir(parents=True)
    names = {}; code = None
    if patch:
        placements, names, settings = read_patch(patch)
        (work / 'placements.json').write_text(json.dumps(placements))
        args = [*patch_flags(settings), f"--placements={work / 'placements.json'}"]
    else:
        opts = load_options(); code = opts.pop('seedcode', None)
        if code is not None: save_options(opts)              # (the code is for this seed only)
        args = code_args(code, work) if code else flags(opts)
    try:
        spoiler, seed = build_seed.build(args, STOCK, work / 'out', say)
        name = spoiler['hashSentence']
        if patch:
            seed['foreign'] = build_seed.chest_names(STOCK, names); seed['archipelago'] = True; name = seed['name'] = 'AP ' + Path(patch).stem
            spoiler = {'archipelago': str(patch), 'gameSettings': spoiler['gameSettings']}
        say('Finishing')
        if not patch and code:                               # (a shared seed never replaces one with saves)
            base = name; k = 2
            while (SEEDS / name).exists(): name = seed['name'] = f'{base} ({k})'; k += 1
        folder = SEEDS / name; shutil.rmtree(folder, ignore_errors=True); folder.mkdir()
        if not patch and build_seed.LAST_PRESET is not None:
            preset = {**build_seed.LAST_PRESET, 'seed': build_seed.permalink_seed(spoiler['permalink'])}
            (folder / 'share.json').write_text(json.dumps({'preset': preset, 'args': share_args(args)}), encoding='utf-8')
        shutil.move(str(work / 'out'), str(folder / 'assets'))
        import packs                                     # the maps the seed changed: their own map packs
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as pool:              # (file system waits: on threads)
            todo = []; merge(STOCK, folder / 'assets', pool, todo)
            while todo: todo.pop().result()
            maps = [d for d in (folder / 'assets' / 'maps').glob('[0-9][0-9][0-9]') if d.is_dir() and not os.stat(d, follow_symlinks=False).st_reparse_tag]
            for f in [pool.submit(packs.make_map, d) for d in maps]: f.result()
        (folder / 'spoiler.json').write_text(json.dumps(spoiler, indent=1), encoding='utf-8')
        (folder / 'seed.json').write_text(json.dumps(seed), encoding='utf-8')
        CURRENT.write_text(name, encoding='utf-8')
    finally:
        shutil.rmtree(work, ignore_errors=True)
    say('Done')



# ------------------------------------------------------------------- shared seeds --
CODE_PREFIX = 'ALUNDRA1-'
_NOT_SHARED = ('--preset=', '--preset-edit=', '--user-presets=', '--permalink=', '--placements=')


def share_args(args):
    """The arguments a code carries besides the permalink: the options the permalink does not hold (the port's)."""
    return [a for a in args if not a.startswith(_NOT_SHARED)]


def seed_folders():
    """The seeds made before, newest first: [(name, folder)]."""
    try: found = [d for d in SEEDS.iterdir() if d.is_dir() and (d / 'seed.json').exists()]
    except OSError: return []
    return [(d.name, d) for d in sorted(found, key=lambda d: (d / 'seed.json').stat().st_mtime, reverse=True)]


def share_code(folder):
    """The code that makes the same seed elsewhere (None: an Archipelago seed, or no seed)."""
    import base64, zlib
    if folder is None: return None
    try: share = json.loads((Path(folder) / 'share.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        try: spoiler = json.loads((Path(folder) / 'spoiler.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): return None
        if 'permalink' not in spoiler: return None
        share = {'permalink': spoiler['permalink'], 'args': []}          # (a seed made before codes: the permalink only)
    raw = zlib.compress(json.dumps(share, separators=(',', ':')).encode('utf-8'), 9)
    return CODE_PREFIX + base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def read_code(code):
    """A shared code's {'permalink', 'args'}; ValueError when it is not one."""
    import base64, zlib, binascii
    code = ''.join(code.split())
    if not code.startswith(CODE_PREFIX): raise ValueError('That is not a seed code.')
    body = code[len(CODE_PREFIX):]
    try: share = json.loads(zlib.decompress(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4))))
    except (binascii.Error, zlib.error, ValueError): raise ValueError('That seed code is damaged.')
    if not isinstance(share, dict) or not isinstance(share.get('args', []), list) or \
            not (isinstance(share.get('preset'), dict) or isinstance(share.get('permalink'), str)):
        raise ValueError('That seed code is damaged.')
    return share


def code_args(code, work):
    """The randomizer's arguments for a code: its preset (with the seed number) as a player preset, and its options."""
    share = read_code(code)
    if 'preset' not in share: return [*share_args(share.get('args', [])), f"--permalink={share['permalink']}"]   # (a seed made before codes)
    own = Path(work) / 'shared_preset'; own.mkdir(parents=True, exist_ok=True)
    (own / '_shared.json').write_text(json.dumps(share['preset']), encoding='utf-8')
    return [*share_args(share.get('args', [])), '--preset=_shared', f'--user-presets={own}']


def copy_text(text):
    """To the clipboard (Windows' clip)."""
    subprocess.run(['clip'], input=text.encode('utf-16-le'), creationflags=NO_WINDOW, check=True)

AP_NAMES = {'Mining Bomb': 'Bomb', 'Magic Elixir': 'Magic Elixyr', 'Strength Elixir': 'Strength Elixyr', 'Earth Magic': 'Earth Magic upgrade', 'Water Magic': 'Water Magic upgrade',
            'Fire Magic': 'Fire Magic upgrade', 'Wind Magic': 'Wind Magic upgrade', 'Sword Upgrade': 'Sword upgrade', 'Flail Upgrade': 'Flail upgrade', 'Bow Upgrade': 'Bow upgrade', 'Armor Upgrade': 'Armor upgrade'}


def read_patch(patch):
    """The .apalundra's placements (in the randomizer's item names), other players' names and options."""
    import zipfile
    with zipfile.ZipFile(patch) as z:
        get = lambda n: json.loads(z.read(n)) if n in z.namelist() else {}
        placements = get('placements.json')['placements']
        return {k: AP_NAMES.get(v, v) for k, v in placements.items()}, get('foreign.json'), get('settings.json')


def patch_flags(settings):
    """The yaml's port options as the randomizer's arguments."""
    types = {'hp_atk_spd': 'hp,atk,spd', 'hp_atk': 'hp,atk'}
    g = settings.get; yn = lambda k, d: 'YN'[g(k, d) != 'yes']
    drops = [k for k in ('healing', 'magic') if g(f'{k}_drops', 'yes') == 'yes'] + ['money']   # (Money drops: in logic, always on)
    return ['--preset=default', '--mode=classic', '--instant-text=N', '--remove-armor=N', '--fast-loads=N', f"--armor-strength={g('armor_strength', 'full')}",
            f"--enemies={g('random_enemies', 'off')}", f"--random-stats={g('random_stats', 'off')}", f"--stat-changes={g('stat_changes', 'buffs')}",
            f"--stat-types={types.get(g('stat_types'), g('stat_types', 'hp,atk,spd'))}", f"--stat-colors={g('stat_colors', 'no_change').replace('_', '-')}",
            f"--stat-chance={int(g('stat_chance', 100))}", f"--balance={g('enemy_balance', 'jp')}", f"--boss-resist={'NY'[g('boss_resist', 'original') == 'adjusted']}",
            f"--weapon-balance={'NY'[g('weapon_balance', 'original') == 'adjusted']}", f"--vessel-heal={yn('vessel_heal', 'yes')}", '--drops=' + ','.join(drops)]


def foreign_text(g, msg, flag):
    """ARCHIPELAGO: the chest's Sluice Key text names what the other player gets."""
    t = active.get('foreign', {}).get(str(flag & 0xFFFF)) if active is not None else None
    if not t: return
    from engine import message
    old = message._cstr(g, msg)
    key = message._cstr(g, g.mem.u32(0x800C7DE4 + 8 * 73))        # (item 73 in the language being played)
    if key not in old: return
    t = t.encode('ascii', 'replace')[:44]
    if len(t) > 22 and b"'s " in t: t = t.replace(b"'s ", b"'s\\N", 1)     # (two lines, as the game's own long names)
    message._write_str(g, msg, old.replace(key, t))


if __name__ == '__main__':
    if '--worker' in sys.argv:
        try:
            worker()
        except BaseException as e:
            SEEDS.mkdir(exist_ok=True)
            (SEEDS / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
            say(str(e) if isinstance(e, RuntimeError) and '\n' not in str(e) else 'Failed: see seeds/error.log')
            sys.exit(1)
