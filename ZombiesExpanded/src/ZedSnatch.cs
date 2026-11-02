using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The Snatcher's theft. Each player's inventory lives on their own game, so the server asks the victim's game to
/// take the held item out (NetPackageZedSnatch) and that game hands it back (NetPackageZedStolen). The server only
/// takes an answer it asked for, once. The Snatcher carries the item (kept with its profile on the server, and saved
/// with it) until it's killed (it drops it) or gets away (it's gone, and so is the item).
/// </summary>
public static class ZedSnatch
{
    /// <summary>Server: grabs waiting for the victim's game to answer (Snatcher id to victim id).</summary>
    private static readonly Dictionary<int, int> pending = new Dictionary<int, int>();

    public static bool Pending(int zombieId) => pending.ContainsKey(zombieId);

    public static void Clear()
    {
        pending.Clear();
    }

    /// <summary>Server: whether it can reach what `player` is holding: within 1.8 m, on the same level, nothing
    /// solid in between.</summary>
    public static bool InReach(EntityAlive z, EntityPlayer player)
    {
        Vector3 d = player.position - z.position;
        if (Mathf.Abs(d.y) > 1.2f || new Vector2(d.x, d.z).magnitude > 1.8f)
        {
            return false;
        }
        Vector3 from = z.getHeadPosition();
        Vector3 to = player.getHeadPosition() - from;
        float dist = to.magnitude;
        return dist < 0.4f || !Voxel.Raycast(z.world, new Ray(from, to / dist), dist - 0.3f, false, false);
    }

    /// <summary>Server: grab whatever `player` is holding.</summary>
    public static void Grab(EntityAlive z, EntityPlayer player)
    {
        ZedBrain brain = ZedBrain.Of(z);
        if (brain == null || pending.ContainsKey(z.entityId))
        {
            return;
        }
        pending[z.entityId] = player.entityId;
        brain.Waiting = Time.time;
        if (player is EntityPlayerLocal local)
        {
            Stolen(z.entityId, player.entityId, Take(local));
            return;
        }
        ClientInfo client = SingletonMonoBehaviour<ConnectionManager>.Instance.Clients.ForEntityId(player.entityId);
        client?.SendPackage(NetPackageManager.GetPackage<NetPackageZedSnatch>().Setup(z.entityId));
    }

    /// <summary>Whether a player has something in hand to take (not while they're in a vehicle).</summary>
    public static bool Holding(EntityPlayer player)
    {
        if (player.AttachedToEntity != null)
        {
            return false;
        }
        ItemStack s = player.inventory?.holdingItemStack;
        return s != null && !s.IsEmpty();
    }

    /// <summary>The victim's game: takes the held item out of the toolbelt and says so. Only what's really in hand
    /// in the selected slot (not an item being used from the backpack, not in a vehicle).</summary>
    public static ItemStack Take(EntityPlayerLocal player)
    {
        Inventory inv = player.inventory;
        int idx = inv.holdingItemIdx;
        ItemStack held = inv.holdingItemStack;
        ItemStack slot = inv.GetItem(idx);
        if (player.AttachedToEntity != null || held == null || held.IsEmpty() || slot == null || slot.IsEmpty()
            || slot.itemValue.type != held.itemValue.type)
        {
            return ItemStack.Empty.Clone();
        }
        held = slot;
        ItemStack stolen = held.Clone();
        inv.SetItem(idx, ItemStack.Empty.Clone());
        string name = stolen.itemValue.ItemClass?.GetLocalizedItemName() ?? "";
        GameManager.ShowTooltip(player, string.Format(Localization.Get("zedSnatched"), name), false, false, 6f);
        return stolen;
    }

    /// <summary>Server: the victim's game handed the item over (only an answer to a grab the server asked for). If
    /// the Snatcher is gone by now, or somehow already carries something, it falls at the victim's feet.</summary>
    public static void Stolen(int zombieId, int playerId, ItemStack stack)
    {
        if (!pending.TryGetValue(zombieId, out int victim) || victim != playerId)
        {
            return;
        }
        pending.Remove(zombieId);
        World world = GameManager.Instance.World;
        EntityAlive z = world?.GetEntity(zombieId) as EntityAlive;
        ZedBrain brain = ZedBrain.Of(z);
        ZedProfile p = ZedStore.Get(zombieId);
        bool empty = stack == null || stack.IsEmpty();
        if (z == null || z.IsDead() || brain == null || p == null || (!empty && ZedStore.Loot(zombieId) != null))
        {
            if (!empty && world?.GetEntity(playerId) is Entity player)
            {
                GameManager.Instance.ItemDropServer(stack, player.position + Vector3.up, Vector3.zero, -1, 1200f, false);
            }
            return;
        }
        brain.Waiting = -1f;
        if (empty)
        {
            // Nothing came of it: a moment before it tries again
            brain.SnatchAgain = Time.time + 2f;
            return;
        }
        ZedStore.SetLoot(zombieId, stack);
        p.Carrying = true;
        Audio.Manager.BroadcastPlay(z, "zombiefemalescoutalert");
        ZedStore.Changed(z);
    }

