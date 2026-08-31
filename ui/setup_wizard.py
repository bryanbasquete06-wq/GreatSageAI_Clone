# -*- coding: utf-8 -*-
"""
Elívea — Setup Wizard
=============================
Guiado de configuração na primeira execução.

Fluxo:
  1. Boas-vindas + nome do usuário
  2. Configuração de API keys (mínimo 1 provedor)
  3. Seleção de voz
  4. Teste de áudio
  5. Configurações finais
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QPixmap, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QStackedWidget, QFrame,
    QProgressBar, QCheckBox, QMessageBox, QFileDialog,
)


class SetupWizard(QWidget):
    """Wizard de configuração na primeira execução."""

    setup_complete = Signal() # Sinal quando o wizard termina

    # Provedores gratuitos ordenados por facilidade de uso
    FREE_PROVIDERS = [
        ("OpenRouter", "OPENROUTER_API_KEY", "openrouter.ai"),
        ("Groq", "GROQ_API_KEY", "console.groq.com"),
        ("Gemini", "GOOGLE_API_KEY", "aistudio.google.com"),
        ("Mistral", "MISTRAL_API_KEY", "console.mistral.ai"),
        ("Cohere", "COHERE_API_KEY", "dashboard.cohere.com"),
    ]

    VOICE_OPTIONS = [
        ("Elivea (Padrão)", "raphael"),
        ("Jarvis", "jarvis"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Elívea — Configuração Inicial")
        self.setMinimumSize(600, 500)
        self.setMaximumSize(700, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        self._current_step = 0
        self._user_name = ""
        self._api_keys = {}
        self._voice = "raphael"
        self._autostart = False

        self._setup_ui()
        self._show_step(0)

    def _setup_ui(self):
        """Monta a interface do wizard."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Header
        self._header = QLabel("Elívea")
        self._header.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._header)

        # Subtitle
        self._subtitle = QLabel("Configuração Inicial")
        self._subtitle.setFont(QFont("Segoe UI", 12))
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setStyleSheet("color: #888;")
        main_layout.addWidget(self._subtitle)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        main_layout.addWidget(sep)

        # Stack de páginas
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack, stretch=1)

        # Cria páginas
        self._stack.addWidget(self._create_welcome_page())
        self._stack.addWidget(self._create_name_page())
        self._stack.addWidget(self._create_api_keys_page())
        self._stack.addWidget(self._create_voice_page())
        self._stack.addWidget(self._create_finish_page())

        # Botões
        btn_layout = QHBoxLayout()

        self._btn_back = QPushButton("← Voltar")
        self._btn_back.setFixedWidth(120)
        self._btn_back.clicked.connect(self._prev_step)
        btn_layout.addWidget(self._btn_back)

        btn_layout.addStretch()

        self._btn_next = QPushButton("Próximo →")
        self._btn_next.setFixedWidth(120)
        self._btn_next.clicked.connect(self._next_step)
        btn_layout.addWidget(self._btn_next)

        main_layout.addLayout(btn_layout)

        # Progress
        self._progress = QProgressBar()
        self._progress.setMaximum(4)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        main_layout.addWidget(self._progress)

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        welcome = QLabel("Bem-vindo ao Elívea!")
        welcome.setFont(QFont("Segoe UI", 16))
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome)

        desc = QLabel(
            "Vou te guiar pela configuração inicial.\n\n"
            "Você precisará:\n"
            "• Um nome para eu te chamar\n"
            "• Pelo menos 1 chave de API gratuita\n"
            "• Escolher uma voz\n\n"
            "Isso leva menos de 2 minutos."
        )
        desc.setFont(QFont("Segoe UI", 11))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #aaa; line-height: 1.5;")
        layout.addWidget(desc)

        return page

    def _create_name_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Como devo te chamar?")
        label.setFont(QFont("Segoe UI", 16))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        desc = QLabel("Escolha um nome que eu usarei para me dirigir a você.")
        desc.setFont(QFont("Segoe UI", 11))
        desc.setStyleSheet("color: #aaa;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Ex: Mestre, Chef, ou seu nome...")
        self._name_input.setFixedWidth(300)
        self._name_input.setFont(QFont("Segoe UI", 12))
        self._name_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_input.returnPressed.connect(self._next_step)
        layout.addWidget(self._name_input, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return page

    def _create_api_keys_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        label = QLabel("Configure pelo menos 1 API Key gratuita")
        label.setFont(QFont("Segoe UI", 14))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        desc = QLabel(
            "Todos os provedores abaixo são 100% gratuitos.\n"
            "Copie a chave do site indicado e cole abaixo."
        )
        desc.setFont(QFont("Segoe UI", 10))
        desc.setStyleSheet("color: #aaa;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        self._api_inputs = {}
        for name, env_key, site in self.FREE_PROVIDERS:
            row = QHBoxLayout()

            lbl = QLabel(f"{name}:")
            lbl.setFixedWidth(100)
            lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(lbl)

            inp = QLineEdit()
            inp.setPlaceholderText(f" Cole sua chave de {site}")
            inp.setFont(QFont("Segoe UI", 10))
            inp.setEchoMode(QLineEdit.EchoMode.Password)
            row.addWidget(inp, stretch=1)

            btn = QPushButton("Visitar site")
            btn.setFixedWidth(100)
            btn.clicked.connect(lambda checked, s=site: self._open_browser(s))
            row.addWidget(btn)

            self._api_inputs[env_key] = inp
            layout.addLayout(row)

        self._api_status = QLabel("Nenhuma chave configurada")
        self._api_status.setStyleSheet("color: #f44;")
        self._api_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._api_status)

        layout.addStretch()
        return page

    def _create_voice_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Escolha sua voz")
        label.setFont(QFont("Segoe UI", 16))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        self._voice_combo = QComboBox()
        for display, key in self.VOICE_OPTIONS:
            self._voice_combo.addItem(display, key)
        self._voice_combo.setFixedWidth(250)
        self._voice_combo.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self._voice_combo, alignment=Qt.AlignmentFlag.AlignCenter)

        self._voice_test_btn = QPushButton("Testar voz")
        self._voice_test_btn.setFixedWidth(150)
        self._voice_test_btn.clicked.connect(self._test_voice)
        layout.addWidget(self._voice_test_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Autostart
        self._autostart_cb = QCheckBox("Iniciar automaticamente com o Windows")
        self._autostart_cb.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self._autostart_cb, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return page

    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Configuração Concluída!")
        label.setFont(QFont("Segoe UI", 18))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        desc = QLabel(
            "Tudo pronto! O Elívea será iniciado em instantes.\n\n"
            "Use sua voz ou digite comandos para interagir comigo.\n"
            "Diga 'ajuda' a qualquer momento para ver o que posso fazer."
        )
        desc.setFont(QFont("Segoe UI", 11))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #aaa; line-height: 1.5;")
        layout.addWidget(desc)

        layout.addStretch()
        return page

    def _show_step(self, index: int):
        """Mostra uma página do wizard."""
        self._current_step = index
        self._stack.setCurrentIndex(index)
        self._progress.setValue(index)

        # Atualiza botões
        self._btn_back.setVisible(index > 0)
        if index == 4: # Página final
            self._btn_next.setText("Iniciar!")
        else:
            self._btn_next.setText("Próximo →")

        # Validação
        if index == 1: # Nome
            self._btn_next.setEnabled(bool(self._name_input.text().strip()))
        elif index == 2: # API Keys
            self._validate_api_keys()
        else:
            self._btn_next.setEnabled(True)

    def _next_step(self):
        """Avança para próxima página."""
        if self._current_step == 1:
            self._user_name = self._name_input.text().strip()
            if not self._user_name:
                return

        if self._current_step == 2:
            if not self._get_configured_keys():
                return

        if self._current_step < 4:
            self._show_step(self._current_step + 1)
        else:
            self._finish_setup()

    def _prev_step(self):
        """Volta para página anterior."""
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _validate_api_keys(self):
        """Valida se pelo menos 1 API key foi configurada."""
        keys = self._get_configured_keys()
        count = len(keys)

        if count > 0:
            self._api_status.setText(f" {count} chave(s) configurada(s)")
            self._api_status.setStyleSheet("color: #4f4;")
            self._btn_next.setEnabled(True)
        else:
            self._api_status.setText("Nenhuma chave configurada")
            self._api_status.setStyleSheet("color: #f44;")
            self._btn_next.setEnabled(True) # Permite prosseguir sem keys

    def _get_configured_keys(self) -> dict:
        """Retorna API keys que foram preenchidas."""
        keys = {}
        for env_key, inp in self._api_inputs.items():
            val = inp.text().strip()
            if val:
                keys[env_key] = val
        return keys

    def _test_voice(self):
        """Testa a voz selecionada."""
        try:
            from core.speech_engine import SpeechEngine
            voice = self._voice_combo.currentData()
            engine = SpeechEngine(voice_key=voice)
            engine.speak("Teste de voz concluído! Esta é minha voz atual.")
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível testar a voz:\n{e}")

    def _open_browser(self, url: str):
        """Abre o site do provedor no navegador."""
        import webbrowser
        webbrowser.open(f"https://{url}")

    def _finish_setup(self):
        """Salva configurações e fecha o wizard."""
        config_dir = Path(__file__).resolve().parent.parent / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Salva nome do usuário
        settings_path = config_dir / "settings.json"
        settings = {}
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        settings["user_name"] = self._user_name
        settings["voice"] = self._voice_combo.currentData()
        settings["setup_complete"] = True
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

        # Salva API keys no .env
        env_path = Path(__file__).resolve().parent.parent / ".env"
        env_lines = []
        if env_path.exists():
            try:
                env_lines = env_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                pass

        # Atualiza ou adiciona keys
        for env_key, val in self._get_configured_keys().items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{env_key}="):
                    env_lines[i] = f"{env_key}={val}"
                    found = True
                    break
            if not found:
                env_lines.append(f"{env_key}={val}")

        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

        # Autostart
        if self._autostart_cb.isChecked():
            self._set_autostart(True)

        # Fecha wizard
        self.setup_complete.emit()
        self.close()

    def _set_autostart(self, enable: bool):
        """Configura autostart no Windows."""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                exe_path = sys.executable
                winreg.SetValueEx(key, "Elívea", 0, winreg.REG_SZ, f'"{exe_path}" --minimized')
            else:
                try:
                    winreg.DeleteValue(key, "Elívea")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass


def should_run_wizard() -> bool:
    """Verifica se o wizard deve ser executado."""
    settings_path = Path(__file__).resolve().parent.parent / "config" / "settings.json"
    if not settings_path.exists():
        return True
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        return not settings.get("setup_complete", False)
    except Exception:
        return True
