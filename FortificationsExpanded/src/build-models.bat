@echo off
rem Builds the fortification models: each blender\<family>.py script makes every piece and stage of its family
rem (FBX files sharing one baked material) into unity\Assets\FortificationsExpanded\<Family>\, renders previews (to
rem unity\Build\previews) and the item icon; then Unity (batch mode with graphics) turns them into prefabs, builds
rem Resources\fortificationsexpanded.unity3d and renders unity\Build\<Piece>-preview.png. Needs Blender on PATH (or
rem BLENDER set) and Unity 2022.3.62f2 (or UNITY set), with Unity Hub signed in. Pass script:folder:icon entries
rem (see MODELS below) to rebuild only those; Unity always rebuilds them all.
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

rem script:folder:icon for every family
set "MODELS=sandbags:Sandbags:DementiveFortSandbagWall palisade:Palisade:DementiveFortPalisade"
set "MODELS=%MODELS% chainlink:ChainLink:DementiveFortChainLink tank_traps:TankTraps:DementiveFortTankTraps"
set "MODELS=%MODELS% hesco:Hesco:DementiveFortHesco container:Container:DementiveFortContainer"
if not "%~1"=="" set "MODELS=%*"

for %%T in (%MODELS%) do (
    for /f "tokens=1-3 delims=:" %%a in ("%%T") do (
        echo Blender: %%a
        "%BLENDER%" -b --factory-startup --python-exit-code 1 --python "%MOD%\blender\%%a.py" -- "%PROJECT%\Assets\FortificationsExpanded\%%b" ^
            "%PROJECT%\Build\previews" "%MOD%\UIAtlases\ItemIconAtlas\%%c.png" > "%PROJECT%\Build\blender-%%a.log" 2>&1
        if errorlevel 1 (
            echo Blender failed; see "%PROJECT%\Build\blender-%%a.log".
            exit /b 1
        )
    )
)

echo Unity: prefabs, bundle and previews
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod FortBuilder.BuildAndPreview -logFile "%PROJECT%\Build\unity.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\fortificationsexpanded.unity3d" "%MOD%\Resources\fortificationsexpanded.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\fortificationsexpanded.unity3d.
