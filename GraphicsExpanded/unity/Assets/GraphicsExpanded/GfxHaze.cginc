// Distance haze, shared by Haze.shader (over the solid world) and Water.shader (over the water's reflections).
// GfxHaze sets these as globals every frame; with w = 0 in _GfxHazeParams the haze is off.
#ifndef GFX_HAZE_INCLUDED
#define GFX_HAZE_INCLUDED

float4 _GfxHazeParams;      // x: thickness per meter at the ground, y: the ground's height where drawn, z: 1 / meters up to thin to a third, w: 1 when on
float4 _GfxHazeColor;       // rgb: the air's own color (the sky's hue at the fog's brightness), w: meters of clear air before it starts
float4 _GfxHazeSunDir;      // xyz: towards the sun
float4 _GfxHazeSunColor;    // rgb: the sun's glow through the haze

// For something at p seen from eye: rgb, the light the haze adds in front of it; a, how much of it gets through
float4 GfxHaze(float3 eye, float3 p)
{
    if (_GfxHazeParams.w <= 0)
        return float4(0, 0, 0, 1);
    float3 ray = p - eye;
    float distance = length(ray);
    // Thinner with height: the thickness at the eye, times the hazy part of the ray, times how much it thins along
    // the way. Nearby stays crisp: the haze only counts past the clear stretch
    float rise = ray.y * _GfxHazeParams.z;
    float along = abs(rise) > 1e-3 ? (1 - exp(-rise)) / rise : 1 - 0.5 * rise;
    float atEye = exp(-clamp((eye.y - _GfxHazeParams.y) * _GfxHazeParams.z, -4, 20));
    float hazy = max(distance - _GfxHazeColor.w, 0);
    float through = exp(-max(_GfxHazeParams.x * atEye * hazy * along, 0));
    float toSun = saturate(dot(ray / max(distance, 1e-3), _GfxHazeSunDir.xyz));
    float3 light = _GfxHazeColor.rgb + _GfxHazeSunColor.rgb * pow(toSun, 8);
    return float4(light * (1 - through), through);
}

#endif
