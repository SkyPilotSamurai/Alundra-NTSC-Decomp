"""Where the game keeps things: the Entity record (0x294 bytes, table at 0x801AC6F8, slot 0
is Alundra), the effect record (0x80 bytes, 128 at 0x80133990) and the globals the ported
code uses.  Names are the remake's attribute names; the bridge (tools/us_decomp) uses this
to load RAM snapshots into the port and to compare results with the original code."""

ENT_BASE, ENT_SIZE, ENT_COUNT = 0x801AC6F8, 0x294, 64
FX_BASE, FX_SIZE, FX_COUNT = 0x80133990, 0x80, 128

# name: (offset, type)    types: i32 u32 i16 u16 i8 u8, 'ptr' (entity), 'fxptr', 'addr' (raw address)
ENTITY = {
    'index': (0x000, 'i32'), 'serial': (0x004, 'i32'), 'root': (0x008, 'ptr'), 'parent': (0x00C, 'ptr'),
    'estatus': (0x010, 'i32'), 'hp': (0x014, 'i32'), 'hp_max': (0x018, 'i32'), 'frame_counter': (0x01C, 'i32'),
    'frozen': (0x020, 'i32'), 'flags2': (0x024, 'i32'), 'holder': (0x028, 'ptr'), 'carried': (0x02C, 'ptr'),
    'carry_dx': (0x030, 'i32'), 'carry_dy': (0x034, 'i32'), 'carry_dz': (0x038, 'i32'),
    'contents_item': (0x03C, 'i32'), 'contents_flag': (0x040, 'i32'), 'record_addr': (0x044, 'addr'),
    'ref_id': (0x048, 'i32'),
    'prog_a': (0x04C, 'i32'), 'prog_b': (0x050, 'i32'), 'prog_c': (0x054, 'i32'), 'prog_d': (0x058, 'i32'),
    'prog_e': (0x05C, 'i32'), 'prog_f': (0x060, 'i32'), 'header_addr': (0x064, 'addr'),
    'sprite_index': (0x068, 'i32'), 'flags': (0x06C, 'i32'),
    'bi_a': (0x070, 'i32'), 'bi_b': (0x074, 'i32'), 'bi_c': (0x078, 'i32'), 'bi_d': (0x07C, 'i32'),
    'bi_e': (0x080, 'i32'), 'bi_f': (0x084, 'i32'),
    'target_anim': (0x088, 'i32'), 'target_dir': (0x08C, 'i32'), 'cur_anim': (0x090, 'i32'),
    'cur_dir': (0x094, 'i32'), 'anim_quadrant': (0x098, 'i32'),
    'next_frame_delay': (0x0A8, 'i32'), 'anim_done': (0x0AC, 'i32'), 'anim_complete': (0x0B0, 'i32'),
    'anim_flags': (0x0B4, 'i32'),
    'fz': (0x0B8, 'i32'), 'tfx': (0x0BC, 'i32'), 'tfy': (0x0C0, 'i32'), 'fx': (0x0C4, 'i32'), 'fy': (0x0C8, 'i32'),
    'pafx': (0x0CC, 'i32'), 'pafy': (0x0D0, 'i32'), 'sfx': (0x0D4, 'i32'), 'sfy': (0x0D8, 'i32'),
    'afx': (0x0DC, 'i32'), 'afy': (0x0E0, 'i32'), 'ffx': (0x0E4, 'i32'), 'ffy': (0x0E8, 'i32'), 'ffz': (0x0EC, 'i32'),
    'accel': (0x0F0, 'i32'), 'speed': (0x0F4, 'i32'), 'zforce_applied': (0x0F8, 'i32'),
    'px': (0x114, 'i32'), 'py': (0x118, 'i32'), 'pz': (0x11C, 'i32'),
    'tile_x': (0x120, 'i32'), 'tile_y': (0x124, 'i32'), 'riding': (0x12C, 'ptr'), 'x_collision': (0x130, 'ptr'),
    'floor': (0x134, 'i32'), 'terrain': (0x138, 'i32'), 'force_adjusted': (0x13C, 'i32'),
    'collided_z': (0x140, 'i32'), 'on_ground': (0x144, 'i32'),
    'vram_or': (0x180, 'i32'), 'vram_and': (0x184, 'i32'), 'tile_flags': (0x188, 'i32'), 'slope_now': (0x18C, 'i32'),
    'shadow': (0x1B8, 'fxptr'), 'balance_addr': (0x1C4, 'addr'), 'damaged_tick': (0x1CC, 'i32'), 'hit_tick': (0x1D0, 'i32'),
    'atk_on': (0x1D4, 'i32'),
    'mpx': (0x1D8, 'i32'), 'mpy': (0x1DC, 'i32'), 'mpz': (0x1E0, 'i32'),
    'modx': (0x1E4, 'i32'), 'mody': (0x1E8, 'i32'), 'modz': (0x1EC, 'i32'),
    'sizex': (0x1F0, 'i32'), 'sizey': (0x1F4, 'i32'), 'sizez': (0x1F8, 'i32'),
    'atk_x': (0x1FC, 'i32'), 'atk_y': (0x200, 'i32'), 'atk_z': (0x204, 'i32'),
    'atk_w': (0x214, 'i32'), 'atk_h': (0x218, 'i32'), 'atk_d': (0x21C, 'i32'),
    'hits': (0x220, 'i32'), 'touching': (0x224, 'ptr'), 'action': (0x228, 'i32'), 'last_action': (0x22C, 'i32'),
    'logic': (0x230, 'ptr'), 'saved_anim': (0x26C, 'i32'), 'saved_dir': (0x270, 'i32'),
    'delay': (0x278, 'i32'), 'item_state': (0x27C, 'i32'),
}
# words not identified yet (generic names; Actor answers 0 for unknown f_ fields)
ENTITY.update({'f_09C': (0x09C, 'i32'), 'f_0A0': (0x0A0, 'i32'), 'f_0A4': (0x0A4, 'i32'), 'f_0FC': (0x0FC, 'i32'), 'f_100': (0x100, 'i32'), 'f_104': (0x104, 'i32'), 'f_108': (0x108, 'i32'), 'f_10C': (0x10C, 'i32'), 'f_110': (0x110, 'i32'), 'tile_z': (0x128, 'i32'), 'cell0': (0x148, 'addr'), 'cell1': (0x14C, 'addr'), 'cell2': (0x150, 'addr'), 'cell3': (0x154, 'addr'), 'mh0': (0x158, 'i32'), 'mh1': (0x15C, 'i32'), 'mh2': (0x160, 'i32'), 'mh3': (0x164, 'i32'), 'f_168': (0x168, 'i32'), 'f_16C': (0x16C, 'i32'), 'f_170': (0x170, 'i32'), 'f_174': (0x174, 'i32'), 'f_178': (0x178, 'i32'), 'f_17C': (0x17C, 'i32'), 'f_190': (0x190, 'i32'), 'f_194': (0x194, 'i32'), 'f_198': (0x198, 'i32'), 'f_19C': (0x19C, 'i32'), 'f_1A0': (0x1A0, 'i32'), 'f_1A4': (0x1A4, 'i32'), 'sort_bias': (0x1A8, 'i32'), 'f_1AC': (0x1AC, 'i32'), 'f_1B0': (0x1B0, 'i32'), 'f_1B4': (0x1B4, 'i32'), 'f_1BC': (0x1BC, 'i32'), 'f_1C0': (0x1C0, 'i32'), 'attack_addr': (0x1C8, 'addr'), 'f_208': (0x208, 'i32'), 'f_20C': (0x20C, 'i32'), 'f_210': (0x210, 'i32'), 'f_234': (0x234, 'i32'), 'f_238': (0x238, 'i32'), 'f_23C': (0x23C, 'i32'), 'f_240': (0x240, 'i32'), 'f_244': (0x244, 'i32'), 'f_248': (0x248, 'i32'), 'f_24C': (0x24C, 'i32'), 'f_250': (0x250, 'i32'), 'f_254': (0x254, 'i32'), 'f_258': (0x258, 'i32'), 'f_25C': (0x25C, 'i32'), 'f_260': (0x260, 'i32'), 'f_264': (0x264, 'i32'), 'f_268': (0x268, 'i32')})
ENTITY_BYTES = {'bytes': (0x274, 4)}             # u8[4]
ENTITY_SHORTS = {'ai': (0x280, 10)}              # i16[10]

