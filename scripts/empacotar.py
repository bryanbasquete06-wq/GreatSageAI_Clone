# -*- coding: utf-8 -*-
"""
Great Sage AI — Empacotador
Cria pacote portatil + ZIP para distribuicao.
Execute: py -3 empacotar.py
"""
import os
import shutil
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DIST = PROJECT / "dist"
BUILD_DIST = DIST / "GreatSageAI"
PORTABLE = DIST / "GreatSageAI_Portatil"
ZIP_PATH = DIST / "GreatSageAI_Portatil.zip"

def create_portable():
    print("[1/3] Criando pacote portatil...")

    if PORTABLE.exists():
        shutil.rmtree(PORTABLE)
    PORTABLE.mkdir()

    # Copy build
    if BUILD_DIST.exists():
        shutil.copytree(BUILD_DIST, PORTABLE / "GreatSageAI")

    # Launcher
    (PORTABLE / "Iniciar.bat").write_text(
        '@echo off\n'
        'chcp 65001 >nul 2>&1\n'
        'title Great Sage AI\n'
        'color 0A\n'
        'echo.\n'
        'echo  ========================================\n'
        'echo   GREAT SAGE AI — Iniciando...\n'
        'echo  ========================================\n'
        'echo.\n'
        'cd /d "%~dp0GreatSageAI"\n'
        'start "" GreatSageAI.exe\n',
        encoding="utf-8"
    )

    # README
    (PORTABLE / "LEIA-ME.txt").write_text(
        "========================================\n"
        "  GREAT SAGE AI v1.0\n"
        "  Assistente Pessoal com IA\n"
        "========================================\n\n"
        "COMO USAR:\n"
        "1. Extraia todos os arquivos para uma pasta\n"
        "2. Clique duas vezes em 'Iniciar.bat'\n"
        "3. Pronto! O Great Sage AI vai abrir.\n\n"
        "CONFIGURACAO (opcional):\n"
        "- Dentro da pasta GreatSageAI, edite o arquivo '.env'\n"
        "- Adicione suas chaves de API:\n"
        "    GROQ_API_KEY=sua_chave_aqui\n"
        "    OPENROUTER_API_KEY=sua_chave_aqui\n"
        "    GEMINI_API_KEY=sua_chave_aqui\n"
        "- Sem chaves, o app funciona com funcionalidades offline\n\n"
        "REQUISITOS:\n"
        "- Windows 10 ou 11 (64-bit)\n"
        "- 4GB de RAM minimo\n"
        "- 1GB de espaco em disco\n\n"
        "SUPORTE:\n"
        "- GitHub: https://github.com/anomalyco/opencode/issues\n",
        encoding="utf-8"
    )

    # .env template
    (PORTABLE / "GreatSageAI" / ".env").write_text(
        "# Great Sage AI — Configuracao de API Keys\n"
        "# Copie este arquivo e preencha suas chaves\n"
        "# Opcional: sem chaves, funcs offline funcionam\n\n"
        "# Chave do Groq (gratuita em console.groq.com)\n"
        "# GROQ_API_KEY=\n\n"
        "# Chave do OpenRouter (gratuita em openrouter.ai)\n"
        "# OPENROUTER_API_KEY=\n\n"
        "# Chave do Google Gemini (gratuita em aistudio.google.com)\n"
        "# GEMINI_API_KEY=\n\n"
        "# Chave do DeepSeek (gratuita em platform.deepseek.com)\n"
        "# DEEPSEEK_API_KEY=\n",
        encoding="utf-8"
    )

    print(f"  [OK] {PORTABLE}")

def create_zip():
    print("[2/3] Gerando ZIP...")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PORTABLE):
            for file in files:
                fp = Path(root) / file
                arcname = fp.relative_to(PORTABLE.parent)
                zf.write(fp, arcname)

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"  [OK] {ZIP_PATH} ({size_mb:.1f} MB)")

def print_summary():
    print("[3/3] Resumo:")
    exe = BUILD_DIST / "GreatSageAI.exe"
    total = sum(f.stat().st_size for f in BUILD_DIST.rglob("*") if f.is_file())
    print(f"  Executavel:  {exe}")
    print(f"  Tamanho:     {total / (1024*1024):.0f} MB")
    print(f"  Portatil:    {PORTABLE}")
    print(f"  ZIP:         {ZIP_PATH}")

def main():
    print("=" * 60)
    print("  GREAT SAGE AI — EMPACOTADOR")
    print("=" * 60)
    print()

    if not BUILD_DIST.exists():
        print("[ERRO] Execute build.py primeiro!")
        return

    create_portable()
    create_zip()
    print_summary()

    print()
    print("=" * 60)
    print("  DISTRIBUICAO PRONTA!")
    print("=" * 60)
    print()
    print("  Para distribuir:")
    print("  1. Envie o arquivo GreatSageAI_Portatil.zip")
    print("  2. O usuario extrai e clica em Iniciar.bat")
    print("  3. Nao precisa instalar nada!")
    print()

if __name__ == "__main__":
    main()
