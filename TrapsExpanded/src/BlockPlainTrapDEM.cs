using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Base for the mod's unpowered traps (Grease Slick, Burn Barrel, Swinging Log, Bear Trap, Trip Bow): always on, with
/// the same model handling, radial menu and records as the powered ones. Their owner is whoever placed them (kept in
/// the trap's record). One bit of block meta holds a trap's own on/off state (the Bear Trap armed, the Burn Barrel
/// lit), so every player sees it and it's saved with the world. Pick them up with the radial menu's Take.
/// </summary>
public abstract class BlockPlainTrapDEM : Block, ITrapDEM
{
    private const byte StateBit = 1;

    public TrapSettingsDEM Settings { get; private set; }

    public abstract TrapControllerDEM AddController(GameObject model);

    public virtual void ExtraCommands(List<BlockActivationCommand> commands, WorldBase world, BlockValue blockValue,
        Vector3i pos, TrapRecordDEM record)
    {
    }

    public virtual bool ServerCommand(World world, Vector3i pos, string command)
    {
        return false;
    }

    public virtual string StateText(WorldBase world, BlockValue blockValue, Vector3i pos, TrapRecordDEM record)
    {
        return null;
    }

    public override void Init()
    {
        base.Init();
        Settings = TrapSettingsDEM.Parse(this);
    }

    public bool IsWornOut(BlockValue blockValue)
    {
        return TrapModelDEM.IsWornOut(this, Settings, blockValue);
    }

    public static bool GetState(BlockValue bv)
    {
        return (bv.meta & StateBit) != 0;
    }

    /// <summary>Server: sets the trap's on/off bit (synced to everyone with the block).</summary>
    public static void SetState(World world, Vector3i pos, bool on)
    {
        BlockValue bv = world.GetBlock(pos);
        if (GetState(bv) == on)
        {
            return;
        }
        bv.meta = (byte)(on ? bv.meta | StateBit : bv.meta & ~StateBit);
        world.SetBlockRPC(pos, bv);
    }

    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
        TrapModelDEM.Prepare(this, _ebcd, _blockPos, true);
    }

    public override bool HasBlockActivationCommands(WorldBase _world, BlockValue _blockValue, Vector3i _blockPos,
        EntityAlive _entityFocusing)
    {
        return true;
    }

    public override BlockActivationCommand[] GetBlockActivationCommands(WorldBase _world, BlockValue _blockValue,
        Vector3i _blockPos, EntityAlive _entityFocusing)
    {
        return TrapUiDEM.Commands(this, base.GetBlockActivationCommands(_world, _blockValue, _blockPos, _entityFocusing),
            _world, _blockValue, _blockPos, _entityFocusing);
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
        string name = string.Format(Localization.Get("dem_trapUse"), GetLocalizedBlockName());
        return TrapUiDEM.Text(this, name, _world, _blockValue, _blockPos);
    }

    public override void OnBlockAdded(WorldBase world, Chunk _chunk, Vector3i _blockPos, BlockValue _blockValue,
        PlatformUserIdentifierAbs _addedByPlayer)
    {
        base.OnBlockAdded(world, _chunk, _blockPos, _blockValue, _addedByPlayer);
        if (!_blockValue.ischild)
        {
            TrapStoreDEM.Placed(_blockPos, Settings.Name, _addedByPlayer);
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

    public override void OnBlockRemoved(WorldBase _world, Chunk _chunk, Vector3i _blockPos, BlockValue _blockValue)
    {
        base.OnBlockRemoved(_world, _chunk, _blockPos, _blockValue);
        if (!_blockValue.ischild)
        {
            TrapStoreDEM.Removed(_world as World, _blockPos);
        }
    }
}
