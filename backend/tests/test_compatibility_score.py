import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import app as backend_app
from compatibility_score import (
    CompareWeightsValidationError,
    _normalize_weight_fractions,
    compute_compatibility_breakdown,
    resolve_compare_weights_from_payload,
    score_job_role,
)
from prolog_meta import prolog_compound_tree_factor


def test_normalize_weight_fractions_intern_redistributes_money():
    w = {
        "skill_pct": 35.0,
        "job_pct": 10.0,
        "money_pct": 5.0,
        "duration_pct": 10.0,
        "gpax_pct": 10.0,
        "education_pct": 0.0,
        "language_pct": 15.0,
        "standardized_test_pct": 15.0,
    }
    fr = _normalize_weight_fractions(w, job_is_intern=True)
    assert fr["money_pct"] == 0.0
    assert abs(sum(fr.values()) - 1.0) < 1e-6


def test_score_job_role_partial():
    assert score_job_role("Software Engineer", "Senior Software Engineer") > 0.5


def test_prolog_compound_tree_factor_fallback():
    """Python fallback must match 0.7**3 when Prolog is absent or query fails."""
    v = prolog_compound_tree_factor(3, 0.7)
    assert abs(v - 0.7**3) < 1e-9


def test_compute_compatibility_monkeypatched_graph(monkeypatch):
    monkeypatch.setattr(
        "compatibility_score.get_employer_metric_weights",
        lambda _email: {
            "skill_pct": 100.0,
            "job_pct": 0.0,
            "money_pct": 0.0,
            "duration_pct": 0.0,
            "gpax_pct": 0.0,
            "education_pct": 0.0,
            "language_pct": 0.0,
            "standardized_test_pct": 0.0,
            "tree_decay_per_hop": 0.7,
            "per_skill_weight_cap_multiplier": 1.5,
        },
    )
    monkeypatch.setattr("compatibility_score.get_jd_skill_importance_map", lambda _jid: {})
    monkeypatch.setattr("compatibility_score.reload_facts_from_db", lambda: None)

    def fake_load_graph():
        adj = {
            "javascript": {"react"},
            "react": {"javascript"},
        }
        alias = {}
        known = {"javascript", "react"}
        parent_of = {"react": "javascript"}
        return adj, alias, known, parent_of

    monkeypatch.setattr("compatibility_score.load_skill_graph", fake_load_graph)
    monkeypatch.setattr("compatibility_score.query_covers", lambda _c, _r: False)

    job = {
        "id": 9,
        "user_email": "e@test.com",
        "source_type": "job_description",
        "skills": [{"name": "react", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    resume = {
        "id": 8,
        "user_email": "e@test.com",
        "source_type": "resume",
        "skills": [{"name": "javascript", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    out = compute_compatibility_breakdown(resume, job, "e@test.com")
    assert "compatibility_percent" in out
    assert out["skill_details"]
    assert out["skill_details"][0]["graph_hops_to_nearest_resume_skill"] == 1
    assert out["skill_details"][0]["resume_match_skill_slug"] == "javascript"
    assert out["skill_details"][0]["tree_upward_hops_for_decay"] == 1
    assert abs(out["skill_details"][0]["tree_decay_factor"] - 0.7) < 1e-6
    assert 40.0 < out["compatibility_percent"] < 80.0


def test_directional_decay_resume_child_full_credit(monkeypatch):
    """JD general skill vs resume specialization: no decay (1×), not 0.7 per hop."""
    monkeypatch.setattr(
        "compatibility_score.get_employer_metric_weights",
        lambda _email: {
            "skill_pct": 100.0,
            "job_pct": 0.0,
            "money_pct": 0.0,
            "duration_pct": 0.0,
            "gpax_pct": 0.0,
            "education_pct": 0.0,
            "language_pct": 0.0,
            "standardized_test_pct": 0.0,
            "tree_decay_per_hop": 0.7,
            "per_skill_weight_cap_multiplier": 1.5,
        },
    )
    monkeypatch.setattr("compatibility_score.get_jd_skill_importance_map", lambda _jid: {})
    monkeypatch.setattr("compatibility_score.reload_facts_from_db", lambda: None)

    def fake_load_graph():
        adj = {"javascript": {"react"}, "react": {"javascript"}}
        parent_of = {"react": "javascript"}
        return adj, {}, {"javascript", "react"}, parent_of

    monkeypatch.setattr("compatibility_score.load_skill_graph", fake_load_graph)
    monkeypatch.setattr("compatibility_score.query_covers", lambda _c, _r: False)

    job = {
        "id": 9,
        "user_email": "e@test.com",
        "source_type": "job_description",
        "skills": [{"name": "javascript", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    resume = {
        "id": 8,
        "user_email": "e@test.com",
        "source_type": "resume",
        "skills": [{"name": "react", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    out = compute_compatibility_breakdown(resume, job, "e@test.com")
    sd = out["skill_details"][0]
    assert sd["graph_hops_to_nearest_resume_skill"] == 1
    assert sd["resume_match_skill_slug"] == "react"
    assert sd["tree_upward_hops_for_decay"] == 0
    assert abs(sd["tree_base_factor"] - 1.0) < 1e-6
    assert sd["skill_bonus_descendant_count"] == 1
    assert abs(sd["tree_decay_factor"] - 1.6) < 1e-6


def test_jd_lists_related_skills_excludes_shared_parent_for_other_line(monkeypatch):
    """If JD lists parent+child and resume only the parent, do not score the child line via parent."""
    monkeypatch.setattr(
        "compatibility_score.get_employer_metric_weights",
        lambda _email: {
            "skill_pct": 100.0,
            "job_pct": 0.0,
            "money_pct": 0.0,
            "duration_pct": 0.0,
            "gpax_pct": 0.0,
            "education_pct": 0.0,
            "language_pct": 0.0,
            "standardized_test_pct": 0.0,
            "tree_decay_per_hop": 0.7,
            "per_skill_weight_cap_multiplier": 1.5,
        },
    )
    monkeypatch.setattr("compatibility_score.get_jd_skill_importance_map", lambda _jid: {})
    monkeypatch.setattr("compatibility_score.reload_facts_from_db", lambda: None)

    def fake_load_graph():
        adj = {"javascript": {"react"}, "react": {"javascript"}}
        parent_of = {"react": "javascript"}
        return adj, {}, {"javascript", "react"}, parent_of

    monkeypatch.setattr("compatibility_score.load_skill_graph", fake_load_graph)
    monkeypatch.setattr("compatibility_score.query_covers", lambda _c, _r: False)

    job = {
        "id": 9,
        "user_email": "e@test.com",
        "source_type": "job_description",
        "skills": [
            {"name": "javascript", "compatibilityLevel": "", "evidence": ""},
            {"name": "react", "compatibilityLevel": "", "evidence": ""},
        ],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    resume = {
        "id": 8,
        "user_email": "e@test.com",
        "source_type": "resume",
        "skills": [{"name": "javascript", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    out = compute_compatibility_breakdown(resume, job, "e@test.com")
    by_slug = {row["job_skill_slug"]: row for row in out["skill_details"]}
    assert abs(by_slug["javascript"]["tree_decay_factor"] - 1.6) < 1e-6
    assert by_slug["javascript"]["skill_bonus_exact_x"] == 1
    assert by_slug["javascript"]["resume_match_skill_slug"] == "javascript"
    assert by_slug["react"]["graph_hops_to_nearest_resume_skill"] is None
    assert by_slug["react"]["resume_match_skill_slug"] is None
    assert by_slug["react"]["tree_decay_factor"] == 0.0


def test_match_compatibility_route(monkeypatch):
    monkeypatch.setattr(backend_app, "_email_from_bearer", lambda: "u@test.com")

    def fake_compute(_resume, _job, employer_email, compare_weights=None):
        return {
            "compatibility_percent": 55.5,
            "employer_email": employer_email,
            "weights_effective_fraction": {},
            "tree_decay_per_hop": 0.7,
            "per_skill_weight_cap_multiplier": 1.5,
            "job_is_intern": False,
            "dimensions_percent_of_total": {},
            "dimension_scores_0_1": {},
            "skill_details": [],
        }

    monkeypatch.setattr(backend_app, "compute_compatibility_breakdown", fake_compute)

    def fake_get_by_id(eid, user_email=None):
        if eid == 1:
            return {
                "id": 1,
                "user_email": "u@test.com",
                "source_type": "resume",
                "skills": [],
                "jobRole": "Dev",
                "moneyEstimate": "",
                "duration": "",
                "gpax": "",
                "educationLevel": "",
                "languages": [],
                "standardizedTests": [],
                "employmentType": "full_time_job",
            }
        if eid == 2:
            return {
                "id": 2,
                "user_email": "u@test.com",
                "source_type": "job_description",
                "skills": [],
                "jobRole": "Dev",
                "moneyEstimate": "",
                "duration": "",
                "gpax": "",
                "educationLevel": "",
                "languages": [],
                "standardizedTests": [],
                "employmentType": "full_time_job",
            }
        return None

    monkeypatch.setattr(backend_app, "get_compatibility_metric_extraction_by_id", fake_get_by_id)
    client = backend_app.app.test_client()
    r = client.post(
        "/api/match/compatibility",
        json={"resume_extraction_id": 1, "job_extraction_id": 2},
        headers={"Authorization": "Bearer token_u@test.com_1"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "compatibility_percent" in data


def test_compare_weights_sum_over_100_raises():
    spec = {
        "metrics": [
            {"key": "skills", "percent": 60, "apply": True},
            {"key": "job_role", "percent": 50, "apply": True},
        ]
    }
    resume = {"skills": [], "employmentType": "full_time_job"}
    job = {"skills": [], "employmentType": "full_time_job"}
    with pytest.raises(CompareWeightsValidationError):
        resolve_compare_weights_from_payload(spec, resume, job, False)


def test_vacuous_gpa_redistributes_weight_to_skills(monkeypatch):
    monkeypatch.setattr(
        "compatibility_score.get_employer_metric_weights",
        lambda _email: {
            "skill_pct": 50.0,
            "job_pct": 0.0,
            "money_pct": 0.0,
            "duration_pct": 0.0,
            "gpax_pct": 50.0,
            "education_pct": 0.0,
            "language_pct": 0.0,
            "standardized_test_pct": 0.0,
            "tree_decay_per_hop": 0.7,
            "per_skill_weight_cap_multiplier": 1.5,
        },
    )
    monkeypatch.setattr("compatibility_score.get_jd_skill_importance_map", lambda _jid: {})
    monkeypatch.setattr("compatibility_score.reload_facts_from_db", lambda: None)

    def fake_load_graph():
        adj = {"javascript": {"react"}, "react": {"javascript"}}
        parent_of = {"react": "javascript"}
        return adj, {}, {"javascript", "react"}, parent_of

    monkeypatch.setattr("compatibility_score.load_skill_graph", fake_load_graph)
    monkeypatch.setattr("compatibility_score.query_covers", lambda _c, _r: False)

    job = {
        "id": 9,
        "user_email": "e@test.com",
        "source_type": "job_description",
        "skills": [{"name": "react", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    resume = {
        "id": 8,
        "user_email": "e@test.com",
        "source_type": "resume",
        "skills": [{"name": "javascript", "compatibilityLevel": "", "evidence": ""}],
        "jobRole": "",
        "moneyEstimate": "",
        "duration": "",
        "gpax": "",
        "educationLevel": "",
        "languages": [],
        "standardizedTests": [],
        "employmentType": "full_time_job",
    }
    out = compute_compatibility_breakdown(resume, job, "e@test.com")
    assert out["vacuous_metrics"].get("gpax") is True
    assert abs(out["weights_effective_fraction"]["skill_pct"] - 1.0) < 1e-4
    assert out["weights_effective_fraction"]["gpax_pct"] == 0.0
