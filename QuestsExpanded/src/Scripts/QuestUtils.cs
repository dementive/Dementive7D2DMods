using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;


public static class QuestUtils
{
    /// <summary>
    /// Gets a POI for a quest that targets specific prefabs, e.g. "any cabin". Every instance of the named
    /// prefabs in the world is a candidate if it passes the same checks as vanilla quest POIs. Like vanilla trader
    /// quests, it picks a random candidate from the closest distance band (within 500m, then 1500m, then anywhere).
    /// </summary>
    /// <param name="questGiver"></param>
    /// <param name="prefabNames">Prefab names (file names without extension)</param>
    /// <param name="questTag"></param>
    /// <param name="usedPoiLocations"></param>
    /// <param name="entityIdForQuests"></param>
    /// <param name="biomeFilterType"></param>
    /// <param name="biomeFilter"></param>
    /// <returns></returns>
    public static PrefabInstance GetNamedPOINearEntity(
        Entity questGiver,
        ICollection<string> prefabNames,
        FastTags<TagGroup.Global> questTag,
        List<Vector2> usedPoiLocations = null,
        int entityIdForQuests = -1,
        BiomeFilterTypes biomeFilterType = BiomeFilterTypes.AnyBiome,
        string biomeFilter = "")
    {
        var bands = new[] { new List<PrefabInstance>(), new List<PrefabInstance>(), new List<PrefabInstance>() };
        Vector2 questGiverPosition = new Vector2(questGiver.position.x, questGiver.position.z);

        foreach (PrefabInstance prefab in GameManager.Instance.GetDynamicPrefabDecorator().allPrefabs)
        {
            if (!prefabNames.Contains(prefab.location.Name))
                continue;

            if (!ValidPrefabForQuest(
                questGiver,
                prefab,
                questTag,
                FastTags<TagGroup.Poi>.none,
                FastTags<TagGroup.Poi>.none,
                usedPoiLocations,
                entityIdForQuests,
                biomeFilterType,
                biomeFilter))
            {
                continue;
            }

            float distance = Vector2.Distance(questGiverPosition, prefab.GetCenterXZ());
            bands[GetTraderPrefabListTier(distance)].Add(prefab);
        }

        foreach (List<PrefabInstance> band in bands)
        {
            if (band.Count > 0)
                return band[GameManager.Instance.World.GetGameRandom().RandomRange(band.Count)];
        }

        if (LoggingEnabled)
        {
            Log.Out($"Quest {questTag}: No usable POI named {string.Join(",", prefabNames)}");
        }
        return null;
    }

    /// <summary>
    /// Whether logging is enabled. Defaults to true if the debug menu is enabled.
    /// Can be set to temporarily override in code for testing, e.g. on the server.
    /// </summary>
    public static bool LoggingEnabled
    {
        get => _loggingEnabled ?? GamePrefs.GetBool(EnumGamePrefs.DebugMenuEnabled);
        set => _loggingEnabled = value;
    }
    private static bool? _loggingEnabled;

