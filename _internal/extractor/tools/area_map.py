"""Map-grid and wall records. Source-derived, static rendering (no map-copy scripts).
Reference xcasadio242b09a20ae1186c90278ba5f15f0f9a84104ef4:
DatasBin/Map.cs,MapTile.cs,WallTiles.cs; GameMap.cs:212-244.
"""
import struct
import math
from PIL import Image

def first_visible_row(image,background=(31,34,40,255)):
 """Top row containing rendered map pixels, ignoring the flat canvas backing."""
 if image.mode!="RGBA":image=image.convert("RGBA")
 width,height=image.size
 if width<=0 or height<=0:return 0
 raw=image.tobytes();background_row=bytes(background)*width;stride=width*4
 for y in range(height):
  if raw[y*stride:(y+1)*stride]!=background_row:return y
 return 0

def map_y_to_view(y,crop_top=0):
 """Convert original rendered-map Y into the cropped canvas coordinate."""
 return y-crop_top

def view_y_to_map(y,crop_top=0):
 """Convert a cropped canvas Y back to the renderer's map coordinate."""
 return y+crop_top

def grid(session,m):
 base,h=session.layout(m);start=base+h[1];w,height=session.data[start:start+2]
 first=start+4+256*6;end=first+w*height*8
 if not w or not height or end>base+h[2]:raise ValueError("Invalid map tile grid")
 cells=[]
 for y in range(height):
  for x in range(w):
   o=first+8*(y*w+x);v=struct.unpack_from("<4BHh",session.data,o)
   walls=[]
   if v[5]!=-1:
    p=end+v[5]*2
    if p<end or p+2>base+h[2]:raise ValueError("Invalid wall list")
    shift,count=struct.unpack_from("<bB",session.data,p)
    if p+2+2*count>base+h[2]:raise ValueError("Truncated wall list")
    walls=[(p+2+2*i,struct.unpack_from("<H",session.data,p+2+2*i)[0],shift,i) for i in range(count)]
   cells.append(dict(x=x,y=y,offset=o,values=v,walls=walls))
 return w,height,cells
def edit_cell(session,m,x,y,values):
 w,h,cells=grid(session,m)
 if not 0<=x<w or not 0<=y<h:raise ValueError("Cell outside map")
 if len(values)!=5 or any(not 0<=v<=255 for v in values[:4]) or not 0<=values[4]<=65535:raise ValueError("Tile fields out of range")
 session.replace(cells[y*w+x]["offset"],struct.pack("<4BH",*values),"Map tile")
def edit_height(session,m,x,y,delta,cells=None,width=None):
 """Increment/decrement one tile's native byte height; each click is undoable.
 cells/width: the grid the map view already read (no re-read of the whole
 map per click); the height byte is read from the game data itself."""
 if delta not in (-1,1):raise ValueError("Height changes are one step per click")
 if cells is None or width is None:
  width,h,cells=grid(session,m)
 else:h=len(cells)//max(1,width)
 if not 0<=x<width or not 0<=y<h:raise ValueError("Tile outside map")
 offset=cells[y*width+x]["offset"];new=session.data[offset+3]+delta
 if not 0<=new<=255:raise ValueError("Tile height is already at its byte limit")
 session.replace(offset+3,bytes((new,)),"Map tile")
 return new
