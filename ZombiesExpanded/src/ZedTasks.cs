using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The mutations' AI tasks, added on the server to a zombie's own task list (alongside its normal tasks, so other
/// mods' AI edits stay) at a higher priority: the game's own leap for Leapers, its run-when-hurt for Regenerators
/// (they slink off to heal), a Screecher hanging back after its shriek, the Stalker's stalk and the Lurker's lurk.
/// </summary>
public static class ZedTasks
{
    /// <summary>Adds the tasks for `mutations` (all of a new zombie's, or those a champion just gained).</summary>
    public static void Add(EntityAlive zombie, ZedProfile p, IList<ZedMutation> mutations)
    {
        EAIManager ai = zombie.aiManager;
        if (ai == null || mutations.Count == 0)
        {
            return;
        }
        if (mutations.Contains(ZedMutation.Leaper))
        {
            Vanilla(ai, zombie, "Leap", "");
        }
        if (mutations.Contains(ZedMutation.Regenerator))
        {
            Vanilla(ai, zombie, "RunawayWhenHurt", "runChance=1;healthPer=.4;healthPerMax=.7");
        }
        if (mutations.Contains(ZedMutation.Screecher))
        {
            Custom(ai, zombie, new EAIZedHangBack());
        }
        if (mutations.Contains(ZedMutation.Stalker))
        {
            Custom(ai, zombie, new EAIZedStalk());
        }
        if (mutations.Contains(ZedMutation.Lurker))
        {
            Custom(ai, zombie, new EAIZedLurk());
        }
        if (mutations.Contains(ZedMutation.Snatcher))
        {
            Custom(ai, zombie, new EAIZedSnatch());
        }
    }

    private static void Custom(EAIManager ai, EntityAlive zombie, EAIBase task)
    {
        task.manager = ai;
        task.Init(zombie);
        ai.tasks.AddTask(-2, task);
    }

    private static void Vanilla(EAIManager ai, EntityAlive zombie, string name, string data)
    {
        EAIBase task = EAIManager.CreateInstance(name);
        if (task == null)
        {
            return;
        }
        task.manager = ai;
        task.Init(zombie);
        Dictionary<string, string> d = new Dictionary<string, string>();
        foreach (string kv in data.Split(';'))
        {
            int eq = kv.IndexOf('=');
            if (eq > 0)
            {
                d[kv.Substring(0, eq)] = kv.Substring(eq + 1);
            }
        }
        task.SetData(d);
        ai.tasks.AddTask(-1, task);
    }

    /// <summary>Whether any living player within 60 m could see the zombie (nothing solid in between), wherever
    /// they're looking.</summary>
    public static bool InSight(EntityAlive zombie)
    {
        Vector3 chest = zombie.getChestPosition();
        foreach (EntityPlayer player in zombie.world.Players.list)
        {
            if (player.IsDead())
            {
                continue;
            }
            Vector3 head = player.getHeadPosition();
            Vector3 to = chest - head;
            float d = to.magnitude;
            if (d < 60f && (d < 0.1f || !Voxel.Raycast(zombie.world, new Ray(head, to / d), d - 0.6f, false, false)))
            {
                return true;
            }
        }
        return false;
    }

    /// <summary>Whether any living player within 45 m is looking at the zombie (within about 45 degrees of where
    /// they're facing) with nothing solid in between.</summary>
    public static bool Watched(EntityAlive zombie)
    {
        Vector3 chest = zombie.getChestPosition();
        foreach (EntityPlayer player in zombie.world.Players.list)
        {
            if (player.IsDead())
            {
                continue;
            }
            Vector3 head = player.getHeadPosition();
            Vector3 to = chest - head;
            float d = to.magnitude;
            if (d > 45f || d < 0.1f)
            {
                continue;
            }
            Vector3 dir = to / d;
            if (Vector3.Dot(player.GetLookVector(), dir) < 0.7f)
            {
                continue;
            }
            if (!Voxel.Raycast(zombie.world, new Ray(head, dir), d - 0.6f, false, false))
            {
                return true;
            }
        }
        return false;
    }
}

/// <summary>
/// Moving away from its target along a path, the way the game's own flee tasks do it: a spot some way off in the
/// direction away from the target, then the pathfinder, at chase speed. Ends when `Wants` stops, or when it's
/// cornered (no farther from its target after 3 s), which `Cornered` hears about.
/// </summary>
public abstract class EAIZedKeepAway : EAIBase
{
    protected EntityPlayer target;
    private float repath;
    private float bestDistance;
    private float gainedAt;
    private bool cornered;

    public override void Init(EntityAlive _theEntity)
    {
        base.Init(_theEntity);
        MutexBits = 3;
        executeDelay = 0.1f;
    }

    protected ZedProfile Profile => ZedStore.Get(theEntity.entityId);

    protected ZedBrain Brain => ZedBrain.Of(theEntity);

    /// <summary>Whether it wants to keep away from `target` right now.</summary>
    protected abstract bool Wants();

    /// <summary>How far each leg of its retreat goes.</summary>
    protected virtual float Leg => 10f;

    /// <summary>It's been backing off for 3 s without getting any farther away.</summary>
    protected virtual void Cornered()
    {
    }

    protected float Distance()
    {
        return (target.position - theEntity.position).magnitude;
    }

    public override bool CanExecute()
    {
        target = theEntity.GetAttackTarget() as EntityPlayer;
        return target != null && !target.IsDead() && Wants();
    }

    public override void Start()
    {
        repath = 0f;
        cornered = false;
        ResetCornered();
    }

    /// <summary>Gives it a fresh 3 s to put distance on its target before it counts as cornered.</summary>
    protected void ResetCornered()
    {
        bestDistance = Distance();
        gainedAt = Time.time;
        repath = 0f;
    }

    public override bool Continue()
    {
        return !cornered && target != null && !target.IsDead() && theEntity.GetAttackTarget() == target && Wants();
    }

    public override void Update()
    {
        if (target == null)
        {
            return;
        }
        float now = Time.time;
        float dist = Distance();
        if (dist > bestDistance + 1f)
        {
            bestDistance = dist;
            gainedAt = now;
        }
        else if (now - gainedAt > 3f)
        {
            cornered = true;
            Cornered();
            return;
        }
        if (now >= repath)
        {
            repath = now + 1f;
            Vector3 away = theEntity.position - target.position;
            away.y = 0f;
            if (away.sqrMagnitude < 0.01f)
            {
                away = -theEntity.transform.forward;
            }
            Vector3 spot = RandomPositionGenerator.CalcPositionInDirection(theEntity, theEntity.position, away.normalized, Leg, 80f);
            if (spot.y != 0f)
            {
                theEntity.FindPath(spot, theEntity.GetMoveSpeedAggro(), false, this);
            }
        }
    }

    public override void Reset()
    {
        theEntity.navigator?.clearPath();
    }
}

/// <summary>
/// A Screecher after its shriek: it backs off for a few seconds while the zombies it called come, then joins the
/// attack. A hit cuts that short, and so does being cornered.
/// </summary>
public class EAIZedHangBack : EAIZedKeepAway
{
    private const float HangBack = 6f;

    protected override bool Wants()
    {
        ZedBrain brain = Brain;
        return brain != null && brain.ShriekedAt > 0f && Time.time - brain.ShriekedAt < HangBack
            && brain.LastHit < brain.ShriekedAt && Distance() < 12f;
    }

    protected override void Cornered()
    {
        ZedBrain brain = Brain;
        if (brain != null)
        {
            brain.ShriekedAt = -HangBack;
        }
    }
}

/// <summary>
/// The Lurker: until it's in a fight, it only comes at you while nobody's looking. When a player looks at it, it
/// turns and runs (looking back from 25 m off, it stands and stares). When they look away, the game's own chase takes
/// over, a third faster (see ZedBrain.SpeedFactor). Once it's within 2.5 m of its target, hits someone, is hit, or
/// is cornered, it's engaged and fights like any zombie for the rest of its life.
/// </summary>
public class EAIZedLurk : EAIZedKeepAway
{
    private float lookedAwayAt;

    protected override float Leg => 8f;

    protected override bool Wants()
    {
        ZedBrain brain = Brain;
        if (brain == null || brain.Engaged)
        {
            return false;
        }
        if (Distance() < 2.5f)
        {
            brain.Engaged = true;
            return false;
        }
        brain.Watched = ZedTasks.Watched(theEntity);
        if (brain.Watched)
        {
            lookedAwayAt = Time.time;
            return true;
        }
        // Keeps running a moment after you look away, so a glance doesn't make it stutter
        return Time.time - lookedAwayAt < 0.4f;
    }

    public override void Update()
    {
        if (target != null && Distance() > 25f)
        {
            // Far enough: it stops and watches you back
            theEntity.navigator?.clearPath();
            theEntity.moveHelper.Stop();
            theEntity.SetLookPosition(target.getHeadPosition());
            ResetCornered();
            return;
        }
        base.Update();
    }

    protected override void Cornered()
    {
        ZedBrain brain = Brain;
        if (brain != null)
        {
            brain.Engaged = true;
        }
    }
}

/// <summary>
/// The Stalker: while it's more than 8 m from its target, it creeps up on them crouched, toward a spot behind them,
/// freezing whenever they look its way. Watched for 1.5 s, or once it's within 8 m, it's revealed: it stands up and
/// sprints in (the game's own chase takes over). Silent until then (see ZedVoice).
/// </summary>
public class EAIZedStalk : EAIBase
{
    private EntityPlayer target;
    private float watched;
    private float repath;
    private int walkBefore = -1;

    public override void Init(EntityAlive _theEntity)
    {
        base.Init(_theEntity);
        MutexBits = 3;
        executeDelay = 0.2f;
    }

    private ZedProfile Profile => ZedStore.Get(theEntity.entityId);

    public override bool CanExecute()
    {
        ZedProfile p = Profile;
        if (p == null || p.Revealed || !p.Has(ZedMutation.Stalker))
        {
            return false;
        }
        target = theEntity.GetAttackTarget() as EntityPlayer;
        return target != null && !target.IsDead() && Distance() > 8f;
    }

    private float Distance()
    {
        return (target.position - theEntity.position).magnitude;
    }

    public override void Start()
    {
        watched = 0f;
        repath = 0f;
        walkBefore = theEntity.GetWalkType();
        theEntity.SetWalkType(EntityAlive.cWalkTypeCrouch);
        Profile.Stalking = true;
        ZedStore.Changed(theEntity);
    }

    public override bool Continue()
    {
        ZedProfile p = Profile;
        return p != null && !p.Revealed && target != null && !target.IsDead() && theEntity.GetAttackTarget() == target && Distance() > 8f;
    }

    public override void Update()
    {
        if (target == null)
        {
            return;
        }
        const float dt = 0.05f;
        Vector3 to = theEntity.getChestPosition() - target.getHeadPosition();
        bool seen = Vector3.Dot(target.GetLookVector(), to.normalized) > 0.82f;
        if (seen)
        {
            // Freeze while it's being looked at
            theEntity.moveHelper.Stop();
            watched += dt;
            if (watched > 1.5f)
            {
                Reveal();
            }
            return;
        }
        watched = Mathf.Max(0f, watched - dt * 0.5f);
        if (Time.time >= repath)
        {
            repath = Time.time + 1f;
            Vector3 back = target.GetLookVector();
            back.y = 0f;
            Vector3 spot = target.position - back.normalized * 6f;
            theEntity.moveHelper.SetMoveTo(spot, false);
        }
        theEntity.SetLookPosition(target.getHeadPosition());
    }

    public override void Reset()
    {
        ZedProfile p = Profile;
        if (p != null && !p.Revealed && target != null && Distance() <= 8.5f)
        {
            Reveal();
        }
        if (walkBefore >= 0 && theEntity.GetWalkType() == EntityAlive.cWalkTypeCrouch)
        {
            theEntity.SetWalkType(walkBefore);
        }
        if (p != null && p.Stalking)
        {
            p.Stalking = false;
            ZedStore.Changed(theEntity);
        }
    }

    private void Reveal()
    {
        ZedProfile p = Profile;
        if (p == null || p.Revealed)
        {
            return;
        }
        p.Revealed = true;
        p.Stalking = false;
        if (walkBefore >= 0)
        {
            theEntity.SetWalkType(walkBefore);
        }
        (theEntity as EntityHuman)?.StartRage(1f, 6f);
        ZedStore.Changed(theEntity);
    }
}
