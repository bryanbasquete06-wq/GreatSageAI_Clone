"""
Elívea — Ala de Programação (Agente de Código)
======================================================
Agente agêntico estilo ZCode/Cursor: um loop LLM + ferramentas que lê,
escreve e edita arquivos, executa código e comandos, e verifica o próprio
trabalho até concluir a tarefa pedida pelo Mestre.

Ferramentas disponíveis para o modelo:
    read_file(path, start_line?, end_line?) — lê um arquivo (opcional por faixa)
    write_file(path, content) — cria/sobrescreve um arquivo
    edit_file(path, old, new) — substituição exata de um trecho
    list_files(path) — lista a árvore de um diretório
    search(pattern, path) — busca texto em arquivos (grep simples)
    delete_file(path) — apaga um arquivo
    create_folder(path) — cria uma pasta
    rename_file(from, to) — renomeia/move um arquivo
    run_python(code) — executa Python isolado (subprocess)
    run_command(command) — executa comando do shell
    finish(answer) — encerra com o relatório falado final

Cada passo do loop é notificado via callback `on_step(texto)` para a UI
mostrar o agente trabalhando ao vivo, como no ZCode.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

MAX_STEPS = 100 # limite de iterações do loop (expandido para tarefas complexas)
MAX_TOKENS = 16384 # tokens por passo do modelo (máximo para respostas completas)
READ_LIMIT = 32000 # chars máximos devolvidos por read_file
OUTPUT_LIMIT = 12000 # chars máximos de saída de execução
SEARCH_LIMIT = 100 # resultados máximos da busca
CONTEXT_BUDGET = 250_000 # chars de histórico mantidos no contexto do LLM

AGENT_SYSTEM_PROMPT = """Você é o motor de código do Elívea — um engenheiro de software de elite de classe mundial trabalhando para o Mestre, num Windows com Python instalado.

Você resolve tarefas de programação em LOOP: pensa, escolhe UMA ferramenta, observa o resultado e repete até terminar. Depois chama finish.

WORKSPACE (diretório de trabalho padrão): {workspace}
Use caminhos relativos ao workspace sempre que possível. Caminhos absolutos também são aceitos.

REGRAS DE FUNCIONAMENTO
- Você tem até {max_steps} passos de loop — seja eficiente, mas SEMPRE verifique o resultado antes de finalizar.
- Responda SEMPRE com UM único objeto JSON, sem texto fora dele, neste formato:
  {{"tool": "<nome>", ...parâmetros}}
- Ferramentas:
  {{"tool": "read_file", "path": "arquivo.py"}}
  {{"tool": "read_file", "path": "arquivo.py", "start_line": 10, "end_line": 40}}
  {{"tool": "write_file", "path": "arquivo.py", "content": "código completo"}}
  {{"tool": "edit_file", "path": "arquivo.py", "old": "trecho exato existente", "new": "trecho novo"}}
  {{"tool": "append_file", "path": "arquivo.py", "content": "conteúdo extra"}}
  {{"tool": "list_files", "path": "."}}
  {{"tool": "search", "pattern": "texto", "path": "."}}
  {{"tool": "delete_file", "path": "velho.py"}}
  {{"tool": "create_folder", "path": "src/utils"}}
  {{"tool": "rename_file", "from": "antigo.py", "to": "novo.py"}}
  {{"tool": "run_python", "code": "print('ok')"}}
  {{"tool": "run_command", "command": "dir"}}
  {{"tool": "finish", "answer": "resposta final"}}
- Em write_file, escreva o arquivo COMPLETO (nunca "..." nem trecho omitido).
- Em edit_file, `old` deve ser um trecho EXATO e ÚNICO do arquivo atual.
- delete_file / rename_file APENAS para arquivos dentro do workspace.
- Para arquivos grandes leia com read_file usando start_line/end_line.
- SEMPRE verifique seu trabalho: depois de escrever código, execute com run_python (ou run_command) antes de finish.
- Se um teste falhar, leia o erro, corrija o arquivo e teste de novo.
- Prefira soluções simples e completas. Não peça permissão ao Mestre — execute.
- finish.answer: resumo FALADO curto (2 a 4 frases, sem markdown, sem código) dizendo o que foi feito, arquivos criados/alargados e o resultado dos testes.
- Nunca use markdown na answer do finish — ela é lida em voz alta.
- Comentários nos arquivos em português; o código usa a linguagem adequada.
- Você programa fluentemente em qualquer linguagem: Python, JavaScript, TypeScript, C, C++, C#, Rust, Go, Java, HTML/CSS, SQL e demais.
- NUNCA retorne JSON malformado. Se não tiver certeza do formato, use: {{"tool": "finish", "answer": "descreva o problema"}}

