/// <summary>
/// A client picked "a survivor joins you" from a Rescue's rewards: the server has one of the saved survivors join
/// them, or sends back the dukes when the party has taken them all.
/// </summary>
public class NetPackageRescueJoinDEM : NetPackage
{
    private bool request;

    private int questCode;

    private int dukes;

    public NetPackageRescueJoinDEM SetupRequest(int _questCode, int _dukes)
    {
        request = true;
        questCode = _questCode;
        dukes = _dukes;
        return this;
    }

    public NetPackageRescueJoinDEM SetupDukes(int _dukes)
    {
        request = false;
        dukes = _dukes;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        request = _br.ReadBoolean();
        questCode = _br.ReadInt32();
        dukes = _br.ReadInt32();
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write(request);
        _bw.Write(questCode);
        _bw.Write(dukes);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
            return;

        if (!request)
        {
            RewardUtilsDEM.GiveDukes(_world.GetPrimaryPlayer(), dukes);
            return;
        }

        if (!SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer || Sender == null)
            return;
        if (_world.GetEntity(Sender.entityId) is EntityPlayer player && RescueJoinPoolDEM.Join(questCode, player))
            return;
        Sender.SendPackage(NetPackageManager.GetPackage<NetPackageRescueJoinDEM>().SetupDukes(dukes));
    }
}
