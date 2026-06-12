# kitmash_assembler_sop.py — paste into a Python SOP's Code parameter.
#
# The assembler runs HERE, in-process, and emits DECISIONS as geometry:
#   points  group `placements`  @P, @orient, s@generator, s@gen_params,
#                               gp_* typed copies, s@part_id, s@parent_id,
#                               f@join_strain, i@era, f@mass, ...
#   prims   group `struts`      2-point segments, f@relief, s@anchor
#   points  group `collars`     v@N, v@up, f@r, f@strain (adapter collars)
#   prims   group `hoses`       polylines, s@ctype, f@dia, f@width, style
#   points  group `open_ports`  full port schema (greeble/terminator hooks)
#   detail                      s@trace (the whole ledger), s@stats, lineage
#
# Spare parameter interface to add on the SOP (see ASSEMBLER-SOP.md):
#   kitmash_path  (String)  dir containing kitmash.py / kitmash_houdini.py
#   faction       (Menu)    0 = High Guild, 1 = Feral
#   seed          (Integer)
#   wants         (String)  JSON dict family -> weight
#   heavy, span   (Float)
#   use_radiator, use_reactor, use_turret  (Toggle) extra genes

import sys, json
import hou

node = hou.pwd()
geo = node.geometry()

path = node.evalParm("kitmash_path")
if path and path not in sys.path:
    sys.path.insert(0, path)
import kitmash as km
import kitmash_houdini as kh

fc = (km.GUILD, km.FERAL)[node.evalParm("faction")]
wants = json.loads(node.evalParm("wants") or "{}")
extra = []
if node.evalParm("use_radiator"): extra.append(km.gen_radiator)
if node.evalParm("use_reactor"):  extra.append(km.gen_reactor)
if node.evalParm("use_turret"):   extra.append(km.gen_turret)

a = km.build(fc, node.evalParm("seed"), wants,
             heavy=node.evalParm("heavy"), span=node.evalParm("span"),
             extra_gens=extra)
kh.write_geo(geo, a, name=node.name())
