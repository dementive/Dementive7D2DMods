using UnityEngine;

/// <summary>Nick of Time. The world can only slow down when nobody else shares it, so a solo player gets the real thing
/// and anyone in co-op gets a speed boost instead (buffs.xml).</summary>
public static class ChemTimeDEM
{
    public const string SoloBuff = "buffDementiveNickSolo";
    public const string CoopBuff = "buffDementiveNickCoop";

    private const float Scale = .35f;

    private static bool active;

    public static bool IsSolo()
    {
        var connections = SingletonMonoBehaviour<ConnectionManager>.Instance;
        return !GameManager.IsDedicatedServer && connections != null && connections.IsServer && connections.ClientCount() == 0;
    }

    /// <summary>Runs every frame. The pause menu puts timeScale back to 1 when it closes, so the slowdown is checked
    /// rather than set once.</summary>
    public static void Update()
    {
        var player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player == null || player.Buffs == null || player.IsDead() || !player.Buffs.HasBuff(SoloBuff) || !IsSolo())
        {
            Restore();
            return;
        }
        if (GameManager.Instance.IsPaused())
            return;
        if (!active || !Mathf.Approximately(Time.timeScale, Scale))
        {
            // Goes through the controller's own setter because it scales the physics step too, which keeps movement smooth
            vp_TimeUtility.TimeScale = Scale;
            active = true;
        }
    }

    public static void Restore()
    {
        if (!active)
            return;
        active = false;
        Time.fixedDeltaTime = vp_TimeUtility.InitialFixedTimeStep;
        if (!GameManager.Instance.IsPaused())
            Time.timeScale = 1f;
    }
}
