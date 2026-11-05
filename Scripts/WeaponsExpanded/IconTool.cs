// Usage:
//   IconTool.exe <in.png> <out.png> <#RRGGBB> [strength 0..1]
//     Recolors a vanilla item icon toward a theme color while keeping its shading (a gradient map from black through
//     the color to a light tint of it, blended with the original), like the 2026 WeaponsExpanded icons.
//   IconTool.exe fx <in.png> <out.png> <op> [<op> ...]
//     Runs a chain of effects on a vanilla icon, for icons in the style of the hand-made WeaponsExpanded ones
//     (paint jobs, decals, glows). Each op is "name:arg,arg,key=value,..." (see the Op* methods below):
//       map:#dark,#mid,#light[,strength][,zone=...]   gradient map by brightness (gold, chrome, leather, ...)
//       pattern:<type>,c1=#..,c2=#..,c3=#..,op=1,scale=24,seed=1,angle=45,zone=...,bloom=0,shade=1
//         types: stripes, hazard, flames, camo, plaid, cracks, splatter, speckle, circuit, woodgrain, dimples
//       glow:#color,radius,strength[,noise=scale]       outer glow behind the item
//       rim:#color,width,strength                        light along the inside of the silhouette
//       emissive:#color,threshold,strength[,zone=...]    bright parts glow (with bloom)
//       sheen:strength                                   polished metal contrast and highlights
//       sparkle:#color,count,size,seed                   star glints on the brightest spots
//       embers:#color,count,size,seed[,zone=...]         glowing specks around the item
//       trail:#color,angle,count,spacing,strength        fading afterimages behind an item moving toward "angle"
//       adjust:sat=1,bright=1,contrast=1
//       bloom:radius,strength                            how far emissive light spreads (default 4,1)
//     Ops for building a new item out of vanilla art (a food icon from parts of others):
//       hue:from,to,shift[,sat=1,val=1,min=.1]           turns colors with hue from..to by shift degrees, keeping shading
//       over:icon,x,y,width[,height=,rot=0,op=1,src=x0/y0/x1/y1,flip=1]
//                                                        lays another icon on top, x,y = its top left corner; icon is
//                                                        a path or a name next to the input icon; src crops it first
//       erase                                            deletes the selected part of the item (give it a selection)
//       place:cx,cy,scale[,sx=1,sy=1,rot=0]              moves the item's center to cx,cy, scales and turns it
//       fill:#color[,grain=.03,shade=0]                  paints the selection flat, keeping shade parts of its shading
//       text:words,cx,cy,size,#color[,font=Georgia,bold=1,italic=1,rot=0]   prints on the item (no commas in the words)
//       blur:radius                                      smooths the selection, melting chunks into a surface
//     zone=angle/start/end limits an op to part of the item: positions along the direction "angle" (degrees, 0 =
//     right, 90 = up) are scaled 0..1 across the item, and the op fades in from start to end. A negative start
//     flips it, so zone=45/-0.6/0.7 covers everything up to 0.6 and fades out by 0.7. Five values make a band:
//     zone=45/0.4/0.45/0.6/0.65 fades in from 0.4 to 0.45 and out from 0.6 to 0.65.
//     These also limit an op to part of the icon, in pixels, and can be combined with zone and each other:
//       box=x0/y0/x1/y1, ell=cx/cy/rx/ry, poly=x/y/x/y/... (soft=1.5 feathers their edges)
//       hsel=from/to[/minsat/maxsat] by hue, lsel=min/max by brightness, invert=1 flips the selection
//   IconTool.exe sheet <out.png> <in1.png> <in2.png> ...
//     Lays icons side by side for review.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.Globalization;
using System.IO;
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
    readonly string iconDir;

    public Fx(string path)
    {
        iconDir = Path.GetDirectoryName(Path.GetFullPath(path));
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
                case "hue": OpHue(a); break;
                case "over": OpOver(a); break;
                case "erase": OpErase(a); break;
                case "place": OpPlace(a); break;
                case "fill": OpFill(a); break;
                case "text": OpText(a); break;
                case "blur": OpBlur(a); break;
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
                case "dimples":
                {
                    // Rows of small pressed holes, like the dock marks in a cracker
                    float fx = Frac(u / scale) - 0.5f, fy = Frac(v / scale) - 0.5f;
                    float r = a.NF("size", 0.14f);
                    m = 1 - Smooth(r * 0.6f, r, (float)Math.Sqrt(fx * fx + fy * fy));
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
            if ((a.Has("zone") || a.Has("box") || a.Has("ell") || a.Has("poly")) && Zone(a, pi) <= 0.05f) continue;
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

    void OpHue(Args a)
    {
        float from = a.F(0, 0), to = a.F(1, 360), shift = a.F(2, 0);
        float sat = a.NF("sat", 1), val = a.NF("val", 1), min = a.NF("min", 0.1f);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            ToHsv(R[i], G[i], B[i], out float h, out float s, out float v);
            if (s <= min || !InHue(h, from, to)) continue;
            float w = Zone(a, i);
            if (w <= 0) continue;
            Mix(i, FromHsv(h + shift, Clamp01(s * sat), Clamp01(v * val)), w);
        }
    }

    void OpOver(Args a)
    {
        string name = a.S(0, "");
        string path = File.Exists(name) ? name : Path.Combine(iconDir, name + ".png");
        float x = a.F(1, 0), y = a.F(2, 0), w = a.F(3, W), rot = a.NF("rot", 0), op = a.NF("op", 1);
        using (var src = new Bitmap(path))
        {
            var box = new RectangleF(0, 0, src.Width, src.Height);
            if (a.Has("src"))
            {
                var c = a.Named["src"].Split('/');
                box = RectangleF.FromLTRB(P(c[0]), P(c[1]), P(c[2]), P(c[3]));
            }
            float h = a.NF("height", w * box.Height / box.Width);
            using (var layer = new Bitmap(W, H, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(layer))
                {
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.PixelOffsetMode = PixelOffsetMode.Half;
                    g.TranslateTransform(x + w / 2, y + h / 2);
                    g.RotateTransform(rot);
                    if (a.Has("flip")) g.ScaleTransform(-1, 1);
                    g.DrawImage(src, new RectangleF(-w / 2, -h / 2, w, h), box, GraphicsUnit.Pixel);
                }
                var bytes = Pixels(layer);
                for (int i = 0; i < R.Length; i++)
                {
                    float ta = bytes[i * 4 + 3] / 255f * op * Zone(a, i, true);
                    if (ta <= 0) continue;
                    float oa = ta + A[i] * (1 - ta);
                    float k = ta / oa;
                    R[i] += (bytes[i * 4 + 2] / 255f - R[i]) * k;
                    G[i] += (bytes[i * 4 + 1] / 255f - G[i]) * k;
                    B[i] += (bytes[i * 4] / 255f - B[i]) * k;
                    A[i] = Mask[i] = oa;
                }
            }
        }
        Bounds();
    }

    void OpErase(Args a)
    {
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            A[i] *= 1 - Zone(a, i);
            Mask[i] = A[i];
        }
        Bounds();
    }

    void OpPlace(Args a)
    {
        float cx = a.F(0, W / 2f), cy = a.F(1, H / 2f), scale = a.F(2, 1);
        float sx = scale * a.NF("sx", 1), sy = scale * a.NF("sy", 1);
        float rot = a.NF("rot", 0) * (float)Math.PI / 180, ca = (float)Math.Cos(rot), sa = (float)Math.Sin(rot);
        float ox = (minX + maxX) / 2f, oy = (minY + maxY) / 2f;
        int n = W * H;
        var nr = new float[n]; var ng = new float[n]; var nb = new float[n]; var na = new float[n];
        for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
        {
            float dx = x - cx, dy = y - cy;
            float px = (dx * ca + dy * sa) / sx + ox, py = (-dx * sa + dy * ca) / sy + oy;
            int x0 = (int)Math.Floor(px), y0 = (int)Math.Floor(py);
            float fx = px - x0, fy = py - y0, sum = 0, tr = 0, tg = 0, tb = 0;
            for (int j = 0; j < 2; j++)
            for (int k = 0; k < 2; k++)
            {
                int qx = x0 + k, qy = y0 + j;
                if (qx < 0 || qy < 0 || qx >= W || qy >= H) continue;
                int q = qy * W + qx;
                float wt = (k == 0 ? 1 - fx : fx) * (j == 0 ? 1 - fy : fy) * A[q];
                sum += wt; tr += R[q] * wt; tg += G[q] * wt; tb += B[q] * wt;
            }
            if (sum <= 0) continue;
            int i = y * W + x;
            nr[i] = tr / sum; ng[i] = tg / sum; nb[i] = tb / sum; na[i] = sum;
        }
        Array.Copy(nr, R, n); Array.Copy(ng, G, n); Array.Copy(nb, B, n); Array.Copy(na, A, n); Array.Copy(na, Mask, n);
        Bounds();
    }

    void OpFill(Args a)
    {
        var c = a.C(0);
        float grain = a.NF("grain", 0.03f), shade = a.NF("shade", 0);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float w = Zone(a, i);
            if (w <= 0) continue;
            float k = 1 + (Lum(i) - 0.5f) * shade + (Hash(i % W, i / W, 7) - 0.5f) * 2 * grain;
            Mix(i, new[] { c[0] * k, c[1] * k, c[2] * k }, w);
        }
    }

    void OpText(Args a)
    {
        var c = a.C(4);
        var style = (a.NF("bold", 0) > 0 ? FontStyle.Bold : FontStyle.Regular) | (a.NF("italic", 0) > 0 ? FontStyle.Italic : FontStyle.Regular);
        using (var layer = new Bitmap(W, H, PixelFormat.Format32bppArgb))
        {
            using (var g = Graphics.FromImage(layer))
            using (var font = new Font(a.Named.ContainsKey("font") ? a.Named["font"] : "Georgia", a.F(3, 12), style, GraphicsUnit.Pixel))
            using (var format = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
            {
                g.TextRenderingHint = TextRenderingHint.AntiAlias;
                g.TranslateTransform(a.F(1, W / 2f), a.F(2, H / 2f));
                g.RotateTransform(a.NF("rot", 0));
                g.DrawString(a.S(0, ""), font, Brushes.White, 0, 0, format);
            }
            var bytes = Pixels(layer);
            for (int i = 0; i < R.Length; i++)
                if (Mask[i] > 0) Mix(i, c, bytes[i * 4 + 3] / 255f * Zone(a, i));
        }
    }

    void OpBlur(Args a)
    {
        float radius = a.F(0, 3);
        var br = Blur((float[])R.Clone(), radius);
        var bg = Blur((float[])G.Clone(), radius);
        var bb = Blur((float[])B.Clone(), radius);
        for (int i = 0; i < R.Length; i++)
        {
            if (Mask[i] <= 0) continue;
            float w = Zone(a, i);
            if (w > 0) Mix(i, new[] { br[i], bg[i], bb[i] }, w);
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

    // How much of an op applies to a pixel: zone=, the pixel selections and the color selections, all multiplied.
    // skipColor leaves out the color selections, which read this item's pixels and mean nothing for a layer laid over it
    float Zone(Args a, int i, bool skipColor = false)
    {
        float w = Along(a, i);
        int x = i % W, y = i / W;
        float soft = a.NF("soft", 1.5f);
        if (a.Has("box"))
        {
            var b = a.Named["box"].Split('/');
            w *= Smooth(0, soft, Math.Min(Math.Min(x - P(b[0]), P(b[2]) - x), Math.Min(y - P(b[1]), P(b[3]) - y)));
        }
        if (a.Has("ell"))
        {
            var e = a.Named["ell"].Split('/');
            float rx = P(e[2]), ry = P(e[3]);
            float d = (1 - Dist((x - P(e[0])) / rx, (y - P(e[1])) / ry, 0, 0)) * Math.Min(rx, ry);
            w *= Smooth(0, soft, d);
        }
        if (a.Has("poly")) w *= Smooth(0, soft, InsidePoly(a.Named["poly"], x, y));
        if (!skipColor)
        {
            if (a.Has("hsel"))
            {
                var hs = a.Named["hsel"].Split('/');
                ToHsv(R[i], G[i], B[i], out float h, out float s, out float v);
                if (!InHue(h, P(hs[0]), P(hs[1])) || s < (hs.Length > 2 ? P(hs[2]) : 0.1f) || s > (hs.Length > 3 ? P(hs[3]) : 1)) w = 0;
            }
            if (a.Has("lsel"))
            {
                var ls = a.Named["lsel"].Split('/');
                float l = Lum(i);
                if (l < P(ls[0]) || l > P(ls[1])) w = 0;
            }
        }
        return a.Has("invert") ? 1 - w : w;
    }

    float Along(Args a, int i)
    {
        if (!a.Has("zone")) return 1;
        var z = a.Named["zone"].Split('/');
        float angle = P(z[0]), start = P(z[1]), end = P(z[2]);
        float t = ProjectT(i % W, i / W, angle);
        if (z.Length == 5) return Smooth(start, end, t) * (1 - Smooth(P(z[3]), P(z[4]), t));
        if (start < 0) return 1 - Smooth(-start, end, t);
        return Smooth(start, end, t);
    }

    // Distance of a point inside a polygon from its nearest edge, negative outside
    static float InsidePoly(string poly, float x, float y)
    {
        var v = poly.Split('/');
        int n = v.Length / 2;
        bool inside = false;
        float best = float.MaxValue;
        for (int i = 0, j = n - 1; i < n; j = i++)
        {
            float xi = P(v[i * 2]), yi = P(v[i * 2 + 1]), xj = P(v[j * 2]), yj = P(v[j * 2 + 1]);
            if ((yi > y) != (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
            float ex = xj - xi, ey = yj - yi;
            float t = Clamp01(((x - xi) * ex + (y - yi) * ey) / Math.Max(0.0001f, ex * ex + ey * ey));
            best = Math.Min(best, Dist(x, y, xi + ex * t, yi + ey * t));
        }
        return inside ? best : -best;
    }

    void Bounds()
    {
        minX = W; minY = H; maxX = 0; maxY = 0;
        for (int i = 0; i < A.Length; i++)
            if (A[i] > 0.1f)
            {
                int x = i % W, y = i / W;
                minX = Math.Min(minX, x); maxX = Math.Max(maxX, x); minY = Math.Min(minY, y); maxY = Math.Max(maxY, y);
            }
    }

    byte[] Pixels(Bitmap bmp)
    {
        var data = bmp.LockBits(new Rectangle(0, 0, W, H), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        var bytes = new byte[W * H * 4];
        Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);
        bmp.UnlockBits(data);
        return bytes;
    }

    static bool InHue(float h, float from, float to) => from <= to ? h >= from && h <= to : h >= from || h <= to;

    static void ToHsv(float r, float g, float b, out float h, out float s, out float v)
    {
        float max = Math.Max(r, Math.Max(g, b)), min = Math.Min(r, Math.Min(g, b)), d = max - min;
        v = max; s = max > 0 ? d / max : 0; h = 0;
        if (d <= 0) return;
        if (max == r) h = 60 * (((g - b) / d) % 6);
        else if (max == g) h = 60 * ((b - r) / d + 2);
        else h = 60 * ((r - g) / d + 4);
        if (h < 0) h += 360;
    }

    static float[] FromHsv(float h, float s, float v)
    {
        h = (h % 360 + 360) % 360;
        float c = v * s, x = c * (1 - Math.Abs(h / 60 % 2 - 1)), m = v - c;
        float[] rgb = h < 60 ? new[] { c, x, 0f } : h < 120 ? new[] { x, c, 0f } : h < 180 ? new[] { 0f, c, x }
            : h < 240 ? new[] { 0f, x, c } : h < 300 ? new[] { x, 0f, c } : new[] { c, 0f, x };
        return new[] { rgb[0] + m, rgb[1] + m, rgb[2] + m };
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
