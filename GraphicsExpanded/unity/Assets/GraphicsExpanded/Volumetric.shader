// Sunbeams and height fog. GfxAtmosphere runs the passes:
// - On the sun (or moon) light, right after its screen-space shadows: 0 writes the depth at low resolution, 1 marches a ray
//   from the camera through the air for each pixel, adding the light scattered towards the camera wherever the
//   light's shadow map says the air is lit, plus the fog's own glow, and how much the air dims what's behind it.
// - On the camera after transparent objects: 2 and 3 blur that across, keeping edges, and 4 lays it over the picture
//   (what's there times the dimming, plus the light), before the game's post-processing tonemaps it.
Shader "Hidden/GraphicsExpanded/Volumetric"
{
    CGINCLUDE
    #include "UnityCG.cginc"

    UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
    float4x4 _GfxInvProjection;     // the camera's, OpenGL style (camera.projectionMatrix.inverse)
    float4x4 _GfxCameraToWorld;
    float4 _GfxLowSize;             // the low resolution: xy size, zw 1 / size
    float4 _GfxFullSize;            // the camera's

    struct v2f
    {
        float4 pos : SV_POSITION;
    };

    // One triangle covering the target
    v2f vert(uint id : SV_VertexID)
    {
        v2f o;
        float2 p = float2((id << 1) & 2, id & 2);
        o.pos = float4(p * 2 - 1, 0, 1);
        return o;
    }

    // Where the camera would see a point at this eye depth through this pixel (same as WeatherSurface)
    float3 WorldFromDepth(float2 uv, float eyeDepth)
    {
        float2 ndc = uv * 2 - 1;
    #if UNITY_UV_STARTS_AT_TOP
        if (_ProjectionParams.x > 0)
            ndc.y = -ndc.y;
    #endif
        float4 farPoint = mul(_GfxInvProjection, float4(ndc, 1, 1));
        float3 view = farPoint.xyz / farPoint.w;
        return mul(_GfxCameraToWorld, float4(view * (eyeDepth / -view.z), 1)).xyz;
    }
    ENDCG

    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always

        // 0: eye depth at the low resolution
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5

            float4 frag(v2f i) : SV_Target
            {
                float2 uv = i.pos.xy * _GfxLowSize.zw;
                return LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv));
            }
            ENDCG
        }

        // 1: march through the air
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5

            UNITY_DECLARE_SHADOWMAP(_GfxShadowMap);
            sampler2D _GfxLowDepth;
            float4 _GfxLightDir;        // xyz: towards the light
            float4 _GfxLightColor;      // rgb: the light's color and brightness, times the sunbeam strength
            float4 _GfxAmbient;         // rgb: the fog's own color, from the game's fog
            float4 _GfxMedium;          // x: fog density at and below the fog base, y: its falloff per meter above, z: the base's height, w: clear air density
            float4 _GfxDust;            // x: extra density near the player when indoors, y: how far out it reaches
            float4 _GfxMarch;           // x: steps, y: how far to march, z: phase g (how much light goes forward), w: frame number
            float _GfxSplitSpheres;     // 1: the shadow cascades are split by spheres (stable fit), 0: by view depth
            float _GfxFar;              // the camera's far clip: rays that reach it are the sky
            sampler3D _GfxFogNoise;     // soft repeating noise the fog is broken into banks with
            float4 _GfxFogBanks;        // x: 1 / the noise's repeat across in meters, y: and upwards, z: how patchy the fog is (0 an even sheet to 1 banks and gaps)
            float4 _GfxFogOffset;       // xyz: added to positions before the noise: the floating origin, and how far the wind has carried the fog

            // 1 where the light reaches the point, 0 in its shadow; past the shadow distance everything is lit
            float Visibility(float3 p, float viewDepth)
            {
                float4 weights;
                if (_GfxSplitSpheres > 0.5)
                {
                    float3 c0 = p - unity_ShadowSplitSpheres[0].xyz;
                    float3 c1 = p - unity_ShadowSplitSpheres[1].xyz;
                    float3 c2 = p - unity_ShadowSplitSpheres[2].xyz;
                    float3 c3 = p - unity_ShadowSplitSpheres[3].xyz;
                    float4 distances = float4(dot(c0, c0), dot(c1, c1), dot(c2, c2), dot(c3, c3));
                    weights = float4(distances < unity_ShadowSplitSqRadii);
                    weights.yzw = saturate(weights.yzw - weights.xyz);
                }
                else
                {
                    weights = float4(viewDepth >= _LightSplitsNear) * float4(viewDepth < _LightSplitsFar);
                }
                if (dot(weights, 1) <= 0)
                    return 1;
                float4 world = float4(p, 1);
                float3 coord = mul(unity_WorldToShadow[0], world).xyz * weights.x
                    + mul(unity_WorldToShadow[1], world).xyz * weights.y
                    + mul(unity_WorldToShadow[2], world).xyz * weights.z
                    + mul(unity_WorldToShadow[3], world).xyz * weights.w;
                return UNITY_SAMPLE_SHADOW(_GfxShadowMap, coord);
            }

            // Henyey-Greenstein: how much light turns from the light's direction towards the camera
            float Phase(float cosTheta, float g)
            {
                float g2 = g * g;
                return (1 - g2) / (4 * UNITY_PI * pow(max(1 + g2 - 2 * g * cosTheta, 1e-4), 1.5));
            }

            // The fog alone: a layer thinning with height, broken into drifting banks with gaps between, their tops
            // rising and falling in wisps
            float Fog(float3 p)
            {
                float3 q = p + _GfxFogOffset.xyz;
                float noise = tex3Dlod(_GfxFogNoise, float4(q.x * _GfxFogBanks.x, q.y * _GfxFogBanks.y, q.z * _GfxFogBanks.x, 0)).r;
                float patchy = _GfxFogBanks.z;
                float top = _GfxMedium.z + (noise - 0.5) * 16 * patchy;
                float banks = lerp(1, smoothstep(0.36, 0.64, noise) * 1.8, patchy);
                return _GfxMedium.x * exp(-max(0, p.y - top) * _GfxMedium.y) * banks;
            }

            float Density(float3 p, float distance)
            {
                float dust = _GfxDust.x * saturate(1 - distance / _GfxDust.y);
                return Fog(p) + dust + _GfxMedium.w;
            }

            // Per-pixel jitter for where the steps start, so too few steps read as noise (which the blur and the game's
            // anti-aliasing smooth) rather than as bands
            float Jitter(float2 pixel)
            {
                pixel += _GfxMarch.w * 5.588238;
                return frac(52.9829189 * frac(dot(pixel, float2(0.06711056, 0.00583715))));
            }

            float4 frag(v2f i) : SV_Target
            {
                float2 uv = i.pos.xy * _GfxLowSize.zw;
                float eyeDepth = tex2D(_GfxLowDepth, uv).r;
                float3 camera = _GfxCameraToWorld._m03_m13_m23;
                float3 ray = WorldFromDepth(uv, eyeDepth) - camera;
                float fullLength = length(ray);
                if (!(fullLength > 1e-3 && fullLength < 1e7))
                    return float4(0, 0, 0, 1);  // no sensible ray (matrices or depth not set): leave the picture alone
                float3 dir = ray / fullLength;
                float marchLength = min(fullLength, _GfxMarch.y);
                float depthPerMeter = eyeDepth / fullLength;

                int steps = max((int)_GfxMarch.x, 1);
                float stepLength = marchLength / steps;
                float jitter = Jitter(i.pos.xy);
                float phase = Phase(dot(dir, _GfxLightDir.xyz), _GfxMarch.z);
                // Clear air still shows sunbeams against the sky, but doesn't dim it: the sky already is the air
                float clearDims = eyeDepth > _GfxFar * 0.98 ? 0 : 1;

                float3 light = 0;
                float transmittance = 1;
                [loop]
                for (int s = 0; s < steps; s++)
                {
                    float t = (s + jitter) * stepLength;
                    float3 p = camera + dir * t;
                    float density = Density(p, t);
                    float3 glow = _GfxLightColor.rgb * Visibility(p, t * depthPerMeter) * phase + _GfxAmbient.rgb;
                    // The light this step scatters towards the camera, dimmed by the air in front of it
                    light += transmittance * glow * (1 - exp(-density * stepLength));
                    transmittance *= exp(-(density - _GfxMedium.w * (1 - clearDims)) * stepLength);
                }
                float4 result = float4(light, transmittance);
                return any(isnan(result)) || any(isinf(result)) ? float4(0, 0, 0, 1) : result;
            }
            ENDCG
        }

        // 2: blur across, keeping edges where the depth jumps
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5

            sampler2D _GfxVolume;
            sampler2D _GfxLowDepth;

            float4 frag(v2f i) : SV_Target
            {
                float2 uv = i.pos.xy * _GfxLowSize.zw;
                float center = tex2D(_GfxLowDepth, uv).r;
                float4 sum = 0;
                float total = 0;
                for (int k = -2; k <= 2; k++)
                {
                    float2 tap = uv + float2(k, 0) * _GfxLowSize.zw;
                    float weight = exp(-abs(tex2D(_GfxLowDepth, tap).r - center) / (0.05 * center + 0.1)) * (k == 0 ? 1 : 0.6);
                    sum += tex2D(_GfxVolume, tap) * weight;
                    total += weight;
                }
                return sum / total;
            }
            ENDCG
        }

        // 3: and down
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5

            sampler2D _GfxBlurred;
            sampler2D _GfxLowDepth;

            float4 frag(v2f i) : SV_Target
            {
                float2 uv = i.pos.xy * _GfxLowSize.zw;
                float center = tex2D(_GfxLowDepth, uv).r;
                float4 sum = 0;
                float total = 0;
                for (int k = -2; k <= 2; k++)
                {
                    float2 tap = uv + float2(0, k) * _GfxLowSize.zw;
                    float weight = exp(-abs(tex2D(_GfxLowDepth, tap).r - center) / (0.05 * center + 0.1)) * (k == 0 ? 1 : 0.6);
                    sum += tex2D(_GfxBlurred, tap) * weight;
                    total += weight;
                }
                return sum / total;
            }
            ENDCG
        }

        // 4: over the picture: what's there times how much gets through, plus the scattered light
        Pass
        {
            Blend One SrcAlpha

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5

            sampler2D _GfxVolume;
            sampler2D _GfxLowDepth;
            float _GfxMarched;      // set to 1 by the march, back to 0 after this pass: 0 means it didn't run this frame

            float4 Upsample(v2f i)
            {
                float2 uv = i.pos.xy * _GfxFullSize.zw;
                float depth = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv));

                // The four low resolution pixels around this one. Smooth between them, unless one is across an edge
                // (a big jump in depth): then take the one at this pixel's depth, so beams don't bleed onto
                // whatever is in front
                float2 base = (floor(uv * _GfxLowSize.xy - 0.5) + 0.5) * _GfxLowSize.zw;
                float2 taps[4] = { base, base + float2(_GfxLowSize.z, 0), base + float2(0, _GfxLowSize.w), base + _GfxLowSize.zw };
                float nearest = 1e9;
                float2 best = base;
                float spread = 0;
                for (int k = 0; k < 4; k++)
                {
                    float difference = abs(tex2D(_GfxLowDepth, taps[k]).r - depth);
                    spread = max(spread, difference);
                    if (difference < nearest)
                    {
                        nearest = difference;
                        best = taps[k];
                    }
                }
                return spread < 0.1 * depth + 0.2 ? tex2D(_GfxVolume, uv) : tex2D(_GfxVolume, best);
            }

            float4 frag(v2f i) : SV_Target
            {
                // Never darken the picture with stale or missing data
                if (_GfxMarched < 0.5)
                    return float4(0, 0, 0, 1);
                float4 result = Upsample(i);
                if (any(isnan(result)) || any(isinf(result)))
                    return float4(0, 0, 0, 1);
                return float4(min(result.rgb, 64), clamp(result.a, 0.02, 1));
            }
            ENDCG
        }
    }
}
