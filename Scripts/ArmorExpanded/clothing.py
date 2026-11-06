"""The named clothing of Armor Expanded: 20 pieces on top of the vanilla clothing (hot/cold insulation only).
Imported by gen_armor.py, which writes the pieces' items, buffs, loot, traders, localization and icons.

Each piece Extends the vanilla clothing item of its slot and tier, so it keeps that item's tags (the storm survival
bonus counts clothing by the clothingT1/T2/T3 tags). Effect groups aren't inherited through Extends, so the vanilla
group (no mod slots, hot and cold resistance by quality) is written out again, with the warm or cool bonus, plus a
signature group. A few perks need a hidden worn-marker buff (added on equip, removed on unequip) that a vanilla buff
patch below checks; see MARKERS and the patches at the bottom.
"""
import os
import re
import xml.etree.ElementTree as ET

# Hot and cold resistance compared to the vanilla piece of the same tier ("warm" = cold resistance, "cool" = heat)
WARM = 1.1       # warm and cool pieces
VERY_WARM = 1.2  # the heavy (tier 3) warm pieces
ECONOMIC_VALUE = {1: 600, 2: 900, 3: 1200}
TIER_WORD = {1: "tattered", 2: "patchwork", 3: "ThermaCore"}
# Trader stages: the same thresholds as the vanilla clothingTier1/2/3 (which only list quality 0, so they would hide
# quality 1-6 pieces from every trader), for the quality 1-6 pieces
TRADER_STAGE = {1: 1, 2: 25, 3: 55}
# Loot stages: the same thresholds as the vanilla clothing groups' ProbT0, ProbT1Cap and ProbT2Cap (0, 30, 88)
LOOT_STAGE = {2: 30, 3: 88}

KILL = '<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>'


def equip(*buffs):
    """Trigger lines that add the worn markers (and flags) on equip and remove them on unequip."""
    start = [f'<triggered_effect trigger="onSelfEquipStart" action="AddBuff" buff="{buffs[0]}"/>']
    stop = [f'<triggered_effect trigger="onSelfEquipStop" action="RemoveBuff" buff="{b}"/>' for b in buffs]
    return "\n".join(start + stop)


