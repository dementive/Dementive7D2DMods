"""Generate the ToolsExpanded mod (and its server-side copy) from the TOOLS table below.

Usage: python gen_tools.py <game dir> <ToolsExpanded dir> [<ToolsExpanded-SERVERSIDE dir>]
Each named tool Extends a vanilla tool and carries copies of its <stats>, effect groups and any action it changes
(those are not inherited), with +20% block damage, +50% durability and a signature effect group. Rewrites
Config/items.xml, item_modifiers.xml, blocks.xml, entityclasses.xml, buffs.xml, loot.xml, traders.xml and
Localization.csv, and paints the vanilla icons into UIAtlases/ItemIconAtlas with Scripts/bin/IconTool.exe (ICONS).
The server-side copy uses the vanilla icons with a color tint instead, since its clients don't have the icons.

Everything is XML, so both copies behave the same. Harvest bonuses use the game's own harvest tags: a drop is only
collected when the held tool's HarvestCount for one of the drop's tags is above 0 (like the Lucky Strike book).
"""
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

game, mod = sys.argv[1:3]
server = sys.argv[3] if len(sys.argv) > 3 else None
cfg_dir = os.path.join(game, "Data", "Config")
van = open(os.path.join(cfg_dir, "items.xml"), encoding="utf-8").read()
# Comments dropped: vanilla keeps commented-out copies of some blocks, which would be read as the real ones
van_blocks = re.sub(r"<!--.*?-->", "", open(os.path.join(cfg_dir, "blocks.xml"), encoding="utf-8").read(), flags=re.S)
icon_tool = os.path.join(os.path.dirname(__file__), "..", "bin", "IconTool.exe")

BLOCK_BOOST = 1.2       # block damage compared to the vanilla tool
DURABILITY_BOOST = 1.5  # DegradationMax compared to the vanilla tool

# Harvest tags this mod adds. The player starts at 0 for each (entityclasses.xml) and only the matching tool sets 1
PROSPECTOR, LUCKY_SPADE, PIT_CREW = "DementiveProspectorHarvest", "DementiveLuckySpadeHarvest", "DementivePitCrewHarvest"
# Extra tags added to existing salvage drops, so a tool can boost just those drops
CAR_SALVAGE, CAR_RARE, TINKER = "DementiveCarSalvage", "DementiveCarRareSalvage", "DementiveTinkerSalvage"
TREE_TAG = "DementiveTree"


def eg(name, body):
    """A signature effect group, written with the mod's indentation (item children at 3 tabs)."""
    lines = body.strip("\n").split("\n")
    return f'\t\t\t<effect_group name="{name}" tiered="false">\n' + "\n".join("\t\t\t\t" + l for l in lines) + "\n\t\t\t</effect_group>"


