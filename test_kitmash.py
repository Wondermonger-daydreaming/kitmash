"""KitMash v0.6 tests — every new code path must leave a trace.

Eight gates:
  1. fleet regression — GS-α reproduces the handoff numbers exactly,
     including the hose path (geometric identity, not just stats)
  2. auction win + eviction — rigged hub where a high-value challenger
     takes a low-value incumbent's clearance, exercising uncommit fully
  3. backjump — rigged hub where every candidate dies on the same blocker;
     the bounded ping-pong must terminate with a consistent ledger
  4. segregation — a high-volt net refuses the cheap fuel trunk and pays
     for the long way around
  5. loom — the second compatible net rides the first one's channel
     because the discount makes it cheapest
  6. capacity + rip-up — a wider bundle evicts a squatter from a narrow
     channel; the victim reroutes via its expensive alternative
  7. houdini round trip — placement records (generator + gen_params +
     orient/P) rehydrate into geometry IDENTICAL to what the assembler
     placed: meshes, ports, grommets; strut/hose decisions match their
     baked counterparts. This is the part-HDA contract, proven in numpy.
  8. anchorable surfaces — struts may only weld where the neighbor
     declares (anchor_vols); no declaration = legacy whole-AABB. Same
     arm, same physics: declared plate takes the weld, anchor-starved
     hub rejects cleanly (every brace parallel, composed relief short).

Run: python3 test_kitmash.py
"""
import numpy as np
from kitmash import (Assembler, Part, Port, Grommet, box, GUILD, FERAL,
                     build, gen_hull, gen_reactor, gen_turret, seg_share_ok,
                     xform)

TESTF = dict(name="TestF", era=1, hull="#888888", accent="#aa6633",
             dark="#444444", glow="#88ccff", safety_factor=1.1,
             blasphemy=0.0, strain_taste=0.0, caps_unused=False,
             hose="catenary", debt=0.0)


# ------------------------------------------------------------- rigged parts
def make_hub(port_specs, mass=100.0, anchor_vols=None):
    """Hub factory: a 1m cube with adversarially arranged ports."""
    def gen(fc, seed=0):
        p = Part("test_hub", {}, mass=mass, silhouette=0.1,
                 faction=fc["name"], era=fc["era"], color=fc["hull"],
                 label="hub")
        v, f = box(1, 1, 1); p.add(v, f)
        p.ports = [Port(*spec[:3], **spec[3]) for spec in port_specs]
        if anchor_vols is not None:
            p.anchor_vols = [(np.array(lo, float), np.array(hi, float))
                             for lo, hi in anchor_vols]
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
GOLDEN_ALPHA_HOSE = [[1.8, 0.0, 1.0], [1.0, 0.0, 0.75], [-1.0, 0.0, 0.75],
                     [-3.2, 0.0, 0.75], [-3.7, 0.0, 0.3]]

def test_fleet_regression():
    A = build(GUILD, 7, {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                         "heavy_cannon": 1.4, "antenna": 0.8,
                         "sensor_pod": 0.6}, heavy=1.0, span=3.0)
    stats = (len(A.placed), int(sum(p.mass for p in A.placed)),
             len(A.struts))
    assert stats == (10, 9464, 3), f"GS-α regression broke: {stats}"
    assert len(A.hoses) == 1, "GS-α hose count changed"
    pts = [[round(x, 3) for x in pt] for pt in A.hoses[0]["pts"]]
    assert pts == GOLDEN_ALPHA_HOSE, f"GS-α hose path drifted: {pts}"
    print("PASS  fleet regression (GS-α = 10/9464/3, hose path golden)")


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


# ------------------------------------------------------ routing v2 rigs
def rig_part(label, pos, groms, gedges=(), supplies=(), demands=()):
    """Fabricate an already-placed part: world grommets only."""
    p = Part(label, {}, mass=10, silhouette=0.1, faction="TestF", era=1,
             color="#888", label=label)
    p.wgrom = [(np.array(pos, float) + np.array(gp, float),
                Grommet(gp, ct, size)) for gp, ct, size in groms]
    p.gedges = list(gedges)
    p.supplies = [list(x) for x in supplies]
    p.demands = [list(x) for x in demands]
    return p


def rig_route(parts):
    a = Assembler(TESTF, 1, dict(design_g=2.5, wants={},
                                 budgets=dict(mass=1, silhouette=1, parts=1)),
                  [])
    a.placed = list(parts)
    a.route()
    return a


