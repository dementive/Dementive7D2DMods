using System;
using System.Collections.Generic;

/// <summary>
/// Turns the mod on or off and switches presets without Gears, for the session only. With Gears installed the
/// Mods menu is the place to change settings; it puts its saved values back the next time anything is applied there.
/// </summary>
public class GfxConsoleCmd : ConsoleCmdAbstract
{
    public override bool IsExecuteOnClient => true;
    public override bool AllowedInMainMenu => true;
    public override int DefaultPermissionLevel => 1000;

    public override string[] getCommands()
    {
        return new[] { "graphicsexpanded", "gfxe" };
    }

    public override string getDescription()
    {
        return "Graphics Expanded: turn it on or off, or pick a look preset";
    }

    public override string getHelp()
    {
        return "Usage:\n"
            + "  gfxe                 - show the current settings\n"
            + "  gfxe on | off        - turn the whole mod on or off\n"
            + "  gfxe preset <name>   - vanilla, natural or cinematic\n"
            + "  gfxe materials       - write the block and terrain materials' settings to the game log\n"
            + "  gfxe grass           - where the grass stops: its fade distance, and chunks with grass on by distance\n"
            + "  gfxe grass fade <m>  - set the grass fade distance for this session, to see if the grass follows\n"
            + "  gfxe distantgrass    - how the distant grass is running\n"
            + "  gfxe distantgrass debug - magenta tufts; again: also those on roads and water, in red; again: off\n"
            + "  gfxe terrain fartiling <x> - the far terrain's tiling (default 1, the game's; lower repeats less)\n"
            + "  gfxe weather         - how wet and snowy things are now\n"
            + "  gfxe weather wet <0-1> | snow <0-1> - set it, to see it without waiting for the weather\n"
            + "  gfxe weather debug   - show the sky check instead: cyan is open to the sky, magenta is covered\n"
            + "  gfxe atmosphere      - how the sunbeams and height fog are running\n"
            + "  gfxe terrain         - how the far terrain and the ground's textures are set\n"
            + "  gfxe terrain table   - write the terrain's per-texture settings to the game log\n"
            + "  gfxe terrain export  - save the 24 ground textures as images, to GraphicsExpanded/TerrainExport\n"
            + "  gfxe terrain tiling <x> - repeat the photoscanned textures x times as often (default 2, 1 is the game's; more is sharper up close)\n"
            + "  gfxe trees           - how the distant forests are running\n"
            + "  gfxe trees save      - save the pictures of each kind of tree, to GraphicsExpanded/Trees\n"
            + "  gfxe trees on | off  - turn the distant forests on or off for this session\n"
            + "  gfxe trees debug     - draw them bright magenta to see where they are (again to stop)\n"
            + "  gfxe farshadows      - how the far shadows are running\n"
            + "  gfxe farshadows save - save the height map they're worked out from, to GraphicsExpanded/FarShadowHeights.png\n"
            + "  gfxe farshadows debug - red: where they fall; again: blue, height map vs ground; again: off\n"
            + "  gfxe haze            - how the distance haze is running\n"
            + "  gfxe water           - how the water is running\n"
            + "  gfxe water debug     - show what the water's reflections find instead\n"
            + "  gfxe shots           - screenshots of this view with and without the mod's look, to the Screenshots folder\n"
            + "Changes last until the game closes. Install Gears to change and save every setting from the Mods menu.";
    }

