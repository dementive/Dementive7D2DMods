using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// A zombie's own behavior on the server, a few times a second, on top of the game's AI: a Regenerator healing, a
/// Sprinter running out of breath, lunges at players backing away, a Hulking's charge, noticing a flashlight beam,
/// searching where it lost you, following its herd's leader, dozing by day, a Screecher's shriek, a Grabber picking
/// who's busy, a champion's roar, the Alpha's rallying, the Volatile's fuse. Speed changes go through SpeedFactor,
/// which the move-speed patches apply.
/// </summary>
public class ZedBrain : MonoBehaviour
{
    private static readonly Dictionary<int, ZedBrain> brains = new Dictionary<int, ZedBrain>();
    private static readonly List<ZedBrain> alphas = new List<ZedBrain>();

    public EntityAlive Zombie;
    public ZedProfile Profile;

    /// <summary>When it was last hit (a Regenerator heals 3 s after).</summary>
    public float LastHit = -100f;
    /// <summary>The player a Grabber is holding, and until when.</summary>
    public EntityAlive Holding;
    /// <summary>A Hulking's next hit knocks you back while this is in the future.</summary>
    public float KnockbackUntil;
    /// <summary>Chest damage a Volatile's tank has taken; when it's armed, it blows at TankBlowAt.</summary>
    public float TankDamage;
    public float TankBlowAt = -1f;
    /// <summary>Poise: how much more it takes before it staggers (worked out on every game from the same hits).</summary>
    public float Poise = -1f;
    public float PoiseHitAt;
    /// <summary>When a Screecher shrieked (it hangs back for a few seconds after).</summary>
    public float ShriekedAt;
    /// <summary>A Lurker that has been in a fight (close to its target, hit, hitting, or cornered) stops lurking.</summary>
    public bool Engaged;
    /// <summary>A Lurker being looked at by a player (worked out by its lurk task).</summary>
    public bool Watched;
    /// <summary>A Snatcher: since when it has been waiting for the victim's game to hand an item over (-1: not
    /// waiting), and when it may grab again after nothing came of it. What it carries is kept by ZedStore.</summary>
    public float Waiting = -1f;
    public float SnatchAgain;

    private float spawnTime;
    private bool healPending;
    private float tick;
    private float sprintTime, exhaustedUntil;
    private float backedOff, boostUntil, boost = 1f, boostCooldown;
    private float chargeCooldown;
    private float lookTick, grabTick, dozeTick;
    private bool shrieked, roared;
    private EntityAlive lastTarget;
    private Vector3 lastSeen;
    private int searchesLeft;
    private float nextSearch;
    private bool dormant, dormantRolled;
    private float savedSight;
    private readonly List<KeyValuePair<EAIWander, float>> savedWander = new List<KeyValuePair<EAIWander, float>>();
    private float millUntil;
    private bool leaderGone;
    private float alphaRoarAt;
    private float auraUntil;
    private float unseen;

    public static void Attach(EntityAlive zombie, ZedProfile p, bool fresh)
    {
        if (zombie.GetComponent<ZedBrain>() != null)
        {
            return;
        }
        ZedBrain b = zombie.gameObject.AddComponent<ZedBrain>();
        b.Zombie = zombie;
        b.Profile = p;
        b.spawnTime = Time.time;
        b.healPending = fresh;
        b.tick = Random.value * 0.25f;
        brains[zombie.entityId] = b;
        if (p.Alpha)
        {
            alphas.Add(b);
        }
    }

    public static ZedBrain Of(Entity e)
    {
        return e != null && brains.TryGetValue(e.entityId, out ZedBrain b) && b != null ? b : null;
    }

    public static void Clear()
    {
        brains.Clear();
        alphas.Clear();
    }

    private void OnDestroy()
    {
        if (Zombie != null)
        {
            brains.Remove(Zombie.entityId);
        }
        alphas.Remove(this);
        Release();
    }

