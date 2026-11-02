using System;
using System.Collections.Generic;
using UnityEngine;
using static GfxJuiceParticles;
using Random = UnityEngine.Random;

/// <summary>
/// Game juice's recipes: what each event throws off, built from GfxJuiceParticles bits, GfxJuiceDebris pieces,
/// GfxJuiceDecals marks, the hit flash and the screen. GfxJuicePatches calls in here from the game's own events;
/// Update runs the things that carry on over time (barrel heat, pools spreading under the dead, loot glints, vehicle
/// dust). Every recipe checks its area's switch and how close it is, and scales its counts by the Juice amount.
/// All positions here are world coordinates (Unity's plus Origin.position).
/// </summary>
public static class GfxJuiceEffects
{
    public enum Surface { None, Metal, Stone, Gravel, Wood, Earth, Sand, Snow, Plant, Grass, Leaves, Cloth, Glass, Organic, Water }
    public enum Weapon { None, Pistol, Smg, Rifle, MachineGun, Shotgun, DoubleBarrel, Bow, Launcher, Nailgun }

    private const float NearHits = 90f, NearSteps = 45f, NearVehicles = 80f, NearGlints = 50f;

    // Colors (linear); glowing ones are brighter than 1 so bloom picks them up
    private static readonly Color SparkHot = new Color(6f, 3.2f, 1.1f), SparkCool = new Color(1.6f, 0.35f, 0.05f);
    private static readonly Color Ember = new Color(4f, 1.4f, 0.3f), EmberCool = new Color(0.9f, 0.12f, 0f);
    private static readonly Color MuzzleFlash = new Color(7f, 4.5f, 2f);
    private static readonly Color Tracer = new Color(4f, 2.6f, 1.1f);
    private static readonly Color Blood = new Color(0.15f, 0.01f, 0.008f, 1f);
    private static readonly Color BloodMist = new Color(0.2f, 0.012f, 0.01f, 0.4f);
    private static readonly Color Brass = new Color(0.78f, 0.56f, 0.24f), ShellRed = new Color(0.55f, 0.06f, 0.05f);
    private static readonly Color GunSmoke = new Color(0.62f, 0.6f, 0.58f, 0.32f);
    private static readonly Color Gold = new Color(1.6f, 1.15f, 0.45f);
    private static readonly Color Glass = new Color(0.2f, 0.24f, 0.25f);    // dark, so the smoothness shows reflections rather than plastic

    private static Vector3 eye;             // the camera, world coordinates
    private static float now;

    // Gunfire: recent shots and impacts by shooter, to draw tracers between them; barrels that are hot
    private struct Shot
    {
        public int shooter;
        public Vector3 muzzle;
        public float time;
        public Weapon kind;
    }

    private struct Struck
    {
        public int shooter;
        public Vector3 at;
        public float time;
    }

    private class Barrel
    {
        public Transform muzzle;
        public float heat, lastShot, nextShimmer, nextWisp;
    }

    private static readonly List<Shot> shots = new List<Shot>();
    private static readonly List<Struck> struck = new List<Struck>();
    private static readonly Dictionary<int, Barrel> barrels = new Dictionary<int, Barrel>();
    private static readonly List<int> cooled = new List<int>();

    // Kills waiting for the body to land so a pool can spread under it
    private struct Corpse
    {
        public EntityAlive entity;
        public Vector3 position;        // where it was hit, for when there's no body (a test)
        public float at;
    }

    private static readonly List<Corpse> corpses = new List<Corpse>();

    // High-quality loot lying about
    private static readonly List<EntityItem> loot = new List<EntityItem>();
    private static readonly Dictionary<int, float> nextGlint = new Dictionary<int, float>();

    private static float nextVehicles;
    private static readonly Dictionary<int, Weapon> weapons = new Dictionary<int, Weapon>();
    private static readonly Dictionary<int, Surface> bodies = new Dictionary<int, Surface>();
    private static FastTags<TagGroup.Global> tagMotorTool, tagShotgun, tagMachinegun, tagHandgun, tagDrum, tagRifle, tagBow, tagCrossbow, tagLauncher, tagNailgun;
    private static bool tagsReady;
    private static int events;

    // ---- Every frame ----

    /// <summary>Called every frame from GfxJuice.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera, float deltaTime)
    {
        now = Time.time;
        eye = playerCamera.transform.position + Origin.position;
        shots.RemoveAll(s => now - s.time > 0.25f);
        struck.RemoveAll(s => now - s.time > 0.25f);
        UpdateBarrels(deltaTime);
        UpdateCorpses();
        UpdateLoot();
        if (now >= nextVehicles)
        {
            nextVehicles = now + 0.06f;
            UpdateVehicles();
        }
    }

    public static void Clear()
    {
        shots.Clear();
        struck.Clear();
        barrels.Clear();
        corpses.Clear();
    }

    private static bool Near(Vector3 at, float meters)
    {
        return (at - eye).sqrMagnitude < meters * meters;
    }

    private static void Note(string what)
    {
        events++;
        if (GfxJuice.Debug)
            Log.Out("[GraphicsExpanded] juice: " + what);
    }

    // ---- Hits on surfaces ----

    /// <summary>
    /// Something struck a surface: what the game showed as impact_{device}_on_{category}, at the point it hit, facing
    /// out of the block face. Bullets belong to Hits; tools, melee and zombies beating on blocks to Breaking.
    /// </summary>
    public static void Impact(string device, Surface surface, Vector3 at, Vector3 normal, Color blockColor, int shooterId)
    {
        bool bullet = device == "bullet";
        if (!GfxJuice.On(bullet ? GfxJuice.Area.Hits : GfxJuice.Area.Breaking) || !Near(at, NearHits))
            return;
        Note(device + " on " + surface + " at " + at);
        if (bullet)
            TracerTo(shooterId, at);
        float power = bullet ? 1f : device == "metal" ? 1.3f : device == "organic" ? 1.1f : 0.9f;
        Vector3 n = normal.sqrMagnitude > 0.5f ? normal.normalized : Vector3.up;
        Color tint = Usable(blockColor) ? blockColor : Default(surface);

        switch (surface)
        {
            case Surface.Metal:
                Sparks(at, n, 9f * power, 1f);
                Add(Shape.Flash, Look.Glowing, at + n * 0.03f, Vector3.zero, 0.06f, 0.1f, 0.14f, SparkHot * 0.6f, SparkHot * 0.2f, fadeIn: 0f);
                if (bullet)
                    PitAt(at, n, 0.035f);
                break;
            case Surface.Stone:
            case Surface.Gravel:
                Chips(GfxJuiceDebris.Kind.Chunk, at, n, 3f * power, tint, 0.012f, 0.03f, 0.15f, 8f);
                Dust(at, n, 2.5f * power, Lighter(tint, 0.25f), 0.08f, 0.45f);
                if (bullet || device == "metal")
                    Sparks(at, n, (bullet ? 2f : 3f) + (IsOre(at, n) ? 6f : 0f), 0.6f);
                if (bullet)
                    PitAt(at, n, 0.05f);
                break;
            case Surface.Wood:
                Chips(GfxJuiceDebris.Kind.Splinter, at, n, 4f * power, tint, 0.03f, 0.075f, 0.35f, 8f);
                Flecks(at, n, 4f * power, tint, 0.006f, 0.014f);
                Dust(at, n, 1f * power, Lighter(tint, 0.3f), 0.06f, 0.3f);
                if (bullet)
                    PitAt(at, n, 0.03f);
                break;
            case Surface.Earth:
            case Surface.Sand:
                Flecks(at, n, 6f * power, tint, 0.012f, 0.03f);
                Dust(at, n, 3f * power, Lighter(tint, 0.2f), 0.1f, 0.6f);
                break;
            case Surface.Snow:
                Flecks(at, n, 6f * power, new Color(0.9f, 0.93f, 0.97f), 0.012f, 0.03f);
                Dust(at, n, 3f * power, new Color(0.95f, 0.97f, 1f, 0.5f), 0.1f, 0.55f);
                break;
            case Surface.Plant:
            case Surface.Grass:
            case Surface.Leaves:
                Leaves(at + n * 0.05f, 3f * power, tint, 0.6f);
                break;
            case Surface.Glass:
                Chips(GfxJuiceDebris.Kind.Shard, at, n, 3f * power, Glass, 0.008f, 0.02f, 0.95f, 6f);
                Dust(at, n, 1f, new Color(0.8f, 0.82f, 0.82f, 0.25f), 0.03f, 0.12f);
                break;
            case Surface.Cloth:
                Flecks(at, n, 3f * power, tint, 0.005f, 0.012f);
                Dust(at, n, 2f * power, Lighter(tint, 0.4f), 0.05f, 0.25f);
                break;
            case Surface.Water:
                Splash(at, n, 1f * power);
                break;
            case Surface.Organic:
                break;
        }
    }

