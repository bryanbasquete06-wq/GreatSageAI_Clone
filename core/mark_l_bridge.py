"""
Great Sage AI - Mark L Integration Bridge & Unified Tool Registry
Provides seamless dynamic loading for ALL 20 Mark-L action modules and tools.
"""

import sys
import os
import importlib
from pathlib import Path

class MarkLBridge:
    def __init__(self, mark_l_path: str | None = None):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.mark_l_dir = self._resolve_path(mark_l_path)
        self.actions = {}
        self._initialize_bridge()

    def _resolve_path(self, path_str: str | None) -> Path | None:
        candidates = []
        if path_str:
            candidates.append(Path(path_str))
            candidates.append(self.base_dir / path_str)
        candidates.append(self.base_dir / "Mark-L-main")
        candidates.append(self.base_dir.parent / "Mark-L-main")

        for cand in candidates:
            if cand.exists() and (cand / "main.py").exists():
                return cand.resolve()
        return None

    def _initialize_bridge(self):
        if not self.mark_l_dir or not self.mark_l_dir.exists():
            return

        if str(self.mark_l_dir) not in sys.path:
            sys.path.insert(0, str(self.mark_l_dir))

        actions_dir = self.mark_l_dir / "actions"
        if not actions_dir.exists():
            return

        # Dynamically load all action modules from Mark-L-main/actions
        for file in actions_dir.glob("*.py"):
            if file.name.startswith("__"):
                continue
            mod_name = file.stem
            try:
                mod = importlib.import_module(f"actions.{mod_name}")
                # Register exported functions
                for attr_name in dir(mod):
                    if attr_name.startswith("_"):
                        continue
                    attr = getattr(mod, attr_name)
                    if callable(attr):
                        self.actions[attr_name] = attr
                        self.actions[f"{mod_name}.{attr_name}"] = attr
            except Exception as e:
                pass

        print(f"[MarkLBridge] Loaded {len(self.actions)} action handlers from {actions_dir}")

    def is_connected(self) -> bool:
        return self.mark_l_dir is not None and self.mark_l_dir.exists()

    def execute_action(self, action_name: str, parameters: dict = None) -> str:
        """Executes any loaded Mark-L action function by name."""
        if action_name not in self.actions:
            return f"[Bridge Error] Action '{action_name}' not registered."
        try:
            handler = self.actions[action_name]
            result = handler(parameters=parameters or {})
            return str(result) if result else f"[Bridge] Executed '{action_name}' successfully."
        except Exception as e:
            return f"[Bridge Error] Execution failed for '{action_name}': {e}"

    def get_status(self) -> dict:
        return {
            "mark_l_detected": self.is_connected(),
            "path": str(self.mark_l_dir) if self.mark_l_dir else "Not Found",
            "actions_loaded": len(self.actions),
            "registered_actions": sorted(list(set(self.actions.keys()))),
            "bridge_active": True
        }

