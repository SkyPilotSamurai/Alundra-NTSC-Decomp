"""Named private session state; never allocates stock game flags/save bytes."""
from copy import deepcopy

MAX_PER_KIND = 128
LIFETIME = 'Main executable session; resets when ALUN_CD.EXE reloads; not memory-card saved'


def _value(kind, value):
    if kind == 'switches':
        if type(value) is not bool: raise ValueError('Project switch initial value must be ON/OFF')
    elif kind == 'variables':
        if type(value) is not int or not -2147483648 <= value <= 2147483647:
            raise ValueError('Project variable value must be signed32')
    else: raise ValueError('Project state kind must be switches or variables')
    return value


def _name(name):
    if not isinstance(name,str) or not name.strip(): raise ValueError('Project state needs a name')
    return name.strip()


class ProjectStateRegistry:
    def __init__(self, document):
        if not isinstance(document,dict):raise ValueError('Content database must be an object')
        self.document=document
        state=document.setdefault('project_state',{'format':'alundra-project-state-v1',
            'switches':[],'variables':[],'next_switch_id':1,'next_variable_id':1})
        if state.get('format')!='alundra-project-state-v1':raise ValueError('Unsupported project state registry')
        self.state=state
        for kind in ('switches','variables'):
            entries=state.setdefault(kind,[])
            if not isinstance(entries,list):raise ValueError('Project state entries must be a list')
            seen=set()
            for entry in entries:
                identity=entry.get('id')
                if type(identity) is not int or not 1 <= identity <= 65535 or identity in seen:
                    raise ValueError('Project state IDs must be distinct1..65535')
                seen.add(identity);_name(entry.get('name'));_value(kind,entry.get('initial_value'))
                if type(entry.get('deleted',False)) is not bool:raise ValueError('Deleted state must be ON/OFF')
            key='next_switch_id' if kind=='switches' else 'next_variable_id'
            next_id=state.get(key,max(seen,default=0)+1)
            if type(next_id) is not int or not max(seen,default=0)<next_id<=65536:
                raise ValueError('Next project state ID must exceed all historical IDs')
            state[key]=next_id
            if len([row for row in entries if not row.get('deleted',False)])>MAX_PER_KIND:
                raise ValueError('Private session state currently supports128 entries per kind')

    def options(self,kind):
        _value(kind,False if kind=='switches' else 0)
        return [deepcopy(row) for row in sorted(self.state[kind],key=lambda row:row['id']) if not row.get('deleted',False)]

    def get(self,kind,identity):
        for row in self.options(kind):
            if type(identity) is int and row['id']==identity:return row
        raise ValueError('Project state definition is missing or deleted')

    def create(self,kind,name,initial_value=None):
        if initial_value is None:initial_value=False if kind=='switches' else 0
        name=_name(name);_value(kind,initial_value)
        if len(self.options(kind))>=MAX_PER_KIND:raise ValueError('Private state entry capacity reached')
        key='next_switch_id' if kind=='switches' else 'next_variable_id'
        identity=self.state[key]
        if identity>65535:raise ValueError('Project state ID space exhausted; IDs are never reused')
        row={'id':identity,'name':name,'initial_value':initial_value,'deleted':False}
        self.state[kind].append(row);self.state[key]+=1
        return deepcopy(row)

    def create_auto(self,kind):
        """Allocate named project state immediately, without using stock flags."""
        _value(kind,False if kind=='switches' else 0)
        key='next_switch_id' if kind=='switches' else 'next_variable_id'
        number=self.state[key];prefix='Switch' if kind=='switches' else 'Variable'
        names={row['name'] for row in self.options(kind)}
        while f'{prefix}{number}' in names:number+=1
        return self.create(kind,f'{prefix}{number}')

    def update(self,kind,identity,*,name=None,initial_value=None):
        old=self.get(kind,identity)
        if name is not None:old['name']=_name(name)
        if initial_value is not None:old['initial_value']=_value(kind,initial_value)
        for row in self.state[kind]:
            if row['id']==identity:row.update(old);return deepcopy(row)

    def references(self,kind,identity):
        scope='switch_scope' if kind=='switches' else 'variable_scope'
        key='switch_id' if kind=='switches' else 'variable_id'
        result=[]
        def walk(value,path):
            if isinstance(value,dict):
                if value.get(scope)=='project' and value.get(key)==identity:result.append(path)
                if kind=='switches' and path.endswith('/native_placement') and value.get('open_switch_id')==identity:result.append(path+'/open_switch_id')
                for k,v in value.items():walk(v,path+'/'+str(k))
            elif isinstance(value,list):
                for i,v in enumerate(value):walk(v,path+'/'+str(i))
        walk(self.document.get('event_graphs',[]),'event_graphs')
        return result

    def delete(self,kind,identity):
        self.get(kind,identity)
        if self.references(kind,identity):raise ValueError('Project state is referenced by events; remove those references before deleting')
        for row in self.state[kind]:
            if row['id']==identity:row['deleted']=True

    def resolve(self,kind,command):
        scope='switch_scope' if kind=='switches' else 'variable_scope'
        key='switch_id' if kind=='switches' else 'variable_id'
        if command.get(scope)!='project':raise ValueError('Select explicit project state scope')
        return self.get(kind,command.get(key))

    def validate_references(self):
        def walk(value,path='event_graphs'):
            if isinstance(value,dict):
                for kind,scope in (('switches','switch_scope'),('variables','variable_scope')):
                    if value.get(scope)=='project':self.resolve(kind,value)
                if path.endswith('/native_placement') and 'open_switch_id' in value:self.get('switches',value['open_switch_id'])
                for key,child in value.items():walk(child,path+'/'+str(key))
            elif isinstance(value,list):
                for i,child in enumerate(value):walk(child,path+'/'+str(i))
        walk(self.document.get('event_graphs',[]))

    def export(self):return deepcopy(self.state)
