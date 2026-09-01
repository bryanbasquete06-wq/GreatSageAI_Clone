"""
Elívea — Elívea Class Application
==========================================
Orquestra o sistema completo:

     Voz → VoicePipeline (VAD + Whisper V3 Turbo)
     LLM → EliveaLLM (Groq GPT-OSS 120B em STREAMING)
     Voz → SpeechEngine (TTS neural por frases, fala enquanto pensa)
     UI → EliveaMainWindow (interface ＜Elívea＞ estilo Tensura)

by: bryan
"""

from __future__ import annotations

import re
import sys
import threading
import time
import atexit
from pathlib import Path

# Carrega .env
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# ═══ SAFETY: patch os.system to run silently (no PowerShell windows) ═══
try:
    from core.silent_run import patch_os_system
    patch_os_system()
except Exception:
    pass

# Tudo no disco F ASCII — evita MCI falhar com acento
try:
    import os, tempfile
    _ft = Path("F:/EliveaTemp")
    _ft.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(_ft)
    os.environ["TMP"] = str(_ft)
    os.environ["TEMP"] = str(_ft)
    os.environ["TMPDIR"] = str(_ft)
    os.environ["HF_HOME"] = str(_ft / "hf_cache")
    os.environ["TRANSFORMERS_CACHE"] = str(_ft / "hf_cache")
    os.environ["TORCH_HOME"] = str(_ft / "torch_cache")
    os.environ["XDG_CACHE_HOME"] = str(_ft / "cache")
    for _d in ["hf_cache","torch_cache","cache","elvea_tts","uploads"]:
        (_ft / _d).mkdir(parents=True, exist_ok=True)
except Exception:
    pass

try:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    _qt_api = "PySide6"
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal as Signal
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
    _qt_api = "PyQt6"

try:
    from core.persona import PersonaManager
except ImportError:
    try:
        from core.persona import PersonaManager
    except ImportError:
        from persona import PersonaManager

try:
    from core.llm import EliveaLLM
except ImportError:
    try:
        from core.llm import EliveaLLM
    except ImportError:
        # fallback para LLMEngine (clone)
        try:
            from core.llm import LLMEngine as EliveaLLM
        except ImportError:
            from core.llm import LLMEngine as EliveaLLM
from core.mark_l_bridge import MarkLBridge
from core.speech_engine import SpeechEngine
from core.voice_pipeline import VoicePipeline
from core.autonomous_engine import AutonomousEngine
from modules.system import SystemModule
from modules.files import FileModule
from modules.web import WebModule
from modules.coder_agent import CoderAgentModule
from modules.automation import AutomationModule
from modules.self_improver import SelfImproverModule
from modules.hardware_controller import HardwareController
from modules.productivity import ProductivityModule
from modules.superuser import SuperUser
from memory.memory_manager import MemoryManager
from core.intent_engine import IntentEngine
from ui.qt_ui import EliveaMainWindow
from core.security import SecurityGuard, SecurityLevel
from core.ambiance import AmbianceEngine
from modules.rag import RAGEngine
from modules.clipboard import ClipboardMonitor
from modules.screen_context import ScreenContext
from modules.scheduler import TaskScheduler
from modules.monitor import SystemMonitor
from modules.plugin_system import PluginManager
from core.voice_cloner import VoiceCloner
from modules.multilang import MultiLang
from modules.learning import LearningEngine
from modules.app_integration import AppIntegration
from ui.dashboard import WebDashboard
from core.updater import AutoUpdater
from modules.config_manager import ConfigManager

from core.logger import get_logger
from core.event_bus import event_bus
from core.state_manager import state
from core.audit_log import audit, ActionLevel
from core.secret_manager import secrets
from core.memory_persistent import PersistentMemory
from core.chain_of_thought import ChainOfThought
from core.proactive_engine import ProactiveEngine
from core.smart_improvements import (
    SessionMemory, LearningDashboard, ErrorLearner, CodePatternLearner,
    VoiceCommandLearner, SmartReminders, ConversationSummarizer,
    MoodTracker, ResponseFeedback, SmartDefaults, CodeSnippetCache,
    ConversationBranching, ProactiveCodeReview, SmartFileRecommendations,
    AdaptiveResponseLength, PersonalityLearning, KnowledgeGraph,
    SmartAliases, HealthMonitor,
)
from core.image_analyzer import analyzer as image_analyzer
from core.video_analyzer import analyzer as video_analyzer
from core.link_analyzer import analyzer as link_analyzer
from core.autonomous_planner import AutonomousPlanner
from core.code_analyzer import analyze_file, analyze_project, quick_analyze
from core.nine_router import NineRouterBridge
from modules.browser_agent import BrowserAgent
from core.usage_tracker import UsageTracker


# ---------------------------------------------------------------------------
# Thread-safe bridge: worker threads → Qt main thread (auto queued signals)
# ---------------------------------------------------------------------------

class SignalBridge(QObject):
    sig_master_text = Signal(str) # user said/typed something
    sig_sage_full = Signal(str) # complete local answer
    sig_sage_begin = Signal() # LLM stream started
    sig_sage_delta = Signal(str) # LLM stream delta
    sig_sage_end = Signal() # LLM stream ended
    sig_state = Signal(str) # pipeline state
    sig_rms = Signal(float) # mic RMS
    sig_telemetry = Signal(str, int, str, int) # stt_engine, stt_ms, model, ttft_ms
    sig_code_request = Signal(str) # abrir Ala de Programação + tarefa
    sig_self_improve = Signal(str, str) # (tarefa, modo) → self-improve via SmartCodeAgent


