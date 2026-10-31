"""Generate the AmmoExpanded mod (and its server-side copy) from the AMMO table below.

Usage: python gen_ammo.py <game dir> <AmmoExpanded dir> [<AmmoExpanded-SERVERSIDE dir>]
Each ammo type Extends a vanilla ammo item and carries copies of its effect groups (those are not inherited), with
edited damage and a signature effect group, plus a schematic that unlocks its recipe. Every gun, bow and crossbow
whose ammo list is the vanilla list for that caliber gets the new ammo appended. Rewrites Config/items.xml,
buffs.xml, recipes.xml, loot.xml, traders.xml and Localization.csv, and recolors the vanilla icons into
UIAtlases/ItemIconAtlas with Scripts/bin/IconTool.exe. The server-side copy uses the vanilla icons with a color tint.
"""
import os
import re
import shutil
import subprocess
import sys

game, mod = sys.argv[1:3]
server = sys.argv[3] if len(sys.argv) > 3 else None
cfg_dir = os.path.join(game, "Data", "Config")
van = open(os.path.join(cfg_dir, "items.xml"), encoding="utf-8").read()
van_loot = open(os.path.join(cfg_dir, "loot.xml"), encoding="utf-8").read()
icon_tool = os.path.join(os.path.dirname(__file__), "..", "bin", "IconTool.exe")

# The vanilla ammo list of each caliber. Any Magazine_items containing it gets the new ammo of that caliber
CALIBERS = {
    "9mm": dict(list="ammo9mmBulletBall,ammo9mmBulletHP,ammo9mmBulletAP", loot="group9mm", trader="40,150"),
    "44": dict(list="ammo44MagnumBulletBall,ammo44MagnumBulletHP,ammo44MagnumBulletAP", loot="group44Magnum", trader="15,60"),
    "762": dict(list="ammo762mmBulletBall,ammo762mmBulletHP,ammo762mmBulletAP", loot="group762mm", trader="20,100"),
    "shotgun": dict(list="ammoShotgunShell,ammoShotgunSlug,ammoShotgunBreachingSlug", loot="groupShotgunShell", trader="15,100"),
    "arrow": dict(list="ammoArrowStone,ammoArrowIron,ammoArrowSteelAP,ammoArrowFlaming,ammoArrowExploding", loot="groupArrow", trader="20,60"),
    "bolt": dict(list="ammoCrossbowBoltStone,ammoCrossbowBoltIron,ammoCrossbowBoltSteelAP,ammoCrossbowBoltFlaming,ammoCrossbowBoltExploding", loot="groupCrossbowBolt", trader="20,60"),
}

# Hit trigger: guns fire the selected ammo's events with the gun's own (ItemValue.FireEvent), arrows and bolts on impact
GUN_HIT, PROJECTILE_HIT = "onSelfAttackedOther", "onProjectileImpact"


def fire(chance, trigger=GUN_HIT):
    """Set the target on fire with the vanilla flaming arrow burn, the same way the flaming arrow does."""
    roll = "" if chance >= 100 else f'<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="{chance}"/>\n'
    return [(None, f"""{roll}<requirement name="CVarCompare" target="other" cvar="_underwater" operation="LT" value="0.3"/>
	<triggered_effect trigger="{trigger}" action="ModifyCVar" target="other" target_tags="zombie,animal,bandit" cvar="$buffBurningFlamingArrowDuration" operation="set" value="14">
		<requirement name="ProgressionLevel" progression_name="perkFiremansAlmanacMolotov" operation="Equals" value="0"/></triggered_effect>
	<triggered_effect trigger="{trigger}" action="ModifyCVar" target="other" target_tags="zombie,animal,bandit" cvar="$buffBurningFlamingArrowDuration" operation="set" value="16">
		<requirement name="ProgressionLevel" progression_name="perkFiremansAlmanacMolotov" operation="Equals" value="1"/></triggered_effect>
	<triggered_effect trigger="{trigger}" action="AddBuff" target="other" target_tags="zombie,animal,bandit" buff="buffBurningFlamingArrow"/>""")]