CLOTHES = [
    # --- Head ---
    dict(
        key="WatchCap", title="Wool Watch Cap", parent="clothingHeadT1", warm=WARM, tint="#3A4A6A",
        # CarryCapacity is the number of backpack slots the player has (EntityPlayer.UpdateBagpackSize reads it with
        # the worn items), the same effect as the vanilla storage pocket armor mod
        signature="""
<passive_effect name="CarryCapacity" operation="base_add" value="2"/>""",
        lore="A navy wool watch cap with a deep roll at the brim. Somehow there's always room for one more thing in it.",
        ability="+2 backpack slots.",
    ),
    dict(
        key="SunHat", title="Straw Sun Hat", parent="clothingHeadT1", cool=WARM, tint="#D8B050",
        # WaterChangeOT is the water drain over time (base .0111 a second); like Hard Traveler this is a perc_add, so it
        # scales the whole of that drain
        signature="""
<passive_effect name="WaterChangeOT" operation="perc_add" value="-.15"/>""",
        lore="A wide straw hat that keeps the sun off your neck. You stay cooler, and you sweat less.",
        ability="Water drains 15% slower.",
    ),
    dict(
        key="WelderCap", title="Welder's Cap", parent="clothingHeadT2", tint="#FF8A20",
        # The burning buffs' damage is patched at the bottom of this file (the marker is what they check)
        signature=equip("buffDementiveClothingWelderCap"),
        lore="A flame-print welder's cap, singed at the edges. Sparks and slag roll right off it.",
        ability="Burning damage over time ticks 25% weaker.",
    ),
    dict(
        key="Boonie", title="Birdwatcher's Boonie", parent="clothingHeadT2", cool=WARM, tint="#7A8450",
        # Noise is worked out on the server, which can't tell a remote player is walking, so the owner keeps a
        # walking flag buff (synced) up to date. Crouching is the _crouching cvar, as in vanilla's Night Stalker
        signature="""
<passive_effect name="NoiseMultiplier" operation="perc_add" value="-.15">
	<requirement name="CVarCompare" cvar="_crouching" operation="Equals" value="1"/>
</passive_effect>
<passive_effect name="NoiseMultiplier" operation="perc_add" value="-.15">
	<requirement name="CVarCompare" cvar="_crouching" operation="Equals" value="0"/>
	<requirement name="HasBuff" buff="buffDementiveClothingWalking"/>
</passive_effect>
""" + equip("buffDementiveClothingBoonie", "buffDementiveClothingWalking"),
        lore="A floppy khaki boonie with a feather tucked in the band. Its owner could sit in a hedge all day and never spook a thing.",
        ability="15% less noise while walking or crouching.",
    ),
    dict(
        key="Ushanka", title="Trapper's Ushanka", parent="clothingHeadT3", warm=VERY_WARM, tint="#8A5A30",
        signature="""
<passive_effect name="StaminaMax" operation="perc_add" value=".1"/>""",
        lore="A fur trapper's ushanka with the flaps tied down. Nothing in the deep cold gets past it, and it never seems to tire.",
        ability="+10% max stamina.",
    ),

    # --- Outfit ---
    dict(
        key="UnionSuit", title="Thermal Union Suit", parent="clothingOutfitT1", warm=WARM, tint="#C8B890",
        signature="""
<passive_effect name="HealthMax" operation="perc_add" value=".05"/>""",
        lore="Red waffle-knit long johns, buttoned to the chin. Grandpa swore they cured everything.",
        ability="+5% max health.",
    ),
    dict(
        key="Coveralls", title="Mechanic's Coveralls", parent="clothingOutfitT1", tint="#2A5A9A",
        signature="""
<passive_effect name="CarryCapacity" operation="base_add" value="4"/>""",
        lore="Oil-stained blue coveralls with a pocket on every limb. Wrenches, rags, one more spare part.",
        ability="+4 backpack slots.",
    ),
    dict(
        key="Slicker", title="Fisherman's Slicker", parent="clothingOutfitT2", tint="#E8B800",
        # buffElementWet is patched at the bottom of this file: rain and swimming both feed it through _wetnessrate
        signature=equip("buffDementiveClothingSlicker"),
        lore="A yellow oilskin slicker from a trawler. Rain beads up and runs off it, and the sea does too.",
        ability="Rain and swimming make you wet 50% slower.",
    ),
    dict(
        key="HuntingJacket", title="Blind Hunter's Jacket", parent="clothingOutfitT2", warm=WARM, tint="#6A5A30",
        signature="""
<passive_effect name="NoiseMultiplier" operation="perc_add" value="-.1">
	<requirement name="CVarCompare" cvar="_crouching" operation="Equals" value="1"/>
</passive_effect>""",
        lore="A quilted camo jacket with a blaze-orange collar, worn soft from long mornings in a deer blind.",
        ability="10% less noise while crouched.",
    ),
    dict(
        key="Sheepskin", title="Sheepskin Coat", parent="clothingOutfitT3", warm=VERY_WARM, tint="#D8B888",
        # The attacker is "other" when incoming damage is resisted (as for Geiger Gloves). Zombies and animals attack in
        # melee; fire, falls, explosions and traps have no attacker and are left alone
        signature="""
<passive_effect name="GeneralDamageResist" operation="base_add" value=".1">
	<requirement name="EntityTagCompare" target="other" tags="zombie,animal"/>
</passive_effect>""",
        lore="A heavy shearling coat, leather outside and fleece in. Teeth and claws find it hard going.",
        ability="Take 10% less damage from zombie and animal attacks.",
    ),

    # --- Hands ---
    dict(
        key="Mittens", title="Knitted Mittens", parent="clothingHandsT1", warm=WARM, tint="#B02A22",
        # Stamina comes back at a base rate read with the movement tag, like the Athletic helmet's
        signature="""
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".05" tags="idle,walking"/>""",
        lore="Chunky red and white mittens, knitted by someone who loved you. They keep your hands warm and your breath steady.",
        ability="Stamina regenerates 5% faster.",
    ),
    dict(
        key="WorkGloves", title="Work Gloves", parent="clothingHandsT1", tint="#9A7040",
        # Swing stamina is asked for with the action tags only; miningTool also tags the auger, which is a motor tool
        signature="""
<passive_effect name="StaminaLoss" operation="perc_add" value="-.1" tags="primary,secondary">
	<requirement name="HoldingItemHasTags" tags="axe,miningTool"/>
	<requirement name="!HoldingItemHasTags" tags="motorTool"/>
</passive_effect>""",
        lore="Stiff canvas and leather work gloves, broken in on a hundred fence posts. Your hands know what to do.",
        ability="Axes and pickaxes cost 10% less stamina per swing.",
    ),
    dict(
        key="Fingerless", title="Fingerless Gloves", parent="clothingHandsT2", cool=WARM, tint="#2A2A2A",
        signature="""
<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".1" tags="gun"/>""",
        lore="Black leather gloves with the fingertips cut away. Nothing between you and the cartridge.",
        ability="Guns reload 10% faster.",
    ),
    dict(
        key="WelderGauntlets", title="Welding Gauntlets", parent="clothingHandsT3", tint="#C06A20",
        # Shocks (fence posts, stun batons, traps) are damage over time from buffShocked, which ignores armor; that buff
        # is patched at the bottom of this file. Electrical hits that armor does resist get the same 25% here
        signature="""
<passive_effect name="ElementalDamageResist" operation="base_add" value="25" tags="electrical"/>
""" + equip("buffDementiveClothingGauntlets"),
        lore="Scorched leather gauntlets to the elbow, rubber-lined inside. Whatever the arc throws at you, they take most of it.",
        ability="Electrical damage taken is cut by 25%, including shocks from fences and traps.",
    ),
    dict(
        key="Mountaineer", title="Mountaineer's Gloves", parent="clothingHandsT3", warm=VERY_WARM, tint="#8AB8E0",
        # buffPlayerFallingDamage is patched at the bottom of this file
        signature=equip("buffDementiveClothingMountaineer"),
        lore="Insulated climbing gloves with a rubber grip, frosted white at the knuckles. A good grip makes for a softer landing.",
        ability="Falls hurt 15% less.",
    ),

    # --- Feet ---
    dict(
        key="WoolSocks", title="Wool Socks and Clogs", parent="clothingFeetT1", warm=WARM, tint="#9A8A70",
        # Same as the Boonie: the owner keeps a moving flag (walking or running) for the server's noise calculation
        signature="""
<passive_effect name="NoiseMultiplier" operation="perc_add" value="-.1">
	<requirement name="HasBuff" buff="buffDementiveClothingMoving"/>
</passive_effect>
""" + equip("buffDementiveClothingSocks", "buffDementiveClothingMoving"),
        lore="Thick grey wool socks in a pair of worn wooden clogs, padded with felt. Funny how quiet a clog can be.",
        ability="Your footsteps are 10% quieter.",
    ),
    dict(
        key="GumBoots", title="Gum Boots", parent="clothingFeetT2", warm=WARM, tint="#1F7A3A",
        # Wetness has no separate feet effect, so these slow how fast it builds (buffElementWet is patched at the
        # bottom of this file). Swimming reads WalkSpeed, swim-sprinting RunSpeed, like Bare Wraps
        signature="""
<passive_effect name="WalkSpeed" operation="perc_add" value=".25">
	<requirement name="EntityHasMovementTag" tags="swimming"/>
</passive_effect>
<passive_effect name="RunSpeed" operation="perc_add" value=".25">
	<requirement name="EntityHasMovementTag" tags="swimmingRun"/>
</passive_effect>
""" + equip("buffDementiveClothingGumBoots"),
        lore="Green rubber boots to the knee, with a wool liner. The puddles never reach your socks.",
        ability="Swim 25% faster. Wetness builds 25% slower.",
    ),
    dict(
        key="Hiking", title="Hiking Boots", parent="clothingFeetT2", tint="#6A4020",
        # Sprinting is 10 x (1 - 1.45) = -4.5 a second; 10% of that is .045 (see Logrollers)
        signature="""
<passive_effect name="StaminaChangeOT" operation="perc_add" value=".045" tags="running"/>""",
        lore="Broken-in leather hiking boots with red laces. They've seen a few mountains and every one of them is still behind you.",
        ability="Sprinting uses 10% less stamina.",
    ),
    dict(
        key="Desert", title="Desert Boots", parent="clothingFeetT2", cool=WARM, tint="#C8A068",
        # Walking, sprinting and crouch-walking read WalkSpeed, RunSpeed and CrouchSpeed. InBiome 5 is the desert (vanilla's
        # Oasis smoothie uses it the same way)
        signature="""
<passive_effect name="WalkSpeed" operation="perc_add" value=".05">
	<requirement name="InBiome" biome="5"/>
</passive_effect>
<passive_effect name="RunSpeed" operation="perc_add" value=".05">
	<requirement name="InBiome" biome="5"/>
</passive_effect>
<passive_effect name="CrouchSpeed" operation="perc_add" value=".05">
	<requirement name="InBiome" biome="5"/>
</passive_effect>""",
        lore="Sand-colored suede boots with a crepe sole. The dunes feel a lot shorter in them.",
        ability="Move 5% faster in the desert biome.",
    ),
    dict(
        key="Snow", title="Snow Boots", parent="clothingFeetT3", warm=VERY_WARM, tint="#C8E4F4",
        # InBiome 1 is the snow biome
        signature="""
<passive_effect name="WalkSpeed" operation="perc_add" value=".05">
	<requirement name="InBiome" biome="1"/>
</passive_effect>
<passive_effect name="RunSpeed" operation="perc_add" value=".05">
	<requirement name="InBiome" biome="1"/>
</passive_effect>
<passive_effect name="CrouchSpeed" operation="perc_add" value=".05">
	<requirement name="InBiome" biome="1"/>
</passive_effect>""",
        lore="Fur-lined snow boots with wide soles. You walk on the drifts instead of through them.",
        ability="Move 5% faster in the snow biome.",
    ),
]
for c in CLOTHES:
    c["name"] = "DementiveClothing" + c["key"]
    c["tier"] = int(c["parent"][-1])
    c["weight"] = "Light"

