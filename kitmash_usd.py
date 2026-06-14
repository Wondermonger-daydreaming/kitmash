"""KitMash -> USD bridge (roadmap item 4). The format's second host.

Houdini was host #1 (v0.7, live-verified under hython). USD is host #2.
A schema that survives two hosts is a schema — and the schema was *designed*
host-agnostic (the v0.4 fields are already attribute-shaped), so this port,
like the Houdini one, ships DECISIONS, not baked meshes.

Doctrine held here exactly as in kitmash_houdini.py:

  * The host-agnostic extractors are SINGLE-SOURCED. placements(),
    strut_records(), hose_records(), open_ports() are imported from
    kitmash_houdini — they are already proven by test_kitmash.py gate 7.
    This module adds NO new extraction; it only serializes.
  * Only `write_usd()` and `read_ship()` touch `pxr`. Everything they
    serialize comes from the tested extractors.

Provenance rides **`primvars:kitmash:*`** — idiomatic USD namespaced
primvars (constant interpolation), so the recipe inherits from each part
Xform down to its child geometry and is queryable at the mesh.

The decision layer is the truth, so it is stored at full fidelity:
gen_params, mass, silhouette, join_strain, and every strut/hose/port
coordinate are authored as **float64** primvars/ops -> the round trip is
*bit-exact*, not float32-honest. USD lets the second host be tighter than
the first; the verify gate's tolerances say so honestly.

The cartoon body Mesh is the "cached opinion": USD `point3f` (float32) by
schema, present only so `usdview` can show a ship. The primvars are the
truth; the mesh is a convenience.

K2 — SHARED PART-ASSET LIBRARY (roadmap item 4 follow-up).
Each family's *prototype* cartoon body lives ONCE, in usd/assets/<family>.usda,
authored from a deterministic canonical cook gen_<family>(GUILD, seed=0) — the
USD twin of the part HDA. Every ship's part Xform `references` its family asset
instead of re-embedding the mesh; re-embedding the same body in every ship was
the flat-dump anti-pattern. What rides the INSTANCE (never the asset):
  * ALL provenance primvars (gen_params, mass, silhouette, join_strain,
    anchor_faces, face_cls, typed kitmash:gp:*) — the TRUTH (inv 7);
  * the P/orient xform ops — the placement;
  * displayColor as an OVERRIDE — color is faction-specific (GUILD vs FERAL
    share the geometry, differ only in colour), so color belongs to the
    instance, not the shared prototype.
The asset holds GEOMETRY ONLY (faction-independent — proven: no generator
branches its mesh on faction). Per-instance gen_params variation (engine size,
wing span, tank h, ...) is NOT in the shared prototype mesh; it is the truth on
the primvars, and any host may re-render it via rehydrate(). The verify gate's
cook test proves both halves honestly (see verify_usd.py).

Run the gate:  .venv/bin/python verify_usd.py            (usd-core, no license)
               /opt/hfs21.0.729/bin/hython verify_usd.py (Houdini's own pxr)
Build the fleet: .venv/bin/python make_fleet_usd.py
Schema string: kitmash/0.6 (same as the Houdini export; USD is additive).
"""
import json

import numpy as np
from pxr import Usd, UsdGeom, Sdf, Gf, Vt, Tf

import os

import kitmash as km
# Single-sourced, gate-7-proven extractors. Do NOT reimplement these here.
from kitmash_houdini import (placements, strut_records, hose_records,
                             open_ports, rehydrate, R_from_quat,
                             GEN_REGISTRY)

NS = "kitmash"
SCHEMA = "kitmash/0.6"

# The faction the canonical prototype is cooked under. Geometry is
# faction-independent (no generator branches its mesh on faction; only colour
# differs), so any faction yields the same prototype body — GUILD is the
# arbitrary-but-fixed canon. Color is NOT baked into the asset (it rides the
# instance as a displayColor override), so this choice never leaks colour.
CANON_FC = km.GUILD


