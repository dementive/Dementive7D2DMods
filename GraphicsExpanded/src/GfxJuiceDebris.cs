using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Game juice's solid bits (JuiceDebris.shader): spent casings, wood splinters, stone and concrete chunks, dirt clods
/// and glass shards. Each piece flies, tumbles and bounces off the world (a ray along its motion each frame), then
/// settles lying flat and stays a while before fading out, so brass piles up round a firing position and chips gather
/// under a wall the horde is beating on. Pieces don't collide with each other. They go into the G-buffer, so they're
/// lit and shaded like everything else. Positions are in world coordinates, so the floating origin doesn't move them.
/// </summary>
public static class GfxJuiceDebris
{
    /// <summary>The meshes: a casing (also shotgun shells), an irregular chunk (stone, concrete, dirt, metal scrap), a splinter, a shard.</summary>
    public enum Kind { Casing, Chunk, Splinter, Shard }

    private const int Max = 1024;
    private const int Kinds = 4;
    private const float FadeSeconds = 1.5f;

    private struct Piece
    {
        public Vector3 position, velocity, spinAxis;    // world coordinates, m/s
        public Quaternion rotation;
        public Vector3 scale;
        public Color color;                             // rgb albedo, a smoothness
        public float metallic, glow, cooling;           // emission as a multiple of the albedo, and how fast it fades (1/s)
        public float spin;                              // degrees/s
        public float age, life, nextCheck;
        public bool resting;
        public Kind kind;
    }

    private struct GpuPiece
    {
        public Vector4 row0, row1, row2, color, surface;
    }

    private static Material material;
    private static readonly Mesh[] meshes = new Mesh[Kinds];
    private static readonly ComputeBuffer[] buffers = new ComputeBuffer[Kinds];
    private static readonly ComputeBuffer[] argBuffers = new ComputeBuffer[Kinds];
    private static readonly MaterialPropertyBlock[] blocks = new MaterialPropertyBlock[Kinds];
    private static readonly GpuPiece[][] uploads = new GpuPiece[Kinds][];
    private static readonly int[] counts = new int[Kinds];
    private static readonly int[] drawn = new int[Kinds];
    private static readonly uint[] argsData = new uint[5];
    private static readonly Piece[] pieces = new Piece[Max];
    private static int count;
    private static int mask;

    public static bool Loaded => material != null;
    public static int Count => count;

    public static void Init(Shader shader)
    {
        if (shader == null)
            return;
        material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        meshes[(int)Kind.Casing] = Cylinder();
        meshes[(int)Kind.Chunk] = Chunk();
        meshes[(int)Kind.Splinter] = Splinter();
        meshes[(int)Kind.Shard] = Shard();
        for (int k = 0; k < Kinds; k++)
        {
            buffers[k] = new ComputeBuffer(Max, 80);
            argBuffers[k] = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
            blocks[k] = new MaterialPropertyBlock();
            blocks[k].SetBuffer("_GfxDebris", buffers[k]);
            uploads[k] = new GpuPiece[Max];
            drawn[k] = -1;
        }
    }

    /// <summary>
    /// Adds a piece flying off from position (world) at velocity, tumbling at spin degrees a second. Scale is its size
    /// in meters: a casing's or splinter's length along x, a shard's flat across x and z. Glow makes it hot (a multiple
    /// of its color as emission) and cooling how fast that fades. The oldest piece goes when the pool is full.
    /// </summary>
    public static void Add(Kind kind, Vector3 position, Vector3 velocity, Vector3 scale, Color color, float smoothness,
        float metallic, float life, float spin = 720f, float glow = 0f, float cooling = 1f)
    {
        if (!Loaded)
            return;
        int slot = count < Max ? count++ : Oldest();
        pieces[slot] = new Piece
        {
            position = position,
            velocity = velocity,
            spinAxis = Random.onUnitSphere,
            spin = spin * Random.Range(0.6f, 1.4f),
            rotation = Random.rotationUniform,
            scale = scale,
            color = new Color(color.r, color.g, color.b, smoothness),
            metallic = metallic,
            glow = glow,
            cooling = cooling,
            life = life,
            kind = kind,
        };
    }

    public static void Clear()
    {
        count = 0;
    }

    private static int Oldest()
    {
        int oldest = 0;
        float most = -1f;
        for (int i = 0; i < count; i++)
        {
            float left = pieces[i].age / pieces[i].life;
            if (left > most)
            {
                most = left;
                oldest = i;
            }
        }
        return oldest;
    }

