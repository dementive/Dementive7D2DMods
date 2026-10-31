using System.Collections.Generic;

/// <summary>
/// Contract requests from a client to the server, and the server's answers (see <see cref="ContractsDEM"/>).
/// </summary>
public class NetPackageContractDEM : NetPackage
{
    public enum Ops : byte
    {
        // Client to server
        Sync,
        Start,
        Reward,
        Stage,
        Lose,
        Pick,
        CashOut,
        Boss,

        // Server to client
        State,
        Payout,
        Message,
    }

    private Ops op;

    private int a;

    private int b;

    private string text = "";

    private string extra = "";

    private List<ItemStack> items = new List<ItemStack>();

    private ContractStateDEM state;

    public NetPackageContractDEM Setup(Ops _op, int _a = 0, int _b = 0, string _text = "", List<ItemStack> _items = null,
        ContractStateDEM state = null, string extra = "")
    {
        op = _op;
        a = _a;
        b = _b;
        text = _text ?? "";
        this.extra = extra ?? "";
        items = _items ?? new List<ItemStack>();
        this.state = state;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        op = (Ops)_br.ReadByte();
        a = _br.ReadInt32();
        b = _br.ReadInt32();
        text = _br.ReadString();
        extra = _br.ReadString();
        int count = _br.ReadInt32();
        items = new List<ItemStack>(count);
        for (int i = 0; i < count; i++)
        {
            items.Add(ItemStack.Empty.Clone().Read(_br));
        }
        state = _br.ReadBoolean() ? ContractStateDEM.Read(_br) : null;
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write((byte)op);
        _bw.Write(a);
        _bw.Write(b);
        _bw.Write(text);
        _bw.Write(extra);
        _bw.Write(items.Count);
        foreach (ItemStack stack in items)
        {
            stack.Write(_bw);
        }
        _bw.Write(state != null);
        state?.Write(_bw);
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
        {
            return;
        }

        if (op >= Ops.State)
        {
            Apply();
            return;
        }

        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer && Sender != null)
        {
            ContractsDEM.ServerHandle(Sender.entityId, op, a, b, text, items);
        }
    }

    /// <summary>
    /// Client side: the server's answer.
    /// </summary>
    public void Apply()
    {
        switch (op)
        {
            case Ops.State:
                ContractsDEM.ClientState(state ?? new ContractStateDEM());
                break;
            case Ops.Payout:
                ContractsDEM.ClientPayout(a, b, items, text);
                break;
            case Ops.Message:
                ContractsDEM.ClientMessage(text, a, extra);
                break;
        }
    }
}
