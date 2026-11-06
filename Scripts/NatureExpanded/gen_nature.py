"""Writes NatureExpanded's Config (blocks, biome drifts, localization) from the plant and biome tables below.

    python gen_nature.py [<repo>\\NatureExpanded] [<game>]

Every plant is a model block (Shape ModelEntity, class PlantDEM: the DLL tags its collider and moves it to the game's
plant shader), placed by world generation like vanilla's wild cotton and harvested like grass. A plant taller than one
block takes more (MultiBlockDim), read from unity/Build/plant-sizes.txt, which NatureBuilder writes; build the bundle
first, then run this.

Biomes. The game decorates a block from its biome or the first sub-biome whose noise matches there, trying each
decoration in order and placing the first that rolls under its prob (WorldDecoratorBlocksFromBiome), so plants go
before the grass. Per biome:
- Drifts: small patches of one species among a few companions, over the biome's own trees, rocks and grass. Each is
  two sub-biomes on the same noise, appended after vanilla's (ore veins and tree groves keep their ground): a dense
  core a few blocks across and a sparse fringe round it, so a patch thins out into the meadow instead of ending at a
  hard edge. Each species has its own noise, so a meadow has a clump of lupine here and a few poppies there.
- Mix: plants added to one of vanilla's sub-biomes (the pine forest's flower clusters, which were all goldenrod,
  cotton and chrysanthemum; those three are thinned to a quarter there).
- Scatter: single plants dotted over the biome itself.
Copies of vanilla's decoration lists leave out the wild crops (cotton, goldenrod, chrysanthemum, snowberries,
blueberries): drifts are for the new plants. Only chunks generated after install get any of it.

The water's-edge plants (cattail, reeds, blue flag iris, marsh marigold) are in no biome table: the DLL (ShoreDEM)
puts them along real shores, which the biome tables can't see.

Grasses. Besides the plant models, the mod has grasses drawn exactly like vanilla's tall grass, from tiles the DLL
(GrassSheetDEM) adds to the game's grass texture sheet; blender/grass/grasses.txt lists them with their texture ids.
Where a biome has them (its "grass" entry), vanilla's grass becomes one grass among several:
- cover: vanilla's ground cover on open ground, thinned (the pine forest's tall grass, down from .4).
- main: the new grasses mixed through open ground, and so through every drift, which copies that ground.
- mix: grasses mixed into vanilla's sub-biomes (flower clusters, tree groves).
- patches: sub-biomes, after the drifts, where one grass takes over the ground (with a companion), core and fringe
  like a drift but bigger, so a hillside has a swathe of hairgrass here and orchard grass there. They come in pairs
  sharing one noise, one in its low tail and one in its high tail (the noise is symmetric about .5, so both get the
  same ground), which the game samples once for both. density scales a biome's patches (sparser in desert and snow).

Trees (blender/trees/*.py, built by src/build-trees.bat, which writes unity/Build/tree-sizes.txt): each variant is a
block like vanilla's trees (treeMaster: a distant decoration that chops and falls), mixed into a biome's own tree
sub-biomes and dotted over its open ground. Only variants the tree build has measured get blocks.
"""
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "NatureExpanded")
GAME = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "..", "..")
BUNDLE = "#@modfolder:Resources/natureexpanded.unity3d?"
TREE_BUNDLE = "#@modfolder:Resources/natureexpanded-trees.unity3d?NatureTree"
PREFIX = "DementiveNature"
CLASS = "PlantDEM, NatureExpanded"

# A drift's core and fringe: the top of its noise band (sub-biome noise runs 0-1 and rarely dips this low; measured
# with the game's PerlinNoise, below .1 is about 0.6% of the ground and below .21 about 4%), how much of the ground
# its species covers there, and each companion
DRIFT_BANDS = [(0.1, 0.1, 0.025), (0.21, 0.03, 0.012)]
# Drift noise frequency: at .06 a core is about 5 blocks across and its fringe about 7 (at .03 they were twice that)
DRIFT_FREQ = 0.06
# Grass patches, in the order the game tries them: the low-tail grass's core and fringe, then the high-tail grass's
# fringe and core (noise band, its share of the ground), and the frequency (at .015 a core is about 25 blocks across)
PATCH_BANDS = [((0.0, 0.21), 0.3), ((0.21, 0.3), 0.12), ((0.7, 0.79), 0.12), ((0.79, 1.5), 0.3)]
PATCH_FREQ = 0.015

# name: (display name, kind). Kinds set the material and what harvesting gives.
PLANTS = {
    # Pine forest meadows
    "Poppy": ("Poppy", "flower"),
    "Lupine": ("Lupine", "flower"),
    "Cornflower": ("Cornflower", "flower"),
    "OxeyeDaisy": ("Oxeye Daisy", "flower"),
    "Paintbrush": ("Indian Paintbrush", "flower"),
    "BlackEyedSusan": ("Black-Eyed Susan", "flower"),
    "Coneflower": ("Coneflower", "flower"),
    "QueenAnnesLace": ("Queen Anne's Lace", "flower"),
    "RedClover": ("Red Clover", "flower"),
    "Bergamot": ("Wild Bergamot", "flower"),
    "Chicory": ("Chicory", "flower"),
    # Forest floor and edges
    "Fern": ("Fern", "flower"),
    "FlyAgaric": ("Fly Agaric", "toadstool"),
    "Bolete": ("Porcini", "mushroom"),
    "Trillium": ("Trillium", "flower"),
    "WildStrawberry": ("Wild Strawberry", "flower"),
    "Foxglove": ("Foxglove", "flower"),
    "WildRose": ("Wild Rose", "bush"),
    "Elderberry": ("Elderberry", "bush"),
    "Sumac": ("Sumac", "bush"),
    "MossyLog": ("Mossy Log", "log"),
    # Water's edge (placed along shores by the DLL, ShoreDEM)
    "Cattail": ("Cattail", "flower"),
    "Reeds": ("Reeds", "flower"),
    "BlueFlagIris": ("Blue Flag Iris", "flower"),
    "MarshMarigold": ("Marsh Marigold", "flower"),
    # Burnt forest
    "Fireweed": ("Fireweed", "flower"),
    "CharredShrub": ("Charred Shrub", "bush"),
    "Morels": ("Morels", "mushroom"),
    # Desert
    "PricklyPear": ("Prickly Pear", "cactus"),
    "BarrelCactus": ("Barrel Cactus", "cactus"),
    "Ocotillo": ("Ocotillo", "bush"),
    "AgaveBloom": ("Flowering Agave", "cactus"),
    "DesertMarigold": ("Desert Marigold", "flower"),
    "Globemallow": ("Globemallow", "flower"),
    "Sagebrush": ("Sagebrush", "bush"),
    "EveningPrimrose": ("Evening Primrose", "flower"),
    # Snow
    "AlpineAster": ("Alpine Aster", "flower"),
    "Heather": ("Heather", "flower"),
    "Winterberry": ("Winterberry", "bush"),
    "Snowdrop": ("Snowdrop", "flower"),
    "FrostedJuniper": ("Juniper", "bush"),
    # Wasteland
    "Thistle": ("Thistle", "flower"),
    "SilverSage": ("Silver Sage", "flower"),
    "WildMustard": ("Wild Mustard", "flower"),
    "CurlyDock": ("Curly Dock", "flower"),
    "DeadBrush": ("Dead Brush", "bush"),
    # Ground cover (blender/groundcover/SPEC_*.md): walk-through patches lying on the ground, in their own bundle
    # (GROUND_BUNDLE). Kinds: litter (nothing to take), stones, sticks, fibers, scrapbits (pick up for a little
    # stone, wood, plant fibers or scrap iron)
    "PineNeedleMat": ("Pine Needle Mat", "litter"),
    "BirchLeafLitter": ("Birch Leaf Litter", "litter"),
    "MapleLeafLitter": ("Maple Leaf Litter", "litter"),
    "OakLeafLitter": ("Oak Leaf Litter", "litter"),
    "MossPatch": ("Moss Patch", "litter"),
    "TwigPile": ("Twig Pile", "sticks"),
    "PineconeCluster": ("Pinecone Cluster", "fibers"),
    "AcornScatter": ("Acorn Scatter", "litter"),
    "LichenStone": ("Lichen Stone", "stones"),
    "PebblesA": ("Pebbles", "stones"),
    "PebblesB": ("Scattered Pebbles", "stones"),
    "PebblesC": ("Pebble Trail", "stones"),
    "FlatStones": ("Flat Stones", "stones"),
    "Driftwood": ("Driftwood", "sticks"),
    "RiverStones": ("River Stones", "stones"),
    "CrackedMud": ("Cracked Mud", "litter"),
    "ShaleChips": ("Shale Chips", "stones"),
    "BleachedBranch": ("Bleached Branch", "sticks"),
    "IceCrust": ("Broken Ice", "litter"),
    "FrostHeavedStones": ("Frost-Heaved Stones", "stones"),
    "AshPatch": ("Ash Drift", "litter"),
    "CharredSticks": ("Charred Sticks", "sticks"),
    "GravelPatch": ("Rubble Gravel", "stones"),
    "RustFlakes": ("Rusted Scrap", "scrapbits"),
    "DeadTumbleweed": ("Dead Tumbleweed", "fibers"),
}

# Grasses drawn from the game's grass sheet (ids in blender/grass/grasses.txt): name: display name
GRASSES = {
    "HairGrass": "Tufted Hairgrass",
    "OrchardGrass": "Orchard Grass",
    "WildOats": "Wild Oats",
    "Foxtail": "Foxtail",
    "Sedge": "Sedge",
    "Timothy": "Timothy",
    "Bracken": "Bracken",
    "Redtop": "Redtop",
    "Clover": "Clover and Plantain",
    "DryBunchgrass": "Dry Bunchgrass",
    "Horsetail": "Horsetail",
    "SheepSorrel": "Sheep Sorrel",
    "BlueGrama": "Blue Grama",
    "Needlegrass": "Needlegrass",
    "CottonGrass": "Cotton Grass",
    "FrostTussock": "Frosted Tussock",
    "BurntStubble": "Burnt Stubble",
    "GreenShoots": "Green Shoots",
    "Cheatgrass": "Cheatgrass",
    "FoxtailBarley": "Foxtail Barley",
}
# Grasses taken out (and no longer placed), each kept as a block drawn with another grass's tile: worlds that already
# have them would otherwise load chunks holding blocks the game no longer knows
RETIRED_GRASSES = {"BlueFescue": "HairGrass", "Wheatgrass": "OrchardGrass"}

# Trees: species: (display name, its variants)
TREES = {
    "Birch": ("Paper Birch", ["Birch01", "Birch02", "Birch03", "Birch04"]),
    "Maple": ("Sugar Maple", ["Maple01", "Maple02", "Maple03", "Maple04"]),
    "DouglasFir": ("Douglas Fir", ["DouglasFir01", "DouglasFir02", "DouglasFir03", "DouglasFir04"]),
    "SubalpineFir": ("Subalpine Fir", ["SubalpineFir01", "SubalpineFir02", "SubalpineFir03", "SubalpineFir04"]),
    "CharredSnag": ("Charred Snag", ["CharredSnag01", "CharredSnag02", "CharredSnag03", "CharredSnag04"]),
    "JoshuaTree": ("Joshua Tree", ["JoshuaTree01", "JoshuaTree02", "JoshuaTree03", "JoshuaTree04"]),
    # Wave 2
    "Willow": ("Weeping Willow", ["Willow01", "Willow02", "Willow03", "Willow04"]),
    "Saguaro": ("Saguaro", ["Saguaro01", "Saguaro02", "Saguaro03", "Saguaro04"]),
    "Sequoia": ("Giant Sequoia", ["Sequoia01", "Sequoia02", "Sequoia03", "Sequoia04"]),
    "WolfOak": ("Wolf Oak", ["WolfOak01", "WolfOak02", "WolfOak03", "WolfOak04"]),
    "Aspen": ("Quaking Aspen", ["Aspen01", "Aspen02", "Aspen03", "Aspen04"]),
    "Bristlecone": ("Bristlecone Pine", ["Bristlecone01", "Bristlecone02", "Bristlecone03", "Bristlecone04"]),
    "BlueSpruce": ("Blue Spruce", ["BlueSpruce01", "BlueSpruce02", "BlueSpruce03", "BlueSpruce04"]),
    "RedMaple": ("Red Maple", ["RedMaple01", "RedMaple02", "RedMaple03", "RedMaple04"]),
    "Cottonwood": ("Cottonwood", ["Cottonwood01", "Cottonwood02", "Cottonwood03", "Cottonwood04"]),
    "PaloVerde": ("Palo Verde", ["PaloVerde01", "PaloVerde02", "PaloVerde03", "PaloVerde04"]),
    "Crabapple": ("Flowering Crabapple", ["Crabapple01", "Crabapple02", "Crabapple03", "Crabapple04"]),
    "HollowSnag": ("Hollow Snag", ["HollowSnag01", "HollowSnag02", "HollowSnag03", "HollowSnag04"]),
}
# Each species' gibs when felled, by height [(up to metres, particle)], as vanilla's trees of its biome: winter
# pines burst snow, burnt pines ash, the desert's juniper dust; the rest vanilla's dead tree's
GIBS = {
    "SubalpineFir": [(8, "treeGib_winter_small"), (16, "treeGib_winter01"), (24, "treeGib_winter02"),
                     (99, "treeGib_winter03")],
    "CharredSnag": [(8, "treeGib_burnt_small"), (99, "treeGib_burnt_55m")],
    "JoshuaTree": [(99, "treeGib_small_dust")],
    # Wave 2: the willow, aspen, maples, wolf oak, cottonwood, crabapple and hollow snag use the default
    "Saguaro": [(99, "treeGib_small_dust")],
    "PaloVerde": [(99, "treeGib_small_dust")],
    "Sequoia": [(30, "treeGib_dead_01"), (99, "treeGib_burnt_75m")],
    "Bristlecone": [(8, "treeGib_winter_small"), (16, "treeGib_winter01"), (99, "treeGib_winter02")],
    "BlueSpruce": [(8, "treeGib_winter_small"), (16, "treeGib_winter01"), (24, "treeGib_winter02"),
                   (99, "treeGib_winter03")],
}
# Burnt trees give coal too, both to a wood axe and to whatever harvests coal (vanilla's burnt pines: 11 to 22 of
# each from a 20 m tree), and, having no seed of their own, vanilla's mountain pine seed as its burnt pines do
COAL = {"CharredSnag": [(8, "3,6"), (99, "6,12")]}
FOREIGN_SEEDS = {"CharredSnag": "treePlantedMountainPine1m"}