class EliveaApp:
    def __init__(self):
        import logging as _log
        _startup_log = _log.getLogger("elvea.startup")
        self._init_errors = []  # Track non-fatal init errors

        # --- engines (critical path — individual protection) ---
        try:
            self.persona = PersonaManager()
        except Exception as e:
            _startup_log.warning(f"PersonaManager init failed: {e}")
            self.persona = None
            self._init_errors.append("PersonaManager")

        try:
            self.llm = EliveaLLM()
        except Exception as e:
            _startup_log.error(f"EliveaLLM init failed: {e}")
            raise  # LLM is critical — cannot start without it

        try:
            self.nine_router = NineRouterBridge(llm_engine=self.llm)
        except Exception as e:
            _startup_log.warning(f"NineRouterBridge init failed: {e}")
            self.nine_router = None
            self._init_errors.append("NineRouterBridge")

        try:
            self.bridge = MarkLBridge()
        except Exception as e:
            _startup_log.warning(f"MarkLBridge init failed: {e}")
            self.bridge = None
            self._init_errors.append("MarkLBridge")

        try:
            self.speech = SpeechEngine(voice_key="raphael")
        except Exception as e:
            _startup_log.warning(f"SpeechEngine init failed: {e}")
            self.speech = None
            self._init_errors.append("SpeechEngine")

        try:
            self.pipeline = VoicePipeline()
        except Exception as e:
            _startup_log.warning(f"VoicePipeline init failed: {e}")
            self.pipeline = None
            self._init_errors.append("VoicePipeline")

        try:
            self.autonomous = AutonomousEngine()
            self.autonomous.start_autonomous_loop()
        except Exception as e:
            _startup_log.warning(f"AutonomousEngine init failed: {e}")
            self.autonomous = None
            self._init_errors.append("AutonomousEngine")

        # --- UI signal bridge
        self.signals = SignalBridge()
        self._first_interaction = True

        # --- wire voice pipeline (only if both components are available)
        if self.pipeline and self.speech:
            try:
                self.pipeline.set_speech_engine(self.speech)
                self.pipeline.on_transcript = self._on_voice_transcript
                self.pipeline.on_wake = self._on_wake_word
                self.pipeline.on_state_changed = self._on_pipeline_state
                self.pipeline.rms_callback = self._on_mic_rms
                self.pipeline.start()
            except Exception as e:
                _startup_log.warning(f"Voice pipeline wiring failed: {e}")

            # --- wire speech playback states → UI
            try:
                self.speech.on_playback_start = lambda: self.signals.sig_state.emit("speaking")
                self.speech.on_playback_end = lambda: self.signals.sig_state.emit(
                    "listening" if self.pipeline.mode == "always_on" else "idle")
                self.speech.on_error = lambda msg: self.signals.sig_sage_full.emit(
                    f"⚠️ {msg}")
            except Exception as e:
                _startup_log.warning(f"Speech UI wiring failed: {e}")

        # --- initialize new modules
        try:
            TaskScheduler.start()
        except Exception as e:
            _startup_log.warning(f"TaskScheduler start failed: {e}")

        try:
            PluginManager.load_all_enabled()
        except Exception as e:
            _startup_log.warning(f"PluginManager load failed: {e}")

        try:
            LearningEngine.record_preference("session_start", __import__("datetime").datetime.now().isoformat())
        except Exception as e:
            _startup_log.debug(f"LearningEngine record failed: {e}")

        # --- Mark-L tools
        try:
            self.mark_l_tools = self.bridge.actions if self.bridge and self.bridge.is_connected() else {}
        except Exception as e:
            self.mark_l_tools = {}
            _startup_log.warning(f"MarkL tools failed: {e}")

        # --- new infrastructure
        self.log = get_logger("elvea.app")
        self.log.info("Elívea inicializando")

        try:
            self.persistent_memory = PersistentMemory()
        except Exception as e:
            _startup_log.error(f"PersistentMemory init failed: {e}")
            raise  # Memory is critical

        try:
            self.proactive = ProactiveEngine(memory=self.persistent_memory)
        except Exception as e:
            _startup_log.warning(f"ProactiveEngine init failed: {e}")
            self.proactive = None
            self._init_errors.append("ProactiveEngine")

        # --- Smart Improvements (20 features) — bulk protection ---
        _smart_modules = {}
        _smart_init_map = {
            "session_mem": lambda: SessionMemory(),
            "learning_dashboard": lambda: LearningDashboard(memory=self.persistent_memory),
            "error_learner": lambda: ErrorLearner(memory=self.persistent_memory),
            "code_patterns": lambda: CodePatternLearner(memory=self.persistent_memory),
            "voice_learner": lambda: VoiceCommandLearner(memory=self.persistent_memory),
            "smart_reminders": lambda: SmartReminders(memory=self.persistent_memory),
            "summarizer": lambda: ConversationSummarizer(memory=self.persistent_memory),
            "mood_tracker": lambda: MoodTracker(memory=self.persistent_memory),
            "response_feedback": lambda: ResponseFeedback(memory=self.persistent_memory),
            "smart_defaults": lambda: SmartDefaults(memory=self.persistent_memory),
            "snippet_cache": lambda: CodeSnippetCache(),
            "conversation_branching": lambda: ConversationBranching(),
            "code_review": lambda: ProactiveCodeReview(memory=self.persistent_memory),
            "file_recs": lambda: SmartFileRecommendations(),
            "adaptive_length": lambda: AdaptiveResponseLength(),
            "personality_learner": lambda: PersonalityLearning(),
            "knowledge_graph": lambda: KnowledgeGraph(),
            "smart_aliases": lambda: SmartAliases(),
            "health_monitor": lambda: HealthMonitor(),
        }
        for name, factory in _smart_init_map.items():
            try:
                _smart_modules[name] = factory()
            except Exception as e:
                _startup_log.debug(f"Smart module '{name}' init skipped: {e}")
                self._init_errors.append(name)
        # Set all successful modules as attributes
        for name, obj in _smart_modules.items():
            setattr(self, name, obj)
        # Set failed modules to None so code can check
        for name in _smart_init_map:
            if not hasattr(self, name):
                setattr(self, name, None)

        # Usage tracker — real-time provider monitoring
        try:
            self.usage_tracker = UsageTracker()
        except Exception as e:
            _startup_log.warning(f"UsageTracker init failed: {e}")
            self.usage_tracker = None
            self._init_errors.append("UsageTracker")

        # Message Monitor — auto-reply to WhatsApp, Telegram, Discord, Email
        try:
            from modules.message_monitor import MessageMonitor, MonitorConfig
            msg_config = MonitorConfig()
            self.message_monitor = MessageMonitor(config=msg_config, llm_engine=self.llm)
            self.message_monitor.on_message(self._on_incoming_message)
            self.message_monitor.on_reply(self._on_auto_reply)
            self.message_monitor.start()
            self.log.info("MessageMonitor started — auto-reply active")
        except Exception as e:
            self.log.debug(f"MessageMonitor init skipped: {e}")

        # SPEED: pre-warm TTS cache + LLM connections
        try:
            from core.speed_optimizer import get_tts_cache, get_connection_pool
            if self.speech:
                tts_cache = get_tts_cache()
                tts_cache.preload(
                    self.speech.preset.voice_id,
                    self.speech.preset.rate,
                    self.speech.preset.pitch,
                )
            pool = get_connection_pool()
            pool.warm_all(self.llm.providers)
        except Exception:
            pass

        try:
            self.cot = ChainOfThought(llm=self.llm)
        except Exception as e:
            _startup_log.warning(f"ChainOfThought init failed: {e}")
            self.cot = None

        try:
            self.autonomous_planner = AutonomousPlanner(llm=self.llm)
        except Exception as e:
            _startup_log.warning(f"AutonomousPlanner init failed: {e}")
            self.autonomous_planner = None

        # Code analyzer uses functions directly
        self.code_analyzer = None  # Using module functions directly

        # --- Wire autonomous self-improvement ---
        # When the autonomous engine detects critical issues,
        # the self-improver kicks in automatically to fix them.
        if self.autonomous:
            try:
                self.autonomous.on_issue_detected(
                    lambda health: SelfImproverModule.on_autonomous_diagnostic(
                        health, llm=self.llm,
                        on_step=lambda text: self.signals.sig_sage_delta.emit(text),
                    )
                )
                self.log.info("Autonomous self-improvement wired")
            except Exception as e:
                _startup_log.warning(f"Self-improvement wiring failed: {e}")

        # ═══════════════════════════════════════════════════════════════
        # MODULE 1: Clipboard Monitor
        # ═══════════════════════════════════════════════════════════════
        try:
            self.clipboard_monitor = ClipboardMonitor()
            self.clipboard_monitor.start()
            self.log.info("ClipboardMonitor active")
        except Exception as e:
            self.log.debug(f"ClipboardMonitor skip: {e}")

        # ═══════════════════════════════════════════════════════════════
        # MODULE 2: Screen Context
        # ═══════════════════════════════════════════════════════════════
        try:
            self.screen_context = ScreenContext()
            self.log.info("ScreenContext active")
        except Exception as e:
            self.log.debug(f"ScreenContext skip: {e}")

        # ═══════════════════════════════════════════════════════════════
        # MODULE 3: RAG Engine
        # ═══════════════════════════════════════════════════════════════
        try:
            self.rag = RAGEngine()
            self.log.info("RAGEngine active")
        except Exception as e:
            self.log.debug(f"RAGEngine skip: {e}")

        # ═══════════════════════════════════════════════════════════════
        # MODULE 4: MultiLang
        # ═══════════════════════════════════════════════════════════════
        try:
            self.multilang = MultiLang()
            self.log.info("MultiLang active")
        except Exception as e:
            self.log.debug(f"MultiLang skip: {e}")

        # ═══════════════════════════════════════════════════════════════
        # MODULE 5: App Integration
        # ═══════════════════════════════════════════════════════════════
        try:
            self.app_integration = AppIntegration()
            self.log.info("AppIntegration active")
        except Exception as e:
            self.log.debug(f"AppIntegration skip: {e}")

        state.update({"app_state": "initializing"})
        event_bus.emit("app.starting")

    def get_api_key(self, provider: str) -> str:
        """Busca API key do secret manager ou .env."""
        key = secrets.get(f"{provider.upper()}_API_KEY")
        if key:
            return key
        import os
        return os.environ.get(f"{provider.upper()}_API_KEY", "")

    # =================================================================
    # Voice event handlers (called from pipeline thread)
    # =================================================================

    def _on_voice_transcript(self, text: str, source: str):
        self.log.debug(f"transcript ({source}): {text}")
        self.signals.sig_master_text.emit(text)
        self._check_ambiance(text)
        # Screen context: capture what's on screen when user speaks
        ctx_prefix = ""
        try:
            if hasattr(self, 'screen_context') and self.screen_context:
                ctx = self.screen_context.get_context()
                if ctx:
                    ctx_prefix = f"[SCREEN: {ctx[:200]}] "
        except Exception:
            pass
        # Prefix [AUDIO] so LLM knows this came from the microphone
        voice_text = f"[AUDIO] {ctx_prefix}{text}" if source == "voice" else text
        self.handle_command(voice_text)

    def _check_ambiance(self, text: str):
        """Analisa humor, saudacao temporal, insights proativos."""
        result = AmbianceEngine.on_interaction(text)
        if self._first_interaction and result.get("greeting"):
            # Boot already sends greeting to chat, don't speak it again
            self._first_interaction = False
        if result.get("proactive"):
            self.signals.sig_sage_full.emit(result["proactive"])
            self.speech.speak(result["proactive"])
        if result.get("humor"):
            self.speech.speak(result["humor"])
        try:
            MemoryManager.save_emotional_state(result["mood"], text[:200])
        except Exception:
            pass

    def _on_wake_word(self):
        self.speech.play_wake_chime()
        greeting = AmbianceEngine.get_greeting()
        self.speech.speak(greeting)

    def _on_pipeline_state(self, state: str):
        self.signals.sig_state.emit(state)

    def _on_mic_rms(self, rms: float):
        self.signals.sig_rms.emit(rms)

    # =================================================================
    # Self-improvement: SmartCodeAgent auto-programação via thread
    # =================================================================

    def _on_self_improve(self, task: str, mode: str):
        """Handler para sig_self_improve — roda SmartCodeAgent em thread."""
        def _worker():
            try:
                self.signals.sig_state.emit("thinking")
                on_step = lambda text: self.signals.sig_sage_delta.emit(text)
                if mode == "prompt":
                    report, answer = SelfImproverModule.run_prompt(
                        self.llm, task, on_step=on_step)
                elif mode == "targeted":
                    report, answer = SelfImproverModule.run_self_improve(
                        self.llm, on_step=on_step, task=task)
                elif mode == "continuous":
                    report, answer = SelfImproverModule.run_continuous(
                        self.llm, on_step=on_step, rounds=0)
                else:
                    report, answer = SelfImproverModule.run_self_improve(
                        self.llm, on_step=on_step)
                self.signals.sig_sage_full.emit(report)
                try:
                    MemoryManager.archive_turn(f"[auto-prog] {task or mode}", answer)
                except Exception:
                    pass
                self.speech.speak(answer)
            except Exception as e:
                err = f"Auto-programação falhou: {e}"
                self.signals.sig_sage_full.emit(err)
                self.speech.speak(err)
            finally:
                self.signals.sig_state.emit("idle")
        threading.Thread(target=_worker, daemon=True).start()

    # =================================================================
    # Message Monitor callbacks
    # =================================================================

    def _on_incoming_message(self, message):
        """Called when a new message is detected."""
        try:
            source = message.source.value if hasattr(message.source, 'value') else str(message.source)
            self.log.info(f"Incoming message [{source}] from {message.sender}: {message.content[:80]}")
            self.signals.sig_sage_full.emit(
                f"\U0001f4e2 Mensagem de {message.sender} ({source}):\n{message.content[:200]}")
        except Exception:
            pass

    def _on_auto_reply(self, message, reply):
        """Called when an auto-reply was sent."""
        try:
            source = message.source.value if hasattr(message.source, 'value') else str(message.source)
            self.log.info(f"Auto-reply to {message.sender} ({source}): {reply[:80]}")
        except Exception:
            pass

    # =================================================================
    # Command routing: local intents first, LLM streaming fallback
    # =================================================================

    def handle_command(self, cmd: str):
        cmd_clean = cmd.strip()
        audit.log("command", cmd_clean[:200], ActionLevel.INFO, "app")
        if not cmd_clean:
            return

        # ═══ GLOBAL SAFETY: block destructive commands unless explicitly confirmed ═══
        _cmd_lower = cmd_clean.lower()
        _dangerous_keywords = ('desligar', 'shutdown', 'reiniciar', 'restart', 'reboot')
        _confirmation_words = ('confirm', 'confirma', 'sim', 'yes', 'tenho certeza', 'pode fazer')
        if any(kw in _cmd_lower for kw in _dangerous_keywords):
            if not any(cw in _cmd_lower for cw in _confirmation_words):
                self._answer_local(cmd_clean,
                    f"⚠️ Comando perigoso detectado: '{cmd_clean[:50]}'. "
                    f"Para confirmar, adicione 'confirmo' ou 'sim' na mensagem.")
                return

        # Clipboard context: auto-detect code/errors in clipboard
        try:
            if hasattr(self, 'clipboard_monitor') and self.clipboard_monitor:
                clip = self.clipboard_monitor.get_content()
                if clip and len(clip) > 10:
                    if self.clipboard_monitor.is_code(clip):
                        cmd_clean = f"[CLIPBOARD_CODE] {cmd_clean}\nClipboard contains code:\n{clip[:500]}"
                    elif self.clipboard_monitor.is_error(clip):
                        cmd_clean = f"[CLIPBOARD_ERROR] {cmd_clean}\nClipboard contains error:\n{clip[:500]}"
        except Exception:
            pass

        # SPEED: batch all pre-routing operations into one try block
        try:
            # Record user pattern for proactive suggestions
            action = "voice_command" if cmd_clean.startswith("[AUDIO]") else "text_command"
            self.persistent_memory.record_user_pattern(action, cmd_clean[:100])
            # Session memory
            self.session_mem.add_turn("user", cmd_clean)
            # Smart aliases — resolve shortcuts
            cmd_clean = self.smart_aliases.resolve(cmd_clean)
            # Smart reminders — detect and set
            self.smart_reminders.detect_reminder(cmd_clean) and self.smart_reminders.add_reminder(cmd_clean)
            # Mood tracking
            from core.persona import detect_user_mood
            mood = detect_user_mood(cmd_clean)
            self.mood_tracker.record_mood(mood.value, cmd_clean[:50])
            # Learn user preferences
            self.smart_defaults.learn_from_interaction(cmd_clean)
            # Detect user corrections — "não", "errado", "isso está errado"
            correction_markers = (
                "não é isso", "está errado", "errado", "isso está errado",
                "incorreto", "você errou", "não foi isso",
            )
            if any(m in cmd_clean.lower() for m in correction_markers):
                recent = self.persistent_memory.get_recent(category="conversation", limit=2)
                if recent:
                    last_ai = recent[0].content.split("AI: ")[-1][:200] if "AI: " in recent[0].content else ""
                    if last_ai:
                        self.persistent_memory.record_correction(
                            wrong_answer=last_ai, correct_answer=cmd_clean, topic=cmd_clean[:50])
        except Exception:
            pass

        # Multi-step compound commands — apenas quando TODAS as partes parecem
        # comandos de sistema reais; frases conversacionais com "depois"
        # (ex.: "o que acontece depois da morte?") seguem para o LLM.
        seps = [" e depois ", " depois ", " em seguida ", " e também ", " e tambem "]
        if any(sep in cmd_clean.lower() for sep in seps):
            parts = [p.strip(" ,.!?") for p in
                     re.split("|".join(map(re.escape, seps)), cmd_clean, flags=re.IGNORECASE)]
            parts = [p for p in parts if len(p) >= 3]
            if len(parts) >= 2 and all(IntentEngine.looks_like_action(p) for p in parts):
                response = self.autonomous.execute_complex_plan(cmd_clean, self._local_answer)
                if response:
                    self._answer_local(cmd_clean, response)
                    return

        response = self._local_answer(cmd_clean)
        if response is not None:
            self._answer_local(cmd_clean, response)
            return

        # Message Monitor control commands
        try:
            cmd_lower = cmd_clean.lower()
            if hasattr(self, 'message_monitor'):
                if any(k in cmd_lower for k in ('ativa auto reply', 'ativa auto-resposta', 'auto reply on')):
                    self.message_monitor.config.auto_reply_enabled = True
                    self._answer_local(cmd_clean, "Auto-reply ativado. Vou responder mensagens automaticamente.")
                    return
                if any(k in cmd_lower for k in ('desativa auto reply', 'desativa auto-resposta', 'auto reply off')):
                    self.message_monitor.config.auto_reply_enabled = False
                    self._answer_local(cmd_clean, "Auto-reply desativado. Não vou mais responder automaticamente.")
                    return
                if any(k in cmd_lower for k in ('status das mensagens', 'status mensagens', 'message status')):
                    stats = self.message_monitor.get_stats()
                    reply = (f"Monitor de mensagens:\n"
                             f"  Status: {'Ativo' if stats['running'] else 'Inativo'}\n"
                             f"  Auto-reply: {'Ligado' if stats['auto_reply_enabled'] else 'Desligado'}\n"
                             f"  Respostas esta hora: {stats['replies_this_hour']}/{stats['max_per_hour']}\n"
                             f"  Total de respostas: {stats['total_replies']}\n"
                             f"  Regras: {stats['rules_count']}\n"
                             f"  Contatos rastreados: {stats['contacts_tracked']}")
                    self._answer_local(cmd_clean, reply)
                    return
                if 'responda' in cmd_lower or 'responde pra' in cmd_lower or 'responde pro' in cmd_lower:
                    # Extract contact name and message
                    match = re.search(r'respond[ae]\s+(?:pra|pro|para)\s+(.+?)(?:\s+diz(?:endo)?\s+(.+))?$', cmd_lower)
                    if match:
                        contact = match.group(1).strip()
                        msg = match.group(2) or "Recebi, vou ver isso."
                        self.message_monitor.set_reply_to([contact])
                        self.message_monitor.config.auto_reply_enabled = True
                        self._answer_local(cmd_clean, f"Vou responder para {contact}: \"{msg}\"")
                        return
        except Exception:
            pass

        # SPEED: PC Controller — smart actions (open app, launch game, media, window)
        try:
            from modules.pc_controller import PCController
            pc_response = PCController.smart_action(cmd_clean)
            if pc_response:
                self._answer_local(cmd_clean, pc_response)
                return
        except ImportError:
            pass
        except Exception:
            pass

        self._answer_llm_stream(cmd_clean)

    # ---------------------------------------------------------- RPG mode

    # ---------------------------------------------------------- local path

    def _answer_local(self, cmd: str, response: str):
        self.signals.sig_sage_full.emit(response)
        event_bus.emit("response.local", {"cmd": cmd[:100], "resp_len": len(response)})

        # Track response in session memory
        try:
            self.session_mem.add_turn("assistant", response[:200])
            self.response_feedback.record_good_response(len(response))
            self.adaptive_length.record_response(len(response))
        except Exception:
            pass
        try:
            MemoryManager.archive_turn(cmd, response)
        except Exception:
            pass
        self.persistent_memory.add(
            "conversation",
            f"User: {cmd[:500]}\nAI: {response[:500]}",
            importance=0.6,
            tags=["conversation", "local"]
        )
        # Knowledge Graph: extract entities and relationships
        try:
            self.knowledge_graph.extract_and_store(cmd, response)
        except Exception:
            pass
        # Proactive: suggest next actions based on context
        try:
            suggestions = self.proactive.get_suggestions(cmd, response)
            if suggestions:
                self.session_mem.set_proactive_hints(suggestions)
        except Exception:
            pass
        # Speak response — but skip pure code blocks
        _skip_tts = ('```' in response and response.count('```') >= 2) or response.strip().startswith('import ')
        if not _skip_tts:
            self.speech.speak(response)
        self.signals.sig_state.emit("success")
        op = cmd[:60] if len(cmd) > 10 else "operacao"
        phrase = AmbianceEngine.on_task_complete(True, is_code=False, op=op)
        if phrase:
            self.speech.speak(phrase)

    # -------------------------------------------------------- streaming path

    def _answer_llm_stream(self, cmd: str):
        self.signals.sig_sage_begin.emit()
        event_bus.emit("llm.query", {"command": cmd[:200]})
        state.set("app_state", "thinking")

        # SPEED: parallel pre-computation — route + prompt + history simultaneously
        from core.request_router import RequestRouter
        from core.nine_router import NineRouterBridge

        # Build route and system prompt in parallel (both are CPU-bound)
        route = RequestRouter.analyze(
            cmd,
            recent_history=MemoryManager.get_recent_turns(limit=4),
        )

        # Determine task type for 9Router routing
        task_type = "chat"
        if route.kind.value in ("code", "debug"):
            task_type = "code"
        elif route.kind.value == "explain":
            task_type = "chat"
        elif route.complexity.value == "simple":
            task_type = "fast"

        # Get 9Router decision
        routing_decision = self.nine_router.router.route(task_type=task_type)
        self.log.info(f"9Router: {routing_decision.provider} ({routing_decision.model}) — {routing_decision.reason}")

        collected: list[str] = []
        full_response = [""]

        # SPEED: cache base prompt — only rebuild dynamic parts per request
        if not hasattr(self, '_cached_base_prompt') or not hasattr(self, '_cached_prompt_mood'):
            self._cached_base_prompt = ""
            self._cached_prompt_mood = None
        _current_mood = self.mood_tracker.get_mood_trend() if hasattr(self, 'mood_tracker') else "neutral"
        if self._cached_base_prompt and self._cached_prompt_mood == _current_mood:
            _base_prompt = self._cached_base_prompt
        else:
            _base_prompt = self.persona.get_system_prompt()
            self._cached_base_prompt = _base_prompt
            self._cached_prompt_mood = _current_mood

        # SPEED: pre-build full system prompt once (not per-yield)
        _full_system = _base_prompt
        try:
            corrections = self.persistent_memory.get_corrections_for_prompt(cmd)
            if corrections:
                _full_system += "\n\n" + corrections
        except Exception:
            pass
        try:
            session_ctx = self.session_mem.to_prompt_context()
            if session_ctx:
                _full_system += "\n\n" + session_ctx
        except Exception:
            pass
        try:
            defaults_ctx = self.smart_defaults.to_prompt_context()
            if defaults_ctx:
                _full_system += "\n\n" + defaults_ctx
        except Exception:
            pass
        _full_system += f"\n\nHumor: {_current_mood}"

        # Build conversation history for context
        _history = []
        try:
            recent = self.persistent_memory.get_recent(category="conversation", limit=10)
            for r in reversed(recent):
                content = r.content if hasattr(r, 'content') else str(r)
                if content.startswith("User: "):
                    _history.append({"role": "user", "content": content[6:]})
                elif content.startswith("AI: "):
                    _history.append({"role": "assistant", "content": content[4:]})
        except Exception:
            pass
        # Also add session memory turns
        try:
            if hasattr(self.session_mem, 'turns') and self.session_mem.turns:
                for turn in self.session_mem.turns[-8:]:
                    role = turn.get('role', 'user')
                    text = turn.get('content', '')
                    if role in ('user', 'assistant'):
                        _history.append({"role": role, "content": text})
        except Exception:
            pass
        # Current message
        _history.append({"role": "user", "content": cmd})

        # ═══ INTELLIGENCE ENGINE: enrich context dynamically ═══
        try:
            from core.intelligence_engine import IntelligenceEngine
            if not hasattr(self, '_intel_engine'):
                self._intel_engine = IntelligenceEngine()
            _full_system = self._intel_engine.enrich_context(
                _full_system, cmd, _history,
                self.session_mem.turns[-8:] if hasattr(self.session_mem, 'turns') else []
            )
        except Exception:
            pass

        def _tee():
            try:
                # Use 9Router for streaming with automatic fallback
                for delta in self.nine_router.route_and_stream(
                    _history,
                    system=_full_system,
                    task_type=task_type,
                    max_tokens=route.max_tokens,
                    temperature=0.65,
                    top_p=0.92,
                    frequency_penalty=0.05,
                    presence_penalty=0.08,
                ):
                    collected.append(delta)
                    self.signals.sig_sage_delta.emit(delta)
                    yield delta
            except Exception as e:
                self.log.error(f"LLM stream error: {e}")
            finally:
                full_response[0] = "".join(collected)
                try:
                    if full_response[0]:
                        MemoryManager.archive_turn(cmd, full_response[0])
                        self.persistent_memory.add(
                            "conversation",
                            f"User: {cmd[:500]}\nAI: {full_response[0][:500]}",
                            importance=0.6,
                            tags=["conversation", "llm"]
                        )
                        self.signals.sig_sage_full.emit(full_response[0])
                        state.set("app_state", "idle")
                        event_bus.emit("response.llm", {"cmd": cmd[:100], "resp_len": len(full_response[0])})
                        # Knowledge Graph: extract entities from LLM response
                        try:
                            self.knowledge_graph.extract_and_store(cmd, full_response[0])
                        except Exception:
                            pass
                        # Proactive suggestions
                        try:
                            suggestions = self.proactive.get_suggestions(cmd, full_response[0])
                            if suggestions:
                                self.session_mem.set_proactive_hints(suggestions)
                        except Exception:
                            pass
                except Exception:
                    pass
                self.signals.sig_sage_end.emit()
                # SPEED: record timing metrics
                try:
                    from core.speed_optimizer import get_speed_tracker
                    st = get_speed_tracker()
                    st.record("ttft", self.llm.last_ttft_ms or 0, self.llm.last_model)
                    if full_response[0]:
                        st.record("response_len", len(full_response[0]))
                except Exception:
                    pass
                self.signals.sig_telemetry.emit(
                    self.pipeline.last_stt_engine, self.pipeline.last_stt_ms,
                    self.llm.last_model, self.llm.last_ttft_ms)

        self.speech.speak_stream(_tee())

        # --- Auto-execute code blocks after stream finishes ---
        self._post_stream_execute(full_response[0])

    def _post_stream_execute(self, full_response: str):
        """Verifica se a resposta contém [EXECUTE] e roda o código com segurança."""
        try:
            from core.code_executor import CodeExecutor
            if not CodeExecutor.has_executable(full_response):
                return

            # Executa com verificações de segurança (requer aprovação para código perigoso)
            clean, results = CodeExecutor.extract_and_execute(full_response, require_approval=True)

            for r in results:
                if r.success:
                    self.log.info(f"Executor {r.language}: OK ({len(r.output)} chars)")
                else:
                    self.log.error(f"Executor {r.language}: ERRO - {r.error[:100]}")

            if results:
                summary_parts = []
                for r in results:
                    if r.success:
                        out = r.output.strip()[:500]
                        summary_parts.append(
                            f"Código {r.language} executado com sucesso. "
                            f"Resultado:\n{out}"
                        )
                    elif r.approved:
                        summary_parts.append(
                            f"Código {r.language} falhou: {r.error[:300]}"
                        )
                    else:
                        summary_parts.append(
                            f"Código {r.language} não executado: {r.error[:300]}"
                        )
                summary = "\n\n".join(summary_parts)

                all_success = all(r.success for r in results)
                langs = list(set(r.language for r in results))
                lang_str = langs[0] if langs else "codigo"
                phrase = AmbianceEngine.on_task_complete(
                    all_success, is_code=True, lang=lang_str,
                )
                if phrase:
                    summary = f"{summary}\n\n{phrase}"

                def _exec_stream():
                    yield f"\n{summary}"
                self.speech.speak_stream(_exec_stream())
                self.signals.sig_sage_full.emit(summary)
        except Exception as e:
            self.log.error(f"Executor error: {e}")

    def _local_answer(self, cmd_clean: str) -> str | None:
        cmd_lower = cmd_clean.lower()

        intent_action, params = IntentEngine.match_intent(cmd_clean)
        # NOTE: removed extract_intent_with_llm fallback — it misclassifies
        # conversational queries as system commands, returning wrong answers.
        # Only rule-based match_intent is used for local routing.

        # --- Ações seguras (leitura/informação) ---
        if intent_action == "clean_recycle_bin":
            return HardwareController.clean_recycle_bin()
        if intent_action == "boost_ram":
            return HardwareController.boost_system_memory()
        if intent_action == "organize_desktop":
            return HardwareController.organize_desktop_files()
        if intent_action == "clean_temp_files":
            return HardwareController.clean_temp_files()
        if intent_action == "get_ip_info":
            return HardwareController.get_ip_info()
        if intent_action == "get_disk_info":
            return HardwareController.get_disk_info()
        if intent_action == "take_screenshot":
            return HardwareController.take_screenshot()
        if intent_action == "get_active_window":
            return HardwareController.get_active_window_title()
        if intent_action == "list_notes":
            return ProductivityModule.list_notes()
        if intent_action == "get_datetime":
            return ProductivityModule.get_current_datetime()
        if intent_action == "show_history":
            return MemoryManager.get_full_history_report()
        if intent_action == "show_memory":
            return MemoryManager.get_memory_context()
        if intent_action == "self_program":
            self.signals.sig_self_improve.emit(params.get("target", ""), "auto")
            return ("Protocolo de auto-melhoria iniciado. O Elívea está "
                    "analisando e melhorando seus próprios arquivos, Mestre.")
        if intent_action == "kill_process":
            return HardwareController.kill_process(params.get("target", ""))
        if intent_action == "open_app":
            target = params.get("target", "")
            # Rate limit: max 1 app launch per 2 seconds
            now = time.time()
            if not hasattr(self, '_last_app_launch'):
                self._last_app_launch = 0
            if now - self._last_app_launch < 2:
                return f"Aviso. Aguardando cooldown para abrir {target}."
            self._last_app_launch = now

            if "open_app" in self.mark_l_tools:
                try:
                    res = self.mark_l_tools["open_app"](
                        parameters={"app_name": target}, response=None, player=None)
                    if res:
                        return res
                except Exception:
                    pass
            import os
            os.system(f"start {target}")
            return f"Aviso. Abrindo {target} para o Mestre."
        if intent_action == "save_note":
            return ProductivityModule.save_note(params.get("text", ""))
        if intent_action == "web_search":
            return AutomationModule.google_search_or_youtube(params.get("query", ""), mode="google")
        if intent_action == "play_youtube":
            return AutomationModule.google_search_or_youtube(params.get("query", ""), mode="youtube")
        if intent_action == "read_file":
            return FileModule.read_file(params.get("path", ""))
        if intent_action == "create_folder":
            return FileModule.create_folder(params.get("folder", ""))
        if intent_action == "list_files":
            return SuperUser.list_dir(params.get("target", "."))
        if intent_action == "search_files":
            return SuperUser.search_files(params.get("target", ""))
        if intent_action == "list_processes":
            return SuperUser.list_processes()
        if intent_action == "list_services":
            return SuperUser.service_list()
        if intent_action == "wifi_list":
            return SuperUser.wifi_list()
        if intent_action == "set_volume":
            try:
                return SuperUser.set_volume(int(params.get("target", "50")))
            except ValueError:
                return SuperUser.set_volume(50)
        if intent_action == "system_info":
            return SuperUser.get_system_info()

        # --- Download & Instalação ---
        if intent_action == "download_file":
            url = params.get("target", "") or params.get("query", "")
            if url:
                return SuperUser.download_file(url)
            return "Forneça a URL para download."
        if intent_action == "install_app":
            target = params.get("target", "") or params.get("query", "")
            if target:
                if target.startswith("http"):
                    return SuperUser.download_and_install(target)
                return SuperUser.winget_install(target)
            return "Forneça o nome do programa ou URL para instalar."
        if intent_action == "uninstall_app":
            target = params.get("target", "") or params.get("query", "")
            if target:
                return SuperUser.winget_uninstall(target)
            return "Forneça o nome do programa para desinstalar."
        if intent_action == "run_command":
            cmd = params.get("target", "") or params.get("query", "")
            if cmd:
                return SuperUser.run_cmd(cmd)
            return "Forneça o comando para executar."
        if intent_action == "copy_file":
            target = params.get("target", "")
            if target:
                parts = target.split(None, 1)
                if len(parts) == 2:
                    return SuperUser.copy(parts[0], parts[1])
            return "Forneça origem e destino."
        if intent_action == "move_file":
            target = params.get("target", "")
            if target:
                parts = target.split(None, 1)
                if len(parts) == 2:
                    return SuperUser.move(parts[0], parts[1])
            return "Forneça origem e destino."
        if intent_action == "delete_file_admin":
            target = params.get("target", "") or params.get("query", "")
            if target:
                return SuperUser.delete(target)
            return "Forneça o caminho para deletar."
        if intent_action == "list_processes":
            return SuperUser.list_processes()
        if intent_action == "kill_process_admin":
            target = params.get("target", "")
            if target:
                return SuperUser.kill_process(target)
            return "Forneça o nome ou PID do processo."
        if intent_action == "list_services":
            return SuperUser.service_list()
        if intent_action == "wifi_list":
            return SuperUser.wifi_list()
        if intent_action == "wifi_connect":
            ssid = params.get("target", "")
            if ssid:
                return SuperUser.wifi_connect(ssid)
            return "Forneça o nome da rede WiFi."
        if intent_action == "set_ip":
            target = params.get("target", "")
            if target:
                parts = target.split()
                if len(parts) >= 2:
                    return SuperUser.set_static_ip(parts[0], parts[1], parts[2] if len(parts) > 2 else "192.168.1.1")
            return "Forneça interface IP gateway."
        if intent_action == "shutdown_pc":
            # SAFETY: always require confirmation, always 30s delay
            if not SecurityGuard.require_confirmation("shutdown", "Desligar o PC em 30 segundos. Tem certeza?"):
                return "Desligamento cancelado pelo Mestre."
            SecurityGuard.audit("shutdown", "user_confirmed")
            return SuperUser.shutdown(30)
        if intent_action == "restart_pc":
            # SAFETY: always require confirmation, always 30s delay
            if not SecurityGuard.require_confirmation("restart", "Reiniciar o PC em 30 segundos. Tem certeza?"):
                return "Reinicialização cancelada pelo Mestre."
            SecurityGuard.audit("restart", "user_confirmed")
            return SuperUser.restart(30)
        if intent_action == "lock_pc":
            return SuperUser.lock_pc()
        if intent_action == "set_volume":
            try:
                return SuperUser.set_volume(int(params.get("target", "50")))
            except ValueError:
                return SuperUser.set_volume(50)

        # --- Navegador ---
        if intent_action == "browser_open":
            target = params.get("target", "") or params.get("query", "")
            if target and (target.startswith("http") or "." in target):
                return BrowserAgent.open(target)
            return BrowserAgent.open()
        if intent_action == "browser_search":
            query = params.get("target", "") or params.get("query", "")
            if query:
                return BrowserAgent.search_google(query)
            return BrowserAgent.search_google(params.get("text", ""))
        if intent_action == "browser_youtube":
            query = params.get("target", "") or params.get("query", "")
            if query:
                return BrowserAgent.search_youtube(query)
            return "Forneça o que pesquisar no YouTube."
        if intent_action == "browser_click":
            target = params.get("target", "") or params.get("text", "")
            if target:
                return BrowserAgent.click(target)
            return "Forneça o elemento para clicar."
        if intent_action == "browser_type":
            target = params.get("target", "")
            text = params.get("text", "")
            if target and text:
                return BrowserAgent.type_in(target, text)
            return "Forneça o campo e o texto."
        if intent_action == "browser_text":
            return BrowserAgent.get_text()
        if intent_action == "browser_screenshot":
            return BrowserAgent.screenshot()
        if intent_action == "browser_scroll":
            return BrowserAgent.scroll_down()
        if intent_action == "browser_close":
            return BrowserAgent.close()
        if intent_action == "browser_back":
            return BrowserAgent.back()

        # --- Analise de imagem, video e links ---
        if intent_action == "analyze_image":
            path = params.get("target", "")
            if path:
                try:
                    result = image_analyzer.analyze_image(path)
                    description = result.description if result else ""
                except Exception as e:
                    self.log.debug(f"Erro ao analisar imagem: {type(e).__name__}: {e}")
                    description = ""
                return description or "Nao foi possivel analisar a imagem."
            # Try clipboard
            result = image_analyzer.analyze_clipboard()
            if result:
                return result.description
            return "Nenhuma imagem encontrada para analise."

        if intent_action == "analyze_screenshot":
            try:
                result = image_analyzer.analyze_screenshot()
                description = result.description if result else ""
            except Exception as e:
                self.log.debug(f"Erro ao analisar screenshot: {type(e).__name__}: {e}")
                description = ""
            return description or "Nao foi possivel capturar ou analisar a tela."

        if intent_action == "analyze_video":
            path = params.get("target", "")
            if path:
                result = video_analyzer.analyze_video(path)
                return result.summary or "Nao foi possivel analisar o video."
            return "Forneça o caminho do video para analise."

        if intent_action == "analyze_link":
            url = params.get("target", "")
            if not url:
                # Try to extract URL from command
                import re as _re
                urls = _re.findall(r'https?://[^\s]+', cmd_clean)
                url = urls[0] if urls else ""
            if url:
                result = link_analyzer.analyze_url(url)
                if result.error:
                    return f"Erro ao analisar link: {result.error}"
                return result.summary or "Nao foi possivel analisar o link."
            return "Forneça um link para analise."

        if intent_action == "extract_links":
            url = params.get("target", "")
            if url:
                links = link_analyzer.extract_links(url)
                if not links:
                    return "Nenhum link encontrado na pagina."
                lines = [f"Links encontrados ({len(links)}):"]
                for l in links[:20]:
                    lines.append(f" - {l['url']}")
                return "\n".join(lines)
            return "Forneça uma URL para extrair links."

        # Detectar URLs diretamente no comando
        if link_analyzer.is_url(cmd_clean):
            result = link_analyzer.analyze_url(cmd_clean)
            if result.error:
                return f"Erro: {result.error}"
            return result.summary or "Analise concluida."

        # --- Broad regex fallback patterns (superuser admin commands) ---
        # Guard: only match if message looks like a command (short, imperative)
        _is_cmd = len(cmd_clean) < 80 and not any(q in cmd_lower for q in ('?', 'como', 'por que', 'porque', 'o que', 'qual', 'quem', 'onde', 'quando', 'me explica', 'me fale', 'conte', 'explica'))

        if intent_action == "install_app":
            if not SecurityGuard.require_confirmation("install", params.get("target", "")):
                return "Aviso. Instalação cancelada pelo Mestre."
            return SuperUser.winget_install(params.get("target", ""))
        if intent_action == "uninstall_app":
            if not SecurityGuard.require_confirmation("uninstall", params.get("target", "")):
                return "Aviso. Desinstalação cancelada pelo Mestre."
            return SuperUser.winget_uninstall(params.get("target", ""))
        if intent_action == "run_command":
            if not SecurityGuard.require_confirmation("run_cmd", params.get("target", "")):
                return "Aviso. Execução cancelada pelo Mestre."
            return SuperUser.run_cmd(params.get("target", ""), admin=False)
        if intent_action == "kill_process_admin":
            if not SecurityGuard.require_confirmation("kill_process", params.get("target", "")):
                return "Aviso. Finalização cancelada pelo Mestre."
            return SuperUser.kill_process(params.get("target", ""))
        if intent_action == "wifi_connect":
            if not SecurityGuard.require_confirmation("wifi_connect", params.get("target", "")):
                return "Aviso. Conexão WiFi cancelada pelo Mestre."
            return SuperUser.wifi_connect(params.get("target", ""))

        # --- Ações DESTRUTIVAS (precisam confirmação + audit) ---
        if intent_action == "shutdown_pc":
            if not SecurityGuard.require_confirmation("shutdown", "Desligar o PC em 10 segundos"):
                return "Aviso. Desligamento cancelado pelo Mestre."
            SecurityGuard.audit("shutdown", "user_confirmed")
            return SuperUser.shutdown(10)
        if intent_action == "restart_pc":
            if not SecurityGuard.require_confirmation("restart", "Reiniciar o PC em 10 segundos"):
                return "Aviso. Reinicialização cancelada pelo Mestre."
            SecurityGuard.audit("restart", "user_confirmed")
            return SuperUser.restart(10)
        if intent_action == "lock_pc":
            return SuperUser.lock_pc()
        if intent_action == "download_file":
            url = params.get("target", "")
            is_safe, reason = SecurityGuard.check_url(url)
            if not is_safe:
                return f"Aviso. Download bloqueado: {reason}"
            if not SecurityGuard.require_confirmation("download", url):
                return "Aviso. Download cancelado pelo Mestre."
            return SuperUser.download_file(url)

        # ===================================================== SUPERUSER (admin total)
        # Comandos de administração total do PC — voz ou texto
        # Guard: skip broad regex patterns if message looks like a question
        if not _is_cmd:
            return None  # let LLM handle conversational queries

        # --- downloads e instalação (COM CONFIRMAÇÃO)
        if re.search(r'\b(baixar|download|pegar|puxar)\b', cmd_lower):
            url_m = re.search(r'(https?://\S+)', cmd_clean)
            if url_m:
                url = url_m.group(1)
                is_safe, reason = SecurityGuard.check_url(url)
                if not is_safe:
                    return f"Aviso. Download bloqueado: {reason}"
                if not SecurityGuard.require_confirmation("download", url):
                    return "Aviso. Download cancelado pelo Mestre."
                return SuperUser.download_file(url)
            # "baixar/notepad++" ou "instalar discord" → winget
            pkg = re.sub(r'^(baixar|download|pegar|puxar|instalar?|instale)\s+', '', cmd_clean).strip()
            if pkg:
                if not SecurityGuard.require_confirmation("install", pkg):
                    return "Aviso. Instalação cancelada pelo Mestre."
                return SuperUser.winget_install(pkg)
            return "Mestre, especifique o que baixar (URL ou nome do programa)."

        if re.search(r'\b(instalar?|instale|colocar|adicione)\b', cmd_lower) and \
                not re.search(r'\b(pacote|python|pip|npm)\b', cmd_lower):
            pkg = re.sub(r'^(instalar?|instale|colocar|adicione)\s+(o |a |no |na )?\s*', '', cmd_clean).strip()
            if pkg:
                if not SecurityGuard.require_confirmation("install", pkg):
                    return "Aviso. Instalação cancelada pelo Mestre."
                return SuperUser.winget_install(pkg)

        if re.search(r'\b(desinstalar?|desinstale|remover|remova)\b', cmd_lower):
            pkg = re.sub(r'^(desinstalar?|desinstale|remover|remova)\s+(o |a |o |a )?\s*', '', cmd_clean).strip()
            if pkg:
                if not SecurityGuard.require_confirmation("uninstall", pkg):
                    return "Aviso. Desinstalação cancelada pelo Mestre."
                return SuperUser.winget_uninstall(pkg)

        if re.search(r'\b(atualizar?|atualize|upgrade)\b', cmd_lower):
            pkg = re.sub(r'^(atualizar?|atualize|upgrade)\s+(o |a )?\s*', '', cmd_clean).strip()
            if not SecurityGuard.require_confirmation("upgrade", pkg or "todos"):
                return "Aviso. Atualização cancelada pelo Mestre."
            return SuperUser.winget_upgrade(pkg or None)

        if "pip install" in cmd_lower or "instalar pacote" in cmd_lower:
            pkg = re.sub(r'.*?(pip install|instalar pacote)\s*', '', cmd_clean).strip()
            if not pkg:
                return "Especifique o pacote pip."
            if not SecurityGuard.require_confirmation("pip_install", pkg):
                return "Aviso. Instalação pip cancelada pelo Mestre."
            return SuperUser.pip_install(pkg)

        # --- comandos diretos (COM CONFIRMAÇÃO)
        if cmd_lower.startswith("cmd ") or cmd_lower.startswith("execute "):
            command = re.sub(r'^(cmd|execute)\s+', '', cmd_clean).strip()
            if not command:
                return "Especifique o comando."
            is_allowed, reason = SecurityGuard.check_command(command)
            if not is_allowed:
                return f"Aviso. Comando bloqueado: {reason}"
            if not SecurityGuard.require_confirmation("run_cmd", command):
                return "Aviso. Execução cancelada pelo Mestre."
            return SuperUser.run_cmd(command, admin=False)

        if cmd_lower.startswith("powershell ") or cmd_lower.startswith("ps "):
            command = re.sub(r'^(powershell|ps)\s+', '', cmd_clean).strip()
            if not command:
                return "Especifique o comando PS."
            is_allowed, reason = SecurityGuard.check_command(command)
            if not is_allowed:
                return f"Aviso. Comando bloqueado: {reason}"
            if not SecurityGuard.require_confirmation("run_powershell", command):
                return "Aviso. Execução PowerShell cancelada pelo Mestre."
            return SuperUser.run_powershell(command)

        if cmd_lower.startswith("python ") or cmd_lower.startswith("py "):
            code = re.sub(r'^(python|py)\s+', '', cmd_clean).strip()
            if not code:
                return "Especifique o código Python."
            from core.security import SandBox
            is_safe, warnings = SandBox.scan_code(code)
            if not is_safe:
                if not SecurityGuard.require_confirmation("run_python", f"Código com {len(warnings)} avisos"):
                    return "Aviso. Execução Python cancelada pelo Mestre."
            return SuperUser.run_python(code)

        # --- arquivos (COM CONFIRMAÇÃO para delete/move)
        if re.search(r'\b(copiar|copie|copy)\b', cmd_lower):
            parts = cmd_clean.split()
            if len(parts) >= 3:
                if not SecurityGuard.require_confirmation("copy", f"{parts[1]} → {parts[2]}"):
                    return "Aviso. Cópia cancelada pelo Mestre."
                return SuperUser.copy(parts[1], parts[2])
            return "Uso: copiar <origem> <destino>"

        if re.search(r'\b(mover|mova|move)\b', cmd_lower) and \
                not re.search(r'\b(mouse|mover o mouse)\b', cmd_lower):
            parts = cmd_clean.split()
            if len(parts) >= 3:
                is_safe, reason = SecurityGuard.check_path(parts[1], "move")
                if not is_safe:
                    return f"Aviso. {reason}"
                if not SecurityGuard.require_confirmation("move", f"{parts[1]} → {parts[2]}"):
                    return "Aviso. Movimentação cancelada pelo Mestre."
                return SuperUser.move(parts[1], parts[2])
            return "Uso: mover <origem> <destino>"

        if re.search(r'\b(deletar|delete|apagar|apague|excluir|exclua)\b', cmd_lower):
            path = re.sub(r'^(deletar|delete|apagar|apague|excluir|exclua)\s+(o |a |arquivo |pasta )?\s*', '', cmd_clean).strip()
            if not path:
                return "Especifique o que deletar."
            is_safe, reason = SecurityGuard.check_path(path, "delete")
            if not is_safe:
                return f"Aviso. {reason}"
            if not SecurityGuard.require_confirmation("delete", path):
                return "Aviso. Exclusão cancelada pelo Mestre."
            SecurityGuard.audit("delete", path)
            return SuperUser.delete(path)

        if re.search(r'\b(buscar arquivo|procurar arquivo|search file)\b', cmd_lower):
            query = re.sub(r'.*?(buscar arquivo|procurar arquivo|search file)\s*', '', cmd_clean).strip()
            return SuperUser.search_files(query) if query else "Especifique o que buscar."

        # --- processos
        if re.search(r'\b(processos?|tasklist|tarefas ativas)\b', cmd_lower) and \
                not re.search(r'\b(agendad|scheduler)\b', cmd_lower):
            filtro = re.sub(r'.*?(processos?|tasklist|tarefas ativas)\s*', '', cmd_clean).strip() or None
            return SuperUser.list_processes(filtro)

        if re.search(r'\b(matar|mate|encerrar|encerre|finalizar|finalise)\b', cmd_lower):
            target = re.sub(r'^(matar|mate|encerrar|encerre|finalizar|finalise)\s+(o |a )?\s*', '', cmd_clean).strip()
            return SuperUser.kill_process(target) if target else "Especifique o processo."

        # --- serviços
        if re.search(r'\b(serviços?|services?)\b', cmd_lower) and \
                not re.search(r'\b(iniciar|parar|start|stop)\b', cmd_lower):
            filtro = re.sub(r'.*?(serviços?|services?)\s*', '', cmd_clean).strip() or None
            return SuperUser.service_list(filtro)

        if re.search(r'\b(iniciar serviço|start service)\b', cmd_lower):
            name = re.sub(r'.*?(iniciar serviço|start service)\s*', '', cmd_clean).strip()
            return SuperUser.service_start(name) if name else "Especifique o serviço."

        if re.search(r'\b(parar serviço|stop service)\b', cmd_lower):
            name = re.sub(r'.*?(parar serviço|stop service)\s*', '', cmd_clean).strip()
            return SuperUser.service_stop(name) if name else "Especifique o serviço."

        # --- rede
        if re.search(r'\b(wifi|wi-fi|redes?)\b', cmd_lower) and \
                re.search(r'\b(listar|ver|mostrar|disponível|disponiveis)\b', cmd_lower):
            return SuperUser.wifi_list()

        if re.search(r'\b(conectar|connect)\b', cmd_lower) and re.search(r'\b(wifi|wi-fi)\b', cmd_lower):
            ssid = re.sub(r'.*?(conectar|connect)\s+(ao |na |no )?\s*(wifi|wi-fi)\s*', '', cmd_clean).strip()
            if not ssid:
                return "Especifique a rede WiFi."
            if not SecurityGuard.require_confirmation("wifi_connect", ssid):
                return "Aviso. Conexão WiFi cancelada pelo Mestre."
            return SuperUser.wifi_connect(ssid)

        if "meu ip" in cmd_lower or cmd_lower in ("ip", "rede"):
            return HardwareController.get_ip_info()

        if re.search(r'\b(flush dns|limpar dns|limpar cache dns)\b', cmd_lower):
            return SuperUser.flush_dns()

        if cmd_lower.startswith("ping "):
            host = cmd_clean.split(maxsplit=1)[-1]
            return SuperUser.ping(host)

        if re.search(r'\b(conexões|netstat|portas abertas)\b', cmd_lower):
            return SuperUser.netstat()

        # --- controle do PC (COM CONFIRMAÇÃO para ações destrutivas)
        if re.search(r'\b(desligar|desligue|shutdown|desligar o pc)\b', cmd_lower):
            if not SecurityGuard.require_confirmation("shutdown", "Desligar o PC em 10 segundos"):
                return "Aviso. Desligamento cancelado pelo Mestre."
            SecurityGuard.audit("shutdown", "user_confirmed")
            return SuperUser.shutdown(10)

        if re.search(r'\b(reiniciar|reinicie|restart|reboot)\b', cmd_lower):
            if not SecurityGuard.require_confirmation("restart", "Reiniciar o PC em 10 segundos"):
                return "Aviso. Reinicialização cancelada pelo Mestre."
            SecurityGuard.audit("restart", "user_confirmed")
            return SuperUser.restart(10)

        if re.search(r'\b(cancelar desligamento|cancel shutdown|abortar)\b', cmd_lower):
            return SuperUser.cancel_shutdown()

        if re.search(r'\b(bloquear|bloqueie|lock|travar)\b', cmd_lower):
            return SuperUser.lock_pc()

        if re.search(r'\b(volume|som|áudio)\b', cmd_lower):
            vol_m = re.search(r'(\d+)', cmd_clean)
            if vol_m:
                return SuperUser.set_volume(int(vol_m.group(1)))
            return SuperUser.set_volume(50)

        if re.search(r'\b(info do pc|informações do sistema|system info|sobre o pc)\b', cmd_lower):
            return SuperUser.get_system_info()

        if re.search(r'\b(bateria|battery)\b', cmd_lower):
            return SuperUser.get_battery()

        # --- tarefas agendadas (COM CONFIRMAÇÃO)
        if re.search(r'\b(tarefas agendadas|scheduled tasks|agendar)\b', cmd_lower):
            if re.search(r'\b(listar|ver|mostrar)\b', cmd_lower):
                return SuperUser.list_tasks()
            # "agendar tarefa nome comando"
            parts = cmd_clean.split(maxsplit=3)
            if len(parts) >= 4:
                if not SecurityGuard.require_confirmation("schedule_task", f"{parts[2]}: {parts[3]}"):
                    return "Aviso. Agendamento cancelado pelo Mestre."
                SecurityGuard.audit("schedule_task", f"{parts[2]}: {parts[3]}")
                return SuperUser.schedule_task(parts[2], parts[3])
            return SuperUser.list_tasks()

        # --- ambiente (COM CONFIRMAÇÃO)
        if cmd_lower.startswith("env ") or cmd_lower.startswith("variável ") or cmd_lower.startswith("variavel "):
            parts = cmd_clean.split(maxsplit=2)
            if len(parts) >= 3:
                if not SecurityGuard.require_confirmation("env_set", f"{parts[1]}={parts[2]}"):
                    return "Aviso. Variável de ambiente não alterada."
                SecurityGuard.audit("env_set", f"{parts[1]}={parts[2]}")
                return SuperUser.set_env(parts[1], parts[2])
            elif len(parts) == 2:
                return SuperUser.get_env(parts[1])
            return "Uso: env <nome> [valor]"

        # --- registro
        if re.search(r'\b(registro|registry)\b', cmd_lower):
            return "Registro Windows disponível via cmd: reg read/write. Use 'cmd reg ...'"

        # --- firewall (COM CONFIRMAÇÃO)
        if re.search(r'\b(firewall|fire wall)\b', cmd_lower):
            port_m = re.search(r'(\d+)', cmd_clean)
            if port_m and re.search(r'\b(abrir|liberar|permitir|allow|add)\b', cmd_lower):
                port = int(port_m.group(1))
                if not SecurityGuard.require_confirmation("firewall", f"Abrir porta {port}"):
                    return "Aviso. Regra de firewall não adicionada."
                SecurityGuard.audit("firewall_add", f"port={port}")
                return SuperUser.firewall_add_rule(f"rule_{port}", port)
            return SuperUser.capabilities()[:500]

        # ------- keyword/regex intents (same as before, voice-friendly) ----
        if "meu historico" in cmd_lower or "historico completo" in cmd_lower or "ver historico" in cmd_lower:
            return MemoryManager.get_full_history_report()

        if "minha memoria" in cmd_lower or "o que voce lembra" in cmd_lower or "fatos lembrados" in cmd_lower:
            return MemoryManager.get_memory_context() or "Aviso. Nenhuma memória salva anteriormente, Mestre."

        if cmd_lower.startswith("lembrar ") or cmd_lower.startswith("gravar memoria "):
            parts = re.sub(r'^(lembrar|gravar memoria)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            if "=" in parts:
                k, v = parts.split("=", 1)
                return MemoryManager.remember_fact(k, v)
            return "Aviso. Formato para gravar memória: lembrar, chave, igual, valor."

        if re.search(r"\bque horas (sao|são)\b", cmd_lower) or re.search(r"\bque dia (e|é) hoje\b", cmd_lower) \
                or "data e hora" in cmd_lower or "horario atual" in cmd_lower \
                or cmd_lower in ("hora", "data", "que horas sao", "que horas são", "me diga as horas"):
            return ProductivityModule.get_current_datetime()

        if cmd_lower.startswith("anotar ") or cmd_lower.startswith("salvar nota "):
            note_str = re.sub(r'^(anotar|salvar nota)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return ProductivityModule.save_note(note_str) if note_str else "Aviso. Especifique o texto da nota, Mestre."

        if "minhas notas" in cmd_lower or "listar notas" in cmd_lower or "ver notas" in cmd_lower:
            return ProductivityModule.list_notes()

        if re.search(r'(lembre|lembrar|agendar|lembrete)', cmd_lower) and \
                ("minuto" in cmd_lower or "hora" in cmd_lower or " em " in cmd_lower):
            m = re.search(r'(\d+)\s*(minuto|minutos|min)', cmd_lower)
            min_val = float(m.group(1)) if m else 5.0
            msg_val = re.sub(r'.*?(minutos|minuto|min)\s*(de|para|que)?\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return ProductivityModule.set_timer_reminder(
                min_val, msg_val or "Lembrete do Elívea", callback_speak=self.speech.speak)

        if "limpar temp" in cmd_lower or "arquivos temporarios" in cmd_lower or "temporários" in cmd_lower:
            return HardwareController.clean_temp_files()

        if any(w in cmd_lower for w in ["capturar tela", "print da tela", "screenshot", "tirar print"]):
            return HardwareController.take_screenshot()

        if any(w in cmd_lower for w in ["pausar musica", "proxima musica", "música anterior", "mutar som", "play musica"]):
            return HardwareController.media_control(cmd_lower)

        if "janela ativa" in cmd_lower or "janela em foco" in cmd_lower:
            return HardwareController.get_active_window_title()

        if re.search(r'(lixeira|recycle)', cmd_lower) and re.search(r'(limp|esvaz|apag)', cmd_lower):
            return HardwareController.clean_recycle_bin()

        if re.search(r'(ram|memoria|memória)', cmd_lower) and re.search(r'(otimiz|liber|limp)', cmd_lower):
            return HardwareController.boost_system_memory()

        if re.search(r'(desktop|trabalho|área de trabalho|area de trabalho)', cmd_lower) and re.search(r'(organiz|arrum)', cmd_lower):
            return HardwareController.organize_desktop_files()

        if "meu ip" in cmd_lower or "ip da rede" in cmd_lower or "qual meu ip" in cmd_lower or cmd_lower in ("ip", "rede"):
            return HardwareController.get_ip_info()

        if any(w in cmd_lower for w in [
                "meus discos", "meu disco", "espaco no disco", "espaço no disco",
                "espaco em disco", "espaço em disco", "espaco livre", "espaço livre",
                "armazenamento do pc", "armazenamento do computador", "meu armazenamento",
                "tamanho do disco", "uso do disco", "quanto espaco", "quanto espaço",
                "espaco de armazenamento", "espaço de armazenamento"]):
            return HardwareController.get_disk_info()

        if "limpar historico" in cmd_lower or "limpar conversa" in cmd_lower or "esquecer conversa" in cmd_lower:
            return self.llm.clear_history()

        if cmd_lower in ("sys", "status", "telemetria", "status do sistema", "sistema"):
            return SystemModule.get_status_report()

        if cmd_lower in ("help", "ajuda"):
            return ("Diretivas do Elívea, Mestre. "
                    "Status, meu ip, meus discos para telemetria. "
                    "Otimizar ram, limpar lixeira, organizar desktop, limpar temporários. "
                    "Abrir ou fechar aplicativo. Capturar tela. Anotar texto. "
                    "Lembrar, chave, igual, valor para memória. "
                    "Google ou Youtube mais termo para pesquisar/tocar. "
                    "Programar mais tarefa para codificar. "
                    "Baixar + URL para download. Instalar + nome para instalar. "
                    "Desinstalar + nome. Cmd + comando para executar qualquer coisa. "
                    "Wifi listar, conectar. Ping, meu ip, netstat. "
                    "Desligar, reiniciar, bloquear o PC. Volume 0 a 100. "
                    "Processos, serviços, tarefas agendadas. "
                    "Tudo que você pedir eu faço, Mestre.")

        if any(cmd_lower.startswith(w) for w in ["fechar ", "feche ", "encerrar ", "encerre ", "kill "]):
            app_target = re.sub(r'^(fechar|feche|encerrar|encerre|kill)\s+(o|a)?\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            if not app_target:
                return "Aviso. Especifique o aplicativo para fechar, Mestre."
            if not SecurityGuard.require_confirmation("kill_process", app_target):
                return "Aviso. Finalização cancelada pelo Mestre."
            return HardwareController.kill_process(app_target)

        if any(cmd_lower.startswith(w) for w in ["abrir ", "abra ", "iniciar ", "inicie "]):
            app_target = re.sub(r'^(abrir|abra|iniciar|inicie)\s+(o|a)?\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            if not app_target:
                return "Aviso. Especifique o aplicativo para abrir, Mestre."
            if "open_app" in self.mark_l_tools:
                try:
                    res = self.mark_l_tools["open_app"](
                        parameters={"app_name": app_target}, response=None, player=None)
                    if res:
                        return res
                except Exception:
                    pass
            import os
            # Rate limit: max 1 app launch per 2 seconds
            import time
            if not hasattr(self, '_last_app_launch'):
                self._last_app_launch = 0
            if time.time() - self._last_app_launch < 2:
                return f"Aviso. Aguardando cooldown para abrir {app_target}."
            self._last_app_launch = time.time()
            os.system(f"start {app_target}")
            return f"Aviso. Abrindo {app_target} para o Mestre."

        if cmd_lower.startswith("ler arquivo ") or cmd_lower.startswith("leia o arquivo "):
            path_part = re.sub(r'^(ler arquivo|leia o arquivo)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return FileModule.read_file(path_part) if path_part else "Aviso. Especifique o caminho do arquivo, Mestre."

        if cmd_lower.startswith("criar pasta ") or cmd_lower.startswith("crie a pasta "):
            folder_part = re.sub(r'^(criar pasta|crie a pasta)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return FileModule.create_folder(folder_part) if folder_part else "Aviso. Especifique o nome da pasta, Mestre."

        if "volume" in cmd_lower:
            nums = re.findall(r"\d+", cmd_clean)
            vol_verbs = ("aument", "diminu", "abaix", "suba", "subir", "coloque",
                         "colocar", "mude", "mudar", "defina", "definir", "ajust", "ponha")
            has_verb = any(v in cmd_lower for v in vol_verbs)
            if nums and (has_verb or cmd_lower.strip().startswith("volume")):
                return HardwareController.set_system_volume(int(nums[0]))
            if has_verb or cmd_lower.strip() in ("volume", "o volume", "mutar", "mudo"):
                return "Aviso. Diga o nível de volume de zero a cem, Mestre."
            # menção conversacional a volume (ex.: volume de uma esfera) → LLM

        if "bloquear pc" in cmd_lower or "bloqueie o pc" in cmd_lower:
            return SuperUser.lock_pc()
        if "reiniciar pc" in cmd_lower or "reinicie o pc" in cmd_lower:
            if not SecurityGuard.require_confirmation("restart", "Reiniciar o PC"):
                return "Aviso. Reinicialização cancelada pelo Mestre."
            SecurityGuard.audit("restart", "user_confirmed")
            return SuperUser.restart(0)
        if "desligar pc" in cmd_lower or "desligue o pc" in cmd_lower:
            if not SecurityGuard.require_confirmation("shutdown", "Desligar o PC"):
                return "Aviso. Desligamento cancelado pelo Mestre."
            SecurityGuard.audit("shutdown", "user_confirmed")
            return SuperUser.shutdown(0)

        if cmd_lower.startswith("exec ") or cmd_lower.startswith("rodar ") or cmd_lower.startswith("executar python "):
            code_body = re.sub(r'^(exec|rodar|executar python)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return CoderAgentModule.run_python_code(code_body)

        if cmd_lower.startswith("analyze ") or cmd_lower.startswith("analisar "):
            code_body = cmd_clean.split(maxsplit=1)[1]
            return CoderAgentModule.analyze_python_syntax(code_body)

        if cmd_lower.startswith("set-key groq ") or cmd_lower.startswith("groq-key "):
            key_part = cmd_clean.split(maxsplit=2)[-1]
            return self.llm.save_groq_key(key_part)

        if cmd_lower.startswith("jogar ") or cmd_lower.startswith("abrir jogo "):
            game_target = cmd_clean.split(maxsplit=1)[1]
            return AutomationModule.open_game_or_app(game_target)

        if cmd_lower.startswith("google ") or cmd_lower.startswith("pesquisar no google "):
            query_str = re.sub(r'^(google|pesquisar no google|pesquisar)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return AutomationModule.google_search_or_youtube(query_str, mode="google")

        if cmd_lower.startswith("youtube ") or cmd_lower.startswith("tocar no youtube "):
            query_str = re.sub(r'^(youtube|tocar no youtube)\s*', '', cmd_clean, flags=re.IGNORECASE).strip()
            return AutomationModule.google_search_or_youtube(query_str, mode="youtube")

        if cmd_lower in ("melhorar-se", "auto-programar", "meus-codigos", "meus codigos"):
            self.signals.sig_self_improve.emit("", "auto")
            return ("Protocolo de auto-melhoria iniciado. O Elívea está "
                    "analisando e melhorando seus próprios arquivos, Mestre. "
                    "Aguarde o relatório.")

        if cmd_lower in ("melhorar continuamente", "loop de melhoria",
                         "melhoria contínua", "melhoria continua",
                         "aprenda e melhore", "auto-aprenda"):
            self.signals.sig_self_improve.emit("", "continuous")
            return ("Modo melhoria contínua ativado. O Elívea vai "
                    "analisar, melhorar e aprender continuamente sem limite "
                    "de rodadas. Use 'parar' para interromper, Mestre.")

        if cmd_lower.startswith("melhorar ") or cmd_lower.startswith("melhorar-"):
            target = cmd_clean.split(maxsplit=1)[-1] if " " in cmd_clean else ""
            if target:
                self.signals.sig_self_improve.emit(target, "targeted")
                return (f"Auto-melhoria direcionada: {target}. "
                        "O Elívea está trabalhando nisso, Mestre.")

        if cmd_lower.startswith("ler-codigo ") or cmd_lower.startswith("ler codigo "):
            rel_p = cmd_clean.split(maxsplit=2)[-1]
            return SelfImproverModule.read_own_code(rel_p)

        if cmd_lower.startswith("mark-l"):
            status = self.bridge.get_status()
            return self.persona.format_report("Ponte de Integração Mark-L", status)

        # ---------------- ALA DE PROGRAMAÇÃO (estilo ZCode / Cursor) ----------------
        # --- programar via prompt: SmartCodeAgent direto (sem abrir UI) ---
        _via_prompt = False
        for pre in ("crie o arquivo ", "criar o arquivo ", "cria o arquivo ",
                    "escreva o arquivo ", "escreva em ", "adicione ao ",
                    "adicione em ", "modifique o ", "altere o ", "edite o ",
                    "refatore o ", "refatorar o ", "corrija o ", "corrige o ",
                    "implemente ", "crie a função ", "crie a classe ",
                    "crie o módulo ", "crie o module ", "crie um módulo ",
                    "crie um module ", "crie um script ",
                    "criar a função ", "criar a classe ", "criar o módulo ",
                    "criar um módulo ", "criar um script ",
                    "programar via prompt ", "programar via prompt: ",
                    "auto programe ", "auto-programar "):
            if cmd_lower.startswith(pre):
                prompt_text = cmd_clean[len(pre):].strip(".,!?;: ")
                if prompt_text:
                    self.signals.sig_self_improve.emit(prompt_text, "prompt")
                    return (f"Modo programar via prompt ativado: {prompt_text}. "
                            "O Elívea está implementando, Mestre.")
                break

        _code_mode = cmd_lower.strip(" \t!?.,;:") in (
            "programar", "modo programador", "modo código", "modo codigo",
            "ala de programação", "ala de programacao", "abrir programador",
            "abra o programador", "abrir o programador", "abrir a ala de programação",
            "abrir a ala de programacao", "abrir ala de programação",
            "abrir ala de programacao", "abrir modo programador",
            "abrir o modo programador", "code lab", "codedock", "codigo lab",
        )
        code_task = None
        for pre in ("programar ", "programe ", "programa um ", "programa uma ",
                    "programar um ", "programar uma ", "crie um programa ",
                    "criar um programa ", "cria um programa ", "faça um programa ",
                    "faca um programa ", "fazer um programa ", "crie um script ",
                    "criar um script ", "cria um script ", "escreva um programa ",
                    "escreve um programa "):
            if cmd_lower.startswith(pre):
                code_task = cmd_clean[len(pre):].strip(".,!?;: ")
                break
        if _code_mode or code_task is not None:
            self.signals.sig_code_request.emit(code_task or "")
            if code_task:
                return (f"Aviso. Abrindo a Ala de Programação com a tarefa: {code_task}. "
                        "Modo programador do Elívea iniciado, Mestre.")
            return ("Aviso. Abrindo a Ala de Programação, Mestre. O CodeDock está "
                    "pronto para receber suas ordens de código.")

        # ======= NOVOS MODULOS — RAG, Monitor, Clipboard, etc =======

        if re.search(r'\b(pesquisar|buscar na internet|google|search|pesquise)\b', cmd_lower) \
                and not cmd_lower.startswith("google ") and not cmd_lower.startswith("pesquisar no google "):
            query = re.sub(r'.*?(pesquisar|buscar na internet|google|search|pesquise)\s*', '', cmd_clean).strip()
            if query:
                result = RAGEngine.search_and_summarize(query)
                return f"Resultado da pesquisa:\n{result}"
            return "Especifique o que pesquisar."

        if re.search(r'\b(status do sistema|como esta o pc|monitorar|monitor|relatorio do sistema)\b', cmd_lower):
            return SystemMonitor.full_report()

        if re.search(r'\b(status rapido|como vai o pc|quanto de cpu|quanto de ram)\b', cmd_lower):
            return SystemMonitor.quick_status()

        if re.search(r'\b(top processos|processos pesados|quais processos)\b', cmd_lower):
            procs = SystemMonitor.get_top_processes(5)
            lines = ["Top 5 processos por CPU:"]
            for p in procs:
                lines.append(f" {p['name']}: CPU {p['cpu_percent']}%, RAM {p['memory_percent']}%")
            return "\n".join(lines)

        if re.search(r'\b(clipboard|area de transferencia|o que copiei|o que esta copiado)\b', cmd_lower):
            analysis = ClipboardMonitor.analyze()
            if analysis["empty"]:
                return "Aviso. A area de transferencia esta vazia."
            if analysis["is_error"]:
                return f"Erro detectado no clipboard:\n{analysis['content'][:500]}"
            if analysis["type"] == "code":
                return f"Codigo detectado ({analysis.get('language', 'desconhecido')}):\n{analysis['content'][:500]}"
            return f"Conteudo do clipboard:\n{analysis['content'][:500]}"

        if re.search(r'\b(analisar tela|ver tela|o que tem na tela|capturar tela e analisar)\b', cmd_lower):
            return ScreenContext.analyze_screenshot()

        if re.search(r'\b(janela ativa|janela em foco|programa aberto)\b', cmd_lower):
            info = ScreenContext.get_active_window()
            return f"Janela ativa: {info.get('title', 'desconhecida')} ({info.get('process', 'desconhecido')})"

        if re.search(r'\b(lembrete|agendar|tarefas agendadas|schedule|timer)\b', cmd_lower):
            m_min = re.search(r'(\d+)\s*(minuto|min)', cmd_lower)
            m_hr = re.search(r'(\d+)\s*(hora|hour)', cmd_lower)
            if m_min:
                mins = int(m_min.group(1))
                msg = re.sub(r'.*?\d+\s*min(uto)?s?\s*', '', cmd_clean).strip()
                task = TaskScheduler.add_reminder(msg or "Lembrete", minutes=mins)
                return f"Aviso. Lembrete agendado para {mins} minutos: {msg or 'sem descricao'}."
            if m_hr:
                hours = int(m_hr.group(1))
                msg = re.sub(r'.*?\d+\s*hora(s)?\s*', '', cmd_clean).strip()
                task = TaskScheduler.add_reminder(msg or "Lembrete", hours=hours)
                return f"Aviso. Lembrete agendado para {hours} horas: {msg or 'sem descricao'}."
            daily = re.search(r'(\d{1,2}:\d{2})', cmd_clean)
            if daily:
                time_str = daily.group(1)
                msg = re.sub(r'\d{1,2}:\d{2}', '', cmd_clean).strip()
                task = TaskScheduler.add_reminder(msg or "Lembrete diario", daily_at=time_str)
                return f"Aviso. Lembrete diario as {time_str}: {msg or 'sem descricao'}."
            return TaskScheduler.get_status()

        if re.search(r'\b(plugins?|extensao|extensao)\b', cmd_lower):
            return PluginManager.get_status()

        if re.search(r'\b(backup|exportar config|salvar configuracao)\b', cmd_lower):
            path = ConfigManager.export_config()
            return f"Aviso. Backup criado: {path}"

        if re.search(r'\b(versao|version|atualizar ia|update)\b', cmd_lower) and \
                not re.search(r'\b(winget|pip|pacote)\b', cmd_lower):
            return AutoUpdater.get_status()

        if re.search(r'\b(exportar|importar|backup)\b', cmd_lower):
            return ConfigManager.get_status()

        if re.search(r'\b(idioma|language|responder em ingles|falar em espanhol)\b', cmd_lower):
            lang = MultiLang.detect_language(cmd_clean)
            return f"Idioma detectado: {MultiLang._LANG_MAP.get(lang, lang)}. Ainda respondendo em portugues, Mestre."

        if re.search(r'\b(voz customizada|clonar voz|nova voz|upload de voz)\b', cmd_lower):
            return VoiceCloner.get_status()

        # Nenhum intent local → deixa o LLM responder (streaming)
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Silencia warning DPI (inofensivo) e evita Acesso negado
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.window.warning=false;qt.qpa.*=false"
    # Não força DPI — deixa Qt escolher o padrão (evita SetProcessDpiAwarenessContext failed)
    # QApplication.setHighDpiScaleFactorRoundingPolicy deve ser chamado antes, mas só se não houver instância
    if QApplication.instance() is None:
        try:
            from PySide6.QtCore import Qt
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            try:
                from PyQt6.QtCore import Qt
                QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
            except Exception:
                pass
    app_qt = QApplication.instance() or QApplication(sys.argv)
    app_qt.setFont(QFont("Segoe UI", 10))

    elvea = EliveaApp()
    win = EliveaMainWindow(
        command_handler=elvea.handle_command,
        pipeline=elvea.pipeline,
        speech=elvea.speech,
        llm=elvea.llm,
        voice_handler=elvea.speech.set_voice,
        stop_speech_handler=elvea.speech.stop_speaking,
        mic_button_handler=elvea.pipeline.begin_push_capture,
    )
    win.voice_test_requested.connect(lambda: elvea.speech.speak(
        f"Teste de síntese de voz concluído, {elvea.persona.user_name}. Esta é minha voz neural atual."))

    # Wire worker-thread signals → UI slots (queued, thread-safe)
    sig = elvea.signals
    sig.sig_master_text.connect(win.add_master_message)
    sig.sig_sage_full.connect(win.add_sage_message)
    sig.sig_sage_begin.connect(win.begin_sage_stream)
    sig.sig_sage_delta.connect(win.append_sage_stream)
    sig.sig_sage_end.connect(win.end_sage_stream)
    sig.sig_state.connect(win.set_pipeline_state)
    sig.sig_rms.connect(win.update_mic_rms)
    sig.sig_telemetry.connect(win.update_telemetry)
    sig.sig_code_request.connect(win.open_code_workspace)
    sig.sig_self_improve.connect(elvea._on_self_improve)

    win.show()

    def _startup():
        # Boot chime + greeting handled by AbilityAwakeningOverlay
        # Only log startup — no duplicate speech
        import logging
        _log = logging.getLogger("elvea.app")
        _log.info("Startup thread started — awakening handles speech")

    threading.Thread(target=_startup, daemon=True).start()

    # ═══════════════════════════════════════════════════════
    # MODULE 6: Auto-Updater (checks on startup)
    # ═══════════════════════════════════════════════════════
    try:
        AutoUpdater.check_on_startup()
    except Exception:
        pass

    # ═══════════════════════════════════════════════════════
    # MODULE 7: Config Manager (loads saved preferences)
    # ═══════════════════════════════════════════════════════
    try:
        ConfigManager.load()
    except Exception:
        pass

    def _on_close(*_):
        elvea.pipeline.stop()
        elvea.speech.stop_speaking()
        # Save config on exit
        try:
            ConfigManager.save()
        except Exception:
            pass

    app_qt.aboutToQuit.connect(_on_close)
    sys.exit(app_qt.exec())


if __name__ == "__main__":
    main()
