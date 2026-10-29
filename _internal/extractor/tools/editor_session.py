"""Undoable fixed-size DATAS edits. Originals are retained and never overwritten."""
import hashlib,json,struct
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from map_inspector import verify_datas,verify_compatible_datas,inspect_map
from texture_codec import unpack_ez,pack_ez,pack_ez_fit

@dataclass
class DocumentEdit:
    target:dict
    before:dict
    after:dict
    label:str
    byte_changes:tuple=()

@dataclass
class GrowEdit:
    """New map blocks appended after the original DATAS (map slots 483-499)."""
    before_tail:bytes
    after_tail:bytes
    label:str
    byte_changes:tuple=()   # (offset, before, after) inside the original-size region

@dataclass
class GroupEdit:
    """Several edits made by one action; undone and redone together."""
    members:tuple
    label:str

def restore_document_edit(change,desired,previous):
    """Restore only this operation's list delta, retaining later class edits."""
    for key in set(desired)|set(previous):
        wanted=desired.get(key);old=previous.get(key)
        if wanted==old:continue
        if isinstance(wanted,list) and isinstance(old,list):
            current=change.target.setdefault(key,[])
            for row in old:
                if row not in wanted:
                    if key=='event_graphs':current[:]=[r for r in current if r.get('id')!=row['id']]
                    elif row in current:current.remove(row)
            for index,row in enumerate(wanted):
                if row not in old:
                    if key=='event_graphs' and any(r.get('id')==row['id'] for r in current):
                        raise ValueError('Cannot restore an event whose ID has been reused')
                    if row not in current:current.insert(min(index,len(current)),deepcopy(row))
        elif key not in desired:change.target.pop(key,None)
        else:change.target[key]=deepcopy(wanted)

