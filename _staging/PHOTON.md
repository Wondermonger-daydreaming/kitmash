# PHOTON receipt — forensic trace GIFs

## What I built

A standalone numpy + Pillow software renderer (`make_trace_gifs.py`) that reads
`fleet.json` and renders four looping GIFs into `media/`. It builds an
isometric-ish camera recentred on each ship's centroid, painter's-sorts every
triangle back-to-front, fills polygons with the mesh's faction `c` color shaded
by face-normal·light, and stamps a 4-line forensic caption band under each
frame. Every caption number is read from that ship's `assembly_trace`; none is
invented (proof table below).

The script is **not** wired into `run_all_gates.sh` and Pillow is never a gate
dependency (verified: `grep make_trace_gifs|Pillow|PIL run_all_gates.sh` → 0).

## Files changed / created

| File | State | Notes |
|------|-------|-------|
| `make_trace_gifs.py` | **created** | Standalone renderer, run via `../.venv/bin/python make_trace_gifs.py` |
| `media/assembly.gif` | **created** | 752 KB |
| `media/face_weld.gif` | **created** | 717 KB |
| `media/auction.gif` | **created** | 742 KB |
| `media/collar.gif` | **created** | 312 KB |
| `README.md` | **edited** | Added "See it run — the trace IS the genome" section right after the intro |

Did **not** touch any forbidden file. `git status` shows `kitmash_usd.py` as
modified — that is KEYSTONE's concurrent USD work, not mine. My footprint is
exactly README.md + make_trace_gifs.py + media/.

## GIF → trace-event provenance (the iron rule, Inv 11)

Every number in every caption was grepped out of `fleet.json` before shipping
(all 16 distinct values confirmed present):

| GIF | Ship | Drives from | Caption numbers (all in trace) |
|-----|------|-------------|--------------------------------|
| `assembly.gif` | GS-α | `seed`, 10×`commit`, 2×`repair`, `adapter`, `hose`, `stats` | per-commit `host_port`/`strain`/`mass_left` (e.g. `wing R -> core_hull#1/struct_M_2`, `4198`); repairs `29545→20000→12622`, `relief 0.57`; adapter `strain 0.109`; hose hops/leaps/`supply_left`; summary `10 parts / 9464 kg / 3 struts / 1 hose` |
| `face_weld.gif` | FV-ε | 2×`repair` (turret joint) | `moment 2045 → cap 1818 → 397`, `relief 0.81`, `result accepted` |
| `auction.gif` | FV-δ | 4×`auction` | per-auction `challenger`/`incumbent`/`scarcity`/rival `prio`+`bid` (e.g. `2.39 vs 4.22`, `scarcity 0.5`), `result: incumbent_holds` |
| `collar.gif` | GS-α | `adapter` | `strain 0.109`, `result: collar_spawned` |

Each frame's geometry is driven by the event it captions: commit frames reveal
exactly the next label's mesh-instance; repair/collar frames fade in the
corresponding `strut/adapter` brace; auction frames highlight the contested
part + its named rival.

## Sizes

assembly 752 KB · face_weld 717 KB · auction 742 KB · collar 312 KB — all well
under the 2–3 MB ceiling; 720×720, ~14 fps, ~1 s final-frame hold, loop forever.

## I looked at them

Extracted frames via `Image.seek` (NOT `ImageSequence.Iterator`, which mis-
composites disposal=2 frames and made every frame look like the final state on
first inspection — a real gotcha). With proper seek: assembly reads as a ship
(central hull, dark engine + cyan exhaust left, gold fuel tank right, wings top/
bottom, cannons, struts, cyan hose), seed intro on frame 0, mid-assembly commit
captions correct. face_weld shows FV-ε in rust/amber with orange struts welded.
auction highlights the contested parts with real bids. collar orbits GS-α and
spawns the gold collar brace. Captions legible in all four.

## Where this is NOT finished (honest)

1. **assembly.gif is the only TRUE geometry animation; the brief allowed the
   other three to be captioned highlight sequences and I took that allowance.**
   face_weld/collar do animate a strut/collar fading in, and auction does a slow
   yaw drift, but they are NOT part-by-part rebuilds. If you want auction to show
   the *eviction* as geometry (part appearing then being replaced), that's not
   done — FV-δ's auctions are all `incumbent_holds` so nothing visually changes
   hands; I caption the hold rather than animate a swap that never happened.

2. **The "weld to a declared FACE" claim is captioned, not visually proven.**
   The strut mesh draws onto the hull, but I do not render the `anchor_faces`
   themselves (the face-class 0/1/2 surfaces, the surface normal). A viewer can't
   *see* that the weld landed on a declared primary face vs. generic hull — they
   only read it in the caption. Rendering the actual anchor face polygon
   highlighted would make the v0.8.1 headline literally visible; I didn't.

3. **Camera is a single fixed pitch with only a shallow yaw drift on three of
   the four GIFs; assembly has no orbit at all (pure front-iso).** Some parts
   (e.g. the second cannon, antennas vs sensor pod) overlap in this projection
   and are hard to disambiguate without rotation. A real orbit on assembly would
   read better but costs frames/bytes; I prioritized staying under size budget
   and keeping the commit-order legible over a prettier camera.

Minor: the multi-mesh-per-commit reveal uses a heuristic (`len(idxs)//n_commits`
per label) to split a label's meshes across its commits. It is correct for this
fleet's data (cannon = 4 meshes / 2 commits = 2 each) but would mis-split if a
future fleet had uneven mesh counts across same-label commits.