# effect record (0x8003C46C fills it)
EFFECT = {
    'slot': (0x00, 'i32'), 'is_map': (0x04, 'i32'), 'frame_addr': (0x08, 'addr'), 'first_addr': (0x0C, 'addr'),
    'f10': (0x10, 'i32'), 'f14': (0x14, 'i32'), 'f18': (0x18, 'i32'), 'f1c': (0x1C, 'i32'),
    'f20': (0x20, 'i32'), 'f24': (0x24, 'i32'), 'f28': (0x28, 'i32'), 'f2c': (0x2C, 'i32'),
    'f64': (0x64, 'i32'), 'b72': (0x72, 'u8'), 'b73': (0x73, 'u8'), 'f74': (0x74, 'addr'), 'f78': (0x78, 'addr'),
    'b7c': (0x7C, 'u8'), 'b7e': (0x7E, 'u8'), 'b7f': (0x7F, 'u8'), 'spr_anim': (0x30, 'i32'), 'mode': (0x34, 'i32'), 'entity': (0x38, 'ptr'),
    'x': (0x3C, 'i32'), 'y': (0x40, 'i32'), 'z': (0x44, 'i32'),
    'ox': (0x48, 'i32'), 'oy': (0x4C, 'i32'), 'oz': (0x50, 'i32'),
    'vx': (0x54, 'i32'), 'vy': (0x58, 'i32'), 'vz': (0x5C, 'i32'), 'arg60': (0x60, 'i32'),
    'state': (0x68, 'i32'), 'b6c': (0x6C, 'u8'), 'b6d': (0x6D, 'u8'), 'index': (0x6E, 'u8'), 'nindex': (0x6F, 'u8'),
    'b70': (0x70, 'u8'), 'b71': (0x71, 'u8'), 'b7d': (0x7D, 'u8'),
}

