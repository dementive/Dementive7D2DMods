using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Game juice's hit flash (JuiceFlash.shader): a creature lights up for a moment when it's hit, brightest round its
/// edges, and longer and hotter on a kill or a headshot. A command buffer on the player camera redraws the creature's
/// own renderers after the scene with the flash material (CommandBuffer.DrawRenderer follows the skinned pose), so
/// nothing about the creature's materials changes.
/// </summary>
public static class GfxJuiceFlash
{
    private const int Max = 24;

    private struct Glow
    {
        public EntityAlive entity;
        public Renderer[] renderers;
        public Color color;
        public float start, seconds, strength;
    }

    private static Material material;
    private static readonly List<Glow> glows = new List<Glow>();
    private static readonly List<Renderer> found = new List<Renderer>();
    private static Camera camera;
    private static CommandBuffer commands;
    private static bool attached;
    private static readonly int FlashId = Shader.PropertyToID("_GfxJuiceFlash");

    public static bool Loaded => material != null;
    public static int Count => glows.Count;

    public static void Init(Shader shader)
    {
        if (shader == null)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        commands = new CommandBuffer { name = "GraphicsExpanded juice hit flash" };
    }

    /// <summary>Lights the creature up: seconds long, strength 0 to 1 (more for kills and headshots).</summary>
    public static void Flash(EntityAlive entity, Color color, float strength, float seconds)
    {
        if (!Loaded || entity == null)
            return;
        for (int i = 0; i < glows.Count; i++)
        {
            if (glows[i].entity == entity)
            {
                Glow again = glows[i];
                again.start = Time.time;
                again.color = color;
                again.strength = Mathf.Max(strength, again.strength * 0.5f);
                again.seconds = seconds;
                glows[i] = again;
                return;
            }
        }
        if (glows.Count >= Max)
            glows.RemoveAt(0);
        glows.Add(new Glow { entity = entity, renderers = Renderers(entity), color = color, start = Time.time, seconds = seconds, strength = strength });
    }

    /// <summary>The creature's visible body: its skinned and plain mesh renderers, without particles and the like.</summary>
    private static Renderer[] Renderers(EntityAlive entity)
    {
        found.Clear();
        Transform model = entity.emodel != null ? entity.emodel.GetModelTransform() : null;
        Transform root = model != null ? model : entity.transform;
        foreach (Renderer r in root.GetComponentsInChildren<Renderer>(true))
        {
            if (r is SkinnedMeshRenderer || r is MeshRenderer)
                found.Add(r);
        }
        return found.ToArray();
    }

    public static void Clear()
    {
        glows.Clear();
    }

    /// <summary>Called every frame from GfxJuice.Update.</summary>
    public static void Update(Camera playerCamera)
    {
        if (!Loaded)
            return;
        float now = Time.time;
        commands.Clear();
        int drawn = 0;
        for (int i = glows.Count - 1; i >= 0; i--)
        {
            Glow g = glows[i];
            float t = (now - g.start) / g.seconds;
            if (t >= 1f || g.entity == null || g.renderers == null)
            {
                glows.RemoveAt(i);
                continue;
            }
            float strength = g.strength * (1f - t) * (1f - t);
            commands.SetGlobalVector(FlashId, new Vector4(g.color.r, g.color.g, g.color.b, strength));
            foreach (Renderer r in g.renderers)
            {
                if (r == null || !r.enabled || !r.isVisible || !r.gameObject.activeInHierarchy)
                    continue;
                int parts = r.sharedMaterials.Length;
                for (int part = 0; part < parts; part++)
                    commands.DrawRenderer(r, material, part, 0);
                drawn++;
            }
        }
        if (drawn > 0 && playerCamera != null)
            Attach(playerCamera);
        else
            Detach();
    }

    private static void Attach(Camera playerCamera)
    {
        if (attached && camera == playerCamera)
            return;
        Detach();
        camera = playerCamera;
        camera.AddCommandBuffer(CameraEvent.AfterForwardAlpha, commands);
        attached = true;
    }

    public static void Detach()
    {
        if (attached && camera != null)
            camera.RemoveCommandBuffer(CameraEvent.AfterForwardAlpha, commands);
        attached = false;
        camera = null;
    }
}
