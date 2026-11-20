"""
Blender geometry nodes script for building 3D university collaboration graphs.
Run via: blender -b templates/University_template.blend --python geonodes_directors.py -- <grid_id> <output_dir>

Prerequisites: pandas must be installed in Blender's Python (see setup.sh).
"""

import os
from pathlib import Path
_ROOT = Path(os.environ.get('FR_ROOT') or Path(__file__).resolve().parent.parent)
import sys

argv = sys.argv
argv = argv[argv.index("--") + 1:]  # get all args after "--"

grid_id = argv[0]
output_dir = argv[1] if len(argv) > 1 else "."

# Ensure output_dir ends with /
if not output_dir.endswith('/'):
    output_dir += '/'

import bpy
import numpy as np
import pandas as pd
from mathutils import Vector
import math

### Clean Scene
obs = [o for o in bpy.data.objects if o.name.find("Plane") >= 0]
for o in obs:
    bpy.data.objects.remove(o, do_unlink=True)

summary = pd.read_csv(f'{output_dir}{grid_id}/summary.csv')
nodes = pd.read_csv(f'{output_dir}{grid_id}/{grid_id}testbundleNodes.csv')
coords = pd.read_csv(f'{output_dir}{grid_id}/{grid_id}fulltestbundle.csv')
cluster_details = pd.read_csv(f'{output_dir}{grid_id}/{grid_id}cluster_details.csv')

# --- French directors adaptation: give every cluster its own level. Parent communities are ranked
# by their original height (field index x field share); every sub-cluster then takes its own level,
# in order (parent, own height), Z_STEP apart, so sub-clusters of one parent stay contiguous.
import os
Z_STEP = float(os.environ.get("FR_Z_STEP", "0.04"))  # per cluster, across all sub-clusters
_cd = cluster_details.drop_duplicates("cluster_id").copy()
if "parent" not in _cd:
    _cd["parent"] = _cd.cluster_id
_pr = {p: i for i, p in enumerate(_cd.groupby("parent").h.mean().sort_values().index)}
_cd["_p"] = _cd.parent.map(_pr)
_cd = _cd.sort_values(["_p", "h"])
_level = {c: i * Z_STEP for i, c in enumerate(_cd.cluster_id)}
cluster_details["h"] = cluster_details.cluster_id.map(_level)
# Height off the ground: the template's +2 offset suited a stack ~2.4 tall (centre ~3.5). Keep the stack
# centred there however tall it gets, so it stays in frame and clear of the title; FR_Z_BASE overrides.
Z_BASE = float(os.environ.get("FR_Z_BASE", 0.0))  # was auto-centred (-1.0 at step 0.05); +1 lift, then step shrunk
print("z base:", round(Z_BASE, 2), "top:", round(Z_BASE + max(_level.values()), 2))
print("cluster levels:", {c: round(v, 2) for c, v in _level.items()})
institutions = pd.DataFrame()
institutions['institution'] = ''
institutions['region'] = ''
institutions['grid_id'] = ''

cx_max = coords.x.max()
cx_min = coords.x.min()
cy_max = coords.y.max()
cy_min = coords.y.min()
cx_mean = coords.x.mean()
cy_mean = coords.y.mean()

xl = cx_max - cx_min
yl = cy_max - cy_min


forpartition = []
forpartition.append((32, (205,74,74)))
forpartition.append((42, (255,130,67)))
forpartition.append((52, (159,129,112)))
forpartition.append((31, (239,205,184)))
forpartition.append((30, (214,138,89)))
forpartition.append((41, (21,128,120)))
forpartition.append((34, (25,158,189)))
forpartition.append((51, (26,72,118)))
forpartition.append((49, (25,116,210)))
forpartition.append((46, (177,212,224)))
forpartition.append((40, (151,154,170)))
forpartition.append((33, (138,121,93)))
forpartition.append((37, (255,207,72)))
forpartition.append((43, (252,217,117)))
forpartition.append((38, (252,232,131)))
forpartition.append((35, (236,234,190)))
forpartition.append((48, (186,184,108)))
forpartition.append((44, (255,255,153)))
forpartition.append((39, (178,236,93)))
forpartition.append((47, (120,81,169)))
forpartition.append((50, (142,69,133)))
forpartition.append((36, (110,81,96)))


colors = {p[0]:(p[1][0]/255,p[1][1]/255,p[1][2]/255,1) for i, p in enumerate(forpartition)}


insts = len(institutions) + 1  # adding 1 for the country label


bpy.data.node_groups["Insititution Labels"].nodes["String.013"].string = summary.iloc()[0]['org_name']+":"+":".join(institutions.institution.apply(lambda s: s if len(s) <=50 else s[0:50] + '...').to_list())
bpy.data.node_groups["Insititution Labels"].nodes["Math.015"].inputs[1].default_value = insts
bpy.data.node_groups["Insititution Region"].nodes["String.013"].string = ""


bpy.context.scene.frame_end = int((480/142)*24* (insts + 2))


FOR1_order = [32,42,52,31,30,41,34,51,49,46,40,33,37,43,38,35,44,39,47]

FOR_order_lookup = {f:i for i,f in enumerate(FOR1_order)}

## Use the scope-aware 'internal/external' column computed in process_graph.py
## (grid: current_research_org == grid_id; country/state: country/admin1 match).
## Falls back to the legacy grid-id check for CSVs produced by older pipeline runs.
if 'internal/external' in nodes.columns:
    filtered_nodes = nodes[nodes['internal/external'] == 'circle'][['id']]
else:
    filtered_nodes = nodes[nodes.current_research_org == grid_id][['id']]
filtered_nodes['search'] = 1


institutes = institutions.grid_id.to_list()
print('institutes_length', len(institutes))

ikey = {}
for i, inst in enumerate(institutes):
    ikey[inst] = i + 1  # leaving room at 0 for grid.all

all_nodes = nodes.groupby('cluster_id').agg(all_researchers=('id','count'))


insts_nodes = nodes.groupby(['cluster_id','current_research_org']).\
    agg(matched_researchers=('id','count')).\
    reset_index().\
    pivot(index='cluster_id', columns='current_research_org', values='matched_researchers')[institutes]

all_searches = insts_nodes.fillna(0).div(all_nodes['all_researchers'].fillna(1), axis=0).reset_index()


nm = nodes.merge(cluster_details[['cluster_id','h']].rename(columns={'h':'z'}), on="cluster_id").merge(filtered_nodes, on='id', how='left')
nm['color'] = nm.FOR1.apply(lambda c: colors[c])
nm['search'] = nm['search'].apply(lambda s: True if s == 1 else False)

nodeswf = nodes.merge(filtered_nodes, on='id', how='left')
nodeswfg = nodeswf.groupby('cluster_id').agg(all_researchers=('id','count'), matched_researchers=('search','sum'))
nodeswfg['percentage_clusters'] = nodeswfg['matched_researchers']/nodeswfg['all_researchers']
nodeswfg.reset_index(inplace=True)
coords = coords.merge(nodeswfg[['cluster_id','percentage_clusters']], on='cluster_id').\
                merge(all_searches, on='cluster_id', how='left').copy()

# Create object for GeoNodes
bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
obj = bpy.context.active_object

print('node length:', len(nm))


def trigger_update():
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.object.mode_set(mode='OBJECT')


def add_attribute(obj, attr_name, type="FLOAT", domain="POINT"):
    attr = obj.data.attributes.new(attr_name, type, domain)
    return attr

if len(obj.modifiers.values()) == 0:
    geo_nodes = obj.modifiers.new("make_vertices", "NODES")
    geo_nodes.node_group = bpy.data.node_groups['make_verticies']

# Set the number of vertices
geo_nodes["Input_2"] = len(nm)

trigger_update()

# Apply modifier
bpy.ops.object.modifier_apply(modifier=geo_nodes.name)

trigger_update()


# Current research org affiliation
current_research_org_seq = nm['current_research_org'].\
    apply(lambda s: float(ikey[s]) if (type(s)==str) and (s in ikey.keys()) else 999).\
    to_list()
attr = add_attribute(obj, "Research_org", "FLOAT")
attr.data.foreach_set('value', current_research_org_seq)

# Store the publications onto the points
publications_seq = nm.publications.apply(lambda p: min([.1875/2,p/1995])).to_list()
attr = add_attribute(obj, "Publications", "FLOAT")
attr.data.foreach_set('value', publications_seq)

