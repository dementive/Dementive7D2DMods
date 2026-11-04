using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Every zombie's profile. The server rolls one when a zombie spawns, keeps the ones for zombies the game saves in
/// its own save file (the game doesn't save buffs or anything else a mod puts on a zombie), and answers players who
/// ask for one when the zombie appears on their screen. Every game then applies it: the server its gameplay parts,
/// each player its looks.
/// </summary>
public static class ZedStore
{
    private class Entry
    {
        public ZedProfile Profile;
        public string Class = "";
        public bool Saved;
        public bool Loaded;
        public ulong LastSeen;
        /// <summary>Server: what a Snatcher is carrying (saved with it, never sent).</summary>
        public ItemStack Loot;
    }

    private const float SaveInterval = 60f;
    private const ulong ForgetAfter = 24000UL * 30;

    private static readonly Dictionary<int, Entry> entries = new Dictionary<int, Entry>();
    private static readonly HashSet<int> requested = new HashSet<int>();
    private static readonly HashSet<int> none = new HashSet<int>();
    private static readonly HashSet<int> changed = new HashSet<int>();
    private static readonly ZedSaveFile file = new ZedSaveFile("zombies.dat");
    private static readonly System.Random rng = new System.Random();
    private static bool dirty;
    private static float saveTimer;

    private static readonly FastTags<TagGroup.Global> ZombieTag = FastTags<TagGroup.Global>.Parse("zombie");
    private static readonly FastTags<TagGroup.Global> AnimalTag = FastTags<TagGroup.Global>.Parse("zombieAnimal");
    private static readonly FastTags<TagGroup.Global> BossTag = FastTags<TagGroup.Global>.Parse("boss");

    public static bool IsServer => SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer;
    public static bool DrawsLooks => !GameManager.IsDedicatedServer;

    public static bool IsZombie(Entity e) => e is EntityEnemy && e.HasAnyTags(ZombieTag);
    public static bool IsHumanoid(Entity e) => e is EntityHuman && !e.HasAnyTags(AnimalTag);
    public static bool IsBoss(Entity e) => e.HasAnyTags(BossTag);

    /// <summary>Server: what a Snatcher carries.</summary>
    public static ItemStack Loot(int entityId)
    {
        return entries.TryGetValue(entityId, out Entry e) ? e.Loot : null;
    }

    public static void SetLoot(int entityId, ItemStack stack)
    {
        if (entries.TryGetValue(entityId, out Entry e))
        {
            e.Loot = stack;
            dirty = true;
        }
    }

    /// <summary>The zombie's profile on this game, or null if it isn't known (yet).</summary>
    public static ZedProfile Get(int entityId)
    {
        return entries.TryGetValue(entityId, out Entry e) ? e.Profile : null;
    }

    // ------------------------------------------------------------------ spawning

