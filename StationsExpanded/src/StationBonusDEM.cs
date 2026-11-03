using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

/// <summary>
/// A named station's bonuses, read from its block's XML once. Any block can carry them; blocks without them get
/// nothing.
/// <list type="bullet">
/// <item><c>StationCraftTime</c> multiplies crafting time (0.8 = 20% faster).</item>
/// <item><c>StationQualityChance</c>: chance a finished item with quality comes out one level higher (up to 6).</item>
/// <item><c>StationExtraChance</c>: chance a finished craft comes out twice.</item>
/// <item><c>StationFuelTime</c> multiplies how long each piece of fuel burns (2 = twice as long).</item>
/// <item><c>StationSmeltSpeed</c> multiplies smelting speed (1.5 = 50% faster).</item>
/// </list>
/// </summary>
public class StationBonusDEM
{
    public const int MaxQuality = 6;

    public float CraftTime = 1f;
    public float QualityChance;
    public float ExtraChance;
    public float FuelTime = 1f;
    public float SmeltSpeed = 1f;

    // Keyed by the Block itself: block ids come from each world's name mapping, and the block list is rebuilt on
    // every world load. Cleared on world start (Reset) so old worlds' blocks don't pile up.
    private static readonly Dictionary<Block, StationBonusDEM> cache = new Dictionary<Block, StationBonusDEM>();

    public static void Reset()
    {
        cache.Clear();
        StationToolDEM.Reset();
    }

    /// <summary>The bonuses of a block, or null if it has none.</summary>
    public static StationBonusDEM Of(BlockValue blockValue)
    {
        Block block = blockValue.Block;
        if (block == null)
        {
            return null;
        }
        if (!cache.TryGetValue(block, out StationBonusDEM bonus))
        {
            DynamicProperties p = block.Properties;
            bonus = new StationBonusDEM
            {
                CraftTime = Read(p, "StationCraftTime", 1f),
                QualityChance = Read(p, "StationQualityChance", 0f),
                ExtraChance = Read(p, "StationExtraChance", 0f),
                FuelTime = Read(p, "StationFuelTime", 1f),
                SmeltSpeed = Read(p, "StationSmeltSpeed", 1f),
            };
            if (bonus.CraftTime == 1f && bonus.QualityChance <= 0f && bonus.ExtraChance <= 0f && bonus.FuelTime == 1f
                && bonus.SmeltSpeed == 1f)
            {
                bonus = null;
            }
            cache[block] = bonus;
        }
        return bonus;
    }

    internal static float Read(DynamicProperties p, string name, float fallback)
    {
        string value = p.GetString(name);
        return !string.IsNullOrEmpty(value) && float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture,
            out float f) ? f : fallback;
    }

    /// <summary>The quality a finished item comes out at: one level higher on a successful roll.</summary>
    public static int RollQuality(float chance, int quality)
    {
        return chance > 0f && quality > 0 && quality < MaxQuality && Random.value < chance ? quality + 1 : quality;
    }

    /// <summary>Whether a second copy fits in the same stack: a quality anvil or a car battery stacks to one.</summary>
    public static bool FitsTwice(ItemClass item, int count)
    {
        return item != null && item.Stacknumber.Value >= count * 2;
    }

    /// <summary>Whether a finished craft comes out twice: the station's chance and its tools' chances each roll.</summary>
    public static bool RollExtra(StationBonusDEM station, ItemStack[] tools, Recipe recipe)
    {
        if (station != null && station.ExtraChance > 0f && Random.value < station.ExtraChance)
        {
            return true;
        }
        if (tools != null && recipe != null)
        {
            foreach (ItemStack stack in tools)
            {
                StationToolDEM tool = StationToolDEM.Of(stack);
                if (tool != null && tool.ExtraChance > 0f && tool.Applies(recipe) && Random.value < tool.ExtraChance)
                {
                    return true;
                }
            }
        }
        return false;
    }
}

