using System;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Game juice's flying bits (Juice.shader) and light-bending ones (JuiceWarp.shader). Every bit lives in a plain array
/// and is moved here on the CPU: gravity, drag towards the wind (so smoke and dust drift and settle), and for the ones
/// that need it a ray against the world each frame, to bounce sparks off the floor or turn a falling blood drop into
/// a splash on whatever it lands on. Each frame the live ones are sorted far to near and drawn in one instanced call.
/// Positions are kept in the game's world coordinates, so the floating origin moving doesn't shift them.
/// </summary>
public static class GfxJuiceParticles
{
    /// <summary>The shapes Juice.shader draws.</summary>
    public enum Shape { Puff, Spark, Drop, Clod, Ring, Glint, Flash, Leaf, Smoke }

    /// <summary>How a bit is drawn: glowing (its own light) or lit by the sky and sun; flat on a surface; soft where it meets one.</summary>
    [Flags]
    public enum Look { Glowing = 0, Lit = 1, Flat = 2, Soft = 4 }

    /// <summary>What a bit does when it runs into something solid.</summary>
    public enum Hit { None, Bounce, Die, Blood }

    public enum Warp { Shimmer, Shockwave }

    private const int Max = 4096, MaxWarps = 96;

    private struct Bit
    {
        public Vector3 position, velocity;      // world coordinates, m/s
        public Vector3 normal;                  // flat bits face this way
        public Color color, endColor;
        public float age, life;                 // seconds
        public float size, endSize;             // half width, m
        public float gravity, drag, stretch;    // m/s²; 1/s (towards the wind); seconds of motion the streak spans
        public float turn, spin;                // radians, radians/s
        public float fadeIn, fadeOut;           // shares of the life spent fading in, and the age (share) fading out starts
        public float seed;
        public Shape shape;
        public Look look;
        public Hit hit;
    }

    // What the shaders read: 64 bytes each
    private struct GpuBit
    {
        public Vector4 place, color, axis, info;
    }

    private static Material material, warpMaterial;
    private static Mesh quad;
    private static ComputeBuffer gpu, gpuWarps, args, warpArgs;
    private static readonly Bit[] bits = new Bit[Max];
    private static readonly Bit[] warps = new Bit[MaxWarps];
    private static readonly GpuBit[] upload = new GpuBit[Max];
    private static readonly GpuBit[] uploadWarps = new GpuBit[MaxWarps];
    private static readonly float[] sortKeys = new float[Max];
    private static readonly int[] sortOrder = new int[Max];
    private static int count, warpCount, drawnCount = -1, drawnWarps = -1;
    private static readonly uint[] argsData = new uint[5];
    private static int mask;

    public static bool Loaded => material != null;
    public static int Count => count;
    public static int WarpCount => warpCount;

    public static void Init(Shader shader, Shader warpShader, Mesh unitQuad)
    {
        if (shader == null)
            return;
        quad = unitQuad;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        gpu = new ComputeBuffer(Max, 64);
        args = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
        material.SetBuffer("_GfxJuiceBits", gpu);
        if (warpShader != null)
        {
            warpMaterial = new Material(warpShader) { hideFlags = HideFlags.HideAndDontSave };
            gpuWarps = new ComputeBuffer(MaxWarps, 64);
            warpArgs = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
            warpMaterial.SetBuffer("_GfxJuiceWarps", gpuWarps);
        }
    }

    /// <summary>
    /// Adds a bit. Positions and velocities are in world coordinates; sizes are half widths. A bit with stretch draws as
    /// a streak along its motion, as long as the distance it covers in that many seconds.
    /// </summary>
    public static void Add(Shape shape, Look look, Vector3 position, Vector3 velocity, float life, float size, float endSize,
        Color color, Color endColor, float gravity = 0f, float drag = 0f, float stretch = 0f, Hit hit = Hit.None,
        float spin = 0f, Vector3 normal = default, float fadeIn = 0.05f, float fadeOut = 0.6f)
    {
        if (!Loaded || count >= Max || life <= 0f)
            return;
        bits[count++] = new Bit
        {
            position = position,
            velocity = velocity,
            normal = normal,
            color = color,
            endColor = endColor,
            life = life,
            size = size,
            endSize = endSize,
            gravity = gravity,
            drag = drag,
            stretch = stretch,
            turn = UnityEngine.Random.value * 6.2831853f,
            spin = spin,
            fadeIn = fadeIn,
            fadeOut = fadeOut,
            seed = UnityEngine.Random.value,
            shape = shape,
            look = look,
            hit = hit,
        };
    }

    /// <summary>Adds a light-bending bit: a heat shimmer or a shockwave ring that grows from size to endSize.</summary>
    public static void AddWarp(Warp kind, Vector3 position, Vector3 velocity, float life, float size, float endSize, float strength)
    {
        if (warpMaterial == null || warpCount >= MaxWarps)
            return;
        warps[warpCount++] = new Bit
        {
            position = position,
            velocity = velocity,
            life = life,
            size = size,
            endSize = endSize,
            color = new Color(0f, 0f, 0f, strength),
            seed = UnityEngine.Random.value,
            shape = (Shape)(int)kind,
            fadeIn = 0.1f,
            fadeOut = 0.5f,
        };
    }

    public static void Clear()
    {
        count = warpCount = 0;
    }

