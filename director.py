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
               mutation=None, bureau=None):
    """A Brief is a plain dict (AGENT-LOOP-SPEC §4a). It extends build()'s
    inputs with director-level knobs that default to today's values.

    `bureau` is the name of the active aesthetic objective (§2c) the brief was
    authored under. It selects which row of BUREAU_OBJECTIVES external_fitness
    scores against; None ⇒ the canonical objective (behaviour unchanged)."""
    return dict(
        faction=faction, seed=int(seed), wants=dict(wants),
        heavy=float(heavy), span=float(span),
        extra_gens=tuple(extra_gens),
        budgets=dict(budgets) if budgets else dict(mass=11000,
                                                   silhouette=3.2, parts=14),
        tie_policy=tie_policy, parent=parent, mutation=mutation,
        bureau=bureau)


# fitness/diagnosis tuning constants — descriptive heuristics, all documented
PART_BAND = (7, 12)            # "honest" part count band
STRUT_PER_PART_OK = 0.6        # above this the frame is over-braced
TIE_EPS_DEFAULT = 0.05

# service families: the plumbing/power complexity a Service-Network bureau prizes
SERVICE_FAMILIES = ("reactor", "turret", "radiator")


# ============================================================ BUREAUS (§2c)
# A bureau is a named brief-authoring preset: a dict of OBJECTIVE WEIGHTS over
# the fitness *terms* (computed below in external_fitness), plus a `seed`
# regime (faction / extra genes / wants slant / scarcity) that gives the
# lineage a genuinely different starting taste. A bureau is NOT a new agent: it
# makes NO LLM call, adds NO legality, is rng-free. It only reweights the SAME
# external_fitness terms, all of which read ONLY the post-hoc diagnosis — never
# score(). The terms are deliberately authored to pull in different directions:
#
#   fueled       1 if no demand_unmet else 0           (always rewarded > 0)
#   legal        1 if no hard overlaps else 0          (always rewarded > 0)
#   diversity    n_fam * (1 - monoculture)             family spread
#   honest       1 - strut_per_part/OK  (clamped ≥0)   LOW bracing
#   in_band      part count inside PART_BAND
#   bracing      strut_per_part/OK  (the INVERSE of honest) — visible mediation
#   repair       (repairs + adapters) scaled           mediation scars
#   service      count of SERVICE_FAMILIES present      plumbing/power depth
#   plumbing     hoses scaled                           routing intricacy
#   antirepeat   1 - (sibling story-collisions / n)     Austerity's anti-attractor
#
# `fueled` and `legal` keep a positive weight in EVERY bureau (a bureau may
# slant taste, but a dead ship is never preferred). The default row reproduces
# today's hard-coded coefficients exactly, so external_fitness(diag) with no
# bureau is byte-for-behaviour identical to before.
BUREAU_OBJECTIVES = {
    # canonical objective — today's coefficients, unchanged default
    None: dict(fueled=2.0, diversity=1.2, honest=1.0, in_band=1.0, legal=1.5),

    # Guild-Structural — clean, redundant, debt-free structure. Heavy weight on
    # honesty (low strut/part) and band compliance; rewards diversity modestly.
    "Guild-Structural": dict(
        fueled=2.0, legal=1.5, honest=2.4, in_band=1.6, diversity=0.8),

    # Feral-Repair — INVERTS the strut penalty. The repair scars ARE the
    # aesthetic: visible bracing and mediation are rewarded, debt tolerated.
    # No `honest` term at all (it would punish the look this bureau wants).
    "Feral-Repair": dict(
        fueled=1.5, legal=1.5, bracing=1.8, repair=1.4, diversity=0.6),

    # Service-Network — reactor/turret/radiator service complexity plus deep
    # fuel/power routing (hoses). A ship is good when its plumbing is intricate
    # AND it stays legal+fueled.
    "Service-Network": dict(
        fueled=2.0, legal=1.5, service=2.2, plumbing=1.2, diversity=0.6),

    # Austerity — optimises AGAINST repetition itself. Penalises a ship whose
    # event-story (family signature + reject narrative) merely retells what its
    # siblings already told. The explicit anti-attractor.
    "Austerity": dict(
        fueled=2.0, legal=1.5, antirepeat=3.0, diversity=1.0, in_band=0.6),
}
DEFAULT_BUREAUS = ("Guild-Structural", "Feral-Repair",
                   "Service-Network", "Austerity")


