using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Sent by a client to ask the server for the POI of an <see cref="ObjectiveGotoPOIDEM"/>. The server replies with
/// the vanilla <see cref="NetPackageQuestGotoPoint"/>, which finalizes any <see cref="ObjectiveRandomPOIGoto"/>.
/// </summary>
public class NetPackageGotoPOIDEM : NetPackage
{
    private int questGiverId;

    private int questCode;

    private FastTags<TagGroup.Global> questTags;

    private byte difficulty;

    private BiomeFilterTypes biomeFilterType;

    private string biomeFilter;

    private string prefabNames;

    public NetPackageGotoPOIDEM Setup(
        int _questGiverId,
        FastTags<TagGroup.Global> _questTags,
        int _questCode,
        byte _difficulty,
        IEnumerable<string> _prefabNames,
        BiomeFilterTypes _biomeFilterType = BiomeFilterTypes.AnyBiome,
        string _biomeFilter = "")
    {
        questGiverId = _questGiverId;
        questTags = _questTags;
        questCode = _questCode;
        difficulty = _difficulty;
        prefabNames = string.Join(",", _prefabNames);
        biomeFilterType = _biomeFilterType;
        biomeFilter = _biomeFilter;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        questGiverId = _br.ReadInt32();
        questCode = _br.ReadInt32();
        questTags = FastTags<TagGroup.Global>.Parse(_br.ReadString());
        difficulty = _br.ReadByte();
        biomeFilterType = (BiomeFilterTypes)_br.ReadByte();
        biomeFilter = _br.ReadString();
        prefabNames = _br.ReadString();
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(questGiverId);
        _bw.Write(questCode);
        _bw.Write(questTags.ToString());
        _bw.Write(difficulty);
        _bw.Write((byte)biomeFilterType);
        _bw.Write(biomeFilter);
        _bw.Write(prefabNames);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null || !SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }

        EntityAlive questGiver = _world.GetEntity(questGiverId) as EntityAlive;
        if (questGiver == null)
        {
            return;
        }

        // A dedicated server has no primary player, so use the player who sent the request
        EntityPlayer requestingPlayer = Sender != null
            ? _world.GetEntity(Sender.entityId) as EntityPlayer
            : _world.GetPrimaryPlayer();
        int requestingPlayerId = requestingPlayer != null ? requestingPlayer.entityId : -1;

        // Same lookup as NetPackageRandomTaggedPOIGotoDEM, so the player isn't sent back to a POI they just did
        Vector2 usedPoiCenter = questGiver is EntityTrader trader && trader.traderArea != null
            ? new Vector2(trader.traderArea.Position.x, trader.traderArea.Position.z)
            : new Vector2(questGiver.position.x, questGiver.position.z);
        List<Vector2> usedPoiLocations = requestingPlayer != null
            ? requestingPlayer.QuestJournal.GetUsedPOIs(usedPoiCenter, difficulty)
            : null;

        PrefabInstance prefabInstance = QuestUtils.GetNamedPOINearEntity(
            questGiver,
            new HashSet<string>(prefabNames.Split(','), StringComparer.OrdinalIgnoreCase),
            questTags,
            usedPoiLocations,
            requestingPlayerId,
            biomeFilterType,
            biomeFilter);

        if (prefabInstance == null)
        {
            return;
        }

        SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
            NetPackageManager.GetPackage<NetPackageQuestGotoPoint>().Setup(
                questGiverId,
                requestingPlayerId,
                questTags,
                questCode,
                NetPackageQuestGotoPoint.QuestGotoTypes.RandomPOI,
                difficulty,
                prefabInstance.boundingBoxPosition.x,
                prefabInstance.boundingBoxPosition.z,
                prefabInstance.boundingBoxSize.x,
                prefabInstance.boundingBoxSize.y,
                prefabInstance.boundingBoxSize.z),
            _onlyClientsAttachedToAnEntity: false,
            requestingPlayerId);
    }
}
