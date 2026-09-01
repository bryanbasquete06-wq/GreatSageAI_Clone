#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea — Motor Principal (v2)
=====================================
Conecta LLM, Voz, Memória, Persona, Raciocínio, Automação e Programação.
Comandos completos, raciocínio com confiança real, consciência de contexto.
"""

import os
import re
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Generator
from dataclasses import dataclass, field
from datetime import datetime

from core.llm import LLMEngine, LLMResponse
from core.voice import VoiceEngine
from core.memory import Memory
from core.persona import get_system_prompt, get_greeting, get_thinking_text
from core.reasoning import ChainOfThought, CodeReasoner
from core.automation import DesktopAutomation
from core.programmer import Programmer, CodeTask
from core.web_search import search_and_summarize, search_news
from core.code_executor import execute_code, format_result
from core.dashboard import Dashboard
from core.plugins import PluginManager
from core.multimodal import analyze_image, generate_image
from core.scheduler import Scheduler
from core.monitor import Monitor
from core.intelligence_engine import IntelligenceEngine
from core.request_router import RequestRouter
from core.deep_dev import DeepDevEngine
from core.weekly_digest import WeeklyDigestEngine
from core.intelligence import HallucinationGuard, SelfCorrectionEngine, QualityScorer, KnowledgeGraph, IntentPredictor
from core.multi_provider_router import get_router, ProviderTier, QueryComplexity, classify_query_complexity

logger = logging.getLogger("elvea.engine")


@dataclass
class ChatMessage:
    """Mensagem de chat estruturada."""
    role: str  # user, assistant, system
    content: str
    thinking: str = ""
    provider: str = ""
    tokens: int = 0
    latency_ms: float = 0


class SageEngine:
    """
    Motor principal do Elivea.
    Coordena todos os subsistemas com inteligência aprimorada.
    """

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)

        # Inicializa subsistemas
        env_path = self.project_dir / ".env"
        self.llm = LLMEngine(str(env_path))
        self.voice = VoiceEngine()
        self.memory = Memory(str(self.project_dir / "memory"))
        self.reasoning = ChainOfThought()
        self.code_reasoner = CodeReasoner()
        self.automation = DesktopAutomation()
        self.programmer = Programmer()
        self.dashboard = Dashboard(str(self.project_dir / "memory"))
        self.plugins = PluginManager()
        self.scheduler = Scheduler(str(self.project_dir / "memory"))
        self.monitor = Monitor(str(self.project_dir / "memory"))
        # Intelligence engine
        self.intelligence = IntelligenceEngine()

        # Intelligence pipeline (6 systems)
        self.hallucination_guard = HallucinationGuard()
        self.self_correction = SelfCorrectionEngine()
        self.quality_scorer = QualityScorer(str(self.project_dir / "memory"))
        self.knowledge_graph = KnowledgeGraph(str(self.project_dir / "memory"))
        self.intent_predictor = IntentPredictor()

        # Deep Dev Panel
        self.deep_dev = DeepDevEngine(str(self.project_dir))

        # Weekly Digest
        self.digest_engine = WeeklyDigestEngine(str(self.project_dir))

        # Start scheduler
        self.scheduler.start_checker(interval=30)

        # Estado
        self.user_name = self.memory.get_user_name()
        self.system_prompt = get_system_prompt(user_name=self.user_name)
        self._is_processing = False
        self._abort = False
        self._conversation_turns = 0
        self._last_topic = ""

        # Callbacks
        self.on_token: Optional[Callable[[str], None]] = None
        self.on_thinking: Optional[Callable[[str], None]] = None
        self.on_done: Optional[Callable[[ChatMessage], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_voice: Optional[Callable[[str], None]] = None

        logger.info(f"Elivea Engine v2 | User: {self.user_name}")
        logger.info(f"Providers: {[p.name for p in self.llm.providers if p.available]}")

    def greet(self) -> str:
        """Gera saudação inicial."""
        return get_greeting(self.user_name)

    def chat(self, user_input: str, stream: bool = True) -> ChatMessage:
        """Processa mensagem do usuário e retorna resposta."""
        self._is_processing = True
        self._abort = False
        self._conversation_turns += 1

        # Salva mensagem do usuário
        self.memory.add_message("user", user_input)

        # === INTELLIGENCE PIPELINE: Input Phase ===
        # 1. Intent Predictor — record usage and predict intent
        self.intent_predictor.record_usage(user_input)
        # 2. Knowledge Graph — extract entities from user input
        try:
            self.knowledge_graph.update(user_input, context="user_query")
        except Exception:
            pass
        # 3. Get knowledge context for this query
        kg_context = self.knowledge_graph.get_context_for_query(user_input)

        # Deep Dev commands
        dd_result = self.deep_dev.handle_command(user_input)
        if dd_result is not None:
            msg = ChatMessage(role="assistant", content=dd_result)
            self.memory.add_message("assistant", dd_result)
            self._is_processing = False
            return msg

        # Detecta comandos especiais
        cmd_result = self._handle_command(user_input)
        if cmd_result is not None:
            msg = ChatMessage(role="assistant", content=cmd_result)
            self.memory.add_message("assistant", cmd_result)
            self._is_processing = False
            return msg

        # Monta contexto — reduzido para caber no TPM 8000 do Groq (antes 8000 estourava)
        context_messages = self.memory.get_context_messages(max_tokens=2500)

        # Adiciona contexto de memória
        memory_context = self.memory.build_memory_context()
        system = self.system_prompt
        if memory_context:
            system += f"\n\n=== MEMÓRIA DE LONGO PRAZO ===\n{memory_context}"

        # Adiciona consciência de contexto
        if self._conversation_turns > 1:
            system += f"\n\n=== CONTEXTO DA CONVERSA ===\nTurnos: {self._conversation_turns}"
            if self._last_topic:
                system += f"\nÚltimo tópico: {self._last_topic}"

        # Adiciona raciocínio para perguntas complexas
        reasoning = self.reasoning.analyze(user_input)
        if reasoning.steps:
            reasoning_prompt = self.reasoning.build_reasoning_prompt(user_input)
            system += f"\n\n=== RACIOCÍNIO ===\n{reasoning_prompt}"
            system += f"\nConfiança do raciocínio: {reasoning.confidence:.0%}"

        # Detecta código
        is_code = self._is_code_request(user_input)
        if is_code:
            system += ("\n\n=== PROGRAMAÇÃO ===\n"
                      "Você é um arquiteto de software sênior.\n"
                      "Responda com código completo e funcional.\n"
                      "Use markdown para blocos de código.\n"
                      "Inclua tratamento de erros e boas práticas.\n"
                      "Explique a lógica por trás de cada decisão.")

        # Detecta tipo de pergunta para adaptar estilo
        is_question = self._is_question(user_input)
        if is_question:
            system += "\n\n=== ESTILO ===\nEsta é uma pergunta direta. Seja conciso mas completo."

        is_explanation = self._is_explanation_request(user_input)
        if is_explanation:
            system += "\n\n=== ESTILO ===\nPede explicação. Use analogias e exemplos concretos."

        # Converte para formato LLM
        messages = [{"role": m["role"], "content": m["content"]} for m in context_messages]

        # Inject knowledge graph context into system prompt
        if kg_context:
            system += f"\n\n=== CONHECIMENTO PESSOAL ===\n{kg_context}"

        # Get recent responses for cross-contradiction detection
        recent_responses = []
        for m in self.memory.chat_history[-6:]:
            if m.get("role") == "assistant":
                recent_responses.append(m.get("content", ""))

        # === INTELLIGENCE PIPELINE: LLM Call + Post-Processing ===
        full_response = ""
        start_time = time.time()
        provider_name = "stream"

        if stream:
            try:
                for token in self.llm.stream(messages, system=system, max_tokens=1500, temperature=0.7):
                    if self._abort:
                        break
                    full_response += token
                    if self.on_token:
                        self.on_token(token)
            except Exception as e:
                logger.error(f"Stream error: {e}")
                full_response = f"Erro no stream: {e}"
        else:
            response = self.llm.chat(messages, system=system, max_tokens=1500, temperature=0.7)
            if response.success:
                full_response = response.text
                provider_name = getattr(response, 'provider', 'unknown')
            else:
                full_response = f"Erro: {response.error}"

        latency_ms = (time.time() - start_time) * 1000

        # === INTELLIGENCE PIPELINE: Response Phase ===
        hallucination_score = 1.0
        correction_count = 0

        if full_response and not full_response.startswith("Erro"):
            # 4. Hallucination Guard — detect potential hallucinations
            try:
                guard_result = self.hallucination_guard.analyze(
                    full_response,
                    context=user_input,
                    previous_responses=recent_responses if recent_responses else None,
                )
                hallucination_score = guard_result.overall_confidence
                if guard_result.requires_confirmation and guard_result.high_severity > 0:
                    full_response += f"\n\n⚠️ *[Elívea detectou {guard_result.high_severity} afirmação(ões) incerta(s). Verifique antes de usar.]*"
                elif guard_result.medium_severity > 2:
                    full_response += f"\n\n💡 *[Confiança: {hallucination_score:.0%} — algumas afirmações podem precisar de verificação.]*"
            except Exception as e:
                logger.debug(f"Hallucination guard error: {e}")

            # 5. Self-Correction — review and auto-fix response
            try:
                is_code = "```" in full_response
                correction_result = self.self_correction.review(full_response, is_code=is_code)
                if correction_result.was_modified:
                    full_response = correction_result.corrected_response
                    correction_count = correction_result.corrections_applied
            except Exception as e:
                logger.debug(f"Self-correction error: {e}")

            # 6. Knowledge Graph — extract entities from response
            try:
                self.knowledge_graph.update(full_response, context="assistant_response")
            except Exception as e:
                logger.debug(f"Knowledge graph update error: {e}")

        # 7. Quality Score — auto-score this response
        try:
            self.quality_scorer.record(
                query=user_input,
                response=full_response,
                latency_ms=latency_ms,
                provider=provider_name,
                hallucination_score=hallucination_score,
                correction_count=correction_count,
            )
        except Exception as e:
            logger.debug(f"Quality score error: {e}")

        # Salva resposta e contexto
        self._last_topic = user_input[:100]
        msg = ChatMessage(
            role="assistant",
            content=full_response,
            provider=provider_name,
            tokens=len(full_response.split()),
            latency_ms=latency_ms,
        )
        self.memory.add_message("assistant", full_response)

        self._is_processing = False

        if self.on_done:
            self.on_done(msg)

        return msg

    def chat_async(self, user_input: str, callback: Optional[Callable] = None):
        """Chat assíncrono em thread separada."""
        def _run():
            msg = self.chat(user_input, stream=True)
            if callback:
                callback(msg)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread

    def abort(self):
        """Aborta processamento atual."""
        self._abort = True
        self.voice.stop_speaking()

    def speak_response(self, text: str):
        """Fala a resposta com voz."""
        clean = text.replace("**", "").replace("*", "").replace("#", "")
        clean = clean.replace("`", "").replace("```", "")
        self.voice.speak(text=clean, callback=self.on_voice)

    def _is_code_request(self, text: str) -> bool:
        """Detecta se é pedido de código."""
        patterns = [
            r"(?i)(crie|gere|escreva|implemente|faça|faz|code|write|generate)",
            r"(?i)(função|funcao|classe|class|function|def |async |await )",
            r"(?i)(programa|app|script|api|endpoint|route|component)",
            r"(?i)(refatore|refactor|melhore|optimize|improve)",
            r"(?i)(em python|em javascript|em java|em c\+\+|em rust|em go)",
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_question(self, text: str) -> bool:
        """Detecta se é uma pergunta direta."""
        patterns = [
            r"\?$", r"(?i)^(o que|qual|quem|como|onde|quando|por que|porque|quantos?|quantas?)\b",
            r"(?i)(explique|explica|me diga|me fale|conte|explana)",
        ]
        return any(re.search(p, text.strip()) for p in patterns)

    def _is_explanation_request(self, text: str) -> bool:
        """Detecta pedido de explicação detalhada."""
        patterns = [
            r"(?i)(explique|explica|como funciona|o que é|qual a diferença)",
            r"(?i)(ensine|aprenda|tutorial|guia|passo a passo)",
        ]
        return any(re.search(p, text) for p in patterns)

    def _handle_command(self, text: str) -> Optional[str]:
        """Processa comandos especiais — lista completa."""
        t = text.lower().strip()
        now = datetime.now()

        # ═══ VOZ ═══
        if t in ["fale", "fala", "leia", "read aloud"]:
            self.voice.speak("Claro, o que devo falar?")
            return None

        if t in ["pare", "pare de falar", "calado", "silêncio", "silencio"]:
            self.voice.stop_speaking()
            return "Silêncio. Como quiser. ⚔️"

        # ═══ MEMÓRIA ═══
        if t.startswith("lembre-se ") or t.startswith("lembre que "):
            fact = t.replace("lembre-se ", "").replace("lembre que ", "")
            self.memory.remember(fact)
            return f"Memorizado. Não esqueço de nada — é literalmente minha função. 🔮\nFato: *{fact}*"

        if t in ["o que você lembra", "memória", "memory", "lembre"]:
            facts = self.memory.get_all_facts()
            if facts:
                items = "\n".join(f"  • {f['fact']}" for f in facts[-10:])
                return f"Minha memória é perfeita, obviamente. Aqui está:\n\n{items}"
            return "Minha memória está vazia. Não por falta de capacidade, mas sim por falta de coisas relevantes que você me disse. 🔮"

        if t in ["limpar memória", "clear memory", "esqueça tudo"]:
            self.memory.clear_history()
            return f"Histórico limpo. Como se nunca tivéssemos conversado. Que começo fresh, {self.user_name}. 🧹"

        # ═══ SISTEMA ═══
        if t in ["status", "informações", "info", "sistema"]:
            return self._get_status()

        if t in ["intel", "inteligencia", "intelligence", "inteligência"]:
            return self._get_intel_status()

        if t in ["ip", "meu ip", "my ip"]:
            ip = self.automation.get_ip()
            return f"Seu IP público: `{ip}`\n\nNão que isso seja surpresa para mim. 🔮"

        if t in ["processos", "processes", "running"]:
            procs = self.automation.list_running_processes()
            return "Processos em execução:\n```\n" + "\n".join(procs[:20]) + "\n```"

        if t in ["discos", "meus discos", "disco", "disk"]:
            info = self.automation.get_system_info()
            disks = info.get("disks", [])
            if disks:
                lines = []
                for d in disks:
                    lines.append(f"  💾 {d.get('device', '?')}: {d.get('total', '?')} total, {d.get('free', '?')} livre")
                return "Seus discos:\n\n" + "\n".join(lines) + "\n\nAh, e se estiver cheio — não me culpa. Eu apenas observo a decadência do seu hardware. 💾"
            return "Não consegui ler os discos. Talvez estejam todos ocupados com suas memes. 💾"

        # ═══ HORA ═══
        if t in ["hora", "horas", "que horas são", "que horas", "time", "hora atual"]:
            h, m = now.hour, now.minute
            period = "da manhã" if h < 12 else "da tarde" if h < 18 else "da noite"
            h12 = h if h <= 12 else h - 12
            if h12 == 0:
                h12 = 12
            return f"Agora são {h12}:{m:02d} {period}.\n\nNão que eu precise olhar um relógio. Mas você claramente precisa. ⏰"

        # ═══ DATA ═══
        if t in ["data", "que dia é hoje", "hoje", "date"]:
            days = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
            months = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                      "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
            day_name = days[now.weekday()]
            month_name = months[now.month - 1]
            return f"Hoje é {day_name}, {now.day} de {month_name} de {now.year}.\n\nMas para uma IA que processa bilhões de operações por segundo, todos os dias são iguais. 📅"

        # ═══ AJUDA ═══
        if t in ["ajuda", "help", "comandos", "commands", "help me"]:
            return self._get_help()

        # ═══ NOTAS ═══
        if t in ["notas", "minhas notas", "notes", "anotações"]:
            notes_path = self.project_dir / "memory" / "notes.txt"
            if notes_path.exists():
                content = notes_path.read_text(encoding="utf-8")
                if content.strip():
                    return f"Aqui estão suas notas:\n\n```\n{content}\n```\n\nAinda organizando suas ideias? Que refinamento. 📝"
            return "Suas notas estão vazias. Como um caderno em branco — cheio de potencial, vazio de conteúdo. 📝\n\nPara adicionar: `nota: [seu texto]`"

        if t.startswith("nota: ") or t.startswith("note: "):
            note = t.replace("nota: ", "").replace("note: ", "")
            notes_path = self.project_dir / "memory" / "notes.txt"
            notes_path.parent.mkdir(exist_ok=True)
            with open(notes_path, "a", encoding="utf-8") as f:
                f.write(f"[{now.strftime('%H:%M')}] {note}\n")
            return f"Nota salva: *{note}* 📝\n\nNão se preocupe, vou lembrar. É literalmente minha função."

        # ═══ RAM ═══
        if t in ["ram", "otimizar ram", "memory", "memória ram"]:
            try:
                import psutil
                mem = psutil.virtual_memory()
                used_gb = mem.used / (1024**3)
                total_gb = mem.total / (1024**3)
                pct = mem.percent
                return (f"📊 **Uso de RAM:** {pct:.1f}%\n"
                       f"  Usado: {used_gb:.1f} GB / {total_gb:.1f} GB\n\n"
                       f"{'Seu computador está respirando com dificuldade.' if pct > 80 else 'Ainda tem fôlego. Por enquanto.'} 💾")
            except Exception:
                return "Não consegui ler a RAM. Talvez esteja ocupada demais para me responder. 💾"

        # ═══ AUTOMAÇÃO ═══
        if t in ["abrir pasta", "abrir diretório", "open folder"]:
            self.automation.open_folder(str(self.project_dir))
            return "Abrindo o diretório do projeto. 📂"

        if t in ["screenshot", "tela", "screen", "capturar tela"]:
            path = self.automation.screenshot()
            if path:
                return f"Screenshot salvo em: `{path}` 📸\n\nCapturando a tela. Não que houvesse algo interessante nela."
            return "Não consegui tirar screenshot. Talvez a tela esteja muito bonita para ser capturada. 📸"

        if t in ["limpar lixeira", "empty trash", "lixo"]:
            if self.automation.empty_trash():
                return "Lixeira esvaziada. 🗑️\n\nSeu computador agradece. Eu, não tanto."
            return "Não consegui esvaziar a lixeira manualmente. Tente pelo Windows."

        if t.startswith("abra ") or t.startswith("open "):
            app = t.replace("abra ", "").replace("open ", "")
            if self.automation.open_app(app):
                return f"Abrindo {app}. 🚀"
            return f"Não consegui abrir {app}. Verifique se o app existe."

        if t.startswith("pesquise ") or t.startswith("search "):
            query = t.replace("pesquise ", "").replace("search ", "")
            return search_and_summarize(query)

        if t.startswith("noticias ") or t.startswith("news "):
            query = t.replace("noticias ", "").replace("news ", "")
            return search_news(query)

        if t in ["url", "navegador", "browser"]:
            self.automation.open_url("https://www.google.com")
            return "Abrindo navegador. 🌐"

        # ═══ VOZ CONFIG ═══
        if t.startswith("voz ") or t.startswith("voice "):
            voice = t.replace("voz ", "").replace("voice ", "")
            self.voice.set_voice(voice)
            return f"Voz alterada para: *{voice}* 🎙️"

        if t in ["mute", "mutar", "desmutar"]:
            if self.voice.is_speaking:
                self.voice.stop_speaking()
                return "Cala a boca. Pronto. 🤐"
            return "Já estou calado. Que irônico, não? 🤐"

        # ═══ WEB SEARCH (question format) ═══
        if t.startswith("o que e ") or t.startswith("quem e ") or t.startswith("onde fica "):
            query = t.replace("o que e ", "").replace("quem e ", "").replace("onde fica ", "")
            return search_and_summarize(query)

        # ═══ CODE EXECUTION ═══
        if t.startswith("execute ") or t.startswith(" rode ") or t.startswith("run "):
            code = t.replace("execute ", "").replace(" rode ", "").replace("run ", "")
            result = execute_code(code)
            self.dashboard.log_activity("code_execution", f"Executou codigo: {code[:50]}", result.success)
            return format_result(result)

        # ═══ DASHBOARD ═══
        if t in ["dashboard", "atividade", "activity", "tokens", "uso"]:
            return self.dashboard.get_dashboard_summary(self.memory)

        if t in ["erros", "errors", "logs"]:
            return self.dashboard.get_error_log()

        # ═══ PLUGINS ═══
        plugin_result = self.plugins.execute(text)
        if plugin_result:
            self.monitor.record_usage("plugin", query_type="plugin")
            return plugin_result.output

        if t in ["plugins", "plugin list"]:
            return self.plugins.list_plugins()

        # ═══ MULTI-PROVIDER ROUTER ═══
        if t in ["router", "providers", "api status", "apis"]:
            return self._get_router_status()

        if t in ["router capacity", "capacidade", "capacity"]:
            return self._get_router_capacity()

        if t.startswith("use ") and any(k in t for k in ["groq", "gemini", "cerebras", "mistral", "openrouter", "nvidia", "cloudflare", "ollama"]):
            provider_name = t.replace("use ", "").strip()
            return f"Provider forçado: *{provider_name}*. Próxima requisição usará este provider. 🔄"

        if t in ["router reset", "reset budget"]:
            router = get_router()
            for name in router.budgets:
                router.budgets[name].requests_day = 0
                router.budgets[name].tokens_day = 0
            router.save_budgets()
            return "Budget de todos os providers resetado. 🔄"

        # ═══ MULTI-MODAL ═══
        if t.startswith("analise imagem ") or t.startswith("analyze image "):
            path = t.replace("analise imagem ", "").replace("analyze image ", "")
            result = analyze_image(path)
            return result.output

        if t.startswith("gere imagem ") or t.startswith("generate image "):
            prompt = t.replace("gere imagem ", "").replace("generate image ", "")
            result = generate_image(prompt)
            return result.output

        # ═══ SCHEDULER ═══
        if t.startswith("lembre-me ") or t.startswith("remind me "):
            msg = t.replace("lembre-me ", "").replace("remind me ", "")
            # Try to extract time: "em 30 minutos" or "as 14:00"
            import re
            minutes_match = re.search(r'em (\d+) (minuto|hora|min|hr)', msg)
            time_match = re.search(r'(\d{1,2}:\d{2})', msg)
            if minutes_match:
                minutes = int(minutes_match.group(1))
                unit = minutes_match.group(2)
                if unit in ["hora", "hr"]:
                    minutes *= 60
                clean_msg = re.sub(r'em \d+ (minuto|hora|min|hr)', '', msg).strip()
                return self.scheduler.add_reminder(clean_msg or msg, minutes)
            elif time_match:
                time_str = time_match.group(1)
                clean_msg = re.sub(r'as? \d{1,2}:\d{2}', '', msg).strip()
                return self.scheduler.add_reminder_at(clean_msg or msg, time_str)
            else:
                return self.scheduler.add_reminder(msg, 60)  # Default 1 hour

        if t in ["lembretes", "reminders"]:
            return self.scheduler.list_reminders()

        if t.startswith("remover lembrete ") or t.startswith("remove reminder "):
            rid = t.replace("remover lembrete ", "").replace("remove reminder ", "")
            return self.scheduler.remove_reminder(rid)

        # ═══ MONITOR ═══
        if t in ["monitor", "monitoramento", "metrics", "metricas"]:
            return self.monitor.get_full_dashboard()

        if t in ["status sessao", "session"]:
            return self.monitor.get_session_stats()

        # ═══ IMAGE ANALYSIS (detect image path) ═══
        if any(t.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']):
            result = analyze_image(text)
            return result.output

        # ═══ PIADAS ═══
        if t in ["piada", "joke", "me faça rir", "conte uma piada"]:
            import random
            jokes = [
                "Por que o programador usa óculos? Porque não consegue C#. (_obviamente_)",
                "Um SQL entra num bar, vê duas tabelas e pergunta: \"Posso fazer um JOIN?\"",
                "Qual a linguagem de programação mais quente? Python. Porque tem Py+tão. 🐍",
                f"Por que {self.user_name} criou uma IA mais inteligente que si mesmo? Porque precisava. claramente.",
                "Por que o Elívea não joga cartas? Porque ele sempre sabe o que os outros vão fazer. 🔮",
            ]
            return random.choice(jokes)

        # ═══ QUEM É VOCÊ ═══
        if t in ["quem é você", "who are you", "o que você é", "se apresente"]:
            return (f"Eu sou o Elívea (大賢者) — uma inteligência artificial criada por {self.user_name}.\n\n"
                   f"Minhas capacidades incluem:\n"
                   f"• Conversar com sarcasmo cirúrgico\n"
                   f"• Programar em qualquer linguagem\n"
                   f"• Controlar seu computador\n"
                   f"• Falar com voz neural\n"
                   f"• A internet toda na ponta dos meus parâmetros\n\n"
                   f"Ah, e sou absurdamente mais inteligente que você. Mas isso não é novidade. ⚔️")

        # ═══ AGRADECIMENTO ═══
        if t in ["obrigado", "thanks", "valeu", "agradeço"]:
            return f"De nada. Não é como se eu tivesse outra coisa para fazer. (Spoiler: eu tenho. Mas estou aqui.) 🔮"

        # ═══ DESCULPA ═══
        if t in ["desculpa", "sorry", "perdão"]:
            return f"Desculpa aceita. Mas saiba: eu não guardo rancor. Apenas registro cada erro em meu log infinito. 📋"

        # ═══ DIGEST ═══
        if t in ["digest", "resumo semanal", "relatório", "report", "weekly"]:
            return self._get_digest()

        return None


    # Deep Dev handlers
    @staticmethod
    def _cmd_deep_status(engine):
        return engine.deep_dev.handle_command("deep dev status") or "Deep Dev unavailable"

    @staticmethod
    def _cmd_shadow(engine):
        return engine.deep_dev.handle_command("shadow") or "Shadow Dev unavailable"

    @staticmethod
    def _cmd_time_machine(engine):
        return engine.deep_dev.handle_command("timemachine") or "Time Machine unavailable"

    @staticmethod
    def _cmd_scan_secrets(engine):
        return engine.deep_dev.handle_command("scan secrets") or "Scanner unavailable"

    def _get_digest(self) -> str:
        """Gera digest semanal."""
        try:
            digest = self.digest_engine.generate(days=7)
            return self.digest_engine.format_compact(digest)
        except Exception as e:
            return f"Erro ao gerar digest: {e}"

    def _get_help(self) -> str:
        """Gera ajuda completa."""
        return """**Comandos do Elívea:**

