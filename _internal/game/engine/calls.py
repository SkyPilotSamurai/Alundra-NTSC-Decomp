"""Calling game functions by address.  call(g, 0x80083394, e, ...) runs the ported routine
when there is one; otherwise the remake's stand-in (g.unported) — and in the checks the
original's recorded call is replayed, so a port can be verified before its callees are."""
import importlib
from .registry import FUNCS


_MODS = {}                               # addr -> (its module, the name, the registry entry)


def resolve(addr):
    m = FUNCS.get(addr)
    if m is None: return None
    c = _MODS.get(addr)
    if c is None or c[2] is not m:
        c = _MODS[addr] = (importlib.import_module(f'engine.{m[0]}'), m[1], m)
    return getattr(c[0], c[1])          # (looked up each call: the checks put mocks in its place)


def call(g, addr, *args):
    f = resolve(addr)
    if f is not None: return f(g, *args)
    h = getattr(g, 'unported', None)
    if h is None: raise NotImplementedError(f'game function {addr:08X} is not ported')
    return h(addr, *args)


class _Stack:
    """An argument that is a buffer in the caller's stack frame (the checks accept any stack address)."""
    def __repr__(self): return 'STACK'


STACK = _Stack()


class Buf(_Stack):
    """A stack buffer whose contents the remake needs (a character to draw, a rectangle):
    the checks treat it like STACK."""
    def __init__(self, data=b'', **kw):
        self.data = bytes(data); self.__dict__.update(kw)
    def __repr__(self): return f'STACK{self.data!r}'
