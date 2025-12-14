#!/bin/bash
# Build script for macOS

echo "Building UnifiedHub for macOS..."
pyinstaller build.spec --distpath ./dist/macos --workpath ./build/macos --specpath ./build

echo "macOS build complete!"
echo "App location: ./dist/macos/UnifiedHub.app"
echo "To run: open ./dist/macos/UnifiedHub.app"
