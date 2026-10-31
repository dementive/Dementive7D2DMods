using System;
using System.Collections.Generic;

/*
 * Sends the player to one of the listed prefabs. The POI is picked when the trader offers the quest, from every
 * instance of those prefabs in the world that can host the quest (see QuestUtils.GetNamedPOINearEntity).
 * 	<objective type="GotoPOIDEM, QuestsExpanded">
            <property name="PrefabName" value="prefabName" />
            <property name="PrefabNames" value="prefabName,prefabName2" />
		</objective>
*/
public class ObjectiveGotoPOIDEM : ObjectiveRandomTaggedPOIGotoDEM
{
    public HashSet<string> PrefabNames { get; internal set; } = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    public override bool useUpdateLoop => true;

    public override void ParseProperties(DynamicProperties properties)
    {
        foreach (string property in new[] { "PrefabName", "PrefabNames" })
        {
            if (!properties.Values.ContainsKey(property))
                continue;

            foreach (string name in properties.Values[property].Split(','))
            {
                if (name.Trim().Length > 0)
                    PrefabNames.Add(name.Trim());
            }
        }

        if (PrefabNames.Count == 0)
            Log.Warning("ObjectiveGotoPOIDEM: PrefabNames contains no prefabs.");

        base.ParseProperties(properties);
    }

    public override PrefabInstance FindPrefab(EntityAlive questOwner, List<UnityEngine.Vector2> usedPoiLocations, int entityIdForQuests)
    {
        return QuestUtils.GetNamedPOINearEntity(
            questOwner,
            PrefabNames,
            OwnerQuest.QuestTags,
            usedPoiLocations,
            entityIdForQuests,
            biomeFilterType,
            biomeFilter);
    }

    public override NetPackage CreateServerRequest(EntityAlive questOwner)
    {
        return NetPackageManager.GetPackage<NetPackageGotoPOIDEM>().Setup(
            questOwner.entityId,
            OwnerQuest.QuestTags,
            OwnerQuest.QuestCode,
            (byte)POITier,
            PrefabNames,
            biomeFilterType,
            biomeFilter);
    }

    public override BaseObjective Clone()
    {
        var objectiveGotoPOI = new ObjectiveGotoPOIDEM();
        CopyValues(objectiveGotoPOI);
        return objectiveGotoPOI;
    }

    public override void CopyValues(BaseObjective objective)
    {
        base.CopyValues(objective);
        // Only read after parsing, so the clones can share the set
        ((ObjectiveGotoPOIDEM)objective).PrefabNames = PrefabNames;
    }
}
