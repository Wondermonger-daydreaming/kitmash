# The Assembler SOP — KitMash inside Houdini

*Roadmap item 5, deliverable (a). Architecture decided 2026-06-12:
**Python decides, VEX details.** The assembler ships decisions, not meshes.*

Status: code complete, numpy-proven (gate 7 of `test_kitmash.py`) AND
**live-verified under hython** (Houdini 21.0.729 Apprentice, 2026-06-12 —
`test_headless.py` 8/8, 11 wrapper HDAs cook clean). Houdini installs at
`/opt/hfs21.0.729` (no `/opt/hfs21.0` symlink — use the full path).

## The network

```
geo: kitmash_ship
├── python_sop: assembler          # paste houdini/kitmash_assembler_sop.py
│     emits decision geometry only (points + curves, no part meshes)
│
├── split: placements              # group `placements`
│   └── foreach_point: rehydrate   # ← the For-Each rehydrator (below)
│
├── split: struts                  # prim group `struts`
│   └── sweep (round, f@width=0.06, 6 cols)         → strut cylinders
├── split: collars                 # point group `collars`
│   └── copytopoints: collar disc (tube r=@r h=0.1, oriented by v@N/v@up)
│
├── split: hoses                   # prim group `hoses`
│   └── … → sweep                  # see hoses-to-sweep.md (deliverable c)
│
└── split: open_ports              # greeble/terminator hooks (optional)
      feral: tape/dangling-cable copies; guild: nothing (caps are parts)
```

Merge the branches at the end. The Python SOP cooks one `build()` per
change of (faction, seed, wants, heavy, span, genes) — under a second per
ship, no caching games needed.

## Parameters on the Python SOP

| parm | type | default | notes |
|---|---|---|---|
| `kitmash_path` | String | dir of kitmash.py | inserted into `sys.path` |
| `faction` | Ordered Menu | 0 | 0 High Guild, 1 Feral |
| `seed` | Integer | 7 | |
| `wants` | String | `{"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":1.4,"antenna":0.8,"sensor_pod":0.6}` | JSON family→weight |
| `heavy` | Float | 1.0 | cannon gene |
| `span` | Float | 3.2 | wing gene |
| `use_radiator` / `use_reactor` / `use_turret` | Toggle | off | extra genes |

These parms ARE the brief — when the agent loop arrives (roadmap 6), the
brief author writes these and PDG wedges them.

## The For-Each rehydrator

Inside a For-Each Point loop (piece attribute `part_id`, single pass per
point):

1. **Switch** on `s@generator` (use an Attribute Wrangle to bake it to a
   switch index, or a Switch-If per part HDA). One input per part HDA:
   `kitmash::part_fuel_tank`, `kitmash::part_engine`, … (one HDA per
   family). **Day-one coverage:** `hython houdini/make_part_hdas.py`
   generates thin-wrapper HDAs for ALL 11 families (interior = Python
   SOP calling the family's own generator via
   `kitmash_houdini.write_part_geo` — round trip by construction).
   Artists then replace interiors family by family with native networks;
   `kitmash_part_tank.md` is the migration pattern.
2. **HDA parms read the point directly** — every gen_param is doubled as
   a typed point attribute `gp_*` precisely so HDA parms can use plain
   `point()` expressions, no JSON parsing in the loop:
   ```
   h     = point("../foreach_begin1", 0, "gp_h", 0)
   seed  = point("../foreach_begin1", 0, "gp_seed", 0)
   ```
3. **Transform** the HDA output by the point's `@orient` + `@P`
   (Transform Pieces, or a wrangle:
   `@P = qrotate(point(1,"orient",0), @P) + point(1,"P",0);`).

The contract this depends on — *HDA output in part-local space ==
generator output in part-local space, ports included* — is exactly what
gate 7 proves in numpy and what `kitmash_part_tank.md` specifies for the
first HDA.

**Why the placement point carries derived values** (`gp_h`, `gp_r`, …):
the HDA must NOT re-run Python's `random.Random(seed)` — VEX can't
reproduce it and shouldn't try. Python derives, the HDA consumes derived
values; `gp_seed` is for cosmetic VEX jitter only (greebles, panel-line
offsets), never for anything structural. `rehydrate()` in
`kitmash_houdini.py` asserts this determinism on every test run.

**Load-bearing precision contract (since the live-verification session):**
`gen_params` records derived jitter at **full float precision**, NOT
rounded. Earlier generators stored `round(h, 2)`; the part HDA consumes
`gp_h` *as-is*, so a rounded recording cannot reproduce the assembler's
geometry. The recorded value IS the consumed value — they must be the
same number to the bit the host can carry. The HDA detail re-stamp uses
`sprintf("%.9g", h)` (full float32 fidelity; plain `%g`'s 6 sig-digits
would silently truncate below the verify gate's tolerance).

## What the decisions carry for VEX (the "details" half)

- `f@join_strain`, `i@era` on placements → strain-driven grunge, retrofit
  weld seams (the HDA reads them as parms or post-bind attributes)
- `f@relief`, `s@anchor` on struts → gusset size, weld-bead density
- `f@strain` on collars → adapter prominence
- `s@hose_style` (`shroud` | `catenary`) on hoses → faction dressing
- detail `s@trace` → the full ledger rides inside the .hip; the Borges
  catalogue and the agent loop read it from here

## Headless smoke test (verified live, 2026-06-12)

```bash
source /opt/hfs21.0.729/houdini_setup
hython -c '
import hou, sys
sys.path.insert(0, "<dir of kitmash.py>")
import kitmash as km, kitmash_houdini as kh
geo = hou.Geometry()
kh.write_geo(geo, km.build(km.GUILD, 7,
    {"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":1.4,
     "antenna":0.8,"sensor_pod":0.6}, heavy=1.0, span=3.0), name="GS-alpha")
print(len(geo.points()), "points,", len(geo.prims()), "prims")
print(geo.attribValue("stats"))'
```

Expected: placements (10) + strut segment points + hose points +
open-port points; `stats` echoing `{"parts": 10, "mass": 9464,
"struts": 3, "hoses": 1}` — the same numbers gate 1 pins.
