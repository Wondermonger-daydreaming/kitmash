"""KitMash -> Houdini bridge (roadmap item 5, architecture decided 2026-06-12).

Doctrine: **Python decides, VEX details.** The assembler ships DECISIONS,
not meshes. This module extracts those decisions from a finished Assembler:

  placements(a)    one record per placed part: P + orient (quaternion) +
                   generator name + gen_params — enough to rehydrate the
                   part anywhere (a Houdini part HDA, or numpy for tests)
  strut_records(a) strut segments (a->b) and adapter collars as data, not
                   baked cylinders — downstream sweeps/copies own the look
  hose_records(a)  hose polylines with ctype/dia/style — feed a Sweep SOP
  open_ports(a)    unfilled ports with full schema attrs (greeble hooks)

  rehydrate(rec)   regenerate the Part from (generator, gen_params) and
                   return (part, R, t). Used by gate 7 to PROVE the round
                   trip: rehydrated geometry must be identical to what the
                   assembler placed. The recorded gen_params double as a
                   checksum — the regenerated part must reproduce them
                   exactly (derived values like tank h are recorded at
                   creation precisely so hosts never re-run Python's RNG).

  write_geo(geo,a) the Houdini side: writes placement points, strut/collar
                   primitives, hose curves, open-port points, and the trace
                   as a detail attribute onto a hou.Geometry. Only this
                   function touches hou; everything above is numpy-only and
                   covered by test_kitmash.py gate 7.

The Python SOP that calls this lives in houdini/kitmash_assembler_sop.py.
Schema kitmash/0.6. Host-agnostic except write_geo.
"""
import inspect, json
import numpy as np
import kitmash as km

# family -> (generator name, callable). The generator name is what the
# placement point carries in s@generator; the For-Each rehydrator in
# Houdini switches on it to pick the matching part HDA.
GEN_REGISTRY = {
    "core_hull":      ("gen_hull",     km.gen_hull),
    "fuel_tank":      ("gen_tank",     km.gen_tank),
    "engine":         ("gen_engine",   km.gen_engine),
    "wing":           ("gen_wing",     km.gen_wing),
    "heavy_cannon":   ("gen_cannon",   km.gen_cannon),
    "antenna":        ("gen_antenna",  km.gen_antenna),
    "sensor_pod":     ("gen_pod",      km.gen_pod),
    "radiator":       ("gen_radiator", km.gen_radiator),
    "reactor":        ("gen_reactor",  km.gen_reactor),
    "turret":         ("gen_turret",   km.gen_turret),
    "terminator_cap": ("gen_cap",      km.gen_cap),
}
FACTIONS = {km.GUILD["name"]: km.GUILD, km.FERAL["name"]: km.FERAL}


