# Scripts

Tools for building and checking the mods without launching the game. They need Python 3 and Visual Studio (any edition, for its C# compiler; no .NET SDK needed).

Run `build.bat` once to build the C# tools into `Scripts\bin` (not committed): `XmlPatch.exe`, `Api.exe` and `IconTool.exe`.

In the examples, `<game>` is the 7 Days to Die install folder and `<repo>` is this repository.

## Validation

XML patches only apply when a world loads, so reaching the main menu proves nothing. These check the mods offline instead.

1. **Generate the game info** (once per game update): the lists of game types, passive effects, item icons and POIs that references are checked against.

   ```
   python Validation\make_gameinfo.py <game> Scripts\bin\Api.exe <info dir>
   ```

2. **Apply the patches** to the vanilla XML, in load order. Every command whose xpath matches nothing is reported, and the merged XML is written out.

   ```
   Scripts\bin\XmlPatch.exe <game>\Data\Config <merged dir> <repo>\AmmoExpanded <repo>\ArmorExpanded <repo>\BooksExpanded <repo>\ConsumablesExpanded <repo>\ModsExpanded <repo>\QuestsExpanded <repo>\ToolsExpanded <repo>\WeaponsExpanded
   ```

3. **Check every reference** the mods add (items, blocks, buffs, loot groups, quests, POIs, icons, meshes, localization, effect actions and requirements, game events and the items they give, defense quest bosses and spawners, trader dialog options) against the merged XML and the game info. Classes from a mod's own DLL (`"Name, Assembly"`) are checked against the mod's `src`. It should end with `TOTAL 0`.

   ```
   python Validation\refcheck.py <game> <merged dir> <info dir> <repo>\AmmoExpanded <repo>\ArmorExpanded <repo>\BooksExpanded <repo>\ConsumablesExpanded <repo>\ModsExpanded <repo>\QuestsExpanded <repo>\ToolsExpanded <repo>\WeaponsExpanded
   ```

Other checks:

- `Validation\modoverrides.py <merged>\item_modifiers.xml <merged>\items.xml Dementive`: lists WeaponsExpanded weapons whose attachment overrides (scopes, flames, silencers) differ from their vanilla parent's. Should print nothing.
- `Validation\poiaudit.py <game> QuestsExpanded\Config\quests.xml`: for each quest, checks that the POIs it can send players to exist and support the quest type (fetch, clear, infested, ...).
- `Scripts\bin\Api.exe <game>\7DaysToDie_Data\Managed <game>\Mods\0_TFP_Harmony <Type>`: prints the members of a game type, for writing C# against the game (e.g. QuestsExpanded's DLL). `?text` lists type names containing `text`.
- `Validation\ilmethod.py game.il Class::Method`: prints a method's IL from an ildasm dump of `Assembly-CSharp.dll`, to see what the game actually does. Make the dump with the Windows SDK's ildasm (`NETFX 4.8 Tools`); in Git Bash prefix it with `MSYS_NO_PATHCONV=1`:

   ```
   ildasm.exe -out=game.il "<game>\7DaysToDie_Data\Managed\Assembly-CSharp.dll"
   ```

## WeaponsExpanded

- `gen_item_modifiers.py <game>\Data\Config\item_modifiers.xml WeaponsExpanded\Config\items.xml WeaponsExpanded\Config\item_modifiers.xml`: writes the attachment overrides. Mods look these up by item name, so they aren't inherited through `Extends`; each weapon gets a copy of its vanilla parent's. Rerun after adding a weapon or after a game update.
- `gen_serverside.py <game> WeaponsExpanded WeaponsExpanded-SERVERSIDE`: rebuilds the server-side copy from the main mod. Weapons use their vanilla parent's icon with a color tint, since server-side-only players don't have the custom icons. Rerun after any change to WeaponsExpanded.
- `add_weapons.py <game> WeaponsExpanded`: generates the signature weapons from their vanilla parents. Weapons already in `items.xml` are skipped, so a new one can be added to the script's list and the script rerun.
- `make_icons.py <game> WeaponsExpanded`: paints the signature weapons' icons from their vanilla icons with `IconTool.exe fx` (a recipe per weapon in `ICONS`). The original 30 weapons' hand-made icons aren't touched.
- `Scripts\bin\IconTool.exe <vanilla icon.png> <out.png> <#RRGGBB> 0.62`: recolors a vanilla icon (from `<game>\Data\ItemIcons`) into a custom one, like the existing icons. `IconTool.exe sheet <out.png> <icons...>` lays icons side by side for comparing. `IconTool.exe fx <vanilla icon.png> <out.png> <op> ...` paints an icon with a chain of effects (gradient maps for gold, chrome or leather, decals like flames, camo, plaid, hazard stripes, cracks and circuits, glows, glowing parts, sparkles and embers, optionally limited to part of the item such as a bullet tip); the ops are listed at the top of `WeaponsExpanded\IconTool.cs`, and ArmorExpanded, AmmoExpanded, ToolsExpanded and ModsExpanded keep their recipes in `ICONS` in their generators.

## ArmorExpanded

- `ArmorExpanded\gen_armor.py <game> ArmorExpanded ArmorExpanded-SERVERSIDE`: writes the whole mod from the `PIECES` table: each named piece copies its vanilla piece's effect groups (they aren't inherited through `Extends`) with the armor and durability boost and its signature effect group, plus buffs, loot, traders, localization, the recolored icons and the server-side copy (tinted vanilla icons). The 20 named clothing pieces are in `ArmorExpanded\clothing.py` (imported by the generator): each extends its vanilla clothing item and adds its perk, hidden worn-marker buffs, patches to the vanilla burning, shock, wet and fall buffs, loot, trader entries, localization and painted icons (`ICONS` in that file).

