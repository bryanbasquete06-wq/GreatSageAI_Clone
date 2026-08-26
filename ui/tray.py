"""
Great Sage AI - System Tray & Taskbar HUD Application
Provides a futuristic Taskbar Overlay, Floating Command Bar, and Tray Interface.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import sys
import os
from pathlib import Path

# Try pystray / PIL for native tray icon
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


class GreatSageTrayApp:
    def __init__(self, assistant_callback=None):
        self.assistant_callback = assistant_callback
        self.root = tk.Tk()
        self.root.title("Great Sage (by: bryan)")
        self.root.configure(bg="#0f0c02")

        # Configure window properties for Taskbar HUD
        self.root.overrideredirect(True) # Borderless futuristic HUD window
        self.root.attributes("-topmost", True) # Keep on top
        self.root.attributes("-alpha", 0.96) # Slight transparency

        self.is_expanded = False
        self._setup_window_position()
        self._build_ui()
        self._setup_tray_icon()

    def _setup_window_position(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Position at bottom-right near Windows Taskbar
        self.width = 420
        self.height_collapsed = 60
        self.height_expanded = 380

        x_pos = screen_w - self.width - 25
        y_pos = screen_h - self.height_collapsed - 65

        self.root.geometry(f"{self.width}x{self.height_collapsed}+{x_pos}+{y_pos}")

    def _build_ui(self):
        # Outer Frame with Golden Neon Border
        self.main_frame = tk.Frame(self.root, bg="#0f0c02", highlightbackground="#ffd700", highlightthickness=2)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header / Status Bar
        self.header_frame = tk.Frame(self.main_frame, bg="#261f05", height=32)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)

        # Title & Indicator
        self.lbl_title = tk.Label(
            self.header_frame,
            text=" ◈ GREAT SAGE ",
            fg="#ffd700",
            bg="#261f05",
            font=("Consolas", 10, "bold")
        )
        self.lbl_title.pack(side=tk.LEFT, padx=5, pady=4)

        self.lbl_by = tk.Label(
            self.header_frame,
            text="[by: bryan]",
            fg="#ffea00",
            bg="#261f05",
            font=("Consolas", 8, "italic")
        )
        self.lbl_by.pack(side=tk.LEFT, padx=2)

        self.lbl_status = tk.Label(
            self.header_frame,
            text="● ONLINE",
            fg="#55ff00",
            bg="#261f05",
            font=("Consolas", 8, "bold")
        )
        self.lbl_status.pack(side=tk.LEFT, padx=5)

        # Window Action Buttons (- / ⚙ / X)
        btn_close = tk.Label(self.header_frame, text=" ✕ ", fg="#ff4466", bg="#261f05", font=("Consolas", 10, "bold"), cursor="hand2")
        btn_close.pack(side=tk.RIGHT, padx=5)
        btn_close.bind("<Button-1>", lambda e: self.root.withdraw())

        btn_toggle = tk.Label(self.header_frame, text=" ↕ ", fg="#ffd700", bg="#261f05", font=("Consolas", 10, "bold"), cursor="hand2")
        btn_toggle.pack(side=tk.RIGHT, padx=2)
        btn_toggle.bind("<Button-1>", lambda e: self.toggle_expand())

        # Quick Input Bar
        self.input_frame = tk.Frame(self.main_frame, bg="#0f0c02")
        self.input_frame.pack(fill=tk.X, side=tk.TOP, padx=6, pady=4)

        self.prompt_label = tk.Label(self.input_frame, text=">", fg="#ffd700", bg="#0f0c02", font=("Consolas", 11, "bold"))
        self.prompt_label.pack(side=tk.LEFT, padx=2)

        self.entry_cmd = tk.Entry(
            self.input_frame,
            bg="#211a05",
            fg="#ffffff",
            insertbackground="#ffd700",
            font=("Consolas", 10),
            bd=1,
            relief=tk.FLAT
        )
        self.entry_cmd.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_cmd.bind("<Return>", self._on_submit)
        self.entry_cmd.focus_set()

        # Output Text Panel (Hidden in collapsed mode)
        self.output_frame = tk.Frame(self.main_frame, bg="#0f0c02")
        self.txt_output = scrolledtext.ScrolledText(
            self.output_frame,
            bg="#171303",
            fg="#fff2b3",
            font=("Consolas", 9),
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0
        )
        self.txt_output.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.txt_output.insert(tk.END, "[Notice] Great Sage Active (by: bryan).\nType 'sys' or query Master...\n")
        self.txt_output.config(state=tk.DISABLED)

    def toggle_expand(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        if self.is_expanded:
            y_pos = screen_h - self.height_collapsed - 65
            self.root.geometry(f"{self.width}x{self.height_collapsed}+{screen_w - self.width - 25}+{y_pos}")
            self.output_frame.pack_forget()
            self.is_expanded = False
        else:
            y_pos = screen_h - self.height_expanded - 65
            self.root.geometry(f"{self.width}x{self.height_expanded}+{screen_w - self.width - 25}+{y_pos}")
            self.output_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
            self.is_expanded = True

    def append_output(self, text: str):
        if not self.is_expanded:
            self.toggle_expand()
        self.txt_output.config(state=tk.NORMAL)
        self.txt_output.insert(tk.END, f"\n{text}\n")
        self.txt_output.see(tk.END)
        self.txt_output.config(state=tk.DISABLED)

    def _on_submit(self, event=None):
        cmd = self.entry_cmd.get().strip()
        if not cmd:
            return
        self.entry_cmd.delete(0, tk.END)
        self.append_output(f"Master> {cmd}")

        if self.assistant_callback:
            threading.Thread(target=self._process_async, args=(cmd,), daemon=True).start()

    def _process_async(self, cmd: str):
        response = self.assistant_callback(cmd)
        if response:
            self.root.after(0, self.append_output, response)

    def _create_tray_image(self):
        # Generates a golden glowing icon for system tray
        image = Image.new("RGBA", (64, 64), (12, 10, 2, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), outline=(255, 215, 0, 255), width=4)
        draw.polygon([(32, 16), (48, 44), (16, 44)], fill=(255, 235, 100, 255))
        return image

    def _setup_tray_icon(self):
        if not HAS_PYSTRAY:
            return

        def on_restore(icon, item):
            self.root.after(0, self.root.deiconify)

        def on_toggle_expand(icon, item):
            self.root.after(0, self.toggle_expand)

        def on_quit(icon, item):
            icon.stop()
            self.root.after(0, self.root.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("Abrir Great Sage HUD", on_restore, default=True),
            pystray.MenuItem("Expandir/Recolher Painel", on_toggle_expand),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", on_quit)
        )

        icon_img = self._create_tray_image()
        self.tray_icon = pystray.Icon("GreatSageAI", icon_img, "Great Sage AI", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def run(self):
        self.root.mainloop()