# ================================================================== Director
class Director:
    """Heuristic, rng-free, network-free creative director."""

    def __init__(s, tie_eps=TIE_EPS_DEFAULT, verification_budget=0,
                 collapse_floor=0.5, diversity_weight=0.35,
                 repair_policy_active=False):
        s.tie_eps = tie_eps
        # 3b PROMOTION FLAG (default OFF — anchor safe). When False,
        # on_repair_choice returns None EXACTLY as the deferred no-op did, so the
        # canonical (no-director) and any active-director build are byte-identical.
        # When True, the real rank_braces policy drives brace selection through
        # the kitmash repair-commit path. Even when True it stays byte-identical
        # on the canonical fleet: rank_braces uses the SAME (-relief, L) key the
        # legacy accumulator does, so its head == legacy argmin and we suppress
        # the reorder/log whenever committing our head would change nothing.
        s.repair_policy_active = repair_policy_active
        # PROPORTIONAL VERIFICATION knob: the *baseline* heavy-review budget is
        # ZERO. It is raised ONLY by verification_plan() in response to a
        # detected anomaly — never as a function of available compute.
        s.verification_budget = verification_budget
        # absolute diversity floor: the LEVEL below which sustained-low novelty
        # plus rising fitness is the Goodhart endgame (not just a falling slope).
        s.collapse_floor = collapse_floor
        # DIVERSITY-AWARE SELECTION knob (§2a): how strongly the facility-
        # location survivor pass weights NEW family-signature variety against a
        # ship's own fitness. 0.35 ⇒ fitness still leads; variety breaks
        # near-ties and rescues distinct-but-slightly-weaker ships.
        s.diversity_weight = diversity_weight
        s._brief = None        # the active brief (sets tie_policy for on_tie)
        s._select_log = []     # ledger-shaped survivor-selection events

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

    # ----------------------------------------------------- 2c bureau seeding
    def _bureau_seed(s, bureau):
        """Author the gen-0 seed brief for one bureau. The seed regime —
        faction, extra service genes, wants slant, tie policy — is chosen so
        the lineage STARTS in a different basin, not merely scores the same
        ships differently. (The objective fork lives in BUREAU_OBJECTIVES; the
        *basin* fork lives here. Together they make bureaus actually diverge.)
        rng-free; no LLM call; adds no legality."""
        if bureau == "Guild-Structural":
            # clean redundant guild frame: modest cannon, no service genes.
            wants = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                     "heavy_cannon": 1.0, "antenna": 0.9, "sensor_pod": 0.8}
            return make_brief(GUILD, 7, wants, heavy=0.9, span=3.0,
                              tie_policy="diversity", bureau=bureau,
                              mutation="bureau:Guild-Structural seed")
        if bureau == "Feral-Repair":
            # over-armed feral lever that braces hard — repair scars by design.
            wants = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.2,
                     "heavy_cannon": 2.8, "sensor_pod": 0.6, "antenna": 0.3}
            return make_brief(FERAL, 23, wants, heavy=1.7, span=3.6,
                              tie_policy="faction", bureau=bureau,
                              mutation="bureau:Feral-Repair seed")
        if bureau == "Service-Network":
            # plumbing-rich: reactor/turret service genes + a service want slant.
            # (radiator is deliberately NOT seeded here — the routed plumbing for
            # reactor+turret fuels cleanly, whereas piling on a radiator demand
            # leaves it `no_route` and the eligibility filter would correctly
            # eject the ship. The bureau prizes intricate-AND-legal plumbing.)
            wants = {"engine": 3.0, "fuel_tank": 2.5, "wing": 1.6,
                     "heavy_cannon": 0.9, "turret": 2.6, "reactor": 2.3,
                     "sensor_pod": 0.4, "antenna": 0.3}
            return make_brief(FERAL, 101, wants, heavy=1.0, span=3.0,
                              extra_gens=(gen_reactor, gen_turret),
                              tie_policy="faction", bureau=bureau,
                              mutation="bureau:Service-Network seed")
        if bureau == "Austerity":
            # broad balanced taste so the anti-repeat term has room to spread.
            wants = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                     "heavy_cannon": 1.4, "sensor_pod": 1.0, "antenna": 1.0,
                     "radiator": 1.2}
            return make_brief(GUILD, 53, wants, heavy=1.0, span=3.2,
                              extra_gens=(gen_radiator,),
                              tie_policy="diversity", bureau=bureau,
                              mutation="bureau:Austerity seed")
        # unknown bureau ⇒ fall back to the canonical guild seed
        return s._seed_briefs()[0]

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
            mutation="; ".join(notes) or "steady",
            bureau=brief.get("bureau"))

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

        3b PROMOTION (AGENT-LOOP-SPEC §3b): the real policy now drives brace
        selection — but ONLY behind `s.repair_policy_active`, and ONLY when
        doing so changes the committed brace's GEOMETRY.

          * `repair_policy_active is False` (default / canonical) ⇒ return None
            EXACTLY as the deferred no-op did. The legacy `best`-accumulator in
            kitmash.propose_strut stays authoritative; no log, byte-identical.

          * `repair_policy_active is True` ⇒ rank with rank_braces (the spine:
            -relief, then +L) and apply a FACTION secondary tie-break ONLY among
            braces that tie on the FULL (relief, L) spine key — i.e. braces the
            legacy accumulator already considers interchangeable. Guild taste
            keeps the spine order (the clean, lexicographically-first anchor ==
            the legacy accumulator). Feral taste — the "Tape Holds" aesthetic
            where visible bracing IS the look — prefers the louder anchor among
            that strict tie. The secondary key NEVER reaches across to a
            different-(relief, L) brace, so the policy can never silently swap a
            short clean brace for a longer one; it only re-resolves a genuine
            tie. This is where guild and feral brace taste DIVERGE, and the
            divergence is now structurally reachable.

        BYTE-IDENTITY GUARD: we compare the brace our order would COMMIT (its
        geometry: anchor / endpoint / relief / L) against the brace the legacy
        accumulator would commit. If they are the SAME PHYSICAL BRACE we return
        None — kitmash's `if pick is not None` short-circuits, no repair_choice
        event is logged, and the fleet is byte-identical. The canonical fleet's
        only (-relief, L)-ties are between GEOMETRICALLY IDENTICAL candidates
        (verified: same core_hull anchor, same endpoint), so even feral taste
        commits the same physical strut there — the flag-ON canonical build is
        byte-identical. We emit a permutation + ledger event ONLY when the
        committed brace genuinely differs (never on canonical input)."""
        if not s.repair_policy_active:
            # anchor-safe deferred behaviour: identical to the historical no-op.
            return None

        order = s._ranked_by_taste(viable, (ctx or {}).get("faction"))
        legacy = s._legacy_argmin(viable)        # what kitmash would commit
        if s._same_brace(viable[order[0]], viable[legacy]):
            # our head commits the SAME physical brace as legacy ⇒ no-op.
            # Suppress so kitmash short-circuits: no event, byte-identical.
            return None

        # GENUINE divergence: the live faction taste commits a different brace
        # than the legacy accumulator. Hand kitmash the permutation, trace it.
        s._select_log.append(dict(
            ev="repair_choice", cause="rank_braces",
            metrics=dict(among=len(viable),
                         head_anchor=viable[order[0]].get("anchor_part"),
                         head_relief=round(viable[order[0]]["relief"], 3),
                         head_L=round(viable[order[0]]["L"], 3),
                         legacy_anchor=viable[legacy].get("anchor_part"),
                         legacy_L=round(viable[legacy]["L"], 3),
                         faction=(ctx or {}).get("faction")),
            result="reordered"))
        return order

    def _ranked_by_taste(s, viable, faction):
        """rank_braces (the -relief,+L spine) plus a FACTION secondary tie-break
        applied ONLY among braces that tie on the FULL (relief, L) spine key —
        the set the legacy accumulator treats as interchangeable. Guild keeps the
        spine order (== legacy). Feral re-resolves a strict tie toward the louder
        anchor (the visible-bracing aesthetic). The secondary key cannot reach a
        different-(relief, L) brace, so this never swaps a clean short brace for a
        longer one; it only breaks a genuine tie differently by faction."""
        base = s.rank_braces(viable)             # spine order (reuse the policy)
        if faction != FERAL["name"]:
            return base                          # guild == spine == legacy
        # FERAL: within each strict (relief, L) tie-group of `base`, prefer the
        # louder anchor (lexicographically larger anchor_part), stable on the
        # spine position otherwise. Only same-(relief, L) members can reorder.
        def feral_key(rank_pos):
            i = base[rank_pos]
            return (-viable[i]["relief"], viable[i]["L"],
                    s._anchor_loudness(viable[i]), rank_pos)
        return [base[p] for p in sorted(range(len(base)), key=feral_key)]

    @staticmethod
    def _anchor_loudness(brace):
        """Feral taste key: a louder (more conspicuous) anchor sorts FIRST. We
        invert the anchor label so the lexicographically LARGER anchor name wins
        a strict tie — a deterministic, geometry-free faction signal."""
        lbl = brace.get("anchor_part") or ""
        # negate via reverse-ordinal so larger label => smaller key => first.
        return tuple(-ord(c) for c in lbl)

    @staticmethod
    def _same_brace(p, q):
        """True iff two viable-brace dicts commit the SAME physical strut: same
        anchor part, same endpoints, same relief/L (within float tol). The
        byte-identity reference — two candidates can tie on (-relief, L) yet be
        the same physical brace (canonical fleet), in which case a faction
        reorder commits identical geometry and must NOT be logged."""
        if p is q:
            return True
        if p.get("anchor_part") != q.get("anchor_part"):
            return False
        if abs(p["relief"] - q["relief"]) > 1e-9 or abs(p["L"] - q["L"]) > 1e-9:
            return False
        pa, pb = p.get("a"), p.get("b")
        qa, qb = q.get("a"), q.get("b")
        import numpy as np
        return bool(np.allclose(pa, qa, atol=1e-9)
                    and np.allclose(pb, qb, atol=1e-9))

    @staticmethod
    def _legacy_argmin(viable):
        """The index kitmash.propose_strut's `best`-accumulator would commit:
        max relief, tie-break shortest L, FIRST-encountered wins a true tie
        (mirrors the accumulator's strict `>`/`<` updates exactly). Pure,
        read-only — the reference point that makes byte-identity provable."""
        best = 0
        for i in range(1, len(viable)):
            if viable[i]["relief"] > viable[best]["relief"] + 1e-9 or \
               (abs(viable[i]["relief"] - viable[best]["relief"]) < 1e-9
                    and viable[i]["L"] < viable[best]["L"]):
                best = i
        return best

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
        cross = (brief_a.get("bureau") != brief_b.get("bureau")
                 and brief_a.get("bureau") is not None
                 and brief_b.get("bureau") is not None)
        note = ("splice: wants∪, knobs from fitter parent"
                + (" | cross-bureau %s×%s, inherits %s"
                   % (brief_a.get("bureau"), brief_b.get("bureau"),
                      fitter.get("bureau")) if cross else ""))
        return make_brief(
            fitter["faction"], blend["seed"], wants,
            heavy=blend["heavy"], span=blend["span"],
            extra_gens=extra, budgets=fitter["budgets"],
            tie_policy=fitter["tie_policy"],
            parent="%s×%s" % (_tag(brief_a), _tag(brief_b)),
            mutation=note, bureau=fitter.get("bureau"))

    # ----------------------------------------- 4f the evolve loop driver
    def evolve(s, generations=2, population=3, seed=0, bureaus=None):
        """The loop. Returns a well-formed lineage record. Zero network calls.

        Per gen: build each brief WITH the director attached (so on_tie fires)
        → review each trace → external fitness (under each ship's bureau) +
        novelty → diversity-aware select survivors → breed (within bureau, plus
        an occasional cross-bureau splice) → next briefs → periodic scarcity
        shock.

        BUREAUS (§2c): `bureaus` defaults to the four standard bureaus. Each
        gen-0 ship is seeded under a bureau (round-robin across `population`),
        and the bureau identity rides on every brief/ship thereafter. Survivors
        breed within their own bureau by default; one deliberate cross-bureau
        splice per generation supplies hybridization. The default call
        `evolve(generations=2, population=3)` still returns exactly `population`
        ships/gen with the full per-ship/per-gen keys the smoke test asserts."""
        bureaus = list(bureaus) if bureaus is not None else list(DEFAULT_BUREAUS)
        s._select_log = []        # fresh whole-run selection ledger
        lineage = dict(generations=[], warnings=[], bureaus=bureaus)
        history = []          # (brief, diag, fitness) of the fittest per gen
        prev_best_fitness = None
        prev_diversity = None

        for g in range(generations):
            # author this generation's briefs (gen-0: one seed per bureau)
            if g == 0:
                seeds = [s._bureau_seed(b) for b in bureaus]
            else:
                seeds = list(next_briefs)
            # scarcity shock on alternating later generations (§4h.3)
            if g > 0 and g % 2 == 0:
                seeds = [s.scarcity_shock(b, g) for b in seeds]
            # round-robin pad/trim to exactly `population` ships
            briefs = [dict(seeds[i % len(seeds)]) for i in range(population)]

            gen_record = dict(gen=g, ships=[])
            sibling_sigs = []          # for Austerity's anti-repeat term
            for k, brief in enumerate(briefs):
                rec = s._build_and_review(brief, g, k, sibling_sigs)
                gen_record["ships"].append(rec)
                sibling_sigs.append(_story_sig(rec["diagnosis"]))

            # generation-level diversity (novelty pressure, §4h.2)
            diversity = s.lineage_novelty(gen_record["ships"])
            best = _fittest_eligible(gen_record["ships"])
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

            # SELECT survivors — diversity-aware facility-location (§2a),
            # eligibility (legal AND fueled) a HARD filter before novelty.
            survivors = s.select_survivors(
                gen_record["ships"], max(2, population // 2), gen_record)
            next_briefs = s._breed(survivors, bureaus)
            prev_best_fitness, prev_diversity = best_fit, diversity

        lineage["best_overall"] = _fittest_eligible(
            [r for gr in lineage["generations"] for r in gr["ships"]])["name"]
        return lineage

    def _build_and_review(s, brief, g, k, sibling_sigs=None):
        """Build one ship from a brief (director attached), review its trace,
        compute external fitness UNDER THE BRIEF'S BUREAU. Returns a per-ship
        lineage record. `sibling_sigs` (story-signatures of already-judged
        ships this gen) feeds Austerity's anti-repeat term — derived purely
        from diagnoses, never from score()."""
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
        # cook check: a ship that "ran" must be legal (no hard overlaps).
        legal = no_hard_overlaps(a)
        diag["legal"] = legal
        bureau = brief.get("bureau")
        ctx = ({"sibling_sigs": sibling_sigs} if sibling_sigs is not None
               and bureau == "Austerity" else None)
        fit = s.external_fitness(diag, bureau=bureau, lineage_ctx=ctx)
        name = "G%d-%02d-%s" % (g, k, brief["faction"]["name"].split()[0])
        return dict(name=name, brief=brief, diagnosis=diag, fitness=fit,
                    stats=stats, parents=brief.get("parent"), legal=legal,
                    bureau=bureau, assembler=a)

    def _breed(s, survivors, bureaus=None):
        """Breed the next generation. By default survivors breed WITHIN their
        own bureau (the objective fork must persist for the lineages to keep
        diverging). One deliberate CROSS-bureau splice per generation supplies
        hybridization (reuses splice_trace). Each bureau's fittest survivor also
        authors one diagnosis-adjusted brief."""
        # group survivors by bureau, fittest-first within each group
        groups = {}
        for r in survivors:
            groups.setdefault(r.get("bureau"), []).append(r)
        for members in groups.values():
            members.sort(key=lambda r: -r["fitness"])

        # breed each bureau into its own child-list (within-bureau splices +
        # one diagnosis-adjusted brief from the bureau's fittest survivor)
        per_bureau = {}
        for bureau, members in groups.items():
            kids = []
            if len(members) == 1:
                kids.append(s._adjust(members[0]["brief"],
                                      members[0]["diagnosis"]))
            else:
                for i in range(len(members)):
                    a = members[i]
                    b = members[(i + 1) % len(members)]
                    kids.append(s.splice_trace(a["brief"], b["brief"],
                                               a["fitness"], b["fitness"]))
                kids.append(s._adjust(members[0]["brief"],
                                      members[0]["diagnosis"]))
            per_bureau[bureau] = kids

        # INTERLEAVE the per-bureau children round-robin so every surviving
        # bureau gets fair representation when evolve() pads to `population`.
        # (Clustering them would let the front bureau crowd the others out and
        # re-collapse the lineage — the exact attractor we are escaping.)
        out = []
        idx = 0
        order = list(per_bureau)
        while any(idx < len(per_bureau[b]) for b in order):
            for b in order:
                if idx < len(per_bureau[b]):
                    out.append(per_bureau[b][idx])
            idx += 1

        # ONE deliberate cross-bureau hybridization per generation (§2c): splice
        # the two fittest survivors of DIFFERENT bureaus. The child inherits the
        # fitter parent's bureau (so it rejoins a real objective lineage).
        ranked = sorted(survivors, key=lambda r: -r["fitness"])
        if len(ranked) >= 2:
            top = ranked[0]
            other = next((r for r in ranked[1:]
                          if r.get("bureau") != top.get("bureau")), None)
            if other is not None:
                out.append(s.splice_trace(top["brief"], other["brief"],
                                          top["fitness"], other["fitness"]))
        return out or [s._adjust(survivors[0]["brief"],
                                 survivors[0]["diagnosis"])]

    # ------------------------------------------------- 4g external fitness
    @staticmethod
    def fitness_terms(diag, lineage_ctx=None):
        """Compute every named fitness TERM from the DIAGNOSIS alone (plus, for
        the anti-repeat term, sibling family/reject signatures passed in
        `lineage_ctx`). EVERY term is a pure function of `diag` — none reads
        score(). This is the single place the firewall is enforced: there is no
        argument here through which a candidate's score() could enter.

        `lineage_ctx`, when present, is a dict {"sibling_sigs": [...]} of the
        (family-signature, reject-signature) tuples of the ships ALREADY judged
        this generation — also derived purely from their diagnoses, never their
        score()."""
        fueled = 1.0 if sum(diag["demand_unmet"].values()) == 0 else 0.0
        n_fam = len(diag["families"])
        diversity = n_fam * (1.0 - diag["monoculture"])
        spp = diag["strut_per_part"]
        honest = max(0.0, 1.0 - spp / STRUT_PER_PART_OK)
        bracing = min(2.0, spp / STRUT_PER_PART_OK)   # INVERSE of honest
        repair = min(2.0, (diag.get("repairs", 0)
                           + diag.get("adapters", 0)) / 3.0)
        service = sum(1 for f in SERVICE_FAMILIES if diag["families"].get(f, 0))
        plumbing = min(2.0, diag.get("hoses", 0) / 3.0)
        lo, hi = PART_BAND
        in_band = 1.0 if lo <= diag["parts"] <= hi else \
            max(0.0, 1.0 - min(abs(diag["parts"] - lo),
                               abs(diag["parts"] - hi)) / 5.0)
        legal = 1.0 if diag.get("legal", True) else 0.0
        # antirepeat: 1.0 if this ship's (families, rejects) story is NOVEL among
        # its already-judged siblings; →0 as it retells what siblings told.
        antirepeat = 1.0
        if lineage_ctx:
            sibs = lineage_ctx.get("sibling_sigs", [])
            if sibs:
                me = _story_sig(diag)
                collisions = sum(1 for sg in sibs if sg == me)
                antirepeat = max(0.0, 1.0 - collisions / len(sibs))
        return dict(fueled=fueled, diversity=diversity, honest=honest,
                    bracing=bracing, repair=repair, service=service,
                    plumbing=plumbing, in_band=in_band, legal=legal,
                    antirepeat=antirepeat)

    def external_fitness(s, diag, bureau=None, lineage_ctx=None):
        """The Goodhart firewall (§4g): computed from the DIAGNOSIS, never from
        score(). Rewards SHIP VIRTUE under the active BUREAU's objective.

        `bureau=None` reproduces today's coefficients exactly
        (2·fueled + 1.2·diversity + 1.0·honest + 1.0·in_band + 1.5·legal), so
        behaviour is unchanged when no bureau is set. Other bureaus reweight the
        SAME terms (see BUREAU_OBJECTIVES) to pull in different aesthetic
        directions. The sampler optimizes score(); this ignores score()
        entirely — every term flows from `diag`, the post-hoc diagnosis."""
        weights = BUREAU_OBJECTIVES.get(bureau, BUREAU_OBJECTIVES[None])
        terms = s.fitness_terms(diag, lineage_ctx)
        total = sum(w * terms[name] for name, w in weights.items())
        return round(total, 4)

    # ----------------------------------------- 2a diversity-aware selection
    def select_survivors(s, ships, k, gen_record=None):
        """Greedy diversity-aware (facility-location) survivor selection.

        Take the fittest ELIGIBLE ship, then repeatedly take the ship that best
        combines its own fitness with the NEW family-signature variety it adds.

        ELIGIBILITY IS A HARD FILTER (the Goodhart guard, §2a): a ship must be
        legal AND fueled to be selectable AT ALL. Novelty is scored only AFTER
        this filter, so novelty can never buy a survival slot for a dead ship —
        a signature can read 'novel' merely because a required family is MISSING
        (a broken ship), and that path is closed by construction here."""
        eligible = [r for r in ships if _is_eligible(r)]
        # fall back to the raw pool ONLY if nothing is eligible (degenerate
        # generation) so evolve() never starves; flagged via the log.
        pool = eligible or ships
        if not pool:
            return []
        chosen = [max(pool, key=lambda r: r["fitness"])]
        s._log_select(chosen[0], novel=True, gen_record=gen_record,
                      cause="fittest_eligible")
        rest = [r for r in pool if r is not chosen[0]]
        fmax = max(r["fitness"] for r in pool) or 1.0
        while rest and len(chosen) < k:
            sigs = {frozenset(r["diagnosis"]["families"]) for r in chosen}

            def marginal(r):
                fit_term = r["fitness"] / fmax
                novel = frozenset(r["diagnosis"]["families"]) not in sigs
                novelty = 1.0 if novel else 0.0
                return (s.diversity_weight * novelty
                        + (1 - s.diversity_weight) * fit_term)
            nxt = max(rest, key=marginal)
            novel = frozenset(nxt["diagnosis"]["families"]) not in sigs
            chosen.append(nxt)
            rest.remove(nxt)
            s._log_select(nxt, novel=novel, gen_record=gen_record,
                          cause="facility_location")
        return chosen

    def _log_select(s, rec, novel, gen_record=None, cause="facility_location"):
        """Append a ledger-shaped survival-selection event. Events land on the
        director's `_select_log` (whole-run, inspectable) AND on the current
        gen_record's `selection` list (per-generation, inspectable in the
        returned lineage). ev/cause/metrics/result shape matches the trace."""
        ev = dict(ev="select", cause=cause,
                  metrics=dict(name=rec["name"],
                               fitness=round(rec["fitness"], 4),
                               novel=bool(novel),
                               families=sorted(rec["diagnosis"]["families"]),
                               bureau=rec.get("brief", {}).get("bureau")),
                  result="survived")
        s._select_log.append(ev)
        if gen_record is not None:
            gen_record.setdefault("selection", []).append(ev)
        return ev

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
                       parent=brief.get("parent"),
                       mutation=brief.get("mutation"),
                       bureau=brief.get("bureau"))
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


def _is_eligible(rec):
    """A ship record is eligible (selectable as survivor OR as 'best') iff it is
    legal AND fully fueled. The single source of truth for eligibility, shared by
    select_survivors and _fittest_eligible so 'best' can never name a ship that
    could not survive (Cassandra v0.7 pass: closes the best/survivor asymmetry)."""
    d = rec["diagnosis"]
    return d.get("legal", True) and sum(d["demand_unmet"].values()) == 0


def _fittest_eligible(records):
    """Highest-fitness ELIGIBLE ship; fall back to the raw fittest only if a
    generation is wholly broken (so a degenerate gen never raises). Inert on
    healthy runs — every ship is eligible — so it cannot perturb the catalogue."""
    pool = [r for r in records if _is_eligible(r)] or records
    return max(pool, key=lambda r: r["fitness"])


def _tag(brief):
    return "%s/%d" % (brief["faction"]["name"].split()[0], brief["seed"])


def _story_sig(diag):
    """The event-STORY signature of a ship, derived ONLY from its diagnosis:
    its sorted family signature plus its sorted reject-cause narrative (the
    'cannon-overload story'). Two ships with the same families AND the same
    reject pattern told the same story — which is exactly what Austerity's
    anti-repeat term penalises. Reads no score(), no geometry."""
    fams = frozenset(diag.get("families", {}))
    rejects = frozenset(diag.get("rejects", {}))
    return (fams, rejects)


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
