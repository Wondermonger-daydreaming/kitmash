"""verify_usd.py — prove the KitMash -> USD round trip (roadmap item 4).

Runs in EITHER USD runtime:
  .venv/bin/python verify_usd.py             (usd-core 26.5, no Houdini license)
  /opt/hfs21.0.729/bin/hython verify_usd.py  (Houdini's own pxr)

The gate is the contract, exactly as verify_tank_hda.py is the part-HDA
contract. It rebuilds the canonical fleet with the REAL assembler, exports
to an in-memory USD stage via kitmash_usd, reads it back, and diffs the
recovered decision records against the host-agnostic extractors:

  - placements: P + orient (bit-exact, double xform ops), generator,
    gen_params (string AND typed kitmash:gp:* primvars), part_id, family,
    label, faction, parent_id, host/part_port (strings exact), era (int
    exact), mass/silhouette/join_strain (DOUBLE storage -> exact to 1e-9,
    NOT float32-honest: USD lets the decision layer be the truth bit-for-bit)
  - struts/collars: owner/anchor/relief/vol/r/strain + endpoint coords
    (double primvars, exact)
  - hoses: ctype/style/dia/kinds + every polyline vertex (exact)
  - open ports: full port schema (exact)

  - THE COOK TEST: compose each part's authored USD xform (translate+orient)
    against the rehydrated LOCAL mesh and compare to the assembler's WORLD
    geometry (<=1e-4, float32 point storage + matrix math). A provenance
    round trip that never composes the transform could carry a wrong-handed
    orient quaternion while every primvar matches — green over broken, the
    v0.7 "built is not cooks" failure mode. This check forbids it.

Exit 0 = round trip proven in this runtime. Any drift prints and exits 1.
"""
import json
import os
import sys

import numpy as np
from pxr import Usd, UsdGeom, Sdf, Gf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kitmash as km
import kitmash_houdini as kh
import kitmash_usd as ku
from make_fleet_usd import build_fleet

FAIL = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name +
          (f"   {detail}" if detail and not ok else ""))
    if not ok:
        FAIL.append(name)


def _num_eq(a, b, atol):
    return abs(float(a) - float(b)) <= atol


