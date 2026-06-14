# KITMASH Agent Loop — Architecture Contract (v0.13)

*The single source of truth for the director. Both builders code against THIS
file. If the spec and your intuition disagree, the spec wins; if the spec is
wrong, flag it — do not silently diverge. Roadmap item 6, architecture decided
in `KITMASH-HANDOFF.md` §6.*

---

## 0. The one-sentence thesis

The agent is a **creative director, not a servo**: it shapes the run from
*outside* (the brief), nudges only at genuine forks (tie-only hooks), and learns
*after* (review → next brief). It NEVER makes a per-port LLM call. Its
intelligence lives in the brief it authors and the trace it reads — not in the
loop.

## 1. Doctrine inherited (violate → forked project)

- **Legality stays dumb; taste lives in the sampler.** The director is *more*
  taste, never new legality. It may reweight, bias, breed — never add a
  legality check.
- **The scorer is descriptive, NEVER the objective.** (Handoff §6, and the
  diary rider.) Selection across generations uses an **external fitness** that
  the scorer does not see and the sampler cannot directly optimize.
- **Trace everything.** Every director decision (brief authored, tie broken,
  repair chosen, generation reviewed, breeding event) appends to a trace, same
  spirit as `assembly_trace`. The loop must be replayable.
- **Built is not cooks.** A director that "ran" must have produced ships that
  *cook and gate*. Verify the artifact in the mode of use.

## 2. THE REGRESSION ANCHOR (load-bearing, non-negotiable)

The canonical fleet MUST stay byte-identical. Before any edit:

```
.venv/bin/python kitmash.py /tmp/x.json   →   md5 = 80ddaccccc594b2a7cc8c7b40a129086
                                              GS-α stats = (10, 9464, 3)
   (md5 re-baselined from e6aeccfe… by P3 hull weld-faces; stats invariant)
```

`test_kitmash.py` is 8/8 green at baseline. **The hooks are a no-op when no
director is attached.** With `director=None` the rng stream, the candidate
order, and every committed part are identical to today. This is THE acceptance
gate for the hook surgery. A director changes only NEW generations, never the
canonical 5.

## 3. The hook interface — EXACT contract (Reflex owns kitmash.py)

The `Assembler` gains one optional attribute, default `None`:

```python
class Assembler:
    def __init__(s, faction, seed, brief, generators, director=None):
        ...
        s.director = director          # None => byte-identical legacy path
```

`build()` passes it through: `build(..., director=None)` →
`Assembler(faction, seed, brief, generators, director=director)`.

### 3a. on_tie — the candidate fork

Site: `kitmash.py run()`, immediately after
`scored = sorted(((score(c),c) for c in cands), key=lambda e:-e[0])`
(currently ~line 695), BEFORE the `for sc,(part,...) in scored:` commit loop.

```python
if s.director is not None and len(scored) >= 2:
    s0 = scored[0][0]; s1 = scored[1][0]
    if s0 - s1 < s.director.tie_eps:          # genuine tie ONLY
        ranked = [c for _, c in scored]        # candidate tuples, best-first
        new_order = s.director.on_tie(ranked, s._tie_context(sp, host))
        if new_order is not None:
            scored = [(scored[i][0], scored[i][1]) for i in new_order]
            s.log(ev="tie_break", port=sp.pid,
                  among=[c[0].label for c in ranked],
                  chose=ranked[new_order[0]][0].label)
```

HARD RULES for `on_tie`:
- It is called ONLY when `director is not None` AND a genuine score-tie exists
  (`tie_eps`, default small, e.g. `0.05`). On a clear winner it is never called.
- It MUST be pure and **must not touch `s.rng`** (no rng consumption — that is
  what preserves replay for sibling generations).
- It returns a permutation (list of indices into `ranked`) or `None` (= keep
  order). It may only REORDER existing candidates; it may not invent or drop.
- `Assembler._tie_context(sp, host)` is a small read-only dict the surgeon adds:
  `{port_type, port_prio, placed_families: Counter, budget: dict(copy),
    faction: name}`. No mutable internals leak.

### 3b. on_repair_choice — the mediation fork

Site: where `propose_strut` returns multiple viable anchor/brace candidates
(`kitmash.py` ~`propose_strut`, the diagonal-anchor candidate list). When
`director is not None` and ≥2 viable braces exist, let the director rank them:

```python
if s.director is not None and len(viable) >= 2:
    pick = s.director.on_repair_choice(viable, s._repair_context(jpos, jaxis))
    if pick is not None: viable = [viable[i] for i in pick]
```

