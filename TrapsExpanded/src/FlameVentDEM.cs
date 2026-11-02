using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Flame Vent (XML class "FlameVentDEM, TrapsExpanded"): the game's own unfinished flamethrower trap, finished. While
/// a zombie is in its cone (Range, ConeAngle) it fires in PulseDelay bursts that burn AmmoPerUse gas cans each: every
/// zombie in the cone takes DamagePerSecond (heat) and catches fire for BurnSeconds; tarred zombies go up as Infernos
/// and soaked ones don't light. Upgrades (level 3): A Napalm (burning fuel stays on the ground for NapalmSeconds,
/// lighting zombies that walk through), B Blowtorch (BlowtorchRange, BlowtorchAngle, BlowtorchDamage times the damage).
///
/// The vanilla model has three nozzles stacked on its -Z end: NozzleOffsets lists them (from the model's origin, in its
/// frame) and NozzleForward is the way they point. The cone is worked out from their middle; each nozzle shows a jet.
/// XML properties: Range, ConeAngle, PulseDelay, DamagePerSecond, BurnSeconds, NapalmSeconds, BlowtorchRange,
/// BlowtorchAngle, BlowtorchDamage, NozzleOffsets ("x,y,z;x,y,z;..."), NozzleForward, FireSound, and the shared ones.
/// </summary>
public class BlockFlameVentDEM : BlockTrapDEM
{
    public float Range = 5f;
    public float ConeAngle = 40f;
    public float PulseDelay = 0.5f;
    public float DamagePerSecond = 15f;
    public float BurnSeconds = 6f;
    public float NapalmSeconds = 4f;
    public float BlowtorchRange = 10f;
    public float BlowtorchAngle = 14f;
    public float BlowtorchDamage = 1.5f;
    public Vector3[] NozzleOffsets = { new Vector3(0f, 0.33f, -1.48f), new Vector3(0f, 0.67f, -1.48f), new Vector3(0f, 1f, -1.48f) };
    public Vector3 NozzleForward = Vector3.back;
    public string FireSound = "flametrap_start";

    public override void Init()
    {
        base.Init();
        Properties.ParseFloat("Range", ref Range);
        Properties.ParseFloat("ConeAngle", ref ConeAngle);
        Properties.ParseFloat("PulseDelay", ref PulseDelay);
        Properties.ParseFloat("DamagePerSecond", ref DamagePerSecond);
        Properties.ParseFloat("BurnSeconds", ref BurnSeconds);
        Properties.ParseFloat("NapalmSeconds", ref NapalmSeconds);
        Properties.ParseFloat("BlowtorchRange", ref BlowtorchRange);
        Properties.ParseFloat("BlowtorchAngle", ref BlowtorchAngle);
        Properties.ParseFloat("BlowtorchDamage", ref BlowtorchDamage);
        if (Properties.Values.ContainsKey("NozzleOffsets"))
        {
            string[] parts = Properties.Values["NozzleOffsets"].Split(';');
            NozzleOffsets = new Vector3[parts.Length];
            for (int i = 0; i < parts.Length; i++)
            {
                NozzleOffsets[i] = StringParsers.ParseVector3(parts[i]);
            }
        }
        if (Properties.Values.ContainsKey("NozzleForward"))
        {
            NozzleForward = StringParsers.ParseVector3(Properties.Values["NozzleForward"]).normalized;
        }
        Properties.ParseString("FireSound", ref FireSound);
    }

    public override TrapControllerDEM AddController(GameObject model)
    {
        // The vanilla model was made for the dart trap's launcher code; that code isn't running for this block
        foreach (MonoBehaviour b in model.GetComponentsInChildren<MonoBehaviour>(true))
        {
            if (b != null && !(b is TrapControllerDEM) && b.GetType().Assembly == typeof(Block).Assembly)
            {
                b.enabled = false;
            }
        }
        return model.AddComponent<FlameVentControllerDEM>();
    }
}

public class FlameVentControllerDEM : TrapControllerDEM
{
    private BlockFlameVentDEM vent;
    private float soundTimer;

    private class Patch
    {
        public Vector3 Pos;
        public float Until;
    }

    private readonly List<Patch> patches = new List<Patch>();
    private static readonly List<int> hit = new List<int>();

    protected override float ActDelay => vent.PulseDelay;

    protected override float IdleDelay => 0.25f;

    public override void Setup(ITrapDEM trap, Vector3i pos)
    {
        vent = (BlockFlameVentDEM)trap;
        base.Setup(trap, pos);
    }

    /// <summary>The middle of the nozzles in world space and the way they point (flattened).</summary>
    private void Nozzle(out Vector3 origin, out Vector3 dir)
    {
        Vector3 sum = Vector3.zero;
        foreach (Vector3 n in vent.NozzleOffsets)
        {
            sum += n;
        }
        origin = transform.TransformPoint(sum / Mathf.Max(1, vent.NozzleOffsets.Length)) + Origin.position;
        dir = transform.TransformDirection(vent.NozzleForward);
        dir.y = 0f;
        dir = dir.sqrMagnitude > 0.0001f ? dir.normalized : Forward;
    }

