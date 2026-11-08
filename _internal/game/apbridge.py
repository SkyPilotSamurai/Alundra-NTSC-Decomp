"""ARCHIPELAGO: runs connector_alundra.lua, the script BizHawk runs, unchanged.  The script sees the
BizHawk functions it uses (mainmemory, memory, emu, gui) and LuaSocket's calls, on the game's memory
and a Python socket; one emu.frameadvance is one game frame, so the Alundra client connects to the
game as it does to BizHawk (port 52980)."""
import socket as pysocket
from pathlib import Path
from home import CODE

TOOL = CODE.parent / 'randomizer'

SETUP = r'''
local py = ...
mainmemory = {read_u8 = py.r8, read_u16_le = py.r16, write_u8 = py.w8, write_u16_le = py.w16}
memory = mainmemory
emu = {framecount = py.frames, frameadvance = coroutine.yield, getsystemid = function() return "PSX" end}
gui = {drawText = py.text, clearGraphics = py.clear}
print = function() end
checkBizHawkVersion = function() return true end
local open = io.open
io.open = function(name, mode) return open(py.path(name), mode) end

local function client(c)
  return {
    settimeout = function() end,
    receive = function() local d, e = py.receive(c); if d == py.none then return nil, e end; return d end,
    send = function(_, data) local n, e = py.send(c, data); if n == py.none then return nil, e end; return n end,
    close = function() py.close(c) end,
  }
end
package.preload["socket"] = function()
  return {bind = function(host, port)
    local s = py.bind(host, port)
    return {
      settimeout = function() end,
      accept = function() local c = py.accept(s); if c == py.none then return nil, "timeout" end; return client(c) end,
      close = function() py.close(s) end,
    }
  end}
end
package.preload["common"] = function() return {} end
package.preload["json"] = function()
  local J = {}
  local esc = {['"']='\\"', ['\\']='\\\\', ['\n']='\\n', ['\r']='\\r', ['\t']='\\t'}
  local function enc(v)
    local t = type(v)
    if t == "string" then return '"' .. v:gsub('[%c"\\]', function(c) return esc[c] or string.format("\\u%04x", c:byte()) end) .. '"'
    elseif t == "table" then
      local out = {}
      if #v > 0 or next(v) == nil then
        for i = 1, #v do out[i] = enc(v[i]) end
        return "[" .. table.concat(out, ",") .. "]"
      end
      for k, x in pairs(v) do out[#out + 1] = enc(tostring(k)) .. ":" .. enc(x) end
      return "{" .. table.concat(out, ",") .. "}"
    elseif t == "number" and v == math.floor(v) then return string.format("%d", v)
    end
    return tostring(v)
  end
  J.encode = enc
  J.decode = function(s)
    local pos = 1
    local value
    local function ws() pos = s:find("%S", pos) or #s + 1 end
    local function str()
      local out = {}; pos = pos + 1
      while true do
        local c = s:sub(pos, pos)
        if c == "" then error("json: unfinished string") end
        if c == '"' then pos = pos + 1; return table.concat(out) end
        if c == "\\" then
          local n = s:sub(pos + 1, pos + 1)
          if n == "u" then out[#out + 1] = utf8.char(tonumber(s:sub(pos + 2, pos + 5), 16)); pos = pos + 6
          else out[#out + 1] = ({n="\n", r="\r", t="\t", b="\b", f="\f"})[n] or n; pos = pos + 2 end
        else out[#out + 1] = c; pos = pos + 1 end
      end
    end
    value = function()
      ws(); local c = s:sub(pos, pos)
      if c == "{" then
        local t = {}; pos = pos + 1; ws()
        if s:sub(pos, pos) == "}" then pos = pos + 1; return t end
        while true do
          ws(); local k = str(); ws(); pos = pos + 1; t[k] = value(); ws()
          local d = s:sub(pos, pos); pos = pos + 1
          if d == "}" then return t end
          if d ~= "," then error("json: bad object") end
        end
      elseif c == "[" then
        local t = {}; pos = pos + 1; ws()
        if s:sub(pos, pos) == "]" then pos = pos + 1; return t end
        while true do
          t[#t + 1] = value(); ws()
          local d = s:sub(pos, pos); pos = pos + 1
          if d == "]" then return t end
          if d ~= "," then error("json: bad array") end
        end
      elseif c == '"' then return str()
      elseif s:sub(pos, pos + 3) == "true" then pos = pos + 4; return true
      elseif s:sub(pos, pos + 4) == "false" then pos = pos + 5; return false
      elseif s:sub(pos, pos + 3) == "null" then pos = pos + 4; return nil
      end
      local n = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", pos)
      if not n then error("json: bad value") end
      pos = pos + #n; return tonumber(n)
    end
    return value()
  end
  return J
end
'''


