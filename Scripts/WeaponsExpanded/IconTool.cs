// Usage:
//   IconTool.exe <in.png> <out.png> <#RRGGBB> [strength 0..1]
//     Recolors a vanilla item icon toward a theme color while keeping its shading (a gradient map from black through
//     the color to a light tint of it, blended with the original), like the 2026 WeaponsExpanded icons.
//   IconTool.exe fx <in.png> <out.png> <op> [<op> ...]
//     Runs a chain of effects on a vanilla icon, for icons in the style of the hand-made WeaponsExpanded ones
//     (paint jobs, decals, glows). Each op is "name:arg,arg,key=value,..." (see the Op* methods below):
//       map:#dark,#mid,#light[,strength][,zone=...]   gradient map by brightness (gold, chrome, leather, ...)
//       pattern:<type>,c1=#..,c2=#..,c3=#..,op=1,scale=24,seed=1,angle=45,zone=...,bloom=0,shade=1
//         types: stripes, hazard, flames, camo, plaid, cracks, splatter, speckle, circuit, woodgrain
//       glow:#color,radius,strength[,noise=scale]       outer glow behind the item
//       rim:#color,width,strength                        light along the inside of the silhouette
//       emissive:#color,threshold,strength[,zone=...]    bright parts glow (with bloom)
//       sheen:strength                                   polished metal contrast and highlights
//       sparkle:#color,count,size,seed                   star glints on the brightest spots
//       embers:#color,count,size,seed[,zone=...]         glowing specks around the item
//       trail:#color,angle,count,spacing,strength        fading afterimages behind an item moving toward "angle"
//       adjust:sat=1,bright=1,contrast=1
//       bloom:radius,strength                            how far emissive light spreads (default 4,1)
//     zone=angle/start/end limits an op to part of the item: positions along the direction "angle" (degrees, 0 =
//     right, 90 = up) are scaled 0..1 across the item, and the op fades in from start to end. A negative start
//     flips it, so zone=45/-0.6/0.7 covers everything up to 0.6 and fades out by 0.7. Five values make a band:
//     zone=45/0.4/0.45/0.6/0.65 fades in from 0.4 to 0.45 and out from 0.6 to 0.65.
//   IconTool.exe sheet <out.png> <in1.png> <in2.png> ...
//     Lays icons side by side for review.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.Runtime.InteropServices;

class IconTool
{
    static void Main(string[] args)
    {
        if (args[0] == "sheet") { Sheet(args); return; }
        if (args[0] == "fx") { new Fx(args[1]).Run(args, 3).Save(args[2]); return; }
        Tint(args);
    }

    static void Sheet(string[] args)
    {
        const int size = 160;
        using (var sheet = new Bitmap(size * (args.Length - 2), size, PixelFormat.Format32bppArgb))
        using (var g = Graphics.FromImage(sheet))
        {
            g.Clear(Color.FromArgb(255, 45, 45, 45));
            for (int i = 2; i < args.Length; i++)
                using (var img = Image.FromFile(args[i]))
                    g.DrawImage(img, (i - 2) * size, 0, size, size);
            sheet.Save(args[1], ImageFormat.Png);
        }
    }

