using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// The traps' particle effects and projectile visuals (Assets/TrapsExpanded/Fx), which the game's own particle list
/// doesn't have: tar, fire jets and ground fire, cold mist and frost, and the arrows, bolts and globs the traps fire.
/// The mod's C# (FxDEM, ProjectileFxDEM) spawns them by prefab name. Looping effects are stopped by the mod when their
/// time is up; projectiles are moved by it, pointing along +Z with their tip at the origin.
/// </summary>
public static class TrapsEffects
{
    private const string Fx = "Assets/TrapsExpanded/Fx";

    public static List<string> BuildAll()
    {
        return new List<string>
        {
            TarDrip(), TarSplat(), TarGlob(), FlameJet("FlameJet", 14f, 12f, 1f), FlameJet("FlameJetLong", 27f, 5f, 1.2f),
            GroundFire(), BarrelFire(), ColdMist(), IcePatch(), FrostMist(), FrostCrust(),
            Arrow("ArrowFx", false), Arrow("ArrowFlamingFx", true), Bolt(),
        };
    }

    // ------------------------------------------------------------------ materials and meshes

    private static Material Additive(string name, Color tint)
    {
        string path = Fx + "/" + name + ".mat";
        Shader shader = Shader.Find("Legacy Shaders/Particles/Additive");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = shader;
        m.SetTexture("_MainTex", TrapsBuilder.Dot());
        m.SetColor("_TintColor", tint);
        EditorUtility.SetDirty(m);
        return m;
    }

    /// <summary>Alpha-blended unlit particles (smoke, trails): not lit, but dark smoke doesn't need light.</summary>
    private static Material Blended(string name, Color tint)
    {
        string path = Fx + "/" + name + ".mat";
        Shader shader = Shader.Find("Legacy Shaders/Particles/Alpha Blended");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(shader);
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = shader;
        m.SetTexture("_MainTex", TrapsBuilder.Dot());
        m.SetColor("_TintColor", tint);
        EditorUtility.SetDirty(m);
        return m;
    }

    private static Material Solid(string name, Color color, float metallic, float smoothness)
    {
        string path = Fx + "/" + name + ".mat";
        Material m = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (m == null)
        {
            m = new Material(Shader.Find("Standard"));
            AssetDatabase.CreateAsset(m, path);
        }
        m.shader = Shader.Find("Standard");
        m.color = color;
        m.SetFloat("_Metallic", metallic);
        m.SetFloat("_Glossiness", smoothness);
        EditorUtility.SetDirty(m);
        return m;
    }

