"""Bounded in-place editing for map-local sprite animation records.

Record sizes and field order follow xcasadio/alundra-datas-analyser, pinned in
the workspace source review. This module only rewrites existing fixed-size
records; it never grows an animation stream or changes pointers.
"""
from dataclasses import dataclass
import struct

# Editor resource guard, not a native frame-count limit. Stock map321/local213
# has four valid72-frame streams; native stepping advances a pointer five bytes
# at a time until a transition marker. Every read remains section-bounded.
MAX_ANIMATION_STREAM_FRAMES=4096


@dataclass(frozen=True)
class AnimationFrame:
    offset: int
    delay_raw: int
    collision_raw: int
    image_set_index: int
    raw: bytes


@dataclass(frozen=True)
class AnimationStream:
    offset: int
    direction_slot: int
    frames: tuple[AnimationFrame, ...]
    terminator: bytes


@dataclass(frozen=True)
class AnimationSet:
    index: int
    offset: int
    speed_raw: int
    direction_offsets: tuple[int, int, int, int]
    tail: bytes
    streams: tuple[AnimationStream | None, ...]


def _bounded_read(data, offset, size, start, end):
    if offset < start or size < 0 or offset + size > end or offset + size > len(data):
        raise ValueError("Sprite animation data points outside its map-local section")
    return bytes(data[offset:offset + size])


def _read_stream(data, start, end, relative, direction_slot):
    if relative == -1:
        return None
    if relative < -1:
        raise ValueError("Unsupported negative animation stream offset")
    position = start + relative
    frames = []
    for _ in range(MAX_ANIMATION_STREAM_FRAMES+1):
        first = _bounded_read(data, position, 1, start, end)[0]
        if first & 0x80:
            if len(frames)>=MAX_ANIMATION_STREAM_FRAMES:
                raise ValueError('Animation stream exceeds editor resource bound')
            raw = _bounded_read(data, position, 5, start, end)
            collision = struct.unpack_from("<h", raw, 1)[0]
            image_set = struct.unpack_from("<H", raw, 3)[0]
            frames.append(AnimationFrame(position, first, collision, image_set, raw))
            position += 5
            continue
        terminator = bytes([first])
        if first == 0:
            terminator += _bounded_read(data, position + 1, 1, start, end)
        if not frames:
            raise ValueError("Animation stream has no drawable frame")
        return AnimationStream(start + relative, direction_slot, tuple(frames), terminator)
    raise ValueError("Animation stream exceeds editor resource bound")


def parse_sprite_animation_record(data, sprite_start, sprite_end, sprite_id,
                                  table_offset, table_end):
    """Decode one sprite and its four-slot animation sets within explicit bounds."""
    if not (0 <= sprite_start < sprite_end <= len(data)):
        raise ValueError("Invalid map-local sprite section")
    if table_offset < 0 or table_end < table_offset or (table_end-table_offset) % 4:
        raise ValueError("Invalid map-local sprite pointer table")
    count = (table_end - table_offset) // 4
    if not 0 <= sprite_id < count:
        raise ValueError("Sprite ID is outside this map's pointer table")
    table_abs = sprite_start + table_offset
    pointers = _bounded_read(data, table_abs, table_end-table_offset, sprite_start, sprite_end)
    relative_record = struct.unpack_from("<i", pointers, sprite_id*4)[0]
    if relative_record <= 0:
        raise ValueError("This map sprite slot has no record")
    record = sprite_start + relative_record
    header = _bounded_read(data, record, 32, sprite_start, sprite_end)
    sets_offset, animations_offset, _collision_offset, _frames_offset = struct.unpack_from("<4I", header)
    record_relative=record-sprite_start
    if sets_offset != record_relative+32 or animations_offset < sets_offset:
        raise ValueError("Sprite animation-set directory has an unsupported shape")
    # The upstream parser computes this as integer division; some records leave
    # a small gap before the animation streams, so require only < one set of pad.
    set_bytes=animations_offset-sets_offset
    animation_count = set_bytes//14
    if not 1 <= animation_count <= 256:
        raise ValueError("Unsupported animation-set count")
    if set_bytes-animation_count*14 >= 14:
        raise ValueError("Unsupported padding after animation sets")
    # Validate the declared set array and keep every opaque byte in each record.
    set_array = _bounded_read(data, sprite_start+sets_offset, animation_count*14, sprite_start, sprite_end)
    result = []
    for index in range(animation_count):
        local = index*14
        directions = struct.unpack_from("<4h", set_array, local)
        speed = struct.unpack_from("<H", set_array, local+8)[0]
        tail = set_array[local+10:local+14]
        streams = tuple(_read_stream(data, sprite_start+animations_offset, sprite_end,
                                     directions[slot], slot) for slot in range(4))
        result.append(AnimationSet(index, sprite_start+sets_offset+local, speed,
                                   tuple(directions), tail, streams))
    return tuple(result)


