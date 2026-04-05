:- dynamic known_skill/1.
:- dynamic alias_alias_to_canonical/2.
:- dynamic subskill_child_parent/2.

%% Canonical slug: known skill or resolved alias (single hop from DB; multi-hop below).
canonical(S, S) :- known_skill(S).
canonical(A, C) :- alias_alias_to_canonical(A, C).
canonical(A, C) :- alias_alias_to_canonical(A, B), canonical(B, C).

%% Parent is more general, Child is more specific (child row points to parent in DB).
generalizes(Parent, Child) :- subskill_child_parent(Child, Parent).
generalizes(Parent, Grandchild) :-
    subskill_child_parent(Grandchild, Mid),
    generalizes(Parent, Mid).

%% Job requires Cr; candidate has Cu. Covered if same skill or candidate is more specific.
covers(UserSkill, Req) :-
    canonical(UserSkill, Cu),
    canonical(Req, Cr),
    (Cu = Cr ; generalizes(Cr, Cu)).

%% Chain of slugs from general (Req) down to specific (Cand), each step a direct child edge.
specialization_chain(G, G, [G]).
specialization_chain(G, S, [G|T]) :-
    G \= S,
    subskill_child_parent(M, G),
    generalizes(M, S),
    specialization_chain(M, S, T).

%% ---------------------------------------------------------------------------
%% Meta-interpreter: reify proofs for selected goals (extend with new clauses).
%% Same logical conditions as covers/2, but binds a structured Proof term.
%% ---------------------------------------------------------------------------
mi_solve(covers(U, R), proof(exact, Canon)) :-
    canonical(U, Cu),
    canonical(R, Cr),
    Cu = Cr,
    Canon = Cu.

mi_solve(covers(U, R), proof(specializes, Chain)) :-
    canonical(U, CandC),
    canonical(R, ReqC),
    CandC \= ReqC,
    generalizes(ReqC, CandC),
    specialization_chain(ReqC, CandC, Chain).

%% Undirected step on the skill tree (parent/child treated the same for distance).
tree_neighbor(A, B) :- subskill_child_parent(A, B).
tree_neighbor(A, B) :- subskill_child_parent(B, A).

%% decay^Hops (legacy undirected hop count). Job compatibility scoring in Python uses
%% upward-only hops along parent edges; child/specialization steps are 1×.
%% Queried from Python via PySwip alongside the same graph facts as covers/2.
compound_tree_factor(Hops, Decay, F) :-
    integer(Hops),
    Hops >= 0,
    Hops < 100,
    F is Decay ** Hops.
