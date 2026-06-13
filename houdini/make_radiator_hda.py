"""make_radiator_hda.py — build kitmash::part_radiator::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_radiator_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py radiator

The drop radiator is the SEVENTH worked example of the wrapper-interior
migration (roadmap item 5). Type name matches the GEN_REGISTRY key `radiator`.

What the radiator adds: the first family with BOTH non-empty clearance_vols
(w-scaled, computed in VEX) AND a literal anchor_vols — and an all-BOX body, so
there is no tube/phase concern at all.
  - body: a panel box (km.gen_radiator: box(0.16, w, 1.4) at z=-0.82, where the
    panel WIDTH sizey = w) MERGED with a mounting block (box(0.3, 0.3, 0.24) at
    z=-0.12). Panel sizey links to the `w` parm post-collapse.
  - a +Z struct_S port (size 0.30, fixed/load-bearing).
  - clearance_vols = one AABB whose y-bounds are w-dependent
    ([-2.2, -w/2-0.5, -2.4] .. [2.2, w/2+0.5, -0.25]) — the radiating faces
    demand a wide emptiness; computed in VEX from chf("../w").
  - anchor_vols = [[[-0.15,-0.15,-0.24],[0.15,0.15,0.0]]] (the mounting block
    only — the panel IS the glass), a literal AABB.
  - NO grommets/gedge/supplies/demands.
  - derived-only gen_param `w` (Python RNG: U(1.6, 2.0) from seed), exposed as a
    parm so the gate injects the Python value.

(Built ahead of the cook; run the gate, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_radiator.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_radiator")

# --- body: panel box (width = w) + mounting block ---------------------------
# All boxes, axis-aligned: no tube/phase concern. Panel sizey links to `w`.
panel = geo.createNode("box", "panel")
panel.setParms({"sizex": 0.16, "sizey": 2.0, "sizez": 1.4, "tz": -0.82})

block = geo.createNode("box", "block")
block.setParms({"sizex": 0.3, "sizey": 0.3, "sizez": 0.24, "tz": -0.12})

body = geo.createNode("merge", "body_merge")
body.setInput(0, panel)
body.setInput(1, block)

# --- ports + detail schema (VEX, detail mode) --------------------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float w = chf("../w");

// ---- body group: every input prim is the placeholder cartoon ----
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

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "radiator");
setdetailattrib(0, "generator",  "gen_radiator");
setdetailattrib(0, "gen_params",
    sprintf("{\"seed\": %d, \"w\": %.9g}", chi("../seed"), w));
setdetailattrib(0, "mass",       260.0);
setdetailattrib(0, "silhouette", 0.5);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[]");
// radiating faces demand a wide emptiness (y-bounds w-dependent); anchorable on
// the mounting block only (the panel IS the glass).
setdetailattrib(0, "clearance_vols",
    sprintf("[[[-2.2, %.9g, -2.4], [2.2, %.9g, -0.25]]]",
            -w / 2 - 0.5, w / 2 + 0.5));
setdetailattrib(0, "anchor_vols",
    "[[[-0.15, -0.15, -0.24], [0.15, 0.15, 0.0]]]");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet([panel, block, body, schema, out],
                                "part_radiator")
asset = subnet.createDigitalAsset(
    name="kitmash::part_radiator::1.0",
    hda_file_name=OUT,
    description="KitMash radiator (family radiator, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: w (derived in Python; drives panel width + clearance AABB
# y-bounds), seed (recorded; radiator geometry is otherwise seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "w", "Panel Width (gen_params.w)", 1, default_value=(1.8,),
    min=1.6, max=2.0,
    help="Derived by Python (U(1.6,2.0) from seed); consume as-is. "
         "Drives panel sizey and the clearance AABB y-bounds (+/- w/2+0.5)."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; radiator geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link the panel width to the w parm
asset.node("panel").parm("sizey").setExpression('ch("../w")')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
