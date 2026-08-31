# -*- coding: utf-8 -*-
"""
Elívea — Plugin System
================================
Sistema de plugins para extensibilidade.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional


class PluginManager:
    """Gerenciador de plugins do Elívea."""

    _PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
    _CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "plugins.json"
    _plugins: dict = {}
    _hooks: dict[str, list[Callable]] = {}

    @classmethod
    def _ensure_dirs(cls):
        cls._PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        cls._CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not cls._CONFIG_FILE.exists():
            cls._CONFIG_FILE.write_text('{"enabled": []}', encoding="utf-8")

    @classmethod
    def discover(cls) -> list:
        """Descobre plugins disponiveis no diretorio plugins/."""
        cls._ensure_dirs()
        discovered = []
        for plugin_dir in cls._PLUGINS_DIR.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
                manifest = cls._load_manifest(plugin_dir)
                discovered.append({
                    "name": manifest.get("name", plugin_dir.name),
                    "version": manifest.get("version", "0.1.0"),
                    "description": manifest.get("description", ""),
                    "path": str(plugin_dir),
                    "enabled": cls._is_enabled(plugin_dir.name),
                })
        return discovered

    @classmethod
    def _load_manifest(cls, plugin_dir: Path) -> dict:
        manifest_file = plugin_dir / "manifest.json"
        if manifest_file.exists():
            try:
                return json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"name": plugin_dir.name}

    @classmethod
    def _is_enabled(cls, name: str) -> bool:
        try:
            config = json.loads(cls._CONFIG_FILE.read_text(encoding="utf-8"))
            return name in config.get("enabled", [])
        except Exception:
            return False

    @classmethod
    def enable(cls, name: str) -> bool:
        cls._ensure_dirs()
        try:
            config = json.loads(cls._CONFIG_FILE.read_text(encoding="utf-8"))
            if name not in config.get("enabled", []):
                config.setdefault("enabled", []).append(name)
                cls._CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    @classmethod
    def disable(cls, name: str) -> bool:
        cls._ensure_dirs()
        try:
            config = json.loads(cls._CONFIG_FILE.read_text(encoding="utf-8"))
            enabled = config.get("enabled", [])
            if name in enabled:
                enabled.remove(name)
                config["enabled"] = enabled
                cls._CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    @classmethod
    def load_plugin(cls, name: str) -> Any:
        """Carrega um plugin pelo nome."""
        if name in cls._plugins:
            return cls._plugins[name]
        plugin_dir = cls._PLUGINS_DIR / name
        if not plugin_dir.exists():
            return None
        try:
            module_path = plugin_dir / "__init__.py"
            spec = importlib.util.spec_from_file_location(f"gs_plugin_{name}", str(module_path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"gs_plugin_{name}"] = module
            spec.loader.exec_module(module)
            cls._plugins[name] = module
            if hasattr(module, "on_load"):
                module.on_load()
            return module
        except Exception as e:
            print(f"[Plugin] Erro ao carregar {name}: {e}")
            return None

    @classmethod
    def load_all_enabled(cls):
        """Carrega todos os plugins habilitados."""
        cls._ensure_dirs()
        config = json.loads(cls._CONFIG_FILE.read_text(encoding="utf-8"))
        for name in config.get("enabled", []):
            cls.load_plugin(name)

    @classmethod
    def register_hook(cls, hook_name: str, callback: Callable):
        """Registra um hook que plugins podem usar."""
        cls._hooks.setdefault(hook_name, []).append(callback)

    @classmethod
    def call_hook(cls, hook_name: str, *args, **kwargs) -> list:
        """Chama todos os callbacks de um hook."""
        results = []
        for cb in cls._hooks.get(hook_name, []):
            try:
                result = cb(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"[Plugin] Hook {hook_name} erro: {e}")
        return results

    @classmethod
    def create_plugin_template(cls, name: str, description: str = "") -> str:
        """Cria estrutura basica de um plugin."""
        plugin_dir = cls._PLUGINS_DIR / name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": name,
            "version": "0.1.0",
            "description": description,
            "author": "user",
        }
        (plugin_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        init_content = f'''# -*- coding: utf-8 -*-
"""
Plugin: {name}
{description}
"""

def on_load():
    """Chamado quando o plugin e carregado."""
    print(f"[Plugin {name}] Carregado com sucesso!")

def on_command(command: str) -> str | None:
    """Processa comandos do usuario. Retorna None para ignorar."""
    return None

def on_response(response: str) -> str:
    """Modifica respostas antes de serem enviadas."""
    return response
'''
        (plugin_dir / "__init__.py").write_text(init_content, encoding="utf-8")
        return str(plugin_dir)

    @classmethod
    def get_status(cls) -> str:
        plugins = cls.discover()
        if not plugins:
            return "Nenhum plugin encontrado."
        lines = [f"Plugins ({len(plugins)}):"]
        for p in plugins:
            status = "ativo" if p["enabled"] else "inativo"
            lines.append(f"  [{status}] {p['name']} v{p['version']} - {p['description']}")
        return "\n".join(lines)