# Layer (parent-community rank, 0 = lowest) so whole layers can be removed in the node group later
_parent_of = cluster_details.drop_duplicates("cluster_id").set_index("cluster_id").get("parent", None)
nm["parent"] = nm.cluster_id.map(_parent_of) if _parent_of is not None else nm.cluster_id
layer_seq = nm["parent"].map(_pr).astype(float).to_list()
attr = add_attribute(obj, "Layer", "FLOAT")
attr.data.foreach_set('value', layer_seq)

# Field of research attribute and FOR sequence attribute
for_seq = nm.FOR1.to_list()
attr = add_attribute(obj, "FOR1", "FLOAT")
attr.data.foreach_set('value', for_seq)

for_order_seq = nm.FOR1.apply(lambda f: FOR_order_lookup.get(f,999)).to_list()
attr = add_attribute(obj, "FOR1 Order", "FLOAT")
attr.data.foreach_set('value', for_order_seq)

# Search
search_seq = nm['search'].to_list()
attr = add_attribute(obj, "Search", "BOOLEAN")
attr.data.foreach_set('value', search_seq)


nm['x'] = nm['x'].apply(lambda x: 100 * (x - cx_mean) / xl)
nm['y'] = nm['y'].apply(lambda y: 100 * (y - cy_mean) / yl)
nm['z'] = nm['z'].apply(lambda z: z + Z_BASE)

# Storing the coordinates onto the points
coordinates = []
for r in nm.iterrows():
    coordinates.append(r[1]['x'])
    coordinates.append(r[1]['y'])
    coordinates.append(r[1]['z'])

attr = add_attribute(obj, "Coordinates", "FLOAT_VECTOR")
attr.data.foreach_set('vector', coordinates)

# Start state of the opening morph: the co-supervision-only layout (flat, at the lowest layer). Nodes outside its
# giant component have no start position; they stay put and grow from nothing (Scale0 = 0).
_cs = pd.read_csv(str(_ROOT / "network_2005_2025/cosup_layout_gcc.csv"), dtype={"director_key": str}).set_index("director_key")
_has0 = nm["id"].isin(_cs.index).to_numpy()
_x0 = np.where(_has0, 100 * (nm["id"].map(_cs.x).astype(float) - cx_mean) / xl, nm["x"])
_y0 = np.where(_has0, 100 * (nm["id"].map(_cs.y).astype(float) - cy_mean) / yl, nm["y"])
_z0 = np.where(_has0, nm["z"].min(), nm["z"])
attr = add_attribute(obj, "Coords0", "FLOAT_VECTOR")
attr.data.foreach_set('vector', np.stack([_x0, _y0, _z0], axis=1).ravel().tolist())
attr = add_attribute(obj, "Scale0", "FLOAT")
attr.data.foreach_set('value', _has0.astype(float).tolist())
print(f"morph start state: {_has0.sum():,} of {len(nm):,} nodes have a co-supervision-only position")


color_seq = []
for r in nm.iterrows():
    color_seq.append(r[1]['color'][0])
    color_seq.append(r[1]['color'][1])
    color_seq.append(r[1]['color'][2])
    color_seq.append(r[1]['color'][3])

attr = obj.data.attributes.get('Color')
if attr is None:
    attr = add_attribute(obj, "Color", "FLOAT_COLOR")

attr.data.foreach_set('color', color_seq)


geo_nodes = obj.modifiers.new("map", "NODES")
geo_nodes.node_group = bpy.data.node_groups['map']

trigger_update()

####### Add colors to Legend #######

nm['mapped_research_org'] = nm['current_research_org'].\
    apply(lambda s: float(ikey[s]) if (type(s)==str) and (s in ikey.keys()) else 999)

nmgorg = nm.groupby(['mapped_research_org']).\
           agg(all_researchers=('mapped_research_org','count')).reset_index()

nmgf = nm.groupby(['mapped_research_org','FOR1','color']).\
           agg(researchers=('FOR1','count')).\
           reset_index().\
           merge(nmgorg, on='mapped_research_org')

nmgf['FOR1_ratio'] = nmgf.researchers / nmgf.all_researchers

nmgp = nmgf.pivot(index='FOR1', columns='mapped_research_org', values='FOR1_ratio')

# Calculate 'all researcher' statistics at index 0
arnm = nm.groupby(['FOR1']).agg(researchers=('FOR1','count'))
arnm[0] = arnm.researchers / arnm.researchers.sum()
arnm.reset_index(inplace=True)

anmgp = nmgp.merge(arnm, on='FOR1')

for_orderdf = pd.DataFrame(FOR1_order)
for_orderdf.columns = ['FOR1']
for_orderdf = for_orderdf.merge(anmgp, on='FOR1', how='left')
for_orderdf['color'] = for_orderdf['FOR1'].apply(lambda c: colors[c])


obj = bpy.data.objects['Label2']

color_seq = []
for r in for_orderdf.iterrows():
    color_seq.append(r[1]['color'][0])
    color_seq.append(r[1]['color'][1])
    color_seq.append(r[1]['color'][2])
    color_seq.append(r[1]['color'][3])

# Add dummy value to match vertices (to make 20...)
color_seq.append(0)
color_seq.append(0)
color_seq.append(0)
color_seq.append(0)

if 'Color' in obj.data.attributes.keys():
    attr = add_attribute(obj, "Color", "FLOAT_COLOR")
attr.data.foreach_set('color', color_seq)

print("columns are", for_orderdf.columns)

for i, inst in enumerate(['grid.all'] + institutes):
    print(i)
    inst_forratio_seq = for_orderdf[i].to_list()
    inst_forratio_seq.append(0)
    attr = obj.data.attributes.get(str(i))
    if attr is None:
        attr = add_attribute(obj, str(i), "FLOAT")
    attr.data.foreach_set('value', inst_forratio_seq)


######## Load cluster points #####

coords['next_x'] = coords['x'].shift(-1)
coords['next_y'] = coords['y'].shift(-1)

cluster_objs = {}
for cluster_id in coords.cluster_id.unique():
    print("working on ", cluster_id)
    bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
    obj = bpy.context.active_object
    cluster_objs[cluster_id] = obj

    if len(obj.modifiers.values()) == 0:
        geo_nodes2 = obj.modifiers.new("make_verticies_2", "NODES")
        geo_nodes2.node_group = bpy.data.node_groups['make_verticies']

    cluster = coords[coords.cluster_id == cluster_id].dropna().merge(cluster_details[['cluster_id','h']].rename(columns={'h':'z'}), on="cluster_id").copy()

    cluster['color'] = cluster.FOR1.apply(lambda c: colors[c])

    print("cluster length", len(cluster))

    if len(cluster) > 0:
        geo_nodes2["Input_2"] = len(cluster)

        trigger_update()

        bpy.ops.object.modifier_apply(modifier=geo_nodes2.name)

        color_seq = []
        for r in cluster.iterrows():
            color_seq.append(r[1]['color'][0])
            color_seq.append(r[1]['color'][1])
            color_seq.append(r[1]['color'][2])
            color_seq.append(r[1]['color'][3])

        attr = add_attribute(obj, "Color", "FLOAT_COLOR")
        attr.data.foreach_set('color', color_seq)

        transparency_seq = cluster.percentage_clusters.to_list()
        attr = add_attribute(obj, "Transparency", "FLOAT")
        attr.data.foreach_set('value', transparency_seq)

        cluster['x'] = cluster['x'].apply(lambda x: 100 * (x - cx_mean) / xl)
        cluster['y'] = cluster['y'].apply(lambda y: 100 * (y - cy_mean) / yl)
        cluster['z'] = cluster['z'].apply(lambda z: z + Z_BASE)

        cluster['next_x'] = cluster['next_x'].apply(lambda x: 100 * (x - cx_mean) / xl)
        cluster['next_y'] = cluster['next_y'].apply(lambda y: 100 * (y - cy_mean) / yl)

        cluster['dist'] = cluster.apply(lambda r: math.dist([r['x'],r['y']],[r['next_x'],r['next_y']]), axis=1)

        start_coordinates = []
        end_coordinates = []
        rotl = []
        distl = []

        for r in cluster.iterrows():
            start_coordinates.append(r[1]['x'])
            start_coordinates.append(r[1]['y'])
            start_coordinates.append(r[1]['z'])
            end_coordinates.append(r[1]['next_x'])
            end_coordinates.append(r[1]['next_y'])
            end_coordinates.append(r[1]['z'])

            v0 = Vector((0,0,1))
            v1 = Vector((r[1]['x'],r[1]['y'], r[1]['z']))
            v2 = Vector((r[1]['next_x'],r[1]['next_y'], r[1]['z']))

            rot = (v1 - v2).rotation_difference(v0).to_euler()
            rotl.append(rot[0])
            rotl.append(rot[1])
            rotl.append(rot[2])

            distl.append(r[1]['dist'])

        attr = add_attribute(obj, "StartCoordinates", "FLOAT_VECTOR")
        attr.data.foreach_set('vector', start_coordinates)

        attr = add_attribute(obj, "EndCoordinates", "FLOAT_VECTOR")
        attr.data.foreach_set('vector', end_coordinates)

        attr = add_attribute(obj, "rotation", "FLOAT_VECTOR")
        attr.data.foreach_set('vector', rotl)

        attr = add_attribute(obj, "distance", "FLOAT")
        attr.data.foreach_set('value', distl)

        for_seq = cluster.FOR1.to_list()
        attr = add_attribute(obj, "FOR1", "FLOAT")
        attr.data.foreach_set('value', for_seq)

        for_order_seq = cluster.FOR1.apply(lambda f: FOR_order_lookup.get(f,999)).to_list()
        attr = add_attribute(obj, "FOR1 Order", "FLOAT")
        attr.data.foreach_set('value', for_order_seq)

        cluster['grid.all'] = 1
        ikey['grid.all'] = 0
        for i in institutes + ['grid.all']:
            print(i)
            inst_alpha_seq = cluster[i].to_list()
            attr = add_attribute(obj, str(ikey[i]), "FLOAT")
            attr.data.foreach_set('value', inst_alpha_seq)

        geo_nodes = obj.modifiers.new(f"graphlayout {cluster_id}", "NODES")
        geo_nodes.node_group = bpy.data.node_groups['graphlayout']


