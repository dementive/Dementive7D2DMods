using System.Collections.Generic;
using HarmonyLib;

/// <summary>
/// Grows the water's-edge plants (cattails, reeds, blue flag iris, marsh marigold, and sedge and horsetail among the
/// grasses) along real shores. The biome tables can't see water, so these plants have no drifts; instead, as world
/// generation decorates each chunk, every dry spot on the ground within two blocks of water may get one: cattails and
/// reeds right at the water line, iris, marigold, sedge and horsetail a step back up the bank. It runs after vanilla's own pass over the chunk, inside its lock, and keeps to the same
/// rules (no roads or buildings, nothing in deco-suppressed ground), taking the spot from grass but nothing else. Like
/// all decoration it happens where the chunk is generated (the server in co-op), and only for new chunks.
/// </summary>
[HarmonyPatch(typeof(WorldDecoratorBlocksFromBiome), nameof(WorldDecoratorBlocksFromBiome.decorateSingleBlocks))]
public static class ShoreDEM
{
    /// <summary>Per biome: the chance a spot right at the water gets a plant and one a block further, and what grows
    /// at each (block name without the mod prefix, weight).</summary>
    private sealed class Shore
    {
        public float Edge;
        public float Bank;
        public (string, float)[] EdgePlants;
        public (string, float)[] BankPlants;
        public (Block, float)[] EdgeBlocks;
        public (Block, float)[] BankBlocks;
    }

    private static readonly Dictionary<string, Shore> Shores = new Dictionary<string, Shore>
    {
        ["pine_forest"] = new Shore
        {
            Edge = 0.45f, Bank = 0.25f,
            EdgePlants = new[] { ("Cattail", 0.4f), ("Reeds", 0.3f), ("BlueFlagIris", 0.15f), ("GrassSedge", 0.15f) },
            BankPlants = new[] { ("Reeds", 0.2f), ("BlueFlagIris", 0.2f), ("MarshMarigold", 0.2f), ("GrassSedge", 0.25f), ("GrassHorsetail", 0.15f) },
        },
        ["burnt_forest"] = new Shore
        {
            Edge = 0.25f, Bank = 0.05f,
            EdgePlants = new[] { ("Reeds", 0.6f), ("Cattail", 0.4f) },
            BankPlants = new[] { ("Reeds", 1f) },
        },
        ["wasteland"] = new Shore
        {
            Edge = 0.2f, Bank = 0.04f,
            EdgePlants = new[] { ("Reeds", 0.6f), ("Cattail", 0.4f) },
            BankPlants = new[] { ("Reeds", 1f) },
        },
        ["desert"] = new Shore
        {
            Edge = 0.2f, Bank = 0f,
            EdgePlants = new[] { ("Reeds", 1f) },
            BankPlants = new (string, float)[0],
        },
    };

    private static bool resolved;

    public static void Postfix(World _world, Chunk _chunk, Chunk cX1Z0, Chunk cX0Z1, Chunk cX1Z1, bool _chunkOverlapsSuppressArea,
        GameRandom _random, WorldDecoratorBlocksFromBiome __instance)
    {
        if (!resolved)
        {
            Resolve();
        }
        Vector3i origin = _chunk.GetWorldPos();
        for (int z = 0; z < 16; z++)
        {
            for (int x = 0; x < 16; x++)
            {
                // Vanilla leaves a column's biome out where decoration is suppressed (around buildings)
                if (_chunkOverlapsSuppressArea && __instance.chunkBiomes[x + z * 16] == null)
                {
                    continue;
                }
                int y = _chunk.GetTerrainHeight(x, z) + 1;
                if (y < 3 || y > 250)
                {
                    continue;
                }
                BiomeDefinition biome = _world.Biomes.GetBiome(_chunk.GetBiomeId(x, z));
                if (biome == null || !Shores.TryGetValue(biome.m_sBiomeName, out Shore shore))
                {
                    continue;
                }
                int distance = WaterDistance(_chunk, x, y, z);
                if (distance == 0)
                {
                    continue;
                }
                (Block, float)[] plants = distance == 1 ? shore.EdgeBlocks : shore.BankBlocks;
                if (plants.Length == 0 || _random.RandomFloat >= (distance == 1 ? shore.Edge : shore.Bank))
                {
                    continue;
                }
                Block block = Pick(plants, _random.RandomFloat);
                if (block != null && Free(_chunk, x, y, z, block))
                {
                    Place(_world, _chunk, cX1Z0, cX0Z1, cX1Z1, _random, origin, x, y, z, block);
                }
            }
        }
    }

