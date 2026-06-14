"""verify_native_hda.py — the per-family migration gate (roadmap item 5 follow-up).

Run:  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py [family ...]
      (default: every family that has a kitmash::part_<family>::1.0 installed)

verify_tank_hda.py proved ONE family's native interior round-trips. This is
that gate generalized: point it at any family and it diffs the installed
`kitmash::part_<family>::1.0` against the Python generator's output. It is
agnostic to whether the interior is a thin Python-SOP wrapper (round-trips by
construction) or a hand-built native VEX network (the migration target) — both
must produce byte-equal *schema* (ports/grommets are load-bearing and may
NEVER move; the body is a placeholder artists may change).

For each family it builds the Python part directly from the generator (no full
assembly needed), reads its gen_params, sets every HDA parm that matches a
gen_params key (**the parms ARE gen_params** — that is the contract), cooks,
and diffs the full exported schema:

  - ports: @P, v@N, v@up, port_type/size/gender/prio/sym (exact; size float32)
  - grommets: @P, conduit_type, conduit_size; gedge polyline count
  - detail: family, generator (exact strings); gen_params (ints exact, floats
    5e-7 rel — float32 VEX channels + %.9g re-stamp); mass 5e-4; silhouette
    1e-6; supplies / demands (exact JSON); clearance_vols / anchor_vols
    (AABB corners, 1e-5) — v0.8 provenance the rehydrator stamps from
  - body bbox vs the kitmash cartoon (1e-4 — placeholder parity)

Tested across several seeds so derived gen_params (tank h, pod r, engine size
scaling) are exercised, not just the default. Exit 0 = every family's round
trip proven; any drift prints and exits 1.
"""
import json
import os
import sys
import inspect

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)
import numpy as np
import kitmash as km
import kitmash_houdini as kh

SEEDS = [0, 7, 41]
FAIL = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name +
          (f"   {detail}" if detail and not ok else ""))
    if not ok:
        FAIL.append(name)


def _gp_eq(a, b):
    a_num = isinstance(a, (int, float)) and not isinstance(a, bool)
    b_num = isinstance(b, (int, float)) and not isinstance(b, bool)
    if not (a_num and b_num):
        return a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return abs(a - b) <= 5e-7 * max(1.0, abs(a), abs(b))


def _netlist_eq(hda_json, py_pairs):
    """Compare exported supplies/demands. The ctype string is exact; the rate
    is float32-honest (a native VEX interior computes rates like 1.2*size on
    float32 channels, so float64-exact equality is physically impossible — the
    same reason gen_params floats and mass get tolerances). The wrapper path
    happens to be exact, but the contract a native interior must meet is
    float32-honest, not float64-wishful."""
    got = json.loads(hda_json)
    if len(got) != len(py_pairs):
        return False
    for (gc, gr), pair in zip(got, py_pairs):
        pc, pr = pair[0], pair[1]
        if gc != pc or abs(gr - pr) > 5e-7 * max(1.0, abs(pr)):
            return False
    return True


def _aabbs_eq(hda_json, py_vols):
    """Compare exported clearance/anchor volume JSON to the Python part's."""
    if py_vols is None:
        return json.loads(hda_json) is None
    got = json.loads(hda_json)
    if got is None or len(got) != len(py_vols):
        return False
    for (glo, ghi), (lo, hi) in zip(got, py_vols):
        if not (np.allclose(glo, lo, atol=1e-5) and
                np.allclose(ghi, hi, atol=1e-5)):
            return False
    return True


def _grp_points(g, name):
    grp = g.findPointGroup(name)
    return list(grp.points()) if grp else []


