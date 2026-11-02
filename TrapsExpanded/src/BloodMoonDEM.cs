using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

/// <summary>
/// Server: the Blood Moon is the wave. While it lasts this counts kills by trap and by player, combos (soaked zombies
/// shocked, Infernos, freezes, shatters) and traps destroyed; at dawn everyone gets the report, with the world's
/// records (kept in the save folder). On the morning of Blood Moon day a radio message forecasts the horde from the
/// game's own spawn tables for the players' game stages.
/// </summary>
public static class BloodMoonDEM
{
    public const string ComboSoakedShock = "SoakedShock";
    public const string ComboInferno = "Inferno";
    public const string ComboFrozen = "Frozen";
    public const string ComboShatter = "Shatter";

    private static readonly string[] ComboOrder = { ComboSoakedShock, ComboInferno, ComboFrozen, ComboShatter };

    /// <summary>Hour of Blood Moon day when the forecast goes out.</summary>
    private const int ForecastHour = 7;

    private const int Version = 1;

    private class Night
    {
        public int Day;
        public readonly Dictionary<Vector3i, int> trapKills = new Dictionary<Vector3i, int>();
        public readonly Dictionary<Vector3i, string> trapNames = new Dictionary<Vector3i, string>();
        public readonly Dictionary<Vector3i, int> trapLevelBefore = new Dictionary<Vector3i, int>();
        public readonly Dictionary<int, int> playerKills = new Dictionary<int, int>();
        public readonly Dictionary<int, string> playerNames = new Dictionary<int, string>();
        public readonly Dictionary<string, int> combos = new Dictionary<string, int>();
        public readonly List<string> lost = new List<string>();
    }

    private class Records
    {
        public int BestNightKills;
        public int BestNightDay;
        public int BestTrapKills;
        public string BestTrapName = "";
        public int BestTrapDay;
        public int BestCombos;
        public int BestCombosDay;
        public int LastForecastDay = -1;
    }

    private static Night night;
    private static Records records = new Records();
    private static readonly TrapSaveFileDEM file = new TrapSaveFileDEM("bloodmoon.dat");
    private static float checkTimer;

    public static bool Active => night != null;

    // ------------------------------------------------------------------ counting

    public static void TrapKill(Vector3i pos, string blockName)
    {
        if (night == null)
        {
            return;
        }
        night.trapKills.TryGetValue(pos, out int n);
        night.trapKills[pos] = n + 1;
        night.trapNames[pos] = blockName;
        if (!night.trapLevelBefore.ContainsKey(pos))
        {
            // This kill already counted toward the level
            TrapRecordDEM rec = TrapStoreDEM.Find(pos);
            night.trapLevelBefore[pos] = rec != null ? TrapLevelsDEM.Level(Mathf.Max(0, rec.Kills - 1)) : 1;
        }
    }

    public static void PlayerKill(EntityPlayer player)
    {
        if (night == null || player == null)
        {
            return;
        }
        night.playerKills.TryGetValue(player.entityId, out int n);
        night.playerKills[player.entityId] = n + 1;
        night.playerNames[player.entityId] = player.PlayerDisplayName;
    }

    public static void Combo(string key)
    {
        if (night == null)
        {
            return;
        }
        night.combos.TryGetValue(key, out int n);
        night.combos[key] = n + 1;
    }

    /// <summary>Server: a trap was destroyed (not picked up).</summary>
    public static void TrapLost(string blockName)
    {
        night?.lost.Add(blockName);
    }

    // ------------------------------------------------------------------ the night

    public static void Update()
    {
        if (!SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            return;
        }
        World world = GameManager.Instance.World;
        if (world == null)
        {
            return;
        }
        checkTimer -= Time.deltaTime;
        if (checkTimer > 0f)
        {
            return;
        }
        checkTimer = 1f;
        if (file.NeedsLoad())
        {
            night = null;
            records = new Records();
            file.Load(Read);
        }

        AIDirectorBloodMoonComponent bm = world.aiDirector?.BloodMoonComponent;
        if (bm == null)
        {
            return;
        }
        bool active = bm.BloodMoonActive;
        int day = GameUtils.WorldTimeToDays(world.worldTime);
        if (active && night == null)
        {
            night = new Night { Day = day };
        }
        else if (!active && night != null)
        {
            Finish(world);
        }

        int hour = GameUtils.WorldTimeToHours(world.worldTime);
        if (day == bm.bmDay && hour >= ForecastHour && hour < bm.duskHour && records.LastForecastDay != day)
        {
            records.LastForecastDay = day;
            Save();
            Forecast(world, day);
        }
    }

    public static void Shutdown()
    {
        night = null;
        records = new Records();
        file.Reset();
    }