Same hard rules: director-gated, no rng, reorder-only, returns permutation or
`None`. If wiring this cleanly risks the regression, the surgeon may DEFER 3b
with a logged TODO and a one-line stub `on_repair_choice` that returns `None` —
3a is the load-bearing hook; 3b is the nice-to-have. **Document the decision.**

### 3c. Regression assertion (surgeon adds to test_kitmash.py)

A new gate `test_director_noop()`:
- run `kitmash.py` export with `director=None`, assert stats `(10,9464,3)` and
  that the produced JSON md5 == `80ddaccccc594b2a7cc8c7b40a129086` (P3 re-baseline
  of `e6aeccfe…`; or compare the in-memory export dict to a fresh `director=None`
  build — dict-equality).
- build one ship WITH a trivial director whose `on_tie` returns `None`
  (identity) and `tie_eps=0` → assert byte-identical to `director=None`
  (proves the gate fires only on real ties and identity-reorder is inert).

## 4. The Director — `director.py` (Director-agent owns this file)

Pure Python, imports from `kitmash` and `kitmash_houdini`. No `hou`, no `pxr`.
Heuristic policy by default; an LLM-backed `author_brief`/`review` is an OPTIONAL
subclass hook (`LLMDirector(Director)`) — do NOT make the core loop require a
network call. Per-port LLM calls are FORBIDDEN (handoff §6).

### 4a. Brief shape

A brief extends the existing `build()` inputs:

```python
Brief = dict(
    faction = GUILD | FERAL,          # which culture
    seed = int,
    wants = {family: weight},         # the taste vector
    heavy = float, span = float,      # cannon/wing gen params
    extra_gens = [...],               # optional gene pool additions
    # director-level knobs (optional, default to today's values):
    budgets = dict(mass=, silhouette=, parts=),
    tie_policy = str,                 # how on_tie breaks ties (see 4c)
    parent = str|None, mutation = str|None,   # lineage prose for the catalogue
)
```

`Director.author_brief(history) -> Brief`. `history` is the list of prior
generations' `(brief, diagnosis, fitness)`. Generation 0 returns seed briefs.
Later generations adjust knobs from diagnoses (see 4d).

### 4b. review(trace, stats) -> diagnosis  (mirror placard() archaeology)

Walk the trace exactly as `make_catalogue.py:placard()` does — count by `ev`,
read `metrics`. Produce a structured diagnosis, e.g.:

```python
diagnosis = dict(
    parts=, mass=, struts=, hoses=,
    rejects=Counter(by cause),
    spine_fails=, repairs=, adapters=,
    auctions=, evictions=, backjumps=,
    demand_unmet=Counter(by cause),
    ports_open=, families=Counter(placed family),
    strut_per_part=, monoculture=float (max family share),
)
```

The diagnosis is the director's *experience*; it drives the next brief.

### 4c. on_tie / on_repair_choice policy (the reflexes)

Deterministic, rng-free, parameterized by the brief's `tie_policy`. At least
these policies, selectable per brief:
- `"diversity"` — among tied candidates, prefer the family with the LOWEST
  placed count (fights monoculture).
- `"silhouette"` — prefer the candidate that best spends remaining silhouette
  budget (big reads first).
- `"faction"` — prefer the family that signals the faction (e.g. feral → more
  cannon/turret; guild → cleaner struct).
- `"identity"` — return `None` (the regression/test policy).

`on_repair_choice` default: prefer the most triangulated brace (largest
`sin(angle)` ⇒ most relief — handoff Lesson 6), tie-break by lowest added mass.

### 4d. author_brief diagnosis → knob rules (heuristic, descriptive)

Map diagnosis to next-brief adjustments. Examples (tune, document each):
- high `strut_per_part` or many `repairs` → reduce `heavy` and/or `wants[heavy_cannon]`,
  or raise `span` (longer lever braces sooner) — the ship is over-armed for its frame.
- many `demand_unmet(no_route)` → reduce demanding families (turret) or raise
  `budgets`; many `demand_unmet(supply_saturated)` → add a supplier gene.
- many `port_open` / `no_candidate` → broaden `wants` (more families wanted).
- `monoculture` high → switch `tie_policy="diversity"` and inject novelty (4f).

### 4e. Breeding
- `blend_gen_params(a, b, t=0.5) -> dict` — numeric interpolation of `heavy`,
  `span`, and any per-part gen_params; seed derived from both parents.
