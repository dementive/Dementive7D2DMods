using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// Contracts: an optional run of up to 5 quests on top of the normal ones. Start one at a trader, and the rewards
/// of every quest you complete go into the contract's pot instead of to you. Each completed quest is a stage: your
/// gamestage goes up (everything that spawns around you gets tougher) and the trader offers three boons to pick
/// one from. Cash out at any trader to collect the pot, worth more the more stages you've done. Dying, failing or
/// abandoning a quest loses the pot. On the last stage a tough boss hunts you down; finishing it pays out the most.
///
/// Quests don't know about contracts: the contract only watches quests close and rewards being given.
/// Every player has their own contract; the server owns them all (saved with the world in
/// QuestsExpanded/contracts.dat) and each client keeps a copy of its own (<see cref="Mine"/>).
/// </summary>
public static class ContractsDEM
{
    public const int LastStage = 5;

    /// <summary>The pot's experience and dukes grow by this much for every stage done when cashing out.</summary>
    public const float PotGrowth = 0.15f;

    /// <summary>The player's gamestage goes up by this much for every stage done.</summary>
    public const float GameStagePerStage = 0.1f;

    public const string GameStageBuff = "buffDementiveContract";

    public const string GameStageCVar = "dementiveContractGS";

    public const string BoonBuffPrefix = "buffDementiveBoon_";

    /// <summary>Boons the trader can offer (buffs <see cref="BoonBuffPrefix"/> + name).</summary>
    public static readonly string[] Boons =
    {
        "deadeye", "bloodthirst", "secondwind", "scavenger", "ironhide", "fleetfoot", "regeneration",
        "glasscannon", "adrenaline", "juggernaut",
    };

    /// <summary>The last stage's boss, by the player's gamestage: the first list whose gamestage isn't passed yet.</summary>
    private static readonly KeyValuePair<int, string>[] HuntBosses =
    {
        new KeyValuePair<int, string>(40, "zombieBiker,zombieFatCop"),
        new KeyValuePair<int, string>(80, "zombieWightFeral,zombieDemolition"),
        new KeyValuePair<int, string>(130, "zombieMutatedRadiated,zombieScreamerRadiated"),
        new KeyValuePair<int, string>(200, "zombieWightCharged,zombieMutatedCharged,zombieSpiderCharged,zombieUtilityWorkerCharged"),
        new KeyValuePair<int, string>(int.MaxValue, "zombieBikerInfernal,zombieFatCopInfernal,zombieWightInfernal,zombieMutatedInfernal,zombieSoldierInfernal"),
    };

    public static void Init()
    {
        ModEvents.GameUpdate.RegisterHandler(ClientUpdate);
    }

    // ===================================================================================================
    // Server
    // ===================================================================================================

    private const int FileVersion = 1;
    private static readonly SaveFileDEM file = new SaveFileDEM("contracts.dat");
    private static readonly Dictionary<string, ContractStateDEM> contracts = new Dictionary<string, ContractStateDEM>();

    private static string Key(int playerId)
    {
        PersistentPlayerData data = GameManager.Instance.persistentPlayers?.GetPlayerDataFromEntityID(playerId);
        return data?.PrimaryId?.CombinedString ?? "entity" + playerId;
    }

    private static ContractStateDEM Get(string key)
    {
        if (file.NeedsLoad())
        {
            contracts.Clear();
            file.Load(reader =>
            {
                reader.ReadInt32();
                int count = reader.ReadInt32();
                for (int i = 0; i < count; i++)
                {
                    string player = reader.ReadString();
                    contracts[player] = ContractStateDEM.Read(reader);
                }
            });
        }
        if (!contracts.TryGetValue(key, out ContractStateDEM state))
        {
            state = new ContractStateDEM();
            contracts.Add(key, state);
        }
        return state;
    }

    private static void Save()
    {
        file.Save(writer =>
        {
            writer.Write(FileVersion);
            int count = 0;
            foreach (ContractStateDEM state in contracts.Values)
                count += state.Active ? 1 : 0;
            writer.Write(count);
            foreach (KeyValuePair<string, ContractStateDEM> entry in contracts)
            {
                if (!entry.Value.Active)
                    continue;
                writer.Write(entry.Key);
                entry.Value.Write(writer);
            }
        });
    }

