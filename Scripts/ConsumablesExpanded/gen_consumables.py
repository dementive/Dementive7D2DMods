"""Writes ConsumablesExpanded's Config from the tables below.

    python gen_consumables.py <mod dir>

Foods and drinks are realistic and no stronger than vanilla items: most only feed you, and a few carry one of the four
small TAGS. Chems are where the strong effects live, in CHEM_BUFFS, with the C# in the mod's src folder.
Mega Crush, Herbal Painkillers and snowberries aren't generated: they're copied as they are from kept/.
blocks.xml and biomes.xml are hand-written and not touched.
"""
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NL = "\r\n"

# Effects at the strength of the vanilla item named beside each. add/cap follow vanilla's +3 and three-servings pattern.
TAGS = {
    "hot": dict(buff="buffDementiveHot", icon="campfire", seconds=300,  # Blackstrap Coffee
                passives=['<passive_effect name="HypothermalResist" operation="base_add" value="10"/>'],
                display=[("dHypothermalResist", "10", 'title_key="statHypothermalResist"')],
                name="Warmed Up", desc="Something hot in your belly keeps the cold out.\n\nCold Resist +10"),
    "cool": dict(buff="buffDementiveCool", icon="water", seconds=300,  # Yucca Smoothie
                 passives=['<passive_effect name="HyperthermalResist" operation="base_add" value="10"/>'],
                 display=[("dHyperthermalResist", "10", 'title_key="statHyperthermalResist"')],
                 name="Cooled Down", desc="Something cool and juicy helps you handle the heat.\n\nHeat Resist +10"),
    "filling": dict(buff="buffDementiveFilling", icon="stomach", seconds=360,  # Red Tea
                    passives=['<passive_effect name="FoodLossPerStaminaPointGained" operation="perc_add" value="-.15"/>',
                              '<passive_effect name="WaterLossPerStaminaPointGained" operation="perc_add" value="-.15"/>'],
                    display=[("dEfficientDigestion", ".15", 'title_key="statEfficientDigestion" display_type="Percent" display_leading_plus="true"')],
                    name="Full Stomach", desc="A solid meal stays with you. Hard work won't make you hungry and thirsty as quickly.\n\nFood and water cost of recovering stamina -15%"),
    "energy": dict(buff="buffDementiveEnergy", icon="coffee", seconds=180,  # weaker than Coffee
                   passives=['<passive_effect name="StaminaChangeOT" operation="perc_add" value=".15"/>'],
                   display=[("dStaminaRegen", ".15", 'title_key="statStaminaRegen" display_type="Percent"')],
                   name="Energized", desc="Sugar or caffeine gives you a small lift.\n\nStamina Regen +15%"),
}

POT, GRILL, STATION = "pot", "grill", "station"
WATER = ("drinkJarBoiledWater", 1)
FAT = ("resourceAnimalFat", 1)


def food(id, parent, name, desc, f, h, w, s, smell, tag, eco, recipe, skill, stack=10, station=POT):
    return dict(id=id, parent=parent, name=name, desc=desc, food=f, health=h, water=w, stamina=s, smell=smell, tag=tag,
                eco=eco, recipe=recipe, skill=skill, stack=stack, station=station)


