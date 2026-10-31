"""Generate the ArmorExpanded mod (and its server-side copy) from the PIECES table below.

Usage: python gen_armor.py <game dir> <ArmorExpanded dir> [<ArmorExpanded-SERVERSIDE dir>]
Each named piece Extends a vanilla armor piece and carries copies of its effect groups (those are not inherited),
with +20% armor rating, +50% durability and a signature effect group. It keeps the vanilla piece's ArmorGroup, so
it counts toward that set's full set bonus. Rewrites Config/items.xml, buffs.xml, loot.xml, traders.xml and
Localization.csv, and paints the vanilla icons into UIAtlases/ItemIconAtlas with Scripts/bin/IconTool.exe (ICONS).
The server-side copy uses the vanilla icons with a color tint instead, since its clients don't have the icons.
"""
import os
import re
import shutil
import subprocess
import sys

game, mod = sys.argv[1:3]
server = sys.argv[3] if len(sys.argv) > 3 else None
van = open(os.path.join(game, "Data", "Config", "items.xml"), encoding="utf-8").read()
icon_tool = os.path.join(os.path.dirname(__file__), "..", "bin", "IconTool.exe")

ARMOR_BOOST = 1.2       # armor rating (physical and elemental) compared to the vanilla piece
DURABILITY_BOOST = 1.5  # DegradationMax compared to the vanilla piece


def eg(name, body):
    """A signature effect group, written with the mod's indentation (item children at 3 tabs)."""
    lines = body.strip("\n").split("\n")
    return f'\t\t\t<effect_group name="{name}" tiered="false">\n' + "\n".join("\t\t\t\t" + l for l in lines) + "\n\t\t\t</effect_group>"


