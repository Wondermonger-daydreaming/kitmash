"""make_turret_hda.py — build kitmash::part_turret::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_turret_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py turret

The turret is the ELEVENTH and LAST worked example (roadmap item 5) — and the
watch-list's sharpest geometry: a TILTED barrel axis. Type name matches the
GEN_REGISTRY key `turret`.

km.gen_turret tilts the barrel with frame([1,0,0.35],[0,0,1]) — local Z maps to
a direction with both X and Z components, so a simple orient + 90 deg roll (the
engine/cannon X-tube trick) cannot reproduce it. Approximating with a single Y
rotation would match the axis but NOT the polygon phase, and for a tilted tapered
cone the phase shifts the bbox above the gate's 1e-4 tolerance. So we reproduce
km's EXACT rotation: compute R = km.frame([1,0,0.35],[0,0,1]) here, hand it to
Houdini as a matrix, and let hou.Matrix4.extractRotates() give Euler angles in
Houdini's own convention — guaranteed consistent with the xform SOP.
  - body: a turret box(0.5, 0.5, 0.3) at z=0.2 MERGED with a Z-native barrel
    cyl(0.06, 0.05, barrel) rotated by the exact frame and translated to
    [barrel/2+0.2, 0, 0.42]. Barrel built orient=2 (Z) to match km.cyl's local
    frame; the frame rotation then does the rest. Barrel height + the xform tx
    both link to the derived `barrel` parm.
  - a -Z struct_S port (gender 1, fixed).
  - a high_volt grommet (no gedge) + DEMANDS high_volt 1.8.
  - gen_params = {seed, barrel}: `barrel` is RNG-derived (U(0.7,0.9)), exposed as
    a parm so the gate injects the Python value.

(Built ahead of the cook; run the gate, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)
import numpy as np
import kitmash as km

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(HERE, "kitmash_part_turret.hda")

# --- reproduce km's tilted-barrel rotation EXACTLY ---------------------------
# km does v_world = R @ v_local + t, with R = frame([1,0,0.35],[0,0,1]) (its
# columns are the world images of local X/Y/Z). Euler decomposition + the xform
# SOP's rotation-order composition did NOT reproduce R faithfully (bbox drifted
# ~1e-2 at the muzzle), so we apply R DIRECTLY as a matrix in a point wrangle.
# VEX transforms row vectors (P*M), so P_world = P_local @ R.T -> M = R.T, whose
# rows are R's columns. Baked at full precision into the wrangle below.
R = km.frame(np.array([1.0, 0.0, 0.35]), np.array([0.0, 0.0, 1.0]))
# M = R.T row-major (each row of M is a column of R):
M_VEX = "set({:.17g},{:.17g},{:.17g}, {:.17g},{:.17g},{:.17g}, " \
        "{:.17g},{:.17g},{:.17g})".format(
            R[0, 0], R[1, 0], R[2, 0],
            R[0, 1], R[1, 1], R[2, 1],
            R[0, 2], R[1, 2], R[2, 2])

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_turret")

# --- body: turret box + tilted Z-native barrel -------------------------------
base = geo.createNode("box", "base")
base.setParms({"sizex": 0.5, "sizey": 0.5, "sizez": 0.3, "tz": 0.2})

# barrel built Z-native (orient=2) to match km.cyl's local frame; the exact
# frame rotation is applied by the xform below, then it is translated.
# NOTE: Houdini's Z-tube (orient=2) puts rad1 at +Z, but km.cyl(r0,r1,h) puts
# r0 at -h/2 (-Z). So to match km.cyl(0.06, 0.05) the radii are SWAPPED:
# rad1 = r1 = 0.05 (top/+Z), rad2 = r0 = 0.06 (bottom/-Z). This is invisible to
# an axis-aligned bbox (xy = max radius either way) but the turret's TILT exposes
# it — the reason this family caught a taper-direction bug the others hid.
barrel = geo.createNode("tube", "barrel")
barrel.setParms({"type": 1, "cap": 1, "orient": 2, "cols": 14,
                 "rad1": 0.05, "rad2": 0.06, "height": 0.8})
# apply km's exact frame rotation, then translate to the muzzle seat
# [barrel/2+0.2, 0, 0.42] (the tx tracks the barrel parm).
barrel_xf = geo.createNode("attribwrangle", "barrel_xf")
barrel_xf.setInput(0, barrel)
barrel_xf.setParms({"class": 2})                           # point
barrel_xf.parm("snippet").set(
    "matrix3 M = " + M_VEX + ";\n"
    "@P = @P * M;\n"
    '@P += set(ch("../barrel")/2 + 0.2, 0, 0.42);\n')

body = geo.createNode("merge", "body_merge")
body.setInput(0, base)
body.setInput(1, barrel_xf)

# --- ports + grommet + detail schema (VEX, detail mode) ----------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float barrel = chf("../barrel");

// ---- body group: every input prim is the placeholder cartoon ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port: struct_S plug, mating axis -Z (down), up +X ----
int pt = addpoint(0, {0, 0, 0});
setpointattrib(0,"N",pt,{0,0,-1}); setpointattrib(0,"up",pt,{1,0,0});
setpointattrib(0,"port_type",pt,"struct_S"); setpointattrib(0,"port_size",pt,0.30);
setpointattrib(0,"port_gender",pt,1); setpointattrib(0,"port_prio",pt,5);
setpointattrib(0,"port_sym",pt,0); setpointattrib(0,"port_cluster",pt,"");
setpointattrib(0,"port_tags",pt,""); setpointgroup(0,"ports",pt,1);

// ---- grommet: a single high_volt tap (no intra-part edge) ----
int g0 = addpoint(0, set(0, 0, 0.12));
setpointattrib(0,"conduit_type",g0,"high_volt");
setpointattrib(0,"conduit_size",g0,0.1);
setpointgroup(0,"grommets",g0,1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "turret");
setdetailattrib(0, "generator",  "gen_turret");
setdetailattrib(0, "gen_params",
    sprintf("{\"seed\": %d, \"barrel\": %.9g}", chi("../seed"), barrel));
setdetailattrib(0, "mass",       170.0);
setdetailattrib(0, "silhouette", 0.3);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[[\"high_volt\", 1.8]]");
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet(
    [base, barrel, barrel_xf, body, schema, out], "part_turret")
asset = subnet.createDigitalAsset(
    name="kitmash::part_turret::1.0",
    hda_file_name=OUT,
    description="KitMash turret (family turret, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: barrel (derived; drives barrel length + muzzle tx),
# seed (recorded; turret geometry is otherwise seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "barrel", "Barrel Length (gen_params.barrel)", 1, default_value=(0.8,),
    min=0.7, max=0.9,
    help="Derived by Python (U(0.7,0.9) from seed); consume as-is. "
         "Drives barrel height and the muzzle tx (barrel/2+0.2)."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; turret geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link barrel length to the barrel parm (the muzzle tx is read in the wrangle)
asset.node("barrel").parm("height").setExpression('ch("../barrel")')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
