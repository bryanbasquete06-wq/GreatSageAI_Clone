"""
Great Sage AI - Futuristic Rich TUI Interface
Holographic Blue/Cyan aesthetic inspired by Great Sage & Jarvis UI.
"""

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

import time

class GreatSageTUI:
    def __init__(self):
        self.theme_color = "yellow"
        self.accent_color = "bright_yellow"
        self.border_color = "gold1"
        if HAS_RICH:
            self.console = Console()

    def print_banner(self):
        banner_art = """
   ▄████████  ▄████████  ▄████████  ███▄▄▄▄      ▄████████    ▄████████    ▄████████    ▄████████
  ███    ███ ███    ███ ███    ███  ███▀▀▀██▄   ███    ███   ███    ███   ███    ███   ███    ███
  ███    █▀  ███    ███ ███    █▀   ███    ███  ███    █▀    ███    █▀    ███    ███   ███    █▀
 ▄███▄▄▄     ███    ███ ███         ███    ███  ███          ███         ▄███▄▄▄▄██▀  ███
▀▀███▀▀▀   ▀███████████ ███    ███  ███    ███ ▀██████████ ▀███████████ ▀▀███▀▀▀▀▀   ███    ███
  ███    █▄  ███    ███ ███    ███  ███    ███          ███         ███ ▀███████████ ███    ███
  ███    ███ ███    ███ ███    ███  ███    ███    ▄█    ███   ▄█    ███   ███    ███   ███    ███
  ██████████ ███    █▀  ████████▀   ███    █▀   ▄████████▀  ▄████████▀    ███    ███   ██████████
                                                                          ███    ███
"""
        if HAS_RICH:
            panel = Panel(
                Text(banner_art, style="bold yellow"),
                title="[bold bright_yellow] GREAT SAGE [/bold bright_yellow]",
                subtitle="[dim yellow]Mode: Active | Persona: Great Sage | Core: Mark-L Compatible | by: bryan[/dim yellow]",
                border_style=self.border_color,
                expand=False
            )
            self.console.print(panel)
        else:
            print("=" * 60)
            print(" GREAT SAGE (by: bryan)")
            print("=" * 60)
            print(banner_art)

    def display_metrics(self, metrics: dict):
        if HAS_RICH:
            table = Table(title="[bold yellow]System Telemetry[/bold yellow]", border_style="gold1", show_header=True)
            table.add_column("Metric", style="bold white")
            table.add_column("Value", style="bold yellow")
            for k, v in metrics.items():
                table.add_row(k, str(v))
            self.console.print(table)
        else:
            print("\n--- [System Telemetry] ---")
            for k, v in metrics.items():
                print(f"  {k}: {v}")

    def render_notice(self, text: str, title: str = "GREAT SAGE NOTICE"):
        if HAS_RICH:
            panel = Panel(
                Text(text, style="bright_yellow"),
                title=f"[bold yellow] ◈ {title} ◈ [/bold yellow]",
                border_style=self.border_color,
                padding=(1, 2)
            )
            self.console.print(panel)
        else:
            print(f"\n=== [ {title} ] ===")
            print(text)
            print("=" * 40)

    def get_input(self) -> str:
        if HAS_RICH:
            return Prompt.ask("[bold yellow]GreatSage>[/bold yellow] [bold bright_yellow]Master[/bold bright_yellow]")
        else:
            return input("\nGreatSage> Master: ")

