#!/usr/bin/env python3
"""
make_evolved_catalogue.py — the Borges catalogue of a *bred* fleet.

The canonical catalogue (make_catalogue.py) narrates the five hand-seeded ships.
This one runs the agent loop (director.evolve) and narrates what the director
BRED: a lineage of ships across generations, each one assembled by the same
machine that kept its reasons, then selected, spliced, and re-authored by the
creative director.

It is deliberately NON-DESTRUCTIVE:
  - it never touches the regression-anchor `fleet.json` or the canonical
    `CATALOGUE.*`; it writes `evolved_fleet.json` + `EVOLVED-CATALOGUE.{md,html}`.
  - it reuses make_catalogue.py's placard archaeology verbatim, so the SAME
    discipline holds: every quantitative claim in a caption traces to a real
    logged event. The bred ships' lineage sentences ("Bred from A×B by splice…")
    are read straight from each ship's own assembly record.

    .venv/bin/python make_evolved_catalogue.py [generations] [population] [seed]

License-free: pure stdlib + numpy (via kitmash). Zero network calls (the loop
is the heuristic Director, not LLMDirector).
"""
import os
import sys

import numpy as np

import kitmash as km
from director import Director
import make_catalogue as cat


HERE = os.path.dirname(os.path.abspath(__file__))

# evocative-but-cosmetic epithets; the PROVENANCE lives in the placard prose
# (seed, spine, lineage, repairs, fuel), which is read from the trace, not here.
_EPITHETS = [
    "First Light", "Seed Cast", "Even Hand", "Feral Get", "Second Draft",
    "Crossbred", "Lean Inheritance", "Scarcity's Child", "Convergent",
    "Late Splice", "Twice-Bred", "Steady State", "Narrowed", "Recombinant",
    "Last of the Line",
]


def _roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
            (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
            (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for v, sym in vals:
        while n >= v:
            out.append(sym)
            n -= v
    return "".join(out)


def evolved_fleet(generations, population, seed):
    """Run the loop and pack its ships into the (name, assembler, offset, plate)
    tuples that kitmash.export consumes. Plate numbers continue past the
    canonical Plate LI (51)."""
    d = Director()
    lineage = d.evolve(generations=generations, population=population, seed=seed)

    ships = []
    plate_n = 51                       # canonical fleet ends at Plate LI
    seq = 0
    for gr in lineage["generations"]:
        for rec in gr["ships"]:
            plate_n += 1
            a = rec["assembler"]
            fac = "EH" if a.fc["name"].startswith("High") else "EF"
            ep = _EPITHETS[seq % len(_EPITHETS)]
            # the name carries the generation tag + epithet; the «epithet» is
            # what the catalogue surfaces in italics.
            name = "%s-%d  «%s»" % (fac, seq, ep)
            offset = np.array([0.0, seq * 7.5, 0.0])
            ships.append((name, a, offset, "Plate %s" % _roman(plate_n)))
            seq += 1
    return lineage, ships


def main():
    generations = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    population = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7

    print("=== running the agent loop: evolve(generations=%d, population=%d, "
          "seed=%d) ===" % (generations, population, seed))
    lineage, ships = evolved_fleet(generations, population, seed)

    # report the loop's own verdict
    for gr in lineage["generations"]:
        legal = sum(1 for r in gr["ships"] if r["legal"])
        fueled = sum(1 for r in gr["ships"]
                     if sum(r["diagnosis"]["demand_unmet"].values()) == 0)
        vb = gr["verification"]["verification_budget"]
        print("  gen%d: %d ships  %d legal  %d fueled  diversity=%.3f  "
              "best=%s  verification_budget=%d"
              % (gr["gen"], len(gr["ships"]), legal, fueled,
                 gr["diversity"], gr["best"], vb))
    print("  warnings(goodhart): %d   best_overall: %s"
          % (len(lineage["warnings"]), lineage["best_overall"]))

    # export to the SEPARATE evolved fleet file (never the regression anchor)
    out_json = os.path.join(HERE, "evolved_fleet.json")
    fleet = km.export(ships, out_json)
    print("\nwrote evolved_fleet.json (%d ships)" % len(fleet["ships"]))

    # render via make_catalogue's archaeology — same discipline, new spine
    print()
    cat.audit(fleet)
    md = cat.render_md(fleet)
    htmlpage = cat.render_html(fleet)
    # retitle so it can't be mistaken for the canonical registry
    md = md.replace("# KITMASH PLATES", "# KITMASH PLATES — BRED FLEET", 1)
    htmlpage = htmlpage.replace(
        "<h1>KitMash Plates</h1>",
        "<h1>KitMash Plates — Bred Fleet</h1>", 1).replace(
        "<title>KitMash Plates</title>",
        "<title>KitMash Plates — Bred Fleet</title>", 1)

    with open(os.path.join(HERE, "EVOLVED-CATALOGUE.md"), "w") as f:
        f.write(md)
    with open(os.path.join(HERE, "EVOLVED-CATALOGUE.html"), "w") as f:
        f.write(htmlpage)
    print("\nwrote EVOLVED-CATALOGUE.md and EVOLVED-CATALOGUE.html (%d plates)"
          % len(fleet["ships"]))


if __name__ == "__main__":
    main()
