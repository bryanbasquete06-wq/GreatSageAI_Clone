# -*- coding: utf-8 -*-
"""Analise de videos usando extracao de frames + analise com vision LLM."""
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("greatsage.video")

@dataclass
class VideoFrame:
    timestamp: float
    image_path: str
    description: str = ""

@dataclass
class VideoAnalysis:
    title: str = ""
    duration_seconds: float = 0.0
    frame_count: int = 0
    frames: List[VideoFrame] = field(default_factory=list)
    summary: str = ""
    model_used: str = ""
    raw_response: str = ""

class VideoAnalyzer:
    """Analise de videos usando extracao de frames + vision LLM."""

    def __init__(self):
        self._image_analyzer = None

    def _get_image_analyzer(self):
        if self._image_analyzer is None:
            from GreatSageAI_Clone.core.image_analyzer import analyzer
            self._image_analyzer = analyzer
        return self._image_analyzer

    def _extract_frames_ffmpeg(self, video_path: str, output_dir: str, num_frames: int = 5) -> List[VideoFrame]:
        """Extrai frames do video usando imageio-ffmpeg."""
        try:
            import imageio_ffmpeg as ffmpeg
            import subprocess

            # Get video duration
            probe_cmd = [
                ffmpeg.get_ffmpeg_exe(), "-i", video_path,
                "-show_entries", "format=duration",
                "-v", "quiet", "-of", "csv=p=0"
            ]
            try:
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                duration = float(result.stdout.strip() or "0")
            except Exception:
                duration = 0

            # Calculate timestamps
            if duration > 0:
                interval = duration / (num_frames + 1)
                timestamps = [interval * (i + 1) for i in range(num_frames)]
            else:
                timestamps = [0] * num_frames

            frames = []
            for i, ts in enumerate(timestamps):
                out_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
                cmd = [
                    ffmpeg.get_ffmpeg_exe(),
                    "-ss", str(ts),
                    "-i", video_path,
                    "-frames:v", "1",
                    "-q:v", "2",
                    out_path,
                    "-y"
                ]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=15)
                    if os.path.exists(out_path):
                        frames.append(VideoFrame(timestamp=ts, image_path=out_path))
                except Exception as e:
                    logger.debug(f"Erro ao extrair frame {ts}s: {e}")

            return frames, duration
        except ImportError:
            logger.warning("imageio-ffmpeg nao instalado")
            return [], 0

    def _extract_frames_pil(self, video_path: str, output_dir: str, num_frames: int = 5) -> List[VideoFrame]:
        """Extrai frames usando PIL/Pillow (fallback)."""
        try:
            from PIL import Image
            import subprocess

            # Use ffmpeg directly if available
            try:
                duration_result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                    capture_output=True, text=True, timeout=10
                )
                duration = float(duration_result.stdout.strip() or "0")
            except Exception:
                duration = 0

            if duration > 0:
                interval = duration / (num_frames + 1)
                timestamps = [interval * (i + 1) for i in range(num_frames)]
            else:
                timestamps = [0] * num_frames

            frames = []
            for i, ts in enumerate(timestamps):
                out_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
                cmd = [
                    "ffmpeg", "-ss", str(ts), "-i", video_path,
                    "-frames:v", "1", "-q:v", "2", out_path, "-y"
                ]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=15)
                    if os.path.exists(out_path):
                        frames.append(VideoFrame(timestamp=ts, image_path=out_path))
                except Exception as e:
                    logger.debug(f"Erro ao extrair frame {ts}s: {e}")

            return frames, duration
        except ImportError:
            return [], 0

    def extract_frames(self, video_path: str, num_frames: int = 5) -> tuple:
        """Extrai frames do video. Retorna (frames, duration)."""
        if not os.path.exists(video_path):
            return [], 0

        output_dir = tempfile.mkdtemp(prefix="sage_video_")
        frames, duration = self._extract_frames_ffmpeg(video_path, output_dir, num_frames)

        if not frames:
            frames, duration = self._extract_frames_pil(video_path, output_dir, num_frames)

        return frames, duration

    def analyze_video(self, video_path: str, prompt: str = None, num_frames: int = 5) -> VideoAnalysis:
        """Analisa um video extraindo frames e enviando ao vision LLM."""
        if not os.path.exists(video_path):
            return VideoAnalysis(summary=f"Video nao encontrado: {video_path}")

        prompt = prompt or "Analise estes frames de um video. Descreva o conteudo, acao, contexto e quaisquer textos visiveis."

        frames, duration = self.extract_frames(video_path, num_frames)

        if not frames:
            return VideoAnalysis(
                summary="Nao foi possivel extrair frames do video. Verifique se ffmpeg esta instalado.",
                duration_seconds=duration
            )

        analyzer = self._get_image_analyzer()
        frame_analyses = []
        all_descriptions = []

        for frame in frames:
            try:
                result = analyzer.analyze_image(frame.image_path, prompt)
                if result and hasattr(result, "description"):
                    frame.description = result.description
                else:
                    frame.description = ""
            except Exception as e:
                logger.debug(f"Erro ao analisar frame: {type(e).__name__}: {e}")
                frame.description = ""
            frame_analyses.append(frame)
            all_descriptions.append(f"[{frame.timestamp:.1f}s] {frame.description}")

        # Build summary
        summary_parts = [
            f"Video analisado ({len(frames)} frames, {duration:.1f}s):",
            "",
        ]
        for desc in all_descriptions:
            summary_parts.append(desc)

        summary = " ming".join(summary_parts)

        # Cleanup temp files
        for frame in frames:
            try:
                os.unlink(frame.image_path)
            except Exception:
                pass

        return VideoAnalysis(
            title=Path(video_path).stem,
            duration_seconds=duration,
            frame_count=len(frames),
            frames=frame_analyses,
            summary=summary,
            model_used=frames[0].image_path if frames else "",
        )

    def analyze_youtube(self, url: str, prompt: str = None) -> VideoAnalysis:
        """Analisa um video do YouTube baixando e extraindo frames."""
        try:
            import subprocess
            tmp = Path(tempfile.gettempdir()) / "sage_youtube.mp4"

            # Download video with yt-dlp
            cmd = [
                "yt-dlp",
                "-f", "best[height<=720]",
                "--max-filesize", "50M",
                "-o", str(tmp),
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if not tmp.exists():
                return VideoAnalysis(summary="Nao foi possivel baixar o video do YouTube.")

            analysis = self.analyze_video(str(tmp), prompt, num_frames=8)
            analysis.title = f"YouTube: {url}"

            tmp.unlink(missing_ok=True)
            return analysis

        except FileNotFoundError:
            return VideoAnalysis(summary="yt-dlp nao instalado. Instale com: pip install yt-dlp")
        except Exception as e:
            logger.error(f"Erro ao analisar YouTube: {e}")
            return VideoAnalysis(summary=f"Erro ao analisar video: {e}")

analyzer = VideoAnalyzer()