# Icon recipes for IconTool.exe fx (see the ops at the top of Scripts/WeaponsExpanded/IconTool.cs), in the style of the
# armor's: a paint job, weave, decal or sheen per piece. The server-side copy uses the vanilla icon with `tint` instead.
ICONS = {
    "DementiveClothingWatchCap": ["map:#05080f,#2a3a5a,#a0b4d8", "pattern:speckle,c1=#d8e0f0,scale=3,amount=.6,op=.45,seed=2", "sheen:.15", "rim:#a0b8e0,2,.35"],
    "DementiveClothingSunHat": ["map:#2a1a05,#c8a040,#fff0b0", "pattern:plaid,c1=#8a6a20,c2=#f0d890,scale=6,op=.55,seed=3", "rim:#fff0b0,3,.5", "glow:#ffd24a,7,.5", "sparkle:#fff6c0,2,10,4"],
    "DementiveClothingWelderCap": ["map:#0a0a0c,#3a4a5a,#a0b0c0", "pattern:flames,c1=#ffd040,c2=#ff5a10,c3=#2a0a00,op=1,reach=.55,count=4,seed=6,shade=.35", "embers:#ffc040,8,1.4,5", "sheen:.3"],
    "DementiveClothingBoonie": ["pattern:camo,c1=#8a8450,c2=#4a5a2a,c3=#b8a878,scale=14,op=.9,seed=4,shade=.7", "pattern:speckle,c1=#2a2a10,scale=5,amount=.55,op=.35,seed=7", "rim:#d8d090,2,.4"],
    "DementiveClothingUshanka": ["map:#120a04,#6b4a2a,#d8b888", "pattern:speckle,c1=#f4e8d0,scale=4,amount=.62,op=.55,seed=5", "rim:#f0e0c0,3,.5", "embers:#ffffff,10,1.4,3"],
    "DementiveClothingUnionSuit": ["map:#1a0806,#c8b890,#fff4e0", "pattern:dimples,c1=#8a1f1a,scale=6,op=.7,seed=2", "glow:#ff8a3a,6,.45", "sheen:.1"],
    "DementiveClothingCoveralls": ["map:#04101f,#2a5a9a,#a8c8f0", "pattern:splatter,c1=#0a0a0a,scale=20,amount=.28,op=.8,seed=5,shade=.5",
                                   "pattern:hazard,c1=#ffcc00,c2=#111111,scale=10,op=.85,zone=90/-0.12/0.2", "sheen:.25", "rim:#c8e0ff,2,.35"],
    "DementiveClothingSlicker": ["map:#2a1a00,#e8b800,#fff6b0", "sheen:.8", "pattern:speckle,c1=#a8d8ff,scale=3,amount=.7,op=.55,seed=4", "rim:#fff8c0,2,.5", "sparkle:#ffffff,3,10,2"],
    "DementiveClothingHuntingJacket": ["pattern:camo,c1=#7a6a38,c2=#3a2f18,c3=#9a8a58,scale=16,op=.9,seed=9,shade=.7", "rim:#ff7a1a,3,.7", "sheen:.15"],
    "DementiveClothingSheepskin": ["map:#2a1a08,#b88a50,#f8e8c8", "pattern:speckle,c1=#fff8e8,scale=3,amount=.75,op=.65,seed=3", "pattern:woodgrain,c1=#4a2a10,scale=14,op=.5,seed=2,zone=90/-0.15/0.3", "rim:#fff0d0,3,.55"],
    "DementiveClothingMittens": ["map:#2a0a0a,#b02a22,#f8d0c8", "pattern:plaid,c1=#f4f0ea,c2=#b02a22,scale=7,op=.6,seed=6", "pattern:speckle,c1=#ffffff,scale=3,amount=.6,op=.35,seed=2", "rim:#ffe0d8,2,.4"],
    "DementiveClothingWorkGloves": ["map:#1a0d03,#9a7040,#e8d0a0", "pattern:splatter,c1=#2a170a,scale=8,amount=.45,op=.85,seed=7,shade=.5", "pattern:speckle,c1=#5a3a18,scale=5,amount=.6,op=.5,seed=3", "sheen:.2"],
    "DementiveClothingFingerless": ["map:#050505,#2a2a2a,#8a8a8a", "sheen:.55", "rim:#c0c0c0,2,.5", "sparkle:#ffffff,3,9,7"],
    "DementiveClothingWelderGauntlets": ["map:#1a0a02,#8a4a1a,#e8b878", "pattern:splatter,c1=#1a0a02,scale=9,amount=.5,op=.8,seed=8,shade=.5", "rim:#ff9030,2,.7", "embers:#ffc040,10,1.4,6", "sheen:.3"],
    "DementiveClothingMountaineer": ["map:#050c18,#2a5a9a,#c8e8ff", "pattern:speckle,c1=#ffffff,scale=4,amount=.62,op=.6,seed=4", "rim:#e8f8ff,3,.7", "sparkle:#e0f4ff,4,10,2"],
    "DementiveClothingWoolSocks": ["map:#1a1208,#9a8a70,#f0e8d8", "pattern:speckle,c1=#4a3a28,scale=4,amount=.6,op=.45,seed=5", "pattern:woodgrain,c1=#5a3a18,scale=10,op=.75,seed=3,zone=90/-0.3/0.45", "rim:#f0e8d0,2,.3"],
    "DementiveClothingGumBoots": ["map:#04140a,#1f7a3a,#a8f0b8", "sheen:.8", "pattern:speckle,c1=#a8d8ff,scale=3,amount=.7,op=.5,seed=6", "rim:#d0ffd8,2,.5", "sparkle:#ffffff,3,10,9"],
    "DementiveClothingHiking": ["map:#140a04,#6a4020,#d8a870", "pattern:speckle,c1=#3a1e0a,scale=5,amount=.6,op=.5,seed=6", "pattern:cracks,c1=#2a1408,scale=16,op=.45,width=.05,seed=3", "rim:#e04a2a,2,.6", "sheen:.25"],
    "DementiveClothingDesert": ["map:#2a1a08,#c8a068,#fff0c8", "pattern:speckle,c1=#a07838,scale=5,amount=.6,op=.5,seed=8", "glow:#ffb050,7,.45", "sparkle:#fff0c0,2,12,5", "embers:#ffd890,8,1.2,4"],
    "DementiveClothingSnow": ["map:#0a1018,#8aa8c8,#ffffff", "pattern:speckle,c1=#ffffff,scale=4,amount=.6,op=.65,seed=7", "rim:#e8f8ff,3,.7", "sparkle:#e0f4ff,4,10,6", "embers:#ffffff,10,1.4,2"],
}

