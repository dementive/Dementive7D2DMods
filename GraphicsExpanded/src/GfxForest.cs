using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

/// <summary>
/// Distant forests (DistantTree.shader, TreeCapture.shader). Past the tree distance the game draws no trees at all, so
/// far hills are bare; this draws every tree out there as a card that turns to face the camera, showing a picture of
/// that kind of tree from the side the camera is on.
///
/// The game keeps every tree's place in memory, in DecoManager's decoration chunks (128 m square). Once a world has
/// loaded they're read a few chunks a frame into one buffer on the graphics card, and read again every few minutes for
/// felled and planted ones. Each kind of tree is pictured from Views sides by borrowing one of the game's own models
/// from its object pool and drawing its nearest level of detail with its own materials' deferred pass into a small
/// G-buffer of ours (no camera: a throwaway camera's command buffers never ran); TreeCapture.shader then turns that
/// into the pictures. One indirect draw a frame then puts every card into the
/// player camera's G-buffer, so the game lights, fogs and hazes them like anything else.
///
/// A card hides where the game draws the tree itself: in a decoration chunk the game shows, closer than where that kind
/// of tree's last level of detail stops drawing. Further than that the game's own tree is gone and the card takes over.
/// Every client reads its own copy of the world's trees, so in multiplayer nothing is sent.
/// </summary>
public static class GfxForest
{
    private const int Views = 8;                    // sides each kind of tree is pictured from
    private const int ViewWidth = 128, ViewHeight = 128;   // square: pines are tall, oaks are wide
    private const int ChunksPerFrame = 16;
    private const float ReadEvery = 300f;           // seconds between reads of the world's trees
    private const float Brightness = 1f;
    private const int MaxKinds = 256;               // the kind's 8 bits in DistantTree.Data
    private static readonly Vector3 PictureSpot = new Vector3(0f, -3000f, 0f);     // far below the world, where nothing else is

    [StructLayout(LayoutKind.Sequential)]
    private struct DistantTree
    {
        public Vector3 Position;    // the foot, in world space
        public uint Data;           // bits 0-7: kind, 8-15: turn in 256ths of a circle, 16-31: decoration chunk
    }

    private class Kind
    {
        public string Model;
        public Vector4 Size;        // as _GfxTreeKinds: half width, height, bottom below the foot, size / last LOD height
        public bool Pictured;
        public int Tries;
        public int Level;           // the level of detail pictured
    }

    private static Shader drawShader, pictureShader;
    private static Material drawMaterial, pictureMaterial;
    private static Mesh card;

    private static World world;
    private static int generation;                  // bumped on release, so a read still running knows to stop
    private static bool reading;
    private static float nextRead;
    private static float readTime;

    private static readonly List<Kind> kinds = new List<Kind>();
    private static readonly Dictionary<int, int> kindByBlock = new Dictionary<int, int>();
    private static readonly Dictionary<int, int> chunkByKey = new Dictionary<int, int>();
    private static float[] chunkShares = new float[0];
    private static float nextChunks;
    private const float TreesSettle = 0.5f;         // seconds a shown chunk's trees get to arrive before its cards fade
    private const float CardsFade = 1f;             // seconds the cards take to fade out once they have
    private static readonly Dictionary<int, float> readySince = new Dictionary<int, float>();
    private static readonly HashSet<int> seenReady = new HashSet<int>();

    private static Texture2DArray colors, normals;
    private static ComputeBuffer trees, kindBuffer, chunkBuffer, args;
    private static int treeCount;

    private static Camera lastCamera;
    private static RenderTexture[] gbuffer;         // ours, for pictures: as the game's G-buffers 0 to 3
    private static RenderTexture pictureDepth, colorTarget, normalTarget;
    private static CommandBuffer pictureCommands;

    private static string state = "not started";

    /// <summary>gfxe trees debug: draws the cards bright magenta, to see where they are.</summary>
    public static bool Debug;

    public static bool Loaded => drawShader != null && pictureShader != null;

