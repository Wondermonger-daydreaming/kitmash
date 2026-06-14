# KitMash in 12 invariants

The Rosetta doc between the long `KITMASH-HANDOFF.md` and the brief `README.md`.
Each line is a load-bearing rule. Violate one and you have forked the project.

1. **Ports are points.** A port is a point in group `ports` carrying
   `N` (mating axis), `up` (roll reference, never omitted), `port_type`,
   `port_size`, `port_gender`, `port_prio`, `port_sym`, and cluster tags.
   Geometry mates by aligning points, not by intersecting meshes.

2. **Legality is dumb.** The legality grammar is ~7 checks (type, gender, size
   band, cluster fingerprint, symmetry-snapped roll, ledger clearance, spine).
   It never grows. Every "ships look wrong" bug is fixed in the scorer.

3. **Taste lives in the sampler and the director, never in legality.** The
   scorer weights diversity, bilateral symmetry, faction fit; the director
   shapes from outside. Legality decides what is *possible*, taste what is
   *chosen* — and the two never trade places.

4. **Propose → reserve → validate → commit.** Geometry is never instanced
   before the reservation ledger clears. Snapping is not committing; the
   transaction is reversible (`uncommit` cascades the subtree).

5. **Trace everything — the ledger is the genome.** Every decision appends an
   `ev / cause / metrics / result` event to `assembly_trace`. Replay the trace
   and you get the identical ship; perturb it and you get a counterfactual
   sibling. The trace *is* the assembly's `gen_params`.

6. **Failures become form.** A rejected part, a moment-relieving strut, a
   retrofit collar, a cold scavenged engine — these are visible mediations with
   recorded reasons, not hidden errors. Mediate failure; never reject silently.

7. **JSON / USD primvars are truth; mesh is cached opinion.** The recipe and
   the ledger define the ship. The mesh is a rendering of a decision, and any
   host may re-render it without changing what the ship *is*.

8. **Native DCC bodies may change; ports may not.** A part HDA's interior (its
   greebles, panel lines, grunge) is artist-editable. Its ports and grommets
   are the contract and may NEVER move — the gate proves byte-equal schema.

9. **USD and Houdini are hosts, not sources of legality.** Export carries the
   provenance outward; it never re-decides what was legal. Legality is settled
   once, in the pure-Python core, and only transported afterward.

10. **The agent is a director, not a servo.** The director shapes the run from
    outside via the brief, nudges only at genuine ties (`on_tie`), and learns
    after (`review(trace) -> next_brief`). No per-port LLM call — the
    intelligence is in the brief authored and the trace read.

11. **Catalogue captions are forensic.** Every placard is read from the ledger
    ("dorsal armament relocated following volume concession" must name a real
    logged event). Captions are grown from `caption_seed` + trace archaeology,
    never invented.

12. **Goodhart gets audited.** The sampler's `score()` is descriptive and is
    NEVER the objective of evolution; cross-generation selection uses an
    independent `external_fitness`. The firewall between them is watched
    (lineage-pathology detector, scarcity shocks, proportional verification) —
    and the watcher itself is adversarially reviewed (`AGENT-LOOP-AUDIT.md`).