TOOLS = [
    dict(
        name="DementiveToolGrandpasHatchet", title="Grandpa's Hatchet", parent="meleeToolRepairT0StoneAxe", rare=False,
        tint="#8B5A2B",
        # Tagged like the vanilla value: untagged, it would also slow the wear on the player's armor while held
        signature="""
<passive_effect name="DegradationPerUse" operation="perc_add" value="-.75" tags="perkMiner69r"/>
<passive_effect name="DamageModifier" operation="perc_add" value=".25" tags="wood"/>
<passive_effect name="DamageModifier" operation="perc_add" value=".25" tags="earth"/>
<passive_effect name="DamageModifier" operation="perc_add" value=".25" tags="stone"/>""",
        lore="A stone hatchet lashed together by somebody's grandpa, back when things were built to last. It still is.",
        ability="Wears out 75% slower. +25% damage to wood, earth and stone.",
    ),
    dict(
        name="DementiveToolContractor", title="The Contractor", parent="meleeToolRepairT1ClawHammer", rare=False,
        tint="#FFB300",
        # Repair speed and upgrade hits are fixed action properties, not passive effects
        actions={"Action1": [(r'(name="Delay" value=")\.64"', r'\g<1>.49"'),
                             (r'(name="Repair_amount" value=")400"', r'\g<1>520"'),
                             (r'(name="Upgrade_hit_offset" value=")-2"', r'\g<1>-3"')]},
        edits=[(r'(name="dBlockRepairAmount" value=")400"', r'\g<1>520"')],
        signature="""
<passive_effect name="PlayerExpGain" operation="perc_add" value=".5" tags="Upgrading,Repairing"/>""",
        lore="A framing hammer with a contractor's name burned into the handle. It's put up more houses than anyone left alive.",
        ability="Repairs and upgrades 30% faster. +50% XP from repairing and upgrading.",
    ),
    dict(
        name="DementiveToolNightShift", title="Night Shift", parent="meleeToolRepairT3Nailgun", rare=True,
        tint="#B22222",
        actions={"Action1": [(r'(name="Repair_amount" value=")1000"', r'\g<1>2000"')]},
        edits=[(r'(name="dBlockRepairAmount" value=")1000"', r'\g<1>2000"')],
        # IsBloodMoon is true from 4 hours before dusk to 2 hours after dawn on a Blood Moon day
        signature="""
<requirement name="IsBloodMoon"/>
<passive_effect name="GeneralDamageResist" operation="base_add" value=".25"/>""",
        lore="A nail gun that's held more walls together on Blood Moon nights than anyone can count. Someone painted a tally of them down the side.",
        ability="Repairs twice as much per hit. On Blood Moon nights you take 25% less damage while holding it.",
    ),
    dict(
        name="DementiveToolWidowmaker", title="Widowmaker", parent="meleeToolAxeT1IronFireaxe", rare=False,
        tint="#2E8B57",
        signature=f"""
<passive_effect name="DamageModifier" operation="perc_add" value=".5" tags="{TREE_TAG}"/>
<passive_effect name="HarvestCount" operation="base_set" value="1" tags="WasteTreasuresHoneyHarvest"/>
<passive_effect name="HarvestCount" operation="perc_add" value="1" tags="WasteTreasuresHoneyHarvest"/>""",
        lore="Loggers call a loose branch that falls without warning a widowmaker. This axe brings the whole tree down instead.",
        ability="+50% damage to trees. Trees can drop honey like with the Waste Treasures book, and twice as much.",
    ),
    dict(
        name="DementiveToolChopper", title="Chopper", parent="meleeToolAxeT2SteelAxe", rare=True,
        tint="#C0C0C0",
        signature="""
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveToolsChopper">
	<requirement name="IsSecondaryAttack"/>
	<requirement name="EntityTagCompare" target="other" tags="zombie"/>
</triggered_effect>""",
        lore="A steel axe with a notch in the handle for every zombie it's split in two. Once it gets going, it doesn't want to stop.",
        ability="Killing a zombie with a power attack makes your axe swing 50% faster and cost no stamina for 5 seconds.",
    ),
    dict(
        name="DementiveToolMeatGrinder", title="Meat Grinder", parent="meleeToolAxeT3Chainsaw", rare=True,
        tint="#8B0000",
        edits=[(r'(name="MagazineSize" operation="base_set" value=")300"', r'\g<1>600"')],
        # The vanilla chainsaw already adds 1 to dismember chance, so more of it would do nothing
        signature="""
<requirement name="EntityTagCompare" target="other" tags="zombie"/>
<passive_effect name="EntityDamage" operation="perc_add" value=".25"/>""",
        lore="A chainsaw with a welded-on second fuel tank and teeth filed to razors. It was made for trees once.",
        ability="Twice the fuel tank. +25% damage to zombies.",
    ),
    dict(
        name="DementiveToolProspectorsPick", title="Prospector's Pick", parent="meleeToolPickT1IronPickaxe", rare=False,
        tint="#DAA520",
        signature=f"""
<passive_effect name="HarvestCount" operation="base_set" value="1" tags="{PROSPECTOR}"/>""",
        lore="An old prospector's pick, worn smooth where a hundred years of hands held it. It always seems to know where to strike.",
        ability="Ore can drop gold, silver and raw diamonds, at 3 times the Lucky Strike book's chance.",
    ),
    dict(
        name="DementiveToolJohnHenry", title="John Henry", parent="meleeToolPickT2SteelPickaxe", rare=True,
        tint="#4682B4",
        edits=[(r'(name="AttacksPerMinute" operation="base_set" value=")55"', r'\g<1>69"')],
        signature="""
<triggered_effect trigger="onSelfDestroyedBlock" action="ModifyStats" stat="Stamina" operation="add" value="5"/>""",
        lore="Named for the steel-driving man who beat the machine. Every rock it breaks only makes you want to swing again.",
        ability="Every block you break gives back 5 stamina. Swings 25% faster.",
    ),
    dict(
        name="DementiveToolBigBertha", title="Big Bertha", parent="meleeToolPickT3Auger", rare=True,
        tint="#FF8C00",
        edits=[(r'(name="MagazineSize" operation="base_set" value=")300"', r'\g<1>600"'),
               (r'(name="RoundsPerMinute" operation="base_set" value=")300"', r'\g<1>360"')],
        signature="""
<passive_effect name="DamageModifier" operation="perc_add" value=".25" tags="stone"/>
<passive_effect name="DamageModifier" operation="perc_add" value=".25" tags="metal"/>""",
        lore="A mining crew's pride, with an oversized tank bolted on and the governor ripped out. It chews through rock like it's angry at it.",
        ability="Twice the fuel tank. Drills 20% faster. +25% damage to stone and metal.",
    ),
    dict(
        name="DementiveToolLuckySpade", title="Lucky Spade", parent="meleeToolShovelT0StoneShovel", rare=False,
        tint="#7CFC00",
        signature=f"""
<passive_effect name="HarvestCount" operation="base_set" value="1" tags="{LUCKY_SPADE}"/>""",
        lore="A crude stone spade with a four-leaf clover carved into the blade. Folks buried a lot of things when the world ended.",
        ability="Digging dirt, forest ground and sand sometimes turns up a buried stash.",
    ),
    dict(
        name="DementiveToolTrenchRaider", title="Trench Raider", parent="meleeToolShovelT1IronShovel", rare=False,
        tint="#556B2F",
        signature="""
<triggered_effect trigger="onSelfAttackedOther" action="AddBuff" target="other" target_tags="zombie" buff="buffInjuryKnockdown01">
	<requirement name="IsSecondaryAttack"/>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="25"/>
</triggered_effect>""",
        # The hit target is set before damage is worked out, the way vanilla's hunting journals check for animals
        extra_signature=("Trench Raider zombie damage", """
<requirement name="EntityTagCompare" target="other" tags="zombie"/>
<passive_effect name="EntityDamage" operation="perc_add" value=".5"/>"""),
        lore="A sharpened entrenching shovel from a war long before this one. Soldiers learned it was better for fighting than digging.",
        ability="+50% damage to zombies. Power attacks have a 25% chance to knock them down.",
    ),
    dict(
        name="DementiveToolXMarksTheSpot", title="X Marks the Spot", parent="meleeToolShovelT2SteelShovel", rare=True,
        tint="#FFD700",
        # The search circle's shrink rate is read once when the treasure quest starts, so the shovel can't change it.
        # Instead it digs faster while the player is inside a treasure circle (buffDementiveToolsTreasureCircle)
        signature="""
<passive_effect name="DamageModifier" operation="perc_add" value=".5" tags="earth"/>""",
        extra_signature=("X Marks the Spot treasure circle", """
<requirement name="HasBuff" buff="buffDementiveToolsTreasureCircle"/>
<passive_effect name="DamageModifier" operation="perc_add" value=".5" tags="earth"/>
<passive_effect name="StaminaLoss" operation="perc_add" value="-1" tags="primary,secondary"/>"""),
        lore="A treasure hunter's steel shovel with a hand-drawn map etched into the blade. It digs best when there's something to find.",
        ability="Digs earth 50% faster. Inside a buried treasure circle it digs twice as fast and uses no stamina.",
    ),
    dict(
        name="DementiveToolGreaseMonkey", title="Grease Monkey", parent="meleeToolSalvageT1Wrench", rare=False,
        tint="#2F4F4F",
        signature=f"""
<passive_effect name="HarvestCount" operation="perc_add" value=".5" tags="{CAR_SALVAGE}"/>
<passive_effect name="HarvestCount" operation="perc_add" value=".5" tags="{CAR_RARE}"/>""",
        lore="A mechanic's wrench, black with fifty years of grease. Whoever owned it could strip a car down to the frame in an afternoon.",
        ability="Salvaging cars gives 50% more parts, and small engines and car batteries come out in pairs.",
    ),
    dict(
        name="DementiveToolTinkerer", title="Tinkerer", parent="meleeToolSalvageT2Ratchet", rare=True,
        tint="#00CED1",
        signature=f"""
<passive_effect name="HarvestCount" operation="perc_add" value="1" tags="{TINKER}"/>""",
        lore="A tinkerer's ratchet with a magnetized head and a set of tiny bits taped to the handle. Nothing electrical is safe from it.",
        ability="+100% electrical parts and springs from salvaging.",
    ),
    dict(
        name="DementiveToolPitCrew", title="Pit Crew", parent="meleeToolSalvageT3ImpactDriver", rare=True,
        tint="#DC143C",
        edits=[(r'(name="AttacksPerMinute" operation="base_set" value=")50"', r'\g<1>70"')],
        signature=f"""
<passive_effect name="HarvestCount" operation="base_set" value="1" tags="{PIT_CREW}"/>""",
        lore="A race team's impact driver, still wearing its sponsor stickers. It takes the good parts off a car before anyone else gets to them.",
        ability="Salvages 40% faster. Each car you strip has a 5% chance to drop a crate with a vanilla vehicle mod.",
    ),
]