    /// <summary>
    /// Gets a random POI near a trader. This is meant to be a replacement for
    /// <see cref="DynamicPrefabDecorator.GetRandomPOINearTrader"/>,
    /// except it also handles search distance and POI tags used to include or exclude the prefab.
    /// </summary>
    /// <param name="trader"></param>
    /// <param name="questTag"></param>
    /// <param name="difficulty"></param>
    /// <param name="usedPoiLocations"></param>
    /// <param name="entityIdForQuests"></param>
    /// <param name="biomeFilterType"></param>
    /// <param name="biomeFilter"></param>
    /// <param name="includeTags"></param>
    /// <param name="excludeTags"></param>
    /// <returns></returns>
    public static PrefabInstance GetRandomPOINearTrader(
        EntityTrader trader,
        FastTags<TagGroup.Global> questTag,
        byte difficulty,
        FastTags<TagGroup.Poi> includeTags,
        FastTags<TagGroup.Poi> excludeTags,
        float minSearchDistance,
        float maxSearchDistance,
        List<Vector2> usedPoiLocations = null,
        int entityIdForQuests = -1,
        BiomeFilterTypes biomeFilterType = BiomeFilterTypes.AnyBiome,
        string biomeFilter = "")
    {
        World world = GameManager.Instance.World;

        int minDistanceTier = minSearchDistance < 0 ? 0 : GetTraderPrefabListTier(minSearchDistance);
        int maxDistanceTier = maxSearchDistance < 0 ? 2 : GetTraderPrefabListTier(maxSearchDistance);

        for (int distanceTier = minDistanceTier; distanceTier <= maxDistanceTier; distanceTier++)
        {
            List<PrefabInstance> prefabsForTrader = QuestEventManager.Current.GetPrefabsForTrader(
                trader.traderArea,
                difficulty,
                distanceTier,
                world.GetGameRandom());

            if (prefabsForTrader != null)
            {
                // GetPrefabsForTrader shuffles the prefabs before returning them, so we can just
                // iterate through the list and still send players to "random" POIs
                for (int j = 0; j < prefabsForTrader.Count; j++)
                {
                    PrefabInstance prefabInstance = prefabsForTrader[j];
                    if (ValidPrefabForQuest(
                        trader,
                        prefabInstance,
                        questTag,
                        includeTags,
                        excludeTags,
                        usedPoiLocations,
                        entityIdForQuests,
                        biomeFilterType,
                        biomeFilter,
                        minSearchDistance,
                        maxSearchDistance))
                    {
                        return prefabInstance;
                    }
                }
            }
        }

        return null;
    }

    /// <summary>
    /// Gets a random POI near an entity's position. This is meant to be a replacement for
    /// <see cref="DynamicPrefabDecorator.GetRandomPOINearWorldPos"/>
    /// except it accepts the quest giver instead of the world position, and it also handles
    /// POI tags used to include or exclude the prefab.
    /// </summary>
    /// <param name="entity"></param>
    /// <param name="questTag"></param>
    /// <param name="difficulty"></param>
    /// <param name="includeTags"></param>
    /// <param name="excludeTags"></param>
    /// <param name="minSearchDistance"></param>
    /// <param name="maxSearchDistance"></param>
    /// <param name="usedPOILocations"></param>
    /// <param name="entityIDforQuests"></param>
    /// <param name="biomeFilterType"></param>
    /// <param name="biomeFilter"></param>
    /// <returns></returns>
    public static PrefabInstance GetRandomPOINearEntityPos(
        Entity entity,
        FastTags<TagGroup.Global> questTag,
        byte difficulty,
        FastTags<TagGroup.Poi> includeTags,
        FastTags<TagGroup.Poi> excludeTags,
        float minSearchDistance,
        float maxSearchDistance,
        List<Vector2> usedPOILocations = null,
        int entityIDforQuests = -1,
        BiomeFilterTypes biomeFilterType = BiomeFilterTypes.AnyBiome,
        string biomeFilter = "")
    {
        List<PrefabInstance> prefabsByDifficultyTier = QuestEventManager.Current.GetPrefabsByDifficultyTier(difficulty);
        if (prefabsByDifficultyTier == null)
        {
            return null;
        }

        World world = GameManager.Instance.World;

        // GetPrefabsByDifficultyTier does NOT shuffle the prefabs before returning them, so try
        // 50 times to get a valid prefab from a random position in the list
        for (int i = 0; i < 50; i++)
        {
            int index = world.GetGameRandom().RandomRange(prefabsByDifficultyTier.Count);
            PrefabInstance prefabInstance = prefabsByDifficultyTier[index];

            if (!ValidPrefabForQuest(
                entity,
                prefabInstance,
                questTag,
                includeTags,
                excludeTags,
                usedPOILocations,
                entityIDforQuests,
                biomeFilterType,
                biomeFilter,
                minSearchDistance,
                maxSearchDistance))
            {
                continue;
            }

            return prefabInstance;
        }
        return null;
    }

    /// <summary>
    /// The trader prefab list has three distance tiers per trader area:
    /// 0 is <= 500, 1 is <= 1500, and 2 is everything else.
    /// </summary>
    /// <param name="distance"></param>
    /// <returns></returns>
    public static int GetTraderPrefabListTier(float distance)
    {
        if (distance <= 500f)
            return 0;

        if (distance <= 1500f)
            return 1;

        return 2;
    }

