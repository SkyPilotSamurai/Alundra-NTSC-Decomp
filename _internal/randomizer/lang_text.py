"""The randomizer's own lines in every Dialogue & font language (user 2026-11-07).

The build writes its lines (shop prompts, Received lines, rewards, hints, Septimus' hints, the nightmare doors'
gates, Nava's line) into the US strings (maps/NNN/data.json).  The other languages read text_<lang>/maps.json
(the European discs' and the JP disc's own texts), where those lines are the disc's own - the vanilla item, no
hint - or empty (a line the randomizer added).  apply() writes the seed's copy of each language's maps.json:

* en_eu: the US line as the build wrote it.
* fr / de / it / es / jp: the line in that language - item names from the language's own item table
  (etc.json 512 + item), place names from its own place names (global_strings.json) where the disc has one,
  the rest translated here.  A line that only names an item (rewards) keeps the disc's own line with the item's
  name replaced; a guardian's hint keeps the disc's own speech with the hint added at its end.

JP lines: full-width characters, 16 to a line, three lines to a box (as the disc's own)."""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGS = ('en_eu', 'fr', 'de', 'it', 'es', 'jp')
B = '\\'
CODE = re.compile(r'\\[0-9]{4}|\\W[0-9]|\\[A-Z]')

# ------------------------------------------------------------------ names --
UPGRADES = {   # (the progressive items: not in the discs' item tables)
    11: {'fr': "Amélioration d'épée", 'de': 'Schwert-Verbesserung', 'it': 'Potenziamento spada', 'es': 'Mejora de espada', 'jp': '剣の強化'},
    12: {'fr': 'Amélioration de fléau', 'de': 'Flegel-Verbesserung', 'it': 'Potenziamento flagello', 'es': 'Mejora de mangual', 'jp': 'フレイルの強化'},
    13: {'fr': "Amélioration d'arc", 'de': 'Bogen-Verbesserung', 'it': 'Potenziamento arco', 'es': 'Mejora de arco', 'jp': '弓の強化'},
    15: {'fr': "Amélioration d'armure", 'de': 'Rüstungs-Verbesserung', 'it': 'Potenziamento corazza', 'es': 'Mejora de armadura', 'jp': '鎧の強化'},
    21: {'fr': 'Amélioration magie Terre', 'de': 'Erdmagie-Verbesserung', 'it': 'Potenziamento magia Terra', 'es': 'Mejora de magia Tierra', 'jp': '大地の魔法の強化'},
    22: {'fr': 'Amélioration magie Eau', 'de': 'Wassermagie-Verbesserung', 'it': 'Potenziamento magia Acqua', 'es': 'Mejora de magia Agua', 'jp': '水の魔法の強化'},
    23: {'fr': 'Amélioration magie Feu', 'de': 'Feuermagie-Verbesserung', 'it': 'Potenziamento magia Fuoco', 'es': 'Mejora de magia Fuego', 'jp': '炎の魔法の強化'},
    24: {'fr': 'Amélioration magie Vent', 'de': 'Windmagie-Verbesserung', 'it': 'Potenziamento magia Vento', 'es': 'Mejora de magia Viento', 'jp': '風の魔法の強化'},
    29: {'fr': 'Amélioration de bottes', 'de': 'Stiefel-Verbesserung', 'it': 'Potenziamento stivali', 'es': 'Mejora de botas', 'jp': '靴の強化'},
}

# the game's place names (global_strings.json) for the hints' places; the others below
PLACE_IDS = {'Ancient Shrine': 89, "Bonaire's Dream": 88, 'Coal Mine': 85, 'Coastal Cave': 90, "Elene's Dream": 100,
             'Fire Manor': 109, "Giles' Dream": 93, 'Ice Manor': 110, "Kline's Dream": 91, 'Lake Shrine': 106,
             'Lars Crypt': 87, 'Magyscar': 94, "Meia's Dream": 96, "Nava's Keep": 105, "Nirude's Lair": 98,
             'Reptile Lair': 92, 'Tarn Manor': 81, 'Torla Mountain': 30, "Twins' Dream": 104, "Wendell's Dream": 112,
             "Olen's Dream": 84, 'the Fairy Pond': 99, 'the Underground Waterway': 97, 'Sanctuary': 95}
