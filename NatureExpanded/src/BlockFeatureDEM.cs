using UnityEngine;

/// <summary>
/// Every Nature Expanded solid natural feature (boulders, rock formations, cairns, bones; see FEATURES.md): a vanilla
/// multi-block model block (Shape ModelEntity, like vanilla's resourceRock boulders) placed by world generation.
/// The game's own code does the heavy lifting: with Collide movement it moves every collider of the model to the
/// movement layer (Chunk.OnDisplayBlockEntities), so players, zombies, animals and vehicles all collide with the
/// compound colliders in the bundle's prefab. What it can't do for a model from a mod's bundle is the tag the game's
/// raycasts look for: a collider counts as part of a block only if it is tagged T_Block (needed for harvesting), and a
/// bundle can't carry the game's tags. The model's material is moved to the game's plant shader (NatureShaderDEM).
/// </summary>
public class BlockFeatureDEM : Block
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
