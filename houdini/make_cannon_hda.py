"""make_cannon_hda.py — build kitmash::part_heavy_cannon::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_cannon_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py heavy_cannon

The heavy cannon is the NINTH worked example (roadmap item 5), a watch-list
family. Type name matches the GEN_REGISTRY key `heavy_cannon`.

What it adds: a mount_rail CLUSTER, and an X-tube barrel OFFSET in z — so the
90 deg phase roll must pivot on the barrel's actual axis (z=0.42), not z=0.
  - body: a receiver box(1.3, 0.6, 0.5) at z=0.35 MERGED with an X-cone barrel
    (km.gen_cannon: cyl(0.12, 0.10, 2.6*heavy) under frame([1,0,0],[0,0,1]) at
    [1.6*heavy, 0, 0.42]). The barrel is an X-tube (orient=0); like the engine
    it needs the 90 deg roll to align km.cyl's vertex-0-at-+z with Houdini's
    X-tube-at-+y — BUT the barrel sits at z=0.42, so the roll pivots at
    py=0, pz=0.42 (rolling about the barrel's own axis). Barrel height + tx both
    link to `heavy` (2.6*heavy, 1.6*heavy).
  - TWO mount_rail ports, gender 1, sym 1, cluster "railA" (the cluster the
    assembler bonds as a pair), up=+X.
  - no grommets/gedge/supplies/demands/clearance/anchor (stamped "[]"/"null").
  - gen_params = {heavy, seed}: `heavy` is an accepted kwarg (drives barrel +
    mass). The gate exercises heavy=1.0; the parm linkage covers any value.

(Built ahead of the cook; run the gate, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_heavy_cannon.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_heavy_cannon")

# --- body: receiver box + X-cone barrel (offset to z=0.42) -------------------
recv = geo.createNode("box", "receiver")
recv.setParms({"sizex": 1.3, "sizey": 0.6, "sizez": 0.5, "tz": 0.35})

# X-cone barrel: tube orient=0 (X); rad1 at -X (0.12), rad2 at +X (0.10).
# tx = 1.6*heavy (links), tz=0.42. The 90 deg roll pivots on the barrel axis
# (py=0, pz=0.42), NOT z=0 — the barrel is offset in z.
# NOTE: Houdini's X-tube puts rad1 at +X; km.cyl(0.12, 0.10) under frame(local
# Z->world X) puts r0=0.12 at -X. So rad1=0.10 (+X, the muzzle), rad2=0.12 (-X)
# — SWAPPED for the correct taper direction. (Bbox-invariant.)
barrel = geo.createNode("tube", "barrel")
barrel.setParms({"type": 1, "cap": 1, "orient": 0, "cols": 14,
                 "rad1": 0.10, "rad2": 0.12, "height": 2.6,
                 "tx": 1.6, "tz": 0.42})
barrel_phase = geo.createNode("xform", "barrel_phase")
barrel_phase.setInput(0, barrel)
barrel_phase.setParms({"rx": 90.0, "px": 0.0, "py": 0.0, "pz": 0.42})

body = geo.createNode("merge", "body_merge")
body.setInput(0, recv)
body.setInput(1, barrel_phase)

# --- ports + detail schema (VEX, detail mode) --------------------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float heavy = chf("../heavy");

// ---- body group: every input prim is the placeholder cartoon ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- TWO mount_rail ports (cluster railA, gender 1, sym 1, up +X) ----
int p0 = addpoint(0, set(-0.5, 0, 0.1));
setpointattrib(0,"N",p0,{0,0,-1}); setpointattrib(0,"up",p0,{1,0,0});
setpointattrib(0,"port_type",p0,"mount_rail"); setpointattrib(0,"port_size",p0,0.4);
setpointattrib(0,"port_gender",p0,1); setpointattrib(0,"port_prio",p0,5);
setpointattrib(0,"port_sym",p0,1); setpointattrib(0,"port_cluster",p0,"railA");
setpointattrib(0,"port_tags",p0,""); setpointgroup(0,"ports",p0,1);

int p1 = addpoint(0, set(0.5, 0, 0.1));
setpointattrib(0,"N",p1,{0,0,-1}); setpointattrib(0,"up",p1,{1,0,0});
setpointattrib(0,"port_type",p1,"mount_rail"); setpointattrib(0,"port_size",p1,0.4);
setpointattrib(0,"port_gender",p1,1); setpointattrib(0,"port_prio",p1,5);
setpointattrib(0,"port_sym",p1,1); setpointattrib(0,"port_cluster",p1,"railA");
setpointattrib(0,"port_tags",p1,""); setpointgroup(0,"ports",p1,1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "heavy_cannon");
setdetailattrib(0, "generator",  "gen_cannon");
setdetailattrib(0, "gen_params",
    sprintf("{\"heavy\": %.9g, \"seed\": %d}", heavy, chi("../seed")));
setdetailattrib(0, "mass",       950.0 * heavy);
setdetailattrib(0, "silhouette", 0.5);
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
subnet = geo.collapseIntoSubnet(
    [recv, barrel, barrel_phase, body, schema, out], "part_heavy_cannon")
asset = subnet.createDigitalAsset(
    name="kitmash::part_heavy_cannon::1.0",
    hda_file_name=OUT,
    description="KitMash heavy cannon (family heavy_cannon, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: heavy (scales barrel length 2.6*heavy, barrel tx 1.6*heavy,
# and mass 950*heavy), seed (recorded; cannon geometry is seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "heavy", "Heaviness (gen_params.heavy)", 1, default_value=(1.0,),
    min=0.5, max=2.0,
    help="Scales barrel length (2.6*heavy), barrel tx (1.6*heavy), and mass."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; cannon geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link barrel length and x-position to the heavy parm
asset.node("barrel").parm("height").setExpression('2.6*ch("../heavy")')
asset.node("barrel").parm("tx").setExpression('1.6*ch("../heavy")')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
