"""Generate the ModsExpanded mod (and its server-side copy) from the MODS table below.

Usage: python gen_mods.py <game dir> <ModsExpanded dir> [<ModsExpanded-SERVERSIDE dir>]
Each mod is an item_modifier in the vanilla style: quality 1-6 (vehicle mods have none, like vanilla's), a schematic
that unlocks its workbench recipe, and a place in the vanilla mod loot and trader groups. Rewrites
Config/item_modifiers.xml, items.xml (schematics), recipes.xml, buffs.xml, nav_objects.xml, loot.xml, traders.xml
and Localization.csv, and paints vanilla icons into UIAtlases/ItemIconAtlas with Scripts/bin/IconTool.exe (ICONS).
The server-side copy uses the vanilla icons with a color tint instead, since its clients don't have the icons.

Values that depend on the mod's quality are set the way vanilla's Cripple 'Em and Bandolier do it: a cvar set on
equip from RequirementItemModTier. Armor mods put their logic in a buff added while the armor is worn, like vanilla's
Impact Bracing.
"""
import os
import re
import shutil
import subprocess
import sys

game, mod = sys.argv[1:3]
server = sys.argv[3] if len(sys.argv) > 3 else None
icon_tool = os.path.join(os.path.dirname(__file__), "..", "bin", "IconTool.exe")
TIERS = range(1, 7)


def tiered(values):
    return f'value="{",".join(str(v) for v in values)}" tier="1,2,3,4,5,6"'


def group(body, tiered_group=True):
    lines = body.strip("\n").split("\n")
    attr = "" if tiered_group else ' tiered="false"'
    return f"\t\t\t<effect_group{attr}>\n" + "\n".join("\t\t\t\t" + l for l in lines) + "\n\t\t\t</effect_group>"


def cvar_by_tier(name, cvar, values, extra_start="", extra_stop=""):
    """Set a cvar from the mod's quality when the item is equipped (and clear it when it isn't), like Cripple 'Em."""
    out = []
    for tier, v in zip(TIERS, values):
        out.append(group(f"""
<requirement name="RequirementItemModTier" mod_name="{name}" operation="Equals" value="{tier}"/>
<triggered_effect trigger="onSelfEquipStart" action="ModifyCVar" cvar="{cvar}" operation="set" value="{v}"/>"""))
    out.append(group(f"""
{extra_start}<triggered_effect trigger="onSelfEquipStop" action="RemoveCVar" cvar="{cvar}"/>{extra_stop}""", False))
    return out


def worn_buff(name, cvar, buffs):
    """Armor mods: the quality goes in a cvar and a buff carries the logic while the armor is worn."""
    start = f'<triggered_effect trigger="onSelfEquipStart" action="AddBuff" buff="{buffs[0]}"/>\n'
    stop = "".join(f'\n<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="{b}"/>' for b in buffs)
    return cvar_by_tier(name, cvar, list(TIERS), start, stop)


def by_tier(tag, make):
    """One triggered effect per quality tier, picked by the tier cvar."""
    return "\n".join(make(t).replace("{req}", f'<requirement name="CVarCompare" cvar="{tag}" operation="Equals" value="{t}"/>') for t in TIERS)


