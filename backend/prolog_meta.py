"""PySwip bridge: DB facts, covers/2, and mi_solve/2 meta-interpreter proofs."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from db import fetch_prolog_skill_facts
from skill_normalize import normalize_skill_list, to_slug

_PROLOG = None
_PL_PATH = Path(__file__).resolve().parent / "prolog" / "skill_meta.pl"


class PrologUnavailableError(RuntimeError):
    pass


def _get_prolog():
    global _PROLOG
    if _PROLOG is not None:
        return _PROLOG
    try:
        from pyswip import Prolog
    except ImportError as exc:
        raise PrologUnavailableError("pyswip is not installed") from exc
    prolog = Prolog()
    if not _PL_PATH.is_file():
        raise PrologUnavailableError(f"Missing Prolog file: {_PL_PATH}")
    prolog.consult(str(_PL_PATH))
    _PROLOG = prolog
    return prolog


def _prolog_atom(slug: str) -> str:
    """Quote atom for SWI-Prolog if needed."""
    if not slug:
        return "''"
    safe = slug.replace("\\", "\\\\").replace("'", "''")
    if all(c.isalnum() or c == "_" for c in slug) and slug and (slug[0].isalpha() or slug[0] == "_"):
        return slug
    return f"'{safe}'"


def _clear_dynamic_facts(prolog) -> None:
    for goal in (
        "retractall(known_skill(_))",
        "retractall(alias_alias_to_canonical(_,_))",
        "retractall(subskill_child_parent(_,_))",
    ):
        list(prolog.query(goal))


def _assert_facts(prolog, facts: Dict[str, List[tuple]]) -> None:
    for (slug,) in facts.get("known_skill", []):
        a = _prolog_atom(slug)
        list(prolog.query(f"assertz(known_skill({a}))"))
    for child, parent in facts.get("subskill_child_parent", []):
        c, p = _prolog_atom(child), _prolog_atom(parent)
        list(prolog.query(f"assertz(subskill_child_parent({c}, {p}))"))
    for alias, canonical in facts.get("alias_alias_to_canonical", []):
        al, ca = _prolog_atom(alias), _prolog_atom(canonical)
        list(prolog.query(f"assertz(alias_alias_to_canonical({al}, {ca}))"))


def reload_facts_from_db() -> None:
    prolog = _get_prolog()
    _clear_dynamic_facts(prolog)
    facts = fetch_prolog_skill_facts()
    _assert_facts(prolog, facts)


def query_covers(candidate_slug: str, requirement_slug: str) -> bool:
    prolog = _get_prolog()
    c, r = _prolog_atom(candidate_slug), _prolog_atom(requirement_slug)
    q = f"covers({c}, {r})"
    return bool(list(prolog.query(q)))


def _atom_to_str(x: Any) -> str:
    if isinstance(x, bytes):
        return x.decode("utf-8", errors="replace")
    return str(x)


def _pyswip_list_to_py(term: Any) -> List[Any]:
    """Convert Prolog list (. /2) to Python list of JSON-friendly values."""
    out: List[Any] = []
    cur = term
    seen = 0
    max_steps = 5000
    while cur is not None and seen < max_steps:
        seen += 1
        name = getattr(cur, "name", None)
        args = getattr(cur, "args", None)
        if name == "." and args is not None and len(args) == 2:
            out.append(_pyswip_term_to_json(args[0]))
            cur = args[1]
            continue
        if name == "[]" or (name == "[]" and not args):
            break
        if isinstance(cur, (list, tuple)) and len(cur) == 0:
            break
        out.append(_pyswip_term_to_json(cur))
        break
    return out


def _pyswip_term_to_json(term: Any) -> Any:
    """Turn a PySwip bound term into JSON-serializable data."""
    if term is None:
        return None
    if isinstance(term, (bool, int, float, str)):
        return term
    if isinstance(term, bytes):
        return term.decode("utf-8", errors="replace")
    if isinstance(term, list):
        return [_pyswip_term_to_json(x) for x in term]

    name = getattr(term, "name", None)
    args = getattr(term, "args", None)
    if name is not None and args is not None:
        if name == "." and len(args) == 2:
            return _pyswip_list_to_py(term)
        if name == "[]" or (not args and name in ("[]", "nil")):
            return []
        return {
            "functor": _atom_to_str(name),
            "args": [_pyswip_term_to_json(a) for a in args],
        }

    val = getattr(term, "value", None)
    if val is not None and val is not term:
        return _pyswip_term_to_json(val)

    return _atom_to_str(term)


def _proof_kind_str(k: Any) -> str:
    if isinstance(k, str):
        return k
    if isinstance(k, dict) and k.get("functor") is not None:
        return _atom_to_str(k["functor"])
    return _atom_to_str(k)


def _proof_term_to_api(proof_term: Any) -> Dict[str, Any]:
    raw = _pyswip_term_to_json(proof_term)
    if isinstance(raw, dict) and raw.get("functor") == "proof":
        pargs = raw.get("args") or []
        if len(pargs) >= 2:
            return {
                "kind": _proof_kind_str(pargs[0]),
                "detail": pargs[1],
            }
    return {"kind": "unknown", "detail": raw}


def mi_solve_covers_proof(candidate_slug: str, requirement_slug: str) -> Optional[Dict[str, Any]]:
    """
    Run the meta-interpreter on covers/2; return a structured proof or None if not covered.
    """
    prolog = _get_prolog()
    c, r = _prolog_atom(candidate_slug), _prolog_atom(requirement_slug)
    q = f"mi_solve(covers({c}, {r}), Proof)"
    sols = list(prolog.query(q))
    if not sols:
        return None
    proof_var = sols[0].get("Proof")
    return _proof_term_to_api(proof_var)


def prolog_match_preview(
    candidate_skills: List[str],
    required_skills: List[str],
    explain: bool = False,
) -> Dict[str, Any]:
    """
    Normalize raw strings, reload facts from DB, return per-requirement coverage.
    """
    cand_slugs = normalize_skill_list(candidate_skills)
    req_slugs = normalize_skill_list(required_skills)
    raw_map = {
        "candidate": [{"raw": r, "slug": to_slug(r)} for r in candidate_skills if isinstance(r, str)],
        "required": [{"raw": r, "slug": to_slug(r)} for r in required_skills if isinstance(r, str)],
    }
    try:
        reload_facts_from_db()
    except PrologUnavailableError:
        raise
    except Exception as exc:
        raise PrologUnavailableError(f"Failed to load Prolog facts: {exc}") from exc

    coverage: List[Dict[str, Any]] = []
    missing: List[str] = []
    for req in req_slugs:
        matched = False
        matched_by: Optional[str] = None
        proof: Optional[Dict[str, Any]] = None
        for cand in cand_slugs:
            try:
                if query_covers(cand, req):
                    matched = True
                    matched_by = cand
                    if explain:
                        try:
                            proof = mi_solve_covers_proof(cand, req)
                        except Exception:
                            proof = None
                    break
            except Exception:
                matched = False
        entry: Dict[str, Any] = {
            "requirement_slug": req,
            "covered": matched,
            "matched_candidate_slug": matched_by,
        }
        if explain:
            entry["proof"] = proof
        coverage.append(entry)
        if not matched:
            missing.append(req)

    return {
        "normalized": {"candidates": cand_slugs, "required": req_slugs},
        "raw_map": raw_map,
        "coverage": coverage,
        "missing": missing,
        "all_covered": len(missing) == 0,
    }


def is_prolog_available() -> bool:
    try:
        _get_prolog()
        return True
    except Exception:
        return False


def prolog_compound_tree_factor(hops: int, decay: float) -> float:
    """
    decay**hops using the same Prolog module as skill coverage (skill_meta.pl).
    Falls back to Python if Prolog is unavailable.
    """
    if hops < 0:
        return 0.0
    try:
        prolog = _get_prolog()
        q = f"compound_tree_factor({int(hops)}, {float(decay)}, F)"
        sol = list(prolog.query(q))
        if sol:
            return float(sol[0]["F"])
    except Exception:
        pass
    return float(decay) ** int(hops)
