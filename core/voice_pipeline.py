"""
Elívea — Unified Voice Pipeline (single audio stream)
=============================================================
Replaces the old duplicated wake-word + realtime-mic double-stream design
(which captured and transcribed every utterance TWICE) with a single
InputStream driven by a state machine:

    ┌─ ALWAYS_ON mode: every finalized utterance → on_transcript
    └─ WAKE mode:      utterance matches wake phrase → armed window → command

Features
    • Adaptive ambient-noise VAD with dynamic speech threshold
    • 400 ms pre-roll ring buffer (never clips the first word)
    • Endpointing: 0.7 s of silence finalizes the phrase (fast turn-taking)
    • Groq Whisper large-v3-turbo STT with Google Speech fallback
    • Fuzzy wake-word matching (survives Whisper accent mishaps)
    • Half-duplex safety: mic paused while the Sage is speaking
    • Push-to-talk single-shot capture for the UI mic button
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import threading
import time
import unicodedata
import wave
import queue

import numpy as np
import sounddevice as sd

try:
    from core.mic_manager import get_best_input_device
except ImportError:
    try:
        from core.mic_manager import get_best_input_device
    except ImportError:
        from mic_manager import get_best_input_device


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TARGET_SR = 16000
BLOCK_SEC = 0.2                      # 200 ms analysis blocks
SILENCE_BLOCKS_END = 2               # 0.4 s silence → utterance done (rápido)
MAX_UTTERANCE_BLOCKS = 75            # 15 s max phrase
PREROLL_BLOCKS = 3                   # 600 ms kept before speech onset
MIN_UTTERANCE_SEC = 0.36             # ignore micro blips
WAKE_ARMED_WINDOW = 12.0             # seconds after wake word to accept command

# Vocabulary bias passed to Whisper — keeps domain names spelled right
def _get_stt_context() -> str:
    """Gera o contexto STT com o nome do usuário configurado."""
    try:
        from core.persona import _load_user_name
        name = _load_user_name()
    except Exception:
        name = "Mestre"
    return (f"Elivea, {name}. "
            "Python, GitHub, Groq, GPT, WhatsApp, YouTube, Google, "
            "Steam, Discord, Chrome, Firefox, Notepad, VS Code, Blender.")


STT_CONTEXT_PROMPT = _get_stt_context()

# Whisper normalmente "repete" só o começo do prompt quando não ouviu nada
_ECHO_HEAD = STT_CONTEXT_PROMPT.split(".")[0] + "."


def is_prompt_echo(txt: str) -> bool:
    """True when Whisper 'heard' nothing and just parroted the context prompt."""
    def _n(s: str) -> str:
        return s.rstrip(".!? ").strip().lower()
    return _n(txt) == _n(STT_CONTEXT_PROMPT) or _n(txt) == _n(_ECHO_HEAD)


def enhance_audio(audio: np.ndarray, sr: int) -> np.ndarray:
    """Clarity pass so Whisper receives loud, clean speech:

      1. DC-offset removal
      2. FFT band-pass 70 Hz – 7.5 kHz (kills rumble, mains hum and hiss)
      3. Soft per-frame noise gate from the quietest 15% of frames —
         gentle on purpose: aggressive spectral subtraction creates
         artifacts that hurt Whisper MORE than the original noise
      4. Peak normalization (+ gain cap) and RMS loudness matching —
         this is the big win: quiet talkers get rescued to full clarity

    Validated: rescues speech at ~0 dB SNR where raw audio mistranscribes.
    """
    a = audio.astype(np.float32)
    if a.size < sr // 4:
        return audio

    # 1) DC offset
    a -= float(a.mean())

    # 2) band-pass via FFT
    spec = np.fft.rfft(a)
    freqs = np.fft.rfftfreq(a.size, 1.0 / sr)
    spec[freqs < 70] *= 0.02
    spec[freqs > 7500] *= 0.25
    a = np.fft.irfft(spec, a.size).astype(np.float32)

    # 3) soft per-frame noise gate (pad trimmed after processing)
    frame = max(1, int(sr * 0.02))                 # 20 ms frames
    pad = (-a.size) % frame
    padded = np.concatenate([a, np.zeros(pad, dtype=np.float32)])
    frames = padded.reshape(-1, frame)
    frms = np.sqrt((frames ** 2).mean(axis=1))
    noise = float(np.percentile(frms, 15)) if frms.size >= 4 else 0.0
    if noise > 1e-6:
        mask = np.clip((frms / (noise * 2.0)) ** 1.4, 0.15, 1.0)
        frames *= mask[:, None]
    a = frames.reshape(-1)[: a.size]               # exact original length

    # 4) normalize loudness (peak → 0.89, RMS → 0.18, capped gains)
    peak = float(np.abs(a).max())
    if peak > 1e-6:
        a *= min(0.89 / peak, 14.0)
    rms = float(np.sqrt((a ** 2).mean()))
    if rms > 1e-6:
        a *= min(0.18 / rms, 6.0)

    return (np.clip(a, -1.0, 1.0) * 32767.0).astype(np.int16)

WAKE_PHRASES = [
    "elívea", "elvea", "great sage", "grande sabio", "grande sage", "grande sape",
    "oi sabio", "ei sabio", "sabio", "raphael", "rafael", "acorde",
]


def _normalize(text: str) -> str:
    txt = unicodedata.normalize("NFD", text.lower())
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", txt).strip()


def fuzzy_wake_match(text: str) -> str | None:
    """Returns the matched wake phrase if the text contains one (fuzzy)."""
    from difflib import SequenceMatcher

    norm = _normalize(text)
    if not norm:
        return None
    for phrase in WAKE_PHRASES:
        if phrase in norm:
            return phrase
    # token-window fuzzy compare for Whisper mishears
    tokens = norm.split()
    for phrase in ("great sage", "grande sabio", "raphael"):
        n = len(phrase.split())
        for i in range(max(1, len(tokens) - n + 1)):
            window = " ".join(tokens[i:i + n])
            if not window:
                continue
            if SequenceMatcher(None, window, phrase).ratio() >= 0.80:
                return phrase
    return None


def strip_wake_phrase(text: str, leading_only: bool = False) -> str:
    """Removes the wake phrase (and leading connectors) from a command.

    leading_only=True remove apenas no INÍCIO da frase — usado nos modos de
    escuta para que menções no meio da frase a "sábio"/"Elívea" (ex.: "quem
    foi o sábio Confúcio?") cheguem inteiras ao LLM.
    """
    if leading_only:
        for phrase in sorted(WAKE_PHRASES, key=len, reverse=True):
            pat = (r"^\s*(?:ei|oi|olá|ola|hey|psiu)?\s*[,.!]?\s*"
                   + r"\s+".join(map(re.escape, phrase.split())) + r"\b[,.!]?\s*")
            cleaned = re.sub(pat, "", text, count=1, flags=re.IGNORECASE)
            if cleaned != text:
                text = cleaned
                break
        text = re.sub(r"^(?:por favor|pode|poderia|me|para mim)\s+", "", text.strip(), flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", text).strip(" ,.!?–—:;").strip()

    norm = _normalize(text)
    for phrase in sorted(WAKE_PHRASES, key=len, reverse=True):
        # compare on normalized text but cut from original via regex
        pat = r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b"
        cleaned = re.sub(pat, " ", text, flags=re.IGNORECASE)
        if cleaned != text:
            text = cleaned
            norm = _normalize(text)
    text = re.sub(r"^(?:por favor|pode|poderia|me|para mim)\s+", "", text.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip(" ,.!?–—:;").strip()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class VoicePipeline:
    """Single-stream voice capture + VAD + STT with mode switching."""

    def __init__(self, groq_key: str | None = None, stt_language: str = "pt"):
        self.groq_key = groq_key
        if not self.groq_key:
            try:
                from dotenv import load_dotenv
                _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
                load_dotenv(_env_path)
                self.groq_key = os.environ.get("GROQ_API_KEY")
            except Exception:
                pass
        self.stt_language = stt_language

        self.groq_client = None
        if self.groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_key)
            except Exception:
                pass

        # Public callbacks
        self.on_transcript = None      # (text, source)  source: "voice"|"push"
        self.on_wake = None            # () — wake word recognized
        self.on_state_changed = None   # (state_str) idle|listening|thinking|speaking
        self.rms_callback = None       # (rms_float)

        # Modes
        self.mode = "always_on"        # "always_on" | "wake"
        self.enabled = True
        self._armed_until = 0.0        # wake-gated armed window

        # Internal
        self._state = "idle"
        self._thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None
        self._audio_q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._ambient = 45.0
        self._speech_engine_ref = None
        self._lock = threading.Lock()
        self._force_capture_until = 0.0
        self._post_speech_cooldown_until = 0.0  # suppress mic after TTS finishes

        # Stats for UI
        self.last_stt_engine = "—"
        self.last_stt_ms = 0

    # ------------------------------------------------------------------ setup

    def set_speech_engine(self, engine):
        self._speech_engine_ref = engine

    def set_mode(self, mode: str):
        self.mode = "wake" if mode == "wake" else "always_on"
        if self.mode == "always_on":
            self._set_state("listening")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.enabled = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gs-voice-pipeline")
        self._thread.start()

    def stop(self):
        self.enabled = False

    # ---------------------------------------------------------- push-to-talk

    def begin_push_capture(self, max_sec: float = 7.0):
        """Mic button pressed: force-capture next utterance regardless of mode
        (delivered through on_transcript with source='push')."""
        self._force_capture_until = time.time() + max_sec
        self._armed_until = 0.0
        self._set_state("listening")

    # ------------------------------------------------------------- state mgt

    def _set_state(self, state: str):
        if state != self._state:
            self._state = state
            if self.on_state_changed:
                try:
                    self.on_state_changed(state)
                except Exception:
                    pass

    @property
    def state(self) -> str:
        return self._state

    # --------------------------------------------------------------- stream

    def _audio_callback(self, indata, frames, time_info, status):
        if self.enabled:
            self._audio_q.put(indata.copy())

    def _loop(self):
        dev_id, dev_sr = get_best_input_device()
        block_samples = int(dev_sr * BLOCK_SEC)
        print(f"[VoicePipeline] stream dev={dev_id} sr={dev_sr}")

        try:
            self._stream = sd.InputStream(
                device=dev_id, samplerate=dev_sr, channels=1,
                dtype="int16", blocksize=block_samples,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            print(f"[VoicePipeline] InputStream falhou: {e}")
            return

        self._set_state("listening")

        preroll: list[np.ndarray] = []
        frames_buf: list[np.ndarray] = []
        in_phrase = False
        silent = 0
        blocks = 0

        while self.enabled:
            try:
                # Half-duplex: while TTS plays, drain and skip capture
                if self._speech_engine_ref and getattr(self._speech_engine_ref, "is_speaking", False):
                    self._drain()
                    preroll.clear(); frames_buf.clear()
                    in_phrase = False; silent = 0
                    self._set_state("speaking")
                    # Record when speech ends for post-speech cooldown
                    self._post_speech_cooldown_until = time.time() + 1.5  # 1.5s cooldown
                    time.sleep(0.15)
                    continue

                # Post-speech cooldown: suppress mic capture for 1.5s after TTS finishes
                # to avoid capturing speaker echo/reverb as user speech
                if time.time() < self._post_speech_cooldown_until:
                    self._drain()
                    preroll.clear(); frames_buf.clear()
                    in_phrase = False; silent = 0
                    time.sleep(0.05)
                    continue

                try:
                    chunk = self._audio_q.get(timeout=0.5)
                except queue.Empty:
                    self._set_state("listening" if self._armed() else
                                    ("listening" if self.mode == "always_on" else "idle"))
                    continue

                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                if self.rms_callback:
                    try:
                        self.rms_callback(rms)
                    except Exception:
                        pass

                self._set_state("listening")

                threshold = max(36.0, self._ambient * 1.22 + 5.0)
                forcing = time.time() < self._force_capture_until
                effective = max(18.0, self._ambient * 1.08) if forcing else threshold

                if rms > effective:
                    if not in_phrase:
                        in_phrase = True
                        frames_buf = list(preroll)   # prepend pre-roll
                        silent = 0
                        blocks = 0
                    frames_buf.append(chunk)
                    silent = 0
                    blocks += 1
                else:
                    if not in_phrase:
                        # ambient calibration + maintain pre-roll ring buffer
                        self._ambient = 0.92 * self._ambient + 0.08 * rms
                        preroll.append(chunk)
                        if len(preroll) > PREROLL_BLOCKS:
                            preroll.pop(0)
                    else:
                        frames_buf.append(chunk)
                        silent += 1
                        blocks += 1

                utt_done = (silent >= SILENCE_BLOCKS_END) or (blocks >= MAX_UTTERANCE_BLOCKS)
                if in_phrase and utt_done:
                    in_phrase = False
                    audio = np.concatenate(frames_buf, axis=0).flatten()
                    frames_buf.clear(); preroll.clear(); silent = 0; blocks = 0

                    dur = len(audio) / dev_sr
                    if dur >= MIN_UTTERANCE_SEC:
                        forcing = time.time() < self._force_capture_until or self._force_capture_until > time.time() - 1.0
                        self._handle_utterance(audio, dev_sr, source="push" if forcing else "voice")

            except Exception as e:
                print(f"[VoicePipeline] loop error: {e}")
                time.sleep(0.3)

        try:
            self._stream.stop(); self._stream.close()
        except Exception:
            pass

    def _armed(self) -> bool:
        return time.time() < self._armed_until

    def _drain(self):
        while True:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                return

    # ------------------------------------------------------------- utterance

    def _handle_utterance(self, audio: np.ndarray, src_sr: int, source: str = "voice"):
        audio16 = self._resample(audio, src_sr, TARGET_SR)
        audio16 = enhance_audio(audio16, TARGET_SR)   # clarity pass for STT
        wav_bytes = self._wav_bytes(audio16)
        self._set_state("thinking")

        t0 = time.perf_counter()
        text, engine = self._transcribe(wav_bytes)
        self.last_stt_ms = int((time.perf_counter() - t0) * 1000)
        self.last_stt_engine = engine

        if not text:
            self._set_state("listening" if self.mode == "always_on" else "idle")
            return

        print(f"[VoicePipeline] ({engine} {self.last_stt_ms}ms) «{text}»")

        # Filter out very short/noise transcriptions (likely echo or ambient)
        text_stripped = text.strip()
        if len(text_stripped) < 4:
            print(f"[VoicePipeline] Ignoring short transcript: «{text}»")
            self._set_state("listening" if self.mode == "always_on" else "idle")
            return
        # Filter common false-positive noise words
        _noise_words = {"shh", "hmm", "uhh", "umm", "ahh", "ehh", "huh", "hm", "uh", "ah", "eh", "oh"}
        if text_stripped.lower().rstrip(".") in _noise_words:
            print(f"[VoicePipeline] Ignoring noise word: «{text}»")
            self._set_state("listening" if self.mode == "always_on" else "idle")
            return

        # Wake-gated mode logic
        if self.mode == "wake":
            wake = fuzzy_wake_match(text)
            if wake:
                self._armed_until = time.time() + WAKE_ARMED_WINDOW
                if self.on_wake:
                    try:
                        self.on_wake()
                    except Exception:
                        pass
                remainder = strip_wake_phrase(text, leading_only=True)
                if len(remainder) >= 3:
                    self._armed_until = 0.0
                    self._emit(remainder)
                return
            if self._armed():
                self._armed_until = 0.0
                self._emit(strip_wake_phrase(text, leading_only=True))
                return
            # not armed and no wake word → ignore utterance
            self._set_state("idle")
            return

        # Always-on mode: everything is a command (wake phrase only if leading)
        cleaned = strip_wake_phrase(text, leading_only=True)
        self._emit(cleaned if len(cleaned) >= 2 else text)

    def _emit(self, text: str):
        if self.on_transcript and text:
            try:
                self.on_transcript(text, "voice")
            except Exception as e:
                print(f"[VoicePipeline] transcript cb error: {e}")

    # ------------------------------------------------------------------- STT

    def _transcribe(self, wav_bytes: bytes) -> tuple[str | None, str]:
        # 1) Groq Whisper large-v3-turbo (fast + accurate)
        if self.groq_client:
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(wav_bytes)
                    tmp_path = tmp.name
                try:
                    with open(tmp_path, "rb") as f:
                        resp = self.groq_client.audio.transcriptions.create(
                            file=(os.path.basename(tmp_path), f.read()),
                            model="whisper-large-v3-turbo",
                            language=self.stt_language,
                            prompt=STT_CONTEXT_PROMPT,   # biases domain vocabulary
                            temperature=0,               # deterministic, no hallucination
                            response_format="text",
                        )
                    txt = str(resp).strip()
                    if txt and len(txt) > 1 and not is_prompt_echo(txt) \
                            and txt.lower() not in ("obrigado.", "obrigado", "thank you."):
                        return txt, "whisper"
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[VoicePipeline] Whisper error: {e}")

        # 2) Google Speech fallback
        try:
            import speech_recognition as sr
            recog = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio_data = recog.record(source)
            txt = recog.recognize_google(audio_data, language="pt-BR")
            if txt and len(txt) > 1:
                return str(txt), "google"
        except Exception:
            pass

        return None, "none"

    # ------------------------------------------------------------------ util

    @staticmethod
    def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        if orig_sr == target_sr:
            return audio
        n = int(len(audio) * target_sr / orig_sr)
        idx = np.linspace(0, len(audio) - 1, n)
        res = np.interp(idx, np.arange(len(audio)), audio.astype(np.float32))
        return res.astype(np.int16)

    @staticmethod
    def _wav_bytes(audio_16k: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(TARGET_SR)
            wf.writeframes(audio_16k.tobytes())
        return buf.getvalue()

    # ------------------------------------------------- one-shot transcription

    def transcribe_bytes(self, wav_bytes: bytes) -> str | None:
        """Public helper: transcribe arbitrary WAV bytes (used by mic button)."""
        text, _ = self._transcribe(wav_bytes)
        return text
