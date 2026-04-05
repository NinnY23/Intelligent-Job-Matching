"""
Idempotent skill hierarchy + aliases seed (structure.md aligned).
Run via POST /api/skills/seed or: python -c \"from seed_skills import run_seed; run_seed()\"
"""

from db import add_skill_alias, ensure_skill


def run_seed() -> None:
    """Insert skills in parent-before-child order; aliases last."""
    # Roots
    ensure_skill("html", "HTML")
    ensure_skill("css", "CSS")
    ensure_skill("javascript", "JavaScript")
    ensure_skill("sql", "SQL")
    ensure_skill("c", "C")

    # Under CSS
    ensure_skill("tailwind", "Tailwind CSS", parent_slug="css")

    # Under JavaScript
    ensure_skill("typescript", "TypeScript", parent_slug="javascript")
    ensure_skill("react", "React", parent_slug="javascript")
    ensure_skill("react_motion", "React Motion", parent_slug="react")

    # Under SQL
    ensure_skill("postgresql", "PostgreSQL", parent_slug="sql")
    ensure_skill("sqlalchemy", "SQLAlchemy", parent_slug="sql")

    # Under C
    ensure_skill("cpp", "C++", parent_slug="c")

    # Aliases (alias_slug must be normalized slugs)
    pairs = [
        ("js", "javascript"),
        ("postgres", "postgresql"),
        ("pg", "postgresql"),
        ("ts", "typescript"),
        ("jsx", "react"),
    ]
    for alias, canonical in pairs:
        try:
            add_skill_alias(alias, canonical)
        except Exception:
            pass


if __name__ == "__main__":
    from db import init_db

    init_db()
    run_seed()
    print("Seed complete.")
