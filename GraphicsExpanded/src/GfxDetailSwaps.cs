using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Moves the level-of-detail swaps of things that snap from one level to the next further out, where the pop is much
/// harder to see: bushes, plants and props drawn with shaders that can't cross-fade (Torch's plant shader among them),
/// and LOD groups set not to fade at all. Trees fade between their levels already and are left alone. Once a second the
/// LOD groups new to the scene are looked over (the game sets theirs once, when it makes them); the ones that snap get
/// their switch heights divided, and the game's own are kept to put back.
/// </summary>
public static class GfxDetailSwaps
{
    private const float Further = 2f;          // how many times as far out the swaps happen
    private const float SweepEvery = 1f;

    private static readonly Dictionary<LODGroup, Moved> moved = new Dictionary<LODGroup, Moved>();
    private static readonly HashSet<LODGroup> leftAlone = new HashSet<LODGroup>();
    private static readonly Dictionary<Shader, bool> shaderFades = new Dictionary<Shader, bool>();
    private static float nextSweep;

    private struct Moved
    {
        public LOD[] Game;          // what the game had
        public float Last;          // the last level's height as we set it, to tell if the game has set it again since
    }

    private static bool Wanted => GfxSettings.DetailActive && GfxSettings.PlantDetail == GfxPlantDetail.Further;

    /// <summary>How many LOD groups have their swaps moved out now.</summary>
    public static int Count => moved.Count;

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update()
    {
        if (!Wanted)
        {
            if (moved.Count > 0 || leftAlone.Count > 0)
                Restore();
            return;
        }
        if (Time.unscaledTime < nextSweep)
            return;
        nextSweep = Time.unscaledTime + SweepEvery;
        Prune();
        foreach (LODGroup group in Object.FindObjectsByType<LODGroup>(FindObjectsSortMode.None))
        {
            if (group == null || moved.ContainsKey(group) || leftAlone.Contains(group))
                continue;
            if (!Snaps(group))
            {
                leftAlone.Add(group);
                continue;
            }
            LOD[] game = group.GetLODs();
            LOD[] further = group.GetLODs();
            if (further.Length == 0)
            {
                leftAlone.Add(group);
                continue;
            }
            for (int i = 0; i < further.Length; i++)
                further[i].screenRelativeTransitionHeight /= Further;
            group.SetLODs(further);
            moved[group] = new Moved { Game = game, Last = further[further.Length - 1].screenRelativeTransitionHeight };
        }
    }

    /// <summary>
    /// How many times further out the group's swaps will be once this reaches it: Further for one that snaps and hasn't
    /// been moved yet, else 1 (already moved, fades on its own, or the setting is off). For pictures of a model taken
    /// before the scene's copies of it are moved (GfxForest), so they match.
    /// </summary>
    public static float Pending(LODGroup group)
    {
        return group != null && Wanted && !moved.ContainsKey(group) && Snaps(group) ? Further : 1f;
    }

    /// <summary>Whether the group switches levels with a pop: set not to fade, or drawn with a shader that can't cross-fade.</summary>
    private static bool Snaps(LODGroup group)
    {
        if (group.fadeMode == LODFadeMode.None)
            return true;
        foreach (LOD lod in group.GetLODs())
        {
            foreach (Renderer renderer in lod.renderers)
            {
                if (renderer == null)
                    continue;
                foreach (Material material in renderer.sharedMaterials)
                {
                    Shader shader = material != null ? material.shader : null;
                    if (shader == null)
                        continue;
                    if (!shaderFades.TryGetValue(shader, out bool fades))
                        shaderFades[shader] = fades = shader.keywordSpace.FindKeyword("LOD_FADE_CROSSFADE").isValid;
                    if (!fades)
                        return true;
                }
            }
        }
        return false;
    }

    /// <summary>Puts the game's own swaps back, leaving any the game has set again since.</summary>
    private static void Restore()
    {
        foreach (KeyValuePair<LODGroup, Moved> entry in moved)
        {
            LODGroup group = entry.Key;
            if (group == null)
                continue;
            LOD[] now = group.GetLODs();
            if (now.Length == entry.Value.Game.Length && now.Length > 0 && Mathf.Approximately(now[now.Length - 1].screenRelativeTransitionHeight, entry.Value.Last))
                group.SetLODs(entry.Value.Game);
        }
        moved.Clear();
        leftAlone.Clear();
        nextSweep = 0f;
    }

    /// <summary>Forgets groups the game has destroyed.</summary>
    private static void Prune()
    {
        List<LODGroup> gone = null;
        foreach (LODGroup group in moved.Keys)
        {
            if (group == null)
                (gone ??= new List<LODGroup>()).Add(group);
        }
        if (gone != null)
        {
            foreach (LODGroup group in gone)
                moved.Remove(group);
        }
        leftAlone.RemoveWhere(group => group == null);
    }
}
