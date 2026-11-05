# Consumables Expanded

More real food for the world of 7 Days to Die, and a line of chems that can save your life or end it.

Foods and drinks are dishes you could actually make in Navezgane, from vanilla ingredients and farmable snowberries. They're balanced against vanilla food: most just feed you, and a few have one small effect no stronger than a vanilla item that already does the same thing. Chems are where the strong effects are.

Has a DLL and new icons, so it has to be installed on the server and on every client.

## What food does

| Tag | Effect | Same strength as |
|---|---|---|
| Hot | +10 cold resistance for 5 minutes | Blackstrap Coffee |
| Cooling | +10 heat resistance for 5 minutes | Yucca Smoothie |
| Filling | Stamina use costs 15% less food and water for 6 minutes | Red Tea |
| Energy | +15% stamina recovery for 3 minutes | Weaker than Coffee (+20%) |

Every dish also has a Smell Distance, like vanilla food. Field food has little or no smell and stacks high, but it makes you thirsty.

## Foods

| Food | Food | Health | Water | Stamina | Smell | Tag | Food skill |
|---|---|---|---|---|---|---|---|
| Corn Hardtack | 15 | 5 | -5 | 10 | 0 | Field food (stack 50) | 4 |
| Smoked Jerky | 20 | 10 | -5 | 10 | 10 | Field food (stack 30) | 8 |
| Fry Bread | 15 | 7 | | 15 | 25 | | 2 |
| Fried Egg | 10 | 5 | | 10 | 25 | | 2 |
| Mushroom Omelet | 30 | 15 | | 15 | 50 | | 10 |
| Biscuits and Gravy | 40 | 20 | | 20 | 50 | Filling | 18 |
| Prospector's Hash | 45 | 22 | | 25 | 50 | Energy | 22 |
| Coffee Cake | 40 | 20 | | 20 | 25 | Energy | 27 |
| Bone Broth | 10 | 20 | 30 | 5 | 25 | Hot | 6 |
| Corn Chowder | 35 | 17 | 20 | 20 | 50 | Hot | 14 |
| Pumpkin Soup | 35 | 17 | 20 | 15 | 25 | Hot | 18 |
| Chicken Noodle Soup | 45 | 35 | 25 | 20 | 50 | Hot | 35 |
| Tamales | 45 | 22 | | 25 | 25 | | 22 |
| Campfire Chili | 55 | 28 | -5 | 30 | 50 | Hot | 27 |
| Chili Mac | 60 | 30 | | 30 | 50 | Hot | 43 |
| Snowberry Pie | 45 | 22 | 10 | 20 | 25 | Cooling | 27 |
| Yucca Pie | 45 | 22 | 10 | 20 | 25 | Cooling | 27 |
| Mushroom Pie | 45 | 22 | | 20 | 25 | | 27 |
| Butcher's Pie | 104 | 52 | | 40 | 50 | Filling | 60 |
| Blueberry Jam | 15 | 5 | | 15 | 0 | Energy | 27 |

## Drinks

| Drink | Water | Tag | Food skill |
|---|---|---|---|
| Pine Needle Tea | 24 | Hot | 6 |
| Acorn Coffee | 24 | Energy | 6 |
| Berry Tea | 24 | Filling | 6 |
| Aloe Juice | 30 | Cooling | 11 |
| Blueberry Soda | 34 | Energy | 27 |
| Snowberry Gin | 15 | Hot, and the room leans a little | 27 |
| Pumpkin Ale | | Same effect as vanilla Beer | 22, chemistry station |

Three Mega Crush flavors are found in loot and at traders:

- **Grape:** jump 3 m higher.
- **Green Apple:** faster searching and lockpicking, and +10 loot stage.
- **Fruit Punch:** harvest 50% more.

## Chems

Every chem except Herbal Painkillers ends in a 2 minute **Crash**: stamina recovers at half speed and your vision blurs. Taking another chem during a Crash is an **Overdose**: the chem has no effect, you collapse for 3 seconds and you lose half your max health, which can kill you. The Crash then starts again.

| Chem | Effect | Medical skill |
|---|---|---|
| Herbal Painkillers | Heals 20 and halves stun chance. No Crash. | 10 |
| Long Haul | 60 seconds of stamina that never drains. | 15 |
| Possum Pills | You collapse and can't move for 8 seconds. Zombies lose you and wander off. Anything still close sees you when you stand. | 30 |
| Put It On My Tab | 15 seconds of no damage at all. When it ends, half of what you absorbed lands at once, and it can kill you. | 50 |
| Nick of Time | The world slows to 35% speed for about 8 seconds. You slow too, but your aim doesn't. | 75 |
| Dead Man's Switch | Loaded for 30 minutes. The next hit that would kill you leaves you at 1 health with 3 seconds of invulnerability, then a Crash. Rare loot and traders only. | |

### Co-op

Everything works in co-op. Nick of Time is the one difference: a shared world can't slow down, so it gives +60% move and reload speed for 8 seconds instead. If another player joins during the slowdown, time returns to normal.

## Snowberries

Snowberries are a farmable crop, with seeds unlocked by the Seeds crafting skill, and grow wild in snow biomes.

## Updating from 2.x

Items that stayed keep their internal names, so they survive in a save, even where the name changed (Omelet is now Mushroom Omelet, Corn Grits is Prospector's Hash, Meat Pie is Butcher's Pie). Mashed Potatoes, Grape Drink and Glowing Green Juice are gone and may disappear from a save that holds them. The candy icon overrides are gone, so candy uses vanilla's art again.

## Building

`src\build.bat` builds the DLL. Config comes from `Scripts\ConsumablesExpanded\gen_consumables.py` and the icons from `Scripts\ConsumablesExpanded\make_icons.py`.
