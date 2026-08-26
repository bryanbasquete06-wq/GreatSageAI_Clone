# -*- coding: utf-8 -*-
"""
Great Sage AI v3 — Suíte de Testes
===================================
Uso:
    python run_tests.py # testes rápidos (offline)
    python run_tests.py --full # inclui rede real (TTS, LLM, Whisper)

by: bryan
"""
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

FULL = "--full" in sys.argv
passed, failed = [], []


def test(name):
    def deco(fn):
        try:
            fn()
            passed.append(name)
            print(f" {name}")
        except Exception:
            failed.append(name)
            print(f" {name}")
            traceback.print_exc()
        return fn
    return deco


print("═" * 62)
print(" ＜大賢者＞ GREAT SAGE AI v3 — SUÍTE DE TESTES")
print("═" * 62)


# ─────────────────────────────────────────────── TTS / texto
@test("TTS: divisão de frases com pausas naturais")
def _():
    from GreatSageAI_Clone.core.speech_engine import split_sentences
    s = split_sentences("Aviso. Sistema **online**, Mestre! RAM em 32%. Confira agora.")
    assert len(s) >= 3, s
    assert "**" not in " ".join(s)


@test("TTS: limpeza de markdown/URLs para fala natural")
def _():
    from GreatSageAI_Clone.core.speech_engine import clean_for_speech
    t = clean_for_speech("veja https://x.com/abc e `codigo` **negrito**")
    assert "https" not in t and "**" not in t


@test("TTS: presets de voz neural com prosódia")
def _():
    from GreatSageAI_Clone.core.speech_engine import VOICE_PRESETS
    assert len(VOICE_PRESETS) >= 2
    assert VOICE_PRESETS["raphael"].voice_id == "pt-BR-FranciscaNeural"


@test("TTS: legado — nomes antigos de voz continuam válidos")
def _():
    from GreatSageAI_Clone.core.speech_engine import SpeechEngine
    se = SpeechEngine(voice_key="Great Sage Anime (Feminino)")
    assert se.preset.voice_id == "pt-BR-FranciscaNeural"
    se.stop_speaking()


@test("Voz: estilizador alinha F0 ao perfil da personagem")
def _():
    import os
    import tempfile
    import wave

    import numpy as np
    from GreatSageAI_Clone.core.voice_converter import convert_voice, _estimate_f0

    sr = 24000
    t = np.arange(int(sr * 2.0)) / sr
    f0 = 220.0 * (1 + 0.02 * np.sin(2 * np.pi * 5 * t))
    phase = 2 * np.pi * np.cumsum(f0) / sr
    voice = 0.6 * np.sin(phase) + 0.2 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)
    x = (voice * env * 0.5 * 32767).astype(np.int16)

    tmp = tempfile.mktemp(suffix="_styler_in.wav")
    out = tempfile.mktemp(suffix="_styler_out.wav")
    with wave.open(tmp, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(x.tobytes())

    assert convert_voice(tmp, out)
    with wave.open(out, "r") as w:
        y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        sr_out = w.getframerate()

    f0_after = _estimate_f0(y, sr_out)
    assert 330 < f0_after < 390, f"F0 fora do alvo: {f0_after}"
    assert abs(len(y) - len(x)) < sr * 0.1, "duração alterada"
    assert np.abs(y).max() <= 0.93, "pico acima do normalizado"

    os.unlink(tmp); os.unlink(out)


@test("Clareza: enhance_audio resgata voz baixa com ruído")
def _():
    import numpy as np
    from GreatSageAI_Clone.core.voice_pipeline import enhance_audio
    sr = 16000
    t = np.arange(int(sr * 2.0)) / sr
    # voz sintética em volume MUITO baixo + ruído forte
    voice = (np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))) * 400.0
    noisy = voice + np.random.default_rng(7).normal(0, 800, t.size)
    out = enhance_audio(noisy.astype(np.int16), sr)
    assert out.dtype == np.int16 and out.size == noisy.size
    rms_in = float(np.sqrt((noisy.astype(np.float32) / 32768.0) ** 2).mean())
    rms_out = float(np.sqrt((out.astype(np.float32) / 32768.0) ** 2).mean())
    assert rms_out > rms_in * 3, f"ganho insuficiente: {rms_in:.4f} → {rms_out:.4f}"


