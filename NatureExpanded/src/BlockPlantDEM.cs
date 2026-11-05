using UnityEngine;

/// <summary>
/// Every Nature Expanded plant: a vanilla model block (Shape ModelEntity, like wild cotton) whose model is fixed up
/// when it spawns. The bundle can't carry the game's tags, so its collider is marked as a block collider (the game's
/// raycasts only treat T_Block colliders as part of a block, which harvesting needs), and its material is moved to the
/// game's plant shader (NatureShaderDEM). Everything else (harvest drops, placement by world generation) is the XML.
/// </summary>
public class BlockPlantDEM : Block
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
