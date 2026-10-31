/// <summary>
/// Messages between defense objectives (clients) and <see cref="WaveDirectorDEM"/> (server): a player's quest
/// joining or leaving a defense, and the server telling each player where the defense stands.
/// </summary>
public class NetPackageDefendWavesDEM : NetPackage
{
    public enum Kinds : byte
    {
        Join,
        Leave,
        Status,
    }

    private Kinds kind;

    private int questCode;

    // Join
    private DefenseSettingsDEM settings;

    // Status
    private DefenseStatusDEM status;

    public NetPackageDefendWavesDEM SetupJoin(int _questCode, DefenseSettingsDEM _settings)
    {
        kind = Kinds.Join;
        questCode = _questCode;
        settings = _settings;
        return this;
    }

    public NetPackageDefendWavesDEM SetupLeave(int _questCode)
    {
        kind = Kinds.Leave;
        questCode = _questCode;
        return this;
    }

    public NetPackageDefendWavesDEM SetupStatus(int _questCode, DefenseStatusDEM _status)
    {
        kind = Kinds.Status;
        questCode = _questCode;
        status = _status;
        return this;
    }

    public override void read(PooledBinaryReader _br)
    {
        kind = (Kinds)_br.ReadByte();
        questCode = _br.ReadInt32();
        if (kind == Kinds.Join)
        {
            settings = DefenseSettingsDEM.Read(_br);
        }
        else if (kind == Kinds.Status)
        {
            status = DefenseStatusDEM.Read(_br);
        }
    }

    public override void write(PooledBinaryWriter _bw)
    {
        base.write(_bw);
        _bw.Write((byte)kind);
        _bw.Write(questCode);
        if (kind == Kinds.Join)
        {
            settings.Write(_bw);
        }
        else if (kind == Kinds.Status)
        {
            status.Write(_bw);
        }
    }

    public override void ProcessPackage(World _world, GameManager _callbacks)
    {
        if (_world == null)
        {
            return;
        }

        if (kind == Kinds.Status)
        {
            ApplyStatus(_world);
            return;
        }

        if (!SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer || Sender == null)
        {
            return;
        }

        if (kind == Kinds.Join)
        {
            WaveDirectorDEM.Join(questCode, Sender.entityId, settings);
        }
        else
        {
            WaveDirectorDEM.Leave(questCode, Sender.entityId);
        }
    }

    /// <summary>
    /// Client side: updates the local player's defense objective for the quest and shows the message, if any.
    /// </summary>
    public void ApplyStatus(World world)
    {
        EntityPlayerLocal player = world.GetPrimaryPlayer();
        if (player == null)
        {
            return;
        }

        ObjectiveDefenseBaseDEM shown = null;
        foreach (Quest quest in player.QuestJournal.quests)
        {
            if (questCode == 0 || quest.QuestCode != questCode || quest.CurrentState != Quest.QuestState.InProgress)
            {
                continue;
            }

            foreach (BaseObjective objective in quest.Objectives)
            {
                if (objective is ObjectiveDefenseBaseDEM defense && defense.Phase == quest.CurrentPhase)
                {
                    shown = defense;
                }
            }
        }

        // The message first: updating the objective can close the quest
        if (status.MessageKey != "")
        {
            string key = shown != null ? shown.TextKey(status.MessageKey) : status.MessageKey;
            GameManager.ShowTooltip(player, string.Format(Localization.Get(key),
                status.WavesDone + 1, status.Waves, status.BreakSeconds, status.MessageValue));
        }
        shown?.UpdateStatus(status);
    }
}

/// <summary>
/// Where a defense stands, from the server.
/// </summary>
public class DefenseStatusDEM
{
    public enum Results : byte
    {
        None,
        Won,
        Lost,
    }

    public int WavesDone;

    public int Waves;

    public bool Fighting;

    public int ZombiesLeft;

    /// <summary>On-screen message, formatted with {0} = the current (or next) wave, {1} = waves,
    /// {2} = seconds between waves, {3} = <see cref="MessageValue"/>.</summary>
    public string MessageKey = "";

    public int MessageValue;

    public int BreakSeconds;

    /// <summary>Outpost: world time of the next attack.</summary>
    public ulong NextTime;

    public Results Result;

    /// <summary>Rescue: survivors lost. Safehouse: refugees lost.</summary>
    public int Lost;

    /// <summary>Rescue and Safehouse: which part of the quest the defense is in.</summary>
    public int Stage;

    /// <summary>Safehouse: what the checklist found (see SafehouseChecklistDEM).</summary>
    public int Checklist;

    public void Write(PooledBinaryWriter _bw)
    {
        _bw.Write(WavesDone);
        _bw.Write(Waves);
        _bw.Write(Fighting);
        _bw.Write(ZombiesLeft);
        _bw.Write(MessageKey ?? "");
        _bw.Write(MessageValue);
        _bw.Write(BreakSeconds);
        _bw.Write(NextTime);
        _bw.Write((byte)Result);
        _bw.Write(Lost);
        _bw.Write(Stage);
        _bw.Write(Checklist);
    }

    public static DefenseStatusDEM Read(PooledBinaryReader _br)
    {
        return new DefenseStatusDEM
        {
            WavesDone = _br.ReadInt32(),
            Waves = _br.ReadInt32(),
            Fighting = _br.ReadBoolean(),
            ZombiesLeft = _br.ReadInt32(),
            MessageKey = _br.ReadString(),
            MessageValue = _br.ReadInt32(),
            BreakSeconds = _br.ReadInt32(),
            NextTime = _br.ReadUInt64(),
            Result = (Results)_br.ReadByte(),
            Lost = _br.ReadInt32(),
            Stage = _br.ReadInt32(),
            Checklist = _br.ReadInt32(),
        };
    }
}
