"""Paint the icons of the WeaponsExpanded signature weapons (the 10 added in 2026) from their vanilla icons.

Usage: python make_icons.py <game dir> <WeaponsExpanded dir> [weapon ...]
Each weapon gets a chain of IconTool.exe fx effects (ops listed at the top of IconTool.cs) that matches its ability,
in the style of the hand-made icons of the original 30 weapons, which this script doesn't touch. Writes
UIAtlases/ItemIconAtlas/<weapon>.png; pass weapon names to redo only those. The server-side copy keeps using the
vanilla icons with a tint (gen_serverside.py).
"""
import os
import subprocess
import sys

game, mod = sys.argv[1:3]
only = sys.argv[3:]
icon_tool = os.path.join(os.path.dirname(__file__), "..", "bin", "IconTool.exe")
GOLD = "map:#2a1800,#d4a017,#fff4c0"

# weapon: (vanilla icon, effects)
ICONS = {
    # 25% bleed chance, more harvest, sneak attacks: a bloodied blade
    "DementivemeleeWpnBladeStalkersHarvester": ("meleeWpnBladeT1HuntingKnife", [
        "map:#0a0a0c,#4a4a52,#d8d8e0", "sheen:0.6", "pattern:splatter,c1=#7a0000,scale=7,amount=0.5,seed=2,shade=0.6,zone=45/0.45/0.55",
        "rim:#ff1a1a,2,0.5", "glow:#8a0000,6,0.6"]),
    # Power attacks send zombies flying: a polished bat with blue grip tape, mid-swing
    "DementivemeleeWpnClubGrandSlam": ("meleeWpnClubT1BaseballBat", [
        "pattern:woodgrain,c1=#e8c08a,c2=#9a6a3a,scale=5,angle=45,op=0.8", "sheen:0.5", "map:#05123a,#1f5bff,#cfe0ff,zone=45/-0.35/0.42",
        "trail:#7fb0ff,135,4,7,0.6", "sparkle:#ffffff,2,12,3"]),
    # Hits heal you: dark iron soaked in blood, with glowing veins in the head
    "DementivemeleeWpnSledgeBloodletter": ("meleeWpnSledgeT1IronSledgehammer", [
        "map:#0a0505,#3a2a2a,#b0a0a0", "pattern:splatter,c1=#6a0000,scale=8,amount=0.55,seed=5,shade=0.6",
        "pattern:cracks,c1=#ff1010,scale=14,width=0.06,op=1,bloom=0.8,seed=3,zone=45/0.55/0.65", "glow:#b00000,7,0.7"]),
    # Sets targets on fire: a burning bow
    "DementivegunBowHellfire": ("gunBowT1WoodenBow", [
        "map:#1a0500,#8a2a0a,#ffb070", "pattern:flames,c1=#ffe94d,c2=#ff3a00,c3=#140000,reach=0.5,count=6,seed=4,shade=0.4",
        "glow:#ff5000,8,0.9", "embers:#ff8a1a,14,1.8,6"]),
    # Sneak attacks: a matte black crossbow in a purple haze
    "DementivegunBowWhisper": ("gunBowT1IronCrossbow", [
        "map:#030308,#2a1a45,#a890d0", "sheen:0.3", "glow:#8a2be2,10,0.9,noise=10", "rim:#c8a8ff,2,0.6"]),
    # Kills explode: hazard stripes on the barrel, glowing hot, throwing sparks
    "DementivegunRifleChainReaction": ("gunRifleT0PipeRifle", [
        "map:#1a0a00,#a85a10,#ffd08a", "pattern:hazard,c1=#ffcc00,c2=#111111,scale=8,op=0.95,zone=45/0.55/0.6/0.75/0.8",
        "emissive:#ffb000,0.7,0.8", "glow:#ff7a00,6,0.6", "embers:#ffb030,12,1.8,7"]),
    # Hits slow enemies: frozen over, with frost cracks and a cold haze
    "DementivegunShotgunFrostbite": ("gunShotgunT0PipeShotgun", [
        "map:#03101c,#4aa8e0,#f0faff", "pattern:cracks,c1=#e8fbff,scale=9,width=0.05,op=0.8,bloom=0.4,seed=8",
        "glow:#9fe8ff,8,0.8,noise=12", "rim:#e8fbff,2,0.6", "sparkle:#ffffff,4,10,2"]),
    # More ore: solid gold with gold flecks
    "DementivemeleeToolPickProspector": ("meleeToolPickT2SteelPickaxe", [
        GOLD, "sheen:0.8", "pattern:speckle,c1=#fff4b0,scale=5,amount=0.7,op=0.6,seed=4", "glow:#ffcc33,5,0.4", "sparkle:#fffbe0,4,11,8"]),
    # Kill streaks: red hot, molten and moving
    "DementivegunMGRampage": ("gunMGT0PipeMachineGun", [
        "map:#050000,#3a0505,#c04040", "pattern:flames,c1=#ffd04d,c2=#ff0a0a,c3=#100000,reach=0.6,count=7,seed=6,shade=0.4",
        "pattern:cracks,c1=#ff3b00,scale=16,op=0.9,bloom=0.8,width=0.06,seed=9", "glow:#ff1a1a,7,0.7", "trail:#ff2020,45,3,7,0.5"]),
    # 7% lucky shots: gold with a green glow and glints
    "DementivegunHandgunLuckySeven": ("gunHandgunT0PipePistol", [
        GOLD, "sheen:0.7", "rim:#2ecc40,2,0.7", "glow:#2ecc40,7,0.7", "sparkle:#ffffff,5,10,7", "embers:#7dff8a,10,1.4,9"]),
}

atlas = os.path.join(mod, "UIAtlases", "ItemIconAtlas")
for name, (vanilla, ops) in ICONS.items():
    if only and name not in only:
        continue
    src = os.path.join(game, "Data", "ItemIcons", vanilla + ".png")
    subprocess.run([icon_tool, "fx", src, os.path.join(atlas, name + ".png"), *ops], check=True)
    print("painted", name)
