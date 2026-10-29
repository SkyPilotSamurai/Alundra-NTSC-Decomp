"""Alundra's physics, ported line by line from the game (ALUN_CD.EXE, via the
MIT xcasadio AlundraEngine PhysicsEngine.cs; addresses in the comments).

Units are the game's: positions and forces are 16.16 fixed point pixels
(0x10000 = 1 pixel), one call of step() is one game frame (60 per second).
Map squares are 24 x 16 pixels; a square's Height unit is 16 pixels of Z.

Entity fields used (see remake Actor):
  px py pz            PosX/Y/Z
  fx fy fz            ForceX/Y/Z
  tfx tfy sfx sfy     TargetForce and ForceStep
  ffx ffy ffz         FinalForce;  afx afy  AdjustedForce
  mod (x, y, z), size (w, h, d)  from the sprite header hit box
  flags, anim_flags, zforce_applied, speed/accel of the current animation set
  target_dir (0-31: 0 down, 8 left, 16 up, 24 right)
"""

TILE_W, TILE_H = 24, 16
ONE = 0x10000

# 0x80023654 / 0x80023694: 32-direction force per unit of speed (X is 1.5x Y)
OFFSET_X = [0x0, -0x96, -0x126, -0x1a6, -0x21f, -0x27f, -0x2c6, -0x2f1, -0x300, -0x2f1, -0x2c6, -0x27f, -0x21f, -0x1a6, -0x126, -0x96,
            0x0, 0x96, 0x126, 0x1a6, 0x21f, 0x27f, 0x2c6, 0x2f1, 0x300, 0x2f1, 0x2c6, 0x27f, 0x21f, 0x1a6, 0x126, 0x96]
OFFSET_Y = [0x200, 0x1f6, 0x1d9, 0x1aa, 0x16a, 0x11c, 0xc4, 0x64, 0x0, -0x64, -0xc4, -0x11c, -0x16a, -0x1aa, -0x1d9, -0x1f6,
            -0x200, -0x1f6, -0x1d9, -0x1aa, -0x16a, -0x11c, -0xc4, -0x64, 0x0, 0x64, 0xc4, 0x11c, 0x16a, 0x1aa, 0x1d9, 0x1f6]
# 0x800236d4: height inside a side ramp square, per pixel column
RAMP = [1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 12, 12, 13, 14, 14, 15, 16, 16]
# conveyor / sliding floor push (ScriptHelper XForceTable / YForceTable), by TileAttributes & 15
X_PUSH = [0, 0, 0, 0, -61440, -61440, -61440, -983040, 61440, 61440, 61440, 983040, 0, 0, 0, 0]
Y_PUSH = [0, -40960, 40960, 0, 0, -40960, 40960, 0, 0, -40960, 40960, 0, 0, -40960, 40960, 0]

# EntityFlags
CLASS_A, CLASS_B, COLLIDABLE, GRAVITY, NO_SLIDE, NO_RIDERS = 0x1, 0x8, 0x80, 0x100, 0x2000, 0x4000
NO_ENTITY_COLLISION = 0x80          # EntityAnimFlags


class Tile:
    __slots__ = ('walk', 'ground', 'slope', 'height')

    def __init__(self, c):
        self.walk, self.ground, self.slope, self.height = (c[0], c[1], c[2], c[3]) if c else (0x40, 0, 0, 0)

    @property
    def flags(self):
        return self.walk | self.ground << 8 | self.slope << 16 | self.height << 24


def _asr(v, n):
    return v >> n                     # Python >> on negatives is arithmetic, as on MIPS sra