# The parent gives the model, sounds and use time, and whether the jar comes back: dishes made with Boiled Water use a
# parent that refunds it, so dishes without any must not.
FOODS = [
    food("DementiveCornHardtack", "foodCornBread", "Corn Hardtack", "Twice-baked cornmeal ration bread. It keeps forever and tastes like it. It has no smell, so it's safe to eat on a run, but you'll want water with it.",
         15, 5, -5, 10, 0, None, 30, [("foodCornMeal", 3), WATER], 4, stack=50),
    food("DementiveSmokedJerky", "foodBaconAndEggs", "Smoked Jerky", "Plain strips of meat dried over a coal fire. It carries well and hardly smells, but it's salty.",
         20, 10, -5, 10, 10, None, 45, [("foodRawMeat", 5), ("resourceCoal", 1)], 8, stack=30, station=GRILL),
    food("DementiveFryBread", "foodBaconAndEggs", "Fry Bread", "Cornmeal dough fried in animal fat. Cheap, filling and easy to make in the first days.",
         15, 7, 0, 15, 25, None, 20, [("foodCornMeal", 2), ("resourceAnimalFat", 2)], 2),

    food("DementiveFriedEgg", "foodBaconAndEggs", "Fried Egg", "One egg in hot fat. The smallest real meal there is.",
         10, 5, 0, 10, 25, None, 30, [("foodEgg", 1), FAT], 2),
    food("DementiveOmlet", "foodBaconAndEggs", "Mushroom Omelet", "Three eggs folded around wild mushrooms.",
         30, 15, 0, 15, 50, None, 60, [("foodEgg", 3), ("foodCropMushrooms", 2), FAT], 10),
    food("DementiveBiscuitsGravy", "foodCornBread", "Biscuits and Gravy", "Diner breakfast: cornmeal biscuits under thick meat gravy. It sits heavy and keeps you going.",
         40, 20, 0, 20, 50, "filling", 90, [("foodCornMeal", 2), ("foodGrilledMeat", 1), FAT, WATER], 18),
    food("DementiveCornGrits", "foodBaconAndEggs", "Prospector's Hash", "Skillet potatoes, corn and meat, the kind of breakfast that gets a long day started.",
         45, 22, 0, 25, 50, "energy", 110, [("foodCropPotato", 3), ("foodCropCorn", 2), ("foodGrilledMeat", 1), FAT], 22),
    food("DementiveCoffeeCake", "foodBaconAndEggs", "Coffee Cake", "Cake with real coffee in it. A small lift and a reminder of better days.",
         40, 20, 0, 20, 25, "energy", 120, [("resourceCropCoffeeBeans", 3), ("foodCornMeal", 2), ("foodEgg", 1), FAT], 27),

    food("DementiveBoneBroth", "foodVegetableStew", "Bone Broth", "Finally a use for all those bones. Boiled for hours, it's good for the sick and the hurt.",
         10, 20, 30, 5, 25, "hot", 40, [("resourceBone", 5), WATER], 6),
    food("DementiveCornChowder", "foodVegetableStew", "Corn Chowder", "Thick corn and potato soup.",
         35, 17, 20, 20, 50, "hot", 100, [("foodCropCorn", 3), ("foodCropPotato", 2), FAT, WATER], 14),
    food("DementivePumpkinSoup", "foodVegetableStew", "Pumpkin Soup", "Pumpkin boiled down with fat and water until it's smooth.",
         35, 17, 20, 15, 25, "hot", 100, [("foodCropPumpkin", 2), FAT, WATER], 18),
    food("DementiveChickenNoodleSoup", "foodVegetableStew", "Chicken Noodle Soup", "Two cans and a pot of water. It tastes like before.",
         45, 35, 25, 20, 50, "hot", 150, [("foodCanChicken", 1), ("foodCanPasta", 1), WATER], 35),

    food("DementiveTamales", "foodFishTacos", "Tamales", "A Southwest staple: meat in cornmeal dough, tied up in yucca and steamed.",
         45, 22, 0, 25, 25, None, 110, [("foodCornMeal", 3), ("foodGrilledMeat", 1), FAT, ("resourceYuccaFibers", 5)], 22),
    food("DementiveCampfireChili", "foodShepardsPie", "Campfire Chili", "Canned chili stretched with real meat and corn. Hot enough to warm you, and you'll want a drink after.",
         55, 28, -5, 30, 50, "hot", 140, [("foodCanChili", 1), ("foodGrilledMeat", 1), ("foodCropCorn", 2)], 27),
    food("DementiveChiliMac", "foodShepardsPie", "Chili Mac", "Two cans in one pot. It tastes better than it should.",
         60, 30, 0, 30, 50, "hot", 170, [("foodCanChili", 1), ("foodCanPasta", 1), FAT], 43),

    food("DementiveSnowberryPie", "foodBlueberryPie", "Snowberry Pie", "Tart cold-country berries under a corn crust.",
         45, 22, 10, 20, 25, "cool", 124, [("foodCropSnowberry", 5), ("foodEgg", 1), ("foodCornMeal", 1), FAT, WATER], 27),
    food("DementiveYuccaPie", "foodBlueberryPie", "Yucca Pie", "Desert fruit pie with a sharp, sweet filling.",
         45, 22, 10, 20, 25, "cool", 124, [("foodCropYuccaFruit", 5), ("foodEgg", 1), ("foodCornMeal", 1), FAT, WATER], 27),
    food("DementiveMushroomPie", "foodBlueberryPie", "Mushroom Pie", "A savory pie of wild mushrooms.",
         45, 22, 0, 20, 25, None, 124, [("foodCropMushrooms", 5), ("foodEgg", 1), ("foodCornMeal", 1), FAT, WATER], 27),
    food("DementiveMeatPie", "foodShepardsPie", "Butcher's Pie", "The big one: three kinds of meat in one crust.",
         104, 52, 0, 40, 50, "filling", 250, [("foodGrilledMeat", 5), ("resourceAnimalFat", 3), ("foodCanChicken", 1), ("foodCanLamb", 1), ("foodCanBeef", 1), ("foodEgg", 1)], 60),
]


def drink(id, parent, name, desc, w, tag, eco, recipe, skill, station=POT, extra_buffs=""):
    return dict(id=id, parent=parent, name=name, desc=desc, water=w, tag=tag, eco=eco, recipe=recipe, skill=skill,
                station=station, extra_buffs=extra_buffs)


DRINKS = [
    drink("DementivePineTea", "drinkJarRedTea", "Pine Needle Tea", "Real survival tea, full of vitamin C, brewed from the seeds and needles of mountain pine.",
          24, "hot", 52, [("treePlantedMountainPine1m", 5), WATER], 6),
    drink("DementiveAcornCoffee", "drinkJarCoffee", "Acorn Coffee", "Roasted acorns stretching your last coffee beans. Weaker than the real thing.",
          24, "energy", 60, [("treePlantedOak1m", 2), ("resourceCropCoffeeBeans", 1), WATER], 6),
    drink("DementiveBerryTea", "drinkJarRedTea", "Berry Tea", "Blueberries steeped in hot water.",
          24, "filling", 52, [("foodCropBlueberries", 5), WATER], 6),
    drink("DementiveAloeJuice", "drinkJarYuccaJuice", "Aloe Juice", "Cool and bitter. Good on a desert day.",
          30, "cool", 60, [("resourceCropAloeLeaf", 2), WATER], 11),
    drink("DementiveBlueberrySoda", "drinkJarYuccaJuice", "Blueberry Soda", "Homemade fizz. The sugar gives you a small lift.",
          34, "energy", 100, [("foodCropBlueberries", 5), ("resourceAcid", 1), WATER], 27),
    drink("DementiveSnowberryGin", "drinkJarBeer", "Snowberry Gin", "Homemade spirit. It warms you up and makes the room lean a little.",
          15, "hot", 100, [("foodCropSnowberry", 5), ("resourceSnowBall", 2), WATER], 27, extra_buffs=",buffDementiveGinSway"),
]

JAM = food("DementiveBlueberryJam", None, "Blueberry Jam", "Eaten straight from the jar. The sugar gives you a small lift.",
           15, 5, 0, 15, 0, "energy", 90, [("foodCropBlueberries", 5), ("foodHoney", 1)], 27)
ALE = dict(id="DementivePumpkinAle", name="Pumpkin Ale", desc="Brewed like beer, with pumpkin in the mash.", eco=110,
           recipe=[("foodCropPumpkin", 1), ("resourceCropHopsFlower", 4), WATER], skill=22)


