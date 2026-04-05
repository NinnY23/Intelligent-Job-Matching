import io
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as backend_app
from resume_extraction import normalize_extraction_payload


def test_normalize_extraction_payload_shapes():
    payload = {
        "skills": ["Python", " Python ", "", 123],
        "achievements": ["Won hackathon", "Won hackathon", None],
        "standardizedTests": [
            {
                "testName": "IELTS",
                "score": "8.0",
                "grade": "",
                "sourceText": "IELTS 8.0",
            },
            "bad item",
        ],
    }

    normalized = normalize_extraction_payload(payload)
    assert len(normalized["skills"]) == 1
    assert normalized["skills"][0]["name"] == "Python"
    assert normalized["achievements"] == ["Won hackathon"]
    assert normalized["standardizedTests"][0]["testName"] == "IELTS"
    assert normalized["standardizedTests"][0]["rawScore"] == "8.0"


def test_extract_resume_endpoint_rejects_missing_file():
    client = backend_app.app.test_client()
    response = client.post(
        "/api/resume/extract-preview",
        headers={"Authorization": "Bearer token_test_1"},
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Missing resume file"


def test_extract_resume_endpoint_rejects_non_pdf():
    client = backend_app.app.test_client()
    response = client.post(
        "/api/resume/extract-preview",
        data={"resume": (io.BytesIO(b"hello"), "resume.txt")},
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer token_test_1"},
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Only PDF files are supported"


def test_extract_resume_endpoint_success(monkeypatch):
    def _mock_extract(pdf_bytes, mime_type):
        assert mime_type == "application/pdf"
        assert pdf_bytes.startswith(b"%PDF")
        return {
            "provider": "gemini",
            "model": "gemini-1.5-flash",
            "extraction": {
                "skills": [{"name": "Python", "compatibilityLevel": "", "evidence": ""}],
                "jobRole": "",
                "moneyEstimate": "",
                "duration": "",
                "gpax": "",
                "educationLevel": "",
                "standardizedTests": [],
                "languages": [],
                "employmentType": "unknown",
                "achievements": ["Top 5%"],
            },
        }

    monkeypatch.setattr(backend_app, "extract_resume_preview", _mock_extract)
    client = backend_app.app.test_client()
    response = client.post(
        "/api/resume/extract-preview",
        data={"resume": (io.BytesIO(b"%PDF-1.7 sample"), "resume.pdf")},
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer token_test_1"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["provider"] == "gemini"
    assert data["extraction"]["skills"][0]["name"] == "Python"
