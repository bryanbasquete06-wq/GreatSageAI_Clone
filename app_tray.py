"""
Elivea - System Tray Launcher
Starts Elivea as a background Taskbar Widget / System Tray App.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.persona import PersonaManager
from core.llm import EliveaLLM
from core.mark_l_bridge import MarkLBridge
from modules.system import SystemModule
from modules.files import FileModule
from modules.web import WebModule
from ui.tray import EliveaTrayApp


class EliveaTrayLauncher:
    def __init__(self):
        self.persona = PersonaManager()
        self.llm = EliveaLLM()
        self.bridge = MarkLBridge()
        self.tray_ui = EliveaTrayApp(assistant_callback=self.process_command)

    def process_command(self, cmd: str) -> str:
        cmd_clean = cmd.strip()
        cmd_lower = cmd_clean.lower()

        if not cmd_clean:
            return ""

        if cmd_lower in ("sys", "status", "telemetria"):
            return SystemModule.get_status_report()

        if cmd_lower in ("help", "ajuda"):
            return (
                "[Notice] Directives:\n"
                "  - sys          : Hardware telemetry\n"
                "  - ls [path]    : List files\n"
                "  - find <term>  : File search\n"
                "  - search <q>   : Web search\n"
                "  - open <url>   : Browser launch\n"
                "  - mark-l       : Mark-L status"
            )

        if cmd_lower.startswith("ls"):
            parts = cmd_clean.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            return FileModule.list_directory(target)

        if cmd_lower.startswith("find "):
            parts = cmd_clean.split(maxsplit=1)
            if len(parts) > 1:
                return FileModule.search_files(parts[1])

        if cmd_lower.startswith("search "):
            parts = cmd_clean.split(maxsplit=1)
            if len(parts) > 1:
                return WebModule.search_web(parts[1])

        if cmd_lower.startswith("open "):
            parts = cmd_clean.split(maxsplit=1)
            if len(parts) > 1:
                return WebModule.open_url(parts[1])

        if cmd_lower.startswith("mark-l"):
            status = self.bridge.get_status()
            return self.persona.format_report("Mark-L Bridge", status)

        # Send to LLM
        return self.llm.query(cmd_clean)

    def start(self):
        print("[Notice] Starting Elívea Taskbar App...")
        self.tray_ui.run()


if __name__ == "__main__":
    app = EliveaTrayLauncher()
    app.start()
