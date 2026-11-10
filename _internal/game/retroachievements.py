"""RETROACHIEVEMENTS (Options > RetroAchievements, off by default): the official Alundra (PlayStation) set, run by
rcheevos (rcheevos.dll, RetroAchievements' own library, MIT: LICENSE-rcheevos.txt) over the port's RAM laid out as
the console's (PS1 map: 0x000000-0x1FFFFF main RAM, 0x200000-0x2003FF scratchpad).  Softcore only, and only in the
base game: no randomizer seed, Archipelago, Crowd Control or speedrun states.
The disc is identified by the hash RetroAchievements uses (extract_assets.py: assets/boot/ra_hash.txt).
Login: the player's own name and password, sent once to retroachievements.org; only the returned token is kept
(settings.json ra_user / ra_token).  Unlocks and the other messages are drawn in the game's font on its parchment."""
import ctypes as C
import queue
import struct
import threading
import pygame
from home import HOME, ASSETS, CODE

DLL = CODE / 'rcheevos.dll'
HASH_FILE = ASSETS / 'boot' / 'ra_hash.txt'
LOG = HOME / '_internal' / 'retroachievements.log'
UA = 'AlundraPC/1.0'
RAM_SIZE = 0x200400
POPUP_FRAMES = 300                     # a message stays this many drawn frames (5 s)

# ---------------------------------------------------------------- rcheevos types
class _Request(C.Structure):
    _fields_ = [('url', C.c_char_p), ('post_data', C.c_char_p), ('content_type', C.c_char_p)]


class _Response(C.Structure):
    _fields_ = [('body', C.c_void_p), ('body_length', C.c_size_t), ('http_status_code', C.c_int)]


class _Achievement(C.Structure):
    _fields_ = [('title', C.c_char_p), ('description', C.c_char_p), ('badge_name', C.c_char * 8),
                ('measured_progress', C.c_char * 24), ('measured_percent', C.c_float), ('id', C.c_uint32),
                ('points', C.c_uint32), ('unlock_time', C.c_int64), ('state', C.c_uint8), ('category', C.c_uint8),
                ('bucket', C.c_uint8), ('unlocked', C.c_uint8), ('rarity', C.c_float), ('rarity_hardcore', C.c_float),
                ('type', C.c_uint8), ('badge_url', C.c_char_p), ('badge_locked_url', C.c_char_p)]


class _ServerError(C.Structure):
    _fields_ = [('error_message', C.c_char_p), ('api', C.c_char_p), ('result', C.c_int), ('related_id', C.c_uint32)]


class _Event(C.Structure):
    _fields_ = [('type', C.c_uint32), ('achievement', C.POINTER(_Achievement)), ('leaderboard', C.c_void_p),
                ('leaderboard_tracker', C.c_void_p), ('leaderboard_scoreboard', C.c_void_p),
                ('server_error', C.POINTER(_ServerError)), ('subset', C.c_void_p)]


class _User(C.Structure):
    _fields_ = [('display_name', C.c_char_p), ('username', C.c_char_p), ('token', C.c_char_p), ('score', C.c_uint32),
                ('score_softcore', C.c_uint32), ('num_unread_messages', C.c_uint32), ('avatar_url', C.c_char_p),
                ('avatar_last_updated', C.c_int64)]


class _Game(C.Structure):
    _fields_ = [('id', C.c_uint32), ('console_id', C.c_uint32), ('title', C.c_char_p), ('hash', C.c_char_p),
                ('badge_name', C.c_char_p), ('badge_url', C.c_char_p)]


class _Bucket(C.Structure):
    _fields_ = [('achievements', C.POINTER(C.POINTER(_Achievement))), ('num_achievements', C.c_uint32),
                ('label', C.c_char_p), ('subset_id', C.c_uint32), ('bucket_type', C.c_uint8)]


class _List(C.Structure):
    _fields_ = [('buckets', C.POINTER(_Bucket)), ('num_buckets', C.c_uint32)]


