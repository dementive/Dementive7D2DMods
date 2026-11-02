"""Writes FortificationsExpanded's Config (blocks, materials, recipes, localization) from the family tables below.

    python gen_fortifications.py [<repo>\\FortificationsExpanded]

Each family is one craftable helper item whose radial picks the piece, plus gates crafted on their own. Pieces move
between stages the vanilla way: UpgradeBlock (fill a sandbag or Hesco, band a palisade, re-tension chain-link,
re-weld a tank trap) and DowngradeBlock (what a piece breaks down to: stumps, a spilled mound, a sagging fence).
Filled stages swap damage-stage meshes (DMG0..DMG2 in the model) as they lose health.
"""
import os
import sys

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                                           "FortificationsExpanded")
BUNDLE = "#@modfolder:Resources/fortificationsexpanded.unity3d?"
PREFIX = "DementiveFort"
CLASS = "FortDEM, FortificationsExpanded"
GATE_CLASS = "FortGateDEM, FortificationsExpanded"

# Damage-stage thresholds as fractions of max health: DMG0 above 65%, DMG1 above 30%, DMG2 below
STAGE_SPLITS = (0.65, 0.3)
SHOOT_THROUGH = "movement,melee,rocket"  # stops zombies; bullets, arrows and sight pass

MATERIALS = """<configs>
	<append xpath="/materials">
		<!-- Sandbags: earth, so cops, boulders, pipe bombs and grenades do nothing and demolishers a tenth, and half
		     of every blast is soaked (explosionresistance 0.5; concrete is 0.1, steel 0.5). -->
		<material id="MsandbagDEM">
			<property name="damage_category" value="earth"/>
			<property name="surface_category" value="earth"/>
			<property name="Hardness" type="float" value="1"/>
			<property name="stepsound" value="sand"/>
			<property name="stability_glue" value="40"/>
			<property name="Mass" type="int" value="10"/>
			<property name="MaxDamage" value="2000"/>
			<property name="explosionresistance" value="0.5"/>
			<property name="Experience" value="2"/>
		</material>
		<!-- Hesco: packed earth like the sandbags (blast resistance 0.2, like concrete), and every single hit is
		     capped at 100 (MaxIncomingDamage; explosions aren't capped): ferals hit for about 24 and are unaffected,
		     charged (150) and infernal (250) zombies are cut down. -->
		<material id="MhescoDEM">
			<property name="damage_category" value="earth"/>
			<property name="surface_category" value="earth"/>
			<property name="Hardness" type="float" value="1"/>
			<property name="stepsound" value="gravel"/>
			<property name="stability_glue" value="60"/>
			<property name="Mass" type="int" value="10"/>
			<property name="MaxDamage" value="5000"/>
			<property name="explosionresistance" value="0.2"/>
			<property name="MaxIncomingDamage" value="100"/>
			<property name="Experience" value="2"/>
		</material>
		<!-- Tank traps: welded structural steel (blast resistance 0.4, like the vanilla hard metals) -->
		<material id="MtankTrapDEM">
			<property name="damage_category" value="metal"/>
			<property name="surface_category" value="metal"/>
			<property name="forge_category" value="iron"/>
			<property name="Hardness" type="float" value="1"/>
			<property name="stepsound" value="metal"/>
			<property name="stability_glue" value="200"/>
			<property name="Mass" type="int" value="20"/>
			<property name="MaxDamage" value="6000"/>
			<property name="explosionresistance" value="0.4"/>
			<property name="Experience" value="4"/>
		</material>
		<!-- Container walls: container steel (blast resistance 0.5) -->
		<material id="McontainerDEM">
			<property name="damage_category" value="metal"/>
			<property name="surface_category" value="metal"/>
			<property name="forge_category" value="iron"/>
			<property name="Hardness" type="float" value="1"/>
			<property name="stepsound" value="metal"/>
			<property name="stability_glue" value="300"/>
			<property name="Mass" type="int" value="20"/>
			<property name="MaxDamage" value="25000"/>
			<property name="explosionresistance" value="0.5"/>
			<property name="Experience" value="4"/>
		</material>
	</append>
</configs>
"""


