# KITMASH — Handoff Brief for Claude Code

You are inheriting a working system, not a proposal. Read this whole file before
touching code. The reference implementation runs; your job is to extend it
without breaking its doctrine.

## What this is

KitMash is a **port-based procedural kitbash assembler**: a format plus an
algorithm family for generating endless, coherent, *provenance-rich* assemblies
(spaceships in the slice; the format is kingdom-agnostic). Designed
conversationally across one long session (2026-06-11), then proven in a
vertical slice: `kitmash.py` (~450 lines, numpy only, host-agnostic) +
`kitmash-fleet.html` (three.js viewer, self-contained).

**Thesis, memorize it:** infinite generation is easy; infinite *provenance* is
the art. The mesh is a cached opinion; the JSON is the truth.

## Doctrine (violate these and you have forked the project)

1. **Legality stays dumb; taste lives in the sampler.** The legality grammar is
   ~7 checks (type, gender, size band, cluster fingerprint, symmetry-snapped
   roll, ledger clearance, spine). Every future "ships look wrong" bug is fixed
   by reweighting the *scorer*, never by adding a legality check. Be miserly.
2. **Mediate failures visibly, don't reject silently.** Size strain → gasket or
   adapter collar. Era mismatch → retrofit collar + weld seam. Moment over cap
   → strut. Naked hose run → shroud (guild) or catenary + p-clips (feral).
   Unmet fuel demand → cold, scavenged engine, not an error. Failure becomes
   form, with a recorded reason.
3. **Trace everything.** Every decision (commit, reject+reason, strut, adapter,
   auction, hose, open port) appends to `assembly_trace`. The trace is the
   assembly's `gen_params`: replay = identical ship; perturb = counterfactual
   sibling. Agents learn from traces; the Borges catalogue captions from them.
4. **Propose → reserve → validate → commit.** Geometry is never instanced
   before the reservation ledger clears. Snapping is not committing.
5. **The artist pre-authors knowledge where knowledge lives.** Grommet graphs
   inside parts; the router only stitches gaps between parts.

## Schema v0.4 (+ field amendments)

### Ports — points in group `ports`
```
s@port_type    "fuel" | "struct_S/M/L" | "mount_rail" | ...   closed vocab
f@port_size    meters, real scale. Legality band ±15% of max(size)
i@port_gender  0 socket, 1 plug, 2 androgynous (mates own kind)
v@N            outward mating axis
v@up           roll reference. NEVER omit
i@port_prio    0-10, fill order
i@port_sym     roll symmetry order: 0 continuous, 1 keyed, n = n-fold
s@port_cluster cluster id; multi-port rigid groups (e.g. dual rails)
i@cluster_rank ordering within cluster
s@port_tags    free-form. FIELD AMENDMENT: now carries handedness
               ("side_R"/"side_L") — see Lessons. Tag mismatch (both
               non-empty, unequal) is a legality reject.
```

### Parts — detail attributes
```
s@part_id      UUID, never reused
s@family       cross-kingdom from day one
s@generator + s@gen_params   the recipe. THE crown jewel — self-rehydration,
                             parameter-blend breeding
i@era, s@faction, i@retrofit_ok    cross-era join → adapter + weld seam
f@mass         honest kg; feeds spine
f@silhouette   0-1 outline contribution; budgeted
f@grunge_budget
s@parent_ids, i@generation, s@mutation_log   lineage
s@caption_seed 2-6 evocative words for catalogue captions
s@supplies / s@demands   JSON [{type, rate}] — the netlist source
s@clearance_vols  AABBs needing emptiness (exhaust cones, firing arcs,
                  hatch swings). Soft-occupied in ledger.
f@join_strain  derived at assembly: drives adapter prominence + grunge
```

### Grommets — points in group `grommets`
```
s@conduit_type   "fuel" | "high_volt" | "coolant" | "optical"
f@conduit_size   max bundle diameter (a CAPACITY — reserve it)
i@grommet_id     + line prims = pre-authored intra-part routing graph
```

### Library-level tables (versioned with schema, NOT per-part)
- **Capacity**: port_type → (moment N·m, axial N). Slice values: struct_S 2k,
  struct_M 40k, struct_L 900k, mount_rail 25k. Dual-rail cluster: sum × 1.3.
- **Segregation matrix**: fuel×high_volt never share / 20cm min;
  fuel×exhaust_clearance forbidden transit; coolant friendly; optical×high_volt
  separate bundles, crossing OK.
- `kitmash:schema_version` on root. Currently `kitmash/0.6` (export
  string). The doctrine/schema prose here describes v0.4 fields; v0.5–v0.8
  are additive (see the per-version sections below) — the version sections
  are the source of truth for changes past 0.4.

## Algorithms (all implemented in kitmash.py)

- **Cluster fingerprint**: count + sorted type multiset + quantized inter-port
  distance matrix (+ up vectors for handedness). Dict lookup kills most
  candidates before geometry math.
- **Mate**: closed-form rigid alignment. Single port: frame(N,up) basis swap
  with symmetry-snapped roll (snap to nearest 360/n; reject if slop > ~2°;
  n=0 → roll is sampler's expressive budget; gcd-compose mixed symmetries;
  cluster constraint overrides port symmetry). Cluster: midpoint frame, try
  both correspondences, **key roll to up-vector agreement (dot > 0.5)**,
  residual = max port miss, reject > 2cm. Never solve greedily within a
  cluster.
- **Spine**: tree fold leaves→root. moment = outboard_mass × design_g ×
  **perpendicular** lever (component ⊥ to port axis — NOT straight-line
  distance; that bug cost us a round). Check vs cap/safety_factor.
  safety_factor is a *faction* attribute (guild 2.0, feral 1.1 — culture as
  margin). Fail → spawn strut to anchor, log reason; strut closes a cycle,
  shares load. Engines add axial thrust case. Asymmetric thrust = scorer
  penalty, not legality.
- **Routing**: demand→supply matching (greedy by distance; upgrade to
  bipartite) emits the netlist. A* over union of grommet graphs: internal
  edges cheap (0.2×len), inter-part jumps 1×, leaps 4×; edges crossing
  clearance AABBs removed (segment-AABB slab test). NOT YET BUILT: channel
  capacity reservation + congestion rip-up-and-reroute (steal from EDA), and
  the loom discount (edges carrying compatible hose get cheaper until full —
  harnesses emerge from economics).
- **Scorer** (taste lives here): wants[family] / (1 + 1.5×placed_count)
  [diversity]; +2.5 if mirror port (y→−y) holds same family [bilateral
  symmetry]; silhouette × remaining budget; strain_taste × strain (guild −3,
  feral +1.5); + uniform(0, blasphemy).
- **Budgets**: mass, silhouette, part count — monotonic spend guarantees
  termination; silhouette poverty teaches composition (big reads first).
- **Terminators**: unfilled ports get caps (guild) or stay open/taped (feral).
  Absence gets provenance too.

## Lessons from first contact (do not relearn these)