    protected override bool Act(World world)
    {
        float now = Time.time;
        patches.RemoveAll(p => p.Until < now);
        bool napalm = Upgraded('A');
        bool torch = Upgraded('B');
        int owner = Owner(world);
        float burn = vent.BurnSeconds * DamageMult;

        // Napalm keeps burning on the ground between bursts
        if (napalm && patches.Count > 0)
        {
            foreach (Patch p in patches)
            {
                foreach (EntityAlive e in Enemies(world, p.Pos + Vector3.up, 1.5f))
                {
                    Vector3 flat = e.position - p.Pos;
                    flat.y = 0f;
                    if (flat.magnitude <= 1f && TrapStatusDEM.Ignite(e, burn, owner))
                    {
                        Touch(e, true);
                    }
                }
            }
        }

        if (!HasAmmo)
        {
            Cooldown = 0.5f;
            return false;
        }
        Nozzle(out Vector3 origin, out Vector3 dir);
        float range = torch ? vent.BlowtorchRange : vent.Range;
        float angle = torch ? vent.BlowtorchAngle : vent.ConeAngle;
        float minCos = Mathf.Cos(angle * 0.5f * Mathf.Deg2Rad);
        float damage = vent.DamagePerSecond * vent.PulseDelay * DamageMult * (torch ? vent.BlowtorchDamage : 1f);
        hit.Clear();
        hit.Add(napalm ? -2 : torch ? -3 : -1);
        foreach (EntityAlive e in Enemies(world, origin + dir * (range * 0.5f), range * 0.5f + 1f))
        {
            Vector3 chest = e.getChestPosition();
            Vector3 to = chest - origin;
            float dist = to.magnitude;
            if (dist > range || dist < 0.01f || Vector3.Dot(to / dist, dir) < minCos)
            {
                continue;
            }
            if (!Reachable(world, origin + dir * 0.3f, chest))
            {
                continue;
            }
            Touch(e, true);
            if (Hit(e, damage, EnumDamageTypes.Heat, to / dist, owner))
            {
                TrapStatusDEM.Ignite(e, burn, owner);
            }
            hit.Add(e.entityId);
        }
        if (hit.Count == 1)
        {
            return false;
        }
        UseAmmo(Settings.AmmoPerUse, out _);
        Wear(world);
        if (napalm)
        {
            Ground(world, origin, dir, range, now + vent.NapalmSeconds);
        }
        soundTimer -= vent.PulseDelay;
        if (soundTimer <= 0f)
        {
            soundTimer = 1.5f;
            Audio.Manager.BroadcastPlay(origin, vent.FireSound);
        }
        Broadcast(origin, hit.ToArray());
        return true;
    }

    /// <summary>Napalm: puddles of burning fuel on the ground along the jet.</summary>
    private void Ground(World world, Vector3 origin, Vector3 dir, float range, float until)
    {
        for (int i = 1; i <= 3; i++)
        {
            // On the floor the vent stands on
            Vector3 ground = origin + dir * (range * i / 3.5f);
            ground.y = BlockPos.y + 0.05f;
            Patch existing = patches.Find(x => (x.Pos - ground).sqrMagnitude < 0.5f);
            if (existing != null)
            {
                existing.Until = until;
            }
            else
            {
                patches.Add(new Patch { Pos = ground, Until = until });
            }
        }
    }

    public override void PlayFx(int[] ids)
    {
        int mode = ids.Length > 0 && ids[0] < 0 ? -ids[0] : 1;
        Nozzle(out Vector3 origin, out Vector3 dir);
        // A jet from every nozzle; each lasts until just after the next burst would start
        foreach (Vector3 n in vent.NozzleOffsets)
        {
            Vector3 at = transform.TransformPoint(n) + Origin.position;
            GameObject jet = FxDEM.Spawn(mode == 3 ? "FlameJetLong" : "FlameJet", at, Quaternion.LookRotation(dir),
                vent.PulseDelay + 0.1f, transform);
            if (jet == null)
            {
                FxDEM.Vanilla("p_flame_hazard", at + dir, Quaternion.LookRotation(dir), 0.8f);
            }
        }
        if (mode == 2)
        {
            float range = vent.Range;
            for (int i = 1; i <= 3; i++)
            {
                Vector3 p = origin + dir * (range * i / 3.5f);
                p.y = BlockPos.y + 0.05f;
                if (!NapalmShown(p))
                {
                    FxDEM.Spawn("GroundFire", p, Quaternion.identity, vent.NapalmSeconds);
                }
            }
        }
    }

    private readonly List<KeyValuePair<Vector3, float>> shownPatches = new List<KeyValuePair<Vector3, float>>();

    /// <summary>Client: don't stack a new ground fire on one that's still burning there.</summary>
    private bool NapalmShown(Vector3 p)
    {
        float now = Time.time;
        shownPatches.RemoveAll(kv => kv.Value < now);
        foreach (KeyValuePair<Vector3, float> kv in shownPatches)
        {
            if ((kv.Key - p).sqrMagnitude < 0.5f)
            {
                return true;
            }
        }
        shownPatches.Add(new KeyValuePair<Vector3, float>(p, now + vent.NapalmSeconds - 0.6f));
        return false;
    }
}
