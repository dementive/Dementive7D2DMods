using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Temperament, on the server: the zombie's own sight, hearing, wandering and chase time, scaled from the values its
/// class gave it. Sluggish zombies notice you later and give up sooner; restless ones wander and notice more;
/// relentless ones keep chasing long after the others give up.
/// </summary>
public static class ZedTemperament
{
    private struct Scales
    {
        public float Sight, Hearing, Chase, Wander;
    }

    private static readonly HashSet<int> applied = new HashSet<int>();

    private static Scales For(ZedTemper t)
    {
        switch (t)
        {
            case ZedTemper.Sluggish:
                return new Scales { Sight = 0.75f, Hearing = 0.7f, Chase = 0.6f, Wander = 0.5f };
            case ZedTemper.Restless:
                return new Scales { Sight = 1.15f, Hearing = 1.25f, Chase = 1f, Wander = 2f };
            case ZedTemper.Relentless:
                return new Scales { Sight = 1.1f, Hearing = 1.1f, Chase = 4f, Wander = 1f };
            default:
                return new Scales { Sight = 1f, Hearing = 1f, Chase = 1f, Wander = 1f };
        }
    }

    public static void Apply(EntityAlive zombie, ZedProfile p)
    {
        EAIManager ai = zombie.aiManager;
        if (ai == null || !applied.Add(zombie.entityId))
        {
            return;
        }
        Scales s = For(p.Temper);
        // Helmets that cover the eyes or ears dull them (while they're on)
        foreach (ZedGearPiece g in p.Gear)
        {
            if (!g.Broken)
            {
                s.Sight *= ZedGearInfo.All[g.Kind].Sight;
                s.Hearing *= ZedGearInfo.All[g.Kind].Hearing;
            }
        }
        if (Mathf.Approximately(s.Sight, 1f) && Mathf.Approximately(s.Hearing, 1f) && Mathf.Approximately(s.Chase, 1f)
            && Mathf.Approximately(s.Wander, 1f))
        {
            return;
        }
        Rescale(zombie, s.Sight, s.Hearing);
        foreach (EAIApproachAndAttackTarget chase in ai.GetTasks<EAIApproachAndAttackTarget>() ?? new List<EAIApproachAndAttackTarget>())
        {
            chase.chaseTimeMax *= s.Chase;
        }
        foreach (EAIWander wander in ai.GetTasks<EAIWander>() ?? new List<EAIWander>())
        {
            wander.executePercent *= s.Wander;
        }
    }

    /// <summary>Scales a zombie's sight and hearing (temperament, or a helmet coming off: the inverse).</summary>
    public static void Rescale(EntityAlive zombie, float sight, float hearing)
    {
        EAIManager ai = zombie.aiManager;
        if (ai == null)
        {
            return;
        }
        zombie.sightRangeBase *= sight;
        zombie.sightRange *= sight;
        ai.noiseSeekDist *= hearing;
        foreach (EAISetNearestEntityAsTarget target in ai.GetTargetTasks<EAISetNearestEntityAsTarget>() ?? new List<EAISetNearestEntityAsTarget>())
        {
            for (int i = 0; i < target.targetClasses.Count; i++)
            {
                EAISetNearestEntityAsTarget.TargetClass tc = target.targetClasses[i];
                tc.hearDistMax *= hearing;
                tc.seeDistMax *= sight;
                target.targetClasses[i] = tc;
            }
        }
    }

    public static void Forget(int entityId)
    {
        applied.Remove(entityId);
    }

    public static void Clear()
    {
        applied.Clear();
    }
}
