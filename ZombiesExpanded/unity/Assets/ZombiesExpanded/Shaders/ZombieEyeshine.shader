// An eye's glint: a soft additive dot that always faces the camera, pulled slightly toward it so the face doesn't
// hide it, and kept a few pixels wide far away. The mod sets _Intensity per zombie from your light.
Shader "Dementive/ZombieEyeshine"
{
    Properties
    {
        _Color ("Color", Color) = (0.9, 0.95, 0.55, 1)
        _Intensity ("Intensity", Float) = 0
    }
    SubShader
    {
        Tags { "Queue" = "Transparent+10" "RenderType" = "Transparent" "IgnoreProjector" = "True" }
        Blend One One
        ZWrite Off
        Cull Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            fixed4 _Color;
            float _Intensity;

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            v2f vert(appdata_base v)
            {
                v2f o;
                float3 center = mul(UNITY_MATRIX_MV, float4(0, 0, 0, 1)).xyz;
                float scale = length(float3(unity_ObjectToWorld[0].x, unity_ObjectToWorld[1].x, unity_ObjectToWorld[2].x));
                scale *= max(1, -center.z / 10);
                center += normalize(-center) * 0.03;
                float3 viewPos = center + float3(v.vertex.xy * scale, 0);
                o.pos = mul(UNITY_MATRIX_P, float4(viewPos, 1));
                o.uv = v.texcoord.xy;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float2 d = i.uv * 2 - 1;
                float r = dot(d, d);
                float glow = exp(-r * 18) + exp(-r * 4) * 0.35;
                return _Color * glow * _Intensity * 2;
            }
            ENDCG
        }
    }
}
