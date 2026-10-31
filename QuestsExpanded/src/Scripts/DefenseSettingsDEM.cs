using UnityEngine;

/// <summary>
/// What a defense looks like, sent by the objective that starts it to <see cref="WaveDirectorDEM"/>.
/// </summary>
public class DefenseSettingsDEM
{
    public enum Modes : byte
    {
        /// <summary>A set number of waves (Clear and Defend, Build and Defend, ...).</summary>
        Waves,
        /// <summary>A boss with a few escorts deep inside the POI; over when the boss is dead.</summary>
        Bounty,
        /// <summary>Endless waves, each harder than the last, with a boss every few waves.</summary>
        LastStand,
        /// <summary>Waves of bosses during the next blood moon, wherever the players are.</summary>
        BloodMoon,
        /// <summary>Nightly attacks on a flag in a POI, for a number of nights.</summary>
        Outpost,
        /// <summary>Bandits (from an NPC mod) holding a POI; over when every one is dead.</summary>
        Hideout,
        /// <summary>A group of survivors under attack in a POI: break the attack and lead them to the trader.</summary>
        Rescue,
        /// <summary>Build a safehouse to a checklist, lead refugees to it and hold it through its first night.</summary>
        Safehouse,
    }

    public Modes Mode;

    public enum SpawnStyles : byte
    {
        /// <summary>All around the defended area, 6-14m outside it (a flag, a spot in the wild).</summary>
        Around,
        /// <summary>Just outside the POI's footprint, so fortifications inside matter.</summary>
        Walls,
        /// <summary>About half out of the building itself (its sleeper spots, away from the players), the rest just
        /// outside the POI's footprint.</summary>
        Inside,
    }

    public SpawnStyles SpawnStyle;

    /// <summary>The POI's corner and size, for <see cref="SpawnStyles.Walls"/> and <see cref="SpawnStyles.Inside"/>.</summary>
    public Vector3 PoiMin;

    public Vector3 PoiSize;

    /// <summary>Center of the defended area.</summary>
    public Vector3 Center;

    /// <summary>Radius of the defended area (a POI's footprint, or the area around a flag); waves spawn 6-14m outside it.</summary>
    public float Radius;

    /// <summary>Waves to beat (boss waves for a blood moon, nights for an outpost). Ignored by a last stand.</summary>
    public int Waves = 1;

    /// <summary>Waves already beaten, when a quest picks the defense up again (e.g. after logging out).</summary>
    public int WavesDone;

    /// <summary>Gamestage spawners (gamestages.xml) waves are drawn from; one is picked at random for each wave.</summary>
    public string Spawners = WaveDirectorDEM.DefaultSpawner;

    /// <summary>
    /// Entity classes, one picked at random, for the boss of the final wave (or the bounty). Empty for no boss.
    /// For a blood moon, one list per boss wave separated by ';'.
    /// </summary>
    public string Bosses = "";

    /// <summary>Multiplier on the gamestage the waves are drawn at, for the harder quests.</summary>
    public float Strength = 1f;

    /// <summary>Seconds between waves.</summary>
    public float BreakSeconds = WaveDirectorDEM.BreakSeconds;

    /// <summary>Last stand: a boss joins every this many waves.</summary>
    public int BossEvery;

    /// <summary>Blood moon: bosses in each wave (more join for a bigger party).</summary>
    public int BossCount = 1;

    /// <summary>Outpost: where the flag is.</summary>
    public Vector3 Flag;

    /// <summary>Outpost: hour of the night the attacks come; waves in each attack.</summary>
    public int AttackHour = 22;

    public int AttackWaves = 3;

    /// <summary>The quest's tier, for picking NPCs (the NPC quests and the outposts' bandit raids).</summary>
    public int Tier = 1;

    /// <summary>Rescue: survivors in the group. Safehouse: refugees.</summary>
    public int Count;

    /// <summary>Outpost: one night's attack is a bandit raid, when an NPC mod adds bandits.</summary>
    public bool BanditRaid;

    /// <summary>Safehouse: where the refugees wait (just outside the trader's compound).</summary>
    public Vector3 Trader;

    public void Write(PooledBinaryWriter _bw)
    {
        _bw.Write((byte)Mode);
        StreamUtils.Write(_bw, Center);
        _bw.Write(Radius);
        _bw.Write(Waves);
        _bw.Write(WavesDone);
        _bw.Write(Spawners);
        _bw.Write(Bosses);
        _bw.Write(Strength);
        _bw.Write(BreakSeconds);
        _bw.Write(BossEvery);
        _bw.Write(BossCount);
        StreamUtils.Write(_bw, Flag);
        _bw.Write(AttackHour);
        _bw.Write(AttackWaves);
        _bw.Write((byte)SpawnStyle);
        StreamUtils.Write(_bw, PoiMin);
        StreamUtils.Write(_bw, PoiSize);
        _bw.Write(Tier);
        _bw.Write(Count);
        _bw.Write(BanditRaid);
        StreamUtils.Write(_bw, Trader);
    }

    public static DefenseSettingsDEM Read(PooledBinaryReader _br)
    {
        return new DefenseSettingsDEM
        {
            Mode = (Modes)_br.ReadByte(),
            Center = StreamUtils.ReadVector3(_br),
            Radius = _br.ReadSingle(),
            Waves = _br.ReadInt32(),
            WavesDone = _br.ReadInt32(),
            Spawners = _br.ReadString(),
            Bosses = _br.ReadString(),
            Strength = _br.ReadSingle(),
            BreakSeconds = _br.ReadSingle(),
            BossEvery = _br.ReadInt32(),
            BossCount = _br.ReadInt32(),
            Flag = StreamUtils.ReadVector3(_br),
            AttackHour = _br.ReadInt32(),
            AttackWaves = _br.ReadInt32(),
            SpawnStyle = (SpawnStyles)_br.ReadByte(),
            PoiMin = StreamUtils.ReadVector3(_br),
            PoiSize = StreamUtils.ReadVector3(_br),
            Tier = _br.ReadInt32(),
            Count = _br.ReadInt32(),
            BanditRaid = _br.ReadBoolean(),
            Trader = StreamUtils.ReadVector3(_br),
        };
    }

    /// <summary>
    /// Center and radius from the quest's POI.
    /// </summary>
    public static bool FromPOI(Quest quest, out Vector3 center, out float radius)
    {
        return FromPOI(quest, out center, out radius, out _, out _);
    }

    /// <summary>
    /// Center, radius, corner and size of the quest's POI.
    /// </summary>
    public static bool FromPOI(Quest quest, out Vector3 center, out float radius, out Vector3 poiPosition, out Vector3 poiSize)
    {
        center = Vector3.zero;
        radius = 0f;
        poiSize = Vector3.zero;
        if (!quest.GetPositionData(out poiPosition, Quest.PositionDataTypes.POIPosition))
            return false;
        quest.GetPositionData(out poiSize, Quest.PositionDataTypes.POISize);
        center = new Vector3(poiPosition.x + poiSize.x / 2f, poiPosition.y, poiPosition.z + poiSize.z / 2f);
        // Half the POI's diagonal: anything farther than this from the center is outside the POI
        radius = new Vector2(poiSize.x / 2f, poiSize.z / 2f).magnitude;
        return true;
    }
}