MODS = [
    # --- Melee ---
    dict(name="DementiveModExecutioner", title="Executioner", slot="melee", trader="modsTier2", loot="modMeleeT2", shop="groupMeleeMods",
         icon="modMeleeSerratedBlade", tint="#8B0000",
         recipe=[("resourceForgedSteel", 3), ("resourceMechanicalParts", 4), ("resourceGlue", 3)],
         effects=[group(f"""
<requirement name="StatComparePercCurrentToMax" target="other" stat="Health" operation="LT" value=".3"/>
<passive_effect name="EntityDamage" operation="perc_add" {tiered([.1, .15, .2, .25, .3, .35])}/>""")],
         lore="A headsman's edge ground onto the striking face. It finishes what you start.",
         ability="+10% to +35% damage (by quality) to anything below 30% health."),
    dict(name="DementiveModLiveWire", title="Live Wire", slot="melee", trader="modsTier3", loot="modMeleeT3", shop="groupMeleeMods",
         icon="modMeleeStunBatonRepulsor", tint="#00BFFF",
         recipe=[("resourceElectricParts", 8), ("resourceForgedSteel", 3), ("resourceScrapPolymers", 6), ("resourceGlue", 3)],
         effects=cvar_by_tier("DementiveModLiveWire", "$DementiveLiveWireChance", [5, 7, 9, 11, 13, 15]) + [group("""
<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="@$DementiveLiveWireChance"/>
<triggered_effect trigger="onSelfDamagedOther" action="AddBuff" target="other" buff="buffDementiveModsLiveWire"/>""", False)],
         lore="A car battery's worth of wiring wrapped around the grip, with the contacts filed sharp.",
         ability="5% to 15% chance (by quality) that a hit shocks the target and arcs to zombies within 3 m."),
    dict(name="DementiveModSecondWind", title="Second Wind", slot="melee", trader="modsTier1", loot="modMeleeT1", shop="groupMeleeMods",
         icon="modMeleeErgonomicGrip", tint="#32CD32",
         recipe=[("resourceLeather", 6), ("resourceGlue", 3), ("resourceForgedIron", 3)],
         effects=cvar_by_tier("DementiveModSecondWind", "$DementiveSecondWind", [5, 8, 11, 14, 17, 20]) + [group("""
<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
<triggered_effect trigger="onSelfKilledOther" action="ModifyStats" stat="Stamina" operation="add" value="@$DementiveSecondWind"/>""", False)],
         lore="A sweat-stained wrap that somehow makes every kill feel like a deep breath.",
         ability="Every kill gives back 5 to 20 stamina (by quality)."),
    dict(name="DementiveModMomentum", title="Momentum", slot="melee", trader="modsTier2", loot="modMeleeT2", shop="groupMeleeMods",
         icon="modMeleeWeightedHead", tint="#FF8C00",
         recipe=[("resourceForgedSteel", 4), ("resourceMechanicalParts", 5), ("resourceSpring", 4)],
         # Dropping the buff on unequip (its remove trigger zeroes the stacks) keeps them from carrying over to another weapon
         effects=cvar_by_tier("DementiveModMomentum", "$DementiveMomentumMax", [.1, .15, .15, .2, .25, .3],
                              extra_stop='\n<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveModsMomentum"/>') + [group("""
<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
<triggered_effect trigger="onSelfDamagedOther" action="ModifyCVar" cvar="$DementiveMomentum" operation="add" value=".05">
	<requirement name="CVarCompare" cvar="$DementiveMomentum" operation="LT" value="@$DementiveMomentumMax"/>
</triggered_effect>
<triggered_effect trigger="onSelfDamagedOther" action="AddBuff" buff="buffDementiveModsMomentum"/>""", False)],
         lore="A counterweight that keeps the swing going. Stop swinging and you lose it.",
         ability="Each hit within 2 seconds of the last adds +5% melee damage, stacking 2 to 6 times (by quality)."),

    # --- Ranged ---
    dict(name="DementiveModHeadhunter", title="Headhunter", slot="ranged", trader="modsTier2", loot="modGunT2", shop="groupRangedMods",
         icon="modGunScopeMedium", tint="#DC143C",
         recipe=[("resourceForgedSteel", 5), ("resourceMechanicalParts", 5), ("resourceGlue", 4), ("resourceSpring", 6)],
         effects=[group(f"""
<passive_effect name="HeadshotDamageModifier" operation="perc_add" {tiered([.1, .15, .2, .25, .3, .35])} tags="head"/>""")],
         lore="A trigger job and a cheek rest tuned for one thing: the head.",
         ability="+10% to +35% headshot damage (by quality)."),
    dict(name="DementiveModSpeedLoader", title="Speed Loader", slot="gun", trader="modsTier1", loot="modGunT1", shop="groupRangedMods",
         icon="modGunMagazineExtender", tint="#FFD700",
         recipe=[("resourceForgedIron", 5), ("resourceSpring", 8), ("resourceMechanicalParts", 3)],
         effects=[group(f"""
<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" {tiered([.08, .12, .17, .21, .26, .3])}/>""")],
         lore="A flared magwell and a set of pre-loaded clips. Reloading is muscle memory now.",
         ability="Reloads 8% to 30% faster (by quality)."),
    dict(name="DementiveModKnockEmDown", title="Knock 'Em Down", slot="ranged", trader="modsTier2", loot="modGunT2", shop="groupRangedMods",
         icon="modGunMuzzleBrake", tint="#A0522D",
         recipe=[("resourceForgedSteel", 5), ("resourceMechanicalParts", 6), ("resourceSpring", 6), ("resourceGlue", 4)],
         # Shotguns roll for every pellet, so they roll against 1/8 of the chance, like Cripple 'Em
         effects=cvar_by_tier("DementiveModKnockEmDown", "$DementiveKnockdownChance", [3, 5, 8, 10, 13, 15]) + [group("""
<requirement name="EntityTagCompare" target="other" tags="zombie"/>
<requirement name="!HoldingItemHasTags" tags="shotgun"/>
<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="@$DementiveKnockdownChance"/>
<triggered_effect trigger="onSelfDamagedOther" action="AddBuff" target="other" buff="buffInjuryKnockdown01"/>""", False), group("""
<requirement name="EntityTagCompare" target="other" tags="zombie"/>
<requirement name="HoldingItemHasTags" tags="shotgun"/>
<requirement name="RandomRoll" seed_type="Random" min_max="0,800" operation="LTE" value="@$DementiveKnockdownChance"/>
<triggered_effect trigger="onSelfDamagedOther" action="AddBuff" target="other" buff="buffInjuryKnockdown01"/>""", False)],
         lore="An overcharged compensator that turns every shot into a shove.",
         ability="3% to 15% chance (by quality) that a hit knocks the zombie down. Shotguns roll for each pellet at 1/8 of the chance."),
    dict(name="DementiveModSpotterTags", title="Spotter Tags", slot="ranged", trader="modsTier3", loot="modGunT3", shop="groupRangedMods",
         icon="modGunLaserSight", tint="#FF4500",
         recipe=[("resourceElectricParts", 10), ("resourceScrapPolymers", 6), ("resourceGlue", 4), ("resourceForgedSteel", 3)],
         effects=cvar_by_tier("DementiveModSpotterTags", "$DementiveSpotterTier", list(TIERS)) + [group(
             '<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>\n'
             + by_tier("$DementiveSpotterTier", lambda t: f'<triggered_effect trigger="onSelfDamagedOther" action="AddBuff" target="other" buff="buffDementiveModsSpotted{t}">\n\t{{req}}\n</triggered_effect>'),
             False)],
         lore="A launcher for tiny radio beacons that stick to whatever you shoot. Everyone with a receiver can see them.",
         ability="Whatever you hit is marked through walls for every player for 4 to 12 seconds (by quality)."),

    # --- Weapons and tools ---
    dict(name="DementiveModRabbitsFoot", title="Rabbit's Foot", slot="weapon,tool", trader="modsTier2", loot="modGunT2", shop="groupMeleeMods",
         icon="modGunMeleeTheHunter", tint="#9ACD32",
         recipe=[("resourceLeather", 4), ("resourceCloth", 3), ("resourceGlue", 2)],
         effects=[group(f"""
<passive_effect name="LootDropProb" operation="perc_add" {tiered([.1, .16, .22, .28, .34, .4])}/>""")],
         lore="A lucky rabbit's foot on a keychain. It wasn't lucky for the rabbit.",
         ability="Zombies you kill are 10% to 40% more likely (by quality) to drop a loot bag."),

    # --- Tools ---
    dict(name="DementiveModTurboMotor", title="Turbo Motor", slot="motorTool", trader="modsTier3", loot="modMeleeT3", shop="groupMeleeMods",
         icon="modFuelTankLarge", tint="#FF6347",
         recipe=[("resourceMechanicalParts", 10), ("resourceForgedSteel", 5), ("resourceSpring", 8), ("resourceOil", 2)],
         effects=[group(f"""
<passive_effect name="RoundsPerMinute" operation="perc_add" {tiered([.08, .11, .15, .18, .22, .25])}/>""")],
         lore="A ported cylinder and a racing carburetor. It screams.",
         ability="Chainsaws and augers run 8% to 25% faster (by quality)."),
    dict(name="DementiveModPayDirt", title="Pay Dirt", slot="miningTool", trader="modsTier1", loot="modMeleeT1", shop="groupMeleeMods",
         icon="modMeleeDiamondTip", tint="#DAA520",
         recipe=[("resourceForgedSteel", 4), ("resourceMechanicalParts", 4), ("resourceGlue", 3)],
         effects=[group(f"""
<passive_effect name="HarvestCount" operation="perc_add" {tiered([.05, .09, .13, .17, .21, .25])} tags="oreWoodHarvest"/>""")],
         lore="A sifting screen clipped behind the head. Nothing worth keeping falls through.",
         ability="+5% to +25% ore, stone and wood (by quality) from what the tool breaks."),
    dict(name="DementiveModScrapMagnet", title="Scrap Magnet", slot="salvageTool", trader="modsTier1", loot="modMeleeT1", shop="groupMeleeMods",
         icon="modMeleeIronBreaker", tint="#708090",
         recipe=[("resourceElectricParts", 4), ("resourceForgedIron", 6), ("resourceMechanicalParts", 3)],
         effects=[group(f"""
<passive_effect name="HarvestCount" operation="perc_add" {tiered([.05, .09, .13, .17, .21, .25])} tags="salvageHarvest"/>""")],
         lore="A magnet off a junkyard crane, cut down to fit a wrench. Screws and parts just jump to it.",
         ability="+5% to +25% salvage (by quality)."),

    # --- Armor ---
    dict(name="DementiveModThorns", title="Thorns", slot="armorChest", trader="modsTier2", loot="modArmorT2", shop="groupArmorMods",
         icon="modArmorPlatingReinforced", tint="#556B2F",
         recipe=[("resourceForgedSteel", 6), ("resourceNail", 20), ("resourceGlue", 4)],
         effects=worn_buff("DementiveModThorns", ".DementiveModsThornsTier", ["buffDementiveModsThorns"]),
         lore="Razor wire woven through the lining. Grabbing whoever wears it is a mistake.",
         ability="Zombies and animals that hit you take 5 to 20 damage (by quality)."),
    dict(name="DementiveModReactivePlating", title="Reactive Plating", slot="armorChest", trader="modsTier3", loot="modArmorT3", shop="groupArmorMods",
         icon="modArmorPlatingBasic", tint="#4682B4",
         recipe=[("resourceForgedSteel", 10), ("resourceScrapPolymers", 8), ("resourceGlue", 5), ("resourceMechanicalParts", 5)],
         effects=worn_buff("DementiveModReactivePlating", ".DementiveModsPlatingTier",
                           ["buffDementiveModsPlating", "buffDementiveModsPlatingReady", "buffDementiveModsPlatingGuard"]),
         lore="A spring-loaded plate that slams out to meet a blow, then needs a while to reset.",
         ability="Blocks the next hit you take, with a clang. Recharges in 60 to 30 seconds (by quality)."),
    dict(name="DementiveModSquadComms", title="Squad Comms", slot="armorHead", trader="modsTier2", loot="modArmorT2", shop="groupArmorMods",
         icon="radioHam", tint="#20B2AA",
         recipe=[("resourceElectricParts", 8), ("resourceScrapPolymers", 6), ("resourceGlue", 3)],
         effects=worn_buff("DementiveModSquadComms", ".DementiveModsCommsTier", ["buffDementiveModsSquadCommsAura"]),
         lore="A headset radio tuned to your party's channel. Callouts win fights.",
         ability="You and party members within about 25 m deal +3% to +10% damage (by quality). Several radios don't stack."),

    # --- Vehicles (no quality, like vanilla's vehicle mods) ---
    dict(name="DementiveModOffRoadSuspension", title="Off-Road Suspension", slot="vehicle", trader="modsTier2", loot="vehicleMods", shop="groupVehicleMods",
         icon="modVehicleSuperCharger", tint="#8B4513", quality=False,
         recipe=[("resourceMechanicalParts", 10), ("resourceSpring", 12), ("resourceForgedSteel", 6)],
         effects=[group("""
<passive_effect name="VehicleSelfDamage" operation="perc_add" value="-.4"/>
<passive_effect name="VehicleStrongSelfDamage" operation="perc_add" value="-.4"/>
<passive_effect name="VehicleMotorTorquePer" operation="perc_add" value=".2"/>""", False)],
         lore="Long-travel shocks and skid plates for roads that aren't roads anymore.",
         ability="Your vehicle takes 40% less damage from collisions and has 20% more pulling power."),
    dict(name="DementiveModRoadkillBumper", title="Roadkill Bumper", slot="vehicle", trader="modsTier2", loot="vehicleMods", shop="groupVehicleMods",
         icon="modVehicleArmor", tint="#B22222", quality=False,
         recipe=[("resourceForgedSteel", 12), ("resourceMechanicalParts", 6), ("resourceGlue", 4)],
         effects=[group("""
<passive_effect name="VehicleEntityDamage" operation="perc_add" value=".75"/>""", False)],
         lore="A welded steel cowcatcher with spikes. It doesn't take up the plow's spot.",
         ability="Zombies you run over take 75% more damage."),
]

