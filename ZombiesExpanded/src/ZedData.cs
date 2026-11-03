using System;
using System.Collections.Generic;
using UnityEngine;

public enum ZedMutation : byte
{
    Bloater,
    Sprinter,
    Spiked,
    Grabber,
    Screecher,
    Frostbitten,
    Smoldering,
    Leaper,
    Regenerator,
    Toxic,
    Volatile,
    Hulking,
    Stalker,
    Brood,
    Lurker,
    Possum,
    Snatcher,
}

public enum ZedGearKind : byte
{
    HardHat,
    WeldingMask,
    FootballHelmet,
    MotorcycleHelmet,
    RiotHelmet,
    MilitaryHelmet,
    KevlarVest,
    ScrapArmor,
    CarDoor,
    RiotShield,
}

/// <summary>Where on the body a model sits, so two never fight over the same spot.</summary>
[Flags]
public enum ZedSlot
{
    None = 0,
    Head = 1,
    Face = 2,
    Neck = 4,
    Chest = 8,
    Back = 16,
    Belly = 32,
    LeftShoulder = 64,
    RightShoulder = 128,
    LeftArm = 256,
    RightArm = 512,
    LeftHand = 1024,
    RightHand = 2048,
    Waist = 4096,
    LeftLeg = 8192,
    RightLeg = 16384,
}

/// <summary>What a mutation is: when it starts appearing, where, the model that shows it, the overlay it adds,
/// and the XML buff that carries its stat trades (health, speed, damage).</summary>
public class ZedMutationInfo
{
    public ZedMutation Id;
    public int FromGamestage;
    public ZedBiome? OnlyIn;
    /// <summary>The bundle model bolted on (null: shown by the overlay and the body only).</summary>
    public string Model;
    public string Buff;
    public Color Veins = Color.clear;
    public float VeinGlow;
    /// <summary>Where its model sits.</summary>
    public ZedSlot Slots;
    /// <summary>Rolled on its own, never in strains, champions or the Alpha (the Snatcher).</summary>
    public bool Solo;

    public static readonly Dictionary<ZedMutation, ZedMutationInfo> All = new Dictionary<ZedMutation, ZedMutationInfo>
    {
        { ZedMutation.Bloater, new ZedMutationInfo { Id = ZedMutation.Bloater, FromGamestage = 0, Model = "Pustules", Buff = "buffZedBloater",
            Veins = new Color(0.55f, 0.6f, 0.15f), VeinGlow = 0f,
            Slots = ZedSlot.Back | ZedSlot.LeftShoulder | ZedSlot.RightShoulder | ZedSlot.LeftArm | ZedSlot.RightArm } },
        { ZedMutation.Sprinter, new ZedMutationInfo { Id = ZedMutation.Sprinter, FromGamestage = 0, Buff = "buffZedSprinter",
            Veins = new Color(1f, 0.08f, 0.05f), VeinGlow = 1.2f } },
        { ZedMutation.Spiked, new ZedMutationInfo { Id = ZedMutation.Spiked, FromGamestage = 30, Model = "BoneSpurs", Buff = "buffZedSpiked",
            Slots = ZedSlot.Back | ZedSlot.LeftShoulder | ZedSlot.RightShoulder | ZedSlot.LeftArm | ZedSlot.RightArm } },
        { ZedMutation.Grabber, new ZedMutationInfo { Id = ZedMutation.Grabber, FromGamestage = 30, Model = "GnarledHands", Buff = "buffZedGrabber",
            Slots = ZedSlot.LeftHand | ZedSlot.RightHand } },
        { ZedMutation.Screecher, new ZedMutationInfo { Id = ZedMutation.Screecher, FromGamestage = 40, Model = "ThroatSacs", Buff = "buffZedScreecher",
            Slots = ZedSlot.Neck } },
        { ZedMutation.Frostbitten, new ZedMutationInfo { Id = ZedMutation.Frostbitten, FromGamestage = 40, OnlyIn = ZedBiome.Snow,
            Buff = "buffZedFrostbitten" } },
        { ZedMutation.Smoldering, new ZedMutationInfo { Id = ZedMutation.Smoldering, FromGamestage = 40, OnlyIn = ZedBiome.Burnt, Buff = "buffZedSmoldering" } },
        { ZedMutation.Leaper, new ZedMutationInfo { Id = ZedMutation.Leaper, FromGamestage = 50, Model = "Claws", Buff = "buffZedLeaper",
            Slots = ZedSlot.LeftHand | ZedSlot.RightHand } },
        { ZedMutation.Regenerator, new ZedMutationInfo { Id = ZedMutation.Regenerator, FromGamestage = 60, Model = "Fungus", Buff = "buffZedRegenerator",
            Slots = ZedSlot.Face | ZedSlot.Back | ZedSlot.LeftShoulder | ZedSlot.LeftArm } },
        { ZedMutation.Toxic, new ZedMutationInfo { Id = ZedMutation.Toxic, FromGamestage = 75, Buff = "buffZedToxic",
            Veins = new Color(0.35f, 1f, 0.2f), VeinGlow = 2.2f } },
        { ZedMutation.Volatile, new ZedMutationInfo { Id = ZedMutation.Volatile, FromGamestage = 75, Model = "PropaneTank", Buff = "buffZedVolatile",
            Slots = ZedSlot.Chest | ZedSlot.Back } },
        { ZedMutation.Hulking, new ZedMutationInfo { Id = ZedMutation.Hulking, FromGamestage = 90, Buff = "buffZedHulking" } },
        { ZedMutation.Stalker, new ZedMutationInfo { Id = ZedMutation.Stalker, FromGamestage = 100, Buff = "buffZedStalker" } },
        { ZedMutation.Brood, new ZedMutationInfo { Id = ZedMutation.Brood, FromGamestage = 120, Model = "BroodSac", Buff = "buffZedBrood",
            Slots = ZedSlot.Belly } },
        { ZedMutation.Lurker, new ZedMutationInfo { Id = ZedMutation.Lurker, FromGamestage = 80, Buff = "buffZedLurker" } },
        { ZedMutation.Possum, new ZedMutationInfo { Id = ZedMutation.Possum, FromGamestage = 40, Buff = "buffZedPossum" } },
        { ZedMutation.Snatcher, new ZedMutationInfo { Id = ZedMutation.Snatcher, FromGamestage = 30, Model = "SnatcherSack", Buff = "buffZedSnatcher",
            Slots = ZedSlot.Back | ZedSlot.Chest, Solo = true } },
    };

