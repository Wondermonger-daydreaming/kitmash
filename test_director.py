"""test_director.py — gates for the KITMASH creative director (spec §5).

Six gates:
  1. noop regression   — identity-policy director ⇒ canonical fleet
                          byte-identical (overlaps Reflex's surgeon gate).
  2. tie-break fires    — a rigged tie ⇒ on_tie chooses the diversity pick,
                          a tie_break event is logged, ship stays legal.
  3. review archaeology — review() of a known fleet trace returns the right
                          counts (cross-checked against the trace directly).
  4. breeding           — blend/splice produce valid briefs; child builds,
                          is legal, and is reviewable.
  5. goodhart detector  — a synthetic lineage with rising fitness + falling
                          diversity trips goodhart_warning; a healthy one does
                          not.
  6. evolve smoke       — evolve(generations=2, population=3) runs, every ship
                          cooks (legal), lineage record well-formed, the
                          proportional-verification rider is exercised.

Run: ../.venv/bin/python test_director.py
"""
import hashlib
import json

import numpy as np

from kitmash import (Assembler, Part, Port, box, GUILD, FERAL, build,
                     gen_radiator, gen_reactor, gen_turret)
from director import (Director, make_brief, no_hard_overlaps, _family_of)


# canonical regression anchor (handoff §2)
# P3 re-baseline: e6aeccfe352bba16f288785ea23e5bc3 -> 80ddaccccc594b2a7cc8c7b40a129086
# (hull weld-FACES replaced the whole-box anchor; strut endpoints + relief moved,
#  topology unchanged). ANCHOR_STATS (parts/mass/struts) is invariant across P3.
ANCHOR_MD5 = "80ddaccccc594b2a7cc8c7b40a129086"
ANCHOR_STATS = (10, 9464, 3)


# ----------------------------------------------------------- shared helpers
def _canonical_export_dict(director):
    """Build the canonical 5-ship fleet exactly as kitmash.__main__ does,
    threading `director` through every build, and return the export dict."""
    from kitmash import export
    wants_g = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
               "heavy_cannon": 1.4, "antenna": 0.8, "sensor_pod": 0.6}
    wants_f = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
               "heavy_cannon": 2.2, "sensor_pod": 1.0, "antenna": 0.4}
    wants_d = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
               "heavy_cannon": 1.8, "radiator": 2.4, "sensor_pod": 1.2,
               "antenna": 0.8}
    wants_e = {"engine": 3.0, "fuel_tank": 2.5, "wing": 1.6,
               "heavy_cannon": 0.9, "turret": 2.6, "reactor": 2.3,
               "sensor_pod": 0.4, "antenna": 0.3}
    A = build(GUILD, 7, wants_g, heavy=1.0, span=3.0, director=director)
    B = build(GUILD, 7, wants_g, heavy=1.7, span=3.9, parent="GS-α",
              mutation="heavy 1.0→1.7, span 3.0→3.9", director=director)
    C = build(FERAL, 23, wants_f, heavy=1.4, span=3.4, director=director)
    D = build(FERAL, 41, wants_d, heavy=1.2, span=3.2,
              extra_gens=[gen_radiator], parent="FV-γ",
              mutation="+radiator gene, wants reshuffled", director=director)
    E = build(FERAL, 101, wants_e, heavy=1.0, span=3.0,
              extra_gens=[gen_reactor, gen_turret], parent="FV-γ",
              mutation="+reactor/turret genes, electrified", director=director)
    return export(
        [("GS-α  «Lawful Mean»", A, np.array([0, -7.5, 0]), "Plate XLVII"),
         ("GS-β  «Heavier Daughter»", B, np.array([0, 0, 0]), "Plate XLVIII"),
         ("FV-γ  «Tape Holds»", C, np.array([0, 7.5, 0]), "Plate XLIX"),
         ("FV-δ  «Cold Shoulder»", D, np.array([0, 15, 0]), "Plate L"),
         ("FV-ε  «Loom»", E, np.array([0, 22.5, 0]), "Plate LI")],
        "/tmp/_director_test_fleet.json")


def _identity_director():
    """A trivial director whose on_tie is identity and tie_eps=0 (never fires
    even on a tie) — the regression policy."""
    d = Director(tie_eps=0.0)
    d._brief = {"tie_policy": "identity"}
    return d


