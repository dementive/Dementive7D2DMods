using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Server side: how every Safehouse quest stands, by quest code (shared copies keep it), saved with the world like
/// <see cref="OutpostRegistryDEM"/>: a safehouse takes days, and its refugees outlive the players' sessions.
/// </summary>
public static class SafehouseRegistryDEM
{
    public class Refugee
    {
        public int Id;
        public int ClassId;
        public Vector3 Position;
        public bool Settled;
    }

    public class Safehouse
    {
        /// <summary>SafehouseDefense.Stages.</summary>
        public int Stage;
        public int Refugees;
        public int Lost;
        /// <summary>World time of the attack.</summary>
        public ulong NextAttack;
        public bool Fallen;
        public bool Won;
        /// <summary>The refugees still alive.</summary>
        public readonly List<Refugee> Members = new List<Refugee>();
    }

    private const int FileVersion = 1;

    private static readonly SaveFileDEM file = new SaveFileDEM("safehouses.dat");
    private static readonly Dictionary<int, Safehouse> safehouses = new Dictionary<int, Safehouse>();

    public static Safehouse Get(int questCode)
    {
        Load();
        if (!safehouses.TryGetValue(questCode, out Safehouse house))
        {
            house = new Safehouse();
            safehouses.Add(questCode, house);
        }
        return house;
    }

    private static void Load()
    {
        if (!file.NeedsLoad())
            return;
        safehouses.Clear();
        file.Load(reader =>
        {
            reader.ReadInt32();
            int count = reader.ReadInt32();
            for (int i = 0; i < count; i++)
            {
                int questCode = reader.ReadInt32();
                var house = new Safehouse
                {
                    Stage = reader.ReadInt32(),
                    Refugees = reader.ReadInt32(),
                    Lost = reader.ReadInt32(),
                    NextAttack = reader.ReadUInt64(),
                    Fallen = reader.ReadBoolean(),
                    Won = reader.ReadBoolean(),
                };
                int members = reader.ReadInt32();
                for (int j = 0; j < members; j++)
                {
                    house.Members.Add(new Refugee
                    {
                        Id = reader.ReadInt32(),
                        ClassId = reader.ReadInt32(),
                        Position = StreamUtils.ReadVector3(reader),
                        Settled = reader.ReadBoolean(),
                    });
                }
                safehouses[questCode] = house;
            }
        });
    }

    /// <summary>
    /// A settled refugee died while its safehouse wasn't running (its party was offline): strike it from the record.
    /// <paramref name="tag"/> is the safehouse's NpcDefense.Tag.
    /// </summary>
    public static void RefugeeDied(float tag, int entityId)
    {
        Load();
        foreach (KeyValuePair<int, Safehouse> entry in safehouses)
        {
            Safehouse house = entry.Value;
            if (house.Won || house.Fallen || NpcDefense.Tag(entry.Key) != tag)
                continue;
            if (house.Members.RemoveAll(refugee => refugee.Id == entityId) > 0)
            {
                house.Lost++;
                Save();
            }
            return;
        }
    }

    public static void Save()
    {
        // Finished safehouses are forgotten after 30 days
        ulong now = GameManager.Instance.World?.worldTime ?? 0;
        var forgotten = new List<int>();
        foreach (KeyValuePair<int, Safehouse> entry in safehouses)
        {
            if ((entry.Value.Fallen || entry.Value.Won) && now > entry.Value.NextAttack + 30 * 24 * WaveDirectorDEM.Hour)
                forgotten.Add(entry.Key);
        }
        foreach (int questCode in forgotten)
            safehouses.Remove(questCode);

        file.Save(writer =>
        {
            writer.Write(FileVersion);
            writer.Write(safehouses.Count);
            foreach (KeyValuePair<int, Safehouse> entry in safehouses)
            {
                Safehouse house = entry.Value;
                writer.Write(entry.Key);
                writer.Write(house.Stage);
                writer.Write(house.Refugees);
                writer.Write(house.Lost);
                writer.Write(house.NextAttack);
                writer.Write(house.Fallen);
                writer.Write(house.Won);
                writer.Write(house.Members.Count);
                foreach (Refugee refugee in house.Members)
                {
                    writer.Write(refugee.Id);
                    writer.Write(refugee.ClassId);
                    StreamUtils.Write(writer, refugee.Position);
                    writer.Write(refugee.Settled);
                }
            }
        });
    }
}
