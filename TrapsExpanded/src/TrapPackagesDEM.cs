using System.Collections.Generic;

/// <summary>Server to a client: a trap's record (or that it has none yet).</summary>
public class NetPackageTrapStateDEM : NetPackage
{
    private Vector3i pos;
    private TrapRecordDEM record;

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public NetPackageTrapStateDEM Setup(Vector3i _pos, TrapRecordDEM _record)
    {
        pos = _pos;
        record = _record;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        pos = StreamUtils.ReadVector3i(_br);
        record = _br.ReadBoolean() ? TrapRecordDEM.Read(_br) : null;
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        StreamUtils.Write(_bw, pos);
        _bw.Write(record != null);
        record?.Write(_bw);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        TrapStoreDEM.Receive(pos, record);
    }
}

/// <summary>Client to server: send me this trap's record.</summary>
public class NetPackageTrapRequestDEM : NetPackage
{
    private Vector3i pos;

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToServer;

    public NetPackageTrapRequestDEM Setup(Vector3i _pos)
    {
        pos = _pos;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        pos = StreamUtils.ReadVector3i(_br);
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        StreamUtils.Write(_bw, pos);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world != null)
        {
            TrapStoreDEM.Request(pos, Sender);
        }
    }
}

/// <summary>Client to server: a player used a trap command (with the items they loaded, already taken from them).</summary>
public class NetPackageTrapCommandDEM : NetPackage
{
    private Vector3i pos;
    private string command = "";
    private List<TrapAmmoDEM> items = new List<TrapAmmoDEM>();

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToServer;

    public NetPackageTrapCommandDEM Setup(Vector3i _pos, string _command, List<TrapAmmoDEM> _items)
    {
        pos = _pos;
        command = _command ?? "";
        items = _items ?? new List<TrapAmmoDEM>();
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        pos = StreamUtils.ReadVector3i(_br);
        command = _br.ReadString();
        items = TrapItemsIO.Read(_br);
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        StreamUtils.Write(_bw, pos);
        _bw.Write(command);
        TrapItemsIO.Write(_bw, items);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null || Sender == null)
        {
            return;
        }
        TrapStoreDEM.ServerCommand(_world, pos, command, items, Sender.entityId);
    }
}

/// <summary>Server to a client: items handed back to the player (unloaded ammo, or what didn't fit).</summary>
public class NetPackageTrapGiveDEM : NetPackage
{
    private List<TrapAmmoDEM> items = new List<TrapAmmoDEM>();

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public NetPackageTrapGiveDEM Setup(List<TrapAmmoDEM> _items)
    {
        items = _items ?? new List<TrapAmmoDEM>();
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        items = TrapItemsIO.Read(_br);
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        TrapItemsIO.Write(_bw, items);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        EntityPlayerLocal player = _world?.GetPrimaryPlayer();
        if (player != null)
        {
            TrapUiDEM.Receive(player, items);
        }
    }
}

/// <summary>Server to clients: the Blood Moon report (or the morning forecast) to show.</summary>
public class NetPackageTrapReportDEM : NetPackage
{
    private string title = "";
    private string text = "";

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public NetPackageTrapReportDEM Setup(string _title, string _text)
    {
        title = _title ?? "";
        text = _text ?? "";
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        title = _br.ReadString();
        text = _br.ReadString();
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(title);
        _bw.Write(text);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        BloodMoonReportDEM.Show(title, text);
    }
}

public static class TrapItemsIO
{
    public static List<TrapAmmoDEM> Read(System.IO.BinaryReader r)
    {
        List<TrapAmmoDEM> list = new List<TrapAmmoDEM>();
        int count = r.ReadByte();
        for (int i = 0; i < count; i++)
        {
            string item = r.ReadString();
            int n = r.ReadInt32();
            list.Add(new TrapAmmoDEM(item, n));
        }
        return list;
    }

    public static void Write(System.IO.BinaryWriter w, List<TrapAmmoDEM> list)
    {
        int count = list == null ? 0 : System.Math.Min(list.Count, 255);
        w.Write((byte)count);
        for (int i = 0; i < count; i++)
        {
            w.Write(list[i].Item ?? "");
            w.Write(list[i].Count);
        }
    }
}
