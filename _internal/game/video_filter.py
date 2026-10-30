"""Options > Filter, Scanlines and Brightness: how the 320 x 240 picture is scaled to the window.

Filter
  Sharp     nearest neighbour (every game pixel a block).  ("Crisp" is gone: old settings files
            with "crisp" read as Sharp)
  Smooth    bilinear over the whole picture (soft, like a cheap LCD upscale)
  CRT       nearest to the largest whole multiple, then bilinear for the rest, with a TV's light bleed across each line and an aperture-grille mask
Scanlines   Off / Light / Medium / Heavy: the dark gap under every game line of a 240-line TV
            picture (lined up with the game's lines, whatever the size).
Brightness  Off / Light / Medium / High (shown only with CRT or scanlines on): white light added back for what the scanlines and the CRT
            mask take away (the picture is lifted before the masks darken it).

Speed (CRT lost frames before): the line bleed and the brightness lift are worked at 320 x 240,
before the one upscale, and the grille and the scanlines are one cached mask, so CRT costs one
scale and one multiply at the window's size (it was three scales, an alpha blend and two
multiplies at full size)."""
import pygame

FILTERS = ['sharp', 'smooth', 'crt']
FILTER_NAME = {'sharp': 'Sharp', 'smooth': 'Smooth', 'crt': 'CRT'}
SCANLINES = [0, 1, 2, 3]
SCANLINE_NAME = {0: 'Off', 1: 'Light', 2: 'Medium', 3: 'Heavy'}
SCANLINE_LEVEL = {1: 200, 2: 150, 3: 95}       # the gap's brightness (of 255)
BRIGHTNESS = [0, 3, 1, 2]                      # Off, Light, Medium, High (stored ids kept)
BRIGHTNESS_NAME = {0: 'Off', 3: 'Light', 1: 'Medium', 2: 'High'}
BRIGHT_GAIN = {3: 0.12, 1: 0.25, 2: 0.5}       # picture * (1 + gain), white-clipped
BRIGHT_LIFT = {3: 3, 1: 6, 2: 12}                    # and a little white light on the dark parts
GRILLE = 205

_cache = {}
_work = {}


def norm_filter(f):
    return 'sharp' if f == 'crisp' or f not in FILTERS else f


def _smooth(src, size, dest=None):
    if src.get_bitsize() < 24: src = src.convert(32)
    try:
        return pygame.transform.smoothscale(src, size, dest) if dest is not None else pygame.transform.smoothscale(src, size)
    except (ValueError, pygame.error):
        return pygame.transform.scale(src, size, dest) if dest is not None else pygame.transform.scale(src, size)


def _scale(src, size, dest=None):
    return pygame.transform.scale(src, size, dest) if dest is not None else pygame.transform.scale(src, size)


def _crisp(src, size, dest=None):
    """Nearest to the largest whole multiple, then bilinear for the rest - one axis at a time
    (the vertical step on the 320-wide picture), into kept buffers: the same picture as one
    whole-size bilinear pass, a fraction of its cost (that pass, every frame at a non-whole
    fullscreen size such as 1080 = 4.5 x 240, made fullscreen miss refreshes)."""
    w, h = src.get_size(); W, H = size
    k = max(1, min(W // w, H // h))
    if (w * k, h * k) == (W, H): return _scale(src, size, dest)
    s = src
    if H != h * k:
        s = _scale(s, (w, h * k), _buf('v1', (w, h * k)))
        s = _smooth(s, (w, H), _buf('v2', (w, H)))
    if W != w * k:
        s = _scale(s, (w * k, H), _buf('h1', (w * k, H)))
        return _smooth(s, size, dest)
    return _scale(s, size, dest)


def _mask(size, src_h, level, crt):
    """One multiply mask: the aperture grille (CRT) times the scanline gaps."""
    key = ('m', size, src_h, level, crt)
    m = _cache.get(key)
    if m is None:
        if len(_cache) > 8: _cache.clear()
        W, H = size
        m = pygame.Surface(size); m.fill((255, 255, 255))
        if crt:
            col = pygame.Surface((3, 1))
            for x, c in enumerate(((255, GRILLE, GRILLE), (GRILLE, 255, GRILLE), (GRILLE, GRILLE, 255))):
                col.set_at((x, 0), c)
            row = pygame.Surface((W, 1))
            for x in range(0, W, 3): row.blit(col, (x, 0))
            m = pygame.transform.scale(row, (W, H))
        if level in SCANLINE_LEVEL:
            sl = pygame.Surface(size); sl.fill((255, 255, 255))
            g = SCANLINE_LEVEL[level]; mid = (g + 255) // 2
            for i in range(src_h):
                y0 = i * H // src_h; y1 = (i + 1) * H // src_h; n = y1 - y0
                if n <= 1:
                    if i & 1: sl.fill((g, g, g), (0, y0, W, max(1, n)))
                    continue
                gap = max(1, n // 2) if n < 4 else max(1, n * 2 // 5)
                sl.fill((g, g, g), (0, y1 - gap, W, gap))
                if n >= 4: sl.fill((mid, mid, mid), (0, y1 - gap - 1, W, 1))       # a soft edge
            m.blit(sl, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        _cache[key] = m
    return m


def _buf(name, size):
    b = _work.get(name)
    if b is None or b.get_size() != size:
        b = _work[name] = pygame.Surface(size).convert() if pygame.display.get_surface() else pygame.Surface(size)
    return b


def _prepare(src, crt, bright):
    """The 320 x 240 work: the beam's bleed along each line (CRT) and the brightness lift."""
    if not crt and not bright: return src
    w, h = src.get_size()
    out = _buf('out', (w, h)); out.blit(src, (0, 0))
    if crt:
        soft = _smooth(_smooth(src, (w // 2, h)), (w, h))
        soft.set_alpha(90); out.blit(soft, (0, 0))
    if bright:
        add = _buf('add', (w, h)); add.blit(out, (0, 0))
        k = int(255 * BRIGHT_GAIN[bright])
        add.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
        out.blit(add, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        l = BRIGHT_LIFT[bright]
        out.fill((l, l, l), special_flags=pygame.BLEND_RGB_ADD)
    return out


def upscale(src, size, settings, dest=None):
    """src scaled to size the way the options ask (into dest, a surface of that size, if given)."""
    size = (int(size[0]), int(size[1]))
    if dest is not None and dest.get_size() != size: dest = None
    f = norm_filter(settings.get('filter', 'sharp')); sl = settings.get('scanlines', 0)
    crt = f == 'crt'
    lines = sl in SCANLINE_LEVEL and size[1] >= src.get_height() * 2
    masked = crt or lines
    bright = settings.get('brightness', 0) if masked else 0     # only what the masks take away
    if bright not in BRIGHT_GAIN: bright = 0
    pic = _prepare(src, crt, bright)
    if f == 'smooth': out = _smooth(pic, size, dest)
    elif crt: out = _crisp(pic, size, dest)
    else: out = _scale(pic, size, dest)
    if masked:
        out.blit(_mask(size, src.get_height(), sl if lines else 0, crt), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return out


def masks_on(settings):
    """CRT or scanlines chosen: Brightness compensation has something to make up for."""
    return norm_filter(settings.get('filter', 'sharp')) == 'crt' or settings.get('scanlines', 0) in SCANLINE_LEVEL
