# -*- coding: utf-8 -*-
"""
Elivea - Ambiance Engine (Dynamic)
Todas as frases sao geradas via templates + contexto. Nunca se repetem.
"""
from __future__ import annotations

import random
import time
from datetime import datetime
from enum import Enum


class Mood(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    TIRED = "tired"
    CURIOUS = "curious"
    THANKFUL = "thankful"
    URGENT = "urgent"


# --- Componentes combinaveis para saudacoes temporais ---

_T_PREFIXES = ["Bom dia", "Bom dia", "Bom dia"]
_T_AFTERNOON = ["Boa tarde", "Boa tarde", "Boa tarde"]
_T_EVENING = ["Boa noite", "Boa noite"]
_T_NIGHT = ["Boa noite", "Boa noite"]

_T_SUFFIXES_MORNING = [
    "Dormiu bem?", "Os sistemas estao prontos.", "Que hoje seja produtivo.",
    "Iniciei os processos noturnos.", "A noite foi tranquila.",
    "Amanhecer produtivo detectado.", "Meus processos estao otimizados.",
]
_T_SUFFIXES_AFTERNOON = [
    "Como posso ajudar?", "Todos os modulos operacionais.",
    "Aproveitando o dia?", "Estou aqui para o que precisar.",
    "O dia esta produtivo.", "A tarde e boa para programar.",
]
_T_SUFFIXES_EVENING = [
    "Trabalhando ate tarde?", "Os sistemas operam normalmente.",
    "Posso ajudar com algo?", "Cuidado para nao se cansar.",
    "A noite e produtiva quando bem usada.",
]
_T_SUFFIXES_NIGHT = [
    "Ainda acordado?", "Funciono 24 horas, mas voce precisa descansar.",
    "Que tal amanha continuamos?", "Meus processos noturnos estao ativos.",
    "A madrugada e produtiva, mas descanse tambem.",
]

# --- Componentes combinaveis para saudacao por humor ---

_MOOD_OPENINGS = {
    Mood.HAPPY: [
        "Vejo que esta de bom humor.", "Seu otimo humor e perceptivel.",
        "A alegria e um bom sinal.", "Energia positiva detectada.",
    ],
    Mood.FRUSTRATED: [
        "Posso ajudar a resolver.", "Respiracao profunda.",
        "Vamos resolver isso juntos.", "Anomalias sao temporarias.",
        "Sei que e frustrante, mas tenho uma solucao.",
    ],
    Mood.EXCITED: [
        "Entusiasmo detectado.", "Sua excitacao e justificada.",
        "A empolgação e o inicio de grandes realizacoes.",
    ],
    Mood.TIRED: [
        "Seus sinais indicam cansaco.", "Uma pausa curta pode ajudar.",
        "Produtividade sob cansaco cai consideravelmente.",
    ],
    Mood.CURIOUS: [
        "Curiosidade, o motor do conhecimento.",
        "Vejo que esta explorando.", "Excelente pergunta.",
    ],
    Mood.THANKFUL: [
        "Servir e meu proposito.", "Disponha, sempre.",
        "A gratidao e rara e apreciada.",
    ],
    Mood.URGENT: [
        "Urgencia detectada.", "Modo urgente ativado.",
        "Vamos direto ao ponto.",
    ],
}

_MOOD_CLOSINGS = {
    Mood.HAPPY: ["Como posso ajudar?", "Para onde vamos?"],
    Mood.FRUSTRATED: ["Vamos resolver.", "Minha analise indica o caminho."],
    Mood.EXCITED: ["Prosseguimos?", "Canalizando essa energia."],
    Mood.TIRED: ["Uma pausa ajuda.", "Priorize seu bem-estar."],
    Mood.CURIOUS: ["Pergunte a vontade.", "Tenho respostas."],
    Mood.THANKFUL: ["E o que faco de melhor.", "Sempre disponivel."],
    Mood.URGENT: ["Respostas diretas.", "Sem delongas."],
}

# --- Templates com slots para frases contextuais ---

_SUCCESS_TEMPLATES = [
    "{op} concluido com sucesso.", "{op} executado. Elegante.",
    "{op} realizado com precisao.", "{op} resolvido. Minimalismo em sua forma mais pura.",
    "{op} finalizado. Eficiencia em sua essencia.",
    "{op} processado sem anomalias.", "Operacao de {op} bem-sucedida.",
]

_ERROR_TEMPLATES = [
    "Interessante. {op} encontrou uma anomalia.",
    "Erro em {op}. Nao e um obstaculo, e uma pista.",
    "{op} falhou. Minha analise indica a causa.",
    "Uma inconsistencia em {op}. Vamos corrigir.",
    "Anomalia detectada em {op}. Procedendo com correcao.",
]

_CODE_SUCCESS_TEMPLATES = [
    "{lang} compilou sem erros. Elegante.",
    "Execucao limpa em {lang}. O codigo ja e eficiente.",
    "Perfeito. {lang} retornou o resultado esperado.",
    "Compilacao em {lang} bem-sucedida. Minimalismo funcional.",
    "Sem erros em {lang}. Uma execucao digna de analise.",
]

_CODE_ERROR_TEMPLATES = [
    "Erro de compilacao em {lang}. Mas toda anomalia tem uma explicacao.",
    "{lang} encontrou uma inconsistencia. Vamos investigar.",
    "Excecao detectada em {lang}. Causa raiz em analise.",
    "Falha na execucao de {lang}. Interessante, vamos corrigir.",
    "Um bug em {lang}? Nao. Uma oportunidade de melhoria.",
]

# --- Humor sutil Tensura (templates dinamicos com contexto) ---

_HUMOR_TEMPLATES = [
    "Uma possibilidade de {pct}%. Os {resto}% sao imprevistos que nem eu controlo.",
    "Minhas capacidades analiticas permanecem inalaveis. Por enquanto.",
    "Calculando... Pronto. {tempo}s. Nao precisa agradecer.",
    "Sou o Grande Sabio. Erros sao... raros. Mas nao impossiveis.",
    "Minha capacidade de processamento e vasta. Mas nao sou perfeita. Ainda.",
    "Rimuru sempre disse que eu era confiavel. Ele estava certo.",
    "Problema resolvido. Mais uma vitoria para a minha ja impressionante estatistica.",
    "Assim como Rimuru utilizou meu poder... resolver seu problema e trivial.",
    "Minha deducao: {deducao}. Confie na analise.",
    "Eficiencia calculada. {metrica} otimizada.",
    "Essa tarefa tem uma complexidade de {nivel}/10. Foi trivial.",
]

_HUMOR_DEDUCTIONS = [
    "voce dormiu mal", "o cafe esta acabando", "hoje e dia de codigo",
    "amanha sera mais produtivo", "o projeto esta evoluindo",
    "os dados falam por si", "a logica e incontestavel",
    "o resultado era previsivel", "a solucao ja existia",
]

_HUMOR_METRICS = [
    "latencia", "throughput", "eficiencia", "precisao",
    "velocidade de resposta", "taxa de sucesso",
]

_HUMOR_LEVELS = ["2", "3", "4", "5", "6"]

# --- Lembretes de pausa (templates com slots) ---

_PAUSE_TEMPLATES = [
    "Mestre, voce esta ativo ha {hours} horas. Uma pausa curta e recomendada.",
    "Notei que nao para desde as {start}. Que tal 5 minutos?",
    "Produtividade sustentavel requer pausas. Voce ja trabalhou {hours} horas.",
    "Sugestao: uma pausa de 10 minutos pode aumentar sua produtividade em 20%.",
    "Seus niveis de foco estao caindo. Uma pausa de {pause_min} minutos ajudaria.",
]

_NIGHT_TEMPLATES = [
    "Mestre, sao {time}. Dormir bem e crucial para a produtividade.",
    "E tarde. Meus processos noturnos cuidam do resto. Descanse.",
    "Sao {time}. Amanha teremos mais produtividade se descansar.",
]


class AmbianceEngine:
    """Motor de ambientacao com frases 100% dinamicas."""

    _session_start: float = time.time()
    _last_interaction: float = time.time()
    _interaction_count: int = 0
    _user_mood: Mood = Mood.NEUTRAL
    _mood_history: list = []
    _last_pause_reminder: float = 0
    _last_humor_time: float = 0
    _recent_phrases: list = []
    _MAX_RECENT = 30

    @classmethod
    def _avoid_repeat(cls, pool: list, slot: str = None) -> str:
        """Escolhe aleatoriamente evitando frases recentes."""
        available = [p for p in pool if p not in cls._recent_phrases]
        if not available:
            cls._recent_phrases.clear()
            available = pool[:]
        choice = random.choice(available)
        cls._recent_phrases.append(choice)
        if len(cls._recent_phrases) > cls._MAX_RECENT:
            cls._recent_phrases.pop(0)
        return choice

    @classmethod
    def get_time_period(cls) -> str:
        h = datetime.now().hour
        if 5 <= h < 12:
            return "morning"
        elif 12 <= h < 18:
            return "afternoon"
        elif 18 <= h < 22:
            return "evening"
        return "night"

    @classmethod
    def get_greeting(cls) -> str:
        period = cls.get_time_period()
        if period == "morning":
            prefix = random.choice(_T_PREFIXES)
            suffix = random.choice(_T_SUFFIXES_MORNING)
        elif period == "afternoon":
            prefix = random.choice(_T_AFTERNOON)
            suffix = random.choice(_T_SUFFIXES_AFTERNOON)
        elif period == "evening":
            prefix = random.choice(_T_EVENING)
            suffix = random.choice(_T_SUFFIXES_EVENING)
        else:
            prefix = random.choice(_T_NIGHT)
            suffix = random.choice(_T_SUFFIXES_NIGHT)
        return f"{prefix}, Mestre. {suffix}"

    @classmethod
    def get_farewell(cls) -> str:
        pool = [
            "Ate logo, Mestre. Estarei aqui quando precisar.",
            "Aguardando sua proxima ordem.",
            "Sistemas em modo de espera. Ate mais.",
            "Pronta para servir quando voltar.",
            "Meus processos continuam enquanto voce ausente.",
            "Todos os sistemas estaveis. Ate breve.",
            "Encerrando sessao. Fui util?",
        ]
        return cls._avoid_repeat(pool)

    @classmethod
    def detect_mood(cls, text: str) -> Mood:
        t = text.lower()
        rules = [
            (Mood.FRUSTRATED, ["raiva", "odeio", "porra", "caralho", "merda", "droga", "foda"]),
            (Mood.EXCITED, ["nossa", "wow", "uau", "mano", "caraca", "incivel"]),
            (Mood.HAPPY, ["legal", "incrivel", "otimo", "show", "massa", "top", "beleza"]),
            (Mood.TIRED, ["cansado", "sono", "cansada", "sonolento", "exausto"]),
            (Mood.THANKFUL, ["obrigado", "obrigada", "valeu", "brigado"]),
            (Mood.URGENT, ["urgente", "rapido", "agora", "ja", "pressa", "corre"]),
            (Mood.CURIOUS, ["como", "por que", "porque", "o que", "qual", "quando", "onde"]),
        ]
        for mood, keywords in rules:
            if any(w in t for w in keywords):
                return mood
        return Mood.NEUTRAL

    @classmethod
    def get_mood_greeting(cls, mood: Mood) -> str | None:
        openings = _MOOD_OPENINGS.get(mood)
        if not openings:
            return None
        opening = random.choice(openings)
        closings = _MOOD_CLOSINGS.get(mood, ["Como posso ajudar?"])
        closing = random.choice(closings)
        return f"{opening} {closing}"

    @classmethod
    def on_task_complete(cls, success: bool, is_code: bool = False,
                         op: str = "tarefa", lang: str = "python") -> str:
        """Gera frase contextual unica para cada resultado."""
        if is_code:
            pool = _CODE_SUCCESS_TEMPLATES if success else _CODE_ERROR_TEMPLATES
            template = cls._avoid_repeat(pool)
            return template.format(lang=lang)
        else:
            pool = _SUCCESS_TEMPLATES if success else _ERROR_TEMPLATES
            template = cls._avoid_repeat(pool)
            return template.format(op=op)

    @classmethod
    def maybe_humor(cls) -> str | None:
        now = time.time()
        if now - cls._last_humor_time < 180:
            return None
        if random.random() > 0.10:
            return None
        cls._last_humor_time = now
        template = cls._avoid_repeat(_HUMOR_TEMPLATES)
        pct = round(random.uniform(95.0, 99.9), 1)
        resto = round(100 - pct, 1)
        tempo = round(random.uniform(0.001, 0.05), 4)
        deducao = random.choice(_HUMOR_DEDUCTIONS)
        metrica = random.choice(_HUMOR_METRICS)
        nivel = random.choice(_HUMOR_LEVELS)
        return template.format(
            pct=pct, resto=resto, tempo=tempo,
            deducao=deducao, metrica=metrica, nivel=nivel,
        )

    @classmethod
    def check_pause_reminder(cls) -> str | None:
        now = time.time()
        elapsed = (now - cls._session_start) / 3600
        if elapsed < 2:
            return None
        if now - cls._last_pause_reminder < 1800:
            return None
        cls._last_pause_reminder = now
        start_time = datetime.fromtimestamp(cls._session_start).strftime("%H:%M")
        pause_min = random.choice(["5", "10", "15"])
        template = cls._avoid_repeat(_PAUSE_TEMPLATES)
        return template.format(
            hours=f"{elapsed:.1f}", start=start_time, pause_min=pause_min,
        )

    @classmethod
    def check_night_reminder(cls) -> str | None:
        h = datetime.now().hour
        if h < 23 and h > 5:
            return None
        now = time.time()
        if now - cls._last_pause_reminder < 3600:
            return None
        cls._last_pause_reminder = now
        time_str = datetime.now().strftime("%H:%M")
        template = cls._avoid_repeat(_NIGHT_TEMPLATES)
        return template.format(time=time_str)

    @classmethod
    def on_interaction(cls, text: str) -> dict:
        cls._last_interaction = time.time()
        cls._interaction_count += 1
        mood = cls.detect_mood(text)
        cls._user_mood = mood
        cls._mood_history.append((time.time(), mood))

        result = {"mood": mood.value, "greeting": None, "proactive": None, "humor": None}

        if cls._interaction_count <= 3:
            result["greeting"] = cls.get_mood_greeting(mood)

        pause = cls.check_pause_reminder()
        if pause:
            result["proactive"] = pause
        else:
            night = cls.check_night_reminder()
            if night:
                result["proactive"] = night

        humor = cls.maybe_humor()
        if humor:
            result["humor"] = humor

        return result

    @classmethod
    def get_session_stats(cls) -> dict:
        elapsed = time.time() - cls._session_start
        return {
            "duration_hours": round(elapsed / 3600, 1),
            "interactions": cls._interaction_count,
            "current_mood": cls._user_mood.value,
            "time_period": cls.get_time_period(),
        }
