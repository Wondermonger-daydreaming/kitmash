# `kitmash::part_fuel_tank` — the first part HDA (deliverable b)

> **Renamed v0.12 (2026-06-13):** the type was originally `kitmash::part_tank::1.0`,
> a legacy name predating the `GEN_REGISTRY` key `fuel_tank`. It is now
> `kitmash::part_fuel_tank::1.0` so the unified gate `verify_native_hda.py`
> (which keys on the registry) exercises the NATIVE interior, not the wrapper.
> The standalone `verify_tank_hda.py` was retired (superseded by the unified
> gate). This doc keeps its filename for stable cross-references.

*One HDA per family; params = gen_params; output = artist-grade mesh PLUS
port/grommet points carrying the schema attributes. The schema is already
in Houdini attribute syntax — that was the point.*

This document is the contract for the first HDA, proving the round trip
for the simplest interesting part: `fuel_tank` (one port, two grommets,
one intra-part routing edge, a supply). Once this round-trips, the other
families are transcription work.

The numeric source of truth is `gen_tank()` in `kitmash.py`; gate 7 of
`test_kitmash.py` proves the placement-record → rehydration identity in
numpy on every test run. `houdini/verify_native_hda.py fuel_tank` re-proves it
against the actual native HDA output.

## Type

| | |
|---|---|
| node type | `kitmash::part_fuel_tank::1.0` (SOP) |
| implements | schema `kitmash/0.6`, family `fuel_tank`, generator `gen_tank` |
| inputs | 0 |
| file | `houdini/kitmash_part_fuel_tank.hda` (built by `make_tank_hda.py`) |

## Parameters (= gen_params, the crown jewel)

| parm | type | default | range | meaning |
|---|---|---|---|---|
| `h` | Float | 2.4 | 2.16 – 2.64 | drum length. **Derived in Python** (`2.4 * U(0.9, 1.1)` from seed), recorded in gen_params, consumed here as-is. The HDA never re-runs the jitter — VEX cannot reproduce `random.Random`, and must not try. |
| `seed` | Integer | 0 | — | cosmetic only: VEX greeble/panel-line jitter. Never structural. |

The rehydrator sets these via `point()` expressions from the placement
point's `gp_h` / `gp_seed` (see `ASSEMBLER-SOP.md`).

## Output contract (part-local space — placement transform happens outside)

### Body — prim group `body`
Placeholder matching the kitmash cartoon, so the three.js viewer and
Houdini agree until an artist replaces it:
- drum: capped tube, radius 0.55, axis **+X**, length `h`, centered
  `{0, 0, 0.55}`. **Vertex-phase note (load-bearing for the bbox gate):**
  Houdini's X-oriented `tube` starts its cross-section at +y, but
  `km.cyl`'s vertex 0 sits at local +x. A 90° roll about the drum axis
  (Transform SOP, pivot `{0, 0, 0.55}`) is required so the body bounding
  box matches the cartoon to ±1e-4 — `verify_tank_hda.py` enforces this.
- mounting skirt: box 0.7 × 0.7 × 0.12 centered `{0, 0, 0.05}`

Artists may replace the body with anything whose silhouette honors the
drum; **ports and grommets are load-bearing and must not move.**

### Port — 1 point in group `ports`

```
@P            {0, 0, 0}
v@N           {0, 0, -1}        outward mating axis (mounts downward)
v@up          {1, 0, 0}         roll reference. NEVER omit
s@port_type   "struct_M"
f@port_size   0.8
i@port_gender 1                 plug
i@port_prio   5
i@port_sym    0                 continuous roll
s@port_cluster ""               s@port_tags ""
```

### Grommets — 2 points in group `grommets`, 1 polyline prim

```
g0: @P {0, 0, 0.1}    s@conduit_type "fuel"   f@conduit_size 0.1
g1: @P {0.6, 0, 0.55} s@conduit_type "fuel"   f@conduit_size 0.1
prim: polyline g0→g1  (the pre-authored intra-part routing graph)
```

### Detail attributes

```
s@family      "fuel_tank"        s@generator "gen_tank"
s@gen_params  {"h": <h>, "seed": <seed>}
              sprintf("%.9g", h) — full float32 fidelity. NOT plain %g
              (6 sig-digits would truncate below the verify tolerance).
              h is recorded at FULL precision (never round()d): the part
              consumes gp_h as-is, so the recorded value must equal the
              consumed value to the bit.
f@mass        900 * h / 2.4      f@silhouette 0.45
s@supplies    [["fuel", 3.0]]    s@demands  []
```

`s@part_id`, `i@era`, `s@faction`, `f@join_strain` are **assembly-time**
facts: the rehydrator stamps them onto the HDA output from the placement
point after instancing (they are not the part's to know).

### VEX dressing hooks (the "details" half — optional, post-v1)
- strain-driven grunge keyed to post-stamped `f@join_strain`
- weld seam at the skirt if `i@era` mismatches the host
- `seed`-jittered panel lines on the drum

## Round-trip proof

1. **numpy (already running, every test run)**: gate 7 rehydrates the
   GS-α tank from its placement record — gen_params checksum, mesh
   identity, port frame identity, grommet identity.
2. **Houdini (verified live 2026-06-12, Apprentice)**: `hython
   houdini/verify_tank_hda.py` — instantiates the HDA with `h`/`seed`
   from a live `build()` placement record and diffs: port
   count/position/N/up/type/size/gender, grommet positions/conduits,
   gedge topology, body bounding box (±1e-4), and the detail gen_params
   JSON against the Python part. **Tolerances are float32-honest**, not
   float64-exact — the values ride float32 VEX channels and a `%.9g`
   re-stamp, so bit-exact equality is physically impossible: gen_params
   floats compare to 5e-7 relative (ints exact, type drift fails), mass
   to 5e-4, silhouette to 1e-6. Exits nonzero on any drift. This is the
   acceptance gate for (b); it passes (`ROUND TRIP PROVEN`).

## Building the HDA

```bash
source /opt/hfs21.0.729/houdini_setup
hython houdini/make_tank_hda.py              # writes houdini/kitmash_part_fuel_tank.hda
hython houdini/verify_native_hda.py fuel_tank  # proves the native round trip
```
