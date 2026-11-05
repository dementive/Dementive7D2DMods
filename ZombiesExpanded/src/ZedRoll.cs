using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The server's rolls for a new zombie, after its individual profile: the strain its group carries and whether it
/// carries it (or, rarely, a Snatcher of its own), the gear it died in, whether it's a champion or the Blood Moon's
/// Alpha, and the remnants that tell who it was. Every model has its spots on the body (ZedSlot), and nothing is
/// put on a spot that's taken.
///
/// Strains: zombies that spawn together (same kind of spawn, within 25 m and 15 s: a POI room's sleepers, a wandering
/// horde, a Blood Moon wave) form a group. A group carries a strain at twice the mutation share for its gamestage, and
/// then half of it is mutated; so the number of mutated zombies is the same as rolling each one alone, just bunched.
/// </summary>
public static class ZedRoll
{
    private class Group
    {
        public int Id;
        public Vector3 Position;
        public float Time;
        public readonly List<ZedMutation> Strain = new List<ZedMutation>();
        public int Leader = -1;
        public float LeaderSize;
        public readonly List<int> Members = new List<int>();
    }

    private const float GroupRange = 25f;
    private const float GroupTime = 15f;

    private static readonly List<Group> groups = new List<Group>();
    private static readonly Dictionary<int, Group> byZombie = new Dictionary<int, Group>();
    private static int nextGroup = 1;
    private static bool bloodMoonWasActive;
    private static readonly HashSet<int> alphaParties = new HashSet<int>();
    private static readonly Dictionary<int, bool> rooms = new Dictionary<int, bool>();

    private static readonly FastTags<TagGroup.Global> BossTag = FastTags<TagGroup.Global>.Parse("boss");

    /// <summary>Share of zombies that carry a mutation at a gamestage.</summary>
    public static float MutationShare(int gamestage)
    {
        float s = gamestage < 30 ? 0.05f : gamestage < 60 ? 0.1f : gamestage < 100 ? 0.15f : gamestage < 150 ? 0.2f : 0.25f;
        return Mathf.Min(1f, s * (ZedSettings.Brutal ? 1.5f : 1f) * ZedSettings.Float("MutationRate", 1f));
    }

    public static float ChampionChance(int gamestage)
    {
        if (gamestage < 50)
        {
            return 0f;
        }
        return (gamestage < 150 ? 0.01f : 0.02f) * (ZedSettings.Brutal ? 1.5f : 1f) * ZedSettings.Float("ChampionRate", 1f);
    }

    public static float GearChance(int gamestage)
    {
        if (gamestage < 20)
        {
            return 0f;
        }
        return (gamestage < 100 ? 0.15f : 0.25f) * ZedSettings.Float("GearRate", 1f);
    }

    /// <summary>The gamestage that counts for a zombie: the nearest player's (or the highest, with nobody near).</summary>
    public static int Gamestage(Entity e)
    {
        int best = 0;
        float bestDist = float.MaxValue;
        int highest = 0;
        foreach (EntityPlayer p in e.world.Players.list)
        {
            highest = Math.Max(highest, p.gameStage);
            float d = (p.position - e.position).sqrMagnitude;
            if (d < bestDist)
            {
                bestDist = d;
                best = p.gameStage;
            }
        }
        return bestDist < 150f * 150f ? best : highest;
    }

