"""make_reactor_hda.py — build kitmash::part_reactor::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_reactor_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py reactor

The auxiliary reactor pod is the FIFTH worked example of the wrapper-interior
migration (roadmap item 5), after tank, engine, sensor_pod, terminator_cap.
Type name matches the GEN_REGISTRY key `reactor` so the generalized gate picks
up this native interior over the wrapper of the same type (installed last).

What the reactor adds beyond the earlier examples — the first ROUTING body on a
Z-native cylinder (the tank proved grommets+gedge+supplies, but on an X-drum):
  - body: a Z-native tapered cylinder (km.gen_reactor: cyl(0.34, 0.30, h,
    seg=10) at np.eye(3), center z = -h/2-0.07) MERGED with a mounting box
    (box(0.5, 0.5, 0.14) at z=-0.07). np.eye(3) -> `tube orient=2` (Z); a body
    of revolution, so polygon phase is bbox-invariant — no phase roll (the
    sensor_pod proved the Z-tube cross-section already aligns with km.cyl's
    vertex-0-at-+x). The tube HEIGHT and its CENTER z both depend on `h`, so
    both link to the parm post-collapse.
  - a +Z struct_S port (size 0.30, fixed/load-bearing).
  - TWO high_volt grommets + an intra-part gedge (the supply tap is grom[0],
    per the generator's docstring). The SECOND grommet's z depends on h
    (-h-0.05), so it is computed in VEX from chf("../h"); the first is fixed.
  - SUPPLIES high_volt 4.0 (constant). No demands, no clearance/anchor volumes
    (stamped "[]"/"null" anyway for full wrapper-schema parity).
  - a derived-only gen_param `h` (Python RNG: U(0.85, 1.0) from seed), exposed
    as a parm so the gate injects the Python value; the native VEX never
    reproduces the RNG.

(Written ahead of the cook; the hou/VEX surface is where goblins live — run the
gate, fix in the surface, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_reactor.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_reactor")

# --- body: tapered Z-native cylinder (0.34 -> 0.30, height h) + mounting box --
# Houdini tube orient=2 is the Z axis; rad1 at -Z (0.34), rad2 at +Z (0.30).
# seg=10 -> cols=10. Height AND center-z both link to `h` post-collapse
# (km: center z = -h/2 - 0.07). No phase roll (Z-tube, body of revolution).
shell = geo.createNode("tube", "shell")
shell.setParms({"type": 1, "cap": 1, "orient": 2, "cols": 10,
                "rad1": 0.34, "rad2": 0.30, "height": 1.0, "tz": -0.57})

mount = geo.createNode("box", "mount")
mount.setParms({"sizex": 0.5, "sizey": 0.5, "sizez": 0.14, "tz": -0.07})

body = geo.createNode("merge", "body_merge")
body.setInput(0, shell)
body.setInput(1, mount)

# --- ports + grommets + detail schema (VEX, detail mode) ---------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float h = chf("../h");

// ---- body group: every input prim is the placeholder cartoon ----
// (run BEFORE the gedge polyline is added, so the gedge stays out of "body")
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port: struct_S plug, mating axis +Z (up), up +X ----
int pt = addpoint(0, {0, 0, 0});
setpointattrib(0, "N",            pt, {0, 0, 1});
setpointattrib(0, "up",           pt, {1, 0, 0});
setpointattrib(0, "port_type",    pt, "struct_S");
setpointattrib(0, "port_size",    pt, 0.30);
setpointattrib(0, "port_gender",  pt, 1);
setpointattrib(0, "port_prio",    pt, 5);
setpointattrib(0, "port_sym",     pt, 0);
setpointattrib(0, "port_cluster", pt, "");
setpointattrib(0, "port_tags",    pt, "");
setpointgroup(0, "ports", pt, 1);

// ---- grommets + the pre-authored intra-part routing edge ----
// grom[0] is the supply tap (fixed); grom[1]'s z depends on h (-h-0.05).
int g0 = addpoint(0, set(0.0,  0.0, -0.18));
int g1 = addpoint(0, set(0.36, 0.0, -h - 0.05));
int gs[] = array(g0, g1);
foreach (int g; gs) {
    setpointattrib(0, "conduit_type", g, "high_volt");
    setpointattrib(0, "conduit_size", g, 0.12);
    setpointgroup(0, "grommets", g, 1);
}
addprim(0, "polyline", g0, g1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "reactor");
setdetailattrib(0, "generator",  "gen_reactor");
// %.9g: full float32 fidelity (gen_params records full precision; %g's 6 sig
// digits would truncate below the verify gate's tolerance).
setdetailattrib(0, "gen_params",
    sprintf("{\"seed\": %d, \"h\": %.9g}", chi("../seed"), h));
setdetailattrib(0, "mass",       420.0);
setdetailattrib(0, "silhouette", 0.35);
setdetailattrib(0, "supplies",   "[[\"high_volt\", 4.0]]");
setdetailattrib(0, "demands",    "[]");
// declares no clearance/anchor volumes; stamp empty to match wrapper schema
// (so the gate PROVES the absence rather than skipping the check).
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet([shell, mount, body, schema, out],
                                "part_reactor")
asset = subnet.createDigitalAsset(
    name="kitmash::part_reactor::1.0",
    hda_file_name=OUT,
    description="KitMash reactor (family reactor, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: h (derived in Python; drives shell height + center z and
# grommet[1] z), seed (recorded; reactor geometry is otherwise seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "h", "Core Height (gen_params.h)", 1, default_value=(0.925,),
    min=0.85, max=1.0,
    help="Derived by Python (U(0.85,1.0) from seed); consume as-is. "
         "Drives shell height, shell center z (-h/2-0.07), and grommet[1] z."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; reactor geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link the shell height and center-z to the h parm (km: center z = -h/2 - 0.07)
asset.node("shell").parm("height").setExpression('ch("../h")')
asset.node("shell").parm("tz").setExpression('-ch("../h")/2 - 0.07')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