PIECES = [
    dict(
        name="DementiveArmorTimberGloves", title="Paul's Timber Gloves", parent="armorLumberjackGloves", set="Lumberjack",
        weight="Light", tint="#C0392B",
        signature="""
<passive_effect name="HarvestCount" operation="perc_add" value=".25" tags="lumberjackHarvest"/>
<triggered_effect trigger="onSelfAttackedOther" action="AddBuff" target="other" target_tags="zombie,animal" buff="buffInjuryKnockdown01">
	<requirement name="HoldingItemHasTags" tags="axe,chainsaw"/>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="20"/>
</triggered_effect>""",
        lore="Thick leather gloves worn smooth by a lifetime of felling trees. Whoever Paul was, he hit hard.",
        ability="Axe and chainsaw hits have a 20% chance to knock zombies and animals down. +25% wood harvest.",
    ),
    dict(
        name="DementiveArmorSundayBest", title="Sunday Best", parent="armorPreacherOutfit", set="Preacher",
        weight="Light", tint="#FFD700",
        # The kill check runs first and leaves a flag, because on the party heal "other" is the party member
        signature="""
<triggered_effect trigger="onSelfKilledOther" action="ModifyCVar" cvar=".DementiveSundayBestKill" operation="set" value="1">
	<requirement name="EntityTagCompare" target="other" tags="zombie"/>
</triggered_effect>
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorSundayBest">
	<requirement name="CVarCompare" cvar=".DementiveSundayBestKill" operation="Equals" value="1"/>
</triggered_effect>
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" target="selfOtherPlayers" target_tags="party,ally" buff="buffDementiveArmorSundayBest">
	<requirement name="CVarCompare" target="self" cvar=".DementiveSundayBestKill" operation="Equals" value="1"/>
	<requirement name="TargetRange" target="other" operation="LTE" value="15"/>
</triggered_effect>
<triggered_effect trigger="onSelfKilledOther" action="ModifyCVar" cvar=".DementiveSundayBestKill" operation="set" value="0"/>""",
        lore="A preacher's finest suit, still pressed and spotless. Folks say the man who wore it could heal the sick, and maybe they were right.",
        ability="Every zombie you kill heals you and your party members within 15 meters for 5 health over 5 seconds.",
    ),
    dict(
        name="DementiveArmorPickpocketGloves", title="Pickpocket's Gloves", parent="armorRogueGloves", set="Rogue",
        weight="Light", tint="#8A2BE2",
        signature="""
<passive_effect name="LockPickTime" operation="perc_add" value="-.5"/>
<passive_effect name="LockPickBreakChance" operation="perc_add" value="-.5"/>
<passive_effect name="ScavengingTime" operation="perc_subtract" value=".25"/>""",
        lore="Thin, supple gloves made for quick fingers and quiet work. No lock or crate stands in your way for long.",
        ability="Lockpicking is 50% faster and breaks 50% fewer lockpicks. Searching containers is 25% faster.",
    ),
    dict(
        name="DementiveArmorMarathonRunners", title="Marathon Runners", parent="armorAthleticBoots", set="Athletic",
        weight="Light", tint="#00BFFF",
        # The fall damage part is in buffs.xml: buffPlayerFallingDamage checks for buffDementiveArmorMarathonRunners
        signature="""
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".3" tags="running,swimmingRun"/>
<passive_effect name="JumpStrength" operation="perc_add" value=".3"/>
<triggered_effect trigger="onSelfEquipStart" action="AddBuff" buff="buffDementiveArmorMarathonRunners"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveArmorMarathonRunners"/>""",
        lore="Top-of-the-line running shoes from a marathon that never got to finish. They still want to go the distance.",
        ability="Sprinting uses 30% less stamina. Jump 30% higher. Falls hurt as if they were 4 meters shorter.",
    ),
    dict(
        name="DementiveArmorDonsShades", title="The Don's Shades", parent="armorEnforcerHelmet", set="Enforcer",
        weight="Light", tint="#B22222",
        signature="""
<passive_effect name="QuestRewardChoiceCount" operation="base_add" value="1"/>
<passive_effect name="BarteringBuying" operation="base_add" value=".1"/>
<passive_effect name="BarteringSelling" operation="base_add" value=".1"/>""",
        lore="Sharp sunglasses that once belonged to a man who never paid full price for anything. Traders still seem to remember them.",
        ability="Trader quests let you choose one extra reward. 10% better prices when buying and selling.",
    ),
    dict(
        name="DementiveArmorMuckBoots", title="Muck Boots", parent="armorFarmerBoots", set="Farmer",
        weight="Medium", tint="#6B8E23",
        # Same random-roll approach as the vanilla Farmer outfit and boots, which these stack with
        signature="""
<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="25"/>
	<passive_effect name="HarvestCount" operation="base_add" value="1" tags="farmerBonusHarvest"/>""",
        extra_signature=("Muck Boots bonus seed", """
<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="25"/>
	<passive_effect name="HarvestCount" operation="base_add" value="1" tags="farmerBonusSeed"/>"""),
        lore="Mud-caked rubber boots from a farm that fed half the county. Plants just seem to grow better around them.",
        ability="Every crop you harvest has a 25% chance to give a bonus crop and a 25% chance to give a bonus seed.",
    ),
    dict(
        name="DementiveArmorRoadCaptainsCut", title="Road Captain's Cut", parent="armorBikerOutfit", set="Biker",
        weight="Medium", tint="#FF4500",
        signature="""
<requirement name="StatComparePercCurrentToMax" stat="health" operation="LT" value=".5"/>
	<passive_effect name="GeneralDamageResist" operation="base_add" value=".2"/>
	<passive_effect name="EntityDamage" operation="perc_add" value=".2" tags="melee"/>""",
        lore="A road captain's leather vest, covered in patches from rides that ended badly for everyone else. It's at its best when things look worst.",
        ability="Below half health you take 20% less damage and deal 20% more melee damage.",
    ),
    dict(
        name="DementiveArmorJunkRatGoggles", title="Junk Rat Goggles", parent="armorScavengerHelmet", set="Scavenger",
        weight="Medium", tint="#DAA520",
        signature="""
<passive_effect name="LootStage" operation="perc_add" value=".1"/>
<passive_effect name="ScrappingTime" operation="perc_add" value="-.5"/>""",
        lore="Scratched goggles held together with tape and stubbornness. Through them, every pile of junk looks like treasure.",
        ability="Find better loot (+10% loot stage). Scrapping items is 50% faster.",
    ),
    dict(
        name="DementiveArmorMarshalsGloves", title="Marshal's Gloves", parent="armorRangerGloves", set="Ranger",
        weight="Medium", tint="#CD853F",
        # rangerDamage is the vanilla tag the Ranger set uses: .44 Magnum, pipe pistol and lever-action rifle
        signature="""
<requirement name="HoldingItemHasTags" tags="rangerDamage"/>
	<passive_effect name="HeadshotDamageModifier" operation="perc_add" value=".35" tags="head"/>
	<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".15"/>""",
        lore="Worn leather gloves from the last lawman in the county. His hands never shook, and with these on, neither will yours.",
        ability="The .44 Magnum, pipe pistol and lever-action rifle deal 35% more headshot damage and reload 15% faster.",
    ),
    dict(
        name="DementiveArmorFlakVest", title="Sergeant's Flak Vest", parent="armorCommandoOutfit", set="Commando",
        weight="Medium", tint="#3CB371",
        signature="""
<triggered_effect trigger="onOtherDamagedSelf" action="AddBuff" buff="buffDementiveArmorFlakVest">
	<requirement name="StatComparePercCurrentToMax" stat="health" operation="LT" value=".3"/>
	<requirement name="!HasBuff" buff="buffDementiveArmorFlakVestCooldown"/>
</triggered_effect>""",
        lore="A battered flak vest from a sergeant who walked out of every firefight. When things get desperate, it kicks in.",
        ability="Dropping below 30% health gives you 10 seconds of 25% damage resistance and 20% faster running. Recharges after 2 minutes.",
    ),
    dict(
        name="DementiveArmorGhostsHood", title="Ghost's Hood", parent="armorAssassinHelmet", set="Assassin",
        weight="Medium", tint="#7B68EE",
        # Same sneak attack check as the vanilla Hidden Strike perk
        signature="""
<passive_effect name="LightMultiplier" operation="perc_add" value="-.25"/>
<passive_effect name="EntityDamage" operation="perc_add" value=".5">
	<requirement name="CVarCompare" cvar="_crouching" operation="Equals" value="1"/>
	<requirement name="CVarCompare" cvar="_notAlerted" operation="GT" value="0" target="other"/>
</passive_effect>""",
        lore="A dark hood from someone nobody ever saw coming. Wear it and you'll be just as hard to spot.",
        ability="Sneak attacks deal 50% more damage. You are 25% harder to see.",
    ),
    dict(
        name="DementiveArmorWildcatterHat", title="Wildcatter's Hard Hat", parent="armorMinerHelmet", set="Miner",
        weight="Heavy", tint="#FFA500",
        signature="""
<passive_effect name="HarvestCount" operation="perc_add" value=".25" tags="oreWoodHarvest"/>
<passive_effect name="StaminaLoss" operation="perc_add" value="-.25">
	<requirement name="HoldingItemHasTags" tags="miningTool"/>
</passive_effect>""",
        lore="A dented hard hat from a wildcat miner who struck it rich more than once. It has a nose for ore.",
        ability="+25% ore and stone from mining. Mining tools use 25% less stamina.",
    ),
    dict(
        name="DementiveArmorWanderersWraps", title="Wanderer's Wraps", parent="armorNomadOutfit", set="Nomad",
        weight="Heavy", tint="#D2B48C",
        signature="""
<passive_effect name="HypothermalResist" operation="base_add" value="30"/>
<passive_effect name="HyperthermalResist" operation="base_add" value="30"/>
<passive_effect name="FoodLossPerStaminaPointGained" operation="perc_add" value="-.2"/>
<passive_effect name="WaterLossPerStaminaPointGained" operation="perc_add" value="-.2"/>""",
        lore="Sun-bleached wraps from a wanderer who crossed every wasteland on foot. Neither heat nor cold bothers whoever wears them.",
        ability="+30 heat and cold resistance. Food and water drain 20% slower.",
    ),
    dict(
        name="DementiveArmorThinkingCap", title="Thinking Cap", parent="armorNerdHelmet", set="Nerd",
        weight="Heavy", tint="#1E90FF",
        signature="""
<passive_effect name="PlayerExpGain" operation="perc_add" value=".1"/>
<passive_effect name="CraftingTime" operation="perc_add" value="-.2"/>""",
        lore="A lucky cap from a genius who never took it off. Everything just makes a little more sense with it on.",
        ability="+10% XP from everything. Crafting is 20% faster.",
    ),
    dict(
        name="DementiveArmorJuggernautBoots", title="Juggernaut Boots", parent="armorRaiderBoots", set="Raider",
        weight="Heavy", tint="#DC143C",
        # TrapIncomingDamage is only read by land mines
        signature="""
<passive_effect name="BuffResistance" operation="base_add" value="1" tags="buffInjuryStunned01CHTrigger,buffInjuryStunned00,buffInjuryStunned01,buffInjuryStunned02,buffInjuryStunned03,buffInjuryKnockdown01,buffInjuryKnockdown02"/>
<passive_effect name="ExplosionIncomingDamage" operation="perc_add" value="-.3"/>
<passive_effect name="TrapIncomingDamage" operation="perc_add" value="-.5"/>""",
        lore="Steel-shod raider boots built for kicking down doors and standing your ground. Nothing knocks you off your feet in these.",
        ability="You can't be knocked down or stunned. 30% less damage from explosions and 50% less from land mines.",
    ),
]