# ----------------------------------------------------------------- gate 1
def test_noop_regression():
    """Identity-policy director with tie_eps=0 ⇒ canonical fleet byte-
    identical to the director=None path (and to the on-disk md5 anchor)."""
    none_dict = _canonical_export_dict(None)
    # uids advance with every Part built; building the fleet twice in one
    # process shifts the counter, so uid-bearing string fields differ while
    # the GEOMETRY is byte-identical. Strip uid-bearing fields; the on-disk
    # md5 anchor below is the hard byte-identity gate.
    ident_dict = _canonical_export_dict(_identity_director())

    UID_FIELDS = ("part_id", "port", "host_port", "part_port", "evicted",
                  "target", "victim", "instigator")

    def scrub(d):
        out = json.loads(json.dumps(d))
        for sh in out["ships"]:
            for ev in sh["trace"]:
                for k in UID_FIELDS:
                    ev.pop(k, None)
                # nested rivals carry no uids, but conflict_set / among do
                ev.pop("conflict_set", None)
                ev.pop("among", None)
        return out
    a, b = scrub(none_dict), scrub(ident_dict)
    assert a == b, "identity director diverged from director=None"

    # GS-α stats anchor
    gs = none_dict["ships"][0]["stats"]
    assert (gs["parts"], gs["mass"], gs["struts"]) == ANCHOR_STATS, \
        f"GS-α stats {gs} != {ANCHOR_STATS}"

    # the on-disk md5 anchor: a fresh director=None export of GS-α only is
    # what kitmash.py writes; confirm the full canonical run reproduces the
    # frozen file when written exactly as __main__ does.
    import subprocess
    import os
    import sys
    # reuse the interpreter running this test (numpy is already importable in
    # it, since we got here) — layout-independent, so the gate cooks in both
    # the lab tree and the flat public mirror.
    subprocess.run([sys.executable, "kitmash.py", "/tmp/_anchor_check.json"],
                   check=True, cwd=os.path.dirname(os.path.abspath(__file__)),
                   stdout=subprocess.DEVNULL)
    md5 = hashlib.md5(open("/tmp/_anchor_check.json", "rb").read()).hexdigest()
    assert md5 == ANCHOR_MD5, f"md5 {md5} != anchor {ANCHOR_MD5}"
    print("PASS  noop regression (identity director == director=None; "
          "md5 anchor holds)")


# ----------------------------------------------------------------- gate 2
def test_tie_break_fires():
    """A rigged hub offers two equal-score candidate families. A diversity
    director must reorder on_tie toward the LESS-placed family, log a
    tie_break event, and the ship must stay legal."""
    TESTF = dict(name="TestF", era=1, hull="#888888", accent="#aa6633",
                 dark="#444444", glow="#88ccff", safety_factor=1.1,
                 blasphemy=0.0, strain_taste=0.0, caps_unused=False,
                 hose="catenary", debt=0.0)

    # Two families the SAMPLER scores identically and constantly: silhouette 0
    # (no silhouette term) and absent from `wants` (want term 0 for both,
    # regardless of placed count). The sampler's own (1+1.5n) diversity divisor
    # therefore CANNOT separate them — every candidacy is a genuine 0.0-vs-0.0
    # tie. The only thing that can break it is the director's diversity policy,
    # reading placed_families from the tie-context. So when one family is
    # already placed, on_tie MUST reorder toward the other and log tie_break.
    def gen_alpha(fc, seed=0):
        p = Part("fam_alpha", {}, mass=80.0, silhouette=0.0,
                 faction=fc["name"], era=fc["era"], color=fc["hull"],
                 label="fam_alpha")
        v, f = box(0.6, 0.6, 0.6); p.add(v, f)
        p.ports = [Port([0, 0, 0], [0, 0, 1], [1, 0, 0], "struct_S", 0.3, 1)]
        return p.finalize()

    def gen_beta(fc, seed=0):
        p = Part("fam_beta", {}, mass=80.0, silhouette=0.0,
                 faction=fc["name"], era=fc["era"], color=fc["hull"],
                 label="fam_beta")
        v, f = box(0.6, 0.6, 0.6); p.add(v, f)
        p.ports = [Port([0, 0, 0], [0, 0, 1], [1, 0, 0], "struct_S", 0.3, 1)]
        return p.finalize()

    def make_hub(fc, seed=0):
        p = Part("test_hub", {}, mass=100.0, silhouette=0.1,
                 faction=fc["name"], era=fc["era"], color=fc["hull"],
                 label="hub")
        v, f = box(3, 3, 1); p.add(v, f)
        # two well-separated downward struct_S ports so two parts fit cleanly
        p.ports = [
            Port([-1.0, 0, 0.5], [0, 0, 1], [1, 0, 0], "struct_S", 0.3, 0,
                 prio=9),
            Port([1.0, 0, 0.5], [0, 0, 1], [1, 0, 0], "struct_S", 0.3, 0,
                 prio=8)]
        return p.finalize()

    # neither family is in `wants` → constant 0.0 score for both → tie
    brief = dict(design_g=2.5, wants={},
                 budgets=dict(mass=5000, silhouette=3.0, parts=10))

    d = Director(tie_eps=0.05)
    d._brief = {"tie_policy": "diversity"}
    a = Assembler(TESTF, 1, brief, [gen_alpha, gen_beta], director=d).run(
        hull_gen=make_hub)

    ties = [e for e in a.trace if e.get("ev") == "tie_break"]
    assert ties, "no tie_break event logged on a rigged tie"
    # the diversity pick: the first port should choose whichever family had the
    # lowest placed count at decision time (both 0 → stable, picks alpha; the
    # SECOND port then favors beta, the now-less-placed family).
    placed_fams = [p.family for p in a.placed if p.family != "test_hub"]
    assert "fam_alpha" in placed_fams and "fam_beta" in placed_fams, \
        f"diversity tie-break failed to spread families: {placed_fams}"
    assert no_hard_overlaps(a), "tie-broken ship has hard overlaps"
    print(f"PASS  tie-break fires ({len(ties)} tie_break events, "
          f"families spread: {sorted(set(placed_fams))})")


