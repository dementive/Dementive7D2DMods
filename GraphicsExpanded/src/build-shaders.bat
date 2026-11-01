@echo off
rem Builds the mod's shaders (unity\Assets\GraphicsExpanded) into Resources\graphicsexpanded.bundle with the Unity
rem editor in batch mode. Needs Unity 2022.3.62f2, the game's exact version: set UNITY to its Unity.exe if it isn't
rem in Unity Hub's default folder. The first run sets up the project and takes a few minutes.
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "PROJECT=%MOD%\unity"
if not defined UNITY set "UNITY=%ProgramFiles%\Unity\Hub\Editor\2022.3.62f2\Editor\Unity.exe"
if not exist "%UNITY%" (
    echo Could not find Unity 2022.3.62f2 at "%UNITY%". Install it with Unity Hub or set UNITY.
    exit /b 1
)

"%UNITY%" -batchmode -nographics -quit -projectPath "%PROJECT%" -executeMethod GfxBundleBuilder.Build -logFile "%PROJECT%\Build\unity.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\graphicsexpanded.bundle" "%MOD%\Resources\graphicsexpanded.bundle" >nul
if errorlevel 1 exit /b 1
echo Built Resources\graphicsexpanded.bundle.
