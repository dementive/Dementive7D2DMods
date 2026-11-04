"""Generate the ArmorExpanded mod (and its server-side copy) from the PIECES and SETS tables below.

Usage: python gen_armor.py <game dir> <ArmorExpanded dir> [<ArmorExpanded-SERVERSIDE dir>]
Each named piece Extends a vanilla armor piece and carries copies of its effect groups (those are not inherited),
with +20% armor rating, +50% durability and a signature effect group. It keeps the vanilla piece's ArmorGroup, so
it counts toward that set's full set bonus, and adds its named set's group for the named-set bonus (SETS).
Rewrites Config/items.xml, buffs.xml, loot.xml, traders.xml, blocks.xml, entityclasses.xml and Localization.csv,
and paints the vanilla icons into UIAtlases/ItemIconAtlas with Scripts/bin/IconTool.exe (ICONS).
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


# Lockpicking and search times are the vanilla time x (1 + the sum of every perc_add), and a total at or below zero
# never finishes (vanilla caps Lucky Looter 5 at -.79 for that reason). So these pieces' cuts are shares of the time
# the perks and other gear leave, worked out once a second (onSelfEquipUpdate) into a "rest" cvar (1 = vanilla time),
# and stacking them never reaches zero. The helmets that cut search time write their cut into .DementiveScavHelmet.
LUCKY_LOOTER = [("perkLuckyLooter", 1, ".1"), ("perkLuckyLooter", 2, ".2"), ("perkLuckyLooter", 3, ".4"),
                ("perkLuckyLooter", 4, ".6"), ("perkLuckyLooter", 5, ".79")]
LOCK_PICKING = [("perkLockPicking", 1, ".17"), ("perkLockPicking", 2, ".2725"), ("perkLockPicking", 3, ".375"),
                ("perkGreatHeistComplete", 1, ".167")]


def update_cvar(cvar, op, value, *reqs):
    body = "".join(f"\n\t{r}" for r in reqs)
    end = f">{body}\n</triggered_effect>" if reqs else "/>"
    return f'<triggered_effect trigger="onSelfEquipUpdate" action="ModifyCVar" cvar="{cvar}" operation="{op}" value="{value}"{end}'


def rest_cvar(cvar, start, perks, extra=None, candy=None):
    """Triggered effects that leave the time the perks (and `extra`, a cvar) leave in `cvar`, never below 0. `candy` is
    Consumables Expanded's Apple Mega Crush share of the same time (a negative perc_add, 0 without it)."""
    out = [update_cvar(cvar, "set", start)]
    for prog, level, value in perks:
        out.append(update_cvar(cvar, "subtract", value,
                               f'<requirement name="ProgressionLevel" progression_name="{prog}" operation="Equals" value="{level}"/>'))
    if extra:
        out.append(update_cvar(cvar, "subtract", "@" + extra))
    if candy:
        out.append(update_cvar(cvar, "add", "@" + candy))
    out.append(update_cvar(cvar, "set", "0", f'<requirement name="CVarCompare" cvar="{cvar}" operation="LT" value="0"/>'))
    return "\n".join(out)


def share(cvar, rest, cut):
    """`cvar` = -cut x `rest`: a perc_add that cuts `cut` of the time left."""
    return update_cvar(cvar, "set", "@" + rest) + "\n" + update_cvar(cvar, "multiply", f"-{cut}")


SCAV_REST = rest_cvar(".DementiveScavRest", "1", LUCKY_LOOTER, ".DementiveScavHelmet", ".DementiveScavCandy")


def scav_helmet(values):
    """The search time cut of a helmet (its vanilla tiered values, as positive numbers) for SCAV_REST."""
    return ('<triggered_effect trigger="onSelfEquipUpdate" action="ModifyCVar" cvar=".DementiveScavHelmet" operation="set" value="%s"/>\n'
            '<triggered_effect trigger="onSelfEquipStop" action="ModifyCVar" cvar=".DementiveScavHelmet" operation="set" value="0"/>' % values)


# Sunday Overalls: (event, name, cvar) for food, drinks and drinking from water by hand
FOOD_CVARS = [("onSelfPrimaryActionEnd", "Food", "$foodAmountAdd"), ("onSelfPrimaryActionEnd", "Water", "$waterAmountAdd"),
              ("onSelfAction2End", "Water", "$waterAmountAdd")]


def food_boost(trigger, name, cvar):
    """Adds 25% of what the item just added to `cvar` (.Dementive<name>Before is noted by the player class first)."""
    gain = f".Dementive{name}Gain"
    return (f'<triggered_effect trigger="{trigger}" action="ModifyCVar" cvar="{gain}" operation="set" value="@{cvar}"/>\n'
            f'<triggered_effect trigger="{trigger}" action="ModifyCVar" cvar="{gain}" operation="subtract" value="@.Dementive{name}Before"/>\n'
            f'<triggered_effect trigger="{trigger}" action="ModifyCVar" cvar="{gain}" operation="multiply" value=".25"/>\n'
            f'<triggered_effect trigger="{trigger}" action="ModifyCVar" cvar="{cvar}" operation="add" value="@{gain}">\n'
            f'\t<requirement name="CVarCompare" cvar="{gain}" operation="GT" value="0"/>\n</triggered_effect>')


