#!/usr/bin/env hython
"""
render_plates.py — shoot every catalogue plate in one pass.

Renders the whole-fleet frontispiece plus one isolated plate per ship into
houdini/plates/, named by the ship's USD prim so make_catalogue.py can find
them. Headless Karma CPU, no display server. Run under hython:

    /opt/hfs21.0.729/bin/hython houdini/render_plates.py

This is the slow, license-bound half of the catalogue. make_catalogue.py
(the captions) runs license-free off fleet.json and just consumes the PNGs
this leaves behind.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_usd_fleet as R  # noqa: E402

from pxr import Usd  # noqa: E402

FLEET = os.path.join(os.path.dirname(HERE), "usd", "kitmash_fleet.usda")
OUTDIR = os.path.join(HERE, "plates")
WIDTH = "760"


def slug(prim_path):
    return prim_path.rsplit("/", 1)[-1]  # /Fleet/GS_alpha -> GS_alpha


def main():
    os.makedirs(OUTDIR, exist_ok=True)

    # frontispiece: the whole stacked fleet
    front = os.path.join(OUTDIR, "fleet.png")
    R.build_cam_layer(FLEET, front + ".cam.usda", root="/Fleet")
    R.subprocess.check_call([
        R.HYTHON, R.USDRECORD, "--renderer", "Karma CPU",
        "--imageWidth", "900", "--complexity", "high",
        "--camera", "/Camera", front + ".cam.usda", front])
    print("plate: fleet ->", front)

    # one isolated plate per ship
    stage = Usd.Stage.Open(FLEET)
    ships = [p.GetPath().pathString
             for p in stage.GetPrimAtPath("/Fleet").GetChildren()
             if p.GetTypeName() == "Xform"]
    for sp in ships:
        out = os.path.join(OUTDIR, "%s.png" % slug(sp))
        R.build_cam_layer(FLEET, out + ".cam.usda", root=sp, isolate=True,
                          az_deg=30.0, el_deg=12.0, dist_factor=1.15,
                          focal=35.0, ap_h=30.0, ap_v=26.0)
        R.subprocess.check_call([
            R.HYTHON, R.USDRECORD, "--renderer", "Karma CPU",
            "--imageWidth", WIDTH, "--complexity", "high",
            "--camera", "/Camera", out + ".cam.usda", out])
        print("plate: %s -> %s" % (slug(sp), out))


if __name__ == "__main__":
    main()
