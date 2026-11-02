using System.Collections.Generic;
using UnityEngine;

/// <summary>Kill thresholds and what each trap level is worth.</summary>
public static class TrapLevelsDEM
{
    /// <summary>Kills needed for levels 2 to 5 (every trap starts at level 1).</summary>
    public static readonly int[] Thresholds = { 25, 75, 150, 300 };

    public const int MaxLevel = 5;

    /// <summary>The level at which a trap's owner picks upgrade A or B.</summary>
    public const int UpgradeLevel = 3;

    public static int Level(int kills)
    {
        int level = 1;
        foreach (int t in Thresholds)
        {
            if (kills >= t)
            {
                level++;
            }
        }
        return level;
    }

    /// <summary>Kills needed for the next level, or -1 at the top.</summary>
    public static int NextAt(int level)
    {
        return level < MaxLevel ? Thresholds[level - 1] : -1;
    }

    /// <summary>+8% damage per level above 1.</summary>
    public static float Damage(int level)
    {
        return 1f + 0.08f * (level - 1);
    }

    /// <summary>+5% attack speed per level above 1 (divide delays by this).</summary>
    public static float Speed(int level)
    {
        return 1f + 0.05f * (level - 1);
    }

    /// <summary>Status traps: +10% status duration per level above 1.</summary>
    public static float Duration(int level)
    {
        return 1f + 0.1f * (level - 1);
    }
}

public class TrapAmmoDEM
{
    public string Item;
    public int Count;

    public TrapAmmoDEM(string item, int count)
    {
        Item = item;
        Count = count;
    }
}

/// <summary>What the server remembers about one placed trap: its kills (level), chosen upgrade and loaded ammo.</summary>
public class TrapRecordDEM
{
    public string Block = "";
    /// <summary>The player who placed it (damage and kills are credited to them, like vanilla traps), or -1.</summary>
    public int Owner = -1;
    public int Kills;
    public byte Upgrade;
    /// <summary>How much of the first ammo item is already used up (fuel burns in fractions).</summary>
    public float Burn;
    public readonly List<TrapAmmoDEM> Ammo = new List<TrapAmmoDEM>();

    public int Level => TrapLevelsDEM.Level(Kills);

    public bool Has(char upgrade)
    {
        return Upgrade == (byte)upgrade;
    }

    public int AmmoTotal
    {
        get
        {
            int n = 0;
            foreach (TrapAmmoDEM a in Ammo)
            {
                n += a.Count;
            }
            return n;
        }
    }

    public string CurrentAmmo => Ammo.Count > 0 ? Ammo[0].Item : null;

    /// <summary>Uses `amount` of the first loaded item (a fraction for fuel). False when empty.</summary>
    public bool UseAmmo(float amount, out string item)
    {
        item = null;
        if (Ammo.Count == 0)
        {
            return false;
        }
        item = Ammo[0].Item;
        Burn += amount;
        while (Burn >= 0.999f && Ammo.Count > 0)
        {
            Burn -= 1f;
            Ammo[0].Count--;
            if (Ammo[0].Count <= 0)
            {
                Ammo.RemoveAt(0);
            }
        }
        if (Ammo.Count == 0 || Burn < 0f)
        {
            Burn = 0f;
        }
        return true;
    }

    /// <summary>Loads up to `count` of an item without going over capacity. Returns how many went in.</summary>
    public int AddAmmo(string item, int count, int capacity)
    {
        int room = Mathf.Max(0, capacity - AmmoTotal);
        int n = Mathf.Min(room, count);
        if (n <= 0)
        {
            return 0;
        }
        TrapAmmoDEM last = Ammo.Count > 0 ? Ammo[Ammo.Count - 1] : null;
        if (last != null && last.Item == item)
        {
            last.Count += n;
        }
        else
        {
            Ammo.Add(new TrapAmmoDEM(item, n));
        }
        return n;
    }

    public void Write(System.IO.BinaryWriter w)
    {
        w.Write(Block ?? "");
        w.Write(Owner);
        w.Write(Kills);
        w.Write(Upgrade);
        w.Write(Burn);
        int count = Mathf.Min(Ammo.Count, 255);
        w.Write((byte)count);
        for (int i = 0; i < count; i++)
        {
            w.Write(Ammo[i].Item ?? "");
            w.Write(Ammo[i].Count);
        }
    }