    /// <summary>
    /// A request from a player's client (or the local player of a listen server).
    /// </summary>
    public static void ServerHandle(int playerId, NetPackageContractDEM.Ops op, int a, int b, string text, List<ItemStack> items)
    {
        string key = Key(playerId);
        ContractStateDEM state = Get(key);
        switch (op)
        {
            case NetPackageContractDEM.Ops.Sync:
                SendState(playerId, state);
                break;

            case NetPackageContractDEM.Ops.Start:
                if (state.Active)
                    break;
                state = new ContractStateDEM { Active = true };
                contracts[key] = state;
                Save();
                SendState(playerId, state);
                SendMessage(playerId, "ContractDEM_started");
                break;

            case NetPackageContractDEM.Ops.Reward:
                if (!state.Active)
                {
                    // Too late for the pot (e.g. the contract just finished): pay it out as normal
                    SendPayout(playerId, a, b, items, "");
                    break;
                }
                state.PotExp += a;
                state.PotDukes += b;
                if (items != null)
                    state.PotItems.AddRange(items);
                Save();
                SendState(playerId, state);
                break;

            case NetPackageContractDEM.Ops.Stage:
                if (!state.Active)
                    break;
                state.Stage++;
                if (state.Stage >= LastStage)
                {
                    Finish(playerId, key, state, "ContractDEM_complete");
                    break;
                }
                state.PendingPicks++;
                if (state.Offer.Count == 0)
                    MakeOffer(state);
                Save();
                SendState(playerId, state);
                SendMessage(playerId, state.Stage == LastStage - 1 ? "ContractDEM_stage_last" : "ContractDEM_stage", state.Stage,
                    Mathf.RoundToInt(100f * (1f + PotGrowth * state.Stage)).ToString());
                break;

            case NetPackageContractDEM.Ops.Lose:
                if (!state.Active)
                    break;
                contracts[key] = new ContractStateDEM();
                WaveDirectorDEM.StopHunt(playerId);
                Save();
                SendState(playerId, contracts[key]);
                SendMessage(playerId, text);
                break;

            case NetPackageContractDEM.Ops.Pick:
                if (!state.Active || !state.Offer.Contains(text))
                    break;
                state.Boons.Add(text);
                state.Offer.Clear();
                state.PendingPicks = Mathf.Max(0, state.PendingPicks - 1);
                if (state.PendingPicks > 0)
                    MakeOffer(state);
                Save();
                SendState(playerId, state);
                SendMessage(playerId, "ContractDEM_picked", 0, text);
                break;

            case NetPackageContractDEM.Ops.CashOut:
                if (state.Active && state.Stage >= 1)
                    Finish(playerId, key, state, "ContractDEM_cashout");
                break;

            case NetPackageContractDEM.Ops.Boss:
                if (!state.Active || state.Stage != LastStage - 1 || state.BossSpawned)
                    break;
                if (!(GameManager.Instance.World?.GetEntity(playerId) is EntityPlayer player))
                    break;
                state.BossSpawned = true;
                Save();
                SendState(playerId, state);
                WaveDirectorDEM.StartHunt(playerId, BossesFor(player), killed =>
                {
                    // A boss that left with the player (logged out) comes back for them later
                    ContractStateDEM current = Get(key);
                    if (!killed && current.Active && current.BossSpawned)
                    {
                        current.BossSpawned = false;
                        Save();
                    }
                });
                break;
        }
    }

    private static string BossesFor(EntityPlayer player)
    {
        int gameStage = player.gameStage;
        foreach (KeyValuePair<int, string> entry in HuntBosses)
        {
            if (gameStage < entry.Key)
                return entry.Value;
        }
        return HuntBosses[HuntBosses.Length - 1].Value;
    }

    private static void MakeOffer(ContractStateDEM state)
    {
        var candidates = new List<string>();
        foreach (string boon in Boons)
        {
            if (!state.Boons.Contains(boon))
                candidates.Add(boon);
        }
        GameRandom random = GameManager.Instance.World.GetGameRandom();
        state.Offer.Clear();
        while (state.Offer.Count < 3 && candidates.Count > 0)
        {
            int i = random.RandomRange(candidates.Count);
            state.Offer.Add(candidates[i]);
            candidates.RemoveAt(i);
        }
    }

    /// <summary>
    /// Pays out the pot, grown by the stages done, and ends the contract.
    /// </summary>
    private static void Finish(int playerId, string key, ContractStateDEM state, string messageKey)
    {
        float growth = 1f + PotGrowth * state.Stage;
        int exp = Mathf.RoundToInt(state.PotExp * growth);
        int dukes = Mathf.RoundToInt(state.PotDukes * growth);
        List<ItemStack> items = state.PotItems;
        contracts[key] = new ContractStateDEM();
        WaveDirectorDEM.StopHunt(playerId);
        Save();
        SendState(playerId, contracts[key]);
        SendPayout(playerId, exp, dukes, items, messageKey);
    }

