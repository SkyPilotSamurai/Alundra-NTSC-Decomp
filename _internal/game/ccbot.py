"""CROWD CONTROL's own programs, started with the game (ccbridge.CrowdControl): the chat bot (Alundra_Crowd_Control.py,
reading the chosen Twitch channel's chat; --no-buffed turns its Buffed Spawn commands off) and the Points Display (Points_Display.pyw), both from
_internal/randomizer/crowd_control, run unchanged apart from the bot's channel line.
    ccbot.py --bot <channel> [--buffed | --no-buffed]      ccbot.py --points"""
import re, sys, types
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / 'randomizer' / 'crowd_control'


def run(name, channel=None, buffed=True):
    src = (DIR / name).read_text(encoding='utf-8')
    if channel is not None:
        src = re.sub(r"(?m)^TWITCH_CHANNEL = .*$", lambda m: f'TWITCH_CHANNEL = {channel.lower()!r}', src, count=1)
        src = re.sub(r"(?m)^buffed_spawns = .*$", lambda m: f'buffed_spawns = {bool(buffed)}', src, count=1)
    try: import requests  # noqa: F401  (only the bot's YouTube connection uses it)
    except ImportError: sys.modules['requests'] = types.ModuleType('requests')
    sys.path.insert(0, str(DIR))
    sys.argv = [str(DIR / name)]
    exec(compile(src, str(DIR / name), 'exec'), {'__name__': '__main__', '__file__': str(DIR / name), '__builtins__': __builtins__})


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['--bot'] and len(a) > 1: run('Alundra_Crowd_Control.py', a[1], '--no-buffed' not in a)
    elif a[:1] == ['--points']: run('Points_Display.pyw')
