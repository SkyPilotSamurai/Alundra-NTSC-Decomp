"""The History Book: CONTINUE on the title (SLUS_005.53, the disc's boot program).

The boot program has its own little engine, ported here routine by routine over its own memory
(assets/boot/slus_data.bin: the program's image with its code removed - texts, tables, the
picture archive at 0x800438A8), with the PlayStation's GPU done in software over a 1024 x 512
VRAM: the routines build the same primitives in the same ordering table as the original, and
the table is drawn the way the GPU draws it.  Checked against the original code on RAM
snapshots of the recompiled game (tools/us_decomp/check_slus.py).

The scene (0x80025124):
  1. 0x80024A90: "Using the Book in Memory Card Slot 1..." (or why not: no card, no file,
     broken file - 0x800248B4 reads BASLUS-00553ALUNDRA and checks its CRC 0x8002403C);
     Cross (once the text is out) closes the scroll; 60 frames.
  2. with a record: 0x80024B68 the library fades in (music 0x29, sound 0x193) while Alundra
     walks in from the bottom; 0x80024BF8 the keeper's words, Cross;
  3. 0x80024CF0 Alundra walks (0x80023C84: 2 px a frame up/down, 2 sideways, stopped by the
     rectangles at 0x80043828); walking into lectern k (0..3) with a record (its book opens,
     0x80024E78) asks "Would you like to rejoin the tale in this chapter?" with the record's
     two title lines, YES / NO by Left / Right, Cross;  walking out at the bottom leaves (6);
  4. 0x80024DC4 fades out (Alundra walks off when leaving), two frames, the record number
     (or -1).
The record (0x801F7220 + k * 0x76C, 0x76C bytes) is then handed to ALUN_CD.EXE at 0x80010000
with [0] = 1 and [1] = k (0x8002536C), after the Now Loading picture."""
import struct
from pathlib import Path
import numpy as np
import pygame
from sound_system import OUTPUT          # the console's output level (sound_system.py)

from home import HOME as ROOT
ASSETS = ROOT / 'assets'
BASE = 0x80020000

# ---------------------------------------------------------------- memory
_hu, _hs, _iu, _is = struct.Struct('<H'), struct.Struct('<h'), struct.Struct('<I'), struct.Struct('<i')


class Mem:
    """2 MB of PlayStation RAM (0x80000000..0x801FFFFF)."""
    def __init__(self, data=None):
        self.b = data if data is not None else bytearray(0x200000)

    def u8(self, a): return self.b[a & 0x1FFFFF]
    def s8(self, a): v = self.b[a & 0x1FFFFF]; return v - 0x100 if v & 0x80 else v
    def u16(self, a): return _hu.unpack_from(self.b, a & 0x1FFFFF)[0]
    def s16(self, a): return _hs.unpack_from(self.b, a & 0x1FFFFF)[0]
    def u32(self, a): return _iu.unpack_from(self.b, a & 0x1FFFFF)[0]
    def s32(self, a): return _is.unpack_from(self.b, a & 0x1FFFFF)[0]
    def w8(self, a, v): self.b[a & 0x1FFFFF] = v & 0xFF
    def w16(self, a, v): _hu.pack_into(self.b, a & 0x1FFFFF, v & 0xFFFF)
    def w32(self, a, v): _iu.pack_into(self.b, a & 0x1FFFFF, v & 0xFFFFFFFF)
    def bytes(self, a, n): a &= 0x1FFFFF; return bytes(self.b[a:a + n])
    def cstr(self, a):
        a &= 0x1FFFFF; e = self.b.index(0, a); return bytes(self.b[a:e])


def s16(v): v &= 0xFFFF; return v - 0x10000 if v & 0x8000 else v
def s32(v): v &= 0xFFFFFFFF; return v - 0x100000000 if v & 0x80000000 else v
def div0(v, n): return int(v / n)          # C division (toward zero)


PORTS = {}            # address -> port (for the checks)


def port(addr):
    def deco(f):
        PORTS[addr] = f; f.addr = addr; return f
    return deco


# ---------------------------------------------------------------- the GPU (software)
class GPU:
    """VRAM and the drawing of the primitives this program uses: DR_MODE (E1 draw mode),
    SPRT (0x64), POLY_FT4 (0x2C) and POLY_F4 (0x28), textured ones modulated by their colour
    (0x80 = as is), texel 0 see-through, semi-transparent texels (bit 15) and flat polygons
    blended by the draw mode's ABR (0: 1/2 + 1/2, 1: +, 2: -, 3: + 1/4)."""
    def __init__(self):
        self.vram = np.zeros((512, 1024), np.uint16)
        self.tpage = 0; self.clip = (0, 0, 320, 240); self.ofs = (0, 0)
        self.disp = (0, 240, 320, 240)

    # ---- transfers
    def load_image(self, x, y, w, h, data):
        a = np.frombuffer(bytes(data[:w * h * 2]), '<u2').reshape(h, w)
        ys = (np.arange(h) + y) & 511; xs = (np.arange(w) + x) & 1023
        self.vram[np.ix_(ys, xs)] = a

    # ---- texture fetch
    def texels(self, tpage, clut, u, v):
        """u, v: int arrays (texture coordinates in the page) -> 16-bit texel colours."""
        mode = (tpage >> 7) & 3
        px = (tpage & 0xF) * 64; py = ((tpage >> 4) & 1) * 256
        u = u & 0xFF; v = v & 0xFF
        if mode == 0:
            w = self.vram[(py + v) & 511, (px + (u >> 2)) & 1023]
            idx = (w >> ((u & 3) * 4)) & 0xF
        elif mode == 1:
            w = self.vram[(py + v) & 511, (px + (u >> 1)) & 1023]
            idx = (w >> ((u & 1) * 8)) & 0xFF
        else:
            return self.vram[(py + v) & 511, (px + u) & 1023]
        cx = (clut & 0x3F) * 16; cy = (clut >> 6) & 511
        return self.vram[cy, (cx + idx) & 1023]

    # ---- pixel output
    def _put(self, ys, xs, col, semi, abr, stp_mask=None):
        """col: 15-bit colours (uint16, bit 15 kept), drawn at (ys, xs)."""
        if semi:
            sm = np.ones(col.shape, bool) if stp_mask is None else stp_mask
            if sm.any():
                b = self.vram[ys, xs]
                br, bg, bb = b & 31, (b >> 5) & 31, (b >> 10) & 31
                fr, fg, fb = col & 31, (col >> 5) & 31, (col >> 10) & 31
                if abr == 0: r, g, bl = (br + fr) >> 1, (bg + fg) >> 1, (bb + fb) >> 1
                elif abr == 1: r, g, bl = br + fr, bg + fg, bb + fb
                elif abr == 2: r, g, bl = br.astype(np.int32) - fr, bg.astype(np.int32) - fg, bb.astype(np.int32) - fb
                else: r, g, bl = br + (fr >> 2), bg + (fg >> 2), bb + (fb >> 2)
                r = np.clip(r, 0, 31).astype(np.uint16); g = np.clip(g, 0, 31).astype(np.uint16)
                bl = np.clip(bl, 0, 31).astype(np.uint16)
                blended = r | (g << 5) | (bl << 10) | (col & 0x8000)
                col = np.where(sm, blended, col)
        self.vram[ys, xs] = col

    def _clip_area(self):
        x0, y0, w, h = self.clip
        return x0, y0, x0 + w, y0 + h

    @staticmethod
    def _modulate(t, r, g, b):
        if r == g == b == 0x80: return t
        tr, tg, tb = t & 31, (t >> 5) & 31, (t >> 10) & 31
        tr = np.minimum(31, (tr.astype(np.int32) * r) >> 7); tg = np.minimum(31, (tg.astype(np.int32) * g) >> 7)
        tb = np.minimum(31, (tb.astype(np.int32) * b) >> 7)
        return (tr | (tg << 5) | (tb << 10)).astype(np.uint16) | (t & 0x8000)

    def sprt(self, x, y, w, h, u, v, clut, rgb, semi, raw):
        ox, oy = self.ofs; x += ox; y += oy
        cx0, cy0, cx1, cy1 = self._clip_area()
        xa, ya = max(x, cx0), max(y, cy0); xb, yb = min(x + w, cx1), min(y + h, cy1)
        if xa >= xb or ya >= yb: return
        uu = (u + np.arange(xa - x, xb - x))[None, :]
        vv = (v + np.arange(ya - y, yb - y))[:, None]
        uu, vv = np.broadcast_arrays(uu, vv)
        t = self.texels(self.tpage, clut, uu, vv)
        drawn = t != 0
        if not raw: t = self._modulate(t, *rgb)
        ys, xs = np.nonzero(drawn)
        if not len(ys): return
        abr = (self.tpage >> 5) & 3
        self._put(ys + ya, xs + xa, t[ys, xs], semi, abr, (t[ys, xs] & 0x8000) != 0)

    def poly_f4(self, pts, rgb, semi, abr):
        r, g, b = rgb
        col = np.uint16((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
        for tri in ((0, 1, 2), (1, 2, 3)):
            ys, xs, _ = self._raster([pts[i] for i in tri])
            if len(ys): self._put(ys, xs, np.full(len(ys), col, np.uint16), semi, abr)

    def poly_ft4(self, pts, uvs, tpage, clut, rgb, semi, raw):
        for tri in ((0, 1, 2), (1, 2, 3)):
            ys, xs, bc = self._raster([pts[i] for i in tri])
            if not len(ys): continue
            u = np.zeros(len(ys)); v = np.zeros(len(ys))
            for k, i in enumerate(tri):
                u += bc[k] * uvs[i][0]; v += bc[k] * uvs[i][1]
            t = self.texels(tpage, clut, np.floor(u).astype(np.int64), np.floor(v).astype(np.int64))
            drawn = t != 0
            if not raw: t = self._modulate(t, *rgb)
            ys, xs, t = ys[drawn], xs[drawn], t[drawn]
            if len(ys): self._put(ys, xs, t, semi, (tpage >> 5) & 3, (t & 0x8000) != 0)

    def _raster(self, tri):
        """Pixels of a triangle (top-left fill rule), with barycentric weights."""
        ox, oy = self.ofs
        (x0, y0), (x1, y1), (x2, y2) = [(x + ox, y + oy) for x, y in tri]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        empty = (np.zeros(0, np.int64), np.zeros(0, np.int64), None)
        if area == 0: return empty
        cx0, cy0, cx1, cy1 = self._clip_area()
        xa, xb = max(min(x0, x1, x2), cx0), min(max(x0, x1, x2), cx1)
        ya, yb = max(min(y0, y1, y2), cy0), min(max(y0, y1, y2), cy1)
        if xa >= xb or ya >= yb: return empty
        X, Y = np.meshgrid(np.arange(xa, xb), np.arange(ya, yb))
        def edge(ax, ay, bx, by):
            return (bx - ax) * (Y - ay) - (by - ay) * (X - ax)
        w0 = edge(x1, y1, x2, y2); w1 = edge(x2, y2, x0, y0); w2 = edge(x0, y0, x1, y1)
        edges = ((x1, y1, x2, y2), (x2, y2, x0, y0), (x0, y0, x1, y1))
        if area < 0:
            w0, w1, w2, area = -w0, -w1, -w2, -area
            edges = tuple((bx, by, ax, ay) for ax, ay, bx, by in edges)
        inside = np.ones(w0.shape, bool)
        for w, (ax, ay, bx, by) in zip((w0, w1, w2), edges):
            dx, dy = bx - ax, by - ay
            # pixels on an edge belong to it only on its top / left side (the GPU leaves out the
            # right and bottom edges), so two triangles sharing an edge never both draw it
            keep = dy < 0 or (dy == 0 and dx > 0)
            inside &= (w > 0) | ((w == 0) if keep else False)
        ys, xs = np.nonzero(inside)
        bc = (w0[ys, xs] / area, w1[ys, xs] / area, w2[ys, xs] / area)
        return ys + ya, xs + xa, bc

    # ---- the ordering table
    def draw_otag(self, mem, addr):
        n = 0
        while (addr & 0xFFFFFF) != 0xFFFFFF and n < 20000:
            n += 1
            tag = mem.u32(addr); ln = tag >> 24; nxt = tag & 0xFFFFFF
            if ln: self.prim(mem, addr, ln)
            addr = 0x80000000 | nxt
            if nxt == 0xFFFFFF: break

    def prim(self, mem, a, ln):
        code = mem.u8(a + 7)
        if code == 0xE1 or (mem.u32(a + 4) >> 24) == 0xE1:
            self.tpage = mem.u32(a + 4) & 0x7FF; return
        semi = bool(code & 2); raw = bool(code & 1)
        rgb = (mem.u8(a + 4), mem.u8(a + 5), mem.u8(a + 6))
        if code & 0xFC == 0x64:
            self.sprt(mem.s16(a + 8), mem.s16(a + 10), mem.u16(a + 16), mem.u16(a + 18),
                      mem.u8(a + 12), mem.u8(a + 13), mem.u16(a + 14), rgb, semi, raw)
        elif code & 0xFC == 0x2C:
            pts = [(mem.s16(a + 8 + 8 * i), mem.s16(a + 10 + 8 * i)) for i in range(4)]
            uvs = [(mem.u8(a + 12 + 8 * i), mem.u8(a + 13 + 8 * i)) for i in range(4)]
            tp = mem.u16(a + 0x16)
            self.tpage = tp & 0x7FF | (self.tpage & ~0x7FF)
            self.poly_ft4(pts, uvs, tp, mem.u16(a + 14), rgb, semi, raw)
        elif code & 0xFC == 0x28:
            pts = [(mem.s16(a + 8 + 4 * i), mem.s16(a + 10 + 4 * i)) for i in range(4)]
            self.poly_f4(pts, rgb, semi, (self.tpage >> 5) & 3)

    # ---- the environments
    def put_draw_env(self, mem, env):
        x, y, w, h = (mem.s16(env + i) for i in (0, 2, 4, 6))
        self.clip = (x, y, w, h); self.ofs = (mem.s16(env + 8), mem.s16(env + 10))
        self.tpage = mem.u16(env + 0x14) & 0x7FF
        if mem.u8(env + 0x18):                                    # isbg: the area is cleared
            r, g, b = mem.u8(env + 0x19), mem.u8(env + 0x1A), mem.u8(env + 0x1B)
            self.vram[y:y + h, x:x + w] = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

    def put_disp_env(self, mem, env):
        self.disp = tuple(mem.s16(env + i) for i in (0, 2, 4, 6))

    def picture(self):
        """The displayed area as a pygame surface."""
        x, y, w, h = self.disp
        a = self.vram[y:y + h, x:x + w]
        rgb = np.dstack([(a & 31) << 3, ((a >> 5) & 31) << 3, ((a >> 10) & 31) << 3]).astype(np.uint8)
        return pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))


