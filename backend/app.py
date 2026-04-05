# app.py

from typing import Any, Dict, List, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from resume_extraction import extract_resume_preview, ResumeExtractionError
from job_description_extraction import (
    extract_job_description_preview,
    JobDescriptionExtractionError,
)
from compatibility_metrics_schema import normalize_compatibility_metrics
from compatibility_score import CompareWeightsValidationError, compute_compatibility_breakdown
from db import (
    init_db,
    insert_resume,
    list_resumes_for_user,
    insert_job_description,
    list_job_descriptions_for_employer,
    insert_compatibility_metric_extraction,
    list_compatibility_metric_extractions,
    get_compatibility_metric_extraction_by_id,
    get_employer_metric_weights,
    upsert_employer_metric_weights,
    get_jd_skill_importance_map,
    replace_jd_skill_importance,
    list_skills_graph,
    list_skill_aliases,
    create_skill_unique,
    _normalize_hierarchy_kind,
    update_skill,
    delete_skill,
    add_skill_alias,
    delete_skill_alias,
    add_skill_hierarchy_link,
    remove_skill_hierarchy_link,
    get_app_user_by_email,
    insert_app_user,
    update_app_user_profile,
    app_user_email_exists,
    list_app_users_for_debug,
)
from seed_skills import run_seed as run_skill_seed
from prolog_meta import prolog_match_preview, PrologUnavailableError
from skill_normalize import to_slug

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

init_db()


