# -*- mode: python ; coding: utf-8 -*-

PATH_TO_SELENIUMWIRE = r'C:\Users\zdaneel\.conda\envs\mercari\lib\site-packages\seleniumwire'
PATH_TO_DRIVER = r'C:\Users\zdaneel\OneDrive\Desktop\my_mercari_bot\driver'

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        (PATH_TO_SELENIUMWIRE, 'seleniumwire'),
        (PATH_TO_DRIVER, 'driver')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MercariMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MercariMonitor',
)
