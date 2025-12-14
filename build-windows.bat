@echo off
REM Build script for Windows

echo Building UnifiedHub for Windows...
pyinstaller build.spec --distpath .\dist\windows --workpath .\build\windows --specpath .\build

echo Windows build complete!
echo Executable location: .\dist\windows\UnifiedHub\UnifiedHub.exe
pause