def mesh_damage(health):
    # No trailing "-,1" stage: vanilla only uses it with Stage2Health and RepairItemsMeshDamage, and on its own it
    # would hide the model at 1 health
    return "DMG0,%d,DMG1,%d,DMG2,%d" % (health, round(health * STAGE_SPLITS[0]), round(health * STAGE_SPLITS[1]))


def piece(name, model, health, material, dim=(1, 1, 1), dmg=False, solid=False, collide=None, upgrade=None,
          downgrade=None, repair=None, harvest=None, tint=None, gate=False, sounds=("", ""), upgrade_sound=None,
          offset=None, support=False, door_sounds=None):
    """One block. upgrade = (to, item, count); downgrade = the block this one breaks down to (leftover damage carries
    down the chain, and zombies count the whole chain's health when deciding whether to break through). support: other
    blocks can be built on it (filled walls). door_sounds: a gate's (open, close, locked) sounds."""
    return dict(name=PREFIX + name, model=model, health=health, material=material, dim=dim, dmg=dmg, solid=solid,
                collide=collide, upgrade=upgrade, downgrade=downgrade, repair=repair or {}, harvest=harvest or {},
                tint=tint, gate=gate, sounds=sounds, upgrade_sound=upgrade_sound, offset=offset, support=support,
                door_sounds=door_sounds)


def block_xml(p, family):
    lines = ['\t\t<block name="%s">' % p["name"]]
    if p["gate"]:
        door = ['\t\t\t\t<property class="TEFeatureDoor" />']
        if p["door_sounds"]:
            opened, closed, locked = p["door_sounds"]
            door = ['\t\t\t\t<property class="TEFeatureDoor">',
                    '\t\t\t\t\t<property name="OpenSound" value="%s" />' % opened,
                    '\t\t\t\t\t<property name="CloseSound" value="%s" />' % closed]
            door += ['\t\t\t\t\t<property name="LockedSound" value="%s" />' % locked] if locked else []
            door += ["\t\t\t\t</property>"]
        lines += ['\t\t\t<property name="Class" value="%s" />' % GATE_CLASS,
                  '\t\t\t<property class="CompositeFeatures">'] + door + [
                  '\t\t\t\t<property class="TEFeatureLockable" />',
                  "\t\t\t</property>",
                  '\t\t\t<property name="CreativeMode" value="Player" />']
    else:
        lines += ['\t\t\t<property name="Class" value="%s" />' % CLASS,
                  '\t\t\t<property name="CreativeMode" value="Dev" />']
    lines += ['\t\t\t<property name="CustomIcon" value="%s" />' % family["icon"],
              '\t\t\t<property name="DescriptionKey" value="%s%sDesc" />' % (PREFIX, family["family"]),
              '\t\t\t<property name="Material" value="%s" />' % p["material"],
              '\t\t\t<property name="Shape" value="ModelEntity" />',
              '\t\t\t<property name="Model" value="%s%s" />' % (BUNDLE, p["model"])]
    if p["offset"]:
        lines.append('\t\t\t<property name="ModelOffset" value="%s" />' % p["offset"])
    if p["dim"] != (1, 1, 1):
        lines.append('\t\t\t<property name="MultiBlockDim" value="%d,%d,%d" />' % p["dim"])
        lines.append('\t\t\t<property name="DisplayType" value="blockMulti" />')
    if p["gate"]:
        lines += ['\t\t\t<property name="Place" value="Door" />',
                  '\t\t\t<property name="Tags" value="door" />',
                  '\t\t\t<property name="BlockTag" value="Door" />',
                  '\t\t\t<property name="PassThroughDamage" value="true" />']
    else:
        lines += ['\t\t\t<property name="Place" value="TowardsPlacerInverted" />',
                  '\t\t\t<property name="OnlySimpleRotations" value="true" />',
                  '\t\t\t<property name="IsTerrainDecoration" value="true" />']
    lines += ['\t\t\t<property name="StabilitySupport" value="%s" />' % ("true" if p["support"] else "false"),
              '\t\t\t<property name="WaterFlow" value="permitted" />',
              '\t\t\t<property name="ImposterDontBlock" value="true" />',
              '\t\t\t<property name="MaxDamage" value="%d" />' % p["health"]]
    if p["solid"]:
        lines.append('\t\t\t<property name="Path" value="solid" />')
    if p["collide"]:
        lines.append('\t\t\t<property name="Collide" value="%s" />' % p["collide"])
    if p["tint"]:
        lines.append('\t\t\t<property name="TintColor" value="%s" />' % p["tint"])
    if p["gate"]:
        # Gates have one stage; the game looks for it under the animated Door object
        lines.append('\t\t\t<property name="MeshDamage" value="Door/DMG0,%d" />' % p["health"])
    elif p["dmg"]:
        lines.append('\t\t\t<property name="MeshDamage" value="%s" />' % mesh_damage(p["health"]))
    if p["repair"]:
        lines.append('\t\t\t<property class="RepairItems">')
        lines += ['\t\t\t\t<property name="%s" value="%d" />' % kv for kv in p["repair"].items()]
        lines.append("\t\t\t</property>")
    if p["upgrade"]:
        to, item, count = p["upgrade"]
        lines += ['\t\t\t<property class="UpgradeBlock">',
                  '\t\t\t\t<property name="ToBlock" value="%s" />' % (PREFIX + to),
                  '\t\t\t\t<property name="Item" value="%s" />' % item,
                  '\t\t\t\t<property name="ItemCount" value="%d" />' % count,
                  '\t\t\t\t<property name="UpgradeHitCount" value="4" />',
                  "\t\t\t</property>"]
        if p["upgrade_sound"]:
            lines.append('\t\t\t<property name="UpgradeSound" value="%s" />' % p["upgrade_sound"])
    if p["downgrade"]:
        lines += ['\t\t\t<property name="DowngradeBlock" value="%s" />' % (PREFIX + p["downgrade"]),
                  '\t\t\t<property name="PassThroughDamage" value="true" />' if not p["gate"] else ""]
    for item, count in p["harvest"].items():
        lines.append('\t\t\t<drop event="Harvest" name="%s" count="%d" tag="allHarvest,perkJunkMiner" />' % (item, count))
    lines.append('\t\t\t<drop event="Destroy" count="0" />')
    if p["sounds"][0]:
        lines += ['\t\t\t<property name="SoundPickup" value="%s" />' % p["sounds"][0],
                  '\t\t\t<property name="SoundPlace" value="%s" />' % p["sounds"][1]]
    lines += ['\t\t\t<property name="Group" value="Building,advBuilding" />',
              '\t\t\t<property name="FilterTags" value="MC_playerBlocks,SC_playerHelpers" />',
              "\t\t</block>"]
    return [l for l in lines if l]


