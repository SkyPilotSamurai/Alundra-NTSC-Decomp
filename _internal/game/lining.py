"""Map background / foreground layers ("lining"), drawn the way the game does
(EXE 0x8005B670 RenderAllTileLayers, 0x8005B848 RenderLayerToBuffer,
0x8005BA40 RenderTileOverlayLayer; xcasadio GraphicManager.cs).

Mode 1 (scroller): a 40x30 map of 16x16 tiles wrapping at 640x480, scrolled by
camera * num/den plus its own drift.  Mode 2 (cellular): up to 200 free pieces
(clouds, fog, rain) that drift, wrap at the screen, respawn at the top (type 2) or
sway on a sine table (type 4).  Layers with ground=0 are behind the map, others in
front.  An optional colour overlay (flag < 0x65 flat at 50%, else 4-corner at 25%)
cycles through its frames."""
import json, random
import pygame

W, H = 320, 240


class Lining:
    def __init__(self, folder):
        f = folder / 'lining.json'
        self.ok = f.exists()
        if not self.ok: return
        self.info = json.loads(f.read_text())
        img = folder / 'lining.png'; st = folder / 'lining_st.png'
        self.sheet = pygame.image.load(str(img)).convert_alpha() if img.exists() else None
        self.st = pygame.image.load(str(st)).convert_alpha() if st.exists() else None
        self.st_dim = None
        if self.st is not None:
            self.st_dim = self.st.copy(); self.st_dim.fill((64, 64, 64, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self.st_half = self.st.copy(); self.st_half.fill((255, 255, 255, 128), special_flags=pygame.BLEND_RGBA_MULT)
            self.st5 = _five_bit(self.st)        # the texels as the GPU adds them: 0..31 a channel
        self._acc = None                        # an adding / subtracting layer's sum (5-bit units)
        self.mode_mask = 3                      # command A4 can change it; map load sets 3
        n = len(self.info['layers'])
        self.anim_timer = [0] * n; self.anim_frame = [0] * n
        self.off = [[0, 0] for _ in range(n)]; self.timer = [[0, 0] for _ in range(n)]
        self.dirs = []
        for lay in self.info['layers']:
            sc = lay.get('scroll') or [0] * 8
            dx = (1 if (sc[4] >= 0) ^ (sc[5] < 0) else -1) if sc[5] else 0
            dy = (1 if (sc[6] >= 0) ^ (sc[7] < 0) else -1) if sc[7] else 0
            self.dirs.append((dx, dy))
        self.cells = []
        for lay in self.info['layers']:
            cells = lay.get('cells') or []
            div = (lay.get('cellular') or [0] * 8)[7]
            self.cells.append([[c['x0'], c['y0'], 0, 0] for c in cells[:max(div, len(cells))]])
        self.wave_tick = [0] * n
        self.clock = None                       # set by the game: its frame count since boot
        self.ovr_off = 0; self.ovr_tick = 0; self.ovr_hold = 0
        self.cache = {}

    # -- drawing helpers ---------------------------------------------------
    def piece(self, surf, blend, pal, u, v, w, h, x, y):
        u &= 255; v &= 255
        # the sheet wraps at 256 in u and v: draw in up to 4 parts
        for (pu, pw, ox) in ((u, min(w, 256 - u), 0), (0, w - (256 - u), 256 - u)) if u + w > 256 else ((u, w, 0),):
            for (pv, ph, oy) in ((v, min(h, 256 - v), 0), (0, h - (256 - v), 256 - v)) if v + h > 256 else ((v, h, 0),):
                if pw <= 0 or ph <= 0: continue
                r = pygame.Rect(pu, pal * 256 + pv, pw, ph); at = (x + ox, y + oy)
                surf.blit(self.sheet, at, r)
                if self.st is not None and blend:
                    if blend == 1:
                        surf.blit(self.st_half, at, r)
                    elif blend in (2, 3) and self._acc is not None:
                        self._acc.blit(self.st5, at, r, special_flags=pygame.BLEND_RGB_ADD)
                    elif blend == 2: surf.blit(self.st, at, r, special_flags=pygame.BLEND_RGB_ADD)
                    elif blend == 3: surf.blit(self.st, at, r, special_flags=pygame.BLEND_RGB_SUB)
                    elif blend == 4: surf.blit(self.st_dim, at, r, special_flags=pygame.BLEND_RGB_ADD)
                elif self.st is not None:
                    surf.blit(self.st, at, r)

    def step(self, k, lay):
        num = self.info['anim_num'] or 1
        self.anim_timer[k] += 1
        if self.anim_timer[k] > lay.get('anim_timer', 0):
            self.anim_frame[k] = (self.anim_frame[k] + 1) % num; self.anim_timer[k] = 0
        return (self.anim_frame[k] << 8) // num

    def draw_layer(self, surf, k, cam_x, cam_y):
        lay = self.info['layers'][k]; mode = lay.get('mode', 0); blend = lay.get('blend', 0)
        if mode == 1:
            fxn, fxd, fyn, fyd, sx, px, sy, py = lay['scroll']
            if not fxd or not fyd or not lay.get('map'): return
            vanim = self.step(k, lay)
            par_x = int(cam_x * fxn / fxd); par_y = int(cam_y * fyn / fyd)
            o = self.off[k]; t = self.timer[k]
            t[0] += 1; o[0] += sx
            if px and t[0] >= abs(px): o[0] += self.dirs[k][0]; t[0] = 0
            t[1] += 1; o[1] += sy
            if py and t[1] >= abs(py): o[1] += self.dirs[k][1]; t[1] = 0
            X = (o[0] + par_x) % 640; Y = (o[1] + par_y) % 480
            tx, ty, subx, suby = X >> 4, Y >> 4, X & 15, Y & 15
            m = lay['map']
            for yy in range((H + suby + 15) >> 4):
                r = (ty + yy) % 30
                for xx in range((W + subx + 15) >> 4):
                    c = (tx + xx) % 40; i = r * 80 + c * 2
                    tile = m[i]
                    if not tile: continue
                    self.piece(surf, blend, m[i + 1] & 7, (tile & 15) << 4, ((tile & 0xF0) + vanim) & 255, 16, 16,
                               xx * 16 - subx, yy * 16 - suby)
        elif mode == 2:
            cells = lay.get('cells') or []
            if not cells: return
            phase = self.step(k, lay)
            clock = self.clock
            # the sway follows the console's vertical-blank count since power-on (VSync(-1); the
            # recompiled game: 0x800CB54C, not reset by a map change), not a count of its own
            self.wave_tick[k] = (clock() & 255) if clock is not None else (self.wave_tick[k] + 1) & 255
            cel = lay.get('cellular') or [0] * 8; lut = self.info.get('wave_lut') or []
            state = self.cells[k]
            for i, c in enumerate(cells[:200]):
                w, h = c['u1'] - c['u0'] + 1, c['v1'] - c['v0'] + 1
                if c['type'] in (0, 2):
                    if i >= len(state): state.append([c['x0'], c['y0'], 0, 0])
                    s = state[i]; s[0] += c['dx']; s[1] += c['dy']
                    stepx = (-1 if c['dx'] < 0 or c['px'] < 0 else 1) if c['px'] else 0
                    stepy = (-1 if c['dy'] < 0 or c['py'] < 0 else 1) if c['py'] else 0
                    if c['px']:
                        s[2] += 1
                        if s[2] >= abs(c['px']): s[0] += stepx; s[2] = 0
                    if c['py']:
                        s[3] += 1
                        if s[3] >= abs(c['py']): s[1] += stepy; s[3] = 0
                    cxn, cxd, cyn, cyd = c['cam']
                    bx = int(cam_x * cxn / cxd) if cxd else 0; by = int(cam_y * cyn / cyd) if cyd else 0
                    x, y = s[0] - bx, s[1] - by
                    minx = c['u0'] - c['u1']
                    if x < minx: s[0] += W - minx; x = s[0] - bx
                    elif x > W - 1: s[0] += -W + minx; x = s[0] - bx
                    miny = c['v0'] - c['v1']
                    if c['type'] == 0:
                        if y < miny: s[1] += H - miny; y = s[1] - by
                        elif y > H - 1: s[1] += -H + miny; y = s[1] - by
                    elif y > H - 1:
                        s[0] = random.randrange(W); s[1] += -H + miny; x, y = s[0] - bx, s[1] - by
                    self.piece(surf, blend, c['pal'] & 7, c['u0'], (c['v0'] + phase) & 255, w, h, x, y)
                elif c['type'] == 4 and lut:
                    a1 = (c['y0'] * cel[1]) & 255; a2 = (self.wave_tick[k] * cel[2]) & 255
                    aw = lut[a1] * lut[a2] * cel[3]
                    if aw < 0: aw += 0x7F
                    b = (c['y0'] * cel[4] + self.wave_tick[k] * cel[5]) & 255
                    t = (aw >> 7) + lut[b] * cel[6]
                    if t < 0: t += 0x7F
                    self.piece(surf, blend, c['pal'] & 7, c['u0'], (c['v0'] + phase) & 255, w, h, c['x0'] + (t >> 7) - 8, c['y0'])

    def draw(self, surf, cam_x, cam_y, front):
        """front=False: the layers behind the map; True: layers over it, then the overlay."""
        if not self.ok or self.sheet is None and not front: return
        if self.sheet is not None and self.info.get('has_graphics'):
            # 0x8005D8F4 adds layer 0 and then layer 1 to the same ordering-table list (0x8005DA44:
            # the behind or the in-front list by the layer's ground byte); the GPU draws a list's
            # last added primitive first, so layer 1 is drawn first and layer 0 over it (map 1's
            # bright clouds over its half-transparent dim band: the giant-tree view)
            for k in reversed(range(len(self.info['layers']))):
                lay = self.info['layers'][k]
                if not (self.mode_mask >> k) & 1 or not lay.get('mode'): continue
                if bool(lay.get('ground')) != front: continue
                blend = lay.get('blend', 0)
                if blend in (2, 3) and getattr(self, 'st5', None) is not None:
                    # the GPU adds (B + F) or subtracts (B - F) in 5 bits a channel, clamped to
                    # 0..31; with pieces only adding or only subtracting the order does not
                    # matter, so the pieces are summed first, then applied once
                    if self._acc is None or self._acc.get_size() != surf.get_size():
                        self._acc = pygame.Surface(surf.get_size())
                    self._acc.fill((0, 0, 0))
                    self.draw_layer(surf, k, cam_x, cam_y)
                    _apply(surf, self._acc, blend == 3)
                    self._acc.fill((0, 0, 0))
                else:
                    saved, self._acc = self._acc, None
                    self.draw_layer(surf, k, cam_x, cam_y)
                    self._acc = saved
        if front and self.info.get('overlay_flag') and self.info.get('overlay'):
            self.draw_overlay(surf)

    def draw_overlay(self, surf):
        frames = self.info['overlay']; ext = self.info.get('overlay_ext')
        size = 1
        self.ovr_tick += 1
        if self.ovr_tick >= self.ovr_hold:
            if self.ovr_off >= len(frames): self.ovr_off = 0
            self.ovr_hold = frames[self.ovr_off][12 if ext else 3]
            self.ovr_tick = 0; self.ovr_off += size
            if self.ovr_hold == 0: self.ovr_off = 0
        fr = frames[max(0, self.ovr_off - 1)]
        alpha = 64 if ext else 128
        key = (tuple(fr[:12] if ext else fr[:3]), alpha)
        ov = self.cache.get(key)
        if ov is None:
            if ext:
                small = pygame.Surface((2, 2)); small.set_at((0, 0), fr[0:3]); small.set_at((1, 0), fr[3:6])
                small.set_at((0, 1), fr[6:9]); small.set_at((1, 1), fr[9:12])
                ov = pygame.transform.smoothscale(small, (W, H))
            else:
                ov = pygame.Surface((W, H)); ov.fill(fr[:3])
            ov.set_alpha(alpha); self.cache = {key: ov}
        surf.blit(ov, (0, 0))


def _five_bit(img):
    """A copy with each colour channel as its 5-bit value (v >> 3), alpha kept."""
    out = img.copy()
    try:
        import numpy as np
        a = pygame.surfarray.pixels3d(out); a >>= 3; del a
    except ImportError:
        pass
    return out


def _apply(surf, acc, sub):
    """surf := 5-bit (surf +/- acc) clamped to 0..31 and widened to 8 bits as the remake shows
    colours (c << 3 | c >> 2), inside surf's clip."""
    try:
        import numpy as np
    except ImportError:
        surf.blit(acc, (0, 0), special_flags=pygame.BLEND_RGB_SUB if sub else pygame.BLEND_RGB_ADD); return
    r = surf.get_clip()
    if r.w <= 0 or r.h <= 0: return
    dst = pygame.surfarray.pixels3d(surf)[r.x:r.right, r.y:r.bottom]
    add = pygame.surfarray.array3d(acc)[r.x:r.right, r.y:r.bottom].astype(np.int16)
    if not add.any(): return
    v = (dst >> 3).astype(np.int16)
    v = v - add if sub else v + add
    np.clip(v, 0, 31, out=v)
    dst[...] = ((v << 3) | (v >> 2)).astype(np.uint8)

