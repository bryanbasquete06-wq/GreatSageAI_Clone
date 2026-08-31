"""
Elívea — Neural Streaming Voice Engine (Elívea Class)
================================================================
Ultra-realistic streaming text-to-speech built on Microsoft Neural voices
(edge-tts) with per-sentence synthesis pipeline:

    LLM tokens -> sentence splitter -> [synth thread] -> MP3 chunks
                                                       -> [player thread] -> MCI out

The FIRST sentence starts playing while the remaining ones are still being
synthesized, cutting perceived latency from seconds to < 1s.

Prosody presets (rate / pitch / volume) make each voice sound alive instead
of a flat robotic read, and every sentence gets a natural breathing pause.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import re
import tempfile
import threading
import time
import winsound
from dataclasses import dataclass, field
from pathlib import Path

import edge_tts

logger = logging.getLogger("elvea.speech")
# Ensure speech errors are visible (not just in JSON log file)
if not logger.handlers:
    _sh = logging.StreamHandler()
    _sh.setLevel(logging.WARNING)
    _sh.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_sh)
    logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Voice catalog — pt-BR neural voices with tuned prosody per persona.
#
# Elivea (Tensura): calm, analytical, precise, slightly slower delivery.
#   Rate  -6% → deliberate pacing (she never rushes)
#   Pitch -3Hz → lower, serene register
#   Volume +0% → controlled, never loud
#
# voice_id: pt-BR-FranciscaNeural — the closest match to Elívea's feminine
#   analytical tone available in edge-tts. We tune rate/pitch to nail the
#   anime feel: measured, elegant, slightly detached.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VoicePreset:
    key: str
    label: str
    voice_id: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    style: str = "neutral"


VOICE_PRESETS: dict[str, VoicePreset] = {
    p.key: p for p in [
        # ── Elivea: Elívea — natural, humana, Gisele Vinchin
        # Antes -10%/-5Hz ficava lento e grave demais (robótico). Agora mais natural:
        VoicePreset("raphael",   "Elivea • Elivea", "pt-BR-FranciscaNeural", "-4%", "-2Hz", "+0%", "analytic"),
        VoicePreset("raphael_natural", "Elivea • Natural", "pt-BR-ThalitaMultilingualNeural", "-2%", "+0Hz", "+0%", "natural"),
        # ── Jarvis: JARVIS BR (formal, masculine, Stark-class)
        VoicePreset("jarvis",    "JARVIS • Antonio",       "pt-BR-AntonioNeural",   "+0%", "-2Hz", "+0%", "formal"),
    ]
}

# Legacy name map (old UI sent display names — keep them working)
_LEGACY_ALIASES = {
    "Elivea Anime (Feminino)": "raphael",
    "Jarvis Male (Masculino)": "jarvis",
    "Soft Sage (Feminino Suave)": "raphael",
    "Deep Sage (Masculino Grave)": "jarvis",
    "Elivea • Elivea (Calma Analítica)": "raphael",
    "Elivea • Elivea (Gisele Vechin)": "raphael",
    "Elivea • Elivea (estilo personagem)": "raphael",
    "JARVIS BR • Antonio (M. Formal)": "jarvis",
    "JARVIS • Antonio": "jarvis",
    # Legacy non-existent presets → fall back to raphael
    "thalita": "raphael",
    "giovanna": "raphael",
    "antonio": "jarvis",
    "humberto": "jarvis",
    "valerio": "jarvis",
    "brenda": "raphael",
    "manuela": "raphael",
    "julio": "jarvis",
    "yara": "raphael",
}

# Legacy dict kept for backwards compatibility with older UI code
NEURAL_VOICES = {p.label: p.voice_id for p in VOICE_PRESETS.values()}

# Tudo no disco F ASCII — evita acento que quebra MCI e fica invisível
def _get_project_tmp() -> Path:
    for cand in [Path("F:/EliveaTemp"), Path(__file__).resolve().parents[1] / "temp", Path("F:/programação/J.A.R.V.I.S/EliveaAI_Clone/temp"), Path(tempfile.gettempdir()) / "elvea_tts"]:
        try:
            cand.mkdir(parents=True, exist_ok=True)
            if str(cand).upper().startswith("F:"):
                return cand
        except Exception:
            continue
    p = Path("F:/EliveaTemp/elvea_tts")
    p.mkdir(parents=True, exist_ok=True)
    return p

_TMP_DIR = _get_project_tmp()


# ---------------------------------------------------------------------------
# Sentence segmentation with human breathing points
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r'(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9"“(\-])')

# ---------------------------------------------------------------------------
# Emotional prosody engine — detects sentence tone for human-like delivery
# ---------------------------------------------------------------------------

_EMPHASIS_WORDS = frozenset({"sempre", "nunca", "absolutamente", "totalmente", "completamente",
                              "muito", "extremamente", "incrível", "fantástico", "perfeito",
                              "impecável", "certeza", "exatamente", "precisamente", "definitivamente",
                              "importante", "fundamental", "essencial", "crucial", "impossível",
                              "surpreendente", "extraordinário", "remarkable", "definitively"})
_HESITATION_WORDS = frozenset({"bem", "então", "entao", "pois", "ora", "hmm", "hã",
                               "olha", "sabe", "imagina", "tipo", "sei lá"})
_THANKS_WORDS = frozenset({"obrigado", "obrigada", "valeu", "agradeço", "brigado", "muito obrigado",
                           "thanks", "thx", "vlw"})
_GREETING_WORDS = frozenset({"olá", "oi", "bom dia", "boa tarde", "boa noite", "e aí",
                             "hey", "hello", "hi", "fala", "salve"})
_EXCLAMATION_WORDS = frozenset({"incrível", "fantástico", "maravilhoso", "perfeito", "excelente",
                               "genial", "brilhante", "sensacional", "impressionante", "wow"})
_QUESTION_MARKERS = frozenset({"como", "por quê", "por que", "onde", "quando", "quem",
                                "qual", "o quê", "quanto", "quantos", "quantas",
                                "será que", "exists", "possível"})
_LIST_MARKERS = frozenset({"primeiro", "segundo", "terceiro", "além disso", "também",
                            "por outro lado", "em resumo", "portanto", "ou seja",
                            "step", "etapa"})
_EMOTION_WORDS_JOY = frozenset({"obrigado", "valeu", "show", "massa", "top", "genial",
                               "perfeito", "incrível", "maravilhoso"})
_EMOTION_WORDS_URGENCY = frozenset({"urgente", "agora", "rápido", "já", "imediato",
                                   "depressa", "logo"})
_EMPATHY_WORDS = frozenset({"triste", "difícil", "problema", "errado", "quebrou",
                           "não funciona", "deu erro", "frustrado", "cansado"})

# Emotional prosody patterns — matched against full text for richer prosody
_HAPPY_PATTERN = re.compile(r'(show|massa|top|genial|perfeito|incrível|maravilhoso|obrigado|valeu)', re.IGNORECASE)
_URGENT_PATTERN = re.compile(r'(urgente|agora|rápido|já|imediato|depressa|pressa)', re.IGNORECASE)
_EMPATHY_PATTERN = re.compile(r'(triste|difícil|problema|errado|quebrou|não funciona|deu erro|frustrado)', re.IGNORECASE)
_EMPHASIS_PATTERN = re.compile(r'\b(nunca|sempre|absolutamente|totalmente|completamente|definitivamente|\d+%)\b', re.IGNORECASE)

# Breathing pause durations (seconds) — natural human-like delivery
# Restored from over-optimized values; each pause mimics real speech rhythm
_PAUSE_AFTER_PERIOD = 0.48       # Natural period pause — speaker finishes thought
_PAUSE_AFTER_EXCLAMATION = 0.38  # Excitement lingers slightly
_PAUSE_AFTER_QUESTION = 0.52     # Questions get extra wait (listener processes)
_PAUSE_BETWEEN_LONG = 0.65       # Long sentence → need to breathe
_PAUSE_BETWEEN_SHORT = 0.22      # Short fragment → quick connect to next
_PAUSE_BREATH_INTRO = 0.55       # Opening phrase → deliberate breath
_PAUSE_EMPHASIS = 0.42           # Emphasis → pause to let weight sink in
_PAUSE_HESITATION = 0.50         # Hesitation → natural uncertainty pause
_PAUSE_EMPATHY = 0.55            # Empathetic → gentle, caring pause
_PAUSE_JOY = 0.25                # Joy → energetic, barely pauses
_PAUSE_URGENCY = 0.12            # Urgency → breathless speed
_PAUSE_SEMICOLON = 0.30          # Semicolon → brief connector pause
_PAUSE_COMMA = 0.15              # Comma → micro-breath
_PAUSE_DASH = 0.20               # Dash → rhetorical pause

# Intra-sentence micro-pause injection (adds natural breathing within long phrases)
_MICRO_PAUSE_COMMA = ', ... '    # Comma becomes a breathing pause
_MICRO_PAUSE_COLON = ', ... '    # Colon → deliberate pause before explanation
_MICRO_PAUSE_SEMICOLON = '; ... ' # Semicolon → clause connector pause
_MICRO_PAUSE_DASH = ', ... '     # Dash → rhetorical beat
_MICRO_PAUSE_PERIOD = '. ... '   # Period inside long sentence → full stop + breath

# Dynamic prosody: rate/pitch/volume adjustments per emotional context
# These modify edge-tts parameters PER SENTENCE for real variation
_PROSODY_BOOST = {
    'joy':         {'rate': '+6%',  'pitch': '+4Hz',  'volume': '+4%'},
    'urgency':     {'rate': '+14%', 'pitch': '+3Hz',  'volume': '+6%'},
    'emphasis':    {'rate': '-6%',  'pitch': '+2Hz',  'volume': '+10%'},
    'hesitation':  {'rate': '-10%', 'pitch': '-3Hz',  'volume': '-3%'},
    'empathy':     {'rate': '-12%', 'pitch': '-4Hz',  'volume': '-5%'},
    'greeting':    {'rate': '-3%',  'pitch': '+2Hz',  'volume': '+3%'},
    'question':    {'rate': '-2%',  'pitch': '+5Hz',  'volume': '+2%'},
    'exclamation': {'rate': '+5%',  'pitch': '+4Hz',  'volume': '+8%'},
    'list':        {'rate': '-4%',  'pitch': '+0Hz',  'volume': '+0%'},
    'narration':   {'rate': '-8%',  'pitch': '-2Hz',  'volume': '-2%'},
    'neutral':     {'rate': '+0%',  'pitch': '+0Hz',  'volume': '+0%'},
}

_SYMBOL_SPEECH = [
    (r'https?://\S+', ' link '),
    (r'```[\s\S]*?```', ' bloco de código. '),
    (r'`([^`]*)`', r'\1'),
    (r'\[(?:Notice|Aviso|Report|Relatório|Action|Ação)[^\]]*\]\s*', ''),
    (r'[#*_~`>|]+', ''),
    (r'\s*->\s*', ' resulta em '),
    (r'\s*=>\s*', ' portanto, '),
    (r'\s*—\s*', ', '),
    (r'\s*–\s*', ', '),
    (r'°', ' graus'),
    (r'%', ' por cento'),
    # Acronyms → pronúncia em português
    (r'\bFAQ\b', 'faquei'),
    (r'\bAPI\b', 'ápi'),
    (r'\bURL\b', 'urle'),
    (r'\bHTML\b', 'ga atche emele'),
    (r'\bCSS\b', 'cêsse'),
    (r'\bJSON\b', 'jêisson'),
    (r'\bSQL\b', 'sequiêlle'),
    (r'\bOK\b', 'óquei'),
    (r'\bPC\b', 'pê cê'),
    (r'\bRAM\b', 'errei eme'),
    (r'\bCPU\b', 'cê pê u'),
    (r'\bSSD\b', 'isse ese dê'),
    (r'\bHD\b', 'aga dê'),
    (r'\bIP\b', 'i pê'),
    (r'\bDNS\b', 'dê ene ese'),
    (r'\bUSB\b', 'usse bê'),
    (r'\bGPU\b', 'jê pê u'),
    (r'\bAI\b', 'á i'),
    (r'\bIDE\b', 'i dê i'),
    (r'\bSDK\b', 'ese dê cá'),
    (r'\bTCP\b', 'tê cê pê'),
    (r'\bUDP\b', 'u dê pê'),
    (r'\bREST\b', 'reste'),
    (r'\bGit\b', 'guit'),
    (r'\bGitHub\b', 'guit hábi'),
    (r'\bNode\.js\b', 'node djís'),
    (r'\bReact\b', 'riacte'),
    (r'\bDocker\b', 'dócar'),
    (r'\bPython\b', 'pitoni'),
    (r'\bJavaScript\b', 'djávi escripte'),
    (r'\bTypeScript\b', 'taipi escripte'),
    (r'\bLinux\b', 'linúcs'),
    (r'\bWindows\b', 'uindons'),
    (r'\bGoogle\b', 'gugou'),
    (r'\bYouTube\b', 'iutubi'),
    (r'\bWhatsApp\b', 'uozápi'),
    (r'\bStreamlit\b', 'estrimilete'),
    (r'\bAutoGen\b', 'autodjene'),
    (r'\bGroq\b', 'groque'),
    (r'\bGemini\b', 'jemini'),
    (r'\bWhisper\b', 'uíspe'),
    (r'\bedge-tts\b', 'editi tis'),
    (r'\bFFmpeg\b', 'efe efeme'),
    (r'\bWi-Fi\b', 'uai fai'),
    (r'\bWiFi\b', 'uai fai'),
    (r'\bBluetooth\b', 'blutusse'),
    (r'\bPDF\b', 'pê dê efe'),
    (r'\bCSV\b', 'cê ese vê'),
    (r'\bXML\b', 'equisse emele'),
    (r'\bYAML\b', 'ia emele'),
]

# Common English words that leak through the LLM → Portuguese equivalents
_EN_TO_PT = {
    "notice": "aviso", "warning": "atenção", "error": "erro", "success": "sucesso",
    "failed": "falhou", "true": "verdadeiro", "false": "falso", "null": "nulo",
    "none": "nenhum", "yes": "sim", "hello": "olá", "hi": "oi", "bye": "tchau",
    "thanks": "obrigado", "thank you": "obrigado", "please": "por favor",
    "sorry": "desculpe", "okay": "óquei", "ok": "óquei", "waiting": "aguardando",
    "loading": "carregando", "processing": "processando", "executing": "executando",
    "completed": "concluído", "finished": "finalizado", "running": "executando",
    "starting": "iniciando", "stopping": "parando", "connecting": "conectando",
    "disconnected": "desconectado", "saved": "salvo", "deleted": "deletado",
    "created": "criado", "updated": "atualizado", "found": "encontrado",
    "not found": "não encontrado", "empty": "vazio", "full": "cheio",
    "open": "aberto", "closed": "fechado", "available": "disponível",
    "unavailable": "indisponível", "enabled": "habilitado", "disabled": "desabilitado",
    "online": "online", "offline": "offline", "active": "ativo", "inactive": "inativo",
    "ready": "pronto", "busy": "ocupado", "free": "livre", "usage": "uso",
    "speed": "velocidade", "memory": "memória", "processor": "processador",
    "disk": "disco", "drive": "unidade", "folder": "pasta", "file": "arquivo",
    "files": "arquivos", "folders": "pastas", "path": "caminho", "command": "comando",
    "commands": "comandos", "process": "processo", "processes": "processos",
    "service": "serviço", "services": "serviços", "application": "aplicativo",
    "applications": "aplicativos", "program": "programa", "programs": "programas",
    "software": "software", "hardware": "hardware", "network": "rede",
    "networks": "redes", "server": "servidor", "client": "cliente", "data": "dados",
    "code": "código", "text": "texto", "image": "imagem", "images": "imagens",
    "video": "vídeo", "videos": "vídeos", "audio": "áudio", "music": "música",
    "message": "mensagem", "messages": "mensagens", "chat": "conversa",
    "history": "histórico", "setting": "configuração", "settings": "configurações",
    "configuration": "configuração", "option": "opção", "options": "opções",
    "feature": "recurso", "features": "recursos", "tool": "ferramenta",
    "tools": "ferramentas", "method": "método", "methods": "métodos",
    "function": "função", "functions": "funções", "variable": "variável",
    "variables": "variáveis", "parameter": "parâmetro", "parameters": "parâmetros",
    "argument": "argumento", "arguments": "argumentos", "class": "classe",
    "classes": "classes", "object": "objeto", "objects": "objetos", "module": "módulo",
    "modules": "módulos", "package": "pacote", "packages": "pacotes",
    "library": "biblioteca", "libraries": "bibliotecas", "request": "requisição",
    "requests": "requisições", "response": "resposta", "responses": "respostas",
    "test": "teste", "tests": "testes", "testing": "testando", "debug": "depurar",
    "bug": "bug", "bugs": "bugs", "issue": "problema", "issues": "problemas",
    "task": "tarefa", "tasks": "tarefas", "project": "projeto", "projects": "projetos",
    "version": "versão", "versions": "versões", "update": "atualização",
    "updates": "atualizações", "upgrade": "atualizar", "install": "instalar",
    "uninstall": "desinstalar", "download": "baixar", "upload": "enviar",
    "copy": "copiar", "paste": "colar", "cut": "recortar", "delete": "deletar",
    "remove": "remover", "add": "adicionar", "create": "criar", "modify": "modificar",
    "change": "alterar", "rename": "renomear", "move": "mover", "search": "buscar",
    "find": "encontrar", "log": "log", "logs": "logs", "status": "status",
    "info": "informação", "information": "informação", "details": "detalhes",
    "report": "relatório", "reports": "relatórios", "summary": "resumo",
    "help": "ajuda", "manual": "manual", "guide": "guia", "example": "exemplo",
    "examples": "exemplos", "template": "modelo", "templates": "modelos",
    "setup": "configuração", "config": "configuração", "env": "ambiente",
    "key": "chave", "keys": "chaves", "value": "valor", "values": "valores",
    "type": "tipo", "types": "tipos", "name": "nome", "names": "nomes",
    "size": "tamanho", "count": "contagem", "number": "número", "total": "total",
    "result": "resultado", "results": "resultados", "output": "saída",
    "input": "entrada", "stream": "fluxo", "queue": "fila", "stack": "pilha",
    "tree": "árvore", "graph": "grafo", "node": "nó", "nodes": "nós",
    "path": "caminho", "paths": "caminhos", "root": "raiz", "next": "próximo",
    "previous": "anterior", "current": "atual", "first": "primeiro", "last": "último",
    "new": "novo", "old": "antigo", "temp": "temporário", "time": "tempo",
    "date": "data", "day": "dia", "week": "semana", "month": "mês", "year": "ano",
    "hour": "hora", "minute": "minuto", "now": "agora", "today": "hoje",
    "yesterday": "ontem", "tomorrow": "amanhã", "never": "nunca", "always": "sempre",
    "sometimes": "às vezes", "probably": "provavelmente", "maybe": "talvez",
    "actually": "na verdade", "basically": "basicamente", "however": "no entanto",
    "but": "mas", "and": "e", "or": "ou", "if": "se", "then": "então",
    "here": "aqui", "there": "lá", "where": "onde", "when": "quando",
    "why": "por quê", "how": "como", "what": "o quê", "who": "quem", "which": "qual",
    "can": "pode", "will": "vai", "have": "tem", "has": "tem", "do": "faz",
    "does": "faz", "did": "fez", "doing": "fazendo", "done": "feito",
    "go": "ir", "goes": "vai", "going": "indo", "gone": "ido",
    "come": "vir", "comes": "vem", "coming": "vindo",
    "run": "rodar", "runs": "roda", "get": "obter", "gets": "obtém",
    "got": "obteve", "set": "definir", "put": "colocar",
    "take": "pegar", "takes": "pega", "took": "pegou", "taken": "pegado",
    "give": "dar", "gives": "dá", "gave": "deu", "given": "dado",
    "make": "fazer", "makes": "faz", "made": "feito",
    "use": "usar", "uses": "usa", "used": "usado", "using": "usando",
    "keep": "manter", "keeps": "mantém", "kept": "mantido",
    "try": "tentar", "tries": "tenta", "tried": "tentou", "trying": "tentando",
    "start": "iniciar", "starts": "inicia", "started": "iniciado",
    "stop": "parar", "stops": "para", "stopped": "parado",
    "wait": "esperar", "waits": "espera", "waited": "esperou", "waiting": "aguardando",
    "need": "precisar", "needs": "precisa", "needed": "precisou",
    "want": "querer", "wants": "quer", "wanted": "quis",
    "think": "pensar", "thinks": "pensa", "thought": "pensou", "thinking": "pensando",
    "know": "saber", "knows": "sabe", "known": "conhecido",
    "believe": "acreditar", "believes": "acredita",
    "feel": "sentir", "feels": "sente", "felt": "sentiu",
    "see": "ver", "sees": "vê", "saw": "viu", "seen": "visto",
    "looking": "procurando", "listen": "ouvir", "listens": "ouve",
    "listened": "ouviu", "listening": "ouvindo",
    "speak": "falar", "speaks": "fala", "spoke": "falou", "speaking": "falando",
    "tell": "contar", "tells": "conta", "told": "contou",
    "ask": "perguntar", "asks": "pergunta", "asked": "perguntou",
    "answer": "responder", "answers": "responde", "answered": "respondeu",
    "read": "ler", "reads": "lê",
    "write": "escrever", "writes": "escreve", "wrote": "escreveu", "written": "escrito",
    "send": "enviar", "sends": "envia", "sent": "enviou",
    "receive": "receber", "receives": "recebe", "received": "recebeu",
    "show": "mostrar", "shows": "mostra", "showed": "mostrou", "shown": "mostrado",
    "hide": "esconder", "hidden": "escondido",
    "check": "verificar", "checks": "verifica", "checked": "verificou",
    "verify": "verificar", "confirm": "confirmar", "confirmed": "confirmado",
    "sort": "ordenar", "sorts": "ordena", "sorted": "ordenado",
    "filter": "filtrar", "filters": "filtra", "filtered": "filtrado",
    "save": "salvar", "saves": "salva", "saved": "salvo", "saving": "salvando",
    "load": "carregar", "loads": "carrega", "loaded": "carregado", "loading": "carregando",
    "close": "fechar", "closes": "fecha", "closed": "fechado",
    "open": "abrir", "opens": "abre", "opened": "aberto", "opening": "abrindo",
    "clean": "limpar", "cleaned": "limpou", "cleaning": "limpando",
    "clear": "limpar", "cleared": "limpou", "clearing": "limpando",
    "boost": "aumentar", "boosted": "aumentado",
    "optimize": "otimizar", "optimized": "otimizado", "performance": "desempenho",
    "connect": "conectar", "connected": "conectado", "connecting": "conectando",
    "disconnect": "desconectar", "disconnected": "desconectado",
    "notify": "notificar", "notified": "notificado", "notifying": "notificando",
    "alert": "alertar", "alerted": "alertado", "alerting": "alertando",
    "timeout": "tempo limite", "error": "erro", "errors": "erros",
    "success": "sucesso", "fail": "falhar", "failed": "falhou", "failure": "falha",
    "crash": "crash", "crashed": "crashou",
    "freeze": "travar", "frozen": "travado", "slow": "lento", "fast": "rápido",
    "quickly": "rapidamente", "efficient": "eficiente",
    "memory": "memória", "speed": "velocidade",
    "system": "sistema", "systems": "sistemas", "device": "dispositivo",
    "devices": "dispositivos", "port": "porta", "ports": "portas",
    "driver": "driver", "drivers": "drivers", "process": "processo",
    "processes": "processos", "thread": "thread", "threads": "threads",
    "service": "serviço", "services": "serviços",
    "resource": "recurso", "resources": "recursos", "usage": "uso",
    "limit": "limite", "limits": "limites", "capacity": "capacidade",
    "availability": "disponibilidade", "latency": "latência",
    "bandwidth": "largura de banda", "speed": "velocidade",
    "performance": "desempenho", "efficiency": "eficiência",
    "optimization": "otimização",
    "render": "renderizar", "rendered": "renderizado", "rendering": "renderizando",
    "display": "exibir", "displayed": "exibido", "displaying": "exibindo",
    "chart": "gráfico", "charts": "gráficos", "plot": "gráfico", "plots": "gráficos",
    "graph": "gráfico", "graphs": "gráficos", "visual": "visual",
    "visualization": "visualização", "visualizations": "visualizações",
    "view": "visualização", "views": "visualizações",
}


def _en_to_pt(text: str) -> str:
    """Replace common English words with Portuguese equivalents for speech."""
    words = text.split()
    result = []
    for w in words:
        lower = w.lower().strip(".,;:!?\"'()[]{}")
        if lower in _EN_TO_PT:
            replacement = _EN_TO_PT[lower]
            # Preserve capitalization
            if w[0].isupper():
                replacement = replacement.capitalize()
            result.append(replacement)
        else:
            result.append(w)
    return " ".join(result)


def clean_for_speech(text: str) -> str:
    """Strips markdown / code / emojis / URLs / symbols and translates English → Portuguese.
    Code blocks and emojis are completely removed — the AI never speaks them."""
    t = text
    # ── Remove emojis (all Unicode emoji ranges) ──
    emoji_pat = (
        r'[\U0001F600-\U0001F64F'  # emoticons
        r'\U0001F300-\U0001F5FF'   # symbols & pictographs
        r'\U0001F680-\U0001F6FF'   # transport & map
        r'\U0001F1E0-\U0001F1FF'   # flags
        r'\U00002702-\U000027B0'   # dingbats
        r'\U000024C2-\U0001F251'   # enclosed chars
        r'\U0001f926-\U0001f937'   # supplemental
        r'\U00010000-\U0010ffff'   # supplementary
        r'\u200d\u2640-\u2642\u2600-\u2B55\u23cf\u23e9\u231a\ufe0f\u3030]+'
    )
    t = re.sub(emoji_pat, '', t)
    # Also remove common emoji-like characters
    t = re.sub(r'[\u2600-\u27BF]', '', t)  # misc symbols
    t = re.sub(r'[\u2300-\u23FF]', '', t)  # technical symbols
    # ── Remove code blocks first (``` ... ``` and ` inline code) ──
    t = re.sub(r'```[\w]*\n[\s\S]*?```', '', t)  # fenced code blocks
    t = re.sub(r'`[^`]+`', '', t)  # inline code
    t = re.sub(r'(?m)^\s*[#>]\s?.*$', '', t)  # comment lines and blockquotes
    # Remove common code-like patterns
    t = re.sub(r'(?m)^(?:from |import |def |class |if __name__|\s*print\().*$', '', t)
    t = re.sub(r'(?m)^\s*\w+\s*[= (].*[:=].*$', '', t)  # assignment / function calls
    # Remove markdown formatting
    for pat, rep in _SYMBOL_SPEECH:
        t = re.sub(pat, rep, t)
    t = _en_to_pt(t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'([.!?])\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ])', r'\1 \2', t)
    return t


def _detect_sentence_tone(sentence: str) -> str:
    """Classifies sentence emotional tone for prosody adjustment.

    Returns: 'emphasis', 'hesitation', 'thanks', 'greeting',
             'exclamation', 'question', 'list', or 'neutral'
    """
    lower = sentence.lower().strip()
    words = lower.split()

    if any(w in _EXCLAMATION_WORDS for w in words) or '!' in lower:
        return 'exclamation'
    if any(m in lower for m in _QUESTION_MARKERS) or lower.endswith('?'):
        return 'question'
    if any(w in _THANKS_WORDS for w in words):
        return 'thanks'
    if any(w in _GREETING_WORDS for w in words):
        return 'greeting'
    if any(w in _EMPHASIS_WORDS for w in words):
        return 'emphasis'
    if any(w in _HESITATION_WORDS for w in words):
        return 'hesitation'
    if any(m in lower for m in _LIST_MARKERS):
        return 'list'
    return 'neutral'


def _inject_breathing(sentences: list[str]) -> list[str]:
    """Returns sentences unchanged — actual pauses are handled by the play loop.

    The play loop inserts time.sleep() between utterances based on sentence
    tone and length, which gives natural breathing rhythm without SSML tags
    (edge-tts does not support SSML).
    """
    return sentences


def split_sentences(text: str, max_len: int = 200, hard_max: int = 340) -> list[str]:
    """Splits text into speakable sentence chunks.

    Speed optimization: merges very short consecutive sentences to reduce
    the number of TTS network calls (each costs ~2s). Two sentences under
    60 chars are joined into one, cutting latency in half for short replies.
    """
    t = clean_for_speech(text)
    if not t:
        return []

    parts = [s.strip() for s in _SENT_SPLIT.split(t) if s and s.strip()]
    raw: list[str] = []
    for sent in parts:
        while len(sent) > hard_max:
            cut = sent.rfind(', ', max_len // 2, max_len + 40)
            if cut <= 0:
                cut = sent.rfind(' e ', max_len // 2, max_len + 40)
            if cut <= 0:
                cut = sent.rfind(' mas ', max_len // 2, max_len + 40)
            if cut <= 0:
                cut = sent.rfind(' ', max_len // 2, max_len + 60)
            if cut <= 0:
                cut = max_len
            raw.append(sent[:cut].strip().rstrip(','))
            sent = sent[cut:].strip()
        if sent:
            raw.append(sent)

    # Speed optimization: merge only tiny fragments (< 8 chars) to save TTS calls
    # while preserving natural sentence boundaries for breathing pauses.
    out: list[str] = []
    buf = ""
    for sent in raw:
        if buf and len(buf) < 8 and len(sent) < 8:
            buf = buf.rstrip('.!?') + '. ' + sent
        elif not buf:
            buf = sent
        else:
            out.append(buf)
            buf = sent
    if buf:
        out.append(buf)

    return _inject_breathing(out)


# ---------------------------------------------------------------------------
# One utterance flowing through the pipeline
# ---------------------------------------------------------------------------

@dataclass
class _Utterance:
    seq: int
    text: str
    path: Path | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    canceled: bool = False
    pause_after: float = 0.0   # seconds to wait after playing this utterance


_WAIT = object()   # nothing to do yet
_SKIP = object()   # sequence number flushed away — advance


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class SpeechEngine:
    """Streaming neural TTS with ordered playback and instant barge-out."""

    def __init__(self, voice_key: str = "raphael"):
        self.preset = VOICE_PRESETS.get(voice_key, VOICE_PRESETS["raphael"])
        self.is_speaking = False
        self.is_listening = False          # legacy flag (pipeline drives it)
        self.on_playback_start = None      # callback()
        self.on_playback_end = None        # callback()
        self.on_error = None               # callback(error_msg: str)

        self._lock = threading.Lock()
        self._queue: list[_Utterance] = []
        self._seq = 0
        self._generation = 0               # bump = flush everything (file naming)
        self._flush_seq = 0                # every seq <= this was flushed away
        self._mci_alias: str | None = None

        # Persistent asyncio loop — avoids 200ms overhead per asyncio.run() call
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True, name="gs-tts-loop")
        self._loop_thread.start()

        # Load SFX from video reference
        self._sfx = {}
        self._load_sfx()

        self._synth_thread = threading.Thread(target=self._synth_loop, daemon=True, name="gs-tts-synth")
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True, name="gs-tts-play")
        self._synth_thread.start()
        self._play_thread.start()

    def _run_event_loop(self):
        """Run persistent asyncio event loop in background thread."""
        self._loop.run_forever()

    def _load_sfx(self):
        """Load SFX files from config directory with named categories."""
        sfx_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        # Named SFX mapping
        sfx_names = {
            0: "activation",     # Ethereal ascending chime
            1: "analysis",       # Digital processing texture
            2: "confirm",        # Clean confirmation
            3: "error",          # Subtle warning
            4: "ambient",        # Background presence hum
        }
        for i, name in sfx_names.items():
            path = os.path.join(sfx_dir, f"sfx_short_{i}.wav")
            if os.path.exists(path):
                self._sfx[name] = path
                self._sfx[f"notify_{i}"] = path  # Legacy mapping

    def play_sfx(self, sfx_name: str):
        """Play a sound effect asynchronously."""
        path = self._sfx.get(sfx_name)
        if not path:
            return
        def _play():
            try:
                alias = f"sfx_{int(time.time() * 1000)}"
                ctypes.windll.winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
                ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
                time.sleep(0.5)
                ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
            except Exception:
                pass
        threading.Thread(target=_play, daemon=True).start()

    def play_notify(self):
        """Play a notification sound (Elivea activation)."""
        self.play_sfx("activation")

    def play_analysis(self):
        """Play analysis/processing sound."""
        self.play_sfx("analysis")

    def play_confirm(self):
        """Play confirmation sound."""
        self.play_sfx("confirm")

    def play_error(self):
        """Play error/warning sound."""
        self.play_sfx("error")

    def play_ambient(self):
        """Play ambient presence sound."""
        self.play_sfx("ambient")

    # ------------------------------------------------------------------ API

    def set_voice(self, voice_key: str):
        """Switch voice by preset key, legacy display name, or raw voice id."""
        key = _LEGACY_ALIASES.get(voice_key, voice_key)
        if key in VOICE_PRESETS:
            self.preset = VOICE_PRESETS[key]
        else:
            # Raw voice id like "pt-BR-AntonioNeural"
            match = next((p for p in VOICE_PRESETS.values() if p.voice_id == voice_key), None)
            if match:
                self.preset = match
            else:
                self.preset = VoicePreset("custom", voice_key, voice_key)

    @property
    def current_voice_label(self) -> str:
        return self.preset.label

    def speak(self, text: str, callback_done=None):
        """Queue a full text for spoken playback (sentence-streamed)."""
        logger.info(f"speak() called: \"{text[:80]}...\"")
        # Reset sentence counter for new response (position rhythm)
        self._sentence_count = 0
        # Start speaking immediately for short text (< 100 chars)
        if len(text) <= 100:
            s = clean_for_speech(text)
            if s:
                self._enqueue(s)
                if callback_done:
                    threading.Timer(0.5, callback_done).start()
            return
        self.speak_stream([text], callback_done=callback_done)

    # Legacy alias
    def speak_async(self, text: str, callback_done=None):
        self.speak(text, callback_done=callback_done)

    def speak_stream(self, text_chunks, callback_done=None):
        """Consume an iterable/generator of text; sentences speak as they arrive.

        Returns immediately. `text_chunks` may be a live LLM token generator.
        SPEED: reuse existing consumer thread instead of spawning new one.
        """
        logger.info(f"speak_stream() called")
        # Start consumer in existing daemon thread pool
        t = threading.Thread(target=self._stream_consumer,
                             args=(text_chunks, callback_done),
                             daemon=True, name="gs-tts-stream")
        t.start()

    def stop_speaking(self):
        """Instantly flush the pipeline and silence audio (barge-out)."""
        with self._lock:
            self._generation += 1
            pending = self._queue[:]
            self._queue.clear()
            # everything numbered up to _seq is now dead: the player must
            # skip past these numbers instead of waiting for them forever
            self._flush_seq = max(self._flush_seq, self._seq)
        for u in pending:
            u.canceled = True
            u.ready.set()
        self._halt_mci()
        self.is_speaking = False

    # ---------------------------------------------------------------- chimes

    @staticmethod
    def play_wake_chime():
        def _beep():
            try:
                winsound.Beep(784, 70); time.sleep(0.02)
                winsound.Beep(1175, 90); time.sleep(0.02)
                winsound.Beep(1568, 130)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_success_chime():
        def _beep():
            try:
                winsound.Beep(1046, 55); time.sleep(0.015)
                winsound.Beep(1318, 55); time.sleep(0.015)
                winsound.Beep(1760, 85)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_boot_chime():
        """Tensura-inspired boot sequence: ethereal ascending chime."""
        def _beep():
            try:
                logger.info("Boot chime playing")
                # Ethereal ascending sequence — Elivea's awakening
                for f, d in [(523, 60), (659, 60), (784, 70), (880, 80),
                             (1047, 100), (1175, 60), (1319, 50), (1568, 180)]:
                    winsound.Beep(f, d)
                    time.sleep(0.015)
                # Final resonance
                time.sleep(0.05)
                winsound.Beep(1568, 120)
                logger.info("Boot chime done")
            except Exception as e:
                logger.error(f"Boot chime error: {e}")
        threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_error_chime():
        def _beep():
            try:
                winsound.Beep(220, 140); time.sleep(0.05); winsound.Beep(180, 200)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    # ------------------------------------------------------------ internals

    def _stream_consumer(self, text_chunks, callback_done):
        """Accumulates streamed chunks and releases complete sentences.

        SPEED: merges ultra-short consecutive sentences to reduce TTS API calls.
        e.g. ["Ok.", "Certo.", "Vou fazer."] → 1 TTS call instead of 3.
        """
        buf = ""
        pending_sentences = []
        try:
            for chunk in text_chunks:
                if not chunk:
                    continue
                buf += chunk
                # Release every complete sentence (keep tail for next pass)
                sentences = split_sentences(buf)
                if len(sentences) > 1:
                    for s in sentences[:-1]:
                        pending_sentences.append(s)
                    buf = sentences[-1]

                    # SPEED: when we have multiple pending, try merging short ones
                    if len(pending_sentences) >= 2:
                        try:
                            from core.speed_optimizer import merge_short_sentences
                            merged = merge_short_sentences(pending_sentences, max_chars=35)
                            for s in merged:
                                self._enqueue(s)
                        except ImportError:
                            for s in pending_sentences:
                                self._enqueue(s)
                        pending_sentences.clear()
        except Exception as e:
            logger.error(f"TTS stream consumer error: {e}", exc_info=True)
        finally:
            # Flush remaining
            if buf.strip():
                pending_sentences.append(buf)
            if pending_sentences:
                try:
                    from core.speed_optimizer import merge_short_sentences
                    merged = merge_short_sentences(pending_sentences, max_chars=35)
                    for s in merged:
                        self._enqueue(s)
                except ImportError:
                    for s in pending_sentences:
                        self._enqueue(s)
            if callback_done:
                threading.Timer(0.5, callback_done).start()

    _sentence_count = 0  # tracks position in a multi-sentence response

    def _calc_pause(self, sentence: str) -> float:
        """Calculate natural breathing pause after a sentence (seconds).

        Mimics human speech rhythm:
        - First sentence of a response gets a slightly longer pause (establishing)
        - Lists get uniform rhythmic pauses
        - Questions get extra pause (listener processes)
        - Emotional content modifies the rhythm
        - Long sentences → longer breath
        """
        slen = len(sentence)
        self._sentence_count += 1

        # Base pause from sentence length and punctuation
        if slen > 100:
            pause = _PAUSE_BETWEEN_LONG
        elif slen < 20:
            pause = _PAUSE_BETWEEN_SHORT
        elif sentence.rstrip().endswith('?'):
            pause = _PAUSE_AFTER_QUESTION
        elif sentence.rstrip().endswith('!'):
            pause = _PAUSE_AFTER_EXCLAMATION
        else:
            pause = _PAUSE_AFTER_PERIOD

        # Position rhythm: first sentence → deliberate breath, last → shorter
        if self._sentence_count == 1:
            pause = max(pause, _PAUSE_BREATH_INTRO)  # Opening: deliberate
        elif self._sentence_count == 2:
            pause = pause * 1.1  # Second: slight linger

        # Punctuation micro-adjustments
        if sentence.rstrip().endswith('...'):
            pause += 0.15   # Trailing ellipsis → contemplative extra beat
        if sentence.rstrip().endswith('—'):
            pause += 0.10   # Em-dash ending → dramatic pause
        if sentence.rstrip().endswith(':'):
            pause += 0.08   # Colon ending → anticipatory pause

        # Emotional prosody — varies pause based on detected tone
        tone = _detect_sentence_tone(sentence)
        tone_pauses = {
            'emphasis':    _PAUSE_EMPHASIS,
            'hesitation':  _PAUSE_HESITATION,
            'thanks':      _PAUSE_EMPATHY,
            'greeting':    _PAUSE_EMPATHY,
            'exclamation': _PAUSE_JOY,
            'question':    _PAUSE_AFTER_QUESTION,
            'list':        _PAUSE_SEMICOLON,
        }
        if tone in tone_pauses:
            pause = tone_pauses[tone]

        # Pattern-based fine-tuning
        if _URGENT_PATTERN.search(sentence):
            pause = min(pause, _PAUSE_URGENCY)
        elif _EMPATHY_PATTERN.search(sentence):
            pause = max(pause, _PAUSE_EMPATHY)
        elif _HAPPY_PATTERN.search(sentence):
            pause = min(pause, _PAUSE_JOY)

        # Add slight randomness for human-like variation (±15%)
        import random
        jitter = random.uniform(0.85, 1.15)
        pause *= jitter

        return round(pause, 3)

    def _get_prosody_adjustment(self, sentence: str) -> dict:
        """Get dynamic prosody adjustments (rate, pitch, volume) for a sentence.

        Returns dict with SSML-like adjustments that modify the voice preset
        for this specific utterance, creating emotional variation.
        """
        if _URGENT_PATTERN.search(sentence):
            return _PROSODY_BOOST['urgency']
        elif _EMPATHY_PATTERN.search(sentence):
            return _PROSODY_BOOST['empathy']
        elif _EMPHASIS_PATTERN.search(sentence):
            return _PROSODY_BOOST['emphasis']
        elif any(w in sentence.lower() for w in _HESITATION_WORDS):
            return _PROSODY_BOOST['hesitation']
        elif _HAPPY_PATTERN.search(sentence):
            return _PROSODY_BOOST['joy']
        return _PROSODY_BOOST['neutral']

    def _apply_prosody(self, text: str, sentence: str) -> str:
        """Apply emotional prosody + intra-sentence micro-pauses.

        Three layers:
        1. Micro-pauses: commas/colons/dashes → breathing pauses (', ... ')
        2. Emphasis: key words get ALL CAPS for neural voice stress
        3. Sentence shaping: ellipses for dramatic effect, rhythm breaks
        """
        # Layer 1: Intra-sentence micro-pauses (natural breathing within phrases)
        text = self._add_micro_pauses(text)

        # Layer 2: Emphasis markers for neural voice stress
        prosody = self._get_prosody_adjustment(sentence)
        if prosody['rate'].startswith('+'):
            # Energetic/urgent: emphasize key words with caps
            for word in _EMPHASIS_WORDS:
                if word in text.lower():
                    text = re.sub(r'\b' + re.escape(word) + r'\b',
                                 lambda m: m.group(0).upper() if m.group(0).islower() else m.group(0).title(),
                                 text, count=1)
                    break
        elif prosody['rate'].startswith('-'):
            # Calm/empathetic: soften emphasis, add gentle rhythm
            # Add ellipses at strategic points for contemplative pacing
            text = re.sub(r'\b(não|talvez|acho|acho que|creio)\b',
                         r'\1, ...', text, count=1)

        # Layer 3: Dramatic shaping for long sentences
        if len(text) > 120:
            # Insert a breath at mid-point connector words
            connectors = [' mas ', ' porém ', ' além disso ', ' portanto ',
                         ' ou seja ', ' isto é ', ' por exemplo ']
            for conn in connectors:
                idx = text.find(conn)
                if 30 < idx < len(text) - 20:
                    text = text[:idx] + conn.strip() + ', ...' + text[idx + len(conn):]
                    break

        return text

    def _add_micro_pauses(self, text: str) -> str:
        """Inject breathing micro-pauses within long phrases.

        Natural speakers pause briefly at commas, colons, semicolons, and dashes.
        edge-tts doesn't interpret these as pauses by default, so we expand them
        into 'comma + ellipsis' patterns that the neural voice reads as micro-breaths.
        Only applies to sentences > 60 chars to avoid over-pausing short phrases.
        """
        if len(text) < 60:
            return text

        # Don't double-inject if already has '...' patterns
        if '...' in text:
            return text

        # Semicolons → clause boundary pause
        text = text.replace('; ', _MICRO_PAUSE_SEMICOLON)

        # Colons → explanatory pause (but not in URLs or times)
        text = re.sub(r'(?<!\d)(?<!\w):(?!//)(?!\d)', _MICRO_PAUSE_COLON, text)

        # Em-dashes → rhetorical pause
        text = re.sub(r'\s*[—–]\s*', _MICRO_PAUSE_DASH, text)

        # Long comma lists: only expand if comma-separated segments > 20 chars each
        # This prevents over-pausing in simple lists like 'a, b, c'
        parts = text.split(', ')
        if len(parts) > 2 and all(len(p) > 20 for p in parts[:3]):
            text = ', ... '.join(parts)

        # Clean up: collapse multiple '...' sequences
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    # --- Speed optimization: skip voice styling for short text ---
    _VOICE_STYLING_MIN_LEN = 200  # chars — skip ffmpeg+convert for most sentences (saves ~1.5s each)

    def _enqueue(self, sentence: str):
        s = clean_for_speech(sentence)
        if not s:
            return
        pause = self._calc_pause(s)
        # Apply emotional prosody to text
        s = self._apply_prosody(s, sentence)
        with self._lock:
            self._seq += 1
            u = _Utterance(seq=self._seq, text=s, pause_after=pause)
            self._queue.append(u)
            gen = self._generation

        # SPEED: reuse thread pool instead of spawning new thread per sentence
        if not hasattr(self, '_synth_pool'):
            self._synth_pool = []
        # Find or create a free worker
        def _synth_one():
            try:
                # SPEED: check TTS cache first — instant playback for common phrases
                try:
                    from core.speed_optimizer import get_tts_cache
                    tts_cache = get_tts_cache()
                    cached = tts_cache.get(s, self.preset.voice_id, self.preset.rate, self.preset.pitch)
                    if cached:
                        import shutil
                        path = _TMP_DIR / f"gs_{gen}_{u.seq}.mp3"
                        shutil.copy2(str(cached), str(path))
                        u.path = path
                        logger.debug(f"TTS cache HIT: {s[:30]} (0ms)")
                        return
                except ImportError:
                    pass

                path = _TMP_DIR / f"gs_{gen}_{u.seq}.mp3"

                # Get dynamic prosody for this sentence
                prosody = self._get_prosody_adjustment(sentence)

                # Synthesize with edge-tts (persistent loop — no per-call overhead)
                future = asyncio.run_coroutine_threadsafe(
                    self._synthesize(s, path, prosody=prosody), self._loop
                )
                future.result(timeout=15)  # 15s max per sentence
                if not path.exists() or path.stat().st_size == 0:
                    logger.error(f"TTS synth produced empty/missing file: {path}")
                    u.canceled = True
                    return
                logger.debug(f"TTS synth OK: {path.name} ({path.stat().st_size}B)")

                # Speed optimization: skip voice styling for short text (saves ~1.5s)
                if len(s) >= self._VOICE_STYLING_MIN_LEN:
                    u.path = self._apply_voice_styling(path, u) or path
                else:
                    u.path = path
                    logger.debug(f"TTS: skipped voice styling for short text ({len(s)} chars)")

                # SPEED: store in TTS cache for future use
                try:
                    from core.speed_optimizer import get_tts_cache
                    tts_cache = get_tts_cache()
                    tts_cache.put(s, self.preset.voice_id, self.preset.rate, self.preset.pitch, u.path or path)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"TTS synth error: {e}", exc_info=True)
                u.canceled = True
                if self.on_error:
                    try: self.on_error(f"Erro de síntese de voz: {e}")
                    except Exception: pass
            finally:
                u.ready.set()

        # SPEED: start synth immediately without waiting
        t = threading.Thread(target=_synth_one, daemon=True)
        t.start()

    async def _synthesize(self, text: str, out_path: Path, prosody: dict = None):
        """Synthesize text with blended dynamic prosody.

        Merges emotional prosody with the base voice preset:
        - Base preset sets the overall character (calm, analytical)
        - Emotional boost ADDS to the base (e.g., base -4% + urgency +14% = net +10%)
        - This creates real variation while maintaining voice identity
        """
        # Parse base preset values
        def _parse_pct(s):
            return int(s.replace('%', '').replace('+', ''))
        def _parse_hz(s):
            return int(s.replace('Hz', '').replace('+', ''))

        base_rate = _parse_pct(self.preset.rate)
        base_pitch = _parse_hz(self.preset.pitch)
        base_vol = _parse_pct(self.preset.volume)

        if prosody:
            # Blend: base + emotional adjustment (clamped to natural range)
            emo_rate = _parse_pct(prosody.get('rate', '+0%'))
            emo_pitch = _parse_hz(prosody.get('pitch', '+0Hz'))
            emo_vol = _parse_pct(prosody.get('volume', '+0%'))

            # Blend ratios: 70% base identity + 30% emotional influence
            blended_rate = int(base_rate * 0.7 + (base_rate + emo_rate) * 0.3)
            blended_pitch = int(base_pitch * 0.7 + (base_pitch + emo_pitch) * 0.3)
            blended_vol = int(base_vol * 0.7 + (base_vol + emo_vol) * 0.3)

            # Clamp to natural speech range
            blended_rate = max(-20, min(20, blended_rate))
            blended_pitch = max(-10, min(10, blended_pitch))
            blended_vol = max(-15, min(15, blended_vol))

            rate = f"{blended_rate:+d}%"
            pitch = f"{blended_pitch:+d}Hz"
            volume = f"{blended_vol:+d}%"
        else:
            rate = self.preset.rate
            pitch = self.preset.pitch
            volume = self.preset.volume

        logger.debug(f"TTS synth: voice={self.preset.voice_id} rate={rate} pitch={pitch} vol={volume}")
        communicate = edge_tts.Communicate(
            text,
            self.preset.voice_id,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        await communicate.save(str(out_path))

    def _synth_loop(self):
        """Pre-warms edge-tts connection + pre-caches common first phrases."""
        # Pre-warm edge-tts (saves ~500ms on first speak)
        try:
            async def _prewarm():
                comm = edge_tts.Communicate("", self.preset.voice_id)
                async for _ in comm.stream():
                    pass
            future = asyncio.run_coroutine_threadsafe(_prewarm(), self._loop)
            future.result(timeout=10)
            logger.debug("TTS pre-warm OK")
        except Exception as e:
            logger.debug(f"TTS pre-warm skipped: {e}")

        # Pre-cache common first-response phrases (instant playback)
        try:
            common = [
                "Claro, Mestre.",
                "Entendido, Mestre.",
                "Processando.",
                "Elívea online, Mestre.",
            ]
            for phrase in common:
                try:
                    clean = clean_for_speech(phrase)
                    if clean:
                        path = _TMP_DIR / f"precache_{hash(clean) & 0xFFFF:04x}.mp3"
                        if not path.exists():
                            async def _synth_pre(phrase=clean, p=path):
                                comm = edge_tts.Communicate(phrase, self.preset.voice_id,
                                                            rate=self.preset.rate, pitch=self.preset.pitch)
                                await comm.save(str(p))
                            f = asyncio.run_coroutine_threadsafe(_synth_pre(), self._loop)
                            f.result(timeout=10)
                except Exception:
                    pass
            logger.debug("TTS pre-cache OK")
        except Exception as e:
            logger.debug(f"TTS pre-cache skipped: {e}")

        while True:
            time.sleep(60)

    def _play_loop(self):
        """Ordered sequential playback with zero-gap prefetch."""
        next_seq = 1
        while True:
            result = self._pop_ready(next_seq)
            if result is _WAIT:
                time.sleep(0.005)  # SPEED: 5ms polling — fastest safe interval
                continue
            next_seq += 1
            if result is _SKIP:
                logger.debug(f"TTS play loop: SKIP seq {next_seq-1}")
                continue
            utter = result
            logger.info(f"TTS play loop: playing seq {utter.seq} \"{utter.text[:40]}...\" from {utter.path.name if utter.path else '?'}")

            was_speaking = self.is_speaking
            self.is_speaking = True
            if not was_speaking and self.on_playback_start:
                try:
                    self.on_playback_start()
                except Exception:
                    pass

            self._play_file_blocking(utter.path)

            # Natural breathing pause between sentences
            if utter.pause_after > 0:
                time.sleep(utter.pause_after)

            with self._lock:
                queue_empty = not self._queue
            if queue_empty:
                self.is_speaking = False
                if self.on_playback_end:
                    try:
                        self.on_playback_end()
                    except Exception:
                        pass

            try:
                utter.path.unlink(missing_ok=True)
            except Exception:
                pass

    def _pop_ready(self, seq: int):
        """Returns _WAIT | _SKIP | next playable _Utterance."""
        with self._lock:
            # skip past anything that was flushed away while we weren't looking
            if seq <= self._flush_seq:
                return _SKIP
            # drop stale entries first (safe, no mutation during search below)
            if self._queue and self._queue[0].seq < seq:
                self._queue = [u for u in self._queue if u.seq >= seq]
            for u in self._queue:
                if u.seq > seq:
                    return _WAIT
                # u.seq == seq
                if u.canceled:
                    self._queue.remove(u)
                    return _SKIP
                if u.ready.is_set() and u.path is not None:
                    self._queue.remove(u)
                    return u
                return _WAIT
            return _WAIT

    def _play_file_blocking(self, path: Path):
        alias = f"gs_{int(time.time() * 1000)}"
        try:
            if not path or not path.exists():
                logger.error(f"TTS play: file does not exist: {path}")
                return
            # Use correct MCI type based on file extension
            ext = path.suffix.lower()
            if ext == ".wav":
                mci_type = "waveaudio"
            else:
                mci_type = "mpegvideo"
            open_cmd = f'open "{path}" type {mci_type} alias {alias}'
            r_open = ctypes.windll.winmm.mciSendStringW(open_cmd, None, 0, 0)
            if r_open != 0:
                logger.error(f"TTS MCI open failed (code {r_open}): {path}")
                return
            self._mci_alias = alias
            r_play = ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
            if r_play != 0:
                logger.error(f"TTS MCI play failed (code {r_play}): {path}")
                return

            buf = ctypes.create_unicode_buffer(128)
            while True:
                time.sleep(0.03)  # Speed: faster MCI status check (was 60ms, now 30ms)
                if self._mci_alias != alias:   # stopped externally
                    return
                ctypes.windll.winmm.mciSendStringW(f'status {alias} mode', buf, 128, 0)
                if buf.value != 'playing':
                    return
        except Exception as e:
            logger.error(f"TTS play error: {e}", exc_info=True)
            if self.on_error:
                try: self.on_error(f"Erro de reprodução de voz: {e}")
                except Exception: pass
        finally:
            try:
                ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                if self._mci_alias == alias:
                    self._mci_alias = None
            except Exception:
                pass

    def _apply_voice_styling(self, path: Path, utterance: _Utterance) -> Path | None:
        """Apply voice styling pipeline: MP3 → WAV → voice_converter → styled WAV.

        Returns the styled WAV path on success, or None to fall back to raw MP3.
        """
        try:
            import sys as _sys
            _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _proj not in _sys.path:
                _sys.path.insert(0, _proj)
            from core.voice_converter import convert_voice
            import subprocess
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            wav_tmp = str(path).replace(".mp3", "_raw.wav")
            subprocess.run(
                [ffmpeg, "-y", "-i", str(path), "-ar", "24000", "-ac", "1", "-f", "wav", wav_tmp],
                capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if not os.path.exists(wav_tmp):
                logger.warning("TTS voice styling: ffmpeg produced no WAV output")
                return None

            wav_out = str(path).replace(".mp3", "_conv.wav")
            convert_voice(wav_tmp, wav_out)

            if os.path.exists(wav_out):
                result = Path(wav_out)
                for stale in (str(path), wav_tmp):
                    try:
                        os.unlink(stale)
                    except OSError:
                        pass
                logger.debug(f"TTS styled: {result.name}")
                return result
            else:
                logger.warning("TTS voice styling: convert_voice produced no output")
                return None

        except ImportError as e:
            logger.warning(f"TTS voice styling skipped (missing dependency): {e}")
            return None
        except Exception as e:
            logger.warning(f"TTS voice styling skipped: {e}")
            return None

    def _halt_mci(self):
        try:
            if self._mci_alias:
                ctypes.windll.winmm.mciSendStringW(f'stop {self._mci_alias}', None, 0, 0)
        except Exception:
            pass

    # ------------------------------------------------------ legacy mic (unused)
    def listen_microphone(self, timeout: int = 5) -> str | None:
        return None