    private static void Send(int playerId, NetPackageContractDEM package)
    {
        World world = GameManager.Instance.World;
        if (world?.GetEntity(playerId) is EntityPlayerLocal)
            package.Apply();
        else
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendPackage(package, _onlyClientsAttachedToAnEntity: false, playerId);
    }

    private static void SendState(int playerId, ContractStateDEM state)
    {
        Send(playerId, NetPackageManager.GetPackage<NetPackageContractDEM>().Setup(NetPackageContractDEM.Ops.State, state: state));
    }

    private static void SendPayout(int playerId, int exp, int dukes, List<ItemStack> items, string messageKey)
    {
        Send(playerId, NetPackageManager.GetPackage<NetPackageContractDEM>().Setup(NetPackageContractDEM.Ops.Payout, exp, dukes, messageKey, items));
    }

    private static void SendMessage(int playerId, string messageKey, int value = 0, string extra = "")
    {
        Send(playerId, NetPackageManager.GetPackage<NetPackageContractDEM>().Setup(NetPackageContractDEM.Ops.Message, value, 0, messageKey, extra: extra));
    }

    // ===================================================================================================
    // Client
    // ===================================================================================================

    /// <summary>The local player's contract, as the server last reported it.</summary>
    public static ContractStateDEM Mine = new ContractStateDEM();

    /// <summary>The server has reported the local player's contract since they joined.</summary>
    public static bool Synced;

    private static float syncTimer;
    private static bool wasDead;
    private static float bossTimer = -1f;

    public static bool Active => Synced && Mine.Active;

    /// <summary>
    /// Sends a request to the server (handled directly on a listen server or in single player).
    /// </summary>
    public static void Send(NetPackageContractDEM.Ops op, int a = 0, int b = 0, string text = "", List<ItemStack> items = null)
    {
        if (SingletonMonoBehaviour<ConnectionManager>.Instance.IsServer)
        {
            EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
            if (player != null)
                ServerHandle(player.entityId, op, a, b, text, items);
        }
        else
        {
            SingletonMonoBehaviour<ConnectionManager>.Instance.SendToServer(
                NetPackageManager.GetPackage<NetPackageContractDEM>().Setup(op, a, b, text, items));
        }
    }

    public static void ClientState(ContractStateDEM state)
    {
        Mine = state;
        Synced = true;
        ApplyBuffs(GameManager.Instance.World?.GetPrimaryPlayer());
    }

