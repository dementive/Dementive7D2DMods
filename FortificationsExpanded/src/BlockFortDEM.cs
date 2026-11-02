using UnityEngine;

/// <summary>
/// Every fortification piece. Health, damage stages (the model's DMG0..DMG2 children, swapped by the game's
/// MeshDamage), fills, breaches and repairs are all vanilla block behaviour from the XML; this only fixes up the model
/// when it spawns (FortModelDEM).
/// </summary>
public class BlockFortDEM : Block
{
    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        FortModelDEM.Prepare(_ebcd);
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
    }
}

/// <summary>
/// The gates: vanilla doors (CompositeTileEntity with the door and lock features, which drive the model's Animator),
/// with the same model fix-up as the other pieces.
/// </summary>
public class BlockFortGateDEM : BlockCompositeTileEntity
{
    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        FortModelDEM.Prepare(_ebcd);
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
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
