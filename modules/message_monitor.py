# -*- coding: utf-8 -*-
"""
Great Sage AI — Message Monitor & Auto-Reply Engine
=====================================================
Monitora notificações de mensagens e responde automaticamente.

  - WhatsApp Desktop / Web
  - Telegram Desktop
  - Discord
  - Email (Outlook/Gmail)
  - SMS (Windows Phone Link)
  - Qualquer app que gere notificações Windows

Fluxo:
  1. NotificationWatcher detecta nova notificação
  2. MessageParser extrai remetente + conteúdo
  3. AutoReplyEngine decide se e como responder
  4. ResponseSender envia resposta (click+type ou API)

Uso:
    from GreatSageAI_Clone.modules.message_monitor import MessageMonitor
    monitor = MessageMonitor(llm_engine=llm)
    monitor.start()
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("greatsage.message_monitor")


# =========================================================================
# Configuration
# =========================================================================

@dataclass
class MonitorConfig:
    """Configuration for the message monitor."""
    # Which apps to monitor
    monitor_whatsapp: bool = True
    monitor_telegram: bool = True
    monitor_discord: bool = True
    monitor_email: bool = True
    monitor_sms: bool = True

    # Auto-reply settings
    auto_reply_enabled: bool = True
    auto_reply_delay_min: float = 2.0    # seconds before replying (feels natural)
    auto_reply_delay_max: float = 5.0
    max_replies_per_hour: int = 20       # rate limit
    quiet_hours_start: int = 23          # 11 PM
    quiet_hours_end: int = 7             # 7 AM

    # Who to auto-reply to
    reply_to_everyone: bool = False
    reply_to_contacts: List[str] = field(default_factory=list)
    ignore_contacts: List[str] = field(default_factory=list)

    # Response style
    response_style: str = "friendly"     # friendly, formal, brief, custom
    custom_prompt: str = ""              # custom system prompt for replies
    language: str = "pt-BR"

    # File paths
    config_dir: Path = field(default_factory=lambda: Path("F:/GreatSageTemp/message_monitor"))
    history_file: str = "reply_history.json"
    rules_file: str = "auto_reply_rules.json"


# =========================================================================
# Data Classes
# =========================================================================

class MessageSource(Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    SMS = "sms"
    UNKNOWN = "unknown"


@dataclass
class IncomingMessage:
    """A detected incoming message."""
    source: MessageSource
    sender: str
    content: str
    timestamp: float = 0.0
    is_group: bool = False
    group_name: str = ""
    raw_notification: str = ""
    replied: bool = False
    reply_text: str = ""

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class ReplyRule:
    """A user-defined rule for auto-reply."""
    name: str
    sender_pattern: str      # regex pattern for sender name
    message_pattern: str     # regex pattern for message content
    reply: str               # static reply (or "LLM" for dynamic)
    priority: int = 0        # higher = checked first
    enabled: bool = True


# =========================================================================
# 1. Notification Watcher — monitors Windows notifications
# =========================================================================

class NotificationWatcher:
    """Watches Windows notifications from messaging apps.

    Uses PowerShell to read Action Center notifications.
    Falls back to polling active window title for app-specific detection.
    """

    # Known notification patterns per app
    NOTIFICATION_PATTERNS = {
        MessageSource.WHATSAPP: [
            r"^(.+?)\s*(?:says?|enviou|forwarded)",
            r"^(.+?):\s*(.+)",
            r"^(.+?)\s*\u2014\s*(.+)",
        ],
        MessageSource.TELEGRAM: [
            r"^(.+?):\s*(.+)",
            r"^(.+?)\s*enviou uma mensagem",
        ],
        MessageSource.DISCORD: [
            r"^(.+?)\s*em\s*(.+?):\s*(.+)",
            r"^(.+?):\s*(.+)",
        ],
        MessageSource.EMAIL: [
            r"^(.+?)\s*:\s*(.+)",
            r"Nova mensagem de\s+(.+)",
        ],
        MessageSource.SMS: [
            r"^(.+?):\s*(.+)",
        ],
    }

    def __init__(self, config: MonitorConfig):
        self.config = config
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_notifications: Dict[str, str] = {}
        self._callbacks: List[Callable[[IncomingMessage], None]] = []
        self._poll_interval = 2.0  # seconds

    def on_message(self, callback: Callable[[IncomingMessage], None]):
        """Register callback for new messages."""
        self._callbacks.append(callback)

    def start(self):
        """Start watching notifications in background."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="notification-watcher")
        self._thread.start()
        logger.info("NotificationWatcher started")

    def stop(self):
        self._running = False

    def _loop(self):
        """Main polling loop."""
        while self._running:
            try:
                notifications = self._read_notifications()
                for notif in notifications:
                    msg = self._parse_notification(notif)
                    if msg and not self._is_duplicate(msg):
                        for cb in self._callbacks:
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.error(f"Message callback error: {e}")
            except Exception as e:
                logger.debug(f"Notification poll error: {e}")
            time.sleep(self._poll_interval)

    def _read_notifications(self) -> List[str]:
        """Read current Windows notifications."""
        notifications = []
        try:
            # Method 1: PowerShell — read Action Center
            ps_cmd = """
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            $toastXml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Microsoft.Windows.Shell.RunDialogue")
            """
            # Method 2: Simpler — check active window titles
            notifications.extend(self._check_active_windows())

            # Method 3: Read notification database (Windows 10/11)
            notifications.extend(self._read_notification_db())

        except Exception as e:
            logger.debug(f"Notification read error: {e}")

        return notifications

    def _check_active_windows(self) -> List[str]:
        """Check if messaging apps have new messages by looking at window titles."""
        results = []
        try:
            import ctypes.wintypes

            user32 = ctypes.windll.user32

            def enum_callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value
                        # Check for messaging app patterns
                        for source, patterns in [
                            (MessageSource.WHATSAPP, ["WhatsApp", "whatsapp"]),
                            (MessageSource.TELEGRAM, ["Telegram", "telegram"]),
                            (MessageSource.DISCORD, ["Discord", "discord"]),
                        ]:
                            if any(p.lower() in title.lower() for p in patterns):
                                # Extract message info from title
                                if "(" in title and ")" in title:
                                    # WhatsApp: "WhatsApp (2) - Contact Name"
                                    results.append(f"[{source.value}] {title}")
                                elif " - " in title:
                                    # Telegram: "Contact Name - Telegram"
                                    results.append(f"[{source.value}] {title}")
                                else:
                                    results.append(f"[{source.value}] {title}")
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        except Exception:
            pass
        return results

    def _read_notification_db(self) -> List[str]:
        """Try to read Windows notification database."""
        results = []
        try:
            # Windows stores notifications in a SQLite database
            db_path = Path(os.path.expanduser(
                r"~\AppData\Local\Microsoft\Windows\Notifications\wpndatabase.db"
            ))
            if db_path.exists():
                import sqlite3
                conn = sqlite3.connect(str(db_path), timeout=2)
                try:
                    cursor = conn.execute(
                        "SELECT payload FROM Notification WHERE launchActionType != '' "
                        "ORDER BY timestamp DESC LIMIT 10"
                    )
                    for row in cursor:
                        payload = row[0]
                        if payload:
                            # Extract text from XML payload
                            text = self._extract_from_payload(payload)
                            if text:
                                results.append(text)
                except Exception:
                    pass
                finally:
                    conn.close()
        except Exception:
            pass
        return results

    def _extract_from_payload(self, payload: str) -> Optional[str]:
        """Extract readable text from Windows notification XML payload."""
        try:
            # Simple XML text extraction
            import re
            texts = re.findall(r'<text[^>]*>(.*?)</text>', payload, re.DOTALL)
            return " ".join(texts) if texts else None
        except Exception:
            return None

    def _parse_notification(self, raw: str) -> Optional[IncomingMessage]:
        """Parse a raw notification into an IncomingMessage."""
        # Detect source
        source = MessageSource.UNKNOWN
        for src in MessageSource:
            if f"[{src.value}]" in raw.lower() or src.value in raw.lower():
                source = src
                break

        if source == MessageSource.UNKNOWN:
            # Try to guess from content
            raw_lower = raw.lower()
            if "whatsapp" in raw_lower:
                source = MessageSource.WHATSAPP
            elif "telegram" in raw_lower:
                source = MessageSource.TELEGRAM
            elif "discord" in raw_lower:
                source = MessageSource.DISCORD
            elif "outlook" in raw_lower or "gmail" in raw_lower or "mail" in raw_lower:
                source = MessageSource.EMAIL

        # Try to extract sender + content
        sender = ""
        content = ""
        clean = re.sub(r'\[.*?\]', '', raw).strip()  # Remove [source] tags

        # Pattern: "Name: Message" or "Name — Message"
        match = re.match(r'^(.+?)[:\s—–-]+\s*(.+)', clean)
        if match:
            sender = match.group(1).strip()
            content = match.group(2).strip()

        # Clean up window title artifacts
        sender = re.sub(r'\s*[-–]\s*(WhatsApp|Telegram|Discord|Microsoft).*', '', sender).strip()
        sender = re.sub(r'\s*\(\d+\).*', '', sender).strip()

        if not sender and not content:
            return None

        return IncomingMessage(
            source=source,
            sender=sender or "Unknown",
            content=content or "(notification)",
            raw_notification=raw,
        )

    def _is_duplicate(self, msg: IncomingMessage) -> bool:
        """Check if this message was already seen."""
        key = f"{msg.sender}:{msg.content[:50]}"
        last = self._last_notifications.get(msg.sender, "")
        if last == msg.content[:50]:
            return True
        self._last_notifications[msg.sender] = msg.content[:50]
        return False


