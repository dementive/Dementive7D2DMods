using System.Collections.Generic;
using HarmonyLib;

/// <summary>
/// Grows the water's-edge plants (cattails, reeds, blue flag iris, marsh marigold, and sedge and horsetail among the
/// grasses) along real shores. The biome tables can't see water, so these plants have no drifts; instead, as world
/// generation decorates each chunk, every dry spot on the ground within two blocks of water may get one: cattails and
/// reeds right at the water line, iris, marigold, sedge and horsetail a step back up the bank. It runs after vanilla's own pass over the chunk, inside its lock, and keeps to the same
/// rules (no roads or buildings, nothing in deco-suppressed ground), taking the spot from grass but nothing else. Like
/// all decoration it happens where the chunk is generated (the server in co-op), and only for new chunks.
/// Weeping willows and cottonwoods also grow along pine forest shores, 3 to 8 (willow) or 10 (cottonwood) blocks from the water.
/// River stones and driftwood (ground cover) lie along the water's edge, and a fisherman's camp (a 5 x 5 feature, set
/// dressing) stands now and then on flat pine forest ground a few blocks back from the water.
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
            EdgePlants = new[] { ("Cattail", 0.4f), ("Reeds", 0.3f), ("BlueFlagIris", 0.15f), ("GrassSedge", 0.15f),
                                 ("RiverStones", 0.1f), ("Driftwood", 0.06f) },
            BankPlants = new[] { ("Reeds", 0.2f), ("BlueFlagIris", 0.2f), ("MarshMarigold", 0.2f), ("GrassSedge", 0.25f), ("GrassHorsetail", 0.15f),
                                 ("RiverStones", 0.05f), ("Driftwood", 0.03f) },
        },
        ["burnt_forest"] = new Shore
        {
            Edge = 0.25f, Bank = 0.05f,
            EdgePlants = new[] { ("Reeds", 0.6f), ("Cattail", 0.4f), ("Driftwood", 0.15f), ("RiverStones", 0.1f) },
            BankPlants = new[] { ("Reeds", 1f) },
        },
        ["wasteland"] = new Shore
        {
            Edge = 0.2f, Bank = 0.04f,
            EdgePlants = new[] { ("Reeds", 0.6f), ("Cattail", 0.4f), ("Driftwood", 0.15f), ("RiverStones", 0.1f) },
            BankPlants = new[] { ("Reeds", 1f) },
        },
        ["desert"] = new Shore
        {
            Edge = 0.2f, Bank = 0f,
            EdgePlants = new[] { ("Reeds", 1f), ("Driftwood", 0.15f), ("RiverStones", 0.15f) },
            BankPlants = new (string, float)[0],
        },
    };

    /// <summary>A tree that grows back from the water, not at it: its chance on each dry spot whose nearest water is
    /// between Min and Max blocks away (block name without the mod prefix).</summary>
    private sealed class ShoreTree
    {
        public string Name;
        public float Chance;
        public float Min;
        public float Max;
        public Block Block;
    }

    /// <summary>Per biome, the trees of the banks. Weeping willows stand a few steps back from the water, cottonwoods a
    /// little further (the biome tables carry the same trees away from water, at their own rates). The chances are per
    /// spot, so a bank 6 blocks deep gets a willow about every 80 spots.</summary>
    private static readonly Dictionary<string, ShoreTree[]> BankTrees = new Dictionary<string, ShoreTree[]>
    {
        ["pine_forest"] = new[]
        {
            new ShoreTree { Name = "TreeWillow01", Chance = 0.002f, Min = 3f, Max = 8f },
            new ShoreTree { Name = "TreeWillow02", Chance = 0.002f, Min = 3f, Max = 8f },
            new ShoreTree { Name = "TreeWillow03", Chance = 0.002f, Min = 3f, Max = 8f },
            new ShoreTree { Name = "TreeWillow04", Chance = 0.002f, Min = 3f, Max = 8f },
            new ShoreTree { Name = "TreeCottonwood01", Chance = 0.0015f, Min = 3f, Max = 10f },
            new ShoreTree { Name = "TreeCottonwood02", Chance = 0.0015f, Min = 3f, Max = 10f },
            new ShoreTree { Name = "TreeCottonwood03", Chance = 0.0015f, Min = 3f, Max = 10f },
            new ShoreTree { Name = "TreeCottonwood04", Chance = 0.004f, Min = 3f, Max = 10f },
        },
    };

    /// <summary>The fisherman's camp (CampFishing, a 5 x 5 feature): per biome, the chance that a cell tries to host it.
    /// A try needs flat, dry, empty ground under the whole footprint and water 3 to 8 blocks away, in this chunk, so only
    /// the few cells near a lake or river count: at 1.2e-4 a large map gets roughly 15 (an estimate; raise or lower
    /// this to taste). Footprints stay inside the chunk (masters 3 to 12 blocks in), so nothing depends on neighbours.</summary>
    private static readonly Dictionary<string, float> CampChance = new Dictionary<string, float>
    {
        ["pine_forest"] = 0.00012f,
    };

    private const int CampHalf = 2;
    private const int CampWaterMin = 3;
    private const int CampWaterMax = 8;

    private static Block campBlock;

    /// <summary>The farthest any bank tree looks for water, and the most its ground may differ in height from the
    /// water's (a bank, not a cliff).</summary>
    private const int TreeReach = 10;
    private const int TreeHeightDiff = 4;

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
                if (BankTrees.TryGetValue(biome.m_sBiomeName, out ShoreTree[] bankTrees))
                {
                    TryBankTree(_world, _chunk, cX1Z0, cX0Z1, cX1Z1, _random, origin, x, y, z, bankTrees);
                }
                if (campBlock != null && x > CampHalf && x < 16 - 1 - CampHalf && z > CampHalf && z < 16 - 1 - CampHalf
                    && CampChance.TryGetValue(biome.m_sBiomeName, out float campChance) && _random.RandomFloat < campChance)
                {
                    TryCamp(_world, _chunk, cX1Z0, cX0Z1, cX1Z1, _random, origin, x, y, z);
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

    /// <summary>The fisherman's camp on this spot if its whole footprint is flat, dry, empty ground (nothing on it but
    /// grass) and the nearest water in the chunk is 3 to 8 blocks from the middle.</summary>
    private static void TryCamp(World world, Chunk chunk, Chunk cX1Z0, Chunk cX0Z1, Chunk cX1Z1, GameRandom random,
        Vector3i origin, int x, int y, int z)
    {
        try
        {
            int height = campBlock.isMultiBlock ? campBlock.multiBlockPos.dim.y : 1;
            for (int dz = -CampHalf; dz <= CampHalf; dz++)
            {
                for (int dx = -CampHalf; dx <= CampHalf; dx++)
                {
                    int nx = x + dx, nz = z + dz;
                    if (chunk.GetTerrainHeight(nx, nz) != y - 1 || chunk.IsWater(nx, y, nz) || chunk.IsWater(nx, y - 1, nz)
                        || chunk.GetBlockNoDamage(nx, y - 1, nz).isair)
                    {
                        return;
                    }
                    BlockValue here = chunk.GetBlockNoDamage(nx, y, nz);
                    if (!here.isair && !Grass(here.Block))
                    {
                        return;
                    }
                    for (int up = 1; up < height; up++)
                    {
                        if (!chunk.GetBlockNoDamage(nx, y + up, nz).isair)
                        {
                            return;
                        }
                    }
                    EnumDecoAllowed allowed = chunk.GetDecoAllowedAt(nx, nz);
                    if (allowed.IsNothing() || allowed.GetStreetOnly())
                    {
                        return;
                    }
                }
            }
            int water = CampWaterDistance(chunk, x, y, z);
            if (water < CampWaterMin || water > CampWaterMax)
            {
                return;
            }
            Place(world, chunk, cX1Z0, cX0Z1, cX1Z1, random, origin, x, y, z, campBlock, 3);
        }
        catch (System.Exception e)
        {
            Log.Warning("[NatureExpanded] fisherman's camp skipped: " + e.Message);
        }
    }

    /// <summary>The distance (blocks, either axis) to the nearest water in this chunk within CampWaterMax, level with the
    /// ground or a block below it; 0 when there is none.</summary>
    private static int CampWaterDistance(Chunk chunk, int x, int y, int z)
    {
        int best = 0;
        for (int dz = -CampWaterMax; dz <= CampWaterMax; dz++)
        {
            for (int dx = -CampWaterMax; dx <= CampWaterMax; dx++)
            {
                int nx = x + dx, nz = z + dz;
                int d = System.Math.Max(System.Math.Abs(dx), System.Math.Abs(dz));
                if (nx < 0 || nz < 0 || nx > 15 || nz > 15 || (best != 0 && d >= best))
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

    /// <summary>Maybe a willow or cottonwood on this spot: one roll against the chances of the trees whose distance
    /// band holds the spot's nearest water, so the water search only runs for the rare spot that rolls under the
    /// biggest chance.</summary>
    private static void TryBankTree(World world, Chunk chunk, Chunk cX1Z0, Chunk cX0Z1, Chunk cX1Z1, GameRandom random,
        Vector3i origin, int x, int y, int z, ShoreTree[] trees)
    {
        float roll = random.RandomFloat;
        float total = 0f;
        foreach (ShoreTree tree in trees)
        {
            if (tree.Block != null)
            {
                total += tree.Chance;
            }
        }
        if (roll >= total)
        {
            return;
        }
        float distance = BankWaterDistance(chunk, cX1Z0, cX0Z1, cX1Z1, x, z, y - 1);
        if (distance < 0f)
        {
            return;
        }
        float at = 0f;
        foreach (ShoreTree tree in trees)
        {
            if (tree.Block == null)
            {
                continue;
            }
            at += tree.Chance;
            if (roll >= at)
            {
                continue;
            }
            // The roll landed on this tree; it stands only where its own band holds the water
            if (distance >= tree.Min && distance <= tree.Max && Free(chunk, x, y, z, tree.Block))
            {
                Place(world, chunk, cX1Z0, cX0Z1, cX1Z1, random, origin, x, y, z, tree.Block);
            }
            return;
        }
    }

    /// <summary>The distance to the nearest water within TreeReach, over this chunk and the ones next to it on the
    /// +x/+z sides (the others aren't at hand), counting only water at about the ground's own height; -1 when there is
    /// none.</summary>
    private static float BankWaterDistance(Chunk chunk, Chunk cX1Z0, Chunk cX0Z1, Chunk cX1Z1, int x, int z, int ground)
    {
        float best = -1f;
        for (int dz = -TreeReach; dz <= TreeReach; dz++)
        {
            for (int dx = -TreeReach; dx <= TreeReach; dx++)
            {
                int nx = x + dx, nz = z + dz;
                float d = (float)System.Math.Sqrt(dx * dx + dz * dz);
                if (d > TreeReach || (best >= 0f && d >= best))
                {
                    continue;
                }
                Chunk c;
                if (nx < 0 || nz < 0 || nx > 31 || nz > 31)
                {
                    continue;
                }
                if (nx <= 15)
                {
                    c = nz <= 15 ? chunk : cX0Z1;
                }
                else
                {
                    c = nz <= 15 ? cX1Z0 : cX1Z1;
                }
                if (c == null)
                {
                    continue;
                }
                int cx = nx & 15, cz = nz & 15;
                int top = c.GetTerrainHeight(cx, cz);
                if (System.Math.Abs(top - ground) <= TreeHeightDiff && (c.IsWater(cx, top, cz) || c.IsWater(cx, top - 1, cz)))
                {
                    best = d;
                }
            }
        }
        return best;
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
        int x, int y, int z, Block block, int rotations = 7)
    {
        BlockValue value = block.ToBlockValue();
        // Grass blocks are drawn unturned, like vanilla's decorator places them
        if (!Grass(block))
        {
            value.rotation = BiomeBlockDecoration.GetRandomRotation(random.RandomFloat, rotations);
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
        campBlock = Block.GetBlockByName("DementiveNatureCampFishing", false);
        foreach (ShoreTree[] trees in BankTrees.Values)
        {
            foreach (ShoreTree tree in trees)
            {
                tree.Block = Block.GetBlockByName("DementiveNature" + tree.Name, false);
            }
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
