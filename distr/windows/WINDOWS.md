# UnifiedHub for Windows

This folder will contain the Windows build of UnifiedHub once built on Windows.

## Build on Windows

1. Install Python 3.8+ and ensure `python` and `pip` are in PATH
2. Install dependencies:
```cmd
pip install -r requirements.txt
pip install pyinstaller
```
3. Build:
```cmd
python build.py windows
```

Output:
- Executable at `dist\windows\UnifiedHub\UnifiedHub.exe`

## Run
Double-click `UnifiedHub.exe` or run from Command Prompt:
```cmd
.\n dist\windows\UnifiedHub\UnifiedHub.exe
```

If Windows Defender warns about an unsigned app, allow it (development builds).

## Optional: Installer
Use Inno Setup or NSIS to create an installer.

## About
UnifiedHub integrates Google, Discord, AI, search, news, utilities, and more, in a single Tkinter app.
