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

## Worked examples (native interiors built so far: 2 / 11)

| Family | Builder | What it demonstrates |
|--------|---------|----------------------|
| `fuel_tank` (`part_tank`) | `make_tank_hda.py` | 1 phase-rolled drum + skirt box; -Z port; supplies; gedge |
| `engine` | `make_engine_hda.py` | 2 size-scaled X-cones; +X port; **demands**; clearance_vols + anchor_vols |

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

## Remaining (9 / 11 still wrappers)

`antenna`, `core_hull`, `heavy_cannon`, `radiator`, `reactor`, `sensor_pod`,
`terminator_cap`, `turret`, `wing`. Each is a `make_<family>_hda.py` following
the recipe, gated by `verify_native_hda.py <family>`. Watch-list: `core_hull`
(two cyls incl. an X-cone nose + 7 ports + a 5-node fuel gedge — the biggest);
`turret` (barrel `frame([1,0,0.35],[0,0,1])` is a *tilted* axis — not a clean X
roll, needs a compound rotation); `wing`/`cannon` (a `mount_rail` **cluster** —
two ports with `cluster`/`sym`, handedness in `port_tags`).
