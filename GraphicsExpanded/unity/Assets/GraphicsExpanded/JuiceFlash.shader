// Game juice (GfxJuiceFlash): the flash a zombie (or anything that bleeds) gives off when it's hit, brightest round
// its edges. Drawn over the creature's own renderers with CommandBuffer.DrawRenderer after the scene, so it follows
// the skinned pose exactly and leaves the game's materials alone. Adds light only.
Shader "GraphicsExpanded/JuiceFlash"
{
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" }

        Pass
        {
            Blend One One
            ZWrite Off
            ZTest LEqual
            Offset -1, -1

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"

            float4 _GfxJuiceFlash;      // rgb: the flash's color, a: how strong it is now, 0 to 1

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 normal : TEXCOORD0;
                float3 view : TEXCOORD1;
            };

            v2f vert(appdata_base v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.normal = UnityObjectToWorldNormal(v.normal);
                o.view = WorldSpaceViewDir(v.vertex);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                float rim = 1 - saturate(dot(normalize(i.normal), normalize(i.view)));
                float glow = (0.25 + 1.6 * rim * rim) * _GfxJuiceFlash.a;
                return float4(_GfxJuiceFlash.rgb * glow, 0);
            }
            ENDCG
        }
    }
}