    /// <summary>A blood-and-guts surface? Left to the damage hook, which knows the creature.</summary>
    public static bool IsCreatureSurface(Surface surface)
    {
        return surface == Surface.Organic;
    }

    // ---- Creatures taking damage ----

    /// <summary>
    /// A creature took damage (EntityAlive.ProcessDamageResponseLocal, on every machine tracking it). Blood sprays from
    /// the hit along the shot, splatters the wall behind, drips into small splats where it lands; kills and headshots
    /// burst bigger, and a pool spreads under the body once it's down. Machines and drones spark.
    /// </summary>
    public static void Damage(EntityAlive victim, DamageResponse response, bool wasDead)
    {
        if (!GfxJuice.On(GfxJuice.Area.Hits) || victim == null || response.Source == null || response.Strength <= 0)
            return;
        if (response.Source.BuffClass != null)
            return;     // bleeding and burning ticks
        Vector3 at = response.Source.getHitTransformPosition();
        if (at.sqrMagnitude < 1e-4f)
            at = victim.position + Vector3.up * victim.height * 0.6f;
        if (!Near(at, NearHits))
            return;
        bool kill = !wasDead && (response.Fatal || victim.IsDead());
        bool head = (response.HitBodyPart & EnumBodyPartHit.Head) != 0;
        float strength = Mathf.Clamp01(response.Strength / Mathf.Max(victim.GetMaxHealth() * 0.35f, 30f));
        Vector3 flying = response.Source.getDirection();
        flying = flying.sqrMagnitude > 1e-4f ? flying.normalized : (victim.position - eye).normalized;
        Note((kill ? "kill " : "hit ") + victim.EntityName + (head ? " in the head" : "") + " for " + response.Strength);

        bool firstPerson = victim is EntityPlayerLocal local && local.bFirstPersonView;
        // Machines don't bleed; their sparks come with the game's own impact on metal (Impact)
        if (Body(victim) != Surface.Organic)
            return;
        if (!firstPerson)
            Bleed(victim, at, flying, strength, kill, head);
    }

    /// <summary>
    /// Blood from a hit at a point, flying on along the shot: the spray, a mist, a splatter on what's behind, and on a
    /// kill a pool under the body once it's down. gfxe juice test blood calls it without a creature.
    /// </summary>
    public static void Bleed(EntityAlive victim, Vector3 at, Vector3 flying, float strength, bool kill, bool head)
    {
        float burst = (1f + strength * 1.5f) * (kill ? 1.6f : 1f) * (head ? 1.5f : 1f);

        // The spray: a fan of fine droplets and a few bigger drops thrown on along the shot, short-tailed, falling into
        // splats where they land
        for (int i = GfxJuice.Count(10f * burst); i > 0; i--)
        {
            Vector3 v = (flying + Random.insideUnitSphere * 0.5f + Vector3.up * 0.2f) * Random.Range(2f, 6f);
            Add(Shape.Drop, Look.Lit, at + Random.insideUnitSphere * 0.04f, v, Random.Range(0.5f, 1f), Random.Range(0.003f, 0.007f), 0.004f, Blood, Blood,
                gravity: 9.8f, drag: 0.8f, stretch: 0.008f, hit: Hit.Blood, fadeIn: 0f, fadeOut: 0.8f);
        }
        for (int i = GfxJuice.Count(2f * burst); i > 0; i--)
        {
            Vector3 v = (flying + Random.insideUnitSphere * 0.4f + Vector3.up * 0.3f) * Random.Range(1.5f, 3.5f);
            Add(Shape.Drop, Look.Lit, at, v, Random.Range(0.8f, 1.4f), Random.Range(0.009f, 0.014f), 0.009f, Blood, Blood,
                gravity: 9.8f, drag: 0.3f, stretch: 0.006f, hit: Hit.Blood, fadeIn: 0f, fadeOut: 0.85f);
        }
        for (int i = GfxJuice.Count(head ? 4f : 1.5f + strength); i > 0; i--)
            Add(Shape.Puff, Look.Lit | Look.Soft, at + Random.insideUnitSphere * 0.05f, flying * 0.8f + Random.insideUnitSphere * 0.4f,
                Random.Range(0.4f, 0.8f), 0.06f, head ? 0.4f : 0.22f, BloodMist, BloodMist, drag: 3f, fadeIn: 0.02f, fadeOut: 0.3f);
        if (head)
        {
            for (int i = GfxJuice.Count(10f); i > 0; i--)
                Add(Shape.Drop, Look.Lit, at, (Vector3.up * 0.8f + Random.insideUnitSphere) * Random.Range(2f, 5f), Random.Range(0.6f, 1.2f),
                    Random.Range(0.004f, 0.01f), 0.005f, Blood, Blood, gravity: 9.8f, drag: 0.6f, stretch: 0.008f, hit: Hit.Blood, fadeIn: 0f, fadeOut: 0.85f);
        }

        // The wall or floor behind takes a splatter
        if (kill || head || Random.value < 0.35f + strength)
        {
            if (Physics.Raycast(at - Origin.position, flying, out RaycastHit hit, 2.5f, GfxJuice.WorldMask, QueryTriggerInteraction.Ignore))
                GfxJuiceDecals.Splat(hit.point + Origin.position, hit.normal, flying, Mathf.Lerp(0.25f, 0.6f, Mathf.Max(strength, kill ? 0.6f : 0f)));
        }
        if (kill)
            corpses.Add(new Corpse { entity = victim, position = at, at = now + 1.5f });
    }

    /// <summary>What a creature is made of, from its entity class (the same property the game picks its impact particle by).</summary>
    private static Surface Body(EntityAlive entity)
    {
        if (bodies.TryGetValue(entity.entityClass, out Surface known))
            return known;
        Surface surface = Surface.None;
        try
        {
            surface = ParseCategory(EntityClass.list[entity.entityClass].Properties.GetValue("SurfaceCategory"));
        }
        catch (Exception)
        {
        }
        if (surface == Surface.None)
            surface = entity is EntityVehicle || entity is EntityTurret || entity is EntityDrone ? Surface.Metal : Surface.Organic;
        bodies[entity.entityClass] = surface;
        return surface;
    }

    private static void UpdateCorpses()
    {
        for (int i = corpses.Count - 1; i >= 0; i--)
        {
            if (now < corpses[i].at)
                continue;
            Corpse corpse = corpses[i];
            corpses.RemoveAt(i);
            if (!GfxJuice.On(GfxJuice.Area.Hits))
                continue;
            Vector3 from = (corpse.entity != null ? corpse.entity.position : corpse.position) - Origin.position + Vector3.up * 0.6f;
            if (Physics.Raycast(from, Vector3.down, out RaycastHit hit, 2.5f, GfxJuice.WorldMask, QueryTriggerInteraction.Ignore) && hit.normal.y > 0.5f)
                GfxJuiceDecals.Pool(hit.point + Origin.position, hit.normal, Random.Range(0.35f, 0.55f));
        }
    }

    // ---- Gunfire ----