def chem(id, parent, name, desc, seconds, eco, buff, recipe=None, skill=None, action=None):
    return dict(id=id, parent=parent, name=name, desc=desc, seconds=seconds, eco=eco, buff=buff, recipe=recipe, skill=skill, action=action)


CHEMS = [
    chem("DementiveLongHaul", "drugRecog", "Long Haul", "Truck stop pills. For 60 seconds your stamina never drains. You'll pay for it after.\n\nEnds in a Crash. Taking another chem during a Crash is an Overdose.",
         60, 200, "buffDementiveLongHaul", [("resourceCropCoffeeBeans", 5), ("resourceAcid", 1), WATER], 15),
    chem("DementivePossumPills", "drugRecog", "Possum Pills", "Your heart nearly stops. You collapse for 8 seconds, zombies lose you and wander off, and you're helpless until you can stand.\n\nEnds in a Crash. Taking another chem during a Crash is an Overdose.",
         8, 300, "buffDementivePossum", [("drugPainkillers", 2), ("resourceCropChrysanthemumPlant", 5), ("resourceAcid", 1)], 30),
    chem("DementiveOnMyTab", "drugFortBites", "Put It On My Tab", "For 15 seconds you take no damage at all. When it ends, half of everything you absorbed lands at once, and that can kill you.\n\nEnds in a Crash. Taking another chem during a Crash is an Overdose.",
         15, 400, "buffDementiveOnMyTab", [("drugPainkillers", 2), ("drugSteroids", 1), ("resourceAcid", 1)], 50),
    chem("DementiveNickOfTime", "drugRecog", "Nick of Time", "The whole world slows down for 8 seconds. You slow too, but your aim doesn't. In co-op, where the world can't slow, it gives you speed instead.\n\nEnds in a Crash. Taking another chem during a Crash is an Overdose.",
         8, 500, None, [("drugRecog", 1), ("resourceCropCoffeeBeans", 5), ("resourceAcid", 1)], 75, action="DementiveNickOfTime, ConsumablesExpanded"),
    chem("DementiveDeadMansSwitch", "drugSteroids", "Dead Man's Switch", "Inject it before a dangerous job. For 30 minutes, the next hit that would kill you leaves you at 1 health with 3 seconds of invulnerability instead. Only found, never made.\n\nA Crash follows when it fires. Taking another chem during a Crash is an Overdose.",
         1800, 1500, "buffDementiveDeadMansSwitch"),
]

KEPT_RECIPES = """	<recipe name="plantedSnowberry1" count="1" craft_time="1" tags="learnable,packMuleCrafting">
		<ingredient name="foodCropSnowberry" count="2"/>
	</recipe>

	<recipe name="drugHerbalPainkillers" count="1" craft_area="chemistryStation" tags="learnable,chemStationCrafting">
		<ingredient name="drinkJarBoiledWater" count="1"/>
		<ingredient name="foodCropSnowberry" count="2"/>
		<ingredient name="resourceCropAloeLeaf" count="2"/>
		<ingredient name="resourceCropGoldenrodPlant" count="2"/>
		<ingredient name="resourceCropChrysanthemumPlant" count="2"/>
	</recipe>
"""

LOOT = {
    "groupFoodUncommon": ["DementiveCornHardtack", "DementiveSmokedJerky", "DementiveFryBread"],
    "groupFoodRare": ["DementiveCoffeeCake", "DementiveCornGrits", "DementiveBiscuitsGravy", "DementiveCornChowder", "DementivePumpkinSoup",
                      "DementiveChickenNoodleSoup", "DementiveTamales", "DementiveCampfireChili", "DementiveChiliMac",
                      "DementiveMeatPie", "DementiveMushroomPie", "DementiveYuccaPie", "DementiveSnowberryPie"],
    "groupDrinksUncommon": ["DementiveBerryTea", "DementiveBlueberryJam", "DementiveBlueberrySoda", "DementiveAcornCoffee", "DementivePineTea",
                            "DementiveSnowberryGin", "DementiveAloeJuice"],
    "groupDrinksRare": ["DementiveFruitPunchMegaCrush", "DementiveGrapeMegaCrush", "DementiveGreenAppleMegaCrush", "DementivePumpkinAle"],
}
AIRDROP_DRINKS = LOOT["groupDrinksUncommon"] + LOOT["groupDrinksRare"]

TRADERS = {
    "foodSupplies": [("foodCropSnowberry", "10,20"), ("DementiveCornHardtack", "3,5"), ("DementiveSmokedJerky", "2,4")],
    "preparedFood": [("DementiveFriedEgg", "3,5"), ("DementiveFryBread", "2,3"), ("DementiveOmlet", "2,3")] + [(i, "1,2") for i in LOOT["groupFoodRare"]],
    "groupDrinks": [(i, "1,2") for i in LOOT["groupDrinksUncommon"]],
    "groupDrinksSpecial": [(i, "1,2") for i in LOOT["groupDrinksRare"]],
    "rareMedicine": [("DementiveLongHaul", "1,2"), ("DementivePossumPills", "1,2"), ("DementiveOnMyTab", "1"), ("DementiveNickOfTime", "1"), ("DementiveDeadMansSwitch", "1")],
}

# What each unlock row says in the crafting skill windows
FOOD_LABELS = {2: "Fry Bread & Fried Egg", 4: "Corn Hardtack", 6: "Bone Broth & Field Teas", 8: "Smoked Jerky", 10: "Mushroom Omelet",
               11: "Aloe Juice", 14: "Corn Chowder", 18: "Biscuits and Gravy & Pumpkin Soup", 22: "Hash, Tamales & Pumpkin Ale",
               27: "Pies, Chili, Coffee Cake, Jam, Soda & Gin", 35: "Chicken Noodle Soup", 43: "Chili Mac", 60: "Butcher's Pie"}