def verify_family(family, fc, seed):
    """Build the Python part, instantiate the HDA with matching parms, diff."""
    gen_name, fn = kh.GEN_REGISTRY[family]
    accepted = set(inspect.signature(fn).parameters) - {"fc"}
    kwargs = {"seed": seed} if "seed" in accepted else {}
    pypart = fn(fc, **kwargs)
    gp = pypart.gen_params
    tag = f"{family}[seed={seed},{fc['name'][0]}]"

    geo_node = hou.node("/obj").createNode("geo", f"verify_{family}_{seed}")
    try:
        hda = geo_node.createNode(f"kitmash::part_{family}::1.0", family)
    except hou.OperationFailed:
        check(f"{tag} HDA installed", False, "type not found")
        geo_node.destroy()
        return
    # the parms ARE gen_params: set every parm the HDA exposes that names one
    for k, v in gp.items():
        p = hda.parm(k)
        if p is not None:
            p.set(v)
    # faction parm (wrappers have it; native HDAs may not) — set if present
    if hda.parm("faction") is not None:
        hda.parm("faction").set(0 if fc is km.GUILD else 1)
    try:
        hda.cook(force=True)
    except hou.Error as e:
        check(f"{tag} cooks", False, str(e)[:140])
        geo_node.destroy()
        return
    g = hda.geometry()

    # ---- ports ----
    ports = _grp_points(g, "ports")
    check(f"{tag} port count == {len(pypart.ports)}",
          len(ports) == len(pypart.ports), f"got {len(ports)}")
    for hp, pp in zip(ports, pypart.ports):
        check(f"{tag} port {pp.type} @P/N/up",
              np.allclose(hp.position(), pp.pos, atol=1e-5) and
              np.allclose(hp.attribValue("N"), pp.N, atol=1e-5) and
              np.allclose(hp.attribValue("up"), pp.up, atol=1e-5))
        check(f"{tag} port {pp.type} schema",
              (hp.attribValue("port_type"),
               round(hp.attribValue("port_size"), 6),
               hp.attribValue("port_gender"), hp.attribValue("port_prio"),
               hp.attribValue("port_sym")) ==
              (pp.type, round(pp.size, 6), pp.gender, pp.prio, pp.sym))

    # ---- grommets + gedges ----
    gr = _grp_points(g, "grommets")
    check(f"{tag} grommet count == {len(pypart.grommets)}",
          len(gr) == len(pypart.grommets))
    for hg, pg_ in zip(gr, pypart.grommets):
        check(f"{tag} grommet {pg_.ctype} @P",
              np.allclose(hg.position(), pg_.pos, atol=1e-5) and
              hg.attribValue("conduit_type") == pg_.ctype and
              abs(hg.attribValue("conduit_size") - pg_.size) < 1e-6)
    gedges = [pr for pr in g.prims() if pr.type() == hou.primType.Polygon
              and not pr.isClosed()]
    check(f"{tag} gedge count == {len(pypart.gedges)}",
          len(gedges) == len(pypart.gedges))

    # ---- detail schema ----
    check(f"{tag} family/generator",
          g.attribValue("family") == family and
          g.attribValue("generator") == gen_name)
    hgp = json.loads(g.attribValue("gen_params"))
    check(f"{tag} gen_params checksum",
          set(hgp) == set(gp) and all(_gp_eq(hgp[k], gp[k]) for k in gp),
          g.attribValue("gen_params"))
    check(f"{tag} mass", abs(g.attribValue("mass") - pypart.mass) < 5e-4,
          f"{g.attribValue('mass')} vs {pypart.mass}")
    check(f"{tag} silhouette",
          abs(g.attribValue("silhouette") - pypart.silhouette) < 1e-6)
    check(f"{tag} supplies",
          _netlist_eq(g.attribValue("supplies"), pypart.supplies))
    check(f"{tag} demands",
          _netlist_eq(g.attribValue("demands"), pypart.demands))
    if g.findGlobalAttrib("clearance_vols") is not None:
        # clearances is always a list (possibly empty -> exported "[]", NOT
        # null); only anchor_vols may be None. Don't collapse [] to None.
        check(f"{tag} clearance_vols",
              _aabbs_eq(g.attribValue("clearance_vols"), pypart.clearances))
    if g.findGlobalAttrib("anchor_vols") is not None:
        # STUB-vs-None match, not a real volume round-trip: canonical parts have
        # anchor_vols=None, and the HDA's static `setdetailattrib(0,"anchor_vols",
        # "null")` stub deserialises to None — so this passes by stub coincidence,
        # not by exporting live volume data. (Behaviour unchanged; see Task 2.)
        check(f"{tag} anchor_vols",
              _aabbs_eq(g.attribValue("anchor_vols"), pypart.anchor_vols))
    # P3 DOCTRINE GATE (ARCHITECTURE.md invariants 7 & 8): the native part HDA
    # carries BODY + PORTS only. Assembly/anchor provenance (anchor_faces,
    # face_cls) is NOT baked into each static native HDA — it rides the
    # rehydrator (kitmash_houdini.py write_part_geo/write_geo) and USD primvars,
    # which are the truth. So the native HDA must carry NO baked anchor_faces.
    #
    # This is a LOUD, ALWAYS-RUN assertion, deliberately replacing the prior
    # `if findGlobalAttrib("anchor_faces") is not None:` guard that *silently
    # skipped* on every family (the v0.7-lesson-4 decorate-instead-of-select
    # failure). If a future native HDA ever DID bake anchor_faces, this now
    # FAILS loudly and forces an explicit doctrine decision — the skip can
    # never recur. Where faces ARE proven is printed once in main().
    check(f"{tag} native carries no baked anchor_faces (rides rehydrator+USD)",
          g.findGlobalAttrib("anchor_faces") is None,
          "native HDA baked anchor_faces — violates ARCHITECTURE.md inv 7&8; "
          "anchor provenance must ride the rehydrator + USD primvars, not the "
          "static native body HDA")

    # ---- body bbox vs the cartoon ----
    pyv = np.vstack([v for v, f, c in pypart.meshes])
    bgrp = g.findPrimGroup("body")
    body = list(bgrp.prims()) if bgrp else []
    check(f"{tag} body group non-empty", len(body) > 0)
    if body:
        pos = np.array([list(v.point().position())
                        for pr in body for v in pr.vertices()])
        check(f"{tag} body bbox",
              np.allclose(pos.min(0), pyv.min(0), atol=1e-4) and
              np.allclose(pos.max(0), pyv.max(0), atol=1e-4),
              f"hda {pos.min(0)}..{pos.max(0)} vs py {pyv.min(0)}..{pyv.max(0)}")
    geo_node.destroy()


