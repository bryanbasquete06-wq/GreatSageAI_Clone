# -*- coding: utf-8 -*-
"""Analise de imagens com vision LLM (Gemini, OpenRouter)."""
import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger("elvea.vision")

@dataclass
class ImageAnalysis:
    description: str = ""
    objects: list = None
    text_detected: str = ""
    colors: list = None
    confidence: float = 0.0
    model_used: str = ""
    raw_response: str = ""

class ImageAnalyzer:
    """Analise de imagens usando LLMs com suporte a vision."""

    def __init__(self):
        self._gemini_client = None
        self._groq_client = None

    def _get_gemini(self):
        if self._gemini_client:
            return self._gemini_client
        try:
            import google.genai as genai
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                from EliveaAI_Clone.core.secret_manager import secrets
                api_key = secrets.get("GEMINI_API_KEY") or ""
            if not api_key:
                return None
            self._gemini_client = genai.Client(api_key=api_key)
            return self._gemini_client
        except Exception as e:
            logger.debug(f"Gemini nao disponivel: {e}")
            return None

    def _get_groq(self):
        if self._groq_client:
            return self._groq_client
        try:
            import groq
            api_key = os.environ.get("GROQ_API_KEY", "")
            if not api_key:
                from EliveaAI_Clone.core.secret_manager import secrets
                api_key = secrets.get("GROQ_API_KEY") or ""
            if not api_key:
                return None
            self._groq_client = groq.Groq(api_key=api_key)
            return self._groq_client
        except Exception as e:
            logger.debug(f"Groq nao disponivel: {e}")
            return None

    def _encode_image(self, image_path: str) -> str:
        """Codifica imagem em base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_mime_type(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        return mime_map.get(ext, "image/png")

    def analyze_image(self, image_path: str, prompt: str | None = None,
                     provider: str = "auto") -> ImageAnalysis:
        """Analisa uma imagem com proteo total contra erros.
        
        Esta metodo nunca levanta exceao. Qualquer erro resulta em uma
        imagem Analysis com confidence=0 e mensagem descriptiva.
        """
        # ---- Camada 1: validacao de entrada ----
        try:
            if not image_path:
                return ImageAnalysis(
                    description="Caminho de imagem nao informado",
                    confidence=0.0
                )
            if not os.path.exists(image_path):
                return ImageAnalysis(
                    description=f"Arquivo de imagem nao encontrado: {image_path}",
                    confidence=0.0
                )
        except Exception as e:
            logger.debug(f"Erro na validacao de entrada: {e}")
            return ImageAnalysis(
                description="Erro ao validar entrada de imagem",
                confidence=0.0
            )

        # ---- Camada 2: prompt prompt ----
        try:
            if not prompt:
                prompt = "Descreva esta imagem em detalhe. Identifique objetos, texto, cores e contexto."
            if not isinstance(prompt, str):
                prompt = str(prompt)
        except Exception as e:
            logger.debug(f"Erro ao processar prompt: {e}")
            prompt = "Descreva esta imagem em detalhe."

        # ---- Camada 3: tentar provedores ----
        try:
            # Build provider list based on request
            providers_to_try = []
            if provider in ("auto", "gemini"):
                providers_to_try.append(("gemini", self._analyze_gemini))
            if provider in ("auto", "groq"):
                providers_to_try.append(("groq", self._analyze_groq))

            # ---- Camada 4: iterar sobre provedores ----
            for prov_name, prov_func in providers_to_try:
                try:
                    # Cada provedor tem seu proprio try/except interno
                    result = prov_func(image_path, prompt)
                    if result is not None:
                        # Validar resultado
                        if hasattr(result, 'confidence'):
                            result.confidence = max(0.0, min(1.0, result.confidence))
                        if hasattr(result, 'description'):
                            if not result.description or result.description == "":
                                result.description = "Analise concluida sem texto descriptivo"
                        return result
                    # Se result for None, continuar para proximo provedor
                except TypeError as e:
                    # Modelo nao suporta input de imagem - pular para proximo
                    logger.debug(f"Provider {prov_name} nao suporta input de imagem: {e}")
                    continue
                except Exception as e:
                    # Qualquer outro erro: logar e continuar
                    logger.debug(f"Erro no provider {prov_name}: {type(e).__name__}: {e}")
                    continue
        except Exception as e:
            # Fallback global se algo inesperado acontecer no loop
            logger.error(f"Erro inesperado ao analisar imagem: {type(e).__name__}: {e}")

        # ---- Camada 5: nenhum provedor funcionou ----
        return ImageAnalysis(
            description="Nenhum provider de vision conseguiu analisar esta imagem. "
                        "Configure GEMINI_API_KEY ou GROQ_API_KEY com modelos compatíveis.",
            confidence=0.0,
            model_used="none"
        )

    def _analyze_gemini(self, image_path: str, prompt: str) -> Optional[ImageAnalysis]:
        """Analisa imagem usando Gemini Vision."""
        try:
            client = self._get_gemini()
            if not client:
                return None
            try:
                import google.genai as genai
                mime = self._get_mime_type(image_path)
                with open(image_path, "rb") as f:
                    image_data = f.read()

                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        genai.types.Part.from_bytes(data=image_data, mime_type=mime),
                        prompt
                    ]
                )
                text = response.text or ""
                return ImageAnalysis(
                    description=text,
                    model_used="gemini-2.0-flash",
                    confidence=0.9,
                    raw_response=text,
                )
            except Exception as e:
                logger.error(f"Erro Gemini vision: {e}")
                return None
        except Exception as e:
            logger.error(f"Erro geral em _analyze_gemini: {type(e).__name__}: {e}")
            return None

    def _analyze_groq(self, image_path: str, prompt: str) -> Optional[ImageAnalysis]:
        """Analisa imagem usando Groq Vision (llama-4-scout)."""
        try:
            client = self._get_groq()
            if not client:
                return None
            try:
                b64 = self._encode_image(image_path)
                mime = self._get_mime_type(image_path)
                response = client.chat.completions.create(
                    model="llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:{mime};base64,{b64}"
                            }}
                        ]
                    }],
                    max_tokens=1024,
                )
                text = response.choices[0].message.content or ""
                return ImageAnalysis(
                    description=text,
                    model_used="llama-4-scout-17b-16e-instruct",
                    confidence=0.85,
                    raw_response=text,
                )
            except Exception as e:
                logger.error(f"Erro Groq vision: {e}")
                return None
        except Exception as e:
            logger.error(f"Erro geral em _analyze_groq: {type(e).__name__}: {e}")
            return None

    def analyze_clipboard_image(self, prompt: str = None) -> Optional[ImageAnalysis]:
        """Analisa imagem da area de transferencia."""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                return None
            tmp = Path(tempfile.gettempdir()) / "sage_clipboard.png"
            try:
                img.save(str(tmp))
            except Exception:
                return None
            try:
                result = self.analyze_image(str(tmp), prompt)
            except Exception:
                result = None
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            return result
        except Exception as e:
            logger.debug(f"Nao foi possivel ler imagem da area de transferencia: {e}")
            return None

    def analyze_screenshot(self, prompt: str = None, region: str = None) -> Optional[ImageAnalysis]:
        """Captura e analisa screenshot."""
        try:
            from EliveaAI_Clone.modules.screen_context import ScreenContext
            try:
                tmp = Path(tempfile.gettempdir()) / "sage_screenshot.png"
                ScreenContext.capture_screenshot(str(tmp), region=region or "full")
            except Exception:
                return None
            try:
                result = self.analyze_image(str(tmp), prompt)
            except Exception:
                result = None
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            return result
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {type(e).__name__}: {e}")
            return None

analyzer = ImageAnalyzer()