## ConsumablesExpanded

- `ConsumablesExpanded\gen_consumables.py ConsumablesExpanded`: writes the mod's Config from the tables at the top of the script: foods, drinks, chems, their buffs, recipes, unlocks, loot, traders and localization. Mega Crush, Herbal Painkillers and snowberries aren't generated: they're copied as they are from `ConsumablesExpanded\kept`. `blocks.xml` and `biomes.xml` are hand-written.
- `ConsumablesExpanded\make_icons.py <game> ConsumablesExpanded`: builds the icons from vanilla art (a recipe per item in `ICONS`).

## ToolsExpanded

- `ToolsExpanded\gen_tools.py <game> ToolsExpanded ToolsExpanded-SERVERSIDE`: writes the whole mod from the `TOOLS` table: each named tool copies its vanilla tool's stats, effect groups and any action it changes (they aren't inherited through `Extends`) with the block damage and durability boost and its signature effect group, plus the block patches its harvest bonuses need, the player's harvest tag defaults, buffs, mod overrides, loot, traders, localization, the painted icons and the server-side copy (tinted vanilla icons). Rerun after a game update: the car, tree and salvage patches are worked out from the vanilla blocks.

## ModsExpanded

- `ModsExpanded\gen_mods.py <game> ModsExpanded ModsExpanded-SERVERSIDE`: writes the whole mod from the `MODS` table: each item mod with its quality-tier effects (cvars set on equip from `RequirementItemModTier`, like vanilla's Cripple 'Em; armor mods carry their logic in a buff while worn), schematic, workbench recipe, the buffs and Spotter Tags' nav object, loot and trader entries in the vanilla mod groups, localization, the painted icons and the server-side copy (tinted vanilla icons).

## AmmoExpanded

- `AmmoExpanded\gen_ammo.py <game> AmmoExpanded AmmoExpanded-SERVERSIDE`: writes the whole mod from the `AMMO` table: each ammo type copies its vanilla parent's effect groups with edited stats and its signature effect group, plus its schematic, recipe, the ammo list patches, loot, traders, localization, the recolored icons and the server-side copy.

## StationsExpanded

- `StationsExpanded\gen_stations.py <game> StationsExpanded`: writes the Config from the `STATIONS` table: each named station extends its vanilla station (model, recipes, window, tool slots) and carries its bonuses as block properties the mod's DLL reads, plus the station's recipe tabs (ui_display.xml), localization and the painted icons (`ICONS`). No server-side copy: crafting time is worked out on the client, so the DLL has to be there.

## FortificationsExpanded

- `FortificationsExpanded\gen_fortifications.py [FortificationsExpanded]`: writes the Config from the family tables (`SANDBAG`): each piece's empty, half and full blocks with their fill upgrades, health, damage-stage meshes and repairs, the family's helper item and recipe, the material and localization. The models come from the mod's own `src\build-models.bat`.

## QuestMaker

`QuestMaker\jinja2.py` is a minimal stand-in for the parts of jinja2 that QuestsExpanded's QuestMaker uses, so it runs without installing jinja2:

```
set PYTHONPATH=<repo>\Scripts\QuestMaker
python main.py
```

## Entity groups

`entity_groups.py` and `make_entitygroups.py` are older helpers for generating entity group XML.