def test_segregation():
    # A fuel bus sits exactly on the cheap straight line between a high-volt
    # supply and demand. Forbidden pair: the HV net must pay for the leap.
    layout = lambda ct: [
        rig_part("S", [0, 0, 0], [([0, 0, 0], ct, 0.2)],
                 supplies=[(ct, 1.0)]),
        rig_part("BUS", [0, 0, 0], [([1, 0, 0], "fuel", 0.2),
                                    ([2, 0, 0], "fuel", 0.2),
                                    ([3, 0, 0], "fuel", 0.2)],
                 gedges=[(0, 1), (1, 2)]),
        rig_part("D", [4, 0, 0], [([0, 0, 0], ct, 0.2)],
                 demands=[(ct, 1.0)])]
    hv = rig_route(layout("high_volt"))
    assert len(hv.hoses) == 1, "HV net failed to route"
    assert len(hv.hoses[0]["pts"]) == 2, \
        f"HV net rode the fuel bus: {hv.hoses[0]['pts']}"
    cg = [e for e in hv.trace if e["ev"] == "channel_graph"]
    assert cg and cg[0]["metrics"]["seg_pruned"] >= 6, "no pruning recorded"
    # control: coolant is friendly with fuel — it SHOULD ride the bus
    co = rig_route(layout("coolant"))
    assert len(co.hoses[0]["pts"]) == 5, \
        f"coolant refused the friendly bus: {co.hoses[0]['pts']}"
    print(f"PASS  segregation (HV pays the leap, "
          f"{cg[0]['metrics']['seg_pruned']} edges pruned; coolant rides)")


def test_loom():
    # Second compatible net prefers the discounted channel through D1's
    # grommet over its own slightly-shorter virgin leap.
    a = rig_route([
        rig_part("S", [0, 0, 0], [([0, 0, 0], "high_volt", 0.2)],
                 supplies=[("high_volt", 4.0)]),
        rig_part("D1", [3, 0, 0], [([0, 0, 0], "high_volt", 0.1)],
                 demands=[("high_volt", 1.0)]),
        rig_part("D2", [3, 1, 0], [([0, 0, 0], "high_volt", 0.1)],
                 demands=[("high_volt", 1.0)])])
    assert len(a.hoses) == 2, "loom rig failed to route both nets"
    h2 = [e for e in a.trace if e["ev"] == "hose"][1]
    assert h2["metrics"].get("loomed") == 1, f"no loom: {h2['metrics']}"
    assert [3.0, 0.0, 0.0] in a.hoses[1]["pts"], "net2 skipped the harness"
    print("PASS  loom (net2 rides net1's channel at 0.55x, loomed=1)")


def test_capacity_ripup():
    # Narrow bridge is the only channel wide enough for net2; net1 (thin)
    # squats it first. Net2 has NO capacity-legal path (the bypass carries
    # only 0.039 — enough for net1's 0.035, not net2's 0.040), so it must
    # rip net1 out; net1 reroutes via the thin bypass it still fits.
    a = rig_route([
        rig_part("S", [0, 0, 0], [([0, 0, 0], "high_volt", 0.2)],
                 supplies=[("high_volt", 10.0)]),
        rig_part("NARROW", [0, 0, 0], [([2.0, 0, 0], "high_volt", 0.06),
                                       ([4.6, 0, 0], "high_volt", 0.06)],
                 gedges=[(0, 1)]),
        rig_part("BYPASS", [0, 0, 0], [([2.0, 2.6, 0], "high_volt", 0.039),
                                       ([4.6, 2.6, 0], "high_volt", 0.039)],
                 gedges=[(0, 1)]),
        rig_part("D1", [6.3, 0, 0], [([0, 0, 0], "high_volt", 0.1)],
                 demands=[("high_volt", 1.0)]),     # dia 0.035
        rig_part("D2", [6.3, 1, 0], [([0, 0, 0], "high_volt", 0.1)],
                 demands=[("high_volt", 1.5)])])    # dia 0.040
    rips = [e for e in a.trace if e["ev"] == "rip_up"]
    assert rips and rips[0]["victim"] == "D1", f"no rip_up: {rips}"
    assert rips[0]["cause"] == "congestion"
    assert len(a.hoses) == 2, "a net was lost in the negotiation"
    hoses = [e for e in a.trace if e["ev"] == "hose"]
    assert any(h["metrics"].get("rerouted") for h in hoses), \
        "victim's reroute not marked"
    rer = [h for h in hoses if h["metrics"].get("rerouted")][0]
    assert a.ripups_left == 3, "rip budget not spent"
    unmet = [e for e in a.trace if e["ev"] == "demand_unmet"]
    assert not unmet, f"negotiation starved a net: {unmet}"
    print(f"PASS  capacity + rip-up (D2 evicts D1 from the narrow channel; "
          f"D1 reroutes, {rer['metrics']['hops']} hop direct)")


