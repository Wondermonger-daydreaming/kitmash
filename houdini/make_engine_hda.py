"""make_engine_hda.py — build kitmash::part_engine::1.0 with a NATIVE interior.

Run:  /opt/hfs21.0.729/bin/hython houdini/make_engine_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py engine

The engine is the SECOND worked example of the wrapper-interior migration
(roadmap item 5), after the tank. It replaces the thin Python-SOP wrapper
(`houdini/hda/kitmash_part_engine.hda`) with a pure SOP/VEX network under the
SAME type name, so the For-Each rehydrator picks it up with no change. The
contract (kitmash_part_tank.md) holds: parms = gen_params; ports/grommets are
load-bearing and verified to NOT move; the body is a placeholder artists may
later greeble.

What the engine adds beyond the tank, as a migration example:
  - TWO X-oriented cones whose radii scale with the `size` parm
    (km.gen_engine: casing cyl 0.75s→0.95s h2.0 @x-1; nozzle 0.95s→0.55s
     h0.7 @x-2.3; frame([1,0,0],[0,0,1]) maps local Z→world X, vertex 0→+z,
     so each needs the tank's 90° phase roll)
  - a port whose axis is +X (not the tank's -Z) — mating face points forward
  - DEMANDS (fuel, scaling with size), not supplies
  - clearance_vols (the exhaust cone's required emptiness) AND anchor_vols
    (the casing only — never weld to the glow nozzle): the v0.8 provenance the
    rehydrator stamps struts from, exported as detail attrs for parity.

(Written ahead of the cook; the hou/VEX surface is where goblins live — run
the gate, fix in the surface, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_engine.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_engine")

# --- body: casing cone + nozzle cone, both X-oriented, phase-rolled ----------
# Houdini tube orient=0 is the X axis; rad1 at -X, rad2 at +X. Radii link to
# the `size` parm post-collapse (placeholder constants until then). The 90°
# roll about world X (pivot on the axis) phase-aligns the 14-gon with km.cyl
# (whose vertex 0 sits at world +z under frame([1,0,0],[0,0,1])).
casing = geo.createNode("tube", "casing")
casing.setParms({"type": 1, "cap": 1, "orient": 0, "cols": 14,
                 "rad1": 0.75, "rad2": 0.95, "height": 2.0, "tx": -1.0})
casing_phase = geo.createNode("xform", "casing_phase")
casing_phase.setInput(0, casing)
casing_phase.setParms({"rx": 90.0, "px": 0.0, "py": 0.0, "pz": 0.0})

nozzle = geo.createNode("tube", "nozzle")
nozzle.setParms({"type": 1, "cap": 1, "orient": 0, "cols": 14,
                 "rad1": 0.95, "rad2": 0.55, "height": 0.7, "tx": -2.3})
nozzle_phase = geo.createNode("xform", "nozzle_phase")
nozzle_phase.setInput(0, nozzle)
nozzle_phase.setParms({"rx": 90.0, "px": 0.0, "py": 0.0, "pz": 0.0})

body = geo.createNode("merge", "body_merge")
body.setInput(0, casing_phase)
body.setInput(1, nozzle_phase)

# --- ports + grommet + detail schema (VEX, detail mode) ----------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float size = chf("../size");

// ---- body group: every input prim is the placeholder cartoon ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port: struct_M plug, mating axis +X (forward), up +Z ----
int pt = addpoint(0, {0, 0, 0});
setpointattrib(0, "N",            pt, {1, 0, 0});
setpointattrib(0, "up",           pt, {0, 0, 1});
setpointattrib(0, "port_type",    pt, "struct_M");
setpointattrib(0, "port_size",    pt, 1.0);
setpointattrib(0, "port_gender",  pt, 1);
setpointattrib(0, "port_prio",    pt, 5);
setpointattrib(0, "port_sym",     pt, 0);
setpointattrib(0, "port_cluster", pt, "");
setpointattrib(0, "port_tags",    pt, "");
setpointgroup(0, "ports", pt, 1);

// ---- grommet: a single fuel tap (no intra-part edge) ----
int g0 = addpoint(0, set(-0.2, 0.0, 0.3));
setpointattrib(0, "conduit_type", g0, "fuel");
setpointattrib(0, "conduit_size", g0, 0.1);
setpointgroup(0, "grommets", g0, 1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "engine");
setdetailattrib(0, "generator",  "gen_engine");
// %.9g: full float32 fidelity (gen_params records full precision; %g's 6 sig
// digits would truncate below the verify gate's tolerance).
setdetailattrib(0, "gen_params",
    sprintf("{\"seed\": %d, \"size\": %.9g}", chi("../seed"), size));
setdetailattrib(0, "mass",       1400.0 * size);
setdetailattrib(0, "silhouette", 0.55);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    sprintf("[[\"fuel\", %.9g]]", 1.2 * size));
// v0.8 provenance: clearance hog (exhaust cone) + anchorable surfaces (the
// casing only — never the glow nozzle). AABBs as [[lo],[hi]], size-scaled.
setdetailattrib(0, "clearance_vols",
    "[[[-6.5, -0.9, -0.9], [-2.3, 0.9, 0.9]]]");
setdetailattrib(0, "anchor_vols",
    sprintf("[[[-2, %.9g, %.9g], [0, %.9g, %.9g]]]",
            -0.95 * size, -0.95 * size, 0.95 * size, 0.95 * size));
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet(
    [casing, casing_phase, nozzle, nozzle_phase, body, schema, out],
    "part_engine")
asset = subnet.createDigitalAsset(
    name="kitmash::part_engine::1.0",
    hda_file_name=OUT,
    description="KitMash engine (family engine, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: size (scales geometry/mass/anchor/demand), seed (cosmetic)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "size", "Size (gen_params.size)", 1, default_value=(1.0,),
    min=0.5, max=2.0,
    help="Scales casing/nozzle radii, mass, anchor box, and fuel demand."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; engine geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link the cone radii to the size parm (km.gen_engine coefficients)
for node, p, coef in (("casing", "rad1", 0.75), ("casing", "rad2", 0.95),
                      ("nozzle", "rad1", 0.95), ("nozzle", "rad2", 0.55)):
    asset.node(node).parm(p).setExpression(f'{coef}*ch("../size")')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