THORNS_DAMAGE = [5, 8, 11, 14, 17, 20]
PLATING_COOLDOWN = [60, 54, 48, 42, 36, 30]
COMMS_DAMAGE = [.03, .045, .06, .07, .085, .1]
SPOTTED_TIME = [4, 6, 7, 9, 10, 12]


def plating_spend():
    """Reactive Plating: spend an armed plate on onOtherAttackedSelf. Every trigger checks the plate is armed, so when
    both the worn buff and progression get the same attack, only the first one spends it."""
    starts = by_tier(".DementiveModsPlatingTier", lambda t: f'<triggered_effect trigger="onOtherAttackedSelf" action="AddBuff" buff="buffDementiveModsPlatingCooldown{t}">\n\t<requirement name="HasBuff" buff="buffDementiveModsPlatingReady"/>\n\t{{req}}\n</triggered_effect>')
    return starts + """
<triggered_effect trigger="onOtherAttackedSelf" action="AddBuff" buff="buffDementiveModsPlatingGuard">
	<requirement name="HasBuff" buff="buffDementiveModsPlatingReady"/>
</triggered_effect>
<triggered_effect trigger="onOtherAttackedSelf" action="PlaySound" sound="metalhitmetal">
	<requirement name="HasBuff" buff="buffDementiveModsPlatingReady"/>
</triggered_effect>
<triggered_effect trigger="onOtherAttackedSelf" action="RemoveBuff" buff="buffDementiveModsPlatingReady">
	<requirement name="HasBuff" buff="buffDementiveModsPlatingReady"/>
</triggered_effect>"""


