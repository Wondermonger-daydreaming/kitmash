"""make_hull_hda.py — build kitmash::part_core_hull::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_hull_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py core_hull

The core hull is the EIGHTH worked example of the wrapper-interior migration
(roadmap item 5) — and the watch-list's biggest. Type name matches the
GEN_REGISTRY key `core_hull`.

Everything the first seven dodged shows up here at once:
  - body: a main hull BOX (km.gen_hull: box(L, W, H), L = 7*scale, W=2.2, H=1.8,
    centered at origin) MERGED with an X-CONE NOSE (cyl(0.9, 0.5, 1.6) under
    frame([1,0,0],[0,0,1]) at x = L/2+0.7). The nose is an X-tube (orient=0),
    so — like the engine/tank — it needs the 90 deg phase roll about its axis to
    align km.cyl's vertex-0-at-+z with Houdini's X-tube-starts-at-+y. The box
    sizex AND the nose tx both link to `scale` (L/2+0.7 = 3.5*scale+0.7).
  - SEVEN ports, all gender 0, with varying prio (9,8,8,9,4,3,3) and two carrying
    handedness tags (side_R / side_L). Port 0's x = -L/2 = -3.5*scale is the only
    scale-dependent port position; the rest are constants (W/2=1.1, H/2=0.9).
    ORDER MATTERS — the gate zips ports against the Python list, so they are
    emitted in exactly the generator's order.
  - FIVE fuel grommets at z = H/2-0.15 = 0.75; grommets 0 and 4 are
    scale-dependent (-L/2+0.3, L/2-0.6). FOUR gedges chaining them (0-1-2-3-4).
  - no supplies/demands/clearance/anchor (stamped "[]"/"null" for parity).
  - gen_params = {scale, seed}: `scale` is an accepted kwarg (drives L, nose,
    port0, grommets 0/4, mass). The gate only exercises scale=1.0 (it passes
    just seed; scale falls to its default), but the parm linkage must be correct.

(Built ahead of the cook; the hou/VEX surface is where goblins live — run the
gate, fix in the surface, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_core_hull.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_core_hull")

# --- body: main hull box (sizex = L = 7*scale) + X-cone nose -----------------
hull = geo.createNode("box", "hull")
hull.setParms({"sizex": 7.0, "sizey": 2.2, "sizez": 1.8})   # centered at origin

# X-cone nose: Houdini tube orient=0 (X); rad1 at -X (0.9), rad2 at +X (0.5).
# tx = L/2 + 0.7 = 3.5*scale + 0.7 (links to scale post-collapse). The 90 deg
# roll about the X axis (pivot on the axis: py=pz=0) phase-aligns with km.cyl.
nose = geo.createNode("tube", "nose")
nose.setParms({"type": 1, "cap": 1, "orient": 0, "cols": 14,
               "rad1": 0.9, "rad2": 0.5, "height": 1.6, "tx": 4.2})
nose_phase = geo.createNode("xform", "nose_phase")
nose_phase.setInput(0, nose)
nose_phase.setParms({"rx": 90.0, "px": 0.0, "py": 0.0, "pz": 0.0})

body = geo.createNode("merge", "body_merge")
body.setInput(0, hull)
body.setInput(1, nose_phase)

# --- ports + grommets + detail schema (VEX, detail mode) ---------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float scale = chf("../scale");
float L = 7.0 * scale;

// ---- body group: every input prim is the placeholder cartoon ----
// (run BEFORE the gedge polylines are added, so they stay out of "body")
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- SEVEN ports, in the generator's order (the gate zips by index) ----
// helper-free: emit each explicitly so types/prio/tags are unmistakable.
int p0 = addpoint(0, set(-L/2.0, 0, 0));
setpointattrib(0,"N",p0,{-1,0,0}); setpointattrib(0,"up",p0,{0,0,1});
setpointattrib(0,"port_type",p0,"struct_M"); setpointattrib(0,"port_size",p0,1.0);
setpointattrib(0,"port_gender",p0,0); setpointattrib(0,"port_prio",p0,9);
setpointattrib(0,"port_sym",p0,0); setpointattrib(0,"port_cluster",p0,"");
setpointattrib(0,"port_tags",p0,""); setpointgroup(0,"ports",p0,1);

int p1 = addpoint(0, set(0, 1.1, 0));   // W/2 = 1.1
setpointattrib(0,"N",p1,{0,1,0}); setpointattrib(0,"up",p1,{0,0,1});
setpointattrib(0,"port_type",p1,"struct_M"); setpointattrib(0,"port_size",p1,1.0);
setpointattrib(0,"port_gender",p1,0); setpointattrib(0,"port_prio",p1,8);
setpointattrib(0,"port_sym",p1,0); setpointattrib(0,"port_cluster",p1,"");
setpointattrib(0,"port_tags",p1,"side_R"); setpointgroup(0,"ports",p1,1);

int p2 = addpoint(0, set(0, -1.1, 0));
setpointattrib(0,"N",p2,{0,-1,0}); setpointattrib(0,"up",p2,{0,0,1});
setpointattrib(0,"port_type",p2,"struct_M"); setpointattrib(0,"port_size",p2,1.0);
setpointattrib(0,"port_gender",p2,0); setpointattrib(0,"port_prio",p2,8);
setpointattrib(0,"port_sym",p2,0); setpointattrib(0,"port_cluster",p2,"");
setpointattrib(0,"port_tags",p2,"side_L"); setpointgroup(0,"ports",p2,1);

int p3 = addpoint(0, set(1.8, 0, 0.9));   // H/2 = 0.9; fuel first
setpointattrib(0,"N",p3,{0,0,1}); setpointattrib(0,"up",p3,{1,0,0});
setpointattrib(0,"port_type",p3,"struct_M"); setpointattrib(0,"port_size",p3,0.8);
setpointattrib(0,"port_gender",p3,0); setpointattrib(0,"port_prio",p3,9);
setpointattrib(0,"port_sym",p3,0); setpointattrib(0,"port_cluster",p3,"");
setpointattrib(0,"port_tags",p3,""); setpointgroup(0,"ports",p3,1);

int p4 = addpoint(0, set(-1.5, 0, 0.9));
setpointattrib(0,"N",p4,{0,0,1}); setpointattrib(0,"up",p4,{1,0,0});
setpointattrib(0,"port_type",p4,"struct_S"); setpointattrib(0,"port_size",p4,0.30);
setpointattrib(0,"port_gender",p4,0); setpointattrib(0,"port_prio",p4,4);
setpointattrib(0,"port_sym",p4,0); setpointattrib(0,"port_cluster",p4,"");
setpointattrib(0,"port_tags",p4,""); setpointgroup(0,"ports",p4,1);

int p5 = addpoint(0, set(0.5, 0, -0.9));
setpointattrib(0,"N",p5,{0,0,-1}); setpointattrib(0,"up",p5,{1,0,0});
setpointattrib(0,"port_type",p5,"struct_S"); setpointattrib(0,"port_size",p5,0.30);
setpointattrib(0,"port_gender",p5,0); setpointattrib(0,"port_prio",p5,3);
setpointattrib(0,"port_sym",p5,0); setpointattrib(0,"port_cluster",p5,"");
setpointattrib(0,"port_tags",p5,""); setpointgroup(0,"ports",p5,1);

int p6 = addpoint(0, set(2.6, 0, -0.9));
setpointattrib(0,"N",p6,{0,0,-1}); setpointattrib(0,"up",p6,{1,0,0});
setpointattrib(0,"port_type",p6,"struct_S"); setpointattrib(0,"port_size",p6,0.30);
setpointattrib(0,"port_gender",p6,0); setpointattrib(0,"port_prio",p6,3);
setpointattrib(0,"port_sym",p6,0); setpointattrib(0,"port_cluster",p6,"");
setpointattrib(0,"port_tags",p6,""); setpointgroup(0,"ports",p6,1);

// ---- FIVE fuel grommets (z = H/2-0.15 = 0.75) + a 4-edge gedge chain ----
// x in (-L/2+0.3, -1.0, 1.0, 1.8, L/2-0.6): ends are scale-dependent.
float gx[] = array(-L/2.0 + 0.3, -1.0, 1.0, 1.8, L/2.0 - 0.6);
int gids[] = array();
foreach (float x; gx) {
    int g = addpoint(0, set(x, 0, 0.75));
    setpointattrib(0, "conduit_type", g, "fuel");
    setpointattrib(0, "conduit_size", g, 0.1);
    setpointgroup(0, "grommets", g, 1);
    append(gids, g);
}
for (int i = 0; i < len(gids) - 1; i++)
    addprim(0, "polyline", gids[i], gids[i + 1]);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "core_hull");
setdetailattrib(0, "generator",  "gen_hull");
setdetailattrib(0, "gen_params",
    sprintf("{\"scale\": %.9g, \"seed\": %d}", scale, chi("../seed")));
setdetailattrib(0, "mass",       4000.0 * scale);
setdetailattrib(0, "silhouette", 0.9);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[]");
// declares no clearance/anchor volumes; stamp empty to match wrapper schema.
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet(
    [hull, nose, nose_phase, body, schema, out], "part_core_hull")
asset = subnet.createDigitalAsset(
    name="kitmash::part_core_hull::1.0",
    hda_file_name=OUT,
    description="KitMash core hull (family core_hull, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: scale (drives L, nose tx, port0 x, grommets 0/4, mass),
# seed (recorded; core_hull geometry is otherwise seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "scale", "Hull Scale (gen_params.scale)", 1, default_value=(1.0,),
    min=0.5, max=2.0,
    help="Drives hull length L=7*scale, nose tx=3.5*scale+0.7, port0 x=-3.5*"
         "scale, grommets 0/4 x, and mass=4000*scale."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; core_hull geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link box length and nose position to the scale parm
asset.node("hull").parm("sizex").setExpression('7.0*ch("../scale")')
asset.node("nose").parm("tx").setExpression('3.5*ch("../scale") + 0.7')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