    public static void Apply(EntityAlive zombie, ZedProfile p, System.Random rng)
    {
        ZedForce force = ZedProfile.ForceNext;
        bool boss = zombie.HasAnyTags(BossTag);
        if (boss || !p.Humanoid || (force != null && force.Plain))
        {
            return;
        }
        int gs = Gamestage(zombie);
        bool bloodMoon = BloodMoon(zombie.world);
        if (bloodMoon)
        {
            gs += 5;
        }

        if (ZedSettings.Mutations)
        {
            Group g = Join(zombie, gs, p.Biome, rng);
            if (g.Strain.Count > 0 && rng.NextDouble() < 0.5)
            {
                p.Mutations.Add(g.Strain[rng.Next(g.Strain.Count)]);
            }
            if (p.Size > g.LeaderSize)
            {
                g.LeaderSize = p.Size;
                g.Leader = zombie.entityId;
            }
            if (p.Mutations.Count == 0 && ZedMutationInfo.Allowed(ZedMutation.Snatcher, gs, p.Biome, solo: true)
                && rng.NextDouble() < MutationShare(gs) * 0.02f && !SnatcherNear(zombie))
            {
                // Rare, and never more than one about
                p.Mutations.Add(ZedMutation.Snatcher);
            }
        }
        bool snatcher = p.Has(ZedMutation.Snatcher);
        string family = Family(zombie.EntityClass.entityClassName);

        if (ZedSettings.Gear && !snatcher && rng.NextDouble() < GearChance(gs))
        {
            Dress(zombie, p, rng, gs);
        }

        if (ZedSettings.Champions && !snatcher && rng.NextDouble() < ChampionChance(gs))
        {
            Champion(p, rng, gs, family);
        }

        if (ZedSettings.Alpha && bloodMoon && !snatcher && AlphaDue(zombie))
        {
            Alpha(p, rng, gs, family);
        }

        if (force != null)
        {
            force.ApplyRank(p, rng, gs, family);
        }

        if (ZedSettings.Remnants && (force == null || force.Remnants.Count == 0))
        {
            Showpiece(zombie, p, rng);
            Remnants(zombie, p, rng);
        }
    }

    /// <summary>Whether a Snatcher is already about within 80 m.</summary>
    private static bool SnatcherNear(EntityAlive zombie)
    {
        foreach (EntityAlive e in zombie.world.EntityAlives)
        {
            if (e != zombie && !e.IsDead() && (e.position - zombie.position).sqrMagnitude < 80f * 80f)
            {
                ZedProfile other = ZedStore.Get(e.entityId);
                if (other != null && other.Has(ZedMutation.Snatcher))
                {
                    return true;
                }
            }
        }
        return false;
    }

    private static bool BloodMoon(World world)
    {
        AIDirector director = world?.aiDirector;
        return director != null && director.BloodMoonComponent != null && director.BloodMoonComponent.BloodMoonActive;
    }

    // ------------------------------------------------------------------ strains

    private static Group Join(EntityAlive zombie, int gs, ZedBiome biome, System.Random rng)
    {
        float now = Time.time;
        groups.RemoveAll(x => now - x.Time > 120f);
        // (Spawners set the source after the zombie is set up, so groups go by place and time alone)
        foreach (Group x in groups)
        {
            if (now - x.Time < GroupTime && (x.Position - zombie.position).sqrMagnitude < GroupRange * GroupRange)
            {
                x.Time = now;
                x.Members.Add(zombie.entityId);
                byZombie[zombie.entityId] = x;
                return x;
            }
        }
        Group g = new Group { Id = nextGroup++, Position = zombie.position, Time = now };
        g.Members.Add(zombie.entityId);
        byZombie[zombie.entityId] = g;
        groups.Add(g);
        if (rng.NextDouble() < Mathf.Min(1f, 2f * MutationShare(gs)))
        {
            List<ZedMutation> allowed = Allowed(gs, biome);
            if (gs >= 100 && rng.NextDouble() < 0.4)
            {
                ZedMutation[] pair = ZedMutationInfo.Pairs[rng.Next(ZedMutationInfo.Pairs.Length)];
                if (allowed.Contains(pair[0]) && allowed.Contains(pair[1]))
                {
                    g.Strain.AddRange(pair);
                }
            }
            if (g.Strain.Count == 0 && allowed.Count > 0)
            {
                g.Strain.Add(allowed[rng.Next(allowed.Count)]);
            }
        }
        return g;
    }

    private static List<ZedMutation> Allowed(int gs, ZedBiome biome)
    {
        List<ZedMutation> list = new List<ZedMutation>();
        foreach (ZedMutation m in ZedMutationInfo.All.Keys)
        {
            if (ZedMutationInfo.Allowed(m, gs, biome))
            {
                list.Add(m);
            }
        }
        return list;
    }

