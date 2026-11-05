"""Paint the ConsumablesExpanded icons from vanilla icons.

Usage: python make_icons.py <game dir> <ConsumablesExpanded dir> [icon ...]
Each icon is a chain of IconTool.exe fx effects (ops listed at the top of IconTool.cs) run on a vanilla icon from
Data/ItemIcons, so the lighting matches the game's own art: new dishes are built from parts of vanilla ones, with
vanilla ingredients laid beside them. PARTS are pieces several icons share, painted first into a temp folder; "@name"
stands for a part, as a base icon or in an "over:" op. Writes UIAtlases/ItemIconAtlas/<icon>.png; pass icon names to
redo only those. DementiveCornGrits (Prospector's Hash) is an older icon that already fits, so it isn't painted here.
"""
import os
import shutil
import subprocess
import sys
import tempfile

game, mod = sys.argv[1:3]
only = sys.argv[3:]
icon_tool = os.path.join(os.path.dirname(__file__), "..", "bin", "IconTool.exe")
CLEAR = "erase:box=-9/-9/170/170"

# The insides of the vanilla bowls, as selections
STEEL_POT = "ell=78/74/49/25"
TEAL_BOWL = "ell=80/70/59/34"
BROWN_BOWL = "ell=80/74/59/41"
BLACK_BOWL = "ell=79/71/58/32"
# The top and the cut face of vanilla's pie wedge
WEDGE_TOP = "poly=22/108/64/42/122/76"
WEDGE_SIDE = "poly=22/109/122/77/128/98/24/126"
# Mega Crush: the flavor band at the foot of the can, where vanilla's says LIMEADE
CAN_BAND = "poly=31/117/71/138/63/149/25/128"


def noodles(*spots):
    """Egg noodles for a soup: a wavy glyph at each x,y,rotation, over its own shadow."""
    ops = []
    for x, y, rot in spots:
        ops.append(f"text:~~,{x + 1},{y + 2},30,#8a5a14,bold=1,font=Arial,rot={rot},{BLACK_BOWL}")
        ops.append(f"text:~~,{x},{y},30,#fff0b8,bold=1,font=Arial,rot={rot},{BLACK_BOWL}")
    return ops


def mega_crush(hue, band, ink, flavor, sparkle):
    return ("drinkCanMegaCrush", [
        hue, "fill:" + band + ",grain=0.02,soft=1," + CAN_BAND, "text:" + flavor + ",47,133,11," + ink + ",bold=1,font=Arial,rot=29",
        "sparkle:" + sparkle + ",2,9,5"])


