import os
import sys
import win32com.client
from pathlib import Path

desktop = Path(os.path.expanduser('~/Desktop'))
start_menu = Path(os.path.expanduser('~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs'))

base_dir = Path(__file__).resolve().parent.parent
great_sage_script = base_dir / "great_sage_app.py"
console_script = base_dir / "great_sage_console.py"
icon_path = base_dir / "great_sage.ico"

python_exe = Path(sys.executable)
pyw_exe = python_exe.parent / "pythonw.exe"
if not pyw_exe.exists():
    pyw_exe = python_exe

shell = win32com.client.Dispatch('WScript.Shell')

# 1. Great Sage AI (Raphael - HUD Dourado Interface Oficial)
gui_shortcut = desktop / "Great Sage AI (Raphael).lnk"
shortcut = shell.CreateShortcut(str(gui_shortcut))
shortcut.TargetPath = str(pyw_exe)
shortcut.Arguments = f'"{great_sage_script}"'
shortcut.WorkingDirectory = str(base_dir.parent)
shortcut.Hotkey = "CTRL+ALT+G"
if icon_path.exists():
    shortcut.IconLocation = str(icon_path)
shortcut.Description = "Great Sage AI (Raphael) - Interface Oficial HUD Dourada"
shortcut.Save()

# Start Menu Copy
create_start = start_menu / "Great Sage AI (Raphael).lnk"
shortcut_sm = shell.CreateShortcut(str(create_start))
shortcut_sm.TargetPath = str(pyw_exe)
shortcut_sm.Arguments = f'"{great_sage_script}"'
shortcut_sm.WorkingDirectory = str(base_dir.parent)
if icon_path.exists():
    shortcut_sm.IconLocation = str(icon_path)
shortcut_sm.Save()

# 2. Great Sage Console Prompt BAT
console_bat = desktop / "Great Sage Console (Prompt).bat"
with open(console_bat, "w", encoding="utf-8") as f:
    f.write(f'@echo off\n')
    f.write(f'title Great Sage AI - Console Terminal [by: bryan]\n')
    f.write(f'color 0A\n')
    f.write(f'"{python_exe}" "{console_script}"\n')
    f.write(f'pause\n')

print("[OK] Interface Oficial Great Sage AI HUD Dourada restaurada na Area de Trabalho com sucesso!")


