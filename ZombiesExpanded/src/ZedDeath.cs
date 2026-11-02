using System;
using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// What mutated and ranked zombies leave behind when they die, and the Volatile's tank. On the server: the
/// Bloater's bile cloud (unless it burned), the Brood's crawlers (unless it burned or blew up), the Smoldering's
/// flare, the Volatile's tank (dropped, or blown if its fuse was lit), champions' and the Alpha's loot, the Alpha's
/// fall staggering everyone near it, a herd's leader leaving it milling. On each player's game: the effects you see.
/// </summary>
public static class ZedDeath
{
    private class Area
    {
        public Vector3 Position;
        public float Radius;
        public float Until;
        public string Buff;
        public int Instigator;
        public float Next;
    }

    private class Later
    {
        public float At;
        public Action Run;
    }

    private static readonly List<Area> areas = new List<Area>();
    private static readonly List<Later> later = new List<Later>();
    private static float auraTick;

    public static void Died(EntityAlive z, DamageResponse dr)
    {
        ZedProfile p = ZedStore.Get(z.entityId);
        ZedCombat.Forget(z.entityId);
        if (p == null)
        {
            return;
        }
        EnumDamageTypes type = dr.Source != null ? dr.Source.GetDamageType() : EnumDamageTypes.None;
        bool burned = type == EnumDamageTypes.Heat || (z.Buffs != null && z.Buffs.HasBuff("buffIsOnFire"));
        bool exploded = dr.HitDirection == Utils.EnumHitDirection.Explosion;
        bool headshot = (dr.HitBodyPart & EnumBodyPartHit.Head) != 0;
        Vector3 chest = z.getChestPosition();

        if (ZedStore.DrawsLooks)
        {
            if (p.Has(ZedMutation.Bloater) && !burned)
            {
                ZedModels.Effect("BileCloud", chest, 6f);
            }
            if (p.Has(ZedMutation.Brood) && !burned && !exploded)
            {
                ZedModels.Effect("GoreBurst", chest - Vector3.up * 0.2f, 3f);
            }
        }
        if (!ZedStore.IsServer)
        {
            return;
        }
        ZedBrain brain = ZedBrain.Of(z);
        brain?.Release();
        ZedSnatch.Drop(z);
        if (p.Has(ZedMutation.Bloater) && !burned)
        {
            areas.Add(new Area { Position = chest, Radius = 3f, Until = Time.time + 5f, Buff = "buffZedNausea", Instigator = z.entityId });
        }
        if (p.Has(ZedMutation.Brood) && !burned && !exploded)
        {
            Vector3 pos = z.position;
            int gs = ZedRoll.Gamestage(z);
            After(0.4f, () => Brood(z.world, pos, gs));
        }
        if (p.Has(ZedMutation.Smoldering))
        {
            foreach (EntityAlive e in z.world.EntityAlives)
            {
                if (e != z && !e.IsDead() && (e.position - z.position).sqrMagnitude < 4f && e.Buffs != null)
                {
                    e.Buffs.AddBuff("buffBurningElement", z.entityId);
                }
            }
        }
        if (p.Has(ZedMutation.Volatile) && p.Tank == 0)
        {
            if (brain != null && brain.TankBlowAt > 0f)
            {
                float wait = Mathf.Max(0.05f, brain.TankBlowAt - Time.time);
                brain.TankBlowAt = -1f;
                After(wait, () => BlowTank(z, p));
            }
            else
            {
                p.Tank = 1;
                ZedStore.Changed(z);
            }
        }
        if (p.Champion || p.Alpha)
        {
            Bag(z, p.Alpha ? 2 : 1);
        }
        if (p.Alpha && brain != null)
        {
            foreach (EntityAlive near in brain.Near(20f))
            {
                ZedCombat.Stagger(near, EnumEntityStunType.Stumble, 1.5f);
            }
        }
        _ = headshot;
    }

