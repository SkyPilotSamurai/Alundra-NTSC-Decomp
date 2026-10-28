"""Alundra EZ texture codec, independently implemented from the stream format.
Format reference: xcasadio 242b09a20ae1186c90278ba5f15f0f9a84104ef4,
AlundraTools/AlundraEngine/Graphics/ImageHelper.cs:23-111.
"""
from collections import defaultdict, deque
_UNPACK_MEMO = {}


def unpack_ez(source, limit=196608):
    """Decode an EZ stream (remembered: a build decodes the same donor pages
    many times; the result depends only on the bytes and the limit)."""
    import hashlib
    if not isinstance(source,(bytes,bytearray)):source=bytes(source)
    key=(hashlib.sha1(source).digest(),len(source),limit)
    hit=_UNPACK_MEMO.get(key)
    if hit is not None:return hit
    result=_unpack_ez(source,limit)
    if len(_UNPACK_MEMO)>=128:_UNPACK_MEMO.pop(next(iter(_UNPACK_MEMO)))
    _UNPACK_MEMO[key]=result
    return result


def _unpack_ez(source, limit=196608):
    if source[:2] != b"EZ" or len(source)<6:
        raise ValueError("Not an EZ texture block")
    if not isinstance(source,(bytes,bytearray)):source=bytes(source)
    out=bytearray();i=6;size=len(source)
    while i<size:
        # Literal runs can be copied in bulk; avoid one Python loop per pixel.
        stop=source.find(b"\xad",i)
        if stop<0:stop=size
        if stop>i:
            available=limit-len(out)
            if available<=0:raise ValueError("Texture exceeds size limit")
            count=min(stop-i,available)
            out.extend(source[i:i+count]);i+=count
            if len(out)==limit:return bytes(out),i
        if i>=size:break
        i+=1
        if i>=size:raise ValueError("Truncated escape")
        distance=source[i];i+=1
        if distance==0:out.append(173)
        else:
            if i>=size:raise ValueError("Truncated match")
            length=source[i];i+=1
            if distance==255 and length==0:return bytes(out),i
            if length==0 or distance>len(out):raise ValueError("Invalid match")
            if len(out)+length>limit:raise ValueError("Texture exceeds size limit")
            window=out[-distance:]
            out.extend((window*((length+distance-1)//distance))[:length])
        if len(out)>limit:raise ValueError("Texture exceeds size limit")
        if len(out)==limit:return bytes(out),i
    raise ValueError("Texture block ended without terminator")

_EZ_MEMO = {}


def pack_ez(raw, header=b"EZ\0\0\0\0"):
    """pack_ez, remembered: the same pixels always pack to the same stream,
    so earlier results are reused (in memory and on disk) instead of
    recompressing on every build (was ~0.5 s a page)."""
    import hashlib
    from pathlib import Path
    key = hashlib.sha256(bytes(header) + bytes(raw)).hexdigest()
    hit = _EZ_MEMO.get(key)
    if hit is not None:
        return hit
    path = Path(__file__).resolve().parents[1] / 'private-inputs' / 'editor-cache' / 'ez' / (key + '.ez')
    try:
        hit = path.read_bytes()
        if hit[:6] == bytes(header):
            _EZ_MEMO[key] = hit
            return hit
    except OSError:
        pass
    hit = _pack_ez(raw, header)
    _EZ_MEMO[key] = hit
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp'); tmp.write_bytes(hit); tmp.replace(path)
    except OSError:
        pass
    return hit


def _pack_ez(raw, header=b"EZ\0\0\0\0"):
    if len(header)!=6 or header[:2]!=b"EZ":raise ValueError("Invalid EZ header")
    out=bytearray(header);positions=defaultdict(deque);i=0
    while i<len(raw):
        # Retail uploads one 64x256 16-bit VRAM rectangle per 32KiB
        # decode. Its decoder finishes a complete match before returning,
        # and the upload discards any bytes beyond that rectangle. It then
        # resets the output pointer to the same buffer for the next page.
        # Thus neither a match nor its source may cross a page boundary.
        if i%32768==0:positions.clear()
        maximum=min(255,len(raw)-i,32768-i%32768)
        key=raw[i:i+3];candidates=positions[key]
        while candidates and i-candidates[0]>255:candidates.popleft()
        length=0;distance=0
        for previous in reversed(candidates):
            if maximum<3:break
            n=3
            while n<maximum and raw[previous+n]==raw[i+n]:n+=1
            if n>length:length=n;distance=i-previous
            if length==maximum:break
        if length>=4:
            out.extend((173,distance,length));step=length
        else:
            out.append(raw[i])
            if raw[i]==173:out.append(0)
            step=1
        for j in range(i,i+step):
            if j+3<=len(raw):positions[raw[j:j+3]].append(j)
        i+=step
    out.extend((173,255,0))
    return bytes(out)


def pack_ez_compact(raw, header=b"EZ\0\0\0\0", max_candidates=48):
    """Smaller EZ stream (optimal parse over the same matches) for tight texture room.

    Same stream rules as pack_ez: distance/length <= 255, nothing crosses a
    32 KiB page, literal 0xAD escaped. About 0.5-1 KB smaller per map, ~2 s."""
    if len(header)!=6 or header[:2]!=b"EZ":raise ValueError("Invalid EZ header")
    out=bytearray(header)
    for page in range(0,len(raw),32768):
        seg=raw[page:page+32768];n=len(seg)
        # longest match (length, distance) at each position, within this page
        best_len=[0]*n;best_dist=[0]*n
        heads={}
        for i in range(n-2):
            key=seg[i:i+3];lst=heads.get(key)
            if lst:
                maximum=min(255,n-i);bl=0;bd=0
                k=len(lst)-1;checked=0
                while k>=0 and checked<max_candidates:
                    p=lst[k];d=i-p
                    if d>255:break
                    checked+=1
                    if seg[p+bl:p+bl+1]==seg[i+bl:i+bl+1] or bl==0:
                        l=3
                        # extend quickly
                        while l<maximum and seg[p+l]==seg[i+l]:l+=1
                        if l>bl:bl=l;bd=d
                        if bl==maximum:break
                    k-=1
                if bl>=4:best_len[i]=bl;best_dist[i]=bd
                # trim list
                if len(lst)>400:del lst[:200]  # keep recent candidates only
                lst.append(i)
            else:heads[key]=[i]
        # DP backwards with range-min over cost[i+4..i+L]
        INF=1<<30
        cost=[0]*(n+1);choice=[0]*n
        # segment tree for min over cost with index
        size=1
        while size<n+1:size*=2
        tree=[INF]*(2*size)
        def update(pos,val):
            pos+=size;tree[pos]=val;pos//=2
            while pos:
                a=tree[2*pos];b=tree[2*pos+1];tree[pos]=a if a<b else b;pos//=2
        def query(lo,hi):  # inclusive
            res=INF;lo+=size;hi+=size+1
            while lo<hi:
                if lo&1:
                    if tree[lo]<res:res=tree[lo]
                    lo+=1
                if hi&1:
                    hi-=1
                    if tree[hi]<res:res=tree[hi]
                lo//=2;hi//=2
            return res
        update(n,0)
        for i in range(n-1,-1,-1):
            lit=(2 if seg[i]==173 else 1)+cost[i+1];c=lit;ch=0
            L=best_len[i]
            if L>=4:
                m=query(i+4,i+L)+3
                if m<c:c=m;ch=-1
            cost[i]=c;choice[i]=ch;update(i,c)
        # reconstruct: need actual length achieving the min
        i=0
        while i<n:
            if choice[i]==-1:
                L=best_len[i];target=cost[i]-3
                l=next(l for l in range(L,3,-1) if cost[i+l]==target)
                out.extend((173,best_dist[i],l));i+=l
            else:
                out.append(seg[i])
                if seg[i]==173:out.append(0)
                i+=1
    out.extend((173,255,0))
    return bytes(out)


def pack_ez_fit(raw, header, room):
    """Greedy pack; if it does not fit in room bytes, the compact packer."""
    packed=pack_ez(raw,header)
    if len(packed)>room:
        compact=pack_ez_compact(raw,header)
        if len(compact)<len(packed):packed=compact
    return packed
