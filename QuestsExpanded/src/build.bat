@echo off
rem Builds QuestsExpanded.dll against the installed game's DLLs using the C# compiler that ships
rem with Visual Studio, so no .NET SDK is needed. Paths are relative to this file, which must stay
rem in <game>\Mods\Dementive7D2DMods\QuestsExpanded\src.
setlocal
set "SRC=%~dp0"
set "GAME=%SRC%..\..\..\.."
set "MANAGED=%GAME%\7DaysToDie_Data\Managed"
set "HARMONY=%GAME%\Mods\0_TFP_Harmony"
set "OUT=%SRC%..\QuestsExpanded.dll"

set "CSC="
for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -find MSBuild\**\Bin\Roslyn\csc.exe`) do set "CSC=%%i"
if not defined CSC (
    echo Could not find csc.exe. Install Visual Studio ^(any edition^).
    exit /b 1
)

rem C# 9 is the newest language version Unity 2022 (the game's runtime) officially supports
"%CSC%" -nologo -target:library -nostdlib -noconfig -langversion:9.0 -optimize+ -debug:portable ^
    -out:"%OUT%" -pdb:"%SRC%..\QuestsExpanded.pdb" ^
    -r:"%MANAGED%\mscorlib.dll" -r:"%MANAGED%\System.dll" -r:"%MANAGED%\System.Core.dll" ^
    -r:"%MANAGED%\netstandard.dll" -r:"%MANAGED%\Assembly-CSharp.dll" -r:"%MANAGED%\LogLibrary.dll" ^
    -r:"%MANAGED%\UnityEngine.dll" -r:"%MANAGED%\UnityEngine.CoreModule.dll" -r:"%HARMONY%\0Harmony.dll" ^
    -recurse:"%SRC%Harmony\*.cs" -recurse:"%SRC%Scripts\*.cs" -recurse:"%SRC%NetPackage\*.cs"
if errorlevel 1 exit /b 1

echo Built QuestsExpanded.dll.
