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
}
# Each species' gibs when felled, by height [(up to metres, particle)], as vanilla's trees of its biome: winter
# pines burst snow, burnt pines ash, the desert's juniper dust; the rest vanilla's dead tree's
GIBS = {
    "SubalpineFir": [(8, "treeGib_winter_small"), (16, "treeGib_winter01"), (24, "treeGib_winter02"),
                     (99, "treeGib_winter03")],
    "CharredSnag": [(8, "treeGib_burnt_small"), (99, "treeGib_burnt_55m")],
    "JoshuaTree": [(99, "treeGib_small_dust")],
}
# Burnt trees give coal too, both to a wood axe and to whatever harvests coal (vanilla's burnt pines: 11 to 22 of
# each from a 20 m tree), and, having no seed of their own, vanilla's mountain pine seed as its burnt pines do
COAL = {"CharredSnag": [(8, "3,6"), (99, "6,12")]}
FOREIGN_SEEDS = {"CharredSnag": "treePlantedMountainPine1m"}

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
}

# kind: (material, harvest drops [(item, count)], description key)
KINDS = {
    "flower": ("Mplants", [("resourceYuccaFibers", "2")], "DementiveNaturePlantDesc"),
    "bush": ("Mplants", [("resourceYuccaFibers", "4")], "DementiveNaturePlantDesc"),
    "cactus": ("Mcactus", [("resourceYuccaFibers", "3")], "DementiveNaturePlantDesc"),
    "mushroom": ("Mmushrooms", [("foodCropMushrooms", "1")], "DementiveNatureMushroomDesc"),
    "toadstool": ("Mmushrooms", [("resourceYuccaFibers", "1")], "DementiveNatureToadstoolDesc"),
    "log": ("MtreeWoodSmall", [("resourceWood", "8")], "DementiveNatureLogDesc"),
}

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


def tree_lines(variant, size, seed):
    """A tree block's model, size, gibs, wood (and coal) and seed drops, wild or planted; `size` its (blocks, metres)
    tall."""
    blocks, metres = size
    species = next(sp for sp in TREES if variant.startswith(sp))
    gib = by_height(GIBS.get(species, ()), metres, "treeGib_dead_01")
    seed = seed or FOREIGN_SEEDS.get(species)
    # Wood and toughness by size, like vanilla's (30, 70, 110 wood for small, medium and large trees)
    material, wood = ("MtreeWoodSmall", 30) if metres < 11 else ("MtreeWoodMedium", 60) if metres < 17 else ("MtreeWoodLarge", 90)
    out = ['\t\t\t<property name="Model" value="%s%s"/>' % (TREE_BUNDLE, variant),
           '\t\t\t<property name="ModelOffset" value="0,-0.5,0"/>',
           '\t\t\t<property name="MultiBlockDim" value="1,%d,1"/>' % blocks,
           '\t\t\t<property name="Material" value="%s"/>' % material,
           '\t\t\t<property name="Path" value="solid"/>',
           '\t\t\t<property name="BigDecorationRadius" value="3"/>',
           '\t\t\t<property name="ParticleOnDeath" value="%s"/>' % gib,
           '\t\t\t<drop event="Harvest" name="resourceWood" count="%d" tag="oreWoodHarvest,lumberjackHarvest"/>' % wood]
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
        lines += ["", '\t\t<block name="%s">' % block(name),
                  '\t\t\t<property name="Extends" value="%sPlantMaster"/>' % PREFIX,
                  '\t\t\t<property name="CreativeMode" value="Dev"/>',
                  '\t\t\t<property name="Model" value="%s%s"/>' % (BUNDLE, name),
                  '\t\t\t<property name="DescriptionKey" value="%s"/>' % desc]
        if material != "Mplants":
            lines.append('\t\t\t<property name="Material" value="%s"/>' % material)
        if h > 1:
            lines.append('\t\t\t<property name="MultiBlockDim" value="1,%d,1"/>' % h)
        for item, count in drops:
            lines.append('\t\t\t<drop event="Harvest" name="%s" count="%s" tag="allHarvest"/>' % (item, count))
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
                lines += (['\t\t<block name="%s">' % block("Tree" + variant),
                           '\t\t\t<property name="Extends" value="treeMaster"/>',
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
                  '\t\t\t\t<property name="Next" value="%s"/>' % planted[0],
                  "\t\t\t</property>",
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
            else:
                lines += ['\t\t<block name="%s">' % planted[i],
                          '\t\t\t<property name="Extends" value="treeMasterGrowing"/>',
                          '\t\t\t<property name="CreativeMode" value="Player"/>',
                          '\t\t\t<property class="PlantGrowing">',
                          '\t\t\t\t<property name="Next" value="%s"/>' % planted[i + 1]]
                # The stage before the grown tree needs richer ground, as vanilla's does
                if i == len(stages) - 2:
                    lines.append('\t\t\t\t<property name="FertileLevel" value="3"/>')
                lines += ["\t\t\t</property>"] + tree_lines(variant, trees[variant], seed)
            lines += ['\t\t\t<property name="CustomIcon" value="%s"/>' % seed,
                      '\t\t\t<property name="SortOrder1" value="B904"/>',
                      '\t\t\t<property name="SortOrder2" value="%04d"/>' % (i + 2),
                      "\t\t</block>"]
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
        ground = open_ground(main, grass)
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
        lines.append("\t</append>")
    lines += ["</configs>", ""]
    text = "\n".join(lines)
    # ElementTree writes ' />'; keep vanilla's '/>'
    text = re.sub(r" />", "/>", text)
    with open(os.path.join(MOD, "Config", "biomes.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def open_ground(main, grass):
    """The biome's own decoration list as the drift and patch sub-biomes copy it: vanilla's, without the wild
    crops, with the biome's grass mix where insert() puts it on the open ground (ahead of the first ground cover,
    or at the end), and its cover thinned the same."""
    out = []
    mix = [grass_deco(g, prob) for g, prob in grass["main"].items()] if grass else []
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
    for key, text in [
        ("DementiveNaturePlantDesc", "A wild plant. Harvest it for plant fibers."),
        ("DementiveNatureMushroomDesc", "Wild mushrooms, good to eat. Harvest them for a bite of food."),
        ("DementiveNatureToadstoolDesc", "Poisonous toadstools. Nothing to eat here."),
        ("DementiveNatureLogDesc", "A fallen log, soft with rot and moss. Chop it for wood."),
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
    if missing:
        print("No size yet (taken as 1 block tall): " + ", ".join(missing))
    print("Wrote blocks.xml (%d plants, %d grasses), biomes.xml and Localization.csv" % (len(PLANTS), len(GRASSES)))


if __name__ == "__main__":
    main()
