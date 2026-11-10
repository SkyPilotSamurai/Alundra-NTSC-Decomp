"""Source-reported content names and local reference icons; no asset import."""
import csv
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "242b09a20ae1186c90278ba5f15f0f9a84104ef4"

def entity_names():
    with (ROOT / "data/upstream-entity-names.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))

# Native data review 2026-10-12 (sprite headers + built-in AI programs):
# projectiles and parts the game spawns for an enemy/boss are objects, not enemies,
# and these enemy entries run boss AI / belong to boss fights.
ATTACK_PARTS = {330, 351, 357, 366, 372, 411, 413, 414, 415, 419, 420, 423, 432, 444, 462, 464, 465, 468,
                474, 475, 477, 480, 481, 498, 469, 483, 484, 496, 502, 503, 504, 505, 507, 510, 511}
ENEMY_BOSSES = {412, 446, 447, 448, 450, 459, 460, 471, 472, 479, 497, 499}
BOSS_MINIONS = {508}
# Slots that are empty in the US game (no sprite) and used for the editor's own-slot copies.
EMPTY_US_SLOTS = {331, 334}
# Catalogue entries with no class of their own: Twin Demons' second half (501) is made by
# Twin Demons (500) when the fight starts and is never placed (2026-10-17, user).
HIDDEN_CATALOGUE = {501, 353}   # 353 'Alicia': no sprite on either disc, never placed (removed 2026-10-18, user)

def classify(index, name):
    # Catalogue grouping, not proof of a particular AI or runtime behavior.
    if index in ATTACK_PARTS: return 'object'
    if index in ENEMY_BOSSES: return 'boss'
    if index in BOSS_MINIONS: return 'enemy'
    if index in (476,482):return 'boss' # User-confirmed Soul Leech/Werewolf.
    if index == 0: return "player"
    if re.match(r'^I\d+_',name): return "item"
    if name.startswith("◆"):
        return "boss" if any(s in name.lower() for s in ("boss", "melzas", "king", "zorgia", "nilude", "abyss", "centipede", "beam brother")) else "enemy"
    # 380 Chicken, 381 Crow: listed with NPCs (user request 2026-10-08).
    if 256 <= index <= 289 or index in (302,331,332,333,334,339,349,353,354,355,358,359,360,378,379,380,381,399,400,402,417,434): return "npc"   # 378 King Miming, 379 Bonaire (YM03 Variant): NPCs (user 2026-10-15)
    return "object"

def icon_path(name):
    def key(value): return re.sub(r"[^a-z0-9]", "", value.lower())
    aliases = {"herb": "herbs", "armor": "armour", "bomb":"miningbomb", "strengthelixyr":"strengthelixir", "magicelixyr":"magicelixir"}
    wanted = key(name).replace("armor", "armour")
    wanted = aliases.get(wanted, wanted)
    folder = ROOT / "Alundra Crowd Control/item_sprites"
    for path in sorted(folder.glob("*.png")):
        if path.stem.endswith("-") or path.stem.startswith(("Swap_", "Force_")): continue
        if key(path.stem) == wanted: return path
    return None

def item_names():
    from native_item_catalogue import native_items
    native=native_items()
    if native is not None:return native
    path = ROOT / "extras/game edits/src/game/data/item.json"
    legacy=json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    # A machine without private retail resources still gets entries. Progressive
    # placeholders do not become asserted vanilla names in that fallback.
    return [{**row,'name':f'Unnamed item {i:02X}' if row.get('tier')==64 else row['name']} for i,row in enumerate(legacy)]

def item_kind(index,items=None):
    items=item_names() if items is None else items
    slot=items[index].get('slot') if index<len(items) else None
    if slot in (1,2,3,4,5,6):return 'weapon'
    if slot in (7,9):return 'armor'
    return 'item'

def graphic_maps(datas):
    """Index local sprite records, including slots not instantiated on a map."""
    found={}
    for m in range(483):
        try:
            base=struct.unpack_from('<I',datas,0x28+m*4)[0]
            h=struct.unpack_from('<7I',datas,base);start,end=base+h[3],base+h[4]
            if not 0<=start<end<=len(datas) or end-start<48:continue
            table,stop=struct.unpack_from('<2I',datas,start+12)
            if not 48<=table<=stop<=end-start or (stop-table)%4:continue
            for i in range(min(256,(stop-table)//4)):
                pointer=struct.unpack_from('<i',datas,start+table+i*4)[0]
                if 48<=pointer<=end-start-32:found.setdefault(256+i,[]).append(m)
        except (ValueError,IndexError,struct.error):continue
    return found

def preview_maps(source):
    maps=list(source.get('observed_maps',[]))+list(source.get('graphic_maps',[]))
    if source.get('observed_map') is not None:maps.insert(0,source['observed_map'])
    return list(dict.fromkeys(maps)) or [0]

def preview_hue(image,row):
    """Preview the native RGB555 hue operation without changing the input art."""
    palette=row.get('data',{}).get('palette_shift',{}) or {}
    degrees=palette.get('hue_degrees',0) or 0;saturation=palette.get('saturation_percent',100)
    if not degrees and saturation==100:return image
    from local_sprite_recolor import shift_hue
    pixels=list(image.get_flattened_data() if hasattr(image,'get_flattened_data') else image.getdata());colors={}
    for rgba in set(pixels):
        r,g,b,a=rgba;word=round(r*31/255)|(round(g*31/255)<<5)|(round(b*31/255)<<10)
        changed=shift_hue([word]*16,degrees,saturation)[0]
        colors[rgba]=((changed&31)*255//31,((changed>>5)&31)*255//31,((changed>>10)&31)*255//31,a)
    result=image.copy();result.putdata([colors[p] for p in pixels]);return result

def _reference_image_uncached(session,row):
    """Return an actual local item icon or decoded map-local source frame."""
    from PIL import Image
    if row['kind'] in ('item','weapon','armor'):
        path=icon_path(row['name'])
        if path:
            with Image.open(path) as asset:return asset.convert('RGBA')
    if session is None:return None
    index=row.get('source',{}).get('catalogue_index')
    if index is not None:
        from native_class_placement import class_preview
        maps=preview_maps(row.get('source',{}))
        facing={'down':0,'up':1,'left':2,'right':3}.get(row.get('source',{}).get('default_facing'),0)   # Red Block, Pattern Plate Moon...
        source=row.get('source',{})
        if facing==0 and not source.get('variant') and not source.get('own_slot') and not source.get('clone_art_catalogue'):
            import object_library   # the game's own class: its picture from the object library
            if object_library.available():
                picture=object_library.preview(index)
                if picture is not None:return preview_hue(picture,row)
        for map_id in maps or [0]:
            try:result=class_preview(source_for(session,map_id),map_id,index,facing)
            except (ValueError,IndexError,KeyError,struct.error):continue
            if result is not None:return preview_hue(result[0],row)
    from entity_preview import EntityPreview,cached_preview
    source=row.get('source',{});sprite=source.get('sprite_id')
    if sprite is None:sprite=row['data'].get('world_sprite',row['data'].get('source_sprite',row['data'].get('sprite_reference')))
    if sprite is None:return None
    maps=preview_maps(source)
    for map_id in maps:
        try:result=cached_preview(source_for(session,map_id),map_id).representative_frame(sprite)
        except (ValueError,IndexError,KeyError,struct.error):continue
        if result is not None:return preview_hue(result[0],row)
    return None

def portrait_image(session,row):
    """Decode the portrait linked to the same native class as its world graphic."""
    if session is None:return None
    from entity_preview import EntityPreview,cached_preview
    from types import SimpleNamespace
    import struct
    source=row.get('source',{});index=source.get('catalogue_index')
    if index is None:return None
    if index<256:
        from native_class_placement import global_sprite_available
        if not global_sprite_available(session.data,index):return None
        start,sheet=struct.unpack_from('<2I',session.data)
        end=struct.unpack_from('<I',session.data,0x14)[0]
        if not sheet<end<=len(session.data):return None
        view=SimpleNamespace(data=session.data,layout=lambda ignored:(0,(0,0,0,start,sheet,end,0)))
        result=cached_preview(session,0,True).portrait(index)
        return preview_hue(result[0],row) if result else None
    for map_id in preview_maps(source):
        try:result=cached_preview(source_for(session,map_id),map_id).portrait(index&255)
        except (ValueError,IndexError,KeyError,struct.error):continue
        if result:return preview_hue(result[0],row)
    return None


_MISSING=object()
from stock_donors import source_for, stock_view   # game objects are drawn from the original game's maps

def reference_image(session,row,database=True):
    """Cache small class thumbnails against actual asset bytes and class edits.
    database=False: the picture as placed on a map (Tri-Color Switch unlit, grey)."""
    from placement_catalogue import INVISIBLE_OBJECTS
    if row.get('source',{}).get('catalogue_index') in INVISIBLE_OBJECTS:return None   # transparent blocks: nothing is drawn in game
    if row.get('source',{}).get('graphic_source'):row=dict(row,source=row['source']['graphic_source'])
    if row.get('source',{}).get('variant')=='tricolor' and not database:
        row=dict(row,source={k:v for k,v in row['source'].items() if k!='variant'})   # the grey switch
    if row.get('source',{}).get('variant')=='tricolor' and session is not None:   # database only   # Tri-Color Switch: lit in its colour
        try:
            import animation_preview as A
            facing={'down':0,'up':1,'left':2,'right':3}.get(row['source'].get('default_facing'),0)
            f=A.load_animation(source_for(session,75),75,383,1,facing).frames[0]
            if f.image is not None:return f.image.convert('RGBA')
        except Exception:pass
    if row.get('source',{}).get('variant')=='sage':   # a sage: its crest map's effect sprite, standing
        try:
            from sage_npc import preview
            return preview(row['source'].get('sage_map'))
        except Exception:return None
    if row.get('source',{}).get('variant')=='warp_panel':   # Warp Panel
        try:
            from heal_tile import preview
            return preview(stock_view(session) if session is not None else session,'panel')
        except Exception:return None
    if row.get('source',{}).get('variant')=='block_switch':   # Block Switch: the orb from Giles' nightmare
        try:
            from block_switch import preview
            return preview(session)
        except Exception:return None
    if row.get('source',{}).get('variant')=='floor_switch':   # Step On Switch (Floor)
        try:
            from heal_tile import preview
            return preview(stock_view(session) if session is not None else session,'switch')
        except Exception:return None
    if row.get('source',{}).get('variant')=='heal_tile':   # Healing Tile: the save room's floor plate
        try:
            from heal_tile import preview
            return preview(stock_view(session) if session is not None else session,row['source'].get('heal_tile'))
        except Exception:return None
    if session is None or not hasattr(session,'data'):return _reference_image_uncached(session,row)
    import hashlib
    source=row.get('source',{});index=source.get('catalogue_index')
    signatures=[]
    candidates=preview_maps(source)
    if type(index) is int and index<256:candidates=[None]
    for map_id in dict.fromkeys(candidates):
        try:
            if map_id is None:
                start,sheet=struct.unpack_from('<2I',session.data);end=struct.unpack_from('<I',session.data,0x14)[0]
            else:
                src=source_for(session,map_id);base,h=src.layout(map_id);start=base+h[3];end=base+h[5]
                if not 0<=start<=end<=len(src.data):raise ValueError('Invalid asset bounds')
                signatures.append((map_id,start,end,hashlib.sha256(memoryview(src.data)[start:end]).digest()));continue
            if not 0<=start<=end<=len(session.data):raise ValueError('Invalid asset bounds')
            signatures.append((map_id,start,end,hashlib.sha256(memoryview(session.data)[start:end]).digest()))
        except (ValueError,IndexError,KeyError,struct.error):signatures.append((map_id,None))
    key=(row.get('id',(row['kind'],row['name'])),row['kind'],row['name'],repr(source),repr(row.get('data',{}).get('palette_shift')),tuple(signatures))
    cache=getattr(session,'_class_thumbnail_cache',None)
    if cache is None:cache={};session._class_thumbnail_cache=cache
    value=cache.get(key,_MISSING)
    if value is _MISSING:   # (None is a valid cached answer: class without a picture)
        # (the background loader can fill this cache at the same time)
        for previous in list(cache):
            if previous[0]==key[0] and previous!=key:cache.pop(previous,None)
        if not getattr(session,'_full_asset_preload',False) and len(cache)>=512:cache.pop(next(iter(cache)),None)
        value=cache[key]=_reference_image_uncached(session,row)
    return value
