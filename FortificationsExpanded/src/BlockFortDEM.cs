using UnityEngine;

/// <summary>
/// What every fortification piece carries from the XML for FortRunDEM: its family (FortFamily, gates included) and,
/// on the stages a fill or restore takes a step further, that stage's name (FortStage: Empty, Half, Stumps, Bent...).
/// Read once when the block loads.
/// </summary>
public interface IFortBlockDEM
{
    string FortFamily { get; }
    string FortStage { get; }
}

/// <summary>
/// Every fortification piece. Health, damage stages (the model's DMG0..DMG2 children, swapped by the game's
/// MeshDamage), fills, breaches and repairs are all vanilla block behaviour from the XML; this fixes up the model
/// when it spawns (FortModelDEM) and tells FortRunDEM when a repair hit fills or repairs it, so the rest of the run
/// gets the same.
/// </summary>
public class BlockFortDEM : Block, IFortBlockDEM
{
    public string FortFamily { get; private set; }
    public string FortStage { get; private set; }

    public override void Init()
    {
        base.Init();
        FortFamily = Properties.GetString("FortFamily");
        FortStage = Properties.GetString("FortStage");
    }

    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        FortModelDEM.Prepare(_ebcd);
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
    }

    public override int OnBlockDamaged(WorldBase _world, BlockValueRef _bvRef, BlockValue _blockValue,
        int _damagePoints, int _entityIdThatDamaged, ItemActionAttack.AttackHitInfo _attackHitInfo,
        bool _bUseHarvestTool, bool _bBypassMaxDamage, int _recDepth = 0)
    {
        // Repairs and upgrades are negative damage
        if (_damagePoints < 0)
        {
            FortRunDEM.Hit(this, _bvRef, _blockValue, _damagePoints, _entityIdThatDamaged);
        }
        return base.OnBlockDamaged(_world, _bvRef, _blockValue, _damagePoints, _entityIdThatDamaged, _attackHitInfo,
            _bUseHarvestTool, _bBypassMaxDamage, _recDepth);
    }
}

/// <summary>
/// The gates: vanilla doors (CompositeTileEntity with the door and lock features, which drive the model's Animator),
/// with the same model fix-up as the other pieces. They belong to their family's runs, for repairs.
/// </summary>
public class BlockFortGateDEM : BlockCompositeTileEntity, IFortBlockDEM
{
    public string FortFamily { get; private set; }
    public string FortStage { get; private set; }

    public override void Init()
    {
        base.Init();
        FortFamily = Properties.GetString("FortFamily");
        FortStage = Properties.GetString("FortStage");
    }

    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        FortModelDEM.Prepare(_ebcd);
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
    }

    public override int OnBlockDamaged(WorldBase _world, BlockValueRef _bvRef, BlockValue _blockValue,
        int _damagePoints, int _entityIdThatDamaged, ItemActionAttack.AttackHitInfo _attackHitInfo,
        bool _bUseHarvestTool, bool _bBypassMaxDamage, int _recDepth = 0)
    {
        if (_damagePoints < 0)
        {
            FortRunDEM.Hit(this, _bvRef, _blockValue, _damagePoints, _entityIdThatDamaged);
        }
        return base.OnBlockDamaged(_world, _bvRef, _blockValue, _damagePoints, _entityIdThatDamaged, _attackHitInfo,
            _bUseHarvestTool, _bBypassMaxDamage, _recDepth);
    }
}

public static class FortModelDEM
{
    /// <summary>
    /// The bundle can't carry the game's tags, so the model's colliders are marked as block colliders (the game's
    /// raycasts only treat T_Block colliders as part of a block), and its materials are moved to the game's model
    /// shader, inactive damage stages included. This runs before the game's own model setup, which then tints the
    /// new materials (TintColor) and picks the damage stage.
    /// </summary>
    public static void Prepare(BlockEntityData ebcd)
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
    }
}
