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
   Scripts\bin\XmlPatch.exe <game>\Data\Config <merged dir> <repo>\BooksExpanded <repo>\ConsumablesExpanded <repo>\QuestsExpanded <repo>\WeaponsExpanded
   ```

3. **Check every reference** the mods add (items, blocks, buffs, loot groups, quests, POIs, icons, meshes, localization, effect actions and requirements, game events and the items they give, defense quest bosses and spawners, trader dialog options) against the merged XML and the game info. Classes from a mod's own DLL (`"Name, Assembly"`) are checked against the mod's `src`. It should end with `TOTAL 0`.

   ```
   python Validation\refcheck.py <game> <merged dir> <info dir> <repo>\BooksExpanded <repo>\ConsumablesExpanded <repo>\QuestsExpanded <repo>\WeaponsExpanded
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
- `Scripts\bin\IconTool.exe <vanilla icon.png> <out.png> <#RRGGBB> 0.62`: recolors a vanilla icon (from `<game>\Data\ItemIcons`) into a custom one, like the existing icons. `IconTool.exe sheet <out.png> <icons...>` lays icons side by side for comparing.

## QuestMaker

`QuestMaker\jinja2.py` is a minimal stand-in for the parts of jinja2 that QuestsExpanded's QuestMaker uses, so it runs without installing jinja2:

```
set PYTHONPATH=<repo>\Scripts\QuestMaker
python main.py
```

## Entity groups

`entity_groups.py` and `make_entitygroups.py` are older helpers for generating entity group XML.
