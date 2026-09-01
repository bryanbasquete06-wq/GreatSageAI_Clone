# Elívea — IA de Engenharia Autônoma

> **A IA que não só responde — ela PENSA, PROGRAMA, CORRIGE e APRENDE.**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Status-Operacional-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Licença-MIT-yellow?style=for-the-badge" />
</p>

---

## O que é o Elívea?

O Elívea é uma IA de engenharia de software que vai muito além de um chatbot. Ele é um **engenheiro autônomo** que:

- 🧠 **Raciocina** sobre problemas antes de responder
- 🔍 **Detecta e corrige bugs** automaticamente no seu código
- 🏗️ **Gera código production-ready** em qualquer linguagem
- 🐝 **Trabalha em equipe** com múltiplos agentes especializados
- ⏰ **Investiga histórico do git** para encontrar quando algo quebrou
- 📊 **Aprende** com cada interação e melhora com o tempo
- 🛡️ **Protege** contra alucinações e erros

---

## 🚀 Como Baixar (Super Fácil!)

### Passo 1: Baixe o Python

Se você ainda não tem Python instalado:

1. Acesse: **https://www.python.org/downloads/**
2. Clique no botão amarelo **"Download Python 3.x.x"**
3. Abra o arquivo baixado
4. **⚠️ MARQUE O QUADRADINHO** "Add Python to PATH" ✅
5. Clique em "Install Now"
6. Aguarde instalar

### Passo 2: Baixe o Elívea

**Opção A — Com Git (mais fácil):**
1. Abra o **Prompt de Comando** ou **Terminal**
2. Cole e pressione Enter:
```bash
git clone https://github.com/bryanbasquete06-wq/GreatSageAI_Clone.git
cd GreatSageAI_Clone
```

**Opção B — Sem Git:**
1. Vá ao repositório no GitHub
2. Clique no botão verde **"<> Code"**
3. Clique em **"Download ZIP"**
4. Descompacte o arquivo
5. Abra a pasta descompactada

### Passo 3: Instale as Dependências

No terminal, dentro da pasta do projeto, cole:
```bash
pip install -r requirements.txt
```

**Pronto!** As dependências serão instaladas automaticamente.

### Passo 4: Configure sua API Key

1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```
2. Abra o arquivo `.env` em qualquer editor de texto
3. Coloque sua chave de API:
   ```
   GEMINI_API_KEY=sua_chave_aqui
   ```
   
**Onde pegar a chave?** gratuitamente em:
- **Google Gemini**: https://aistudio.google.com/apikey (grátis!)

### Passo 5: Execute!

```bash
python elvea_app.py
```

**Isso é tudo!** O Elívea vai abrir na sua tela. 🎉

---

## 🖥️ Interface

O Elívea tem uma interface holográfica inspirada em anime:

- **Painel Esquerdo**: Chat com a IA
- **Centro**: Círculo mágico animado com runas
- **Painel Direito**: Monitor do sistema, ações rápidas
- **Deep Dev Panel**: Para engenharia autônoma (Ctrl+D)

---

## 🧠 Comandos Disponíveis

### Chat Normal
| Comando | O que faz |
|---------|-----------|
| `status` | Mostra status do sistema |
| `crie uma API` | Gera código completo |
| `debug este erro` | Analisa e corrige bugs |
| `teste` | Gera testes unitários |
| `refatore` | Melhora o código existente |
| `pesquise sobre X` | Busca na web |
| `ajuda` | Lista todos os comandos |

### Deep Dev Panel
| Comando | O que faz |
|---------|-----------|
| `/shadow` | Análise autônoma de bugs |
| `/timemachine` | Investigação de regressões no git |
| `scan secrets` | Busca dados sensíveis no código |
| `approve shadow` | Aprova correções sugeridas |

---

## 🏗️ Arquitetura

```
elvea/
├── core/                    # Motor da IA
│   ├── engine.py           # Motor principal
│   ├── llm.py              # Provedores LLM (Gemini, OpenAI, etc.)
│   ├── memory.py           # Memória inteligente (BM25 + relevância)
│   ├── persona.py          # Personalidade e system prompt
│   ├── intelligence_engine.py  # Enriquecimento de contexto
│   ├── deep_dev/           # Engenharia autônoma
│   │   ├── shadow_dev.py   # Detecção automática de bugs
│   │   ├── time_machine.py # Investigação temporal no git
│   │   ├── safety.py       # Sandbox e segurança
│   │   └── engine.py       # Orquestrador
│   ├── intelligence/       # Sistemas inteligentes
│   │   ├── hallucination_guard.py  # Anti-alucinação
│   │   ├── self_correction.py      # Auto-correção
│   │   ├── quality_score.py        # Scoring de qualidade
│   │   ├── knowledge_graph.py      # Grafo de conhecimento
│   │   └── intent_predictor.py     # Predição de intenção
│   ├── agent/              # Agente autônomo
│   ├── swarm/              # Múltiplos agentes especializados
│   └── ...                 # +20 módulos core
├── ui/                      # Interface gráfica
│   ├── qt_ui.py            # Janela principal (PySide6)
│   ├── deep_dev_panel.py   # Painel Deep Dev
│   └── ...                 # Widgets holográficos
├── .env.example             # Template de configuração
├── pyproject.toml           # Metadados do projeto
└── elvea_app.py            # Ponto de entrada GUI
```

---

## 🔧 Pré-requisitos

- **Python** 3.10 ou superior
- **Sistema**: Windows 10+, macOS 10.15+, ou Linux
- **RAM**: 4GB mínimo (8GB recomendado)
- **Espaço**: 500MB livres
- **Internet**: Necessária para providers LLM (exceto modo offline)

---

## 📜 Licença

MIT License — use como quiser, comercialize, modifique.

---

## 💬 Suporte

Se encontrar problemas:
1. Abra uma **Issue** no GitHub
2. Descreva o erro com detalhes
3. Anexe prints ou logs se possível

---

**Feito com ❤️ por bryan**