    /// <summary>The zombie its group follows (the biggest), or -1.</summary>
    public static int LeaderOf(int entityId)
    {
        return byZombie.TryGetValue(entityId, out Group g) && g.Members.Count > 2 ? g.Leader : -1;
    }

    /// <summary>The rest of a zombie's group (those still in the world are looked up by the caller).</summary>
    public static IReadOnlyList<int> GroupOf(int entityId)
    {
        return byZombie.TryGetValue(entityId, out Group g) ? g.Members : (IReadOnlyList<int>)Array.Empty<int>();
    }

    public static void Forget(int entityId)
    {
        byZombie.Remove(entityId);
    }

    public static void Clear()
    {
        groups.Clear();
        byZombie.Clear();
        alphaParties.Clear();
        bloodMoonWasActive = false;
        rooms.Clear();
    }

    /// <summary>Champion rooms: a POI's final room (a sleeper volume spawning the game's "badass" groups) has a 25%
    /// chance to hold a champion: the first zombie it spawns. Called as a sleeper volume adds a zombie to the world
    /// (sleepers are set up before the volume marks them as its own). True when this zombie should become one.</summary>
    public static bool ChampionRoom(SleeperVolume volume)
    {
        if (!ZedSettings.Champions || volume == null || volume.groupName == null
            || volume.groupName.IndexOf("Badass", StringComparison.OrdinalIgnoreCase) < 0)
        {
            return false;
        }
        int key = volume.GetHashCode();
        if (rooms.ContainsKey(key))
        {
            return false;
        }
        bool champion = UnityEngine.Random.value < 0.25f;
        rooms[key] = champion;
        return champion;
    }

    /// <summary>Called every second on the server: a new Blood Moon gets new Alphas.</summary>
    public static void Tick(World world)
    {
        bool active = BloodMoon(world);
        if (active && !bloodMoonWasActive)
        {
            alphaParties.Clear();
        }
        bloodMoonWasActive = active;
    }

    // ------------------------------------------------------------------ gear

    private static void Dress(EntityAlive zombie, ZedProfile p, System.Random rng, int gs)
    {
        string cls = zombie.EntityClass.entityClassName;
        string family = Family(cls);
        ZedSlot used = Used(p, family);
        List<ZedGearKind> options = new List<ZedGearKind>();
        if (ZedGearInfo.Jobs.TryGetValue(family, out ZedGearKind[] job))
        {
            options.AddRange(job);
        }
        else
        {
            options.AddRange(ZedGearInfo.All.Keys);
        }
        // Scrap armor's rigid chest plate would sink into a fat zombie's belly
        bool fat = zombie.GetWalkType() == EntityAlive.cWalkTypeFat || p.Body == ZedBody.Bloated;
        // Rigid body armor only sits right on a regular build: on a fat or female body it rode up or sank in
        bool regular = !fat && !Female(zombie);
        options.RemoveAll(k => ZedGearInfo.All[k].Cut || (ZedGearInfo.All[k].Slots & used) != 0 || gs < ZedGearInfo.All[k].FromGamestage
            || (k == ZedGearKind.ScrapArmor && fat) || (ZedGearInfo.All[k].BodyArmor && !regular));
        if (options.Count == 0)
        {
            return;
        }
        Wear(p, options[rng.Next(options.Count)]);
    }

    public static void Wear(ZedProfile p, ZedGearKind kind)
    {
        ZedGearInfo info = ZedGearInfo.All[kind];
        p.Gear.RemoveAll(g => g.Kind == kind);
        foreach (string part in info.Parts)
        {
            // Scrap armor's shoulder pads are small: a quarter of its soak each, the plates the rest
            float soak = kind == ZedGearKind.ScrapArmor && part.Contains("Arm") ? info.Soak * 0.25f : info.Soak;
            p.Gear.Add(new ZedGearPiece { Kind = kind, Part = part, Soak = soak });
        }
    }