    /// <summary>Server: it died with the item: it falls where it lies.</summary>
    public static void Drop(EntityAlive z)
    {
        ItemStack loot = ZedStore.Loot(z.entityId);
        if (loot == null || loot.IsEmpty())
        {
            return;
        }
        GameManager.Instance.ItemDropServer(loot, z.getChestPosition(), Vector3.zero, -1, 1200f, false);
        ZedStore.SetLoot(z.entityId, null);
    }
}

/// <summary>
/// The Snatcher's AI, while it has a player to rob (it holds the movement the whole time, so the game's own attack
/// never runs: it never hits anyone). Empty-handed, it goes for a player holding something and grabs it at arm's
/// length; if they're holding nothing it hangs about 5 to 9 m off, waiting. Carrying, it runs from them. Getting
/// away (ZedBrain) is 60 m from every player, or 20 s out of everyone's sight.
/// </summary>
public class EAIZedSnatch : EAIBase
{
    private EntityPlayer target;
    private float repath;

    public override void Init(EntityAlive _theEntity)
    {
        base.Init(_theEntity);
        MutexBits = 3;
        executeDelay = 0.1f;
    }

    private ZedProfile Profile => ZedStore.Get(theEntity.entityId);

    public override bool CanExecute()
    {
        ZedProfile p = Profile;
        if (p == null || !p.Has(ZedMutation.Snatcher))
        {
            return false;
        }
        target = theEntity.GetAttackTarget() as EntityPlayer;
        return target != null && !target.IsDead();
    }

    public override void Start()
    {
        repath = 0f;
    }

    public override bool Continue()
    {
        return target != null && !target.IsDead() && theEntity.GetAttackTarget() == target;
    }

    public override void Update()
    {
        ZedProfile p = Profile;
        ZedBrain brain = ZedBrain.Of(theEntity);
        if (p == null || brain == null || target == null)
        {
            return;
        }
        float now = Time.time;
        if (ZedSnatch.Pending(theEntity.entityId) && now - brain.Waiting < 10f)
        {
            // Waiting for the player's game to hand it over
            theEntity.moveHelper.Stop();
            return;
        }
        Vector3 away = theEntity.position - target.position;
        away.y = 0f;
        float d = away.magnitude;
        if (p.Carrying)
        {
            Run(away, 12f, now);
            return;
        }
        if (ZedSnatch.Holding(target))
        {
            if (now >= brain.SnatchAgain && !ZedSnatch.Pending(theEntity.entityId) && ZedSnatch.InReach(theEntity, target))
            {
                theEntity.SetLookPosition(target.getHeadPosition());
                ZedSnatch.Grab(theEntity, target);
                return;
            }
            Go(target.position, now, 0.5f);
            return;
        }
        // Nothing to take yet: it hangs about out of reach, watching
        if (d < 5f)
        {
            Run(away, 6f, now);
        }
        else if (d > 9f)
        {
            Go(target.position + away / Mathf.Max(d, 0.01f) * 7f, now, 1f);
        }
        else
        {
            theEntity.navigator?.clearPath();
            theEntity.moveHelper.Stop();
            theEntity.SetLookPosition(target.getHeadPosition());
        }
    }

    private void Go(Vector3 spot, float now, float every)
    {
        if (now < repath)
        {
            return;
        }
        repath = now + every;
        theEntity.FindPath(spot, theEntity.GetMoveSpeedAggro(), false, this);
    }

    private void Run(Vector3 away, float leg, float now)
    {
        if (now < repath)
        {
            return;
        }
        repath = now + 1f;
        if (away.sqrMagnitude < 0.01f)
        {
            away = -theEntity.transform.forward;
        }
        Vector3 spot = RandomPositionGenerator.CalcPositionInDirection(theEntity, theEntity.position, away.normalized, leg, 80f);
        if (spot.y != 0f)
        {
            theEntity.FindPath(spot, theEntity.GetMoveSpeedAggro(), false, this);
        }
    }

    public override void Reset()
    {
        theEntity.navigator?.clearPath();
    }
}

/// <summary>Server to the victim's game: a Snatcher grabs what you're holding.</summary>
public class NetPackageZedSnatch : NetPackage
{
    private int zombieId;

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public NetPackageZedSnatch Setup(int _zombieId)
    {
        zombieId = _zombieId;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        zombieId = _br.ReadInt32();
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(zombieId);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        EntityPlayerLocal player = _world?.GetPrimaryPlayer();
        if (player == null || player.IsDead())
        {
            return;
        }
        ItemStack stolen = ZedSnatch.Take(player);
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
            NetPackageManager.GetPackage<NetPackageZedStolen>().Setup(zombieId, player.entityId, stolen));
    }
}

/// <summary>The victim's game to the server: here's what the Snatcher took (empty if nothing).</summary>
public class NetPackageZedStolen : NetPackage
{
    private int zombieId;
    private int playerId;
    private ItemStack stack;

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToServer;

    public NetPackageZedStolen Setup(int _zombieId, int _playerId, ItemStack _stack)
    {
        zombieId = _zombieId;
        playerId = _playerId;
        stack = _stack;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        zombieId = _br.ReadInt32();
        playerId = _br.ReadInt32();
        stack = new ItemStack().Read(_br);
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(zombieId);
        _bw.Write(playerId);
        (stack ?? ItemStack.Empty.Clone()).Write(_bw);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world != null && Sender != null && Sender.entityId == playerId)
        {
            ZedSnatch.Stolen(zombieId, playerId, stack);
        }
    }
}
