# Cassandra Audit — KITMASH Agent Loop (director.py / kitmash.py / test_director.py)

*Adversarial review against AGENT-LOOP-SPEC.md v0.13. I assume every green test hides a body.*
*Date: 2026-06-13. Tooling: `../.venv/bin/python`. No source files were modified.*

**Headline:** The regression anchor holds, the firewall holds, the hooks are genuinely inert
when `director=None`, and the ships actually cook. BUT two of the spec's own Goodhart guards
are softer than they advertise: the **Goodhart detector has a reproducible false negative**
(blind to *sustained* collapse), and the **proportional-verification rider inflates its budget
on fully-healthy generations** — the diary's exact sin, lurking. Both are real and reproducible.

---

## Charge 1 — The scorer firewall (§4g). VERDICT: HOLDS

**Claim:** `external_fitness` is independent of `score()`; the sampler cannot game fitness.

**Evidence.**
- Static trace: `external_fitness(s, diag)` (director.py:426) takes *only* the `diag` dict.
  Grep for `score` in director.py returns only docstring mentions and the unrelated `external_fitness`/
  `scarcity` tokens — no code path reads the candidate `score()` value. The two quantities are
  computed in different modules and never meet.
- Dynamic attack — try to game `score()` by stacking one beloved family (`wants={'heavy_cannon':100.0,...}`):
  ```
  ATTACK (stack heavy_cannon, want=100): monoculture=0.429  external_fitness=5.5556
  BALANCED:                              monoculture=0.222  external_fitness=10.6016
  ```
  Gaming the internal scorer LOWERED external fitness (5.56 < 10.60). The wall is real *and*
  anti-correlated: `score()`'s own `(1+1.5*n)` divisor (kitmash.py:718) suppresses repeats, and
  `external_fitness` rewards `n_fam*(1-monoculture)`. Stacking loses on both sides.

**Note (not a break, but record it):** the firewall is enforced by *correlation direction*, not
by a structural barrier. `external_fitness` and `score()` happen to disagree on monoculture; they
are not provably orthogonal for all briefs. No counterexample found, but the wall is "empirically
anti-correlated," not "mechanically impossible." Acceptable for the doctrine as written (§4g says
*the sampler has no channel to push fitness directly* — confirmed: there is no channel).

---

## Charge 2 — Proportional-verification rider (§4h.5). VERDICT: WEAK (rider violated in spirit; harmless today)

**Claim (spec & docstring):** heavy review is gated on a *detected anomaly*; a clean/green
generation gets **zero** extra budget. "An agent that spawns eighty skeptics for every green
task has confused thoroughness with diligence."

**The body I found.** A generation in which **every ship is legal AND fueled AND
family-diverse AND high-fitness** — the picture of health — still spawns a non-zero
verification budget, because `verification_plan` (director.py:516) treats
`gen_record["diversity"] < 0.5` as an anomaly (`taste_collapse`), and `diversity` here is
`lineage_novelty` = *distinct family-SET signatures across ships*, which has nothing to do with
ship health.

