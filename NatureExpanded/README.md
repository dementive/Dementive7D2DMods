# Nature Expanded

Wildflower drifts and 46 new plants across every biome, so the fields aren't all goldenrod, cotton and grass. Each
plant has its own 3D model that sways in the wind with the game's own plant shader. For 7 Days to Die V3.4.

A standalone mod: it needs no other mod. Plants are placed by the game's world generation, so in co-op the server
decides them and every player sees the same. **Only ground generated after you install it gets the new plants**: in
an existing world, head somewhere you haven't been, or start a new world.

## What grows where

Plants grow in **drifts**: small patches of one species, a few blocks across, that thin out into the meadow with a
few companions mixed in, so a meadow has a clump of lupine here and a scatter of poppies there. The pine forest's old flower clusters (goldenrod, cotton and
chrysanthemum) are now a mixed meadow of every wildflower, with those three thinned to a quarter.

| Where | Plants |
|---|---|
| Pine forest meadows | Poppy, Lupine, Cornflower, Oxeye Daisy, Indian Paintbrush, Black-Eyed Susan, Coneflower, Queen Anne's Lace, Red Clover, Wild Bergamot, Chicory |
| Forest floor (under the trees) | Fern, Fly Agaric, Porcini, Trillium, Wild Strawberry, Foxglove, Wild Rose, Elderberry, Sumac, Mossy Log |
| Lake and river shores | Cattail, Reeds, Blue Flag Iris, Marsh Marigold (in the burnt forest and wasteland fewer, and only reeds and cattails; reeds in the desert) |
| Burnt forest | Fireweed, Charred Shrub (putting out new shoots), Morels, Lupine coming back |
| Desert | Prickly Pear, Barrel Cactus, Ocotillo, Flowering Agave, Desert Marigold, Globemallow, Sagebrush, Evening Primrose |
| Snow | Alpine Aster, Heather, Winterberry, Snowdrop, Juniper |
| Wasteland | Thistle, Silver Sage, Wild Mustard, Curly Dock, Dead Brush |

**Grasses:** 20 new grasses, mixed through the ground and taking over whole patches of hillside, so the ground isn't
all one grass. They're drawn just like vanilla's grass (the mod adds them to the game's own grass texture sheet), so
they cost no more.

| Where | Grasses |
|---|---|
| Pine forest | Mostly green: Tufted Hairgrass, Orchard Grass, Foxtail, Timothy, Clover and Plantain, Sedge, Bracken and Horsetail (more of the last three under the trees and by water), with the odd Wild Oats, Dry Bunchgrass, Redtop or Sheep Sorrel as an accent. Vanilla's tall grass is one grass among them. |
| Desert | Blue Grama, Needlegrass, Dry Bunchgrass |
| Snow | Frosted Tussock, Cotton Grass |
| Burnt forest | Burnt Stubble, Green Shoots |
| Wasteland | Cheatgrass, Foxtail Barley, Dry Bunchgrass |

**Trees:** paper birch in the pine forest, in four shapes (straight, leaning, a clump of trunks, a young one), among
the pines and oaks and now and then alone in a meadow. They're drawn by the game's own SpeedTree shader, so they're lit,
fade and sway in the wind like vanilla's trees, and they chop and fall like them.

**Harvesting:** plants give plant fibers like grass (bushes a few more), porcini and morels give mushrooms, fly agaric
is poisonous (a fiber, no food), and a mossy log chops into wood.

## Building it

- `blender/`: one script per plant (`FLORA.md` has the specs and rules; `poppy.py` is the worked example), on
  `naturekit.py` and `zkit.py`. Each writes its model to `unity/Assets/NatureExpanded/Models/<Name>/` and previews to
  `unity/Build/previews/`:

  ```
  blender -b --factory-startup --python poppy.py -- <unity models folder> <preview folder>
  ```

- `src\build-bundle.bat`: Unity 2022.3.62f2 turns the models into block prefabs, builds
  `Resources\natureexpanded.unity3d`, and renders each plant in the game's plant shader beside vanilla cotton
  (`unity\Build\plants\<Name>.png`) and all of them in a row (`lineup.png`).
- `Scripts\NatureExpanded\gen_nature.py`: writes `Config\blocks.xml`, `Config\biomes.xml` and `Config\Localization.csv`
  from its plant and biome tables (run it after the bundle, which records each plant's height).
- `blender/grass/grass_tiles.py` renders each grass in `blender/grass/grasses.txt` from the side, and
  `src\build-grass.bat` turns the renders into tiles in the game's grass texture format, builds
  `Resources\natureexpanded-grass.unity3d`, and tries the copy on the game's own sheet (`unity\Build\grass\sheet.png`).
- `blender/trees/<tree>.py` (on `treekit.py`; `TREES.md` has the rules and specs) build each tree species' variants,
  and `src\build-trees.bat` turns them into SpeedTree prefabs (writing SpeedTree's per-vertex wind data from each
  tree's shape), builds `Resources\natureexpanded-trees.unity3d`, and renders them beside vanilla's trees
  (`unity\Build\trees\`).
- `src\build.bat`: builds `NatureExpanded.dll`, which:
  - moves each plant to the game's plant shader as it spawns;
  - copies the grass tiles into the empty corner of the game's grass texture sheet as it loads;
  - gives the trees copies of a vanilla oak's SpeedTree material with their own maps, and the game's wind;
  - grows the water's-edge plants along shores as world generation decorates each chunk (the biome tables can't see
    water).