    /// <summary>Whether a zombie class has a woman's body, going by its voice (the game's female zombie sounds), which
    /// works for other mods' zombies too.</summary>
    public static bool Female(EntityAlive zombie)
    {
        string hurt = zombie.EntityClass?.Properties?.GetString("SoundHurt") ?? "";
        return hurt.IndexOf("female", StringComparison.OrdinalIgnoreCase) >= 0;
    }

    /// <summary>The spots on a zombie's body already taken: by its mutations' and gear's models, its remnants, and a
    /// vanilla zombie's own hat or hood.</summary>
    public static ZedSlot Used(ZedProfile p, string family)
    {
        ZedSlot used = ZedSlot.None;
        foreach (ZedMutation m in p.Mutations)
        {
            used |= ZedMutationInfo.All[m].Slots;
        }
        foreach (ZedGearPiece g in p.Gear)
        {
            used |= ZedGearInfo.All[g.Kind].Slots;
        }
        foreach (ZedRemnant r in p.Remnants)
        {
            used |= ZedRemnantInfo.All[r].Slots;
        }
        if (Array.IndexOf(ZedGearInfo.Headwear, family) >= 0)
        {
            used |= ZedSlot.Head;
        }
        if (Array.IndexOf(ZedRemnantInfo.FaceCovered, family) >= 0)
        {
            used |= ZedSlot.Face | ZedSlot.Mouth;
        }
        return used;
    }

    /// <summary>About 1 zombie in 40 (ShowpieceRate) is a showpiece: a STOP sign through the gut, a cinder block
    /// chained to an ankle, a harpoon, a pincushion of arrows. Rolled before the everyday remnants,
    /// which then keep off its spots.</summary>
    private static void Showpiece(EntityAlive zombie, ZedProfile p, System.Random rng)
    {
        if (rng.NextDouble() >= 0.025 * ZedSettings.Float("ShowpieceRate", 1f))
        {
            return;
        }
        ZedSlot used = Used(p, Family(zombie.EntityClass.entityClassName));
        List<ZedRemnant> options = new List<ZedRemnant>();
        foreach (ZedRemnantInfo info in ZedRemnantInfo.All.Values)
        {
            if (info.Showpiece && !info.Cut && (info.Slots & used) == 0)
            {
                options.Add(info.Id);
            }
        }
        if (options.Count > 0)
        {
            p.Remnants.Add(options[rng.Next(options.Count)]);
        }
    }

    // ------------------------------------------------------------------ remnants

    /// <summary>About half of all zombies carry a remnant, and a fifth of those a second: one that fits the job when
    /// there is one (two times in three), otherwise one anyone might have. Other mods' zombies pick from everything.</summary>
    private static void Remnants(EntityAlive zombie, ZedProfile p, System.Random rng)
    {
        float rate = ZedSettings.Float("RemnantRate", 1f);
        if (rng.NextDouble() >= 0.5f * rate)
        {
            return;
        }
        string family = Family(zombie.EntityClass.entityClassName);
        int count = rng.NextDouble() < 0.2 ? 2 : 1;
        // A fat zombie's puffy face buries a cigar (its face sits well off where its head hit box says)
        ZedSlot fat = zombie.GetWalkType() == EntityAlive.cWalkTypeFat ? ZedSlot.Mouth : ZedSlot.None;
        // The wounds sit on a regular build's skin
        bool regular = fat == ZedSlot.None && p.Body != ZedBody.Bloated && !Female(zombie);
        for (int i = 0; i < count; i++)
        {
            ZedSlot used = Used(p, family) | fat;
            List<ZedRemnant> options = new List<ZedRemnant>();
            if (ZedRemnantInfo.Jobs.TryGetValue(family, out ZedRemnant[] job) && rng.NextDouble() < 0.67)
            {
                options.AddRange(job);
            }
            if (options.Count == 0)
            {
                foreach (ZedRemnantInfo info in ZedRemnantInfo.All.Values)
                {
                    if (info.Anyone || !Known(family))
                    {
                        options.Add(info.Id);
                    }
                }
            }
            options.RemoveAll(r => ZedRemnantInfo.All[r].Cut || ZedRemnantInfo.All[r].Showpiece || p.Remnants.Contains(r)
                || (ZedRemnantInfo.All[r].Slots & used) != 0 || (ZedRemnantInfo.All[r].Skin && !regular));
            if (options.Count == 0)
            {
                return;
            }
            p.Remnants.Add(options[rng.Next(options.Count)]);
        }
    }