# Hidden worn markers (the buffs the vanilla buff patches below check) and the movement flags the noise perks use
MARKERS = ["buffDementiveClothingWelderCap", "buffDementiveClothingSlicker", "buffDementiveClothingGumBoots",
           "buffDementiveClothingGauntlets", "buffDementiveClothingMountaineer"]


def num(x):
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def scale_list(values, factor):
    return ",".join(num(float(v) * factor) for v in values.split(","))


def van_item(van, name):
    return re.search(r'\n<item name="%s">.*?\n</item>' % re.escape(name), van, re.S).group(0)


def resist(van, parent, stat):
    return re.search(r'name="%s" operation="base_add" value="([\d.,]+)"' % stat, van_item(van, parent)).group(1)


def kind_word(c):
    return {1: "thin", 2: "regular", 3: "heavy"}[c["tier"]]


def item_xml(c, van, eg):
    cold = resist(van, c["parent"], "HypothermalResist")
    heat = resist(van, c["parent"], "HyperthermalResist")
    if c.get("warm"):
        cold = scale_list(cold, c["warm"])
    if c.get("cool"):
        heat = scale_list(heat, c["cool"])
    tiers = "1,2,3,4,5,6"
    head = [
        f"\t\t<!-- {c['title']} ({kind_word(c)} clothing) -->",
        f'\t\t<item name="{c["name"]}">',
        f'\t\t\t<property name="Extends" value="{c["parent"]}"/>',
        f'\t\t\t<property name="CustomIcon" value="{c["name"]}"/>',
        f'\t\t\t<property name="DescriptionKey" value="{c["name"]}Desc"/>',
        f'\t\t\t<property name="EconomicValue" value="{ECONOMIC_VALUE[c["tier"]]}"/>',
        f'\t\t\t<property name="TraderStageTemplate" value="dementiveClothingTier{c["tier"]}"/>',
        "",
        "\t\t\t<effect_group>",
        '\t\t\t\t<passive_effect name="ModSlots" operation="base_set" value="0"/>',
        f'\t\t\t\t<passive_effect name="HypothermalResist" operation="base_add" value="{cold}" tier="{tiers}"/>',
        f'\t\t\t\t<passive_effect name="HyperthermalResist" operation="base_add" value="{heat}" tier="{tiers}"/>',
        "\t\t\t</effect_group>",
        "",
    ]
    return "\n".join(head) + eg(c["title"], c["signature"]) + "\n\t\t</item>\n"