def progression_xml():
    # The player's attributes always exist, and progression gets onOtherAttackedSelf for buff damage too (vanilla's
    # Pack Mule perk uses that event), so this is where damage over time spends the plate
    return f"""<Dementive>

	<!-- Reactive Plating: damage over time spends the plate too, so an armed plate can't block it forever -->
	<append xpath="/progression/attributes/attribute[@name='attFortitude']">
		<effect_group name="DementiveMods Reactive Plating">
{indent(plating_spend(), 3)}
		</effect_group>
	</append>

</Dementive>
"""


def buffs_xml():
    b = []
    # Live Wire: the shocked target arcs to zombies close by
    b.append("""		<!-- Live Wire: the target is shocked and the shock arcs to zombies within 3 m. Runs where the target's buffs
		     run (the server for zombies) -->
		<buff name="buffDementiveModsLiveWire" hidden="true">
			<stack_type value="replace"/>
			<duration value="1"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="AddBuff" buff="buffShocked"/>
				<triggered_effect trigger="onSelfBuffStart" action="AddBuff" target="selfAOE" range="3" target_tags="zombie" buff="buffShocked"/>
				<triggered_effect trigger="onSelfBuffStack" action="AddBuff" buff="buffShocked"/>
				<triggered_effect trigger="onSelfBuffStack" action="AddBuff" target="selfAOE" range="3" target_tags="zombie" buff="buffShocked"/>
			</effect_group>
		</buff>""")
    # Momentum
    b.append("""		<!-- Momentum: each hit refreshes it (replace resets the duration without removing it). The stacks reset when it
		     runs out -->
		<buff name="buffDementiveModsMomentum" name_key="buffDementiveModsMomentumName" description_key="buffDementiveModsMomentumDesc" icon="ui_game_symbol_boxer" icon_color="255,140,0">
			<stack_type value="replace"/>
			<duration value="2"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="EntityDamage" operation="perc_add" value="@$DementiveMomentum" tags="melee"/>
				<triggered_effect trigger="onSelfBuffFinish" action="ModifyCVar" cvar="$DementiveMomentum" operation="set" value="0"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="$DementiveMomentum" operation="set" value="0"/>
			</effect_group>
		</buff>""")
    # Spotter Tags
    for t, secs in zip(TIERS, SPOTTED_TIME):
        b.append(f"""		<buff name="buffDementiveModsSpotted{t}" hidden="true">  <!-- Spotter Tags, quality {t} -->
			<stack_type value="replace"/>
			<duration value="{secs}"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="SetNavObject" nav_object="DementiveModsSpotted" add="true"/>
				<triggered_effect trigger="onSelfBuffFinish" action="SetNavObject" nav_object="DementiveModsSpotted" add="false"/>
				<triggered_effect trigger="onSelfBuffRemove" action="SetNavObject" nav_object="DementiveModsSpotted" add="false"/>
			</effect_group>
		</buff>""")
    # Thorns
    hits = by_tier(".DementiveModsThornsTier", lambda t: f'<triggered_effect trigger="onOtherDamagedSelf" action="AddBuff" target="other" buff="buffDementiveModsThornsHit{t}">\n\t<requirement name="HasBuff" buff="buffDementiveModsThornsWindow"/>\n\t{{req}}\n</triggered_effect>')
    # No TargetRange here: it fails whenever the event carries no item, which a buff's events needn't.
    # onOtherDamagedSelf also fires for every tick of a damage-over-time buff, with the zombie that caused it as Other,
    # so it only counts right after a direct attack: buffs only get onOtherAttackedSelf for those, and it fires first.
    # The window can't target Other itself: on clients Other is stale during onOtherAttackedSelf
    b.append(f"""		<!-- Thorns: worn marker. Zombies and animals that hurt the wearer with a direct attack (not burning or bleeding
		     they caused) get a hit buff for the mod's quality -->
		<buff name="buffDementiveModsThorns" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<effect_group>
				<triggered_effect trigger="onOtherAttackedSelf" action="AddBuff" buff="buffDementiveModsThornsWindow"/>
			</effect_group>
			<effect_group>
				<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
{indent(hits, 4)}
			</effect_group>
		</buff>
		<buff name="buffDementiveModsThornsWindow" hidden="true">
			<stack_type value="replace"/>
			<duration value=".2"/>
		</buff>""")
    for t, dmg in zip(TIERS, THORNS_DAMAGE):
        b.append(f"""		<buff name="buffDementiveModsThornsHit{t}" hidden="true">  <!-- Thorns, quality {t} -->
			<stack_type value="replace"/>
			<duration value="1"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyStats" stat="Health" operation="add" value="-{dmg}"/>
				<triggered_effect trigger="onSelfBuffStack" action="ModifyStats" stat="Health" operation="add" value="-{dmg}"/>
			</effect_group>
		</buff>""")
    # Reactive Plating
    cooldowns = ",".join(f"buffDementiveModsPlatingCooldown{t}" for t in TIERS)
    b.append(f"""		<!-- Reactive Plating: worn marker. Arms the plate whenever it isn't armed or recharging. The plate's resistance
		     blocks the hit (the attack event only fires after the damage is worked out); the attack event then starts the
		     recharge for the mod's quality and leaves a half-second guard for the rest of that attack. Damage over time
		     (burning, bleeding) never sends the attack event to buffs, so progression.xml spends the charge for those -->
		<buff name="buffDementiveModsPlating" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<update_rate value="1"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="buffDementiveModsPlatingReady">
					<requirement name="!HasBuff" buff="buffDementiveModsPlatingReady,{cooldowns}"/>
				</triggered_effect>
				<triggered_effect trigger="onSelfBuffStart" action="AddBuff" buff="buffDementiveModsPlatingReady">
					<requirement name="!HasBuff" buff="buffDementiveModsPlatingReady,{cooldowns}"/>
				</triggered_effect>
{indent(plating_spend(), 4)}
			</effect_group>
		</buff>
		<buff name="buffDementiveModsPlatingReady" name_key="buffDementiveModsPlatingReadyName" description_key="buffDementiveModsPlatingReadyDesc" icon="ui_game_symbol_armor_iron" icon_color="70,130,180">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value="1"/>
			</effect_group>
		</buff>
		<buff name="buffDementiveModsPlatingGuard" hidden="true">
			<stack_type value="replace"/>
			<duration value=".5"/>
			<effect_group>
				<passive_effect name="GeneralDamageResist" operation="base_add" value="1"/>
			</effect_group>
		</buff>""")
    for t, secs in zip(TIERS, PLATING_COOLDOWN):
        b.append(f"""		<buff name="buffDementiveModsPlatingCooldown{t}" name_key="buffDementiveModsPlatingCooldownName" description_key="buffDementiveModsPlatingCooldownDesc" icon="ui_game_symbol_armor_iron" icon_color="128,128,128">
			<stack_type value="ignore"/>
			<duration value="{secs}"/>  <!-- quality {t} -->
			<display_value value="duration"/>
		</buff>""")
    # Squad Comms
    shares = by_tier(".DementiveModsCommsTier", lambda t: f"""<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="buffDementiveModsSquadComms{t}">
	{{req}}
</triggered_effect>
<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" target="selfAOE" range="25" target_tags="party" buff="buffDementiveModsSquadComms{t}">
	{{req}}
</triggered_effect>""")
    # selfAOE checks the range itself (a box, so up to ~35 m on the diagonal) and treats "party" as a relationship
    # (MinEventActionTargetedBase.isValidTarget); "ally" would also take in friends-list players and allied NPCs.
    # TargetRange would fail here: it needs an item in the event, which a buff's update doesn't carry
    b.append(f"""		<!-- Squad Comms: worn marker. Every 2 seconds it gives the wearer and party members within 25 m the bonus for the
		     mod's quality -->
		<buff name="buffDementiveModsSquadCommsAura" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<update_rate value="2"/>
			<effect_group>
{indent(shares, 4)}
			</effect_group>
		</buff>""")
    for t, pct in zip(TIERS, COMMS_DAMAGE):
        higher = ",".join(f"buffDementiveModsSquadComms{h}" for h in TIERS if h > t)
        req = f'\n\t\t\t\t<requirement name="!HasBuff" buff="{higher}"/>' if higher else ""
        b.append(f"""		<buff name="buffDementiveModsSquadComms{t}" name_key="buffDementiveModsSquadCommsName" description_key="buffDementiveModsSquadCommsDesc{t}" icon="ui_game_symbol_talk" icon_color="32,178,170">
			<stack_type value="replace"/>
			<duration value="3"/>
			<effect_group>{req}
				<passive_effect name="EntityDamage" operation="perc_add" value="{pct}"/>
			</effect_group>
		</buff>""")
    return "<Dementive>\n\n\t<append xpath=\"/buffs\">\n" + "\n\n".join(b) + "\n\t</append>\n\n</Dementive>\n"


