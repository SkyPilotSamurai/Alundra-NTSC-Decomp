"""Native music selection; source tables are located by structural signatures."""
import struct

MUSIC_SIGNATURE = struct.pack('<4I',0x581800,0x594800,0x595800,0x5A4800)
MAP_SIGNATURE = struct.pack('<16I',0,17,*([7]*14))
TRACK_COUNT = 47

def map_table_offset(exe):
    """Follow the native default lookup's LUI/LW rather than editable table bytes."""
    if exe[:8]!=b'PS-X EXE' or len(exe)<2048:raise ValueError('Music needs a PS-X executable')
    load,size=struct.unpack_from('<2I',exe,0x18);found=[]
    if size>len(exe)-2048:raise ValueError('Executable payload is truncated')
    for offset in range(2048,2048+size-23,4):
        a,b,c,d,e,f=struct.unpack_from('<6I',exe,offset)
        if a!=0x00041080 or b&0xFFFF0000!=0x3C010000 or c!=0x00220821 or d&0xFFFF0000!=0x8C220000 or (e,f)!=(0x03E00008,0):continue
        low=d&65535;low=low-65536 if low>=32768 else low
        address=((b&65535)<<16)+low;table=2048+address-load
        if 2048<=table<=2048+size-483*4:
            values=struct.unpack_from('<483i',exe,table)
            if all(-1<=v<TRACK_COUNT for v in values):found.append(table)
    if len(found)!=1:raise ValueError('Native map music lookup is not uniquely recognized in this game')
    return found[0]

def unique_table(exe,signature,length):
    if exe[:8] != b'PS-X EXE':raise ValueError('Music needs the selected game executable')
    offset=exe.find(signature,2048)
    if offset<0 or exe.find(signature,offset+1)>=0 or offset+length>len(exe):
        raise ValueError('Native music table is not uniquely recognized in this game')
    return offset

def encode_music(music_id):
    if type(music_id) is not int or not 0<=music_id<TRACK_COUNT:
        raise ValueError('Music ID must be0..46')
    # A7 (track, play): loads the track and, with play = 1, starts it (game scripts
    # use both; with 0 the track is only loaded and stays silent until A5).
    return bytes((0xA7,music_id,1))

def music_rows(exe,sound=None):
    offset=unique_table(exe,MUSIC_SIGNATURE,(TRACK_COUNT*3+1)*4)
    values=struct.unpack_from('<'+str(TRACK_COUNT*3+1)+'I',exe,offset)
    rows=[]
    for i in range(TRACK_COUNT):
        seq,header,body,end=values[i*3:i*3+4]
        if not seq<header<body<end:raise ValueError('Music bank boundaries are invalid')
        if sound is not None and (end>len(sound) or (i!=0 and sound[seq:seq+4]!=b'pQES') or sound[header:header+4]!=b'pBAV'):
            raise ValueError('Selected music bank does not match its executable')
        rows.append(dict(id=i,sequence_offset=seq,header_offset=header,body_offset=body,end_offset=end))
    return rows

def map_music_values(exe):
    return struct.unpack_from('<483i',exe,map_table_offset(exe))

def map_music(exe,map_id):
    if type(map_id) is not int or not 0<=map_id<483:raise ValueError('Map ID must be0..482')
    offset=map_table_offset(exe)
    value=struct.unpack_from('<i',exe,offset+map_id*4)[0]
    if not -1<=value<TRACK_COUNT:raise ValueError('Map music value is not recognized')
    return value

def patch_map_music(exe,selections):
    if not isinstance(selections,dict):raise ValueError('Map music selections must be an object')
    data=bytearray(exe);offset=map_table_offset(exe);report=[]
    values=struct.unpack_from('<483i',exe,offset)
    for key,value in selections.items():
        try:map_id=int(key)
        except (ValueError,TypeError):raise ValueError('Map music key must be a map ID')
        encode_music(value)
        if not 0<=map_id<483:raise ValueError('Map ID must be0..482')
        before=values[map_id]
        struct.pack_into('<i',data,offset+map_id*4,value)
        report.append(dict(map_id=map_id,before=before,after=value,file_offset=offset+map_id*4))
    return bytes(data),report