# globals the port keeps (name: (address, type))
GLOBALS = {
    'rng_seed': (0x8009AF70, 'u32'),
    'ent_count': (0x801D93EC, 'i32'),
    'pad_held': (0x801DDA48, 'u16'), 'pad_pressed': (0x801DDA4A, 'u16'), 'pad_repeat': (0x801DDA4E, 'u16'),
    'talk_target': (0x801EFE5C, 'ptr'),
    'mode_flags': (0x801F0060, 'i32'),
    'weapon_class': (0x801F0A10, 'i32'),          # MovePlayer: 0x80028BB8[equipped item kind]
    'attack_rec': (0x801F0A14, 'addr'),           # the weapon record of the swing in progress
    'attack_timer': (0x801F0A18, 'i32'),
    'charge': (0x801C47D4, 'i32'), 'pad_released': (0x801DDA4C, 'u16'),                # Square held: 11+ charging, 60 charged
    'item_use': (0x801F121C, 'i32'),              # item effect in progress (31..50)
    'land_sound_done': (0x8009B798, 'i32'),
    'low_hp_timer': (0x8009B794, 'i32'),
    'carry_timer': (0x8009B790, 'i32'),
    'sprint_resume': (0x80104804, 'i32'),
    'charge_fx': (0x801AC6C0, 'fxptr'),
    'debug_mode': (0x801AC6C8, 'i32'), 'debug_flags': (0x801AC6CC, 'i32'),
    'floor_damage_lock': (0x801D8740, 'i32'),
    'warp_request': (0x801F11F4, 'i32'), 'warp_effect': (0x801F11F8, 'i32'), 'warp_map': (0x801F11FC, 'i32'),
    'warp_anim': (0x801F1200, 'i32'), 'warp_sound': (0x801F1218, 'i32'),
    'tile_effects_addr': (0x801F0070, 'addr'),    # map's tile effect info (byte 0xA = dust effect)
    'item_frames': (0x801D7B38, 'i32'), 'item_dda6c': (0x801DDA6C, 'i32'),
    'warp_busy': (0x801F11F0, 'i32'), 'warp_dir': (0x801F1204, 'i32'),
    'warp_x': (0x801F1208, 'i32'), 'warp_y': (0x801F120C, 'i32'), 'warp_z': (0x801F1210, 'i32'),
    'cur_map': (0x801F5358, 'i32'), 'portal_debug_count': (0x8009B78C, 'i32'),
    'talk_lock': (0x8009B774, 'ptr'), 'talk_serial': (0x80104774, 'i32'),
    'talk_ex': (0x80104768, 'i32'), 'talk_ey': (0x8010476C, 'i32'), 'talk_ez': (0x80104770, 'i32'),
    'talk_px': (0x80104758, 'i32'), 'talk_py': (0x8010475C, 'i32'), 'talk_pz': (0x80104760, 'i32'),
    'talk_dir': (0x80104764, 'i32'),
}
