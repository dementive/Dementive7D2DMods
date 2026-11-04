using System.Collections.Generic;
using System.Text;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// A short status under a workstation's use prompt: what it's making, how many are left and how long the next one
/// takes, or Idle; and for stations that burn fuel, how long the loaded fuel lasts.
///
/// Runs on the looking player's game, from its copy of the station (TileEntityWorkstation). While nobody has a
/// station open, the server works its queue and fuel once a second and sends the whole station (queue, time left on
/// the current item, fuel, burn time) to the clients near it, so a client's copy is right to the second. While
/// someone has it open, their game does the crafting and only sends the queue when crafting starts or stops
/// (XUiC_WorkstationWindowGroup.syncTEfromUI), so everyone else's copy of the queue is stale; fuel still updates. A
/// full output or an unlit fire stops the clock as well. So the time left is shown only while it's really running:
/// the fire is lit (or the station has no fuel), the time is above 0, and nobody has the station open. Only the
/// server knows that last part (LockManager), so a client asks it about the station it's looking at, about once a
/// second (NetPackageStationOpenDEM). When it's stopped the line shows the item and count without a time, and when
/// someone has the station open, only the item. Tools aren't shown: clients don't get them in the same copy
/// (toolsNet).
/// </summary>
public static class StationStatusDEM
{
    /// <summary>How often a client asks the server whether the station it's looking at is open.</summary>
    private const float AskSeconds = 1f;

    /// <summary>How long a client trusts the server's last answer.</summary>
    private const float AnswerSeconds = 3f;

    private class OpenState
    {
        public bool Open;
        public float Asked = float.MinValue;
        public float Answered = float.MinValue;
    }

    /// <summary>A client's answers from the server, by station position (only the stations it looked at).</summary>
    private static readonly Dictionary<Vector3i, OpenState> openStations = new Dictionary<Vector3i, OpenState>();

    /// <summary>A new world: the old answers are about another one.</summary>
    public static void Reset()
    {
        openStations.Clear();
    }

    [HarmonyPatch(typeof(BlockWorkstation), nameof(BlockWorkstation.GetActivationText))]
    private static class WorkstationText
    {
        private static void Postfix(WorldBase _world, Vector3i _blockPos, ref string __result)
        {
            __result = WithStatus(__result, _world, _blockPos);
        }
    }

    /// <summary>The forge has its own text (BlockCampfire uses the workstation's).</summary>
    [HarmonyPatch(typeof(BlockForge), nameof(BlockForge.GetActivationText))]
    private static class ForgeText
    {
        private static void Postfix(WorldBase _world, Vector3i _blockPos, ref string __result)
        {
            __result = WithStatus(__result, _world, _blockPos);
        }
    }

    /// <summary>The caller has already turned a multi-block's child into its parent block, where the station
    /// is.</summary>
    private static string WithStatus(string text, WorldBase world, Vector3i pos)
    {
        try
        {
            if (string.IsNullOrEmpty(text) || !(world?.GetTileEntity(pos) is TileEntityWorkstation te))
            {
                return text;
            }
            string status = Status(te);
            // The caller runs the text through string.Format for the use key, so braces in names are escaped
            return string.IsNullOrEmpty(status) ? text : text + "\n" + status.Replace("{", "{{").Replace("}", "}}");
        }
        catch (System.Exception e)
        {
            Log.Warning("[StationsExpanded] Station status: " + e);
            return text;
        }
    }