### Camera and compositing setup

objl = ['Label2','Plane','Text','Text.001','Title','Title.001']

for o in objl:
    obj = bpy.data.objects[o]
    obj.hide_render = True
    obj.hide_viewport = True

bpy.context.scene.render.film_transparent = False

bpy.context.scene.frame_current = 81

bpy.context.scene.render.film_transparent = True

bpy.context.scene.use_nodes = True

for o in objl:
    obj = bpy.data.objects[o]
    obj.hide_render = False
    obj.hide_viewport = False

bpy.context.scene.render.filepath = f"{output_dir}{grid_id}/{grid_id}_A0.png"

print(f'{output_dir}{grid_id}/')

# ======================================================================
# Animation: fades off; top-down view -> poster view -> 360 degree orbit
# ======================================================================
import math
from mathutils import Euler, Vector

scene = bpy.context.scene
FREEZE_FRAME = 81  # the state of the stills: everything visible, nothing fading

# 1. Disable the time-driven fades. Every Scene Time node in the template's node groups (graph growth,
# node visibility, labels) is replaced by a constant, frozen at the still-image frame.
frozen = 0
for _ng in bpy.data.node_groups:
    for _n in [n for n in _ng.nodes if n.bl_idname == "GeometryNodeInputSceneTime"]:
        for _out in _n.outputs:
            _targets = [l.to_socket for l in _out.links]
            if not _targets:
                continue
            for l in list(_out.links):
                _ng.links.remove(l)
            _v = _ng.nodes.new("ShaderNodeValue")
            _v.location = _n.location
            _v.outputs[0].default_value = FREEZE_FRAME if _out.name == "Frame" else FREEZE_FRAME / scene.render.fps
            for _ts in _targets:
                _ng.links.new(_v.outputs[0], _ts)
            frozen += 1
print("scene-time outputs frozen:", frozen)

# 2. Camera path. 'Camera' carries the title/legend as children, 'Camera.001' is the render camera,
# so animate 'Camera' and make 'Camera.001' copy it.
cam = bpy.data.objects["Camera"]
cam1 = bpy.data.objects["Camera.001"]
loc0, rx = cam.location.copy(), cam.rotation_euler.x
zc = Z_BASE + max(_level.values()) / 2                      # mid-height of the stack
fwd = Vector((0, math.sin(rx), -math.cos(rx)))
dist1 = (loc0.z - zc) / math.cos(rx)                         # distance along the view axis to the stack mid-plane
target_now = loc0 + fwd * dist1                              # what the poster view looks at
target_top = Vector((0, 0, zc))                              # the top-down view is centred on the graph
r_top = float(os.environ.get("FR_TOP_R", 230))               # top-down distance (the graph is ~100 x 100)

MORPH_PRE, MORPH_LEN, MORPH_POST = 36, int(os.environ.get("FR_MORPH", 96)), 24     # supervisor-only hold, morph, settle
HOLD_TOP = int(os.environ.get("FR_HOLD_TOP", MORPH_PRE + MORPH_LEN + MORPH_POST))
f_m0, f_m1 = MORPH_PRE, MORPH_PRE + MORPH_LEN
MOVE = int(os.environ.get("FR_MOVE", 72))
HOLD_MID = int(os.environ.get("FR_HOLD_MID", 12))
ORBIT = int(os.environ.get("FR_ORBIT", 240))
f_move0, f_move1 = HOLD_TOP, HOLD_TOP + MOVE
f_orb0, f_orb1 = f_move1 + HOLD_MID, f_move1 + HOLD_MID + ORBIT

for _o in (cam, cam1):
    _o.animation_data_clear()

def _pose(e: float) -> tuple[Vector, float]:
    """Camera position and tilt at eased progress e (0 = top-down, 1 = poster view)."""
    a = e * rx
    r = r_top + e * (dist1 - r_top)
    tgt = target_top.lerp(target_now, e)
    return tgt + Vector((0, -math.sin(a), math.cos(a))) * r, a

def _key(fr: int, e: float) -> None:
    p, a = _pose(e)
    cam.location = p
    cam.rotation_euler = (a, 0.0, 0.0)
    cam.keyframe_insert("location", frame=fr)
    cam.keyframe_insert("rotation_euler", frame=fr)

_key(0, 0.0)
for fr in range(f_move0, f_move1 + 1):
    s = (fr - f_move0) / MOVE
    _key(fr, s * s * (3 - 2 * s))          # smoothstep: ease out of the top view and into the poster view
_key(f_orb1, 1.0)

# 360 degree orbit: the camera is parented to a pivot at the graph centre, which turns once about Z.
pivot = bpy.data.objects.new("Orbit Pivot", None)
scene.collection.objects.link(pivot)
cam.parent = pivot
pivot.rotation_euler = (0, 0, 0)
pivot.keyframe_insert("rotation_euler", frame=0)
pivot.keyframe_insert("rotation_euler", frame=f_orb0)
pivot.rotation_euler = (0, 0, 2 * math.pi)
pivot.keyframe_insert("rotation_euler", frame=f_orb1)

for _o in (cam, pivot):
    for _fc in _o.animation_data.action.fcurves:
        for _kp in _fc.keyframe_points:
            _kp.interpolation = "LINEAR"        # easing is baked into the sampled keys; the orbit is constant speed

con = cam1.constraints.new("COPY_TRANSFORMS")
con.target = cam


# ----------------------------------------------------------------------
# After the orbit: pull back, then take the layers off one at a time (top first). For each layer the camera
# flies in to it, then a halo disc at its height and a hovering label joined by a thin pointer announce it.
# ----------------------------------------------------------------------
import textwrap

sys.path.insert(0, str(_ROOT / "scripts"))
from discipline_fields import FIELD_NAMES

SHORT = {"32": "Biomedical", "42": "Health", "52": "Psychology", "31": "Biological", "30": "Agri & Food",
         "41": "Environmental", "34": "Chemical", "51": "Physical", "49": "Mathematical",
         "46": "Info & Computing", "40": "Engineering", "33": "Built Environment", "37": "Earth",
         "43": "History & Heritage", "38": "Economics", "35": "Management", "44": "Society & Law",
         "39": "Education", "47": "Language & Culture"}

