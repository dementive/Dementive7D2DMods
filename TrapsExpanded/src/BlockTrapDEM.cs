using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Base for the mod's powered traps. Like the vanilla blade trap it keeps the placer as owner in a
/// TileEntityPoweredMeleeTrap and is switched by the power grid through ActivateTrap. When the model spawns it marks
/// the colliders as block colliders, switches the materials to the game's model shader and adds the trap's
/// controller, which does the work. Settings shared by every trap (wear, ammo, upgrades) are in TrapSettingsDEM.
/// </summary>
public abstract class BlockTrapDEM : BlockPoweredTrap, ITrapDEM
{
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

    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
        TrapModelDEM.Prepare(this, _ebcd, _blockPos, false);
    }

    public override bool ActivateTrap(BlockEntityData blockEntity, bool isOn)
    {
        if (blockEntity == null || !blockEntity.bHasTransform || blockEntity.transform == null)
        {
            return false;
        }
        TrapControllerDEM controller = blockEntity.transform.GetComponent<TrapControllerDEM>();
        if (controller == null)
        {
            return false;
        }
        controller.IsOn = isOn;
        return true;
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
        return TrapUiDEM.Text(this, base.GetActivationText(_world, _blockValue, _blockPos, _entityFocusing), _world,
            _blockValue, _blockPos);
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

    /// <summary>The trap's controller at a block position, if its model is loaded here.</summary>
    public static TrapControllerDEM FindController(World world, Vector3i pos)
    {
        return TrapModelDEM.FindController(world, pos);
    }
}

/// <summary>What every trap base does with its model and its health.</summary>
public static class TrapModelDEM
{
    /// <summary>Worn down to its last WornOutFraction of health: it stops until repaired, rather than wearing
    /// itself to destruction.</summary>
    public static bool IsWornOut(Block block, TrapSettingsDEM s, BlockValue blockValue)
    {
        return s != null && s.WearPerUse > 0 && blockValue.damage >= block.MaxDamage * (1f - s.WornOutFraction);
    }

    /// <summary>
    /// The bundle can't carry the game's tags, so this marks the model's colliders as block colliders (the game's
    /// raycasts only treat T_Block colliders as part of a block), moves our materials to the game's model shader, and
    /// adds the trap's controller. Unpowered traps are always on.
    /// </summary>
    public static void Prepare(ITrapDEM trap, BlockEntityData ebcd, Vector3i pos, bool alwaysOn)
    {
        if (ebcd == null || ebcd.transform == null)
        {
            return;
        }
        foreach (Collider collider in ebcd.transform.GetComponentsInChildren<Collider>(true))
        {
            collider.gameObject.tag = "T_Block";
        }
        GameShaderDEM.Apply(ebcd.transform);

        TrapControllerDEM controller = ebcd.transform.GetComponent<TrapControllerDEM>();
        if (controller == null)
        {
            controller = trap.AddController(ebcd.transform.gameObject);
        }
        if (controller == null)
        {
            return;
        }
        controller.Setup(trap, pos);
        if (alwaysOn)
        {
            controller.IsOn = true;
        }
    }

    public static TrapControllerDEM FindController(World world, Vector3i pos)
    {
        Chunk chunk = world?.GetChunkFromWorldPos(pos) as Chunk;
        BlockEntityData entity = chunk?.GetBlockEntity(pos);
        if (entity == null || !entity.bHasTransform || entity.transform == null)
        {
            return null;
        }
        return entity.transform.GetComponent<TrapControllerDEM>();
    }
}