/// <summary>
/// A named station tool, read from its item's XML once. It stands in for its vanilla tool (<c>StationToolBase</c>):
/// it goes in that tool's slot and counts for recipes that need it. Its own bonuses apply to the recipes that need
/// the vanilla tool, or to everything made at the station with <c>StationToolScope</c> "all" (for tools no recipe
/// needs, like the anvil): <c>StationToolCraftTime</c> multiplies crafting time and <c>StationToolExtraChance</c> is
/// the chance a finished craft comes out twice. Like vanilla tools, they only count while the tool sits in the
/// station.
/// </summary>
public class StationToolDEM
{
    public int BaseType;
    public float CraftTime = 1f;
    public float ExtraChance;
    public bool AllRecipes;

    // Keyed by the ItemClass itself, like StationBonusDEM's cache (item ids change between worlds)
    private static readonly Dictionary<ItemClass, StationToolDEM> cache = new Dictionary<ItemClass, StationToolDEM>();

    /// <summary>Recipe name and crafting area to the tool it needs (see ToolType).</summary>
    private static readonly Dictionary<string, int> toolTypes = new Dictionary<string, int>();

    public static void Reset()
    {
        cache.Clear();
        toolTypes.Clear();
    }

    public static StationToolDEM Of(ItemStack stack)
    {
        return stack == null || stack.IsEmpty() ? null : Of(stack.itemValue.ItemClass);
    }

    public static StationToolDEM Of(ItemClass item)
    {
        if (item == null)
        {
            return null;
        }
        if (!cache.TryGetValue(item, out StationToolDEM tool))
        {
            string baseName = item.Properties.GetString("StationToolBase");
            ItemClass baseItem = string.IsNullOrEmpty(baseName) ? null : ItemClass.GetItemClass(baseName);
            tool = baseItem == null ? null : new StationToolDEM
            {
                BaseType = baseItem.Id,
                CraftTime = StationBonusDEM.Read(item.Properties, "StationToolCraftTime", 1f),
                ExtraChance = StationBonusDEM.Read(item.Properties, "StationToolExtraChance", 0f),
                AllRecipes = item.Properties.GetString("StationToolScope") == "all",
            };
            cache[item] = tool;
        }
        return tool;
    }

    public bool Applies(Recipe recipe)
    {
        return AllRecipes || ToolType(recipe) == BaseType;
    }

    /// <summary>
    /// The tool a recipe needs. A queued recipe that was saved or sent over the network comes back without it (Recipe
    /// and RecipeQueueItem don't write craftingToolType), so it's looked up from the game's recipes by name and
    /// crafting area, which are kept.
    /// </summary>
    public static int ToolType(Recipe recipe)
    {
        if (recipe.craftingToolType > 0)
        {
            return recipe.craftingToolType;
        }
        string key = recipe.GetName() + "|" + recipe.craftingArea;
        if (!toolTypes.TryGetValue(key, out int type))
        {
            type = 0;
            List<Recipe> recipes = CraftingManager.GetRecipes(recipe.GetName());
            if (recipes != null)
            {
                foreach (Recipe r in recipes)
                {
                    if (r.craftingToolType > 0 && string.Equals(r.craftingArea ?? "", recipe.craftingArea ?? "",
                        System.StringComparison.OrdinalIgnoreCase))
                    {
                        type = r.craftingToolType;
                        break;
                    }
                }
            }
            toolTypes[key] = type;
        }
        return type;
    }

    /// <summary>The crafting time multiplier of the tools in a station for one recipe.</summary>
    public static float CraftTimeFor(ItemStack[] tools, Recipe recipe)
    {
        float time = 1f;
        if (tools != null && recipe != null)
        {
            foreach (ItemStack stack in tools)
            {
                StationToolDEM tool = Of(stack);
                if (tool != null && tool.Applies(recipe))
                {
                    time *= tool.CraftTime;
                }
            }
        }
        return time;
    }
}
