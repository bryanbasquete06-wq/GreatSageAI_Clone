"""
Great Sage AI - Continuous Wake Word Detection Engine
Monitors background microphone audio using gapless InputStream for wake phrases ("Great Sage", "Grande Sábio", "Raphael", "Sábio").
"""

import os
import sys
import io
import time
import wave
import queue
import tempfile
import threading
import numpy as np
import sounddevice as sd
from groq import Groq
from GreatSageAI_Clone.core.mic_manager import get_best_input_device


class WakeWordDetector:
    WAKE_PHRASES = ["great sage", "grande sábio", "grande sabio", "raphael", "sábio", "sabio", "ei sábio", "ei sabio", "sage"]

    def __init__(self, on_wake_callback=None, sample_rate: int = 16000, groq_key: str | None = None):
        self.sample_rate = sample_rate
        self.on_wake_callback = on_wake_callback
        self.is_running = False
        self._thread = None
        self.speech_engine_ref = None
        self.audio_queue = queue.Queue()

        self.groq_key = groq_key or os.environ.get("GROQ_API_KEY", "")
        self.groq_client = None
        if self.groq_key:
            try:
                self.groq_client = Groq(api_key=self.groq_key)
            except Exception:
                pass

        self.ambient_rms = 40.0

    def set_speech_engine(self, speech_engine):
        self.speech_engine_ref = speech_engine

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_running:
            self.audio_queue.put(indata.copy())

    def _loop(self):
        best_device_id, best_sr = get_best_input_device()
        try:
            print(f"[WakeWord] InputStream no dispositivo ID {best_device_id} ({best_sr} Hz) iniciado.")
        except Exception:
            pass

        block_samples = int(best_sr * 0.2) # 200ms blocks

        try:
            stream = sd.InputStream(
                device=best_device_id,
                samplerate=best_sr,
                channels=1,
                dtype='int16',
                blocksize=block_samples,
                callback=self._audio_callback
            )
            stream.start()
        except Exception as e:
            print(f"[WakeWord Error] Failed to open InputStream: {e}")
            return

        buffer_frames = []
        silent_count = 0

        while self.is_running:
            try:
                # Pause wake-word listening while assistant is speaking TTS
                if self.speech_engine_ref and getattr(self.speech_engine_ref, "is_speaking", False):
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except queue.Empty:
                            break
                    buffer_frames.clear()
                    time.sleep(0.2)
                    continue

                try:
                    chunk = self.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                threshold = max(45.0, self.ambient_rms * 1.3 + 10.0)

                if rms > threshold:
                    buffer_frames.append(chunk)
                    silent_count = 0
                else:
                    if not buffer_frames:
                        self.ambient_rms = 0.9 * self.ambient_rms + 0.1 * rms
                    else:
                        silent_count += 1
                        buffer_frames.append(chunk)

                        # User stopped speaking after ~0.8s of silence or max 7s buffer
                        if silent_count >= 4 or len(buffer_frames) >= 35:
                            audio_data = np.concatenate(buffer_frames, axis=0)
                            buffer_frames.clear()
                            silent_count = 0

                            # Transcribe buffer
                            text = self._transcribe_chunk(audio_data)
                            if text:
                                text_lower = text.lower().strip()
                                try:
                                    print(f"[WakeWord Audio] Transcricao: '{text_lower}'")
                                except Exception:
                                    pass

                                # Check for Wake Word
                                found_wake = any(w in text_lower for w in self.WAKE_PHRASES)
                                if found_wake:
                                    try:
                                        print("[WakeWord] WAKE WORD DETECTADA! 'Great Sage' reconhecido com sucesso!")
                                    except Exception:
                                        pass

                                    # Extract command after wake word if present
                                    cmd_after = text_lower
                                    for w in self.WAKE_PHRASES:
                                        cmd_after = cmd_after.replace(w, "").strip()

                                    if self.on_wake_callback:
                                        self.on_wake_callback(cmd_after)

            except Exception as e:
                time.sleep(0.3)

        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

    def _transcribe_chunk(self, audio_data: np.ndarray) -> str | None:
        best_device_id, best_sr = get_best_input_device()
        try:
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(best_sr)
                wf.writeframes(audio_data.tobytes())
            wav_bytes = wav_io.getvalue()

            if self.groq_client:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(wav_bytes)
                    tmp_path = tmp.name

                with open(tmp_path, "rb") as audio_file:
                    transcription = self.groq_client.audio.transcriptions.create(
                        file=(os.path.basename(tmp_path), audio_file.read()),
                        model="whisper-large-v3-turbo",
                        language="pt",
                        response_format="text"
                    )

                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

                text_res = str(transcription).strip()
                if text_res and "Thank you" not in text_res and "Obrigado" not in text_res:
                    return text_res
        except Exception:
            pass
        return None
