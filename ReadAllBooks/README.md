# ReadAllBooks

Adds a "Read All Books" button to the loot window and to your backpack. Open any loot container (chest, crate,
dropped backpack, ...) and click the book icon on the right of the window's title bar, or press **F2**: every book and
schematic in the container that you don't know yet is read, exactly as if you'd taken it and pressed Read. Perks,
recipes, the reading experience and challenge progress all count, and the books are used up.

The backpack (inventory) window has the same button in its title bar, left of your money. It reads the unread books
and schematics in your backpack (not the toolbelt). **F2** does the same whenever the backpack is open without a loot
container, for example in the inventory, at a workbench or trader, or next to a vehicle's storage; with a loot
container open, F2 reads the container.

- Books and schematics you already know stay where they are, so you can sell them. If a stack has several copies,
  one is read and the rest stay.
- Slots you've locked (in the container or the backpack) are left alone.
- Skill magazines are not included.
- A message says how many were read, and how many you already knew.

## Install

Drop the `ReadAllBooks` folder into `7 Days To Die/Mods/`. It needs EasyAntiCheat off (it has C# code) and uses the
game's own `0_TFP_Harmony`. It runs on the client: in multiplayer, each player who wants the button installs it, and
the container updates for everyone like it does when you take an item out. Reading from your own backpack is local,
like the inventory's Read button.

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
