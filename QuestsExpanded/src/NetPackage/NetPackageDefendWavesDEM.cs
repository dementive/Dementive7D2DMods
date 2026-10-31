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
    private int waves;

    private int wavesDone;

    private bool fighting;

    private int zombiesLeft;

    private string messageKey = "";

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

    public NetPackageDefendWavesDEM SetupStatus(int _questCode, int _wavesDone, int _waves, bool _fighting, int _zombiesLeft, string _messageKey)
    {
        kind = Kinds.Status;
        questCode = _questCode;
        wavesDone = _wavesDone;
        waves = _waves;
        fighting = _fighting;
        zombiesLeft = _zombiesLeft;
        messageKey = _messageKey;
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
            waves = _br.ReadInt32();
            wavesDone = _br.ReadInt32();
            fighting = _br.ReadBoolean();
            zombiesLeft = _br.ReadInt32();
            messageKey = _br.ReadString();
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
            _bw.Write(waves);
            _bw.Write(wavesDone);
            _bw.Write(fighting);
            _bw.Write(zombiesLeft);
            _bw.Write(messageKey);
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

        ObjectiveDefendWavesDEM shown = null;
        foreach (Quest quest in player.QuestJournal.quests)
        {
            if (quest.QuestCode != questCode || quest.CurrentState != Quest.QuestState.InProgress)
            {
                continue;
            }

            foreach (BaseObjective objective in quest.Objectives)
            {
                if (objective is ObjectiveDefendWavesDEM defend && defend.Phase == quest.CurrentPhase)
                {
                    defend.UpdateStatus(wavesDone, fighting, zombiesLeft);
                    shown = defend;
                }
            }
        }

        if (messageKey != "")
        {
            string key = shown != null ? shown.TextKey(messageKey) : messageKey;
            GameManager.ShowTooltip(player, string.Format(Localization.Get(key), wavesDone + 1, waves, (int)WaveDirectorDEM.BreakSeconds));
        }
    }
}
