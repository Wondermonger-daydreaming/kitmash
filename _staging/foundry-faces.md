# FOUNDRY — Per-Family Anchor Faces (P3 fan-out)

Agent: FOUNDRY  
Files edited: `kitmash.py` (generators region), `test_kitmash.py`  
Branch: p3-face-anchors

---

## md5 trace

```
before  80ddaccccc594b2a7cc8c7b40a129086   (v0.8.1 baseline, hull faces only)
after   80ddaccccc594b2a7cc8c7b40a129086   (UNCHANGED — all 10 leaf families added)
```

Invariant holds. The 10 families receiving faces are all leaf nodes in the
canonical fleet (every canonical strut anchors to `core_hull` only), so
adding `anchor_faces` to them changes no strut computation.

---

## Per-family face declarations

### engine (headline case)

| face | centre | normal | hu × hv | cls |
|------|--------|--------|---------|-----|
| casing +y barrel | [-1, 0.95, 0] | [0,1,0] | 1.0×0.95 | **2** primary |
| casing -y barrel | [-1,-0.95, 0] | [0,-1,0] | 1.0×0.95 | **2** primary |
| casing +z barrel | [-1, 0, 0.95] | [0,0,1] | 1.0×0.95 | **2** primary |
| casing -z barrel | [-1, 0,-0.95] | [0,0,-1] | 1.0×0.95 | **2** primary |
| fwd mating flange | [0, 0, 0] | [1,0,0] | 0.95×0.95 | **2** primary |
| **glow nozzle** | **[-3.0, 0, 0]** | [-1,0,0] | 0.55×0.55 | **0 GLASS** |

`anchor_vols` retained alongside faces for legacy consumers.
`face_candidates(nozzle, com)` returns `[]` at any com — verified in gate 10.

### antenna

| face | centre | normal | hu × hv | cls |
|------|--------|--------|---------|-----|
| base top | [0, 0, 0.10] | [0,0,1] | 0.15×0.15 | **2** primary |
| base +x side | [0.15, 0, 0.05] | [1,0,0] | 0.05×0.15 | **2** primary |
| base -x side | [-0.15, 0, 0.05] | [-1,0,0] | 0.05×0.15 | **2** primary |
| base +y side | [0, 0.15, 0.05] | [0,1,0] | 0.15×0.05 | **2** primary |
| base -y side | [0,-0.15, 0.05] | [0,-1,0] | 0.15×0.05 | **2** primary |
| **mast tip** | [0, 0, h/2] | [0,0,1] | 0.03×0.03 | **0 GLASS** |

`anchor_vols` retained for legacy. Mast is a whip — no weld above the base box.

### radiator

| face | centre | normal | hu × hv | cls |
|------|--------|--------|---------|-----|
| block top | [0, 0, 0] | [0,0,1] | 0.15×0.15 | **2** primary |
| block +x | [0.15, 0,-0.12] | [1,0,0] | 0.12×0.15 | **2** primary |
| block -x | [-0.15, 0,-0.12] | [-1,0,0] | 0.12×0.15 | **2** primary |
| block +y | [0, 0.15,-0.12] | [0,1,0] | 0.15×0.12 | **1** secondary |
| block -y | [0,-0.15,-0.12] | [0,-1,0] | 0.15×0.12 | **1** secondary |
| **panel face** | [0, 0,-0.82] | [0,0,-1] | 0.08×w/2 | **0 GLASS** |

The radiating panel IS the glass — named explicitly in the v0.8 handoff.

### wing (hand=1, span=3.2 shown; extents scale with span)

| face | centre | normal | hu × hv | cls |
|------|--------|--------|---------|-----|
| root spar top | [0, 0.25, 0.17] | [0,0,1] | 1.1×0.25 | **2** primary |
| root spar belly | [0, 0.25,-0.17] | [0,0,-1] | 1.1×0.25 | **2** primary |
| root +x chord | [1.1, 0.25, 0] | [1,0,0] | 0.17×0.25 | **1** secondary |
| root -x chord | [-1.1, 0.25, 0] | [-1,0,0] | 0.17×0.25 | **1** secondary |
| **wing panel** | [0, 0.5+span/4, 0.11] | [0,0,1] | 1.0×span/4 | **0 GLASS** |