# where-phrases: (preposition, place) -> the phrase; {} = the game's name for the place
WHERE = {
    'fr': {'in': {'': 'dans {}', 'Inoa': 'à Inoa', 'Magyscar': 'dans Magyscar', 'Torla Mountain': 'sur le {}',
                  'Riverside Casino': 'au Casino de Riverside', 'an unknown place': 'dans un lieu inconnu',
                  'lower desert': 'dans le bas du désert', 'upper desert': 'dans le haut du désert',
                  'ruins north of Fire Manor': 'dans les ruines au nord du Manoir de feu',
                  'the Cliffs of Madness': 'sur les Falaises de la folie', 'the Murgg woods': 'dans les bois des Murgg',
                  'the Great Tree': 'dans le Grand arbre'},
           'near': {'': 'près de {}', 'Nava\'s cabin': 'près de la cabane de Nava', 'Riverside pub': 'près du pub de Riverside',
                    'the watermill': 'près du moulin à eau', 'Sanctuary': 'près du {}', 'Tarn Manor': 'près du {}',
                    'Coal Mine': 'près de la {}'}},
    'de': {'in': {'': 'in {}', 'Torla Mountain': 'auf dem {}', 'Riverside Casino': 'im Riverside-Kasino',
                  'an unknown place': 'an einem unbekannten Ort', 'lower desert': 'in der unteren Wüste',
                  'upper desert': 'in der oberen Wüste', 'ruins north of Fire Manor': 'in den Ruinen nördlich des Feuerpalasts',
                  'the Cliffs of Madness': 'auf den Klippen des Wahnsinns', 'the Murgg woods': 'in den Murgg-Wäldern',
                  'the Great Tree': 'im großen Baum', 'Coal Mine': 'in der {}', 'Coastal Cave': 'in der {}',
                  'Ancient Shrine': 'im Alten Schrein', 'Fire Manor': 'im {}', 'Ice Manor': 'im {}', 'Lake Shrine': 'im {}',
                  'Lars Crypt': 'in der {}', 'Reptile Lair': 'in der {}', 'the Fairy Pond': 'im {}',
                  'the Underground Waterway': 'im {}'},
           'near': {'': 'nahe {}', 'Nava\'s cabin': 'nahe Navas Hütte', 'Riverside pub': 'nahe der Riverside-Kneipe',
                    'the watermill': 'nahe der Wassermühle', 'Coal Mine': 'nahe der {}', 'Sanctuary': 'nahe der {}'}},
    'it': {'in': {'': 'in {}', 'Inoa': 'a Inoa', 'Magyscar': 'a Magyscar', 'Torla Mountain': 'sul {}',
                  'Riverside Casino': 'nel Casinò di Riverside', 'an unknown place': 'in un luogo sconosciuto',
                  'lower desert': 'nella parte bassa del deserto', 'upper desert': 'nella parte alta del deserto',
                  'ruins north of Fire Manor': 'nelle rovine a nord della Tenuta del Fuoco',
                  'the Cliffs of Madness': 'sulle Scogliere della follia', 'the Murgg woods': 'nel bosco dei Murgg',
                  'the Great Tree': 'dentro il Grande Albero'},
           'near': {'': 'vicino a {}', 'Nava\'s cabin': 'vicino alla capanna di Nava', 'Riverside pub': 'vicino al pub di Riverside',
                    'the watermill': 'vicino al mulino ad acqua'}},
    'es': {'in': {'': 'en {}', 'Riverside Casino': 'en el Casino de Riverside', 'an unknown place': 'en un lugar desconocido',
                  'lower desert': 'en la parte baja del desierto', 'upper desert': 'en la parte alta del desierto',
                  'ruins north of Fire Manor': 'en las ruinas al norte de la Mansión del fuego',
                  'the Cliffs of Madness': 'en los Acantilados de la locura', 'the Murgg woods': 'en el bosque de los Murgg',
                  'the Great Tree': 'dentro del Gran Arbol'},
           'near': {'': 'cerca de {}', 'Nava\'s cabin': 'cerca de la cabaña de Nava', 'Riverside pub': 'cerca del bar de Riverside',
                    'the watermill': 'cerca del molino de agua'}},
    'jp': {'in': {'': '{}', 'Inoa': 'イノアの村', 'Magyscar': '『お袋』', 'Torla Mountain': 'トーラ山', "Nava's Keep": 'ハヴァンの地下通路',
                  "Nirude's Lair": '巨神『ニルード』のすみか', 'Riverside Casino': 'カジノ', 'an unknown place': 'どこか知らない場所',
                  'lower desert': '砂漠の低地', 'upper desert': '砂漠の高台', 'ruins north of Fire Manor': '炎の館の北の遺跡',
                  'the Cliffs of Madness': '狂気の崖', 'the Murgg woods': 'ムルータの森', 'the Great Tree': '大樹の塔'},
           'near': {'': '{}の近く', 'Nava\'s cabin': 'ハヴァンの小屋の近く', 'Riverside pub': '川沿いの酒場の近く',
                    'the watermill': '水車小屋の近く', 'Magyscar': '『お袋』の近く', 'Coal Mine': 'イノアの炭坑の近く'}},
}
HINT = {   # (item can be found / nothing of interest / something useful) + where
    'fr': ('{item} se trouve {w}', "il n'y a rien d'intéressant {w}", "quelque chose d'utile se trouve {w}"),
    'de': ('{item} befindet sich {w}', 'es gibt nichts Interessantes {w}', 'etwas Nützliches befindet sich {w}'),
    'it': ('{item} si trova {w}', "non c'è nulla di interessante {w}", 'qualcosa di utile si trova {w}'),
    'es': ('{item} se encuentra {w}', 'no hay nada de interés {w}', 'algo útil se encuentra {w}'),
    'jp': ('{w}に{item}がある', '{w}には何もない', '{w}に役立つ物がある'),
}