BUFF_LOC = [
    ("buffDementiveModsMomentumName", "Momentum"),
    ("buffDementiveModsMomentumDesc", "Keep hitting to keep your melee damage bonus."),
    ("buffDementiveModsPlatingReadyName", "Reactive Plating"),
    ("buffDementiveModsPlatingReadyDesc", "The next hit you take is blocked."),
    ("buffDementiveModsPlatingCooldownName", "Reactive Plating Recharging"),
    ("buffDementiveModsPlatingCooldownDesc", "Your plating is resetting."),
    ("buffDementiveModsSquadCommsName", "Squad Comms"),
] + [(f"buffDementiveModsSquadCommsDesc{t}", f"+{round(p * 100, 1):g}% damage from a squadmate's radio.") for t, p in zip(TIERS, COMMS_DAMAGE)]

NAV_OBJECTS = """<Dementive>

	<!-- Spotter Tags: a marker over whatever was hit, seen through walls -->
	<append xpath="/nav_object_classes">
		<nav_object_class name="DementiveModsSpotted">
			<onscreen_settings>
				<property name="sprite_name" value="ui_game_symbol_enemy_dot"/>
				<property name="min_distance" value="0"/>
				<property name="max_distance" value="150"/>
				<property name="color" value="255,69,0,255"/>
				<property name="use_head_offset" value="true"/>
				<property name="offset" value="0,0.6,0"/>
				<property name="sprite_size" value="28"/>
			</onscreen_settings>
		</nav_object_class>
	</append>

</Dementive>
"""

