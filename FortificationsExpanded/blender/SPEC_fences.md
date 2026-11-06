# Fences (Picket Fence, Post-and-Rail Fence): model spec for the integrator

Scripts: `blender\picket_fence.py`, `blender\post_rail.py`, both on the shared helper module `blender\fencekit.py` (new;
needs `blender\trapkit.py` and the existing `blender\textures\weathered_planks` and `metal_plate_02` / `rust_coarse_01`
sets, so **no new texture downloads**; `fetch-textures.ps1` is unchanged).

Run exactly like the other families (see `src\build-models.bat`):

    blender -b --factory-startup --python blender\picket_fence.py -- <unity\Assets\FortificationsExpanded\PicketFence> <unity\Build\previews> <UIAtlases\ItemIconAtlas\DementiveFortPicketFence.png> [all|reuse|export]
    blender -b --factory-startup --python blender\post_rail.py   -- <unity\Assets\FortificationsExpanded\PostRail>     <unity\Build\previews> <UIAtlases\ItemIconAtlas\DementiveFortPostRail.png> [all|reuse|export]

Optional environment variables for cheap runs: `FENCE_DEVICE=CPU`, `FENCE_TEX=1024` (atlas size, default 2048),
`FENCE_BAKE_SCALE=0.3` (bake sample scale), `FENCE_SAMPLES`, `FENCE_RESCALE` (previews). The delivered files were baked
at 2048 with `FENCE_BAKE_SCALE=0.3` (a final bake at full samples is fine but not needed).

