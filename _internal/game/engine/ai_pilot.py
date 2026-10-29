"""Built-in sprite programs (pilot): C1."""
from .registry import port
from .core import s32, next_seed, hi
from . import aihelp
from .player import dir_from_delta
from . import rodata as R

TURN = 0x80028AD8           # u8[32]: the direction turned away


@port(0x8006821C)
def ai_c1(g, e):
    """C1 (cats, birds...): wait, wander or turn to Alundra when he is near."""
    r = aihelp.rel_tile(g, e)
    a = e.target_anim & 0xFFFFFFFF
    p = g.ent[0]
    if a == 0:
        t = e.ai[1] & 0xFFFF
        if t:
            e.ai[1] = t - 1
            if (t - 1) & 0xFFFF: return
        if r[0] < 3 and r[1] < 3 and not (0x200000 < r[2]) and e.bytes[1] == 0:
            e.target_dir = dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
            e.target_anim = 3; e.bytes[1] = 1
            return
        s = next_seed(g)
        e.target_anim = 1
        e.ai[1] = hi(s, 0x3D) + 0x3C
        if r[0] < 4 and r[1] < 4:
            e.target_dir = dir_from_delta(s32(p.px - e.px), s32(p.py - e.py))
        e.bytes[1] = 0
    elif a == 1:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if t: return
        if e.force_adjusted:
            s = next_seed(g)
            e.sfy = e.sfx = e.fy = e.fx = e.tfy = e.tfx = 0
            e.target_dir = R.u8(TURN + e.target_dir)
            e.ai[1] = hi(s, 0x1F) + 0x1E
        else:
            s = next_seed(g)
            e.target_anim = 0
            e.ai[1] = (s >> 19) & 0x7F
            e.target_dir = s >> 27
    elif a == 2:
        if r[0] < 4 and r[1] < 4: e.target_anim = 4
    elif a == 3:
        if e.anim_done:
            aihelp.start_moving(g, e, 1, 0x28, 0x14)
            e.bytes[1] = 0
    elif a == 7:
        if e.anim_done:
            if e.bytes[3]:
                e.target_anim = 6; e.flags = s32(e.flags | 0x40)
                return
            e.target_anim = 0; e.ai[1] = 0x28
    elif a == 4:
        if e.anim_done: e.target_anim = 0; e.ai[1] = 0x1E
    elif 8 <= a <= 14:
        if e.on_ground: e.target_anim = 2
    elif a == 19:
        t = ((e.ai[1] & 0xFFFF) - 1) & 0xFFFF
        e.ai[1] = t
        if not t: e.target_anim = 0; e.ai[1] = 0x1E