MOVE = int(os.environ.get("FR_LAYER_MOVE", 14))      # camera flight to the next layer
HOLD = int(os.environ.get("FR_LAYER_HOLD", 32))      # label on screen
OUTRO = 20
R_LABEL = float(os.environ.get("FR_LABEL_R", 235))   # wide pull-back distance
ZOOM_K = float(os.environ.get("FR_ZOOM_K", 7.6))     # camera distance = ZOOM_K x layer radius (so the layer + label fill the frame)
R_MIN, R_MAX = 90.0, 420.0
LABEL_HEAD, LABEL_SUB = 7.5, 5.4        # label text sizes in world units at the wide distance R_LABEL
f_hold2 = f_orb1 + 12
f_pull = f_hold2 + 30
f_layers0 = f_pull + 12

def _cam_key(fr: int, tgt: Vector, r: float) -> None:
    cam.location = tgt + Vector((0, -math.sin(rx), math.cos(rx))) * r
    cam.rotation_euler = (rx, 0.0, 0.0)
    cam.keyframe_insert("location", frame=fr)
    cam.keyframe_insert("rotation_euler", frame=fr)

def _fly(f0: int, f1: int, t0: Vector, r0: float, t1: Vector, r1: float) -> None:
    for fr in range(f0, f1 + 1):
        s = (fr - f0) / max(1, f1 - f0)
        e = s * s * (3 - 2 * s)
        _cam_key(fr, t0.lerp(t1, e), r0 * (r1 / r0) ** e)

_cam_key(f_hold2, target_now, dist1)
_fly(f_hold2, f_pull, target_now, dist1, target_now, R_LABEL)

# node group: delete points whose Layer is above LayerCut (a keyframed value)
_map = bpy.data.node_groups["map"]
_gin = next(n for n in _map.nodes if n.bl_idname == "NodeGroupInput")
_setpos = _map.nodes["Set Position"]
_del = _map.nodes.new("GeometryNodeDeleteGeometry")
_nam = _map.nodes.new("GeometryNodeInputNamedAttribute")
_nam.inputs[0].default_value = "Layer"
_cmp = _map.nodes.new("FunctionNodeCompare")
_cmp.operation = "GREATER_THAN"
_cut = _map.nodes.new("ShaderNodeValue")
_cut.name = "LayerCut"
for l in [l for l in _map.links if l.to_node == _setpos and l.to_socket.name == "Geometry"]:
    _map.links.remove(l)
_map.links.new(_gin.outputs["Geometry"], _del.inputs["Geometry"])
_map.links.new(_del.outputs["Geometry"], _setpos.inputs["Geometry"])
_map.links.new(_nam.outputs[0], _cmp.inputs[0])
_map.links.new(_cut.outputs[0], _cmp.inputs[1])
_map.links.new(_cmp.outputs[0], _del.inputs["Selection"])

n_layers = len(_pr)
# The 'map' and 'graphlayout' node groups rescale height on the way in (z_world = z * 4 - 8), so anything
# placed by hand at a layer's height has to go through the same transform.
_zmul = _map.nodes["Math.006"].inputs[1].default_value
_zsub = _map.nodes["Math.007"].inputs[1].default_value

# opening morph: blend each node's position from Coords0 to Coordinates by a keyframed value, and grow nodes with no start state
_morph = _map.nodes.new("ShaderNodeValue")
_morph.name = "Morph"
_na0 = _map.nodes.new("GeometryNodeInputNamedAttribute")
_na0.data_type, _na0.inputs[0].default_value = "FLOAT_VECTOR", "Coords0"
_mix = _map.nodes.new("ShaderNodeMix")
_mix.data_type = "VECTOR"
_vin = [i for i in _mix.inputs if i.type == "VECTOR" and i.name in ("A", "B")]
_map.links.new(_na0.outputs[0], _vin[0])
_map.links.new(_map.nodes["Named Attribute"].outputs[0], _vin[1])
_map.links.new(_morph.outputs[0], _mix.inputs[0])
_map.links.new([o for o in _mix.outputs if o.type == "VECTOR"][0], _map.nodes["Separate XYZ"].inputs["Vector"])
_ns0 = _map.nodes.new("GeometryNodeInputNamedAttribute")
_ns0.data_type, _ns0.inputs[0].default_value = "FLOAT", "Scale0"
_one = _map.nodes.new("ShaderNodeMath"); _one.operation = "SUBTRACT"; _one.inputs[0].default_value = 1.0
_m_a = _map.nodes.new("ShaderNodeMath"); _m_a.operation = "MULTIPLY"
_m_b = _map.nodes.new("ShaderNodeMath"); _m_b.operation = "ADD"
_m_c = _map.nodes.new("ShaderNodeMath"); _m_c.operation = "MULTIPLY"
_map.links.new(_morph.outputs[0], _one.inputs[1])
_map.links.new(_ns0.outputs[0], _m_a.inputs[0]); _map.links.new(_one.outputs[0], _m_a.inputs[1])
_map.links.new(_m_a.outputs[0], _m_b.inputs[0]); _map.links.new(_morph.outputs[0], _m_b.inputs[1])
_map.links.new(_map.nodes["Named Attribute.001"].outputs[0], _m_c.inputs[0]); _map.links.new(_m_b.outputs[0], _m_c.inputs[1])
_map.links.new(_m_c.outputs[0], _map.nodes["Instance on Points"].inputs["Scale"])
for _f, _v in ((0, 0.0), (f_m0, 0.0), (f_m1, 1.0)):
    _morph.outputs[0].default_value = _v
    _morph.outputs[0].keyframe_insert("default_value", frame=_f)

def _zw(z: float) -> float:
    return z * _zmul - _zsub

_inv = {r: p for p, r in _pr.items()}
_font = bpy.data.objects["Text"].data.font

def _mat(name: str, rgb: tuple, strength: float = 1.0, alpha: float = 1.0) -> "bpy.types.Material":
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (*rgb, 1)
    em.inputs[1].default_value = strength
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
    return m

# The template's compositor applies a large gain (a linear 0.06 comes out near white), so dark things
# need near-zero emission and anything coloured needs a tiny strength to stay subtle.
_m_title, _m_sub, _m_line = _mat("FRTitle", (0.0, 0.0, 0.0)), _mat("FRSub", (0.002, 0.002, 0.003)), _mat("FRLine", (0.0, 0.0, 0.0))

def _text(name, body, size, loc, align):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.align_x, cu.font = body, size, align, _font
    o = bpy.data.objects.new(name, cu)
    o.location, o.rotation_euler = loc, (rx, 0, 0)
    scene.collection.objects.link(o)
    return o, cu

def _window(o, on: int, off: int) -> None:
    o.hide_render = True
    o.keyframe_insert("hide_render", frame=0)
    o.hide_render = False
    o.keyframe_insert("hide_render", frame=on)
    o.hide_render = True
    o.keyframe_insert("hide_render", frame=off)


def _rrect(x0, x1, y0, y1, r, n=10):
    pts = []
    for cx_, cy_, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx_ + r * math.cos(a), cy_ + r * math.sin(a), 0))
    return pts

def _glass_card(name, x0, x1, y0, y1, r, depth):
    """Two stacked rounded plates (rim, then pane) as camera-space overlays; returns the objects."""
    import bmesh
    objs = []
    for k, (grow, col, st, al) in enumerate(((0.0, (1, 1, 1), 0.06, 0.55), (-0.12, (1, 1, 1), 0.06, 0.78))):
        me = bpy.data.meshes.new(f"{name}{k}")
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in _rrect(x0 - grow, x1 + grow, y0 - grow, y1 + grow, r + grow)]
        bm.faces.new(vs)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(f"{name}{k}", me)
        scene.collection.objects.link(o)
        o.parent = cam
        o.location = (0, 0, -(depth + 0.15 * (1 - k)))
        o.visible_shadow = False
        me.materials.append(_mat(f"FRGlass{name}{k}", col, st, alpha=al))
        objs.append(o)
    return objs

