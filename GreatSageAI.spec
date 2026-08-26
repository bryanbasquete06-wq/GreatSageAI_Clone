# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/modules', 'GreatSageAI_Clone/modules'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/ui', 'GreatSageAI_Clone/ui'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/core', 'GreatSageAI_Clone/core'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/memory', 'GreatSageAI_Clone/memory'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/plugins', 'GreatSageAI_Clone/plugins'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/config', 'GreatSageAI_Clone/config'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/tests', 'GreatSageAI_Clone/tests'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/great_sage.ico', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/great_sage_icon.png', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/.env.example', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/main.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/great_sage_app.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/great_sage_console.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/assistant.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/app_tray.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/gui_launcher.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/run_tests.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/setup_api_keys.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/test_providers.py', 'GreatSageAI_Clone'), ('F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/test_voice.py', 'GreatSageAI_Clone')]
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
    ['F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/main.py'],
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
    name='GreatSageAI',
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
    icon=['F:/programação/J.A.R.V.I.S/GreatSageAI_Clone/great_sage.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GreatSageAI',
)
