using UnityEngine;

/// <summary>
/// Shared code for objectives whose zombies <see cref="WaveDirectorDEM"/> runs on the server: joining the quest's
/// defense when the objective's phase starts (directly on the server, by package from a client), leaving it when the
/// phase ends, and taking the server's status.
/// Properties every defense objective takes:
/// 	keyword: localization key of the objective's text
/// 	text: use the quest's own version of a text where there is one, e.g. DefendWavesDEM_incoming_horde for "horde"
/// </summary>
public abstract class ObjectiveDefenseBaseDEM : BaseObjective
{
    public string KeywordKey;

    public string Text = "";

    protected bool joined;

    protected DefenseStatusDEM status = new DefenseStatusDEM();

    protected ObjectiveDefenseBaseDEM(string keywordKey)
    {
        KeywordKey = keywordKey;
    }

    public override ObjectiveValueTypes ObjectiveValueType => ObjectiveValueTypes.Number;

    public override bool UpdateUI => true;

    protected EntityPlayerLocal Player => OwnerQuest.OwnerJournal.OwnerPlayer;

    public override void SetupObjective()
    {
        keyword = Localization.Get(KeywordKey);
    }

    public override void SetupDisplay()
    {
        Description = keyword;
    }

    /// <summary>
    /// What the defense looks like, or false if the quest isn't ready for it.
    /// </summary>
    protected abstract bool BuildSettings(out DefenseSettingsDEM settings);

    /// <summary>
    /// The server's status of the defense.
    /// </summary>
    public virtual void UpdateStatus(DefenseStatusDEM newStatus)
    {
        status = newStatus;
        if (status.Result == DefenseStatusDEM.Results.Lost)
        {
            Fail(null);
            return;
        }
        if (status.Result == DefenseStatusDEM.Results.Won || status.WavesDone > CurrentValue)
        {
            CurrentValue = (byte)Mathf.Clamp(status.Result == DefenseStatusDEM.Results.Won ? status.Waves : status.WavesDone, 0, 255);
            Refresh();
        }
    }

    /// <summary>Whether the objective is done, checked by <see cref="Refresh"/>.</summary>
    protected abstract bool IsDone();

    public override void AddHooks()
    {
        if (joined || Complete || !BuildSettings(out DefenseSettingsDEM settings))
            return;

        joined = true;
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            WaveDirectorDEM.Join(OwnerQuest.QuestCode, Player.entityId, settings);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageDefendWavesDEM>().SetupJoin(OwnerQuest.QuestCode, settings));
        }
    }

    public override void RemoveHooks()
    {
        if (!joined)
            return;

        joined = false;
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            WaveDirectorDEM.Leave(OwnerQuest.QuestCode, Player.entityId);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageDefendWavesDEM>().SetupLeave(OwnerQuest.QuestCode));
        }
    }

    public override void Refresh()
    {
        if (Complete)
            return;

        Complete = IsDone() && OwnerQuest.CheckRequirements();
        if (Complete)
            OwnerQuest.RefreshQuestCompletion();
    }

    /// <summary>
    /// Fails the quest, with an on-screen message if there is one.
    /// </summary>
    protected void Fail(string messageKey)
    {
        if (OwnerQuest.CurrentState != Quest.QuestState.InProgress)
            return;
        if (messageKey != null)
            GameManager.ShowTooltip(Player, Localization.Get(TextKey(messageKey)));
        OwnerQuest.CloseQuest(Quest.QuestState.Failed);
    }

    /// <summary>
    /// The quest's own version of a text, e.g. DefendWavesDEM_incoming_horde for text "horde", if there is one.
    /// </summary>
    public string TextKey(string key)
    {
        return Text != "" && Localization.Exists(key + "_" + Text) ? key + "_" + Text : key;
    }

    protected string Format(string key, params object[] values)
    {
        return string.Format(Localization.Get(TextKey(key)), values);
    }

    public override void ParseProperties(DynamicProperties properties)
    {
        base.ParseProperties(properties);
        properties.ParseString("keyword", ref KeywordKey);
        properties.ParseString("text", ref Text);
    }

    protected void CopyDefenseValues(ObjectiveDefenseBaseDEM objective)
    {
        CopyValues(objective);
        objective.KeywordKey = KeywordKey;
        objective.Text = Text;
    }

    /// <summary>
    /// Horizontal distance between two points.
    /// </summary>
    protected static float Flat(Vector3 a, Vector3 b)
    {
        return new Vector2(a.x - b.x, a.z - b.z).magnitude;
    }
}