# Named-set bonuses that need the player to be the one moving or hurting: only the owner's client knows that
LOCAL = '<requirement name="IsLocalPlayer"/>'
KILL = '<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>'


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
        # Both time cuts are shares of what's left (see LUCKY_LOOTER). The lock one starts from the gloves' own vanilla
        # cut, and also works out Master Thief's share, since the set always has these gloves
        signature="""
<passive_effect name="LockPickTime" operation="perc_add" value="@.DementiveLockPickpocket"/>
<passive_effect name="LockPickBreakChance" operation="perc_add" value="-.5"/>
<passive_effect name="ScavengingTime" operation="perc_add" value="@.DementiveScavPickpocket"/>
""" + rest_cvar(".DementiveLockRest", ".98,.96,.94,.92,.9,.8", LOCK_PICKING, candy=".DementiveLockCandy") + "\n"
          + share(".DementiveLockPickpocket", ".DementiveLockRest", ".5") + "\n"
          + share(".DementiveLockThief", ".DementiveLockRest", ".25") + "\n"
          + SCAV_REST + "\n" + share(".DementiveScavPickpocket", ".DementiveScavRest", ".25"),
        lore="Thin, supple gloves made for quick fingers and quiet work. No lock or crate stands in your way for long.",
        ability="Lockpicking is 50% faster and breaks 50% fewer lockpicks. Searching containers is 25% faster.",
    ),
    dict(
        name="DementiveArmorMarathonRunners", title="Marathon Runners", parent="armorAthleticBoots", set="Athletic",
        weight="Light", tint="#00BFFF",
        # The fall damage part is in buffs.xml: buffPlayerFallingDamage checks for buffDementiveArmorMarathonRunners
        signature="""
<!-- 30% of the drain: sprinting is 10 x (1 - 1.45) = -4.5 a second and fast swimming 10 x (1 - 1.9) = -9 -->
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".135" tags="running"/>
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".27" tags="swimmingRun"/>
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
        # Both only while holding a mining tool, like the vanilla Miner helmet's bonus (oreWoodHarvest also tags
        # tree wood and dug clay). Swing stamina is asked for with the action tags only
        signature="""
<passive_effect name="HarvestCount" operation="perc_add" value=".25" tags="oreWoodHarvest">
	<requirement name="HoldingItemHasTags" tags="miningTool"/>
</passive_effect>
<passive_effect name="StaminaLoss" operation="perc_add" value="-.25" tags="primary,secondary">
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

    # *** The rest of each set. weight and tint come from SETS ***
    # Lumberjack. Trees have no tag of their own (they are "wood" like any wooden block), so Big Jim's covers all wood
    dict(
        name="DementiveArmorBigJimsEarflaps", title="Big Jim's Earflaps", parent="armorLumberjackHelmet", set="Lumberjack",
        signature="""
<passive_effect name="DamageModifier" operation="perc_add" value=".4" tags="wood">
	<requirement name="HoldingItemHasTags" tags="axe,chainsaw"/>
</passive_effect>""",
        lore="A fur-lined trapper hat with the earflaps tied up, sized for a very big head. Big Jim could drop a pine before breakfast.",
        ability="Axes and chainsaws cut trees and other wood 40% faster.",
    ),
    dict(
        name="DementiveArmorRedFlannel", title="Red Flannel", parent="armorLumberjackOutfit", set="Lumberjack",
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="ModifyStats" stat="Stamina" operation="add" value="15">
	<requirement name="ItemHasTags" tags="axe,chainsaw"/>
	{KILL}
</triggered_effect>
<passive_effect name="StaminaLoss" operation="perc_add" value="-.25" tags="secondary">
	<requirement name="HoldingItemHasTags" tags="axe,chainsaw"/>
</passive_effect>""",
        lore="A faded red flannel shirt that smells of sawdust and coffee. Hard work never seemed to tire out the man who wore it.",
        ability="Axe and chainsaw kills restore 15 stamina, and power attacks with them cost 25% less stamina.",
    ),
    dict(
        name="DementiveArmorLogrollers", title="Logrollers", parent="armorLumberjackBoots", set="Lumberjack",
        signature="""
<passive_effect name="RunSpeed" operation="perc_add" value=".1">
	<requirement name="HoldingItemHasTags" tags="axe,chainsaw"/>
</passive_effect>
<!-- 20% of sprinting's 10 x (1 - 1.45) = -4.5 a second, like Marathon Runners -->
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".09" tags="running"/>""",
        lore="Spiked logger's boots from a river drive champion. Whoever wore them never once fell in.",
        ability="Run 10% faster with an axe or chainsaw in hand. Sprinting uses 20% less stamina.",
    ),

    # Preacher. A first aid bandage, kit or aloe cream adds to medicalRegHealthAmount and sets medRegHealthIncSpeed;
    # buffHealHealth then heals that speed every second while taking 2 off the amount, so the speed scales the total.
    # Armor gets the event after the held item, so the item has already set it (the plain bandage heals nothing)
    dict(
        name="DementiveArmorReverendsHat", title="The Reverend's Hat", parent="armorPreacherHelmet", set="Preacher",
        # Read by the server when a zombie dies: the class's LootDropProb x the killer's
        signature="""
<passive_effect name="LootDropProb" operation="perc_add" value=".25"/>""",
        lore="A wide-brimmed black hat from a circuit preacher. The dead seem to give up a little more in his presence.",
        ability="Zombies you kill are 25% more likely to drop a loot bag.",
    ),
    dict(
        name="DementiveArmorLayingOnOfHands", title="Laying On of Hands", parent="armorPreacherGloves", set="Preacher",
        signature="""
<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="medRegHealthIncSpeed" operation="set" value="@$medicRegHealthIncreaseSpeed">
	<requirement name="HoldingItemHasTags" tags="medical"/>
	<requirement name="CVarCompare" cvar="medicalRegHealthAmount" operation="GT" value="0"/>
</triggered_effect>
<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="medRegHealthIncSpeed" operation="multiply" value="1.4">
	<requirement name="HoldingItemHasTags" tags="medical"/>
	<requirement name="CVarCompare" cvar="medicalRegHealthAmount" operation="GT" value="0"/>
</triggered_effect>""",
        lore="Soft white gloves worn for blessings and bandaging alike. Wounds close a little faster under them.",
        ability="First aid bandages, first aid kits and aloe cream heal you 40% more.",
    ),
    dict(
        name="DementiveArmorPilgrimsShoes", title="Pilgrim's Shoes", parent="armorPreacherBoots", set="Preacher",
        # infectionCounter runs up to $infectionMaxDuration = 25200 (100%), so 1260 is 5%
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="ModifyCVar" cvar="infectionCounter" operation="subtract" value="1260">
	<requirement name="EntityTagCompare" target="other" tags="zombie"/>
	<requirement name="CVarCompare" cvar="infectionCounter" operation="GT" value="0"/>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="25"/>
</triggered_effect>""",
        lore="Simple buckled shoes that have walked a thousand miles of bad road. Every soul laid to rest lightens the load.",
        ability="Each zombie you kill has a 25% chance to cure 5% of your infection.",
    ),

    # Rogue. The cap's container bonus is a stack size: counts are rounded down, so single items stay single
    dict(
        name="DementiveArmorSecondStoryCap", title="Second-Story Cap", parent="armorRogueHelmet", set="Rogue",
        signature="""
<passive_effect name="LootQuantity" operation="perc_add" value=".15"/>
""" + scav_helmet(".02,.04,.06,.08,.1,.19"),
        lore="A snug black watch cap from a cat burglar who only ever worked the top floor. The best stuff is always upstairs.",
        ability="Stacks of items in the containers you search are 15% bigger.",
    ),
    dict(
        name="DementiveArmorGetawayJacket", title="Getaway Jacket", parent="armorRogueOutfit", set="Rogue",
        signature="""
<requirement name="StatComparePercCurrentToMax" stat="health" operation="LT" value=".5"/>
	<passive_effect name="RunSpeed" operation="perc_add" value=".25"/>""",
        lore="A dark windbreaker made for running from trouble. It's never slower than when you need it most.",
        ability="Below half health you run 25% faster.",
    ),
    dict(
        name="DementiveArmorRooftopRunners", title="Rooftop Runners", parent="armorRogueBoots", set="Rogue",
        # FallDamageReduction is taken off the impact speed before anything reads it: an 8 m fall lands at about
        # .218 and damage starts at .1923. The landing sound comes after onSelfFallImpact, so the buff silences it
        signature="""
<passive_effect name="FallDamageReduction" operation="base_subtract" value=".03"/>
<triggered_effect trigger="onSelfFallImpact" action="AddBuff" buff="buffDementiveArmorRooftopRunners"/>""",
        lore="Soft-soled climbing shoes from someone who traveled by rooftop. The street was for amateurs.",
        ability="Falls of up to 8 meters don't hurt at all, and zombies can't hear you land.",
    ),

    # Athletic
    dict(
        name="DementiveArmorCoachsVisor", title="Coach's Visor", parent="armorAthleticHelmet", set="Athletic",
        # Stamina comes back at a base 10 a second, read with the movement tag; this leaves sprinting's drain alone
        signature="""
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".25" tags="idle,walking"/>""",
        lore="A sweat-stained coach's visor with a whistle still clipped to it. Catch your breath and get back out there.",
        ability="Stamina comes back 25% faster.",
    ),
    dict(
        name="DementiveArmorGripTapeGloves", title="Grip Tape Gloves", parent="armorAthleticGloves", set="Athletic",
        signature="""
<passive_effect name="StaminaLoss" operation="perc_add" value="-.15" tags="primary,secondary"/>""",
        lore="Gloves with grip tape wrapped around the palms. Every swing feels lighter.",
        ability="Every swing and shot costs 15% less stamina.",
    ),
    dict(
        name="DementiveArmorVarsityJacket", title="Varsity Jacket", parent="armorAthleticOutfit", set="Athletic",
        # Incoming damage is worked out on the server, which can't tell a client player is sprinting, so the owner
        # keeps a sprint flag buff (synced) up to date. GeneralDamageResist is read once per hit and capped at 1
        signature="""
<passive_effect name="GeneralDamageResist" operation="base_add" value="1">
	<requirement name="HasBuff" buff="buffDementiveArmorVarsitySprint"/>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LT" value="15"/>
</passive_effect>
<triggered_effect trigger="onSelfEquipStart" action="AddBuff" buff="buffDementiveArmorVarsityJacket"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveArmorVarsityJacket"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveArmorVarsitySprint"/>""",
        lore="A letterman jacket from a state champion sprinter. Nobody could lay a hand on him once he got going.",
        ability="While you sprint, 15% of hits on you do no damage.",
    ),

    # Enforcer. 44enforcer is the tag only the .44 Magnum and Desert Vulture carry
    dict(
        name="DementiveArmorDonsPinstripes", title="The Don's Pinstripes", parent="armorEnforcerOutfit", set="Enforcer",
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorDonsPinstripes">
	<requirement name="ItemHasTags" tags="44enforcer"/>
	{KILL}
</triggered_effect>""",
        lore="A tailored pinstripe suit with a carnation still in the lapel. The Don settled his disputes personally.",
        ability=".44 Magnum and Desert Vulture kills give you 5 seconds of 25% more damage.",
    ),
    dict(
        name="DementiveArmorWheelmansGloves", title="Wheelman's Gloves", parent="armorEnforcerGloves", set="Enforcer",
        # Vehicle.CalcEffects reads these from the driver, with the vehicle's tags (every vehicle has "vehicle")
        signature="""
<passive_effect name="VehicleVelocityMaxPer" operation="perc_add" value=".15" tags="vehicle"/>
<passive_effect name="VehicleMotorTorquePer" operation="perc_add" value=".15" tags="vehicle"/>
<passive_effect name="VehicleEntityDamage" operation="perc_add" value=".5" tags="vehicle"/>""",
        lore="Thin leather driving gloves with the knuckles cut out. The getaway driver never once got caught.",
        ability="Vehicles you drive go 15% faster and hit zombies 50% harder.",
    ),
    dict(
        name="DementiveArmorTwoToneWingtips", title="Two-Tone Wingtips", parent="armorEnforcerBoots", set="Enforcer",
        # DamageModifier multiplies the finished damage (the player class sets it to 1), so +1 is a true double
        signature="""
<passive_effect name="DamageModifier" operation="perc_add" value="1" tags="entity">
	<requirement name="HoldingItemHasTags" tags="pistol,revolver"/>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="10"/>
</passive_effect>""",
        lore="Polished black and white wingtips that never once got scuffed. Their owner always made the first shot count.",
        ability="Pistol and revolver hits have a 10% chance to deal double damage.",
    ),

    # Farmer. wildCropsHarvest is the wild plants' own drop tag (the player class sets their HarvestCount to 1)
    dict(
        name="DementiveArmorSunBonnet", title="Sun Bonnet", parent="armorFarmerHelmet", set="Farmer",
        signature="""
<passive_effect name="HarvestCount" operation="base_add" value="1" tags="wildCropsHarvest"/>""",
        lore="A gingham sun bonnet from a farm wife who knew every wild plant in the county. She never came home with an empty basket.",
        ability="Wild plants (berries, cotton, yucca, flowers, mushrooms) give one extra when picked.",
    ),
    dict(
        name="DementiveArmorOldBessiesGloves", title="Old Bessie's Gloves", parent="armorFarmerGloves", set="Farmer",
        signature="""
<passive_effect name="HarvestCount" operation="perc_add" value=".5" tags="butcherHarvest"/>""",
        lore="Heavy work gloves named after the best cow the farm ever had. They know how to make the most of an animal.",
        ability="Butchering animals gives 50% more meat, hide, fat and bone.",
    ),
    dict(
        name="DementiveArmorSundayOveralls", title="Sunday Overalls", parent="armorFarmerOutfit", set="Farmer",
        # Food and drinks add to $foodAmountAdd / $waterAmountAdd, which drain into the stats over time. The player
        # class (entityclasses.xml) notes them before the item runs, so this adds 25% of just what the item added
        signature="\n".join(food_boost(*f) for f in FOOD_CVARS),
        lore="Clean overalls saved for church and the county fair. A good meal goes further when you're wearing them.",
        ability="Food and drinks fill you 25% more.",
    ),

    # Biker. bikerSetBonus is the tag only minibikes and motorcycles carry
    dict(
        name="DementiveArmorSkullLid", title="Skull Lid", parent="armorBikerHelmet", set="Biker",
        signature="""
<passive_effect name="VehicleVelocityMaxPer" operation="perc_add" value=".15" tags="bikerSetBonus"/>
<passive_effect name="VehicleMotorTorquePer" operation="perc_add" value=".15" tags="bikerSetBonus"/>""",
        lore="A beat-up half helmet with a skull painted on the back. It's been down more highways than most maps.",
        ability="Minibikes and motorcycles go 15% faster.",
    ),
    dict(
        name="DementiveArmorKnuckleDusters", title="Knuckle Dusters", parent="armorBikerGloves", set="Biker",
        # The streak is a cvar the buff's damage bonus reads; a hit within 2 s (the buff is still up) adds 5%. Melee
        # damage is worked out on the attacker's machine, so a local cvar is fine
        signature="""
<triggered_effect trigger="onSelfAttackedOther" action="ModifyCVar" cvar=".DementiveKnuckleStreak" operation="add" value=".05">
	<requirement name="ItemHasTags" tags="melee"/>
	<requirement name="HasBuff" buff="buffDementiveArmorKnuckleDusters"/>
</triggered_effect>
<triggered_effect trigger="onSelfAttackedOther" action="ModifyCVar" cvar=".DementiveKnuckleStreak" operation="set" value=".05">
	<requirement name="ItemHasTags" tags="melee"/>
	<requirement name="!HasBuff" buff="buffDementiveArmorKnuckleDusters"/>
</triggered_effect>
<triggered_effect trigger="onSelfAttackedOther" action="ModifyCVar" cvar=".DementiveKnuckleStreak" operation="set" value=".25">
	<requirement name="CVarCompare" cvar=".DementiveKnuckleStreak" operation="GT" value=".25"/>
</triggered_effect>
<triggered_effect trigger="onSelfAttackedOther" action="AddBuff" buff="buffDementiveArmorKnuckleDusters">
	<requirement name="ItemHasTags" tags="melee"/>
</triggered_effect>""",
        lore="Fingerless riding gloves with brass studs over the knuckles. Once the fight gets going, it only gets worse.",
        ability="Each melee hit within 2 seconds of the last adds 5% damage, up to 25%.",
    ),
    dict(
        name="DementiveArmorSteelToeStompers", title="Steel-Toe Stompers", parent="armorBikerBoots", set="Biker",
        # Same power attack event and knockdown as the vanilla Skull Crusher perk; it fires before the damage
        signature="""
<triggered_effect trigger="onSelfSecondaryActionRayHit" action="AddBuff" target="other" target_tags="zombie" buff="buffInjuryKnockdown01">
	<requirement name="ItemHasTags" tags="club,sledge"/>
	<requirement name="IsAlive" target="other"/>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="20"/>
</triggered_effect>""",
        lore="Steel-toed riding boots that have kicked in more doors than a SWAT team. Put your weight behind it.",
        ability="Club and sledgehammer power attacks have a 20% chance to knock zombies down.",
    ),

    # Scavenger. Salvage tools carry salvageTool (wrench, ratchet, impact driver)
    dict(
        name="DementiveArmorKnuckleBusterMitts", title="Knuckle-Buster Mitts", parent="armorScavengerGloves", set="Scavenger",
        signature="""
<passive_effect name="BlockDamage" operation="perc_add" value=".25" tags="salvageTool"/>""",
        lore="Padded mechanic's mitts patched with duct tape. Busted knuckles are a thing of the past.",
        ability="Wrenches, ratchets and impact drivers salvage 25% faster.",
    ),
    dict(
        name="DementiveArmorPackRatParka", title="Pack Rat Parka", parent="armorScavengerOutfit", set="Scavenger",
        # A share of the search time left, like Pickpocket's Gloves (see LUCKY_LOOTER)
        signature="""
<passive_effect name="ScavengingTime" operation="perc_add" value="@.DementiveScavPackRat"/>
""" + SCAV_REST + "\n" + share(".DementiveScavPackRat", ".DementiveScavRest", ".4"),
        lore="A huge parka with more pockets than anyone could count. Its owner never walked past a trash can.",
        ability="Search containers and zombie loot bags 40% faster.",
    ),
    dict(
        name="DementiveArmorDumpsterDivers", title="Dumpster Divers", parent="armorScavengerBoots", set="Scavenger",
        # Swings set their stamina cost with base_set on the held item; equipment comes after it
        signature="""
<passive_effect name="StaminaLoss" operation="base_set" value="0" tags="primary,secondary">
	<requirement name="HoldingItemHasTags" tags="salvageTool"/>
</passive_effect>""",
        lore="Rubber boots that have waded through every landfill in the state. Salvaging just doesn't wear you out in them.",
        ability="Wrenches, ratchets and impact drivers use no stamina.",
    ),

    # Ranger. There's no aiming cvar; the owner's aim events add and remove a buff (synced to the server)
    dict(
        name="DementiveArmorLawmansStetson", title="Lawman's Stetson", parent="armorRangerHelmet", set="Ranger",
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorLawmansStetson">
	<requirement name="HitLocation" body_parts="Head"/>
	{KILL}
</triggered_effect>""",
        lore="A sweat-stained Stetson with a bullet hole through the crown. The lawman who wore it never missed twice.",
        ability="A headshot kill gives you 5 seconds of 20% faster reloads and 15% faster running.",
    ),
    dict(
        name="DementiveArmorLongRiderDuster", title="Long Rider Duster", parent="armorRangerOutfit", set="Ranger",
        signature="""
<triggered_effect trigger="onSelfAimingGunStart" action="AddBuff" buff="buffDementiveArmorLongRiderDuster"/>
<triggered_effect trigger="onSelfAimingGunStop" action="RemoveBuff" buff="buffDementiveArmorLongRiderDuster"/>
<triggered_effect trigger="onSelfEquipStart" action="RemoveBuff" buff="buffDementiveArmorLongRiderDuster"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveArmorLongRiderDuster"/>""",
        lore="A long canvas duster that has stood its ground in a hundred showdowns. Steady hands, steady nerves.",
        ability="While aiming down sights you take 15% less damage.",
    ),
    dict(
        name="DementiveArmorTrailBoots", title="Trail Boots", parent="armorRangerBoots", set="Ranger",
        signature="""
<triggered_effect trigger="onSelfAimingGunStart" action="AddBuff" buff="buffDementiveArmorTrailBoots"/>
<triggered_effect trigger="onSelfAimingGunStop" action="RemoveBuff" buff="buffDementiveArmorTrailBoots"/>
<triggered_effect trigger="onSelfEquipStart" action="RemoveBuff" buff="buffDementiveArmorTrailBoots"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveArmorTrailBoots"/>""",
        lore="Worn riding boots from a tracker who could follow a trail across bare rock. Keep moving, keep your aim.",
        ability="Move 25% faster while aiming down sights.",
    ),

    # Commando. Explosions use the thrower's Explosion* effects with the item's tags, on the server.
    # DementiveArmorGrenade is added to the grenades and pipe bomb in items.xml
    dict(
        name="DementiveArmorBlastHelmet", title="Blast Helmet", parent="armorCommandoHelmet", set="Commando",
        signature="""
<passive_effect name="ExplosionIncomingDamage" operation="perc_add" value="-.5"/>
<passive_effect name="ExplosionRadius" operation="perc_add" value=".25" tags="DementiveArmorGrenade"/>""",
        lore="A scorched demolition helmet with a cracked visor. The blast always seems to go somewhere else.",
        ability="Explosions hurt you 50% less, and grenades and pipe bombs you throw blast 25% wider.",
    ),
    dict(
        name="DementiveArmorTriggerDiscipline", title="Trigger Discipline", parent="armorCommandoGloves", set="Commando",
        signature="""
<passive_effect name="KickDegreesVerticalMin" operation="perc_add" value="-.3" tags="gun"/>
<passive_effect name="KickDegreesVerticalMax" operation="perc_add" value="-.3" tags="gun"/>
<passive_effect name="KickDegreesHorizontalMin" operation="perc_add" value="-.3" tags="gun"/>
<passive_effect name="KickDegreesHorizontalMax" operation="perc_add" value="-.3" tags="gun"/>
<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".15" tags="gun"/>""",
        lore="Worn shooting gloves from a drill instructor who never once raised his voice. Breathe, aim, squeeze.",
        ability="Guns kick 30% less and reload 15% faster.",
    ),
    dict(
        name="DementiveArmorJumpBoots", title="Jump Boots", parent="armorCommandoBoots", set="Commando",
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorJumpBoots">
	{KILL}
</triggered_effect>""",
        lore="Paratrooper's jump boots, laced tight and spit-shined. Once the shooting starts, you keep moving.",
        ability="Kills give you 4 seconds of 15% faster running.",
    ),

    # Assassin. Bows read their draw time from RoundsPerMinute when they are equipped, like the Archery perk's
    dict(
        name="DementiveArmorSilentHands", title="Silent Hands", parent="armorAssassinGloves", set="Assassin",
        signature="""
<passive_effect name="RoundsPerMinute" operation="perc_add" value=".25" tags="bowDrawPenalty"/>
<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".25" tags="crossbow"/>
<passive_effect name="ProjectileVelocity" operation="perc_add" value=".25" tags="perkArchery"/>""",
        lore="Thin black archer's gloves, worn shiny at the fingertips. The string makes no sound at all.",
        ability="Bows draw and crossbows reload 25% faster, and arrows and bolts fly 25% faster. (Re-equip a bow for the faster draw.)",
    ),
    dict(
        name="DementiveArmorShroud", title="Shroud", parent="armorAssassinOutfit", set="Assassin",
        signature="""
<passive_effect name="NoiseMultiplier" operation="perc_add" value="-.3"/>""",
        lore="A hooded black cloak that seems to swallow sound. Nobody hears it coming, and nobody hears it leave.",
        ability="You make 30% less noise.",
    ),
    dict(
        name="DementiveArmorGhostSteps", title="Ghost Steps", parent="armorAssassinBoots", set="Assassin",
        # Crouch-walking reads CrouchSpeed, crouch-sprinting reads WalkSpeed
        signature="""
<passive_effect name="CrouchSpeed" operation="perc_add" value=".25"/>
<passive_effect name="WalkSpeed" operation="perc_add" value=".25">
	<requirement name="CVarCompare" cvar="_crouching" operation="Equals" value="1"/>
</passive_effect>""",
        lore="Split-toe boots with felt soles. Where they walk, there are no footprints.",
        ability="Move 25% faster while crouched.",
    ),

    # Miner. miningTool also tags the stone axes, so Rock Splitters leaves axes out
    dict(
        name="DementiveArmorRockSplitters", title="Rock Splitters", parent="armorMinerGloves", set="Miner",
        signature="""
<passive_effect name="EntityDamage" operation="perc_add" value=".4" tags="miningTool">
	<requirement name="!HoldingItemHasTags" tags="axe"/>
</passive_effect>""",
        lore="Cracked leather mining gloves with steel plates sewn over the knuckles. Rock or bone, it all splits the same.",
        ability="Pickaxes and augers deal 40% more damage to zombies and animals.",
    ),
    dict(
        name="DementiveArmorBlastingCoveralls", title="Blasting Coveralls", parent="armorMinerOutfit", set="Miner",
        # Thrown, placed and fired explosives (not land mines or barrels, which have no owner)
        signature="""
<passive_effect name="ExplosionBlockDamage" operation="perc_add" value=".25" tags="explosion"/>""",
        lore="Scorched coveralls from a powder monkey who loved his work a little too much. Stand back.",
        ability="Explosives you throw, place or fire deal 25% more damage to blocks.",
    ),
    dict(
        name="DementiveArmorCanaryBoots", title="Canary Boots", parent="armorMinerBoots", set="Miner",
        signature="""
<passive_effect name="RunSpeed" operation="perc_add" value=".1">
	<requirement name="HoldingItemHasTags" tags="miningTool"/>
</passive_effect>""",
        lore="Bright yellow rubber boots from a miner who always made it out first. When the canary stops singing, run.",
        ability="Run 10% faster with a mining tool in hand.",
    ),

    # Nomad. Murky water, raw meat, rotting flesh and the like all give dysentery through these two catch buffs
    dict(
        name="DementiveArmorSandVeil", title="Sand Veil", parent="armorNomadHelmet", set="Nomad",
        signature="""
<passive_effect name="BuffResistance" operation="base_add" value="1" tags="buffDysenteryCatchFood,buffDysenteryCatchDrink"/>""",
        lore="A sand-colored veil wrapped around a desert hat. Its owner drank from puddles and ate whatever crawled by, and never got sick.",
        ability="Murky water and raw or spoiled food never give you dysentery.",
    ),
    dict(
        name="DementiveArmorGeigerGloves", title="Geiger Gloves", parent="armorNomadGloves", set="Nomad",
        # Charged and infernal zombies are ferals too. The attacker is "other" when incoming damage is resisted
        signature="""
<passive_effect name="EntityDamage" operation="perc_add" value=".25">
	<requirement name="EntityTagCompare" target="other" tags="feral,radiated"/>
</passive_effect>
<passive_effect name="GeneralDamageResist" operation="base_add" value=".2">
	<requirement name="EntityTagCompare" target="other" tags="feral,radiated"/>
</passive_effect>""",
        lore="Lead-lined gloves with a cracked radiation badge on the cuff. The worst of the wasteland can't get through.",
        ability="Deal 25% more damage to feral and radiated zombies, and take 20% less damage from them.",
    ),
    dict(
        name="DementiveArmorLongWalkBoots", title="Long Walk Boots", parent="armorNomadBoots", set="Nomad",
        # walking is the movement tag for moving without sprinting. Health over time costs a little water, as usual
        signature="""
<passive_effect name="HealthChangeOT" operation="base_add" value=".25">
	<requirement name="EntityHasMovementTag" tags="walking"/>
</passive_effect>""",
        lore="Resoled desert boots that have walked across three states. Every mile mends you a little.",
        ability="While walking (not sprinting) you regain 1 health every 4 seconds.",
    ),

    # Nerd. Junk turrets, sledges and drones deal damage with their owner's effects and their item's tags
    dict(
        name="DementiveArmorSolderingGloves", title="Soldering Gloves", parent="armorNerdGloves", set="Nerd",
        signature="""
<passive_effect name="EntityDamage" operation="perc_add" value=".25" tags="perkTurrets,stunBaton"/>""",
        lore="Heat-scarred gloves from a tinkerer who built robots out of junk. Everything he soldered hit harder.",
        ability="Stun batons and your junk turrets, junk sledges and drones deal 25% more damage.",
    ),
    dict(
        name="DementiveArmorLabCoat", title="Lab Coat", parent="armorNerdOutfit", set="Nerd",
        # A hit that kills doesn't count. onSelfAttackedOther never fires on damage-over-time ticks
        signature="""
<triggered_effect trigger="onSelfAttackedOther" action="ModifyCVar" cvar=".DementiveLabCoatHits" operation="add" value="1">
	<requirement name="IsAlive" target="other"/>
	<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
</triggered_effect>
<triggered_effect trigger="onSelfAttackedOther" action="AddBuff" target="other" buff="buffDementiveArmorLabCoatShock">
	<requirement name="CVarCompare" target="self" cvar=".DementiveLabCoatHits" operation="GTE" value="8"/>
	<requirement name="IsAlive" target="other"/>
	<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
</triggered_effect>
<triggered_effect trigger="onSelfAttackedOther" action="ModifyCVar" cvar=".DementiveLabCoatHits" operation="set" value="0">
	<requirement name="CVarCompare" cvar=".DementiveLabCoatHits" operation="GTE" value="8"/>
	<requirement name="IsAlive" target="other"/>
	<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
</triggered_effect>""",
        lore="A singed lab coat with a pocket full of capacitors. Static crackles off it every time you swing.",
        ability="Every 8th hit you land shocks the target for 2 seconds.",
    ),
    dict(
        name="DementiveArmorKineticSneakers", title="Kinetic Sneakers", parent="armorNerdBoots", set="Nerd",
        # The charging is in buffDementiveArmorKineticSneakers, on the owner's machine (where sprinting is known)
        signature="""
<triggered_effect trigger="onSelfEquipStart" action="AddBuff" buff="buffDementiveArmorKineticSneakers"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveArmorKineticSneakers"/>""",
        lore="Prototype sneakers with coils in the soles and a battery in each heel. Run long enough and they bite back.",
        ability="Sprinting for 5 seconds charges your next hit to deal double damage.",
    ),

    # Raider. The War Crown stacks are three buffs (buffs sync to the server, which resists incoming damage)
    dict(
        name="DementiveArmorWarCrown", title="War Crown", parent="armorRaiderHelmet", set="Raider",
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorWarCrown3">
	<requirement name="HasBuff" buff="buffDementiveArmorWarCrown2"/>
	{KILL}
</triggered_effect>
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorWarCrown2">
	<requirement name="HasBuff" buff="buffDementiveArmorWarCrown1"/>
	{KILL}
</triggered_effect>
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorWarCrown1">
	{KILL}
</triggered_effect>""",
        lore="A crown of welded rebar and bike chain, worn by a raider king. Every kill makes his court stronger.",
        ability="Each kill gives you 3 seconds of 10% damage resistance, stacking up to three times.",
    ),
    dict(
        name="DementiveArmorSpikedGauntlets", title="Spiked Gauntlets", parent="armorRaiderGloves", set="Raider",
        signature=f"""
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveArmorSpikedGauntlets">
	<requirement name="ItemHasTags" tags="melee"/>
	{KILL}
</triggered_effect>""",
        lore="Spiked steel gauntlets hammered out of road signs. One kill only makes them hungrier.",
        ability="Melee kills give you 3 seconds of 30% faster attacks.",
    ),
    dict(
        name="DementiveArmorScrapPlate", title="Scrap Plate", parent="armorRaiderOutfit", set="Raider",
        signature="""
<passive_effect name="BuffResistance" operation="base_add" value="1" tags="buffInjuryBleeding,buffInjuryBleedingOne,buffInjuryBleedingTwo,buffInjuryBleedingBarbedWire"/>""",
        lore="Car doors and stop signs riveted into a breastplate. Claws and teeth just scrape off it.",
        ability="You can't be made to bleed.",
    ),

    # Primitive (all four new). There's no vanilla piece bonus or set bonus. The stone and bone weapons share no tag,
    # so each pair has to match together
    dict(
        name="DementiveArmorCastawaysHeadband", title="Castaway's Headband", parent="armorPrimitiveHelmet", set="Primitive",
        signature="".join(f"""
<passive_effect name="EntityDamage" operation="perc_add" value=".25" tags="T0,{tag}" match_all_tags="true"/>""" for tag in ("axe", "spearSkill", "sledge", "knife", "bow")),
        lore="A strip of sun-bleached cloth tied around the forehead. Its owner made everything from what washed ashore.",
        ability="Stone and bone weapons and tools (stone axe, stone spear, stone sledgehammer, bone knife, primitive bow) deal 25% more damage.",
    ),
    dict(
        name="DementiveArmorLuckyRags", title="Lucky Rags", parent="armorPrimitiveOutfit", set="Primitive",
        # Read once per hit; the window is the other end of the roll from the Varsity Jacket's
        signature="""
<passive_effect name="GeneralDamageResist" operation="base_add" value="1">
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="GTE" value="90"/>
</passive_effect>""",
        lore="Patched-together rags that have somehow survived everything. So has whoever wore them.",
        ability="10% of hits on you do no damage.",
    ),
    dict(
        name="DementiveArmorWrappedFists", title="Wrapped Fists", parent="armorPrimitiveGloves", set="Primitive",
        # perkBrawler is on bare hands and the knuckles only
        signature="""
<passive_effect name="EntityDamage" operation="perc_add" value=".5" tags="perkBrawler"/>""",
        lore="Hands wrapped in strips of hide, stiff with old blood. Who needs a weapon?",
        ability="Bare hands and knuckles deal 50% more damage.",
    ),
    dict(
        name="DementiveArmorBareWraps", title="Bare Wraps", parent="armorPrimitiveBoots", set="Primitive",
        # Swimming reads WalkSpeed, swim-sprinting RunSpeed (which already has the 10%)
        signature="""
<passive_effect name="RunSpeed" operation="perc_add" value=".1"/>
<passive_effect name="WalkSpeed" operation="perc_add" value=".25">
	<requirement name="EntityHasMovementTag" tags="swimming"/>
</passive_effect>
<passive_effect name="RunSpeed" operation="perc_add" value=".15">
	<requirement name="EntityHasMovementTag" tags="swimmingRun"/>
</passive_effect>""",
        lore="Foot wraps of plant fiber and leather. Lighter than any boot, on land or in the water.",
        ability="Run 10% faster and swim 25% faster.",
    ),
]

# Named-set bonuses. Each named piece is also in ArmorGroup groupDementiveNamed<set>, which the engine counts from what
# is worn (like the vanilla sets), and buffStatusCheck02 gives buffDementiveArmorSet<set> while all four are worn, the
# same way it gives the vanilla set bonuses. `buff` is the set buff's content. weight is the trader group, tint the
# server-side icon tint and icon_color the set buff's. vanilla is whether the vanilla set has a full set bonus
SETS = {
    "Lumberjack": dict(
        title="Paul's Crew", weight="Light", tint="#C0392B", icon_color="192,57,43", vanilla=True,
        buff=f"""
<effect_group>
	<triggered_effect trigger="onSelfKilledOther" action="ModifyStats" stat="Health" operation="add" value="10">
		<requirement name="ItemHasTags" tags="axe,chainsaw"/>
		{KILL}
	</triggered_effect>
</effect_group>""",
        ability="Axe and chainsaw kills heal you 10 health.",
    ),
    "Preacher": dict(
        # Checked on every hit (onOtherDamagedSelf comes after the health drops and before a death check, so the
        # heal can save a killing blow) and twice a second for anything else, like falls
        title="Divine Intervention", weight="Light", tint="#FFD700", icon_color="255,215,0", vanilla=True, update=".5",
        buff=f"""
<effect_group>
	{LOCAL}
	<requirement name="!HasBuff" buff="buffDementiveArmorDivineInterventionCooldown"/>
	<requirement name="StatComparePercCurrentToMax" stat="health" operation="LT" value=".15"/>
""" + "\n".join(f"""	<triggered_effect trigger="{t}" action="ModifyStats" stat="Health" operation="add" value="50"/>
	<triggered_effect trigger="{t}" action="AddBuff" buff="buffDementiveArmorDivineIntervention"/>
	<triggered_effect trigger="{t}" action="AddBuff" buff="buffDementiveArmorDivineInterventionCooldown"/>""" for t in ("onOtherDamagedSelf", "onSelfBuffUpdate")) + """
</effect_group>""",
        ability="Dropping below 15% health heals you 50 and makes you immune to damage for 3 seconds. Once every 20 minutes.",
    ),
    "Rogue": dict(
        # Pickpocket's Gloves work out the lock share (always worn with the set)
        title="Master Thief", weight="Light", tint="#8A2BE2", icon_color="138,43,226", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="LockPickBreakChance" operation="perc_add" value="-2"/>
	<passive_effect name="LockPickTime" operation="perc_add" value="@.DementiveLockThief"/>
</effect_group>""",
        ability="Lockpicks never break, and every lock opens twice as fast.",
    ),
    "Athletic": dict(
        # Exhausted stamina sits at 0 for a moment before it climbs back, so check often. Setting a stat clamps it to
        # the current max, so set-then-halve is exactly half
        title="Second Wind", weight="Light", tint="#00BFFF", icon_color="0,191,255", vanilla=True, update=".1",
        buff=f"""
<effect_group>
	{LOCAL}
	<requirement name="!HasBuff" buff="buffDementiveArmorSecondWindCooldown"/>
	<requirement name="StatCompareCurrent" stat="Stamina" operation="LT" value="3"/>
	<triggered_effect trigger="onSelfBuffUpdate" action="ModifyStats" stat="Stamina" operation="set" value="9999"/>
	<triggered_effect trigger="onSelfBuffUpdate" action="ModifyStats" stat="Stamina" operation="multiply" value=".5"/>
	<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="buffDementiveArmorSecondWindCooldown"/>
</effect_group>""",
        ability="Running out of stamina refills half of it at once. Once a minute.",
    ),
    "Enforcer": dict(
        # V3.4 traders have no secret stash (no tier_items). The trader window hides stock above your trader stage
        # (each item's TraderStageTemplate), and this shows you more of it, like the Daring Adventurer perk
        title="Made Man", weight="Light", tint="#B22222", icon_color="178,34,34", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="TraderStage" operation="base_add" value="50"/>
	<passive_effect name="BarteringBuying" operation="base_add" value=".1"/>
	<passive_effect name="BarteringSelling" operation="base_add" value=".1"/>
</effect_group>""",
        ability="Traders show you stock they'd normally hold back (+50 trader stage), and prices are another 10% better.",
    ),
    "Farmer": dict(
        # The other end of the roll from Muck Boots' (rolls in the same moment come out the same)
        title="Green Thumb", weight="Medium", tint="#6B8E23", icon_color="107,142,35", vanilla=True,
        buff="""
<effect_group>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="GTE" value="75"/>
	<passive_effect name="HarvestCount" operation="base_add" value="2" tags="farmerBonusHarvest"/>
</effect_group>""",
        ability="Each crop you harvest has a 25% chance to give two more.",
    ),
    "Biker": dict(
        title="Outlaw", weight="Medium", tint="#FF4500", icon_color="255,69,0", vanilla=True,
        buff=f"""
<effect_group>
	<triggered_effect trigger="onSelfKilledOther" action="ModifyStats" stat="Health" operation="add" value="15">
		<requirement name="ItemHasTags" tags="melee"/>
		<requirement name="StatComparePercCurrentToMax" stat="health" operation="LT" value=".5"/>
		{KILL}
	</triggered_effect>
</effect_group>""",
        ability="Below half health, melee kills heal you 15 health.",
    ),
    "Scavenger": dict(
        # Scrapping in the backpack reads no effects at all (ItemActionEntryScrap), so this is salvaging instead
        title="Scrap King", weight="Medium", tint="#DAA520", icon_color="218,165,32", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="HarvestCount" operation="perc_add" value=".25" tags="salvageHarvest"/>
</effect_group>""",
        ability="Salvaging gives 25% more materials.",
    ),
    "Ranger": dict(
        title="Dead Eye", weight="Medium", tint="#CD853F", icon_color="205,133,63", vanilla=True,
        buff="""
<effect_group>
	<requirement name="HoldingItemHasTags" tags="gun"/>
	<passive_effect name="HeadshotDamageModifier" operation="perc_add" value=".25" tags="head"/>
</effect_group>""",
        ability="+25% headshot damage with every gun.",
    ),
    "Commando": dict(
        # Magazine sizes are rounded down, so a double barrel stays at 2
        title="Lock and Load", weight="Medium", tint="#3CB371", icon_color="60,179,113", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="MagazineSize" operation="perc_add" value=".2" tags="gun"/>
</effect_group>""",
        ability="Gun magazines hold 20% more rounds.",
    ),
    "Assassin": dict(
        title="Shadow Strike", weight="Medium", tint="#7B68EE", icon_color="123,104,238", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="EntityDamage" operation="perc_add" value=".75">
		<requirement name="CVarCompare" cvar="_crouching" operation="Equals" value="1"/>
		<requirement name="CVarCompare" cvar="_notAlerted" operation="GT" value="0" target="other"/>
	</passive_effect>
</effect_group>""",
        ability="Sneak attacks deal another 75% damage.",
    ),
    "Miner": dict(
        # Ore drops are paid out hit by hit, so the roll is per hit. DementiveArmorOre is added to the ore drops in
        # blocks.xml (their own tag is shared with stone, clay and trees)
        title="Mother Lode", weight="Heavy", tint="#FFA500", icon_color="255,165,0", vanilla=True,
        buff="""
<effect_group>
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="10"/>
	<passive_effect name="HarvestCount" operation="base_add" value="2" tags="DementiveArmorOre"/>
</effect_group>""",
        ability="Each hit on an ore block has a 10% chance to give triple ore.",
    ),
    "Nomad": dict(
        # The drain over time; no vanilla perc_add touches these, so this is exactly 25%. The stamina part of the
        # drain is already cut by the vanilla Nomad set, the helmet and Wanderer's Wraps
        title="Hard Traveler", weight="Heavy", tint="#D2B48C", icon_color="210,180,140", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="FoodChangeOT" operation="perc_add" value="-.25"/>
	<passive_effect name="WaterChangeOT" operation="perc_add" value="-.25"/>
</effect_group>""",
        ability="Food and water drain 25% slower over time.",
    ),
    "Nerd": dict(
        # Tagged so armor wear isn't slowed too (the item's tags are the query's)
        title="Genius", weight="Heavy", tint="#1E90FF", icon_color="30,144,255", vanilla=True,
        buff="""
<effect_group>
	<passive_effect name="DegradationPerUse" operation="perc_add" value="-.3" tags="tool,weapon"/>
</effect_group>""",
        ability="Tools and weapons wear out 30% slower, on top of the Nerd set bonus.",
    ),
    "Raider": dict(
        # One roll for the whole blast: the AOE checks its requirements per zombie. selfAOE skips you and the dead
        title="Warlord", weight="Heavy", tint="#DC143C", icon_color="220,20,60", vanilla=True,
        buff="""
<effect_group>
	<triggered_effect trigger="onSelfKilledOther" action="ModifyCVar" cvar=".DementiveWarlordRoll" operation="set" value="randomint(1,100)">
		<requirement name="ItemHasTags" tags="melee"/>
	</triggered_effect>
	<triggered_effect trigger="onSelfKilledOther" action="AddBuff" target="selfAOE" range="3" target_tags="zombie" buff="buffInjuryKnockdown01">
		<requirement name="ItemHasTags" tags="melee"/>
		<requirement name="CVarCompare" target="self" cvar=".DementiveWarlordRoll" operation="LTE" value="30"/>
	</triggered_effect>
</effect_group>""",
        ability="Melee kills have a 30% chance to knock down every zombie within 3 meters.",
    ),
    "Primitive": dict(
        # oreWoodHarvest is trees, stone, clay, sand and ore alike
        title="Living Off the Land", weight="Light", tint="#20B2AA", icon_color="32,178,170", vanilla=False,
        buff="""
<effect_group>
	<passive_effect name="HarvestCount" operation="perc_add" value=".25" tags="oreWoodHarvest,lumberjackHarvest,cropHarvest,wildCropsHarvest,butcherHarvest"/>
</effect_group>""",
        ability="+25% from harvesting wood, stone and ore, plants and animals.",
    ),
}
SLOTS = ["Helmet", "Outfit", "Gloves", "Boots"]
for p in PIECES:
    p.setdefault("weight", SETS[p["set"]]["weight"])
    p.setdefault("tint", SETS[p["set"]]["tint"])
PIECES.sort(key=lambda p: (list(SETS).index(p["set"]), SLOTS.index(next(s for s in SLOTS if p["parent"].endswith(s)))))

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

    # The rest of each set follows its first piece's look, with its own accent
    "DementiveArmorBigJimsEarflaps": ["pattern:plaid,c1=#b0201a,c2=#151010,scale=12,op=0.9,seed=2", "rim:#ffcf8a,3,0.5", "sheen:0.2"],
    "DementiveArmorRedFlannel": ["pattern:plaid,c1=#d4261c,c2=#1a0c0c,scale=16,op=0.95,seed=3", "sheen:0.15", "glow:#ff5a3a,6,0.5"],
    "DementiveArmorLogrollers": ["map:#1a0d04,#6b3a1a,#d9a86b", "pattern:woodgrain,c1=#3a1e0c,scale=14,op=0.6,seed=4",
                                 "pattern:plaid,c1=#c0281e,c2=#111111,scale=10,op=0.9,zone=90/0.6/0.68", "sheen:0.25"],
    "DementiveArmorReverendsHat": ["map:#050505,#24242a,#8a8a98", "rim:#ffd700,3,0.7", "glow:#ffd24a,9,0.8", "sparkle:#fff3b0,2,12,3"],
    "DementiveArmorLayingOnOfHands": ["map:#3a2a10,#e8e2d0,#ffffff", "emissive:#fff2a0,0.6,0.8", "glow:#ffe680,10,1", "sparkle:#ffffff,3,10,6"],
    "DementiveArmorPilgrimsShoes": ["map:#1a1208,#5a4020,#c8a870", "rim:#ffd700,2,0.6", "glow:#ffd24a,7,0.7", "embers:#fff3b0,6,1,5"],
    "DementiveArmorSecondStoryCap": ["map:#0a0314,#3a1460,#b890ff", "glow:#8a2be2,8,0.8,noise=10", "rim:#e0c4ff,2,0.5", "sparkle:#e8d0ff,2,10,7"],
    "DementiveArmorGetawayJacket": ["map:#05020a,#2a1050,#9a70e0", "trail:#b06aff,180,3,7,0.6", "glow:#8a2be2,6,0.6", "rim:#e0c4ff,2,0.4"],
    "DementiveArmorRooftopRunners": ["map:#0a0314,#4a1a80,#d6b8ff", "glow:#8a2be2,10,0.9,noise=14", "trail:#c890ff,270,3,6,0.5", "sparkle:#e8d0ff,1,10,9"],
    "DementiveArmorCoachsVisor": ["map:#00141f,#00a8e0,#c8f6ff", "sheen:0.4", "rim:#ff2fd0,2,0.8", "glow:#00d0ff,6,0.6"],
    "DementiveArmorGripTapeGloves": ["map:#00141f,#00a8e0,#c8f6ff", "pattern:speckle,c1=#0a0a0a,scale=4,amount=0.5,op=0.6,seed=3", "rim:#ff2fd0,2,0.8", "glow:#00d0ff,5,0.5"],
    "DementiveArmorVarsityJacket": ["map:#001020,#0090d0,#d0f8ff", "sheen:0.3", "rim:#ff2fd0,3,0.8", "trail:#00d0ff,0,3,7,0.5"],
    "DementiveArmorDonsPinstripes": ["map:#050505,#1c1c22,#8a8a96", "pattern:stripes,c1=#d4a017,scale=6,op=0.55,angle=90", "rim:#ffd700,2,0.6", "sparkle:#ffffff,2,12,4"],
    "DementiveArmorWheelmansGloves": [GOLD, "sheen:0.6", "trail:#ffe9a0,0,3,6,0.5", "sparkle:#ffffff,2,12,5"],
    "DementiveArmorTwoToneWingtips": ["map:#050505,#1a1a1a,#606060", "map:#3a2a10,#e8e2d0,#ffffff,zone=0/0.45/0.55", "rim:#ffd700,2,0.6", "sparkle:#ffffff,2,12,6"],
    "DementiveArmorSunBonnet": ["map:#2a1a05,#c8a040,#fff0b0", "pattern:plaid,c1=#6b8e23,c2=#f0e0b0,scale=10,op=0.5,seed=5", "glow:#ffd24a,8,0.6", "sheen:0.2"],
    "DementiveArmorOldBessiesGloves": ["map:#140c05,#7a5030,#e0c090", "pattern:splatter,c1=#2a170a,scale=8,amount=0.45,op=0.9,seed=6,shade=0.5",
                                       "pattern:speckle,c1=#6b8e23,scale=6,amount=0.7,op=0.5,seed=2", "sheen:0.2"],
    "DementiveArmorSundayOveralls": ["map:#0d1405,#4f6b1f,#b9cf7a", "pattern:plaid,c1=#c0281e,c2=#f0f0f0,scale=8,op=0.6,zone=90/0.6/0.7",
                                     "pattern:splatter,c1=#2a170a,scale=9,amount=0.5,op=0.8,seed=8,shade=0.5,zone=90/-0.35/0.45", "sheen:0.2"],
    "DementiveArmorSkullLid": ["map:#050505,#262626,#9a9a9a", "pattern:flames,c1=#ffe94d,c2=#ff2a00,c3=#120000,op=1,reach=0.7,count=4,seed=5,shade=0.35",
                               "sheen:0.7", "sparkle:#ffffff,2,12,2"],
    "DementiveArmorKnuckleDusters": ["map:#050505,#2a2a2a,#c0c0c0", "pattern:flames,c1=#ffe94d,c2=#ff2a00,c3=#120000,op=1,reach=0.6,count=5,seed=7,shade=0.35",
                                     "sheen:0.6", "emissive:#ff8a2a,0.85,0.6"],
    "DementiveArmorSteelToeStompers": ["map:#050505,#262626,#7a7a7a", "pattern:flames,c1=#ffe94d,c2=#ff2a00,c3=#120000,op=1,reach=0.8,count=6,seed=9,shade=0.35",
                                       "sheen:0.5", "rim:#c0c0c0,2,0.4"],
    "DementiveArmorKnuckleBusterMitts": ["map:#1a0d03,#9a6a2a,#f0d8a0", "pattern:speckle,c1=#7a2e0e,scale=8,amount=0.5,op=0.8,seed=5",
                                         "pattern:cracks,c1=#3a8a6a,scale=14,op=0.5,width=0.05,seed=3", "sheen:0.3"],
    "DementiveArmorPackRatParka": ["map:#1a0d03,#8a6030,#e8d0a0", "pattern:camo,c1=#7a2e0e,c2=#3a8a6a,c3=#9a6a2a,scale=14,op=0.6,seed=9,shade=0.7",
                                   "pattern:speckle,c1=#3a1a05,scale=6,amount=0.6,op=0.6,seed=4", "sparkle:#fff6c0,2,10,8"],
    "DementiveArmorDumpsterDivers": ["map:#1a0d03,#9a6a2a,#f0d8a0", "pattern:splatter,c1=#3a8a6a,scale=9,amount=0.45,op=0.8,seed=11,shade=0.5",
                                     "pattern:speckle,c1=#7a2e0e,scale=8,amount=0.55,op=0.8,seed=6", "sheen:0.3"],
    "DementiveArmorLawmansStetson": ["map:#120802,#6b3f1a,#d9a066", "sheen:0.3", "rim:#ffd700,2,0.7", "sparkle:#ffe9a0,2,14,3"],
    "DementiveArmorLongRiderDuster": ["map:#100a04,#5a4024,#c8a070", "pattern:speckle,c1=#2a1808,scale=5,amount=0.6,op=0.45,seed=3", "rim:#ffd700,2,0.6", "glow:#ffb040,6,0.4"],
    "DementiveArmorTrailBoots": ["map:#120802,#7a4a1e,#e0b070", "pattern:speckle,c1=#3a1e0a,scale=5,amount=0.6,op=0.5,seed=8", "sheen:0.35",
                                 "rim:#ffd700,2,0.6", "sparkle:#ffe9a0,1,14,4"],
    "DementiveArmorBlastHelmet": ["pattern:camo,c1=#6b7a30,c2=#34451f,c3=#8a7048,scale=16,op=0.9,seed=8,shade=0.7", "sheen:0.3", "glow:#ff7a20,6,0.5", "embers:#ffa040,8,1.2,3"],
    "DementiveArmorTriggerDiscipline": ["pattern:camo,c1=#5a6a28,c2=#2a3a18,c3=#7a6040,scale=14,op=0.9,seed=11,shade=0.7", "sheen:0.3",
                                        "rim:#c8d890,2,0.4", "sparkle:#fff0c0,1,10,5"],
    "DementiveArmorJumpBoots": ["pattern:camo,c1=#6b7a30,c2=#34451f,c3=#8a7048,scale=18,op=0.9,seed=13,shade=0.7", "sheen:0.4", "trail:#c8d890,90,3,6,0.5"],
    "DementiveArmorSilentHands": ["map:#020208,#1b1b30,#6a6a9a", "glow:#8fd0ff,10,0.9,noise=10", "rim:#bfe6ff,2,0.6"],
    "DementiveArmorShroud": ["map:#010104,#141428,#5a5a8a", "glow:#8fd0ff,14,1,noise=14", "rim:#bfe6ff,3,0.5", "emissive:#9fe8ff,0.6,0.6"],
    "DementiveArmorGhostSteps": ["map:#020208,#1b1b30,#6a6a9a", "glow:#8fd0ff,10,0.8,noise=8", "trail:#8fd0ff,0,3,6,0.4", "rim:#bfe6ff,2,0.5"],
    "DementiveArmorRockSplitters": ["map:#2a0f00,#c86a00,#ffe0a0", "pattern:cracks,c1=#ffcc00,scale=14,op=0.9,bloom=0.7,width=0.06,seed=4", "sheen:0.4"],
    "DementiveArmorBlastingCoveralls": ["map:#2a0f00,#ff8c00,#ffe0a0", "pattern:hazard,c1=#ffcc00,c2=#111111,scale=10,op=0.85,zone=90/0.55/0.62",
                                        "embers:#ffd080,8,1.2,6", "sheen:0.3"],
    "DementiveArmorCanaryBoots": ["map:#2a1a00,#e8b800,#fff6b0", "emissive:#fff2b0,0.8,0.8", "pattern:hazard,c1=#ffcc00,c2=#111111,scale=10,op=0.9,zone=90/-0.25/0.3", "sheen:0.4"],
    "DementiveArmorSandVeil": ["pattern:camo,c1=#c8a874,c2=#8a6a3e,c3=#e8d6a8,scale=14,op=0.9,seed=9,shade=0.8", "pattern:speckle,c1=#f0dca8,scale=5,amount=0.62,op=0.35,seed=4",
                               "glow:#ff9a3a,8,0.5", "embers:#ffe0a8,8,1.2,7"],
    "DementiveArmorGeigerGloves": ["pattern:camo,c1=#c8a874,c2=#8a6a3e,c3=#e8d6a8,scale=12,op=0.9,seed=12,shade=0.8", "glow:#7aff3a,8,0.7,noise=10",
                                   "emissive:#c0ff80,0.75,0.7", "sparkle:#e0ffb0,2,10,3"],
    "DementiveArmorLongWalkBoots": ["pattern:camo,c1=#b8986a,c2=#7a5a34,c3=#e0cc9a,scale=16,op=0.9,seed=15,shade=0.8", "pattern:speckle,c1=#f0dca8,scale=5,amount=0.62,op=0.35,seed=9",
                                    "sheen:0.2", "trail:#ffd0a0,0,3,6,0.4"],
    "DementiveArmorSolderingGloves": ["map:#06142b,#1e5bb8,#9fd0ff", "pattern:circuit,c1=#3ff0ff,scale=10,op=0.8,bloom=0.5,seed=6", "embers:#ffd060,6,1,4", "rim:#7fe8ff,2,0.4"],
    "DementiveArmorLabCoat": ["map:#20283a,#c8d8f0,#ffffff", "pattern:circuit,c1=#3ff0ff,scale=12,op=0.6,bloom=0.6,seed=8", "glow:#40c0ff,8,0.7", "sparkle:#c0f8ff,3,10,4"],
    "DementiveArmorKineticSneakers": ["map:#06142b,#1e5bb8,#9fd0ff", "pattern:circuit,c1=#3ff0ff,scale=12,op=0.8,bloom=0.6,seed=10", "trail:#3ff0ff,180,3,7,0.6", "rim:#7fe8ff,2,0.5"],
    "DementiveArmorWarCrown": ["map:#0b0b0d,#3a3a40,#9a9aa5", "pattern:cracks,c1=#ff3b00,scale=16,op=1,bloom=0.9,width=0.07,seed=5", "sheen:0.5", "embers:#ff6a20,6,1.2,3"],
    "DementiveArmorSpikedGauntlets": ["map:#0b0b0d,#40404a,#b0b0bd", "pattern:cracks,c1=#ff3b00,scale=14,op=1,bloom=0.8,width=0.06,seed=7", "sheen:0.6", "sparkle:#ffd0b0,2,10,4"],
    "DementiveArmorScrapPlate": ["map:#0b0b0d,#3a3a40,#9a9aa5", "pattern:speckle,c1=#7a2e0e,scale=8,amount=0.55,op=0.6,seed=4",
                                 "pattern:cracks,c1=#ff3b00,scale=20,op=1,bloom=0.9,width=0.07,seed=9", "sheen:0.4"],
    # Primitive: sun-bleached hide and fiber with a sea-green glow
    "DementiveArmorCastawaysHeadband": ["map:#1a1005,#a07848,#f0dcb0", "pattern:woodgrain,c1=#5a3a18,scale=12,op=0.5,seed=3", "glow:#20d0c0,8,0.7,noise=10", "sparkle:#c0fff8,2,10,3"],
    "DementiveArmorLuckyRags": ["map:#1a1005,#8a6a40,#e8d4a8", "pattern:splatter,c1=#2a8a7a,scale=10,amount=0.5,op=0.6,seed=5,shade=0.6", "glow:#20d0c0,10,0.8,noise=12",
                                "sparkle:#fff6c0,4,10,7"],
    "DementiveArmorWrappedFists": ["map:#1a1005,#a07848,#f0dcb0", "pattern:woodgrain,c1=#3a2410,scale=8,op=0.5,seed=8", "emissive:#ff9a3a,0.8,0.6", "glow:#20d0c0,6,0.6"],
    "DementiveArmorBareWraps": ["map:#1a1005,#9a7044,#ecd8ac", "pattern:woodgrain,c1=#5a3a18,scale=10,op=0.45,seed=11", "trail:#20d0c0,0,3,6,0.5", "glow:#20d0c0,6,0.5"],
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

		<!-- Rooftop Runners: the landing after a fall is silent to zombies (buffs come last, so this is the total) -->
		<buff name="buffDementiveArmorRooftopRunners" hidden="true">
			<stack_type value="replace"/>
			<duration value="1"/>
			<effect_group>
				<passive_effect name="NoiseMultiplier" operation="perc_set" value="0"/>
			</effect_group>
		</buff>

		<!-- Varsity Jacket: worn marker that keeps buffDementiveArmorVarsitySprint on while sprinting. Only the owner
		     knows; the flag syncs to the server, which works out the damage -->
		<buff name="buffDementiveArmorVarsityJacket" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<update_rate value=".25"/>
			<effect_group>
				<requirement name="IsLocalPlayer"/>
				<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="buffDementiveArmorVarsitySprint">
					<requirement name="EntityHasMovementTag" tags="running"/>
					<requirement name="!HasBuff" buff="buffDementiveArmorVarsitySprint"/>
				</triggered_effect>
				<triggered_effect trigger="onSelfBuffUpdate" action="RemoveBuff" buff="buffDementiveArmorVarsitySprint">
					<requirement name="!EntityHasMovementTag" tags="running"/>
					<requirement name="HasBuff" buff="buffDementiveArmorVarsitySprint"/>
				</triggered_effect>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorVarsitySprint" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
		</buff>

		<!-- The Don's Pinstripes: after a .44 Magnum or Desert Vulture kill -->
		<buff name="buffDementiveArmorDonsPinstripes" name_key="buffDementiveArmorDonsPinstripesName" description_key="buffDementiveArmorDonsPinstripesDesc" icon="ui_game_symbol_pistol" icon_color="178,34,34">
			<stack_type value="replace"/>
			<duration value="5"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="EntityDamage" operation="perc_add" value=".25"/>
			</effect_group>
		</buff>

		<!-- Knuckle Dusters: up while melee hits keep coming within 2 seconds; the streak is in .DementiveKnuckleStreak -->
		<buff name="buffDementiveArmorKnuckleDusters" name_key="buffDementiveArmorKnuckleDustersName" description_key="buffDementiveArmorKnuckleDustersDesc" icon="ui_game_symbol_boxer" icon_color="255,69,0">
			<stack_type value="replace"/>
			<duration value="2"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="EntityDamage" operation="perc_add" value="@.DementiveKnuckleStreak" tags="melee"/>
				<triggered_effect trigger="onSelfBuffFinish" action="ModifyCVar" cvar=".DementiveKnuckleStreak" operation="set" value="0"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar=".DementiveKnuckleStreak" operation="set" value="0"/>
			</effect_group>
		</buff>

		<!-- Lawman's Stetson: after a headshot kill -->
		<buff name="buffDementiveArmorLawmansStetson" name_key="buffDementiveArmorLawmansStetsonName" description_key="buffDementiveArmorLawmansStetsonDesc" icon="ui_game_symbol_run" icon_color="205,133,63">
			<stack_type value="replace"/>
			<duration value="5"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".2"/>
				<passive_effect name="RunSpeed" operation="perc_add" value=".15"/>
			</effect_group>
		</buff>

		<!-- Long Rider Duster and Trail Boots: while aiming down sights -->
		<buff name="buffDementiveArmorLongRiderDuster" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value=".15"/>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorTrailBoots" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<effect_group>
				<!-- Aiming stops a sprint, so moving while aiming is walking (or crouch-walking) -->
				<passive_effect name="WalkSpeed" operation="perc_add" value=".25"/>
				<passive_effect name="CrouchSpeed" operation="perc_add" value=".25"/>
			</effect_group>
		</buff>

		<!-- Jump Boots: after a kill -->
		<buff name="buffDementiveArmorJumpBoots" name_key="buffDementiveArmorJumpBootsName" description_key="buffDementiveArmorJumpBootsDesc" icon="ui_game_symbol_run" icon_color="60,179,113">
			<stack_type value="replace"/>
			<duration value="4"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="RunSpeed" operation="perc_add" value=".15"/>
			</effect_group>
		</buff>

		<!-- Lab Coat: on the zombie (zombie buffs run on the server). Any electrical buff starts the electrocuted
		     stagger, and each electrical damage tick (every half second) restarts it, like buffShocked but 2 seconds -->
		<buff name="buffDementiveArmorLabCoatShock" hidden="true">
			<damage_type value="electrical"/>
			<stack_type value="replace"/>
			<duration value="2"/>
			<effect_group>
				<passive_effect name="HealthChangeOT" operation="base_add" value="-2"/>
				<passive_effect name="RunSpeed" operation="perc_subtract" value=".9"/>
				<passive_effect name="WalkSpeed" operation="perc_subtract" value=".9"/>
				<passive_effect name="CrouchSpeed" operation="perc_subtract" value=".9"/>
				<passive_effect name="JumpStrength" operation="perc_subtract" value=".9"/>
				<triggered_effect trigger="onSelfBuffStart" action="AttachParticleEffectToEntity" particle="p_electric_shock" parent_transform="Spine1" local_offset="0,-.2,0"/>
				<triggered_effect trigger="onSelfBuffStart" action="PlaySound" sound="electric_fence_impact"/>
				<triggered_effect trigger="onSelfBuffFinish" action="RemoveParticleEffectFromEntity" particle="p_electric_shock"/>
				<triggered_effect trigger="onSelfBuffRemove" action="RemoveParticleEffectFromEntity" particle="p_electric_shock"/>
				<triggered_effect trigger="onSelfDied" action="RemoveParticleEffectFromEntity" particle="p_electric_shock"/>
			</effect_group>
		</buff>

		<!-- Kinetic Sneakers: worn marker that counts seconds of sprinting on the owner's machine (where the hit's
		     damage is worked out too), then the charge, used up by the next hit -->
		<buff name="buffDementiveArmorKineticSneakers" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<update_rate value="1"/>
			<effect_group>
				<requirement name="IsLocalPlayer"/>
				<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveKineticSprint" operation="add" value="1">
					<requirement name="EntityHasMovementTag" tags="running"/>
				</triggered_effect>
				<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveKineticSprint" operation="set" value="0">
					<requirement name="!EntityHasMovementTag" tags="running"/>
				</triggered_effect>
				<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="buffDementiveArmorKineticCharge">
					<requirement name="CVarCompare" cvar=".DementiveKineticSprint" operation="GTE" value="5"/>
					<requirement name="!HasBuff" buff="buffDementiveArmorKineticCharge"/>
				</triggered_effect>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorKineticCharge" name_key="buffDementiveArmorKineticChargeName" description_key="buffDementiveArmorKineticChargeDesc" icon="ui_game_symbol_electric_power" icon_color="30,144,255">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<effect_group>
				<!-- DamageModifier multiplies the finished damage (the player class sets it to 1), so +1 doubles it -->
				<passive_effect name="DamageModifier" operation="perc_add" value="1" tags="entity"/>
				<triggered_effect trigger="onSelfAttackedOther" action="RemoveBuff" buff="buffDementiveArmorKineticCharge"/>
			</effect_group>
		</buff>

		<!-- War Crown: one buff per stack. Each kill refreshes the stacks there are and adds the next one -->
		<buff name="buffDementiveArmorWarCrown1" name_key="buffDementiveArmorWarCrownName" description_key="buffDementiveArmorWarCrownDesc" icon="ui_game_symbol_armor_iron" icon_color="220,20,60">
			<stack_type value="replace"/>
			<duration value="3"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value=".1"/>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorWarCrown2" hidden="true">
			<stack_type value="replace"/>
			<duration value="3"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value=".1"/>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorWarCrown3" hidden="true">
			<stack_type value="replace"/>
			<duration value="3"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value=".1"/>
			</effect_group>
		</buff>

		<!-- Spiked Gauntlets: after a melee kill -->
		<buff name="buffDementiveArmorSpikedGauntlets" name_key="buffDementiveArmorSpikedGauntletsName" description_key="buffDementiveArmorSpikedGauntletsDesc" icon="ui_game_symbol_boxer" icon_color="220,20,60">
			<stack_type value="replace"/>
			<duration value="3"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="AttacksPerMinute" operation="perc_add" value=".3" tags="melee"/>
			</effect_group>
		</buff>

		<!-- Divine Intervention (Preacher named set) -->
		<buff name="buffDementiveArmorDivineIntervention" name_key="buffDementiveArmorDivineInterventionName" description_key="buffDementiveArmorDivineInterventionDesc" icon="ui_game_symbol_add" icon_color="255,215,0">
			<stack_type value="ignore"/>
			<duration value="3"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value="1"/>
				<passive_effect name="FallDamageReduction" operation="base_subtract" value="1"/>
			</effect_group>
		</buff>
		<buff name="buffDementiveArmorDivineInterventionCooldown" name_key="buffDementiveArmorDivineInterventionCooldownName" description_key="buffDementiveArmorDivineInterventionCooldownDesc" icon="ui_game_symbol_clock" icon_color="128,128,128" remove_on_death="false">
			<stack_type value="ignore"/>
			<duration value="1200"/>
			<display_value value="duration"/>
		</buff>

		<!-- Second Wind (Athletic named set) -->
		<buff name="buffDementiveArmorSecondWindCooldown" name_key="buffDementiveArmorSecondWindCooldownName" description_key="buffDementiveArmorSecondWindCooldownDesc" icon="ui_game_symbol_clock" icon_color="128,128,128">
			<stack_type value="ignore"/>
			<duration value="60"/>
			<display_value value="duration"/>
		</buff>

		<!-- Named-set bonuses, given by buffStatusCheck02 below -->
{set_buffs}
	</append>

	<!-- Marathon Runners: falls hurt as if they were 4 m shorter (vanilla boots use the same impact speed units:
	     .02828 = 2 m). Goes in the group where the vanilla boots reduce the impact speed, before it is checked -->
	<append xpath="/buffs/buff[@name='buffPlayerFallingDamage']/effect_group[triggered_effect[@value='@$rogueBootFallDMG']]">
		<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar=".impactSpeed" operation="subtract" value=".05656">
			<requirement name="HasBuff" buff="buffDementiveArmorMarathonRunners"/>
		</triggered_effect>
	</append>

	<!-- Named-set bonuses: the same check vanilla uses for its full set bonuses. ArmorGroupCount counts what is worn
	     (rebuilt on every equipment change), so equipping, unequipping and loading can't leave it wrong -->
	<append xpath="/buffs/buff[@name='buffStatusCheck02']">
{set_checks}
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
    ("buffDementiveArmorDonsPinstripesName", "The Don's Pinstripes"),
    ("buffDementiveArmorDonsPinstripesDesc", "25% more damage."),
    ("buffDementiveArmorKnuckleDustersName", "Knuckle Dusters"),
    ("buffDementiveArmorKnuckleDustersDesc", "Keep landing melee hits within 2 seconds: each adds 5% damage, up to 25%."),
    ("buffDementiveArmorLawmansStetsonName", "Lawman's Stetson"),
    ("buffDementiveArmorLawmansStetsonDesc", "20% faster reloads and 15% faster running."),
    ("buffDementiveArmorJumpBootsName", "Jump Boots"),
    ("buffDementiveArmorJumpBootsDesc", "15% faster running."),
    ("buffDementiveArmorKineticChargeName", "Kinetic Charge"),
    ("buffDementiveArmorKineticChargeDesc", "Your next hit deals double damage."),
    ("buffDementiveArmorWarCrownName", "War Crown"),
    ("buffDementiveArmorWarCrownDesc", "10% damage resistance for each kill in the last 3 seconds, up to 30%."),
    ("buffDementiveArmorSpikedGauntletsName", "Spiked Gauntlets"),
    ("buffDementiveArmorSpikedGauntletsDesc", "30% faster melee attacks."),
    ("buffDementiveArmorDivineInterventionName", "Divine Intervention"),
    ("buffDementiveArmorDivineInterventionDesc", "You can't be hurt."),
    ("buffDementiveArmorDivineInterventionCooldownName", "Divine Intervention Recharging"),
    ("buffDementiveArmorDivineInterventionCooldownDesc", "Divine Intervention can't save you again until this runs out."),
    ("buffDementiveArmorSecondWindCooldownName", "Second Wind Recharging"),
    ("buffDementiveArmorSecondWindCooldownDesc", "Second Wind can't refill your stamina again until this runs out."),
]

# Chance per container opened that one piece drops, same as Weapons Expanded's weapons
LOOT = """<Dementive>

	<append xpath="/lootcontainers/lootprobtemplates">
		<!-- Chance per container opened that one armor piece drops. With 64 pieces each piece is half as likely as
		     each of the first 15 was (0.005 to 0.05), so a piece turns up 64 / 30 times as often overall. Every
		     group these go in is count="all" with 2.5 or more picks, so it stays under 1% of a group's picks -->
		<lootprobtemplate name="DementiveArmorRaresT1">
			<loot level="1,999999" prob="0.0107"/>  <!-- 1 / 94 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT2">
			<loot level="1,999999" prob="0.0213"/>  <!-- 1 / 47 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT3">
			<loot level="1,999999" prob="0.0427"/>  <!-- 1 / 23 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT4">
			<loot level="1,999999" prob="0.0853"/>  <!-- 1 / 12 -->
		</lootprobtemplate>
		<lootprobtemplate name="DementiveArmorRaresT5">
			<loot level="1,999999" prob="0.1067"/>  <!-- 1 / 9 -->
		</lootprobtemplate>

		<!-- Quest rewards: the reward "value" is the quest tier. At tiers 4-6 roughly 3% of schematic rewards
		     (about 1 in 20 quests) offer one of the armor pieces instead. This stays as it was with 15 pieces: any
		     more would be over 3% of the group's picks -->
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
	     groups that traders restock from (6 picks each, 8 for Joel), under 1% of each group's picks, so a typical
	     trader has about a 10% chance per restock to have one piece (Joel about 14%). Each piece's
	     TraderStageTemplate (baseTier2) keeps them to trader stage 50 and up.
	     The game only lets a group use groups defined above it, so these go before groupArmorLight. -->
	<insertBefore xpath="/traders/trader_item_groups/trader_item_group[@name='groupArmorLight']">
{groups}
	</insertBefore>

{appends}
</Dementive>
"""
# Weight per piece in its trader group: half what each of the first 15 pieces had (the groups had 0.055 for 5 light,
# 6 medium and 4 heavy pieces)
TRADER_PIECE_PROB = {"Light": 0.0055, "Medium": 0.0046, "Heavy": 0.0069}

# The vanilla helmets that cut search time tell SCAV_REST how much (Second-Story Cap does it in its signature)
SCAV_HELMETS = ["armorRogueHelmet", "armorSantaHatHelmet"]
# Blast Helmet's radius bonus: the frag and contact grenades and the pipe bomb get a tag of their own
GRENADES = ["thrownGrenade", "thrownGrenadeContact", "thrownAmmoPipeBomb"]
# Mother Lode: the ore blocks' ore drops (not the stone that comes with them) get a tag of their own
ORE_BLOCKS = ["terrOreIron", "terrOreLead", "terrOreCoal", "terrOrePotassiumNitrate", "terrOreOilDeposit",
              "oreIronBoulder", "oreLeadBoulder", "oreCoalBoulder", "orePotassiumNitrateBoulder", "oreShaleBoulder"]


def van_item(name):
    return re.search(r'\n<item name="%s">.*?\n</item>' % re.escape(name), van, re.S).group(0)


def van_prop(item, prop):
    return re.search(r'<property name="%s" value="([^"]*)"' % prop, van_item(item)).group(1)


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
        # The vanilla group first (cosmetics read only the first), then the named set's own
        f'\t\t\t<property name="ArmorGroup" value="{van_prop(p["parent"], "ArmorGroup")},groupDementiveNamed{p["set"]}"/>',
    ]
    if van_prop(p["parent"], "Extends") == "armorPrimitiveMaster":
        head.append('\t\t\t<property name="SellableToTrader" value="true"/>')  # like the other named pieces
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
items += "\t</append>\n"
items += "\n\t<!-- Search time cut of the vanilla helmets, for the Pickpocket's Gloves and Pack Rat Parka shares -->\n"
for name in SCAV_HELMETS:
    cut = ",".join(v.lstrip("-") for v in
                   re.search(r'name="ScavengingTime" operation="perc_add" value="([^"]*)"', van_item(name)).group(1).split(","))
    group = eg("Dementive search time", scav_helmet(cut)).replace("\n\t", "\n")[1:]  # one tab shallower
    items += f"\t<append xpath=\"/items/item[@name='{name}']\">\n{group}\n\t</append>\n"
items += "\n\t<!-- Blast Helmet: a tag for the grenades and the pipe bomb, so its radius bonus skips other explosives -->\n"
for name in GRENADES:
    items += f"\t<append xpath=\"/items/item[@name='{name}']/property[@name='Tags']/@value\">,DementiveArmorGrenade</append>\n"
items += "\n</Dementive>\n"

# Mother Lode: a tag on the ore drops. Their own tag (oreWoodHarvest) is shared with stone, clay and trees
vblocks = open(os.path.join(game, "Data", "Config", "blocks.xml"), encoding="utf-8").read()
blocks = ["<Dementive>", "", "\t<!-- Mother Lode: the ore blocks' ore drops get a tag of their own. Generated by Scripts/ArmorExpanded/gen_armor.py -->"]
for name in ORE_BLOCKS:
    body = "".join(re.findall(r'<block name="%s">(.*?)</block>' % name, vblocks, re.S))
    ores = sorted(set(re.findall(r'<drop event="Harvest" name="(\w+)"[^>]*tag="oreWoodHarvest"', body)) - {"resourceRockSmall"})
    if not ores:
        raise SystemExit(f"Mother Lode: no ore drop on {name}")
    for ore in ores:
        blocks.append(f"\t<setattribute xpath=\"/blocks/block[@name='{name}']/drop[@event='Harvest' and @name='{ore}' and @tag='oreWoodHarvest']\" "
                      f"name=\"tag\">oreWoodHarvest,DementiveArmorOre</setattribute>")
blocks += ["", "</Dementive>", ""]

# Sunday Overalls: the player class sees each event first (before the held item), so it notes the food and water
# still to come before an item adds to them. playerFemale extends playerMale
entityclasses = ("<Dementive>\n\n\t<!-- Sunday Overalls: the food and water still to come before an item adds to it. Generated by "
                 "Scripts/ArmorExpanded/gen_armor.py -->\n\t<append xpath=\"/entity_classes/entity_class[@name='playerMale']\">\n"
                 "\t\t<effect_group name=\"Dementive food before\">\n"
                 + "".join(f'\t\t\t<triggered_effect trigger="{t}" action="ModifyCVar" cvar=".Dementive{n}Before" operation="set" value="@{c}"/>\n'
                           for t, n, c in FOOD_CVARS)
                 + "\t\t</effect_group>\n\t</append>\n\n</Dementive>\n")

set_buffs, set_checks = [], []
for key, st in SETS.items():
    buff = f"buffDementiveArmorSet{key}"
    update = f'\n\t\t\t<update_rate value="{st["update"]}"/>' if "update" in st else ""
    content = "\n".join("\t\t\t" + l for l in st["buff"].strip("\n").split("\n"))
    set_buffs.append(f'\t\t<!-- {st["title"]} ({key}) -->\n'
                     f'\t\t<buff name="{buff}" name_key="{buff}Name" description_key="{buff}Desc" icon="ui_game_symbol_armor_iron" icon_color="{st["icon_color"]}">\n'
                     f'\t\t\t<stack_type value="ignore"/>{update}\n{content}\n\t\t</buff>')
    group = f"groupDementiveNamed{key}"
    set_checks.append(f"""\t\t<effect_group> <!-- {st["title"]} -->
\t\t\t<triggered_effect trigger="onSelfBuffUpdate" action="RemoveBuff" buff="{buff}">
\t\t\t\t<requirement name="ArmorGroupCount" group_name="{group}" operation="LTE" value="3"/>
\t\t\t\t<requirement name="HasBuff" buff="{buff}"/>
\t\t\t</triggered_effect>
\t\t\t<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="{buff}">
\t\t\t\t<requirement name="ArmorGroupCount" group_name="{group}" operation="Equals" value="4"/>
\t\t\t\t<requirement name="!HasBuff" buff="{buff}"/>
\t\t\t</triggered_effect>
\t\t</effect_group>""")
    BUFF_LOC.append((buff + "Name", st["title"]))
    BUFF_LOC.append((buff + "Desc", st["ability"]))
buffs = BUFFS.replace("{set_buffs}", "\n".join(set_buffs)).replace("{set_checks}", "\n".join(set_checks))

header = "Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"
loc = [header]
for p in PIECES:
    st = SETS[p["set"]]
    desc = f"{p['lore']}\\n\\n{p['ability']}\\n\\n"
    if st["vanilla"]:
        desc += f"Counts toward the {p['set']} full set bonus.\\n\\n"
    desc += f"{st['title']}, with all four named {p['set']} pieces: {st['ability']}"
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
                   f'\t\t<item group="groupDementiveTraderArmor{weight}" prob="{TRADER_PIECE_PROB[weight] * len(members):.4f}"/>\n\t</append>\n')
traders = TRADERS.replace("{groups}", "\n".join(groups)).replace("{appends}", "\n".join(appends))

cfg = os.path.join(mod, "Config")
write(os.path.join(cfg, "items.xml"), items)
write(os.path.join(cfg, "buffs.xml"), buffs)
write(os.path.join(cfg, "blocks.xml"), "\n".join(blocks))
write(os.path.join(cfg, "entityclasses.xml"), entityclasses)
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
