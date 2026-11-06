using UnityEngine;

/// <summary>
/// The hollow trunk cache (see FEATURES.md, kind "cache"): a vanilla composite-tile-entity loot container (like
/// cntTrashPile: CompositeFeatures / TEFeatureStorage with a LootList, so the container UI, open and close, the
/// respawn rules and multiplayer sync are the game's own) whose model is a solid multi-block feature. All it adds is
/// what BlockFeatureDEM adds for the other features: the T_Block tag on the model's colliders, so the interaction ray
/// finds the block, and the move of the model's material to the game's plant shader.
/// </summary>
public class BlockFeatureCacheDEM : BlockCompositeTileEntity
{
    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        if (_ebcd != null && _ebcd.transform != null)
        {
            foreach (Collider collider in _ebcd.transform.GetComponentsInChildren<Collider>(true))
            {
                collider.gameObject.tag = "T_Block";
            }
            NatureShaderDEM.Apply(_ebcd.transform);
        }
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
    }
}