    /// <summary>
    /// A gun fired (ItemActionRanged.ItemActionEffects, on every machine near the shooter): a brighter flare and sparks
    /// at the muzzle on top of the game's flash, smoke that hangs, a casing thrown out to the right, and the barrel
    /// heating up under sustained fire until the air over it shimmers.
    /// </summary>
    public static void Fired(EntityAlive holder, ItemValue item, Transform muzzle)
    {
        if (!GfxJuice.On(GfxJuice.Area.Shooting) || holder == null || item == null || muzzle == null)
            return;
        Weapon kind = KindOf(item);
        if (kind == Weapon.None)
            return;
        Vector3 at = muzzle.position + Origin.position;
        if (!Near(at, NearHits))
            return;
        Vector3 forward = muzzle.forward, right = muzzle.right, up = muzzle.up;
        Note("shot " + kind + " by " + holder.EntityName);

        shots.Add(new Shot { shooter = holder.entityId, muzzle = at, time = now, kind = kind });
        for (int i = struck.Count - 1; i >= 0; i--)
        {
            if (struck[i].shooter == holder.entityId)
            {
                Trace(kind, at, struck[i].at);
                struck.RemoveAt(i);
            }
        }

        bool firearm = kind != Weapon.Bow && kind != Weapon.Nailgun;
        if (!firearm)
            return;
        float size = kind == Weapon.Pistol ? 0.09f : kind == Weapon.Shotgun || kind == Weapon.DoubleBarrel ? 0.2f : kind == Weapon.Launcher ? 0.3f : 0.14f;
        Add(Shape.Flash, Look.Glowing, at + forward * size * 0.6f, Vector3.zero, 0.05f, size, size * 1.3f, MuzzleFlash, MuzzleFlash * 0.3f, fadeIn: 0f, fadeOut: 0.3f);
        for (int i = GfxJuice.Count(kind == Weapon.Shotgun || kind == Weapon.DoubleBarrel ? 7f : 3f); i > 0; i--)
            Add(Shape.Spark, Look.Glowing, at, (forward + Random.insideUnitSphere * 0.3f) * Random.Range(10f, 22f), Random.Range(0.05f, 0.12f),
                0.006f, 0.004f, SparkHot, SparkCool, gravity: 4f, drag: 2f, stretch: 0.012f, fadeIn: 0f);
        Vector3 carried = holder.GetVelocityPerSecond();
        for (int i = GfxJuice.Count(kind == Weapon.Launcher ? 6f : 1.5f); i > 0; i--)
            Add(Shape.Smoke, Look.Lit | Look.Soft, at + forward * 0.1f, carried + forward * Random.Range(0.8f, 2.2f) + Random.insideUnitSphere * 0.3f,
                Random.Range(1.2f, 2.2f), 0.04f, kind == Weapon.Launcher ? 0.9f : 0.28f, GunSmoke, GunSmoke, gravity: -0.25f, drag: 1.8f, fadeIn: 0.05f, fadeOut: 0.4f);

        if (kind != Weapon.Launcher && kind != Weapon.DoubleBarrel)
            Eject(kind, at, forward, right, up, carried);

        if (!barrels.TryGetValue(holder.entityId, out Barrel barrel))
            barrels[holder.entityId] = barrel = new Barrel();
        barrel.muzzle = muzzle;
        barrel.heat = Mathf.Min(barrel.heat + (kind == Weapon.MachineGun ? 0.32f : kind == Weapon.Smg ? 0.22f : kind == Weapon.Pistol ? 0.15f : 0.3f), 3.5f);
        barrel.lastShot = now;
    }

    /// <summary>A spent casing (or shotgun shell) thrown out of the port behind the muzzle, to the right.</summary>
    private static void Eject(Weapon kind, Vector3 muzzle, Vector3 forward, Vector3 right, Vector3 up, Vector3 carried)
    {
        if (GfxJuice.Amount <= 0f)
            return;
        bool shell = kind == Weapon.Shotgun;
        float back = kind == Weapon.Pistol ? 0.12f : shell ? 0.32f : 0.38f;
        Vector3 port = muzzle - forward * back + up * 0.03f;
        Vector3 v = carried + right * Random.Range(2f, 3.4f) + up * Random.Range(1.2f, 2.4f) - forward * Random.Range(0.2f, 0.8f);
        Vector3 scale = shell ? new Vector3(0.062f, 0.02f, 0.02f) : kind == Weapon.Pistol ? new Vector3(0.02f, 0.009f, 0.009f) : new Vector3(0.042f, 0.011f, 0.011f);
        GfxJuiceDebris.Add(GfxJuiceDebris.Kind.Casing, port, v, scale, shell ? ShellRed : Brass, shell ? 0.45f : 0.72f, shell ? 0.1f : 1f,
            shell ? 45f : 60f, spin: Random.Range(900f, 1600f));
    }

    /// <summary>A bullet struck: draw a tracer from the shooter's muzzle if they've just fired, or keep it for when they do.</summary>
    private static void TracerTo(int shooterId, Vector3 at)
    {
        for (int i = shots.Count - 1; i >= 0; i--)
        {
            if (shots[i].shooter == shooterId)
            {
                Trace(shots[i].kind, shots[i].muzzle, at);
                return;
            }
        }
        struck.Add(new Struck { shooter = shooterId, at = at, time = now });
    }

    /// <summary>A streak of light racing from the muzzle to where it hit: rifles, machine guns and SMGs.</summary>
    private static void Trace(Weapon kind, Vector3 from, Vector3 to)
    {
        if (kind != Weapon.Rifle && kind != Weapon.MachineGun && kind != Weapon.Smg)
            return;
        Vector3 path = to - from;
        float distance = path.magnitude;
        if (distance < 4f)
            return;
        Vector3 direction = path / distance;
        const float speed = 320f;
        Add(Shape.Spark, Look.Glowing, from + direction * 1.5f, direction * speed, (distance - 1.5f) / speed, 0.011f, 0.011f, Tracer, Tracer,
            stretch: 0.012f, fadeIn: 0f, fadeOut: 0.97f);
    }

    /// <summary>Hot barrels: shimmering air over them while hot, and a wisp of smoke once firing stops.</summary>
    private static void UpdateBarrels(float deltaTime)
    {
        cooled.Clear();
        foreach (KeyValuePair<int, Barrel> pair in barrels)
        {
            Barrel b = pair.Value;
            b.heat -= deltaTime * 0.3f;
            if (b.heat <= 0f || b.muzzle == null)
            {
                cooled.Add(pair.Key);
                continue;
            }
            if (b.heat < 1f || !GfxJuice.On(GfxJuice.Area.Shooting))
                continue;
            Vector3 at = b.muzzle.position + Origin.position;
            if (!Near(at, 30f))
                continue;
            float hot = Mathf.Clamp01((b.heat - 1f) / 1.5f);
            if (now >= b.nextShimmer)
            {
                b.nextShimmer = now + 0.07f;
                AddWarp(Warp.Shimmer, at + Vector3.up * 0.04f - b.muzzle.forward * Random.Range(0f, 0.25f), Vector3.up * 0.45f + GfxJuice.Wind * 0.1f,
                    0.8f, 0.04f, 0.13f, 0.25f + 0.6f * hot);
            }
            if (now - b.lastShot > 0.3f && now >= b.nextWisp)
            {
                b.nextWisp = now + Mathf.Lerp(0.35f, 0.12f, hot);
                Add(Shape.Smoke, Look.Lit | Look.Soft, at - b.muzzle.forward * Random.Range(0f, 0.2f), Vector3.up * 0.35f, 1.6f, 0.012f, 0.07f,
                    new Color(0.7f, 0.7f, 0.7f, 0.22f * (0.4f + hot)), new Color(0.75f, 0.75f, 0.75f, 0f), gravity: -0.15f, drag: 1.2f, fadeIn: 0.15f);
            }
        }
        foreach (int key in cooled)
            barrels.Remove(key);
    }

