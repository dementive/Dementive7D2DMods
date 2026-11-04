"""Generate the StationsExpanded mod's Config and icons from the STATIONS, COLLECTORS and TOOLS tables below.

Usage: python gen_stations.py <game dir> <StationsExpanded dir>
Every named item Extends its vanilla station, collector or tool, so it keeps the vanilla model, recipes, window, tool
slots and fuel. Station and tool bonuses are block/item properties that the mod's DLL reads (StationBonusDEM,
StationToolDEM); collector bonuses are the vanilla collector settings themselves. Item effect groups aren't inherited
through Extends, so each named tool carries copies of its vanilla tool's. Rewrites Config/blocks.xml, items.xml,
ui_display.xml, loot.xml, traders.xml and Localization.csv, and paints the vanilla icons into UIAtlases/ItemIconAtlas
with Scripts/bin/IconTool.exe (ICONS).
"""
import os
import re
import subprocess
import sys

game, mod = sys.argv[1:3]
cfg_dir = os.path.join(game, "Data", "Config")
icon_tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "IconTool.exe")

REPAIR = "\\n\\nFound, not crafted."

# Workstations: their bonuses are block properties read by StationBonusDEM
STATIONS = [
    dict(name="DementiveStationWorkbench", parent="workbench", title="Grandpa's Workbench", value=6000,
         bonus={"StationCraftTime": "0.8", "StationQualityChance": "0.1"},
         desc="A heavy old workbench, built by hand and used for fifty years. It works like a workbench, but crafts "
              "20% faster, and a weapon, tool or armor piece made on it has a 10% chance to come out one quality "
              "higher."),
    dict(name="DementiveStationForge", parent="forge", title="Old Smoky", value=6000,
         bonus={"StationSmeltSpeed": "1.5", "StationFuelTime": "1.25"},
         desc="A blackened, patched-up forge that draws like a chimney. It works like a forge, but smelts 50% faster, "
              "and its fuel lasts 25% longer."),
    dict(name="DementiveStationChemistry", parent="chemistryStation", title="Doc's Lab", value=8000,
         bonus={"StationCraftTime": "0.8", "StationExtraChance": "0.15"},
         desc="A chemistry station kept spotless by someone who knew what they were doing. It works like a chemistry "
              "station, but crafts 20% faster, and each craft has a 15% chance to come out twice."),
    dict(name="DementiveStationCementMixer", parent="cementMixer", title="Big Tumbler", value=5000,
         bonus={"StationCraftTime": "0.5", "StationExtraChance": "0.1"},
         desc="An oversized contractor's cement mixer. It works like a cement mixer, but mixes twice as fast, and "
              "each batch has a 10% chance to come out twice."),
    dict(name="DementiveStationCampfire", parent="campfire", title="Grandma's Hearth", value=3000,
         bonus={"StationCraftTime": "0.75", "StationFuelTime": "2", "StationExtraChance": "0.1"},
         desc="A stone hearth that holds its heat like nothing else. It works like a campfire, but cooks 25% faster, "
              "its fuel lasts twice as long, and each dish has a 10% chance to come out twice."),
]

# Collectors: the vanilla collector settings, changed. OutputTypes fields: name, fuel, fuel cost, extra fuel cost,
# fuel divisor with a Cost mod, output, output with a Type mod, speed multiplier with a Speed mod, count multiplier
# with a Count mod, min and max fill time (1000 = 1 game hour), sound.
COLLECTORS = [
    dict(name="DementiveStationDewCollector", parent="cntDewCollector", title="Rain Catcher", value=3000,
         props={"OutputTypes": "{water,jar,1,1,1,drinkJarRiverWater,drinkJarBoiledWater,2,3,4000,7000,collector_complete_item}"},
         desc="A dew collector with a wide funnel and a cleaner catch. It works like a dew collector, but fills a "
              "jar in 4 to 7 hours (instead of 6 to 10), and with a tarp each fill gives 3 jars instead of 2."),
    dict(name="DementiveStationApiary", parent="cntApiary", title="Queen's Court", value=3000,
         props={"OutputTypes": "{honey,flower,10,0,2,foodHoney,foodHoney,2,2,32000,32000,apiary_complete_item}",
                "ModTypes": "Speed,Count,Cost"},
         desc="A hive with an unusually strong queen. It works like an apiary, but makes honey every 32 hours "
              "(instead of 48), and its smoker slot works: a smoker halves the flowers each honey takes."),
    dict(name="DementiveStationChickenCoop", parent="cntChickenCoop", title="Henhouse Deluxe", value=3000,
         props={"OutputTypes": "{egg,feed,2,2,2,foodEgg,foodEgg,2,2,16000,16000,coop_eggs_complete}"
                               "{feather,feed,2,2,2,resourceFeather,resourceFeather,2,2,16000,16000,coop_feathers_complete}"
                               "{chicken,feed,30,0,2,domesticatedChicken,domesticatedChicken,2,1,72000,72000,coop_chicken_complete}",
                "CatalystMultiplier": "egg=3,feather=5,chicken=0"},
         desc="A roomy coop with warm nesting boxes. It works like a chicken coop, but hens lay and moult every 16 "
              "hours (instead of 24), and each hen lays 3 eggs instead of 2."),
]

