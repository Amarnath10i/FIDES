import io
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["GOOGLE_API_KEY"] = ""  # never call the real API from tests

import app as fides  # noqa: E402

client = TestClient(fides.app)


def blank_pdf() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_sanctioned_consignee_and_shell_address_are_flagged():
    risk = fides.RiskEnricher.enrich({
        "vessel_name": "MV CLEAN", "shipper_name": "Acme Exports",
        "consignee_address": "TechImport BV, PO Box 12, Rotterdam", "unit_price": "10", "hs_code": "520100",
    })
    f = risk["risk_factors"]
    assert f["consignee_sanctions_risk"]["sanctions_match"]
    assert f["address_risk"]["is_shell_company"]
    assert not f["shipper_sanctions_risk"]["sanctions_match"]


def test_price_deviation_uses_the_hs_chapter():
    r = fides.MockAPIs.check_market_price("851712", 700.0)
    assert r["category"] == "ELECTRONICS" and r["is_overpriced"]
    assert r["deviation_percentage"] == pytest.approx(100.0)


def test_fingerprint_is_the_same_across_processes():
    code = ("import app; d={'hs_code':'520100','vessel_name':'MV STAR'}; "
            "print(app.RiskFingerprintGenerator.generate(d, {'overall_risk_score':0.4})['risk_fingerprint_hash'])")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outs = {subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True,
                           env={**os.environ, "PYTHONHASHSEED": seed}).stdout.strip().splitlines()[-1]
            for seed in ("1", "2")}
    assert len(outs) == 1


def test_parse_entities_accepts_fenced_json_and_rejects_prose():
    assert fides.parse_entities('```json\n{"vessel_name": "MV A"}\n```') == {"vessel_name": "MV A"}
    with pytest.raises(fides.HTTPException) as e:
        fides.parse_entities("I could not find any fields.")
    assert e.value.status_code == 502


def test_without_a_key_the_response_says_the_sample_was_used():
    r = client.post("/analyze", files={"files": ("bl.pdf", blank_pdf(), "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["extraction_source"] == "sample"
    assert isinstance(body["audit_report"], str)


def test_a_failing_model_is_an_error_not_a_fake_analysis(monkeypatch):
    monkeypatch.setattr(fides, "_gemini_model", object())
    monkeypatch.setattr(fides, "call_gemini", lambda prompt: (None, "quota exceeded"))
    r = client.post("/analyze", files={"files": ("bl.pdf", blank_pdf(), "application/pdf")})
    assert r.status_code == 502
    assert "quota exceeded" in r.json()["detail"]


def test_extracted_fields_from_the_model_are_used(monkeypatch):
    monkeypatch.setattr(fides, "_gemini_model", object())
    reply = '{"vessel_name": "MV CLEAN", "shipper_name": "Acme", "consignee_address": "Main St 1", "unit_price": "12", "hs_code": "520100"}'
    monkeypatch.setattr(fides, "call_gemini", lambda prompt: (reply, None) if "Extract" in prompt else ("report", None))
    body = client.post("/analyze", files={"files": ("bl.pdf", blank_pdf(), "application/pdf")}).json()
    assert body["extraction_source"] == "gemini"
    assert body["extracted_data"]["vessel_name"] == "MV CLEAN"
    assert body["risk_assessment"]["risk_level"] == "LOW"
    assert body["audit_report"] == "report"