    /// <summary>What the zombie's speed is multiplied by right now (the move-speed patches apply it; aggro is chase speed).</summary>
    public float SpeedFactor(bool aggro)
    {
        float now = Time.time;
        float f = 1f;
        if (now < exhaustedUntil || now < millUntil)
        {
            return 0.15f;
        }
        if (Profile.Alpha && now - spawnTime < 45f && Zombie.Health > Zombie.GetMaxHealth() * 0.7f)
        {
            // The Alpha holds back behind its horde at first
            f *= 0.55f;
        }
        if (aggro)
        {
            if (Profile.Has(ZedMutation.Sprinter) && Zombie.world.IsDaytime())
            {
                f *= 1.45f;
            }
            if (now < boostUntil)
            {
                f *= boost;
            }
            if (Profile.Has(ZedMutation.Lurker) && !Engaged && !Watched && Zombie.GetAttackTarget() is EntityPlayer)
            {
                // Darting in while nobody's looking
                f *= 1.3f;
            }
            if (Profile.Has(ZedMutation.Snatcher))
            {
                // Quick on its feet, by day or night
                f *= Zombie.world.IsDaytime() ? 1.6f : 1.2f;
            }
        }
        if (now < auraUntil)
        {
            f *= 1.1f;
        }
        return f;
    }

    /// <summary>A Hulking never runs except when it charges.</summary>
    public bool CapAtWalk => Profile.Has(ZedMutation.Hulking) && !(Time.time < boostUntil && boost > 1.5f);

    private void Update()
    {
        if (Zombie == null || Zombie.IsDead() || !ZedStore.IsServer)
        {
            return;
        }
        tick += Time.deltaTime;
        if (tick < 0.25f)
        {
            return;
        }
        float dt = tick;
        tick = 0f;
        float now = Time.time;

        if (healPending && now - spawnTime > 0.5f)
        {
            // Health changes from the mutation and rank buffs: start at full
            healPending = false;
            Zombie.Health = Zombie.GetMaxHealth();
        }
        if (TankBlowAt > 0f && now >= TankBlowAt)
        {
            TankBlowAt = -1f;
            ZedDeath.BlowTank(Zombie, Profile);
        }

        EntityAlive target = Zombie.GetAttackTarget();
        Regenerate(now, dt);
        Sprint(target, now, dt);
        Lunge(target, now, dt);
        Charge(target, now);
        Shriek(target);
        Escape(dt);
        Roar(target);
        Rally(target, now);
        Grab(target, now);
        if (ZedSettings.Senses)
        {
            Flashlight(target, now);
            Search(target, now);
        }
        if (ZedSettings.Crowd)
        {
            Herd(target, now);
            Doze(target, now);
        }
        if (Holding != null && (now > grabEnd || Holding.IsDead() || (Holding.position - Zombie.position).sqrMagnitude > 9f))
        {
            Release();
        }
    }

    // ------------------------------------------------------------------ mutations

    private void Regenerate(float now, float dt)
    {
        if (!Profile.Has(ZedMutation.Regenerator) || now - LastHit < 3f || Burning())
        {
            return;
        }
        int max = Zombie.GetMaxHealth();
        if (Zombie.Health < max)
        {
            Zombie.AddHealth(Mathf.Max(1, Mathf.RoundToInt(max * 0.02f * dt)));
        }
    }

    public bool Burning()
    {
        return Zombie.Buffs != null && Zombie.Buffs.HasBuff("buffIsOnFire");
    }

    private void Sprint(EntityAlive target, float now, float dt)
    {
        if (!Profile.Has(ZedMutation.Sprinter) || now < exhaustedUntil)
        {
            return;
        }
        if (target != null && Running(Zombie))
        {
            sprintTime += dt;
            if (sprintTime >= 8f)
            {
                // Doubled over, catching its breath
                sprintTime = 0f;
                exhaustedUntil = now + 3f;
                ZedCombat.Stagger(Zombie, EnumEntityStunType.Kneel, 3f);
            }
        }
        else
        {
            sprintTime = Mathf.Max(0f, sprintTime - dt);
        }
    }