    /// <summary>A zombie was just set up (before it enters the world). On the server: roll or restore its profile and
    /// apply it. On a player's game: apply it, asking the server first if needed.</summary>
    public static void Spawned(EntityAlive zombie)
    {
        if (IsServer && !zombie.isEntityRemote)
        {
            EnsureLoaded();
            bool fresh = !entries.TryGetValue(zombie.entityId, out Entry entry);
            if (!fresh && entry.Class.Length > 0 && entry.Class != zombie.EntityClass.entityClassName)
            {
                // A saved profile for an id the world has since reused (after a crash): not this zombie's
                fresh = true;
            }
            if (fresh)
            {
                ZedProfile p = ZedProfile.Roll(zombie, rng);
                ZedRoll.Apply(zombie, p, rng);
                if (p.Has(ZedMutation.Hulking))
                {
                    p.Size *= 1.15f;
                    p.Body = ZedBody.Bulky;
                }
                else if (p.Has(ZedMutation.Bloater) && p.Body != ZedBody.Bulky)
                {
                    p.Body = ZedBody.Bloated;
                }
                else if (p.Has(ZedMutation.Lurker))
                {
                    p.Body = ZedBody.Hunched;
                }
                ZedProfile.RollInjury(zombie, p, rng);
                entry = new Entry { Profile = p, Class = zombie.EntityClass.entityClassName };
                entries[zombie.entityId] = entry;
            }
            entry.Loaded = true;
            entry.LastSeen = zombie.world.worldTime;
            dirty = true;
            ApplyServer(zombie, entry.Profile, fresh);
            Apply(zombie, entry.Profile);
            return;
        }
        if (entries.TryGetValue(zombie.entityId, out Entry known))
        {
            Apply(zombie, known.Profile);
        }
        else if (!none.Contains(zombie.entityId) && requested.Add(zombie.entityId))
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageZedRequest>().Setup(zombie.entityId));
        }
    }

    /// <summary>Server: the parts only the server runs. Size travels to players in the zombie's spawn data, the
    /// rest (speed, temperament) is the AI's.</summary>
    private static void ApplyServer(EntityAlive zombie, ZedProfile p, bool fresh)
    {
        // Only a zombie nothing has sized yet: one the game reloads from its save already has its size (ours), and
        // spawns that set their own (game events, Twitch) keep theirs
        bool unsized = zombie.OverrideSize <= 0f || Math.Abs(zombie.OverrideSize - 1f) < 0.001f;
        if (unsized && Math.Abs(p.Size - 1f) > 0.001f)
        {
            zombie.OverrideSize = zombie.EntityClass.SizeScale * p.Size;
            zombie.SetScale(zombie.OverrideSize);
        }
        ZedTemperament.Apply(zombie, p);
        if (zombie.Buffs != null)
        {
            foreach (ZedMutation m in p.Mutations)
            {
                zombie.Buffs.AddBuff(ZedMutationInfo.All[m].Buff);
            }
            if (p.Champion)
            {
                zombie.Buffs.AddBuff("buffZedChampion");
            }
            if (p.Alpha)
            {
                zombie.Buffs.AddBuff("buffZedAlpha");
            }
            foreach (ZedGearPiece g in p.Gear)
            {
                string buff = GearBuff(g.Kind);
                if (!g.Broken && buff != null)
                {
                    zombie.Buffs.AddBuff(buff);
                }
            }
            foreach (ZedRemnant r in p.Remnants)
            {
                if (ZedRemnantInfo.All[r].Buff != null)
                {
                    zombie.Buffs.AddBuff(ZedRemnantInfo.All[r].Buff);
                }
            }
        }
        if (zombie.aiManager != null && ZedSettings.Crowd)
        {
            // The game's own spread for zombies that attack together: they relocate around the target
            zombie.aiManager.groupCircle = 1f;
        }
        ZedTasks.Add(zombie, p, p.Mutations);
        ZedBrain.Attach(zombie, p, fresh);
        ZedPossum.Spawned(zombie, p, fresh);
    }

    /// <summary>What wearing a piece of gear costs (its buff), if anything.</summary>
    private static string GearBuff(ZedGearKind kind)
    {
        ZedGearInfo info = ZedGearInfo.All[kind];
        if (info.IsShield)
        {
            return "buffZedShield";
        }
        if (kind == ZedGearKind.ScrapArmor)
        {
            return "buffZedHeavyGear";
        }
        return info.Speed < 1f ? "buffZedGear" : null;
    }

    /// <summary>Server: a sleeper volume is adding a zombie from a POI's final room that the room made its champion
    /// (before the zombie enters the world, so its new size travels in its spawn data).</summary>
    public static void Promote(EntityAlive zombie)
    {
        ZedProfile p = Get(zombie.entityId);
        if (p == null || p.Champion || p.Alpha || !p.Humanoid || IsBoss(zombie) || p.Has(ZedMutation.Snatcher))
        {
            return;
        }
        List<ZedMutation> before = new List<ZedMutation>(p.Mutations);
        ZedRoll.Champion(p, rng, Math.Max(50, ZedRoll.Gamestage(zombie)), ZedRoll.Family(zombie.EntityClass.entityClassName));
        zombie.OverrideSize = (zombie.OverrideSize > 0f ? zombie.OverrideSize : zombie.EntityClass.SizeScale) * 1.15f;
        zombie.SetScale(zombie.OverrideSize);
        List<ZedMutation> added = p.Mutations.FindAll(m => !before.Contains(m));
        foreach (ZedMutation m in added)
        {
            zombie.Buffs?.AddBuff(ZedMutationInfo.All[m].Buff);
        }
        zombie.Buffs?.AddBuff("buffZedChampion");
        ZedTasks.Add(zombie, p, added);
        ZedBrain.Of(zombie)?.HealSoon();
        dirty = true;
        if (DrawsLooks)
        {
            ZedModels.Refresh(zombie, p);
            ZedLook.Restyle(zombie, p);
        }
    }

    private static readonly Dictionary<int, HashSet<ZedGearKind>> gearOff = new Dictionary<int, HashSet<ZedGearKind>>();

    /// <summary>Server: gear broke. What a whole piece of gear cost the zombie (a helmet's dulled senses, armor's
    /// weight) ends when the last of its parts is off.</summary>
    public static void GearOff(EntityAlive zombie, ZedProfile p)
    {
        if (!gearOff.TryGetValue(zombie.entityId, out HashSet<ZedGearKind> done))
        {
            done = new HashSet<ZedGearKind>();
            gearOff[zombie.entityId] = done;
        }
        HashSet<string> still = new HashSet<string>();
        foreach (ZedGearKind kind in ZedGearInfo.All.Keys)
        {
            List<ZedGearPiece> pieces = p.Gear.FindAll(g => g.Kind == kind);
            if (pieces.Count == 0)
            {
                continue;
            }
            bool allOff = pieces.TrueForAll(g => g.Broken);
            if (!allOff)
            {
                string buff = GearBuff(kind);
                if (buff != null)
                {
                    still.Add(buff);
                }
            }
            else if (done.Add(kind))
            {
                ZedGearInfo info = ZedGearInfo.All[kind];
                ZedTemperament.Rescale(zombie, 1f / info.Sight, 1f / info.Hearing);
            }
        }
        foreach (string buff in new[] { "buffZedHeavyGear", "buffZedGear", "buffZedShield" })
        {
            if (!still.Contains(buff))
            {
                zombie.Buffs?.RemoveBuff(buff);
            }
        }
    }

    /// <summary>Server: something about a zombie changed after it spawned (gear knocked off, its tank, a Stalker
    /// seen): send its whole profile again to the players near it, on the next update. Not at once: from inside a hit,
    /// the profile would reach the other players before the game sends them that hit, and they'd play the hit against
    /// the profile it already changed.</summary>
    public static void Changed(EntityAlive zombie)
    {
        if (zombie != null && IsServer)
        {
            changed.Add(zombie.entityId);
        }
    }

    private static void SendChanged()
    {
        World world = GameManager.Instance.World;
        foreach (int id in changed)
        {
            if (world?.GetEntity(id) is EntityAlive zombie)
            {
                SendNow(zombie);
            }
        }
        changed.Clear();
    }

    private static void SendNow(EntityAlive zombie)
    {
        ZedProfile p = Get(zombie.entityId);
        if (p == null)
        {
            return;
        }
        dirty = true;
        if (DrawsLooks)
        {
            ZedModels.Refresh(zombie, p);
        }
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
            NetPackageManager.GetPackage<NetPackageZedProfile>().Setup(zombie.entityId, p), false, -1, -1, -1, zombie.position, 192);
    }

    /// <summary>Every game: the body (bones and walk style, which the hit boxes follow, so the server needs them too)
    /// and, where something is drawn, the looks.</summary>
    private static void Apply(EntityAlive zombie, ZedProfile p)
    {
        if (zombie == null || zombie.emodel == null)
        {
            return;
        }
        if (p.Walk >= 0 && zombie.GetWalkType() != p.Walk && !zombie.IsWalkTypeACrawl())
        {
            zombie.SetWalkType(p.Walk);
        }
        ZedBodyRig.Attach(zombie, p);
        if (DrawsLooks)
        {
            ZedLook.Attach(zombie, p);
            ZedModels.Attach(zombie, p);
        }
    }

    // ------------------------------------------------------------------ network

    /// <summary>Server: a player asks for a zombie's profile.</summary>
    public static void Request(int entityId, ClientInfo client)
    {
        client?.SendPackage(NetPackageManager.GetPackage<NetPackageZedProfile>().Setup(entityId, Get(entityId)));
    }

    /// <summary>Player: the server's answer.</summary>
    public static void Receive(int entityId, ZedProfile profile)
    {
        requested.Remove(entityId);
        if (profile == null)
        {
            none.Add(entityId);
            return;
        }
        bool update = entries.ContainsKey(entityId);
        entries[entityId] = new Entry { Profile = profile, Loaded = true };
        if (GameManager.Instance.World?.GetEntity(entityId) is EntityAlive zombie)
        {
            Apply(zombie, profile);
            if (update)
            {
                ZedModels.Refresh(zombie, profile);
            }
            ZedPossum.Received(zombie, profile);
        }
    }

    // ------------------------------------------------------------------ lifetime

    /// <summary>A zombie left this game's world. The server keeps the profile of a zombie the game saved with its chunk
    /// (unloaded, not despawned or killed) for when it comes back.</summary>
    public static void Unloaded(Entity e, bool chunkUnloaded)
    {
        requested.Remove(e.entityId);
        none.Remove(e.entityId);
        ZedRoll.Forget(e.entityId);
        ZedPossum.Forget(e.entityId);
        gearOff.Remove(e.entityId);
        if (!entries.TryGetValue(e.entityId, out Entry entry))
        {
            return;
        }
        // Whether the game saves a zombie can change after it spawns (its spawner sets that), so ask now
        if (IsServer && chunkUnloaded && !e.IsDead() && e.IsSavedToFile())
        {
            entry.Saved = true;
            entry.Loaded = false;
            entry.LastSeen = e.world?.worldTime ?? entry.LastSeen;
            dirty = true;
            return;
        }
        entries.Remove(e.entityId);
        if (IsServer && entry.Saved)
        {
            dirty = true;
        }
    }

    public static void Update()
    {
        if (!IsServer || GameManager.Instance.World == null)
        {
            return;
        }
        if (changed.Count > 0)
        {
            SendChanged();
        }
        saveTimer += Time.deltaTime;
        if (dirty && saveTimer >= SaveInterval)
        {
            Save();
        }
    }

    public static void Shutdown()
    {
        if (IsServer && dirty)
        {
            Save();
        }
        file.Reset();
        entries.Clear();
        requested.Clear();
        none.Clear();
        changed.Clear();
        ZedTemperament.Clear();
        ZedRoll.Clear();
        gearOff.Clear();
        ZedBrain.Clear();
    }

    private static void EnsureLoaded()
    {
        if (!file.NeedsLoad())
        {
            return;
        }
        entries.Clear();
        file.Load(r =>
        {
            int count = r.ReadInt32();
            for (int i = 0; i < count; i++)
            {
                int id = r.ReadInt32();
                string cls = r.ReadString();
                ulong seen = r.ReadUInt64();
                ZedProfile p = ZedProfile.Read(r);
                ItemStack loot = p.Carrying && r.ReadBoolean() ? new ItemStack().Read(r) : null;
                entries[id] = new Entry { Profile = p, Class = cls, Saved = true, LastSeen = seen, Loot = loot };
            }
        });
    }

    private static void Save()
    {
        saveTimer = 0f;
        dirty = false;
        if (file.NeedsLoad())
        {
            return;
        }
        World world = GameManager.Instance.World;
        ulong now = world?.worldTime ?? 0;
        List<KeyValuePair<int, Entry>> keep = new List<KeyValuePair<int, Entry>>();
        List<int> forget = new List<int>();
        foreach (KeyValuePair<int, Entry> kv in entries)
        {
            if (kv.Value.Loaded)
            {
                Entity e = world?.GetEntity(kv.Key);
                kv.Value.Saved = e != null && !e.IsDead() && e.IsSavedToFile();
            }
            if (!kv.Value.Saved)
            {
                continue;
            }
            if (!kv.Value.Loaded && now > kv.Value.LastSeen + ForgetAfter)
            {
                forget.Add(kv.Key);
                continue;
            }
            keep.Add(kv);
        }
        foreach (int id in forget)
        {
            entries.Remove(id);
        }
        file.Save(w =>
        {
            w.Write(keep.Count);
            foreach (KeyValuePair<int, Entry> kv in keep)
            {
                w.Write(kv.Key);
                w.Write(kv.Value.Class ?? "");
                w.Write(kv.Value.Loaded ? now : kv.Value.LastSeen);
                kv.Value.Profile.Write(w);
                if (kv.Value.Profile.Carrying)
                {
                    w.Write(kv.Value.Loot != null);
                    kv.Value.Loot?.Write(w);
                }
            }
        });
    }

    /// <summary>For the console: how many profiles this game knows, and how many of them are saved.</summary>
    public static string Stats()
    {
        int saved = 0, loaded = 0;
        foreach (Entry e in entries.Values)
        {
            saved += e.Saved ? 1 : 0;
            loaded += e.Loaded ? 1 : 0;
        }
        return $"{entries.Count} profiles ({loaded} in the world, {saved} saved), {requested.Count} waiting for the server";
    }
}
