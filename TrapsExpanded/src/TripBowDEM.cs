using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Trip Bow (XML class "TripBowDEM, TrapsExpanded"): a hunting bow lashed to a sawhorse. Every FireDelay seconds it
/// shoots one of its loaded vanilla arrows at the first zombie in a line straight ahead (within Range, LineWidth wide)
/// that the arrow can reach. Damage is the arrow's (ArrowDamage); flaming arrows set the zombie on fire like the
/// vanilla ones, and exploding arrows explode like the vanilla ones. Upgrades (level 3): A Repeater (RepeaterDelay
/// between shots), B Long Draw (LongDrawDamage times the damage and LongDrawRange).
///
/// The model's ArrowOrigin (the nocked arrow's tip) and ArrowAim (a meter ahead) give the line. XML properties: Range,
/// LineWidth, FireDelay, RepeaterDelay, LongDrawRange, LongDrawDamage, ArrowDamage ("item:damage,..."), FireSound,
/// and the shared ones.
/// </summary>
public class BlockTripBowDEM : BlockPlainTrapDEM
{
    public float Range = 12f;
    public float LineWidth = 1.2f;
    public float FireDelay = 3f;
    public float RepeaterDelay = 1.5f;
    public float LongDrawRange = 20f;
    public float LongDrawDamage = 1.5f;
    public string FireSound = "bow_fire";
    public readonly Dictionary<string, float> ArrowDamage = new Dictionary<string, float>();

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("LineWidth", ref LineWidth);
        Properties.ParseFloat("FireDelay", ref FireDelay);
        Properties.ParseFloat("RepeaterDelay", ref RepeaterDelay);
        Properties.ParseFloat("LongDrawRange", ref LongDrawRange);
        Properties.ParseFloat("LongDrawDamage", ref LongDrawDamage);
        Properties.ParseString("FireSound", ref FireSound);
        string damage = "";
        Properties.ParseString("ArrowDamage", ref damage);
        foreach (string entry in damage.Split(','))
        {
            string[] kv = entry.Split(':');
            if (kv.Length == 2 && float.TryParse(kv[1].Trim(), System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out float d))
            {
                ArrowDamage[kv[0].Trim()] = d;
            }
        }
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        return model.AddComponent<TripBowControllerDEM>();
    }
}

public class TripBowControllerDEM : TrapControllerDEM
{
    private BlockTripBowDEM bow;
    private Transform arrowOrigin;
    private Transform arrowAim;

    protected override float ActDelay => Upgraded('A') ? bow.RepeaterDelay : bow.FireDelay;

    protected override float IdleDelay => 0.25f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        bow = (BlockTripBowDEM)trap;
        base.Setup(trap, pos);
        arrowOrigin = FindDeep(transform, "ArrowOrigin");
        arrowAim = FindDeep(transform, "ArrowAim");
    }

    private void Line(out Vector3 origin, out Vector3 dir)
    {
        origin = WorldPoint(arrowOrigin, new Vector3(0f, 0.6f, 0.4f));
        dir = arrowOrigin != null && arrowAim != null ? (arrowAim.position - arrowOrigin.position).normalized : Forward;
    }

    protected override bool Act(World world)
    {
        if (!HasAmmo)
        {
            Cooldown = 1f;
            return false;
        }
        bool longDraw = Upgraded('B');
        float range = longDraw ? bow.LongDrawRange : bow.Range;
        Line(out Vector3 origin, out Vector3 dir);

        // The first zombie along the line
        EntityAlive target = null;
        float best = range;
        foreach (EntityAlive e in Enemies(world, origin + dir * (range * 0.5f), range * 0.5f + 1f))
        {
            Vector3 chest = e.getChestPosition();
            Vector3 to = chest - origin;
            float along = Vector3.Dot(to, dir);
            if (along < 0.2f || along > best)
            {
                continue;
            }
            Vector3 flatOff = to - dir * along;
            flatOff.y = 0f;
            if (flatOff.magnitude > bow.LineWidth * 0.5f || Mathf.Abs(to.y - dir.y * along) > 1.6f)
            {
                continue;
            }
            if (!Reachable(world, origin + dir * 0.1f, chest))
            {
                continue;
            }
            target = e;
            best = along;
        }
        if (target == null)
        {
            return false;
        }

        UseAmmo(1f, out string arrow);
        int owner = Owner(world);
        Vector3 hitAt = target.getChestPosition();
        Vector3 shot = (hitAt - origin).normalized;
        bow.ArrowDamage.TryGetValue(arrow ?? "", out float damage);
        if (damage <= 0f)
        {
            damage = 35f;
        }
        damage *= DamageMult * (longDraw ? bow.LongDrawDamage : 1f);
        Touch(target, false);
        bool alive = Hit(target, damage, EnumDamageTypes.Piercing, shot, owner, 0.5f);
        if (arrow == "ammoArrowFlaming" && alive && !TrapStatusDEM.IsSoaked(target))
        {
            target.Buffs.SetCustomVar("$buffBurningFlamingArrowDuration", 14f);
            target.Buffs.AddBuff("buffBurningFlamingArrow", owner, true, false);
            Touch(target, true);
        }
        else if (arrow == "ammoArrowExploding")
        {
            Explode(world, arrow, hitAt, owner);
        }
        Audio.Manager.BroadcastPlay(origin, bow.FireSound);
        Broadcast(origin, new[] { target.entityId, arrow == "ammoArrowFlaming" ? 1 : 0 });
        return true;
    }

    /// <summary>An exploding arrow's own explosion (from its item's Explosion properties), credited to the
    /// owner; zombies in the blast count as this trap's if it kills them.</summary>
    private void Explode(World world, string arrow, Vector3 at, int owner)
    {
        ItemClass ic = ItemClass.GetItemClass(arrow);
        if (ic == null)
        {
            return;
        }
        ExplosionData data = new ExplosionData(ic.Properties, ic.Effects);
        foreach (EntityAlive e in Enemies(world, at, Mathf.Max(2f, data.EntityRadius)))
        {
            Touch(e, false);
        }
        // The explosion damages at once (no delay), so its kills count for this trap rather than the arrow's owner
        TrapKillsDEM.Begin(BlockPos, Settings.Name, false);
        try
        {
            GameManager.Instance.ExplosionServer(at, World.worldToBlockPos(at), Quaternion.identity, data, owner, 0f,
                false, ItemClass.GetItem(arrow));
        }
        finally
        {
            TrapKillsDEM.End();
        }
    }

    public override void PlayFx(int[] ids)
    {
        World world = GameManager.Instance.World;
        if (world == null || ids.Length < 1 || !(world.GetEntity(ids[0]) is EntityAlive target))
        {
            return;
        }
        Line(out Vector3 origin, out _);
        bool flaming = ids.Length > 1 && ids[1] == 1;
        ProjectileFxDEM.Launch(flaming ? "ArrowFlamingFx" : "ArrowFx", origin, target.getChestPosition(), 55f, 0.05f,
            null, 0f);
    }
}
