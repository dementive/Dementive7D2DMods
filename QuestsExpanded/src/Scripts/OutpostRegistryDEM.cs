using System.Collections.Generic;

/// <summary>
/// Server side: how every Create Outpost quest stands, by quest code (shared copies keep it), saved with the world.
/// An outpost lasts for days, so this outlives the players' sessions: a party member who was offline when the
/// outpost fell or held finds out when they log back in.
/// </summary>
public static class OutpostRegistryDEM
{
    public class Outpost
    {
        public int Nights;
        public int NightsHeld;
        /// <summary>World time of the next attack.</summary>
        public ulong NextAttack;
        public bool Fallen;
        public bool Won;
    }

    private const int FileVersion = 1;

    private static readonly SaveFileDEM file = new SaveFileDEM("outposts.dat");
    private static readonly Dictionary<int, Outpost> outposts = new Dictionary<int, Outpost>();

    public static Outpost Get(int questCode)
    {
        Load();
        if (!outposts.TryGetValue(questCode, out Outpost outpost))
        {
            outpost = new Outpost();
            outposts.Add(questCode, outpost);
        }
        return outpost;
    }

    private static void Load()
    {
        if (!file.NeedsLoad())
            return;
        outposts.Clear();
        file.Load(reader =>
        {
            reader.ReadInt32();
            int count = reader.ReadInt32();
            for (int i = 0; i < count; i++)
            {
                int questCode = reader.ReadInt32();
                outposts[questCode] = new Outpost
                {
                    Nights = reader.ReadInt32(),
                    NightsHeld = reader.ReadInt32(),
                    NextAttack = reader.ReadUInt64(),
                    Fallen = reader.ReadBoolean(),
                    Won = reader.ReadBoolean(),
                };
            }
        });
    }

    public static void Save()
    {
        // Finished outposts are forgotten after 30 days
        ulong now = GameManager.Instance.World?.worldTime ?? 0;
        var forgotten = new List<int>();
        foreach (KeyValuePair<int, Outpost> entry in outposts)
        {
            if ((entry.Value.Fallen || entry.Value.Won) && now > entry.Value.NextAttack + 30 * 24 * WaveDirectorDEM.Hour)
                forgotten.Add(entry.Key);
        }
        foreach (int questCode in forgotten)
            outposts.Remove(questCode);

        file.Save(writer =>
        {
            writer.Write(FileVersion);
            writer.Write(outposts.Count);
            foreach (KeyValuePair<int, Outpost> entry in outposts)
            {
                writer.Write(entry.Key);
                writer.Write(entry.Value.Nights);
                writer.Write(entry.Value.NightsHeld);
                writer.Write(entry.Value.NextAttack);
                writer.Write(entry.Value.Fallen);
                writer.Write(entry.Value.Won);
            }
        });
    }
}
