"""
Great Sage AI - Sounddevice Microphone & Groq Whisper STT Engine
Captures voice from system microphone using sounddevice (no PyAudio required) and transcribes via Groq Whisper V3 Turbo.
"""

import os
import sys
import io
import time
import tempfile
import wave
import numpy as np
import sounddevice as sd
from pathlib import Path
from groq import Groq


def get_best_input_device() -> tuple[int | None, int]:
    """Retorna o melhor microfone com perfeição — prioriza WASAPI/MME com fallback inteligente."""
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        default_in = sd.default.device[0]
        # 1) Tenta o default do Windows primeiro (geralmente o melhor e calibrado)
        if default_in is not None and default_in >= 0:
            try:
                d = devices[int(default_in)]
                if d.get('max_input_channels', 0) > 0:
                    sr = int(d.get('default_samplerate') or 44100)
                    # Evita DroidCam virtual que rouba default mas é péssimo para voz
                    if "droidcam" not in d['name'].lower():
                        return int(default_in), sr
            except Exception:
                pass

        # 2) Scoreia todos os inputs: prefere WASAPI > DirectSound > MME, evita WDM-KS cru
        scored = []
        for i, d in enumerate(devices):
            if d.get('max_input_channels', 0) <= 0:
                continue
            name_lower = d['name'].lower()
            if "droidcam" in name_lower:
                continue
            # score por hostapi
            ha_idx = d.get('hostapi', 0)
            try:
                ha_name = hostapis[ha_idx]['name'].lower() if ha_idx < len(hostapis) else ""
            except Exception:
                ha_name = ""
            score = 0
            if "wasapi" in ha_name:
                score += 30
            elif "directsound" in ha_name:
                score += 20
            elif "mme" in ha_name:
                score += 10
            if "wdm-ks" in name_lower:
                score -= 50  # WDM-KS cru tem latência e ruído, só último fallback
            # microfones reais têm nomes com "microphone", "array", "headset"
            if any(k in name_lower for k in ("microphone", "array", "headset", "mic")):
                score += 5
            sr = int(d.get('default_samplerate') or 44100)
            scored.append((score, i, sr, d['name']))

        if scored:
            scored.sort(reverse=True)  # maior score primeiro
            _, best_id, best_sr, best_name = scored[0]
            # log para debug
            try:
                print(f"[MicManager] Melhor microfone: ID {best_id} '{best_name}' ({best_sr}Hz) score={scored[0][0]}")
            except Exception:
                pass
            return best_id, best_sr

        # 3) Último fallback: qualquer input que existir
        for i, d in enumerate(devices):
            if d.get('max_input_channels', 0) > 0:
                sr = int(d.get('default_samplerate') or 44100)
                return i, sr
    except Exception as e:
        try:
            print(f"[MicManager] Erro ao escolher microfone: {e}")
        except Exception:
            pass
    return None, 44100


class MicrophoneManager:
    def __init__(self, groq_key: str | None = None, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.groq_key = groq_key
        if not self.groq_key:
            try:
                from dotenv import load_dotenv
                _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
                load_dotenv(_env_path)
                self.groq_key = os.environ.get("GROQ_API_KEY", "")
            except Exception:
                self.groq_key = os.environ.get("GROQ_API_KEY", "")
        self.groq_client = None
        if self.groq_key:
            try:
                self.groq_client = Groq(api_key=self.groq_key)
            except Exception:
                pass

        self.is_recording = False

    @staticmethod
    def list_microphones() -> list[str]:
        """Returns list of available system microphones via sounddevice."""
        try:
            devices = sd.query_devices()
            input_devs = [f"{i}: {d['name']}" for i, d in enumerate(devices) if d.get('max_input_channels', 0) > 0]
            return input_devs if input_devs else ["0: Microfone Padrão"]
        except Exception:
            return ["0: Microfone Padrão"]

    def record_audio_wav(self, duration_sec: float = 5.0, device_index: int | None = None) -> bytes:
        """Records raw WAV audio bytes using sounddevice."""
        num_frames = int(duration_sec * self.sample_rate)

        recording = sd.rec(
            num_frames,
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16',
            device=device_index
        )
        sd.wait()

        # Write to WAV buffer
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())

        wav_io.seek(0)
        return wav_io.read()

    def record_and_transcribe(self, device_index: int | None = None, timeout: int = 6) -> str | None:
        """Captures voice from microphone and transcribes via Groq Whisper V3 Turbo."""
        try:
            self.is_recording = True
            print("[MicManager] Escutando via SoundDevice...")
            wav_bytes = self.record_audio_wav(duration_sec=timeout, device_index=device_index)

            # Transcribe via Groq Whisper V3 Turbo API
            if self.groq_client:
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(wav_bytes)
                        tmp_path = tmp.name

                    try:
                        with open(tmp_path, "rb") as audio_file:
                            transcription = self.groq_client.audio.transcriptions.create(
                                file=(os.path.basename(tmp_path), audio_file.read()),
                                model="whisper-large-v3-turbo",
                                language="pt",
                                response_format="text"
                            )
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

                    text_res = str(transcription).strip()
                    if text_res and len(text_res) > 1 and "Thank you" not in text_res and "Obrigado" not in text_res:
                        print(f"[MicManager] Transcrição Groq Whisper: '{text_res}'")
                        return text_res
                except Exception as e:
                    print(f"[MicManager] Groq Whisper error: {e}")

            return None

        except Exception as e:
            print(f"[MicManager] Erro no microfone: {e}")
            return None
        finally:
            self.is_recording = False

