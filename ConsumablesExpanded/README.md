# Consumables Expanded

This mod adds 30+ new foods, drinks, and other consumables. All additions are in the same style as the base game and will fit seemlessly alongside all of the existing consumables in the game, no out of place icons or unbalanced buffs. All candy icons have been retextured to look more interesting as well. No other food mods should be needed.

Adds new textures so has to be installed on server and client.

## V3.4 Updates

- Bumped to version 2.0.0.0
- Renamed `Localization.txt` to `Localization.csv` (the game no longer loads `.txt` localization from mods) and converted it to the V3.4 column layout, so item names show correctly
- Rewrote the snowberry crop patches for the V3.4 block format: the old `CropsGrown` block class no longer exists, and planted snowberries now grow (they used the removed `PlantGrowing.Next` property)
- Player-planted snowberries now grow into the player harvest stage, like blueberries, and support the farmer bonus harvest/seed drops
- Replaced held-item models that were removed from the game (`parcelPrefab`, `bottled_waterPrefab`)
- Foods that restore health support the farmer armor set bonus, like vanilla foods
- Cooking pot recipes get the `cookingPotFood` tag so cooking pot crafting-time bonuses apply
