"""Write the lists of game names that refcheck.py checks references against.

Usage: python make_gameinfo.py <game dir> <Api.exe> <out dir>
- types.txt: every type in Assembly-CSharp, by full and short name (from Api.exe)
- passive_effects.txt: the PassiveEffects enum (from Api.exe)
- icons.txt: vanilla item icons (Data/ItemIcons)
- pois.txt: vanilla POI prefabs (Data/Prefabs/POIs)
Rerun it after a game update.
"""
import os
import subprocess
import sys

game, api, out = sys.argv[1:4]
managed = os.path.join(game, "7DaysToDie_Data", "Managed")
harmony = os.path.join(game, "Mods", "0_TFP_Harmony")
os.makedirs(out, exist_ok=True)


def api_lines(*query):
    result = subprocess.run([api, managed, harmony, *query], capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def write(name, values):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(set(values))) + "\n")
    print(f"{name}: {len(set(values))}")


types = set()
for full in api_lines("?"):
    types.add(full)
    # Short name too: refcheck looks classes up by the name XML uses, e.g. MinEventActionExplode
    types.add(full.split("<")[0].split(".")[-1])
write("types.txt", types)

passives = api_lines("PassiveEffects")
assert passives[0].startswith("### "), passives[0]
write("passive_effects.txt", passives[1:])

icons_dir = os.path.join(game, "Data", "ItemIcons")
write("icons.txt", [os.path.splitext(f)[0] for f in os.listdir(icons_dir) if f.lower().endswith(".png")])

pois_dir = os.path.join(game, "Data", "Prefabs", "POIs")
write("pois.txt", [f[:-4] for f in os.listdir(pois_dir) if f.endswith(".xml")])
