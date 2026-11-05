param([Parameter(Mandatory = $true)][string]$Destination)
# Downloads the Poly Haven texture sets (CC0, https://polyhaven.com) that GfxTerrainPack builds the photoscanned ground
# textures from: each set's color, OpenGL normal, AO/roughness/metal and displacement maps at 2k as JPEG, into
# $Destination\<set>\<set>_{diff|nor_gl|arm|disp}_2k.jpg. About 170 MB. Files already there and intact are skipped.
# Keep the list in step with GfxTerrainPack.Sets. Then run build-terrain.bat <Destination> <export>.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

$sets = @(
    "snow_02", "rock_face_03", "forest_leaves_02", "asphalt_07", "gravel_road", "red_laterite_soil_stones",
    "forest_ground_04", "burned_ground_01", "sandy_gravel_02", "tiger_rock", "brown_mud_rocks_01", "gravelly_sand",
    "rock_ground", "road_damaged", "dry_ground_rocks", "rock_06", "rocks_ground_06"
)
# Poly Haven's name for each map, and the suffix GfxTerrainPack reads (some sets name their color map "diffuse")
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
