"""KitMash v0.5 tests — every new code path must leave a trace.

Three gates:
  1. fleet regression — GS-α reproduces the handoff numbers exactly
  2. auction win + eviction — rigged hub where a high-value challenger
     takes a low-value incumbent's clearance, exercising uncommit fully
  3. backjump — rigged hub where every candidate dies on the same blocker;
     the bounded ping-pong must terminate with a consistent ledger

Run: python3 test_kitmash.py
"""
import numpy as np
from kitmash import (Assembler, Part, Port, box, GUILD, build, gen_hull)

TESTF = dict(name="TestF", era=1, hull="#888888", accent="#aa6633",
             dark="#444444", glow="#88ccff", safety_factor=1.1,
             blasphemy=0.0, strain_taste=0.0, caps_unused=False,
             hose="catenary", debt=0.0)


# ------------------------------------------------------------- rigged parts
def make_hub(port_specs, mass=100.0):
    """Hub factory: a 1m cube with adversarially arranged ports."""
    def gen(fc, seed=0):
        p = Part("test_hub", {}, mass=mass, silhouette=0.1,
                 faction=fc["name"], era=fc["era"], color=fc["hull"],
                 label="hub")
        v, f = box(1, 1, 1); p.add(v, f)
        p.ports = [Port(*spec[:3], **spec[3]) for spec in port_specs]
        return p.finalize()
    return gen

P_TOP_S9 = ([0, 0, 0.5], [0, 0, 1], [1, 0, 0],
            dict(ptype="struct_S", size=0.3, gender=0, prio=9))
P_SIDE_M8 = ([0.5, 0, 0], [1, 0, 0], [0, 0, 1],
             dict(ptype="struct_M", size=1.0, gender=0, prio=8))


def gen_junk(fc, seed=0):
    """Low-value squatter: tiny body, huge clearance demand."""
    p = Part("junk", {}, mass=20, silhouette=0.05, faction=fc["name"],
             era=fc["era"], color=fc["dark"], label="junk")
    v, f = box(0.4, 0.4, 0.4); p.add(np.asarray(v) + [0, 0, 0.3], f)
    p.ports = [Port([0, 0, 0], [0, 0, -1], [1, 0, 0], "struct_S", 0.3, 1)]
    p.clearances = [(np.array([0.5, -1.0, -0.2]), np.array([4.0, 1.0, 1.2]))]
    return p.finalize()


def gen_big(fc, seed=0):
    """High-value module that lands inside junk's clearance volume."""
    p = Part("big", {}, mass=500, silhouette=0.5, faction=fc["name"],
             era=fc["era"], color=fc["accent"], label="big")
    v, f = box(2, 1, 1); p.add(np.asarray(v) + [-1.2, 0, 0], f)
    p.ports = [Port([0, 0, 0], [1, 0, 0], [0, 0, 1], "struct_M", 1.0, 1)]
    return p.finalize()


def gen_blocker(fc, seed=0):
    """Long boom that physically occupies big's only mounting space."""
    p = Part("blocker", {}, mass=30, silhouette=0.3, faction=fc["name"],
             era=fc["era"], color=fc["dark"], label="blocker")
    v, f = box(6, 1, 1); p.add(np.asarray(v) + [1.5, 0, 0.3], f)
    p.ports = [Port([0, 0, 0], [0, 0, -1], [1, 0, 0], "struct_S", 0.3, 1)]
    return p.finalize()


def rigged_run(gens, wants, hub):
    brief = dict(design_g=2.5, wants=wants,
                 budgets=dict(mass=5000, silhouette=3.0, parts=5))
    a = Assembler(TESTF, 1, brief, gens)
    a.run(hull_gen=hub)
    return a


def evs(a, kind):
    return [e for e in a.trace if e["ev"] == kind]


def no_hard_overlaps(a):
    L = a.ledger
    for i in range(len(L)):
        for j in range(i + 1, len(L)):
            lo1, hi1, p1 = L[i]; lo2, hi2, p2 = L[j]
            if p2 is p1.parent or p1 is p2.parent: continue
            assert not (np.all(lo1 < hi2) and np.all(lo2 < hi1)), \
                f"ledger overlap: {p1.label} vs {p2.label}"


# ------------------------------------------------------------------- tests
def test_fleet_regression():
    A = build(GUILD, 7, {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                         "heavy_cannon": 1.4, "antenna": 0.8,
                         "sensor_pod": 0.6}, heavy=1.0, span=3.0)
    stats = (len(A.placed), int(sum(p.mass for p in A.placed)),
             len(A.struts))
    assert stats == (10, 9464, 3), f"GS-α regression broke: {stats}"
    print("PASS  fleet regression (GS-α = 10 parts / 9464 kg / 3 struts)")


def test_auction_win_and_evict():
    a = rigged_run([gen_junk, gen_big], {"junk": 0.1, "big": 5.0},
                   make_hub([P_TOP_S9, P_SIDE_M8]))
    wins = [e for e in evs(a, "auction") if e["result"] == "challenger_wins"]
    holds = [e for e in evs(a, "auction") if e["result"] == "incumbent_holds"]
    ev = evs(a, "evict")
    assert wins, "no challenger_wins fired"
    assert ev and ev[0]["cause"] == "auction_evict", "no auction eviction"
    assert holds, "re-proposed junk should lose the counter-auction"
    labels = sorted(p.label for p in a.placed)
    assert labels == ["big", "hub"], f"final assembly wrong: {labels}"
    # uncommit invariants: budgets refunded exactly, ledger/clear purged
    spent = sum(p.mass for p in a.placed)
    assert abs((5000 - spent) - a.budget["mass"]) < 1e-6, "mass ledger drift"
    assert all(e[2].label != "junk" for e in a.ledger), "junk ghost in ledger"
    assert all(e[2].label != "junk" for e in a.clear), "junk ghost clearance"
    assert a.budget["parts"] == 5 - 2, "parts budget not refunded"
    no_hard_overlaps(a)
    print(f"PASS  auction win + evict (bids: challenger "
          f"{wins[0]['metrics']['challenger']} > incumbent "
          f"{wins[0]['metrics']['incumbent']}; counter-auction held)")


def test_backjump():
    a = rigged_run([gen_blocker, gen_big], {"blocker": 1.0, "big": 5.0},
                   make_hub([P_TOP_S9, P_SIDE_M8]))
    bj = evs(a, "backjump")
    assert bj, "no backjump fired"
    assert bj[0]["conflict_set"], "backjump lacks conflict set"
    assert evs(a, "evict"), "backjump did not evict"
    assert a.backjumps_left >= 0, "backjump budget overrun"
    # bounded ping-pong must terminate consistently: exactly one of the
    # two rivals survives, no ledger overlap, budgets coherent
    labels = sorted(p.label for p in a.placed)
    assert labels in (["big", "hub"], ["blocker", "hub"]), labels
    spent = sum(p.mass for p in a.placed)
    assert abs((5000 - spent) - a.budget["mass"]) < 1e-6, "mass ledger drift"
    no_hard_overlaps(a)
    print(f"PASS  backjump ({len(bj)} jump(s), conflict_set="
          f"{bj[0]['conflict_set']}, survivor={labels})")


if __name__ == "__main__":
    test_fleet_regression()
    test_auction_win_and_evict()
    test_backjump()
    print("ALL GATES PASS")
