using UnityEngine;

/// <summary>
/// The statuses traps put on zombies (buffs in Config/buffs.xml) and the tags the traps check. Buffs on zombies run
/// on the server and sync to clients like the vanilla ones; the C# here only decides which buff and sets the cvars
/// that pick a buff's strength.
/// </summary>
public static class TrapStatusDEM
{
    /// <summary>From the Sprinkler: slower, can't burn, and the Tesla Coil hits it harder.</summary>
    public const string Soaked = "buffDementiveTrapsSoaked";
    /// <summary>From the Grease Slick and Tar Sprayer: slower, and fire turns it into an Inferno.</summary>
    public const string Tarred = "buffDementiveTrapsTarred";
    /// <summary>The traps' own fire (Burn Barrel, Flame Vent): weaker than a molotov.</summary>
    public const string Burning = "buffDementiveTrapsBurning";
    /// <summary>A tarred zombie set alight: triple burn, spreading to tarred zombies nearby.</summary>
    public const string Inferno = "buffDementiveTrapsInferno";
    /// <summary>From the Cryo Vent: stacks (cvar dementiveChill), each slower; enough stacks freeze.</summary>
    public const string Chilled = "buffDementiveTrapsChilled";
    public const string Frozen = "buffDementiveTrapsFrozen";
    public const string FrozenImmune = "buffDementiveTrapsFrozenImmune";
    /// <summary>From the Bear Trap: can't move.</summary>
    public const string Held = "buffDementiveTrapsHeld";
    /// <summary>Just knocked back: not again for a moment.</summary>
    public const string Knocked = "buffDementiveTrapsKnocked";

    /// <summary>Tarred strength: 1 normal (35% slower), 2 Deep Grease (55%), 3 Sticky Tar (60%).</summary>
    public const string TarLevelVar = "dementiveTarLevel";
    /// <summary>1, or 2 for Volatile grease or tar (Infernos 50% stronger).</summary>
    public const string InfernoPowerVar = "dementiveInfernoPower";
    /// <summary>1 (spreads 3 m), or 2 for Volatile Tar (5 m).</summary>
    public const string InfernoSpreadVar = "dementiveInfernoSpread";
    public const string ChillVar = "dementiveChill";

    /// <summary>Vanilla fire buffs: a tarred zombie that catches any of these goes up as an Inferno (in
    /// buffs.xml).</summary>
    public static readonly string[] VanillaFire =
    {
        "buffBurningMolotov", "buffBurningFlamingArrow", "buffBurningElement", "buffBurningEnvironment",
        "buffBurningZombie", "buffIsOnFire"
    };

    /// <summary>Demolishers and bosses: can't be frozen or stunned for long, slows are halved.</summary>
    public static readonly FastTags<TagGroup.Global> BigTags = FastTags<TagGroup.Global>.Parse("boss");

    /// <summary>Charged zombies shrug off shocks, like the vanilla stun baton's.</summary>
    public static readonly FastTags<TagGroup.Global> ChargedTags = FastTags<TagGroup.Global>.Parse("charged");

    public static bool IsSoaked(EntityAlive entity)
    {
        return entity.Buffs.HasBuff(Soaked);
    }

    public static bool IsTarred(EntityAlive entity)
    {
        return entity.Buffs.HasBuff(Tarred);
    }

    public static bool IsFrozen(EntityAlive entity)
    {
        return entity.Buffs.HasBuff(Frozen);
    }

    public static bool IsBurning(EntityAlive entity)
    {
        if (entity.Buffs.HasBuff(Burning) || entity.Buffs.HasBuff(Inferno))
        {
            return true;
        }
        foreach (string b in VanillaFire)
        {
            if (entity.Buffs.HasBuff(b))
            {
                return true;
            }
        }
        return false;
    }

    public static bool IsBig(EntityAlive entity)
    {
        return entity.HasAnyTags(BigTags);
    }

    public static bool IsShockImmune(EntityAlive entity)
    {
        return entity.HasAnyTags(ChargedTags) || entity.Buffs.HasBuff("buffShockImmune");
    }

    public static bool IsFire(EnumDamageTypes type)
    {
        return type == EnumDamageTypes.Heat;
    }

