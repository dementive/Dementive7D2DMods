# Changes

1. Trader quests will reset 2 days instead of every 3 days

2. Adds 100+ quests, offered by every trader

The mod used to replace the starting quest chain with a quest that just marks the trader. V3.4's own starting quest already does that, so the replacement was removed.

ZZZTongPrefabs-QuestsExpanded is the same mod with quests for ZZTong's POIs added; install one or the other, not both.

**Back up your save before adding or removing this mod.** Quest mods add C# code and quests that get saved with your character, so removing the mod from an existing save can reset your character to level 1.

## V3.4 Updates

- Bumped to version 2.0.0.0
- Renamed `Localization.txt` to `Localization.csv` (the game no longer loads `.txt` localization from mods) and converted it to the V3.4 column layout. Quest text that contained commas or an unclosed quote is no longer cut off.
- Quests are added to each trader's own quest list (V3.4 replaced the shared `trader_quests` list)
- Rally points use V3.4's quest-type rally markers and quests carry `filter_tags="poi"` so the "POI quests" game option applies to them
- Reward loot groups renamed in V3.4 are remapped (`groupQuestSteel` -> `groupQuestSteel01`/`02` by tier, `groupQuestResources` -> `groupQuestResourcesT0`, T0 armor groups -> `groupQuestArmorT1`)
- Zombies removed from the game are replaced in defend quests (Cheerleader/Stripper -> Party Girl, Farmer -> Rancher, Old Timer -> Chuck, Snow -> Frostclaw)
- Removed `army_barracks_01`, a POI that no longer exists
- POI vending machines are no longer slowed to a 2 day reset (V3.4 resets them daily)
- `QuestsExpanded.dll` rebuilt against V3.4 (see below)

## Fixes for reported bugs

- Fetch quests no longer pick POIs that have no spot for the satchel. The satchel used to spawn in another POI kilometers away, and leaving the quest area to get it failed the quest. Quests now use the same POI checks as vanilla: the POI must support the quest type (fetch, clear, infested), have sleepers, and not be in use by another player's quest.
- POI-specific quests (cabins, caves, gas stations, farms, ...) now pick from every matching POI on the map, preferring ones near the trader. They used to lock in one random POI name for the whole game session, so if that POI wasn't on your map the quest had no marker, and if it was far away every copy of the quest was far away.
- In multiplayer, POI-specific quests taken by a client now search for POIs near the trader instead of near the corner of the map.
- Quest POIs show their proper names (e.g. "Crack-A-Book") instead of file names like `store_book_01`.
- The tier 2 defense quest counted as a tier 1 quest, and the tier 6 defense quest could never be offered (there are no tier 6 POIs; it now uses tier 5 POIs like vanilla's tier 6 quests).

## Building QuestsExpanded.dll

The custom quest objectives (`GotoPOIDEM`, `RandomTaggedPOIGotoDEM`) live in `src` and are adapted from SCore's `GotoPOISDX` / `RandomTaggedPOIGotoSDX`. They only reference the game's own DLLs, so SCore does not need to be installed.

Run `src\build.bat`. It compiles against the installed game with the C# compiler that ships with Visual Studio (no .NET SDK needed) and copies the DLL into `ZZZTongPrefabs-QuestsExpanded` as well.
