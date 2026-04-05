import io
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as backend_app
from job_description_extraction import normalize_job_description_payload


def test_normalize_job_description_payload():
    payload = {
        "jobTitle": "  Engineer  ",
        "location": "Remote",
        "yearsExperienceMin": "3",
        "yearsExperienceMax": "",
        "skills": ["Python", "Python", 99],
        "educationRequirements": ["BS CS"],
        "certifications": ["AWS"],
        "otherConsiderations": ["On-call"],
    }
    out = normalize_job_description_payload(payload)
    assert out["jobRole"] == "Engineer"
    assert [s["name"] for s in out["skills"]] == ["Python"]
    assert "BS CS" in (out.get("educationLevel") or "")


def test_extract_job_description_rejects_non_pdf(monkeypatch):
    monkeypatch.setattr(backend_app, "_email_from_bearer", lambda: "jd@test.com")
    client = backend_app.app.test_client()
    response = client.post(
        "/api/job-description/extract-preview",
        data={"job_description": (io.BytesIO(b"hello"), "jd.txt")},
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer token_jduser_1"},
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Only PDF files are supported"


def test_extract_job_description_success(monkeypatch):
    monkeypatch.setattr(backend_app, "_email_from_bearer", lambda: "jd@test.com")

    def _mock(pdf_bytes, mime_type):
        return {
            "provider": "gemini",
            "model": "gemini-test",
            "extraction": {
                "jobRole": "PM",
                "skills": [{"name": "SQL", "compatibilityLevel": "", "evidence": ""}],
                "moneyEstimate": "",
                "duration": "5-7 years (experience range)",
                "gpax": "",
                "educationLevel": "",
                "standardizedTests": [],
                "languages": [],
                "employmentType": "full_time_job",
                "achievements": [],
            },
        }

    monkeypatch.setattr(backend_app, "extract_job_description_preview", _mock)
    client = backend_app.app.test_client()
    response = client.post(
        "/api/job-description/extract-preview",
        data={"job_description": (io.BytesIO(b"%PDF-1.7 jd"), "jd.pdf")},
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer token_jduser_1"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["extraction"]["jobRole"] == "PM"
