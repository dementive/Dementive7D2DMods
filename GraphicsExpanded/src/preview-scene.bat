@echo off
rem Renders the water and distance haze shaders outside the game into unity\Build\scene-preview.png (see
rem GfxScenePreview.cs). Needs Unity 2022.3.62f2, as build-shaders.bat does, and a graphics card: it runs in batch
rem mode but not -nographics.
setlocal
set "SRC=%~dp0"
set "PROJECT=%SRC%..\unity"
if not defined UNITY set "UNITY=%ProgramFiles%\Unity\Hub\Editor\2022.3.62f2\Editor\Unity.exe"
if not exist "%UNITY%" (
    echo Could not find Unity 2022.3.62f2 at "%UNITY%". Install it with Unity Hub or set UNITY.
    exit /b 1
)

"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod GfxScenePreview.Render -logFile "%PROJECT%\Build\scene-preview.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\scene-preview.log".
    exit /b 1
)
echo Wrote unity\Build\scene-preview.png.
