using HarmonyLib;
using UnityEngine;

/// <summary>Put It On My Tab and Dead Man's Switch. A hit on a player is processed on their own machine and on the
/// server, which can decide on its own that the hit is fatal, so both chems run on every machine, from cvars the buffs
/// set on each copy of the player. Only the player's own machine keeps the bill and fires the switch.</summary>
public static class ChemDamageDEM
{
    private const string OnTabCVar = "%dementiveOnTab";
    private const string ShieldedCVar = "%dementiveShielded";
    private const string SwitchLoadedCVar = "%dementiveSwitchLoaded";
    private const string TabOwedCVar = "$dementiveTabOwed";
    private const string SwitchBuff = "buffDementiveDeadMansSwitch";
    private const string SwitchFiredBuff = "buffDementiveSwitchFired";
    private const string CrashBuff = "buffDementiveCrash";

    private static int pendingHurt;

    public static void OnHit(EntityPlayer _player, ref DamageResponse _response)
    {
        var buffs = _player.Buffs;
        if (buffs == null || _response.Strength <= 0 || _player.IsDead())
            return;

        if (buffs.GetCustomVar(OnTabCVar) > 0f)
        {
            if (!_player.isEntityRemote)
                buffs.SetCustomVar(TabOwedCVar, buffs.GetCustomVar(TabOwedCVar) + _response.Strength, false);
            Absorb(_player, ref _response);
            return;
        }
        if (buffs.GetCustomVar(ShieldedCVar) > 0f)
        {
            Absorb(_player, ref _response);
            return;
        }

        if (buffs.GetCustomVar(SwitchLoadedCVar) <= 0f || _response.Source?.damageType == EnumDamageTypes.Suicide)
            return;
        if (!_response.Fatal && _response.Strength < _player.Health)
            return;
        _response.Fatal = false;
        _response.Strength = Mathf.Max(_player.Health - 1, 0);
        KeepAlive(_player);
        if (_player.isEntityRemote)
            return;
        buffs.SetCustomVar(SwitchLoadedCVar, 0f);
        buffs.SetCustomVar(ShieldedCVar, 1f);
        buffs.RemoveBuff(SwitchBuff);
        buffs.AddBuff(SwitchFiredBuff);
    }

    /// <summary>The bill for the Tab: half of what was absorbed. It goes through the normal damage path, so it can kill,
    /// and a loaded Dead Man's Switch catches it like any other hit.</summary>
    public static void PayTab(EntityAlive _self)
    {
        var owed = _self.Buffs.GetCustomVar(TabOwedCVar);
        _self.Buffs.SetCustomVar(OnTabCVar, 0f);
        _self.Buffs.SetCustomVar(TabOwedCVar, 0f, false);
        Hurt(Mathf.CeilToInt(owed * .5f));
    }

    /// <summary>Queued for Update because the callers are buff actions: a killing blow inside the buff update starts a
    /// second update on the same buff list, which then runs past its end.</summary>
    public static void Hurt(int _amount)
    {
        pendingHurt += _amount;
    }

    public static void Update()
    {
        if (pendingHurt <= 0)
            return;
        var amount = pendingHurt;
        pendingHurt = 0;
        var player = GameManager.Instance.World?.GetPrimaryPlayer();
        if (player == null || player.IsDead())
            return;
        // A source with a buff class is the game's damage over time: the server doesn't send it back to the player who
        // already applied it, so it lands once on a co-op client
        var source = new DamageSource(EnumDamageSource.Internal, EnumDamageTypes.Disease) { BuffClass = BuffManager.GetBuff(CrashBuff) };
        player.DamageEntity(source, amount, false);
    }

    public static void Reset()
    {
        pendingHurt = 0;
    }

    private static void Absorb(EntityPlayer _player, ref DamageResponse _response)
    {
        _response.Strength = 0;
        _response.Fatal = false;
        _response.Dismember = false;
        KeepAlive(_player);
    }

    /// <summary>Some damage takes health straight down through ModifyStats and never comes here. The game then finishes
    /// the player with a 1 point hit at 0 health, and that hit does, but at 0 health the game kills whatever the hit
    /// says, so the health has to come back first.</summary>
    private static void KeepAlive(EntityPlayer _player)
    {
        if (!_player.isEntityRemote && _player.Health <= 0)
            _player.Health = 1;
    }
}

[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.ProcessDamageResponseLocal))]
public static class DamageResponsePatchDEM
{
    public static void Prefix(EntityAlive __instance, ref DamageResponse _dmResponse)
    {
        if (__instance is EntityPlayer player)
            ChemDamageDEM.OnHit(player, ref _dmResponse);
    }
}
