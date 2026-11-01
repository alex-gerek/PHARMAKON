# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

# Collect all hidden imports for FastAPI, Uvicorn, Soundfile, Scipy
hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'fastapi',
    'fastapi.staticfiles',
    'fastapi.responses',
    'fastapi.middleware.cors',
    'starlette',
    'starlette.staticfiles',
    'starlette.responses',
    'starlette.middleware.cors',
    'starlette.routing',
    'soundfile',
    'scipy',
    'scipy.signal',
    'scipy.ndimage',
    'numpy',
    'tkinter',
    'tkinter.filedialog',
]
hidden_imports += collect_submodules('uvicorn')
hidden_imports += collect_submodules('fastapi')
hidden_imports += collect_submodules('starlette')

datas = [
    ('gui/static', 'gui/static'),
    ('demo_audio', 'demo_audio'),
    ('pharmakon_hd_256.ico', '.'),
]
datas += collect_data_files('soundfile')

binaries = []
binaries += collect_dynamic_libs('soundfile')

a = Analysis(
    ['launcher.pyw'],
    pathex=['C:\\Users\\User\\PHARMAKON'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'torch', 'torchaudio', 'torchvision', 'pandas'],
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
    name='Pharmakon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pharmakon_hd_256.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PHARMAKON',
)
