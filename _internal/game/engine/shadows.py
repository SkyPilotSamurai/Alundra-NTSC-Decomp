"""Entity shadows: every entity of status 2 or 3 owns an effect record (Entity+0x1B8) that is
its shadow, placed on the floor under it each frame and drawn with the effects, sorted just
before the entity (its key - 1)."""
from .registry import port
from . import core
from .core import M32, s32


@port(0x8003C9AC, ret='ptr')
def spawn_effect_behind(g, bank_map, index, sub, ent, mode60, x, y, z):
    """An effect that sorts with an entity (mode 3: moves by its own force, drawn at the
    entity's key + mode60) without following it."""
    e = core.alloc_effect(g)
    if e is not None:
        core.init_effect(g, e, 0, -1, 3, bank_map, index, sub, x, y, z)
        e.entity = ent; e.arg60 = mode60
        return e
    return None


def _dust_effect(g):
    f = getattr(g, 'map_info_byte', None)
    if f is not None: return f(0xA)
    return g.mem.u8(g.tile_effects_addr + 0xA)


@port(0x80039788)
def update_shadows(g):
    """GameFrameBody after the physics.  An entity not of status 2 or 3, or blinking from a
    hit (damage counter & 3 == 3), loses its shadow record.  Otherwise its record (made on
    first use) is hidden (state 1) when the sprite has no shadow size (flags bits 16-18),
    anim_flags has 0x10 or something holds it; else by the floor kind under it (+0x18C):
      1, 2  (shallow water) the ripple, global effect 1, animation size - 1
      4     (deep water) hidden; moving, a splash (effect 0x15) every 8 frames
      3     moving, the map's dust effect (tile info +0xA) every 8 frames, then as 0
      0, 5, 6, 7  global effect 0, animation size - 1 - (height above the floor >> 20),
            kept in 0..5
      other the record keeps what it had
    and is shown (state 2) at x, y and the floor height.  Stepping into or out of deep water
    (kind 4 now or the frame before, +0x190) makes a splash (effect 6)."""
    n = g.ent_count
    i = 0
    while n >= i:
        e = g.ent[i]
        i += 1
        if ((e.estatus - 2) & M32) >= 2 or (e.damaged_tick & 3) == 3:
            sh = e.shadow
            if sh is not None and sh != 0: sh.state = 0
            if sh is not None: e.shadow = None
            continue
        sh = e.shadow
        if sh is None or sh == 0:
            sh = spawn_effect_behind(g, 0, 0, 0, e, -1, 0, 0, 0)
            if sh is None: continue
            e.shadow = sh
        size = (e.flags >> 16) & 7
        if size == 0 or e.anim_flags & 0x10 or e.holder is not None:
            sh.state = 1
            continue
        now = e.slope_now & M32
        prev = e.f_190 & M32
        anim = size - 1
        if (now == 4 or prev == 4) and now != prev:
            core.spawn_effect(g, 0, 6, 0, e.px, e.py, e.floor)
        moving = not (e.frame_counter & 7) and (e.fx | e.fy) != 0
        if now in (1, 2):
            sh.b6c = 0; sh.index = 1
        elif now == 4:
            sh.state = 1
            if moving: core.spawn_effect(g, 0, 0x15, 0, e.px, e.py, e.floor)
            continue
        elif now in (0, 3, 5, 6, 7):
            if now == 3 and moving: core.spawn_effect(g, 0, _dust_effect(g), 0, e.px, e.py, e.floor)
            anim = ((anim - (s32(e.pz - e.floor) >> 20)) + 0x80 & 0xFF) - 0x80      # (an s8)
            anim = 5 if anim >= 6 else (0 if anim < 0 else anim)
            sh.b6c = 0; sh.index = 0
        else:
            continue
        sh.b70 = anim & 0xFF
        sh.state = 2
        sh.x = e.px; sh.y = e.py; sh.z = e.floor