# Bundles some tools dig up: opening one fills a loot window from its loot container (loot.xml)
BUNDLES = [
    dict(name="DementiveToolsBuriedStash", title="Buried Stash", icon="cntWoodenChestRottenClosed", tint="#C8A050",
         container="DementiveToolsBuriedStash", size="6,3", group="groupHiddenStash",
         desc="A rotten little chest somebody buried and never came back for. Open it to see what's inside."),
    dict(name="DementiveToolsVehicleModCrate", title="Salvaged Vehicle Mod", icon="bundleVehicleParts", tint="#DC143C",
         container="DementiveToolsVehicleModCrate", size="1,1", group="vehicleMods",
         desc="A vehicle mod pulled off a wreck in one piece. Open it to see what you got."),
]

# Icon recipes for IconTool.exe fx (see the ops in Scripts/WeaponsExpanded/IconTool.cs): a paint job, decal or glow
# per tool, in the style of the hand-made Weapons Expanded icons. `tint` above is only for the server-side copy.
GOLD = "map:#2a1800,#d4a017,#fff4c0"
ICONS = {
    # The stone axe's head is at the top, the handle below it
    "DementiveToolGrandpasHatchet": ["map:#120a04,#6b4422,#d8b080", "pattern:woodgrain,c1=#c89058,c2=#4a2a10,scale=5,angle=60,op=0.55,zone=90/-0.55/0.62",
                                     "map:#101318,#66707c,#e6eef6,zone=90/0.55/0.65", "sheen:0.35", "rim:#ffd890,2,0.5", "sparkle:#fff6d8,2,10,3"],
    "DementiveToolContractor": ["map:#1a1000,#ffb300,#fff2c0", "pattern:hazard,c1=#111111,c2=#ffcc00,scale=8,op=0.9,zone=90/-0.35/0.4",
                                "sheen:0.5", "rim:#fff2b0,2,0.4"],
    # Gunmetal with a painted tally down the side and a Blood Moon glow
    "DementiveToolNightShift": ["map:#060608,#3a3a44,#c8c8d4", "sheen:0.5", "pattern:stripes,c1=#f0f0f0,scale=4,angle=90,op=0.75,zone=0/0.25/0.28/0.5/0.53",
                                "pattern:splatter,c1=#9a0000,scale=7,amount=0.5,op=0.95,seed=5,shade=0.6", "rim:#ff2020,2,0.6", "glow:#ff1a1a,6,0.5"],
    "DementiveToolWidowmaker": ["map:#04140a,#2e8b57,#c8f0d0", "pattern:woodgrain,c1=#6ad08a,c2=#0a3a1a,scale=5,angle=45,op=0.45",
                                "sheen:0.45", "glow:#ffc030,6,0.6", "sparkle:#ffe080,3,10,4"],
    "DementiveToolChopper": ["map:#0a0a0c,#7a7a84,#ffffff", "sheen:0.8", "pattern:splatter,c1=#8a0000,scale=7,amount=0.52,op=1,seed=3,shade=0.6",
                             "trail:#ff3030,200,3,7,0.6"],
    "DementiveToolMeatGrinder": ["map:#0a0000,#7a0e0e,#ff9a8a", "sheen:0.6", "pattern:splatter,c1=#3a0000,scale=6,amount=0.55,op=0.9,seed=9,shade=0.5",
                                 "rim:#ff6040,2,0.45", "sparkle:#ffffff,2,10,4"],
    "DementiveToolProspectorsPick": [GOLD, "sheen:0.7", "pattern:speckle,c1=#ffffff,scale=4,amount=0.75,op=0.6,seed=2", "sparkle:#ffffff,4,12,5",
                                     "glow:#ffd24a,6,0.6"],
    "DementiveToolJohnHenry": ["map:#050a14,#2a4a78,#c0dcff", "sheen:0.6", "pattern:cracks,c1=#9fd8ff,scale=14,op=0.9,bloom=0.7,width=0.06,seed=4",
                               "emissive:#bfe8ff,0.8,0.8", "embers:#ffd080,8,1.4,3"],
    "DementiveToolBigBertha": ["map:#1a0800,#ff7a00,#ffe0b0", "pattern:hazard,c1=#111111,c2=#ffcc00,scale=9,op=0.95,zone=0/0.42/0.45/0.58/0.61",
                               "sheen:0.5", "pattern:cracks,c1=#ffef9a,scale=16,op=0.7,bloom=0.6,width=0.05,seed=7", "embers:#ffb040,10,1.6,6"],
    "DementiveToolLuckySpade": ["map:#061a02,#3aa020,#d8ffb0", "pattern:speckle,c1=#a8ff60,scale=5,amount=0.68,op=0.5,seed=4,bloom=0.4",
                                "glow:#7cfc00,8,0.8", "sparkle:#f0ffd0,4,12,8"],
    "DementiveToolTrenchRaider": ["pattern:camo,c1=#556b2f,c2=#2f3a1a,c3=#7a6a40,scale=14,op=0.95,seed=3,shade=0.7", "sheen:0.3",
                                  "pattern:splatter,c1=#5a0000,scale=6,amount=0.6,op=0.85,seed=2,shade=0.6,zone=90/0.55/0.65", "rim:#c8d890,2,0.3"],
    # Old copper rather than gold, so it doesn't look like Prospector's Pick
    "DementiveToolXMarksTheSpot": ["map:#1a0800,#a8582a,#ffd8b0", "sheen:0.55", "pattern:cracks,c1=#2a1000,scale=12,op=0.7,width=0.05,seed=8,shade=0.6",
                                   "glow:#ffcc33,9,0.9,noise=12", "sparkle:#ffffff,3,14,6"],
    "DementiveToolGreaseMonkey": ["map:#0a0a0c,#4a5a5a,#d0e0e0", "sheen:0.7", "pattern:splatter,c1=#050505,scale=8,amount=0.5,op=0.85,seed=6,shade=0.5",
                                  "rim:#ffb000,2,0.7", "sparkle:#ffe0a0,2,10,5"],
    "DementiveToolTinkerer": ["map:#021418,#00a8b0,#d0ffff", "pattern:circuit,c1=#7ffff0,scale=11,op=0.85,bloom=0.6,seed=5", "rim:#bffff8,2,0.5",
                              "sparkle:#e0ffff,2,10,4"],
    "DementiveToolPitCrew": ["map:#1a0004,#dc143c,#ffc0c8", "pattern:stripes,c1=#ffffff,scale=6,angle=-30,op=0.85,zone=0/0.45/0.5/0.62/0.67",
                             "sheen:0.75", "trail:#ffffff,180,3,7,0.55", "sparkle:#ffffff,2,12,3"],
    "DementiveToolsBuriedStash": ["map:#120a04,#6b4a22,#e0c090", "pattern:splatter,c1=#2a1a08,scale=8,amount=0.5,op=0.8,seed=4,shade=0.5",
                                  "glow:#ffcc33,7,0.7", "sparkle:#fff0b0,3,12,5"],
    "DementiveToolsVehicleModCrate": ["map:#120004,#9a1030,#ffb0c0", "sheen:0.5", "rim:#ff5070,2,0.6", "glow:#ff2a50,6,0.6", "sparkle:#ffffff,2,10,7"],
}

