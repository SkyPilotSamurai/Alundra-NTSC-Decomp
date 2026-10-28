"""Built-in sprite programs (the A/C/D/E handlers a sprite header names when the map
record gives no script for that slot), the entity life cycle and item drops.
Ported from the MIT xcasadio AlundraEngine (EntityManager.UpdateEntitiesEvents
0x800386D0, FunctionTypeA/C/D/E, GameEngine.DestroyEntity 0x8003A59C,
SpawnEntityContents, FunctionTypeC.FUN_8007C174 items).

Life cycle each frame (normal entities): DeactivateOnImpact (0x10) and blocked or on
the ground, DeactivateOnHit (0x20) and it hit something, DeactivateOnAnimationEnd
(0x40) and its animation ended -> deactivated (E runs every frame from then on);
else D (touch) when an attack reached it last frame, else C (tick)."""
import json, random
from gamerng import rnd as _rnd          # the game's generator (seed 0x8009AF70)
from combat import direction_to

ONE = 0x10000
try:                                     # ported programs that passed tools/us_decomp/check_ai.py
    from pathlib import Path as _P
    VERIFIED = set(json.loads((_P(__file__).resolve().parent / 'engine' / 'ai_verified.json').read_text()))
except Exception:
    VERIFIED = None
BUILTIN_TABLES = {'A': 0x800C699C, 'C': 0x800C6D9C, 'D': 0x800C719C, 'E': 0x800C759C, 'F': 0x800C799C}
IMPACT, ON_HIT, ON_ANIM_END, COLLIDABLE = 0x10, 0x20, 0x40, 0x80
HITS_B, HITS_A = 0x2, 0x4


class SpriteAI:
    def __init__(self, game, assets):
        self.g = game
        f = assets / 'items.json'
        it = json.loads(f.read_text()) if f.exists() else {'random': [0] * 256, 'props': []}
        self.random_table = it['random']; self.props = it['props']

    # -- contents ----------------------------------------------------------------
    def choose(self, cid):
        """ChooseRandomlyAnItem."""
        while 0 <= cid < 0x100 and cid & 0x80:
            cid = self.random_table[(cid & 0x7F) * 16 + _rnd(16)]
        return cid if 0 < cid <= 0x61 else 0

    def init_contents(self, a, rec, header):
        """InitializeContents 0x80033154 (engine/drops.py): the record's contents unless its
        collection flag is set, else the sprite header's."""
        from engine import drops
        a.record = rec; a.header_contents = (header or {}).get('contents', 0)
        drops.init_contents(self.g, a)

    def prop(self, item, k):
        return self.props[item][k] if 0 <= item < len(self.props) else 0

    def drop_contents(self, a):
        """SpawnEntityContents 0x800332A8 (engine/drops.py)."""
        from engine import drops
        drops.spawn_contents(self.g, a)

    # -- destroy -------------------------------------------------------------------
    def destroy(self, a, effect=-1):
        """DestroyEntity 0x8003AEE4 (engine/drops.py): contents, status 4, the break effect."""
        from engine import drops
        drops.destroy_entity(self.g, a, effect)

    # -- the per-frame trigger ------------------------------------------------------
    def builtin(self, a, slot):
        return 0 if (a.programs.get(slot, 0) & 0x7F) else (getattr(a, 'sprite_programs', {}) or {}).get(slot, 0)

    def has(self, a, slot):
        n = self.builtin(a, slot)
        return (n in HANDLERS.get(slot, {}) or self.ported(slot, n) is not None) and not (a.programs.get(slot, 0) & 0x7F)

    def ported(self, slot, n):
        """The faithful port (engine/ai_*.py) of built-in program n of a slot, if done:
        0x80039198 calls (*(table[action]))[Entity.builtin[action]](entity)."""
        t = BUILTIN_TABLES.get(slot)
        if t is None or not (0 <= n < 256): return None
        from engine import rodata, calls
        a = rodata.u32(t + 4 * n)
        if VERIFIED is not None and f'{a:08X}' not in VERIFIED: return None    # not checked against the game yet
        return calls.resolve(a)

    def run(self, a, slot):
        n = self.builtin(a, slot)
        if not (a.programs.get(slot, 0) & 0x7F):
            f = self.ported(slot, n)
            if f is not None: f(self.g, a); return True
        fn = HANDLERS.get(slot, {}).get(n)
        if fn is None and slot == 'C' and not (a.programs.get('C', 0) & 0x7F) and n:
            fn = c_fallback                                   # tick AI not ported yet
        if fn is None and slot == 'E' and not (a.programs.get('E', 0) & 0x7F):
            fn = e_destroy                                    # E handler not ported yet (most destroy)
        if fn is None or (a.programs.get(slot, 0) & 0x7F): return False
        fn(self, a); return True

    def lifecycle(self, a):
        """Returns 'E' when the entity is (now) deactivated, else None."""
        if getattr(a, 'status', 'normal') == 'deactivated': return 'E'
        f = a.flags
        if (f & IMPACT and (a.force_adjusted or a.on_ground)) or (f & ON_HIT and a.hits) or \
           (f & ON_ANIM_END and a.anim.done):
            a.status = 'deactivated'; return 'E'
        return None


