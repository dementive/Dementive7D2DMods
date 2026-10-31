@echo off
rem Builds the C# tools in Scripts into Scripts\bin with the C# compiler that ships with Visual Studio
rem (no .NET SDK needed): XmlPatch.exe and Api.exe for validation, IconTool.exe for weapon icons.
setlocal
set "SCRIPTS=%~dp0"
set "BIN=%SCRIPTS%bin"

set "CSC="
for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -find MSBuild\**\Bin\Roslyn\csc.exe`) do set "CSC=%%i"
if not defined CSC (
    echo Could not find csc.exe. Install Visual Studio ^(any edition^).
    exit /b 1
)
for %%i in ("%CSC%") do set "ROSLYN=%%~dpi"
rem Api.exe uses Roslyn, which is built against netstandard; these facades come with the .NET Framework 4.8 targeting pack
set "FACADES=%ProgramFiles(x86)%\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.8\Facades"
if not exist "%BIN%" mkdir "%BIN%"

"%CSC%" -nologo -optimize+ -r:System.Xml.dll -out:"%BIN%\XmlPatch.exe" "%SCRIPTS%Validation\XmlPatch.cs" || exit /b 1
"%CSC%" -nologo -optimize+ -r:System.Drawing.dll -out:"%BIN%\IconTool.exe" "%SCRIPTS%WeaponsExpanded\IconTool.cs" || exit /b 1
"%CSC%" -nologo -optimize+ -r:"%ROSLYN%Microsoft.CodeAnalysis.dll" -r:"%ROSLYN%Microsoft.CodeAnalysis.CSharp.dll" ^
    -r:"%ROSLYN%System.Collections.Immutable.dll" -r:"%FACADES%\System.Runtime.dll" -r:"%FACADES%\netstandard.dll" ^
    -out:"%BIN%\Api.exe" "%SCRIPTS%Validation\Api.cs" || exit /b 1

echo Built XmlPatch.exe, IconTool.exe and Api.exe in %BIN%
echo Api.exe loads Roslyn from ROSLYN_DIR; set it to %ROSLYN% if Visual Studio isn't in the default location.
