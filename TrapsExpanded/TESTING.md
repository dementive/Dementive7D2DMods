# Traps Expanded: quick test checklist

About 30 minutes. Note anything broken, too strong, too weak or odd-looking, with a screenshot when it's visual.

## Setup

- [ ] Use a creative test world (not your hardcore save). In the console (F1): `cm` opens the creative menu, `dm` turns
      on debug mode, and **F6** then spawns zombies at your crosshair. `settime day` makes it daytime.
- [ ] From the creative menu, search `Dementive`: take all 14 traps, Tar and Rebar Bolts.
- [ ] Also take: `generatorbank`, `ammoGasCan` (two stacks), `meleeToolWireTool`, `resourceAnimalFat`, `resourceWood`,
      `ammoArrowStone`, `ammoArrowFlaming`, `thrownAmmoMolotovCocktail`, a club or sledgehammer,
      `resourceRepairKit` and two `cntWoodWritableCrate` (storage crates).
- [ ] Place the generator bank, fuel it and switch it on. Wire every powered trap to it.

For each trap: place it, hold **E** and use **Load** where it takes ammo, then spawn 2 or 3 zombies (F6) that walk
into it.

## Each trap

- [ ] **Grease Slick** (load fat): zombies that walk through drip black and slow down a lot. It uses 1 fat per 4
      zombies.
- [ ] **Burn Barrel** (load wood, then E > **Light**): zombies within 1.5 m catch fire and it lights up the area.
      **Put out** works, and it uses about 1 wood every 20 s while lit.
- [ ] **Swinging Log**: a zombie in front gets hit (35 damage) and knocked back about 3 m. The log re-cocks over 5 s.
- [ ] **Bear Trap**: the first zombie on it is held for 3 s and takes 50 damage. The trap then stays sprung until
      E > **Re-arm**.
- [ ] **Trip Bow** (load arrows): it fires every 3 s at the first zombie in a 12 m line ahead. Flaming arrows set
      zombies on fire.
- [ ] **Sprinkler** (5 W): zombies in its 6 m cone get soaked (dripping water) and are a little slower. A molotov
      won't set a soaked zombie on fire.
- [ ] **Tar Sprayer** (5 W, load Tar): every 2 s it lobs a glob at the nearest zombie within 10 m, and the 2 m splash
      tars them.
- [ ] **Salvage Hopper**: zombies your traps kill within 10 m add 1 to 3 scrap iron. The haul is in its bin: open it like a
      storage box (the hopper takes no ammo, so it has no Load or Unload).
- [ ] **Tesla Coil** (30 W): a quick check that it still zaps and jumps to 2 more zombies.
- [ ] **Cryo Vent** (20 W): zombies on the grate slow down with each pulse, and 3 pulses freeze them for 2 s.
- [ ] **Ram** (15 W): every 2 s it punches zombies within 2 m for 60 damage and knocks them back about 4 m.
- [ ] **Flame Vent** (10 W, load gas): it fires a 5 m flame from its three nozzles and sets zombies on fire, using
      1 gas can a second.
- [ ] **Overcharger** (40 W): place it within 5 m of the Tesla Coil. The coil zaps visibly faster and wears faster.
- [ ] **Bolt Thrower** (15 W, load bolts): every 3 s it shoots the toughest zombie within 30 m, for 800 damage and a
      knockdown.

## Combos

- [ ] **Sprinkler then Tesla**: soaked zombies take double zaps, the arc jumps to one more zombie, and they're stunned
      2 s.
- [ ] **Tar then fire** (Burn Barrel, Flame Vent, molotov or flaming arrow): you get an **Inferno**. The tarred zombie
      burns hard, and the fire spreads to other tarred zombies within 3 m.
- [ ] **Frozen then blunt** (Ram, Swinging Log, club): a **Shatter** does double damage.
- [ ] Optional: a demolisher never freezes and is held only briefly.

## Supply crates and Load all nearby

- [ ] Place a storage crate within 3 blocks of the Trip Bow (try one a block lower or higher) with stone arrows and
      something else in it. Within 3 s the bow fills to 30 (look at it) and the crate loses only the arrows it took.
- [ ] Take the arrows out of the crate and Unload the bow. Open the crate, put arrows back in and keep it open for
      10 s: the bow stays empty. Close it: the bow fills within 3 s. Lock the arrows' slot in the crate (unload the
      bow again): the bow leaves that slot alone.
- [ ] A crate 4 blocks away isn't used, and neither is a POI's loot container (a cupboard or trash pile).
- [ ] Switch the generator off and Unload the Flame Vent: it still refills from gas cans in a crate next to it.
- [ ] Put arrows, gas cans and wood in your inventory, stand among three or more traps that take them and use
      **Load all nearby**: the closest traps fill first, until your ammo runs out, and a tooltip says how many traps
      it loaded. With every trap full it says there's nothing to load.
- [ ] Optional, co-op: as a client, Load all nearby and a supply crate both work, nothing is duplicated or lost, and the
      other player sees the crate's contents go down as a trap refills.

## Everything else

- [ ] Look at a trap: it shows its level, kills, upgrade and what's loaded.
- [ ] **Unload** gives the ammo back. Picking a trap up drops its ammo and resets its level.
- [ ] Wearing traps (Log, Tesla, Cryo, Ram) stop at 5% health, and powered ones blink their lamp. A repair kit fixes
      them.
- [ ] Level 1 arrives at 25 kills: the look-at text shows Level 1.
- [ ] Look at a vanilla turret or blade trap: it shows a level too.
- [ ] Save, quit and reload: levels, kills and loaded ammo are kept.
- [ ] The traps crafting skill lists the new traps at 5, 10, 15, 20, 25, 50, 75 and 100. Primitive traps are crafted
      by hand, the rest at a workbench.
- [ ] The models look right next to vanilla traps, and the effects (water, tar, frost, fire, bolts) look right.

## Blood Moon

Check the day count first: by default the Blood Moon is day 7.

- [ ] `settime 7 6 59`: at 07:00 a radio forecast of the horde appears in chat.
- [ ] `settime 7 21 55`: let the traps fight the horde. At dawn a report window and a chat summary should show kills
      by trap, the MVP trap and combos. The window waits until no awake zombie is within 30 m (and no other window
      is open); the chat summary comes at once.

## Skipped

- **Level 3 upgrades** need 150 kills on one trap, which is too slow to test by hand. I can add a test command that
  sets a trap's level.
