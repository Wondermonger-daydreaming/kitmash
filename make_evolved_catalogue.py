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


def _gen_dashboard(gr):
    """Build a per-generation lineage-pathology dashboard, reading ONLY fields
    that already exist in the lineage record (director.evolve / _build_and_review
    / lineage_pathology / verification_plan). Nothing here is invented:

      - diversity            ← gr["diversity"]                  (lineage_novelty)
      - best, best_fitness   ← gr["best"] / max ship fitness    (gen_record)
      - avg_monoculture      ← mean of ships' diagnosis["monoculture"]
      - warnings_fired       ← gr["trace"] goodhart_warning events (per-gen)
      - scarcity_shocks      ← ships whose brief["mutation"] carries
                               "scarcity_shock g%d"            (scarcity_shock())
      - verification_budget  ← gr["verification"]["verification_budget"]
      - anomalies            ← len(gr["verification"]["anomalies"])
      - bureaus              ← Counter of each ship's bureau identity
    """
    from collections import Counter

    ships = gr["ships"]
    monos = [sh["diagnosis"]["monoculture"] for sh in ships]
    fits = [sh["fitness"] for sh in ships]
    bureaus = Counter(sh.get("bureau") or sh["brief"].get("bureau") for sh in ships)

    shocks = []
    for sh in ships:
        mut = sh["brief"].get("mutation", "") or ""
        if "scarcity_shock" in mut:
            # carry the shock token verbatim, e.g. "scarcity_shock g2"
            tok = next((p.strip() for p in mut.split("|")
                        if "scarcity_shock" in p), "scarcity_shock")
            shocks.append({"name": sh["name"], "token": tok})

    warns = [e for e in gr.get("trace", []) if e.get("ev") == "goodhart_warning"]
    verif = gr.get("verification", {}) or {}

    return {
        "gen": gr["gen"],
        "diversity": gr["diversity"],
        "best": gr["best"],
        "best_fitness": round(max(fits), 4) if fits else None,
        "avg_monoculture": round(sum(monos) / len(monos), 4) if monos else None,
        "n_ships": len(ships),
        "warnings_fired": warns,                       # full event records
        "n_warnings": len(warns),
        "scarcity_shocks": shocks,
        "n_scarcity_shocks": len(shocks),
        "verification_budget": verif.get("verification_budget", 0),
        "anomalies": len(verif.get("anomalies", []) or []),
        "bureau_composition": dict(bureaus),
    }


def evolved_fleet(generations, population, seed):
    """Run the loop and pack its ships into the (name, assembler, offset, plate)
    tuples that kitmash.export consumes. Plate numbers continue past the
    canonical Plate LI (51).

    Returns (lineage, ships, dashboards, contexts):
      - dashboards: list of per-generation dashboards (see _gen_dashboard)
      - contexts:   list aligned with `ships`, each the forensic lineage-context
                    for that ship (its bureau, its gen's dashboard, its own
                    shock token / strut-per-part / monoculture) — all read from
                    the record, to be injected into the exported fleet dict so
                    the placards can narrate them.
    """
    d = Director()
    lineage = d.evolve(generations=generations, population=population, seed=seed)

    dashboards = [_gen_dashboard(gr) for gr in lineage["generations"]]

    ships = []
    contexts = []
    plate_n = 51                       # canonical fleet ends at Plate LI
    seq = 0
    for gr, dash in zip(lineage["generations"], dashboards):
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

            mut = rec["brief"].get("mutation", "") or ""
            shock_tok = next((p.strip() for p in mut.split("|")
                              if "scarcity_shock" in p), None)
            contexts.append({
                "gen": gr["gen"],
                "bureau": rec.get("bureau") or rec["brief"].get("bureau"),
                "strut_per_part": rec["diagnosis"].get("strut_per_part"),
                "monoculture": rec["diagnosis"].get("monoculture"),
                "scarcity_shock": shock_tok,          # e.g. "scarcity_shock g2"
                "dashboard": dash,                    # the gen-level dashboard
            })
            seq += 1
    return lineage, ships, dashboards, contexts


# --------------------------------------------------------------------------
# Forensic placard extension. The canonical placard (cat.placard) narrates the
# ASSEMBLY ledger. Here we append the LINEAGE-pathology context — the loop's own
# conscience — read from `ship["lineage_context"]` (injected post-export). Every
# clause below cites a real field; if the field is absent the clause is skipped.

