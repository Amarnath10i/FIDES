"""
FIDES — Risk Intelligence Pipeline
FastAPI backend that orchestrates a 5-stage trade-compliance analysis.
"""
from __future__ import annotations

import io
import json
import os
import re
from typing import Any, Dict, List, Optional

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from PyPDF2 import PdfReader

import google.generativeai as genai
from dotenv import find_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv(find_dotenv())

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

# Auto-detect available Gemini model
def _detect_available_model() -> Optional[str]:
    """Auto-detect an available Gemini model that supports generateContent."""
    try:
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                model_name = model.name.split('/')[-1]
                print(f"[DEBUG] Auto-detected model: {model_name}")
                return model_name
    except Exception as e:
        print(f"[DEBUG] Failed to list models: {e}")
    return None

_gemini_model: Optional[genai.GenerativeModel] = None
_gemini_error: Optional[str] = None
GEMINI_MODEL_NAME: Optional[str] = None

if GOOGLE_API_KEY and GOOGLE_API_KEY != "your_gemini_api_key_here":
    try:
        print("[DEBUG] Configuring Gemini API...")
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Auto-detect model
        GEMINI_MODEL_NAME = _detect_available_model()
        
        if GEMINI_MODEL_NAME:
            _gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            print(f"[DEBUG] Gemini model initialized successfully: {GEMINI_MODEL_NAME}")
        else:
            _gemini_error = "No compatible Gemini model found"
            print(f"[DEBUG] {_gemini_error}")
    except Exception as exc:  # pragma: no cover
        _gemini_error = f"Failed to initialize Gemini: {exc}"
        print(f"[DEBUG] Failed to initialize: {_gemini_error}")
else:
    _gemini_error = (
        "GOOGLE_API_KEY is not set. Add it to .env to enable AI extraction; "
        "the pipeline will fall back to mock data."
    )
    print(f"[DEBUG] {_gemini_error}")

# Lazy OCR reader (heavy import — only created on first image upload)
_ocr_reader = None


def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr  # imported lazily
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


def call_gemini(prompt: str) -> tuple[Optional[str], Optional[str]]:
    """Call Gemini safely; return (text, error_message) tuple."""
    if _gemini_model is None:
        return None, "Gemini model not initialized"
    try:
        response = _gemini_model.generate_content(prompt)
        result = (response.text or "").strip()
        if not result:
            return None, "Gemini returned empty response"
        return result, None
    except Exception as exc:
        import traceback
        err = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=__import__('sys').stderr)
        return None, err


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="FIDES Risk Intelligence Pipeline")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Mock enrichment APIs
# ---------------------------------------------------------------------------
class MockAPIs:
    SUSPICIOUS_VESSELS = {"MV STAR", "OCEAN PRINCE", "SEA GLORY"}
    SANCTIONS_LIST = ["EURO FASHION GMBH", "TECHIMPORT BV", "CHEMCO LTD"]
    MARKET_PRICES = {
        "TEXTILE": 12.50,
        "ELECTRONICS": 350.00,
        "PHARMA": 45.00,
        "AUTO": 250.00,
        "FOOD": 8.00,
        "STEEL": 850.00,
        "HANDICRAFT": 35.00,
        "CHEMICAL": 28.00,
    }

    @staticmethod
    def check_ais(vessel_name: str) -> Dict[str, Any]:
        sus = vessel_name.upper() in MockAPIs.SUSPICIOUS_VESSELS
        return {
            "vessel_name": vessel_name,
            "ais_gap_detected": sus,
            "last_known_position": "Position unknown" if sus else "Normal tracking",
            "risk_score": 0.7 if sus else 0.1,
        }

    @staticmethod
    def check_sanctions(entity_name: str) -> Dict[str, Any]:
        u = entity_name.upper()
        match = any(s in u for s in MockAPIs.SANCTIONS_LIST)
        return {
            "entity": entity_name,
            "sanctions_match": match,
            "list_name": "OFAC_SDN" if match else None,
            "risk_score": 0.9 if match else 0.0,
        }

    @staticmethod
    def check_market_price(hs_code: str, price: float, currency: str = "USD") -> Dict[str, Any]:
        category = "TEXTILE"
        if hs_code.startswith("85"):
            category = "ELECTRONICS"
        elif hs_code.startswith("30"):
            category = "PHARMA"
        elif hs_code.startswith("87"):
            category = "AUTO"
        market_avg = MockAPIs.MARKET_PRICES.get(category, 50.0)
        deviation = ((price - market_avg) / market_avg) * 100 if market_avg else 0
        return {
            "category": category,
            "market_average": market_avg,
            "declared_price": price,
            "currency": currency,
            "deviation_percentage": round(deviation, 2),
            "is_overpriced": price > market_avg * 1.5,
            "is_underpriced": 0 < price < market_avg * 0.5,
            "risk_score": min(abs(deviation) / 100, 1.0),
        }

    @staticmethod
    def check_address(address: str) -> Dict[str, Any]:
        suspicious_terms = ["PO BOX", "PMB", "SUITE", "VIRTUAL", "SHELL"]
        has = any(t in address.upper() for t in suspicious_terms)
        return {
            "address": address,
            "is_shell_company": has,
            "address_quality": "Poor" if has else "Good",
            "risk_score": 0.8 if has else 0.1,
        }

    @staticmethod
    def check_vessel_history(vessel_name: str) -> Dict[str, Any]:
        history = {"MV STAR", "OCEAN PRINCE"}
        changes = 3 if vessel_name.upper() in history else 0
        return {
            "vessel_name": vessel_name,
            "name_changes_2_years": changes,
            "high_risk_flag": changes >= 2,
            "risk_score": min(changes / 3, 1.0),
        }