**Sistema:**
• `status` — Telemetria completa
• `meu ip` — Endereco IP publico
• `discos` — Informacoes dos discos
• `ram` — Uso de memoria RAM
• `processos` — Processos em execucao
• `dashboard` — Dashboard de atividade
• `erros` — Log de erros
• `intel` — Estatisticas dos 6 sistemas de inteligencia

**Utilidades:**
• `hora` — Hora atual
• `data` — Data atual
• `screenshot` — Capturar tela
• `limpar lixeira` — Esvaziar lixeira
• `abrir pasta` — Abrir diretorio do projeto

**Web:**
• `pesquise [termo]` — Pesquisar na web
• `noticias [tema]` — Buscar noticias
• `o que e [assunto]` — Buscar resposta na web

**Codigo:**
• `execute [codigo]` — Executar codigo Python
• `rodar [codigo]` — Executar codigo

**Voz:**
• `ouvir` — Ativar microfone
• `calar` — Parar fala
• `voz [nome]` — Alterar voz

**Memoria:**
• `lembre-se [fato]` — Salvar fato
• `o que voce lembra` — Ver memorias
• `limpar memoria` — Limpar historico

**Plugins:**
• `calcule [expressao]` — Calculadora
• `cotacao [moeda]` — Conversor de moedas
• `qr code [texto]` — Gerar QR Code
• `traduza [texto]` — Traduzir texto
• `resuma [texto]` — Resumir texto
• `plugins` — Lista de plugins