# Icon recipes for IconTool.exe fx (see the ops in Scripts/WeaponsExpanded/IconTool.cs), in the style of the
# hand-made Weapons Expanded icons. `tint` above is only for the server-side copy.
GOLD = "map:#2a1800,#d4a017,#fff4c0"
ICONS = {
    "DementiveModExecutioner": ["map:#080000,#4a0000,#d06060", "sheen:0.6", "pattern:splatter,c1=#ff1a1a,scale=7,amount=0.55,op=0.9,seed=4,shade=0.5",
                                "rim:#ff3030,2,0.6", "glow:#8a0000,6,0.6"],
    "DementiveModLiveWire": ["map:#020a14,#0a5a9a,#c8f0ff", "pattern:cracks,c1=#9ff0ff,scale=10,op=1,bloom=0.9,width=0.06,seed=3",
                             "glow:#00bfff,9,0.9,noise=12", "emissive:#bff8ff,0.8,0.9", "sparkle:#ffffff,3,10,5"],
    "DementiveModSecondWind": ["map:#031405,#2a8a2a,#d0ffc0", "sheen:0.35", "glow:#7dff5a,7,0.7", "trail:#a0ff80,90,3,6,0.5", "sparkle:#f0ffe0,2,10,3"],
    "DementiveModMomentum": ["map:#1a0800,#d06a00,#ffe0a0", "sheen:0.6", "trail:#ffa030,0,4,6,0.7", "embers:#ffb040,8,1.4,4"],
    "DementiveModHeadhunter": ["map:#0a0a0c,#3a3a44,#c8c8d4", "sheen:0.6", "pattern:splatter,c1=#9a0000,scale=6,amount=0.55,op=0.9,seed=7,shade=0.5",
                               "emissive:#ff2020,0.85,0.9", "rim:#ff3030,2,0.5"],
    "DementiveModSpeedLoader": [GOLD, "sheen:0.75", "trail:#fff0a0,180,3,6,0.6", "sparkle:#ffffff,3,12,2"],
    "DementiveModKnockEmDown": ["map:#140802,#7a3a14,#f0c090", "sheen:0.45", "pattern:hazard,c1=#ffcc00,c2=#111111,scale=7,op=0.9,zone=0/0.4/0.45/0.6/0.65",
                                "embers:#ffa040,8,1.5,6"],
    "DementiveModSpotterTags": ["map:#0a0400,#5a2a0a,#ffc0a0", "sheen:0.5", "emissive:#ff4500,0.75,1", "glow:#ff4500,8,0.8,noise=10",
                                "sparkle:#ffd0b0,2,10,8"],
    "DementiveModRabbitsFoot": ["map:#081405,#5a8a2a,#f0ffd0", "pattern:speckle,c1=#ffffff,scale=4,amount=0.72,op=0.5,seed=3", "glow:#c8ff40,8,0.8",
                                "sparkle:#ffffff,4,12,9"],
    "DementiveModTurboMotor": ["map:#140200,#c02a10,#ffc0a0", "pattern:flames,c1=#ffe94d,c2=#ff3a00,c3=#120000,op=1,reach=0.6,count=5,seed=4,shade=0.35",
                               "sheen:0.5", "embers:#ff8a1a,10,1.6,3"],
    "DementiveModPayDirt": [GOLD, "sheen:0.65", "pattern:speckle,c1=#ffffff,scale=4,amount=0.7,op=0.55,seed=5", "sparkle:#ffffff,4,12,6"],
    "DementiveModScrapMagnet": ["map:#06080a,#4a5a6a,#d8e8f0", "sheen:0.6", "pattern:circuit,c1=#7fbfff,scale=12,op=0.6,bloom=0.4,seed=2",
                                "glow:#5a9aff,7,0.6", "sparkle:#e0f0ff,3,10,4"],
    "DementiveModThorns": ["map:#060a02,#3a4a1a,#c0d090", "pattern:cracks,c1=#e0ffa0,scale=9,op=0.9,width=0.05,seed=6,shade=0.6",
                           "pattern:splatter,c1=#6a0000,scale=7,amount=0.62,op=0.8,seed=8,shade=0.5", "sheen:0.4", "rim:#d8ff80,2,0.4"],
    "DementiveModReactivePlating": ["map:#040810,#2a4a7a,#d0e4ff", "sheen:0.8", "rim:#9fd8ff,3,0.6", "glow:#4fa0ff,7,0.7", "sparkle:#ffffff,3,12,5"],
    "DementiveModSquadComms": ["map:#021212,#1a8a84,#c8fff8", "sheen:0.45", "pattern:circuit,c1=#7ffff0,scale=10,op=0.75,bloom=0.6,seed=7",
                               "emissive:#bffff8,0.85,0.8", "glow:#20b2aa,6,0.6"],
    "DementiveModOffRoadSuspension": ["pattern:camo,c1=#8b6a3a,c2=#4a3a1a,c3=#c8a870,scale=14,op=0.9,seed=4,shade=0.7",
                                      "pattern:splatter,c1=#3a2a10,scale=8,amount=0.5,op=0.9,seed=5,shade=0.5", "sheen:0.45", "rim:#ffd890,2,0.4"],
    "DementiveModRoadkillBumper": ["map:#0a0a0c,#6a6a74,#ffffff", "sheen:0.8", "pattern:splatter,c1=#8a0000,scale=7,amount=0.48,op=1,seed=2,shade=0.6",
                                   "rim:#ff3030,2,0.5"],
}