# --------------------------------------------------------------------------- helpers
def face_away(ai, a):
    p = ai.g.player
    a.target_dir = direction_to(a.px - p.px, a.py - p.py)


def hit_common(ai, a, anim):
    """HitCommon: life by the balance rules (Bytes[3] = 1 when it dies), hurt
    animation, turned away from Alundra."""
    if ai.g.combat.damage(a, a.balance['responses'] if a.balance else [0x80] * 11): a.bytes[3] = 1
    a.target_anim = anim; face_away(ai, a)


def attack_kind(a):
    t = a.touching
    return (t.cur_attack[0] & 15) if t is not None and t.cur_attack else 0


# --------------------------------------------------------------------------- A: load
def a_set(n):
    def f(ai, a): a.target_anim = n
    return f


def a_random4(ai, a):
    a.target_anim = 4; a.ai[0] = _rnd(0x1F) + 0xB4


def a_zpos(ai, a): a.ai[0] = (a.pz >> 16) & 0xFFFF


def a_anim8_b3(ai, a): a.target_anim = 8; a.bytes[0] = 3


def a_rest_z(ai, a): a.rest_z = a.pz                      # SetCustomByteFromZPos (A20)


def a_byte_from_program(ai, a): a.bytes[1] = a.programs.get('C', 0) & 0xFF   # A19


def a_noop(ai, a): pass


def a_chest(ai, a):
    """FUN_80061BD4 (chests and placed items): an empty chest shows open (anim 1);
    a placed item whose flag is already set is gone."""
    if a.balance_index == 0x1E:
        if not getattr(a, 'contents_item', 0): a.target_anim = 1
        return
    if a.bytes[0] in (1, 2): return
    a.flags &= ~COLLIDABLE
    if a.contents_flag and ai.g.flag(a.contents_flag):
        ai.destroy(a, 0); return
    a.item_flag = a.contents_flag; a.item_state = 0; a.delay = -1; a.bounce = 0


# --------------------------------------------------------------------------- C: tick
def c_item(ai, a):
    """FUN_8007C174 (dropped / placed items): bounce to rest, blink for the last 120
    frames, vanish after 600 (timed items); touching Alundra collects it."""
    g = ai.g; p = g.player; it = a.balance_index - 0x1E
    if a.bytes[0] == 2: return                                      # chest-opening sequence: not ported
    if a.on_ground and a.bounce:
        v = (a.bounce * 0xC) >> 4
        a.bounce = 0 if v <= (g.world.gravity << 8) else v
        a.fz = a.bounce
    if a.delay > 0:
        a.delay -= 1
        if a.delay == 0: ai.destroy(a, 0); return
        if a.delay == 0x78: a.damaged_tick = 0x78
    if a.item_state == 0:
        if a.fz <= 0: a.item_state = 1
        return
    if a.item_state != 1 or g.dialogue is not None: return
    if not (_near(a.mpx, a.size[0], p.mpx, p.size[0]) and _near(a.mpy, a.size[1], p.mpy, p.size[1])
            and _near(a.mpz, a.size[2], p.mpz, p.size[2])): return
    g.collect(it)
    if a.item_flag: g.set_flag(a.item_flag, True)
    snd = ai.prop(it, 1)
    if snd: g.sound(snd)
    ai.destroy(a, 0)


