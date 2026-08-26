# -*- coding: utf-8 -*-
"""State Management centralizado — store reativo para o app."""
import logging
from typing import Any, Dict, Callable
from copy import deepcopy

logger = logging.getLogger("greatsage.state")

class StateManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = {}
            cls._instance._listeners = {}
            cls._instance._history = []
        return cls._instance

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set(self, key: str, value: Any):
        old = self._state.get(key)
        if old == value:
            return
        self._state[key] = value
        self._history.append({"key": key, "old": old, "new": value})
        if len(self._history) > 500:
            self._history = self._history[-250:]
        for cb in self._listeners.get(key, []):
            try:
                cb(value, old)
            except Exception as e:
                logger.error(f"Error in state listener for '{key}': {e}")

    def subscribe(self, key: str, callback: Callable):
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)

    def update(self, data: Dict[str, Any]):
        for k, v in data.items():
            self.set(k, v)

    def to_dict(self) -> Dict[str, Any]:
        return deepcopy(self._state)

state = StateManager()
