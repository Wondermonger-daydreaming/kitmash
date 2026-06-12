"""verify_tank_hda.py — prove the kitmash::part_tank round trip in Houdini.

Run:  source /opt/hfs21.0/houdini_setup
      hython houdini/verify_tank_hda.py

Builds GS-α with the real assembler, takes the fuel tank's PLACEMENT
RECORD (the decision the Python SOP would emit), instantiates the HDA
with gp_h / gp_seed exactly as the For-Each rehydrator would, and diffs
the HDA's output against the Python part:

  - port: position, v@N, v@up, type, size, gender, prio, sym (exact)
  - grommets: positions, conduit_type, conduit_size, gedge prim (exact)
  - detail: family, generator, gen_params JSON, mass, silhouette,
    supplies (exact; gen_params is the determinism checksum)
  - body: bounding box vs the kitmash cartoon (±1e-4 — placeholder
    parity; artists may later change the body, ports may NEVER move)

Exit 0 = round trip proven. Any drift prints and exits 1.
"""
import json, os, sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import numpy as np
import kitmash as km
import kitmash_houdini as kh

FAIL = []
def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name +
          (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAIL.append(name)

# --- 1. real assembly, real decision record ---------------------------------
a = km.build(km.GUILD, 7, {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
                           "heavy_cannon": 1.4, "antenna": 0.8,
                           "sensor_pod": 0.6}, heavy=1.0, span=3.0)
rec = next(r for r in kh.placements(a) if r["family"] == "fuel_tank")
gp = json.loads(rec["gen_params"])
pypart, _, _ = kh.rehydrate(rec)          # numpy ground truth (gate-7 path)
print(f"placement record: {rec['part_id']}  gen_params={gp}")

# --- 2. instantiate the HDA as the rehydrator would -------------------------
hou.hda.installFile(os.path.join(HERE, "kitmash_part_tank.hda"))
geo_node = hou.node("/obj").createNode("geo", "verify_tank")
hda = geo_node.createNode("kitmash::part_tank::1.0", "tank")
hda.setParms({"h": gp["h"], "seed": gp["seed"]})
g = hda.geometry()

# --- 3. port ------------------------------------------------------------------
ports = list(g.pointGroups()[
    [pg.name() for pg in g.pointGroups()].index("ports")].points()) \
    if any(pg.name() == "ports" for pg in g.pointGroups()) else []
check("port count == 1", len(ports) == 1, f"got {len(ports)}")
if ports:
    hp, pp = ports[0], pypart.ports[0]
    check("port @P", np.allclose(hp.position(), pp.pos, atol=1e-6))
    check("port v@N", np.allclose(hp.attribValue("N"), pp.N, atol=1e-6))
    check("port v@up", np.allclose(hp.attribValue("up"), pp.up, atol=1e-6))
    check("port schema", (hp.attribValue("port_type"),
                          round(hp.attribValue("port_size"), 6),
                          hp.attribValue("port_gender"),
                          hp.attribValue("port_prio"),
                          hp.attribValue("port_sym")) ==
          (pp.type, pp.size, pp.gender, pp.prio, pp.sym))

# --- 4. grommets + gedge -------------------------------------------------------
gr = [pt for pt in g.points()
      if any(grp.name() == "grommets" for grp in pt.groups())]
check("grommet count == 2", len(gr) == len(pypart.grommets))
for hg, pg_ in zip(gr, pypart.grommets):
    check(f"grommet @P {pg_.pos.tolist()}",
          np.allclose(hg.position(), pg_.pos, atol=1e-6))
    check("grommet conduit",
          (hg.attribValue("conduit_type"),
           round(hg.attribValue("conduit_size"), 6)) ==
          (pg_.ctype, pg_.size))
gedges = [pr for pr in g.prims() if pr.type() == hou.primType.Polygon
          and not pr.isClosed()]
check("gedge prim count == 1", len(gedges) == len(pypart.gedges))

# --- 5. detail schema ------------------------------------------------------------
check("family", g.attribValue("family") == "fuel_tank")
check("generator", g.attribValue("generator") == "gen_tank")
check("gen_params checksum",
      json.loads(g.attribValue("gen_params")) == gp,
      g.attribValue("gen_params"))
check("mass", abs(g.attribValue("mass") - pypart.mass) < 1e-4)
check("silhouette", abs(g.attribValue("silhouette") - 0.45) < 1e-9)
check("supplies", json.loads(g.attribValue("supplies")) ==
      [list(x) for x in pypart.supplies])

# --- 6. body bbox vs the cartoon ---------------------------------------------------
pyv = np.vstack([v for v, f, c in pypart.meshes])
body_prims = [pr for pr in g.prims()
              if any(grp.name() == "body" for grp in pr.groups())]
check("body group non-empty", len(body_prims) > 0)
if body_prims:
    pos = np.array([list(v.point().position())
                    for pr in body_prims for v in pr.vertices()])
    check("body bbox", np.allclose(pos.min(0), pyv.min(0), atol=1e-4)
          and np.allclose(pos.max(0), pyv.max(0), atol=1e-4),
          f"hda {pos.min(0)}..{pos.max(0)} vs py {pyv.min(0)}..{pyv.max(0)}")

print()
if FAIL:
    print(f"ROUND TRIP FAILED: {len(FAIL)} check(s): {FAIL}")
    sys.exit(1)
print("ROUND TRIP PROVEN: HDA output is identical to the assembler's part.")