# one-clause characterisation of each bureau's objective, paraphrasing the
# coefficients in director.BUREAU_OBJECTIVES (cited, not invented).
_BUREAU_GLOSS = {
    "Guild-Structural": "whose objective prizes honest, low-strut structure "
                        "(honest 2.4, in-band 1.6)",
    "Feral-Repair":     "whose objective inverts the strut penalty and rewards "
                        "the visible bracing it carries (bracing 1.8, repair 1.4)",
    "Service-Network":  "whose objective rewards intricate plumbing and service "
                        "parts (service 2.2, plumbing 1.2)",
    "Austerity":        "whose objective optimises against repetition itself "
                        "(antirepeat 3.0)",
}


def forensic_sentences(ship):
    """Lineage-pathology clauses for one ship, read from ship['lineage_context'].
    Returns a list of sentences; every number traces to a recorded field."""
    ctx = ship.get("lineage_context")
    if not ctx:
        return []
    dash = ctx.get("dashboard", {}) or {}
    out = []

    # 1. bureau identity + its objective, and (for Feral) the strut/part it earns
    bureau = ctx.get("bureau")
    if bureau:
        gloss = _BUREAU_GLOSS.get(bureau)
        spp = ctx.get("strut_per_part")
        tail = ""
        if bureau == "Feral-Repair" and spp is not None:
            tail = " — strut/part %s, the bracing made flesh" % spp
        out.append("It was bred under the %s bureau%s%s." % (
            bureau, ", %s" % gloss if gloss else "", tail))

    # 2. a scarcity shock applied to THIS ship's brief
    if ctx.get("scarcity_shock"):
        out.append("The director struck it with a %s, perturbing its budgets "
                   "and wants mid-lineage." % ctx["scarcity_shock"])

    # 3. lineage-pathology of its generation: a fired Goodhart warning means the
    #    director flagged fitness rising while diversity sat on or below the floor
    warns = dash.get("warnings_fired") or []
    if warns:
        m = warns[0].get("metrics", {})
        out.append(
            "Its generation tripped the Goodhart alarm: fitness rose to %s while "
            "diversity held at %s, on or under the floor of %s — the loop flagged "
            "its own collapse rather than rewarding it."
            % (m.get("fitness"), m.get("diversity"), m.get("floor")))

    # 4. verification budget the director raised for that generation's anomalies
    vb = dash.get("verification_budget", 0)
    if vb:
        anomalies = dash.get("anomalies", 0)
        out.append(
            "Sensing %d anomal%s, the director raised the verification budget to "
            "%d for this generation — scrutiny proportional to doubt."
            % (anomalies, "y" if anomalies == 1 else "ies", vb))

    # 5. the generation's standing as a cohort (all recorded gen-level numbers)
    bc = dash.get("bureau_composition") or {}
    comp = ", ".join("%d %s" % (n, b) for b, n in bc.items())
    out.append(
        "It stands in generation %s of the bred line — %d ships (%s), best "
        "fitness %s, mean monoculture %s, novelty/diversity %s."
        % (dash.get("gen"), dash.get("n_ships"), comp,
           dash.get("best_fitness"), dash.get("avg_monoculture"),
           dash.get("diversity")))
    return out


def _install_forensic_placard():
    """Wrap cat.placard so it appends forensic lineage clauses after the
    canonical assembly clauses. Idempotent."""
    if getattr(cat, "_forensic_installed", False):
        return
    _orig = cat.placard

    def placard(ship):
        sents, used = _orig(ship)
        # insert forensic clauses just before the closing tally (last sentence)
        extra = forensic_sentences(ship)
        if extra:
            sents = sents[:-1] + extra + sents[-1:]
        return sents, used

    cat.placard = placard
    cat._forensic_installed = True


def main():
    generations = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    population = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7

    print("=== running the agent loop: evolve(generations=%d, population=%d, "
          "seed=%d) ===" % (generations, population, seed))
    lineage, ships, dashboards, contexts = evolved_fleet(
        generations, population, seed)

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

    # surface the lineage-pathology dashboard into the fleet json: per-generation
    # dashboards at fleet["dashboards"], and each ship's own lineage-context at
    # fleet["ships"][i]["lineage_context"]. All read from the lineage record.
    fleet["dashboards"] = dashboards
    for sd, ctx in zip(fleet["ships"], contexts):
        sd["lineage_context"] = ctx
    import json as _json
    with open(out_json, "w") as f:
        _json.dump(fleet, f)
    print("\nwrote evolved_fleet.json (%d ships, %d gen dashboards)"
          % (len(fleet["ships"]), len(dashboards)))

    # let the catalogue captions read the dashboard back
    _install_forensic_placard()

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