# ------------------------------------------------------------------ lines --
SEPTIMUS = {'fr': "{c}Alundra, c'est moi, Septimus. Écoute bien : {hint}.", 'de': '{c}Alundra, ich bin es, Septimus. Hör gut zu: {hint}.',
            'it': '{c}Alundra, sono io, Septimus. Ascolta bene: {hint}.', 'es': '{c}Alundra, soy yo, Septimus. Escucha bien: {hint}.',
            'jp': '{c}アランドラよ、セクタスじゃ。よく聞くがよい。{hint}。'}
HINT_ADD = {'fr': 'Écoute bien : {hint}.', 'de': 'Hör gut zu: {hint}.', 'it': 'Ascolta bene: {hint}.', 'es': 'Escucha bien: {hint}.',
            'jp': 'よいか、{hint}。'}
SHOP = {'fr': '{item} : {price} florins. D\'accord ?', 'de': '{item} kostet {price} Gulden. Ok?', 'it': '{item} costa {price} Gilder. Va bene?',
        'es': '{item} cuesta {price} Gilder. ¿Vale?', 'jp': '{item}か、{price}ギルダじゃな。', 'jp\\D': '{item}ね。{price}ギルダよ。'}
RECEIVED = {'fr': 'Obtenu : {item}.', 'de': '{item} erhalten.', 'it': 'Ricevuto: {item}.', 'es': 'Obtención: {item}.', 'jp': '{item}を手にいれた。'}
GAMES = {22: {'fr': 'Chasseurs de Limons', 'de': 'Schleimige verprügeln', 'it': 'Caccia Slime', 'es': 'Slime Busters', 'jp': 'スライムたたき'},
         23: {'fr': 'Chasse aux Monstres', 'de': 'Monster-Schießen', 'it': 'Colpisci il Mostro', 'es': 'Disparar al monstruo', 'jp': 'モンスター射的'},
         24: {'fr': 'Roulette', 'de': 'Roulette', 'it': 'Roulette', 'es': 'Ruleta', 'jp': 'ルーレット'}}
REWARDS = {'fr': "Récompenses de '{g}' :", 'de': "Preise bei '{g}':", 'it': "Premi di '{g}':", 'es': "Premios de '{g}':", 'jp': '『{g}』の景品：'}
FIXED = {   # (map, string): whole lines the build writes in place of the disc's
    (25, 37): {'fr': '{c}Bonne chance dans ta quête.', 'de': '{c}Viel Glück bei Deiner Suche.', 'it': '{c}Buona fortuna per la tua missione.',
               'es': '{c}Buena suerte en tu búsqueda.', 'jp': '{c}そなたの旅の無事を祈っておるぞ。'},
    (61, 8): {'fr': '\\B\\HSalle des machines à droite\\N\\HPour démarrer le moteur :\\N\\HGauche, gauche, droite, gauche',
              'de': '\\B\\HMaschinenraum rechts\\N\\HUm die Maschine zu starten:\\N\\HLinks, links, rechts, links',
              'it': '\\B\\HSala macchine a destra\\N\\HPer avviare il motore:\\N\\HSinistra, sinistra, destra, sinistra',
              'es': '\\B\\HSala de máquinas a la derecha\\N\\HPara arrancar el motor:\\N\\HIzquierda, izquierda, derecha, izquierda',
              'jp': '\\B\\H右に機関室\\N\\H機関の動かし方：\\N\\H左、左、右、左'},
}
SHORTENED = {(432, 32), (432, 34)}   # (the build cuts these speeches short: the disc's own first two boxes)
GATES = {'Wendell': {'fr': "Wendell est perdu dans un cauchemar, mais tu n'es pas prêt à y entrer. Tu dois d'abord nettoyer le sous-sol du Manoir de Tarn.",
                     'de': 'Wendell ist in einem Alptraum gefangen, aber Du bist noch nicht bereit, ihn zu betreten. Du musst erst den Keller von Tarn´s Anwesen säubern.',
                     'it': 'Wendell è perso in un incubo, ma non sei pronto per entrarvi. Devi prima ripulire il sotterraneo della Tenuta di Tarn.',
                     'es': 'Wendell está perdido en una pesadilla, pero no estás preparado para entrar. Antes debes limpiar el sótano de la Casa de Tarn.',
                     'jp': 'ワインズは悪夢にとらわれておる。だが、まだ入るときではない。ターラスの館の地下をかたづけるのじゃ。'},
         'twins': {'fr': "Les jumeaux sont perdus dans un cauchemar, mais tu n'es pas prêt à y entrer. Il te faut deux armoiries.",
                   'de': 'Die Zwillinge sind in einem Alptraum gefangen, aber Du bist noch nicht bereit, ihn zu betreten. Du brauchst zwei Wappen.',
                   'it': 'I gemelli sono persi in un incubo, ma non sei pronto per entrarvi. Ti servono due creste.',
                   'es': 'Los gemelos están perdidos en una pesadilla, pero no estás preparado para entrar. Necesitas dos emblemas.',
                   'jp': 'ふたごは悪夢にとらわれておる。だが、まだ入るときではない。紋章がふたつ必要じゃ。'},
         'Kline': {'fr': "Kline est perdu dans un cauchemar, mais tu n'es pas prêt à y entrer. Il te faut une armoirie.",
                   'de': 'Kline ist in einem Alptraum gefangen, aber Du bist noch nicht bereit, ihn zu betreten. Du brauchst ein Wappen.',
                   'it': 'Kline è perso in un incubo, ma non sei pronto per entrarvi. Ti serve una cresta.',
                   'es': 'Kline está perdido en una pesadilla, pero no estás preparado para entrar. Necesitas un emblema.',
                   'jp': 'クラインは悪夢にとらわれておる。だが、まだ入るときではない。紋章がひとつ必要じゃ。'},
         'Meia': {'fr': "Meia est perdue dans un rêve, mais tu n'es pas prêt à y entrer. Il te faut {iron} ou {steel} et {boots}.",
                  'de': 'Meia ist in einem Traum gefangen, aber Du bist noch nicht bereit, ihn zu betreten. Du brauchst {iron} oder {steel} und {boots}.',
                  'it': 'Meia è persa in un sogno, ma non sei pronto per entrarvi. Ti servono {iron} o {steel} e {boots}.',
                  'es': 'Meia está perdida en un sueño, pero no estás preparado para entrar. Necesitas {iron} o {steel} y {boots}.',
                  'jp': 'メディアムは夢にとらわれておる。だが、まだ入るときではない。{iron}か{steel}と、{boots}が必要じゃ。'}}
