// Game juice (GfxJuice): the sparks, dust, smoke, blood drops, tracers, glints and rings thrown off by fights,
// gunfire, breaking things, footsteps and rewards. Every bit is moved on the CPU (GfxJuiceParticles) and drawn here in
// one DrawMeshInstancedIndirect of a quad, each instance read from _GfxJuiceBits.
//
// Drawn after the opaque scene with premultiplied alpha, so glowing bits add light and lit ones (dust, smoke, blood,
// chips) cover what's behind them; depth tested, not written, and soft where they meet surfaces. Lit bits take the
// sky's ambient light and the sun (when outdoors) the way the ambient motes do; glowing ones are their own light.
Shader "GraphicsExpanded/Juice"
{
    SubShader
    {
        Tags { "Queue"="Transparent+30" "RenderType"="Transparent" "IgnoreProjector"="True" }

        Pass
        {
            Tags { "LightMode"="ForwardBase" }
            Blend One OneMinusSrcAlpha
            ZWrite Off
            Cull Off

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 4.5
            #pragma multi_compile_fog
            #include "UnityCG.cginc"

            // The shapes (GfxJuiceParticles.Shape)
            #define PUFF 0
            #define SPARK 1
            #define DROP 2
            #define CLOD 3
            #define RING 4
            #define GLINT 5
            #define FLASH 6
            #define LEAF 7
            #define SMOKE 8

            // Flags
            #define LIT 1
            #define FLAT 2
            #define SOFT 4

            struct Bit
            {
                float4 place;   // xyz: where (Unity), w: half its width in meters
                float4 color;   // rgb: a lit bit's own color, or the light a glowing one adds; a: how much it covers
                float4 axis;    // xyz: a stretched bit's half length along its motion, or the way a flat one faces; w: turn, radians
                float4 info;    // x: shape, y: seed 0 to 1, z: age 0 to 1, w: flags
            };

            StructuredBuffer<Bit> _GfxJuiceBits;
            float4 _GfxJuiceSun;            // rgb: the sunlight reaching bits out in the open (already scaled for how far it's up)
            UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);

            struct appdata
            {
                float4 vertex : POSITION;
                uint id : SV_InstanceID;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;      // -1 to 1 across the bit; on stretched ones y runs along the motion, caps included
                float4 color : TEXCOORD1;   // rgb: lit already, a: cover
                float4 info : TEXCOORD2;    // x shape, y seed, z age, w: a stretched bit's half length in half widths (0 round)
                float4 screen : TEXCOORD3;
                float2 fade : TEXCOORD4;    // x: 1 / meters of soft edge (0: hard), y: eye depth
                UNITY_FOG_COORDS(5)
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

            float Fbm(float2 p)
            {
                return Noise(p) * 0.55 + Noise(p * 2.1 + 17.3) * 0.3 + Noise(p * 4.3 + 41.9) * 0.15;
            }

            v2f vert(appdata v)
            {
                v2f o;
                Bit b = _GfxJuiceBits[v.id];
                uint flags = (uint)(b.info.w + 0.5);
                float2 corner = v.vertex.xy * 2;
                float width = b.place.w;
                float3 center = b.place.xyz;
                float spin = b.axis.w;
                float2 turned = float2(corner.x * cos(spin) - corner.y * sin(spin), corner.x * sin(spin) + corner.y * cos(spin));
                float length_ = length(b.axis.xyz);
                float3 world;
                float stretch = 0;
                if (flags & FLAT)
                {
                    // Lying flat on a surface, facing the way axis points
                    float3 n = length_ > 1e-5 ? b.axis.xyz / length_ : float3(0, 1, 0);
                    float3 t = normalize(cross(n, abs(n.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0)));
                    float3 s = cross(n, t);
                    world = center + (t * turned.x + s * turned.y) * width + n * 0.03;
                }
                else if (length_ > 1e-4)
                {
                    // Stretched along its motion, turned about that line to face the camera
                    float3 along = b.axis.xyz / length_;
                    float3 side = cross(along, normalize(_WorldSpaceCameraPos - center));
                    float sideLength = length(side);
                    side = sideLength > 1e-4 ? side / sideLength : float3(0, 1, 0);
                    world = center + side * corner.x * width + along * corner.y * (length_ + width);
                    stretch = length_ / max(width, 1e-4);
                }
                else
                {
                    // Round, facing the camera, turned
                    world = center + (UNITY_MATRIX_V[0].xyz * turned.x + UNITY_MATRIX_V[1].xyz * turned.y) * width;
                }

                o.pos = mul(UNITY_MATRIX_VP, float4(world, 1));
                o.uv = corner;
                // The game's sky ambient is much brighter than what its surfaces end up lit by; half of it matches better
                float3 light = (flags & LIT) ? ShadeSH9(float4(0, 1, 0, 1)) * 0.5 + _GfxJuiceSun.rgb : 1;
                o.color = float4(b.color.rgb * light, b.color.a);
                o.info = float4(b.info.xyz, stretch);
                o.screen = ComputeScreenPos(o.pos);
                o.fade = float2((flags & SOFT) ? 1 / max(width, 0.05) : 0, -mul(UNITY_MATRIX_V, float4(world, 1)).z);
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                uint shape = (uint)(i.info.x + 0.5);
                float seed = i.info.y;
                float age = i.info.z;
                float2 uv = i.uv;
                float r = length(uv);
                float3 color = i.color.rgb;
                float mask;

                // Along a stretched bit: distance from its middle line in half widths, and 0 at the tail to 1 at the head
                float stretch = i.info.w;
                float along = uv.y * (stretch + 1);
                float line_ = length(float2(uv.x, max(abs(along) - stretch, 0)));
                float head = saturate((along + stretch + 1) / (2 * stretch + 2));

                if (shape == SPARK)
                {
                    mask = exp(-line_ * line_ * 5) * lerp(0.1, 1, head * head);
                }
                else if (shape == DROP)
                {
                    mask = saturate((1 - line_) * 5) * lerp(0.55, 1, head);
                    color *= 0.8 + 0.4 * saturate(uv.x * 0.5 + 0.5);
                }
                else if (shape == CLOD)
                {
                    float edge = 0.55 + 0.4 * Noise(uv / max(r, 1e-4) * 1.6 + seed * 41);
                    mask = saturate((edge - r) * 10);
                    color *= 0.7 + 0.3 * saturate(0.5 + uv.y * 0.6) + 0.15 * (Noise(uv * 4 + seed * 9) - 0.5);
                }
                else if (shape == RING)
                {
                    float band = (r - 0.72) * 6;
                    mask = exp(-band * band) * saturate((1 - r) * 5) * (0.55 + 0.6 * Noise(uv / max(r, 1e-4) * 3 + seed * 13));
                }
                else if (shape == GLINT)
                {
                    float rays = exp(-abs(uv.x) * 22) * saturate(1 - abs(uv.y)) + exp(-abs(uv.y) * 22) * saturate(1 - abs(uv.x));
                    mask = rays + exp(-r * r * 40) * 1.5;
                }
                else if (shape == FLASH)
                {
                    float angle = atan2(uv.y, uv.x);
                    float rays = Noise(float2(angle * 3.5 + seed * 20, seed * 7));
                    mask = exp(-r * r * 6) * 1.4 + exp(-r * r * 2.2) * rays * rays * 0.6;
                }
                else if (shape == LEAF)
                {
                    float halfWidth = 0.42 * sqrt(saturate(1 - uv.y * uv.y)) * (1 - 0.25 * uv.y);
                    mask = saturate((halfWidth - abs(uv.x)) * 18);
                    color *= 1 - 0.35 * exp(-uv.x * uv.x * 600) * step(abs(uv.y), 0.9);
                    color *= 0.85 + 0.3 * Noise(uv * 3 + seed * 17);
                }
                else if (shape == SMOKE)
                {
                    float n = Fbm(uv * 1.3 + seed * 53 + age * float2(0.35, -0.7));
                    mask = saturate((1 - r * r) * (0.25 + 1.3 * n) - 0.12);
                    color *= 0.8 + 0.4 * n;
                }
                else
                {
                    // PUFF: a soft, ragged cloud of dust or spray
                    float n = Fbm(uv * 1.8 + seed * 37 + float2(0, age * 0.8));
                    mask = saturate((1 - r) * (0.55 + n) * 1.4 - 0.12);
                    mask *= mask;
                }

                // Soft where it meets a surface, and gone right in front of the eye
                float fade = saturate((i.fade.y - 0.12) * 4);
                if (i.fade.x > 0)
                {
                    float scene = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE_PROJ(_CameraDepthTexture, UNITY_PROJ_COORD(i.screen)));
                    fade *= saturate((scene - i.fade.y) * i.fade.x * 2);
                }
                mask = saturate(mask) * fade;

                float cover = mask * i.color.a;
                float4 result = float4(color * (i.color.a > 0 ? cover : mask), cover);
                // Covering bits fade into the fog's color, glowing ones into nothing
                UNITY_APPLY_FOG_COLOR(i.fogCoord, result.rgb, unity_FogColor.rgb * result.a);
                return result;
            }
            ENDCG
        }
    }
}
