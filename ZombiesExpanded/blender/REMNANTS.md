# Remnants and round-2 models: specs

Remnants are small cosmetic props that tell who a zombie was and how it died: things stuck in it, things it wore or
carried. About half of all zombies get one. They go on any zombie in the game, vanilla or modded, through the same
pipeline as the gear and growths, so read `MODELS.md` first (coordinates, fitting, look, build command). This file
says what each model is. Several agents build these at once: only touch your own scripts and model folders.

## Rules for every remnant

- **Parts:** name every part exactly as listed (`zk.on(obj, bone, piece)` gives `Bone#Piece`). The game finds a part
  by that name, so a different name means it never shows.
- **Rigid:** each part rides one bone and nothing bends, so keep anything that hangs (a cut rope, a cable, a chain)
  short, and hang it the way it would hang with the body upright.
- **Stuck-in objects:** sink 3 to 4 cm past the stand-in's surface, so the entry point stays hidden on slimmer zombies.
  Joe's real chest front sits about 2 cm inside his chest hit box; a nurse's or a fat cop's pushes past it. Show the
  wound on the object itself (blood and gore drying on the blade or shaft near the skin), not as a patch of skin: flat
  skin patches read as stickers in game.
- **Worn items:** 0.5 to 1.5 cm off the stand-in. On the head, keep caps and hats about 2 cm off the head hit box,
  because Joe's shaggy hair comes down to his jaw and pokes through anything tighter.
- **Look:** photo-real and worn, like the game's own art and the existing gear (`cut/hard_hat.py`, `cut/military_helmet.py`,
  `cut/kevlar_vest.py`). Dirt, grime in creases, wear on edges, blood where it fits. Keep colors as dark and dirty as the
  zombies; bright or saturated albedo reads as a flat cut-out in game (see `MODELS.md`).
- **Budget:** small props up to 1,500 triangles with `zk.export(Name, pieces, ASSETS, size=512)`; the big ones
  (HiVisVest, MessengerBag, CowboyHat, SnatcherSack, CarDoor, RiotShield) up to 3,000 with the default 1024.
- **Face:** eyes about (±0.032, -0.075, 1.719), nose bridge about (0, -0.09, 1.725), temples about x ±0.075 at z 1.73;
  check against `skeletons/joe.json` (the brow bones) and the stand-in. The jaw opens when the zombie attacks, so
  masks sit a little loose under the chin.

## The models

Name (as passed to `zk.export`), script, parts, and what it is.

### Stuck in them

| Name | Script | Parts | What |
|---|---|---|---|
| Arrows | arrows.py | `Spine2#Arrows`, `LeftUpLeg#Arrow` | Two arrows in the upper back at different angles (one shaft snapped), one in the back of the left thigh. Wooden or carbon shafts, worn fletching, blood dried on the shafts at the skin. |
| CrossbowBolt | crossbow_bolt.py | `LeftShoulder#Bolt` | A crossbow bolt through the left shoulder, front to back: the tip out the back, the vanes at the front. |
| KitchenKnife | kitchen_knife.py | `RightShoulder#Knife` | A big kitchen knife buried in the front of the right shoulder, handle out. |
| Screwdriver | screwdriver.py | `Neck#Screwdriver` | A flat-head screwdriver with a worn plastic handle, stuck in the left side of the neck. |
| Axe | axe.py | `Spine2#Axe` | A wood axe buried in the upper back, handle angled down and out. |
| Machete | machete.py | `Head#Machete` | A machete wedged in the top-left of the skull, the blade sunk deep, the handle out to the side and up. |
| Pitchfork | pitchfork.py | `Spine1#Pitchfork` | A pitchfork's tines in the lower back, the handle snapped off about 40 cm out. |
| Rebar | rebar.py | `Spine2#Rebar` | A length of rusty bent rebar through the chest, out the back, with concrete still on one end. |
| GlassShards | glass_shards.py | `Head#Shards`, `LeftForeArm#Shards`, `RightForeArm#Shards` | Shards of dirty window glass stuck in the face (cheeks, forehead, clear of the eyes) and the forearms. Opaque: grey-green edges, dark faces. |
| BearTrap | bear_trap.py | `LeftLeg#Trap` | A rusty bear trap clamped on the left ankle (low on the shin) with a short length of chain hanging from it. The zombie limps. |
| BarbedWire | barbed_wire.py | `RightForeArm#WireVar1`, `LeftUpLeg#WireVar2`, `Spine1#WireVar3` | Barbed wire in loose coils, a loose end sticking out: round the right forearm, the left thigh or the waist (variant parts). |
| Noose | noose.py | `Neck#Noose` | A hangman's noose round the neck with the rope cut short, hanging down the chest about 25 cm. |

### Hospital