    public static void ClientPayout(int exp, int dukes, List<ItemStack> items, string messageKey)
    {
        EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player == null)
            return;
        RewardUtilsDEM.GiveExp(player, exp);
        RewardUtilsDEM.GiveDukes(player, dukes);
        if (items != null)
        {
            foreach (ItemStack stack in items)
                RewardUtilsDEM.GiveItem(player, stack);
        }
        if (!string.IsNullOrEmpty(messageKey))
            GameManager.ShowTooltip(player, string.Format(Localization.Get(messageKey), exp, dukes, items?.Count ?? 0));
    }

    public static void ClientMessage(string messageKey, int value, string extra)
    {
        EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player != null && !string.IsNullOrEmpty(messageKey))
            GameManager.ShowTooltip(player, string.Format(Localization.Get(messageKey), value, BoonName(extra), extra));
    }

    public static string BoonName(string boon)
    {
        return string.IsNullOrEmpty(boon) ? "" : Localization.Get(BoonBuffPrefix + boon + "Name");
    }

    /// <summary>
    /// Shows where the local player's contract stands.
    /// </summary>
    public static void ShowStatus()
    {
        EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player == null || !Active)
            return;
        GameManager.ShowTooltip(player, string.Format(Localization.Get("ContractDEM_status"), Mine.Stage, LastStage,
            Mine.PotExp, Mine.PotDukes, Mine.PotItems.Count, Mathf.RoundToInt(100f * (1f + PotGrowth * Mine.Stage))));
    }

    /// <summary>
    /// Boon buffs and the gamestage buff follow the contract.
    /// </summary>
    private static void ApplyBuffs(EntityPlayerLocal player)
    {
        if (player == null)
            return;
        foreach (string boon in Boons)
            SetBuff(player, BoonBuffPrefix + boon, Mine.Active && Mine.Boons.Contains(boon));

        bool escalated = Mine.Active && Mine.Stage > 0;
        player.Buffs.SetCustomVar(GameStageCVar, escalated ? GameStagePerStage * Mine.Stage : 0f);
        SetBuff(player, GameStageBuff, escalated);
    }

    private static void SetBuff(EntityPlayerLocal player, string buff, bool on)
    {
        bool has = player.Buffs.HasBuff(buff);
        if (on && !has)
            player.Buffs.AddBuff(buff);
        else if (!on && has)
            player.Buffs.RemoveBuff(buff);
    }

    private static void ClientUpdate(ref ModEvents.SGameUpdateData data)
    {
        EntityPlayerLocal player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player == null)
        {
            // Back at the main menu: forget the last world's contract
            Synced = false;
            Mine = new ContractStateDEM();
            syncTimer = 0f;
            return;
        }

        float deltaTime = Time.deltaTime;
        if (!Synced)
        {
            syncTimer -= deltaTime;
            if (syncTimer <= 0f)
            {
                syncTimer = 10f;
                Send(NetPackageContractDEM.Ops.Sync);
            }
            return;
        }

        // Dying ends the contract
        bool dead = player.IsDead();
        if (dead && !wasDead && Mine.Active)
            Send(NetPackageContractDEM.Ops.Lose, text: "ContractDEM_lost_death");
        wasDead = dead;

        // On the last stage, a boss comes for the player a few minutes into their quest, wherever they are
        if (Mine.Active && Mine.Stage == LastStage - 1 && !Mine.BossSpawned && !dead && HasQuestInProgress(player))
        {
            if (bossTimer < 0f)
                bossTimer = Random.Range(180f, 480f);
            bossTimer -= deltaTime;
            if (bossTimer <= 0f && !GameManager.Instance.World.IsWithinTraderArea(new Vector3i(player.position)))
            {
                bossTimer = 60f;
                Send(NetPackageContractDEM.Ops.Boss);
            }
        }
        else
        {
            bossTimer = -1f;
        }
    }

    private static bool HasQuestInProgress(EntityPlayerLocal player)
    {
        foreach (Quest quest in player.QuestJournal.quests)
        {
            if (quest.CurrentState == Quest.QuestState.InProgress)
                return true;
        }
        return false;
    }

    // ===================================================================================================
    // Hooks
    // ===================================================================================================

    /// <summary>
    /// During a contract, a quest's experience, dukes and items go into the pot instead of to the player.
    /// </summary>
    [HarmonyPatch(typeof(BaseReward), nameof(BaseReward.GiveReward), new System.Type[0])]
    public static class BaseRewardGiveReward
    {
        public static bool Prefix(BaseReward __instance)
        {
            if (!Active || __instance.OwnerQuest?.OwnerJournal?.OwnerPlayer == null)
                return true;

            int exp = 0;
            int dukes = 0;
            ItemStack item = null;
            switch (__instance)
            {
                case RewardExp _:
                    int.TryParse(__instance.Value, out exp);
                    break;
                case RewardItem reward:
                    item = reward.Item;
                    break;
                case RewardLootItem reward:
                    item = reward.Item;
                    break;
                case IPotRewardDEM reward:
                    exp = reward.PotExp;
                    dukes = reward.PotDukes;
                    break;
                default:
                    return true;
            }

            List<ItemStack> items = null;
            if (item != null && !item.IsEmpty())
            {
                if (item.itemValue.ItemClass?.GetItemName() == RewardUtilsDEM.Dukes)
                    dukes += item.count;
                else
                    items = new List<ItemStack> { item.Clone() };
            }
            Send(NetPackageContractDEM.Ops.Reward, exp, dukes, items: items);
            return false;
        }
    }

    /// <summary>
    /// A quest completed during a contract is a stage; a failed or abandoned one ends the contract.
    /// </summary>
    [HarmonyPatch(typeof(Quest), nameof(Quest.CloseQuest))]
    public static class QuestCloseQuest
    {
        public static void Prefix(Quest __instance, out Quest.QuestState __state)
        {
            __state = __instance.CurrentState;
        }

        public static void Postfix(Quest __instance, Quest.QuestState finalState, Quest.QuestState __state)
        {
            if (!Active || __instance.OwnerJournal?.OwnerPlayer == null || __instance.CurrentState != finalState)
                return;
            if (__state != Quest.QuestState.InProgress && __state != Quest.QuestState.ReadyForTurnIn)
                return;

            if (finalState == Quest.QuestState.Completed)
                Send(NetPackageContractDEM.Ops.Stage);
            else if (finalState == Quest.QuestState.Failed || finalState == Quest.QuestState.Cancelled)
                Send(NetPackageContractDEM.Ops.Lose, text: "ContractDEM_lost_quest");
        }
    }
}
