"""
Great Sage AI - Smart LLM & Rule-Based Intent Engine (Optimized v2)
===================================================================
Parses natural spoken or typed Portuguese queries and executes real OS actions on Windows.

v2 optimizations:
  - Intent classification cache (LRU, 100 entries) — repeat commands instant
  - Precompiled regex patterns — faster first-time matching
  - Faster offline fallback with direct rule matching
"""

import re
import json
import time
import unicodedata
from collections import OrderedDict


def _norm(text: str) -> str:
    txt = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


class _IntentCache:
    """LRU cache de classificações de intenção com TTL de 2 minutos."""

    def __init__(self, max_size: int = 100, ttl: float = 120.0):
        self._cache: OrderedDict[str, tuple[tuple[str | None, dict], float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def _key(self, prompt: str) -> str:
        return _norm(prompt)

    def get(self, prompt: str) -> tuple[str | None, dict] | None:
        key = self._key(prompt)
        if key in self._cache:
            value, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                self._cache.move_to_end(key)
                return value
            del self._cache[key]
        return None

    def put(self, prompt: str, result: tuple[str | None, dict]):
        key = self._key(prompt)
        self._cache[key] = (result, time.time())
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


class IntentEngine:
    ACTIONS = {
        "clean_recycle_bin": [r'\b(lixeira|recycle)\b', r'\b(limp|esvaz|apag|limpe|esvazie)\b'],
        "boost_ram": [r'\b(ram|memoria|memória)\b', r'\b(otimiz|liber|limp|otimizar|liberar)\b'],
        "organize_desktop": [r'\b(desktop|trabalho|área de trabalho)\b', r'\b(organiz|arrum|organizar)\b'],
        "clean_temp_files": [r'\b(temp|temporarios|temporários|cache)\b', r'\b(limp|esvaz|limpar)\b'],
        "get_ip_info": [r'\b(ip|rede|conexao|conexão)\b', r'\b(meu|qual|status)\b'],
        "get_disk_info": [r'\b(disco|hd|ssd|armazenamento)\b', r'\b(meus|espaco|espaço|status)\b'],
        "take_screenshot": [r'\b(print|screenshot|captura|capturar)\b', r'\b(tela|print)\b'],
        "get_active_window": [r'\b(janela)\b', r'\b(ativa|foco|focada)\b'],
        "list_notes": [r'\b(notas|anotacoes|anotações)\b', r'\b(minhas|ver|listar)\b'],
        # Exige indicador de hora/data ATUAL — "que horas o jogo começa" NÃO casa (pat2)
        "get_datetime": [
            r'\b(que horas|que dia|as horas|a hora|a data|data e hora|horario atual|horário atual)\b',
            r'\b(sao|são|hoje|agora|atual|diga)\b',
        ],
        "show_history": [r'\b(historico|histórico|conversas)\b', r'\b(meu|ver|completo)\b'],
        "show_memory": [r'\b(memoria|memória|fatos)\b', r'\b(minha|oque|lembra)\b'],
        "self_program": [r'\b(auto|programe|codigos|código)\b', r'\b(se|melhorar|meus)\b']
    }

    # Precompiled regex patterns for faster matching
    _COMPILED_ACTIONS: dict[str, list[re.Pattern]] = {}

    # Palavras que indicam que a frase POSSO ser um comando de sistema.
    # Se nenhuma aparece, pulamos direto para o LLM principal — economiza uma
    # viagem completa à API (~0,4-1,5 s) em toda pergunta conversacional.
    _ACTION_HINTS = (
        # verbos de comando
        "abrir", "abra", "abre", "iniciar", "inicie", "fechar", "feche",
        "encerrar", "encerre", "kill", "limpar", "limpe", "limpa", "esvaziar",
        "esvazie", "apagar", "apague", "otimizar", "otimize", "otimiza",
        "liberar", "libere", "organizar", "organize", "arrumar", "arrume",
        "anotar", "anote", "salvar nota", "salve a nota", "pesquisar",
        "pesquise", "googlar", "capturar", "captura", "mutar", "silenciar",
        "bloquear", "reiniciar", "desligar", "criar pasta", "crie a pasta",
        "ler arquivo", "leia o arquivo", "executar", "rodar", "exec",
        "tocar", "toque", "toca", "ouvir", "colocar pra tocar",
        # nomes/apps específicos
        "google", "youtube", "notepad", "chrome", "screenshot", "print",
        "lixeira", "recycle", "ram", "cache", "desktop",
        # pedidos típicos por extenso
        "meu ip", "meus discos", "meu disco", "espaco no disco",
        "espaco em disco", "espaco livre", "que horas", "que dia",
        "data de hoje", "meu historico", "minhas notas", "ver notas",
        "arquivos temporarios", "area de trabalho", "janela ativa",
        "volume", "lembrete", "timer", "lembrar", "gravar memoria",
        # variações coloquiais / voz
        "abre", "fecha", "mata", "termina", "desliga o", "liga o",
        "coloca no", "bota no", "poe no", "põe no", "me mostra",
        "mostra meu", "mostra o", "qual e meu", "qual é meu",
        "tira print", "da um print", "dá um print", "faz print",
        "esvazia", "esvaziar", "deleta", "apaga tudo",
        "libera memoria", "libera memória", "melhora a ram",
        "status do pc", "status do sistema", "como ta o pc", "como está o pc",
        "silencia", "silencie", "muta", "mute", "aumenta volume", "abaixa volume",
        "bloqueia o pc", "reinicia o pc", "desliga o pc",
    )

    _ACTION_HINTS_SET: set[str] = set(_ACTION_HINTS)  # precomputed set for O(1) lookup

    _CLIENTS: dict = {}
    _intent_cache = _IntentCache()

    @classmethod
    def _ensure_compiled(cls):
        """Compile regex patterns once on first use."""
        if not cls._COMPILED_ACTIONS:
            for action_name, patterns in cls.ACTIONS.items():
                cls._COMPILED_ACTIONS[action_name] = [re.compile(pat) for pat in patterns]

    @classmethod
    def looks_like_action(cls, prompt: str) -> bool:
        """Heurística barata: a frase parece um comando de sistema?
        Usada para pular o classificador LLM em frases claramente conversacionais."""
        norm = _norm(prompt)
        if not norm:
            return False
        # Fast path: check if any word in prompt starts with an action hint
        words = norm.split()
        return any(any(h.startswith(w) or w.startswith(h) for w in words)
                   for h in cls._ACTION_HINTS_SET)

    @classmethod
    def match_intent(cls, prompt: str) -> tuple[str | None, dict]:
        # Check cache first
        cached = cls._intent_cache.get(prompt)
        if cached is not None:
            return cached

        cls._ensure_compiled()
        p_lower = prompt.lower().strip()

        # Check rule-based intent patterns first (using precompiled regex)
        for action_name, compiled_patterns in cls._COMPILED_ACTIONS.items():
            if all(pat.search(p_lower) for pat in compiled_patterns):
                result = (action_name, {})
                cls._intent_cache.put(prompt, result)
                return result

        # Check parametric intents
        if any(p_lower.startswith(w) for w in ["fechar ", "feche ", "encerrar ", "kill "]):
            target = re.sub(r'^(fechar|feche|encerrar|encerre|kill)\s+(o|a)?\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("kill_process", {"target": target})
            cls._intent_cache.put(prompt, result)
            return result

        if any(p_lower.startswith(w) for w in ["abrir ", "abra ", "iniciar ", "open "]):
            target = re.sub(r'^(abrir|abra|iniciar|inicie|open)\s+(o|a)?\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("open_app", {"target": target})
            cls._intent_cache.put(prompt, result)
            return result

        if p_lower.startswith("anotar ") or p_lower.startswith("salvar nota "):
            note = re.sub(r'^(anotar|salvar nota)\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("save_note", {"text": note})
            cls._intent_cache.put(prompt, result)
            return result

        if p_lower.startswith("google ") or "pesquisar no google" in p_lower or p_lower.startswith("pesquisar "):
            q = re.sub(r'^(google|pesquisar no google|pesquisar)\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("web_search", {"query": q})
            cls._intent_cache.put(prompt, result)
            return result

        if p_lower.startswith("youtube ") or "tocar no youtube" in p_lower:
            q = re.sub(r'^(youtube|tocar no youtube)\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("play_youtube", {"query": q})
            cls._intent_cache.put(prompt, result)
            return result

        if p_lower.startswith("ler arquivo ") or p_lower.startswith("leia o arquivo "):
            path = re.sub(r'^(ler arquivo|leia o arquivo)\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("read_file", {"path": path})
            cls._intent_cache.put(prompt, result)
            return result

        if p_lower.startswith("criar pasta ") or p_lower.startswith("crie a pasta "):
            folder = re.sub(r'^(criar pasta|crie a pasta)\s*', '', prompt, flags=re.IGNORECASE).strip()
            result = ("create_folder", {"folder": folder})
            cls._intent_cache.put(prompt, result)
            return result

        result = (None, {})
        cls._intent_cache.put(prompt, result)
        return result

    @classmethod
    def extract_intent_with_llm(cls, prompt: str, groq_key: str | None = None) -> tuple[str | None, dict]:
        """Fast LLM Intent Classifier Fallback via Groq GPT-OSS 20B (~150ms).

        Only runs when the utterance looks like a system command
        (`looks_like_action`); conversational questions skip straight to the
        main LLM instead of paying this extra round trip first.
        """
        if not groq_key:
            return None, {}
        key = groq_key
        if not cls.looks_like_action(prompt):
            return None, {}

        # Check LLM intent cache
        cached = cls._intent_cache.get(prompt)
        if cached is not None and cached[0] is not None:
            return cached

        try:
            from groq import Groq
            client = cls._CLIENTS.get(key)
            if client is None:
                client = Groq(api_key=key, max_retries=1)
                cls._CLIENTS[key] = client

            system_prompt = (
                "Você é um classificador de intenções para comandos de sistema Windows.\n"
                "Sua resposta DEVE ser estritamente um JSON no formato:\n"
                '{"action": "<ACTION_NAME>", "target": "<OPTIONAL_TARGET>"}\n\n'
                "Ações possíveis:\n"
                "- clean_recycle_bin (esvaziar/limpar lixeira)\n"
                "- boost_ram (otimizar/liberar memória/RAM)\n"
                "- organize_desktop (organizar/arrumar área de trabalho/desktop)\n"
                "- clean_temp_files (limpar arquivos temporários/cache)\n"
                "- get_ip_info (ver meu IP / status de rede)\n"
                "- get_disk_info (ver meus discos / HD / armazenamento)\n"
                "- take_screenshot (tirar print / capturar tela)\n"
                "- get_active_window (ver janela ativa / focada)\n"
                "- list_notes (ver minhas notas / anotações)\n"
                "- get_datetime (que horas são / que dia é hoje)\n"
                "- show_history (ver meu histórico de conversas)\n"
                "- show_memory (ver minha memória / o que você lembra)\n"
                "- self_program (se auto programar / melhorar código)\n"
                "- open_app (abrir aplicativo, 'target': nome do app)\n"
                "- kill_process (fechar/encerrar aplicativo, 'target': nome do app)\n"
                "- web_search (pesquisar no google, 'target': busca)\n"
                "- play_youtube (tocar no youtube, 'target': música/vídeo)\n"
                "- read_file (ler arquivo, 'target': caminho)\n"
                "- create_folder (criar pasta, 'target': nome)\n"
                "- save_note (anotar texto, 'target': nota)\n"
                "- download_file (baixar arquivo de URL, 'target': url)\n"
                "- install_app (instalar programa, 'target': nome/pacote)\n"
                "- uninstall_app (desinstalar programa, 'target': nome/pacote)\n"
                "- run_command (executar comando do sistema, 'target': comando)\n"
                "- list_files (listar arquivos de uma pasta, 'target': caminho)\n"
                "- search_files (buscar arquivo no PC, 'target': query)\n"
                "- copy_file (copiar arquivo, 'target': origem destino)\n"
                "- move_file (mover arquivo, 'target': origem destino)\n"
                "- delete_file_admin (deletar arquivo/pasta, 'target': caminho)\n"
                "- list_processes (ver processos ativos)\n"
                "- kill_process_admin (matar processo, 'target': nome/pid)\n"
                "- list_services (ver serviços do Windows)\n"
                "- wifi_list (ver redes WiFi disponíveis)\n"
                "- wifi_connect (conectar WiFi, 'target': ssid)\n"
                "- set_ip (configurar IP, 'target': ip gateway)\n"
                "- shutdown_pc (desligar o PC)\n"
                "- restart_pc (reiniciar o PC)\n"
                "- lock_pc (bloquear o PC)\n"
                "- set_volume (ajustar volume, 'target': nível 0-100)\n"
                "- system_info (informações do sistema)\n"
                "- none (se for uma conversa genérica ou dúvida sem ação de sistema)\n"
            )

            res = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model="openai/gpt-oss-20b",
                temperature=0.0,
                max_tokens=128,         # saída é um JSON minúsculo
                timeout=2.0,            # reduzido de 4s → 2s para latência mais baixa
                reasoning_effort="low",
                reasoning_format="hidden",
                response_format={"type": "json_object"}
            )

            if res.choices and res.choices[0].message.content:
                data = json.loads(res.choices[0].message.content)
                act = data.get("action")
                target = data.get("target", "")
                if act and act != "none":
                    params = {}
                    if target:
                        params["target"] = target
                        params["text"] = target
                        params["query"] = target
                        params["path"] = target
                        params["folder"] = target
                    result = (act, params)
                    cls._intent_cache.put(prompt, result)
                    return result
        except Exception:
            pass

        return None, {}