    /// <summary>A copy (for a package, written later on the network thread while the trap keeps using ammo).</summary>
    public TrapRecordDEM Copy()
    {
        TrapRecordDEM c = new TrapRecordDEM { Block = Block, Owner = Owner, Kills = Kills, Upgrade = Upgrade, Burn = Burn };
        foreach (TrapAmmoDEM a in Ammo)
        {
            c.Ammo.Add(new TrapAmmoDEM(a.Item, a.Count));
        }
        return c;
    }

    public static TrapRecordDEM Read(System.IO.BinaryReader r)
    {
        TrapRecordDEM rec = new TrapRecordDEM
        {
            Block = r.ReadString(),
            Owner = r.ReadInt32(),
            Kills = r.ReadInt32(),
            Upgrade = r.ReadByte(),
            Burn = r.ReadSingle()
        };
        int count = r.ReadByte();
        for (int i = 0; i < count; i++)
        {
            string item = r.ReadString();
            int n = r.ReadInt32();
            if (n > 0)
            {
                rec.Ammo.Add(new TrapAmmoDEM(item, n));
            }
        }
        return rec;
    }
}

/// <summary>
/// The server's records of every placed trap, saved in the world's save folder. Clients see a copy of a trap's
/// record while they look at it (requested from the server every couple of seconds) and send their commands (load,
/// unload, upgrade, re-arm, light) to the server, which does them and replies with the new state.
/// </summary>
public static class TrapStoreDEM
{
    private const int Version = 1;
    private const float SaveInterval = 30f;

    private static readonly Dictionary<Vector3i, TrapRecordDEM> records = new Dictionary<Vector3i, TrapRecordDEM>();
    private static readonly TrapSaveFileDEM file = new TrapSaveFileDEM("traps.dat");
    private static bool dirty;
    private static float saveTimer;
    private static int checkedFrame = -1;

    private class Cached
    {
        public TrapRecordDEM Record;
        public float Received = -100f;
        public float Requested = -100f;
    }

    private static readonly Dictionary<Vector3i, Cached> cache = new Dictionary<Vector3i, Cached>();

    public static bool IsServer => SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer;

    // ------------------------------------------------------------------ server

    private static void EnsureLoaded()
    {
        // Working out the save folder builds strings: once a frame is plenty
        if (Time.frameCount == checkedFrame)
        {
            return;
        }
        checkedFrame = Time.frameCount;
        if (!file.NeedsLoad())
        {
            return;
        }
        records.Clear();
        dirty = false;
        file.Load(r =>
        {
            int version = r.ReadInt32();
            if (version != Version)
            {
                return;
            }
            int count = r.ReadInt32();
            for (int i = 0; i < count; i++)
            {
                Vector3i pos = new Vector3i(r.ReadInt32(), r.ReadInt32(), r.ReadInt32());
                records[pos] = TrapRecordDEM.Read(r);
            }
        });
    }

    public static void Save()
    {
        if (!IsServer || file.NeedsLoad())
        {
            return;
        }
        dirty = false;
        saveTimer = 0f;
        file.Save(w =>
        {
            w.Write(Version);
            w.Write(records.Count);
            foreach (KeyValuePair<Vector3i, TrapRecordDEM> kv in records)
            {
                w.Write(kv.Key.x);
                w.Write(kv.Key.y);
                w.Write(kv.Key.z);
                kv.Value.Write(w);
            }
        });
    }

    /// <summary>Server: the record of the trap at pos, made if it has none yet (or if another block is there now).</summary>
    public static TrapRecordDEM Get(Vector3i pos, string blockName)
    {
        EnsureLoaded();
        if (!records.TryGetValue(pos, out TrapRecordDEM rec) || rec.Block != blockName)
        {
            rec = new TrapRecordDEM { Block = blockName };
            records[pos] = rec;
            dirty = true;
        }
        return rec;
    }

    /// <summary>Server: the trap's record if it has one.</summary>
    public static TrapRecordDEM Find(Vector3i pos)
    {
        EnsureLoaded();
        records.TryGetValue(pos, out TrapRecordDEM rec);
        return rec;
    }