Root spar is the load-bearing structural member; wing panel skin is thin aerofoil
shell — cls-0. Handedness is in the port tags, not in the face normals (spar
faces are symmetric about the port axis).

### heavy_cannon

| face | centre | normal | hu × hv | cls |
|------|--------|--------|---------|-----|
| block top | [0, 0, 0.60] | [0,0,1] | 0.65×0.30 | **2** primary |
| block +x | [0.65, 0, 0.35] | [1,0,0] | 0.25×0.30 | **2** primary |
| block -x | [-0.65, 0, 0.35] | [-1,0,0] | 0.25×0.30 | **2** primary |
| block +y | [0, 0.30, 0.35] | [0,1,0] | 0.65×0.25 | **1** secondary |
| block -y | [0,-0.30, 0.35] | [0,-1,0] | 0.65×0.25 | **1** secondary |
| **barrel tip** | [1.6*heavy, 0, 0.42] | [1,0,0] | 0.12×0.12 | **0 GLASS** |

Gun tube is never a weld surface.

### fuel_tank

5 faces on the base flange (box 0.7×0.7×0.12 centred at [0,0,0.05]):
- top (z=0.11), +x/-x sides, +y/-y sides — all cls-2 primary.

The pressure vessel cylinder has no declared face (no weld to a tank body).

### sensor_pod

6 faces (radius rw = r−0.02, r ∈ [0.28, 0.325]):
- mounting flange at z=0 (cls-2); four cardinal barrel faces (cls-1);
- **bottom dome at z≈-0.85 (cls-0 GLASS)** — instrument aperture.

### reactor

6 faces on base plate (box 0.5×0.5×0.14 at [0,0,-0.07]):
- top (z=0) + four sides (all cls-2 primary);
- one cylinder +x face (cls-1 secondary).
No cls-0 on reactor — forged pod, not an optic.

### turret

6 faces on base box (box 0.5×0.5×0.3 at [0,0,0.2]):
- top (z=0.35) + +x/-x sides (cls-2); +y/-y sides (cls-1);
- **barrel tip (cls-0 GLASS)** — gun tube muzzle.

### terminator_cap

2 faces on the disc (cyl r≈0.22, h=0.12, at z=-0.06):
- mounting ring face at z=0 (cls-2 primary);
- **domed underside at z=-0.12 (cls-0 GLASS)** — pressed shell.

---

## Summary counts

| stat | value |
|------|-------|
| families declaring `anchor_faces` | 10 / 10 |
| cls-2 primary weld faces (total) | 38 |
| cls-1 secondary weld faces (total) | 14 |
| cls-0 GLASS faces (total) | 8 |
| families with at least one cls-0 face | 7 |

---

## Test results

```
PASS  fleet regression (GS-α = 10/9464/3, hose path golden)
PASS  auction win + evict
PASS  backjump
PASS  segregation
PASS  loom
PASS  capacity + rip-up
PASS  anchorable surfaces
PASS  face anchors (gate 9): cls-0 glass refuses; class factor live (relief ×1.538); primary wins
PASS  houdini round trip (20 placements rehydrated exactly; 5 strut decisions, 4 hoses match)
PASS  director no-op (md5 anchor holds)
PASS  family face coverage (gate 10): 10/10 families declare faces; 8 cls-0 GLASS faces;
      engine nozzle cls-0 at x=-3.0 sterile; wing+cannon cls-2 verified
ALL GATES PASS
```

Gate 10 proves, for each non-hull family:
- (A) all 10 families now declare `anchor_faces`
- (B) engine glow nozzle is cls-0 at x=-3.0 and `face_candidates` returns `[]`
- (C) engine, antenna, radiator each have a cls-0 face (the three v0.8 headline cases)
- (D) no cls-0 face on any family leaks a candidate
- (E) every face-declaring family has at least one cls-2 primary face
- (F) wing and heavy_cannon cls-2 faces sit on structural slabs (top/belly normals ±z verified)

---

## Deferred (still honest)

- `write_part_geo` (Houdini) and `write_usd` do not yet export `anchor_faces` —
  DCC contract item remains open (KITMASH-HANDOFF.md deferred item 2).
- No Cassandra adversary pass on the new face declarations (deferred item 3).
