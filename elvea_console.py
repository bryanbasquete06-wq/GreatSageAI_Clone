"""
Elívea — Console Terminal & Escuta ao Vivo (v3 Elivea)
================================================================
Versão headless (sem janela) com o pipeline de voz unificado:
microfone → VAD → Whisper V3 Turbo → comando → resposta falada.

Uso: python elvea_console.py
"""

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elvea_app import EliveaApp


C_Y = "\033[93m"
C_C = "\033[96m"
C_G = "\033[92m"
C_R = "\033[91m"
C_W = "\033[97m"
C_0 = "\033[0m"


def main():
    os.system("") # ANSI no CMD

    print(f"{C_Y}{'=' * 70}")
    print(" ＜Elivea＞ Elívea — CONSOLE v3")
    print(" Pipeline de voz unificado • Whisper V3 Turbo • TTS neural streaming")
    print(f"{'=' * 70}{C_0}\n")

    print(f"{C_C}[SYS] Inicializando motores de voz, inteligência e automação...{C_0}")
    app = EliveaApp()
    pipeline = app.pipeline

    # Streaming de resposta impresso ao vivo no terminal
    sig = app.signals
    sig.sig_sage_begin.connect(lambda: print(f"{C_C}[SÁBIO {C_0}", end="", flush=True))
    sig.sig_sage_delta.connect(lambda d: print(d, end="", flush=True))
    sig.sig_sage_end.connect(lambda: print(f"{C_C}]{C_0}\n", flush=True))
    sig.sig_sage_full.connect(lambda t: print(f"{C_G}[SÁBIO] {t}{C_0}\n", flush=True))

    print(f"{C_G}[SYS] Microfone contínuo ONLINE — fale 'Elívea' ou qualquer comando.{C_0}\n")

    def _on_speech(text: str, source: str):
        print(f"\n{C_Y}[FALA CAPTURADA ({source})]:{C_0} \"{C_W}{text}{C_0}\"")
        print(f"{C_C}[SÁBIO] Processando…{C_0}")
        t0 = time.perf_counter()
        try:
            app.handle_command(text)
        except Exception as e:
            print(f"{C_R}[erro] {e}{C_0}")
        print(f"{C_G}[ respondido em {time.perf_counter() - t0:.1f}s — STT {pipeline.last_stt_ms}ms/{pipeline.last_stt_engine} | TTFT {app.llm.last_ttft_ms}ms]{C_0}")

    pipeline.on_transcript = _on_speech
    pipeline.on_wake = lambda: print(f"{C_Y}［Elivea ativado — à escuta, Mestre］{C_0}")

    print(f"{C_Y}Digite comandos abaixo ('sair' encerra).{C_0}\n")
    while True:
        try:
            user_input = input(f"{C_Y}{app.persona.user_name} > {C_0}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("sair", "exit", "quit"):
                print(f"{C_R}Encerrando o Elívea...{C_0}")
                pipeline.stop()
                app.speech.stop_speaking()
                sys.exit(0)

            print(f"{C_C}[SÁBIO] Executando...{C_0}")
            app.handle_command(user_input)
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_R}Encerrando...{C_0}")
            pipeline.stop()
            app.speech.stop_speaking()
            break


if __name__ == "__main__":
    main()