    /// <summary>Pairs a strain can carry from gamestage 100: mutations that work together.</summary>
    public static readonly ZedMutation[][] Pairs =
    {
        new[] { ZedMutation.Screecher, ZedMutation.Sprinter },
        new[] { ZedMutation.Grabber, ZedMutation.Toxic },
        new[] { ZedMutation.Bloater, ZedMutation.Brood },
        new[] { ZedMutation.Stalker, ZedMutation.Leaper },
    };

    /// <summary>Whether a mutation can turn up at a gamestage in a biome (solo ones only when asked for by name).</summary>
    public static bool Allowed(ZedMutation m, int gamestage, ZedBiome biome, bool solo = false)
    {
        ZedMutationInfo info = All[m];
        return (solo || !info.Solo) && gamestage >= info.FromGamestage && (!info.OnlyIn.HasValue || info.OnlyIn.Value == biome);
    }
}

/// <summary>What a piece of gear covers, how much it soaks before it breaks, and what wearing it costs.</summary>
public class ZedGearInfo
{
    public ZedGearKind Id;
    public string Model;
    /// <summary>The model's parts, each its own piece with its own soak (scrap armor's plates break off one by one).</summary>
    public string[] Parts;
    public EnumBodyPartHit Covers;
    /// <summary>For chest pieces: which sides a plate covers (scrap armor's chest plate the front, its back plate the back).</summary>
    public Utils.EnumHitDirection[][] Sides;
    public float Soak;
    /// <summary>The share of each hit it takes.</summary>
    public float Takes;
    public float Speed = 1f;
    public float Sight = 1f;
    public float Hearing = 1f;
    /// <summary>Where its model sits.</summary>
    public ZedSlot Slots;
    /// <summary>The first gamestage it's worn at.</summary>
    public int FromGamestage;
    /// <summary>Taken out after review: never rolled (kept so saved zombies still load). All gear is cut now: the last
    /// helmets went because there's no telling what another mod's zombie already wears on its head.</summary>
    public bool Cut;
    /// <summary>Rigid body armor: only fits a regular build (not fat, not female).</summary>
    public bool BodyArmor;

