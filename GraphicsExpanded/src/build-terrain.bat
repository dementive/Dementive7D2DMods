@echo off
rem Builds the photoscanned terrain textures into Resources\graphicsexpanded_terrain.bundle (see GfxTerrainPack.cs).
rem   build-terrain.bat <sources> <export>
rem <sources> is the folder fetch-terrain-textures.ps1 downloaded the Poly Haven sets into, and <export> the folder
rem "gfxe terrain export" saved the game's own ground textures into (for color matching), usually
rem %APPDATA%\7DaysToDie\GraphicsExpanded\TerrainExport. Needs Unity 2022.3.62f2 signed in to Unity Hub. The bundle is
rem about 300 MB, too big for GitHub, so it's left out of git: build it from the script instead.
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "PROJECT=%MOD%\unity"
if "%~2"=="" (
    echo Usage: build-terrain.bat ^<sources^> ^<export^>
    exit /b 1
)
set "GFX_TERRAIN_SOURCES=%~1"
set "GFX_TERRAIN_EXPORT=%~2"
if not defined UNITY set "UNITY=%ProgramFiles%\Unity\Hub\Editor\2022.3.62f2\Editor\Unity.exe"
if not exist "%UNITY%" (
    echo Could not find Unity 2022.3.62f2 at "%UNITY%". Install it with Unity Hub or set UNITY.
    exit /b 1
)

"%UNITY%" -batchmode -nographics -quit -projectPath "%PROJECT%" -executeMethod GfxTerrainPack.Build -logFile "%PROJECT%\Build\terrain.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\terrain.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\terrain\graphicsexpanded_terrain.bundle" "%MOD%\Resources\graphicsexpanded_terrain.bundle" >nul
if errorlevel 1 exit /b 1
echo Built Resources\graphicsexpanded_terrain.bundle.
