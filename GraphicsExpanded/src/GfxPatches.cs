using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// The game re-applies the player's camera options on spawn and whenever the video menu changes, resetting the
/// contact shadows and the brightness tone curve; put ours back on top.
/// </summary>
[HarmonyPatch(typeof(GameRenderManager), nameof(GameRenderManager.ApplyCameraOptions), new Type[0])]
public class GfxPatch_CameraOptions
{
    static void Postfix(GameRenderManager __instance)
    {
        if (__instance.player != null)
            GfxApply.OnCameraOptionsApplied(__instance.player.playerCamera);
    }
}

[HarmonyPatch(typeof(GameOptionsManager), nameof(GameOptionsManager.ApplyShadowQuality))]
public class GfxPatch_ShadowQuality
{
    static void Postfix()
    {
        GfxApply.ApplySunShadows();
    }
}

[HarmonyPatch(typeof(SkyManager), nameof(SkyManager.OnShadowDistanceChanged))]
public class GfxPatch_SunShadowResolution
{
    static void Postfix()
    {
        GfxApply.ApplySunResolution();
    }
}

[HarmonyPatch(typeof(GameOptionsManager), nameof(GameOptionsManager.GetLODBias))]
public class GfxPatch_LodBias
{
    static void Postfix(ref float __result)
    {
        if (GfxSettings.DetailActive)
            __result *= GfxSettings.LodDistance;
    }
}

[HarmonyPatch(typeof(GameOptionsManager), nameof(GameOptionsManager.ApplyTextureFilter))]
public class GfxPatch_TextureFilter
{
    static void Postfix()
    {
        GfxApply.ApplyTextureFilter();
    }
}

/// <summary>
/// The fog. SkyManager sets it every frame from its fog density (cubed for Unity's exponential fog, squared for the
/// game's own shaders) and color, so redo those with ours. The density slider scales what's on screen, so it
/// scales the density before cubing by its cube root.
/// </summary>
public static class GfxFog
{
    public static bool Active
    {
        get
        {
            GfxLook look = GfxSettings.Effective;
            return look.FogDensity != 1f || look.FogTint != Color.white;
        }
    }

    public static float Density()
    {
        return SkyManager.GetFogDensity() * Mathf.Pow(Mathf.Max(GfxSettings.Effective.FogDensity, 0f), 1f / 3f);
    }

    public static Color FogColor()
    {
        Color color = SkyManager.GetFogColor();
        Color tint = GfxSettings.Effective.FogTint;
        return new Color(color.r * tint.r, color.g * tint.g, color.b * tint.b, color.a);
    }
}

[HarmonyPatch(typeof(SkyManager), nameof(SkyManager.UpdateFogShader))]
public class GfxPatch_FogShader
{
    static void Postfix(SkyManager __instance)
    {
        if (!GfxFog.Active)
            return;
        float density = GfxFog.Density();
        __instance.fogParams.w = density * density;
    }
}

[HarmonyPatch(typeof(SkyManager), nameof(SkyManager.UpdateShaderGlobals))]
public class GfxPatch_FogGlobals
{
    static void Postfix(SkyManager __instance)
    {
        if (!GfxFog.Active)
            return;
        float density = GfxFog.Density();
        density = density * density * density;
        Color color = GfxFog.FogColor();
        RenderSettings.fogDensity = density;
        RenderSettings.fogColor = color;
        Shader.SetGlobalVector("_FogParams", new Vector4(density, __instance.fogParams.x, __instance.fogParams.y, 0f));
        Shader.SetGlobalColor("_FogColor", color.linear);
        Shader.SetGlobalVector("FogColor", color);
    }
}