_sup = pd.read_csv(str(_ROOT / "output_2005/supervision_edges.csv"), dtype=str, keep_default_na=False, usecols=["nnt", "year", "director_key"])
_sup = _sup[_sup.year.astype(int) <= 2025]
_nmu = nm.drop_duplicates("id").set_index("id")
sys.path.insert(0, str(_ROOT / "scripts"))
from discipline_fields import field_of
# the thesis's OWN discipline (theses.fr), mapped to the same broad fields as the nodes: defined for every thesis,
# whether or not its supervisors are in the plotted network
_thd = pd.read_csv(str(_ROOT / "output_2005/theses.csv"), dtype=str, keep_default_na=False, usecols=["nnt", "year", "discipline"]).drop_duplicates("nnt")
_thd["yr"] = _thd.year.astype(int)
_thd["fo"] = pd.to_numeric(_thd.discipline.map(field_of).replace("", np.nan))
_thd = _thd[_thd.yr.between(2005, 2025)]
_sup["cl"] = _sup.director_key.map(_nmu.cluster_id)
_sup["fo"] = _sup.nnt.map(_thd.set_index("nnt").fo)
_sup = _sup.dropna(subset=["cl"]).assign(cl=lambda d: d.cl.astype(int)).drop_duplicates(["nnt", "cl"])
_sup["yr"] = _sup.year.astype(int)
TH = _sup.groupby("cl").size()                                       # distinct theses per sub-cluster
THF = _sup.groupby(["cl", "fo"]).size()                              # ... split by the field of the supervising director
SW_PT, SW_DY = float(os.environ.get("FR_SW_PT", 1.045)), float(os.environ.get("FR_SW_DY", 0.36))   # swatch line pitch / offset above the baseline, in heading sizes
CARD_DEPTH = float(os.environ.get("FR_CARD_DEPTH", 0.5))   # fraction of the camera-to-centre distance (1.0 dips into the floor)
LB_ROT = -90.0                                       # bars stand in the card plane: height = screen-up, depth = toward the camera
LB_T = float(os.environ.get("FR_LB_T", 0.55))        # how far the bars protrude from the card
def _bar_mesh(name):
    """Unit box standing on z=0 with its faces tagged top / front (-Y) / sides, so three flat materials fake the shading."""
    me = bpy.data.meshes.new(name)
    v = [(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0), (-.5, -.5, 1), (.5, -.5, 1), (.5, .5, 1), (-.5, .5, 1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    me.update()
    idx = [2, 0, 1, 2, 3, 2]       # bottom, top, front(-Y), +X, back(+Y), -X  -> materials [top, front, side]
    for poly, mi in zip(me.polygons, [2, 0, 1, 2, 2, 2]):
        poly.material_index = mi
    return me

_bar_mat_cache: dict = {}

def _bar_mats(f):
    if f not in _bar_mat_cache:
        c = colors[f][:3]
        _bar_mat_cache[f] = [_mat(f"FRLB{f}_{k}", tuple(v * w for v in c), 0.11) for k, w in enumerate((1.0, 0.8, 0.6))]
    return _bar_mat_cache[f]

_cut_frames: list[tuple[int, float]] = [(0, n_layers - 1)]
_edge_hide: list[tuple] = []
_up = Vector((0, math.cos(rx), math.sin(rx)))     # screen-up in world space for a camera-facing object
frame = f_layers0
prev_t, prev_r = target_now, R_LABEL
for rank in range(n_layers - 1, -1, -1):
    m = nm[nm.parent == _inv[rank]]
    cx, cy, cz = float(m.x.median()), float(m.y.median()), _zw(float(m.z.mean()))
    rad = max(8.0, float(((m.x - cx) ** 2 + (m.y - cy) ** 2).pow(0.5).quantile(0.9)) * 1.1)
    centre = Vector((cx, cy, cz))
    on, off = frame + MOVE, frame + MOVE + HOLD

    # label: the fields that make up the layer (not just the biggest), then the top disciplines.
    # Drawn as an overlay in camera space, in front of all geometry, so the graph can never hide or clip it.
    shares = m.FOR1.astype(int).astype(str).value_counts(normalize=True)
    pick, cum = [], 0.0
    for code, sh in shares.items():
        pick.append((code, sh))
        cum += sh
        if cum >= 0.65 or len(pick) == 3:
            break
    heading = "\n".join(f"{SHORT.get(c, c)} {sh:.0%}" for c, sh in pick)
    top_disc = [d for d in m.discipline.value_counts().index[:2]] if "discipline" in m else []
    sub_body = textwrap.fill(", ".join(top_disc), 22) + f"\n{len(m):,} directors"
    # sub-clusters whose own field is not in the heading (e.g. a computing hub inside a biomedical layer) are
    # still visible in the 3D view, so name the largest one rather than let the label contradict the picture
    shown = {int(c) for c, _ in pick}
    cl = m.groupby("cluster_id").agg(n=("FOR1", "size"), f=("FOR1", lambda v: int(v.mode().iloc[0])),
                                     d=("discipline", lambda v: v.value_counts().index[0] if len(v) else ""))
    cl = cl[~cl.f.isin(shown) & (cl.n >= 0.04 * len(m))].sort_values("n", ascending=False)
    hub_f, hub_i = None, 0
    if len(cl):
        r0 = cl.iloc[0]
        hub_f, hub_i = int(r0.f), sub_body.count("\n") + 1
        sub_body += "\n" + textwrap.fill(f"Hub: {r0.d} ({int(r0.n):,})", 26)
    # completed theses per sub-cluster, bar colour = the sub-cluster's own focus field
    _cf = m.groupby("cluster_id").FOR1.agg(lambda v: int(v.mode().iloc[0]))
    _ly = _sup[_sup.cl.isin(set(m.cluster_id.astype(int)))].drop_duplicates("nnt")
    _yf = _ly.dropna(subset=["fo"]).assign(fo=lambda d: d.fo.astype(int)).groupby(["yr", "fo"]).size()
    _bars = []
    for y_ in range(2005, 2026):
        if y_ in _yf.index.get_level_values(0):
            pr = [(int(f_), int(n_)) for f_, n_ in _yf.loc[y_].sort_values(ascending=False).items()]
            _bars.append((sum(n_ for _, n_ in pr), pr))
        else:
            _bars.append((0, []))
    if sum(v for v, _ in _bars) < 30:
        _bars = []
    cap = f"Theses per year, max {max(v for v, _ in _bars):,}" if _bars else ""
    f1 = int(m.FOR1.mode().iloc[0])
    col = colors[f1][:3]
    side = -1 if cx < 0 else 1
    align = "RIGHT" if side < 0 else "LEFT"

    D = 40.0                                            # depth of the label plane in camera space
    half_w = D * 0.3640                                 # half the frame width at that depth (50 mm lens, 36 mm sensor)
    half_h = half_w * 1391 / 1966
    _inv_rot = Euler((rx, 0, 0)).to_matrix().transposed()

    def _to_cam(p: Vector) -> tuple[float, float]:
        l = _inv_rot @ (p - cam_loc)
        f = D / -l.z
        return l.x * f, l.y * f

    TS, SS = LABEL_HEAD * D / R_LABEL, LABEL_SUB * D / R_LABEL      # same size on screen at every zoom
    n_head = heading.count("\n") + 1
    n_sub = sub_body.count("\n") + 1
    w_head = max(len(s) for s in heading.split("\n")) * 0.36 * TS
    w_sub = max(len(s) for s in sub_body.split("\n")) * 0.36 * SS
    CS = SS * 0.78                                      # caption size
    CH_H = 2.7 if _bars else 0.0                        # on-screen height of the tallest bar
    width = max(w_head, w_sub, len(cap) * 0.36 * CS)
    block = n_head * TS * 1.2
    pad = 0.75 * TS
    # the card hugs one frame edge; the camera is zoomed and shifted so the whole layer sits in the free part of the frame
    SQ, SG = 0.5 * TS, 0.3 * TS                          # colour swatch beside the field names: size, gap
    cw = width + 2 * pad + SQ + SG
    free = 2 * 0.97 * half_w - cw - 0.04 * half_w
    R = min(R_MAX, max(R_MIN, 3.4 * rad * D / free))
    rho = rad * D / R                                    # layer radius on screen
    mid = side * (0.97 * half_w - cw - 0.02 * half_w - 1.1 * rho)   # layer sits just beside the card, not mid-way across the free space
    centre_t = centre - Vector((1, 0, 0)) * (mid * R / D)
    on, off = frame + MOVE, frame + MOVE + HOLD
    _fly(frame, on, prev_t, prev_r, centre_t, R)
    _cam_key(off, centre_t, R)
    prev_t, prev_r = centre_t, R
    cam_loc = centre_t + Vector((0, -math.sin(rx), math.cos(rx))) * R
    total = block + SS * 0.8 + n_sub * SS * 1.25 + (SS * 0.9 + CH_H + CS * 1.7 if _bars else 0.0)
    px, py = _to_cam(Vector((cx + side * rad * 1.25, cy, cz)))
    ex, ey = _to_cam(centre)
    px = 0.93 * half_w - width if side > 0 else -0.93 * half_w + width
    py = max(-0.88 * half_h + total - block * 0.5, min(0.88 * half_h - block * 0.5, py))
    base = (px, py + block * 0.5, -D)
    title, _ = _text(f"Layer{rank} title", heading, TS, base, align)
    sub, _ = _text(f"Layer{rank} sub", sub_body, SS, (0, -block - SS * 0.8, 0), align)
    sub.parent = title
    for o_ in (title, sub):
        o_.rotation_euler = (0, 0, 0)
    title.parent = cam
    title.data.materials.append(_m_title)
    sub.data.materials.append(_m_sub)
    chart_objs = []
    base_y = py + block * 0.5
    def _swatch(nm_, f, xs, yc, sz):
        me_ = bpy.data.meshes.new(nm_)
        h_ = sz / 2
        me_.from_pydata([(xs, yc - h_, 0), (xs + sz, yc - h_, 0), (xs + sz, yc + h_, 0), (xs, yc + h_, 0)], [], [(0, 1, 2, 3)])
        me_.update()
        me_.materials.append(_bar_mats(f)[1])
        o_ = bpy.data.objects.new(nm_, me_)
        scene.collection.objects.link(o_)
        o_.parent, o_.location = cam, (0, 0, -D)
        o_.visible_shadow = False
        return o_
    sw_x = (lambda sz: px + SG) if side < 0 else (lambda sz: px - SG - sz)
    swatches = []
    for i_, (code, _sh) in enumerate(pick):
        swatches.append(_swatch(f"Layer{rank} sw{i_}", int(code), sw_x(SQ), base_y - i_ * TS * SW_PT + TS * SW_DY, SQ))
    if hub_f is not None:
        sq2 = SQ * 0.85
        swatches.append(_swatch(f"Layer{rank} swhub", hub_f, sw_x(sq2), base_y - block - SS * 0.8 - hub_i * SS * 1.015 + SS * 0.33, sq2))
    chart_objs.extend(swatches)
    # frosted-glass card behind the text: translucent white, soft rim, big corner radius
    top_y = py + block * 0.5 + TS * 0.9 + pad * 0.5
    y_last = py + block * 0.5 - block - SS * 0.8 - (n_sub - 1) * SS * 1.25
    bot_y = y_last - pad * 0.35
    if _bars:
        ch_top = y_last - SS * 0.9
        ch_base = ch_top - CH_H
        pitch = min(width / len(_bars), 0.8)
        piv = bpy.data.objects.new(f"Layer{rank} bars", None)
        scene.collection.objects.link(piv)
        piv.parent, piv.location = cam, (0, ch_base, -(D + 0.3) + 0.02)
        piv.rotation_euler = (math.radians(LB_ROT), 0, 0)
        mx0 = max(v for v, _ in _bars)
        bw = pitch * 0.78
        for i, (v, parts) in enumerate(_bars):
            z0 = 0.0
            for j, (f, n) in enumerate(parts):
                h = n / mx0 * CH_H
                if h < 0.02:
                    continue
                o = bpy.data.objects.new(f"Layer{rank} bar{i}_{j}", _bar_mesh(f"LB{rank}_{i}_{j}"))
                scene.collection.objects.link(o)
                for mt in _bar_mats(f):
                    o.data.materials.append(mt)
                o.parent = piv
                o.location = (px + side * (i + 0.5) * pitch, -LB_T / 2, z0)
                o.scale = (bw, LB_T, h)
                o.visible_shadow = False
                chart_objs.append(o)
                z0 += h
        chart_objs.append(piv)
        capo, _ = _text(f"Layer{rank} caption", cap, CS, (px, ch_base - CS * 1.35, -D), align)
        capo.rotation_euler = (0, 0, 0)
        capo.parent = cam
        capo.data.materials.append(_m_sub)
        chart_objs.append(capo)
        bot_y = ch_base - CS * 1.35 - CS * 0.5 - pad * 0.35
    x0, x1 = (px - pad - SQ - SG, px + width + pad) if side > 0 else (px - width - pad, px + pad + SQ + SG)
    x0, x1 = max(x0, -0.97 * half_w), min(x1, 0.97 * half_w)
    glass = _glass_card(f"Layer{rank} glass", x0, x1, bot_y, top_y, min(1.6 * pad, (top_y - bot_y) / 2.2), D + 0.3)
    # thin pointer from the label to the layer's centre, ending in a dot (also an overlay)
    sx = x0 if side > 0 else x1
    cu = bpy.data.curves.new(f"Layer{rank} pointer", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.resolution_u = "3D", 0.035, 1
    sp = cu.splines.new("POLY")
    sp.points.add(1)
    sp.points[0].co, sp.points[1].co = (sx, py, -D, 1), (ex, ey, -D, 1)
    cu.materials.append(_m_line)
    line = bpy.data.objects.new(f"Layer{rank} pointer", cu)
    scene.collection.objects.link(line)
    line.parent = cam
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(ex, ey, -D), segments=16, ring_count=8)
    dot = bpy.context.active_object
    dot.name = f"Layer{rank} dot"
    dot.parent = cam
    dot.data.materials.append(_mat(f"FRDot{rank}", col, 0.05))
    # halo: a translucent disc in the layer's colour at its height
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=rad, fill_type="NGON", location=centre)
    halo = bpy.context.active_object
    halo.name = f"Layer{rank} halo"
    halo.data.materials.append(_mat(f"FRHalo{rank}", col, 0.045, alpha=0.5))
    halo.visible_shadow = False
    # sit the card back at the depth of the layer's centre: same screen position and size, but it lives in the scene
    k_ = CARD_DEPTH * R / D
    root = bpy.data.objects.new(f"Layer{rank} card root", None)
    scene.collection.objects.link(root)
    root.parent, root.scale = cam, (k_, k_, k_)
    for o in (title, line, dot, *glass, *chart_objs):
        if o.parent == cam:
            o.parent = root
    for o in (title, sub, line, dot, halo, *glass, *chart_objs):
        _window(o, on, off)
    _cut_frames.append((off, rank - 1))
    _edge_hide.append((rank, off))
    frame = off

_fly(frame, frame + OUTRO, prev_t, prev_r, target_now, R_LABEL)     # back out for the closing cards
frame += OUTRO

for _fc in cam.animation_data.action.fcurves:
    for _kp in _fc.keyframe_points:
        _kp.interpolation = "LINEAR"

for cid, o in cluster_objs.items():
    rank = _pr.get(_parent_of.get(cid), None) if _parent_of is not None else None
    off = next((f for r, f in _edge_hide if r == rank), None)
    on_e = f_m1 - 6 + 2 * (rank or 0)                       # edges appear layer by layer as the nodes settle
    o.hide_render = True
    o.keyframe_insert("hide_render", frame=0)
    o.hide_render = False
    o.keyframe_insert("hide_render", frame=on_e)
    if off is not None:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=off)