def bleed(chance, trigger=GUN_HIT):
    """Add a bleed stack and start bleeding, the same way the vanilla Serrated Blade mod does."""
    roll = "" if chance >= 100 else f'<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="{chance}"/>\n'
    return [
        (None, f"""{roll}<requirement name="CVarCompare" cvar="bleedCounter" operation="LT" value="@$maxBleedCounter" target="other"/>
	<triggered_effect trigger="{trigger}" action="ModifyCVar" target="other" target_tags="zombie,animal,bandit" cvar="bleedCounter" operation="add" value="1"/>"""),
        ("bleed", f"""<requirement name="CVarCompare" cvar="bleedCounter" operation="GT" value="0" target="other"/>
	<triggered_effect trigger="{trigger}" action="AddBuff" target="other" target_tags="zombie,animal,bandit" buff="buffInjuryBleeding"/>"""),
    ]


def knockdown(chance, trigger=GUN_HIT):
    return [(None, f"""<requirement name="RandomRoll" seed_type="Random" min_max="0,100" operation="LTE" value="{chance}"/>
	<triggered_effect trigger="{trigger}" action="AddBuff" target="other" target_tags="zombie,animal,bandit" buff="buffInjuryKnockdown01"/>""")]


def passives(body):
    return [(None, body.strip("\n"))]


# Frangible: armor stops twice as much (AP rounds use -.5 for half)
FRANGIBLE = """<passive_effect name="TargetArmor" operation="perc_add" value="1"/>
<display_value name="dTargetArmor" value="1"/>"""

DMG = r'(name="EntityDamage" operation="base_set" value=")[\d.]+(")'
BLOCK = r'(name="BlockDamage" operation="base_set" value=")[\d.]+(")'


def dmg(v):
    return (DMG, r"\g<1>%s\2" % v)


def block(v):
    return (BLOCK, r"\g<1>%s\2" % v)


def prop(name, v):
    return (r'(name="%s" operation="base_set" value=")[\d.]+(")' % name, r"\g<1>%s\2" % v)


