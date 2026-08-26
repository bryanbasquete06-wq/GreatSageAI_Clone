"""
Great Sage AI - PC Automation & Game Controller Module
Provides desktop automation, game launching & gameplay inputs, and media controls.
"""

import sys
import os
import time
import subprocess
import webbrowser
import pyautogui
import keyboard


class AutomationModule:
    # Disable pyautogui failsafe pause for fast gaming inputs
    pyautogui.FAILSAFE = False

    @staticmethod
    def open_game_or_app(target_name: str) -> str:
        """Launches games or system applications."""
        target_lower = target_name.lower().strip()
        
        # Common games & apps mapping
        known_apps = {
            "chrome": "chrome",
            "google": "chrome",
            "spotify": "spotify",
            "discord": "discord",
            "vscode": "code",
            "steam": "steam",
            "roblox": "roblox",
            "minecraft": "minecraft",
            "valorant": "valorant",
            "league": "leagueoflegends",
            "fortnite": "fortnite",
            "gta": "gta5"
        }
        
        app_cmd = known_apps.get(target_lower, target_lower)
        
        try:
            # Rate limit: max 1 app launch per 2 seconds
            import time
            if not hasattr(AutomationModule, '_last_launch'):
                AutomationModule._last_launch = 0
            if time.time() - AutomationModule._last_launch < 2:
                return f"[Action] Aguardando cooldown para abrir '{target_name}'."
            AutomationModule._last_launch = time.time()
            
            # Try Windows Start execution
            subprocess.Popen(f"start {app_cmd}", shell=True)
            return f"[Action] Launching '{target_name}' on system."
        except Exception as e:
            return f"[Action Error] Could not launch '{target_name}': {e}"

    @staticmethod
    def google_search_or_youtube(query: str, mode: str = "google") -> str:
        """Opens browser directly on Google Search or YouTube video."""
        if mode == "youtube":
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        else:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
        webbrowser.open(url)
        return f"[Action] Opening browser targeting {mode.upper()}: '{query}'"

    @staticmethod
    def execute_game_input(command: str) -> str:
        """Simulates key presses or mouse clicks for gaming or PC control."""
        cmd_lower = command.lower().strip()
        
        if "andar" in cmd_lower or "frente" in cmd_lower:
            pyautogui.keyDown('w')
            time.sleep(1.5)
            pyautogui.keyUp('w')
            return "[Game Input] Moved forward (W key)."
        elif "pular" in cmd_lower or "jump" in cmd_lower:
            pyautogui.press('space')
            return "[Game Input] Jumped (Spacebar)."
        elif "clicar" in cmd_lower or "click" in cmd_lower:
            pyautogui.click()
            return "[Game Input] Mouse left click executed."
        elif "tab" in cmd_lower:
            keyboard.send("alt+tab")
            return "[Action] Window switched (Alt+Tab)."
        elif "desktop" in cmd_lower or "trabalho" in cmd_lower:
            keyboard.send("win+d")
            return "[Action] Toggled Desktop (Win+D)."
        else:
            try:
                keyboard.send(command)
                return f"[Action] Key combination '{command}' executed."
            except Exception as e:
                return f"[Action Error] {e}"