    /// <summary>The tank goes off: a fireball that hurts players a little and zombies a lot, and some blocks.</summary>
    public static void BlowTank(EntityAlive z, ZedProfile p)
    {
        if (z == null || p == null || p.Tank == 2)
        {
            return;
        }
        p.Tank = 2;
        ZedStore.Changed(z);
        Vector3 pos = z.getChestPosition();
        DynamicProperties props = new DynamicProperties();
        props.SetValue("Explosion", "ParticleIndex", "8");
        props.SetValue("Explosion", "RadiusBlocks", "2");
        props.SetValue("Explosion", "BlockDamage", "80");
        props.SetValue("Explosion", "RadiusEntities", "4");
        props.SetValue("Explosion", "EntityDamage", "60");
        props.SetValue("Explosion", "DamageType", "Heat");
        GameManager.Instance.ExplosionServer(pos, World.worldToBlockPos(pos), Quaternion.identity, new ExplosionData(props), z.entityId, 0f, false);
        foreach (EntityAlive e in z.world.EntityAlives)
        {
            if (e != z && !e.IsDead() && ZedStore.IsZombie(e) && (e.position - pos).sqrMagnitude < 16f)
            {
                e.DamageEntity(new DamageSource(EnumDamageSource.External, EnumDamageTypes.Crushing), 240, false);
            }
        }
    }

    /// <summary>Two weak crawlers burst out of the Brood's sac.</summary>
    private static void Brood(World world, Vector3 pos, int gs)
    {
        int cls = EntityClass.FromString(gs >= 70 ? "zombieSteveCrawlerFeral" : "zombieSteveCrawler");
        if (!EntityClass.list.ContainsKey(cls))
        {
            return;
        }
        for (int i = 0; i < 2; i++)
        {
            Vector3 at = pos + new Vector3(UnityEngine.Random.Range(-0.6f, 0.6f), 0.2f, UnityEngine.Random.Range(-0.6f, 0.6f));
            ZedProfile.ForceNext = new ZedForce { Plain = true };
            try
            {
                Entity e = EntityFactory.CreateEntity(cls, at, new Vector3(0f, UnityEngine.Random.Range(0f, 360f), 0f));
                if (e is EntityAlive ea)
                {
                    ea.SetSpawnerSource(EnumSpawnerSource.Dynamic);
                    world.SpawnEntityInWorld(ea);
                    ea.Buffs?.AddBuff("buffZedWeakBrood");
                }
            }
            finally
            {
                ZedProfile.ForceNext = null;
            }
        }
    }

    private static void Bag(EntityAlive z, int count)
    {
        int cls = EntityClass.FromString("EntityLootContainerStrong");
        if (!EntityClass.list.ContainsKey(cls))
        {
            return;
        }
        for (int i = 0; i < count; i++)
        {
            Entity bag = EntityFactory.CreateEntity(cls, z.GetPosition() + new Vector3(i * 0.4f, 0.9f, 0f), Vector3.zero);
            z.world.SpawnEntityInWorld(bag);
        }
        Audio.Manager.BroadcastPlay(z.GetPosition(), "zpack_spawn");
    }

    private static void After(float seconds, Action run)
    {
        later.Add(new Later { At = Time.time + seconds, Run = run });
    }

    /// <summary>Every game update on the server: lingering clouds, delayed effects, and the Alpha's aura.</summary>
    public static void Update()
    {
        if (!ZedStore.IsServer)
        {
            return;
        }
        float now = Time.time;
        for (int i = later.Count - 1; i >= 0; i--)
        {
            if (now >= later[i].At)
            {
                Later l = later[i];
                later.RemoveAt(i);
                try
                {
                    l.Run();
                }
                catch (Exception e)
                {
                    Log.Exception(e);
                }
            }
        }
        World world = GameManager.Instance.World;
        for (int i = areas.Count - 1; i >= 0; i--)
        {
            Area a = areas[i];
            if (now > a.Until)
            {
                areas.RemoveAt(i);
                continue;
            }
            if (now < a.Next)
            {
                continue;
            }
            a.Next = now + 0.5f;
            foreach (EntityPlayer p in world.Players.list)
            {
                if (!p.IsDead() && (p.getChestPosition() - a.Position).sqrMagnitude < a.Radius * a.Radius)
                {
                    p.Buffs.AddBuff(a.Buff, a.Instigator);
                }
            }
        }
        if (now >= auraTick)
        {
            auraTick = now + 1f;
            ZedBrain.AlphaAura();
            ZedRoll.Tick(world);
        }
    }

    public static void Clear()
    {
        areas.Clear();
        later.Clear();
    }
}

[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.ClientKill))]
public class ZedKillPatch
{
    public static void Prefix(EntityAlive __instance, DamageResponse _dmResponse)
    {
        try
        {
            if (!__instance.IsDead() && ZedStore.IsZombie(__instance))
            {
                ZedDeath.Died(__instance, _dmResponse);
            }
        }
        catch (Exception e)
        {
            Log.Exception(e);
        }
    }
}
