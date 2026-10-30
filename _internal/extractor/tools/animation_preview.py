"""Actual native frame sequences for a database animation player.

Frame counts/delays/terminator bytes remain native. Tick->milliseconds is a
user-selected preview rate, not a claim of engine framerate. Format/runtime
interpretation is source-reported at xcasadio242b09a20ae1186c90278ba5f15f0f9a84104ef4.
"""
from dataclasses import dataclass
from types import SimpleNamespace
import struct
from PIL import Image
from entity_preview import EntityPreview,cached_preview
from entity_animation import parse_sprite_animation_record


@dataclass(frozen=True)
class PreviewFrame:
    index:int
    offset:int
    delay_raw:int
    ticks:int
    image_set_index:int
    collision_raw:int
    image:object
    left:int
    top:int
    unsupported_reason:str|None=None


@dataclass(frozen=True)
class AnimationClip:
    catalogue_index:int
    animation_index:int
    requested_direction:int
    selected_direction:int
    native_speed_raw:int
    frames:tuple
    terminator:bytes
    terminal_kind:str
    next_animation:int|None

    @property
    def duration_ticks(self):return sum(f.ticks for f in self.frames)

    @property
    def bounds(self):
        supported=[f for f in self.frames if f.image is not None]
        if not supported:return (0,0,1,1)
        return (min(f.left for f in supported),min(f.top for f in supported),
                max(f.left+f.image.width for f in supported),
                max(f.top+f.image.height for f in supported))

    def frame_at_tick(self,tick):
        if type(tick) is not int or tick<0:raise ValueError('Preview tick must be a nonnegative integer')
        if self.terminal_kind=='loop':tick%=self.duration_ticks
        else:tick=min(tick,self.duration_ticks-1)
        for frame in self.frames:
            if tick<frame.ticks:return frame
            tick-=frame.ticks
        return self.frames[-1]

    def canvas_image(self,frame):
        """Fixed entity-origin canvas avoids jumping when frame crop size varies."""
        left,top,right,bottom=self.bounds
        canvas=Image.new('RGBA',(right-left,bottom-top))
        if frame.image is not None:canvas.alpha_composite(frame.image,(frame.left-left,frame.top-top))
        return canvas


def terminal_meaning(raw):
    """Preserve the source transition encoding instead of pretending all loops."""
    if raw==b'\x01':return 'loop',None
    if len(raw)==2 and raw[0]==0:
        return ('hold',None) if raw[1]&128 else ('change',raw[1])
    if len(raw)==1 and 1<raw[0]<128:return 'change',0
    return 'unknown',None


def animation_reader(session,map_id,catalogue_index):
    if type(catalogue_index) is not int or not 0<=catalogue_index<512:
        raise ValueError('Catalogue index outside native two-bank identity')
    if catalogue_index<256:
        start,sheet=struct.unpack_from('<2I',session.data)
        end=struct.unpack_from('<I',session.data,0x14)[0]
        if not 0<=start<=start+48<=sheet<end<=len(session.data):
            raise ValueError('Global sprite texture bounds invalid')
        view=SimpleNamespace(data=session.data,
            layout=lambda ignored:(0,(0,0,0,start,sheet,end,0)))
        preview=cached_preview(session,0,True)
    else:preview=cached_preview(session,map_id)
    cache=getattr(preview,'animation_sets',None)
    if cache is None:cache={};preview.animation_sets=cache
    sprite=catalogue_index&255
    if sprite not in cache:
        cache[sprite]=parse_sprite_animation_record(session.data,preview.start,preview.end,sprite,*preview.header[3:5])
    sets=cache[sprite]
    return preview,sets


def available_animations(session,map_id,catalogue_index):
    _,sets=animation_reader(session,map_id,catalogue_index)
    return tuple(dict(index=s.index,native_speed_raw=s.speed_raw,
                      direction_frames=tuple(0 if st is None else len(st.frames) for st in s.streams),
                      direction_terminators=tuple(None if st is None else st.terminator.hex() for st in s.streams))
                 for s in sets)


def load_animation(session,map_id,catalogue_index,animation_index=0,direction=0,*,fallback_direction=True):
    preview,sets=animation_reader(session,map_id,catalogue_index)
    if type(animation_index) is not int or not 0<=animation_index<len(sets):
        raise ValueError('Animation outside native set directory')
    if type(direction) is not int or not 0<=direction<4:raise ValueError('Direction slot must be0..3')
    anim=sets[animation_index];selected=direction;stream=anim.streams[selected]
    if stream is None and fallback_direction:
        selected=next((i for i,st in enumerate(anim.streams) if st is not None),None)
        stream=None if selected is None else anim.streams[selected]
    if stream is None:raise ValueError('Animation has no drawable stream for selected direction')
    frames=[];cache={}
    for i,frame in enumerate(stream.frames):
        key=frame.image_set_index
        if key not in cache:
            try:cache[key]=(*preview.image_set(catalogue_index&255,key),None)
            except (ValueError,IndexError,struct.error) as exc:cache[key]=(None,0,0,str(exc))
        image,left,top,reason=cache[key]
        frames.append(PreviewFrame(i,frame.offset,frame.delay_raw,max(1,frame.delay_raw&127),
                                   key,frame.collision_raw,image,left,top,reason))
    kind,next_animation=terminal_meaning(stream.terminator)
    return AnimationClip(catalogue_index,animation_index,direction,selected,anim.speed_raw,
                         tuple(frames),stream.terminator,kind,next_animation)


def preview_delay_ms(ticks,tick_rate=60,playback_multiplier=1):
    """Explicit display-only speed conversion. Native raw values are not edited."""
    if type(ticks) is not int or ticks<1 or tick_rate<=0 or playback_multiplier<=0:
        raise ValueError('Positive tick count, preview tick rate and speed required')
    return max(1,round(1000*ticks/tick_rate/playback_multiplier))
