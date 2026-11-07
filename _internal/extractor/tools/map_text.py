"""Fixed-capacity map text editing; retain literal game control tokens."""
import struct,hashlib

def entries(session,m):
 if m is None:
  # Shared dialogue table: source-reported DATAS header +0x0C.
  start=struct.unpack_from("<I",session.data,0x0C)[0]
  boundaries=[struct.unpack_from("<I",session.data,p)[0] for p in (0,4,8,16,24,28,32,36)]
  base=start
 else:
  base,h=session.layout(m);start=base+h[6];boundaries=[]
 # Map boundaries come from the map table, not a guessed universal size.
 offsets=[struct.unpack_from("<I",session.data,0x28+i*4)[0] for i in range(501)]  # incl. new map slots
 end=min((o for o in offsets+boundaries if start<o<=len(session.data)),default=len(session.data))
 if not 0<=start<=end-256:return []
 signature=hashlib.sha256(memoryview(session.data)[start:end]).digest()
 cache=getattr(session,'_dialogue_cache',None)
 if cache is None:cache={};session._dialogue_cache=cache
 if m in cache and cache[m][0]==(start,end,signature):return list(cache[m][1])
 rows=[]
 for i in range(128):
  relative=struct.unpack_from("<h",session.data,start+i*2)[0]
  if relative<256:continue
  pos=start+relative
  if not start+256<=pos<end:continue
  stop=session.data.find(0,pos,end)
  if stop<0:continue
  rows.append((i,pos,bytes(session.data[pos:stop])))
 cache[m]=((start,end,signature),tuple(rows))
 return rows

def edit_text(session,m,index,text):
 row=next((r for r in entries(session,m) if r[0]==index),None)
 if row is None:raise ValueError("Text entry not found")
 _,offset,old=row
 try:new=text.encode("latin-1")
 except UnicodeEncodeError:raise ValueError("This text contains characters outside the game's byte character set")
 if b"\0" in new:raise ValueError("Text cannot contain a zero byte")
 if len(new)>len(old):raise ValueError(f"This text has room for {len(old)} bytes; your edit uses {len(new)}")
 # Preserve the original terminator and capacity by padding with spaces.
 session.replace(offset,new.ljust(len(old),b" "),"Map dialogue text")


def dialogue_reference(data,offset):
 """Source-derived display-text operands: high bit selects map-local storage."""
 op=data[offset]
 operand={0x0D:1,0x5C:2}.get(op)
 if operand is None:return None
 value=data[offset+operand]
 return bool(value&128),value&127

def dialogue_entry(session,m,offset):
 reference=dialogue_reference(session.data,offset)
 if reference is None:return None
 return next((r for r in entries(session,m if reference[0] else None) if r[0]==reference[1]),None)


def edit_dialogue(session,m,offset,text):
 reference=dialogue_reference(session.data,offset)
 if reference is None:raise ValueError("Not a supported Show Text command")
 edit_text(session,m if reference[0] else None,reference[1],text)
