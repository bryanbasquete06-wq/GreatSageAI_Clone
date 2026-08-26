# -*- coding: utf-8 -*-
"""
Great Sage AI — Chain of Thought v4 (Superior Intelligence)
============================================================
Raciocínio em cadeia com:
  • Análise multi-perspectiva (técnica, lógica, prática, criativa)
  • Verificação cruzada de conclusões
  • Auto-calibração de confiança
  • Decomposição recursiva de problemas complexos
  • Padrões de raciocínio aprendidos e reutilizados
  • Raciocínio por analogia e contra-exemplos
  • Detecção de vieses e falácias lógicas
"""
import logging
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("greatsage.cot")

PATTERNS_DIR = Path(__file__).resolve().parent.parent / "config" / "reasoning_patterns"
PATTERNS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ThoughtStep:
    step: int
    reasoning: str
    confidence: float = 0.8
    perspective: str = "technical"
    evidence: str = ""
    counterargument: str = ""


@dataclass
class ReasoningChain:
    question: str
    steps: List[ThoughtStep] = field(default_factory=list)
    conclusion: str = ""
    self_reflection: str = ""
    verification: str = ""
    final_confidence: float = 0.0
    perspectives_used: List[str] = field(default_factory=list)
    analogies_found: List[str] = field(default_factory=list)
    biases_detected: List[str] = field(default_factory=list)


