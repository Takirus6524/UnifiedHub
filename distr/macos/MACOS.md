# UnifiedHub for macOS

This folder will contain the macOS build of UnifiedHub once built on macOS.

## Build on macOS

```bash
# From project root
pip install pyinstaller
python build.py macos
```

Output:
- App bundle at `dist/macos/UnifiedHub.app`

## Run

```bash
open dist/macos/UnifiedHub.app
```

If macOS warns the app is from an unidentified developer:
```bash
xattr -d com.apple.quarantine dist/macos/UnifiedHub.app
open dist/macos/UnifiedHub.app
```

## Code Signing (optional)
For distribution:
```bash
codesign -s - --deep dist/macos/UnifiedHub.app
```

## About
UnifiedHub integrates Google, Discord, AI, search, news, utilities, and more, in a single Tkinter app.
