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

## Round 5: personality, gore and showpieces (2026-11-03)

The user's playtest favorites were the Sunglasses and the lumberjack's Axe: props that give each zombie its own
flavor. This round adds lots more eyewear and fun accessories, gore that shows how they died, and rare showpieces.
Same rules as above, plus these:

- **Fun is the point.** The eyewear and accessories may be playful (heart and star party glasses, 3D glasses), but
  they're still on a corpse: scuffed, grimy, a scratch or a crack, maybe a speck of blood. Keep colors a step darker
  and dirtier than new, or they read as flat cut-outs in game (see `MODELS.md`).
- **Lenses are opaque** (the game's model shader has no transparency): a dark glossy lens with a painted reflection
  gradient (a lighter streak across the top) and low roughness reads as glass.
- **Eyewear sits on the face** like `sunglasses.py` and `cracked_glasses.py` (read both, and reuse their fitting):
  temples run back over the ears and tuck into the hair. Use the face numbers in "Rules for every remnant".
- **Swinging parts.** Anything that should swing as the zombie moves is its own part whose name ends in `Swing`,
  with a `pivot` where it hangs from: `zk.on(obj, "Spine1", "GutSwing", pivot=(x, y, z))`. Model it hanging
  straight down (Joe is upright), at most 40 cm long. In game it swings about the pivot, up to about 35 degrees.
- **Gore is never a flat patch.** A wound is a torn hole with thickness: a ragged rim of torn skin and cloth that
  curls outward 0.5 to 1.5 cm, wet dark-red flesh sunk inside it, yellowed bone where bone shows, and a dark, ragged
  outer edge, so it reads as torn through the clothes, not laid on top. Wet (low roughness) inside, dull outside.
  Dark like the zombies: deep maroon and brown, never pink or bright red. End with `tk.grade(...)` like the growths
  (`fungus.py`, `brood_sac.py` and `throat_sacs.py` show flesh materials).
- **Budget:** eyewear and small accessories up to 1,500 triangles at 512; gore up to 2,500 at 1024; showpieces up to
  3,500 at 1024.

### Eyewear (all on `Head`, slot Face; only one per zombie)

| Name | Script | Parts | What |
|---|---|---|---|
| Aviators | aviators.py | `Head#Glasses` | Classic pilot sunglasses: a thin gold wire frame worn to brass at the edges, teardrop lenses, a double bridge, mirrored lenses (dark at the top fading to a warm amber-blue sheen). One lens chipped at the corner. |
| RoundShades | round_shades.py | `Head#Glasses` | Small round wire-rim "John Lennon" sunglasses, dark green-brown lenses, the thin frame slightly bent so they sit a touch crooked. |
| TapedGlasses | taped_glasses.py | `Head#Glasses` | Thick black plastic nerd glasses broken at the bridge and held together with a wad of grimy white tape; dark glossy lenses. |
| Glasses3D | glasses_3d.py | `Head#Glasses` | Cardboard 3D movie glasses: a flat folded card frame (dirty white, a smudged cinema logo), one red and one cyan lens (dulled and dark, not neon), one arm bent. |
| StarShades | star_shades.py | `Head#Glasses` | Novelty party sunglasses with big five-pointed star frames, faded glittery gold or pink plastic, dark lenses, one point snapped off. |
| HeartShades | heart_shades.py | `Head#Glasses` | Heart-shaped plastic sunglasses, a faded red frame, dark red lenses, scuffed. |
| ShutterShades | shutter_shades.py | `Head#Glasses` | Shutter shades: a plastic frame with horizontal slats instead of lenses, dirty white, one slat broken. |
| SkiGoggles | ski_goggles.py | `Head#Goggles` | Big ski goggles over the eyes, an orange-to-gold mirrored lens, a foam rim, and a wide elastic strap round the back of the head kept 2 cm off the head hit box (Joe's hair). Bare-headed zombies only. |
| EyePatch | eye_patch.py | `Head#Patch` | A black leather pirate eye patch over the right eye, its thin cord running diagonally round the head (2 cm off the hit box at the back). Bare-headed zombies only. |
| WeldingGoggles | welding_goggles.py | `Head#Goggles` | Round dark welding goggles pushed up on the forehead (not over the eyes), riveted metal cups, a leather strap round the head 2 cm off the hit box. Bare-headed zombies only. |

### Accessories

| Name | Script | Parts | What |
|---|---|---|---|
| Cigar | cigar.py | `Jaw#Cigar` | A fat half-smoked cigar clamped in the right corner of the mouth, angled down and out about 20 degrees, its tip a dim orange glowing ember (emission) inside grey ash. On the Jaw bone, so it moves when the mouth opens. Slot Mouth. |
| MardiGrasBeads | mardi_gras_beads.py | `Neck#Beads` | Three or four strands of cheap shiny plastic beads (purple, gold, green; tarnished and grimy) round the neck, hanging to different lengths on the chest. Slot Neck. |
| FlowerLei | flower_lei.py | `Neck#Lei` | A Hawaiian lei of wilted, faded fabric flowers (dull magenta, orange, white gone grey) round the neck and down the chest. Slot Neck. |
| BowTie | bow_tie.py | `Neck#BowTie` | A black or dark red bow tie at the collar under the chin, crooked. Clear of the jaw, which opens. Slot Neck. |
| DogTags | dog_tags.py | `Neck#Chain`, `Neck#TagsSwing` | Military dog tags: a ball chain round the neck (`Neck#Chain`), and the two stamped steel tags hanging on the upper chest as a swing part (`Neck#TagsSwing`, pivot where the chain meets them; on the Neck bone so it moves with the chain on bigger zombies). Slot Neck. |

### Retrofits (swing)

| Name | Script | Change |
|---|---|---|
| Noose | noose.py | Split the hanging cut rope end into its own part `Neck#RopeSwing` (pivot at the knot, where it hangs from). `Neck#Noose` keeps the rest. |
| PadlockChain | padlock_chain.py | Split the hanging torn length of chain (and nothing else) into `LeftForeArm#ChainSwing` (pivot where it leaves the loops). `LeftForeArm#Chain` keeps the loops and the padlock. |

### How they died (gore; any zombie)

| Name | Script | Parts | What |
|---|---|---|---|
| CompoundFracture | compound_fracture.py | `RightForeArm#Fracture` | A compound fracture of the right forearm: the jagged, splintered end of the broken bone (yellowed, marrow showing, blood dried on it) sticking 4 to 6 cm out through a torn hole on the outer side a little above the wrist, with torn skin and sleeve flaps round it. Slot RightArm. |
| GutLoop | gut_loop.py | `Spine1#Gash`, `Spine1#GutSwing` | A torn-open wound low on the belly, left of center: the ragged gash with its curled rim (`Spine1#Gash`), and a loop of dark grey-purple intestine hanging out of it 20 to 25 cm (`Spine1#GutSwing`, pivot at the gash where it comes out). Slot Belly. |
| ExposedRibs | exposed_ribs.py | `Spine2#Ribs` | The left side of the chest torn open from under the armpit down about 18 cm: three or four ribs showing, yellowed and wet, dark flesh between them, a torn rim of skin and shirt. Slot Chest. |
| ExposedSpine | exposed_spine.py | `Spine2#Vertebrae`, `Spine1#Vertebrae` | A long tear down the middle of the back with the knobbly spine showing through: five or six vertebra knuckles, dark wet flesh either side, a torn shirt rim. Split across Spine2 and Spine1 so it bends with the back. Slot Back. |
| TurningBite | turning_bite.py | `LeftShoulder#Bite` | The bite that turned them: a mouth-sized chunk torn out where the neck meets the left shoulder, a ring of human tooth marks round the rim, dark wet flesh, and a bruised, infected edge (dark purple-green spreading 2 to 3 cm). Slot LeftShoulder. |
| ChewedCalf | chewed_calf.py | `RightLeg#Calf` | The back of the right calf chewed away: a ragged hollow down to the shin bone (a strip of yellowed bone showing), short rigid torn strips of muscle hanging, dark blood down the leg. Slot RightLeg. |

### Rare showpieces (about 1 zombie in 40; any zombie)

| Name | Script | Parts | What |
|---|---|---|---|
| StopSign | stop_sign.py | `Spine1#Sign` | A STOP sign on its bent steel U-channel post, rammed through the belly from the front and out the back: the octagon (faded red, dented, two bullet holes, the white letters dirty) about 35 cm in front of the belly, tilted down and sideways; the post through the body; its torn bottom end 30 cm out the back with a clump of concrete still on it. Slots Belly, Back. |
| CinderBlock | cinder_block.py | `RightLeg#Cuff`, `RightLeg#ChainDrag`, `RightLeg#BlockDrag` | A rusty shackle locked round the right ankle (`RightLeg#Cuff`, near the bottom of the shin bone, clear of the foot). The chain (`RightLeg#ChainDrag`): exactly 1.0 m of heavy rusty chain, straight and horizontal, running from its pivot at the shackle's ring straight back along +Y (behind the zombie); the game stretches it and aims it at the block. The block (`RightLeg#BlockDrag`): a cracked, chipped grey cinder block with the chain's last link through one of its holes, upright as it would lie on the ground, its pivot where the chain enters it, exactly 10 cm above the block's bottom face. The game drags it along the ground behind the zombie. Slots RightLeg, LeftLeg. |
| Harpoon | harpoon.py | `Spine2#Harpoon`, `Spine2#RopeSwing` | A speargun harpoon through the chest from behind: the barbed steel head out the front right of center, the shaft out the back about 40 cm, and a short tail of frayed yellow-grey rope hanging off its end (`Spine2#RopeSwing`, pivot at the shaft end, about 30 cm long). Slots Chest, Back. |
| Pincushion | pincushion.py | `Spine2#Arrows`, `Spine1#Arrows`, `LeftArm#Arrows`, `RightUpLeg#Arrows` | Someone's last stand: eight arrows (reuse `arrows.py`'s arrow, with a mix of fletching colors and a couple snapped): three in the upper back, two in the lower back, one in the left upper arm, one in the right thigh, one in the chest from the front. Slots Back, Chest, LeftArm, RightLeg. |
| Bumper | bumper.py | `Spine1#Bumper` | A torn-off half of a rusty chrome car bumper (a corner and part of the face, bent, the chrome peeling) wedged into the right side under the ribs, the jagged torn end buried in the body, the rest jutting out and back about 50 cm. Slots Chest, Belly. |

**After the review (2026-11-03):** kept every eyewear, accessory and showpiece model except the Bumper (from every angle it read as a box strapped to the lower back; cut). Fat zombies never get a Cigar: their puffy faces bury it wherever it goes. DogTags hang from the Neck bone so they move with their chain, and the C# moves Neck parts forward with the chest (at least 8 cm on fat zombies).

**Gore review (2026-11-03):** each wound is a raised torn hole built on the skin measured on Joe (a sunk hole would vanish under the zombie's own mesh). Kept the fracture, gut loop, ribs, spine and chewed calf. Cut the TurningBite: from the front it read as a pale lump on the shoulder, not a bite. The torso and calf wounds only go on regular builds. A fat zombie's belly, side and back sit 3 to 8 cm outside a scaled piece and bury them. A woman's chest side hides the ribs and her slimmer calf leaves that wound standing off.