BUFFS = """<Dementive>

	<append xpath="/buffs">
		<!-- Chopper: given for a zombie killed with a power attack -->
		<buff name="buffDementiveToolsChopper" name_key="buffDementiveToolsChopperName" description_key="buffDementiveToolsChopperDesc" icon="ui_game_symbol_run_and_gun" icon_color="192,192,192">
			<stack_type value="replace"/>
			<duration value="5"/>
			<display_value value="duration"/>
			<!-- Swing stamina is asked for with the action's tags (primary/secondary) only, so the axe check is a
			     requirement rather than a tag -->
			<effect_group>
				<requirement name="HoldingItemHasTags" tags="axe"/>
				<passive_effect name="AttacksPerMinute" operation="perc_add" value=".5" tags="primary,secondary"/>
				<passive_effect name="StaminaLoss" operation="perc_add" value="-1" tags="primary,secondary"/>
			</effect_group>
		</buff>

		<!-- X Marks the Spot: added while the player is inside a buried treasure circle (entityclasses.xml). It also
		     runs out on its own, in case the circle is left in a way that doesn't fire the exit event -->
		<buff name="buffDementiveToolsTreasureCircle" hidden="true">
			<stack_type value="replace"/>
			<duration value="900"/>
		</buff>
	</append>

</Dementive>
"""

BUFF_LOC = [
    ("buffDementiveToolsChopperName", "Chopper"),
    ("buffDementiveToolsChopperDesc", "Your axe swings 50% faster and costs no stamina."),
]

