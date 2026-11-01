using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Builds GraphicsExpanded's shaders into one asset bundle for the game. Run from build-shaders.bat, which calls
/// Unity in batch mode with -executeMethod GfxBundleBuilder.Build; the bundle lands in Build/ and the script copies
/// it into the mod's Resources folder.
/// The editor must be the game's exact version (2022.3.62f2), or the game may refuse the bundle.
/// </summary>
public static class GfxBundleBuilder
{
    private const string BundleName = "graphicsexpanded.bundle";

    private static readonly string[] Shaders =
    {
        "Assets/GraphicsExpanded/WeatherSurface.shader",
        "Assets/GraphicsExpanded/Volumetric.shader",
        "Assets/GraphicsExpanded/Haze.shader",
        "Assets/GraphicsExpanded/Water.shader",
        "Assets/GraphicsExpanded/TreeCapture.shader",
        "Assets/GraphicsExpanded/DistantTree.shader",
        "Assets/GraphicsExpanded/FarShadows.shader",
        "Assets/GraphicsExpanded/DistantGrass.shader",
        "Assets/GraphicsExpanded/Ambience.shader",
    };

    public static void Build()
    {
        // Same as the game: linear color, and every graphics API it can run on
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[]
        {
            GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Direct3D12, GraphicsDeviceType.Vulkan,
            GraphicsDeviceType.OpenGLCore,
        });

        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        Directory.CreateDirectory(output);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = Shaders };
        // Always from scratch: an incremental build skips the bundle when only project settings changed
        AssetBundleManifest manifest = BuildPipeline.BuildAssetBundles(output, new[] { bundle },
            BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode
                | BuildAssetBundleOptions.ForceRebuildAssetBundle,
            BuildTarget.StandaloneWindows64);
        if (manifest == null)
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        Debug.Log("[GfxBundleBuilder] Built " + Path.Combine(output, BundleName));
    }
}
