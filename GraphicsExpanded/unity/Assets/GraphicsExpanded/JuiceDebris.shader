// Game juice (GfxJuice): the solid bits that fly, bounce and lie about for a while, spent casings, wood splinters,
// stone and concrete chunks, glass shards and dirt clods (GfxJuiceDebris). One DrawMeshInstancedIndirect per kind of
// mesh, each piece's place, turn, size and color read from _GfxDebris.
//
// It's a deferred surface shader, so the pieces go into the G-buffer like any other surface and the game's sun,
// shadows, ambient light and fog (and Torch) light them. Pieces on their way out fade dithered rather than popping.
Shader "GraphicsExpanded/JuiceDebris"
{
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }

        CGPROGRAM
        #pragma surface surf Standard vertex:vert exclude_path:prepass nolightmap nodynlightmap nodirlightmap nometa noforwardadd
        #pragma multi_compile_instancing
        #pragma instancing_options procedural:setup
        #pragma target 4.5

        struct Piece
        {
            float4 row0;        // the piece's object-to-world matrix (Unity space), top three rows
            float4 row1;
            float4 row2;
            float4 color;       // rgb: albedo, a: smoothness
            float4 surface;     // x: metallic, y: glow (emission as a multiple of the albedo), z: how much shows, 0 to 1
        };

        #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
        StructuredBuffer<Piece> _GfxDebris;
        #endif

        struct Input
        {
            float4 tint;            // the piece's color and surface (Piece.color, .surface); not named color, which surface shaders take as vertex color
            float4 finish;
            float4 screenPos;
            float3 facet;           // the face's own normal, for a tone per face
        };

        void setup()
        {
            #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
            Piece p = _GfxDebris[unity_InstanceID];
            unity_ObjectToWorld = float4x4(p.row0, p.row1, p.row2, float4(0, 0, 0, 1));
            // The inverse, for the normals: the 3x3 part's inverse and the moved-back translation
            float3x3 m = (float3x3)unity_ObjectToWorld;
            float3 c0 = cross(m[1], m[2]);
            float3 c1 = cross(m[2], m[0]);
            float3 c2 = cross(m[0], m[1]);
            float det = dot(m[0], c0);
            float3x3 inv = transpose(float3x3(c0, c1, c2)) / (abs(det) > 1e-12 ? det : 1e-12);
            float3 t = float3(p.row0.w, p.row1.w, p.row2.w);
            float3 back = -mul(inv, t);
            unity_WorldToObject = float4x4(float4(inv[0], back.x), float4(inv[1], back.y), float4(inv[2], back.z), float4(0, 0, 0, 1));
            #endif
        }

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            #ifdef UNITY_PROCEDURAL_INSTANCING_ENABLED
            Piece p = _GfxDebris[unity_InstanceID];
            o.tint = p.color;
            o.finish = p.surface;
            #endif
            o.facet = v.normal;
        }

        float Hash(float3 p)
        {
            p = frac(p * float3(0.1031, 0.1030, 0.0973));
            p += dot(p, p.yxz + 33.33);
            return frac((p.x + p.y) * p.z);
        }

        void surf(Input i, inout SurfaceOutputStandard o)
        {
            // On its way out: a screen-door pattern of the right density, steady from frame to frame
            float2 pixel = i.screenPos.xy / max(i.screenPos.w, 1e-5) * _ScreenParams.xy;
            clip(i.finish.z - frac(52.9829189 * frac(dot(pixel, float2(0.06711056, 0.00583715)))) - 0.001);

            // Each face a slightly different tone, like broken stone or wood, so a pile doesn't look like plastic
            float tone = 0.8 + 0.35 * Hash(floor(i.facet * 3 + 3.5));
            o.Albedo = saturate(i.tint.rgb * tone);
            o.Smoothness = i.tint.a;
            o.Metallic = i.finish.x;
            o.Emission = i.tint.rgb * i.finish.y;
            o.Occlusion = 1;
        }
        ENDCG
    }
}
