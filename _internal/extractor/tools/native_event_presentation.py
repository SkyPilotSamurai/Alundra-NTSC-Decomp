"""Presentation of native commands without rewriting their control flow.

Names are source labels, not new discoveries of game flags or item behavior.
Only event_editor.EDITABLE operands can be changed; all other bytes stay opaque.
"""
import csv
import struct
from functools import lru_cache
from pathlib import Path
from event_editor import EDITABLE, SIZES
from map_names import map_label, NAMES
from database_catalogue import item_names
from map_text import dialogue_reference, dialogue_entry

ROOT=Path(__file__).resolve().parents[1]
BRANCHES=(2,3,4,0x30,0x31,0x74,0x78)
FLAG_OPS=(5,6,0x30,0x31,0x36)

@lru_cache(maxsize=1)
def flag_choices():
    with (ROOT/'data/event-flags.csv').open(encoding='utf-8-sig',newline='') as stream:
        return {f"{row['event_code']} · {row['name']} (reported)":int(row['event_code'],16)
                for row in csv.DictReader(stream)}

@lru_cache(maxsize=128)
def operand_choices(op,index):
    if op in FLAG_OPS and index==0:return flag_choices()
    if op==0x53 and index==0:return {map_label(i):i for i in range(483)}
    if op==0x83 and index==0:return {f"{i} · {row['name']}":i for i,row in enumerate(item_names())}
    return {}

def parse_operand(value,choices=None):
    if choices and value in choices:return choices[value]
    try:return int(value,0)
    except ValueError:raise ValueError('Choose a named value or enter a native numeric operand')

def group_for(op):
    from native_event_knowledge import KNOWLEDGE
    if op in KNOWLEDGE: return KNOWLEDGE[op][0]
    if op in (0x0D,0x5C):return 'Message'
    if op in FLAG_OPS or op in (0x73,0x83,0x98,0x99,0x9A):return 'Game progression'
    if op in BRANCHES or op in (0,0x37,0x6A,0x6B,0x6C,0x6D,0x7D,255):return 'Flow control'
    if op in (0x10,0x11,0x19,0x1A,0x27,0x2C,0x42,0x5A,0x62,0x63,0x8A,0x8B):return 'Characters / objects'
    if op==0x39:return 'Message'
    if op in (0x67,0x68,0x69):return 'Camera'
    if op in (0x53,0x9B,0x9C):return 'Map'
    if op==0x75:return 'Audio'
    return 'Misc / Unknown'

READ_ONLY={0:'Yield until next scheduler step',1:'Do nothing',
           0x10:'Lock player movement',0x11:'Unlock player movement',
           0x19:'Deactivate this character',0x27:'Face the player',
           0x39:'Wait for dialogue',0x42:'Use player as logic context',
           0x6A:'Remember current XYZ position',
           0x7D:'Return from local process',255:'End process',
           0x2C:'Check map template absent',0x8B:'Spawn relative to selected character (source-reported)'}

def present(session,map_id,offset,op,size,lines):
    raw=bytes(session.data[offset:offset+size]);group=group_for(op)
    if SIZES.get(op)!=size:
        return dict(group='Misc / Unknown',action=f'Unknown event {op:02X} (truncated command)',
                    settings=f'{len(raw)} preserved bytes: '+raw[:32].hex(' '),editable=False)
    reference=dialogue_reference(session.data,offset)
    if reference:
        row=dialogue_entry(session,map_id,offset)
        text=row[2].decode('latin-1') if row else 'Unresolved text reference'
        speaker=f'Speaker selector {raw[1]} · ' if op==0x5C else ''
        return dict(group=group,action='Show text',settings=speaker+text,
                    editable=row is not None)
    if op in EDITABLE:
        name,fmt,labels=EDITABLE[op];values=struct.unpack_from('<'+fmt,raw,1)
        settings=[]
        for i,(label,value) in enumerate(zip(labels,values)):
            if op in BRANCHES and i==len(values)-1:
                settings.append(f'→ Line {lines[offset+value]}' if offset+value in lines else f'→ Outside listing (relative {value:+d})')
                continue
            choices=operand_choices(op,i)
            displayed=next((k for k,v in choices.items() if v==value),str(value))
            if op in FLAG_OPS and i==0:
                from native_flag_index import flag_label,flag_uses
                flag_uses(session)   # once per game data: lets unnamed flags say who sets them
                displayed=flag_label(value,map_id)
            settings.append(f'{label}: {displayed}')
        return dict(group=group,action=name,settings='; '.join(settings),editable=True)
    # Source-reported handlers at pinned xcasadio commit242b09a. Preserve
    # selectors/masks numerically where their specific meaning is unresolved.
    descriptions={
        0x5A:('Face direction','BB',('Character selector','Direction operand')),
        0x62:('Set character flags','BH',('Character selector','Flag mask (meaning unknown)')),
        0x63:('Clear character flags','BH',('Character selector','Flag mask (meaning unknown)')),
        0x67:('Camera follows character','B',('Character selector',)),
        0x68:('Stop camera following','',()),
        0x69:('Set camera position','3H',('World X','World Y','World Z')),
    }
    if op in descriptions and op not in (0x5A,0x62,0x63,0x67,0x68,0x69):
        name,fmt,labels=descriptions[op]
        if len(raw)==1+struct.calcsize('<'+fmt):
            values=struct.unpack_from('<'+fmt,raw,1)
            settings='; '.join(f'{label}: {value}' for label,value in zip(labels,values))
            return dict(group=group,action=name,settings=settings or 'No operands',editable=False,
                        interpretation='source-reported')
    from native_event_knowledge import describe
    def _item(v):
        try:return item_names()[v]['name']
        except Exception:return None
    known=describe(op,raw,_item,map_label,lambda o:lines.get(o),offset)
    if known:
        g,name,settings,_=known
        return dict(group=g,action=name,settings=settings,editable=False,interpretation='decoded from the game interpreter')
    name=READ_ONLY.get(op,f'Unknown event {op:02X}')
    return dict(group=group,action=name,settings=raw[1:].hex(' '),editable=False)

def help_for(op):
    from native_event_knowledge import KNOWLEDGE
    known=KNOWLEDGE.get(op,(None,None,None,''))[3]
    return {0x37:'Wait counts native scheduler steps; exact video-frame timing is not established.',
            0x8A:'Spawns an existing map-local template, not a database type. XYZ are world coordinates, not tiles.',
            0x1A:'Changes the actor animation; this does not select an arbitrary frame.',
            0x73:'One scratch repeat counter is shared by this process; nested loops can overwrite it.',
            0x74:'Decrements the scratch repeat counter and jumps while it remains positive.',
            0x78:'Uses one scratch return address. Nested calls can overwrite it.',
            0x6A:'Saves the current actor position as a reference point. By itself this does not move the actor.',
            0x6B:'Checks X distance from that saved position and sets a condition for the next branch. It tests route progress; it does not issue movement.',
            0x6C:'Checks Y distance from that saved position and sets a condition for the next branch. It tests route progress; it does not issue movement.',
            0x6D:'Checks Z distance from that saved position and sets a condition for the next branch. It tests route progress; it does not issue movement.',
            0x8B:'Source-reported spawn relative to a selected character. The exact selector and spawned template behavior need US-specific confirmation.'}.get(op,known or 'Edits preserve native operand widths and instruction size. Existing game switches affect original progression.')
