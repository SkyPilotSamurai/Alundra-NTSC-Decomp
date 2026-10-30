"""Effect sprites (EffectManager / SpriteEffect): shadows, hit puffs, splashes, dust,
sparkles.  An effect plays one animation of a global or map effect bank; a frame
delay of 0 ends it, 1 loops (exported 'change' / 'hold').  Update modes: 0 free
(moves by its force), 1 attached to an entity (+ offset), 3 detached (moves by its
force, sorted with its entity).  Entity shadows are effect records too (mode 3, made
and placed by engine/shadows.py, 0x80039788)."""
import json
import pygame
import packs

ONE = 0x10000


class Bank:
    cache = {}

    def __init__(self, folder):
        self.folder = folder
        f = folder / 'animations.json'
        self.meta = json.loads(f.read_text()) if f.exists() else {'animations': []}
        self.images = {}

    @classmethod
    def get(cls, folder):
        if folder not in cls.cache: cls.cache[folder] = Bank(folder)
        return cls.cache[folder]

    def anim(self, i):
        a = self.meta['animations']
        return a[i] if 0 <= i < len(a) else None

    def preload(self):
        for a in self.meta.get('animations', []):
            for f in a.get('frames', []):
                if f.get('image') is not None: self.image(f['image'])

    _raw = {}                           # path -> picture decoded ahead (Sprite.prefetch_globals)

    def prefetch_files(self):
        return [self.folder / f'{f["image"]}{t}.png' for a in self.meta.get('animations', []) for f in a.get('frames', [])
                if f.get('image') is not None and f['image'] not in self.images
                for t in [''] + ['_' + n for n in self.meta.get('blend', {}).get(str(f['image']), [])]]

    @staticmethod
    def _decoded(p):
        img = Bank._raw.pop(p, None)
        return img if img is not None else packs.load(p)

    def image(self, index):
        if index not in self.images:
            p = self.folder / f'{index}.png'
            img = self._decoded(p)
            self.images[index] = img.convert_alpha() if img is not None else None
            layers = []
            for name in self.meta.get('blend', {}).get(str(index), []):
                q = self.folder / f'{index}_{name}.png'
                img = self._decoded(q)
                if img is not None:
                    layers.append((img.convert_alpha(),
                                   pygame.BLEND_RGB_ADD if name == 'add' else pygame.BLEND_RGB_SUB))
            self.images[('l', index)] = layers
        return self.images[index], self.images[('l', index)]


def _s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


class Effect:
    """One of the 128 effect records (0x80133990, engine/layout.py EFFECT) plus what the
    remake needs to draw it (bank, frame, delay).  state 0 = free slot."""
    def __init__(self, slot):
        from engine.layout import EFFECT
        for n in EFFECT: setattr(self, n, 0)
        self.slot = slot; self.entity = None
        self.bank = None; self.anim = 0; self.frame = 0; self.delay = 0; self.map_id = -1; self.pos = 0

    @property
    def dead(self): return self.state == 0
    @dead.setter
    def dead(self, v):
        if v: self.state = 0

    def start(self, bank, anim):
        self.bank = bank; self.anim = anim; self.frame = 0; self.map_id = -1
        a = bank.anim(anim) if bank else None
        if not a or not a['frames']: self.state = 0
        else: self.delay = a['frames'][0]['ticks']

    # ---- UpdateEffects 0x8003CDF4: animation 0x8003C548, movement 0x8003CC64
    def update_anim(self, effects):
        if self.index != self.nindex or self.b6c != self.b6d:        # bank chosen / changed
            bank = effects.bank(bool(self.b6c), self.index)
            if bank is None or not bank.meta.get('animations'):
                self.b7d = 1; self.bank = None; self.f20 = 0; self.f24 = 0; return
            self.bank = bank; self.b6d = self.b6c; self.nindex = self.index
            self.b71 = (~self.b70) & 0xFF
        if self.b70 != self.b71:                                     # animation (re)started
            self.b71 = self.b70; self.b7c = 0; self.b7d = 0; self.anim = self.b70; self.pos = 0
            self._read()
        else:
            self.b7c = (self.b7c - 1) & 0xFF
            if self.b7c == 0: self._read()

    def _read(self):
        for _ in range(64):
            a = self.bank.anim(self.anim) if self.bank else None
            frames = a['frames'] if a else []
            if self.pos < len(frames):
                f = frames[self.pos]; self.frame = self.pos; self.pos += 1
                self.b7c = f['ticks'] & 0x7F
                self.f20 = f.get('sort', 0)              # the image set's first byte: its sort bias
                return
            end = a.get('end') if a else 'change'
            if end == 'hold' and a.get('next') == 1:                 # terminator 1: loop
                self.pos = 0; continue
            self.b7c = 0xFF; self.b7d = 1                            # terminator 0: finished
            return
        self.b7d = 1

    def move(self):
        """0x8003CC64: movement and the sort key (+0x64) the drawing order uses: a free effect
        sorts by its own y / z (+ bias +0x20 rows), one tied to an entity by that entity's
        key (+0x1BC) + its bias (+0x60)."""
        m = self.mode
        if m == 0:
            self.x = _s32(self.x + self.vx); self.z = _s32(self.z + self.vz); self.y = _s32(self.y + self.vy)
            self.f64 = _s32((self.y & ~0xFFFF) + (self.z >> 16) + (self.f20 << 16))
            return
        if m == 1:
            e = self.entity
            st = getattr(e, 'estatus', 0) if e is not None else 0    # the status word (+0x10), not 'alive'
            if st == 0:
                self.mode = 2
            else:
                self.x = _s32(e.px + self.ox); self.y = _s32(e.py + self.oy); self.z = _s32(e.pz + self.oz)
                self.f64 = _s32(getattr(e, 'sort_key', 0) + self.arg60)
                if st == 4: self.mode = 2
            m = 3
        if m == 3:
            e = self.entity
            self.x = _s32(self.x + self.vx); self.y = _s32(self.y + self.vy); self.z = _s32(self.z + self.vz)
            st = getattr(e, 'estatus', 0) if e is not None else 0    # the status word (+0x10), not 'alive'
            if st == 0:
                self.mode = 2
            else:
                self.f64 = _s32(getattr(e, 'sort_key', 0) + self.arg60)
                if st == 4: self.mode = 2

    def draw(self, surf, cam, margin):
        if self.bank is None: return
        a = self.bank.anim(self.anim)
        if not a or self.frame >= len(a['frames']): return
        f = a['frames'][self.frame]
        if f.get('image') is None: return
        img, layers = self.bank.image(f['image'])
        if img is None: return
        sx = (self.x >> 16) - cam[0] + f['left']                # 0x8002DEAC: screen y = (y - z) >> 16, so a z with
        sy = ((self.y - self.z) >> 16) + margin - cam[1] + f['top']   # the +1 fraction (floors, spawns) is a pixel higher
        surf.blit(img, (sx, sy))
        for layer, mode in layers: surf.blit(layer, (sx, sy), special_flags=mode)

    def screen_rect(self, cam, margin):
        """Where draw() puts the current frame (None when nothing is drawn)."""
        if self.bank is None: return None
        a = self.bank.anim(self.anim)
        if not a or self.frame >= len(a['frames']): return None
        f = a['frames'][self.frame]
        if f.get('image') is None: return None
        img, _ = self.bank.image(f['image'])
        if img is None: return None
        sx = (self.x >> 16) - cam[0] + f['left']
        sy = ((self.y - self.z) >> 16) + margin - cam[1] + f['top']
        return pygame.Rect(sx, sy, img.get_width(), img.get_height())

    def row(self, th):
        return self.f64 >> 20                    # 0x8002DEAC: OT row = key >> 20