    /// <summary>A short burst at a player who keeps backing away within reach.</summary>
    private void Lunge(EntityAlive target, float now, float dt)
    {
        if (!ZedSettings.Crowd || !(target is EntityPlayer) || now < boostCooldown)
        {
            return;
        }
        Vector3 away = target.position - Zombie.position;
        float dist = away.magnitude;
        Vector3 v = target.GetVelocityPerSecond();
        bool backing = dist < 3f && Vector3.Dot(v, away / Mathf.Max(dist, 0.01f)) > 0.8f;
        backedOff = backing ? backedOff + dt : 0f;
        if (backedOff >= 2f)
        {
            backedOff = 0f;
            Boost(1.6f, 0.8f, 6f);
        }
    }

    /// <summary>A Hulking charges across open ground: a short sprint whose hit knocks you back.</summary>
    private void Charge(EntityAlive target, float now)
    {
        if (!Profile.Has(ZedMutation.Hulking) || target == null || now < chargeCooldown)
        {
            return;
        }
        float dist = (target.position - Zombie.position).magnitude;
        if (dist > 4f && dist < 10f && Zombie.CanSee(target))
        {
            chargeCooldown = now + 8f;
            Boost(1.8f, 1.3f, 0f);
            KnockbackUntil = now + 2.3f;
        }
    }

    /// <summary>A short burst of speed (a Possum getting up).</summary>
    public void Lunge()
    {
        Boost(1.6f, 1f, 0f);
    }

    /// <summary>A Snatcher carrying something gets away (gone, and the item with it) 60 m from every player, or
    /// after 20 s out of everyone's sight.</summary>
    private void Escape(float dt)
    {
        if (!Profile.Carrying || !Profile.Has(ZedMutation.Snatcher) || Waiting > 0f)
        {
            return;
        }
        bool near = false;
        foreach (EntityPlayer player in Zombie.world.Players.list)
        {
            near |= !player.IsDead() && (player.position - Zombie.position).sqrMagnitude < 60f * 60f;
        }
        unseen = ZedTasks.InSight(Zombie) ? 0f : unseen + dt;
        if (!near || unseen >= 20f)
        {
            ZedStore.SetLoot(Zombie.entityId, null);
            Zombie.Despawn();
        }
    }

    private void Boost(float factor, float seconds, float cooldown)
    {
        boost = factor;
        boostUntil = Time.time + seconds;
        if (cooldown > 0f)
        {
            boostCooldown = Time.time + cooldown;
        }
    }

    /// <summary>The Screecher's shriek, the first time it has someone: every zombie within 25 m comes, and it hangs
    /// back for a few seconds while they do (EAIZedHangBack).</summary>
    private void Shriek(EntityAlive target)
    {
        if (shrieked || !Profile.Has(ZedMutation.Screecher) || target == null)
        {
            return;
        }
        shrieked = true;
        ShriekedAt = Time.time;
        Audio.Manager.BroadcastPlay(Zombie, "zombiefemalescoutalert");
        Call(target, 25f);
    }

    /// <summary>A champion, once, badly hurt: pulls the zombies near it in.</summary>
    private void Roar(EntityAlive target)
    {
        if (roared || !(Profile.Champion || Profile.Alpha) || target == null || Zombie.Health > Zombie.GetMaxHealth() * 0.3f)
        {
            return;
        }
        roared = true;
        Audio.Manager.BroadcastPlay(Zombie, "zombieferalsense");
        Call(target, 25f);
    }

    /// <summary>The Alpha's roars: every 20 s, the zombies within 20 m surge for a few seconds.</summary>
    private void Rally(EntityAlive target, float now)
    {
        if (!Profile.Alpha || target == null || now < alphaRoarAt)
        {
            return;
        }
        alphaRoarAt = now + 20f;
        Audio.Manager.BroadcastPlay(Zombie, "zombieferalsense");
        foreach (EntityAlive z in Near(20f))
        {
            ZedBrain b = Of(z);
            if (b != null)
            {
                b.Boost(1.25f, 3f, 0f);
            }
        }
    }

    /// <summary>Zombies near the Alpha (while it lives) are 10% faster; called by the Alpha for its followers.</summary>
    public static void AlphaAura()
    {
        float now = Time.time;
        foreach (ZedBrain a in alphas)
        {
            if (a == null || a.Zombie == null || a.Zombie.IsDead())
            {
                continue;
            }
            foreach (EntityAlive z in a.Near(20f))
            {
                ZedBrain b = Of(z);
                if (b != null)
                {
                    b.auraUntil = now + 1.5f;
                }
            }
        }
    }