# --------------------------------------------- anchorable surfaces (gate 8)
def gen_arm(fc, seed=0):
    """Heavy cantilever: needs a strut on any TESTF struct_S joint
    (M = 200kg x 24.525 x 1.0m lever = 4905 N·m > 1818 cap)."""
    p = Part("arm", {}, mass=200, silhouette=0.1, faction=fc["name"],
             era=fc["era"], color=fc["dark"], label="arm")
    v, f = box(2.4, 0.3, 0.3); p.add(np.asarray(v) + [1.0, 0, 0.45], f)
    p.ports = [Port([0, 0, 0], [0, 0, -1], [1, 0, 0], "struct_S", 0.3, 1,
                    sym=1)]
    p.com = np.array([1.0, 0, 0.3])
    return p.finalize()


def test_anchor_semantics():
    """Roadmap 3: struts may only weld where the neighbor declares.
    Same arm, same physics — only the anchorable declaration changes."""
    arm_wants = {"arm": 5.0}
    # A: legacy hub (no declaration) — whole AABB anchorable, strut lands
    a = rigged_run([gen_arm], arm_wants, make_hub([P_TOP_S9]))
    assert "arm" in [p.label for p in a.placed], "baseline arm not placed"
    assert a.strut_segs and a.strut_segs[0]["vol"] == -1, \
        "legacy anchor should report vol=-1"
    # B: hub declares its top plate — the strut must land inside it
    b = rigged_run([gen_arm], arm_wants,
                   make_hub([P_TOP_S9],
                            anchor_vols=[([-0.5, -0.5, 0.45],
                                          [0.5, 0.5, 0.5])]))
    assert "arm" in [p.label for p in b.placed], "declared-plate arm lost"
    st = [s for s in b.strut_segs if s["kind"] == "strut"]
    assert st and st[0]["vol"] == 0, "strut did not record its anchor vol"
    bb = st[0]["b"]
    assert -0.5 <= bb[0] <= 0.5 and -0.5 <= bb[1] <= 0.5 \
        and 0.45 <= bb[2] <= 0.5, f"strut welded outside declared vol: {bb}"
    # C: hub only anchorable directly beneath the com — every brace is
    # parallel to the moment axis (relief 0.35), two compose to 0.4225M
    # = 2072 > 1818: clean reject, arm starves. Honest constraints.
    c = rigged_run([gen_arm], arm_wants,
                   make_hub([P_TOP_S9],
                            anchor_vols=[([0.8, -0.2, -0.5],
                                          [1.2, 0.2, -0.45])]))
    assert "arm" not in [p.label for p in c.placed], \
        "arm placed despite anchor-starved hub"
    rej = [e for e in c.trace if e["ev"] == "reject"
           and e.get("cause") == "moment_over_cap"]
    assert rej and rej[0]["result"] == "strut_insufficient", \
        f"expected strut_insufficient reject: {rej}"
    assert not c.strut_segs, "rejected arm left ghost strut decisions"
    print(f"PASS  anchorable surfaces (legacy vol=-1 holds; declared plate "
          f"weld at z={bb[2]:.2f}; anchor-starved hub rejects "
          f"relief={rej[0]['metrics']['relief']})")


# ----------------------------------------------- director no-op (gate 3c)
class _IdentityDirector:
    """Trivial director: tie_eps=0 means on_tie never fires on a genuine
    tie (s0-s1 < 0 is impossible for sorted scores); on_repair_choice and
    on_tie return None (identity) regardless. Proves the hook surface is
    inert — present but reorder-only and rng-free."""
    tie_eps = 0.0
    def on_tie(self, ranked, ctx): return None
    def on_repair_choice(self, viable, ctx): return None


def _alpha_build(director=None):
    return build(GUILD, 7, {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                            "heavy_cannon": 1.4, "antenna": 0.8,
                            "sensor_pod": 0.6}, heavy=1.0, span=3.0,
                 director=director)


