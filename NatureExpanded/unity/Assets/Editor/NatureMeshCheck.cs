using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Finds loose pieces floating in the plants' meshes: parts (connected by shared vertex positions) that touch no
/// other part and hang above the ground, like a flower head or berry that missed its stalk. Reads the built meshes in
/// Assets/NatureExpanded/Prefabs (run src/build-bundle.bat first) and writes Build/floaters.txt: per plant and LOD, each
/// floating piece's size, height and the gap to its nearest neighbour.
/// Run: Unity -batchmode -quit -projectPath unity -executeMethod NatureMeshCheck.Floaters
/// </summary>
public static class NatureMeshCheck
{
    public static void Floaters()
    {
        StringBuilder sb = new StringBuilder();
        foreach (string path in Directory.GetFiles("Assets/NatureExpanded/Prefabs", "*.asset").OrderBy(p => p))
        {
            Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(path.Replace('\\', '/'));
            if (mesh == null || !mesh.isReadable)
            {
                continue;
            }
            List<(float gap, int[] verts, Bounds b)> found = Find(mesh.vertices, mesh.triangles, 0.012f, 0.03f);
            int slivers = Slivers(mesh.vertices, mesh.triangles).Count;
            if (found.Count == 0 && slivers == 0)
            {
                continue;
            }
            sb.AppendLine(mesh.name + ": " + found.Count + " floating pieces, " + found.Count(f => f.gap > 0.03f) + " over 3 cm; "
                + slivers + " slivers of " + mesh.triangles.Length / 3 + " triangles");
            foreach ((float gap, int[] verts, Bounds b) in found.OrderByDescending(f => f.gap).Take(8))
            {
                sb.AppendLine(string.Format("    gap {0:F3} m, {1} verts, size {2}, at {3}", gap, verts.Length, b.size.ToString("F3"), b.center.ToString("F2")));
            }
        }
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "Build", "floaters.txt"), sb.ToString());
    }

    /// <summary>The triangles left after taking out pieces floating more than `gap` clear of everything else (a
    /// flower, berry or leaf whose stalk the far LOD dropped, or that missed it), and how many pieces that was.</summary>
    public static int[] WithoutFloaters(Vector3[] v, int[] tris, float gap, out int removed)
    {
        HashSet<int> drop = new HashSet<int>();
        removed = 0;
        foreach ((float g, int[] verts, Bounds _) in Find(v, tris, 0.012f, 0.03f))
        {
            if (g > gap)
            {
                removed++;
                drop.UnionWith(verts);
            }
        }
        if (removed == 0)
        {
            return tris;
        }
        List<int> kept = new List<int>(tris.Length);
        for (int i = 0; i < tris.Length; i += 3)
        {
            if (!drop.Contains(tris[i]))
            {
                kept.Add(tris[i]);
                kept.Add(tris[i + 1]);
                kept.Add(tris[i + 2]);
            }
        }
        return kept.ToArray();
    }

    /// <summary>Triangles that are needles: longer than 2 cm and under half a millimetre across (what a decimated
    /// thin stem or petal collapses to), drawn as hairlines.</summary>
    public static List<int> Slivers(Vector3[] v, int[] tris)
    {
        List<int> slivers = new List<int>();
        for (int i = 0; i < tris.Length; i += 3)
        {
            Vector3 a = v[tris[i]], b = v[tris[i + 1]], c = v[tris[i + 2]];
            float longest = Mathf.Max((b - a).magnitude, (c - b).magnitude, (a - c).magnitude);
            float area2 = Vector3.Cross(b - a, c - a).magnitude;
            if (longest > 0.02f && area2 / longest < 0.0005f)
            {
                slivers.Add(i);
            }
        }
        return slivers;
    }

    /// <summary>Pieces whose nearest other piece is more than `touch` away and whose lowest point is above
    /// `ground` (the meshes stand on y 0): each with that gap, its vertices and its bounds.</summary>
    public static List<(float, int[], Bounds)> Find(Vector3[] v, int[] tris, float touch, float ground)
    {
        // Weld by position (0.5 mm), then join each triangle's corners
        int[] parent = Enumerable.Range(0, v.Length).ToArray();
        int Root(int i)
        {
            while (parent[i] != i)
            {
                parent[i] = parent[parent[i]];
                i = parent[i];
            }
            return i;
        }
        void Join(int a, int b) => parent[Root(a)] = Root(b);
        Dictionary<Vector3Int, int> weld = new Dictionary<Vector3Int, int>();
        for (int i = 0; i < v.Length; i++)
        {
            Vector3Int k = Vector3Int.RoundToInt(v[i] * 2000f);
            if (weld.TryGetValue(k, out int j))
            {
                Join(i, j);
            }
            else
            {
                weld[k] = i;
            }
        }
        for (int i = 0; i < tris.Length; i += 3)
        {
            Join(tris[i], tris[i + 1]);
            Join(tris[i], tris[i + 2]);
        }
        // Each triangle in every grid cell its box (grown by `touch`) overlaps, so a vertex finds the surfaces near it
        const float cell = 0.05f;
        Dictionary<Vector3Int, List<int>> grid = new Dictionary<Vector3Int, List<int>>();
        for (int t = 0; t < tris.Length; t += 3)
        {
            Vector3 a = v[tris[t]], b = v[tris[t + 1]], c = v[tris[t + 2]];
            Vector3Int lo = Vector3Int.FloorToInt((Vector3.Min(a, Vector3.Min(b, c)) - Vector3.one * touch) / cell);
            Vector3Int hi = Vector3Int.FloorToInt((Vector3.Max(a, Vector3.Max(b, c)) + Vector3.one * touch) / cell);
            for (int x = lo.x; x <= hi.x; x++)
            for (int y = lo.y; y <= hi.y; y++)
            for (int z = lo.z; z <= hi.z; z++)
            {
                Vector3Int k = new Vector3Int(x, y, z);
                if (!grid.TryGetValue(k, out List<int> l))
                {
                    grid[k] = l = new List<int>();
                }
                l.Add(t);
            }
        }
        List<(float, int[], Bounds)> found = new List<(float, int[], Bounds)>();
        foreach (IGrouping<int, int> piece in Enumerable.Range(0, v.Length).GroupBy(Root))
        {
            int[] idx = piece.ToArray();
            Bounds bounds = new Bounds(v[idx[0]], Vector3.zero);
            foreach (int i in idx)
            {
                bounds.Encapsulate(v[i]);
            }
            if (bounds.min.y < ground)
            {
                continue;
            }
            // The nearest surface of any other piece to any of this piece's vertices
            float gap = float.MaxValue;
            foreach (int i in idx)
            {
                if (!grid.TryGetValue(Vector3Int.FloorToInt(v[i] / cell), out List<int> l))
                {
                    continue;
                }
                foreach (int t in l)
                {
                    if (Root(tris[t]) == piece.Key)
                    {
                        continue;
                    }
                    gap = Mathf.Min(gap, (Closest(v[i], v[tris[t]], v[tris[t + 1]], v[tris[t + 2]]) - v[i]).magnitude);
                }
                if (gap < touch)
                {
                    break;
                }
            }
            if (gap >= touch)
            {
                found.Add((gap == float.MaxValue ? cell : gap, idx, bounds));
            }
        }
        return found;
    }

    /// <summary>The point of triangle abc nearest p (Ericson, Real-Time Collision Detection 5.1.5).</summary>
    private static Vector3 Closest(Vector3 p, Vector3 a, Vector3 b, Vector3 c)
    {
        Vector3 ab = b - a, ac = c - a, ap = p - a;
        float d1 = Vector3.Dot(ab, ap), d2 = Vector3.Dot(ac, ap);
        if (d1 <= 0f && d2 <= 0f) return a;
        Vector3 bp = p - b;
        float d3 = Vector3.Dot(ab, bp), d4 = Vector3.Dot(ac, bp);
        if (d3 >= 0f && d4 <= d3) return b;
        float vc = d1 * d4 - d3 * d2;
        if (vc <= 0f && d1 >= 0f && d3 <= 0f) return a + ab * (d1 / (d1 - d3));
        Vector3 cp = p - c;
        float d5 = Vector3.Dot(ab, cp), d6 = Vector3.Dot(ac, cp);
        if (d6 >= 0f && d5 <= d6) return c;
        float vb = d5 * d2 - d1 * d6;
        if (vb <= 0f && d2 >= 0f && d6 <= 0f) return a + ac * (d2 / (d2 - d6));
        float va = d3 * d6 - d5 * d4;
        if (va <= 0f && d4 - d3 >= 0f && d5 - d6 >= 0f) return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)));
        float denom = 1f / (va + vb + vc);
        return a + ab * (vb * denom) + ac * (vc * denom);
    }
}
