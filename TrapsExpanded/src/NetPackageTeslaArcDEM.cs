/// <summary>
/// Server to clients: a Tesla Coil at Pos just zapped these entities, in order, so draw the bolt. The damage is
/// already done on the server; this is only the visual.
/// </summary>
public class NetPackageTeslaArcDEM : NetPackage
{
    private Vector3i pos;

    private int[] ids = new int[0];

    public NetPackageTeslaArcDEM Setup(Vector3i _pos, int[] _ids)
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
        _bw.Write((byte)ids.Length);
        foreach (int id in ids)
        {
            _bw.Write(id);
        }
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
        {
            return;
        }
        BlockTeslaCoilDEM.FindController(_world, pos)?.ShowArcs(ids);
    }
}
