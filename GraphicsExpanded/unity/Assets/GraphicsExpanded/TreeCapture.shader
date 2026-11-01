// Pictures one view of a tree for the distant forests (GfxForest). GfxForest draws the game's own tree model with its
// materials' deferred pass into a small G-buffer of its own, and this turns that into two pictures:
// - color: the tree's diffuse color times its coverage, and the coverage (1 where the tree is, 0 around it);
// - normal: its normal in the view's space (x right, y up, z towards the viewer) as 0 to 1, times coverage, and its
//   occlusion times coverage.
// Times coverage, so that once the pictures are shrunk into mipmaps, dividing by the shrunk coverage gives back the
// tree's own color and normal at its edges instead of mixing in the empty background. Coverage is where a normal was
// written: the G-buffer is cleared to 0, and an encoded unit normal never is.
Shader "Hidden/GraphicsExpanded/TreeCapture"
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

            sampler2D _GfxCapture0;         // G-buffer 0: diffuse color, occlusion
            sampler2D _GfxCapture2;         // G-buffer 2: world normal as 0 to 1
            float4 _GfxCaptureSize;         // xy: pixels, zw: 1 / pixels
            float4x4 _GfxCaptureView;       // the view's world to view matrix

            struct v2f
            {
                float4 pos : SV_POSITION;
            };

            struct Pictures
            {
                float4 color : SV_Target0;
                float4 normal : SV_Target1;
            };

            // One triangle covering the picture
            v2f vert(uint id : SV_VertexID)
            {
                v2f o;
                float2 p = float2((id << 1) & 2, id & 2);
                o.pos = float4(p * 2 - 1, 0, 1);
                return o;
            }

            Pictures frag(v2f i)
            {
                float2 uv = i.pos.xy * _GfxCaptureSize.zw;
                float4 g0 = tex2D(_GfxCapture0, uv);
                float3 encoded = tex2D(_GfxCapture2, uv).rgb;
                float coverage = dot(encoded, encoded) > 0.05 ? 1 : 0;

                float3 viewNormal = mul((float3x3)_GfxCaptureView, encoded * 2 - 1);
                viewNormal = dot(viewNormal, viewNormal) > 1e-6 ? normalize(viewNormal) : float3(0, 0, 1);

                Pictures o;
                o.color = float4(g0.rgb * coverage, coverage);
                o.normal = float4((viewNormal * 0.5 + 0.5) * coverage, g0.a * coverage);
                return o;
            }
            ENDCG
        }
    }
}