GATE_ITEMS = {'iron': 'Iron Flail', 'steel': 'Steel Flail', 'boots': 'Merman Boots'}   # (Meia's line: the items' names in each language)
WHO = {'Wendell': {'fr': 'de Wendell', 'de': 'Wendells', 'it': 'di Wendell', 'es': 'de Wendell', 'jp': 'ワインズ', 'name': {'jp': 'ワインズ'}},
       "the twins'": {'fr': 'des jumeaux', 'de': 'der Zwillinge', 'it': 'dei gemelli', 'es': 'de los gemelos', 'jp': 'ふたご'},
       'Bonaire': {'fr': 'de Bonaire', 'de': 'Bonaires', 'it': 'di Bonaire', 'es': 'de Bonaire', 'jp': 'ボージス'},
       'Giles': {'fr': 'de Giles', 'de': "Giles'",'it': 'di Giles', 'es': 'de Giles', 'jp': 'ゴウセル'},
       'Kline': {'fr': 'de Kline', 'de': 'Klines', 'it': 'di Kline', 'es': 'de Kline', 'jp': 'クライン'},
       'Elene': {'fr': "d'Elene", 'de': 'Elenes', 'it': 'di Elene', 'es': 'de Elene', 'jp': 'エリーン'},
       'Meia': {'fr': 'de Meia', 'de': 'Meias', 'it': 'di Meia', 'es': 'de Meia', 'jp': 'メディアム'}}
ENTER = {'nightmare': {'fr': 'Entrer dans le cauchemar {w} ?', 'de': '{w} Alptraum betreten?', 'it': "Entrare nell'incubo {w}?",
                       'es': '¿Entrar en la pesadilla {w}?', 'jp': '{w}の悪夢に入るか？'},
         'dream': {'fr': 'Entrer dans le rêve {w} ?', 'de': '{w} Traum betreten?', 'it': 'Entrare nel sogno {w}?',
                   'es': '¿Entrar en el sueño {w}?', 'jp': '{w}の夢に入るか？'}}
DE_ENTER_TWINS = {'nightmare': 'Den Alptraum {w} betreten?', 'dream': 'Den Traum {w} betreten?'}
LOST = {'fr': "{who} est perdu dans un cauchemar, mais tu n'es pas prêt à y entrer. Il te faut : {need}.",
        'de': '{who} ist in einem Alptraum gefangen, aber Du bist noch nicht bereit, ihn zu betreten. Du brauchst: {need}.',
        'it': '{who} è perso in un incubo, ma non sei pronto per entrarvi. Ti serve: {need}.',
        'es': '{who} está perdido en una pesadilla, pero no estás preparado para entrar. Necesitas: {need}.',
        'jp': '{who}は悪夢にとらわれておる。だが、まだ入るときではない。必要なのは、{need}じゃ。'}