| Name | Script | Parts | What |
|---|---|---|---|
| HeadBandage | head_bandage.py | `Head#Bandage` | Gauze wrapped round the forehead and over the top, a dried blood stain, loose ends. |
| ArmCast | arm_cast.py | `LeftForeArm#Cast` | A plaster cast on the left forearm from below the elbow to the wrist, filthy, with marker signatures and doodles. |
| LegCast | leg_cast.py | `RightLeg#Cast` | A plaster cast on the right shin from below the knee to the ankle. |
| NeckBrace | neck_brace.py | `Neck#Brace` | A foam cervical collar, beige, stained. |
| IVLine | iv_line.py | `LeftForeArm#IV` | A cannula taped on the inside of the left forearm near the wrist, a torn clear tube hanging a little way (opaque, pale and dirty), and a white hospital wristband. |

### Face and neck

| Name | Script | Parts | What |
|---|---|---|---|
| CrackedGlasses | cracked_glasses.py | `Head#Glasses` | Dark plastic frame glasses sitting crooked, one lens cracked. Lenses opaque: dark and glossy with a white crack. |
| Sunglasses | sunglasses.py | `Head#Sunglasses` | Wraparound sunglasses, scuffed. |
| Headphones | headphones.py | `Neck#Headphones` | Over-ear headphones round the neck, a short cable end hanging. |
| SurgicalMask | surgical_mask.py | `Head#Mask` | A pale blue surgical mask over the nose and mouth, loops over the ears, blood soaked through at the mouth. |
| DustMask | dust_mask.py | `Head#Mask` | A white N95 dust mask with a valve and straps, grimy. |
| GasMask | gas_mask.py | `Neck#GasMask` | A gas mask with one filter, hanging at the throat by its strap (not on the face). |

### Headwear (only on zombies with no hat or helmet of their own)

| Name | Script | Parts | What |
|---|---|---|---|
| BaseballCap | baseball_cap.py | `Head#Cap` | A faded cap, peak forward, sweat stains. |
| Beanie | beanie.py | `Head#Beanie` | A knit beanie, dark, pulled down over the ears. |
| Bandana | bandana.py | `Head#Bandana` | A paisley bandana tied over the head, knot at the back. |
| CowboyHat | cowboy_hat.py | `Head#Hat` | A battered straw or felt cowboy hat. |

### Personal, work and law

| Name | Script | Parts | What |
|---|---|---|---|
| ChainNecklace | chain_necklace.py | `Spine2#Chain` | A chain round the neck resting on the collarbones, with dog tags or a small pendant on the chest. |
| Wristwatch | wristwatch.py | `LeftHand#Watch` | A wristwatch on the left wrist, cracked face. |
| Lanyard | lanyard.py | `Spine2#Lanyard` | A lanyard from round the neck to an ID badge on the chest (photo, name, company logo). |
| HiVisVest | hi_vis_vest.py | `Spine2#Vest` | An orange or yellow-green hi-vis vest with reflective stripes, filthy and torn, open at the front. |
| ToolBelt | tool_belt.py | `Hips#Belt` | A leather tool belt round the waist with pouches, a hammer loop and a tape measure. |
| MessengerBag | messenger_bag.py | `Spine2#Strap`, `Hips#Bag` | A strap across the body from the right shoulder to the left hip, and the bag hanging at the left hip. |
| FannyPack | fanny_pack.py | `Hips#Pack` | A fanny pack, faded nylon, at the front of the waist. |
| Handcuffs | handcuffs.py | `RightHand#Cuffs` | One cuff locked on the right wrist, the other hanging open from the chain. |
| AnkleMonitor | ankle_monitor.py | `RightLeg#Monitor` | A house-arrest ankle monitor low on the right shin, black strap, small box. |

### Round-2 mutations and gear

| Name | Script | Parts | What |
|---|---|---|---|
| SnatcherSack | snatcher_sack.py | `Spine2#Sack`, `Spine2#SackFull` | The Snatcher's burlap sack slung on its back on a rope across the chest. `Sack` is the sack empty (hanging flat); `SackFull` is the same sack stuffed and bulging with lumps, its neck tied. The game shows one or the other, so both sit in the same place. |
| CarDoor | car_door.py | `LeftForeArm#Shield` | A rear door off a small car (about 80 × 70 cm), rusty and dented, window glass gone, with a belt looped through as a strap, held on the left forearm as a shield. |
| RiotShield | riot_shield.py | `LeftForeArm#Shield` | A police riot shield (about 90 × 50 cm), dark tinted (opaque: the game's model shader can't do see-through), scratched, POLICE lettering, a handle and arm strap. |

**Shields:** strapped to the outside of the left forearm, with the face of the shield toward the zombie's front (-Y)
when the arm hangs in the bind pose, and offset a few cm in front of the forearm so it covers the left side of the
torso from the front. The zombie's arm swings it when it attacks.

## After the first review (2026-11-01)

**Cut** (scripts moved to `blender/cut/`, not built): Bandana, BaseballCap, Beanie, DustMask, FannyPack, Handcuffs,
HeadBandage, HiVisVest, IVLine, Lanyard, LegCast, MessengerBag, NeckBrace, SurgicalMask, ToolBelt, Wristwatch, and
from the earlier models HardHat, ScrapArmor and Icicles.