# Saguaros are cacti, not wood: wild ones extend vanilla's treeCactus01 (Class Cactus: touching one hurts, Shape
# DistantDeco, and it gives yucca fibers, yucca fruit and its seed instead of wood). Set CACTUS_CLASS False to make
# them ordinary trees (the tree class, fiber and fruit drops) if the cactus class misbehaves in game.
CACTI = {"Saguaro"}
CACTUS_CLASS = True

# A tree 33 m or taller drops what vanilla's 41 to 48 m oak does: MtreeWoodFull and 150 wood
FULL_WOOD_FROM = 33

# Wild trees whose block covers more than one column (MultiBlockDim x,H,z): variant: (x, z). The placement code
# clears the footprint, which the game's decorator needs for a wide crown or trunk; the planted chain stays 1,N,1 (a
# seed needs one free block). BigDecorationRadius follows: (x - 1) // 2 + 1, vanilla's 3 for the default width.
FOOTPRINT = {"Sequoia01": (5, 5), "Sequoia02": (5, 5), "Sequoia04": (5, 5), "Sequoia03": (3, 3),
             "Aspen01": (5, 5), "Aspen02": (5, 5), "Aspen03": (1, 1), "Aspen04": (3, 3)}

# Slower growers: species: minutes per growth stage (vanilla's trees: GrowthRate 63)
GROWTH = {"Sequoia": 120}

# Tree seeds, as vanilla's oak and pine seeds: species: (the seed's name, its seedling (the planted seed's model), the
# variants it grows through after it, the last the grown tree). Every tree of the species, wild or planted, drops
# seeds when felled: 1 from a tree under 15 m, 2 from a bigger one (vanilla's small oak and pine drop 1, the rest 2).
# A seed's icon is the tree build's unity/Assets/NatureExpanded/Trees/<Species>/<Species>Seed_Icon.png (blender/trees'
# script draws it), copied into UIAtlases/ItemIconAtlas.
SEEDS = {
    "Birch": ("Birch Seed", "BirchSapling", ["Birch04", "Birch01"]),
    "Maple": ("Maple Seed", "MapleSapling", ["Maple04", "Maple03", "Maple01"]),
    "DouglasFir": ("Douglas Fir Seed", "DouglasFirSapling", ["DouglasFir04", "DouglasFir02", "DouglasFir01"]),
    "SubalpineFir": ("Subalpine Fir Seed", "SubalpineFirSapling", ["SubalpineFir04", "SubalpineFir02",
                                                                  "SubalpineFir01"]),
    "JoshuaTree": ("Joshua Tree Seed", "JoshuaTreeSapling", ["JoshuaTree04", "JoshuaTree03", "JoshuaTree02",
                                                            "JoshuaTree01"]),
    # Wave 2 (HollowSnag has none: a dead tree, no seed). Saguaro and palo verde start as the small variants.
    "Willow": ("Willow Seed", "WillowSapling", ["Willow04", "Willow02", "Willow01"]),
    "Saguaro": ("Saguaro Seed", "SaguaroSapling", ["Saguaro03", "Saguaro01"]),
    "Sequoia": ("Sequoia Seed", "SequoiaSapling", ["Sequoia03", "Sequoia02"]),
    "WolfOak": ("Wolf Oak Acorn", "WolfOakSapling", ["WolfOak04", "WolfOak03", "WolfOak01"]),
    "Aspen": ("Aspen Seed", "AspenSapling", ["Aspen04", "Aspen01"]),
    "Bristlecone": ("Bristlecone Pine Seed", "BristleconeSapling", ["Bristlecone04", "Bristlecone03", "Bristlecone01"]),
    "BlueSpruce": ("Blue Spruce Seed", "BlueSpruceSapling", ["BlueSpruce04", "BlueSpruce03", "BlueSpruce01"]),
    "RedMaple": ("Red Maple Seed", "RedMapleSapling", ["RedMaple04", "RedMaple01"]),
    "Cottonwood": ("Cottonwood Seed", "CottonwoodSapling", ["Cottonwood04", "Cottonwood01"]),
    "PaloVerde": ("Palo Verde Seed", "PaloVerdeSapling", ["PaloVerde04", "PaloVerde03", "PaloVerde02", "PaloVerde01"]),
    "Crabapple": ("Crabapple Seed", "CrabappleSapling", ["Crabapple04", "Crabapple03", "Crabapple02", "Crabapple01"]),
}

# kind: (material, harvest drops [(item, count)], description key)
KINDS = {
    "flower": ("Mplants", [("resourceYuccaFibers", "2")], "DementiveNaturePlantDesc"),
    "bush": ("Mplants", [("resourceYuccaFibers", "4")], "DementiveNaturePlantDesc"),
    "cactus": ("Mcactus", [("resourceYuccaFibers", "3")], "DementiveNaturePlantDesc"),
    "mushroom": ("Mmushrooms", [("foodCropMushrooms", "1")], "DementiveNatureMushroomDesc"),
    "toadstool": ("Mmushrooms", [("resourceYuccaFibers", "1")], "DementiveNatureToadstoolDesc"),
    "log": ("MtreeWoodSmall", [("resourceWood", "8")], "DementiveNatureLogDesc"),
    # Ground cover: one hit picks it up (MaxDamage 1, like a plant), the material only sets the hit sound and dust
    "litter": ("Mplants", [], "DementiveNatureLitterDesc"),
    "stones": ("Mstone_scrap", [("resourceRockSmall", "1,3")], "DementiveNatureStonesDesc"),
    "sticks": ("Mwood_weak", [("resourceWood", "1,2")], "DementiveNatureSticksDesc"),
    # The game has no pinecone, acorn or tumbleweed item: dry plant matter is plant fibers
    "fibers": ("Mplants", [("resourceYuccaFibers", "1,2")], "DementiveNatureFibersDesc"),
    "scrapbits": ("Miron_scrap", [("resourceScrapIron", "1,2")], "DementiveNatureScrapBitsDesc"),
}
GROUND_KINDS = {"litter", "stones", "sticks", "fibers", "scrapbits"}
# Ground cover with a smaller yield than its kind's
GROUND_COUNTS = {"LichenStone": "1,2", "GravelPatch": "1,2"}
# Ground cover is drawn from its own bundle (it keeps the textures' baked sizes, which the plants bundle's 512 cap
# would not): built by src/build-bundle.bat together with the plants, git-ignored, see NatureExpanded/.gitignore
GROUND_BUNDLE = "#@modfolder:Resources/natureexpanded-ground.unity3d?"

MEADOW = ["Poppy", "Lupine", "Cornflower", "OxeyeDaisy", "Paintbrush", "BlackEyedSusan", "Coneflower",
          "QueenAnnesLace", "RedClover", "Bergamot", "Chicory"]
FLOOR = {"Fern": 0.04, "Trillium": 0.008, "WildStrawberry": 0.008, "Foxglove": 0.006, "FlyAgaric": 0.005,
         "Bolete": 0.005, "MossyLog": 0.004, "WildRose": 0.006, "Elderberry": 0.005, "Sumac": 0.005}

