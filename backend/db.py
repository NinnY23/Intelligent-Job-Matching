import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_PATH = os.environ.get(
    "SQLITE_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db"),
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _normalize_hierarchy_kind(raw: Any) -> str:
    if raw is None:
        return "skill"
    s = str(raw).strip().lower()
    if s in ("job", "jobs", "role", "job_title"):
        return "job"
    return "skill"


def _migrate_skills_hierarchy_kind(conn: sqlite3.Connection) -> None:
    """Add hierarchy_kind to skills when upgrading an older database."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(skills)").fetchall()]
    if "hierarchy_kind" in cols:
        return
    conn.execute(
        """
        ALTER TABLE skills ADD COLUMN hierarchy_kind TEXT NOT NULL DEFAULT 'skill'
        """
    )


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                achievements_json TEXT NOT NULL,
                standard_test_scores_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                gemini_model TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employer_email TEXT NOT NULL,
                job_title TEXT NOT NULL,
                location TEXT NOT NULL,
                years_experience_min TEXT NOT NULL,
                years_experience_max TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                education_requirements_json TEXT NOT NULL,
                certifications_json TEXT NOT NULL,
                other_considerations_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                gemini_model TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                display_name TEXT,
                parent_id INTEGER REFERENCES skills(id),
                hierarchy_kind TEXT NOT NULL DEFAULT 'skill'
                    CHECK (hierarchy_kind IN ('skill', 'job'))
            )
            """
        )
        _migrate_skills_hierarchy_kind(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_slug TEXT UNIQUE NOT NULL,
                skill_id INTEGER NOT NULL REFERENCES skills(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_hierarchy_edges (
                parent_id INTEGER NOT NULL,
                child_id INTEGER NOT NULL,
                PRIMARY KEY (parent_id, child_id),
                FOREIGN KEY (parent_id) REFERENCES skills(id) ON DELETE CASCADE,
                FOREIGN KEY (child_id) REFERENCES skills(id) ON DELETE CASCADE,
                CHECK (parent_id != child_id)
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO skill_hierarchy_edges (parent_id, child_id)
            SELECT parent_id, id FROM skills WHERE parent_id IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                email TEXT PRIMARY KEY NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                bio TEXT NOT NULL DEFAULT '',
                skills TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compatibility_metric_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                source_type TEXT NOT NULL CHECK (source_type IN ('resume', 'job_description')),
                created_at TEXT NOT NULL,
                gemini_model TEXT,
                job_role TEXT NOT NULL DEFAULT '',
                money_estimate TEXT NOT NULL DEFAULT '',
                duration_text TEXT NOT NULL DEFAULT '',
                gpax TEXT NOT NULL DEFAULT '',
                education_level TEXT NOT NULL DEFAULT '',
                employment_type TEXT NOT NULL DEFAULT '',
                achievements_json TEXT NOT NULL DEFAULT '[]',
                raw_payload_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (user_email) REFERENCES app_users(email) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compatibility_metric_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                compatibility_level TEXT NOT NULL DEFAULT '',
                evidence TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (extraction_id) REFERENCES compatibility_metric_extractions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compatibility_metric_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id INTEGER NOT NULL,
                test_name TEXT NOT NULL,
                normalized_score TEXT NOT NULL DEFAULT '',
                raw_score TEXT NOT NULL DEFAULT '',
                grade TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (extraction_id) REFERENCES compatibility_metric_extractions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compatibility_metric_languages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                proficiency_level TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (extraction_id) REFERENCES compatibility_metric_extractions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employer_compatibility_weights (
                employer_email TEXT PRIMARY KEY NOT NULL,
                skill_pct REAL NOT NULL DEFAULT 35,
                job_pct REAL NOT NULL DEFAULT 10,
                money_pct REAL NOT NULL DEFAULT 5,
                duration_pct REAL NOT NULL DEFAULT 10,
                gpax_pct REAL NOT NULL DEFAULT 10,
                education_pct REAL NOT NULL DEFAULT 0,
                language_pct REAL NOT NULL DEFAULT 15,
                standardized_test_pct REAL NOT NULL DEFAULT 15,
                tree_decay_per_hop REAL NOT NULL DEFAULT 0.7,
                per_skill_weight_cap_multiplier REAL NOT NULL DEFAULT 1.5,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (employer_email) REFERENCES app_users(email) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jd_skill_importance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_extraction_id INTEGER NOT NULL,
                skill_slug TEXT NOT NULL,
                relative_weight REAL NOT NULL DEFAULT 1.0,
                FOREIGN KEY (job_extraction_id) REFERENCES compatibility_metric_extractions(id) ON DELETE CASCADE,
                UNIQUE (job_extraction_id, skill_slug)
            )
            """
        )
        conn.commit()
    ensure_default_dev_user()


def ensure_default_dev_user() -> None:
    """Create a local dev account if the database has no users (survives server restarts)."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM app_users").fetchone()
        if int(row["c"]) > 0:
            return
        conn.execute(
            "INSERT INTO app_users (email, password, name) VALUES (?, ?, ?)",
            ("dev@localhost", "dev", "Dev user"),
        )
        conn.commit()


def get_app_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT email, password, name, phone, location, bio, skills
            FROM app_users WHERE email = ?
            """,
            (email,),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def app_user_email_exists(email: str) -> bool:
    return get_app_user_by_email(email) is not None


def insert_app_user(
    email: str,
    password: str,
    name: str,
    phone: str = "",
    location: str = "",
    bio: str = "",
    skills: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_users (email, password, name, phone, location, bio, skills)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (email, password, name, phone, location, bio, skills),
        )
        conn.commit()


def update_app_user_profile(
    email: str,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
    bio: Optional[str] = None,
    skills: Optional[str] = None,
) -> None:
    user = get_app_user_by_email(email)
    if not user:
        raise ValueError("User not found")
    n = name if name is not None else user["name"]
    p = phone if phone is not None else user["phone"]
    loc = location if location is not None else user["location"]
    b = bio if bio is not None else user["bio"]
    sk = skills if skills is not None else user["skills"]
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE app_users
            SET name = ?, phone = ?, location = ?, bio = ?, skills = ?
            WHERE email = ?
            """,
            (n, p, loc, b, sk, email),
        )
        conn.commit()


def list_app_users_for_debug() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT email, name, phone, location, bio, skills FROM app_users ORDER BY email"
        ).fetchall()
    return [dict(r) for r in rows]


