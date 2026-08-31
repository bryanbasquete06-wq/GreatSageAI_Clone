# -*- coding: utf-8 -*-
"""SmartCodeAgent v2 — Ala de Programação AUTÔNOMA, ilimitada e de raciocínio de elite.

Subclasse de CodeAgent que supera ZCode/Cursor com 6 capacidades:

  1. PROVIDER OLLAMA-FIRST: Ollama (GRÁTIS/ilimitado) → Groq → OpenRouter → DeepSeek.
     Nunca gasta um centavo quando Ollama está disponível.

  2. CODEINDEX — recuperação semântica injeta trechos relevantes no contexto.
     Repos ARBITRARIAMENTE GRANDES dentro de um contexto finito.

  3. AUTO-PROGRAMAÇÃO: flag self_program relaxa sandbox para self-modification.

  4. CONTEXTO INTELIGENTE: compressão de histórico (resume tool outputs antigos),
     trimming adaptativo, e priorização de informações relevantes.

  5. AUTO-APRENDIZADO: registra padrões de sucesso/fracasso para melhorar
     decisões futuras (qual provider usar, quando parar, etc).

  6. MAX_STEPS ADAPTATIVO: tarefas simples = menos passos, complexos = mais.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from modules.code_agent import (
    CodeAgent, AGENT_SYSTEM_PROMPT, MAX_STEPS, MAX_TOKENS, CONTEXT_BUDGET,
    READ_LIMIT, OUTPUT_LIMIT, SEARCH_LIMIT,
)

# --------------------------------------------------------------------------- #
# Memória de aprendizado do agente (persistente entre sessões)
# --------------------------------------------------------------------------- #

MEMORY_DIR = Path(__file__).resolve().parent.parent / "config" / "agent_memory"
LEARNING_FILE = MEMORY_DIR / "learning.json"


def _load_learning() -> dict:
    """Carrega memória de aprendizado (provider performance, padrões de sucesso)."""
    try:
        if LEARNING_FILE.exists():
            return json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {
        "provider_scores": {}, # provider -> {success: int, fail: int, avg_time: float}
        "task_patterns": {}, # pattern -> {success: int, fail: int}
        "total_runs": 0,
        "total_improvements": 0,
    }


def _save_learning(data: dict):
    """Salva memória de aprendizado (não bloqueante)."""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LEARNING_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    except Exception:
        pass


def _record_provider_score(provider_name: str, success: bool, elapsed: float):
    """Registra performance de um provider para decisão futura."""
    data = _load_learning()
    scores = data.setdefault("provider_scores", {})
    p = scores.setdefault(provider_name, {"success": 0, "fail": 0, "total_time": 0.0})
    if success:
        p["success"] = p.get("success", 0) + 1
    else:
        p["fail"] = p.get("fail", 0) + 1
    p["total_time"] = p.get("total_time", 0.0) + elapsed
    _save_learning(data)


def _get_best_provider() -> str | None:
    """Retorna o provider com melhor score histórico (para decisões futuras)."""
    data = _load_learning()
    scores = data.get("provider_scores", {})
    if not scores:
        return None
    best = None
    best_score = -1
    for name, s in scores.items():
        total = s.get("success", 0) + s.get("fail", 0)
        if total < 3:
            continue # precisa de pelo menos 3 tentativas
        score = s.get("success", 0) / total
        if score > best_score:
            best_score = score
            best = name
    return best


# --------------------------------------------------------------------------- #
# System prompts
# --------------------------------------------------------------------------- #

DEFAULT_CODER_PROMPT = (
    "Especialista em refatoração, testes e correção de bugs. Progrida com calma, "
    "verifique compilação/tests a cada passo e nunca deixe o build quebrado."
)


# --------------------------------------------------------------------------- #
# SmartCodeAgent v2
# --------------------------------------------------------------------------- #

class SmartCodeAgent(CodeAgent):
    """Loop agêntico de programação de raciocínio de elite + recursos avançados.

    Compatível com o CodeAgent legado: quando não há provider (testes com mock),
    delega para o cliente Groq do llm.
    """

    def __init__(self, llm=None, workspace: Path | str = ".", on_step=None, max_tokens=None,
                 provider=None, self_program: bool = False, reasoning: bool = True,
                 index=None, system_prompt_extra: str = "", max_steps: int | None = None,
                 max_action_log: int = 4000, adaptive_steps: bool = True):
        super().__init__(llm, workspace, on_step=on_step, max_tokens=max_tokens)
        self.provider = provider
        self.self_program = self_program
        self.reasoning = reasoning
        self.max_steps = max_steps or MAX_STEPS
        self._base_max_steps = self.max_steps
        self.adaptive_steps = adaptive_steps
        self.max_action_log = max_action_log
        self.index = index
        self.system_prompt_extra = system_prompt_extra or ""
        self._step_times: list[float] = []
        self._errors_in_row = 0

    # ----------------------------------------------------------------- helpers

    def _resolve_provider(self):
        """Resolve o provider: Ollama (grátis) > Groq (grátis) > Gemini (grátis) > OpenRouter (grátis)."""
        if self.provider is not None and self.provider.available():
            return self.provider
        try:
            from core.providers import resolve_code_provider
            p = resolve_code_provider(self.llm)
            if p is not None:
                self.provider = p
            return p
        except Exception:
            return None

    def _inside(self, p: Path) -> bool:
        if self.self_program:
            return True
        try:
            p.relative_to(self.workspace)
            return True
        except ValueError:
            return False

    @property
    def _api_max_tokens(self):
        return self.max_tokens if (self.max_tokens and self.max_tokens > 0) else None

    # ---------------------------------------------------------------- context

    def _compress_history(self, messages: list[dict]):
        """Comprime o histórico: resume tool outputs antigos em resumos curtos.

        Mantém as últimas 4 interações completas, e resume o resto em bullets.
        Isso permite loops longos (50+ steps) sem estourar o contexto.
        """
        if len(messages) <= 10:
            return # pouco histórico, nada a comprimir

        # preserva: system + contexto index + primeira tarefa + últimas 8 mensagens
        preserve_until = 3 # system + context + user_task
        keep_recent = 8

        if len(messages) <= preserve_until + keep_recent:
            return

        old = messages[preserve_until:-keep_recent]
        recent = messages[-keep_recent:]

        # resume outputs antigos em bullets compactos
        compressed = []
        for msg in old:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and content.startswith("RESULTADO DE "):
                # comprime resultado de tool: mantém só nome + primeiras linhas
                lines = content.split("\n")
                tool_name = lines[0].replace("RESULTADO DE ", "") if lines else "?"
                summary = "\n".join(lines[1:4]) # primeiras 3 linhas
                if len(lines) > 4:
                    summary += f"\n...({len(lines)} linhas total)"
                compressed.append({"role": "user",
                                   "content": f"[{tool_name} — resultado comprimido]\n{summary}"})
            elif role == "assistant":
                # mantém apenas a tool choice, não o JSON completo
                try:
                    a = json.loads(content)
                    compact = {"tool": a.get("tool"), "path": a.get("path", "")}
                    compressed.append({"role": "assistant",
                                       "content": json.dumps(compact, ensure_ascii=False)})
                except Exception:
                    compressed.append({"role": "assistant", "content": content[:300]})
            else:
                compressed.append(msg)

        # reconstrói: preservado + comprimido + recente
        messages[:] = messages[:preserve_until] + compressed + recent

    def _trim_history(self, messages: list[dict], budget: int = CONTEXT_BUDGET):
        """Mantém o contexto no orçamento — compressão primeiro, depois corte."""
        # primeiro tenta comprimir
        self._compress_history(messages)

        # depois verifica se ainda passa do budget
        i = 2
        try:
            while i + 1 < len(messages):
                total = sum(len(str(m.get("content", ""))) for m in messages)
                if total <= budget:
                    break
                if messages[i].get("role") == "assistant" and messages[i + 1].get("role") == "user":
                    del messages[i:i + 2]
                else:
                    break
        except Exception:
            pass

    # ----------------------------------------------------------------- adaptive

    def _adapt_steps(self, task: str, step: int, last_tool: str, result: str):
        """Adapta max_steps exponencialmente baseado no progresso e complexidade."""
        if not self.adaptive_steps:
            return

        # Exponential scaling: se está progredindo bem, dobra o limite
        progress_ratio = step / self.max_steps
        if progress_ratio > 0.6 and "finish" not in last_tool:
            # Tarefa complexa detectada — escala exponencial
            new_limit = min(int(self.max_steps * 1.5), self._base_max_steps * 4)
            if new_limit > self.max_steps:
                self.max_steps = new_limit
                self._notify(f" tarefa complexa — limite expandido para {self.max_steps} passos\n")

        # Anti-loop inteligente: para após 3 erros consecutivos OU se o mesmo tool
        # falhou 3 vezes seguidas
        if "ERRO" in result:
            self._errors_in_row += 1
            if self._errors_in_row >= 3:
                self._notify("! 3 erros consecutivos — interrompendo para evitar loop\n")
                self.max_steps = step
        else:
            self._errors_in_row = max(0, self._errors_in_row - 1)

    # -------------------------------------------------------------------- llm

    def _llm_call(self, messages, client=None, max_tokens=None, reasoning=False):
        """Provider (preferido) ou cliente Groq/mock legado (compat)."""
        api_mt = max_tokens if (max_tokens and max_tokens > 0) else None
        provider = self.provider
        if provider is not None:
            try:
                r = provider.complete(messages, max_tokens=api_mt, reasoning=reasoning)
                if getattr(r, "reasoning", ""):
                    self._notify(f" raciocínio: {(r.reasoning or '')[:1500]}\n")
                try:
                    if self.llm is not None:
                        self.llm.last_model = r.model
                except Exception:
                    pass
                return r.content
            except Exception as e:
                self._notify(f" provider {provider.name} falhou ({e}); tentando fallback\n")
                self.provider = None
                provider = None
        # fallback legado: cliente Groq/mock
        if client is None and self.llm is not None and hasattr(self.llm, "_ensure_groq_client"):
            client = self.llm._ensure_groq_client()
        if client is None:
            return None
        try:
            models = self.llm._groq_models()
        except Exception:
            models = ["openai/gpt-oss-20b"]
        for model in models:
            try:
                extra = ({"reasoning_effort": "high", "reasoning_format": "hidden"}
                         if "gpt-oss" in model else {})
                kw = dict(messages=messages, model=model, temperature=0.2,
                          timeout=120.0, response_format={"type": "json_object"}, **extra)
                if api_mt:
                    kw["max_tokens"] = api_mt
                call = client.chat.completions.create(**kw)
                try:
                    self.llm.last_model = model
                except Exception:
                    pass
                return call.choices[0].message.content or ""
            except Exception as e:
                self._notify(f" modelo {model} falhou ({e}); tentando próximo\n")
        return None

    # -------------------------------------------------------------------- loop

    def run(self, task: str, stop_event=None) -> tuple[str, str]:
        provider = self._resolve_provider()
        client = None if provider is not None else (
            self.llm._ensure_groq_client()
            if (self.llm is not None and hasattr(self.llm, "_ensure_groq_client")) else None)
        if provider is None and client is None:
            msg = ("Aviso. Modo programador indisponível: sem núcleo neural "
                   "(Groq/OpenRouter/DeepSeek/Ollama). Verifique as chaves de API.")
            return msg, msg

        system = AGENT_SYSTEM_PROMPT.format(workspace=str(self.workspace),
                                            max_steps=self.max_steps)
        if self.system_prompt_extra:
            system += "\n\nDIRETRIVAS DESTE AGENTE:\n" + self.system_prompt_extra
        if self.self_program:
            system += ("\n\nAUTO-PROGRAMAÇÃO ATIVADA: você pode modificar os próprios "
                       "arquivos do sistema e arquivos fora do workspace — verifique "
                       "consistência antes de deletar/renomear.")

        # injeta memória de aprendizado
        learning = _load_learning()
        if learning.get("total_improvements", 0) > 0:
            system += (f"\n\nMEMÓRIA DE APRENDIZADO: {learning['total_improvements']} "
                       "melhorias já aplicadas com sucesso nesta codebase.")

        messages: list[dict] = [{"role": "system", "content": system}]
        if self.index is not None:
            ctx = ""
            try:
                ctx = self.index.query(task, k=12)
            except Exception:
                ctx = ""
            if ctx:
                messages.append({"role": "user", "content": (
                    "[Contexto auto-recuperado via CodeIndex — trechos relevantes; "
                    "evite read_file redundante.]\n\n" + ctx)})
        messages.append({"role": "user", "content": f"Tarefa do Mestre: {task}"})

        log: list[str] = []
        files_touched: set[str] = set()
        answer = ""
        t0 = time.perf_counter()
        self._notify(f"== SmartCodeAgent v2 iniciado — tarefa: {task}\n")
        provider_name = provider.name if provider else "groq-mock"
        provider_quality = getattr(provider, 'quality_score', 'N/A') if provider else "N/A"
        self._notify(f" provider: {provider_name} (qualidade: {provider_quality})"
                     + (" · raciocínio" if self.reasoning else "")
                     + f" · tokens/passo: {self.max_tokens or '∞'}"
                     + f" · max_steps: {self.max_steps}\n")

        step = 0
        consecutive_errors = 0
        while step < self.max_steps:
            step += 1
            if stop_event is not None and stop_event.is_set():
                answer = ("Tarefa interrompida a seu pedido, Mestre. "
                          "Os arquivos já alterados foram preservados.")
                break
            t_step = time.perf_counter()
            raw = self._llm_call(messages, client,
                                 max_tokens=self.max_tokens, reasoning=self.reasoning)
            self._step_times.append(time.perf_counter() - t_step)
            if raw is None:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self._notify("! provider indisponível após 3 tentativas; interrompendo.\n")
                    break
                self._notify(f" tentativa {consecutive_errors}/3 — retry em 2s...\n")
                time.sleep(2)
                continue
            consecutive_errors = 0
            try:
                action = json.loads(raw)
            except Exception:
                # Tenta extrair JSON de resposta mista
                import re
                json_match = re.search(r'\{[^{}]*"tool"\s*:\s*"[^"]*"[^{}]*\}', raw)
                if json_match:
                    try:
                        action = json.loads(json_match.group())
                    except Exception:
                        messages.append({"role": "assistant", "content": raw[:1500]})
                        messages.append({"role": "user", "content": (
                            "ERRO: sua resposta não foi JSON válido. "
                            "Responda APENAS com o objeto JSON da próxima ferramenta.")})
                        continue
                else:
                    messages.append({"role": "assistant", "content": raw[:1500]})
                    messages.append({"role": "user", "content": (
                        "ERRO: sua resposta não foi JSON válido. "
                        "Responda APENAS com o objeto JSON da próxima ferramenta.")})
                    continue
            tool = str(action.get("tool", "")).strip()
            messages.append({"role": "assistant", "content": json.dumps(action, ensure_ascii=False)})
            if tool == "finish":
                answer = str(action.get("answer", "")).strip()
                break
            result, human = self._exec_tool(tool, action, files_touched)
            log.append(human)
            self._notify(f" {human}\n")
            messages.append({"role": "user", "content": f"RESULTADO DE {tool}:\n{result}"})
            self._trim_history(messages)
            self._adapt_steps(task, step, tool, result)

        if not answer:
            answer = (f"Concluí o máximo possível dentro do limite de "
                      f"{self.max_steps} passos, Mestre.")

        elapsed = time.perf_counter() - t0
        self.last_action_count = len(log)

        # registra performance do provider
        _record_provider_score(provider_name, bool(answer), elapsed)
        data = _load_learning()
        data["total_runs"] = data.get("total_runs", 0) + 1
        _save_learning(data)

        if not answer:
            answer = "Encerrei o modo programador, Mestre."
        avg_step = sum(self._step_times) / len(self._step_times) if self._step_times else 0
        header = (f"== ALA DE PROGRAMAÇÃO (IA Super v2) — {len(log)} ações em "
                  f"{elapsed:.1f}s · {self.max_tokens or '∞'} tokens/passo"
                  f" · média/step: {avg_step:.1f}s\n")
        body = "\n".join(f"- {l}" for l in log[-50:]) if log else "- nenhuma ação necessária"
        report = f"{header}{body}\n\n{answer}"
        return report, answer


# --------------------------------------------------------------------------- #
# Multi-Agent: diversos agentes de programação, cada um com sua persona
# --------------------------------------------------------------------------- #

class MultiAgentPool:
    """Pool de agentes de programação nomeados (cria e aciona via prompt).

    pool = MultiAgentPool(llm, workspace)
    pool.create("revisor", "Releia e corrija bugs com rigor.")
    report, ans = pool.run("revisor", "revisa modules/code_agent.py")
    """
    def __init__(self, llm, workspace, defaults: dict | None = None, on_step=None):
        self.llm = llm
        self.workspace = workspace
        self.on_step = on_step
        self.agents: dict[str, SmartCodeAgent] = {}
        self.defaults = dict(defaults or {})

    def create(self, name: str, system_prompt: str = "", **overrides) -> SmartCodeAgent:
        kw = dict(self.defaults)
        kw.update(overrides)
        kw.setdefault("system_prompt_extra", system_prompt)
        self.agents[name] = SmartCodeAgent(
            llm=self.llm, workspace=self.workspace, on_step=self.on_step, **kw)
        return self.agents[name]

    def get(self, name: str) -> SmartCodeAgent | None:
        return self.agents.get(name)

    def run(self, name: str, task: str, stop_event=None, **overrides) -> tuple[str, str]:
        agent = self.agents.get(name)
        if agent is None:
            agent = self.create(name)
        for k, v in overrides.items():
            setattr(agent, k, v)
        return agent.run(task, stop_event=stop_event)

    def names(self) -> list[str]:
        return list(self.agents)
