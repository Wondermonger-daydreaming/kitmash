#!/usr/bin/env hython
"""test_headless.py — Headless kitmash↔Houdini integration test suite.

Run with:
    /opt/hfs21.0/bin/hython houdini/test_headless.py
    # or after sourcing houdini_setup:
    hython houdini/test_headless.py [--seed N] [--verbose]

Gates
─────
  1  hython environment  — hou importable, correct version, no $DISPLAY needed
  2  kitmash imports     — kitmash + kitmash_houdini importable from hython
  3  pure-Python bridge  — placements / strut_records / hose_records /
                           open_ports all return correct shapes without hou
  4  rehydrate round-trip— gen_params checksum holds; R·Rᵀ=I; t reproducible
  5  write_geo           — hou.Geometry populated; point counts match;
                           attribute types correct; groups exist
  6  attribute spot-check— sample placement point carries orient (unit quat),
                           generator name in GEN_REGISTRY, gen_params valid JSON
  7  provenance detail   — kitmash_schema == "kitmash/0.6"; trace round-trips
  8  multi-faction       — guild + feral assemblies both write clean geo

Exit 0 = all gates passed. Exit 1 = at least one gate failed (details printed).

[builder-instance note, 2026-06-12: fixed three pre-run API mismatches —
 reference assemblies now use km.build(km.GUILD, seed, wants) (Assembler
 has no zero-brief constructor and no .build() method; build() is
 module-level), and gate 6's registry check used a TypeError-raising
 `in .__class__` expression. Behavior otherwise untouched.]
"""
import sys, os, json, math, argparse, traceback

# ── allow running from the project root without installing kitmash ─────────────
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

# ─────────────────────────────────────────────────────────────── helpers ──────

PASS = "✓"
FAIL = "✗"
results = []

# canonical GS-α wants — same numbers gate 1 of test_kitmash.py pins
REF_WANTS = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
             "heavy_cannon": 1.4, "antenna": 0.8, "sensor_pod": 0.6}

def gate(name, fn):
    """Run fn(); record pass/fail; print result."""
    try:
        fn()
        results.append((name, True, None))
        print(f"  {PASS}  {name}")
    except Exception as exc:
        tb = traceback.format_exc()
        results.append((name, False, tb))
        print(f"  {FAIL}  {name}")
        print(f"       {exc}")
        if VERBOSE:
            print(tb)

def assert_close(a, b, tol=1e-6, msg=""):
    import numpy as np
    if not np.allclose(a, b, atol=tol):
        raise AssertionError(f"{msg}: {a} != {b}")

# ─────────────────────────────────────────────────────────────── gates ───────

def gate1_hython_env():
    import hou
    ver = hou.applicationVersionString()
    assert ver.startswith("21.0"), f"unexpected version: {ver}"
    # confirm no display is required — headless sessions must not crash here
    assert hou.isUIAvailable() is not None   # attribute exists; value may be False

def gate2_imports():
    import kitmash as km          # noqa: F401
    import kitmash_houdini as kh  # noqa: F401
    assert hasattr(kh, "placements")
    assert hasattr(kh, "write_geo")

def gate3_pure_python(a):
    import kitmash_houdini as kh
    recs   = kh.placements(a)
    struts = kh.strut_records(a)
    hoses  = kh.hose_records(a)
    ports  = kh.open_ports(a)

    assert isinstance(recs, list) and len(recs) > 0, "no placement records"
    for rec in recs:
        assert "P" in rec and len(rec["P"]) == 3
        assert "orient" in rec and len(rec["orient"]) == 4
        assert "generator" in rec
        assert "gen_params" in rec
        json.loads(rec["gen_params"])   # must be valid JSON

    assert isinstance(struts, list)
    assert isinstance(hoses,  list)
    assert isinstance(ports,  list)

def gate4_rehydrate(a):
    import numpy as np
    import kitmash_houdini as kh
    recs = kh.placements(a)
    # test the first 3 placements (or fewer)
    for rec in recs[:3]:
        part, R, t = kh.rehydrate(rec)
        # R must be a proper rotation: R·Rᵀ ≈ I, det ≈ +1
        assert_close(R @ R.T, np.eye(3), tol=1e-5, msg="R·Rᵀ≠I")
        assert abs(np.linalg.det(R) - 1.0) < 1e-5, "det(R)≠1"
        # t must match recorded P
        assert_close(t, np.array(rec["P"]), tol=1e-6, msg="t≠P")
        # gen_params checksum: rehydrate asserts internally; if we got here, OK