for f, v in _cut_frames:
    _cut.outputs[0].default_value = v
    _cut.outputs[0].keyframe_insert("default_value", frame=f)

for _id in [bpy.data.objects[n].animation_data for n in [o.name for o in bpy.data.objects] if bpy.data.objects[n].animation_data] + [_map.animation_data]:
    if _id and _id.action:
        for _fc in _id.action.fcurves:
            if _fc.data_path in ("hide_render", 'nodes["LayerCut"].outputs[0].default_value'):
                for _kp in _fc.keyframe_points:
                    _kp.interpolation = "CONSTANT"

f_end = frame + 12
print(f"layers: {n_layers}, labels from frame {f_layers0}, end {f_end}")

# ----------------------------------------------------------------------
# Closing cards: how the network was made, source material and credits. Text sits in camera space
# (like the legend), each card fades in, holds for a reading time, and fades out. The legend is hidden
# meanwhile so the cards can use the whole frame and be large.
# ----------------------------------------------------------------------
f_credits0 = f_end
CARDS = [
    ("Source material", [
        "Thesis records: theses.fr (Abes), every defence 2005-2025.",
        "People: IdRef identifiers (Abes).",
        "ORCID iDs for 52,362 of 103,202 supervisors. Co-authorship from the ORCID public data file (2026).",
    ]),
    ("How the network was built", [
        "Nodes: 85,516 supervisors in the main network.",
        "Links: a shared thesis (about 121,000) or a shared DOI between ORCID records (about 357,000).",
        "Coverage: 85% of theses (234,967 of 274,842) have a supervisor in it.",
    ]),
    ("Layout, layers and colour", [
        "Layout: BatchLayout. Communities: Leiden (Traag, Waltman and van Eck, 2019), then 181 sub-clusters, one height each.",
        "Colour: field of research. Size: theses supervised.",
    ]),
    ("Credits: data, method and tools", [
        "Data: theses.fr and IdRef (Abes); ORCID public data file.",
        "Method and colours: UniversityExplorer, Digital Science and Dimensions.",
        "Tools: BatchLayout, NetworkX, igraph, leidenalg, datashader, Blender.",
    ]),
    ("Credits: people and project", [
        "The 3D model approach was developed\nas part of the project\n\"What does a University Look like\":\nfigshare.com/projects/\nWhat_does_a_university_look_like_/159509",
        "Concept and analysis: Simon Porter. Built with Claude Code (Anthropic).",
    ]),
]
for _n in ("Label2", "Text", "Text.001", "Text.002"):          # legend off from the first zoom
    _lo = bpy.data.objects[_n]
    _lo.hide_render = False
    _lo.keyframe_insert("hide_render", frame=0)
    _lo.hide_render = True
    _lo.keyframe_insert("hide_render", frame=f_layers0)
    for _fc in _lo.animation_data.action.fcurves:
        for _kp in _fc.keyframe_points:
            _kp.interpolation = "CONSTANT"
