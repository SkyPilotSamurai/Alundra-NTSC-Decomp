"""Fixed-length editing of natively recovered event operands."""
import json,struct,hashlib
from pathlib import Path
SIZES={int(k):v for k,v in json.loads((Path(__file__).resolve().parents[1]/"data/event-instruction-lengths.json").read_text())["sizes"].items()}
EDITABLE={
 0xA7:("Change music","BB",["Music track ID","Stop sound effects"]),
 2:("Jump to line","h",["Relative jump (signed bytes)"]),
 0x31:("Branch if flag clear","Hh",["Flag operand","Relative jump (signed bytes)"]),
 0x37:("Wait","B",["Scheduler steps"]),
 0x1A:("Change animation","B",["Animation ID"]),
 0x73:("Set repeat counter","B",["Repeat count"]),
 0x74:("Repeat while counter remains","h",["Relative jump (signed bytes)"]),
 0x78:("Call local process","h",["Relative jump (signed bytes)"]),
 0x6B:("Check actor X movement since saved position","H",["World distance"]),
 0x6C:("Check actor Y movement since saved position","H",["World distance"]),
 0x6D:("Check actor Z movement since saved position","H",["World distance"]),
 0x8A:("Spawn existing map template","B3H",["Template index","World X","World Y","World Z"]),
 0x98:("Add money","H",["Amount"]),
 0x99:("Try spending money","H",["Cost (condition true if paid)"]),
 0x9A:("Check money >= amount","H",["Minimum money"]),
 0x9B:("Warp lock ON","",[]),
 0x9C:("Warp lock OFF","",[]),
 0x75:("Play sound effect","B",["Sound effect ID"]),
 5:("Set flag","H",["Flag operand"]),
 6:("Clear flag","H",["Flag operand"]),
 0x30:("Branch if flag set","Hh",["Flag operand","Relative jump (signed bytes)"]),
 0x36:("Wait until flag set","H",["Flag operand"]),
 0x83:("Check item quantity","BB",["Item ID","Minimum quantity"]),
 # Stock USA1.1 bounded instruction evidence:
 # data/2026-10-06-key-door-native-contract.json. These retain native
 # selector operands and fixed lengths; they do not relocate branch targets.
 0x84:("Remove one item if available","B",["Item ID"]),
 0x59:("Change selected actor animation","BB",["Native actor selector","Animation ID"]),
 0x2E:("Mark selected actor inactive","B",["Native actor selector"]),
 0x53:("Change map","H5B",["Destination map","X","Y","Z","Effect","Sound"]),
 3:("Branch if condition true","h",["Relative jump (signed bytes)"]),
 4:("Branch if condition false","h",["Relative jump (signed bytes)"]),
}
def script_roots(session,m):
 from native_script_allocation import script_tables
 base,h=session.layout(m);sp=base+h[3]
 section_end=base+h[4] if h[4]>h[3] else len(session.data)
 signature=hashlib.sha256(memoryview(session.data)[sp:section_end]).digest()
 cache=getattr(session,'_script_roots_cache',None)
 if cache is None:cache={};session._script_roots_cache=cache
 # The map block can move (an earlier map grew) with identical contents: the
 # roots are absolute offsets, so the cache must also match the position.
 signature=(sp,signature)
 if m in cache and cache[m][0]==signature:return cache[m][1]
 header,tables,code,minimum=script_tables(session.data[sp:section_end])
 a=sp+header[6];end=sp+header[0];minimum+=sp
 roots={f"{chr(65+bank)} {index}":(a+value,end,minimum)
         for bank,table in enumerate(tables) for index,value in enumerate(table)
         if value>0 and minimum<=a+value<end}
 cache[m]=(signature,roots);return roots
def _generated_bounds(session,m,roots):
 """Only hash-matched allocator metadata proves an injected root's bounds."""
 bounds={}
 def visit(value):
  if isinstance(value,dict):
   bank=value.get('bank');index=value.get('root_index');count=value.get('code_bytes')
   digest=value.get('code_sha256');key=f'{bank} {index}'
   if value.get('map_id')==m and key in roots and type(count) is int and count>0 and isinstance(digest,str):
    start,end,_=roots[key]
    if start+count<=end and hashlib.sha256(memoryview(session.data)[start:start+count]).hexdigest()==digest:
     bounds[key]=start+count
   for child in value.values():visit(child)
  elif isinstance(value,(list,tuple)):
   for child in value:visit(child)
 visit(getattr(session,'native_event_export_report',[]))
 return bounds

