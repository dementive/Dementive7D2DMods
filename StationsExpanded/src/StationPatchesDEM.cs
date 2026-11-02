using HarmonyLib;

/// <summary>
/// Fuel, smelting and tool slots. A station's fuel and smelting run on the server while its window is closed and on
/// the client who has it open, so these patches run on both and only read the station's own block.
/// </summary>
public static class StationPatchesDEM
{
    // ------------------------------------------------------------------ fuel: each piece burns longer

    [HarmonyPatch(typeof(TileEntityWorkstation), nameof(TileEntityWorkstation.GetFuelTime))]
    private static class FuelTime
    {
        private static void Postfix(TileEntityWorkstation __instance, ref float __result)
        {
            __result *= FuelScale(__instance);
        }
    }

    [HarmonyPatch(typeof(TileEntityWorkstation), nameof(TileEntityWorkstation.getFuelTime))]
    private static class FuelTimeLegacy
    {
        private static void Postfix(TileEntityWorkstation __instance, ref float __result)
        {
            __result *= FuelScale(__instance);
        }
    }

    /// <summary>The fuel still waiting in the slots (shown as burn time left, and the cap on catching up after the
    /// chunk was unloaded).</summary>
    [HarmonyPatch(typeof(TileEntityWorkstation), nameof(TileEntityWorkstation.getTotalFuelSeconds))]
    private static class TotalFuel
    {
        private static void Postfix(TileEntityWorkstation __instance, ref float __result)
        {
            __result *= FuelScale(__instance);
        }
    }

    private static float FuelScale(TileEntityWorkstation te)
    {
        StationBonusDEM station = StationBonusDEM.Of(te.blockValue);
        return station != null ? station.FuelTime : 1f;
    }

    // ------------------------------------------------------------------ smelting

    [HarmonyPatch(typeof(TileEntityWorkstation), nameof(TileEntityWorkstation.HandleMaterialInput))]
    private static class Smelting
    {
        private static void Prefix(TileEntityWorkstation __instance, ref float timePassed)
        {
            StationBonusDEM station = StationBonusDEM.Of(__instance.blockValue);
            if (station != null)
            {
                timePassed *= station.SmeltSpeed;
            }
        }
    }

    // ------------------------------------------------------------------ named tools stand in for their vanilla tool

    /// <summary>A tool slot takes one exact item; a named tool also goes in its vanilla tool's slot.</summary>
    [HarmonyPatch(typeof(XUiC_RequiredItemStack), nameof(XUiC_RequiredItemStack.ItemAllowed))]
    private static class ToolSlot
    {
        private static void Postfix(XUiC_RequiredItemStack __instance, ItemStack _stack, ref bool __result)
        {
            if (__result)
            {
                return;
            }
            StationToolDEM tool = StationToolDEM.Of(_stack);
            if (tool != null && __instance.allowedItemClasses.Exists(c => c != null && c.Id == tool.BaseType))
            {
                __result = true;
            }
        }
    }

    /// <summary>Recipes that need a tool check for that exact item; a named tool counts as its vanilla tool.</summary>
    [HarmonyPatch(typeof(XUiC_WorkstationToolGrid), nameof(XUiC_WorkstationToolGrid.HasRequirement))]
    private static class ToolRequirement
    {
        private static void Postfix(XUiC_WorkstationToolGrid __instance, Recipe recipe, ref bool __result)
        {
            if (__result || recipe == null || recipe.craftingToolType <= 0)
            {
                return;
            }
            foreach (ItemStack stack in __instance.GetSlots())
            {
                StationToolDEM tool = StationToolDEM.Of(stack);
                if (tool != null && tool.BaseType == recipe.craftingToolType)
                {
                    __result = true;
                    return;
                }
            }
        }
    }
}