class World:
    """One map's physics. entities: active entities in slot order; player: Alundra."""

    def __init__(self, cells, width, height, gravity=128, z_viscosity=4096, slide_effect=0):
        self.coll = []; self.entities = []
        self.cells = cells; self.w = width; self.h = height
        self.gravity = gravity; self.z_viscosity = z_viscosity; self.slide = slide_effect & 31
        self.gravity_flag = 0          # g_gravityFlag (boots / special states)
        self.entities = []; self.player = None
        self.level_top_fix = False            # Options > Level Top Fix (hidden, Ctrl+0): see collide_down

    # ---------------------------------------------------------------- tiles --
    def tile(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            return Tile(self.cells[ty * self.w + tx])
        return Tile(None)

    # ------------------------------------------------------------- the frame --
    def collideable(self):
        """0x80038DCC's second list: every entity (no status or frozen test - unlike the moving list) with
        COLLIDABLE, without anim flag 0x80, not held.  A frozen entity stays solid: the item pickup freezes
        the room, and a brazier Alundra stood on stopped holding him up (Lake Shrine map 343, user report
        2026-10-24; docs/2026-10-24-lake-shrine-torch-stuck.txt)."""
        return [e for e in getattr(self, 'coll_source', self.entities)
                if e.flags & COLLIDABLE and not e.anim_flags & NO_ENTITY_COLLISION and e.platform is None]

    def step(self):
        """UpdateEntitiesPhysics 0x80038364."""
        self.coll = self.collideable()
        for e in self.entities:
            e.platform_flag = 0; e.collided_z = 0; e.force_adjusted = 0
            self.modded(e)
        self.check_riding()
        self.update_forces()
        for e in self.coll:
            if e.riding is not None: self.update_riding(e, e.riding)
        for e in self.entities:
            if not e.platform_flag: self.move(e)
        for e in self.entities:
            self.tile_attributes(e)

    @staticmethod
    def modded(e):
        e.mpx = e.px + e.mod[0]; e.mpy = e.py + e.mod[1]; e.mpz = e.pz + e.mod[2]

    # 0x80037364
    def update_riding(self, e, r):
        if r.riding is not None: self.update_riding(r, r.riding)
        e.ffx += r.afx; e.ffy += r.afy
        if e.zforce_applied == 0:
            e.fz = r.ffz; e.ffz = r.ffz

    # 0x80037e34
    def move(self, e):
        e.platform_flag = 1
        p = e.platform
        if p is None:
            self.compute_z(e)
            e.x_collision = self.compute_xy(e)
        else:
            if not p.platform_flag: self.move(p)
            e.collided_z = 1; e.force_adjusted = 1; e.x_collision = None
            e.floor = p.floor; e.terrain = p.terrain
            e.px = p.px + p.carry[0]; e.py = p.py + p.carry[1]; e.pz = p.pz + p.carry[2]
            self.modded(e)

    # 0x800375e0
    def compute_z(self, e):
        v = e.ffz
        e.terrain = self.ground_height(e)
        if v < 1:
            while True:
                hit, h, other = self.collide_down(e)
                if not hit: break
                if other is None or other.platform_flag:
                    e.collided_z = 1; e.pz = h - e.mod[2]
                    if e.flags & GRAVITY: e.fz = 0
                    return
                self.move(other)
        else:
            while True:
                hit, h, other = self.collide_up(e)
                if not hit: break
                if other is None or other.platform_flag:
                    e.collided_z = 1; e.pz = h - e.mod[2] - e.size[2]
                    if e.flags & GRAVITY: e.fz = 0
                    return
                self.move(other)
        e.pz += v

    @staticmethod
    def _overlap_xy(e, c):
        d = c.mpx - e.mpx
        if d < 0:
            if not e.mpx - c.mpx < c.size[0] + 1: return False
        elif not d < e.size[0] + 1: return False
        d = c.mpy - e.mpy
        if d < 0: return e.mpy - c.mpy < c.size[1] + 1
        return d < e.size[1] + 1

    def _entity_collision_on(self, e):
        return e.flags & COLLIDABLE and not e.anim_flags & NO_ENTITY_COLLISION and e.platform is None

    # 0x80036bfc
    def collide_down(self, e):
        top = e.mpz + e.ffz
        hit = top <= e.terrain; best = None
        if hit: top = e.terrain + 1
        if self._entity_collision_on(e):
            for c in self.coll:
                if c is e: continue
                ctop = c.mpz + c.size[2]
                # (Alundra exactly level with a top, not one unit above it as the game always leaves him,
                # is kept on it too: Lake Shrine map 343 brazier, user report 2026-10-24 - he sank into it
                # and could only turn; docs/2026-10-24-lake-shrine-torch-stuck.txt)
                above = ctop < e.mpz or (ctop == e.mpz and e is self.player and self.level_top_fix)
                if above and top <= ctop and self._overlap_xy(e, c):
                    top = ctop + 1; hit = True; best = c
        return hit, top, best

    # 0x80036d94
    def collide_up(self, e):
        head = e.mpz + e.size[2]; cand = head + e.ffz
        hit = 0x7800000 < cand; best = None
        if hit: cand = 0x77fffff
        if self._entity_collision_on(e):
            for c in self.coll:
                if c is e: continue
                cz = c.mpz
                if head < cz <= cand and self._overlap_xy(e, c):
                    cand = cz - 1; hit = True; best = c
        return hit, cand, best

    # EntityGameplayManager.GetTileHeightAtOffset: highest square under the box moved by (ox, oy)
    def tile_height_at(self, e, ox, oy):
        x = e.px + e.mod[0] + ox; y = e.py + e.mod[1] + oy
        xs = ((x >> 16) // TILE_W, ((x + e.size[0]) >> 16) // TILE_W)
        ys = (y >> 20, (y + e.size[1]) >> 20)
        bits = (1 if e.flags & CLASS_B else 0) | (0x1000 if e.flags & CLASS_A else 0)
        best = 0
        for tx in xs:
            for ty in ys:
                t = self.tile(max(0, min(tx, 51)), max(0, min(ty, 59)))
                if t.walk & bits: return 0x7800000
                best = max(best, t.height)
        return best << 20

    # 0x800370c4
    def ground_height(self, e):
        x1 = (e.px + e.mod[0]) >> 16; x2 = (e.px + e.mod[0] + e.size[0]) >> 16
        y1 = (e.py + e.mod[1]) >> 16; y2 = (e.py + e.mod[1] + e.size[1]) >> 16
        pts = ((x1, y1), (x2, y1), (x1, y2), (x2, y2))
        highest = 0; slopes = 0
        e.map_tiles = []; e.map_heights = []
        for x, y in pts:
            tx = max(0, min(int(x / TILE_W) if x >= 0 else 0, 51)); ty = max(0, min(int(y / TILE_H) if y >= 0 else 0, 59))
            t = self.tile(tx, ty); e.map_tiles.append(t)
            h = t.height * TILE_H
            k = t.slope & 3
            base = (t.height - 1) * TILE_H                  # a slope's base; a second slope kind in the
            if k == 1:                                      # same box counts as the full square (base + 16)
                h = base + TILE_H - (y % TILE_H) if not slopes & 6 else base + TILE_H
                slopes |= 1
            elif k == 2:
                h = base + RAMP[(23 - x % TILE_W) % TILE_W] if not slopes & 5 else base + TILE_H
                slopes |= 2
            elif k == 3:
                h = base + RAMP[x % TILE_W] if not slopes & 3 else base + TILE_H
                slopes |= 4
            h <<= 16
            e.map_heights.append(h)
            highest = max(highest, h)
        return highest

    # 0x80037488 (Alundra) / 0x800373e4 (others)
    def collision_flags(self, e, out):
        flag = 0x41 if e.flags & CLASS_B else 0x40
        if e.flags & CLASS_A: flag |= 0x1000
        for i in range(4):
            t = e.map_tiles[i]; tf = t.walk | t.ground << 8
            out[i] = 1 if (tf & flag) or e.map_heights[i] >= e.mpz else 0
            if e is self.player and self.gravity_flag < 2 and (tf & 0xE00) == 0x800:
                out[i] = 1
            # US 0x80037E3C: while the Sand Cape (item 0x20) is in use only quicksand squares
            # (floor type 0x600) at his own level are passable
            if e is self.player and getattr(self, 'item_in_use', 0) == 0x20 and \
                    (e.mpz != e.map_heights[i] + 1 or (tf & 0xE00) != 0x600):
                out[i] = 1
        return out[0] | out[1] | out[2] | out[3]

    # 0x80036F34
    def find_entity(self, e):
        if not self._entity_collision_on(e): return None
        for c in self.coll:
            if c is e or not self._overlap_xy(e, c): continue
            d = c.mpz - e.mpz
            if d < 0:
                if e.mpz - c.mpz < c.size[2] + 1: return c
            elif d < e.size[2] + 1: return c
        return None

    # 0x80037730 (xcasadio build); USA v1.1 ALUN_CD.EXE 0x80038008
    def compute_xy(self, e):
        straight = (e.target_dir & 7) == 0
        flags = [0, 0, 0, 0]
        adjusted_once = False
        while True:                                   # START_COLLISION_CHECK
            dx, dy = e.ffx, e.ffy
            if dx == 0 and dy == 0:
                self.modded(e); e.terrain = self.ground_height(e); return None
            settled = False; candidate = None; result = None; i = 0
            while True:                               # TRY_ADVANCE
                # US 0x800380A4: the value returned (Entity+0x130, the entity bumped) is the
                # entity found by the PREVIOUS attempt (s4), not the last non-null one; and
                # s4 is only re-read when the step-up branch did not step (0x800381A4).
                # Checked against BizHawk (docs/2026-10-21-ice-pillar-diagonal-push.txt).
                result = candidate
                ox, oy, oz = e.px, e.py, e.pz
                flags = [0, 0, 0, 0]
                e.px += dx; e.py += dy
                self.modded(e)
                g = self.ground_height(e); e.terrain = g
                stepped = False
                if e.flags & GRAVITY and e.fz == 0:
                    dz = g - e.mpz - 1; tol = 0x30000
                    if dz < 0: tol = 0x30003; dz = -dz
                    if dz < tol:                       # walks up / down small steps and ramps
                        saved = e.pz; e.pz = g + 1; self.modded(e)
                        if self.find_entity(e) is not None:
                            e.pz = saved; self.modded(e)
                        else:
                            stepped = True             # (s4 keeps the previous attempt's entity)
                if not stepped:
                    candidate = self.find_entity(e)
                blocked = (not stepped and candidate is not None) or self.collision_flags(e, flags) != 0
                if blocked:
                    e.px, e.py, e.pz = ox, oy, oz
                    hx = 0 if dx == -1 else _asr(dx, 1); hy = 0 if dy == -1 else _asr(dy, 1)
                    if (straight and (hx or hy)) or (not straight and hx and hy):
                        i += 1; dx, dy = hx, hy; continue
                    break                              # DECIDE_FINAL_OBSTACLE
                settled = True
                if i == 0: return result
                hx = 0 if dx == -1 else _asr(dx, 1); hy = 0 if dy == -1 else _asr(dy, 1)
                if (straight and (hx or hy)) or (not straight and hx and hy):
                    i += 1; dx, dy = hx, hy; continue
                return result
            # DECIDE_FINAL_OBSTACLE
            if settled:
                return self._finish(e, result)
            if adjusted_once or e.flags & NO_SLIDE or candidate is not None:
                e.force_adjusted = 1; return self._finish(e, result)
            adjusted_once = True
            if not self._slide(e, flags):
                e.force_adjusted = 1; return self._finish(e, result)

    def _finish(self, e, result):
        self.modded(e); e.terrain = self.ground_height(e); return result

    @staticmethod
    def _slide(e, f):
        """Sliding round corners (0x8003799C): returns False when blocked for good."""
        d = e.target_dir
        if d >= 32: return False
        if d == 0:
            if (f[2] and f[3]) or f[0] or f[1]: return False
            e.ffy = 0
            if f[2] and not f[3]: e.ffx = 0xC000
            elif not f[2] and f[3]: e.ffx = -0xC000
        elif d < 8:
            if f[0]:
                if f[3]: return False
                e.ffx = 0
            elif f[3]: e.ffy = 0
        elif d == 8:
            if (f[0] and f[2]) or f[1] or f[3]: return False
            e.ffx = 0
            if f[0] and not f[2]: e.ffy = 0x8000
            elif not f[0] and f[2]: e.ffy = -0x8000
        elif d < 16:
            if not f[1]:
                if f[2]: e.ffx = 0
            else:
                if f[2]: return False
                e.ffy = 0
        elif d == 16:
            if (f[0] and f[1]) or f[2] or f[3]: return False
            e.ffy = 0
            if f[0] and not f[1]: e.ffx = 0xC000
            elif not f[0] and f[1]: e.ffx = -0xC000
        elif d < 24:
            if f[0] and f[3]: return False
            if f[3]: e.ffx = 0
            elif f[0]: e.ffy = 0
        elif d == 24:
            if (f[1] and f[3]) or f[0] or f[2]: return False
            e.ffx = 0
            if f[1] and not f[3]: e.ffy = 0x8000
            elif not f[1] and f[3]: e.ffy = -0x8000
        else:
            if f[1] and f[2]: return False
            if f[2]: e.ffy = 0
            if f[1]: e.ffx = 0
        return True

    # 0x800364c8
    def check_riding(self):
        for e in self.coll:
            # The C# port clears RidingEntity only for gravity entities, which would leave an
            # entity that switches gravity off (command 17) glued to what it stood on, copying
            # its Z force forever (the ship intro's sailor never climbs down). The game clearly
            # lets go, so every entity is re-checked each frame.
            e.riding = None
            if e.flags & (GRAVITY | NO_RIDERS) != GRAVITY: continue
            for o in self.coll:
                if o is e: continue
                if o.mpz + o.size[2] + 1 != e.mpz: continue
                d = o.mpx - e.mpx
                if d < 0:
                    if not e.mpx - o.mpx < o.size[0] + 1: continue
                elif not d < e.size[0] + 1: continue
                d = o.mpy - e.mpy
                if d < 0:
                    if not e.mpy - o.mpy < o.size[1] + 1: continue
                elif not d < e.size[1] + 1: continue        # ALUN_CD.EXE 0x80036E10 uses Height (the C# port says Depth)
                e.riding = o; break

    # 0x80036828
    def update_forces(self):
        g = self.gravity << 8; term = self.z_viscosity << 8
        for e in self.entities:
            if e is self.player:
                if e.zforce_applied == 0:
                    if e.flags & GRAVITY:
                        f = e.fz - g
                        e.fz = f if abs(f) <= term else (-term if f < 0 else term)
                elif not e.flags & GRAVITY or not e.vram_or & 0x10 or self.gravity_flag > 0:
                    e.fz = e.zforce_applied << 8
                else:
                    e.fz = e.zforce_applied * 0xA0          # weaker jump from sand / shallow water
                self.update_entity_physics(e)
                xs, ys = e.sfx, e.sfy
                if e.vram_or & 0x20:                         # slippery floor: 1/16 of the acceleration
                    xs = (xs * 0x1000) >> 16; ys = (ys * 0x1000) >> 16
                tx, ty = e.tfx, e.tfy
                if e.vram_or & 8 and self.gravity_flag < 1:  # slow floor: half speed
                    tx = (tx * 0x8000) >> 16; ty = (ty * 0x8000) >> 16
                e.fx = increment(e.fx, tx, xs); e.fy = increment(e.fy, ty, ys)
            else:
                if e.platform is not None:
                    e.fx = e.fy = e.fz = e.afx = e.afy = e.ffx = e.ffy = e.ffz = 0
                    continue
                if e.zforce_applied == 0:
                    if e.flags & GRAVITY:
                        f = e.fz - g                         # US 0x800373C8: clamped both ways, as for Alundra
                        e.fz = f if abs(f) <= term else (term if f > 0 else -term)
                elif e.zforce_applied == -0x8000 and not e.flags & GRAVITY:
                    e.fz = 0
                else:
                    e.fz = e.zforce_applied << 8
                self.update_entity_physics(e)
                e.fx = increment(e.fx, e.tfx, e.sfx); e.fy = increment(e.fy, e.tfy, e.sfy)
            self.apply_forces(e)
            e.ffx = e.afx; e.ffy = e.afy; e.ffz = e.fz

    # 0x800366fc
    def apply_forces(self, e):
        # US ALUN_CD.EXE 0x80036F64: ((force + push) >> slide) + previous adjust; the C# port
        # shifts only the push.  Slide is the map's info byte 8 (two maps use 1: everything moves
        # at half speed there).
        i = e.tile_attr & 15
        x = ((e.fx + X_PUSH[i]) >> self.slide) + e.pafx
        y = ((e.fy + Y_PUSH[i]) >> self.slide) + e.pafy
        e.pafx = e.pafy = 0
        lo_x, lo_y = -e.mod[0], -e.mod[1]
        hi_x = 0x4E00000 - (e.mod[0] + e.size[0] + (1 if e.size[0] else 0))
        hi_y = 0x3C00000 - (e.mod[1] + e.size[1] + (1 if e.size[1] else 0))
        if e.px + x < lo_x: x = lo_x - e.px; e.force_adjusted = 1
        elif hi_x < e.px + x: x = hi_x - e.px; e.force_adjusted = 1
        if e.py + y < lo_y: y = lo_y - e.py; e.force_adjusted = 1
        elif hi_y < e.py + y: y = hi_y - e.py; e.force_adjusted = 1
        e.afx, e.afy = x, y

    # 0x80036614
    @staticmethod
    def update_entity_physics(e):
        if e.cur_speed == e.speed and e.target_dir == e.cur_dir and e.cur_accel == e.accel:
            return
        e.cur_dir = e.target_dir; e.cur_speed = e.speed; e.cur_accel = e.accel
        d = e.target_dir & 31
        e.tfx = OFFSET_X[d] * e.speed; e.tfy = OFFSET_Y[d] * e.speed
        e.sfx = abs(e.tfx - e.fx) >> e.accel; e.sfy = abs(e.tfy - e.fy) >> e.accel

    # 0x80037f28
    def floor_z(self, e):
        z = e.terrain + 1
        if not self._entity_collision_on(e): return z
        for o in self.coll:
            if o is e: continue
            top = o.mpz + o.size[2]
            if top >= e.mpz or top < z: continue
            d = o.mpx - e.mpx
            if d >= 0:
                if d >= e.size[0] + 1: continue
            elif e.mpx - o.mpx >= o.size[0] + 1: continue
            d = o.mpy - e.mpy
            if (d >= 0 and d < e.size[1] + 1) or (d < 0 and e.mpy - o.mpy < o.size[1] + 1):
                z = top + 1
        return z

    # 0x80038064
    def tile_attributes(self, e):
        e.tile_x = (e.px >> 16) // TILE_W; e.tile_y = (e.py >> 16) // TILE_H; e.tile_z = e.pz >> 20
        z = self.floor_z(e); e.floor = z
        e.on_ground = 0 if z < e.pz else 1
        tx = max(0, min(e.tile_x, 51)); ty = max(0, min(e.tile_y, 59))
        best = 0
        if not e.flags & GRAVITY:
            e.vram_or = e.vram_and = 0
            tf = self.tile(tx, ty).flags
            if not (tf & 0xC00000 and tf & 0x80000):
                e.tile_attr = 0; e.slope_prev, e.slope_now = e.slope_now, best >> 9; return
        else:
            best = 0xE00; temp = [0, 0, 0, 0]
            for i in range(4):
                tf = e.map_tiles[i].flags
                if e.map_heights[i] + 1 == e.mpz:
                    temp[i] = tf
                    if tf & 0xE00 < best: best = tf & 0xE00
                else:
                    temp[i] = 0; best = 0
            e.vram_or = temp[0] | temp[1] | temp[2] | temp[3]
            e.vram_and = temp[0] & temp[1] & temp[2] & temp[3]
            tf = self.tile(tx, ty).flags
            if not tf & 0xC00000:
                e.tile_attr = 0; e.slope_prev, e.slope_now = e.slope_now, best >> 9; return
            attr = 0x40000 if ((tf & 0xFF000000) >> 4) + 1 == e.mpz else 0x80000
            if not tf & attr:
                e.tile_attr = 0; e.slope_prev, e.slope_now = e.slope_now, best >> 9; return
        attr = 1 << ((tf >> 20) & 3)
        e.tile_attr = attr | (0x80 if tf & 0x800000 else 0)
        e.slope_prev, e.slope_now = e.slope_now, best >> 9


# 0x800367e4
def increment(force, target, step):
    if target != force:
        if force < target:
            force += step
            if target < force: return target
        else:
            force -= step
            if force < target: return target
    return force


class Body:
    """The physics state of one entity (mixed into the remake's Actor)."""

    def init_body(self, hitbox_offset=(-9, -6, 0), hitbox_size=(18, 12, 32)):
        ox, oy, oz = hitbox_offset; sx, sy, sz = hitbox_size
        self.mod = (ox << 16, oy << 16, oz << 16)
        self.size = tuple(((s << 16) - 1) if s else 0 for s in (sx, sy, sz))
        self.px = self.py = self.pz = 0
        self.fx = self.fy = self.fz = 0
        self.tfx = self.tfy = self.sfx = self.sfy = 0
        self.afx = self.afy = self.ffx = self.ffy = self.ffz = 0
        self.pafx = self.pafy = 0
        self.mpx = self.mpy = self.mpz = 0
        self.speed = 0; self.accel = 0; self.anim_flags = 0; self.zforce_applied = 0
        self.cur_speed = self.cur_dir = self.cur_accel = -1
        self.terrain = 0; self.floor = 1; self.on_ground = 1
        self.platform = None; self.carry = (0, 0, 0); self.riding = None; self.x_collision = None
        self.platform_flag = 0; self.collided_z = 0; self.force_adjusted = 0
        self.tile_attr = 0; self.vram_or = self.vram_and = 0; self.slope_now = self.slope_prev = 0
        self.tile_x = self.tile_y = self.tile_z = 0
        self.map_tiles = [Tile(None)] * 4; self.map_heights = [0] * 4

    # the game's record fields kept as tuples here (engine/layout.py names)
    def _tup(name, i):
        def get(self): return getattr(self, name)[i]
        def put(self, v):
            t = list(getattr(self, name)); t[i] = v; setattr(self, name, tuple(t))
        return property(get, put)
    carry_dx, carry_dy, carry_dz = _tup('carry', 0), _tup('carry', 1), _tup('carry', 2)
    modx, mody, modz = _tup('mod', 0), _tup('mod', 1), _tup('mod', 2)
    sizex, sizey, sizez = _tup('size', 0), _tup('size', 1), _tup('size', 2)
    def _lst(name, i):
        def get(self): return getattr(self, name)[i]
        def put(self, v): getattr(self, name)[i] = v
        return property(get, put)
    mh0, mh1, mh2, mh3 = _lst('map_heights', 0), _lst('map_heights', 1), _lst('map_heights', 2), _lst('map_heights', 3)
    del _tup, _lst

    # pixel views for the script machine and drawing
    @property
    def wx(self): return self.px / ONE
    @wx.setter
    def wx(self, v): self.px = int(round(v * ONE))
    @property
    def wy(self): return self.py / ONE
    @wy.setter
    def wy(self, v): self.py = int(round(v * ONE))
    @property
    def z(self): return self.pz / ONE
    @z.setter
    def z(self, v): self.pz = int(round(v * ONE))
    @property
    def vz(self): return self.fz / ONE
    @vz.setter
    def vz(self, v): self.fz = int(round(v * ONE))
