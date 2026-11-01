// Ambient life (GfxAmbience): small, slow movement in the air around the player. One DrawMeshInstancedIndirect of a
// small quad; each instance works out what it is from its number (motes first, then leaves) and where it is from the
// time alone, so nothing is simulated. Motes are points fixed in the world that drift and wander, wrapped into a box
// that follows the camera (fading out towards its sides, so none pops at the wrap):
// - motes: pollen in the forest, dust in the desert and wasteland, ash flakes in the burnt forest, ice crystals in the
//   snow. Pollen, dust and ice add light where the sun's light scatters forward to the eye, so they glint looking into
//   the sun and in its beams; ash covers what's behind, lit by the sun and sky;
// - leaves: tumbling down from the crowns of the broadleaf trees nearest the player (GfxAmbience finds them), carried
//   along the wind, the odd one at a time.
// Drawn after the opaque scene with premultiplied alpha, so glints add and leaves cover, depth tested, not written.
Shader "GraphicsExpanded/Ambience"
{
    SubShader
    {
        Tags { "Queue"="Transparent+20" "RenderType"="Transparent" "IgnoreProjector"="True" }

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
            #include "UnityCG.cginc"

            float4 _GfxOrigin;              // xyz: the game's Origin.position (world = Unity + this)
            float4 _GfxAmbCounts;           // how many of each, in order: x motes, y leaves; w: trees in _GfxAmbTrees
            float4 _GfxAmbMotes;            // x: how much they show, 0 to 1, y: kind (0 pollen, 1 dust, 2 ash, 3 ice), z: box width, w: box height
            float4 _GfxAmbLeaves;           // x: how much they show
            float4 _GfxAmbTrees[16];        // broadleaf trees near the player: xyz the middle of the crown (Unity), w its radius
            float4 _GfxAmbSun;              // xyz: towards the sun, w: how far it's up, 0 to 1
            float4 _GfxAmbSunColor;         // rgb: its light
            float4 _GfxAmbGround;           // x: the ground under the player (Unity y), y: unused, z: debug (1 magenta)
            float4 _GfxAmbWind;             // xy: the game's wind direction (world x, z), z: how windy, 0 to 1

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                uint id : SV_InstanceID;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float4 color : TEXCOORD1;   // premultiplied: rgb what it adds, a how much it covers what's behind
                float shape : TEXCOORD2;    // 0 a soft dot, 1 a leaf
            };

            float3 Hash3(float n)
            {
                float3 p = frac(n * float3(0.1031, 0.1030, 0.0973));
                p += dot(p, p.yzx + 33.33);
                return frac((p.xxy + p.yzz) * p.zyx);
            }

            // A point fixed in the world (it moves only as it drifts), wrapped into a box that follows the camera
            float3 Wrap(float3 p, float3 center, float3 size)
            {
                return p - size * floor((p - (center - size * 0.5)) / size);
            }

            // Fades towards the box's sides, so nothing pops where it wraps
            float EdgeFade(float3 p, float3 center, float3 size)
            {
                float3 e = abs(p - center) / (size * 0.5);
                return saturate((1 - max(e.x, e.z)) * 5) * saturate((1 - e.y) * 5);
            }

            // Meters a pixel covers at this distance
            float PixelSize(float distance)
            {
                return 2 * distance / (_ScreenParams.y * UNITY_MATRIX_P._m11);
            }

            float4 Facing(float3 unity, float2 corner, float size)
            {
                float3 right = UNITY_MATRIX_V[0].xyz, up = UNITY_MATRIX_V[1].xyz;
                return mul(UNITY_MATRIX_VP, float4(unity + (right * corner.x + up * corner.y) * size, 1));
            }

            float4 Debug(float shows)
            {
                return shows > 0.001 ? float4(1, 0, 1, 1) : 0;
            }

            void Mote(float i, float2 corner, float3 eye, inout v2f o)
            {
                float3 h = Hash3(i + 0.5);
                float kind = _GfxAmbMotes.y;
                float3 size = float3(_GfxAmbMotes.z, _GfxAmbMotes.w, _GfxAmbMotes.z);
                float t = _Time.y;
                // Drifts with the wind and wanders a little of its own; ash and ice crystals sink
                float3 wind = float3(_GfxAmbWind.x, 0, _GfxAmbWind.y) * (0.3 + 0.7 * _GfxAmbWind.z);
                float sink = kind > 1.5 ? 0.3 : 0.03;
                float3 wander = float3(sin(t * (0.3 + 0.2 * h.y) + h.x * 40), 0.6 * sin(t * (0.25 + 0.2 * h.z) + h.y * 40), cos(t * (0.3 + 0.2 * h.x) + h.z * 40)) * 0.7;
                float3 p = h * size + wind * t - float3(0, sink * t, 0) + wander;
                // From a little below the eye to well above it
                float3 center = eye + float3(0, size.y * 0.5 - 2.5, 0);
                p = Wrap(p, center, size);
                float3 unity = p - _GfxOrigin.xyz;
                float3 toMote = unity - _WorldSpaceCameraPos;
                float distance = length(toMote);
                float3 view = toMote / max(distance, 1e-3);

                // At least a pixel and a half across, dimmer when grown to that
                float tiny = kind > 2.5 ? 0.02 : kind > 1.5 ? 0.035 : 0.018;
                float across = max(tiny, PixelSize(distance) * 1.5);
                float dim = (tiny / across) * (tiny / across);
                float shows = _GfxAmbMotes.x * EdgeFade(p, center, size) * saturate((distance - 0.4) / 0.6);
                float3 sun = _GfxAmbSunColor.rgb * _GfxAmbSun.w;
                if (kind > 1.5 && kind < 2.5)
                {
                    // Ash: grey flakes lit by the sun and sky, covering what's behind
                    float3 lit = float3(0.5, 0.48, 0.46) * (0.35 * sun + ShadeSH9(float4(0, 1, 0, 1)));
                    o.color = float4(lit, 1) * shows * 0.85;
                }
                else
                {
                    // Glints where the sun's light scatters forward towards the eye
                    float forward = saturate(dot(view, _GfxAmbSun.xyz));
                    float glint = 0.1 + 0.6 * pow(forward, 3) + 3.5 * pow(forward, 12);
                    float3 tint = kind < 0.5 ? float3(1, 0.93, 0.72) : kind < 1.5 ? float3(0.95, 0.85, 0.7) : float3(0.9, 0.95, 1);
                    // Ice crystals flash as they turn
                    float sparkle = kind > 2.5 ? 0.3 + 4 * pow(saturate(sin(t * (2 + 3 * h.x) + h.y * 30)), 16) : 1;
                    o.color = float4(tint * sun * glint * sparkle * 0.6, 0) * shows * dim;
                }
                if (_GfxAmbGround.z > 0.5)
                {
                    o.color = Debug(shows);
                    across = max(across, 0.08);
                }
                o.pos = Facing(unity, corner, across);
                o.shape = 0;
            }

            void Leaf(float i, float2 corner, inout v2f o)
            {
                uint trees = (uint)_GfxAmbCounts.w;
                if (trees == 0)
                    return;
                float3 h = Hash3(i * 2.11 + 503.5);
                float4 tree = _GfxAmbTrees[(uint)i % trees];
                float t = _Time.y;
                // Each fall starts somewhere new in the crown, and not every leaf falls every time
                float fall = 6 + 5 * h.x;
                float cycle = t / fall + h.y;
                float turn = floor(cycle);
                float phase = cycle - turn;
                float3 r = Hash3(turn * 7.31 + i * 0.73 + 11.5);
                float falls = r.z < 0.25 + 0.25 * _GfxAmbWind.z ? 1 : 0;
                float angle = r.x * 6.2832;
                float radius = sqrt(r.y) * tree.w;
                float3 start = tree.xyz + float3(cos(angle) * radius, (r.z - 0.5) * tree.w * 0.6, sin(angle) * radius);
                float drop = max(start.y - _GfxAmbGround.x, 1);
                // Down to about the ground, carried along the wind and swinging from side to side
                float3 wind = float3(_GfxAmbWind.x, 0, _GfxAmbWind.y);
                float3 p = start - float3(0, phase * drop, 0)
                         + wind * phase * drop * (0.2 + 0.5 * _GfxAmbWind.z)
                         + float3(sin(t * 1.7 + h.z * 20), 0, cos(t * 1.3 + h.x * 20)) * 0.6 * sin(phase * 3.1416);
                // Tumbling as it goes
                float a = t * (2 + 2 * h.y) + h.x * 10, b = t * (1.3 + h.z) + h.y * 10;
                float3 along = float3(cos(a), sin(a) * cos(b), sin(a) * sin(b));
                float3 side = normalize(cross(along, float3(0.3, 1, 0.2)));
                float3 normal = cross(along, side);
                float leafSize = 0.07;
                o.pos = mul(UNITY_MATRIX_VP, float4(p + (along * corner.x * 1.4 + side * corner.y) * leafSize, 1));

                float3 green = lerp(float3(0.13, 0.19, 0.04), float3(0.32, 0.28, 0.07), h.z * h.z);
                float lit = 0.35 + 0.65 * abs(dot(normal, _GfxAmbSun.xyz));
                float3 color = green * (ShadeSH9(float4(0, 1, 0, 1)) + _GfxAmbSunColor.rgb * _GfxAmbSun.w * lit * 0.5);
                float shows = _GfxAmbLeaves.x * falls * saturate(phase * 8) * saturate((1 - phase) * 8);
                o.color = float4(color, 1) * shows;
                if (_GfxAmbGround.z > 0.5)
                    o.color = Debug(shows);
                o.shape = 1;
            }

            v2f vert(appdata v)
            {
                v2f o = (v2f)0;
                o.uv = v.uv;
                o.pos = float4(2, 2, 2, 1);
                float2 corner = v.vertex.xy;
                float3 eye = _WorldSpaceCameraPos + _GfxOrigin.xyz;
                uint motes = (uint)_GfxAmbCounts.x;
                if (v.id < motes)
                    Mote(v.id, corner, eye, o);
                else
                    Leaf(v.id - motes, corner, o);
                // Nothing to show: off screen, so it costs nothing to draw
                if (max(max(o.color.r, o.color.g), max(o.color.b, o.color.a)) <= 0)
                    o.pos = float4(2, 2, 2, 1);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float2 d = i.uv * 2 - 1;
                float r2 = dot(d, d);
                float cover;
                if (i.shape < 0.5)
                {
                    cover = saturate(1 - r2);
                    cover *= cover;
                }
                else
                {
                    // A leaf: an oval with soft edges
                    float2 q = d * float2(1, 1.7);
                    cover = saturate((1 - dot(q, q)) * 4);
                }
                return i.color * cover;
            }
            ENDCG
        }
    }
}
