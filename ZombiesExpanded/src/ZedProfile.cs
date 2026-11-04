using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public enum ZedBody : byte
{
    Normal,
    Gaunt,
    Bulky,
    Bloated,
    Hunched,
}

public enum ZedTemper : byte
{
    Normal,
    Sluggish,
    Restless,
    Relentless,
}

public enum ZedBiome : byte
{
    Forest,
    Desert,
    Snow,
    Burnt,
    Wasteland,
}

/// <summary>An old injury that shows in how a zombie holds itself (pose only; see ZedInjuryPose).</summary>
public enum ZedInjury : byte
{
    None,
    LimpArm,
    DraggedFoot,
    LolledHead,
    TwistedBack,
}

/// <summary>
/// What makes one zombie different from the next, rolled once by the server when it spawns and sent to every player
/// who sees it: size, body, gait, speed, voice, weathering, age, temperament and an old injury. Saved with zombies the
/// game saves.
/// </summary>
public class ZedProfile
{
    private const byte Version = 4;

    /// <summary>Drives every random detail drawn from the profile (the look's noise, which wounds look how).</summary>
    public int Seed;
    /// <summary>A factor on the zombie class's own size.</summary>
    public float Size = 1f;
    public ZedBody Body;
    /// <summary>The walk style (the animator's walk type), or -1 to keep the class's own.</summary>
    public sbyte Walk = -1;
    public float Speed = 1f;
    public float Pitch = 1f;
    public ZedBiome Biome;
    /// <summary>0 fresh and bloody, 1 rotten and grimy.</summary>
    public float Age;
    public ZedTemper Temper;
    /// <summary>A humanoid zombie (the shared zombie skeleton), not a zombie animal.</summary>
    public bool Humanoid;
    /// <summary>An old injury (pose only), and whether it's on the left side (else the right).</summary>
    public ZedInjury Injury;
    public bool InjuryLeft;

    // Mutations, gear and rank (rolled after the rest; see ZedRoll)
    public readonly List<ZedMutation> Mutations = new List<ZedMutation>();
    public readonly List<ZedGearPiece> Gear = new List<ZedGearPiece>();
    /// <summary>The props that tell who it was and how it died (cosmetic, except the bear trap's limp).</summary>
    public readonly List<ZedRemnant> Remnants = new List<ZedRemnant>();
    public bool Champion;
    public bool Alpha;
    public string Name = "";

    // What's happened to it since (sent along with the profile)
    /// <summary>The Volatile's tank: 0 on its chest, 1 dropped, 2 blown.</summary>
    public byte Tank;
    /// <summary>A Stalker that has been seen (stands up and runs).</summary>
    public bool Revealed;
    /// <summary>A Stalker creeping up (crouch-walking).</summary>
    public bool Stalking;
    /// <summary>A Possum lying still as if dead, and whether it has used its one fake death.</summary>
    public bool PlayingDead;
    public bool FakedDeath;
    /// <summary>Its sleeper pose while it plays dead (the game's lying poses: 1 back, 2 and 3 sides, 4 stomach).</summary>
    public byte DeadPose = 1;
    /// <summary>A Snatcher carrying something it stole (its sack shows full).</summary>
    public bool Carrying;

    public bool Has(ZedMutation m) => Mutations.Contains(m);

    public bool Wears(ZedGearKind kind)
    {
        foreach (ZedGearPiece g in Gear)
        {
            if (g.Kind == kind && !g.Broken)
            {
                return true;
            }
        }
        return false;
    }

    public void Write(BinaryWriter w)
    {
        w.Write(Version);
        w.Write(Seed);
        w.Write(Size);
        w.Write((byte)Body);
        w.Write(Walk);
        w.Write(Speed);
        w.Write(Pitch);
        w.Write((byte)Biome);
        w.Write(Age);
        w.Write((byte)Temper);
        w.Write(Humanoid);
        w.Write((byte)Mutations.Count);
        foreach (ZedMutation m in Mutations)
        {
            w.Write((byte)m);
        }
        w.Write((byte)Gear.Count);
        foreach (ZedGearPiece g in Gear)
        {
            w.Write((byte)g.Kind);
            w.Write(g.Part);
            w.Write(g.Soak);
        }
        w.Write(Champion);
        w.Write(Alpha);
        w.Write(Name ?? "");
        w.Write(Tank);
        w.Write(Revealed);
        w.Write(Stalking);
        w.Write((byte)Remnants.Count);
        foreach (ZedRemnant rem in Remnants)
        {
            w.Write((byte)rem);
        }
        w.Write(PlayingDead);
        w.Write(FakedDeath);
        w.Write(DeadPose);
        w.Write(Carrying);
        w.Write((byte)Injury);
        w.Write(InjuryLeft);
    }

