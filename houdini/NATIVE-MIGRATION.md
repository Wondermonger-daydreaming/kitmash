# Wrapper → native interior migration (roadmap item 5 follow-up)

Every family ships day-one as a **thin Python-SOP wrapper**
(`houdini/hda/kitmash_part_<family>.hda`, built by `make_part_hdas.py`): the
interior calls the family's own generator via `write_part_geo`, so it
round-trips *by construction*. The migration replaces that interior, family by
family, with a **native SOP/VEX network** under the SAME type name — faster, no
Python dependency, and artist-editable (greebles, panel lines, strain grunge).

**The contract never changes** (`kitmash_part_tank.md`): parms ARE gen_params;
ports and grommets are load-bearing and may NEVER move; the body is a
placeholder artists may change. Migration is a swap of the *interior*, gated.

## Worked examples (native interiors built: 11 / 11 — COMPLETE)

| Family | Builder | What it demonstrates |
|--------|---------|----------------------|
| `fuel_tank` | `make_tank_hda.py` | 1 phase-rolled drum + skirt box; -Z port; supplies; gedge. Type fixed `part_tank`→`part_fuel_tank` in v0.12 (see note) |
| `engine` | `make_engine_hda.py` | 2 size-scaled X-cones; +X port; **demands**; clearance_vols + anchor_vols |
| `sensor_pod` | `make_pod_hda.py` | the MINIMAL case: 1 Z-native straight cyl (no phase roll — bbox phase-invariant); +Z port; a **derived-only** gen_param `r` exposed as a parm so the gate injects the Python RNG value |
| `terminator_cap` | `make_cap_hda.py` | the DEGENERATE case: 1 Z-native cone; -Z port; **gen_params = {}** (no parm templates at all); smallest part in the kit |
| `reactor` | `make_reactor_hda.py` | first ROUTING body on a Z-native cyl: tapered shell (height + center-z both link to `h`) + mount box; +Z port; **2 high_volt grommets** (one h-dependent in VEX) + gedge + supplies |
| `antenna` | `make_antenna_hda.py` | first NON-NULL `anchor_vols` (literal AABB — base box only, the mast is a whip); Z-native whip cone (seg=14) + base box; -Z port; height + center-z link to `h` |
| `radiator` | `make_radiator_hda.py` | first family with BOTH non-empty clearance_vols (w-scaled in VEX) and a literal anchor_vols; all-BOX body (no phase concern); panel sizey links to `w`; +Z port |
| `core_hull` | `make_hull_hda.py` | the biggest: hull box + **X-cone nose** (phase-rolled, scale-dependent tx); **7 ports** (all gender 0, varying prio, side_R/side_L tags, emitted in generator order); **5 grommets + 4-edge gedge chain**; `scale` drives L/nose/port0/grommets/mass |
| `heavy_cannon` | `make_cannon_hda.py` | mount_rail **cluster** (2 ports, sym 1, cluster railA); X-cone barrel **offset in z** → the 90° roll pivots on the barrel axis (pz=0.42), not z=0; `heavy` scales barrel + mass |
| `wing` | `make_wing_hda.py` | **handedness**: `hand` (±1) flips rail-port x-signs, up vectors, and the side_R/side_L tag (computed in VEX, not baked); all-box body; `span` drives panel/tip-port/grommet/mass |
| `turret` | `make_turret_hda.py` | the sharpest: **tilted barrel axis** `frame([1,0,0.35],[0,0,1])`. Euler + the xform SOP did NOT reproduce it — applied km's exact rotation matrix in a **point wrangle** instead. Caught the Houdini-tube taper-flip bug (below) |

> **✓ Tank type-name drift — found AND fixed 2026-06-13 (v0.12).** The native
> tank HDA was type `kitmash::part_tank::1.0` — a legacy name from when it was
> "the first part HDA (deliverable b)," before the registry settled on the family
> key `fuel_tank`. The generalized gate `verify_native_hda.py` looks up
> `kitmash::part_fuel_tank::1.0` (the registry key) — which was the **wrapper**,
> not the native `part_tank`. So the unified gate's `fuel_tank` pass was testing
> the WRAPPER by construction; the native interior was reachable only via the
> standalone legacy `verify_tank_hda.py`. **Fix applied:** `make_tank_hda.py` now
> builds `kitmash::part_fuel_tank::1.0` → `houdini/kitmash_part_fuel_tank.hda`;
> the orphaned `kitmash_part_tank.hda` and the now-redundant `verify_tank_hda.py`
> were retired (two divergent gates were what let the drift hide); the
> `part_tank.md` contract was updated. Verified native wins for all four families
> via `type().definition().libraryFilePath()`. **The rule this codifies: a native
> HDA's type suffix MUST equal its `GEN_REGISTRY` key, or the unified gate
> silently tests the wrapper.**

## The gate: `verify_native_hda.py`

The generalization of `verify_tank_hda.py`. Point it at any family; it diffs the
installed `kitmash::part_<family>::1.0` against the Python generator across
several seeds and both factions:

```sh
/opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py engine      # one family
/opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py             # all installed
```

It is agnostic to wrapper vs. native (wrappers pass by construction; native must
*earn* it). It installs wrappers first and native interiors (`houdini/*.hda`)
last, so a migrated family's native HDA wins over its wrapper of the same type.
It checks: ports (@P, v@N, v@up, type/size/gender/prio/sym), grommets +
conduit attrs, gedge count, `family`/`generator`, `gen_params` (float32-honest),
`mass`, `silhouette`, `supplies`/`demands` (float32-honest rates),
`clearance_vols`, `anchor_vols`, and body bbox (≤1e-4).