MEDICAL_LABELS = {10: "Herbal Painkillers", 15: "Long Haul", 30: "Possum Pills", 50: "Put It On My Tab", 75: "Nick of Time"}
SEED_LABELS = {4: "Snowberry Seeds"}

# The Mega Crush tooltips' labels
STAT_TEXT = [
    ("dem_statJump", "Jump Height"),
    ("dem_statLockpickTime", "Lockpick Time"),
    ("dem_statSearchTime", "Search Time"),
    ("dem_statHarvestOre", "Ore Harvest"),
    ("dem_statHarvestWood", "Wood Harvest"),
    ("dem_statHarvestSalvage", "Salvage Harvest"),
    ("dem_statHarvestMeat", "Meat Harvest"),
]

CRASH_NOTE = "Stamina recovers at half speed and your vision blurs. Taking another chem now is an Overdose."

CHEM_BUFFS = """		<buff name="buffDementiveCrash" name_key="buffDementiveCrash" description_key="buffDementiveCrashDesc" icon="ui_game_symbol_pills" icon_color="255,128,0">
			<stack_type value="replace"/>
			<duration value="120"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="StaminaChangeOT" operation="perc_add" value="-.5"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Blur" intensity=".35" fade="2"/>
				<triggered_effect trigger="onSelfBuffUpdate" action="ModifyScreenEffect" effect_name="Blur" intensity=".35" fade="2"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Blur" intensity="0" fade="2"/>
			</effect_group>
		</buff>

		<buff name="buffDementiveOverdose" name_key="buffDementiveOverdose" description_key="buffDementiveOverdoseDesc" icon="ui_game_symbol_skull" icon_color="255,0,0">
			<stack_type value="ignore"/>
			<duration value="3"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="RunSpeed" operation="perc_set" value="0"/>
				<passive_effect name="WalkSpeed" operation="perc_set" value="0"/>
				<passive_effect name="CrouchSpeed" operation="perc_set" value="0"/>
				<passive_effect name="JumpStrength" operation="perc_set" value="0"/>
				<triggered_effect trigger="onSelfBuffStart" action="Ragdoll" duration="2.5"/>
				<triggered_effect trigger="onSelfBuffStart" action="PlaySound" sound="player#painlg"/>
				<triggered_effect trigger="onSelfBuffStart" action="DementiveOverdose, ConsumablesExpanded"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
			</effect_group>
		</buff>

		<buff name="buffDementiveLongHaul" name_key="DementiveLongHaul" description_key="buffDementiveLongHaulDesc" icon="ui_game_symbol_run">
			<stack_type value="replace"/>
			<duration value="60"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="StaminaLoss" operation="base_set" value="0"/>
				<triggered_effect trigger="onSelfBuffUpdate" action="ModifyStats" stat="Stamina" operation="set" value="500"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
			</effect_group>
		</buff>

		<!-- The cvar is what the C# reads, on the server too: see ChemPossumDEM -->
		<buff name="buffDementivePossum" name_key="DementivePossumPills" description_key="buffDementivePossumDesc" icon="ui_game_symbol_near_death_trauma">
			<stack_type value="replace"/>
			<duration value="8"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="DisableMovement" operation="base_set" value="1"/>
				<passive_effect name="Mobility" operation="base_set" value="0"/>
				<passive_effect name="RunSpeed" operation="perc_set" value="0"/>
				<passive_effect name="WalkSpeed" operation="perc_set" value="0"/>
				<passive_effect name="CrouchSpeed" operation="perc_set" value="0"/>
				<passive_effect name="JumpStrength" operation="perc_set" value="0"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar="%dementivePlayingDead" operation="set" value="1"/>
				<triggered_effect trigger="onSelfBuffStart" action="Ragdoll" duration="7.5"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Greyscale" intensity=".8" fade="1"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Dark" intensity=".5" fade="1"/>
				<triggered_effect trigger="onSelfAttackedOther" action="AddBuff" buff="buffDementiveCrash"/>
				<triggered_effect trigger="onSelfAttackedOther" action="RemoveBuff" buff="buffDementivePossum"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="%dementivePlayingDead" operation="set" value="0"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Greyscale" intensity="0" fade="1"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Dark" intensity="0" fade="1"/>
				<triggered_effect trigger="onSelfLeaveGame" action="RemoveBuff" buff="buffDementivePossum"/>
			</effect_group>
		</buff>

		<!-- The C# absorbs the hits and keeps the bill: see ChemDamageDEM -->
		<buff name="buffDementiveOnMyTab" name_key="DementiveOnMyTab" description_key="buffDementiveOnMyTabDesc" icon="ui_game_symbol_armor_iron">
			<stack_type value="replace"/>
			<duration value="15"/>
			<display_value value="duration"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar="$dementiveTabOwed" operation="set" value="0"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar="%dementiveOnTab" operation="set" value="1"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Greyscale" intensity=".35" fade="1"/>
				<triggered_effect trigger="onSelfBuffFinish" action="DementiveTabBill, ConsumablesExpanded"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="%dementiveOnTab" operation="set" value="0"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Greyscale" intensity="0" fade="1"/>
			</effect_group>
		</buff>

		<buff name="buffDementiveDeadMansSwitch" name_key="DementiveDeadMansSwitch" description_key="buffDementiveDeadMansSwitchDesc" icon="ui_game_symbol_critical">
			<stack_type value="replace"/>
			<duration value="1800"/>
			<display_value value="duration"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar="%dementiveSwitchLoaded" operation="set" value="1"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="%dementiveSwitchLoaded" operation="set" value="0"/>
			</effect_group>
		</buff>

		<buff name="buffDementiveSwitchFired" name_key="buffDementiveSwitchFired" description_key="buffDementiveSwitchFiredDesc" icon="ui_game_symbol_critical" icon_color="255,0,0">
			<stack_type value="replace"/>
			<duration value="3"/>
			<display_value value="duration"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyCVar" cvar="%dementiveShielded" operation="set" value="1"/>
				<triggered_effect trigger="onSelfBuffStart" action="PlaySound" sound="player#painlg"/>
				<triggered_effect trigger="onSelfBuffStart" action="ShowToolbeltMessage" message_key="buffDementiveSwitchFiredMessage"/>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Greyscale" intensity=".6" fade=".2"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="%dementiveShielded" operation="set" value="0"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Greyscale" intensity="0" fade="1"/>
			</effect_group>
		</buff>

		<!-- About 8 real seconds: buff time runs on game time, which is at 35% here. The slowdown itself is in ChemTimeDEM -->
		<buff name="buffDementiveNickSolo" name_key="DementiveNickOfTime" description_key="buffDementiveNickSoloDesc" icon="ui_game_symbol_clock">
			<stack_type value="replace"/>
			<duration value="2.8"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Greyscale" intensity=".5" fade=".2"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Greyscale" intensity="0" fade=".5"/>
			</effect_group>
		</buff>

		<buff name="buffDementiveNickCoop" name_key="DementiveNickOfTime" description_key="buffDementiveNickCoopDesc" icon="ui_game_symbol_clock">
			<stack_type value="replace"/>
			<duration value="8"/>
			<display_value value="duration"/>
			<effect_group>
				<passive_effect name="RunSpeed" operation="perc_add" value=".6"/>
				<passive_effect name="WalkSpeed" operation="perc_add" value=".6"/>
				<passive_effect name="ReloadSpeedMultiplier" operation="perc_add" value=".6"/>
				<triggered_effect trigger="onSelfBuffFinish" action="AddBuff" buff="buffDementiveCrash"/>
			</effect_group>
		</buff>

		<buff name="buffDementiveGinSway" hidden="true">
			<stack_type value="replace"/>
			<duration value="90"/>
			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyScreenEffect" effect_name="Drunk" intensity=".3" fade="4"/>
				<triggered_effect trigger="onSelfBuffUpdate" action="ModifyScreenEffect" effect_name="Drunk" intensity=".3" fade="4"/>
				<triggered_effect trigger="onSelfBuffRemove" action="ModifyScreenEffect" effect_name="Drunk" intensity="0" fade="4"/>
			</effect_group>
		</buff>
"""

