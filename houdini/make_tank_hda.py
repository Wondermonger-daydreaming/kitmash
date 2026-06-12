"""make_tank_hda.py — build kitmash::part_tank::1.0 programmatically.

Run:  source /opt/hfs21.0/houdini_setup
      hython houdini/make_tank_hda.py [out.hda]

Builds the network specified in kitmash_part_tank.md, collapses it into
a subnet, converts to a digital asset with parms (h, seed), and saves
houdini/kitmash_part_tank.hda. Then run verify_tank_hda.py to prove the
round trip. (Written ahead of the install; hou API is standard but this
script is UNTESTED until Houdini 21.0.729 lands.)
"""
import os, sys
import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_tank.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_tank")

# --- body: drum (axis +X, centered z=0.55) + mounting skirt -----------------
tube = geo.createNode("tube", "drum")
tube.setParms({"type": 1, "cap": 1, "orient": 0,          # poly, capped, X
               "rad1": 0.55, "rad2": 0.55, "cols": 14,
               "tz": 0.55})
tube.parm("height").set(2.4)                               # re-linked below

skirt = geo.createNode("box", "skirt")
skirt.setParms({"sizex": 0.7, "sizey": 0.7, "sizez": 0.12, "tz": 0.05})

body = geo.createNode("merge", "body_merge")
body.setInput(0, tube); body.setInput(1, skirt)

# --- ports + grommets + detail schema (VEX, detail mode) --------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (once)
schema.parm("snippet").set(r'''
// ---- body group: every input prim (the gedge added below stays out) ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port: struct_M plug, mounts downward ----
int pt = addpoint(0, {0, 0, 0});
setpointattrib(0, "N",            pt, {0, 0, -1});
setpointattrib(0, "up",           pt, {1, 0, 0});
setpointattrib(0, "port_type",    pt, "struct_M");
setpointattrib(0, "port_size",    pt, 0.8);
setpointattrib(0, "port_gender",  pt, 1);
setpointattrib(0, "port_prio",    pt, 5);
setpointattrib(0, "port_sym",     pt, 0);
setpointattrib(0, "port_cluster", pt, "");
setpointattrib(0, "port_tags",    pt, "");
setpointgroup(0, "ports", pt, 1);

// ---- grommets + the pre-authored intra-part routing edge ----
float h = chf("../h");
int g0 = addpoint(0, {0, 0, 0.1});
int g1 = addpoint(0, set(0.6, 0.0, 0.55));
foreach (int g; array(g0, g1)) {
    setpointattrib(0, "conduit_type", g, "fuel");
    setpointattrib(0, "conduit_size", g, 0.1);
    setpointgroup(0, "grommets", g, 1);
}
addprim(0, "polyline", g0, g1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "fuel_tank");
setdetailattrib(0, "generator",  "gen_tank");
setdetailattrib(0, "gen_params",
    sprintf("{\"h\": %g, \"seed\": %d}", h, chi("../seed")));
setdetailattrib(0, "mass",       900.0 * h / 2.4);
setdetailattrib(0, "silhouette", 0.45);
setdetailattrib(0, "supplies",   "[[\"fuel\", 3.0]]");
setdetailattrib(0, "demands",    "[]");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True); out.setRenderFlag(True)

# --- collapse -> digital asset ----------------------------------------------
subnet = geo.collapseIntoSubnet(
    [tube, skirt, body, schema, out], "part_tank")
asset = subnet.createDigitalAsset(
    name="kitmash::part_tank::1.0",
    hda_file_name=OUT,
    description="KitMash fuel tank (family fuel_tank, schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: h (derived in Python, consumed here), seed (cosmetic)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "h", "Drum Length (gen_params.h)", 1, default_value=(2.4,),
    min=2.16, max=2.64,
    help="Derived by Python (2.4*U(0.9,1.1) from seed); consume as-is."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (cosmetic VEX jitter only)", 1, default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link internals to the asset parms
inner = asset.node("drum")
inner.parm("height").setExpression('ch("../h")')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