# ---------------------------------------------------------------- the machine
class Book:
    """The boot program's state (its RAM and the GPU) and what it reaches outside: the pad,
    the sound, the memory card (the remake's BIOS card services)."""
    def __init__(self, g=None, bios=None):
        img = (ASSETS / 'boot' / 'slus_data.bin').read_bytes()
        b = bytearray(0x200000); b[0x20000:0x20000 + len(img)] = img
        self.mem = Mem(b); self.gpu = GPU(); self.g = g; self.bios = bios
        self.pad = 0; self.held = 0; self.music_fade = None
        self.jp = False                        # the JP texts / layout in use (set_lang, a remake addition)
        self.eu = None; self.eu_glyphs = None    # a European language's texts / boot font (set_lang)
        self.calls = None                      # the checks record library calls here
        m = self.mem
        # left by boot before the title (0x80025228, 0x8002536C, the GPU / pad / card set-up)
        m.w32(0x801F48FC, 0x800438A8)                       # the picture archive
        m.w8(0x801484B8, 3)                                 # GPU version: the old draw mode format
        for i, (clip_y, disp_y) in enumerate(((0, 240), (240, 0))):
            env = 0x801F01E8 + i * 0x2280                   # DRAWENV / DISPENV of the two buffers
            for k, v in enumerate((0, clip_y, 320, 240, 0, clip_y)): m.w16(env + 2 * k, v)
            m.w16(env + 0x14, 0xA); m.w8(env + 0x16, 1); m.w8(env + 0x17, 1); m.w8(env + 0x18, 1)
            for k, v in enumerate((0, disp_y, 320, 240)): m.w16(env + 0x5C + 2 * k, v)
        m.w32(0x801F48BC, 0x801F01E8); m.w32(0x801EFFDC, 0)

    # ---- library calls (HLE)
    def lib(self, name, *args):
        if self.calls is not None: self.calls.append((name,) + args)

    def sfx(self, n):                                   # 0x800289D8
        self.lib('sfx', n)
        if self.g is not None and getattr(self.g, 'snd', None) is not None: self.g.snd.play(n, book=True)

    def sfx_stop(self, n):                              # 0x80028680
        self.lib('sfx_stop', n)
        if self.g is not None and getattr(self.g, 'snd', None) is not None: self.g.snd.stop(n)

    def music(self, n):                                 # 0x80028D48
        self.lib('music', n); self.mem.w16(0x801EFE04, n)
        self.music_fade = None
        if self.g is not None and getattr(self.g, 'snd', None) is not None: self.g.snd.music_load_now(n, True)

    def music_fade_out(self, on):                       # 0x80028D00 (SsSeqSetDecrescendo(seq, 127, 120))
        self.lib('music_fade', on)
        self.music_fade = 120 if on else None
        if not on and self.g is not None and getattr(self.g, 'snd', None) is not None: self.g.snd.music_stop(False)

    @property
    def confirm(self):
        """Cross (0x40), or Square (0x80) with the remake's Controls > Confirm button = JP."""
        s = getattr(self.g, 'settings', None)
        return 0x80 if s and s.get('confirm') == 'jp' else 0x40

    def pad_held(self):                                 # 0x800351D8
        self.lib('pad'); return self.pad

    def load_image(self, rect, data):                   # LoadImage 0x8002D9F8
        m = self.mem
        x, y, w, h = m.s16(rect), m.s16(rect + 2), m.s16(rect + 4), m.s16(rect + 6)
        self.lib('load_image', x, y, w, h, data)
        if w > 0 and h > 0: self.gpu.load_image(x, y, w, h, m.bytes(data, w * h * 2))


# ---------------------------------------------------------------- libgpu
@port(0x8002DB84)
def clear_otag(b, ot, n):
    m = b.mem; a = ot
    for _ in range(n - 1):
        m.w8(a + 3, 0); m.w32(a, (m.u32(a) & 0xFF000000) | ((a + 4) & 0xFFFFFF)); a += 4
    m.w32(a, 0x80148574 & 0xFFFFFF)
    return a


@port(0x8002CCB0)
def add_prim(b, ot, p):
    m = b.mem
    m.w32(p, (m.u32(p) & 0xFF000000) | (m.u32(ot) & 0xFFFFFF))
    m.w32(ot, (m.u32(ot) & 0xFF000000) | (p & 0xFFFFFF))


@port(0x8002CA88)
def get_tpage(b, tp, abr, x, y):
    return ((tp & 3) << 7) | ((abr & 3) << 5) | ((y & 0x100) >> 4) | ((x & 0x3FF) >> 6) | ((y & 0x200) << 2)


@port(0x8002CFB8)
def set_draw_mode(b, p, dfe, dtd, tpage):
    m = b.mem; m.w8(p + 3, 1)
    v = 0xE1000000 | (0x200 if dtd else 0) | (tpage & 0x9FF) | (0x400 if dfe else 0)
    m.w32(p + 4, v)


def _set_bit(b, p, bit, on):
    m = b.mem; c = m.u8(p + 7)
    m.w8(p + 7, (c | bit) if on else (c & ~bit))


@port(0x8002CD8C)
def set_shade_tex(b, p, on): _set_bit(b, p, 1, on)


@port(0x8002CD64)
def set_semi_trans(b, p, on): _set_bit(b, p, 2, on)


@port(0x8002CE7C)
def set_sprt(b, p): b.mem.w8(p + 3, 4); b.mem.w8(p + 7, 0x64)


