# Hoses → Sweep (deliverable c)

*Python decides, VEX details: the router decided the PATH (A* over the
channel graph, segregation, loom, rip-up — all already fought and logged
in the trace). Houdini only dresses the polyline it is handed.*

The assembler SOP emits hose polylines in prim group `hoses` with:

```
point  f@width        dia/2 — Sweep reads this directly
point  f@dia          full bundle diameter (reserved capacity)
point  s@ctype        "fuel" | "high_volt" | "coolant" | "optical"
point  s@hose_style   "shroud" (guild) | "catenary" (feral)
```

Gravity in kitmash space is **−Z** (the assembler's spine fold uses z-up;
the hull deck faces +Z).

## Network

```
split: hoses
└── switch on s@hose_style (prim wrangle bakes it to a detail int)
    │
    ├── [0] GUILD — shroud: the hose pretends it isn't there
    │     └── sweep: Surface Shape = Square Tube, Columns 4,
    │               Scale 1.6 (shroud swallows the bundle),
    │               Radius from f@width  → flange cube at each end
    │
    └── [1] FERAL — catenary + p-clips: the hose is the ornament
          ├── convertline          # each route hop becomes its own prim
          ├── resample             # Length 0.15, ✓ Curve U Attribute
          ├── pointwrangle: SAG    # vex below
          ├── sweep: Round Tube, Radius from f@width,
          │          Columns by ctype (fuel 8, high_volt 6,
          │          coolant 8, optical 4)
          └── copytopoints: P-CLIPS at the route nodes (vex below)
```

`convertline` before `resample` is the load-bearing trick: it makes
every hop of the routed path its own primitive, so `@curveu` is
per-span and each span sags like a real harness between clips —
instead of one droop across the whole run.

## SAG — point wrangle (after resample)

```c
// catenary cartoon: parabola per span, deeper on longer spans.
// slack: feral 0.06; leaps sag more than grommet-hugging runs.
float slack = chf("slack");                       // default 0.06
int   pr    = pointprims(0, @ptnum)[0];
float len   = primintrinsic(0, "measuredperimeter", pr);
@P.z -= slack * len * 4.0 * @curveu * (1.0 - @curveu);
```

## P-CLIPS — where the hose touches the ship

Clips belong at the route NODES (grommet taps and inter-part jump
points) — the places the router actually paid for. Take the
pre-`convertline` hose points, drop the two end taps, copy a clip:

```c
// point wrangle on the raw hose curve, before convertline:
// keep interior route nodes only; orient clip along the hose tangent.
if (@ptnum == 0 || @ptnum == npoints(0) - 1) removepoint(0, @ptnum);
int   prim = pointprims(0, @ptnum)[0];
vector nxt = point(0, "P", min(@ptnum + 1, npoints(0) - 1));
v@N   = normalize(nxt - @P);                      // tangent
v@up  = {0, 0, 1};
f@pscale = f@dia * 1.4;                           // clip wraps the bundle
```

Clip geometry: a 3/4 torus + base tab (or a 0.02m box as placeholder).
Copy to Points with `v@N`/`v@up` orientation.

## Per-ctype dressing (closes a known v0.6 cheat)

The .html viewer draws all ctypes in one style — Houdini does better
for free. Prim wrangle before the sweep:

```c
s@ctype == "fuel"      ? v@Cd = {0.85, 0.55, 0.20} :
s@ctype == "high_volt" ? v@Cd = {0.90, 0.25, 0.15} :
s@ctype == "coolant"   ? v@Cd = {0.30, 0.65, 0.85} :
                         v@Cd = {0.80, 0.80, 0.30};  // optical
```

High-volt additionally wants ring ribs (Sweep → UV Columns +
displacement, or a boolean-less wrangle pushing rings out every 0.1
along @curveu) — cosmetic, post-v1.

## What NOT to do here

- Do not smooth/shortcut the path (Fuse, Facet, Smooth on @P): the
  polyline IS the reservation — every node is a channel the router paid
  capacity for. Sag displaces BETWEEN nodes; nodes stay put.
- Do not merge hoses into one wire mesh before sweeping: `loomed`
  bundles share channels deliberately; their parallel runs reading as a
  harness is the v0.6 economics made visible. Keep prims separate so
  each keeps its own f@width and v@Cd.