# Per vanilla biome: drifts [(species, [companions])], mix {vanilla sub-biome noise: {plant: prob}}, scatter {plant: prob}
BIOMES = {
    "pine_forest": {
        "drifts": [
            ("Lupine", ["Paintbrush", "OxeyeDaisy", "Bergamot"]), ("Poppy", ["Cornflower", "OxeyeDaisy", "Chicory"]),
            ("Cornflower", ["Poppy", "Chicory", "RedClover"]), ("OxeyeDaisy", ["Cornflower", "RedClover", "Lupine"]),
            ("Paintbrush", ["Lupine", "BlackEyedSusan", "QueenAnnesLace"]),
            ("BlackEyedSusan", ["Coneflower", "QueenAnnesLace", "Poppy"]),
            ("Coneflower", ["BlackEyedSusan", "Bergamot", "OxeyeDaisy"]),
            ("QueenAnnesLace", ["Chicory", "Bergamot", "Paintbrush"]),
            ("RedClover", ["OxeyeDaisy", "QueenAnnesLace", "Cornflower"]),
            ("Bergamot", ["Coneflower", "Lupine", "BlackEyedSusan"]),
            ("Chicory", ["QueenAnnesLace", "RedClover", "Poppy"]),
            ("Fern", ["Trillium", "Foxglove", "WildStrawberry"]),
        ],
        "mix": {
            # Clustered flowers (vanilla: goldenrod, cotton and chrysanthemum at 3% each)
            ".0095, 0, .21": {p: 0.01 for p in MEADOW},
            # The tree groves and the ring round them: the forest floor
            ".072, 0, .29": FLOOR,
            ".014, 0, .38": FLOOR,
            ".014, 0, .46": FLOOR,
        },
        "thin": {".0095, 0, .21": {"plantedGoldenrod3Harvest": ".008", "plantedCotton3Harvest": ".008",
                                   "plantedChrysanthemum3Harvest": ".008"}},
        "scatter": dict({p: 0.0015 for p in MEADOW}, Fern=0.003, Trillium=0.001, Foxglove=0.001, WildRose=0.0008,
                        FlyAgaric=0.0008, Bolete=0.0008, MossyLog=0.0005, Elderberry=0.0005, Sumac=0.0005),
        "grass": {
            "cover": {"treeTallGrassDiagonal": 0.2},
            # Green dominates: the user found the colourful mix "like confetti". The straw and red ones (wild oats,
            # dry bunchgrass, redtop, sheep sorrel) are rare accents, at about 15% of their old rates, and never
            # lead a patch
            "main": {"HairGrass": 0.02, "OrchardGrass": 0.018, "Foxtail": 0.02, "Timothy": 0.016, "Sedge": 0.01,
                     "Clover": 0.016, "Horsetail": 0.004, "Bracken": 0.005,
                     "WildOats": 0.0024, "DryBunchgrass": 0.0018, "Redtop": 0.0009, "SheepSorrel": 0.0006},
            "mix": {
                ".0095, 0, .21": {"OrchardGrass": 0.03, "Foxtail": 0.03, "Timothy": 0.03, "Clover": 0.03,
                                  "WildOats": 0.0045, "Redtop": 0.0015},
                ".072, 0, .29": {"Bracken": 0.05, "Sedge": 0.03, "HairGrass": 0.02, "Horsetail": 0.01},
                ".014, 0, .38": {"Bracken": 0.05, "Sedge": 0.03, "HairGrass": 0.02, "Horsetail": 0.01},
                ".014, 0, .46": {"Bracken": 0.04, "Sedge": 0.03, "HairGrass": 0.02, "Clover": 0.015},
            },
            "patches": [
                [("HairGrass", {"Sedge": 0.04}), ("OrchardGrass", {"Foxtail": 0.04})],
                [("Timothy", {"OrchardGrass": 0.04, "Redtop": 0.003}), ("Clover", {"HairGrass": 0.04, "SheepSorrel": 0.002})],
                [("Foxtail", {"Timothy": 0.04, "WildOats": 0.006}), ("OrchardGrass", {"Clover": 0.04, "DryBunchgrass": 0.004})],
                [("Sedge", {"Horsetail": 0.05}), ("Bracken", {"Sedge": 0.05})],
                [("HairGrass", {"Foxtail": 0.04}), ("Foxtail", {"HairGrass": 0.04})],
            ],
            "density": 1.0,
        },
        # Trees: into vanilla's tree sub-biomes (the dense large trees and the ring round them hold about .2 of
        # pines and oaks), and a few lone ones over the open ground
        "trees": {
            ".014, 0, .38": {"Birch01": 0.006, "Birch02": 0.005, "Birch03": 0.004, "Birch04": 0.006,
                             "Maple01": 0.006, "Maple02": 0.004, "Maple03": 0.005, "Maple04": 0.005,
                             "DouglasFir01": 0.004, "DouglasFir02": 0.003, "DouglasFir03": 0.002, "DouglasFir04": 0.004},
            ".014, 0, .46": {"Birch01": 0.005, "Birch02": 0.004, "Birch03": 0.003, "Birch04": 0.006,
                             "Maple01": 0.004, "Maple02": 0.003, "Maple03": 0.004, "Maple04": 0.005,
                             "DouglasFir01": 0.003, "DouglasFir02": 0.002, "DouglasFir03": 0.001, "DouglasFir04": 0.004},
            "main": {"Birch01": 0.0003, "Birch02": 0.0002, "Birch03": 0.0002, "Birch04": 0.0003,
                     "Maple01": 0.0003, "Maple02": 0.0002, "Maple03": 0.0002, "Maple04": 0.0003,
                     "DouglasFir01": 0.0002, "DouglasFir02": 0.0001, "DouglasFir03": 0.0001, "DouglasFir04": 0.0003},
        },
    },
    "burnt_forest": {
        "drifts": [("Fireweed", ["Lupine", "CharredShrub", "Morels"]), ("Lupine", ["Fireweed", "Morels", "DeadBrush"])],
        "mix": {".033, 0, .3": {"Morels": 0.01, "CharredShrub": 0.01, "Fireweed": 0.01}},
        "scatter": {"CharredShrub": 0.004, "Morels": 0.002, "Fireweed": 0.002, "DeadBrush": 0.002},
        "grass": {
            "main": {"BurntStubble": 0.05, "GreenShoots": 0.03},
            "mix": {".033, 0, .3": {"GreenShoots": 0.06, "BurntStubble": 0.04}},
            "patches": [[("GreenShoots", {"BurntStubble": 0.06}), ("BurntStubble", {"GreenShoots": 0.05})]],
            "density": 0.8,
        },
        # Charred snags among vanilla's burnt pines (.01 each over the open ground, .03 each in its tree sub-biomes):
        # about a third as many
        "trees": dict({noise: {"CharredSnag01": 0.01, "CharredSnag02": 0.008, "CharredSnag03": 0.005,
                               "CharredSnag04": 0.005} for noise in (".031, 0, .22", ".032, 0, .23", ".04, 0, .4")},
                      main={"CharredSnag01": 0.004, "CharredSnag02": 0.003, "CharredSnag03": 0.002,
                            "CharredSnag04": 0.002}),
    },
    "desert": {
        "drifts": [("DesertMarigold", ["Globemallow", "EveningPrimrose", "Sagebrush"]),
                   ("Globemallow", ["DesertMarigold", "Sagebrush", "PricklyPear"]),
                   ("EveningPrimrose", ["DesertMarigold", "PricklyPear", "Globemallow"]),
                   ("Sagebrush", ["Globemallow", "BarrelCactus", "DesertMarigold"])],
        "mix": {noise: {"PricklyPear": 0.01, "BarrelCactus": 0.008, "Ocotillo": 0.006, "AgaveBloom": 0.003}
                for noise in (".02, 0, .3", ".02, 0, .45", ".03, 0, .3")},
        "scatter": {"PricklyPear": 0.0015, "BarrelCactus": 0.0015, "Ocotillo": 0.001, "AgaveBloom": 0.0006,
                    "Sagebrush": 0.003, "DesertMarigold": 0.0015, "Globemallow": 0.0015, "EveningPrimrose": 0.001},
        "grass": {
            "main": {"BlueGrama": 0.03, "Needlegrass": 0.025, "DryBunchgrass": 0.012},
            "patches": [[("BlueGrama", {"Needlegrass": 0.05}), ("Needlegrass", {"BlueGrama": 0.05})]],
            "density": 0.6,
        },
        # Joshua trees about as common as vanilla's few desert oaks (.0023 over the open ground), more in the oaks'
        # sub-biomes and its dead trees' one
        "trees": dict({noise: {"JoshuaTree01": 0.001, "JoshuaTree02": 0.0015, "JoshuaTree03": 0.0015,
                               "JoshuaTree04": 0.002}
                       for noise in (".03, 0, .2", ".032, 0, .22", ".04, 0, .3", ".02, 0, .45")},
                      main={"JoshuaTree01": 0.0004, "JoshuaTree02": 0.0006, "JoshuaTree03": 0.0006,
                            "JoshuaTree04": 0.0008}),
    },
    "snow": {
        "drifts": [("Heather", ["AlpineAster", "Snowdrop", "Winterberry"]),
                   ("AlpineAster", ["Heather", "Snowdrop", "FrostedJuniper"])],
        "mix": {".033, 0, .3": {"Winterberry": 0.01, "Heather": 0.02, "AlpineAster": 0.015, "Snowdrop": 0.01}},
        "scatter": {"Winterberry": 0.002, "FrostedJuniper": 0.003, "Snowdrop": 0.002, "Heather": 0.002,
                    "AlpineAster": 0.0015},
        "grass": {
            "main": {"FrostTussock": 0.04, "CottonGrass": 0.025},
            "patches": [[("FrostTussock", {"CottonGrass": 0.05}), ("CottonGrass", {"FrostTussock": 0.06})]],
            "density": 0.7,
        },
        # Subalpine firs among vanilla's winter pines (.003 each of five, over the open ground and in its tree
        # sub-biomes): about a third as many again
        "trees": dict({noise: {"SubalpineFir01": 0.002, "SubalpineFir02": 0.0015, "SubalpineFir03": 0.001,
                               "SubalpineFir04": 0.002} for noise in (".031, 0, .22", ".032, 0, .23", ".04, 0, .4")},
                      main={"SubalpineFir01": 0.0015, "SubalpineFir02": 0.001, "SubalpineFir03": 0.0015,
                            "SubalpineFir04": 0.0015}),
    },
    "wasteland": {
        "drifts": [("WildMustard", ["Thistle", "CurlyDock", "SilverSage"]),
                   ("Thistle", ["CurlyDock", "SilverSage", "WildMustard"]),
                   ("CurlyDock", ["Thistle", "WildMustard", "DeadBrush"])],
        "mix": {".028, 0, .32": {"Thistle": 0.01, "CurlyDock": 0.01, "DeadBrush": 0.01}},
        "scatter": {"SilverSage": 0.003, "DeadBrush": 0.004, "Thistle": 0.0015, "WildMustard": 0.0015,
                    "CurlyDock": 0.0015},
        "grass": {
            "main": {"Cheatgrass": 0.035, "FoxtailBarley": 0.03, "DryBunchgrass": 0.015},
            "mix": {".028, 0, .32": {"Cheatgrass": 0.04, "FoxtailBarley": 0.03}},
            "patches": [[("Cheatgrass", {"FoxtailBarley": 0.06}), ("FoxtailBarley", {"Cheatgrass": 0.06})]],
            "density": 0.7,
        },
    },
}

# Wave 2 trees (rates from the tree agents' specs, relative to the birch, maple and subalpine fir rates above), merged
# into each biome's "trees" table. Pine forest: the tree sub-biomes .38 (dense large trees) and .46 (the ring round
# them), then lone trees over the open ground ("main"). Willow and cottonwood also grow along shores (the DLL's
# ShoreDEM, BankTrees). Flame-red maple (RedMaple03) is a sixth of its siblings' rate.
_PINE_38 = {
    "Willow01": 0.0015, "Willow02": 0.001, "Willow03": 0.001, "Willow04": 0.0015,
    "Sequoia03": 0.002, "Sequoia02": 0.0012, "Sequoia04": 0.0006, "Sequoia01": 0.0004,
    "WolfOak04": 0.0005, "WolfOak01": 0.0001,
    "Aspen01": 0.004, "Aspen02": 0.004, "Aspen03": 0.003, "Aspen04": 0.005,
    "BlueSpruce01": 0.0004, "BlueSpruce02": 0.0004, "BlueSpruce03": 0.0003, "BlueSpruce04": 0.0003,
    "RedMaple01": 0.006, "RedMaple02": 0.004, "RedMaple03": 0.0008, "RedMaple04": 0.005,
    "Cottonwood01": 0.0004, "Cottonwood02": 0.0008, "Cottonwood03": 0.0008, "Cottonwood04": 0.001,
    "Crabapple01": 0.0006, "Crabapple02": 0.0004, "Crabapple03": 0.0005, "Crabapple04": 0.0005,
    "HollowSnag01": 0.0008, "HollowSnag02": 0.0004, "HollowSnag03": 0.0004, "HollowSnag04": 0.0006,
}
# The ring (.46): willow and sequoia a little thinner, the red maples at the sugar maples' ring rates
_PINE_46 = dict(_PINE_38, Willow01=0.0013, Willow03=0.0008, Willow04=0.0013,
                Sequoia03=0.0014, Sequoia02=0.00084, Sequoia04=0.00042, Sequoia01=0.00028,
                RedMaple01=0.004, RedMaple02=0.003, RedMaple03=0.0007, RedMaple04=0.005)
_PINE_MAIN = {
    "Sequoia03": 0.0001, "Sequoia02": 0.00006, "Sequoia04": 0.00004, "Sequoia01": 0.00003,
    "WolfOak01": 0.00016, "WolfOak02": 0.0001, "WolfOak03": 0.00008, "WolfOak04": 0.00006,
    "Aspen03": 0.0002, "Aspen04": 0.0002,
    "Cottonwood01": 0.0001, "Cottonwood02": 0.0003, "Cottonwood03": 0.0003, "Cottonwood04": 0.0003,
    "Crabapple01": 0.00003, "Crabapple02": 0.00002, "Crabapple03": 0.00003, "Crabapple04": 0.00002,
    "HollowSnag01": 0.0001, "HollowSnag02": 0.00005, "HollowSnag03": 0.00005, "HollowSnag04": 0.00005,
}
_TREE_NOISE = (".031, 0, .22", ".032, 0, .23", ".04, 0, .4")           # snow and burnt forest tree sub-biomes
_DESERT_NOISE = (".03, 0, .2", ".032, 0, .22", ".04, 0, .3", ".02, 0, .45")
_WASTE_NOISE = (".028, 0, .21", ".03, 0, .21", ".031, 0, .22", ".04, 0, .4")
_WAVE2 = [
    ("pine_forest", (".014, 0, .38",), _PINE_38),
    ("pine_forest", (".014, 0, .46",), _PINE_46),
    ("pine_forest", ("main",), _PINE_MAIN),
    # Blue spruce at the subalpine fir's rates split 3:3:2:2; bristlecone beside it
    ("snow", _TREE_NOISE, {"BlueSpruce01": 0.00195, "BlueSpruce02": 0.00195, "BlueSpruce03": 0.0013,
                           "BlueSpruce04": 0.0013, "Bristlecone01": 0.0008, "Bristlecone02": 0.0005,
                           "Bristlecone03": 0.001, "Bristlecone04": 0.0008}),
    ("snow", ("main",), {"BlueSpruce01": 0.00165, "BlueSpruce02": 0.00165, "BlueSpruce03": 0.0011,
                         "BlueSpruce04": 0.0011, "Bristlecone01": 0.0006, "Bristlecone02": 0.0004,
                         "Bristlecone03": 0.0008, "Bristlecone04": 0.0006}),
    ("burnt_forest", _TREE_NOISE, {"HollowSnag01": 0.004, "HollowSnag02": 0.003, "HollowSnag03": 0.003,
                                   "HollowSnag04": 0.003}),
    ("burnt_forest", ("main",), {"HollowSnag01": 0.0005, "HollowSnag02": 0.0003, "HollowSnag03": 0.0004,
                                 "HollowSnag04": 0.0003}),
    # Saguaros and palo verdes among the Joshua trees' sub-biomes; the palo verdes' two flowering forms stay rare
    ("desert", _DESERT_NOISE, {"Saguaro01": 0.0012, "Saguaro02": 0.0004, "Saguaro03": 0.002, "Saguaro04": 0.0008,
                               "PaloVerde01": 0.0006, "PaloVerde02": 0.0006, "PaloVerde03": 0.0008,
                               "PaloVerde04": 0.001}),
    ("desert", ("main",), {"Saguaro01": 0.0006, "Saguaro02": 0.0002, "Saguaro03": 0.001, "Saguaro04": 0.0004,
                           "PaloVerde01": 0.0003, "PaloVerde02": 0.0003, "PaloVerde03": 0.0004,
                           "PaloVerde04": 0.0005}),
    # Hollow snags: dead ground, about .004 over the open wasteland and two or three times that in its trees
    ("wasteland", _WASTE_NOISE, {"HollowSnag01": 0.003, "HollowSnag02": 0.002, "HollowSnag03": 0.003,
                                 "HollowSnag04": 0.0025}),
    ("wasteland", ("main",), {"HollowSnag01": 0.0012, "HollowSnag02": 0.0008, "HollowSnag03": 0.0012,
                              "HollowSnag04": 0.001}),
]
for _biome, _where, _probs in _WAVE2:
    for _noise in _where:
        BIOMES[_biome].setdefault("trees", {}).setdefault(_noise, {}).update(_probs)