LOOT_PROB = {"vehicleMods": ' loot_prob_template="ProbT2Cap"'}
SCHEMATIC_LOOT = {"modsTier1": "T0", "modsTier2": "T1", "modsTier3": "T2"}


def indent(text, tabs):
    return "\n".join("\t" * tabs + l for l in text.split("\n"))


def build(m):
    quality = m.get("quality", True)
    head = [
        f"\t\t<!-- {m['title']} -->",
        f'\t\t<item_modifier name="{m["name"]}" installable_tags="{m["slot"]}" modifier_tags="{m["name"]}" blocked_tags="noMods" type="attachment">',
        '\t\t\t<property name="Extends" value="modGeneralMaster" param1="CustomIcon"/>',
        f'\t\t\t<property name="CustomIcon" value="{m["name"]}"/>',
        f'\t\t\t<property name="DescriptionKey" value="{m["name"]}Desc"/>',
        f'\t\t\t<property name="UnlockedBy" value="{m["name"]}Schematic"/>',
        f'\t\t\t<property name="TraderStageTemplate" value="{m["trader"]}"/>',
    ]
    if quality:
        head += ['\t\t\t<property name="ShowQuality" value="true"/>', '\t\t\t<property name="QualityMin" value="1"/>']
    return "\n".join(head) + "\n\n" + "\n".join(m["effects"]) + "\n\t\t</item_modifier>\n"


def schematic(m):
    return "\n".join([
        f'\t\t<item name="{m["name"]}Schematic">',
        '\t\t\t<property name="Extends" value="schematicNoQualityMaster"/>',
        '\t\t\t<property name="CreativeMode" value="Player"/>',
        f'\t\t\t<property name="CustomIcon" value="{m["name"]}"/>',
        f'\t\t\t<property name="Unlocks" value="{m["name"]}"/>',
        '\t\t\t<effect_group tiered="false">',
        f'\t\t\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="{m["name"]}" operation="set" value="1"/>',
        '\t\t\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="GiveExp" exp="50"/>',
        '\t\t\t</effect_group>',
        '\t\t</item>\n',
    ])


def recipe(m):
    ings = "\n".join(f'\t\t\t<ingredient name="{n}" count="{c}"/>' for n, c in m["recipe"])
    return f'\t\t<recipe name="{m["name"]}" count="1" craft_area="workbench" tags="learnable,workbenchCrafting">\n{ings}\n\t\t</recipe>'


def csv_field(s):
    return '"' + s.replace('"', '""') + '"' if "," in s or '"' in s else s


def loc_row(key, kind, text):
    return f"{key},{kind},,,,{csv_field(text)},,,,,,,,,,,,,"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n"))


mods_xml = ("<Dementive>\n\n\t<!-- Item mods in the vanilla style. Generated by Scripts/ModsExpanded/gen_mods.py -->\n"
            "\t<append xpath=\"/item_modifiers\">\n" + "\n".join(build(m) for m in MODS) + "\t</append>\n\n</Dementive>\n")