for _n in ("Title", "Title.001"):                              # title off for the cards (it collides with the headings)
    _lo = bpy.data.objects[_n]
    _lo.hide_render = False
    _lo.keyframe_insert("hide_render", frame=0)
    _lo.hide_render = True
    _lo.keyframe_insert("hide_render", frame=f_credits0)
for _n in ("Title", "Title.001"):
    for _fc in bpy.data.objects[_n].animation_data.action.fcurves:
        for _kp in _fc.keyframe_points:
            _kp.interpolation = "CONSTANT"
HUD_Z = -154.0           # camera-space distance of the legend, so the cards sit in the same plane
FADE = 12
WPS_FRAMES = float(os.environ.get("FR_CARD_FRAMES_PER_WORD", 6))   # reading time per word, in frames
BODY, HEAD, LEAD = 4.6, 7.2, 5.8
WRAP = 36

# ----------------------------------------------------------------------
# 3D bar chart of completed (defended) theses per year, standing on every card.
# ----------------------------------------------------------------------
_t = pd.read_csv(str(_ROOT / "output_2005/theses.csv"), dtype=str, keep_default_na=False, usecols=["nnt", "year"])
_by_year = _t.drop_duplicates("nnt").assign(year=lambda d: d.year.astype(int)).query("2005 <= year <= 2025").groupby("year").size()
CH_YEARS, CH_VALS = _by_year.index.tolist(), _by_year.tolist()
CH_MAX = max(CH_VALS)
print("bar chart:", dict(zip(CH_YEARS, CH_VALS)), "total", sum(CH_VALS))

def _fade_mat(name, rgb, strength, on, off, fade):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out_n = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (*rgb, 1)
    em.inputs[1].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out_n.inputs[0])
    for f, v in ((on, 0.0), (on + fade, 1.0), (off - fade, 1.0), (off, 0.0)):
        mx.inputs[0].default_value = v
        mx.inputs[0].keyframe_insert("default_value", frame=f)
    return m

CH_ROT_X, CH_ROT_Z, CH_SCALE = float(os.environ.get("FR_CH_RX", -52)), float(os.environ.get("FR_CH_RZ", -8)), float(os.environ.get("FR_CH_S", 1.54))
CH_POS = (float(os.environ.get("FR_CH_X", 33)), float(os.environ.get("FR_CH_Y", -12)), HUD_Z)

def _bar_chart(tag, on, off, text_mat):
    outer = bpy.data.objects.new(f"Chart {tag}", None)
    scene.collection.objects.link(outer)
    outer.parent, outer.location = cam, CH_POS
    outer.rotation_euler = (math.radians(CH_ROT_X), 0, 0)
    outer.scale = (CH_SCALE,) * 3
    inner = bpy.data.objects.new(f"Chart {tag} plane", None)
    scene.collection.objects.link(inner)
    inner.parent = outer
    inner.rotation_euler = (0, 0, math.radians(CH_ROT_Z))
    mats = [_fade_mat(f"FRBar{tag}{k}", c, 0.05, on, off, FADE) for k, c in enumerate(((0.35, 0.62, 1.0), (0.14, 0.36, 0.80), (0.07, 0.20, 0.50)))]
    me = _bar_mesh(f"FRBarMesh{tag}")
    for m_ in mats:
        me.materials.append(m_)
    H = 9.5
    n = len(CH_YEARS)
    for i, (yr, val) in enumerate(zip(CH_YEARS, CH_VALS)):
        o = bpy.data.objects.new(f"Bar {tag} {yr}", me)
        scene.collection.objects.link(o)
        o.parent = inner
        o.location = ((i - (n - 1) / 2) * 1.0, 0, 0)
        o.visible_shadow = False
        h = val / CH_MAX * H
        st = on + i * 0.2
        o.scale = (0.8, 0.8, 0.001)
        o.keyframe_insert("scale", frame=int(st))
        o.scale = (0.8, 0.8, h)
        o.keyframe_insert("scale", frame=int(st) + 8)
        _window(o, on, off)
    def label(txt, size, loc, rot, align="CENTER"):
        o, _ = _text(f"Chart {tag} {txt}", txt, size, (0, 0, 0), align)
        o.parent, o.location, o.rotation_euler = inner, loc, rot
        o.data.materials.append(text_mat)
        _window(o, on, off)
        return o
    up = (math.radians(90), 0, 0)
    for yr in (2005, 2010, 2015, 2020, 2025):
        label(str(yr), 1.15, ((CH_YEARS.index(yr) - (n - 1) / 2), -0.9, -1.6), up)
    pk = CH_VALS.index(CH_MAX)
    label(f"{CH_MAX:,}", 1.15, ((pk - (n - 1) / 2), -0.55, H + 0.9), up)
    label("Theses defended per year", 1.5, (-(n - 1) / 2 - 0.4, -0.5, H + 3.0), up, "LEFT")
    label(f"{sum(CH_VALS):,} theses, 2005-2025", 1.15, (-(n - 1) / 2 - 0.4, -0.5, H + 1.5), up, "LEFT")

cf = f_credits0 + 12
CARD_HOLDS: list[tuple[int, int]] = []
CARD_SPANS: list[tuple[int, int]] = []
for _title, _paras in CARDS:
    words = sum(len(p.split()) for p in _paras) + len(_title.split())
    hold = max(120, int(words * WPS_FRAMES))
    on, off = cf, cf + FADE + hold + FADE
    m = bpy.data.materials.new(f"FRCard{_title}")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out_n = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (0.0, 0.0, 0.0, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out_n.inputs[0])
    for f, v in ((on, 0.0), (on + FADE, 1.0), (off - FADE, 1.0), (off, 0.0)):
        mix.inputs[0].default_value = v
        mix.inputs[0].keyframe_insert("default_value", frame=f)
    objs = []
    y = 28.0
    o, _ = _text(f"Card {_title} head", _title, HEAD, (0, 0, 0), "LEFT")
    objs.append((o, y))
    y -= HEAD * 1.1 + 3.5
    for p in _paras:
        w = p if "\n" in p else textwrap.fill(p, WRAP)
        o, _ = _text(f"Card {_title} p", w, BODY, (0, 0, 0), "LEFT")
        objs.append((o, y))
        y -= (w.count("\n") + 1) * LEAD + 2.6
    assert y > -40, f"card '{_title}' runs off the frame (y={y:.1f}); shorten it"
    for o, yy in objs:
        o.parent = cam
        o.location = (-50.0, yy, HUD_Z)
        o.rotation_euler = (0, 0, 0)
        o.data.materials.append(m)
        _window(o, on, off)
    CARD_HOLDS.append((on + FADE, off - FADE))
    CARD_SPANS.append((on, off))
    cf = off + 6