class Effects:
    """All effects of the map: the game's 128 records (lowest free slot first)."""

    def __init__(self, assets, map_folder):
        self.assets = assets; self.map_folder = map_folder
        self.fx = [Effect(i) for i in range(128)]

    @property
    def list(self): return [e for e in self.fx if e.state]

    def bank(self, is_map, index):
        root = (self.map_folder / 'effects') if is_map else (self.assets / 'effects' / 'global')
        return Bank.get(root / f'{index:03d}')

    def started(self, e):
        """engine.core.init_effect filled record e (nindex = ~index: the bank is looked up on
        the first update)."""
        e.bank = None; e.pos = 0; e.frame = 0

    def create(self, is_map, index, anim, x, y, z, mode=0, entity=None):
        from engine import core
        e = core.alloc_effect(self)
        if e is None: return None
        core.init_effect(self, e, 0, -1, mode, is_map, index, anim, x, y, z)
        e.entity = entity
        return e if e.state else None

    def attached(self, is_map, index, anim, entity, off=(0, 0, 0)):
        e = self.create(is_map, index, anim, entity.px + off[0], entity.py + off[1], entity.pz + off[2], 1, entity)
        if e: e.ox, e.oy, e.oz = off
        return e

    effect_started = started

    # -- map effect records (SpawnSpriteEffect / GetMapEffectRecord) --------------
    def load_records(self, hexes):
        self.records = []
        for h in hexes or []:
            b = bytes.fromhex(h)
            if len(b) < 10: continue
            x1, y1, x2, y2, flags, eid, x, y, z, anim = b[:10]
            self.records.append(dict(x1=x1, y1=y1, x2=x2, y2=y2, flags=flags, effect=eid, x=x, y=y, z=z, anim=anim))

    def spawn_record(self, i, check_area, player_tile=None):
        recs = getattr(self, 'records', [])
        if not 0 <= i < len(recs): return None
        r = recs[i]
        if check_area and player_tile is not None:
            tx, ty = player_tile
            if not (r['x1'] <= tx <= r['x2'] and r['y1'] <= ty <= r['y2']): return None
        if not check_area and not r['flags'] & 0x40: return None
        e = self.create(bool(r['flags'] & 0x80), r['effect'], r['anim'],
                        (r['x'] * 12 + 12) << 16, (r['y'] * 8 + 8) << 16, r['z'] << 19)
        if e: e.map_id = i
        return e

    def spawn_initial(self, player_tile=None):
        """InitializeEffectSlots 0x8003CB88: every record up to the first all-zero one is tried
        with SpawnSpriteEffect(i, 0): it appears when its flags have 0x40 and Alundra's square
        is inside its rectangle (0x8003C3C8 with the area test)."""
        for i, r in enumerate(getattr(self, 'records', [])):
            if r['x1'] == r['x2'] == r['y1'] == r['y2'] == 0 and r['flags'] == 0 and r['effect'] == 0: break
            if not r['flags'] & 0x40: continue
            self.spawn_record(i, True, player_tile)

    def by_id(self, i):
        return [e for e in self.list if e.map_id == i]

    @property
    def fx_table(self): return self.fx

    def set_anim(self, e, anim):
        """Command 92: the record's animation byte (+0x70); restarts on the next update."""
        e.b70 = anim & 0xFF

    def update(self, mode_flags=0):
        """UpdateEffects 0x8003CDF4: records in use (state 2), in slot order; one that finished
        its animation last frame is freed now."""
        if mode_flags & 0x48: return
        for e in self.fx:
            if e.state != 2: continue
            if e.b7d: e.state = 0; continue
            e.update_anim(self); e.move()
