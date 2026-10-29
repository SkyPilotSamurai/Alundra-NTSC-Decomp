"""Structural map-block replacement. Native allocation safety is NOT established.

The map pointer table has483entries plus an end sentinel. Shift subsequent
entries together, preserving their blocks byte-for-byte. No files are written.
Do not treat successful parser checks as emulator validation.
"""
import struct

COUNT=483
TABLE=0x28

import os

class OwnedData(bytearray):
 """Game data that one build step owns outright (the event compiler's working
 copy): replace_block edits it in place instead of copying all ~130 MB for
 every small change (2026-10-15: 392 copies were 2/3 of the compile time).
 Plain bytes / bytearray keep the old copy-on-change behaviour."""

def owned(data):
 """data as OwnedData (the same object when it already is one)."""
 if isinstance(data,OwnedData) and data.__dict__.get('inplace',True) and not os.environ.get('ALUNDRA_NO_INPLACE'):return data
 return OwnedData(data) if not os.environ.get('ALUNDRA_NO_INPLACE') else bytearray(data)

def owned_copy(data):
 """A new OwnedData copy of data (the caller's data is never edited)."""
 return bytearray(data) if os.environ.get('ALUNDRA_NO_INPLACE') else OwnedData(data)

_OWNED_CLASSES={}

def own_session_data(session):
 """Make session.data an OwnedData for the rest of a build step: whatever is
 assigned to session.data is kept as OwnedData (copied once only when a step
 hands back plain data), so every following replace_block edits in place.
 release_session_data() undoes it. The session must be the step's own copy."""
 if os.environ.get('ALUNDRA_NO_INPLACE'):return session
 base=type(session)
 if base not in _OWNED_CLASSES:
  def get(self):return self.__dict__['_owned_data']
  def put(self,value):
   self.__dict__['_owned_data']=value if isinstance(value,OwnedData) else OwnedData(value)
  _OWNED_CLASSES[base]=type('Owned'+base.__name__,(base,),{'data':property(get,put),'_owned_base':base})
 data=session.__dict__.pop('data',None)
 session.__class__=_OWNED_CLASSES[base]
 if isinstance(data,OwnedData) and data.__dict__.pop('fresh',False):
  session.data=data      # made for this step only (stock_donors.prepare): taken over as it is
 else:
  session.data=OwnedData(data)   # otherwise always this step's own copy
 return session

def release_session_data(session):
 """Back to a plain session holding plain data."""
 base=getattr(type(session),'_owned_base',None)
 if base is None:return session
 data=session.__dict__.pop('_owned_data')
 session.__class__=base
 data.inplace=False   # from here on it is ordinary data: no in-place edits (no 130 MB copy needed)
 session.data=data
 return session

_CHECKED=set()

def pointers(data):
 """Offsets of every existing map plus the end of the last one: the 483 stock
 maps, new slots 483-499 and expanded maps 500+ (see map_slots)."""
 from map_slots import offsets,table_end,ENTRIES,_offsets_key
 if len(data)<TABLE+4*ENTRIES:raise ValueError("Truncated map table")
 key=_offsets_key(data)
 values=offsets(data)
 if key is not None and key in _CHECKED:return values   # this header was checked already
 if values[0]<TABLE+4*ENTRIES or values[-1]!=table_end(data):raise ValueError("Unsupported map table bounds")
 if any(a>=b or a%2048 for a,b in zip(values,values[1:])) or values[-1]%2048:
  raise ValueError("Unsupported map alignment/order")
 if key is not None:
  if len(_CHECKED)>256:_CHECKED.clear()
  _CHECKED.add(key)
 return values

def sections(block):
 if len(block)<28:raise ValueError("Truncated map block")
 offsets=list(struct.unpack_from("<7I",block))
 if offsets[0]!=28 or any(v%4 for v in offsets) or any(a>b for a,b in zip(offsets,offsets[1:])) or offsets[-1]>len(block):
  raise ValueError("Unsupported section offsets")
 return offsets

