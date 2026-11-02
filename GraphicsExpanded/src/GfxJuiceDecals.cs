using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Game juice's marks on surfaces (JuiceDecal.shader): blood splattered on walls and floors, pools spreading under the
/// dead, scorch marks from explosions and the pits bullets leave in stone and metal. A command buffer on the player
/// camera paints them into the G-buffer before lighting, so they're lit like the surface they're on.
///
/// Blood goes from wet and glossy to dark and dull over a minute and a half, and fades after a few minutes; out under
/// the open sky in rain (the weather's sky map says where), it washes away within a minute. Scorch marks last longer
/// and only fade a little faster in rain. Positions are in world coordinates, so the floating origin doesn't move them.
/// </summary>
public static class GfxJuiceDecals
{
    public enum Kind { Splat, Pool, Scorch, Pit }

    private const int Max = 384;
    private const float BloodSeconds = 240f, BloodDrySeconds = 90f, ScorchSeconds = 420f, PitSeconds = 120f;
    private const float FadeSeconds = 30f;
    private const float RainWash = 7f;      // how much faster blood ages out in the rain under open sky

    private static readonly Color WetBlood = new Color(0.17f, 0.004f, 0.004f);
    private static readonly Color DryBlood = new Color(0.075f, 0.018f, 0.012f);
    // Pooled blood is thick, so much darker: deep maroon wet, near black-brown dry
    private static readonly Color WetPool = new Color(0.07f, 0.006f, 0.005f);
    private static readonly Color DryPool = new Color(0.038f, 0.013f, 0.01f);
    private static readonly Color ScorchColor = new Color(0.018f, 0.016f, 0.014f);
    private static readonly Color PitColor = new Color(0.04f, 0.038f, 0.035f);

    private struct Mark
    {
        public Vector3 position, normal;    // world coordinates
        public float radius, turn, seed;
        public float age, life, grow;       // seconds; grow: how long it takes to spread to full size
        public Kind kind;
    }

    private struct GpuMark
    {
        public Vector4 place, normal, look, color;
    }

    private static Material material;
    private static Mesh box;
    private static ComputeBuffer gpu, args;
    private static readonly Mark[] marks = new Mark[Max];
    private static readonly GpuMark[] upload = new GpuMark[Max];
    private static readonly uint[] argsData = new uint[5];
    private static int count, drawn = -1;

    private static Camera camera;
    private static CommandBuffer commands;
    private static bool attached;

    public static bool Loaded => material != null;
    public static int Count => count;

    public static void Init(Shader shader)
    {
        if (shader == null)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        gpu = new ComputeBuffer(Max, 64);
        args = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
        material.SetBuffer("_GfxDecals", gpu);
        Vector3[] corners =
        {
            new Vector3(-0.5f, -0.5f, -0.5f), new Vector3(0.5f, -0.5f, -0.5f), new Vector3(0.5f, 0.5f, -0.5f), new Vector3(-0.5f, 0.5f, -0.5f),
            new Vector3(-0.5f, -0.5f, 0.5f), new Vector3(0.5f, -0.5f, 0.5f), new Vector3(0.5f, 0.5f, 0.5f), new Vector3(-0.5f, 0.5f, 0.5f),
        };
        int[] tris =
        {
            0, 2, 1, 0, 3, 2,   4, 5, 6, 4, 6, 7,   0, 1, 5, 0, 5, 4,
            3, 6, 2, 3, 7, 6,   0, 4, 7, 0, 7, 3,   1, 2, 6, 1, 6, 5,
        };
        box = GfxJuiceDebris.Flat("GraphicsExpanded decal box", corners, tris);
    }

    // ---- Adding marks ----

    /// <summary>Blood flung onto a surface: a blot where it hit and drops flying on along the way it was going.</summary>
    public static void Splat(Vector3 position, Vector3 normal, Vector3 flying, float radius)
    {
        Vector3 along = Vector3.ProjectOnPlane(flying, normal);
        Add(Kind.Splat, position, normal, radius, BloodSeconds, 0.15f, along.sqrMagnitude > 1e-4f ? along : (Vector3?)null);
    }

    /// <summary>A pool of blood spreading under a body over several seconds.</summary>
    public static void Pool(Vector3 position, Vector3 normal, float radius)
    {
        Add(Kind.Pool, position, normal, radius, BloodSeconds * 1.25f, 8f, null);
    }

    /// <summary>A falling drop of blood landing: now and then a small splat, unless it lands in fresh blood.</summary>
    public static void BloodDrop(Vector3 position, Vector3 normal, float dropSize)
    {
        if (Random.value > 0.3f + dropSize * 30f)
            return;
        float radius = Mathf.Clamp(dropSize * 8f, 0.05f, 0.14f);
        if (NearFresh(position, 0.2f))
            return;
        Add(Kind.Splat, position, normal, radius, BloodSeconds, 0.05f, null);
    }

    public static void Scorch(Vector3 position, Vector3 normal, float radius)
    {
        Add(Kind.Scorch, position, normal, radius, ScorchSeconds, 0.1f, null);
    }

    /// <summary>The small dark pit a bullet leaves in stone, concrete or metal.</summary>
    public static void Pit(Vector3 position, Vector3 normal, float radius)
    {
        if (NearFresh(position, radius * 0.5f))
            return;
        Add(Kind.Pit, position, normal, radius, PitSeconds, 0f, null);
    }

