"""Build WeaponsExpanded-SERVERSIDE/Config from WeaponsExpanded/Config.

Usage: python gen_serverside.py <game dir> <WeaponsExpanded dir> <WeaponsExpanded-SERVERSIDE dir>
Server-side-only clients don't have the mod's UIAtlases, so each weapon uses its vanilla parent's icon with a
color tint (TINTS below) instead of its custom icon. Every other config file is copied unchanged.
"""
import os
import re
import shutil
import sys

game, main, server = sys.argv[1:4]
van = open(os.path.join(game, "Data", "Config", "items.xml"), encoding="utf-8").read()
van_items = {m.group(1): m.group(0) for m in re.finditer(r'\n<item name="(\w+)">.*?\n</item>', van, re.S)}

# Tints from the last hand-made server-side version (commit 9a85f31); anything else gets the default orange
TINTS = {
    "DementiveDesertRedeemer": "#FB58F5", "DementivegunHandgunT2Magnum44": "#FE9B2F", "DementivegunHandgunT3SMG5": "#F2E3A9",
    "DementivegunMGT1AK47": "#FA5959", "DementivegunMGT2TacticalAR": "#FAAD59", "DementivegunMGT3M60": "#F68081",
    "DementivegunRifleT1HuntingRifle": "#FE2E2E", "DementivegunRifleT2LeverActionRifle": "#DE0001",
    "DementivegunRifleT3SniperRifle": "#FFBE01", "DementivegunShotgunT1DoubleBarrel": "#F6D258",
    "DementivegunShotgunT2PumpShotgun": "#FFFE01", "DementivegunShotgunT3AutoShotgun": "#A4DE00",
    "DementivemeleeToolAxeT1IronFireaxe": "#58FA58", "DementivemeleeToolAxeT2SteelAxe": "#F5A8A8",
    "DementivemeleeToolAxeT3Chainsaw": "#B40505", "DementivemeleeWpnBatonT2StunBaton": "#F2F681",
    "DementivemeleeWpnClubT3SteelClub": "#8A4A09", "DementivemeleeWpnKnucklesT3SteelKnuckles": "#F7FF2F",
    "DementivemeleeWpnSledgeT3SteelSledgehammer": "#D6DF00", "DementivemeleeWpnSpearT3SteelSpear": "#AFB405",
    # 2026 weapons: the theme colors their custom icons were recolored with
    "DementivemeleeWpnBladeStalkersHarvester": "#C21F1F", "DementivemeleeWpnClubGrandSlam": "#2E6BFF",
    "DementivemeleeWpnSledgeBloodletter": "#8B0000", "DementivegunBowHellfire": "#FF5A00", "DementivegunBowWhisper": "#8A2BE2",
    "DementivegunRifleChainReaction": "#FFD000", "DementivegunShotgunFrostbite": "#7FDBFF", "DementivemeleeToolPickProspector": "#FFC125",
    "DementivegunMGRampage": "#E0115F", "DementivegunHandgunLuckySeven": "#2ECC40",
    "DementivegunBowOldFaithful": "#FFB030", "DementivemeleeWpnClubPersuader": "#FFCC00",
    "DementivemeleeWpnBatonLeadPipeLarry": "#FF6A10", "DementivemeleeWpnSledgeCaveman": "#FF8C1A",
    "DementivemeleeWpnBladeFemur": "#A00000", "DementivemeleeWpnKnucklesBarFight": "#B0202A",
    "DementivemeleeWpnKnucklesBrassTacks": "#D4A017", "DementivemeleeWpnSpearFirstBlood": "#D00000",
    "DementivemeleeWpnSpearPigSticker": "#E0507A",
}
DEFAULT_TINT = "#DE7501"

def vanilla_icon(name):
    item = name
    while item:
        icon = re.search(r'<property name="CustomIcon" value="(\w+)"', van_items[item])
        if icon:
            return icon.group(1)
        ext = re.search(r'<property name="Extends" value="(\w+)"', van_items[item])
        item = ext.group(1) if ext else None
    return name

def swap_icon(m):
    body = m.group(0)
    parent = re.search(r'<property name="Extends" value="(\w+)"', body).group(1)
    icon = vanilla_icon(parent)
    if not os.path.exists(os.path.join(game, "Data", "ItemIcons", icon + ".png")):
        raise SystemExit(f"{m.group(1)}: no vanilla icon {icon}")
    return re.sub(r'([ \t]*)<property name="CustomIcon" value="\w+"/>',
                  lambda p: f'{p.group(1)}<property name="CustomIcon" value="{icon}"/>\r\n{p.group(1)}<property name="CustomIconTint" value="{TINTS.get(m.group(1), DEFAULT_TINT)}"/>',
                  body, count=1)

cfg_main, cfg_server = os.path.join(main, "Config"), os.path.join(server, "Config")
items = open(os.path.join(cfg_main, "items.xml"), encoding="utf-8", newline="").read()
items, n = re.subn(r'<item name="(\w+)">.*?</item>', swap_icon, items, flags=re.S)
open(os.path.join(cfg_server, "items.xml"), "w", encoding="utf-8", newline="").write(items)
print(f"items.xml: {n} items use tinted vanilla icons")
for f in os.listdir(cfg_main):
    if f != "items.xml":
        shutil.copyfile(os.path.join(cfg_main, f), os.path.join(cfg_server, f))
        print("copied", f)
