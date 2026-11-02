// Game juice (GfxJuiceScreen): what's drawn on the screen itself, under the HUD.
// - Low health: the edges darkening and reddening with each heartbeat (the game already shows blood on the side a
//   hit came from, so that's left to it).
// - Rewards: a soft warm glow round the edges on a level-up, fainter on a finished quest.
// One triangle covering the screen, drawn on the UI camera before its widgets (after the scene has been upscaled), with
// premultiplied alpha.
Shader "Hidden/GraphicsExpanded/JuiceScreen"
{
    SubShader
    {
        Pass
        {
            Blend One OneMinusSrcAlpha
            ZWrite Off
            ZTest Always
            Cull Off

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"

            float4 _GfxJuiceHurt;       // x: low health 0 to 1, y: the heartbeat now 0 to 1
            float4 _GfxJuiceReward;     // x: progress 0 to 1 (0: none), y: strength 0 to 1

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            v2f vert(uint id : SV_VertexID)
            {
                v2f o;
                float2 p = float2((id << 1) & 2, id & 2);
                // uv 0 to 1 with y up the screen; flipped in clip space when the camera renders upside down into a texture
                o.pos = float4(p * 2 - 1, 0, 1);
                o.pos.y *= _ProjectionParams.x;
                o.uv = p;
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                // About 1 at the screen's edges
                float round_ = length(i.uv * 2 - 1) * 0.75;
                float4 result = 0;

                // Low health: the edges darken and redden with each heartbeat
                if (_GfxJuiceHurt.x > 0.001)
                {
                    float beat = 0.45 + 0.55 * _GfxJuiceHurt.y;
                    float a = smoothstep(0.45, 1.25, round_) * _GfxJuiceHurt.x * beat * 0.7;
                    result = float4(float3(0.12, 0.0, 0.0) * a, a);
                }

                // A reward: a soft warm glow round the edges that swells and fades
                if (_GfxJuiceReward.x > 0.001)
                {
                    float t = _GfxJuiceReward.x;
                    float swell = saturate(t * 6) * (1 - t) * (1 - t);
                    float glow = smoothstep(0.55, 1.3, round_) * swell * 0.22 * _GfxJuiceReward.y;
                    result.rgb += float3(1.0, 0.78, 0.4) * glow;
                }
                return result;
            }
            ENDCG
        }
    }
}
