#!/usr/bin/env python3
"""
Universal build script for UnifiedHub
Works on Windows, macOS, and Linux
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def get_platform():
    """Get the current platform"""
    return platform.system().lower()

def build_app(target_platform=None):
    """Build UnifiedHub for the specified platform"""
    if target_platform is None:
        target_platform = get_platform()
    
    target_platform = target_platform.lower()
    
    # Validate platform
    valid_platforms = ['windows', 'darwin', 'linux']
    if target_platform == 'darwin':
        target_platform = 'macos'
    
    if target_platform not in ['windows', 'macos', 'linux']:
        print(f"Error: Invalid platform '{target_platform}'")
        print(f"Valid options: windows, macos, linux")
        return False
    
    print(f"\nBuilding UnifiedHub for {target_platform.upper()}...")
    print("-" * 50)
    
    # Create output directories
    build_dir = Path('build') / target_platform
    dist_dir = Path('dist') / target_platform
    
    build_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd = [
        'pyinstaller',
        'build.spec',
        f'--distpath={dist_dir}',
        f'--workpath={build_dir}',
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        
        print("\n" + "=" * 50)
        print(f"✓ {target_platform.upper()} build successful!")
        print("=" * 50)
        
        # Show output location
        if target_platform == 'macos':
            print(f"\nApp location: {dist_dir}/UnifiedHub.app")
            print(f"To run: open {dist_dir}/UnifiedHub.app")
        elif target_platform == 'windows':
            print(f"\nExecutable location: {dist_dir}\\UnifiedHub\\UnifiedHub.exe")
            print(f"To run: Double-click UnifiedHub.exe")
        else:  # linux
            print(f"\nExecutable location: {dist_dir}/UnifiedHub/UnifiedHub")
            print(f"To run: {dist_dir}/UnifiedHub/UnifiedHub")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ PyInstaller not found. Install with: pip install pyinstaller")
        return False

def main():
    """Main entry point"""
    print("\n" + "=" * 50)
    print("UnifiedHub - Multi-Platform Builder")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        current = get_platform()
        print(f"\nDetected platform: {current.upper()}")
        target = None
    
    success = build_app(target)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
