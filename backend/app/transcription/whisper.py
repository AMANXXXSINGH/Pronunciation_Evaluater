from __future__ import annotations

import threading
import os
from dataclasses import dataclass
from typing import Any

import whisper


@dataclass(frozen=True)
class TranscriptionResult:
    text: str


class WhisperTranscriber:
    def __init__(self) -> None:
        self._models: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._ffmpeg_setup_done = False

    def _get_model(self, model_name: str) -> Any:
        with self._lock:
            if model_name in self._models:
                return self._models[model_name]
            model = whisper.load_model(model_name)
            self._models[model_name] = model
            return model

    def _ensure_ffmpeg_on_path(self) -> None:
        """
        The `whisper` package internally shells out to `ffmpeg`.
        On Windows the server process may not inherit the same PATH as your shell.
        """
        if self._ffmpeg_setup_done:
            return

        ffmpeg_env = os.environ.get("FFMPEG_BIN") or os.environ.get("FFMPEG_PATH")
        ffmpeg_dir: str | None = None
        if ffmpeg_env:
            # If it's a file, use its parent; if it's a dir, use it directly.
            p = os.path.abspath(ffmpeg_env)
            if os.path.isdir(p):
                ffmpeg_dir = p
            else:
                ffmpeg_dir = os.path.dirname(p)
        else:
            # Common Windows install locations.
            for candidate_dir in [
                r"C:\ffmpeg\bin",
                r"C:\FFmpeg\bin",
                r"D:\ffmpeg\bin",
                r"D:\ffmpeg",
                r"C:\Program Files\ffmpeg\bin",
                r"C:\Program Files (x86)\ffmpeg\bin",
            ]:
                ffmpeg_exe = os.path.join(candidate_dir, "ffmpeg.exe")
                if os.path.isfile(ffmpeg_exe):
                    ffmpeg_dir = candidate_dir
                    break

        if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        self._ffmpeg_setup_done = True

    def transcribe(
        self,
        audio_path: str,
        *,
        model_name: str = "base",
        language: str | None = None,
    ) -> TranscriptionResult:
        self._ensure_ffmpeg_on_path()
        model = self._get_model(model_name)
        # fp16=False is safer on CPU.
        result = model.transcribe(audio_path, language=language, task='transcribe', fp16=False)
        text = (result.get("text") or "").strip()
        return TranscriptionResult(text=text)

