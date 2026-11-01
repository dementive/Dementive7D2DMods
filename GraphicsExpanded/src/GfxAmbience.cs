using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Ambient life (Ambience.shader): small, slow movement in the air around the player, for a calmer, living world.
/// - Motes by day, the kind by the biome the player stands in: pollen in the forest, dust in the desert and wasteland,
///   ash flakes in the burnt forest (by night too), ice crystals in the snow on clear days. They glint where the sun's
///   light scatters forward to the eye, so mostly looking into the sun and in its beams.
/// - The odd leaf tumbling down from the broadleaf trees nearest the player (oaks and plains trees, from DecoManager).
/// None of them come in rain or snowfall, or indoors; they ease in and out over a few seconds as things change. One
/// DrawMeshInstancedIndirect of a few hundred quads, whose shader works out every particle from the time alone. Every
/// player's game draws its own around them from what it already has, so in multiplayer nothing is sent.
/// </summary>
public static class GfxAmbience
{
    private const int Motes = 400, Leaves = 12;     // at 100%; up to twice as many at 200%
    private const float MoteBox = 30f, MoteHeight = 12f;
    private const float LeafReach = 40f;
    private const int MaxTrees = 16;
    private const float EaseSeconds = 3f;

    // The shader's mote kinds
    private const int Pollen = 0, Dust = 1, Ash = 2, Ice = 3;

    private static Shader shader;
    private static Material material;
    private static Mesh quad;
    private static ComputeBuffer args;
    private static int drawn = -1;

    private static float motes, leaves;             // how much each shows now, eased
    private static int moteKind = Pollen;
    private static readonly Vector4[] trees = new Vector4[MaxTrees];
    private static int treeCount;
    private static float nextTrees;
    private static readonly List<KeyValuePair<float, Vector4>> nearTrees = new List<KeyValuePair<float, Vector4>>();
    private static readonly Dictionary<Block, Vector2> crowns = new Dictionary<Block, Vector2>();   // per broadleaf tree: crown height, radius; (0, 0) for others
    private static string biomeName = "";
    private static string state = "not started";

    /// <summary>gfxe ambience debug: everything shown in magenta, whatever the time and weather.</summary>
    public static bool Debug;

    public static bool Loaded => shader != null;

    public static void Init(AssetBundle bundle)
    {
        shader = bundle != null ? bundle.LoadAsset<Shader>("Ambience") : null;
        if (shader != null && !shader.isSupported || !SystemInfo.supportsComputeShaders)
        {
            Log.Warning("[GraphicsExpanded] The ambient life shader isn't supported on this graphics card; ambient life is off");
            shader = null;
        }
        if (!Loaded)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        quad = new Mesh { name = "GraphicsExpanded ambience quad", hideFlags = HideFlags.HideAndDontSave };
        quad.vertices = new[] { new Vector3(-0.5f, -0.5f, 0f), new Vector3(0.5f, -0.5f, 0f), new Vector3(0.5f, 0.5f, 0f), new Vector3(-0.5f, 0.5f, 0f) };
        quad.uv = new[] { new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f) };
        quad.triangles = new[] { 0, 2, 1, 0, 3, 2 };
        quad.bounds = new Bounds(Vector3.zero, Vector3.one * 100000f);
        args = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        World world = GameManager.Instance != null ? GameManager.Instance.World : null;
        float setting = GfxSettings.LookActive ? Mathf.Clamp(GfxSettings.AmbientLife, 0f, 2f) : 0f;
        if (setting <= 0f || player == null || playerCamera == null || world == null)
        {
            motes = leaves = 0f;
            treeCount = 0;
            state = setting <= 0f ? "off" : "no world";
            return;
        }
        float ease = 1f - Mathf.Exp(-Time.deltaTime / EaseSeconds);

