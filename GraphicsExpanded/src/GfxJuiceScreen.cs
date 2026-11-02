using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Game juice on the screen itself (JuiceScreen.shader), under the HUD:
/// - low health: below 30% the edges darken and redden with a heartbeat that quickens as health drops (the game
///   already shows blood on the side a hit came from, so that's left to it);
/// - rewards: a soft warm glow round the edges on a level-up, fainter when a quest is done.
/// It's drawn by a command buffer on the UI camera, before its widgets, so it lands on the finished (upscaled) picture
/// rather than going through the game's anti-aliasing and upscaling, which would smear it.
/// </summary>
public static class GfxJuiceScreen
{
    private const float RewardSeconds = 1.4f;
    private const float LowHealth = 0.3f;

    private static Material material;
    private static Camera camera;
    private static CommandBuffer commands;
    private static bool attached;

    private static float low, beat;
    private static float reward = -1f, rewardStrength;

    public static bool Loaded => material != null;

    public static void Init(Shader shader)
    {
        if (shader == null)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        commands = new CommandBuffer { name = "GraphicsExpanded juice screen" };
        commands.DrawProcedural(Matrix4x4.identity, material, 0, MeshTopology.Triangles, 3);
    }

    /// <summary>The reward glow: 1 for a level-up, less for a finished quest.</summary>
    public static void Reward(float strength)
    {
        reward = 0f;
        rewardStrength = strength;
    }

    public static void Clear()
    {
        low = 0f;
        reward = -1f;
    }

    /// <summary>Called every frame from GfxJuice.Update. hurtOn and rewardsOn are the Feel tab's switches.</summary>
    public static void Update(EntityPlayerLocal player, float deltaTime, bool hurtOn, bool rewardsOn)
    {
        if (!Loaded)
            return;
        bool alive = player != null && !player.IsDead();
        if (!alive || !rewardsOn)
            reward = -1f;

        // Health below 30%: the lower it is, the stronger and faster the heartbeat
        float lowTarget = 0f;
        if (alive && hurtOn && player.Stats?.Health != null)
        {
            float max = Mathf.Max(player.Stats.Health.Max, 1f);
            lowTarget = Mathf.Clamp01(1f - player.Stats.Health.Value / (max * LowHealth));
        }
        low = alive && hurtOn ? Mathf.MoveTowards(low, lowTarget, deltaTime * 0.8f) : 0f;
        float bpm = 70f + 70f * low;
        beat = (beat + deltaTime * bpm / 60f) % 1f;
        float pulse = Mathf.Exp(-beat * 9f) + 0.6f * Mathf.Exp(-Mathf.Abs(beat - 0.22f) * 14f);

        if (reward >= 0f)
        {
            reward += deltaTime / RewardSeconds;
            if (reward >= 1f)
                reward = -1f;
        }

        bool show = low > 0.001f || reward >= 0f;
        Camera ui = show ? UiCamera() : null;
        if (ui == null)
        {
            Detach();
            return;
        }
        material.SetVector("_GfxJuiceHurt", new Vector4(low, Mathf.Clamp01(pulse), 0f, 0f));
        material.SetVector("_GfxJuiceReward", new Vector4(reward >= 0f ? Mathf.Max(reward, 0.001f) : 0f, rewardStrength, 0f, 0f));
        Attach(ui);
    }

    private static Camera UiCamera()
    {
        LocalPlayerUI ui = LocalPlayerUI.primaryUI;
        return ui != null ? ui.camera : null;
    }

    private static void Attach(Camera uiCamera)
    {
        if (attached && camera == uiCamera)
            return;
        Detach();
        camera = uiCamera;
        camera.AddCommandBuffer(CameraEvent.BeforeForwardAlpha, commands);
        attached = true;
    }

    public static void Detach()
    {
        if (attached && camera != null)
            camera.RemoveCommandBuffer(CameraEvent.BeforeForwardAlpha, commands);
        attached = false;
        camera = null;
    }

    public static string Status()
    {
        return string.Format("screen: low health {0:0.00}, reward {1:0.00}, {2}", low, reward,
            attached ? "drawing on " + (camera != null ? camera.name : "?") : "idle");
    }
}
