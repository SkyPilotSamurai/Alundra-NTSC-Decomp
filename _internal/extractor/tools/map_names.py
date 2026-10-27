"""Source-reported place labels; numeric map IDs disambiguate rooms."""
import json,re
from pathlib import Path
NAMES=json.loads((Path(__file__).resolve().parents[1]/"data/map-names.json").read_text())["maps"]
CUSTOM={}  # names given in the editor (database document['map_names']), set by the editor
def set_custom_names(names):
 global CUSTOM
 CUSTOM=names if isinstance(names,dict) else {}
def map_label(number):
 custom=CUSTOM.get(str(number))
 if custom:return f"{custom} (Map {number})"
 if 483<=number<2547 and str(number) not in NAMES:return f"New Map {number-482} (Map {number})"
 name=NAMES.get(str(number),{}).get("name","Unknown area")
 if name=="Inoa Randomizer":name="Inoa Village"
 return f"{name} (Map {number})"
def map_is_reported_unused(number):
 """Return whether the current source-reported label contains 'Unused'."""
 return "unused" in NAMES.get(str(number),{}).get("name","").casefold()
def map_number(value):
 match=re.search(r"\(Map (\d+)\)$",value)
 return int(match.group(1)) if match else int(value.strip(),0)
