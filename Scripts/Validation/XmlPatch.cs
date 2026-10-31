// Usage: XmlPatch.exe <vanillaConfigDir> <outDir> <modDir> [<modDir> ...]
// Applies 7D2D-style xpath patch files from each mod's Config folder (in the order given) to the
// vanilla XML, reports every command whose xpath matched nothing, and writes the merged XML to outDir.
// Each written file's elements get a dmMod="<mod>" attribute on nodes a mod added, for reference checks.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Xml;

class XmlPatch
{
    static readonly Dictionary<string, XmlDocument> Docs = new Dictionary<string, XmlDocument>(StringComparer.OrdinalIgnoreCase);
    static int problems;

    static void Main(string[] args)
    {
        string vanilla = args[0], outDir = args[1];
        foreach (string mod in args.Skip(2))
        {
            string modName = Path.GetFileName(mod.TrimEnd('\\', '/'));
            string cfg = Path.Combine(mod, "Config");
            if (!Directory.Exists(cfg)) continue;
            foreach (string patch in Directory.GetFiles(cfg, "*.xml", SearchOption.AllDirectories).OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
            {
                string rel = patch.Substring(cfg.Length + 1);
                string target = Path.Combine(vanilla, rel);
                if (!File.Exists(target)) { Report(modName, rel, "no vanilla file " + rel + " (new file, not a patch)"); continue; }
                XmlDocument doc;
                if (!Docs.TryGetValue(rel, out doc))
                {
                    doc = new XmlDocument { PreserveWhitespace = false };
                    doc.Load(target);
                    Docs[rel] = doc;
                }
                var p = new XmlDocument();
                try { p.Load(patch); }
                catch (XmlException e) { Report(modName, rel, "MALFORMED XML: " + e.Message); continue; }
                foreach (XmlNode cmd in p.DocumentElement.ChildNodes)
                    if (cmd is XmlElement el) Apply(doc, el, modName, rel);
            }
        }
        Directory.CreateDirectory(outDir);
        foreach (var kv in Docs)
        {
            string dst = Path.Combine(outDir, kv.Key);
            Directory.CreateDirectory(Path.GetDirectoryName(dst));
            kv.Value.Save(dst);
        }
        Console.WriteLine(problems == 0 ? "All xpath commands matched." : problems + " problem(s).");
    }

    static void Report(string mod, string file, string msg)
    {
        problems++;
        Console.WriteLine("[" + mod + "] " + file + ": " + msg);
    }

    static string Short(XmlElement cmd)
    {
        string s = cmd.OuterXml.Replace("\r", "").Replace("\n", " ").Replace("\t", " ");
        while (s.Contains("  ")) s = s.Replace("  ", " ");
        return s.Length > 220 ? s.Substring(0, 220) + "..." : s;
    }

    static void Apply(XmlDocument doc, XmlElement cmd, string mod, string file)
    {
        string xpath = cmd.GetAttribute("xpath");
        if (string.IsNullOrEmpty(xpath)) { Report(mod, file, "command without xpath: " + Short(cmd)); return; }
        XmlNodeList nodes;
        try { nodes = doc.SelectNodes(xpath); }
        catch (Exception e) { Report(mod, file, "BAD XPATH (" + e.Message + "): " + Short(cmd)); return; }
        if (nodes.Count == 0) { Report(mod, file, "NO MATCH: " + Short(cmd)); return; }

        foreach (XmlNode n in nodes.Cast<XmlNode>().ToList())
        {
            switch (cmd.Name)
            {
                case "set":
                    if (n is XmlAttribute a) a.Value = cmd.InnerText;
                    else { n.InnerXml = cmd.InnerXml; Tag(n, mod); }
                    break;
                case "append":
                    if (n is XmlAttribute aa) aa.Value += cmd.InnerText;
                    else foreach (XmlNode c in cmd.ChildNodes) n.AppendChild(Tag(doc.ImportNode(c, true), mod));
                    break;
                case "prepend":
                    if (n is XmlAttribute pa) pa.Value = cmd.InnerText + pa.Value;
                    else foreach (XmlNode c in cmd.ChildNodes.Cast<XmlNode>().Reverse()) n.PrependChild(Tag(doc.ImportNode(c, true), mod));
                    break;
                case "insertAfter":
                    {
                        XmlNode at = n;
                        foreach (XmlNode c in cmd.ChildNodes) { var imp = Tag(doc.ImportNode(c, true), mod); n.ParentNode.InsertAfter(imp, at); at = imp; }
                    }
                    break;
                case "insertBefore":
                    foreach (XmlNode c in cmd.ChildNodes) n.ParentNode.InsertBefore(Tag(doc.ImportNode(c, true), mod), n);
                    break;
                case "remove":
                    if (n is XmlAttribute ra) ra.OwnerElement.RemoveAttributeNode(ra);
                    else n.ParentNode.RemoveChild(n);
                    break;
                case "removeattribute":
                    // The game's RemoveAttributeByXPath only accepts xpaths that select attributes
                    if (!(n is XmlAttribute rattr)) { Report(mod, file, "removeattribute xpath must select an attribute (matched " + n.NodeType + "): " + Short(cmd)); return; }
                    rattr.OwnerElement.RemoveAttributeNode(rattr);
                    break;
                case "setattribute":
                    if (!(n is XmlElement)) { Report(mod, file, "setattribute xpath must select an element: " + Short(cmd)); return; }
                    if (!cmd.HasAttribute("name")) { Report(mod, file, "setattribute needs a name attribute: " + Short(cmd)); return; }
                    ((XmlElement)n).SetAttribute(cmd.GetAttribute("name"), cmd.InnerText.Trim());
                    break;
                default:
                    Report(mod, file, "unsupported command <" + cmd.Name + ">");
                    return;
            }
        }
    }

    static XmlNode Tag(XmlNode n, string mod)
    {
        if (n is XmlElement e) e.SetAttribute("dmMod", mod);
        return n;
    }
}