class EditSession:
    def __init__(self,data,path=None,verify=True,allow_compatible=False):
        self.source_verified=False
        if verify:
            try:
                verify_datas(data);self.source_verified=True
            except ValueError:
                if not allow_compatible:raise
                verify_compatible_datas(data)
        self.original=bytes(data);self.data=bytearray(data);self.path=Path(path).resolve() if path else None
        self.undo_stack=[];self.redo_stack=[]
    @classmethod
    def readonly(cls,data):
        """A session for reading scripts only (no copies of the ~130 MB data;
        callers never edit it). The build made dozens of full copies this way."""
        self=cls.__new__(cls)
        self.source_verified=False;self.original=data;self.data=data;self.path=None
        self.undo_stack=[];self.redo_stack=[]
        return self
    @classmethod
    def open_data(cls,data,path,allow_compatible=False):
        try:return cls(data,path,allow_compatible=allow_compatible)
        except ValueError:
            sidecar=Path(str(path)+".alundra-edit.json")
            if not sidecar.exists():raise ValueError("Unknown build. Open the original DATAS or an editor copy with its .alundra-edit.json sidecar.")
            patch=json.loads(sidecar.read_text())
            if hashlib.sha256(data).hexdigest()!=patch.get("result_sha256"):raise ValueError("Edited copy does not match its sidecar")
            original=bytearray(data)
            for c in reversed(patch["changes"]):
                o=c["offset"];before=bytes.fromhex(c["before"]);after=bytes.fromhex(c["after"])
                if not isinstance(o,int) or o<0 or len(before)!=len(after) or o+len(after)>len(original) or original[o:o+len(after)]!=after:raise ValueError("Invalid edited-copy sidecar")
                original[o:o+len(before)]=before
            session=cls(original,path,allow_compatible=allow_compatible)
            session.apply_patch(patch)
            return session

    def replace(self,offset,replacement,label):
        replacement=bytes(replacement)
        if offset<0 or offset+len(replacement)>len(self.data):raise ValueError("Edit outside file")
        before=bytes(self.data[offset:offset+len(replacement)])
        if before==replacement:return
        self.data[offset:offset+len(replacement)]=replacement
        self._push((offset,before,replacement,label))
    def group(self,label):
        """`with session.group('label'):` -- every edit inside is one undo step."""
        from contextlib import contextmanager
        @contextmanager
        def scope():
            start=len(self.undo_stack)
            try:yield
            finally:
                members=self.undo_stack[start:]
                if len(members)>1:
                    del self.undo_stack[start:]
                    group=GroupEdit(tuple(members),label)
                    self.undo_stack.append(group)
                    parts=self.__dict__.setdefault('_parts',{})
                    infos=[parts.pop(id(m),None) for m in members]
                    if all(i is not None for i in infos):
                        maps=set();rows=[];structural=False;known=True
                        for i in infos:
                            if i['maps'] is None:known=False
                            else:maps|=i['maps']
                            rows+=i['parts'];structural=structural or i['structural']
                        parts[id(group)]=dict(maps=maps if known else None,parts=rows,structural=structural,change=group)
        return scope()
    def _undo_one(self,change):
        if isinstance(change,GroupEdit):
            for member in reversed(change.members):self._undo_one(member)
            return
        if isinstance(change,DocumentEdit):
            restore_document_edit(change,change.before,change.after);self.content_database=change.target
            for o,b,a in reversed(change.byte_changes):self.data[o:o+len(b)]=b
        elif isinstance(change,GrowEdit):
            self._set_tail(change.before_tail)
            for o,b,a in reversed(change.byte_changes):self.data[o:o+len(b)]=b
        else:o,b,a,_=change;self.data[o:o+len(b)]=b
    def _redo_one(self,change):
        if isinstance(change,GroupEdit):
            for member in change.members:self._redo_one(member)
            return
        if isinstance(change,DocumentEdit):
            restore_document_edit(change,change.after,change.before);self.content_database=change.target
            for o,b,a in change.byte_changes:self.data[o:o+len(a)]=a
        elif isinstance(change,GrowEdit):
            self._set_tail(change.after_tail)
            for o,b,a in change.byte_changes:self.data[o:o+len(a)]=a
        else:o,b,a,_=change;self.data[o:o+len(a)]=a
    def _set_tail(self,tail):
        """Replace the grown part after the original data. If something still
        holds a view of the data (a preview), the bytearray cannot change size
        in place ("BufferError: Existing exports..."), so use a fresh copy."""
        try:self.data[len(self.original):]=tail
        except BufferError:self.data=bytearray(bytes(self.data[:len(self.original)])+bytes(tail))
    def undo(self):
        if self.undo_stack and isinstance(self.undo_stack[-1],GroupEdit):
            change=self.undo_stack.pop();self._undo_one(change);self.redo_stack.append(change);return
        if self.undo_stack:
            change=self.undo_stack.pop()
            if isinstance(change,DocumentEdit):
                restore_document_edit(change,change.before,change.after);self.content_database=change.target
                for o,b,a in reversed(change.byte_changes):self.data[o:o+len(b)]=b
            elif isinstance(change,GrowEdit):
                self._set_tail(change.before_tail)
                for o,b,a in reversed(change.byte_changes):self.data[o:o+len(b)]=b
            else:o,b,a,_=change;self.data[o:o+len(b)]=b
            self.redo_stack.append(change)
    def redo(self):
        if self.redo_stack and isinstance(self.redo_stack[-1],GroupEdit):
            change=self.redo_stack.pop();self._redo_one(change);self.undo_stack.append(change);return
        if self.redo_stack:
            change=self.redo_stack.pop()
            if isinstance(change,DocumentEdit):
                restore_document_edit(change,change.after,change.before);self.content_database=change.target
                for o,b,a in change.byte_changes:self.data[o:o+len(a)]=a
            elif isinstance(change,GrowEdit):
                self._set_tail(change.after_tail)
                for o,b,a in change.byte_changes:self.data[o:o+len(a)]=a
            else:o,b,a,_=change;self.data[o:o+len(a)]=a
            self.undo_stack.append(change)
    def set_tail(self,tail,label,byte_changes=()):
        """Replace everything after the original DATAS (new map blocks) as one undo step."""
        start=len(self.original);changes=[]
        for offset,after in byte_changes:
            after=bytes(after)
            if offset<0 or offset+len(after)>start:raise ValueError('Map table edit outside the original data')
            changes.append((offset,bytes(self.data[offset:offset+len(after)]),after))
        change=GrowEdit(bytes(self.data[start:]),bytes(tail),label,tuple(changes))
        self.data[start:]=tail
        for o,b,a in changes:self.data[o:o+len(a)]=a
        self._push(change)
    def replace_document(self,target,replacement,label,byte_changes=()):
        changes=[]
        for offset,after in byte_changes:
            after=bytes(after)
            if offset<0 or offset+len(after)>len(self.data):raise ValueError('Document edit outside game data')
            changes.append((offset,bytes(self.data[offset:offset+len(after)]),after))
        # Copy only the parts that change; unchanged parts are shared by the
        # undo snapshots (restore_document_edit skips keys that are equal).
        changed={k for k in set(target)|set(replacement)
                 if k not in target or k not in replacement or target[k] is not replacement[k] and target[k]!=replacement[k]}
        before={k:(deepcopy(v) if k in changed else v) for k,v in target.items()}
        after={k:(deepcopy(v) if k in changed else target[k]) for k,v in replacement.items()}
        change=DocumentEdit(target,before,after,label,tuple(changes))
        for k in [k for k in target if k not in replacement]:del target[k]
        for k in changed:
            if k in replacement:target[k]=deepcopy(replacement[k])
        self.content_database=target
        for o,b,a in changes:self.data[o:o+len(a)]=a
        self._push(change)
    # -- per-map undo: Undo / Redo take back the last change on the map you are on
    def _push(self,change):
        """Record a change (already applied): which maps it touches, and how to
        take it back on its own later. Redo steps of those maps are dropped."""
        info=None
        try:info=self._map_info(change)
        except Exception:info=None
        if info is not None:self.__dict__.setdefault('_parts',{})[id(change)]=info
        self.undo_stack.append(change)
        maps=info['maps'] if info else None
        if getattr(change,'label','')=='Import foreign map tiles':return   # background picture write: redo steps stay
        keep=[]
        for old in self.redo_stack:
            other=self._info(old)
            if maps is None or other is None or other['maps'] is None or other['maps']&maps:
                self.__dict__.get('_parts',{}).pop(id(old),None)   # dropped for good
                continue
            keep.append(old)
        self.redo_stack[:]=keep
    def _info(self,change):
        info=self.__dict__.get('_parts',{}).get(id(change))
        return info if info is not None and info.get('change') is change else None
    def _pointers(self,data=None):
        from map_block_repack import pointers
        return pointers(self.data if data is None else data)
    def _byte_parts(self,rows,ptrs):
        """(offset, before, after) rows as map-relative parts ('bytes', map,
        offset in the map block, before, after); outside any map: ('abs', ...)."""
        import bisect
        parts=[];maps=set()
        for o,b,a in rows:
            i=0
            while i<len(a):
                at=o+i
                m=bisect.bisect_right(ptrs,at)-1
                if 0<=m<len(ptrs)-1:
                    end=min(o+len(a),ptrs[m+1])
                    parts.append(('bytes',m,at-ptrs[m],bytes(b[i:end-o]),bytes(a[i:end-o])));maps.add(m)
                else:
                    end=o+len(a) if m<0 else o+len(a)
                    if m<0:end=min(end,ptrs[0])
                    parts.append(('abs',at,bytes(b[i:end-o]),bytes(a[i:end-o])))
                i=end-o
        return parts,maps
    def _map_info(self,change):
        if isinstance(change,GroupEdit):return None
        if isinstance(change,GrowEdit):
            limit=len(self.original)
            before=bytearray(self.data[:limit])
            for o,b,a in change.byte_changes:before[o:o+len(b)]=b
            before+=change.before_tail
            pb=self._pointers(before);pa=self._pointers()
            parts=[];maps=set();structural=len(pb)!=len(pa)
            for m in range(min(len(pb),len(pa))-1):
                if pa[m]<limit and pb[m]<limit and pa[m+1]<=limit and pb[m+1]<=limit:continue
                old=bytes(before[pb[m]:pb[m+1]]);new=bytes(self.data[pa[m]:pa[m+1]])
                if old!=new:parts.append(('block',m,old,new));maps.add(m)
            if structural:
                for m in range(min(len(pb),len(pa))-1,max(len(pb),len(pa))-1):maps.add(m)
            return dict(maps=maps,parts=parts,structural=structural,change=change)
        ptrs=self._pointers()
        if isinstance(change,DocumentEdit):
            parts,maps=self._byte_parts(change.byte_changes,ptrs)
            b=change.before.get('event_graphs');a=change.after.get('event_graphs')
            if b is not a:
                old={r.get('id'):r for r in (b or [])};new={r.get('id'):r for r in (a or [])}
                for key in set(old)|set(new):
                    if old.get(key)!=new.get(key):
                        for row in (old.get(key),new.get(key)):
                            if row is not None and type(row.get('map_id')) is int:maps.add(row['map_id'])
            others=[k for k in set(change.before)|set(change.after) if k!='event_graphs' and change.before.get(k) is not change.after.get(k)
                    and change.before.get(k)!=change.after.get(k)]
            parts.append(('doc',change))
            return dict(maps=maps if (maps or not others) else None,parts=parts,structural=False,change=change)
        o,b,a,_=change
        parts,maps=self._byte_parts([(o,b,a)],ptrs)
        return dict(maps=maps or None,parts=parts,structural=False,change=change)
    def _find(self,stack,m):
        for i in range(len(stack)-1,-1,-1):
            info=self._info(stack[i])
            if info is None or info['maps'] is None or m in info['maps']:return i
        return None
    def last_for_map(self,m,redo=False):
        """The most recent undo (or redo) step of map m, or None."""
        stack=self.redo_stack if redo else self.undo_stack
        i=self._find(stack,m)
        return None if i is None else stack[i]
    def _apply_parts(self,info,forward):
        """Take a change back (forward=False) or put it in again on its own,
        map by map, against the data as it is now."""
        from map_block_repack import replace_block
        rows=info['parts'] if forward else list(reversed(info['parts']))
        # check everything first: nothing is written unless all of it fits
        ptrs=self._pointers()
        for part in rows:
            if part[0]=='bytes':
                _,m,rel,b,a=part;want=b if forward else a;at=ptrs[m]+rel
                if bytes(self.data[at:at+len(want)])!=want:raise ValueError('This map changed since; undo the later change on it first')
            elif part[0]=='block':
                _,m,b,a=part;want=b if forward else a
                if bytes(self.data[ptrs[m]:ptrs[m+1]])!=want:raise ValueError('This map changed since; undo the later change on it first')
            elif part[0]=='abs':
                _,at,b,a=part;want=b if forward else a
                if bytes(self.data[at:at+len(want)])!=want:raise ValueError('The game data changed since; undo the later change first')
        extra=self.__dict__.setdefault('_extra_spans',[])
        limit=len(self.original)
        for part in rows:
            if part[0]=='doc':
                change=part[1]
                if forward:restore_document_edit(change,change.after,change.before)
                else:restore_document_edit(change,change.before,change.after)
                self.content_database=change.target
            elif part[0]=='bytes':
                _,m,rel,b,a=part;ptrs=self._pointers();at=ptrs[m]+rel;new=a if forward else b
                self.data[at:at+len(new)]=new
                if at<limit:extra.append((at,min(at+len(new),limit)))
            elif part[0]=='abs':
                _,at,b,a=part;new=a if forward else b
                self.data[at:at+len(new)]=new
                if at<limit:extra.append((at,min(at+len(new),limit)))
            elif part[0]=='block':
                _,m,b,a=part;new=a if forward else b
                header=self._pointers()[0]   # the map table lies before the first map
                result=replace_block(self.data,m,new)
                if len(result)<limit:raise ValueError('Map table change outside the grown data')
                old_head=bytes(self.data[:header]);new_head=bytes(result[:header])
                extra.extend((j,j+1) for j in range(header) if old_head[j]!=new_head[j])
                try:self.data[:]=result
                except BufferError:self.data=bytearray(result)
    def undo_map(self,m):
        """Take back the last change on map m (changes on other maps stay).
        Returns the change, or None when map m has nothing to undo."""
        i=self._find(self.undo_stack,m)
        if i is None:return None
        change=self.undo_stack[i]
        if i==len(self.undo_stack)-1:
            self.undo();return change
        info=self._info(change)
        if info is None or info['structural'] or info['maps'] is None:
            label=change[-1] if isinstance(change,tuple) else getattr(change,'label','')
            raise ValueError(f"The last change on this map ({label}) is tied to later changes elsewhere; undo those first")
        self._apply_parts(info,forward=False)
        del self.undo_stack[i];self.redo_stack.append(change)
        return change
    def redo_map(self,m):
        """Put back the last change undone on map m."""
        i=self._find(self.redo_stack,m)
        if i is None:return None
        change=self.redo_stack[i]
        if i==len(self.redo_stack)-1:
            self.redo();return change
        info=self._info(change)
        if info is None or info['structural'] or info['maps'] is None:
            raise ValueError('Redo the later changes on other maps first')
        self._apply_parts(info,forward=True)
        del self.redo_stack[i];self.undo_stack.append(change)
        return change
    def patch(self):
        if getattr(self,'compiled_project',False):raise ValueError('Use Save mod for compiled dungeon projects; DATAS-only patches omit the required executable')
        spans=[];limit=len(self.original)
        def flat(changes):
            for change in changes:
                if isinstance(change,GroupEdit):yield from flat(change.members)
                else:yield change
        for change in flat(self.undo_stack):
            rows=change.byte_changes if isinstance(change,(DocumentEdit,GrowEdit)) else [change[:3]]
            # Edits inside new map blocks are carried by the tail below.
            spans.extend((o,min(o+len(a),limit)) for o,b,a in rows if o<limit)
        spans.extend(getattr(self,'_extra_spans',[]))   # written by a per-map undo / redo
        spans.sort()
        merged=[]
        for start,end in spans:
            if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
            else:merged.append([start,end])
        changes=[]
        for start,end in merged:
            i=start
            while i<end:
                if self.original[i]==self.data[i]:i+=1;continue
                j=i+1
                while j<end and self.original[j]!=self.data[j]:j+=1
                changes.append(dict(offset=i,before=self.original[i:j].hex(),after=self.data[i:j].hex()))
                i=j
        result=dict(format="alundra-datas-patch-v1",base_sha256=hashlib.sha256(self.original).hexdigest(),
                    result_sha256=hashlib.sha256(self.data).hexdigest(),changes=changes)
        if len(self.data)>limit:
            import base64,zlib
            result['tail']=base64.b64encode(zlib.compress(bytes(self.data[limit:]),9)).decode('ascii')
        return result
    def apply_patch(self,p):
        if self.undo_stack or self.redo_stack or self.data!=self.original:raise ValueError("Load patches into a fresh original session")
        if p.get("format")!="alundra-datas-patch-v1" or p.get("base_sha256")!=hashlib.sha256(self.original).hexdigest():raise ValueError("Patch build mismatch")
        trial=bytearray(self.data);previous=0;edits=[]
        for c in p["changes"]:
            o=c["offset"];b=bytes.fromhex(c["before"]);a=bytes.fromhex(c["after"])
            if not isinstance(o,int) or o<previous or not b or len(b)!=len(a) or o+len(b)>len(trial) or trial[o:o+len(b)]!=b:raise ValueError("Invalid patch preimage or overlap")
            trial[o:o+len(a)]=a;previous=o+len(b);edits.append((o,a))
        tail=b''
        if p.get('tail'):
            import base64,zlib
            tail=zlib.decompress(base64.b64decode(p['tail']))
        if hashlib.sha256(bytes(trial)+tail).hexdigest()!=p.get("result_sha256"):raise ValueError("Patch result hash mismatch")
        for o,a in edits:self.replace(o,a,"Imported patch")
        if tail:self.set_tail(tail,"Imported new maps")
    def save_copy(self,path):
        path=Path(path).resolve()
        if path==self.path:raise ValueError("Choose a different file; original is protected")
        sidecar=Path(str(path)+".alundra-edit.json")
        if sidecar.exists():raise ValueError("A sidecar already exists for that name; choose another")
        metadata=json.dumps(self.patch(),indent=2)
        with path.open("xb") as stream:stream.write(self.data)
        try:
            with sidecar.open("x",encoding="utf-8") as stream:stream.write(metadata)
        except Exception:
            path.unlink() # Only the new file just created by this method.
            raise
    def layout(self,m):
        from map_slots import map_exists,is_new_slot
        if not map_exists(self.data,m):raise ValueError(f"Map {m} has not been created yet" if is_new_slot(m) else "Map number is out of range")
        from map_slots import map_base
        base=map_base(self.data,m)
        h=struct.unpack_from("<7I",self.data,base)
        return base,h
    def texture(self,m):
        base,h=self.layout(m);start=base+h[2];end=base+h[3]
        pending=getattr(self,'_pending_textures',None)
        if pending and m in pending:return pending[m],start,end   # imported tiles not compressed yet
        signature=hashlib.sha256(memoryview(self.data)[start:end]).digest()
        key=(start,end,signature)
        cache=getattr(self,'_texture_cache',None)
        if cache is None:cache={};self._texture_cache=cache
        if key not in cache:
            raw,_=unpack_ez(self.data[start:end])
            if len(raw)%32768:raise ValueError("Unsupported partial texture sheet")
            # Replace outdated versions of this source section, keeping other maps.
            for previous in list(cache):
                if previous[:2]==key[:2]:del cache[previous]
            cache[key]=raw
        return cache[key],start,end
    def defer_palette(self,offset,payload):
        """A palette an import needs; written with the waiting texture."""
        if not hasattr(self,'_pending_palettes'):self._pending_palettes={}
        self._pending_palettes[offset]=bytes(payload)
    def defer_texture(self,m,raw):
        """Map m shows texture `raw` from now on; map_tile_import.flush_texture
        compresses it into the game data later (save, build, undo, map change,
        or in the background)."""
        if not hasattr(self,'_pending_textures'):self._pending_textures={}
        self._pending_textures[m]=bytes(raw)
    def set_texture(self,m,raw):
        old,start,end=self.texture(m)
        if len(raw)!=len(old):raise ValueError("Texture dimensions cannot change")
        if raw==old:return
        packed=pack_ez_fit(raw,bytes(self.data[start:start+6]),end-start)
        decoded,_=unpack_ez(packed)
        if decoded!=raw:raise ValueError("Texture round-trip failed")
        if len(packed)>end-start:raise ValueError(f"Edited texture needs {len(packed)} bytes; room has {end-start}. Simplify the edit.")
        self.replace(start,packed+bytes(end-start-len(packed)),"Texture pixels")
        getattr(self,'_pending_textures',{}).pop(m,None)   # the painted texture includes it
    def palette(self,m,index):
        if not 0<=index<32:raise ValueError("Palette must be 0-31")
        base,h=self.layout(m);o=base+h[0]+16+index*32
        waiting=getattr(self,'_pending_palettes',None)
        if waiting and o in waiting:return list(struct.unpack("<16H",waiting[o])),o   # imported, not written yet
        return list(struct.unpack_from("<16H",self.data,o)),o
    def set_palette_color(self,m,palette,index,rgb):
        words,o=self.palette(m,palette)
        if not 0<=index<16:raise ValueError("Colour must be 0-15")
        # Retain bit15 and PS1 BGR555 word layout (red in the low five bits).
        r,g,b=rgb;word=(words[index]&32768)|((b>>3)<<10)|((g>>3)<<5)|(r>>3)
        self.replace(o+index*2,struct.pack("<H",word),"Palette colour")
    def edit_record(self,m,kind,index,values):
        info=inspect_map(self.data,m)
        row=info[kind][index];o=int(row["offset"],16)
        raw=bytearray(self.data[o:o+(20 if kind=="entities" else 8)])
        limits=([255]*16+[65535,65535]) if kind=="entities" else [255]*8
        if len(values)!=len(limits) or any(not 0<=v<=limit for v,limit in zip(values,limits)):raise ValueError("A field is outside its range")
        packed=struct.pack("<16B2H",*values) if kind=="entities" else bytes(values)
        if (kind=="entities" and packed[2:4]==bytes(2)) or (kind=="events" and packed[:4]==bytes(4)):raise ValueError("This rectangle would terminate the table")
        if values[0]>values[2] or values[1]>values[3]:raise ValueError("Rectangle minimum exceeds maximum")
        self.replace(o,packed,kind+" record")