    /// <summary>Called every frame from GfxJuice.Update: moves, settles and draws the pieces.</summary>
    public static void Update(Camera playerCamera, float deltaTime)
    {
        if (!Loaded)
            return;
        if (mask == 0)
            mask = GfxJuice.WorldMask;
        deltaTime = Mathf.Min(deltaTime, 0.1f);
        Vector3 origin = Origin.position;
        for (int k = 0; k < Kinds; k++)
            counts[k] = 0;

        for (int i = 0; i < count; i++)
        {
            ref Piece p = ref pieces[i];
            p.age += deltaTime;
            if (p.age >= p.life)
            {
                pieces[i--] = pieces[--count];
                continue;
            }
            p.glow *= Mathf.Exp(-p.cooling * deltaTime);
            if (p.resting)
                CheckStillResting(ref p, origin);
            else
                Fly(ref p, deltaTime, origin);

            int kind = (int)p.kind;
            Matrix4x4 m = Matrix4x4.TRS(p.position - origin, p.rotation, p.scale);
            float shown = 1f - Mathf.Clamp01((p.age - (p.life - FadeSeconds)) / FadeSeconds);
            uploads[kind][counts[kind]++] = new GpuPiece
            {
                row0 = m.GetRow(0),
                row1 = m.GetRow(1),
                row2 = m.GetRow(2),
                color = p.color,
                surface = new Vector4(p.metallic, p.glow, shown, 0f),
            };
        }

        Bounds bounds = new Bounds(playerCamera.transform.position, Vector3.one * 2000f);
        for (int k = 0; k < Kinds; k++)
        {
            if (counts[k] == 0)
                continue;
            buffers[k].SetData(uploads[k], 0, 0, counts[k]);
            if (counts[k] != drawn[k])
            {
                argsData[0] = meshes[k].GetIndexCount(0);
                argsData[1] = (uint)counts[k];
                argBuffers[k].SetData(argsData);
                drawn[k] = counts[k];
            }
            Graphics.DrawMeshInstancedIndirect(meshes[k], 0, material, bounds, argBuffers[k], 0, blocks[k],
                ShadowCastingMode.Off, true, 0, playerCamera, LightProbeUsage.Off);
        }
    }

    private static void Fly(ref Piece p, float deltaTime, Vector3 origin)
    {
        p.velocity.y -= 9.81f * deltaTime;
        p.velocity *= 1f - 0.15f * deltaTime;
        Vector3 move = p.velocity * deltaTime;
        float distance = move.magnitude;
        float radius = Thickness(ref p) * 0.5f;
        if (distance > 1e-5f && Physics.Raycast(p.position - origin, move / distance, out RaycastHit hit, distance + radius, mask, QueryTriggerInteraction.Ignore))
        {
            Vector3 n = hit.normal;
            Vector3 along = Vector3.Dot(p.velocity, n) * n;
            Vector3 across = p.velocity - along;
            p.velocity = -along * 0.35f + across * 0.55f;
            p.spin *= 0.6f;
            p.spinAxis = Vector3.Cross(n, across.sqrMagnitude > 1e-4f ? across.normalized : Random.onUnitSphere).normalized;
            p.position = hit.point + origin + n * radius;
            if (p.velocity.sqrMagnitude < 0.36f && n.y > 0.55f)
                Settle(ref p, n);
            return;
        }
        p.position += move;
        if (p.spinAxis.sqrMagnitude > 0.5f)
            p.rotation = Quaternion.AngleAxis(p.spin * deltaTime, p.spinAxis) * p.rotation;
    }

    /// <summary>Lies down on the surface: long pieces along it, flat ones flat on it.</summary>
    private static void Settle(ref Piece p, Vector3 normal)
    {
        p.resting = true;
        p.velocity = Vector3.zero;
        p.spin = 0f;
        p.nextCheck = p.age + 1f;
        if (p.kind == Kind.Chunk)
            return;
        Vector3 length = p.rotation * Vector3.right;
        Vector3 flat = Vector3.ProjectOnPlane(length, normal);
        if (flat.sqrMagnitude < 1e-4f)
            flat = Vector3.ProjectOnPlane(Random.onUnitSphere, normal);
        Quaternion lying = Quaternion.LookRotation(flat.normalized, normal);
        // LookRotation points z along flat; casings and splinters run along x, shards lie in x and z
        p.rotation = p.kind == Kind.Shard ? lying : lying * Quaternion.Euler(0f, -90f, 0f);
    }

    /// <summary>Once a second: if what a resting piece lay on is gone (a block broken), it falls again.</summary>
    private static void CheckStillResting(ref Piece p, Vector3 origin)
    {
        if (p.age < p.nextCheck)
            return;
        p.nextCheck = p.age + 1f;
        if (!Physics.Raycast(p.position - origin + Vector3.up * 0.02f, Vector3.down, Thickness(ref p) + 0.08f, mask, QueryTriggerInteraction.Ignore))
            p.resting = false;
    }

    /// <summary>How thick it is lying down: a chunk's smallest side; a casing's width, a splinter's or shard's thickness (y).</summary>
    private static float Thickness(ref Piece p)
    {
        return p.kind == Kind.Chunk ? Mathf.Min(p.scale.x, Mathf.Min(p.scale.y, p.scale.z)) : p.scale.y;
    }

    // ---- Meshes, all flat shaded, about a unit across ----