    /// <summary>What kind of gun it is, by the game's tags (cached per item type). Motor tools aren't guns.</summary>
    public static Weapon KindOf(ItemValue item)
    {
        if (weapons.TryGetValue(item.type, out Weapon known))
            return known;
        if (!tagsReady)
        {
            tagMotorTool = FastTags<TagGroup.Global>.Parse("motorTool");
            tagShotgun = FastTags<TagGroup.Global>.Parse("shotgun");
            tagMachinegun = FastTags<TagGroup.Global>.Parse("machinegunSkill");
            tagHandgun = FastTags<TagGroup.Global>.Parse("handgunSkill");
            tagDrum = FastTags<TagGroup.Global>.Parse("drumMagazine");
            tagRifle = FastTags<TagGroup.Global>.Parse("rifleSkill");
            tagBow = FastTags<TagGroup.Global>.Parse("bow");
            tagCrossbow = FastTags<TagGroup.Global>.Parse("crossbow");
            tagLauncher = FastTags<TagGroup.Global>.Parse("launcher");
            tagNailgun = FastTags<TagGroup.Global>.Parse("nailgun");
            tagsReady = true;
        }
        ItemClass ic = item.ItemClass;
        Weapon kind = Weapon.None;
        if (ic != null && !ic.HasAnyTags(tagMotorTool))
        {
            string name = ic.GetItemName() ?? "";
            if (ic.HasAnyTags(tagShotgun))
                kind = name.IndexOf("DoubleBarrel", StringComparison.OrdinalIgnoreCase) >= 0 ? Weapon.DoubleBarrel : Weapon.Shotgun;
            else if (ic.HasAnyTags(tagMachinegun))
                kind = Weapon.MachineGun;
            else if (ic.HasAnyTags(tagHandgun))
                kind = ic.HasAnyTags(tagDrum) ? Weapon.Smg : Weapon.Pistol;
            else if (ic.HasAnyTags(tagRifle))
                kind = Weapon.Rifle;
            else if (ic.HasAnyTags(tagBow) || ic.HasAnyTags(tagCrossbow))
                kind = Weapon.Bow;
            else if (ic.HasAnyTags(tagLauncher))
                kind = Weapon.Launcher;
            else if (ic.HasAnyTags(tagNailgun))
                kind = Weapon.Nailgun;
        }
        weapons[item.type] = kind;
        return kind;
    }

    // ---- Breaking things ----

    /// <summary>A block broke (the game's blockdestroy_ / door / tree particles): it bursts into chunks and dust.</summary>
    public static void Broke(Surface surface, Vector3 at, Color blockColor, bool tree)
    {
        if (!GfxJuice.On(GfxJuice.Area.Breaking) || !Near(at, NearHits))
            return;
        Note("broke " + surface + (tree ? " tree" : "") + " at " + at);
        Color tint = Usable(blockColor) ? blockColor : Default(surface);
        if (tree)
        {
            Burst(GfxJuiceDebris.Kind.Splinter, at, 8f, tint, 0.04f, 0.12f, 0.3f, 25f, 4f);
            Leaves(at + Vector3.up * 2.5f, 8f, new Color(0.24f, 0.33f, 0.12f), 2f);
            DustCloud(at - Vector3.up * 0.3f, 1.5f, new Color(0.55f, 0.5f, 0.42f), 0.8f);
            CeilingDust(at, 0.5f);
            return;
        }
        switch (surface)
        {
            case Surface.Wood:
                Burst(GfxJuiceDebris.Kind.Splinter, at, 7f, tint, 0.03f, 0.09f, 0.3f, 20f, 3.5f);
                Burst(GfxJuiceDebris.Kind.Chunk, at, 3f, tint, 0.015f, 0.04f, 0.25f, 20f, 3f);
                break;
            case Surface.Glass:
                Burst(GfxJuiceDebris.Kind.Shard, at, 8f, Glass, 0.01f, 0.035f, 0.95f, 15f, 2.5f);
                break;
            case Surface.Metal:
                Burst(GfxJuiceDebris.Kind.Chunk, at, 5f, Darker(tint, 0.2f), 0.015f, 0.045f, 0.5f, 20f, 3.5f, metallic: 0.9f);
                Burst(GfxJuiceDebris.Kind.Shard, at, 3f, Darker(tint, 0.1f), 0.02f, 0.05f, 0.5f, 20f, 3.5f, metallic: 0.9f);
                Sparks(at, Vector3.up, 6f, 1.2f);
                break;
            case Surface.Plant:
            case Surface.Grass:
            case Surface.Leaves:
                Leaves(at, 6f, tint, 1f);
                return;
            case Surface.Earth:
            case Surface.Sand:
            case Surface.Snow:
                for (int i = GfxJuice.Count(10f); i > 0; i--)
                    Add(Shape.Clod, Look.Lit, at + Random.insideUnitSphere * 0.4f, (Random.insideUnitSphere + Vector3.up * 0.6f) * Random.Range(1.5f, 3.5f),
                        Random.Range(0.6f, 1.2f), Random.Range(0.015f, 0.035f), 0.02f, Opaque(surface == Surface.Snow ? new Color(0.92f, 0.95f, 1f) : tint), Opaque(tint),
                        gravity: 9.8f, drag: 0.3f, hit: Hit.Die, spin: Random.Range(-6f, 6f), fadeIn: 0f, fadeOut: 0.85f);
                break;
            case Surface.Water:
                Splash(at, Vector3.up, 2f);
                return;
            default:
                Burst(GfxJuiceDebris.Kind.Chunk, at, 7f, tint, 0.015f, 0.05f, 0.15f, 20f, 3.5f);
                break;
        }
        if (surface != Surface.Glass)
            DustCloud(at, 1.5f, Lighter(tint, 0.25f), 0.6f);
        CeilingDust(at, 0.6f);
    }

    /// <summary>
    /// A block's damage changed without it breaking, from whatever hit it, here or on another machine (zombies beating on
    /// a wall come through here on every client). Indoors near the player, dust sifts down from the ceiling.
    /// </summary>
    public static void BlockDamaged(Vector3 at)
    {
        if (!GfxJuice.On(GfxJuice.Area.Breaking) || !Near(at, 14f))
            return;
        CeilingDust(at, 0.35f);
    }

    /// <summary>
    /// An explosion (GameManager.ExplosionClient, on every machine): a flash, a shockwave rippling the air, debris and
    /// embers thrown high, a ring of dust racing out along the ground, a smoke column that drifts on the wind, a
    /// scorch mark, and the camera shaken by how close it was.
    /// </summary>
    public static void Exploded(Vector3 at, float radius, EntityPlayerLocal player)
    {
        if (!GfxJuice.On(GfxJuice.Area.Breaking))
            return;
        radius = Mathf.Clamp(radius, 1f, 12f);
        float distance = (at - eye).magnitude;
        Note("explosion r" + radius + " at " + at + ", " + distance + " m away");
        if (player != null && player.vp_FPCamera != null && distance < radius * 8f)
        {
            float shake = Mathf.Pow(1f - distance / (radius * 8f), 2f) * Mathf.Clamp(radius / 4f, 0.5f, 1.5f) * GfxJuice.Amount;
            player.vp_FPCamera.DoBomb(new Vector3(1f, -10f, 1f) * (0.6f * shake), 1f * shake, 2f * shake);
        }
        if (distance > 250f)
            return;

        // Where's the ground under it, and what's it made of
        Vector3 ground = at;
        Vector3 groundNormal = Vector3.up;
        bool onGround = Physics.Raycast(at - Origin.position + Vector3.up * 0.5f, Vector3.down, out RaycastHit hit, radius + 1.5f, GfxJuice.WorldMask, QueryTriggerInteraction.Ignore);
        if (onGround)
        {
            ground = hit.point + Origin.position;
            groundNormal = hit.normal;
        }
        Surface surface = GroundSurface(ground, out Color groundColor);
        Color dirt = Usable(groundColor) ? groundColor : Default(surface == Surface.None ? Surface.Earth : surface);

        Add(Shape.Flash, Look.Glowing, at + Vector3.up * 0.5f, Vector3.zero, 0.14f, radius * 0.6f, radius * 1.3f, new Color(9f, 5.5f, 2.2f), new Color(3f, 1f, 0.2f), fadeIn: 0f, fadeOut: 0.2f);
        AddWarp(Warp.Shockwave, at + Vector3.up * 0.5f, Vector3.zero, 0.5f, radius * 0.3f, radius * 3.5f, 0.7f);

        Burst(GfxJuiceDebris.Kind.Chunk, ground + Vector3.up * 0.3f, 14f, dirt, 0.04f, 0.14f, 0.15f, 25f, 7f + radius, upward: 1.3f);
        for (int i = GfxJuice.Count(6f); i > 0; i--)
            GfxJuiceDebris.Add(GfxJuiceDebris.Kind.Chunk, ground + Vector3.up * 0.3f, (Random.insideUnitSphere + Vector3.up * 1.4f) * Random.Range(5f, 10f),
                Vector3.one * Random.Range(0.03f, 0.07f), new Color(0.12f, 0.1f, 0.08f), 0.2f, 0f, 20f, glow: 6f, cooling: 0.8f);
        for (int i = GfxJuice.Count(30f + radius * 4f); i > 0; i--)
            Add(Shape.Spark, Look.Glowing, at + Random.insideUnitSphere * radius * 0.3f, (Random.insideUnitSphere + Vector3.up * 1.1f) * Random.Range(3f, 12f),
                Random.Range(1.2f, 3.5f), 0.012f, 0.006f, Ember, EmberCool, gravity: 3.5f, drag: 0.7f, stretch: 0.02f, hit: Hit.Bounce, fadeIn: 0f, fadeOut: 0.5f);

        if (onGround && groundNormal.y > 0.5f)
        {
            Color ring = Lighter(dirt, 0.2f);
            ring.a = 0.55f;
            Add(Shape.Ring, Look.Lit | Look.Flat, ground, Vector3.zero, 0.9f, radius * 0.4f, radius * 2.8f, ring, new Color(ring.r, ring.g, ring.b, 0f), normal: groundNormal, fadeIn: 0f, fadeOut: 0.3f);
            GfxJuiceDecals.Scorch(ground, groundNormal, Mathf.Clamp(radius * 0.55f, 0.8f, 3.5f));
        }
        DustCloud(ground + Vector3.up * 0.3f, 8f, Lighter(dirt, 0.15f), radius * 0.6f);
        // The smoke: all one color, so overlapping puffs look the same whichever is drawn on top as the view moves
        Color smoke = new Color(0.22f, 0.21f, 0.2f, 0.5f);
        for (int i = GfxJuice.Count(8f); i > 0; i--)
        {
            Vector3 start = at + new Vector3(Random.Range(-1f, 1f), Random.Range(0f, 1f), Random.Range(-1f, 1f)) * radius * 0.4f;
            Add(Shape.Smoke, Look.Lit | Look.Soft, start, Vector3.up * Random.Range(1.5f, 3.5f) + Random.insideUnitSphere, Random.Range(3.5f, 6f),
                radius * 0.25f + 0.4f, radius * 0.8f + 1.5f, smoke, smoke, gravity: -0.3f, drag: 0.6f, spin: Random.Range(-0.3f, 0.3f), fadeIn: 0.04f, fadeOut: 0.35f);
        }
        if (distance < 25f)
            CeilingDust(at, 1.2f);
    }