# ------------------------------------------------------------------ Sandbag Wall: blast wall

def sandbag_family():
    sounds = ("sandbags_grab", "sandbags_place")
    pieces = []
    # piece, model prefix, multiblock height, health per stage (empty, half, full), sand per fill
    for name, model, height, healths, fill in [("Wall", "SandbagWall", 2, (200, 1000, 2000), 10),
                                               ("Low", "SandbagLow", 1, (100, 500, 1000), 5),
                                               ("Corner", "SandbagCorner", 2, (200, 1000, 2000), 10),
                                               ("End", "SandbagEnd", 2, (200, 1000, 2000), 10)]:
        for i, stage in enumerate(("Empty", "Half", "Full")):
            nxt = ("Sandbag%s%s" % (name, ("Half", "Full")[i]), "resourceCrushedSand", fill) if i < 2 else None
            sand = (0, fill // 2, fill)[i]
            repair = {"resourceCrushedSand": sand, "resourceCloth": 4} if sand else {"resourceCloth": 5}
            harvest = {"resourceCloth": 4}
            if i:
                harvest["resourceCrushedSand"] = fill * i // 2
            pieces.append(piece("Sandbag%s%s" % (name, stage), model + stage, healths[i], "MsandbagDEM",
                                dim=(1, height, 1), dmg=i > 0, solid=i == 2, upgrade=nxt, repair=repair,
                                harvest=harvest, sounds=sounds, upgrade_sound="sandbags_place", support=i == 2))
    return dict(family="Sandbag", icon=PREFIX + "SandbagWall", pieces=pieces,
                helper=["SandbagWallEmpty", "SandbagLowEmpty", "SandbagCornerEmpty", "SandbagEndEmpty"],
                recipe=dict(items=[("resourceCloth", 10)], area=None), gates=[],
                names={"": "Sandbag Wall",
                       "SandbagWall": ("Sandbag Wall (empty bags)", "Sandbag Wall (half filled)", "Sandbag Wall"),
                       "SandbagLow": ("Low Sandbag Wall (empty bags)", "Low Sandbag Wall (half filled)", "Low Sandbag Wall"),
                       "SandbagCorner": ("Sandbag Corner (empty bags)", "Sandbag Corner (half filled)", "Sandbag Corner"),
                       "SandbagEnd": ("Sandbag Wall End (empty bags)", "Sandbag Wall End (half filled)", "Sandbag Wall End")},
                desc="A 2 m wall of sandbags that zombies can't climb, built to take blasts. Cops, boulders and "
                     "grenades barely scratch it, and a full wall survives about four point-blank demolisher blasts; "
                     "rockets and dynamite still wreck it.\n\nPlace the empty bags, then fill them twice with a hammer "
                     "or nail gun and crushed sand (10 each fill, 5 for the low wall). Pick the piece from the radial "
                     "menu: wall, low wall (1 m cover you can shoot over), corner or wall end.\n\nRepair with Crushed "
                     "Sand and Cloth.")


# ------------------------------------------------------------------ Log Palisade: tall wall on day one

def palisade_family():
    wood = "Mwood_regular"
    pieces = [
        piece("PalisadeSection", "PalisadeSection", 1500, wood, dim=(1, 3, 1), dmg=True, solid=True,
              upgrade=("PalisadeSectionBanded", "resourceForgedIron", 4), downgrade="PalisadeStumps",
              repair={"resourceWood": 10}, harvest={"resourceWood": 12}, upgrade_sound="place_block_metal",
              support=True),
        piece("PalisadeSectionBanded", "PalisadeSectionBanded", 3000, wood, dim=(1, 3, 1), dmg=True, solid=True,
              downgrade="PalisadeStumps", repair={"resourceWood": 10, "resourceForgedIron": 2},
              harvest={"resourceWood": 12, "resourceScrapIron": 6}, support=True),
        piece("PalisadeCorner", "PalisadeCorner", 1500, wood, dim=(1, 3, 1), dmg=True, solid=True,
              upgrade=("PalisadeCornerBanded", "resourceForgedIron", 4), downgrade="PalisadeCornerStumps",
              repair={"resourceWood": 10}, harvest={"resourceWood": 12}, upgrade_sound="place_block_metal",
              support=True),
        piece("PalisadeCornerBanded", "PalisadeCornerBanded", 3000, wood, dim=(1, 3, 1), dmg=True, solid=True,
              downgrade="PalisadeCornerStumps", repair={"resourceWood": 10, "resourceForgedIron": 2},
              harvest={"resourceWood": 12, "resourceScrapIron": 6}, support=True),
        # What's left: 1 m stumps zombies can climb; hammer it back into a section (or corner) with wood
        piece("PalisadeStumps", "PalisadeStumps", 300, wood, dim=(1, 3, 1),
              upgrade=("PalisadeSection", "resourceWood", 15), repair={"resourceWood": 5},
              harvest={"resourceWood": 4}, upgrade_sound="place_block_wood"),
        piece("PalisadeCornerStumps", "PalisadeStumps", 300, wood, dim=(1, 3, 1),
              upgrade=("PalisadeCorner", "resourceWood", 15), repair={"resourceWood": 5},
              harvest={"resourceWood": 4}, upgrade_sound="place_block_wood"),
    ]
    gate = piece("PalisadeGate", "PalisadeGate", 2500, wood, dim=(3, 3, 1), gate=True,
                 repair={"resourceWood": 20, "resourceNail": 4}, harvest={"resourceWood": 20},
                 door_sounds=("gate_wood_large_open", "gate_wood_large_close", "gate_wood_large_locked"))
    return dict(family="Palisade", icon=PREFIX + "Palisade", pieces=pieces, helper=["PalisadeSection", "PalisadeCorner"],
                recipe=dict(items=[("resourceWood", 25), ("resourceYuccaFibers", 4)], area=None),
                gates=[(gate, dict(items=[("resourceWood", 60), ("resourceYuccaFibers", 10), ("resourceNail", 20)],
                                   area=None), "Log Palisade Gate",
                        "A double gate of sharpened logs on two heavy posts, 3 wide and 3 m tall. Open and close it "
                        "like a door; it can be locked.\n\nRepair with Wood and Nails.")],
                names={"": "Log Palisade", "PalisadeSection": "Log Palisade", "PalisadeSectionBanded": "Iron-Banded Palisade",
                       "PalisadeCorner": "Log Palisade Corner", "PalisadeCornerBanded": "Iron-Banded Palisade Corner",
                       "PalisadeStumps": "Palisade Stumps", "PalisadeCornerStumps": "Palisade Corner Stumps"},
                desc="A 3 m wall of sharpened logs: cheap, quick, and too tall for zombies to climb. When a section "
                     "breaks it leaves 1 m stumps they can climb over; hammer the stumps back into a wall with 15 "
                     "wood.\n\nBand a section with 4 forged iron (hammer or nail gun) to double its health. Pick a "
                     "section or a corner from the radial menu.\n\nRepair with Wood (and Forged Iron once banded).")


# ------------------------------------------------------------------ Chain-Link: see-through screen and gates

def chainlink_family():
    pieces = []
    stages = ("Taut", "Sagging", "Torn")
    for shape, model, height, scale in [("Panel", "ChainLinkPanel", 2, 1.0), ("Tall", "ChainLinkTall", 3, 1.5),
                                        ("Corner", "ChainLinkCorner", 2, 1.0)]:
        for weight, base in [("Light", (400, 300, 200)), ("Heavy", (800, 600, 400))]:
            for i, stage in enumerate(stages):
                name = "ChainLink%s%s%s" % (shape, weight, stage)
                if i == 0:
                    up = ("ChainLink%sHeavyTaut" % shape, "resourceForgedIron", 2) if weight == "Light" else None
                else:
                    up = ("ChainLink%s%s%s" % (shape, weight, stages[i - 1]), "resourceScrapIron", 3)
                down = "ChainLink%s%s%s" % (shape, weight, stages[i + 1]) if i < 2 else None
                repair = {"resourceScrapIron": 3} if weight == "Light" else {"resourceScrapIron": 3, "resourceForgedIron": 1}
                pieces.append(piece(name, model + weight + stage, round(base[i] * scale), "Mmetal",
                                    dim=(1, height, 1), solid=True, collide=SHOOT_THROUGH, upgrade=up, downgrade=down,
                                    repair=repair, harvest={"resourceScrapIron": 3}, upgrade_sound="place_block_metal"))
    gate = piece("ChainLinkGate", "ChainLinkGate", 1500, "Mmetal", dim=(3, 2, 1), gate=True, collide=SHOOT_THROUGH,
                 repair={"resourceScrapIron": 10}, harvest={"resourceScrapIron": 8},
                 door_sounds=("gate_chainlink_open", "gate_chainlink_close", "gate_chainlink_locked"))
    names = {"": "Chain-Link Fence"}
    for shape, label in [("Panel", "Chain-Link Fence"), ("Tall", "Tall Chain-Link Fence"), ("Corner", "Chain-Link Corner")]:
        for weight in ("Light", "Heavy"):
            for stage, word in zip(stages, ("", " (sagging)", " (torn)")):
                names["ChainLink%s%s%s" % (shape, weight, stage)] = ("Heavy " if weight == "Heavy" else "") + label + word
    return dict(family="ChainLink", icon=PREFIX + "ChainLink", pieces=pieces,
                helper=["ChainLinkPanelLightTaut", "ChainLinkTallLightTaut", "ChainLinkCornerLightTaut"],
                recipe=dict(items=[("resourceScrapIron", 6), ("resourceDuctTape", 1)], area="workbench"),
                gates=[(gate, dict(items=[("resourceScrapIron", 20), ("resourceDuctTape", 2), ("resourceMechanicalParts", 2)],
                                   area="workbench"), "Chain-Link Rolling Gate",
                        "A 3 wide rolling gate that slides aside on its wheels. Bullets and arrows go through it, and it "
                        "can be locked.\n\nRepair with Scrap Iron.")],
                names=names,
                desc="A chain-link screen that stops zombies but not your bullets or arrows (they can see you "
                     "through it too). It sags, then tears, as it takes damage, each stage weaker; hammer a damaged "
                     "fence back up a stage with 3 scrap iron. Upgrade it to heavy chain-link with 2 forged iron "
                     "for twice the health. Pick a 2 m panel, a 3 m panel or a corner from the radial menu.\n\n"
                     "Repair with Scrap Iron (and Forged Iron once heavy).")


# ------------------------------------------------------------------ Hesco: cheap bulk wall

def hesco_family():
    pieces = []
    for shape, model, dim, healths, fill in [("", "Hesco", (1, 2, 1), (300, 1500, 3000, 5000), 10),
                                             ("Double", "HescoDouble", (2, 2, 1), (600, 3000, 6000, 10000), 20)]:
        stages = ("Empty", "Third", "TwoThirds", "Full")
        for i, stage in enumerate(stages):
            name = "Hesco%s%s" % (shape, stage)
            up = ("Hesco%s%s" % (shape, stages[i + 1]), "resourceClayLump", fill) if i < 3 else None
            pieces.append(piece(name, model + stage, healths[i], "MhescoDEM", dim=dim, dmg=i > 0, solid=i == 3,
                                upgrade=up, downgrade="Hesco%sMound" % shape if i > 0 else None,
                                repair={"resourceClayLump": fill // 2, "resourceCloth": 2} if i else {"resourceCloth": 3},
                                harvest={"resourceClayLump": fill * i // 2} if i else {"resourceScrapIron": 4},
                                upgrade_sound="sandbags_place", support=i > 0))
        # A breach spills into a 1 m mound zombies can climb; shovel it back in with clay
        pieces.append(piece("Hesco%sMound" % shape, model + "Mound", healths[1] // 3, "MhescoDEM", dim=dim,
                            upgrade=("Hesco%sThird" % shape, "resourceClayLump", fill),
                            repair={"resourceClayLump": fill // 2}, harvest={"resourceClayLump": fill // 2},
                            upgrade_sound="sandbags_place"))
    names = {"": "Hesco Barrier"}
    for shape, label in [("", "Hesco Barrier"), ("Double", "Double Hesco Barrier")]:
        for stage, word in [("Empty", " (empty)"), ("Third", " (a third full)"), ("TwoThirds", " (two thirds full)"),
                            ("Full", ""), ("Mound", " (breached)")]:
            names["Hesco%s%s" % (shape, stage)] = label + word
    return dict(family="Hesco", icon=PREFIX + "Hesco", pieces=pieces, helper=["HescoEmpty", "HescoDoubleEmpty"],
                recipe=dict(items=[("resourceForgedIron", 4), ("resourceCloth", 6)], area="workbench"), gates=[],
                names=names,
                desc="A wire-mesh cage lined with fabric that you fill with clay you've dug anyway: the cheapest "
                     "strong wall, no cement mixer needed. Fill it three times with a hammer or nail gun and clay "
                     "(10 each fill, 20 for the double). Like sandbags it ignores small explosives, and every single "
                     "hit on it is capped at 100, so charged and infernal zombies struggle with it. A breach spills "
                     "into a 1 m mound zombies can climb; refill it with clay.\n\nRepair with Clay and Cloth.")


# ------------------------------------------------------------------ Tank Traps: funnels

def tank_traps_family():
    m = "MtankTrapDEM"
    pieces = [
        piece("TankTrapHedgehog", "TankTrapHedgehog", 6000, m, dim=(2, 2, 2), dmg=True, solid=True,
              collide=SHOOT_THROUGH, downgrade="TankTrapHedgehogBent", repair={"resourceForgedIron": 6},
              harvest={"resourceScrapIron": 20}),
        piece("TankTrapHedgehogBent", "TankTrapHedgehogBent", 2000, m, dim=(2, 2, 2), solid=True,
              collide=SHOOT_THROUGH, upgrade=("TankTrapHedgehog", "resourceForgedIron", 6),
              repair={"resourceForgedIron": 3}, harvest={"resourceScrapIron": 15}, upgrade_sound="place_block_metal"),
        piece("TankTrapLine", "TankTrapLine", 5000, m, dim=(3, 2, 1), dmg=True, solid=True, collide=SHOOT_THROUGH,
              downgrade="TankTrapLineBent", repair={"resourceForgedIron": 6}, harvest={"resourceScrapIron": 20}),
        piece("TankTrapLineBent", "TankTrapLineBent", 1500, m, dim=(3, 2, 1), solid=True, collide=SHOOT_THROUGH,
              upgrade=("TankTrapLine", "resourceForgedIron", 6), repair={"resourceForgedIron": 3},
              harvest={"resourceScrapIron": 15}, upgrade_sound="place_block_metal"),
    ]
    return dict(family="TankTraps", icon=PREFIX + "TankTraps", pieces=pieces,
                helper=["TankTrapHedgehog", "TankTrapLine"],
                recipe=dict(items=[("resourceForgedIron", 12)], area="workbench"), gates=[],
                names={"": "Tank Traps", "TankTrapHedgehog": "Tank Trap", "TankTrapHedgehogBent": "Tank Trap (bent)",
                       "TankTrapLine": "Tank Trap Line", "TankTrapLineBent": "Tank Trap Line (bent)"},
                desc="Welded steel beams that shape the horde's path. Zombies can't climb them and would rather walk a "
                     "long way around than break through, while your bullets, arrows and sight pass between the "
                     "beams. Lay a maze across open ground fast. A wrecked trap bends but stays a barrier; re-weld it "
                     "with 6 forged iron. Pick a 2 by 2 hedgehog or a 3 wide line from the radial menu.\n\nRepair "
                     "with Forged Iron.")


# ------------------------------------------------------------------ Container Wall: a late wall in one placement

CONTAINER_TINTS = [("Red", "8A2E22"), ("Blue", "2A4C78"), ("Green", "3E5A34"), ("Rust", "7A4A2A")]


def container_family():
    m = "McontainerDEM"
    pieces = []
    for color, tint in CONTAINER_TINTS:
        pieces.append(piece("ContainerWall" + color, "ContainerWall", 25000, m, dim=(3, 3, 1), dmg=True, solid=True,
                            tint=tint, repair={"resourceForgedSteel": 10, "resourceForgedIron": 4},
                            harvest={"resourceScrapIron": 60}, support=True))
        pieces.append(piece("ContainerCorner" + color, "ContainerCorner", 8000, m, dim=(1, 3, 1), dmg=True, solid=True,
                            tint=tint, repair={"resourceForgedSteel": 4, "resourceForgedIron": 2},
                            harvest={"resourceScrapIron": 20}, support=True))
    gate = piece("ContainerGate", "ContainerGate", 15000, m, dim=(3, 3, 1), gate=True, tint=CONTAINER_TINTS[0][1],
                 repair={"resourceForgedSteel": 8, "resourceForgedIron": 4}, harvest={"resourceScrapIron": 40},
                 door_sounds=("door_metal_open", "door_metal_close", None))
    names = {"": "Container Wall"}
    for color, _ in CONTAINER_TINTS:
        names["ContainerWall" + color] = "Container Wall (%s)" % color.lower()
        names["ContainerCorner" + color] = "Container Corner (%s)" % color.lower()
    return dict(family="Container", icon=PREFIX + "Container", pieces=pieces,
                helper=["ContainerWall" + c for c, _ in CONTAINER_TINTS] + ["ContainerCorner" + c for c, _ in CONTAINER_TINTS],
                recipe=dict(items=[("resourceForgedSteel", 30), ("resourceForgedIron", 10)], area="workbench"),
                gates=[(gate, dict(items=[("resourceForgedSteel", 20), ("resourceForgedIron", 10),
                                          ("resourceMechanicalParts", 4)], area="workbench"), "Container Gate",
                        "Shipping-container cargo doors in a steel frame, 3 wide and 3 m tall. Open and close it like "
                        "a door; it can be locked.\n\nRepair with Forged Steel and Forged Iron.")],
                names=names,
                desc="A 3 by 3 wall cut from shipping containers, placed whole with no upgrade hits, and tough "
                     "against blasts. The catch: it has one pool of health, so when it breaks the whole 3 by 3 goes "
                     "at once, and a blast counts once for every cell it covers. Pick a wall or a corner and its "
                     "colour from the radial menu.\n\nRepair with Forged Steel and Forged Iron.")


FAMILIES = [sandbag_family(), palisade_family(), chainlink_family(), hesco_family(), tank_traps_family(),
            container_family()]


def blocks_xml():
    out = ["<configs>", '\t<append xpath="/blocks">',
           "\t\t<!-- Generated by Scripts/FortificationsExpanded/gen_fortifications.py. Pieces move between stages with",
           "\t\t     UpgradeBlock and DowngradeBlock; filled stages swap their DMG0-DMG2 meshes as they lose health and",
           "\t\t     puff from FX when a stage breaks. Gates are vanilla doors (CompositeTileEntity) with their own",
           "\t\t     animated models. -->"]
    for f in FAMILIES:
        out.append("\t\t<!-- %s -->" % f["family"])
        for p in f["pieces"]:
            out += block_xml(p, f)
        for gate, _, _, _ in f["gates"]:
            out += block_xml(gate, dict(f, family=gate["name"][len(PREFIX):]))
        first = PREFIX + f["helper"][0]
        out += ['\t\t<block name="%s%s">' % (PREFIX, f["family"]),
                '\t\t\t<property name="Extends" value="%s" />' % first,
                '\t\t\t<property name="CreativeMode" value="Player" />',
                '\t\t\t<property name="ItemTypeIcon" value="all_blocks" />',
                '\t\t\t<property name="SelectAlternates" value="true" />',
                '\t\t\t<property name="PlaceAltBlockValue" value="%s" />' % ",".join(PREFIX + h for h in f["helper"]),
                '\t\t\t<property name="EconomicValue" value="40" />',
                '\t\t\t<property name="SortOrder1" value="U201" />',
                "\t\t</block>"]
    out += ["\t</append>", "</configs>"]
    return "\n".join(out) + "\n"


def recipe_lines(name, recipe):
    area = ' craft_area="%s"' % recipe["area"] if recipe["area"] else ""
    tags = "workbenchCrafting" if recipe["area"] else "packMuleCrafting"
    lines = ['\t\t<recipe name="%s" count="1"%s tags="%s">' % (name, area, tags)]
    lines += ['\t\t\t<ingredient name="%s" count="%d"/>' % kv for kv in recipe["items"]]
    return lines + ["\t\t</recipe>"]


def recipes_xml():
    out = ["<configs>", '\t<append xpath="/recipes">']
    for f in FAMILIES:
        out += recipe_lines(PREFIX + f["family"], f["recipe"])
        for gate, recipe, _, _ in f["gates"]:
            out += recipe_lines(gate["name"], recipe)
    out += ["\t</append>", "</configs>"]
    return "\n".join(out) + "\n"


def csv_field(text):
    text = text.replace("\n", "\\n")
    return '"%s"' % text.replace('"', '""') if any(c in text for c in ',"') else text


def localization():
    rows = ["Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,"
            "french,italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese"]

    def row(key, text):
        rows.append("%s,blocks,Block,,,,%s%s" % (key, csv_field(text), "," * 13))

    for f in FAMILIES:
        row(PREFIX + f["family"], f["names"][""])
        row(PREFIX + f["family"] + "Desc", f["desc"])
        for p in f["pieces"]:
            short = p["name"][len(PREFIX):]
            name = f["names"].get(short)
            if name is None:
                # Staged families keep one tuple per model prefix
                for prefix, stage_names in f["names"].items():
                    if isinstance(stage_names, tuple) and short.startswith(prefix):
                        name = stage_names[("Empty", "Half", "Full").index(short[len(prefix):])]
            row(p["name"], name)
        for gate, _, title, desc in f["gates"]:
            row(gate["name"], title)
            row(gate["name"] + "Desc", desc)
    return "\n".join(rows) + "\n"


def write(rel, text):
    path = os.path.join(MOD, "Config", rel)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", path)


def staged_models():
    """Every model a block's MeshDamage names DMG0-DMG2 in, for FortBuilder to check: a missing stage would throw in
    game each time the piece spawns or changes stage."""
    return "\n".join(sorted({p["model"] for f in FAMILIES for p in f["pieces"] if p["dmg"]})) + "\n"


write("materials.xml", MATERIALS)
write("blocks.xml", blocks_xml())
write("recipes.xml", recipes_xml())
write("Localization.csv", localization())
with open(os.path.join(MOD, "unity", "staged-models.txt"), "w", encoding="utf-8", newline="\n") as f:
    f.write(staged_models())
print("wrote staged-models.txt")