    public static ZedProfile Read(BinaryReader r)
    {
        byte version = r.ReadByte();
        if (version < 1 || version > Version)
        {
            throw new IOException("Unknown zombie profile version " + version);
        }
        ZedProfile p = new ZedProfile
        {
            Seed = r.ReadInt32(),
            Size = r.ReadSingle(),
            Body = (ZedBody)r.ReadByte(),
            Walk = r.ReadSByte(),
            Speed = r.ReadSingle(),
            Pitch = r.ReadSingle(),
            Biome = (ZedBiome)r.ReadByte(),
            Age = r.ReadSingle(),
            Temper = (ZedTemper)r.ReadByte(),
            Humanoid = r.ReadBoolean(),
        };
        if (version < 2)
        {
            return p;
        }
        int mutations = r.ReadByte();
        for (int i = 0; i < mutations; i++)
        {
            p.Mutations.Add((ZedMutation)r.ReadByte());
        }
        int gear = r.ReadByte();
        for (int i = 0; i < gear; i++)
        {
            p.Gear.Add(new ZedGearPiece { Kind = (ZedGearKind)r.ReadByte(), Part = r.ReadString(), Soak = r.ReadSingle() });
        }
        p.Champion = r.ReadBoolean();
        p.Alpha = r.ReadBoolean();
        p.Name = r.ReadString();
        p.Tank = r.ReadByte();
        p.Revealed = r.ReadBoolean();
        p.Stalking = r.ReadBoolean();
        if (version < 3)
        {
            return p;
        }
        int remnants = r.ReadByte();
        for (int i = 0; i < remnants; i++)
        {
            p.Remnants.Add((ZedRemnant)r.ReadByte());
        }
        p.PlayingDead = r.ReadBoolean();
        p.FakedDeath = r.ReadBoolean();
        p.DeadPose = r.ReadByte();
        p.Carrying = r.ReadBoolean();
        if (version < 4)
        {
            return p;
        }
        p.Injury = (ZedInjury)r.ReadByte();
        p.InjuryLeft = r.ReadBoolean();
        return p;
    }

    // ------------------------------------------------------------------ rolling (server)

    private static readonly int[] NormalWalks = { 2, 3, 5, 6, 7 };

    /// <summary>Set by `ze spawn` around the zombie it spawns: parts of the profile to use instead of rolling.</summary>
    public static ZedForce ForceNext;

    public static ZedProfile Roll(EntityAlive e, System.Random rng)
    {
        ZedProfile p = new ZedProfile
        {
            Seed = rng.Next(),
            Humanoid = ZedStore.IsHumanoid(e),
            Biome = BiomeAt(e),
            Age = (float)rng.NextDouble(),
            Pitch = Range(rng, 0.88f, 1.12f),
        };
        if (ZedSettings.Individuals)
        {
            p.Size = Range(rng, 0.93f, 1.07f);
            p.Speed = Range(rng, 0.92f, 1.08f);
            if (p.Humanoid)
            {
                int walk = e.GetWalkType();
                p.Body = RollBody(rng, walk == EntityAlive.cWalkTypeFat);
                if (Array.IndexOf(NormalWalks, walk) >= 0 && rng.NextDouble() < 0.5)
                {
                    int pick;
                    do
                    {
                        pick = NormalWalks[rng.Next(NormalWalks.Length)];
                    }
                    while (pick == walk);
                    p.Walk = (sbyte)pick;
                }
            }
        }
        if (ZedSettings.Temperament)
        {
            double t = rng.NextDouble();
            p.Temper = t < 0.3 ? ZedTemper.Sluggish : t < 0.8 ? ZedTemper.Normal : t < 0.9 ? ZedTemper.Restless : ZedTemper.Relentless;
        }
        ForceNext?.Apply(p);
        return p;
    }

    /// <summary>Normal half the time, then gaunt, bulky, bloated or hunched. Heavy zombies are never gaunt or bloated.</summary>
    private static ZedBody RollBody(System.Random rng, bool heavy)
    {
        double b = rng.NextDouble();
        if (b < 0.5)
        {
            return ZedBody.Normal;
        }
        if (b < 0.65)
        {
            return heavy ? ZedBody.Normal : ZedBody.Gaunt;
        }
        if (b < 0.8)
        {
            return ZedBody.Bulky;
        }
        if (b < 0.9)
        {
            return heavy ? ZedBody.Normal : ZedBody.Bloated;
        }
        return ZedBody.Hunched;
    }

