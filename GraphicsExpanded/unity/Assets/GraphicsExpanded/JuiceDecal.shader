// Game juice (GfxJuiceDecals): blood splattered on walls and floors, pools spreading under the dead, scorch marks
// left by explosions and the small dark pits bullets leave. Painted into the deferred G-buffer after the game has
// drawn every surface (and after the rain wetness pass), before reflections and lighting, so the game's lighting and
// Torch's light them like anything else.
//
// One DrawMeshInstancedIndirect of a box per mark, read from _GfxDecals. Each pixel inside a box finds the scene
// point behind it from the depth buffer and paints it if it lies close to the mark's surface and faces the same way,
// so the marks wrap onto what's there and skip what only passes through (a zombie's legs, a fence post).
//
// Two passes over the same boxes. The first blends into G-buffers 0 to 2 (bound like the rain wetness pass binds
// them): the diffuse by coverage; the specular color and, through the alpha channel, extra smoothness (wet blood
// gloss); the normals are left alone. The second darkens the light buffer (the camera's target, where the game has
// already added the ambient light) by the same amount the diffuse was, or dark marks would glow in the shade.
Shader "GraphicsExpanded/JuiceDecal"
{
    SubShader
    {
        CGINCLUDE
        #include "UnityCG.cginc"

        // Kinds (GfxJuiceDecals.Kind)
        #define SPLAT 0
        #define POOL 1
        #define SCORCH 2
        #define PIT 3

        struct Decal
        {
            float4 place;   // xyz: the middle (Unity), w: radius in meters
            float4 normal;  // xyz: the surface's normal; w: turn about it, radians (a splatter flies along the turned +x)
            float4 look;    // x: kind, y: seed 0 to 1, z: opacity 0 to 1, w: growth 0 to 1
            float4 color;   // rgb: diffuse color, a: smoothness
        };

        StructuredBuffer<Decal> _GfxDecals;
        float _GfxDecalDebug;           // 1: every mark's whole box in magenta, to see where they are
        UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);

        struct appdata
        {
            float4 vertex : POSITION;
            uint id : SV_InstanceID;
        };

        struct v2f
        {
            float4 pos : SV_POSITION;
            float4 screen : TEXCOORD0;
            float3 ray : TEXCOORD1;         // from the camera to this point of the box
            nointerpolation uint id : TEXCOORD2;
        };

        float Hash(float n)
        {
            return frac(sin(n * 12.9898 + 4.1414) * 43758.5453);
        }

        float Hash2(float2 p)
        {
            p = frac(p * float2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return frac(p.x * p.y);
        }

        float Noise(float2 p)
        {
            float2 i = floor(p);
            float2 f = frac(p);
            float2 u = f * f * (3 - 2 * f);
            return lerp(lerp(Hash2(i), Hash2(i + float2(1, 0)), u.x),
                        lerp(Hash2(i + float2(0, 1)), Hash2(i + 1), u.x), u.y);
        }

        // The surface frame: t and s along the surface, n out of it
        void Frame(Decal d, out float3 t, out float3 s, out float3 n)
        {
            n = normalize(d.normal.xyz);
            float3 a = normalize(cross(n, abs(n.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0)));
            float3 b = cross(n, a);
            float c = cos(d.normal.w), si = sin(d.normal.w);
            t = a * c + b * si;
            s = cross(n, t);
        }

        // Half the box's depth, along the normal
        float Depth(Decal d)
        {
            return min(d.place.w * 0.5, 0.35);
        }

        v2f vert(appdata v)
        {
            v2f o;
            Decal d = _GfxDecals[v.id];
            float3 t, s, n;
            Frame(d, t, s, n);
            float3 local = v.vertex.xyz * 2;
            float3 world = d.place.xyz + (t * local.x + s * local.z) * d.place.w + n * local.y * Depth(d);
            o.pos = mul(UNITY_MATRIX_VP, float4(world, 1));
            o.screen = ComputeScreenPos(o.pos);
            o.ray = world - _WorldSpaceCameraPos;
            o.id = v.id;
            return o;
        }

        float Splat(float2 q, float seed, float growth)
        {
            // A main blot just behind where it hit, and drops flung out along +x, smaller and longer further out
            float2 blot = (q + float2(0.18, 0)) / float2(0.42, 0.34);
            float mask = saturate((0.75 + 0.35 * Noise(q * 5 + seed * 30) - length(blot)) * 6);
            [unroll]
            for (int k = 0; k < 14; k++)
            {
                float h1 = Hash(seed * 97 + k * 1.37);
                float h2 = Hash(seed * 61 + k * 2.71);
                float h3 = Hash(seed * 23 + k * 4.13);
                float out_ = lerp(0.05, 0.92, h1);
                float2 center = float2(out_, (h2 - 0.5) * lerp(0.25, 0.95, out_));
                float radius = lerp(0.025, 0.1, h3) * (1.1 - out_ * 0.6);
                float2 offset = (q - center) / float2(radius * (1 + out_ * 2.2), radius);
                mask = max(mask, saturate((1 - dot(offset, offset)) * 3));
            }
            return mask * saturate(growth * 3);
        }

        float Pool(float2 q, float seed, float growth)
        {
            float r = length(q);
            float edge = (0.6 + 0.4 * Noise(q / max(r, 1e-4) * 1.8 + seed * 17)) * growth;
            return saturate((edge - r) * 14);
        }

        float Scorch(float2 q, float seed)
        {
            float r = length(q);
            float n = Noise(q * 3 + seed * 11) * 0.6 + Noise(q * 9 + seed * 5) * 0.4;
            return saturate((0.95 - r - 0.35 * n) * 2.5) * (0.75 + 0.25 * n);
        }

        float Pit(float2 q, float seed)
        {
            float r = length(q);
            float core = saturate((0.35 - r) * 12);
            float ring = saturate((0.8 - r - 0.25 * Noise(q * 6 + seed * 13)) * 6) * 0.45;
            return max(core, ring);
        }

        // How much of the mark covers this pixel's scene point, 0 to 1; discards the pixel where there's none
        float Cover(v2f i, out Decal d)
        {
            d = _GfxDecals[i.id];
            float3 t, s, n;
            Frame(d, t, s, n);

            // The scene point behind this pixel, and where it lies in the mark's box
            float2 uv = i.screen.xy / i.screen.w;
            float eye = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv));
            float3 forward = -UNITY_MATRIX_V[2].xyz;
            float3 world = _WorldSpaceCameraPos + i.ray * (eye / dot(i.ray, forward));
            float3 offset = world - d.place.xyz;
            float2 q = float2(dot(offset, t), dot(offset, s)) / d.place.w;
            float height = dot(offset, n) / Depth(d);

            // The surface's facing, from neighbouring pixels (before any are discarded)
            float3 surface = normalize(cross(ddy(world), ddx(world)));
            surface *= dot(surface, _WorldSpaceCameraPos - world) < 0 ? -1 : 1;
            if (_GfxDecalDebug > 0.5)
                return 1;
            clip(1 - max(max(abs(q.x), abs(q.y)), abs(height)));

            // Only on surfaces facing much the same way as the one it hit
            float facing = saturate((dot(surface, n) - 0.35) * 3);
            uint kind = (uint)(d.look.x + 0.5);
            float seed = d.look.y;
            float mask = kind == SPLAT ? Splat(q, seed, d.look.w)
                : kind == POOL ? Pool(q, seed, d.look.w)
                : kind == SCORCH ? Scorch(q, seed)
                : Pit(q, seed);
            float cover = saturate(mask * facing * d.look.z * saturate((1 - abs(height)) * 4));
            clip(cover - 0.004);
            return cover;
        }
        ENDCG

        // The G-buffer: diffuse, specular and smoothness
        Pass
        {
            Cull Front
            ZWrite Off
            ZTest Always
            Blend 0 SrcAlpha OneMinusSrcAlpha
            ColorMask RGB 0
            Blend 1 SrcAlpha OneMinusSrcAlpha, One OneMinusSrcAlpha
            ColorMask 0 2

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 4.5

            struct Output
            {
                float4 diffuse : SV_Target0;
                float4 specular : SV_Target1;
                float4 normal : SV_Target2;
            };

            Output frag(v2f i)
            {
                Decal d;
                float cover = Cover(i, d);
                Output o;
                o.diffuse = _GfxDecalDebug > 0.5 ? float4(1, 0, 1, 0.8) : float4(d.color.rgb, cover);
                o.specular = float4(0.04, 0.04, 0.04, d.color.a * cover);
                o.normal = 0;
                return o;
            }
            ENDCG
        }

        // The light buffer: what the game's ambient light already added, scaled to the new diffuse
        Pass
        {
            Cull Front
            ZWrite Off
            ZTest Always
            Blend Zero SrcColor
            ColorMask RGB

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 4.5

            float4 frag(v2f i) : SV_Target
            {
                Decal d;
                float cover = Cover(i, d);
                float3 darker = _GfxDecalDebug > 0.5 ? float3(1, 0.3, 1) : saturate(d.color.rgb / 0.35 + 0.15);
                return float4(lerp(1, darker, cover), 1);
            }
            ENDCG
        }
    }
}
