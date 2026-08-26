# -*- coding: utf-8 -*-
"""
Great Sage AI — Screen Context
===============================
Captura a tela e analisa o conteudo usando o LLM.
"""
from __future__ import annotations

import base64
import io
import os
import time
import tempfile
from pathlib import Path
from typing import Optional


class ScreenContext:
    """Captura e analisa a tela do usuario."""

    _last_capture_path: Optional[str] = None
    _last_capture_time: float = 0

    @classmethod
    def capture(cls, region: str = "full") -> Optional[str]:
        """
        Captura a tela. Retorna caminho do arquivo salvo.
        region: "full", "active", ou uma string "x,y,w,h"
        """
        try:
            return cls._capture_win32(region)
        except Exception:
            try:
                return cls._capture_pil(region)
            except Exception:
                return None

    @classmethod
    def _capture_win32(cls, region: str) -> Optional[str]:
        """Captura usando win32 API (mais rapido)."""
        try:
            import win32gui
            import win32ui
            import win32con
            import win32api

            if region == "active":
                hwnd = win32gui.GetForegroundWindow()
                rect = win32gui.GetWindowRect(hwnd)
                x, y, x2, y2 = rect
                w, h = x2 - x, y2 - y
            elif region == "full":
                w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                x, y = 0, 0
            else:
                parts = [int(p) for p in region.split(",")]
                x, y, w, h = parts[0], parts[1], parts[2], parts[3]

            hwnd_desktop = win32gui.GetDesktopWindow()
            hwnd_dc = win32gui.GetWindowDC(hwnd_desktop)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)
            save_dc.BitBlt((0, 0), (w, h), mfc_dc, (x, y), win32con.SRCCOPY)

            bmp_info = bitmap.GetInfo()
            bmp_data = bitmap.GetBitmapBits(True)
            img = io.BytesIO()

            from PIL import Image
            pil_img = Image.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_data, "raw", "BGRX", 0, 1
            )

            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd_desktop, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            tmp = os.path.join(tempfile.gettempdir(), f"gs_screen_{int(time.time())}.png")
            pil_img.save(tmp, "PNG")
            cls._last_capture_path = tmp
            cls._last_capture_time = time.time()
            return tmp
        except ImportError:
            raise

    @classmethod
    def _capture_pil(cls, region: str) -> Optional[str]:
        """Fallback: captura usando PIL/Pillow."""
        from PIL import ImageGrab
        if region == "full":
            img = ImageGrab.grab()
        elif region == "active":
            img = ImageGrab.grab()
        else:
            parts = [int(p) for p in region.split(",")]
            img = ImageGrab.grab(bbox=(parts[0], parts[1], parts[0]+parts[2], parts[1]+parts[3]))

        tmp = os.path.join(tempfile.gettempdir(), f"gs_screen_{int(time.time())}.png")
        img.save(tmp, "PNG")
        cls._last_capture_path = tmp
        cls._last_capture_time = time.time()
        return tmp

    @classmethod
    def capture_to_base64(cls, region: str = "full") -> Optional[str]:
        """Captura e retorna como base64 (para envio ao LLM vision)."""
        path = cls.capture(region)
        if not path:
            return None
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return None

    @classmethod
    def get_active_window(cls) -> dict:
        """Retorna informacoes da janela ativa."""
        try:
            import win32gui
            import win32process
            import psutil

            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                name = proc.name()
                path = proc.exe()
            except Exception:
                name = "unknown"
                path = ""

            rect = win32gui.GetWindowRect(hwnd)
            return {
                "title": title,
                "process": name,
                "path": path,
                "pid": pid,
                "rect": {"x": rect[0], "y": rect[1], "w": rect[2]-rect[0], "h": rect[3]-rect[1]},
            }
        except Exception:
            return {"title": "unknown", "process": "unknown", "path": "", "pid": 0}

    @classmethod
    def analyze_screenshot(cls, llm_vision_fn=None) -> str:
        """Captura a tela e retorna analise textual."""
        path = cls.capture()
        if not path:
            return "Nao foi possivel capturar a tela."

        # Try image analyzer first
        try:
            from GreatSageAI_Clone.core.image_analyzer import analyzer as img_analyzer
            result = img_analyzer.analyze_image(
                path,
                prompt="Analise esta captura de tela. Descreva o que voce ve, identifique programas abertos, erros visiveis, e sugira acoes relevantes."
            )
            if result and result.description:
                return result.description
        except Exception:
            pass

        if llm_vision_fn:
            try:
                b64 = cls.capture_to_base64()
                if b64:
                    return llm_vision_fn(
                        "Analise esta captura de tela do usuario. "
                        "Descreva o que voce ve, identifique programas abertos, "
                        "erros visiveis, e sugira acoes relevantes.",
                        image_base64=b64,
                    )
            except Exception:
                pass

        active = cls.get_active_window()
        return (
            f"Tela capturada. Janela ativa: {active.get('title', 'desconhecida')} "
            f"({active.get('process', 'desconhecido')}). "
            f"Salva em: {path}"
        )

    @classmethod
    def get_recent_capture(cls) -> Optional[str]:
        """Retorna o caminho da ultima captura."""
        if cls._last_capture_path and os.path.exists(cls._last_capture_path):
            return cls._last_capture_path
        return None
