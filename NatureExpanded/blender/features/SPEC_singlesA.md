# Single finds, set A (Nature Expanded features)

Six small "single find" props, built with the solid-feature pipeline. Scripts are in `blender/features/` (one per prop, all on the
shared `singleskit.py`: rounded-box and sweep geometry, an `ang` vertex attribute, litter/grass/weed/vine helpers, weathered wood,
corroded steel, oxidised aluminium, old rubber, pseudo-handwriting). Output: `unity/Assets/NatureExpanded/Features/<Name>/`
(`Name.fbx` with `Name` and `Name_LOD1`, `_Albedo/_Normal/_RMOM.png`, `Name_colliders.txt`). Previews:
`unity/Build/previews/features/<name>_*.png` (far = 7 m, mid = 3 m, close/detail = 1 m, back, top; a 1.8 m figure stands in them).
Unity was not run; nothing here is checked in the engine. Colliders were placed to lie inside the mesh bounds by construction, not verified.

Run (CPU only, 1024 atlas except the Wheelbarrow's 2048):
`blender -b --factory-startup --python <abs>\blender\features\<script>.py -- <abs features folder> <abs preview folder> [Name]`
Env switches for quick looks: `SK_LIVE=1` (no bake/export), `SK_FAST=1`, `SK_SHOTS=far,mid` (which previews).

| Name | Display name | Script | Footprint (cells x high x cells) | Triangles (LOD1) | Mesh extent | Atlas |
|---|---|---|---|---|---|---|
| TrailMarker | Trail Marker | trail_marker.py | 1 x 2 x 1 | 7455 (5288) | +-0.5 m, 1.81 m high | 1024 |
| Antlers | Shed Antlers | antlers.py | 1 x 1 x 1 | 6017 (4081) | +-0.5 m, 0.35 m high | 1024 |
| LoneBoot | Lone Boot | lone_boot.py | 1 x 1 x 1 | 7048 (5912) | +-0.5 m, 0.43 m (grass tips; the boot is about 0.25 m) | 1024 |
| OldTire | Old Tire | old_tire.py | 1 x 1 x 1 | 8868 (4932) | +-0.5 m, 0.47 m (tire top about 0.30 m) | 1024 |
| Wheelbarrow | Rusted Wheelbarrow | wheelbarrow.py | 3 x 1 x 1 (rectangular: sidecar has `rect`; x 3, z 1) | 10462 (7966) | x +-0.80, y -0.42..0.50, 0.66 m high | 2048 |
| LawnChair | Old Lawn Chair | lawn_chair.py | 1 x 1 x 1 | 8346 (7338) | +-0.5 m, 0.76 m high | 1024 |

Footprints come from the mesh extents (the export prints them; Unity's builder will confirm in feature-sizes.txt). Every mesh was kept
within +-0.52 m on a 1x1 prop (weeds, leaves, soil heap and sticks are clamped to it), so none grows to 3x3.
LOD1: the far mesh drops the lod-1 parts (small leaves, litter, half the grass) and decimates the lod-2 bodies (post, tire).

## Per prop

**TrailMarker** (a 4x4 post 1.8 m, leaning ~3 degrees, pointed arrow board hanging from its one remaining nail, faded red arrow,
two lines of scratched pseudo-handwriting that read as text and say nothing, lichen on one side, rot waist at the ground line,
bindweed up it, grass round the foot).
- Solid. Colliders: one capsule (r 0.04) down the post, one thin oriented box (0.62 x 0.02 x 0.14) for the board.
- Harvest: kind `timber` (MtreeWoodSmall, an axe gives resourceWood); count about 5 (a 0.002 m3 of wood: keep it small).
- Placement: `pine_forest` main 0.0003, `wasteland` 0.00012, `desert` 0.00008, `snow` 0.0001. Uncommon.
- Rotation: the board faces -y at export; rotatemax 3 is fine (the sign reads from all four sides' approach).

**Antlers** (a large shed with brow tine and three more, and a smaller, older one, both gnawed at the burr and at two tine tips with
fine parallel tooth marks, bleached on top, stained brown under, half under leaf litter, pine cones, a fern).
- Walk-through: Collide `melee` only. Two boxes (0.51 x 0.45 x 0.14 and 0.40 x 0.20 x 0.11) so a pick can hit them.
- Harvest: kind `bone` (existing: Mplants, resourceBone, count 1 to 6). It computes a count from the mesh volume; 2 is plenty.
- Placement: `pine_forest` main 0.0004 (next to AntlerShed01, same weight), `burnt_forest` 0.00015, `snow` 0.00012. Common.

**LoneBoot** (one leather work boot lying on its side, toe tipped up out of the dirt, heel and lower half sunk; leather crazed into a
net with pale scuffs at the toe, mold and salt tide-marks, eyelets, a few surviving laces and two dangling ends, the tongue lolling,
the collar slumped, moss and earth filling the opening and the heel).
- Walk-through: Collide `melee`, one box.
- Harvest: none sensible. Suggest a new kind `junk` (Mplants, no drop, or at most 1 resourceLeather if the item exists in V3.4) so the
  hit box can still be destroyed.
- Placement: any open ground: `pine_forest` 0.0003, `burnt_forest` 0.0002, `wasteland` 0.0003, `desert` 0.0002, `snow` 0.0001. Common.

**OldTire** (a rimless car tire on its edge, tilted 41 degrees and half sunk, sidewall crazed with ozone cracks and moulded
pseudo-lettering, tread bald in the middle with a patch of cord showing, mud in the grooves, moss on the lower sidewall, soil, leaves
and a weed heaped in the well; about 0.3 m above the ground: step-over height).
- Solid: the closed mesh is voxelized (13 boxes of 0.045 m voxels, margin 0.012).
- Harvest: none sensible (suggest the same `junk` kind, or a `scrap` kind giving 1 resourceScrapPolymers if present).
- Placement: `wasteland` 0.0004, `desert` 0.0003, `pine_forest` 0.0002, `burnt_forest` 0.0002. Common near anything built; the integrator
  may also add it to the road/ruin spawns.

**Wheelbarrow** (a steel-tubbed wheelbarrow knocked over on its side: tub rusted through in several holes with the old red paint
flaking, rim eaten away in places, rolled lip, a dent; one wooden handle rotted and snapped, the other split with a vine round it;
flat cracked tire on a rusty rim; soil and leaves in the tub with grass and a dock growing out of it).
- Solid: oriented box over the tub (0.58 x 0.46 x 0.27, so the open tub is a block, not walkable into), a capsule down each handle,
  a box for the wheel. Footprint 3 x 1 (the sidecar says `rect`).
- Harvest: kind `scrap`: new kind, material a metal one (Mmetal-type, 250 HP), item `resourceScrapIron` count about 6 with a pick or
  impact tag (a second drop of 2 `resourceWood` would be nice for the handles).
- Placement: `wasteland` 0.0002, `pine_forest` 0.00012, `desert` 0.00012. Rare. Because the footprint is 3 x 1, use BigDecorationRadius 2.

**LawnChair** (an aluminium folding lawn chair tipped over onto its side, frame tubes chalky with oxide and bled with rust from the
rivets, one arm bar bent, striped green and pale webbing mildewed and snapped strip by strip, the ends frayed, bindweed through the
seat and up the back post, grass through it).
- Solid frame: 16 capsules (r 0.011) down the tubes and cross bars; the webbing has no collider (it is mostly gone).
- Harvest: kind `scrap`, `resourceScrapIron` about 3 (or 2 iron and 1 cloth).
- Placement: `wasteland` 0.0002, `pine_forest` 0.00015, `desert` 0.00012. Uncommon.

## Weak spots (be honest)
- Not run in Unity or the game: texel density, shader result (the Feature_ plant shader), collider-in-bounds check, footprints are the
  printed extents only. The previews are Cycles renders of the baked atlas, not the game shader.
- LoneBoot: leather baked greyer than the live look (the leather reads as grey-brown dried clay at 3 m); the boot is small and low,
  readable only within a few metres. This is the weakest of the six.
- Antlers: the beam surface reads a little like driftwood at 1 m; tooth marks are mostly bump detail. The soil heap is a smooth dark
  disc without the litter-texture bite I wanted. The antler is propped up on its tines more than a real shed would be.
- Wheelbarrow: the tub's crack pattern is regular; the bindweed leaves are edge-on spikes; only one handle is easy to see. The
  atlas is 2048 and slow to bake (about 40 min on two low-priority threads here).
- LawnChair: the webbing is regular and the tubes still read a little clean/galvanised; the chair is only unmistakable from the
  side or above (lying on its side it is a flat frame from some angles).
- Leaf litter and grass are cheap cards (4 rows a leaf, 4-row blades): fine at 1 m, flat-shaded at 30 cm.
- The soil/litter "bed" under each prop is a low heap with a sunk rim, clamped to the cell; its edge shows against terrain unless the
  terrain is dark forest litter.
- TrailMarker sits on a leaning capsule, so a zombie or a bullet passing through the board's corner may miss; it is thin by design.
- Harvest kinds `junk` and `scrap` do not exist in gen_nature.py yet; I did not touch it.
