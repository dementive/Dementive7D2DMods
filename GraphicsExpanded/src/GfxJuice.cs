using System.Text;
using UnityEngine;

/// <summary>
/// Game juice: particles, debris, marks and screen effects that make fights, gunfire, breaking things, moving about
/// and rewards feel punchier. The Feel tab has one Juice amount (0 to 200%) and a switch for each area.
///
/// The game's own events drive it (GfxJuicePatches), on every player's machine from what the game already sends
/// there: impacts, block breaks and explosions reach every client, gunfire every client near the shooter, damage
/// every client tracking the creature. So in multiplayer everyone sees everyone's juice and nothing extra is sent.
/// The pieces:
/// - GfxJuiceParticles: sparks, dust, smoke, blood drops, tracers, leaves, glints, rings, heat shimmer;
/// - GfxJuiceDebris: casings, splinters, chunks and shards that bounce and settle;
/// - GfxJuiceDecals: blood, scorch marks and bullet pits painted onto surfaces;
/// - GfxJuiceFlash: creatures lighting up when hit;
/// - GfxJuiceScreen: the low-health heartbeat and the reward bursts;
/// - GfxJuiceEffects: the recipes that put those together for each event.
/// </summary>
public static class GfxJuice
{
    public enum Area { Hits, Shooting, Breaking, Moving, Hurt, Rewards }

    private static Mesh quad;
    private static bool active;
    private static int worldMask;
    private static string state = "not started";

    /// <summary>gfxe juice debug: logs every event the hooks see.</summary>
    public static bool Debug;

    public static bool Loaded => GfxJuiceParticles.Loaded;

    /// <summary>The world as seen by the bits' rays: everything solid, not creatures, players, water or triggers.</summary>
    public static int WorldMask
    {
        get
        {
            if (worldMask == 0)
                worldMask = BuildWorldMask();
            return worldMask;
        }
    }

    /// <summary>The wind the bits drift on, m/s in world space, set every frame.</summary>
    public static Vector3 Wind { get; private set; }

    /// <summary>Whether that area is on now: juice on, the look on (the compare key turns it off) and in a world.</summary>
    public static bool On(Area area)
    {
        if (!active)
            return false;
        switch (area)
        {
            case Area.Hits: return GfxSettings.JuiceHits;
            case Area.Shooting: return GfxSettings.JuiceShooting;
            case Area.Breaking: return GfxSettings.JuiceBreaking;
            case Area.Moving: return GfxSettings.JuiceMoving;
            case Area.Hurt: return GfxSettings.JuiceHurt;
            case Area.Rewards: return GfxSettings.JuiceRewards;
        }
        return false;
    }

    /// <summary>The Juice amount, 0 to 2.</summary>
    public static float Amount => Mathf.Clamp(GfxSettings.Juice, 0f, 2f);

    /// <summary>How many bits for n at 100%, scaled by the Juice amount, the fraction rounded at random.</summary>
    public static int Count(float n)
    {
        float scaled = n * Amount;
        int whole = (int)scaled;
        return whole + (Random.value < scaled - whole ? 1 : 0);
    }