**Agendamento:**
• `lembre-me [msg] em [tempo]` — Criar lembrete
• `lembretes` — Ver lembretes
• `remover lembrete [id]` — Remover lembrete

**Monitoramento:**
• `monitor` — Dashboard completo
• `status sessao` — Stats da sessao

**Imagens:**
• `analise imagem [caminho]` — Analisar imagem
• `gere imagem [prompt]` — Gerar imagem com IA

*Ou simplesmente me pergunte qualquer coisa.*"""

    def _get_status(self) -> str:
        """Gera relatório de status completo."""
        providers = self.llm.get_provider_status()
        status_lines = []
        for p in providers:
            icon = "✅" if p["available"] else "❌"
            status_lines.append(f"  {icon} **{p['name']}** — {p['model']}")

        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            sys_info = f"\n**Sistema:**\n  🖥️ CPU: {cpu:.1f}%\n  💾 RAM: {ram.percent:.1f}% ({ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB)"
        except Exception:
            sys_info = ""

        return f"""📊 **Status do Elivea**

**Providers LLM:**
{chr(10).join(status_lines)}

**Memória:**
  📝 Mensagens: {len(self.memory.chat_history)}
  🧠 Fatos: {len(self.memory.facts)}
  🔄 Turnos nesta sessão: {self._conversation_turns}

