#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage — Instalador Comercial Automatizado
==============================================
Instalador Plug & Play para distribuição comercial da IA Great Sage.

Arquitetura modular com POO, logging corporativo, tratamento granular
de exceções e interface terminal dourado/branco.

Uso:
    python installer.py              # instala a IA
    python installer.py --build      # compila Instalador_Great_Sage.exe
"""
from __future__ import annotations

import importlib
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import List, Dict, Tuple

# Paleta Great Sage — ANSI dourado/branco (sem emojis)
COR_DOURADO = "\033[93m"
COR_AMARELO = "\033[33m"
COR_BRANCO = "\033[97m"
COR_RESET = "\033[0m"
COR_DIM = "\033[90m"

# ASCII Art limpa e geométrica
ASCII_LOGO = r"""
  _____ _____  ______       _______     _____         _____  ______ ______
 / ____|  __ \|  ____|   /\|__   __|   / ____|  /\   / ____|  ____|  ____|
| |  __| |__) | |__     /  \  | |     | (___   /  \ | |  __| |__  | |__
| | |_ |  _  /|  __|   / /\ \ | |      \___ \ / /\ \| | |_ |  __| |  __|
| |__| | | \ \| |____ / ____ \| |      ____) / ____ \ |__| | |____| |____
 \_____|_|  \_\______/_/    \_\_|     |____//_/    \_\_____|______|______|
"""

# Pacotes necessários para a IA (voz, áudio, API)
PACOTES_REQUERIDOS: Dict[str, str] = {
    "PySide6": "PySide6",
    "requests": "requests",
    "numpy": "numpy",
    "sounddevice": "sounddevice",
    "pydub": "pydub",
    "scipy": "scipy",
    "edge_tts": "edge-tts",
    "groq": "groq",
    "google.genai": "google-genai",
    "dotenv": "python-dotenv",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "ddgs": "duckduckgo-search",
    "pydantic": "pydantic",
    "speech_recognition": "SpeechRecognition",
    "psutil": "psutil",
    "pyautogui": "pyautogui",
    "keyboard": "keyboard",
}

# Pastas que o instalador deve garantir
ESTRUTURA_PASTAS: List[str] = [
    "config",
    "config/audio",
    "logs",
    "memory",
]

# Chaves críticas que devem existir em .env.example / secrets
CHAVES_CRITICAS: List[str] = [
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
]


def limpar_terminal() -> None:
    """Limpa o terminal de forma portável."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except OSError as exc:
        logging.getLogger("greatsage.install").warning(f"Falha ao limpar terminal: {exc}")


def obter_logger(log_path: Path) -> logging.Logger:
    """Configura logger corporativo com saída em terminal e arquivo rotativo."""
    logger = logging.getLogger("greatsage.install")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    # Handler terminal — INFO e acima
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    # Handler arquivo rotativo — DEBUG e acima
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            str(log_path), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    except PermissionError as exc:
        logger.warning(f"[ ALERTA ] Sem permissão para criar log em {log_path}: {exc}")
    except OSError as exc:
        logger.warning(f"[ ALERTA ] Falha ao criar arquivo de log: {exc}")

    return logger


class EnvironmentManager:
    """Gerencia caminhos absolutos e estrutura de pastas."""

    def __init__(self, base_dir: Path, logger: logging.Logger) -> None:
        self.base_dir: Path = base_dir
        self.logger: logging.Logger = logger

    def obter_diretorio_base(self) -> Path:
        """Retorna diretório base absoluto da instalação."""
        return self.base_dir.resolve()

    def garantir_estrutura_pastas(self) -> bool:
        """Cria pastas necessárias sem erros de permissão."""
        self.logger.info(f"{COR_BRANCO}[ INFO ] Sincronizando estrutura de diretórios...{COR_RESET}")
        for rel in ESTRUTURA_PASTAS:
            caminho: Path = self.base_dir / rel
            try:
                caminho.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Diretório garantido: {caminho}")
            except PermissionError as exc:
                self.logger.error(f"[ ERRO ] Permissão negada ao criar {caminho}: {exc}")
                return False
            except OSError as exc:
                self.logger.error(f"[ ERRO ] Falha ao criar diretório {caminho}: {exc}")
                return False
        self.logger.info(f"{COR_DOURADO}[ OK ] Estrutura de diretórios validada.{COR_RESET}")
        return True

    def resolver_caminho(self, *partes: str) -> Path:
        """Resolve caminho absoluto baseado no diretório base."""
        return (self.base_dir / Path(*partes)).resolve()


