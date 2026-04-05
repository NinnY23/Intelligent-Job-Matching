# PySwip and SWI-Prolog setup

## Overview

[PySwip](https://github.com/yuce/pyswip) runs SWI-Prolog rules in [`prolog/skill_meta.pl`](prolog/skill_meta.pl). Skill hierarchy and aliases are loaded from SQLite ([`db.py`](db.py)) as dynamic facts.

**Meta-interpreter:** `mi_solve/2` in `skill_meta.pl` reifies **proofs** for `covers/2`—either `proof(exact, Canon)` (same canonical slug after aliases) or `proof(specializes, Chain)` (general JD skill → … → specific resume skill along the tree). Python exposes this via `mi_solve_covers_proof` and optional `explain` on the match preview API.

## Install SWI-Prolog

1. Download SWI-Prolog for your OS from [https://www.swi-prolog.org/download/stable](https://www.swi-prolog.org/download/stable).
2. On Windows, add the installation directory containing `swipl.exe` to your **PATH** (e.g. `C:\Program Files\swipl\bin`).
3. Use a **64-bit** SWI build if your Python is 64-bit (mismatched architectures break PySwip).

## Python dependency

From the `backend` folder:

```bash
pip install -r requirements.txt
```

(`pyswip` is listed in `requirements.txt`.)

## API usage

1. **Seed** the skill tree (idempotent): `POST /api/skills/seed` with `Authorization: Bearer <token>`.
2. **Inspect** graph: `GET /api/skills/graph`.
3. **Match preview**: `POST /api/match/prolog-preview` with JSON:

```json
{
  "candidate_skills": ["React", "js"],
  "required_skills": ["JavaScript", "HTML"],
  "explain": true
}
```

Set `"explain": true` to add a `proof` object on each `coverage` row where `covered` is true (`kind`: `exact` or `specializes`, `detail`: canonical slug or list of slugs top-down).

Response includes `normalized` slugs, per-requirement `coverage`, and `missing` requirements.

Full resume–JD compatibility (`POST /api/match/compatibility`) includes `meta_interpreter_proof` per JD skill in `skill_details` when Prolog is available.

## Skill normalization

Raw strings are lowercased, parenthetical segments removed (e.g. `(v18)`), then slugified in [`skill_normalize.py`](skill_normalize.py) before Prolog queries.

## Troubleshooting

- **`PrologUnavailableError` / 503**: SWI-Prolog not found — verify `swipl` / `swipl.exe` on PATH and restart the terminal.
- **Empty coverage**: Run `POST /api/skills/seed` so `skills` and `skill_aliases` tables are populated.