OR_AND = {'fr': (' ou ', ' et '), 'de': (' oder ', ' und '), 'it': (' o ', ' e '), 'es': (' o ', ' y '), 'jp': ('か', 'と')}
MOVED = {(10, 9): (10, 78, 'If you go to the basement')}   # (a line the base edits made from another line's last boxes)
MOVED_OWN = {(10, 9): {'jp': '{c}わしの家の地下に、宝が眠っておる。\\Aランプは、左上、右下、いちばん下の左、下のまん中、上のまん中、右上の順に灯すのじゃ。\\Aきっと、苦労にみあう物が手にはいるぞ。'}}   # (the JP line has no such boxes)
FEMALE = {'Elene', 'Meia', 'Bonaire'}
FEM = {'fr': ('est perdu ', 'est perdue '), 'it': ('è perso ', 'è persa '), 'es': ('está perdido ', 'está perdida ')}
ALIAS = {'Legendary Sword': 'Legend Sword'}
FIND_LANG = {(7, 0): {'de': 'legendäres Schwert', 'it': 'Spada della Leggenda', 'es': 'legendaria espada', 'jp': '伝説の剣'},
             (472, 81): {'de': 'Goldenen Falken'}}   # (the disc's own words for the item, where not its item name)
NAVA = {'fr': 'Il te faut {bomb} et {boots} pour entrer dans ma cachette.', 'de': 'Du brauchst {bomb} und {boots}, um mein Verlies zu betreten.',
        'it': 'Ti servono {bomb} e {boots} per entrare nella mia prigione.', 'es': 'Necesitas {bomb} y {boots} para entrar en mi torre.',
        'jp': 'わしの地下通路に入るには、{bomb}と{boots}が必要じゃ。'}


class Lang:
    def __init__(self, stock, lang):
        d = Path(stock) / f'text_{lang}'
        self.lang = lang
        self.etc = json.loads((d / 'etc.json').read_text(encoding='utf-8'))['etc']
        self.glob = json.loads((d / 'global_strings.json').read_text(encoding='utf-8'))

    def item(self, name, ids):
        i = ids.get(name)
        if i is None: return name                                  # (another player's item: its own name)
        if i in UPGRADES: return UPGRADES[i][self.lang]
        n = self.etc.get(str(512 + i), '').strip()
        return n or name

    def place(self, p):
        i = PLACE_IDS.get(p)
        if i is None: return p
        s = self.glob.get(str(i), '')
        s = CODE.sub('', s).strip()
        s = re.sub(r'^\d+|\d+$', '', s).strip()
        return s or p

    def where(self, prep, p):
        w = WHERE[self.lang][prep]
        f = w.get(p, w[''])
        return f.format(self.place(p)) if '{}' in f else f

    def hint(self, en, ids):
        """'X can be found in Y' / 'nothing of interest can be found in Y' / 'something useful lies in Y'."""
        m = re.match(r'^(.*?) (?:can be found|lies) (?:(in|near|inside) )?(.+)$', en)
        if not m: return en
        what, prep, p = m.groups(); prep = prep or 'in'
        if prep == 'inside': prep = 'in'
        w = self.where(prep, p)
        t = HINT[self.lang]
        if what == 'nothing of interest': return t[1].format(w=w)
        if what == 'something useful': return t[2].format(w=w)
        return t[0].format(item=self.item(what, ids), w=w)


# ------------------------------------------------------------------ format --
def full_width(s):
    """JP: ASCII as the disc's full-width characters (control codes kept)."""
    out, i = [], 0
    while i < len(s):
        m = CODE.match(s, i)
        if m: out.append(m.group(0)); i = m.end(); continue
        c = s[i]
        out.append('　' if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c); i += 1
    return ''.join(out)


def jp_format(s, width=16):
    """16 characters to a line, three lines to a box; the line's own breaks kept."""
    s = full_width(s); out, n, lines, i = [], 0, 0, 0
    while i < len(s):
        m = CODE.match(s, i)
        if m:
            c = m.group(0); i = m.end()
            if c == B + 'N': lines += 1; n = 0
            elif c == B + 'A': lines = 0; n = 0
            out.append(c); continue
        if n >= width and not (s[i] in '。、！？…』」）ー' and n < width + 2):   # (no line starts with these)
            if lines < 2: out.append(B + 'N'); lines += 1
            else: out.append(B + 'A'); lines = 0
            n = 0
        out.append(s[i]); n += 1; i += 1
    return ''.join(out)


def fmt(lang, s, format_text):
    if lang == 'jp': return jp_format(s)
    if lang == 'fr':                                       # (French: no line starts with ? ! : ;)
        for p in '?!:;': s = s.replace(' ' + p, '\x00' + p)
        return format_text(s).replace('\x00', ' ')
    return format_text(s)