        // What's around: the biome underfoot, the weather, the sun
        biomeName = player.biomeStandingOn?.m_sBiomeName ?? "";
        float calm = 1f - Smooth(0.03f, 0.25f, Mathf.Max(GfxMood.RainAmount, GfxMood.SnowAmount));
        float outdoors = GfxMood.Outdoors;
        Light sun = SkyManager.sunLight;
        Vector3 toSun = sun != null ? -sun.transform.forward : Vector3.up;
        float sunUp = sun != null && sun.isActiveAndEnabled ? Smooth(-0.02f, 0.12f, toSun.y) : 0f;

        // Motes by day, the biome's kind (ash in the burnt forest by night too); a new kind waits until the old has gone
        int kind = Contains(biomeName, "burnt") ? Ash : Contains(biomeName, "desert") || Contains(biomeName, "waste") ? Dust
            : Contains(biomeName, "snow") ? Ice : Pollen;
        float moteTarget = Debug ? 1f : calm * outdoors * (kind == Ash ? 1f : sunUp) * (kind == Dust ? 0.7f : 1f);
        if (kind != moteKind)
        {
            moteTarget = 0f;
            if (motes < 0.02f)
                moteKind = kind;
        }
        motes = Ease(motes, moteTarget, ease);

        // Leaves under the broadleaf trees nearby
        UpdateTrees(world, player);
        float wet = Mathf.Max(GfxMood.RainAmount, GfxMood.SnowAmount);
        leaves = Ease(leaves, treeCount == 0 ? 0f : Debug ? 1f : 1f - 0.7f * wet, ease);

        if (motes + leaves < 0.002f)
        {
            state = "nothing in the air here now";
            return;
        }

