# Forest-floor ground cover (9 walk-through decoration blocks)

Scripts: `NatureExpanded/blender/<script>.py` on the shared `kit_ground.py` (new; built on naturekit/kit_forest/kit_shrub/zkit).
Run: `blender -b --factory-startup --python <abs script> -- <models dir> <previews dir>`. `NK_QUICK=1` skips the bake and renders 2 small previews.
Output: `NatureExpanded/unity/Assets/NatureExpanded/Models/<Name>/` (<Name>.fbx with <Name> + <Name>_LOD1, _Albedo/_Normal/_RMOM.png).
Previews: `unity/Build/previews/<script>_{stand,crouch,m3,close,top,lod,patch}.png`.
All: ground at z=-0.5, patch about 0.8-0.9 m with ragged, thinning rim and a few outlier pieces beyond it (extents below), no solid, no collider, no alpha textures, atlas 2048 (leaf/needle/moss pieces 1-2 above) except the last four built at 1024 (see notes).

| Name | Script | Display name | Tris / LOD1 | Height | Extent x / y (m) | Atlas |
|---|---|---|---|---|---|---|
| PineNeedleMat | pine_needle_mat.py | Pine Needle Mat | 2336 / 1138 | 3.7 cm | -0.56..0.52 / -0.54..0.67 | 2048 |
| BirchLeafLitter | birch_leaf_litter.py | Birch Leaf Litter | 2622 / 1514 | 7 cm | -0.49..0.49 / -0.58..0.46 | 2048 |
| MapleLeafLitter | maple_leaf_litter.py | Maple Leaf Litter | 2088 / 1164 | 9.4 cm | -0.55..0.50 / -0.61..0.54 | 2048 |
| OakLeafLitter | oak_leaf_litter.py | Oak Leaf Litter | 2580 / 1492 | 8.7 cm | -0.50..0.49 / -0.46..0.44 | 2048 |
| MossPatch | moss_patch.py | Moss Patch | 2268 / 1012 | 7.5 cm | -0.36..0.41 / -0.36..0.52 | 2048 |
| TwigPile | twig_pile.py | Twig Pile | 2422 / 892 | 16 cm (crown; ~12 typical) | -0.46..0.54 / -0.37..0.42 | 1024 |
| PineconeCluster | pinecone_cluster.py | Pinecone Cluster | 2106 / 1342 | 11 cm | -0.48..0.65 / -0.48..0.46 | 1024 |
| AcornScatter | acorn_scatter.py | Acorn Scatter | 2503 / 1423 | 8 cm | -0.39..0.46 / -0.57..0.50 | 1024 |
| LichenStone | lichen_stone.py | Lichen Stone | 1204 / 749 | 10 cm | -0.37..0.46 / -0.25..0.34 | 1024 |

Contents: PineNeedleMat ~800 needles in bundles on a needle-duff layer, 5 short snapped twigs, 3 loose cone scales. Birch/Maple/Oak ~150-170 real leaves each (birch/oak a share curled, some damp-dark) resting on each other on a duff layer. MossPatch ~80 small mounds + 3-4 stones + half-buried twig. TwigPile 8 branches, ~50 twigs, forks, 9 bark flakes, 12 caught leaves. PineconeCluster 6 cones of ~60 spiral scales each (one half sunk), needles. AcornScatter ~20 acorns (bare, capped, loose caps, 2 gnawed, 2 split) on oak leaves. LichenStone one 38 cm flat-topped faceted stone, two small ones, moss at the foot.

## Proposed handling (nothing is defined in code)
- Walk-through decoration blocks (no collision), placed by worldgen like the wildflowers; no shadows needed far away; LOD1 shares the atlas.
- Placement: PineNeedleMat and PineconeCluster: pine/spruce forest (common / uncommon). BirchLeafLitter: birch and mixed forest (common). MapleLeafLitter: mixed/autumn forest (uncommon). OakLeafLitter and AcornScatter: deciduous/mixed forest (common / rare, acorns near oak). MossPatch: damp forest, near streams and shade (common). TwigPile: any forest (uncommon). LichenStone: forest and meadow edges (uncommon-rare).
- Harvest (suggestion): leaf litters and PineNeedleMat give nothing; TwigPile 1-2 wood (or a few sticks if such an item exists); PineconeCluster plant fiber (or pinecones if vanilla has an item); AcornScatter nothing or 1-2 nuts as a food/crafting item if wanted; MossPatch nothing (or plant fiber 1); LichenStone 1-2 stones.
- Mods that do not exist in the game's tag set should be left out; any block name collisions with other pieces are the integrator's call.

## Notes and weak spots
- Bundle texture size: FLORA.md says non-solid plants drop to 512 in the bundle; these pieces want 1024-2048 (leaf veins, needles, bark are about 10-20 px/cm at 2048). TwigPile, PineconeCluster, AcornScatter and LichenStone were baked at 1024 (4-6 px/cm on twigs, duff and needles) to save time; re-run the scripts (change `size=1024` to 2048) for crisper results.
- The packed layer (`*Duff`) is a flat mulch texture with real low relief; at 0.3 m it can read a little like gravel. Leaves are fans of 8-30 triangles, so from very close the outlines are polygonal.
- TwigPile: the thick branches sit around the rim so it reads partly as a ring/nest; centre is lower than ideal. Tops out at ~16 cm.
- Footprints spill 0.1-0.2 m past +-0.45 through sparse outlier pieces (as the brief allows).
- Everything in the previews was checked at stand/crouch/3 m/close; the far LODs keep the dark base layer and about 35-60% of the pieces, enlarged.
- Needle quads were found with downward normals once (AO baked black); fixed in kit_ground.needle_bundle and re-baked.