BUFF_TEXT = [
    ("buffDementiveCrash", "Crash"),
    ("buffDementiveCrashDesc", "The chem has worn off and your body wants its money back.\n\n" + CRASH_NOTE),
    ("buffDementiveOverdose", "Overdose"),
    ("buffDementiveOverdoseDesc", "Too much, too soon. You collapse and lose half your maximum health."),
    ("buffDementiveLongHaulDesc", "Your stamina never drains. A Crash follows."),
    ("buffDementivePossumDesc", "You're playing dead. Zombies have lost you, and you can't move. A Crash follows."),
    ("buffDementiveOnMyTabDesc", "You take no damage. Half of what you absorb lands when this ends, and a Crash follows."),
    ("buffDementiveDeadMansSwitchDesc", "The next hit that would kill you leaves you at 1 health instead."),
    ("buffDementiveSwitchFired", "Second Chance"),
    ("buffDementiveSwitchFiredDesc", "You can't be hurt for 3 seconds. Get out of there. A Crash follows."),
    ("buffDementiveSwitchFiredMessage", "Dead Man's Switch fired!"),
    ("buffDementiveNickSoloDesc", "The world has slowed down around you. A Crash follows."),
    ("buffDementiveNickCoopDesc", "You move and reload 60% faster. A Crash follows."),
]


def indent(lines, tabs):
    return [("\t" * tabs + l) if l else l for l in lines]


def tag_effects(tag, buffs=""):
    """Effect lines shared by foods and drinks with a tag: the stats shown on the item, the duration, the buff."""
    if not tag:
        return [], "buffProcessConsumables" + buffs
    t = TAGS[tag]
    cvar = f'${t["buff"]}Duration'
    add, cap = t["seconds"] + 3, t["seconds"] * 3 + 3
    lines = [f'<display_value name="{n}" value="{v}"/>' for n, v, _ in t["display"]]
    lines.append(f'<display_value name="dDuration" value="{t["seconds"]}"/>')
    lines.append(f'<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="{cvar}" operation="add" value="{add}"/>')
    lines.append(f'<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="{cvar}" operation="set" value="{cap}">')
    lines.append(f'\t<requirement name="CVarCompare" cvar="{cvar}" operation="GT" value="{cap}"/></triggered_effect>')
    return lines, f'buffProcessConsumables,{t["buff"]}' + buffs


def water_lines(w):
    if w > 0:
        return [f'<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="$waterAmountAdd" operation="add" value="{w}"/>']
    if w < 0:
        return [f'<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyStats" stat="water" operation="add" value="{w}"/>',
                f'<display_value name="$waterAmountAdd" value="{w}"/>']
    return []


def display_type(it, kind):
    water = "Water" if it.get("water") else ""
    if not it.get("tag"):
        return "foodWater" if water else "food"
    return f'dementive{kind}{water if kind == "Food" else ""}{it["tag"].capitalize()}'


