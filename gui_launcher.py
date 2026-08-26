"""
Great Sage AI - Standalone Desktop GUI Application
Pops up immediately on screen when double-clicked on Desktop.

┌─────────────────────────────────────────────────────────────────┐
│ DEPRECATED — Esta interface tkinter foi substituída pela │
│ nova interface Qt (ui/qt_ui.py) e será REMOVIDA na v2.0. │
│ Use `python main.py` para iniciar a interface atual. │
│ Mantido apenas como fallback de emergência. │
└─────────────────────────────────────────────────────────────────┘
"""

import warnings

warnings.warn(
    "gui_launcher.py está depreciado e será removido na v2.0. "
    "Use a interface Qt via main.py.",
    DeprecationWarning,
    stacklevel=2,
)

import sys
import os
import threading
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext

# Ensure project root in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from GreatSageAI_Clone.core.persona import PersonaManager
from GreatSageAI_Clone.core.llm import GreatSageLLM
from GreatSageAI_Clone.core.mark_l_bridge import MarkLBridge
from GreatSageAI_Clone.modules.system import SystemModule
from GreatSageAI_Clone.modules.files import FileModule
from GreatSageAI_Clone.modules.web import WebModule


class GreatSageGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Great Sage - (by: bryan)")
        self.root.geometry("620x520")
        self.root.configure(bg="#0c0a02")

        # Persona & Engines
        self.persona = PersonaManager()
        self.llm = GreatSageLLM()
        self.bridge = MarkLBridge()

        self._build_ui()

    def _build_ui(self):
        # Header Frame
        header = tk.Frame(self.root, bg="#211b05", height=45)
        header.pack(fill=tk.X, side=tk.TOP)

        lbl_title = tk.Label(
            header,
            text="GREAT SAGE AI",
            fg="#ffd700",
            bg="#211b05",
            font=("Consolas", 12, "bold")
        )
        lbl_title.pack(side=tk.LEFT, padx=10, pady=8)

        lbl_by = tk.Label(
            header,
            text="[by: bryan]",
            fg="#ffea00",
            bg="#211b05",
            font=("Consolas", 10, "italic")
        )
        lbl_by.pack(side=tk.LEFT, padx=2)

        lbl_status = tk.Label(
            header,
            text="ONLINE",
            fg="#55ff00",
            bg="#211b05",
            font=("Consolas", 9, "bold")
        )
        lbl_status.pack(side=tk.RIGHT, padx=12)

        # Main Output Area
        output_frame = tk.Frame(self.root, bg="#0c0a02", highlightbackground="#ffd700", highlightthickness=1)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.txt_out = scrolledtext.ScrolledText(
            output_frame,
            bg="#141103",
            fg="#fff4b3",
            font=("Consolas", 10),
            wrap=tk.WORD,
            bd=0
        )
        self.txt_out.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Initial greeting
        init_msg = (
            "=== [ GREAT SAGE INITIALIZED ] ===\n"
            "by: bryan | Core: Mark-L Compatible\n\n"
            "[Notice] Great Sage system online and operating within optimal parameters.\n"
            "Type your command below or use quick directives:\n"
            " - sys : Display hardware telemetry\n"
            " - help : List available protocols\n"
            " - search <q> : Web search\n"
            " - mark-l : Check Mark-L connection status\n"
            "=========================================\n\n"
        )
        self.txt_out.insert(tk.END, init_msg)

        # Quick Action Buttons Frame
        btn_frame = tk.Frame(self.root, bg="#0c0a02")
        btn_frame.pack(fill=tk.X, padx=10, pady=2)

        btn_sys = tk.Button(btn_frame, text="Telemetria", bg="#262005", fg="#ffd700", font=("Consolas", 9, "bold"), bd=1, command=lambda: self.run_cmd("sys"))
        btn_sys.pack(side=tk.LEFT, padx=4)

        btn_help = tk.Button(btn_frame, text="Ajuda", bg="#262005", fg="#ffd700", font=("Consolas", 9, "bold"), bd=1, command=lambda: self.run_cmd("help"))
        btn_help.pack(side=tk.LEFT, padx=4)

        btn_markl = tk.Button(btn_frame, text="Mark-L", bg="#262005", fg="#ffd700", font=("Consolas", 9, "bold"), bd=1, command=lambda: self.run_cmd("mark-l"))
        btn_markl.pack(side=tk.LEFT, padx=4)

        # Input Frame
        input_frame = tk.Frame(self.root, bg="#211b05", highlightbackground="#ffd700", highlightthickness=1)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)

        lbl_prompt = tk.Label(input_frame, text="Master> ", fg="#ffd700", bg="#211b05", font=("Consolas", 11, "bold"))
        lbl_prompt.pack(side=tk.LEFT, padx=2)

        self.entry_cmd = tk.Entry(
            input_frame,
            bg="#141103",
            fg="#ffffff",
            insertbackground="#ffd700",
            font=("Consolas", 11),
            bd=0
        )
        self.entry_cmd.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6)
        self.entry_cmd.bind("<Return>", self._on_enter)
        self.entry_cmd.focus_set()

        btn_send = tk.Button(input_frame, text="Enviar", bg="#ffd700", fg="#000000", font=("Consolas", 10, "bold"), bd=0, command=self._on_enter)
        btn_send.pack(side=tk.RIGHT, padx=4, pady=4)

    def _on_enter(self, event=None):
        cmd = self.entry_cmd.get().strip()
        if cmd:
            self.entry_cmd.delete(0, tk.END)
            self.run_cmd(cmd)

    def append_text(self, text: str):
        self.txt_out.insert(tk.END, text + "\n\n")
        self.txt_out.see(tk.END)

    def run_cmd(self, cmd: str):
        self.append_text(f"Master> {cmd}")
        threading.Thread(target=self._process_cmd, args=(cmd,), daemon=True).start()

    def _process_cmd(self, cmd: str):
        cmd_clean = cmd.strip()
        cmd_lower = cmd_clean.lower()

        if cmd_lower in ("sys", "status", "telemetria"):
            res = SystemModule.get_status_report()
        elif cmd_lower in ("help", "ajuda"):
            res = (
                "[Notice] Protocols available:\n"
                " - sys : Hardware metrics\n"
                " - ls [path] : Directory listing\n"
                " - find <term> : File search\n"
                " - search <q> : Web search\n"
                " - mark-l : Mark-L bridge state"
            )
        elif cmd_lower.startswith("ls"):
            parts = cmd_clean.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            res = FileModule.list_directory(target)
        elif cmd_lower.startswith("find "):
            parts = cmd_clean.split(maxsplit=1)
            res = FileModule.search_files(parts[1]) if len(parts) > 1 else "Specify term."
        elif cmd_lower.startswith("search "):
            parts = cmd_clean.split(maxsplit=1)
            res = WebModule.search_web(parts[1]) if len(parts) > 1 else "Specify query."
        elif cmd_lower.startswith("mark-l"):
            status = self.bridge.get_status()
            res = self.persona.format_report("Mark-L Bridge", status)
        else:
            res = self.llm.query(cmd_clean)

        self.root.after(0, self.append_text, f"Great Sage> {res}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = GreatSageGUI()
    app.run()