# =========================================================================
# 2. Message Parser — extracts structured info from messages
# =========================================================================

class MessageParser:
    """Parses incoming messages to extract intent, urgency, and context."""

    # Urgency patterns
    URGENT_PATTERNS = [
        r'\burgente\b', r'\bimportante\b', r'\bemergência\b', r'\bSOS\b',
        r'\bpreciso agora\b', r'\bajuda\b', r'\bhelp\b', r'\bquanto antes\b',
        r'\bASSÉDIO\b', r'\bagora\b', r'\brápido\b',
    ]

    # Question patterns
    QUESTION_PATTERNS = [
        r'\?$',  # ends with ?
        r'^(o que|como|quando|onde|por que|qual|quem|quanto)',
        r'\bvocê (sabe|pode|quer|tem|gostaria)\b',
        r'\bcan you\b', r'\bcould you\b', r'\bwill you\b',
    ]

    # Greeting patterns
    GREETING_PATTERNS = [
        r'^(oi|olá|bom dia|boa tarde|boa noite|hello|hi|hey|fala|e aí)',
        r'^(bom dia|boa tarde|boa noite)',
    ]

    # farewell patterns
    FAREWELL_PATTERNS = [
        r'(tchau|até logo|até mais|bye|see you|falou|valeu)',
        r'(boa noite|durma bem|sleep well)',
    ]

    @classmethod
    def parse(cls, message: IncomingMessage) -> Dict[str, Any]:
        """Parse a message and return structured analysis."""
        content = message.content.lower().strip()

        return {
            "is_question": cls._matches_any(content, cls.QUESTION_PATTERNS),
            "is_urgent": cls._matches_any(content, cls.URGENT_PATTERNS),
            "is_greeting": cls._matches_any(content, cls.GREETING_PATTERNS),
            "is_farewell": cls._matches_any(content, cls.FAREWELL_PATTERNS),
            "is_group": message.is_group,
            "source": message.source.value,
            "sender": message.sender,
            "length": len(content),
            "word_count": len(content.split()),
            "sentiment": cls._detect_sentiment(content),
        }

    @classmethod
    def _matches_any(cls, text: str, patterns: List[str]) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    @classmethod
    def _detect_sentiment(cls, text: str) -> str:
        positive = ['obrigado', 'obrigada', 'valeu', 'legal', 'show', 'massa', 'top',
                    'perfeito', 'incrível', 'obg', 'vlw', 'thanks', 'good', 'great']
        negative = ['errado', 'problema', 'ruim', 'péssimo', 'droga', 'porra',
                    'merda', 'não funciona', 'bug', 'error', 'fail']
        if any(w in text for w in positive):
            return "positive"
        if any(w in text for w in negative):
            return "negative"
        return "neutral"


