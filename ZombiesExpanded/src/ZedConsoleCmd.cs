using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

/// <summary>
/// For testing and tuning: spawn a zombie with a chosen profile, see a zombie's profile, change settings for the
/// session, and show what every zombie nearby is doing. Runs on the server (in single player, this game).
/// </summary>
public class ZedConsoleCmd : ConsoleCmdAbstract
{
    public override int DefaultPermissionLevel => 0;

    public override string[] getCommands()
    {
        return new[] { "zombiesexpanded", "ze" };
    }

    public override string getDescription()
    {
        return "Zombies Expanded: spawn test zombies, show profiles and settings, show what zombies are doing";
    }

    public override string getHelp()
    {
        return "Usage:\n"
            + "  ze                     - settings and how many zombie profiles this game knows\n"
            + "  ze spawn [class] [k=v ...] - spawn a zombie 5 m ahead (default zombieJoe) with parts of its profile set:\n"
            + "                           body=normal|gaunt|bulky|bloated|hunched  temper=normal|sluggish|restless|relentless\n"
            + "                           walk=<walk type>  size=<factor>  speed=<factor>  pitch=<factor>  age=<0-1>\n"
            + "                           biome=forest|desert|snow|burnt|wasteland  mutation=Bloater,Toxic,...  gear=KevlarVest,...\n"
            + "                           remnant=Axe,Sunglasses,...  dead=1 (a Possum lying \"dead\")\n"
            + "                           injury=none|LimpArm|DraggedFoot|LolledHead|TwistedBack[,left|right]\n"
            + "                           champion=1  alpha=1  plain=1 (no mutations, gear, remnants or rank)\n"
            + "  ze info                - the profile of the zombie you're looking at (within 30 m)\n"
            + "  ze set <name> <value>  - change a setting for this session (see the list from 'ze')\n"
            + "  ze debug               - show each zombie's profile and what its AI is doing above it (again to stop)";
    }

    public override void Execute(List<string> _params, CommandSenderInfo _senderInfo)
    {
        World world = GameManager.Instance.World;
        if (_params.Count == 0)
        {
            foreach (KeyValuePair<string, string> kv in ZedSettings.All)
            {
                Output("  " + kv.Key + " = " + kv.Value);
            }
            Output(ZedStore.Stats());
            return;
        }
        switch (_params[0].ToLowerInvariant())
        {
            case "spawn":
                Spawn(world, Player(world, _senderInfo), _params);
                break;
            case "info":
                Info(world, Player(world, _senderInfo));
                break;
            case "set":
                if (_params.Count < 3 || !ZedSettings.Set(_params[1], _params[2]))
                {
                    Output("Unknown setting. Type 'ze' for the list.");
                    return;
                }
                Output(_params[1] + " = " + _params[2] + " (this session; zombies already in the world keep their profile)");
                break;
            case "debug":
                Output("Debug readout " + (ZedDebug.Toggle() ? "on" : "off"));
                break;
            default:
                Output(getHelp());
                break;
        }
    }

    private static void Output(string line)
    {
        SingletonMonoBehaviour<SdtdConsole>.Instance.Output(line);
    }

    private static EntityPlayer Player(World world, CommandSenderInfo sender)
    {
        if (sender.RemoteClientInfo != null)
        {
            return world.GetEntity(sender.RemoteClientInfo.entityId) as EntityPlayer;
        }
        return world.GetPrimaryPlayer();
    }

    private static void Spawn(World world, EntityPlayer player, List<string> args)
    {
        if (player == null)
        {
            Output("No player to spawn near.");
            return;
        }
        string name = args.Count > 1 && !args[1].Contains("=") ? args[1] : "zombieJoe";
        int cls = EntityClass.FromString(name);
        if (!EntityClass.list.ContainsKey(cls))
        {
            Output("No entity class " + name);
            return;
        }
        ZedForce force = new ZedForce();
        foreach (string a in args)
        {
            int eq = a.IndexOf('=');
            if (eq <= 0)
            {
                continue;
            }
            if (!force.Set(a.Substring(0, eq).ToLowerInvariant(), a.Substring(eq + 1)))
            {
                Output("Didn't understand " + a);
                return;
            }
        }
        Vector3 forward = player.GetLookVector();
        forward.y = 0f;
        Vector3 pos = player.position + forward.normalized * 5f + Vector3.up * 0.5f;
        float yaw = Quaternion.LookRotation(-forward).eulerAngles.y;
        ZedProfile.ForceNext = force;
        try
        {
            Entity e = EntityFactory.CreateEntity(cls, pos, new Vector3(0f, yaw, 0f));
            world.SpawnEntityInWorld(e);
            Output("Spawned " + name + " (" + e.entityId + "): " + ZedStore.Get(e.entityId));
        }
        finally
        {
            ZedProfile.ForceNext = null;
        }
    }

    private static void Info(World world, EntityPlayer player)
    {
        if (player == null)
        {
            return;
        }
        Vector3 eye = player.getHeadPosition();
        Vector3 look = player.GetLookVector();
        EntityAlive best = null;
        float bestScore = 0.9f;
        foreach (EntityAlive e in world.EntityAlives)
        {
            if (!ZedStore.IsZombie(e))
            {
                continue;
            }
            Vector3 to = e.getChestPosition() - eye;
            float d = to.magnitude;
            if (d > 30f || d < 0.1f)
            {
                continue;
            }
            float score = Vector3.Dot(look, to / d);
            if (score > bestScore)
            {
                bestScore = score;
                best = e;
            }
        }
        if (best == null)
        {
            Output("No zombie in front of you within 30 m.");
            return;
        }
        Output(best.EntityClass.entityClassName + " (" + best.entityId + "): " + (ZedStore.Get(best.entityId)?.ToString() ?? "no profile"));
        Output("  " + ZedDebug.Tasks(best));
    }
}