def instructions(session,m,key,*,reachable=False):
 roots=script_roots(session,m);start,end,minimum=roots[key]
 existing=getattr(session,'_script_roots_cache',{}).get(m)
 signature=existing[0] if existing is not None else hashlib.sha256(memoryview(session.data)[minimum:end]).digest()
 generated=_generated_bounds(session,m,roots)
 signature=(signature,tuple(sorted(generated.items())))
 cache=getattr(session,'_instruction_cache',None)
 if cache is None:cache={};session._instruction_cache=cache
 if m not in cache or cache[m][0]!=signature:cache[m]=(signature,{})
 cache_key=(key,reachable)
 if cache_key in cache[m][1]:return list(cache[m][1][cache_key])
 # Follow proven relative branches and calls, retaining alternate paths after
 # an early FF. End/return stop only that path; this is not blind first-FF
 # truncation. Unknown instruction widths terminate their path, visibly.
 storage_end=end
 private_sizes=dict(SIZES)
 from project_state_runtime import OPCODES
 private_sizes.update(OPCODES);private_sizes.update({0xE5:1,0xE6:2,0xE7:2,0xE8:1,0xE9:3,0xEA:2})
 root_keys={r[0]:name for name,r in roots.items()}
 pending=[(start,generated.get(key,end),key in generated)];decoded={};occupied=set()
 while pending and len(decoded)<1024:
  p,end,is_generated=pending.pop()
  sizes=private_sizes if is_generated else SIZES
  while minimum<=p<end and p not in decoded and len(decoded)<1024:
   if p in occupied:break # A malformed branch into an operand stays opaque.
   op=session.data[p];size=sizes.get(op)
   if not size or p+size>end:
    # Never treat the final root's unbounded record/padding storage as a huge
    # unknown command. A subsequent root proves a small opaque span; absent
    # that proof expose the opcode byte only, without claiming native width.
    next_roots=[r[0] for r in roots.values() if p<r[0]<end]
    tail=min(min(next_roots),p+32) if next_roots else p+1
    decoded[p]=(p,op,tail-p);break
   if any(q in occupied for q in range(p,p+size)):break
   decoded[p]=(p,op,size);occupied.update(range(p,p+size))
   if reachable and op in (2,3,4,0x30,0x31,0x74,0x78):
    target=p+struct.unpack_from('<h',session.data,p+size-2)[0]
    if minimum<=target<storage_end and target in root_keys and target not in decoded:
     # A proven call/branch can enter another declared shared root beyond an
     # allocator-bounded caller. That callee has its own verified bound.
     target_key=root_keys[target]
     pending.append((target,generated.get(target_key,storage_end),target_key in generated))
    elif minimum<=target<end and target not in decoded:
     pending.append((target,end,is_generated))
    if op==2:break # Unconditional relative jump has no fall-through.
   if op==255 or reachable and op==0x7D:break
   p+=size
 rows=[decoded[p] for p in sorted(decoded)]
 cache[m][1][cache_key]=tuple(rows)
 return rows

def reachable_instructions(session,m,key):
 """Native UI view, including proven branches beyond the linear first FF."""
 return instructions(session,m,key,reachable=True)

def assign_entity_hook(session,m,index,bank,script_key=None):
 """Point one existing entity hook at an existing map-local script root.

 The one-byte hook layout is source-derived: bit 7 enables the hook and the
 low seven bits select a root in that hook's A-F table. This does not create
 scripts, entities, or establish runtime interaction semantics.
 """
 if bank not in "ABCDEF" or len(bank)!=1:raise ValueError("Entity hook must be A through F")
 from map_inspector import inspect_map
 rows=inspect_map(session.data,m)["entities"]
 if not 0<=index<len(rows):raise ValueError("Entity no longer exists")
 offset=int(rows[index]["offset"],16)+10+ord(bank)-ord("A")
 if script_key is None:
  value=0
 else:
  if script_key not in script_roots(session,m):raise ValueError("Choose an existing map-local script root")
  prefix,raw_index=script_key.split(" ",1)
  if prefix!=bank:raise ValueError("Script root must use the same event hook bank")
  number=int(raw_index,10)
  if not 0<=number<=127:raise ValueError("Script index is outside the native hook range")
  value=0x80|number
 session.replace(offset,bytes([value]),f"Entity {index} {bank} event hook")
 return value
def edit_instruction(session,m,key,offset,values,replacement_opcode=None):
 rows=reachable_instructions(session,m,key);row=next((r for r in rows if r[0]==offset),None)
 if not row or row[1] not in EDITABLE:raise ValueError("Instruction is not editable")
 _,op,size=row
 if replacement_opcode is not None and replacement_opcode!=op:
  if not any(op in group and replacement_opcode in group for group in ((3,4),(5,6),(0x30,0x31),(0x9B,0x9C))):
   raise ValueError("Unsupported command replacement")
  op=replacement_opcode
 name,fmt,labels=EDITABLE[op]
 try:payload=struct.pack("<"+fmt,*values)
 except (struct.error,TypeError):raise ValueError("An operand is outside its native range")
 if len(payload)+1!=size:raise ValueError("Instruction length mismatch")
 if op==0x53 and not 0<=values[0]<2547:raise ValueError("Map must be 0-2546")
 if op in (2,3,4,0x30,0x31,0x74,0x78):
  target=offset+values[-1];_,end,minimum=script_roots(session,m)[key]
  if values[-1]==0 or not minimum<=target<end:raise ValueError("Branch must remain inside map script storage and not yield at offset zero")
  if target not in {r[0] for r in rows}:
   # Existing cross-root targets may be retained verbatim; new targets must be
   # decoded instruction boundaries in the current process.
   old=struct.unpack_from('<'+fmt,session.data,offset+1)[-1]
   if old!=values[-1]:raise ValueError("Choose a decoded destination line")
 if op==0x8A:
  from map_inspector import inspect_map
  if values[0]>=len(inspect_map(session.data,m)['entities']):raise ValueError('Choose an existing map-local template')
 session.replace(offset,bytes([op])+payload,name)
