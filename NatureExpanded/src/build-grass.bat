@echo off
rem Builds Resources\natureexpanded-grass.unity3d, the tiles the mod adds to the game's grass texture sheet, from the
rem renders in unity\Build\grass (made by blender\grass\grass_tiles.py) with Unity 2022.3.62f2 in batch mode, and
rem saves unity\Build\grass\sheet*.png: the game's own sheets with the tiles copied in, as the mod does it. Needs
rem Unity 2022.3.62f2 (or UNITY set) with Unity Hub signed in.
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "PROJECT=%MOD%\unity"
if not defined UNITY set "UNITY=%ProgramFiles%\Unity\Hub\Editor\2022.3.62f2\Editor\Unity.exe"
if not exist "%UNITY%" (
    echo Could not find Unity 2022.3.62f2 at "%UNITY%". Install it with Unity Hub or set UNITY.
    exit /b 1
)
if not exist "%PROJECT%\Build" mkdir "%PROJECT%\Build"

echo Unity: grass tiles
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod NatureGrassBuilder.Build -logFile "%PROJECT%\Build\unity-grass.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity-grass.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\grass-bundle\natureexpanded-grass.unity3d" "%MOD%\Resources\natureexpanded-grass.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\natureexpanded-grass.unity3d.