def food_group(it):
    fx, buffs = tag_effects(it["tag"])
    lines = [f'<effect_group tiered="false" name="Food">',
             f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="$foodAmountAdd" operation="add" value="{it["food"]}"/>',
             f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="foodHealthAmount" operation="add" value="{it["health"]}"/>',
             f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="foodHealthFarmer" operation="set" value="{it["health"]}">',
             '\t\t<requirement name="HasBuff" buff="buffFarmerSetBonus"/></triggered_effect>']
    lines += ["\t" + l for l in water_lines(it["water"])]
    lines += [f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar=".foodStaminaBonusAdd" operation="add" value="{it["stamina"]}"/>',
              f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="foodStaminaFarmer" operation="set" value="{it["stamina"]}">',
              '\t\t<requirement name="HasBuff" buff="buffFarmerSetBonus"/></triggered_effect>']
    lines += ["\t" + l for l in fx]
    lines += [f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="AddBuff" buff="{buffs}"/>',
              f'\t<display_value name="dSmellUse" value="{it["smell"]}"/>',
              "</effect_group>"]
    return lines


FIRE_GROUP = ['<effect_group tiered="false">',
              '\t<requirement name="HasBuff" buff="buffIsOnFire"/>',
              '\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="AddBuff" buff="buffExtinguishFire"/>',
              "</effect_group>"]


def drink_group(it):
    fx, buffs = tag_effects(it["tag"], it["extra_buffs"])
    return (['<effect_group tiered="false" name="Drink">', '\t<requirement name="!HasBuff" buff="buffIsOnFire"/>']
            + ["\t" + l for l in water_lines(it["water"])] + ["\t" + l for l in fx]
            + [f'\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="AddBuff" buff="{buffs}"/>', "</effect_group>"] + FIRE_GROUP)


def item_head(id, parent, display, eco, stack=None):
    lines = [f'<item name="{id}">']
    if parent:
        lines.append(f'\t<property name="Extends" value="{parent}"/>')
    lines += [f'\t<property name="CustomIcon" value="{id}"/>',
              f'\t<property name="DescriptionKey" value="{id}Desc"/>',
              f'\t<property name="DisplayType" value="{display}"/>',
              f'\t<property name="EconomicValue" value="{eco}"/>']
    if stack:
        lines.append(f'\t<property name="Stacknumber" value="{stack}"/>')
    return lines


def food_item(it):
    lines = item_head(it["id"], it["parent"], display_type(it, "Food"), it["eco"], it["stack"])
    lines += ['\t<property name="UnlockedBy" value="craftingFood"/>',
              '\t<property class="Action0">',
              f'\t\t<property name="SmellUse" value="{it["smell"]}"/>',
              "\t</property>"]
    lines += ["\t" + l for l in food_group(it)]
    return lines + ["</item>"]


def jam_item(it):
    lines = item_head(it["id"], None, display_type(it, "Food"), it["eco"], it["stack"])
    lines += ['\t<property name="Tags" value="food,foodSkill,fitness,farmerFoodBonus"/>',
              '\t<property name="HoldType" value="3"/>',
              '\t<property name="Meshfile" value="@:Other/Items/Food/masonJarHoneyTeaPrefab.prefab"/>',
              '\t<property name="DropMeshfile" value="@:Other/Items/Misc/sack_droppedPrefab.prefab"/>',
              '\t<property name="Material" value="Mglass"/>',
              '\t<property name="UnlockedBy" value="craftingFood"/>',
              '\t<property name="Group" value="Food/Cooking,CFFood/Cooking"/>',
              '\t<property class="Action0">',
              '\t\t<property name="Class" value="Eat"/>',
              '\t\t<property name="Delay" value="1.0"/>',
              '\t\t<property name="Sound_start" value="player_eating"/>',
              f'\t\t<property name="SmellUse" value="{it["smell"]}"/>',
              "\t</property>"]
    lines += ["\t" + l for l in food_group(it)]
    return lines + ["</item>"]


def drink_item(it):
    lines = item_head(it["id"], it["parent"], display_type(it, "Drink"), it["eco"])
    lines.append('\t<property name="UnlockedBy" value="craftingFood"/>')
    lines += ["\t" + l for l in drink_group(it)]
    return lines + ["</item>"]


def ale_item(it):
    """The same effect as vanilla's beer, so it also shares vanilla's buff and its duration cvar."""
    lines = item_head(it["id"], "drinkJarBeer", "waterBeer", it["eco"])
    lines += ['\t<effect_group tiered="false" name="Drink">',
              '\t\t<requirement name="!HasBuff" buff="buffIsOnFire"/>',
              '\t\t<display_value name="dStaminaRegen" value=".4"/>',
              '\t\t<display_value name="dEntityDamageBrawling" value="3"/>',
              '\t\t<display_value name="dStunResist" value="1"/>',
              '\t\t<display_value name="dDuration" value="60"/>',
              '\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="$buffBeerDuration" operation="add" value="63"/>',
              '\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="ModifyCVar" cvar="$buffBeerDuration" operation="set" value="183">',
              '\t\t\t<requirement name="CVarCompare" cvar="$buffBeerDuration" operation="GT" value="183"/></triggered_effect>',
              '\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="AddBuff" buff="buffBeer"/>',
              "\t</effect_group>"]
    lines += ["\t" + l for l in FIRE_GROUP]
    return lines + ["</item>"]


def chem_item(it):
    lines = item_head(it["id"], it["parent"], "dementiveChem", it["eco"])
    if it["recipe"]:
        lines.append('\t<property name="UnlockedBy" value="craftingMedical"/>')
    dose = (f'<triggered_effect trigger="onSelfPrimaryActionEnd" action="{it["action"]}"/>' if it["action"]
            else f'<triggered_effect trigger="onSelfPrimaryActionEnd" action="AddBuff" buff="{it["buff"]}"/>')
    lines += ['\t<effect_group tiered="false" name="Dose">',
              '\t\t<requirement name="!HasBuff" buff="buffDementiveCrash"/>',
              f'\t\t{dose}',
              "\t</effect_group>",
              '\t<effect_group tiered="false" name="Overdose">',
              '\t\t<requirement name="HasBuff" buff="buffDementiveCrash"/>',
              '\t\t<triggered_effect trigger="onSelfPrimaryActionEnd" action="AddBuff" buff="buffDementiveOverdose"/>',
              "\t</effect_group>",
              f'\t<effect_group tiered="false" name="Display">',
              f'\t\t<display_value name="dDuration" value="{it["seconds"]}"/>',
              "\t</effect_group>",
              "</item>"]
    return lines


