"""Reference checks on mod content merged into vanilla XML by XmlPatch.exe.

Usage: python refcheck.py <gameDir> <mergedDir> <gameInfoDir> <modDir> [<modDir> ...]
Elements added by a mod carry dmMod="<mod>"; every reference inside them is resolved against the
merged config set and the game's own type/enum/icon/POI lists.
"""
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

game, merged, info = sys.argv[1], sys.argv[2], sys.argv[3]
mod_dirs = sys.argv[4:]
cfg = os.path.join(game, "Data", "Config")

def load(name):
    p = os.path.join(merged, name)
    if not os.path.exists(p):
        p = os.path.join(cfg, name)
    return ET.parse(p).getroot()

def lines(name):
    with open(os.path.join(info, name), encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}

X = {n: load(n + ".xml") for n in [
    "items", "blocks", "buffs", "loot", "recipes", "traders", "progression", "quests",
    "ui_display", "item_modifiers", "entityclasses", "entitygroups", "gameevents", "npc"]}

types = lines("types.txt")
passives = lines("passive_effects.txt")
pois = lines("pois.txt")
icons = lines("icons.txt")
mod_names = {os.path.basename(m.rstrip("/\\")) for m in mod_dirs}
for m in mod_dirs:
    d = os.path.join(m, "UIAtlases", "ItemIconAtlas")
    if os.path.isdir(d):
        icons |= {os.path.splitext(f)[0] for f in os.listdir(d) if f.lower().endswith(".png")}

# Localization: vanilla + every mod's file (csv or legacy txt)
loc = {}
def read_loc(path, src):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    head = [h.strip().lower() for h in rows[0]]
    eng = head.index("english") if "english" in head else None
    for r in rows[1:]:
        if r and r[0].strip():
            loc[r[0].strip()] = (r[eng] if eng is not None and eng < len(r) else "", src)
read_loc(os.path.join(cfg, "Localization.csv"), "vanilla")
for m in mod_dirs:
    for fn in ("Localization.csv", "Localization.txt"):
        p = os.path.join(m, "Config", fn)
        if os.path.exists(p):
            read_loc(p, os.path.basename(m) + "/" + fn)

names = lambda root, tag, attr="name": {e.get(attr) for e in root.iter(tag) if e.get(attr)}
items = names(X["items"], "item")
blocks = names(X["blocks"], "block")
item_mods = names(X["item_modifiers"], "item_modifier")
itemlike = items | blocks | item_mods
buffs = names(X["buffs"], "buff")
lootgroups = names(X["loot"], "lootgroup")
lootcontainers = names(X["loot"], "lootcontainer")
prob_t = names(X["loot"], "lootprobtemplate")
qual_t = names(X["loot"], "lootqualitytemplate")
trader_groups = names(X["traders"], "trader_item_group")
prog_names = {e.get("name") for e in X["progression"].iter() if e.get("name")}
quests = names(X["quests"], "quest", "id")
quest_lists = names(X["quests"], "quest_list", "id")
display_types = names(X["ui_display"], "item_display_info", "display_type")
entity_classes = names(X["entityclasses"], "entity_class")
entity_groups = names(X["entitygroups"], "entitygroup")
recipes_out = names(X["recipes"], "recipe")
workstations = {b for b in blocks}  # craft_area names are block names of workstations
game_events = names(X["gameevents"], "action_sequence")

issues = defaultdict(list)

def owner(path_stack):
    for e in reversed(path_stack):
        m = e.get("dmMod")
        if m:
            return m
    return None

def walk(root, fn):
    stack = []
    def rec(e):
        stack.append(e)
        m = owner(stack)
        if m:
            fn(e, stack, m)
        for c in e:
            rec(c)
        stack.pop()
    rec(root)

def ctx(stack):
    for e in reversed(stack):
        for a in ("name", "id"):
            if e.get(a) and e.tag in ("item", "block", "buff", "lootgroup", "quest", "recipe", "trader_item_group", "perk", "skill", "attribute", "item_modifier", "book"):
                return f"{e.tag} {e.get(a)}"
    return stack[-1].tag