# ----------------------------------------------------------------- gate 3
def test_review_archaeology():
    """review() of a real fleet trace returns counts consistent with a
    direct walk of the same trace (cross-check the placard discipline)."""
    a = build(FERAL, 101,
              {"engine": 3.0, "fuel_tank": 2.5, "wing": 1.6,
               "heavy_cannon": 0.9, "turret": 2.6, "reactor": 2.3,
               "sensor_pod": 0.4, "antenna": 0.3},
              heavy=1.0, span=3.0, extra_gens=[gen_reactor, gen_turret])
    stats = dict(parts=len(a.placed),
                 mass=int(sum(p.mass for p in a.placed)),
                 struts=len(a.struts), hoses=len(a.hoses))
    d = Director()
    diag = d.review(a.trace, stats)

    # independent ground truth from the trace
    commits = sum(1 for e in a.trace if e.get("ev") == "commit")
    repairs = sum(1 for e in a.trace if e.get("ev") == "repair")
    hoses = sum(1 for e in a.trace if e.get("ev") == "hose")
    unmet = sum(1 for e in a.trace if e.get("ev") == "demand_unmet")

    assert diag["parts"] == commits, (diag["parts"], commits)
    assert diag["repairs"] == repairs, (diag["repairs"], repairs)
    assert diag["hoses"] == hoses, (diag["hoses"], hoses)
    assert sum(diag["demand_unmet"].values()) == unmet
    assert diag["struts"] == stats["struts"]
    # families recovered, hull excluded, sums to non-hull commits
    assert sum(diag["families"].values()) == commits - 1, \
        (dict(diag["families"]), commits)
    assert 0.0 <= diag["monoculture"] <= 1.0
    assert diag["strut_per_part"] == round(stats["struts"] / commits, 3)
    print(f"PASS  review archaeology (parts={diag['parts']}, "
          f"repairs={diag['repairs']}, hoses={diag['hoses']}, "
          f"families={dict(diag['families'])})")


# ----------------------------------------------------------------- gate 4
def test_breeding():
    """blend_gen_params + splice_trace produce valid briefs; the child
    builds, is legal, and reviews."""
    d = Director()
    pa = make_brief(GUILD, 7,
                    {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                     "heavy_cannon": 1.4}, heavy=1.0, span=3.0)
    pb = make_brief(GUILD, 11,
                    {"engine": 3.0, "fuel_tank": 2.0, "sensor_pod": 1.5,
                     "antenna": 1.0}, heavy=2.0, span=4.0)

    blend = d.blend_gen_params(pa, pb, t=0.5)
    assert abs(blend["heavy"] - 1.5) < 1e-6, blend
    assert abs(blend["span"] - 3.5) < 1e-6, blend
    assert isinstance(blend["seed"], int) and blend["seed"] >= 0

    child = d.splice_trace(pa, pb, fit_a=5.0, fit_b=2.0)
    # fitter parent is pa (guild, knobs from pa)
    assert child["faction"] is GUILD
    assert abs(child["heavy"] - 1.5) < 1e-6        # blended
    # wants take the louder taste per family
    assert child["wants"]["engine"] == 3.0
    assert child["wants"]["sensor_pod"] == 1.5     # only pb had it
    assert child["wants"]["heavy_cannon"] == 1.4   # only pa had it
    assert child["parent"] and child["mutation"]

    # the child must actually build, cook (legal), and review
    a = build(child["faction"], child["seed"], child["wants"],
              heavy=child["heavy"], span=child["span"],
              extra_gens=child["extra_gens"])
    assert no_hard_overlaps(a), "spliced child has hard overlaps"
    diag = d.review(a.trace,
                    dict(parts=len(a.placed),
                         mass=int(sum(p.mass for p in a.placed)),
                         struts=len(a.struts), hoses=len(a.hoses)))
    assert diag["parts"] >= 2, "spliced child built nothing"
    print(f"PASS  breeding (blend heavy={blend['heavy']} span={blend['span']}; "
          f"child {child['parent']} built {diag['parts']} parts, legal)")