def description(c):
    more = ""
    if c.get("warm"):
        more = f", with {round((c['warm'] - 1) * 100)}% more cold resistance"
    elif c.get("cool"):
        more = f", with {round((c['cool'] - 1) * 100)}% more heat resistance"
    return (f"{c['lore']}\\n\\n{c['ability']}\\n\\nInsulates like {TIER_WORD[c['tier']]} clothing (hot and cold resistance, "
            f"longer survival in storms){more}.")


def buffs_xml():
    out = ["\t<append xpath=\"/buffs\">",
           "\t\t<!-- Named clothing: worn markers. The perks that live in vanilla buffs (the burning, shock, wetness and fall",
           "\t\t     buffs, patched below) check these. Added on equip, removed on unequip -->"]
    for name in MARKERS:
        out.append(f'\t\t<buff name="{name}" hidden="true">\n\t\t\t<stack_type value="ignore"/>\n\t\t\t<duration value="0"/>\n\t\t</buff>')
    out.append("\n\t\t<!-- Birdwatcher's Boonie and Wool Socks: noise is worked out on the server, which can't tell a remote player is\n"
               "\t\t     walking, so the owner keeps a flag buff (synced) up to date. A flag's own marker runs while the piece is worn -->")
    for marker, flag, tags in (("buffDementiveClothingBoonie", "buffDementiveClothingWalking", "walking"),
                               ("buffDementiveClothingSocks", "buffDementiveClothingMoving", "walking,running")):
        out.append(f"""\t\t<buff name="{marker}" hidden="true">
\t\t\t<stack_type value="ignore"/>
\t\t\t<duration value="0"/>
\t\t\t<update_rate value=".25"/>
\t\t\t<effect_group>
\t\t\t\t<requirement name="IsLocalPlayer"/>
\t\t\t\t<triggered_effect trigger="onSelfBuffUpdate" action="AddBuff" buff="{flag}">
\t\t\t\t\t<requirement name="EntityHasMovementTag" tags="{tags}"/>
\t\t\t\t\t<requirement name="!HasBuff" buff="{flag}"/>
\t\t\t\t</triggered_effect>
\t\t\t\t<triggered_effect trigger="onSelfBuffUpdate" action="RemoveBuff" buff="{flag}">
\t\t\t\t\t<requirement name="!EntityHasMovementTag" tags="{tags}"/>
\t\t\t\t\t<requirement name="HasBuff" buff="{flag}"/>
\t\t\t\t</triggered_effect>
\t\t\t</effect_group>
\t\t</buff>
\t\t<buff name="{flag}" hidden="true">
\t\t\t<stack_type value="ignore"/>
\t\t\t<duration value="0"/>
\t\t</buff>""")
    out.append("\t</append>\n")
    return "\n".join(out)