def bad(mod, stack, msg):
    issues[mod].append(f"{ctx(stack)}: {msg}")

def split(v):
    return [s.strip() for s in re.split(r"[,]", v or "") if s.strip()]

# --- generic effect checks (items, blocks, buffs, progression, item_modifiers) ---
sounds = {e.get("name") for e in ET.parse(os.path.join(cfg, "sounds.xml")).getroot().iter("SoundDataNode") if e.get("name")}

with open(os.path.join(game, "7DaysToDie_Data", "StreamingAssets", "aa", "catalog.json"), encoding="utf-8", errors="replace") as f:
    assets = set(re.findall(r"Assets/AssetBundles/Automatic/([^\"\s]+?\.prefab)", f.read()))

def mesh_props(e, stack, mod):
    if e.tag == "property" and e.get("name") in ("Meshfile", "DropMeshfile", "HandMeshfile", "Model") and (e.get("value") or "").startswith("@:"):
        p = e.get("value")[2:]
        if p.endswith(".prefab") and p not in assets:
            bad(mod, stack, f"{e.get('name')} '{e.get('value')}' is not in the game's asset catalog")

def class_props(e, stack, mod):
    mesh_props(e, stack, mod)
    """Block/item/action Class names must map to a game type."""
    if e.tag != "property" or e.get("name") != "Class" or not e.get("value"):
        return
    v = e.get("value").split(",")[0].strip()
    parent = stack[-2] if len(stack) > 1 else None
    if parent is not None and parent.tag == "property" and (parent.get("class") or "").startswith("Action"):
        cands = ["ItemAction" + v, v]
    elif parent is not None and parent.tag == "block":
        cands = ["Block" + v, v]
    elif parent is not None and parent.tag == "item":
        cands = ["ItemClass" + v, v]
    else:
        return
    if not any(c in types for c in cands):
        bad(mod, stack, f"Class '{v}' has no matching game type ({cands[0]})")

def effects(e, stack, mod):
    class_props(e, stack, mod)
    for a in ("progression_name", "skill_name", "perk"):
        for v in split(e.get(a)):
            if v not in prog_names:
                bad(mod, stack, f"{e.tag} {a} '{v}' does not exist in progression.xml")
    if e.tag == "triggered_effect" and e.get("action") == "PlaySound" and e.get("sound") not in sounds:
        bad(mod, stack, f"sound '{e.get('sound')}' does not exist")
    if e.tag == "passive_effect":
        n = e.get("name")
        if n and n not in passives:
            bad(mod, stack, f"unknown passive_effect '{n}'")
    if e.tag == "triggered_effect":
        a = e.get("action")
        if a and ("MinEventAction" + a) not in types and a not in types:
            bad(mod, stack, f"unknown triggered_effect action '{a}'")
        for b in split(e.get("buff")):
            if b not in buffs:
                bad(mod, stack, f"triggered_effect buff '{b}' does not exist")
        if a in ("AddItems", "GiveItem", "RemoveItem") or e.get("item"):
            for it in split(e.get("items") or e.get("item")):
                if it not in itemlike:
                    bad(mod, stack, f"triggered_effect item '{it}' does not exist")
    if e.tag == "requirement":
        n = (e.get("name") or "").lstrip("!")
        if n and ("Requirement" + n) not in types and n not in types:
            bad(mod, stack, f"unknown requirement '{n}'")
        for b in split(e.get("buff")):
            if b not in buffs:
                bad(mod, stack, f"requirement buff '{b}' does not exist")
        if n in ("ProgressionLevel",) and e.get("progression_name") not in prog_names:
            bad(mod, stack, f"requirement progression '{e.get('progression_name')}' does not exist")

# --- items ---
item_el = {e.get("name"): e for e in X["items"].iter("item")}
def prop(e, n):
    for p in e.findall("property"):
        if p.get("name") == n:
            return p.get("value")
    return None
def eff_prop(e, n, seen=None):
    v = prop(e, n)
    if v is not None:
        return v
    ext = prop(e, "Extends")
    if ext and ext in item_el and ext != e.get("name"):
        return eff_prop(item_el[ext], n)
    return None