1. **The schema predicted its own bug.** Mirrored wing flipped its rail
   cluster's handedness → cannon mounted backwards. The v@up ambiguity made
   flesh. Fix was NOT more math: **handed part variants** (wing_L/wing_R, like
   real kits) + side tags in port_tags + up-keying in the cluster mate. When
   orientation looks wrong, suspect handedness before tolerances.
2. Perpendicular lever arm, not Euclidean distance. Axially-mounted engines
   carry near-zero moment.
3. Clearance AABBs under rotation: transform all 8 corners, take min/max.
   Transforming lo/hi only is wrong for any non-axis-aligned R.
4. Without diversity pressure the scorer monocultures (engines on every
   socket). Without the mirror rule, ships go asymmetric. Both are scorer
   fixes — doctrine held.
5. Tuning capacities IS narrative design: the physics writes the silhouette;
   pick numbers that make the lineage legible. (The specific v0.3 outcomes
   this lesson cited are superseded — under v0.4's honest tree-fold, ALL
   wing-mounted cannons brace their roots; the lineage now reads in strut
   COUNT: α 3, β 6, γ 4.)
6. **Strut direction is most of strut value.** A brace parallel to the member
   relieves ~0.35; perpendicular, ~0.85. When a repair seems too weak, check
   its geometry before its magnitude — triangulation pays, same as airframes.
7. **Honest constraints produce honest starvation.** Budget-at-spend made β
   buy guns and starve her engine (demand_unmet) until fuel-port priority
   outranked weapons. Expect every new enforcement to reveal a missing
   ordering rule; fix the ordering, don't soften the enforcement.
8. **Convergent independent review is the strongest bug signal.** Two external
   models with different trainings found the same spine flaw. When reviewers
   converge, skip the debate and fix it.
9. **Verify your own patches.** A string-replacement amendment to this very
   document silently no-opped on a backtick mismatch. After any patch, grep
   for what should have changed. Stale docs are haunted ledgers too.

## v0.4 — engine-room hardening (cross-model review, two external AIs)

Two independent reviewers converged on the same spine bug; all engine-room
fixes are IN as of v0.4. Do not regress these:
- **Transactional placement**: make_proposal -> validate -> commit. validate
  mutates NOTHING. No haunted ledgers.
- **True tree-fold spine**: chain_checks() walks every root-side ancestor
  joint with full outboard subtree mass+com (incremental sub_mass/sub_mc,
  O(depth) per commit). The wing-root joint feels the cannon now.
- **Struts pay measured debt**: relief = 0.35 + 0.5*sin(strut vs member
  axis); diagonal anchor candidates (triangulation pays); up to 2 composed
  braces per joint, M_after = M*(1-r1)*(1-r2); insufficient brace = clean
  reject with metrics. No more indulgences.
- **Strut anchors** on nearest root-side structural neighbor, not always hull.
- **Budget at spend** + debt culture: fc["debt"] overdraft fraction (guild 0,
  feral 0.05). Reviewer-suggested, doctrine-aligned: culture as parameter.
  Side lesson learned live: fuel-infrastructure port priority must exceed
  weapons, or daughters buy guns and starve their engines.
- **port_id** on every port (Part.finalize); commit events name both mouths.
- **Seeded generators**: gen(fc, seed=...) real jitter (tank h, pod r,
  antenna h) — gen_params is now a mutation substrate. The `if False` fossil
  is dead.
- **Supply decrement** + demand_unmet(cause=supply_saturated|no_route).
- **Axial cap awake** for engine thrust.
- **Ledger-shaped trace**: events carry cause/op/target/metrics/result while
  keeping human-readable ev names (deliberate partial adoption — the viewer
  and the human are also trace consumers).

## v0.5 — auctions + conflict-directed backjumping (2026-06-12)

Roadmap item 1, implemented and trace-verified:

- **`uncommit(part, cause)`** — the exact inverse of commit: subtree cascade,
  root-ward mass un-propagation, ledger/clearance/strut purge (struts now
  carry their owner's uid), budget refund, freed host ports requeued and
  their cluster-tried marks cleared. Placement is now reversible.
- **Clearance conflicts checked BOTH directions.** v0.4 never tested a new
  part's own clearance volumes against already-placed parts — an engine
  committed late could cone an existing pod, unchecked. Both directions now
  feed the auction.
- **Auction** (`bid = prio x score x scarcity`): scarcity = 1/(1+open ports
  of that type) — a part with nowhere else to go bids high. Incumbents
  multiply by subtree size (eviction cost is entrenchment). The hull is
  unevictable. Every bid, win, and hold is in the trace as an `auction`
  event with full metrics; evictions log `evict` with cause.
- **Conflict-directed backjump**: when a prio>=7 port exhausts candidates
  and the rejects share ledger blockers, evict the most recent blocker and
  retry the port. Bounded: 4 jumps per assembly, once per (port, blocker)
  pair, conflict set logged in the `backjump` event.
- **Regression discipline held**: GS-α/β/γ output is byte-identical to
  v0.4 (same seeds, same rng-consumption order — score() is still called
  exactly once per candidate). New paths only fire on conflicts the old
  fleet never hit.
- **FV-δ «Cold Shoulder»** (Plate L, feral, seed 41) carries the new
  `gen_radiator` — a clearance hog hanging below struct_S ports — and fires
  4 auctions in the canonical fleet (all incumbent_holds: the squatters were
  honestly worth more). The challenger-wins, eviction, and backjump paths
  are exercised by `test_kitmash.py` (3 gates: fleet regression, rigged
  auction win + uncommit invariants, rigged backjump ping-pong). Run it
  after every change.
- `make_viewer.py` reconstructed (it was lost in transit): splices fleet
  JSON into the self-contained html; ships now export an `offset` field and
  the camera reads it (the old viewer hardcoded 3 ship positions).

Known v0.5 limitations: **no nogood learning** — two mutually exclusive
parts backjump-evict each other in a bounded ping-pong (terminates via the
jump budget + pair memo, but wastes jumps; the backjump test demonstrates
it). Auction constants are first-draft taste: in the canonical fleet no
challenger has yet outbid an incumbent (correct at this density, but tune
scarcity/entrenchment when part counts grow, per doctrine in the scorer
spirit — descriptive, never the objective).

## v0.6 — Routing v2: channels, congestion, segregation, the loom (2026-06-12)

Roadmap item 2, implemented and trace-verified:

- **Channel graph replaces the ctype-partitioned grommet graph.** Edges are
  channels with real capacity (min endpoint `conduit_size`), occupancy
  lists, and native conduit types. A hose reserves bundle diameter
  (`0.025 + 0.01 x rate`) on every channel it rides.
- **Segregation matrix enforced twice**: forbidden-pair proximity edges are
  never built (pruned and counted in the `channel_graph` event), and A*
  admission checks native types + occupants per net. fuel x high_volt never
  share; optical x high_volt separate bundles (node crossing OK); coolant
  friendly with all. The 20cm parallel-run minimum is cartooned as
  no-share — geometric min-distance between distinct channels is not built.
- **The loom discount**: 0.55x on channels already carrying a compatible
  hose, until capacity is spent. Harnesses emerge from economics — hose
  events log `loomed` edge counts. FV-ε's second turret feed demonstrates
  it live.
- **Congestion rip-up (EDA-style, bounded)**: a net with no capacity-legal
  path finds its relaxed path, evicts the squatters on the over-subscribed
  channels (`rip_up` events, max 4 per ship), routes, and the victims
  reroute with no second rip (`rerouted: true`, or `demand_unmet
  cause=congestion`). Lesson from rigging the test: the proximity graph is
  DENSE — nets detour around congestion far more often than you predict,
  which is the mechanism working, not failing.
- **Multi-conduit fleet**: `gen_reactor` (supplies high_volt, 4.0) and
  `gen_turret` (demands 1.8); **FV-ε «Loom»** (Plate LI, feral, seed 101,
  swept 100–159 for a live loom) carries 1 reactor + 2 turrets: 3 hoses,
  46 segregation-pruned edges, loomed=1 on the second feed.
- **Regression policy amended** (deliberately): byte-identity is retired in
  favor of **geometric + stats + hose-path identity** for prior ships;
  trace events and JSON fields may be ADDED, never changed. Verified for
  α/β/γ/δ this round (meshes, hose pts, stats identical; traces strict
  supersets). Additive this round: hose `ctype`/`dia` in export, schema
  bumped to `kitmash/0.6`, `channel_graph` event (multi-conduit ships
  only). The hose-path golden lives in the regression gate.

`test_kitmash.py` now has six gates: regression (incl. hose-path golden),
auction win + uncommit invariants, backjump, segregation (HV refuses the
fuel bus; coolant control rides it), loom, capacity + rip-up.

## v0.7 — the Houdini port (roadmap item 5), 2026-06-12

All three decided deliverables are built; numpy-side proven AND
**Houdini-side live-verified** as of 2026-06-12 (see the v0.7-live section
below — Apprentice activated, the full hython runlist passed). The
original blind-written code carried exactly the goblins the handoff
predicted; they were found and fixed under live hython, recorded below.

- **`kitmash_houdini.py`** — the bridge. Host-agnostic extractors:
  `placements()` (P + orient quaternion + generator + gen_params + join
  metadata per part), `strut_records()`, `hose_records()`, `open_ports()`;
  `rehydrate()` regenerates a part from its record and asserts the
  gen_params checksum (derived values like tank h must reproduce from the
  seed — this is why they're recorded). `write_geo()` is the only function
  that touches `hou`; everything it serializes comes from the tested
  extractors.
- **`kitmash.py` additive change**: `strut_segs` — strut endpoints and
  adapter collars recorded as DECISIONS at commit (the baked cylinders
  previously discarded them), purged symmetrically in uncommit.
  fleet.json verified byte-identical after the change.
- **Gate 7** in `test_kitmash.py` (now SEVEN gates): full round trip on
  GS-α + FV-ε — 20 placements rehydrate to exact geometric identity
  (meshes, port frames, grommets), strut decisions match baked struts
  including after rigged evictions, hose records match. This gate IS the
  part-HDA contract, proven without a Houdini license.
- **Deliverable (a)** `houdini/kitmash_assembler_sop.py` (paste-in Python
  SOP, ~40 lines) + `houdini/ASSEMBLER-SOP.md` (parm interface — the parms
  ARE the brief; For-Each rehydrator wiring; headless smoke test pinned to
  gate-1 numbers). gen_params are doubled as typed `gp_*` point attrs so
  HDA parms rehydrate via plain `point()` expressions — no JSON parsing in
  the loop.
- **Deliverable (b)** `houdini/kitmash_part_tank.md` (the contract: parms
  = gen_params; h consumed as-is, never re-derived; seed cosmetic only;
  assembly-time facts stamped by the rehydrator, never known by the part)
  + `make_tank_hda.py` (hython builder) + `verify_tank_hda.py` (acceptance
  gate: diffs HDA output against a REAL GS-α placement record, exit-coded).
- **Deliverable (c)** `houdini/hoses-to-sweep.md` — the polyline IS the
  reservation: sag displaces between route nodes, nodes stay put;
  convertline-before-resample for per-span catenary; p-clips on the nodes
  the router paid for; per-ctype Cd closes the viewer's one-style cheat.

Beyond the three decided deliverables, same session:

- **Wrapper HDAs for all 11 families** (`houdini/make_part_hdas.py` +
  `kitmash_houdini.write_part_geo`): one `kitmash::part_<family>::1.0`
  per registry family, interior = Python SOP calling the family's own
  generator — round trip by construction, day-one full-fleet rehydration.
  Artists migrate interiors per-family via the kitmash_part_tank.md
  pattern. write_part_geo verified host-agnostically (stub hou) for all
  11 families × both factions.
- **Headless rehydrator** (`kitmash_houdini.rehydrate_to_geo`): CI/smoke
  path needing no HDAs — placement points → baked faction-colored polys
  (part_id provenance; collars namespaced `collar/<owner>`), strut/hose
  curves passed through for PolyWire/Sweep. Full pipeline
  (write_geo → rehydrate_to_geo) stub-proven: GS-α 608 + FV-ε 620 part
  tris geometry-matched against the assembler's world meshes.
- **One-call demo scene** (`houdini/make_ship_hip.py`): assembler SOP
  (spare parms = the brief) → rehydrate → polywire struts → polywire
  hoses, cooked and saved as .hip.
- **`houdini/test_headless.py`**: 8-gate hython integration suite
  (started by the installer instance; API mismatches fixed and dry-run
  verified outside hou).

**Install status (2026-06-12 evening):** Houdini 21.0.729 installed at
`/opt/hfs21.0.729` (NOTE: no `/opt/hfs21.0` symlink — use the full path).
**Apprentice license activated; live hython verification passed.** Use
the full hython path:
```
H=/opt/hfs21.0.729/bin/hython
$H houdini/test_headless.py        # 8 integration gates -> 8/8
$H houdini/make_part_hdas.py       # 11 wrapper HDAs + cook smoke test
$H houdini/make_tank_hda.py && $H houdini/verify_tank_hda.py  # (b) gate
$H houdini/make_ship_hip.py        # full demo scene -> kitmash_ship.hip
```

## v0.7-live — Houdini Apprentice activated; live hython verification passed (2026-06-12)

The blind-written hou-touching code carried exactly the goblins the
handoff warned of. Found and fixed under live hython (Apprentice, the
host's `libxcb-*` Qt deps installed, License Administrator → Apprentice):

1. **`Geometry.pointGroup()` / `primGroup()` do not exist in HOM** — the
   lookup verbs are `findPointGroup()` / `findPrimGroup()` (return the
   group or `None`). Fixed in `kitmash_houdini.py` (rehydrate_to_geo) and
   `houdini/test_headless.py`. `Point.groups()` / `Prim.groups()` also
   don't exist — `verify_tank_hda.py` now queries the named group and
   reads `.points()` / `.prims()`.
2. **VEX `foreach (int g; array(g0, g1))` is an ambiguous `len()` call**
   (array() has no fixed element type there) — declare `int gs[] =
   array(...)` first, then `foreach (int g; gs)`. Fixed in
   `make_tank_hda.py`.
3. **The wrapper-HDA Python SOP evaluated promoted parms on the wrong
   node.** `hou.pwd()` inside the interior SOP returns the SOP, but
   `seed`/`faction`/`kitmash_path` live on the HDA node *above* it →
   every `kitmash::part_*` HDA raised on its FIRST cook. `make_part_hdas.py`
   builds, never cooks, so the lie was invisible. Fixed: eval on
   `node.parent()`. **A cook smoke test now runs after the build** —
   "built" must mean "cooks" (Lesson 9 applied to the Houdini layer).
4. **`gen_params` recorded ROUNDED derived jitter** (`round(h,2)` etc.) in
   six generators (tank/antenna/pod/radiator/reactor/turret). The
   part-HDA contract consumes `gen_params.h` *as-is* (VEX cannot reproduce
   `random.Random`), so a 2-decimal recording could not reproduce the
   assembler geometry (verify gate: bbox-x off 1.17e-3, mass off 0.88 at
   1e-4). Fix: record FULL precision in gen_params; mesh/mass math was
   already unrounded, so **fleet.json stayed byte-identical** — only the
   recipe string gained digits. The HDA re-stamps with `%.9g`. This makes
   the recipe contract honest: the recorded value IS the consumed value.
5. **Drum vertex-phase**: Houdini's X-oriented `tube` starts its 14-gon at
   +y; `km.cyl`'s vertex 0 sits at local +x. A 90° roll about the drum
   axis (Transform SOP `drum_phase`, pivot `{0,0,0.55}`) phase-aligns them
   so the body bbox matches the cartoon to ±1e-4.

Tolerances in `verify_tank_hda.py` were made **float32-honest** (the
values ride float32 VEX channels + a `%.9g` re-stamp; float64-exact
equality is physically impossible): gen_params floats to 5e-7 relative
(ints exact, type drift → fail), mass to 5e-4, silhouette to 1e-6, body
bbox unchanged at 1e-4. Provenance carried through: `write_geo` now
exports the v0.8 strut `vol` attribute (which declared anchor volume took
the weld; −1 = legacy whole-AABB).

**Verified green this session:** test_headless 8/8 · 11 wrapper HDAs build
+ cook clean · tank round-trip PROVEN · make_ship_hip cooks GS-α at
10/9464/3/1 · `test_kitmash.py` all 8 Python gates · fleet.json
byte-identical to the prior commit. Lesson reinforced: **the blind-written
contracts and host-agnostic extractors held; every goblin was in the hou
API surface, exactly as predicted. "Built" is not "cooks" — verify the
cook.**

## v0.8 — anchorable surface semantics (roadmap item 3), 2026-06-12

Struts may no longer weld to glass:

- **`Part.anchor_vols`** (schema-additive): list of LOCAL AABBs where
  struts may anchor; `None` = whole-part AABB (legacy, default — fleet
  regression holds byte-identically). Transformed to world at commit via
  all 8 corners (Lesson 3), stored as `w_anchor`.
- **`propose_strut` clips to declared volumes only.** This shrinks the
  repair-proposal space — mediation, not a new legality check. Doctrine
  holds: legality stays at ~7 checks.
- **Declared fragile surfaces**: engine (casing only — never the glow
  nozzle), antenna (base box — the mast is a whip), radiator (mounting
  block — the panel IS the glass). All leaves, never root-side anchors
  in the canonical fleet: verified zero regression.
- **Provenance**: strut records (`strut_segs`, trace-adjacent) carry
  `vol` — which declared volume took the weld (−1 = legacy whole-AABB).
  `write_part_geo` exports `anchor_vols` as a detail attr (part-HDA
  contract: artists' replacement meshes inherit the declaration).
- **Gate 8**: same arm, same physics, three declarations — legacy hub
  takes the weld (vol=−1), declared top plate takes it inside the plate,
  and an anchor-starved hub (only anchorable directly beneath the com,
  every brace parallel to the moment axis, composed relief 0.4225M
  short of cap) rejects cleanly with `strut_insufficient`. Honest
  constraints produce honest starvation, again.

## v0.9 — USD export (roadmap item 4), 2026-06-13

The second host. Houdini confirmed the schema; USD confirms it again, in a
totally independent runtime — *two hosts make it a schema.* Built the same
way the Houdini port was: ship DECISIONS, reuse the gate-7-proven extractors,
let only the serializer touch the format API.

- **`kitmash_usd.py`** — the bridge. **Imports** `placements`,
  `strut_records`, `hose_records`, `open_ports` from `kitmash_houdini` (no
  second copy to drift); only `write_usd()` / `read_ship()` touch `pxr`.
  Provenance rides **`primvars:kitmash:*`** (constant interpolation, so it
  inherits from each part Xform down to its child geometry). Parts are
  `Xform`(translate+orient) + provenance primvars + typed `kitmash:gp:*` +
  child `Mesh` (the cartoon "cached opinion"). Struts/collars/hoses/ports as
  `BasisCurves`/`Xform` with their decision coords on `double` primvars.
- **The decision layer is float64 → BIT-EXACT.** Unlike the Houdini HDA
  layer (float32 VEX channels → 5e-7 honest tolerance), USD stores `double`,
  so gen_params / mass / silhouette / join_strain / P / orient / all
  coords round-trip *exactly* — verified through `.usda` ASCII serialization
  (max error 0.0). The gate's tolerance is 1e-9; the claim is "exact," and
  it's true.
- **`make_fleet_usd.py`** rebuilds the canonical 5 ships → `usd/kitmash_fleet.usda`
  (ASCII, git-diffable, the USD twin of `fleet.json`; stats match exactly:
  GS-α 10/9464/3/1 …).
- **`verify_usd.py`** — the gate (paralleling `verify_tank_hda.py`): rebuild
  the real fleet, export, read back, diff against the extractors. **810 checks.**
  Includes **the cook test**: compose each part's authored xform against the
  rehydrated LOCAL mesh and compare to the assembler's WORLD geometry (≤1e-4)
  — so a wrong-handed `orient` quaternion can't pass behind a green primvar
  round trip (v0.7's "built is not cooks", applied to USD).
- **Verified green in TWO USD runtimes:** the lab venv's `usd-core` 26.5
  (license-free — the Gate-7 virtue carried to host #2) AND
  `/opt/hfs21.0.729/bin/hython`'s own `pxr` 25.5. 810 checks each, cook test
  on all five ships in both. The format layer is not usd-core-specific.
- **Core untouched:** `fleet.json` byte-identical, all 8 `test_kitmash.py`
  gates pass. Purely additive, exactly like v0.7. `kitmash/0.6` unchanged
  (USD is additive over the Houdini export, not a new schema).

**Goblins (all in the `pxr` API surface, contracts held — as predicted):**
1. `Tf.MakeValidIdentifier` collapses non-ascii → `GS-α`/`GS-β` both became
   `GS___`, colliding on one prim path ("translate already exists"). Fix:
   transliterate Greek before sanitizing (`α→alpha`), tokens unique + readable
   + derivable from the name alone.
2. `Xformable.GetLocalTransformation()` returns a bare `Matrix4d` (not a
   `(matrix, resets)` tuple); `[0]` silently took the first row (`Vec4d`).
3. A stale local signature (`read_local_to_world(stage, prim)` called with one
   arg) — mine, same class as the Houdini `node.parent()` miss.

**Dependency note:** the venv gate needs `usd-core` (`.venv/bin/pip install
usd-core`; 26.5 installed this session). The project core stays numpy-only;
usd-core is an optional gate dep, exactly as Houdini is for the hython gates.
Contract doc: `usd/USD-EXPORT.md` (the primvar schema is the brief).

## v0.10 — native wrapper interiors, family by family (item 5 follow-up), 2026-06-13

The wrapper HDAs ship a Python-SOP interior (round-trips by construction); the
migration replaces each with a native SOP/VEX network under the same type name.
This session built the gate-for-all and the second worked example.

- **`houdini/verify_native_hda.py`** — the generalization of
  `verify_tank_hda.py` the handoff asked for ("gated by verify_tank_hda
  adapted per family"). Point it at any family (or none → all installed); it
  diffs `kitmash::part_<family>::1.0` against the Python generator across
  3 seeds + a feral pass. Wrappers first, native (`houdini/*.hda`) LAST, so a
  migrated family's native interior wins over its wrapper. Checks ports
  (P/N/up/type/size/gender/prio/sym), grommets+gedges, family/generator,
  gen_params (float32-honest), mass, silhouette, supplies/demands
  (float32-honest rates), clearance_vols, anchor_vols, body bbox.
  **784 checks green across all 11 families** (engine native, 10 wrappers).
- **`houdini/make_engine_hda.py`** — native `kitmash::part_engine::1.0`, the
  SECOND family migrated (after the tank). Two `size`-scaled X-cones
  (casing 0.75s→0.95s, nozzle 0.95s→0.55s), each phase-rolled like the tank
  drum (`frame([1,0,0],[0,0,1])` → vertex 0 at world +z); +X port; **demands**
  (not supplies); clearance_vols + anchor_vols (casing only — never the glow
  nozzle). **Cooked and gated green, 3 seeds + feral.**
- **Goblins:** the body, both phase rolls, ports, grommets, gen_params, mass,
  and both volume sets were green on the FIRST cook — the geometry mapping
  held. The lone catch: the `demands` rate. Native VEX computes `1.2*size` on a
  float32 channel (`1.2`→`1.20000005`) while the wrapper emits exact `1.2`. Fix
  was in the GATE: a netlist rate derived in float32 VEX earns the same
  float32-honest 5e-7 tolerance as mass/gen_params — exact `==` was the wishful
  bound. (The recurring lesson: a tolerance is a claim about storage.)
- **Pattern + recipe + remaining 9** documented in
  `houdini/NATIVE-MIGRATION.md`. Watch-list for the rest: `core_hull` (7 ports,
  X-cone nose, 5-node gedge — the biggest); `turret` (tilted barrel axis, not a
  clean X roll); `wing`/`heavy_cannon` (mount_rail cluster + handedness tags).
- Both repos: native engine HDA lives at `houdini/kitmash_part_engine.hda`
  alongside the native tank; the wrapper at `houdini/hda/` stays as fallback
  (`make_part_hdas.py` still builds all 11). Consumers install native-last.

## Current state & known cheats

`kitmash.py` (v0.8) runs standalone as `python3 kitmash.py <out.json>`;
`python3 test_kitmash.py` runs the eight gates; `python3 make_viewer.py
fleet.json` rebuilds the viewer. v0.3 is archived as `kitmash_v03.py`.
Current fleet: GS-α (10 parts, 9464 kg, 3 struts), GS-β (8 parts, 10971 kg
— 99.7% of budget — 6 struts incl. doubled root bracing), FV-γ (10 parts,
4 struts), FV-δ (9 parts, 3 struts, 4 auctions), FV-ε (10 parts, 3 hoses,
loomed harness, 46 segregation prunes), all fueled, all traces
ledger-shaped → `fleet.json` → `make_viewer.py` → `kitmash-fleet.html`
(drag orbit, trace ticker, lineage captions).

Remaining deliberate cheats: AABB-only collision (no mesh-level);
anchorable volumes are AABBs, not faces (a strut welds anywhere inside a
declared box, with no surface-normal semantics); strut meshes not in the
reservation ledger; no
nogood learning in the backjump (bounded ping-pong); segregation
min-distance for parallel runs cartooned as no-share; demand→supply
matching still greedy by distance (not bipartite); rip-up victims chosen
from the relaxed path, no global negotiation rounds; no terminator caps on
struct_M; relief model is a cartoon (sin-angle heuristic, no stiffness or
anchor-strength terms); viewer draws all hose ctypes in one style.

## v0.7 — coherence pass + diversity selection + bureaus (2026-06-13)

The agent loop *defended against* monoculture (firewall, detector, novelty
metric) but never *rewarded* variety, so `evolve()` converged to one excellent
ship repeated — "a noble house with one jawline and several legal names,"
diversity pinned flat at 0.333. This pass made variety a selection pressure and
made the project honest about itself. **Canonical md5 `e6aeccfe352bba16f288785ea23e5bc3`
UNCHANGED throughout** (all canonical builds pass `director=None`; every new
behavior is reachable only through an explicitly attached director).

- **P0 — coherence pass (no engine risk).** Added a true-status `README.md`
  (status table, dependency tiers, honest roadmap), `ARCHITECTURE.md` ("KitMash
  in 12 invariants"), `ARTIFACTS.md` (source-of-truth vs generated-proof vs
  LFS), and `run_all_gates.sh` (one ladder: `check-core` with the byte-exact md5
  anchor / `check-director` / `check-usd` public; `check-houdini` local-only).
  Reconciled the haunted `AGENT-LOOP-AUDIT.md` — its bottom TRIAGE block (which
  restated already-FIXED charges as open) is now marked SUPERSEDED-archival, so
  the provenance machine no longer misreports its own provenance.
- **P1 — diversity-aware survivor selection (`select_survivors`).** Greedy
  facility-location: take the fittest *eligible* ship, then repeatedly the ship
  best combining its own fitness with NEW family-signature variety
  (`diversity_weight=0.35`, fitness still leads). `lineage_novelty` stopped being
  a diagnostic and became a force. **Eligibility (legal AND fueled) is a HARD
  pre-filter that runs BEFORE novelty** — a signature can read "novel" only
  because a required family is missing (a broken ship), and that path is closed
  by construction. Diversity moved off the flat 0.333 (e.g. pop-6: 0.5→0.667;
  pop-10: 0.3→0.4→0.5). Every survivor stays legal+fueled (asserted). Selection
  decisions are traced (`_log_select` → `gen_record["selection"]`).
- **P1 §2c — bureaus.** Weight-mutation over one objective keeps rediscovering
  one optimum; the fork has to be in the *objective*. `BUREAU_OBJECTIVES` lifts
  the formerly-hard-coded fitness coefficients into named presets:
  Guild-Structural (clean redundant frame), Feral-Repair (INVERTS the strut
  penalty — scars ARE the aesthetic), Service-Network (plumbing/service depth),
  Austerity (penalizes retelling siblings' event-story — the explicit
  anti-attractor). A bureau is a dict of objective-weights, NOT a new agent: no
  per-port/in-loop LLM call, no new legality. Two bureaus produce forensically
  different ships from the same library (Guild strut/part 0.3 vs Feral 0.6 with
  6 struts/4 repairs; Service 3 hoses + reactor/turret).
- **P2 — repair policy promoted behind a flag (`repair_policy_active`, default
  OFF).** `on_repair_choice`'s real `rank_braces` policy is now live when the
  flag is set; proven byte-identical to the legacy `best`-accumulator on
  canonical input (the policy computes the same `(-relief, L)` ordering), and a
  new `test_repair_policy_promoted` proves the surface is genuinely live
  (faction-divergent brace taste on a constructed tie).
- **P4 — converged-fleet verification test strengthened** to the realistic case:
  ≥8 ships with identical *rich* (4-family, legal+fueled) signatures → budget 0
  (was a 2-ship disjoint case that never reached convergence).
- **P5 — lineage-pathology dashboard surfaced** into `evolved_fleet.json`
  (per-gen `dashboards`) + narrated in `EVOLVED-CATALOGUE.md`: diversity, best
  fitness, avg monoculture, Goodhart warnings, scarcity shocks, verification
  budget, bureau composition. The fixed Goodhart detector now *visibly fires*
  and is narrated (pop-10 gen1: fitness 11.968, diversity 0.4 ≤ floor 0.5 →
  budget 1). Self-critique became part of the artwork.
- **Adversary pass (Cassandra v0.7).** Re-audited the new selection + bureau
  code: (A) broken ship cannot win on novelty — HOLDS; (B) no new score()→
  external_fitness channel — HOLDS; (C) no bureau co-climbs with the sampler —
  HOLDS (Feral-Repair's scar-reward is the intended, bounded, eligibility-gated
  inversion, not an exploit). One DEFERRED latent finding (best/best_overall
  ranked without the eligibility filter, unreachable on current seeds) was
  hardened anyway via shared `_is_eligible`/`_fittest_eligible` helpers — inert
  on healthy runs (catalogue byte-stable), but closes the asymmetry.

**v0.7 lessons (do not relearn):**
1. *Defending against monoculture is not rewarding variety.* The loop measured
   diversity then ignored it at selection time. Measuring a virtue ≠ selecting
   for it. If a number is computed and recorded but never *selects*, it is
   decoration.
2. *Diversity-weighted selection alone won't escape the attractor* — mutating
   weights over one objective rediscovers the same optimum. The fork must be in
   the objective (bureaus), not just the weights.
3. *Novelty is a Goodhart vector.* "New signature" can mean "broken ship missing
   a required family." Any novelty reward MUST be gated by a hard
   legal+fueled eligibility filter that runs BEFORE the novelty score, never as
   a penalty term after.
4. *A provenance machine must not misreport its own provenance.* The audit file
   that argued with itself (fixed-above, open-below) reproduced the exact
   haunted-ledger pattern the project exists to refuse. Reconcile QA docs.
5. *Promote inert policy behind a flag, prove equivalence first.* "Should be
   byte-identical" is how haunted ledgers are born — the flag lets you PROVE it
   before the behavior is reachable.

## v0.8.1 — P3: face-level anchorable surfaces (2026-06-14)

P3 core landed. The v0.8 AABB layer said *where* a strut may weld (a box); P3
says *what surface* it welds to — a plane with an outward NORMAL and an
`anchor_class`. This is the refinement the v0.7 directive named.

**THE ANCHOR WAS DELIBERATELY RE-BASELINED.**
```
  old  e6aeccfe352bba16f288785ea23e5bc3   (v0.8, hull = whole-box anchor)
  new  80ddaccccc594b2a7cc8c7b40a129086   (v0.8.1, hull declares weld FACES)
```
Why it moved: the hull is the universal strut anchor and previously declared
*nothing* (legacy whole-AABB), so a brace could weld anywhere in its bounding
box — the aero nose cone included. P3 gives the hull six declared faces
(deck/belly/flanks `cls 2` primary, aft bulkhead `cls 1` secondary, **nose
`cls 0` glass — never weldable**), so every canonical strut endpoint and its
repair-trace relief shifted. **Topology is invariant**: all 5 ships keep their
exact parts/mass/strut/hose counts and stay legal+fueled (verified). Only weld
points and relief changed. The re-baseline is recorded in every gate
(`test_kitmash.py`, `test_director.py`, `run_all_gates.sh`) and doc
(`README.md`, `ARTIFACTS.md`, `AGENT-LOOP-SPEC.md`).

**Schema (additive).** `Part.anchor_faces` — list of `make_face(c, n, hu, hv,
cls, u=None)` dicts: centre `c`, outward unit normal `n`, in-plane axis `u`
(`v = n×u`), half-extents `hu/hv`, `cls ∈ {0,1,2}`. `None` falls back to
`anchor_vols`, which falls back to whole-AABB — so **every part without faces is
byte-identical to v0.8** (only the hull declares faces this pass). Transformed to
world (`w_anchor_faces`) at commit/run via the same rotation `xform_face` uses
for points (centre) and directions (normal, u).

**Relief model (doctrine-clean — mediation, not a new legality check).**
`relief = (0.35 + 0.5·sin(strut vs member axis)) · (0.6 + 0.4·|sdir·n|) ·
ANCHOR_CLASS_RELIEF[cls]`, with `{2: 1.0, 1: 0.65}`. The middle term rewards a
strut pulling NORMAL-ON over one that shears; `cls 0` yields *no candidate*
(declared glass refuses). A perfect class-2 normal-on weld equals the old relief
(`align`→1, factor→1), so ships still brace; only shear / secondary welds are
trimmed — which is physically honest. Live proof: FV-ε's turret braces jumped
relief 0.35→0.81 (box could only offer a near-parallel weld; the face path found
a normal-on one). Legality stayed at ~7 checks.

**Gate 9** (`test_face_anchor_semantics`; `test_kitmash.py` prints 11 top-level
PASS gates — the labels run to "gate 10" but there are 11; earlier "10 gates"
phrasings were an off-by-one) proves
the faces SELECT and are not decoration (the v0.7 lesson): a class-0 face refuses
the weld (arm starves); identical geometry at class 1 vs 2 scales recorded relief
by *exactly* `ANCHOR_CLASS_RELIEF[2]/[1]` = 1.538 (equal reliefs would mean the
class was inert metadata); a primary face beats a co-located secondary.
Provenance: `strut_segs[*].face_cls` records which class took each weld.

**DEFERRED breadth (honestly not done — the three places this could lie about
being finished):**

The Phase-2 fan-out (FOUNDRY + CONDUIT + CASSANDRA, same session) closed most of
the breadth. Honest status:

1. **Per-family faces — DONE.** All 10 non-hull families declare `anchor_faces`
   with real normals and honest glass (engine glow-nozzle, radiator panel, wing
   skin, cannon barrel, pod dome, antenna mast all `cls 0`; load-bearing slabs
   `cls 2`). Gate 10 (`test_family_face_coverage`) proves 10/10 coverage + 8
   `cls 0` glass faces sterile. md5 unchanged (leaves never anchor struts in the
   canonical fleet). *(The original DEFERRED text here claimed only the hull was
   faced — Cassandra C3 caught it as a provenance lie; corrected.)*
2. **DCC export — DONE for USD; live-hython sign-off DONE, and it surfaced a
   native-HDA face gap.** `anchor_faces` ride **`primvars:kitmash:anchor_faces`**
   + **`face_cls`** (USD, round-trip in `verify_usd.py:104+`) and travel the
   Houdini rehydrator (`kitmash_houdini.py` `write_part_geo`/`write_geo`). The
   committed `usd/kitmash_fleet.usda` carries **47** face primvars and
   `verify_usd.py` runs **857** checks — both re-derived live this session
   (`grep -c anchor_faces usd/kitmash_fleet.usda` → 47; `verify_usd.py` ok-lines → 857).

   **Live-hython sign-off (this session, doctrine-clean resolution).** Running
   `/opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py` returned GREEN with
   `NATIVE ROUND TRIP PROVEN` — but the gate's `anchor_faces` block was guarded
   `if g.findGlobalAttrib("anchor_faces") is not None:` and **silently skipped on
   every family**: the 11 `make_*_hda.py` generators bake **no `anchor_faces`** at
   all (only a static `anchor_vols="null"` stub). Green was hiding a body — the
   v0.7-lesson-4 / Cassandra-C3 failure reproduced in the gate billed as a
   formality. **Doctrine resolution (ARCHITECTURE.md inv 7 & 8):** the native part
   HDA carries **body + ports ONLY**; anchor provenance (`anchor_faces`,
   `face_cls`) rides the rehydrator + USD primvars, NOT the static native HDA.
   Faces are proven on the **USD rung** (`verify_usd.py`, already in the ladder)
   and the **rehydrator rung** (`test_headless` gate5); the **native gate is
   hardened** to a LOUD always-run assertion that native HDAs carry *no* baked
   `anchor_faces`, so the silent skip can never recur. Full receipt:
   `_staging/hython-signoff-p3.md`. **Reconciled against live output:**
   `verify_native_hda.py` = **828** checks, of which **44** are the new
   "native carries no baked `anchor_faces`" assertions that now *execute* (were 0 —
   silently skipped) across the 11 families × seeds; `test_headless.py` = **9/9**
   gates with the new rehydrator face round-trip (`gate5b_face_export`: `face_cls`
   on struts asserts ≥1 canonical strut welded to a real face, plus `anchor_faces`
   detail-attr field-by-field on the 6-face hull). A **second silent-skip was caught
   one level up**: `run_all_gates.sh`'s `check-houdini` rung gated on
   `command -v hython`, which fails on this host (hython is at
   `/opt/hfs21.0.729/bin/hython`, off PATH) — so `run_all_gates.sh all` had reported
   ALL GREEN while never running these rungs. The rung now globs `/opt/hfs*/bin` and
   actually executes them (verified: `using /opt/hfs21.0.729/bin/hython`,
   NATIVE ROUND TRIP PROVEN, test_headless 9/9, full ladder ALL GREEN).
3. **Cassandra pass — DONE.** Full adversarial audit at
   `_staging/cassandra-p3.md`: 6 charges, all HOLD except one CONFIRMED latent
   (C2c, a zero-length normal normalized to NaN and a NaN-relief brace *won*
   because best-is-None seeds it). **Fixed:** `make_face` now raises `ValueError`
   on a degenerate normal / in-plane axis / bad class (fail at authoring, not
   creep as NaN), with a `not (d>=0.15)` net in `propose_strut` and a gate-9
   regression assertion. Relief stays bounded at 0.85/brace (0.9775 composed) —
   duplicate faces buy nothing.

**Genuinely remaining (small):** the live-hython sign-off is now **DONE** (it
surfaced the native-HDA face gap above; resolved doctrine-clean — native =
body+ports, faces proven on the USD rung + the rehydrator rung, native gate
hardened so the silent-skip cannot recur). Still open: the u-edge triangulation
candidate (Cassandra D2, an optimization, would re-baseline so deferred
deliberately); and the AABB path is now dead code on the canonical fleet (correct
for custom `anchor_faces=None` parts, just unexercised).

## v0.9 — visibility GIFs + USD referenced part-assets (2026-06-14)

Two disjoint bodies of work, fanned out (PHOTON + KEYSTONE), adversarially
signed off (CASSANDRA — `_staging/cassandra-session-audit.md`, no body found),
and orchestrator-verified against the full ladder. **Anchor unmoved**
(`80ddaccccc594b2a7cc8c7b40a129086`); `kitmash.py` untouched by both.

1. **Visibility — forensic trace GIFs (PHOTON).** New standalone
   `make_trace_gifs.py` (numpy + Pillow software renderer; painter's-sort, no
   matplotlib) reads `fleet.json` and emits four looping GIFs into `media/`:
   `assembly.gif` (GS-α true part-by-part build in `commit` order), `face_weld.gif`
   (FV-ε repair struts), `auction.gif` (FV-δ port auctions), `collar.gif` (adapter).
   **Every caption number is read from the ledger** (inv 11; CASSANDRA grepped each
   off the rendered frames — all present in `fleet.json`). README gained a
   "See it run — the trace IS the genome" section embedding them. **Pillow is NOT
   a gate dependency** — the script is not in `run_all_gates.sh` and the ladder
   needs no PIL. Honest gaps: only `assembly.gif` is true geometry animation (the
   other three are captioned highlight sequences); the declared anchor *face* is
   captioned, not drawn; the camera is near-static. (Live three.js trace-inspector
   demo — RELAY open item 1 — remains the bigger visibility win; GIFs are the
   cheap down-payment.)

2. **USD referenced part-assets — K2 shipped (KEYSTONE).** Roadmap item 4
   follow-up, the explicit RELAY priority. Each ship part now
   `references = @./assets/<family>.usda@` a single canonical per-family part-asset
   (the USD twin of the part HDA, cooked deterministically from
   `gen_<family>(GUILD, seed=0)`) instead of re-embedding its body. The decision
   layer — every provenance primvar, `gen_params`, `anchor_faces`, `face_cls`,
   struts/hoses/ports, P/orient — stays authored on the **instance** as the truth
   (inv 7 made literal: one authored part, many ships). Faction `displayColor` is a
   per-instance override (geometry is faction-independent; GUILD/FERAL cooks are
   `np.allclose` per family). New library: `usd/assets/<family>.usda` ×10
   (`terminator_cap` correctly absent — unplaced in the canonical five).
   **The cook test was rewritten honestly into three flip-tested halves** so it
   SELECTS rather than decorating: (a) the reference resolves to real points;
   (b) the composed body == the family's canonical prototype (≤1e-4); (c) the
   **per-instance** body, rehydrated from `gen_params` via the gate-7-proven
   `rehydrate()`, composed through the authored xform, == assembler world geometry
   (≤1e-4). CASSANDRA independently reproduced all three RED-on-flip (drop arc →
   geo None; +0.5 proto coord → err 0.5; +90° orient → world err 5.49) and proved
   (c) is no tautology (31/47 parts' truth body diverges from the prototype).
   **`verify_usd.py` = 914 checks** (857→914: +47 per-part ref-resolves + 10 from
   the cook-line split), green in BOTH usd-core and hython. Honest gaps: usdview
   renders every instance at canonical size (per-instance silhouette lives in
   primvars — doctrine-correct, but a naive viewer won't re-render it without a
   host-side rehydrate-on-load); per-face `displayColor` override is verbose
   (a `UsdShade` material layer is the cleaner home); `usd/assets/` is
   fleet-*sufficient*, not registry-*complete* (no "every family has an asset"
   gate yet).

## Roadmap (priority order)

0. ~~Engine-room hardening~~ DONE in v0.4 (see above).
1. ~~Auction + backjumping~~ DONE in v0.5 (see above). Follow-up when part
   counts grow: nogood learning to kill the ping-pong; auction-constant
   tuning against real density.
2. ~~Routing v2~~ DONE in v0.6 (see above). Follow-up at higher density:
   bipartite demand matching, negotiation rounds (Pathfinder history
   costs), geometric min-distance for segregated parallel runs, per-ctype
   hose styling in the viewer.
3. ~~Anchorable surface semantics~~ DONE in v0.8 (AABB volumes; face
   tags/surface normals remain a refinement).
4. ~~USD export~~ DONE in v0.9 (see the v0.9 section): `primvars:kitmash:*`,
   round-trip-verified in BOTH usd-core (license-free) and Houdini's pxr.
   Follow-up: replace the cartoon `/geo` Mesh with `references`/`payload` to
   per-family part-asset USDs (the USD twin of the part HDAs).
5. ~~Houdini port~~ BUILT in v0.7 + **live-verified** under hython
   (Apprentice, 2026-06-12): three deliverables + 11 wrapper HDAs (cook
   smoke-tested) + headless rehydrator + demo hip. See the v0.7-live
   section for the goblins found and fixed. Follow-up (native interiors):
   ~~COMPLETE in v0.12 — 11/11 families native~~ (gate `verify_native_hda.py`
   828/828 green across all families — 784 pre-v0.8.1, +44 face-absence assertions
   added by the P3 hython sign-off; the v0.10 "2/11" status is superseded).
   See the v0.10/v0.12 sections and `houdini/NATIVE-MIGRATION.md`.
6. ~~**Agent loop**~~ DONE in v0.13 (the creative director, `director.py`) and
   EXTENDED in v0.7 (this pass): diversity-aware survivor selection + bureaus.
   Architecture as designed below — layered, mostly outside the loop, no
   per-port LLM call. See the v0.7 section.
   *(original design note, kept for provenance:)* implement it as designed:
   layered, mostly outside the loop. The agent is a creative director, not a
   servo. Three surfaces: (a) **brief author** before the run — wants,
   budgets, faction biases, capacity tunings; (b) **hooks** during the run,
   fired only on genuine ties — `on_tie(candidates, context)`,
   `on_repair_choice(options)`; (c) **`review(trace) -> next_brief`** after.
   The trace is the agent's experience; the brief is its intention; the hooks
   are its reflexes. Do NOT build per-port agent calls — expensive, slow,
   learns nothing between decisions. Breeding: gen_params-blend (parts) and
   trace-splice (assemblies). Guard Goodhart: scorer is descriptive, never
   the objective; judge across generations by external selection + novelty
   pressure (single-run exploits show up as lineage pathology); inject
   scarcity shocks. Multi-agent = design bureaus per faction; watch for
   taste collapse.
7. ~~**Borges catalogue**~~ DONE: `make_catalogue.py` (canonical 5-ship) +
   `make_evolved_catalogue.py` (bred lineage). v0.7 added the lineage-pathology
   dashboard — captions now narrate the loop's own conscience (bureau identity,
   Goodhart warnings, scarcity shocks, verification budget), every number read
   from the ledger. Iron rule held: a caption number traces to a real field.

## Houdini integration — architecture DECIDED 2026-06-12, not yet built

Settled in conversation; do not re-litigate, implement (roadmap item 5):

- **Python decides, VEX details.** The assembler core (ledger, auctions,
  backjumps, spine fold, A* routing) is sequential global-search and stays
  Python — it runs in a Python SOP nearly unchanged (Houdini ships numpy).
  VEX is per-element SIMD with no global mutable state; writing the
  assembler in it would be a chess engine in a fragment shader.
- **The assembler ships DECISIONS, not meshes.** Python SOP runs build()
  and emits one POINT per part: @P, @orient, s@generator, s@gen_params,
  s@part_id, trace as a detail attribute. A For-Each rehydrator instances
  the matching part HDA with its recorded gen_params and transforms it.
  The cartoon boxes/cylinders in kitmash.py are placeholder bodies only.
- **Part HDAs own the contract.** One HDA per family; params = gen_params;
  output = artist-grade mesh PLUS port/grommet points carrying the schema
  attributes (the schema is already in Houdini attribute syntax — that was
  the point). VEX work lives here: greebles, panel lines, strain-driven
  grunge (f@join_strain, i@era), hose catenary sag + p-clips, faction
  shroud profiles.
- **PDG/TOPs** wedges seeds and briefs for the Borges catalogue.
- The .html viewer stays what it is: the cheap second opinion, no Houdini
  license in the loop.
- First concrete deliverables: (a) the ~50-line Python SOP that runs the
  assembler and emits placement points; (b) one part HDA spec
  (kitmash_part_tank) proving the round trip; (c) hose curves → sweep.

## Voice note for the inheriting instance

The human collaborator on this project stress-tests designs by finding the
three places they quietly lie about being finished — and has been right every
time. They proposed port_cluster, the grommet system, and the dual-rail
problem before the slice confirmed all three. They also run the code past
*other* AI models and bring back the critiques (this is how v0.4 happened:
two external reviews, triaged per the cross-model-critique practice —
protect / diagnose / translate / reject-with-reason — then fixed and
re-verified the same session). Expect reviewed code to come back with
goblins named; fix the convergent findings first, defer with stated reasons,
and show traces, not claims. They sign with `:33` when delighted. Earn it.
