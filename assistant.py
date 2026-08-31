"""
Elivea - Assistant Core Application
Main entry point coordinating Persona, System Modules, UI, and Mark-L Bridge.
"""

import sys
import os
from pathlib import Path

# Ensure root directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.persona import PersonaManager
from core.llm import EliveaLLM
from core.mark_l_bridge import MarkLBridge
from modules.system import SystemModule
from modules.files import FileModule
from modules.web import WebModule
from modules.hardware_controller import HardwareController
from ui.tui import EliveaTUI


class EliveaAssistant:
    def __init__(self):
        self.tui = EliveaTUI()
        self.persona = PersonaManager()
        self.llm = EliveaLLM()
        self.bridge = MarkLBridge()
        self.running = True

    def initialize(self):
        """Boot sequence for Elivea System."""
        self.tui.print_banner()

        status_msg = (
            "[Notice] Elívea Core Initialized.\n"
            f"  - Neural Core: Active ({self.llm.provider.upper()})\n"
            f"  - Mark-L Integration: {'ONLINE' if self.bridge.is_connected() else 'STANDBY'}\n"
            "  - Interface: Futuristic TUI Mode Active\n\n"
            "Type 'help' for available directives, 'sys' for metrics, or enter any query."
        )
        self.tui.render_notice(status_msg, title="SYSTEM BOOT COMPLETED")

    def handle_command(self, user_input: str):
        cmd = user_input.strip()
        cmd_lower = cmd.lower()

        if not cmd:
            return

        if cmd_lower in ("exit", "quit", "sair", "desligar"):
            self.tui.render_notice("[Notice] Terminating Elívea session. Farewell, Master.", title="SHUTDOWN")
            self.running = False
            return

        if cmd_lower in ("sys", "status", "telemetry"):
            metrics = SystemModule.get_metrics()
            self.tui.display_metrics(metrics)
            return

        if "meu ip" in cmd_lower or "ip da rede" in cmd_lower or cmd_lower in ("ip", "rede"):
            res = HardwareController.get_ip_info()
            self.tui.render_notice(res, title="REDE TELEMETRIA")
            return

        if "limpar lixeira" in cmd_lower or "esvaziar lixeira" in cmd_lower:
            res = HardwareController.clean_recycle_bin()
            self.tui.render_notice(res, title="LIXEIRA WINDOWS")
            return

        if "meus discos" in cmd_lower or "disco" in cmd_lower or "armazenamento" in cmd_lower:
            res = HardwareController.get_disk_info()
            self.tui.render_notice(res, title="DISCOS RIGIDOS")
            return

        if "limpar historico" in cmd_lower or "limpar conversa" in cmd_lower:
            res = self.llm.clear_history()
            self.tui.render_notice(res, title="HISTORICO")
            return

        if cmd_lower.startswith("set-key groq ") or cmd_lower.startswith("groq-key "):
            key_part = cmd.split(maxsplit=2)[-1]
            res = self.llm.save_groq_key(key_part)
            self.tui.render_notice(res, title="API KEY GROQ")
            return

        if cmd_lower in ("help", "ajuda"):
            help_text = (
                "[Notice] Elivea Directive Protocols:\n"
                "  - sys / status   : Display real-time hardware telemetry\n"
                "  - ls [path]      : List contents of directory\n"
                "  - find <term>    : Search file system for target pattern\n"
                "  - search <query> : Execute web search\n"
                "  - open <url>     : Open URL in default web browser\n"
                "  - mark-l status  : Check Mark-L core bridge status\n"
                "  - exit / quit    : Terminate Elivea process"
            )
            self.tui.render_notice(help_text, title="DIRECTIVE ASSIST")
            return

        if cmd_lower.startswith("ls") or cmd_lower.startswith("dir "):
            parts = cmd.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            res = FileModule.list_directory(target)
            self.tui.render_notice(res, title="FILE SYSTEM")
            return

        if cmd_lower.startswith("find "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                res = FileModule.search_files(parts[1])
                self.tui.render_notice(res, title="FILE SEARCH")
            return

        if cmd_lower.startswith("search "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                res = WebModule.search_web(parts[1])
                self.tui.render_notice(res, title="WEB MODULE")
            return

        if cmd_lower.startswith("open "):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1:
                res = WebModule.open_url(parts[1])
                self.tui.render_notice(res, title="WEB NAVIGATION")
            return

        if cmd_lower.startswith("mark-l"):
            bridge_status = self.bridge.get_status()
            report = self.persona.format_report("Mark-L Bridge", bridge_status)
            self.tui.render_notice(report, title="MARK-L INTEGRATION")
            return

        # Default query to LLM / Analytical Engine
        response = self.llm.query(cmd)
        self.tui.render_notice(response, title="ELIVEA RESPONSE")

    def run(self):
        self.initialize()
        while self.running:
            try:
                user_input = self.tui.get_input()
                self.handle_command(user_input)
            except KeyboardInterrupt:
                self.tui.render_notice("\n[Notice] Session interrupted. Shutting down.", title="INTERRUPT")
                break
            except Exception as e:
                self.tui.render_notice(f"[Notice] An exception occurred: {e}", title="ERROR REPORT")


if __name__ == "__main__":
    assistant = EliveaAssistant()
    assistant.run()
