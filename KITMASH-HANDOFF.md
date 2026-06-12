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
- `kitmash:schema_version` on root. Currently 0.4.

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

All three decided deliverables are built; numpy-side proven, Houdini-side
written-but-unverified (the 21.0.729 download was still in flight —
`houdini/install_houdini.sh` installs to `/opt/hfs21.0` when it lands;
NOTE: its pinned MD5 did not match the partially-downloaded tarball —
re-pin or drop the check once the download completes).

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

First session with Houdini installed: run `install_houdini.sh`, then
`hython houdini/make_tank_hda.py && hython houdini/verify_tank_hda.py`,
then the smoke test in ASSEMBLER-SOP.md. Expect hou-API goblins in
make_tank_hda.py (written blind; flagged); fix there, not in the contract.

## Current state & known cheats

`kitmash.py` (v0.7) runs standalone as `python3 kitmash.py <out.json>`;
`python3 test_kitmash.py` runs the seven gates; `python3 make_viewer.py
fleet.json` rebuilds the viewer. v0.3 is archived as `kitmash_v03.py`.
Current fleet: GS-α (10 parts, 9464 kg, 3 struts), GS-β (8 parts, 10971 kg
— 99.7% of budget — 6 struts incl. doubled root bracing), FV-γ (10 parts,
4 struts), FV-δ (9 parts, 3 struts, 4 auctions), FV-ε (10 parts, 3 hoses,
loomed harness, 46 segregation prunes), all fueled, all traces
ledger-shaped → `fleet.json` → `make_viewer.py` → `kitmash-fleet.html`
(drag orbit, trace ticker, lineage captions).

Remaining deliberate cheats: AABB-only collision (no mesh-level); strut
anchors clip to neighbor AABBs (no anchorable-surface semantics — a strut
could still weld to glass); strut meshes not in the reservation ledger; no
nogood learning in the backjump (bounded ping-pong); segregation
min-distance for parallel runs cartooned as no-share; demand→supply
matching still greedy by distance (not bipartite); rip-up victims chosen
from the relaxed path, no global negotiation rounds; no terminator caps on
struct_M; relief model is a cartoon (sin-angle heuristic, no stiffness or
anchor-strength terms); viewer draws all hose ctypes in one style.

## Roadmap (priority order)

0. ~~Engine-room hardening~~ DONE in v0.4 (see above).
1. ~~Auction + backjumping~~ DONE in v0.5 (see above). Follow-up when part
   counts grow: nogood learning to kill the ping-pong; auction-constant
   tuning against real density.
2. ~~Routing v2~~ DONE in v0.6 (see above). Follow-up at higher density:
   bipartite demand matching, negotiation rounds (Pathfinder history
   costs), geometric min-distance for segregated parallel runs, per-ctype
   hose styling in the viewer.
3. **Anchorable surface semantics** for struts (face tags or a surface group).
4. **USD export**: `kitmash:` namespaced primvars; the format's real test.
5. **Houdini HDA generators** emitting schema-compliant parts (the original
   host, arriving late — by design).
6. **Agent loop** — architecture is DECIDED, implement it as designed:
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
7. **Borges catalogue**: PDG-style sweep, specimen renders, captions grown
   from caption_seed + trace archaeology ("dorsal armament relocated following
   volume concession" must describe a real logged event).

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