class _Summary(C.Structure):
    _fields_ = [('num_core', C.c_uint32), ('num_unofficial', C.c_uint32), ('num_unlocked', C.c_uint32),
                ('num_unsupported', C.c_uint32), ('points_core', C.c_uint32), ('points_unlocked', C.c_uint32),
                ('beaten_time', C.c_int64), ('completed_time', C.c_int64)]


_SERVER_CB = C.CFUNCTYPE(None, C.POINTER(_Response), C.c_void_p)
_SERVER_CALL = C.CFUNCTYPE(None, C.POINTER(_Request), C.c_void_p, C.c_void_p, C.c_void_p)
_CALLBACK = C.CFUNCTYPE(None, C.c_int, C.c_char_p, C.c_void_p, C.c_void_p)
_EVENT = C.CFUNCTYPE(None, C.POINTER(_Event), C.c_void_p)
_LOGFN = C.CFUNCTYPE(None, C.c_char_p, C.c_void_p)

EV_TRIGGERED, EV_COMPLETED, EV_SERVER_ERROR, EV_DISCONNECTED, EV_RECONNECTED = 1, 15, 16, 17, 18
RC_INVALID_CREDENTIALS, RC_EXPIRED_TOKEN = -34, -35


def _s(b):
    return b.decode('utf-8', 'replace') if b else ''


def base_game():
    """Achievements run only in the base game (user, 2026-11-08: not in speedrun, randomizer, Archipelago...)."""
    import seedgen, speedrun
    return (seedgen.active is None and seedgen.bridge is None and getattr(seedgen, 'cc', None) is None
            and not speedrun.active())


def disc_hash():
    try: h = HASH_FILE.read_text().strip().lower()
    except OSError: return None
    return h if len(h) == 32 else None


# ---------------------------------------------------------------- the RAM the set reads
class RamView:
    """g.mem with what the port keeps on objects put back at the console's addresses: the named globals
    (engine/layout.py GLOBALS), the 64 entity records, Alundra's position words 0x801D7B40 / 0x801D7B90 (as
    apbridge.py) and the VSync count (as ccbridge.py)."""

    def __init__(self):
        from engine import layout as L
        self.L = L
        self.buf = bytearray(RAM_SIZE)
        self.ptr = (C.c_uint8 * RAM_SIZE).from_buffer(self.buf)
        ent = sorted((o, n, t) for n, (o, t) in L.ENTITY.items())
        fmt, at, self.ent_names = '<', 0, []
        for o, n, t in ent:
            if o < at: continue
            if o > at: fmt += f'{o - at}x'
            fmt += 'I'; at = o + 4; self.ent_names.append((n, t))
        self.ent_struct = struct.Struct(fmt)
        self.bytes_off, self.bytes_n = L.ENTITY_BYTES['bytes']
        self.ai_off, self.ai_n = L.ENTITY_SHORTS['ai']
        self.glob = [(n, a & 0x1FFFFF, t) for n, (a, t) in L.GLOBALS.items()]
        self.ent0 = L.ENT_BASE & 0x1FFFFF

    def ent_addr(self, a):
        s = getattr(a, 'slot', None)
        return self.L.ENT_BASE + self.L.ENT_SIZE * s if isinstance(s, int) else 0

    def value(self, v, t):
        if v is None or v is False: return 0
        if t == 'ptr': return self.ent_addr(v) if not isinstance(v, int) else v
        if t == 'fxptr': return v if isinstance(v, int) else 0
        try: return int(v) & 0xFFFFFFFF
        except (TypeError, ValueError): return 0

    def fill(self, g):
        b = self.buf; b[:0x200000] = g.mem.b[:0x200000]
        val = self.value
        for i, a in enumerate(getattr(g, 'slots', ())[:64]):
            base = self.ent0 + self.L.ENT_SIZE * i
            if a is None:
                b[base + 0x10:base + 0x14] = b'\0\0\0\0'            # estatus 0: a free slot
                continue
            self.ent_struct.pack_into(b, base, *[val(getattr(a, n, 0), t) for n, t in self.ent_names])
            x = getattr(a, 'bytes', None)
            if x is not None:
                for k in range(min(self.bytes_n, len(x))): b[base + self.bytes_off + k] = int(x[k]) & 0xFF
            x = getattr(a, 'ai', None)
            if x is not None:
                for k in range(min(self.ai_n, len(x))): struct.pack_into('<H', b, base + self.ai_off + 2 * k, int(x[k]) & 0xFFFF)
        for n, a, t in self.glob:
            v = val(getattr(g, n, 0), t)
            if t in ('u8', 'i8'): b[a] = v & 0xFF
            elif t in ('u16', 'i16'): struct.pack_into('<H', b, a, v & 0xFFFF)
            else: struct.pack_into('<I', b, a, v)
        p = getattr(g, 'player', None)
        if p is not None:
            struct.pack_into('<H', b, 0x1D7B40, (getattr(p, 'px', 0) >> 16) & 0xFFFF)
            struct.pack_into('<H', b, 0x1D7B90, (getattr(p, 'py', 0) >> 16) & 0xFFFF)
        struct.pack_into('<I', b, 0x0CB54C, type(g).VBLANKS & 0xFFFFFFFF)


