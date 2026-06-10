# FIDES — Risk Intelligence Pipeline

AI-powered trade-compliance analyzer. Upload shipping documents (PDF / image),
the pipeline extracts entities with Gemini, scores risk against mock
enrichment APIs (AIS, sanctions, market price, address, vessel history),
and renders an explainable audit report with a built-in chat assistant.

## Stack
- **Backend:** FastAPI + Uvicorn
- **LLM:** Google Gemini (`gemini-1.5-flash`)
- **OCR:** EasyOCR (images) / PyPDF2 (PDFs)
- **UI:** Vanilla HTML/CSS/JS (dark dashboard)

## Run locally (VS Code)

1. **Clone / unzip** the project and open the folder in VS Code.
2. **Create a virtual environment** (Python 3.10 or 3.11 recommended):
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```
3. **Install dependencies** (first install pulls PyTorch for EasyOCR — a few hundred MB):
   ```bash
   pip install -r requirements.txt
   ```
4. **Add your Gemini API key.** Open `.env` and replace the placeholder:
   ```
   GOOGLE_API_KEY=AIza...your_real_key...
   ```
   Get a free key at https://aistudio.google.com/app/apikey.
5. **Start the server:**
   ```bash
   uvicorn app:app --reload --port 8000
   ```
6. Open http://localhost:8000 in your browser.

## Notes
- No API key is hard-coded; the app reads `GOOGLE_API_KEY` from `.env`.
- If the key is missing, the UI will show a clear error and fall back to mock
  extraction so the pipeline can still be demoed.
- EasyOCR downloads its detection model on first image upload (~64 MB).