# ----------------------------------------------------------------- gate 5
def test_goodhart_detector():
    """A synthetic lineage with rising fitness + falling diversity trips
    goodhart_warning; a healthy lineage (fitness up, diversity steady/up)
    does not."""
    d = Director()
    # sick: fitness 5→8 while diversity 0.9→0.4
    warn = d.lineage_pathology(fit=8.0, diversity=0.4,
                               prev_fit=5.0, prev_div=0.9)
    assert warn is not None and warn["ev"] == "goodhart_warning", warn
    assert warn["cause"] == "fitness_up_diversity_down"

    # healthy: fitness up, diversity also up
    ok = d.lineage_pathology(fit=8.0, diversity=0.95,
                             prev_fit=5.0, prev_div=0.9)
    assert ok is None, ok
    # healthy: fitness flat, diversity down (not the Goodhart signature)
    ok2 = d.lineage_pathology(fit=5.0, diversity=0.4,
                              prev_fit=5.0, prev_div=0.9)
    assert ok2 is None, ok2
    # first generation: nothing to compare
    assert d.lineage_pathology(8.0, 0.4, None, None) is None

    # SUSTAINED collapse (Cassandra charge 3): fitness climbing while diversity
    # holds FLAT at the floor — the Goodhart endgame the slope-only detector
    # was blind to. Must now flag.
    farmed = d.lineage_pathology(fit=7.0, diversity=0.3,
                                 prev_fit=6.0, prev_div=0.3)
    assert farmed is not None and \
        farmed["cause"] == "fitness_up_diversity_floored", farmed
    assert d.lineage_pathology(100.0, 0.1, 1.0, 0.1) is not None
    # a healthy STABLE converged fleet (flat fitness, low diversity) is
    # monotonous, not pathological — must stay clean.
    assert d.lineage_pathology(7.0, 0.33, 7.0, 0.33) is None

    # the verification rider must NOT inflate on a healthy, stable, converged
    # fleet (Cassandra charge 2 / directive P4): the REALISTIC case is >=8 ships
    # with IDENTICAL *rich* (legal+fueled+multi-family) signatures, all healthy
    # — the actual body that occurs in evolve(). The masking bug the audit found
    # was a 2-ship disjoint case that never reached convergence; this exercises
    # a converged-rich fleet of 8 ships sharing one 4-family signature.
    rich_sig = {"engine": 1, "fuel_tank": 1, "wing": 2, "heavy_cannon": 1}
    converged_healthy = dict(
        ships=[dict(name="c%d" % i, fitness=10.6,
                    diagnosis=dict(legal=True, demand_unmet={},
                                   families=dict(rich_sig)))
               for i in range(8)],
        diversity=0.125)          # 8 identical signatures → 1/8 (well below floor)
    # the case is genuinely "all healthy" (legal AND fueled AND multi-family):
    assert all(s["diagnosis"]["legal"]
               and sum(s["diagnosis"]["demand_unmet"].values()) == 0
               and len(s["diagnosis"]["families"]) >= 3
               for s in converged_healthy["ships"]), "test setup not rich+healthy"
    cv = d.verification_plan(converged_healthy, prev_fit=10.6, prev_div=0.125)
    assert cv["verification_budget"] == 0, \
        "healthy converged fleet drew verification budget — the rider's sin"

    # the verification plan must escalate on the anomaly, proportionally
    fake_gen = dict(
        ships=[dict(name="x", fitness=8.0,
                    diagnosis=dict(legal=True, demand_unmet={},
                                   families={"engine": 1}))],
        diversity=0.4)
    plan = d.verification_plan(fake_gen, prev_fit=5.0, prev_div=0.9)
    assert plan["verification_budget"] > 0, "anomaly did not escalate review"
    assert plan["verification_budget"] <= 3, "verification not capped/bounded"
    # a clean generation gets ZERO extra skeptics (the rider)
    clean_gen = dict(
        ships=[dict(name="a", fitness=8.0,
                    diagnosis=dict(legal=True, demand_unmet={},
                                   families={"engine": 1, "wing": 1})),
               dict(name="b", fitness=7.0,
                    diagnosis=dict(legal=True, demand_unmet={},
                                   families={"turret": 1, "reactor": 1}))],
        diversity=1.0)
    clean = d.verification_plan(clean_gen, prev_fit=7.0, prev_div=1.0)
    assert clean["verification_budget"] == 0, \
        "clean generation spawned a tribunal — the rider is violated"
    print("PASS  goodhart detector (sick lineage flagged, healthy clean; "
          "verification proportional: sick→%d, clean→0)"
          % plan["verification_budget"])