    /// <summary>Whether a family is one of the game's own zombies (the rest come from other mods).</summary>
    private static bool Known(string family)
    {
        return ZedRemnantInfo.Jobs.ContainsKey(family) || Array.IndexOf(VanillaFamilies, family) >= 0;
    }

    private static readonly string[] VanillaFamilies =
    {
        "zombieArlene", "zombieBiker", "zombieBoe", "zombieBowler", "zombieBurnt", "zombieBusinessMan", "zombieChuck", "zombieDarlene",
        "zombieDemolition", "zombieFatCop", "zombieFatHawaiian", "zombieFemaleFat", "zombieFrostclaw", "zombieInmate", "zombieJanitor",
        "zombieJoe", "zombieLab", "zombieLumberjack", "zombieMaleHazmat", "zombieMarlene", "zombieMoe", "zombieMutated", "zombieNurse",
        "zombiePartyGirl", "zombiePlagueSpitter", "zombieRancher", "zombieScreamer", "zombieSkateboarder", "zombieSoldier", "zombieSpider",
        "zombieSteve", "zombieSteveCrawler", "zombieTomClark", "zombieUtilityWorker", "zombieWight", "zombieYo",
    };

    /// <summary>A class's family: "zombieJoeFeral" is a "zombieJoe".</summary>
    public static string Family(string cls)
    {
        foreach (string tier in new[] { "Feral", "Radiated", "Charged", "Infernal" })
        {
            if (cls.EndsWith(tier))
            {
                return cls.Substring(0, cls.Length - tier.Length);
            }
        }
        return cls;
    }

    // ------------------------------------------------------------------ champions and the Alpha

    private static readonly string[] FirstNames =
    {
        "Earl", "Darla", "Hank", "Marge", "Dale", "Rhonda", "Vern", "Loretta", "Butch", "Gus", "Wanda", "Clem", "Doris", "Rusty",
        "Bobbi", "Lyle", "Tammy", "Otis", "Jolene", "Cletus", "Peggy", "Wade", "Edna", "Floyd", "Nadine", "Boone", "Mavis", "Duane",
    };

    private static readonly Dictionary<ZedMutation, string> Epithets = new Dictionary<ZedMutation, string>
    {
        { ZedMutation.Sprinter, "the Sprinter" }, { ZedMutation.Spiked, "the Thorn" },
        { ZedMutation.Grabber, "the Grabber" }, { ZedMutation.Screecher, "the Screecher" }, { ZedMutation.Frostbitten, "the Frozen" },
        { ZedMutation.Smoldering, "the Smoldering" }, { ZedMutation.Leaper, "the Leaper" }, { ZedMutation.Regenerator, "the Undying" },
        { ZedMutation.Toxic, "the Toxic" }, { ZedMutation.Volatile, "the Volatile" }, { ZedMutation.Hulking, "the Hulk" },
        { ZedMutation.Stalker, "the Stalker" }, { ZedMutation.Brood, "the Brood Mother" }, { ZedMutation.Lurker, "the Lurker" },
        { ZedMutation.Possum, "the Possum" }, { ZedMutation.Snatcher, "the Snatcher" },
    };

    /// <summary>Makes it a champion: more mutations, none of them on a spot its gear, remnants or other mutations
    /// already take (`family` is its class's, see Used).</summary>
    public static void Champion(ZedProfile p, System.Random rng, int gs, string family)
    {
        p.Champion = true;
        int count = gs >= 150 ? 3 : 2;
        List<ZedMutation> allowed = Allowed(gs, p.Biome);
        allowed.RemoveAll(m => p.Mutations.Contains(m));
        while (p.Mutations.Count < count && allowed.Count > 0)
        {
            ZedMutation m = allowed[rng.Next(allowed.Count)];
            allowed.Remove(m);
            if (!Clashes(p, m) && !Crowded(p, m, family))
            {
                p.Mutations.Add(m);
            }
        }
        p.Size *= 1.15f;
        p.Name = Name(p, rng);
    }

