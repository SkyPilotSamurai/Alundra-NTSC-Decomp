"""ARCHIPELAGO's yaml menu: the apworld's options (Options.py) as menu rows, and the player yaml they make.
A row: (label, yaml key, values shown, values written); a count row: (label, yaml key, default, most)."""
import json
from home import HOME

STATE = HOME / 'seeds' / 'ap_yaml.json'
GAME_ROWS = (
    ('Accessibility', 'accessibility', ('Full', 'Minimal'), ('full', 'minimal')),
    ('Armor strength', 'armor_strength', ('Full', 'Half', 'Quarter'), ('full', 'half', 'quarter')),
    ('Balance', 'enemy_balance', ('JP', 'US & EU'), ('jp', 'us')),
    ('Random Enemies', 'random_enemies', ('Off', 'Shuffle', 'Random', 'Switch'), ('off', 'shuffle', 'switch', 'swap')),
    ('Random stats', 'random_stats', ('Off', 'Enemies', 'Enemies & Bosses'), ('off', 'enemies', 'both')),
    ('Stat changes', 'stat_changes', ('Buffs', 'Mixed'), ('buffs', 'mixed')),
    ('Stat chance', 'stat_chance', tuple(f'{v}%' for v in range(0, 101, 10)), tuple(str(v) for v in range(0, 101, 10)), 3),
    ('Stat types', 'stat_types', ('HP, ATK, SPD', 'HP, ATK', 'HP', 'ATK', 'SPD', 'None'), ('hp_atk_spd', 'hp_atk', 'hp', 'atk', 'spd', 'none')),
    ('Stat colors', 'stat_colors', ('No Change', 'Changed', 'Random'), ('no_change', 'changed', 'random')),
    ('Late Game Boss Resistance', 'boss_resist', ('Original', 'Adjusted'), ('original', 'adjusted')),
    ('Weapon Balance', 'weapon_balance', ('Original', 'Adjusted'), ('original', 'adjusted')),
    ('Life Vessels heal', 'vessel_heal', ('Yes', 'No'), ('yes', 'no')),
    ('Healing drops', 'healing_drops', ('Yes', 'No'), ('yes', 'no')),
    ('Magic drops', 'magic_drops', ('Yes', 'No'), ('yes', 'no')),
)


def _counts(*rows):
    return tuple((label, label.lower().replace("'", '').replace(' ', '_') + '_count', default, most) for label, default, most in rows)


TABS = (
    ('Game', GAME_ROWS),
    ('Items', _counts(('Life Vessel', 40, 100), ('Magic Seed', 4, 20), ('Herbs', 30, 100), ('Strength Tonic', 5, 100), ('Strength Elixir', 5, 100),
                      ('Magic Elixir', 5, 100), ('Wonder Essence', 2, 100), ('Gilded Falcon', 80, 200), ('Gilder', 30, 100), ('Gilder 10', 0, 100),
                      ('Gilder 5', 0, 100), ('Gilder 1', 0, 100))),
    ('Gear', _counts(('Sword', 4, 20), ('Flail', 2, 20), ('Bow', 2, 20), ('Armor', 3, 20), ('Fire Wand', 2, 20), ('Ice Wand', 2, 20), ('Mining Bomb', 2, 20),
                     ('Long Boots', 2, 20), ('Merman Boots', 2, 20), ('Charm Boots', 1, 20), ('Sand Cape', 2, 20), ('Aqua Cape', 2, 20), ('Power Glove', 2, 20),
                     ('Spring Bean', 2, 20), ("Nava's Charm", 1, 20), ("Olga's Ring", 1, 20), ('Silver Armlet', 1, 20), ('Recovery Ring', 1, 20),
                     ('Earth Magic', 2, 20), ('Water Magic', 2, 20), ('Fire Magic', 2, 20), ('Wind Magic', 2, 20))),
    ('Keys', _counts(('Bouquet', 2, 20), ('Tree Gem', 2, 20), ('Secret Pass', 2, 20), ('Small Key', 2, 20), ('Broken Armor', 2, 20), ('Ruby Crest', 2, 20),
                     ('Sapphire Crest', 2, 20), ('Topaz Crest', 2, 20), ('Agate Crest', 2, 20), ('Garnet Crest', 2, 20), ('Emerald Crest', 2, 20), ('Diamond Crest', 2, 20))),
)
ABOUT = {'accessibility': 'Full: every location can be reached.', 'armor_strength': 'How much armor reduces damage.',
         'random_enemies': 'How enemies are randomized.', 'random_stats': 'Who gets changed stats.', 'stat_changes': 'Mixed can weaken; Buffs only boost.',
         'stat_types': 'Which stats can change.', 'stat_colors': 'The tint of buffed enemies.', 'stat_chance': 'The odds of a stat change.',
         'enemy_balance': 'Enemy and boss values for this seed.', 'boss_resist': "Late game bosses' resistance to weapons.",
         'weapon_balance': 'Weapons hit as in the game, or adjusted.', 'vessel_heal': 'No: a vessel adds health, heals none.',
         'healing_drops': 'No: nothing dropped heals.', 'magic_drops': 'No: no magic is dropped.'}


def shown(key, v):
    if key in ('stat_changes', 'stat_chance', 'stat_types'): return v.get('random_stats', 0) != 0
    return True


def default(row):
    return row[2] if isinstance(row[2], int) else row[4] if len(row) > 4 else 0


def load():
    """{'values': {key: index or count}, 'name', 'path'}"""
    s = {'values': {}, 'name': 'Alundra', 'path': None}
    try: s.update(json.loads(STATE.read_text(encoding='utf-8')))
    except (OSError, ValueError): pass
    return s


def save(s):
    STATE.parent.mkdir(exist_ok=True); STATE.write_text(json.dumps(s), encoding='utf-8')


def text(s):
    out = ['# Alundra player settings, made by the game\'s Archipelago menu', f'name: {s["name"]}', 'game: Alundra', '', 'Alundra:']
    for tab, rows in TABS:
        out.append(f'  # {tab}')
        for row in rows:
            v = s['values'].get(row[1], default(row))
            w = row[3][v % len(row[3])] if not isinstance(row[2], int) else v
            out.append(f'  {row[1]}: "{w}"' if w in ('yes', 'no', 'on', 'off') else f'  {row[1]}: {w}')   # (YAML reads those bare as true / false)
    return '\n'.join(out) + '\n'