ENTITYCLASSES = f"""<Dementive>

	<!-- The harvest tags this mod adds start at 0, like the Lucky Strike book's. Only the matching tool sets them to 1,
	     so nobody else gets the bonus drops -->
	<append xpath="/entity_classes/entity_class[@name='playerMale']/effect_group[passive_effect[@name='HarvestCount' and contains(@tags,'artOfMiningLuckyStrikeHarvest')]]">
		<passive_effect name="HarvestCount" operation="base_set" value="0" tags="{PROSPECTOR},{LUCKY_SPADE},{PIT_CREW}"/>
	</append>

	<!-- X Marks the Spot digs faster inside a buried treasure circle -->
	<append xpath="/entity_classes/entity_class[@name='playerMale']">
		<effect_group name="DementiveTools treasure circle">
			<triggered_effect trigger="onTreasureRadiusEntered" action="AddBuff" buff="buffDementiveToolsTreasureCircle"/>
			<triggered_effect trigger="onTreasureRadiusExited" action="RemoveBuff" buff="buffDementiveToolsTreasureCircle"/>
			<triggered_effect trigger="onTreasureRadiusCompleted" action="RemoveBuff" buff="buffDementiveToolsTreasureCircle"/>
		</effect_group>
	</append>

</Dementive>
"""

# Chance per container opened that one tool drops, same as Armor Expanded's armor
LOOT = """<Dementive>

	<append xpath="/lootcontainers/lootprobtemplates">
		<!-- Chance per container opened that one named tool drops -->
		<lootprobtemplate name="DementiveToolRaresT1">
			<loot level="1,999999" prob="0.005"/>  <!-- 1 / 200 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveToolRaresT2">
			<loot level="1,999999" prob="0.01"/>  <!-- 1 / 100 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveToolRaresT3">
			<loot level="1,999999" prob="0.02"/>  <!-- 1 / 50 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveToolRaresT4">
			<loot level="1,999999" prob="0.04"/>  <!-- 1 / 25 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveToolRaresT5">
			<loot level="1,999999" prob="0.05"/>  <!-- 1 / 20 -->
		</lootprobtemplate>

		<!-- Quest rewards: the reward "value" is the quest tier. At tiers 4-6 roughly 3% of schematic rewards
		     (about 1 in 20 quests) offer one of the named tools instead -->
		<lootprobtemplate name="DementiveToolQuestRewards">
			<loot level="0,3" prob="0"/>
			<loot level="4,7" prob="0.06"/>
		</lootprobtemplate>
	</append>

	<insertBefore xpath="/lootcontainers/lootgroup[@name='groupScrapCommon']">
		<lootgroup name="groupDementiveToolsAll" count="1" loot_quality_template="qualBaseTemplate">
{items}
		</lootgroup>
	</insertBefore>

	<!-- Wall and picture safes -->
	<append xpath="//lootgroup[@name='groupSmallSafeLoot']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT2" force_prob="true"/>
	</append>
	<!-- Locked Iron Chest -->
	<append xpath="//lootgroup[@name='groupReinforcedChestT3']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT3" force_prob="true"/>
	</append>
	<!-- Locked Small Hardened Chest -->
	<append xpath="//lootgroup[@name='groupHardenedChestT4']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT4" force_prob="true"/>
	</append>
	<!-- Locked Large Hardened Chest -->
	<append xpath="//lootgroup[@name='groupHardenedChestT5']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT5" force_prob="true"/>
	</append>

	<append xpath="//lootgroup[@name='groupZpackBoss']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT3" force_prob="true"/>
	</append>
	<append xpath="//lootgroup[@name='groupZpackStrong']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT2" force_prob="true"/>
	</append>
	<append xpath="//lootgroup[@name='groupZpackReg']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT1" force_prob="true"/>
	</append>

	<append xpath="//lootgroup[@name='groupHiddenStash']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT2" force_prob="true"/>
	</append>

	<append xpath="//lootgroup[@name='groupBuriedTreasure']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolRaresT3" force_prob="true"/>
	</append>

	<append xpath="/lootcontainers/lootgroup[@name='groupQuestSchematics']">
		<item group="groupDementiveToolsAll" loot_prob_template="DementiveToolQuestRewards"/>
	</append>

	<!-- What the dug-up bundles hold -->
	<append xpath="/lootcontainers">
{containers}
	</append>

</Dementive>
"""

TRADERS = """<Dementive>

	<!-- Traders can stock the tools: each group is a small-weight entry in the vanilla tools and rare tools groups
	     that traders restock from. Each tool's TraderStageTemplate keeps the iron and stone ones to trader stage 1+
	     (baseTier1) and the steel and motor ones to 50+ (baseTier2).
	     The game only lets a group use groups defined above it, so these go before rareTools (the first of the two). -->
	<insertBefore xpath="/traders/trader_item_groups/trader_item_group[@name='rareTools']">
{groups}
	</insertBefore>

{appends}
</Dementive>
"""
TRADER_PROB = "0.055"


def van_item(name):
    return re.search(r'\n<item name="%s">.*?\n</item>' % re.escape(name), van, re.S).group(0)


def van_prop(item, prop_name):
    """A property from an item or the item it Extends."""
    while item:
        v = van_item(item)
        m = re.search(r'\n\t<property name="%s" value="([^"]*)"' % prop_name, v)
        if m:
            return m.group(1)
        m = re.search(r'\n\t<property name="Extends" value="([^"]*)"', v)
        item = m.group(1) if m else None
    return None


def scale(values, factor):
    out = []
    for v in values.split(","):
        x = round(float(v) * factor, 2)
        out.append(str(int(x)) if x == int(x) else str(x))
    return ",".join(out)


def indent2(block):
    return "\n".join("\t\t" + l if l else l for l in block.split("\n"))