def tag_buff(t):
    b = t["buff"]
    cvar, disp = f"${b}Duration", f".{b}Display"
    lines = [f'<buff name="{b}" name_key="{b}" description_key="{b}Desc" icon="ui_game_symbol_{t["icon"]}">',
             '\t<stack_type value="replace"/>',
             '\t<duration value="0"/>',
             f'\t<display_value value="{disp}"/>',
             '\t<display_value_format value="time"/>',
             "",
             "\t<effect_group>",
             f'\t\t<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar="{cvar}" operation="subtract" value="@$MetabolismDuration"/>',
             f'\t\t<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar="{disp}" operation="set" value="@{cvar}"/>',
             f'\t\t<triggered_effect trigger="onSelfBuffUpdate" action="ModifyCVar" cvar="{disp}" operation="divide" value="@$MetabolismDuration"/>',
             "\t</effect_group>",
             "",
             "\t<effect_group>",
             f'\t\t<triggered_effect trigger="onSelfBuffUpdate" action="RemoveBuff" buff="{b}">',
             f'\t\t\t<requirement name="CVarCompare" cvar="{cvar}" operation="LTE" value="0"/>',
             "\t\t</triggered_effect>",
             f'\t\t<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="{disp}" operation="set" value="0"/>',
             f'\t\t<triggered_effect trigger="onSelfBuffRemove" action="ModifyCVar" cvar="{cvar}" operation="set" value="0"/>',
             "\t</effect_group>",
             "",
             "\t<effect_group>"]
    lines += ["\t\t" + p for p in t["passives"]]
    return lines + ["\t</effect_group>", "</buff>"]


def display_types(all_items):
    out, seen = [], set()
    for it, kind in all_items:
        if not it.get("tag"):
            continue
        name = display_type(it, kind)
        if name in seen:
            continue
        seen.add(name)
        lines = [f'<item_display_info display_type="{name}" display_group="groupConsumables">']
        if kind == "Food":
            lines.append('\t<display_entry name="$foodAmountAdd" title_key="statFoodAmount"/>')
        if it.get("water"):
            lines.append('\t<display_entry name="$waterAmountAdd" title_key="statWaterAmount"/>')
        if kind == "Food":
            lines += ['\t<display_entry name="foodHealthAmount" title_key="statHealthAmount"/>',
                      '\t<display_entry name=".foodStaminaBonusAdd" title_key="statFoodStaminaBonus"/>']
        lines += [f'\t<display_entry name="{n}" {attrs}/>' for n, _, attrs in TAGS[it["tag"]]["display"]]
        lines.append('\t<display_entry name="dDuration" title_key="statDuration" display_type="Time"/>')
        if kind == "Food":
            lines.append('\t<display_entry name="dSmellUse" title_key="statFoodSmell"/>')
        out += lines + ["</item_display_info>"]
    out += ['<item_display_info display_type="dementiveChem" display_group="groupConsumables">',
            '\t<display_entry name="dDuration" title_key="statDuration" display_type="Time"/>',
            "</item_display_info>"]
    return out


def recipe(id, ingredients, station):
    attrs = {POT: 'craft_area="campfire" craft_tool="toolCookingPot" tags="perkMasterChef,learnable,cookingPotFood"',
             GRILL: 'craft_area="campfire" craft_tool="toolCookingGrill" tags="perkMasterChef,learnable,grill"',
             STATION: 'craft_area="chemistryStation" tags="perkMasterChef,learnable,chemStationCrafting"',
             "chem": 'craft_area="chemistryStation" tags="learnable,chemStationCrafting"'}[station]
    lines = [f'<recipe name="{id}" count="1" {attrs}>']
    lines += [f'\t<ingredient name="{n}" count="{c}"/>' for n, c in ingredients]
    return lines + ["</recipe>"]


def skill_block(skill, prefix, levels):
    out = [f"<append xpath=\"/progression/crafting_skills/crafting_skill[@name='{skill}']\">"]
    for level in sorted(levels):
        items = levels[level]
        out.append(f'\t<display_entry icon="{",".join(items)}" name_key="{prefix}{level}" has_quality="false" unlock_level="{level}">')
        out += [f'\t\t<unlock_entry item="{i}" unlock_tier="1"/>' for i in items]
        out.append("\t</display_entry>")
    out.append("\t<effect_group>")
    for level in sorted(levels):
        out += [f'\t\t<passive_effect name="RecipeTagUnlocked" operation="base_set" level="{level},100" value="1" tags="{i}"/>' for i in levels[level]]
    return out + ["\t</effect_group>", "</append>"]


def write(path, lines):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(NL.join(lines).replace("\r\n", "\n").replace("\n", NL) + NL)