def gate5_write_geo(a):
    import hou
    import kitmash_houdini as kh
    recs   = kh.placements(a)
    struts = [s for s in kh.strut_records(a) if s["kind"] == "strut"]
    hoses  = kh.hose_records(a)
    ports  = kh.open_ports(a)

    geo = hou.Geometry()
    kh.write_geo(geo, a, name="test_ship", plate="TS-001")

    # groups must exist
    group_names = [g.name() for g in geo.pointGroups()]
    for g in ("placements", "open_ports", "collars"):
        assert g in group_names, f"missing point group '{g}'"
    prim_group_names = [g.name() for g in geo.primGroups()]
    for g in ("struts", "hoses"):
        assert g in prim_group_names, f"missing prim group '{g}'"

    # placement point count must match
    n_place = len(geo.pointGroup("placements").points())
    assert n_place == len(recs), f"placement point count {n_place} != {len(recs)}"

    # strut prim count
    n_strut_prims = len(geo.primGroup("struts").prims())
    assert n_strut_prims == len(struts), \
        f"strut prim count {n_strut_prims} != {len(struts)}"

def gate6_attribute_spotcheck(a):
    import hou, numpy as np
    import kitmash_houdini as kh
    recs = kh.placements(a)

    geo = hou.Geometry()
    kh.write_geo(geo, a)

    pts = geo.pointGroup("placements").points()
    for pt, rec in zip(pts, recs):
        # orient must be a unit quaternion (x,y,z,w)
        q = pt.attribValue("orient")
        mag = math.sqrt(sum(v * v for v in q))
        assert abs(mag - 1.0) < 1e-5, f"orient not unit: {q}"

        # generator name must be in registry
        gen = pt.attribValue("generator")
        assert any(gen == v[0] for v in kh.GEN_REGISTRY.values()), \
               f"unknown generator: {gen}"

        # gen_params must round-trip through JSON
        gp_str = pt.attribValue("gen_params")
        gp = json.loads(gp_str)
        assert isinstance(gp, dict)

        # P stored correctly
        p = pt.position()
        for i, v in enumerate(rec["P"]):
            assert abs(p[i] - v) < 1e-5, f"P[{i}] mismatch: {p[i]} != {v}"

def gate7_provenance(a):
    import hou
    import kitmash_houdini as kh
    geo = hou.Geometry()
    kh.write_geo(geo, a, name="provenance_test")

    schema = geo.attribValue("kitmash_schema")
    assert schema == "kitmash/0.6", f"schema: {schema}"

    name_val = geo.attribValue("ship_name")
    assert name_val == "provenance_test"

    trace_str = geo.attribValue("trace")
    trace = json.loads(trace_str)
    assert isinstance(trace, list) and len(trace) > 0

def gate8_multi_faction():
    import kitmash as km
    import kitmash_houdini as kh
    import hou
    for fc in (km.GUILD, km.FERAL):
        a = km.build(fc, SEED, REF_WANTS)
        recs = kh.placements(a)
        assert len(recs) > 0, f"no placements for faction {fc['name']}"
        geo = hou.Geometry()
        kh.write_geo(geo, a, name=f"test_{fc['name']}")
        pts = geo.pointGroup("placements").points()
        assert len(pts) == len(recs)


# ──────────────────────────────────────────────────────────────── main ────────

def main():
    import kitmash as km

    print(f"\nkitmash headless test suite  (seed={SEED})")
    print("──────────────────────────────────────────")

    gate("1 hython environment",  gate1_hython_env)
    gate("2 kitmash imports",     gate2_imports)

    # build a reference assembly once (gates 3–7 share it)
    a = km.build(km.GUILD, SEED, REF_WANTS)
    n_parts = len(a.placed)
    print(f"     reference assembly: {n_parts} parts, "
          f"{len(a.struts)} struts, {len(a.hoses)} hoses")

    gate("3 pure-Python bridge",   lambda: gate3_pure_python(a))
    gate("4 rehydrate round-trip", lambda: gate4_rehydrate(a))
    gate("5 write_geo",            lambda: gate5_write_geo(a))
    gate("6 attribute spot-check", lambda: gate6_attribute_spotcheck(a))
    gate("7 provenance detail",    lambda: gate7_provenance(a))
    gate("8 multi-faction",        gate8_multi_faction)

    print("──────────────────────────────────────────")
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print(f"  {passed}/{total} gates passed")

    if passed < total:
        print("\nFailed gates:")
        for name, ok, tb in results:
            if not ok:
                print(f"  {FAIL} {name}")
                if tb:
                    print(tb)
        sys.exit(1)
    else:
        print("  All gates passed — hython integration confirmed.\n")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="kitmash headless Houdini tests")
    parser.add_argument("--seed",    type=int, default=42)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    SEED    = args.seed
    VERBOSE = args.verbose
    main()
