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
  ruins, made from the game's own shadows, with dusty air indoors so beams through windows show. A layer of fog sits
  about 15 m above the ground around you, filling valleys and low ground, with morning mist after dawn and thicker,
  redder fog under the Blood Moon. Quality from Low to High, or Off. Only the sun and moon: lamps and torches are
  Torch's.

The shadow and detail settings start at "Video menu", so out of the box only the look changes.

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
gfxe materials                  write the block and terrain materials and textures to the game log
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
- Sky cover: for every block column within 6 chunks, the top of the highest block that stops rain (solid blocks, not
  plants, grass, flowers or water), read from the chunks 24 a frame and refreshed every two seconds. It comes from the
  block data rather than from rendering, because the game culls chunk pieces you can't see (from inside a house, parts
  of the roof).
- Textures: blocks are one 512x512 texture array (407 layers) whose shader has no tunable settings, and terrain is 24
  layers at 2048x2048, so there's nothing to sharpen; a mipmap bias and the shaders' `_MipSlope` made no visible
  difference.

## Building

- `src/build.bat` compiles `GraphicsExpanded.dll` against the installed game with the C# compiler that ships with Visual
  Studio (no .NET SDK needed).
- `src/build-shaders.bat` builds the shaders in `unity/` into `Resources/graphicsexpanded.bundle` with the Unity
  editor in batch mode. It needs Unity 2022.3.62f2, the game's version, from Unity Hub (set `UNITY` to its Unity.exe if
  it isn't in Hub's default folder). The project has no packages besides the built-in AssetBundle module, so nothing is
  downloaded, and every build starts from scratch. Players don't need Unity: the bundle ships in the mod.
