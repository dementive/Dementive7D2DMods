// Far shadows (GfxFarShadows): hills shading the land behind them past where the sun's shadow map reaches.
// Pass 0 copies one of the game's far terrain tiles into a world height map, in world heights.
// Pass 1 runs on the sun (or moon) after Unity has worked out its screen-space shadow mask, and puts a far shadow
// into it (keeping the darker of the two, so where the shadow map's own shadows fade out they don't double up): for
// every pixel past the shadow distance it walks from the point towards the light over the height map, and darkens it
// where ground rises above the path. Being in the shadow mask, only the light's own direct light dims, and anything
// out there is shaded: ground, the distant forests, far-off buildings.
// Pass 2 is gfxe farshadows debug: the same shadow laid over the picture in red, or (_GfxDebugMode 2) how far the
// height map is from the ground actually drawn, in blue, to check the map lines up with the world.
Shader "Hidden/GraphicsExpanded/FarShadows"
{
    CGINCLUDE
    #include "UnityCG.cginc"

    UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
    sampler2D _GfxHeight;           // world heights, Unity space
    float4 _GfxHeightRect;          // xy: the map's corner (x, z), zw: 1 / its size in meters
    float4 _GfxFarShadow;           // x: distance it starts at, y: 1 / meters it fades in over, z: the highest ground, w: penumbra per meter of distance
    float4 _GfxLightDir;            // xyz: towards the light
    float4x4 _GfxInvProjection;     // the camera's, OpenGL style
    float4x4 _GfxCameraToWorld;
    float4 _GfxFullSize;            // xy: pixels, zw: 1 / pixels
    float _GfxDebugMode;            // 1: the far shadow in red, 2: the height map's mismatch with the ground in blue

    struct v2f
    {
        float4 pos : SV_POSITION;
    };

    // One triangle covering the screen
    v2f vertScreen(uint id : SV_VertexID)
    {
        v2f o;
        float2 p = float2((id << 1) & 2, id & 2);
        o.pos = float4(p * 2 - 1, 0, 1);
        return o;
    }

    float2 MapUV(float2 xz)
    {
        return (xz - _GfxHeightRect.xy) * _GfxHeightRect.zw;
    }

    bool Inside(float2 xz)
    {
        float2 uv = MapUV(xz);
        return all(uv > 0) && all(uv < 1);
    }

    // The pixel's world position, and false for the sky
    bool WorldOf(float4 pos, out float3 world)
    {
        world = 0;
        float2 uv = pos.xy * _GfxFullSize.zw;
        float eyeDepth = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv));
        if (eyeDepth > _ProjectionParams.z * 0.99)
            return false;

        float2 ndc = uv * 2 - 1;
    #if UNITY_UV_STARTS_AT_TOP
        if (_ProjectionParams.x > 0)
            ndc.y = -ndc.y;
    #endif
        float4 farPoint = mul(_GfxInvProjection, float4(ndc, 1, 1));
        float3 view = farPoint.xyz / farPoint.w;
        world = mul(_GfxCameraToWorld, float4(view * (eyeDepth / -view.z), 1)).xyz;
        return true;
    }

    float HeightAt(float2 xz)
    {
        return tex2Dlod(_GfxHeight, float4(MapUV(xz), 0, 0)).r;
    }

    // How much of the light reaches the pixel past the shadow distance (1 where the far shadow isn't worked out),
    // and in fade how far into the far shadow's reach it is
    float FarLit(float4 pos, out float fade)
    {
        fade = 0;
        float3 world;
        if (!WorldOf(pos, world))
            return 1;

        fade = saturate((length(world - _WorldSpaceCameraPos) - _GfxFarShadow.x) * _GfxFarShadow.y);
        if (fade <= 0 || _GfxLightDir.y <= 0.001 || !Inside(world.xz))
            return 1;

        // Walk towards the light in steps that grow with distance (2 m at first, kilometers by the end), from a
        // little above the point so its own ground doesn't shade it
        float3 toLight = _GfxLightDir.xyz;
        float3 start = world + float3(0, 1.5, 0);
        float lit = 1;
        float t = 4;
        [loop]
        for (int step = 0; step < 48; step++)
        {
            float3 p = start + toLight * t;
            if (p.y > _GfxFarShadow.z || !Inside(p.xz))
                break;
            float above = p.y - HeightAt(p.xz);
            // Soft at the edge: the closer the path skims the ground, and the further along, the darker
            lit = min(lit, saturate(above / (t * _GfxFarShadow.w)));
            if (lit <= 0)
                break;
            t = t * 1.12 + 2;
        }
        return lit;
    }
    ENDCG

    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always

        // 0: one terrain tile's heights into the world height map
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5

            sampler2D _GfxTileHeight;       // the tile's heightmapTexture
            float4 _GfxTileRect;            // xy: its corner in the height map (0 to 1), zw: its size there
            float4 _GfxTileParams;          // x: the tile's base height, y: its height scale (size.y / kMaxHeight), z: heightmap resolution

            struct v2fTile
            {
                float4 pos : SV_POSITION;
                float2 corner : TEXCOORD0;
            };

            static const float2 Corners[6] = { float2(0, 0), float2(1, 0), float2(1, 1), float2(0, 0), float2(1, 1), float2(0, 1) };

            v2fTile vert(uint id : SV_VertexID)
            {
                v2fTile o;
                float2 corner = Corners[id];
                float2 clip = (_GfxTileRect.xy + corner * _GfxTileRect.zw) * 2 - 1;
            #if UNITY_UV_STARTS_AT_TOP
                clip.y = -clip.y;
            #endif
                o.pos = float4(clip, 0, 1);
                o.corner = corner;
                return o;
            }

            float frag(v2fTile i) : SV_Target
            {
                // Heightmap texels sit on the terrain's vertices: the first at the tile's edge
                float resolution = _GfxTileParams.z;
                float2 uv = (i.corner * (resolution - 1) + 0.5) / resolution;
                return _GfxTileParams.x + tex2Dlod(_GfxTileHeight, float4(uv, 0, 0)).r * _GfxTileParams.y;
            }
            ENDCG
        }

        // 1: the far shadow, into the light's screen-space shadow mask
        Pass
        {
            BlendOp Min
            Blend One One

            CGPROGRAM
            #pragma vertex vertScreen
            #pragma fragment frag
            #pragma target 3.5

            float4 frag(v2f i) : SV_Target
            {
                float fade;
                float lit = FarLit(i.pos, fade);
                return lerp(1, lit, fade);
            }
            ENDCG
        }

        // 2: gfxe farshadows debug: the far shadow laid over the picture in red
        Pass
        {
            Blend SrcAlpha OneMinusSrcAlpha

            CGPROGRAM
            #pragma vertex vertScreen
            #pragma fragment frag
            #pragma target 3.5

            float4 frag(v2f i) : SV_Target
            {
                if (_GfxDebugMode > 1.5)
                {
                    // Bright blue where the map is 20 m or more off the ground drawn (trees and buildings stand above it)
                    float3 world;
                    if (!WorldOf(i.pos, world) || !Inside(world.xz))
                        return 0;
                    return float4(0, 0.4, 1, saturate(abs(world.y - HeightAt(world.xz)) / 20) * 0.9);
                }
                float fade;
                float lit = FarLit(i.pos, fade);
                return float4(1, 0, 0, (1 - lit) * fade * 0.85);
            }
            ENDCG
        }
    }
}
