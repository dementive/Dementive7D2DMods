"""Compare vanilla item_property_overrides for each mod weapon's parent with the mod weapon's own overrides.

Usage: python modoverrides.py <merged item_modifiers.xml> <merged items.xml> <mod prefix>
"""
import sys
import xml.etree.ElementTree as ET

mods = ET.parse(sys.argv[1]).getroot()
items = ET.parse(sys.argv[2]).getroot()
prefix = sys.argv[3]
parent = {}
for it in items.iter("item"):
    n = it.get("name")
    if n.startswith(prefix):
        ext = it.find("property[@name='Extends']")
        if ext is not None:
            parent[n] = ext.get("value")

for im in mods.iter("item_modifier"):
    ov = {o.get("name"): {p.get("name"): p.get("value") for p in o.findall("property")} for o in im.findall("item_property_overrides")}
    for m, p in parent.items():
        if p in ov or m in ov:
            v, mine = ov.get(p), ov.get(m)
            if v != mine:
                print(f"{im.get('name')}: {m} (parent {p})")
                if v is None:
                    print("    vanilla parent has no override; mod has", mine)
                elif mine is None:
                    print("    MISSING; vanilla:", v)
                else:
                    for k in sorted(set(v) | set(mine)):
                        if v.get(k) != mine.get(k):
                            print(f"    {k}: vanilla={v.get(k)!r} mod={mine.get(k)!r}")