    private void Call(EntityAlive target, float range)
    {
        foreach (EntityAlive z in Near(range))
        {
            if (z.GetAttackTarget() == null)
            {
                z.SetAttackTarget(target, 1200);
            }
        }
    }

    /// <summary>Living zombies within `range` of this one (not itself).</summary>
    public List<EntityAlive> Near(float range)
    {
        List<EntityAlive> list = new List<EntityAlive>();
        float r2 = range * range;
        foreach (EntityAlive e in Zombie.world.EntityAlives)
        {
            if (e != Zombie && !e.IsDead() && ZedStore.IsZombie(e) && (e.position - Zombie.position).sqrMagnitude < r2)
            {
                list.Add(e);
            }
        }
        return list;
    }

    // ------------------------------------------------------------------ grabs

    private float grabEnd;

    /// <summary>A Grabber goes for whoever is busiest: the player with the most other zombies on them.</summary>
    private void Grab(EntityAlive target, float now)
    {
        if (!Profile.Has(ZedMutation.Grabber) || target == null || now < grabTick)
        {
            return;
        }
        grabTick = now + 2f;
        EntityPlayer best = null;
        int bestCount = 0;
        foreach (EntityPlayer p in Zombie.world.Players.list)
        {
            if (p.IsDead() || (p.position - Zombie.position).sqrMagnitude > 15f * 15f)
            {
                continue;
            }
            int count = 0;
            foreach (EntityAlive z in Zombie.world.EntityAlives)
            {
                if (z != Zombie && !z.IsDead() && ZedStore.IsZombie(z) && (z.position - p.position).sqrMagnitude < 16f)
                {
                    count++;
                }
            }
            if (count > bestCount)
            {
                bestCount = count;
                best = p;
            }
        }
        if (best != null && best != target)
        {
            Zombie.SetAttackTarget(best, 1200);
        }
    }

    /// <summary>A Grabber's hit caught `player`: hold them for 2 s.</summary>
    public void Hold(EntityAlive player)
    {
        Release();
        Holding = player;
        grabEnd = Time.time + 2f;
        player.Buffs.AddBuff("buffZedGrabbed");
    }

    /// <summary>Lets go (a hit on it, the time ran out, it died): the player can't be grabbed again for 8 s.</summary>
    public void Release()
    {
        if (Holding == null)
        {
            return;
        }
        if (Holding.Buffs != null && !Holding.IsDead())
        {
            Holding.Buffs.RemoveBuff("buffZedGrabbed");
            Holding.Buffs.AddBuff("buffZedGrabImmune");
        }
        Holding = null;
    }

    // ------------------------------------------------------------------ senses

    /// <summary>At night, a flashlight or other light pointed at a zombie within 35 m gives you away.</summary>
    private void Flashlight(EntityAlive target, float now)
    {
        if (target != null || now < lookTick || !Zombie.world.IsDark())
        {
            return;
        }
        lookTick = now + 1f;
        Vector3 chest = Zombie.getChestPosition();
        foreach (EntityPlayer p in Zombie.world.Players.list)
        {
            if (p.IsDead() || p.GetLightLevel() < 0.01f)
            {
                continue;
            }
            Vector3 to = chest - p.getHeadPosition();
            float d = to.magnitude;
            if (d > 35f || d < 1f || Vector3.Dot(p.GetLookVector(), to / d) < 0.966f)
            {
                continue;
            }
            if (!Voxel.Raycast(Zombie.world, new Ray(p.getHeadPosition(), to / d), d - 0.5f, false, false))
            {
                Zombie.SetAttackTarget(p, 1200);
                return;
            }
        }
    }