    /// <summary>
    /// Returns true if the prefab is valid for a quest. Uses all utility validation methods.
    /// </summary>
    /// <param name="questGiver"></param>
    /// <param name="prefab"></param>
    /// <param name="questTag"></param>
    /// <param name="includeTags"></param>
    /// <param name="excludeTags"></param>
    /// <param name="usedPoiLocations"></param>
    /// <param name="entityIdForQuests"></param>
    /// <param name="biomeFilterType"></param>
    /// <param name="biomeFilter"></param>
    /// <param name="minSearchDistance"></param>
    /// <param name="maxSearchDistance"></param>
    /// <returns></returns>
    public static bool ValidPrefabForQuest(
        Entity questGiver,
        PrefabInstance prefab,
        FastTags<TagGroup.Global> questTag,
        FastTags<TagGroup.Poi> includeTags,
        FastTags<TagGroup.Poi> excludeTags,
        List<Vector2> usedPoiLocations = null,
        int entityIdForQuests = -1,
        BiomeFilterTypes biomeFilterType = BiomeFilterTypes.AnyBiome,
        string biomeFilter = "",
        float minSearchDistance = -1,
        float maxSearchDistance = -1)
    {
        // Same checks vanilla's DynamicPrefabDecorator.ValidPrefabForQuest uses
        if (!prefab.prefab.SleeperVolumeList.AnyUsedEntry)
        {
            if (LoggingEnabled)
            {
                Log.Out($"Quest {questTag}: Prefab {prefab.name} has no sleeper volumes");
            }
            return false;
        }

        // The POI must support every quest tag (fetch, clear, infested, ...). Without this, fetch quests could
        // pick a POI with no fetch container markers and the satchel would spawn in another POI kilometers away.
        if (!prefab.prefab.GetQuestTag(questTag))
        {
            if (LoggingEnabled)
            {
                Log.Out($"Quest {questTag}: Prefab {prefab.name} does not have quest tag {questTag}");
            }
            return false;
        }

        Vector2 poiLocation = new Vector2(prefab.boundingBoxPosition.x, prefab.boundingBoxPosition.z);

        if (usedPoiLocations != null && usedPoiLocations.Contains(poiLocation))
        {
            if (LoggingEnabled)
            {
                Log.Out($"Quest {questTag}: Prefab {prefab.name} has already been used");
            }
            return false;
        }

        QuestEventManager.POILockoutReasonTypes lockoutReason = QuestEventManager.Current.CheckForPOILockouts(entityIdForQuests, poiLocation, out var num);

        if (lockoutReason != QuestEventManager.POILockoutReasonTypes.None)
        {
            if (LoggingEnabled)
            {
                Log.Out($"Quest {questTag}: Prefab {prefab.name} is locked out: {lockoutReason}");
            }
            return false;
        }

        if (!MeetsBiomeRequirements(poiLocation, questGiver, biomeFilterType, biomeFilter))
        {
            if (LoggingEnabled)
            {
                Log.Out($"Quest {questTag}: Prefab {prefab.name} does not meet biome requirements: type={biomeFilterType}, filter={biomeFilter}");
            }
            return false;
        }

        if (!MeetsTagRequirements(prefab, includeTags, excludeTags))
        {
            if (LoggingEnabled)
            {
                var includeTagsText = includeTags.IsEmpty ? string.Empty : $"must include {includeTags}; ";
                var excludeTagsText = excludeTags.IsEmpty ? string.Empty : $"must exclude {excludeTags}; ";
                Log.Out($"Quest {questTag}: Prefab {prefab.name} fails tag requirements: {includeTagsText}{excludeTagsText}prefab tags are{prefab.prefab.Tags}");
            }
            return false;
        }

        if (!MeetsDistanceRequirements(prefab, questGiver, minSearchDistance, maxSearchDistance))
        {
            if (LoggingEnabled)
            {
                var minSearchText = minSearchDistance > 0 ? $" minimum distance {minSearchDistance} and" : string.Empty;
                Log.Out($"Quest {questTag}: Prefab {prefab.name} is not within{minSearchText} maximum distance {maxSearchDistance}");
            }
            return false;
        }

        return true;
    }