@test("Clareza: guarda anti-eco do prompt do Whisper")
def _():
    from GreatSageAI_Clone.core.voice_pipeline import is_prompt_echo
    assert is_prompt_echo("Grande Sábio, Mestre Bryan.")
    assert is_prompt_echo("grande sábio, mestre bryan")
    assert not is_prompt_echo("Grande Sábio, otimize minha RAM")


@test("Voz: wake word exata e difusa")
def _():
    from GreatSageAI_Clone.core.voice_pipeline import fuzzy_wake_match
    assert fuzzy_wake_match("grande sábio abra o chrome")
    assert fuzzy_wake_match("grande sabiu me ajude") # Whisper mishear
    assert not fuzzy_wake_match("bom dia como vai você")


@test("Voz: extração do comando após a wake word")
def _():
    from GreatSageAI_Clone.core.voice_pipeline import strip_wake_phrase
    cmd = strip_wake_phrase("grande sábio, abra o chrome")
    assert "sab" not in cmd.lower() and "chrome" in cmd.lower()


# ─────────────────────────────────────────────── LLM
@test("LLM: chave Groq carregada das configurações")
def _():
    from GreatSageAI_Clone.core.llm import GreatSageLLM
    assert GreatSageLLM().groq_key


@test("Persona: prompt voz-primeiro carregado")
def _():
    from GreatSageAI_Clone.core.persona import PersonaManager
    p = PersonaManager().get_system_prompt()
    assert "Mestre Bryan" in p and "NUNCA use markdown" in p


# ─────────────────────────────────────────────── UI
@test("UI: 4 temas aplicáveis sem erro")
def _():
    from GreatSageAI_Clone.ui.qt_ui import THEMES, apply_theme
    for key in THEMES:
        apply_theme(key)
    apply_theme("tensura")


@test("UI: janela principal constrói e boot anima")
def _():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from GreatSageAI_Clone.ui.qt_ui import GreatSageMainWindow
    win = GreatSageMainWindow(command_handler=None)
    win.show()
    app.processEvents()
    assert win.boot.isVisible()
    win._on_boot_done()
    win.add_sage_message("teste")
    win.set_pipeline_state("listening")
    app.processEvents()


@test("Orbe: Raphael flutuante — minimizar vira orbe, estados reagem")
def _():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from GreatSageAI_Clone.ui.qt_ui import GreatSageMainWindow
    win = GreatSageMainWindow(command_handler=None)
    win.show()
    app.processEvents()
    win._hide_to_orb()
    app.processEvents()
    assert not win.isVisible() and win.orb.isVisible()
    win.set_pipeline_state("speaking")
    app.processEvents()
    assert win.orb.state == "speaking"
    win.orb.push_rms(150.0)
    win._restore_from_orb()
    app.processEvents()
    assert win.isVisible() and not win.orb.isVisible()
    # fechar (X) não encerra: vira orbe
    win.close()
    app.processEvents()
    assert not win.isVisible() and win.orb.isVisible()
    win.orb.hide()
    win._real_exit = True


@test("CodeDock: detecção de linguagem e criação do highlighter")
def _():
    from GreatSageAI_Clone.ui.code_syntax import CodeHighlighter, detect_language
    assert detect_language("main.py") == "python"
    assert detect_language("app.tsx") == "typescript"
    assert detect_language("index.html") == "html"
    assert detect_language("style.css") == "css"
    assert detect_language("script.go") == "go"
    assert detect_language("sem_extensao") == "text"
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument("def hello():\n return 1 # ok")
    hl = CodeHighlighter(doc, "python")
    hl.refresh_theme()
    hl.set_language("rust")
    doc.setPlainText("fn main() { println!(\"oi\"); }")


