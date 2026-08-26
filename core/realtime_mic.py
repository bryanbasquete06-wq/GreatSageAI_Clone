"""
Great Sage AI - Continuous Audio Stream Mic Listener (Gapless Queue Architecture)
Streams live audio via sounddevice.InputStream with adaptive dynamic noise thresholding and Groq Whisper STT.
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


def resample_pcm(audio_data: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
    """Resamples PCM audio array to target sample rate using linear interpolation."""
    if orig_sr == target_sr:
        return audio_data
    num_target_samples = int(len(audio_data) * target_sr / orig_sr)
    old_indices = np.linspace(0, len(audio_data) - 1, num_target_samples)
    resampled = np.interp(old_indices, np.arange(len(audio_data)), audio_data.astype(np.float32))
    return resampled.astype(np.int16)


class RealtimeMicListener:
    def __init__(self, sample_rate: int = 16000, groq_key: str | None = None):
        self.sample_rate = sample_rate
        self.is_listening = False
        self.speech_callback = None
        self.audio_rms_callback = None
        self._thread = None
        self.audio_queue = queue.Queue()

        self.groq_key = groq_key or os.environ.get("GROQ_API_KEY", "")
        self.groq_client = None
        if self.groq_key:
            try:
                self.groq_client = Groq(api_key=self.groq_key)
            except Exception:
                pass

        # Dynamic Ambient Noise Calibration
        self.ambient_rms = 40.0
        self.speech_engine_ref = None

    def set_speech_engine(self, speech_engine):
        self.speech_engine_ref = speech_engine

    def start_listening(self, callback):
        """Starts gapless real-time stream listener."""
        if self.is_listening:
            return

        self.speech_callback = callback
        self.is_listening = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop_listening(self):
        self.is_listening = False

    def _audio_stream_callback(self, indata, frames, time_info, status):
        """Callback invoked by sounddevice InputStream for every audio chunk."""
        if self.is_listening:
            self.audio_queue.put(indata.copy())
            if self.audio_rms_callback:
                try:
                    rms = float(np.sqrt(np.mean(indata.astype(np.float32)**2)))
                    self.audio_rms_callback(rms)
                except Exception:
                    pass

    def _worker_loop(self):
        best_device_id, best_sr = get_best_input_device()
        try:
            print(f"[RealtimeMic] InputStream no dispositivo ID {best_device_id} ({best_sr} Hz) iniciado com sucesso.")
        except Exception:
            pass
        block_samples = int(best_sr * 0.2) # 200ms blocks

        # Start non-blocking gapless InputStream
        try:
            stream = sd.InputStream(
                device=best_device_id,
                samplerate=best_sr,
                channels=1,
                dtype='int16',
                blocksize=block_samples,
                callback=self._audio_stream_callback
            )
            stream.start()
        except Exception as e:
            print(f"[RealtimeMic Error] Failed to open InputStream: {e}")
            return

        recording_frames = []
        is_speaking_phrase = False
        silent_blocks = 0
        max_silent_blocks = 4  # ~0.8s silence ends phrase
        max_total_blocks = 40  # ~8s max phrase duration

        while self.is_listening:
            try:
                # If assistant is currently speaking TTS, clear queue and pause capture
                if self.speech_engine_ref and getattr(self.speech_engine_ref, "is_speaking", False):
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except queue.Empty:
                            break
                    recording_frames.clear()
                    is_speaking_phrase = False
                    time.sleep(0.2)
                    continue

                try:
                    chunk = self.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))

                # Calculate dynamic threshold: highly sensitive adaptive thresholding
                speech_threshold = max(45.0, self.ambient_rms * 1.3 + 10.0)

                if rms > speech_threshold:
                    if not is_speaking_phrase:
                        try:
                            print(f"[RealtimeMic] FALA DETECTADA! (RMS: {rms:.1f} > Thresh: {speech_threshold:.1f}) Gravando...")
                        except Exception:
                            pass
                        is_speaking_phrase = True
                        recording_frames.clear()

                    recording_frames.append(chunk)
                    silent_blocks = 0
                else:
                    # Update ambient noise baseline when user is not speaking
                    if not is_speaking_phrase:
                        self.ambient_rms = 0.9 * self.ambient_rms + 0.1 * rms
                    else:
                        recording_frames.append(chunk)
                        silent_blocks += 1

                        if silent_blocks >= max_silent_blocks or len(recording_frames) >= max_total_blocks:
                            # User finished speaking phrase! Process audio
                            audio_data = np.concatenate(recording_frames, axis=0)
                            recording_frames.clear()
                            is_speaking_phrase = False
                            silent_blocks = 0

                            # Resample to 16000 Hz for 100% Whisper accuracy
                            audio_16k = resample_pcm(audio_data.flatten(), best_sr, 16000)

                            # Convert to 16-bit 16kHz WAV bytes
                            wav_io = io.BytesIO()
                            with wave.open(wav_io, 'wb') as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(16000)
                                wf.writeframes(audio_16k.tobytes())
                            wav_bytes = wav_io.getvalue()

                            text_res = None
                            # 1. Try Groq Whisper V3 Turbo
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

                                    txt = str(transcription).strip()
                                    if txt and len(txt) > 1 and "Thank you" not in txt and "Obrigado" not in txt:
                                        text_res = txt
                                except Exception as e:
                                    print(f"[RealtimeMic] Groq Whisper STT Error: {e}")

                            # 2. Fallback to Google STT if Groq failed
                            if not text_res:
                                try:
                                    import speech_recognition as sr
                                    recog = sr.Recognizer()
                                    with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                                        audio_data = recog.record(source)
                                        text_res = recog.recognize_google(audio_data, language="pt-BR")
                                except Exception as e:
                                    print(f"[RealtimeMic] Google STT Fallback Error: {e}")

                            if text_res and len(text_res) > 1:
                                try:
                                    print(f"[RealtimeMic] Transcricao Ao Vivo: '{text_res}'")
                                except Exception:
                                    pass
                                if self.speech_callback:
                                    self.speech_callback(text_res)

            except Exception as e:
                time.sleep(0.3)

        try:
            stream.stop()
            stream.close()
        except Exception:
            pass