def tile_at_canvas(renderer,x,y,hit_index):
 """Resolve a visible floor/wall surface to its underlying height-bearing cell."""
 hit=renderer.surface_at(x,y)
 if hit is not None:return hit[2],hit[3]
 cell=hit_index.get((int(x)//24,int(y)//16))
 return (cell[2],cell[3]) if cell is not None else None
def entity_preview_anchor(x,y,z,cells,width,height,margin,elevation=True,footprint=None):
 """Return the native actor origin projected onto the editor map.

 Raw entity XYZ are half-tile steps: runtime X/Y are x*12+12,y*8+8 pixels,
 and stored height is z*8 pixels. On load, native code clamps PosZ to the
 terrain height if it starts below the floor; it does not add the record
 height to the terrain height. When available, the sprite header footprint
 (offsetX/Y/Z,sizeX/Y) supplies the same four terrain samples as the game.
 """
 actor_x=x*12+12
 actor_y=y*8+8+margin
 tile_x=math.floor(actor_x/24);tile_y=math.floor((y*8+8)/16)
 ground_height=0
 offsets=(0,0,0,1,1,1) if footprint is None else footprint
 ox,oy,oz,sx,sy,_=offsets
 px1=actor_x+ox;py1=y*8+8+oy
 px2=px1+max(0,sx-1);py2=py1+max(0,sy-1)
 points=((px1,py1),(px2,py1),(px1,py2),(px2,py2))
 heights=[]
 for px,py in points:
  tx=math.floor(px/24);ty=math.floor(py/16)
  if 0<=tx<width and 0<=ty<height:
   heights.append(cells[ty*width+tx]["values"][3])
 if heights:ground_height=max(heights)
 if elevation:
  native_z=max(z*8-oz,ground_height*16)
  actor_y-=native_z
 return actor_x,actor_y,ground_height

def entity_tile_selection_anchor(x,y,cells,width,height,margin,elevation=True):
 """Return the visible ground-tile center/bottom for picking an entity."""
 tile_x=math.floor(x/2);tile_y=math.floor(y/2)
 ground_height=0
 if 0<=tile_x<width and 0<=tile_y<height:
  ground_height=cells[tile_y*width+tile_x]["values"][3]
 projected_height=ground_height*16 if elevation else 0
 return tile_x*24+12,(tile_y+1)*16+margin-projected_height,ground_height
def tile_stroke_steps(dx,dy):
 """Bound paint-drag interpolation to one sample per crossed map tile."""
 return max(1,math.ceil(max(abs(dx)/24,abs(dy)/16)))
def edit_wall(session,m,x,y,index,tile):
 w,h,cells=grid(session,m)
 if not 0<=x<w or not 0<=y<h or not 0<=tile<=65535:raise ValueError("Invalid wall edit")
 walls=cells[y*w+x]["walls"]
 if not 0<=index<len(walls):raise ValueError("Wall layer outside cell")
 o,_,_,_=walls[index]
 session.replace(o,struct.pack("<H",tile),"Wall tile (shared list)")
class MapRenderer:
 def __init__(self,session,m):
  self.session=session;self.m=m;self.raw=session.texture(m)[0];self.cache={}
 def tile(self,code):
  if code in self.cache:return self.cache[code]
  tile=code&1023;palette=(code>>12)&15
  image=Image.new("RGBA",(24,16),(0,0,0,0))
  if code!=65535 and tile<960:
   words,_=self.session.palette(self.m,palette)
   colors=[((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31,0 if v==0 else 255) for v in words]
   tx=tile%10*12;ty=tile//10*16
   pixels=[]
   for y in range(16):
    for b in self.raw[(ty+y)*128+tx:(ty+y)*128+tx+12]:
     pixels.extend((colors[b&15],colors[b>>4]))
   image.putdata(pixels)
  self.cache[code]=image
  return image
 def render(self,elevation=True):
  w,h,cells=grid(self.session,self.m)
  margin=max((c["values"][3] for c in cells),default=0)*16 if elevation else 0
  image=Image.new("RGBA",(w*24,h*16+margin),(31,34,40,255));hits=[];self.surface_hits={}
  for c in cells:
   v=c["values"];x=c["x"]*24;y=c["y"]*16+margin-(v[3]*16 if elevation else 0)
   image.alpha_composite(self.tile(v[4]),(x,y))
   hits.append((x,y,c["x"],c["y"]))
   self.surface_hits.setdefault((x//24,y//16),[]).append((x,y,c["x"],c["y"],"Floor",v[4]))
   if elevation:
    for _,code,shift,i in c["walls"]:
     wall_y=y+(i+1-shift)*16
     image.alpha_composite(self.tile(code),(x,wall_y))
     self.surface_hits.setdefault((x//24,wall_y//16),[]).append((x,wall_y,c["x"],c["y"],f"Wall {i}",code))
  return image,hits,margin

 def surface_at(self,x,y):
  candidates=self.surface_hits.get((int(x)//24,int(y)//16),[])
  for px,py,tx,ty,layer,code in reversed(candidates):
   if self.tile(code).getpixel((int(x-px),int(y-py)))[3]:return px,py,tx,ty,layer,code
  return next((hit for hit in reversed(candidates) if hit[4]=="Floor"),None)


def render_region(renderer, cells, width, margin, rect, elevation=True):
    """Picture of rect (left, top, right, bottom, in render() coordinates) drawn
    from `cells` (map_area_copy.cells_of rows: values, walls=(shift, codes) or
    None) the same way render() draws the map. The editor shows edits that
    wait for save/build with it, without drawing the whole map again."""
    left, top, right, bottom = rect
    image = Image.new("RGBA", (right - left, bottom - top), (31, 34, 40, 255))
    for index, c in enumerate(cells):
        x = index % width * 24
        if x + 24 <= left or x >= right:
            continue
        v = c['values']; y = index // width * 16 + margin - (v[3] * 16 if elevation else 0)
        pieces = [(v[4], y)]
        if elevation and c.get('walls'):
            shift, codes = c['walls']
            pieces += [(code, y + (i + 1 - shift) * 16) for i, code in enumerate(codes)]
        for code, py in pieces:
            if py + 16 <= top or py >= bottom or code == 0xFFFF:
                continue
            tile = renderer.tile(code)
            image.paste(tile, (x - left, py - top), tile)
    return image


def piece_rows(cell, row, margin, elevation=True):
    """Top and bottom pixel (render() coordinates) a cell covers."""
    v = cell['values']; y = row * 16 + margin - (v[3] * 16 if elevation else 0)
    top, bottom = y, y + 16
    if elevation and cell.get('walls'):
        shift, codes = cell['walls']
        for i in range(len(codes)):
            py = y + (i + 1 - shift) * 16; top = min(top, py); bottom = max(bottom, py + 16)
    return top, bottom