# Tools: StationToolDEM properties (they stand in for StationToolBase in its slot and for its recipes) plus extra
# effect groups. "copy" lists which vanilla effect groups to keep (by index); "groups" are added after them.
BELLOWS_SMELT = "-.46,-.57,-.67,-.75,-.82,-.89"  # twice the vanilla bellows' speed gain at each quality
TOOLS = [
    dict(name="DementiveStationToolAnvil", parent="toolAnvil", title="Old Ironsides", value=2500,
         # A chance to come out twice instead of an iron discount: ingredient bonuses round down per craft, so -10%
         # made one-iron recipes (nails) free
         props={"StationToolCraftTime": "0.75", "StationToolExtraChance": "0.1", "StationToolScope": "all"},
         desc="A battle-scarred anvil that's outlived three blacksmiths. Everything it does as an anvil, and "
              "everything made at its forge is another 25% faster, with a 10% chance to come out twice."),
    dict(name="DementiveStationToolBellows", parent="toolBellows", title="Big Lung", value=3000, copy=[0],
         groups=["""<effect_group>
				<passive_effect name="CraftingSmeltTime" operation="perc_add" value="%s" tier="1,2,3,4,5,6"/>
				<display_value name="dCraftingSmeltTime" value="%s" tier="1,2,3,4,5,6"/>
			</effect_group>""" % (BELLOWS_SMELT, BELLOWS_SMELT)],
         desc="A huge leather bellows that pumps like a blacksmith's dream. It speeds up smelting twice as much as a "
              "vanilla bellows of the same quality."),
    dict(name="DementiveStationToolCrucible", parent="toolForgeCrucible", title="The Hellpot", value=12000,
         props={"StationToolCraftTime": "0.75", "StationToolExtraChance": "0.15"},
         desc="A thick, glowing-hot crucible. It works like a crucible, but everything that needs one (forged "
              "steel and the like) is made 25% faster, and each craft has a 15% chance to come out twice."),
    dict(name="DementiveStationToolCookingPot", parent="toolCookingPot", title="Grandma's Stockpot", value=1500,
         props={"StationToolCraftTime": "0.75", "StationToolExtraChance": "0.1"},
         desc="A dented enamel stockpot that's made ten thousand meals. Everything it does as a cooking pot, and "
              "pot recipes are another 25% faster, with a 10% chance of a second serving."),
    dict(name="DementiveStationToolCookingGrill", parent="toolCookingGrill", title="Pitmaster's Grill", value=1500,
         props={"StationToolCraftTime": "0.75", "StationToolExtraChance": "0.15"},
         desc="A heavy cast-iron grill, seasoned black. Everything it does as a grill, and grill recipes are another "
              "25% faster, with a 15% chance of a second serving."),
    dict(name="DementiveStationToolBeaker", parent="toolBeaker", title="Doc's Beaker", value=2000,
         props={"StationToolCraftTime": "0.75", "StationToolExtraChance": "0.15", "Stacknumber": "1"},
         desc="A heavy lab beaker with faded measuring marks. It works like a beaker, but beaker recipes (medicine, "
              "paper and the like) are made 25% faster, with a 15% chance to come out twice."),
]

# Text the DLL shows: the status line under a station's use prompt (StationStatusDEM; {0} {1} {2} are filled in by
# the code) and the message when crafting from storage fails (StorageCraftingDEM)
UI_TEXT = [
    ("DementiveStationStatusIdle", "Idle"),
    ("DementiveStationStatusCrafting", "Making {0} x{1}, next one in {2}"),
    ("DementiveStationStatusCraftingPaused", "Making {0} x{1}"),
    ("DementiveStationStatusInUse", "Making {0} (someone is using it)"),
    ("DementiveStationStatusMore", "{0} (+{1} more in the queue)"),
    ("DementiveStationStatusFuel", "Fuel: {0} left"),
    ("DementiveStationStatusFuelOff", "Fuel: {0} left (fire is out)"),
    ("DementiveStationStatusNoFuel", "Out of fuel"),
    ("DementiveStorageCraftFailed", "Couldn't take the items from nearby storage. Someone may be using it."),
]