    static void Tint(string[] args)
    {
        Color theme = ColorTranslator.FromHtml(args[2]);
        double strength = args.Length > 3 ? double.Parse(args[3], CultureInfo.InvariantCulture) : 0.8;
        double tr = theme.R / 255.0, tg = theme.G / 255.0, tb = theme.B / 255.0;

        using (var src = new Bitmap(args[0]))
        using (var dst = new Bitmap(src.Width, src.Height, PixelFormat.Format32bppArgb))
        {
            for (int y = 0; y < src.Height; y++)
            for (int x = 0; x < src.Width; x++)
            {
                Color c = src.GetPixel(x, y);
                if (c.A == 0) { dst.SetPixel(x, y, c); continue; }
                double r = c.R / 255.0, gr = c.G / 255.0, b = c.B / 255.0;
                double lum = 0.299 * r + 0.587 * gr + 0.114 * b;
                // Slight contrast boost so the metal still reads after recoloring
                lum = Math.Min(1, Math.Max(0, (lum - 0.5) * 1.15 + 0.5));
                double mr, mg, mb;
                if (lum < 0.55)
                {
                    double t = lum / 0.55;
                    mr = tr * t; mg = tg * t; mb = tb * t;
                }
                else
                {
                    double t = (lum - 0.55) / 0.45;
                    mr = tr + (1 - tr) * t * 0.7; mg = tg + (1 - tg) * t * 0.7; mb = tb + (1 - tb) * t * 0.7;
                }
                int nr = Clamp((r * (1 - strength) + mr * strength) * 255);
                int ng = Clamp((gr * (1 - strength) + mg * strength) * 255);
                int nb = Clamp((b * (1 - strength) + mb * strength) * 255);
                dst.SetPixel(x, y, Color.FromArgb(c.A, nr, ng, nb));
            }
            dst.Save(args[1], ImageFormat.Png);
        }
    }

    static int Clamp(double v) => (int)Math.Round(Math.Min(255, Math.Max(0, v)));
}

class Fx
{
    readonly int W, H;
    readonly float[] R, G, B, A;          // the item, straight (not premultiplied) color
    readonly float[] Mask;                // the original silhouette
    readonly float[] GR, GG, GB, GA;      // glow behind the item, straight color
    readonly float[] ER, EG, EB;          // emissive light, bloomed and added on top
    float bloomRadius = 4, bloomStrength = 1;
    // Item bounds, for zones and patterns
    int minX, minY, maxX, maxY;

    public Fx(string path)
    {
        using (var src = new Bitmap(path))
        {
            W = src.Width; H = src.Height;
            int n = W * H;
            R = new float[n]; G = new float[n]; B = new float[n]; A = new float[n]; Mask = new float[n];
            GR = new float[n]; GG = new float[n]; GB = new float[n]; GA = new float[n];
            ER = new float[n]; EG = new float[n]; EB = new float[n];
            var data = src.LockBits(new Rectangle(0, 0, W, H), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            var bytes = new byte[n * 4];
            Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);
            src.UnlockBits(data);
            minX = W; minY = H; maxX = 0; maxY = 0;
            for (int i = 0; i < n; i++)
            {
                B[i] = bytes[i * 4] / 255f; G[i] = bytes[i * 4 + 1] / 255f; R[i] = bytes[i * 4 + 2] / 255f;
                A[i] = Mask[i] = bytes[i * 4 + 3] / 255f;
                if (A[i] > 0.1f)
                {
                    int x = i % W, y = i / W;
                    minX = Math.Min(minX, x); maxX = Math.Max(maxX, x); minY = Math.Min(minY, y); maxY = Math.Max(maxY, y);
                }
            }
        }
    }

    public Fx Run(string[] args, int first)
    {
        for (int i = first; i < args.Length; i++)
        {
            string op = args[i];
            int colon = op.IndexOf(':');
            string name = colon < 0 ? op : op.Substring(0, colon);
            var pos = new List<string>();
            var named = new Dictionary<string, string>();
            if (colon >= 0)
                foreach (var part in op.Substring(colon + 1).Split(','))
                {
                    int eq = part.IndexOf('=');
                    if (eq > 0) named[part.Substring(0, eq).Trim()] = part.Substring(eq + 1).Trim();
                    else pos.Add(part.Trim());
                }
            var a = new Args(pos, named);
            switch (name)
            {
                case "map": OpMap(a); break;
                case "pattern": OpPattern(a); break;
                case "glow": OpGlow(a); break;
                case "rim": OpRim(a); break;
                case "emissive": OpEmissive(a); break;
                case "sheen": OpSheen(a); break;
                case "sparkle": OpSparkle(a); break;
                case "embers": OpEmbers(a); break;
                case "trail": OpTrail(a); break;
                case "adjust": OpAdjust(a); break;
                case "bloom": bloomRadius = a.F(0, 4); bloomStrength = a.F(1, 1); break;
                default: throw new Exception("unknown op " + name);
            }
        }
        return this;
    }