    // ---- Moving through the world ----

    /// <summary>
    /// A footstep (EntityAlive.PlayStepSound: the local player, other players, zombies and animals, on every machine
    /// near them). The step sound names the surface: dust off dirt, sand and gravel, mud when the ground's wet, snow
    /// kicked up, splashes in water and puddles, leaves shed pushing through bushes.
    /// </summary>
    public static void Step(EntityAlive walker, string sound)
    {
        if (!GfxJuice.On(GfxJuice.Area.Moving) || walker == null || string.IsNullOrEmpty(sound))
            return;
        Vector3 at = walker.position;
        if (!Near(at, NearSteps))
            return;
        Surface surface = StepSurface(sound);
        if (surface == Surface.None)
            return;
        bool heavy = sound.StartsWith("heavy") || sound.StartsWith("large") || sound.StartsWith("animalhvy") || sound.StartsWith("barehvy");
        float size = heavy ? 1.5f : walker is EntityPlayerLocal ? 0.7f : 1f;
        Vector3 moving = walker.GetVelocityPerSecond();
        moving.y = 0f;

        float wet = GfxWeather.Wetness;
        bool puddle = GfxWeather.Puddles > 0.05f && Random.value < GfxWeather.Puddles * 1.5f && GfxWeather.OpenToSky(at + Vector3.up);
        switch (surface)
        {
            case Surface.Earth:
            case Surface.Sand:
            case Surface.Gravel:
            case Surface.Grass:
                if (puddle)
                    Splash(at, Vector3.up, 0.5f * size);
                else if (wet > 0.4f)
                    Mud(at, moving, size);
                else
                {
                    Color dust = surface == Surface.Sand ? new Color(0.78f, 0.68f, 0.5f, 0.5f) : surface == Surface.Gravel ? new Color(0.56f, 0.55f, 0.52f, 0.35f)
                        : surface == Surface.Grass ? new Color(0.45f, 0.43f, 0.33f, 0.2f) : new Color(0.5f, 0.42f, 0.33f, 0.42f);
                    float puffs = (surface == Surface.Sand ? 2f : surface == Surface.Grass ? 0.6f : 1.4f) * size;
                    for (int i = GfxJuice.Count(puffs); i > 0; i--)
                        Add(Shape.Puff, Look.Lit | Look.Soft, at + Random.insideUnitSphere * 0.15f + Vector3.up * 0.05f,
                            -moving * 0.15f + new Vector3(Random.Range(-0.4f, 0.4f), Random.Range(0.2f, 0.5f), Random.Range(-0.4f, 0.4f)),
                            Random.Range(0.9f, 1.6f), 0.07f * size, 0.32f * size, dust, dust, gravity: 0.05f, drag: 2.5f, fadeIn: 0.1f, fadeOut: 0.3f);
                }
                break;
            case Surface.Snow:
                for (int i = GfxJuice.Count(3f * size); i > 0; i--)
                    Add(Shape.Clod, Look.Lit, at + Vector3.up * 0.05f, -moving * 0.2f + (Random.insideUnitSphere * 0.6f + Vector3.up * 0.9f) * Random.Range(0.8f, 1.8f),
                        Random.Range(0.4f, 0.8f), Random.Range(0.012f, 0.025f), 0.012f, Opaque(new Color(0.92f, 0.95f, 1f)), Opaque(new Color(0.92f, 0.95f, 1f)),
                        gravity: 9.8f, drag: 0.6f, hit: Hit.Die, fadeIn: 0f, fadeOut: 0.8f);
                Add(Shape.Puff, Look.Lit | Look.Soft, at + Vector3.up * 0.08f, Vector3.up * 0.2f, 1f, 0.06f * size, 0.25f * size,
                    new Color(0.95f, 0.97f, 1f, 0.35f), new Color(0.95f, 0.97f, 1f, 0.35f), drag: 2f, fadeIn: 0.05f, fadeOut: 0.3f);
                break;
            case Surface.Water:
                Splash(at, Vector3.up, 0.6f * size);
                break;
            case Surface.Leaves:
                Leaves(at + Vector3.up * Random.Range(0.4f, 0.9f), 2.5f * size, LeafColor(walker), 0.4f);
                break;
            case Surface.Stone:
            case Surface.Metal:
            case Surface.Wood:
                if (puddle)
                    Splash(at, Vector3.up, 0.4f * size);
                break;
        }
    }

    /// <summary>The local player landed hard (EntityPlayerLocal.FallImpact): a ring of dust out from their feet. The game dips the camera itself.</summary>
    public static void Landed(EntityPlayerLocal player, float speed)
    {
        if (!GfxJuice.On(GfxJuice.Area.Moving) || player == null || speed < 0.18f)
            return;
        Vector3 at = player.position;
        Surface surface = GroundSurface(at, out Color color);
        Note("landed at " + speed + " on " + surface);
        float strength = Mathf.Clamp01((speed - 0.18f) / 0.5f);
        if (surface == Surface.Water)
        {
            Splash(at, Vector3.up, 1f + strength);
            return;
        }
        Color dust = surface == Surface.Snow ? new Color(0.95f, 0.97f, 1f, 0.5f) : Lighter(Usable(color) ? color : Default(surface == Surface.None ? Surface.Earth : surface), 0.2f);
        dust.a = surface == Surface.Stone || surface == Surface.Metal || surface == Surface.Wood ? 0.25f : 0.5f;
        Add(Shape.Ring, Look.Lit | Look.Flat, at + Vector3.up * 0.02f, Vector3.zero, 0.6f, 0.2f, 1.2f + strength, dust, new Color(dust.r, dust.g, dust.b, 0f), normal: Vector3.up, fadeIn: 0f, fadeOut: 0.3f);
        for (int i = GfxJuice.Count(4f + 4f * strength); i > 0; i--)
        {
            Vector3 outward = Quaternion.Euler(0f, Random.value * 360f, 0f) * Vector3.forward;
            Add(Shape.Puff, Look.Lit | Look.Soft, at + outward * 0.2f + Vector3.up * 0.05f, outward * Random.Range(1f, 2.5f) + Vector3.up * 0.2f,
                Random.Range(0.8f, 1.4f), 0.08f, 0.35f, dust, dust, drag: 2.5f, fadeIn: 0.05f, fadeOut: 0.3f);
        }
    }