    /// <summary>1 when water lies right beside the spot (level with the ground there or a block below), 2 when it's a
    /// block further, 0 when there's none within two (this chunk only).</summary>
    private static int WaterDistance(Chunk chunk, int x, int y, int z)
    {
        int best = 0;
        for (int dz = -2; dz <= 2; dz++)
        {
            for (int dx = -2; dx <= 2; dx++)
            {
                int nx = x + dx, nz = z + dz;
                int d = System.Math.Max(System.Math.Abs(dx), System.Math.Abs(dz));
                if (d == 0 || nx < 0 || nz < 0 || nx > 15 || nz > 15 || (best != 0 && d >= best))
                {
                    continue;
                }
                if (chunk.IsWater(nx, y - 1, nz) || chunk.IsWater(nx, y - 2, nz))
                {
                    best = d;
                }
            }
        }
        return best;
    }

    /// <summary>A dry spot on solid ground, empty or holding grass, with room above for the whole plant.</summary>
    private static bool Free(Chunk chunk, int x, int y, int z, Block block)
    {
        if (chunk.IsWater(x, y, z) || chunk.GetBlockNoDamage(x, y - 1, z).isair)
        {
            return false;
        }
        BlockValue here = chunk.GetBlockNoDamage(x, y, z);
        if (!here.isair && !Grass(here.Block))
        {
            return false;
        }
        EnumDecoAllowed allowed = chunk.GetDecoAllowedAt(x, z);
        if (allowed.IsNothing() || allowed.GetStreetOnly())
        {
            return false;
        }
        int height = block.isMultiBlock ? block.multiBlockPos.dim.y : 1;
        for (int i = 1; i < height; i++)
        {
            if (y + i > 254 || !chunk.GetBlockNoDamage(x, y + i, z).isair || chunk.IsWater(x, y + i, z))
            {
                return false;
            }
        }
        return true;
    }

    /// <summary>Places the plant the way vanilla's decorator places one (WorldDecoratorBlocksFromBiome.
    /// decorateSingleBlockTryPlaceDeco): a random turn, the deco-allowed checks and marks, then the block itself.</summary>
    private static void Place(World world, Chunk chunk, Chunk cX1Z0, Chunk cX0Z1, Chunk cX1Z1, GameRandom random, Vector3i origin,
        int x, int y, int z, Block block)
    {
        BlockValue value = block.ToBlockValue();
        // Grass blocks are drawn unturned, like vanilla's decorator places them
        if (!Grass(block))
        {
            value.rotation = BiomeBlockDecoration.GetRandomRotation(random.RandomFloat, 7);
        }
        Vector3i pos = origin + new Vector3i(x, y, z);
        if (!DecoUtils.CanPlaceDeco(chunk, cX1Z0, cX0Z1, cX1Z1, pos, value, allowed => !allowed.GetStreetOnly()))
        {
            return;
        }
        DecoUtils.ApplyDecoAllowed(chunk, cX1Z0, cX0Z1, cX1Z1, pos, value);
        value = block.OnBlockPlaced(world, pos, value, random);
        chunk.SetBlock(world, x, y, z, value, true, true, false, false, -1);
    }

    /// <summary>A grass block, vanilla's or ours (they share the tall grass material).</summary>
    private static bool Grass(Block block)
    {
        return block.blockMaterial != null && block.blockMaterial.id == "Mtallgrass";
    }

    private static Block Pick((Block, float)[] plants, float roll)
    {
        float total = 0f;
        foreach ((Block _, float weight) in plants)
        {
            total += weight;
        }
        roll *= total;
        foreach ((Block block, float weight) in plants)
        {
            if ((roll -= weight) < 0f)
            {
                return block;
            }
        }
        return plants[plants.Length - 1].Item1;
    }

    /// <summary>Looks the blocks up once, after blocks.xml has loaded (world generation runs later); a missing block is
    /// left out.</summary>
    private static void Resolve()
    {
        foreach (Shore shore in Shores.Values)
        {
            shore.EdgeBlocks = Blocks(shore.EdgePlants);
            shore.BankBlocks = Blocks(shore.BankPlants);
        }
        resolved = true;
    }

    private static (Block, float)[] Blocks((string, float)[] plants)
    {
        List<(Block, float)> found = new List<(Block, float)>();
        foreach ((string name, float weight) in plants)
        {
            Block block = Block.GetBlockByName("DementiveNature" + name, false);
            if (block != null)
            {
                found.Add((block, weight));
            }
        }
        return found.ToArray();
    }
}
