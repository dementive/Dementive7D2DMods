using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// "gfxe materials": writes what the block, terrain and other voxel mesh materials are made of to the game log, so
/// their shaders' settings can be tuned: each mesh's texture arrays (size, format, mipmaps, filtering) and each
/// material's shader, keywords and every property with its current value.
/// </summary>
public static class GfxDiagnostics
{
    public static int LogMaterials()
    {
        List<string> lines = new List<string>();
        lines.Add("_MipSlope " + Shader.GetGlobalFloat("_MipSlope"));

        MeshDescription[] meshes = MeshDescription.meshes;
        if (meshes == null)
        {
            lines.Add("No voxel meshes yet; load a world first.");
        }
        else
        {
            for (int i = 0; i < meshes.Length; i++)
            {
                MeshDescription mesh = meshes[i];
                if (mesh == null)
                    continue;
                lines.Add(string.Format("Mesh {0} '{1}': type {2}, texture array {3}, terrain {4}, atlas {5}, layer {6}",
                    i, mesh.Name, mesh.meshType, mesh.bTextureArray, mesh.bTerrain, mesh.TextureAtlasClass, mesh.MeshLayerName));
                AddTexture(lines, "  diffuse", mesh.TexDiffuse);
                AddTexture(lines, "  normal", mesh.TexNormal);
                AddTexture(lines, "  specular", mesh.TexSpecular);
                AddTexture(lines, "  emission", mesh.TexEmission);
                AddTexture(lines, "  height", mesh.TexHeight);
                AddTexture(lines, "  occlusion", mesh.TexOcclusion);

                HashSet<Material> seen = new HashSet<Material>();
                if (mesh.materials != null)
                {
                    for (int m = 0; m < mesh.materials.Length; m++)
                        AddMaterial(lines, "  material " + m, mesh.materials[m], seen);
                }
                AddMaterial(lines, "  distant material", mesh.materialDistant, seen);
            }
        }

        foreach (string line in lines)
            Log.Out("[GraphicsExpanded] " + line);
        return lines.Count;
    }

    private static void AddTexture(List<string> lines, string label, Texture texture)
    {
        if (texture == null)
            return;
        lines.Add(label + ": " + Describe(texture));
    }

    private static string Describe(Texture texture)
    {
        if (texture == null)
            return "none";
        string size = texture is Texture2DArray array
            ? string.Format("{0}x{1} x {2} layers, {3}", array.width, array.height, array.depth, array.format)
            : texture is Texture2D flat
                ? string.Format("{0}x{1}, {2}", flat.width, flat.height, flat.format)
                : string.Format("{0}x{1} {2}", texture.width, texture.height, texture.dimension);
        return string.Format("'{0}' {1}, {2} mipmaps, filter {3}, aniso {4}, mip bias {5}",
            texture.name, size, texture.mipmapCount, texture.filterMode, texture.anisoLevel, texture.mipMapBias);
    }

    private static void AddMaterial(List<string> lines, string label, Material material, HashSet<Material> seen)
    {
        if (material == null || !seen.Add(material))
            return;
        Shader shader = material.shader;
        lines.Add(string.Format("{0} '{1}': shader '{2}', keywords [{3}]", label, material.name,
            shader != null ? shader.name : "none", string.Join(" ", material.shaderKeywords)));
        if (shader == null)
            return;

        StringBuilder values = new StringBuilder();
        for (int p = 0; p < shader.GetPropertyCount(); p++)
        {
            string name = shader.GetPropertyName(p);
            ShaderPropertyType type = shader.GetPropertyType(p);
            values.Clear();
            values.Append("    ").Append(name).Append(" (").Append(type).Append(") = ");
            switch (type)
            {
                case ShaderPropertyType.Float:
                    values.Append(material.GetFloat(name));
                    break;
                case ShaderPropertyType.Range:
                    Vector2 limits = shader.GetPropertyRangeLimits(p);
                    values.Append(material.GetFloat(name)).Append(" in ").Append(limits.x).Append("..").Append(limits.y);
                    break;
                case ShaderPropertyType.Int:
                    values.Append(material.GetInteger(name));
                    break;
                case ShaderPropertyType.Color:
                    values.Append(material.GetColor(name));
                    break;
                case ShaderPropertyType.Vector:
                    values.Append(material.GetVector(name));
                    break;
                case ShaderPropertyType.Texture:
                    values.Append(Describe(material.GetTexture(name)));
                    break;
            }
            lines.Add(values.ToString());
        }
    }
}
