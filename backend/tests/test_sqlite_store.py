import importlib
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_sqlite_resume_and_job_roundtrip():
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".db").name
    os.environ["SQLITE_DB_PATH"] = path
    import db

    importlib.reload(db)
    db.init_db()

    rid = db.insert_resume(
        "user1",
        {
            "skills": ["A", "B"],
            "achievements": ["Won"],
            "standardTestScores": [{"testName": "GRE", "score": "320", "grade": "", "sourceText": ""}],
        },
        gemini_model="m1",
    )
    resumes = db.list_resumes_for_user("user1")
    assert len(resumes) == 1
    assert resumes[0]["id"] == rid
    assert resumes[0]["skills"] == ["A", "B"]

    jid = db.insert_job_description(
        "emp1",
        {
            "jobTitle": "Dev",
            "location": "SF",
            "yearsExperienceMin": "2",
            "yearsExperienceMax": "4",
            "skills": ["Go"],
            "educationRequirements": ["MS"],
            "certifications": [],
            "otherConsiderations": ["Travel"],
        },
        gemini_model="m2",
    )
    jobs = db.list_job_descriptions_for_employer("emp1")
    assert len(jobs) == 1
    assert jobs[0]["id"] == jid
    assert jobs[0]["skills"] == ["Go"]

    db.insert_app_user("compat_u", "pw", "Compat User")
    metrics = {
        "skills": [{"name": "Go", "compatibilityLevel": "expert", "evidence": "5y"}],
        "jobRole": "Backend",
        "moneyEstimate": "",
        "duration": "2y",
        "gpax": "3.6",
        "educationLevel": "MS CS",
        "standardizedTests": [
            {
                "testName": "GRE",
                "normalizedScore": "85",
                "rawScore": "320",
                "grade": "",
                "sourceText": "",
            }
        ],
        "languages": [{"language": "English", "level": "C1"}],
        "employmentType": "full_time_job",
        "achievements": ["Award"],
    }
    ceid = db.insert_compatibility_metric_extraction(
        "compat_u", "resume", metrics, gemini_model="gx"
    )
    listed = db.list_compatibility_metric_extractions("compat_u")
    assert len(listed) == 1
    assert listed[0]["id"] == ceid
    assert listed[0]["skills"][0]["name"] == "Go"
    assert listed[0]["standardizedTests"][0]["testName"] == "GRE"
    assert listed[0]["languages"][0]["language"] == "English"

    if os.path.exists(path):
        for _ in range(20):
            try:
                os.remove(path)
                break
            except PermissionError:
                time.sleep(0.05)
