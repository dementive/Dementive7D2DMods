# ReadAllBooks

Adds a "Read All Books" button to the loot window. Open any loot container (chest, crate, backpack, ...) and click
the book icon on the right of the window's title bar, or press **F2**: every book and schematic in the container that
you don't know yet is read, exactly as if you'd taken it and pressed Read. Perks, recipes, the reading experience and
challenge progress all count, and the books are used up.

- Books and schematics you already know stay in the container, so you can sell them. If a stack has several copies,
  one is read and the rest stay.
- Slots you've locked in the container are left alone.
- Skill magazines are not included.
- A message says how many were read, and how many you already knew.

## Install

Drop the `ReadAllBooks` folder into `7 Days To Die/Mods/`. It needs EasyAntiCheat off (it has C# code) and uses the
game's own `0_TFP_Harmony`. It runs on the client: in multiplayer, each player who wants the button installs it, and
the container updates for everyone like it does when you take an item out.

## Configuration

Edit `Config/keybinding.json` to change the hotkey. Any `UnityEngine.KeyCode` name works (e.g. `F1`, `F2`,
`Backspace`, `Alpha5`). Restart the game for the change to take effect.

## V3.4 update (why it never worked)

- The button patch was in `Config/XUi/windows.xml`; V3.4 reads in-game windows from `Config/XUi_InGame/`, so the
  button was never added. The loot window's layout also changed, so the patch targeted elements that no longer exist.
- The Harmony patches targeted loot window methods that V3.4 doesn't have, and the code read the container through a
  field that no longer exists.
- `Localization.txt` is no longer loaded by the game (it's now `Localization.csv` in the V3.4 column layout).
- Reading fired a generic "primary action" event on the book and on the player instead of using the item's Read
  action, and emptied the container's slots directly, which doesn't sync in multiplayer. It now uses the same Read
  action as the inventory, through the container's slots.

## Building

`src/build.bat` compiles `ReadAllBooks.dll` against the installed game with the C# compiler that ships with Visual
Studio (no .NET SDK needed).