    public static void Init(AssetBundle bundle)
    {
        Shader particles = Load(bundle, "Juice"), warp = Load(bundle, "JuiceWarp"), debris = Load(bundle, "JuiceDebris");
        Shader decals = Load(bundle, "JuiceDecal"), flash = Load(bundle, "JuiceFlash"), screen = Load(bundle, "JuiceScreen");
        if (particles == null || !SystemInfo.supportsComputeShaders)
        {
            Log.Warning("[GraphicsExpanded] The game juice shaders didn't load or aren't supported on this graphics card; game juice is off");
            return;
        }
        quad = new Mesh { name = "GraphicsExpanded juice quad", hideFlags = HideFlags.HideAndDontSave };
        quad.vertices = new[] { new Vector3(-0.5f, -0.5f, 0f), new Vector3(0.5f, -0.5f, 0f), new Vector3(0.5f, 0.5f, 0f), new Vector3(-0.5f, 0.5f, 0f) };
        quad.uv = new[] { new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f) };
        quad.triangles = new[] { 0, 2, 1, 0, 3, 2 };
        quad.bounds = new Bounds(Vector3.zero, Vector3.one * 100000f);
        GfxJuiceParticles.Init(particles, warp, quad);
        GfxJuiceDebris.Init(debris);
        GfxJuiceDecals.Init(decals);
        GfxJuiceFlash.Init(flash);
        GfxJuiceScreen.Init(screen);
    }

    private static Shader Load(AssetBundle bundle, string name)
    {
        Shader shader = bundle != null ? bundle.LoadAsset<Shader>(name) : null;
        if (shader != null && !shader.isSupported)
        {
            Log.Warning("[GraphicsExpanded] The " + name + " shader isn't supported on this graphics card");
            return null;
        }
        return shader;
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        bool was = active;
        active = GfxSettings.LookActive && Amount > 0f && player != null && playerCamera != null
            && GameManager.Instance != null && GameManager.Instance.World != null;
        if (!active)
        {
            if (was)
                ClearAll();
            GfxJuiceScreen.Update(player, Time.deltaTime, false, false);
            state = Amount <= 0f ? "off" : !GfxSettings.LookActive ? "off while comparing or disabled" : "no world";
            return;
        }

        float dt = Time.deltaTime;
        Wind = WindNow();
        GfxJuiceEffects.Update(player, playerCamera, dt);
        GfxJuiceParticles.Update(playerCamera, dt, Wind, Sunlight());
        GfxJuiceDebris.Update(playerCamera, dt);
        GfxJuiceDecals.Update(playerCamera, dt, On(Area.Hits) || On(Area.Breaking));
        GfxJuiceFlash.Update(playerCamera);
        GfxJuiceScreen.Update(player, dt, On(Area.Hurt), On(Area.Rewards));
        state = "on";
    }

    private static void ClearAll()
    {
        GfxJuiceParticles.Clear();
        GfxJuiceDebris.Clear();
        GfxJuiceDecals.Clear();
        GfxJuiceDecals.Update(null, 0f, false);
        GfxJuiceFlash.Clear();
        GfxJuiceFlash.Detach();
        GfxJuiceScreen.Clear();
        GfxJuiceEffects.Clear();
    }

    /// <summary>
    /// The sunlight reaching lit bits, scaled down indoors and when the sun is low (then most bits are in the shade of
    /// hills and trees; they don't sample the shadows, so they'd glow in a shaded valley at dusk).
    /// </summary>
    private static Color Sunlight()
    {
        Light sun = SkyManager.sunLight;
        if (sun == null || !sun.isActiveAndEnabled)
            return Color.black;
        float up = Mathf.Clamp01((-sun.transform.forward.y - 0.03f) / 0.35f);
        Color light = sun.color.linear * sun.intensity * up * up * Mathf.Lerp(0.06f, 0.3f, GfxMood.Outdoors);
        light.a = 0f;
        return light;
    }

    /// <summary>The game's wind as a velocity: its WindZone's direction, about 0.5 m/s on a still day to 10 in a storm.</summary>
    private static Vector3 WindNow()
    {
        WeatherManager weather = WeatherManager.Instance;
        Vector3 direction = Vector3.right;
        if (weather != null && weather.windZone != null)
        {
            Vector3 forward = weather.windZone.transform.forward;
            forward.y = 0f;
            if (forward.sqrMagnitude > 1e-4f)
                direction = forward.normalized;
        }
        float speed = weather != null ? 0.5f + Mathf.Clamp(WeatherManager.GetWindSpeed(), 0f, 100f) / 10f : 1f;
        return direction * speed;
    }

    /// <summary>Every layer but creatures, players, water, triggers, held items and the like.</summary>
    private static int BuildWorldMask()
    {
        string[] skip = { "player", "physics", "water", "ui", "ignore", "trigger", "holding", "item", "entity", "ragdoll", "dead", "transparentfx", "blocker", "postprocess" };
        int mask = 0;
        for (int layer = 0; layer < 32; layer++)
        {
            string name = LayerMask.LayerToName(layer);
            if (string.IsNullOrEmpty(name))
                continue;
            string lower = name.ToLowerInvariant();
            bool solid = true;
            foreach (string s in skip)
            {
                if (lower.Contains(s))
                {
                    solid = false;
                    break;
                }
            }
            if (solid)
                mask |= 1 << layer;
        }
        return mask;
    }

    /// <summary>The layers by name, marking the ones the bits collide with.</summary>
    public static string Layers()
    {
        StringBuilder text = new StringBuilder();
        int mask = WorldMask;
        for (int layer = 0; layer < 32; layer++)
        {
            string name = LayerMask.LayerToName(layer);
            if (string.IsNullOrEmpty(name))
                continue;
            text.Append(layer).Append((mask & (1 << layer)) != 0 ? "* " : " ").Append(name).Append(", ");
        }
        return text.ToString();
    }

    public static string Status()
    {
        if (!Loaded)
            return "Game juice is off: its shaders didn't load (see the log).";
        return string.Format("Game juice {0} at {1:0%}: {2} bits, {3} warps, {4} pieces, {5} marks, {6} flashing; {7}. {8}",
            state, Amount, GfxJuiceParticles.Count, GfxJuiceParticles.WarpCount, GfxJuiceDebris.Count, GfxJuiceDecals.Count,
            GfxJuiceFlash.Count, GfxJuiceScreen.Status(), GfxJuiceEffects.Status());
    }
}