def _near(a, asz, b, bsz):
    d = a - b
    return (d < bsz + 1) if d >= 0 else (b - a < asz + 1)


def c_none(ai, a): pass


SCRIPT_ANIMS = [0, 3, 1, 4, 0]           # g_scriptAnimationTable(2): throw standing, moving, from a jump


def c_carried(ai, a):
    """AI_FUN_8006B848 (pots, crates, rocks): while Alundra holds it nothing happens;
    once he lets go (Flags2: -1 dropped, 1-3 thrown) it starts its flight animation, can
    no longer be stood on and breaks on impact or when it hits something."""
    if a.platform is None: return
    if a.flags2 == 0: a.target_anim = 0; return
    a.target_anim = 3 if a.flags2 == -1 else SCRIPT_ANIMS[a.flags2]
    a.flags2 = 0
    if getattr(a.platform, 'carried', None) is a: a.platform.carried = None
    a.platform = None
    a.flags = (a.flags | IMPACT | ON_HIT) & ~COLLIDABLE


def c_liftable(ai, a):
    """AI_FUN_80066984 (barrels, stones, liftable items): like c_carried while held;
    when free and not resting it settles on landing (sound 0x18)."""
    if a.platform is not None:
        if a.flags2 == 0: return
        if a.flags2 == -1:
            a.target_anim = 3
            if ai.builtin(a, 'E') == 2: a.flags = (a.flags & ~COLLIDABLE) | IMPACT
        else:
            a.target_anim = SCRIPT_ANIMS[a.flags2]
        a.flags2 = 0
        if getattr(a.platform, 'carried', None) is a: a.platform.carried = None
        a.platform = None
        return
    if a.target_anim != 0 and not a.force_adjusted and (a.on_ground or a.hits):
        ai.g.sound(0x18); a.target_anim = 0


def c_fallback(ai, a):
    """Stand-in for a tick AI that is not ported yet: the common ending every enemy AI
    shares (e.g. AI_UpdateEntityAI_6_2 case 5): when the hurt animation has played and the
    hit was fatal (Bytes[3]), deactivate at the end of the animation; else back to idle."""
    if a.bytes[3] and a.anim.done:
        a.flags |= ON_ANIM_END
    elif a.anim.done and a.target_anim != 0:
        a.target_anim = 0


# --------------------------------------------------------------------------- D: touch
def d_hit(anim):
    def f(ai, a): hit_common(ai, a, anim)
    return f


def d_hit_sound(ai, a):
    hit_common(ai, a, 6)
    if a.balance_index - 0x1C4 in (0, 1): ai.g.sound(0x41)


def d_hit4(ai, a):
    if ai.g.combat.damage(a, a.balance['responses']): a.bytes[3] = 1
    a.target_anim = 4; face_away(ai, a)


def d_chance(base_anim, special_index, special_anim, chance):
    """Hurt, but some sprites dodge melee hits (types 1-3) by chance."""
    def f(ai, a):
        face_away(ai, a)
        if attack_kind(a) - 1 < 3 and a.balance_index == special_index and a.target_anim < 2 \
                and _rnd(100) > chance:
            a.target_anim = special_anim; return
        if ai.g.combat.damage(a, a.balance['responses']): a.bytes[3] = 1
        a.target_anim = base_anim
    return f


def d_flail_break(step):
    """Only the flail (hammer, type 2) breaks it."""
    def f(ai, a):
        if attack_kind(a) == 2:
            a.target_anim = (a.target_anim + 1) if step else 2
            a.flags |= ON_ANIM_END
    return f


def d_fire_ignite(ai, a):
    if attack_kind(a) == 6:
        a.target_anim = 1
        a.flags = (a.flags | HITS_B | HITS_A | ON_ANIM_END) & ~COLLIDABLE


def d_turtle(ai, a):
    if a.balance_index in (0x1B5, 0x1B9) and 4 <= a.target_anim < 7:
        a.target_anim = 9; a.ai[1] = 0x78
    else:
        if ai.g.combat.damage(a, a.balance['responses']): a.bytes[3] = 1
        a.target_anim = 7
    face_away(ai, a)


