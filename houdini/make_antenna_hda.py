"""make_antenna_hda.py — build kitmash::part_antenna::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_antenna_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py antenna

The antenna is the SIXTH worked example of the wrapper-interior migration
(roadmap item 5). Type name matches the GEN_REGISTRY key `antenna`.

What the antenna adds: the first NON-NULL `anchor_vols` on a simple body —
the mast is a whip (not weldable), so only the base box is anchorable. The
AABB is a literal (not h-scaled), stamped in VEX.
  - body: a Z-native whip cone (km.gen_antenna: cyl(0.05, 0.02, h, seg=14) at
    np.eye(3), center z = h/2) MERGED with a base box (box(0.3, 0.3, 0.1) at
    z=0.05). np.eye(3) -> `tube orient=2` (Z); body of revolution -> no phase
    roll; seg default 14 -> cols=14. Height AND center-z link to `h`.
  - a -Z struct_S port (size 0.30, fixed/load-bearing).
  - NO grommets/gedge/supplies/demands/clearances.
  - anchor_vols = [[[-0.15,-0.15,0.0],[0.15,0.15,0.1]]] (the base box only),
    a literal AABB. clearance_vols stamped "[]" for parity.
  - derived-only gen_param `h` (Python RNG: 1.9*U(0.85,1.2) from seed), exposed
    as a parm so the gate injects the Python value.

(Built ahead of the cook; run the gate, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_antenna.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_antenna")

# --- body: Z-native whip cone (0.05 -> 0.02, height h) + base box ------------
# Houdini tube orient=2 is the Z axis; rad1 at -Z (0.05), rad2 at +Z (0.02).
# seg default 14 -> cols=14. Height AND center-z both link to `h` (km center
# z = h/2). No phase roll (Z-tube, body of revolution).
# NOTE: Houdini's tube puts rad1 at +Z; km.cyl(0.05, 0.02) puts r0=0.05 at -h/2.
# So rad1=0.02 (+Z, the whip tip), rad2=0.05 (-Z, the base) — SWAPPED so the
# mast tapers to a point at the top, not the bottom.
mast = geo.createNode("tube", "mast")
mast.setParms({"type": 1, "cap": 1, "orient": 2, "cols": 14,
               "rad1": 0.02, "rad2": 0.05, "height": 1.0, "tz": 0.5})

base = geo.createNode("box", "base")
base.setParms({"sizex": 0.3, "sizey": 0.3, "sizez": 0.1, "tz": 0.05})

body = geo.createNode("merge", "body_merge")
body.setInput(0, mast)
body.setInput(1, base)

# --- ports + detail schema (VEX, detail mode) --------------------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float h = chf("../h");

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
setdetailattrib(0, "family",     "antenna");
setdetailattrib(0, "generator",  "gen_antenna");
setdetailattrib(0, "gen_params",
    sprintf("{\"seed\": %d, \"h\": %.9g}", chi("../seed"), h));
setdetailattrib(0, "mass",       40.0);
setdetailattrib(0, "silhouette", 0.25);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[]");
// the mast is a whip (not weldable); only the base box is anchorable.
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",
    "[[[-0.15, -0.15, 0.0], [0.15, 0.15, 0.1]]]");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet([mast, base, body, schema, out],
                                "part_antenna")
asset = subnet.createDigitalAsset(
    name="kitmash::part_antenna::1.0",
    hda_file_name=OUT,
    description="KitMash antenna (family antenna, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: h (derived in Python; drives mast height + center z),
# seed (recorded; antenna geometry is otherwise seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "h", "Mast Length (gen_params.h)", 1, default_value=(1.9,),
    min=1.615, max=2.28,
    help="Derived by Python (1.9*U(0.85,1.2) from seed); consume as-is. "
         "Drives mast height and mast center z (h/2)."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; antenna geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link the mast height and center-z to the h parm (km: center z = h/2)
asset.node("mast").parm("height").setExpression('ch("../h")')
asset.node("mast").parm("tz").setExpression('ch("../h")/2')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