def _legacy_standard_test_scores_from_metrics(tests: List[Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for t in tests or []:
        if not isinstance(t, dict):
            continue
        out.append(
            {
                "testName": t.get("testName", ""),
                "score": t.get("rawScore") or t.get("normalizedScore", ""),
                "grade": t.get("grade", ""),
                "sourceText": t.get("sourceText", ""),
            }
        )
    return out


def _parse_token_email(token: str) -> Optional[str]:
    """Extract email from token format token_<email>_<unix_ts>; supports underscores in email."""
    if not token or not isinstance(token, str):
        return None
    parts = token.split("_")
    if len(parts) < 3 or parts[0] != "token":
        return None
    try:
        float(parts[-1])
    except ValueError:
        return None
    email = "_".join(parts[1:-1])
    return email or None


def _email_from_bearer() -> Optional[str]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    email = _parse_token_email(token)
    if not email or not app_user_email_exists(email):
        return None
    return email


reset_tokens = {}
job_posts_db = {}
job_counter = 1

@app.route("/")
def home():
    return "Backend is running!"

@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        
        if not email or not password or not name:
            return jsonify({"message": "Email, password, and name are required"}), 400
        
        if app_user_email_exists(email):
            return jsonify({"message": "Email already exists"}), 400

        insert_app_user(email, password, name)
        
        # Generate fake token
        token = f"token_{email}_{datetime.now().timestamp()}"
        
        return jsonify({
            "token": token,
            "user": {
                "email": email,
                "name": name,
                "phone": '',
                "location": '',
                "bio": '',
                "skills": ''
            }
        }), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"message": "Email and password are required"}), 400
        
        user = get_app_user_by_email(email)
        if not user or user["password"] != password:
            return jsonify({"message": "Invalid email or password"}), 401
        
        # Generate fake token
        token = f"token_{email}_{datetime.now().timestamp()}"
        
        return jsonify({
            "token": token,
            "user": {
                "email": email,
                "name": user['name'],
                "phone": user['phone'],
                "location": user['location'],
                "bio": user['bio'],
                "skills": user['skills']
            }
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    try:
        data = request.json
        email = data.get('email')
        
        if not email:
            return jsonify({"message": "Email is required"}), 400
        
        if not app_user_email_exists(email):
            # For security, don't reveal if email exists
            return jsonify({"message": "If the email exists, a reset link has been sent"}), 200
        
        # In production: Generate secure token and send email
        reset_token = f"reset_{email}_{datetime.now().timestamp()}"
        reset_tokens[reset_token] = email
        
        return jsonify({"message": "If the email exists, a reset link has been sent"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/profile", methods=["GET"])
def get_profile():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Unauthorized"}), 401
        
        token = auth_header.split(" ", 1)[1].strip()
        email = _parse_token_email(token)
        if not email:
            return jsonify({"message": "Invalid token"}), 401

        user = get_app_user_by_email(email)
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        return jsonify({
            "user": {
                "email": email,
                "name": user['name'],
                "phone": user['phone'],
                "location": user['location'],
                "bio": user['bio'],
                "skills": user['skills']
            }
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/profile", methods=["PUT"])
def update_profile():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Unauthorized"}), 401
        
        token = auth_header.split(" ", 1)[1].strip()
        email = _parse_token_email(token)
        if not email:
            return jsonify({"message": "Invalid token"}), 401

        user = get_app_user_by_email(email)
        if not user:
            return jsonify({"message": "User not found"}), 404

        data = request.json
        update_app_user_profile(
            email,
            name=data.get("name", user["name"]),
            phone=data.get("phone", user["phone"]),
            location=data.get("location", user["location"]),
            bio=data.get("bio", user["bio"]),
            skills=data.get("skills", user["skills"]),
        )
        user = get_app_user_by_email(email)

        return jsonify({
            "user": {
                "email": email,
                "name": user["name"],
                "phone": user["phone"],
                "location": user["location"],
                "bio": user["bio"],
                "skills": user["skills"],
            }
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/match-jobs", methods=["GET"])
def match_jobs():
    return jsonify({"status": "ok"})

@app.route("/api/debug/users", methods=["GET"])
def get_all_users():
    """Debug endpoint - View all registered users (remove in production)"""
    rows = list_app_users_for_debug()
    return jsonify({"total_users": len(rows), "users": rows}), 200

@app.route("/api/job-posts", methods=["POST"])
def create_job_post():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Unauthorized"}), 401
        
        employer_email = _email_from_bearer()
        if not employer_email:
            return jsonify({"message": "Unauthorized"}), 401
        
        data = request.json
        global job_counter
        
        # Validate required fields
        if not data.get('position') or not data.get('company') or not data.get('location') or not data.get('description'):
            return jsonify({"message": "Missing required fields"}), 400
        
        job_post = {
            'id': job_counter,
            'employer_email': employer_email,
            'company': data.get('company'),
            'position': data.get('position'),
            'location': data.get('location'),
            'description': data.get('description'),
            'skills': data.get('skills', ''),
            'salary_min': data.get('salaryMin', ''),
            'salary_max': data.get('salaryMax', ''),
            'job_type': data.get('type', 'Full-time'),
            'openings': int(data.get('openings', 1)),
            'deadline': data.get('deadline', ''),
            'created_at': datetime.now().isoformat(),
            'applicants': 0
        }
        
        job_posts_db[job_counter] = job_post
        job_counter += 1
        
        return jsonify({
            "message": "Job post created successfully",
            "job": job_post
        }), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/job-posts", methods=["GET"])
def get_job_posts():
    try:
        # Return all job posts
        jobs_list = list(job_posts_db.values())
        return jsonify({
            "total": len(jobs_list),
            "jobs": jobs_list
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/debug/jobs", methods=["GET"])
def debug_get_jobs():
    """Debug endpoint - View all job posts"""
    return jsonify({
        "total_jobs": len(job_posts_db),
        "jobs": job_posts_db
    }), 200


@app.route("/api/resume/extract-preview", methods=["POST"])
def extract_resume():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Unauthorized"}), 401

        if "resume" not in request.files:
            return jsonify({"message": "Missing resume file"}), 400

        resume_file = request.files["resume"]
        if not resume_file or not resume_file.filename:
            return jsonify({"message": "Invalid file upload"}), 400

        if resume_file.mimetype != "application/pdf":
            return jsonify({"message": "Only PDF files are supported"}), 400

        pdf_bytes = resume_file.read()
        if not pdf_bytes:
            return jsonify({"message": "Uploaded file is empty"}), 400

        extraction_result = extract_resume_preview(pdf_bytes, mime_type=resume_file.mimetype)
        return jsonify(extraction_result), 200
    except ResumeExtractionError as exc:
        return jsonify({"message": str(exc)}), 502
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/job-description/extract-preview", methods=["POST"])
def extract_job_description():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401

        if "job_description" not in request.files:
            return jsonify({"message": "Missing job_description file"}), 400

        pdf_file = request.files["job_description"]
        if not pdf_file or not pdf_file.filename:
            return jsonify({"message": "Invalid file upload"}), 400

        if pdf_file.mimetype != "application/pdf":
            return jsonify({"message": "Only PDF files are supported"}), 400

        pdf_bytes = pdf_file.read()
        if not pdf_bytes:
            return jsonify({"message": "Uploaded file is empty"}), 400

        result = extract_job_description_preview(pdf_bytes, mime_type=pdf_file.mimetype)
        return jsonify(result), 200
    except JobDescriptionExtractionError as exc:
        return jsonify({"message": str(exc)}), 502
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/resumes", methods=["POST"])
def save_resume_extraction():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401

        data = request.get_json(silent=True) or {}
        ext = data.get("extraction") or data
        metrics = normalize_compatibility_metrics(ext)
        if not isinstance(metrics.get("skills"), list):
            return jsonify({"message": "Invalid body: skills must be an array"}), 400

        model = data.get("model")
        compat_id = insert_compatibility_metric_extraction(
            email, "resume", metrics, gemini_model=model
        )
        skill_names = [s.get("name", "") for s in metrics["skills"] if isinstance(s, dict)]
        resume_id = insert_resume(
            email,
            {
                "skills": skill_names,
                "achievements": metrics.get("achievements", []),
                "standardTestScores": _legacy_standard_test_scores_from_metrics(
                    metrics.get("standardizedTests")
                ),
            },
            gemini_model=model,
        )
        return jsonify(
            {
                "id": compat_id,
                "compatibility_metric_extraction_id": compat_id,
                "resume_id": resume_id,
                "message": "Resume extraction saved (compatibility metrics + legacy resume row)",
            }
        ), 201
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/resumes", methods=["GET"])
def list_resumes():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401

        rows = list_resumes_for_user(email)
        return jsonify({"total": len(rows), "resumes": rows}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/job-descriptions", methods=["POST"])
def save_job_description_extraction():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401

        data = request.get_json(silent=True) or {}
        ext = data.get("extraction") or data
        metrics = normalize_compatibility_metrics(ext)
        if not isinstance(metrics.get("skills"), list):
            return jsonify({"message": "Invalid body: skills must be an array"}), 400

        extras = {
            "location": ext.get("location") if isinstance(ext.get("location"), str) else "",
            "jobTitle": ext.get("jobTitle") if isinstance(ext.get("jobTitle"), str) else "",
            "yearsExperienceMin": ext.get("yearsExperienceMin")
            if isinstance(ext.get("yearsExperienceMin"), str)
            else str(ext.get("yearsExperienceMin") or ""),
            "yearsExperienceMax": ext.get("yearsExperienceMax")
            if isinstance(ext.get("yearsExperienceMax"), str)
            else str(ext.get("yearsExperienceMax") or ""),
            "educationRequirements": ext.get("educationRequirements", [])
            if isinstance(ext.get("educationRequirements"), list)
            else [],
            "certifications": ext.get("certifications", [])
            if isinstance(ext.get("certifications"), list)
            else [],
            "otherConsiderations": ext.get("otherConsiderations", [])
            if isinstance(ext.get("otherConsiderations"), list)
            else [],
        }

        model = data.get("model")
        compat_id = insert_compatibility_metric_extraction(
            email, "job_description", metrics, gemini_model=model, extras=extras
        )
        skill_names = [s.get("name", "") for s in metrics["skills"] if isinstance(s, dict)]
        normalized = {
            "jobTitle": metrics.get("jobRole") or extras["jobTitle"] or "",
            "location": extras["location"] or "",
            "yearsExperienceMin": extras["yearsExperienceMin"] or "",
            "yearsExperienceMax": extras["yearsExperienceMax"] or "",
            "skills": skill_names,
            "educationRequirements": extras["educationRequirements"],
            "certifications": extras["certifications"],
            "otherConsiderations": extras["otherConsiderations"],
        }

        row_id = insert_job_description(email, normalized, gemini_model=model)
        return jsonify(
            {
                "id": compat_id,
                "compatibility_metric_extraction_id": compat_id,
                "job_description_id": row_id,
                "message": "Job description extraction saved (compatibility metrics + legacy JD row)",
            }
        ), 201
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/compatibility-metric-extractions", methods=["GET"])
def list_compatibility_metric_extractions_route():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        rows = list_compatibility_metric_extractions(email)
        return jsonify({"total": len(rows), "extractions": rows}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/match/compatibility", methods=["POST"])
def match_compatibility():
    """
    Prolog-backed skill tree decay + employer metric weights. Requires the authenticated user
    to own both extractions (resume + job description) for this MVP.
    """
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        rid = data.get("resume_extraction_id")
        jid = data.get("job_extraction_id")
        if rid is None or jid is None:
            return jsonify(
                {"message": "resume_extraction_id and job_extraction_id are required"}
            ), 400
        try:
            rid = int(rid)
            jid = int(jid)
        except (TypeError, ValueError):
            return jsonify({"message": "extraction ids must be integers"}), 400

        resume = get_compatibility_metric_extraction_by_id(rid, user_email=email)
        job = get_compatibility_metric_extraction_by_id(jid, user_email=email)
        if not resume or not job:
            return jsonify({"message": "One or both extractions not found"}), 404
        if resume.get("source_type") != "resume":
            return jsonify({"message": "resume_extraction_id must be a resume extraction"}), 400
        if job.get("source_type") != "job_description":
            return jsonify({"message": "job_extraction_id must be a job description extraction"}), 400

        employer_email = job.get("user_email") or email
        compare_weights = data.get("compare_weights")
        try:
            result = compute_compatibility_breakdown(
                resume, job, employer_email, compare_weights
            )
        except CompareWeightsValidationError as exc:
            return jsonify({"message": str(exc)}), 400
        result["resume_extraction_id"] = rid
        result["job_extraction_id"] = jid
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/employer/compatibility-weights", methods=["GET", "PATCH"])
def employer_compatibility_weights_route():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        if request.method == "GET":
            row = get_employer_metric_weights(email)
            return jsonify(row), 200
        data = request.get_json(silent=True) or {}
        allowed = (
            "skill_pct",
            "job_pct",
            "money_pct",
            "duration_pct",
            "gpax_pct",
            "education_pct",
            "language_pct",
            "standardized_test_pct",
            "tree_decay_per_hop",
            "per_skill_weight_cap_multiplier",
        )
        kwargs = {k: data[k] for k in allowed if k in data}
        row = upsert_employer_metric_weights(email, **kwargs)
        return jsonify(row), 200
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route(
    "/api/compatibility-extractions/<int:extraction_id>/jd-skill-weights",
    methods=["GET", "PUT"],
)
def jd_skill_weights_route(extraction_id: int):
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        row = get_compatibility_metric_extraction_by_id(extraction_id, user_email=email)
        if not row:
            return jsonify({"message": "Extraction not found"}), 404
        if row.get("source_type") != "job_description":
            return jsonify({"message": "Not a job description extraction"}), 400
        if request.method == "GET":
            m = get_jd_skill_importance_map(extraction_id)
            return jsonify({"job_extraction_id": extraction_id, "weights": m}), 200
        data = request.get_json(silent=True) or {}
        weights = data.get("weights")
        if not isinstance(weights, dict):
            return jsonify({"message": "weights object required"}), 400
        clean: Dict[str, float] = {}
        for k, v in weights.items():
            try:
                clean[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        replace_jd_skill_importance(extraction_id, clean)
        return jsonify(
            {
                "job_extraction_id": extraction_id,
                "weights": get_jd_skill_importance_map(extraction_id),
                "message": "JD skill weights updated",
            }
        ), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/job-descriptions", methods=["GET"])
def list_job_descriptions():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401

        rows = list_job_descriptions_for_employer(email)
        return jsonify({"total": len(rows), "job_descriptions": rows}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills", methods=["POST"])
def create_skill():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        display_name = (data.get("display_name") or "").strip()
        raw_slug = (data.get("slug") or "").strip()
        slug = to_slug(raw_slug) if raw_slug else to_slug(display_name)
        if not slug:
            return jsonify({"message": "display_name or slug is required"}), 400
        parent_slug = data.get("parent_slug")
        if parent_slug is not None and isinstance(parent_slug, str):
            parent_slug = parent_slug.strip() or None
            if parent_slug:
                parent_slug = to_slug(parent_slug)
        else:
            parent_slug = None
        hk = _normalize_hierarchy_kind(data.get("hierarchy_kind"))
        row_id = create_skill_unique(
            slug,
            display_name or slug.replace("_", " ").title(),
            parent_slug=parent_slug,
            hierarchy_kind=hk,
        )
        return jsonify(
            {
                "id": row_id,
                "slug": slug,
                "hierarchy_kind": hk,
                "message": "Skill created",
            }
        ), 201
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/<skill_slug>", methods=["PATCH"])
def patch_skill(skill_slug):
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        canon_slug = to_slug(skill_slug)
        display_name = None
        if "display_name" in data:
            v = data.get("display_name")
            display_name = None if v is None else str(v).strip()
        hk_arg = None
        if "hierarchy_kind" in data:
            hk_arg = _normalize_hierarchy_kind(data.get("hierarchy_kind"))
        update_skill(
            canon_slug,
            display_name=display_name if "display_name" in data else None,
            hierarchy_kind=hk_arg,
        )
        return jsonify({"message": "Skill updated"}), 200
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/<skill_slug>/hierarchy", methods=["POST"])
def post_skill_hierarchy(skill_slug):
    """Add one hierarchy link. relation=parent: target_slug is a parent of this skill. relation=child: target is a child."""
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        relation = (data.get("relation") or "").strip().lower()
        raw_target = (data.get("target_slug") or "").strip()
        if relation not in ("parent", "child"):
            return jsonify({"message": "relation must be 'parent' or 'child'"}), 400
        if not raw_target:
            return jsonify({"message": "target_slug is required"}), 400
        canon = to_slug(skill_slug)
        target_slug = to_slug(raw_target)
        if relation == "parent":
            add_skill_hierarchy_link(target_slug, canon)
        else:
            add_skill_hierarchy_link(canon, target_slug)
        return jsonify({"message": "Hierarchy link added"}), 201
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/<skill_slug>/hierarchy", methods=["DELETE"])
def delete_skill_hierarchy(skill_slug):
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        relation = (request.args.get("relation") or "").strip().lower()
        raw_target = (request.args.get("target_slug") or "").strip()
        if relation not in ("parent", "child"):
            return jsonify({"message": "relation must be 'parent' or 'child'"}), 400
        if not raw_target:
            return jsonify({"message": "target_slug is required"}), 400
        canon = to_slug(skill_slug)
        target_slug = to_slug(raw_target)
        if relation == "parent":
            ok = remove_skill_hierarchy_link(target_slug, canon)
        else:
            ok = remove_skill_hierarchy_link(canon, target_slug)
        if not ok:
            return jsonify({"message": "Link not found"}), 404
        return jsonify({"message": "Hierarchy link removed"}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/<skill_slug>", methods=["DELETE"])
def remove_skill(skill_slug):
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        delete_skill(to_slug(skill_slug))
        return jsonify({"message": "Skill deleted"}), 200
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/aliases", methods=["POST"])
def create_skill_alias():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        alias_raw = (data.get("alias_slug") or data.get("alias") or "").strip()
        skill_raw = (data.get("skill_slug") or "").strip()
        if not alias_raw or not skill_raw:
            return jsonify({"message": "alias_slug and skill_slug are required"}), 400
        alias_slug = to_slug(alias_raw)
        skill_slug = to_slug(skill_raw)
        row_id = add_skill_alias(alias_slug, skill_slug)
        return jsonify({"id": row_id, "message": "Alias created"}), 201
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/aliases/<int:alias_id>", methods=["DELETE"])
def remove_skill_alias(alias_id):
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        if not delete_skill_alias(alias_id):
            return jsonify({"message": "Alias not found"}), 404
        return jsonify({"message": "Alias deleted"}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/graph", methods=["GET"])
def skills_graph():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        skills = list_skills_graph()
        aliases = list_skill_aliases()
        return jsonify({"skills": skills, "aliases": aliases}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/skills/seed", methods=["POST"])
def skills_seed():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        run_skill_seed()
        return jsonify({"message": "Skill hierarchy and aliases seeded"}), 200
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


@app.route("/api/match/prolog-preview", methods=["POST"])
def match_prolog_preview():
    try:
        email = _email_from_bearer()
        if not email:
            return jsonify({"message": "Unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        candidates = data.get("candidate_skills") or []
        required = data.get("required_skills") or []
        if not isinstance(candidates, list) or not isinstance(required, list):
            return jsonify({"message": "candidate_skills and required_skills must be arrays"}), 400
        explain = bool(data.get("explain"))
        result = prolog_match_preview(candidates, required, explain=explain)
        return jsonify(result), 200
    except PrologUnavailableError as exc:
        return jsonify({"message": str(exc)}), 503
    except Exception as exc:
        return jsonify({"message": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
