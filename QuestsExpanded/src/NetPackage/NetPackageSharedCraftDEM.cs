using System;

/// <summary>
/// A party member crafted an item one of their shared quests is waiting for. Clients send it to the server, which
/// passes it to the rest of the crafter's party; each member adds it to the Craft objectives of their own copy of
/// the quest (matched by quest code, which shared copies keep).
/// </summary>
public class NetPackageSharedCraftDEM : NetPackage
{
    private int crafterId;

    private int questCode;

    private string itemName;

    private int count;

    public NetPackageSharedCraftDEM Setup(int _crafterId, int _questCode, string _itemName, int _count)
    {
        crafterId = _crafterId;
        questCode = _questCode;
        itemName = _itemName;
        count = _count;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        crafterId = _br.ReadInt32();
        questCode = _br.ReadInt32();
        itemName = _br.ReadString();
        count = _br.ReadInt32();
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(crafterId);
        _bw.Write(questCode);
        _bw.Write(itemName);
        _bw.Write(count);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
        {
            return;
        }

        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            // Only pass on crafting the sender did themselves
            if (Sender != null)
            {
                crafterId = Sender.entityId;
            }
            Relay(_world);
            return;
        }

        Apply(_world.GetPrimaryPlayer());
    }

    /// <summary>
    /// Server side: gives the craft to every other member of the crafter's party.
    /// </summary>
    public void Relay(World world)
    {
        EntityPlayer crafter = world.GetEntity(crafterId) as EntityPlayer;
        if (crafter == null || crafter.Party == null)
        {
            return;
        }

        foreach (EntityPlayer member in crafter.Party.MemberList)
        {
            if (member == null || member.entityId == crafterId)
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
                    NetPackageManager.GetPackage<NetPackageSharedCraftDEM>().Setup(crafterId, questCode, itemName, count),
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
                if (objective is ObjectiveCraft craft
                    && craft.Phase == quest.CurrentPhase
                    && !craft.Complete
                    && craft.expectedItemClass != null
                    && craft.expectedItemClass.GetItemName() == itemName)
                {
                    craft.CurrentValue = (byte)Math.Min(craft.CurrentValue + count, craft.itemCount);
                    craft.Refresh();
                }
            }
        }
    }
}
