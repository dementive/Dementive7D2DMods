using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The player-side extras, on each player's game: horde audio (a distant crowd moan from where a lot of zombies are
/// close), first-meeting tips (what a mutation, piece of gear or champion is and what works against it, once per
/// player), and which champion the bar at the top of the screen shows.
/// </summary>
public static class ZedClient
{
    private static readonly string[] Moans = { "zombiemaleroam", "zombiemale2roam", "zombiefemaleroam", "zombiefemale2roam", "zombieferalroam" };

    private static float hordeTick, tipTick, tipQuietUntil;
    private static readonly Dictionary<int, float> hitByMe = new Dictionary<int, float>();

    /// <summary>The champion (or Alpha) the bar shows, or null.</summary>
    public static EntityAlive BarZombie { get; private set; }

    public static void Update()
    {
        if (!ZedStore.DrawsLooks)
        {
            return;
        }
        World world = GameManager.Instance.World;
        EntityPlayerLocal player = world?.GetPrimaryPlayer();
        if (player == null)
        {
            BarZombie = null;
            hitByMe.Clear();
            return;
        }
        float now = Time.time;
        if (now >= hordeTick)
        {
            hordeTick = now + 2.5f;
            Horde(world, player);
        }
        if (now >= tipTick)
        {
            tipTick = now + 0.5f;
            Bar(world, player, now);
            if (now >= tipQuietUntil)
            {
                Tips(world, player, now);
            }
        }
    }

    /// <summary>The local player hit this zombie (the bar shows a champion you've hit for 20 s).</summary>
    public static void HitByMe(int entityId)
    {
        hitByMe[entityId] = Time.time;
    }

    private static void Horde(World world, EntityPlayerLocal player)
    {
        if (!ZedSettings.HordeAudio)
        {
            return;
        }
        int count = 0;
        Vector3 sum = Vector3.zero;
        foreach (EntityAlive e in world.EntityAlives)
        {
            if (!e.IsDead() && !e.IsSleeper && ZedStore.IsZombie(e) && (e.position - player.position).sqrMagnitude < 40f * 40f)
            {
                count++;
                sum += e.position;
            }
        }
        if (count < 8 || Random.value > count / 16f)
        {
            return;
        }
        Vector3 dir = sum / count - player.position;
        float d = dir.magnitude;
        if (d < 4f)
        {
            return;
        }
        Vector3 at = player.position + dir / d * Mathf.Min(d, 22f) + Vector3.up;
        Audio.Manager.Play(at, Moans[Random.Range(0, Moans.Length)], -1, false, Mathf.Clamp01(count / 24f) * 0.7f);
    }

    private static void Bar(World world, EntityPlayerLocal player, float now)
    {
        BarZombie = null;
        if (!ZedSettings.ChampionBar)
        {
            return;
        }
        float best = float.MaxValue;
        foreach (EntityAlive e in world.EntityAlives)
        {
            if (e.IsDead() || !ZedStore.IsZombie(e))
            {
                continue;
            }
            ZedProfile p = ZedStore.Get(e.entityId);
            if (p == null || !(p.Champion || p.Alpha))
            {
                continue;
            }
            float d = (e.position - player.position).sqrMagnitude;
            bool engaged = e.GetAttackTargetLocal() == player || e.GetAttackTarget() == player
                || (hitByMe.TryGetValue(e.entityId, out float at) && now - at < 20f);
            if (d < 30f * 30f && engaged && d < best)
            {
                best = d;
                BarZombie = e;
            }
        }
    }

    /// <summary>The first time each player meets a mutation, gear or a champion within 20 m in view: a short line on
    /// what it is and what works against it (once per player, kept in a cvar on the player).</summary>
    private static void Tips(World world, EntityPlayerLocal player, float now)
    {
        if (!ZedSettings.Tips || player.Buffs == null)
        {
            return;
        }
        Camera cam = Camera.main;
        foreach (EntityAlive e in world.EntityAlives)
        {
            if (e.IsDead() || !ZedStore.IsZombie(e) || (e.position - player.position).sqrMagnitude > 20f * 20f)
            {
                continue;
            }
            ZedProfile p = ZedStore.Get(e.entityId);
            if (p == null || (p.Mutations.Count == 0 && p.Gear.Count == 0 && !p.Champion && !p.Alpha))
            {
                continue;
            }
            if (cam != null && Vector3.Dot(cam.transform.forward, (e.getChestPosition() - Origin.position - cam.transform.position).normalized) < 0.6f)
            {
                continue;
            }
            List<string> topics = new List<string>();
            if (p.Alpha)
            {
                topics.Add("Alpha");
            }
            else if (p.Champion)
            {
                topics.Add("Champion");
            }
            foreach (ZedMutation m in p.Mutations)
            {
                // A Possum gives itself away only by getting up
                if (m != ZedMutation.Possum || (p.FakedDeath && !p.PlayingDead))
                {
                    topics.Add(m.ToString());
                }
            }
            foreach (ZedGearPiece g in p.Gear)
            {
                ZedGearInfo info = ZedGearInfo.All[g.Kind];
                topics.Add(info.IsHelmet ? "Helmet" : info.IsShield ? "Shield" : g.Kind.ToString());
            }
            foreach (string topic in topics)
            {
                string cvar = "zedTipSeen" + topic;
                if (player.Buffs.GetCustomVar(cvar) > 0f)
                {
                    continue;
                }
                player.Buffs.SetCustomVar(cvar, 1f);
                GameManager.ShowTooltip(player, Localization.Get("zedTip" + topic), false, false, 8f);
                tipQuietUntil = now + 10f;
                return;
            }
        }
    }
}

/// <summary>The champion bar at the top of the screen (windowZedChampion in XUi): the champion's name and health,
/// in the game's boss bar art. Shown while a champion or the Alpha is after you or you've hit it.</summary>
public class XUiC_ZedChampionBar : XUiController
{
    private EntityAlive shown;
    private string fill = "0";

    public override void Update(float _dt)
    {
        base.Update(_dt);
        EntityAlive z = ZedClient.BarZombie;
        bool show = z != null && !z.IsDead();
        if (viewComponent != null && viewComponent.IsVisible != show)
        {
            viewComponent.IsVisible = show;
        }
        if (!show)
        {
            shown = null;
            return;
        }
        string f = (z.Health / (float)Mathf.Max(1, z.GetMaxHealth())).ToString("0.000", System.Globalization.CultureInfo.InvariantCulture);
        if (z != shown || f != fill)
        {
            shown = z;
            fill = f;
            RefreshBindings();
        }
    }

    public override bool GetBindingValueInternal(ref string _value, string _bindingName)
    {
        switch (_bindingName)
        {
            case "zedname":
                ZedProfile p = shown != null ? ZedStore.Get(shown.entityId) : null;
                _value = p?.Name ?? "";
                return true;
            case "zedfill":
                _value = fill;
                return true;
        }
        return base.GetBindingValueInternal(ref _value, _bindingName);
    }
}
