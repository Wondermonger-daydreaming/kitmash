"""make_wing_hda.py — build kitmash::part_wing::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_wing_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py wing

The wing is the TENTH worked example (roadmap item 5), a watch-list family.
Type name matches the GEN_REGISTRY key `wing`.

What it adds: TWO geometry parms (span, hand) where `hand` flips handedness —
port x-signs, up vectors, and the side_R/side_L tag all depend on it. All-BOX
body, so no tube/phase concern.
  - body: a wing panel box(2.0, span, 0.22) at y=span/2 MERGED with a root box
    (2.2, 0.5, 0.34) at y=0.25. Panel sizey AND ty link to `span`.
  - port 0: a struct_M root mount, gender 1, with tag side_R/side_L by `hand`.
  - ports 1,2: a mount_rail CLUSTER "railA" (gender 0, sym 1, prio 8) at the
    wingtip (y = span-0.45); their x = -/+0.5*hand and up = (hand,0,0) flip with
    handedness. ORDER MATTERS (the gate zips by index).
  - TWO fuel grommets (the second's y = span-0.85 tracks span) + 1 gedge.
  - gen_params = {span, hand, seed}. The gate exercises span=3.2, hand=1; VEX
    reads chf("../span")/chi("../hand") so handedness is computed, not baked.

(Built ahead of the cook; run the gate, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_wing.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_wing")

# --- body: wing panel (sizey = span) + root box -----------------------------
panel = geo.createNode("box", "panel")
panel.setParms({"sizex": 2.0, "sizey": 3.2, "sizez": 0.22, "ty": 1.6})

root = geo.createNode("box", "root")
root.setParms({"sizex": 2.2, "sizey": 0.5, "sizez": 0.34, "ty": 0.25})

body = geo.createNode("merge", "body_merge")
body.setInput(0, panel)
body.setInput(1, root)

# --- ports + grommets + detail schema (VEX, detail mode) ---------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float span = chf("../span");
int   hand = chi("../hand");
float y    = span - 0.45;
vector up_rail = set(hand, 0, 0);
string side = hand > 0 ? "side_R" : "side_L";

// ---- body group: every input prim is the placeholder cartoon ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port 0: struct_M root mount (gender 1), handedness tag ----
int p0 = addpoint(0, {0, 0, 0});
setpointattrib(0,"N",p0,{0,-1,0}); setpointattrib(0,"up",p0,{0,0,1});
setpointattrib(0,"port_type",p0,"struct_M"); setpointattrib(0,"port_size",p0,1.0);
setpointattrib(0,"port_gender",p0,1); setpointattrib(0,"port_prio",p0,5);
setpointattrib(0,"port_sym",p0,0); setpointattrib(0,"port_cluster",p0,"");
setpointattrib(0,"port_tags",p0,side); setpointgroup(0,"ports",p0,1);

// ---- ports 1,2: mount_rail cluster railA (gender 0, sym 1), hand-flipped ----
int p1 = addpoint(0, set(-0.5*hand, y, 0.11));
setpointattrib(0,"N",p1,{0,0,1}); setpointattrib(0,"up",p1,up_rail);
setpointattrib(0,"port_type",p1,"mount_rail"); setpointattrib(0,"port_size",p1,0.4);
setpointattrib(0,"port_gender",p1,0); setpointattrib(0,"port_prio",p1,8);
setpointattrib(0,"port_sym",p1,1); setpointattrib(0,"port_cluster",p1,"railA");
setpointattrib(0,"port_tags",p1,""); setpointgroup(0,"ports",p1,1);

int p2 = addpoint(0, set(0.5*hand, y, 0.11));
setpointattrib(0,"N",p2,{0,0,1}); setpointattrib(0,"up",p2,up_rail);
setpointattrib(0,"port_type",p2,"mount_rail"); setpointattrib(0,"port_size",p2,0.4);
setpointattrib(0,"port_gender",p2,0); setpointattrib(0,"port_prio",p2,8);
setpointattrib(0,"port_sym",p2,1); setpointattrib(0,"port_cluster",p2,"railA");
setpointattrib(0,"port_tags",p2,""); setpointgroup(0,"ports",p2,1);

// ---- TWO fuel grommets (second tracks span) + 1 gedge ----
int g0 = addpoint(0, set(0, 0.2, 0.12));
int g1 = addpoint(0, set(0, y - 0.4, 0.12));
int gs[] = array(g0, g1);
foreach (int g; gs) {
    setpointattrib(0, "conduit_type", g, "fuel");
    setpointattrib(0, "conduit_size", g, 0.1);
    setpointgroup(0, "grommets", g, 1);
}
addprim(0, "polyline", g0, g1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "wing");
setdetailattrib(0, "generator",  "gen_wing");
setdetailattrib(0, "gen_params",
    sprintf("{\"span\": %.9g, \"hand\": %d, \"seed\": %d}",
            span, hand, chi("../seed")));
setdetailattrib(0, "mass",       600.0 * span / 3.2);
setdetailattrib(0, "silhouette", 0.7);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[]");
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet([panel, root, body, schema, out], "part_wing")
asset = subnet.createDigitalAsset(
    name="kitmash::part_wing::1.0",
    hda_file_name=OUT,
    description="KitMash wing (family wing, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: span (drives panel sizey/ty, tip-port y, grommet y, mass),
# hand (+1/-1 handedness: port x-signs, up vectors, side tag), seed (recorded)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "span", "Span (gen_params.span)", 1, default_value=(3.2,),
    min=2.0, max=5.0,
    help="Drives panel sizey + ty (span/2), tip-port y (span-0.45), grommet[1] "
         "y (span-0.85), and mass (600*span/3.2)."))
ptg.append(hou.IntParmTemplate(
    "hand", "Hand (gen_params.hand: +1 R / -1 L)", 1, default_value=(1,),
    min=-1, max=1,
    help="Handedness: flips rail-port x-signs and up vectors, and the "
         "side_R/side_L tag on the root port."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; wing geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link the panel width and center to span
asset.node("panel").parm("sizey").setExpression('ch("../span")')
asset.node("panel").parm("ty").setExpression('ch("../span")/2')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
