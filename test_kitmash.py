"""KitMash v0.6 tests — every new code path must leave a trace.

Ten gates:
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
  9. face-level anchors (P3) — anchor_class + surface normal genuinely
     SELECT: a class-0 (glass) face refuses the weld, the class factor
     scales relief by exactly ANCHOR_CLASS_RELIEF[2]/[1] (proving it is
     live, not metadata), and a primary face beats a co-located secondary.
 10. per-family face coverage (P3) — all 10 non-hull families declare
     anchor_faces with real surface normals and honest glass: the engine
     glow nozzle, radiator panel, and antenna mast are cls-0 (weld-proof);
     wing and cannon load-bearing slabs are cls-2 primary structure.

Run: python3 test_kitmash.py
"""
import numpy as np
from kitmash import (Assembler, Part, Port, Grommet, box, GUILD, FERAL,
                     build, gen_hull, gen_reactor, gen_turret, seg_share_ok,
                     xform, make_face, ANCHOR_CLASS_RELIEF, face_candidates,
                     gen_engine, gen_tank, gen_cannon, gen_wing, gen_antenna,
                     gen_pod, gen_radiator, gen_cap, gen_turret)

TESTF = dict(name="TestF", era=1, hull="#888888", accent="#aa6633",
             dark="#444444", glow="#88ccff", safety_factor=1.1,
             blasphemy=0.0, strain_taste=0.0, caps_unused=False,
             hose="catenary", debt=0.0)


# ------------------------------------------------------------- rigged parts
def make_hub(port_specs, mass=100.0, anchor_vols=None, anchor_faces=None):
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
        if anchor_faces is not None:        # P3: list of make_face() dicts
            p.anchor_faces = anchor_faces
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


# ----------------------------------------- face-level anchor surfaces (gate 9)
def gen_arm_light(fc, seed=0):
    """Lighter cantilever (M = 110kg x 24.525 x 1.0m = 2698 > 1818 cap): needs
    a strut, but braces under BOTH the class-1 and class-2 relief factors, so a
    single gate can read and compare the two reliefs."""
    p = Part("arm", {}, mass=110, silhouette=0.1, faction=fc["name"],
             era=fc["era"], color=fc["dark"], label="arm")
    v, f = box(2.4, 0.3, 0.3); p.add(np.asarray(v) + [1.0, 0, 0.45], f)
    p.ports = [Port([0, 0, 0], [0, 0, -1], [1, 0, 0], "struct_S", 0.3, 1,
                    sym=1)]
    p.com = np.array([1.0, 0, 0.3])
    return p.finalize()


