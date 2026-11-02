using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Salvage Hopper (XML class "HopperDEM, TrapsExpanded"): a rusty bin with a funnel and a car-alternator magnet, and a
/// storage container (its TEFeatureStorage in XML). Each zombie a trap kills within Range of it drops ScrapCount scrap
/// iron into it, and BrassChance of BrassCount brass, earning back part of the traps' ammo. Only the nearest hopper
/// gets each haul; it levels up from them. Upgrades (level 3): A Ammo Press (the haul is pressed into ammo for the
/// emptiest ammo trap within Range that has room: each trap's PressItem and PressCount), B Scavenger (ScavengeChance of
/// one of ScavengeItems as well).
///
/// XML properties: Range, ScrapItem, ScrapCount ("min,max"), BrassItem, BrassChance, BrassCount, ScavengeItems,
/// ScavengeChance, DropSound, and the shared ones.
/// </summary>
public class BlockHopperDEM : BlockCompositeTileEntity, ITrapDEM
{
    public float Range = 10f;
    public string ScrapItem = "resourceScrapIron";
    public Vector2i ScrapCount = new Vector2i(1, 3);
    public string BrassItem = "resourceScrapBrass";
    public float BrassChance = 0.35f;
    public Vector2i BrassCount = new Vector2i(1, 2);
    public string[] ScavengeItems = new string[0];
    public float ScavengeChance = 0.12f;
    public string DropSound = "trapiron_place";

    public TrapSettingsDEM Settings { get; private set; }

    public override void Init()
    {
        base.Init();
        Settings = TrapSettingsDEM.Parse(this);
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseString("ScrapItem", ref ScrapItem);
        ScrapCount = Range2(Properties, "ScrapCount", ScrapCount);
        Properties.ParseString("BrassItem", ref BrassItem);
        Properties.ParseFloat("BrassChance", ref BrassChance);
        BrassCount = Range2(Properties, "BrassCount", BrassCount);
        string items = "";
        Properties.ParseString("ScavengeItems", ref items);
        if (!string.IsNullOrEmpty(items))
        {
            ScavengeItems = items.Split(',');
            for (int i = 0; i < ScavengeItems.Length; i++)
            {
                ScavengeItems[i] = ScavengeItems[i].Trim();
            }
        }
        Properties.ParseFloat("ScavengeChance", ref ScavengeChance);
        Properties.ParseString("DropSound", ref DropSound);
    }

    private static Vector2i Range2(DynamicProperties p, string name, Vector2i fallback)
    {
        if (!p.Values.ContainsKey(name))
        {
            return fallback;
        }
        string[] parts = p.Values[name].Split(',');
        if (parts.Length == 2 && int.TryParse(parts[0].Trim(), out int a) && int.TryParse(parts[1].Trim(), out int b))
        {
            return new Vector2i(a, b);
        }
        return fallback;
    }