    public static readonly Dictionary<ZedGearKind, ZedGearInfo> All = new Dictionary<ZedGearKind, ZedGearInfo>
    {
        { ZedGearKind.HardHat, Dropped(Helmet(ZedGearKind.HardHat, "HardHat", 30f)) },
        { ZedGearKind.WeldingMask, Dropped(Helmet(ZedGearKind.WeldingMask, "WeldingMask", 40f, sight: 0.7f, face: true)) },
        { ZedGearKind.FootballHelmet, Dropped(Helmet(ZedGearKind.FootballHelmet, "FootballHelmet", 60f, face: true)) },
        { ZedGearKind.MotorcycleHelmet, Dropped(Helmet(ZedGearKind.MotorcycleHelmet, "MotorcycleHelmet", 80f, hearing: 0.7f, face: true)) },
        { ZedGearKind.RiotHelmet, Dropped(Helmet(ZedGearKind.RiotHelmet, "RiotHelmet", 100f, hearing: 0.7f, face: true)) },
        { ZedGearKind.MilitaryHelmet, Dropped(Helmet(ZedGearKind.MilitaryHelmet, "MilitaryHelmet", 100f)) },
        { ZedGearKind.KevlarVest, new ZedGearInfo { Id = ZedGearKind.KevlarVest, Model = "KevlarVest", Cut = true, Parts = new[] { "Spine2" },
            Covers = EnumBodyPartHit.Torso, Soak = 150f, Takes = 0.5f, Speed = 0.9f, Slots = ZedSlot.Chest | ZedSlot.Back, BodyArmor = true } },
        { ZedGearKind.ScrapArmor, new ZedGearInfo { Id = ZedGearKind.ScrapArmor, Model = "ScrapArmor", Cut = true,
            Parts = new[] { "Spine2#Chest", "Spine2#Back", "LeftArm#Pad", "RightArm#Pad" },
            Covers = EnumBodyPartHit.Torso | EnumBodyPartHit.LeftUpperArm | EnumBodyPartHit.RightUpperArm, Soak = 250f, Takes = 0.6f, Speed = 0.8f,
            Slots = ZedSlot.Chest | ZedSlot.Back | ZedSlot.LeftShoulder | ZedSlot.RightShoulder, FromGamestage = 100, BodyArmor = true } },
        { ZedGearKind.CarDoor, Dropped(Shield(ZedGearKind.CarDoor, "CarDoor", 120f)) },
        { ZedGearKind.RiotShield, Dropped(Shield(ZedGearKind.RiotShield, "RiotShield", 200f)) },
    };

    private static ZedGearInfo Helmet(ZedGearKind id, string model, float soak, float sight = 1f, float hearing = 1f, bool face = false)
    {
        // A helmet takes all of a hit to the head until it's done
        return new ZedGearInfo { Id = id, Model = model, Parts = new[] { "Head" }, Covers = EnumBodyPartHit.Head, Soak = soak, Takes = 1f,
            Sight = sight, Hearing = hearing, Slots = ZedSlot.Head | (face ? ZedSlot.Face : ZedSlot.None) };
    }

    private static ZedGearInfo Dropped(ZedGearInfo info)
    {
        info.Cut = true;
        return info;
    }

    private static ZedGearInfo Shield(ZedGearKind id, string model, float soak)
    {
        // A shield on the left forearm takes all of a hit from the front on the head, the torso or the left arm
        return new ZedGearInfo { Id = id, Model = model, Parts = new[] { "LeftForeArm#Shield" },
            Covers = EnumBodyPartHit.Head | EnumBodyPartHit.Torso | EnumBodyPartHit.LeftUpperArm | EnumBodyPartHit.LeftLowerArm,
            Soak = soak, Takes = 1f, Speed = 0.85f, Slots = ZedSlot.LeftArm, FromGamestage = 40 };
    }

    public bool IsHelmet => Covers == EnumBodyPartHit.Head;

    public bool IsShield => Id == ZedGearKind.CarDoor || Id == ZedGearKind.RiotShield;

    /// <summary>Whether a part of this gear takes a hit on `part` from `dir`.</summary>
    public static bool PartCovers(ZedGearKind kind, string partName, EnumBodyPartHit part, Utils.EnumHitDirection dir)
    {
        if (All[kind].IsShield)
        {
            return (part & All[kind].Covers) != 0 && dir == Utils.EnumHitDirection.Front;
        }
        if (partName.EndsWith("#Chest"))
        {
            return (part & EnumBodyPartHit.Torso) != 0 && dir != Utils.EnumHitDirection.Back;
        }
        if (partName.EndsWith("#Back"))
        {
            return (part & EnumBodyPartHit.Torso) != 0 && dir == Utils.EnumHitDirection.Back;
        }
        if (partName.StartsWith("LeftArm"))
        {
            return (part & EnumBodyPartHit.LeftUpperArm) != 0;
        }
        if (partName.StartsWith("RightArm"))
        {
            return (part & EnumBodyPartHit.RightUpperArm) != 0;
        }
        return (part & All[kind].Covers) != 0;
    }