@port(0x8002CE04)
def set_poly_f4(b, p): b.mem.w8(p + 3, 5); b.mem.w8(p + 7, 0x28)


# ---------------------------------------------------------------- GTE (z rotation only)
RCOSSIN = 0x80148768            # rcossin_tbl: {sin, cos} s16 pairs for 0..4095


def _rcossin(b, a):
    m = b.mem
    if a < 0:
        a = (-a) & 0xFFF; return -m.s16(RCOSSIN + 4 * a), m.s16(RCOSSIN + 4 * a + 2)
    a &= 0xFFF; return m.s16(RCOSSIN + 4 * a), m.s16(RCOSSIN + 4 * a + 2)


def rot_trans_z(b, angle, tx, ty, dx, dy):
    """RotMatrix({0, 0, angle}) + SetTransMatrix + RotTrans: the GTE's MVMVA with the
    translation, shifted right 12 (rounded toward minus infinity)."""
    s, c = _rcossin(b, s16(angle))
    x = ((tx << 12) + c * dx - s * dy) >> 12
    y = ((ty << 12) + s * dx + c * dy) >> 12
    return x, y


# ---------------------------------------------------------------- the frame
@port(0x800259A0)
def frame_begin(b):
    m = b.mem; buf = m.u32(0x801F48BC)
    clear_otag(b, buf + 0x70, 0x100)
    for o in (0x227C, 0x1878, 0x1274, 0x870): m.w32(buf + o, 0)


def frame_end(b):
    """0x800259E4: the frame is shown - DrawSync, VSync, the pad, PutDispEnv / PutDrawEnv of
    this buffer (the area is cleared), DrawOTag, then the other buffer is the next frame's."""
    m = b.mem; buf = m.u32(0x801F48BC)
    b.lib('frame_end')
    if b.g is not None and getattr(b.g, 'snd', None) is not None:
        b.g.snd.tick()
        if b.music_fade:                                 # SsSeqSetDecrescendo(seq, 127, 120)
            b.music_fade -= 1
            try: pygame.mixer.music.set_volume(b.music_fade / 120 * b.g.settings.get('music_volume', 100) / 100 * OUTPUT)
            except pygame.error: pass
    if b.calls is None:
        b.gpu.put_disp_env(m, buf + 0x5C); b.gpu.put_draw_env(m, buf); b.gpu.draw_otag(m, buf + 0x70)
    yield
    b.pad = b.held                                       # read at the vertical blank
    i = m.s32(0x801EFFDC) ^ 1; m.w32(0x801EFFDC, i)
    nb = 0x801F01E8 + i * 0x2280; m.w32(0x801F48BC, nb)
    m.w8(nb + 0x19, m.u32(0x801EFFE0)); m.w8(nb + 0x1A, m.u32(0x801EFE1C)); m.w8(nb + 0x1B, m.u32(0x801EFE08))


# ---------------------------------------------------------------- pictures (TIM) and canvases
@port(0x80027540)
def archive_find(b, arc, name, idx):
    m = b.mem
    key = (m.u8(name) | m.u8(name + 1) << 8 | m.u8(name + 2) << 16 | (idx & 0xFF) << 24) & 0xFFFFFFFF
    a = arc
    while m.u32(a) != 0xFF444E45:
        if m.u32(a) == key: return a + 8
        a = a + 8 + m.u32(a + 4)
    return 0


