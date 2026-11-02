using HarmonyLib;

/// <summary>
/// Where named stations' and tools' bonuses go into the game's crafting.
///
/// Crafting time is worked out by the client of the player who queues a craft (from their perks, the recipe and the
/// tools in the open window) and stored in the queue, so station and tool speed are applied there, while the window
/// is open. Finished items are made in one of two places: by that client while the window is open
/// (XUiC_RecipeStack.outputStack), or by the server while it's closed (TileEntityWorkstation.HandleRecipeQueue, which
/// always finishes the last queue slot). The quality and extra-item rolls are applied in both, once per finished
/// craft.
/// </summary>
public static class CraftingPatchesDEM
{
    /// <summary>The named station whose window this client has open, if any.</summary>
    private static StationBonusDEM openStation;

    /// <summary>Set while the server finishes queued crafts for a station that has bonuses or tools with them.</summary>
    [System.ThreadStatic]
    private static TileEntityWorkstation finishing;

    /// <summary>Before the window's children open, so the info panel shows the station's crafting times at once (the
    /// station's block is set just before the window opens).</summary>
    [HarmonyPatch(typeof(XUiC_WorkstationWindowGroup), nameof(XUiC_WorkstationWindowGroup.OnOpen))]
    private static class WindowOpen
    {
        private static void Prefix(XUiC_WorkstationWindowGroup __instance)
        {
            openStation = StationBonusDEM.Of(__instance.workstationBlock);
        }
    }

    [HarmonyPatch(typeof(XUiC_WorkstationWindowGroup), nameof(XUiC_WorkstationWindowGroup.OnClose))]
    private static class WindowClose
    {
        private static void Postfix()
        {
            openStation = null;
        }
    }

    /// <summary>Crafting time shown in the window and stored in the queue.</summary>
    [HarmonyPatch(typeof(XUiM_Recipes), nameof(XUiM_Recipes.GetRecipeCraftTime))]
    private static class CraftTime
    {
        private static void Postfix(XUi xui, Recipe _recipe, ref float __result)
        {
            if (openStation != null)
            {
                __result *= openStation.CraftTime;
            }
            XUiC_WorkstationToolGrid tools = xui?.CurrentWorkstationToolGrid;
            if (tools != null)
            {
                __result *= StationToolDEM.CraftTimeFor(tools.GetSlots(), _recipe);
            }
        }
    }

    /// <summary>Window open: this client makes the craft from the stack's recipe count and output quality.</summary>
    [HarmonyPatch(typeof(XUiC_RecipeStack), nameof(XUiC_RecipeStack.outputStack))]
    private static class OutputStack
    {
        private struct State
        {
            public int Quality;
            public int Count;
        }

        private static void Prefix(XUiC_RecipeStack __instance, out State __state)
        {
            __state = new State { Quality = -1, Count = -1 };
            // Repairs hand back the item being repaired; only new crafts roll
            if (!(__instance.windowGroup?.Controller is XUiC_WorkstationWindowGroup group) || __instance.recipe == null
                || (__instance.originalItem != null && !__instance.originalItem.IsEmpty()))
            {
                return;
            }
            StationBonusDEM station = StationBonusDEM.Of(group.workstationBlock);
            ItemStack[] tools = group.toolWindow?.GetSlots();
            ItemClass item = ItemClass.GetForId(__instance.recipe.itemValueType);
            if (station != null && item != null && item.HasQuality)
            {
                int quality = StationBonusDEM.RollQuality(station.QualityChance, __instance.outputQuality);
                if (quality != __instance.outputQuality)
                {
                    __state.Quality = __instance.outputQuality;
                    __instance.outputQuality = quality;
                }
            }
            if (StationBonusDEM.RollExtra(station, tools, __instance.recipe))
            {
                __state.Count = __instance.recipe.count;
                __instance.recipe.count *= 2;
            }
        }

        private static void Postfix(XUiC_RecipeStack __instance, State __state)
        {
            if (__state.Quality >= 0)
            {
                __instance.outputQuality = __state.Quality;
            }
            if (__state.Count >= 0)
            {
                __instance.recipe.count = __state.Count;
            }
        }
    }

    /// <summary>Window closed: the server finishes queued crafts into the station's output.</summary>
    [HarmonyPatch(typeof(TileEntityWorkstation), nameof(TileEntityWorkstation.HandleRecipeQueue))]
    private static class RecipeQueue
    {
        private static void Prefix(TileEntityWorkstation __instance)
        {
            finishing = __instance;
        }

        private static void Finalizer()
        {
            finishing = null;
        }
    }

    /// <summary>Each craft the server adds to a station's output gets its own rolls.</summary>
    [HarmonyPatch(typeof(ItemStack), nameof(ItemStack.AddToItemStackArray))]
    private static class AddToOutput
    {
        private static void Prefix(ItemStack _itemStack)
        {
            TileEntityWorkstation te = finishing;
            if (te == null || _itemStack == null || _itemStack.IsEmpty() || te.queue == null || te.queue.Length == 0)
            {
                return;
            }
            StationBonusDEM station = StationBonusDEM.Of(te.blockValue);
            Recipe recipe = te.queue[te.queue.Length - 1]?.Recipe;
            ItemValue item = _itemStack.itemValue;
            if (station != null && item.HasQuality)
            {
                int quality = StationBonusDEM.RollQuality(station.QualityChance, item.Quality);
                if (quality != item.Quality)
                {
                    _itemStack.itemValue = new ItemValue(item.type, quality, quality, false, null, 1f);
                }
            }
            if (StationBonusDEM.RollExtra(station, te.tools, recipe))
            {
                _itemStack.count *= 2;
            }
        }
    }
}
