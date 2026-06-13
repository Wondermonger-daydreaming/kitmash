"""director.py — KITMASH agent loop, the creative director (roadmap item 6).

A creative director, NOT a servo. It shapes the run from *outside* (the
brief it authors), nudges only at genuine forks (the tie-only hooks in
kitmash.Assembler), and learns *after* (review the trace → author the next
brief). It NEVER makes a per-port LLM call (handoff §6). Its intelligence
lives in the brief it authors and the trace it reads — not in the loop.

================================================================================
THE GOODHART FIREWALL (load-bearing — AGENT-LOOP-SPEC §4g/§4h)
================================================================================

The internal `score()` in kitmash.Assembler.run() is the SAMPLER's taste. It
is *descriptive*: it ranks candidates so the loop can commit one. It is
explicitly NEVER the objective of evolution.

Cross-generation selection uses `external_fitness(diagnosis)`, computed ONLY
from the post-hoc `review()` diagnosis — counts of placed families, fueling,
silhouette spent, strut/part ratio, part-count band. The fitness function
*never reads* the candidate `score()` value, and the sampler has no channel to
push fitness directly: it optimizes `score()`, which fitness ignores. The two
quantities live on opposite sides of a wall. A run that games `score()` (e.g.
by stacking one beloved family) is PENALIZED by fitness (monoculture, low
diversity), not rewarded. That asymmetry is the firewall.

Guards layered on top (§4h):
  1. scorer ≠ objective (above).
  2. novelty pressure — a generation collapsing toward one silhouette/family
     mix is penalized (see `lineage_novelty`); lineage spread is rewarded.
  3. scarcity shocks — `scarcity_shock()` perturbs budgets/wants periodically
     so a single-run exploit cannot dominate the lineage.
  4. lineage-pathology detector — `lineage_pathology()` flags "fitness rising
     while diversity falling" (the Goodhart signature) and logs
     ev="goodhart_warning". This is the explicit hook the adversary tests.
  5. PROPORTIONAL VERIFICATION (THE RIDER) — review is a cheap deterministic
     trace-walk BY DEFAULT. Heavier verification is gated on a detected
     anomaly, with a `verification_budget` proportional to detected
     UNCERTAINTY, not to available compute. See `verification_plan()`.

     Diary 2026-06-12 §"Long": "Goodhart lives in the review fan-out as surely
     as in the scorer. An agent that spawns eighty skeptics for every green
     task has confused thoroughness with diligence."
================================================================================
"""
from collections import Counter

from kitmash import GUILD, FERAL, build, gen_radiator, gen_reactor, gen_turret


# ---------------------------------------------------------------- brief shape
def make_brief(faction, seed, wants, heavy=1.0, span=3.2, extra_gens=(),
               budgets=None, tie_policy="diversity", parent=None,
               mutation=None):
    """A Brief is a plain dict (AGENT-LOOP-SPEC §4a). It extends build()'s
    inputs with director-level knobs that default to today's values."""
    return dict(
        faction=faction, seed=int(seed), wants=dict(wants),
        heavy=float(heavy), span=float(span),
        extra_gens=tuple(extra_gens),
        budgets=dict(budgets) if budgets else dict(mass=11000,
                                                   silhouette=3.2, parts=14),
        tie_policy=tie_policy, parent=parent, mutation=mutation)


# fitness/diagnosis tuning constants — descriptive heuristics, all documented
PART_BAND = (7, 12)            # "honest" part count band
STRUT_PER_PART_OK = 0.6        # above this the frame is over-braced
TIE_EPS_DEFAULT = 0.05


