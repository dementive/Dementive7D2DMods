@echo off
rem Builds Resources\natureexpanded-trees.unity3d from the trees in unity\Assets\NatureExpanded\Trees (made by the
rem blender\trees\*.py scripts) with Unity 2022.3.62f2 in batch mode, writes unity\Build\tree-sizes.txt for
rem gen_nature.py, and renders unity\Build\trees\*.png: each tree in the game's plant shader beside vanilla's own, its
rem LODs, its bark, and a grove. Needs Unity 2022.3.62f2 (or UNITY set) with Unity Hub signed in.
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

echo Unity: trees
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod NatureTreeBuilder.Build -logFile "%PROJECT%\Build\unity-trees.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity-trees.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\trees-bundle\natureexpanded-trees.unity3d" "%MOD%\Resources\natureexpanded-trees.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\natureexpanded-trees.unity3d.
