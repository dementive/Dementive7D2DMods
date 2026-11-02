/// <summary>
/// Server to clients: the trap at Pos just acted on these entities (a Tesla Coil's bolt through them in order, a
/// Sprinkler soaking them), so play its effects. The work itself is already done on the server.
/// </summary>
public class NetPackageTrapFxDEM : NetPackage
{
    private Vector3i pos;

    private int[] ids = new int[0];

    public override NetPackageDirection PackageDirection => NetPackageDirection.ToClient;

    public NetPackageTrapFxDEM Setup(Vector3i _pos, int[] _ids)
    {
        pos = _pos;
        ids = _ids;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        pos = StreamUtils.ReadVector3i(_br);
        int count = _br.ReadByte();
        ids = new int[count];
        for (int i = 0; i < count; i++)
        {
            ids[i] = _br.ReadInt32();
        }
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        StreamUtils.Write(_bw, pos);
        int count = System.Math.Min(ids.Length, 255);
        _bw.Write((byte)count);
        for (int i = 0; i < count; i++)
        {
            _bw.Write(ids[i]);
        }
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
        {
            return;
        }
        BlockTrapDEM.FindController(_world, pos)?.PlayFx(ids);
    }
}