def build(t):
    v = van_item(t["parent"])
    tier = "baseTier2" if t["rare"] else "baseTier1"
    head = [
        f"\t\t<!-- {t['title']} -->",
        f'\t\t<item name="{t["name"]}">',
        f'\t\t\t<property name="Extends" value="{t["parent"]}"/>',
        f'\t\t\t<property name="CustomIcon" value="{t["name"]}"/>',
        '\t\t\t<property name="CustomIconTint" value="FFFFFF"/>',  # the steel shovel tints its borrowed icon
        f'\t\t\t<property name="DescriptionKey" value="{t["name"]}Desc"/>',
        '\t\t\t<property name="EconomicValue" value="3000"/>',
        f'\t\t\t<property name="TraderStageTemplate" value="{tier}"/>',
    ]
    # Actions that change are copied whole, with the edits, rather than relying on how nested properties merge
    actions = []
    for action, edits in t.get("actions", {}).items():
        a = re.search(r'\n(\t<property class="%s">.*?\n\t</property>)' % action, v, re.S)
        if not a:
            raise SystemExit(f"{t['name']}: no {action} on {t['parent']}")
        body = a.group(1)
        for pattern, repl in edits:
            body, n = re.subn(pattern, repl, body)
            if n != 1:
                raise SystemExit(f"{t['name']}: {action} edit {pattern!r} matched {n} times")
        actions.append(indent2(body))
    # <stats> and effect groups are children at one tab in vanilla; the mod's item children are at three
    blocks = re.findall(r'\n(\t<stats>.*?\n\t</stats>|\t<effect_group.*?\n\t</effect_group>)', v, re.S)
    if not blocks:
        raise SystemExit(f"{t['name']}: no effect groups on {t['parent']}")
    body = "\n".join(indent2(b) for b in blocks)
    body = body.replace(f'<effect_group name="{t["parent"]}">', f'<effect_group name="{t["name"]}">', 1)
    body, n_dur = re.subn(r'(name="DegradationMax" operation="base_set" value=")([\d.,]+)(" tier=")',
                          lambda m: m.group(1) + scale(m.group(2), DURABILITY_BOOST) + m.group(3), body)
    body, n_block = re.subn(r'(name="BlockDamage" operation="base_set" value=")([\d.]+)(")',
                            lambda m: m.group(1) + scale(m.group(2), BLOCK_BOOST) + m.group(3), body, count=1)
    if n_dur != 1:
        raise SystemExit(f"{t['name']}: expected 1 durability value, got {n_dur}")
    if n_block != 1 and t["parent"] != "meleeToolRepairT3Nailgun":  # the nail gun fires nails, it has no block damage
        raise SystemExit(f"{t['name']}: expected a block damage value, got {n_block}")
    for pattern, repl in t.get("edits", []):
        body, n = re.subn(pattern, repl, body)
        if n != 1:
            raise SystemExit(f"{t['name']}: edit {pattern!r} matched {n} times")
    sig = [eg(t["title"], t["signature"])]
    if "extra_signature" in t:
        sig.append(eg(*t["extra_signature"]))
    parts = "\n".join(head) + "\n\n"
    if actions:
        parts += "\n".join(actions) + "\n\n"
    return parts + body + "\n\n" + "\n".join(sig) + "\n\t\t</item>\n"


def bundle_item(b):
    return "\n".join([
        f"\t\t<!-- {b['title']}: dug up by a named tool -->",
        f'\t\t<item name="{b["name"]}">',
        '\t\t\t<property name="Extends" value="questRewardBundleMaster"/>',
        '\t\t\t<property name="CreativeMode" value="Player"/>',
        f'\t\t\t<property name="CustomIcon" value="{b["name"]}"/>',
        '\t\t\t<property name="CustomIconTint" value="FFFFFF"/>',
        '\t\t\t<property name="ItemTypeIcon" value="bundle"/>',
        f'\t\t\t<property name="DescriptionKey" value="{b["name"]}Desc"/>',
        '\t\t\t<property name="Stacknumber" value="10"/>',
        '\t\t\t<property class="Action0">',
        '\t\t\t\t<property name="Class" value="OpenLootBundle"/>',
        '\t\t\t\t<property name="Delay" value="0"/>',
        '\t\t\t\t<property name="Sound_start" value="close_garbage"/>',
        f'\t\t\t\t<property name="LootList" value="{b["container"]}"/>',
        '\t\t\t</property>',
        '\t\t</item>',
    ]) + "\n"


# --- blocks.xml: the drops and tags the tools rely on ---

def block_bodies():
    return dict(re.findall(r'<block name="([^"]+)">(.*?)</block>', van_blocks, re.S))


def descendants(bodies, root):
    parent = {n: (re.search(r'<property name="Extends" value="([^"]+)"', b) or [None, None])[1] for n, b in bodies.items()}
    out = []
    for n in bodies:
        p = parent[n]
        while p and p != root:
            p = parent.get(p)
        if p == root:
            out.append(n)
    return out