def _world_signature(a):
    """A geometric+stats fingerprint of a built ship: every committed
    part's world meshes, struts, and stats. Byte-identity proxy that does
    not require disk I/O. NB: Part.uid embeds a global monotonic counter
    (Part._n), so two builds in one process get different #N suffixes for
    identical geometry — we key on family+label, NOT uid, exactly as the
    JSON export does (it never serializes uid)."""
    sig = []
    for p in a.placed:
        sig.append((p.family, p.label,
                    tuple(tuple(np.round(v, 6).ravel().tolist())
                          for v, f, c in p.world)))
    for v, f, c, owner in a.struts:
        sig.append(("strut", tuple(np.round(v, 6).ravel().tolist())))
    sig.append((len(a.placed), int(sum(p.mass for p in a.placed)),
                len(a.struts), len(a.hoses)))
    sig.append(tuple(tuple(map(lambda x: round(x, 6), pt))
                     for h in a.hoses for pt in h["pts"]))
    return sig


def test_director_noop():
    """3c: director=None AND a trivial identity-director both reproduce the
    canonical GS-α byte-identical. Proves (a) the hook path is a true no-op
    when director is None, and (b) an attached identity-director with
    tie_eps=0 never perturbs the build (gate fires only on real ties,
    identity-reorder is inert)."""
    # (a) director=None matches the canonical stats and golden hose path
    a0 = _alpha_build(director=None)
    stats0 = (len(a0.placed), int(sum(p.mass for p in a0.placed)),
              len(a0.struts))
    assert stats0 == (10, 9464, 3), f"director=None broke GS-α: {stats0}"
    pts0 = [[round(x, 3) for x in pt] for pt in a0.hoses[0]["pts"]]
    assert pts0 == GOLDEN_ALPHA_HOSE, f"director=None hose drift: {pts0}"

    # (b) identity-director (tie_eps=0, on_tie/on_repair_choice -> None)
    # produces a build geometrically identical to director=None
    a1 = _alpha_build(director=_IdentityDirector())
    assert _world_signature(a0) == _world_signature(a1), \
        "identity-director perturbed the canonical build"
    # no hook ever fired: tie_eps=0 cannot satisfy s0-s1<0, identity returns
    assert not [e for e in a1.trace if e["ev"] == "tie_break"], \
        "tie_break fired under tie_eps=0 (gate should never trigger)"
    assert not [e for e in a1.trace if e["ev"] == "repair_choice"], \
        "repair_choice fired under identity director (should be inert)"

    # full-disk byte-identity check against the regression anchor md5
    import json, hashlib, os
    from kitmash import export, FERAL, gen_radiator, gen_reactor, gen_turret
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
    # Part.uid embeds a process-global monotonic counter (Part._n) that the
    # trace serializes as part_id. To reproduce the fresh-process anchor md5
    # byte-for-byte (prior gates in this run advanced the counter), reset it
    # so the part_id sequence matches a clean `python kitmash.py` invocation.
    Part._n = 0
    A = build(GUILD, 7, wants_g, heavy=1.0, span=3.0)
    B = build(GUILD, 7, wants_g, heavy=1.7, span=3.9,
              parent="GS-α", mutation="heavy 1.0→1.7, span 3.0→3.9")
    C = build(FERAL, 23, wants_f, heavy=1.4, span=3.4)
    D = build(FERAL, 41, wants_d, heavy=1.2, span=3.2,
              extra_gens=[gen_radiator],
              parent="FV-γ", mutation="+radiator gene, wants reshuffled")
    E = build(FERAL, 101, wants_e, heavy=1.0, span=3.0,
              extra_gens=[gen_reactor, gen_turret],
              parent="FV-γ", mutation="+reactor/turret genes, electrified")
    tmp = "/tmp/test_director_noop_fleet.json"
    export([("GS-α  «Lawful Mean»", A, np.array([0, -7.5, 0]), "Plate XLVII"),
            ("GS-β  «Heavier Daughter»", B, np.array([0, 0, 0]), "Plate XLVIII"),
            ("FV-γ  «Tape Holds»", C, np.array([0, 7.5, 0]), "Plate XLIX"),
            ("FV-δ  «Cold Shoulder»", D, np.array([0, 15, 0]), "Plate L"),
            ("FV-ε  «Loom»", E, np.array([0, 22.5, 0]), "Plate LI")], tmp)
    md5 = hashlib.md5(open(tmp, "rb").read()).hexdigest()
    os.remove(tmp)
    assert md5 == "e6aeccfe352bba16f288785ea23e5bc3", \
        f"canonical fleet md5 drifted: {md5}"
    print("PASS  director no-op (director=None & identity-director both "
          "byte-identical; md5 anchor holds, no hooks fired)")


