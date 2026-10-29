"""The HUD portrait (a speaker's face during a message, Alundra's in the Start menu), ported
from the US ALUN_CD.EXE.  One textured quad (POLY_FT4, two buffers at 0x801EF384) and its
flight state:
  0x801EF380  s16 state: 1 flying in (growing, white fading to normal), 2 flying back
              (shrinking, getting whiter), 4 shown; 0 none
  0x801EF3D4.. pointers to the source's x, y, z (16.16) and to the camera x, y (0x801EF434/8)
  0x801EF3E8/EC  from (the source on screen, 32 px above its feet)   0x801EF3F0/F4  start
  0x801EF3F8/FC  the distance            0x801EF400  frames left (15)
  0x801EF404/08  full size 48 x 56       0x801EF40C/10  where it settles (speaker 8, 0x74;
              menu 0xF8, 0x68)"""
from .registry import port
from . import calls
from . import layout as L

STATE, PRIM = 0x801EF380, 0x801EF384
SRC, FROM, START, DIST, LEFT, SIZE, TARGET = 0x801EF3D4, 0x801EF3E8, 0x801EF3F0, 0x801EF3F8, 0x801EF400, 0x801EF404, 0x801EF40C
BUFI = 0x801E5F38


def _cdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _hi(g, a):
    """The whole-pixel half (s16 at +2) of a 16.16 coordinate at address a (an entity's x / y / z
    goes through its object)."""
    a &= 0xFFFFFFFF
    lo, hi = L.ENT_BASE, L.ENT_BASE + L.ENT_SIZE * L.ENT_COUNT
    if lo <= a < hi:
        slot, off = divmod(a - lo, L.ENT_SIZE)
        for n, (o, t) in L.ENTITY.items():
            if o == off:
                v = getattr(g.ent[slot], n) & 0xFFFFFFFF
                v >>= 16
                return v - 0x10000 if v & 0x8000 else v
    return g.mem.s16(a + 2)


@port(0x80086C18)
def set_poly_ft4(g, p): g.mem.w8(p + 3, 9); g.mem.w8(p + 7, 0x2C)


def _sides(g):
    m = g.mem
    sx = _hi(g, m.u32(SRC)) - m.s32(m.u32(SRC + 0xC))
    sy = _hi(g, m.u32(SRC + 4)) - m.s32(m.u32(SRC + 0x10)) - _hi(g, m.u32(SRC + 8)) - 0x20
    return sx, sy


@port(0x80059B50)
def portrait_start(g, ex, ey, ez, camx, camy, u, v, w, h, clut, tpage, img=None):
    """Flies the picture (u, v, w x h of the texture page) from the source to the target over
    15 frames, unless one is already up."""
    m = g.mem
    if m.s16(STATE) != 0: return
    for i, a in enumerate((ex, ey, ez, camx, camy)): m.w32(SRC + 4 * i, a)
    m.w16(STATE, 5)
    for b in range(2):
        p = PRIM + b * 0x28
        set_poly_ft4(g, p)
        for o in (4, 5, 6): m.w8(p + o, 0xFF)
        m.w8(p + 0xC, u); m.w8(p + 0x14, u + w); m.w8(p + 0x1C, u); m.w8(p + 0x1D, v + h)
        m.w8(p + 0x24, u + w); m.w8(p + 0x25, v + h)
        m.w16(p + 8, 0x64); m.w16(p + 0xA, 0x64); m.w16(p + 0x10, w + 0x64); m.w16(p + 0x12, 0x64)
        m.w16(p + 0x18, 0x64); m.w16(p + 0x1A, h + 0x64); m.w16(p + 0x20, w + 0x64); m.w16(p + 0x22, h + 0x64)
        m.w8(p + 0xD, v); m.w8(p + 0x15, v)
        m.w16(p + 0xE, clut); m.w16(p + 0x16, tpage)
    sx, sy = _sides(g)
    m.w32(FROM, sx)
    m.w32(SIZE, 0x30); m.w32(SIZE + 4, 0x38)
    tx = m.s32(TARGET); m.w32(START, tx); m.w32(DIST, sx - tx); m.w32(LEFT, 0xF)
    ty = m.s32(TARGET + 4); m.w32(FROM + 4, sy); m.w32(START + 4, ty); m.w32(DIST + 4, sy - ty)
    hook = getattr(g, 'portrait_set', None)
    if hook is not None and not hasattr(g, 'ram'): hook(img)