def blocks_xml():
    bodies = block_bodies()
    out = ["<Dementive>", ""]

    # Widowmaker: a tag on every tree, so a damage bonus (DamageModifier also matches block tags, like the pickaxe's
    # terrGravel one) can tell trees from other wood. Trees inherit treeMaster's tags unless they set their own
    out.append("\t<!-- Widowmaker: trees get a tag of their own, so its damage bonus skips other wood -->")
    for name in ["treeMaster"] + descendants(bodies, "treeMaster"):
        m = re.search(r'<property name="Tags" value="([^"]*)"', bodies[name])
        if m:
            out.append(f"\t<set xpath=\"/blocks/block[@name='{name}']/property[@name='Tags']/@value\">{m.group(1)},{TREE_TAG}</set>")
    out.append("")

    # Prospector's Pick: the Lucky Strike book's gem drops again, at 3x the chance, under the pick's own tag. The ore
    # blocks have no children, so a second drop of the same item isn't lost to inheritance
    out.append("\t<!-- Prospector's Pick: the Lucky Strike book's drops again, at 3x the chance, for the pick only -->")
    for name, body in bodies.items():
        drops = re.findall(r'<drop event="Harvest" name="(\w+)" prob="([\d.]+)" count="1" tag="artOfMiningLuckyStrikeHarvest"', body)
        if not drops:
            continue
        out.append(f"\t<append xpath=\"/blocks/block[@name='{name}']\">")
        for item, prob in drops:
            out.append(f'\t\t<drop event="Harvest" name="{item}" prob="{round(float(prob) * 3, 4)}" count="1" tag="{PROSPECTOR}"/>')
        out.append("\t</append>")
    out.append("")

    # Lucky Spade: a buried stash in dirt, forest ground and sand (terrSand and terrTopSoil inherit it)
    out.append("\t<!-- Lucky Spade: dirt, forest ground and sand can hold a buried stash (sand and topsoil inherit it) -->")
    for name in ("terrDirt", "terrForestGround", "terrBurntForestGround", "terrDesertGround"):
        if name not in bodies:
            raise SystemExit(f"no vanilla block {name}")
        out.append(f"\t<append xpath=\"/blocks/block[@name='{name}']\">")
        out.append(f'\t\t<drop event="Harvest" name="DementiveToolsBuriedStash" prob=".004" count="1" tag="{LUCKY_SPADE}"/>')
        out.append("\t</append>")
    out.append("")

    # Cars are the blocks that salvage into headlights. Their variants inherit these drops, tags included. A child
    # only copies one drop per item name from its parent, so the bonuses are extra tags on the existing drops (read by
    # HarvestCount on the tool) rather than second drops of the same items
    cars = [n for n, b in bodies.items() if re.search(r'<drop event="Harvest" name="resourceHeadlight"', b)]
    out.append("\t<!-- Grease Monkey and Pit Crew: cars are the blocks that salvage into headlights. Their color variants")
    out.append("\t     inherit the drops, tags included. Grease Monkey boosts the drops tagged here; Pit Crew's crate is")
    out.append("\t     a drop of its own -->")
    for name in cars:
        tags = sorted(set(re.findall(r'<drop event="Harvest" name="\w+"[^>]*?tag="([^"]*salvageHarvest[^"]*)"', bodies[name])))
        for tag in tags:
            rare = f"\t<setattribute xpath=\"/blocks/block[@name='{name}']/drop[@event='Harvest' and @tag='{tag}' and (@name='smallEngine' or @name='carBattery')]\" name=\"tag\">{tag},{CAR_SALVAGE},{CAR_RARE}</setattribute>"
            rest = f"\t<setattribute xpath=\"/blocks/block[@name='{name}']/drop[@event='Harvest' and @tag='{tag}' and @name!='smallEngine' and @name!='carBattery']\" name=\"tag\">{tag},{CAR_SALVAGE}</setattribute>"
            if re.search(r'<drop event="Harvest" name="(smallEngine|carBattery)"[^>]*?tag="%s"' % re.escape(tag), bodies[name]):
                out.append(rare)
            if re.search(r'<drop event="Harvest" name="(?!smallEngine"|carBattery")\w+"[^>]*?tag="%s"' % re.escape(tag), bodies[name]):
                out.append(rest)
        out.append(f"\t<append xpath=\"/blocks/block[@name='{name}']\">")
        out.append(f'\t\t<drop event="Harvest" name="DementiveToolsVehicleModCrate" prob=".05" count="1" tag="{PIT_CREW}"/>')
        out.append("\t</append>")
    out.append("")

    # Tinkerer: electrical parts and springs salvaged from anything. Runs after the car tags, so it matches them
    out.append("\t<!-- Tinkerer: electrical parts and springs from anything salvaged -->")
    tinker_tags = set()
    for name, body in bodies.items():
        for item, tag in re.findall(r'<drop event="Harvest" name="(resourceElectricParts|resourceSpring)"[^>]*?tag="([^"]*salvageHarvest[^"]*)"', body):
            if name in cars:
                tag = f"{tag},{CAR_SALVAGE}"
            tinker_tags.add(tag)
    for tag in sorted(tinker_tags):
        out.append(f"\t<setattribute xpath=\"/blocks/block/drop[@event='Harvest' and @tag='{tag}' and (@name='resourceElectricParts' or @name='resourceSpring')]\" name=\"tag\">{tag},{TINKER}</setattribute>")
    out += ["", "</Dementive>", ""]
    return "\n".join(out), len(cars)


def item_modifiers_xml():
    """Per-item mod overrides (the Burning Shaft's flames) for each tool whose parent has them: mods look these up by
    item name, so they aren't inherited through Extends."""
    vroot = ET.parse(os.path.join(cfg_dir, "item_modifiers.xml")).getroot()
    out = ["<Dementive>", "",
           "\t<!-- Mod overrides (flame effects) for each tool, copied from its vanilla parent. Mods look these up by",
           "\t     item name, so they are not inherited through Extends. -->"]
    for im in vroot.iter("item_modifier"):
        overrides = {o.get("name"): o for o in im.findall("item_property_overrides")}
        mine = [t for t in TOOLS if t["parent"] in overrides]
        if not mine:
            continue
        out.append("")
        out.append(f"\t<append xpath=\"/item_modifiers/item_modifier[@name='{im.get('name')}']\">")
        for t in mine:
            out.append(f'\t\t<item_property_overrides name="{t["name"]}">')
            for prop in overrides[t["parent"]]:
                attrs = " ".join(f'{k}="{v}"' for k, v in prop.attrib.items())
                out.append(f"\t\t\t<property {attrs}/>")
            out.append("\t\t</item_property_overrides>")
        out.append("\t</append>")
    out += ["", "</Dementive>", ""]
    return "\n".join(out)