/// <summary>
/// The grass fade distance, which SetGrassQuality puts on the grass material. Torch's grass shader starts thinning the
/// grass at about half of it (gfxe grass fade showed it), so it's set well past the cut-off to keep the grass full
/// nearly to where it stops.
/// </summary>
[HarmonyPatch(typeof(MeshDescription), nameof(MeshDescription.SetGrassQuality))]
public class GfxPatch_GrassFade
{
    static void Postfix()
    {
        float meters = GfxApply.GrassCullDistance(0f);
        if (meters <= 0f || MeshDescription.meshes == null || MeshDescription.meshes.Length <= MeshDescription.MESH_GRASS)
            return;
        Material material = MeshDescription.meshes[MeshDescription.MESH_GRASS]?.material;
        if (material != null)
            material.SetFloat("_FadeDistance", meters * 1.6f);
    }
}

/// <summary>
/// The grass cut-off. CheckLODs picks 48, 64, 96 or 112 m from the grass distance option into one local; pass each
/// through <see cref="GfxApply.GrassCullDistance"/>.
/// </summary>
[HarmonyPatch(typeof(ChunkGameObject), nameof(ChunkGameObject.CheckLODs))]
public class GfxPatch_GrassCull
{
    private static readonly float[] Distances = { 48f, 64f, 96f, 112f };

    static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
    {
        List<CodeInstruction> codes = new List<CodeInstruction>(instructions);
        MethodInfo hook = AccessTools.Method(typeof(GfxApply), nameof(GfxApply.GrassCullDistance));
        int local = -1;
        int patched = 0;
        for (int i = 0; i < codes.Count - 1; i++)
        {
            if (codes[i].opcode != OpCodes.Ldc_R4 || !(codes[i].operand is float value) || Array.IndexOf(Distances, value) < 0)
                continue;
            int store = StoredLocal(codes[i + 1]);
            if (store < 0)
                continue;
            if (local < 0 && value == Distances[0])
                local = store;
            if (store != local)
                continue;
            codes.Insert(i + 1, new CodeInstruction(OpCodes.Call, hook));
            patched++;
            i++;
        }
        if (patched != Distances.Length)
            Log.Warning("[GraphicsExpanded] ChunkGameObject.CheckLODs has changed; found " + patched + " of 4 grass distances, so the grass distance setting may only partly work");
        return codes;
    }

    private static int StoredLocal(CodeInstruction code)
    {
        if (code.opcode == OpCodes.Stloc_0) return 0;
        if (code.opcode == OpCodes.Stloc_1) return 1;
        if (code.opcode == OpCodes.Stloc_2) return 2;
        if (code.opcode == OpCodes.Stloc_3) return 3;
        if (code.opcode != OpCodes.Stloc_S && code.opcode != OpCodes.Stloc)
            return -1;
        return code.operand switch
        {
            LocalBuilder builder => builder.LocalIndex,
            byte index => index,
            int index => index,
            _ => -1,
        };
    }
}

/// <summary>
/// The tree distance. UpdateTick reads the option as a radius of 128 m decoration chunks around the local player;
/// read it through <see cref="GfxApply.TreeRadius"/> instead.
/// </summary>
[HarmonyPatch(typeof(DecoManager), nameof(DecoManager.UpdateTick))]
public class GfxPatch_TreeDistance
{
    static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
    {
        List<CodeInstruction> codes = new List<CodeInstruction>(instructions);
        MethodInfo getInt = AccessTools.Method(typeof(GamePrefs), nameof(GamePrefs.GetInt), new[] { typeof(EnumGamePrefs) });
        MethodInfo hook = AccessTools.Method(typeof(GfxApply), nameof(GfxApply.TreeRadius));
        int patched = 0;
        for (int i = 0; i < codes.Count - 1; i++)
        {
            if (codes[i].LoadsConstant((long)EnumGamePrefs.OptionsGfxTreeDistance) && codes[i + 1].Calls(getInt))
            {
                codes[i + 1].operand = hook;
                patched++;
            }
        }
        if (patched == 0)
            Log.Warning("[GraphicsExpanded] DecoManager.UpdateTick has changed; the tree distance setting won't work");
        return codes;
    }
}
