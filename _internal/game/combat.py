"""Combat as the game runs it (ported from the MIT xcasadio AlundraEngine, checked
against the US EXE tables).

* Every animation frame may carry an attack box (sprites' animations.json 'boxes').
  While it shows, the entity's current attack (balance record: attacks[anim + 1]) can
  hit any entity of a class it reaches (UpdateBalanceRecords 0x80039300):
  flags 0x02 hits class B (0x08, Alundra), 0x04 hits class A (0x01), 0x1000 hits
  class C (0x800).  A target that is not immune (0x80 response) gets TouchingEntity =
  the attacker (its D / touch program runs next frame) and 25 frames before it can be
  hit again; two puffs fly off the impact.
* Damage (0x8004464C): r = responses[(attribute & 15) - 1]; r & 0xC0 == 0 ->
  hp -= max(1, power * r >> 4) (power + the equipped items' power for attribute
  & 0x80), 0x40 -> killed outright, 0x80 -> nothing.
* Alundra's responses come from his best armour (17-20; else his own record) adjusted
  by the weapon's and ring's records (UpdateItemEffectState 0x800307E8).
* Records by balance level: the first record of the sprite's chain whose level is at
  least the map's balance level (0x80044550)."""
import json, random
from pathlib import Path

ONE = 0x10000
CLASS_A, HITS_B, HITS_A, CLASS_B, CLASS_C, HITS_C = 0x1, 0x2, 0x4, 0x8, 0x800, 0x1000
INVULNERABLE = 0x40

# 0x80028C1C: per weapon class {chargeable, ground anim, ..., jump anim, ..., charge anim, ...}
WEAPON_INIT = [
    [0, 16, 0, 0, 0, 20, 0, 0, 0, 0, 0, 0, 0], [1, 63, 0, 0, 0, 65, 0, 0, 0, 24, 27, 20, 0],
    [1, 68, 0, 0, 0, 70, 0, 0, 0, 24, 28, 20, 0], [1, 73, 0, 0, 0, 75, 0, 0, 0, 24, 29, 20, 0],
    [1, 17, 11, 10, 32, 21, 11, 10, 32, 17, 12, 10, 32], [1, 17, 14, 10, 32, 21, 14, 10, 32, 17, 15, 10, 32],
    [0, 18, 0, 0, 0, 22, 0, 0, 0, 0, 0, 0, 0], [1, 64, 0, 0, 0, 66, 0, 0, 0, 25, 0, 0, 0],
    [0, 19, 3, 8, 16, 23, 3, 0, 16, 0, 0, 0, 0], [1, 19, 4, 8, 16, 23, 4, 8, 16, 19, 7, 8, 8],
    [0] * 13, [0, 16, 0, 0, 0, 20, 0, 0, 0, 0, 0, 0, 0]]
# 0x80028BB8: weapon item -> weapon class
WEAPON_BY_ITEM = {1: 0, 2: 1, 3: 2, 4: 3, 5: 8, 6: 9, 7: 10, 8: 11, 9: 6, 10: 7, 14: 5, 16: 4}
ARMOURS = (20, 19, 18, 17)
RINGS = (56, 55, 54, 53, 52, 51)


def _half(v):
    """(a + b) / 2 as the game divides: toward zero."""
    return -((-v) >> 1) if v < 0 else v >> 1