def _trim_text_tail(block):
 """Drop the zero bytes after the last string of the map's text section (the
 block's last section: 128 offsets, then zero-terminated strings). Every edit
 re-padded the block to 2048 with the old padding still inside it, so each
 script / text / record allocation grew the map by 2 KB (2026-10-15). No text
 lookup reads past a string's terminator, so those bytes are never used."""
 try:
  start=sections(block)[6]
 except ValueError:
  return block
 if len(block)-start<256:return block
 end=start+256
 for value in struct.unpack_from('<128h',block,start):
  if value>0 and start+value<len(block):
   stop=block.find(0,start+value)
   if stop<0:return block
   end=max(end,stop+1)
 end+=(-end)%4
 if end>=len(block) or any(block[end:]):return block
 return block[:end]

def replace_block(data,map_id,block):
 old=pointers(data)
 if type(map_id) is not int or not 0<=map_id<len(old)-1:raise ValueError("Map outside table")
 sections(block)
 block=_trim_text_tail(bytes(block))
 block=bytes(block)+bytes((-len(block))%2048)
 start,end=old[map_id:map_id+2];delta=len(block)-(end-start)
 from map_slots import serialize
 if isinstance(data,OwnedData) and data.__dict__.get('inplace',True) and not os.environ.get('ALUNDRA_NO_INPLACE'):
  if delta==0:
   data[start:end]=block
   return data
  new=[p+(delta if i>map_id else 0) for i,p in enumerate(old)]
  del data[old[-1]:]                 # the old extended table (serialize writes it again)
  data[start:end]=block              # bytearray shifts the rest in place
  result=serialize(data,new)
  if result is not data:raise ValueError('In-place map table update failed')
  assert pointers(result)==new
  return result
 view=memoryview(data)
 if delta==0:
  # Same padded size (the usual case): one copy, block written in place.
  result=bytearray(view);result[start:end]=block
  return result
 # One pass build; serialize then writes the table in place.
 new=[p+(delta if i>map_id else 0) for i,p in enumerate(old)]
 # one preallocated buffer: each byte copied once (was three growing copies)
 result=bytearray(new[-1]);result[:start]=view[:start];result[start:start+len(block)]=block
 rest=view[end:old[-1]];result[start+len(block):start+len(block)+len(rest)]=rest
 result=serialize(result,new)
 assert pointers(result)==new
 return result

def transplant_sprite_sections(data,target,donor):
 """Copy complete donor sprite-info and compressed sprite pages as one unit.

All donor entity/script behavior remains; this is a structural experiment,
not authored dungeon content. Original target terrain, scroll and text retained.
"""
 values=pointers(data)
 if not all(type(m) is int and 0<=m<COUNT for m in (target,donor)):
  raise ValueError("Map outside table")
 tb=bytes(data[values[target]:values[target+1]])
 db=bytes(data[values[donor]:values[donor+1]])
 th,dh=sections(tb),sections(db)
 sprite=db[dh[3]:dh[5]]
 block=bytearray(tb[:th[3]]+sprite+tb[th[5]:])
 shift=len(sprite)-(th[5]-th[3])
 new=th[:];new[4]=th[3]+dh[4]-dh[3];new[5]+=shift;new[6]+=shift
 struct.pack_into("<7I",block,0,*new)
 return replace_block(data,target,block)


def replace_section(data,map_id,index,replacement):
 """Replace one complete section, preserving all other section byte sequences."""
 if len(replacement)%4:raise ValueError('Replacement section must preserve four-byte alignment')
 if type(index) is not int or not 0<=index<6:raise ValueError("Only bounded sections0..5 supported")
 values=pointers(data);block=bytes(data[values[map_id]:values[map_id+1]])
 h=sections(block);start,end=h[index:index+2];delta=len(replacement)-(end-start)
 result=bytearray(block[:start])+bytes(replacement)+block[end:]
 new=[offset+(delta if i>index else 0) for i,offset in enumerate(h)]
 struct.pack_into("<7I",result,0,*new)
 return replace_block(data,map_id,result)