    /// <summary>A mesh of boxes (center, size), saved as an asset so the bundle carries it.</summary>
    private static Mesh Boxes(string name, params (Vector3 c, Vector3 s)[] boxes)
    {
        List<Vector3> v = new List<Vector3>();
        List<Vector3> n = new List<Vector3>();
        List<int> tri = new List<int>();
        Vector3[] dirs = { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
        foreach ((Vector3 c, Vector3 s) in boxes)
        {
            foreach (Vector3 d in dirs)
            {
                Vector3 a = d.x != 0f ? Vector3.up : Vector3.right;
                Vector3 b = Vector3.Cross(d, a);
                int i0 = v.Count;
                foreach (Vector2 k in new[] { new Vector2(-1, -1), new Vector2(1, -1), new Vector2(1, 1), new Vector2(-1, 1) })
                {
                    Vector3 p = d + a * k.x + b * k.y;
                    v.Add(c + Vector3.Scale(p, s * 0.5f));
                    n.Add(d);
                }
                // Both windings: the parts are thin and seen from every side
                tri.AddRange(new[] { i0, i0 + 2, i0 + 1, i0, i0 + 3, i0 + 2, i0, i0 + 1, i0 + 2, i0, i0 + 2, i0 + 3 });
            }
        }
        Mesh mesh = new Mesh { name = name };
        mesh.SetVertices(v);
        mesh.SetNormals(n);
        mesh.SetTriangles(tri, 0);
        mesh.RecalculateBounds();
        string path = Fx + "/" + name + ".asset";
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(mesh, path);
        return mesh;
    }

    private static GameObject MeshObject(string name, Transform parent, Mesh mesh, Material material)
    {
        GameObject go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        MeshRenderer r = go.AddComponent<MeshRenderer>();
        r.sharedMaterial = material;
        r.shadowCastingMode = ShadowCastingMode.Off;
        return go;
    }

    private static ParticleSystem.MinMaxGradient Ramp(params (float t, Color c, float a)[] keys)
    {
        Gradient g = new Gradient();
        List<GradientColorKey> ck = new List<GradientColorKey>();
        List<GradientAlphaKey> ak = new List<GradientAlphaKey>();
        foreach ((float t, Color c, float a) in keys)
        {
            ck.Add(new GradientColorKey(c, t));
            ak.Add(new GradientAlphaKey(a, t));
        }
        g.SetKeys(ck.ToArray(), ak.ToArray());
        return new ParticleSystem.MinMaxGradient(g);
    }

    private static void Grow(ParticleSystem ps, float from, float to)
    {
        ParticleSystem.SizeOverLifetimeModule size = ps.sizeOverLifetime;
        size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, from, 1f, to));
    }

    private static string Save(GameObject go)
    {
        string path = Fx + "/" + go.name + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(go, path);
        Object.DestroyImmediate(go);
        return path;
    }

    private static void Light(Transform parent, Color color, float intensity, float range)
    {
        GameObject l = new GameObject("Glow");
        l.transform.SetParent(parent, false);
        Light light = l.AddComponent<Light>();
        light.type = LightType.Point;
        light.color = color;
        light.intensity = intensity;
        light.range = range;
        light.shadows = LightShadows.None;
    }

    // ------------------------------------------------------------------ tar

    private static readonly Color TarColor = new Color(0.025f, 0.022f, 0.02f);

    /// <summary>Thick black tar dripping off a tarred zombie, looping (the mod stops it when the tar wears off).</summary>
    private static string TarDrip()
    {
        GameObject go = new GameObject("TarDrip");
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("TarDrops", TarColor, 0.85f),
            ParticleSystemRenderMode.Stretch);
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.velocityScale = 0.08f;
        r.lengthScale = 2f;
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.duration = 1f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
        main.startSpeed = 0f;
        main.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.055f);
        main.gravityModifier = 0.7f;
        main.maxParticles = 60;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 12f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Box;
        shape.scale = new Vector3(0.4f, 0.8f, 0.3f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = TrapsBuilder.Fade(TarColor, 0.95f);
        return Save(go);
    }

    /// <summary>A glob of tar landing: black splatter thrown out and falling.</summary>
    private static string TarSplat()
    {
        GameObject go = new GameObject("TarSplat");
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("TarSplatter", TarColor, 0.8f),
            ParticleSystemRenderMode.Stretch);
        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.velocityScale = 0.05f;
        r.lengthScale = 1.2f;
        ParticleSystem.MainModule main = ps.main;
        main.loop = false;
        main.playOnAwake = true;
        main.duration = 0.3f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.7f, 1.1f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(1.5f, 3.5f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.06f, 0.14f);
        main.gravityModifier = 1.4f;
        main.maxParticles = 60;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 40) });
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Hemisphere;
        shape.radius = 0.15f;
        shape.rotation = new Vector3(-90f, 0f, 0f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = TrapsBuilder.Fade(TarColor, 1f);
        return Save(go);
    }

    /// <summary>A flying glob of tar: a glossy black lump trailing strings of tar.</summary>
    private static string TarGlob()
    {
        GameObject go = new GameObject("TarGlob");
        Mesh lump = Boxes("TarGlobMesh", (Vector3.zero, new Vector3(0.14f, 0.12f, 0.18f)),
            (new Vector3(0.02f, 0.03f, -0.06f), new Vector3(0.09f, 0.08f, 0.12f)),
            (new Vector3(-0.03f, -0.02f, 0.04f), new Vector3(0.1f, 0.1f, 0.1f)));
        MeshObject("Lump", go.transform, lump, Solid("TarGlobLump", TarColor, 0f, 0.85f));
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("TarStrings", TarColor, 0.8f),
            ParticleSystemRenderMode.Stretch);
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.25f, 0.45f);
        main.startSpeed = 0f;
        main.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.06f);
        main.gravityModifier = 0.6f;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 50f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.06f;
        return Save(go);
    }

    // ------------------------------------------------------------------ fire

    private static readonly Color FlameYellow = new Color(1f, 0.85f, 0.45f);
    private static readonly Color FlameOrange = new Color(1f, 0.45f, 0.1f);
    private static readonly Color FlameRed = new Color(0.6f, 0.12f, 0.03f);
    private static readonly Color Smoke = new Color(0.12f, 0.11f, 0.1f);

    private static ParticleSystem Flames(GameObject go, string material)
    {
        ParticleSystem ps = TrapsBuilder.Particles(go, Additive(material, new Color(1f, 0.78f, 0.5f, 0.5f)),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Ramp((0f, FlameYellow, 0.95f), (0.4f, FlameOrange, 0.8f), (0.75f, FlameRed, 0.25f), (1f, FlameRed, 0f));
        ParticleSystem.RotationOverLifetimeModule rot = ps.rotationOverLifetime;
        rot.enabled = true;
        rot.z = new ParticleSystem.MinMaxCurve(-2f, 2f);
        return ps;
    }

    private static void SmokeChild(Transform parent, string name, float rate, float speed, float size, float life)
    {
        GameObject s = new GameObject(name);
        s.transform.SetParent(parent, false);
        ParticleSystem ps = TrapsBuilder.Particles(s, Blended("TrapSmoke", new Color(0.5f, 0.5f, 0.5f, 0.5f)),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(life * 0.7f, life);
        main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.6f, speed);
        main.startSize = new ParticleSystem.MinMaxCurve(size * 0.6f, size);
        main.gravityModifier = -0.15f;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = rate;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 15f;
        shape.radius = 0.1f;
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Ramp((0f, Smoke, 0f), (0.2f, Smoke, 0.45f), (1f, Smoke, 0f));
        Grow(ps, 0.6f, 2f);
    }

    /// <summary>The Flame Vent's jet: flames streaming along +Z for about `speed` x 0.5 m, with smoke and a light.
    /// Looping; the mod spawns one for each burst.</summary>
    private static string FlameJet(string name, float speed, float angle, float size)
    {
        GameObject go = new GameObject(name);
        ParticleSystem ps = Flames(go, "FlameJetFire");
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.duration = 1f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.4f, 0.5f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.85f, speed);
        main.startSize = new ParticleSystem.MinMaxCurve(0.2f * size, 0.34f * size);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        main.gravityModifier = -0.2f;
        main.maxParticles = 700;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 420f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = angle;
        shape.radius = 0.04f;
        ParticleSystem.VelocityOverLifetimeModule drag = ps.velocityOverLifetime;
        drag.enabled = true;
        drag.space = ParticleSystemSimulationSpace.Local;
        drag.speedModifier = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 1f, 1f, 0.45f));
        Grow(ps, 0.4f, 4.5f);
        SmokeChild(go.transform, "JetSmoke", 25f, speed * 0.4f, 0.8f * size, 0.9f);
        Light(go.transform, FlameOrange, 3f, 7f);
        return Save(go);
    }

    /// <summary>Napalm burning on the ground: low flames over a patch about a meter across, with smoke.</summary>
    private static string GroundFire()
    {
        GameObject go = new GameObject("GroundFire");
        ParticleSystem ps = Flames(go, "GroundFireFire");
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.4f, 1.1f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.35f, 0.65f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        main.gravityModifier = -0.1f;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 90f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 0.5f;
        shape.rotation = new Vector3(-90f, 0f, 0f);
        Grow(ps, 1f, 0.3f);
        SmokeChild(go.transform, "GroundSmoke", 6f, 0.8f, 0.7f, 1.6f);
        go.transform.Find("GroundSmoke").localRotation = Quaternion.Euler(-90f, 0f, 0f);
        Light(go.transform, FlameOrange, 1.8f, 5f);
        return Save(go);
    }

    /// <summary>Flames and embers out of the Burn Barrel's top (used if the game's own barrel fire isn't
    /// found).</summary>
    private static string BarrelFire()
    {
        GameObject go = new GameObject("BarrelFire");
        ParticleSystem ps = Flames(go, "BarrelFireFire");
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.85f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.8f, 1.5f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.3f, 0.55f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 80f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 0.22f;
        shape.rotation = new Vector3(-90f, 0f, 0f);
        Grow(ps, 1f, 0.2f);

        GameObject embers = new GameObject("Embers");
        embers.transform.SetParent(go.transform, false);
        ParticleSystem e = TrapsBuilder.Particles(embers, Additive("BarrelEmbers", new Color(1f, 0.55f, 0.2f, 0.9f)),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule em = e.main;
        em.loop = true;
        em.playOnAwake = true;
        em.startLifetime = new ParticleSystem.MinMaxCurve(1f, 2f);
        em.startSpeed = new ParticleSystem.MinMaxCurve(1f, 2.2f);
        em.startSize = new ParticleSystem.MinMaxCurve(0.015f, 0.03f);
        em.gravityModifier = -0.05f;
        ParticleSystem.EmissionModule ee = e.emission;
        ee.rateOverTime = 6f;
        ParticleSystem.ShapeModule es = e.shape;
        es.shapeType = ParticleSystemShapeType.Cone;
        es.angle = 20f;
        es.radius = 0.2f;
        es.rotation = new Vector3(-90f, 0f, 0f);
        ParticleSystem.NoiseModule noise = e.noise;
        noise.enabled = true;
        noise.strength = 0.6f;
        noise.frequency = 1.5f;
        SmokeChild(go.transform, "BarrelSmoke", 5f, 1f, 0.6f, 2f);
        go.transform.Find("BarrelSmoke").localRotation = Quaternion.Euler(-90f, 0f, 0f);
        return Save(go);
    }

    // ------------------------------------------------------------------ cold

    private static readonly Color Frost = new Color(0.82f, 0.9f, 1f);

    /// <summary>A Cryo Vent pulse: cold vapor rolling up off the grate and spilling out.</summary>
    private static string ColdMist()
    {
        GameObject go = new GameObject("ColdMist");
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("ColdVapor", Frost, 0.2f),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule main = ps.main;
        main.loop = false;
        main.playOnAwake = true;
        main.duration = 0.4f;
        main.startLifetime = new ParticleSystem.MinMaxCurve(1f, 1.6f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 0.7f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.25f, 0.5f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        main.gravityModifier = 0.02f;
        main.maxParticles = 80;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 26) });
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Box;
        shape.scale = new Vector3(0.6f, 0.6f, 0.05f);
        shape.rotation = new Vector3(-90f, 0f, 0f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Ramp((0f, Frost, 0f), (0.15f, Frost, 0.4f), (1f, Frost, 0f));
        Grow(ps, 0.7f, 2.4f);
        return Save(go);
    }

    /// <summary>Frost Field: a pale ice sheet on the ground around the vent with a few glints.</summary>
    private static string IcePatch()
    {
        GameObject go = new GameObject("IcePatch");
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("IceSheet", new Color(0.78f, 0.88f, 1f), 0.95f),
            ParticleSystemRenderMode.HorizontalBillboard);
        ParticleSystem.MainModule main = ps.main;
        main.loop = false;
        main.playOnAwake = true;
        main.duration = 0.1f;
        main.startLifetime = 6f;
        main.startSpeed = 0f;
        main.startSize = new ParticleSystem.MinMaxCurve(1.2f, 2.2f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        main.maxParticles = 12;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 7) });
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 1.6f;
        shape.rotation = new Vector3(-90f, 0f, 0f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Ramp((0f, Frost, 0f), (0.05f, Frost, 0.45f), (0.8f, Frost, 0.4f), (1f, Frost, 0f));
        return Save(go);
    }

    /// <summary>A chilled zombie: thin cold vapor drifting off it, looping.</summary>
    private static string FrostMist()
    {
        GameObject go = new GameObject("FrostMist");
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("FrostVapor", Frost, 0.2f),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.3f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.05f, 0.25f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.15f, 0.3f);
        main.gravityModifier = 0.05f;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 16f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Box;
        shape.scale = new Vector3(0.45f, 1f, 0.35f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Ramp((0f, Frost, 0f), (0.2f, Frost, 0.38f), (1f, Frost, 0f));
        Grow(ps, 0.6f, 1.8f);
        return Save(go);
    }

    /// <summary>A frozen zombie: a crust of white ice glints all over the body, and heavy cold vapor.</summary>
    private static string FrostCrust()
    {
        GameObject go = new GameObject("FrostCrust");
        ParticleSystem ps = TrapsBuilder.Particles(go, TrapsBuilder.WaterMaterial("FrostIce", new Color(0.9f, 0.95f, 1f), 0.9f),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule main = ps.main;
        main.loop = true;
        main.playOnAwake = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.6f, 1.1f);
        main.startSpeed = 0f;
        main.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.12f);
        main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
        main.maxParticles = 220;
        main.prewarm = true;
        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 160f;
        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Box;
        shape.scale = new Vector3(0.45f, 1.5f, 0.32f);
        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        col.color = Ramp((0f, Frost, 0f), (0.1f, Frost, 0.85f), (0.85f, Frost, 0.8f), (1f, Frost, 0f));

        GameObject vapor = new GameObject("Vapor");
        vapor.transform.SetParent(go.transform, false);
        ParticleSystem v = TrapsBuilder.Particles(vapor, TrapsBuilder.WaterMaterial("FrostVapor", Frost, 0.2f),
            ParticleSystemRenderMode.Billboard);
        ParticleSystem.MainModule vm = v.main;
        vm.loop = true;
        vm.playOnAwake = true;
        vm.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.4f);
        vm.startSpeed = new ParticleSystem.MinMaxCurve(0.05f, 0.2f);
        vm.startSize = new ParticleSystem.MinMaxCurve(0.25f, 0.45f);
        vm.gravityModifier = 0.08f;
        ParticleSystem.EmissionModule ve = v.emission;
        ve.rateOverTime = 14f;
        ParticleSystem.ShapeModule vs = v.shape;
        vs.shapeType = ParticleSystemShapeType.Box;
        vs.scale = new Vector3(0.5f, 1.4f, 0.4f);
        ParticleSystem.ColorOverLifetimeModule vc = v.colorOverLifetime;
        vc.enabled = true;
        vc.color = Ramp((0f, Frost, 0f), (0.2f, Frost, 0.3f), (1f, Frost, 0f));
        Grow(v, 0.6f, 1.8f);
        return Save(go);
    }

    // ------------------------------------------------------------------ projectiles

    private static void Trail(GameObject go, Color color, float width, float time)
    {
        TrailRenderer trail = go.AddComponent<TrailRenderer>();
        trail.sharedMaterial = Blended("ProjectileTrail", new Color(0.5f, 0.5f, 0.5f, 0.5f));
        trail.time = time;
        trail.widthMultiplier = width;
        trail.widthCurve = AnimationCurve.Linear(0f, 1f, 1f, 0f);
        trail.startColor = color;
        trail.endColor = new Color(color.r, color.g, color.b, 0f);
        trail.minVertexDistance = 0.1f;
        trail.shadowCastingMode = ShadowCastingMode.Off;
        trail.receiveShadows = false;
    }

    /// <summary>An arrow in flight: shaft, broadhead and vanes, tip at the origin pointing +Z; a flaming arrow has a
    /// flame at its head.</summary>
    private static string Arrow(string name, bool flaming)
    {
        GameObject go = new GameObject(name);
        Mesh shaft = Boxes(name + "ShaftMesh", (new Vector3(0f, 0f, -0.36f), new Vector3(0.011f, 0.011f, 0.68f)));
        Mesh head = Boxes(name + "HeadMesh", (new Vector3(0f, 0f, -0.025f), new Vector3(0.026f, 0.006f, 0.05f)),
            (new Vector3(0f, 0f, -0.025f), new Vector3(0.006f, 0.026f, 0.05f)));
        Mesh vanes = Boxes(name + "VaneMesh", (new Vector3(0f, 0.012f, -0.64f), new Vector3(0.002f, 0.018f, 0.09f)),
            (new Vector3(0.011f, -0.007f, -0.64f), new Vector3(0.018f, 0.002f, 0.09f)),
            (new Vector3(-0.011f, -0.007f, -0.64f), new Vector3(0.018f, 0.002f, 0.09f)));
        MeshObject("Shaft", go.transform, shaft, Solid("ArrowShaft", new Color(0.18f, 0.16f, 0.14f), 0.2f, 0.4f));
        MeshObject("Head", go.transform, head, Solid("ArrowHead", new Color(0.35f, 0.34f, 0.33f), 0.9f, 0.55f));
        MeshObject("Vanes", go.transform, vanes, Solid("ArrowVanes", new Color(0.55f, 0.6f, 0.2f), 0f, 0.3f));
        Trail(go, new Color(1f, 1f, 1f, 0.18f), 0.02f, 0.12f);
        if (flaming)
        {
            GameObject fire = new GameObject("HeadFire");
            fire.transform.SetParent(go.transform, false);
            fire.transform.localPosition = new Vector3(0f, 0f, -0.06f);
            ParticleSystem ps = Flames(fire, "ArrowFire");
            ParticleSystem.MainModule main = ps.main;
            main.loop = true;
            main.playOnAwake = true;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.15f, 0.3f);
            main.startSpeed = 0.2f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.06f, 0.12f);
            ParticleSystem.EmissionModule emission = ps.emission;
            emission.rateOverTime = 60f;
            ParticleSystem.ShapeModule shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.02f;
            Light(fire.transform, FlameOrange, 1f, 3f);
        }
        return Save(go);
    }

    /// <summary>A rebar bolt in flight: ribbed steel with bottle-plastic vanes, tip at the origin pointing +Z.</summary>
    private static string Bolt()
    {
        GameObject go = new GameObject("BoltFx");
        List<(Vector3, Vector3)> ribs = new List<(Vector3, Vector3)>
        {
            (new Vector3(0f, 0f, -0.5f), new Vector3(0.022f, 0.022f, 0.92f)),
            (new Vector3(0f, 0f, -0.03f), new Vector3(0.014f, 0.014f, 0.06f)),
        };
        for (int i = 0; i < 9; i++)
        {
            ribs.Add((new Vector3(0f, 0f, -0.15f - i * 0.08f), new Vector3(0.027f, 0.027f, 0.012f)));
        }
        Mesh rod = Boxes("BoltRodMesh", ribs.ToArray());
        Mesh vanes = Boxes("BoltVaneMesh", (new Vector3(0f, 0.028f, -0.88f), new Vector3(0.003f, 0.04f, 0.16f)),
            (new Vector3(0.024f, -0.016f, -0.88f), new Vector3(0.04f, 0.003f, 0.16f)),
            (new Vector3(-0.024f, -0.016f, -0.88f), new Vector3(0.04f, 0.003f, 0.16f)));
        MeshObject("Rod", go.transform, rod, Solid("BoltRust", new Color(0.3f, 0.17f, 0.1f), 0.6f, 0.3f));
        MeshObject("Vanes", go.transform, vanes, Solid("BoltVanes", new Color(0.15f, 0.42f, 0.2f), 0f, 0.5f));
        Trail(go, new Color(1f, 1f, 1f, 0.25f), 0.04f, 0.15f);
        return Save(go);
    }
}
