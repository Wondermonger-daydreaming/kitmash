"""make_ship_hip.py — build a complete demo scene with one hython call.

Run:  source /opt/hfs21.0/houdini_setup
      hython houdini/make_ship_hip.py [out.hip] [--faction N] [--seed N]

Network (the headless path — no HDAs required):

  /obj/kitmash_ship
  ├── assembler    (Python SOP)  runs build(), emits decisions
  ├── rehydrate    (Python SOP)  kitmash_houdini.rehydrate_to_geo —
  │                              parts + collars baked as colored polys,
  │                              strut/hose curves passed through
  ├── wire_struts  (PolyWire on group struts, radius 0.06)
  ├── wire_hoses   (PolyWire on group hoses,  radius 0.02)
  └── OUT

Open the saved .hip: a finished ship, decisions made in Python, geometry
born in Houdini. The artist path (part HDAs, sweeps, sag, p-clips) is
specified in ASSEMBLER-SOP.md / hoses-to-sweep.md and replaces the two
Python SOPs node-for-node. (Written ahead of the install; UNTESTED
until 21.0.729 lands.)
"""
import os, sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)

args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = args[0] if args else os.path.join(HERE, "kitmash_ship.hip")
def flag(name, default):
    return (int(sys.argv[sys.argv.index(name) + 1])
            if name in sys.argv else default)
FACTION = flag("--faction", 0)            # 0 guild, 1 feral
SEED = flag("--seed", 7)

ASSEMBLER_CODE = open(os.path.join(HERE, "kitmash_assembler_sop.py")).read()
REHYDRATE_CODE = '''\
node = hou.pwd(); geo = node.geometry()
import sys
p = node.parent().node("assembler").evalParm("kitmash_path")
if p and p not in sys.path: sys.path.insert(0, p)
import kitmash_houdini as kh
kh.rehydrate_to_geo(geo)
'''

obj = hou.node("/obj")
ship = obj.createNode("geo", "kitmash_ship")

asm = ship.createNode("python", "assembler")
# spare parms = the brief (see ASSEMBLER-SOP.md)
for tmpl in (
    hou.StringParmTemplate("kitmash_path", "KitMash Path", 1,
                           default_value=(PROJECT,)),
    hou.MenuParmTemplate("faction", "Faction", ("guild", "feral"),
                         ("High Guild", "Feral")),
    hou.IntParmTemplate("seed", "Seed", 1, default_value=(SEED,)),
    hou.StringParmTemplate("wants", "Wants (JSON)", 1, default_value=(
        '{"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":1.4,'
        '"antenna":0.8,"sensor_pod":0.6}',)),
    hou.FloatParmTemplate("heavy", "Heavy", 1, default_value=(1.0,)),
    hou.FloatParmTemplate("span", "Span", 1, default_value=(3.0,)),
    hou.ToggleParmTemplate("use_radiator", "Radiator Gene"),
    hou.ToggleParmTemplate("use_reactor", "Reactor Gene"),
    hou.ToggleParmTemplate("use_turret", "Turret Gene"),
):
    asm.addSpareParmTuple(tmpl)
asm.parm("python").set(ASSEMBLER_CODE)
asm.parm("faction").set(FACTION)

reh = ship.createNode("python", "rehydrate")
reh.setInput(0, asm)
reh.parm("python").set(REHYDRATE_CODE)

w_struts = ship.createNode("polywire", "wire_struts")
w_struts.setInput(0, reh)
w_struts.setParms({"group": "struts", "radius": 0.06})

w_hoses = ship.createNode("polywire", "wire_hoses")
w_hoses.setInput(0, w_struts)
w_hoses.setParms({"group": "hoses", "radius": 0.02})

out = ship.createNode("output", "OUT")
out.setInput(0, w_hoses)
out.setDisplayFlag(True); out.setRenderFlag(True)
ship.layoutChildren()

# cook once so the .hip opens pre-built; surface errors loudly
out.geometry()
stats = out.geometry().attribValue("stats") \
    if out.geometry().findGlobalAttrib("stats") else "?"
print("cooked:", stats)

hou.hipFile.save(OUT)
print("saved", OUT)
