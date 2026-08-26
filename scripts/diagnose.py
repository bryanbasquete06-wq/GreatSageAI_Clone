#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — CLI Diagnostic Tool
====================================
Test and diagnose individual components from the command line.

Usage:
    python scripts/diagnose.py              # Full system diagnostic
    python scripts/diagnose.py voice        # Test voice pipeline
    python scripts/diagnose.py speech       # Test speech synthesis
    python scripts/diagnose.py llm          # Test LLM connectivity
    python scripts/diagnose.py health       # Run autonomous diagnostics
    python scripts/diagnose.py fix          # Auto-fix safe issues
    python scripts/diagnose.py index        # Test code index
    python scripts/diagnose.py intent       # Test intent engine
"""
from __future__ import annotations

import sys
import os
import sys
import time
from pathlib import Path

# Fix Windows cp1252 encoding for emoji output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


def _header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _ok(msg: str):
    print(f"  ✅ {msg}")


def _warn(msg: str):
    print(f"  ⚠️  {msg}")


def _fail(msg: str):
    print(f"  ❌ {msg}")


def _info(msg: str):
    print(f"  ℹ️  {msg}")


# ===================================================================
# Individual diagnostic commands
# ===================================================================

def diagnose_full():
    """Run a complete system diagnostic."""
    _header("Great Sage AI — Diagnostic Completo")
    diagnose_health()
    diagnose_speech()
    diagnose_llm()
    diagnose_intent()
    diagnose_index()
    print(f"\n{'='*60}")
    print("  Diagnóstico completo!")
    print(f"{'='*60}")


def diagnose_health():
    """Run autonomous engine diagnostics."""
    _header("Auto-Diagnóstico do Sistema")
    try:
        from core.autonomous_engine import run_diagnostics
        health = run_diagnostics(PROJECT_ROOT)
        score = health.health_score
        if score >= 90:
            _ok(f"Score de saúde: {score:.0f}/100")
        elif score >= 70:
            _warn(f"Score de saúde: {score:.0f}/100")
        else:
            _fail(f"Score de saúde: {score:.0f}/100")

        _info(f"Arquivos analisados: {health.total_files}")
        _info(f"Erros de sintaxe: {health.syntax_errors}")
        _info(f"Problemas de segurança: {health.security_issues}")
        _info(f"Problemas de performance: {health.performance_issues}")
        _info(f"Total de issues: {len(health.issues)}")

        if health.issues:
            print(f"\n  Top issues:")
            for issue in health.issues[:10]:
                severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
                icon = severity_icon.get(issue.severity, "⚪")
                fixable = " [auto-fix]" if issue.auto_fixable else ""
                print(f"    {icon} {issue.file}:{issue.line} — {issue.message}{fixable}")

        # Module health
        print(f"\n  Módulos core:")
        for mod, ok in health.modules_ok.items():
            icon = "✅" if ok else "❌"
            print(f"    {icon} {mod}")

    except Exception as e:
        _fail(f"Erro ao executar diagnóstico: {e}")


def diagnose_speech():
    """Test the speech engine components."""
    _header("Teste do Motor de Voz")

    # Test 1: edge-tts
    _info("Testando edge-tts...")
    try:
        import edge_tts
        import asyncio
        voices = asyncio.run(edge_tts.list_voices())
        _ok(f"edge-tts OK — {len(voices)} vozes disponíveis")
    except ImportError:
        _fail("edge-tts não instalado")
    except Exception as e:
        _fail(f"edge-tts erro: {e}")

    # Test 2: SpeechEngine imports
    _info("Testando imports do SpeechEngine...")
    try:
        from core.speech_engine import SpeechEngine, split_sentences, clean_for_speech
        _ok("SpeechEngine imports OK")

        # Test sentence splitting
        result = split_sentences("Olá. Tudo bem?")
        _ok(f"Split sentences: {len(result)} partes")

        # Test text cleaning
        cleaned = clean_for_speech("**bold** https://example.com test")
        _ok(f"Text cleaning OK: '{cleaned[:40]}...'")
    except Exception as e:
        _fail(f"SpeechEngine erro: {e}")

    # Test 3: MCI availability
    _info("Testando MCI (Windows audio)...")
    try:
        import ctypes
        result = ctypes.windll.winmm.mciSendStringW(
            'open "C:\\Windows\\Media\\chimes.wav" type mpegvideo alias _test_diag',
            None, 0, 0
        )
        if result == 0:
            ctypes.windll.winmm.mciSendStringW('close _test_diag', None, 0, 0)
            _ok("MCI disponível")
        else:
            _warn(f"MCI retornou código: {result}")
    except Exception as e:
        _fail(f"MCI erro: {e}")

    # Test 4: ffmpeg
    _info("Testando ffmpeg...")
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg):
            _ok(f"ffmpeg OK: {ffmpeg}")
        else:
            _fail(f"ffmpeg não encontrado: {ffmpeg}")
    except ImportError:
        _warn("imageio_ffmpeg não instalado (voice styling desabilitado)")
    except Exception as e:
        _fail(f"ffmpeg erro: {e}")

    # Test 5: voice_converter
    _info("Testando voice_converter...")
    try:
        from core.voice_converter import convert_voice
        _ok("voice_converter import OK")
    except ImportError:
        _warn("voice_converter não disponível (voice styling desabilitado)")
    except Exception as e:
        _fail(f"voice_converter erro: {e}")

    # Test 6: Full synthesis test
    _info("Teste completo de síntese (edge-tts → arquivo)...")
    try:
        import asyncio
        import tempfile

        async def _test_synth():
            communicate = edge_tts.Communicate(
                "Teste de síntese do Grande Sábio",
                "pt-BR-FranciscaNeural",
                rate="-4%", pitch="-2Hz",
            )
            tmp = Path(tempfile.gettempdir()) / "_gs_diag_test.mp3"
            await communicate.save(str(tmp))
            return tmp

        tmp_path = asyncio.run(_test_synth())
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            _ok(f"Síntese OK: {tmp_path.stat().st_size} bytes")
            tmp_path.unlink(missing_ok=True)
        else:
            _fail("Síntese produziu arquivo vazio")
    except Exception as e:
        _fail(f"Síntese erro: {e}")


def diagnose_llm():
    """Test LLM provider connectivity."""
    _header("Teste de Conectividade LLM")

    providers_tested = 0
    providers_ok = 0

    # Test Groq
    _info("Testando Groq...")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Responda apenas: OK"}],
                max_tokens=5,
                timeout=10,
            )
            if resp.choices:
                _ok(f"Groq OK — modelo: {resp.model}")
                providers_ok += 1
            else:
                _warn("Groq retornou resposta vazia")
        except Exception as e:
            _warn(f"Groq erro: {e}")
        providers_tested += 1
    else:
        _info("Groq: GROQ_API_KEY não configurada")

    # Test Gemini
    _info("Testando Gemini...")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content("Responda apenas: OK", generation_config=genai.GenerationConfig(max_output_tokens=5))
            if resp.text:
                _ok(f"Gemini OK — resposta: {resp.text.strip()[:20]}")
                providers_ok += 1
            else:
                _warn("Gemini retornou resposta vazia")
        except Exception as e:
            _warn(f"Gemini erro: {e}")
        providers_tested += 1
    else:
        _info("Gemini: GEMINI_API_KEY não configurada")

    # Test OpenRouter
    _info("Testando OpenRouter...")
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        try:
            import httpx
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {or_key}"},
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Responda apenas: OK"}],
                    "max_tokens": 5,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                _ok("OpenRouter OK")
                providers_ok += 1
            else:
                _warn(f"OpenRouter status: {resp.status_code}")
        except Exception as e:
            _warn(f"OpenRouter erro: {e}")
        providers_tested += 1
    else:
        _info("OpenRouter: OPENROUTER_API_KEY não configurada")

    # Test Ollama (local)
    _info("Testando Ollama (local)...")
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            _ok(f"Ollama OK — {len(models)} modelos: {[m['name'] for m in models[:3]]}")
            providers_ok += 1
        else:
            _info("Ollama: não disponível")
    except Exception:
        _info("Ollama: não disponível localmente")
    providers_tested += 1

    print(f"\n  Resumo: {providers_ok}/{providers_tested} providers disponíveis")
    if providers_ok == 0:
        _fail("Nenhum provider LLM disponível! Configure pelo menos uma API key no .env")
    elif providers_ok == 1:
        _warn("Apenas 1 provider disponível — fallback limitado")
    else:
        _ok(f"{providers_ok} providers disponíveis — fallback robusto")


def diagnose_intent():
    """Test the intent engine."""
    _header("Teste do Intent Engine")
    try:
        from core.intent_engine import IntentEngine

        test_cases = [
            ("liste processos", "list_processes"),
            ("informações do sistema", "system_info"),
            ("que horas são", "get_datetime"),
            ("limpe a lixeira", "clean_recycle_bin"),
            ("abra o notepad", "open_app"),
            ("qual é o sentido da vida?", None),
        ]

        passed = 0
        for text, expected in test_cases:
            action, params = IntentEngine.match_intent(text)
            if action == expected:
                _ok(f"'{text}' → {action}")
                passed += 1
            else:
                _fail(f"'{text}' → {action} (esperado: {expected})")

        print(f"\n  Resumo: {passed}/{len(test_cases)} intents corretos")

    except Exception as e:
        _fail(f"IntentEngine erro: {e}")


def diagnose_index():
    """Test the code index."""
    _header("Teste do Code Index")
    try:
        from modules.code_index import CodeIndex

        t0 = time.perf_counter()
        index = CodeIndex(PROJECT_ROOT, chunk_size=300, overlap=100, max_files=50)
        count = index.build()
        elapsed = time.perf_counter() - t0

        _ok(f"Index construído: {count} chunks em {elapsed:.2f}s")

        # Test query
        t0 = time.perf_counter()
        result = index.query("speech engine text to speech voice", k=5)
        elapsed = time.perf_counter() - t0
        _ok(f"Query executada em {elapsed:.3f}s, {len(result)} chars de resultado")

        if result:
            # Show first few lines
            lines = result.strip().split("\n")[:5]
            for line in lines:
                _info(f"  {line[:80]}")

    except Exception as e:
        _fail(f"Code Index erro: {e}")


def diagnose_fix():
    """Auto-fix safe issues."""
    _header("Auto-Fix de Issues Seguras")
    try:
        from core.autonomous_engine import run_diagnostics, auto_fix_issue

        health = run_diagnostics(PROJECT_ROOT)
        fixable = [i for i in health.issues if i.auto_fixable]

        if not fixable:
            _ok("Nenhuma issue auto-fixável encontrada!")
            return

        _info(f"{len(fixable)} issues auto-fixáveis encontradas")
        fixed = 0
        for issue in fixable:
            success, desc = auto_fix_issue(issue, dry_run=False)
            if success:
                _ok(f"Corrigido: {issue.file}:{issue.line} — {desc}")
                fixed += 1
            else:
                _fail(f"Falhou: {issue.file}:{issue.line} — {desc}")

        print(f"\n  Resumo: {fixed}/{len(fixable)} issues corrigidas")

    except Exception as e:
        _fail(f"Auto-fix erro: {e}")


# ===================================================================
# Main
# ===================================================================

COMMANDS = {
    "full": diagnose_full,
    "health": diagnose_health,
    "voice": diagnose_speech,
    "speech": diagnose_speech,
    "llm": diagnose_llm,
    "intent": diagnose_intent,
    "index": diagnose_index,
    "fix": diagnose_fix,
}


def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "full"

    if cmd in ("help", "-h", "--help"):
        print(__doc__)
        print("Comandos disponíveis:")
        for name, func in COMMANDS.items():
            doc = (func.__doc__ or "").strip().split("\n")[0]
            print(f"  {name:12s} — {doc}")
        return

    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Comando desconhecido: {cmd}")
        print("Use 'python scripts/diagnose.py help' para ver os comandos disponíveis.")
        sys.exit(1)


if __name__ == "__main__":
    main()
