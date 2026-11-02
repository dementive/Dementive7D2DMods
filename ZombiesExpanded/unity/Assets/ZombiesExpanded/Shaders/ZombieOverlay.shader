// Drawn as an extra material over a zombie's own (the renderer draws its mesh again with it), so it works on any
// zombie whatever shader it uses. It reads the zombie's own albedo and normal map (handed over per zombie through a
// MaterialPropertyBlock) and paints over them: grime in the creases, sun-bleach, dust, ash, frost rime or soot on
// the parts facing up, a wet sheen, charring with glowing cracks, frost, glowing veins, old blood, and wounds at world
// positions the mod moves with the bones every frame.
Shader "Dementive/ZombieOverlay"
{
    Properties
    {
        _BaseAlbedo ("Base Albedo", 2D) = "gray" {}
        _BaseNormal ("Base Normal", 2D) = "bump" {}
        _HasBase ("Has Base", Float) = 0
        _Grime ("Grime", Range(0, 1)) = 0
        _GrimeColor ("Grime Color", Color) = (0.24, 0.19, 0.12, 1)
        _Settle ("Settle", Range(0, 1)) = 0
        _SettleColor ("Settle Color", Color) = (0.66, 0.56, 0.4, 1)
        _Bleach ("Bleach", Range(0, 1)) = 0
        _Wet ("Wet", Range(0, 1)) = 0
        _Char ("Char", Range(0, 1)) = 0
        _Embers ("Embers", Range(0, 1)) = 0
        _Frost ("Frost", Range(0, 1)) = 0
        _Blood ("Blood", Range(0, 1)) = 0
        _Veins ("Veins", Range(0, 1)) = 0
        _VeinColor ("Vein Color", Color) = (0.35, 1, 0.25, 1)
        _VeinGlow ("Vein Glow", Float) = 2
        _Seed ("Seed", Float) = 0
    }
    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "IgnoreProjector" = "True" }
        ZWrite Off
        Offset -1, -1

        CGPROGRAM
        #pragma surface surf Standard alpha:fade vertex:vert nolightmap nodynlightmap nodirlightmap
        #pragma target 3.5

        sampler2D _BaseAlbedo;
        sampler2D _BaseNormal;
        float _HasBase, _Grime, _Settle, _Bleach, _Wet, _Char, _Embers, _Frost, _Blood, _Veins, _VeinGlow, _Seed;
        fixed4 _GrimeColor, _SettleColor, _VeinColor;
        float4 _Wounds[12];
        float _WoundCount;

        struct Input
        {
            float2 texc;
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.texc = v.texcoord.xy;
        }

        float hash(float2 p)
        {
            p = frac(p * float2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return frac(p.x * p.y);
        }

        // Gradient noise, 0..1: smooth shapes without the square cells value noise shows once it's thresholded
        float noise(float2 p)
        {
            float2 i = floor(p);
            float2 f = frac(p);
            float2 u = f * f * f * (f * (f * 6 - 15) + 10);
            float a0 = hash(i) * 6.2831853, a1 = hash(i + float2(1, 0)) * 6.2831853;
            float a2 = hash(i + float2(0, 1)) * 6.2831853, a3 = hash(i + float2(1, 1)) * 6.2831853;
            float va = dot(float2(cos(a0), sin(a0)), f);
            float vb = dot(float2(cos(a1), sin(a1)), f - float2(1, 0));
            float vc = dot(float2(cos(a2), sin(a2)), f - float2(0, 1));
            float vd = dot(float2(cos(a3), sin(a3)), f - float2(1, 1));
            return saturate(lerp(lerp(va, vb, u.x), lerp(vc, vd, u.x), u.y) * 0.9 + 0.5);
        }

        float fbm(float2 p)
        {
            float v = 0, a = 0.5;
            for (int k = 0; k < 5; k++)
            {
                v += a * noise(p);
                p = p * 2.03 + 17.1;
                a *= 0.5;
            }
            return v / 0.97;
        }

        float hash3(float3 p)
        {
            p = frac(p * 0.3183099 + 0.1);
            p *= 17.0;
            return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
        }

        float noise3(float3 x)
        {
            float3 i = floor(x);
            float3 f = frac(x);
            f = f * f * (3 - 2 * f);
            return lerp(lerp(lerp(hash3(i), hash3(i + float3(1, 0, 0)), f.x), lerp(hash3(i + float3(0, 1, 0)), hash3(i + float3(1, 1, 0)), f.x), f.y),
                        lerp(lerp(hash3(i + float3(0, 0, 1)), hash3(i + float3(1, 0, 1)), f.x), lerp(hash3(i + float3(0, 1, 1)), hash3(i + float3(1, 1, 1)), f.x), f.y), f.z);
        }

        float2 hash2(float2 p)
        {
            p = float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)));
            return frac(sin(p) * 43758.5453);
        }

        // Distance to the nearest cell border: a network of cracks
        float cracks(float2 p)
        {
            float2 n = floor(p);
            float2 f = frac(p);
            float md = 8;
            float2 mr = 0;
            for (int j = -1; j <= 1; j++)
            {
                for (int i = -1; i <= 1; i++)
                {
                    float2 g = float2(i, j);
                    float2 r = g + hash2(n + g) - f;
                    float d = dot(r, r);
                    if (d < md)
                    {
                        md = d;
                        mr = r;
                    }
                }
            }
            md = 8;
            for (int j2 = -1; j2 <= 1; j2++)
            {
                for (int i2 = -1; i2 <= 1; i2++)
                {
                    float2 g = float2(i2, j2);
                    float2 r = g + hash2(n + g) - f;
                    if (dot(mr - r, mr - r) > 0.00001)
                    {
                        md = min(md, dot(0.5 * (mr + r), normalize(r - mr)));
                    }
                }
            }
            return md;
        }

        // fbm bunches around 0.5: spread it over 0..1
        float spread(float n)
        {
            return saturate((n - 0.28) * 2.3);
        }

        // How much of the surface a layer covers at `amount`: none at 0, all at 1, ragged edges between
        float cover(float n, float amount)
        {
            return smoothstep(1 - amount - 0.1, 1 - amount + 0.12, spread(n)) * step(0.001, amount);
        }

        void layer(inout float3 col, inout float smooth, inout float alpha, float3 c, float s, float a)
        {
            col = lerp(col, c, a);
            smooth = lerp(smooth, s, a);
            alpha = alpha + a * (1 - alpha);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float2 uv = IN.texc;
            float2 nuv = uv + _Seed * 0.37;
            float3 base = _HasBase > 0.5 ? tex2D(_BaseAlbedo, uv).rgb : float3(0.45, 0.42, 0.4);
            // What faces up comes from the mesh itself (reliable whatever the zombie's normal map holds)
            float up = saturate(WorldNormalVector(IN, float3(0, 0, 1)).y);
            o.Normal = UnpackNormal(tex2D(_BaseNormal, uv));
            float lum = Luminance(base);
            float crease = saturate(1 - lum * 2.5);

            float3 col = base;
            float smooth = 0.25;
            float alpha = 0;
            float3 emit = 0;

            // Grime: the zombie's own colors darkened and tinted, gathering in the creases and broken up finely
            float grain = noise(nuv * 150);
            float grime = cover(fbm(nuv * 26) * 0.75 + crease * 0.35 + grain * 0.15, _Grime);
            layer(col, smooth, alpha, base * _GrimeColor.rgb * 2.0, 0.15, grime * 0.75);

            // Sun-bleach: paler and greyer
            float3 bleached = lerp(base, lum.xxx * 1.2 + 0.05, 0.7);
            layer(col, smooth, alpha, bleached, 0.2, _Bleach * (0.5 + 0.5 * fbm(nuv * 9)));

            // Dust, ash, rime or soot settled on what faces up: head, shoulders, the tops of the arms and feet
            float settle = cover(fbm(nuv * 34 + 7) * 0.6 + grain * 0.4, _Settle) * smoothstep(0.35, 0.8, up);
            layer(col, smooth, alpha, lerp(base, _SettleColor.rgb, 0.75) * (0.85 + 0.3 * grain), 0.2, settle * 0.85);

            // Wet: darker and glossy
            float wet = _Wet * (0.75 + 0.25 * fbm(nuv * 10 + 3));
            layer(col, smooth, alpha, col * 0.72, 0.85, wet * 0.7);

            // Char: blackened, keeping the shapes underneath, with glowing cracks while it burns
            float c = fbm(nuv * 18 + 11) * 0.8 + grain * 0.2;
            float charMask = cover(c, _Char);
            float3 charCol = base * 0.06 + float3(0.012, 0.01, 0.009) * (0.6 + 0.8 * grain);
            layer(col, smooth, alpha, charCol, 0.1, charMask * 0.95);
            float crack = cracks(nuv * 26 + 3);
            float glowCells = cover(fbm(nuv * 9 + 5), _Char * 0.45) * charMask;
            float flicker = 0.7 + 0.3 * sin(_Time.y * 6 + nuv.x * 40);
            emit += float3(1.0, 0.28, 0.03) * (1 - smoothstep(0.0, 0.035, crack)) * glowCells * _Embers * flicker * 3;

            // Frost: a thin crust of pale crystals, thicker on what faces up, the colors showing through
            float crystals = noise(nuv * 140) * 0.6 + noise(nuv * 60 + 9) * 0.4;
            float frost = cover(fbm(nuv * 12 + 5) * 0.45 + crystals * 0.35 + up * 0.25, _Frost);
            layer(col, smooth, alpha, lerp(base, float3(0.78, 0.86, 0.94), 0.55 + 0.3 * crystals), 0.8, frost * 0.65);

            // Veins
            float ridge = abs(noise(nuv * 34 + 23) * 2 - 1);
            float veins = (1 - smoothstep(0.0, 0.07, ridge)) * cover(fbm(nuv * 6 + 31), _Veins);
            layer(col, smooth, alpha, base * 0.3 + _VeinColor.rgb * 0.2, 0.55, veins * 0.9);
            emit += _VeinColor.rgb * veins * _VeinGlow * (0.6 + 0.4 * sin(_Time.y * 3 + _Seed));

            // Old blood soaked into the clothes and skin: the colors underneath, darkened and reddened
            float old = cover(fbm(nuv * 32 + 41) * 0.7 + grain * 0.3, _Blood * 0.6);
            layer(col, smooth, alpha, base * float3(0.42, 0.1, 0.08), 0.3, old * 0.8);

            // Wounds: dark wet blood around a hole; blunt hits leave bruising instead
            float blood = 0;
            float hole = 0;
            float bruise = 0;
            for (int i = 0; i < 12; i++)
            {
                if (i >= _WoundCount)
                {
                    break;
                }
                float4 w = _Wounds[i];
                float kind = floor(w.w / 10);
                float r = w.w - kind * 10;
                float d = distance(IN.worldPos, w.xyz);
                float n = noise3(IN.worldPos * 45 + i * 7.1) - 0.5;
                float spot = smoothstep(r, r * 0.45, d + n * r * 1.2);
                if (kind > 0.5)
                {
                    bruise = max(bruise, spot);
                }
                else
                {
                    blood = max(blood, spot);
                    hole = max(hole, smoothstep(r * 0.3, r * 0.15, d + n * r * 0.35));
                }
            }
            layer(col, smooth, alpha, base * float3(0.35, 0.2, 0.3), 0.3, bruise * 0.75);
            layer(col, smooth, alpha, base * float3(0.3, 0.05, 0.04) + float3(0.03, 0.0, 0.0), 0.8, blood * 0.9);
            layer(col, smooth, alpha, float3(0.015, 0.0, 0.0), 0.5, hole);

            o.Albedo = col;
            o.Smoothness = smooth;
            o.Metallic = 0;
            o.Emission = emit;
            o.Alpha = saturate(alpha + saturate(dot(emit, 1)) * 0.5);
        }
        ENDCG
    }
}
