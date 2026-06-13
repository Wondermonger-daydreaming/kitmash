"""make_tank_hda.py — build kitmash::part_fuel_tank::1.0 (NATIVE interior).

Run:  /opt/hfs21.0.729/bin/hython houdini/make_tank_hda.py [out.hda]
      then  /opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py fuel_tank

Builds the network specified in kitmash_part_tank.md, collapses it into
a subnet, converts to a digital asset with parms (h, seed), and saves
houdini/kitmash_part_fuel_tank.hda.

TYPE-NAME FIX (v0.12, 2026-06-13): this asset was originally named
`kitmash::part_tank::1.0` — a legacy name from when the tank was "the first
part HDA (deliverable b)," before the GEN_REGISTRY key settled on `fuel_tank`.
The generalized gate `verify_native_hda.py` looks up the type by registry key
(`kitmash::part_fuel_tank::1.0`), so under the legacy name the unified gate was
silently exercising the WRAPPER, not this native interior (the native was
reachable only via the standalone legacy `verify_tank_hda.py`). Renamed to
`kitmash::part_fuel_tank::1.0` so the native interior wins over the wrapper of
the same type (installed last) under the unified gate — same pattern as engine.
"""
import os, sys
import hou

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "kitmash_part_fuel_tank.hda")

obj = hou.node("/obj")
geo = obj.createNode("geo", "build_part_fuel_tank")

# --- body: drum (axis +X, centered z=0.55) + mounting skirt -----------------
tube = geo.createNode("tube", "drum")
tube.setParms({"type": 1, "cap": 1, "orient": 0,          # poly, capped, X
               "rad1": 0.55, "rad2": 0.55, "cols": 14,
               "tz": 0.55})
tube.parm("height").set(2.4)                               # re-linked below

# phase-align the 14-gon with kitmash.cyl: km.cyl's vertex 0 sits at local
# +x -> world +z (frame([1,0,0],[0,0,1])), while Houdini's X-oriented tube
# starts its cross-section at +y. A 90° roll about the drum axis matches
# the cartoon's bbox exactly (verify gate holds the body to ±1e-4).
phase = geo.createNode("xform", "drum_phase")
phase.setInput(0, tube)
phase.setParms({"rx": 90.0, "px": 0.0, "py": 0.0, "pz": 0.55})

skirt = geo.createNode("box", "skirt")
skirt.setParms({"sizex": 0.7, "sizey": 0.7, "sizez": 0.12, "tz": 0.05})

body = geo.createNode("merge", "body_merge")
body.setInput(0, phase); body.setInput(1, skirt)

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
int gs[] = array(g0, g1);
foreach (int g; gs) {
    setpointattrib(0, "conduit_type", g, "fuel");
    setpointattrib(0, "conduit_size", g, 0.1);
    setpointgroup(0, "grommets", g, 1);
}
addprim(0, "polyline", g0, g1);

// ---- part-level schema (detail) ----
setdetailattrib(0, "family",     "fuel_tank");
setdetailattrib(0, "generator",  "gen_tank");
// %.9g: full float32 fidelity (gen_params now records full precision;
// %g's 6 sig digits would truncate below the verify gate's tolerance)
setdetailattrib(0, "gen_params",
    sprintf("{\"h\": %.9g, \"seed\": %d}", h, chi("../seed")));
setdetailattrib(0, "mass",       900.0 * h / 2.4);
setdetailattrib(0, "silhouette", 0.45);
setdetailattrib(0, "supplies",   "[[\"fuel\", 3.0]]");
setdetailattrib(0, "demands",    "[]");
// The tank declares no clearance/anchor volumes, but the wrapper schema stamps
// them anyway ("[]" / "null"). Match it so the gate PROVES the absence rather
// than skipping the check (attrib-presence guard): full parity, no dropped
// coverage.
setdetailattrib(0, "clearance_vols", "[]");
setdetailattrib(0, "anchor_vols",    "null");
''')

out = geo.createNode("output", "OUT")
out.setInput(0, schema)
out.setDisplayFlag(True); out.setRenderFlag(True)

# --- collapse -> digital asset ----------------------------------------------
subnet = geo.collapseIntoSubnet(
    [tube, phase, skirt, body, schema, out], "part_fuel_tank")
asset = subnet.createDigitalAsset(
    name="kitmash::part_fuel_tank::1.0",
    hda_file_name=OUT,
    description="KitMash fuel tank (family fuel_tank, native interior, "
                "schema kitmash/0.6)",
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