# ---------------------------------------------------------------- the client
class Client:
    def __init__(self, server=None):
        """server(url, post, content_type) -> (status, body bytes): the tests' own; None: retroachievements.org."""
        self.dll = C.CDLL(str(DLL))
        d = self.dll
        d.alundra_ra_create.restype = C.c_void_p; d.alundra_ra_create.argtypes = [_SERVER_CALL]
        d.alundra_ra_set_ram.argtypes = [C.c_void_p, C.c_uint32]
        for n in ('rc_client_do_frame', 'rc_client_idle', 'rc_client_logout', 'rc_client_unload_game', 'rc_client_reset', 'rc_client_destroy'):
            getattr(d, n).argtypes = [C.c_void_p]; getattr(d, n).restype = None
        d.rc_client_set_hardcore_enabled.argtypes = [C.c_void_p, C.c_int]
        d.rc_client_set_event_handler.argtypes = [C.c_void_p, _EVENT]
        d.rc_client_enable_logging.argtypes = [C.c_void_p, C.c_int, _LOGFN]
        for n in ('rc_client_begin_login_with_password', 'rc_client_begin_login_with_token'):
            getattr(d, n).argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, _CALLBACK, C.c_void_p]; getattr(d, n).restype = C.c_void_p
        d.rc_client_begin_load_game.argtypes = [C.c_void_p, C.c_char_p, _CALLBACK, C.c_void_p]; d.rc_client_begin_load_game.restype = C.c_void_p
        d.rc_client_get_user_info.argtypes = [C.c_void_p]; d.rc_client_get_user_info.restype = C.POINTER(_User)
        d.rc_client_get_game_info.argtypes = [C.c_void_p]; d.rc_client_get_game_info.restype = C.POINTER(_Game)
        d.rc_client_is_game_loaded.argtypes = [C.c_void_p]
        d.rc_client_get_user_game_summary.argtypes = [C.c_void_p, C.POINTER(_Summary)]
        d.rc_client_get_user_agent_clause.argtypes = [C.c_void_p, C.c_char_p, C.c_size_t]
        d.rc_client_create_achievement_list.argtypes = [C.c_void_p, C.c_int, C.c_int]; d.rc_client_create_achievement_list.restype = C.POINTER(_List)
        d.rc_client_destroy_achievement_list.argtypes = [C.POINTER(_List)]; d.rc_client_destroy_achievement_list.restype = None
        self.server = server; self.done = queue.Queue(); self.messages = []
        self.ram = RamView()
        self._call = _SERVER_CALL(self._server_call); self._event = _EVENT(self._on_event); self._log = _LOGFN(self._on_log)
        self._login_cb = _CALLBACK(self._on_login); self._load_cb = _CALLBACK(self._on_load)
        self.c = d.alundra_ra_create(self._call)
        d.alundra_ra_set_ram(C.addressof(self.ram.ptr), RAM_SIZE)
        d.rc_client_set_hardcore_enabled(self.c, 0)
        d.rc_client_set_event_handler(self.c, self._event)
        d.rc_client_enable_logging(self.c, 2, self._log)
        clause = C.create_string_buffer(128); d.rc_client_get_user_agent_clause(self.c, clause, 128)
        self.ua = f'{UA} (Windows) {_s(clause.value)}'.strip()
        self.state = 'out'                 # out, logging_in, in, loading, loaded, failed
        self.status = 'Not logged in'; self.loaded_hash = None; self.pending_login = None

    # ---- server calls: a thread each, answered on the game's thread (pump)
    def _server_call(self, req, cb, cb_data, client):
        r = req.contents
        url, post, ctype = _s(r.url), (r.post_data or b''), _s(r.content_type) or 'application/x-www-form-urlencoded'
        threading.Thread(target=self._fetch, args=(url, post, ctype, cb, cb_data), daemon=True).start()

    def _fetch(self, url, post, ctype, cb, cb_data):
        try:
            if self.server is not None: status, body = self.server(url, post.decode('utf-8', 'replace'), ctype)
            else:
                import urllib.request, urllib.error
                rq = urllib.request.Request(url, data=post or None, headers={'User-Agent': self.ua, 'Content-Type': ctype})
                try:
                    with urllib.request.urlopen(rq, timeout=30) as f: status, body = f.status, f.read()
                except urllib.error.HTTPError as e: status, body = e.code, e.read()
        except Exception:
            status, body = -2, b''                                  # (rcheevos retries it)
        self.done.put((cb, cb_data, status, body))

    def pump(self):
        while True:
            try: cb, cb_data, status, body = self.done.get_nowait()
            except queue.Empty: return
            buf = C.create_string_buffer(body, len(body) + 1)
            resp = _Response(C.cast(buf, C.c_void_p), len(body), status)
            _SERVER_CB(cb)(C.byref(resp), cb_data)

    # ---- events
    def say(self, *lines): self.messages.append([list(lines), POPUP_FRAMES])

    def _on_log(self, msg, client):
        try:
            with open(LOG, 'a', encoding='utf-8') as f: f.write(_s(msg) + '\n')
        except OSError: pass

    def _on_event(self, ev, client):
        e = ev.contents
        if e.type == EV_TRIGGERED and e.achievement:
            a = e.achievement.contents
            self.say(f'{_s(a.title)}  ({a.points})', _s(a.description))
        elif e.type == EV_COMPLETED:
            g = self.dll.rc_client_get_game_info(self.c)
            self.say('Mastered', _s(g.contents.title) if g else '')
        elif e.type == EV_SERVER_ERROR and e.server_error:
            self.say('RetroAchievements', _s(e.server_error.contents.error_message))
        elif e.type == EV_DISCONNECTED: self.say('RetroAchievements', 'Unlock waiting for the connection')
        elif e.type == EV_RECONNECTED: self.say('RetroAchievements', 'Unlocks sent')

    # ---- login and the game
    def login_password(self, user, password):
        self.state = 'logging_in'; self.status = 'Logging in...'; self.pending_login = 'password'
        self.dll.rc_client_begin_login_with_password(self.c, user.encode(), password.encode(), self._login_cb, None)

    def login_token(self, user, token):
        self.state = 'logging_in'; self.status = 'Logging in...'; self.pending_login = 'token'
        self.dll.rc_client_begin_login_with_token(self.c, user.encode(), token.encode(), self._login_cb, None)

    def user(self):
        u = self.dll.rc_client_get_user_info(self.c)
        return u.contents if u else None

    def _on_login(self, result, err, client, ud):
        if result == 0:
            u = self.user(); self.state = 'in'
            self.status = f'Logged in as {_s(u.display_name)}' if u else 'Logged in'
            self.login_ok = (_s(u.username), _s(u.token)) if u else None
        else:
            self.state = 'failed'; self.status = _s(err) or f'Login failed ({result})'; self.login_ok = None
            self.login_error = result

    def load(self, h):
        self.state = 'loading'; self.loaded_hash = h
        self.dll.rc_client_begin_load_game(self.c, h.encode(), self._load_cb, None)

    def _on_load(self, result, err, client, ud):
        if result != 0:
            self.state = 'noload'; self.status = _s(err) or f'Game not loaded ({result})'   # (not asked again this run)
            self.say('RetroAchievements', self.status); return
        self.state = 'loaded'
        s = _Summary(); self.dll.rc_client_get_user_game_summary(self.c, C.byref(s))
        g = self.dll.rc_client_get_game_info(self.c)
        title = _s(g.contents.title) if g else 'Alundra'
        self.status = f'{title}: {s.num_unlocked} / {s.num_core}'
        self.say(title, f'{s.num_unlocked} of {s.num_core} achievements unlocked')

    def achievements(self):
        """The set's achievements by rcheevos' groups (Unlocked, Locked, ...): [(label, [(title, description,
        points, unlocked, progress)])]."""
        if self.state != 'loaded': return []
        lst = self.dll.rc_client_create_achievement_list(self.c, 1, 0)        # core, by lock state
        if not lst: return []
        out = []
        try:
            l = lst.contents
            for i in range(l.num_buckets):
                b = l.buckets[i]
                out.append((_s(b.label), [(_s(a.contents.title), _s(a.contents.description), a.contents.points,
                                           bool(a.contents.unlocked), _s(a.contents.measured_progress))
                                          for a in b.achievements[:b.num_achievements]]))
        finally:
            self.dll.rc_client_destroy_achievement_list(lst)
        return out

    def summary(self):
        s = _Summary(); self.dll.rc_client_get_user_game_summary(self.c, C.byref(s))
        return s

    def unload(self):
        if self.state in ('loading', 'loaded'): self.dll.rc_client_unload_game(self.c); self.state = 'in'
        self.loaded_hash = None

    def logout(self):
        self.unload(); self.dll.rc_client_logout(self.c); self.state = 'out'; self.status = 'Not logged in'

    def frame(self, g):
        self.pump()
        if self.state == 'loaded':
            self.ram.fill(g); self.dll.rc_client_do_frame(self.c)

    def idle(self):
        self.pump(); self.dll.rc_client_idle(self.c)

    def destroy(self):
        self.dll.rc_client_destroy(self.c); self.c = None