def before_choice(s, add):
    """add at the end of a line, before its closing choice codes (\\0100\\Y ...)."""
    m = re.search(r'((?:\\[0-9]{4})?\\Y)$', s)
    return s[:m.start()] + add + s[m.start():] if m else s + add


# ------------------------------------------------------------------ apply --
def apply(files, spoiler, T, items, placed, gold, format_text, us_text, new_lines):
    """us_text: {(map, str): every US line the build changed or added}; new_lines: {(map, str): (kind, ...)} the lines
    the build added (septimus, gate, nava).  Written to the seed's text_<lang>/maps.json."""
    ids = {x['name']: i for i, x in enumerate(items) if x.get('name')}
    hints = {T['hint_ids'][k]: v for k, v in spoiler.get('hints', {}).items() if k in T['hint_ids']}
    stock = files.stock
    us_names = json.loads((stock / 'text' / 'etc_usa.json').read_text(encoding='utf-8'))['items']
    us_ids = {v['name']: int(k) for k, v in us_names.items() if v.get('name')}
    for lang in LANGS:
        if not (stock / f'text_{lang}' / 'maps.json').exists(): continue
        doc = files.doc(f'text_{lang}/maps.json')
        if lang == 'en_eu':
            for (m, k), t in us_text.items(): doc.setdefault(str(m), {})[str(k)] = t
            continue
        L = Lang(stock, lang)
        def put(m, k, t): doc.setdefault(str(m), {})[str(k)] = t
        def disc(m, k): return doc.get(str(m), {}).get(str(k), '')
        for op in T['text_ops']:
            m, k = op['map'], op['str']
            if (m, k) not in us_text: continue
            parts = op['parts']; head = parts[0][:2] if isinstance(parts[0], str) and parts[0].startswith(B) else ''
            names = [p for p in parts if isinstance(p, list) and p[0] == 'name']
            prices = [p for p in parts if isinstance(p, list) and p[0] == 'price']
            hint_parts = [p for p in parts if isinstance(p, list) and p[0] == 'hint']
            if 'find' in op and us_text[(m, k)].startswith(B + 'BReceived') and names:
                put(m, k, fmt(lang, B + 'B' + RECEIVED[lang].format(item=L.item(placed[names[0][1]], ids)), format_text))
            elif 'find' in op:                                   # (a reward: the disc's line, the item's name replaced)
                old = re.sub(r'^(the|a|an|fantastic)\s+', '', CODE.sub(' ', op['find']).strip(' !.'), flags=re.I)
                old = ALIAS.get(old, old); new = placed.get(names[0][1]) if names else None
                own = disc(m, k); oldn = FIND_LANG.get((m, k), {}).get(lang) or (L.item(old, ids) if old in ids else '')
                if own and oldn and new:
                    pat = re.compile(r'(?:\s|\\N)+'.join(re.escape(w) for w in oldn.split()), re.I)
                    if pat.search(own): put(m, k, pat.sub(lambda _: L.item(new, ids), own, count=1))
            elif prices:
                item = L.item(placed[names[0][1]], ids); price = str(gold.get(placed[names[0][1]], 0))
                t = SHOP.get(f'{lang}{head}', SHOP[lang]).format(item=item, price=price)
                put(m, k, fmt(lang, head + t, format_text) + B + '0100' + B + 'Y')
            elif m == 394:
                g = GAMES[k][lang]
                rows = [REWARDS[lang].format(g=g)] + [('・' if lang == 'jp' else '- ') + L.item(placed[p[1]], ids) for p in names]
                t = head + (B + 'N').join(rows)
                put(m, k, full_width(t) if lang == 'jp' else t)
            elif names and isinstance(parts[0], str) and parts[0].startswith(B + 'BReceived'):
                t = RECEIVED[lang].format(item=L.item(placed[names[0][1]], ids))
                put(m, k, fmt(lang, B + 'B' + t, format_text))
            elif hint_parts:
                h = hints.get(hint_parts[0][1], '')
                own = disc(m, k)
                if h and own:
                    add = HINT_ADD[lang].format(hint=L.hint(h, ids))
                    put(m, k, before_choice(own, B + 'A' + fmt(lang, add, format_text)))
            elif (m, k) in FIXED:
                put(m, k, FIXED[(m, k)][lang].format(c=head))
            elif (m, k) in SHORTENED:
                own = disc(m, k); boxes = own.split(B + 'A')
                if len(boxes) > 2: put(m, k, (B + 'A').join(boxes[:2]) + ('…' if lang != 'jp' else '…'))
        for (m, k), t in us_text.items():                          # lines the base edits wrote
            if t == '' and disc(m, k): put(m, k, '')
            elif lang in MOVED_OWN.get((m, k), {}):
                put(m, k, fmt(lang, MOVED_OWN[(m, k)][lang].format(c=t[:2]), format_text))
            elif (m, k) in MOVED:
                fm, fk, start = MOVED[(m, k)]
                us0 = json.loads((stock / f'maps/{fm:03d}/data.json').read_text(encoding='utf-8'))['strings'].get(str(fk), '').split(B + 'A')
                i = next((n for n, b in enumerate(us0) if start in b), None); boxes = disc(fm, fk).split(B + 'A')
                if i is not None and len(boxes) > i: put(m, k, t[:2] + (B + 'A').join(boxes[i:]).lstrip())
            elif m == 241:
                plain = re.sub(r'\\[NA]', ' ', t).replace('  ', ' ')
                e = re.match(r"^Enter (the twins'|\w+)(?:'s|')? (nightmare|dream)\?(\\0990\\Y)$", plain)
                g = re.match(r"^(\w+) is lost in a nightmare, but you are not ready to enter it\. You need (.+)\.$", plain)
                if e:
                    who = WHO.get(e.group(1)); kind = e.group(2)
                    if who:
                        f = DE_ENTER_TWINS[kind] if lang == 'de' and e.group(1) == "the twins'" else ENTER[kind][lang]
                        put(m, k, fmt(lang, f.format(w=who[lang]), format_text) + e.group(3))
                elif g and (m, k) not in new_lines:
                    o, a = OR_AND[lang]
                    parts = re.split(r', | and ', g.group(2))
                    names_l = [o.join(L.item(x, ids) for x in p.split(' or ')) for p in parts]
                    need = ', '.join(names_l[:-1]) + a + names_l[-1] if len(names_l) > 1 else names_l[0]
                    if lang == 'jp': need = need.replace(', ', '、')
                    who = g.group(1) if lang != 'jp' else WHO.get(g.group(1), {}).get('jp', g.group(1))
                    line = LOST[lang].format(who=who, need=need)
                    if g.group(1) in FEMALE and lang in FEM: line = line.replace(*FEM[lang], 1)
                    put(m, k, fmt(lang, line, format_text))
        for (m, k), kind in new_lines.items():                     # the randomizer's own new lines
            what = kind[0]
            if what == 'septimus':
                put(m, k, fmt(lang, SEPTIMUS[lang].format(c=B + 'C', hint=L.hint(kind[1], ids)), format_text))
            elif what == 'gate':
                put(m, k, fmt(lang, GATES[kind[1]][lang].format(**{n: L.item(i, ids) for n, i in GATE_ITEMS.items()}), format_text))
            elif what == 'nava':
                put(m, k, fmt(lang, B + 'C' + NAVA[lang].format(bomb=L.item('Bomb', ids), boots=L.item('Merman Boots', ids)), format_text))