Already produced (this phase) into `unity\Assets\FortificationsExpanded\PicketFence\` and `...\PostRail\`:
`<Family>{Section,Corner,Gate}.fbx` plus `<Family>_Albedo.png / _Normal.png / _RMOM.png` (one shared material per
family, named `PicketFence` / `PostRail`), previews in `unity\Build\previews\picket_*.png` and `postrail_*.png`, item icons
`UIAtlases\ItemIconAtlas\DementiveFortPicketFence.png` and `DementiveFortPostRail.png`.

## Things to add to shared files (not done by me)

- `build-models.bat` MODELS: `picket_fence:PicketFence:DementiveFortPicketFence post_rail:PostRail:DementiveFortPostRail`
- `FortBuilder.Families`: `("PicketFence", new Color(0.55f, 0.52f, 0.46f))` (pale paint flakes and grey splinters) and
  `("PostRail", new Color(0.5f, 0.46f, 0.4f))`.
- `FortBuilder.Footprints`: `("PicketFenceGate", 2f, 1f), ("PostRailGate", 2f, 1f)` (sections and corners are 1 x 1).
- `staged-models.txt` (the intact-stage models whose MeshDamage needs DMG0..DMG2): `PicketFenceSection`,
  `PicketFenceCorner`, `PostRailSection`, `PostRailCorner`.
- Preview "finished" list in `BuildAndPreview`: add `PicketFenceSection`, `PicketFenceCorner`, `PostRailSection`,
  `PostRailCorner` if previews against vanilla sandbags are wanted (gates are picked up by the `Gate` suffix already).

## Common conventions (identical to palisade.py / chainlink.py)

- Meters, Blender Z-up, model bottom at z = -0.5 (the ground), fence line along X at y = 0, **front is -Y** (the side
  the leaves swing to). Origin at the cell centre.
- Section and corner FBX: three meshes `DMG0` (intact), `DMG1` (damaged), `DMG2` (wreck) at the same origin plus an
  empty `FX` (the burst point), one material. Use `MeshDamage = "DMG0,H,DMG1,0.65H,DMG2,0.3H"` as for the other families.
  Wrecks keep everything inside the 1 x 1 cell except a few centimetres of debris (listed per piece).
- Corner: the post is at the origin, the fence runs toward +X (front -Y) and toward +Y (front -X, the mirror image), so the
  outside of the corner is (-X, -Y), exactly like `PalisadeCorner`. Footprint 1 x 1; the arms end at the cell edges.
- Gate FBX: objects `Frame` (the two gate posts and their pintles, static; give it the mesh collider), `LeftLeaf` and
  `RightLeaf` (children of `Frame`, origin on the hinge axis, bottom z = -0.5; box colliders). Same names, same swing
  directions as `PalisadeGate`: **the existing `Leaves` table (LeftLeaf +90, RightLeaf -90) is correct, no SlideLeaf**.
  The gate is 2 wide and centred on the origin (x -1 .. 1; Blender LeftLeaf is the -X one); if the engine anchors a 2-wide
  multiblock at its first cell instead, give it the same `ModelOffset` the 2-wide `HescoDouble` needs. Model width is
  within 2.0 m (picket 1.998, post-and-rail 2.00 including the posts).
- Every part of every model is solid mesh (no cut-out alpha, no second material).

## PicketFenceSection / PicketFenceCorner / PicketFenceGate  (display: "Picket Fence", "Picket Fence Corner", "Picket Fence Gate")

| | Section | Corner | Gate |
|---|---|---|---|
| footprint | 1 x 1 (x +-0.5, y -0.04 .. 0.13) | 1 x 1 | 2 x 1 (x +-1.0, y -0.05 .. 0.09) |
| height | slats 0.96 .. 1.10 m, post 1.12 m (tallest point 1.146 m, z up to 0.646) | post 1.18 m (to z 0.68) | posts 1.2 m, slats to 1.09 m |
| triangles | DMG0 1274, DMG1 1380, DMG2 1298 | 1010, 1090, 862 | Frame 412, each leaf 1196 (2804 total) |

- Look: eight different boards per cell (pointed, flat, dog-eared, warped, a raw grey replacement slat, a wide one, a short
  one), 3.5 cm gaps, white-grey paint flaking to weathered brown wood, algae and mud at the foot, nails with a few missing or
  bent, two rails (z 0.27 / 0.78 above the ground) and a post behind (post at y 0.03 .. 0.12, so a run has one post a metre).
  Photo texture (weathered_planks) baked into one 2048 atlas; albedo mean sRGB (0.36, 0.32, 0.28), roughness 0.73.
- Stages: DMG1 = three slats out (one hangs from a nail, one snapped with its top on the ground, one kicked out and leaning
  against the front, bent nails left in the rail), the whole fence leaning 7 degrees back; DMG2 = slats snapped to 0.3 - 0.5 m
  stubs, the top rail broken in two and lying, the post snapped to a 0.44 m stump (leaning 12 degrees), tops scattered on the
  ground; the wreck stands about 0.64 m high at its tallest.
  Debris outside the cell: DMG1 up to 0.03 m beyond x +-0.5, DMG2 the post top reaches x 0.57.
- FX (model coordinates): section (0, -0.08, 0.05), corner (-0.03, -0.10, 0.05): in front of the slats at 0.55 m above the ground.
- Collision / see-through: a section blocks 81 % of a ray grid from the front (the gaps are 3.5 cm, 19 % get through), so
  **treat the picket fence as solid for bullets, arrows and sight** (default `Collide`, no SHOOT_THROUGH). Zombies climb it
  (1.1 m). Slats are the "bits that are debris" (harvest: wood).
- Gate: two leaves, each seven slats (one raw, one wide) on two rails with a Z-brace, two iron strap hinges, a slide bolt on
  the right leaf and a keeper loop on the left. Hinge axes x = -+0.875, y = -0.035. Leaves swing out toward -Y, 90 degrees
  (checked: clear of the posts at 0, 5, 10, 20, 45, 90 degrees). Closed, the leaves are 3 cm apart.

## PostRailSection / PostRailCorner / PostRailGate  (display: "Post-and-Rail Fence", "Post-and-Rail Corner", "Post-and-Rail Gate")

| | Section | Corner | Gate |
|---|---|---|---|
| footprint | 1 x 1 (rails x +-0.496, y -0.07 .. 0.07) | 1 x 1 | 2 x 1 (x +-1.0, y -0.07 .. 0.08) |
| height | post 1.205 m, top rail 1.13 m | post 1.22 m | posts 1.22 m, leaf to 1.15 m |
| triangles | DMG0 956, DMG1 832, DMG2 1008 | 842, 842, 982 | Frame 412, each leaf 760 (1932 total) |

- Look: one weathered, checked, silvered split post in the middle of the cell (13 x 12 cm, three through-mortises), three
  split rails (z 0.38 / 0.74 / 1.08, 10 x 5.5 cm, tapered ends, rough irregular outline) running through it from cell edge to cell
  edge, rusty wire stapled to the post and the top rail with a loose end hanging. Albedo mean sRGB (0.40, 0.37, 0.33).
  Rails of neighbouring cells meet end to end (4 - 8 mm gap) midway between two posts; there is no way around that with posts
  at the cell centre (it keeps the cell symmetric under the game's 180 degree rotation).
- Stages: DMG1 = the top rail snapped (left half stays, right half lying in front), the bottom rail dipping, the post
  leaning 4 degrees; DMG2 = the post leaning 18 degrees, the lower rail dropped at one end, the other rails and a broken top rail
  lying on the ground, wire hanging loose and a coil on the ground.
- FX (model coordinates): section (0, -0.10, 0.20), corner (-0.05, -0.12, 0.20): in front of the rails at 0.7 m above the ground.
- Collision / see-through: **rails are see-through**: 61 % of a front ray grid (z 0.05 .. 1.15) passes the section, 58 % passes
  a closed gate. Recommend `Collide = SHOOT_THROUGH` ("movement,melee,rocket") like chain-link, so bullets and sight pass the
  gaps. The BoxCollider FortBuilder adds around DMG0 is a solid box 1.2 m high, 0.14 deep; with SHOOT_THROUGH that is fine.
  Zombies climb it (1.2 m).
- Gate: two framed leaves (three rails, two back stiles, a Z-brace, strap hinges on the rail ends, a slide bolt and a
  keeper), 2 wide, posts at x = +-0.935. Hinge axes x = -+0.875, y = -0.031 (the leaf's front face). The hinge eye barrel
  overlaps the post face by 7 mm on purpose (a barrel hinge embedded in the post). Leaves swing out toward -Y, 90 degrees.
  Closed, the leaves are 3 cm apart; a rail-gate leaf is open mesh, so it is **see-through** as well.

## Doubtful / unfinished (honest list)

- Not seen in the game shader (no Unity run in this phase): the albedo values follow the palisade calibration, but the white-grey
  paint (mean about 0.5 in the paint areas, cool grey) may read brighter than the surrounding vanilla wood in game; the
  `value`/`paint_rgb` arguments in `picket_fence.py` / `fencekit.fence_wood` are the knobs.
- The picket paint has a slight blue-green cast in the previews (it is the preview lighting plus the algae tint); in the
  atlas the paint is (0.21, 0.21, 0.19) linear.
- Post-and-rail wire is one thin tube (about 100 triangles) per piece; at distance it will alias to thin dark lines.
- Rail ends meet mid-span between posts (see above); the picket fence has a post a metre.
- Gate frames have no damage stages (single `DMG0` stage under `Door`), no wreck model for gates. Corners have full stages.
- Previews were rendered at reduced sample counts and size (CPU, 24 samples) because the machine was shared; geometry and
  textures are final.
- Debris pieces lying in DMG1/DMG2 reach a few cm outside the 1 x 1 cell (listed above); the BoxCollider is clipped to the
  footprint by FortBuilder anyway.

## Proposed placement (for world / loot dressing, if wanted)

- Picket Fence: residential and suburban POIs, farms and rural homesteads; common in grass / forest / plains biomes, rare in
  desert and snow. Post-and-Rail: farms, ranches, camps, roadsides; common in plains, forest and desert edges, rare in
  burnt forest and snow.