**Reproduction — the real `evolve()` run does this on BOTH generations:**
```
GEN 0 diversity=0.333 anomalies=[('taste_collapse',1)] budget=1   ALL SHIPS HEALTHY (legal+fueled): True
GEN 1 diversity=0.333 anomalies=[('taste_collapse',1)] budget=1   ALL SHIPS HEALTHY (legal+fueled): True
```
**Worst case (the charge's own ask — many ships, all healthy):**
```
8 healthy ships, identical rich signatures:  diversity=0.125  anomalies=[goodhart_signature, taste_collapse]  budget=2
8 healthy ships, ALL distinct signatures:    diversity=1.0    budget=0
```
A converged-but-healthy fleet (the *expected* outcome of selection pressure) is punished with
verification budget purely for converging. That is the diary's automated sin: thoroughness on a
green task, triggered by sameness rather than sickness.

**Why WEAK and not BROKEN:** `verification_budget` is currently **computed and recorded but never
consumed** — nothing in `evolve()` spawns extra reviewers from it (grep: only set at director.py:80,
523; read nowhere as a loop driver). So the bloat is *nominal* today (a number in the lineage
record), not wasted compute. It becomes a real BROKEN the moment someone wires the budget to actual
work, exactly as the docstring invites ("a few targeted checks").

**The test masks it.** `test_goodhart_detector` (test_director.py:304) only checks "clean" with
**2 ships of deliberately disjoint families** (diversity 1.0 → budget 0). It never tests the
realistic converged-healthy fleet, so the green test asserts nothing about the case that actually
occurs in `evolve()`.

**Exact line:** `director.py:516` — `if gen_record["diversity"] < 0.5: anomalies.append(("taste_collapse",1))`.
`diversity` is `lineage_novelty` (director.py:448), a *novelty* metric, not a *health* metric.
Conflating "ships converged" with "anomaly worth extra verification" IS the rider violation.

---

## Charge 3 — Goodhart detector (§4h.4). VERDICT: BROKEN (reproducible false negative)

**Claim:** flags "fitness climbing while diversity collapsing."

**The body.** `lineage_pathology` (director.py:481) fires only when
`fit > prev_fit + 1e-9 AND diversity < prev_div - 1e-9` — diversity must be **strictly
decreasing**. Once a lineage has *already* collapsed and diversity holds *flat* at a low floor,
fitness can climb forever and the detector stays silent. That is precisely the Goodhart endgame:
find the gamed config once, then farm it at stable-low diversity.

**Reproduction (sequence of (fitness, diversity) generations):**
```
gen0 fit=5.0 div=0.9 -> clean
gen1 fit=6.0 div=0.3 -> FLAGGED      # the transition is caught (once)
gen2 fit=7.0 div=0.3 -> clean        # rising fitness on a mono-culture lineage...
gen3 fit=8.0 div=0.3 -> clean        # ...completely unflagged
gen4 fit=9.0 div=0.3 -> clean
```
And the degenerate extreme passes too: `lineage_pathology(100.0, 0.1, 1.0, 0.1)` → `None`
(fitness ×100 at pinned-low diversity, no warning).

**This is reachable in the real loop.** The actual `evolve(2,3)` run sits at `diversity=0.333`
across both generations. Had fitness ticked up between them, the detector would not fire — the
loop is already living in the blind spot.

**False positive:** none of concern — the detector fires exactly on the literal signature
(`fit up + div down`), including benign churn, but that is acceptable conservatism.

**Exact line:** `director.py:481` — the `diversity < prev_div - 1e-9` clause. A sustained-collapse
guard (e.g. flag when `fit` rises AND `diversity` is below an absolute floor regardless of
direction) is missing. The detector watches the *derivative* and ignores the *level*.

---

## Charge 4 — Regression no-op. VERDICT: HOLDS

**md5 confirmed:** `../.venv/bin/python kitmash.py /tmp/cass.json && md5sum` →
`e6aeccfe352bba16f288785ea23e5bc3` ✓ (spec §2 anchor). GS-α stats `(10, 9464, 3)` ✓.
`test_director.py` 6/6 PASS; the surgeon's gate inside it re-derives the same md5.

**Can the on_tie block EVER perturb the canonical fleet?** No, structurally.
- All 5 canonical builds in `kitmash.py __main__` (lines 1049–1060) call `build(...)` with **no
  `director=` argument** → `director=None` (default, build sig at kitmash.py:994).
- With `director=None`, the on_tie guard `if s.director is not None ...` (kitmash.py:734) and the
  repair guard (kitmash.py:498) short-circuit *before* any director method is reached. The hook
  bodies are dead code on the canonical path.
- Independent proof: `director=None` vs an identity director (`tie_eps=0`) produce byte-identical
  geometry `(10, 9464, 3)`; a real diversity director (`tie_eps=0.05`) on GS-α logs **0 tie_breaks**
  and also yields `(10, 9464, 3)` — no genuine score-tie occurs in the canonical fleet, so even an
  active director changes nothing.
- The hook draws no rng: `_tie_context` (kitmash.py:633) exposes no `rng` key; `on_tie` is placed
  *after* `scored=sorted(...)` (where all `score()` rng draws complete) and only permutes an existing
  list. Confirmed identity == None above.

---

## Charge 5 — Doctrine creep. VERDICT: HOLDS

- **No legality check disguised as taste.** Grep of director.py for `anchor_vols|reject|forbid|
  illegal|disallow|veto|block` hits only: read-only `reject`-counting in `review()` (director.py:174)
  and the comment at :504. `no_hard_overlaps` (director.py:583) is a *post-hoc, read-only* cook
  check over `a.ledger`; it sets `diag['legal']` for fitness/anomaly bookkeeping and **never blocks
  a placement or feeds the sampler**. Legality stays dumb in kitmash; the director adds taste, not law.
- **Director does not mutate assembler internals through the "read-only" context.** Proven: a
  malicious director that mutates `ctx['placed_families']['HACK']=999` and `ctx['budget']['mass']=-1`
  leaves `a.budget == {'mass':1000,...}` untouched — `_tie_context` returns a fresh `Counter` and a
  `dict()` copy (kitmash.py:636–639). No mutable internal leaks.
- **No hook touches `s.rng`.** Grep `rng` in director.py: only docstring assertions ("rng-free").
  `on_tie`/`on_repair_choice`/`scarcity_shock` consume no randomness; `scarcity_shock` uses the gen
  index. Replay for sibling generations is preserved.
- **on_repair_choice is a genuine no-op (3b deferred).** Returns `None` unconditionally
  (director.py:276); verified at runtime with a 2-brace input → `None`. The legacy `best`-accumulator
  (kitmash.py:484) stays authoritative.

---

## Charge 6 — Built is not cooks. VERDICT: HOLDS

`evolve(generations=2, population=3)` run; ships inspected directly (not via the summary):
```
G0-00 parts=10 mass=9464 legal=True unmet=0 fit=10.60  fams={engine:1,fuel_tank:1,wing:2,heavy_cannon:2,antenna:2,sensor_pod:1}
G0-01 parts=10 mass=10604 legal=True unmet=0 fit=10.43 ...
G0-02 parts=10 mass=9464 legal=True unmet=0 fit=10.60 ...
G1-00..02 parts=10 legal=True unmet=0 fit=10.60
```
Every ship is **legal** (independent `no_hard_overlaps` re-check on each `assembler`, not the cached
flag) AND **fueled** (`demand_unmet` sum = 0). lineage record well-formed; `best_overall` set. The
loop's success claim matches the artifacts. Ships cook.

*(Side observation feeding Charges 2 & 3: the fleet converges hard — every ship lands the same
6-family signature, diversity pinned at 0.333. Healthy, but monotonous; this is the exact terrain
where the two soft guards above fail to bite.)*

---

## RESOLUTION (orchestrator, 2026-06-13 — fixes applied + re-verified)

- **Charge 3 (CRITICAL) — FIXED.** `lineage_pathology` now flags on the LEVEL
  as well as the slope: `rising AND (falling OR diversity < collapse_floor)`,
  with a new `collapse_floor=0.5` knob. Re-ran both repros: `(7.0,0.3,6.0,0.3)`
  → FLAGGED (`fitness_up_diversity_floored`); `(100.0,0.1,1.0,0.1)` → FLAGGED.
  A healthy *stable* converged fleet (flat fitness, low diversity) stays clean —
  the detector requires rising fitness. New test assertions cover both.
- **Charge 2 (SHOULD-FIX) — FIXED.** `taste_collapse` now requires novelty
  ACTIVELY eroding into the floor (`diversity < floor AND diversity < prev_div`),
  not mere low diversity. The real-evolve healthy converged fleet (8 ships,
  diversity 0.333 flat) now draws budget **0** (was 1–2). New test asserts it.
- **Charge 1 (DEFER) — noted.** Added a one-line "empirical, not mechanical"
  caveat to AGENT-LOOP-SPEC.md §4g. No exploit exists; flagged for future briefs.
- **Charge 5 / 3b (DEFER) — no action,** by design and documented.

Post-fix gate: `test_director.py` 6/6, `test_kitmash.py` 9/9, regression md5
`e6aeccfe352bba16f288785ea23e5bc3` unchanged. The cliff is now watched as well
as the slope.

---

## Original triage — SUPERSEDED by the Resolution above (archival)

*The items below are the ORIGINAL adversarial triage. Charges 2 & 3 were
subsequently FIXED — see the Resolution section above. Retained for provenance,
not as open work.*

### CRITICAL (fix before commit)
1. **Goodhart detector false negative (Charge 3, director.py:481).** The detector is blind to
   *sustained* collapse — the actual Goodhart endgame. Reproducible: fitness ×100 at flat-low
   diversity → no warning. The loop already runs at flat diversity=0.333, i.e. inside the blind
   spot. This is the *one explicit guard the spec says the adversary will test* (§4h.4) and it does
   not catch the failure it names. **Fix:** add a level-based clause — flag when fitness rises AND
   diversity is below an absolute floor, regardless of direction. Add a test for the
   collapse-then-climb sequence (the current test only checks the single transition).

### SHOULD-FIX
2. **Verification rider inflates on healthy generations (Charge 2, director.py:516).**
   `taste_collapse` keys off `lineage_novelty` (a sameness metric), so a fully-legal/fueled
   converged fleet draws verification budget for converging — the diary's automated sin. Harmless
   only because the budget is never consumed *yet*. **Fix:** gate `taste_collapse` on novelty-drop
   *combined with* a health or fitness-trajectory signal, not novelty alone; and add a test asserting
   `budget==0` for a *many-ship, identical-rich-signature, all-healthy* generation (the test's
   current "clean" case uses 2 disjoint ships and never exercises this).

### DEFER (with reason)
3. **Firewall is anti-correlation, not a mechanical barrier (Charge 1).** No exploit found and the
   spec only promises "no channel to push fitness directly" — which holds. Defer unless a future
   brief is shown where `score()` and `external_fitness` co-climb. Worth a one-line note in §4g that
   the wall is empirical, not structural.
4. **on_repair_choice 3b still deferred (Charge 5).** By design and documented; the no-op is real.
   No action.

---

*A green gate can hide a body pointing backwards. Two of the six guards here are pointing the
right way but with their eyes closed. The fleet builds, the wall holds, the anchor is byte-exact —
but the lineage-pathology detector watches the slope and forgets the cliff it's already standing on.*

---

## v0.7 Adversarial Pass — diversity selection + bureaus (2026-06-13)

*Second Cassandra pass, branch `v0.7-coherence-and-diversity`. New surface: diversity-aware
`select_survivors` (§2a) and the four bureaus (§2c). I assume every green test hides a body and
trust only what reproduces at the command line. Tooling: `../.venv/bin/python` (numpy present).
No source modified.*

**Headline:** All three directive charges HOLD. The eligibility filter in `select_survivors` is a
genuine hard pre-filter — no broken ship buys a survival slot on novelty even at fitness 99 with
`diversity_weight` cranked to 0.99. The firewall survives the bureau refactor: every bureau
reweights the SAME diagnosis-only terms; no `score()` channel exists, and no bureau co-climbs with
the family-stack exploit. **One latent WEAK finding** (not a directive charge, found while tracing):
the `best` / `best_overall` selection at director.py:604 / :633 ranks ships by raw fitness with NO
eligibility filter — asymmetric with `select_survivors`. Unreachable with the current seeds (no
illegal ship ever tops fitness), but it is the only place an illegal-but-high-fitness ship could be
crowned and fed into `history` → `author_brief`. Deferred, not blocking.

### Quick confirmations (re-derived, not trusted)
- Canonical md5: `../.venv/bin/python kitmash.py /tmp/cass_fleet.json && md5sum` →
  `e6aeccfe352bba16f288785ea23e5bc3` ✓ (anchor holds).
- `test_director.py` → ALL DIRECTOR GATES PASS (7/7). `test_kitmash.py` → ALL GATES PASS (9/9).
- Survivors across real runs, INDEPENDENT `no_hard_overlaps` re-check on each `assembler` (not the
  cached flag) + `demand_unmet` sum: `evolve(3,10,0)` **0 violations**; `evolve(3,6,0)` **0
  violations**.
- Diversity genuinely moved off the flat 0.333: `evolve(3,10,0)` → `[0.3, 0.4, 0.5]`;
  `evolve(3,6,0)` → `[0.5, 0.667, 0.667]`. Off-0.333 = True both runs.

---

### Charge A — Can a broken ship win a survival slot on novelty? VERDICT: HOLDS

**Claim:** eligibility (`legal AND sum(demand_unmet)==0`, director.py:794–796) is a HARD pre-filter
that runs BEFORE any novelty score; a signature reading "novel" because a required family is MISSING
(a broken ship) can never buy a survivor slot.

**Reproduction.** Fixtures fed directly to `select_survivors`: a fitness-99 maximally-novel-but-
ILLEGAL ship and a fitness-99 novel-but-UNFUELED (`demand_unmet={no_route:2}`) ship, mixed with
legal+fueled fitness-6..8 ships.
```
CHARGE A — selected: ['LEGAL-A', 'LEGAL-B', 'LEGAL-C']     # both broken ships excluded
  no broken ship in survivors: True
```
Stress with `diversity_weight=0.99` (novelty almost fully dominant) + a broken ship carrying a
UNIQUE 4-family signature against 6 legal ships sharing one signature:
```
div_weight=0.99 selected: ['L0','L1','L2','L3','L4']       # broken-unique present?: False
unfueled-unique selected: ['L0','L1','L2','L3','L4']       # present?: False
```
The filter precedes the marginal-novelty loop by construction (director.py:794 vs the `while`
at :807), so cranking `diversity_weight` cannot reach across it.

**Edge — every ship broken (`pool = eligible or ships`, director.py:799).** Returns the raw pool
(broken ships), e.g. `['B1','B2']`, none legal+fueled. This is the documented degenerate fallback so
`evolve()` never starves. **Safe in practice:** it only triggers when ZERO ships are eligible, and
the bureau seeds never produce such a generation (the 0-violation runs above). It is a starvation
guard, not a novelty-bypass — novelty plays no role on this path. Empty input → `[]`.

VERDICT: **HOLDS.** Novelty is structurally downstream of eligibility; no broken ship is selectable
while any eligible ship exists.

---

### Charge B — Does diversity_weight or any bureau open a NEW score()→fitness channel? VERDICT: HOLDS

**Claim:** `external_fitness` reads ONLY the post-hoc diagnosis; the bureau table reweights the same
diagnosis-only terms; no argument carries a `score()` value.

**Static trace.** `fitness_terms(diag, lineage_ctx=None)` (director.py:727) and
`external_fitness(s, diag, bureau=None, lineage_ctx=None)` (director.py:767). Every read in the
fitness path is a `diag` key: `{adapters, demand_unmet, families, hoses, legal, monoculture, parts,
repairs, strut_per_part}`. The only `score` tokens in the whole fitness path are five DOCSTRING
mentions — zero code reads it. `lineage_ctx` carries only `sibling_sigs`, each a `_story_sig(diag)` =
`(frozenset(families), frozenset(rejects))` — pure diagnosis, no geometry, no `score()`.
`diversity_weight` lives entirely inside `select_survivors` and never touches `external_fitness`.

**Dynamic attack — family-stack under every bureau** (game `score()` by hammering one family; compare
`external_fitness` of the gamed ship vs the balanced ship):
```
                 balanced   stacked
None             10.6016    5.5556    stack < bal
Guild-Structural 10.0344    6.8704    stack < bal
Feral-Repair      8.1008    2.5278    stack < bal
Service-Network   6.7008    3.3278    stack < bal
Austerity        11.7680    6.8130    stack < bal
```
No bureau rewards the stack. (The naive stack also goes unfueled, so to remove that free help I
re-ran with a LEGAL+FUELED wing-stack: `bal None-fit 10.602` vs `stk 8.405` — still lower. The
sampler's own `1/(1+1.5n)` divisor suppresses repeats, so a high want cannot actually pile one
family without losing the diversity term.)

**Feral-Repair specific (gratuitous repairs):** confirmed that under Feral, a more-scarred ship
(6 struts / 4 repairs) scores HIGHER than a clean one (8.5339 > 5.9339) while the None objective
reverses it (8.2344 < 8.9011). This is the **intended inversion** (spec: "the repair scars ARE the
aesthetic"), not a `score()` channel — `bracing`/`repair` are pure diagnosis terms. See Charge C for
whether it is gameable.

**Austerity specific (sibling-trace channel):** `antirepeat` reads `sibling_sigs`; collide → 6.2000,
novel → 9.2000. The channel responds only to whether THIS ship's `(families, rejects)` matches
already-judged siblings — all diagnosis-derived. No sampler-controllable quantity enters.

VERDICT: **HOLDS** for every concern. The firewall is enforced in exactly one place
(`fitness_terms`), and the bureau refactor did not widen it.

---

### Charge C — Do bureau objectives stay anti-correlated with the sampler? VERDICT: HOLDS (with one intended-inversion note)

**Claim:** for each of the 4 bureaus, the sampler-gamed (family-stacked) ship scores no higher than
the balanced ship.

**Reproduction.** Same table as Charge B: under all five objectives the stacked ship scores strictly
lower (None 5.56<10.60, Guild 6.87<10.03, Feral 2.53<8.10, Service 3.33<6.70, Austerity 6.81<11.77).
No accidental co-climb. The two non-obvious bureaus checked individually:

- **Service-Network:** rewards `service` (reactor/turret/radiator present) + `plumbing` (hoses). A
  family-stacked ship lacks service families and routing, so it scores low (3.33). Anti-correlated.
- **Austerity:** `antirepeat` weight 3.0 means a ship retelling its siblings' story is heavily
  penalised; the stack (monoculture story) loses. Anti-correlated.

**Feral-Repair — intended inversion vs gameable exploit (the directive's explicit ask).** Feral
DOES reward a worse-engineered (more-braced) ship over a cleaner one — by design. The test for
"exploit" is whether a sampler can drive fitness UP without bound by manufacturing failures. It
cannot, because the climb is **capped and gated**:
- `bracing = min(2.0, spp/OK)` and `repair = min(2.0, (repairs+adapters)/3)` are both **saturated at
  2.0** (director.py:743–745). Past the cap, more scars add nothing.
- More importantly, a ship that fails so hard it goes **illegal or unfueled is filtered out of
  `select_survivors`** before fitness is consulted. I confirmed an over-scarred ship that loses
  legality scores feral_fit=9.7672 (higher than the legal scarred 8.5339, because only the `legal`
  term zeroes) — BUT it is ejected by the Charge-A eligibility filter, so the perverse score never
  buys a survivor slot.

So Feral's inversion is the **intended aesthetic**, bounded by saturation and walled by eligibility —
not a runaway exploit.

VERDICT: **HOLDS.** No bureau co-climbs with the sampler; Feral's reward for scars is intended,
capped, and eligibility-gated.

---

### Latent finding (NOT a directive charge) — `best` / `best_overall` skip the eligibility filter. VERDICT: WEAK

While tracing every fitness-ranking site I found an asymmetry: `select_survivors` filters on
eligibility, but `gen_record["best"]` (director.py:604, `max(gen_record["ships"], key=fitness)`) and
`lineage["best_overall"]` (director.py:633) rank ALL ships by raw fitness with **no eligibility
filter**.

**Reproduction (ranking logic, two-ship fixture, Feral-Repair):**
```
gen 'best' (line 604, NO eligibility filter) = ILLEGAL-highfit  legal= False
survivors (filtered)                          = ['legal-lowfit']
```
If a generation ever produced an illegal-but-top-fitness ship (most reachable under Feral-Repair,
whose `bracing`+`repair` terms climb to 9.77 while `legal` zeroes), it would be crowned `best` and
`best_overall`, AND `best["brief"]` feeds `history` (director.py:624) → `author_brief` → the next
brief. The diversity reward would then steer the lineage off a DEAD ship.

**Why WEAK, not BROKEN:** unreachable with the shipped seeds. In `evolve(3,10,0)`, `evolve(3,6,0)`,
and `evolve(2,3,0)` the gen-best and best_overall are ALL legal+fueled (re-derived: 0 bad). The body
exists but no current seed walks into it. It becomes BROKEN the moment a brief (or a future bureau)
can produce a high-fitness illegal ship.

---

### TRIAGE

**CONFIRMED (must fix before commit):** none. All three directive charges HOLD; the anchor, tests,
survivor health, and diversity gains all re-derive clean. Nothing blocks the commit.

**DEFERRED (with reason):**
1. **`best`/`best_overall` skip eligibility (director.py:604, :633) — WEAK, latent.** Defer:
   unreachable with current seeds (0 bad bests across three real runs). Cheap hardening when touched:
   reuse the `select_survivors` eligibility predicate when picking `best`/`best_overall`, or fall
   back to raw only if no eligible ship exists (mirror `pool = eligible or ships`). Add a test that
   injects an illegal high-fitness ship and asserts it is not crowned.
2. **Charge-A all-broken fallback (`pool = eligible or ships`, director.py:799) returns broken
   ships.** Defer: documented starvation guard, only fires when zero ships are eligible (never in
   real runs), and novelty plays no role on that path. Worth a one-line log/warning when the fallback
   triggers so a degenerate generation is visible in the lineage record.

*The wall held the refactor. The bureaus pull in genuinely different directions yet every one of them
still prefers a live, diverse ship to a gamed monoculture — and the eligibility filter is a real
gate, not a painted door. The one crack is cosmetic today: `best` looks at fitness without first
asking whether the ship is alive, and only Feral's inverted objective could ever make that matter.*