def insert_compatibility_metric_extraction(
    user_email: str,
    source_type: str,
    metrics: Dict[str, Any],
    gemini_model: Optional[str] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist 9-metric extraction; source_type is resume or job_description."""
    if source_type not in ("resume", "job_description"):
        raise ValueError("source_type must be resume or job_description")
    created = datetime.now(timezone.utc).isoformat()
    full_blob: Dict[str, Any] = {
        "skills": metrics.get("skills") or [],
        "jobRole": metrics.get("jobRole") or "",
        "moneyEstimate": metrics.get("moneyEstimate") or "",
        "duration": metrics.get("duration") or "",
        "gpax": metrics.get("gpax") or "",
        "educationLevel": metrics.get("educationLevel") or "",
        "standardizedTests": metrics.get("standardizedTests") or [],
        "languages": metrics.get("languages") or [],
        "employmentType": metrics.get("employmentType") or "",
        "achievements": metrics.get("achievements") or [],
    }
    if extras:
        full_blob["_extras"] = extras
    raw_json = json.dumps(full_blob, ensure_ascii=False)
    achievements_json = json.dumps(full_blob["achievements"], ensure_ascii=False)
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO compatibility_metric_extractions (
                user_email, source_type, created_at, gemini_model,
                job_role, money_estimate, duration_text, gpax, education_level,
                employment_type, achievements_json, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_email,
                source_type,
                created,
                gemini_model,
                full_blob["jobRole"],
                full_blob["moneyEstimate"],
                full_blob["duration"],
                full_blob["gpax"],
                full_blob["educationLevel"],
                full_blob["employmentType"],
                achievements_json,
                raw_json,
            ),
        )
        eid = int(cur.lastrowid)
        for i, sk in enumerate(full_blob["skills"]):
            if not isinstance(sk, dict):
                continue
            conn.execute(
                """
                INSERT INTO compatibility_metric_skills (
                    extraction_id, skill_name, compatibility_level, evidence, sort_order
                ) VALUES (?,?,?,?,?)
                """,
                (
                    eid,
                    str(sk.get("name", "")).strip(),
                    str(sk.get("compatibilityLevel", "")).strip(),
                    str(sk.get("evidence", "")).strip(),
                    i,
                ),
            )
        for i, t in enumerate(full_blob["standardizedTests"]):
            if not isinstance(t, dict):
                continue
            conn.execute(
                """
                INSERT INTO compatibility_metric_tests (
                    extraction_id, test_name, normalized_score, raw_score, grade,
                    source_text, sort_order
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    eid,
                    str(t.get("testName", "")).strip(),
                    str(t.get("normalizedScore", "")).strip(),
                    str(t.get("rawScore", "")).strip(),
                    str(t.get("grade", "")).strip(),
                    str(t.get("sourceText", "")).strip(),
                    i,
                ),
            )
        for i, lang in enumerate(full_blob["languages"]):
            if not isinstance(lang, dict):
                continue
            conn.execute(
                """
                INSERT INTO compatibility_metric_languages (
                    extraction_id, language, proficiency_level, sort_order
                ) VALUES (?,?,?,?)
                """,
                (
                    eid,
                    str(lang.get("language", "")).strip(),
                    str(lang.get("level", "")).strip(),
                    i,
                ),
            )
        conn.commit()
    return eid


