# Zombie gear and growth models: brief

The remnants (small props on any zombie) and the round-2 models have their own specs in `REMNANTS.md`.

Zombies Expanded bolts these models onto any zombie in 7 Days to Die: helmets and armor some zombies still wear, and
growths that show a zombie's mutation. Each is one Blender script here that builds the model with `zkit` (the
traps' model kit: parts, photo-textured materials, baking, export) and `zombiekit` (the reference skeleton, a
stand-in body, the per-bone export). `cut/hard_hat.py` (a model no longer built) is the worked example; read it, `zombiekit.py`, and the parts of
`zkit.py` you use. Traps Expanded's scripts (`../../TrapsExpanded/blender/*.py`) show more material and mesh
technique (custom node materials like `grease_material` in grease_slick.py, `push`/`solidify` helpers, dents).

## Coordinates and fitting

- Blender meters, Z up. The reference zombie (Joe, `skeletons/joe.json`) stands at the origin, feet at z = 0,
  facing **-Y**; its **left is +X**. It is in its bind pose: an A-pose, arms hanging out and down at 45 degrees.
- `zk.joe().pos("Head")` is a bone's pivot; `.center(bone)` and `.radius(bone)` its hit box (the body's
  thickness there); `.axis("LeftArm", "LeftForeArm")` the direction along a limb. `zk.body()` builds a grey stand-in
  from the hit boxes to fit against (it's only for fitting and previews, never exported).
- Useful numbers on Joe: Head bone (0, 0.035, 1.675), head hit box a capsule of radius 0.10 around a vertical axis
  through the bone, from z 1.545 to 1.845; brows at (+-0.03, -0.065, 1.745), eyes about 2.6 cm below them; Spine2 bone
  (0, 0, 1.23), chest hit box a capsule of radius 0.158, centered (0, 0.05, 1.34), z from 1.07 to 1.61; Neck
  (0, 0.035, 1.595). The stand-in is a little slimmer than the real zombie's skin: leave 1 to 2 cm of clearance.
- Mark every piece with `zk.on(obj, bone)` (or `zk.on(obj, bone, "Name")` to make it its own part, which the
  game can knock off or drop alone, e.g. `zk.on(plate, "Spine2", "Chest")`). It moves with that bone in game, so
  pick the bone that carries that part of the body: Head, Neck, Jaw, Spine1/Spine2/Spine3, LeftShoulder,
  LeftArm (upper arm), LeftForeArm, LeftHand, finger bones (LeftHandIndex1/2...), LeftUpLeg, LeftLeg, and the
  Right* twins.
- In game each piece is scaled to the zombie's own hit box on that bone (a fat cop's chest is about 1.4 times
  Joe's, a nurse's head 0.85 times), and head and chest pieces are moved to match where its head or chest sits. So
  build for Joe and keep pieces hugging the body; don't rely on exact skin contact.
- `zk.export(Name, pieces, folder)` bakes everything into one 1024 atlas and writes `<Name>.fbx` plus textures.
  Call it once per model with all its pieces.

## Look

- Like the game's own art: photo-real and worn. Use `tk.photo_material` / `tk.grimy` with the Poly Haven sets in
  `textures/` for hard materials (scuffed paint, scratches, worn edges, grime in the creases, blood spatter where it
  fits). Look at the game's item icons in `<game>/Data/ItemIcons` for the target style (e.g. `armorMinerHelmet.png`,
  `armorBikerHelmet.png`, `armorCommandoHelmet.png`, `armorAthleticHelmet.png`, `armorRaiderHelmet.png`,
  `armorEnforcerHelmet.png`, `hubCaps.png`, `ammoGasCan.png`), where `<game>` is
  `C:/Program Files (x86)/Steam/steamapps/common/7 Days To Die`.
- Growths are grounded, not magic: rot, infection, bone, fungus. Wet, veiny, bruised colors (yellowed bone,
  purple-red sacs, pale cream fungus), with low roughness where wet. Write custom node materials for flesh
  (noise-driven color, veins with Voronoi, bump), registered with `tk.finish` so the baker sees them.
- The game draws these with its opaque model shader: no transparency. A glow (e.g. embers, spores) can go in the
  emission signal of `tk.finish(..., emission=...)`.
- Keep colors as dark and dirty as the zombies they sit on. The game's zombie textures are dark; a near-white or
  strongly saturated albedo (bright ice, pink flesh) reads as a flat cut-out in game even when it looks right in
  Blender. The organic models end in a `tk.grade(...)` that pulls value and saturation down for this, and the
  growths' skin patches get a dark, ragged rim so they read as torn through the clothes, not laid on top.
- Budget: about 3,000 triangles a model (organic sets up to 5,000 across all their pieces). One 1024 atlas.

## Build and check

    blender -b --factory-startup --python-exit-code 1 --python blender/<script>.py -- unity/Assets/ZombiesExpanded/Models unity/Build/previews > unity/Build/blender-<script>.log 2>&1

(from `ZombiesExpanded/`, with Windows paths: wrap them with `$(cygpath -aw ...)` in Git Bash; `-w` on a relative path writes to `C:/unity/...`). The script writes
`unity/Assets/ZombiesExpanded/Models/<Name>/` and previews `unity/Build/previews/<script>_{front,back,side}.png`
via `zk.previews(...)`; add close-ups where useful. Look at the previews and fix what looks wrong (floating,
clipping into the body, too clean, too big) before you're done. Don't run Unity (the main session builds the
bundle and renders every model on the real vanilla zombies), and don't edit `zkit.py` or `zombiekit.py` (other
models are being built at the same time): put helpers in your own script.
