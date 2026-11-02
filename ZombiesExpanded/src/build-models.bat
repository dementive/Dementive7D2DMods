@echo off
rem Builds the gear and growth models: each blender\<model>.py script (all but the kits) makes its pieces on the
rem reference zombie, bakes their textures into unity\Assets\ZombiesExpanded\Models\<Name>\ and renders previews on
rem the stand-in body (unity\Build\previews); then build-bundle.bat turns them into prefabs, builds the bundle and
rem renders them on vanilla zombies (unity\Build\models). Needs Blender on PATH (or BLENDER set), and Unity for the
rem second half (see build-bundle.bat).
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "PROJECT=%MOD%\unity"
if not defined BLENDER set "BLENDER=blender"
if not exist "%PROJECT%\Build\previews" mkdir "%PROJECT%\Build\previews"

for %%F in ("%MOD%\blender\*.py") do (
    if /i not "%%~nF"=="zkit" if /i not "%%~nF"=="zombiekit" (
        echo Blender: %%~nF
        "%BLENDER%" -b --factory-startup --python-exit-code 1 --python "%%F" -- "%PROJECT%\Assets\ZombiesExpanded\Models" ^
            "%PROJECT%\Build\previews" > "%PROJECT%\Build\blender-%%~nF.log" 2>&1
        if errorlevel 1 (
            echo Blender failed; see "%PROJECT%\Build\blender-%%~nF.log".
            exit /b 1
        )
    )
)
call "%SRC%build-bundle.bat"
