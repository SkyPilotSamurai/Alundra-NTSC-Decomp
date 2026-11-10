"""Static first-frame previews from map-local sprite records.
Independent parser; format reference xcasadio commit
242b09a20ae1186c90278ba5f15f0f9a84104ef4 AlundraEngine/DatasBin:
SpriteRecord, SpriteTableHeader, SiFrame, SiImageSet, SiImage, GameMap.
Unsupported/transitional frames use the editor's labelled marker fallback.
"""
import struct
from PIL import Image
from texture_codec import unpack_ez

_LOW_NIBBLES=bytes(v&15 for v in range(256))
_HIGH_NIBBLES=bytes(v>>4 for v in range(256))

def indexed_sprite_page(raw,sheet):
 """Expand a 4-bit page in bulk rather than looping over every pixel."""
 start=sheet*32768
 packed=raw[start:start+32768]
 if len(packed)!=32768:raise IndexError('Sprite page outside sheet')
 pixels=bytearray(65536)
 pixels[0::2]=packed.translate(_LOW_NIBBLES)
 pixels[1::2]=packed.translate(_HIGH_NIBBLES)
 return Image.frombytes('P',(256,256),bytes(pixels))


CLONE_BASE={}   # own slot -> original catalogue (enemy_clone), filled by the editor
PREFERRED_FRAMES={428:96,   # Reaper
                  440:24}   # Shadow   # Shadow (440)

def _opaque(image):
 """Number of drawn (non-transparent) pixels."""
 try:return sum(image.getchannel('A').point(lambda v:255 if v else 0).histogram()[255:])
 except Exception:return 0

