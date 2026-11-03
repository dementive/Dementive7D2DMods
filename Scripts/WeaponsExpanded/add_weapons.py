"""Add the WeaponsExpanded signature weapons (the 10 added in 2026) to the mod.

Usage: python add_weapons.py <game dir> <WeaponsExpanded dir>
Each weapon Extends a vanilla weapon and carries copies of its <stats> and effect groups (those are not
inherited), with legendary stat boosts and a signature effect group. Weapons already in items.xml are skipped,
so a new weapon can be added to WEAPONS and the script rerun. Also rewrites buffs.xml and adds missing
localization rows. Afterwards, add the weapon to loot.xml/traders.xml, add its icon recipe to make_icons.py and run it, and rerun
gen_item_modifiers.py and gen_serverside.py.
"""
import os
import re
import sys

game, mod = sys.argv[1:3]
van = open(os.path.join(game, "Data", "Config", "items.xml"), encoding="utf-8").read()
items_path = os.path.join(mod, "Config", "items.xml")
items = open(items_path, encoding="utf-8", newline="").read().replace("\r\n", "\n")
loc_path = os.path.join(mod, "Config", "Localization.csv")
loc = open(loc_path, encoding="utf-8", newline="").read().replace("\r\n", "\n")


def eg(name, body):
    """A signature effect group, written with the mod's indentation (item children at 3 tabs)."""
    lines = [l for l in body.strip("\n").split("\n")]
    return f'\t\t\t<effect_group name="{name}" tiered="false">\n' + "\n".join("\t\t\t\t" + l for l in lines) + "\n\t\t\t</effect_group>"


def pe(name, op, value, tags=None, tier=None, comment=None):
    s = f'<passive_effect name="{name}" operation="{op}" value="{value}"'
    if tier:
        s += f' tier="{tier}"'
    if tags:
        s += f' tags="{tags}"'
    s += "/>"
    return s + (f" <!-- {comment} -->" if comment else "")


MOD_SLOTS = '<passive_effect name="ModSlots" operation="base_set" value="4,4,4,4,4,4" tier="1,2,3,4,5,6"/>'