# Icon recipes for IconTool.exe fx (see the ops in Scripts/WeaponsExpanded/IconTool.cs), painted over the vanilla
# icons in the style of the hand-made Weapons Expanded icons.
ICONS = {
    # Warmed toward old oiled hardwood (lightly, so the bench's clutter still reads) with an heirloom golden glow
    "DementiveStationWorkbench": ["adjust:sat=1.1,bright=1.05,contrast=1.1", "map:#200c02,#9a5a24,#ffe6b8,0.35",
                                  "rim:#ffd890,2,0.5", "glow:#ffd070,9,0.75,noise=12", "sparkle:#ffffff,4,12,6"],
    # Soot-black with a roaring fire inside
    "DementiveStationForge": ["map:#0a0604,#4a3020,#d8b090,0.45", "emissive:#ff7020,0.72,0.9", "embers:#ffa040,12,1.6,4",
                              "glow:#ff6a20,8,0.65,noise=10"],
    "DementiveStationChemistry": ["map:#02121a,#1a7a8a,#c8f8ff,0.4", "pattern:speckle,c1=#9ff0ff,scale=4,amount=0.75,op=0.45,seed=3,bloom=0.4",
                                  "glow:#40e0d0,8,0.65", "sparkle:#e0ffff,4,10,3"],
    "DementiveStationCementMixer": ["map:#1a0800,#ff8c1a,#ffe0b0,0.5", "pattern:hazard,c1=#111111,c2=#ffcc00,scale=8,op=0.8,zone=90/0.4/0.45/0.6/0.65",
                                    "sheen:0.4", "rim:#ffd080,2,0.5", "trail:#ffb050,0,3,6,0.4"],
    "DementiveStationCampfire": ["adjust:sat=1.15,bright=1.05", "emissive:#ff8030,0.68,0.95", "embers:#ffb050,14,1.6,7",
                                 "glow:#ff9040,9,0.75,noise=10"],
    "DementiveStationDewCollector": ["map:#020a18,#2a6ab0,#d0ecff,0.45", "pattern:speckle,c1=#a0d8ff,scale=4,amount=0.72,op=0.5,seed=3,bloom=0.4",
                                     "glow:#60b0ff,8,0.65", "sparkle:#ffffff,4,10,2"],
    "DementiveStationApiary": ["map:#2a1400,#e0a020,#fff0b0,0.5", "pattern:speckle,c1=#ffd040,scale=5,amount=0.72,op=0.5,seed=5",
                               "glow:#ffc020,8,0.7", "sparkle:#fff6c0,4,10,6"],
    "DementiveStationChickenCoop": ["map:#100402,#6a1a10,#e8d0b0,0.7", "pattern:woodgrain,c1=#a03020,c2=#2a0604,scale=5,angle=0,op=0.35",
                                    "sheen:0.2", "rim:#ffe8b0,2,0.6", "glow:#ffd890,8,0.6", "sparkle:#fff6d0,4,10,8"],
    "DementiveStationToolAnvil": ["map:#050608,#3a3e48,#d0d8e8", "sheen:0.75", "pattern:cracks,c1=#ffb060,scale=14,op=0.5,width=0.04,seed=6,bloom=0.4",
                                  "rim:#ffd890,2,0.5", "sparkle:#ffffff,3,10,4"],
    "DementiveStationToolBellows": ["map:#140802,#7a3a14,#ffc890,0.6", "trail:#ffa040,180,3,6,0.5", "embers:#ffb040,8,1.4,5",
                                    "glow:#ff8030,6,0.5"],
    "DementiveStationToolCrucible": ["map:#1a0200,#c02800,#ffd060,0.7", "pattern:cracks,c1=#ffef9a,scale=14,op=0.8,bloom=0.6,width=0.05,seed=4",
                                     "emissive:#ff8020,0.8,0.9", "embers:#ffb040,10,1.6,6"],
    "DementiveStationToolCookingPot": ["map:#020818,#2a50a8,#d8e8ff,0.6", "pattern:speckle,c1=#ffffff,scale=4,amount=0.72,op=0.7,seed=2",
                                       "sheen:0.4", "glow:#ffd090,6,0.45"],
    "DementiveStationToolCookingGrill": ["map:#050505,#2e2e2e,#c8c8c8,0.7", "pattern:flames,c1=#ff5a00,c2=#ffd000,scale=8,op=1,bloom=0.6",
                                         "embers:#ffb040,12,1.5,3", "glow:#ff6a10,7,0.6"],
    "DementiveStationToolBeaker": ["map:#021a06,#20a040,#d0ffd8,0.4", "emissive:#80ff80,0.75,0.8", "glow:#50ff70,8,0.7",
                                   "sparkle:#f0fff0,3,10,2"],
}