# Icon recipes for IconTool.exe fx (see the ops in Scripts/WeaponsExpanded/IconTool.cs): a paint job, decal or glow
# per piece, in the style of the hand-made Weapons Expanded icons. `tint` above is only for the server-side copy.
GOLD = "map:#2a1800,#d4a017,#fff4c0"
ICONS = {
    "DementiveArmorTimberGloves": ["pattern:plaid,c1=#c0281e,c2=#111111,scale=14,op=0.9", "sheen:0.2"],
    "DementiveArmorSundayBest": ["map:#3a2a10,#e8e2d0,#ffffff", "rim:#ffd700,3,0.6", "glow:#ffd24a,8,0.9", "sparkle:#fff3b0,3,12,2"],
    "DementiveArmorPickpocketGloves": ["map:#0a0314,#5a1f9a,#d6b8ff", "glow:#8a2be2,9,0.9,noise=12", "rim:#e0c4ff,2,0.6", "sparkle:#e8d0ff,1,10,5"],
    "DementiveArmorMarathonRunners": ["map:#00141f,#00a8e0,#c8f6ff", "sheen:0.4", "rim:#ff2fd0,2,0.8", "glow:#00d0ff,5,0.5", "trail:#ff2fd0,180,4,8,0.7"],
    "DementiveArmorDonsShades": [GOLD, "sheen:0.7", "sparkle:#ffffff,2,14,3"],
    "DementiveArmorMuckBoots": ["map:#0d1405,#4f6b1f,#b9cf7a", "pattern:splatter,c1=#2a170a,scale=9,amount=0.44,op=1,seed=4,shade=0.5,zone=90/-0.55/0.7", "sheen:0.3"],
    "DementiveArmorRoadCaptainsCut": ["map:#050505,#262626,#7a7a7a", "pattern:flames,c1=#ffe94d,c2=#ff2a00,c3=#120000,op=1,reach=0.8,count=5,seed=3,shade=0.35", "sheen:0.5"],
    "DementiveArmorJunkRatGoggles": ["map:#1a0d03,#9a6a2a,#f0d8a0", "pattern:speckle,c1=#7a2e0e,scale=8,amount=0.55,op=0.8,seed=3", "pattern:speckle,c1=#3a8a6a,scale=12,amount=0.68,op=0.6,seed=8", "sheen:0.3", "sparkle:#fff6c0,2,10,4"],
    "DementiveArmorMarshalsGloves": ["map:#120802,#6b3f1a,#d9a066", "sheen:0.3", "rim:#ffd700,2,0.7", "sparkle:#ffe9a0,1,14,2"],
    "DementiveArmorFlakVest": ["pattern:camo,c1=#6b7a30,c2=#34451f,c3=#8a7048,scale=18,op=0.9,seed=5,shade=0.7", "sheen:0.25", "rim:#c8d890,2,0.3"],
    "DementiveArmorGhostsHood": ["map:#020208,#1b1b30,#6a6a9a", "glow:#8fd0ff,12,1,noise=10", "rim:#bfe6ff,3,0.6", "emissive:#9fe8ff,0.5,0.9"],
    "DementiveArmorWildcatterHat": ["map:#2a0f00,#ff8c00,#ffe0a0", "pattern:hazard,c1=#ffcc00,c2=#111111,scale=10,op=0.9,zone=90/-0.3/0.36", "emissive:#fff2b0,0.85,1", "sheen:0.4"],
    "DementiveArmorWanderersWraps": ["pattern:camo,c1=#c8a874,c2=#8a6a3e,c3=#e8d6a8,scale=16,op=0.9,seed=7,shade=0.8", "pattern:speckle,c1=#f0dca8,scale=5,amount=0.62,op=0.35,seed=2",
                                     "sheen:0.2", "glow:#ff9a3a,7,0.5", "embers:#ffe0a8,8,1.2,4"],
    "DementiveArmorThinkingCap": ["map:#06142b,#1e5bb8,#9fd0ff", "pattern:circuit,c1=#3ff0ff,scale=12,op=0.8,bloom=0.5,seed=4", "rim:#7fe8ff,3,0.4"],
    "DementiveArmorJuggernautBoots": ["map:#0b0b0d,#3a3a40,#9a9aa5", "pattern:cracks,c1=#ff3b00,scale=18,op=1,bloom=0.9,width=0.07,seed=2", "sheen:0.4"],
}