CLIENT = None
SERVER = None                     # (the tests' server; None: retroachievements.org)


def client(g):
    """The client while the option is on (made, and logged in with the kept token, the first time)."""
    global CLIENT
    s = g.settings
    if not s.get('ra_enabled'):
        if CLIENT is not None and CLIENT.state in ('loading', 'loaded'): CLIENT.unload()
        return None
    if CLIENT is None:
        try: CLIENT = Client(SERVER)
        except OSError as e:
            g.toast(f'RetroAchievements: {e}'[:60]); s['ra_enabled'] = False; return None
        if s.get('ra_user') and s.get('ra_token'): CLIENT.login_token(s['ra_user'], s['ra_token'])
    return CLIENT


def frame(g):
    """After each game frame."""
    c = client(g)
    if c is None: return
    login = getattr(c, 'login_ok', None)
    if login is not None:                                     # keep the token (never the password)
        g.settings['ra_user'], g.settings['ra_token'] = login; c.login_ok = None
        from settings_screen import save_settings
        save_settings(g.settings)
    if c.state == 'failed' and c.pending_login == 'token' and getattr(c, 'login_error', 0) in (RC_INVALID_CREDENTIALS, RC_EXPIRED_TOKEN):
        g.settings['ra_token'] = ''; c.pending_login = None
    if base_game():
        if c.state == 'in':
            h = disc_hash()
            if h is None:
                c.state = 'noload'; c.status = 'No disc hash: extract again'; c.say('RetroAchievements', c.status)
            else: c.load(h)
    elif c.state in ('loading', 'loaded'):
        c.unload(); c.status = 'Off in this mode'
    c.frame(g)


