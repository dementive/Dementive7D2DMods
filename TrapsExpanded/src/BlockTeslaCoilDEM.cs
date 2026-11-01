using UnityEngine;

/// <summary>
/// Tesla Coil block (XML class "TeslaCoilDEM, TrapsExpanded"). A powered trap like the blade trap: it keeps the
/// placer as owner in a TileEntityPoweredMeleeTrap and gets switched by the power grid through ActivateTrap. The
/// zapping itself lives in TeslaCoilControllerDEM on the block's model.
///
/// XML properties: EntityDamage, Range, FireDelay (seconds between zaps), Chains (extra targets per zap),
/// ChainRange, ChainFalloff (damage multiplier per jump), JoltChance and JoltBuff (per zombie hit), WearPerZap
/// (block damage the coil takes per zap), WornOutFraction (health share left at which it stops until repaired),
/// ZapSound.
/// </summary>
public class BlockTeslaCoilDEM : BlockPoweredTrap
{
    public float EntityDamage = 22f;
    public float Range = 8f;
    public float FireDelay = 1.5f;
    public int Chains = 2;
    public float ChainRange = 4f;
    public float ChainFalloff = 0.6f;
    public float JoltChance = 0.1f;
    public string JoltBuff = "buffDementiveTrapsJolt";
    public int WearPerZap = 1;
    public float WornOutFraction = 0.05f;
    public string ZapSound = "electric_fence_impact";

    /// <summary>Arc origin: the toroid's center, relative to the bottom center of the block.</summary>
    public static readonly Vector3 ArcOffset = new Vector3(0.5f, 1.62f, 0.5f);

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("EntityDamage", ref EntityDamage);
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("FireDelay", ref FireDelay);
        Properties.ParseInt("Chains", ref Chains);
        Properties.ParseFloat("ChainRange", ref ChainRange);
        Properties.ParseFloat("ChainFalloff", ref ChainFalloff);
        Properties.ParseFloat("JoltChance", ref JoltChance);
        Properties.ParseString("JoltBuff", ref JoltBuff);
        Properties.ParseInt("WearPerZap", ref WearPerZap);
        Properties.ParseFloat("WornOutFraction", ref WornOutFraction);
        Properties.ParseString("ZapSound", ref ZapSound);
    }

    /// <summary>Worn down to its last WornOutFraction of health: it stops zapping until repaired, rather than
    /// wearing itself to destruction.</summary>
    public bool IsWornOut(BlockValue blockValue)
    {
        return blockValue.damage >= MaxDamage * (1f - WornOutFraction);
    }

    public override void OnBlockEntityTransformBeforeActivated(WorldBase _world, Vector3i _blockPos,
        BlockValue _blockValue, BlockEntityData _ebcd)
    {
        base.OnBlockEntityTransformBeforeActivated(_world, _blockPos, _blockValue, _ebcd);
        if (_ebcd == null || _ebcd.transform == null)
        {
            return;
        }

        // The bundle can't carry the game's tags, so mark the colliders as block colliders here (the game's
        // raycasts only treat T_Block colliders as part of a block)
        foreach (Collider collider in _ebcd.transform.GetComponentsInChildren<Collider>(true))
        {
            collider.gameObject.tag = "T_Block";
        }
        GameShaderDEM.Apply(_ebcd.transform);

        TeslaCoilControllerDEM controller = _ebcd.transform.GetComponent<TeslaCoilControllerDEM>();
        if (controller == null)
        {
            controller = _ebcd.transform.gameObject.AddComponent<TeslaCoilControllerDEM>();
        }
        controller.Setup(this, _blockPos);
    }

    public override bool ActivateTrap(BlockEntityData blockEntity, bool isOn)
    {
        if (blockEntity == null || !blockEntity.bHasTransform || blockEntity.transform == null)
        {
            return false;
        }
        TeslaCoilControllerDEM controller = blockEntity.transform.GetComponent<TeslaCoilControllerDEM>();
        if (controller == null)
        {
            return false;
        }
        controller.IsOn = isOn;
        return true;
    }

    /// <summary>The coil's controller at a block position, if its model is loaded here.</summary>
    public static TeslaCoilControllerDEM FindController(World world, Vector3i pos)
    {
        Chunk chunk = world?.GetChunkFromWorldPos(pos) as Chunk;
        BlockEntityData entity = chunk?.GetBlockEntity(pos);
        if (entity == null || !entity.bHasTransform || entity.transform == null)
        {
            return null;
        }
        return entity.transform.GetComponent<TeslaCoilControllerDEM>();
    }
}
