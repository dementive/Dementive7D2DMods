// Unity's built-in SpeedTree 8 shader (Nature/SpeedTree8: the same include, SpeedTree8Common.cginc, and the same
// passes and options), which the game's own trees use renamed as Game/SpeedTree8, plus the one thing the game adds
// that our trees need: the falling tree's fade. When a tree is felled the game (EntityFallingTree.updateTransform)
// dissolves it as it comes to rest by enabling ENABLE_FADEOUT on its materials and running _FadeOut from 1 down to 0;
// Unity's shader ignores both, so ours lay on the ground whole, sunk into the terrain, then vanished. Built into the
// tree bundle with the trees (NatureTreeBuilder).
Shader "NatureExpanded/SpeedTree8"
{
    Properties
    {
        _MainTex ("Base (RGB) Transparency (A)", 2D) = "white" {}
        _Color ("Color", Color) = (1,1,1,1)

        [Toggle(EFFECT_HUE_VARIATION)] _HueVariationKwToggle("Hue Variation", Float) = 0
        _HueVariationColor ("Hue Variation Color", Color) = (1.0,0.5,0.0,0.1)

        [Toggle(EFFECT_BUMP)] _NormalMapKwToggle("Normal Mapping", Float) = 0
        _BumpMap ("Normal Map", 2D) = "bump" {}

        _ExtraTex ("Smoothness (R), Metallic (G), AO (B)", 2D) = "(0.5, 0.0, 1.0)" {}
        _Glossiness ("Smoothness", Range(0.0, 1.0)) = 0.5
        _Metallic ("Metallic", Range(0.0, 1.0)) = 0.0

        [Toggle(EFFECT_SUBSURFACE)] _SubsurfaceKwToggle("Subsurface", Float) = 0
        _SubsurfaceTex ("Subsurface (RGB)", 2D) = "white" {}
        _SubsurfaceColor ("Subsurface Color", Color) = (1,1,1,1)
        _SubsurfaceIndirect ("Subsurface Indirect", Range(0.0, 1.0)) = 0.25

        [Toggle(EFFECT_BILLBOARD)] _BillboardKwToggle("Billboard", Float) = 0
        _BillboardShadowFade ("Billboard Shadow Fade", Range(0.0, 1.0)) = 0.5

        [Enum(No,2,Yes,0)] _TwoSided ("Two Sided", Int) = 2 // enum matches cull mode
        [KeywordEnum(None,Fastest,Fast,Better,Best,Palm)] _WindQuality ("Wind Quality", Range(0,5)) = 0

        _FadeOut ("Fade Out (felled)", Range(0.0, 1.0)) = 1.0
    }

    SubShader
    {
        Tags
        {
            "Queue"="AlphaTest"
            "IgnoreProjector"="True"
            "RenderType"="TransparentCutout"
            "DisableBatching"="LODFading"
        }
        LOD 400
        Cull [_TwoSided]

        CGPROGRAM
            #pragma surface FadingSurf SpeedTreeSubsurface vertex:SpeedTreeVert dithercrossfade addshadow
            #pragma target 3.0
            #pragma multi_compile_vertex LOD_FADE_PERCENTAGE
            #pragma instancing_options assumeuniformscaling maxcount:50

            #pragma shader_feature_local _WINDQUALITY_NONE _WINDQUALITY_FASTEST _WINDQUALITY_FAST _WINDQUALITY_BETTER _WINDQUALITY_BEST _WINDQUALITY_PALM
            #pragma shader_feature_local EFFECT_BILLBOARD
            #pragma shader_feature_local EFFECT_HUE_VARIATION
            #pragma shader_feature_local EFFECT_SUBSURFACE
            #pragma shader_feature_local EFFECT_BUMP
            #pragma shader_feature_local EFFECT_EXTRA_TEX
            // Switched on at run time by the game, so both variants must be built
            #pragma multi_compile_local _ ENABLE_FADEOUT

            #define ENABLE_WIND
            #define EFFECT_BACKSIDE_NORMALS
            #include "SpeedTree8Common.cginc"

            half _FadeOut;

            void FadingSurf(Input IN, inout SurfaceOutputStandard OUT)
            {
                SpeedTreeSurf(IN, OUT);
                #ifdef ENABLE_FADEOUT
                    // Dissolve: each texel block of the texture drops out at its own point as _FadeOut falls, in
                    // shadows too (addshadow runs this surface function)
                    float2 cell = floor(IN.uv_MainTex * 256.0);
                    float n = frac(sin(dot(cell, float2(12.9898, 78.233))) * 43758.5453);
                    clip(_FadeOut - n - 0.001);
                #endif
            }
        ENDCG
    }
}
