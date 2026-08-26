"""
PyInstaller Great Sage AI Setup
===============================
Build script para criar executável instalador do Grande Sábio AI.
"""

from setuptools import setup

# Dados do bundle
APP = ["installer.py"]  # Ponto de entrada

# Arquivos de dados/ativos opcionais
DATA_FILES = []

# Módulos ocultos (PyInstaller às vezes precisa deles explicitamente)
HIDDEN_IMPORTS = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "GreatSageAI_Clone",
    "GreatSageAI_Clone.core",
    "GreatSageAI_Clone.ui",
    "GreatSageAI_Clone.core.chain_of_thought",
    "GreatSageAI_Clone.core.llm",
    "GreatSageAI_Clone.core.speech_engine",
    "GreatSageAI_Clone.core.voice_pipeline",
    "GreatSageAI_Clone.core.persona",
    "GreatSageAI_Clone.core.request_router",
    "GreatSageAI_Clone.core.autonomous_planner",
    "GreatSageAI_Clone.core.code_analyzer",
    "GreatSageAI_Clone.core.chain_of_thought",
    "GreatSageAI_Clone.ui.programming_tab",
    "GreatSageAI_Clone.ui.qt_ui",
]

# Excluir módulos desnecessários
EXCLUDES = [
    "tkinter",
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "jinja2",
    "click",
    "pytest",
]

# Opções do PyInstaller
OPTIONS = {
    "optimize": True,  # Otimizar imports
    "debug": False,
    "strip": True,
    "upx": True,  # Compactar com UPX (se disponível)
    "console": True,  # Terminal visível (para instalador)
    "windowed": False,
    "icon": None,  # Ícone .ico caso tenha
    "offline": False,
    "hooks_dir": None,
    "excludes": EXCLUDES,
    "hiddenimports": HIDDEN_IMPORTS,
    "runtime_tmpdir": None,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"pyinstaller": OPTIONS},
    version="2.0.0",
    description="Instalador do Grande Sábio AI - Assistente Holográfico",
    author="Sistema Great Sage AI",
)