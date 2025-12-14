#!/bin/bash
# Build script for Linux

echo "Building UnifiedHub for Linux..."
pyinstaller build.spec --distpath ./dist/linux --workpath ./build/linux --specpath ./build

echo "Linux build complete!"
echo "Executable location: ./dist/linux/UnifiedHub/UnifiedHub"