    /// <summary>Gear that fits a vanilla zombie's job, by its class name (other zombies pick from everything).</summary>
    public static readonly Dictionary<string, ZedGearKind[]> Jobs = new Dictionary<string, ZedGearKind[]>
    {
        { "zombieJanitor", new[] { ZedGearKind.WeldingMask } },
        { "zombieInmate", new[] { ZedGearKind.WeldingMask } },
        { "zombieBoe", new[] { ZedGearKind.WeldingMask } },
        { "zombieMoe", new[] { ZedGearKind.WeldingMask } },
        { "zombieSkateboarder", new[] { ZedGearKind.MotorcycleHelmet } },
        { "zombieYo", new[] { ZedGearKind.MotorcycleHelmet } },
        { "zombieSteve", new[] { ZedGearKind.MotorcycleHelmet } },
        { "zombieJoe", new[] { ZedGearKind.MotorcycleHelmet } },
        { "zombieSoldier", new[] { ZedGearKind.RiotHelmet } },
                                { "zombieLab", new[] { ZedGearKind.RiotHelmet } },
        { "zombieBusinessMan", new[] { ZedGearKind.RiotHelmet, ZedGearKind.MotorcycleHelmet } },
    };

    /// <summary>Vanilla zombies whose own model already wears something on its head (hat, helmet, hood): no helmets.</summary>
    public static readonly string[] Headwear =
    {
        "zombieBiker", "zombieFatCop", "zombieDemolition", "zombieMaleHazmat", "zombieLumberjack", "zombieRancher",
        "zombiePlagueSpitter", "zombieSoldier", "zombieTomClark", "zombieUtilityWorker", "zombieChuck", "zombieFrostclaw",
    };
}

/// <summary>A piece of gear a zombie wears: which part of which model, and how much it can still soak.</summary>
public class ZedGearPiece
{
    public ZedGearKind Kind;
    public string Part;
    public float Soak;

    public bool Broken => Soak <= 0f;
}

public enum ZedRemnant : byte
{
    Arrows,
    CrossbowBolt,
    KitchenKnife,
    Screwdriver,
    Axe,
    Machete,
    Pitchfork,
    Rebar,
    GlassShards,
    BearTrap,
    BarbedWire,
    Noose,
    HeadBandage,
    ArmCast,
    LegCast,
    NeckBrace,
    IVLine,
    CrackedGlasses,
    Sunglasses,
    Headphones,
    SurgicalMask,
    DustMask,
    GasMask,
    BaseballCap,
    Beanie,
    Bandana,
    CowboyHat,
    ChainNecklace,
    Wristwatch,
    Lanyard,
    HiVisVest,
    ToolBelt,
    MessengerBag,
    FannyPack,
    Handcuffs,
    AnkleMonitor,
    // Round 4: more things stuck in them, one per spot on the body (saved by number: only ever add at the end)
    Spear,
    Shovel,
    Cleaver,
    Hatchet,
    Crowbar,
    SkiPole,
    PoolCue,
    Fishhook,
    Nails,
    PadlockChain,
}

/// <summary>
/// A remnant: a small prop telling who a zombie was and how it died. The model is named after it (see
/// blender/REMNANTS.md); the slots keep it off anything else on the same spot; a bare-head one only goes on a zombie
/// with no hat or helmet of its own; an anyone one can turn up on any zombie, the rest only on the jobs they fit
/// (and on other mods' zombies, which pick from everything).
/// </summary>
public class ZedRemnantInfo
{
    public ZedRemnant Id;
    public ZedSlot Slots;
    public bool BareHead;
    public bool Anyone;
    public string Buff;
    /// <summary>Taken out after review: never rolled or shown (kept so saved zombies still load).</summary>
    public bool Cut;

    public string Model => Id.ToString();

    public static readonly Dictionary<ZedRemnant, ZedRemnantInfo> All = new Dictionary<ZedRemnant, ZedRemnantInfo>();