# =========================================================================
# 3. Auto-Reply Engine — decides how and when to reply
# =========================================================================

class AutoReplyEngine:
    """Decides whether and how to reply to a message.

    Uses LLM to generate contextually appropriate responses.
    Respects rate limits, quiet hours, and user-defined rules.
    """

    def __init__(self, config: MonitorConfig, llm_engine=None):
        self.config = config
        self._llm = llm_engine
        self._reply_count_hour = 0
        self._hour_start = time.time()
        self._rules: List[ReplyRule] = []
        self._conversation_history: Dict[str, List[Dict]] = {}  # sender -> messages
        self._reply_history: List[Dict] = []
        self._load_rules()

    def should_reply(self, message: IncomingMessage) -> bool:
        """Decide if we should reply to this message."""
        if not self.config.auto_reply_enabled:
            return False

        # Rate limit check
        now = time.time()
        if now - self._hour_start > 3600:
            self._reply_count_hour = 0
            self._hour_start = now
        if self._reply_count_hour >= self.config.max_replies_per_hour:
            logger.debug("Rate limit reached — skipping reply")
            return False

        # Quiet hours check
        hour = datetime.now().hour
        if self.config.quiet_hours_start > self.config.quiet_hours_end:
            # Wraps midnight (e.g., 23-7)
            if hour >= self.config.quiet_hours_start or hour < self.config.quiet_hours_end:
                logger.debug("Quiet hours — skipping reply")
                return False
        else:
            if self.config.quiet_hours_start <= hour < self.config.quiet_hours_end:
                logger.debug("Quiet hours — skipping reply")
                return False

        # Already replied check
        if message.replied:
            return False

        # Empty content
        if not message.content or message.content == "(notification)":
            return False

        # Ignore list
        if message.sender in self.config.ignore_contacts:
            return False

        # Reply-to list (if not empty, only reply to listed contacts)
        if self.config.reply_to_contacts and message.sender not in self.config.reply_to_contacts:
            return False

        # Check rules
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            if not rule.enabled:
                continue
            if re.search(rule.sender_pattern, message.sender, re.IGNORECASE):
                if re.search(rule.message_pattern, message.content, re.IGNORECASE):
                    return True  # Rule matches — should reply

        # Default: reply if configured to reply to everyone
        return self.config.reply_to_everyone

    def generate_reply(self, message: IncomingMessage) -> str:
        """Generate a reply for the message."""
        # Check static rules first
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            if not rule.enabled:
                continue
            if re.search(rule.sender_pattern, message.sender, re.IGNORECASE):
                if re.search(rule.message_pattern, message.content, re.IGNORECASE):
                    if rule.reply.upper() != "LLM":
                        return rule.reply

        # Use LLM for dynamic reply
        if self._llm:
            return self._generate_llm_reply(message)

        # Fallback: generic reply
        return self._generate_generic_reply(message)

    def _generate_llm_reply(self, message: IncomingMessage) -> str:
        """Generate reply using the LLM."""
        try:
            # Build context
            history = self._conversation_history.get(message.sender, [])
            history_text = ""
            for h in history[-5:]:  # last 5 messages
                role = h.get("role", "user")
                text = h.get("content", "")
                history_text += f"{role}: {text}\n"

            system_prompt = f"""Você é um assistente pessoal que responde mensagens no WhatsApp/Telegram/Discord do usuário.
O usuário pediu para você responder automaticamente as mensagens dele.

REGRAS:
- Responda de forma NATURAL e HUMANA — como se fosse o próprio usuário respondendo
- Seja BREVE — máx 2-3 frases (mensagens de chat são curtas)
- Use linguagem casual e amigável em português
- Não pareça um bot — varie as respostas
- Se a mensagem é uma pergunta, responda com a informação
- Se é um convite/combine, responda confirmando ou perguntando detalhes
- Se é uma mensagem urgente, responda prontamente
- Se é só um "oi", responda com um "oi" breve
- NUNCA use emojis excessivos
- NUNCA diga que é uma IA respondendo

CONTEXTO:
- Mensagens anteriores com {message.sender}:
{history_text if history_text else "(primeira mensagem)"}

- Estilo de resposta: {self.config.response_style}
"""

            # Build messages for LLM
            messages = [{"role": "user", "content": message.content}]

            if hasattr(self._llm, 'chat'):
                response = self._llm.chat(messages, system=system_prompt)
                if response.success:
                    reply = response.text.strip()
                    # Track
                    self._record_reply(message, reply)
                    return reply

            # Fallback: use stream
            if hasattr(self._llm, 'stream'):
                chunks = []
                for chunk in self._llm.stream(messages, system=system_prompt, max_tokens=200):
                    chunks.append(chunk)
                reply = "".join(chunks).strip()
                if reply:
                    self._record_reply(message, reply)
                    return reply

        except Exception as e:
            logger.error(f"LLM reply generation error: {e}")

        return self._generate_generic_reply(message)

    def _generate_generic_reply(self, message: IncomingMessage) -> str:
        """Generate a generic reply without LLM."""
        parsed = MessageParser.parse(message)

        if parsed["is_greeting"]:
            return "Oi! Tudo bem?"
        if parsed["is_farewell"]:
            return "Tchau! Até mais!"
        if parsed["is_question"]:
            return "Hmm, boa pergunta. Deixa eu ver e te respondo."
        if parsed["is_urgent"]:
            return "Vi que é urgente. Já estou vendo."
        return "Recebi, vou dar uma olhada."

    def _record_reply(self, message: IncomingMessage, reply: str):
        """Record the reply in history."""
        self._reply_count_hour += 1
        self._conversation_history.setdefault(message.sender, []).append({
            "role": "other",
            "content": message.content,
            "time": message.timestamp,
        })
        self._conversation_history[message.sender].append({
            "role": "assistant",
            "content": reply,
            "time": time.time(),
        })
        self._reply_history.append({
            "sender": message.sender,
            "source": message.source.value,
            "message": message.content[:200],
            "reply": reply[:200],
            "time": time.time(),
        })
        # Save to file
        self._save_history()

    def _load_rules(self):
        """Load auto-reply rules from file."""
        rules_file = self.config.config_dir / self.config.rules_file
        try:
            if rules_file.exists():
                data = json.loads(rules_file.read_text(encoding="utf-8"))
                for r in data.get("rules", []):
                    self._rules.append(ReplyRule(**r))
        except Exception:
            pass

    def add_rule(self, name: str, sender_pattern: str, message_pattern: str,
                 reply: str, priority: int = 0):
        """Add a new auto-reply rule."""
        rule = ReplyRule(
            name=name,
            sender_pattern=sender_pattern,
            message_pattern=message_pattern,
            reply=reply,
            priority=priority,
        )
        self._rules.append(rule)
        self._save_rules()

    def _save_rules(self):
        """Save rules to file."""
        rules_file = self.config.config_dir / self.config.rules_file
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {"rules": [
                {"name": r.name, "sender_pattern": r.sender_pattern,
                 "message_pattern": r.message_pattern, "reply": r.reply,
                 "priority": r.priority, "enabled": r.enabled}
                for r in self._rules
            ]}
            rules_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _save_history(self):
        """Save reply history to file."""
        history_file = self.config.config_dir / self.config.history_file
        history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Keep last 500 entries
            recent = self._reply_history[-500:]
            history_file.write_text(
                json.dumps(recent, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


# =========================================================================
# 4. Response Sender — sends replies to the correct app
# =========================================================================

class ResponseSender:
    """Sends auto-replies back to the messaging app.

    Strategies:
    1. WhatsApp/Telegram Web: click + type via browser agent
    2. Desktop apps: focus window + type via pyautogui
    3. Notification reply: use Windows notification reply action
    """

    @classmethod
    def send(cls, message: IncomingMessage, reply: str) -> bool:
        """Send a reply to the messaging app."""
        try:
            # Try notification reply first (fastest)
            if cls._reply_via_notification(message, reply):
                return True

            # Try app-specific methods
            if message.source == MessageSource.WHATSAPP:
                return cls._reply_whatsapp(message, reply)
            elif message.source == MessageSource.TELEGRAM:
                return cls._reply_telegram(message, reply)
            elif message.source == MessageSource.DISCORD:
                return cls._reply_discord(message, reply)
            elif message.source == MessageSource.EMAIL:
                return cls._reply_email(message, reply)

            # Fallback: type in active window
            return cls._type_in_active_window(reply)

        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return False

    @classmethod
    def _reply_via_notification(cls, message: IncomingMessage, reply: str) -> bool:
        """Try to reply via Windows notification action."""
        try:
            # Windows 10/11 supports inline reply from notifications
            # This is the fastest method but not always available
            import pyautogui
            # Focus the notification area
            pyautogui.hotkey('win', 'n')  # Open notification center
            time.sleep(0.5)
            # The notification should be visible — try to find reply button
            # This is app-specific and unreliable, so return False as fallback
            pyautogui.hotkey('escape')  # Close notification center
            return False
        except Exception:
            return False

    @classmethod
    def _reply_whatsapp(cls, message: IncomingMessage, reply: str) -> bool:
        """Reply via WhatsApp Desktop."""
        try:
            # Focus WhatsApp window
            cls._focus_app("WhatsApp")
            time.sleep(0.5)

            # Use Ctrl+F to search for contact
            import pyautogui
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.3)
            pyautogui.typewrite(message.sender, interval=0.02)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(0.3)

            # Type the reply
            pyautogui.typewrite(reply, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            return True
        except Exception as e:
            logger.debug(f"WhatsApp reply failed: {e}")
            return False

    @classmethod
    def _reply_telegram(cls, message: IncomingMessage, reply: str) -> bool:
        """Reply via Telegram Desktop."""
        try:
            cls._focus_app("Telegram")
            time.sleep(0.5)

            import pyautogui
            # Ctrl+F to search
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.3)
            pyautogui.typewrite(message.sender, interval=0.02)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(0.3)

            # Type reply
            pyautogui.typewrite(reply, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            return True
        except Exception as e:
            logger.debug(f"Telegram reply failed: {e}")
            return False

    @classmethod
    def _reply_discord(cls, message: IncomingMessage, reply: str) -> bool:
        """Reply via Discord."""
        try:
            cls._focus_app("Discord")
            time.sleep(0.5)

            import pyautogui
            # Discord uses Ctrl+K to search
            pyautogui.hotkey('ctrl', 'k')
            time.sleep(0.3)
            pyautogui.typewrite(message.sender, interval=0.02)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(0.3)

            # Type in chat
            pyautogui.typewrite(reply, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            return True
        except Exception as e:
            logger.debug(f"Discord reply failed: {e}")
            return False

    @classmethod
    def _reply_email(cls, message: IncomingMessage, reply: str) -> bool:
        """Reply via email (Outlook or browser)."""
        # Email reply is more complex — just open the compose window
        try:
            cls._focus_app("Outlook")
            time.sleep(0.5)
            import pyautogui
            pyautogui.hotkey('ctrl', 'r')  # Reply
            time.sleep(1)
            pyautogui.typewrite(reply, interval=0.02)
            return True
        except Exception:
            return False

    @classmethod
    def _type_in_active_window(cls, text: str) -> bool:
        """Type text in whatever window is active."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
            return True
        except Exception:
            return False

    @classmethod
    def _focus_app(cls, app_name: str) -> bool:
        """Focus a specific app window."""
        try:
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            found_hwnd = None

            def enum_callback(hwnd, _):
                nonlocal found_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if app_name.lower() in buff.value.lower():
                            found_hwnd = hwnd
                            return False  # Stop enumeration
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            if found_hwnd:
                user32.SetForegroundWindow(found_hwnd)
                time.sleep(0.3)
                return True
            return False
        except Exception:
            return False


# =========================================================================
# 5. Message Monitor — the main orchestrator
# =========================================================================

class MessageMonitor:
    """Main message monitor — orchestrates detection, parsing, reply generation, and sending.

    Usage:
        monitor = MessageMonitor(llm_engine=llm)
        monitor.start()
        # Now it monitors messages in background and auto-replies
    """

    def __init__(self, config: MonitorConfig = None, llm_engine=None):
        self.config = config or MonitorConfig()
        self._watcher = NotificationWatcher(self.config)
        self._engine = AutoReplyEngine(self.config, llm_engine)
        self._running = False
        self._on_message_callbacks: List[Callable] = []
        self._on_reply_callbacks: List[Callable] = []

        # Wire up the watcher
        self._watcher.on_message(self._handle_message)

    def start(self):
        """Start monitoring messages."""
        self._running = True
        self._watcher.start()
        logger.info("MessageMonitor started")

    def stop(self):
        """Stop monitoring."""
        self._running = False
        self._watcher.stop()
        logger.info("MessageMonitor stopped")

    def on_message(self, callback: Callable[[IncomingMessage], None]):
        """Register callback for incoming messages."""
        self._on_message_callbacks.append(callback)

    def on_reply(self, callback: Callable[[IncomingMessage, str], None]):
        """Register callback when a reply is sent."""
        self._on_reply_callbacks.append(callback)

    def add_rule(self, name: str, sender: str, pattern: str, reply: str, priority: int = 0):
        """Add an auto-reply rule."""
        self._engine.add_rule(name, sender, pattern, reply, priority)

    def set_reply_to(self, contacts: List[str]):
        """Set list of contacts to auto-reply to."""
        self.config.reply_to_contacts = contacts

    def set_ignore(self, contacts: List[str]):
        """Set list of contacts to ignore."""
        self.config.ignore_contacts = contacts

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "running": self._running,
            "auto_reply_enabled": self.config.auto_reply_enabled,
            "replies_this_hour": self._engine._reply_count_hour,
            "max_per_hour": self.config.max_replies_per_hour,
            "total_replies": len(self._engine._reply_history),
            "rules_count": len(self._engine._rules),
            "contacts_tracked": len(self._engine._conversation_history),
        }

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get recent reply history."""
        return self._engine._reply_history[-limit:]

    def _handle_message(self, message: IncomingMessage):
        """Handle an incoming message — parse, decide, reply."""
        try:
            # Notify callbacks
            for cb in self._on_message_callbacks:
                try:
                    cb(message)
                except Exception:
                    pass

            # Parse the message
            parsed = MessageParser.parse(message)

            # Decide if we should reply
            if not self._engine.should_reply(message):
                logger.debug(f"Skipping reply to {message.sender}: not in auto-reply scope")
                return

            # Generate reply
            reply = self._engine.generate_reply(message)
            if not reply:
                return

            # Add natural delay (human-like response time)
            import random
            delay = random.uniform(
                self.config.auto_reply_delay_min,
                self.config.auto_reply_delay_max
            )
            time.sleep(delay)

            # Send the reply
            success = ResponseSender.send(message, reply)
            if success:
                message.replied = True
                message.reply_text = reply
                logger.info(f"Auto-replied to {message.sender}: {reply[:80]}")

                # Notify reply callbacks
                for cb in self._on_reply_callbacks:
                    try:
                        cb(message, reply)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Message handling error: {e}")