    private static void Finish(World world)
    {
        Night n = night;
        night = null;
        int trapTotal = n.trapKills.Values.Sum();
        int playerTotal = n.playerKills.Values.Sum();
        int comboTotal = n.combos.Values.Sum();
        if (trapTotal + playerTotal == 0 && n.lost.Count == 0)
        {
            return;
        }

        StringBuilder sb = new StringBuilder();
        sb.AppendLine(string.Format(Localization.Get("dem_reportTotal"), trapTotal + playerTotal, trapTotal, playerTotal));

        // Kills by kind of trap
        Dictionary<string, int> byType = new Dictionary<string, int>();
        Dictionary<string, int> countByType = new Dictionary<string, int>();
        foreach (KeyValuePair<Vector3i, int> kv in n.trapKills)
        {
            string name = n.trapNames[kv.Key];
            byType.TryGetValue(name, out int k);
            byType[name] = k + kv.Value;
            countByType.TryGetValue(name, out int c);
            countByType[name] = c + 1;
        }
        if (byType.Count > 0)
        {
            sb.AppendLine();
            sb.AppendLine(Localization.Get("dem_reportByTrap"));
            foreach (KeyValuePair<string, int> kv in byType.OrderByDescending(kv => kv.Value))
            {
                int count = countByType[kv.Key];
                sb.AppendLine(string.Format(Localization.Get(count > 1 ? "dem_reportTrapLineMany" : "dem_reportTrapLine"),
                    BlockName(kv.Key), count, kv.Value));
            }
        }

        // The MVP trap and any level-ups
        string mvpName = "";
        int mvpKills = 0;
        if (n.trapKills.Count > 0)
        {
            KeyValuePair<Vector3i, int> mvp = n.trapKills.OrderByDescending(kv => kv.Value).First();
            mvpName = n.trapNames[mvp.Key];
            mvpKills = mvp.Value;
            sb.AppendLine();
            sb.AppendLine(string.Format(Localization.Get("dem_reportMvp"), BlockName(mvpName), mvpKills));
            int ups = 0;
            foreach (KeyValuePair<Vector3i, int> before in n.trapLevelBefore)
            {
                TrapRecordDEM rec = TrapStoreDEM.Find(before.Key);
                if (rec != null && rec.Level > before.Value)
                {
                    ups++;
                }
            }
            if (ups > 0)
            {
                sb.AppendLine(string.Format(Localization.Get("dem_reportLevelUps"), ups));
            }
        }

        if (n.playerKills.Count > 0)
        {
            sb.AppendLine();
            sb.AppendLine(Localization.Get("dem_reportByPlayer"));
            foreach (KeyValuePair<int, int> kv in n.playerKills.OrderByDescending(kv => kv.Value))
            {
                sb.AppendLine(string.Format(Localization.Get("dem_reportPlayerLine"), n.playerNames[kv.Key], kv.Value));
            }
        }

        if (comboTotal > 0)
        {
            sb.AppendLine();
            List<string> parts = new List<string>();
            foreach (string key in ComboOrder)
            {
                if (n.combos.TryGetValue(key, out int c) && c > 0)
                {
                    parts.Add(string.Format(Localization.Get("dem_reportCombo" + key), c));
                }
            }
            sb.AppendLine(Localization.Get("dem_reportCombos") + " " + string.Join(", ", parts));
        }

        if (n.lost.Count > 0)
        {
            sb.AppendLine();
            List<string> names = n.lost.GroupBy(x => x)
                .Select(g => g.Count() > 1 ? g.Count() + "x " + BlockName(g.Key) : BlockName(g.Key)).ToList();
            sb.AppendLine(string.Format(Localization.Get("dem_reportLost"), n.lost.Count, string.Join(", ", names)));
        }

        // Records
        List<string> newRecords = new List<string>();
        if (trapTotal > records.BestNightKills)
        {
            records.BestNightKills = trapTotal;
            records.BestNightDay = n.Day;
            newRecords.Add(string.Format(Localization.Get("dem_reportRecordNight"), trapTotal));
        }
        if (mvpKills > records.BestTrapKills)
        {
            records.BestTrapKills = mvpKills;
            records.BestTrapName = mvpName;
            records.BestTrapDay = n.Day;
            newRecords.Add(string.Format(Localization.Get("dem_reportRecordTrap"), BlockName(mvpName), mvpKills));
        }
        if (comboTotal > records.BestCombos)
        {
            records.BestCombos = comboTotal;
            records.BestCombosDay = n.Day;
            newRecords.Add(string.Format(Localization.Get("dem_reportRecordCombos"), comboTotal));
        }
        sb.AppendLine();
        foreach (string r in newRecords)
        {
            sb.AppendLine(r);
        }
        sb.AppendLine(string.Format(Localization.Get("dem_reportRecords"), records.BestNightKills, records.BestNightDay,
            BlockName(records.BestTrapName), records.BestTrapKills, records.BestTrapDay));
        Save();

        string title = string.Format(Localization.Get("dem_reportTitle"), n.Day);
        string text = sb.ToString().TrimEnd();
        if (!GameManager.IsDedicatedServer)
        {
            BloodMoonReportDEM.Show(title, text);
        }
        SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(
            NetPackageManager.GetPackage<NetPackageTrapReportDEM>().Setup(title, text));
        string summary = mvpKills > 0
            ? string.Format(Localization.Get("dem_reportChat"), trapTotal + playerTotal, trapTotal, BlockName(mvpName), mvpKills)
            : string.Format(Localization.Get("dem_reportChatNoTrap"), trapTotal + playerTotal);
        Chat(summary);
    }