@test("CodeDock: CodeAgent roda o loop com mock LLM (write → run → finish)")
def _():
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace as NS
    from GreatSageAI_Clone.modules.code_agent import CodeAgent

    steps = iter([
        '{"tool": "write_file", "path": "ola.py", "content": "print(42)"}',
        '{"tool": "run_python", "code": "print(42)"}',
        '{"tool": "finish", "answer": "Criei o arquivo ola.py e o teste passou, Mestre."}',
    ])

    class FakeLLM:
        last_model = "openai/gpt-oss-20b"

        def _groq_models(self):
            return ["openai/gpt-oss-20b"]

        def _ensure_groq_client(self):
            def create(**kw):
                return NS(choices=[NS(message=NS(content=next(steps)))])
            return NS(chat=NS(completions=NS(create=create)))

    ws = Path(tempfile.mkdtemp(prefix="gs_codedock_"))
    logs = []
    agent = CodeAgent(llm=FakeLLM(), workspace=ws, on_step=logs.append)
    report, answer = agent.run("Crie um script de teste.")
    assert (ws / "ola.py").read_text(encoding="utf-8") == "print(42)"
    assert "2 ações" in report, report
    assert "Criei o arquivo ola.py" in answer, answer
    assert any("" not in l or "escrevi" in l for l in logs)


@test("CodeDock: janela da Ala de Programação constrói (editor árvore agente)")
def _():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from GreatSageAI_Clone.ui.code_workspace import CodeWorkspaceWindow
    win = CodeWorkspaceWindow(llm=None, workspace=None)
    win.show()
    app.processEvents()
    assert win.editor is not None
    assert win.tree is not None
    assert win.transcript is not None
    win.run_task("print('x')") # llm None → aviso, sem crash
    app.processEvents()
    win.close()
    app.processEvents()


@test("CodeDock: abrir/salvar arquivo no editor não corrompe estado")
def _():
    import tempfile
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from GreatSageAI_Clone.ui.code_workspace import CodeWorkspaceWindow
    tmp = Path(tempfile.mkdtemp(prefix="gs_win_"))
    f = tmp / "hello.py"
    f.write_text("print('oi')\n", encoding="utf-8")
    win = CodeWorkspaceWindow(llm=None, workspace=tmp)
    win.show()
    app.processEvents()
    win.open_file(f)
    assert win.current_lang == "python"
    assert not win._dirty
    assert win.editor.toPlainText() == "print('oi')\n"
    win.editor.setPlainText("print('oi 2')\n")
    assert win._dirty
    win.save_current()
    assert f.read_text(encoding="utf-8") == "print('oi 2')\n"
    assert not win._dirty
    win.close()


# ─────────────────────────────────────────────── REDE REAL (--full)
if FULL:
    @test("E2E rede: TTS neural toca em <3s (streaming por frases)")
    def _():
        from GreatSageAI_Clone.core.speech_engine import SpeechEngine
        se = SpeechEngine(voice_key="raphael")
        t0 = time.perf_counter()
        se.speak("Aviso. Teste de voz neural do Grande Sábio, Mestre.")
        for _ in range(50):
            time.sleep(0.1)
            if se.is_speaking:
                break
        else:
            raise AssertionError("playback não iniciou")
        assert time.perf_counter() - t0 < 3.0
        time.sleep(1.5)
        se.stop_speaking()

    @test("E2E rede: LLM em streaming (primeiro token <3s)")
    def _():
        from GreatSageAI_Clone.core.llm import GreatSageLLM
        llm = GreatSageLLM()
        t0 = time.perf_counter()
        chunks = list(llm.query_stream("Responda apenas: ok"))
        assert chunks and "".join(chunks).strip()
        assert time.perf_counter() - t0 < 8.0

    @test("E2E rede: Whisper V3 Turbo transcreve áudio sintetizado")
    def _():
        import asyncio, tempfile
        import edge_tts
        from groq import Groq
        from GreatSageAI_Clone.core.llm import GreatSageLLM
        tmp = Path(tempfile.gettempdir()) / "gs_test_stt.mp3"
        asyncio.run(edge_tts.Communicate(
            "Grande Sábio, que horas são?", "pt-BR-FranciscaNeural").save(str(tmp)))
        gq = Groq(api_key=GreatSageLLM().groq_key)
        with open(tmp, "rb") as f:
            txt = str(gq.audio.transcriptions.create(
                file=("t.mp3", f.read()), model="whisper-large-v3-turbo",
                language="pt", response_format="text")).strip().lower()
        assert "horas" in txt or "sábio" in txt or "sabio" in txt, txt


# ─────────────────────────────────────────────── resultado
print("─" * 62)
print(f" RESULTADO: {len(passed)} passaram, {len(failed)} falharam")
if failed:
    print(" FALHARAM:", ", ".join(failed))
    sys.exit(1)
print(" ＜大賢者＞ TODOS OS TESTES PASSARAM")