/// <summary>Parts of the next spawned zombie's profile, set by `ze spawn`.</summary>
public class ZedForce
{
    public bool Plain;
    public bool Champion, Alpha;
    public readonly List<ZedMutation> Mutations = new List<ZedMutation>();
    public readonly List<ZedGearKind> Gear = new List<ZedGearKind>();
    public readonly List<ZedRemnant> Remnants = new List<ZedRemnant>();
    public bool Dead;
    public ZedBody? Body;
    public ZedTemper? Temper;
    public ZedBiome? Biome;
    public int? Walk;
    public float? Size, Speed, Pitch, Age;
    public ZedInjury? Injury;
    public bool? InjuryLeft;

    public bool Set(string key, string value)
    {
        switch (key)
        {
            case "body":
                return Enum(value, ref Body);
            case "temper":
                return Enum(value, ref Temper);
            case "biome":
                return Enum(value, ref Biome);
            case "walk":
                if (int.TryParse(value, out int w))
                {
                    Walk = w;
                    return true;
                }
                return false;
            case "size":
                return Number(value, ref Size);
            case "speed":
                return Number(value, ref Speed);
            case "pitch":
                return Number(value, ref Pitch);
            case "age":
                return Number(value, ref Age);
            case "injury":
                // A name and optionally its side: LimpArm,left
                string[] injury = value.Split(',');
                if (injury.Length > 1)
                {
                    string side = injury[1].Trim().ToLowerInvariant();
                    if (side != "left" && side != "right")
                    {
                        return false;
                    }
                    InjuryLeft = side == "left";
                }
                return Enum(injury[0].Trim(), ref Injury);
            case "mutation":
            case "mutations":
                foreach (string m in value.Split(','))
                {
                    if (!System.Enum.TryParse(m, true, out ZedMutation mu))
                    {
                        return false;
                    }
                    Mutations.Add(mu);
                }
                return true;
            case "gear":
                foreach (string g in value.Split(','))
                {
                    if (!System.Enum.TryParse(g, true, out ZedGearKind gk))
                    {
                        return false;
                    }
                    Gear.Add(gk);
                }
                return true;
            case "remnant":
            case "remnants":
                foreach (string r in value.Split(','))
                {
                    if (!System.Enum.TryParse(r, true, out ZedRemnant rem))
                    {
                        return false;
                    }
                    Remnants.Add(rem);
                }
                return true;
            case "dead":
                Dead = value == "1" || value.Equals("true", System.StringComparison.OrdinalIgnoreCase);
                return true;
            case "champion":
                Champion = value == "1" || value.Equals("true", System.StringComparison.OrdinalIgnoreCase);
                return true;
            case "alpha":
                Alpha = value == "1" || value.Equals("true", System.StringComparison.OrdinalIgnoreCase);
                return true;
            case "plain":
                Plain = value == "1" || value.Equals("true", System.StringComparison.OrdinalIgnoreCase);
                return true;
        }
        return false;
    }

    /// <summary>Mutations, gear and rank asked for (after the rolls, which they replace).</summary>
    public void ApplyRank(ZedProfile p, System.Random rng, int gs, string family)
    {
        if (Mutations.Count > 0)
        {
            p.Mutations.Clear();
            p.Mutations.AddRange(Mutations);
        }
        if (Gear.Count > 0)
        {
            p.Gear.Clear();
            foreach (ZedGearKind g in Gear)
            {
                ZedRoll.Wear(p, g);
            }
        }
        if (Remnants.Count > 0)
        {
            p.Remnants.Clear();
            p.Remnants.AddRange(Remnants);
        }
        if (Dead)
        {
            // A Possum lying "dead" from the start
            if (!p.Has(ZedMutation.Possum))
            {
                p.Mutations.Add(ZedMutation.Possum);
            }
            p.PlayingDead = true;
            p.FakedDeath = true;
        }
        if (Champion && !p.Champion)
        {
            ZedRoll.Champion(p, rng, System.Math.Max(gs, 50), family);
        }
        if (Alpha && !p.Alpha)
        {
            ZedRoll.Alpha(p, rng, System.Math.Max(gs, 60), family);
        }
    }

    private static bool Enum<T>(string value, ref T? field) where T : struct
    {
        if (System.Enum.TryParse(value, true, out T v))
        {
            field = v;
            return true;
        }
        return false;
    }

    private static bool Number(string value, ref float? field)
    {
        if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float f))
        {
            field = f;
            return true;
        }
        return false;
    }

    public void Apply(ZedProfile p)
    {
        if (Body.HasValue)
        {
            p.Body = Body.Value;
        }
        if (Temper.HasValue)
        {
            p.Temper = Temper.Value;
        }
        if (Biome.HasValue)
        {
            p.Biome = Biome.Value;
        }
        if (Walk.HasValue)
        {
            p.Walk = (sbyte)Walk.Value;
        }
        if (Size.HasValue)
        {
            p.Size = Size.Value;
        }
        if (Speed.HasValue)
        {
            p.Speed = Speed.Value;
        }
        if (Pitch.HasValue)
        {
            p.Pitch = Pitch.Value;
        }
        if (Age.HasValue)
        {
            p.Age = Age.Value;
        }
    }
}
