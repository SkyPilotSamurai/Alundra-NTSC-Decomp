"""Game flags (switches) across every map: what each flag is called and which
events set, clear or check it, so the event editor can name a flag and jump to
the events that use it."""
import csv
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAG_OPS = {0x05: 'sets', 0x06: 'clears', 0x32: 'toggles', 0x30: 'jumps if set', 0x31: 'jumps if clear',
            0x35: 'waits until clear', 0x36: 'waits until set', 0x7B: 'calls if set', 0x7C: 'calls if clear',
            0x80: 'returns if set', 0x81: 'returns if clear', 0x33: 'checks (all set)', 0x34: 'checks (all clear)'}
_cache = {}
_document = {}


def set_document(document):
    """The open mod's database document (user flag names live in document['flag_names'])."""
    _document['doc'] = document


def reported_names():
    if 'csv' not in _cache:
        out = {}
        try:
            with (ROOT / 'data/event-flags.csv').open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    if row.get('event_code'): out[int(row['event_code'], 16)] = row['name']
        except OSError:
            pass
        _cache['csv'] = out
    return _cache['csv']


def flag_name(flag):
    doc = _document.get('doc') or {}
    name = (doc.get('flag_names') or {}).get(f'{flag:04X}')
    return name or reported_names().get(flag)


def set_flag_name(document, flag, name):
    names = document.setdefault('flag_names', {})
    if name and name.strip(): names[f'{flag:04X}'] = name.strip()
    else: names.pop(f'{flag:04X}', None)


def auto_name(flag, map_id=None):
    """No name yet: say who sets it (temporary flags: on this map only)."""
    uses = (_cache.get('uses') or (None, {}))[1].get(flag, [])
    if flag & 0x8000 and map_id is not None:
        uses = [u for u in uses if u['map'] == map_id]
    if not uses: return None
    setters = [u for u in uses if u['op'] in (0x05, 0x32)]
    first = (setters or uses)[0]
    who = f"{'Actor' if first['kind'] == 'entities' else 'Event'} {first['index']}"
    where = '' if (flag & 0x8000 or first['map'] == map_id) else f" (map {first['map']})"
    others = len({(u['map'], u['kind'], u['index']) for u in uses}) - 1
    return (f"set by {who}{where}" if setters else f"used by {who}{where}") + (f", +{others} more" if others > 0 else '')


def flag_label(flag, map_id=None):
    name = flag_name(flag) or auto_name(flag, map_id)
    kind = 'temporary ' if flag & 0x8000 else ''
    return f'{kind}flag {flag:#06x}' + (f' · {name}' if name else '')


def _flags_in(data, offset, op):
    if op in (0x33, 0x34):
        return [struct.unpack_from('<H', data, offset + 1 + 2 * i)[0] for i in range(4)]
    return [struct.unpack_from('<H', data, offset + 1)[0]]


def flag_uses(session, maps=None, progress=None):
    """{flag: [{map, kind, index, bank, key, offset, line, op, verb}]} for every map."""
    from map_inspector import inspect_map
    from native_event_view import event_hooks
    from event_editor import reachable_instructions as instructions
    from map_slots import map_exists
    import hashlib
    if getattr(session, 'data_frozen', False):        # read-only export runs: hash the 100 MB once
        digest = _cache.get('frozen_digest')
        if digest is None or _cache.get('frozen_id') != id(session.data):
            digest = hashlib.sha256(memoryview(session.data)).hexdigest()
            _cache['frozen_digest'] = digest; _cache['frozen_id'] = id(session.data)
    else:
        digest = hashlib.sha256(memoryview(session.data)).hexdigest()
    if maps is None and _cache.get('uses', (None,))[0] == digest:
        return _cache['uses'][1]
    out = {}
    todo = maps if maps is not None else [m for m in range(2547) if (m < 483 or map_exists(session.data, m))]
    for n, m in enumerate(todo):
        if progress and n % 25 == 0: progress(n, len(todo))
        try: info = inspect_map(session.data, m)
        except Exception: continue
        seen = set()
        for kind in ('entities', 'events'):
            for index in range(len(info[kind])):
                try: hooks = event_hooks(session, m, kind, index, info)
                except Exception: continue
                for hook in hooks:
                    key = hook['key']
                    if key is None or (key, kind, index) in seen: continue
                    seen.add((key, kind, index))
                    try: rows = instructions(session, m, key)
                    except Exception: continue
                    for line, (offset, op, size) in enumerate(rows, 1):
                        if op not in FLAG_OPS: continue
                        for flag in _flags_in(session.data, offset, op):
                            out.setdefault(flag, []).append(dict(map=m, kind=kind, index=index, bank=hook['bank'], key=key,
                                                                 offset=offset, line=line, op=op, verb=FLAG_OPS[op]))
    if maps is None: _cache['uses'] = (digest, out)
    return out


def open_native_event(editor, map_id, kind, index, key=None, offset=None):
    """Show an existing game event (switching map first), with the command selected."""
    if editor.current_map != map_id:
        editor.map_id.set(str(map_id)); editor.load_map()
    from native_event_graph_ui import NativeEventGraphWindow
    view = NativeEventGraphWindow(editor, kind, index)
    if key is not None:
        page = next((p for p in view.working['pages'] if p.get('native_key') == key), None)
        if page is not None:
            view.page_id = page['id']
            try:
                view.page.set(next(name for name, pid in view.page_names.items() if pid == page['id']))
            except Exception:
                pass
            view.load_page()
            if offset is not None and view.commands.exists(str(offset)):
                view.commands.selection_set(str(offset)); view.commands.see(str(offset))
    return view


def show_uses(editor, parent, flag):
    """A small list of every event that uses the flag; double-click to go there."""
    import tkinter as tk
    from tkinter import ttk
    from map_names import map_label
    win = tk.Toplevel(parent); win.title(flag_label(flag)); win.transient(parent)
    tree = ttk.Treeview(win, columns=('map', 'event', 'what'), show='headings', height=14)
    for col, text, width in (('map', 'Map', 260), ('event', 'Event', 200), ('what', 'Line', 220)):
        tree.heading(col, text=text); tree.column(col, width=width, anchor='w')
    tree.pack(fill='both', expand=True, padx=8, pady=8)
    editor.status.set('Finding every event that uses this flag…'); win.update_idletasks()
    uses = flag_uses(editor.session).get(flag, [])
    rows = {}
    for i, u in enumerate(uses):
        who = f"{'Actor' if u['kind'] == 'entities' else 'Event'} {u['index']} ({u['bank']})"
        tree.insert('', 'end', iid=str(i), values=(map_label(u['map']), who, f"line {u['line']}: {u['verb']}"))
        rows[str(i)] = u
    if not uses: tree.insert('', 'end', values=('No event uses this flag', '', ''))
    editor.status.set(f'{len(uses)} use(s) of {flag_label(flag)}.')

    def go(_=None):
        sel = tree.selection()
        if sel and sel[0] in rows:
            u = rows[sel[0]]; editor.guard(lambda: open_native_event(editor, u['map'], u['kind'], u['index'], u['key'], u['offset']))
    tree.bind('<Double-Button-1>', go)
    ttk.Button(win, text='Go to event', command=go).pack(side='right', padx=8, pady=(0, 8))
    return win