def _hydrate_compatibility_extraction(conn: sqlite3.Connection, d: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(d)
    eid = int(row["id"])
    row["achievements"] = json.loads(row["achievements_json"] or "[]")
    del row["achievements_json"]
    sk_rows = conn.execute(
        """
        SELECT skill_name, compatibility_level, evidence
        FROM compatibility_metric_skills
        WHERE extraction_id = ?
        ORDER BY sort_order, id
        """,
        (eid,),
    ).fetchall()
    row["skills"] = [
        {
            "name": sr["skill_name"],
            "compatibilityLevel": sr["compatibility_level"],
            "evidence": sr["evidence"],
        }
        for sr in sk_rows
    ]
    t_rows = conn.execute(
        """
        SELECT test_name, normalized_score, raw_score, grade, source_text
        FROM compatibility_metric_tests
        WHERE extraction_id = ?
        ORDER BY sort_order, id
        """,
        (eid,),
    ).fetchall()
    row["standardizedTests"] = [
        {
            "testName": tr["test_name"],
            "normalizedScore": tr["normalized_score"],
            "rawScore": tr["raw_score"],
            "grade": tr["grade"],
            "sourceText": tr["source_text"],
        }
        for tr in t_rows
    ]
    lr = conn.execute(
        """
        SELECT language, proficiency_level
        FROM compatibility_metric_languages
        WHERE extraction_id = ?
        ORDER BY sort_order, id
        """,
        (eid,),
    ).fetchall()
    row["languages"] = [
        {"language": x["language"], "level": x["proficiency_level"]} for x in lr
    ]
    row["jobRole"] = row.pop("job_role")
    row["moneyEstimate"] = row.pop("money_estimate")
    row["duration"] = row.pop("duration_text")
    row["educationLevel"] = row.pop("education_level")
    row["employmentType"] = row.pop("employment_type")
    return row


def get_compatibility_metric_extraction_by_id(
    extraction_id: int, user_email: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        if user_email:
            r = conn.execute(
                """
                SELECT id, user_email, source_type, created_at, gemini_model,
                       job_role, money_estimate, duration_text, gpax, education_level,
                       employment_type, achievements_json, raw_payload_json
                FROM compatibility_metric_extractions
                WHERE id = ? AND user_email = ?
                """,
                (extraction_id, user_email),
            ).fetchone()
        else:
            r = conn.execute(
                """
                SELECT id, user_email, source_type, created_at, gemini_model,
                       job_role, money_estimate, duration_text, gpax, education_level,
                       employment_type, achievements_json, raw_payload_json
                FROM compatibility_metric_extractions
                WHERE id = ?
                """,
                (extraction_id,),
            ).fetchone()
        if not r:
            return None
        return _hydrate_compatibility_extraction(conn, dict(r))


def list_compatibility_metric_extractions(
    user_email: str, limit: int = 100
) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_email, source_type, created_at, gemini_model,
                   job_role, money_estimate, duration_text, gpax, education_level,
                   employment_type, achievements_json, raw_payload_json
            FROM compatibility_metric_extractions
            WHERE user_email = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_email, limit),
        ).fetchall()
        return [_hydrate_compatibility_extraction(conn, dict(r)) for r in rows]


