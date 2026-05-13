from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
import uuid
import wave
import shutil

from datetime import datetime
from typing import Any
from pathlib import Path
import shutil

from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..analysis.phoneme_feedback import PhonemeComparator
from ..analysis.wer import wer_with_alignment, levenshtein_similarity
from ..db.sqlite_store import SQLiteStore
from ..schemas import EvaluateResponse, EvaluateResponseWord
from ..transcription.whisper import WhisperTranscriber
from ..utils.text import normalize_text, tokenize_words

try:
    from .groq_feedback import GroqFeedback
    GROQ_AVAILABLE = True
except Exception as e:
    print(f"Warning: Groq feedback not available: {e}")
    GROQ_AVAILABLE = False
    GroqFeedback = None


class EvaluationService:
    def __init__(
        self,
        *,
        store: SQLiteStore,
        transcriber: WhisperTranscriber,
        phoneme_comparator: PhonemeComparator,
        groq_feedback: any = None,
    ) -> None:
        self.store = store
        self.transcriber = transcriber
        self.phoneme_comparator = phoneme_comparator
        if GROQ_AVAILABLE and GroqFeedback:
            try:
                self.ai_feedback_service = groq_feedback or GroqFeedback()
                self.ai_enabled = self.ai_feedback_service.enabled
            except Exception as e:
                print(f"Warning: AI feedback disabled: {e}")
                self.ai_feedback_service = None
                self.ai_enabled = False
        else:
            self.ai_feedback_service = None
            self.ai_enabled = False

    def _generate_general_feedback(
        self,
        accuracy_score: float,
        wpm: float,
        mispronounced_count: int,
        has_expected: bool,
        mispronounced: list[EvaluateResponseWord] = []
    ) -> str:
        feedback_parts = []
        
        # Pronunciation performance
        if has_expected:
            if accuracy_score >= 90:
                feedback_parts.append("Excellent pronunciation! You're speaking like a native speaker.")
            elif accuracy_score >= 75:
                feedback_parts.append("Great effort! Your speech is very clear, just a few small refinements needed.")
            elif accuracy_score >= 50:
                feedback_parts.append("Keep it up! You're communicating well, but focusing on the red words will make you sound more natural.")
            else:
                feedback_parts.append("Practice makes perfect. Focus on enunciating each sound clearly and try repeating the words highlighted in red.")
        else:
            pass

        # Specific word feedback for top mispronounced words
        if mispronounced and has_expected:
            # Sort by similarity to show most critical first, but only if they have similarity
            critical = [w for w in mispronounced if w.phoneme_similarity is not None]
            critical.sort(key=lambda x: x.phoneme_similarity or 0)
            
            if critical:
                top_word = critical[0]
                if top_word.suggestion:
                    feedback_parts.append(f"Key Tip: For the word '{top_word.expected}', {top_word.suggestion}")

        # Speaking rate
        if wpm > 165:
            feedback_parts.append("Pace Tip: You're a bit fast! Slowing down slightly will help others understand your clear pronunciation.")
        elif wpm < 100 and wpm > 0:
            feedback_parts.append("Pace Tip: You're a bit slow. Try to connect the words more smoothly to sound more fluent.")
        elif wpm >= 100 and wpm <= 165:
            feedback_parts.append("Perfect Tempo: Your speaking rate is ideal for clear communication.")



        return "\n\n".join(feedback_parts)

    def _convert_audio_to_wav(self, input_path: str, output_path: str) -> None:
        # ffmpeg converts whatever the browser produced (often webm/opus) into PCM wav.
        ffmpeg_env = os.environ.get("FFMPEG_BIN") or os.environ.get("FFMPEG_PATH")
        candidates: list[str] = []
        if ffmpeg_env:
            # If the env var points to a dir, append ffmpeg.exe.
            p = Path(ffmpeg_env)
            if p.is_dir():
                candidates.append(str(p / "ffmpeg.exe"))
            else:
                candidates.append(str(p))

        # Common locations on Windows. (Does not require PATH.)
        for p in [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\FFmpeg\bin\ffmpeg.exe",
            r"D:\ffmpeg\ffmpeg.exe",
            r"D:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        ]:
            candidates.append(p)

        # Finally, try PATH lookup.
        which = shutil.which("ffmpeg")
        if which:
            candidates.append(which)

        ffmpeg_bin = next((c for c in candidates if c and Path(c).is_file()), None)
        if not ffmpeg_bin:
            raise HTTPException(
                status_code=500,
                detail=(
                    "ffmpeg is required but could not be found. "
                    "Install ffmpeg and ensure it is reachable to the backend. "
                    "Tip: set `FFMPEG_BIN` to the full path of ffmpeg.exe."
                ),
            )

        cmd = [ffmpeg_bin, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path]
        
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"FFmpeg error output: {proc.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"ffmpeg failed completely. {proc.stderr.strip()[:500]}",
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Audio conversion failed: {str(e)}")

    async def evaluate(
        self,
        *,
        upload_file: UploadFile,
        expected_text: str,
        language: str | None = None,
        model_name: str = "base",
    ) -> EvaluateResponse:
        if not upload_file:
            raise HTTPException(status_code=400, detail="audio file is required.")

        # Save + convert in temp folder.
        with tempfile.TemporaryDirectory() as tmpdir:
            ext = os.path.splitext(upload_file.filename or "")[1].lower() or ".webm"
            input_path = os.path.join(tmpdir, f"input{ext}")
            
            base_dir = Path(__file__).resolve().parent.parent.parent
            uploads_dir = base_dir / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            file_id = str(uuid.uuid4())
            wav_filename = f"{file_id}.wav"
            wav_path = str(uploads_dir / wav_filename)
            audio_url = f"/uploads/{wav_filename}"

            file_bytes = await upload_file.read()
            with open(input_path, "wb") as f:
                f.write(file_bytes)

            # Convert synchronously (small files), but keep API responsive via threadpool.
            await run_in_threadpool(self._convert_audio_to_wav, input_path, wav_path)

            transcription = await run_in_threadpool(
                self.transcriber.transcribe,
                wav_path,
                model_name=model_name,
                language=language,
            )
            transcribed_text = transcription.text

            duration = 0.0
            try:
                with wave.open(wav_path, "rb") as w:
                    duration = w.getnframes() / w.getframerate()
            except:
                pass

        if not transcribed_text.strip() or duration < 0.1:
            raise HTTPException(
                status_code=400, 
                detail="No speech could be recognized. Please try speaking more clearly or for longer."
            )

        expected_text = expected_text or ""
        expected_norm = normalize_text(expected_text)
        recognized_norm = normalize_text(transcribed_text)

        suggestions: list[str] = []
        if expected_norm:
            expected_words = tokenize_words(expected_norm)
            recognized_words = tokenize_words(recognized_norm)

            wer, alignments = wer_with_alignment(expected_words, recognized_words)
            accuracy_score = max(0.0, min(100.0, (1.0 - wer) * 100.0))
            levensim = levenshtein_similarity(expected_norm, recognized_norm)

            words: list[EvaluateResponseWord] = []
            mispronounced: list[EvaluateResponseWord] = []

            for idx, a in enumerate(alignments):
                ok = a.op == "match"
                item = EvaluateResponseWord(
                    index=idx,
                    expected=a.expected if a.expected is not None else "[Extra word]",
                    recognized=a.recognized,
                    ok=ok,
                    feedback=None,
                    phoneme_similarity=None,
                    suggestion=None,
                )

                if a.op == "insert":
                    item.feedback = "Extra word detected in speech."
                    item.suggestion = "Try to stick exactly to the expected text."
                    suggestions.append(item.suggestion)
                    mispronounced.append(item)
                elif not ok:
                    match = self.phoneme_comparator.compare_words(a.expected or "", a.recognized or "")
                    item.feedback = match.message
                    item.phoneme_similarity = match.similarity
                    item.suggestion = self.phoneme_comparator.suggest_improvement(
                        a.expected or "", a.recognized or ""
                    )
                    if item.suggestion:
                        suggestions.append(item.suggestion)
                    mispronounced.append(item)

                words.append(item)
            has_expected = True
        else:
            recognized_words = tokenize_words(recognized_norm)
            wer = 0.0
            accuracy_score = 100.0
            levensim = 1.0
            words = []
            for index, recognized_word in enumerate(recognized_words):
                phonemes = self.phoneme_comparator.phonemes_for_word(recognized_word)
                suggestion = None
                if phonemes:
                    suggestion = f"Pronounce as: /{self.phoneme_comparator._format_sound(phonemes)}/"
                else:
                    suggestion = "Pronunciation guide not available for this word."
                words.append(
                    EvaluateResponseWord(
                        index=index,
                        expected=recognized_word,
                        recognized=recognized_word,
                        ok=True,
                        feedback="Pronunciation guide provided.",
                        phoneme_similarity=None,
                        suggestion=suggestion,
                    )
                )
            mispronounced = []
            has_expected = False

        # Calculate WPM before sending to DB and Response
        wpm_val = (len(recognized_words) / (duration / 60.0)) if duration > 0 else 0.0

        # Generate overall feedback
        overall_feedback = self._generate_general_feedback(
            accuracy_score=accuracy_score,
            wpm=wpm_val,
            mispronounced_count=len(mispronounced),
            has_expected=has_expected,
            mispronounced=mispronounced
        )

        # Generate AI feedback (if available and enabled)
        ai_feedback = None
        ai_grammar_analysis = None
        if self.ai_enabled and self.ai_feedback_service:
            try:
                mispronounced_dicts = [
                    {"expected": w.expected, "spoken": w.recognized}
                    for w in mispronounced[:10]
                ]
                ai_feedback = await run_in_threadpool(
                    self.ai_feedback_service.generate_feedback,
                    expected_text=expected_text,
                    transcribed_text=transcribed_text,
                    accuracy_score=accuracy_score,
                    mispronounced_words=mispronounced_dicts,
                    has_expected=has_expected,
                )
                ai_grammar_analysis = await run_in_threadpool(
                    self.ai_feedback_service.generate_grammar_analysis,
                    transcribed_text=transcribed_text,
                )
            except Exception as e:
                print(f"Failed to generate AI feedback (continuing without it): {e}")
                ai_feedback = None
                ai_grammar_analysis = None

        created_at = datetime.now()
        attempt_id, created_at_db = self.store.create_attempt(
            expected_text=expected_text,
            transcribed_text=transcribed_text,
            wer=wer,
            accuracy_score=accuracy_score,
            levenshtein_similarity=levensim,
            words=[w.model_dump() for w in words],
            audio_url=audio_url,
            duration=duration,
            wpm=wpm_val,
            feedback=overall_feedback,
            ai_feedback=ai_feedback,
        )
        created_at = created_at_db

        return EvaluateResponse(
            expected_text=expected_text,
            transcribed_text=transcribed_text,
            has_expected=has_expected,
            wer=wer,
            accuracy_score=accuracy_score,
            levenshtein_similarity=levensim,
            words=words,
            mispronounced_words=mispronounced,
            suggestions=suggestions,
            ai_grammar_analysis=ai_grammar_analysis,
            created_at=created_at,
            attempt_id=attempt_id,
            audio_url=audio_url,
            duration=duration,
            wpm=wpm_val,
            feedback=overall_feedback,
            ai_feedback=ai_feedback,
        )