# The burning buffs' damage over time: (buff, effect group number, passive number) of each HealthChangeOT that hurts a
# player. The game applies a buff's damage once for each of its HealthChangeOT passives, so a second always-on passive
# would double it. Instead the original gets a "no Welder's Cap" requirement and a 75% copy takes over while it is worn
BURNING = [("buffBurningElement", 3, 1), ("buffBurningEnvironment", 2, 1), ("buffBurningFlamingArrow", 4, 1),
           ("buffBurningMolotov", 4, 1), ("buffHazardBurningElement", 3, 1)]


def burn_patches(game):
    root = ET.parse(os.path.join(game, "Data", "Config", "buffs.xml")).getroot()
    buffs = {b.get("name"): b for b in root.iter("buff")}
    mark = "buffDementiveClothingWelderCap"
    out = ["\t<!-- Welder's Cap: burning damage over time ticks 25% weaker (see the note on BURNING in clothing.py) -->"]
    for name, k, j in BURNING:
        group = buffs[name].findall("effect_group")[k - 1]
        passive = [p for p in group.findall("passive_effect") if p.get("name") == "HealthChangeOT"][j - 1]
        if passive.get("operation") != "base_subtract":
            raise SystemExit(f"{name}: unexpected HealthChangeOT {passive.attrib}")
        path = f"/buffs/buff[@name='{name}']/effect_group[{k}]/passive_effect[@name='HealthChangeOT'][{j}]"
        attrs = f'name="HealthChangeOT" operation="base_subtract"'
        if passive.get("duration"):
            attrs += f' duration="{passive.get("duration")}"'
        attrs += f' value="{scale_list(passive.get("value"), .75)}"'
        reqs = "".join("\n\t\t\t" + ET.tostring(r, encoding="unicode").strip() for r in passive.findall("requirement"))
        out.append(f"\t<append xpath=\"{path}\">\n\t\t<requirement name=\"!HasBuff\" buff=\"{mark}\"/>\n\t</append>")
        out.append(f"\t<insertAfter xpath=\"{path}\">\n\t\t<passive_effect {attrs}>{reqs}\n\t\t\t<requirement name=\"HasBuff\" buff=\"{mark}\"/>\n\t\t</passive_effect>\n\t</insertAfter>")
    return "\n".join(out) + "\n"