@port(0x800265F8)
def tim_parse(b, t, tim):
    m = b.mem
    if m.u32(tim) != 0x10: return -1
    fl = m.u32(tim + 4)
    m.w32(t + 0x10, fl & 7)
    has = (fl >> 3) & 1; m.w32(t, has)
    if has:
        m.w32(t, m.u32(tim + 8))
        for k in range(4): m.w16(t + 4 + 2 * k, m.u16(tim + 0xC + 2 * k))
        m.w32(t + 0xC, tim + 0x14)
    q = (m.s32(t) // 4 if m.s32(t) >= 0 else -((-m.s32(t)) // 4)) * 4
    m.w32(t + 0x14, m.u32(tim + q + 8))
    for k in range(4): m.w16(t + 0x18 + 2 * k, m.u16(tim + q + 0xC + 2 * k))
    m.w32(t + 0x20, tim + q + 0x14)
    mode = m.s32(t + 0x10)
    w = m.s16(t + 0x1C)
    if mode == 0: m.w32(t + 0x24, s16(w * 4))
    elif mode == 1: m.w32(t + 0x24, s16(w * 2))
    elif mode in (2, 3): m.w32(t + 0x24, w)
    m.w32(t + 0x28, m.s16(t + 0x1E))
    return 0


@port(0x80026774)
def tim_upload(b, t, x, y, cx, cy, sync):
    m = b.mem
    if s16(x) != -1: m.w16(t + 0x18, x)
    if s16(y) != -1: m.w16(t + 0x1A, y)
    if s16(cx) != -1: m.w16(t + 4, cx)
    if s32(cy) != -1: m.w16(t + 6, cy)
    if s32(sync) != -1:
        if m.u32(t): b.load_image(t + 4, m.u32(t + 0xC))
        if m.u32(t + 0x14): b.load_image(t + 0x18, m.u32(t + 0x20))
        b.lib('draw_sync', sync)
    return 0


@port(0x8002696C)
def canvas_init(b, cv, mode, w, h, data):
    m = b.mem
    m.w32(cv + 0x24, w); m.w32(cv + 0x28, h)
    hw = w
    if mode == 0: hw = (w + 3 if w < 0 else w) >> 2
    if mode == 1: hw = div0(hw, 2)
    size = hw * h
    m.w32(cv + 0x10, mode); m.w16(cv + 0x18, 0); m.w16(cv + 0x1A, 0)
    m.w16(cv + 0x1C, hw); m.w16(cv + 0x1E, h); m.w32(cv + 0x20, data); m.w32(cv, 0)
    m.w32(cv + 0x14, size)


@port(0x800268B0)
def canvas_set(b, cv, x, y, v):
    m = b.mem
    x &= 0xFFFFFFFF; y &= 0xFFFFFFFF
    w = m.u32(cv + 0x24)
    if not (x < w and y < m.u32(cv + 0x28)): return
    row = (y * w) & 0xFFFFFFFF
    mode = m.s32(cv + 0x10)
    if mode == 0:
        a = m.u32(cv + 0x20) + (s32(row) >> 1) + (s32(x) >> 1)
        if x & 1: m.w8(a, ((v << 4) & 0xFF) | (m.u8(a) & 0xF))
        else: m.w8(a, (v & 0xF) | (m.u8(a) & 0xF0))
    elif mode == 1: m.w8(m.u32(cv + 0x20) + row + x, v)
    elif mode == 2: m.w16(m.u32(cv + 0x20) + (row + x) * 2, s16(s8_(v)))


def s8_(v): v &= 0xFF; return v - 0x100 if v & 0x80 else v


@port(0x80026820)
def canvas_get(b, cv, x, y):
    m = b.mem
    row = y * m.s32(cv + 0x24); mode = m.s32(cv + 0x10)
    if mode == 0:
        v = m.u8(m.u32(cv + 0x20) + (row >> 1) + (x >> 1))
        return (v >> 4) & 0xF if x & 1 else v & 0xF
    if mode == 1: return m.u8(m.u32(cv + 0x20) + row + x)
    if mode == 2: return m.u16(m.u32(cv + 0x20) + (row + x) * 2) & 0xFF
    return 0xFF


@port(0x800269D4)
def canvas_copy(b, dst, dx, dy, src, sx, sy, w, h):
    for r in range(h):
        for c in range(w):
            canvas_set(b, dst, dx + c, dy + r, canvas_get(b, src, sx + c, sy + r) & 0xFFFF)


@port(0x80026AD4)
def canvas_blit(b, dst, dx, dy, src, sx, sy, w, h):
    """A glyph from the font canvas: pixels whose palette colour is not 0."""
    m = b.mem
    if m.u32(src + 0x10) < 2:
        if m.u32(src) == 0:
            canvas_copy(b, dst, dx, dy, src, sx, sy, w, h); return
        clut = m.u32(src + 0xC)
        for r in range(h):
            for c in range(w):
                v = canvas_get(b, src, sx + c, sy + r) & 0xFFFF
                if m.u16(clut + v * 2): canvas_set(b, dst, dx + c, dy + r, v)
    else:
        for r in range(h):
            for c in range(w):
                v = canvas_get(b, src, sx + c, sy + r) & 0xFFFF
                if v: canvas_set(b, dst, dx + c, dy + r, v)


@port(0x80026CFC)
def canvas_scroll(b, cv):
    """A 4-bit canvas moves up one row; the last row is cleared."""
    m = b.mem
    w = m.s32(cv + 0x24); h = m.s32(cv + 0x28)
    if m.s32(cv + 0x10) != 0: return
    d = m.u32(cv + 0x20); half = div0(w, 2)
    for r in range(1, h):
        for k in range(0, (w + 1) // 2):
            m.w8(d + (r - 1) * half + k, m.u8(d + r * half + k))
    for k in range(0, (w + 1) // 2): m.w8(d + (h - 1) * half + k, 0)


# ---------------------------------------------------------------- sprites and tiles
@port(0x80025C18)
def obj_init(b, o, mode, semi, vx, vy, w, h, cx, cy):
    m = b.mem
    m.w32(o + 8, -1); m.w16(o + 4, -1); m.w16(o + 2, -1); m.w16(o, -1)
    m.w8(o + 0xE, 0x80); m.w8(o + 0xD, 0x80); m.w8(o + 0xC, 0x80)
    m.w16(o + 0x14, mode); m.w16(o + 0x16, semi); m.w16(o + 0x18, vx)
    m.w16(o + 0x12, 0); m.w16(o + 0x10, 0)
    m.w16(o + 0x1A, vy); m.w16(o + 0x20, cx); m.w16(o + 0x22, cy); m.w16(o + 0x1C, w); m.w16(o + 0x1E, h)


@port(0x80025C80)
def obj_ofs(b, o, x, y): b.mem.w16(o + 0x10, x); b.mem.w16(o + 0x12, y)


@port(0x80025C8C)
def obj_pos(b, o, x, y, prio, angle):
    m = b.mem; m.w16(o, x); m.w16(o + 2, y); m.w16(o + 4, prio); m.w32(o + 8, s16(angle))


@port(0x80025CAC)
def obj_rgb(b, o, r, g, bl): m = b.mem; m.w8(o + 0xC, r); m.w8(o + 0xD, g); m.w8(o + 0xE, bl)


@port(0x800261D8)
def obj_draw_n(b, o, n):
    m = b.mem; x, y = m.u16(o), m.u16(o + 2)
    for i in range(n):
        p = o + 0x24 * i
        m.w16(p, x); m.w16(p + 2, y)
        obj_draw(b, p)


@port(0x80025CBC)
def obj_draw(b, o):
    m = b.mem
    prio = m.s16(o + 4)
    if prio < 0: return
    x = m.s16(o) + m.s16(o + 0x10); y = m.s16(o + 2) + m.s16(o + 0x12)
    angle = m.s32(o + 8)
    if angle == -1:
        if not (x < 0x140 and y < 0xF0 and x + m.s16(o + 0x1C) >= 0 and y + m.s16(o + 0x1E) >= 0): return
    semi = m.s16(o + 0x16)
    abr, st = (0, 0) if semi == -1 else (semi, 1)
    mode = m.s16(o + 0x14); vx = m.s16(o + 0x18); vy = m.s16(o + 0x1A)
    if mode == 0: px, py, u, v = vx & ~0x3F, vy & ~0xFF, (vx & 0x3F) * 4, vy & 0xFF
    elif mode == 1: px, py, u, v = vx & ~0x7F, vy & ~0xFF, (vx & 0x7F) * 2, vy & 0xFF
    else: px, py, u, v = vx & ~0xFF, vy & ~0xFF, vx & 0xFF, vy & 0xFF
    clut = (m.u16(o + 0x22) << 6) | ((m.u16(o + 0x20) >> 4) & 0x3F)
    buf = m.u32(0x801F48BC); ot = buf + 0x70 + prio * 4
    if angle == -1:
        k = m.s32(buf + 0x870); m.w32(buf + 0x870, k + 1); dr = buf + 0x470 + k * 8
        j = m.s32(buf + 0x1274); m.w32(buf + 0x1274, j + 1); sp = buf + 0x874 + j * 0x14
        set_draw_mode(b, dr, 0, 0, get_tpage(b, mode, abr, px, py) & 0xFFFF)
        set_sprt(b, sp); set_shade_tex(b, sp, 0); set_semi_trans(b, sp, st)
        m.w8(sp + 0xC, u); m.w8(sp + 0xD, v)
        m.w16(sp + 0x10, m.u16(o + 0x1C)); m.w16(sp + 0x12, m.u16(o + 0x1E))
        m.w16(sp + 8, x); m.w16(sp + 0xE, clut); m.w16(sp + 0xA, y)
        m.w8(sp + 4, m.u8(o + 0xC)); m.w8(sp + 5, m.u8(o + 0xD)); m.w8(sp + 6, m.u8(o + 0xE))
        add_prim(b, ot, sp); add_prim(b, ot, dr)
        return
    w1 = m.s16(o + 0x1C) - 1; h1 = m.s16(o + 0x1E) - 1
    k = m.s32(buf + 0x227C); m.w32(buf + 0x227C, k + 1); p = buf + 0x187C + k * 0x28
    m.w8(p + 3, 9); m.w8(p + 7, 0x2C)
    set_shade_tex(b, p, 0); set_semi_trans(b, p, st)
    m.w16(p + 0x16, get_tpage(b, mode, abr, px, py))
    m.w16(p + 0xE, clut)
    m.w8(p + 4, m.u8(o + 0xC)); m.w8(p + 5, m.u8(o + 0xD))
    u1 = (u + w1) & 0xFF; v1 = (v + h1) & 0xFF
    m.w8(p + 0xC, u); m.w8(p + 0xD, v); m.w8(p + 0x14, u1); m.w8(p + 0x15, v)
    m.w8(p + 0x1C, u); m.w8(p + 0x1D, v1); m.w8(p + 0x24, u1); m.w8(p + 0x25, v1)
    m.w8(p + 6, m.u8(o + 0xE))
    hw, hh = w1 >> 1, h1 >> 1
    tx, ty = x + hw, y + hh
    pts = [rot_trans_z(b, angle, tx, ty, dx, dy) for dx, dy in ((-hw, -hh), (hw, -hh), (-hw, hh), (hw, hh))]
    for i, (px_, py_) in enumerate(pts):
        m.w16(p + 8 + 8 * i, px_); m.w16(p + 0xA + 8 * i, py_)
    add_prim(b, ot, p)


@port(0x80026264)
def tile_init(b, t, semi, w, h, r, g, bl):
    m = b.mem
    m.w16(t + 4, -1); m.w16(t + 2, -1); m.w16(t, -1)
    m.w16(t + 0xE, semi); m.w16(t + 0x10, w); m.w16(t + 0x12, h)
    m.w16(t + 0xC, 0); m.w16(t + 0xA, 0); m.w8(t + 6, r); m.w8(t + 7, g); m.w8(t + 8, bl)


@port(0x800262A4)
def tile_ofs(b, t, x, y): b.mem.w16(t + 0xA, x); b.mem.w16(t + 0xC, y)


@port(0x800262B0)
def tile_pos(b, t, x, y, prio): m = b.mem; m.w16(t, x); m.w16(t + 2, y); m.w16(t + 4, prio)


@port(0x800262C0)
def tile_draw(b, t):
    m = b.mem
    prio = m.s16(t + 4)
    if prio < 0: return
    x = m.s16(t) + m.s16(t + 0xA)
    if x >= 0x140: return
    y = m.s16(t + 2) + m.s16(t + 0xC)
    if y >= 0xF0: return
    x1 = x + m.s16(t + 0x10)
    if x1 < 0: return
    y1 = x + m.s16(t + 0x12)                         # (the original adds the height to x)
    if y1 < 0: return
    buf = m.u32(0x801F48BC)
    k = m.s32(buf + 0x870); j = m.s32(buf + 0x1878)
    m.w32(buf + 0x870, k + 1); m.w32(buf + 0x1878, j + 1)
    p = buf + 0x1278 + j * 0x18; dr = buf + 0x470 + k * 8
    semi = m.s16(t + 0xE)
    abr, st = (0, 0) if semi == -1 else (semi, 1)
    set_draw_mode(b, dr, 0, 0, get_tpage(b, 0, abr, 0, 0) & 0xFFFF)
    set_poly_f4(b, p); set_shade_tex(b, p, 0); set_semi_trans(b, p, st)
    for i, (px, py) in enumerate(((x, y), (x1, y), (x, y1), (x1, y1))):
        m.w16(p + 8 + 4 * i, px); m.w16(p + 0xA + 4 * i, py)
    m.w8(p + 4, m.u8(t + 6)); m.w8(p + 5, m.u8(t + 7)); m.w8(p + 6, m.u8(t + 8))
    ot = buf + 0x70 + prio * 4
    add_prim(b, ot, p); add_prim(b, ot, dr)


# ---------------------------------------------------------------- windows and text
@port(0x80022354)
def win_init(b, w, x, y, sx, sy, tx, ty):
    m = b.mem
    for k, v in enumerate((x, y, sx, sy, tx, ty)): m.w32(w + 4 * k, v)


@port(0x8002247C)
def win_target(b, w, tx, ty): b.mem.w32(w + 0x10, tx); b.mem.w32(w + 0x14, ty)


@port(0x80022464)
def win_pos(b, w): return b.mem.s32(w), b.mem.s32(w + 4)


@port(0x8002237C)
def win_step(b, w):
    m = b.mem
    for p, s, t in ((0, 8, 0x10), (4, 0xC, 0x14)):
        if m.s32(w + p) < m.s32(w + t):
            v = m.s32(w + p) + m.s32(w + s); m.w32(w + p, v)
            if v >= m.s32(w + t): m.w32(w + p, m.s32(w + t))
        if m.s32(w + t) < m.s32(w + p):
            v = m.s32(w + p) - m.s32(w + s); m.w32(w + p, v)
            if v < m.s32(w + t): m.w32(w + p, m.s32(w + t))


@port(0x80022500)
def ctx_init(b, c, canvas, sprite):
    m = b.mem
    m.w32(c, canvas); m.w32(c + 4, sprite)
    for o in (0xC, 8, 0x10, 0x18, 0x1C): m.w32(c + o, 0)
    m.w32(c + 0x14, 2)


@port(0x80022CA8)
def ctx_clear(b, c, upload):
    m = b.mem; cv = m.u32(c)
    h = m.s32(cv + 0x28); w = m.s32(cv + 0x24)
    for y in range(h):
        for x in range(w): canvas_set(b, m.u32(c), x, y, 0)
    if upload == 1: tim_upload(b, m.u32(c), -1, -1, -1, -1, 0)
    m.w32(c + 0xC, 0); m.w32(c + 8, 0)


_KROM = {}


def krom(code):
    """Krom2RawAdd (0x800300C4, the BIOS kanji ROM): the Shift-JIS code's 16 x 15 glyph as 15 rows
    of 16 bits (bit 15 = the left pixel), or None (-1) for a code outside the ROM's two ranges
    (0x8140-0x84BE, 0x889F-0x9872).  The glyphs come from assets/ui/jp/kanji.png (the ROM, written
    by tools/remake_export_jp.py); a code inside the ranges that the sheet lacks is blank.  Without
    the sheet every code answers -1, as before."""
    hit = _KROM.get(code, False)
    if hit is not False: return hit
    rows = None
    if 0x8140 <= code <= 0x84BE or 0x889F <= code <= 0x9872:
        sheet = _KROM.get('sheet', False)
        if sheet is False:
            sheet = None
            try:
                import json
                d = ASSETS / 'ui' / 'jp'
                meta = json.loads((d / 'kanji.json').read_text())
                sheet = (pygame.image.load(str(d / 'kanji.png')), meta['columns'],
                         {int(k, 16): v for k, v in meta['codes'].items()})
            except Exception:
                sheet = None
            _KROM['sheet'] = sheet
        if sheet is not None:
            img, cols, codes = sheet
            rows = [0] * 15
            n = codes.get(code)
            if n is not None:
                ox, oy = (n % cols) * 16, (n // cols) * 16
                for y in range(15):
                    r = 0
                    for x in range(16):
                        if img.get_at((ox + x, oy + y))[3]: r |= 0x8000 >> x
                    rows[y] = r
    _KROM[code] = rows
    return rows


@port(0x80022528)
def kanji(b, c, ch, upload):
    """A two-byte letter from the BIOS kanji font at the context's pen: each set pixel of the
    16 x 16 cell (15 ROM rows, a blank 16th) is ink 6 with shade 3 right, below and diagonally;
    advance 0x11 (0 when Krom2RawAdd answers -1, nothing drawn)."""
    m = b.mem
    x0 = m.s32(c + 8); y0 = m.s32(c + 0xC)
    rows = krom(ch & 0xFFFF)
    if rows is None: return 0
    cv = m.u32(c)
    for y in range(16):
        r = rows[y] if y < 15 else 0
        for x in range(16):
            if r & (0x8000 >> x):
                canvas_set(b, cv, x0 + x, y0 + y, 6)
                canvas_set(b, cv, x0 + x + 1, y0 + y, 3)
                canvas_set(b, cv, x0 + x, y0 + y + 1, 3)
                canvas_set(b, cv, x0 + x + 1, y0 + y + 1, 3)
    if upload == 1: tim_upload(b, cv, -1, -1, -1, -1, 0)
    return 0x11


GLYPHS = 0x80042DF8          # per character 20 bytes: advance, height, u, v, y offset


@port(0x80022718)
def glyph(b, c, ch, upload):
    m = b.mem; ch &= 0xFFFF
    eg = getattr(b, 'eu_glyphs', None)
    if eg is not None:                           # a European disc's 256 letters, x += advance (DE 0x80022440)
        adv, hh, u, v, yo = eg[ch & 0xFF]
        m.w32(0x8014E6F0, u); m.w32(0x8014E6F4, v); m.w32(0x8014E6F8, adv); m.w32(0x8014E6FC, hh); m.w32(0x8014E700, yo)
        canvas_blit(b, m.u32(c), m.s32(c + 8), m.s32(c + 0xC) + yo, 0x801E23C0, u, v, adv, hh)
        if upload == 1: tim_upload(b, m.u32(c), -1, -1, -1, -1, 0)
        m.w32(c + 8, m.s32(c + 8) + adv)
        return adv
    if ch >= 0x80:                               # two-byte letters: the BIOS kanji font
        jp = getattr(b, 'jp', False)
        if jp and krom(ch) is None: ch = 0x8148  # JP 0x80029C88: a code the ROM lacks is drawn as "？"
        v = kanji(b, c, ch, upload)
        # JP layout (SCPS_100.35 0x80029B10): 16 x 16 cells side by side, no gap
        m.w32(0x8014E6F8, v); m.w32(c + 8, m.s32(c + 8) + (16 if jp and v else 1 + v))
        return v
    g = GLYPHS + ch * 0x14
    adv, hh, u, v, yo = (m.s32(g + 4 * k) for k in range(5))
    m.w32(0x8014E6F0, u); m.w32(0x8014E6F4, v); m.w32(0x8014E6F8, adv); m.w32(0x8014E6FC, hh); m.w32(0x8014E700, yo)
    canvas_blit(b, m.u32(c), m.s32(c + 8), m.s32(c + 0xC) + yo, 0x801E23C0, u, v, adv, hh)
    if upload == 1: tim_upload(b, m.u32(c), -1, -1, -1, -1, 0)
    m.w32(c + 8, m.s32(c + 8) + 1 + m.s32(0x8014E6F8))
    return m.s32(0x8014E6F8)


_W = {k: 0x10 + k for k in range(10)}
_W.update({0x11 + k: 0x1A + k for k in range(6)})          # \W0..9 -> 0x10..0x19, \WA..F -> 0x1A..0x1F


def _w_glyph(d):
    return _W.get(d - 0x30, 0x20) if 0 <= d - 0x30 < 0x17 else 0x20


@port(0x8002285C)
def ctx_print(b, c, s, upload):
    """A whole string at once (\\N or \\A: next line; \\W<x>: a button picture)."""
    m = b.mem; p = s
    while m.u8(p):
        ch = m.u8(p)
        if ch == 0x5C:
            d = m.u8(p + 1); p += 2
            if d in (0x4E, 0x41):
                m.w32(c + 8, 0); m.w32(c + 0xC, m.s32(c + 0xC) + 0x10)
            elif d == 0x57:
                k = m.u8(p); p += 1
                glyph(b, c, _w_glyph(k), 0)
            continue
        if ch >= 0x80 and getattr(b, 'eu_glyphs', None) is None:
            ch = (ch << 8) | m.u8(p + 1); p += 2
        else:
            p += 1
        glyph(b, c, ch, 0)
    if upload == 1: tim_upload(b, m.u32(c), -1, -1, -1, -1, 0)


@port(0x80022A2C)
def ctx_scroll(b, c, upload):
    canvas_scroll(b, b.mem.u32(c))
    if upload == 1: tim_upload(b, b.mem.u32(c), -1, -1, -1, -1, 0)


@port(0x80022A8C)
def ctx_type(b, c):
    """One step of typing: a letter every (+0x14) + 1 frames (the talk sound on odd addresses),
    \\N / \\A a new line, scrolling up 16 rows (one a frame) when the canvas is full."""
    m = b.mem
    if m.s32(c + 0x1C):
        m.w32(c + 0x1C, m.s32(c + 0x1C) - 1); m.w32(c + 0xC, m.s32(c + 0xC) - 1)
        ctx_scroll(b, c, 1); return
    cd = m.s32(c + 0x18) - 1; m.w32(c + 0x18, cd)
    if cd != -1: return
    m.w32(c + 0x18, m.s32(c + 0x14))
    p = m.u32(c + 0x10)
    if p == 0 or m.u8(p) == 0: return
    if p & 1: b.sfx(0x4F)
    ch = m.u8(p)
    if ch == 0x5C:
        d = m.u8(p + 1); p += 2
        if d in (0x4E, 0x41):
            m.w32(c + 8, 0); y = m.s32(c + 0xC) + 0x10; m.w32(c + 0xC, y)
            if y >= m.s32(m.u32(c) + 0x28): m.w32(c + 0x1C, 0x10)
        elif d == 0x57:
            k = m.u8(p); p += 1
            glyph(b, c, _w_glyph(k), 1)
        m.w32(c + 0x10, p); return
    if ch >= 0x80 and getattr(b, 'eu_glyphs', None) is None:   # (European texts: one byte a letter)
        ch = (ch << 8) | m.u8(p + 1); p += 2
    else:
        p += 1
    glyph(b, c, ch, 1)
    m.w32(c + 0x10, p)


def text_mods(b, c):
    """Mods > Text speed / Instant text on the book's typing (a remake addition): 1.5x / 2x run
    ctx_type an extra half / whole time a frame; Instant types the rest of the text at once
    (a full canvas still scrolls, a row a frame, before the next letters)."""
    st = getattr(b.g, 'settings', None) or {}
    m = b.mem
    if st.get('instant_text'):
        for _ in range(0x800):
            p = m.u32(c + 0x10)
            if m.s32(c + 0x1C) or p == 0 or m.u8(p) == 0: break
            m.w32(c + 0x18, 0); ctx_type(b, c)
        return
    from settings_screen import EXTRA_PRINTS
    extra = EXTRA_PRINTS.get(st.get('text_speed', 1), 0.0)
    if not extra: return
    acc = b.__dict__.setdefault('_text_extra', {})
    acc[c] = acc.get(c, 0.0) + extra
    while acc[c] >= 1.0:
        acc[c] -= 1.0; ctx_type(b, c)


@port(0x80029F90)
def strncpy(b, dst, src, n):
    m = b.mem; i = 0
    while i < n:
        v = m.u8(src + i); m.w8(dst + i, v); i += 1
        if v == 0: break
    while i < n: m.w8(dst + i, 0); i += 1
    return dst


# ---------------------------------------------------------------- the JP texts (a remake addition)
JP_TEXTS = 0x80180000        # where the JP texts are put in this memory (free here)
_JPT = {}


def jp_texts():
    """{US address: the JP boot program's text (bytes)} from assets/boot/jp_texts.json (written from
    the JP disc's SCPS_100.35 by tools/remake_export_boot_jp.py); {} without it."""
    if 'texts' not in _JPT:
        try:
            import json
            d = json.loads((ASSETS / 'boot' / 'jp_texts.json').read_text(encoding='utf-8'))
            _JPT['texts'] = {int(k, 16): bytes.fromhex(v['sjis']) for k, v in d['texts'].items()}
        except Exception:
            _JPT['texts'] = {}
    return _JPT['texts']


def jp_rows(s):
    """The JP text window's layout (SCPS_100.35 0x800284F8 / 0x800288E0) as this window's text:
    rows of 16 two-byte letters (0x20 bytes each); a run of 0x814F "＾" is shown as full-width
    spaces typed at once (row padding), so each row ends at its last letter here."""
    out = []
    for i in range(0, len(s), 0x20):
        cells = [s[k:k + 2] for k in range(i, min(i + 0x20, len(s)), 2)]
        while cells and cells[-1] in (b'\x81\x4f', b'\x81\x40'): cells.pop()
        out.append(b''.join(b'\x81\x40' if c == b'\x81\x4f' else c for c in cells))
    while out and not out[-1]: out.pop()
    return b'\\N'.join(out)


def txt(b, a):
    """The text at US address a, or its JP counterpart while the JP texts are in use."""
    if getattr(b, 'eu', None): return b.eu_at.get(a, a)
    return getattr(b, 'jp_at', {}).get(a, a) if getattr(b, 'jp', False) else a


# The European discs' History Book texts: their ETC_RES.R numbers for the US boot program's texts
# (same numbers on all five discs; matched by meaning with the English disc's: 0xC4, a second
# "insert a card", has no US counterpart).
EU_TEXT_IDS = {0x800200E4: 0xCA, 0x800200E8: 0xCB, 0x8002010C: 0xC2, 0x80020144: 0xC3, 0x80020190: 0xC5,
               0x800201C4: 0xC6, 0x8002020C: 0xC8, 0x80020258: 0xC1, 0x80020284: 0xC7, 0x8002032C: 0xC9}
EU_LANGS = ('en_eu', 'fr', 'de', 'it', 'es')


def _eu_font(b, lang):
    """The European boot font (TIM 4, same size as the US one) over the US one in the archive, and
    its letters (FR / DE / IT / ES: 256, x += advance; EN: the US 128, + 1); None: back to the US."""
    m = b.mem
    t = archive_find(b, m.u32(0x801F48FC), BASE, 4)
    if not hasattr(b, 'us_font'): b.us_font = bytes(m.u8(t + i) for i in range(32832))
    d = ASSETS / 'title_eu'
    f = None if lang is None else d / ('en' if lang == 'en_eu' else '') / 'font.tim'
    data = f.read_bytes() if f is not None and f.exists() else b.us_font
    for i, v in enumerate(data): m.w8(t + i, v)
    b.eu_glyphs = None
    if lang not in (None, 'en_eu') and (d / 'boot_glyphs.json').exists():
        import json
        b.eu_glyphs = json.loads((d / 'boot_glyphs.json').read_text())
    font_init(b)


def set_lang(b):
    """Options > Language (b.g.lang): Japanese puts the JP boot program's texts in (laid out as
    jp_rows); a European language its disc's texts (ETC_RES.R, EU_TEXT_IDS) and boot font; English
    is the program as it is.  YES / NO are printed again (as text_init).  Nothing is done while
    the language is the one already in use."""
    g = getattr(b, 'g', None); lang = getattr(g, 'lang', 'us')
    eu_t = g.eu_texts(lang) if lang in EU_LANGS and hasattr(g, 'eu_texts') else None
    eu = lang if eu_t and (ASSETS / 'title_eu' / 'font.tim').exists() else None
    jp = lang == 'jp' and bool(jp_texts())
    if jp == b.jp and eu == getattr(b, 'eu', None): return
    m = b.mem
    if eu or getattr(b, 'eu', None): _eu_font(b, eu)
    b.jp = jp; b.eu = eu
    if jp:
        a = JP_TEXTS; b.jp_at = {}
        for us, s in jp_texts().items():
            s = s if us in (0x800200E4, 0x800200E8) else jp_rows(s)
            for k, v in enumerate(s + b'\0'): m.w8(a + k, v)
            b.jp_at[us] = a; a = (a + len(s) + 4) & ~3
    if eu:
        a = JP_TEXTS; b.eu_at = {}
        for us, n in EU_TEXT_IDS.items():
            s = eu_t['etc']['etc'].get(str(n), '').replace(chr(10), '').encode('cp1252', 'replace')
            for k, v in enumerate(s + b'\0'): m.w8(a + k, v)
            b.eu_at[us] = a; a = (a + len(s) + 4) & ~3
    c = 0x801E2620
    ctx_clear(b, c, 0)
    m.w32(c + 8, 0); m.w32(c + 0xC, 0)
    ctx_print(b, c, txt(b, 0x800200E4), 0)                  # "Yes"
    m.w32(c + 8, 0x30); m.w32(c + 0xC, 0)
    ctx_print(b, c, txt(b, 0x800200E8), 1)                  # "No "


# ---------------------------------------------------------------- set-up (boot, before the title)
@port(0x80022488)
def font_init(b):
    m = b.mem
    tim_parse(b, 0x801E23C0, archive_find(b, m.u32(0x801F48FC), BASE, 4))
    m.w16(m.u32(0x801E23CC), 0)                          # palette colour 0 see-through
    tim_upload(b, 0x801E23C0, 0x2C0, 0x100, 0x100, 0x1E1, 0)


@port(0x80022D7C)
def text_init(b):
    """The scroll (TIM 3), the font (TIM 4), three text canvases and their windows: the main
    scroll (256 x 48, at 0x2C0, 0x180), the record's title (256 x 32), YES / NO (96 x 16)."""
    m = b.mem
    font_init(b)
    tim_parse(b, 0x801E23F0, archive_find(b, m.u32(0x801F48FC), BASE, 3))
    tim_upload(b, 0x801E23F0, 0x3C0, 0, 0x110, 0x1E0, 0)
    canvas_init(b, 0x801D1FB8, 0, 0x100, 0x30, 0x8014E704)
    canvas_init(b, 0x801D1FE8, 0, 0x100, 0x20, 0x80150744)
    canvas_init(b, 0x801D2018, 0, 0x60, 0x10, 0x80151F84)
    for y in range(0x100):
        for x in range(0x100):
            for cv in (0x801D1FB8, 0x801D1FE8, 0x801D2018): canvas_set(b, cv, x, y, 0)
    tim_upload(b, 0x801D1FB8, 0x2C0, 0x180, -1, -1, 0)
    tim_upload(b, 0x801D1FE8, 0x2C0, 0x1B0, -1, -1, 0)
    tim_upload(b, 0x801D2018, 0x2C0, 0x1D0, -1, -1, 0)
    for o, vy, ox in ((0x801EFD28, 0, 0), (0x801EFD4C, 0x40, 0xA0), (0x801EFD70, 0x80, 0), (0x801EFD94, 0xC0, 0xA0)):
        obj_init(b, o, 0, -1, 0x3C0, vy, 0xA0, 0x40, 0x110, 0x1E0); obj_ofs(b, o, ox, 0); obj_pos(b, o, 0, 0, 0x64, -1)
    for o, vy, ox in ((0x801EFDB8, 0, 0), (0x801EFDDC, 0x20, 0x40)):
        obj_init(b, o, 0, -1, 0x3F0, vy, 0x40, 0x20, 0x110, 0x1E0); obj_ofs(b, o, ox, 0); obj_pos(b, o, 0, 0, 0x64, -1)
    for o, vy, w, h, ox, oy in ((0x801E24E0, 0x180, 0x100, 0x30, 0x20, 8), (0x801E2548, 0x1B0, 0x100, 0x20, 0x20, 0x10),
                                (0x801E2570, 0x1D0, 0x60, 0x10, 0x10, 8)):
        obj_init(b, o, 0, -1, 0x2C0, vy, w, h, 0x100, 0x1E1); obj_ofs(b, o, ox, oy); obj_pos(b, o, 0, 0, 0x64, -1)
    ctx_init(b, 0x801E25E0, 0x801D1FB8, 0x801E24E0); m.w32(0x801E25F0, 0)
    ctx_init(b, 0x801E2600, 0x801D1FE8, 0x801E2548); m.w32(0x801E2610, 0)
    ctx_init(b, 0x801E2620, 0x801D2018, 0x801E2570); m.w32(0x801E2630, 0)
    m.w32(0x801E2628, 0); m.w32(0x801E262C, 0)
    ctx_print(b, 0x801E2620, 0x800200E4, 0)                 # "Yes"
    m.w32(0x801E2628, 0x30); m.w32(0x801E262C, 0)
    ctx_print(b, 0x801E2620, 0x800200E8, 1)                 # "No "
    win_init(b, 0x801F4958, 0, 0xF0, 0, 4, 0, 0xF0)
    win_init(b, 0x801F4970, 0, 0xF0, 0, 8, 0, 0xF0)
    win_init(b, 0x801F4988, 0x140, 0x90, 0x10, 4, 0x140, 0x90)
    obj_init(b, 0x801F4930, 0, -1, 0x2C0, 0x170, 0x10, 0x10, 0x100, 0x1E1)
    obj_ofs(b, 0x801F4930, 0, 0); obj_pos(b, 0x801F4930, 0xAF, 0x85, 0x78, -1)
    m.w32(0x801E2644, 0); m.w32(0x801E2640, 0)


@port(0x800237B0)
def actors_init(b):
    """TIM 5: Alundra (24 x 40, 4 walk frames x 4 directions) and his shadow, the keeper and
    the light about him, the four books on the lecterns."""
    m = b.mem
    tim_parse(b, 0x801E2070, archive_find(b, m.u32(0x801F48FC), BASE, 5))
    tim_upload(b, 0x801E2070, 0x280, 0, 0, 0x1E1, 0)
    obj_init(b, 0x801EFEE0, 1, -1, 0x280, 0, 0x18, 0x28, 0, 0x1E1); obj_ofs(b, 0x801EFEE0, -0xC, -0x28)
    obj_pos(b, 0x801EFEE0, 0x3C, 0x3C, 0xC, 0)
    obj_init(b, 0x801EFF04, 1, 0, 0x280, 0xA0, 0x18, 0x10, 0, 0x1E1); obj_ofs(b, 0x801EFF04, -0xC, -0xF)
    obj_pos(b, 0x801EFF04, 0x3C, 0x3C, 0xC, 0)
    m.w32(0x801F479C, 0xA0000); m.w32(0x801EFE00, 1); m.w32(0x801EFE10, 1)
    m.w32(0x801F47A0, 0xB4000); m.w32(0x801EFE0C, 0); m.w32(0x801EFE14, -1)
    obj_init(b, 0x801F00A0, 1, -1, 0x280, 0xB0, 0x20, 0x30, 0, 0x1E1); obj_ofs(b, 0x801F00A0, -0x10, -0x18)
    obj_pos(b, 0x801F00A0, 0xA0, 0x60, 0xC, -1)
    obj_init(b, 0x801F00C4, 1, 1, 0x2C4, 0xB0, 0x33, 0x31, 0, 0x1E1); obj_ofs(b, 0x801F00C4, -0x19, -0x15)
    obj_pos(b, 0x801F00C4, 0xA0, 0x60, 0xD, -1)
    for o, prio in ((0x801F00E8, 0xE), (0x801F010C, 0xF)):
        obj_init(b, o, 1, 1, 0x28C, 0xA0, 0x50, 8, 0, 0x1E1); obj_ofs(b, o, -0x28, -1); obj_pos(b, o, 0xA0, 0x60, prio, -1)
    m.w32(0x801F4B60, 0); m.w32(0x801FB02C, 0); m.w32(0x801FB030, 0x3DE)
    for i, ox in enumerate((0x4C, 0x7C, 0xAC, 0xDC)):
        o = 0x801EFE50 + 0x24 * i
        obj_init(b, o, 1, -1, 0x280, 0xE8, 0x18, 0x18, 0, 0x1E1); obj_ofs(b, o, ox, 0x6C); obj_pos(b, o, 0, 0, 0xC, -1)
    for k in range(4): m.w32(0x801F49D0 + 4 * k, 0x800437F8)


@port(0x800240A4)
def room_init(b):
    """TIM 1 (the room, 5 strips of 64 x 240, 8 bits) and TIM 2 (the pillars in front, 64 x 128,
    and the drifting mist, 4 bits, half transparent); the fade (a 320 x 240 polygon)."""
    m = b.mem
    tim_parse(b, 0x801E2390, archive_find(b, m.u32(0x801F48FC), BASE, 1))
    tim_parse(b, 0x801E20A0, archive_find(b, m.u32(0x801F48FC), BASE, 2))
    tim_upload(b, 0x801E2390, 0x300, 0, 0, 0x1E0, 0)
    tim_upload(b, 0x801E20A0, 0x300, 0x180, 0x100, 0x1E0, 0)
    for i in range(5):
        o = 0x801EFFE8 + 0x24 * i
        obj_init(b, o, 1, -1, 0x300 + 0x20 * i, 0, 0x40, 0xF0, 0, 0x1E0); obj_ofs(b, o, 0x40 * i, 0); obj_pos(b, o, 0x40 * i, 0, 0, -1)
    for i in range(5):
        o = 0x801F46E8 + 0x24 * i
        obj_init(b, o, 1, -1, 0x300 + 0x20 * i, 0x100, 0x40, 0x80, 0, 0x1E0); obj_ofs(b, o, 0x40 * i, 0x2A)
        obj_pos(b, o, 0x40 * i, 0, 9, -1)
    for i in range(5):
        o = 0x801EFF28 + 0x24 * i
        obj_init(b, o, 0, 0, 0x300 + 0x10 * i, 0x180, 0x40, 0x80, 0x100, 0x1E0); obj_ofs(b, o, 0x40 * i, 0x78)
        obj_pos(b, o, 0x40 * i, 0, 1, -1)
    tile_init(b, 0x801EFE28, 1, 0x140, 0xF0, 0xFF, 0xFF, 0xFF)
    tile_ofs(b, 0x801EFE28, 0, 0); tile_pos(b, 0x801EFE28, 0, 0, 0xC8)


# ---------------------------------------------------------------- the scene, frame by frame
@port(0x800246E8)
def draw_room(b):
    m = b.mem
    obj_pos(b, 0x801EFFE8, 0, 0, 0, -1); obj_draw_n(b, 0x801EFFE8, 5)
    obj_pos(b, 0x801F46E8, 0, 0, 9, -1); obj_draw_n(b, 0x801F46E8, 5)
    obj_pos(b, 0x801EFF28, m.s16(0x801F48F8), 0, 1, -1); obj_draw_n(b, 0x801EFF28, 5)
    obj_pos(b, 0x801EFF28, s16(m.s32(0x801F48F8) + 0x140), 0, 1, -1); obj_draw_n(b, 0x801EFF28, 5)
    t = m.s32(0x801F4910) + 1; m.w32(0x801F4910, t)
    if t == 4:
        m.w32(0x801F4910, 0); m.w32(0x801F48F8, m.s32(0x801F48F8) - 1)
    if m.s32(0x801F48F8) < -0x13F: m.w32(0x801F48F8, 0)
    f = m.s32(0x801F49E0)
    if f > 0:                                            # fading out: white added
        m.w16(0x801EFE36, 1)
        for a in (0x801EFE30, 0x801EFE2F, 0x801EFE2E): m.w8(a, f)
        tile_draw(b, 0x801EFE28)
    f = m.s32(0x801F49E0)
    if f < 0:                                            # fading in: black taken away
        m.w16(0x801EFE36, 2)
        for a in (0x801EFE30, 0x801EFE2F, 0x801EFE2E): m.w8(a, -f)
        tile_draw(b, 0x801EFE28)


@port(0x80023458)
def draw_windows(b):
    """The three scrolls slide to where the mode (0x801D19AC) wants them, the texts type, and
    the pointing hand turns at YES / NO."""
    m = b.mem
    mode = m.s32(0x801D19AC)
    if mode == 0:
        win_target(b, 0x801F4958, 0, 0xF0); win_target(b, 0x801F4970, 0, 0xF0); win_target(b, 0x801F4988, 0x140, 0x90)
    elif mode == 1:
        win_target(b, 0x801F4958, 0, 0xA8); win_target(b, 0x801F4970, 0, 0xF0); win_target(b, 0x801F4988, 0x140, 0x90)
    elif mode == 2:
        win_target(b, 0x801F4958, 0, 0xA8); win_target(b, 0x801F4970, 0, 0x20)
        if m.u8(m.u32(0x801E25F0)) == 0: win_target(b, 0x801F4988, 0xAF, 0x90)
    (x0, y0), (x1, y1), (x2, y2) = (win_pos(b, w) for w in (0x801F4958, 0x801F4970, 0x801F4988))
    obj_pos(b, 0x801EFD28, x0, y0, 0x64, -1); obj_draw_n(b, 0x801EFD28, 2)
    obj_pos(b, 0x801EFD70, x1, y1, 0x64, -1); obj_draw_n(b, 0x801EFD70, 2)
    obj_pos(b, 0x801EFDB8, x2, y2, 0x64, -1); obj_draw_n(b, 0x801EFDB8, 2)
    obj_pos(b, 0x801E24E0, x0, y0, 0x6E, -1); obj_draw(b, 0x801E24E0)
    obj_pos(b, 0x801E2548, x1, y1, 0x6E, -1); obj_draw(b, 0x801E2548)
    obj_pos(b, 0x801E2570, x2, y2, 0x6E, -1); obj_draw(b, 0x801E2570)
    for c in (0x801E25E0, 0x801E2600, 0x801E2620): ctx_type(b, c); text_mods(b, c)
    for w in (0x801F4958, 0x801F4970, 0x801F4988): win_step(b, w)
    a = m.s32(0x801E2640)
    t = m.s32(0x801E2644) + 1
    m.w16(0x801F4948, a * 4 + 0x2C0); m.w32(0x801E2644, t)
    if t == 9:
        m.w32(0x801E2640, (a + 1) & 3); m.w32(0x801E2644, 0)
    if m.s32(0x801F4988) == 0xAF: obj_draw(b, 0x801F4930)


RECTS = 0x80043828          # {id, x, y, w, h} s16, to an id of -1: 0..3 lecterns, 6 the way out


@port(0x80023C58)
def walk_set(b, standing, d):
    if standing != -1: b.mem.w32(0x801EFE00, standing)
    if d != -1: b.mem.w32(0x801EFE10, d)


def _q12(v): return (v + 0xFFF if v < 0 else v) >> 12


@port(0x80023C84)
def walk_step(b):
    """Alundra's step: 1.5 px up / down, 2 px sideways (20.12); the first rectangle the new
    place would be inside stops him and is the answer."""
    m = b.mem
    if m.s32(0x801EFE00) != 0: return -1
    x, y = m.s32(0x801F479C), m.s32(0x801F47A0)
    d = m.s32(0x801EFE10)
    if d == 1: y -= 0x1800
    elif d == 0: y += 0x1800
    elif d == 2: x -= 0x2000
    elif d == 3: x += 0x2000
    a = RECTS
    while m.s16(a) != -1:
        rx, ry, rw, rh = m.s16(a + 2), m.s16(a + 4), m.s16(a + 6), m.s16(a + 8)
        qx, qy = _q12(x), _q12(y)
        if rx < qx and ry < qy and rx + rw >= qx and ry + rh >= qy: return m.s16(a)
        a += 10
    m.w32(0x801F479C, x); m.w32(0x801F47A0, y)
    return -1


@port(0x80023DD8)
def draw_actors(b):
    m = b.mem
    k = m.s32(0x801EFE0C); m.w32(0x801EFE0C, k + 1)
    m.w16(0x801EFEF8, m.s32(0x801EFE00) * 0x30 + ((k >> 3) & 3) * 0xC + 0x280)    # walking / standing frame
    m.w16(0x801EFEFA, m.s32(0x801EFE10) * 0x28)                                  # facing
    obj_pos(b, 0x801EFEE0, s16(_q12(m.s32(0x801F479C))), s16(_q12(m.s32(0x801F47A0))), 0xC, -1)
    obj_draw_n(b, 0x801EFEE0, 2)
    hit = walk_step(b); m.w32(0x801EFE14, hit)
    t = m.s32(0x801F4B60); m.w32(0x801F4B60, t + 1)
    m.w16(0x801F00B8, ((t * 2) & 0x30) + 0x280)                                  # the keeper's frame
    a = m.s32(0x801F00CC) - 0x16; m.w32(0x801F00CC, a)
    if a == 0x1000: m.w32(0x801F00CC, 0)
    r0, r1 = m.s32(0x801FB02C), m.s32(0x801FB030)
    m.w32(0x801F00F0, r0); m.w32(0x801F0114, r1)
    m.w32(0x801FB02C, r0 + 0xB if r0 + 0xB != 0x1000 else 0)
    m.w32(0x801FB030, r1 + 0xB if r1 + 0xB != 0x1000 else 0)
    obj_draw_n(b, 0x801F00A0, 4 if (t + 1) & 1 else 1)                           # the light every other frame
    for i in range(4):
        slot = 0x801F49D0 + 4 * i
        p = m.u32(slot)
        if p:
            if m.u8(p) == 0: p -= 1; m.w32(slot, p)
            m.w32(slot, p + 1)
            m.w16(0x801EFE68 + 0x24 * i, (m.u8(p) - 0x30) * 0xC + 0x280)            # the book's frame
            obj_draw(b, 0x801EFE50 + 0x24 * i)


@port(0x8002403C)
def crc(b, n, a):
    m = b.mem; c = 0xFFFFFFFF
    if n:
        for i in range(n):
            c ^= m.u8(a + i) << 24
            for _ in range(8): c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else c << 1
            c &= 0xFFFFFFFF
    return ~c & 0xFFFFFFFF


NAMES = 0x80042DEC          # the file names to look for ("BASLUS-00553ALUNDRA ")
US_NAME = b'BASLUS-00553ALUNDRA '     # SLUS_005.53 / US ALUN_CD.EXE
JP_NAME = b'BISCPS-10035ALUNDRA '     # the JP disc's SCPS_100.35 (file +0xB58) / JP ALUN_CD.EXE (+0x738C)
from engine.card import EU_NAMES        # the European discs' save names


def _names(b):
    """The names the remake looks for (a remake addition): the boot program's list (0x80042DEC,
    the US name), then the JP release's (BISCPS-10035) - with Options > Dialogue & font = JP the
    JP name first."""
    m = b.mem; out = []; i = 0
    while True:
        name = m.cstr(m.u32(NAMES + 4 * i))
        if not name: break
        if name not in out: out.append(name)
        i += 1
    if JP_NAME not in out: out.append(JP_NAME)
    for n in EU_NAMES.values():
        if n not in out: out.append(n)
    lang = getattr(getattr(b, 'g', None), 'lang', 'us')
    if lang == 'jp': out.sort(key=lambda n: n != JP_NAME)
    elif lang in EU_NAMES: out.sort(key=lambda n: n != EU_NAMES[lang])
    return out


@port(0x80022228)
def card_read(b):
    """The card in slot 1 (the SLUS card library 0x8002726C / 0x80027378 / 0x80027424 / 0x800274AC
    over the BIOS): 0 or 1 read (1: not the first name), -1 no card / not readable, -2 never
    answers here, -3 no file, -4 too big, -5 a read error."""
    m = b.mem; bios = b.bios
    s = bios.slots[0] if bios is not None else None
    b.lib('card_read')
    if s is None or not s.present: return -1          # 0x8002726C: _card_info times out
    s.new = False                                       # a new card: _new_card + a sector write
    if not s.formatted(): return -1                    # _card_load: an error
    later = 0
    for name in _names(b):
        f = s.find(name[:20])
        if f is not None: break
        later = 1
    else:
        return -3
    head, n = f
    size = n * 0x2000
    if size >= 0x4001: return -4
    blocks = s.chain(head)
    data = b''.join(bytes(s.data[k * 0x2000:(k + 1) * 0x2000]) for k in blocks)[:size]
    for k, v in enumerate(data): m.w8(0x801F7020 + k, v)
    return later


@port(0x800248B4)
def book_open(b, c):
    m = b.mem
    for a in range(0x801F7020, 0x801F9020): m.w8(a, 0)
    r = card_read(b)
    b.lib('pad_reset')
    msg = {-1: 0x8002010C, -2: 0x80020144, -3: 0x80020190, -4: 0x800201C4, -5: 0x800201C4}.get(r, 0)
    if msg:
        m.w32(c + 0x10, txt(b, msg)); return -1
    if crc(b, 0x1FFC, 0x801F7020) != m.u32(0x801F901C):
        m.w32(c + 0x10, txt(b, 0x800201C4)); return -1
    n = 0
    for k in range(4): m.w32(0x801F49D0 + 4 * k, 0)
    for k in range(4):
        if m.u8(0x801F7228 + k * 0x76C):
            n += 1; m.w32(0x801F49D0 + 4 * k, 0x800437F8)
    if n:
        m.w32(c + 0x10, txt(b, 0x80020258)); return 0
    m.w32(c + 0x10, txt(b, 0x8002020C)); return -1


def frame(b, *draws):
    """frame_begin, the drawing routines, frame_end."""
    frame_begin(b)
    for f in draws: f(b)
    yield from frame_end(b)


@port(0x80024A90)
def book_card(b):
    m = b.mem
    ctx_clear(b, 0x801E25E0, 1)
    r = book_open(b, 0x801E25E0)
    b.sfx(4); m.w32(0x801D19AC, 1)
    while True:
        frame_begin(b); pad = b.pad_held(); draw_windows(b)
        yield from frame_end(b)
        if m.u8(m.u32(0x801E25F0)) != 0: continue
        if pad & b.confirm: break
    b.sfx(5); m.w32(0x801D19AC, 0)
    for _ in range(0x3C):
        yield from frame(b, draw_windows)
    return r


@port(0x80024B68)
def book_fade_in(b):
    m = b.mem
    b.music(0x29); b.sfx(0x193)
    m.w32(0x801F49E0, -0xFF)
    while True:
        m.w32(0x801F49E0, m.s32(0x801F49E0) + 8)
        yield from frame(b, draw_room, draw_windows, draw_actors)
        if m.s32(0x801F49E0) >= 0: break
    m.w32(0x801F49E0, 0)


@port(0x80024BF8)
def book_words(b):
    m = b.mem
    m.w32(0x801EFE00, 1)
    ctx_clear(b, 0x801E25E0, 1)
    m.w32(0x801E25F0, txt(b, 0x80020284))
    b.sfx(4); m.w32(0x801D19AC, 1)
    while True:
        frame_begin(b); pad = b.pad_held(); draw_room(b); draw_windows(b); draw_actors(b)
        yield from frame_end(b)
        if m.u8(m.u32(0x801E25F0)) != 0: continue
        if pad & b.confirm: break
    b.sfx(5); m.w32(0x801D19AC, 0)
    for _ in range(0x3C):
        yield from frame(b, draw_room, draw_windows, draw_actors)


@port(0x80024CF0)
def book_walk(b):
    m = b.mem
    while True:
        frame_begin(b)
        pad = b.pad_held()
        if pad & 0x1000: walk_set(b, 0, 1)
        if pad & 0x4000: walk_set(b, 0, 0)
        if pad & 0x8000: walk_set(b, 0, 2)
        if pad & 0x2000: walk_set(b, 0, 3)
        walk_set(b, 0 if pad & 0xF000 else 1, -1)
        draw_room(b); draw_windows(b); draw_actors(b)
        yield from frame_end(b)
        hit = m.s32(0x801EFE14)
        if hit != -1: return hit


@port(0x80024E78)
def book_ask(b, k):
    """Lectern k: its book opens, the record's two title lines show and YES / NO is asked."""
    m = b.mem
    slot = 0x801F49D0 + 4 * k
    if not (k < 4 and m.u32(slot)): return -1
    sel = 0
    b.sfx(4); m.w32(0x801D19AC, 2)
    ctx_clear(b, 0x801E25E0, 1); ctx_clear(b, 0x801E2600, 1)
    rec = k * 0x76C
    m.w32(0x801EFE00, 1)
    m.w32(0x801E25F0, txt(b, 0x8002032C))
    t1, t2 = 0x801FFD00, 0x801FFD28                      # (stack buffers in the original)
    strncpy(b, t1, rec + 0x801F7228, 0x20); m.w8(t1 + 0x20, 0)
    strncpy(b, t2, rec + 0x801F7248, 0x20); m.w8(t2 + 0x20, 0)
    m.w32(0x801E2608, 0); m.w32(0x801E260C, 0)
    ctx_print(b, 0x801E2600, t1, 0)
    m.w32(0x801E2608, 0); m.w32(0x801E260C, 0x10)
    ctx_print(b, 0x801E2600, t2, 1)
    wait = 0xA
    m.w32(slot, 0x800437FC)                               # the book opens
    b.sfx(0x194)
    first = 1
    while True:
        if m.u8(m.u32(slot)) == 0 and first == 1:
            b.sfx(0xCC); first = 0
        m.w16(0x801F4930, (sel * 3) * 0x10 + 0xBF)
        frame_begin(b); draw_room(b); draw_windows(b); draw_actors(b)
        yield from frame_end(b)
        pad = b.pad_held()
        if m.u8(m.u32(0x801E25F0)) != 0: continue
        if m.s32(0x801F4988) != 0xAF: continue
        wait -= 1
        if wait != -1: continue
        wait = 0
        if pad & 0x8000: sel = 0
        if pad & 0x2000: sel = 1
        if pad & b.confirm: break
    b.sfx(2 if sel == 0 else 3); b.sfx(5)
    m.w32(0x801D19AC, 0)
    m.w32(slot, 0x80043820)                               # and closes
    return k if sel == 0 else -1


@port(0x80024DC4)
def book_fade_out(b, k):
    m = b.mem
    b.music_fade_out(1); b.sfx_stop(0x193)
    m.w32(0x801F49E0, 0)
    while True:
        if k == 6: m.w32(0x801F47A0, m.s32(0x801F47A0) + 0x400)
        yield from frame(b, draw_room, draw_windows, draw_actors)
        f = m.s32(0x801F49E0) + 3; m.w32(0x801F49E0, f)
        if f >= 0xFF: break


@port(0x80025124)
def book_main(b):
    m = b.mem
    set_lang(b)                                          # (remake: Options > Dialogue & font)
    m.w32(0x801F479C, 0xA0000); m.w32(0x801F47A0, 0xF0000); m.w32(0x801EFE10, 1)
    for a in (0x801F4910, 0x801F48F8, 0x801F49E0, 0x801EFE00, 0x801EFE0C): m.w32(a, 0)
    m.w32(0x801EFE14, -1)
    r = yield from book_card(b)
    if r != 0: return -1
    yield from book_fade_in(b)
    yield from book_words(b)
    while True:
        k = yield from book_walk(b)
        if k == 6: break
        k = yield from book_ask(b, k)
        if k != -1: break
    yield from book_fade_out(b, k)
    for _ in range(2):
        frame_begin(b); yield from frame_end(b)
    return -1 if k == 6 else k


def boot(b):
    """What boot sets up before the title (0x8002536C): the room, the texts, the actors."""
    room_init(b); text_init(b); actors_init(b)


def record(b, k):
    """The record handed to ALUN_CD.EXE at 0x80010000 (0x8002536C)."""
    return b.mem.bytes(0x801F7220 + k * 0x76C, 0x76C)
