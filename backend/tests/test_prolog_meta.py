import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prolog_meta import is_prolog_available, prolog_match_preview


pytestmark = pytest.mark.skipif(
    not is_prolog_available(),
    reason="SWI-Prolog / PySwip not available",
)


def test_prolog_covers_react_for_javascript_requirement():
    from db import init_db
    from seed_skills import run_seed

    init_db()
    run_seed()
    out = prolog_match_preview(
        candidate_skills=["React"],
        required_skills=["JavaScript"],
    )
    assert out["all_covered"] is True
    assert out["missing"] == []


def test_prolog_alias_js_to_javascript():
    from db import init_db
    from seed_skills import run_seed

    init_db()
    run_seed()
    out = prolog_match_preview(
        candidate_skills=["js"],
        required_skills=["javascript"],
    )
    assert out["all_covered"] is True


def test_prolog_match_preview_explain_proof():
    from db import init_db
    from seed_skills import run_seed

    init_db()
    run_seed()
    out = prolog_match_preview(
        candidate_skills=["React"],
        required_skills=["JavaScript"],
        explain=True,
    )
    assert out["all_covered"] is True
    cov = out["coverage"][0]
    assert cov.get("proof") is not None
    assert cov["proof"]["kind"] == "specializes"
    assert isinstance(cov["proof"]["detail"], list)
    assert "javascript" in cov["proof"]["detail"] and "react" in cov["proof"]["detail"]


def test_prolog_match_preview_explain_exact():
    from db import init_db
    from seed_skills import run_seed

    init_db()
    run_seed()
    out = prolog_match_preview(
        candidate_skills=["JavaScript"],
        required_skills=["JavaScript"],
        explain=True,
    )
    cov = out["coverage"][0]
    assert cov["proof"]["kind"] == "exact"
    assert cov["proof"]["detail"] == "javascript"
