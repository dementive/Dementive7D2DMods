# Graphics Expanded

Better color, fog, shadows and draw distances, on top of whatever the video menu is set to. Everything works as an
adjustment to vanilla, so the game's own effects (biome fog, weather, night, brightness) keep working.

- **Look presets**: Vanilla, Natural (the default: a little more contrast, color and warmth, less grey haze, gentle
  dynamic grading) and Cinematic (filmic ACES tonemapping, warm tint, film finish, full dynamic grading). Or set each
  value yourself.
- **Hold Home** in game to see vanilla, and let go to see yours again. Look and shadows switch; draw distances stay.
- **Color**: tonemapping (vanilla, neutral or ACES), exposure, contrast, saturation, white balance, tint.
- **Atmosphere**: fog density and fog tint.
- **Film**: vignette, film grain and bloom strength.
- **Dynamic grading**: the look shifts by itself, blending smoothly. Golden light around sunrise and sunset, cool
  muted moonlight at night (never brighter), greyer in rain and storms, colder in snow, and a red tint with thicker
  red fog under the Blood Moon. Time of day and weather fade the more enclosed you are, so a lit room at night doesn't
  turn blue. Each has a strength slider.
- **Shadows**: sun shadow distance past the menu's 300 m (up to 800 m) and resolution past its 4096 (8192), keeping
  close shadows as sharp. Contact shadows (the game's own, normally only at High shadow quality and above) on at any
  quality, with adjustable length.
- **Detail**: level of detail distance, tree distance (+128 or +256 m), grass distance (150 or 200 m, the menu stops
  at about 112 m) and forced 16x texture filtering.
- **Weather**: in rain, ground, roofs and roads turn dark and glossy and reflect the sky and lights, with a light sheen
  on walls and rippling puddles on flat ground. In snowfall, snow settles on roofs, roads, cars and the tops of blocks,
  flattest first, with a fine grain that sparkles in the sun. Both build up while it falls and wear off after (dry in
  about five minutes, melted in about ten), and anything under a roof stays dry. Zombies and players get wet and
  snowy too.
- **Sunbeams and height fog**: real shafts of sunlight (and faint moonlight) through windows, doorways, trees and
  ruins, made from the game's own shadows, with dusty air indoors so beams through windows show. Fog lies in the low
  ground and over water in drifting banks with wisps rising off them. A clear afternoon has next to none: it gathers
  through the night, is thickest at dawn and burns off by mid-morning, and comes with rain, snow, overcast skies and
  the Blood Moon. Quality from Low to High, or Off. Only the sun and moon: lamps and torches are Torch's.
- **Distance haze**: far hills, trees and buildings soften into the color of the air, while the first 150 m stay crisp.
  On a clear day the air takes the sky's hue (blue by day, warm at sunrise and sunset), greying under cloud, rain and
  snow, with a warm glow towards the sun. The sky itself is left alone.
- **Water**: lakes, rivers and pools near and far, clear in the shallows and deep blue-green further down, bending
  what's under them, reflecting the sky and shore (on High also the trees and buildings around, traced across the
  screen), with the sun's glint, foam along the edges and rings when it rains. Quality Medium or High, or Off for the
  game's water, and a Waves slider.
- **Ground**: photoscanned ground textures. Most of the game's 24 ground layers (rock, soil, gravel, forest floor,
  asphalt, snow) are swapped for photographed sets from Poly Haven, each matched to the layer it replaces in color,
  contrast, normal depth and height, so every biome keeps its palette and the layers blend as before. Up close it's
  real moss, leaf litter and weathered rock, tiled twice as densely as the game's textures so it stays sharp; far hills
  keep their rocky structure. Needs the texture pack (see
  Building) and about 400 MB of video memory. **Distant terrain** keeps more of far hills' shape, and the ground keeps
  its full textures twice as far out (High) or four times (Ultra).
