# 🧠 Elívea — Descrição Completa do Sistema

> **Nome:** Elívea (anteriormente Great Sage / Grande Sábio)
> **Versão:** 2.0
> **Autor:** bryan (bryanbasquete06-wq)
> **Framework:** Python 3.11 + PySide6 (Qt6)
> **Arquivo:** 156 arquivos .py | ~63.700 linhas de código
> **Plataforma:** Windows (compatível com Linux via adaptações)

---

## 📋 RESUMO GERAL

Elívea é uma IA de desktop completa com interface gráfica holográfica estilo Tensei Shitara Slime (Tensura), voz neural, 15+ providers de LLM gratuitos, memória persistente, autocorreção, e um painel de programação integrado. É projetada para ser uma assistente pessoal autônoma e autodidática.

---

## 🏗️ ARQUITETURA DO SISTEMA

```
┌─────────────────────────────────────────────────────────────┐
│                    Elívea Desktop App                        │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  UI (Qt6)    │  Core Engine │  Modules     │  Intelligence  │
│  20 arquivos │  59 arquivos │  27 arquivos │  5 subsystemos │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ qt_ui.py     │ engine.py    │ clipboard.py │ hallucination_ │
│ chat_panel.py│ llm.py       │ screen_ctx.py│   guard.py     │
│ deep_dev.py  │ speech.py    │ rag.py       │ quality_score  │
│ programming  │ memory.py    │ multilang.py │ intent_        │
│   _panel.py  │ autonomous.py│ learning.py  │   predictor.py │
│ command_     │ voice_       │ plugin_sys.py│ knowledge_     │
│   palette.py │   pipeline.py│ message_     │   graph.py     │
│ provider_    │ code_        │   monitor.py │ self_          │
│   status.py  │   analyzer.py│ web.py       │   correction.py│
│ professional │ nine_router  │ superuser.py │                │
│   _widgets.py│ multi_       │ browser_     │                │
│ orb_widget.py│   provider.py│   agent.py   │                │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

---

## 🎨 INTERFACE GRÁFICA (UI)

### Janela Principal — `ui/qt_ui.py` (EliveaMainWindow)
- **1400x850px** janela com tema holográfico dark/gold
- **Layout:** Chat Sidebar (esquerda) + RuneCore Center (centro) + Painel Direito
- **Keyboard shortcuts:** Ctrl+K (Command Palette), Ctrl+P (Code Workspace), Ctrl+Shift+P (Programming Panel), F1 (Help), Escape (fechar overlays)
- **Detecção automática de tema** baseada no horário do dia (manhã=dourado, tarde=brilhante, noite=azul, madrugada=vermelho)

### RuneCoreWidget — `ui/professional_widgets.py`
- **Círculo mágico anime** com 10 camadas de geometria sagrada
- Camadas: soul glow → lens flare → magic circle ring → hexagram → inner hexagon → connecting lines → center orb → pulsing rings → orbiting arcs → rune anchor points
- **Reage a 6 estados:** idle, thinking, speaking, success, error, listening
- **Reage a áudio** via `set_audio_level()`
- **Rotação:** 3 anéis rúnicos girando em velocidades diferentes
- **Partículas flutuantes** com vida útil e decaimento
- **Ondas de choque** em transições de estado

### AbilityAwakeningOverlay — Animação de Abertura
- **5 fases:** Dark void → Explosion → Magic circle → Elívea reveal → Fade out
- Duração: ~8 segundos
- Efeitos: flash, shockwaves, runes progressivas, particles burst
- Texto: "贤者" (贤者) → "＜Elívea＞" com glow

### Chat Panel — `ui/chat_panel.py`
- **Bolhas de mensagem** custom painted com tema Tensura
- **Streaming** de respostas LLM com throttle (12 updates/s)
- **Typing indicator** animado
- **Sidebar de histórico** com toggle

### Programming Panel — `ui/programming_panel.py`
- **IDE completo** com syntax highlighting (Python, JS, TS, HTML, CSS, etc.)
- **Auto-complete** popup
- **Find & Replace** bar
- **File explorer** integrado
- **Output panel** para execução de código
- **Line numbers** com área custom painted

### Deep Dev Panel — `ui/deep_dev_panel.py`
- **Shadow Dev Mode:** auto-scan de bugs em background
- **Time Machine Debugger:** investigação temporal de bugs
- **Diff viewer** interativo com botões [Aplicar] [Descartar]
- **3 tabs:** Painel, Shadow Dev, Time Machine

### Command Palette — `ui/command_palette.py` (Ctrl+K)
- **Busca fuzzy** de comandos
- **Categorias:** System, Memory, Router, Intelligence, Dev
- **30+ comandos** registrados

### Provider Status Panel — `ui/provider_status_panel.py`
- **Status em tempo real** de todos os providers (verde/amarelo/vermelho)
- **Barras de uso** animadas (RPM + RPD)
- **Capacity header** combinado
- **Auto-refresh** a cada 5 segundos

### Outros Componentes UI
- **OrbWidget** — orbe flutuante companion (visível quando janela minimizada)
- **SystemMonitor** — CPU, RAM, disco em tempo real
- **AIStatus** — modelo ativo, latência, TTFT
- **QuickActions** — botões de ação rápida
- **StatusBar** — informações do sistema
- **AmbientParticles** — partículas de fundo atmosféricas
- **MicroInteractions** — confetti em success, shake em error
- **NotificationToast** — notificações flutuantes
- **ConversationHistoryMap** — grafo interativo de conversas
- **HistoryDrawer** — drawer de histórico completo
- **CodeWorkspace** — editor de código overlay
- **CodeScratchpad** — area de anotações de código
- **SetupWizard** — assistente de configuração
- **InstallerGUI** — instalador visual com MagicCircle
- **TrayIcon** — ícone na bandeja com menu

---

## 🧠 MOTOR LLM — Multi-Provider Router

### Providers Suportados (15+)
| Provider | Modelo Principal | Tier |
|----------|-----------------|------|
| **Groq** | openai/gpt-oss-120b | ⚡ Blazing |
| **Gemini** | gemini-3.6-flash | 🔹 Fast |
| **OpenRouter** | llama-3.3-70b-instruct | 🔹 Fast |
| **Cerebras** | llama-3.3-70b | 🔹 Fast |
| **HuggingFace** | Llama-3.3-70B-Instruct | ◇ Basic |
| **Ollama** | llama3.1:8b (local) | 🏠 Local |
| **Mistral** | mistral-small-latest | 🔹 Fast |
| **NVIDIA NIM** | llama-3.1-8b-instruct | ◇ Basic |
| **Cloudflare** | llama-3.3-70b | ◇ Basic |
| **Together** | llama-3.3-70b-instruct | ◇ Basic |
| **SambaNova** | llama-3.3-70b | ◇ Basic |
| **Fireworks** | llama-v3.3-70b | ◇ Basic |
| **Cohere** | command-r-plus | ◇ Basic |
| **DeepSeek** | deepseek-chat | ◇ Basic |
| **Zhipu** | glm-4-flash | ◇ Basic |

### Funcionalidades do Router
- **Health Score** por provider (0-100)
- **Circuit Breaker** — provider removido após 5 erros consecutivos
- **Exponential Backoff** — recovery automático (30s → 60s → 120s → 5min)
- **Token Usage Tracking** — log JSONL de cada request
- **Cost Estimation** — comparação com APIs pagas (GPT-4o, Claude, ChatGPT Plus)
- **Round-Robin Load Balancing** — distribuição equilibrada de requests
- **Lazy Client Init** — imports de groq/google.genai deferidos ao primeiro uso

### NineRouter — Roteador Inteligente
- Analisa complexidade do prompt (simple/medium/complex)
- Roteia para o provider ideal baseado em: task type, latência, custo, qualidade
- Fallback automático se provider falhar

### RequestRouter — Classificação de Intenção
- Analisa o tipo de request: code, debug, explain, chat
- Ajusta max_tokens e temperature baseado na complexidade

---

## 🗣️ SISTEMA DE VOZ

### VoicePipeline — `core/voice_pipeline.py`
- **VAD (Voice Activity Detection)** — detecção de fala
- **Wake Word** — "Elívea", "Great Sage", "Grande Sábio", "Raphael", etc. (12 frases)
- **Push-to-Talk** — botão de pressionar para falar
- **Always-On Mode** — escuta contínua
- **Modos:** wake, always_on, push_to_talk

### SpeechEngine — `core/speech_engine.py`
- **TTS Neural** — 7 vozes PT/EN via edge-tts
- **Streaming** — fala enquanto a IA pensa (token por token)
- **Sentence Splitting** — divide texto em frases para playback incremental
- **Audio Cache** — cache de áudio TTS para respostas frequentes
- **Barge-out** — interrupção instantânea do áudio
- **Chimes** — sons de wake, success, boot

### Voice Cloner — `core/voice_cloner.py`
- Clonagem de voz personalizada

### Voice Converter — `core/voice_converter.py`
- Conversão de voz em tempo real

---

## 💾 SISTEMA DE MEMÓRIA

### PersistentMemory — `core/memory_persistent.py`
- **SQLite** — armazenamento persistente
- **Auto-backup** a cada 24h (SQLite backup API, atômico)
- **Auto-recovery** — detecta DB corrompido e recria
- **WAL journal mode** — resiliência contra crashes
- **30+ backups** mantidos (pruning automático)
- **Categories:** conversation, correction, fact, preference, pattern
- **Importance scoring** — prioriza memórias importantes

### MemoryManager — `memory/memory_manager.py`
- **Archive** de conversas
- **Emotional state** tracking
- **Conversation history** com timestamps

### SessionMemory
- Memória de sessão atual (não persiste entre reinícios)
- Contexto para prompts

### KnowledgeGraph — `core/intelligence/knowledge_graph.py`
- Extração de entidades e relacionamentos
- Graph-based context para queries

---

## 🧪 SISTEMAS DE INTELIGÊNCIA (6 subsistemas)

### 1. HallucinationGuard — `core/intelligence/hallucination_guard.py`
- Detecta alucinações em respostas
- Verifica consistência factual
- Score de confiança

### 2. QualityScorer — `core/intelligence/quality_score.py`
- Avalia qualidade das respostas
- Métricas: completude, relevância, clareza
- Histórico de scores para trending

### 3. ResponseCorrector — `core/intelligence/self_correction.py`
- Auto-correção de respostas incorretas
- Aprende com corrections do usuário

### 4. IntentPredictor — `core/intelligence/intent_predictor.py`
- Prediz intenção do usuário antes da resposta
- Padrões de uso para sugestões proativas

### 5. KnowledgeGraph — (já listado acima)
- Grafo de conhecimento dinâmico
- Extração automática de entidades

### 6. SpeedOptimizer — `core/speed_optimizer.py`
- Otimização de latência
- Connection pooling
- TTS cache preload
- Request batching

---

## 🤖 SISTEMAS AUTÔNOMOS

### AutonomousEngine — `core/autonomous_engine.py`
- Loop autônomo de auto-melhoria
- Detecta problemas críticos
- Dispara SelfImprover automaticamente

### AutonomousPlanner — `core/autonomous_planner.py`
- Planejamento autônomo de tarefas
- Decomposição de objetivos complexos

### SelfImproverModule — `modules/self_improver.py`
- Auto-reparo de código
- Otimização de performance
- Correção de bugs detectados

### ProactiveEngine — `core/proactive_engine.py`
- Sugestões proativas baseadas em contexto
- Padrões de uso do usuário

### IntelligenceEngine — `core/intelligence_engine.py`
- Enriquecimento dinâmico de contexto
- Combina todos os 6 subsistemas

---

## 🔧 MÓDULOS FUNCIONAIS (27 módulos)

### Automação & Controle
- **AutomationModule** — controle desktop (pyautogui)
- **HardwareController** — controle de hardware
- **PCController** — ações inteligentes (abrir apps, mídia, janelas)
- **SuperUser** — operações privilegiadas com confirmação

### Código & Desenvolvimento
- **CoderAgentModule** — agente de código autônomo
- **CodeAgent** — geração e análise de código
- **CodeIndex** — indexação de código para busca
- **CodeAnalyzer** — análise AST de code smells
- **CodeExecutor** — execução segura de código com aprovação

### Web & Pesquisa
- **WebModule** — pesquisa web (DuckDuckGo)
- **RAGEngine** — Retrieval-Augmented Generation
- **BrowserAgent** — automação de navegador
- **LinkAnalyzer** — análise de URLs

### Memória & Aprendizado
- **LearningEngine** — aprendizado contínuo
- **ErrorLearner** — aprende com erros anteriores
- **CodePatternLearner** — aprende padrões de código
- **VoiceCommandLearner** — aprende comandos de voz
- **PersonalityLearning** — aprende personalidade do usuário
- **SmartDefaults** — preferências automáticas
- **SmartAliases** — atalhos personalizados

### Comunicação
- **MessageMonitor** — auto-reply WhatsApp, Telegram, Discord, Email
- **ClipboardMonitor** — monitora clipboard para código/erros
- **ScreenContext** — captura contexto da tela

### Sistema
- **PluginManager** — sistema de plugins extensível
- **TaskScheduler** — agendamento de tarefas
- **ConfigManager** — gerenciamento de configurações
- **MultiLang** — suporte multilíngue
- **AppIntegration** — integração com outros apps

---

## 📊 MÓDULOS SMART (20 features)

| Módulo | Função |
|--------|--------|
| SessionMemory | Memória de sessão |
| LearningDashboard | Dashboard de aprendizado |
| ErrorLearner | Aprendizado com erros |
| CodePatternLearner | Padrões de código |
| VoiceCommandLearner | Comandos de voz |
| SmartReminders | Lembretes inteligentes |
| ConversationSummarizer | Resumo de conversas |
| MoodTracker | Tracking de humor |
| ResponseFeedback | Feedback de respostas |
| SmartDefaults | Preferências automáticas |
| CodeSnippetCache | Cache de snippets |
| ConversationBranching | Ramificação de conversas |
| ProactiveCodeReview | Code review proativo |
| SmartFileRecommendations | Recomendações de arquivos |
| AdaptiveResponseLength | Tamanho adaptativo de resposta |
| PersonalityLearning | Aprendizado de personalidade |
| KnowledgeGraph | Grafo de conhecimento |
| SmartAliases | Atalhos inteligentes |
| HealthMonitor | Monitor de saúde do sistema |
| ProactiveEngine | Sugestões proativas |

---

## 🛡️ SEGURANÇA

### SecurityGuard — `core/security.py`
- Níveis de segurança (LOW, MEDIUM, HIGH, CRITICAL)
- Verificação de código antes de executar
- Aprovação humana para operações perigosas

### AuditLog — `core/audit_log.py`
- Log de todas as operações
- Action levels (INFO, WARNING, ERROR, CRITICAL)

### SecretScanner — `scripts/pre_commit_hook.py`
- Bloqueia commits com API keys, tokens, senhas
- Padrões: AWS, Google, OpenAI, Anthropic, GitHub, etc.
- Pre-commit hook opcional

### CodeExecutor — `core/code_executor.py`
- Execução sandboxed de código
- Verificação de segurança antes de executar
- Aprovação para código perigoso

---

## 📈 MONITORAMENTO & ANALYTICS

### TokenTracker — `core/token_tracker.py`
- Log JSONL de cada request LLM
- Custo estimado por provider
- Relatório de uso diário/semanal
- Comparação com APIs pagas (economia)

### UsageTracker — `core/usage_tracker.py`
- Limites diários por provider
- Alertas de proximidade do limite
- Dashboard de uso em tempo real

### ProviderHealthMonitor — `core/provider_health_monitor.py`
- Health score (0-100) por provider
- Circuit breaker pattern
- Exponential backoff recovery
- Alerta quando todos os providers estão down

### WeeklyDigest — `core/weekly_digest.py`
- Resumo semanal de atividade
- Métricas de performance da IA
- Trends de uso

### Dashboard — `core/dashboard.py`
- Web dashboard para monitoramento

---

## 🎭 PERSONALIDADE & AMBIÊNCIA

### PersonaManager — `core/persona.py`
- System prompt dinâmico
- Detecção de humor do usuário
- Adaptação de tom (formal/informal)
- 5 níveis de raciocínio (simple → genius)

### AmbianceEngine — `core/ambiance.py`
- Saudações temporais (bom dia, boa tarde, etc.)
- Respostas proativas baseadas em humor
- Frases de conclusão de tarefa
- Análise de humor contínua

### ChainOfThought — `core/chain_of_thought.py`
- Raciocínio em cadeia para problemas complexos
- Decomposição em passos lógicos
- Conclusão com personalidade

---

## 🎨 VISUAL EFFECTS

### Professinal Widgets — `ui/professional_widgets.py` (4245 linhas)
- **RuneCoreWidget** — círculo mágico anime (10 camadas)
- **AbilityAwakeningOverlay** — animação de abertura cinemática
- **AwakeningSFX** — efeitos sonoros de awakening
- **TopBarWidget** — barra superior com navegação
- **InputBarWidget** — barra de entrada de comandos
- **CommandCenterDrawer** — drawer de centro de comando
- **SystemMonitorWidget** — monitor do sistema
- **AIStatusWidget** — status da IA
- **QuickActionsWidget** — ações rápidas
- **RecentCommandsWidget** — comandos recentes
- **CodeScratchpadWidget** — area de código
- **CodeWorkspaceWidget** — workspace de código
- **ConversationHistoryMap** — mapa de conversas
- **HistoryDrawer** — drawer de histórico
- **AmbientParticles** — partículas atmosféricas
- **StatusBar** — barra de status
- **MicroInteractions** — micro-interações (confetti, shake)
- **NotificationToast** — notificações
- **GlassPanel** — painéis com efeito glass
- **CodeBlockWidget** — blocos de código formatados
- **StatsTableWidget** — tabelas de estatísticas
- **WaveformWidget** — waveform de áudio
- **StatsTableWidget** — tabelas de stats
- **MagicCircle** — círculo mágico para installer
- **ProgressBar** — barra de progresso animada
- **StepIndicator** — indicador de passos
- **WizardPage** — páginas de wizard

---

## ⚙️ INFRAESTRUTURA

### Event Bus — `core/event_bus.py`
- Sistema de eventos pub/sub
- Desacoplamento entre componentes

### State Manager — `core/state_manager.py`
- Estado global da aplicação
- Thread-safe

### Logger — `core/logger.py`
- Logging configurável
- Arquivo + console

### Config Validator — `core/config_validator.py`
- Validação de configurações
- Schema validation

### Silent Run — `core/silent_run.py`
- Execução silenciosa de comandos OS
- Patch de os.system para evitar janelas PowerShell

### Rate Limiter — `core/rate_limiter.py`
- Rate limiting por provider
- Window-based throttling

### Request Router — `core/request_router.py`
- Classificação de intenção
- Roteamento baseado em complexidade

### RAG Embeddings — `core/rag_embeddings.py`
- Embeddings para RAG
- Cache de embeddings

---

## 📦 DEPENDÊNCIAS PRINCIPAIS

- **PySide6** — Qt6 bindings (UI)
- **edge-tts** — TTS neural gratuito
- **groq** — API Groq (LLM rápido)
- **google-genai** — API Gemini
- **requests** — HTTP client
- **psutil** — monitoramento de sistema
- **pyautogui** — automação desktop
- **speech_recognition** — reconhecimento de voz
- **pyttsx3** — TTS fallback
- **python-dotenv** — variáveis de ambiente
- **sqlite3** — banco de dados (built-in)
- **numpy** — computação numérica

---

## 🚀 PERFORMANCE

| Métrica | Valor |
|---------|-------|
| Import time | ~2.4s |
| EliveaApp init | ~0.5s |
| Window creation | ~2.7s |
| Total startup | ~5.5s |
| Streaming throttle | 12 updates/s |
| UI repaint | 30 FPS (timer) |
| Background init | ~2s (deferred) |
| Memory DB | SQLite WAL mode |
| Providers | 15+ gratuitos |
| Token limit | 8192 (configurável) |

---

## 🔑 COMANDOS SUPORTADOS

| Comando | Função |
|---------|--------|
| `status` | Status completo do sistema |
| `router` | Status do Multi-Provider Router |
| `router reset` | Reset do budget |
| `capacity` | Capacidade dos providers |
| `health` | Health monitor dos providers |
| `health recover` | Forçar recovery |
| `usage` | Uso de tokens (7 dias) |
| `savings` | Relatório de economia |
| `backup` | Criar backup da memória |
| `restore` | Restaurar do último backup |
| `backups` | Status dos backups |
| `config` | Configurações atuais |
| `update` | Verificar atualizações |
| `deep dev status` | Status do Deep Dev |
| `help` | Lista de comandos |

---

## 📁 ESTRUTURA DE DADOS

```
config/
├── settings.json          # Configurações gerais
├── security.json          # Configurações de segurança
├── memory.db              # Memória persistente (SQLite)
├── smart_data/            # Dados inteligentes
│   ├── knowledge_graph.json
│   ├── mood_history.json
│   ├── reminders.json
│   ├── response_feedback.json
│   ├── smart_aliases.json
│   ├── user_defaults.json
│   ├── voice_commands.json
│   ├── code_patterns.json
│   └── error_log.jsonl
├── backups/               # Backups da memória
├── audit/                 # Logs de auditoria
├── logs/                  # Logs gerais
├── rag_cache/             # Cache de RAG
├── rag_embeddings/        # Embeddings RAG
├── audio/                 # Áudios TTS
├── custom_voices/         # Vozes personalizadas
└── plugins/               # Plugins instalados
```

---

## 🎯 COMANDO DE VOZ

### Wake Words
- "Elívea", "Elvea"
- "Great Sage", "Grande Sábio"
- "Raphael", "Sábio", "Sage"
- "EI Sábio", "EI Sage"

### Modos
- **Wake** — acorda com frase de ativação
- **Always-On** — escuta contínua
- **Push-to-Talk** — botão para falar

---

## 🔄 FLUXO DE UMA CONVERSAA

```
1. Usuário digita/fala → handle_command()
2. Session memory registra turno
3. Smart aliases resolvem atalhos
4. Mood tracker analisa humor
5. Knowledge graph extrai entidades
6. Intent predictor classifica intenção
7. RequestRouter analisa complexidade
8. NineRouter seleciona provider ideal
9. Sistema de memória busca contexto relevante
10. IntelligenceEngine enriquece prompt
11. LLM gera resposta (streaming)
12. HallucinationGuard verifica
13. QualityScorer avalia
14. ResponseCorrector auto-corrige se necessário
15. Resposta enviada ao usuário via signal
16. SpeechEngine fala a resposta (streaming)
17. Knowledge graph atualiza
18. Proactive engine sugere próximas ações
19. Token tracker registra uso
20. Provider health monitor atualiza scores
```

---

## 🏆 DIFERENCIAIS

1. **15+ providers gratuitos** com failover automático
2. **Voz neural streaming** — fala enquanto pensa
3. **6 sistemas de inteligência** trabalhando em paralelo
4. **Memória persistente** com backup automático
5. **Auto-reparo** — detecta e corrige bugs sozinha
6. **IDE integrado** com syntax highlighting e auto-complete
7. **Deep Dev Panel** — Shadow Dev + Time Machine Debugger
8. **Interface anime** com círculo mágico reativo
9. **Multi-idioma** — suporte PT/EN
10. **Plugin system** — extensível
11. **Segurança** — sandbox, audit log, secret scanner
12. **Health monitoring** — circuit breaker, auto-recovery
13. **Token tracking** — economia vs APIs pagas
14. **Weekly digest** — resumo de atividade
15. **Proactive suggestions** — sugere ações antes de pedir