    public static void Init(AssetBundle bundle)
    {
        drawShader = bundle != null ? bundle.LoadAsset<Shader>("DistantTree") : null;
        pictureShader = bundle != null ? bundle.LoadAsset<Shader>("TreeCapture") : null;
        if (drawShader != null && !drawShader.isSupported || pictureShader != null && !pictureShader.isSupported || !SystemInfo.supportsComputeShaders)
        {
            Log.Warning("[GraphicsExpanded] The distant forest shaders aren't supported on this graphics card; distant forests are off");
            drawShader = pictureShader = null;
        }
        if (!Loaded)
            return;
        drawMaterial = new Material(drawShader) { hideFlags = HideFlags.HideAndDontSave, enableInstancing = true };
        pictureMaterial = new Material(pictureShader) { hideFlags = HideFlags.HideAndDontSave };

        // A card: x from -0.5 to 0.5 across, y from 0 at the foot to 1 at the top
        card = new Mesh { name = "GraphicsExpanded tree card", hideFlags = HideFlags.HideAndDontSave };
        card.vertices = new[] { new Vector3(-0.5f, 0f, 0f), new Vector3(0.5f, 0f, 0f), new Vector3(0.5f, 1f, 0f), new Vector3(-0.5f, 1f, 0f) };
        card.uv = new[] { new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f) };
        card.normals = new[] { Vector3.back, Vector3.back, Vector3.back, Vector3.back };
        card.tangents = new[] { new Vector4(1, 0, 0, -1), new Vector4(1, 0, 0, -1), new Vector4(1, 0, 0, -1), new Vector4(1, 0, 0, -1) };
        card.triangles = new[] { 0, 2, 1, 0, 3, 2 };
        card.bounds = new Bounds(Vector3.zero, Vector3.one * 100000f);
    }

    /// <summary>Called every frame from GfxApply.Update.</summary>
    public static void Update(EntityPlayerLocal player, Camera playerCamera)
    {
        if (!Loaded)
            return;
        World current = GameManager.Instance != null ? GameManager.Instance.World : null;
        bool wanted = GfxSettings.DetailActive && GfxSettings.DistantTrees == GfxDistantTrees.On;
        if (!wanted || player == null || playerCamera == null || current == null)
        {
            if (!wanted || current != world)
                Release();
            state = !wanted ? "off" : "no world";
            return;
        }
        if (current != world)
        {
            Release();
            world = current;
        }
        lastCamera = playerCamera;

        DecoManager decos = DecoManager.Instance;
        if (decos == null || decos.decoChunks == null || decos.decoChunks.Count == 0)
        {
            state = "waiting for the world's trees";
            return;
        }
        if (!reading && Time.unscaledTime >= nextRead)
            GameManager.Instance.StartCoroutine(Read(decos));
        if (trees == null || treeCount == 0)
            return;

        UpdateChunks(decos);
        drawMaterial.SetVector("_GfxOrigin", Origin.position);
        drawMaterial.SetVector("_GfxTreeParams", new Vector4(LodScale(playerCamera), Views, Brightness, Debug ? 1f : 0f));
        Graphics.DrawMeshInstancedIndirect(card, 0, drawMaterial, new Bounds(playerCamera.transform.position, Vector3.one * 100000f), args, 0,
            null, ShadowCastingMode.Off, false, 0, playerCamera, LightProbeUsage.Off);
    }

    /// <summary>Unity hides a level of detail below a screen height of size / distance * this.</summary>
    private static float LodScale(Camera camera)
    {
        return QualitySettings.lodBias / (2f * Mathf.Tan(camera.fieldOfView * 0.5f * Mathf.Deg2Rad));
    }

    // ---- Reading the world's trees ----

    private static IEnumerator Read(DecoManager decos)
    {
        reading = true;
        int run = generation;
        List<DecoChunk> chunks = new List<DecoChunk>(decos.decoChunks.Values);
        List<DistantTree> found = new List<DistantTree>(treeCount > 0 ? treeCount : 65536);
        for (int i = 0; i < chunks.Count; i++)
        {
            ReadChunk(chunks[i], found);
            if (i % ChunksPerFrame == ChunksPerFrame - 1)
            {
                yield return null;
                if (run != generation)
                    yield break;
            }
        }

        // Picture any kinds not pictured yet, one a frame
        if (!EnsurePictureSpace())
        {
            reading = false;
            nextRead = Time.unscaledTime + ReadEvery;
            yield break;
        }
        for (int k = 0; k < kinds.Count; k++)
        {
            if (kinds[k].Pictured || kinds[k].Tries >= 3)
                continue;
            kinds[k].Tries++;
            kinds[k].Pictured = Picture(k);
            yield return null;
            if (run != generation)
                yield break;
        }

        Upload(found);
        readTime = Time.unscaledTime;
        nextRead = Time.unscaledTime + ReadEvery;
        reading = false;
    }

    private static void ReadChunk(DecoChunk chunk, List<DistantTree> found)
    {
        try
        {
            if (chunk == null || chunk.decosPerSmallChunks == null)
                return;
            int key = DecoChunk.MakeKey16(chunk.decoChunkX, chunk.decoChunkZ);
            if (!chunkByKey.TryGetValue(key, out int index))
            {
                index = chunkByKey.Count;
                chunkByKey[key] = index;
            }
            if (index > 0xFFFF)
                return;
            Vector3 middle = DecoManager.cDecoMiddleOffset;
            foreach (List<DecoObject> list in chunk.decosPerSmallChunks.Values)
            {
                foreach (DecoObject deco in list)
                {
                    if (deco == null || deco.state == DecoState.GeneratedInactive)
                        continue;
                    Block block = deco.bv.Block;
                    if (!(block is BlockModelTree) || !(block.shape is BlockShapeModelEntity shape))
                        continue;
                    int kind = KindOf(block);
                    if (kind < 0)
                        continue;
                    int rotation = deco.bv.rotation;
                    if (!shape.Has45DegreeRotations)
                        rotation &= 3;
                    float yaw = BlockShapeNew.GetRotationStatic(rotation).eulerAngles.y;
                    uint turn = (uint)Mathf.RoundToInt(yaw / 360f * 256f) & 0xFF;
                    found.Add(new DistantTree
                    {
                        Position = new Vector3(deco.pos.x + middle.x, deco.realYPos + shape.modelOffset.y, deco.pos.z + middle.z),
                        Data = (uint)kind | turn << 8 | (uint)index << 16,
                    });
                }
            }
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't read a decoration chunk's trees: " + e.Message);
        }
    }

    private static int KindOf(Block block)
    {
        if (kindByBlock.TryGetValue(block.blockID, out int kind))
            return kind;
        string model = block.Properties != null ? block.Properties.GetValue("Model") : null;
        kind = -1;
        if (!string.IsNullOrEmpty(model))
        {
            kind = kinds.FindIndex(k => k.Model == model);
            if (kind < 0 && kinds.Count < MaxKinds)
            {
                kind = kinds.Count;
                kinds.Add(new Kind { Model = model });
            }
        }
        kindByBlock[block.blockID] = kind;
        return kind;
    }

    /// <summary>
    /// How far the game has taken over each decoration chunk's trees, for the cards to fade by. Not as soon as a chunk
    /// turns visible: the game makes its trees over the next frames (isModelsUpdated once it has asked for them all,
    /// and the models arrive after), so the cards wait a moment and then fade out over a second. A chunk that goes out
    /// of sight is 0 again at once, its cards back in full, since the game's trees go with it.
    /// </summary>
    private static void UpdateChunks(DecoManager decos)
    {
        if (Time.unscaledTime < nextChunks || decos.visibleDecoChunks == null)
            return;
        nextChunks = Time.unscaledTime + 0.05f;
        float now = Time.unscaledTime;
        seenReady.Clear();
        foreach (DecoChunk chunk in decos.visibleDecoChunks)
        {
            if (chunk == null || !chunk.isModelsUpdated)
                continue;
            int key = DecoChunk.MakeKey16(chunk.decoChunkX, chunk.decoChunkZ);
            if (!readySince.TryGetValue(key, out float since))
                readySince[key] = since = now;
            seenReady.Add(key);
        }
        // Forget chunks that went out of sight or are being remade, so they wait again next time
        foreach (int key in new List<int>(readySince.Keys))
        {
            if (!seenReady.Contains(key))
                readySince.Remove(key);
        }
        bool changed = false;
        float[] shares = new float[chunkShares.Length];
        foreach (KeyValuePair<int, float> ready in readySince)
        {
            if (chunkByKey.TryGetValue(ready.Key, out int index) && index < shares.Length)
                shares[index] = Mathf.Clamp01((now - ready.Value - TreesSettle) / CardsFade);
        }
        for (int i = 0; i < shares.Length && !changed; i++)
            changed = shares[i] != chunkShares[i];
        if (!changed)
            return;
        chunkShares = shares;
        chunkBuffer.SetData(chunkShares);
    }

    private static void Upload(List<DistantTree> found)
    {
        treeCount = found.Count;
        if (treeCount == 0)
        {
            state = "no trees in this world";
            return;
        }
        if (trees == null || trees.count != treeCount)
        {
            trees?.Release();
            trees = new ComputeBuffer(treeCount, 16);
        }
        trees.SetData(found);

        if (kindBuffer == null)
            kindBuffer = new ComputeBuffer(MaxKinds, 16);
        Vector4[] sizes = new Vector4[MaxKinds];
        for (int k = 0; k < kinds.Count; k++)
            sizes[k] = kinds[k].Pictured ? kinds[k].Size : Vector4.zero;
        kindBuffer.SetData(sizes);

        int chunks = Mathf.Max(chunkByKey.Count, 1);
        if (chunkBuffer == null || chunkBuffer.count != chunks)
        {
            chunkBuffer?.Release();
            chunkBuffer = new ComputeBuffer(chunks, 4);
            chunkShares = new float[chunks];
            chunkBuffer.SetData(chunkShares);
        }

        if (args == null)
            args = new ComputeBuffer(1, 5 * sizeof(uint), ComputeBufferType.IndirectArguments);
        args.SetData(new uint[] { card.GetIndexCount(0), (uint)treeCount, 0, 0, 0 });

        drawMaterial.SetBuffer("_GfxTrees", trees);
        drawMaterial.SetBuffer("_GfxTreeKinds", kindBuffer);
        drawMaterial.SetBuffer("_GfxTreeChunks", chunkBuffer);
        drawMaterial.SetTexture("_GfxTreeColors", colors);
        drawMaterial.SetTexture("_GfxTreeNormals", normals);
        drawMaterial.SetVector("_GfxTreeSize", new Vector4(ViewWidth, ViewHeight, 0f, 0f));
    }

    // ---- Pictures of each kind of tree ----

    /// <summary>Makes the picture arrays big enough for every kind, keeping the pictures already taken.</summary>
    private static bool EnsurePictureSpace()
    {
        int needed = Mathf.Max(kinds.Count, 1) * Views;
        if (colors != null && colors.depth >= needed)
            return true;
        if (needed > SystemInfo.maxTextureArraySlices)
        {
            Log.Warning("[GraphicsExpanded] " + kinds.Count + " kinds of tree need more texture slices than this graphics card has; distant forests are off");
            return false;
        }
        // Room for a few more kinds, so a later read finding one doesn't mean taking every picture again
        int depth = Mathf.Min(needed + 8 * Views, SystemInfo.maxTextureArraySlices);
        Texture2DArray newColors = new Texture2DArray(ViewWidth, ViewHeight, depth, TextureFormat.RGBA32, true, false)
            { name = "GraphicsExpanded tree colors", hideFlags = HideFlags.HideAndDontSave, wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Trilinear, anisoLevel = 4 };
        Texture2DArray newNormals = new Texture2DArray(ViewWidth, ViewHeight, depth, TextureFormat.RGBA32, true, true)
            { name = "GraphicsExpanded tree normals", hideFlags = HideFlags.HideAndDontSave, wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Trilinear, anisoLevel = 4 };
        newColors.Apply(false, true);
        newNormals.Apply(false, true);
        if (colors != null)
        {
            for (int slice = 0; slice < colors.depth; slice++)
            {
                Graphics.CopyTexture(colors, slice, newColors, slice);
                Graphics.CopyTexture(normals, slice, newNormals, slice);
            }
            Object.Destroy(colors);
            Object.Destroy(normals);
        }
        colors = newColors;
        normals = newNormals;
        drawMaterial.SetTexture("_GfxTreeColors", colors);
        drawMaterial.SetTexture("_GfxTreeNormals", normals);
        return true;
    }

    private static void EnsurePictureTargets()
    {
        if (gbuffer != null)
            return;
        gbuffer = new[]
        {
            Target("color", RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB),
            Target("specular", RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB),
            Target("normal", RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear),
            Target("light", RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear),
        };
        pictureDepth = new RenderTexture(ViewWidth, ViewHeight, 24, RenderTextureFormat.Depth) { name = "GraphicsExpanded tree depth", hideFlags = HideFlags.HideAndDontSave };
        pictureDepth.Create();
        colorTarget = Target("picture color", RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB, true);
        normalTarget = Target("picture normal", RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear, true);
        pictureCommands = new CommandBuffer { name = "GraphicsExpanded tree picture" };
        pictureMaterial.SetVector("_GfxCaptureSize", new Vector4(ViewWidth, ViewHeight, 1f / ViewWidth, 1f / ViewHeight));
        pictureMaterial.SetTexture("_GfxCapture0", gbuffer[0]);
        pictureMaterial.SetTexture("_GfxCapture2", gbuffer[2]);
    }

    private static RenderTexture Target(string name, RenderTextureFormat format, RenderTextureReadWrite space, bool mips = false)
    {
        RenderTexture target = new RenderTexture(ViewWidth, ViewHeight, 0, format, space)
            { name = "GraphicsExpanded tree " + name, hideFlags = HideFlags.HideAndDontSave, useMipMap = mips, autoGenerateMips = false };
        target.Create();
        return target;
    }

    /// <summary>
    /// One picture: the shown renderers drawn with their materials' deferred pass into our G-buffer from the given
    /// view, then turned into the color and normal pictures. Returns how many surfaces were drawn.
    /// </summary>
    private static int Draw(List<Renderer> shown, Matrix4x4 view, Matrix4x4 projection, Vector3 eye)
    {
        CommandBuffer cb = pictureCommands;
        cb.Clear();
        cb.SetRenderTarget(new RenderTargetIdentifier[] { gbuffer[0], gbuffer[1], gbuffer[2], gbuffer[3] }, pictureDepth);
        cb.ClearRenderTarget(true, true, Color.clear);
        cb.SetViewProjectionMatrices(view, projection);
        cb.SetGlobalVector("_WorldSpaceCameraPos", eye);
        int drawn = 0;
        foreach (Renderer renderer in shown)
        {
            Material[] materials = renderer.sharedMaterials;
            for (int sub = 0; sub < materials.Length; sub++)
            {
                Material material = materials[sub];
                int pass = material != null ? material.FindPass("DEFERRED") : -1;
                if (pass < 0)
                    continue;
                cb.DrawRenderer(renderer, material, sub, pass);
                drawn++;
            }
        }
        cb.SetRenderTarget(new RenderTargetIdentifier[] { colorTarget, normalTarget }, pictureDepth);
        cb.ClearRenderTarget(false, true, Color.clear);
        cb.DrawProcedural(Matrix4x4.identity, pictureMaterial, 0, MeshTopology.Triangles, 3);
        Graphics.ExecuteCommandBuffer(cb);
        return drawn;
    }

    /// <summary>Borrows one of the game's models of the kind and pictures it from every side; false if it couldn't.</summary>
    private static bool Picture(int index)
    {
        Kind kind = kinds[index];
        GameObject tree;
        try
        {
            // The pool knows models by file name alone, as DecoObject.GetModelName gives it
            tree = GameObjectPool.Instance.GetObjectForType(GameIO.GetFilenameFromPathWithoutExtension(kind.Model));
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't get the tree model " + kind.Model + ": " + e.Message);
            return false;
        }
        if (tree == null)
            return false;

        EnsurePictureTargets();
        LODGroup[] groups = tree.GetComponentsInChildren<LODGroup>(true);
        try
        {
            tree.transform.SetPositionAndRotation(PictureSpot, Quaternion.identity);
            tree.SetActive(true);
            // Pictured as the game draws it where it takes over from the cards, so the cards look like what replaces them
            int level = HandOverLevel(groups);
            kind.Level = level;
            foreach (LODGroup group in groups)
                group.ForceLOD(Mathf.Min(level, Mathf.Max(group.lodCount - 1, 0)));

            // What shows at that level of detail, how big it is, and when the game stops drawing it
            List<Renderer> shown = Shown(tree, groups, level);
            if (shown.Count == 0)
                return false;
            Bounds bounds = shown[0].bounds;
            foreach (Renderer renderer in shown)
                bounds.Encapsulate(renderer.bounds);
            float reach = 0f;
            for (int corner = 0; corner < 4; corner++)
            {
                Vector3 p = new Vector3((corner & 1) == 0 ? bounds.min.x : bounds.max.x, 0f, (corner & 2) == 0 ? bounds.min.z : bounds.max.z);
                reach = Mathf.Max(reach, Vector2.Distance(new Vector2(p.x, p.z), new Vector2(PictureSpot.x, PictureSpot.z)));
            }
            float bottom = bounds.min.y - PictureSpot.y, top = bounds.max.y - PictureSpot.y;
            float aspect = (float)ViewWidth / ViewHeight;
            float halfHeight = Mathf.Max((top - bottom) * 0.51f, reach * 1.02f / aspect);
            float halfWidth = halfHeight * aspect;
            float middle = (top + bottom) * 0.5f;
            kind.Size = new Vector4(halfWidth, halfHeight * 2f, halfHeight - middle, LodFactor(groups));

            Matrix4x4 projection = Matrix4x4.Ortho(-halfWidth, halfWidth, -halfHeight, halfHeight, 0.5f, reach * 2f + 20f);
            Vector3 center = PictureSpot + Vector3.up * middle;
            int drawn = 0;
            for (int view = 0; view < Views; view++)
            {
                Vector3 side = Quaternion.Euler(0f, view * 360f / Views, 0f) * Vector3.forward;
                Vector3 eye = center + side * (reach + 10f);
                // As a camera's: world to camera, with the camera looking down its -z
                Matrix4x4 worldToView = Matrix4x4.Scale(new Vector3(1f, 1f, -1f)) * Matrix4x4.TRS(eye, Quaternion.LookRotation(-side, Vector3.up), Vector3.one).inverse;
                pictureMaterial.SetMatrix("_GfxCaptureView", worldToView);
                drawn += Draw(shown, worldToView, projection, eye);
                colorTarget.GenerateMips();
                normalTarget.GenerateMips();
                int slice = index * Views + view;
                for (int mip = 0; mip < colors.mipmapCount; mip++)
                {
                    Graphics.CopyTexture(colorTarget, 0, mip, colors, slice, mip);
                    Graphics.CopyTexture(normalTarget, 0, mip, normals, slice, mip);
                }
            }
            if (drawn == 0)
                Log.Warning("[GraphicsExpanded] The tree " + kind.Model + " has no surfaces with a deferred pass to picture");
            return drawn > 0;
        }
        catch (Exception e)
        {
            Log.Warning("[GraphicsExpanded] Couldn't picture the tree " + kind.Model + ": " + e.Message);
            return false;
        }
        finally
        {
            foreach (LODGroup group in groups)
            {
                if (group != null)
                    group.ForceLOD(-1);
            }
            GameObjectPool.Instance.PoolObject(tree);
        }
    }

    /// <summary>The renderers drawn at a level of detail: each LOD group's at that level (or its last), and any outside a group.</summary>
    private static List<Renderer> Shown(GameObject tree, LODGroup[] groups, int level)
    {
        HashSet<Renderer> inGroups = new HashSet<Renderer>();
        List<Renderer> shown = new List<Renderer>();
        foreach (LODGroup group in groups)
        {
            LOD[] lods = group.GetLODs();
            int at = Mathf.Min(level, lods.Length - 1);
            for (int l = 0; l < lods.Length; l++)
            {
                foreach (Renderer renderer in lods[l].renderers)
                {
                    if (renderer == null)
                        continue;
                    inGroups.Add(renderer);
                    if (l == at && renderer.enabled)
                        shown.Add(renderer);
                }
            }
        }
        foreach (Renderer renderer in tree.GetComponentsInChildren<Renderer>())
        {
            if (renderer.enabled && !inGroups.Contains(renderer) && (renderer is MeshRenderer || renderer is SkinnedMeshRenderer))
                shown.Add(renderer);
        }
        return shown;
    }

    /// <summary>
    /// The level of detail the game draws the tree's largest LOD group at where it takes over from the cards (the edge
    /// of the tree distance, in decoration chunks of 128 m), but never a flat billboard level, which pictures badly: the
    /// nearest real model to it.
    /// </summary>
    private static int HandOverLevel(LODGroup[] groups)
    {
        LODGroup largest = null;
        float best = 0f;
        foreach (LODGroup group in groups)
        {
            Vector3 scale = group.transform.lossyScale;
            float size = group.size * Mathf.Max(Mathf.Abs(scale.x), Mathf.Max(Mathf.Abs(scale.y), Mathf.Abs(scale.z)));
            if (size > best)
            {
                best = size;
                largest = group;
            }
        }
        if (largest == null)
            return 0;
        float distance = (Mathf.Max(GfxApply.TreeRadius(EnumGamePrefs.OptionsGfxTreeDistance), 1) + 0.5f) * 128f;
        float fov = lastCamera != null ? lastCamera.fieldOfView : 65f;
        float relative = best * GfxDetailSwaps.Pending(largest) * QualitySettings.lodBias / (2f * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad)) / distance;
        LOD[] lods = largest.GetLODs();
        int level = lods.Length - 1;
        for (int i = 0; i < lods.Length; i++)
        {
            if (relative >= lods[i].screenRelativeTransitionHeight)
            {
                level = i;
                break;
            }
        }
        while (level > 0 && IsBillboard(lods[level]))
            level--;
        return Mathf.Max(level, 0);
    }

    private static bool IsBillboard(LOD lod)
    {
        foreach (Renderer renderer in lod.renderers)
        {
            if (renderer == null)
                continue;
            if (renderer is BillboardRenderer)
                return true;
            foreach (Material material in renderer.sharedMaterials)
            {
                if (material != null && (material.IsKeywordEnabled("EFFECT_BILLBOARD") || material.IsKeywordEnabled("_BILLBOARD")))
                    return true;
            }
            MeshFilter filter = renderer.GetComponent<MeshFilter>();
            if (filter != null && filter.sharedMesh != null && filter.sharedMesh.vertexCount <= 8)
                return true;
        }
        return false;
    }

    /// <summary>The largest LOD group's size over its last level's screen height (0 if it never stops drawing).</summary>
    private static float LodFactor(LODGroup[] groups)
    {
        float best = 0f, factor = 0f;
        foreach (LODGroup group in groups)
        {
            Vector3 scale = group.transform.lossyScale;
            float size = group.size * Mathf.Max(Mathf.Abs(scale.x), Mathf.Max(Mathf.Abs(scale.y), Mathf.Abs(scale.z)));
            LOD[] lods = group.GetLODs();
            if (size <= best || lods.Length == 0)
                continue;
            best = size;
            float last = lods[lods.Length - 1].screenRelativeTransitionHeight;
            factor = last > 1e-5f ? size / last * GfxDetailSwaps.Pending(group) : 0f;
        }
        return factor;
    }

    // ---- Housekeeping ----

    private static void Release()
    {
        generation++;
        reading = false;
        nextRead = 0f;
        world = null;
        kinds.Clear();
        kindByBlock.Clear();
        chunkByKey.Clear();
        chunkShares = new float[0];
        readySince.Clear();
        treeCount = 0;
        trees?.Release();
        kindBuffer?.Release();
        chunkBuffer?.Release();
        args?.Release();
        trees = kindBuffer = chunkBuffer = args = null;
        if (colors != null)
            Object.Destroy(colors);
        if (normals != null)
            Object.Destroy(normals);
        colors = normals = null;
    }

    /// <summary>gfxe trees save: writes every picture to GraphicsExpanded/Trees in the game's user folder.</summary>
    public static string SavePictures()
    {
        if (colors == null)
            return "No tree pictures yet (load a world with distant forests on).";
        string folder = Path.Combine(GameIO.GetUserGameDataDir(), "GraphicsExpanded", "Trees");
        Directory.CreateDirectory(folder);
        int saved = 0;
        for (int k = 0; k < kinds.Count; k++)
        {
            if (!kinds[k].Pictured)
                continue;
            for (int view = 0; view < Views; view++)
            {
                int slice = k * Views + view;
                Save(GfxTerrain.Read(colors, ViewWidth, ViewHeight, slice, RenderTextureFormat.ARGB32, TextureFormat.RGBA32, true), Path.Combine(folder, string.Format("{0:00}_{1}_color.png", k, view)));
                Save(GfxTerrain.Read(normals, ViewWidth, ViewHeight, slice, RenderTextureFormat.ARGB32, TextureFormat.RGBA32, false), Path.Combine(folder, string.Format("{0:00}_{1}_normal.png", k, view)));
                saved += 2;
            }
            Log.Out(string.Format("[GraphicsExpanded] Tree kind {0}: {1}, card {2:0.0} m wide and {3:0.0} m tall, last LOD factor {4:0.0}, pictured at level of detail {5}", k, kinds[k].Model, kinds[k].Size.x * 2f, kinds[k].Size.y, kinds[k].Size.w, kinds[k].Level));
        }
        return "Saved " + saved + " tree pictures to " + folder + " (and each kind's size to the game log).";
    }

    private static void Save(Texture2D picture, string path)
    {
        File.WriteAllBytes(path, picture.EncodeToPNG());
        Object.Destroy(picture);
    }

    public static string Status()
    {
        if (!Loaded)
            return "Distant forests are off: the shaders didn't load (see the log).";
        if (treeCount == 0)
            return "Distant forests: " + (reading ? "reading the world's trees" : state) + ".";
        int pictured = kinds.FindAll(k => k.Pictured).Count;
        float lodScale = lastCamera != null ? LodScale(lastCamera) : 0f;
        List<float> lastDraws = new List<float>();
        foreach (Kind kind in kinds)
        {
            if (kind.Pictured && kind.Size.w > 0f)
                lastDraws.Add(kind.Size.w * lodScale);
        }
        lastDraws.Sort();
        string lod = lastDraws.Count > 0 ? string.Format("; the game's own trees stop at {0:0} to {1:0} m (median {2:0} m)", lastDraws[0], lastDraws[lastDraws.Count - 1], lastDraws[lastDraws.Count / 2]) : "";
        return string.Format("Distant forests: {0} trees of {1} kinds ({2} pictured) in {3} decoration chunks, the game showing {4} of them{5}; read {6:0} s ago.",
            treeCount, kinds.Count, pictured, chunkByKey.Count, Array.FindAll(chunkShares, f => f >= 1f).Length, lod, Time.unscaledTime - readTime);
    }
}