    /// <summary>A casing: an eight-sided cylinder along x, 1 long and 1 across.</summary>
    private static Mesh Cylinder()
    {
        const int sides = 8;
        Vector3[] corners = new Vector3[sides * 2];
        for (int i = 0; i < sides; i++)
        {
            float a = i * Mathf.PI * 2f / sides;
            corners[i] = new Vector3(-0.5f, Mathf.Cos(a) * 0.5f, Mathf.Sin(a) * 0.5f);
            corners[i + sides] = new Vector3(0.5f, Mathf.Cos(a) * 0.5f, Mathf.Sin(a) * 0.5f);
        }
        System.Collections.Generic.List<int> tris = new System.Collections.Generic.List<int>();
        for (int i = 0; i < sides; i++)
        {
            int j = (i + 1) % sides;
            tris.AddRange(new[] { i, j, j + sides, i, j + sides, i + sides });
            if (i > 0 && i < sides - 1)
            {
                tris.AddRange(new[] { 0, i + 1, i });
                tris.AddRange(new[] { sides, sides + i, sides + i + 1 });
            }
        }
        return Flat("GraphicsExpanded casing", corners, tris.ToArray());
    }

    /// <summary>A chunk: a unit cube with its corners pushed about, so it looks broken off.</summary>
    private static Mesh Chunk()
    {
        Vector3[] corners =
        {
            new Vector3(-0.5f, -0.42f, -0.5f), new Vector3(0.38f, -0.5f, -0.46f), new Vector3(0.5f, 0.36f, -0.5f), new Vector3(-0.44f, 0.5f, -0.3f),
            new Vector3(-0.32f, -0.5f, 0.5f), new Vector3(0.5f, -0.3f, 0.44f), new Vector3(0.3f, 0.5f, 0.5f), new Vector3(-0.5f, 0.28f, 0.42f),
        };
        int[] tris =
        {
            0, 2, 1, 0, 3, 2,   4, 5, 6, 4, 6, 7,   0, 1, 5, 0, 5, 4,
            3, 6, 2, 3, 7, 6,   0, 4, 7, 0, 7, 3,   1, 2, 6, 1, 6, 5,
        };
        return Flat("GraphicsExpanded chunk", corners, tris);
    }

    /// <summary>A splinter: a three-sided rod along x, 1 long and 1 across, pointed at one end.</summary>
    private static Mesh Splinter()
    {
        Vector3[] corners =
        {
            new Vector3(-0.5f, 0.5f, 0f), new Vector3(-0.5f, -0.3f, 0.45f), new Vector3(-0.5f, -0.3f, -0.45f),
            new Vector3(0.3f, 0.3f, 0f), new Vector3(0.3f, -0.2f, 0.25f), new Vector3(0.3f, -0.2f, -0.25f),
            new Vector3(0.5f, 0f, 0f),
        };
        int[] tris =
        {
            0, 2, 1,
            0, 1, 4, 0, 4, 3,   1, 2, 5, 1, 5, 4,   2, 0, 3, 2, 3, 5,
            3, 4, 6, 4, 5, 6, 5, 3, 6,
        };
        return Flat("GraphicsExpanded splinter", corners, tris);
    }

    /// <summary>A shard: a thin three-cornered plate lying in x and z, 1 across and 1 thick.</summary>
    private static Mesh Shard()
    {
        Vector3[] corners =
        {
            new Vector3(-0.5f, 0.5f, -0.4f), new Vector3(0.5f, 0.5f, -0.2f), new Vector3(-0.1f, 0.5f, 0.5f),
            new Vector3(-0.5f, -0.5f, -0.4f), new Vector3(0.5f, -0.5f, -0.2f), new Vector3(-0.1f, -0.5f, 0.5f),
        };
        int[] tris =
        {
            0, 2, 1,   3, 4, 5,
            0, 1, 4, 0, 4, 3,   1, 2, 5, 1, 5, 4,   2, 0, 3, 2, 3, 5,
        };
        return Flat("GraphicsExpanded shard", corners, tris);
    }

    /// <summary>A mesh with its own corners for each triangle, so every face is flat. Winding is fixed up to face outwards.</summary>
    internal static Mesh Flat(string name, Vector3[] corners, int[] tris)
    {
        Vector3 middle = Vector3.zero;
        foreach (Vector3 c in corners)
            middle += c;
        middle /= corners.Length;
        Vector3[] vertices = new Vector3[tris.Length];
        Vector3[] normals = new Vector3[tris.Length];
        int[] indices = new int[tris.Length];
        for (int t = 0; t < tris.Length; t += 3)
        {
            Vector3 a = corners[tris[t]], b = corners[tris[t + 1]], c = corners[tris[t + 2]];
            Vector3 n = Vector3.Cross(b - a, c - a).normalized;
            if (Vector3.Dot(n, (a + b + c) / 3f - middle) < 0f)
            {
                (b, c) = (c, b);
                n = -n;
            }
            vertices[t] = a;
            vertices[t + 1] = b;
            vertices[t + 2] = c;
            normals[t] = normals[t + 1] = normals[t + 2] = n;
            indices[t] = t;
            indices[t + 1] = t + 1;
            indices[t + 2] = t + 2;
        }
        Mesh mesh = new Mesh { name = name, hideFlags = HideFlags.HideAndDontSave };
        mesh.vertices = vertices;
        mesh.normals = normals;
        mesh.triangles = indices;
        mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 100000f);
        return mesh;
    }
}
