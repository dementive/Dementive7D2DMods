"""Write WeaponsExpanded's item_modifiers.xml: every mod weapon gets its vanilla parent's item_property_overrides.

Usage: python gen_item_modifiers.py <vanilla item_modifiers.xml> <mod items.xml> <out item_modifiers.xml>
Mods such as Burning Shaft, scopes and silencers look up per-item overrides by item name, so items that
Extend a vanilla weapon need their own copy. Generating them from vanilla keeps asset paths and offsets current.
"""
import re
import sys
import xml.etree.ElementTree as ET

van_path, items_path, out_path = sys.argv[1:4]
van = ET.parse(van_path).getroot()
items = open(items_path, encoding="utf-8").read()
weapons = re.findall(r'<item name="(\w+)">\s*<property name="Extends" value="(\w+)"', items)

out = ["<Dementive>", "",
       "\t<!-- Attachment overrides (flame effects, scope and sight offsets, silencer sounds, meshes) for each",
       "\t     weapon, copied from its vanilla parent weapon. Mods look these up by item name, so they are not",
       "\t     inherited through Extends. -->"]
for im in van.iter("item_modifier"):
    blocks = {o.get("name"): o for o in im.findall("item_property_overrides")}
    mine = [(w, p) for w, p in weapons if p in blocks]
    if not mine:
        continue
    out.append("")
    out.append(f"\t<append xpath=\"/item_modifiers/item_modifier[@name='{im.get('name')}']\">")
    for w, p in mine:
        out.append(f'\t\t<item_property_overrides name="{w}">')
        for prop in blocks[p]:
            attrs = " ".join(f'{k}="{v}"' for k, v in prop.attrib.items())
            out.append(f"\t\t\t<{prop.tag} {attrs}/>")
        out.append("\t\t</item_property_overrides>")
    out.append("\t</append>")
out += ["", "</Dementive>", ""]
open(out_path, "w", encoding="utf-8", newline="\r\n").write("\n".join(out))
print(f"{len(weapons)} weapons")
