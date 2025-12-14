# Building UnifiedHub for Different Platforms

This guide explains how to create standalone executable files for Windows, macOS, and Linux.

## Prerequisites

1. **Python 3.8+** installed on your system
2. All dependencies installed: `pip install -r requirements.txt`
3. PyInstaller installed: `pip install pyinstaller`
4. Virtual environment activated (recommended)

## Building for Your Current Platform

### Linux

```bash
chmod +x build-linux.sh
./build-linux.sh
```

The executable will be created at: `./dist/linux/UnifiedHub/UnifiedHub`

To run:

```bash
./dist/linux/UnifiedHub/UnifiedHub
```

To create a desktop shortcut:

```bash
# Copy to applications
cp -r dist/linux/UnifiedHub ~/.local/share/applications/unifiedhub.desktop

# Or create a symlink
ln -s $(pwd)/dist/linux/UnifiedHub/UnifiedHub ~/Desktop/UnifiedHub
```

### macOS

```bash
chmod +x build-macos.sh
./build-macos.sh
```

The app will be created at: `./dist/macos/UnifiedHub.app`

To run:

```bash
open ./dist/macos/UnifiedHub.app
```

To create an alias:

```bash
ln -s $(pwd)/dist/macos/UnifiedHub.app ~/Desktop/UnifiedHub
```

### Windows

Run the batch file from Command Prompt or PowerShell:

```cmd
build-windows.bat
```

Or using PowerShell:

```powershell
.\build-windows.bat
```

The executable will be created at: `.\dist\windows\UnifiedHub\UnifiedHub.exe`

Double-click to run, or create a shortcut on your desktop.

## Cross-Platform Building (Advanced)

To build for other platforms, you need to do so on that platform:

- **Build for Windows** → Run on Windows with Python installed
- **Build for macOS** → Run on macOS with Python installed
- **Build for Linux** → Run on Linux with Python installed

PyInstaller is platform-specific and creates executables only for the platform it's run on.

## Customizing the Build

Edit `build.spec` to customize:

- **Icon**: Add your own `icon.ico` (Windows), `icon.icns` (macOS), or `icon.png` (Linux)
- **Console**: Change `console=False` to `console=True` to show terminal output
- **Hidden Imports**: Add any missing module names that PyInstaller couldn't detect
- **Data Files**: Include additional files (templates, configs, etc.)

### Adding an Icon

**Windows**:

```bash
# Convert PNG to ICO
convert icon.png icon.ico
# Update build.spec: icon='icon.ico'
```

**macOS**:

```bash
# Create iconset and convert
# Update build.spec: icon='icon.icns'
```

**Linux**:

```bash
# No icon needed for Linux executable
# Update build.spec to remove icon reference
```

## Troubleshooting

### "No module named 'X'"

Add the module name to `hiddenimports=[]` in `build.spec`

Example:

```python
hiddenimports=[
    'tkinter',
    'requests',
    'bs4',
    'PIL',
    'psutil',
    'dotenv',
    'mistralai',
    'your_missing_module',
]
```

### "Permission denied" on Linux/macOS

Make build scripts executable:

```bash
chmod +x build-linux.sh build-macos.sh
```

### Large executable file size

This is normal. PyInstaller bundles Python runtime + all dependencies.
Typical size: 80-150 MB depending on installed packages.

To reduce size:

- Remove unused dependencies from `requirements.txt`
- Use `--onefile` flag in PyInstaller (slower startup, single executable)

### macOS Code Signing Issues

If you get signing errors on macOS:

```bash
# Allow running unsigned apps (development only)
xattr -d com.apple.quarantine ./dist/macos/UnifiedHub.app
```

Or code sign properly:

```bash
codesign -s - --deep ./dist/macos/UnifiedHub.app
```

## Distribution

After building:

1. **Windows**: Create an installer with NSIS or Inno Setup
2. **macOS**: Create a `.dmg` installer or distribute `.app` directly
3. **Linux**: Create `.AppImage`, `.deb`, or `.rpm` package

## Platform-Specific Notes

### Windows Requirements

- Requires Windows 7 or later
- .exe file can be signed with a certificate for distribution
- Windows Defender may flag unsigned executables (false positive)

### macOS Requirements

- Requires macOS 10.12 or later
- App is unsigned (will show security warning first run)
- Code sign with your certificate for distribution
- Runs native on both Intel and Apple Silicon (M1/M2/M3) when built on that architecture

### Linux Requirements

- Requires glibc 2.17+ (most modern distributions)
- Desktop integration via `.desktop` file
- Can be packaged as AppImage, Snap, or Flatpak for broader compatibility

## Next Steps

1. Build for your current platform
2. Test the executable thoroughly
3. Customize icons and branding
4. Create distribution packages as needed
5. Host on GitHub Releases or your website

For questions, see [PyInstaller documentation](https://pyinstaller.org/)
