// The distant forests (GfxForest): every tree the game doesn't draw itself, as a card that turns to face the camera
// showing a picture of that kind of tree (TreeCapture.shader) from the side the camera is on. All of them go in one
// DrawMeshInstancedIndirect, each instance's place, kind, turn and decoration chunk read from _GfxTrees.
//
// It's a deferred surface shader, so the cards go into the G-buffer like any other surface and the game's own sun,
// ambient light, fog (and Torch, and our haze) light and fade them. A card gives way where the game draws the tree
// itself: in a decoration chunk the game has shown, closer than where that kind of tree's last level of detail stops
// drawing. It fades rather than vanishing, dithered: out over a second as a chunk's trees arrive (_GfxTreeChunks
// rises from 0 to 1), and in across a band around where the game's tree stops drawing, so neither side snaps.
Shader "GraphicsExpanded/DistantTree"
{
    SubShader
    {
        Tags { "RenderType"="TransparentCutout" "Queue"="AlphaTest" }
        Cull Off

        CGPROGRAM
        #pragma surface surf Standard vertex:vert exclude_path:prepass nolightmap nodynlightmap nodirlightmap nometa noforwardadd
        #pragma multi_compile_instancing
        #pragma instancing_options procedural:setup
        #pragma target 4.5

        UNITY_DECLARE_TEX2DARRAY(_GfxTreeColors);
        UNITY_DECLARE_TEX2DARRAY(_GfxTreeNormals);

        struct DistantTree
        {
            float3 position;    // the tree's foot in world space (add the game's Origin.position back off to draw it)
            uint data;          // bits 0-7: kind, 8-15: turn in 256ths of a circle, 16-31: decoration chunk
        };

        #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
        StructuredBuffer<DistantTree> _GfxTrees;
        StructuredBuffer<float4> _GfxTreeKinds;     // x: half the picture's width, y: its height, z: how far its bottom is below the foot, w: size / last LOD's screen height (0: never culled)
        StructuredBuffer<float> _GfxTreeChunks;     // how far the game has taken over the decoration chunk's trees: 0 not at all, 1 fully
        #endif

        float4 _GfxOrigin;          // xyz: the game's Origin.position
        float4 _GfxTreeParams;      // x: LOD bias / (2 tan(fov / 2)), y: views per kind, z: brightness, w: 1 to show the cards in magenta
        float4 _GfxTreeSize;        // xy: picture size in pixels

        struct Input
        {
            float3 atlas;           // xy: where on the picture, z: which picture
            float shown;            // how much of the card shows, 0 to 1, dithered
            float4 screenPos;
        };

        void setup()
        {
            #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
            // vert places the card in world space itself
            unity_ObjectToWorld = float4x4(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1);
            unity_WorldToObject = unity_ObjectToWorld;
            #endif
        }

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
            DistantTree tree = _GfxTrees[unity_InstanceID];
            uint kind = tree.data & 0xFF;
            float turn = ((tree.data >> 8) & 0xFF) * (6.2831853 / 256);
            uint chunk = tree.data >> 16;
            float4 size = _GfxTreeKinds[kind];

            float3 foot = tree.position - _GfxOrigin.xyz;
            float3 toCamera = _WorldSpaceCameraPos - foot;
            float distance = length(toCamera);
            // Past where the game's tree stops drawing the card shows; across the band around it, partly
            float stops = size.w * _GfxTreeParams.x;
            float beyond = size.w <= 0 ? 0 : saturate((distance - stops * 0.92) / (stops * 0.12));
            float shown = lerp(1, beyond, _GfxTreeChunks[chunk]);
            bool gameDraws = shown <= 0.002;

            // Turned about the upright to face the camera
            float2 across = toCamera.xz;
            across = dot(across, across) > 1e-6 ? normalize(across) : float2(0, 1);
            float3 facing = float3(across.x, 0, across.y);
            float3 right = float3(-facing.z, 0, facing.x);
            float3 world = foot + right * ((v.vertex.x * 2) * size.x) + float3(0, v.vertex.y * size.y - size.z, 0);
            v.vertex = float4(gameDraws ? foot : world, 1);
            v.normal = facing;
            v.tangent = float4(right, -1);

            // The picture taken from nearest the side the camera's on, in the tree's own turn
            float views = _GfxTreeParams.y;
            float around = frac((atan2(facing.x, facing.z) - turn) / 6.2831853 + 0.5 / views);
            o.atlas = float3(v.texcoord.xy, kind * views + min(floor(around * views), views - 1));
            o.shown = shown;
            #endif
        }

        void surf(Input i, inout SurfaceOutputStandard o)
        {
            float4 color = UNITY_SAMPLE_TEX2DARRAY(_GfxTreeColors, i.atlas);
            float4 normal = UNITY_SAMPLE_TEX2DARRAY(_GfxTreeNormals, i.atlas);

            // Shrunk pictures average coverage down, so far trees would thin to nothing: lift it with the mipmap level
            float2 dx = ddx(i.atlas.xy * _GfxTreeSize.xy);
            float2 dy = ddy(i.atlas.xy * _GfxTreeSize.xy);
            float mip = 0.5 * log2(max(max(dot(dx, dx), dot(dy, dy)), 1e-6));
            clip(color.a * (1 + max(mip, 0) * 0.25) - 0.5);
            // Partly shown: a screen-door pattern of the right density, steady from frame to frame
            float2 pixel = i.screenPos.xy / max(i.screenPos.w, 1e-5) * _ScreenParams.xy;
            clip(i.shown - frac(52.9829189 * frac(dot(pixel, float2(0.06711056, 0.00583715)))) - 0.001);

            float coverage = max(color.a, 1e-3);
            o.Albedo = saturate(color.rgb / coverage * _GfxTreeParams.z);
            o.Normal = normalize(normal.rgb / coverage * 2 - 1);
            o.Occlusion = saturate(normal.a / coverage);
            o.Smoothness = 0.1;
            o.Metallic = 0;
            if (_GfxTreeParams.w > 0.5)
            {
                o.Albedo = float3(1, 0, 1);
                o.Emission = float3(0.6, 0, 0.6);
            }
        }
        ENDCG
    }
}
