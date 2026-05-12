from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


from dotenv import load_dotenv

from app.db.sqlite_store import SQLiteStore
from app.analysis.phoneme_feedback import PhonemeComparator
from app.services.evaluate import EvaluationService
from app.services.history import HistoryService
from app.transcription.whisper import WhisperTranscriber


def create_app() -> FastAPI:
    load_dotenv()
    
    app = FastAPI(title="Pronunciation Evaluator", version="1.0.0")

    # Allow local dev frontend access.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    base_dir = Path(__file__).resolve().parent
    uploads_dir = base_dir / 'uploads'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount('/uploads', StaticFiles(directory=str(uploads_dir)), name='uploads')
    db_path = base_dir / "pronunciation.db"
    store = SQLiteStore(db_path)
    transcriber = WhisperTranscriber()
    phoneme_comparator = PhonemeComparator(download_if_missing=True)

    evaluate_service = EvaluationService(
        store=store,
        transcriber=transcriber,
        phoneme_comparator=phoneme_comparator,
    )
    history_service = HistoryService(store=store)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/evaluate")
    async def evaluate(
        audio: UploadFile = File(...),
        expected_text: str | None = Form(None),
        language: str | None = Form(None),
        model_name: str = Form("base"),
    ):
        return await evaluate_service.evaluate(
            upload_file=audio,
            expected_text=expected_text,
            language=language,
            model_name=model_name,
        )

    @app.get("/api/history")
    def history(limit: int = 20):
        return history_service.list(limit=limit)

    @app.delete("/api/history")
    def delete_history():
        history_service.clear()
        return {"status": "ok", "deleted": True}

    @app.delete("/api/history/{attempt_id}")
    def delete_history_item(attempt_id: int):
        deleted = history_service.delete(attempt_id=attempt_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="History item not found")
        return {"status": "ok", "deleted": True}

    return app


app = create_app()

