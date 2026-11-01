@echo off
rem Builds GraphicsExpanded.dll against the installed game's DLLs using the C# compiler that ships with Visual Studio,
rem so no .NET SDK is needed. Paths are relative to this file, which must stay in
rem <game>\Mods\Dementive7D2DMods\GraphicsExpanded\src.
rem GearsAPI.dll is Gears' own, shipped in the mod folder so the mod loads without Gears installed. Replace it with
rem the one from the current Gears release when Gears updates.
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "GAME=%SRC%..\..\..\.."
set "MANAGED=%GAME%\7DaysToDie_Data\Managed"
set "HARMONY=%GAME%\Mods\0_TFP_Harmony"
set "OUT=%MOD%\GraphicsExpanded.dll"

set "CSC="
for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -find MSBuild\**\Bin\Roslyn\csc.exe`) do set "CSC=%%i"
if not defined CSC (
    echo Could not find csc.exe. Install Visual Studio ^(any edition^).
    exit /b 1
)

rem C# 9 is the newest language version Unity 2022 (the game's runtime) officially supports
"%CSC%" -nologo -target:library -nostdlib -noconfig -langversion:9.0 -optimize+ ^
    -out:"%OUT%" ^
    -r:"%MANAGED%\mscorlib.dll" -r:"%MANAGED%\System.dll" -r:"%MANAGED%\System.Core.dll" ^
    -r:"%MANAGED%\netstandard.dll" -r:"%MANAGED%\Assembly-CSharp.dll" -r:"%MANAGED%\LogLibrary.dll" ^
    -r:"%MANAGED%\UnityEngine.dll" -r:"%MANAGED%\UnityEngine.CoreModule.dll" ^
    -r:"%MANAGED%\Unity.Postprocessing.Runtime.dll" -r:"%MANAGED%\InControl.dll" ^
    -r:"%MANAGED%\UnityEngine.AssetBundleModule.dll" ^
    -r:"%HARMONY%\0Harmony.dll" -r:"%MOD%\GearsAPI.dll" ^
    "%SRC%*.cs"
if errorlevel 1 exit /b 1

echo Built GraphicsExpanded.dll.
