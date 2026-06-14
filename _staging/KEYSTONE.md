# KEYSTONE — K2 shared part-asset library (roadmap item 4 follow-up)

**Shipped: K2** (the explicit roadmap intent), not the K1 fallback. Every ship
part now `references` a single canonical per-family asset; no body is
re-embedded. The decision layer (the truth) is unchanged and fully gated.

## The design shipped

### usd/assets/ — the shared library
One ASCII `.usda` per family that appears in the canonical fleet (10 files;
`terminator_cap` is not placed in the canonical five, so it is correctly
absent — `fleet_families()` authors only what is used):

```
core_hull engine fuel_tank wing heavy_cannon antenna sensor_pod radiator reactor turret
```

Each asset is:
```
/<Family>   Xform   defaultPrim; customData kitmash:{family, schema_version}
  /geo      Mesh    canonical prototype body — GEOMETRY ONLY, no color
```

- The prototype body is the **deterministic canonical cook**
  `gen_<family>(GUILD, seed=0)` — `kitmash_usd.canonical_part(family)`. This is
  the USD twin of the part HDA and the gate's ground truth.
- `defaultPrim` is set so a bare `references = @./assets/<family>.usda@` (no prim
  path) resolves to the prototype — the instance's child `/geo` composes
  through the arc.

### usd/kitmash_fleet.usda — composes from the library
Each `/Fleet/<ship>/Parts/part{i}_<id>` Xform now carries
`prepend references = @./assets/<family>.usda@` (RELATIVE uri → the fleet +
library are a relocatable bundle, git-diffable, ASCII). All provenance primvars
(`gen_params`, `mass`, `silhouette`, `join_strain`, `anchor_faces`, `face_cls`,
typed `kitmash:gp:*`) and the P/orient xform ops stay on the **instance**,
exactly as before. Only the *body* moved to the referenced asset.

### Where color lives — DECIDED: the instance
Geometry is faction-independent (verified: no generator branches its mesh on
faction; GUILD and FERAL cooks are `np.allclose` for every family). So the
shared prototype is **colorless**, and the faction `displayColor` is authored as
a per-instance **override** on the composed `/geo`. GUILD and FERAL reference
the *same* asset and differ only in the override. This is the clean home for
color: shared body, per-instance appearance.

## The cook test — rewritten honestly into three halves (the crux)

A naive K2 breaks the old cook test (it compared the *embedded* mesh to world;
the embedded mesh was the per-instance body). Under K2 the composed body is the
shared *prototype*, so "composed body == world" would become a tautology that
can never fail — the exact sin this project hunts. The rewrite (in
`verify_usd.verify_ship`) proves what is now actually true, **per part**:

| Half | What it proves | How it FAILS RED (flip-tested) |
|------|----------------|-------------------------------|
| **(a) ref resolves** | `prim.GetChild("geo")` composes through the arc and has real points | `ClearReferences()` on the part → `geo` points become `None` → check fails (verified: "after drop: points is None") |
| **(b) body == canonical proto** | composed `geo` points == `canonical_points(family)` (≤1e-4) | corrupt one prototype coord by +0.5 → err 0.5 > 1e-4 → red (verified). A wrong-family asset or a wrong cook also fails here. |
| **(c) instance xform composes to world** | `rehydrate(rec)` the per-instance body from `gen_params` (the truth path), apply the authored translate+orient, compare to assembler world (≤1e-4) | apply a wrong rotation (+90° about z) → err 4.0 > 1e-4 → red (verified). A wrong-handed `orient` fails even with every primvar green — the v0.7 "built is not cooks" mode, still forbidden. |

Half (c) is the load-bearing one: it composes the **per-instance** body
(reconstructed from the gen_params primvars via the gate-7-proven `rehydrate`),
NOT the shared prototype — so it proves the *truth* re-renders to the assembler
geometry, independent of what body the asset happens to carry. (a)+(b) together
prove the shared library resolves to the right thing. Neither can hide a broken
arc behind a green primvar pass.

The flip-test evidence above was produced by a throwaway harness against an
in-memory stage; the green baseline is the committed gate.

## Numbers

- **Check count: 857 → 914 (+57).** Breakdown: +47 per-part `ref resolves`
  checks (47 placed parts across the 5 ships) + 10 from splitting the single
  per-ship cook line into three (5 ships × 2 extra lines). Arithmetic confirmed.
- **Green in BOTH runtimes:** `.venv/bin/python verify_usd.py` → 914 ok / 0 fail,
  exit 0; `/opt/hfs21.0.729/bin/hython verify_usd.py` → 914 ok / 0 fail, exit 0.
- **References compose from the committed files:** opening `usd/kitmash_fleet.usda`
  and traversing, all 47 part `/geo` prims resolve through the relative
  `./assets/` arcs with real points; `stage.Flatten()` succeeds. `make_fleet_usd.py`
  under hython writes a fleet whose refs also resolve when reopened under
  usd-core (cross-runtime).

## Anchor — UNTOUCHED
`../.venv/bin/python kitmash.py /tmp/keystone.json && md5sum` →
`80ddaccccc594b2a7cc8c7b40a129086` (the contract, unchanged). `kitmash.py` and
`kitmash_houdini.py` are unmodified (`git status` clean for both). Files touched:
`kitmash_usd.py`, `verify_usd.py`, `usd/USD-EXPORT.md`, `usd/kitmash_fleet.usda`,
and the new `usd/assets/`.

## Where this is NOT finished (the soft spots — beating the owner to them)

1. **usdview shows every instance at canonical size, not its true size.** The
   shared prototype is `gen_*(seed=0)`, so all engines render at size 1.0, all
   wings at span 3.2, etc. — the per-instance variation lives in primvars
   (truth, inv 7) but a *naive* viewer does not re-render it. This is
   doctrine-correct (mesh is cached opinion) but it is a real fidelity loss for
   anyone who opens the fleet expecting the actual silhouettes. The honest fix
   is a host-side rehydrate-on-load (the `rehydrate()` path already exists), or
   K2-variant assets keyed by quantized gen_params. Not built.

2. **The per-instance `displayColor` override is verbose (per-face) and bloats
   the .usda diff.** A part with 68 faces authors 68 identical color tuples on
   one line. It is correct and git-diffable but ugly, and it partly undercuts
   the "shared, lean" win at the fleet-layer. Cleaner: author color as a
   *constant*-interpolation displayColor per sub-body, or push faction color
   into a small set of per-faction material/look assets the instance binds (a
   `UsdShade` MaterialBindingAPI) instead of raw vertex color. Not built — I
   kept the existing color *semantics* (uniform per-face) to avoid perturbing
   what `make_viewer`/downstream may read; revisit when a material layer lands.

3. **The asset library is authored from the fleet, not from a standalone
   catalogue pass, and uses GUILD as the canonical-cook faction by fiat.**
   `export_fleet` / the gate build the library on the fly from whichever
   families the ships use; there is no `make_asset_library.py` entrypoint, and
   `terminator_cap` (a real family) has no committed asset because the canonical
   fleet never places it. The moment buildings or a sixth ship introduce a new
   family, the library silently grows — fine for now, but there is no gate that
   the committed `usd/assets/` is *complete* w.r.t. the family registry, only
   that it is *sufficient* for the current fleet. A `GEN_REGISTRY`-complete
   library + a "every family has an asset" check is the next rung.