# --------------------------------------------------------- canonical prototype
def canonical_part(family):
    """The deterministic prototype Part for a family — the asset library's
    ground truth. gen_<family>(GUILD, seed=0) with all-default kwargs. Used
    BOTH to author usd/assets/<family>.usda AND by the gate's cook test to
    prove the reference arc resolves to the right body (a broken arc, or an
    asset pointing at the wrong family, fails the <=1e-4 compare)."""
    _, fn = GEN_REGISTRY[family]
    return fn(CANON_FC)


def canonical_points(family):
    """Flat (N,3) float64 array of the prototype body's LOCAL points, in the
    same vertex order _bake_part_mesh emits. The cook test's ground truth for
    'the reference resolved to this exact prototype'."""
    pts = []
    for v, f, c in canonical_part(family).meshes:
        pts.extend([float(x) for x in pos] for pos in v)
    return np.array(pts, float)


# Families that actually appear in the canonical fleet (built lazily so a
# caller may author a subset). Authored as ASCII .usda, one per family.
def fleet_families(ships):
    """Every family placed across `ships`, in first-seen order — the set of
    assets the library must author."""
    seen = []
    for _name, a, _off, _plate in ships:
        for placed in a.placed:
            if placed.family not in seen:
                seen.append(placed.family)
    return seen


# --------------------------------------------------------------- name hygiene
# Greek transliteration: MakeValidIdentifier alone collapses every non-ascii
# letter to '_', so "GS-α" and "GS-β" would both become "GS___" and collide on
# one prim path. Transliterating first keeps tokens unique AND readable
# (GS_alpha), and derivable from the name alone (driver and gate stay in sync).
_TRANSLIT = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "ζ": "zeta", "η": "eta", "θ": "theta", "ι": "iota", "κ": "kappa",
    "λ": "lambda", "μ": "mu", "ν": "nu", "ξ": "xi", "ο": "omicron",
    "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau", "υ": "upsilon",
    "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
}


def _ident(s, fallback="x"):
    """USD prim name from an arbitrary id (part_id carries '#'; ship names
    carry Greek). The real id is preserved verbatim in the kitmash primvars;
    this only sanitizes the *path token*."""
    s = "".join(_TRANSLIT.get(ch, ch) for ch in str(s))
    out = Tf.MakeValidIdentifier(s)
    return out or fallback


def _hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ------------------------------------------------------------- primvar helpers
# Map a Python scalar to (Sdf type, coerced value). Floats -> Double for an
# exact round trip; bools excluded from the int branch (bool is an int in py).
def _scalar_type(v):
    if isinstance(v, bool):
        return Sdf.ValueTypeNames.Bool, v
    if isinstance(v, int):
        return Sdf.ValueTypeNames.Int, int(v)
    if isinstance(v, float):
        return Sdf.ValueTypeNames.Double, float(v)
    return Sdf.ValueTypeNames.String, str(v)


def _pv(api, name, sdf_type, value):
    pv = api.CreatePrimvar(f"{NS}:{name}", sdf_type,
                           UsdGeom.Tokens.constant)
    pv.Set(value)
    return pv


def _pv_scalar(api, name, value):
    t, v = _scalar_type(value)
    _pv(api, name, t, v)


def _pv_vec3d(api, name, v):
    _pv(api, name, Sdf.ValueTypeNames.Double3, Gf.Vec3d(*(float(x) for x in v)))


def _get_pv(prim, name):
    pv = UsdGeom.PrimvarsAPI(prim).GetPrimvar(f"{NS}:{name}")
    return pv.Get() if pv and pv.HasValue() else None


def _provenance(api, rec, skip):
    """Author every scalar field of an extractor record as a kitmash primvar."""
    for k, v in rec.items():
        if k in skip:
            continue
        _pv_scalar(api, k, v)


# --------------------------------------------------------------- geometry bake
def _proto_prim_name(family):
    """Top prim name inside usd/assets/<family>.usda (and the asset's
    defaultPrim). Derived from the family alone so authoring and the gate stay
    in sync."""
    return _ident(family, fallback="Part")


