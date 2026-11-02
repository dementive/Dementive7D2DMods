// Distance haze. GfxHaze runs this on the player camera after the solid world and before transparent objects: the
// further away each pixel is, the more of the air's own color it takes on (GfxHaze.cginc). The sky is left alone,
// since it's already as far as the eye can see.
Shader "Hidden/GraphicsExpanded/Haze"
{
    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always

        // What's there times how much gets through, plus the haze's light
        Pass
        {
            Blend One SrcAlpha

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"
            #include "GfxHaze.cginc"

            UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
            float4x4 _GfxInvProjection;     // the camera's, OpenGL style (camera.projectionMatrix.inverse)
            float4x4 _GfxCameraToWorld;
            float4 _GfxFullSize;            // xy: the camera's size, zw: 1 / it

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

            // Where the camera would see a point at this eye depth through this pixel (same as Volumetric.shader)
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

            float4 frag(v2f i) : SV_Target
            {
                float2 uv = i.pos.xy * _GfxFullSize.zw;
                float depth = LinearEyeDepth(SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, uv));
                if (depth > _ProjectionParams.z * 0.98)
                    return float4(0, 0, 0, 1);
                float4 haze = GfxHaze(_GfxCameraToWorld._m03_m13_m23, WorldFromDepth(uv, depth));
                if (Bad(haze))
                    return float4(0, 0, 0, 1);
                return float4(min(haze.rgb, 64), saturate(haze.a));
            }
            ENDCG
        }
    }
}