    private static void R(ZedRemnant id, ZedSlot slots, bool anyone = true, bool bareHead = false, string buff = null, bool cut = false)
    {
        All[id] = new ZedRemnantInfo { Id = id, Slots = slots, Anyone = anyone, BareHead = bareHead, Buff = buff, Cut = cut };
    }

    static ZedRemnantInfo()
    {
        R(ZedRemnant.Arrows, ZedSlot.Back | ZedSlot.LeftLeg);
        R(ZedRemnant.CrossbowBolt, ZedSlot.LeftShoulder);
        R(ZedRemnant.KitchenKnife, ZedSlot.RightShoulder);
        R(ZedRemnant.Screwdriver, ZedSlot.Neck);
        R(ZedRemnant.Axe, ZedSlot.Back);
        R(ZedRemnant.Machete, ZedSlot.Head, bareHead: true);
        R(ZedRemnant.Pitchfork, ZedSlot.Back, anyone: false);
        R(ZedRemnant.Rebar, ZedSlot.Chest | ZedSlot.Back);
        R(ZedRemnant.GlassShards, ZedSlot.Face | ZedSlot.LeftArm | ZedSlot.RightArm);
        R(ZedRemnant.BearTrap, ZedSlot.LeftLeg, buff: "buffZedBearTrap");
        // Its coils turn up on the forearm, a leg or round the waist (variant parts)
        R(ZedRemnant.BarbedWire, ZedSlot.RightArm | ZedSlot.LeftLeg | ZedSlot.Waist);
        R(ZedRemnant.Noose, ZedSlot.Neck | ZedSlot.Chest);
        R(ZedRemnant.HeadBandage, ZedSlot.Head, bareHead: true, cut: true);
        R(ZedRemnant.ArmCast, ZedSlot.LeftArm);
        R(ZedRemnant.LegCast, ZedSlot.RightLeg, cut: true);
        R(ZedRemnant.NeckBrace, ZedSlot.Neck, cut: true);
        R(ZedRemnant.IVLine, ZedSlot.LeftArm, anyone: false, cut: true);
        R(ZedRemnant.CrackedGlasses, ZedSlot.Face);
        R(ZedRemnant.Sunglasses, ZedSlot.Face);
        R(ZedRemnant.Headphones, ZedSlot.Neck);
        R(ZedRemnant.SurgicalMask, ZedSlot.Face, anyone: false, cut: true);
        R(ZedRemnant.DustMask, ZedSlot.Face, cut: true);
        R(ZedRemnant.GasMask, ZedSlot.Neck | ZedSlot.Chest, anyone: false);
        R(ZedRemnant.BaseballCap, ZedSlot.Head, bareHead: true, cut: true);
        R(ZedRemnant.Beanie, ZedSlot.Head, bareHead: true, cut: true);
        R(ZedRemnant.Bandana, ZedSlot.Head, bareHead: true, cut: true);
        R(ZedRemnant.CowboyHat, ZedSlot.Head, anyone: false, bareHead: true, cut: true);
        R(ZedRemnant.ChainNecklace, ZedSlot.Neck);
        R(ZedRemnant.Wristwatch, ZedSlot.LeftHand, cut: true);
        R(ZedRemnant.Lanyard, ZedSlot.Neck | ZedSlot.Chest, anyone: false, cut: true);
        R(ZedRemnant.HiVisVest, ZedSlot.Chest | ZedSlot.Back, anyone: false, cut: true);
        R(ZedRemnant.ToolBelt, ZedSlot.Waist, anyone: false, cut: true);
        R(ZedRemnant.MessengerBag, ZedSlot.Chest | ZedSlot.Back | ZedSlot.Waist, cut: true);
        R(ZedRemnant.FannyPack, ZedSlot.Waist, cut: true);
        R(ZedRemnant.Handcuffs, ZedSlot.RightHand, anyone: false, cut: true);
        R(ZedRemnant.AnkleMonitor, ZedSlot.RightLeg, anyone: false);
        R(ZedRemnant.Spear, ZedSlot.Belly);
        R(ZedRemnant.Shovel, ZedSlot.Back);
        R(ZedRemnant.Cleaver, ZedSlot.LeftShoulder);
        R(ZedRemnant.Hatchet, ZedSlot.RightLeg);
        R(ZedRemnant.Crowbar, ZedSlot.Chest);
        R(ZedRemnant.SkiPole, ZedSlot.LeftLeg, cut: true);
        R(ZedRemnant.PoolCue, ZedSlot.RightShoulder, cut: true);
        R(ZedRemnant.Fishhook, ZedSlot.RightArm, cut: true);
        R(ZedRemnant.Nails, ZedSlot.LeftArm);
        // On the forearm bone at the wrist
        R(ZedRemnant.PadlockChain, ZedSlot.LeftHand);
    }

