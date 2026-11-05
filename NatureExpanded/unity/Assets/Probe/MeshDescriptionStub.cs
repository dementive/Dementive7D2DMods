using System;
using UnityEngine;

// Stand-ins for the game's own MeshDescriptionCollection and MeshDescription, so NatureAtlasProbe can read the grass
// atlas out of the game's mesh-description prefab: Unity binds a bundle's script by class name in Assembly-CSharp and
// fills fields by name. Only the fields the probe reads are here. Reference only, used by no prefab of ours.
public class MeshDescriptionCollection : MonoBehaviour
{
    public MeshDescription[] meshes;
}

[Serializable]
public class MeshDescription
{
    public string Name;
    public string Tag;
    public bool bTextureArray;
    public string TextureAtlasClass;
    public Material BaseMaterial;
    public Material SecondaryMaterial;
    public Texture TexDiffuse;
    public Texture TexNormal;
    public Texture TexSpecular;
    public Texture TexEmission;
    public Texture TexHeight;
    public Texture TexOcclusion;
    public Texture2D TexMask;
    public Texture2D TexMaskNormal;
    public TextAsset MetaData;
}