    /// <summary>Vehicles moving on dirt, sand or snow throw dust, mud or snow out behind their wheels, on every machine (they drive remotely too).</summary>
    private static void UpdateVehicles()
    {
        if (!GfxJuice.On(GfxJuice.Area.Moving))
            return;
        World world = GameManager.Instance.World;
        List<Entity> entities = world?.Entities?.list;
        if (entities == null)
            return;
        Vector3 origin = Origin.position;
        foreach (Entity entity in entities)
        {
            if (!(entity is EntityVehicle vehicle) || vehicle.wheels == null || !Near(vehicle.position, NearVehicles))
                continue;
            Vector3 velocity = vehicle.GetVelocityPerSecond();
            float speed = velocity.magnitude;
            if (speed < 2.5f)
                continue;
            float amount = Mathf.Clamp01((speed - 2.5f) / 12f);
            foreach (EntityVehicle.Wheel wheel in vehicle.wheels)
            {
                if (wheel?.tireT == null)
                    continue;
                if (!Physics.Raycast(wheel.tireT.position + Vector3.up * 0.2f, Vector3.down, out RaycastHit hit, 1.6f, GfxJuice.WorldMask, QueryTriggerInteraction.Ignore))
                    continue;
                Vector3 at = hit.point + origin;
                Surface surface = GroundSurface(at, out Color _);
                if (surface == Surface.Snow)
                {
                    for (int i = GfxJuice.Count(1.2f * amount + 0.3f); i > 0; i--)
                        Add(Shape.Puff, Look.Lit | Look.Soft, at + Vector3.up * 0.1f, -velocity * 0.25f + Vector3.up * Random.Range(0.5f, 1.5f) + Random.insideUnitSphere * 0.5f,
                            Random.Range(1f, 1.8f), 0.15f, 0.7f, new Color(0.95f, 0.97f, 1f, 0.45f), new Color(0.95f, 0.97f, 1f, 0.45f), gravity: 0.6f, drag: 1.5f, fadeIn: 0.05f, fadeOut: 0.3f);
                }
                else if (surface == Surface.Earth || surface == Surface.Sand || surface == Surface.Gravel || surface == Surface.Grass)
                {
                    if (GfxWeather.Wetness > 0.4f)
                    {
                        for (int i = GfxJuice.Count(1.5f * amount + 0.3f); i > 0; i--)
                            Add(Shape.Clod, Look.Lit, at + Vector3.up * 0.1f, -velocity * 0.3f + (Vector3.up * 1.2f + Random.insideUnitSphere) * Random.Range(1f, 2.5f),
                                Random.Range(0.5f, 0.9f), Random.Range(0.012f, 0.03f), 0.015f, Opaque(new Color(0.16f, 0.12f, 0.08f)), Opaque(new Color(0.16f, 0.12f, 0.08f)),
                                gravity: 9.8f, drag: 0.3f, hit: Hit.Die, spin: Random.Range(-6f, 6f), fadeIn: 0f, fadeOut: 0.8f);
                        continue;
                    }
                    Color dust = surface == Surface.Sand ? new Color(0.78f, 0.68f, 0.5f, 0.5f) : surface == Surface.Gravel ? new Color(0.58f, 0.57f, 0.54f, 0.4f)
                        : surface == Surface.Grass ? new Color(0.5f, 0.47f, 0.37f, 0.25f) : new Color(0.55f, 0.47f, 0.37f, 0.45f);
                    for (int i = GfxJuice.Count(amount * (surface == Surface.Grass ? 0.5f : 1.2f) + 0.2f); i > 0; i--)
                        Add(Shape.Puff, Look.Lit | Look.Soft, at + Vector3.up * 0.15f, -velocity * 0.2f + Vector3.up * Random.Range(0.3f, 1.2f) + Random.insideUnitSphere * 0.6f,
                            Random.Range(2f, 3.5f), 0.2f, 1.1f + amount, dust, new Color(dust.r, dust.g, dust.b, dust.a * 0.6f), gravity: 0.05f, drag: 1.2f, fadeIn: 0.05f, fadeOut: 0.35f);
                }
            }
        }
    }

    // ---- Rewards ----

    /// <summary>The local player went up a level: the golden burst on screen and sparkles rising round them.</summary>
    public static void LevelUp(EntityPlayerLocal player)
    {
        if (!GfxJuice.On(GfxJuice.Area.Rewards) || player == null)
            return;
        Note("level up");
        GfxJuiceScreen.Reward(1f);
        Sparkle(player.position, 6f, 0.8f);
    }

    /// <summary>The local player finished a quest: a smaller burst.</summary>
    public static void QuestDone(EntityPlayerLocal player)
    {
        if (!GfxJuice.On(GfxJuice.Area.Rewards) || player == null)
            return;
        Note("quest done");
        GfxJuiceScreen.Reward(0.5f);
    }

    /// <summary>An item lying on the ground came into view (EntityItem.createMesh): high quality loot glints now and then.</summary>
    public static void ItemShown(EntityItem item)
    {
        ItemValue value = item?.itemStack?.itemValue;
        if (value == null || !value.HasQuality || value.Quality < 5 || loot.Contains(item))
            return;
        if (loot.Count >= 48)
            loot.RemoveAt(0);
        loot.Add(item);
    }

    private static void UpdateLoot()
    {
        for (int i = loot.Count - 1; i >= 0; i--)
        {
            EntityItem item = loot[i];
            if (item == null || item.IsDead() || item.IsDespawned)
            {
                if (item != null)
                    nextGlint.Remove(item.entityId);
                loot.RemoveAt(i);
                continue;
            }
            if (!GfxJuice.On(GfxJuice.Area.Rewards) || !Near(item.position, NearGlints))
                continue;
            nextGlint.TryGetValue(item.entityId, out float next);
            if (now < next)
                continue;
            bool legendary = item.itemStack.itemValue.Quality >= 6;
            nextGlint[item.entityId] = now + Random.Range(legendary ? 0.6f : 1.2f, legendary ? 1.2f : 2.4f);
            Color glint = legendary ? new Color(5f, 2.6f, 0.8f) : new Color(3.5f, 3.2f, 2.2f);
            Add(Shape.Glint, Look.Glowing, item.position + Vector3.up * 0.15f + Random.insideUnitSphere * 0.12f, Vector3.zero, 0.45f, 0.02f, 0.11f, glint, glint * 0.2f, spin: 2f, fadeIn: 0.2f, fadeOut: 0.5f);
        }
    }

    // ---- Building blocks ----

    private static void Sparks(Vector3 at, Vector3 normal, float count, float speed)
    {
        for (int i = GfxJuice.Count(count); i > 0; i--)
        {
            Vector3 v = (normal + Random.insideUnitSphere * 0.9f).normalized * Random.Range(2f, 7f) * speed;
            Add(Shape.Spark, Look.Glowing, at + normal * 0.02f, v, Random.Range(0.25f, 0.8f), 0.008f, 0.004f, SparkHot, SparkCool,
                gravity: 9.8f, drag: 0.6f, stretch: 0.025f, hit: Hit.Bounce, fadeIn: 0f, fadeOut: 0.5f);
        }
    }