    /// <summary>When it loses you, it looks around where it last saw you before giving up; longer if relentless.</summary>
    private void Search(EntityAlive target, float now)
    {
        if (target != null)
        {
            lastTarget = target;
            lastSeen = target.position;
            searchesLeft = 0;
            return;
        }
        if (lastTarget != null)
        {
            lastTarget = null;
            searchesLeft = Profile.Temper == ZedTemper.Sluggish ? 1 : Profile.Temper == ZedTemper.Relentless ? 6
                : Profile.Temper == ZedTemper.Restless ? 4 : 3;
            nextSearch = now + 1f;
        }
        if (searchesLeft > 0 && now >= nextSearch)
        {
            searchesLeft--;
            nextSearch = now + 8f;
            Vector3 p = lastSeen + new Vector3(Random.Range(-6f, 6f), 0f, Random.Range(-6f, 6f));
            Zombie.SetInvestigatePosition(p, 160, true);
        }
    }

    // ------------------------------------------------------------------ the crowd

    /// <summary>Without a target, a group's zombies keep near its leader (the biggest); if the leader dies, they mill
    /// about for a few seconds.</summary>
    private void Herd(EntityAlive target, float now)
    {
        if (target != null || leaderGone)
        {
            return;
        }
        int leaderId = ZedRoll.LeaderOf(Zombie.entityId);
        if (leaderId < 0 || leaderId == Zombie.entityId)
        {
            return;
        }
        EntityAlive leader = Zombie.world.GetEntity(leaderId) as EntityAlive;
        if (leader == null || leader.IsDead())
        {
            leaderGone = true;
            if (leader != null)
            {
                millUntil = now + 5f;
            }
            return;
        }
        if ((leader.position - Zombie.position).sqrMagnitude > 64f && !Zombie.HasInvestigatePosition)
        {
            Vector3 p = leader.position + new Vector3(Random.Range(-3f, 3f), 0f, Random.Range(-3f, 3f));
            Zombie.SetInvestigatePosition(p, 200, false);
        }
    }

    /// <summary>Outdoors by day, some zombies (not restless ones) stand dozing: they notice you late and don't wander.</summary>
    private void Doze(EntityAlive target, float now)
    {
        if (now < dozeTick)
        {
            return;
        }
        dozeTick = now + 10f;
        if (!dormantRolled)
        {
            dormantRolled = true;
            if (Profile.Temper == ZedTemper.Restless || (Profile.Seed & 0xff) >= 77)
            {
                return;
            }
        }
        else if (Profile.Temper == ZedTemper.Restless || (Profile.Seed & 0xff) >= 77)
        {
            return;
        }
        bool should = target == null && Zombie.world.IsDaytime() && !Zombie.IsSleeper && !Zombie.IsBloodMoon && Outdoors();
        if (should && !dormant)
        {
            dormant = true;
            // The game works sight out from sightRangeBase on every check, so that's the one to dull
            savedSight = Zombie.sightRangeBase;
            Zombie.sightRangeBase *= 0.5f;
            savedWander.Clear();
            foreach (EAIWander w in Zombie.aiManager?.GetTasks<EAIWander>() ?? new List<EAIWander>())
            {
                savedWander.Add(new KeyValuePair<EAIWander, float>(w, w.executePercent));
                w.executePercent = 0f;
            }
        }
        else if (!should && dormant)
        {
            dormant = false;
            Zombie.sightRangeBase = savedSight;
            foreach (KeyValuePair<EAIWander, float> kv in savedWander)
            {
                kv.Key.executePercent = kv.Value;
            }
        }
    }

    private bool Outdoors()
    {
        Vector3 top = Zombie.getHeadPosition() + Vector3.up * 0.6f;
        return !Voxel.Raycast(Zombie.world, new Ray(top, Vector3.up), 40f, false, false);
    }

    /// <summary>After its health changed (a champion room's promotion): back to full half a second later.</summary>
    public void HealSoon()
    {
        healPending = true;
        spawnTime = Time.time;
    }

    /// <summary>Whether a zombie is actually running (moving faster than a walk), from its movement.</summary>
    public static bool Running(EntityAlive z)
    {
        Vector3 v = z.GetVelocityPerSecond();
        v.y = 0f;
        return v.sqrMagnitude > 2.5f * 2.5f;
    }

    /// <summary>A herd that just lost its leader, or an Alpha's death: everyone near stumbles.</summary>
    public void Mill(float seconds)
    {
        millUntil = Time.time + seconds;
    }
}