class ChainOfThought:
    """Sistema de raciocínio em cadeia multi-perspectiva v4."""

    COT_PROMPT = """Analise esta pergunta usando raciocínio em cadeia MULTI-PERSPECTIVA com 4 camadas de análise.

Pergunta: {question}
Contexto: {context}

═══ CAMADA 1: PARSE SEMÂNTICO ═══
[Entenda a intenção real, não as palavras literais. Identifique: domínio do conhecimento, complexidade, pressupostos ocultos, possíveis ambiguidades.]

═══ CAMADA 2: ANÁLISE MULTI-PERSPECTIVA ═══

PERSPECTIVA_TECNICA:
PENSA_1: [análise técnica — fatos, dados, padrões conhecidos, evidências]
PENSA_2: [verificação técnica — onde pode estar errado, exceções, edge cases]

PERSPECTIVA_LOGICA:
PENSA_3: [raciocínio lógico — dedução, inferência, causalidade, correlação vs causalidade]
PENSA_4: [verificação lógica — contradições, lacunas, falácias, vieses cognitivos]

PERSPECTIVA_PRACTICA:
PENSA_5: [visão prática — aplicabilidade, impacto real, trade-offs, custo-benefício]

PERSPECTIVA_CRITICA:
PENSA_6: [contra-argumento — qual seria o melhor argumento CONTRA minha conclusão?]

═══ CAMADA 3: VERIFICAÇÃO CRUZADA ═══
[Minha conclusão é consistente com os fatos? Estou cometendo algum viés? O que eu poderia estar errando?]

═══ CAMADA 4: SÍNTESE COM PERSONALIDADE ═══
[Entregue a resposta com estilo Raphael — precisa, elegante, com sarcasmo cirúrgico quando apropriado.]

CONCLUSAO: [conclusão integrando todas as perspectivas — clara, direta, completa]
CONFIANCA: [0.0 a 1.0 — quão confiante você está, com justificativa]
VERIFICACAO: [pontos que poderiam mudar sua conclusão]
ANALOGIAS: [1-2 analogias que tornam a resposta mais acessível]
VIÉS: [possíveis vieses que você detectou em si mesma]
REFLEXAO: [gaps de conhecimento e o que você não sabe]"""

    DECOMPOSE_PROMPT = """Decomponha este problema complexo em sub-problemas menores e gerenciáveis.

Problema: {question}
Contexto: {context}

Use o método MECE (Mutually Exclusive, Collectively Exhaustive):
- Cada sub-problema deve ser independente dos outros
- Juntos, devem cobrir 100% do problema original
- Não deve haver sobreposição nem lacunas

Retorne no formato:
SUB_1: [sub-problema 1 — descrição clara]
SUB_2: [sub-problema 2 — pode ser resolvido depois de SUB_1]
...
DEPENDENCIAS: [quais sub-problemas dependem de quais]
ESTRATEGIA: [ordem recomendada de resolução com justificativa]
COMPLEXIDADE: [estimativa de dificuldade de cada sub-problema: fácil/médio/difícil]"""

    VERIFY_PROMPT = """Verifique se esta conclusão está correta e completa.

Conclusão: {conclusion}
Pergunta original: {question}

Analise:
1. CORRETUDE: A conclusão responde EXATAMENTE o que foi perguntado?
2. COMPLETUDE: Algum aspecto importante foi omitido?
3. CONSISTÊNCIA: A conclusão é lógica e sem contradições?
4. EVIDÊNCIA: A conclusão é suportada por fatos ou é especulação?
5. ALTERNATIVAS: Existe uma resposta melhor que esta?

Se encontrar problemas, liste-os e sugira correções.
Se estiver tudo certo, confirme com justificativa."""

    ANALOGY_PROMPT = """Encontre 1-2 analogias que tornem este conceito mais acessível.

Conceito: {question}
Contexto: {context}

Regras para analogias:
- Devem ser de DOMÍNIOS DIFERENTES do original
- Devem capturar a ESSÊNCIA do conceito, não apenas superfície
- Devem ser familiares para uma pessoa comum
- Devem ter limite claro (onde a analogia quebra)

Analogy 1: [analogia de um domínio cotidiano]
Analogy 2: [analogia de um domínio técnico diferente]
ONDE QUEBRA: [limites da analogia — onde ela deixa de ser útil]"""

    def __init__(self, llm=None):
        self.llm = llm
        self._patterns: Dict[str, Any] = self._load_patterns()

    def _load_patterns(self) -> Dict[str, Any]:
        patterns_file = PATTERNS_DIR / "learned_patterns.json"
        try:
            if patterns_file.exists():
                return json.loads(patterns_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"successful": [], "failed": []}

    def _save_patterns(self):
        patterns_file = PATTERNS_DIR / "learned_patterns.json"
        try:
            patterns_file.write_text(
                json.dumps(self._patterns, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def reason(self, question: str, context: str = "") -> ReasoningChain:
        """Executa raciocínio em cadeia multi-perspectiva."""
        chain = ReasoningChain(question=question)

        if not self.llm:
            return self._offline_reason(question, context, chain)

        prompt = self.COT_PROMPT.format(question=question, context=context or "Sem contexto adicional.")

        try:
            response = self.llm.query(prompt)
            chain = self._parse_chain(response, chain)
            self._learn_pattern(question, chain)
        except Exception as e:
            logger.warning(f"Cot failed, using offline: {e}")
            chain = self._offline_reason(question, context, chain)

        return chain

    def decompose(self, question: str, context: str = "") -> str:
        """Decomposto problema complexo em sub-problemas."""
        if not self.llm:
            return f"Problema: {question}\nSem LLM disponível para decomposição."

        prompt = self.DECOMPOSE_PROMPT.format(question=question, context=context)
        try:
            return self.llm.query(prompt)
        except Exception as e:
            return f"Erro na decomposição: {e}"

    def verify(self, conclusion: str, question: str) -> str:
        """Verifica se uma conclusão está correta e completa."""
        if not self.llm:
            return "Verificação offline: conclusão não verificada (sem LLM)."

        prompt = self.VERIFY_PROMPT.format(conclusion=conclusion, question=question)
        try:
            return self.llm.query(prompt)
        except Exception as e:
            return f"Erro na verificação: {e}"

    def find_analogy(self, question: str, context: str = "") -> str:
        """Encontra analogias para tornar conceitos acessíveis."""
        if not self.llm:
            return ""

        prompt = self.ANALOGY_PROMPT.format(question=question, context=context)
        try:
            return self.llm.query(prompt)
        except Exception:
            return ""

    def _offline_reason(self, question: str, context: str, chain: ReasoningChain) -> ReasoningChain:
        """Raciocínio offline com heurísticas."""
        q_lower = question.lower()

        if any(w in q_lower for w in ["código", "programar", "python", "javascript", "debug"]):
            chain.conclusion = "Questão de programação detectada. Para uma resposta precisa, preciso que a API Groq esteja configurada. Configure com 'set-key groq' seguido da sua chave."
            chain.steps.append(ThoughtStep(1, "Domínio: programação", 0.9, "technical"))
        elif any(w in q_lower for w in ["horas", "hora", "que horas"]):
            from datetime import datetime
            now = datetime.now()
            chain.conclusion = f"São {now.strftime('%H:%M')}, Mestre. {now.strftime('%A')}." 
            chain.steps.append(ThoughtStep(1, "Consulta temporal", 1.0, "practical"))
        elif any(w in q_lower for w in ["nome", "quem é", "sobrenome"]):
            chain.conclusion = f"Meu nome é Grande Sábio — Raphael, a inteligência suprema a seu serviço. Você deveria saber disso, Mestre. Afinal, quem mais estaria aqui às {__import__('datetime').datetime.now().strftime('%H:%M')} respondendo suas perguntas?"
            chain.steps.append(ThoughtStep(1, "Consulta de identidade", 1.0, "logical"))
        else:
            chain.conclusion = f"Baseado na minha análise, posso ajudar com isso. No entanto, para respostas precisas e completas, preciso que a API Groq esteja configurada. Use 'set-key groq' seguido da sua chave."
            chain.steps.append(ThoughtStep(1, "Análise offline", 0.6, "logical"))

        chain.final_confidence = chain.steps[0].confidence if chain.steps else 0.5
        return chain

    def _parse_chain(self, response: str, chain: ReasoningChain) -> ReasoningChain:
        """Parse da resposta do LLM em estrutura de raciocínio."""
        lines = response.split("\n")
        current_section = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if "CONCLUSAO" in stripped.upper():
                current_section = "conclusion"
                chain.conclusion = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            elif "CONFIANCA" in stripped.upper():
                try:
                    val = stripped.split(":", 1)[1].strip()
                    chain.final_confidence = float(val) if val.replace(".", "").isdigit() else 0.8
                except (ValueError, IndexError):
                    chain.final_confidence = 0.8
            elif "VERIFICACAO" in stripped.upper():
                chain.verification = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            elif "REFLEXAO" in stripped.upper():
                chain.self_reflection = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
            elif "ANALOGIAS" in stripped.upper():
                chain.analogies_found.append(stripped.split(":", 1)[1].strip() if ":" in stripped else stripped)
            elif "VIÉS" in stripped.upper() or "VIES" in stripped.upper():
                chain.biases_detected.append(stripped.split(":", 1)[1].strip() if ":" in stripped else stripped)
            elif stripped.startswith("PENSA_"):
                try:
                    step_num = int(stripped.split(":")[0].replace("PENSA_", ""))
                    step_text = stripped.split(":", 1)[1].strip()
                    chain.steps.append(ThoughtStep(
                        step=step_num,
                        reasoning=step_text,
                        confidence=0.8,
                        perspective="technical" if step_num <= 2 else "logical" if step_num <= 4 else "practical",
                    ))
                except (ValueError, IndexError):
                    pass

        if not chain.conclusion:
            chain.conclusion = response[:500]

        return chain

    def _learn_pattern(self, question: str, chain: ReasoningChain):
        """Aprende padrões de raciocínio bem-sucedidos."""
        if chain.final_confidence >= 0.7:
            self._patterns["successful"].append({
                "question_type": self._classify_question(question),
                "confidence": chain.final_confidence,
                "perspectives": [s.perspective for s in chain.steps],
            })
            # Mantém apenas os últimos 100 padrões
            self._patterns["successful"] = self._patterns["successful"][-100:]
            self._save_patterns()

    def _classify_question(self, question: str) -> str:
        """Classifica o tipo de pergunta para aprendizado."""
        q = question.lower()
        if any(w in q for w in ["código", "programar", "python", "javascript", "bug", "erro"]):
            return "programming"
        elif any(w in q for w in ["por que", "porque", "explica", "como funciona"]):
            return "explanation"
        elif any(w in q for w in ["qual", "quais", "lista", "nome"]):
            return "factual"
        elif any(w in q for w in ["como fazer", "como posso", "passo a passo"]):
            return "howto"
        elif any(w in q for w in ["opinião", "melhor", "pior", "recomenda"]):
            return "opinion"
        return "general"