- `splice_trace(brief_a, brief_b) -> Brief` — recombine `wants` (per-family
  pick from whichever parent, or average) + inherit the fitter parent's knobs.
  Record `parent`/`mutation` prose so the catalogue can narrate the cross.

### 4f. evolve(generations, population, seed) -> lineage
The loop driver:
1. gen 0: seed briefs (≥1 guild, ≥1 feral).
2. each gen: `build()` each brief (with the director attached so hooks fire) →
   `review` each trace → score by **external fitness** (4g) + **novelty** →
   select survivors → breed → next briefs → periodic **scarcity shock** (4h).
3. return a lineage record: per ship `{name, brief, diagnosis, fitness,
   parents}`. The lineage is itself trace-spliceable and catalogue-able
   (caption seed for the Borges plates).

### 4g. External fitness (the Goodhart firewall — load-bearing)

Fitness is computed from the DIAGNOSIS, and deliberately does NOT reward the
internal `score()` value. It rewards *ship virtue*, e.g.:
`fueled (no demand_unmet) + family diversity + silhouette spent + LOW
strut_per_part (honest frame, not over-braced) + part-count in band`.
The sampler cannot directly push this — it optimizes `score()`, which fitness
ignores. Document the firewall explicitly in a module docstring.

> **Caveat (Cassandra charge 1, 2026-06-13):** the wall is enforced by
> *correlation direction* — `external_fitness` and `score()` are empirically
> anti-correlated (the scorer's `1/(1+1.5n)` diversity divisor and fitness's
> `(1−monoculture)` reward both punish family-stacking), not by a mechanical
> barrier. The promise the spec makes — "the sampler has no channel to push
> fitness directly" — holds (no code path connects them). But if a future brief
> is shown where `score()` and `external_fitness` co-climb, revisit this. The
> firewall is a load-bearing assumption, audited, not a theorem.

### 4h. Goodhart guards (the diary's rider, made code)
1. **Scorer ≠ objective** (4g).
2. **Novelty pressure**: penalize a generation whose ships collapse toward one
   silhouette/family mix (taste collapse). Reward lineage spread.
3. **Scarcity shocks**: periodically perturb `budgets`/`wants` so a single-run
   exploit cannot dominate the lineage.
4. **Lineage-pathology detector**: a function that flags
   "fitness climbing while diversity collapsing" — the Goodhart signature — and
   logs it as `ev="goodhart_warning"`. This is the explicit hook the adversary
   will test.
5. **Proportional verification (THE RIDER):** `review` is a cheap deterministic
   trace-walk by DEFAULT. The director must NOT spawn a tribunal per ship.
   Escalation to heavier review is gated on a detected *anomaly* (e.g. a
   pathology flag), with a `verification_budget` proportional to detected
   uncertainty, NOT to available compute. Encode this as an explicit policy
   knob, not a vibe. (See diary 2026-06-12 §"Long": "Goodhart lives in the
   review fan-out as surely as in the scorer.")

## 5. Tests — `test_director.py` (Director-agent owns)
- `test_noop_regression` — director with identity policy ⇒ canonical fleet
  byte-identical (overlaps surgeon's gate; both must hold).
- `test_tie_break_fires` — a rigged tie → on_tie chooses the diversity pick,
  `tie_break` event logged, ship still legal (no hard overlaps).
- `test_review_archaeology` — review of a known fleet trace returns the right
  counts (cross-check against `make_catalogue.py` audit numbers).
- `test_breeding` — blend/splice produce valid briefs; child builds & cooks.
- `test_goodhart_detector` — a synthetic lineage with rising fitness + falling
  diversity trips `goodhart_warning`; a healthy one does not.
- `test_evolve_smoke` — `evolve(generations=2, population=3)` runs, every ship
  cooks (legal, fueled-or-logged), lineage record well-formed.

## 6. Two-repo sync & commit discipline
- Build in the LAB dir (`…/Houdini Kitbash Blender Dream Parts Factory/`).
- After each artifact gates green: `cp` to `~/Desktop/kitmash/` (permission rule
  exists), commit per artifact in BOTH repos with a message naming the piece.
- `git diff --check` before every commit (no conflict markers).
- Cook-and-gate ANYTHING that touches geometry; for the loop, "cook" = the
  ship builds, is legal (`no_hard_overlaps`), and round-trips if exported.
- Remember: a green gate can still hide a body pointing backwards. If a ship
  looks wrong, suspect handedness before tolerances.
