@echo off
rem Builds Resources\natureexpanded-features.unity3d from the solid features (boulders, rock formations, cairns, bones)
rem in unity\Assets\NatureExpanded\Features (made by the blender\features\*.py scripts) with Unity 2022.3.62f2 in
rem batch mode, writes unity\Build\feature-sizes.txt for gen_nature.py, checks every collider against its mesh, and
rem renders unity\Build\features\*.png (each feature in the game's plant shader beside vanilla's boulder and a 1.8 m
rem figure, and beside its colliders). Pass feature names (MossyBoulder01,StoneCairn01) to render only their previews;
rem the bundle always has all. Needs Unity 2022.3.62f2 (or UNITY set) with Unity Hub signed in. Unity batch builds
rem share one project: take unity\Build\.unity-lock (mkdir) while running.
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
if not "%~1"=="" set "ONLY=-features %~1"

echo Unity: features
"%UNITY%" -batchmode -quit -projectPath "%PROJECT%" -executeMethod NatureFeatureBuilder.Build %ONLY% -logFile "%PROJECT%\Build\unity-features.log"
if errorlevel 1 (
    echo Unity failed; see "%PROJECT%\Build\unity-features.log".
    exit /b 1
)

if not exist "%MOD%\Resources" mkdir "%MOD%\Resources"
copy /y "%PROJECT%\Build\features-bundle\natureexpanded-features.unity3d" "%MOD%\Resources\natureexpanded-features.unity3d" >nul
if errorlevel 1 exit /b 1
echo Built Resources\natureexpanded-features.unity3d.