DEFAULT_EMPLOYER_METRIC_WEIGHTS: Dict[str, float] = {
    "skill_pct": 35.0,
    "job_pct": 10.0,
    "money_pct": 5.0,
    "duration_pct": 10.0,
    "gpax_pct": 10.0,
    "education_pct": 0.0,
    "language_pct": 15.0,
    "standardized_test_pct": 15.0,
    "tree_decay_per_hop": 0.7,
    "per_skill_weight_cap_multiplier": 1.5,
}


def _ensure_employer_weights_row(conn: sqlite3.Connection, employer_email: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM employer_compatibility_weights WHERE employer_email = ?",
        (employer_email,),
    ).fetchone()
    if row:
        return row
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO employer_compatibility_weights (
            employer_email, skill_pct, job_pct, money_pct, duration_pct, gpax_pct,
            education_pct, language_pct, standardized_test_pct,
            tree_decay_per_hop, per_skill_weight_cap_multiplier, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            employer_email,
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["skill_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["job_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["money_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["duration_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["gpax_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["education_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["language_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["standardized_test_pct"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["tree_decay_per_hop"],
            DEFAULT_EMPLOYER_METRIC_WEIGHTS["per_skill_weight_cap_multiplier"],
            now,
        ),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM employer_compatibility_weights WHERE employer_email = ?",
        (employer_email,),
    ).fetchone()


def get_employer_metric_weights(employer_email: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = _ensure_employer_weights_row(conn, employer_email)
        return dict(row)


def upsert_employer_metric_weights(
    employer_email: str,
    skill_pct: Optional[float] = None,
    job_pct: Optional[float] = None,
    money_pct: Optional[float] = None,
    duration_pct: Optional[float] = None,
    gpax_pct: Optional[float] = None,
    education_pct: Optional[float] = None,
    language_pct: Optional[float] = None,
    standardized_test_pct: Optional[float] = None,
    tree_decay_per_hop: Optional[float] = None,
    per_skill_weight_cap_multiplier: Optional[float] = None,
) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = dict(_ensure_employer_weights_row(conn, employer_email))
        updates = {
            "skill_pct": skill_pct,
            "job_pct": job_pct,
            "money_pct": money_pct,
            "duration_pct": duration_pct,
            "gpax_pct": gpax_pct,
            "education_pct": education_pct,
            "language_pct": language_pct,
            "standardized_test_pct": standardized_test_pct,
            "tree_decay_per_hop": tree_decay_per_hop,
            "per_skill_weight_cap_multiplier": per_skill_weight_cap_multiplier,
        }
        for k, v in updates.items():
            if v is not None:
                if isinstance(v, (int, float)) and v < 0:
                    raise ValueError(f"{k} must be non-negative")
                cur[k] = float(v)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            UPDATE employer_compatibility_weights SET
                skill_pct = ?, job_pct = ?, money_pct = ?, duration_pct = ?, gpax_pct = ?,
                education_pct = ?, language_pct = ?, standardized_test_pct = ?,
                tree_decay_per_hop = ?, per_skill_weight_cap_multiplier = ?, updated_at = ?
            WHERE employer_email = ?
            """,
            (
                cur["skill_pct"],
                cur["job_pct"],
                cur["money_pct"],
                cur["duration_pct"],
                cur["gpax_pct"],
                cur["education_pct"],
                cur["language_pct"],
                cur["standardized_test_pct"],
                cur["tree_decay_per_hop"],
                cur["per_skill_weight_cap_multiplier"],
                now,
                employer_email,
            ),
        )
        conn.commit()
        return dict(
            conn.execute(
                "SELECT * FROM employer_compatibility_weights WHERE employer_email = ?",
                (employer_email,),
            ).fetchone()
        )


def get_jd_skill_importance_map(job_extraction_id: int) -> Dict[str, float]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT skill_slug, relative_weight
            FROM jd_skill_importance
            WHERE job_extraction_id = ?
            """,
            (job_extraction_id,),
        ).fetchall()
    return {str(r["skill_slug"]): float(r["relative_weight"]) for r in rows if r["skill_slug"]}


def replace_jd_skill_importance(job_extraction_id: int, weights: Dict[str, float]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM jd_skill_importance WHERE job_extraction_id = ?", (job_extraction_id,))
        for slug, w in weights.items():
            s = str(slug).strip()
            if not s or float(w) <= 0:
                continue
            conn.execute(
                """
                INSERT INTO jd_skill_importance (job_extraction_id, skill_slug, relative_weight)
                VALUES (?,?,?)
                """,
                (job_extraction_id, s, float(w)),
            )
        conn.commit()


def insert_resume(
    user_email: str,
    extraction: Dict[str, Any],
    gemini_model: Optional[str] = None,
) -> int:
    skills = extraction.get("skills", [])
    achievements = extraction.get("achievements", [])
    scores = extraction.get("standardTestScores", [])
    created = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO resumes (
                user_email, skills_json, achievements_json, standard_test_scores_json,
                created_at, gemini_model
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_email,
                json.dumps(skills),
                json.dumps(achievements),
                json.dumps(scores),
                created,
                gemini_model,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_resumes_for_user(user_email: str, limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_email, skills_json, achievements_json, standard_test_scores_json,
                   created_at, gemini_model
            FROM resumes
            WHERE user_email = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_email, limit),
        ).fetchall()
    return [_row_to_resume_dict(r) for r in rows]


def _row_to_resume_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_email": row["user_email"],
        "skills": json.loads(row["skills_json"]),
        "achievements": json.loads(row["achievements_json"]),
        "standardTestScores": json.loads(row["standard_test_scores_json"]),
        "created_at": row["created_at"],
        "gemini_model": row["gemini_model"],
    }


def insert_job_description(
    employer_email: str,
    extraction: Dict[str, Any],
    gemini_model: Optional[str] = None,
) -> int:
    created = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO job_descriptions (
                employer_email, job_title, location, years_experience_min, years_experience_max,
                skills_json, education_requirements_json, certifications_json,
                other_considerations_json, created_at, gemini_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employer_email,
                extraction.get("jobTitle") or "",
                extraction.get("location") or "",
                extraction.get("yearsExperienceMin") or "",
                extraction.get("yearsExperienceMax") or "",
                json.dumps(extraction.get("skills", [])),
                json.dumps(extraction.get("educationRequirements", [])),
                json.dumps(extraction.get("certifications", [])),
                json.dumps(extraction.get("otherConsiderations", [])),
                created,
                gemini_model,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_job_descriptions_for_employer(employer_email: str, limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, employer_email, job_title, location, years_experience_min, years_experience_max,
                   skills_json, education_requirements_json, certifications_json,
                   other_considerations_json, created_at, gemini_model
            FROM job_descriptions
            WHERE employer_email = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (employer_email, limit),
        ).fetchall()
    return [_row_to_job_dict(r) for r in rows]


def _row_to_job_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "employer_email": row["employer_email"],
        "jobTitle": row["job_title"],
        "location": row["location"],
        "yearsExperienceMin": row["years_experience_min"],
        "yearsExperienceMax": row["years_experience_max"],
        "skills": json.loads(row["skills_json"]),
        "educationRequirements": json.loads(row["education_requirements_json"]),
        "certifications": json.loads(row["certifications_json"]),
        "otherConsiderations": json.loads(row["other_considerations_json"]),
        "created_at": row["created_at"],
        "gemini_model": row["gemini_model"],
    }


def get_skill_by_slug(conn: sqlite3.Connection, slug: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT id FROM skills WHERE slug = ?", (slug,)).fetchone()


def _edge_exists(conn: sqlite3.Connection, parent_id: int, child_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM skill_hierarchy_edges WHERE parent_id = ? AND child_id = ?",
        (parent_id, child_id),
    ).fetchone()
    return row is not None


def _would_create_cycle(conn: sqlite3.Connection, parent_id: int, child_id: int) -> bool:
    """True if child_id can reach parent_id via existing parent->child edges (before adding the new edge)."""
    if parent_id == child_id:
        return True
    stack = [child_id]
    seen = set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for r in conn.execute(
            "SELECT child_id FROM skill_hierarchy_edges WHERE parent_id = ?", (cur,)
        ):
            cid = int(r["child_id"])
            if cid == parent_id:
                return True
            stack.append(cid)
    return False


def _insert_hierarchy_edge(
    conn: sqlite3.Connection, parent_id: int, child_id: int
) -> None:
    if parent_id == child_id:
        raise ValueError("Skill cannot be its own parent")
    if _edge_exists(conn, parent_id, child_id):
        return
    if _would_create_cycle(conn, parent_id, child_id):
        raise ValueError("Cannot add hierarchy link: would create a cycle")
    conn.execute(
        "INSERT INTO skill_hierarchy_edges (parent_id, child_id) VALUES (?, ?)",
        (parent_id, child_id),
    )


def add_skill_hierarchy_link(parent_slug: str, child_slug: str) -> None:
    """Directed edge: parent_slug is a parent of child_slug (multi-parent / multi-child supported)."""
    ps = parent_slug.strip()
    cs = child_slug.strip()
    if not ps or not cs:
        raise ValueError("parent and child slugs are required")
    with get_connection() as conn:
        prow = get_skill_by_slug(conn, ps)
        crow = get_skill_by_slug(conn, cs)
        if not prow:
            raise ValueError(f"Parent skill not found: {ps}")
        if not crow:
            raise ValueError(f"Child skill not found: {cs}")
        pid, cid = int(prow["id"]), int(crow["id"])
        _insert_hierarchy_edge(conn, pid, cid)
        conn.commit()


def remove_skill_hierarchy_link(parent_slug: str, child_slug: str) -> bool:
    """Remove one parent/child edge. Returns True if a row was deleted."""
    with get_connection() as conn:
        prow = get_skill_by_slug(conn, parent_slug.strip())
        crow = get_skill_by_slug(conn, child_slug.strip())
        if not prow or not crow:
            return False
        cur = conn.execute(
            """
            DELETE FROM skill_hierarchy_edges
            WHERE parent_id = ? AND child_id = ?
            """,
            (int(prow["id"]), int(crow["id"])),
        )
        conn.commit()
        return cur.rowcount > 0


def ensure_skill(
    slug: str,
    display_name: str,
    parent_slug: Optional[str] = None,
    hierarchy_kind: str = "skill",
) -> int:
    """Insert skill if missing; return id. Optional single parent edge if parent_slug set."""
    hk = _normalize_hierarchy_kind(hierarchy_kind)
    with get_connection() as conn:
        row = get_skill_by_slug(conn, slug)
        if row:
            return int(row["id"])
        cur = conn.execute(
            """
            INSERT INTO skills (slug, display_name, parent_id, hierarchy_kind)
            VALUES (?, ?, NULL, ?)
            """,
            (slug, display_name or slug, hk),
        )
        sid = int(cur.lastrowid)
        if parent_slug:
            if parent_slug == slug:
                raise ValueError("Skill cannot be its own parent")
            prow = get_skill_by_slug(conn, parent_slug)
            if not prow:
                raise ValueError(f"Parent skill not found: {parent_slug}")
            _insert_hierarchy_edge(conn, int(prow["id"]), sid)
        conn.commit()
        return sid


def create_skill_unique(
    slug: str,
    display_name: str,
    parent_slug: Optional[str] = None,
    hierarchy_kind: str = "skill",
) -> int:
    """Insert a new skill; raises ValueError if slug already exists."""
    hk = _normalize_hierarchy_kind(hierarchy_kind)
    with get_connection() as conn:
        if get_skill_by_slug(conn, slug):
            raise ValueError(f"Skill slug already exists: {slug}")
        cur = conn.execute(
            """
            INSERT INTO skills (slug, display_name, parent_id, hierarchy_kind)
            VALUES (?, ?, NULL, ?)
            """,
            (slug, display_name or slug, hk),
        )
        sid = int(cur.lastrowid)
        if parent_slug:
            if parent_slug == slug:
                raise ValueError("Skill cannot be its own parent")
            prow = get_skill_by_slug(conn, parent_slug)
            if not prow:
                raise ValueError(f"Parent skill not found: {parent_slug}")
            _insert_hierarchy_edge(conn, int(prow["id"]), sid)
        conn.commit()
        return sid


def update_skill(
    slug: str,
    display_name: Optional[str] = None,
    hierarchy_kind: Optional[str] = None,
) -> bool:
    """Update display_name and/or hierarchy_kind (skill vs job node)."""
    with get_connection() as conn:
        row = get_skill_by_slug(conn, slug)
        if not row:
            raise ValueError(f"Skill not found: {slug}")
        sets: List[str] = []
        vals: List[Any] = []
        if display_name is not None:
            sets.append("display_name = ?")
            vals.append(display_name)
        if hierarchy_kind is not None:
            hk = _normalize_hierarchy_kind(hierarchy_kind)
            if hk not in ("skill", "job"):
                raise ValueError("hierarchy_kind must be skill or job")
            sets.append("hierarchy_kind = ?")
            vals.append(hk)
        if not sets:
            return True
        vals.append(slug)
        conn.execute(
            f"UPDATE skills SET {', '.join(sets)} WHERE slug = ?",
            vals,
        )
        conn.commit()
        return True


def delete_skill(slug: str) -> None:
    """Delete skill if it has no children in hierarchy edges; removes aliases first."""
    with get_connection() as conn:
        row = get_skill_by_slug(conn, slug)
        if not row:
            raise ValueError(f"Skill not found: {slug}")
        sid = int(row["id"])
        child = conn.execute(
            "SELECT COUNT(*) AS c FROM skill_hierarchy_edges WHERE parent_id = ?",
            (sid,),
        ).fetchone()
        if child and int(child["c"]) > 0:
            raise ValueError(
                "Cannot delete skill that has child skills; remove child links first"
            )
        conn.execute("DELETE FROM skill_aliases WHERE skill_id = ?", (sid,))
        conn.execute("DELETE FROM skills WHERE id = ?", (sid,))
        conn.commit()


def delete_skill_alias(alias_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM skill_aliases WHERE id = ?", (alias_id,))
        conn.commit()
        return cur.rowcount > 0


def add_skill_alias(alias_slug: str, skill_slug: str) -> int:
    with get_connection() as conn:
        skill = get_skill_by_slug(conn, skill_slug)
        if not skill:
            raise ValueError(f"Skill not found: {skill_slug}")
        sid = int(skill["id"])
        conn.execute(
            "INSERT OR IGNORE INTO skill_aliases (alias_slug, skill_id) VALUES (?, ?)",
            (alias_slug, sid),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM skill_aliases WHERE alias_slug = ?", (alias_slug,)
        ).fetchone()
        return int(row["id"]) if row else -1


def list_skills_graph() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        skills_rows = conn.execute(
            """
            SELECT id, slug, display_name,
                   COALESCE(hierarchy_kind, 'skill') AS hierarchy_kind
            FROM skills ORDER BY slug
            """
        ).fetchall()
        edge_rows = conn.execute(
            """
            SELECT e.parent_id, e.child_id,
                   p.slug AS parent_slug, p.display_name AS parent_display,
                   c.slug AS child_slug, c.display_name AS child_display
            FROM skill_hierarchy_edges e
            JOIN skills p ON e.parent_id = p.id
            JOIN skills c ON e.child_id = c.id
            """
        ).fetchall()
    parents_of: Dict[int, List[Dict[str, str]]] = {}
    children_of: Dict[int, List[Dict[str, str]]] = {}
    for r in edge_rows:
        cid = int(r["child_id"])
        pid = int(r["parent_id"])
        plabel = (r["parent_display"] or r["parent_slug"] or "").strip() or r["parent_slug"]
        clabel = (r["child_display"] or r["child_slug"] or "").strip() or r["child_slug"]
        parents_of.setdefault(cid, []).append(
            {"slug": r["parent_slug"], "label": plabel}
        )
        children_of.setdefault(pid, []).append(
            {"slug": r["child_slug"], "label": clabel}
        )
    out: List[Dict[str, Any]] = []
    for s in skills_rows:
        sid = int(s["id"])
        out.append(
            {
                "id": sid,
                "slug": s["slug"],
                "display_name": s["display_name"],
                "hierarchy_kind": str(s["hierarchy_kind"] or "skill"),
                "parents": parents_of.get(sid, []),
                "children": children_of.get(sid, []),
            }
        )
    return out


def list_skill_aliases() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.alias_slug, a.skill_id, s.slug AS skill_slug
            FROM skill_aliases a
            JOIN skills s ON a.skill_id = s.id
            ORDER BY a.alias_slug
            """
        ).fetchall()
    return [
        {
            "id": r["id"],
            "alias_slug": r["alias_slug"],
            "skill_id": r["skill_id"],
            "skill_slug": r["skill_slug"],
        }
        for r in rows
    ]


def fetch_prolog_skill_facts() -> Dict[str, List[tuple]]:
    """Rows for asserting Prolog dynamic facts."""
    with get_connection() as conn:
        skills = conn.execute("SELECT slug FROM skills ORDER BY id").fetchall()
        known = [(r["slug"],) for r in skills]
        subskill_rows = conn.execute(
            """
            SELECT c.slug AS child_slug, p.slug AS parent_slug
            FROM skill_hierarchy_edges e
            JOIN skills p ON e.parent_id = p.id
            JOIN skills c ON e.child_id = c.id
            """
        ).fetchall()
        subskill_edges = [(r["child_slug"], r["parent_slug"]) for r in subskill_rows]
        aliases = conn.execute(
            """
            SELECT a.alias_slug, s.slug
            FROM skill_aliases a
            JOIN skills s ON a.skill_id = s.id
            """
        ).fetchall()
        alias_pairs = [(row["alias_slug"], row["slug"]) for row in aliases]
    return {
        "known_skill": known,
        "subskill_child_parent": subskill_edges,
        "alias_alias_to_canonical": alias_pairs,
    }