# Vanilla blocks without a crafting area of their own use their block name, so a variant must name the vanilla area
CRAFTING_AREAS = {"campfire": "campfire", "chemistryStation": "chemistryStation", "cementMixer": "cementMixer"}

van_blocks = re.sub(r"<!--.*?-->", "", open(os.path.join(cfg_dir, "blocks.xml"), encoding="utf-8").read(), flags=re.S)
van_items = re.sub(r"<!--.*?-->", "", open(os.path.join(cfg_dir, "items.xml"), encoding="utf-8").read(), flags=re.S)
van_ui = open(os.path.join(cfg_dir, "ui_display.xml"), encoding="utf-8").read()


def van_block(name):
    m = re.search(r'<block name="%s">(.*?)\n</block>' % re.escape(name), van_blocks, re.S)
    if not m:
        raise SystemExit("vanilla block not found: " + name)
    return m.group(1)


def van_prop(name, prop):
    m = re.search(r'<property name="%s" value="([^"]*)"' % prop, van_block(name))
    return m.group(1) if m else None


def van_item_groups(name):
    m = re.search(r'<item name="%s">(.*?)\n</item>' % re.escape(name), van_items, re.S)
    if not m:
        raise SystemExit("vanilla item not found: " + name)
    groups = re.findall(r"<effect_group\b.*?</effect_group>", m.group(1), re.S)
    # Re-indent to the mod's item children (3 tabs)
    out = []
    for g in groups:
        lines = [l.strip() for l in g.split("\n") if l.strip()]
        depth, text = 0, []
        for l in lines:
            if l.startswith("</"):
                depth -= 1
            text.append("\t" * (3 + depth) + l)
            if re.match(r"<[a-z_]+[^/]*[^/]>$", l) and not l.startswith("</"):
                depth += 1
        out.append("\n".join(text))
    return out


def prop(key, value):
    return '\t\t\t<property name="%s" value="%s" />' % (key, value)


def blocks_xml():
    out = ["<configs>", '\t<append xpath="/blocks">',
           "\t\t<!-- Generated by Scripts/StationsExpanded/gen_stations.py. Every named station extends its vanilla station,",
           "\t\t     so it keeps the same model, recipes, window, tool slots and fuel. It must name the vanilla window",
           "\t\t     (WorkstationWindow) and must not set WorkstationName, which would replace the vanilla station's",
           "\t\t     crafting data. Its bonuses are read by StationBonusDEM: StationCraftTime multiplies crafting time,",
           "\t\t     StationQualityChance is the chance a finished item with quality comes out one level higher,",
           "\t\t     StationExtraChance the chance a craft comes out twice, StationFuelTime multiplies how long fuel",
           "\t\t     burns and StationSmeltSpeed how fast it smelts. Named collectors change the vanilla collector",
           "\t\t     settings. Everything here is found, not crafted, so it doesn't inherit the vanilla unlock or trader",
           "\t\t     stage (rare stock from trader stage 50). -->"]
    for s in STATIONS + COLLECTORS:
        parent = s["parent"]
        out += ['\t\t<block name="%s">' % s["name"],
                '\t\t\t<property name="Extends" value="%s" param1="UnlockedBy,TraderStageTemplate" />' % parent,
                prop("CreativeMode", "Player"), prop("CustomIcon", s["name"]), prop("DescriptionKey", s["name"] + "Desc"),
                prop("EconomicValue", s["value"]), prop("TraderStageTemplate", "baseTier2")]
        if s in STATIONS:
            out.append(prop("WorkstationWindow", "workstation_" + parent))
            if parent in CRAFTING_AREAS and not van_prop(parent, "CraftingAreaRecipes"):
                out += ['\t\t\t<property class="Workstation">',
                        '\t\t\t\t<property name="CraftingAreaRecipes" value="%s" />' % CRAFTING_AREAS[parent],
                        "\t\t\t</property>"]
            out += [prop(k, v) for k, v in s["bonus"].items()]
        else:
            out += [prop(k, v) for k, v in s["props"].items()]
        out.append("\t\t</block>")
    out += ["\t</append>", "</configs>"]
    return "\n".join(out) + "\n"


