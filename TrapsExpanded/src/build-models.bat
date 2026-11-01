@echo off
rem Builds the traps' models: each blender\<trap>.py script makes its mesh, bakes its textures into
rem unity\Assets\TrapsExpanded\<Trap>\ and renders previews (to unity\Build\previews) and the item icon; then Unity
rem (batch mode with graphics) turns them into prefabs, builds Resources\trapsexpanded.unity3d and renders
rem unity\Build\<Trap>-preview.png. Needs Blender on PATH (or BLENDER set) and Unity 2022.3.62f2 (or UNITY set), with
rem Unity Hub signed in.
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "PROJECT=%MOD%\unity"
if not defined BLENDER set "BLENDER=blender"
if not defined UNITY set "UNITY=%ProgramFiles%\Unity\Hub\Editor\2022.3.62f2\Editor\Unity.exe"
if not exist "%UNITY%" (
    echo Could not find Unity 2022.3.62f2 at "%UNITY%". Install it with Unity Hub or set UNITY.
    exit /b 1
)
if not exist "%PROJECT%\Build\previews" mkdir "%PROJECT%\Build\previews"

for %%T in (tesla_coil:TeslaCoil:DementiveTrapTeslaCoil) do (
    for /f "tokens=1-3 delims=:" %%a in ("%%T") do (
        echo Blender: %%a
        "%BLENDER%" -b --factory-startup --python-exit-code 1 --python "%MOD%\blender\%%a.py" -- "%PROJECT%\Assets\TrapsExpanded\%%b" ^
            "%PROJECT%\Build\previews" "%MOD%\UIAtlases\ItemIconAtlas\%%c.png" > "%PROJECT%\Build\blender-%%a.log" 2>&1
        if errorlevel 1 (
            echo Blender failed; see "%PROJECT%\Build\blender-%%a.log".
            exit /b 1
        )
    )
)

echo Unity: prefabs, bundle and previews
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod TrapsBuilder.BuildAndPreview -logFile "%PROJECT%\Build\unity.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\trapsexpanded.unity3d" "%MOD%\Resources\trapsexpanded.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\trapsexpanded.unity3d.
