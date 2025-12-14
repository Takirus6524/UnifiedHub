# UnifiedHub - Quick Build Reference

## One-Command Build

```bash
python build.py linux    # Linux
python build.py macos    # macOS  
python build.py windows  # Windows
```

## Build Output Locations

| Platform | Location | Run Command |
|----------|----------|------------|
| **Linux** | `dist/linux/UnifiedHub/UnifiedHub` | `./dist/linux/UnifiedHub/UnifiedHub` |
| **macOS** | `dist/macos/UnifiedHub.app` | `open dist/macos/UnifiedHub.app` |
| **Windows** | `dist/windows/UnifiedHub/UnifiedHub.exe` | Double-click or `.\dist\windows\UnifiedHub\UnifiedHub.exe` |

## Requirements for Building

- Python 3.8+
- `pip install -r requirements.txt`
- `pip install pyinstaller`
- Virtual environment activated

## Build Files Included

- **build.py** - Universal Python builder (works on all platforms)
- **build.spec** - PyInstaller configuration
- **build-linux.sh** - Linux-specific shell script
- **build-macos.sh** - macOS-specific shell script
- **build-windows.bat** - Windows-specific batch file

## Cross-Platform Notes

⚠️ **Important**: You must build on the target platform

- Build for Linux → Run on Linux with Python
- Build for macOS → Run on macOS with Python
- Build for Windows → Run on Windows with Python

PyInstaller creates native executables only for the OS it runs on.

## File Sizes (Approximate)

- Linux executable: ~80-100 MB
- macOS app bundle: ~150-200 MB
- Windows executable: ~100-150 MB

This includes Python runtime + all dependencies bundled inside.

## Troubleshooting

**"No module named X"**
→ Add to `hiddenimports=[]` in build.spec

**"Permission denied" (Linux/macOS)**
→ `chmod +x build-linux.sh build-macos.sh`

**Large file size**
→ Normal! Includes Python runtime. Remove unused packages from requirements.txt

**macOS "App can't be opened"**
→ `xattr -d com.apple.quarantine dist/macos/UnifiedHub.app`

## Next Steps

1. ✓ Build executable: `python build.py [platform]`
2. ✓ Test the app: Run the executable
3. Add custom icon: Place `icon.ico/icns/png` in project root
4. Create installer: Use NSIS (Windows), DMG (macOS), AppImage (Linux)
5. Distribute to users

For detailed guide, see **BUILD_GUIDE.md**