    /// <summary>
    /// If min and/or max search distance is provided, returns true if the prefab is within that
    /// search distance from the quest giver.
    /// </summary>
    /// <param name="questGiver"></param>
    /// <param name="prefab"></param>
    /// <param name="minSearchDistance"></param>
    /// <param name="maxSearchDistance"></param>
    /// <returns></returns>
    public static bool MeetsDistanceRequirements(
        PrefabInstance prefab,
        Entity questGiver,
        float minSearchDistance,
        float maxSearchDistance)
    {
        if (minSearchDistance < 0 && maxSearchDistance < 0)
            return true;

        Vector2 worldPos = new Vector2(questGiver.position.x, questGiver.position.z);

        Vector2 prefabCenter = prefab.GetCenterXZ();

        // Work with the square of the distance to avoid taking square roots
        float sqrDistance = (worldPos - prefabCenter).sqrMagnitude;

        if (minSearchDistance >= 0 &&
            sqrDistance < (minSearchDistance * minSearchDistance))
        {
            return false;
        }

        if (maxSearchDistance >= 0 &&
            sqrDistance > (maxSearchDistance * maxSearchDistance))
        {
            return false;
        }

        return true;
    }

    /// <summary>
    /// Returns true if the POI at the specified location meets the biome filter requirements.
    /// </summary>
    /// <param name="poiLocation"></param>
    /// <param name="questGiver"></param>
    /// <param name="biomeFilterType"></param>
    /// <param name="biomeFilter"></param>
    /// <returns></returns>
    public static bool MeetsBiomeRequirements(
        Vector2 poiLocation,
        Entity questGiver,
        BiomeFilterTypes biomeFilterType,
        string biomeFilter)
    {
        if (biomeFilterType == BiomeFilterTypes.AnyBiome)
        {
            return true;
        }

        IBiomeProvider biomeProvider = GameManager.Instance.World.ChunkCache.ChunkProvider.GetBiomeProvider();

        BiomeDefinition poiBiome = biomeProvider.GetBiomeAt((int)poiLocation.x, (int)poiLocation.y);

        if (biomeFilterType == BiomeFilterTypes.OnlyBiome && poiBiome.m_sBiomeName != biomeFilter)
        {
            return false;
        }
        else if (biomeFilterType == BiomeFilterTypes.ExcludeBiome)
        {
            string[] biomes = biomeFilter.Split(new char[] { ',' });

            bool inBiome = false;

            for (int i = 0; i < biomes.Length; i++)
            {
                if (poiBiome.m_sBiomeName == biomes[i])
                {
                    inBiome = true;
                    break;
                }
            }

            if (inBiome)
            {
                return false;
            }
        }
        else if (biomeFilterType == BiomeFilterTypes.SameBiome && questGiver != null)
        {
            var questGiverBiome = biomeProvider.GetBiomeAt(
                (int)questGiver.position.x,
                (int)questGiver.position.z);

            if (poiBiome != questGiverBiome && biomeFilter != "" && poiBiome.m_sBiomeName != biomeFilter)
            {
                return false;
            }
        }

        return true;
    }

    /// <summary>
    /// Returns true if the POI meets the POI tag requirements.
    /// If include tags are provided, it must have one or more of those tags;
    /// if exclude tags are provided, it cannot have any of those tags.
    /// </summary>
    /// <param name="prefabInstance"></param>
    /// <param name="includeTags"></param>
    /// <param name="excludeTags"></param>
    /// <returns></returns>
    public static bool MeetsTagRequirements(PrefabInstance prefabInstance, FastTags<TagGroup.Poi> includeTags, FastTags<TagGroup.Poi> excludeTags)
    {
        if (!includeTags.IsEmpty &&
            !prefabInstance.prefab.Tags.Test_AnySet(includeTags))
        {
            return false;
        }

        if (!excludeTags.IsEmpty &&
            prefabInstance.prefab.Tags.Test_AnySet(excludeTags))
        {
            return false;
        }

        return true;
    }
}