def kept(name):
    with open(os.path.join(HERE, "kept", name), encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").rstrip("\n")


def main():
    config = os.path.join(sys.argv[1], "Config")

    items = ["<Dementive>", '\t<append xpath="/items">', "\t\t<!-- Foods -->", ""]
    for it in FOODS:
        items += indent(food_item(it), 2) + [""]
    items += indent(jam_item(JAM), 2) + ["", "\t\t<!-- Drinks -->", ""]
    for it in DRINKS:
        items += indent(drink_item(it), 2) + [""]
    items += indent(ale_item(ALE), 2) + ["", "\t\t<!-- Chems -->", ""]
    for it in CHEMS:
        items += indent(chem_item(it), 2) + [""]
    items += ["\t\t<!-- Mega Crush, Herbal Painkillers and snowberries: copied from kept/ -->", "", kept("items.xml"), "\t</append>", "",
              "\t" + kept("item_patches.xml").lstrip(), "", "</Dementive>"]
    write(os.path.join(config, "items.xml"), items)

    buffs = ["<Dementive>", '\t<append xpath="/buffs">']
    for t in TAGS.values():
        buffs += indent(tag_buff(t), 2) + [""]
    buffs += [CHEM_BUFFS.rstrip("\n"), "", kept("buffs.xml"), "\t</append>", "",
              "\t<!-- Fall damage takes health straight down, so it never reaches the C# that blocks every other hit -->",
              "\t<set xpath=\"/buffs/buff[@name='buffPlayerFallingDamage']/effect_group/triggered_effect[@action='ModifyStats' and @stat='Health']/requirement[@name='!HasBuff']/@buff\">"
              "buffDrugOhShitzDrops,buffTwitchDontBreakLeg,buffDontBreakMyLeg,god,buffDementiveOnMyTab,buffDementiveSwitchFired</set>",
              "</Dementive>"]
    write(os.path.join(config, "buffs.xml"), buffs)

    every = [(it, "Food") for it in FOODS + [JAM]] + [(it, "Drink") for it in DRINKS]
    write(os.path.join(config, "ui_display.xml"),
          ["<Dementive>", '\t<append xpath="ui_display_info/item_display">', kept("ui_display.xml")] + indent(display_types(every), 2) + ["\t</append>", "</Dementive>"])

    recipes = ["<Dementive>", '<append xpath="/recipes">', ""]
    for it in FOODS + [JAM] + DRINKS:
        recipes += indent(recipe(it["id"], it["recipe"], it["station"]), 1) + [""]
    recipes += indent(recipe(ALE["id"], ALE["recipe"], STATION), 1) + [""]
    for it in CHEMS:
        if it["recipe"]:
            recipes += indent(recipe(it["id"], it["recipe"], "chem"), 1) + [""]
    recipes += [KEPT_RECIPES.rstrip("\n"), "", "</append>", "</Dementive>"]
    write(os.path.join(config, "recipes.xml"), recipes)

    food_levels = {}
    for it in FOODS + [JAM] + DRINKS + [ALE]:
        food_levels.setdefault(it["skill"], []).append(it["id"])
    medical_levels = {10: ["drugHerbalPainkillers"]}
    for it in CHEMS:
        if it["skill"]:
            medical_levels.setdefault(it["skill"], []).append(it["id"])
    progression = ["<Dementive>"] + indent(skill_block("craftingFood", "dem_food", food_levels), 1) + [""]
    progression += indent(skill_block("craftingSeeds", "dem_seeds", {4: ["plantedSnowberry1"]}), 1) + [""]
    progression += indent(skill_block("craftingMedical", "dem_medical", medical_levels), 1) + ["</Dementive>"]
    write(os.path.join(config, "progression.xml"), progression)

    loot = ["<Dementive>"]
    for group, names in LOOT.items():
        loot.append(f"\t<append xpath=\"/lootcontainers/lootgroup[@name='{group}']\">")
        loot += [f'\t\t<item name="{n}"/>' for n in names]
        loot.append("\t</append>")
    for group in ("airdropdrink", "twitch_drink"):
        loot.append(f"\t<append xpath=\"/lootcontainers/lootgroup[@name='{group}']\">")
        loot += [f'\t\t<item name="{n}"/>' for n in AIRDROP_DRINKS]
        loot.append("\t</append>")
    loot.append("\t<append xpath=\"/lootcontainers/lootgroup[@name='groupMedicalRare']\">")
    loot += [f'\t\t<item name="{n}"/>' for n in ("DementiveLongHaul", "DementivePossumPills", "DementiveOnMyTab", "DementiveNickOfTime")]
    loot.append('\t\t<item name="DementiveDeadMansSwitch" prob=".25"/>')
    loot += ["\t</append>", "</Dementive>"]
    write(os.path.join(config, "loot.xml"), loot)

    traders = ["<Dementive>"]
    for group, names in TRADERS.items():
        traders.append(f"\t<append xpath=\"/traders/trader_item_groups/trader_item_group[@name='{group}']\">")
        traders += [f'\t\t<item name="{n}" count="{c}"/>' for n, c in names]
        traders.append("\t</append>")
    write(os.path.join(config, "traders.xml"), traders + ["</Dementive>"])

    with open(os.path.join(HERE, "kept", "Localization.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.reader(io.StringIO(f.read().replace("\r\n", "\n"))))
    width = len(rows[0])

    def row(key, file, kind, text):
        rows.append(([key, file, kind, "", "", "", text.replace("\n", "\\n")] + [""] * width)[:width])

    for it in FOODS + [JAM] + DRINKS + [ALE]:
        row(it["id"], "items", "Food", it["name"])
        row(it["id"] + "Desc", "items", "Food", it["desc"])
    for it in CHEMS:
        row(it["id"], "items", "Medical", it["name"])
        row(it["id"] + "Desc", "items", "Medical", it["desc"])
    for t in TAGS.values():
        row(t["buff"], "buffs", "Buff", t["name"])
        row(t["buff"] + "Desc", "buffs", "Buff", t["desc"])
    for key, text in BUFF_TEXT:
        row(key, "buffs", "Buff", text)
    for prefix, labels in (("dem_food", FOOD_LABELS), ("dem_medical", MEDICAL_LABELS), ("dem_seeds", SEED_LABELS)):
        for level, text in labels.items():
            row(f"{prefix}{level}", "progression", "Attribute", text)
    for key, text in STAT_TEXT:
        row(key, "ui_display", "Item stat", text)
    out = io.StringIO()
    csv.writer(out, lineterminator=NL).writerows(rows)
    with open(os.path.join(config, "Localization.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(out.getvalue())


if __name__ == "__main__":
    main()
