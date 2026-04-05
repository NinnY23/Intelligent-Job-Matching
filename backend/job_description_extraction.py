import json
import os
import re
import tempfile
from typing import Any, Dict

import google.generativeai as genai

from compatibility_metrics_schema import (
    metrics_document_for_prompt,
    normalize_compatibility_metrics,
    normalize_skill_entries,
)

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image")


class JobDescriptionExtractionError(Exception):
    """Raised when job description PDF extraction fails."""


def normalize_job_description_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise JobDescriptionExtractionError("Model output is not a JSON object")
    merged = dict(payload)
    if not merged.get("jobRole") and merged.get("jobTitle"):
        merged["jobRole"] = merged.get("jobTitle")
    metrics = normalize_compatibility_metrics(merged)
    if not metrics["skills"] and isinstance(payload.get("skills"), list):
        metrics["skills"] = normalize_skill_entries(payload.get("skills"))
    return metrics


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


def _build_prompt() -> str:
    return (
        "You are an extraction engine. Read the job description PDF (posted by a hiring manager) and "
        + metrics_document_for_prompt(is_resume=False)
    )


def extract_job_description_preview(pdf_bytes: bytes, mime_type: str = "application/pdf") -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise JobDescriptionExtractionError("Missing GEMINI_API_KEY")

    if not pdf_bytes:
        raise JobDescriptionExtractionError("Job description PDF is empty")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(DEFAULT_MODEL)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_bytes)
            temp_path = tmp_file.name

        try:
            uploaded = genai.upload_file(path=temp_path, mime_type=mime_type)
            response = model.generate_content(
                [_build_prompt(), uploaded],
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
