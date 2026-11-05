@echo off
rem Builds Resources\natureexpanded.unity3d from the plant models in unity\Assets\NatureExpanded\Models (made by the
rem blender\*.py scripts) with Unity 2022.3.62f2 in batch mode, and renders unity\Build\plants\<Name>.png (each plant
rem in the game's plant shader, up close and as a drift) and lineup.png. Needs Unity 2022.3.62f2 (or UNITY set) with
rem Unity Hub signed in. Pass plant names (Poppy,Lupine) to render only their previews; the bundle always has all.
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
set "ONLY="
if not "%~1"=="" set "ONLY=-plants %~1"

echo Unity: bundle and previews
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod NatureBuilder.BuildAndPreview %ONLY% -logFile "%PROJECT%\Build\unity.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\natureexpanded.unity3d" "%MOD%\Resources\natureexpanded.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\natureexpanded.unity3d.