items = ("<Dementive>\n\n\t<!-- Schematics: each one unlocks its mod's workbench recipe -->\n\t<append xpath=\"/items\">\n"
         + "\n".join(schematic(m) for m in MODS) + "\t</append>\n\n</Dementive>\n")
recipes = "<Dementive>\n\n\t<append xpath=\"/recipes\">\n" + "\n\n".join(recipe(m) for m in MODS) + "\n\t</append>\n\n</Dementive>\n"

# --- loot.xml: the mods go into the vanilla mod groups by tier, so they turn up wherever vanilla mods do. The
# schematics go in the vanilla mod schematic groups, each about as likely as a vanilla schematic ---
loot = ["<Dementive>\n"]
for g in dict.fromkeys(m["loot"] for m in MODS):
    loot.append(f"\t<append xpath=\"/lootcontainers/lootgroup[@name='{g}']\">")
    loot += [f'\t\t<item name="{m["name"]}"{LOOT_PROB.get(g, "")}/>' for m in MODS if m["loot"] == g]
    loot.append("\t</append>")
loot.append("\n\t<insertBefore xpath=\"/lootcontainers/lootgroup[@name='schematicsModsAndGeneralT0']\">")
for tier, g in SCHEMATIC_LOOT.items():
    loot.append(f'\t\t<lootgroup name="groupDementiveModsSchematics{g}">')
    loot += [f'\t\t\t<item name="{m["name"]}Schematic"/>' for m in MODS if m["trader"] == tier]
    loot.append("\t\t</lootgroup>")
loot.append("\t</insertBefore>")
for tier, g in SCHEMATIC_LOOT.items():
    n = sum(1 for m in MODS if m["trader"] == tier)
    loot.append(f"\t<append xpath=\"/lootcontainers/lootgroup[@name='schematicsModsAndGeneral{g}']\">\n"
                f'\t\t<item group="groupDementiveModsSchematics{g}" prob="{n}"/>\n\t</append>')
loot.append("\n</Dementive>\n")
loot = "\n".join(loot)

# --- traders.xml: mods in the vanilla mod groups, schematics with the vanilla mod schematics ---
traders = ["<Dementive>\n"]
for g in dict.fromkeys(m["shop"] for m in MODS):
    traders.append(f"\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='{g}']\">")
    traders += [f'\t\t<item name="{m["name"]}"/>' for m in MODS if m["shop"] == g]
    traders.append("\t</append>")
for g, pick in (("schematicsModsCommon", lambda m: m["slot"] != "vehicle"), ("schematicsVehiclesMods", lambda m: m["slot"] == "vehicle")):
    traders.append(f"\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='{g}']\">")
    traders += [f'\t\t<item name="{m["name"]}Schematic"/>' for m in MODS if pick(m)]
    traders.append("\t</append>")
traders.append("\n</Dementive>\n")
traders = "\n".join(traders)

header = "Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"
loc = [header]
for m in MODS:
    loc.append(loc_row(m["name"], "item_modifiers,Mod", m["title"]))
    loc.append(loc_row(m["name"] + "Desc", "item_modifiers,Mod", f"{m['lore']}\\n\\n{m['ability']}"))
    loc.append(loc_row(m["name"] + "Schematic", "items,Schematic", m["title"] + " Schematic"))
for key, text in BUFF_LOC:
    loc.append(loc_row(key, "buffs,Buff", text))

cfg = os.path.join(mod, "Config")
write(os.path.join(cfg, "item_modifiers.xml"), mods_xml)
write(os.path.join(cfg, "items.xml"), items)
write(os.path.join(cfg, "recipes.xml"), recipes)
write(os.path.join(cfg, "buffs.xml"), buffs_xml())
write(os.path.join(cfg, "nav_objects.xml"), NAV_OBJECTS)
write(os.path.join(cfg, "progression.xml"), progression_xml())
write(os.path.join(cfg, "loot.xml"), loot)
write(os.path.join(cfg, "traders.xml"), traders)
write(os.path.join(cfg, "Localization.csv"), "\n".join(loc) + "\n")
print(f"{len(MODS)} mods written to {cfg}")

atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
os.makedirs(atlas, exist_ok=True)
for m in MODS:
    src = os.path.join(game, "Data", "ItemIcons", m["icon"] + ".png")
    subprocess.run([icon_tool, "fx", src, os.path.join(atlas, m["name"] + ".png"), *ICONS[m["name"]]], check=True)
print(f"{len(MODS)} icons written to {atlas}")

if server:
    scfg = os.path.join(server, "Config")
    os.makedirs(scfg, exist_ok=True)
    for f in os.listdir(cfg):
        text = open(os.path.join(cfg, f), encoding="utf-8", newline="").read()
        if f in ("item_modifiers.xml", "items.xml"):
            for m in MODS:
                text = text.replace(f'<property name="CustomIcon" value="{m["name"]}"/>',
                                    f'<property name="CustomIcon" value="{m["icon"]}"/>\r\n\t\t\t<property name="CustomIconTint" value="{m["tint"][1:]}"/>')
            if re.search(r'name="CustomIcon" value="Dementive', text):
                raise SystemExit(f"server-side {f} still uses a custom icon")
        open(os.path.join(scfg, f), "w", encoding="utf-8", newline="").write(text)
    print(f"server-side copy written to {scfg}")