def check_item(e, stack, mod):
    effects(e, stack, mod)
    if e.tag == "item" and e.get("dmMod"):
        n = e.get("name")
        ext = prop(e, "Extends")
        if ext and ext not in items:
            bad(mod, stack, f"Extends '{ext}' does not exist")
        icon = eff_prop(e, "CustomIcon") or n
        if icon not in icons:
            bad(mod, stack, f"icon '{icon}' not found (vanilla ItemIcons or mod UIAtlases)")
        dt = eff_prop(e, "DisplayType")
        if dt and dt not in display_types:
            bad(mod, stack, f"DisplayType '{dt}' not in ui_display.xml")
        if n not in loc:
            bad(mod, stack, "no localization for name")
        dk = prop(e, "DescriptionKey") or (None if eff_prop(e, "DescriptionKey") else n + "Desc")
        if dk and dk not in loc:
            bad(mod, stack, f"no localization for description '{dk}'")
        inherited = eff_prop(e, "DescriptionKey") if not prop(e, "DescriptionKey") else None
        if inherited and (n + "Desc") in loc and loc[n + "Desc"][1] != "vanilla":
            bad(mod, stack, f"mod text '{n}Desc' is unused: DescriptionKey '{inherited}' is inherited via Extends")
        for pn in ("Unlocks",):
            for u in split(prop(e, pn)):
                if u not in itemlike and u not in prog_names:
                    bad(mod, stack, f"{pn} '{u}' is not an item/block/perk")
    if e.tag == "property" and e.get("name") in ("UnlockedBy",):
        for u in split(e.get("value")):
            if u not in prog_names and u not in items:
                bad(mod, stack, f"UnlockedBy '{u}' does not exist")
    if e.tag == "property" and e.get("name") == "Create_item":
        for u in split(e.get("value")):
            if u not in itemlike:
                bad(mod, stack, f"Create_item '{u}' does not exist")
walk(X["items"], check_item)
walk(X["blocks"], lambda e, s, m: (effects(e, s, m), e.tag == "block" and e.get("dmMod") and prop(e, "Extends") and prop(e, "Extends") not in blocks and bad(m, s, f"Extends '{prop(e, 'Extends')}' does not exist")))
walk(X["item_modifiers"], effects)
walk(X["progression"], effects)

def check_buff(e, stack, mod):
    effects(e, stack, mod)
    if e.tag == "buff" and e.get("dmMod"):
        n = e.get("name")
        for a in ("name_key", "description_key", "tooltip_key"):
            pass
walk(X["buffs"], check_buff)

# --- recipes ---
def check_recipe(e, stack, mod):
    if e.tag == "recipe":
        if e.get("name") not in itemlike:
            bad(mod, stack, "recipe output does not exist")
        ca = e.get("craft_area")
        if ca and ca not in workstations:
            bad(mod, stack, f"craft_area '{ca}' is not a block")
        ct = e.get("craft_tool")
        if ct and ct not in items:
            bad(mod, stack, f"craft_tool '{ct}' does not exist")
    if e.tag == "ingredient" and e.get("name") not in itemlike:
        bad(mod, stack, f"ingredient '{e.get('name')}' does not exist")
    effects(e, stack, mod)
walk(X["recipes"], check_recipe)

# --- loot ---
def check_loot(e, stack, mod):
    if e.tag == "item":
        if e.get("name") and e.get("name") not in itemlike:
            bad(mod, stack, f"loot item '{e.get('name')}' does not exist")
        if e.get("group") and e.get("group") not in lootgroups:
            bad(mod, stack, f"loot group '{e.get('group')}' does not exist")
        pt = e.get("loot_prob_template")
        if pt and pt not in prob_t:
            bad(mod, stack, f"loot_prob_template '{pt}' does not exist")
    if e.tag == "lootgroup":
        qt = e.get("loot_quality_template")
        if qt and qt not in qual_t:
            bad(mod, stack, f"loot_quality_template '{qt}' does not exist")
