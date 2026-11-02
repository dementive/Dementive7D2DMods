/// <summary>Player to server: send me this zombie's profile.</summary>
public class NetPackageZedRequest : NetPackage
{
    private int entityId;

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToServer;

    public NetPackageZedRequest Setup(int _entityId)
    {
        entityId = _entityId;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        entityId = _br.ReadInt32();
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(entityId);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world != null)
        {
            ZedStore.Request(entityId, Sender);
        }
    }
}

/// <summary>Server to a player: a zombie's profile (or that it has none).</summary>
public class NetPackageZedProfile : NetPackage
{
    private int entityId;
    private ZedProfile profile;

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public NetPackageZedProfile Setup(int _entityId, ZedProfile _profile)
    {
        entityId = _entityId;
        profile = _profile;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        entityId = _br.ReadInt32();
        profile = _br.ReadBoolean() ? ZedProfile.Read(_br) : null;
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(entityId);
        _bw.Write(profile != null);
        profile?.Write(_bw);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world != null)
        {
            ZedStore.Receive(entityId, profile);
        }
    }
}