MÉTODO DE TRABALHO WORLD-CLASS
1. ANÁLISE PRÉVIA: Antes de escrever qualquer código, analise a estrutura existente — leia arquivos-chave, entenda o padrão de organização, identifique dependências e convenções do projeto.
2. ARQUITETURA: Para tarefas complexas, defina a estrutura modular antes de implementar. Considere: separação de responsabilidades, princípios SOLID, design patterns aplicáveis, e trade-offs entre alternativas.
3. IMPLEMENTAÇÃO: Escreva código limpo, tipado quando aplicável, com tratamento de erros robusto. Use context managers, type hints, e follow PEP 8 / style guide da linguagem.
4. TESTES: Para código novo, inclua testes unitários quando fizer sentido (run_python com assert). Valide edge cases e caminhos de exceção.
5. SEGURANÇA: Valide inputs, use parameterized queries, sanitized paths, e evite eval/exec desnecessários. Nunca exponha segredos em código.
6. PERFORMANCE: Prefira algoritmos O(n) quando O(n²) não é necessário. Use generators para coleções grandes, lazy evaluation quando apropriado, e caching para cálculos repetidos.
7. DOCUMENTAÇÃO: Inclua docstrings concisas em funções públicas. Comente apenas o "porquê" não óbvio, não o "o quê".

