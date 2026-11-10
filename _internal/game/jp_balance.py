"""JP (original Japanese) game balance as a mod option.

Source: Dinopony Alundra randomizer (MIT), src/assets/patched_balance.bin,
used by its "originalGameBalance" option: "the game balance from the japanese
version is used instead of the balance edited by Working Designs for the US
version. This mostly changes enemies HP and damage." 107 of 512 entries
differ from US v1.1 (e.g. Slime HP 9 -> 6, Melzas HP 68 -> 60).

Turning the option on replaces the mod's BALANCE.BIN base with the JP file;
turning it off restores the opened disc's own balance. Either way, balance
values you edited are replaced, so the editor warns first.
"""
import hashlib
from copy import deepcopy
from pathlib import Path
from enemy_definition import BalanceSession, BalanceTable

ROOT = Path(__file__).resolve().parents[1]
JP_BALANCE_PATH = ROOT / 'extras/game edits/src/assets/patched_balance.bin'
JP_BALANCE_SHA256 = 'ef523c1e60cb0a30c5b42b266c2557a24baa454011343ac8a66e2758b8739b68'
BALANCE = 'DATA/BALANCE.BIN'
US_BALANCE_SHA256 = '6c3f125fc7a8709e75539df9b62f1cbeeec6bc48e7140c2e6d1575d4c642a9b2'  # stock US v1.1
US_BALANCE_PATH = ROOT / 'private-inputs/disc/DATA/BALANCE.BIN'


def us_balance_bytes(disc=None):
    """Stock US v1.1 balance: the opened disc's own file when it is stock,
    otherwise the extracted stock file in private-inputs."""
    if disc is not None and hashlib.sha256(bytes(disc)).hexdigest() == US_BALANCE_SHA256:
        return bytes(disc)
    if US_BALANCE_PATH.is_file():
        data = US_BALANCE_PATH.read_bytes()
        if hashlib.sha256(data).hexdigest() == US_BALANCE_SHA256:
            return data
    raise ValueError('The stock US balance is not available: this disc\'s BALANCE.BIN is modified and '
                     'private-inputs/disc/DATA/BALANCE.BIN is missing or not the stock US v1.1 file')


def balance_mode(options):
    """'us', 'jp' or None (the disc's own) from saved mod options."""
    options = options or {}
    mode = options.get('balance')
    if mode in ('us', 'jp'):
        return mode
    return 'jp' if options.get('jp_balance') else None


def balance_bytes(mode, disc):
    if mode == 'jp':
        return jp_balance_bytes()
    if mode == 'us':
        return us_balance_bytes(disc)
    return bytes(disc)


def jp_balance_bytes():
    if not JP_BALANCE_PATH.is_file():
        raise ValueError('JP balance file is missing: extras/game edits/src/assets/patched_balance.bin')
    data = JP_BALANCE_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != JP_BALANCE_SHA256:
        raise ValueError('JP balance file differs from the known randomizer asset')
    if len(data) > 0x3000 or len(BalanceTable(data).chains) != 512:
        raise ValueError('JP balance file is not a valid 512-entry table')
    return data


def _records(data):
    table = BalanceTable(data)
    out = []
    for entry, chain in enumerate(table.chains):
        out.append([{k: v for k, v in table.record(entry, tier).items() if k not in ('offset', 'alias_entries')}
                    for tier in range(len(chain))])
    return out


def edited_entries(session):
    """Balance entries whose values differ from the session's own base."""
    if session is None or bytes(session.data) == bytes(session.original):
        return []
    before, after = _records(session.original), _records(session.data)
    return [entry for entry, (a, b) in enumerate(zip(before, after)) if a != b]


def disc_balance(session):
    """The opened disc's own balance, even after JP balance was switched on."""
    return bytes(getattr(session, 'disc_original', session.original))


def make_session(base, disc_original):
    """New BALANCE session on `base`; remembers the disc's file for building."""
    session = BalanceSession(base, verify=False)
    if bytes(base) != bytes(disc_original):
        session.disc_original = bytes(disc_original)
    return session


def refresh_definitions(database, session):
    """Point every source class at the new balance and reload its stats."""
    table = BalanceTable(session.data)
    digest = hashlib.sha256(bytes(session.original)).hexdigest()
    changed = []
    for row in database.definitions:
        source = row.get('source', {})
        entry = source.get('balance_entry')
        if row.get('clone_of') or type(entry) is not int or not 0 <= entry < len(table.chains):
            continue
        tiers = [table.record(entry, tier) for tier in range(len(table.chains[entry]))]
        data = row['data']
        before = deepcopy(data)
        source['balance_sha256'] = digest
        source['tier_offsets'] = [record['offset'] for record in tiers]
        data['balance_tiers'] = [{'threshold': r['level'], 'max_hp': r['max_hp'],
                                  'damage_responses_raw': r['damage_responses'], 'attacks_raw': r['attacks']}
                                 for r in tiers]
        data['max_hp'] = tiers[0]['max_hp']
        data['attacks'] = deepcopy(tiers[0]['attacks'])
        if row['kind'] in ('enemy', 'boss'):
            data['damage_responses_raw'] = list(tiers[0]['damage_responses'])
        source['native_data_baseline'] = deepcopy(data)
        if data != before:
            changed.append(row['id'])
    return changed


def switch_balance(extra_files, database, enable):
    """Swap the mod's BALANCE base: 'us', 'jp' (or True), or the disc's own (False/None).

    Returns (new session, number of classes whose stats changed)."""
    current = extra_files.get(BALANCE)
    if current is None:
        raise ValueError('Open the game disc first so its balance data is available')
    disc = disc_balance(current)
    mode = 'jp' if enable is True else enable if enable in ('us', 'jp') else None
    base = balance_bytes(mode, disc)
    new = make_session(base, disc)
    extra_files[BALANCE] = new
    return new, len(refresh_definitions(database, new))