- **Distant forests**: past the tree distance the game draws no trees at all, so far hills are bare. Every tree out
  there is drawn to the horizon as a lightweight picture of the game's own model, photographed from eight sides when a
  world loads. They take the game's sunlight, fog and haze, and give way to the real trees wherever the game draws them.

The shadow and detail settings start at "Video menu", so they follow the game's own until you change them.

## Install

Drop the `GraphicsExpanded` folder into `7 Days To Die/Mods/`. It needs EasyAntiCheat off (it has C# code) and uses
the game's own `0_TFP_Harmony`.

It runs on the client only. In multiplayer each player picks their own settings, nothing is sent to the server, and
the server doesn't need the mod. Dynamic grading and the weather effects only read the world time, weather and blocks
every client already has.

## Settings

With [Gears](https://www.nexusmods.com/7daystodie/mods/4017) installed, every setting is on the mod's page in the
Mods menu (main menu or in game). Gears 8.0.0 also needs [Quartz](https://www.nexusmods.com/7daystodie/mods/2409)
(v10 for V3.4) even though its page doesn't say so: without it, its Mods menu logs "Could not load file or assembly
'Quartz'" every frame. Changes preview live as you move them; Apply keeps them, Back undoes them. The
compare key can be rebound there too.

Without Gears the mod runs the Natural preset, and the `gfxe` console command (F1) can turn it off or switch presets
for the session:

```
gfxe                  show the current settings
gfxe on | off         turn the whole mod on or off
gfxe preset <name>    vanilla, natural or cinematic
```

For testing and tuning:

```
gfxe weather                    how wet and snowy things are now (also written to the game log)
gfxe weather wet <0-1>          set it, to see it without waiting for rain
gfxe weather snow <0-1>         the same for snow
gfxe weather debug              show the sky check: cyan is open to the sky, magenta is covered
gfxe atmosphere                 how the sunbeams and height fog are running, and what they hold mid-screen
gfxe haze                       how the distance haze is running
gfxe water                      how the water is running
gfxe water debug                show what the reflections find: red screen-space hits, green the reflection's share,
                                blue the shore foam
gfxe shots                      two screenshots of the view, with and without the mod's look, to the Screenshots
                                folder (status lines go to the game log)
gfxe materials                  write the block and terrain materials and textures to the game log
gfxe terrain                    how the far terrain and the ground's textures are set
gfxe terrain table              write the terrain's per-texture settings to the game log
gfxe terrain export             save the 24 ground textures as images to GraphicsExpanded/TerrainExport in the
                                game's user folder, for build-terrain.bat to match the texture pack to
gfxe terrain tiling <x>         repeat the photoscanned textures x times as often as the game's did (default 2;
                                more is sharper up close, with smaller pebbles and leaves)
gfxe trees                      how the distant forests are running: trees, kinds, and where the game's own stop
gfxe trees save                 save the pictures of each kind of tree to GraphicsExpanded/Trees in the user folder
gfxe trees on | off             turn the distant forests on or off for this session
gfxe trees debug                draw them bright magenta to see where they are (again to stop)
```

## Works with

- **Torch**, which handles lights and global illumination. This mod leaves local lights alone, and when Torch limits
  the sun's shadow cascades, a longer shadow distance keeps its cascade count.
- **Gears**: optional. `GearsAPI.dll` ships in this folder so the mod loads without it; it must be the same version
  as the installed Gears (3.0.0 for Gears 8).

## How it works

- Color and film: the player camera's post-processing profile (Unity's Post Processing Stack v2), saved as vanilla
  had it the first time it's seen and adjusted from there. Vanilla uses a custom tone curve with neutral grading and
  no vignette or grain.
- Dynamic grading (`GfxMood`): every frame, from the world time against `SkyManager`'s dawn and dusk, the weather's
  rainfall and snowfall, `SkyManager.BloodMoonVisiblePercent` and the player's `GetAmountEnclosed`, eased over about
  three seconds and added to the look.
- Presets: a preset other than Custom always matches its rows, so when the saved settings load, its values are put
  back on them. That carries new rows and retuned presets over to players' saved settings.
- Fog: `SkyManager` sets it every frame; patches redo it with the density scaled and the color tinted.
- Shadows: a postfix on `GameOptionsManager.ApplyShadowQuality` stretches the distance and cascades, and the sun and
  moon get the custom shadow map size (also on the sun's NGSS soft shadows, if it has them). Contact shadows are the
  game's NGSS frustum shadows on the player camera.
- Detail: a postfix on `GetLODBias`, transpilers on `ChunkGameObject.CheckLODs` (grass cut-off) and
  `DecoManager.UpdateTick` (tree radius), and a postfix on `MeshDescription.SetGrassQuality` (grass fade).
- Weather (`GfxWeather`, `unity/Assets/GraphicsExpanded/WeatherSurface.shader`): a command buffer on the player camera
  at `BeforeReflections`, after the game has drawn every surface into the deferred G-buffer and before reflections and
  lighting, copies G-buffers 0 to 2 and redraws the wet, puddled and snowy surfaces into them. The game's and Torch's
  lighting then light them like anything else; Torch's own hooks come later in the frame. It's only attached while
  something is wet or snowy.
- Sunbeams and height fog (`GfxAtmosphere`, `unity/Assets/GraphicsExpanded/Volumetric.shader`): while the player
  camera renders, the sun (or moon) gets two command buffers: one at `AfterShadowMap` keeps its shadow map, one at
  `AfterScreenspaceMask`, while its shadow cascades are still set up, marches a ray per pixel at half or quarter resolution
  through the fog layer and air, adding the light that scatters towards the camera where the shadow map says the air
  is lit. A camera command buffer at `AfterForwardAlpha` blurs it, keeping edges, and lays it over the picture
  (what's there times what gets through, plus the light) before the game's post-processing. Those are the light
  slots the game's own sun effects use (NGSS soft shadows, contact shadows), and the light buffers are added before
  the camera culls, as the game does: added in `OnPreRender`, Unity doesn't run them that frame. The overlay only touches
  the picture on frames the march ran (`_GfxMarched`), and catches invalid values, so it can never black the scene out.
- The fog's banks are a 32x32x32 tiling noise made when the mod starts, scrolled with the world time so every player
  sees the same banks. Clear air still scatters sunbeams against the sky but doesn't dim it.
- Distance haze (`GfxHaze`, `unity/Assets/GraphicsExpanded/Haze.shader`, `GfxHaze.cginc`): a camera command buffer at
  `BeforeForwardAlpha`, after the solid world and before transparent objects, dims each pixel past 150 m towards the
  air's color by its distance and height. Its color is `SkyManager.GetSkyColor()`'s hue at the brightness of the
  game's fog color. The water shader hazes its own reflections the same way.
- Water (`GfxWater`, `unity/Assets/GraphicsExpanded/Water.shader`): the mod's shader goes on the game's two water
  materials (`MeshDescription.meshes[1]`: the near one and `materialDistant`, the far one) and the game's shaders go
  back when it's off or the compare key is held. It grabs the picture behind the water, reads the depth behind it for
  how deep the water is, reflects the game's reflection probe (`PlayerReflectionProbe`), and on High marches each
  reflected ray across the screen. The far water still steps aside where near water is drawn, from the game's
  `_ClipChunks` map of loaded chunks.
- Sky cover: for every block column within 6 chunks, the top of the highest block that stops rain (solid blocks, not
  plants, grass, flowers or water), read from the chunks 24 a frame and refreshed every two seconds. It comes from the
  block data rather than from rendering, because the game culls chunk pieces you can't see (from inside a house, parts
  of the roof).
- Ground textures (`GfxTerrainTextures`): the terrain shader (MicroSplat) reads three texture arrays of 24 layers at
  2048x2048 from `MeshDescription.meshes[5]`'s near and far materials: color with height in alpha, normal, and
  smoothness with AO. The mod makes three arrays in exactly the game's format, copies each layer in on the graphics
  card from `Resources/graphicsexpanded_terrain.bundle` where the pack has one and from the game's array where it
  doesn't, and puts them on both materials. Row 0 of the terrain's per-texture settings (`_PerTexProps`) is each
  layer's UV scale, so a copy with the replaced layers' doubled goes on with them. The game's arrays and settings are
  kept, so turning it off or holding the compare key puts them straight back. The bundle loads in the background when a world starts and is unloaded once copied.
- Distant terrain (`GfxTerrain`): the far-off Unity terrain tiles get a lower `heightmapPixelError` and a longer
  `basemapDistance`.
- Distant forests (`GfxForest`, `DistantTree.shader`, `TreeCapture.shader`): the game keeps every tree's place in
  `DecoManager`'s 128 m decoration chunks, which the mod reads a few a frame once a world loads, and again every five
  minutes for felled and planted trees. Each kind of tree is pictured from eight sides by borrowing a model from the
  game's `GameObjectPool` (by file name, as `DecoObject.GetModelName` gives it) and drawing its nearest level of detail
  with its own materials' deferred pass into a small G-buffer of the mod's; a throwaway camera's command buffers never
  ran. One `DrawMeshInstancedIndirect` a frame then draws every tree as a camera-facing card into the player camera's
  G-buffer, so the game's lighting, fog and the haze apply. A card collapses where the game draws the tree itself: in a
  decoration chunk it shows (`visibleDecoChunks`), closer than that kind's last level of detail stops drawing.
- Block textures are one 512x512 texture array (407 layers) whose shader has no tunable settings, so there's nothing
  to sharpen; a mipmap bias and the shaders' `_MipSlope` made no visible difference.

## Building

- `src/build.bat` compiles `GraphicsExpanded.dll` against the installed game with the C# compiler that ships with Visual
  Studio (no .NET SDK needed).
- `src/build-shaders.bat` builds the shaders in `unity/` into `Resources/graphicsexpanded.bundle` with the Unity
  editor in batch mode. It needs Unity 2022.3.62f2, the game's version, from Unity Hub (set `UNITY` to its Unity.exe if
  it isn't in Hub's default folder). The project has no packages besides the built-in AssetBundle module, so nothing is
  downloaded, and every build starts from scratch. Players don't need Unity: the bundle ships in the mod.
- `src/preview-scene.bat` renders the water and distance haze outside the game, in a made-up lake scene with the
  game's measured light and exposure, into `unity/Build/scene-preview.png` (with a debug column). It needs a graphics
  card (batch mode, but not `-nographics`).
- `src/build-terrain.bat <sources> <export>` builds the texture pack into `Resources/graphicsexpanded_terrain.bundle`.
  At about 300 MB it's over GitHub's file limit, so it isn't in the repository: build it, and ship it in the mod's
  `Resources` folder. Without it the Textures setting does nothing and the ground keeps the game's textures.
  `src/fetch-terrain-textures.ps1 -Destination <sources>` downloads the Poly Haven sets first (about 170 MB, checked
  against Poly Haven's checksums), and `gfxe terrain export` in game saves the game's own ground textures into
  `<export>` to match against. `GfxTerrainPack` (`unity/Assets/Editor`) holds which set replaces which layer and
  matches each to the game's: average color, contrast octave by octave from fine grain up to the whole tile (so it
  reads like the game's near and far, without a photo's broad patches tiling into a camouflage pattern), color
  variety, normal depth, height spread, and average smoothness and AO. It logs every factor to
  `unity/Build/terrain.log` and saves previews in `unity/Build/terrain/previews`.
- Unity Hub must be signed in for the Unity scripts.

## Credits

The photoscanned ground textures are from [Poly Haven](https://polyhaven.com) (CC0): asphalt_02, brown_mud_rocks_01,
burned_ground_01, dry_ground_rocks, forest_ground_04, forest_leaves_02, gravel_road, gravelly_sand,
red_laterite_soil_stones, road_damaged, rock_06, rock_face_03, rock_ground, rocks_ground_06, sandy_gravel_02,
snow_02 and tiger_rock.
