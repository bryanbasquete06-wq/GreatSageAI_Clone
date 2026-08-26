#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — Suporte Multi-Modal
====================================
Analise e geracao de imagens.
"""

import os
import io
import base64
import logging
import tempfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("greatsage.multimodal")


@dataclass
class ImageResult:
    success: bool
    output: str
    image_path: str = ""


def analyze_image(image_path: str) -> ImageResult:
    """Analyze an image and describe its contents."""
    try:
        path = Path(image_path)
        if not path.exists():
            return ImageResult(False, f"Arquivo nao encontrado: {image_path}")

        # Get file info
        size = path.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB"

        # Try to get image dimensions
        try:
            from PIL import Image
            img = Image.open(path)
            width, height = img.size
            fmt = img.format or "Desconhecido"
            mode = img.mode
            dims = f"{width}x{height}"
        except ImportError:
            dims = "desconhecido"
            fmt = path.suffix.upper().replace(".", "")
            mode = "N/A"
        except Exception:
            dims = "erro ao ler"
            fmt = path.suffix.upper().replace(".", "")
            mode = "N/A"

        # Try AI-powered analysis
        analysis = _analyze_with_ai(path)

        return ImageResult(
            True,
            f"**Analise da Imagem:**\n\n"
            f"Arquivo: `{path.name}`\n"
            f"Tamanho: {size_str}\n"
            f"Dimensoes: {dims}\n"
            f"Formato: {fmt}\n"
            f"Modo: {mode}\n\n"
            f"{analysis}" if analysis else f"Arquivo: `{path.name}` ({size_str}, {dims})",
            str(path)
        )
    except Exception as e:
        return ImageResult(False, f"Erro ao analisar imagem: {e}")


def _analyze_with_ai(image_path: Path) -> str:
    """Try to analyze image with AI (Google Gemini)."""
    try:
        import google.genai as genai
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            return ""

        client = genai.Client(api_key=api_key)

        # Upload image
        file = client.files.upload(file=str(image_path))

        # Analyze
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[file, "Descreva esta imagem em detalhes. O que voce ve?"]
        )

        return response.text or ""
    except Exception as e:
        logger.warning(f"AI image analysis failed: {e}")
        return ""


def generate_image(prompt: str) -> ImageResult:
    """Generate an image from a text prompt."""
    try:
        # Try DALL-E via OpenAI
        try:
            import openai
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key:
                client = openai.OpenAI(api_key=api_key)
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                image_url = response.data[0].url
                return ImageResult(
                    True,
                    f"**Imagem gerada:**\n\n"
                    f"Prompt: {prompt}\n"
                    f"URL: {image_url}\n\n"
                    f"Ou baixe diretamente do link acima.",
                    image_url
                )
        except Exception:
            pass

        # Try Stable Diffusion via Hugging Face
        try:
            import requests
            api_key = os.environ.get("HUGGINGFACE_API_KEY", "")
            if api_key:
                response = requests.post(
                    "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"inputs": prompt},
                    timeout=60,
                )
                if response.status_code == 200:
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp.write(response.content)
                    tmp.close()
                    return ImageResult(
                        True,
                        f"**Imagem gerada:**\n\n"
                        f"Prompt: {prompt}\n"
                        f"Salva em: `{tmp.name}`",
                        tmp.name
                    )
        except Exception:
            pass

        return ImageResult(
            False,
            "Para gerar imagens, configure:\n"
            "- `OPENAI_API_KEY` para DALL-E\n"
            "- `HUGGINGFACE_API_KEY` para Stable Diffusion\n\n"
            "Ou use manualmente:\n"
            "```python\n"
            "from PIL import Image\n"
            "# Sua imagem aqui\n"
            "```"
        )
    except Exception as e:
        return ImageResult(False, f"Erro ao gerar imagem: {e}")


def get_image_info(image_path: str) -> str:
    """Get basic info about an image file."""
    try:
        from PIL import Image
        img = Image.open(image_path)
        return (f"Formato: {img.format}, Tamanho: {img.size}, "
                f"Modo: {img.mode}")
    except ImportError:
        return "PIL nao instalado. Use: pip install Pillow"
    except Exception as e:
        return f"Erro: {e}"
