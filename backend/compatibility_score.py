"""
Resume vs job-description compatibility (0–100).

Skill matching uses the same tree/alias facts as Prolog (skill_meta.pl). For each JD skill we
find the nearest eligible resume skill (excluding tree-sibling JD bullets to avoid double
counting). **Base** match quality uses decay only on **upward** (parent) graph steps; child steps
are 1×. We add **+1** if the exact JD skill is on the resume, **+1** per eligible resume
descendant (more specific than JD), stacking; **Prolog** ``covers/2`` floors the base at 1.0.
The per-requirement multiplier is capped at **1.6**. Other metrics use lightweight heuristics.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from db import get_employer_metric_weights, get_jd_skill_importance_map
from prolog_meta import (
    mi_solve_covers_proof,
    query_covers,
    reload_facts_from_db,
)
from skill_normalize import to_slug
from skill_tree import (
    augment_isolated_nodes,
    best_resume_match_for_jd,
    canonical_skill_slug,
    count_resume_descendants_for_jd_bonus,
    load_skill_graph,
)

# Max multiplier on (weight_share * base_tree_match) for a single JD skill row.
SKILL_PER_REQUIREMENT_MAX_MULTIPLIER = 1.6

COMPARE_DIMENSION_ORDER: List[str] = [
    "skills",
    "job_role",
    "money",
    "duration",
    "gpax",
    "education",
    "languages",
    "standardized_tests",
]

INTERNAL_TO_FR_KEY: Dict[str, str] = {
    "skills": "skill_pct",
    "job_role": "job_pct",
    "money": "money_pct",
    "duration": "duration_pct",
    "gpax": "gpax_pct",
    "education": "education_pct",
    "languages": "language_pct",
    "standardized_tests": "standardized_test_pct",
}


class CompareWeightsValidationError(ValueError):
    """Invalid compare-page weight payload (e.g. applied percents sum over 100)."""


def _str_blank(v: Any) -> bool:
    return not str(v or "").strip()


def dimension_both_vacuous(
    resume: Dict[str, Any], job: Dict[str, Any], dim: str, job_is_intern: bool
) -> bool:
    """True when resume and JD both lack data for this dimension — exclude from scoring."""
    if dim == "money" and job_is_intern:
        return True
    if dim == "skills":

        def skills_blank(ext: Dict[str, Any]) -> bool:
            for s in ext.get("skills") or []:
                if isinstance(s, dict) and not _str_blank(s.get("name")):
                    return False
            return True

        return skills_blank(resume) and skills_blank(job)
    if dim == "job_role":
        return _str_blank(resume.get("jobRole")) and _str_blank(job.get("jobRole"))
    if dim == "money":
        return _str_blank(resume.get("moneyEstimate")) and _str_blank(job.get("moneyEstimate"))
    if dim == "duration":
        return _str_blank(resume.get("duration")) and _str_blank(job.get("duration"))
    if dim == "gpax":
        return _str_blank(resume.get("gpax")) and _str_blank(job.get("gpax"))
    if dim == "education":
        return _str_blank(resume.get("educationLevel")) and _str_blank(
            job.get("educationLevel")
        )

    if dim == "languages":

        def lang_nonempty(ext: Dict[str, Any]) -> bool:
            for x in ext.get("languages") or []:
                if isinstance(x, dict) and not _str_blank(
                    x.get("language") or x.get("name")
                ):
                    return True
            return False

        return not lang_nonempty(resume) and not lang_nonempty(job)

    if dim == "standardized_tests":

        def test_nonempty(ext: Dict[str, Any]) -> bool:
            for x in ext.get("standardizedTests") or []:
                if isinstance(x, dict) and not _str_blank(
                    x.get("testName") or x.get("name")
                ):
                    return True
            return False

        return not test_nonempty(resume) and not test_nonempty(job)

    return False


def _fr_to_internal(fr: Dict[str, float]) -> Dict[str, float]:
    return {d: float(fr.get(INTERNAL_TO_FR_KEY[d], 0) or 0) for d in COMPARE_DIMENSION_ORDER}


def _internal_to_fr(wi: Dict[str, float]) -> Dict[str, float]:
    return {INTERNAL_TO_FR_KEY[d]: float(wi.get(d, 0) or 0) for d in COMPARE_DIMENSION_ORDER}


def apply_vacuous_redistribution_internal(
    wi: Dict[str, float],
    resume: Dict[str, Any],
    job: Dict[str, Any],
    job_is_intern: bool,
) -> Tuple[Dict[str, float], List[str], Dict[str, bool]]:
    """
    Zero out vacuous dimensions and spread their weight across remaining dimensions
    proportionally to their current weights.
    """
    notes: List[str] = []
    vacuous = {
        d: dimension_both_vacuous(resume, job, d, job_is_intern) for d in COMPARE_DIMENSION_ORDER
    }
    out = {d: float(wi.get(d, 0) or 0) for d in COMPARE_DIMENSION_ORDER}
    freed = sum(out[d] for d in COMPARE_DIMENSION_ORDER if vacuous[d])
    for d in COMPARE_DIMENSION_ORDER:
        if vacuous[d]:
            out[d] = 0.0
            label = INTERNAL_TO_FR_KEY[d].replace("_pct", "").replace("_", " ")
            notes.append(
                f"{label}: both resume and JD empty — weight removed and redistributed."
            )
    active = [d for d in COMPARE_DIMENSION_ORDER if out[d] > 1e-15]
    if freed > 1e-15 and active:
        s_act = sum(out[d] for d in active)
        if s_act > 1e-15:
            for d in active:
                out[d] += freed * (out[d] / s_act)
    tot = sum(out.values())
    if tot <= 1e-15:
        return {d: 0.0 for d in COMPARE_DIMENSION_ORDER}, notes, vacuous
    out = {d: out[d] / tot for d in COMPARE_DIMENSION_ORDER}
    return out, notes, vacuous


def _add_int_remainder_proportional(pct: Dict[str, int], keys: List[str], remainder: int) -> None:
    if remainder == 0 or not keys:
        return
    s_sub = sum(pct[k] for k in keys)
    if s_sub == 0:
        base, extra = divmod(remainder, len(keys))
        for i, k in enumerate(keys):
            pct[k] += base + (1 if i < extra else 0)
        return
    adds: Dict[str, int] = {k: 0 for k in keys}
    allocated = 0
    frac_parts: List[Tuple[float, str]] = []
    for k in keys:
        raw = remainder * pct[k] / s_sub
        a = int(math.floor(raw + 1e-9))
        adds[k] = a
        allocated += a
        frac_parts.append((raw - a, k))
    left = remainder - allocated
    frac_parts.sort(key=lambda x: -x[0])
    for i in range(left):
        adds[frac_parts[i % len(frac_parts)][1]] += 1
    for k in keys:
        pct[k] += adds[k]


def resolve_compare_weights_from_payload(
    compare_weights: Dict[str, Any],
    resume: Dict[str, Any],
    job: Dict[str, Any],
    job_is_intern: bool,
) -> Tuple[Dict[str, float], List[str], Dict[str, bool], bool, Dict[str, bool]]:
    """
    Build internal weight fractions from compare UI (integer percents, apply toggles).
    Returns wi, notes, vacuous flags, used_compare True, apply_map (user toggles per dimension).
    """
    notes: List[str] = []
    metrics = compare_weights.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise CompareWeightsValidationError("compare_weights.metrics must be a non-empty list")

    pct: Dict[str, int] = {d: 0 for d in COMPARE_DIMENSION_ORDER}
    apply_map: Dict[str, bool] = {d: False for d in COMPARE_DIMENSION_ORDER}

    for item in metrics:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in INTERNAL_TO_FR_KEY:
            continue
        apply_map[key] = bool(item.get("apply", True))
        raw_p = item.get("percent", 0)
        try:
            p = int(raw_p)
        except (TypeError, ValueError) as exc:
            raise CompareWeightsValidationError(
                "each weight percent must be an integer"
            ) from exc
        if p < 0 or p > 100:
            raise CompareWeightsValidationError("each weight percent must be 0–100")
        pct[key] = p if apply_map[key] else 0

    applied = [d for d in COMPARE_DIMENSION_ORDER if apply_map[d]]
    if not applied:
        raise CompareWeightsValidationError("at least one metric must be applied")

    s_applied = sum(pct[d] for d in applied)
    if s_applied > 100:
        raise CompareWeightsValidationError(
            "applied weights must sum to exactly 100% before compare (currently over 100%)."
        )

    if s_applied < 100:
        remainder = 100 - s_applied
        if apply_map["skills"]:
            pct["skills"] += remainder
            notes.append(
                f"Applied weights summed to {s_applied}%; added {remainder}% to skills."
            )
        else:
            others = [d for d in applied if d != "skills"]
            if not others:
                others = list(applied)
            _add_int_remainder_proportional(pct, others, remainder)
            notes.append(
                f"Applied weights summed to {s_applied}%; distributed {remainder}% "
                f"across applied metrics (skills not applied)."
            )

    total_i = sum(pct[d] for d in COMPARE_DIMENSION_ORDER)
    if total_i != 100:
        drift = 100 - total_i
        pct[applied[0]] += drift

    wi = {d: pct[d] / 100.0 for d in COMPARE_DIMENSION_ORDER}
    wi2, vac_notes, vacuous = apply_vacuous_redistribution_internal(
        wi, resume, job, job_is_intern
    )
    notes.extend(vac_notes)
    return wi2, notes, vacuous, True, dict(apply_map)


def resolve_effective_weight_fractions(
    resume: Dict[str, Any],
    job: Dict[str, Any],
    employer_email: str,
    compare_weights: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, float], List[str], Dict[str, bool], bool, Dict[str, bool]]:
    """
    Effective fr dict (skill_pct keys), notes, vacuous map, used_compare, compare_metric_apply.
    """
    wrow = get_employer_metric_weights(employer_email)
    job_type = str(job.get("employmentType") or "").lower()
    job_is_intern = job_type in ("intern", "internship")

    all_applied = {d: True for d in COMPARE_DIMENSION_ORDER}

    if compare_weights:
        wi, notes, vacuous, used, apply_map = resolve_compare_weights_from_payload(
            compare_weights, resume, job, job_is_intern
        )
        fr = _internal_to_fr(wi)
        return fr, notes, vacuous, used, apply_map

    fr0 = _normalize_weight_fractions(wrow, job_is_intern)
    wi0 = _fr_to_internal(fr0)
    wi1, notes, vacuous = apply_vacuous_redistribution_internal(
        wi0, resume, job, job_is_intern
    )
    return _internal_to_fr(wi1), notes, vacuous, False, all_applied


CEFR_ORDER: Dict[str, int] = {
    "a1": 1,
    "a2": 2,
    "b1": 3,
    "b2": 4,
    "c1": 5,
    "c2": 6,
    "native": 7,
    "fluent": 6,
}


def _norm_keys(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _similarity(a: str, b: str) -> float:
    a, b = _norm_keys(a), _norm_keys(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.85
    return SequenceMatcher(None, a, b).ratio()


def score_job_role(resume: str, job: str) -> float:
    return _similarity(resume or "", job or "")


def _parse_money_tokens(text: str) -> List[float]:
    if not text:
        return []
    out: List[float] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([kKmM]?)", text.replace(",", "")):
        val = float(m.group(1))
        suf = (m.group(2) or "").lower()
        if suf == "k":
            val *= 1000
        if suf == "m":
            val *= 1_000_000
        out.append(val)
    return out


def score_money(resume_money: str, job_money: str) -> float:
    ra = _parse_money_tokens(resume_money or "")
    ja = _parse_money_tokens(job_money or "")
    if not ja:
        return 1.0
    if not ra:
        return 0.4
    r_mid = sum(ra) / len(ra)
    j_lo, j_hi = min(ja), max(ja)
    if j_lo <= r_mid <= j_hi:
        return 1.0
    if r_mid < j_lo:
        return max(0.0, 1.0 - (j_lo - r_mid) / max(j_lo, 1.0))
    return max(0.0, 1.0 - (r_mid - j_hi) / max(j_hi, 1.0))


def score_duration(resume_d: str, job_d: str) -> float:
    return _similarity(resume_d or "", job_d or "")


def _parse_gpa(s: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", s or "")
    if m:
        return float(m.group(1)) / float(m.group(2)) * 4.0
    m = re.search(r"(\d+\.\d+|\d+)", s or "")
    if m:
        v = float(m.group(1))
        if v <= 4.5:
            return v
        if v <= 100:
            return v / 25.0
    return None


def score_gpax(res_g: str, job_g: str) -> float:
    rg = _parse_gpa(res_g or "")
    jg = _parse_gpa(job_g or "")
    if jg is None:
        return 1.0 if not (job_g or "").strip() else _similarity(res_g or "", job_g or "")
    if rg is None:
        return 0.45
    if rg >= jg:
        return 1.0
    return max(0.0, rg / jg)


def education_rank(text: str) -> int:
    t = _norm_keys(text or "")
    for keys, r in (
        ("phd doctorate doctoral", 6),
        ("master ms mba graduate", 5),
        ("bachelor bs ba btech undergraduate", 4),
        ("associate", 3),
        ("high school ged secondary", 2),
    ):
        for k in keys.split():
            if k in t:
                return r
    return 0


def score_education(res_e: str, job_e: str) -> float:
    if not (job_e or "").strip():
        return 1.0
    rr, jr = education_rank(res_e), education_rank(job_e)
    if jr == 0:
        return _similarity(res_e or "", job_e or "")
    if rr >= jr:
        return 1.0
    return max(0.0, float(rr) / float(jr))


def _lang_level_rank(s: str) -> int:
    t = _norm_keys(s or "")
    for token, r in CEFR_ORDER.items():
        if token in t:
            return r
    return 0


def score_languages(res_langs: List[dict], job_langs: List[dict]) -> float:
    if not job_langs:
        return 1.0
    res_map: Dict[str, int] = {}
    for x in res_langs or []:
        if not isinstance(x, dict):
            continue
        lang = _norm_keys(x.get("language") or x.get("name") or "")
        if not lang:
            continue
        res_map[lang] = max(res_map.get(lang, 0), _lang_level_rank(str(x.get("level") or "")))
    scores: List[float] = []
    for x in job_langs:
        if not isinstance(x, dict):
            continue
        jl = _norm_keys(x.get("language") or x.get("name") or "")
        if not jl:
            continue
        need = _lang_level_rank(str(x.get("level") or ""))
        got = 0
        for rl, rv in res_map.items():
            if jl in rl or rl in jl or SequenceMatcher(None, jl, rl).ratio() > 0.82:
                got = max(got, rv)
                break
        if need <= 0:
            scores.append(1.0 if got > 0 else 0.5)
        else:
            scores.append(min(1.0, got / need) if got else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _norm_test_name(s: str) -> str:
    return _norm_keys(s or "")


def score_standardized_tests(res_tests: List[dict], job_tests: List[dict]) -> float:
    if not job_tests:
        return 1.0
    res_by: Dict[str, Optional[float]] = {}
    for t in res_tests or []:
        if not isinstance(t, dict):
            continue
        key = _norm_test_name(t.get("testName") or "")
        if not key:
            continue
        ns = t.get("normalizedScore") or ""
        try:
            val = float(str(ns).strip())
        except ValueError:
            val = None
        res_by[key] = val
    parts: List[float] = []
    for t in job_tests:
        if not isinstance(t, dict):
            continue
        jn = _norm_test_name(t.get("testName") or "")
        if not jn:
            continue
        j_need = t.get("normalizedScore") or ""
        try:
            jmin = float(str(j_need).strip())
        except ValueError:
            jmin = None
        rscore = None
        for rk, rv in res_by.items():
            if jn in rk or rk in jn or SequenceMatcher(None, jn, rk).ratio() > 0.75:
                rscore = rv
                break
        if jmin is None:
            parts.append(1.0 if rscore is not None else 0.35)
        elif rscore is None:
            parts.append(0.0)
        else:
            parts.append(min(1.0, rscore / jmin) if jmin > 0 else 1.0)
    return sum(parts) / len(parts) if parts else 0.0


def _normalize_weight_fractions(w: Dict[str, Any], job_is_intern: bool) -> Dict[str, float]:
    keys = [
        "skill_pct",
        "job_pct",
        "money_pct",
        "duration_pct",
        "gpax_pct",
        "education_pct",
        "language_pct",
        "standardized_test_pct",
    ]
    raw = {k: float(w.get(k) or 0) for k in keys}
    if job_is_intern:
        raw["money_pct"] = 0.0
    s = sum(raw.values())
    if s <= 0:
        return {k: 0.0 for k in keys}
    return {k: raw[k] / s for k in keys}


def compute_compatibility_breakdown(
    resume_extraction: Dict[str, Any],
    job_extraction: Dict[str, Any],
    employer_email: str,
    compare_weights: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        reload_facts_from_db()
    except Exception:
        pass

    wrow = get_employer_metric_weights(employer_email)
    decay = float(wrow["tree_decay_per_hop"] or 0.7)
    cap_m = float(wrow["per_skill_weight_cap_multiplier"] or 1.5)
    job_type = str(job_extraction.get("employmentType") or "").lower()
    job_is_intern = job_type in ("intern", "internship")

    (
        fr,
        weight_notes,
        vacuous_map,
        compare_weights_used,
        compare_metric_apply,
    ) = resolve_effective_weight_fractions(
        resume_extraction, job_extraction, employer_email, compare_weights
    )

    adj_base, alias_to_canon, known, parent_of = load_skill_graph()

    job_skills = job_extraction.get("skills") or []
    resume_skills = resume_extraction.get("skills") or []

    skills_vacuous = bool(vacuous_map.get("skills"))
    jd_importance = (
        {}
        if skills_vacuous
        else get_jd_skill_importance_map(int(job_extraction["id"]))
    )

    slug_weights: Dict[str, float] = defaultdict(float)
    for sk in job_skills:
        if not isinstance(sk, dict):
            continue
        raw_name = (sk.get("name") or "").strip()
        jc = canonical_skill_slug(raw_name, alias_to_canon, known)
        if not jc:
            continue
        slug = to_slug(raw_name) or jc
        slug_weights[jc] += float(jd_importance.get(jc, jd_importance.get(slug, 1.0)))

    resume_pairs: List[tuple[str, str]] = []
    for s in resume_skills:
        if not isinstance(s, dict):
            continue
        cn = canonical_skill_slug((s.get("name") or ""), alias_to_canon, known)
        if cn:
            resume_pairs.append((cn, str(s.get("compatibilityLevel") or "")))
    resume_canonicals = [p[0] for p in resume_pairs]
    resume_canonical_set = set(resume_canonicals)

    all_slugs = list({*slug_weights.keys(), *resume_canonicals})
    adj = augment_isolated_nodes(adj_base, all_slugs)

    skill_details: List[Dict[str, Any]] = []
    skill_aggregate = 0.0

    if skills_vacuous:
        skill_aggregate = 0.0
        skill_details = []
    elif not slug_weights:
        skill_aggregate = 1.0
    else:
        n = len(slug_weights)
        equal = 1.0 / n
        ssum = sum(slug_weights.values()) or 1.0
        norm_w = {k: v / ssum for k, v in slug_weights.items()}
        max_share = cap_m * equal
        for k, v in list(norm_w.items()):
            norm_w[k] = min(v, max_share)
        s2 = sum(norm_w.values()) or 1.0
        norm_w = {k: v / s2 for k, v in norm_w.items()}

        jd_canonicals = set(norm_w.keys())
        for req, share in norm_w.items():
            hops, nearest_resume_slug, upward_hops = best_resume_match_for_jd(
                req, resume_canonicals, adj, jd_canonicals, parent_of
            )
            if hops is None:
                tree_base = 0.0
            else:
                tree_base = float(decay) ** int(upward_hops)
            prolog_covers_flag = False
            proof_cand: Optional[str] = None
            for cand, _ in resume_pairs:
                try:
                    if query_covers(cand, req):
                        prolog_covers_flag = True
                        proof_cand = cand
                        break
                except Exception:
                    continue
            meta_proof: Optional[Dict[str, Any]] = None
            if proof_cand:
                try:
                    meta_proof = mi_solve_covers_proof(proof_cand, req)
                except Exception:
                    meta_proof = None
            resume_match_slug: Optional[str] = None
            if proof_cand:
                resume_match_slug = proof_cand
            else:
                resume_match_slug = nearest_resume_slug
            if prolog_covers_flag:
                tree_base = max(tree_base, 1.0)
            bonus_exact = 1.0 if req in resume_canonical_set else 0.0
            n_desc_bonus = count_resume_descendants_for_jd_bonus(
                req, resume_canonical_set, jd_canonicals, parent_of
            )
            bonus_children = float(n_desc_bonus)
            raw_multiplier = tree_base + bonus_exact + bonus_children
            factor = min(SKILL_PER_REQUIREMENT_MAX_MULTIPLIER, raw_multiplier)
            contrib = share * factor
            skill_aggregate += contrib
            skill_details.append(
                {
                    "job_skill_slug": req,
                    "resume_match_skill_slug": resume_match_slug,
                    "weight_share": round(share, 4),
                    "graph_hops_to_nearest_resume_skill": hops,
                    "tree_upward_hops_for_decay": upward_hops
                    if hops is not None
                    else None,
                    "tree_base_factor": round(tree_base, 4),
                    "skill_bonus_exact_x": int(bonus_exact),
                    "skill_bonus_descendant_count": n_desc_bonus,
                    "skill_multiplier_raw": round(raw_multiplier, 4),
                    "tree_decay_factor": round(factor, 4),
                    "prolog_strict_covers": prolog_covers_flag,
                    "meta_interpreter_proof": meta_proof,
                    "weighted_contribution": round(contrib, 4),
                }
            )

    jr = score_job_role(
        str(resume_extraction.get("jobRole") or ""),
        str(job_extraction.get("jobRole") or ""),
    )
    money_s = (
        1.0
        if job_is_intern
        else score_money(
            str(resume_extraction.get("moneyEstimate") or ""),
            str(job_extraction.get("moneyEstimate") or ""),
        )
    )
    dur_s = score_duration(
        str(resume_extraction.get("duration") or ""),
        str(job_extraction.get("duration") or ""),
    )
    gp_s = score_gpax(
        str(resume_extraction.get("gpax") or ""),
        str(job_extraction.get("gpax") or ""),
    )
    ed_s = score_education(
        str(resume_extraction.get("educationLevel") or ""),
        str(job_extraction.get("educationLevel") or ""),
    )
    lang_s = score_languages(
        list(resume_extraction.get("languages") or []),
        list(job_extraction.get("languages") or []),
    )
    test_s = score_standardized_tests(
        list(resume_extraction.get("standardizedTests") or []),
        list(job_extraction.get("standardizedTests") or []),
    )

    parts = {
        "skills": skill_aggregate * fr["skill_pct"],
        "job_role": jr * fr["job_pct"],
        "money": money_s * fr["money_pct"],
        "duration": dur_s * fr["duration_pct"],
        "gpax": gp_s * fr["gpax_pct"],
        "education": ed_s * fr["education_pct"],
        "languages": lang_s * fr["language_pct"],
        "standardized_tests": test_s * fr["standardized_test_pct"],
    }
    total_percent = sum(parts.values()) * 100.0

    return {
        "compatibility_percent": round(min(100.0, max(0.0, total_percent)), 2),
        "employer_email": employer_email,
        "weights_effective_fraction": {k: round(v, 4) for k, v in fr.items()},
        "compare_weights_applied": compare_weights_used,
        "compare_metric_apply": compare_metric_apply,
        "compare_weight_adjustments": weight_notes,
        "vacuous_metrics": {k: v for k, v in vacuous_map.items() if v},
        "tree_decay_per_hop": decay,
        "per_skill_weight_cap_multiplier": cap_m,
        "job_is_intern": job_is_intern,
        "dimensions_percent_of_total": {
            k: round(v * 100.0, 2) for k, v in parts.items()
        },
        "dimension_scores_0_1": {
            "skills": round(skill_aggregate, 4),
            "job_role": round(jr, 4),
            "money": round(money_s, 4),
            "duration": round(dur_s, 4),
            "gpax": round(gp_s, 4),
            "education": round(ed_s, 4),
            "languages": round(lang_s, 4),
            "standardized_tests": round(test_s, 4),
        },
        "skill_details": skill_details,
    }