# ================================================================== Director
class Director:
    """Heuristic, rng-free, network-free creative director."""

    def __init__(s, tie_eps=TIE_EPS_DEFAULT, verification_budget=0,
                 collapse_floor=0.5):
        s.tie_eps = tie_eps
        # PROPORTIONAL VERIFICATION knob: the *baseline* heavy-review budget is
        # ZERO. It is raised ONLY by verification_plan() in response to a
        # detected anomaly — never as a function of available compute.
        s.verification_budget = verification_budget
        # absolute diversity floor: the LEVEL below which sustained-low novelty
        # plus rising fitness is the Goodhart endgame (not just a falling slope).
        s.collapse_floor = collapse_floor
        s._brief = None        # the active brief (sets tie_policy for on_tie)

    # ----------------------------------------------------------- 4a authoring
    def author_brief(s, history):
        """history: list of prior (brief, diagnosis, fitness). Generation 0
        (empty history) returns a list of seed briefs (≥1 guild, ≥1 feral).
        Later: adjust knobs from the most recent diagnosis (§4d)."""
        if not history:
            return s._seed_briefs()
        brief, diag, _fit = history[-1]
        return [s._adjust(brief, diag)]

    def _seed_briefs(s):
        wants_g = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                   "heavy_cannon": 1.4, "antenna": 0.8, "sensor_pod": 0.6}
        wants_f = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                   "heavy_cannon": 2.2, "sensor_pod": 1.0, "antenna": 0.4}
        return [
            make_brief(GUILD, 7, wants_g, heavy=1.0, span=3.0,
                       tie_policy="diversity"),
            make_brief(FERAL, 23, wants_f, heavy=1.4, span=3.4,
                       tie_policy="faction"),
        ]

    def _adjust(s, brief, diag):
        """4d: map a diagnosis to next-brief knob adjustments. Descriptive
        heuristics, each documented. Returns a NEW brief (does not mutate)."""
        wants = dict(brief["wants"])
        heavy, span = brief["heavy"], brief["span"]
        budgets = dict(brief["budgets"])
        tie_policy = brief["tie_policy"]
        notes = []

        # over-armed for its frame: many struts/repairs → dial back the cannon
        if diag["strut_per_part"] > STRUT_PER_PART_OK or diag["repairs"] >= 3:
            heavy = round(max(0.7, heavy * 0.85), 3)
            if "heavy_cannon" in wants:
                wants["heavy_cannon"] = round(wants["heavy_cannon"] * 0.8, 3)
            span = round(span * 1.05, 3)         # longer lever braces sooner
            notes.append("over-braced→lighter cannon, longer span")

        # demand left unfueled by saturation → add a supplier gene's want
        if diag["demand_unmet"].get("supply_saturated", 0) > 0:
            wants["reactor"] = round(wants.get("reactor", 0.0) + 1.0, 3)
            notes.append("unmet(saturated)→more supply")
        # demand unrouted → ease the demanding family / raise budgets
        if diag["demand_unmet"].get("no_route", 0) > 0 or \
           diag["demand_unmet"].get("congestion", 0) > 0:
            if "turret" in wants:
                wants["turret"] = round(wants["turret"] * 0.7, 3)
            budgets["parts"] += 1
            notes.append("unmet(route)→fewer demanders, +parts")

        # ports left open / no candidate → broaden the taste vector
        if diag["ports_open"] >= 2:
            for fam in ("sensor_pod", "antenna"):
                wants[fam] = round(wants.get(fam, 0.0) + 0.5, 3)
            notes.append("open ports→broader wants")

        # monoculture high → fight it with diversity policy + novelty
        if diag["monoculture"] > 0.5:
            tie_policy = "diversity"
            least = min(("heavy_cannon", "wing", "sensor_pod", "turret"),
                        key=lambda f: diag["families"].get(f, 0))
            wants[least] = round(wants.get(least, 0.0) + 0.7, 3)
            notes.append("monoculture→diversity + novelty inject")

        return make_brief(
            brief["faction"], brief["seed"] + 1, wants, heavy=heavy, span=span,
            extra_gens=brief["extra_gens"], budgets=budgets,
            tie_policy=tie_policy, parent=brief.get("parent"),
            mutation="; ".join(notes) or "steady")

    # ----------------------------------------------------------- 4b review
    def review(s, trace, stats):
        """Mirror make_catalogue.py:placard() archaeology — walk the trace,
        count by `ev`, read `metrics`. Produce a structured diagnosis."""
        rejects = Counter()
        demand_unmet = Counter()
        families = Counter()
        spine_fails = repairs = adapters = 0
        auctions = evictions = backjumps = 0
        ports_open = 0
        hoses = 0
        parts = 0

        for e in trace:
            ev = e.get("ev")
            if ev == "commit":
                parts += 1
                fam = _family_of(e.get("part", ""))
                if fam and fam != "core_hull":
                    families[fam] += 1
            elif ev == "reject":
                rejects[e.get("cause", "?")] += 1
                if e.get("cause") in ("moment_over_cap", "axial_over_cap"):
                    spine_fails += 1
            elif ev == "repair":
                repairs += 1
            elif ev == "adapter":
                adapters += 1
            elif ev == "auction":
                auctions += 1
            elif ev == "evict":
                evictions += 1
            elif ev == "backjump":
                backjumps += 1
            elif ev == "demand_unmet":
                demand_unmet[e.get("cause", "?")] += 1
            elif ev in ("port_open",):
                ports_open += 1
            elif ev == "hose":
                hoses += 1

        # struts come straight from stats (baked count), not the trace, so the
        # ratio is honest about what shipped — mirrors the placard's tally.
        struts = stats.get("struts", 0)
        mass = stats.get("mass", 0)
        body = max(parts, 1)
        placed_total = sum(families.values())
        monoculture = (max(families.values()) / placed_total
                       if placed_total else 0.0)

        return dict(
            parts=parts, mass=mass, struts=struts, hoses=hoses,
            rejects=rejects,
            spine_fails=spine_fails, repairs=repairs, adapters=adapters,
            auctions=auctions, evictions=evictions, backjumps=backjumps,
            demand_unmet=demand_unmet,
            ports_open=ports_open, families=families,
            strut_per_part=round(struts / body, 3),
            monoculture=round(monoculture, 3))

    # ----------------------------------------------- 4c tie / repair reflexes
    def on_tie(s, ranked, ctx):
        """Deterministic, rng-free, REORDER-ONLY tie-break. `ranked` is a list
        of candidate tuples (part, plugs, mates, strain), best-first. `ctx` is
        Assembler._tie_context. Returns a permutation (list of indices into
        ranked) or None (keep order). It may only reorder existing candidates.

        Policy selected by the active brief's tie_policy (defaults to the
        Director's own default if no brief is attached)."""
        policy = (s._brief or {}).get("tie_policy", "diversity")
        n = len(ranked)
        idx = list(range(n))

        if policy == "identity":
            return None

        if policy == "diversity":
            placed = ctx["placed_families"]
            # prefer the family with the LOWEST placed count (fights monoculture)
            key = lambda i: placed.get(ranked[i][0].family, 0)
        elif policy == "silhouette":
            sil = max(ctx["budget"].get("silhouette", 0.0), 0.0)
            # prefer the candidate that best spends remaining silhouette (big
            # reads first); when budget is gone this collapses to the order.
            key = lambda i: -ranked[i][0].silhouette * (sil > 0)
        elif policy == "faction":
            feral = ctx["faction"] == FERAL["name"]
            sig = {"heavy_cannon", "turret"} if feral else {"core_hull"}
            # prefer the family that signals the faction; guild → cleaner
            # struct (penalize the loud families instead)
            def key(i):
                fam = ranked[i][0].family
                if feral:
                    return 0 if fam in sig else 1
                return 1 if fam in {"heavy_cannon", "turret"} else 0
        else:
            return None

        new = sorted(idx, key=lambda i: (key(i), i))   # stable: i breaks ties
        return None if new == idx else new

    def on_repair_choice(s, viable, ctx):
        """Deterministic, rng-free, REORDER-ONLY brace ranking. Default policy
        (handoff Lesson 6): prefer the most triangulated brace (largest relief
        ⇒ most relief from a steeper sin-angle), tie-break lowest added mass
        (proxy: shortest brace L).

        3b IS DEFERRED (AGENT-LOOP-SPEC §3b, and the in-code TODO in
        kitmash.propose_strut): the legacy `best`-accumulator stays
        AUTHORITATIVE. This policy computes the same (-relief, L)-min ordering
        the accumulator already uses, so its top pick can never differ from
        the legacy `best`. We therefore return None unless our chosen head
        differs from the head kitmash would otherwise commit — which, for the
        canonical fleet, it never does. That guarantees byte-identity (no
        spurious repair_choice log) while leaving the policy real and ready to
        drive selection once 3b is promoted."""
        order = s.rank_braces(viable)        # the real policy, ready for 3b
        # 3b deferred: returning the permutation would only relog a no-op
        # (our head == legacy argmin == same committed brace). Return None to
        # keep the canonical fleet byte-identical. Promote `return order` when
        # 3b is wired (kitmash's accumulator replaced by the sorted list).
        del order
        return None

    @staticmethod
    def rank_braces(viable):
        """The brace policy as a pure function (handoff Lesson 6): most
        triangulated first (largest relief), tie-break lowest added mass
        (shortest L). Returns a permutation of indices into `viable`."""
        return sorted(range(len(viable)),
                      key=lambda i: (-viable[i]["relief"], viable[i]["L"]))

    # ----------------------------------------------------------- 4e breeding
    @staticmethod
    def blend_gen_params(a, b, t=0.5):
        """Numeric interpolation of heavy, span (and any shared gen_params).
        Seed derived from both parents so the cross is reproducible."""
        out = dict(
            heavy=round(a["heavy"] * (1 - t) + b["heavy"] * t, 3),
            span=round(a["span"] * (1 - t) + b["span"] * t, 3),
            seed=(a["seed"] * 131 + b["seed"] * 17 + 1) % 100000)
        return out

    def splice_trace(s, brief_a, brief_b, fit_a=0.0, fit_b=0.0):
        """Recombine wants (per-family from whichever parent has the larger
        weight) + inherit the fitter parent's knobs. Records parent/mutation
        prose so the catalogue can narrate the cross."""
        fitter, weaker = ((brief_a, brief_b) if fit_a >= fit_b
                          else (brief_b, brief_a))
        wants = {}
        for fam in set(brief_a["wants"]) | set(brief_b["wants"]):
            wa = brief_a["wants"].get(fam, 0.0)
            wb = brief_b["wants"].get(fam, 0.0)
            wants[fam] = round(max(wa, wb), 3)      # take the louder taste
        blend = s.blend_gen_params(brief_a, brief_b)
        # union the gene pools so spliced wants can actually be supplied
        extra = tuple(dict.fromkeys(
            list(brief_a["extra_gens"]) + list(brief_b["extra_gens"])))
        return make_brief(
            fitter["faction"], blend["seed"], wants,
            heavy=blend["heavy"], span=blend["span"],
            extra_gens=extra, budgets=fitter["budgets"],
            tie_policy=fitter["tie_policy"],
            parent="%s×%s" % (_tag(brief_a), _tag(brief_b)),
            mutation="splice: wants∪, knobs from fitter parent")

    # ----------------------------------------- 4f the evolve loop driver
    def evolve(s, generations=2, population=3, seed=0):
        """The loop. Returns a well-formed lineage record. Zero network calls.

        Per gen: build each brief WITH the director attached (so on_tie fires)
        → review each trace → external fitness + novelty → select survivors →
        breed → next briefs → periodic scarcity shock.
        """
        lineage = dict(generations=[], warnings=[])
        history = []          # (brief, diag, fitness) of the fittest per gen
        prev_best_fitness = None
        prev_diversity = None
        ships = []            # current generation's briefs

        for g in range(generations):
            # author this generation's briefs
            if g == 0:
                briefs = s.author_brief([])
            else:
                briefs = list(next_briefs)
            # scarcity shock on alternating later generations (§4h.3)
            if g > 0 and g % 2 == 0:
                briefs = [s.scarcity_shock(b, g) for b in briefs]
            # pad/trim to population
            briefs = (briefs * ((population // len(briefs)) + 1))[:population]
            briefs = [dict(b) for b in briefs]      # defensive copies

            gen_record = dict(gen=g, ships=[])
            for k, brief in enumerate(briefs):
                rec = s._build_and_review(brief, g, k)
                gen_record["ships"].append(rec)
                ships.append(rec)

            # generation-level diversity (novelty pressure, §4h.2)
            diversity = s.lineage_novelty(gen_record["ships"])
            best = max(gen_record["ships"], key=lambda r: r["fitness"])
            gen_record["best"] = best["name"]
            gen_record["diversity"] = round(diversity, 3)
            best_fit = best["fitness"]

            # PROPORTIONAL VERIFICATION (the rider, §4h.5): default is the
            # cheap review already done. Heavier verification is authorized
            # ONLY when an anomaly is detected, sized to the uncertainty.
            plan = s.verification_plan(gen_record, prev_best_fitness,
                                       prev_diversity)
            gen_record["verification"] = plan

            # lineage-pathology: fitness rising while diversity falling (§4h.4)
            warn = s.lineage_pathology(best_fit, diversity,
                                       prev_best_fitness, prev_diversity)
            if warn:
                gen_record.setdefault("trace", []).append(warn)
                lineage["warnings"].append(warn)

            lineage["generations"].append(gen_record)
            history.append((best["brief"], best["diagnosis"], best_fit))

            # SELECT survivors (top half by fitness, ≥2) and BREED next gen
            survivors = sorted(gen_record["ships"],
                               key=lambda r: -r["fitness"])[:max(2,
                                                                 population // 2)]
            next_briefs = s._breed(survivors)
            prev_best_fitness, prev_diversity = best_fit, diversity

        lineage["best_overall"] = max(
            (r for gr in lineage["generations"] for r in gr["ships"]),
            key=lambda r: r["fitness"])["name"]
        return lineage

    def _build_and_review(s, brief, g, k):
        """Build one ship from a brief (director attached), review its trace,
        compute external fitness. Returns a per-ship lineage record."""
        s._brief = brief                 # arms on_tie's policy for this build
        a = build(brief["faction"], brief["seed"], brief["wants"],
                  heavy=brief["heavy"], span=brief["span"],
                  parent=brief.get("parent"), mutation=brief.get("mutation"),
                  extra_gens=brief["extra_gens"], director=s)
        s._brief = None
        stats = dict(
            parts=len(a.placed),
            mass=int(sum(p.mass for p in a.placed)),
            struts=len(a.struts), hoses=len(a.hoses))
        diag = s.review(a.trace, stats)
        fit = s.external_fitness(diag)
        name = "G%d-%02d-%s" % (g, k, brief["faction"]["name"].split()[0])
        # cook check: a ship that "ran" must be legal (no hard overlaps).
        legal = no_hard_overlaps(a)
        diag["legal"] = legal
        return dict(name=name, brief=brief, diagnosis=diag, fitness=fit,
                    stats=stats, parents=brief.get("parent"), legal=legal,
                    assembler=a)

    def _breed(s, survivors):
        """Pair survivors and splice; carry the fittest brief through too."""
        out = []
        for i in range(len(survivors)):
            a = survivors[i]
            b = survivors[(i + 1) % len(survivors)]
            child = s.splice_trace(a["brief"], b["brief"],
                                   a["fitness"], b["fitness"])
            out.append(child)
        # also let each survivor's diagnosis author one adjusted brief
        out.append(s._adjust(survivors[0]["brief"], survivors[0]["diagnosis"]))
        return out

    # ------------------------------------------------- 4g external fitness
    def external_fitness(s, diag):
        """The Goodhart firewall (§4g): computed from the DIAGNOSIS, never
        from score(). Rewards SHIP VIRTUE, not sampler taste:
            + fueled            (no demand_unmet)
            + family diversity  (more distinct families, less monoculture)
            + silhouette spent  (richer reads — proxied by part count in band)
            + LOW strut/part    (honest frame, not over-braced)
            + part-count in band
        The sampler optimizes score(); this ignores score() entirely."""
        fueled = 1.0 if sum(diag["demand_unmet"].values()) == 0 else 0.0
        n_fam = len(diag["families"])
        diversity = n_fam * (1.0 - diag["monoculture"])
        honest = max(0.0, 1.0 - diag["strut_per_part"] / STRUT_PER_PART_OK)
        lo, hi = PART_BAND
        in_band = 1.0 if lo <= diag["parts"] <= hi else \
            max(0.0, 1.0 - min(abs(diag["parts"] - lo),
                               abs(diag["parts"] - hi)) / 5.0)
        legal = 1.0 if diag.get("legal", True) else 0.0
        return round(2.0 * fueled + 1.2 * diversity + 1.0 * honest +
                     1.0 * in_band + 1.5 * legal, 4)

    # --------------------------------------------------- 4h Goodhart guards
    def lineage_novelty(s, ship_records):
        """§4h.2 novelty pressure: spread across the generation's family
        signatures. 1.0 = every ship distinct; →0 = taste collapse."""
        if not ship_records:
            return 0.0
        sigs = [frozenset(r["diagnosis"]["families"]) for r in ship_records]
        distinct = len(set(sigs))
        return distinct / len(sigs)

    def scarcity_shock(s, brief, g):
        """§4h.3: deterministically perturb budgets/wants so a single-run
        exploit cannot dominate the lineage. rng-free (uses gen index)."""
        b = make_brief(brief["faction"], brief["seed"], brief["wants"],
                       heavy=brief["heavy"], span=brief["span"],
                       extra_gens=brief["extra_gens"],
                       budgets=dict(brief["budgets"]),
                       tie_policy=brief["tie_policy"],
                       parent=brief.get("parent"), mutation=brief.get("mutation"))
        # cut mass and parts budget on shock generations
        b["budgets"]["mass"] = int(b["budgets"]["mass"] * 0.9)
        b["budgets"]["parts"] = max(8, b["budgets"]["parts"] - 1)
        # damp the loudest want so the exploit can't simply repeat
        if b["wants"]:
            loud = max(b["wants"], key=b["wants"].get)
            b["wants"][loud] = round(b["wants"][loud] * 0.75, 3)
        b["mutation"] = (b.get("mutation") or "") + " | scarcity_shock g%d" % g
        return b

    def lineage_pathology(s, fit, diversity, prev_fit, prev_div):
        """§4h.4 the Goodhart signature detector: fitness CLIMBING while
        diversity is bad. Returns a goodhart_warning event dict or None.

        Two ways diversity is "bad" (Cassandra charge 3, 2026-06-13): the
        SLOPE (actively collapsing this generation) OR the LEVEL (already
        collapsed and held flat at/below the floor — the actual Goodhart
        endgame: find the gamed config once, then farm it at stable-low
        diversity). The original detector watched only the slope and was blind
        to the cliff it was already standing on. Both clauses require RISING
        fitness — a healthy *stable* converged fleet (flat fitness, low
        diversity) is monotonous, not pathological, and is NOT flagged."""
        if prev_fit is None or prev_div is None:
            return None
        rising = fit > prev_fit + 1e-9
        if not rising:
            return None
        falling = diversity < prev_div - 1e-9
        floored = diversity < s.collapse_floor
        if falling or floored:
            return dict(ev="goodhart_warning",
                        cause="fitness_up_diversity_down" if falling
                              else "fitness_up_diversity_floored",
                        metrics=dict(fitness=round(fit, 3),
                                     prev_fitness=round(prev_fit, 3),
                                     diversity=round(diversity, 3),
                                     prev_diversity=round(prev_div, 3),
                                     floor=s.collapse_floor),
                        result="flagged")
        return None

    def verification_plan(s, gen_record, prev_fit, prev_div):
        """§4h.5 PROPORTIONAL VERIFICATION (THE RIDER), as real code.

        Diary 2026-06-12 §"Long": "Goodhart lives in the review fan-out as
        surely as in the scorer. An agent that spawns eighty skeptics for
        every green task has confused thoroughness with diligence."

        Default: review is the cheap deterministic trace-walk already done —
        budget 0 extra skeptics. We escalate ONLY on a detected anomaly, and
        the budget is proportional to the *magnitude of detected uncertainty*,
        NOT to available compute. A clean generation gets one cheap pass; a
        suspicious one gets a few targeted checks — never a tribunal."""
        anomalies = []
        # signal 1: any ship illegal or unfueled is a real anomaly
        sick = [r for r in gen_record["ships"]
                if not r["diagnosis"].get("legal", True)
                or sum(r["diagnosis"]["demand_unmet"].values()) > 0]
        if sick:
            anomalies.append(("ship_health", len(sick)))
        # signal 2: the Goodhart signature contributes uncertainty
        if s.lineage_pathology(
                max(r["fitness"] for r in gen_record["ships"]),
                gen_record["diversity"], prev_fit, prev_div):
            anomalies.append(("goodhart_signature", 1))
        # signal 3: taste collapse — novelty ACTIVELY eroding into the floor.
        # NOT mere low diversity (Cassandra charge 2, 2026-06-13): a fully
        # legal+fueled fleet that has simply converged and holds flat is
        # monotonous, not sick, and must draw ZERO extra budget — spawning
        # skeptics for a stable green generation is the diary's automated sin.
        # We escalate only when diversity is below the floor AND still dropping.
        if prev_div is not None and gen_record["diversity"] < s.collapse_floor \
                and gen_record["diversity"] < prev_div - 1e-9:
            anomalies.append(("taste_collapse", 1))

        # budget is proportional to detected uncertainty, capped — NEVER scaled
        # to the number of ships or available compute.
        units = sum(n for _, n in anomalies)
        budget = min(units, 3) if anomalies else 0
        s.verification_budget = budget
        return dict(anomalies=anomalies, verification_budget=budget,
                    rationale=("proportional to detected uncertainty, not "
                               "compute"))


# ------------------------------------------------ optional LLM-backed subclass
class LLMDirector(Director):
    """OPTIONAL subclass hook (§4). An LLM may author the brief or narrate the
    review — but the CORE loop must run with ZERO network calls, and per-port
    LLM calls are FORBIDDEN. By default this falls straight back to the
    heuristic parent; wiring a real client is left to a future instance."""

    def __init__(s, client=None, **kw):
        super().__init__(**kw)
        s.client = client          # None => identical to heuristic Director

    def author_brief(s, history):
        if s.client is None:
            return super().author_brief(history)
        # A real implementation would ask the client for a brief here. It is
        # called ONCE per generation, never per port. Falls back if no client.
        return super().author_brief(history)

    def review(s, trace, stats):
        # The structured diagnosis is always the cheap deterministic walk; an
        # LLM may *narrate* it, but the numbers come from the trace.
        return super().review(trace, stats)


# ----------------------------------------------------------------- helpers
_FAMILIES = ("core_hull", "fuel_tank", "engine", "wing", "heavy_cannon",
             "antenna", "sensor_pod", "radiator", "reactor", "turret",
             "terminator_cap")


def _family_of(label):
    """Map a commit event's `part` (which is the part LABEL, not family) back
    to a family. Labels like 'wing R', 'fuel tank', 'sensor pod' differ from
    family ids; resolve by best prefix/substring match."""
    if not label:
        return ""
    s = label.replace(" ", "_").lower()
    if s in _FAMILIES:
        return s
    # label-to-family fixups (labels carry spaces / handedness)
    table = {"fuel_tank": "fuel_tank", "wing": "wing", "cannon": "heavy_cannon",
             "sensor_pod": "sensor_pod", "blanking_cap": "terminator_cap",
             "engine": "engine", "antenna": "antenna", "radiator": "radiator",
             "reactor": "reactor", "turret": "turret"}
    for key, fam in table.items():
        if s.startswith(key) or key in s:
            return fam
    return s


def _tag(brief):
    return "%s/%d" % (brief["faction"]["name"].split()[0], brief["seed"])


def no_hard_overlaps(a):
    """Cook check: no two committed parts hard-overlap (mirrors the kitmash
    legality predicate, read-only). Hosts/parents are allowed to touch."""
    import numpy as np
    led = a.ledger
    for i in range(len(led)):
        lo_i, hi_i, p_i = led[i]
        for j in range(i + 1, len(led)):
            lo_j, hi_j, p_j = led[j]
            if p_i.parent is p_j or p_j.parent is p_i:
                continue
            if np.all(lo_i < hi_j) and np.all(lo_j < hi_i):
                # allow a small touch tolerance consistent with the 0.02 pad
                overlap = np.minimum(hi_i, hi_j) - np.maximum(lo_i, lo_j)
                if np.all(overlap > 0.045):
                    return False
    return True
