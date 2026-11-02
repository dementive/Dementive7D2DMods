// Game juice (GfxJuice): the bits that bend light instead of adding any, the heat shimmer over a hot gun barrel and
// the shockwave ring of an explosion. Like Juice.shader, one DrawMeshInstancedIndirect of a camera-facing quad per
// bit, read from _GfxJuiceWarps; each one redraws what's behind it from a grab of the screen, pushed aside.
Shader "GraphicsExpanded/JuiceWarp"
{
    SubShader
    {
        Tags { "Queue"="Transparent+40" "RenderType"="Transparent" "IgnoreProjector"="True" }

        GrabPass { "_GfxJuiceGrab" }

        Pass
        {
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 4.5
            #include "UnityCG.cginc"

            #define SHIMMER 0
            #define SHOCKWAVE 1

            struct Bit
            {
                float4 place;   // xyz: where (Unity), w: half its width in meters
                float4 color;   // a: strength
                float4 axis;    // unused
                float4 info;    // x: shape, y: seed 0 to 1, z: age 0 to 1
            };

            StructuredBuffer<Bit> _GfxJuiceWarps;
            sampler2D _GfxJuiceGrab;

            struct appdata
            {
                float4 vertex : POSITION;
                uint id : SV_InstanceID;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float4 grab : TEXCOORD1;
                float4 info : TEXCOORD2;    // x shape, y seed, z age, w: strength in screen heights
            };

            float Hash(float2 p)
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
                return lerp(lerp(Hash(i), Hash(i + float2(1, 0)), u.x),
                            lerp(Hash(i + float2(0, 1)), Hash(i + 1), u.x), u.y);
            }

            v2f vert(appdata v)
            {
                v2f o;
                Bit b = _GfxJuiceWarps[v.id];
                float2 corner = v.vertex.xy * 2;
                float3 world = b.place.xyz + (UNITY_MATRIX_V[0].xyz * corner.x + UNITY_MATRIX_V[1].xyz * corner.y) * b.place.w;
                o.pos = mul(UNITY_MATRIX_VP, float4(world, 1));
                o.uv = corner;
                o.grab = ComputeGrabScreenPos(o.pos);
                // How big the bit is on screen, as a share of the screen's height, so the push scales with it
                float depth = max(-mul(UNITY_MATRIX_V, float4(world, 1)).z, 0.1);
                o.info = float4(b.info.xyz, b.color.a * b.place.w / depth * unity_CameraProjection._m11 * 0.5);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                float r = length(i.uv);
                float2 push;
                float mask;
                if ((uint)(i.info.x + 0.5) == SHOCKWAVE)
                {
                    // A ring pushing outwards, sharp at its front
                    float band = (r - 0.8) * 7;
                    mask = exp(-band * band) * saturate((1 - r) * 8);
                    push = i.uv / max(r, 1e-4) * mask * 0.35;
                }
                else
                {
                    // Rising, wavering haze
                    float2 flow = i.uv * 2.5 + float2(i.info.y * 31, -_Time.y * 2.2);
                    push = float2(Noise(flow) - 0.5, Noise(flow + 19.7) - 0.5) * 0.5;
                    mask = saturate(1 - r * r);
                }
                push *= i.info.w;
                #if UNITY_UV_STARTS_AT_TOP
                push.y = -push.y;
                #endif
                float4 grab = i.grab;
                grab.xy += push * grab.w;
                float3 behind = tex2Dproj(_GfxJuiceGrab, UNITY_PROJ_COORD(grab)).rgb;
                return float4(behind, saturate(mask * 4));
            }
            ENDCG
        }
    }
}