class Combat:
    def __init__(self, assets):
        f = assets / 'balance.json'
        self.chains = json.loads(f.read_text()) if f.exists() else []
        self.level = 0
        import copy
        self.us = copy.deepcopy(self.chains)                 # the US / EU disc's values
        f = assets / 'balance_jp.json'
        if not f.exists(): f = Path(__file__).resolve().parent / 'balance_jp.json'   # (shipped with the code)
        self.jp = {int(k): v for k, v in json.loads(f.read_text())['chains'].items()} if f.exists() else {}
        self.mode = 'us'

    def set_balance(self, mode, actors=()):
        """Options > Balance: 'us' (the US and EU discs' BALANCE.BIN) or 'jp' (the Japanese
        release's: enemy and boss max HP, some attack powers and one damage response).  The
        records are changed in place, so entities already out get the new attacks; their life
        keeps its share of the new maximum."""
        import copy
        mode = 'jp' if mode == 'jp' else 'us'
        if mode == self.mode: return
        self.mode = mode
        for i, c in enumerate(self.chains):
            src = self.jp.get(i) if mode == 'jp' else None
            if src is None or len(src) != len(c): src = self.us[i]
            for r, v in zip(c, src):
                r['hp'] = v['hp']; r['responses'] = list(v['responses']); r['attacks'] = copy.deepcopy(v['attacks'])
        for a in actors:
            r = getattr(a, 'balance', None)
            if r is None or a is getattr(self, 'player', None): continue
            old = getattr(a, 'hp_max', 0); new = r['hp']
            if old == new: continue
            a.hp_max = new
            a.hp = new if a.hp >= old else max(1, a.hp * new // old) if old and a.hp > 0 else a.hp

    # -- records -------------------------------------------------------------
    def record(self, index, level=None):
        level = self.level if level is None else level
        if 0x1F <= index < 0x80: index = 0x1E
        if not 0 <= index < len(self.chains) or not self.chains[index]: return None
        for r in self.chains[index]:
            if r['level'] >= level: return r
        return self.chains[index][-1]

    def item_record(self, item):
        """GetItemDataPointer 0x800445C0: items use chain item + 0x1E directly."""
        i = item + 0x1E
        if not 0 <= i < len(self.chains) or not self.chains[i]: return None
        return next((r for r in self.chains[i] if r['level'] >= self.level), self.chains[i][-1])

    def attach(self, a, index):
        a.balance_index = index
        a.balance = self.record(index)
        a.hp = a.hp_max = a.balance['hp'] if a.balance else 0
        a.cur_attack = None; a.box = None
        a.touching = None; a.hits = 0; a.damaged_tick = 0; a.hit_tick = 0

    @staticmethod
    def attack_for(rec, anim):
        if not rec or not rec['attacks']: return None
        atk = rec['attacks']
        return atk[0] if anim + 1 >= len(atk) else atk[anim + 1]

    # -- per frame -----------------------------------------------------------
    def counters(self, actors):
        """UpdateEntitiesCounters 0x80038998 (after the programs ran)."""
        for a in actors:
            a.touching = None; a.hits = 0
            if a.damaged_tick: a.damaged_tick -= 1
            if a.hit_tick: a.hit_tick -= 1

    def animated(self, a, started, frame):
        """UpdateAnimation: a new animation picks its attack; each frame its box."""
        box = None
        if frame is not None and frame.get('collision', -1) not in (-1, None, 0xFFFF):
            b = a.anim.sprite.meta.get('boxes', {}).get(str(frame['collision'])) if a.anim.sprite else None
            if b: box = b
        a.box = box

    def resolve(self, actors, player_responses, on_hit=None):
        """UpdateBalanceRecords 0x80039300 (after physics)."""
        for e in actors:
            if e.box is None or not e.cur_attack or not e.cur_attack[0]: continue
            want = ((e.flags >> 2) & CLASS_A) | ((e.flags << 2) & CLASS_B)
            if e.flags & HITS_C: want |= CLASS_C
            if not want: continue
            ox, oy, oz, w, d, h = e.box
            hx, hy, hz = e.px + (ox << 16), e.py + (oy << 16), e.pz + (oz << 16)
            cw, cd, ch = (w << 16) - 1, (d << 16) - 1, (h << 16) - 1
            for o in actors:
                if o is e or o.hit_tick or o.damaged_tick or getattr(o, 'anim_flags', 0) & INVULNERABLE: continue
                if not o.flags & want: continue
                if not self._overlap(hx, cw, o.mpx, o.size[0]): continue
                if not self._overlap(hy, cd, o.mpy, o.size[1]): continue
                if not self._overlap(hz, ch, o.mpz, o.size[2]): continue
                kind = e.cur_attack[0] & 15
                resp = player_responses if o is self.player else (o.balance['responses'] if getattr(o, 'balance', None) else [0x80] * 11)
                val = (o.balance['hp'] if o.balance else 0) if kind == 0 else resp[kind - 1]
                if val & 0xC0 != 0x80: o.touching = e
                o.hit_tick = 0x19; e.hits += 1
                x = _half(max(hx, o.mpx) + min(hx + cw, o.mpx + o.size[0]))
                y = _half(max(hy, o.mpy) + min(hy + cd, o.mpy + o.size[1]))
                z = _half(max(hz, o.mpz) + min(hz + ch, o.mpz + o.size[2]))
                if on_hit: on_hit(e, o, kind, val, x, y, z)       # 0x80039C00: effects 4 / 5, then the poofs

    @staticmethod
    def _overlap(a_pos, a_size, b_pos, b_size):
        d = a_pos - b_pos
        if d > 0: return d < b_size + 1
        return b_pos - a_pos < a_size + 1

    # -- damage --------------------------------------------------------------
    def damage(self, target, responses, equip_power=0):
        """ComputeNewHp / ResolveBalanceTarget: returns True when the target dies."""
        atk = target.touching.cur_attack if target.touching is not None else None
        if not atk or not atk[0]: return target.hp == 0
        attr, power = atk
        if attr & 0x80 and target.touching is getattr(self, 'player', None) and getattr(self, 'equip_power_fn', None):
            equip_power = self.equip_power_fn(target.touching.anim.anim)
        r = responses[(attr & 15) - 1]
        if r & 0xC0 == 0:
            p = power + (equip_power if attr & 0x80 else 0)
            n = (p * r) >> 4
            if n == 0: n = 1; reduced = 1 < target.hp
            else: reduced = n < target.hp
            target.hp = target.hp - n if reduced else 0
        elif r & 0xC0 == 0x40:
            target.hp = 0
        return target.hp == 0

    def player_responses(self, inventory, weapon_item, ring_item):
        """UpdateItemEffectState 0x800307E8: armour (or Alundra's record) adjusted by the
        weapon's and the ring's records."""
        base = next((self.item_record(i) for i in ARMOURS if inventory.get(i)), None) or self.record(0)
        wa = self.item_record(weapon_item) if weapon_item else None
        rb = self.item_record(ring_item) if ring_item else None
        out = []
        for i in range(11):
            b = base['responses'][i] if base else 0
            va = wa['responses'][i] if wa else 0x10; vb = rb['responses'][i] if rb else 0x10
            fa, fb = va & 0xC0, vb & 0xC0
            if b & 0xC0 == 0x80 or fa == 0x80 or fb == 0x80: out.append(0x80); continue
            r = b
            if b & 0xC0:
                r = 0x10
                if fa:
                    r = 0x40
                    if fb: out.append(r); continue
                    r = 0x10
            if not fa: r = r - 0x10 + va
            if not fb: r = r - 0x10 + vb
            out.append(0x1F if r >= 0x20 else max(0, r))
        return out

    def equip_power(self, weapon_item, ring_item, armour_item, anim):
        """Power the equipped items add to an attack with attribute bit 0x80."""
        p = 0
        for it in (armour_item, weapon_item, ring_item):
            if it:
                a = self.attack_for(self.item_record(it), anim)
                if a: p += a[1]
        return p


# ScriptHelper.GetDirectionToTarget (EXE table 0x80028B34-ish): exact 32-direction lookup
_DIV = [15, 31, 63, 127, 255, 511, 1023, 2047, 4095, 8191, 16383, 32767, 65535, 131071, 262143, 524287, 1048575, 2097151, 4194303, 8388607, 16777215, 33554431, 67108863, 134217727, 268435455, 536870911, 1073741823, 2147483647, 4294967295]
_DIRS = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 4, 2, 2, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 8, 6, 4, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 8, 6, 5, 4, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 8, 7, 6, 5, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 8, 7, 6, 5, 5, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2, 8, 7, 6, 6, 5, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 8, 7, 7, 6, 5, 5, 4, 4, 4, 3, 3, 3, 3, 3, 2, 2, 8, 7, 7, 6, 6, 5, 5, 4, 4, 4, 3, 3, 3, 3, 3, 2, 8, 7, 7, 6, 6, 5, 5, 5, 4, 4, 4, 3, 3, 3, 3, 3, 8, 7, 7, 7, 6, 6, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 8, 8, 7, 7, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 8, 8, 7, 7, 6, 6, 6, 5, 5, 5, 4, 4, 4, 4, 4, 3, 8, 8, 7, 7, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4, 4, 8, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4, 8, 8, 7, 7, 7, 6, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4]


def direction_to(x, y):
    flip = 2 if y < 1 else 0
    if x < 0: flip += 1; x = -x
    if y < 0: y = -y
    g = max(x, y); k = 0
    while k < len(_DIV) - 1 and _DIV[k] < g: k += 1
    d = _DIRS[(y >> k) * 16 + (x >> k)]
    return ((8 - d) if flip == 1 else (0x18 - d) if flip == 2 else (8 + d) if flip == 3 else (0x18 + d)) & 31