def csv_field(s):
    return '"' + s.replace('"', '""') + '"' if "," in s or '"' in s else s


def loc_row(key, kind, text):
    return f"{key},{kind},,,,{csv_field(text)},,,,,,,,,,,,,"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n"))


items = "<Dementive>\n\n\t<!-- Named tools: rare, only looted or bought. Generated by Scripts/ToolsExpanded/gen_tools.py -->\n\t<append xpath=\"/items\">\n"
items += "\n".join(build(t) for t in TOOLS)
items += "\n" + "\n".join(bundle_item(b) for b in BUNDLES)
items += "\t</append>\n\n</Dementive>\n"

header = "Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"
loc = [header]
for t in TOOLS:
    loc.append(loc_row(t["name"], "items,Tool", t["title"]))
    loc.append(loc_row(t["name"] + "Desc", "items,Tool", f"{t['lore']}\\n\\n{t['ability']}"))
for b in BUNDLES:
    loc.append(loc_row(b["name"], "items,Item", b["title"]))
    loc.append(loc_row(b["name"] + "Desc", "items,Item", b["desc"]))
for key, text in BUFF_LOC:
    loc.append(loc_row(key, "buffs,Buff", text))

containers = "\n".join(
    f'\t\t<lootcontainer name="{b["container"]}" count="1" size="{b["size"]}" sound_open="UseActions/open_garbage" sound_close="silencefiller" '
    f'loot_quality_template="qualBaseTemplate" destroy_on_close="empty">\n\t\t\t<item group="{b["group"]}"/>\n\t\t</lootcontainer>'
    for b in BUNDLES)
loot = LOOT.replace("{items}", "\n".join(f'\t\t\t<item name="{t["name"]}"/>' for t in TOOLS)).replace("{containers}", containers)

groups, appends = [], []
for rare, vanilla in ((False, "tools"), (True, "rareTools")):
    kind = "Rare" if rare else "Basic"
    members = [t for t in TOOLS if t["rare"] == rare]
    groups.append(f'\t\t<trader_item_group name="groupDementiveTraderTools{kind}" count="1">\n'
                  + "\n".join(f'\t\t\t<item name="{t["name"]}" quality="1,6"/>' for t in members)
                  + "\n\t\t</trader_item_group>")
    appends.append(f"\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='{vanilla}']\">\n"
                   f'\t\t<item group="groupDementiveTraderTools{kind}" prob="{TRADER_PROB}"/>\n\t</append>\n')
traders = TRADERS.replace("{groups}", "\n".join(groups)).replace("{appends}", "\n".join(appends))

blocks, n_cars = blocks_xml()
cfg = os.path.join(mod, "Config")
write(os.path.join(cfg, "items.xml"), items)
write(os.path.join(cfg, "item_modifiers.xml"), item_modifiers_xml())
write(os.path.join(cfg, "blocks.xml"), blocks)
write(os.path.join(cfg, "entityclasses.xml"), ENTITYCLASSES)
write(os.path.join(cfg, "buffs.xml"), BUFFS)
write(os.path.join(cfg, "loot.xml"), loot)
write(os.path.join(cfg, "traders.xml"), traders)
write(os.path.join(cfg, "Localization.csv"), "\n".join(loc) + "\n")
print(f"{len(TOOLS)} tools and {len(BUNDLES)} bundles written to {cfg} ({n_cars} car blocks tagged)")

atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
os.makedirs(atlas, exist_ok=True)
icon_dir = os.path.join(game, "Data", "ItemIcons")
for name, base in [(t["name"], van_prop(t["parent"], "CustomIcon") or t["parent"]) for t in TOOLS] + [(b["name"], b["icon"]) for b in BUNDLES]:
    subprocess.run([icon_tool, "fx", os.path.join(icon_dir, base + ".png"), os.path.join(atlas, name + ".png"), *ICONS[name]], check=True)
print(f"{len(TOOLS) + len(BUNDLES)} icons written to {atlas}")

if server:
    scfg = os.path.join(server, "Config")
    os.makedirs(scfg, exist_ok=True)
    tinted = items
    for t in TOOLS:
        base = van_prop(t["parent"], "CustomIcon") or t["parent"]
        tinted = tinted.replace(f'<property name="CustomIcon" value="{t["name"]}"/>\n\t\t\t<property name="CustomIconTint" value="FFFFFF"/>',
                                f'<property name="CustomIcon" value="{base}"/>\n\t\t\t<property name="CustomIconTint" value="{t["tint"][1:]}"/>')
    for b in BUNDLES:
        tinted = tinted.replace(f'<property name="CustomIcon" value="{b["name"]}"/>\n\t\t\t<property name="CustomIconTint" value="FFFFFF"/>',
                                f'<property name="CustomIcon" value="{b["icon"]}"/>\n\t\t\t<property name="CustomIconTint" value="{b["tint"][1:]}"/>')
    if re.search(r'name="CustomIcon" value="Dementive', tinted):
        raise SystemExit("server-side copy still uses a custom icon")
    write(os.path.join(scfg, "items.xml"), tinted)
    for f in os.listdir(cfg):
        if f != "items.xml":
            shutil.copyfile(os.path.join(cfg, f), os.path.join(scfg, f))
    print(f"server-side copy written to {scfg}")