## The recipe (per family)

1. **Read the generator** in `kitmash.py` (`gen_<family>`). Note every mesh
   (`box`/`cyl` + transform), the port list, the grommets/gedges, supplies/
   demands, clearances, anchor_vols, mass, silhouette, and which gen_params keys
   are *accepted kwargs* (drive geometry) vs *recorded only* (cosmetic seed).
2. **Body from native primitives.** `box()` → a `box` SOP (identity transform);
   `cyl(r0,r1,h)` → a `tube` SOP. Match the frame:
   - `np.eye(3)` (the cyl's native Z axis) → `tube orient=2` (Z).
   - `frame([1,0,0],[0,0,1])` (local Z → world X) → `tube orient=0` (X) **plus a
     90° roll about the axis** (`xform rx=90`, pivot on the axis): km.cyl's
     vertex 0 sits at world +z, Houdini's X-tube starts its cross-section at +y.
     Without the roll the bbox still matches (a cone of revolution) but the
     polygon phase is wrong — `make_tank_hda`'s `drum_phase` and
     `make_engine_hda`'s `casing_phase`/`nozzle_phase` are this fix.
   - **Taper direction (found v0.12 via turret).** Houdini's `tube` puts `rad1`
     at the **+axis** end; `km.cyl(r0,r1,h)` puts `r0` at **−h/2** (the −axis
     end). So they are SWAPPED: set `rad1 = r1`, `rad2 = r0`. This is invisible
     to an axis-aligned bbox (xy = max radius either way), so the gate does NOT
     catch a flipped taper on an axis-aligned cone — but the cone points the
     wrong way. A *tilted* cone (turret) breaks the bbox and exposes it. All
     tapered tubes carry the swap; only `frame([1,0,0.35],…)` made it gate-visible.
   - **Tilted axes (found v0.12 via turret).** For a non-trivial `frame(N,up)`
     (N not axis-aligned), do NOT decompose to Euler for the xform SOP — its
     rotation-order composition drifted the bbox ~1e-2. Build the tube `orient=2`
     (Z-native, matching km.cyl's local frame), then apply km's EXACT rotation
     matrix in a **point wrangle**: `matrix3 M = set(<R.T row-major>); @P = @P*M;
     @P += <translate>;` where `R = km.frame(N,up)` computed in the build script
     and baked at `%.17g`. VEX is row-vector (`P*M`), so `M = R.T`.
   - `cols` = the generator's `seg` (default 14; pod/reactor seg=10; cap seg=8).
   - Parametric radii/lengths link to the parm post-collapse via
     `setExpression('<coef>*ch("../<parm>")')` (see the engine's radius links).
3. **One detail-mode `attribwrangle`** authors ports + grommets + the part-level
   schema in VEX, copied from the generator's literals. Group every input prim
   into `body`. `addpoint` + `setpointattrib` + `setpointgroup(…,"ports"/"grommets")`.
   `addprim(0,"polyline",g_i,g_j)` per gedge. Detail attrs: `family`,
   `generator`, `gen_params` (sprintf with `%.9g` for floats — `%g`'s 6 digits
   truncate below tolerance), `mass`, `silhouette`, `supplies`, `demands`,
   and (if the part declares them) `clearance_vols` / `anchor_vols` as
   `[[lo],[hi]]` AABB JSON, size-scaled where the generator scales them.
4. **Collapse → digital asset**, append parm templates for the accepted kwargs
   (+ a recorded `seed`), link inner-node expressions to those parms.
5. **Cook, then gate.** `built` is not `cooks`: a wrong parm path or VEX goblin
   stays invisible until instantiation. Run the gate; fix goblins in the
   `hou`/VEX surface; never trust green-build over green-cook.

## Goblins met (engine, 2026-06-13)

- The body, ports, grommets, both phase rolls, gen_params, mass, clearance and
  anchor volumes were green on the **first cook** — the geometry mapping in
  step 2 held. The lone discrepancy the gate caught: **`demands` rate**. The
  native VEX computes `1.2*size` on a **float32** channel (`1.2`→`1.20000005`),
  while the wrapper emits Python's exact `1.2`. Fix was in the *gate*, not the
  HDA: a netlist rate derived in float32 VEX deserves the same float32-honest
  tolerance (5e-7) as `mass` and `gen_params` floats — exact `==` was the wishful
  bound. (Lesson, again: a tolerance is a claim about storage.)

## Complete (11 / 11 native, 2026-06-13 v0.12)

Every family now ships a native SOP/VEX interior — no wrapper left. The full
gate `verify_native_hda.py` is **784/784, 0 FAIL** across all 11 families, both
factions, three seeds each. The whole watch-list landed this session:
`core_hull` (X-cone nose + 7 ports + 5-grommet/4-edge gedge), `heavy_cannon` and
`wing` (mount_rail clusters; wing adds handedness), and `turret` (the tilted
barrel axis — which forced the point-wrangle matrix technique and caught the
taper-flip bug now codified in recipe step 2).

The wrappers in `houdini/hda/` are kept as the day-one fallback and as the gate's
"prove the native earns it" baseline — they are installed first, the native
`houdini/*.hda` last, so native wins. Nothing else remains for item 5.