    // ---------- ops ----------

    void OpMap(Args a)
    {
        var c1 = a.C(0); var c2 = a.C(1); var c3 = a.C(2);
        float strength = a.F(3, 1);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float w = strength * Zone(a, i);
            if (w <= 0) continue;
            float l = Contrast(Lum(i), 1.15f);
            float[] m = l < 0.5f ? Lerp3(c1, c2, l / 0.5f) : Lerp3(c2, c3, (l - 0.5f) / 0.5f);
            Mix(i, m, w);
        }
    }

    void OpPattern(Args a)
    {
        string type = a.S(0, "stripes");
        var c1 = a.NC("c1", "#ffffff"); var c2 = a.NC("c2", "#000000"); var c3 = a.NC("c3", "#808080");
        float opacity = a.NF("op", 1), scale = a.NF("scale", 24), angle = a.NF("angle", 45) * (float)Math.PI / 180;
        float bloom = a.NF("bloom", 0), shadeK = a.NF("shade", 1);
        int seed = (int)a.NF("seed", 1);
        float ca = (float)Math.Cos(angle), sa = -(float)Math.Sin(angle);
        float bw = Math.Max(1, maxX - minX), bh = Math.Max(1, maxY - minY);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float zw = Zone(a, i);
            if (zw <= 0) continue;
            int x = i % W, y = i / W;
            float m = 0;
            float[] col = c1;
            // u runs along the pattern direction, v across it
            float u = x * ca + y * sa, v = -x * sa + y * ca;
            switch (type)
            {
                case "stripes":
                {
                    float duty = a.NF("duty", 0.35f);
                    float t = Frac(u / scale);
                    m = Smooth(duty + 0.04f, duty, t) * Smooth(0, 0.04f, t);
                    break;
                }
                case "hazard":
                {
                    float t = Frac(u / scale);
                    float k = Smooth(0.47f, 0.53f, t);
                    col = Lerp3(c1, c2, k);
                    m = 1;
                    break;
                }
                case "flames":
                {
                    // Hot rod flames: pointed tongues of different heights rising along "angle" from the item's base,
                    // leaning as they rise, yellow at the base to red at the tips, with a dark outline
                    float dir = a.NF("angle", 90);
                    float rise = ProjectT(x, y, dir), across = ProjectT(x, y, dir - 90);
                    float reach = a.NF("reach", 0.6f);
                    float count = a.NF("count", 5);
                    float lean = across + 0.06f * rise * rise * 4 + 0.025f * (Fbm(x / 9f, y / 9f, seed + 4, 2) - 0.5f);
                    float k = lean * count;
                    int idx = (int)Math.Floor(k);
                    float f = k - idx;
                    float tongue = reach * (0.55f + 0.45f * Hash(idx, 7, seed));
                    float half = 0.5f * (float)Math.Pow(Clamp01(1 - rise / tongue), 0.75f);
                    float inside = (half - Math.Abs(f - 0.5f)) / count;
                    float baseFill = 0.14f * reach - rise;
                    float d = Math.Max(inside, baseFill);
                    m = Smooth(-0.004f, 0.004f, d);
                    float heat = Clamp01(rise / tongue + Math.Abs(f - 0.5f) * 0.7f);
                    col = Lerp3(c1, c2, Smooth(0.15f, 0.85f, heat));
                    float outline = 1 - Smooth(0.004f, 0.012f, d);
                    col = Lerp3(col, c3, outline * 0.9f);
                    break;
                }
                case "camo":
                {
                    float n = Fbm(x / scale, y / scale, seed, 4);
                    float n2 = Fbm(x / scale + 17, y / scale + 5, seed + 7, 4);
                    col = n < 0.45f ? c1 : c2;
                    if (n2 > 0.58f) col = c3;
                    m = 1;
                    break;
                }
                case "plaid":
                {
                    // Buffalo check: c1 squares, c2 where both bands cross, a mix where one does
                    float bx = Smooth(0.48f, 0.52f, Frac(x / scale)), by = Smooth(0.48f, 0.52f, Frac(y / scale));
                    float both = bx * by, one = Math.Max(bx, by) - both;
                    col = Lerp3(Lerp3(c1, c2, one * 0.55f), c2, both);
                    float fine = 0.5f + 0.5f * (float)Math.Sin((x + y) * 1.6f);
                    col = Lerp3(col, c1, fine * 0.08f);
                    m = 1;
                    break;
                }
                case "cracks":
                {
                    Worley(x / scale, y / scale, seed, out float f1, out float f2);
                    float width = a.NF("width", 0.06f);
                    float wobble = 0.05f * (Fbm(x / 6f, y / 6f, seed + 3, 2) - 0.5f);
                    m = 1 - Smooth(0, width, f2 - f1 + wobble);
                    break;
                }
                case "splatter":
                {
                    float n = Fbm(x / scale, y / scale, seed, 4);
                    float th = a.NF("amount", 0.6f);
                    m = Smooth(th, th + 0.04f, n);
                    // Speckles around the blobs
                    if (Hash(x, y, seed + 11) > 0.985f && n > th - 0.12f) m = 1;
                    break;
                }
                case "speckle":
                {
                    float n = Fbm(x / scale, y / scale, seed, 5);
                    float th = a.NF("amount", 0.55f);
                    m = Smooth(th, th + 0.12f, n) * (0.6f + 0.4f * Hash(x, y, seed));
                    break;
                }
                case "circuit":
                {
                    // Traces along a grid: each cell runs a line across or down its middle, some have a pad
                    float cs = scale;
                    int cx = (int)Math.Floor(x / cs), cy = (int)Math.Floor(y / cs);
                    float fx = x / cs - cx, fy = y / cs - cy;
                    float h = Hash(cx, cy, seed);
                    float line = 0.07f;
                    float hor = Smooth(line, line * 0.5f, Math.Abs(fy - 0.5f)) * (h < 0.5f ? 1 : Step(0.5f, fx));
                    float ver = Smooth(line, line * 0.5f, Math.Abs(fx - 0.5f)) * (h >= 0.5f ? 1 : Step(0.5f, fy));
                    float pad = Hash(cx, cy, seed + 1) > 0.6f ? Smooth(0.17f, 0.12f, Dist(fx, fy, 0.5f, 0.5f)) : 0;
                    float skip = Hash(cx, cy, seed + 2) > 0.8f ? 0 : 1;
                    m = Math.Max(Math.Max(hor, ver), pad) * skip;
                    break;
                }
                case "woodgrain":
                {
                    float t = (float)Math.Sin(v / scale * 6 + 6 * Fbm(u / (scale * 4), v / scale, seed, 3));
                    col = Lerp3(c1, c2, Smooth(0.2f, 0.9f, t));
                    m = 1;
                    break;
                }
                default: throw new Exception("unknown pattern " + type);
            }
            float w = m * opacity * zw;
            if (w <= 0) continue;
            // Keep the item's shading under the decal (shade=0 paints it flat)
            float shade = 1 + (0.35f + 0.9f * Lum(i) - 1) * shadeK;
            Mix(i, new[] { col[0] * shade, col[1] * shade, col[2] * shade }, w);
            if (bloom > 0) { ER[i] += col[0] * w * bloom * Mask[i]; EG[i] += col[1] * w * bloom * Mask[i]; EB[i] += col[2] * w * bloom * Mask[i]; }
        }
    }

    void OpGlow(Args a)
    {
        var c = a.C(0);
        float radius = a.F(1, 6), strength = a.F(2, 1), noise = a.NF("noise", 0);
        int seed = (int)a.NF("seed", 1);
        var g = Blur((float[])Mask.Clone(), radius);
        for (int i = 0; i < g.Length; i++)
        {
            float v = Clamp01(g[i] * 2.2f * strength);
            if (noise > 0) v *= 0.35f + 0.9f * Fbm((i % W) / noise, (i / W) / noise, seed, 3);
            v = Clamp01(v);
            if (v <= GA[i]) continue;
            GR[i] = c[0]; GG[i] = c[1]; GB[i] = c[2]; GA[i] = v;
        }
    }

    void OpRim(Args a)
    {
        var c = a.C(0);
        float width = a.F(1, 3), strength = a.F(2, 0.8f);
        var b = Blur((float[])Mask.Clone(), width);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float e = Clamp01((Mask[i] - b[i]) * 3f) * strength;
            R[i] = Clamp01(R[i] + c[0] * e); G[i] = Clamp01(G[i] + c[1] * e); B[i] = Clamp01(B[i] + c[2] * e);
        }
    }

    void OpEmissive(Args a)
    {
        var c = a.C(0);
        float th = a.F(1, 0.7f), strength = a.F(2, 1);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float w = Smooth(th, th + 0.15f, Lum(i)) * Zone(a, i) * strength;
            if (w <= 0) continue;
            var hot = new[] { Clamp01(c[0] + 0.35f), Clamp01(c[1] + 0.35f), Clamp01(c[2] + 0.35f) };
            Mix(i, hot, Clamp01(w * 0.8f));
            ER[i] += c[0] * w * Mask[i]; EG[i] += c[1] * w * Mask[i]; EB[i] += c[2] * w * Mask[i];
        }
    }

    void OpSheen(Args a)
    {
        float s = a.F(0, 0.6f);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float l = Lum(i);
            float curved = Smooth(0, 1, l);
            float k = l > 0.001f ? (l + (curved - l) * s) / l : 1;
            float spec = (float)Math.Pow(l, 5) * s * 0.9f;
            R[i] = Clamp01(R[i] * k + spec); G[i] = Clamp01(G[i] * k + spec); B[i] = Clamp01(B[i] * k + spec);
        }
    }

    void OpSparkle(Args a)
    {
        var c = a.C(0);
        int count = (int)a.F(1, 3);
        float size = a.F(2, 12);
        int seed = (int)a.F(3, 1);
        var spots = new List<int>();
        var order = new List<KeyValuePair<float, int>>();
        for (int i = 0; i < R.Length; i++)
            if (Mask[i] > 0.9f) order.Add(new KeyValuePair<float, int>(Lum(i) + 0.15f * Hash(i % W, i / W, seed), i));
        order.Sort((p, q) => q.Key.CompareTo(p.Key));
        foreach (var p in order)
        {
            if (spots.Count >= count) break;
            int x = p.Value % W, y = p.Value / W;
            bool far = true;
            foreach (int s in spots) if (Dist(x, y, s % W, s / W) < size * 2.5f) { far = false; break; }
            if (far) spots.Add(p.Value);
        }
        foreach (int s in spots)
        {
            int sx = s % W, sy = s / W;
            float sz = size * (0.7f + 0.6f * Hash(sx, sy, seed + 5));
            for (int y = Math.Max(0, (int)(sy - sz)); y < Math.Min(H, (int)(sy + sz) + 1); y++)
            for (int x = Math.Max(0, (int)(sx - sz)); x < Math.Min(W, (int)(sx + sz) + 1); x++)
            {
                float dx = Math.Abs(x - sx) / sz, dy = Math.Abs(y - sy) / sz;
                float star = Math.Max(Clamp01(1 - dx) * (float)Math.Exp(-dy * 18), Clamp01(1 - dy) * (float)Math.Exp(-dx * 18));
                float core = (float)Math.Exp(-(dx * dx + dy * dy) * 30);
                float v = Math.Max(star, core) * 1.4f;
                int i = y * W + x;
                ER[i] += c[0] * v; EG[i] += c[1] * v; EB[i] += c[2] * v;
            }
        }
    }

    void OpEmbers(Args a)
    {
        var c = a.C(0);
        int count = (int)a.F(1, 12);
        float size = a.F(2, 2), seedF = a.F(3, 1);
        int seed = (int)seedF;
        float pad = 14;
        var rng = new Random(seed);
        for (int k = 0, tries = 0; k < count && tries < count * 200; tries++)
        {
            float px = minX - pad + (float)rng.NextDouble() * (maxX - minX + 2 * pad);
            float py = minY - pad + (float)rng.NextDouble() * (maxY - minY + 2 * pad);
            int pi = Math.Min(H - 1, Math.Max(0, (int)py)) * W + Math.Min(W - 1, Math.Max(0, (int)px));
            if (a.Has("zone") && Zone(a, pi) <= 0.05f) continue;
            k++;
            float r = size * (0.5f + (float)rng.NextDouble());
            float bright = 0.6f + 0.6f * (float)rng.NextDouble();
            for (int y = Math.Max(0, (int)(py - r * 3)); y < Math.Min(H, (int)(py + r * 3) + 1); y++)
            for (int x = Math.Max(0, (int)(px - r * 3)); x < Math.Min(W, (int)(px + r * 3) + 1); x++)
            {
                float d = Dist(x, y, px, py) / r;
                float v = (float)Math.Exp(-d * d * 1.5f) * bright * 1.6f;
                int i = y * W + x;
                ER[i] += c[0] * v; EG[i] += c[1] * v; EB[i] += c[2] * v;
            }
        }
    }

    void OpTrail(Args a)
    {
        var c = a.C(0);
        float angle = a.F(1, 0) * (float)Math.PI / 180;
        int count = (int)a.F(2, 4);
        float spacing = a.F(3, 7), strength = a.F(4, 0.7f);
        // Afterimages trail away from the direction of motion
        float dx = -(float)Math.Cos(angle) * spacing, dy = (float)Math.Sin(angle) * spacing;
        var soft = Blur((float[])Mask.Clone(), 1.5f);
        for (int k = 1; k <= count; k++)
        {
            float fade = strength * (1 - (k - 1) / (float)count) * 0.8f;
            int ox = (int)Math.Round(dx * k), oy = (int)Math.Round(dy * k);
            for (int y = 0; y < H; y++)
            for (int x = 0; x < W; x++)
            {
                int sx = x - ox, sy = y - oy;
                if (sx < 0 || sy < 0 || sx >= W || sy >= H) continue;
                float v = soft[sy * W + sx] * fade;
                int i = y * W + x;
                if (v <= GA[i]) continue;
                GR[i] = c[0]; GG[i] = c[1]; GB[i] = c[2]; GA[i] = v;
            }
        }
    }

    void OpAdjust(Args a)
    {
        float sat = a.NF("sat", 1), bright = a.NF("bright", 1), contrast = a.NF("contrast", 1);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float l = Lum(i);
            float r = l + (R[i] - l) * sat, g = l + (G[i] - l) * sat, b = l + (B[i] - l) * sat;
            r = (r - 0.5f) * contrast + 0.5f; g = (g - 0.5f) * contrast + 0.5f; b = (b - 0.5f) * contrast + 0.5f;
            R[i] = Clamp01(r * bright); G[i] = Clamp01(g * bright); B[i] = Clamp01(b * bright);
        }
    }

    // ---------- output ----------

    public void Save(string path)
    {
        int n = W * H;
        var br = Blur((float[])ER.Clone(), bloomRadius);
        var bg = Blur((float[])EG.Clone(), bloomRadius);
        var bb = Blur((float[])EB.Clone(), bloomRadius);
        var bytes = new byte[n * 4];
        for (int i = 0; i < n; i++)
        {
            // Item over glow, premultiplied
            float a = A[i];
            float pr = R[i] * a, pg = G[i] * a, pb = B[i] * a;
            float ga = GA[i] * (1 - a);
            pr += GR[i] * ga; pg += GG[i] * ga; pb += GB[i] * ga;
            float oa = a + ga;
            // Emissive light: a sharp core plus the bloom, added on top
            float lr = (ER[i] * 0.5f + br[i] * 1.6f) * bloomStrength;
            float lg = (EG[i] * 0.5f + bg[i] * 1.6f) * bloomStrength;
            float lb = (EB[i] * 0.5f + bb[i] * 1.6f) * bloomStrength;
            pr += lr; pg += lg; pb += lb;
            oa = Clamp01(oa + Clamp01(Math.Max(lr, Math.Max(lg, lb))) * (1 - oa));
            if (oa <= 0.002f) continue;
            bytes[i * 4] = (byte)(Clamp01(pb / oa) * 255 + 0.5f);
            bytes[i * 4 + 1] = (byte)(Clamp01(pg / oa) * 255 + 0.5f);
            bytes[i * 4 + 2] = (byte)(Clamp01(pr / oa) * 255 + 0.5f);
            bytes[i * 4 + 3] = (byte)(oa * 255 + 0.5f);
        }
        using (var dst = new Bitmap(W, H, PixelFormat.Format32bppArgb))
        {
            var data = dst.LockBits(new Rectangle(0, 0, W, H), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            Marshal.Copy(bytes, 0, data.Scan0, bytes.Length);
            dst.UnlockBits(data);
            dst.Save(path, ImageFormat.Png);
        }
    }

    // ---------- helpers ----------

    float Lum(int i) => 0.299f * R[i] + 0.587f * G[i] + 0.114f * B[i];

    void Mix(int i, float[] c, float w)
    {
        w = Clamp01(w);
        R[i] += (Clamp01(c[0]) - R[i]) * w; G[i] += (Clamp01(c[1]) - G[i]) * w; B[i] += (Clamp01(c[2]) - B[i]) * w;
    }

    // Position of a pixel along a direction, 0..1 across the item
    float ProjectT(int x, int y, float angleDeg)
    {
        float an = angleDeg * (float)Math.PI / 180, ca = (float)Math.Cos(an), sa = -(float)Math.Sin(an);
        float p = x * ca + y * sa;
        float p0 = float.MaxValue, p1 = float.MinValue;
        foreach (int cx in new[] { minX, maxX })
        foreach (int cy in new[] { minY, maxY })
        {
            float q = cx * ca + cy * sa;
            p0 = Math.Min(p0, q); p1 = Math.Max(p1, q);
        }
        return (p - p0) / Math.Max(1, p1 - p0);
    }

    float Zone(Args a, int i)
    {
        if (!a.Has("zone")) return 1;
        var z = a.Named["zone"].Split('/');
        float angle = P(z[0]), start = P(z[1]), end = P(z[2]);
        float t = ProjectT(i % W, i / W, angle);
        if (z.Length == 5) return Smooth(start, end, t) * (1 - Smooth(P(z[3]), P(z[4]), t));
        if (start < 0) return 1 - Smooth(-start, end, t);
        return Smooth(start, end, t);
    }

    float[] Blur(float[] src, float radius)
    {
        // Three box blurs approximate a gaussian
        int r = Math.Max(1, (int)Math.Round(radius / 1.7f));
        int w = W, h = H;
        for (int pass = 0; pass < 3; pass++)
        {
            src = BoxH(src, w, h, r);
            src = BoxV(src, w, h, r);
        }
        return src;
    }

    static float[] BoxH(float[] s, int w, int h, int r)
    {
        var d = new float[s.Length];
        for (int y = 0; y < h; y++)
        {
            float sum = 0;
            for (int x = -r; x <= r; x++) sum += s[y * w + Math.Min(w - 1, Math.Max(0, x))];
            for (int x = 0; x < w; x++)
            {
                d[y * w + x] = sum / (2 * r + 1);
                int add = Math.Min(w - 1, x + r + 1), sub = Math.Max(0, x - r);
                sum += s[y * w + add] - s[y * w + sub];
            }
        }
        return d;
    }

    static float[] BoxV(float[] s, int w, int h, int r)
    {
        var d = new float[s.Length];
        for (int x = 0; x < w; x++)
        {
            float sum = 0;
            for (int y = -r; y <= r; y++) sum += s[Math.Min(h - 1, Math.Max(0, y)) * w + x];
            for (int y = 0; y < h; y++)
            {
                d[y * w + x] = sum / (2 * r + 1);
                int add = Math.Min(h - 1, y + r + 1), sub = Math.Max(0, y - r);
                sum += s[add * w + x] - s[sub * w + x];
            }
        }
        return d;
    }

    static float Hash(int x, int y, int s)
    {
        unchecked
        {
            uint h = (uint)(x * 374761393 + y * 668265263 + s * 1442695041);
            h = (h ^ (h >> 13)) * 1274126177u;
            h ^= h >> 16;
            return (h & 0xffffff) / 16777215f;
        }
    }

    static float ValueNoise(float x, float y, int s)
    {
        int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
        float fx = x - xi, fy = y - yi;
        fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
        float a = Hash(xi, yi, s), b = Hash(xi + 1, yi, s), c = Hash(xi, yi + 1, s), d = Hash(xi + 1, yi + 1, s);
        return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
    }

    static float Fbm(float x, float y, int s, int octaves)
    {
        float sum = 0, amp = 0.5f, norm = 0;
        for (int o = 0; o < octaves; o++)
        {
            sum += ValueNoise(x, y, s + o * 31) * amp;
            norm += amp; amp *= 0.5f; x *= 2.03f; y *= 2.03f;
        }
        return sum / norm;
    }

    static void Worley(float x, float y, int s, out float f1, out float f2)
    {
        int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
        f1 = f2 = 9;
        for (int j = -1; j <= 1; j++)
        for (int i = -1; i <= 1; i++)
        {
            float px = xi + i + Hash(xi + i, yi + j, s), py = yi + j + Hash(xi + i, yi + j, s + 1);
            float d = Dist(x, y, px, py);
            if (d < f1) { f2 = f1; f1 = d; } else if (d < f2) f2 = d;
        }
    }

    static float Dist(float x0, float y0, float x1, float y1) => (float)Math.Sqrt((x0 - x1) * (x0 - x1) + (y0 - y1) * (y0 - y1));
    static float Frac(float v) => v - (float)Math.Floor(v);
    static float Step(float edge, float v) => v >= edge ? 1 : 0;
    static float Clamp01(float v) => v < 0 ? 0 : v > 1 ? 1 : v;
    static float Contrast(float v, float k) => Clamp01((v - 0.5f) * k + 0.5f);
    static float Smooth(float e0, float e1, float v)
    {
        float t = Clamp01((v - e0) / (e1 - e0));
        return t * t * (3 - 2 * t);
    }
    static float[] Lerp3(float[] a, float[] b, float t) => new[] { a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t };
    static float P(string s) => float.Parse(s, CultureInfo.InvariantCulture);

    class Args
    {
        readonly List<string> pos;
        public readonly Dictionary<string, string> Named;
        public Args(List<string> p, Dictionary<string, string> n) { pos = p; Named = n; }
        public bool Has(string k) => Named.ContainsKey(k);
        public string S(int i, string def) => i < pos.Count ? pos[i] : def;
        public float F(int i, float def) => i < pos.Count ? P(pos[i]) : def;
        public float NF(string k, float def) => Named.ContainsKey(k) ? P(Named[k]) : def;
        public float[] C(int i) => Col(pos[i]);
        public float[] NC(string k, string def) => Col(Named.ContainsKey(k) ? Named[k] : def);
        static float[] Col(string hex)
        {
            var c = ColorTranslator.FromHtml(hex);
            return new[] { c.R / 255f, c.G / 255f, c.B / 255f };
        }
    }
}