class EntityPreview:
 def __init__(self,session,m):
  self.data=session.data;self.cache={};self.raw=None
  base,h=session.layout(m);self.start=base+h[3];self.end=base+h[4]
  self.header=self.read("12I",self.start)
  self.sheet_start=base+h[4];self.sheet_end=base+h[5]
 def read(self,fmt,offset):
  size=struct.calcsize("<"+fmt)
  if not self.start<=offset or offset+size>self.end:raise ValueError("Sprite record outside section")
  return struct.unpack_from("<"+fmt,self.data,offset)
 def frame(self,index,direction=0):
  key=(index,direction)
  if key not in self.cache:
   try:self.cache[key]=self.decode(index,direction)
   except (ValueError,IndexError,struct.error):self.cache[key]=None
  return self.cache[key]
 def decode(self,index,direction):
  table,stop=self.header[3:5]
  if not 0<=index<(stop-table)//4:raise ValueError("Sprite index outside table")
  pointer=self.read("i",self.start+table+index*4)[0]
  if pointer<=0:raise ValueError("No map sprite")
  record=self.start+pointer
  sets,animations,_,frames=self.read("4I",record)
  if animations<=sets:raise ValueError("No animation sets")
  offsets=self.read("4H",record+32)
  order=[direction&3]+[d for d in range(4) if d!=(direction&3)]
  offset=next((offsets[d] for d in order if offsets[d]!=65535),None)
  if offset is None:raise ValueError("No direction frame")
  delay,collision,frame=self.read("BHH",self.start+animations+offset)
  if not delay&128:raise ValueError("Transition frame")
  pos=self.start+frames+frame*2
  _,count=self.read("2B",pos)
  if not 0<count<=64:raise ValueError("Unsupported image count")
  return self.images(pos,count)
 def ground_footprint(self,index):
  """Return native sprite collision offsets/sizes used when snapping to terrain.

  SpriteTableHeader stores signed OffsetX/Y/Z and byte SizeX/Y/Z at +0x18.
  EntityManager applies those values before computing the four terrain samples.
  This is source-derived metadata for the editor preview, not a write to DATAS.
  """
  try:
   table,stop=self.header[3:5]
   if not 0<=index<(stop-table)//4:return None
   pointer=self.read("i",self.start+table+index*4)[0]
   if pointer<=0:return None
   return self.read("3b3B",self.start+pointer+24)
  except (ValueError,IndexError,struct.error):return None   # unreadable record: plain marker
 def representative_frame(self,index,direction=0):
  """Database fallback: look beyond a blank/unsupported initial animation."""
  picked=self.preferred_frame(index)
  if picked is not None:return picked
  first=self.frame(index,direction)
  if first is not None and first[0].getbbox() is not None:
   # Some actors (Reaper, Shadow) are only partly drawn in their first pose and
   # show fully only in certain animations: use the fullest frame instead when
   # the first one shows much less than it.
   return first   # (the 'fullest frame' guess picked Alundra's magic burst; only hand-picked poses override)
  key=('representative',index,direction)
  if key in self.cache:return self.cache[key]
  self.cache[key]=None
  try:
   table,stop=self.header[3:5]
   if not 0<=index<(stop-table)//4:return None
   pointer=self.read('i',self.start+table+index*4)[0]
   if pointer<=0:return None
   record=self.start+pointer;sets,animations,_,frames=self.read('4I',record)
   if sets!=pointer+32 or not 1<=(animations-sets)//14<=256:return None
   order=[direction&3]+[d for d in range(4) if d!=(direction&3)]
   for slot in range((animations-sets)//14):
    offsets=self.read('4h',self.start+sets+slot*14)
    for d in order:
     if offsets[d]<0:continue
     pos=self.start+animations+offsets[d]
     for _ in range(64):
      delay=self.read('B',pos)[0]
      if not delay&128:break
      frame=self.read('H',pos+3)[0]
      try:
       result=self.image_set(index,frame)
       if result[0].getbbox() is not None:
        self.cache[key]=result;return result
      except (ValueError,IndexError,struct.error):pass
      pos+=5
  except (ValueError,IndexError,struct.error):pass
  return None
 def preferred_frame(self,index):
  """Hand-picked editor poses (user 2026-10-11): Reaper standing with its
  scythe (#3), Shadow risen over its pool (#4). Map sprite bank only."""
  if getattr(self,'global_bank',False):return None
  frame=PREFERRED_FRAMES.get(index+256,PREFERRED_FRAMES.get(CLONE_BASE.get(index+256)))   # own-slot copies use their original's pose
  if frame is None:return None
  key=('preferred',index)
  if key not in self.cache:
   self.cache[key]=None
   try:
    result=self.image_set(index,frame)
    if result[0].getbbox() is not None:self.cache[key]=result
   except (ValueError,IndexError,struct.error):pass
  return self.cache[key]
 def fullest_frame(self,index,direction=0):
  """The frame (any animation, this facing first) with the most drawn pixels."""
  key=('fullest',index,direction)
  if key in self.cache:return self.cache[key]
  self.cache[key]=None;best=None;best_n=0
  try:
   table,stop=self.header[3:5]
   if not 0<=index<(stop-table)//4:return None
   pointer=self.read('i',self.start+table+index*4)[0]
   if pointer<=0:return None
   record=self.start+pointer;sets,animations,_,frames=self.read('4I',record)
   if sets!=pointer+32 or not 1<=(animations-sets)//14<=256:return None
   decoded={};runs=[]
   for slot in range((animations-sets)//14):
    offsets=self.read('4h',self.start+sets+slot*14)
    d=direction&3
    if offsets[d]<0:continue
    pos=self.start+animations+offsets[d];run=[]
    for _ in range(64):
     delay=self.read('B',pos)[0]
     if not delay&128:break
     frame=self.read('H',pos+3)[0];pos+=5
     if frame not in decoded:
      try:result=self.image_set(index,frame);decoded[frame]=(result,_opaque(result[0]))
      except (ValueError,IndexError,struct.error):decoded[frame]=(None,0)
     run.append(frame)
    runs.append(run)
   top=max((n for _,n in decoded.values()),default=0)
   # The animation where it shows fully (e.g. revealing before an attack):
   # take its first frame that already shows most of it, the "about to
   # attack" pose, not the middle of the swing.
   for run in runs:
    if any(decoded[f][1]==top for f in run):
     for f in run:
      if decoded[f][1]>=.6*top:best,best_n=decoded[f];break
     break
  except (ValueError,IndexError,struct.error):pass
  self.cache[key]=best;return best
 def portrait(self,index):
  key=("portrait",index)
  if key not in self.cache:self.cache[key]=self.decode_portrait(index)
  return self.cache[key]
 def decode_portrait(self,index):
  """First image in the native portrait frame, only when HasPortrait is set.

  Pinned SpriteRecord.GetPortraitImageset uses FramesPointer directly and
  SiImageSet forces one quad for a portrait. This is distinct from a world frame.
  """
  try:
   table,stop=self.header[3:5]
   if not 0<=index<(stop-table)//4:return None
   pointer=self.read("i",self.start+table+index*4)[0]
   if pointer<=0:return None
   record=self.start+pointer
   if not self.read('B',record+18)[0]&128:return None
   frames=self.read('4I',record)[3]
   pos=self.start+frames
   self.read('2B',pos)
   return self.images(pos,1)
  except (ValueError,IndexError,struct.error):return None
 def image_set(self,index,image_set_index):
  key=('imageset',index,image_set_index)
  if key not in self.cache:self.cache[key]=self.decode_image_set(index,image_set_index)
  return self.cache[key]
 def decode_image_set(self,index,image_set_index):
  """Decode an existing frame reference, measured in native halfword units."""
  table,stop=self.header[3:5]
  if not 0<=index<(stop-table)//4:raise ValueError('Sprite outside table')
  pointer=self.read('i',self.start+table+index*4)[0]
  if pointer<=0:raise ValueError('Sprite unavailable')
  frames=self.read('4I',self.start+pointer)[3]
  pos=self.start+frames+image_set_index*2
  _,count=self.read('2B',pos)
  if not 0<count<=64:raise ValueError('Unsupported frame image count')
  return self.images(pos,count)
 def images(self,pos,count):
  if not hasattr(self,'cache'):self.cache={}
  key=('composition',pos,count)
  if key not in self.cache:self.cache[key]=self.compose_images(pos,count)
  return self.cache[key]
 def palette_bytes(self,palette):
  if not hasattr(self,'palette_cache'):self.piece_cache={};self.palette_cache={}
  if palette not in self.palette_cache:
   palstart=self.start+self.header[5]+palette*32
   if palstart+32>self.start+self.header[6]:raise ValueError("Palette outside table")
   words=self.read("16H",palstart)
   colors=[((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31,0 if v==0 else 255) for v in words]
   self.palette_cache[palette]=bytes(channel for color in colors for channel in color)
  return self.palette_cache[palette]
 def transformed_piece(self,sheet,palette,sx,sy,w,h,corners):
  """Texture rectangle drawn onto a rotated/scaled quad (corners: texture
  top-left, top-right, bottom-left, bottom-right), as the GPU's POLY_FT4."""
  if self.raw is None:
   self.raw=unpack_ez(bytes(self.data[self.sheet_start:self.sheet_end]),limit=262144)[0]
  if not hasattr(self,'indexed_pages'):self.indexed_pages={}
  page=sheet&7
  if page not in self.indexed_pages:self.indexed_pages[page]=indexed_sprite_page(self.raw,page)
  texture=self.indexed_pages[page].crop((sx,sy,min(256,sx+w),min(256,sy+h)))
  texture.putpalette(self.palette_bytes(palette),rawmode='RGBA');texture=texture.convert('RGBA')
  xs=[c[0] for c in corners];ys=[c[1] for c in corners]
  left,top=min(xs),min(ys);bw,bh=max(1,max(xs)-left),max(1,max(ys)-top)
  source=((0,0),(w,0),(0,h),(w,h))
  # Solve the perspective map destination -> source from the 4 point pairs.
  rows=[];rhs=[]
  for (dx,dy),(u,v) in zip(corners,source):
   dx-=left;dy-=top
   rows.append([dx,dy,1,0,0,0,-u*dx,-u*dy]);rhs.append(u)
   rows.append([0,0,0,dx,dy,1,-v*dx,-v*dy]);rhs.append(v)
  coeffs=_solve(rows,rhs)
  if coeffs is None:return (left,top,Image.new('RGBA',(bw,bh)))
  return (left,top,texture.transform((bw,bh),Image.Transform.PERSPECTIVE,coeffs,Image.Resampling.NEAREST))
 def compose_images(self,pos,count):
  if self.raw is None:
   self.raw=unpack_ez(bytes(self.data[self.sheet_start:self.sheet_end]),limit=262144)[0]
  pieces=[]
  for i in range(count):
   sheet,palette,sx,sy,w,h,x1,y1,x2,y2,x3,y3,x4,y4=self.read("6B8b",pos+2+i*14)
   if not w or not h:continue
   if x1!=x3 or x2!=x4 or y1!=y2 or y3!=y4:
    # Rotated/scaled quad: map the texture rectangle onto its four corners.
    pieces.append(self.transformed_piece(sheet,palette,sx,sy,w,h,((x1,y1),(x2,y2),(x3,y3),(x4,y4))));continue
   flipx=x1>x2;flipy=y1>y3
   sx+=int(flipx and sx+w<256);sy+=int(flipy and sy+h<256)
   if sx+w>256 or sy+h>256:raise ValueError("Sprite crop outside page")
   dw,dh=abs(x2-x1),abs(y3-y1)
   if not dw or not dh:continue
   if not hasattr(self,'piece_cache'):self.piece_cache={};self.palette_cache={}
   key=(sheet&7,palette,sx,sy,w,h,flipx,flipy,dw,dh)
   image=self.piece_cache.get(key)
   if image is None:
    if palette not in self.palette_cache:
     palstart=self.start+self.header[5]+palette*32
     if palstart+32>self.start+self.header[6]:raise ValueError("Palette outside table")
     words=self.read("16H",palstart)
     colors=[((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31,0 if v==0 else 255) for v in words]
     self.palette_cache[palette]=bytes(channel for color in colors for channel in color)
    if not hasattr(self,'indexed_pages'):self.indexed_pages={}
    page=sheet&7
    if page not in self.indexed_pages:self.indexed_pages[page]=indexed_sprite_page(self.raw,page)
    image=self.indexed_pages[page].crop((sx,sy,sx+w,sy+h))
    image.putpalette(self.palette_cache[palette],rawmode='RGBA')
    image=image.convert('RGBA')
    if flipx:image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flipy:image=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if image.size!=(dw,dh):image=image.resize((dw,dh),Image.Resampling.NEAREST)
    self.piece_cache[key]=image
   pieces.append((min(x1,x2),min(y1,y3),image))
  if not pieces:raise ValueError("Empty sprite")
  left=min(x for x,y,im in pieces);top=min(y for x,y,im in pieces)
  right=max(x+im.width for x,y,im in pieces);bottom=max(y+im.height for x,y,im in pieces)
  image=Image.new("RGBA",(right-left,bottom-top))
  # Native ordering-table insertion renders the last quad first. The first
  # record is the foreground (often an NPC's face), not the background.
  # Pinned GraphicManager.RenderEntities/RenderEffects also iterate backwards.
  for x,y,im in reversed(pieces):image.alpha_composite(im,(x-left,y-top))
  return image,left,top


def _solve(rows,rhs):
 """Gaussian elimination for the 8x8 perspective system; None if degenerate."""
 n=len(rhs);m=[list(map(float,r))+[float(b)] for r,b in zip(rows,rhs)]
 for c in range(n):
  p=max(range(c,n),key=lambda r:abs(m[r][c]))
  if abs(m[p][c])<1e-9:return None
  m[c],m[p]=m[p],m[c]
  for r in range(n):
   if r!=c:
    f=m[r][c]/m[c][c]
    m[r]=[a-f*b for a,b in zip(m[r],m[c])]
 return [m[i][n]/m[i][i] for i in range(n)]


def is_transformed(data,pos,count):
 """True when an image set at `pos` has a rotated/scaled quad."""
 for i in range(count):
  x1,y1,x2,y2,x3,y3,x4,y4=struct.unpack_from('<8b',data,pos+8+i*14)
  if data[pos+6+i*14] and (x1!=x3 or x2!=x4 or y1!=y2 or y3!=y4):return True
 return False


def cached_preview(session,map_id,global_bank=False):
 """Reuse decoded frames until their actual sprite/texture bytes change."""
 import hashlib
 from types import SimpleNamespace
 if global_bank:
  start,sheet=struct.unpack_from('<2I',session.data)
  end=struct.unpack_from('<I',session.data,0x14)[0]
  if not 0<=start<sheet<end<=len(session.data):raise ValueError('Global sprite bank bounds invalid')
  view=SimpleNamespace(data=session.data,layout=lambda ignored:(0,(0,0,0,start,sheet,end,0)))
 else:
  base,h=session.layout(map_id);start=base+h[3];sheet=base+h[4];end=base+h[5];view=session
  if not 0<=start<=sheet<=end<=len(session.data):raise ValueError('Map sprite bank bounds invalid')
 signature=hashlib.sha256(memoryview(session.data)[start:end]).digest()
 key=(global_bank,start,sheet,end,signature)
 cache=getattr(session,'_entity_preview_cache',None)
 if cache is None:cache={};session._entity_preview_cache=cache
 if key not in cache:
  if not getattr(session,'_full_asset_preload',False) and len(cache)>=8:cache.pop(next(iter(cache)))
  for previous in list(cache):
   if previous[:4]==key[:4] and previous!=key:cache.pop(previous,None)   # the background loader may have removed it
  cache[key]=EntityPreview(view,map_id);cache[key].global_bank=global_bank
 return cache[key]