# ---------------------------------------------------------------------------
# Stage 1 — Document processing
# ---------------------------------------------------------------------------
class DocumentProcessor:
    @staticmethod
    async def process_pdf(file: UploadFile) -> str:
        contents = await file.read()
        pdf = PdfReader(io.BytesIO(contents))
        return "\n".join((page.extract_text() or "") for page in pdf.pages)

    @staticmethod
    async def process_image(file: UploadFile) -> str:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        result = get_ocr_reader().readtext(np.array(image))
        return " ".join(item[1] for item in result)

    @staticmethod
    async def process(file: UploadFile) -> str:
        name = (file.filename or "").lower()
        if name.endswith(".pdf"):
            return await DocumentProcessor.process_pdf(file)
        if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
            return await DocumentProcessor.process_image(file)
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")


# ---------------------------------------------------------------------------
# Stage 2 — Entity extraction
# ---------------------------------------------------------------------------
MOCK_ENTITIES = {
    "vessel_name": "MV STAR",
    "hs_code": "520100",
    "total_weight": "5000",
    "unit_price": "12.50",
    "shipper_name": "Sunrise Textiles Pvt Ltd",
    "consignee_address": "Euro Fashion GmbH, Hamburg, Germany",
    "invoice_amount": "USD 1750.00",
    "bl_number": "BL20240701",
    "product_description": "Cotton Textiles",
}


class EntityExtractor:
    @staticmethod
    async def extract(text: str) -> Dict[str, Any]:
        prompt = f"""
Extract trade-document fields from the text below.
Return ONLY a valid JSON object (no markdown, no commentary).

Required fields:
- vessel_name, hs_code, total_weight, unit_price, shipper_name,
  consignee_address, invoice_amount, bl_number, product_description

Document text:
\"\"\"
{text[:6000]}
\"\"\"
"""
        raw = call_gemini(prompt)
        if not raw:
            return dict(MOCK_ENTITIES)
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            return json.loads(match.group() if match else raw)
        except Exception:
            return dict(MOCK_ENTITIES)


# ---------------------------------------------------------------------------
# Stage 3 — Risk enrichment
# ---------------------------------------------------------------------------
def _parse_number(value: Any) -> float:
    m = re.search(r"([\d,]+\.?\d*)", str(value or ""))
    return float(m.group(1).replace(",", "")) if m else 0.0


class RiskEnricher:
    @staticmethod
    def enrich(data: Dict[str, Any]) -> Dict[str, Any]:
        vessel = data.get("vessel_name", "Unknown")
        shipper = data.get("shipper_name", "Unknown")
        consignee = data.get("consignee_address", "Unknown")
        unit_price = _parse_number(data.get("unit_price"))
        hs_code = str(data.get("hs_code", "000000"))

        factors = {
            "ais_risk": MockAPIs.check_ais(vessel),
            "shipper_sanctions_risk": MockAPIs.check_sanctions(shipper),
            "consignee_sanctions_risk": MockAPIs.check_sanctions(consignee),
            "price_risk": MockAPIs.check_market_price(hs_code, unit_price),
            "address_risk": MockAPIs.check_address(consignee),
            "vessel_history_risk": MockAPIs.check_vessel_history(vessel),
        }

        scores = [f.get("risk_score", 0.0) for f in factors.values()]
        overall = round(sum(scores) / len(scores), 3) if scores else 0.0
        if overall >= 0.6:
            level = "HIGH"
        elif overall >= 0.3:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "risk_factors": factors,
            "overall_risk_score": overall,
            "risk_level": level,
        }


