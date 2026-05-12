# Pronunciation Evaluator (Full Stack)

React frontend + FastAPI backend. The backend:
- records audio sent from the browser (multipart upload),
- converts it to WAV (requires `ffmpeg`),
- transcribes with OpenAI Whisper (`openai-whisper`),
- computes Word Error Rate (WER) using Levenshtein distance on word tokens,
- highlights mispronounced words and estimates phoneme similarity using NLTK `cmudict`,
- stores attempts + history in SQLite.

## 1) Prerequisites

### Install ffmpeg (required)
The backend uses `ffmpeg` to convert the browser audio (often WebM/Opus) into a WAV file Whisper can read.

- Windows: install `ffmpeg` and make sure `ffmpeg.exe` is available in your `PATH`.

### Install Python 3.10+ (recommended)

### Whisper note (heavy dependency)
`openai-whisper` requires PyTorch. Install PyTorch first using the correct command for your machine (CPU vs GPU).

Example (CPU, pip wheels): install from the official PyTorch site:
https://pytorch.org/get-started/locally/

## 2) Backend setup (FastAPI)

```powershell
cd "pronunciation-evaluator\backend"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

If `cmudict` is missing, the first request will trigger an NLTK download automatically.

## 3) Frontend setup (React + Vite)

```powershell
cd "pronunciation-evaluator\frontend"
npm install
npm run dev
```

By default the frontend calls the backend at `http://localhost:8000`.

If you run the backend on a different host/port:
Set `VITE_API_BASE`, e.g.
`VITE_API_BASE=http://localhost:8001`.

## 4) How it works (end-to-end)

1. Type/paste the expected text.
2. Click `Start Recording`, speak, then `Stop`.
3. The app shows:
   - Whisper transcription,
   - WER and an accuracy score (`accuracy = (1 - WER) * 100`),
   - word-level highlight (green = match, red = substitution/deletion),
   - phoneme similarity feedback for mispronounced words using CMU dict.
4. Attempts are stored in `backend/pronunciation.db` and shown in the history panel.

## 5) Limitations

- WER here uses simple whitespace tokenization + case/punctuation normalization.
- Pronunciation “phoneme feedback” is heuristic: it compares expected-vs-spoken words after Whisper transcription, using CMU dict entries when available.
- Deep phoneme alignment from raw audio is not implemented (this keeps the project feasible with open-source tooling).