**Variant parts.** A part whose piece name contains `Var` (for example `Spine2#BackVar1`, `LeftLeg#WireVar2`) is
optional: each zombie shows a random selection of a model's `Var` parts, picked from its profile so every player
sees the same ones. Each `Var` part is shown about half the time, and at least one always shows when a model has
nothing but `Var` parts. Parts without `Var` always show. Every `Var` part must look right on its own and with any
of the others.

**Checking on the real zombies.** Model agents may now render their own models in Unity (one Unity at a time per
project):
1. Take the lock: `mkdir unity/Build/unity.lock`. If that fails, another agent is rendering: do other work and try
   again later.
2. Render, from `ZombiesExpanded/`:
   `ZED_MODELS="<Name>" "/c/Program Files/Unity/Hub/Editor/2022.3.62f2/Editor/Unity.exe" -batchmode -quit -projectPath "$(cygpath -aw unity)" -executeMethod ZombiesModels.BuildAndPreviewSome -logFile "$(cygpath -aw unity/Build)/unity-<name>.log"`
   It writes `unity/Build/models/<Name>.png` (the lineup on Joe, the fat cop and the nurse, front and back; it shows
   every `Var` part at once) and `unity/Build/closeups/<Name>.png` (front and back on Joe, framed on the model).
3. Release the lock straight after, even if Unity failed: `rmdir unity/Build/unity.lock`.

These renders are what counts: the vanilla zombies are slimmer than the stand-in at the front of the chest, the neck
and the limbs, and the game's shader shows pale, glossy or saturated materials brighter and flatter than Blender
does. The nurse's hair shows pink in the editor (it can't draw the game's hair shader); ignore that.

## Round 4: stuck in them, part two (2026-11-03)

The "stuck in them" props survived the first review best, so ten more in the same grim style. **Body only, never the
head or face:** other mods' zombies may wear something of their own up there. Each sits on its own spot (the slot in
brackets), so they spread round the body instead of piling onto the back. Same rules as above: sink 3 to 4 cm past the
stand-in, show the wound as drying blood and gore on the object, dark and dirty, small props up to 1,500 triangles at
512.

| Name | Script | Parts | What |
|---|---|---|---|
| Spear | spear.py | `Spine1#Spear` | [Belly] A homemade spear (a big kitchen knife lashed to a broom handle with grimy duct tape) driven into the belly a little left of center, from the front and slightly below; the tip doesn't come out the back. The handle is snapped about 45 cm out, the splintered end drooping a little. |
| Shovel | shovel.py | `Spine2#Shovel` | [Back] A garden spade's blade driven into the upper right back (across from the axe's left shoulder blade), the ash shaft snapped about 50 cm out and angled up and back. Rusty blade, the shaft dark with handling. |
| Cleaver | cleaver.py | `LeftShoulder#Cleaver` | [LeftShoulder] A heavy meat cleaver chopped down into the top of the left shoulder, between the neck and the shoulder joint, the blade sunk to half its height, the wooden handle sticking up and out to the side. |
| Hatchet | hatchet.py | `RightUpLeg#Hatchet` | [RightLeg] A small camp hatchet buried in the front-outside of the right thigh, the handle out and down. |
| Crowbar | crowbar.py | `Spine1#Crowbar` | [Chest] A rusty crowbar with its hooked claw end caught in under the right lower ribs at the side, the straight bar hanging down and out past the right hip (not crossing in front of the thigh, which swings when it walks). |
| SkiPole | ski_pole.py | `LeftLeg#Pole` | [LeftLeg] The top half of a snapped aluminum ski pole driven into the back of the left calf, the grip and its strap out behind and slightly down, the bent, snapped tube end in the body. |
| PoolCue | pool_cue.py | `RightShoulder#Cue` | [RightShoulder] The thick half of a snapped pool cue jabbed into the back of the right shoulder (behind the joint), splintered end in the body, the butt with its wrap and rubber bumper sticking out about 45 cm behind and up. |
| Fishhook | fishhook.py | `RightForeArm#Hook` | [RightArm] A big treble fishhook through the outside of the right forearm, 20 to 30 cm of torn line hanging (keep it short and rigid, hanging down with the body upright) with a battered, faded fishing lure on the end. |
| Nails | nails.py | `LeftArm#Nails`, `LeftForeArm#Nails` | [LeftArm] A line of 6 to 10 framing nails from a nail gun driven into the outside of the left upper arm and forearm, heads 1 to 2 cm proud, a couple bent over, a scrap of the paper collation strip on one, rust and blood. |
| PadlockChain | padlock_chain.py | `LeftForeArm#Chain` | [LeftHand] Two loops of heavy rusty chain locked round the left wrist with a big padlock, and a short torn length (15 to 20 cm) hanging. On the forearm bone, close to the wrist. |

**After the review (2026-11-03):** kept Spear, Shovel, Cleaver, Hatchet, Crowbar, Nails and PadlockChain. Cut (scripts moved to `blender/cut/`, not built): SkiPole, PoolCue and Fishhook.
