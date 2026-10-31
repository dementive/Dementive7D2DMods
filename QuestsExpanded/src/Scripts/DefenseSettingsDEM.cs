using UnityEngine;

/// <summary>
/// What a defense looks like, sent by the objective that starts it to <see cref="WaveDirectorDEM"/>.
/// </summary>
public class DefenseSettingsDEM
{
    /// <summary>Center of the defended area.</summary>
    public Vector3 Center;

    /// <summary>Radius of the defended area (a POI's footprint, or the area around a flag); waves spawn 6-14m outside it.</summary>
    public float Radius;

    public int Waves = 1;

    public int WavesDone;

    /// <summary>Gamestage spawners (gamestages.xml) waves are drawn from; one is picked at random for each wave.</summary>
    public string Spawners = WaveDirectorDEM.DefaultSpawner;

    /// <summary>Entity classes, one picked at random, for the boss of the final wave (or the bounty). Empty for no boss.</summary>
    public string Bosses = "";

    /// <summary>Multiplier on the gamestage the waves are drawn at, for the harder compound quests.</summary>
    public float Strength = 1f;

    /// <summary>
    /// Bounty: instead of waves, a boss with a few escorts spawns deep inside the POI (at one of its sleeper spawn
    /// points), and the defense is over when the boss is dead.
    /// </summary>
    public bool Bounty;

    public void Write(PooledBinaryWriter _bw)
    {
        StreamUtils.Write(_bw, Center);
        _bw.Write(Radius);
        _bw.Write(Waves);
        _bw.Write(WavesDone);
        _bw.Write(Spawners);
        _bw.Write(Bosses);
        _bw.Write(Strength);
        _bw.Write(Bounty);
    }

    public static DefenseSettingsDEM Read(PooledBinaryReader _br)
    {
        return new DefenseSettingsDEM
        {
            Center = StreamUtils.ReadVector3(_br),
            Radius = _br.ReadSingle(),
            Waves = _br.ReadInt32(),
            WavesDone = _br.ReadInt32(),
            Spawners = _br.ReadString(),
            Bosses = _br.ReadString(),
            Strength = _br.ReadSingle(),
            Bounty = _br.ReadBoolean(),
        };
    }

    /// <summary>
    /// Center and radius from the quest's POI.
    /// </summary>
    public static bool FromPOI(Quest quest, out Vector3 center, out float radius)
    {
        center = Vector3.zero;
        radius = 0f;
        if (!quest.GetPositionData(out Vector3 poiPosition, Quest.PositionDataTypes.POIPosition))
            return false;
        quest.GetPositionData(out Vector3 poiSize, Quest.PositionDataTypes.POISize);
        center = new Vector3(poiPosition.x + poiSize.x / 2f, poiPosition.y, poiPosition.z + poiSize.z / 2f);
        // Half the POI's diagonal: anything farther than this from the center is outside the POI
        radius = new Vector2(poiSize.x / 2f, poiSize.z / 2f).magnitude;
        return true;
    }
}