WEAPONS = [
    dict(
        name="DementivemeleeWpnBladeStalkersHarvester", title="Stalker's Harvester", parent="meleeWpnBladeT1HuntingKnife",
        value=2500, trader="baseTier2", type="Melee",
        edits=[
            (r'(name="AttacksPerMinute" operation="base_set" value=")120"', r'\g<1>130"'),
            (r'(name="DegradationMax" operation="base_set" value=")500,1000"', r'\g<1>900,1600"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_set" value=")12"', r'\g<1>19"'),
            (r'(name="HarvestCount" operation="base_set" value=")1(" tags="butcherHarvest")', r'\g<1>1.5\2'),
            (r'(name="DamageBonus" operation="base_add" value=")4"', r'\g<1>6"'),
            (r'(name="EntityDamage" operation="perc_add" value=")4(" tags="perkDeepCuts")', r'\g<1>6\2'),
            (r'(name="dEntityDamageSneak" value=")4"', r'\g<1>6"'),
        ],
        signature=[
            "<!-- Stalker's Harvester: 25% chance per hit to add a bleed stack, the same way the Serrated Blade mod does -->",
            eg("DementivemeleeWpnBladeStalkersHarvester bleed chance", """
<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="25"/>
<requirement name="CVarCompare" cvar="bleedCounter" operation="LT" value="@$maxBleedCounter" target="other"/>
	<triggered_effect trigger="onSelfPrimaryActionRayHit" action="ModifyCVar" target="other" cvar="bleedCounter" operation="add" value="1"/>
	<triggered_effect trigger="onSelfSecondaryActionRayHit" action="ModifyCVar" target="other" cvar="bleedCounter" operation="add" value="1"/>"""),
            eg("DementivemeleeWpnBladeStalkersHarvester bleed", """
<requirement name="CVarCompare" cvar="bleedCounter" operation="GT" value="0" target="other"/>
	<triggered_effect trigger="onSelfPrimaryActionRayHit" action="AddBuff" target="other" buff="buffInjuryBleeding"/>
	<triggered_effect trigger="onSelfSecondaryActionRayHit" action="AddBuff" target="other" buff="buffInjuryBleeding"/>"""),
        ],
        lore="An old hunter's knife that never stopped hunting. Its wounds keep bleeding long after the cut, it carves extra meat and hide off anything you bring down, and it hits hardest when your prey never sees you coming.",
        ability="25% chance to cause bleeding. +50% harvest from corpses. Sneak attacks deal 6x damage.",
    ),
    dict(
        name="DementivemeleeWpnClubGrandSlam", title="Grand Slam", parent="meleeWpnClubT1BaseballBat",
        value=2500, trader="baseTier2", type="Melee",
        edits=[
            (r'(name="AttacksPerMinute" operation="base_set" value=")52"', r'\g<1>58"'),
            (r'(name="DegradationMax" operation="base_set" value=")200,500"', r'\g<1>600,1000"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_set" value=")20"', r'\g<1>30"'),
            (r'(name="BlockDamage" operation="base_set" value=")18"', r'\g<1>27"'),
        ],
        signature=[
            "<!-- Grand Slam: power attacks launch what they hit and can knock it down -->",
            eg("DementivemeleeWpnClubGrandSlam home run", """
<requirement name="!EntityTagCompare" target="other" tags="trader"/>
<requirement name="IsAlive" target="other"/>
<triggered_effect trigger="onSelfSecondaryActionRayHit" action="Ragdoll" target="other" duration="2" force="400"/>
<triggered_effect trigger="onSelfSecondaryActionRayHit" action="AddBuff" target="other" buff="buffInjuryKnockdown01">
	<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="30"/>
</triggered_effect>"""),
        ],
        lore="Batter up! This bat swung for the fences in the last game ever played before the outbreak, and it still hasn't lost its touch.",
        ability="Power attacks send zombies flying and have a 30% chance to knock them down.",
    ),
    dict(
        name="DementivemeleeWpnSledgeBloodletter", title="Bloodletter", parent="meleeWpnSledgeT1IronSledgehammer",
        value=2500, trader="baseTier2", type="Melee",
        edits=[
            (r'(name="AttacksPerMinute" operation="base_set" value=")34"', r'\g<1>38"'),
            (r'(name="DegradationMax" operation="base_set" value=")200,400"', r'\g<1>600,900"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_set" value=")32"', r'\g<1>48"'),
            (r'(name="BlockDamage" operation="base_set" value=")52"', r'\g<1>78"'),
        ],
        signature=[
            "<!-- Bloodletter: every hit on a living target heals the wielder, kills heal more -->",
            eg("DementivemeleeWpnSledgeBloodletter life steal", """
<triggered_effect trigger="onSelfAttackedOther" action="ModifyStats" stat="Health" operation="add" value="8">
	<requirement name="IsAlive" target="other"/>
</triggered_effect>
<triggered_effect trigger="onSelfKilledOther" action="ModifyStats" stat="Health" operation="add" value="23"/><!-- the hit heal skips the killing blow (the target is dead by then), so 8 + 15 -->"""),
        ],
        lore="A heavy iron sledge with dried blood caked into every groove. Nobody knows who made it, but every swing that lands seems to give a little life back to whoever is holding it.",
        ability="Each hit heals you 8 health. Kills heal 15 more.",
    ),
    dict(
        name="DementivegunBowHellfire", title="Hellfire", parent="gunBowT1WoodenBow",
        value=2500, trader="bowsTier2", type="Gun",
        edits=[
            (r'(name="EntityDamage" operation="base_add" value=")9(" tags="perkArchery"/>) <!-- damage offset -->', r'\g<1>35\2 <!-- damage offset, 70 with ammoArrowStone -->'),
            (r'(name="ReloadSpeedMultiplier" operation="base_set" value=")\.9"', r'\g<1>1.2"'),
            (r'(name="DegradationMax" operation="base_set" value=")200,350"', r'\g<1>500,900"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
        ],
        signature=[
            "<!-- Hellfire: arrow hits can't trigger effects on the bow itself (onProjectileImpact skips the held item),",
            "     so the bow gives a buff while held and the buff sets targets on fire -->",
            eg("DementivegunBowHellfire fire arrows", """
<triggered_effect trigger="onSelfEquipStart" action="AddBuff" buff="buffDementiveHellfire"/>
<triggered_effect trigger="onSelfPrimaryActionStart" action="AddBuff" buff="buffDementiveHellfire"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveHellfire"/>"""),
        ],
        lore="Carved from a tree that burned for forty days and never fell. Arrows loosed from this bow have a habit of bursting into flames when they hit.",
        ability="35% chance to set targets on fire. Draws and reloads faster than a wooden bow.",
    ),
    dict(
        name="DementivegunBowWhisper", title="Whisper", parent="gunBowT1IronCrossbow",
        value=3000, trader="bowsTier2", type="Gun",
        edits=[
            (r'(<passive_effect name="MagazineSize" operation="base_set" value="1" tags="perkArchery"/>)',
             r'\1\n\t\t\t\t' + pe("EntityDamage", "base_add", "30", "perkArchery", comment="damage offset, 80 with ammoCrossbowBoltStone")),
            (r'(name="ReloadSpeedMultiplier" operation="base_set" value=")\.5(" tags="perkArchery"/>) <!-- 3.4s -->', r'\g<1>.7\2 <!-- 2.4s -->'),
            (r'(name="DegradationMax" operation="base_set" value=")200,350"', r'\g<1>500,900"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="perc_add" value=")2(" tags="perkArchery"/>)', r'\g<1>5\2'),
            (r'(name="dEntityDamageSneak" value=")2"', r'\g<1>5"'),
        ],
        signature=[],
        lore="A matte black crossbow built by a survivalist who preferred never to be heard. In the right hands it puts down anything that hasn't noticed you yet.",
        ability="Sneak attacks deal 5x damage. Reloads 40% faster than an iron crossbow.",
    ),
    dict(
        name="DementivegunRifleChainReaction", title="Chain Reaction", parent="gunRifleT0PipeRifle",
        value=2500, trader="baseTier2", type="Gun",
        edits=[
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_add" value=")-3(" tags="perkDeadEye"/>) <!-- damage offset -->', r'\g<1>40\2 <!-- damage offset, 87 with ammo762mmBulletBall -->'),
            (r'(name="DegradationMax" operation="base_set" value=")100,200"', r'\g<1>400,700"'),
        ],
        signature=[
            "<!-- Chain Reaction: whatever this rifle kills explodes (buffDementiveChainReaction in buffs.xml). Added twice on purpose: the second add is what sets it off -->",
            eg("DementivegunRifleChainReaction explosion", """
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" target="other" buff="buffDementiveChainReaction"/>
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" target="other" buff="buffDementiveChainReaction"/>"""),
        ],
        lore="Somebody packed this pipe rifle's ammo box with a little too much extra. Whatever it kills goes out with a bang, so keep your distance.",
        ability="Anything killed with this rifle explodes, dealing up to 120 damage to everything within 4 meters, including you.",
    ),
    dict(
        name="DementivegunShotgunFrostbite", title="Frostbite", parent="gunShotgunT0PipeShotgun",
        value=2500, trader="baseTier2", type="Gun",
        edits=[
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_add" value=")-2(" tags="perkBoomstick"/>) <!-- damage offset -->', r'\g<1>10\2 <!-- damage offset, 20.1 per pellet with ammoShotgunShell -->'),
            (r'(name="DegradationMax" operation="base_set" value=")100,200"', r'\g<1>400,700"'),
        ],
        signature=[
            "<!-- Frostbite: hits slow the target (buffDementiveFrostbite in buffs.xml) -->",
            eg("DementivegunShotgunFrostbite slow", """
<triggered_effect trigger="onSelfAttackedOther" action="AddBuff" target="other" buff="buffDementiveFrostbite"/>"""),
        ],
        lore="A pipe shotgun some lunatic rigged up with an old freezer compressor. Nobody knows how it works, but anything it hits slows to a crawl.",
        ability="Hits slow enemies by 50% for 4 seconds.",
    ),
    dict(
        name="DementivemeleeToolPickProspector", title="The Prospector", parent="meleeToolPickT2SteelPickaxe",
        value=3000, trader="baseTier3", type="Tool",
        edits=[
            (r'(name="AttacksPerMinute" operation="base_set" value=")55"', r'\g<1>62"'),
            (r'(name="DegradationMax" operation="base_set" value=")1000,2000"', r'\g<1>1500,3000"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_set" value=")23.2"', r'\g<1>30"'),
            (r'(<passive_effect name="BlockDamage" operation="base_set" value=")85(" tags="perkMiner69r,miningTool"/>)',
             r'\g<1>125\2\n\t\t\t\t' + pe("HarvestCount", "base_set", "1.5", "oreWoodHarvest")),
        ],
        signature=[],
        lore="An old prospector's steel pick that has struck more veins than anyone can count. It bites through rock and always seems to turn up a little more ore than you'd expect.",
        ability="+50% ore and stone from mining. Swings faster and lasts longer than a steel pickaxe.",
    ),
    dict(
        name="DementivegunMGRampage", title="Rampage", parent="gunMGT0PipeMachineGun",
        value=2500, trader="baseTier2", type="Gun",
        edits=[
            (r'(name="EntityDamage" operation="base_add" value=")-17(" tags="perkMachineGunner"/>) <!-- damage offset -->', r'\g<1>15\2 <!-- damage offset, 62 with ammo762mmBulletBall -->'),
            (r'(name="RoundsPerMinute" operation="base_set" value=")335"', r'\g<1>400"'),
            (r'(name="MagazineSize" operation="base_set" value=")15"', r'\g<1>30"'),
            (r'(name="DegradationMax" operation="base_set" value=")100,200"', r'\g<1>400,700"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
        ],
        signature=[
            "<!-- Rampage: every kill starts or refreshes buffDementiveRampage (buffs.xml); putting the gun away ends it -->",
            eg("DementivegunMGRampage kill streak", """
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" buff="buffDementiveRampage"/>
<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="buffDementiveRampage"/>"""),
        ],
        lore="Welded together from scrap during a horde night that never seemed to end. The more it kills, the faster it fires, and the faster you move.",
        ability="Each kill gives you 6 seconds of +25% fire rate, 20% faster reloads and 15% faster movement. Keep killing to keep it going.",
    ),
    dict(
        name="DementivegunHandgunLuckySeven", title="Lucky Seven", parent="gunHandgunT0PipePistol",
        value=2500, trader="baseTier2", type="Gun",
        edits=[
            (r'(name="RoundsPerMinute" operation="base_set" value=")126"', r'\g<1>150"'),
            (r'(name="MagazineSize" operation="base_set" value=")6"', r'\g<1>7"'),
            (r'<passive_effect name="ModSlots" [^>]*/>', MOD_SLOTS),
            (r'(name="EntityDamage" operation="base_add" value=")-4(" tags="perkGunslinger"/>) <!-- damage offset -->', r'\g<1>12\2 <!-- damage offset, 44 with ammo9mmBulletBall -->'),
            (r'(name="DegradationMax" operation="base_set" value=")100,200"', r'\g<1>400,700"'),
        ],
        signature=[
            "<!-- Lucky Seven: every shot rolls 1-100; on 7 or less the shot gets +600% damage. Same per-shot CVar approach as",
            "     vanilla's Uncontrolled Burst perk -->",
            eg("DementivegunHandgunLuckySeven lucky shot", """
<triggered_effect trigger="onSelfRangedBurstShotStart" action="ModifyCVar" cvar=".DementiveLuckySevenRoll" operation="set" value="randomint(1,100)"/>
<triggered_effect trigger="onSelfRangedBurstShotStart" action="ModifyCVar" cvar=".DementiveLuckySevenBonus" operation="set" value="0"/>
<triggered_effect trigger="onSelfRangedBurstShotStart" action="ModifyCVar" cvar=".DementiveLuckySevenBonus" operation="set" value="6">
	<requirement name="CVarCompare" cvar=".DementiveLuckySevenRoll" operation="LTE" value="7"/>
</triggered_effect>
<triggered_effect trigger="onSelfRangedBurstShotStart" action="PlaySound" sound="nerd_outfit_perk">
	<requirement name="CVarCompare" cvar=".DementiveLuckySevenRoll" operation="LTE" value="7"/>
</triggered_effect>
<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar=".DementiveLuckySevenBonus" operation="set" value="0"/>
<passive_effect name="EntityDamage" operation="perc_add" value="@.DementiveLuckySevenBonus"/>"""),
        ],
        lore="A beat-up pipe pistol with a pair of dice welded to the grip. Most shots are nothing special. Some shots are very, very special.",
        ability="Every shot has a 7% chance to hit for up to 7x damage. Holds 7 rounds.",
    ),
]

BUFFS = """<Dementive>

	<append xpath="/buffs">
		<!-- Given by the Hellfire bow while it is held: its arrows can set targets on fire -->
		<buff name="buffDementiveHellfire" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
			<effect_group>
				<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="35"/>
				<requirement name="CVarCompare" target="other" cvar="_underwater" operation="LT" value="0.3"/>
					<triggered_effect trigger="onProjectileImpact" action="ModifyCVar" target="other" cvar="$buffBurningElementDuration" operation="set" value="10"/>
					<triggered_effect trigger="onProjectileImpact" action="AddBuff" target="other" buff="buffBurningElement"/>
			</effect_group>
			<effect_group>
				<triggered_effect trigger="onSelfDied" action="RemoveBuff" buff="buffDementiveHellfire"/>
			</effect_group>
		</buff>

		<!-- Given by the Rampage machine gun on each kill -->
		<buff name="buffDementiveRampage" name_key="buffDementiveRampageName" description_key="buffDementiveRampageDesc" icon="ui_game_symbol_run_and_gun" icon_color="224,17,95">
			<stack_type value="replace"/>
			<duration value="6"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="RoundsPerMinute" operation="perc_add" value=".25" tags="perkMachineGunner"/>
				<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".2" tags="perkMachineGunner"/>
				<passive_effect name="RunSpeed" operation="perc_add" value=".15"/>
				<passive_effect name="WalkSpeed" operation="perc_add" value=".15"/>
			</effect_group>
		</buff>

		<!-- Applied by the Frostbite shotgun -->
		<buff name="buffDementiveFrostbite" name_key="buffDementiveFrostbiteName" description_key="buffDementiveFrostbiteDesc" icon="ui_game_symbol_cold" icon_color="128,200,255">
			<damage_type value="cold"/>
			<stack_type value="replace"/>
			<duration value="4"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="RunSpeed" operation="perc_subtract" value=".5"/>
				<passive_effect name="WalkSpeed" operation="perc_subtract" value=".5"/>
				<passive_effect name="CrouchSpeed" operation="perc_subtract" value=".5"/>
				<passive_effect name="JumpStrength" operation="perc_subtract" value=".5"/>
			</effect_group>
		</buff>

		<!-- Added twice to whatever the Chain Reaction rifle kills. Explode only runs on the server, but the kill event
		     fires on the shooter's machine, and buffs never start on a dead entity. Adding a buff the body already has
		     fires onSelfBuffStack right away on every machine the add reaches, the server included, so the blast
		     happens for every player. No block damage, but it hurts anyone close by, including the shooter -->
		<buff name="buffDementiveChainReaction" hidden="true">
			<stack_type value="replace"/>
			<duration value="1"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStack" action="Explode" blast_power="0" block_damage="0" block_radius="1" entity_damage="120" entity_radius="4" damage_type="Heat"/>
			</effect_group>
		</buff>
	</append>

</Dementive>
"""


def van_item(name):
    return re.search(r'\n<item name="%s">.*?\n</item>' % re.escape(name), van, re.S).group(0)


def build(w):
    v = van_item(w["parent"])
    unlocked = re.search(r'<property name="UnlockedBy" value="(\w+)"', v)
    head = [
        f"\t\t<!-- {w['title']} -->",
        f'\t\t<item name="{w["name"]}">',
        f'\t\t\t<property name="Extends" value="{w["parent"]}"/>',
        f'\t\t\t<property name="CustomIcon" value="{w["name"]}"/>',
        f'\t\t\t<property name="EconomicValue" value="{w["value"]}"/>',
        f'\t\t\t<property name="TraderStageTemplate" value="{w["trader"]}"/>',
    ]
    if unlocked:
        head.append(f'\t\t\t<property name="UnlockedBy" value="{unlocked.group(1)}"/>')
    # <stats> and effect groups are children at one tab in vanilla; the mod's item children are at three
    blocks = re.findall(r'\n(\t<stats>.*?\n\t</stats>|\t<effect_group.*?\n\t</effect_group>)', v, re.S)
    body = "\n".join("\n".join("\t\t" + l if l else l for l in b.split("\n")) for b in blocks)
    body = body.replace(f'<effect_group name="{w["parent"]}">', f'<effect_group name="{w["name"]}">', 1)
    for pattern, repl in w["edits"]:
        body, n = re.subn(pattern, repl, body)
        if n != 1:
            raise SystemExit(f"{w['name']}: edit {pattern!r} matched {n} times")
    sig = "\n".join(s if s.startswith("\t") else "\t\t\t" + s.replace("\n", "\n\t\t\t") for s in w["signature"])
    return "\n".join(head) + "\n\n" + body + ("\n\n" + sig if sig else "") + "\n\t\t</item>\n"


def csv_field(s):
    return f'"{s}"' if "," in s or '"' in s else s


new_items = []
new_loc = []
for w in WEAPONS:
    if f'<item name="{w["name"]}">' in items:
        print("already added:", w["name"])
        continue
    new_items.append(build(w))
    desc = f"{w['lore']}\\n\\n{w['ability']}"
    new_loc.append(f"{w['name']},items,{w['type']},,,,{csv_field(w['title'])},,,,,,,,,,,,,")
    new_loc.append(f"{w['name']}Desc,items,{w['type']},,,,{csv_field(desc)},,,,,,,,,,,,,")
new_loc.append("buffDementiveFrostbiteName,buffs,Buff,,,,Frostbite,,,,,,,,,,,,,")
new_loc.append("buffDementiveFrostbiteDesc,buffs,Buff,,,,Chilled to the bone and moving at half speed.,,,,,,,,,,,,,")
new_loc.append("buffDementiveRampageName,buffs,Buff,,,,Rampage,,,,,,,,,,,,,")
new_loc.append("buffDementiveRampageDesc,buffs,Buff,,,,Every kill keeps you going: faster fire rate and reloads with your machine gun and faster movement.,,,,,,,,,,,,,")
new_loc = [l for l in new_loc if l.split(",", 1)[0] + "," not in loc]

if new_items:
    end = items.rindex("\t</append>")
    items = items[:end] + "\n".join(new_items) + "\n" + items[end:]
    open(items_path, "w", encoding="utf-8", newline="").write(items.replace("\n", "\r\n"))
open(os.path.join(mod, "Config", "buffs.xml"), "w", encoding="utf-8", newline="").write(BUFFS.replace("\n", "\r\n"))
if new_loc:
    loc = loc.rstrip("\n") + "\n" + "\n".join(new_loc) + "\n"
    open(loc_path, "w", encoding="utf-8", newline="").write(loc.replace("\n", "\r\n"))
print(f"added {len(new_items)} weapons, {len(new_loc)} localization rows")
