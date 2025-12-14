# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for UnifiedHub

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['unifiedhub.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'requests',
        'bs4',
        'PIL',
        'psutil',
        'dotenv',
        'mistralai',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UnifiedHub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if sys.platform == 'win32' else ('icon.icns' if sys.platform == 'darwin' else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='UnifiedHub',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='UnifiedHub.app',
        icon='icon.icns',
        bundle_identifier='com.unifiedhub.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