def _bake_proto_mesh(stage, parent_path, part):
    """Author the PROTOTYPE body Mesh as a child `geo` under parent_path.
    GEOMETRY ONLY — no displayColor (color is faction-specific and rides the
    instance as an override). point3f (float32) — the cached opinion."""
    pts, counts, idx = [], [], []
    base = 0
    for v, f, c in part.meshes:
        for pos in v:
            pts.append(Gf.Vec3f(*(float(x) for x in pos)))
        for tri in f:
            counts.append(len(tri))
            idx.extend(int(base + k) for k in tri)
        base += len(v)
    mesh = UsdGeom.Mesh.Define(stage, parent_path.AppendChild("geo"))
    mesh.CreatePointsAttr(Vt.Vec3fArray(pts))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(counts))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    return mesh


def write_asset_library(assets_dir, families):
    """Author one ASCII usd/assets/<family>.usda per family. Each holds a
    single referenceable Xform (the family prototype), defaultPrim-marked so a
    bare `references = @<family>.usda@` (no prim path) resolves to it. The body
    is the deterministic canonical_part(family) cook — the USD twin of the part
    HDA, and the gate's ground truth. Returns {family: abspath}."""
    os.makedirs(assets_dir, exist_ok=True)
    out = {}
    for family in families:
        path = os.path.join(assets_dir, f"{family}.usda")
        if os.path.exists(path):
            os.remove(path)            # CreateNew refuses to overwrite
        astage = Usd.Stage.CreateNew(path)
        UsdGeom.SetStageUpAxis(astage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(astage, 1.0)
        proto = UsdGeom.Xform.Define(
            astage, Sdf.Path(f"/{_proto_prim_name(family)}"))
        pp = proto.GetPrim()
        astage.SetDefaultPrim(pp)
        pp.SetCustomDataByKey("kitmash:schema_version", SCHEMA)
        pp.SetCustomDataByKey("kitmash:family", family)
        _bake_proto_mesh(astage, proto.GetPath(), canonical_part(family))
        astage.GetRootLayer().Save()
        out[family] = os.path.abspath(path)
    return out


def _reference_family(xf, family, asset_uri):
    """Reference the family's part-asset onto an instance Xform. asset_uri is
    the layer identifier authored on the reference arc; the asset's defaultPrim
    supplies the prim (so the instance's child `geo` composes through the arc).
    """
    xf.GetPrim().GetReferences().AddReference(asset_uri)


def _author_face_color(prim, part):
    """Faction color as a displayColor OVERRIDE on the instance's referenced
    `geo` Mesh. Per-mesh-face uniform colors (a part may mix accent/dark on its
    sub-bodies). Authored at the instance so the shared prototype stays
    colorless and two factions can reference the same asset."""
    colors = []
    for v, f, c in part.meshes:
        rgb = _hex_rgb(c)
        colors.extend(Gf.Vec3f(*rgb) for _tri in f)
    geo = UsdGeom.Mesh(prim.GetChild("geo"))
    dc = geo.CreateDisplayColorPrimvar(UsdGeom.Tokens.uniform)
    dc.Set(Vt.Vec3fArray(colors))


def _linear_curve(stage, path, points, width):
    """A linear BasisCurves (struts, hoses) — viewer geometry. The exact
    decision coordinates ride double primvars; these points are float32."""
    crv = UsdGeom.BasisCurves.Define(stage, path)
    crv.CreateTypeAttr(UsdGeom.Tokens.linear)
    crv.CreateCurveVertexCountsAttr(Vt.IntArray([len(points)]))
    crv.CreatePointsAttr(Vt.Vec3fArray(
        [Gf.Vec3f(*(float(x) for x in p)) for p in points]))
    crv.CreateWidthsAttr(Vt.FloatArray([float(width)] * len(points)))
    crv.SetWidthsInterpolation(UsdGeom.Tokens.vertex)
    return crv


# ------------------------------------------------------------------ write side
def write_usd(stage, a, ship_path, name="", plate="", offset=(0.0, 0.0, 0.0),
              asset_uri=None):
    """Author one finished assembly under `ship_path` on `stage`. The ONLY
    function (with read_ship) that touches pxr; every value it writes comes
    from the host-agnostic extractors. Returns the ship Xform prim.

    `asset_uri(family) -> str` resolves a family to the layer identifier its
    part-asset lives at (K2 shared library). Each part Xform `references` that
    asset (its child `geo` composes through the arc) instead of re-embedding
    the body. If asset_uri is None the bodies are NOT embedded — only a host
    that pairs write_usd with write_asset_library gets viewable geometry; the
    decision layer (the truth) is authored regardless.

    Layout:
      <ship>            Xform  (xformOp:translate = plate offset; kitmash:* meta)
        Parts/<part>    Xform  (translate+orient = the placement; provenance
                                primvars; typed kitmash:gp:*; references the
                                family part-asset -> composed child Mesh `geo`;
                                faction displayColor override on that geo)
        Struts/strut_i  BasisCurves (+ exact double a/b primvars + relief/...)
        Struts/collar_i Xform  (translate=pos; axis/up/r/strain primvars)
        Hoses/hose_i    BasisCurves (+ exact double pts primvar + ctype/dia)
        OpenPorts/port_i Xform  (translate=P; full port schema primvars)
    """
    recs = placements(a)
    struts = strut_records(a)
    hoses = hose_records(a)
    ports = open_ports(a)

    ship = UsdGeom.Xform.Define(stage, ship_path)
    ship.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(
        Gf.Vec3d(*(float(x) for x in offset)))
    sp = ship.GetPrim()
    sapi = UsdGeom.PrimvarsAPI(sp)
    _pv(sapi, "schema", Sdf.ValueTypeNames.String, SCHEMA)
    _pv(sapi, "ship_name", Sdf.ValueTypeNames.String, name)
    _pv(sapi, "plate", Sdf.ValueTypeNames.String, plate)
    _pv(sapi, "faction", Sdf.ValueTypeNames.String, a.fc["name"])
    _pv(sapi, "trace", Sdf.ValueTypeNames.String, json.dumps(a.trace))
    _pv(sapi, "lineage", Sdf.ValueTypeNames.String,
        json.dumps(getattr(a, "lineage", {})))
    _pv(sapi, "stats", Sdf.ValueTypeNames.String, json.dumps(dict(
        parts=len(a.placed), mass=int(sum(p.mass for p in a.placed)),
        struts=len(a.struts), hoses=len(a.hoses))))

    parts_scope = UsdGeom.Scope.Define(stage, ship_path.AppendChild("Parts"))
    pp = parts_scope.GetPath()
    # a.placed is in the same order placements() iterates -> parts pair up.
    for i, (rec, placed) in enumerate(zip(recs, a.placed)):
        path = pp.AppendChild(f"part{i}_{_ident(rec['part_id'])}")
        xf = UsdGeom.Xform.Define(stage, path)
        # order [translate, orient] -> world = T * R * local = R@local + t
        xf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(
            Gf.Vec3d(*(float(x) for x in rec["P"])))
        x, y, z, w = rec["orient"]
        xf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(
            Gf.Quatd(float(w), Gf.Vec3d(float(x), float(y), float(z))))
        api = UsdGeom.PrimvarsAPI(xf.GetPrim())
        # P/orient ride the xform ops (the geometry-driving attrs); the rest
        # of the decision record rides provenance primvars.
        _provenance(api, rec, skip=("P", "orient"))
        # gen_params doubled as typed kitmash:gp:* (parallels the Houdini
        # gp_* attrs) so a DCC can bind without parsing JSON.
        for k, v in json.loads(rec["gen_params"]).items():
            _pv_scalar(api, f"gp:{k}", v)
        # P3: anchor_faces — face-level weld patches as a JSON string primvar.
        # Each face: {c:[3f], n:[3f], u:[3f], hu:f, hv:f, cls:i}.
        # None = no declared faces (fall back to anchor_vols; whole-AABB for
        # parts that declare neither). This is LOCAL-space (part frame) so any
        # replacement asset inherits the exact same face geometry.
        af = placed.anchor_faces
        _pv(api, "anchor_faces", Sdf.ValueTypeNames.String,
            "null" if af is None else json.dumps(
                [{"c": [float(x) for x in f["c"]],
                  "n": [float(x) for x in f["n"]],
                  "u": [float(x) for x in f["u"]],
                  "hu": float(f["hu"]),
                  "hv": float(f["hv"]),
                  "cls": int(f["cls"])}
                 for f in af]))
        # K2: reference the family part-asset (its `geo` composes through the
        # arc) instead of re-embedding the body. Faction color is an override
        # on the composed geo — the shared prototype stays colorless.
        if asset_uri is not None:
            _reference_family(xf, placed.family, asset_uri(placed.family))
            _author_face_color(xf.GetPrim(), placed)

    struts_scope = UsdGeom.Scope.Define(stage, ship_path.AppendChild("Struts"))
    stp = struts_scope.GetPath()
    si = ci = 0
    for st in struts:
        if st["kind"] == "strut":
            path = stp.AppendChild(f"strut{si}")
            crv = _linear_curve(stage, path, (st["a"], st["b"]), 0.06)
            api = UsdGeom.PrimvarsAPI(crv.GetPrim())
            _pv(api, "kind", Sdf.ValueTypeNames.String, "strut")
            _pv(api, "owner", Sdf.ValueTypeNames.String, st["owner"])
            _pv(api, "anchor", Sdf.ValueTypeNames.String, st["anchor"])
            _pv(api, "relief", Sdf.ValueTypeNames.Double, float(st["relief"]))
            _pv(api, "vol", Sdf.ValueTypeNames.Int, int(st.get("vol", -1)))
            # P3: face_cls = anchor class that took the weld (-1 = AABB/legacy)
            fc_raw = st.get("face_cls")
            _pv(api, "face_cls", Sdf.ValueTypeNames.Int,
                int(fc_raw) if fc_raw is not None else -1)
            _pv_vec3d(api, "a", st["a"])
            _pv_vec3d(api, "b", st["b"])
            si += 1
        else:  # collar
            path = stp.AppendChild(f"collar{ci}")
            xf = UsdGeom.Xform.Define(stage, path)
            xf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(
                Gf.Vec3d(*(float(x) for x in st["pos"])))
            api = UsdGeom.PrimvarsAPI(xf.GetPrim())
            _pv(api, "kind", Sdf.ValueTypeNames.String, "collar")
            _pv(api, "owner", Sdf.ValueTypeNames.String, st["owner"])
            _pv(api, "r", Sdf.ValueTypeNames.Double, float(st["r"]))
            _pv(api, "strain", Sdf.ValueTypeNames.Double, float(st["strain"]))
            _pv_vec3d(api, "axis", st["axis"])
            _pv_vec3d(api, "up", st["up"])
            _pv_vec3d(api, "pos", st["pos"])
            ci += 1

    hoses_scope = UsdGeom.Scope.Define(stage, ship_path.AppendChild("Hoses"))
    hp = hoses_scope.GetPath()
    for i, h in enumerate(hoses):
        path = hp.AppendChild(f"hose{i}")
        crv = _linear_curve(stage, path, h["pts"], float(h["dia"]) * 0.5)
        api = UsdGeom.PrimvarsAPI(crv.GetPrim())
        _pv(api, "ctype", Sdf.ValueTypeNames.String, h["ctype"])
        _pv(api, "hose_style", Sdf.ValueTypeNames.String, h["style"])
        _pv(api, "dia", Sdf.ValueTypeNames.Double, float(h["dia"]))
        _pv(api, "kinds", Sdf.ValueTypeNames.StringArray,
            Vt.StringArray([str(k) for k in h["kinds"]]))
        _pv(api, "pts", Sdf.ValueTypeNames.Double3Array,
            Vt.Vec3dArray([Gf.Vec3d(*(float(x) for x in p))
                           for p in h["pts"]]))

    ports_scope = UsdGeom.Scope.Define(stage,
                                       ship_path.AppendChild("OpenPorts"))
    opp = ports_scope.GetPath()
    for i, op in enumerate(ports):
        path = opp.AppendChild(f"port{i}_{_ident(op['port_id'])}")
        xf = UsdGeom.Xform.Define(stage, path)
        xf.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(
            Gf.Vec3d(*(float(x) for x in op["P"])))
        api = UsdGeom.PrimvarsAPI(xf.GetPrim())
        _provenance(api, op, skip=("P", "N", "up"))
        _pv_vec3d(api, "N", op["N"])
        _pv_vec3d(api, "up", op["up"])
    return sp


def export_fleet(ships, path, assets_subdir="assets"):
    """ships: list of (name, assembler, offset, plate). Writes an ASCII
    .usda (inspectable, git-diffable) PLUS the shared part-asset library under
    <path's dir>/<assets_subdir>/. Each ship part references its family asset
    by a RELATIVE uri (`assets/<family>.usda`) so the fleet + library are a
    relocatable bundle. Returns the stage."""
    path = str(path)
    out_dir = os.path.dirname(os.path.abspath(path))
    assets_dir = os.path.join(out_dir, assets_subdir)
    families = fleet_families(ships)
    write_asset_library(assets_dir, families)
    # Relative asset uri keeps the .usda relocatable and the diff readable.
    def asset_uri(family):
        return f"./{assets_subdir}/{family}.usda"

    stage = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    fleet = UsdGeom.Scope.Define(stage, "/Fleet")
    stage.SetDefaultPrim(fleet.GetPrim())
    fleet.GetPrim().SetCustomDataByKey("kitmash:schema_version", SCHEMA)
    for name, a, offset, plate in ships:
        token = _ident(name.split()[0])
        write_usd(stage, a, Sdf.Path(f"/Fleet/{token}"),
                  name=name, plate=plate, offset=offset, asset_uri=asset_uri)
    stage.GetRootLayer().Save()
    return stage


# ------------------------------------------------------------------- read side
def read_ship(stage, ship_path):
    """Inverse of write_usd's decision layer: recover one record dict per
    placed part, shaped like placements(), reading from the authored xform
    ops + kitmash primvars. Used by verify_usd.py to prove the round trip."""
    parts_prim = stage.GetPrimAtPath(f"{ship_path}/Parts")
    out = []
    # Children are named part{i}_... -> sort by that integer to match order.
    kids = sorted(parts_prim.GetChildren(),
                  key=lambda p: int(p.GetName().split("_")[0][4:]))
    for prim in kids:
        ops = {op.GetOpType(): op for op in
               UsdGeom.Xformable(prim).GetOrderedXformOps()}
        t = ops[UsdGeom.XformOp.TypeTranslate].Get()
        q = ops[UsdGeom.XformOp.TypeOrient].Get()
        im = q.GetImaginary()
        rec = dict(
            P=[t[0], t[1], t[2]],
            orient=[im[0], im[1], im[2], q.GetReal()],
        )
        for k in ("generator", "gen_params", "part_id", "family", "label",
                  "faction", "parent_id", "host_port", "part_port"):
            rec[k] = _get_pv(prim, k)
        rec["era"] = _get_pv(prim, "era")
        for k in ("mass", "silhouette", "join_strain"):
            rec[k] = _get_pv(prim, k)
        # P3: recover anchor_faces JSON string; None if the primvar is absent or "null"
        af_raw = _get_pv(prim, "anchor_faces")
        rec["anchor_faces"] = None if (af_raw is None or af_raw == "null") \
            else json.loads(af_raw)
        out.append(rec)
    return out


def read_local_to_world(part_prim):
    """The part's local (ship-relative) transform as a 4x4 — used by the gate's
    cook test: apply to the local mesh and compare to assembler world geometry,
    so a wrong-handed orient quaternion cannot pass behind a green provenance
    round trip."""
    m = UsdGeom.Xformable(part_prim).GetLocalTransformation()
    return m[0] if isinstance(m, tuple) else m   # binding returns bare Matrix4d