def buff_patches(game):
    shock = """\t<!-- Welding Gauntlets: a shock's damage is its $buffShockedDamage a second (set when the buff starts, after which this
	     group runs), so 75% of it is 25% less. Fence posts, stun batons and traps all use buffShocked -->
	<append xpath="/buffs/buff[@name='buffShocked']">
		<effect_group>
			<requirement name="HasBuff" buff="buffDementiveClothingGauntlets"/>
			<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar="$buffShockedDamage" operation="multiply" value=".75"/>
		</effect_group>
	</append>
"""
    wet = """\t<!-- Fisherman's Slicker (50%) and Gum Boots (25%): buffElementWet adds _wetnessrate (rain, swimming) to $WetTempRate every
	     update; this takes that share of it back first, so the net gain is what's left. Nothing is taken away when
	     the rate is too low for the buff to count it -->
	<insertBefore xpath="/buffs/buff[@name='buffElementWet']/effect_group[1]">
		<effect_group>
			<requirement name="CVarCompare" cvar="_wetnessrate" operation="GT" value=".005"/>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetCut" operation="set" value="0"/>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetTmp" operation="set" value="@_wetnessrate"/>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetTmp" operation="multiply" value=".5"/>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetCut" operation="add" value="@.DementiveWetTmp">
				<requirement name="HasBuff" buff="buffDementiveClothingSlicker"/>
			</triggered_effect>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetTmp" operation="set" value="@_wetnessrate"/>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetTmp" operation="multiply" value=".25"/>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar=".DementiveWetCut" operation="add" value="@.DementiveWetTmp">
				<requirement name="HasBuff" buff="buffDementiveClothingGumBoots"/>
			</triggered_effect>
			<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar="$WetTempRate" operation="subtract" value="@.DementiveWetCut">
				<requirement name="CVarCompare" cvar=".DementiveWetCut" operation="GT" value="0"/>
			</triggered_effect>
		</effect_group>
	</insertBefore>
"""
    fall = """\t<!-- Mountaineer's Gloves: falls hurt 15% less. Fall damage is (impact speed - .189) x 300, so 85% of it is
	     .85 x impact speed + .15 x .189. A fall too soft to hurt stays too soft. After Marathon Runners' part above, in the
	     same group (where the vanilla boots cut the impact speed) -->
	<append xpath="/buffs/buff[@name='buffPlayerFallingDamage']/effect_group[triggered_effect[@value='@$rogueBootFallDMG']]">
		<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar=".impactSpeed" operation="multiply" value=".85">
			<requirement name="HasBuff" buff="buffDementiveClothingMountaineer"/>
		</triggered_effect>
		<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar=".impactSpeed" operation="add" value=".02835">
			<requirement name="HasBuff" buff="buffDementiveClothingMountaineer"/>
		</triggered_effect>
	</append>
"""
    return buffs_xml() + "\n" + burn_patches(game) + "\n" + shock + "\n" + wet + "\n" + fall


# Loot: the same containers and the same rare-drop style as the named armor, with half the armor's chance per container
# (there are 20 pieces rather than 64, and each is a weaker piece), and the loot stage thresholds of the vanilla clothing
LOOT_TEMPLATES = [("DementiveClothingRaresT1", "0.0053", "1 / 188"), ("DementiveClothingRaresT2", "0.0107", "1 / 94"),
                  ("DementiveClothingRaresT3", "0.0213", "1 / 47"), ("DementiveClothingRaresT4", "0.0427", "1 / 23"),
                  ("DementiveClothingRaresT5", "0.0533", "1 / 19")]
