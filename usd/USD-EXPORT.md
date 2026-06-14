# KitMash → USD export (roadmap item 4) — the contract

USD is **host #2**. Houdini was the first host to confirm the schema (v0.7,
live under hython); USD is the second. *A schema that survives two hosts is a
schema* — and the schema was designed host-agnostic, so this port, like the
Houdini one, ships **decisions, not baked meshes**.

The primvar schema below **is the brief**: anything reading a KitMash `.usd`
recovers the full provenance from `primvars:kitmash:*`, and anything composing
the part xform against a part asset reproduces the assembler's geometry.

## Files

| File | Role |
|------|------|
| `kitmash_usd.py` | The bridge. Reuses the **gate-7-proven** extractors (`placements`, `strut_records`, `hose_records`, `open_ports` from `kitmash_houdini`); only `write_usd()` / `read_ship()` touch `pxr`. |
| `make_fleet_usd.py` | Rebuilds the canonical 5-ship fleet (same seeds/briefs as `kitmash.py __main__`) → `usd/kitmash_fleet.usda`. |
| `verify_usd.py` | The acceptance gate. Round-trips every ship and runs the **cook test**. Exit-coded. |
| `usd/kitmash_fleet.usda` | The committed artifact — ASCII, git-diffable, the USD twin of `fleet.json`. |

## Run

```sh
# build the fleet
.venv/bin/python make_fleet_usd.py            # usd-core (no license)
/opt/hfs21.0.729/bin/hython make_fleet_usd.py  # Houdini's own pxr

# prove the round trip (runs in EITHER runtime — 810 checks)
.venv/bin/python verify_usd.py
/opt/hfs21.0.729/bin/hython verify_usd.py
```

The venv path needs `usd-core` (`.venv/bin/pip install usd-core`, 26.5 here).
No Houdini license is required for the venv gate — the Gate-7 virtue carried to
the second host. The hython path needs nothing extra (Houdini ships `pxr`).

## Stage layout

```
/Fleet                       Scope   (customData kitmash:schema_version)
  /GS_alpha                  Xform   xformOp:translate = plate offset
                                     primvars:kitmash:{ship_name,plate,faction,
                                       schema,trace,lineage,stats}
    /Parts/part{i}_<id>      Xform   xformOp:translate + xformOp:orient  ← the placement
                                     primvars:kitmash:{part_id,family,generator,
                                       gen_params,label,faction,era,mass,
                                       silhouette,parent_id,host_port,part_port,
                                       join_strain}
                                     primvars:kitmash:gp:<key>           ← typed gen_params
                                     primvars:kitmash:anchor_faces       ← P3 face patches (JSON string)
      /geo                   Mesh    faction-colored cartoon (the cached opinion)
    /Struts/strut{i}         BasisCurves  kitmash:{owner,anchor,relief,vol,face_cls,a,b}
    /Struts/collar{i}        Xform        kitmash:{owner,r,strain,axis,up,pos}
    /Hoses/hose{i}           BasisCurves  kitmash:{ctype,hose_style,dia,kinds,pts}
    /OpenPorts/port{i}_<id>  Xform        kitmash:{port_id,port_type,port_size,
                                            port_gender,port_sym,port_tags,owner,N,up}
```

## Contract clauses (violate these and the round trip is a lie)

1. **The extractors are single-sourced.** `kitmash_usd` imports `placements`
   et al. from `kitmash_houdini`. There is no second copy of the extraction
   logic to drift. If the decision shape changes, it changes in one place and
   both hosts follow.

2. **`primvars:kitmash:*`, constant interpolation.** Provenance rides
   namespaced primvars so it *inherits* from each part Xform down to its child
   geometry — queryable at the mesh, which is where a renderer or a catalogue
   sweep asks. `primvars:` is USD's own namespace; `kitmash:` is ours inside it.

3. **The decision layer is float64 — bit-exact.** `gen_params` (string **and**
   typed `gp:*`), `mass`, `silhouette`, `join_strain`, `P`, `orient`, and every
   strut/collar/hose/port coordinate are authored as `double`/`quatd`. The
   round trip is bit-exact (verified through `.usda` ASCII serialization, max
   error 0.0), so the gate's tolerance is `1e-9`, **not** the float32-honest
   `5e-7` the Houdini HDA layer needed. USD lets the second host be tighter; a
   tolerance encodes a claim about storage, and `double` storage is exact.

4. **The mesh is the cached opinion.** `/geo` is `point3f` (float32) per the
   `UsdGeom.Mesh` schema, faction-colored via `displayColor`. It exists so
   `usdview` shows a ship. *The primvars are the truth; the mesh is a
   convenience.* The artist path (a follow-up) replaces `/geo` with a
   `references`/`payload` to a part-asset USD — the USD twin of the part HDA —
   and the `kitmash:gp:*` primvars drive its parameters.

5. **The cook test is mandatory.** `verify_usd.py` composes each part's
   authored `xformOp:translate`+`orient` against the **rehydrated local mesh**
   and compares to the assembler's **world** geometry (≤1e-4). A provenance
   round trip that never composes the transform could carry a wrong-handed
   `orient` quaternion while every primvar matches — green over broken, the
   v0.7 *"built is not cooks"* failure mode. This check forbids it. **Author a
   USD asset, then compose and compare it — never trust a green primvar pass
   alone.**

6. **`anchor_faces` is a JSON string primvar (P3, additive).** Each part's
   local-space face patches ride as `primvars:kitmash:anchor_faces` (String,
   constant). Format: `"null"` or a JSON array of `{c, n, u, hu, hv, cls}`
   objects (all float64 inside the JSON string — exact). A replacement asset
   reads this primvar to inherit the face declaration without recomputing
   geometry. `face_cls` (Int) on each strut records which anchor class took
   the weld (−1 = AABB/legacy). The gate verifies both round-trip in
   `verify_usd.py` (857 checks, 0 failures after this addition).

## Goblins found at first contact (do not relearn these)

All three lived in the `pxr` API surface — exactly the pattern the Houdini port
predicted (*contracts hold; goblins live in the host surface*). The
host-agnostic extractors were never wrong.

1. **`Tf.MakeValidIdentifier` collapses non-ascii to `_`.** `GS-α` and `GS-β`
   both became `GS___` → the second ship re-defined the first's prim path,
   raising *"xformOp:translate already exists"*. Fix: transliterate Greek
   (`α→alpha`) before sanitizing, so tokens stay unique *and* readable and are
   derivable from the ship name alone (driver and gate need no shared state).

2. **`Xformable.GetLocalTransformation()` returns a bare `Matrix4d`** in this
   binding, not a `(matrix, resetsStack)` tuple. Indexing `[0]` silently took
   the first *row* (`Vec4d`), which has no `.Transform()`. Guard both shapes.

3. **A stale function signature** (`read_local_to_world(stage, prim)` called
   with one arg) — mine, not USD's. The same class of bug as the Houdini
   `node.parent()` miss: the host code is a hypothesis until it runs.

## Status

v0.9 baseline: Verified green in **both** runtimes (usd-core 26.5, Houdini pxr
25.5): 810 checks, cook test on all five ships, `fleet.json` byte-identical.
`kitmash:schema_version = kitmash/0.6`.

P3 addition (2026-06-14): `anchor_faces` + `face_cls` exported. **857 checks, 0
failures** (usd-core 26.5). Houdini pxr re-verification deferred (requires
hython session). The assembler decision path was not touched; canonical md5
`80ddaccccc594b2a7cc8c7b40a129086` unchanged.