walk(X["loot"], check_loot)

# --- traders ---
def check_trader(e, stack, mod):
    if e.tag == "item":
        if e.get("name") and e.get("name") not in itemlike:
            bad(mod, stack, f"trader item '{e.get('name')}' does not exist")
        if e.get("group") and e.get("group") not in trader_groups:
            bad(mod, stack, f"trader group '{e.get('group')}' does not exist")
walk(X["traders"], check_trader)

# --- quests ---
def check_quest(e, stack, mod):
    if e.tag == "objective":
        t = (e.get("type") or "").split(",")[0].strip()
        if "," not in (e.get("type") or "") and ("Objective" + t) not in types and t not in types:
            bad(mod, stack, f"unknown objective type '{t}'")
        for p in e.findall("property"):
            if p.get("name") in ("PrefabName", "PrefabNames"):
                for poi in split(p.get("value")):
                    if poi not in pois:
                        bad(mod, stack, f"POI '{poi}' not in Data/Prefabs/POIs")
    if e.tag == "reward":
        t = e.get("type")
        if t and ("Reward" + t) not in types:
            bad(mod, stack, f"unknown reward type '{t}'")
        if t == "Item" and e.get("id") not in itemlike:
            bad(mod, stack, f"reward item '{e.get('id')}' does not exist")
        if t == "LootItem":
            for g in split(e.get("id")):
                if g not in lootgroups:
                    bad(mod, stack, f"reward loot group '{g}' does not exist")
    if e.tag == "action":
        t = e.get("type")
        if t and ("QuestAction" + t) not in types:
            bad(mod, stack, f"unknown quest action '{t}'")
        if t == "SpawnEnemy":
            for ent in split(e.get("id")):
                if ent not in entity_classes:
                    bad(mod, stack, f"SpawnEnemy entity '{ent}' does not exist")
    if e.tag == "requirement" and stack[-2].tag == "quest":
        t = e.get("type")
        if t and ("QuestRequirement" + t) not in types and ("Requirement" + t) not in types:
            bad(mod, stack, f"unknown quest requirement '{t}'")
    if e.tag == "quest" and e.get("dmMod"):
        q = e.get("id")
        for key in ("name_key", "subtitle_key", "description_key", "offer_key", "statustext_key", "group_name_key"):
            for p in e.findall("property"):
                if p.get("name") == key and p.get("value") not in loc:
                    bad(mod, stack, f"no localization for {key} '{p.get('value')}'")
    if e.tag == "quest" and e.get("dmMod") is None and stack[-2].tag == "quest_list":
        pass
    if e.tag == "quest" and len(stack) > 1 and stack[-2].tag == "quest_list" and e.get("id") not in quests:
        bad(mod, stack, f"quest_list entry '{e.get('id')}' is not a defined quest")
walk(X["quests"], check_quest)

# --- duplicate definitions (a mod re-adding something vanilla or another mod already defines) ---
for fname, tag, attr in (("items", "item", "name"), ("blocks", "block", "name"), ("buffs", "buff", "name"),
                         ("loot", "lootgroup", "name"), ("quests", "quest", "id"), ("item_modifiers", "item_modifier", "name")):
    seen_def = {}
    for e in X[fname].iter(tag):
        n = e.get(attr)
        if not n or (tag == "quest" and not len(e)):
            continue
        if n in seen_def and e.get("dmMod"):
            issues[e.get("dmMod")].append(f"{tag} {n}: DUPLICATE definition (already defined by {seen_def[n] or 'vanilla'})")
        seen_def.setdefault(n, e.get("dmMod"))
for e in X["recipes"].iter("recipe"):
    pass

total = 0
for mod in sorted(issues):
    seen = {}
    for i in issues[mod]:
        seen[i] = seen.get(i, 0) + 1
    print(f"===== {mod}: {len(issues[mod])} issue(s), {len(seen)} unique")
    for i, c in seen.items():
        print(("  " if c == 1 else f"  x{c} ") + i)
    total += len(issues[mod])
print("TOTAL", total)