# Tree groves: sub-biomes of one species' trees on their own noise (after the drifts, ahead of the grass patches):
# (label, noise frequency, noise band, {variant: chance per spot}). Aspens grow in stands.
BIOMES["pine_forest"]["groves"] = [
    ("Aspen stand", 0.02, (0.0, 0.15), {"Aspen01": 0.012, "Aspen02": 0.012, "Aspen04": 0.012}),
]

# Vanilla's wild crops, left out of the drifts' copies of the biome's decorations
CROPS = {"plantedCotton3Harvest", "plantedGoldenrod3Harvest", "plantedChrysanthemum3Harvest",
         "plantedSnowberry3Harvest", "plantedBlueberry3Harvest"}


def block(name):
    return PREFIX + name


def tree_sizes():
    """variant: (height in blocks, height in metres) for each tree the tree build has measured."""
    path = os.path.join(MOD, "unity", "Build", "tree-sizes.txt")
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            parts = line.split()
            if len(parts) >= 3:
                out[parts[0]] = (int(parts[1]), float(parts[2]))
    return out


def seed_block(species, trees):
    """The species' seed block, if it has one and the tree build has measured its seedling and every stage."""
    if species not in SEEDS:
        return None
    _, seedling, stages = SEEDS[species]
    if any(v not in trees for v in [seedling] + stages):
        return None
    return block("Tree" + species + "Seed")


def by_height(table, metres, default=None):
    """The value for a tree `metres` tall from [(up to metres, value)]."""
    for top, value in table:
        if metres < top:
            return value
    return default


def tree_species(variant):
    """The species a variant belongs to (the longest species name it starts with)."""
    return max((sp for sp in TREES if variant.startswith(sp)), key=len)