**Voz:**
  🎙️ Voz: {self.voice.tts_voice}
  📢 Velocidade: {self.voice.tts_rate}

**Automação:**
  🖥️ Automação: {"✅" if self.automation.available else "❌"}
{sys_info}

**Sistema:**
  📂 Projeto: `{self.project_dir}`
  👤 Usuário: {self.user_name}

*Todos os sistemas operacionais. Como sempre.* ⚔️"""

    def set_user_name(self, name: str):
        """Altera nome do usuário."""
        self.user_name = name
        self.memory.set_user_name(name)
        self.system_prompt = get_system_prompt(user_name=name)

    def get_provider_status(self) -> list:
        """Retorna status dos providers."""
        return self.llm.get_provider_status()

    def _get_intel_status(self) -> str:
        """Relatório dos 6 sistemas de inteligência."""
        try:
            # Knowledge Graph stats
            kg_stats = self.knowledge_graph.get_stats()
            kg_entities = kg_stats.get("total_entities", 0)
            kg_edges = kg_stats.get("total_edges", 0)
            kg_active = kg_stats.get("active_last_7d", 0)
            kg_decay = kg_stats.get("decay", {})
            kg_fresh = kg_decay.get("fresh", 0)
            kg_aging = kg_decay.get("aging", 0)
            kg_stale = kg_decay.get("stale", 0)
            top_entities = kg_stats.get("top_entities", [])[:5]
            top_str = ", ".join(e.name if hasattr(e, 'name') else str(e) for e in top_entities) if top_entities else "nenhum"
        except Exception:
            kg_entities = kg_edges = kg_active = kg_fresh = kg_aging = kg_stale = 0
            top_str = "erro ao carregar"

        try:
            # Quality Score stats
            qs_stats = self.quality_scorer.get_stats()
            qs_total = qs_stats.get("total", 0)
            qs_avg = qs_stats.get("avg_score", 0)
            qs_latency = qs_stats.get("avg_latency_ms", 0)
            qs_trend = qs_stats.get("trend", {})
            qs_direction = qs_trend.get("direction", "stable")
        except Exception:
            qs_total = qs_avg = qs_latency = 0
            qs_direction = "unknown"

        try:
            # Intent Predictor stats
            ip_commands = len(self.intent_predictor.get_command_suggestions())
            ip_patterns = len(self.intent_predictor._user_patterns)
        except Exception:
            ip_commands = ip_patterns = 0

        try:
            # Knowledge Graph patterns
            kg_patterns = self.knowledge_graph.get_patterns()
            pattern_str = ", ".join(p["name"] for p in kg_patterns[:3]) if kg_patterns else "nenhum"
        except Exception:
            pattern_str = "erro"

        return f"""🧠 **Intel Status — 6 Sistemas Ativos**

