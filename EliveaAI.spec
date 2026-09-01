# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/modules', 'EliveaAI_Clone/modules'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/ui', 'EliveaAI_Clone/ui'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/core', 'EliveaAI_Clone/core'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/memory', 'EliveaAI_Clone/memory'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/plugins', 'EliveaAI_Clone/plugins'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/config', 'EliveaAI_Clone/config'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/tests', 'EliveaAI_Clone/tests'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/elvea.ico', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/elvea_icon.png', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/.env.example', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/main.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/elvea_app.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/elvea_console.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/assistant.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/app_tray.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/gui_launcher.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/run_tests.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/setup_api_keys.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/test_providers.py', 'EliveaAI_Clone'), ('F:/programação/J.A.R.V.I.S/EliveaAI_Clone/test_voice.py', 'EliveaAI_Clone')]
binaries = []
hiddenimports = ['PySide6', 'groq', 'requests', 'numpy', 'sounddevice', 'pydub', 'scipy', 'edge_tts', 'google.genai', 'dotenv', 'imageio_ffmpeg', 'ddgs', 'pydantic', 'speech_recognition', 'psutil', 'pyautogui', 'keyboard', 'json', 'threading', 'subprocess', 'pathlib']
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('groq')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sounddevice')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pydub')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('google')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ddgs')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['F:/programação/J.A.R.V.I.S/EliveaAI_Clone/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='EliveaAI',
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
    icon=['F:/programação/J.A.R.V.I.S/EliveaAI_Clone/elvea.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EliveaAI',
)