def gp_eq(a, b):
    """gen_params equality: ints exact, floats exact-to-1e-9 (double storage),
    strings exact, type drift -> False."""
    a_num = isinstance(a, (int, float)) and not isinstance(a, bool)
    b_num = isinstance(b, (int, float)) and not isinstance(b, bool)
    if not (a_num and b_num):
        return a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def verify_ship(stage, ship_path, a, name):
    print(f"\n=== {name}  ({ship_path}) ===")
    recs = kh.placements(a)
    got = ku.read_ship(stage, ship_path)
    check(f"[{name}] part count", len(got) == len(recs),
          f"{len(got)} != {len(recs)}")

    # ---- placement decision layer ----
    for r0, r1 in zip(recs, got):
        pid = r0["part_id"]
        for k in ("generator", "gen_params", "part_id", "family", "label",
                  "faction", "parent_id", "host_port", "part_port"):
            check(f"[{name}] {pid}.{k}", r0[k] == r1[k],
                  f"{r1[k]!r} != {r0[k]!r}")
        check(f"[{name}] {pid}.era", int(r0["era"]) == int(r1["era"]))
        for k, atol in (("mass", 1e-9), ("silhouette", 1e-9),
                        ("join_strain", 1e-9)):
            check(f"[{name}] {pid}.{k}",
                  _num_eq(r0[k], r1[k], atol * max(1.0, abs(r0[k]))),
                  f"{r1[k]} != {r0[k]}")
        check(f"[{name}] {pid}.P",
              np.allclose(r0["P"], r1["P"], atol=1e-9))
        check(f"[{name}] {pid}.orient",
              np.allclose(r0["orient"], r1["orient"], atol=1e-9),
              f"{r1['orient']} != {r0['orient']}")
        # typed gp:* primvars reproduce the json recipe exactly
        prim = stage.GetPrimAtPath(
            f"{ship_path}/Parts/part{recs.index(r0)}_{ku._ident(pid)}")
        gp = json.loads(r0["gen_params"])
        typed = {k: ku._get_pv(prim, f"gp:{k}") for k in gp}
        check(f"[{name}] {pid}.gp:* typed",
              set(typed) == set(gp) and all(gp_eq(typed[k], gp[k]) for k in gp),
              f"{typed} != {gp}")

    # ---- THE COOK TEST: compose the xform, compare to world geometry ----
    parts_prim = stage.GetPrimAtPath(f"{ship_path}/Parts")
    kids = sorted(parts_prim.GetChildren(),
                  key=lambda p: int(p.GetName().split("_")[0][4:]))
    worst = 0.0
    for prim, placed in zip(kids, a.placed):
        M = ku.read_local_to_world(prim)
        meshprim = UsdGeom.Mesh(prim.GetChild("geo"))
        local = np.array([[p[0], p[1], p[2]]
                          for p in meshprim.GetPointsAttr().Get()])
        composed = np.array([list(M.Transform(Gf.Vec3d(*map(float, p))))
                             for p in local])
        world = np.vstack([v for v, f, c in placed.world])
        # match point counts/order: bake order in _bake_part_mesh follows
        # placed.meshes; placed.world is the same meshes transformed.
        if composed.shape == world.shape:
            worst = max(worst, float(np.abs(composed - world).max()))
        else:
            check(f"[{name}] {placed.uid} mesh shape",
                  False, f"{composed.shape} vs {world.shape}")
    check(f"[{name}] cook: composed xform == world geometry (<=1e-4)",
          worst <= 1e-4, f"worst point error {worst:.2e}")

    # ---- struts / collars ----
    sr = kh.strut_records(a)
    struts_prim = stage.GetPrimAtPath(f"{ship_path}/Struts")
    by_kind = {"strut": [], "collar": []}
    for p in struts_prim.GetChildren():
        by_kind[ku._get_pv(p, "kind")].append(p)
    exp = {"strut": [s for s in sr if s["kind"] == "strut"],
           "collar": [s for s in sr if s["kind"] == "collar"]}
    for kind in ("strut", "collar"):
        check(f"[{name}] {kind} count",
              len(by_kind[kind]) == len(exp[kind]),
              f"{len(by_kind[kind])} != {len(exp[kind])}")
    for prim, s in zip(by_kind["strut"], exp["strut"]):
        check(f"[{name}] strut {s['owner']}",
              ku._get_pv(prim, "owner") == s["owner"] and
              ku._get_pv(prim, "anchor") == s["anchor"] and
              int(ku._get_pv(prim, "vol")) == int(s.get("vol", -1)) and
              _num_eq(ku._get_pv(prim, "relief"), s["relief"], 1e-9) and
              np.allclose(list(ku._get_pv(prim, "a")), s["a"], atol=1e-9) and
              np.allclose(list(ku._get_pv(prim, "b")), s["b"], atol=1e-9))
    for prim, s in zip(by_kind["collar"], exp["collar"]):
        check(f"[{name}] collar {s['owner']}",
              ku._get_pv(prim, "owner") == s["owner"] and
              _num_eq(ku._get_pv(prim, "r"), s["r"], 1e-9) and
              _num_eq(ku._get_pv(prim, "strain"), s["strain"], 1e-9) and
              np.allclose(list(ku._get_pv(prim, "pos")), s["pos"], atol=1e-9) and
              np.allclose(list(ku._get_pv(prim, "axis")), s["axis"], atol=1e-9))

    # ---- hoses ----
    hr = kh.hose_records(a)
    hoses_prim = stage.GetPrimAtPath(f"{ship_path}/Hoses")
    hkids = sorted(hoses_prim.GetChildren(),
                   key=lambda p: int(p.GetName()[4:]))
    check(f"[{name}] hose count", len(hkids) == len(hr))
    for prim, h in zip(hkids, hr):
        pts = np.array([list(v) for v in ku._get_pv(prim, "pts")])
        check(f"[{name}] hose {h['ctype']}",
              ku._get_pv(prim, "ctype") == h["ctype"] and
              ku._get_pv(prim, "hose_style") == h["style"] and
              _num_eq(ku._get_pv(prim, "dia"), h["dia"], 1e-9) and
              pts.shape == np.array(h["pts"]).shape and
              np.allclose(pts, h["pts"], atol=1e-9))

    # ---- open ports ----
    op = kh.open_ports(a)
    ports_prim = stage.GetPrimAtPath(f"{ship_path}/OpenPorts")
    pkids = sorted(ports_prim.GetChildren(),
                   key=lambda p: int(p.GetName().split("_")[0][4:]))
    check(f"[{name}] open-port count", len(pkids) == len(op))
    for prim, o in zip(pkids, op):
        t = {x.GetOpType(): x for x in
             UsdGeom.Xformable(prim).GetOrderedXformOps()}[
            UsdGeom.XformOp.TypeTranslate].Get()
        check(f"[{name}] port {o['port_id']}",
              ku._get_pv(prim, "port_type") == o["port_type"] and
              int(ku._get_pv(prim, "port_gender")) == o["port_gender"] and
              _num_eq(ku._get_pv(prim, "port_size"), o["port_size"], 1e-9) and
              np.allclose([t[0], t[1], t[2]], o["P"], atol=1e-9) and
              np.allclose(list(ku._get_pv(prim, "N")), o["N"], atol=1e-9))


def main():
    from pxr import Usd as _Usd
    print(f"USD runtime: pxr {_Usd.GetVersion()}  "
          f"({'hython' if 'hou' in sys.modules or os.environ.get('HFS') else 'usd-core'})")
    ships = build_fleet()
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    fleet = UsdGeom.Scope.Define(stage, "/Fleet")
    for name, a, offset, plate in ships:
        token = ku._ident(name.split()[0])
        ku.write_usd(stage, a, Sdf.Path(f"/Fleet/{token}"),
                     name=name, plate=plate, offset=offset)
    # verify every ship in the fleet (not just GS-α): each exercises a
    # different corner — δ auctions, ε the loom/multi-conduit hoses.
    for name, a, offset, plate in ships:
        token = ku._ident(name.split()[0])
        verify_ship(stage, f"/Fleet/{token}", a, name.split()[0])

    print()
    if FAIL:
        print(f"USD ROUND TRIP FAILED: {len(FAIL)} check(s): {FAIL[:12]}"
              + (" ..." if len(FAIL) > 12 else ""))
        sys.exit(1)
    print("USD ROUND TRIP PROVEN: every decision survives the format, "
          "and the composed transform reproduces the assembler geometry.")


if __name__ == "__main__":
    main()
