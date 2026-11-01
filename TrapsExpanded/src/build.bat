@echo off
rem Builds TrapsExpanded.dll against the installed game's DLLs using the C# compiler that ships with Visual Studio,
rem so no .NET SDK is needed. Paths are relative to this file, which must stay in
rem <game>\Mods\Dementive7D2DMods\TrapsExpanded\src. The models are built separately by build-models.bat.
setlocal
set "SRC=%~dp0"
set "MOD=%SRC%.."
set "GAME=%SRC%..\..\..\.."
set "MANAGED=%GAME%\7DaysToDie_Data\Managed"
set "OUT=%MOD%\TrapsExpanded.dll"

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
    -r:"%MANAGED%\UnityEngine.PhysicsModule.dll" ^
    "%SRC%*.cs"
if errorlevel 1 exit /b 1

echo Built TrapsExpanded.dll.
