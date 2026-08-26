# -*- coding: utf-8 -*-
"""Sistema de eventos pub/sub para comunicacao entre modulos."""
from collections import defaultdict
from typing import Callable, Any
import logging

logger = logging.getLogger("greatsage.events")

class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners = defaultdict(list)
            cls._instance._history = []
        return cls._instance

    def subscribe(self, event: str, callback: Callable):
        self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        if callback in self._listeners[event]:
            self._listeners[event].remove(callback)

    def emit(self, event: str, data: Any = None):
        self._history.append({"event": event, "data": data})
        if len(self._history) > 1000:
            self._history = self._history[-500:]
        for cb in self._listeners.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"Error in handler for '{event}': {e}")

    def get_history(self, event: str = None, limit: int = 50):
        if event:
            return [h for h in self._history if h["event"] == event][-limit:]
        return self._history[-limit:]

event_bus = EventBus()