AMMO = [
    # --- Incendiary: tier 2 (HP tier) ---
    dict(name="DementiveAmmo9mmIncendiary", title="9mm Incendiary Round", parent="ammo9mmBulletBall", caliber="9mm", tier=2,
         edits=[dmg(30)], signature=fire(15), tint="#FF5A00",
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 2), ("resourceBulletCasing", 1), ("resourceCoal", 1)],
         lore="A 9mm round with an incendiary charge packed behind the tip.",
         ability="15% chance per hit to set the target on fire."),
    dict(name="DementiveAmmo44Incendiary", title=".44 Magnum Incendiary Round", parent="ammo44MagnumBulletBall", caliber="44", tier=2,
         edits=[dmg(66)], signature=fire(35), tint="#FF5A00",
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 3), ("resourceBulletCasing", 1), ("resourceCoal", 1)],
         lore="A heavy .44 round with an incendiary charge packed behind the tip.",
         ability="35% chance per hit to set the target on fire."),
    dict(name="DementiveAmmo762Incendiary", title="7.62mm Incendiary Round", parent="ammo762mmBulletBall", caliber="762", tier=2,
         edits=[dmg(44)], signature=fire(25), tint="#FF5A00",
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 5), ("resourceBulletCasing", 1), ("resourceCoal", 1)],
         lore="A 7.62mm rifle round with an incendiary charge packed behind the tip.",
         ability="25% chance per hit to set the target on fire."),
    # --- Frangible: tier 2 ---
    dict(name="DementiveAmmo9mmFrangible", title="9mm Frangible Round", parent="ammo9mmBulletBall", caliber="9mm", tier=2,
         edits=[dmg(36), block(3)], signature=passives(FRANGIBLE) + bleed(15), tint="#C21F1F",
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 2), ("resourceBulletCasing", 1), ("resourceScrapIron", 2)],
         lore="A 9mm round with a pressed metal tip that shatters inside whatever it hits. Hard targets shrug it off.",
         ability="15% chance per hit to cause bleeding. Armor stops twice as much. Half block damage."),
    dict(name="DementiveAmmo44Frangible", title=".44 Magnum Frangible Round", parent="ammo44MagnumBulletBall", caliber="44", tier=2,
         edits=[dmg(80), block(6)], signature=passives(FRANGIBLE) + bleed(35), tint="#C21F1F",
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 3), ("resourceBulletCasing", 1), ("resourceScrapIron", 2)],
         lore="A .44 round with a pressed metal tip that shatters inside whatever it hits. Hard targets shrug it off.",
         ability="35% chance per hit to cause bleeding. Armor stops twice as much. Half block damage."),
    dict(name="DementiveAmmo762Frangible", title="7.62mm Frangible Round", parent="ammo762mmBulletBall", caliber="762", tier=2,
         edits=[dmg(54), block(4)], signature=passives(FRANGIBLE) + bleed(25), tint="#C21F1F",
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 5), ("resourceBulletCasing", 1), ("resourceScrapIron", 2)],
         lore="A 7.62mm round with a pressed metal tip that shatters inside whatever it hits. Hard targets shrug it off.",
         ability="25% chance per hit to cause bleeding. Armor stops twice as much. Half block damage."),
    # --- Tier 3 (AP tier) ---
    dict(name="DementiveAmmo762Match", title="7.62mm Match Grade Round", parent="ammo762mmBulletBall", caliber="762", tier=3,
         edits=[dmg(52)], tint="#FFD700",
         signature=passives("""<passive_effect name="HeadshotDamageModifier" operation="perc_add" value=".5" tags="head"/>
<passive_effect name="SpreadMultiplierAiming" operation="perc_add" value="-.3"/>
<passive_effect name="EntityPenetrationCount" operation="base_set" value="0"/>"""),
         recipe=[("resourceBulletTip", 2), ("resourceGunPowder", 5), ("resourceBulletCasing", 1), ("resourceScrapBrass", 1)],
         lore="A hand-loaded 7.62mm round made to exacting tolerances. Every one flies exactly where you put it.",
         ability="+50% headshot damage. 30% tighter spread when aiming. Doesn't pass through targets."),
    dict(name="DementiveAmmo44Explosive", title=".44 Magnum Explosive Tip Round", parent="ammo44MagnumBulletBall", caliber="44", tier=3,
         edits=[dmg(60)], tint="#F1C40F",
         # The Explode action only runs on the server, so the blast goes through a buff on the target (buffs.xml).
         # Buffs never start on a dead entity, so a killing hit adds a second buff twice: re-adding a buff fires
         # onSelfBuffStack right away, dead or not. The IsAlive check keeps hits on corpses from exploding
         signature=[(None, f"""<requirement name="IsAlive" target="other"/>
	<triggered_effect trigger="{GUN_HIT}" action="AddBuff" target="other" target_tags="zombie,animal,bandit" buff="buffDementiveAmmoExplosiveTip"/>"""),
                    ("kill", """<triggered_effect trigger="onSelfKilledOther" action="AddBuff" target="other" target_tags="zombie,animal,bandit" buff="buffDementiveAmmoExplosiveTipKill"/>
<triggered_effect trigger="onSelfKilledOther" action="AddBuff" target="other" target_tags="zombie,animal,bandit" buff="buffDementiveAmmoExplosiveTipKill"/>""")],
         recipe=[("resourceBulletTip", 1), ("resourceGunPowder", 5), ("resourceBulletCasing", 1), ("resourceScrapPolymers", 1)],
         lore="A .44 round with a tiny explosive charge in the tip. Don't fire it at anything standing next to you.",
         ability="Every hit sets off a small blast: 50 damage to everything within 2 meters, including you."),
    # --- Shotgun ---
    dict(name="DementiveAmmoShotgunDragonsBreath", title="Dragon's Breath Shell", parent="ammoShotgunShell", caliber="shotgun", tier=3,
         edits=[dmg(8), prop("MaxRange", 7), prop("DamageFalloffRange", 3)], signature=fire(100), tint="#FF2D00",
         recipe=[("resourceGunPowder", 5), ("resourcePaper", 1), ("resourceCoal", 2)],
         lore="A shotgun shell loaded with burning pellets instead of shot. Short range, but anything it touches goes up in flames.",
         ability="Sets targets on fire. 8 damage per pellet, 7 meter range."),
    dict(name="DementiveAmmoShotgunFlechette", title="Flechette Shell", parent="ammoShotgunShell", caliber="shotgun", tier=3,
         edits=[dmg(6), prop("RoundRayCount", 16), prop("MaxRange", 14), prop("DamageFalloffRange", 7),
                prop("SpreadDegreesVertical", 3.5), prop("SpreadDegreesHorizontal", 3.5)],
         signature=bleed(10), tint="#7FDBFF",
         recipe=[("resourceNail", 3), ("resourceGunPowder", 4), ("resourcePaper", 1)],
         lore="A shotgun shell packed with sixteen steel darts. Tighter and longer reaching than buckshot, and the darts tear.",
         ability="16 darts per shot with a 14 meter range. Each dart that hits has a 10% chance to cause bleeding."),
    dict(name="DementiveAmmoShotgunBeanBag", title="Bean Bag Round", parent="ammoShotgunSlug", caliber="shotgun", tier=2,
         edits=[dmg(40), block(5), prop("MaxRange", 15),
                (r'\n\t*<passive_effect name="TargetArmor" operation="perc_add" value="-\.5" />\n\t*<display_value name="dTargetArmor" value="-\.5"/>', ""),
                (r'(name="EntityPenetrationCount" operation="base_set" value=")2(" />\n\t*<display_value name="dTargetPenetration" value=")2(")', r"\g<1>0\g<2>0\3")],
         drop_groups=["perkPenetrator"], signature=knockdown(50), tint="#2ECC40",
         recipe=[("resourceCloth", 2), ("resourceGunPowder", 2), ("resourceScrapPolymers", 1)],
         lore="A cloth bag of lead shot that hits like a sledgehammer but rarely breaks the skin. Good for clearing some room.",
         ability="50% chance to knock the target down. Low damage, 15 meter range."),
    # --- Arrows and bolts ---
    dict(name="DementiveAmmoArrowBarbed", title="Barbed Broadhead Arrow", parent="ammoArrowIron", caliber="arrow", tier=2,
         edits=[dmg(36)], signature=bleed(100, PROJECTILE_HIT), tint="#C21F1F", packmule=True,
         recipe=[("resourceArrowHeadIron", 1), ("resourceWood", 1), ("resourceFeather", 1), ("resourceScrapIron", 2)],
         lore="An arrow with a wide, barbed broadhead that won't come out clean.",
         ability="Always causes bleeding."),
    dict(name="DementiveAmmoBoltBarbed", title="Barbed Crossbow Bolt", parent="ammoCrossbowBoltIron", caliber="bolt", tier=2,
         edits=[dmg(56)], signature=bleed(100, PROJECTILE_HIT), tint="#C21F1F", packmule=True,
         recipe=[("resourceArrowHeadIron", 1), ("resourceWood", 1), ("resourceFeather", 1), ("resourceScrapIron", 2)],
         lore="A crossbow bolt with a wide, barbed broadhead that won't come out clean.",
         ability="Always causes bleeding."),
    dict(name="DementiveAmmoArrowBlunt", title="Blunt Arrow", parent="ammoArrowIron", caliber="arrow", tier=2,
         edits=[dmg(30), (r'\n\t*<passive_effect name="TargetArmor" operation="perc_add" value="-\.2"/>\n\t*<display_value name="dTargetArmor" value="-\.2"/>', "")],
         signature=knockdown(40, PROJECTILE_HIT), tint="#8B5A2B", packmule=True,
         recipe=[("resourceWood", 2), ("resourceFeather", 1), ("resourceCloth", 1)],
         lore="An arrow with a heavy padded head. It won't pierce much, but it lands like a punch.",
         ability="40% chance to knock the target down."),
    dict(name="DementiveAmmoBoltBlunt", title="Blunt Crossbow Bolt", parent="ammoCrossbowBoltIron", caliber="bolt", tier=2,
         edits=[dmg(45), (r'\n\t*<passive_effect name="TargetArmor" operation="perc_add" value="-\.2"/>\n\t*<display_value name="dTargetArmor" value="-\.2"/>', "")],
         signature=knockdown(50, PROJECTILE_HIT), tint="#8B5A2B", packmule=True,
         recipe=[("resourceWood", 2), ("resourceFeather", 1), ("resourceCloth", 1)],
         lore="A crossbow bolt with a heavy padded head. It won't pierce much, but it lands like a punch.",
         ability="50% chance to knock the target down."),
]