    public override void Execute(List<string> _params, CommandSenderInfo _senderInfo)
    {
        SdtdConsole console = SingletonMonoBehaviour<SdtdConsole>.Instance;
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("terrain"))
        {
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("export"))
            {
                console.Output(GfxTerrain.ExportTextures());
                return;
            }
            if (_params.Count == 3 && _params[1].EqualsCaseInsensitive("fartiling"))
            {
                if (!float.TryParse(_params[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float far))
                {
                    console.Output("Give the tiling as a number, like 0.5 (1 is the game's).");
                    return;
                }
                GfxSettings.DistantTiling = UnityEngine.Mathf.Clamp(far, 0.125f, 4f);
                console.Output("The far terrain's photoscanned textures now repeat " + GfxSettings.DistantTiling.ToString("0.###") + " times as often as the game's did.");
                Log.Out("[GraphicsExpanded] Far terrain tiling set to " + GfxSettings.DistantTiling.ToString("0.###"));
                return;
            }
            if (_params.Count == 3 && _params[1].EqualsCaseInsensitive("tiling"))
            {
                if (!float.TryParse(_params[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float tiling))
                {
                    console.Output("Give the tiling as a number, like 1.5 (1 is the game's).");
                    return;
                }
                GfxSettings.TerrainTiling = UnityEngine.Mathf.Clamp(tiling, 0.25f, 4f);
                console.Output("Photoscanned textures now repeat " + GfxSettings.TerrainTiling.ToString("0.##") + " times as often as the game's did.");
                Log.Out("[GraphicsExpanded] Terrain tiling set to " + GfxSettings.TerrainTiling.ToString("0.##"));
                return;
            }
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("table"))
            {
                console.Output("Wrote " + GfxTerrain.LogTextureTable() + " rows of the terrain's per-texture settings to the game log.");
                return;
            }
            console.Output(GfxTerrain.Status());
            console.Output(GfxTerrainTextures.Status());
            Log.Out("[GraphicsExpanded] " + GfxTerrain.Status() + " " + GfxTerrainTextures.Status());
            return;
        }
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("trees"))
        {
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("save"))
            {
                console.Output(GfxForest.SavePictures());
                return;
            }
            if (_params.Count == 2 && (_params[1].EqualsCaseInsensitive("on") || _params[1].EqualsCaseInsensitive("off")))
            {
                GfxSettings.DistantTrees = _params[1].EqualsCaseInsensitive("on") ? GfxDistantTrees.On : GfxDistantTrees.Off;
                console.Output("Distant forests " + (GfxSettings.DistantTrees == GfxDistantTrees.On ? "on (give it a moment to picture the trees)." : "off."));
                return;
            }
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("debug"))
            {
                GfxForest.Debug = !GfxForest.Debug;
                console.Output(GfxForest.Debug ? "Distant forest cards in magenta." : "Distant forest cards drawn normally.");
                return;
            }
            console.Output(GfxForest.Status());
            Log.Out("[GraphicsExpanded] " + GfxForest.Status());
            return;
        }
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("farshadows"))
        {
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("save"))
            {
                console.Output(GfxFarShadows.SaveHeights());
                return;
            }
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("debug"))
            {
                GfxFarShadows.Debug = (GfxFarShadows.Debug + 1) % 3;
                console.Output(GfxFarShadows.Debug == 1 ? "Far shadows shown in red." : GfxFarShadows.Debug == 2
                    ? "The height map's mismatch with the ground shown in blue (should be clear on bare ground)." : "Far shadows shown normally.");
                return;
            }
            console.Output(GfxFarShadows.Status());
            Log.Out("[GraphicsExpanded] " + GfxFarShadows.Status());
            return;
        }
        if (_params.Count == 1 && _params[0].EqualsCaseInsensitive("haze"))
        {
            console.Output(GfxHaze.Status());
            Log.Out("[GraphicsExpanded] " + GfxHaze.Status());
            return;
        }
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("water"))
        {
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("debug"))
            {
                GfxWater.Debug = !GfxWater.Debug;
                console.Output("Water debug view " + (GfxWater.Debug ? "on" : "off") + ": red where screen-space reflections found something, green the reflection's share, blue the shore foam.");
            }
            console.Output(GfxWater.Status());
            Log.Out("[GraphicsExpanded] " + GfxWater.Status());
            return;
        }
        if (_params.Count == 1 && _params[0].EqualsCaseInsensitive("shots"))
        {
            console.Output(GfxShots.Take());
            return;
        }
        if (_params.Count == 1 && _params[0].EqualsCaseInsensitive("atmosphere"))
        {
            console.Output(GfxAtmosphere.Status());
            Log.Out("[GraphicsExpanded] " + GfxAtmosphere.Status());
            return;
        }
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("weather"))
        {
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("debug"))
            {
                GfxWeather.Debug = !GfxWeather.Debug;
                console.Output("Sky check view " + (GfxWeather.Debug ? "on" : "off") + ".");
            }
            else if (_params.Count == 3 && (_params[1].EqualsCaseInsensitive("wet") || _params[1].EqualsCaseInsensitive("snow"))
                && float.TryParse(_params[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float amount))
            {
                if (_params[1].EqualsCaseInsensitive("wet"))
                    GfxWeather.Force(amount, null);
                else
                    GfxWeather.Force(null, amount);
            }
            else if (_params.Count != 1)
            {
                console.Output(getHelp());
                return;
            }
            console.Output(GfxWeather.Status());
            Log.Out("[GraphicsExpanded] " + GfxWeather.Status());
            return;
        }
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("distantgrass"))
        {
            if (_params.Count == 2 && _params[1].EqualsCaseInsensitive("debug"))
            {
                GfxDistantGrass.Debug = (GfxDistantGrass.Debug + 1) % 3;
                console.Output(GfxDistantGrass.Debug == 1 ? "Distant grass in magenta." : GfxDistantGrass.Debug == 2
                    ? "Distant grass in magenta, and on roads and water in red (normally left out)." : "Distant grass drawn normally.");
                return;
            }
            console.Output(GfxDistantGrass.Status());
            Log.Out("[GraphicsExpanded] " + GfxDistantGrass.Status());
            return;
        }
        if (_params.Count >= 1 && _params[0].EqualsCaseInsensitive("grass"))
        {
            float fade = 0f;
            if (_params.Count == 3 && _params[1].EqualsCaseInsensitive("fade")
                && !float.TryParse(_params[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out fade))
            {
                console.Output("Give the fade distance in meters, like 250.");
                return;
            }
            foreach (string line in GfxDiagnostics.Grass(fade))
            {
                console.Output(line);
                Log.Out("[GraphicsExpanded] " + line);
            }
            return;
        }
        if (_params.Count == 1 && _params[0].EqualsCaseInsensitive("materials"))
        {
            int lines = GfxDiagnostics.LogMaterials();
            console.Output("Wrote " + lines + " lines about the voxel mesh materials to the game log (lines starting [GraphicsExpanded]).");
            return;
        }
        if (_params.Count == 1 && (_params[0].EqualsCaseInsensitive("on") || _params[0].EqualsCaseInsensitive("off")))
        {
            GfxSettings.Enabled = _params[0].EqualsCaseInsensitive("on");
        }
        else if (_params.Count == 2 && _params[0].EqualsCaseInsensitive("preset"))
        {
            if (!Enum.TryParse(_params[1], true, out GfxPreset preset) || !GfxSettings.UsePreset(preset))
            {
                console.Output("Unknown preset '" + _params[1] + "'. Use vanilla, natural or cinematic.");
                return;
            }
        }
        else if (_params.Count != 0)
        {
            console.Output(getHelp());
            return;
        }

        GfxLook look = GfxSettings.Look;
        console.Output(string.Format("Graphics Expanded is {0}. Preset {1}: tonemapping {2}, exposure {3:+0.00;-0.00;0.00}, contrast {4:+0;-0;0}, saturation {5:+0;-0;0}, white balance {6:+0;-0;0}, fog {7:0%}.",
            GfxSettings.Enabled ? "on" : "off", GfxSettings.Preset, look.Tonemapping, look.Exposure, look.Contrast,
            look.Saturation, look.WhiteBalance, look.FogDensity));
        console.Output(string.Format("Film: vignette {0:0%}, grain {1:0%}, bloom {2:0%}. Dynamic grading: time of day {3:0%}, weather {4:0%}, Blood Moon {5:0%}.",
            look.Vignette, look.Grain, look.Bloom, look.TimeOfDay, look.Weather, look.BloodMoon));
        GfxLook now = GfxSettings.Effective;
        console.Output(string.Format("On screen now: exposure {0:+0.00;-0.00;0.00}, contrast {1:+0;-0;0}, saturation {2:+0;-0;0}, white balance {3:+0;-0;0}, fog {4:0%}.",
            now.Exposure, now.Contrast, now.Saturation, now.WhiteBalance, now.FogDensity));
        console.Output(string.Format("Shadows: distance {0}, resolution {1}, contact {2} at {3:0%}. Detail: LOD {4:0%}, trees {5}, grass {6}, 16x filtering {7}. Gears {8}.",
            GfxSettings.ShadowDistance, GfxSettings.ShadowResolution, GfxSettings.ContactShadows,
            GfxSettings.ContactShadowLength, GfxSettings.LodDistance, GfxSettings.TreeDistance,
            GfxSettings.GrassDistance, GfxSettings.Anisotropic16x ? "on" : "off",
            GraphicsExpanded.GearsLoaded ? "is installed" : "isn't installed"));
    }
}
