"""Where the remake's files are.  CODE is this folder (the game's .py files and engine/).  HOME
holds what the player has and makes: assets/ (the game data built from their disc), saves/,
settings.json, controls.json, crash.log.  In Alundra Remake.exe the code is packed inside the
exe's _internal folder and HOME is the exe's folder; from the source, HOME is the folder above
game/ (or the code's own folder in a development folder)."""
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent
if getattr(sys, 'frozen', False):
    HOME = Path(sys.executable).resolve().parent
else:
    HOME = CODE.parent if CODE.name == 'game' else CODE
ASSETS = HOME / 'assets'