# part: (vanilla icon or @part, effects)
PARTS = {
    # A square of hardtack cut from the top of the cornbread
    "tack": ("foodCornBread", [
        "erase:poly=32/46/100/40/124/76/52/88,invert=1", "place:80,80,1.75,sy=1.1", "map:#6a4a22,#c8a468,#f0dcae",
        "blur:1", "pattern:dimples,c1=#4a3218,scale=19,size=0.2,angle=0,op=0.8,shade=0.4",
        "pattern:speckle,c1=#7a5428,scale=3,amount=0.6,op=0.5,seed=3"]),
    "tack_side": ("@tack", ["map:#2a1a0a,#6a4a26,#9a7240"]),
    # One tamale: the vanilla tied bundle narrowed and tapered, wrapped in corn husk with a twine tie
    "tamale": ("foodRawMeatBundle", [
        "place:80,80,1,sx=0.62,sy=1.1", "fill:#d6c074,grain=0.03,box=0/0/160/160",
        "pattern:woodgrain,c1=#e6d690,c2=#9c8640,scale=8,angle=90,op=0.6",
        "map:#3a2c10,#7a6630,#a8924a,0.9,zone=0/-0.1/0.3", "map:#3a2c10,#7a6630,#a8924a,0.9,zone=0/0.7/0.9",
        "erase:ell=80/80/31/66,invert=1,soft=2",
        "fill:#5c4a22,grain=0.04,soft=1,poly=40/40/120/40/120/45/40/45", "fill:#5c4a22,grain=0.04,soft=1,poly=40/115/120/115/120/120/40/120"]),
    "tamale_shadow": ("@tamale", ["fill:#000000,grain=0,box=-9/-9/170/170"]),
    # Vanilla's spaghetti in pale egg noodle colors
    "noodles": ("foodSpaghetti", ["map:#a87c2a,#ecca7c,#fff4c4"]),
    # The chicken and corn out of vanilla's black stew
    "stew_chicken": ("foodAshChickenStew", [
        "erase:poly=46/70/60/60/70/52/98/47/104/58/100/66/112/72/112/84/120/84/120/96/90/98/78/96/44/98/42/90/56/80,invert=1,soft=2",
        "erase:lsel=0/0.13,soft=1", "adjust:bright=1.3,sat=1.05"]),
    # Blueberries repainted as pale snowberries
    "snowberries": ("foodCropBlueberries", ["map:#6a7c98,#d4e0f0,#ffffff", "pattern:speckle,c1=#ffffff,scale=4,amount=0.55,op=0.6,seed=2"]),
    # The coffee beans out of the vanilla grounds
    "beans": ("resourceCropCoffeeBeans", ["erase:ell=80/98/40/18,invert=1,soft=3", "place:80,80,1.9"]),
    # A round biscuit cut from the crust of the loaf
    "biscuit": ("foodPumpkinBread", ["erase:ell=76/72/56/46,invert=1,soft=2", "map:#5a3410,#c8863a,#f8dea8"]),
    # The gravy off vanilla's toast, turned to white pepper gravy
    "gravy": ("foodTunaFishGravyToast", [
        "erase:ell=80/68/44/34,invert=1,soft=5", "erase:hsel=25/70/0.3",
        "map:#a8987c,#e4d6bc,#fff9ec", "blur:2", "pattern:speckle,c1=#3a2c20,scale=2.5,amount=0.64,op=0.7,seed=6",
        "pattern:speckle,c1=#8a5a36,scale=7,amount=0.66,op=0.8,seed=9"]),
    # A half moon of egg, from the domed top of the loaf
    "omelet": ("foodPumpkinBread", [
        "place:80,82,1.22", "map:#8e5a0e,#efc23e,#fff3ac", "blur:1.5",
        "erase:ell=80/64/72/60,invert=1,soft=2", "erase:box=-9/-9/170/66,soft=2",
        "pattern:speckle,c1=#a8641c,scale=8,amount=0.6,op=0.65,seed=3",
        "pattern:speckle,c1=#3f6a22,scale=3,amount=0.66,op=0.8,seed=5"]),
}