    public TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<SalvageHopperControllerDEM>();
    }

    public void ExtraCommands(List<BlockActivationCommand> commands, WorldBase world, BlockValue blockValue,
        Vector3i pos, TrapRecordDEM record)
    {
    }

    public bool ServerCommand(World world, Vector3i pos, string command)
    {
        return false;
    }

    public string StateText(WorldBase world, BlockValue blockValue, Vector3i pos, TrapRecordDEM record)
    {
        return null;
    }

    public override void OnBlockEntityTransformAfterActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _bed)
    {
        base.OnBlockEntityTransformAfterActivated(_world, _blockPos, _blockValue, _bed);
        TrapModelDEM.Prepare(this, _bed, _blockPos, true);
    }

    public override BlockActivationCommand[] GetBlockActivationCommands(WorldBase _world, BlockValue _blockValue,
        Vector3i _blockPos, EntityAlive _entityFocusing)
    {
        return TrapUiDEM.Commands(this, base.GetBlockActivationCommands(_world, _blockValue, _blockPos, _entityFocusing),
            _world, _blockValue, _blockPos, _entityFocusing);
    }

    public override bool HasBlockActivationCommands(WorldBase _world, BlockValue _blockValue, Vector3i _blockPos,
        EntityAlive _entityFocusing)
    {
        return true;
    }

    public override bool OnBlockActivated(string _commandName, WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, EntityPlayerLocal _player)
    {
        if (TrapUiDEM.OnCommand(this, _commandName, _world, _blockPos, _blockValue, _player))
        {
            return true;
        }
        return base.OnBlockActivated(_commandName, _world, _blockPos, _blockValue, _player);
    }

    public override string GetActivationText(WorldBase _world, BlockValue _blockValue, Vector3i _blockPos,
        EntityAlive _entityFocusing)
    {
        return TrapUiDEM.Text(this, base.GetActivationText(_world, _blockValue, _blockPos, _entityFocusing), _world,
            _blockValue, _blockPos);
    }

    public override void OnBlockAdded(WorldBase _world, Chunk _chunk, Vector3i _blockPos, BlockValue _blockValue,
        PlatformUserIdentifierAbs _addedByPlayer)
    {
        base.OnBlockAdded(_world, _chunk, _blockPos, _blockValue, _addedByPlayer);
        if (!_blockValue.ischild)
        {
            TrapStoreDEM.Placed(_blockPos, Settings.Name, _addedByPlayer);
        }
    }

    public override void OnBlockRemoved(WorldBase _world, Chunk _chunk, Vector3i _blockPos, BlockValue _blockValue)
    {
        base.OnBlockRemoved(_world, _chunk, _blockPos, _blockValue);
        if (!_blockValue.ischild)
        {
            TrapStoreDEM.Removed(_world as World, _blockPos);
        }
    }

    public override DestroyedResult OnBlockDestroyedBy(WorldBase _world, BlockValueRef _bvRef, BlockValue _blockValue,
        int _entityId, bool _bUseHarvestTool)
    {
        if (!_blockValue.ischild && SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            BloodMoonDEM.TrapLost(GetBlockName());
        }
        return base.OnBlockDestroyedBy(_world, _bvRef, _blockValue, _entityId, _bUseHarvestTool);
    }

    public override DestroyedResult OnBlockDestroyedByExplosion(WorldBase _world, BlockValueRef _bvRef,
        BlockValue _blockValue, int _playerThatStartedExpl)
    {
        if (!_blockValue.ischild && SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            BloodMoonDEM.TrapLost(GetBlockName());
        }
        return base.OnBlockDestroyedByExplosion(_world, _bvRef, _blockValue, _playerThatStartedExpl);
    }
}

/// <summary>Lives on a Salvage Hopper's model: takes the hauls from trap kills nearby (server) and clanks when one
/// lands (everyone).</summary>
public class SalvageHopperControllerDEM : TrapControllerDEM
{
    private BlockHopperDEM hopper;

    protected override float ActDelay => 60f;

