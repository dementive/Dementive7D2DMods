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
            + "  gfxe weather         - how wet and snowy things are now\n"
            + "  gfxe weather wet <0-1> | snow <0-1> - set it, to see it without waiting for the weather\n"
            + "  gfxe weather debug   - show the sky check instead: cyan is open to the sky, magenta is covered\n"
            + "  gfxe atmosphere      - how the sunbeams and height fog are running\n"
            + "Changes last until the game closes. Install Gears to change and save every setting from the Mods menu.";
    }

    public override void Execute(List<string> _params, CommandSenderInfo _senderInfo)
    {
        SdtdConsole console = SingletonMonoBehaviour<SdtdConsole>.Instance;
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