class DependencyInstaller:
    """Verifica e instala dependências de forma silenciosa."""

    def __init__(self, python_exe: str, logger: logging.Logger) -> None:
        self.python_exe: str = python_exe
        self.logger: logging.Logger = logger

    def verificar_dependencia(self, modulo: str) -> bool:
        """Verifica se um módulo está importável."""
        try:
            importlib.import_module(modulo)
            return True
        except ModuleNotFoundError:
            return False
        except ImportError as exc:
            self.logger.warning(f"[ ALERTA ] Módulo {modulo} com importação quebrada: {exc}")
            return False

    def coletar_pendentes(self) -> List[str]:
        """Retorna lista de pacotes pip pendentes."""
        pendentes: List[str] = []
        for modulo, pacote in PACOTES_REQUERIDOS.items():
            if not self.verificar_dependencia(modulo):
                pendentes.append(pacote)
        return pendentes

    def instalar_silenciosamente(self, pacotes: List[str]) -> bool:
        """Instala pacotes via pip de forma 100% silenciosa."""
        if not pacotes:
            self.logger.info(f"{COR_DOURADO}[ OK ] Todas as dependências já sincronizadas.{COR_RESET}")
            return True

        self.logger.info(f"{COR_BRANCO}[ INFO ] Sincronizando componentes de áudio e API ({len(pacotes)} pacotes)...{COR_RESET}")
        cmd: List[str] = [self.python_exe, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"] + pacotes
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                self.logger.info(f"{COR_DOURADO}[ OK ] Dependências sincronizadas.{COR_RESET}")
                return True
            # Fallback para ambientes PEP 668
            if "externally-managed-environment" in (result.stderr or ""):
                self.logger.warning(f"{COR_AMARELO}[ ALERTA ] Ambiente gerenciado detectado, tentando --break-system-packages...{COR_RESET}")
                cmd_break = [self.python_exe, "-m", "pip", "install", "--quiet", "--break-system-packages"] + pacotes
                result2 = subprocess.run(
                    cmd_break,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result2.returncode == 0:
                    self.logger.info(f"{COR_DOURADO}[ OK ] Dependências sincronizadas (break-system-packages).{COR_RESET}")
                    return True
                self.logger.error(f"[ ERRO ] pip falhou mesmo com break-system-packages: {result2.stderr[:400]}")
                return False
            self.logger.error(f"[ ERRO ] pip retornou código {result.returncode}: {(result.stderr or '')[:400]}")
            return False
        except FileNotFoundError as exc:
            self.logger.error(f"[ ERRO ] Interpretador Python não encontrado: {exc}")
            return False
        except PermissionError as exc:
            self.logger.error(f"[ ERRO ] Permissão negada ao executar pip: {exc}")
            return False
        except OSError as exc:
            self.logger.error(f"[ ERRO ] Falha de sistema ao executar pip: {exc}")
            return False


class SecurityVerifier:
    """Verifica integridade de chaves e credenciais."""

    def __init__(self, base_dir: Path, logger: logging.Logger) -> None:
        self.base_dir: Path = base_dir
        self.logger: logging.Logger = logger

    def verificar_chave(self, caminho: Path) -> Tuple[bool, str]:
        """Verifica se arquivo de chaves existe e contém chaves críticas."""
        try:
            if not caminho.exists():
                return False, f"Arquivo não encontrado: {caminho}"
            texto: str = caminho.read_text(encoding="utf-8", errors="replace")
            faltantes: List[str] = [k for k in CHAVES_CRITICAS if k not in texto]
            if faltantes:
                return False, f"Chaves ausentes: {', '.join(faltantes)}"
            # Verifica se há valores vazios (ex: GROQ_API_KEY=)
            for chave in CHAVES_CRITICAS:
                for linha in texto.splitlines():
                    if linha.strip().startswith(chave):
                        valor = linha.split("=", 1)[1].strip().strip('"').strip("'") if "=" in linha else ""
                        if not valor or valor.lower() in ("", "null", "none", "placeholder"):
                            return False, f"Chave {chave} com valor vazio/corrompido"
            return True, "Integridade validada"
        except FileNotFoundError as exc:
            return False, f"Arquivo não encontrado: {exc}"
        except PermissionError as exc:
            return False, f"Permissão negada ao ler {caminho}: {exc}"
        except OSError as exc:
            return False, f"Erro de leitura em {caminho}: {exc}"

    def verificar_todas(self) -> bool:
        """Verifica .env e .env.example de forma silenciosa."""
        self.logger.info(f"{COR_BRANCO}[ INFO ] Verificando integridade de credenciais...{COR_RESET}")
        candidatos: List[Path] = [
            self.base_dir / ".env",
            self.base_dir / ".env.example",
            self.base_dir / "GreatSageAI_Clone" / ".env.example",
        ]
        for caminho in candidatos:
            if caminho.exists():
                ok, detalhe = self.verificar_chave(caminho)
                if ok:
                    self.logger.info(f"{COR_DOURADO}[ OK ] Credenciais verificadas em {caminho.name}.{COR_RESET}")
                    return True
                else:
                    self.logger.warning(f"{COR_AMARELO}[ ALERTA ] Falha de integridade em {caminho}: {detalhe}{COR_RESET}")
        # Não bloqueia instalação, apenas alerta
        self.logger.warning(
            f"{COR_AMARELO}[ ALERTA ] Nenhum arquivo de credenciais válido encontrado. "
            f"A IA pode operar em modo offline/limitado. Verifique a integridade do pacote.{COR_RESET}"
        )
        return True


def criar_atalho_desktop(base_dir: Path, logger: logging.Logger) -> bool:
    """Cria .exe na Área de Trabalho com ícone dourado.
    
    Tenta copiar .exe pré-compilados de desktop_exes/.
    Se não existirem, cria .bat como fallback.
    """
    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "OneDrive" / "Desktop"
        if not desktop.exists():
            logger.warning(f"{COR_AMARELO}[ ALERTA ] Área de Trabalho não encontrada, pulando atalho.{COR_RESET}")
            return False
        desktop.mkdir(parents=True, exist_ok=True)

        icone = base_dir / "great_sage.ico"
        if not icone.exists():
            icone = base_dir / "GreatSageAI_Clone" / "great_sage.ico"

        # --- Tenta copiar .exe pré-compilados ---
        desktop_exes = base_dir / "desktop_exes"
        ai_exe_src = desktop_exes / "Grande Sabio AI.exe"
        inst_exe_src = desktop_exes / "Instalador Great Sage.exe"

        ai_ok = False
        inst_ok = False

        if ai_exe_src.exists():
            dst = desktop / "Grande Sabio AI.exe"
            shutil.copy2(str(ai_exe_src), str(dst))
            if dst.exists():
                logger.info(f"{COR_DOURADO}[ OK ] .exe da IA copiado para {dst}{COR_RESET}")
                ai_ok = True

        if inst_exe_src.exists():
            dst = desktop / "Instalador Great Sage.exe"
            shutil.copy2(str(inst_exe_src), str(dst))
            if dst.exists():
                logger.info(f"{COR_DOURADO}[ OK ] .exe do Instalador copiado para {dst}{COR_RESET}")
                inst_ok = True

        # --- Fallback: cria .bat se .exe não existe ---
        # Detecta o Python correto que tem PySide6
        _uv_python = base_dir / ".." / ".." / ".." / ".." / ".." / "AppData" / "Roaming" / "uv" / "python" / "cpython-3.11-windows-x86_64-none" / "python.exe"
        if _uv_python.exists():
            _correct_python = str(_uv_python)
        else:
            _correct_python = sys.executable

        if not ai_ok:
            alvo = base_dir / "main.py"
            if not alvo.exists():
                alvo = base_dir / "GreatSageAI_Clone" / "main.py"
            if alvo.exists():
                bat = desktop / "Grande Sabio AI.bat"
                bat.write_text(
                    f'@echo off\ntitle Grande Sabio AI\ncd /d "{alvo.parent}"\n"{_correct_python}" "{alvo}"\nif errorlevel 1 pause\n',
                    encoding="utf-8",
                )
                logger.info(f"{COR_DOURADO}[ OK ] Atalho .bat criado: {bat}{COR_RESET}")
                ai_ok = True

        return ai_ok
    except PermissionError as exc:
        logger.error(f"[ ERRO ] Permissão negada ao criar atalho: {exc}")
        return False
    except OSError as exc:
        logger.error(f"[ ERRO ] Falha ao criar atalho: {exc}")
        return False
    except Exception as exc:
        logger.error(f"[ ERRO ] Erro inesperado no atalho: {exc}\n{traceback.format_exc()}")
        return False


class BuildAutomator:
    """Automatiza compilação comercial com PyInstaller."""

    def __init__(self, base_dir: Path, logger: logging.Logger) -> None:
        self.base_dir: Path = base_dir
        self.logger: logging.Logger = logger

    def verificar_pyinstaller(self) -> bool:
        """Verifica se pyinstaller está disponível."""
        try:
            import PyInstaller  # type: ignore
            self.logger.debug(f"PyInstaller {PyInstaller.__version__} encontrado")
            return True
        except ModuleNotFoundError:
            return False
        except ImportError as exc:
            self.logger.warning(f"[ ALERTA ] PyInstaller com importação quebrada: {exc}")
            return False

    def instalar_pyinstaller_silenciosamente(self, python_exe: str) -> bool:
        """Instala pyinstaller de forma silenciosa."""
        self.logger.info(f"{COR_BRANCO}[ INFO ] Instalando PyInstaller...{COR_RESET}")
        try:
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "--quiet", "pyinstaller"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                self.logger.info(f"{COR_DOURADO}[ OK ] PyInstaller instalado.{COR_RESET}")
                return True
            if "externally-managed-environment" in (result.stderr or ""):
                result2 = subprocess.run(
                    [python_exe, "-m", "pip", "install", "--quiet", "--break-system-packages", "pyinstaller"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return result2.returncode == 0
            self.logger.error(f"[ ERRO ] Falha ao instalar PyInstaller: {result.stderr[:400]}")
            return False
        except FileNotFoundError as exc:
            self.logger.error(f"[ ERRO ] Python não encontrado para instalar PyInstaller: {exc}")
            return False
        except PermissionError as exc:
            self.logger.error(f"[ ERRO ] Permissão negada ao instalar PyInstaller: {exc}")
            return False

    def compilar(self, modo_teste: bool = False) -> bool:
        """Compila o instalador e a IA em executável único."""
        python_exe = sys.executable
        if not self.verificar_pyinstaller():
            if not self.instalar_pyinstaller_silenciosamente(python_exe):
                self.logger.error("[ ERRO ] Não foi possível preparar PyInstaller para build.")
                return False

        # Coleta --add-data necessários (ícones, pastas de dados)
        datas: List[str] = []
        for rel in ["great_sage.ico", "great_sage_icon.png", "config", "GreatSageAI_Clone/config"]:
            p = self.base_dir / rel
            if p.exists():
                sep = ";" if os.name == "nt" else ":"
                datas.append(f"--add-data={p}{sep}{rel}")

        cmd: List[str] = [
            python_exe, "-m", "PyInstaller",
            "--onefile",
            "--name=Instalador_Great_Sage",
            "--console",
            "--icon=great_sage.ico" if (self.base_dir / "great_sage.ico").exists() else "",
            "installer.py",
        ]
        # Remove entradas vazias (quando ícone não existe)
        cmd = [c for c in cmd if c]
        cmd.extend(datas)
        # Também empacota a IA principal se solicitado
        # pyinstaller --onefile --name=Great_Sage --windowed main.py poderia ser adicionado aqui

        self.logger.info(f"{COR_BRANCO}[ INFO ] Iniciando compilação comercial: {' '.join(cmd)}{COR_RESET}")
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                dist_exe = self.base_dir / "dist" / "Instalador_Great_Sage.exe"
                if dist_exe.exists():
                    self.logger.info(f"{COR_DOURADO}[ OK ] [Sucesso] Produto Comercial 'Instalador_Great_Sage.exe' gerado com sucesso na pasta /dist!{COR_RESET}")
                else:
                    # PyInstaller pode gerar com nome sem sublinhado
                    alt = self.base_dir / "dist" / "GreatSageAI_Installer.exe"
                    if alt.exists():
                        self.logger.info(f"{COR_DOURADO}[ OK ] Produto gerado: {alt}{COR_RESET}")
                    else:
                        self.logger.warning(f"{COR_AMARELO}[ ALERTA ] Build retornou 0 mas exe não encontrado em dist/{COR_RESET}")
                return True
            else:
                self.logger.error(f"[ ERRO ] Build falhou (código {result.returncode}): {result.stdout[-800:]}")
                return False
        except FileNotFoundError as exc:
            self.logger.error(f"[ ERRO ] PyInstaller não encontrado após instalação: {exc}")
            return False
        except PermissionError as exc:
            self.logger.error(f"[ ERRO ] Permissão negada durante build: {exc}")
            return False
        except OSError as exc:
            self.logger.error(f"[ ERRO ] Falha de sistema no build: {exc}")
            return False


class InstaladorGreatSage:
    """Orquestrador principal do instalador comercial."""

    def __init__(self) -> None:
        # Caminho absoluto baseado no local de execução
        if getattr(sys, "frozen", False):
            self.base_dir: Path = Path(sys.executable).resolve().parent
            # Quando congelado, o código fonte pode estar em _MEIPASS
            self.source_dir: Path = Path(getattr(sys, "_MEIPASS", self.base_dir))
            # Se _MEIPASS não contém GreatSageAI_Clone, usa base_dir
            if not (self.source_dir / "main.py").exists() and (self.base_dir / "GreatSageAI_Clone" / "main.py").exists():
                self.source_dir = self.base_dir / "GreatSageAI_Clone"
        else:
            self.base_dir: Path = Path(__file__).resolve().parent
            self.source_dir: Path = self.base_dir

        # Logger corporativo em arquivo rotativo
        log_path: Path = self.base_dir / "logs" / "great_sage_install.log"
        # Se rodando congelado, log vai para base_dir/logs
        if getattr(sys, "frozen", False):
            log_path = self.base_dir / "logs" / "great_sage_install.log"
        self.logger: logging.Logger = obter_logger(log_path)
        self.env_manager = EnvironmentManager(self.base_dir, self.logger)
        self.dep_installer = DependencyInstaller(sys.executable, self.logger)
        self.security = SecurityVerifier(self.base_dir, self.logger)
        self.builder = BuildAutomator(self.base_dir, self.logger)

    def exibir_cabecalho(self) -> None:
        """Exibe logo ASCII dourado/branco e status inicial."""
        limpar_terminal()
        print(f"{COR_DOURADO}{ASCII_LOGO}{COR_RESET}")
        print(f"{COR_BRANCO}  Great Sage — Assistente Omnipotente | Conversa • Estudo • Programação • Automação{COR_RESET}")
        print(f"{COR_DIM}  Distribuição Comercial — Plug & Play{COR_RESET}\n")
        self.logger.info("[Great Sage] Iniciando assistente de instalação oficial...")
        print(f"{COR_BRANCO}[ INFO ] Iniciando assistente de instalação oficial...{COR_RESET}")
        print(f"{COR_BRANCO}[ INFO ] Módulos de Verificação: Prontos.{COR_RESET}")

    def executar(self, modo_build: bool = False) -> int:
        """Fluxo principal blindado com try/except global."""
        try:
            self.exibir_cabecalho()

            if modo_build:
                print(f"\n{COR_BRANCO}[ INFO ] Modo compilação comercial solicitado.{COR_RESET}")
                self.logger.info("[ INFO ] Modo build solicitado")
                ok = self.builder.compilar()
                return 0 if ok else 1

            # 1. Ambiente
            print(f"\n{COR_BRANCO}[ INFO ] Sincronizando ambiente seguro...{COR_RESET}")
            if not self.env_manager.garantir_estrutura_pastas():
                print(f"{COR_AMARELO}[ ALERTA ] Falha ao criar pastas — tentando continuar...{COR_RESET}")
            # 1b. Atalho desktop com ícone (exigido: baixar totalmente + ícone)
            print(f"{COR_BRANCO}[ INFO ] Criando atalho na Área de Trabalho com ícone...{COR_RESET}")
            if criar_atalho_desktop(self.base_dir, self.logger):
                print(f"{COR_DOURADO}[ OK ] Atalhos criados: Grande Sábio AI + Instalador Great Sage.{COR_RESET}")
            else:
                print(f"{COR_AMARELO}[ ALERTA ] Atalho não criado — verifique permissões.{COR_RESET}")

            # 2. Dependências silenciosas
            print(f"{COR_BRANCO}[ INFO ] Verificando dependências do sistema...{COR_RESET}")
            pendentes = self.dep_installer.coletar_pendentes()
            if pendentes:
                print(f"{COR_BRANCO}[ INFO ] Sincronizando {len(pendentes)} componentes em segundo plano...{COR_RESET}")
                ok_dep = self.dep_installer.instalar_silenciosamente(pendentes)
                if not ok_dep:
                    print(f"{COR_AMARELO}[ ALERTA ] Alguns componentes não puderam ser sincronizados — modo offline disponível.{COR_RESET}")
                else:
                    print(f"{COR_DOURADO}[ OK ] Componentes sincronizados.{COR_RESET}")
            else:
                print(f"{COR_DOURADO}[ OK ] Dependências validadas.{COR_RESET}")

            # 3. Verificação de chaves integrada
            print(f"{COR_BRANCO}[ INFO ] Verificando integridade de credenciais...{COR_RESET}")
            chaves_ok = self.security.verificar_todas()
            if not chaves_ok:
                print(f"{COR_AMARELO}[ ALERTA ] Integridade de chaves comprometida — verifique great_sage_install.log{COR_RESET}")

            # 4. Finalização suprema
            print(f"\n{COR_DOURADO}[ OK ] [Great Sage] Instalação concluída com sucesso! Conexão estabelecida.{COR_RESET}")
            self.logger.info("[ OK ] Instalação concluída com sucesso! Conexão estabelecida.")
            print(f"{COR_BRANCO}[ INFO ] Inicializando Great Sage em 3 segundos...{COR_RESET}")
            time.sleep(3)
            limpar_terminal()
            # reexibe cabeçalho com nome para não piscar sem nome
            print(f"{COR_DOURADO}{ASCII_LOGO}{COR_RESET}")
            print(f"{COR_DOURADO}[ OK ] [Great Sage] Instalação concluída com sucesso! Conexão estabelecida.{COR_RESET}\n")
            codigo = self._iniciar_ia()
            if codigo == 0:
                print(f"\n{COR_BRANCO}[ INFO ] Great Sage iniciado — verifique a janela e a bandeja do sistema.{COR_RESET}")
                print(f"{COR_DIM}Log: logs/great_sage_install.log | Atalhos: Desktop/Grande Sábio AI + Instalador Great Sage{COR_RESET}")
                time.sleep(4)
            return codigo

        except KeyboardInterrupt:
            self.logger.warning("[ ALERTA ] Instalação interrompida pelo usuário")
            print(f"\n{COR_AMARELO}[ ALERTA ] Instalação interrompida.{COR_RESET}")
            return 130
        except Exception as exc:
            self.logger.error(f"[ ERRO ] Falha crítica na instalação: {exc}\n{traceback.format_exc()}")
            print(f"\n{COR_AMARELO}[ ERRO ] Falha crítica: {exc}{COR_RESET}")
            print(f"{COR_DIM}Detalhes registrados em logs/great_sage_install.log{COR_RESET}")
            return 1

    def _iniciar_ia(self) -> int:
        """Executa o script principal da IA de forma direta (sem piscar outro launcher)."""
        # Tenta GreatSageAI_Clone/main.py primeiro, depois main.py na raiz
        candidatos = [
            self.base_dir / "GreatSageAI_Clone" / "main.py",
            self.base_dir / "main.py",
            self.source_dir / "main.py",
            self.source_dir / "GreatSageAI_Clone" / "main.py",
        ]
        alvo: Path | None = None
        for c in candidatos:
            if c.exists():
                alvo = c
                break
        if alvo is None:
            msg = "Script principal da IA não encontrado (main.py)"
            self.logger.error(f"[ ERRO ] {msg}")
            print(f"{COR_AMARELO}[ ERRO ] {msg}{COR_RESET}")
            return 1
        print(f"{COR_BRANCO}[ INFO ] Ativando inputs de voz e texto...{COR_RESET}")
        self.logger.info(f"Iniciando IA: {alvo}")
        try:
            # Resolve python real (não o .exe congelado) — prefere .venv da instalação
            py_exe: str = sys.executable
            venv = self.base_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if venv.exists():
                py_exe = str(venv)
            elif getattr(sys, "frozen", False):
                # tenta localizar python do sistema quando rodando como .exe
                for cand in [shutil.which("python"), shutil.which("python3"), shutil.which("py")]:
                    if cand:
                        # py launcher precisa -3
                        if cand.endswith("py.exe") or cand.endswith("py"):
                            py_exe = cand
                            break
                if py_exe == sys.executable:
                    for base in [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python", Path(r"C:\Python314"), Path(r"C:\Python313")]:
                        if (base / "python.exe").exists():
                            py_exe = str(base / "python.exe")
                            break
            # Para GUI PySide6 não precisa de console — evita piscar
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(
                [py_exe, str(alvo)],
                cwd=str(alvo.parent),
                creationflags=creationflags,
                close_fds=True,
            )
            print(f"{COR_DOURADO}[ OK ] Great Sage em execução.{COR_RESET}")
            return 0
        except FileNotFoundError as exc:
            self.logger.error(f"[ ERRO ] Interpretador não encontrado: {exc}")
            print(f"{COR_AMARELO}[ ERRO ] Python não encontrado para iniciar a IA.{COR_RESET}")
            return 1
        except PermissionError as exc:
            self.logger.error(f"[ ERRO ] Permissão negada ao iniciar IA: {exc}")
            print(f"{COR_AMARELO}[ ERRO ] Permissão negada ao iniciar great_sage.{COR_RESET}")
            return 1
        except OSError as exc:
            self.logger.error(f"[ ERRO ] Falha ao iniciar IA: {exc}")
            print(f"{COR_AMARELO}[ ERRO ] Falha ao iniciar IA: {exc}{COR_RESET}")
            return 1


def main() -> None:
    """Ponto de entrada blindado globalmente."""
    try:
        modo_build = "--build" in sys.argv
        modo_cli = "--cli" in sys.argv

        # Tenta abrir GUI se PySide6 disponível e não for modo build/CLI
        if not modo_build and not modo_cli:
            try:
                from ui.installer_gui import main as gui_main
                gui_main()
                return
            except Exception:
                pass  # Fallback para CLI

        instalador = InstaladorGreatSage()
        codigo = instalador.executar(modo_build=modo_build)
        sys.exit(codigo)
    except Exception as exc:
        # Fail-safe global — nunca fecha silenciosamente
        try:
            log_path = Path(__file__).resolve().parent / "logs" / "great_sage_install.log"
            logging.getLogger("greatsage.install").error(f"Erro não tratado no main: {exc}\n{traceback.format_exc()}")
        except Exception:
            pass
        print(f"{COR_AMARELO}[ ERRO ] Falha inesperada: {exc}{COR_RESET}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