    /// <summary>Solid chips flying off a surface: n pieces of the kind, sized min to max, settling to stay life seconds.</summary>
    private static void Chips(GfxJuiceDebris.Kind kind, Vector3 at, Vector3 normal, float count, Color color, float min, float max, float smoothness, float life)
    {
        for (int i = GfxJuice.Count(count); i > 0; i--)
        {
            float s = Random.Range(min, max);
            Vector3 scale = kind == GfxJuiceDebris.Kind.Splinter ? new Vector3(s, s * 0.18f, s * 0.22f)
                : kind == GfxJuiceDebris.Kind.Shard ? new Vector3(s, s * 0.08f, s * Random.Range(0.6f, 1f))
                : new Vector3(s, s * Random.Range(0.6f, 1f), s * Random.Range(0.6f, 1f));
            Vector3 v = (normal + Random.insideUnitSphere * 0.8f).normalized * Random.Range(1.5f, 4f);
            GfxJuiceDebris.Add(kind, at + normal * (s + 0.01f), v, scale, Vary(color), smoothness, 0f, life * Random.Range(0.7f, 1.3f));
        }
    }

    /// <summary>A burst of pieces flying every way from a breaking block, mostly upwards.</summary>
    private static void Burst(GfxJuiceDebris.Kind kind, Vector3 at, float count, Color color, float min, float max, float smoothness, float life,
        float speed, float metallic = 0f, float upward = 0.6f)
    {
        for (int i = GfxJuice.Count(count); i > 0; i--)
        {
            float s = Random.Range(min, max);
            Vector3 scale = kind == GfxJuiceDebris.Kind.Splinter ? new Vector3(s, s * 0.16f, s * 0.2f)
                : kind == GfxJuiceDebris.Kind.Shard ? new Vector3(s, s * 0.08f, s * Random.Range(0.6f, 1f))
                : new Vector3(s, s * Random.Range(0.6f, 1f), s * Random.Range(0.6f, 1f));
            Vector3 v = (Random.insideUnitSphere + Vector3.up * upward) * Random.Range(0.4f, 1f) * speed;
            GfxJuiceDebris.Add(kind, at + Random.insideUnitSphere * 0.35f, v, scale, Vary(color), smoothness, metallic, life * Random.Range(0.7f, 1.3f));
        }
    }

    /// <summary>Little bits that don't stay: dirt clods, splinter flecks, lint.</summary>
    private static void Flecks(Vector3 at, Vector3 normal, float count, Color color, float min, float max)
    {
        for (int i = GfxJuice.Count(count); i > 0; i--)
            Add(Shape.Clod, Look.Lit, at + normal * 0.02f, (normal + Random.insideUnitSphere * 0.8f).normalized * Random.Range(1.5f, 4f),
                Random.Range(0.4f, 0.9f), Random.Range(min, max), min, Opaque(Vary(color)), Opaque(color), gravity: 9.8f, drag: 0.4f,
                hit: Hit.Die, spin: Random.Range(-8f, 8f), fadeIn: 0f, fadeOut: 0.8f);
    }

    /// <summary>A quick puff off an impact, gone within about half a second.</summary>
    private static void Dust(Vector3 at, Vector3 normal, float count, Color color, float size, float endSize)
    {
        if (color.a <= 0.01f || color.a >= 0.99f)
            color.a = 0.4f;
        for (int i = GfxJuice.Count(count); i > 0; i--)
            Add(Shape.Puff, Look.Lit | Look.Soft, at + normal * 0.05f, (normal + Random.insideUnitSphere * 0.6f) * Random.Range(0.6f, 1.4f),
                Random.Range(0.35f, 0.7f), size, endSize * 0.7f, color, color, gravity: 0.05f, drag: 3f, fadeIn: 0.05f, fadeOut: 0.2f);
    }

    /// <summary>A short cloud of dust off something breaking, gone within about a second.</summary>
    private static void DustCloud(Vector3 at, float count, Color color, float spread)
    {
        color.a = 0.4f;
        for (int i = GfxJuice.Count(count); i > 0; i--)
            Add(Shape.Puff, Look.Lit | Look.Soft, at + Random.insideUnitSphere * spread * 0.4f, Random.insideUnitSphere * 1.2f + Vector3.up * 0.3f,
                Random.Range(0.7f, 1.2f), 0.2f, 0.5f + spread * 0.5f, color, color, gravity: 0.08f, drag: 2f, fadeIn: 0.05f, fadeOut: 0.25f);
    }

    private static void Leaves(Vector3 at, float count, Color color, float spread)
    {
        for (int i = GfxJuice.Count(count); i > 0; i--)
            Add(Shape.Leaf, Look.Lit, at + Random.insideUnitSphere * spread * 0.4f, Random.insideUnitSphere * 1.2f + Vector3.up * 0.8f,
                Random.Range(2f, 4f), Random.Range(0.025f, 0.045f), 0.035f, Opaque(Vary(color)), Opaque(Darker(color, 0.15f)),
                gravity: 1.2f, drag: 2.5f, hit: Hit.Die, spin: Random.Range(-5f, 5f), fadeIn: 0.05f, fadeOut: 0.85f);
    }

    /// <summary>A splash: a thin crown of fine droplets thrown up and a puff of white spray.</summary>
    private static void Splash(Vector3 at, Vector3 normal, float strength)
    {
        Color water = new Color(0.85f, 0.9f, 0.95f, 0.4f);
        float lift = Mathf.Sqrt(strength);
        for (int i = GfxJuice.Count(8f * strength); i > 0; i--)
        {
            Vector3 v = (normal * 1.5f + Random.insideUnitSphere * 0.5f) * Random.Range(1.2f, 2.8f) * lift;
            Add(Shape.Drop, Look.Lit, at + Vector3.up * 0.02f + Random.insideUnitSphere * 0.03f, v, Random.Range(0.25f, 0.5f),
                Random.Range(0.002f, 0.005f), 0.003f, water, water, gravity: 9.8f, drag: 0.6f, stretch: 0.01f, hit: Hit.Die, fadeIn: 0f, fadeOut: 0.6f);
        }
        Color spray = new Color(0.9f, 0.93f, 0.96f, 0.3f);
        for (int i = GfxJuice.Count(1.5f * strength); i > 0; i--)
            Add(Shape.Puff, Look.Lit | Look.Soft, at + Vector3.up * 0.05f, normal * Random.Range(0.4f, 1f) * lift + Random.insideUnitSphere * 0.2f,
                Random.Range(0.25f, 0.45f), 0.03f, 0.14f * lift, spray, spray, gravity: 0.5f, drag: 3f, fadeIn: 0.02f, fadeOut: 0.2f);
    }

    private static void Mud(Vector3 at, Vector3 moving, float size)
    {
        Color mud = Opaque(new Color(0.14f, 0.1f, 0.07f));
        for (int i = GfxJuice.Count(3f * size); i > 0; i--)
            Add(Shape.Clod, Look.Lit, at + Vector3.up * 0.04f, -moving * 0.15f + (Random.insideUnitSphere * 0.6f + Vector3.up) * Random.Range(0.6f, 1.4f),
                Random.Range(0.3f, 0.6f), Random.Range(0.008f, 0.018f), 0.008f, mud, mud, gravity: 9.8f, drag: 0.4f, hit: Hit.Die, fadeIn: 0f, fadeOut: 0.8f);
    }

    /// <summary>A few soft golden motes drifting up round the player.</summary>
    private static void Sparkle(Vector3 at, float count, float radius)
    {
        for (int i = GfxJuice.Count(count); i > 0; i--)
        {
            Vector3 around = Quaternion.Euler(0f, Random.value * 360f, 0f) * Vector3.forward * Random.Range(0.4f, radius);
            Add(Shape.Flash, Look.Glowing, at + around + Vector3.up * Random.Range(0.3f, 1.2f), Vector3.up * Random.Range(0.3f, 0.6f), Random.Range(1.2f, 1.8f),
                0.02f, 0.012f, Gold, Gold * 0.2f, drag: 1f, fadeIn: 0.25f, fadeOut: 0.5f);
        }
    }