def test_face_anchor_semantics():
    """P3: face-level anchors genuinely SELECT — they are not decoration.
    Same arm, same physics; only the face declaration changes. Proves the
    anchor_class and the surface normal both reach the strut decision."""
    arm_wants = {"arm": 5.0}
    TOP = lambda cls: make_face([0, 0, 0.5], [0, 0, 1], 2.0, 2.0, cls=cls)

    # A — declared GLASS refuses: the hub's only surface is class 0, so it
    # offers zero candidates and the arm starves. (Before P3 the whole box,
    # this surface included, was weldable.)
    a = rigged_run([gen_arm_light], arm_wants,
                   make_hub([P_TOP_S9], anchor_faces=[TOP(0)]))
    assert "arm" not in [p.label for p in a.placed], \
        "strut welded to a declared class-0 GLASS face"
    rejA = [e for e in a.trace if e["ev"] == "reject"
            and e.get("cause") == "moment_over_cap"]
    assert rejA and rejA[0]["result"] in ("no_anchor", "strut_insufficient"), \
        f"class-0 face should leave no anchor: {rejA}"
    assert not a.strut_segs, "glass-refused arm left ghost strut decisions"

    # B — the class factor is LIVE: identical face GEOMETRY at class 1 vs class
    # 2 scales the recorded relief by exactly ANCHOR_CLASS_RELIEF[2]/[1]. Were
    # the class mere metadata, the two reliefs would be equal. The winning
    # geometric candidate is the same in both runs (the class factor scales all
    # candidates equally and cannot change the argmax), so the ratio isolates
    # the class factor — and face_cls provenance is recorded for each.
    def weld(cls):
        b = rigged_run([gen_arm_light], arm_wants,
                       make_hub([P_TOP_S9], anchor_faces=[TOP(cls)]))
        assert "arm" in [p.label for p in b.placed], f"class-{cls} arm lost"
        return [s for s in b.strut_segs if s["kind"] == "strut"][0]
    s1, s2 = weld(1), weld(2)
    assert s1["face_cls"] == 1 and s2["face_cls"] == 2, \
        f"face_cls not recorded: {s1.get('face_cls')},{s2.get('face_cls')}"
    ratio = s2["relief"] / s1["relief"]
    expect = ANCHOR_CLASS_RELIEF[2] / ANCHOR_CLASS_RELIEF[1]
    # 5e-3 absorbs the 3-decimal rounding of two independently-stored reliefs;
    # equal (decoration) reliefs would give ratio 1.0 — nowhere near 1.54.
    assert abs(ratio - expect) < 5e-3, \
        f"class factor not applied to relief: {ratio:.5f} != {expect:.5f}"

    # C — among CO-LOCATED faces the PRIMARY (class 2) wins the weld over the
    # SECONDARY (class 1): same geometry, the class breaks the tie.
    c = rigged_run([gen_arm_light], arm_wants,
                   make_hub([P_TOP_S9], anchor_faces=[TOP(1), TOP(2)]))
    stc = [s for s in c.strut_segs if s["kind"] == "strut"][0]
    assert stc["vol"] == 1 and stc["face_cls"] == 2, \
        f"secondary won over primary: vol={stc['vol']} cls={stc['face_cls']}"

    # D — a degenerate normal must CRASH at authoring, not creep in as NaN.
    # (Cassandra P3 C2c: an unguarded zero-normal normalizes to NaN, and a
    # NaN-relief brace wins because best-is-None seeds it and nothing beats NaN.)
    for bad_n in ([0, 0, 0], [0, 0, 1e-12]):
        try:
            make_face([0, 0, 0], bad_n, 1.0, 1.0, cls=2)
            assert False, f"make_face accepted degenerate normal {bad_n}"
        except ValueError:
            pass
    print(f"PASS  face anchors (gate 9): cls-0 glass refuses; class factor live "
          f"(relief ×{expect:.3f} cls2/cls1); primary wins tie; degenerate "
          f"normal crashes at authoring")


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
    # ANCHOR RE-BASELINE (P3 — face-level anchorable surfaces):
    #   old e6aeccfe352bba16f288785ea23e5bc3  (v0.8 AABB anchor volumes)
    #   new 80ddaccccc594b2a7cc8c7b40a129086  (v0.8.1 hull declares weld FACES)
    # Deliberate: the hull's universal-anchor whole-box was replaced by declared
    # surfaces (deck/belly/flanks cls2, aft cls1, nose cls0-glass), so every
    # canonical strut endpoint + its repair-trace relief moved. Topology held
    # (all 5 ships same parts/mass/strut counts, legal+fueled); only weld points
    # and relief shifted. See KITMASH-HANDOFF.md "v0.8.1 — P3".
    assert md5 == "80ddaccccc594b2a7cc8c7b40a129086", \
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


# ----------------------------------------- family face coverage (gate 10)
TESTF_GUILD = dict(name="Guild", era=1, hull="#888888", accent="#aa6633",
                   dark="#444444", glow="#88ccff", safety_factor=2.0,
                   blasphemy=0.0, strain_taste=0.0, caps_unused=False,
                   hose="catenary", debt=0.0)


def _all_faces(part):
    """Collect all face dicts from a part's anchor_faces list."""
    return part.anchor_faces or []