# icon: (vanilla icon or @part, effects)
ICONS = {
    # ---- Field food ----
    # Two square crackers, stacked
    "DementiveCornHardtack": ("foodCornBread", [
        CLEAR, "over:@tack_side,6,34,132,rot=-8", "over:@tack,6,26,132,rot=-8",
        "over:@tack_side,26,12,120,rot=9", "over:@tack,26,5,120,rot=9"]),
    # Dark, peppery strips with the paper taken away
    "DementiveSmokedJerky": ("foodRoadrunnerChickenJerky", [
        "erase:poly=18/72/48/55/78/30/86/32/106/38/125/44/140/55/140/66/106/118/92/114/62/108/42/104/26/96,invert=1,soft=2",
        "erase:hsel=15/60/0/0.5,lsel=0.34/1", "erase:lsel=0.62/1", "place:80,80,1.26", "adjust:sat=1.1,bright=1.06,contrast=1.1", "sheen:0.3",
        "fill:#cdbb92,grain=0.05,shade=0.6,soft=1,poly=40/66/43/62/126/118/123/122"]),
    # A blistered round of dough, fried gold, on the shape of the vanilla tart
    "DementiveFryBread": ("foodBlueberryPie", [
        "over:foodCornBread,-30,-10,220,ell=80/78/66/34,soft=4", "map:#6a3408,#d88e24,#ffe29a", "blur:1.5",
        "pattern:speckle,c1=#7e3e0c,scale=11,amount=0.6,op=0.6,seed=4", "pattern:speckle,c1=#fff0c0,scale=6,amount=0.66,op=0.45,seed=2"]),

    # ---- Breakfast ----
    # One vanilla fried egg, on its own
    "DementiveFriedEgg": ("foodBaconAndEggs", ["erase:ell=122/36/37/26,invert=1", "place:80,80,1.9"]),
    # A folded omelet with mushrooms spilling out of it
    "DementiveOmlet": ("foodPumpkinBread", [
        CLEAR, "over:foodCropMushrooms,22,26,72,rot=-20", "over:foodCropMushrooms,76,22,64,rot=16,flip=1",
        "over:@omelet,2,6,156,rot=-8"]),
    # Two biscuits under white pepper gravy
    "DementiveBiscuitsGravy": ("foodPumpkinBread", [
        CLEAR, "over:@biscuit,-8,22,116", "over:@biscuit,50,34,116", "over:@gravy,6,6,148"]),
    # A loaf under a crumb topping, with beans beside it
    "DementiveCoffeeCake": ("foodPumpkinBread", [
        "map:#3a1e0a,#a8682c,#e8bc84", "pattern:speckle,c1=#f4d8a8,c2=#000000,scale=5,amount=0.5,op=0.95,seed=8,zone=60/0.42/0.56",
        "pattern:speckle,c1=#6a3a14,scale=4,amount=0.56,op=0.8,seed=3,zone=60/0.42/0.56",
        "over:@beans,62,64,104"]),

    # ---- Soups: a different bowl for each ----
    # Clear amber broth in the steel pot, with a bone in it
    "DementiveBoneBroth": ("foodVegetableStew", [
        "blur:6," + STEEL_POT, "map:#4a2408,#b06e1c,#f0c060," + STEEL_POT,
        "pattern:speckle,c1=#ffe6a0,scale=7,amount=0.6,op=0.7,seed=4," + STEEL_POT,
        "over:resourceBone,66,4,88,rot=8"]),
    # Thick cream soup in the teal bowl, full of corn
    "DementiveCornChowder": ("foodShamChowder", [
        "blur:2.5," + TEAL_BOWL, "map:#a07c30,#ecd28a,#fff6d4," + TEAL_BOWL,
        "pattern:speckle,c1=#ffbe14,scale=5,amount=0.57,op=1,seed=6,shade=0.6," + TEAL_BOWL,
        "over:foodCornOnTheCob,84,86,74,rot=6"]),
    # Smooth orange soup in the brown bowl, with a pumpkin beside it
    "DementivePumpkinSoup": ("foodGumboStew", [
        "blur:6," + BROWN_BOWL, "map:#8a3206,#ee8420,#ffd488," + BROWN_BOWL,
        "pattern:speckle,c1=#fff0d0,scale=6,amount=0.66,op=0.5,seed=7," + BROWN_BOWL,
        "over:plantedPumpkin3Harvest,100,92,58"]),
    # Gold broth in the black bowl around vanilla's chicken, with noodles through it
    "DementiveChickenNoodleSoup": ("foodAshChickenStew", [
        "fill:#d09a30,grain=0.02," + BLACK_BOWL,
        "over:@noodles,16,36,126,height=72,src=44/100/116/122," + BLACK_BOWL,
        *noodles((40, 64, -18), (46, 82, 14), (114, 58, 12), (120, 74, -14), (90, 48, 6), (62, 50, -8), (104, 90, 8)),
        "over:@stew_chicken,0,0,160"]),

    # ---- Main dishes ----
    # Three corn husk bundles, tied
    "DementiveTamales": ("foodRawMeatBundle", [
        CLEAR, "over:@tamale,48,-16,132,rot=-35", "over:@tamale_shadow,-14,44,132,rot=-35,op=0.5", "over:@tamale,-18,40,132,rot=-35",
        "over:@tamale_shadow,17,17,132,rot=-35,op=0.6", "over:@tamale,13,13,132,rot=-35"]),
    # A sooty pot of dark red chili with a wedge of cornbread, still on the coals
    "DementiveCampfireChili": ("foodHoboStew", [
        "hue:345,40,-4,sat=1.1,val=0.72," + STEEL_POT, "pattern:speckle,c1=#2a0a04,scale=5,amount=0.56,op=0.8,seed=3," + STEEL_POT,
        "map:#0c0b0a,#3a3734,#8c8882,0.85,zone=90/-0.34/0.72", "over:foodCornBread,94,84,62,rot=-14",
        "embers:#ff7a1a,7,1.5,3,box=20/118/120/150"]),
    # Vanilla's plate of spaghetti, turned cheesy orange and smothered in chili
    "DementiveChiliMac": ("foodSpaghetti", [
        "hue:0,30,-4,sat=1.15,val=0.6,ell=80/72/45/40", "hue:20,70,-8,sat=1.8,val=1.14,ell=80/72/45/40,invert=1",
        "pattern:speckle,c1=#1e0a04,scale=4,amount=0.56,op=0.8,seed=6,ell=80/72/45/40"]),

    # ---- Pies: a different shape for each ----
    # The whole tart under pale berries and frost
    "DementiveSnowberryPie": ("foodBlueberryPie", [
        "hue:195,300,0,sat=0.3,val=1.5", "pattern:speckle,c1=#f4faff,scale=3,amount=0.58,op=0.85,seed=2,ell=80/76/66/32",
        "over:@snowberries,36,26,62", "over:@snowberries,76,36,50,rot=40", "sparkle:#ffffff,3,8,4"]),
    # A cream-topped wedge with a sharp green filling and the fruit beside it
    "DementiveYuccaPie": ("foodPumpkinCheesecake", [
        "hue:25,60,26,sat=1.0,val=0.96", "over:foodCropYuccaFruit,82,76,76,rot=12"]),
    # A golden wedge with a dark mushroom filling, and a mushroom beside it
    "DementiveMushroomPie": ("foodPumpkinPie", [
        "map:#6a3a10,#c98c3a,#f4d492," + WEDGE_TOP, "map:#20120a,#5e3c22,#9a7450," + WEDGE_SIDE,
        "pattern:speckle,c1=#d8c0a0,scale=6,amount=0.58,op=0.9,seed=4," + WEDGE_SIDE, "over:foodCropMushrooms,88,86,66"]),
    # The whole pie under a golden lid, with a wedge cut out to show the meat
    "DementiveMeatPie": ("foodBlueberryPie", [
        "over:foodPumpkinBread,-10,-6,190,ell=80/74/66/32,soft=3", "map:#6a3a10,#c98c3a,#f4d492,ell=80/74/66/34",
        "over:foodShepardsPie,0,0,160,src=50/70/120/120,poly=80/78/132/56/146/84/122/104,soft=1",
        "fill:#5a3210,poly=52/68/78/60/79/63/53/71,soft=1", "fill:#5a3210,poly=44/84/70/78/71/81/45/87,soft=1",
        "fill:#5a3210,poly=70/52/94/48/95/51/71/55,soft=1"]),

    # ---- Drinks ----
    # Vanilla's tea jar with the goldenrod turned brown behind a pine cone
    "DementivePineTea": ("drinkJarGoldenRodTea", [
        "hue:40,110,-14,sat=0.9", "hue:30,70,-6,sat=0.5,val=0.5,box=88/122/160/160", "hue:30,70,-6,sat=0.5,val=0.5,box=60/138/160/160",
        "over:treePlantedMountainPine1m,72,82,80"]),
    "DementiveAcornCoffee": ("drinkJarCoffee", ["map:#120804,#4a2a14,#a8784c,box=46/44/110/132", "over:treePlantedOak1m,82,84,74"]),
    "DementiveBerryTea": ("drinkJarRedTea", ["hue:5,60,300,sat=0.72,val=0.8", "over:foodCropBlueberries,88,92,66"]),
    "DementiveAloeJuice": ("drinkJarYuccaJuice", ["hue:140,200,-46,sat=0.7,val=1.05", "over:resourceCropAloeLeaf,82,74,74"]),
    # A float: foam over dark blue fizz
    "DementiveBlueberrySoda": ("foodFrostbiteSmoothie", [
        "map:#10103a,#3a3aa8,#a0a8f0,zone=90/-0.68/0.74", "map:#6a6aa0,#c4c0ec,#ffffff,zone=90/0.68/0.74",
        "pattern:speckle,c1=#d8e0ff,scale=3.5,amount=0.68,op=0.9,seed=6,shade=0,zone=90/-0.66/0.7", "over:foodCropBlueberries,88,94,64"]),
    # Vanilla's honey jar full of jam, with berries over the comb
    "DementiveBlueberryJam": ("foodHoney", ["hue:20,70,240,sat=0.85,val=0.66", "over:foodCropBlueberries,78,86,76"]),
    # Vanilla's bottle with a new label
    "DementiveSnowberryGin": ("drinkJarGrandpasAwesomeSauce", [
        "hue:10,60,170,sat=0.5,val=1.2", "fill:#e4e6da,grain=0.02,poly=57/60/103/60/103/128/57/128,soft=1",
        "text:SNOWBERRY,80,74,10,#23384c,bold=1,font=Arial Narrow", "text:GIN,80,92,20,#23384c,bold=1", "text:small batch,80,112,8,#5a6c7c,italic=1",
        "over:@snowberries,88,104,50"]),
    # Vanilla's beer glass, darker and orange, with a pumpkin over the hops
    "DementivePumpkinAle": ("drinkJarBeer", ["hue:25,55,-10,sat=1.15,val=0.9", "hue:60,130,-50,sat=0.8,val=0.7", "over:plantedPumpkin3Harvest,86,88,66"]),
    "DementiveGrapeMegaCrush": mega_crush("hue:45,170,195,sat=1,val=0.92", "#2e1248", "#ffd84a", "GRAPE", "#e8c8ff"),
    "DementiveGreenAppleMegaCrush": mega_crush("hue:45,170,-20,sat=1.1,val=1.05", "#22420e", "#f4ff9a", "APPLE", "#f4ffc0"),
    "DementiveFruitPunchMegaCrush": mega_crush("hue:45,170,-90,sat=1.05,val=0.95", "#4a0e0c", "#ffe08a", "PUNCH", "#ffd0c0"),

    # ---- Chems ----
    # Time slipping: a gold capsule with afterimages
    "DementiveNickOfTime": ("drugAntibiotics", ["place:96,76,0.78", "map:#3a2a08,#c89a2a,#ffe9a8,0.9", "sheen:0.2", "trail:#ffd28a,20,5,8,0.6", "sparkle:#fff4d0,2,10,3"]),
    # Vanilla's apothecary bottle, relabeled
    "DementivePossumPills": ("drugRecog", [
        "hue:15,50,-25,sat=0.9,val=0.8", "fill:#d9c79a,grain=0.03,box=50/74/110/124",
        "text:POSSUM,80,84,13,#2a1c12,bold=1", "text:PILLS,80,98,13,#2a1c12,bold=1", "text:play dead,80,113,9,#6b1a14"]),
    # Vanilla's mint tin with a new red lid and a cream label
    "DementiveOnMyTab": ("drugFortBites", [
        "hue:35,70,-48,sat=1.15,val=0.85", "fill:#b23a2c,grain=0.02,shade=0.3,soft=2,poly=6/44/12/38/88/4/98/5/141/44/141/52/62/109/50/110/6/52",
        "fill:#efe0b4,grain=0.02,soft=1.5,poly=22/50/92/17/122/46/54/84",
        "text:PUT IT ON MY,67,39,9,#7a1e16,bold=1,rot=-26", "text:TAB,75,56,25,#7a1e16,bold=1,rot=-26",
        "text:feel it later,95,74,9,#f2e2b4,italic=1,rot=-32"]),
    # A red dose in vanilla's syringe
    "DementiveDeadMansSwitch": ("drugSteroids", ["hue:25,75,-48,sat=1.5,val=0.95", "glow:#b01818,10,0.5", "sparkle:#ffd0c0,3,9,4"]),
    # Truck stop orange tablets, stamped and on the move
    "DementiveLongHaul": ("drugPainkillers", [
        "place:92,80,0.84", "map:#4a1c06,#d9681e,#ffd9a0,0.9", "sheen:0.3", "text:LH,108,84,16,#8a3a0c,bold=1,font=Arial,rot=-18", "trail:#ff9a40,0,3,8,0.4"]),
    # Pressed herbal tablets with an aloe leaf
    "drugHerbalPainkillers": ("drugPainkillers", [
        "map:#2c3a1c,#7f9a4a,#e4ecc8,0.85", "pattern:speckle,c1=#3f5a22,c2=#2c3a1c,op=0.6,scale=4,amount=0.56,seed=2",
        "over:resourceCropAloeLeaf,96,80,60,rot=10"]),
}

icons_dir = os.path.join(game, "Data", "ItemIcons")
atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
parts_dir = tempfile.mkdtemp()


def source(name):
    if name.startswith("@"):
        return os.path.join(parts_dir, name[1:] + ".png")
    return os.path.join(icons_dir, name + ".png")


def part_path(op):
    name, rest = op[len("over:@"):].split(",", 1)
    return "over:" + source("@" + name) + "," + rest


def paint(base, out, ops):
    ops = [part_path(op) if op.startswith("over:@") else op for op in ops]
    subprocess.run([icon_tool, "fx", source(base), out, *ops], check=True)


try:
    for name, (base, ops) in PARTS.items():
        paint(base, os.path.join(parts_dir, name + ".png"), ops)
    for name, (base, ops) in ICONS.items():
        if only and name not in only:
            continue
        paint(base, os.path.join(atlas, name + ".png"), ops)
        print("painted", name)
finally:
    shutil.rmtree(parts_dir, ignore_errors=True)
