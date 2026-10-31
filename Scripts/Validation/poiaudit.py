"""Audit quest POI targets against the game's prefab data.

Usage: python poiaudit.py <game dir> <quests.xml> [extra prefab dir ...]
For each quest, works out the quest tags the game will give it (fetch/clear/infested/restore_power/hidden_cache)
and checks GotoPOIDEM PrefabNames (exists, has those QuestTags, DifficultyTier) and counts candidates for
RandomTaggedPOIGotoDEM include/exclude tags.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

game, quests_path = sys.argv[1], sys.argv[2]
prefab_dirs = [os.path.join(game, "Data", "Prefabs", "POIs")] + sys.argv[3:]

pois = {}
for d in prefab_dirs:
    for root, _, files in os.walk(d):
        for f in files:
            if not f.endswith(".xml"):
                continue
            try:
                r = ET.parse(os.path.join(root, f)).getroot()
            except ET.ParseError:
                continue
            props = {p.get("name"): p.get("value", "") for p in r.iter("property")}
            def tags(v):
                return {t.strip().lower() for t in v.split(",") if t.strip()}
            pois[f[:-4]] = dict(quest=tags(props.get("QuestTags", "")), tags=tags(props.get("Tags", "")),
                                tier=int(props.get("DifficultyTier", "0") or 0), dir=root)

text = open(quests_path, encoding="utf-8").read()
root = ET.fromstring(re.sub(r"<(/?)Dementive>", r"<\1Dementive>", text))
problems = 0
for q in root.iter("quest"):
    qid = q.get("id")
    if qid is None:
        continue
    props = {p.get("name"): p.get("value") for p in q.findall("property")}
    need = set()
    objs = q.findall("objective")
    for o in objs:
        t = o.get("type")
        if t == "FetchFromContainer":
            op = {p.get("name"): p.get("value") for p in o.findall("property")}
            need.add("hidden_cache" if op.get("fetch_mode", "").lower() == "hidden" else "fetch")
        elif t == "ClearSleepers":
            need.add("clear")
        elif t == "POIBlockActivate":
            need.add("restore_power")
    if props.get("extra_tags"):
        need |= {t.strip() for t in props["extra_tags"].split(",") if t.strip()}
    tier = int(props.get("difficulty_tier", "0") or 0)
    for o in objs:
        t = o.get("type")
        op = {p.get("name"): p.get("value") for p in o.findall("property")}
        poi_tier = int(op.get("poi_tier", tier))
        poi_tier = tier if poi_tier < 0 else poi_tier
        if t.startswith("GotoPOIDEM"):
            names = [n.strip() for n in (op.get("PrefabNames") or op.get("PrefabName") or "").split(",") if n.strip()]
            bad = []
            for n in names:
                p = pois.get(n)
                if p is None:
                    bad.append(f"{n}:MISSING")
                elif not need <= p["quest"]:
                    bad.append(f"{n}:lacks {','.join(sorted(need - p['quest']))}")
            tiers = sorted({pois[n]["tier"] for n in names if n in pois})
            ok = len(names) - len(bad)
            flag = "!!" if bad else "  "
            if bad or ok == 0:
                problems += 1
            print(f"{flag} {qid} [tier {tier}, poi tiers {tiers}, needs {sorted(need)}] {ok}/{len(names)} ok" + (f"; {' '.join(bad)}" if bad else ""))
        elif t.startswith("RandomTaggedPOIGotoDEM") or t == "RandomPOIGoto":
            inc = {x.strip().lower() for x in (op.get("include_tags") or "").split(",") if x.strip()}
            exc = {x.strip().lower() for x in (op.get("exclude_tags") or "").split(",") if x.strip()}
            cands = [n for n, p in pois.items() if p["tier"] == poi_tier and need <= p["quest"]
                     and (not inc or p["tags"] & inc) and not (p["tags"] & exc)]
            flag = "!!" if len(cands) < 3 else "  "
            if len(cands) < 3:
                problems += 1
            print(f"{flag} {qid} [{t.split(',')[0]} tier {tier} poi_tier {poi_tier}, needs {sorted(need)}, inc {sorted(inc)}] {len(cands)} candidate prefabs")
print("problem quests:", problems)
