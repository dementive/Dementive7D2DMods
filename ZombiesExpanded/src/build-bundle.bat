@echo off
rem Builds Resources\zombiesexpanded.unity3d (the overlay and eyeshine shaders, the blood drip effect) with Unity
rem 2022.3.62f2 in batch mode, and renders unity\Build\looks-*.png: the looks on vanilla zombies loaded from the game's
rem own bundles. Needs Unity 2022.3.62f2 (or UNITY set) with Unity Hub signed in.
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

echo Unity: bundle and previews
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod ZombiesBuilder.BuildAndPreview -logFile "%PROJECT%\Build\unity.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\zombiesexpanded.unity3d" "%MOD%\Resources\zombiesexpanded.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\zombiesexpanded.unity3d.