BUFFS = """<Dementive>

	<append xpath="/buffs">
		<!-- .44 Magnum Explosive Tip: added to whatever the round hits and doesn't kill. MinEventActionExplode only runs
		     on the server, and buffs on zombies run there, so the blast works when a client fires too -->
		<buff name="buffDementiveAmmoExplosiveTip" hidden="true">
			<stack_type value="ignore"/>
			<duration value="1"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="Explode" blast_power="0" block_damage="5" block_radius="1" entity_damage="50" entity_radius="2" damage_type="Heat"/>
				<triggered_effect trigger="onSelfBuffStart" action="RemoveBuff" buff="buffDementiveAmmoExplosiveTip"/>
			</effect_group>
		</buff>

		<!-- .44 Magnum Explosive Tip on a killing hit: added twice to the body. Buffs never start on a dead entity, but
		     adding one the body already has fires onSelfBuffStack right away on every machine the add reaches, the
		     server included. The blast only goes off on the stack, so it happens once -->
		<buff name="buffDementiveAmmoExplosiveTipKill" hidden="true">
			<stack_type value="replace"/>
			<duration value="1"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStack" action="Explode" blast_power="0" block_damage="5" block_radius="1" entity_damage="50" entity_radius="2" damage_type="Heat"/>
				<triggered_effect trigger="onSelfBuffStack" action="RemoveBuff" buff="buffDementiveAmmoExplosiveTipKill"/>
			</effect_group>
		</buff>
	</append>

</Dementive>
"""


