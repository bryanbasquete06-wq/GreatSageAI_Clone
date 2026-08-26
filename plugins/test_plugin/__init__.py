# -*- coding: utf-8 -*-
"""
Plugin: test_plugin
Teste
"""

def on_load():
    """Chamado quando o plugin e carregado."""
    print(f"[Plugin test_plugin] Carregado com sucesso!")

def on_command(command: str) -> str | None:
    """Processa comandos do usuario. Retorna None para ignorar."""
    return None

def on_response(response: str) -> str:
    """Modifica respostas antes de serem enviadas."""
    return response
