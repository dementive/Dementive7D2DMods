using System.Collections.Generic;

/// <summary>
/// One player's contract: the stages done, the pot (the rewards of those stages, held until cashing out), the boons
/// picked and the pick of three on offer. The server owns it (<see cref="ContractsDEM"/>); clients get a copy.
/// </summary>
public class ContractStateDEM
{
    public bool Active;

    /// <summary>Stages (quests) completed on the contract.</summary>
    public int Stage;

    public int PotExp;

    public int PotDukes;

    public List<ItemStack> PotItems = new List<ItemStack>();

    public List<string> Boons = new List<string>();

    /// <summary>The three boons the trader is offering, empty when there is nothing to pick.</summary>
    public List<string> Offer = new List<string>();

    /// <summary>Stages whose boon hasn't been picked yet.</summary>
    public int PendingPicks;

    /// <summary>The last stage's boss has come for the player.</summary>
    public bool BossSpawned;

    public void Write(PooledBinaryWriter _bw)
    {
        _bw.Write(Active);
        _bw.Write(Stage);
        _bw.Write(PotExp);
        _bw.Write(PotDukes);
        _bw.Write(PotItems.Count);
        foreach (ItemStack stack in PotItems)
            stack.Write(_bw);
        WriteList(_bw, Boons);
        WriteList(_bw, Offer);
        _bw.Write(PendingPicks);
        _bw.Write(BossSpawned);
    }

    public static ContractStateDEM Read(PooledBinaryReader _br)
    {
        var state = new ContractStateDEM
        {
            Active = _br.ReadBoolean(),
            Stage = _br.ReadInt32(),
            PotExp = _br.ReadInt32(),
            PotDukes = _br.ReadInt32(),
        };
        int items = _br.ReadInt32();
        for (int i = 0; i < items; i++)
            state.PotItems.Add(ItemStack.Empty.Clone().Read(_br));
        state.Boons = ReadList(_br);
        state.Offer = ReadList(_br);
        state.PendingPicks = _br.ReadInt32();
        state.BossSpawned = _br.ReadBoolean();
        return state;
    }

    private static void WriteList(PooledBinaryWriter _bw, List<string> list)
    {
        _bw.Write(list.Count);
        foreach (string value in list)
            _bw.Write(value);
    }

    private static List<string> ReadList(PooledBinaryReader _br)
    {
        int count = _br.ReadInt32();
        var list = new List<string>(count);
        for (int i = 0; i < count; i++)
            list.Add(_br.ReadString());
        return list;
    }
}
