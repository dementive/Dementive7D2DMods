using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The human NPCs other mods add, for the NPC quests (Bandit Hideout, Rescue, Safehouse and the outposts' bandit
/// raids). QuestsExpanded needs no NPC mod: those quests are only offered when this finds NPCs to use.
/// - Hostile: the entity's C# class derives from vanilla EntityBandit (SCore's EntityNPCBandit does), or its faction is
///   "bandits".
/// - Followers: the class derives from vanilla EntityNPC and is made with SCore (it implements IEntityAliveSDX), since
///   only those can follow a player; not traders, bandits or animals.
/// Templates and test entities are skipped. Hostile NPCs are ranked by their weapon and NPC Core's difficulty tags,
/// so low tiers get the weaker ones.
/// </summary>
public static class NpcCatalogDEM
{
    private static List<int> hostile;
    private static List<int> followers;

    /// <summary>Hostile NPC classes, weakest first.</summary>
    public static List<int> Hostile
    {
        get
        {
            Build();
            return hostile;
        }
    }

    /// <summary>Friendly NPC classes that can follow a player.</summary>
    public static List<int> Followers
    {
        get
        {
            Build();
            return followers;
        }
    }

    public static bool HasHostile => Hostile.Count > 0;

    public static bool HasFollowers => Followers.Count > 0 && NpcFollowDEM.Available;

    private static void Build()
    {
        if (hostile != null)
            return;
        hostile = new List<int>();
        followers = new List<int>();
        if (EntityClass.list == null)
            return;

        var threat = new Dictionary<int, int>();
        foreach (KeyValuePair<int, EntityClass> entry in EntityClass.list.Dict)
        {
            EntityClass entityClass = entry.Value;
            Type type = entityClass.classname;
            string name = entityClass.entityClassName ?? "";
            if (type == null || name.IndexOf("template", StringComparison.OrdinalIgnoreCase) >= 0
                || name.IndexOf("test", StringComparison.OrdinalIgnoreCase) >= 0)
                continue;

            string faction = Property(entityClass, "Faction").ToLowerInvariant();
            string tags = "," + Property(entityClass, "Tags").ToLowerInvariant().Replace(" ", "") + ",";
            bool animal = entityClass.bIsAnimalEntity || tags.Contains(",animal,");
            if (typeof(EntityBandit).IsAssignableFrom(type)
                || (faction == "bandits" && typeof(EntityAlive).IsAssignableFrom(type) && !animal))
            {
                hostile.Add(entry.Key);
                threat[entry.Key] = Threat(entityClass, tags);
            }
            else if (typeof(EntityNPC).IsAssignableFrom(type) && type.GetInterface("IEntityAliveSDX") != null
                && faction != "trader" && faction != "bandits" && !animal && !tags.Contains(",trader,")
                && Property(entityClass, "Hirable").ToLowerInvariant() != "false")
            {
                followers.Add(entry.Key);
            }
        }
        hostile.Sort((a, b) => threat[a].CompareTo(threat[b]));
        Log.Out($"QuestsExpanded: found {hostile.Count} hostile and {followers.Count} friendly NPC types for the NPC quests"
            + (NpcFollowDEM.Available ? "" : " (SCore isn't loaded, so no NPC can follow a player)"));
    }

    private static string Property(EntityClass entityClass, string name)
    {
        return entityClass.Properties != null && entityClass.Properties.Values.ContainsKey(name)
            ? entityClass.Properties.Values[name] ?? ""
            : "";
    }

    /// <summary>
    /// How dangerous a hostile NPC is: its weapon (melee, pipe guns, guns, automatic and heavy weapons) plus NPC Core's
    /// difficulty tags (DRLow, DRMid, DRHigh).
    /// </summary>
    private static int Threat(EntityClass entityClass, string tags)
    {
        string weapon = Property(entityClass, "HandItem").ToLowerInvariant();
        int score = 1;
        if (weapon.Contains("rocket") || weapon.Contains("m60") || weapon.Contains("srifle") || weapon.Contains("sniper"))
            score = 5;
        else if (weapon.Contains("ak47") || weapon.Contains("smg") || weapon.Contains("trifle") || weapon.Contains("hrifle")
            || weapon.Contains("ashotgun") || weapon.Contains("mg"))
            score = 4;
        else if (weapon.Contains("pipe") && weapon.StartsWith("gun"))
            score = 2;
        else if (weapon.StartsWith("gun") || weapon.Contains("bow"))
            score = 3;

        if (tags.Contains(",drhigh,"))
            score += 2;
        else if (tags.Contains(",drmid,"))
            score += 1;
        return score;
    }

    /// <summary>
    /// A hostile NPC class for the tier: low tiers only pick from the weaker ones (the weakest 40% at tier 2, 60% at
    /// tier 3, 80% at tier 4), tiers 5-6 from all of them. -1 if there are none.
    /// </summary>
    public static int PickHostile(int tier, GameRandom random)
    {
        List<int> list = Hostile;
        if (list.Count == 0)
            return -1;
        float share = tier <= 2 ? 0.4f : tier == 3 ? 0.6f : tier == 4 ? 0.8f : 1f;
        int count = Mathf.Clamp(Mathf.CeilToInt(list.Count * share), 1, list.Count);
        return list[random.RandomRange(count)];
    }

    /// <summary>The strongest hostile NPC class the tier allows, for a bandit leader.</summary>
    public static int PickLeader(int tier, GameRandom random)
    {
        List<int> list = Hostile;
        if (list.Count == 0)
            return -1;
        float share = tier <= 2 ? 0.4f : tier == 3 ? 0.6f : tier == 4 ? 0.8f : 1f;
        int count = Mathf.Clamp(Mathf.CeilToInt(list.Count * share), 1, list.Count);
        // One of the top few within the tier's range
        int pick = count - 1 - random.RandomRange(Mathf.Min(3, count));
        return list[pick];
    }

    public static int PickFollower(GameRandom random)
    {
        List<int> list = Followers;
        return list.Count == 0 ? -1 : list[random.RandomRange(list.Count)];
    }
}