def tree_lines(variant, size, seed, wild=True):
    """A tree block's model, size, gibs, wood (and coal) and seed drops; `size` its (blocks, metres) tall. `wild`
    blocks get their species' footprint (planted-chain stages stay one column wide)."""
    blocks, metres = size
    species = tree_species(variant)
    gib = by_height(GIBS.get(species, ()), metres, "treeGib_dead_01")
    seed = seed or FOREIGN_SEEDS.get(species)
    cactus = species in CACTI and CACTUS_CLASS
    # Wood and toughness by size, like vanilla's (30, 70, 110 wood for small, medium and large trees, 150 for the
    # 41 to 48 m ones)
    if cactus:
        material, wood = "Mcactus", 0
    elif metres >= FULL_WOOD_FROM:
        material, wood = "MtreeWoodFull", 150
    else:
        material, wood = (("MtreeWoodSmall", 30) if metres < 11 else ("MtreeWoodMedium", 60) if metres < 17
                          else ("MtreeWoodLarge", 90))
    fx, fz = FOOTPRINT.get(variant, (1, 1)) if wild else (1, 1)
    out = ['\t\t\t<property name="Model" value="%s%s"/>' % (TREE_BUNDLE, variant),
           '\t\t\t<property name="ModelOffset" value="0,-0.5,0"/>',
           '\t\t\t<property name="MultiBlockDim" value="%d,%d,%d"/>' % (fx, blocks, fz),
           '\t\t\t<property name="Material" value="%s"/>' % material,
           '\t\t\t<property name="Path" value="solid"/>',
           '\t\t\t<property name="BigDecorationRadius" value="%d"/>' % ((fx - 1) // 2 + 1 if wild and variant in FOOTPRINT else 3),
           '\t\t\t<property name="ParticleOnDeath" value="%s"/>' % gib]
    if species in CACTI:
        # As vanilla's treeCactus01: fibers per hit, fruit and fibers when it falls (its own drops, not treeMaster's)
        out += ['\t\t\t<dropextendsoff/>' if cactus else '',
                '\t\t\t<drop event="Harvest" name="resourceYuccaFibers" count="10" tag="oreWoodHarvest"/>',
                '\t\t\t<drop event="Destroy" name="foodCropYuccaFruit" count="3"/>',
                '\t\t\t<drop event="Destroy" name="resourceYuccaFibers" count="5"/>']
        out = [line for line in out if line]
    else:
        out.append('\t\t\t<drop event="Harvest" name="resourceWood" count="%d" tag="oreWoodHarvest,lumberjackHarvest"/>' % wood)
    coal = by_height(COAL.get(species, ()), metres)
    if coal:
        out += ['\t\t\t<drop event="Harvest" name="resourceCoal" count="%s" tag="oreWoodHarvest"/>' % coal,
                '\t\t\t<drop event="Harvest" name="resourceCoal" count="%s" tag="coalHarvest"/>' % coal]
    if seed is not None:
        out.append('\t\t\t<drop event="Destroy" name="%s" count="%d"/>' % (seed, 1 if metres < 15 else 2))
    return out


def heights():
    path = os.path.join(MOD, "unity", "Build", "plant-sizes.txt")
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            parts = line.split()
            if len(parts) >= 2:
                out[parts[0]] = int(parts[1])
    return out


def deco(plant, prob):
    return '<decoration type="block" blockname="%s" prob="%s" rotatemax="7"/>' % (block(plant), fmt(prob))


def grass_deco(name, prob):
    return '<decoration type="block" blockname="%s" prob="%s"/>' % (block("Grass" + name), fmt(prob))


def grass_ids():
    """Each grass's texture id in the game's grass sheet, from blender/grass/grasses.txt."""
    out = {}
    for line in open(os.path.join(MOD, "blender", "grass", "grasses.txt"), encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            gid, name = line.split()[:2]
            out[name] = int(gid)
    missing = set(GRASSES) - set(out)
    if missing:
        raise SystemExit("grasses.txt has no id for " + ", ".join(sorted(missing)))
    return out


def fmt(p):
    s = ("%.5f" % p).rstrip("0")
    s = s[1:] if s.startswith("0.") else s
    return s.rstrip(".") or "0"


# ===================================================================================================================
# FEATURES: solid natural features (boulders, rock formations, cairns, bones). See NatureExpanded/FEATURES.md.
# Everything for them lives in this section and the four hooks that call it (write_blocks, write_biomes twice,
# write_localization). Models: blender/features/*.py, built by src/build-features.bat into
# Resources/natureexpanded-features.unity3d, which writes unity/Build/feature-sizes.txt ("Name cellsX cellsY cellsZ
# meshX meshY meshZ"); only features the build has measured get blocks.
# ===================================================================================================================
FEATURE_BUNDLE = "#@modfolder:Resources/natureexpanded-features.unity3d?"
FEATURE_CLASS = "FeatureDEM, NatureExpanded"

# name: (display name, kind)
FEATURES = {
    # Forest and meadow
    "MossyBoulder01": ("Mossy Boulder", "rock"),
    "MossyBoulder02": ("Mossy Boulder", "rock"),
    "MossyBoulder03": ("Mossy Boulder", "rock"),
    "MossyBoulder04": ("Boulder Tumble", "rock"),
    "GlacialErratic01": ("Glacial Erratic", "rock"),
    "GlacialErratic02": ("Glacial Erratic", "rock"),
    "GraniteOutcrop01": ("Granite Outcrop", "rock"),
    "StoneCairnForest": ("Stone Cairn", "rock"),
    "AntlerShed01": ("Shed Antler", "bone"),
    # Desert
    "Hoodoo01": ("Hoodoo", "rock"),
    "Hoodoo02": ("Hoodoo", "rock"),
    "Hoodoo03": ("Hoodoo Cluster", "rock"),
    "DesertArch01": ("Natural Arch", "rock"),
    "MesaLedge01": ("Mesa Ledge", "rock"),
    "StoneCairnDesert": ("Stone Cairn", "rock"),
    # Snow
    "SnowSpire01": ("Frost Spire", "rock"),
    "SnowSpire02": ("Frost Spire", "rock"),
    "SnowSlab01": ("Frozen Slabs", "rock"),
    "StoneCairnSnow": ("Stone Cairn", "rock"),
    # Wasteland
    "WindColumn01": ("Wind-Carved Column", "rock"),
    "WindColumn02": ("Wind-Carved Columns", "rock"),
    "WasteSlab01": ("Weathered Slab", "rock"),
    # Desert and wasteland bones
    "ElkSkull01": ("Elk Skull", "bone"),
    "ElkRibcage01": ("Elk Ribcage", "bone"),
}

# kind: material, collide flags, harvest item, count per cubic metre of half the mesh bounds with its floor and cap,
# harvest tag, description key
FEATURE_KINDS = {
    "rock": dict(material="Mboulder", collide="movement,melee,bullet,arrow,rocket", item="resourceRockSmall",
                 per_m3=8, lo=4, hi=40, tag="oreWoodHarvest", desc="DementiveNatureRockDesc"),
    "bone": dict(material="Mplants", collide="melee", item="resourceBone", per_m3=6, lo=1, hi=6, tag="allHarvest",
                 desc="DementiveNatureBonesDesc"),
}
FEATURE_DESCS = {
    "DementiveNatureRockDesc": "A weathered boulder. Break it up with a pickaxe for stone.",
    "DementiveNatureBonesDesc": "Old bones bleached by the weather. Pick them over for bone.",
}

# Where they stand. Per biome: "main": {name: prob} over the open ground (like a plant's scatter), "mix": {vanilla
# sub-biome noise: {name: prob}}, "fields": [(freq, (low, high), {name: prob})]: patches of ground (sub-biomes on their
# own noise, like grass patches) where a formation stands denser, e.g. a hoodoo field. Probabilities are per block (a
# 16 x 16 chunk is 256 blocks), so .0005 is one in two chunks.
FEATURE_PLACEMENT = {
    "pine_forest": {
        "main": {"MossyBoulder01": 0.0006, "MossyBoulder02": 0.0004, "MossyBoulder03": 0.0003, "MossyBoulder04": 0.00015,
                 "GlacialErratic01": 0.00004, "GlacialErratic02": 0.00006, "GraniteOutcrop01": 0.00006,
                 "StoneCairnForest": 0.0001, "AntlerShed01": 0.0004},
        "mix": {".0095, 0, .21": {"MossyBoulder01": 0.001, "MossyBoulder02": 0.0006, "MossyBoulder03": 0.0005,
                                   "MossyBoulder04": 0.0003, "GlacialErratic02": 0.0001, "GraniteOutcrop01": 0.0001}},
    },
    "desert": {
        "main": {"DesertArch01": 0.00003, "MesaLedge01": 0.0001, "Hoodoo01": 0.00006, "StoneCairnDesert": 0.00012,
                 "ElkSkull01": 0.0002, "ElkRibcage01": 0.00015},
        # Hoodoo fields: a few big patches of ground (about 1.5% of the desert) where they stand thick
        "fields": [(0.012, (0.0, 0.14), {"Hoodoo01": 0.004, "Hoodoo02": 0.0015, "Hoodoo03": 0.002, "MesaLedge01": 0.0006})],
    },
    "snow": {
        "main": {"SnowSpire01": 0.0001, "SnowSlab01": 0.00008, "StoneCairnSnow": 0.00015},
        "fields": [(0.014, (0.0, 0.13), {"SnowSpire01": 0.003, "SnowSpire02": 0.0015, "SnowSlab01": 0.002})],
    },
    "wasteland": {
        "main": {"WindColumn01": 0.0001, "WasteSlab01": 0.00008, "ElkSkull01": 0.0002, "ElkRibcage01": 0.00015},
        "fields": [(0.012, (0.0, 0.13), {"WindColumn01": 0.003, "WindColumn02": 0.0015, "WasteSlab01": 0.002})],
    },
}


# ---- Timber features (windfalls, nurse logs, giant stumps, the hollow trunk cache, deadfall piles): added by the logs
# work; blender/features/windfall.py, nurse_log.py, giant_stump.py, hollow_trunk.py, deadfall.py (shared kit logkit.py).
FEATURES.update({
    "WindfallFresh01": ("Windfall", "timber"),
    "WindfallOld01": ("Old Windfall", "timber"),
    "WindfallBurnt01": ("Burnt Windfall", "timber"),
    "WindfallPair01": ("Windfall Pair", "timber"),
    "NurseLog01": ("Nurse Log", "timber"),
    "NurseLog02": ("Nurse Log", "timber"),
    "NurseLogSnow01": ("Frosted Nurse Log", "timber"),
    "GiantStump01": ("Giant Stump", "timber"),
    "GiantStumpBurnt01": ("Charred Giant Stump", "timber"),
    "GiantStumpBleached01": ("Bleached Giant Stump", "timber"),
    "HollowTrunk01": ("Hollow Trunk", "cache"),
    "HollowTrunk02": ("Hollow Trunk", "cache"),
    "DeadfallPile01": ("Deadfall Pile", "timber"),
    "DeadfallPile02": ("Burnt Deadfall Pile", "timber"),
})
FEATURE_KINDS["timber"] = dict(material="MtreeWoodSmall", collide="movement,melee,bullet,arrow,rocket", item="resourceWood",
                               per_m3=2, lo=8, hi=70, tag="oreWoodHarvest,lumberjackHarvest", desc="DementiveNatureTimberDesc")
FEATURE_KINDS["cache"] = dict(FEATURE_KINDS["timber"], desc="DementiveNatureCacheDesc", loot="dementiveHollowCache",
                              klass="FeatureCacheDEM, NatureExpanded")
FEATURE_DESCS["DementiveNatureTimberDesc"] = "A fallen tree. Chop it up with an axe for wood."
FEATURE_DESCS["DementiveNatureCacheDesc"] = "A hollow trunk. Something has been stashed inside."
# Wood paid out by an axe for a whole feature, about 6 per cubic metre of trunk (vanilla's stump, 1.5 m across, pays 10
# to 15): mesh bounds say nothing about a 17 m windfall that is mostly air
FEATURE_COUNTS = {
    "WindfallFresh01": 45, "WindfallOld01": 28, "WindfallBurnt01": 28, "WindfallPair01": 60,
    "NurseLog01": 12, "NurseLog02": 16, "NurseLogSnow01": 11,
    "GiantStump01": 30, "GiantStumpBurnt01": 24, "GiantStumpBleached01": 20,
    "HollowTrunk01": 8, "HollowTrunk02": 8, "DeadfallPile01": 22, "DeadfallPile02": 18,
}


def _merge_placement(extra):
    for biome, spec in extra.items():
        dst = FEATURE_PLACEMENT.setdefault(biome, {})
        for key, val in spec.items():
            if key == "fields":
                dst.setdefault("fields", []).extend(val)
            elif key == "mix":
                for noise, table in val.items():
                    dst.setdefault("mix", {}).setdefault(noise, {}).update(table)
            else:
                dst.setdefault(key, {}).update(val)


# Probabilities are per block roll; a chunk is 256 blocks. The decorator only tries a feature where its footprint fits
# in the chunk pair it knows (the master is shifted by BigDecorationRadius, so (16 - r)/16 of each axis is accepted;
# r = 10 to 11 for a 19 to 21 m windfall: 14 to 10%, r = 5: 47%, r = 3: 66%) and only on flat ground (guessed at half the forest) and in
# the biome's open ground (guessed at 60% of it). Per forest chunk, that is about
#   windfalls    1 in 300  (4 kinds, p .00038 in all; 21 x 9)       nurse logs  1 in 60  (9 x 3, p .00046 in all)
#   giant stumps 1 in 100  (3 x 3, p .00017)                          deadfalls   1 in 120 (5 x 5, p .00016)
#   hollow trunk 1 in 10 000 (5 x 3, p 2e-6 in all)
_merge_placement({
    "pine_forest": {"main": {"WindfallFresh01": 0.00014, "WindfallOld01": 0.00016, "WindfallPair01": 0.00008,
                             "NurseLog01": 0.0002, "NurseLog02": 0.00015, "GiantStump01": 0.0001, "DeadfallPile01": 0.0001,
                             "HollowTrunk01": 0.000001, "HollowTrunk02": 0.000001}},
    "burnt_forest": {"main": {"WindfallBurnt01": 0.00016, "GiantStumpBurnt01": 0.0002, "DeadfallPile02": 0.0001}},
    "snow": {"main": {"NurseLogSnow01": 0.00015}},
    "wasteland": {"main": {"GiantStumpBleached01": 0.0001}},
    "desert": {"main": {"GiantStumpBleached01": 0.00006}},
})

# The cache's loot: a small forest stash (vanilla items, vanilla quality rules)
CACHE_LOOT = """<configs>
	<!-- The hollow trunk cache of Nature Expanded: a modest forest stash. Written by gen_nature.py. Respawn follows the
	     server's loot respawn setting like every other world container. -->
	<append xpath="/lootcontainers">
		<lootgroup name="groupDementiveHollowFood">
			<item name="foodCharredMeat"/>
			<item name="foodBoiledMeat"/>
			<item name="foodCornBread"/>
			<item name="foodCanPears"/>
			<item name="foodCanSoup"/>
			<item name="drinkJarRiverWater"/>
		</lootgroup>
		<lootgroup name="groupDementiveHollowAmmo">
			<item name="ammoArrowStone" count="5,10"/>
			<item name="ammo9mmBulletBall" count="4,9"/>
			<item name="ammoShotgunShell" count="2,5"/>
		</lootgroup>
		<lootgroup name="groupDementiveHollowTool">
			<item name="meleeToolRepairT0StoneAxe"/>
			<item name="meleeToolShovelT0StoneShovel"/>
			<item name="meleeToolFlashlight02"/>
		</lootgroup>
		<lootgroup name="groupDementiveHollowCache" count="all">
			<item group="groupDementiveHollowFood" count="1,2" loot_prob_template="high" force_prob="true"/>
			<item name="resourceYuccaFibers" count="3,8" loot_prob_template="high" force_prob="true"/>
			<item name="medicalBandage" count="1,2" loot_prob_template="medHigh" force_prob="true"/>
			<item group="groupDementiveHollowAmmo" loot_prob_template="med" force_prob="true"/>
			<item group="groupDementiveHollowTool" loot_prob_template="lower" force_prob="true"/>
		</lootgroup>
		<lootcontainer name="dementiveHollowCache" count="1" size="6,2" sound_open="UseActions/open_backpack" sound_close="UseActions/close_backpack" loot_quality_template="qualBaseTemplate">
			<item group="groupDementiveHollowCache"/>
		</lootcontainer>
	</append>
</configs>
"""


def write_loot():
    with open(os.path.join(MOD, "Config", "loot.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(CACHE_LOOT)



def feature_sizes():
    """name: (cells x, y, z, mesh size x, y, z) for each feature the features build has measured."""
    path = os.path.join(MOD, "unity", "Build", "feature-sizes.txt")
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            p = line.split()
            if len(p) >= 7:
                out[p[0]] = tuple(int(x) for x in p[1:4]) + tuple(float(x) for x in p[4:7])
    return out


# ---- Camps and single finds: abandoned camps (4, 5x5 multi-blocks) and the odd lost thing (12). Pure set dressing, with
# no loot: the only reward is the break-for-materials harvest. Models: blender/features/camp_*.py, antlers.py,
# lone_boot.py ... singles_b.py (specs in blender/features/SPEC_*.md), same bundle and pipeline as the rest of FEATURES.
FEATURES.update({
    "CampTent": ("Abandoned Tent Camp", "cloth"),
    "CampLeanTo": ("Collapsed Lean-To Camp", "cloth"),
    "CampChairs": ("Abandoned Car Camp", "scrap"),
    "CampFishing": ("Fisherman's Camp", "timber"),
    "TrailMarker": ("Trail Marker", "timber"),
    "Antlers": ("Shed Antlers", "bone"),
    "LoneBoot": ("Lone Boot", "leather"),
    "OldTire": ("Old Tire", "plastic"),
    "Wheelbarrow": ("Rusted Wheelbarrow", "scrap"),
    "LawnChair": ("Old Lawn Chair", "scrap"),
    "BrokenCooler": ("Broken Cooler", "plastic"),
    "ShoppingCart": ("Tipped Shopping Cart", "scrap"),
    "RustyBucketCans": ("Rusty Bucket and Cans", "scrap"),
    "FirewoodStack": ("Collapsed Firewood Stack", "timber"),
    "AbandonedPack": ("Abandoned Backpack", "cloth"),
    "RustedBicycle": ("Rusted Bicycle", "scrap"),
})
NEW_FEATURES = ["CampTent", "CampLeanTo", "CampChairs", "CampFishing", "TrailMarker", "Antlers", "LoneBoot", "OldTire",
                "Wheelbarrow", "LawnChair", "BrokenCooler", "ShoppingCart", "RustyBucketCans", "FirewoodStack",
                "AbandonedPack", "RustedBicycle"]
_SOLID = "movement,melee,bullet,arrow,rocket"
# Scrap is vanilla's scrapMetalPile recipe (a metal pile pays scrap iron to any tool, and to Junk Miner); cloth, plastic
# and leather follow it with their own item. hp = the block's MaxDamage (its material's default is far tougher or
# weaker than a prop of that size should be)
FEATURE_KINDS["scrap"] = dict(material="MmetalNoGlue", collide=_SOLID, item="resourceScrapIron", per_m3=8, lo=3, hi=20,
                              tag="allHarvest,perkJunkMiner", desc="DementiveNatureScrapDesc", hp=250)
FEATURE_KINDS["cloth"] = dict(material="Mcloth", collide=_SOLID, item="resourceCloth", per_m3=8, lo=2, hi=12,
                              tag="allHarvest,perkJunkMiner", desc="DementiveNatureClothDesc", hp=150)
FEATURE_KINDS["plastic"] = dict(material="Mplastics", collide=_SOLID, item="resourceScrapPolymers", per_m3=8, lo=2, hi=8,
                                tag="allHarvest,perkJunkMiner", desc="DementiveNaturePlasticDesc", hp=100)
FEATURE_KINDS["leather"] = dict(material="Mleather", collide=_SOLID, item="resourceLeather", per_m3=8, lo=1, hi=4,
                                tag="allHarvest,perkJunkMiner", desc="DementiveNatureLeatherDesc", hp=60)
FEATURE_COUNTS.update({
    "CampTent": 6, "CampLeanTo": 6, "CampChairs": 6, "CampFishing": 10, "TrailMarker": 5, "Antlers": 2, "LoneBoot": 2,
    "OldTire": 3, "Wheelbarrow": 8, "LawnChair": 3, "BrokenCooler": 3, "ShoppingCart": 8, "RustyBucketCans": 4,
    "FirewoodStack": 24, "AbandonedPack": 3, "RustedBicycle": 8,
})
# A second drop on a feature made of two things (the wheelbarrow's handles, a camp's firewood)
FEATURE_EXTRA_DROPS = {
    "Wheelbarrow": [("resourceWood", 2, "allHarvest,lumberjackHarvest")],
    "LawnChair": [("resourceCloth", 1, "allHarvest,perkJunkMiner")],
    "CampTent": [("resourceWood", 2, "allHarvest,lumberjackHarvest")],
    "CampLeanTo": [("resourceWood", 3, "allHarvest,lumberjackHarvest")],
    "CampChairs": [("resourceCloth", 2, "allHarvest,perkJunkMiner")],
    "CampFishing": [("resourceScrapIron", 3, "allHarvest,perkJunkMiner")],
}
FEATURE_HP = {"CampTent": 200, "CampLeanTo": 200, "TrailMarker": 150, "Antlers": 20, "BrokenCooler": 100,
              "RustyBucketCans": 100, "OldTire": 200, "FirewoodStack": 250}
# Things you walk through: a hit box for the tool, nothing for movement, bullets or the zombies' paths (the spec's
# solid ones have real colliders in their bundle prefab)
FEATURE_WALK_THROUGH = {"Antlers", "LoneBoot", "BrokenCooler", "RustyBucketCans", "AbandonedPack"}
FEATURE_DESCS.update({
    "DementiveNatureScrapDesc": "Abandoned junk, rusted through. Break it up for scrap iron.",
    "DementiveNatureClothDesc": "Rotting canvas and cloth. Cut it up for cloth.",
    "DementiveNaturePlasticDesc": "Brittle old plastic and rubber. Break it up for polymers.",
    "DementiveNatureLeatherDesc": "Cracked old leather. Salvage what is left.",
    "DementiveNatureCampTentDesc": "A tent camp somebody left behind long ago. Salvage what is left of it.",
    "DementiveNatureCampLeanToDesc": "A collapsed lean-to and its fire ring. Salvage what is left of it.",
    "DementiveNatureCampChairsDesc": "Folding chairs, a cooler and a cold fire. Salvage what is left of them.",
    "DementiveNatureCampFishingDesc": "A fisherman's camp on the bank. Break up the bench for wood.",
    "DementiveNatureTrailMarkerDesc": "A rotting trail marker. Chop it up for wood.",
    "DementiveNatureFirewoodStackDesc": "A collapsed stack of old firewood. Chop it up for wood.",
})
FEATURE_NAME_DESCS = {"CampTent", "CampLeanTo", "CampChairs", "CampFishing", "TrailMarker", "FirewoodStack"}

# Counts per large (8192 m) map: the user asked for a camp of each kind about 12 to 25 times and a single find 20 to
# 50 times, the rarest (bicycle, cart, wheelbarrow) about 20. FEATURE_TARGETS spreads each across biomes the specs
# name; the probabilities are worked out from them (feature_probability), so retuning is changing a count here.
FEATURE_TARGETS = {
    "CampTent": {"pine_forest": 14, "snow": 4},
    "CampLeanTo": {"pine_forest": 8, "burnt_forest": 4, "snow": 3},
    "CampChairs": {"pine_forest": 6, "desert": 4, "wasteland": 5},
    # CampFishing: placed beside real water by the DLL (ShoreDEM.CampChance), not from a biome table
    "TrailMarker": {"pine_forest": 22, "wasteland": 5, "desert": 4, "snow": 4},
    "Antlers": {"pine_forest": 20, "burnt_forest": 8, "snow": 7},
    "LoneBoot": {"pine_forest": 14, "burnt_forest": 8, "wasteland": 10, "desert": 5, "snow": 3},
    "OldTire": {"wasteland": 16, "desert": 10, "pine_forest": 8, "burnt_forest": 6},
    "Wheelbarrow": {"wasteland": 10, "pine_forest": 6, "desert": 4},
    "LawnChair": {"wasteland": 14, "pine_forest": 14, "desert": 7},
    "BrokenCooler": {"wasteland": 18, "burnt_forest": 10, "pine_forest": 7},
    "ShoppingCart": {"wasteland": 14, "pine_forest": 3, "desert": 3},
    "RustyBucketCans": {"wasteland": 18, "burnt_forest": 10, "pine_forest": 12, "desert": 5},
    "FirewoodStack": {"pine_forest": 30},
    "AbandonedPack": {"pine_forest": 18, "wasteland": 10, "burnt_forest": 7},
    "RustedBicycle": {"wasteland": 14, "burnt_forest": 3, "pine_forest": 3},
}
# Rough ground an 8k map gives each biome (cells), and the share of a biome's cells a feature can stand on: the open
# ground (not one of vanilla's tree sub-biomes, about 40% of the pine forest) that is flat (about half). A feature with a
# footprint also loses (r/16) of each axis to the chunk edge (see the placement notes above). These are guesses, so
# the counts are good to a factor of two or so.
MAP_CELLS = {"pine_forest": 24e6, "burnt_forest": 9e6, "desert": 12e6, "snow": 11e6, "wasteland": 11e6}
OPEN_FLAT = 0.2


def feature_probability(name, biome, count, sizes):
    """The decoration probability that puts `count` of feature `name` on a large map's `biome`."""
    cells = sizes[name][0:3:2]
    reach = 0 if max(cells) <= 1 else (max(cells) - 1) // 2 + 1
    accept = OPEN_FLAT * ((16 - reach) / 16.0) ** 2
    return count / (MAP_CELLS[biome] * accept)


def _targets(sizes):
    out = {}
    for name, where in FEATURE_TARGETS.items():
        if name not in sizes:
            continue
        for biome, count in where.items():
            out.setdefault(biome, {"main": {}})["main"][name] = feature_probability(name, biome, count, sizes)
    return out


_merge_placement(_targets(feature_sizes()))

# ---- Ground cover (the 25 PLANTS of the litter, stones, shore, ash, ... kinds): "more ground cover, not clutter". Probabilities
# are per block on flat ground, low enough for a few patches in view at a time: about 1 in 500 blocks of open ground
# (a patch every 20 m or so), and a few times that under the trees, where leaf litter, needles and moss belong. COVER_SCALE
# scales every rate at once. Per biome: "main" over the open ground (also copied into the drift and patch sub-biomes,
# which otherwise take most of the ground from it) and "mix" {vanilla sub-biome noise: {block: prob}} into vanilla's own
# sub-biomes (the pine forest's tree groves). Placed ahead of the grass, like every plant.
COVER_SCALE = 1.0
_GROVE = {"PineNeedleMat": 0.0018, "BirchLeafLitter": 0.0007, "MapleLeafLitter": 0.0006, "OakLeafLitter": 0.0007,
          "MossPatch": 0.0006, "TwigPile": 0.0005, "PineconeCluster": 0.0006, "AcornScatter": 0.0002,
          "LichenStone": 0.0002}
_RING = {n: p * 0.8 for n, p in _GROVE.items()}
COVER = {
    "pine_forest": {
        "main": {"PineNeedleMat": 0.0003, "BirchLeafLitter": 0.0002, "MapleLeafLitter": 0.00015, "OakLeafLitter": 0.00025,
                 "MossPatch": 0.0003, "TwigPile": 0.0002, "PineconeCluster": 0.0002, "AcornScatter": 0.00007,
                 "LichenStone": 0.00012, "PebblesA": 0.00025, "PebblesB": 0.00012, "PebblesC": 0.00012,
                 "FlatStones": 0.00004},
        "mix": {".014, 0, .38": _GROVE, ".014, 0, .46": _RING,
                ".072, 0, .29": {"PineNeedleMat": 0.001, "OakLeafLitter": 0.0006, "BirchLeafLitter": 0.0005,
                                 "MapleLeafLitter": 0.0004, "MossPatch": 0.0008, "TwigPile": 0.0006,
                                 "PineconeCluster": 0.0004, "LichenStone": 0.0002}},
    },
    "burnt_forest": {
        "main": {"AshPatch": 0.0006, "CharredSticks": 0.0008, "PebblesA": 0.0002, "PebblesB": 0.0001,
                 "ShaleChips": 0.00015},
        "mix": dict({noise: {"AshPatch": 0.0015, "CharredSticks": 0.0018} for noise in (".031, 0, .22", ".032, 0, .23", ".04, 0, .4")},
                    **{".033, 0, .3": {"AshPatch": 0.002, "CharredSticks": 0.001}}),
    },
    "desert": {
        "main": {"CrackedMud": 0.0005, "BleachedBranch": 0.00025, "ShaleChips": 0.0003, "PebblesA": 0.0003,
                 "PebblesB": 0.00015, "PebblesC": 0.00015, "DeadTumbleweed": 0.00015},
        "mix": {noise: {"CrackedMud": 0.0004, "BleachedBranch": 0.0002, "ShaleChips": 0.00025, "PebblesA": 0.00025,
                        "PebblesB": 0.0001, "DeadTumbleweed": 0.0001}
                for noise in (".02, 0, .3", ".02, 0, .45", ".03, 0, .3")},
    },
    "snow": {
        "main": {"IceCrust": 0.0003, "FrostHeavedStones": 0.0004, "ShaleChips": 0.0001},
        "mix": {".033, 0, .3": {"IceCrust": 0.0004, "FrostHeavedStones": 0.0005}},
    },
    "wasteland": {
        "main": {"GravelPatch": 0.0005, "RustFlakes": 0.0003, "DeadTumbleweed": 0.0003, "PebblesA": 0.0002,
                 "PebblesB": 0.0001, "ShaleChips": 0.0002, "CrackedMud": 0.0001, "BleachedBranch": 0.0001},
        "mix": {".028, 0, .32": {"GravelPatch": 0.0006, "RustFlakes": 0.0004, "DeadTumbleweed": 0.0003,
                                 "PebblesA": 0.0002, "ShaleChips": 0.0002}},
    },
}


def cover_main(biome_name, sizes):
    """The ground cover's open-ground entries as decoration lines (those the bundle build has measured)."""
    table = COVER.get(biome_name, {}).get("main", {})
    return [deco(p, prob * COVER_SCALE) for p, prob in table.items() if p in sizes]


def extra_ground(biome_name, sizes):
    """What the drift, grove, patch and field sub-biomes copy into their open ground besides vanilla's decorations: the
    ground cover and the camps and single finds (the older solid features keep to the plain open ground)."""
    out = cover_main(biome_name, sizes)
    table = FEATURE_PLACEMENT.get(biome_name, {}).get("main", {})
    built = feature_sizes()
    out += [feature_deco(n, table[n]) for n in NEW_FEATURES if n in table and n in built]
    return out


def cover_lines(biome_name, biome, path, main, sizes):
    """Ground cover into the biome itself and into the vanilla sub-biomes it names."""
    spec = COVER.get(biome_name)
    out = []
    if not spec:
        return out
    entries = cover_main(biome_name, sizes)
    if entries:
        out += insert(path + "/decorations", main, entries)
    for noise, table in spec.get("mix", {}).items():
        sub = biome.find("./subbiome[@noise='%s']" % noise)
        if sub is None:
            raise SystemExit("no sub-biome %s in %s" % (noise, biome_name))
        entries = [deco(p, prob * COVER_SCALE) for p, prob in table.items() if p in sizes]
        if entries:
            out += insert("%s/subbiome[@noise='%s']/decorations" % (path, noise), sub.find("decorations"), entries)
    return out


def feature_block_lines(sizes):
    built = [n for n in FEATURES if n in sizes]
    if not built:
        return []
    lines = ["", "\t\t<!-- Solid natural features: multi-block models like vanilla's boulders (resourceRock01), from",
             "\t\t     Resources/natureexpanded-features.unity3d; their compound colliders are in the model. The DLL",
             "\t\t     (FeatureDEM) tags them so harvesting finds the block and moves the material to the plant shader. -->",
             '\t\t<block name="%sFeatureMaster">' % PREFIX,
             '\t\t\t<property name="CreativeMode" value="None"/>',
             '\t\t\t<property name="Class" value="%s"/>' % FEATURE_CLASS,
             '\t\t\t<property name="Shape" value="ModelEntity"/>',
             '\t\t\t<property name="Model" value="%s%s"/>' % (FEATURE_BUNDLE, built[0]),
             '\t\t\t<property name="Material" value="Mboulder"/>',
             '\t\t\t<property name="DisplayType" value="blockHardenedMulti"/>',
             '\t\t\t<property name="ImposterDontBlock" value="true"/>',
             '\t\t\t<property name="WaterFlow" value="permitted"/>',
             '\t\t\t<property name="OnlySimpleRotations" value="true"/>',
             '\t\t\t<property name="Collide" value="movement,melee,bullet,arrow,rocket"/>',
             '\t\t\t<property name="IsTerrainDecoration" value="true"/>',
             '\t\t\t<property name="StabilitySupport" value="false"/>',
             '\t\t\t<property name="PassThroughDamage" value="true"/>',
             '\t\t\t<property name="DisplayInfo" value="Name"/>',
             '\t\t\t<property name="CustomIcon" value="treeForestGrassDiagonal"/>',
             '\t\t\t<drop event="Destroy" count="0"/>',
             '\t\t\t<property name="FilterTags" value="MC_outdoor,SC_decor"/>',
             '\t\t\t<property name="SortOrder1" value="M206"/>',
             "\t\t</block>"]
    for name in built:
        display, kind = FEATURES[name]
        k = FEATURE_KINDS[kind]
        x, y, z, mx, my, mz = sizes[name]
        count = int(max(k["lo"], min(k["hi"], round(mx * my * mz * 0.5 * k["per_m3"]))))
        count = FEATURE_COUNTS.get(name, count)
        lines += ["", '\t\t<block name="%s">' % block(name),
                  '\t\t\t<property name="Extends" value="%sFeatureMaster"/>' % PREFIX,
                  '\t\t\t<property name="CreativeMode" value="Dev"/>',
                  '\t\t\t<property name="Model" value="%s%s"/>' % (FEATURE_BUNDLE, name),
                  '\t\t\t<property name="DescriptionKey" value="%s"/>'
                  % ("DementiveNature%sDesc" % name if name in FEATURE_NAME_DESCS else k["desc"]),
                  '\t\t\t<property name="Material" value="%s"/>' % k["material"],
                  '\t\t\t<property name="Collide" value="%s"/>' % ("melee" if name in FEATURE_WALK_THROUGH else k["collide"])]
        hp = FEATURE_HP.get(name, k.get("hp"))
        if hp:
            lines.append('\t\t\t<property name="MaxDamage" value="%d"/>' % hp)
        if k.get("loot"):
            lines += ['\t\t\t<property name="Class" value="%s"/>' % k["klass"], '\t\t\t<property class="CompositeFeatures">',
                      '\t\t\t\t<property class="TEFeatureStorage">', '\t\t\t\t\t<property name="LootList" value="%s"/>' % k["loot"],
                      '\t\t\t\t</property>', '\t\t\t</property>']
        if (x, y, z) != (1, 1, 1):
            lines.append('\t\t\t<property name="MultiBlockDim" value="%d,%d,%d"/>' % (x, y, z))
        if max(x, z) > 1:
            # Keeps other big decorations clear of its footprint (the decorator also shifts it to stay in its chunk);
            # the radius is one square number, so a rectangle uses its long side
            lines.append('\t\t\t<property name="BigDecorationRadius" value="%d"/>' % ((max(x, z) - 1) // 2 + 1))
        lines.append('\t\t\t<drop event="Harvest" name="%s" count="%d" tag="%s"/>' % (k["item"], count, k["tag"]))
        for item, extra, tag in FEATURE_EXTRA_DROPS.get(name, ()):
            lines.append('\t\t\t<drop event="Harvest" name="%s" count="%d" tag="%s"/>' % (item, extra, tag))
        lines.append("\t\t</block>")
    return lines


def feature_deco(name, prob):
    text = ("%.8f" % prob).rstrip("0").rstrip(".")
    text = text[1:] if text.startswith("0.") else text
    return '<decoration type="block" blockname="%s" prob="%s" rotatemax="3"/>' % (block(name), text)


def feature_biome_lines(biome_name, biome, path, main, sizes):
    """Entries for the open ground and vanilla sub-biomes, inserted before their ground cover like plants."""
    spec = FEATURE_PLACEMENT.get(biome_name)
    out = []
    if not spec:
        return out
    probs = {n: p for n, p in spec.get("main", {}).items() if n in sizes}
    if probs:
        out += insert(path + "/decorations", main, [feature_deco(n, p) for n, p in probs.items()])
    for noise, table in spec.get("mix", {}).items():
        table = {n: p for n, p in table.items() if n in sizes}
        sub = biome.find("./subbiome[@noise='%s']" % noise)
        if sub is None:
            raise SystemExit("no sub-biome %s in %s" % (noise, biome_name))
        if table:
            out += insert("%s/subbiome[@noise='%s']/decorations" % (path, noise), sub.find("decorations"),
                          [feature_deco(n, p) for n, p in table.items()])
    return out


def feature_field_lines(biome_name, layers, ground, offset, sizes):
    """Field sub-biomes (inside the biome's <append>): patches where features stand denser, over a copy of the open
    ground."""
    out = []
    for i, (freq, (low, high), table) in enumerate(FEATURE_PLACEMENT.get(biome_name, {}).get("fields", [])):
        table = {n: p for n, p in table.items() if n in sizes}
        if not table:
            continue
        off = offset + 40 + i
        out += ["\t\t<!-- Feature field %d -->" % (i + 1),
                '\t\t<subbiome noise="%s, %s, %s" noiseoffset="%d, %d">'
                % (fmt(freq), fmt(low), fmt(high), off * 7 % 90000, off * 13 % 90000),
                "\t\t\t<layers>"]
        for layer in layers:
            out.append("\t\t\t\t" + ET.tostring(layer, encoding="unicode").strip())
        out += ["\t\t\t</layers>", "\t\t\t<decorations>"]
        out += ["\t\t\t\t" + feature_deco(n, p) for n, p in table.items()]
        out += ["\t\t\t\t" + d for d in ground]
        out += ["\t\t\t</decorations>", "\t\t</subbiome>"]
    return out


def feature_localization(sizes):
    return ["%s,blocks,Block,,,,%s%s" % (block(name), csv(display), "," * 13)
            for name, (display, _) in FEATURES.items() if name in sizes]


def write_blocks(sizes):
    lines = ["<configs>", '\t<append xpath="/blocks">',
             "\t\t<!-- Every Nature Expanded plant: a model block placed by world generation (biomes.xml) and harvested",
             "\t\t     like grass. The DLL (PlantDEM) moves its model to the game's plant shader. -->",
             '\t\t<block name="%sPlantMaster">' % PREFIX,
             '\t\t\t<property name="CreativeMode" value="None"/>',
             '\t\t\t<property name="Class" value="%s"/>' % CLASS,
             '\t\t\t<property name="Shape" value="ModelEntity"/>',
             # The game builds the master too and throws without a model, which stops blocks.xml loading.
             '\t\t\t<property name="Model" value="%s%s"/>' % (BUNDLE, next(iter(PLANTS))),
             '\t\t\t<property name="Material" value="Mplants"/>',
             '\t\t\t<property name="ImposterDontBlock" value="true"/>',
             '\t\t\t<property name="LightOpacity" value="0"/>',
             '\t\t\t<property name="WaterFlow" value="permitted"/>',
             '\t\t\t<property name="Collide" value="melee"/>',
             '\t\t\t<property name="IsTerrainDecoration" value="true"/>',
             '\t\t\t<property name="IsDecoration" value="true"/>',
             '\t\t\t<property name="CanDecorateOnSlopes" value="true"/>',
             '\t\t\t<property name="StabilitySupport" value="false"/>',
             '\t\t\t<property name="HarvestOverdamage" value="false"/>',
             '\t\t\t<property name="DisplayInfo" value="Name"/>',
             '\t\t\t<property name="CustomIcon" value="treeForestGrassDiagonal"/>',
             '\t\t\t<property name="VehicleHitScale" value=".1"/>',
             '\t\t\t<drop event="Destroy" count="0"/>',
             '\t\t\t<drop event="Fall" name="resourceYuccaFibers" count="0" prob="1" stick_chance="0"/>',
             '\t\t\t<property name="FilterTags" value="MC_outdoor,SC_decor"/>',
             '\t\t\t<property name="SortOrder1" value="M205"/>',
             "\t\t</block>"]
    missing = []
    for name, (_, kind) in PLANTS.items():
        material, drops, desc = KINDS[kind]
        if name not in sizes:
            missing.append(name)
        h = sizes.get(name, 1)
        ground = kind in GROUND_KINDS
        lines += ["", '\t\t<block name="%s">' % block(name),
                  '\t\t\t<property name="Extends" value="%sPlantMaster"/>' % PREFIX,
                  '\t\t\t<property name="CreativeMode" value="Dev"/>',
                  '\t\t\t<property name="Model" value="%s%s"/>' % (GROUND_BUNDLE if ground else BUNDLE, name),
                  '\t\t\t<property name="DescriptionKey" value="%s"/>' % desc]
        if material != "Mplants":
            lines.append('\t\t\t<property name="Material" value="%s"/>' % material)
        if ground:
            # A flat patch lying on the ground: not on slopes (its uphill edge would bury and its downhill edge float),
            # and picked up by one hit whatever its material's toughness
            lines.append('\t\t\t<property name="CanDecorateOnSlopes" value="false"/>')
            if material != "Mplants":
                lines.append('\t\t\t<property name="MaxDamage" value="1"/>')
        if h > 1:
            lines.append('\t\t\t<property name="MultiBlockDim" value="1,%d,1"/>' % h)
        for item, count in drops:
            lines.append('\t\t\t<drop event="Harvest" name="%s" count="%s" tag="allHarvest"/>'
                         % (item, GROUND_COUNTS.get(name, count)))
        lines.append("\t\t</block>")
    lines += ["", "\t\t<!-- Grasses drawn like vanilla's tall grass, from tiles the DLL (GrassSheetDEM) adds to the game's grass",
              "\t\t     texture sheet (ids in blender/grass/grasses.txt) -->"]
    ids = grass_ids()
    for name in list(GRASSES) + list(RETIRED_GRASSES):
        lines += ['\t\t<block name="%s">' % block("Grass" + name),
                  '\t\t\t<property name="Extends" value="treeGrassMaster" param1="CustomIcon"/>',
                  '\t\t\t<property name="CreativeMode" value="Dev"/>',
                  '\t\t\t<property name="Class" value="Tallgrass"/>',
                  '\t\t\t<property name="Texture" value="%d"/>' % ids[RETIRED_GRASSES.get(name, name)],
                  '\t\t\t<property name="CustomIcon" value="treeTallGrassDiagonal"/>',
                  "\t\t</block>"]
    trees = tree_sizes()
    if trees:
        lines += ["", "\t\t<!-- Trees: like vanilla's (treeMaster), from Resources/natureexpanded-trees.unity3d (SpeedTree",
                  "\t\t     materials built in); the DLL (TreeShaderDEM) links their colliders and feeds them the wind -->"]
    for species, (display, variants) in TREES.items():
        seed = seed_block(species, trees)
        for variant in variants:
            if variant in trees:
                cactus = species in CACTI and CACTUS_CLASS
                lines += (['\t\t<block name="%s">' % block("Tree" + variant),
                           '\t\t\t<property name="Extends" value="%s"/>' % ("treeCactus01" if cactus else "treeMaster"),
                           '\t\t\t<property name="CreativeMode" value="Dev"/>']
                          + tree_lines(variant, trees[variant], seed) + ["\t\t</block>"])
        if seed is None:
            continue
        # The seed and the trees it grows into, as vanilla's oak and pine seeds (treePlantedOak1m and on): the seed is
        # a growing tree block showing its seedling, needing fertile ground (FertileLevel) and growing a stage every
        # 63 in-game minutes (treeMasterGrowing); the grown tree is the wild one, placeable
        _, seedling, stages = SEEDS[species]
        planted = [block("TreePlanted" + v) for v in stages]
        lines += ["", "\t\t<!-- %s seeds, dropped by every %s felled, and the trees they grow into -->" % (species, display),
                  '\t\t<block name="%s">' % seed,
                  '\t\t\t<property name="Extends" value="treeMasterGrowing" param1="CustomIcon"/>',
                  '\t\t\t<property name="CreativeMode" value="Player"/>',
                  '\t\t\t<property name="FallOver" value="false"/>',
                  '\t\t\t<property name="PlaceAsRandomRotation" value="true"/>',
                  '\t\t\t<property class="PlantGrowing">',
                  '\t\t\t\t<property name="Next" value="%s"/>' % planted[0]]
        if species in GROWTH:
            lines.append('\t\t\t\t<property name="GrowthRate" value="%d"/>' % GROWTH[species])
        lines += ["\t\t\t</property>",
                  '\t\t\t<property name="DescriptionKey" value="treePlantedSeed1mDesc"/>',
                  '\t\t\t<property name="Material" value="Mplants"/>',
                  '\t\t\t<property name="Model" value="%s%s"/>' % (TREE_BUNDLE, seedling),
                  '\t\t\t<property name="ModelOffset" value="0,-0.5,0"/>',
                  '\t\t\t<property name="ParticleOnDeath" value="treeGib_sapling"/>',
                  '\t\t\t<property name="Collide" value="melee"/>',
                  '\t\t\t<property name="StabilitySupport" value="false"/>',
                  '\t\t\t<property name="EconomicValue" value="12"/>',
                  '\t\t\t<property name="EconomicBundleSize" value="5"/>',
                  '\t\t\t<property name="SellableToTrader" value="false"/>',
                  '\t\t\t<property name="MaxDamage" value="10"/>',
                  '\t\t\t<property name="ActivationDistance" value="4"/>',
                  "\t\t\t<dropextendsoff/>",
                  '\t\t\t<drop event="Destroy" name="%s" count="1"/>' % seed,
                  '\t\t\t<property name="SortOrder1" value="B904"/>',
                  '\t\t\t<property name="SortOrder2" value="0001"/>',
                  '\t\t\t<property name="Group" value="Resources"/>',
                  '\t\t\t<property name="SoundPickup" value="seeds_cone_grab"/>',
                  '\t\t\t<property name="SoundPlace" value="seeds_cone_place"/>',
                  "\t\t</block>"]
        for i, variant in enumerate(stages):
            last = i == len(stages) - 1
            if last:
                # The grown tree: the wild one (vanilla's last stage extends its wild tree too)
                lines += ['\t\t<block name="%s">' % planted[i],
                          '\t\t\t<property name="Extends" value="%s"/>' % block("Tree" + variant),
                          '\t\t\t<property name="CreativeMode" value="Player"/>',
                          '\t\t\t<property class="PlantGrowing">',
                          '\t\t\t\t<property name="FertileLevel" value="5"/>',
                          "\t\t\t</property>"]
                if variant in FOOTPRINT:
                    # A planted tree stays one column wide, whatever its wild form covers
                    lines += ['\t\t\t<property name="MultiBlockDim" value="1,%d,1"/>' % trees[variant][0],
                              '\t\t\t<property name="BigDecorationRadius" value="3"/>']
            else:
                lines += ['\t\t<block name="%s">' % planted[i],
                          '\t\t\t<property name="Extends" value="treeMasterGrowing"/>',
                          '\t\t\t<property name="CreativeMode" value="Player"/>',
                          '\t\t\t<property class="PlantGrowing">',
                          '\t\t\t\t<property name="Next" value="%s"/>' % planted[i + 1]]
                if species in GROWTH:
                    lines.append('\t\t\t\t<property name="GrowthRate" value="%d"/>' % GROWTH[species])
                # The stage before the grown tree needs richer ground, as vanilla's does
                if i == len(stages) - 2:
                    lines.append('\t\t\t\t<property name="FertileLevel" value="3"/>')
                lines += ["\t\t\t</property>"] + tree_lines(variant, trees[variant], seed, wild=False)
            lines += ['\t\t\t<property name="CustomIcon" value="%s"/>' % seed,
                      '\t\t\t<property name="SortOrder1" value="B904"/>',
                      '\t\t\t<property name="SortOrder2" value="%04d"/>' % (i + 2),
                      "\t\t</block>"]
    lines += feature_block_lines(feature_sizes())
    lines += ["\t</append>", "</configs>", ""]
    with open(os.path.join(MOD, "Config", "blocks.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return missing


def vanilla_biomes():
    return ET.parse(os.path.join(GAME, "Data", "Config", "biomes.xml")).getroot()


def write_biomes():
    root = vanilla_biomes()
    lines = ["<configs>",
             "\t<!-- Wildflower drifts and new plants for every biome, written by Scripts/NatureExpanded/gen_nature.py.",
             "\t     Only chunks generated after install get them. -->"]
    offset = 5000
    for biome_name, spec in BIOMES.items():
        biome = root.find("./biomes/biome[@name='%s']" % biome_name)
        if biome is None:
            raise SystemExit("no vanilla biome " + biome_name)
        path = "/worldgeneration/biomes/biome[@name='%s']" % biome_name
        lines += ["", "\t<!-- ***** %s -->" % biome_name]
        # Thin vanilla's crops where the mix goes
        for noise, probs in spec.get("thin", {}).items():
            for crop, prob in probs.items():
                lines.append("\t<set xpath=\"%s/subbiome[@noise='%s']/decorations/decoration[@blockname='%s']/@prob\">%s</set>"
                             % (path, noise, crop, prob))
        # Mix into vanilla sub-biomes, before their grass
        for noise, plants in spec.get("mix", {}).items():
            sub = biome.find("./subbiome[@noise='%s']" % noise)
            if sub is None:
                raise SystemExit("no sub-biome %s in %s" % (noise, biome_name))
            lines += insert("%s/subbiome[@noise='%s']/decorations" % (path, noise), sub.find("decorations"),
                            [deco(p, prob) for p, prob in plants.items()])
        # Scatter over the biome itself
        main = biome.find("decorations")
        lines += insert(path + "/decorations", main, [deco(p, prob) for p, prob in spec["scatter"].items()])
        # Grasses: the open ground's mix, vanilla's cover thinned, and into vanilla's sub-biomes
        grass = spec.get("grass")
        if grass:
            lines += insert(path + "/decorations", main, [grass_deco(g, prob) for g, prob in grass["main"].items()])
            for cover, prob in grass.get("cover", {}).items():
                lines.append("\t<set xpath=\"%s/decorations/decoration[@blockname='%s']/@prob\">%s</set>" % (path, cover, fmt(prob)))
            for noise, mixed in grass.get("mix", {}).items():
                sub = biome.find("./subbiome[@noise='%s']" % noise)
                if sub is None:
                    raise SystemExit("no sub-biome %s in %s" % (noise, biome_name))
                lines += insert("%s/subbiome[@noise='%s']/decorations" % (path, noise), sub.find("decorations"),
                                [grass_deco(g, prob) for g, prob in mixed.items()])
        # Trees, where the tree build has made them
        built = tree_sizes()
        for where, probs in spec.get("trees", {}).items():
            probs = {v: prob for v, prob in probs.items() if v in built}
            if not probs:
                continue
            entries = [deco("Tree" + v, prob) for v, prob in probs.items()]
            if where == "main":
                lines += insert(path + "/decorations", main, entries)
            else:
                sub = biome.find("./subbiome[@noise='%s']" % where)
                if sub is None:
                    raise SystemExit("no sub-biome %s in %s" % (where, biome_name))
                lines += insert("%s/subbiome[@noise='%s']/decorations" % (path, where), sub.find("decorations"), entries)
        lines += feature_biome_lines(biome_name, biome, path, main, feature_sizes())
        measured = heights()
        lines += cover_lines(biome_name, biome, path, main, measured)
        ground = open_ground(main, grass, extra_ground(biome_name, measured))
        # Two drift sub-biomes per species, core then fringe, on one noise (the game samples it once for both), after
        # vanilla's
        layers = biome.find("layers")
        lines.append('\t<append xpath="%s">' % path)
        for species, companions in spec["drifts"]:
            offset += 1
            low = 0.0
            for i, (high, density, companion) in enumerate(DRIFT_BANDS):
                lines += ["\t\t<!-- Drift: %s (%s) -->" % (PLANTS[species][0], "core" if i == 0 else "fringe"),
                          '\t\t<subbiome noise="%s, %s, %s" noiseoffset="%d, %d">'
                          % (fmt(DRIFT_FREQ), fmt(low), fmt(high), offset * 7 % 90000, offset * 13 % 90000),
                          "\t\t\t<layers>"]
                for layer in layers:
                    lines.append("\t\t\t\t" + ET.tostring(layer, encoding="unicode").strip())
                lines += ["\t\t\t</layers>", "\t\t\t<decorations>", "\t\t\t\t" + deco(species, density)]
                lines += ["\t\t\t\t" + deco(c, companion) for c in companions]
                lines += ["\t\t\t\t" + d for d in ground]
                lines += ["\t\t\t</decorations>", "\t\t</subbiome>"]
                low = high
        # Tree groves (own noise, own offsets, so adding one never moves the grass patches' noise)
        for g, (label, freq, (low, high), probs) in enumerate(spec.get("groves", [])):
            probs = {v: prob for v, prob in probs.items() if v in built}
            if not probs:
                continue
            offset_g = 7000 + g + 100 * list(BIOMES).index(biome_name)
            lines += ["\t\t<!-- Grove: %s -->" % label,
                      '\t\t<subbiome noise="%s, %s, %s" noiseoffset="%d, %d">'
                      % (fmt(freq), fmt(low), fmt(high), offset_g * 7 % 90000, offset_g * 13 % 90000),
                      "\t\t\t<layers>"]
            for layer in layers:
                lines.append("\t\t\t\t" + ET.tostring(layer, encoding="unicode").strip())
            lines += ["\t\t\t</layers>", "\t\t\t<decorations>"]
            lines += ["\t\t\t\t" + deco("Tree" + v, prob) for v, prob in probs.items()]
            lines += ["\t\t\t\t" + d for d in ground]
            lines += ["\t\t\t</decorations>", "\t\t</subbiome>"]
        # Grass patches, after the drifts: a pair on one noise, each a core and a fringe
        for pair in (grass or {}).get("patches", []):
            offset += 1
            scale = grass.get("density", 1.0)
            for i, ((low, high), density) in enumerate(PATCH_BANDS):
                species, companions = pair[0] if i < 2 else pair[1]
                lines += ["\t\t<!-- Grass patch: %s (%s) -->" % (GRASSES[species], "core" if i in (0, 3) else "fringe"),
                          '\t\t<subbiome noise="%s, %s, %s" noiseoffset="%d, %d">'
                          % (fmt(PATCH_FREQ), fmt(low), fmt(high), offset * 7 % 90000, offset * 13 % 90000),
                          "\t\t\t<layers>"]
                for layer in layers:
                    lines.append("\t\t\t\t" + ET.tostring(layer, encoding="unicode").strip())
                share = density / PATCH_BANDS[0][1] * scale
                lines += ["\t\t\t</layers>", "\t\t\t<decorations>", "\t\t\t\t" + grass_deco(species, density * scale)]
                lines += ["\t\t\t\t" + grass_deco(c, p * share) for c, p in companions.items()]
                lines += ["\t\t\t\t" + d for d in ground]
                lines += ["\t\t\t</decorations>", "\t\t</subbiome>"]
        lines += feature_field_lines(biome_name, layers, ground, offset, feature_sizes())
        lines.append("\t</append>")
    lines += ["</configs>", ""]
    text = "\n".join(lines)
    # ElementTree writes ' />'; keep vanilla's '/>'
    text = re.sub(r" />", "/>", text)
    with open(os.path.join(MOD, "Config", "biomes.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def open_ground(main, grass, extra=()):
    """The biome's own decoration list as the drift and patch sub-biomes copy it: vanilla's, without the wild
    crops, with the biome's grass mix where insert() puts it on the open ground (ahead of the first ground cover,
    or at the end), and its cover thinned the same. `extra` (the ground cover) goes in just ahead of the grass."""
    out = []
    mix = list(extra) + ([grass_deco(g, prob) for g, prob in grass["main"].items()] if grass else [])
    cover = next((d.get("blockname") for d in main if float(d.get("prob", "0")) >= 0.3), None)
    for d in main:
        name = d.get("blockname")
        if name in CROPS:
            continue
        if name == cover:
            out += mix
            mix = []
        if grass and name in grass.get("cover", {}):
            d = ET.fromstring(ET.tostring(d))
            d.set("prob", fmt(grass["cover"][name]))
        out.append(ET.tostring(d, encoding="unicode").strip())
    return out + mix


def insert(xpath, decorations, entries):
    """Lines adding decoration entries to a list ahead of its first ground cover (grass or the like at 30% or more,
    which would otherwise win nearly every roll), or at its end when it has none (burnt forest, desert)."""
    cover = next((d.get("blockname") for d in decorations if float(d.get("prob", "0")) >= 0.3), None)
    if cover is None:
        out, close = ['\t<append xpath="%s">' % xpath], "\t</append>"
    else:
        out, close = ["\t<insertBefore xpath=\"%s/decoration[@blockname='%s']\">" % (xpath, cover)], "\t</insertBefore>"
    return out + ["\t\t" + e for e in entries] + [close]


def write_localization():
    header = ("Key,File,Type,UsedInMainMenu,NoTranslate,KeepLoaded,english,Context / Alternate Text,german,spanish,french,"
              "italian,japanese,koreana,polish,brazilian,russian,turkish,schinese,tchinese")
    pad = "," * 13
    rows = [header]
    for name, (display, _) in PLANTS.items():
        rows.append("%s,blocks,Block,,,,%s%s" % (block(name), csv(display), pad))
    for name, display in GRASSES.items():
        rows.append("%s,blocks,Block,,,,%s%s" % (block("Grass" + name), csv(display), pad))
    for name, now in RETIRED_GRASSES.items():
        rows.append("%s,blocks,Block,,,,%s%s" % (block("Grass" + name), csv(GRASSES[now]), pad))
    built = tree_sizes()
    for species, (display, variants) in TREES.items():
        for variant in variants:
            if variant in built:
                rows.append("%s,blocks,Block,,,,%s%s" % (block("Tree" + variant), csv(display), pad))
        seed = seed_block(species, built)
        if seed is not None:
            name, _, stages = SEEDS[species]
            rows.append("%s,blocks,Block,,,,%s%s" % (seed, csv(name), pad))
            for variant in stages:
                rows.append("%s,blocks,Block,,,,%s%s" % (block("TreePlanted" + variant), csv(display), pad))
    rows += feature_localization(feature_sizes())
    for key, text in list(FEATURE_DESCS.items()) + [
        ("DementiveNaturePlantDesc", "A wild plant. Harvest it for plant fibers."),
        ("DementiveNatureMushroomDesc", "Wild mushrooms, good to eat. Harvest them for a bite of food."),
        ("DementiveNatureToadstoolDesc", "Poisonous toadstools. Nothing to eat here."),
        ("DementiveNatureLogDesc", "A fallen log, soft with rot and moss. Chop it for wood."),
        ("DementiveNatureLitterDesc", "Natural ground cover. Nothing here worth taking."),
        ("DementiveNatureStonesDesc", "Loose stones. Pick them up for stone."),
        ("DementiveNatureSticksDesc", "Dry sticks and branches. Pick them up for wood."),
        ("DementiveNatureFibersDesc", "Dry plant matter. Pick it up for plant fibers."),
        ("DementiveNatureScrapBitsDesc", "Rusted scraps of metal. Pick them up for scrap iron."),
    ]:
        rows.append("%s,blocks,Block,,,,%s%s" % (key, csv(text), pad))
    with open(os.path.join(MOD, "Config", "Localization.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows) + "\n")


def csv(text):
    return '"%s"' % text.replace('"', '""') if any(c in text for c in ',"\'') else text


def write_icons():
    """The seeds' icons, from the tree build's folders into the mod's item icons."""
    built = tree_sizes()
    folder = os.path.join(MOD, "UIAtlases", "ItemIconAtlas")
    for species in SEEDS:
        seed = seed_block(species, built)
        src = os.path.join(MOD, "unity", "Assets", "NatureExpanded", "Trees", species, species + "Seed_Icon.png")
        if seed is not None and os.path.exists(src):
            os.makedirs(folder, exist_ok=True)
            shutil.copyfile(src, os.path.join(folder, seed + ".png"))


def main():
    os.makedirs(os.path.join(MOD, "Config"), exist_ok=True)
    missing = write_blocks(heights())
    write_biomes()
    write_localization()
    write_icons()
    write_loot()
    if missing:
        print("No size yet (taken as 1 block tall): " + ", ".join(missing))
    print("Wrote blocks.xml (%d plants, %d grasses), biomes.xml and Localization.csv" % (len(PLANTS), len(GRASSES)))


if __name__ == "__main__":
    main()