# ------------------------------------------------------------------ Crowd Control --
# game/ccbridge.py: the CC script's own words (Alundra_CC_Bizhawk.lua) in each language; a key ending in ' '
# keeps what follows it (the amount)
CC_TEXT = {
    'Invincibility': {'en_eu': 'Invincibility', 'fr': 'Invincibilité', 'de': 'Unverwundbar', 'it': 'Invincibilità', 'es': 'Invencible', 'jp': '無敵'},
    'No I Frames': {'en_eu': 'No I Frames', 'fr': "Pas d'invulnérabilité", 'de': 'Keine Schonzeit', 'it': 'Niente invulnerabilità', 'es': 'Sin invulnerabilidad', 'jp': '無敵時間なし'},
    'No Jump': {'en_eu': 'No Jump', 'fr': 'Pas de saut', 'de': 'Kein Springen', 'it': 'Niente salto', 'es': 'Sin salto', 'jp': 'ジャンプ不可'},
    'Slow Motion': {'en_eu': 'Slow Motion', 'fr': 'Ralenti', 'de': 'Zeitlupe', 'it': 'Rallentatore', 'es': 'Cámara lenta', 'jp': 'スロー'},
    'Weapon Locked': {'en_eu': 'Weapon Locked', 'fr': 'Arme bloquée', 'de': 'Waffe gesperrt', 'it': 'Arma bloccata', 'es': 'Arma bloqueada', 'jp': '武器固定'},
    'Item Locked': {'en_eu': 'Item Locked', 'fr': 'Objet bloqué', 'de': 'Gegenstand gesperrt', 'it': 'Oggetto bloccato', 'es': 'Objeto bloqueado', 'jp': '道具固定'},
    'Weapon & Item Locked': {'en_eu': 'Weapon & Item Locked', 'fr': 'Arme et objet bloqués', 'de': 'Waffe & Gegenstand gesperrt', 'it': 'Arma e oggetto bloccati', 'es': 'Arma y objeto bloqueados', 'jp': '武器と道具固定'},
    'Poisoned': {'en_eu': 'Poisoned', 'fr': 'Empoisonné', 'de': 'Vergiftet', 'it': 'Avvelenato', 'es': 'Envenenado', 'jp': '毒'},
    'Regen': {'en_eu': 'Regen', 'fr': 'Régénération', 'de': 'Regeneration', 'it': 'Rigenerazione', 'es': 'Regeneración', 'jp': '回復'},
    'Regen & Poison': {'en_eu': 'Regen & Poison', 'fr': 'Régénération et poison', 'de': 'Regeneration & Gift', 'it': 'Rigenerazione e veleno', 'es': 'Regeneración y veneno', 'jp': '回復と毒'},
    'Cannot Swap (no weapon)': {'en_eu': 'Cannot Swap (no weapon)', 'fr': "Échange impossible (pas d'arme)", 'de': 'Kein Wechsel (keine Waffe)', 'it': 'Cambio impossibile (niente arma)', 'es': 'No se puede cambiar (sin arma)', 'jp': '交換できない（武器なし）'},
    'Cannot Swap (no item)': {'en_eu': 'Cannot Swap (no item)', 'fr': "Échange impossible (pas d'objet)", 'de': 'Kein Wechsel (kein Gegenstand)', 'it': 'Cambio impossibile (niente oggetto)', 'es': 'No se puede cambiar (sin objeto)', 'jp': '交換できない（道具なし）'},
    'Cannot Force (no item)': {'en_eu': 'Cannot Force (no item)', 'fr': "Forçage impossible (pas d'objet)", 'de': 'Kein Erzwingen (kein Gegenstand)', 'it': 'Impossibile forzare (niente oggetto)', 'es': 'No se puede forzar (sin objeto)', 'jp': '強制できない（道具なし）'},
    'Cannot Spawn (no enemies)': {'en_eu': 'Cannot Spawn (no enemies)', 'fr': "Apparition impossible (pas d'ennemis)", 'de': 'Kein Erscheinen (keine Gegner)', 'it': 'Impossibile evocare (niente nemici)', 'es': 'No se puede invocar (sin enemigos)', 'jp': '出現できない（敵なし）'},
    'Cannot Spawn (no room)': {'en_eu': 'Cannot Spawn (no room)', 'fr': 'Apparition impossible (pas de place)', 'de': 'Kein Erscheinen (kein Platz)', 'it': 'Impossibile evocare (niente spazio)', 'es': 'No se puede invocar (sin espacio)', 'jp': '出現できない（場所なし）'},
    'Cannot Spawn (not here)': {'en_eu': 'Cannot Spawn (not here)', 'fr': 'Apparition impossible (absent ici)', 'de': 'Kein Erscheinen (nicht hier)', 'it': 'Impossibile evocare (non qui)', 'es': 'No se puede invocar (no aquí)', 'jp': '出現できない（ここにいない）'},
    'Item Returned': {'en_eu': 'Item Returned', 'fr': 'Objet rendu', 'de': 'Gegenstand zurück', 'it': 'Oggetto restituito', 'es': 'Objeto devuelto', 'jp': '道具が戻った'},
    'Herbs Obtained! Amount: ': {'en_eu': 'Herbs Obtained! Amount: ', 'fr': 'Herbes obtenues ! Quantité : ', 'de': 'Kräuter erhalten! Anzahl: ', 'it': 'Erbe ottenute! Quantità: ', 'es': '¡Hierbas obtenidas! Cantidad: ', 'jp': '薬草を手にいれた！　数：'},
    'Herbs Lost! Amount: ': {'en_eu': 'Herbs Lost! Amount: ', 'fr': 'Herbes perdues ! Quantité : ', 'de': 'Kräuter verloren! Anzahl: ', 'it': 'Erbe perse! Quantità: ', 'es': '¡Hierbas perdidas! Cantidad: ', 'jp': '薬草を失った！　数：'},
    'Herbs is already at maximum!': {'en_eu': 'Herbs is already at maximum!', 'fr': 'Herbes déjà au maximum !', 'de': 'Kräuter schon am Maximum!', 'it': 'Erbe già al massimo!', 'es': '¡Hierbas ya al máximo!', 'jp': '薬草はもう最大だ！'},
    'Herbs is already at Zero!': {'en_eu': 'Herbs is already at Zero!', 'fr': 'Plus aucune herbe !', 'de': 'Keine Kräuter mehr!', 'it': 'Erbe già a zero!', 'es': '¡No quedan hierbas!', 'jp': '薬草はもうない！'},
}


def cc_text(t, lang):
    """A CC script line in this language (the game's lang: 'us', 'jp' or a European disc's); other lines as they are."""
    lang = {'us': 'en_eu'}.get(lang, lang)
    for k, v in CC_TEXT.items():
        if t == k or (k.endswith(' ') and t.startswith(k)): return v.get(lang, k) + t[len(k):]
    return t
