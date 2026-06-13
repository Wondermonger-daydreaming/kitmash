"""make_fleet_usd.py — the canonical KitMash fleet as a USD stage.

Rebuilds the same five ships as kitmash.py's __main__ (identical seeds,
briefs, mutations — the regression anchors) and writes them to
usd/kitmash_fleet.usda via the kitmash_usd bridge. The .usda is ASCII so
it is inspectable and git-diffable, the same virtue fleet.json has.

  .venv/bin/python make_fleet_usd.py [out.usda]      (usd-core, no license)
  /opt/hfs21.0.729/bin/hython make_fleet_usd.py       (Houdini's own pxr)

Open the result in any USD viewer (usdview, Houdini, Blender 4.x, omniverse):
the parts are faction-colored cartoon bodies; the provenance is on every
prim as primvars:kitmash:*.
"""
import os
import sys

import numpy as np

import kitmash as km
import kitmash_usd as ku


def build_fleet():
    """The canonical five. Mirrors kitmash.py __main__ exactly."""
    wants_g = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
               "heavy_cannon": 1.4, "antenna": 0.8, "sensor_pod": 0.6}
    wants_f = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
               "heavy_cannon": 2.2, "sensor_pod": 1.0, "antenna": 0.4}
    wants_d = {"engine": 3.0, "fuel_tank": 2.5, "wing": 2.0,
               "heavy_cannon": 1.8, "radiator": 2.4, "sensor_pod": 1.2,
               "antenna": 0.8}
    wants_e = {"engine": 3.0, "fuel_tank": 2.5, "wing": 1.6,
               "heavy_cannon": 0.9, "turret": 2.6, "reactor": 2.3,
               "sensor_pod": 0.4, "antenna": 0.3}
    A = km.build(km.GUILD, 7, wants_g, heavy=1.0, span=3.0)
    B = km.build(km.GUILD, 7, wants_g, heavy=1.7, span=3.9,
                 parent="GS-α", mutation="heavy 1.0→1.7, span 3.0→3.9")
    C = km.build(km.FERAL, 23, wants_f, heavy=1.4, span=3.4)
    D = km.build(km.FERAL, 41, wants_d, heavy=1.2, span=3.2,
                 extra_gens=[km.gen_radiator], parent="FV-γ",
                 mutation="+radiator gene, wants reshuffled")
    E = km.build(km.FERAL, 101, wants_e, heavy=1.0, span=3.0,
                 extra_gens=[km.gen_reactor, km.gen_turret], parent="FV-γ",
                 mutation="+reactor/turret genes, electrified")
    return [
        ("GS-α  «Lawful Mean»", A, np.array([0, -7.5, 0]), "Plate XLVII"),
        ("GS-β  «Heavier Daughter»", B, np.array([0, 0, 0]), "Plate XLVIII"),
        ("FV-γ  «Tape Holds»", C, np.array([0, 7.5, 0]), "Plate XLIX"),
        ("FV-δ  «Cold Shoulder»", D, np.array([0, 15, 0]), "Plate L"),
        ("FV-ε  «Loom»", E, np.array([0, 22.5, 0]), "Plate LI"),
    ]


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    dest = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(here, "usd", "kitmash_fleet.usda")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        os.remove(dest)            # CreateNew refuses to overwrite
    ships = build_fleet()
    ku.export_fleet(ships, dest)
    print(f"wrote {dest}")
    for name, a, _off, plate in ships:
        print(f"  {name:28s} {plate:12s} "
              f"parts={len(a.placed)} mass={int(sum(p.mass for p in a.placed))} "
              f"struts={len(a.struts)} hoses={len(a.hoses)}")