        int moteCount = Mathf.RoundToInt(Motes * setting), leafCount = Mathf.RoundToInt(Leaves * setting);
        int count = moteCount + leafCount;
        if (count != drawn)
        {
            args.SetData(new uint[] { quad.GetIndexCount(0), (uint)count, 0, 0, 0 });
            drawn = count;
        }
        Color sunLight = sun != null ? sun.color.linear * sun.intensity : Color.black;
        material.SetVector("_GfxOrigin", Origin.position);
        material.SetVector("_GfxAmbCounts", new Vector4(moteCount, leafCount, 0f, treeCount));
        material.SetVector("_GfxAmbMotes", new Vector4(motes, moteKind, MoteBox, MoteHeight));
        material.SetVector("_GfxAmbLeaves", new Vector4(leaves, 0f, 0f, 0f));
        material.SetVectorArray("_GfxAmbTrees", trees);
        material.SetVector("_GfxAmbSun", new Vector4(toSun.x, toSun.y, toSun.z, sunUp));
        material.SetVector("_GfxAmbSunColor", new Vector4(sunLight.r, sunLight.g, sunLight.b, 0f));
        material.SetVector("_GfxAmbGround", new Vector4(player.transform.position.y, 0f, Debug ? 1f : 0f, 0f));
        material.SetVector("_GfxAmbWind", Wind());
        Graphics.DrawMeshInstancedIndirect(quad, 0, material, new Bounds(playerCamera.transform.position, Vector3.one * 1000f), args, 0, null,
            ShadowCastingMode.Off, false, 0, playerCamera, LightProbeUsage.Off);
        state = string.Format("{0} {1:0%}, leaves {2:0%} from {3} broadleaf trees", MoteName(moteKind), motes, leaves, treeCount);
    }

    /// <summary>
    /// What carries things along: the game's wind direction (its WindZone's, world x and z) and how windy its weather
    /// is, 0 to 1 (the weather's Wind is 0 to 100: about 3 to 25 most days, 30 to 50 in storms).
    /// </summary>
    private static Vector4 Wind()
    {
        WeatherManager weather = WeatherManager.Instance;
        Vector2 direction = new Vector2(1f, 0f);
        if (weather != null && weather.windZone != null)
        {
            Vector3 forward = weather.windZone.transform.forward;
            Vector2 flat = new Vector2(forward.x, forward.z);
            if (flat.sqrMagnitude > 1e-4f)
                direction = flat.normalized;
        }
        float windy = weather != null ? Mathf.Clamp01(0.3f + WeatherManager.GetWindSpeed() / 40f) : 0.3f;
        return new Vector4(direction.x, direction.y, windy, 0f);
    }

    /// <summary>The broadleaf trees nearest the player, every two seconds, from the game's decorations.</summary>
    private static void UpdateTrees(World world, EntityPlayerLocal player)
    {
        if (Time.unscaledTime < nextTrees)
            return;
        nextTrees = Time.unscaledTime + 2f;
        treeCount = 0;
        DecoManager decos = DecoManager.Instance;
        if (decos?.decoChunks == null)
            return;
        Vector3 here = player.GetPosition();
        Vector3 middle = DecoManager.cDecoMiddleOffset;
        Vector3 origin = Origin.position;
        nearTrees.Clear();
        for (int cx = DecoChunk.ToDecoChunkPos(here.x - LeafReach); cx <= DecoChunk.ToDecoChunkPos(here.x + LeafReach); cx++)
        {
            for (int cz = DecoChunk.ToDecoChunkPos(here.z - LeafReach); cz <= DecoChunk.ToDecoChunkPos(here.z + LeafReach); cz++)
            {
                if (!decos.decoChunks.TryGetValue(DecoChunk.MakeKey16(cx, cz), out DecoChunk chunk) || chunk?.decosPerSmallChunks == null)
                    continue;
                foreach (List<DecoObject> list in chunk.decosPerSmallChunks.Values)
                {
                    foreach (DecoObject deco in list)
                    {
                        if (deco == null || deco.state == DecoState.GeneratedInactive)
                            continue;
                        float x = deco.pos.x + middle.x, z = deco.pos.z + middle.z;
                        float apart = (x - here.x) * (x - here.x) + (z - here.z) * (z - here.z);
                        if (apart > LeafReach * LeafReach)
                            continue;
                        Vector2 crown = Crown(deco.bv.Block);
                        if (crown.y <= 0f)
                            continue;
                        nearTrees.Add(new KeyValuePair<float, Vector4>(apart, new Vector4(x - origin.x, deco.realYPos + crown.x - origin.y, z - origin.z, crown.y)));
                    }
                }
            }
        }
        nearTrees.Sort((a, b) => a.Key.CompareTo(b.Key));
        for (int i = 0; i < nearTrees.Count && treeCount < MaxTrees; i++)
            trees[treeCount++] = nearTrees[i].Value;
    }

    /// <summary>A broadleaf tree's crown, by its block's name: height of its middle over the base and its radius; zero for anything else.</summary>
    private static Vector2 Crown(Block block)
    {
        if (block == null)
            return Vector2.zero;
        if (crowns.TryGetValue(block, out Vector2 known))
            return known;
        Vector2 crown = Vector2.zero;
        string name = block is BlockModelTree ? block.GetBlockName() : "";
        if ((name.Contains("Oak") || name.Contains("PlainsTree")) && !name.Contains("Burnt") && !name.Contains("Dead"))
        {
            crown = name.Contains("Lrg") ? new Vector2(8.5f, 4f) : name.Contains("Med") ? new Vector2(6f, 3f)
                : name.Contains("Sml") || name.Contains("Planted") ? new Vector2(3.5f, 2f) : new Vector2(6f, 3.5f);
        }
        crowns[block] = crown;
        return crown;
    }

    private static string MoteName(int kind)
    {
        return kind == Dust ? "dust" : kind == Ash ? "ash" : kind == Ice ? "ice crystals" : "pollen";
    }

    private static bool Contains(string text, string part)
    {
        return text.IndexOf(part, System.StringComparison.OrdinalIgnoreCase) >= 0;
    }

    /// <summary>0 below from, 1 above to, smooth between.</summary>
    private static float Smooth(float from, float to, float value)
    {
        float t = Mathf.Clamp01((value - from) / (to - from));
        return t * t * (3f - 2f * t);
    }

    private static float Ease(float current, float target, float amount)
    {
        return current + (target - current) * amount;
    }

    public static string Status()
    {
        if (!Loaded)
            return "Ambient life is off: the shader didn't load (see the log).";
        return string.Format("Ambient life: {0}; biome '{1}'.", state, biomeName);
    }
}
