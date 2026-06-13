#!/usr/bin/env hython
"""
render_usd_fleet.py — the catalogue's headless eye.

Renders usd/kitmash_fleet.usda to a framed PNG with no display server:
auto-frames the whole fleet from its world bbox, drops a dome + key light,
and shoots a 3/4 hero from Karma CPU. This is the "I looked" half of
"built is not cooks" — it confirms with eyes what verify_usd.py confirms
with numbers.

Why this over usdview (which the v0.10 handoff floated as the catalogue's
eye): usdview needs GL + a display. usdrecord --renderer "Karma CPU" runs
on a headless box, which is the only kind this lab has.

Usage (must run under Houdini's python so pxr + Karma resolve):
    /opt/hfs21.0.729/bin/hython houdini/render_usd_fleet.py \
        [usd/kitmash_fleet.usda] [out.png] [imageWidth]

It writes a sidecar camera+light layer next to the output (out.cam.usda)
that sublayers the fleet read-only — the fleet file itself is never touched.
"""
import os
import sys
import math
import subprocess

from pxr import Usd, UsdGeom, Gf, UsdLux

HFS = os.environ.get("HFS", "/opt/hfs21.0.729")
USDRECORD = os.path.join(HFS, "bin", "usdrecord")
HYTHON = os.path.join(HFS, "bin", "hython")


def build_cam_layer(fleet_path, cam_path, root="/Fleet",
                    az_deg=32.0, el_deg=12.0, dist_factor=0.62,
                    focal=40.0, ap_h=20.0, ap_v=30.0):
    """Write a camera+light layer that sublayers the fleet and frames it."""
    stage = Usd.Stage.Open(fleet_path)
    prim = stage.GetPrimAtPath(root)
    if not prim:
        raise SystemExit("no prim at %s in %s" % (root, fleet_path))

    bbc = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    rng = bbc.ComputeWorldBound(prim).ComputeAlignedRange()
    mn, mx = rng.GetMin(), rng.GetMax()
    center = (mn + mx) * 0.5
    diag = (mx - mn).GetLength()

    cs = Usd.Stage.CreateNew(cam_path)
    cs.GetRootLayer().subLayerPaths.append(os.path.abspath(fleet_path))
    UsdGeom.SetStageUpAxis(cs, UsdGeom.Tokens.y)

    UsdLux.DomeLight.Define(cs, "/Lights/dome").CreateIntensityAttr(1.0)
    key = UsdLux.DistantLight.Define(cs, "/Lights/key")
    key.CreateIntensityAttr(2.5)
    key.CreateAngleAttr(2.0)
    UsdGeom.Xformable(key).AddRotateXYZOp().Set(Gf.Vec3f(-40, 30, 0))

    dist = diag * dist_factor
    az, el = math.radians(az_deg), math.radians(el_deg)
    eye = Gf.Vec3d(
        center[0] + dist * math.cos(el) * math.sin(az),
        center[1] + dist * math.sin(el),
        center[2] + dist * math.cos(el) * math.cos(az))
    fwd = (center - eye); fwd /= fwd.GetLength()
    right = Gf.Cross(fwd, Gf.Vec3d(0, 1, 0)); right /= right.GetLength()
    up = Gf.Cross(right, fwd)
    m = Gf.Matrix4d(
        right[0], right[1], right[2], 0,
        up[0],    up[1],    up[2],    0,
        -fwd[0],  -fwd[1],  -fwd[2],  0,
        eye[0],   eye[1],   eye[2],   1)

    cam = UsdGeom.Camera.Define(cs, "/Camera")
    UsdGeom.Xformable(cam).AddTransformOp().Set(m)
    cam.CreateFocalLengthAttr(focal)
    cam.CreateHorizontalApertureAttr(ap_h)
    cam.CreateVerticalApertureAttr(ap_v)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.1, float(dist * 4)))
    cs.Save()
    return diag


def main():
    fleet = sys.argv[1] if len(sys.argv) > 1 else "usd/kitmash_fleet.usda"
    out = sys.argv[2] if len(sys.argv) > 2 else "houdini/kitmash_fleet_render.png"
    width = sys.argv[3] if len(sys.argv) > 3 else "800"
    cam_layer = out + ".cam.usda"

    diag = build_cam_layer(fleet, cam_layer)
    print("framed /Fleet (diag=%.1f) -> %s" % (diag, cam_layer))

    cmd = [HYTHON, USDRECORD, "--renderer", "Karma CPU",
           "--imageWidth", str(width), "--complexity", "high",
           "--camera", "/Camera", cam_layer, out]
    print("$ " + " ".join(cmd))
    subprocess.check_call(cmd)
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
