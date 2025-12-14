# UnifiedHub for Linux

This folder contains the Linux build of UnifiedHub.

## Run

```bash
./UnifiedHub
```

If you see a permission error:
```bash
chmod +x ./UnifiedHub
./UnifiedHub
```

## Requirements
- Modern Linux distro (glibc 2.17+)
- No Python required; everything is bundled

## Notes
- First launch may take a few seconds while libraries load.
- If UI does not appear, run from terminal to see logs:
```bash
./UnifiedHub --verbose
```

## Troubleshooting
- Missing libraries: ensure `libX11`, `libXext`, `libXi`, `libXrender`, `libXtst`, `libXcursor`, `libXrandr` are present.
- Wayland issues: try running under X11 or install `xorg-x11` packages.

## About
UnifiedHub integrates Google, Discord, AI, search, news, utilities, and more, in a single Tkinter app.
