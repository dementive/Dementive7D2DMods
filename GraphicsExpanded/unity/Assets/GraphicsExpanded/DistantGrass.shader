// Distant grass (GfxDistantGrass): grass on the far terrain past the chunks the game has loaded, where it grows none.
// One DrawMeshInstancedIndirect of a whole grid of cells around the camera; each instance works out its own cell's
// place on a fixed world grid (so tufts stay put as the grid follows the camera), and collapses to nothing where no
// grass belongs: a chunk the game has loaded (its own grass is there), a road or water (the world's splat maps), a
// building's footprint or a biome with little grass (the field GfxDistantGrass makes), steep ground, or past the
// outer edge. It's drawn twice: a fine grid of small tufts near, and a coarse grid of tufts twice the size far, which
// cover the ground the same, handing over in a band (_GfxGrassRing) where each draws fewer the further into the other's.
// Each tuft is a low, wide card turned to face the camera, with blades from a texture GfxDistantGrass draws, colored
// by biome, drawn into the G-buffer like any surface so the game's sun, shadows, fog and the haze light it.
Shader "GraphicsExpanded/DistantGrass"
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

        sampler2D _GfxGrassBlades;      // four blade patterns side by side, alpha the blades
        sampler2D _GfxGrassField;       // around the camera: r how much grass grows (biome, buildings), g the biome's color index / 255
        sampler2D _GfxGrassChunks;      // same area: r how far the game's own grass has taken over the chunk, 0 to 1 over a second
        sampler2D _GfxGrassHeights;     // world heights, Unity space (GfxFarShadows' height map)
        sampler2D _GfxGrassRoads;       // the world's splat3: roads in any channel
        sampler2D _GfxGrassWater;       // the world's splat4: water in green and blue

        float4 _GfxGrassGrid;           // xy: the grid's corner (world x, z), z: cell size, w: cells per side
        float4 _GfxGrassFieldRect;      // xy: the field's corner (world x, z), z: 1 / its size
        float4 _GfxGrassHeightRect;     // xy: the height map's corner (Unity x, z), zw: 1 / its size
        float4 _GfxGrassRange;          // x: unused, y: the outer edge, z: fades out over this, w: unused
        float4 _GfxGrassRing;           // this draw's: x, y where the hand-over band starts and ends, z: 1 for the far grid, w: tuft size (times)
        float4 _GfxGrassCard;           // x: tuft width, y: tuft height, z: has splat maps (1), w: debug (1 magenta, 2 red where masked)
        float4 _GfxGrassWorld;          // xy: world size in blocks (splat maps cover it)
        float4 _GfxOrigin;              // xyz: the game's Origin.position (world = Unity + this)
        float4 _GfxGrassColors[16];     // per biome: rgb linear color, a unused

        struct Input
        {
            float4 card;                // xy: where on the tuft (0 to 1), z: blade pattern, w: color index
            float4 look;                // x: brightness, y: debug red, zw: unused
        };

        void setup()
        {
            #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
            unity_ObjectToWorld = float4x4(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1);
            unity_WorldToObject = unity_ObjectToWorld;
            #endif
        }

        float Hash(float2 p)
        {
            p = frac(p * float2(0.1031, 0.1030));
            p += dot(p, p.yx + 33.33);
            return frac((p.x + p.y) * p.x);
        }

        float Height(float2 unityXZ)
        {
            return tex2Dlod(_GfxGrassHeights, float4((unityXZ - _GfxGrassHeightRect.xy) * _GfxGrassHeightRect.zw, 0, 0)).r;
        }

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
            uint cells = (uint)_GfxGrassGrid.w;
            uint id = unity_InstanceID;
            float2 cellIndex = float2(id % cells, id / cells) + floor(_GfxGrassGrid.xy / _GfxGrassGrid.z + 0.5);
            float a = Hash(cellIndex), b = Hash(cellIndex + 17.3), c = Hash(cellIndex + 41.7), d = Hash(cellIndex + 73.1);
            float2 world = (cellIndex + float2(a, b)) * _GfxGrassGrid.z;
            float2 unityXZ = world - _GfxOrigin.xz;
            float2 cameraWorld = _WorldSpaceCameraPos.xz + _GfxOrigin.xz;
            float distance = length(world - cameraWorld);

            float2 fieldUV = (world - _GfxGrassFieldRect.xy) * _GfxGrassFieldRect.z;
            float4 field = tex2Dlod(_GfxGrassField, float4(fieldUV, 0, 0));
            float loaded = tex2Dlod(_GfxGrassChunks, float4(fieldUV, 0, 0)).r;
            float ground = Height(unityXZ);
            // Steep ground grows none: the height map's slope across a couple of meters
            float slope = length(float2(Height(unityXZ + float2(2, 0)) - Height(unityXZ - float2(2, 0)),
                                        Height(unityXZ + float2(0, 2)) - Height(unityXZ - float2(0, 2)))) / 4;
            bool masked = false;
            if (_GfxGrassCard.z > 0.5)
            {
                float2 splatUV = world / _GfxGrassWorld.xy + 0.5;
                float4 roads = tex2Dlod(_GfxGrassRoads, float4(splatUV, 0, 0));
                float4 water = tex2Dlod(_GfxGrassWater, float4(splatUV, 0, 0));
                masked = max(max(roads.r, roads.g), max(roads.b, roads.a)) > 0.15 || max(water.g, water.b) > 0.15;
            }

            // The near grid gives way to the far one across the band, each drawing fewer the further into the other's
            float band = saturate((distance - _GfxGrassRing.x) / max(_GfxGrassRing.y - _GfxGrassRing.x, 1));
            float share = _GfxGrassRing.z > 0.5 ? band : 1 - band;
            // Where the game's grass is coming in, tufts drop out one by one rather than all at once
            float keep = field.r * share * saturate((_GfxGrassRange.y - distance) / _GfxGrassRange.z) * saturate(1.3 - slope * 1.6) * (1 - loaded);
            bool showMasked = _GfxGrassCard.w > 1.5;
            bool none = any(fieldUV < 0) || any(fieldUV > 1) || ground < -9000 || c > keep || (masked && !showMasked);

            float scale = _GfxGrassRing.w * (0.75 + 0.5 * d);
            float3 foot = float3(unityXZ.x, ground - 0.15, unityXZ.y);
            float2 across = _WorldSpaceCameraPos.xz - foot.xz;
            across = dot(across, across) > 1e-6 ? normalize(across) : float2(0, 1);
            float3 right = float3(-across.y, 0, across.x);
            float tall = v.vertex.y * _GfxGrassCard.y * scale;
            float sway = sin(_Time.y * 1.6 + a * 6.28) * 0.06 * tall;
            float3 position = foot + right * (v.vertex.x * _GfxGrassCard.x * scale + sway) + float3(0, tall, 0);
            v.vertex = float4(none ? foot : position, 1);
            // Lit as the ground it stands on
            v.normal = float3(0, 1, 0);
            v.tangent = float4(right, 1);
            o.card = float4(v.texcoord.xy, floor(b * 4), field.g * 255);
            o.look = float4(0.8 + 0.3 * a, masked ? 1 : 0, 0, 0);
            #endif
        }

        void surf(Input i, inout SurfaceOutputStandard o)
        {
            float2 uv = float2((i.card.z + i.card.x) * 0.25, i.card.y);
            float alpha = tex2D(_GfxGrassBlades, uv).a;
            // Shrunk blades average their coverage down; lift it with the mipmap level so far grass doesn't thin out
            float2 texels = i.card.xy * float2(64, 64);
            float2 dx = ddx(texels), dy = ddy(texels);
            float mip = 0.5 * log2(max(max(dot(dx, dx), dot(dy, dy)), 1e-6));
            clip(alpha * (1 + max(mip, 0) * 0.3) - 0.5);

            float3 color = _GfxGrassColors[(uint)(i.card.w + 0.5) & 15].rgb;
            // Dark down among the blades, lighter at the tips: a meadow seen from afar is mostly its shade
            o.Albedo = color * lerp(0.45, 1.0, i.card.y) * i.look.x;
            o.Occlusion = lerp(0.35, 0.9, i.card.y);
            o.Smoothness = 0.05;
            o.Metallic = 0;
            if (_GfxGrassCard.w > 0.5)
            {
                o.Albedo = i.look.y > 0.5 ? float3(1, 0, 0) : float3(1, 0, 1);
                o.Emission = o.Albedo * 0.5;
            }
        }
        ENDCG
    }
}