BUFFS = """<Dementive>

	<append xpath="/buffs">
		<!-- Sunday Best: given to the wearer and party members within 15 m for each zombie killed. Each kill adds 5
		     seconds of 1 health per second -->
		<buff name="buffDementiveArmorSundayBest" name_key="buffDementiveArmorSundayBestName" description_key="buffDementiveArmorSundayBestDesc" icon="ui_game_symbol_add" icon_color="255,215,0">
			<stack_type value="duration"/>
			<duration value="5"/>
			<update_rate value="1"/>
			<display_value value="duration"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffUpdate" action="ModifyStats" stat="Health" operation="add" value="1"/>
			</effect_group>
		</buff>

		<!-- Marathon Runners: worn marker, checked by buffPlayerFallingDamage below -->
		<buff name="buffDementiveArmorMarathonRunners" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
		</buff>

		<!-- Sergeant's Flak Vest: low health burst, then a 2 minute cooldown -->
		<buff name="buffDementiveArmorFlakVest" name_key="buffDementiveArmorFlakVestName" description_key="buffDementiveArmorFlakVestDesc" icon="ui_game_symbol_armor_iron" icon_color="60,179,113">
			<stack_type value="ignore"/>
			<duration value="10"/>
			<display_value value="duration"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="AddBuff" buff="buffDementiveArmorFlakVestCooldown"/>
				<passive_effect name="GeneralDamageResist" operation="base_add" value=".25"/>
				<passive_effect name="RunSpeed" operation="perc_add" value=".2"/>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorFlakVestCooldown" name_key="buffDementiveArmorFlakVestCooldownName" description_key="buffDementiveArmorFlakVestCooldownDesc" icon="ui_game_symbol_armor_iron" icon_color="128,128,128">
			<stack_type value="ignore"/>
			<duration value="120"/>
			<display_value value="duration"/>
		</buff>
	</append>

	<!-- Marathon Runners: falls hurt as if they were 4 m shorter (vanilla boots use the same impact speed units:
	     .02828 = 2 m). Goes in the group where the vanilla boots reduce the impact speed, before it is checked -->
	<append xpath="/buffs/buff[@name='buffPlayerFallingDamage']/effect_group[triggered_effect[@value='@$rogueBootFallDMG']]">
		<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar=".impactSpeed" operation="subtract" value=".05656">
			<requirement name="HasBuff" buff="buffDementiveArmorMarathonRunners"/>
		</triggered_effect>
	</append>

</Dementive>
"""

