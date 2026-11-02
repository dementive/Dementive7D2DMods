param([string]$Destination = (Join-Path $PSScriptRoot "..\blender\textures"))
# Downloads the Poly Haven texture sets (CC0, https://polyhaven.com) the trap models are textured with: each set's
# color, OpenGL normal, AO/roughness/metal and displacement maps at 2k as JPEG, into
# $Destination\<set>\<set>_{diff|nor_gl|arm|disp}_2k.jpg (blender\textures, not committed). Blender projects them
# onto the models and bakes the result, so only the baked textures ship. Files already there and intact are skipped.
# Keep the list in step with trapkit.PHOTO.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

$sets = @(
    "rusty_painted_metal", "green_metal_rust", "container_side", "metal_plate_02", "rust_coarse_01",
    "worn_corrugated_iron", "weathered_planks"
)
# Poly Haven's name for each map, and the suffix trapkit reads (some sets name their color map "diffuse")
$maps = [ordered]@{ Diffuse = "diff"; nor_gl = "nor_gl"; arm = "arm"; Displacement = "disp" }

foreach ($set in $sets) {
    $files = Invoke-RestMethod "https://api.polyhaven.com/files/$set"
    $folder = Join-Path $Destination $set
    New-Item -ItemType Directory -Force $folder | Out-Null
    foreach ($map in $maps.Keys) {
        $file = $files.$map.'2k'.jpg
        if ($null -eq $file) { throw "Poly Haven has no 2k JPEG $map map for $set" }
        $path = Join-Path $folder ("{0}_{1}_2k.jpg" -f $set, $maps[$map])
        if ((Test-Path $path) -and (Get-FileHash $path -Algorithm MD5).Hash -eq $file.md5) { continue }
        Write-Host "Downloading $set $map"
        Invoke-WebRequest $file.url -OutFile $path -UseBasicParsing
        if ((Get-FileHash $path -Algorithm MD5).Hash -ne $file.md5) { throw "$path didn't download intact; run this again" }
    }
}
Write-Host "All $($sets.Count) sets are in $Destination"
