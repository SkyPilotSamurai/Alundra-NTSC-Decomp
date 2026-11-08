"""The entity system (spawning, destroying, the per-frame dispatch).  Routines not ported
yet call into the remake (Game) and are replayed from the original in the checks."""
from .registry import port
from . import layout as L
from . import calls
from .core import s32, next_seed, hi


@port(0x8003A860, ret='ptr', replay=True)
def spawn_warp_entity(g, parent, is_map, index, x, y, z, direction):
    """SpawnWarpEntity: a new entity of global (is_map 0) or map sprite `index`."""
    return g.spawn_sprite(parent, is_map, index, x, y, z, direction)


@port(0x8003AAE8, ret='ptr', replay=True)
def spawn_map_entity(g, logic, ref, forced):
    """SpawnMapEntity: the map's entity record ref (enabled) as a child of logic, when forced
    or when Alundra's square is inside its rectangle and its flags have 0x40; NULL otherwise
    (also with no free slot).  (The remake's Game.spawn makes the actor from the record.)"""
    recs = g.map.doc['entities']
    if not (0 <= ref < len(recs)) or not recs[ref]['enabled']: return None
    r = recs[ref]
    if not forced:
        p = g.player; tx, ty = int(p.wx // 24), int(p.wy // 16)
        x1, y1, x2, y2 = r['rect']
        if not (x1 <= tx <= x2 and y1 <= ty <= y2) or not r['flags'] & 0x40: return None
    e = g.spawn(ref)
    if e is None: return None
    e.parent = logic
    return e


@port(0x8003A964, ret='ptr', replay=True)
def spawn_entity_in_slot(g, slot_e, parent, is_map, index, x, y, z, direction):
    """SpawnEntityInSlot: the record at slot_e (whatever was there) is blanked and made the
    sprite index of this map (is_map) / the global one, at x, y, z facing direction
    (InitializeEntity with ref -1); NULL when the sprite has no record."""
    k = getattr(slot_e, 'slot', None)
    if k is None or not (0 <= k < L.ENT_COUNT): return None
    cat = (0x100 + index) if is_map else index
    from alundra_remake import Sprite, Actor, ASSETS, GLOBAL_HEADERS
    folder = g.map.sprite_folder(cat) if is_map else ASSETS / 'sprites' / 'global' / f'{cat:03d}'
    sp = Sprite.get(folder)
    if sp is None: return None
    old = g.slots[k]
    if old is not None:
        old.alive = False; old.estatus = 0
        if old in g.actors: g.actors.remove(old)
    a = Actor(sp, 0, 0, 0, direction); a.px, a.py = s32(x), s32(y)
    hdr = g.header(cat)
    if hdr:
        a.flags = hdr['flags']; a.set_hitbox(hdr['hitbox_offset'], hdr['hitbox_size'])
        a.sprite_programs = hdr['sprite_programs']; a.break_effect = hdr['break_effect']
    a.solid = bool(a.flags & 0x80); a.programs = {}; a.parent = parent; a.sprite_index = cat
    g.place(a, s32(z))
    g.combat.attach(a, cat)
    g.sprite_ai.init_contents(a, None, hdr)
    g.slots[k] = a; a.slot = k; a.estatus = 1
    a.frame_counter = 0                                  # (the blank record is copied in: counter 0,
    a._index = 0                                         # and the index word: InitializeEntity then
    g.slot_fc[k] = 0                                     # leaves the entity count alone, so the slot
    g.serial_counter += 1; a.serial = g.serial_counter   # is not counted this frame when it is past it)
    a.cur_anim = ~a.target_anim; g.animate(a)
    a.action = None if k <= g.sel_count else 'A'
    g.actors.append(a)
    return a


@port(0x8003B518, ret=True, replay=True)
def reset_to_record(g, e):
    """0x8003B518: an entity made from a map record is initialised again from it (same
    parent, sprite, record, catalogue and ref; the record's position and direction);
    0 when it has no record."""
    rec = getattr(e, 'record', None)
    if not rec: return 0
    from alundra_remake import Actor
    import vm as eventvm
    d = eventvm.CARDINAL[rec['flags'] & 3]
    a = g.make_actor(rec)
    keep = e.parent
    k = e.slot
    if e in g.actors: g.actors.remove(e)
    e.alive = False
    g.slots[k] = a; a.slot = k; a.estatus = 1; a.parent = keep
    a.frame_counter = e.frame_counter
    g.serial_counter += 1; a.serial = g.serial_counter
    a.cur_anim = ~a.target_anim; g.animate(a)
    a.action = None if k <= g.sel_count else 'A'
    g.actors.append(a)
    return 1


@port(0x8003CA78, ret='ptr', replay=True)
def spawn_sprite_effect(g, index, forced):
    """SpawnSpriteEffect 0x8003CA78: the map's effect record index as a live effect when forced
    or its flags have 0x40 (no area test here: the area test is 0x8003C3C8's, used by the
    initial spawn); NULL with no record or no free effect slot."""
    recs = getattr(g.effects, 'records', [])
    if not 0 <= index < len(recs): return None
    r = recs[index]
    if not forced and not r['flags'] & 0x40: return None
    return g.effects.spawn_record(index, True, None)


@port(0x80083394)
def boss_death(g, e):
    """0x80083394, the bosses' death (bytes[3] 1..3 while their AI calls this every frame):
    ai[1] counts down; every 8th frame sound 0x2E and a death puff (effect 0x1B) at a random
    point of the hit box; 1: at 0 the screen flashes red (0x1E frames, kept) and 2 starts with
    30 frames, meanwhile ai[5] counts down to short red flashes at random gaps (0x1E + 8 k);
    2: at 0 the flash fades over 0x1E frames, 3 starts; 3: at 0 bytes[3] = 4 (the AI's end)."""
    t = (e.ai[1] - 1) & 0xFFFF; e.ai[1] = t
    b3 = e.bytes[3]
    if b3 < 3 and not t & 7:
        calls.call(g, 0x8004A128, 0x2E)
        t1 = next_seed(g); t0 = next_seed(g); t4 = next_seed(g); t2 = next_seed(g)
        x = s32(e.mpx + ((hi(t1, (s32(e.sizex) >> 20) + 1) * 16 + hi(t0, 0x11)) << 16))
        y = s32(e.mpy + e.sizey)
        z = s32(e.mpz + ((hi(t4, (s32(e.sizez) >> 20) + 1) * 16 + hi(t2, 0x11)) << 16))
        calls.call(g, 0x8003C760, 0, 0x1B, 0, x, y, z)
    if b3 == 1:
        if e.ai[1] & 0xFFFF == 0:
            calls.call(g, 0x80083324, 0xFF0000, 0x1E, 1, 1)
            e.ai[1] = 0x1E; e.bytes[3] = b3 + 1
        else:
            v = (e.ai[5] - 1) & 0xFFFF; e.ai[5] = v
            if v == 0:
                calls.call(g, 0x80083324, 0xFF0000, 4, 0, 1)
                s = next_seed(g)
                e.ai[5] = (hi(s, 5) * 8 + 0x1E) & 0xFFFF
    elif b3 == 2:
        if e.ai[1] & 0xFFFF == 0:
            calls.call(g, 0x80083324, 0, 0x1E, 0, 0)
            e.ai[1] = 0x1E; e.bytes[3] = b3 + 1
    elif b3 == 3:
        if e.ai[1] & 0xFFFF == 0: e.bytes[3] = b3 + 1


@port(0x8004A7B4, mock_always=True)
def stop_sound(g, n):
    """StopSound: presentation only.  The remake hooks g.stop_sound."""
    f = getattr(g, 'stop_sound', None)
    if f is not None and not hasattr(g, 'ram'): f(n)


def destroy_entity(g, e, effect):
    """DestroyEntity 0x8003AEE4 (engine/drops.py)."""
    from . import drops
    return drops.destroy_entity(g, e, effect)


SEL_LIST = 0x8013D488        # Entity *[]: what select() found (callers walk it from the end)


def ent_addr(e):
    """The RAM address of an entity record (g_ent + slot * 0x294)."""
    return L.ENT_BASE + e.slot * L.ENT_SIZE


def _st123(e):
    s = e.estatus
    return ((s - 1) & 0xFFFFFFFF) < 2 or s == 3


@port(0x8003A4C0, ret=True)
def map_record(g, ref):
    """The map's entity record ref (20 bytes at *(0x801F2EC8) + ref * 20) when ref is below
    the record count (0x801F2ED4) and the record is enabled (byte 4); else 0 (with a debug
    message when ref is out of range)."""
    if ref < 0 or not ref < g.mem.s32(0x801F2ED4):
        return 0
    rec = (g.mem.u32(0x801F2EC8) + ref * 20) & 0xFFFFFFFF
    return rec if g.mem.u8(rec + 4) else 0


@port(0x8003D23C, mock_always=True)
def fatal(g, msg):
    """Prints the map / entity / command and stops the game (BIOS exit)."""
    f = getattr(g, 'fatal', None)
    if f is not None: f(msg)


@port(0x8003D330, ret=True)
def map_record_checked(g, ref):
    r = map_record(g, ref)
    if r == 0: fatal(g, 0x80023BFC)                  # "Illegal InitData Number!!"
    return r


@port(0x8003D374, ret='list')
def select(g, logic, sel):
    """The entities a script / AI names by sel, in slot order; also left in the list at
    0x8013D488 (returns the list; the game returns the count).
    sel < 0x80: map record number (the game tests the LOGIC entity's status, not each one's);
    0x80 logic; 0x81 Alundra; 0x82 slots 0..count, status 1-3; 0x83 slots 1..count; 0x84
    collidable (flags 0x80), anim flag 0x80 clear, nobody holding it (logic's status again);
    0x85 the entity logic rides; 0x86 those riding logic; 0x87 the one logic bumped; 0x88
    those that bumped logic; 0x89 logic's children; 0x8A its parent; 0x8B those being held."""
    out = []; n = g.ent_count; E = g.ent
    if not sel & 0x80:
        map_record_checked(g, sel)
        for i in range(1, n + 1):
            if _st123(logic) and E[i].ref_id == sel: out.append(E[i])
    else:
        f = sel & 0x7F
        if f == 0: out = [logic]
        elif f == 1: out = [E[0]]
        elif f == 2: out = [E[i] for i in range(0, n + 1) if _st123(E[i])]
        elif f == 3: out = [E[i] for i in range(1, n + 1) if _st123(E[i])]
        elif f == 4:
            out = [E[i] for i in range(0, n + 1) if _st123(logic) and E[i].flags & 0x80
                   and not E[i].anim_flags & 0x80 and E[i].holder is None]
        elif 5 <= f <= 11:
            test = {5: lambda e: logic.riding is e, 6: lambda e: e.riding is logic,
                    7: lambda e: logic.x_collision is e, 8: lambda e: e.x_collision is logic,
                    9: lambda e: e.parent is logic, 10: lambda e: logic.parent is e,
                    11: lambda e: e.holder is not None}[f]
            out = [E[i] for i in range(1, n + 1) if _st123(E[i]) and test(E[i])]
        else:
            fatal(g, 0x80023C18)                     # "Illegal Distination!"
    for k, e in enumerate(out): g.mem.w32(SEL_LIST + 4 * k, ent_addr(e))
    return out


def ent_at(g, addr):
    """The entity object of a RAM address (0 -> None; an address that is no slot of the table:
    a record read and written there, as the game does with a stale word)."""
    if not addr: return None
    a = addr & 0xFFFFFFFF
    if L.ENT_BASE <= a < L.ENT_BASE + L.ENT_SIZE * L.ENT_COUNT and not (a - L.ENT_BASE) % L.ENT_SIZE:
        return g.ent[(a - L.ENT_BASE) // L.ENT_SIZE]
    from .ai_g5 import _At
    return _At(g, a)


@port(0x8003B748)
def sort_targets(g, ents, dists, lo, hi):
    """Quicksort of the u32 distances at dists[lo..hi] (RAM arrays), the entity pointers at
    ents moving with them; pivot = (d[lo] + d[hi]) >> 1."""
    m = g.mem; M = 0xFFFFFFFF
    d = lambda k: m.u32(dists + 4 * k)
    i, j = lo, hi
    p = ((d(lo) + d(hi)) & M) >> 1
    while True:
        while d(i) < p: i += 1
        while p < d(j): j -= 1
        if not i < j: break
        a, b = d(i), d(j); m.w32(dists + 4 * i, b); m.w32(dists + 4 * j, a)
        a, b = m.u32(ents + 4 * i), m.u32(ents + 4 * j); m.w32(ents + 4 * i, b); m.w32(ents + 4 * j, a)
        i += 1; j -= 1
    if lo < i - 1: sort_targets(g, ents, dists, lo, i - 1)
    if j + 1 < hi: sort_targets(g, ents, dists, j + 1, hi)


@port(0x8003B8B0, ret=True)
def find_targets(g, e, mask, resp, ents, dists):
    """Entities e's attack (response byte resp of the balance record) can hurt: slots 1 ..
    count - 1 (the last slot is never looked at), not e, status 2-3, not frozen, flags & mask,
    no hit / damage tick, anim flag 0x40 clear, a balance record whose response is not
    0x80-0xBF (immune).  Written to the RAM arrays ents / dists (squared pixel distance),
    sorted nearest first when there are 3 or more (2 stay in slot order).  Returns the count."""
    n = 0; E = g.ent; cnt = g.ent_count
    for i in range(1, cnt):
        t = E[i]
        if t is e or not ((t.estatus - 2) & 0xFFFFFFFF) < 2 or t.frozen or not (t.flags & mask): continue
        if t.hit_tick or t.damaged_tick or t.anim_flags & 0x40: continue
        ba = getattr(t, 'balance_addr', None)
        if ba is not None:                                   # a record in RAM (the checks)
            if not ba or (g.mem.u8(ba + resp + 2) & 0xC0) == 0x80: continue
        else:                                                # the remake's actor: its balance entry
            bal = getattr(t, 'balance', None)
            if not bal: continue
            r = bal['responses'][resp] if resp < len(bal['responses']) else 0
            if (r & 0xC0) == 0x80: continue
        dx = s32(t.px - e.px) >> 16; dy = s32(t.py - e.py) >> 16
        g.mem.w32(ents + 4 * n, ent_addr(t)); g.mem.w32(dists + 4 * n, dx * dx + dy * dy)
        n += 1
    if n >= 3: sort_targets(g, ents, dists, 0, n - 1)
    return n
