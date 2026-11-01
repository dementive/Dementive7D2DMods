// The water surface, in place of the game's own: GfxWater puts it on the water material while it's on and gives the
// game's shader back when it's off. For each pixel of water it:
// - bends what's under it (a grab of the picture before any water) and dims and tints it by how much water the light
//   goes through: clear in the shallows, deep blue-green further down;
// - reflects the world: the game's reflection probe (the sky and what's around the player), and on High a ray marched
//   across the screen to find the shores, trees and buildings it hits;
// - adds the sun's glint, foam where it meets the shore, and rings while it rains.
// Waves are the game's own water normal map, scrolled two ways. Fog and distance haze go on top like the rest of the
// world. Only the game's water mesh draws with it, and nothing it does is sent anywhere.
Shader "GraphicsExpanded/Water"
{
    Properties
    {
        _MainTex ("Water", 2D) = "white" {}
        _BumpMap ("Waves", 2D) = "bump" {}
        // The far, low-detail water: the game's map of loaded chunks (green where near water is drawn) and the
        // world's size, and _GfxDistant 1 on that material only
        _ClipChunks ("Loaded chunks", 2D) = "black" {}
        _WorldDim ("World size", Vector) = (6144, 6144, 0, 0)
        _GfxDistant ("Far water", Float) = 0
    }

    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "IgnoreProjector" = "True" }

        // Everything behind the water, once a frame, before the first water is drawn
        GrabPass { "_GfxWaterGrab" }

        Pass
        {
            Tags { "LightMode" = "ForwardBase" }
            Cull Off
            ZWrite On

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5
            #pragma multi_compile_fog
            #include "UnityCG.cginc"
            #include "GfxHaze.cginc"

            sampler2D _BumpMap;
            sampler2D _ClipChunks;
            float4 _WorldDim;
            float _GfxDistant;
            sampler2D _GfxWaterGrab;
            UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);

            float4 _GfxWater;           // x: wave strength 0 to 2, y: rain 0 to 1, z: 1 for screen-space reflections, w: 1 when the game's reflection probe is on
            float4 _GfxWaterOrigin;     // xyz: the floating origin, so the waves don't jump when it moves
            float4 _GfxWaterLightDir;   // xyz: towards the sun or moon, w: how much the player is outdoors (no glints indoors)
            float4 _GfxWaterLight;      // rgb: its light
            float4 _GfxWaterSky;        // rgb: the sky overhead, for reflections when the game's probe is off
            float4 _GfxWaterHorizon;    // rgb: the sky at the horizon (the game's fog color), also the light the water body is lit by
            float _GfxWaterDebug;       // 1: show what the reflections found instead (gfxe water debug)

            struct appdata
            {
                float4 vertex : POSITION;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 world : TEXCOORD0;
                float4 screen : TEXCOORD1;
                float4 grab : TEXCOORD2;
                float eye : TEXCOORD3;
                UNITY_FOG_COORDS(4)
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.screen = ComputeScreenPos(o.pos);
                o.grab = ComputeGrabScreenPos(o.pos);
                COMPUTE_EYEDEPTH(o.eye);
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }

            float Hash(float2 p)
            {
                return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453);
            }

            // How far the light travels through water to reach the eye at this screen spot (eye depths of the
            // surface and of what's behind it)
            float BehindDepth(float2 screenUv)
            {
                return LinearEyeDepth(SAMPLE_DEPTH_TEXTURE_LOD(_CameraDepthTexture, float4(screenUv, 0, 0)));
            }

            // Rain: rings spreading from random drops, one per 0.7 m cell in two offset layers. Returns the tilt they give
            // the surface in x and z.
            float2 RainRings(float2 p, float time)
            {
                float2 tilt = 0;
                for (int layer = 0; layer < 2; layer++)
                {
                    float2 q = p / 0.7 + layer * 0.5;
                    float2 cell = floor(q);
                    float seed = Hash(cell + layer * 17.3);
                    float2 center = float2(Hash(cell + 3.1), Hash(cell + 7.7)) * 0.6 + 0.2;
                    float age = frac(time * 0.9 + seed);
                    float2 away = frac(q) - center;
                    float r = length(away);
                    float ring = r - age * 0.45;
                    float wave = sin(ring * 60) * exp(-ring * ring * 900) * (1 - age);
                    tilt += away / max(r, 1e-3) * wave * 0.35;
                }
                return tilt;
            }

            // The reflection probe, or a plain sky when the game has reflections off
            float3 Surroundings(float3 dir, float blur)
            {
                float3 sky = lerp(_GfxWaterHorizon.rgb, _GfxWaterSky.rgb, sqrt(saturate(dir.y)));
                float3 probe = DecodeHDR(UNITY_SAMPLE_TEXCUBE_LOD(unity_SpecCube0, dir, blur), unity_SpecCube0_HDR);
                return _GfxWater.w > 0.5 ? probe : sky;
            }

            // High: march the reflected ray across the screen until it passes behind something the camera sees. Returns
            // what it hit in rgb, and in a how sure it is (0 where it found nothing or ran off the screen).
            float4 ScreenReflection(float3 start, float3 dir, float jitter)
            {
                float step = 0.4 + 0.004 * length(start - _WorldSpaceCameraPos);
                float3 p = start + dir * step * jitter;
                float4 result = 0;
                [loop]
                for (int s = 0; s < 32; s++)
                {
                    p += dir * step;
                    float4 clip = mul(UNITY_MATRIX_VP, float4(p, 1));
                    float4 screen = ComputeScreenPos(clip);
                    float2 uv = screen.xy / max(screen.w, 1e-4);
                    if (clip.w <= 0.05 || any(uv < 0) || any(uv > 1))
                        break;
                    float behind = BehindDepth(uv);
                    if (clip.w > behind && clip.w - behind < step * 2 + 0.5 && behind < _ProjectionParams.z * 0.98)
                    {
                        // Halve back and forth to the surface it crossed
                        float3 low = p - dir * step;
                        float3 high = p;
                        [unroll]
                        for (int k = 0; k < 4; k++)
                        {
                            float3 mid = (low + high) * 0.5;
                            float4 c = mul(UNITY_MATRIX_VP, float4(mid, 1));
                            float4 sc = ComputeScreenPos(c);
                            if (c.w > BehindDepth(sc.xy / max(sc.w, 1e-4)))
                                high = mid;
                            else
                                low = mid;
                        }
                        float4 hitClip = mul(UNITY_MATRIX_VP, float4(high, 1));
                        float4 grab = ComputeGrabScreenPos(hitClip);
                        float2 hitUv = ComputeScreenPos(hitClip).xy / max(hitClip.w, 1e-4);
                        float2 edge = min(hitUv, 1 - hitUv);
                        float sure = saturate(min(edge.x, edge.y) * 10) * (1 - s / 32.0);
                        result = float4(tex2Dlod(_GfxWaterGrab, float4(grab.xy / max(grab.w, 1e-4), 0, 0)).rgb, sure);
                        break;
                    }
                    step *= 1.15;
                }
                return result;
            }

            float4 frag(v2f i) : SV_Target
            {
                // The far water steps aside wherever the near water is drawn, as the game's own far water does
                if (_GfxDistant > 0.5)
                {
                    float2 chunk = (i.world.xz + _GfxWaterOrigin.xz) / _WorldDim.xy + 0.5;
                    if (tex2Dlod(_ClipChunks, float4(chunk, 0, 0)).g > 0.5)
                        discard;
                }

                float3 toEye = _WorldSpaceCameraPos - i.world;
                float distance = length(toEye);
                float3 V = toEye / max(distance, 1e-4);
                // The surface's own facing, turned towards the camera
                float3 flat = normalize(cross(ddx(i.world), ddy(i.world)));
                if (dot(flat, V) < 0)
                    flat = -flat;
                float2 screenUv = i.screen.xy / i.screen.w;
                float2 grabUv = i.grab.xy / i.grab.w;

                // Looking up from under the water: what's above, tinted, without the rest
                if (flat.y < -0.3)
                {
                    float3 above = tex2D(_GfxWaterGrab, grabUv).rgb * float3(0.55, 0.8, 0.85);
                    UNITY_APPLY_FOG(i.fogCoord, above);
                    return float4(above, 1);
                }

                // Waves, on level water only, fading out with distance where they'd only shimmer
                float time = _Time.y;
                float2 p = i.world.xz + _GfxWaterOrigin.xz;
                float level = saturate(flat.y * 2 - 1);
                float strength = _GfxWater.x * level * saturate(1.2 - distance / 250);
                float3 a = UnpackNormal(tex2D(_BumpMap, p * 0.11 + time * float2(0.021, 0.013)));
                float3 b = UnpackNormal(tex2D(_BumpMap, p * 0.29 + time * float2(-0.017, 0.029)));
                // Gentle up close, where every ripple shows; a little livelier further out, where they blend into a sparkle
                float choppy = lerp(0.18, 0.45, saturate(distance / 30));
                float2 tilt = (a.xy * 0.6 + b.xy * 0.4) * choppy * strength;
                if (_GfxWater.y > 0)
                    tilt += RainRings(p, time) * _GfxWater.y * level;
                float3 N = normalize(flat + float3(tilt.x, 0, tilt.y) * level);

                // What's under the water, bent a little by the waves, unless that would pick up something in front of it
                float behind = BehindDepth(screenUv);
                float2 bend = tilt * 0.035 * saturate((behind - i.eye) * 0.5);
                float2 bentScreen = screenUv + bend;
                float behindBent = BehindDepth(bentScreen);
                if (behindBent < i.eye)
                {
                    bend = 0;
                    behindBent = behind;
                }
                float3 under = tex2D(_GfxWaterGrab, grabUv + bend).rgb;
                // Meters of water the light comes through (along the view), from the eye depths, and how deep the
                // water is straight down there
                float path = max(behindBent - i.eye, 0) * distance / max(i.eye, 1e-3);
                float deep = max(behind - i.eye, 0) * distance / max(i.eye, 1e-3) * max(V.y, 0.05);
                float shallow = saturate(deep / 0.05);

                // Red goes first, then green: shallows stay clear, deeper water turns blue-green and dark
                float3 through = exp(-path * float3(0.42, 0.11, 0.075));
                float sunHeight = saturate(_GfxWaterLightDir.y);
                float3 lit = _GfxWaterHorizon.rgb + _GfxWaterLight.rgb * sunHeight * 0.4;
                float3 body = under * through + lit * float3(0.025, 0.08, 0.1) * (1 - through);

                // Reflection, stronger at a glancing angle
                float3 R = reflect(-V, N);
                R.y = abs(R.y);
                float3 reflected = Surroundings(R, strength * 2);
                float4 hit = 0;
                if (_GfxWater.z > 0.5 && distance < 400)
                {
                    hit = ScreenReflection(i.world, R, Hash(i.pos.xy + frac(time) * 61));
                    reflected = lerp(reflected, hit.rgb, hit.a);
                }
                float facing = saturate(dot(N, V));
                float fresnel = (0.02 + 0.98 * pow(1 - facing, 5)) * shallow;
                // gfxe water debug: red where screen-space reflections found something, green the reflection's share,
                // blue the shallows' foam
                if (_GfxWaterDebug > 0.5)
                    return float4(hit.a, fresnel, 1 - saturate(deep / 0.25), 1);

                // The sun's (or moon's) glint
                float3 L = _GfxWaterLightDir.xyz;
                float3 H = normalize(L + V);
                float rough = 0.06 + 0.1 * strength;
                float a2 = rough * rough;
                float nh = saturate(dot(N, H));
                float d = nh * nh * (a2 - 1) + 1;
                float glint = a2 / (UNITY_PI * d * d) * 0.25 / max(facing, 0.1) * saturate(dot(N, L));
                float3 sun = _GfxWaterLight.rgb * min(glint, 60) * (0.02 + 0.98 * pow(1 - saturate(dot(H, V)), 5)) * _GfxWaterLightDir.w * shallow;

                // Foam where it laps against the shore
                float edge = 1 - saturate(deep / 0.25);
                float bubbles = saturate((a.x * b.y + a.y * b.x) * 3 + 0.35);
                float foam = edge * edge * bubbles * level * saturate(_GfxWater.x + 0.25) * 0.8;

                // What's under the water already has the world's haze and fog on it; the surface's own light (the
                // reflection, the glint and the foam) gets them here, as if it were solid
                float bodyShare = (1 - fresnel) * (1 - foam);
                float3 surface = (reflected * fresnel * (1 - foam) + sun * (1 - foam) + lit * 0.75 * foam) / max(1 - bodyShare, 1e-3);
                float4 haze = GfxHaze(_WorldSpaceCameraPos, i.world);
                surface = surface * haze.a + haze.rgb;
                UNITY_APPLY_FOG(i.fogCoord, surface);
                float3 color = body * bodyShare + surface * (1 - bodyShare);
                if (any(isnan(color)) || any(isinf(color)))
                    color = under;
                return float4(min(color, 64), 1);
            }
            ENDCG
        }
    }
}