# ------------------------------------------------------- rotation <-> quat
def quat_from_R(R):
    """3x3 rotation -> quaternion in Houdini p@orient order (x, y, z, w)."""
    R = np.asarray(R, float)
    t = np.trace(R)
    if t > 0:
        s = 2.0 * np.sqrt(1.0 + t)
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(R)))
        if i == 0:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
            w = (R[2, 1] - R[1, 2]) / s
        elif i == 1:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
            w = (R[0, 2] - R[2, 0]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
            w = (R[1, 0] - R[0, 1]) / s
    return [float(x), float(y), float(z), float(w)]


def R_from_quat(q):
    """Quaternion (x, y, z, w) -> 3x3 rotation. Inverse of quat_from_R."""
    x, y, z, w = (float(v) for v in q)
    n = np.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


# ------------------------------------------------------ decision extraction
def _commit_map(a):
    """part_id -> commit trace event (for join metadata: strain, mouths)."""
    return {e["part_id"]: e for e in a.trace
            if e.get("ev") == "commit" and "part_id" in e}


def placements(a):
    """One decision record per placed part, in commit order.

    The record is the whole contract: a host that can run the generator
    named in `generator` with the params in `gen_params`, then transform
    by (orient, P), reproduces the assembler's world geometry exactly.
    """
    cm = _commit_map(a)
    out = []
    for p in a.placed:
        ev = cm.get(p.uid, {})
        met = ev.get("metrics", {})
        out.append(dict(
            P=[float(x) for x in p.t],
            orient=quat_from_R(p.R),
            generator=GEN_REGISTRY[p.family][0],
            gen_params=json.dumps(p.gen_params, sort_keys=True),
            part_id=p.uid, family=p.family, label=p.label,
            faction=p.faction, era=int(p.era),
            mass=float(p.mass), silhouette=float(p.silhouette),
            parent_id=p.parent.uid if p.parent is not None else "",
            host_port=ev.get("host_port", ""),
            part_port=ev.get("part_port", ""),
            join_strain=float(met.get("strain", 0.0)),
        ))
    return out


def strut_records(a):
    """Strut segments + adapter collars as decisions (kitmash.strut_segs).
    kind=strut: a, b, relief, anchor. kind=collar: pos, axis, up, r, strain.
    Both carry owner (part uid) so provenance survives the trip."""
    return [dict(st) for st in a.strut_segs]


def hose_records(a):
    """Hose polylines, ready for Resample -> sag VEX -> Sweep."""
    return [dict(pts=[[float(x) for x in pt] for pt in h["pts"]],
                 kinds=list(h["kinds"]), ctype=h["ctype"],
                 dia=float(h["dia"]), style=a.fc["hose"])
            for h in a.hoses]


def open_ports(a):
    """Unfilled ports with full schema attrs — terminator/greeble hooks."""
    out = []
    for p in a.placed:
        for wpos, wN, wup, pt in p.wports:
            if pt.filled:
                continue
            out.append(dict(P=[float(x) for x in wpos],
                            N=[float(x) for x in wN],
                            up=[float(x) for x in wup],
                            port_id=pt.pid, port_type=pt.type,
                            port_size=float(pt.size), port_gender=pt.gender,
                            port_sym=pt.sym, port_tags=pt.tags,
                            owner=p.uid))
    return out


# ----------------------------------------------------------- rehydration
def rehydrate(rec, factions=None):
    """Regenerate a part from a placement record. Returns (part, R, t).

    Raises AssertionError if the regenerated gen_params differ from the
    recorded ones — the recorded dict is a checksum proving determinism.
    Generator kwargs are filtered through the generator's signature:
    derived values (tank h, pod r, ...) are recorded but not passed; the
    seed must reproduce them, and the assertion verifies it did.
    """
    factions = factions or FACTIONS
    name, fn = GEN_REGISTRY[rec["family"]]
    assert name == rec["generator"], \
        f"generator mismatch: {name} != {rec['generator']}"
    gp = json.loads(rec["gen_params"])
    accepted = set(inspect.signature(fn).parameters) - {"fc"}
    kwargs = {k: v for k, v in gp.items() if k in accepted}
    part = fn(factions[rec["faction"]], **kwargs)
    assert part.gen_params == gp, \
        f"gen_params checksum failed for {rec['part_id']}: " \
        f"{part.gen_params} != {gp}"
    return part, R_from_quat(rec["orient"]), np.array(rec["P"], float)


# ------------------------------------------------------------ Houdini side
def _hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def write_part_geo(geo, part):
    """Write ONE part, in part-local space, onto a hou.Geometry:
    cartoon body triangles (prim group `body`, v@Cd from the faction
    palette), port points (group `ports`, full schema attrs), grommet
    points + gedge polylines (group `grommets`), and the part-level
    schema as detail attributes.

    This is the interior of the generated thin-wrapper part HDAs
    (houdini/make_part_hdas.py): the HDA calls the family's own Python
    generator and hands the Part here — the round trip holds by
    construction. Assembly-time facts (part_id, join_strain, era of the
    HOST) are stamped by the rehydrator, never known here."""
    import hou
    for nm in ("port_type", "port_cluster", "port_tags", "conduit_type"):
        geo.addAttrib(hou.attribType.Point, nm, "")
    for nm in ("port_size", "conduit_size"):
        geo.addAttrib(hou.attribType.Point, nm, 0.0)
    for nm in ("port_gender", "port_prio", "port_sym", "cluster_rank"):
        geo.addAttrib(hou.attribType.Point, nm, 0)
    for nm in ("N", "up"):
        geo.addAttrib(hou.attribType.Point, nm, (0.0, 0.0, 0.0))
    geo.addAttrib(hou.attribType.Prim, "Cd", (1.0, 1.0, 1.0))

    g_body = geo.createPrimGroup("body")
    g_port = geo.createPointGroup("ports")
    g_grom = geo.createPointGroup("grommets")

    for v, f, c in part.meshes:
        rgb = _hex_rgb(c)
        pts = []
        for pos in v:
            pt = geo.createPoint()
            pt.setPosition(hou.Vector3([float(x) for x in pos]))
            pts.append(pt)
        for tri in f:
            poly = geo.createPolygon()
            for k in tri:
                poly.addVertex(pts[k])
            poly.setAttribValue("Cd", rgb)
            g_body.add(poly)

    counts = {}
    for p in part.ports:
        pt = geo.createPoint()
        pt.setPosition(hou.Vector3([float(x) for x in p.pos]))
        pt.setAttribValue("N", tuple(float(x) for x in p.N))
        pt.setAttribValue("up", tuple(float(x) for x in p.up))
        pt.setAttribValue("port_type", p.type)
        pt.setAttribValue("port_size", float(p.size))
        pt.setAttribValue("port_gender", p.gender)
        pt.setAttribValue("port_prio", p.prio)
        pt.setAttribValue("port_sym", p.sym)
        pt.setAttribValue("port_cluster", p.cluster)
        pt.setAttribValue("port_tags", p.tags)
        counts[p.cluster] = counts.get(p.cluster, 0)
        pt.setAttribValue("cluster_rank", counts[p.cluster])
        counts[p.cluster] += 1
        g_port.add(pt)

    gpts = []
    for g in part.grommets:
        pt = geo.createPoint()
        pt.setPosition(hou.Vector3([float(x) for x in g.pos]))
        pt.setAttribValue("conduit_type", g.ctype)
        pt.setAttribValue("conduit_size", float(g.size))
        g_grom.add(pt)
        gpts.append(pt)
    for i, j in part.gedges:
        poly = geo.createPolygon(is_closed=False)
        poly.addVertex(gpts[i]); poly.addVertex(gpts[j])

    for nm, val in (("family", part.family),
                    ("generator", GEN_REGISTRY[part.family][0]),
                    ("gen_params", json.dumps(part.gen_params,
                                              sort_keys=True)),
                    ("supplies", json.dumps([list(x)
                                             for x in part.supplies])),
                    ("demands", json.dumps([list(x)
                                            for x in part.demands])),
                    ("clearance_vols", json.dumps(
                        [[list(map(float, lo)), list(map(float, hi))]
                         for lo, hi in part.clearances])),
                    ("anchor_vols", json.dumps(
                        None if part.anchor_vols is None else
                        [[list(map(float, lo)), list(map(float, hi))]
                         for lo, hi in part.anchor_vols]))):
        geo.addAttrib(hou.attribType.Global, nm, "")
        geo.setGlobalAttribValue(nm, val)
    for nm, val in (("mass", float(part.mass)),
                    ("silhouette", float(part.silhouette))):
        geo.addAttrib(hou.attribType.Global, nm, 0.0)
        geo.setGlobalAttribValue(nm, val)


def rehydrate_to_geo(geo, keep_decisions=False):
    """The HEADLESS rehydrator (CI/smoke path — the For-Each + part-HDA
    network in ASSEMBLER-SOP.md is the artist path). Reads placement
    points (group `placements`) from a geometry the assembler SOP wrote,
    regenerates every part via rehydrate() — same code gate 7 proves —
    transforms it by the point's orient/P, and writes the bodies as
    faction-colored polygons. Adapter collars are baked too (single
    points can't ride a downstream PolyWire). Strut segments and hose
    curves are left as curves for wiring/sweeping downstream. Decision
    points are consumed unless keep_decisions=True."""
    import hou
    place = [pt for pt in geo.findPointGroup("placements").points()]
    collars = [pt for pt in geo.findPointGroup("collars").points()]
    geo.addAttrib(hou.attribType.Prim, "Cd", (1.0, 1.0, 1.0))
    geo.addAttrib(hou.attribType.Prim, "part_id", "")

    def bake(verts, faces, color, pid):
        rgb = _hex_rgb(color)
        pts = []
        for pos in verts:
            p = geo.createPoint()
            p.setPosition(hou.Vector3([float(x) for x in pos]))
            pts.append(p)
        for tri in faces:
            poly = geo.createPolygon()
            for k in tri:
                poly.addVertex(pts[k])
            poly.setAttribValue("Cd", rgb)
            poly.setAttribValue("part_id", pid)

    for pt in place:
        rec = {k: pt.attribValue(k) for k in
               ("family", "generator", "gen_params", "faction", "part_id")}
        rec["orient"] = list(pt.attribValue("orient"))
        rec["P"] = list(pt.position())
        part, R, t = rehydrate(rec)
        for v, f, c in part.meshes:
            bake(np.asarray(v) @ R.T + t, f, c, rec["part_id"])

    for pt in collars:
        fc = FACTIONS[geo.attribValue("faction")]
        v, f = km.cyl(pt.attribValue("r"), pt.attribValue("r"), 0.1, seg=8)
        R = km.frame(np.array(pt.attribValue("N")),
                     np.array(pt.attribValue("up")))
        bake(np.asarray(v) @ R.T + np.array(list(pt.position())), f,
             fc["accent"], "collar/" + pt.attribValue("owner"))

    if not keep_decisions:
        geo.deletePoints(place + collars)


def write_geo(geo, a, name="", plate=""):
    """Write a finished assembly onto a hou.Geometry as decisions:
    placement points (group `placements`), strut segments (prim group
    `struts`) + collar points (group `collars`), hose curves (prim group
    `hoses`), open-port points (group `open_ports`), trace + stats as
    detail attributes. Houdini-only; everything it serializes comes from
    the host-agnostic extractors above (gate 7 covers those)."""
    import hou
    recs, struts, hoses, ports = (placements(a), strut_records(a),
                                  hose_records(a), open_ports(a))

    # --- attribute declarations -------------------------------------------
    geo.addAttrib(hou.attribType.Point, "orient", (0.0, 0.0, 0.0, 1.0))
    for nm in ("generator", "gen_params", "part_id", "family", "label",
               "faction", "parent_id", "host_port", "part_port",
               "port_id", "port_type", "port_tags", "owner", "kind",
               "anchor", "ctype", "hose_style"):
        geo.addAttrib(hou.attribType.Point, nm, "")
    for nm in ("mass", "silhouette", "join_strain", "port_size",
               "relief", "r", "strain", "dia", "width"):
        geo.addAttrib(hou.attribType.Point, nm, 0.0)
    for nm in ("era", "port_gender", "port_sym", "vol"):
        geo.addAttrib(hou.attribType.Point, nm, 0)
    for nm in ("N", "up"):
        geo.addAttrib(hou.attribType.Point, nm, (0.0, 0.0, 0.0))
    # gen_params doubled as typed gp_* attrs so HDA parms can use plain
    # point() expressions — no JSON parsing inside the For-Each loop.
    gp_keys = {}
    for rec in recs:
        for k, v in json.loads(rec["gen_params"]).items():
            gp_keys[k] = int if isinstance(v, int) else float
    for k, typ in gp_keys.items():
        geo.addAttrib(hou.attribType.Point, "gp_" + k,
                      0 if typ is int else 0.0)

    g_place = geo.createPointGroup("placements")
    g_open = geo.createPointGroup("open_ports")
    g_collar = geo.createPointGroup("collars")
    g_strut = geo.createPrimGroup("struts")
    g_hose = geo.createPrimGroup("hoses")

    def setattrs(pt, d, skip=()):
        for k, v in d.items():
            if k in ("P",) or k in skip:
                continue
            pt.setAttribValue(k, v)

    # --- placement points --------------------------------------------------
    for rec in recs:
        pt = geo.createPoint()
        pt.setPosition(hou.Vector3(rec["P"]))
        setattrs(pt, rec)
        for k, v in json.loads(rec["gen_params"]).items():
            pt.setAttribValue("gp_" + k, v)
        g_place.add(pt)

    # --- struts + collars ---------------------------------------------------
    for st in struts:
        if st["kind"] == "strut":
            poly = geo.createPolygon(is_closed=False)
            for pos in (st["a"], st["b"]):
                pt = geo.createPoint()
                pt.setPosition(hou.Vector3(pos))
                pt.setAttribValue("kind", "strut")
                pt.setAttribValue("owner", st["owner"])
                pt.setAttribValue("anchor", st["anchor"])
                pt.setAttribValue("relief", st["relief"])
                # v0.8 anchorable-surface provenance: which declared volume
                # took the weld (-1 = legacy whole-part AABB). Dropping it
                # on the Houdini side would lose the only record of WHERE a
                # strut may grunge/dress against a fragile surface.
                pt.setAttribValue("vol", int(st.get("vol", -1)))
                pt.setAttribValue("width", 0.06)
                poly.addVertex(pt)
            g_strut.add(poly)
        else:  # collar
            pt = geo.createPoint()
            pt.setPosition(hou.Vector3(st["pos"]))
            pt.setAttribValue("kind", "collar")
            pt.setAttribValue("owner", st["owner"])
            pt.setAttribValue("N", st["axis"])
            pt.setAttribValue("up", st["up"])
            pt.setAttribValue("r", st["r"])
            pt.setAttribValue("strain", st["strain"])
            g_collar.add(pt)

    # --- hoses ---------------------------------------------------------------
    for h in hoses:
        poly = geo.createPolygon(is_closed=False)
        for pos in h["pts"]:
            pt = geo.createPoint()
            pt.setPosition(hou.Vector3(pos))
            pt.setAttribValue("ctype", h["ctype"])
            pt.setAttribValue("hose_style", h["style"])
            pt.setAttribValue("dia", h["dia"])
            pt.setAttribValue("width", h["dia"] * 0.5)   # Sweep radius
            poly.addVertex(pt)
        g_hose.add(poly)

    # --- open ports ------------------------------------------------------------
    for op in ports:
        pt = geo.createPoint()
        pt.setPosition(hou.Vector3(op["P"]))
        setattrs(pt, op)
        g_open.add(pt)

    # --- detail provenance ------------------------------------------------------
    for nm, val in (("kitmash_schema", "kitmash/0.6"),
                    ("ship_name", name), ("plate", plate),
                    ("faction", a.fc["name"]),
                    ("trace", json.dumps(a.trace)),
                    ("lineage", json.dumps(getattr(a, "lineage", {}))),
                    ("stats", json.dumps(dict(
                        parts=len(a.placed),
                        mass=int(sum(p.mass for p in a.placed)),
                        struts=len(a.struts), hoses=len(a.hoses))))):
        geo.addAttrib(hou.attribType.Global, nm, "")
        geo.setGlobalAttribValue(nm, val)