    protected override float IdleDelay => 60f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        hopper = (BlockHopperDEM)trap;
        base.Setup(trap, pos);
    }

    protected override bool Act(World world)
    {
        return false;
    }

    /// <summary>Server: a trap killed a zombie; the nearest hopper within range gets the haul.</summary>
    public static void TrapKill(World world, EntityAlive victim)
    {
        if (world == null || victim == null)
        {
            return;
        }
        SalvageHopperControllerDEM best = null;
        float bestDist = float.MaxValue;
        foreach (TrapControllerDEM c in Active)
        {
            if (!(c is SalvageHopperControllerDEM h) || h.hopper == null)
            {
                continue;
            }
            float d = (h.BlockPos.ToVector3() + new Vector3(0.5f, 0.5f, 0.5f) - victim.position).sqrMagnitude;
            if (d <= h.hopper.Range * h.hopper.Range && d < bestDist)
            {
                best = h;
                bestDist = d;
            }
        }
        best?.Haul(world, victim);
    }

    private void Haul(World world, EntityAlive victim)
    {
        TrapStoreDEM.AddKill(BlockPos, Settings.Name);
        if (Upgraded('A') && Press(world))
        {
            Broadcast(BlockPos.ToVector3(), new[] { 1 });
            return;
        }
        if (!(world.GetTileEntity(BlockPos) is TileEntityComposite te))
        {
            return;
        }
        TEFeatureStorage storage = te.GetFeature<TEFeatureStorage>();
        if (storage == null)
        {
            return;
        }
        GameRandom rnd = world.GetGameRandom();
        Add(storage, hopper.ScrapItem, rnd.RandomRange(hopper.ScrapCount.x, hopper.ScrapCount.y + 1));
        if (rnd.RandomFloat < hopper.BrassChance)
        {
            Add(storage, hopper.BrassItem, rnd.RandomRange(hopper.BrassCount.x, hopper.BrassCount.y + 1));
        }
        if (Upgraded('B') && hopper.ScavengeItems.Length > 0 && rnd.RandomFloat < hopper.ScavengeChance)
        {
            Add(storage, hopper.ScavengeItems[rnd.RandomRange(0, hopper.ScavengeItems.Length)], 1);
        }
        storage.SetModified();
        Broadcast(BlockPos.ToVector3(), new[] { 0 });
    }

    /// <summary>Into the bin: onto stacks already there first, then an empty slot; if the bin is full it spills
    /// on the ground by the hopper.</summary>
    private void Add(TEFeatureStorage storage, string item, int count)
    {
        ItemValue iv = ItemClass.GetItem(item);
        if (iv == null || iv.IsEmpty() || count <= 0)
        {
            return;
        }
        ItemStack stack = new ItemStack(iv, count);
        storage.TryStackItem(0, stack);
        if (stack.count > 0 && !storage.AddItem(stack))
        {
            GameManager.Instance.ItemDropServer(stack, BlockPos.ToVector3() + new Vector3(0.5f, 1.1f, 0.5f),
                new Vector3(0.3f, 0f, 0.3f), -1, 600f);
        }
    }

    /// <summary>Ammo Press: tops up the emptiest ammo trap in range that has room. False when none needs it.</summary>
    private bool Press(World world)
    {
        Vector3 here = BlockPos.ToVector3();
        TrapControllerDEM emptiest = null;
        float lowest = 1f;
        foreach (TrapControllerDEM c in Active)
        {
            if (c == this || !(world.GetBlock(c.Position).Block is ITrapDEM t))
            {
                continue;
            }
            TrapSettingsDEM s = t.Settings;
            if (!s.UsesAmmo || string.IsNullOrEmpty(s.PressItem)
                || (c.Position.ToVector3() - here).sqrMagnitude > hopper.Range * hopper.Range)
            {
                continue;
            }
            TrapRecordDEM rec = TrapStoreDEM.Get(c.Position, s.Name);
            float fill = rec.AmmoTotal / (float)s.AmmoCapacity;
            if (fill < lowest)
            {
                lowest = fill;
                emptiest = c;
            }
        }
        if (emptiest == null)
        {
            return false;
        }
        ITrapDEM trap = (ITrapDEM)world.GetBlock(emptiest.Position).Block;
        TrapRecordDEM target = TrapStoreDEM.Get(emptiest.Position, trap.Settings.Name);
        if (target.AddAmmo(trap.Settings.PressItem, trap.Settings.PressCount, trap.Settings.AmmoCapacity) <= 0)
        {
            return false;
        }
        TrapStoreDEM.Changed(emptiest.Position);
        return true;
    }

    /// <summary>A clank as the haul drops in (a hiss of the press for Ammo Press).</summary>
    public override void PlayFx(int[] ids)
    {
        Vector3 at = BlockPos.ToVector3() + new Vector3(0.5f, 0.8f, 0.5f);
        if (ids.Length > 0 && ids[0] == 1)
        {
            FxDEM.Vanilla("p_wire_tool_sparks", at, Quaternion.identity, 1f);
        }
        if (!GameManager.IsDedicatedServer && !string.IsNullOrEmpty(hopper.DropSound))
        {
            Audio.Manager.Play(at, hopper.DropSound);
        }
    }
}