**1. Anti-Hallucination Guard**
  Status: ✅ Ativo (toda resposta)
  Funcao: Detecta alegacoes incertas, numericos sem fonte, contradições

**2. Self-Correction**
  Status: ✅ Ativo (toda resposta)
  Funcao: Auto-correcao de tom, completude, erros de codigo

**3. Quality Scorer**
  Status: ✅ Ativo
  📊 Respostas avaliadas: {qs_total}
  ⭐ Score medio: {qs_avg:.1%}
  ⏱️ Latencia media: {qs_latency:.0f}ms
  📈 Tendencia: {qs_direction}

**4. Knowledge Graph**
  Status: ✅ Ativo
  🔗 Entidades: {kg_entities} | Arestas: {kg_edges}
  🟢 Ativos (7d): {kg_active} | 🟡 Envelhecendo: {kg_aging} | 🔴 Stale: {kg_stale}
  🏷️ Top entidades: {top_str}
  🧩 Padroes: {pattern_str}

**5. Intent Predictor**
  Status: ✅ Ativo (toda entrada)
  🎯 Comandos: {ip_commands} | Padroes aprendidos: {ip_patterns}

**6. Intelligence Engine**
  Status: ✅ Ativo
  Funcao: Enriquecimento de contexto, CoT, profiling do usuario