    public static void Alpha(ZedProfile p, System.Random rng, int gs, string family)
    {
        p.Alpha = true;
        p.Champion = false;
        if (!p.Mutations.Contains(ZedMutation.Hulking))
        {
            p.Mutations.Insert(0, ZedMutation.Hulking);
        }
        // Not a Lurker: the Alpha leads the horde in, it doesn't run from being looked at
        p.Mutations.Remove(ZedMutation.Lurker);
        List<ZedMutation> allowed = Allowed(Math.Max(gs, 60), p.Biome);
        allowed.RemoveAll(m => p.Mutations.Contains(m) || m == ZedMutation.Lurker);
        while (p.Mutations.Count < 3 && allowed.Count > 0)
        {
            ZedMutation m = allowed[rng.Next(allowed.Count)];
            allowed.Remove(m);
            if (!Clashes(p, m) && !Crowded(p, m, family))
            {
                p.Mutations.Add(m);
            }
        }
        p.Size *= 1.2f;
        p.Name = FirstNames[rng.Next(FirstNames.Length)] + ", the Alpha";
    }

    /// <summary>Mutations whose behaviors fight each other: a Stalker freezes when watched, a Lurker runs.</summary>
    private static bool Clashes(ZedProfile p, ZedMutation m)
    {
        return (m == ZedMutation.Lurker && p.Has(ZedMutation.Stalker)) || (m == ZedMutation.Stalker && p.Has(ZedMutation.Lurker));
    }

    /// <summary>A mutation whose model would sit on a spot something on the zombie already takes.</summary>
    private static bool Crowded(ZedProfile p, ZedMutation m, string family)
    {
        return (ZedMutationInfo.All[m].Slots & Used(p, family)) != 0;
    }

    private static string Name(ZedProfile p, System.Random rng)
    {
        string first = FirstNames[rng.Next(FirstNames.Length)];
        List<ZedMutation> named = p.Mutations.FindAll(m => !ZedMutationInfo.All[m].Solo);
        if (named.Count == 0)
        {
            return first;
        }
        ZedMutation lead = named[rng.Next(named.Count)];
        return Epithets.TryGetValue(lead, out string epithet) ? first + " " + epithet : first;
    }

    /// <summary>One Alpha per Blood Moon for each group of players: the first zombie that spawns near a party (or a
    /// player alone) that hasn't had one tonight.</summary>
    private static bool AlphaDue(EntityAlive zombie)
    {
        EntityPlayer nearest = null;
        float best = float.MaxValue;
        foreach (EntityPlayer pl in zombie.world.Players.list)
        {
            float d = (pl.position - zombie.position).sqrMagnitude;
            if (d < best)
            {
                best = d;
                nearest = pl;
            }
        }
        if (nearest == null || best > 120f * 120f)
        {
            return false;
        }
        Party party = nearest.Party;
        int key = party != null && party.LeaderIndex >= 0 && party.LeaderIndex < party.MemberList.Count
            ? party.MemberList[party.LeaderIndex].entityId : nearest.entityId;
        return alphaParties.Add(key);
    }
}

/// <summary>Champion rooms: decided as the sleeper volume adds its zombie, when the volume is known.</summary>
[HarmonyLib.HarmonyPatch(typeof(SleeperVolume), nameof(SleeperVolume.AddEnemyToWorld))]
public class ZedChampionRoomPatch
{
    public static void Prefix(SleeperVolume __instance, EntityAlive zombie)
    {
        try
        {
            if (ZedStore.IsServer && zombie != null && ZedStore.IsZombie(zombie) && ZedRoll.ChampionRoom(__instance))
            {
                ZedStore.Promote(zombie);
            }
        }
        catch (Exception e)
        {
            Log.Exception(e);
        }
    }
}
