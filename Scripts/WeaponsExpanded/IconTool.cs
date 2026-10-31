// Usage: IconTool.exe <in.png> <out.png> <#RRGGBB> [strength 0..1] [sheet.png in1 in2 ...]
// Recolors a vanilla item icon toward a theme color while keeping its shading (a gradient map from black through
// the color to a light tint of it, blended with the original), like the existing WeaponsExpanded icons.
// "sheet" mode: IconTool.exe sheet <out.png> <in1.png> <in2.png> ... lays icons side by side for review.
using System;
using System.Drawing;
using System.Drawing.Imaging;

class IconTool
{
    static void Main(string[] args)
    {
        if (args[0] == "sheet")
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
            return;
        }

        Color theme = ColorTranslator.FromHtml(args[2]);
        double strength = args.Length > 3 ? double.Parse(args[3], System.Globalization.CultureInfo.InvariantCulture) : 0.8;
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