def parse_map_sprite_animations(data, map_id, sprite_id):
    """Resolve a map-local sprite pointer using the DATAS map directory."""
    if not 0 <= map_id < 2547:
        raise ValueError("Map ID must be 0-2546")
    try:   # every map, also expanded maps 500+ (their offsets are not in the plain table)
        from map_block_repack import pointers
        base = pointers(data)[map_id]
    except (ValueError, IndexError, struct.error):
        base = struct.unpack_from("<I", data, 0x28 + map_id*4)[0]
    sections = struct.unpack_from("<7I", data, base)
    sprite_start, sprite_end = base+sections[3], base+sections[4]
    table_header = _bounded_read(data, sprite_start, 48, sprite_start, sprite_end)
    offsets = struct.unpack("<12I", table_header)
    return parse_sprite_animation_record(data, sprite_start, sprite_end, sprite_id,
                                         offsets[3], offsets[4])


def prepare_animation_edit(data, animation_set, stream, speed_raw, frame_order,
                           frame_edits=None):
    """Create fixed-size replacements; caller applies them transactionally.

    `frame_order` must be a permutation of the current frames. `frame_edits`
    maps original frame indices to optional raw `delay_raw` and `image_set_index`
    values. Image-set IDs may only refer to an already-present frame source in
    this animation stream, avoiding unverified out-of-range pointers.
    """
    if type(speed_raw) is not int or not 0 <= speed_raw <= 0xFFFF:
        raise ValueError("Animation speed is an unsigned 16-bit value")
    frames = stream.frames
    if sorted(frame_order) != list(range(len(frames))):
        raise ValueError("Frame order must contain every original frame exactly once")
    frame_edits = frame_edits or {}
    known_image_sets = {frame.image_set_index for frame in frames}
    edited = []
    for index, frame in enumerate(frames):
        values = frame_edits.get(index, {})
        delay = values.get("delay_raw", frame.delay_raw)
        image_set = values.get("image_set_index", frame.image_set_index)
        if type(delay) is not int or not 0x80 <= delay <= 0xFF:
            raise ValueError("Drawable frame delay/control must retain its high-bit marker")
        if type(image_set) is not int or image_set not in known_image_sets:
            raise ValueError("Choose an image-set source already used by this animation")
        raw = bytearray(frame.raw)
        raw[0] = delay
        struct.pack_into("<H", raw, 3, image_set)
        edited.append(bytes(raw))
    speed_replacement = struct.pack("<H", speed_raw)
    speed_offset = animation_set.offset+8
    frame_replacement = b"".join(edited[index] for index in frame_order)+stream.terminator
    before_frames = b"".join(frame.raw for frame in frames)+stream.terminator
    changes = []
    if bytes(data[speed_offset:speed_offset+2]) != speed_replacement:
        changes.append((speed_offset, speed_replacement, "Set sprite animation speed"))
    if bytes(data[stream.offset:stream.offset+len(before_frames)]) != frame_replacement:
        changes.append((stream.offset, frame_replacement, "Edit sprite animation frames"))
    return changes