    /// <summary>Called every frame from GfxJuice.Update: moves every bit, then draws them.</summary>
    public static void Update(Camera playerCamera, float deltaTime, Vector3 wind, Color sunlight)
    {
        if (!Loaded)
            return;
        if (mask == 0)
            mask = GfxJuice.WorldMask;
        Vector3 origin = Origin.position;
        Vector3 camera = playerCamera.transform.position + origin;
        deltaTime = Mathf.Min(deltaTime, 0.1f);

        // Move, and drop the dead by moving the last one into their place
        for (int i = 0; i < count; i++)
        {
            ref Bit b = ref bits[i];
            b.age += deltaTime;
            if (b.age >= b.life || !Step(ref b, deltaTime, wind, origin))
            {
                bits[i--] = bits[--count];
                continue;
            }
        }
        for (int i = 0; i < warpCount; i++)
        {
            ref Bit w = ref warps[i];
            w.age += deltaTime;
            w.position += w.velocity * deltaTime;
            if (w.age >= w.life)
                warps[i--] = warps[--warpCount];
        }

        // Far to near, so covering bits overlap the right way round. Distances are rounded to half a meter with each
        // bit's seed breaking ties, so bits about as far away don't keep swapping (and flickering) as the view moves.
        for (int i = 0; i < count; i++)
        {
            sortKeys[i] = -Mathf.Round((bits[i].position - camera).magnitude * 2f) - bits[i].seed * 0.5f;
            sortOrder[i] = i;
        }
        Array.Sort(sortKeys, sortOrder, 0, count);
        for (int i = 0; i < count; i++)
            upload[i] = ToGpu(ref bits[sortOrder[i]], origin);

        material.SetVector("_GfxJuiceSun", sunlight);
        Draw(material, gpu, args, upload, count, ref drawnCount, playerCamera);

        if (warpMaterial != null)
        {
            for (int i = 0; i < warpCount; i++)
                uploadWarps[i] = ToGpu(ref warps[i], origin);
            Draw(warpMaterial, gpuWarps, warpArgs, uploadWarps, warpCount, ref drawnWarps, playerCamera);
        }
    }

    /// <summary>One frame of motion. False when the bit should go (it hit something it dies on).</summary>
    private static bool Step(ref Bit b, float deltaTime, Vector3 wind, Vector3 origin)
    {
        b.turn += b.spin * deltaTime;
        if (b.drag > 0f)
            b.velocity += (wind - b.velocity) * (1f - Mathf.Exp(-b.drag * deltaTime));
        b.velocity.y -= b.gravity * deltaTime;
        Vector3 move = b.velocity * deltaTime;
        if (b.hit != Hit.None && move.sqrMagnitude > 1e-8f)
        {
            float distance = move.magnitude;
            if (Physics.Raycast(b.position - origin, move / distance, out RaycastHit hit, distance + 0.01f, mask, QueryTriggerInteraction.Ignore))
            {
                Vector3 at = hit.point + origin;
                switch (b.hit)
                {
                    case Hit.Die:
                        return false;
                    case Hit.Blood:
                        GfxJuiceDecals.BloodDrop(at, hit.normal, b.size);
                        return false;
                    case Hit.Bounce:
                        b.position = at + hit.normal * 0.01f;
                        b.velocity = Vector3.Reflect(b.velocity, hit.normal) * 0.35f;
                        b.velocity -= hit.normal * Vector3.Dot(b.velocity, hit.normal) * 0.3f;
                        if (b.velocity.sqrMagnitude < 0.04f)
                            b.velocity = Vector3.zero;
                        return true;
                }
            }
        }
        b.position += move;
        return true;
    }

    private static GpuBit ToGpu(ref Bit b, Vector3 origin)
    {
        float t = Mathf.Clamp01(b.age / b.life);
        float alpha = (b.fadeIn > 0f ? Mathf.Clamp01(t / b.fadeIn) : 1f) * (1f - Smooth(b.fadeOut, 1f, t));
        Color color = Color.LerpUnclamped(b.color, b.endColor, t);
        float size = Mathf.LerpUnclamped(b.size, b.endSize, t);
        Vector3 axis;
        if ((b.look & Look.Flat) != 0)
            axis = b.normal;
        else if (b.stretch > 0f)
            axis = b.velocity * (b.stretch * 0.5f);
        else
            axis = Vector3.zero;
        return new GpuBit
        {
            place = new Vector4(b.position.x - origin.x, b.position.y - origin.y, b.position.z - origin.z, size),
            color = (b.look & Look.Lit) != 0 || color.a > 0f
                ? new Vector4(color.r, color.g, color.b, color.a * alpha)
                : new Vector4(color.r * alpha, color.g * alpha, color.b * alpha, 0f),
            axis = new Vector4(axis.x, axis.y, axis.z, b.turn),
            info = new Vector4((int)b.shape, b.seed, t, (int)b.look),
        };
    }

    private static void Draw(Material drawWith, ComputeBuffer buffer, ComputeBuffer drawArgs, GpuBit[] data, int n, ref int drawn, Camera playerCamera)
    {
        if (n == 0)
            return;
        buffer.SetData(data, 0, 0, n);
        if (n != drawn)
        {
            argsData[0] = quad.GetIndexCount(0);
            argsData[1] = (uint)n;
            drawArgs.SetData(argsData);
            drawn = n;
        }
        Graphics.DrawMeshInstancedIndirect(quad, 0, drawWith, new Bounds(playerCamera.transform.position, Vector3.one * 4000f), drawArgs, 0,
            null, ShadowCastingMode.Off, false, 0, playerCamera, LightProbeUsage.Off);
    }

    private static float Smooth(float from, float to, float value)
    {
        if (to <= from)
            return value >= to ? 1f : 0f;
        float t = Mathf.Clamp01((value - from) / (to - from));
        return t * t * (3f - 2f * t);
    }
}