BUFF_LOC = [
    ("buffDementiveArmorSundayBestName", "Sunday Best"),
    ("buffDementiveArmorSundayBestDesc", "Healing 1 health per second."),
    ("buffDementiveArmorFlakVestName", "Flak Vest"),
    ("buffDementiveArmorFlakVestDesc", "25% damage resistance and 20% faster running."),
    ("buffDementiveArmorFlakVestCooldownName", "Flak Vest Recharging"),
    ("buffDementiveArmorFlakVestCooldownDesc", "Your flak vest can't kick in again until this runs out."),
]

# Chance per container opened that one piece drops, same as Weapons Expanded's weapons
LOOT = """<Dementive>

	<append xpath="/lootcontainers/lootprobtemplates">
		<!-- Chance per container opened that one armor piece drops -->
		<lootprobtemplate name="DementiveArmorRaresT1">
			<loot level="1,999999" prob="0.005"/>  <!-- 1 / 200 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT2">
			<loot level="1,999999" prob="0.01"/>  <!-- 1 / 100 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT3">
			<loot level="1,999999" prob="0.02"/>  <!-- 1 / 50 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT4">
			<loot level="1,999999" prob="0.04"/>  <!-- 1 / 25 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT5">
			<loot level="1,999999" prob="0.05"/>  <!-- 1 / 20 -->
		</lootprobtemplate>

		<!-- Quest rewards: the reward "value" is the quest tier. At tiers 4-6 roughly 3% of schematic rewards
		     (about 1 in 20 quests) offer one of the armor pieces instead -->
		<lootprobtemplate name="DementiveArmorQuestRewards">
			<loot level="0,3" prob="0"/>
			<loot level="4,7" prob="0.06"/>
		</lootprobtemplate>
	</append>

	<insertBefore xpath="/lootcontainers/lootgroup[@name='groupScrapCommon']">
		<lootgroup name="groupDementiveArmorAll" count="1" loot_quality_template="armorQualityTemplate">
{items}
		</lootgroup>
	</insertBefore>

	<!-- Wall and picture safes -->
	<append xpath="//lootgroup[@name='groupSmallSafeLoot']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT2" force_prob="true"/>
	</append>
	<!-- Locked Iron Chest -->
	<append xpath="//lootgroup[@name='groupReinforcedChestT3']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT3" force_prob="true"/>
	</append>
	<!-- Locked Small Hardened Chest -->
	<append xpath="//lootgroup[@name='groupHardenedChestT4']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT4" force_prob="true"/>
	</append>
	<!-- Locked Large Hardened Chest -->
	<append xpath="//lootgroup[@name='groupHardenedChestT5']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT5" force_prob="true"/>
	</append>

	<append xpath="//lootgroup[@name='groupZpackBoss']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT3" force_prob="true"/>
	</append>
	<append xpath="//lootgroup[@name='groupZpackStrong']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT2" force_prob="true"/>
	</append>
	<append xpath="//lootgroup[@name='groupZpackReg']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT1" force_prob="true"/>
	</append>

	<append xpath="//lootgroup[@name='groupHiddenStash']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT2" force_prob="true"/>
	</append>

	<append xpath="//lootgroup[@name='groupBuriedTreasure']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorRaresT3" force_prob="true"/>
	</append>

	<append xpath="/lootcontainers/lootgroup[@name='groupQuestSchematics']">
		<item group="groupDementiveArmorAll" loot_prob_template="DementiveArmorQuestRewards"/>
	</append>

</Dementive>
"""