def van_item(name):
    return re.search(r'\n<item name="%s">.*?\n</item>' % re.escape(name), van, re.S).group(0)


def van_prop(name, prop_name):
    """A property of a vanilla item, following its Extends chain."""
    while name:
        item = van_item(name)
        m = re.search(r'<property name="%s" value="([^"]*)"' % prop_name, item)
        if m:
            return m.group(1)
        ext = re.search(r'<property name="Extends" value="(\w+)"', item)
        name = ext.group(1) if ext else None
    return None


def eg(name, body):
    lines = body.split("\n")
    open_tag = f'\t\t\t<effect_group name="{name}" tiered="false">' if name else '\t\t\t<effect_group tiered="false">'
    return open_tag + "\n" + "\n".join("\t\t\t\t" + l for l in lines) + "\n\t\t\t</effect_group>"


def trader_template(a):
    if a["caliber"] in ("arrow", "bolt"):
        return "arrowsTier2" if a["tier"] == 2 else "arrowsTier3"
    return "ammoTier2" if a["tier"] == 2 else "ammoTier3"


def build(a):
    v = van_item(a["parent"])
    # Price like the vanilla HP/AP round (or steel/flaming arrow) of the same caliber
    value = int(van_prop(a["parent"], "EconomicValue")) * (2 if a["tier"] == 2 else 3)
    head = [
        f"\t\t<!-- {a['title']} -->",
        f'\t\t<item name="{a["name"]}">',
        f'\t\t\t<property name="Extends" value="{a["parent"]}"/>',
        f'\t\t\t<property name="CustomIcon" value="{a["name"]}"/>',
        f'\t\t\t<property name="DescriptionKey" value="{a["name"]}Desc"/>',
        f'\t\t\t<property name="EconomicValue" value="{value}"/>',
        f'\t\t\t<property name="TraderStageTemplate" value="{trader_template(a)}"/>',
        f'\t\t\t<property name="UnlockedBy" value="{a["name"]}Schematic"/>',
    ]
    blocks = re.findall(r'\n(\t<effect_group.*?\n\t</effect_group>)', v, re.S)
    blocks = [b for b in blocks if not any(f'name="{g}"' in b.split("\n")[0] for g in a.get("drop_groups", []))]
    body = "\n".join("\n".join("\t\t" + l if l else l for l in b.split("\n")) for b in blocks)
    body = body.replace(f'<effect_group name="{a["parent"]}"', f'<effect_group name="{a["name"]}"', 1)
    for pattern, repl in a["edits"]:
        body, n = re.subn(pattern, repl, body, count=1)
        if n != 1:
            raise SystemExit(f"{a['name']}: edit {pattern!r} matched nothing")
    sig = "\n".join(eg(f"{a['title']}{' ' + suffix if suffix else ''}", b) for suffix, b in a["signature"])
    return "\n".join(head) + "\n\n" + body + "\n\n" + sig + "\n\t\t</item>\n"


def schematic(a):
    return "\n".join([
        f'\t\t<item name="{a["name"]}Schematic">',
        '\t\t\t<property name="Extends" value="schematicNoQualityMaster"/>',
        '\t\t\t<property name="CreativeMode" value="Player"/>',
        f'\t\t\t<property name="CustomIcon" value="{a["name"]}"/>',
        f'\t\t\t<property name="Unlocks" value="{a["name"]}"/>',
        '\t\t\t<effect_group tiered="false">',
        f'\t\t\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="{a["name"]}" operation="set" value="1"/>',
        '\t\t\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="GiveExp" exp="50"/>',
        '\t\t\t</effect_group>',
        '\t\t</item>\n',
    ])