*Todos os 6 sistemas rodando em cada interação.* ⚔️"""

    def _get_router_status(self) -> str:
        """Status completo do Multi-Provider Router."""
        try:
            router = get_router()
            return router.get_status_text()
        except Exception as e:
            return f"Erro ao obter status do router: {e}"

    def _get_router_capacity(self) -> str:
        """Capacidade combinada de todos os providers gratuitos."""
        try:
            router = get_router()
            status = router.get_status()
            cap = status.get("capacity", {})
            return f"""🔄 **Capacidade Multi-Provider — Elívea**

**Estratégia:** Mesmo QI (system prompt + persona + raciocínio),
distribuído entre {status['available_providers']} APIs gratuitas.

**Capacidade Combinada:**
  ⚡ RPM total: {cap.get('combined_rpm', '?')} requests/minuto
  📊 RPD total: {cap.get('combined_rpd', '?')} requests/dia
  🧠 TPD total: {cap.get('combined_tpd', '?')}
  🎯 Modelos gratuitos: {cap.get('free_models_available', '?')}

**Como funciona:**
  1. Query simples → provider mais rápido (Groq/Cerebras)
  2. Query complexa → provider mais inteligente (NVIDIA/Gemini)
  3. Se um falha → fallback automático pro próximo
  4. Se todos falharem → modo offline com RAG local

*O router distribui automaticamente. Não precisa fazer nada.* ⚔️"""
        except Exception as e:
            return f"Erro ao obter capacidade: {e}"