TRADERS = """<Dementive>

	<!-- Traders can stock the armor: each group is a small-weight entry in the vanilla light, medium and heavy armor
	     groups that traders restock from (6 picks each, 8 for Joel), so a typical trader has about a 5% chance per
	     restock to have one piece (Joel about 7%). Each piece's TraderStageTemplate (baseTier2) keeps them to trader
	     stage 50 and up.
	     The game only lets a group use groups defined above it, so these go before groupArmorLight. -->
	<insertBefore xpath="/traders/trader_item_groups/trader_item_group[@name='groupArmorLight']">
{groups}
	</insertBefore>

{appends}
</Dementive>
"""
TRADER_PROB = "0.055"


def van_item(name):
    return re.search(r'\n<item name="%s">.*?\n</item>' % re.escape(name), van, re.S).group(0)


def scale(values, factor):
    out = []
    for v in values.split(","):
        x = round(float(v) * factor, 2)
        out.append(str(int(x)) if x == int(x) else str(x))
    return ",".join(out)


def build(p):
    v = van_item(p["parent"])
    head = [
        f"\t\t<!-- {p['title']} ({p['set']} set) -->",
        f'\t\t<item name="{p["name"]}">',
        f'\t\t\t<property name="Extends" value="{p["parent"]}"/>',
        f'\t\t\t<property name="CustomIcon" value="{p["name"]}"/>',
        f'\t\t\t<property name="DescriptionKey" value="{p["name"]}Desc"/>',
        '\t\t\t<property name="EconomicValue" value="3000"/>',
        '\t\t\t<property name="TraderStageTemplate" value="baseTier2"/>',
    ]
    # Effect groups are children at one tab in vanilla; the mod's item children are at three
    blocks = re.findall(r'\n(\t<effect_group.*?\n\t</effect_group>)', v, re.S)
    if not blocks:
        raise SystemExit(f"{p['name']}: no effect groups on {p['parent']}")
    body = "\n".join("\n".join("\t\t" + l if l else l for l in b.split("\n")) for b in blocks)
    n_armor = 0
    for stat in ("PhysicalDamageResist", "ElementalDamageResist"):
        def boost(m):
            return m.group(1) + scale(m.group(2), ARMOR_BOOST) + m.group(3)
        body, n = re.subn(r'(name="%s" operation="base_add" value=")([\d.,]+)(" tier=")' % stat, boost, body)
        n_armor += n
    body, n_dur = re.subn(r'(name="DegradationMax" operation="base_set" value=")([\d.,]+)(" tier=")',
                          lambda m: m.group(1) + scale(m.group(2), DURABILITY_BOOST) + m.group(3), body)
    if n_armor != 2 or n_dur != 1:
        raise SystemExit(f"{p['name']}: expected 2 armor and 1 durability values, got {n_armor} and {n_dur}")
    sig = [eg(f"{p['title']}", p["signature"])]
    if "extra_signature" in p:
        sig.append(eg(*p["extra_signature"]))
    return "\n".join(head) + "\n\n" + body + "\n\n" + "\n".join(sig) + "\n\t\t</item>\n"