# ----------------------------------------------------------------- gate 6
def test_evolve_smoke():
    """evolve(generations=2, population=3) runs; every ship cooks (legal),
    the lineage record is well-formed, and the proportional-verification
    rider is exercised."""
    d = Director()
    lineage = d.evolve(generations=2, population=3, seed=0)

    assert set(lineage) >= {"generations", "warnings", "best_overall"}
    assert len(lineage["generations"]) == 2
    for gr in lineage["generations"]:
        assert len(gr["ships"]) == 3, gr
        assert "diversity" in gr and "best" in gr
        assert "verification" in gr
        vp = gr["verification"]
        assert "verification_budget" in vp and vp["verification_budget"] <= 3
        for r in gr["ships"]:
            assert set(r) >= {"name", "brief", "diagnosis", "fitness",
                              "stats", "parents", "legal"}
            assert r["legal"], f"{r['name']} did not cook (hard overlaps)"
            assert r["stats"]["parts"] >= 2, f"{r['name']} built nothing"
            assert isinstance(r["fitness"], float)
    assert lineage["best_overall"]
    print("PASS  evolve smoke (2×3 ships built & cooked; lineage well-formed; "
          "verification rider exercised)")


# ----------------------------------------------------------------- gate 7
def test_repair_policy_promoted():
    """The 3b promotion (P2): on_repair_choice is genuinely LIVE behind the
    `repair_policy_active` flag, faction-divergent brace taste is structurally
    reachable, and the canonical anchor is byte-identical even with the flag ON.

    Construction: a STRICT (relief, L)-tie between two braces of DIFFERENT
    anchor/geometry — the set the legacy accumulator treats as interchangeable.
    Guild taste keeps the spine/legacy head (the lexicographically-clean anchor);
    feral taste re-resolves the SAME tie toward the louder anchor. The two
    factions therefore COMMIT DIFFERENT braces on identical input — proving the
    surface drives selection rather than returning a frozen no-op.

    rng-free, network-free, geometry-free divergence (anchor-name key)."""
    # two genuinely interchangeable braces (same relief, same L) of distinct
    # geometry — a real tie, not the canonical fleet's geometrically-identical one
    def fresh_viable():
        return [
            dict(relief=0.6, L=1.0, anchor_part="aaa_clean",
                 a=[0.0, 0.0, 0.0], b=[1.0, 0.0, 0.0], vol=-1),
            dict(relief=0.6, L=1.0, anchor_part="zzz_loud",
                 a=[0.0, 0.0, 0.0], b=[0.0, 1.0, 0.0], vol=-1),
        ]
    ctx_g = {"faction": GUILD["name"]}
    ctx_f = {"faction": FERAL["name"]}

    # 1) FLAG OFF ⇒ the historical no-op exactly: None for BOTH factions, no log.
    d_off = Director(repair_policy_active=False)
    assert d_off.on_repair_choice(fresh_viable(), ctx_g) is None
    assert d_off.on_repair_choice(fresh_viable(), ctx_f) is None
    assert d_off._select_log == [], "flag-off path must never log"

    # 2) FLAG ON + GUILD ⇒ spine head == legacy argmin ⇒ suppressed (None), so
    #    the legacy `aaa_clean` brace rides through; no spurious event.
    d_g = Director(repair_policy_active=True)
    pick_g = d_g.on_repair_choice(fresh_viable(), ctx_g)
    assert pick_g is None, ("guild taste == legacy spine, must suppress", pick_g)
    assert d_g._select_log == [], "guild no-op must not log"
    guild_commit = fresh_viable()[0]["anchor_part"]   # legacy head rides

    # 3) FLAG ON + FERAL ⇒ the louder anchor wins the SAME strict tie ⇒ a real
    #    permutation whose head differs from legacy ⇒ kitmash commits viable[head]
    #    and a ledger-shaped repair_choice event is appended.
    vf = fresh_viable()
    d_f = Director(repair_policy_active=True)
    pick_f = d_f.on_repair_choice(vf, ctx_f)
    assert pick_f is not None, "feral taste must reorder a genuine tie"
    assert vf[pick_f[0]]["anchor_part"] == "zzz_loud", \
        ("feral must commit the louder anchor", pick_f)
    assert len(d_f._select_log) == 1, "feral divergence must log exactly once"
    ev = d_f._select_log[0]
    assert ev["ev"] == "repair_choice" and ev["cause"] == "rank_braces" \
        and ev["result"] == "reordered", ev
    assert ev["metrics"]["faction"] == FERAL["name"]
    feral_commit = vf[pick_f[0]]["anchor_part"]

    # 4) THE DIVERGENCE: guild and feral commit DIFFERENT braces on the SAME input
    assert guild_commit != feral_commit, \
        ("faction taste failed to diverge", guild_commit, feral_commit)

    # 5) ORDER-INDEPENDENCE (the policy is live, not a frozen passthrough): feed
    #    the SAME braces in REVERSED order; the feral committed brace is the same
    #    physical strut (zzz_loud) regardless of input order — the live policy
    #    re-derives the choice deterministically rather than echoing position.
    vr = list(reversed(fresh_viable()))
    d_r = Director(repair_policy_active=True)
    pick_r = d_r.on_repair_choice(vr, ctx_f)
    chosen_r = vr[pick_r[0]]["anchor_part"] if pick_r is not None \
        else vr[0]["anchor_part"]
    assert chosen_r == "zzz_loud", \
        ("policy must be order-independent (live), not positional", chosen_r)

    # 6) ANCHOR SAFETY: the flag-ON canonical GS-α build is byte-identical to the
    #    director=None legacy path (md5 anchor holds, no repair_choice events).
    import subprocess
    import os
    import sys
    subprocess.run([sys.executable, "kitmash.py", "/tmp/_promote_anchor.json"],
                   check=True, cwd=os.path.dirname(os.path.abspath(__file__)),
                   stdout=subprocess.DEVNULL)
    md5 = hashlib.md5(
        open("/tmp/_promote_anchor.json", "rb").read()).hexdigest()
    assert md5 == ANCHOR_MD5, f"md5 {md5} != anchor {ANCHOR_MD5}"

    # full canonical fleet with an ACTIVE repair-policy director ⇒ every strut
    # decision is byte-identical to the legacy build, zero repair_choice events.
    def _active_director():
        d = Director(repair_policy_active=True)
        d._brief = {"tie_policy": "identity"}     # isolate the repair surface
        return d
    legacy_dict = _canonical_export_dict(None)
    active_dict = _canonical_export_dict(_active_director())
    UID_FIELDS = ("part_id", "port", "host_port", "part_port", "evicted",
                  "target", "victim", "instigator")

    def scrub(d):
        out = json.loads(json.dumps(d))
        for sh in out["ships"]:
            for ev2 in sh["trace"]:
                for k in UID_FIELDS:
                    ev2.pop(k, None)
                ev2.pop("conflict_set", None)
                ev2.pop("among", None)
        return out
    assert scrub(legacy_dict) == scrub(active_dict), \
        "active repair-policy director diverged from legacy on canonical fleet"
    rc = [ev2 for sh in active_dict["ships"] for ev2 in sh["trace"]
          if ev2.get("ev") == "repair_choice"]
    assert rc == [], ("active director logged repair_choice on canonical", rc)

    print("PASS  repair policy promoted (flag gates the surface; guild→%s / "
          "feral→%s diverge; order-independent; canonical byte-identical, "
          "md5 anchor holds)" % (guild_commit, feral_commit))


if __name__ == "__main__":
    test_noop_regression()
    test_tie_break_fires()
    test_review_archaeology()
    test_breeding()
    test_goodhart_detector()
    test_evolve_smoke()
    test_repair_policy_promoted()
    print("ALL DIRECTOR GATES PASS")
