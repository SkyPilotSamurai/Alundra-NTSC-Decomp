"""Ported functions by their address in the US ALUN_CD.EXE (for tools/us_decomp/check.py)."""
FUNCS = {}        # addr -> (module, function name)
SIGS = {}         # addr -> ('ret',) when the return value matters
RETKIND = {}      # addr -> 'ptr' (entity / effect / record or None) or 'int'
# presentation / bookkeeping the checks always replay from the original (sound, HUD,
# debug text): the port calls them, the harness feeds back what the original did
MOCK_ALWAYS = set()
# routines whose port hands the work to the remake (Game methods the check states do not have):
# the checks run the original's call and replay its result and writes to the port
REPLAY = set()
# routines a port reaches through a function pointer (jalr: a program table entry), which the
# checks cannot see in the code: addr -> [callee addresses]
CALLS = {}


def port(addr, ret=False, mock_always=False, replay=False, calls=()):
    def deco(f):
        FUNCS[addr] = (f.__module__.split('.')[-1], f.__name__)
        if ret: SIGS[addr] = ('ret',); RETKIND[addr] = ret if ret in ('ptr', 'list') else 'int'
        if mock_always: MOCK_ALWAYS.add(addr)
        if replay: REPLAY.add(addr)
        if calls: CALLS[addr] = list(calls)
        f.addr = addr
        return f
    return deco


def load_all():
    from . import core, menu, items, entity, player, aihelp, message, portrait, screen, choice, card, savewin, gamestart, drops, shadows  # noqa: F401  (registers everything)
    import importlib, os
    here = os.path.dirname(os.path.abspath(__file__))
    for f in sorted(os.listdir(here)):                   # ai_*.py: the built-in sprite programs
        if f.startswith('ai_') and f.endswith('.py'): importlib.import_module(f'engine.{f[:-3]}')