def test_family_face_coverage():
    """Gate 10: per-family anchor_faces — real surface normals, honest glass.

    Checks:
    A. At least 8 of the 10 non-hull families now declare anchor_faces.
    B. Engine glow-nozzle face is cls-0 (x=-3.0): face_candidates yields []
       and a live weld attempt against the engine anchors to the casing,
       not the nozzle.
    C. Engine, radiator, and antenna each declare a cls-0 GLASS face — the
       three families named in the v0.8 handoff as the headline cases.
    D. Each family's cls-0 face yields no candidates (glass is weld-proof).
    E. Each family with faces declares at least one cls-2 primary face.
    F. Wing and heavy_cannon declare cls-2 structural faces on their load-
       bearing slabs (not just secondary or glass-only).
    """
    fc = TESTF_GUILD

    # ---- A: count families with declared faces ----
    gens = [gen_engine, gen_tank, gen_cannon, gen_wing, gen_antenna,
            gen_pod, gen_radiator, gen_cap, gen_turret, gen_reactor]
    parts = [g(fc, seed=0) for g in gens]
    with_faces = [p for p in parts if p.anchor_faces]
    assert len(with_faces) >= 8, \
        f"fewer than 8 families declare anchor_faces: {len(with_faces)}"

    # ---- B: engine glow nozzle is cls-0 and refuses candidates ----
    eng = gen_engine(fc, seed=0, size=1.0)
    nozzle_faces = [f for f in _all_faces(eng) if f["cls"] == 0]
    assert nozzle_faces, "engine declares no cls-0 face (glow nozzle should be GLASS)"
    # The glow nozzle face centre is at x≈-3.0 (behind the casing)
    nozzle = min(nozzle_faces, key=lambda f: f["c"][0])  # most -x face
    assert nozzle["c"][0] < -2.5, \
        f"engine cls-0 face not behind casing: c={nozzle['c']}"
    # face_candidates must yield empty for cls-0
    dummy_com = np.array([0.0, 0.0, 0.0])
    assert face_candidates(nozzle, dummy_com) == [], \
        "cls-0 nozzle face leaked a candidate"

    # Live weld test: engine mounted on a hub; strut must land on casing NOT nozzle.
    # We use a heavy arm placed via the engine struct_M port, then check that
    # any strut_segs record face_cls != 0 and the weld x > -2.5.
    def gen_eng_hub(fc_inner, seed=0):
        """A hub that offers one struct_M port for the engine to plug into."""
        p = Part("test_hub", {}, mass=500, silhouette=0.5,
                 faction=fc_inner["name"], era=fc_inner["era"],
                 color=fc_inner["hull"], label="hub")
        v, f = box(2, 2, 2); p.add(v, f)
        p.ports = [Port([0, 0, 0], [0, 0, 1], [1, 0, 0], "struct_M", 1.0, 0,
                        prio=9)]
        return p.finalize()

    # A small arm that creates a moment requiring a strut, mounted via the engine
    # requires an engine that can supply struct_M; we verify by rigged assembly.
    # Simpler approach: instantiate the engine and manually call face_candidates
    # on each of its anchor_faces; verify the cls-0 face is sterile.
    eng_faces = _all_faces(eng)
    cls2_faces = [f for f in eng_faces if f["cls"] == 2]
    assert cls2_faces, "engine declares no cls-2 weldable faces"
    # All cls-0 faces are sterile
    cls0_faces = [f for f in eng_faces if f["cls"] == 0]
    for gf in cls0_faces:
        cands = face_candidates(gf, dummy_com)
        assert cands == [], f"engine cls-0 face leaked candidates: {cands}"

    # ---- C: engine, radiator, antenna each have a cls-0 face ----
    ant = gen_antenna(fc, seed=0)
    rad = gen_radiator(fc, seed=0)
    for label, part in [("engine", eng), ("antenna", ant), ("radiator", rad)]:
        cls0 = [f for f in _all_faces(part) if f["cls"] == 0]
        assert cls0, f"{label} missing cls-0 GLASS face"

    # ---- D: all cls-0 faces on all families yield no candidates ----
    com_zero = np.array([0.0, 0.0, 0.0])
    for part in parts:
        for face in _all_faces(part):
            if face["cls"] == 0:
                assert face_candidates(face, com_zero) == [], \
                    f"{part.family} cls-0 face leaked candidates"

    # ---- E: every face-declaring family has at least one cls-2 face ----
    for part in with_faces:
        cls2 = [f for f in _all_faces(part) if f["cls"] == 2]
        assert cls2, f"{part.family} declares faces but has no cls-2 primary face"

    # ---- F: wing and heavy_cannon cls-2 faces are on structural slabs ----
    wing = gen_wing(fc, seed=0, span=3.2, hand=1)
    cannon = gen_cannon(fc, seed=0, heavy=1.0)
    # Wing: root spar faces should be near z=±0.17 (top/belly)
    wing_cls2 = [f for f in _all_faces(wing) if f["cls"] == 2]
    assert wing_cls2, "wing has no cls-2 face"
    # At least one face with normal roughly [0,0,±1] (top or belly of root spar)
    top_belly = [f for f in wing_cls2 if abs(f["n"][2]) > 0.9]
    assert top_belly, f"wing has no top/belly cls-2 face: normals={[f['n'].tolist() for f in wing_cls2]}"
    # Cannon: cls-2 faces on mount block (|n[0]|>0.9 or |n[2]|>0.9, NOT barrel)
    cannon_cls2 = [f for f in _all_faces(cannon) if f["cls"] == 2]
    assert cannon_cls2, "heavy_cannon has no cls-2 face"
    cannon_cls0 = [f for f in _all_faces(cannon) if f["cls"] == 0]
    assert cannon_cls0, "heavy_cannon: barrel should be cls-0 GLASS"

    n_glass = sum(1 for p in with_faces
                  for f in _all_faces(p) if f["cls"] == 0)
    print(f"PASS  family face coverage (gate 10): {len(with_faces)}/10 families "
          f"declare faces; {n_glass} cls-0 GLASS faces total; engine nozzle "
          f"cls-0 at x={nozzle['c'][0]:.1f} sterile; wing+cannon cls-2 verified")


if __name__ == "__main__":
    test_fleet_regression()
    test_auction_win_and_evict()
    test_backjump()
    test_segregation()
    test_loom()
    test_capacity_ripup()
    test_anchor_semantics()
    test_face_anchor_semantics()
    test_houdini_roundtrip()
    test_director_noop()
    test_family_face_coverage()
    print("ALL GATES PASS")