    /// <summary>Dust sifting down from the ceiling over the player when they're indoors and something heavy hits nearby.</summary>
    private static void CeilingDust(Vector3 near, float amount)
    {
        EntityPlayerLocal player = GameManager.Instance?.World?.GetPrimaryPlayer();
        if (player == null || GfxMood.Outdoors > 0.5f || (player.position - near).sqrMagnitude > 20f * 20f)
            return;
        Vector3 head = player.position + Vector3.up * 1.6f;
        for (int i = GfxJuice.Count(4f * amount); i > 0; i--)
        {
            Vector3 from = head + new Vector3(Random.Range(-3f, 3f), 0f, Random.Range(-3f, 3f)) - Origin.position;
            if (!Physics.Raycast(from, Vector3.up, out RaycastHit hit, 4f, GfxJuice.WorldMask, QueryTriggerInteraction.Ignore))
                continue;
            Vector3 at = hit.point + Origin.position - Vector3.up * 0.05f;
            Color dust = new Color(0.6f, 0.56f, 0.5f, 0.35f);
            Add(Shape.Puff, Look.Lit | Look.Soft, at, Vector3.down * 0.3f, Random.Range(2.5f, 4f), 0.05f, 0.35f, dust, new Color(dust.r, dust.g, dust.b, 0.15f),
                gravity: 0.25f, drag: 1.2f, fadeIn: 0.15f, fadeOut: 0.5f);
            for (int k = GfxJuice.Count(2f); k > 0; k--)
                Add(Shape.Clod, Look.Lit, at + Random.insideUnitSphere * 0.1f, Vector3.zero, Random.Range(0.8f, 1.5f), Random.Range(0.004f, 0.009f), 0.004f,
                    Opaque(dust), Opaque(dust), gravity: 9.8f, drag: 0.5f, hit: Hit.Die, fadeIn: 0f, fadeOut: 0.9f);
        }
    }

    private static void PitAt(Vector3 at, Vector3 normal, float radius)
    {
        // The face normal is square to the block; find the real surface under the point
        Vector3 from = at - Origin.position + normal * 0.15f;
        if (Physics.Raycast(from, -normal, out RaycastHit hit, 0.35f, GfxJuice.WorldMask, QueryTriggerInteraction.Ignore))
            GfxJuiceDecals.Pit(hit.point + Origin.position, hit.normal, radius);
        else
            GfxJuiceDecals.Pit(at, normal, radius);
    }

    // ---- Surfaces and colors ----

    /// <summary>A material's surface category (as the game names them in its particles) as a Surface.</summary>
    public static Surface ParseCategory(string category)
    {
        switch (category)
        {
            case "metal": return Surface.Metal;
            case "stone": case "boulder": return Surface.Stone;
            case "wood": return Surface.Wood;
            case "earth": return Surface.Earth;
            case "snow": return Surface.Snow;
            case "plant": return Surface.Plant;
            case "xt_tallgrass": return Surface.Grass;
            case "xt_leaves1": case "xt_leaves2": case "xt_leaves3": return Surface.Leaves;
            case "cloth": return Surface.Cloth;
            case "glass": return Surface.Glass;
            case "organic": return Surface.Organic;
            case "water": return Surface.Water;
        }
        return Surface.None;
    }

    /// <summary>The surface a step sound names: the sound is the walker's step type followed by the material's step sound.</summary>
    private static Surface StepSurface(string sound)
    {
        if (sound.EndsWith("dirt")) return Surface.Earth;
        if (sound.EndsWith("sand")) return Surface.Sand;
        if (sound.EndsWith("gravel")) return Surface.Gravel;
        if (sound.EndsWith("snow")) return Surface.Snow;
        if (sound.EndsWith("water")) return Surface.Water;
        if (sound.EndsWith("leaves") || sound.EndsWith("bush") || sound.EndsWith("fern")) return Surface.Leaves;
        if (sound.EndsWith("grass")) return Surface.Grass;
        if (sound.EndsWith("stone")) return Surface.Stone;
        if (sound.EndsWith("metal")) return Surface.Metal;
        if (sound.EndsWith("wood")) return Surface.Wood;
        return Surface.None;
    }

    /// <summary>What the ground at a world point is: the block just under it, by its material's step sound or surface.</summary>
    private static Surface GroundSurface(Vector3 at, out Color color)
    {
        color = Color.clear;
        World world = GameManager.Instance?.World;
        if (world == null)
            return Surface.None;
        BlockValue value = world.GetBlock(World.worldToBlockPos(at - Vector3.up * 0.1f));
        if (value.isair)
            value = world.GetBlock(World.worldToBlockPos(at - Vector3.up * 0.6f));
        Block block = value.Block;
        MaterialBlock material = block?.blockMaterial;
        if (value.isair || material == null)
            return Surface.None;
        try
        {
            color = block.GetColorForSide(value, BlockFace.Top);
        }
        catch (Exception)
        {
        }
        Surface byStep = material.stepSound != null ? StepSurface(material.stepSound.name ?? "") : Surface.None;
        return byStep != Surface.None ? byStep : ParseCategory(material.SurfaceCategory);
    }

    /// <summary>Whether the block behind a hit is an ore (by name), for the extra sparks off a pick.</summary>
    private static bool IsOre(Vector3 at, Vector3 normal)
    {
        World world = GameManager.Instance?.World;
        if (world == null)
            return false;
        BlockValue value = world.GetBlock(World.worldToBlockPos(at - normal * 0.1f));
        string name = value.isair ? null : value.Block?.GetBlockName();
        return name != null && name.IndexOf("ore", StringComparison.OrdinalIgnoreCase) >= 0 && name.IndexOf("Store", StringComparison.Ordinal) < 0;
    }

    private static Color LeafColor(EntityAlive walker)
    {
        string biome = walker.biomeStandingOn?.m_sBiomeName ?? "";
        if (biome.IndexOf("burnt", StringComparison.OrdinalIgnoreCase) >= 0)
            return new Color(0.12f, 0.1f, 0.08f);
        if (biome.IndexOf("snow", StringComparison.OrdinalIgnoreCase) >= 0)
            return new Color(0.16f, 0.24f, 0.12f);
        if (biome.IndexOf("desert", StringComparison.OrdinalIgnoreCase) >= 0 || biome.IndexOf("waste", StringComparison.OrdinalIgnoreCase) >= 0)
            return new Color(0.34f, 0.3f, 0.16f);
        return new Color(0.22f, 0.32f, 0.11f);
    }

    /// <summary>A block's own color is gray when the game has none for it; then the surface's usual color looks better.</summary>
    private static bool Usable(Color c)
    {
        float spread = Mathf.Max(c.r, Mathf.Max(c.g, c.b)) - Mathf.Min(c.r, Mathf.Min(c.g, c.b));
        return c.a > 0.01f && (spread > 0.03f || Mathf.Abs(c.r - 0.5f) > 0.08f);
    }

    private static Color Default(Surface surface)
    {
        switch (surface)
        {
            case Surface.Metal: return new Color(0.4f, 0.38f, 0.36f);
            case Surface.Stone: return new Color(0.5f, 0.49f, 0.46f);
            case Surface.Gravel: return new Color(0.52f, 0.5f, 0.47f);
            case Surface.Wood: return new Color(0.46f, 0.32f, 0.19f);
            case Surface.Earth: return new Color(0.36f, 0.28f, 0.2f);
            case Surface.Sand: return new Color(0.72f, 0.62f, 0.45f);
            case Surface.Snow: return new Color(0.92f, 0.95f, 1f);
            case Surface.Plant:
            case Surface.Grass:
            case Surface.Leaves: return new Color(0.24f, 0.33f, 0.12f);
            case Surface.Cloth: return new Color(0.45f, 0.42f, 0.38f);
            case Surface.Glass: return new Color(0.62f, 0.72f, 0.75f);
            case Surface.Water: return new Color(0.72f, 0.8f, 0.85f);
        }
        return new Color(0.45f, 0.43f, 0.4f);
    }

    private static Color Vary(Color c)
    {
        float k = Random.Range(0.8f, 1.15f);
        return new Color(c.r * k, c.g * k, c.b * k, c.a);
    }

    private static Color Lighter(Color c, float amount)
    {
        return new Color(Mathf.Lerp(c.r, 1f, amount), Mathf.Lerp(c.g, 1f, amount), Mathf.Lerp(c.b, 1f, amount), c.a);
    }

    private static Color Darker(Color c, float amount)
    {
        return new Color(c.r * (1f - amount), c.g * (1f - amount), c.b * (1f - amount), c.a);
    }

    private static Color Opaque(Color c)
    {
        return new Color(c.r, c.g, c.b, 1f);
    }

    public static string Status()
    {
        return string.Format("{0} events seen; {1} hot barrels, {2} glinting items.", events, barrels.Count, loot.Count);
    }
}