def recipe(a):
    if a.get("packmule"):
        tag = 'craft_time="2.4" tags="learnable,packMuleCrafting"'
    else:
        tag = f'craft_time="{3.6 if a["tier"] == 2 else 4.8}" craft_area="workbench" tags="learnable,workbenchCrafting"'
    ings = "\n".join(f'\t\t\t<ingredient name="{n}" count="{c}"/>' for n, c in a["recipe"])
    return f'\t\t<recipe name="{a["name"]}" count="1" {tag}>\n{ings}\n\t\t</recipe>'


def loot_count(group, parent):
    """The count vanilla uses for this caliber's rounds in that loot group."""
    m = re.search(r'<lootgroup name="%s">(.*?)</lootgroup>' % group, van_loot, re.S)
    if not m:
        raise SystemExit(f"no vanilla loot group {group}")
    c = re.search(r'count="([\d,]+)"', m.group(1))
    return c.group(1)


def csv_field(s):
    return '"' + s.replace('"', '""') + '"' if "," in s or '"' in s else s


def loc_row(key, kind, text):
    return f"{key},{kind},,,,{csv_field(text)},,,,,,,,,,,,,"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n"))


# --- items.xml: ammo, schematics, and the ammo lists ---
items = ["<Dementive>\n",
         "\t<!-- Special ammo for the vanilla guns, bows and crossbows. Generated by Scripts/AmmoExpanded/gen_ammo.py -->",
         '\t<append xpath="/items">']
items += [build(a) for a in AMMO]
items.append("\t\t<!-- Schematics: each one unlocks its ammo's recipe -->")
items += [schematic(a) for a in AMMO]
items.append("\t</append>\n")
items.append("\t<!-- Add the ammo to every gun, bow and crossbow that uses the vanilla ammo list for its caliber. Guns from other\n"
             "\t     mods that inherit their ammo list from a vanilla gun get it too -->")
for cal, c in CALIBERS.items():
    names = ",".join(a["name"] for a in AMMO if a["caliber"] == cal)
    items.append(f"\t<append xpath=\"/items/item/property[@class]/property[@name='Magazine_items'][contains(@value, '{c['list']}')]/@value\">,{names}</append>")
items.append("\n</Dementive>\n")
items = "\n".join(items)

recipes = "<Dementive>\n\n\t<append xpath=\"/recipes\">\n" + "\n\n".join(recipe(a) for a in AMMO) + "\n\t</append>\n\n</Dementive>\n"

# --- loot.xml ---
loot = ["<Dementive>\n",
        '\t<append xpath="/lootcontainers/lootprobtemplates">',
        "\t\t<!-- Loose rounds in ammo loot: a quarter as likely as a vanilla HP (tier 2) or AP (tier 3) round once the loot",
        "\t\t     stage reaches the level those start dropping at -->",
        '\t\t<lootprobtemplate name="DementiveAmmoLootT2">\n\t\t\t<loot level="0,29" prob="0"/>\n\t\t\t<loot level="30,999999" prob="0.25"/>\n\t\t</lootprobtemplate>',
        '\t\t<lootprobtemplate name="DementiveAmmoLootT3">\n\t\t\t<loot level="0,87" prob="0"/>\n\t\t\t<loot level="88,999999" prob="0.25"/>\n\t\t</lootprobtemplate>',
        "\t</append>\n",
        "\t<!-- Schematics drop alongside the vanilla mod schematics, together about as often as three of those -->",
        "\t<insertBefore xpath=\"/lootcontainers/lootgroup[@name='schematicsModsAndGeneralT0']\">"]
for tier, group in ((2, "T1"), (3, "T2")):
    loot.append(f'\t\t<lootgroup name="groupDementiveAmmoSchematics{group}">')
    loot += [f'\t\t\t<item name="{a["name"]}Schematic"/>' for a in AMMO if a["tier"] == tier]
    loot.append("\t\t</lootgroup>")
loot.append("\t</insertBefore>")
for group in ("T1", "T2"):
    loot.append(f"\t<append xpath=\"/lootcontainers/lootgroup[@name='schematicsModsAndGeneral{group}']\">\n"
                f'\t\t<item group="groupDementiveAmmoSchematics{group}" prob="3"/>\n\t</append>')