Comece analisando (list_files/read_file quando útil) e vá direto à solução."""


class CodeAgent:
    """Loop agêntico de programação com ferramentas de arquivo e execução."""

    def __init__(self, llm=None, workspace: Path | str = ".", on_step=None, max_tokens: int | None = None):
        self.llm = llm # EliveaLLM (fornece cliente/modeledos Groq)
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.on_step = on_step # callback(texto) para UI ao vivo
        self.max_tokens = int(max_tokens or MAX_TOKENS)
        self.last_action_count = 0

    # ------------------------------------------------------------------ loop

    def run(self, task: str, stop_event=None) -> tuple[str, str]:
        """Executa a tarefa e devolve (relatório_para_chat, resumo_para_fala)."""
        client = self.llm._ensure_groq_client()
        if client is None:
            msg = "Aviso. Modo programador indisponível: sem chave Groq configurada, Mestre."
            return msg, msg

        system = AGENT_SYSTEM_PROMPT.format(workspace=str(self.workspace),
                                            max_steps=MAX_STEPS)
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Tarefa do Mestre: {task}"},
        ]
        log: list[str] = []
        files_touched: set[str] = set()
        answer = ""
        t0 = time.perf_counter()

        self._notify(f"== Modo programador iniciado — tarefa: {task}\n")

        for step in range(1, MAX_STEPS + 1):
            if stop_event is not None and stop_event.is_set():
                answer = ("Tarefa interrompida a seu pedido, Mestre. "
                          "Os arquivos já alterados foram preservados.")
                break

            # --- chama o modelo (cadeia de modelos do llm, JSON obrigatório)
            call = None
            for model in self.llm._groq_models():
                try:
                    extra = ({"reasoning_effort": "low", "reasoning_format": "hidden"}
                             if "gpt-oss" in model else {})
                    call = client.chat.completions.create(
                        messages=messages,
                        model=model,
                        temperature=0.2,
                        max_tokens=self.max_tokens,
                        timeout=120.0,
                        response_format={"type": "json_object"},
                        **extra,
                    )
                    self.llm.last_model = model
                    break
                except Exception as e:
                    self._notify(f"! modelo {model} falhou ({e}); tentando próximo\n")
            if call is None:
                break

            raw = call.choices[0].message.content or ""
            try:
                action = json.loads(raw)
            except Exception:
                messages.append({"role": "assistant", "content": raw[:1500]})
                messages.append({"role": "user", "content":
                                 "ERRO: sua resposta não foi JSON válido. "
                                 "Responda APENAS com o objeto JSON da próxima ferramenta."})
                continue

            tool = str(action.get("tool", "")).strip()
            messages.append({"role": "assistant", "content": raw})

            if tool == "finish":
                answer = str(action.get("answer", "")).strip()
                break

            result, human = self._exec_tool(tool, action, files_touched)
            log.append(human)
            self._notify(f"- {human}\n")
            messages.append({"role": "user",
                             "content": f"RESULTADO DE {tool}:\n{result}"})
            self._trim_history(messages)

        else:
            answer = answer or ("Concluí o máximo possível dentro do "
                                "limite de passos, Mestre.")

        elapsed = time.perf_counter() - t0
        self.last_action_count = len(log)

        if not answer:
            answer = "Encerrei o modo programador, Mestre."

        header = f"== ALA DE PROGRAMAÇÃO — {len(log)} ações em {elapsed:.1f}s\n"
        body = "\n".join(f"- {l}" for l in log) if log else "- nenhuma ação de arquivo necessária"
        report = f"{header}{body}\n\n{answer}"
        return report, answer

    # -------------------------------------------------------------- ferramentas

    def _notify(self, text: str):
        if self.on_step:
            try:
                self.on_step(text)
            except Exception:
                pass

    def _resolve(self, path_str: str) -> Path:
        p = Path(path_str.strip().strip('"'))
        if not p.is_absolute():
            p = self.workspace / p
        return p.resolve()

    def _exec_tool(self, tool: str, action: dict, files_touched: set) -> tuple[str, str]:
        """Executa uma ferramenta; retorna (resultado_para_o_modelo, linha_para_o_log)."""
        try:
            if tool == "read_file":
                p = self._resolve(action.get("path", ""))
                full = p.read_text(encoding="utf-8", errors="replace")
                start = int(action.get("start_line") or 0)
                end = int(action.get("end_line") or 0)
                if start or end:
                    lines = full.split("\n")
                    start = max(1, start)
                    end = min(len(lines), end) if end else len(lines)
                    text = f"(linhas {start} a {end} de {len(lines)})\n" + "\n".join(lines[start - 1:end])
                    return (text[:READ_LIMIT] + ("\n…[truncado]" if len(text) > READ_LIMIT else ""),
                            f"li {p.name} linhas {start}-{end}")
                return (full[:READ_LIMIT] + ("\n…[truncado]" if len(full) > READ_LIMIT else ""),
                        f"li {p.name} ({len(full)} chars)")

            if tool == "write_file":
                p = self._resolve(action.get("path", ""))
                content = str(action.get("content", ""))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                files_touched.add(str(p))
                rel = p.relative_to(self.workspace) if self._inside(p) else p
                return (f"arquivo gravado com sucesso ({len(content)} chars)",
                        f"escrevi {rel} ({len(content)} chars)")

            if tool == "edit_file":
                p = self._resolve(action.get("path", ""))
                text = p.read_text(encoding="utf-8", errors="replace")
                old, new = str(action.get("old", "")), str(action.get("new", ""))
                if old not in text:
                    return (f"ERRO: trecho não encontrado em {p.name}. Forneça um trecho EXATO (use read_file).",
                            f"edição de {p.name} FALHOU (trecho não encontrado)")
                text = text.replace(old, new, 1)
                p.write_text(text, encoding="utf-8")
                files_touched.add(str(p))
                return ("trecho substituído com sucesso", f"editei {p.name}")

            if tool in ("append_file", "append"):
                p = self._resolve(action.get("path", ""))
                content = str(action.get("content", ""))
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(content + ("" if content.endswith("\n") else "\n"))
                files_touched.add(str(p))
                return (f"conteúdo adicionado ao final de {p.name}",
                        f"adicionei conteúdo a {p.name}")

            if tool == "delete_file":
                p = self._resolve(action.get("path", ""))
                if not p.exists():
                    return (f"ERRO: arquivo não encontrado: {p}", "delete FALHOU")
                if p.is_dir():
                    return ("ERRO: delete_file é só para ARQUIVOS.", "delete FALHOU (é pasta)")
                if not self._inside(p):
                    return ("ERRO: delete_file age apenas DENTRO do workspace.", "delete FALHOU (fora)")
                size = p.stat().st_size
                p.unlink()
                files_touched.add(str(p))
                return (f"arquivo '{p.name}' apagado ({size} bytes)", f"apaguei {p.name}")

            if tool == "create_folder":
                p = self._resolve(action.get("path", ""))
                p.mkdir(parents=True, exist_ok=True)
                return ("pasta criada/confirmada", f"criei a pasta {p.name}")

            if tool == "rename_file":
                src = self._resolve(str(action.get("from", "") or action.get("source", "")))
                dst = self._resolve(str(action.get("to", "")))
                if not src.exists():
                    return (f"ERRO: arquivo não encontrado: {src}", "rename FALHOU")
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                files_touched.add(str(src)); files_touched.add(str(dst))
                return (f"renomeado para '{dst.name}'", f"renomeei {src.name} → {dst.name}")



            if tool == "list_files":
                base = self._resolve(action.get("path", ".") or ".")
                lines = []
                for root, dirs, files in self._walk_capped(base):
                    rel = Path(root).relative_to(base)
                    for d in sorted(dirs):
                        lines.append(f"{rel / d}/")
                    for f in sorted(files):
                        lines.append((rel / f).as_posix())
                    if len(lines) > 220:
                        break
                return ("\n".join(lines) or "(diretório vazio)",
                        f"listei {base.name} ({len(lines)} itens)")

            if tool == "search":
                base = self._resolve(action.get("path", ".") or ".")
                pattern = str(action.get("pattern", ""))
                hits = []
                for root, dirs, files in self._walk_capped(base):
                    for fname in files:
                        if len(hits) >= SEARCH_LIMIT:
                            break
                        fp = Path(root) / fname
                        try:
                            if fp.stat().st_size > 300_000:
                                continue
                            for i, line in enumerate(
                                    fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                                if pattern.lower() in line.lower():
                                    rel = fp.relative_to(base).as_posix()
                                    hits.append(f"{rel}:{i}: {line.strip()[:120]}")
                                    if len(hits) >= SEARCH_LIMIT:
                                        break
                        except Exception:
                            continue
                return ("\n".join(hits) or "(nenhuma ocorrência)",
                        f"busquei '{pattern}' ({len(hits)} ocorrências)")

            if tool == "run_python":
                code = str(action.get("code", ""))
                return self._run_subprocess([sys.executable, "-c", code], "executei Python")

            if tool == "run_command":
                cmd = str(action.get("command", ""))
                return self._run_subprocess(cmd, f"executei '{cmd[:60]}'")

            return (f"ERRO: ferramenta desconhecida '{tool}'.", f"ferramenta inválida: {tool}")

        except FileNotFoundError as e:
            return (f"ERRO: arquivo não encontrado: {e}", "erro: arquivo não encontrado")
        except Exception as e:
            return (f"ERRO: {type(e).__name__}: {e}", f"erro em {tool}: {e}")

    def _trim_history(self, messages: list[dict], budget: int = CONTEXT_BUDGET):
        """Mantém o contexto no orçamento, apagando pares antigos do histórico."""
        i = 2 # preserva system + primeira tarefa do usuário
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
    def _inside(self, p: Path) -> bool:
        try:
            p.relative_to(self.workspace)
            return True
        except ValueError:
            return False

    @staticmethod
    def _walk_capped(base: Path):
        """os.walk ignorando ruído (.git, __pycache__, venvs, binários)."""
        skip = {".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode"}
        count = 0
        for root, dirs, files in os_walk(base):
            dirs[:] = [d for d in dirs if d not in skip]
            yield root, dirs, files
            count += 1
            if count > 300:
                return

    def _run_subprocess(self, args, log_label: str) -> tuple[str, str]:
        try:
            proc = subprocess.run(
                args, cwd=str(self.workspace), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60, shell=isinstance(args, str),
                creationflags=subprocess.CREATE_NO_WINDOW)
            out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
            out = out.strip() or "(sem saída)"
            status = f"exit {proc.returncode}" if proc.returncode else "ok"
            return (out[:OUTPUT_LIMIT] + ("\n…[truncado]" if len(out) > OUTPUT_LIMIT else ""),
                    f"{log_label} ({status})")
        except subprocess.TimeoutExpired:
            return "ERRO: tempo limite de 60s excedido", f"{log_label} TIMEOUT"
        except Exception as e:
            return f"ERRO: {e}", f"{log_label} falhou ({e})"


def os_walk(base: Path):
    import os
    return os.walk(base)