    /// <summary>Once the rest of the profile is rolled (its remnants and its final body): a share of the humanoid
    /// zombies (InjuryShare percent, a third) carry an old injury on one side. Never a crawler. A limp arm goes on an arm
    /// it still has, and never on the right with a prop hanging at the right hip (the crowbar, the hatchet's handle)
    /// for the arm to hang into.</summary>
    public static void RollInjury(EntityAlive e, ZedProfile p, System.Random rng)
    {
        ZedForce force = ForceNext;
        if (force != null && force.Injury.HasValue)
        {
            p.Injury = force.Injury.Value;
            p.InjuryLeft = force.InjuryLeft ?? rng.NextDouble() < 0.5;
            return;
        }
        if (!ZedSettings.Individuals || !p.Humanoid || e.IsWalkTypeACrawl()
            || rng.NextDouble() * 100.0 >= ZedSettings.Float("InjuryShare", 33f))
        {
            return;
        }
        p.Injury = (ZedInjury)(1 + rng.Next(4));
        p.InjuryLeft = rng.NextDouble() < 0.5;
        if (p.Injury == ZedInjury.LimpArm)
        {
            bool leftFree = ArmFree(e, p, true);
            bool rightFree = ArmFree(e, p, false);
            if (!leftFree && !rightFree)
            {
                // One of the others instead
                p.Injury = (ZedInjury)(2 + rng.Next(3));
            }
            else if (!(p.InjuryLeft ? leftFree : rightFree))
            {
                p.InjuryLeft = !p.InjuryLeft;
            }
        }
    }

    /// <summary>Whether a limp arm can hang on that side: the arm is still there, with nothing hanging at that hip.</summary>
    private static bool ArmFree(EntityAlive e, ZedProfile p, bool left)
    {
        uint lost = left ? BodyDamage.cNoArmLUpper | BodyDamage.cNoArmLLower : BodyDamage.cNoArmRUpper | BodyDamage.cNoArmRLower;
        if ((e.bodyDamage.Flags & lost) != 0)
        {
            return false;
        }
        return left || (!p.Remnants.Contains(ZedRemnant.Crowbar) && !p.Remnants.Contains(ZedRemnant.Hatchet));
    }

    public static ZedBiome BiomeAt(Entity e)
    {
        BiomeDefinition biome = e.world?.GetBiome(Mathf.FloorToInt(e.position.x), Mathf.FloorToInt(e.position.z));
        string name = biome?.m_sBiomeName ?? "";
        if (name.IndexOf("snow", StringComparison.OrdinalIgnoreCase) >= 0)
        {
            return ZedBiome.Snow;
        }
        if (name.IndexOf("desert", StringComparison.OrdinalIgnoreCase) >= 0)
        {
            return ZedBiome.Desert;
        }
        if (name.IndexOf("waste", StringComparison.OrdinalIgnoreCase) >= 0)
        {
            return ZedBiome.Wasteland;
        }
        if (name.IndexOf("burn", StringComparison.OrdinalIgnoreCase) >= 0)
        {
            return ZedBiome.Burnt;
        }
        return ZedBiome.Forest;
    }

    private static float Range(System.Random rng, float min, float max)
    {
        return min + (float)rng.NextDouble() * (max - min);
    }

    public override string ToString()
    {
        string extra = "";
        if (Injury != ZedInjury.None)
        {
            extra += ", " + Injury + (InjuryLeft ? " (left)" : " (right)");
        }
        if (Mutations.Count > 0)
        {
            extra += ", " + string.Join("+", Mutations);
        }
        foreach (ZedGearPiece g in Gear)
        {
            extra += ", " + g.Kind + (g.Part.Contains("#") ? g.Part.Substring(g.Part.IndexOf('#')) : "") + " " + (g.Broken ? "off" : g.Soak.ToString("0"));
        }
        if (Remnants.Count > 0)
        {
            extra += ", " + string.Join("+", Remnants);
        }
        if (Champion || Alpha)
        {
            extra += ", " + (Alpha ? "Alpha " : "champion ") + Name;
        }
        if (PlayingDead)
        {
            extra += ", playing dead";
        }
        return $"size {Size:0.00}, body {Body}, walk {(Walk < 0 ? "class" : Walk.ToString())}, speed {Speed:0.00}, voice {Pitch:0.00}, "
            + $"{Biome}, age {Age:0.00}, {Temper}" + (Humanoid ? "" : ", not humanoid") + extra;
    }
}
