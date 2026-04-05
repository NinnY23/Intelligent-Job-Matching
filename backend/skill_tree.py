"""
Skill graph distances using the same SQLite facts asserted into Prolog (skill_meta.pl).

Decay for job matching uses **upward** steps only (resume skill is a more general parent of
the JD requirement). Steps toward a **child** (resume more specific) apply 1× per edge.
See ``best_resume_match_for_jd`` and ``eligible_resume_target_for_jd``.
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from db import fetch_prolog_skill_facts
from skill_normalize import to_slug


def load_skill_graph() -> Tuple[Dict[str, Set[str]], Dict[str, str], Set[str], Dict[str, str]]:
    facts = fetch_prolog_skill_facts()
    known: Set[str] = {str(t[0]) for t in facts.get("known_skill", [])}
    alias_to_canon: Dict[str, str] = {}
    for a, c in facts.get("alias_alias_to_canonical", []):
        alias_to_canon[str(a)] = str(c)
    adj: Dict[str, Set[str]] = {s: set() for s in known}
    parent_of: Dict[str, str] = {}
    for child, parent in facts.get("subskill_child_parent", []):
        ch, pa = str(child), str(parent)
        parent_of[ch] = pa
        if ch not in adj:
            adj[ch] = set()
        if pa not in adj:
            adj[pa] = set()
        adj[ch].add(pa)
        adj[pa].add(ch)
    return adj, alias_to_canon, known, parent_of


def canonical_skill_slug(
    raw: str, alias_to_canon: Dict[str, str], known: Set[str]
) -> str:
    s = to_slug(raw)
    if not s:
        return ""
    if s in known:
        return s
    return alias_to_canon.get(s, s)


def augment_isolated_nodes(adj: Dict[str, Set[str]], slugs: List[str]) -> Dict[str, Set[str]]:
    out = {k: set(v) for k, v in adj.items()}
    for s in slugs:
        if s and s not in out:
            out[s] = set()
    return out


def _is_tree_ancestor(ancestor: str, desc: str, parent_of: Dict[str, str]) -> bool:
    cur: Optional[str] = desc
    for _ in range(10000):
        if cur == ancestor:
            return True
        cur = parent_of.get(cur) if cur else None
        if not cur:
            break
    return False


def count_resume_descendants_for_jd_bonus(
    req_slug: str,
    resume_slugs: Set[str],
    jd_slugs: Set[str],
    parent_of: Dict[str, str],
) -> int:
    """
    Resume skills that are strict tree descendants of ``req_slug`` (more specific than JD),
    counting toward +1x stacking bonuses. Excludes JD sibling slugs (also JD lines and
    tree-related to req) to stay consistent with ``eligible_resume_target_for_jd``.
    """
    if not req_slug:
        return 0
    n = 0
    for s in resume_slugs:
        if not s or s == req_slug:
            continue
        if not _is_tree_ancestor(req_slug, s, parent_of):
            continue
        if s in jd_slugs and tree_related(req_slug, s, parent_of):
            continue
        n += 1
    return n


def tree_related(a: str, b: str, parent_of: Dict[str, str]) -> bool:
    """True if one skill is a strict ancestor of the other in the subskill tree (same chain)."""
    if a == b:
        return False
    return _is_tree_ancestor(a, b, parent_of) or _is_tree_ancestor(b, a, parent_of)


def eligible_resume_target_for_jd(
    req_slug: str, target: str, jd_slugs: Set[str], parent_of: Dict[str, str]
) -> bool:
    """
    Resume skill ``target`` may be used to score JD requirement ``req_slug``.

    If ``target`` is also its own JD bullet and is tree-related to ``req_slug``, it is
    excluded so hierarchy is not double-counted against a sibling JD line.
    """
    if not target or not req_slug:
        return False
    if target == req_slug:
        return True
    if target not in jd_slugs:
        return True
    if tree_related(req_slug, target, parent_of):
        return False
    return True


def _upward_steps_on_edge(u: str, v: str, parent_of: Dict[str, str]) -> int:
    """Count 1 when moving from child u to parent v; 0 when moving parent→child or unknown."""
    if parent_of.get(u) == v:
        return 1
    if parent_of.get(v) == u:
        return 0
    return 0


def best_resume_match_for_jd(
    req_slug: str,
    resume_slugs: List[str],
    adj: Dict[str, Set[str]],
    jd_slugs: Set[str],
    parent_of: Dict[str, str],
) -> Tuple[Optional[int], Optional[str], int]:
    """
    Shortest path to an eligible resume skill.

    Returns (total_hops, resume_slug, upward_hops). Decay factor should be
    ``decay ** upward_hops`` (child/specialization steps do not reduce score).
    """
    targets = {
        s
        for s in resume_slugs
        if s and eligible_resume_target_for_jd(req_slug, s, jd_slugs, parent_of)
    }
    if not targets:
        return None, None, 0
    if req_slug in targets:
        return 0, req_slug, 0
    if req_slug not in adj:
        return None, None, 0

    prev: Dict[str, str] = {}
    seen: Dict[str, int] = {req_slug: 0}
    q = deque([req_slug])
    while q:
        u = q.popleft()
        du = seen[u]
        for v in adj.get(u, ()):
            if v in seen:
                continue
            nv = du + 1
            seen[v] = nv
            prev[v] = u
            if v in targets:
                path: List[str] = [v]
                cur = v
                while cur != req_slug:
                    cur = prev[cur]
                    path.append(cur)
                path.reverse()
                upward = 0
                for i in range(len(path) - 1):
                    upward += _upward_steps_on_edge(path[i], path[i + 1], parent_of)
                return nv, v, upward
            q.append(v)
    return None, None, 0


def min_hops_and_nearest_resume(
    req_slug: str, candidate_slugs: List[str], adj: Dict[str, Set[str]]
) -> Tuple[Optional[int], Optional[str]]:
    """Shortest path ignoring JD eligibility; use ``best_resume_match_for_jd`` for scoring."""
    targets = {s for s in candidate_slugs if s}
    if not req_slug or not targets:
        return None, None
    if req_slug in targets:
        return 0, req_slug
    if req_slug not in adj:
        return None, None
    seen: Dict[str, int] = {req_slug: 0}
    q = deque([req_slug])
    while q:
        u = q.popleft()
        du = seen[u]
        for v in adj.get(u, ()):
            if v in seen:
                continue
            nv = du + 1
            seen[v] = nv
            if v in targets:
                return nv, v
            q.append(v)
    return None, None


def min_undirected_hops(req_slug: str, candidate_slugs: List[str], adj: Dict[str, Set[str]]) -> Optional[int]:
    """Shortest path length between JD canonical skill and any resume canonical skill."""
    hops, _ = min_hops_and_nearest_resume(req_slug, candidate_slugs, adj)
    return hops