def items_xml():
    out = ["<configs>", '\t<append xpath="/items">',
           "\t\t<!-- Named station tools (generated by Scripts/StationsExpanded/gen_stations.py). Each extends its vanilla",
           "\t\t     tool and carries copies of its effect groups (they aren't inherited). StationToolBase lets it go in",
           "\t\t     that tool's slot and count for its recipes; StationToolCraftTime and StationToolExtraChance apply to",
           "\t\t     the recipes that need the vanilla tool (all recipes at the station with StationToolScope all) while",
           "\t\t     it sits in the station. -->"]
    for t in TOOLS:
        groups = van_item_groups(t["parent"])
        keep = t.get("copy", range(len(groups)))
        out += ['\t\t<item name="%s">' % t["name"],
                '\t\t\t<property name="Extends" value="%s" param1="UnlockedBy,TraderStageTemplate" />' % t["parent"],
                prop("CreativeMode", "Player"), prop("CustomIcon", t["name"]), prop("DescriptionKey", t["name"] + "Desc"),
                prop("EconomicValue", t["value"]), prop("SellableToTrader", "true"), prop("TraderStageTemplate", "baseTier2"),
                prop("StationToolBase", t["parent"])]
        out += [prop(k, v) for k, v in t.get("props", {}).items()]
        out += [groups[i] for i in keep]
        out += ["\t\t\t" + g for g in t.get("groups", [])]
        out.append("\t\t</item>")
    out += ["\t</append>", "</configs>"]
    return "\n".join(out) + "\n"


def ui_display_xml():
    """A station window picks its recipe tabs by the station's block name, so each named station repeats the tabs of
    the vanilla station it extends."""
    out = ["<configs>", '\t<append xpath="/ui_display_info/crafting_category_display">']
    for s in STATIONS:
        m = re.search(r'<crafting_category_list display_type="%s">(.*?)</crafting_category_list>' % s["parent"], van_ui,
                      re.S)
        if not m:
            raise SystemExit("no crafting tabs for " + s["parent"])
        tabs = re.findall(r"<crafting_category [^>]*/>", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S))
        out.append('\t\t<crafting_category_list display_type="%s">' % s["name"])
        out += ["\t\t\t" + t for t in tabs]
        out.append("\t\t</crafting_category_list>")
    out += ["\t</append>", "</configs>"]
    return "\n".join(out) + "\n"


ALL = STATIONS + COLLECTORS + TOOLS


def loot_xml():
    """The same places and odds as the named tools (Tools Expanded), as one pool of all 14."""
    items = "\n".join('\t\t\t<item name="%s"%s/>' % (x["name"], ' quality="1,6"' if x in TOOLS and x["parent"] in
                      ("toolAnvil", "toolBellows", "toolCookingPot", "toolCookingGrill") else "") for x in ALL)
    places = [("groupSmallSafeLoot", "T2", "Wall and picture safes"), ("groupReinforcedChestT3", "T3", "Locked Iron Chest"),
              ("groupHardenedChestT4", "T4", "Locked Small Hardened Chest"),
              ("groupHardenedChestT5", "T5", "Locked Large Hardened Chest"), ("groupZpackBoss", "T3", None),
              ("groupZpackStrong", "T2", None), ("groupZpackReg", "T1", None), ("groupHiddenStash", "T2", None),
              ("groupBuriedTreasure", "T3", None)]
    out = ["<Dementive>", "",
           '\t<append xpath="/lootcontainers/lootprobtemplates">',
           "\t\t<!-- Chance per container opened that one named station, collector or tool drops -->"]
    for tier, prob, note in [("T1", "0.005", "1 / 200"), ("T2", "0.01", "1 / 100"), ("T3", "0.02", "1 / 50"),
                             ("T4", "0.04", "1 / 25"), ("T5", "0.05", "1 / 20")]:
        out += ['\t\t<lootprobtemplate name="DementiveStationRares%s">' % tier,
                '\t\t\t<loot level="1,999999" prob="%s"/>  <!-- %s -->' % (prob, note), "\t\t</lootprobtemplate>"]
    out += ["", "\t\t<!-- Quest rewards: the reward \"value\" is the quest tier. At tiers 4-6 about 1 in 20 quests offer one",
            "\t\t     instead of a schematic -->",
            '\t\t<lootprobtemplate name="DementiveStationQuestRewards">',
            '\t\t\t<loot level="0,3" prob="0"/>', '\t\t\t<loot level="4,7" prob="0.06"/>', "\t\t</lootprobtemplate>",
            "\t</append>", "",
            "\t<insertBefore xpath=\"/lootcontainers/lootgroup[@name='groupScrapCommon']\">",
            '\t\t<lootgroup name="groupDementiveStationsAll" count="1" loot_quality_template="qualBaseTemplate">',
            items, "\t\t</lootgroup>", "\t</insertBefore>", ""]
    for group, tier, note in places:
        if note:
            out.append("\t<!-- %s -->" % note)
        out += ["\t<append xpath=\"//lootgroup[@name='%s']\">" % group,
                '\t\t<item group="groupDementiveStationsAll" loot_prob_template="DementiveStationRares%s" force_prob="true"/>'
                % tier, "\t</append>"]
    out += ["", "\t<append xpath=\"/lootcontainers/lootgroup[@name='groupQuestSchematics']\">",
            '\t\t<item group="groupDementiveStationsAll" loot_prob_template="DementiveStationQuestRewards"/>',
            "\t</append>", "", "</Dementive>"]
    return "\n".join(out) + "\n"


