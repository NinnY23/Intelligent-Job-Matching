"""
Unified 9-metric schema for resume and job-description extraction (structure.md).
"""

from typing import Any, Dict, List

def _str_field(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_str_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    for v in values:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if s and s not in out:
            out.append(s)
    return out


def normalize_skill_entries(values: Any) -> List[Dict[str, str]]:
    if not isinstance(values, list):
        return []
    out: List[Dict[str, str]] = []
    seen_lower: set[str] = set()
    for item in values:
        if isinstance(item, str):
            name = item.strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_lower:
                continue
            seen_lower.add(key)
            out.append({"name": name, "compatibilityLevel": "", "evidence": ""})
            continue
        if not isinstance(item, dict):
            continue
        name = _str_field(item.get("name") or item.get("skill"))
        if not name:
            continue
        key = name.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        out.append(
            {
                "name": name,
                "compatibilityLevel": _str_field(
                    item.get("compatibilityLevel")
                    or item.get("level")
                    or item.get("proficiency")
                ),
                "evidence": _str_field(item.get("evidence") or item.get("notes")),
            }
        )
    return out


def _normalize_tests(values: Any) -> List[Dict[str, str]]:
    if not isinstance(values, list):
        return []
    out: List[Dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        row = {
            "testName": _str_field(item.get("testName")),
            "normalizedScore": _str_field(
                item.get("normalizedScore") or item.get("normalized_score")
            ),
            "rawScore": _str_field(item.get("rawScore") or item.get("score")),
            "grade": _str_field(item.get("grade")),
            "sourceText": _str_field(item.get("sourceText")),
        }
        if any(row.values()):
            out.append(row)
    return out


def _normalize_languages(values: Any) -> List[Dict[str, str]]:
    if not isinstance(values, list):
        return []
    out: List[Dict[str, str]] = []
    for item in values:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append({"language": s, "level": ""})
            continue
        if not isinstance(item, dict):
            continue
        lang = _str_field(item.get("language") or item.get("name"))
        if not lang:
            continue
        out.append(
            {
                "language": lang,
                "level": _str_field(item.get("level") or item.get("proficiency")),
            }
        )
    return out


def normalize_compatibility_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize model output to the 9-metric shape (+ achievements for resumes).
    Accepts legacy resume keys (standardTestScores, string skills) and JD keys (jobTitle, ...).
    """
    if not isinstance(payload, dict):
        payload = {}

    skills_raw = payload.get("skills")
    skills = normalize_skill_entries(skills_raw)

    job_role = _str_field(
        payload.get("jobRole")
        or payload.get("jobTitle")
        or payload.get("job_title")
    )

    money = _str_field(payload.get("moneyEstimate") or payload.get("money"))
    duration = _str_field(
        payload.get("duration")
        or payload.get("durationText")
        or payload.get("contractDuration")
    )
    if not duration:
        ymin = _str_field(payload.get("yearsExperienceMin"))
        ymax = _str_field(payload.get("yearsExperienceMax"))
        if ymin or ymax:
            duration = f"{ymin or '?'}-{ymax or '?'} years (experience range)"

    gpax = _str_field(payload.get("gpax") or payload.get("gpa") or payload.get("GPA"))

    edu = _str_field(payload.get("educationLevel") or payload.get("education"))
    if not edu and isinstance(payload.get("educationRequirements"), list):
        parts = _clean_str_list(payload.get("educationRequirements"))
        if parts:
            edu = "; ".join(parts[:5])

    tests = _normalize_tests(
        payload.get("standardizedTests") or payload.get("standardTestScores")
    )

    languages = _normalize_languages(
        payload.get("languages") or payload.get("languageLevels")
    )
    if not languages and _str_field(payload.get("languageLevel")):
        languages = [
            {
                "language": "general",
                "level": _str_field(payload.get("languageLevel")),
            }
        ]

    emp = _str_field(
        payload.get("employmentType")
        or payload.get("internOrJob")
        or payload.get("positionType")
    ).lower()
    if emp not in (
        "intern",
        "internship",
        "full_time_job",
        "full_time",
        "full-time",
        "part_time",
        "part-time",
        "contract",
        "unknown",
        "",
    ):
        emp = emp.replace(" ", "_")
    if emp in ("full-time",):
        emp = "full_time_job"
    if emp in ("part-time",):
        emp = "part_time"
    if emp == "internship":
        emp = "intern"
    if not emp:
        emp = "unknown"

    if emp == "intern":
        money = ""

    achievements = _clean_str_list(payload.get("achievements"))

    return {
        "skills": skills,
        "jobRole": job_role,
        "moneyEstimate": money,
        "duration": duration,
        "gpax": gpax,
        "educationLevel": edu,
        "standardizedTests": tests,
        "languages": languages,
        "employmentType": emp,
        "achievements": achievements,
    }


def metrics_document_for_prompt(is_resume: bool) -> str:
    schema = (
        '{"skills":[{"name":"","compatibilityLevel":"","evidence":""}],'
        '"jobRole":"","moneyEstimate":"","duration":"","gpax":"","educationLevel":"",'
        '"standardizedTests":[{"testName":"","normalizedScore":"","rawScore":"","grade":"","sourceText":""}],'
        '"languages":[{"language":"","level":""}],'
        '"employmentType":"","achievements":[]}'
    )
    ach_rule = (
        "achievements: short bullet strings from the resume (use [] for job descriptions)."
        if is_resume
        else "achievements: always []."
    )
    return (
        "Return only valid JSON with this exact top-level schema: "
        + schema
        + ". Rules: "
        "1) Evidence from the PDF only. "
        "2) skills[].compatibilityLevel: e.g. expert/proficient/familiar or years if stated. "
        "3) jobRole: target role/title (candidate aim on resume; role hired for on JD). "
        "4) moneyEstimate: salary/range if stated; MUST be empty string if employmentType is intern. "
        "5) duration: contract length, program length, notice period, or experience span text. "
        "6) gpax: overall GPA / CGPA if present. "
        "7) educationLevel: highest degree (e.g. BS Computer Science). "
        "8) standardizedTests: SAT/ACT/GRE/GMAT/TOEFL/IELTS; normalizedScore 0-100 when inferable, else empty. "
        "9) languages: spoken/written languages and CEFR/ILR level if given. "
        "10) employmentType: one of intern, full_time_job, part_time, contract, unknown. "
        f"11) {ach_rule} "
        "12) Empty strings/arrays when unknown. No markdown or extra keys."
    )