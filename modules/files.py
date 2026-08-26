"""
Great Sage AI - File Management Module
Handles file operations, searching, reading, writing, and disk organization.
"""

import os
from pathlib import Path

class FileModule:
    @staticmethod
    def list_directory(target_path: str = ".") -> str:
        try:
            p = Path(target_path).resolve()
            if not p.exists():
                return f"[Notice] Error: Path '{target_path}' does not exist."

            items = list(p.iterdir())
            dirs = [f"[DIR]  {item.name}" for item in items if item.is_dir()]
            files = [f"[FILE] {item.name} ({item.stat().st_size} bytes)" for item in items if item.is_file()]

            output = [f"[Report] Contents of {p}:"]
            output.extend(dirs)
            output.extend(files)
            return "\n".join(output)
        except Exception as e:
            return f"[Notice] File access exception: {e}"

    @staticmethod
    def read_file(file_path: str, max_chars: int = 5000) -> str:
        """Reads content from a text file."""
        try:
            p = Path(file_path).resolve()
            if not p.exists() or not p.is_file():
                return f"[Erro] O arquivo '{file_path}' não foi encontrado ou é um diretório."
            content = p.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                return f"[Conteúdo do Arquivo '{p.name}'] (Truncado em {max_chars} caracteres):\n\n" + content[:max_chars] + "\n..."
            return f"[Conteúdo do Arquivo '{p.name}']:\n\n{content}"
        except Exception as e:
            return f"[Erro] Não foi possível ler o arquivo: {e}"

    @staticmethod
    def write_file(file_path: str, content: str) -> str:
        """Writes text content to a file."""
        try:
            p = Path(file_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"[Ação] Arquivo '{p.name}' salvo com sucesso ({len(content)} caracteres)."
        except Exception as e:
            return f"[Erro] Falha ao escrever arquivo: {e}"

    @staticmethod
    def create_folder(folder_path: str) -> str:
        """Creates a directory on disk."""
        try:
            p = Path(folder_path).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return f"[Ação] Pasta '{p}' criada com sucesso."
        except Exception as e:
            return f"[Erro] Falha ao criar pasta: {e}"

    @staticmethod
    def search_files(name_query: str, root_dir: str = ".") -> str:
        results = []
        root = Path(root_dir)
        try:
            for item in root.rglob(f"*{name_query}*"):
                if len(results) >= 20:
                    break
                results.append(str(item))

            if not results:
                return f"[Notice] No files found matching query '{name_query}'."
            return f"[Report] Found {len(results)} matches for '{name_query}':\n" + "\n".join(f"  - {r}" for r in results)
        except Exception as e:
            return f"[Notice] File search exception: {e}"