# ---------------------------------------------------------------------------
# Stage 4 — Federated risk fingerprint
# ---------------------------------------------------------------------------
class RiskFingerprintGenerator:
    @staticmethod
    def generate(data: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
        factors = risk.get("risk_factors", {})
        return {
            "risk_fingerprint_hash": abs(hash(json.dumps([
                data.get("hs_code", ""),
                (data.get("vessel_name", "") or "")[:3],
                risk.get("overall_risk_score", 0),
            ]))) % 1_000_000,
            "privacy_note": "No PII shared — only risk indicators.",
            "sharable_features": {
                "price_deviation": factors.get("price_risk", {}).get("deviation_percentage", 0),
                "vessel_risk": factors.get("ais_risk", {}).get("risk_score", 0),
                "sanctions_risk": max(
                    factors.get("shipper_sanctions_risk", {}).get("risk_score", 0),
                    factors.get("consignee_sanctions_risk", {}).get("risk_score", 0),
                ),
            },
        }


# ---------------------------------------------------------------------------
# Stage 5 — Report
# ---------------------------------------------------------------------------
class ReportGenerator:
    @staticmethod
    def _violations(data: Dict[str, Any], factors: Dict[str, Any]) -> List[str]:
        v: List[str] = []
        pr = factors.get("price_risk", {})
        if pr.get("is_overpriced"):
            v.append(f"⚠️ Price anomaly: {pr.get('deviation_percentage')}% above market average")
        if pr.get("is_underpriced"):
            v.append(f"⚠️ Price anomaly: {pr.get('deviation_percentage')}% below market average")
        if factors.get("ais_risk", {}).get("ais_gap_detected"):
            v.append(f"⚠️ AIS gap: vessel {data.get('vessel_name')} has tracking gaps")
        if factors.get("address_risk", {}).get("is_shell_company"):
            v.append("⚠️ Shell company: consignee address appears to be a virtual office")
        if factors.get("shipper_sanctions_risk", {}).get("sanctions_match"):
            v.append("🚨 Sanctions alert: shipper found on OFAC list")
        if factors.get("consignee_sanctions_risk", {}).get("sanctions_match"):
            v.append("🚨 Sanctions alert: consignee found on OFAC list")
        if factors.get("vessel_history_risk", {}).get("high_risk_flag"):
            v.append("⚠️ Vessel history: multiple name changes detected")
        return v

    @staticmethod
    def generate(data: Dict[str, Any], risk: Dict[str, Any]) -> str:
        level = risk.get("risk_level", "Unknown")
        score = risk.get("overall_risk_score", 0)
        violations = ReportGenerator._violations(data, risk.get("risk_factors", {}))

        prompt = f"""
Write a professional trade-compliance audit report.

Transaction:
- Shipper: {data.get('shipper_name')}
- Consignee: {data.get('consignee_address')}
- Vessel: {data.get('vessel_name')}
- Product: {data.get('product_description')}
- Amount: {data.get('invoice_amount')}

Risk: {level} ({score}/1.0)

Findings:
{chr(10).join(violations) if violations else 'No major violations detected.'}

Structure:
1. Executive Summary (2-3 sentences)
2. Risk Breakdown
3. Regulatory Implications
4. Recommended Actions
"""
        ai = call_gemini(prompt)
        if ai:
            return ai

        return (
            f"# FIDES Risk Assessment Report\n\n"
            f"## Executive Summary\nTransaction risk level: **{level}** (score {score}).\n\n"
            f"## Risk Breakdown\n" + ("\n".join(f"- {x}" for x in violations) or "- All checks passed.") + "\n\n"
            f"## Recommendation\n"
            + ("Review flagged items before proceeding." if violations else "Transaction appears compliant.")
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "gemini_ready": _gemini_model is not None,
            "gemini_error": _gemini_error,
            "model_name": GEMINI_MODEL_NAME,
        },
    )

    


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "gemini_ready": _gemini_model is not None,
        "gemini_error": _gemini_error,
        "model": GEMINI_MODEL_NAME,
    }


@app.post("/analyze")
async def analyze(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one document is required")
    try:
        all_text = ""
        for f in files:
            all_text += await DocumentProcessor.process(f) + "\n"

        extracted = await EntityExtractor.extract(all_text)
        risk = RiskEnricher.enrich(extracted)
        fingerprint = RiskFingerprintGenerator.generate(extracted, risk)
        report = ReportGenerator.generate(extracted, risk)

        return JSONResponse(
            {
                "extracted_data": extracted,
                "risk_assessment": risk,
                "federated_fingerprint": fingerprint,
                "audit_report": report,
                "raw_text_preview": all_text[:1000],
                "status": "success",
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat")
async def chat(request: Request):
    payload = await request.json()
    question = (payload.get("question") or "").strip()
    context = payload.get("context") or ""
    if not question:
        return JSONResponse({"answer": "Please ask a question."})

    prompt = f"""
You are a trade-compliance expert. Use the analysis context to answer the question concisely.

Context:
{json.dumps(context)[:6000]}

Question: {question}
"""
    answer, error = call_gemini(prompt)
    if not answer:
        answer = f"AI assistant unavailable: {error or 'Unknown error'}"
    return JSONResponse({"answer": answer})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
