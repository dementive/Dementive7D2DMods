using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Turns the Blender trees in Assets/NatureExpanded/Trees/&lt;Species&gt;/ (blender/trees/*.py; see blender/TREES.md)
/// into tree prefabs drawn by the game's own SpeedTree shader, builds them into
/// Build/trees-bundle/natureexpanded-trees.unity3d, writes Build/tree-sizes.txt for gen_nature.py, and renders them
/// beside vanilla's own trees to Build/trees/. Run from src/build-trees.bat (batch mode with graphics).
///
/// Each variant's FBX has four meshes, Variant_LOD0 to _LOD3 (LOD3 the far impostor cards), with materials named
/// for the part: &lt;Species&gt;Bark (and BarkFoot, BarkTwig), &lt;Species&gt;Leaves, &lt;Variant&gt;Impostor, each with its
/// _Albedo/_Normal/_RMOM maps in the species folder. Laid out like vanilla's trees: the root (NatureTree&lt;Variant&gt;,
/// the name the mod's TreeShaderDEM looks for) on layer 23 carries the LODGroup (SpeedTree fading, cross-faded), the
/// meshes sit at the root with their origin on the ground (the block's ModelOffset drops it half a block, as
/// vanilla's), and children on layer 23 carry the collision: a chain of capsules along every trunk (trunks.txt), and
/// CollisionObject0's long capsule up the main trunk, switched off but read by the falling tree for its size.
///
/// The game's trees are SpeedTrees (Game/SpeedTree8, Unity's SpeedTree 8 shader renamed), and ours use a copy of
/// Unity's own (NatureExpanded/SpeedTree8, Assets/NatureExpanded/Shaders, built into the bundle with them: the same
/// shader plus the fade the game gives a felled tree) in its "palm" wind mode, set up like vanilla's oaks
/// (MakeMaterial); the mod feeds their materials the game's wind (SpeedTreeWindDEM). That shader reads
/// per-vertex data the SpeedTree Modeler normally writes; this writes it from the tree's shape, in the ranges vanilla's
/// own oaks use (NatureProbe.SpeedTreeData):
/// - uv0.zw: how far the vertex sways with its branch (0 at the trunk, about 0.45 at the crown's edge) and the
///   direction it sways, packed into one float (a smooth field, so a branch moves together and its neighbours don't);
/// - uv3: every vertex a "frond" (geometry type 1), leaf cards with a ripple scale growing from the card's middle to
///   its edges, so leaves flutter as vanilla's oak leaves do;
/// - uv2.xyz the vertex's own position (the SpeedTree LOD morph target: no morph), uv1.zw and uv2.w an anchor;
/// - color: ambient occlusion, darker deep in the crown (0.69 to 1, as vanilla's).
/// The shader draws both sides (_TwoSided 0, cull off), so nothing is doubled.
/// </summary>
public static class NatureTreeBuilder
{
    public const string BundleName = "natureexpanded-trees.unity3d";
    private const string Trees = "Assets/NatureExpanded/Trees";
    private const string Prefabs = "Assets/NatureExpanded/Prefabs";
    public const string Prefix = "NatureTree";
    public const string ShaderName = "NatureExpanded/SpeedTree8";
    // Screen heights where each LOD hands over (vanilla's SpeedTrees: .647, .455, .252, .051), then culled
    private static readonly float[] LodHeights = { 0.45f, 0.22f, 0.08f, 0.012f };
    // The corner of a leaf atlas (u, v below these) that holds bark decals, which don't flutter (TREES.md)
    private static readonly Vector2 DecalStrip = new Vector2(0.375f, 0.0625f);
    // Species scaled up from their Blender size to stand with vanilla's trees (its pine forest's run 12 to 48 m,
    // most of them 19 to 27): birches 15 m in Blender would read as saplings among them
    private static readonly Dictionary<string, float> Scales = new Dictionary<string, float> { ["Birch"] = 1.35f };

    private struct Info
    {
        public float Height, TrunkRadius, CrownRadius;
        // Each trunk's centre line from just under the ground up past the crown's start, (x, y, z, radius) in the
        // FBX meshes' own coordinates before the species' scale (Trees/trunks.txt, blender/trees treekit.write_trunks)
        public List<List<Vector4>> Trunks;
    }

    public static void Build()
    {
        PlayerSettings.colorSpace = ColorSpace.Linear;
        KeepShaderVariants();
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (!AssetDatabase.IsValidFolder(Prefabs))
        {
            AssetDatabase.CreateFolder("Assets/NatureExpanded", "Prefabs");
        }
        Dictionary<string, Info> info = ReadInfo();
        Dictionary<string, List<List<Vector4>>> trunks = ReadTrunks();
        List<string> prefabs = new List<string>();
        List<string> sizes = new List<string>();
        foreach (string dir in Directory.GetDirectories(Trees).OrderBy(d => d))
        {
            string folder = dir.Replace('\\', '/');
            foreach (string path in Directory.GetFiles(folder, "*.png"))
            {
                ConfigureTexture(path.Replace('\\', '/'));
            }
            foreach (string fbx in Directory.GetFiles(folder, "*.fbx").OrderBy(f => f))
            {
                string variant = Path.GetFileNameWithoutExtension(fbx);
                info.TryGetValue(variant, out Info i);
                float scale = Scales.TryGetValue(Path.GetFileName(folder), out float sc) ? sc : 1f;
                i.Height *= scale;
                i.TrunkRadius *= scale;
                i.CrownRadius *= scale;
                i.Trunks = trunks.TryGetValue(variant, out List<List<Vector4>> t) ? t : null;
                prefabs.Add(MakeTree(folder, variant, i, scale, sizes));
            }
        }
        AssetDatabase.SaveAssets();
        string output = Path.Combine(Directory.GetCurrentDirectory(), "Build");
        File.WriteAllLines(Path.Combine(output, "tree-sizes.txt"), sizes);
        string bundleDir = Path.Combine(output, "trees-bundle");
        Directory.CreateDirectory(bundleDir);
        AssetBundleBuild bundle = new AssetBundleBuild { assetBundleName = BundleName, assetNames = prefabs.ToArray() };
        if (BuildPipeline.BuildAssetBundles(bundleDir, new[] { bundle },
                BuildAssetBundleOptions.ChunkBasedCompression | BuildAssetBundleOptions.StrictMode | BuildAssetBundleOptions.ForceRebuildAssetBundle,
                BuildTarget.StandaloneWindows64) == null)
        {
            throw new System.Exception("Building " + BundleName + " failed; see the log above");
        }
        Debug.Log("[NatureTreeBuilder] Built " + BundleName + " with " + prefabs.Count + " trees");
        Previews(prefabs, Path.Combine(output, "trees"));
    }

    /// <summary>The bundle carries its own build of the SpeedTree shader, and Unity leaves out variants nothing in the
    /// project's scenes uses (this project has no scenes): keep every fog mode (the game fogs the world) and the
    /// instanced variants (the game batches trees), so ours draw like vanilla's.</summary>
    private static void KeepShaderVariants()
    {
        SerializedObject gs = new SerializedObject(UnityEngine.Rendering.GraphicsSettings.GetGraphicsSettings());
        gs.FindProperty("m_FogStripping").intValue = 1;
        gs.FindProperty("m_FogKeepLinear").boolValue = true;
        gs.FindProperty("m_FogKeepExp").boolValue = true;
        gs.FindProperty("m_FogKeepExp2").boolValue = true;
        gs.FindProperty("m_InstancingStripping").intValue = 1;
        gs.ApplyModifiedPropertiesWithoutUndo();
        AssetDatabase.SaveAssets();
    }

    /// <summary>trees.txt: "Variant height H trunk_radius R crown_radius C lean X Y" per line.</summary>
    private static Dictionary<string, Info> ReadInfo()
    {
        Dictionary<string, Info> info = new Dictionary<string, Info>();
        string path = Trees + "/trees.txt";
        if (!File.Exists(path))
        {
            return info;
        }
        foreach (string line in File.ReadAllLines(path))
        {
            string[] p = line.Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries);
            if (p.Length < 2 || line.StartsWith("#"))
            {
                continue;
            }
            float Value(string key)
            {
                int k = System.Array.IndexOf(p, key);
                return k >= 0 && k + 1 < p.Length ? float.Parse(p[k + 1], CultureInfo.InvariantCulture) : 0f;
            }
            info[p[0]] = new Info { Height = Value("height"), TrunkRadius = Value("trunk_radius"), CrownRadius = Value("crown_radius") };
        }
        return info;
    }

    /// <summary>trunks.txt: "Variant x y z r x y z r ..." per trunk (a clump's variant has a line for each).</summary>
    private static Dictionary<string, List<List<Vector4>>> ReadTrunks()
    {
        Dictionary<string, List<List<Vector4>>> trunks = new Dictionary<string, List<List<Vector4>>>();
        string path = Trees + "/trunks.txt";
        if (!File.Exists(path))
        {
            return trunks;
        }
        foreach (string line in File.ReadAllLines(path))
        {
            string[] p = line.Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries);
            if (p.Length < 9 || line.StartsWith("#"))
            {
                continue;
            }
            float F(int k) => float.Parse(p[k], CultureInfo.InvariantCulture);
            List<Vector4> trunk = new List<Vector4>();
            for (int k = 1; k + 3 < p.Length; k += 4)
            {
                trunk.Add(new Vector4(F(k), F(k + 1), F(k + 2), F(k + 3)));
            }
            if (!trunks.TryGetValue(p[0], out List<List<Vector4>> list))
            {
                trunks[p[0]] = list = new List<List<Vector4>>();
            }
            list.Add(trunk);
        }
        return trunks;
    }

    private static string MakeTree(string folder, string variant, Info info, float scale, List<string> sizes)
    {
        string fbx = folder + "/" + variant + ".fbx";
        ModelImporter model = (ModelImporter)AssetImporter.GetAtPath(fbx);
        model.globalScale = 1f;
        model.useFileScale = true;
        model.importNormals = ModelImporterNormals.Import;
        model.importTangents = ModelImporterTangents.CalculateMikk;
        model.animationType = ModelImporterAnimationType.None;
        model.importAnimation = false;
        model.importCameras = false;
        model.importLights = false;
        model.isReadable = true;
        // Imported only for their names, which say which part each submesh is
        model.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        model.materialLocation = ModelImporterMaterialLocation.InPrefab;
        model.SaveAndReimport();

        GameObject source = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
        string name = Prefix + variant;
        GameObject root = new GameObject(name) { layer = 23 };
        List<Renderer> lods = new List<Renderer>();
        int triangles = 0;
        Shape shape = null;
        // From Blender's coordinates (trunks.txt's) to the prefab's, as Baked moves LOD0's vertices
        Matrix4x4 toTree = Matrix4x4.identity;
        Vector3[] lod0 = null;
        for (int lod = 0; lod < 4; lod++)
        {
            MeshFilter f = source.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault(m => m.name == variant + "_LOD" + lod);
            if (f == null)
            {
                throw new System.Exception(fbx + " has no mesh " + variant + "_LOD" + lod);
            }
            if (lod == 0)
            {
                // The FBX importer turns Blender's right-handed z-up coordinates into the meshes' own as (-x, z, -y)
                Matrix4x4 fromBlender = new Matrix4x4(new Vector4(-1f, 0f, 0f, 0f), new Vector4(0f, 0f, -1f, 0f), new Vector4(0f, 1f, 0f, 0f),
                    new Vector4(0f, 0f, 0f, 1f));
                toTree = Matrix4x4.Scale(Vector3.one * scale) * source.transform.worldToLocalMatrix * f.transform.localToWorldMatrix * fromBlender;
            }
            string[] parts = f.GetComponent<MeshRenderer>().sharedMaterials.Select(m => m != null ? m.name : "").ToArray();
            Mesh mesh = Baked(f, source.transform, parts, info, scale, ref shape);
            AssetDatabase.DeleteAsset(Prefabs + "/" + name + "_LOD" + lod + ".asset");
            AssetDatabase.CreateAsset(mesh, Prefabs + "/" + name + "_LOD" + lod + ".asset");
            if (lod == 0)
            {
                triangles = mesh.triangles.Length / 3;
                lod0 = mesh.vertices;
            }
            GameObject part = new GameObject(variant + "_LOD" + lod);
            part.transform.SetParent(root.transform, false);
            part.AddComponent<MeshFilter>().sharedMesh = mesh;
            MeshRenderer r = part.AddComponent<MeshRenderer>();
            r.sharedMaterials = parts.Select(p => MakeMaterial(folder, p)).ToArray();
            r.shadowCastingMode = ShadowCastingMode.On;
            r.receiveShadows = true;
            lods.Add(r);
        }
        // As vanilla's SpeedTrees: SpeedTree fading, animated cross-fades between the levels. A small tree (a
        // seedling) fills less of the screen at the same distance, so it hands over at smaller heights, keeping each
        // level out to the distance a full tree keeps it
        float small = Mathf.Clamp(shape.Height / 10f, 0.25f, 1f);
        LODGroup group = root.AddComponent<LODGroup>();
        group.fadeMode = LODFadeMode.SpeedTree;
        group.animateCrossFading = true;
        group.SetLODs(lods.Select((r, i) => new LOD(LodHeights[i] * small, new[] { r })).ToArray());
        group.RecalculateBounds();

        // The trunks in the prefab's coordinates: points, and radii a hair inside the bark (a 12-sided tube's flat
        // faces lie 3.4% inside its corners), so the player meets the trunk where its bark is, never a wall in the air
        List<List<(Vector3 p, float r)>> lines = (info.Trunks ?? new List<List<Vector4>>())
            .Select(t => t.Select(q => (toTree.MultiplyPoint3x4(new Vector3(q.x, q.y, q.z)), q.w * scale * 0.95f)).ToList())
            .Where(t => t.Count >= 2).ToList();

        // The main trunk's capsule, from its base up and along its lean, three quarters of the tree's height: what the
        // falling tree goes by (EntityFallingTree sizes its own capsule from the tallest one, reading disabled ones
        // too). With the trunks' chains below it's switched off, as a straight capsule stands out of a bowed trunk;
        // it's all the collision there is without trunks.txt, and a seedling's (an easier target than its stem)
        GameObject col = new GameObject("CollisionObject0") { layer = 23 };
        col.transform.SetParent(root.transform, false);
        Vector3 bottom = shape.Base, toward = shape.TrunkMid;
        float radius = info.TrunkRadius > 0f ? info.TrunkRadius : 0.15f;
        if (lines.Count > 0)
        {
            List<(Vector3 p, float r)> main = lines[0];
            int ground = Mathf.Max(0, main.FindIndex(q => q.p.y >= 0f));
            bottom = main[ground].p;
            toward = main[main.Count - 1].p;
            radius = main.OrderBy(q => Mathf.Abs(q.p.y - 1.35f)).First().r;
        }
        col.transform.localRotation = Quaternion.FromToRotation(Vector3.up, (toward - bottom).normalized);
        col.transform.localPosition = bottom;
        CapsuleCollider capsule = col.AddComponent<CapsuleCollider>();
        capsule.direction = 1;
        capsule.radius = Mathf.Max(0.12f, radius);
        capsule.height = shape.Height * 0.75f;
        capsule.center = new Vector3(0f, capsule.height * 0.5f, 0f);
        bool chains = lines.Count > 0 && shape.Height >= 3f;
        capsule.enabled = !chains;
        if (!chains)
        {
            lines.Clear();
        }

        // Then every trunk's own chain of capsules along its centre line, a metre long where the player stands and
        // three above, up past where the crown starts: a clump's other trunks and a bowed trunk's curve are solid
        // too (vanilla's trees let you into their branches, never their trunks)
        int chain = 0;
        foreach (List<(Vector3 p, float r)> line in lines)
        {
            // A check that the line runs up the trunk's middle: the nearest bark to it 1 m up should be its radius off
            (Vector3 p, float r) knee = line.OrderBy(q => Mathf.Abs(q.p.y - 1.35f)).First();
            float nearest = lod0.Min(v => Vector3.Distance(v, knee.p));
            Debug.Log("[NatureTreeBuilder] " + name + " trunk at " + knee.p.ToString("F2") + ": nearest bark " + nearest.ToString("F2")
                + " m, capsule radius " + knee.r.ToString("F2"));
            for (int a = 0; a < line.Count - 1;)
            {
                float want = line[a].p.y < 3f ? 1f : 3f;
                int b = a + 1;
                float run = Vector3.Distance(line[a].p, line[b].p);
                while (b < line.Count - 1 && run < want)
                {
                    run += Vector3.Distance(line[b].p, line[b + 1].p);
                    b++;
                }
                Vector3 from = line[a].p, to = line[b].p;
                GameObject seg = new GameObject("CollisionObject" + (++chain)) { layer = 23 };
                seg.transform.SetParent(root.transform, false);
                seg.transform.localPosition = (from + to) * 0.5f;
                seg.transform.localRotation = Quaternion.FromToRotation(Vector3.up, (to - from).normalized);
                CapsuleCollider c = seg.AddComponent<CapsuleCollider>();
                c.direction = 1;
                c.radius = Mathf.Max(0.02f, line.Skip(a).Take(b - a + 1).Min(q => q.r));
                c.height = Vector3.Distance(from, to) + 2f * c.radius;
                a = b;
            }
        }

        int blocks = Mathf.Clamp(Mathf.CeilToInt(shape.Height), 1, 20);
        sizes.Add(variant + " " + blocks + " " + shape.Height.ToString("F1", CultureInfo.InvariantCulture) + " "
            + capsule.radius.ToString("F2", CultureInfo.InvariantCulture));
        Debug.Log("[NatureTreeBuilder] " + name + ": " + shape.Height.ToString("F1") + " m, " + triangles + " triangles at LOD0, crown "
            + shape.CrownCenter.ToString("F1") + " r " + shape.CrownRadius.ToString("F1") + ", trunk lean " + (toward - bottom).ToString("F2")
            + ", " + lines.Count + " trunks in " + chain + " capsules besides the main one");
        string prefab = Prefabs + "/" + name + ".prefab";
        PrefabUtility.SaveAsPrefabAsset(root, prefab);
        Object.DestroyImmediate(root);
        return prefab;
    }

    /// <summary>The tree's overall shape, measured once from its LOD0 and used for every LOD, so the levels sway and
    /// shade alike.</summary>
    private class Shape
    {
        public Vector3 Base, TrunkMid, CrownCenter;
        public float Height, CrownRadius, CrownHalfHeight;
    }

    private static Shape Measure(List<Vector3> v, bool[] leaf, Info info)
    {
        Shape s = new Shape { Height = info.Height > 0f ? info.Height : v.Max(p => p.y) };
        List<Vector3> bark = v.Where((p, i) => !leaf[i]).ToList();
        List<Vector3> leaves = v.Where((p, i) => leaf[i]).ToList();
        List<Vector3> low = bark.Where(p => p.y < 0.6f).ToList();
        s.Base = low.Count > 0 ? new Vector3(low.Average(p => p.x), 0f, low.Average(p => p.z)) : Vector3.zero;
        List<Vector3> mid = bark.Where(p => p.y > s.Height * 0.3f && p.y < s.Height * 0.45f
            && new Vector2(p.x - s.Base.x, p.z - s.Base.z).magnitude < 2.5f).ToList();
        s.TrunkMid = mid.Count > 0 ? new Vector3(mid.Average(p => p.x), mid.Average(p => p.y), mid.Average(p => p.z))
            : s.Base + new Vector3(0f, s.Height * 0.4f, 0f);
        List<Vector3> crown = leaves.Count > 0 ? leaves : bark;
        s.CrownCenter = new Vector3(crown.Average(p => p.x), crown.Average(p => p.y), crown.Average(p => p.z));
        s.CrownRadius = info.CrownRadius > 0f ? info.CrownRadius
            : Mathf.Max(0.5f, crown.Max(p => new Vector2(p.x - s.CrownCenter.x, p.z - s.CrownCenter.z).magnitude));
        s.CrownHalfHeight = Mathf.Max(0.5f, (crown.Max(p => p.y) - crown.Min(p => p.y)) * 0.5f);
        return s;
    }

    /// <summary>A copy of an imported mesh with its node's import transform baked in (origin on the ground) and
    /// SpeedTree's per-vertex wind and occlusion data written in (see the class summary).</summary>
    private static Mesh Baked(MeshFilter filter, Transform fbxRoot, string[] parts, Info info, float scale, ref Shape shape)
    {
        Matrix4x4 m = Matrix4x4.Scale(Vector3.one * scale) * fbxRoot.worldToLocalMatrix * filter.transform.localToWorldMatrix;
        Mesh src = filter.sharedMesh;
        List<Vector3> v = src.vertices.Select(x => m.MultiplyPoint3x4(x)).ToList();
        List<Vector3> n = src.normals.Select(x => m.MultiplyVector(x).normalized).ToList();
        List<Vector4> t = src.tangents.Select(x =>
        {
            Vector3 d = m.MultiplyVector(x).normalized;
            return new Vector4(d.x, d.y, d.z, x.w);
        }).ToList();
        Vector2[] uv = src.uv;

        // Which vertices are leaves (or impostor cards), and the cards they make: each card a connected patch
        bool[] leaf = new bool[v.Count];
        int[] card = Enumerable.Repeat(-1, v.Count).ToArray();
        int[] parent = Enumerable.Range(0, v.Count).ToArray();
        int Find(int i)
        {
            while (parent[i] != i)
            {
                parent[i] = parent[parent[i]];
                i = parent[i];
            }
            return i;
        }
        for (int sub = 0; sub < src.subMeshCount; sub++)
        {
            string part = sub < parts.Length ? parts[sub] : "";
            if (!(part.EndsWith("Leaves") || part.EndsWith("Impostor")))
            {
                continue;
            }
            int[] tris = src.GetTriangles(sub);
            for (int i = 0; i < tris.Length; i += 3)
            {
                for (int k = 0; k < 3; k++)
                {
                    leaf[tris[i + k]] = true;
                }
                parent[Find(tris[i + 1])] = Find(tris[i]);
                parent[Find(tris[i + 2])] = Find(tris[i]);
            }
        }
        // Decals on the bark (a birch's branch scars) share the leaves' cutout material but sit in the atlas's bottom
        // strip (TREES.md); they're bark as far as wind and the crown go
        for (int i = 0; i < v.Count; i++)
        {
            if (leaf[i] && i < uv.Length && uv[i].x < DecalStrip.x && uv[i].y < DecalStrip.y)
            {
                leaf[i] = false;
            }
        }
        Dictionary<int, (Vector3 center, float reach)> cards = new Dictionary<int, (Vector3, float)>();
        foreach (IGrouping<int, int> g in Enumerable.Range(0, v.Count).Where(i => leaf[i]).GroupBy(Find))
        {
            Vector3 c = g.Aggregate(Vector3.zero, (a, i) => a + v[i]) / g.Count();
            cards[g.Key] = (c, Mathf.Max(0.01f, g.Max(i => (v[i] - c).magnitude)));
            foreach (int i in g)
            {
                card[i] = g.Key;
            }
        }
        if (shape == null)
        {
            shape = Measure(v, leaf, info);
        }

        List<Vector4> uv0 = new List<Vector4>(), uv1 = new List<Vector4>(), uv2 = new List<Vector4>(), uv3 = new List<Vector4>();
        List<Color> colors = new List<Color>();
        for (int i = 0; i < v.Count; i++)
        {
            Vector3 p = v[i];
            float out01 = Mathf.Clamp01(new Vector2(p.x - shape.Base.x, p.z - shape.Base.z).magnitude / shape.CrownRadius);
            float up01 = Mathf.Clamp01(p.y / (shape.Height * 0.3f));
            float weight = Mathf.Clamp01(0.46f * Mathf.Pow(out01, 0.8f) * up01 + 0.06f * Mathf.Clamp01(p.y / shape.Height) + (leaf[i] ? 0.04f : 0f));
            Vector3 anchor = card[i] >= 0 ? cards[card[i]].center : p;
            float ripple = card[i] >= 0 ? Mathf.Clamp01((p - cards[card[i]].center).magnitude / cards[card[i]].reach) * 0.6f : 0f;
            // Ambient occlusion: dark deep in the crown, light at its surface and on the open trunk below it
            Vector3 d = p - shape.CrownCenter;
            float depth = Mathf.Clamp01(new Vector3(d.x / shape.CrownRadius, d.y / shape.CrownHalfHeight, d.z / shape.CrownRadius).magnitude);
            float below = Mathf.Clamp01((shape.CrownCenter.y - shape.CrownHalfHeight - p.y) / 2f);
            float ao = Mathf.Lerp(leaf[i] ? 0.69f : 0.72f, 1f, Mathf.Max(Mathf.Pow(depth, 1.2f), below * 0.9f));
            uv0.Add(new Vector4(uv.Length > i ? uv[i].x : 0f, uv.Length > i ? uv[i].y : 0f, weight, Pack(SwayDirection(p))));
            uv1.Add(new Vector4(0f, 0f, anchor.x, anchor.y));
            uv2.Add(new Vector4(p.x, p.y, p.z, anchor.z));
            uv3.Add(new Vector4(0f, ripple, 0f, 1f));
            colors.Add(new Color(ao, ao, ao, 1f));
        }

        Mesh mesh = new Mesh { name = filter.name };
        mesh.indexFormat = v.Count > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
        mesh.SetVertices(v);
        mesh.SetNormals(n);
        if (t.Count == v.Count)
        {
            mesh.SetTangents(t);
        }
        mesh.SetUVs(0, uv0);
        mesh.SetUVs(1, uv1);
        mesh.SetUVs(2, uv2);
        mesh.SetUVs(3, uv3);
        mesh.SetColors(colors);
        mesh.subMeshCount = src.subMeshCount;
        for (int sub = 0; sub < src.subMeshCount; sub++)
        {
            mesh.SetTriangles(src.GetTriangles(sub), sub);
        }
        mesh.RecalculateBounds();
        mesh.UploadMeshData(false);
        return mesh;
    }

    /// <summary>The direction a point sways with its branch: a smooth field over the tree, so one branch moves as a
    /// piece and its neighbours move differently.</summary>
    private static Vector3 SwayDirection(Vector3 p)
    {
        return new Vector3(Mathf.Sin(1.3f * p.x + 0.7f * p.z + 1.1f), Mathf.Sin(0.9f * p.y + 1.7f * p.x + 2.3f),
            Mathf.Sin(1.1f * p.z + 0.6f * p.y + 0.4f)).normalized;
    }

    /// <summary>SpeedTree's packing of a direction into one float, the inverse of UnpackNormalFromFloat
    /// (SpeedTreeWind.cginc): x and y to sixteenths in the whole and first fractional digits, z in the rest.</summary>
    public static float Pack(Vector3 dir)
    {
        Vector3 u = dir.normalized * 0.5f + new Vector3(0.5f, 0.5f, 0.5f);
        float qx = Mathf.Round(u.x * 15f) / 16f, qy = Mathf.Round(u.y * 15f) / 16f;
        return 16f * qx + qy + Mathf.Clamp(u.z, 0f, 0.999f) / 16f;
    }

    private static void ConfigureTexture(string path)
    {
        bool albedo = path.EndsWith("_Albedo.png"), normal = path.EndsWith("_Normal.png"), rmom = path.EndsWith("_RMOM.png");
        if (!(albedo || normal || rmom))
        {
            return;
        }
        string file = Path.GetFileNameWithoutExtension(path);
        bool cutout = albedo && (file.Contains("Leaves") || file.Contains("Impostor"));
        bool bark = file.Contains("Bark");
        TextureImporter ti = (TextureImporter)AssetImporter.GetAtPath(path);
        ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
        ti.sRGBTexture = albedo;
        ti.alphaSource = cutout || rmom ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
        // Spreads the leaves' colour into the cut-away parts, so far mips don't fade them to a dark fringe
        ti.alphaIsTransparency = cutout;
        ti.mipmapEnabled = true;
        ti.mipMapsPreserveCoverage = cutout;
        ti.alphaTestReferenceValue = 0.5f;
        ti.wrapMode = bark ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
        // Bark is seen up close and along the trunk: full size (a birch's is 2048 x 4096) and sharp at a slant
        ti.anisoLevel = bark ? 8 : 2;
        ti.maxTextureSize = bark ? 4096 : 2048;
        ti.textureCompression = TextureImporterCompression.Compressed;
        ti.SaveAndReimport();
    }

    /// <summary>A part's material in our copy of Unity's SpeedTree 8 shader (the game's Game/SpeedTree8 is that
    /// shader renamed, with a few tweaks; ours adds the felled tree's fade), set up like vanilla's oaks: normal mapped,
    /// "palm" wind, both sides drawn, smoothness, metallic and occlusion from the extra map (SMO) times the vertex
    /// colours' occlusion. Built into the bundle (with the shader) as an ordinary asset, it loads with its maps like
    /// any other; materials made at runtime from a vanilla one drew magenta in game. Shared by every variant that uses
    /// the part.</summary>
    private static Material MakeMaterial(string folder, string part)
    {
        Shader shader = Shader.Find(ShaderName);
        if (shader == null)
        {
            throw new System.Exception("The shader " + ShaderName + " (Assets/NatureExpanded/Shaders) didn't import");
        }
        string path = Prefabs + "/" + part + ".mat";
        Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (material == null)
        {
            material = new Material(shader);
            AssetDatabase.CreateAsset(material, path);
        }
        material.shader = shader;
        material.shaderKeywords = new string[0];
        material.name = part;
        Texture2D Tex(string suffix) => AssetDatabase.LoadAssetAtPath<Texture2D>(folder + "/" + part + "_" + suffix + ".png");
        if (Tex("Albedo") == null)
        {
            throw new System.Exception("No " + folder + "/" + part + "_Albedo.png for the material " + part);
        }
        material.SetTexture("_MainTex", Tex("Albedo"));
        material.SetTexture("_BumpMap", Tex("Normal"));
        Texture2D smo = Smo(folder, part);
        material.SetTexture("_ExtraTex", smo);
        material.SetColor("_Color", Color.white);
        foreach ((string name, float value) in new[] { ("_Glossiness", 0.1f), ("_Metallic", 0f), ("_NormalMapKwToggle", 1f), ("_WindQuality", 5f),
                     ("_TwoSided", 0f), ("_BillboardKwToggle", 0f), ("_HueVariationKwToggle", 0f), ("_SubsurfaceKwToggle", 0f), ("_FadeOut", 1f) })
        {
            if (material.HasProperty(name))
            {
                material.SetFloat(name, value);
            }
        }
        material.EnableKeyword("EFFECT_BUMP");
        material.EnableKeyword("_WINDQUALITY_PALM");
        // Bark reads its smoothness and occlusion from the extra map. Leaves and impostors don't, as vanilla's tree
        // materials don't (no EFFECT_EXTRA_TEX): their flat 0.1 smoothness keeps them matte, where the leaf maps'
        // 0.55 or so mirrored the sky and turned the crowns blue-grey
        if (smo != null && part.Contains("Bark"))
        {
            material.EnableKeyword("EFFECT_EXTRA_TEX");
        }
        material.renderQueue = 2450;
        material.enableInstancing = true;
        EditorUtility.SetDirty(material);
        return material;
    }

    /// <summary>SpeedTree's "extra" map (red smoothness, green metallic, blue occlusion) from our RMOM map (red
    /// roughness, green metallic, blue occlusion), as a texture of its own in Prefabs.</summary>
    private static Texture2D Smo(string folder, string part)
    {
        string path = Prefabs + "/" + part + "_SMO.png";
        string rmom = folder + "/" + part + "_RMOM.png";
        if (!File.Exists(rmom))
        {
            return null;
        }
        Texture2D src = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        src.LoadImage(File.ReadAllBytes(rmom));
        Color32[] px = src.GetPixels32();
        for (int i = 0; i < px.Length; i++)
        {
            px[i] = new Color32((byte)(255 - px[i].r), px[i].g, px[i].b, 255);
        }
        src.SetPixels32(px);
        File.WriteAllBytes(path, src.EncodeToPNG());
        Object.DestroyImmediate(src);
        AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
        TextureImporter ti = (TextureImporter)AssetImporter.GetAtPath(path);
        ti.sRGBTexture = false;
        ti.wrapMode = part.Contains("Bark") ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
        ti.anisoLevel = part.Contains("Bark") ? 8 : 2;
        ti.maxTextureSize = part.Contains("Bark") ? 2048 : 1024;
        ti.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    // ------------------------------------------------------------------ previews

    /// <summary>For each tree, in the game's SpeedTree shader: whole beside vanilla's mountain pine and small oak
    /// (the SpeedTrees it grows among), its four LODs in a row, and its bark from a few metres and from an arm's length (the
    /// trunk's foot meeting its white bark), the game's fade, the whole tree framed and its collision capsules (_colliders,
    /// red); then a grove of all of
    /// them mixed with vanilla pines from 70 m. Wind is still, as it is outside the game.</summary>
    private static void Previews(List<string> prefabs, string output)
    {
        Directory.CreateDirectory(output);
        string game = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "../../../.."));
        string addressables = Path.Combine(game, "Data/Addressables/Standalone");
        List<AssetBundle> loaded = new[] { "7c401d1245288cd4ca6169241e1a104c_unitybuiltinshaders.bundle", "shaders_assets_all.bundle" }
            .Select(b => AssetBundle.LoadFromFile(Path.Combine(addressables, b))).Where(b => b != null).ToList();
        AssetBundle trees = AssetBundle.LoadFromFile(Path.Combine(game, "Data/Bundles/Standalone/Entities/trees"));
        try
        {
            GameObject Vanilla(string end) => trees.LoadAsset<GameObject>(trees.GetAllAssetNames().First(n => n.ToLowerInvariant().EndsWith(end)));
            GameObject pine = Vanilla("mountainpinemed01gimbalprefab.prefab"), oak = Vanilla("oaksml01gimbalprefab.prefab");
            GameObject Spawn(string prefab, Vector3 at, float turn)
            {
                // The bundle's own materials, as the game loads them
                GameObject go = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(prefab));
                // In game the block's ModelOffset puts the tree's base on the block's floor, the stage's ground
                go.transform.position = at + new Vector3(0f, -0.5f, 0f);
                go.transform.rotation = Quaternion.Euler(0f, turn, 0f);
                return go;
            }
            GameObject Place(GameObject vanilla, Vector3 at, float turn)
            {
                return Object.Instantiate(vanilla, at + new Vector3(0f, -0.5f, 0f), Quaternion.Euler(0f, turn, 0f));
            }

            foreach (string prefab in prefabs)
            {
                string name = Path.GetFileNameWithoutExtension(prefab).Substring(Prefix.Length);
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                NatureBuilder.Stage(160f);
                GameObject tree = Spawn(prefab, Vector3.zero, 0f);
                float h = Mathf.Max(4f, tree.GetComponentInChildren<MeshRenderer>().bounds.size.y);
                Place(pine, new Vector3(-14f, 0f, 4f), 40f);
                Place(oak, new Vector3(12f, 0f, 3f), 0f);
                const int width = 1600, height = 900;
                Save(NatureBuilder.Shot(new Vector3(4f, 6f, -46f), new Vector3(0f, 9f, 0f), 42f, width, height), output, name + ".png");
                Save(NatureBuilder.Shot(new Vector3(-3f, 2f, -18f), new Vector3(0f, h * 0.55f, 0f), 55f, width, height), output, name + "_near.png");
                // Its LODs in a row, near to far detail, and the bark close up
                Object.DestroyImmediate(tree);
                for (int lod = 0; lod < 4; lod++)
                {
                    GameObject copy = Spawn(prefab, new Vector3(-21f + lod * 14f, 0f, 40f), 30f);
                    copy.GetComponent<LODGroup>().ForceLOD(lod);
                }
                Save(NatureBuilder.Shot(new Vector3(0f, 8f, -16f), new Vector3(0f, h * 0.45f, 40f), 50f, width, height), output, name + "_lods.png");
                Spawn(prefab, new Vector3(0f, 0f, -60f), 200f).GetComponent<LODGroup>().ForceLOD(0);
                Save(NatureBuilder.Shot(new Vector3(0.4f, 1.6f, -63.2f), new Vector3(0f, 1.8f, -60f), 50f, 1000, 900), output, name + "_bark.png");
                // As the player sees it walking up: an arm's length off, the foot changing to the white bark
                Save(NatureBuilder.Shot(new Vector3(0.35f, 1.55f, -61.25f), new Vector3(0f, 1.15f, -60f), 55f, 1000, 900), output, name + "_bark_close.png");
                // The game's fade on a felled tree (EntityFallingTree turns on ENABLE_FADEOUT and runs _FadeOut down to
                // 0): whole, two thirds and a third left
                for (int k = 0; k < 3; k++)
                {
                    GameObject faded = Spawn(prefab, new Vector3(-14f + k * 14f, 0f, 120f), 0f);
                    faded.GetComponent<LODGroup>().ForceLOD(0);
                    foreach (MeshRenderer r in faded.GetComponentsInChildren<MeshRenderer>())
                    {
                        r.sharedMaterials = r.sharedMaterials.Select(m =>
                        {
                            Material copy = new Material(m);
                            copy.EnableKeyword("ENABLE_FADEOUT");
                            copy.SetFloat("_FadeOut", 1f - k / 3f);
                            return copy;
                        }).ToArray();
                    }
                }
                Save(NatureBuilder.Shot(new Vector3(0f, 9f, 80f), new Vector3(0f, 9f, 120f), 60f, width, height), output, name + "_fade.png");
                // The whole tree filling the frame, whatever its size (a seedling is lost in the other shots)
                GameObject whole = Spawn(prefab, new Vector3(0f, 0f, 160f), 30f);
                whole.GetComponent<LODGroup>().ForceLOD(0);
                float th = whole.GetComponentInChildren<MeshRenderer>().bounds.size.y;
                Save(NatureBuilder.Shot(new Vector3(th * 0.25f, -0.5f + th * 0.6f, 160f - th * 1.7f - 0.6f), new Vector3(0f, -0.5f + th * 0.5f, 160f),
                    50f, 1000, 900), output, name + "_whole.png");
                // Its enabled collision capsules in red: over the tree on the left (red showing means a capsule stands
                // out of the bark, a wall in the air), alone on the right (where the trunks are, the capsules must be)
                Material red = new Material(Shader.Find("Standard")) { color = new Color(0.85f, 0.1f, 0.08f) };
                float lower = Mathf.Min(th, 10f);
                for (int k = 0; k < 2; k++)
                {
                    Vector3 at = new Vector3((k == 0 ? -1f : 1f) * (lower * 0.3f + 0.6f), 0f, 240f);
                    GameObject host = Spawn(prefab, at, 30f);
                    host.GetComponent<LODGroup>().ForceLOD(0);
                    foreach (CapsuleCollider c in host.GetComponentsInChildren<CapsuleCollider>().Where(c => c.enabled))
                    {
                        GameObject g = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                        Object.DestroyImmediate(g.GetComponent<Collider>());
                        g.GetComponent<MeshRenderer>().sharedMaterial = red;
                        g.transform.SetParent(c.transform, false);
                        g.transform.localPosition = c.center;
                        g.transform.localScale = new Vector3(c.radius * 2f, c.height * 0.5f, c.radius * 2f);
                    }
                    if (k == 1)
                    {
                        foreach (MeshRenderer r in host.GetComponentsInChildren<MeshRenderer>().Where(r => r.sharedMaterial != red))
                        {
                            r.enabled = false;
                        }
                    }
                }
                Save(NatureBuilder.Shot(new Vector3(0f, -0.5f + lower * 0.45f, 240f - lower * 1.3f - 1.5f), new Vector3(0f, -0.5f + lower * 0.4f, 240f),
                    55f, 1200, 900), output, name + "_colliders.png");
            }

            // A grove: the new trees at random among vanilla pines and oaks, from a way off and from inside it
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            NatureBuilder.Stage(220f);
            System.Random rnd = new System.Random(7);
            for (int i = 0; i < 40; i++)
            {
                Vector3 at = new Vector3((float)rnd.NextDouble() * 70f - 35f, 0f, (float)rnd.NextDouble() * 60f);
                float turn = (float)rnd.NextDouble() * 360f;
                double pick = rnd.NextDouble();
                if (pick < 0.25)
                {
                    Place(pine, at, turn);
                }
                else if (pick < 0.35)
                {
                    Place(oak, at, turn);
                }
                else
                {
                    Spawn(prefabs[rnd.Next(prefabs.Count)], at, turn);
                }
            }
            Save(NatureBuilder.Shot(new Vector3(10f, 12f, -70f), new Vector3(0f, 8f, 25f), 45f, 1600, 900), output, "grove.png");
            Save(NatureBuilder.Shot(new Vector3(-2f, 1.7f, 18f), new Vector3(6f, 7f, 40f), 60f, 1600, 900), output, "grove_inside.png");
        }
        finally
        {
            trees.Unload(true);
            foreach (AssetBundle b in loaded)
            {
                b.Unload(true);
            }
        }
    }

    private static void Save(Texture2D shot, string output, string file)
    {
        File.WriteAllBytes(Path.Combine(output, file), shot.EncodeToPNG());
        Object.DestroyImmediate(shot);
        Debug.Log("[NatureTreeBuilder] Wrote " + file);
    }
}
