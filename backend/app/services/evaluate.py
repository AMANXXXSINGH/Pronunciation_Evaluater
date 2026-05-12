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
    from .grok_feedback import GrokFeedback
    GROK_AVAILABLE = True
except Exception as e:
    print(f"Warning: Grok feedback not available: {e}")
    GROK_AVAILABLE = False
    GrokFeedback = None


class EvaluationService:
    def __init__(
        self,
        *,
        store: SQLiteStore,
        transcriber: WhisperTranscriber,
        phoneme_comparator: PhonemeComparator,
        grok_feedback: any = None,
    ) -> None:
        self.store = store
        self.transcriber = transcriber
        self.phoneme_comparator = phoneme_comparator
        if GROK_AVAILABLE and GrokFeedback:
            try:
                self.ai_feedback_service = grok_feedback or GrokFeedback()
                self.ai_enabled = self.ai_feedback_service.enabled
            except Exception as e:
                print(f"Warning: AI feedback disabled: {e}")
                self.ai_feedback_service = None
                self.ai_enabled = False
        else:
            self.ai_feedback_service = None
            self.ai_enabled = False

    def _format_grammar_issue(self, message: str, replacement: str | None = None) -> str:
        if replacement:
            return f"{message} Suggestion: {replacement}"
        return message

    def _find_grammar_issues_regex(self, text: str, language: str | None = None) -> tuple[list[str], str | None]:
        if not text.strip():
            return [], None

        issues: list[str] = []
        normalized = text.strip()
        lower = normalized.lower()
        corrected_text = normalized

        if language and not language.startswith("en"):
            issues.append("Grammar analysis is currently supported only for English.")
            return issues, None



        # 2. 'of' instead of 'have'
        if re.search(r"\b(could|should|would|might|must)\s+of\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Use 'have' instead of 'of' after modal verbs.", "e.g., 'could have' instead of 'could of'."
                )
            )
            corrected_text = re.sub(r"\b(could|should|would|might|must)\s+of\b", r"\1 have", corrected_text, flags=re.IGNORECASE)

        # 3. Subject-verb agreement
        if re.search(r"\b(we|you|they)\s+was\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Incorrect verb agreement.", "Use 'were' instead of 'was' for we/you/they."
                )
            )
            corrected_text = re.sub(r"\b(we|you|they)\s+was\b", r"\1 were", corrected_text, flags=re.IGNORECASE)

        if re.search(r"\b(he|she|it)\s+don't\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Incorrect verb agreement.", "Use 'doesn't' instead of 'don't' for he/she/it."
                )
            )
            corrected_text = re.sub(r"\b(he|she|it)\s+don't\b", r"\1 doesn't", corrected_text, flags=re.IGNORECASE)

        if re.search(r"\b(i|you|we|they)\s+doesn't\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Incorrect verb agreement.", "Use 'don't' instead of 'doesn't' for I/you/we/they."
                )
            )
            corrected_text = re.sub(r"\b(I|you|we|they)\s+doesn't\b", r"\1 don't", corrected_text, flags=re.IGNORECASE)

        # 4. Irregular verbs past participle
        if re.search(r"\b(have|has|had)\s+went\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Incorrect past participle.", "Use 'gone' instead of 'went' after have/has/had."
                )
            )
            corrected_text = re.sub(r"\b(have|has|had)\s+went\b", r"\1 gone", corrected_text, flags=re.IGNORECASE)
            
        if re.search(r"\b(have|has|had)\s+did\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Incorrect past participle.", "Use 'done' instead of 'did' after have/has/had."
                )
            )
            corrected_text = re.sub(r"\b(have|has|had)\s+did\b", r"\1 done", corrected_text, flags=re.IGNORECASE)

        if re.search(r"\b(have|has|had)\s+came\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Incorrect past participle.", "Use 'come' instead of 'came' after have/has/had."
                )
            )
            corrected_text = re.sub(r"\b(have|has|had)\s+came\b", r"\1 come", corrected_text, flags=re.IGNORECASE)

        # 5. Double negatives
        if re.search(r"\b(don't|doesn't|didn't|won't|can't|haven't|hasn't|isn't|aren't|ain't)\s+(have|got|need|want|get|know|see|find|do|make)\s+no\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Double negative detected.", "Use 'any' or remove the negative to make it positive."
                )
            )
            corrected_text = re.sub(r"\b(don't|doesn't|didn't|won't|can't|haven't|hasn't|isn't|aren't|ain't)\s+(have|got|need|want|get|know|see|find|do|make)\s+no\b", r"\1 \2 any", corrected_text, flags=re.IGNORECASE)
            
        # 6. 'a' vs 'an'
        if re.search(r"\ba\s+(apple|egg|elephant|ice|orange|umbrella|hour|honest|answer|animal|artist)\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Use 'an' before vowel sounds.", "Change 'a' to 'an'."
                )
            )
            corrected_text = re.sub(r"\ba\s+(apple|egg|elephant|ice|orange|umbrella|hour|honest|answer|animal|artist)\b", r"an \1", corrected_text, flags=re.IGNORECASE)
            
        if re.search(r"\ban\s+(car|dog|book|house|tree|user|university|one|person)\b", lower):
            issues.append(
                self._format_grammar_issue(
                    "Use 'a' before consonant sounds.", "Change 'an' to 'a'."
                )
            )
            corrected_text = re.sub(r"\ban\s+(car|dog|book|house|tree|user|university|one|person)\b", r"a \1", corrected_text, flags=re.IGNORECASE)

        # 7. Repeated words
        match = re.search(r"\b(\w+)\s+\1\b", lower)
        if match and match.group(1) not in ['that', 'had', 'very']:
            issues.append(
                self._format_grammar_issue(
                    "Repeated words were detected.",
                    "Remove the duplicate word."
                )
            )
            corrected_text = re.sub(r"\b(\w+)\s+\1\b", r"\1", corrected_text, flags=re.IGNORECASE)

        if len(issues) > 5:
            issues = issues[:5]

        if corrected_text != normalized and len(corrected_text) > 0:
            corrected_text = corrected_text[0].upper() + corrected_text[1:]
            return issues, corrected_text

        return issues, None

    async def _find_grammar_issues(self, text: str, language: str | None = None) -> tuple[list[str], str | None]:
        if not text.strip():
            return [], None

        if language and not language.startswith("en"):
            return ["Grammar analysis is currently supported only for English."], None

        import urllib.request
        import urllib.parse
        import json
        from fastapi.concurrency import run_in_threadpool

        url = 'https://api.languagetool.org/v2/check'
        lang_code = 'en-US' if not language or language.startswith('en') else language
        data = urllib.parse.urlencode({'text': text, 'language': lang_code}).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        
        try:
            response = await run_in_threadpool(urllib.request.urlopen, req, timeout=5)
            result = json.loads(response.read().decode('utf-8'))
            
            matches = result.get("matches", [])
            if not matches:
                return [], None
                
            issues = []
            corrected_text = text
            
            for match in sorted(matches, key=lambda x: x["offset"], reverse=True):
                # Ignore upper/lower case issues and punctuation issues
                rule_category = match.get("rule", {}).get("category", {}).get("id")
                if rule_category in ["CASING", "PUNCTUATION"]:
                    continue
                    
                issues.append(f"{match['shortMessage'] or 'Grammar issue'}: {match['message']}")
                
                replacements = match.get("replacements", [])
                if replacements:
                    rep_value = replacements[0]["value"]
                    offset = match["offset"]
                    length = match["length"]
                    corrected_text = corrected_text[:offset] + rep_value + corrected_text[offset+length:]
                    
            if len(issues) > 5:
                issues = issues[:5]
                
            if corrected_text == text:
                return issues, None
                
            return issues, corrected_text
            
        except Exception as e:
            print(f"LanguageTool API error: {e}")
            return self._find_grammar_issues_regex(text, language)

    def _generate_general_feedback(
        self,
        accuracy_score: float,
        wpm: float,
        mispronounced_count: int,
        grammar_issues_count: int,
        has_expected: bool,
        mispronounced: list[EvaluateResponseWord] = []
    ) -> str:
        feedback_parts = []
        
        # Pronunciation performance
        if has_expected:
            if accuracy_score >= 90:
                feedback_parts.append("✨ **Excellent pronunciation!** You're speaking like a native speaker.")
            elif accuracy_score >= 75:
                feedback_parts.append("👍 **Great effort!** Your speech is very clear, just a few small refinements needed.")
            elif accuracy_score >= 50:
                feedback_parts.append("💪 **Keep it up!** You're communicating well, but focusing on the red words will make you sound more natural.")
            else:
                feedback_parts.append("🎯 **Practice makes perfect.** Focus on enunciating each sound clearly and try repeating the words highlighted in red.")
        else:
            feedback_parts.append("📝 I've transcribed your free speech. Look at the WPM and word breakdown below.")

        # Specific word feedback for top mispronounced words
        if mispronounced and has_expected:
            # Sort by similarity to show most critical first, but only if they have similarity
            critical = [w for w in mispronounced if w.phoneme_similarity is not None]
            critical.sort(key=lambda x: x.phoneme_similarity or 0)
            
            if critical:
                top_word = critical[0]
                if top_word.suggestion:
                    feedback_parts.append(f"🔍 **Key Tip:** For the word **'{top_word.expected}'**, {top_word.suggestion}")

        # Speaking rate
        if wpm > 165:
            feedback_parts.append("🐢 **Pace Tip:** You're a bit fast! Slowing down slightly will help others understand your clear pronunciation.")
        elif wpm < 100 and wpm > 0:
            feedback_parts.append("🚀 **Pace Tip:** You're a bit slow. Try to connect the words more smoothly to sound more fluent.")
        elif wpm >= 100 and wpm <= 165:
            feedback_parts.append("✅ **Perfect Tempo:** Your speaking rate is ideal for clear communication.")

        # Grammar
        if grammar_issues_count > 0:
            feedback_parts.append(f"✍️ **Grammar:** I found {grammar_issues_count} potential improvements in your sentence structure.")
        elif grammar_issues_count == 0 and has_expected:
            feedback_parts.append("🌟 **Perfect Grammar!** Your sentence structure is flawless.")

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

        # We add 500ms of silence to the beginning of the audio using '-af adelay=500|500'. 
        # This prevents Whisper's Voice Activity Detection from aggressively cutting off the first word.
        cmd = [ffmpeg_bin, "-y", "-i", input_path, "-af", "adelay=500|500", "-ar", "16000", "-ac", "1", output_path]
        
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"FFmpeg error output: {proc.stderr}")
                # Fallback: Try without adelay if it fails (some ffmpeg versions or input formats might struggle)
                print("Retrying without adelay...")
                cmd_fallback = [ffmpeg_bin, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path]
                proc_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True)
                if proc_fallback.returncode != 0:
                    raise HTTPException(
                        status_code=500,
                        detail=f"ffmpeg failed completely. {proc_fallback.stderr.strip()[:500]}",
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

        grammar_issues, corrected_text = await self._find_grammar_issues(transcribed_text, language)

        # Calculate WPM before sending to DB and Response
        wpm_val = (len(recognized_words) / (duration / 60.0)) if duration > 0 else 0.0

        # Generate overall feedback
        overall_feedback = self._generate_general_feedback(
            accuracy_score=accuracy_score,
            wpm=wpm_val,
            mispronounced_count=len(mispronounced),
            grammar_issues_count=len(grammar_issues),
            has_expected=has_expected,
            mispronounced=mispronounced
        )

        # Generate AI feedback (if available and enabled)
        ai_feedback = None
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
            except Exception as e:
                print(f"Failed to generate AI feedback (continuing without it): {e}")
                ai_feedback = None

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
            grammar_issues=grammar_issues,
            corrected_text=corrected_text,
            created_at=created_at,
            attempt_id=attempt_id,
            audio_url=audio_url,
            duration=duration,
            wpm=wpm_val,
            feedback=overall_feedback,
            ai_feedback=ai_feedback,
        )