    /// <summary>What fits a vanilla zombie's job, by its family (zombies not listed pick from the anyone ones).</summary>
    public static readonly Dictionary<string, ZedRemnant[]> Jobs = new Dictionary<string, ZedRemnant[]>
    {
        { "zombieNurse", new[] { ZedRemnant.CrackedGlasses, ZedRemnant.ArmCast, ZedRemnant.Headphones } },
        { "zombieLab", new[] { ZedRemnant.CrackedGlasses, ZedRemnant.GasMask } },
        { "zombieBusinessMan", new[] { ZedRemnant.CrackedGlasses, ZedRemnant.KitchenKnife, ZedRemnant.ChainNecklace } },
        { "zombieInmate", new[] { ZedRemnant.AnkleMonitor, ZedRemnant.Screwdriver, ZedRemnant.KitchenKnife, ZedRemnant.Noose, ZedRemnant.PadlockChain } },
        { "zombieJanitor", new[] { ZedRemnant.Screwdriver, ZedRemnant.GlassShards, ZedRemnant.Crowbar } },
        { "zombieUtilityWorker", new[] { ZedRemnant.Rebar, ZedRemnant.BarbedWire, ZedRemnant.Crowbar, ZedRemnant.Nails } },
        { "zombieBoe", new[] { ZedRemnant.Rebar, ZedRemnant.Screwdriver, ZedRemnant.Nails } },
        { "zombieMoe", new[] { ZedRemnant.Rebar, ZedRemnant.GlassShards, ZedRemnant.Crowbar } },
        { "zombieLumberjack", new[] { ZedRemnant.Axe, ZedRemnant.BarbedWire, ZedRemnant.BearTrap, ZedRemnant.Hatchet } },
        { "zombieRancher", new[] { ZedRemnant.Pitchfork, ZedRemnant.BearTrap, ZedRemnant.BarbedWire, ZedRemnant.Arrows, ZedRemnant.Shovel } },
        { "zombieTomClark", new[] { ZedRemnant.Pitchfork, ZedRemnant.BearTrap, ZedRemnant.BarbedWire, ZedRemnant.Shovel, ZedRemnant.Hatchet } },
        { "zombieSkateboarder", new[] { ZedRemnant.Headphones, ZedRemnant.ArmCast } },
        { "zombieYo", new[] { ZedRemnant.Headphones, ZedRemnant.Sunglasses, ZedRemnant.ChainNecklace } },
        { "zombieSteve", new[] { ZedRemnant.Headphones, ZedRemnant.Sunglasses } },
        { "zombiePartyGirl", new[] { ZedRemnant.Sunglasses, ZedRemnant.ChainNecklace } },
        { "zombieMarlene", new[] { ZedRemnant.CrackedGlasses, ZedRemnant.ChainNecklace } },
        { "zombieDarlene", new[] { ZedRemnant.Sunglasses, ZedRemnant.ArmCast } },
        { "zombieArlene", new[] { ZedRemnant.CrackedGlasses, ZedRemnant.ChainNecklace } },
        { "zombieBiker", new[] { ZedRemnant.ChainNecklace, ZedRemnant.Sunglasses, ZedRemnant.BarbedWire, ZedRemnant.Wristwatch, ZedRemnant.PadlockChain } },
        { "zombieSoldier", new[] { ZedRemnant.GasMask, ZedRemnant.ChainNecklace, ZedRemnant.CrossbowBolt, ZedRemnant.Arrows } },
        { "zombieFatHawaiian", new[] { ZedRemnant.Sunglasses, ZedRemnant.Headphones } },
        { "zombieFatCop", new[] { ZedRemnant.Sunglasses, ZedRemnant.Wristwatch, ZedRemnant.Arrows, ZedRemnant.KitchenKnife } },
        { "zombieMaleHazmat", new[] { ZedRemnant.GasMask } },
        { "zombieDemolition", new[] { ZedRemnant.Rebar } },
    };

    /// <summary>Vanilla zombies whose own model covers the face (a hazmat hood): no glasses or masks.</summary>
    public static readonly string[] FaceCovered = { "zombieMaleHazmat", "zombieDemolition" };
}
