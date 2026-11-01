// Rain wetness, puddles and snow cover, drawn over the deferred G-buffer after the game has drawn every surface and
// before reflections and lighting, so the game's lighting (and Torch's) treats the result like any other surface.
// GfxWeather copies G-buffers 0 to 2 into _GfxGBuffer0..2 and renders this into the real ones. Pixels it doesn't
// change are discarded, so they keep what the game drew.
Shader "Hidden/GraphicsExpanded/WeatherSurface"
{
    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"

            sampler2D _GfxGBuffer0;         // diffuse color, occlusion
            sampler2D _GfxGBuffer1;         // specular color, smoothness
            sampler2D _GfxGBuffer2;         // world normal
            float4 _GfxGBuffer0_TexelSize;
            UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);

            sampler2D _GfxSkyHeight;        // per block column around the player: the top of the highest block that stops rain
            float4 _GfxSkyArea;             // xy: the map's corner (x, z where drawn), z: 1 / its size in meters, w: height offset
            float4 _GfxWeather;             // x: wetness, y: puddle fill, z: snow cover, w: ripples, all 0 to 1
            float4x4 _GfxInvProjection;     // the camera's, OpenGL style (camera.projectionMatrix.inverse)
            float4x4 _GfxCameraToWorld;
            float _GfxDebug;                // 1: show the sky map instead (cyan open to the sky, magenta covered)

            struct v2f
            {
                float4 pos : SV_POSITION;
            };

            struct GBuffer
            {
                float4 g0 : SV_Target0;
                float4 g1 : SV_Target1;
                float4 g2 : SV_Target2;
            };

            // One triangle covering the screen
            v2f vert(uint id : SV_VertexID)
            {
                v2f o;
                float2 p = float2((id << 1) & 2, id & 2);
                o.pos = float4(p * 2 - 1, 0, 1);
                return o;
            }

            // Value noise and a few octaves of it, in world space so the patterns stay put
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
                return Noise(p) * 0.5 + Noise(p * 2.03 + 17.1) * 0.3 + Noise(p * 4.1 + 31.7) * 0.2;
            }

            // How much of the sky the point sees: 1 in the open, 0 under a roof, soft at the edges
            float SkyExposure(float3 worldPos, float3 normal)
            {
                // Step out from walls so they check the open column beside them, not the roof they hold up
                float2 xz = worldPos.xz + normal.xz * 0.5;
                float2 uv = (xz - _GfxSkyArea.xy) * _GfxSkyArea.z;
                if (any(uv < 0) || any(uv > 1))
                    return 1;   // beyond the map: assume open sky
                // Smooth terrain sits up to a block below the top of its block, and nothing that covers anything is
                // closer than a block and a bit above it
                float top = worldPos.y + 1.2 - _GfxSkyArea.w;
                float edge = 0.3 * _GfxSkyArea.z;   // soften the block edges by 30 cm
                float exposure = step(tex2Dlod(_GfxSkyHeight, float4(uv + float2(-edge, -edge), 0, 0)).r, top);
                exposure += step(tex2Dlod(_GfxSkyHeight, float4(uv + float2(edge, -edge), 0, 0)).r, top);
                exposure += step(tex2Dlod(_GfxSkyHeight, float4(uv + float2(-edge, edge), 0, 0)).r, top);
                exposure += step(tex2Dlod(_GfxSkyHeight, float4(uv + float2(edge, edge), 0, 0)).r, top);
                return exposure * 0.25;
            }

            // Rain hitting a puddle: rings spreading from random spots in 0.6 m cells, each on its own beat.
            // Returns the slope they give the water surface.
            float2 Ripples(float2 xz, float time)
            {
                float2 cell = floor(xz / 0.6);
                float2 slope = 0;
                for (int y = -1; y <= 1; y++)
                {
                    for (int x = -1; x <= 1; x++)
                    {
                        float2 c = cell + float2(x, y);
                        float2 center = (c + float2(Hash(c + 7.1), Hash(c + 3.7))) * 0.6;
                        float t = frac(time * 0.9 + Hash(c));
                        float2 d = xz - center;
                        float r = length(d);
                        float radius = t * 0.5;
                        float wave = sin((r - radius) * 40) * saturate(1 - abs(r - radius) * 12) * (1 - t);
                        slope += (r > 0.001 ? d / r : 0) * wave;
                    }
                }
                return slope * 0.15;
            }

            GBuffer frag(v2f i)
            {
                float2 uv = i.pos.xy * _GfxGBuffer0_TexelSize.xy;
                float eyeDepth = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv));
                // The sky, and the player's own hands and gun right in front of the camera
                if (eyeDepth > _ProjectionParams.z * 0.99 || eyeDepth < 0.6)
                    discard;

                // Back from the depth to the world position
                float2 ndc = uv * 2 - 1;
            #if UNITY_UV_STARTS_AT_TOP
                if (_ProjectionParams.x > 0)
                    ndc.y = -ndc.y;
            #endif
                float4 farPoint = mul(_GfxInvProjection, float4(ndc, 1, 1));
                float3 view = farPoint.xyz / farPoint.w;
                float3 worldPos = mul(_GfxCameraToWorld, float4(view * (eyeDepth / -view.z), 1)).xyz;

                float4 g0 = tex2D(_GfxGBuffer0, uv);
                float4 g1 = tex2D(_GfxGBuffer1, uv);
                float4 g2 = tex2D(_GfxGBuffer2, uv);
                float3 normal = normalize(g2.rgb * 2 - 1);
                float up = normal.y;
                if (up < -0.05 && _GfxDebug == 0)
                    discard;    // undersides stay dry

                float exposure = SkyExposure(worldPos, normal);
                if (exposure <= 0 && _GfxDebug == 0)
                    discard;

                float3 albedo = g0.rgb;
                float occlusion = g0.a;
                float3 specular = g1.rgb;
                float smoothness = g1.a;

                // Wet: darker and glossier, fully on ground and roofs, a light sheen on walls
                float wet = _GfxWeather.x * exposure * lerp(0.25, 1, smoothstep(0.1, 0.7, up)) * step(-0.05, up);
                albedo *= lerp(1, 0.7, wet);
                smoothness = lerp(smoothness, max(smoothness, 0.7), wet);
                specular = lerp(specular, max(specular, 0.04), wet);

                // Puddles on flat ground: the fuller they get, the more of the noise pattern they cover
                float puddle = 0;
                float flat = smoothstep(0.9, 0.98, up);
                if (_GfxWeather.y > 0 && flat > 0)
                {
                    float edge = 1 - _GfxWeather.y;
                    puddle = smoothstep(edge, edge + 0.06, Fbm(worldPos.xz * 0.12)) * flat * exposure;
                }
                if (puddle > 0)
                {
                    albedo *= lerp(1, 0.55, puddle);
                    specular = lerp(specular, 0.02, puddle);
                    smoothness = lerp(smoothness, 0.95, puddle);
                    float2 ripple = _GfxWeather.w > 0 ? Ripples(worldPos.xz, _Time.y) * _GfxWeather.w : 0;
                    normal = normalize(lerp(normal, normalize(float3(-ripple.x, 1, -ripple.y)), puddle));
                }

                // Snow: builds up evenly, flattest tops first, then on slopes up to about 40 degrees as it deepens.
                // Only the very edge of the cover is broken up, finely, so it doesn't look like blotches of paint.
                float snow = 0;
                if (_GfxWeather.z > 0)
                {
                    float flatness = saturate((up - 0.75) / 0.23);
                    float cover = saturate(_GfxWeather.z * 1.6 - (1 - flatness) * 0.9);
                    float fringe = cover * (1 - cover) * 4;     // 1 halfway in, 0 where bare or fully covered
                    cover = saturate(cover + (Noise(worldPos.xz * 7) - 0.5) * 0.5 * fringe);
                    snow = smoothstep(0, 1, cover) * step(0.62, up) * exposure;
                }
                if (snow > 0)
                {
                    // Slightly blue white, with a little of the surface's own color and texture showing through
                    float3 snowColor = float3(0.80, 0.84, 0.90) * (0.88 + 0.24 * saturate(Luminance(albedo) * 2));
                    albedo = lerp(albedo, snowColor, snow * 0.92);
                    specular = lerp(specular, 0.03, snow);
                    smoothness = lerp(smoothness, 0.3, snow);
                    occlusion = lerp(occlusion, 1, snow * 0.25);

                    // The surface's own shape under a fine grain of bumps and a soft drift
                    float2 grain = float2(Noise(worldPos.xz * 18 + 3.1), Noise(worldPos.xz * 18 + 9.7)) - 0.5;
                    float2 drift = float2(Noise(worldPos.xz * 1.3 + 5.3), Noise(worldPos.xz * 1.3 + 1.9)) - 0.5;
                    float2 bumps = grain * 0.35 + drift * 0.12;
                    float3 snowNormal = normalize(lerp(normal, float3(0, 1, 0), 0.4) + float3(bumps.x, 0, bumps.y));
                    normal = normalize(lerp(normal, snowNormal, snow));

                    // Sparse sparkles: a few tiny glossy specks that catch the sun
                    float speck = step(0.985, Hash(floor(worldPos.xz * 30) + floor(worldPos.y * 30)));
                    smoothness = lerp(smoothness, 0.92, speck * snow);
                    specular = lerp(specular, 0.25, speck * snow);
                }

                if (_GfxDebug > 0)
                    albedo = lerp(float3(1, 0, 1), float3(0, 1, 1), exposure);
                else if (wet <= 0 && puddle <= 0 && snow <= 0)
                    discard;

                GBuffer o;
                o.g0 = float4(albedo, occlusion);
                o.g1 = float4(specular, smoothness);
                o.g2 = float4(normal * 0.5 + 0.5, g2.a);
                return o;
            }
            ENDCG
        }
    }
}