# ------------------------------------------------- houdini bridge (gate 7)
def test_houdini_roundtrip():
    """The part-HDA contract, proven host-agnostically: a placement record
    (generator name + gen_params + orient/P) must rehydrate into geometry
    identical to what the assembler committed. gen_params equality is the
    determinism checksum (derived values like tank h must reproduce)."""
    import kitmash_houdini as kh

    ships = [
        build(GUILD, 7, {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                         "heavy_cannon": 1.4, "antenna": 0.8,
                         "sensor_pod": 0.6}, heavy=1.0, span=3.0),
        build(FERAL, 101, {"engine": 3.0, "fuel_tank": 2.5, "wing": 1.6,
                           "heavy_cannon": 0.9, "turret": 2.6,
                           "reactor": 2.3, "sensor_pod": 0.4,
                           "antenna": 0.3}, heavy=1.0, span=3.0,
              extra_gens=[gen_reactor, gen_turret]),
    ]
    n_parts = n_struts = n_hoses = 0
    for a in ships:
        recs = kh.placements(a)
        assert len(recs) == len(a.placed), "placement count mismatch"
        for rec, p in zip(recs, a.placed):
            # quaternion round trip is exact to float noise
            R2 = kh.R_from_quat(rec["orient"])
            assert np.allclose(R2, p.R, atol=1e-9), \
                f"orient drift on {p.uid}"
            part, R, t = kh.rehydrate(rec)   # asserts gen_params checksum
            # meshes: rehydrated local geometry x (R, t) == committed world
            assert len(part.meshes) == len(p.world), p.uid
            for (v, f, c), (wv, wf, wc) in zip(part.meshes, p.world):
                assert np.allclose(xform(v, R, t), wv, atol=1e-6), \
                    f"mesh drift on {p.uid}"
                assert f == wf and c == wc, f"topology drift on {p.uid}"
            # ports: position, axes, and every schema attribute
            assert len(part.ports) == len(p.wports), p.uid
            for pt, (wpos, wN, wup, wp) in zip(part.ports, p.wports):
                assert np.allclose(R @ pt.pos + t, wpos, atol=1e-6), p.uid
                assert np.allclose(R @ pt.N, wN, atol=1e-6), p.uid
                assert np.allclose(R @ pt.up, wup, atol=1e-6), p.uid
                assert (pt.type, pt.size, pt.gender, pt.sym, pt.cluster,
                        pt.tags) == (wp.type, wp.size, wp.gender, wp.sym,
                                     wp.cluster, wp.tags), p.uid
            # grommets ride along too
            assert len(part.grommets) == len(p.wgrom), p.uid
            for g, (wpos, wg) in zip(part.grommets, p.wgrom):
                assert np.allclose(R @ g.pos + t, wpos, atol=1e-6), p.uid
                assert (g.ctype, g.size) == (wg.ctype, wg.size), p.uid
        # struts/collars: one decision record per baked cylinder
        assert len(a.strut_segs) == len(a.struts), \
            f"strut decisions diverge from baked struts: " \
            f"{len(a.strut_segs)} != {len(a.struts)}"
        # hoses: path + conduit identity
        hr = kh.hose_records(a)
        assert len(hr) == len(a.hoses)
        for rec, h in zip(hr, a.hoses):
            assert rec["pts"] == [list(map(float, pt)) for pt in h["pts"]]
            assert rec["ctype"] == h["ctype"] and rec["dia"] == h["dia"]
            assert rec["style"] == a.fc["hose"]
        n_parts += len(recs); n_struts += len(a.strut_segs)
        n_hoses += len(hr)
    # eviction must purge strut decisions exactly like baked struts
    b = rigged_run([gen_blocker, gen_big], {"blocker": 1.0, "big": 5.0},
                   make_hub([P_TOP_S9, P_SIDE_M8]))
    assert len(b.strut_segs) == len(b.struts), \
        "uncommit left ghost strut decisions"
    print(f"PASS  houdini round trip ({n_parts} placements rehydrated "
          f"exactly; {n_struts} strut decisions, {n_hoses} hoses match)")


if __name__ == "__main__":
    test_fleet_regression()
    test_auction_win_and_evict()
    test_backjump()
    test_segregation()
    test_loom()
    test_capacity_ripup()
    test_anchor_semantics()
    test_houdini_roundtrip()
    test_director_noop()
    print("ALL GATES PASS")
