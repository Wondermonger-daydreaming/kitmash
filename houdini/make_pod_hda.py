"""make_pod_hda.py — build kitmash::part_sensor_pod::1.0 with a NATIVE interior.

Run:  /opt/hfs21.0.729/bin/hython houdini/make_pod_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py sensor_pod

The sensor pod is the THIRD worked example of the wrapper-interior migration
(roadmap item 5), after tank and engine. It replaces the thin Python-SOP
wrapper (`houdini/hda/kitmash_part_sensor_pod.hda`) with a pure SOP/VEX network
under the SAME type name the registry uses — `kitmash::part_sensor_pod::1.0`
(matched to the GEN_REGISTRY key `sensor_pod`, so the generalized gate
`verify_native_hda.py` picks it up — every native HDA's type suffix MUST equal
its registry key, the lesson the tank's old `part_tank` type taught when it
silently masqueraded as native; fixed to `part_fuel_tank` in v0.12).

What the pod shows as a migration example — the MINIMAL native case:
  - ONE Z-native cylinder (km.gen_pod: cyl(r-0.02, r-0.02, 0.8, seg=10) at
    np.eye(3), centered z=-0.45). np.eye(3) is the cyl's native Z axis ->
    `tube orient=2` (Z). It is a STRAIGHT cylinder of revolution, so the
    14/10-gon's polygon phase is cosmetically invisible and the body bbox is
    phase-invariant — no phase-roll needed (unlike the tank/engine X-tubes,
    which DO need the 90 deg roll to align their cross-section). The verify gate
    holds the body to +/-1e-4 and that is exact here.
  - a +Z port (mating face up), struct_S, size = the derived radius `r`.
  - a derived-only gen_param `r` (Python RNG: U(0.30, 0.345) from seed): the
    native VEX never reproduces the RNG — `r` is EXPOSED AS A PARM so the gate
    injects the Python value (verify sets every parm that names a gen_params
    key), and the VEX reads ch("../r"). Geometry: radius links to r-0.02.
  - NO grommets, NO gedge, NO supplies/demands, NO clearance/anchor volumes
    (the pod declares none) — so, following the tank precedent, those detail
    attrs are stamped to match the wrapper's full schema exactly: supplies/
    demands -> "[]", clearance_vols -> "[]", anchor_vols -> "null". (The gate
    guards clearance_vols/anchor_vols on attrib-presence, so omitting them would
    pass too — but stamping them keeps full parity and PROVES the absence rather
    than silently dropping those checks.)

(Written ahead of the cook; the hou/VEX surface is where goblins live — run the
gate, fix in the surface, never trust 'built' over 'cooks'.)
"""
import os
import sys

import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_sensor_pod.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_sensor_pod")

# --- body: one Z-native cylinder, radius (r - 0.02), height 0.8, z=-0.45 ------
# Houdini tube orient=2 is the Z axis; rad1 at -Z, rad2 at +Z. The radius links
# to the `r` parm post-collapse (placeholder constant until then). seg=10 in
# km.gen_pod -> cols=10. No phase roll: a straight cylinder of revolution has a
# phase-invariant bbox (the verify gate holds the body to +/-1e-4).
body = geo.createNode("tube", "shell")
body.setParms({"type": 1, "cap": 1, "orient": 2, "cols": 10,
               "rad1": 0.30, "rad2": 0.30, "height": 0.8, "tz": -0.45})

# --- ports + detail schema (VEX, detail mode) --------------------------------
schema = geo.createNode("attribwrangle", "schema_points")
schema.setInput(0, body)
schema.setParms({"class": 0})                              # detail (run once)
schema.parm("snippet").set(r'''
float r = chf("../r");

// ---- body group: every input prim is the placeholder cartoon ----
for (int i = 0; i < nprimitives(0); i++)
    setprimgroup(0, "body", i, 1);

// ---- port: struct_S plug, mating axis +Z (up), up +X ----
int pt = addpoint(0, {0, 0, 0});
setpointattrib(0, "N",            pt, {0, 0, 1});
setpointattrib(0, "up",           pt, {1, 0, 0});
setpointattrib(0, "port_type",    pt, "struct_S");
setpointattrib(0, "port_size",    pt, r);
setpointattrib(0, "port_gender",  pt, 1);
setpointattrib(0, "port_prio",    pt, 5);
setpointattrib(0, "port_sym",     pt, 0);
setpointattrib(0, "port_cluster", pt, "");
setpointattrib(0, "port_tags",    pt, "");
setpointgroup(0, "ports", pt, 1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "sensor_pod");
setdetailattrib(0, "generator",  "gen_pod");
// %.9g: full float32 fidelity (gen_params records full precision; %g's 6 sig
// digits would truncate below the verify gate's tolerance).
setdetailattrib(0, "gen_params",
    sprintf("{\"seed\": %d, \"r\": %.9g}", chi("../seed"), r));
setdetailattrib(0, "mass",       120.0);
setdetailattrib(0, "silhouette", 0.3);
setdetailattrib(0, "supplies",   "[]");
setdetailattrib(0, "demands",    "[]");
// The pod declares no clearance/anchor volumes, but the wrapper schema stamps
// them anyway (json.dumps([]) -> "[]", json.dumps(None) -> "null"). Match it so
// the gate PROVES the absence rather than skipping the check (attrib-presence
// guard): full parity, no silently-dropped coverage.
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True)
out.setRenderFlag(True)

# --- collapse -> digital asset -----------------------------------------------
subnet = geo.collapseIntoSubnet([body, schema, out], "part_sensor_pod")
asset = subnet.createDigitalAsset(
    name="kitmash::part_sensor_pod::1.0",
    hda_file_name=OUT,
    description="KitMash sensor pod (family sensor_pod, native interior, "
                "schema kitmash/0.6)",
    min_num_inputs=0, max_num_inputs=0)

# parms = gen_params: r (derived in Python, consumed here; drives radius and the
# port size), seed (recorded; pod geometry is otherwise seed-independent)
ptg = asset.type().definition().parmTemplateGroup()
ptg.append(hou.FloatParmTemplate(
    "r", "Radius (gen_params.r)", 1, default_value=(0.32,),
    min=0.30, max=0.345,
    help="Derived by Python (U(0.30,0.345) from seed); consume as-is. "
         "Shell radius is r-0.02; port size is r."))
ptg.append(hou.IntParmTemplate(
    "seed", "Seed (recorded; pod geometry is seed-independent)", 1,
    default_value=(0,)))
asset.type().definition().setParmTemplateGroup(ptg)

# link the shell radii to the r parm (km.gen_pod: shell radius = r - 0.02)
asset.node("shell").parm("rad1").setExpression('ch("../r") - 0.02')
asset.node("shell").parm("rad2").setExpression('ch("../r") - 0.02')

asset.type().definition().updateFromNode(asset)
asset.type().definition().save(OUT, asset)
print("saved", OUT)
