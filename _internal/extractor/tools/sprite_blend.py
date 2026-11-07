"""Sprite frames drawn the way the PlayStation draws them, blending included.

Native rule (ALUN_CD.EXE 0x8002DEAC, the sprite-piece -> POLY_FT4 builder):
each 14-byte piece starts with a 'sheet' byte:
    bits 0-2  texture page
    bit  3    semi-transparent (primitive code |= 2)
    bits 4-5  blend mode, selecting the tpage row at 0x801F2E10 + mode*44:
              0 = 50% back + 50% sprite, 1 = back + sprite (additive),
              2 = back - sprite, 3 = back + 25% sprite
The GPU only blends texels whose colour has bit 15 (STP) set; other non-zero
texels of a semi-transparent piece are opaque, and colour 0 is never drawn.

compose(preview, pos, count) -> (layers, left, top) where layers is a dict of
same-sized RGBA images: 'normal' (opaque pixels, 50% blends as alpha 128),
'add' (to add on top: additive and 25% pieces) and 'sub' (to subtract).
"""
from PIL import Image
import numpy as np


def _palette(preview, palette):
    cache = preview.__dict__.setdefault('blend_palettes', {})
    if palette not in cache:
        start = preview.start + preview.header[5] + palette * 32
        if start + 32 > preview.start + preview.header[6]: raise ValueError('Palette outside table')
        words = preview.read('16H', start)
        rgb = np.array([[(v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31] for v in words], np.uint8)
        drawn = np.array([v != 0 for v in words]); stp = np.array([bool(v & 0x8000) for v in words])
        cache[palette] = rgb, drawn, stp
    return cache[palette]


def _piece_indices(preview, sheet, sx, sy, w, h):
    from entity_preview import indexed_sprite_page, unpack_ez
    if preview.raw is None:
        preview.raw = unpack_ez(bytes(preview.data[preview.sheet_start:preview.sheet_end]), limit=262144)[0]
    pages = preview.__dict__.setdefault('indexed_pages', {})
    page = sheet & 7
    if page not in pages: pages[page] = indexed_sprite_page(preview.raw, page)
    return pages[page].crop((sx, sy, min(256, sx + w), min(256, sy + h)))


def _page_array(preview, sheet):
    """The whole 256 x 256 texture page of a piece as palette indices (numpy, [v, u])."""
    arrays = preview.__dict__.setdefault('indexed_page_arrays', {})
    page = sheet & 7
    if page not in arrays:
        full = _piece_indices(preview, sheet, 0, 0, 256, 256)
        a = np.zeros((256, 256), np.uint8); f = np.array(full, dtype=np.uint8)
        a[:f.shape[0], :f.shape[1]] = f
        arrays[page] = a
    return arrays[page]


def _as_l(image):
    """Palette indices as a greyscale image (never converted through colours)."""
    return Image.fromarray(np.array(image, dtype=np.uint8), 'L')


def _transform(image, corners, w, h):
    from entity_preview import _solve
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    left, top = min(xs), min(ys); bw, bh = max(1, max(xs) - left), max(1, max(ys) - top)
    rows = []; rhs = []
    for (dx, dy), (u, v) in zip(corners, ((0, 0), (w, 0), (0, h), (w, h))):
        dx -= left; dy -= top
        rows.append([dx, dy, 1, 0, 0, 0, -u * dx, -u * dy]); rhs.append(u)
        rows.append([0, 0, 0, dx, dy, 1, -v * dx, -v * dy]); rhs.append(v)
    coeffs = _solve(rows, rhs)
    if coeffs is None: return left, top, None
    return left, top, image.transform((bw, bh), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.NEAREST)


def _pieces(preview, pos, count):
    out = []
    for i in range(count):
        sheet, palette, sx, sy, w, h, x1, y1, x2, y2, x3, y3, x4, y4 = preview.read('6B8b', pos + 2 + i * 14)
        if not w or not h: continue
        # palette index image ('P' via 'L'), carried through the same geometry as the colours
        idx = _as_l(_piece_indices(preview, sheet, sx, sy, w, h))
        if x1 != x3 or x2 != x4 or y1 != y2 or y3 != y4:
            left, top, im = _transform(idx, ((x1, y1), (x2, y2), (x3, y3), (x4, y4)), w, h)
            mask_left, _, mask = _transform(Image.new('L', idx.size, 255), ((x1, y1), (x2, y2), (x3, y3), (x4, y4)), w, h)
            if im is None: continue
            ind = np.array(im); inside = np.array(mask) > 0
        else:
            # an axis-aligned quad (flipped and / or scaled): each screen pixel takes the texel the
            # GPU interpolates from the vertices, u = sx + floor((x - x1) * w / (x2 - x1) + 1/2), v alike
            # (the right / bottom edge is not drawn).  This also gives the flipped pieces' one-texel
            # shift (u starts at sx + 1).  A flip-then-resize with nearest-neighbour picked other
            # texels: sprite 21's Fire Book storm lost its middle column (images 2305 / 2369 / 2412).
            dw, dh = abs(x2 - x1), abs(y3 - y1)
            if not dw or not dh: continue
            left, top = min(x1, x2), min(y1, y3)
            X = np.arange(left, left + dw); Y = np.arange(top, top + dh)
            U = np.clip(sx + np.floor((X - x1) * w / (x2 - x1) + 0.5).astype(int), 0, 255)
            V = np.clip(sy + np.floor((Y - y1) * h / (y3 - y1) + 0.5).astype(int), 0, 255)
            page = _page_array(preview, sheet)
            ind = page[V[:, None], U[None, :]]; inside = np.ones(ind.shape, bool)
        rgb, drawn, stp = _palette(preview, palette)
        ind = np.clip(ind, 0, 15)
        out.append(dict(left=left, top=top, rgb=rgb[ind], drawn=drawn[ind] & inside, stp=stp[ind] & inside,
                        semi=bool(sheet & 8), mode=(sheet >> 4) & 3))
    return out


def compose(preview, pos, count):
    pieces = _pieces(preview, pos, count)
    if not pieces: raise ValueError('Empty sprite')
    left = min(p['left'] for p in pieces); top = min(p['top'] for p in pieces)
    right = max(p['left'] + p['rgb'].shape[1] for p in pieces); bottom = max(p['top'] + p['rgb'].shape[0] for p in pieces)
    H, W = bottom - top, right - left
    normal = np.zeros((H, W, 4), np.float64); add = np.zeros((H, W, 3), np.float64); sub = np.zeros((H, W, 3), np.float64)
    # the ordering table draws the last record first (see entity_preview.compose_images)
    for p in reversed(pieces):
        y, x = p['top'] - top, p['left'] - left; h, w = p['rgb'].shape[:2]
        rgb = p['rgb'].astype(np.float64); drawn = p['drawn']
        blend = drawn & p['stp'] if p['semi'] else np.zeros_like(drawn)
        solid = drawn & ~blend
        region = normal[y:y + h, x:x + w]
        region[solid, :3] = rgb[solid]; region[solid, 3] = 255
        add[y:y + h, x:x + w][solid] = 0; sub[y:y + h, x:x + w][solid] = 0
        if blend.any():
            if p['mode'] == 0:            # 50/50: exact as alpha 128 over anything
                a = region[blend, 3:4] / 255
                # over an existing solid pixel: average it; over nothing: half alpha
                region[blend, :3] = np.where(a > 0, (region[blend, :3] + rgb[blend]) / 2, rgb[blend])
                region[blend, 3] = np.where(a[:, 0] > 0, 255, 128)
            elif p['mode'] == 1:
                add[y:y + h, x:x + w][blend] += rgb[blend]
            elif p['mode'] == 3:
                add[y:y + h, x:x + w][blend] += rgb[blend] / 4
            else:
                sub[y:y + h, x:x + w][blend] += rgb[blend]
    layers = {'normal': Image.fromarray(np.clip(normal, 0, 255).astype(np.uint8), 'RGBA')}
    for name, arr in (('add', add), ('sub', sub)):
        if arr.any():
            a = np.clip(arr, 0, 255).astype(np.uint8)
            alpha = (a.max(axis=2) > 0).astype(np.uint8) * 255
            layers[name] = Image.fromarray(np.dstack([a, alpha]), 'RGBA')
    return layers, left, top


def image_set_layers(preview, sprite, image_set_index):
    table, stop = preview.header[3:5]
    pointer = preview.read('i', preview.start + table + sprite * 4)[0]
    if pointer <= 0: raise ValueError('Sprite unavailable')
    frames = preview.read('4I', preview.start + pointer)[3]
    pos = preview.start + frames + image_set_index * 2
    _, count = preview.read('2B', pos)
    if not 0 < count <= 64: raise ValueError('Unsupported frame image count')
    return compose(preview, pos, count)


def preview_on(layers, background=(40, 40, 48)):
    """One flat picture of how the frame looks in game over a plain background."""
    n = layers['normal']; base = Image.new('RGBA', n.size, background + (255,))
    base.alpha_composite(n)
    arr = np.array(base).astype(np.int32)
    if 'add' in layers: arr[..., :3] += np.array(layers['add'])[..., :3]
    if 'sub' in layers: arr[..., :3] -= np.array(layers['sub'])[..., :3]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
