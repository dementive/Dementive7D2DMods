// Drawn as an extra material over a zombie's own (the renderer draws its mesh again with it), so it works on any
// zombie whatever shader it uses. It reads the zombie's own albedo (handed over per zombie through a
// MaterialPropertyBlock) and works out how the surface should look instead: grime in the creases, sun-bleach, dust,
// ash, frost rime or soot on the parts facing up, wet darkening, charring, frost, old blood, and wounds at world
// positions the mod moves with the bones every frame.
//
// It does no lighting of its own: it multiplies the zombie as the game already lit it by how much each color changed
// (new albedo / old), so shadows, dark rooms and night carry through exactly. (Lit by itself, as a see-through forward
// surface it got the sun without shadows, which made zombies glow indoors.) Nothing in it glows: glowing veins and
// embers looked bad at night and were taken out.
Shader "Dementive/ZombieOverlay"
{
    Properties
    {
        _BaseAlbedo ("Base Albedo", 2D) = "gray" {}
        _HasBase ("Has Base", Float) = 0
        _Grime ("Grime", Range(0, 1)) = 0
        _GrimeColor ("Grime Color", Color) = (0.24, 0.19, 0.12, 1)
        _Settle ("Settle", Range(0, 1)) = 0
        _SettleColor ("Settle Color", Color) = (0.66, 0.56, 0.4, 1)
        _Bleach ("Bleach", Range(0, 1)) = 0
        _Wet ("Wet", Range(0, 1)) = 0
        _Char ("Char", Range(0, 1)) = 0
        _Frost ("Frost", Range(0, 1)) = 0
        _Blood ("Blood", Range(0, 1)) = 0
        _Seed ("Seed", Float) = 0
    }
    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "IgnoreProjector" = "True" }
        ZWrite Off
        Offset -1, -1

        CGINCLUDE
        #include "UnityCG.cginc"

        sampler2D _BaseAlbedo;
        float _HasBase, _Grime, _Settle, _Bleach, _Wet, _Char, _Frost, _Blood, _Seed;
        fixed4 _GrimeColor, _SettleColor;
        float4 _Wounds[12];
        float _WoundCount;

        struct appdata
        {
            float4 vertex : POSITION;
            float3 normal : NORMAL;
            float2 uv : TEXCOORD0;
        };

        struct v2f
        {
            float4 pos : SV_POSITION;
            float2 uv : TEXCOORD0;
            float3 worldPos : TEXCOORD1;
            float3 worldNormal : TEXCOORD2;
            UNITY_FOG_COORDS(3)
        };

        v2f vert(appdata v)
        {
            v2f o;
            o.pos = UnityObjectToClipPos(v.vertex);
            o.uv = v.uv;
            o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
            o.worldNormal = UnityObjectToWorldNormal(v.normal);
            UNITY_TRANSFER_FOG(o, o.pos);
            return o;
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

        void layer(inout float3 col, inout float alpha, float3 c, float a)
        {
            col = lerp(col, c, a);
            alpha = alpha + a * (1 - alpha);
        }

        float3 Base(v2f i)
        {
            return _HasBase > 0.5 ? tex2D(_BaseAlbedo, i.uv).rgb : float3(0.45, 0.42, 0.4);
        }

        // The surface's new albedo, from its own (`base`)
        float3 Paint(v2f i, float3 base)
        {
            float2 nuv = i.uv + _Seed * 0.37;
            // What faces up comes from the mesh itself (reliable whatever the zombie's normal map holds)
            float up = saturate(normalize(i.worldNormal).y);
            float lum = Luminance(base);
            float crease = saturate(1 - lum * 2.5);

            float3 col = base;
            float alpha = 0;

            // Grime: the zombie's own colors darkened and tinted, gathering in the creases and broken up finely
            float grain = noise(nuv * 150);
            float grime = cover(fbm(nuv * 26) * 0.75 + crease * 0.35 + grain * 0.15, _Grime);
            layer(col, alpha, base * _GrimeColor.rgb * 2.0, grime * 0.75);

            // Sun-bleach: paler and greyer
            float3 bleached = lerp(base, lum.xxx * 1.2 + 0.05, 0.7);
            layer(col, alpha, bleached, _Bleach * (0.5 + 0.5 * fbm(nuv * 9)));

            // Dust, ash, rime or soot settled on what faces up: head, shoulders, the tops of the arms and feet
            float settle = cover(fbm(nuv * 34 + 7) * 0.6 + grain * 0.4, _Settle) * smoothstep(0.35, 0.8, up);
            layer(col, alpha, lerp(base, _SettleColor.rgb, 0.75) * (0.85 + 0.3 * grain), settle * 0.85);

            // Wet: darker
            float wet = _Wet * (0.75 + 0.25 * fbm(nuv * 10 + 3));
            layer(col, alpha, col * 0.72, wet * 0.7);

            // Char: blackened, keeping the shapes underneath (no glowing cracks)
            float charMask = cover(fbm(nuv * 18 + 11) * 0.8 + grain * 0.2, _Char);
            float3 charCol = base * 0.06 + float3(0.012, 0.01, 0.009) * (0.6 + 0.8 * grain);
            layer(col, alpha, charCol, charMask * 0.95);

            // Frost: a thin crust of pale crystals, thicker on what faces up, the colors showing through
            float crystals = noise(nuv * 140) * 0.6 + noise(nuv * 60 + 9) * 0.4;
            float frost = cover(fbm(nuv * 12 + 5) * 0.45 + crystals * 0.35 + up * 0.25, _Frost);
            layer(col, alpha, lerp(base, float3(0.78, 0.86, 0.94), 0.55 + 0.3 * crystals), frost * 0.65);

            // Old blood soaked into the clothes and skin: the colors underneath, darkened to a dried brown-red
            float old = cover(fbm(nuv * 32 + 41) * 0.7 + grain * 0.3, _Blood * 0.6);
            layer(col, alpha, base * float3(0.32, 0.12, 0.09), old * 0.8);

            // Wounds: dark wet blood around a hole; blunt hits leave bruising instead
            float blood = 0;
            float hole = 0;
            float bruise = 0;
            for (int k = 0; k < 12; k++)
            {
                if (k >= _WoundCount)
                {
                    break;
                }
                float4 w = _Wounds[k];
                float kind = floor(w.w / 10);
                float r = w.w - kind * 10;
                float d = distance(i.worldPos, w.xyz);
                float n = noise3(i.worldPos * 45 + k * 7.1) - 0.5;
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
            layer(col, alpha, base * float3(0.35, 0.2, 0.3), bruise * 0.75);
            layer(col, alpha, base * float3(0.3, 0.05, 0.04) + float3(0.03, 0.0, 0.0), blood * 0.9);
            layer(col, alpha, float3(0.015, 0.0, 0.0), hole);
            return lerp(base, col, alpha);
        }

        ENDCG

        // The look: the lit zombie times how much each color changed. A surface can only be lightened so far before
        // its texture's noise and shine blow up: past that the whole change is scaled down, keeping its hue (capping
        // each channel alone turned frost and snow on red cloth pink)
        Pass
        {
            Blend DstColor Zero

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #pragma target 3.5

            float4 frag(v2f i) : SV_Target
            {
                float3 base = Base(i);
                float3 tint = Paint(i, base) / max(base, 0.02);
                tint *= min(1, 8 / max(tint.r, max(tint.g, tint.b)));
                float4 c = float4(tint, 1);
                UNITY_APPLY_FOG_COLOR(i.fogCoord, c, float4(1, 1, 1, 1));
                return c;
            }
            ENDCG
        }
    }
}
