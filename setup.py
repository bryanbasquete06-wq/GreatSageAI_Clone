"""
PyInstaller Elivea Setup
===============================
Build script para criar executável instalador do Elívea AI.
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
    "EliveaAI_Clone",
    "EliveaAI_Clone.core",
    "EliveaAI_Clone.ui",
    "EliveaAI_Clone.core.chain_of_thought",
    "EliveaAI_Clone.core.llm",
    "EliveaAI_Clone.core.speech_engine",
    "EliveaAI_Clone.core.voice_pipeline",
    "EliveaAI_Clone.core.persona",
    "EliveaAI_Clone.core.request_router",
    "EliveaAI_Clone.core.autonomous_planner",
    "EliveaAI_Clone.core.code_analyzer",
    "EliveaAI_Clone.core.chain_of_thought",
    "EliveaAI_Clone.ui.programming_tab",
    "EliveaAI_Clone.ui.qt_ui",
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
    description="Instalador do Elívea AI - Assistente Holográfico",
    author="Sistema Elivea",
)