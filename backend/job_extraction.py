import json
import os
import re
import tempfile
from typing import Any, Dict, List

import google.generativeai as genai

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image")


class JobDescriptionExtractionError(Exception):
    """Raised when job description PDF extraction fails."""


def _clean_text_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    cleaned: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_job_description_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise JobDescriptionExtractionError("Model output is not a JSON object")

    return {
        "jobTitle": _clean_str(payload.get("jobTitle")),
        "company": _clean_str(payload.get("company")),
        "location": _clean_str(payload.get("location")),
        "skills": _clean_text_list(payload.get("skills")),
        "yearsExperience": _clean_str(payload.get("yearsExperience")),
        "otherConsiderations": _clean_text_list(payload.get("otherConsiderations")),
        "summary": _clean_str(payload.get("summary")),
    }


def _extract_json_block(text: str) -> str:
    if not text or not isinstance(text, str):
        raise JobDescriptionExtractionError("Empty response from model")

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        raise JobDescriptionExtractionError("Could not locate JSON object in model response")

    return text[start_index : end_index + 1]


def _build_job_prompt() -> str:
    return (
        "You are an extraction engine. Read the job description PDF and return only valid JSON "
        "with this exact top-level schema: "
        '{"jobTitle":"","company":"","location":"","skills":[],"yearsExperience":"","otherConsiderations":[],"summary":""}. '
        "Rules: "
        "1) Include only evidence from the PDF. "
        "2) skills is a list of required or preferred technical and professional skills. "
        "3) yearsExperience is a single string summarizing required years of experience "
        "(e.g. \"3+ years\", \"5-7 years\", or \"\" if not stated). "
        "4) otherConsiderations is a list of important non-skill factors: certifications, education, "
        "travel, clearance, soft skills, language, work authorization, leadership, domain knowledge. "
        "5) summary is a short plain-text overview of the role (2-5 sentences). "
        "6) Use empty string or empty array if unknown. "
        "7) Do not include markdown, prose, or extra keys."
    )


def extract_job_description_preview(
    pdf_bytes: bytes, mime_type: str = "application/pdf"
) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise JobDescriptionExtractionError("Missing GEMINI_API_KEY")

    if not pdf_bytes:
        raise JobDescriptionExtractionError("Job description file is empty")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(DEFAULT_MODEL)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_bytes)
            temp_path = tmp_file.name

        try:
            uploaded = genai.upload_file(path=temp_path, mime_type=mime_type)
            response = model.generate_content(
                [_build_job_prompt(), uploaded],
                request_options={"timeout": 90},
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        response_text = getattr(response, "text", "") or ""
        json_block = _extract_json_block(response_text)
        raw_payload = json.loads(json_block)
        normalized_payload = normalize_job_description_payload(raw_payload)
        return {
            "provider": "gemini",
            "model": DEFAULT_MODEL,
            "extraction": normalized_payload,
        }
    except JobDescriptionExtractionError:
        raise
    except json.JSONDecodeError as exc:
        raise JobDescriptionExtractionError(f"Invalid JSON from model: {exc}") from exc
    except Exception as exc:
        raise JobDescriptionExtractionError(f"Gemini extraction failed: {exc}") from exc