    /// <summary>Server: a record changed. Players nearby get the new state if `tell` is set.</summary>
    public static void Changed(Vector3i pos, bool tell = false)
    {
        dirty = true;
        if (!tell || !records.TryGetValue(pos, out TrapRecordDEM rec))
        {
            return;
        }
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
            NetPackageManager.GetPackage<NetPackageTrapStateDEM>().Setup(pos, rec.Copy()),
            _entitiesInRangeOfWorldPos: pos.ToVector3(), _range: 64);
    }

    /// <summary>Server: the trap at pos is gone (picked up or destroyed). Its loaded ammo drops on the ground.</summary>
    public static void Removed(World world, Vector3i pos)
    {
        if (!IsServer || world == null)
        {
            return;
        }
        EnsureLoaded();
        if (!records.TryGetValue(pos, out TrapRecordDEM rec))
        {
            return;
        }
        records.Remove(pos);
        dirty = true;
        Vector3 at = pos.ToVector3() + new Vector3(0.5f, 0.75f, 0.5f);
        foreach (TrapAmmoDEM a in rec.Ammo)
        {
            Drop(a.Item, a.Count, at, -1);
        }
    }

    private static void Drop(string item, int count, Vector3 at, int entityId)
    {
        ItemValue iv = ItemClass.GetItem(item);
        if (iv == null || iv.IsEmpty() || count <= 0)
        {
            return;
        }
        int stack = Mathf.Max(1, iv.ItemClass.Stacknumber.Value);
        while (count > 0)
        {
            int n = Mathf.Min(count, stack);
            count -= n;
            GameManager.Instance.ItemDropServer(new ItemStack(iv, n), at, new Vector3(0.3f, 0f, 0.3f), entityId, 600f);
        }
    }

    /// <summary>Every game update: saves the server's records now and then.</summary>
    public static void Update()
    {
        if (!IsServer || GameManager.Instance.World == null)
        {
            return;
        }
        EnsureLoaded();
        saveTimer += Time.deltaTime;
        if (dirty && saveTimer >= SaveInterval)
        {
            Save();
        }
    }

    /// <summary>The world is closing: save, and forget this world's traps.</summary>
    public static void Shutdown()
    {
        if (IsServer && dirty)
        {
            Save();
        }
        cache.Clear();
        records.Clear();
        dirty = false;
        checkedFrame = -1;
        file.Reset();
    }

    // ------------------------------------------------------------------ everyone

    /// <summary>The trap's record to show (the server's own, or a client's copy, refreshed while looked at).</summary>
    public static TrapRecordDEM View(Vector3i pos)
    {
        if (IsServer)
        {
            return Find(pos);
        }
        if (!cache.TryGetValue(pos, out Cached c))
        {
            c = new Cached();
            cache[pos] = c;
        }
        float now = Time.time;
        if (now - c.Received > 2f && now - c.Requested > 1f)
        {
            c.Requested = now;
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageTrapRequestDEM>().Setup(pos));
        }
        return c.Record;
    }

    /// <summary>Client: the server sent a trap's state.</summary>
    public static void Receive(Vector3i pos, TrapRecordDEM rec)
    {
        if (!cache.TryGetValue(pos, out Cached c))
        {
            c = new Cached();
            cache[pos] = c;
        }
        c.Record = rec;
        c.Received = Time.time;
    }

    /// <summary>Server: a client asked for a trap's state.</summary>
    public static void Request(Vector3i pos, ClientInfo client)
    {
        if (client == null)
        {
            return;
        }
        client.SendPackage(NetPackageManager.GetPackage<NetPackageTrapStateDEM>().Setup(pos, Find(pos)?.Copy()));
    }

    /// <summary>A player used one of the trap's commands. `items` are what they loaded (already taken from their
    /// inventory).</summary>
    public static void Command(Vector3i pos, string command, List<TrapAmmoDEM> items, EntityPlayerLocal player)
    {
        if (IsServer)
        {
            ServerCommand(GameManager.Instance.World, pos, command, items, player.entityId);
            return;
        }
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
            NetPackageManager.GetPackage<NetPackageTrapCommandDEM>().Setup(pos, command, items));
        // Show the change soon
        if (cache.TryGetValue(pos, out Cached c))
        {
            c.Received = -100f;
            c.Requested = -100f;
        }
    }

    public static void ServerCommand(World world, Vector3i pos, string command, List<TrapAmmoDEM> items, int playerId)
    {
        if (world == null)
        {
            return;
        }
        BlockValue bv = world.GetBlock(pos);
        if (!(bv.Block is ITrapDEM trap) || bv.ischild)
        {
            Give(world, playerId, items, pos);
            return;
        }
        TrapSettingsDEM s = trap.Settings;
        TrapRecordDEM rec = Get(pos, s.Name);
        switch (command)
        {
            case TrapUiDEM.CmdLoad:
                List<TrapAmmoDEM> back = new List<TrapAmmoDEM>();
                if (items != null)
                {
                    foreach (TrapAmmoDEM a in items)
                    {
                        int taken = System.Array.IndexOf(s.AmmoItems, a.Item) >= 0
                            ? rec.AddAmmo(a.Item, a.Count, s.AmmoCapacity) : 0;
                        if (taken < a.Count)
                        {
                            back.Add(new TrapAmmoDEM(a.Item, a.Count - taken));
                        }
                    }
                }
                Give(world, playerId, back, pos);
                break;
            case TrapUiDEM.CmdUnload:
                // A part-used item (a tar with globs gone, a burning log) isn't handed back
                List<TrapAmmoDEM> back2 = new List<TrapAmmoDEM>();
                for (int i = 0; i < rec.Ammo.Count; i++)
                {
                    int n = rec.Ammo[i].Count - (i == 0 && rec.Burn > 0.001f ? 1 : 0);
                    if (n > 0)
                    {
                        back2.Add(new TrapAmmoDEM(rec.Ammo[i].Item, n));
                    }
                }
                Give(world, playerId, back2, pos);
                rec.Ammo.Clear();
                rec.Burn = 0f;
                break;
            case TrapUiDEM.CmdUpgradeA:
            case TrapUiDEM.CmdUpgradeB:
                if (rec.Upgrade == 0 && rec.Level >= TrapLevelsDEM.UpgradeLevel)
                {
                    rec.Upgrade = (byte)(command == TrapUiDEM.CmdUpgradeA ? 'A' : 'B');
                }
                break;
            default:
                trap.ServerCommand(world, pos, command);
                break;
        }
        Changed(pos, true);
    }

    /// <summary>Server: hands items back to a player (straight into their inventory, or dropped at the trap).</summary>
    private static void Give(World world, int playerId, List<TrapAmmoDEM> items, Vector3i pos)
    {
        if (items == null || items.Count == 0)
        {
            return;
        }
        EntityPlayerLocal local = world.GetPrimaryPlayer();
        if (local != null && local.entityId == playerId)
        {
            TrapUiDEM.Receive(local, items);
            return;
        }
        ClientInfo client = SingletonMonoBehaviour<ConnectionManager>.Instance.Clients.ForEntityId(playerId);
        if (client != null)
        {
            client.SendPackage(NetPackageManager.GetPackage<NetPackageTrapGiveDEM>().Setup(items));
            return;
        }
        Vector3 at = pos.ToVector3() + new Vector3(0.5f, 0.75f, 0.5f);
        foreach (TrapAmmoDEM a in items)
        {
            Drop(a.Item, a.Count, at, -1);
        }
    }

    // ------------------------------------------------------------------ kills

    /// <summary>Server: a trap killed a zombie.</summary>
    public static void AddKill(Vector3i pos, string blockName)
    {
        TrapRecordDEM rec = Get(pos, blockName);
        int before = rec.Level;
        rec.Kills++;
        dirty = true;
        if (rec.Level != before)
        {
            Changed(pos, true);
        }
    }

    /// <summary>Server: a player placed a trap; it remembers them as its owner.</summary>
    public static void Placed(Vector3i pos, string blockName, PlatformUserIdentifierAbs player)
    {
        if (!IsServer || player == null)
        {
            return;
        }
        PersistentPlayerData data = GameManager.Instance.persistentPlayers?.GetPlayerData(player);
        if (data == null)
        {
            return;
        }
        TrapRecordDEM rec = Get(pos, blockName);
        rec.Owner = data.EntityId;
        dirty = true;
    }

    /// <summary>Server: the level of any trap, the mod's own or vanilla (vanilla traps level too).</summary>
    public static int LevelAt(Vector3i pos)
    {
        TrapRecordDEM rec = Find(pos);
        return rec != null ? rec.Level : 1;
    }
}