    private static void Add(Kind kind, Vector3 position, Vector3 normal, float radius, float life, float grow, Vector3? along)
    {
        if (!Loaded || normal.sqrMagnitude < 1e-6f)
            return;
        normal.Normalize();
        float turn = Random.value * Mathf.PI * 2f;
        if (along.HasValue)
        {
            // The shader flies the drops along its turned +x: find the turn that points it along the spray
            Vector3 a = Vector3.Cross(normal, Mathf.Abs(normal.y) < 0.9f ? Vector3.up : Vector3.right).normalized;
            Vector3 b = Vector3.Cross(normal, a);
            Vector3 dir = along.Value.normalized;
            turn = Mathf.Atan2(Vector3.Dot(dir, b), Vector3.Dot(dir, a));
        }
        int slot = count < Max ? count++ : Oldest();
        marks[slot] = new Mark
        {
            position = position,
            normal = normal,
            radius = radius,
            turn = turn,
            seed = Random.value,
            life = life,
            grow = grow,
            kind = kind,
        };
    }

    private static bool NearFresh(Vector3 position, float within)
    {
        for (int i = 0; i < count; i++)
        {
            if (marks[i].age < 20f && (marks[i].position - position).sqrMagnitude < within * within)
                return true;
        }
        return false;
    }

    private static int Oldest()
    {
        int oldest = 0;
        float most = -1f;
        for (int i = 0; i < count; i++)
        {
            float gone = marks[i].age / marks[i].life;
            if (gone > most)
            {
                most = gone;
                oldest = i;
            }
        }
        return oldest;
    }

    public static void Clear()
    {
        count = 0;
    }

    // ---- Every frame ----

    /// <summary>Called every frame from GfxJuice.Update: ages the marks and hands the live ones to the shader.</summary>
    public static void Update(Camera playerCamera, float deltaTime, bool show)
    {
        if (!Loaded)
            return;
        if (!show || playerCamera == null)
        {
            Detach();
            if (!show)
                count = 0;
            return;
        }

        float rain = GfxMood.RainAmount;
        Vector3 origin = Origin.position;
        for (int i = 0; i < count; i++)
        {
            ref Mark m = ref marks[i];
            float aging = 1f;
            if (rain > 0.05f && m.kind != Kind.Pit && GfxWeather.OpenToSky(m.position + m.normal * 0.2f))
                aging = 1f + rain * (m.kind == Kind.Scorch ? 1f : RainWash);
            m.age += deltaTime * aging;
            if (m.age >= m.life)
                marks[i--] = marks[--count];
        }
        if (count == 0)
        {
            Detach();
            return;
        }

        for (int i = 0; i < count; i++)
        {
            ref Mark m = ref marks[i];
            float opacity = Mathf.Clamp01((m.life - m.age) / FadeSeconds);
            float growth = m.grow > 0f ? Mathf.Clamp01(m.age / m.grow) : 1f;
            growth = 1f - (1f - growth) * (1f - growth);
            Color color;
            float smoothness;
            switch (m.kind)
            {
                case Kind.Scorch:
                    color = ScorchColor;
                    smoothness = 0.05f;
                    opacity *= 0.92f;
                    break;
                case Kind.Pit:
                    color = PitColor;
                    smoothness = 0.1f;
                    opacity *= 0.85f;
                    break;
                case Kind.Pool:
                    float dried = Mathf.Clamp01(m.age / BloodDrySeconds);
                    color = Color.Lerp(WetPool, DryPool, dried);
                    smoothness = Mathf.Lerp(0.6f, 0.25f, dried);
                    opacity *= 0.9f;
                    break;
                default:
                    float dry = Mathf.Clamp01(m.age / BloodDrySeconds);
                    color = Color.Lerp(WetBlood, DryBlood, dry);
                    smoothness = Mathf.Lerp(0.85f, 0.3f, dry);
                    opacity *= 0.9f;
                    break;
            }
            upload[i] = new GpuMark
            {
                place = new Vector4(m.position.x - origin.x, m.position.y - origin.y, m.position.z - origin.z, m.radius),
                normal = new Vector4(m.normal.x, m.normal.y, m.normal.z, m.turn),
                look = new Vector4((int)m.kind, m.seed, opacity, growth),
                color = new Vector4(color.r, color.g, color.b, smoothness),
            };
        }
        gpu.SetData(upload, 0, 0, count);
        material.SetFloat("_GfxDecalDebug", GfxJuice.Debug ? 1f : 0f);
        if (count != drawn)
        {
            argsData[0] = box.GetIndexCount(0);
            argsData[1] = (uint)count;
            args.SetData(argsData);
            drawn = count;
        }
        Attach(playerCamera);
    }

    private static void Attach(Camera playerCamera)
    {
        if (attached && camera == playerCamera)
            return;
        Detach();
        if (commands == null)
        {
            commands = new CommandBuffer { name = "GraphicsExpanded juice marks" };
            // G-buffers 0 to 2 bound the way the rain wetness pass binds them; then the light buffer on its own, which is
            // the camera's target (the game renders HDR, so there's no separate G-buffer 3)
            commands.SetRenderTarget(new RenderTargetIdentifier[]
            {
                BuiltinRenderTextureType.GBuffer0, BuiltinRenderTextureType.GBuffer1, BuiltinRenderTextureType.GBuffer2,
            }, BuiltinRenderTextureType.CameraTarget);
            commands.DrawMeshInstancedIndirect(box, 0, material, 0, args);
            commands.SetRenderTarget(BuiltinRenderTextureType.CameraTarget);
            commands.DrawMeshInstancedIndirect(box, 0, material, 1, args);
        }
        camera = playerCamera;
        camera.AddCommandBuffer(CameraEvent.BeforeReflections, commands);
        attached = true;
    }

    private static void Detach()
    {
        if (attached && camera != null)
            camera.RemoveCommandBuffer(CameraEvent.BeforeReflections, commands);
        attached = false;
        camera = null;
    }
}