f_end = cf + 24

# ----------------------------------------------------------------------
# All completed theses per year, standing in the card plane beside the credits. It starts as plain totals and gains
# detail as the cards change: totals -> top fields + other -> every field (same silhouette, so only the colours split).
# ----------------------------------------------------------------------
_all = _thd.dropna(subset=["fo"]).assign(fo=lambda d: d.fo.astype(int))
_yfa = _all.groupby(["yr", "fo"]).size()
_order = [int(f_) for f_ in _all.fo.value_counts().index]
_GREY = (0.62, 0.62, 0.62)
def _groups(yr, nkeep):
    tot = CH_VALS[CH_YEARS.index(yr)]
    row = {int(f_): int(n_) for f_, n_ in _yfa.loc[yr].items()} if yr in _yfa.index.get_level_values(0) else {}
    keep = _order if nkeep is None else _order[:nkeep]
    parts = [(f_, row[f_]) for f_ in keep if row.get(f_, 0) > 0]
    rest = tot - sum(n_ for _, n_ in parts)
    if rest > 0:
        parts.append((None, rest))
    return parts
_lv_tot = [(None, v) for v in CH_VALS]
CS0, CS1, CS2 = CARD_SPANS[0][0], CARD_SPANS[-1][1], None
_sw1 = CARD_SPANS[1][0] - 3
_sw2 = CARD_SPANS[2][0] - 3
_fm_cache: dict = {}
def _cmats(f):
    if f not in _fm_cache:
        c = (0.35, 0.55, 0.95) if f == "tot" else _GREY if f is None else tuple(colors[f][:3])
        _fm_cache[f] = [_fade_mat(f"FRCh{f}_{k}", tuple(v * w for v in c), 0.11, CS0, CS1, FADE) for k, w in enumerate((1.0, 0.8, 0.6))]
    return _fm_cache[f]
_ctext = _fade_mat("FRChText", (0.0, 0.0, 0.0), 1.0, CS0, CS1, FADE)
CX0, CX1, CYB, CHH, CT_ = 14.0, 52.0, -23.0, 21.0, 3.0
_cp = (CX1 - CX0) / len(CH_YEARS)
_cpiv = bpy.data.objects.new("AllTheses pivot", None)
scene.collection.objects.link(_cpiv)
_cpiv.parent, _cpiv.location = cam, (0, CYB, HUD_Z)
_cpiv.rotation_euler = (math.radians(-90), 0, 0)
for _lvl, (_a, _b, _fn) in enumerate(((CS0, _sw1, lambda y: [("tot", CH_VALS[CH_YEARS.index(y)])]),
                                      (_sw1, _sw2, lambda y: _groups(y, 6)),
                                      (_sw2, CS1, lambda y: _groups(y, None)))):
    for _i, _yr in enumerate(CH_YEARS):
        z0 = 0.0
        for _j, (_f, _n) in enumerate(_fn(_yr)):
            h = _n / CH_MAX * CHH
            o = bpy.data.objects.new(f"AllTheses L{_lvl} {_yr} {_j}", _bar_mesh(f"AT{_lvl}_{_yr}_{_j}"))
            scene.collection.objects.link(o)
            for mt in _cmats(_f):
                o.data.materials.append(mt)
            o.parent = _cpiv
            o.location = (CX0 + (_i + 0.5) * _cp, -CT_ / 2, z0)
            o.visible_shadow = False
            if _lvl == 0:                       # grow in with the first card
                st = CS0 + int(_i * 0.2)
                o.scale = (_cp * 0.78, CT_, 0.001)
                o.keyframe_insert("scale", frame=st)
                o.scale = (_cp * 0.78, CT_, h)
                o.keyframe_insert("scale", frame=st + 8)
            else:
                o.scale = (_cp * 0.78, CT_, h)
            _window(o, _a, _b)
            z0 += h
def _chtext(txt, size, x, y, align="LEFT"):
    o, _ = _text(f"AllTheses {txt}", txt, size, (x, y, HUD_Z), align)
    o.rotation_euler = (0, 0, 0)
    o.parent = cam
    o.data.materials.append(_ctext)
    _window(o, CS0, CS1)
_chtext("Theses completed per year", 2.9, CX0, CYB + CHH + 7.5)
_chtext(f"{sum(CH_VALS):,} theses, 2005-2025 (peak {CH_MAX:,})", 2.2, CX0, CYB + CHH + 3.8)
for _txt, _a, _b in (("Grey: all other fields", _sw1, _sw2), ("Grey: discipline not mapped to a field", _sw2, CS1)):
    _o, _ = _text(f"AllTheses note {_a}", _txt, 1.9, (CX0, CYB - 8.2, HUD_Z), "LEFT")
    _o.rotation_euler = (0, 0, 0)
    _o.parent = cam
    _o.data.materials.append(_ctext)
    _window(_o, _a, _b)
for _yr in (2005, 2010, 2015, 2020, 2025):
    _chtext(str(_yr), 2.0, CX0 + (CH_YEARS.index(_yr) + 0.5) * _cp, CYB - 4.2, "CENTER")
import json
open(f"{output_dir}{grid_id}/holds.json", "w").write(json.dumps({"holds": CARD_HOLDS, "end": f_end}))
print(f"cards: {len(CARDS)}, from frame {f_credits0 + 1}, end {f_end}")

# Opening captions: the supervisor-only graph, then the morph into the combined graph. Same fade material as the cards.
def _caption(tag, head, body, on, off, y):
    m = bpy.data.materials.new(f"FRCap{tag}")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out_n = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (0.0, 0.0, 0.0, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out_n.inputs[0])
    for f, v in ((max(0, on - FADE), 0.0), (on, 1.0), (off - FADE, 1.0), (off, 0.0)):
        mix.inputs[0].default_value = v
        mix.inputs[0].keyframe_insert("default_value", frame=f)
    nh = head.count("\n") + 1
    for txt, size, yy in ((head, CAP_H, y), (body, CAP_B, y - nh * CAP_H * 1.3 - 2.0)):
        o, _ = _text(f"Caption {tag}", txt, size, (0, 0, 0), "LEFT")
        o.parent, o.location, o.rotation_euler = cam, (-50.0, yy, HUD_Z), (0, 0, 0)
        o.data.materials.append(m)
        _window(o, max(0, on - FADE), off)

CAP_Y, CAP_H, CAP_B = float(os.environ.get("FR_CAP_Y", 16)), 4.6, 3.3
_caption("A", "Co-supervision\nonly", "Supervisors who\nshared a thesis,\n2005-2025.", 12, f_m0 + 30, CAP_Y)
_caption("B", "Adding ORCID\nco-authorship", "Shared publications\nreshape the map;\ncommunities rise\ninto layers.", f_m0 + 42, f_m1 + 24, CAP_Y)

# Bigger legend for small screens (the template's is tiny). Scaled about each object's own origin, then nudged up.
LEG_S = float(os.environ.get("FR_LEGEND_SCALE", 1.0))
for _n in ("Label2", "Text", "Text.001", "Text.002"):
    _lo = bpy.data.objects[_n]
    _lo.scale = (_lo.scale[0] * LEG_S, _lo.scale[1] * LEG_S, _lo.scale[2] * LEG_S)
bpy.data.objects["Label2"].location.y += float(os.environ.get("FR_LEGEND_LIFT", 0))
for _n in ("Text", "Text.001", "Text.002"):
    bpy.data.objects[_n].location.y += float(os.environ.get("FR_LEGEND_LIFT", 0))

scene.frame_start, scene.frame_end = 0, f_end
scene.frame_current = f_move1
print(f"camera: top-down 0-{f_move0}, move {f_move0}-{f_move1}, hold to {f_orb0}, orbit {f_orb0}-{f_orb1}")

# Preview/animation resolution: the poster size is 14043 x 9933; 14% gives ~1966 x 1391.
bpy.context.scene.render.resolution_percentage = int(os.environ.get("FR_RES_PCT", "14"))
bpy.context.scene.render.image_settings.color_depth = "8"

bpy.ops.wm.save_as_mainfile(filepath=f"{output_dir}{grid_id}/University.blend")