class Bridge:
    def __init__(self, folder):
        import lupa.lua54 as L
        self.folder = Path(folder); self.g = None; self.frame = 0; self.lines = []; self.failed = None; self.modelled = set()
        self.lua = L.LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
        none = object()
        def receive(c):
            try:
                while b'\n' not in c.buf:
                    d = c.s.recv(65536)
                    if not d: return none, 'closed'
                    c.buf += d
            except BlockingIOError:
                return none, 'timeout'
            except OSError:
                return none, 'closed'
            line, c.buf = c.buf.split(b'\n', 1)
            return line.decode('utf-8', 'replace'), None
        def send(c, data):
            try: c.s.sendall(data.encode('utf-8')); return len(data), None
            except OSError: return none, 'closed'
        def bind(host, port):
            s = pysocket.socket(); s.setsockopt(pysocket.SOL_SOCKET, pysocket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1' if host == 'localhost' else host, port)); s.listen(1); s.setblocking(False)
            self.server = s
            return s
        def accept(s):
            try: c, _ = s.accept()
            except OSError: return none
            c.setblocking(False)
            return type('C', (), {'s': c, 'buf': b''})()
        def close(x): getattr(x, 's', x).close()
        py = self.lua.table_from({
            'r8': lambda a: self.read(a, 'u8'), 'r16': lambda a: self.read(a, 'u16'),
            'w8': lambda a, v: self.write(a, v, 'w8'), 'w16': lambda a, v: self.write(a, v, 'w16'),
            'frames': lambda: self.frame, 'text': lambda x, y, t, *a: self.lines.append((x, y, t, a[0] if a else 'white')),
            'clear': lambda: self.lines.clear(), 'path': lambda n: str(self.folder / n),
            'bind': bind, 'accept': accept, 'receive': receive, 'send': send, 'close': close, 'none': none})
        self.lua.execute(SETUP, py)
        src = (TOOL / 'connector_alundra.lua').read_text(encoding='utf-8')
        self.resume = self.lua.execute('local src = ...; local co = coroutine.create(load(src, "connector_alundra.lua")); return function() return coroutine.resume(co) end', src)
        self.server = None

    def read(self, a, how):
        """RAM as the script knows it; what the port keeps on objects comes from there."""
        g = self.g
        if a == 0x1AC710: return g.player.hp_max
        if a == 0x1D7B40: return (g.player.px >> 16) & 0xFFFF
        if a == 0x1D7B90: return (g.player.py >> 16) & 0xFFFF
        try: return getattr(g.mem, how)(0x80000000 | a)
        except Exception:
            from engine import mem
            self.modelled.add(a)
            v = getattr(g, mem._GLOB.get(a, ''), 0) or 0
            return v & (0xFF if how == 'u8' else 0xFFFF)

    def write(self, a, v, how):
        g = self.g
        if a == 0x1AC710: g.player.hp_max = v; return
        try: getattr(g.mem, how)(0x80000000 | a, v)
        except Exception:
            from engine import mem
            self.modelled.add(a)
            if mem._GLOB.get(a): setattr(g, mem._GLOB[a], v)

    def tick(self, g):
        """One game frame of the script (up to its next emu.frameadvance)."""
        if self.failed: return
        self.g = g; self.frame += 1
        r = self.resume()
        ok = r[0] if isinstance(r, tuple) else r
        if not ok:
            self.failed = str(r[1]) if isinstance(r, tuple) else 'stopped'
            (self.folder / 'connector_error.txt').write_text(self.failed, encoding='utf-8')

    def draw(self, g, surf):
        """The script's message (it draws white text outlined in black at the bottom): the game's
        font on the menus' parchment, its dark ink being unreadable on a dark map."""
        gf = g.game_font; ss = getattr(g, 'settings_screen', None)
        texts = [t for x, y, t, c in self.lines if c == 'white']
        if not texts or not gf.ok or ss is None: return
        lines = ['']
        for word in texts[-1].split(' '):                 # (up to two lines, whole words; what is left is cut)
            line = f'{lines[-1]} {word}'.strip()
            if gf.width(line) <= 272 or len(lines) == 2: lines[-1] = line
            else: lines.append(word)
        while gf.width(lines[-1]) > 272: lines[-1] = lines[-1][:-1]
        if not g.settings.get('ap_textbox', True):        # Text Box off: white letters above the screen's edge
            import pygame
            for i, l in enumerate(lines):
                x = (320 - gf.width(l)) // 2; y = 224 - 16 * (len(lines) - i)
                ink = pygame.Surface((320, 16), pygame.SRCALPHA); gf.draw(ink, l, 0, 0)
                white = ink.copy(); white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
                black = ink.copy(); black.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)): surf.blit(black, (x + dx, y + dy))
                surf.blit(white, (x, y))
            return
        h = 16 + 16 * len(lines); w = max(64, max(gf.width(l) for l in lines) + 32); x, y = (320 - w) // 2, 236 - h
        surf.blit(ss.parchment(w, h), (x, y))
        for i, l in enumerate(lines): gf.draw(surf, l, x + 16, y + 8 + 16 * i)

    def stop(self):
        if self.server is not None:
            try: self.server.close()
            except OSError: pass
