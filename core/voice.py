#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Sistema de Voz (v3)
====================================
TTS rápido via edge-tts + os.startfile
STT via speech_recognition
Wake word detection: "Elívea"
Always-listening mode
"""

import os
import io
import re
import tempfile
import asyncio
import logging
import subprocess
import threading
import wave
import struct
import time
from pathlib import Path
from typing import Optional, Callable, List
from enum import Enum

logger = logging.getLogger("elvea.voice")

# Vozes disponíveis
PT_VOICES = {
    "Feminina Brasil": "pt-BR-FranciscaNeural",
    "Masculina Brasil": "pt-BR-AntonioNeural",
    "Feminina Portugal": "pt-PT-RaquelNeural",
    "Masculina Portugal": "pt-PT-DuarteNeural",
}

EN_VOICES = {
    "Feminina US": "en-US-JennyNeural",
    "Masculina US": "en-US-GuyNeural",
    "Feminina UK": "en-GB-SoniaNeural",
}

ALL_VOICES = {**PT_VOICES, **EN_VOICES}

# Wake words (case-insensitive)
WAKE_WORDS = [
    "elívea",
    "elvea",
    "great sage",
    "grande sabio",
    "grande sábio",
    "grande saber",
    "hey sage",
    "hey sabio",
    "sage",
]


class ListenMode(Enum):
    OFF = "off"
    PUSH_TO_TALK = "push_to_talk"
    WAKE_WORD = "wake_word"
    ALWAYS_ON = "always_on"


class VoiceEngine:
    """Engine de voz com TTS, STT, wake word e always-listening."""

    def __init__(self):
        self.tts_voice = "pt-BR-FranciscaNeural"
        self.tts_rate = "+0%"
        self.tts_volume = "+0%"
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._recording = False
        self._listen_mode = ListenMode.OFF
        self._wake_word_thread: Optional[threading.Thread] = None
        self._wake_word_active = False

        # Callbacks
        self.on_wake_detected: Optional[Callable[[str], None]] = None
        self.on_command_received: Optional[Callable[[str], None]] = None
        self.on_listen_state_changed: Optional[Callable[[str], None]] = None

    # ═══ TEXT-TO-SPEECH ═══════════════════════════════════════════════

    def speak(self, text: str, callback: Optional[Callable] = None):
        """Fala o texto usando edge-tts."""
        if not text.strip():
            return

        self._is_speaking = True
        self._stop_event.clear()

        def _do_tts():
            tmp_mp3 = None
            try:
                import edge_tts
                communicate = edge_tts.Communicate(
                    text, self.tts_voice,
                    rate=self.tts_rate,
                    volume=self.tts_volume,
                )
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_mp3 = f.name
                asyncio.run(communicate.save(tmp_mp3))

                if self._stop_event.is_set():
                    return

                # Play with default media player
                os.startfile(tmp_mp3)

                # Estimate duration and wait
                try:
                    file_size = os.path.getsize(tmp_mp3)
                    estimated = max(1.0, min(file_size / 16000.0, 30.0))
                except Exception:
                    estimated = 5.0

                elapsed = 0.0
                while elapsed < estimated and not self._stop_event.is_set():
                    time.sleep(0.2)
                    elapsed += 0.2

            except Exception as e:
                logger.error(f"TTS error: {e}")
            finally:
                self._is_speaking = False
                if tmp_mp3:
                    try:
                        os.unlink(tmp_mp3)
                    except OSError:
                        pass
                if callback:
                    try:
                        callback()
                    except Exception:
                        pass

        thread = threading.Thread(target=_do_tts, daemon=True)
        thread.start()

    def speak_async(self, text: str, callback: Optional[Callable] = None):
        """Fala o texto assincronamente."""
        self.speak(text, callback)

    def stop_speaking(self):
        """Para de falar."""
        self._stop_event.set()
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    # ═══ SPEECH RECOGNITION ═══════════════════════════════════════════

    def listen_once(self, callback: Optional[Callable[[str], None]] = None,
                    timeout: int = 5, language: str = "pt-BR"):
        """Escuta uma vez do microfone."""
        def _listen():
            text = self.listen(timeout=timeout, language=language)
            if callback and text:
                callback(text)
        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()

    def listen(self, timeout: int = 5, language: str = "pt-BR") -> Optional[str]:
        """Escuta do microfone e retorna o texto reconhecido.
        Tenta Whisper local primeiro, depois Google STT como fallback.
        """
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8

            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=15)

            # Try Whisper first (offline, more accurate)
            try:
                import whisper
                import tempfile
                wav_data = audio.get_wav_data()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(wav_data)
                    tmp_path = f.name

                model = whisper.load_model("base")
                result = model.transcribe(tmp_path, language="pt")
                text = result.get("text", "").strip()

                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

                if text:
                    logger.info(f"Whisper: {text}")
                    return text
            except ImportError:
                pass  # Whisper not installed
            except Exception as e:
                logger.warning(f"Whisper error: {e}")

            # Fallback to Google STT
            try:
                text = recognizer.recognize_google(audio, language=language)
                logger.info(f"Google STT: {text}")
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                logger.warning(f"STT erro: {e}")
                return None
        except Exception as e:
            logger.error(f"Microfone erro: {e}")
            return None

    # ═══ WAKE WORD DETECTION ═══════════════════════════════════════════

    def _contains_wake_word(self, text: str) -> bool:
        """Verifica se o texto contém uma wake word."""
        text_lower = text.lower().strip()
        for wake in WAKE_WORDS:
            if wake in text_lower:
                return True
        return False

    def _extract_command_after_wake(self, text: str) -> Optional[str]:
        """Extrai o comando após a wake word."""
        text_lower = text.lower().strip()
        for wake in WAKE_WORDS:
            idx = text_lower.find(wake)
            if idx >= 0:
                # Remove wake word and everything before it
                after = text[idx + len(wake):].strip()
                # Remove common connectors
                for connector in [",", ".", ":", "por favor", "pf", "pff"]:
                    if after.lower().startswith(connector):
                        after = after[len(connector):].strip()
                if after:
                    return after
        return None

    def start_wake_word_detection(self, command_callback: Callable[[str], None]):
        """Inicia detecção de wake word em background."""
        if self._wake_word_active:
            return

        self._wake_word_active = True
        self._listen_mode = ListenMode.WAKE_WORD

        def _wake_loop():
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                recognizer.energy_threshold = 300
                recognizer.dynamic_energy_threshold = True
                recognizer.pause_threshold = 0.8

                logger.info("Wake word detection iniciada")

                while self._wake_word_active:
                    try:
                        with sr.Microphone() as source:
                            recognizer.adjust_for_ambient_noise(source, duration=0.3)
                            # Shorter timeout for responsive wake detection
                            audio = recognizer.listen(source, timeout=2,
                                                      phrase_time_limit=10)

                        text = recognizer.recognize_google(audio, language="pt-BR")
                        if text:
                            logger.info(f"Wake scan: {text}")

                            if self._contains_wake_word(text):
                                logger.info(f"Wake word detectada: {text}")

                                # Notify UI
                                if self.on_wake_detected:
                                    self.on_wake_detected(text)

                                # Extract command after wake word
                                command = self._extract_command_after_wake(text)
                                if command:
                                    # Command was said with wake word
                                    if self.on_command_received:
                                        self.on_command_received(command)
                                else:
                                    # Just wake word — now listen for command
                                    if self.on_listen_state_changed:
                                        self.on_listen_state_changed("listening_for_command")

                                    cmd_text = self.listen(timeout=8, language="pt-BR")
                                    if cmd_text and self.on_command_received:
                                        self.on_command_received(cmd_text)

                                    if self.on_listen_state_changed:
                                        self.on_listen_state_changed("wake_word")

                    except Exception:
                        continue

            except ImportError:
                logger.warning("speech_recognition não instalado")
            except Exception as e:
                logger.error(f"Wake word erro: {e}")

        self._wake_word_thread = threading.Thread(target=_wake_loop, daemon=True)
        self._wake_word_thread.start()

    def stop_wake_word_detection(self):
        """Para a detecção de wake word."""
        self._wake_word_active = False
        self._listen_mode = ListenMode.OFF
        logger.info("Wake word detection parada")

    # ═══ ALWAYS-ON LISTENING ═══════════════════════════════════════════

    def start_always_on(self, command_callback: Callable[[str], None]):
        """Modo sempre ouvindo — envia qualquer fala como comando."""
        if self._recording:
            return

        self._recording = True
        self._listen_mode = ListenMode.ALWAYS_ON

        def _always_loop():
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                recognizer.energy_threshold = 300
                recognizer.dynamic_energy_threshold = True
                recognizer.pause_threshold = 1.0

                logger.info("Modo sempre ouvindo ativado")

                while self._recording:
                    try:
                        with sr.Microphone() as source:
                            recognizer.adjust_for_ambient_noise(source, duration=0.3)
                            audio = recognizer.listen(source, timeout=3,
                                                      phrase_time_limit=15)

                        text = recognizer.recognize_google(audio, language="pt-BR")
                        if text:
                            logger.info(f"Always-on: {text}")
                            if self.on_listen_state_changed:
                                self.on_listen_state_changed("command_received")
                            if command_callback:
                                command_callback(text)
                    except Exception:
                        continue

            except ImportError:
                logger.warning("speech_recognition não instalado")
            except Exception as e:
                logger.error(f"Always-on erro: {e}")

        thread = threading.Thread(target=_always_loop, daemon=True)
        thread.start()

    def stop_always_on(self):
        """Para o modo sempre ouvindo."""
        self._recording = False
        self._listen_mode = ListenMode.OFF
        logger.info("Modo sempre ouvindo parado")

    # ═══ LISTEN MODE MANAGEMENT ═════════════════════════════════════════

    def set_listen_mode(self, mode: ListenMode, command_callback: Optional[Callable] = None):
        """Muda o modo de escuta."""
        # Stop current mode
        self.stop_wake_word_detection()
        self.stop_always_on()

        self._listen_mode = mode

        if mode == ListenMode.WAKE_WORD and command_callback:
            self.start_wake_word_detection(command_callback)
        elif mode == ListenMode.ALWAYS_ON and command_callback:
            self.start_always_on(command_callback)

    @property
    def listen_mode(self) -> ListenMode:
        return self._listen_mode

    @property
    def is_listening(self) -> bool:
        return self._wake_word_active or self._recording

    # ═══ CONFIGURATION ═════════════════════════════════════════════════

    def set_voice(self, voice_name: str):
        if voice_name in ALL_VOICES:
            self.tts_voice = ALL_VOICES[voice_name]
        elif voice_name in PT_VOICES.values() or voice_name in EN_VOICES.values():
            self.tts_voice = voice_name

    def set_rate(self, rate: str):
        self.tts_rate = rate

    def set_volume(self, volume: str):
        self.tts_volume = volume

    def get_available_voices(self) -> dict:
        return ALL_VOICES.copy()