@port(0x80059AE4)
def portrait_speaker(g, ex, ey, ez, camx, camy, u, v, w, h, clut, tpage, img=None):
    """A speaker's face (sprite flag 0x800000, its image set 0) to (8, 0x74)."""
    g.mem.w32(TARGET, 8); g.mem.w32(TARGET + 4, 0x74)
    portrait_start(g, ex, ey, ez, camx, camy, u, v, w, h, clut, tpage, img=img)


@port(0x80059A78)
def portrait_menu(g, ex, ey, ez, camx, camy, u, v, clut, tpage, img=None):
    """Alundra's face to the Start menu's corner (0xF8, 0x68), 48 x 56."""
    g.mem.w32(TARGET, 0xF8); g.mem.w32(TARGET + 4, 0x68)
    portrait_start(g, ex, ey, ez, camx, camy, u, v, 0x30, 0x38, clut, tpage, img=img)


@port(0x800599A4)
def portrait_back(g, *_):
    """The face flies back to its source, shrinking (15 frames)."""
    m = g.mem
    if m.s16(STATE) == 0: return
    m.w16(STATE, 0)
    sx, _ = _sides(g)
    tx = m.s32(TARGET); ty = m.s32(TARGET + 4)
    m.w32(START, sx); m.w32(FROM, tx); m.w32(DIST, tx - sx); m.w32(FROM + 4, ty)
    m.w16(STATE, 2)
    sy = _hi(g, m.u32(SRC + 4)) - m.s32(m.u32(SRC + 0x10)) - _hi(g, m.u32(SRC + 8))
    m.w32(START + 4, sy)
    m.w32(LEFT, 0xF)
    m.w32(START + 4, sy - 0x20)
    m.w32(DIST + 4, ty - (sy - 0x20))


@port(0x8005997C)
def portrait_reset(g):
    m = g.mem
    m.w32(TARGET, 8); m.w16(STATE, 0); m.w32(TARGET + 4, 0x78)


@port(0x80059D5C)
def portrait_update(g):
    """One frame of the flight: place, size and colour of the quad."""
    m = g.mem
    st = m.s16(STATE)
    if st == 0: return
    w = h = c = 0
    t = m.s32(LEFT)
    if t == 0:
        if st & 2:
            x, y = m.s32(FROM), m.s32(FROM + 4)
            m.w16(STATE, 0)
        else:
            c = 0x80
            x, y = m.s32(START), m.s32(START + 4)
            w, h = m.s32(SIZE), m.s32(SIZE + 4)
            m.w16(STATE, st & 0xFFFE)
    else:
        x = _cdiv(t * m.s32(DIST), 15) + m.s32(START)
        y = _cdiv(t * m.s32(DIST + 4), 15) + m.s32(START + 4)
        if st & 1:
            k = 0xF - t
            w = _cdiv(m.s32(SIZE) * k, 15); h = _cdiv(m.s32(SIZE + 4) * k, 15)
            c = _cdiv(t << 7, 15) + 0x7F
        elif st & 2:
            w = _cdiv(m.s32(SIZE) * t, 15); h = _cdiv(m.s32(SIZE + 4) * t, 15)
            c = _cdiv((0xF - t) << 7, 15) + 0x7F
        m.w32(LEFT, t - 1)
    p = PRIM + m.s32(BUFI) * 0x28
    m.w8(p + 4, c)
    m.w16(p + 8, x); m.w16(p + 0xA, y); m.w16(p + 0x10, x + w); m.w16(p + 0x12, y)
    m.w16(p + 0x18, x); m.w16(p + 0x1A, y + h); m.w16(p + 0x20, x + w); m.w16(p + 0x22, y + h)
    m.w8(p + 5, c); m.w8(p + 6, c)


@port(0x8005A028)
def portrait_draw(g, ot):
    """Every frame (the UI's drawing, 0x80045BD0): the flight moves on and the quad is queued."""
    m = g.mem
    calls.call(g, 0x80088230, calls.STACK)
    calls.call(g, 0x800882D8, 0x801F1320 + m.s32(BUFI) * 0xC, calls.STACK)
    if m.s16(STATE) != 0:
        portrait_update(g)
        p = PRIM + m.s32(BUFI) * 0x28
        m.w32(p, (m.u32(p) & 0xFF000000) | (m.u32(ot) & 0xFFFFFF))
        m.w32(ot, (m.u32(ot) & 0xFF000000) | (p & 0xFFFFFF))
        return True
    return False