# (group, which template) for each container, as for the armor
LOOT_CONTAINERS = [("groupSmallSafeLoot", 2), ("groupReinforcedChestT3", 3), ("groupHardenedChestT4", 4),
                   ("groupHardenedChestT5", 5), ("groupZpackBoss", 3), ("groupZpackStrong", 2), ("groupZpackReg", 1),
                   ("groupHiddenStash", 2), ("groupBuriedTreasure", 3)]


def loot_xml():
    t = ["\t<append xpath=\"/lootcontainers/lootprobtemplates\">",
         "\t\t<!-- Chance per container opened that one named clothing piece drops: half the named armor's, since there are 20",
         "\t\t     pieces instead of 64 and each is a weaker piece. A group is count=\"all\" with 2.5 or more picks, so this stays",
         "\t\t     far below 1% of what any group picks -->"]
    for name, prob, frac in LOOT_TEMPLATES:
        t.append(f'\t\t<lootprobtemplate name="{name}">\n\t\t\t<loot level="1,999999" prob="{prob}"/>  <!-- {frac} -->\n\t\t</lootprobtemplate>')
    t.append("\n\t\t<!-- Which pieces a drop can be, by loot stage: tier 1 from the start, tier 2 from stage 30 and tier 3 from stage 88,\n"
             "\t\t     the same thresholds as the vanilla clothing (ProbT0, ProbT1Cap, ProbT2Cap) -->")
    for tier, stage in LOOT_STAGE.items():
        t.append(f'\t\t<lootprobtemplate name="DementiveClothingTier{tier}">\n\t\t\t<loot level="0,{stage - 1}" prob="0"/>\n'
                 f'\t\t\t<loot level="{stage},999999" prob="1"/>\n\t\t</lootprobtemplate>')
    t.append("\t</append>\n")
    items = []
    for c in CLOTHES:
        gate = f' loot_prob_template="DementiveClothingTier{c["tier"]}"' if c["tier"] > 1 else ""
        items.append(f'\t\t\t<item name="{c["name"]}"{gate}/>')
    t.append('\t<insertBefore xpath="/lootcontainers/lootgroup[@name=\'groupScrapCommon\']">\n'
             '\t\t<lootgroup name="groupDementiveClothingAll" count="1" loot_quality_template="qualBaseTemplate">\n'
             + "\n".join(items) + "\n\t\t</lootgroup>\n\t</insertBefore>\n")
    for group, n in LOOT_CONTAINERS:
        t.append(f'\t<append xpath="//lootgroup[@name=\'{group}\']">\n'
                 f'\t\t<item group="groupDementiveClothingAll" loot_prob_template="DementiveClothingRaresT{n}" force_prob="true"/>\n\t</append>')
    return "\n".join(t) + "\n"


# Per restock a trader has about a 5% chance to stock one (6 picks from groupArmorLight, 8 for Joel, who sells clothes
# and armor); the group's other entries have weight 1
TRADER_CLOTHING_PROB = 0.17


def traders_xml():
    stages = ["\t<append xpath=\"/traders/traderstage_templates\">",
              "\t\t<!-- Named clothing: the vanilla clothing tiers' trader stages (1, 25 and 55), but for quality 1-6 (the vanilla ones\n"
              "\t\t     only list quality 0, which no quality 1-6 trader item matches) -->"]
    for tier, stage in TRADER_STAGE.items():
        entries = "\n".join(f'\t\t\t<entry min="{stage}" max="999999" quality="{q}"/>' for q in range(0, 7))
        stages.append(f'\t\t<traderstage_template name="dementiveClothingTier{tier}">\n{entries}\n\t\t</traderstage_template>')
    stages.append("\t</append>\n")
    group = ('\t<insertBefore xpath="/traders/trader_item_groups/trader_item_group[@name=\'groupArmorLight\']">\n'
             '\t\t<trader_item_group name="groupDementiveTraderClothing" count="1">\n'
             + "\n".join(f'\t\t\t<item name="{c["name"]}" quality="1,6"/>' for c in CLOTHES)
             + "\n\t\t</trader_item_group>\n\t</insertBefore>\n")
    append = ('\t<append xpath="/traders/trader_item_groups/trader_item_group[@name=\'groupArmorLight\']">\n'
              f'\t\t<item group="groupDementiveTraderClothing" prob="{TRADER_CLOTHING_PROB:.4f}"/>\n\t</append>\n')
    return "\n".join(stages) + "\n" + group + "\n" + append