loot.append("")
for cal, c in CALIBERS.items():
    for size in ("Small", "Medium", "Large"):
        group = c["loot"] + size
        members = [a for a in AMMO if a["caliber"] == cal]
        loot.append(f"\t<append xpath=\"/lootcontainers/lootgroup[@name='{group}']\">")
        for a in members:
            loot.append(f'\t\t<item name="{a["name"]}" count="{loot_count(group, a["parent"])}" loot_stage_count_mod="0.01" loot_prob_template="DementiveAmmoLootT{a["tier"]}"/>')
        loot.append("\t</append>")
loot.append("\n</Dementive>\n")
loot = "\n".join(loot)

# --- traders.xml ---
def trader_count(cal):
    lo, hi = (int(x) for x in CALIBERS[cal]["trader"].split(","))
    return f"{max(1, lo // 2)},{hi // 2}"


traders = ["<Dementive>\n",
           "\t<!-- Traders stock the rounds rarely (weight 0.3 against 1 for a vanilla round, in half the amount): tier 2 with",
           "\t     the HP rounds, tier 3 with the AP rounds, arrows and bolts with the others. Schematics sell alongside the",
           "\t     vanilla mod schematics, together about as often as three of those. -->"]
for group, pick in (("ammoHP", lambda a: a["tier"] == 2 and a["caliber"] not in ("arrow", "bolt")),
                    ("ammoAP", lambda a: a["tier"] == 3 and a["caliber"] not in ("arrow", "bolt")),
                    ("ammoArrowsBolts", lambda a: a["caliber"] in ("arrow", "bolt")),
                    ("ammoAll", lambda a: True)):
    traders.append(f"\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='{group}']\">")
    traders += [f'\t\t<item name="{a["name"]}" count="{trader_count(a["caliber"])}" prob="0.3"/>' for a in AMMO if pick(a)]
    traders.append("\t</append>")
traders.append("\n\t<insertBefore xpath=\"/traders/trader_item_groups/trader_item_group[@name='schematicsModsCommon']\">")
traders.append('\t\t<trader_item_group name="groupDementiveAmmoSchematics">')
traders += [f'\t\t\t<item name="{a["name"]}Schematic"/>' for a in AMMO]
traders.append("\t\t</trader_item_group>\n\t</insertBefore>")
traders.append("\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='schematicsModsCommon']\">\n"
               '\t\t<item group="groupDementiveAmmoSchematics" prob="3"/>\n\t</append>')
traders.append("\n</Dementive>\n")
traders = "\n".join(traders)

# --- Localization ---
header = "Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"
loc = [header]
for a in AMMO:
    loc.append(loc_row(a["name"], "items,Ammo", a["title"]))
    loc.append(loc_row(a["name"] + "Desc", "items,Ammo", f"{a['lore']}\\n\\n{a['ability']}"))
    loc.append(loc_row(a["name"] + "Schematic", "items,Schematic", a["title"] + " Schematic"))

cfg = os.path.join(mod, "Config")
write(os.path.join(cfg, "items.xml"), items)
write(os.path.join(cfg, "buffs.xml"), BUFFS)
write(os.path.join(cfg, "recipes.xml"), recipes)
write(os.path.join(cfg, "loot.xml"), loot)
write(os.path.join(cfg, "traders.xml"), traders)
write(os.path.join(cfg, "Localization.csv"), "\n".join(loc) + "\n")
print(f"{len(AMMO)} ammo types written to {cfg}")


def vanilla_icon(name):
    icon = van_prop(name, "CustomIcon")
    return icon or name


atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
os.makedirs(atlas, exist_ok=True)
for a in AMMO:
    src = os.path.join(game, "Data", "ItemIcons", vanilla_icon(a["parent"]) + ".png")
    subprocess.run([icon_tool, src, os.path.join(atlas, a["name"] + ".png"), a["tint"], "0.62"], check=True)
print(f"{len(AMMO)} icons written to {atlas}")

if server:
    scfg = os.path.join(server, "Config")
    os.makedirs(scfg, exist_ok=True)
    tinted = items
    for a in AMMO:
        tinted = tinted.replace(f'<property name="CustomIcon" value="{a["name"]}"/>',
                                f'<property name="CustomIcon" value="{vanilla_icon(a["parent"])}"/>\n\t\t\t<property name="CustomIconTint" value="{a["tint"]}"/>')
    write(os.path.join(scfg, "items.xml"), tinted)
    for f in os.listdir(cfg):
        if f != "items.xml":
            shutil.copyfile(os.path.join(cfg, f), os.path.join(scfg, f))
    print(f"server-side copy written to {scfg}")
