param([string]$Destination = (Join-Path $PSScriptRoot "..\blender\textures"))
# Downloads the Poly Haven texture sets (CC0, https://polyhaven.com) the Stone Works models (blender\stone_works.py)
# are textured with: color, OpenGL normal, AO/roughness/metal and displacement maps at 2k as JPEG, into
# $Destination\<set>\<set>_{diff|nor_gl|arm|disp}_2k.jpg (blender\textures, not committed). Same layout and rules as
# fetch-textures.ps1; the integrator can fold this list into that script's $sets. Files already there and intact are
# skipped.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

$sets = @(
    "rock_boulder_dry", "dry_riverbed_rock", "quarry_wall_02", "rock_face_03", "dark_rock_02", "rough_plaster_03",
    "mossy_rock", "lichen_rock"
)
$maps = [ordered]@{ Diffuse = "diff"; nor_gl = "nor_gl"; arm = "arm"; Displacement = "disp" }

foreach ($set in $sets) {
    $files = Invoke-RestMethod "https://api.polyhaven.com/files/$set" -UserAgent "Mozilla/5.0"
    $folder = Join-Path $Destination $set
    New-Item -ItemType Directory -Force $folder | Out-Null
    foreach ($map in $maps.Keys) {
        $file = $files.$map.'2k'.jpg
        if ($null -eq $file) { throw "Poly Haven has no 2k JPEG $map map for $set" }
        $path = Join-Path $folder ("{0}_{1}_2k.jpg" -f $set, $maps[$map])
        if ((Test-Path $path) -and (Get-FileHash $path -Algorithm MD5).Hash -eq $file.md5) { continue }
        Write-Host "Downloading $set $map"
        Invoke-WebRequest $file.url -OutFile $path -UseBasicParsing -UserAgent "Mozilla/5.0"
        if ((Get-FileHash $path -Algorithm MD5).Hash -ne $file.md5) { throw "$path didn't download intact; run this again" }
    }
}
Write-Host "All $($sets.Count) sets are in $Destination"