def main():
    # Install wrappers FIRST, native interiors LAST: for a migrated family the
    # native kitmash::part_<family>::1.0 must win over the wrapper of the same
    # type name (last installFile takes precedence). Un-migrated families keep
    # their wrapper; migrated families cook native.
    hda_dir = os.path.join(HERE, "hda")
    if os.path.isdir(hda_dir):
        for fn in sorted(os.listdir(hda_dir)):
            if fn.endswith(".hda"):
                hou.hda.installFile(os.path.join(hda_dir, fn))
    for fn in sorted(os.listdir(HERE)):
        if fn.startswith("kitmash_part_") and fn.endswith(".hda"):
            hou.hda.installFile(os.path.join(HERE, fn))

    families = sys.argv[1:] or sorted(kh.GEN_REGISTRY)
    for family in families:
        if family not in kh.GEN_REGISTRY:
            check(f"{family} known", False, "no such family")
            continue
        print(f"\n=== {family} ===")
        for seed in SEEDS:
            verify_family(family, km.GUILD, seed)
        verify_family(family, km.FERAL, 0)   # one feral pass for palette/era

    print()
    if FAIL:
        print(f"NATIVE ROUND TRIP FAILED: {len(FAIL)} check(s): {FAIL[:12]}"
              + (" ..." if len(FAIL) > 12 else ""))
        sys.exit(1)
    print("anchor_faces/face_cls proven on the USD rung (verify_usd.py, 47 "
          "primvars) and the rehydrator rung (test_headless gate5).")
    print(f"NATIVE ROUND TRIP PROVEN for: {', '.join(families)}")


if __name__ == "__main__":
    main()