    /// <summary>
    /// Server: tars a zombie for `seconds`. The strongest tar on it wins while it lasts (level 1 normal, 2 Deep Grease,
    /// 3 Sticky Tar), and so do Volatile's stronger, wider Infernos. A tarred zombie that's already burning goes up
    /// at once.
    /// </summary>
    public static void Tar(EntityAlive e, int level, bool volatileInferno, bool wideSpread, float seconds,
        int instigator)
    {
        EntityBuffs buffs = e.Buffs;
        bool had = buffs.HasBuff(Tarred);
        buffs.SetCustomVar(TarLevelVar, had ? Mathf.Max(buffs.GetCustomVar(TarLevelVar), level) : level);
        buffs.SetCustomVar(InfernoPowerVar,
            had ? Mathf.Max(buffs.GetCustomVar(InfernoPowerVar), volatileInferno ? 2 : 1) : volatileInferno ? 2 : 1);
        buffs.SetCustomVar(InfernoSpreadVar,
            had ? Mathf.Max(buffs.GetCustomVar(InfernoSpreadVar), wideSpread ? 2 : 1) : wideSpread ? 2 : 1);
        buffs.AddBuff(Tarred, instigator, true, false, seconds);
        if (IsBurning(e) && !IsSoaked(e) && !buffs.HasBuff(Inferno))
        {
            StartInferno(e, instigator);
        }
    }

    /// <summary>Server: sets a zombie on fire with the traps' own fire (an Inferno if it's tarred). Soaked zombies
    /// don't light. Returns whether it caught.</summary>
    public static bool Ignite(EntityAlive e, float seconds, int instigator)
    {
        if (IsSoaked(e))
        {
            return false;
        }
        if (IsTarred(e))
        {
            StartInferno(e, instigator);
            return true;
        }
        if (!e.Buffs.HasBuff(Inferno))
        {
            e.Buffs.AddBuff(Burning, instigator, true, false, seconds);
        }
        return true;
    }

    /// <summary>Server: turns a tarred zombie into an Inferno (its tar burns off).</summary>
    public static void StartInferno(EntityAlive e, int instigator)
    {
        e.Buffs.AddBuff(Inferno, instigator, true, false);
        e.Buffs.RemoveBuff(Tarred);
    }

    /// <summary>
    /// Server: adds Chilled stacks. At `freezeAt` stacks the zombie freezes for `freezeSeconds`, then can't freeze
    /// again for 6 s (it can still be chilled). Big zombies never freeze. Returns true when it froze.
    /// </summary>
    public static bool Chill(EntityAlive e, int stacks, int freezeAt, float freezeSeconds, float chillSeconds,
        int instigator)
    {
        EntityBuffs buffs = e.Buffs;
        if (buffs.HasBuff(Frozen))
        {
            return false;
        }
        float current = buffs.HasBuff(Chilled) ? buffs.GetCustomVar(ChillVar) : 0f;
        float next = current + stacks;
        if (next >= freezeAt && !IsBig(e) && !buffs.HasBuff(FrozenImmune))
        {
            buffs.RemoveBuff(Chilled);
            buffs.SetCustomVar(ChillVar, 0f);
            buffs.AddBuff(Frozen, instigator, true, false, freezeSeconds);
            buffs.AddBuff(FrozenImmune, instigator, true, false, freezeSeconds + 6f);
            return true;
        }
        buffs.SetCustomVar(ChillVar, Mathf.Clamp(next, 1f, Mathf.Max(1, freezeAt - 1)));
        buffs.AddBuff(Chilled, instigator, true, false, chillSeconds);
        return false;
    }

    /// <summary>
    /// Server: knocks a zombie back about `meters` (a short ragdoll, synced to everyone by the game), at most once
    /// every couple of seconds. The force is scaled by the zombie's mass like the vanilla Ragdoll action, so every
    /// zombie flies about as far; big zombies half as far.
    /// </summary>
    public static bool Knockback(EntityAlive e, Vector3 dir, float meters)
    {
        if (meters <= 0f || e.emodel == null || !e.IsAlive() || e.Buffs.HasBuff(Knocked))
        {
            return false;
        }
        dir.y = 0f;
        if (dir.sqrMagnitude < 0.0001f)
        {
            return false;
        }
        dir.Normalize();
        float mass = 70f;
        if (EntityClass.list.TryGetValue(e.entityClass, out EntityClass ec) && ec.MassKg > 1f)
        {
            mass = ec.MassKg;
        }
        // About 70 per meter at the vanilla Home Run scale (force 1400 x mass x 0.013)
        float force = meters * KnockbackPerMeter * mass * 0.013f;
        if (IsBig(e))
        {
            force *= 0.5f;
        }
        Vector3 vec = (dir + Vector3.up * 0.35f) * force;
        e.emodel.DoRagdoll(EModelBase.RagdollMode.Default, 0.6f, EnumBodyPartHit.Torso, vec, e.getChestPosition(),
            false);
        e.Buffs.AddBuff(Knocked, -1, true, false);
        return true;
    }

    /// <summary>Knockback force per meter (before mass); a guess to be tuned in game.</summary>
    public static float KnockbackPerMeter = 70f;
}
