# FIDES

**Document screening for small customs brokers: upload a shipment's documents, get a plain-language risk brief.**

FIDES (Federated Intelligence for Document & Entity Screening) reads a bill of lading, invoice and packing list (PDF or image), extracts the trade fields with an LLM, runs a set of risk checks on them and writes an audit-style report that a broker can question in a chat.

> **Status: hackathon prototype.** Document reading and LLM extraction are real. The risk checks are rule-based stand-ins over small built-in lists (a few sanctioned names, flagged vessels and reference prices), not live sanctions, AIS or pricing feeds, and the risk score is an unweighted average that has not been validated on labelled shipments. Treat the output as a demonstration of the workflow, not a compliance decision.

## Pipeline

| Stage | What it does | Real or stand-in |
|---|---|---|
| 1. Ingest | PDF text with PyPDF2; images through EasyOCR | real |
| 2. Extract | Gemini returns vessel, HS code, weight, unit price, shipper, consignee, invoice amount, B/L number and product as JSON | real (needs `GOOGLE_API_KEY`) |
| 3. Enrich | sanctions name match, AIS-gap and vessel-rename flags, price deviation against a reference price for the HS chapter, PO-box / virtual-office address check | stand-in lists in `MockAPIs` |
| 4. Score | mean of the six check scores; ≥ 0.6 HIGH, ≥ 0.3 MEDIUM, else LOW | heuristic |
| 5. Share | a non-identifying fingerprint (HS code, vessel prefix, score) that brokers could pool without sharing documents | design sketch; nothing is sent anywhere |
| 6. Report | Gemini writes the brief from the findings; a template is used if the model is unavailable; a chat endpoint answers follow-up questions | real |

Without an API key the app still runs: it shows a built-in sample shipment and says so on the page (`extraction_source: "sample"` in the API response). With a key, a failed or non-JSON model reply is returned as an error rather than replaced by sample data.

## Run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # add GOOGLE_API_KEY
uvicorn app:app --reload                             # http://localhost:8000
```

## API

| Method | Route | Body / result |
|---|---|---|
| `POST` | `/analyze` | multipart `files` (PDF, JPG, PNG); returns extracted fields, `extraction_source`, risk factors, fingerprint and report |
| `POST` | `/chat` | `{"question": ..., "context": <analyze result>}`; returns an answer grounded in the analysis |
| `GET` | `/api/health` | whether Gemini is configured and which model was detected |

## Tests

```bash
pip install pytest httpx
pytest -q
```

The tests cover the risk rules, JSON parsing of model replies, that a failing model produces an error instead of a fabricated analysis, that the sample fallback is labelled, and that the fingerprint is stable across processes.

## What it would take to be real

- **Data sources:** OFAC SDN / UN / EU consolidated lists with fuzzy name matching, an AIS provider for gap detection, and customs unit-value statistics per HS code instead of the reference table.
- **Scoring:** labelled historical shipments to fit and validate weights, and calibrated probabilities instead of an average of hand-set scores.
- **Extraction:** a field-level evaluation set of real documents, and per-field confidence so low-confidence fields are shown for review.
- **SDK:** `google-generativeai` is deprecated; move to `google-genai`.

## Layout

```
app.py              FastAPI app and the pipeline stages
templates/, static/ single-page UI
tests/              pipeline and API tests (no network)
```