    public static string Status(TileEntityWorkstation te)
    {
        // The station works on the last queue slot and moves the others up when it's done
        // (TileEntityWorkstation.HandleRecipeQueue, cycleRecipeQueue)
        RecipeQueueItem current = null;
        int more = 0;
        RecipeQueueItem[] queue = te.queue;
        if (queue != null)
        {
            for (int i = queue.Length - 1; i >= 0; i--)
            {
                RecipeQueueItem q = queue[i];
                if (q?.Recipe == null || q.Multiplier <= 0)
                {
                    continue;
                }
                if (current == null)
                {
                    current = q;
                }
                else
                {
                    more++;
                }
            }
        }
        bool[] modules = te.isModuleUsed;
        bool usesFuel = modules != null && modules.Length > (int)TileEntityWorkstation.Module.Fuel
            && modules[(int)TileEntityWorkstation.Module.Fuel];

        StringBuilder text = new StringBuilder();
        if (current != null)
        {
            ItemClass item = ItemClass.GetForId(current.Recipe.itemValueType);
            string name = item != null ? item.GetLocalizedItemName() : current.Recipe.GetName();
            // Multiplier is the crafts left in the slot, counting the one in progress; CraftingTimeLeft is the time
            // left on that one
            int count = current.Multiplier * Mathf.Max(1, current.Recipe.count);
            bool? open = OpenByAnyone(te);
            string making;
            if (open == true)
            {
                // Its queue here is as of when they started crafting: only the item is sure
                making = string.Format(Localization.Get("DementiveStationStatusInUse"), name);
            }
            else if (open == false && current.CraftingTimeLeft > 0f && (!usesFuel || te.IsBurning))
            {
                making = string.Format(Localization.Get("DementiveStationStatusCrafting"), name, count,
                    Duration(current.CraftingTimeLeft));
            }
            else
            {
                making = string.Format(Localization.Get("DementiveStationStatusCraftingPaused"), name, count);
            }
            text.Append(more > 0
                ? string.Format(Localization.Get("DementiveStationStatusMore"), making, more) : making);
        }
        else
        {
            text.Append(Localization.Get("DementiveStationStatusIdle"));
        }

        if (usesFuel)
        {
            // The burning piece plus the fuel slots, with the station's fuel bonus (StationPatchesDEM)
            float fuel = te.BurnTotalTimeLeft;
            if (fuel > 0f)
            {
                text.Append('\n').Append(string.Format(
                    Localization.Get(te.IsBurning ? "DementiveStationStatusFuel" : "DementiveStationStatusFuelOff"),
                    Duration(fuel)));
            }
            else if (current != null)
            {
                // A fuel station doesn't craft while it's out
                text.Append('\n').Append(Localization.Get("DementiveStationStatusNoFuel"));
            }
        }
        return text.ToString();
    }

    /// <summary>
    /// Whether someone has the station open (station windows lock it on channel 0, BlockWorkstation.OnBlockActivated).
    /// The server checks its locks; a client asks the server, and doesn't know (null) until a recent answer is in.
    /// </summary>
    private static bool? OpenByAnyone(TileEntityWorkstation te)
    {
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return LockManager.Instance.IsLockedServer(te);
        }
        Vector3i pos = te.ToWorldPos();
        if (!openStations.TryGetValue(pos, out OpenState state))
        {
            openStations[pos] = state = new OpenState();
        }
        if (Time.time - state.Asked >= AskSeconds)
        {
            state.Asked = Time.time;
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageStationOpenDEM>().Setup(pos));
        }
        return Time.time - state.Answered > AnswerSeconds ? (bool?)null : state.Open;
    }

    /// <summary>The server's answer (client only).</summary>
    internal static void Answer(Vector3i pos, bool open)
    {
        if (openStations.TryGetValue(pos, out OpenState state))
        {
            state.Open = open;
            state.Answered = Time.time;
        }
    }

    /// <summary>m:ss, or h:mm:ss from an hour (rounded up, so it reads 0:01 until it's done).</summary>
    private static string Duration(float seconds)
    {
        int s = Mathf.CeilToInt(Mathf.Max(0f, seconds));
        return s >= 3600 ? string.Format("{0}:{1:00}:{2:00}", s / 3600, s / 60 % 60, s % 60)
            : string.Format("{0}:{1:00}", s / 60, s % 60);
    }
}

/// <summary>Client to server: does someone have the station at this position open?</summary>
public class NetPackageStationOpenDEM : NetPackage
{
    private Vector3i pos;

    public NetPackageStationOpenDEM Setup(Vector3i _pos)
    {
        pos = _pos;
        return this;
    }

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToServer;

    public override void read(PooledBinaryReader _reader)
    {
        pos = StreamUtils.ReadVector3i(_reader);
    }

    public override void write(PooledBinaryWriter _writer)
    {
        base.write(_writer);
        StreamUtils.Write(_writer, pos);
    }

    /// <summary>On the server.</summary>
    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null || Sender == null)
        {
            return;
        }
        bool open = _world.GetTileEntity(pos) is TileEntityWorkstation te && LockManager.Instance.IsLockedServer(te);
        Sender.SendPackage(NetPackageManager.GetPackage<NetPackageStationOpenReplyDEM>().Setup(pos, open));
    }
}

/// <summary>Server to client: whether someone has the station open.</summary>
public class NetPackageStationOpenReplyDEM : NetPackage
{
    private Vector3i pos;
    private bool open;

    public NetPackageStationOpenReplyDEM Setup(Vector3i _pos, bool _open)
    {
        pos = _pos;
        open = _open;
        return this;
    }

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public override void read(PooledBinaryReader _reader)
    {
        pos = StreamUtils.ReadVector3i(_reader);
        open = _reader.ReadBoolean();
    }

    public override void write(PooledBinaryWriter _writer)
    {
        base.write(_writer);
        StreamUtils.Write(_writer, pos);
        _writer.Write(open);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        StationStatusDEM.Answer(pos, open);
    }
}