def idle(g):
    """While the game is paused under the settings page."""
    c = CLIENT if g.settings.get('ra_enabled') else None
    if c is not None: c.idle()


SIZE = 0.5                         # the message's size against the game's picture
MARGIN = 4                         # game pixels from the picture's top and right edges


def tick():
    """One game frame of the shown message's time."""
    c = CLIENT
    if c is None or not c.messages: return
    c.messages[0][1] -= 1
    if c.messages[0][1] <= 0: c.messages.pop(0); c.box = None


def draw(g, screen, dst):
    """The first waiting message on the game's parchment in its font, at SIZE of the picture's scale, in the top right
    corner of the picture (dst: where it is in the window)."""
    c = CLIENT
    if c is None or not c.messages: return
    m = c.messages[0]
    if getattr(c, 'box', None) is None or c.box[0] is not m:
        box = _box(g, m)
        if box is None: return
        c.box = (m, box, {})
    m_, box, scaled = c.box
    f = dst.w / 320 * SIZE
    size = (max(1, round(box.get_width() * f)), max(1, round(box.get_height() * f)))
    s = scaled.get(size)
    if s is None:
        n = max(1, -(-size[0] // box.get_width()))                 # nearest-neighbour up to a whole multiple, then down
        big = pygame.transform.scale(box, (box.get_width() * n, box.get_height() * n))
        s = scaled[size] = big if big.get_size() == size else pygame.transform.smoothscale(big, size)
    m_px = round(MARGIN * dst.w / 320)
    screen.blit(s, (dst.right - m_px - size[0], dst.y + m_px))


def _box(g, m):
    """The message on its parchment at the game's own size."""
    gf = g.game_font; ss = getattr(g, 'settings_screen', None)
    if not gf.ok or ss is None: return None
    lines = []
    for text in m[0]:
        if not text: continue
        cur = ''
        for word in text.split(' '):
            t = f'{cur} {word}'.strip() if cur else word
            if gf.width(t) <= 272 or not cur: cur = t
            else: lines.append(cur); cur = word
        lines.append(cur)
    lines = lines[:3]
    for i, l in enumerate(lines):
        while gf.width(lines[i]) > 272: lines[i] = lines[i][:-1]
    h = 16 + 16 * len(lines); w = max(64, max(gf.width(l) for l in lines) + 32)
    box = ss.parchment(w, h).copy()
    for i, l in enumerate(lines): gf.draw(box, l, 16, 8 + 16 * i)
    return box


# ---------------------------------------------------------------- Options > RetroAchievements
class Window:
    """Its own window over the settings page: Achievements On / Off, the login (name, password) or log out."""
    W, H = 272, 152

    def __init__(self, ss):
        self.ss = ss; self.g = ss.g; self.row = 0; self.edit = None; self.name = self.g.settings.get('ra_user', ''); self.pw = ''
        self.rects = []

    def rows(self):
        s = self.g.settings; c = CLIENT if s.get('ra_enabled') else None
        r = [('toggle', 'Achievements')]
        if s.get('ra_enabled'):
            if c is not None and c.state == 'loaded': r.append(('view', 'View Achievements'))
            if c is not None and c.state in ('in', 'loading', 'loaded', 'noload'): r.append(('logout', 'Log Out'))
            elif c is None or c.state != 'logging_in':
                r += [('name', 'Name'), ('pw', 'Password'), ('login', 'Log In')]
        return r + [('back', 'Back')]

    def close(self):
        self.edit = None; pygame.key.stop_text_input(); self.ss.ra_win = None; self.ss.sound(5)

    def activate(self):
        rows = self.rows(); self.row = min(self.row, len(rows) - 1); kind = rows[self.row][0]; s = self.g.settings
        if kind == 'toggle':
            s['ra_enabled'] = not s['ra_enabled']; self.ss.sound(2); client(self.g)
        elif kind in ('name', 'pw'):
            self.edit = kind; pygame.key.start_text_input(); self.ss.sound(2)
        elif kind == 'login':
            c = client(self.g)
            if c is None or not self.name or not self.pw: self.ss.sound(3); return
            c.login_password(self.name, self.pw); self.pw = ''; self.ss.sound(2)
        elif kind == 'logout':
            if CLIENT is not None: CLIENT.logout()
            s['ra_token'] = ''; self.ss.sound(2)
        elif kind == 'back': self.close()
        elif kind == 'view' and CLIENT is not None:
            items = []
            for label, achs in CLIENT.achievements():
                items.append(('head', label)); items += [('ach', a) for a in achs]
            s = CLIENT.summary(); gi = CLIENT.dll.rc_client_get_game_info(CLIENT.c)
            head = f'{_s(gi.contents.title) if gi else "Alundra"}  {s.num_unlocked} / {s.num_core}'
            sel = next((i for i, it in enumerate(items) if it[0] == 'ach'), None)
            if sel is None: self.ss.sound(3); return
            self.list = {'items': items, 'sel': sel, 'top': 0, 'head': head}; self.ss.sound(2)

    # ---- View Achievements: the set's list on a large parchment
    LW, LH = 304, 224
    list = None

    def list_move(self, d):
        L = self.list; items = L['items']; i = L['sel']
        while True:
            i += d
            if not 0 <= i < len(items): self.ss.sound(3); return
            if items[i][0] == 'ach': break
        L['sel'] = i; self.ss.sound(1)

    def list_handle(self, e):
        back = False
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_UP, pygame.K_w): self.list_move(-1)
            elif k in (pygame.K_DOWN, pygame.K_s): self.list_move(1)
            elif k in (pygame.K_PAGEUP, pygame.K_LEFT, pygame.K_a): [self.list_move(-1) for _ in range(5)]
            elif k in (pygame.K_PAGEDOWN, pygame.K_RIGHT, pygame.K_d): [self.list_move(1) for _ in range(5)]
            elif k in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_z) or \
                    pygame.key.name(k) in self.ss.c.keys.get('dash', []) + self.ss.c.keys.get('item', []): back = True
        elif e.type == pygame.JOYHATMOTION and e.value[1]: self.list_move(-e.value[1])
        elif e.type == pygame.JOYBUTTONDOWN:
            tok = f'button:{e.button}'
            if tok in self.ss.c.pad.get('dash', []) or tok in self.ss.c.pad.get('item', []) or e.button in (0, 7): back = True
        elif e.type == pygame.MOUSEWHEEL: self.list_move(-1 if e.y > 0 else 1)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3: back = True
        if back: self.list = None; self.ss.sound(5)
        return True

    def list_draw(self, screen, v):
        ss = self.ss; gf = self.g.game_font; L = self.list; items = L['items']
        x, y = (320 - self.LW) // 2, (240 - self.LH) // 2
        v.blit(ss.parchment(self.LW, self.LH), (x, y))
        ss.text(v, L['head'], x + 16, y + 8, self.LW - 32)
        top, bottom = y + 28, y + self.LH - 12
        h = lambda it: 16 if it[0] == 'head' else 32
        if L['sel'] < L['top']: L['top'] = L['sel'] - (1 if L['sel'] and items[L['sel'] - 1][0] == 'head' else 0)
        while sum(h(it) for it in items[L['top']:L['sel'] + 1]) > bottom - top: L['top'] += 1
        ry = top; i = L['top']
        while i < len(items) and ry + h(items[i]) <= bottom:
            kind, it = items[i]
            if kind == 'head': ss.text(v, it, x + 16, ry)
            else:
                title, desc, pts, unlocked, prog = it
                p = str(pts); pw = gf.width(p) if gf.ok else 16
                ss.text(v, title, x + 32, ry, self.LW - 56 - pw)
                ss.text(v, p, x + self.LW - 16 - pw, ry)
                ss.text(v, desc + (f'  {prog}' if prog and not unlocked else ''), x + 40, ry + 14, self.LW - 56)
                if i == L['sel']: ss.glove(v, x + 12, ry)
            ry += h(items[i]); i += 1
        sh8 = self.g.inventory_ui.sheet_us(8)
        if sh8 is not None and i < len(items):
            v.blit(sh8, (x + self.LW // 2 - 8, y + self.LH - 18), (176 + 16 * ((ss.glove_t // 10) % 4), 56, 16, 16))
        screen.fill((0, 0, 0))
        dst = self.g.view_rect()
        import video_filter as VF
        screen.blit(VF.upscale(v, dst.size, self.g.settings), dst.topleft)

    def handle(self, e):
        if self.list is not None: return self.list_handle(e)
        if self.edit is not None:
            if e.type == pygame.TEXTINPUT:
                if self.edit == 'name': self.name = (self.name + e.text)[:32]
                else: self.pw = (self.pw + e.text)[:64]
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    if self.edit == 'name': self.name = self.name[:-1]
                    else: self.pw = self.pw[:-1]
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                    self.edit = None; pygame.key.stop_text_input(); self.ss.sound(1)
                    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB, pygame.K_DOWN): self.row = (self.row + 1) % len(self.rows())
                    elif e.key == pygame.K_UP: self.row = (self.row - 1) % len(self.rows())
            return True
        n = len(self.rows())
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_UP, pygame.K_w): self.row = (self.row - 1) % n; self.ss.sound(1)
            elif k in (pygame.K_DOWN, pygame.K_s): self.row = (self.row + 1) % n; self.ss.sound(1)
            elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d) and self.rows()[self.row][0] == 'toggle': self.activate()
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_z): self.activate()
            elif k == pygame.K_ESCAPE or pygame.key.name(k) in self.ss.c.keys.get('dash', []) + self.ss.c.keys.get('item', []): self.close()
        elif e.type == pygame.JOYHATMOTION and e.value[1]:
            self.row = (self.row - e.value[1]) % n; self.ss.sound(1)
        elif e.type == pygame.JOYBUTTONDOWN:
            tok = f'button:{e.button}'
            if tok in self.ss.c.pad.get('dash', []) or tok in self.ss.c.pad.get('item', []) or e.button == 7: self.close()
            elif e.button == 0: self.activate()
        elif e.type == pygame.MOUSEMOTION or (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
            pos = self.ss.to_canvas(e.pos)
            for r, i in self.rects:
                if pos and r.collidepoint(pos):
                    if i != self.row: self.row = i; self.ss.sound(1)
                    if e.type == pygame.MOUSEBUTTONDOWN: self.activate()
        return True

    def draw(self, screen, v):
        if self.list is not None: return self.list_draw(screen, v)
        ss = self.ss; gf = self.g.game_font; s = self.g.settings
        x, y = (320 - self.W) // 2, (240 - self.H) // 2
        v.blit(ss.parchment(self.W, self.H), (x, y))
        ss.text(v, 'RetroAchievements', x + (self.W - gf.width(ss.tr('RetroAchievements'))) // 2 if gf.ok else x + 16, y + 10)
        rows = self.rows(); self.row = min(self.row, len(rows) - 1); self.rects = []
        lx = x + 32; vx = x + 128
        for i, (kind, label) in enumerate(rows):
            ry = y + 32 + 16 * i
            ss.text(v, label, lx, ry)
            val = None
            if kind == 'toggle': val = 'On' if s.get('ra_enabled') else 'Off'
            elif kind == 'name': val = self.name + ('_' if self.edit == 'name' else '')
            elif kind == 'pw': val = '*' * len(self.pw) + ('_' if self.edit == 'pw' else '')
            if val is not None: ss.text(v, val, vx, ry, x + self.W - 16 - vx)
            if i == self.row: ss.glove(v, lx - 20, ry)
            self.rects.append((pygame.Rect(lx - 4, ry, self.W - 56, 16), i))
        c = CLIENT if s.get('ra_enabled') else None
        if c is not None:
            st = c.status if base_game() or c.state not in ('in', 'loading', 'loaded') else 'Off in this mode'
            ss.text(v, st, x + 16, y + self.H - 24, self.W - 32)
        screen.fill((0, 0, 0))
        dst = self.g.view_rect()
        import video_filter as VF
        screen.blit(VF.upscale(v, dst.size, self.g.settings), dst.topleft)