def csv_field(s):
    return '"' + s.replace('"', '""') + '"' if "," in s or '"' in s else s


def loc_row(key, kind, text):
    return f"{key},{kind},,,,{csv_field(text)},,,,,,,,,,,,,"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n"))


items = "<Dementive>\n\n\t<!-- Named armor pieces: rare, only looted or bought. Generated by Scripts/ArmorExpanded/gen_armor.py -->\n\t<append xpath=\"/items\">\n"
items += "\n".join(build(p) for p in PIECES)
items += "\t</append>\n\n</Dementive>\n"

header = "Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"
loc = [header]
for p in PIECES:
    desc = f"{p['lore']}\\n\\n{p['ability']}\\n\\nCounts toward the {p['set']} full set bonus."
    loc.append(loc_row(p["name"], "items,Armor", p["title"]))
    loc.append(loc_row(p["name"] + "Desc", "items,Armor", desc))
for key, text in BUFF_LOC:
    loc.append(loc_row(key, "buffs,Buff", text))

loot = LOOT.replace("{items}", "\n".join(f'\t\t\t<item name="{p["name"]}"/>' for p in PIECES))

groups, appends = [], []
for weight in ("Light", "Medium", "Heavy"):
    members = [p for p in PIECES if p["weight"] == weight]
    groups.append(f'\t\t<trader_item_group name="groupDementiveTraderArmor{weight}" count="1">\n'
                  + "\n".join(f'\t\t\t<item name="{p["name"]}" quality="1,6"/>' for p in members)
                  + "\n\t\t</trader_item_group>")
    appends.append(f"\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='groupArmor{weight}']\">\n"
                   f'\t\t<item group="groupDementiveTraderArmor{weight}" prob="{TRADER_PROB}"/>\n\t</append>\n')
traders = TRADERS.replace("{groups}", "\n".join(groups)).replace("{appends}", "\n".join(appends))

cfg = os.path.join(mod, "Config")
write(os.path.join(cfg, "items.xml"), items)
write(os.path.join(cfg, "buffs.xml"), BUFFS)
write(os.path.join(cfg, "loot.xml"), loot)
write(os.path.join(cfg, "traders.xml"), traders)
write(os.path.join(cfg, "Localization.csv"), "\n".join(loc) + "\n")
print(f"{len(PIECES)} pieces written to {cfg}")

atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
os.makedirs(atlas, exist_ok=True)
for p in PIECES:
    src = os.path.join(game, "Data", "ItemIcons", p["parent"] + ".png")
    subprocess.run([icon_tool, "fx", src, os.path.join(atlas, p["name"] + ".png"), *ICONS[p["name"]]], check=True)
print(f"{len(PIECES)} icons written to {atlas}")

if server:
    scfg = os.path.join(server, "Config")
    os.makedirs(scfg, exist_ok=True)
    tinted = items
    for p in PIECES:
        tinted = tinted.replace(f'<property name="CustomIcon" value="{p["name"]}"/>',
                                f'<property name="CustomIcon" value="{p["parent"]}"/>\n\t\t\t<property name="CustomIconTint" value="{p["tint"]}"/>')
    write(os.path.join(scfg, "items.xml"), tinted)
    for f in os.listdir(cfg):
        if f != "items.xml":
            shutil.copyfile(os.path.join(cfg, f), os.path.join(scfg, f))
    print(f"server-side copy written to {scfg}")