def d_lizard(ai, a):
    face_away(ai, a)
    if attack_kind(a) - 1 < 3:
        if a.balance_index == 0x16A and (a.target_anim < 2 or a.target_anim == 0xD):
            a.target_anim = 0xC; return
        if a.balance_index == 0x16D and a.target_anim < 2 and _rnd(100) > 0x31:
            a.target_anim = 10; return
    if ai.g.combat.damage(a, a.balance['responses']): a.bytes[3] = 1
    a.target_anim = 7


# --------------------------------------------------------------------------- E: deactivated
def e_destroy(ai, a): ai.destroy(a, -1)


def e_break(anim):
    """Plays its break animation once, then is destroyed (pots, crates, spores...)."""
    def f(ai, a):
        if (a.target_anim == anim and a.anim.done) or getattr(a, 'vram_and', 0) & 4:
            ai.destroy(a, -1)
        else:
            pass
            a.target_anim = anim
            a.flags = (a.flags & ~(IMPACT | ON_HIT)) | ON_ANIM_END
    return f


def e_sound_destroy(n):
    def f(ai, a): ai.g.sound(n); ai.destroy(a, -1)
    return f


def e_destroy_family(ai, a):
    """E11 FUN_8003A648 (bosses): everything it spawned goes with it."""
    for o in list(ai.g.actors):
        if o.alive and o.parent is a: e_destroy_family(ai, o)
    ai.destroy(a, -1)


def e_break_spawn(ai, a):
    """E20 AI_FUN_8007F6C8 (bombs, eggs...): break animation; at its end, unless it was
    stopped by sprite 0x187, release global sprite 0x0C (a falling hazard) and vanish."""
    if a.target_anim == 2 and a.anim.done:
        if a.bytes[0] == 0:
            e = ai.g.spawn_sprite(a, False, 0x0C, a.px, a.py, a.pz, a.target_dir)
            if e is not None:
                e.sprite_programs = {k: 0 for k in e.sprite_programs}
                e.target_anim = 3; e.flags = (e.flags & ~IMPACT) | HITS_B
        ai.destroy(a, -1); return
    pass
    a.target_anim = 2
    a.flags = (a.flags & ~(IMPACT | ON_HIT)) | ON_ANIM_END
    xc = getattr(a, 'x_collision', None)
    if xc is not None and getattr(xc, 'balance_index', -1) == 0x187: a.bytes[0] = 1


HANDLERS = {
    'A': {0: a_zpos, 1: a_set(2), 2: a_random4, 3: a_set(4), 4: a_set(9), 5: a_set(7), 6: a_set(3), 7: a_set(9),
          8: a_anim8_b3, 9: a_set(10), 10: a_set(6), 13: a_noop, 16: a_set(0), 17: a_set(0xE), 18: a_set(0xE),
          19: a_byte_from_program, 20: a_rest_z, 254: a_noop, 255: a_chest},
    'C': {0: c_none, 4: c_liftable, 23: c_carried, 24: c_none, 255: c_item},
    'D': {0: c_none, 1: d_hit(5), 2: d_lizard, 3: d_turtle, 4: c_none, 5: d_chance(5, 0x1A9, 0xB, 0x3B), 6: d_hit(6),
          8: d_hit(4), 9: d_hit(2), 10: d_hit_sound, 11: d_hit4, 12: d_chance(4, 0x152, 6, 0x45), 13: d_hit(3),
          17: d_hit(8), 19: d_hit(8), 31: d_flail_break(True), 33: d_flail_break(False), 34: d_fire_ignite},
    'E': {0: e_destroy, 1: e_destroy, 2: e_break(2), 3: e_break(1), 14: e_sound_destroy(0x2D), 15: e_sound_destroy(0x2E),
          11: e_destroy_family, 16: e_sound_destroy(0x2F), 18: e_sound_destroy(0xE1), 19: e_sound_destroy(0xE6),
          20: e_break_spawn},
}

# creature / enemy tick AIs
import enemy_ai as _enemy_ai
for _k, _f in _enemy_ai.HANDLERS.items(): HANDLERS['C'].setdefault(_k, _f)
