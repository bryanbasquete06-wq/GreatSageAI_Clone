# -*- coding: utf-8 -*-
"""
Great Sage AI — Ponto de Entrada Único
======================================
Restaura fluxo original que estava tão bom (usa great_sage_app Raphael)
Execute: python main.py
"""

import sys
import os
import traceback
from pathlib import Path

# Garante paths corretos: Clone em 0 para "core", parent para "GreatSageAI_Clone"
_project_root = str(Path(__file__).resolve().parent)
_parent = str(Path(_project_root).parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Tudo no disco F ASCII — perfeição, nada em C:
_F_TEMP = Path("F:/GreatSageTemp")
try:
    import tempfile
    _F_TEMP.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(_F_TEMP)
    os.environ["TMP"] = str(_F_TEMP)
    os.environ["TEMP"] = str(_F_TEMP)
    os.environ["TMPDIR"] = str(_F_TEMP)
    os.environ["HF_HOME"] = str(_F_TEMP / "hf_cache")
    os.environ["TRANSFORMERS_CACHE"] = str(_F_TEMP / "hf_cache")
    os.environ["HF_HUB_CACHE"] = str(_F_TEMP / "hf_cache")
    os.environ["TORCH_HOME"] = str(_F_TEMP / "torch_cache")
    os.environ["XDG_CACHE_HOME"] = str(_F_TEMP / "cache")
    os.environ["PIP_CACHE_DIR"] = str(_F_TEMP / "pip_cache")
    os.environ["UV_CACHE_DIR"] = str(_F_TEMP / "uv_cache")
    os.environ["PYTHONPYCACHEPREFIX"] = str(_F_TEMP / "pycache")
    os.environ["XTTS_CACHE"] = str(_F_TEMP / "xtts")
    os.environ["RAG_CACHE"] = str(_F_TEMP / "rag")
    for _d in ["hf_cache","torch_cache","cache","greatsage_tts","uploads","pip_cache","uv_cache","pycache","xtts","rag","logs","models"]:
        (_F_TEMP / _d).mkdir(parents=True, exist_ok=True)
    # garante que logs do app também vão para F
    os.environ["GREATSAGE_LOG_DIR"] = str(_F_TEMP / "logs")
except Exception:
    pass

# UTF-8 seguro
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ["PYTHONIOENCODING"] = "utf-8"
except Exception:
    pass
# Terminal invisível é feito pelo GreatSage.bat / GreatSage_invisivel.vbs usando pythonw — sem console preto feio

# Carrega .env
try:
    from dotenv import load_dotenv
    _env_path = Path(_project_root) / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

def main():
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.window.warning=false"
    print("="*60)
    print("  Great Sage AI — Raphael Class (restaurado)")
    print("  Iniciando via great_sage_app original...")
    print("="*60)
    try:
        # tenta importar com fallback PySide6/PyQt6 já tratado em great_sage_app
        from great_sage_app import main as app_main
        app_main()
    except Exception as e:
        traceback.print_exc()
        # salva crash
        try:
            p = Path(_project_root) / "config" / "crash.log"
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"\nCrash: {e}\n" + traceback.format_exc())
        except: pass
        print(f"[ERRO FATAL] {e}")
        # só pausa se tiver console visível
        if "--show-console" in sys.argv or sys.stdin.isatty():
            try:
                input("Pressione Enter para sair...")
            except: pass
        sys.exit(1)

if __name__ == "__main__":
    main()