    // ------------------------------------------------------------------ the forecast

    private static readonly string[] SpecialWords =
    {
        "Feral", "Radiated", "Charged", "Infernal", "Spider", "Cop", "Demolisher", "Screamer", "Wight", "Mutated",
        "Dog", "Wolf", "Vulture", "Bear", "Boss"
    };

    private static void Forecast(World world, int day)
    {
        List<int> stages = new List<int>();
        foreach (EntityPlayer p in world.Players.list)
        {
            if (p != null && p.IsAlive())
            {
                stages.Add(p.gameStage);
            }
        }
        if (stages.Count == 0)
        {
            return;
        }
        int party = GameStageDefinition.CalcPartyLevel(stages);
        if (!GameStageDefinition.TryGetGameStage("BloodMoonHorde", out GameStageDefinition def))
        {
            return;
        }
        GameStageDefinition.Stage stage = def.GetStage(party);
        if (stage == null)
        {
            return;
        }
        int waves = 0;
        int maxAlive = 0;
        bool untilDawn = false;
        List<string> specials = new List<string>();
        foreach (GameStageDefinition.SpawnGroup g in stage.spawnGroups)
        {
            if (g.spawnCount >= 500)
            {
                untilDawn = true;
            }
            else
            {
                waves += g.spawnCount;
            }
            maxAlive = Mathf.Max(maxAlive, g.maxAlive);
            if (!EntityGroups.list.TryGetValue(g.groupName, out List<SEntityClassAndProb> members))
            {
                continue;
            }
            foreach (SEntityClassAndProb m in members)
            {
                if (!EntityClass.list.TryGetValue(m.entityClassId, out EntityClass ec))
                {
                    continue;
                }
                string cls = ec.entityClassName ?? "";
                if (!SpecialWords.Any(w => cls.IndexOf(w, System.StringComparison.OrdinalIgnoreCase) >= 0))
                {
                    continue;
                }
                string name = Localization.Get(cls);
                if (!specials.Contains(name))
                {
                    specials.Add(name);
                }
            }
        }
        string size = untilDawn
            ? string.Format(Localization.Get("dem_forecastSizeDawn"), waves, maxAlive)
            : string.Format(Localization.Get("dem_forecastSize"), waves, maxAlive);
        string msg = string.Format(Localization.Get("dem_forecast"), party, size);
        if (specials.Count > 0)
        {
            int shown = Mathf.Min(6, specials.Count);
            string list = string.Join(", ", specials.Take(shown));
            if (specials.Count > shown)
            {
                list += string.Format(Localization.Get("dem_forecastMore"), specials.Count - shown);
            }
            msg += " " + string.Format(Localization.Get("dem_forecastSpecials"), list);
        }
        Chat(msg);
    }

    // ------------------------------------------------------------------ helpers

    private static string BlockName(string blockName)
    {
        Block b = string.IsNullOrEmpty(blockName) ? null : Block.GetBlockByName(blockName);
        return b != null ? b.GetLocalizedBlockName() : blockName ?? "";
    }

    private static void Chat(string msg)
    {
        GameManager.Instance.ChatMessageServer(null, EChatType.Global, -1, msg, null, EMessageSender.Server);
    }

    private static void Read(PooledBinaryReader r)
    {
        if (r.ReadInt32() != Version)
        {
            return;
        }
        records.BestNightKills = r.ReadInt32();
        records.BestNightDay = r.ReadInt32();
        records.BestTrapKills = r.ReadInt32();
        records.BestTrapName = r.ReadString();
        records.BestTrapDay = r.ReadInt32();
        records.BestCombos = r.ReadInt32();
        records.BestCombosDay = r.ReadInt32();
        records.LastForecastDay = r.ReadInt32();
    }

    private static void Save()
    {
        file.Save(w =>
        {
            w.Write(Version);
            w.Write(records.BestNightKills);
            w.Write(records.BestNightDay);
            w.Write(records.BestTrapKills);
            w.Write(records.BestTrapName ?? "");
            w.Write(records.BestTrapDay);
            w.Write(records.BestCombos);
            w.Write(records.BestCombosDay);
            w.Write(records.LastForecastDay);
        });
    }
}

/// <summary>Client: shows the Blood Moon report in the mod's report window (the vanilla tip window if it's
/// missing).</summary>
public static class BloodMoonReportDEM
{
    private const string WindowGroup = "dementiveTrapReport";

    public static void Show(string title, string text)
    {
        EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player == null)
        {
            return;
        }
        LocalPlayerUI ui = LocalPlayerUI.GetUIForPlayer(player);
        XUiC_TipWindow window = ui?.xui?.FindWindowGroupByName(WindowGroup)?.GetChildByType<XUiC_TipWindow>();
        if (window == null)
        {
            XUiC_TipWindow.ShowTip(text, title, player, null);
            return;
        }
        window.TipText = text;
        window.TipTitle = title;
        ui.windowManager.Open(WindowGroup, true);
    }
}
