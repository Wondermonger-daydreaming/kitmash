"""make_cap_hda.py — build kitmash::part_terminator_cap::1.0, NATIVE interior.

Run:  /opt/hfs21.0.729/bin/hython houdini/make_cap_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py terminator_cap

The blanking cap is the FOURTH worked example of the wrapper-interior migration
(roadmap item 5), after tank, engine, and sensor_pod. Type name matches the
GEN_REGISTRY key `terminator_cap` so the generalized gate picks it up.

The cap is the DEGENERATE native case — the smallest part in the kit:
  - ONE Z-native tapered cylinder (km.gen_cap: cyl(0.22, 0.20, 0.12, seg=8) at
    np.eye(3), centered z=-0.06 -> spans z=-0.12..0.0). np.eye(3) -> `tube
    orient=2` (Z); a cone of revolution, so polygon phase is bbox-invariant —
    no phase roll. cap=1 closes both ends; seg=8 -> cols=8.
  - a -Z port (mating face down), struct_S, size 0.30 — load-bearing, fixed.
  - gen_params = {} — the cap takes NO accepted kwargs and records NO derived
    value (km.gen_cap(fc) has no seed even). So NO parm templates at all, and
    the VEX stamps gen_params as the literal empty object "{}". The gate's
    set(hgp)==set(gp) holds with both empty.
  - NO grommets/gedge/supplies(beyond [])/demands/clearance/anchor. mass 8,
    silhouette 0.02.

(Built ahead of the cook; run the gate, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_terminator_cap.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_terminator_cap")

# --- body: one Z-native tapered cylinder, 0.22 -> 0.20, height 0.12, z=-0.06 --
# Houdini tube orient=2 is the Z axis; rad1 at -Z, rad2 at +Z. seg=8 -> cols=8.
# A cone of revolution: phase-invariant bbox, no roll. Constant radii (no parm).
body = geo.createNode("tube", "shell")
body.setParms({"type": 1, "cap": 1, "orient": 2, "cols": 8,
               "rad1": 0.22, "rad2": 0.20, "height": 0.12, "tz": -0.06})

# --- ports + detail schema (VEX, detail mode) --------------------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
// ---- body group: every input prim is the placeholder cartoon ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port: struct_S plug, mating axis -Z (down), up +X ----
int pt = addpoint(0, {0, 0, 0});
setpointattrib(0, "N",            pt, {0, 0, -1});
setpointattrib(0, "up",           pt, {1, 0, 0});
setpointattrib(0, "port_type",    pt, "struct_S");
setpointattrib(0, "port_size",    pt, 0.30);
setpointattrib(0, "port_gender",  pt, 1);
setpointattrib(0, "port_prio",    pt, 5);
setpointattrib(0, "port_sym",     pt, 0);
setpointattrib(0, "port_cluster", pt, "");
setpointattrib(0, "port_tags",    pt, "");
setpointgroup(0, "ports", pt, 1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "terminator_cap");
setdetailattrib(0, "generator",  "gen_cap");
setdetailattrib(0, "gen_params", "{}");
setdetailattrib(0, "mass",       8.0);
setdetailattrib(0, "silhouette", 0.02);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[]");
// The cap declares no clearance/anchor volumes, but the wrapper schema stamps
// them anyway ("[]" / "null"). Match it so the gate PROVES the absence rather
// than skipping the check (attrib-presence guard): full parity, no dropped
// coverage.
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet([body, schema, out], "part_terminator_cap")
asset = subnet.createDigitalAsset(
    name="kitmash::part_terminator_cap::1.0",
    hda_file_name=OUT,
    description="KitMash blanking cap (family terminator_cap, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# gen_params = {} : no parm templates at all. The cap is fully constant.

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