def traders_xml():
    def group(name, members):
        return (['\t\t<trader_item_group name="%s" count="1">' % name]
                + ['\t\t\t<item name="%s"%s/>' % (x["name"], ' quality="1,6"' if x["parent"] in
                   ("toolAnvil", "toolBellows", "toolCookingPot", "toolCookingGrill") else "") for x in members]
                + ["\t\t</trader_item_group>"])
    out = ["<Dementive>", "",
           "\t<!-- Traders can stock them: a small-weight entry in the vanilla workstation and tool groups that traders",
           "\t     restock from, from trader stage 50 (TraderStageTemplate baseTier2 on each). The game only lets a group",
           "\t     use groups defined above it, so these go before 'tools' (the first of the two). -->",
           "\t<insertBefore xpath=\"/traders/trader_item_groups/trader_item_group[@name='tools']\">"]
    out += group("groupDementiveTraderStations", STATIONS + COLLECTORS)
    out += group("groupDementiveTraderStationTools", TOOLS)
    out += ["\t</insertBefore>", "",
            "\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='workstations']\">",
            '\t\t<item group="groupDementiveTraderStations" prob="0.055"/>', "\t</append>", "",
            "\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='tools']\">",
            '\t\t<item group="groupDementiveTraderStationTools" prob="0.055"/>', "\t</append>", "", "</Dementive>"]
    return "\n".join(out) + "\n"


def csv_field(text):
    return '"%s"' % text.replace('"', '""') if any(c in text for c in ',"') else text


def localization():
    rows = ["Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,"
            "french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"]
    for x in ALL:
        kind = ("blocks", "Workstation") if x not in TOOLS else ("items", "Item")
        rows.append("%s,%s,%s,,,,%s%s" % (x["name"], kind[0], kind[1], csv_field(x["title"]), "," * 13))
        rows.append("%sDesc,%s,%s,,,,%s%s" % (x["name"], kind[0], kind[1], csv_field(x["desc"] + REPAIR), "," * 13))
    for key, text in UI_TEXT:
        rows.append("%s,UI,HUD,,,,%s%s" % (key, csv_field(text), "," * 13))
    return "\n".join(rows) + "\n"


def write(rel, text):
    path = os.path.join(mod, "Config", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", path)


write("blocks.xml", blocks_xml())
write("items.xml", items_xml())
write("ui_display.xml", ui_display_xml())
write("loot.xml", loot_xml())
write("traders.xml", traders_xml())
write("Localization.csv", localization())

atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
os.makedirs(atlas, exist_ok=True)
icon_dir = os.path.join(game, "Data", "ItemIcons")
for x in ALL:
    base = x["parent"]
    if x not in TOOLS:
        base = van_prop(base, "CustomIcon") or base
    subprocess.run([icon_tool, "fx", os.path.join(icon_dir, base + ".png"), os.path.join(atlas, x["name"] + ".png"),
                    *ICONS[x["name"]]], check=True)
print(f"{len(ALL)} icons written to {atlas}")
