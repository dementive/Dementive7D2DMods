using UnityEngine;

/// <summary>
/// A party member planted the flag for a shared quest. Clients send it to the server, which passes it to the rest
/// of the planter's party; each member completes the PlaceFlagDEM objective of their own copy of the quest.
/// </summary>
public class NetPackageQuestFlagDEM : NetPackage
{
    private int placerId;

    private int questCode;

    private Vector3 position;

    public NetPackageQuestFlagDEM Setup(int _placerId, int _questCode, Vector3 _position)
    {
        placerId = _placerId;
        questCode = _questCode;
        position = _position;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        placerId = _br.ReadInt32();
        questCode = _br.ReadInt32();
        position = StreamUtils.ReadVector3(_br);
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(placerId);
        _bw.Write(questCode);
        StreamUtils.Write(_bw, position);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
        {
            return;
        }

        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            if (Sender != null)
            {
                placerId = Sender.entityId;
            }
            Relay(_world);
            return;
        }

        Apply(_world.GetPrimaryPlayer());
    }

    /// <summary>
    /// Server side: passes the flag to every other member of the planter's party.
    /// </summary>
    public void Relay(World world)
    {
        EntityPlayer placer = world.GetEntity(placerId) as EntityPlayer;
        if (placer == null || placer.Party == null)
        {
            return;
        }

        foreach (EntityPlayer member in placer.Party.MemberList)
        {
            if (member == null || member.entityId == placerId)
            {
                continue;
            }

            if (member is EntityPlayerLocal localMember)
            {
                Apply(localMember);
            }
            else
            {
                SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
                    NetPackageManager.GetPackage<NetPackageQuestFlagDEM>().Setup(placerId, questCode, position),
                    _onlyClientsAttachedToAnEntity: false,
                    member.entityId);
            }
        }
    }

    private void Apply(EntityPlayerLocal player)
    {
        if (player == null)
        {
            return;
        }

        foreach (Quest quest in player.QuestJournal.quests)
        {
            if (quest.QuestCode != questCode || quest.CurrentState != Quest.QuestState.InProgress)
            {
                continue;
            }

            foreach (BaseObjective objective in quest.Objectives)
            {
                if (objective is ObjectivePlaceFlagDEM flag && flag.Phase == quest.CurrentPhase)
                {
                    flag.TryPlace(position, false);
                }
            }
        }
    }
}
