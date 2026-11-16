"""
《对账》试播集 · Blender Q2 精品档 previs 生成器 (light & camera consistency)
=============================================================================
Purpose : Q2 灰模预演。验证「同一夜被三个视角讲三遍」时的两态光位、
         三视角机位一致性与连拍动线。不产生任何成片三维镜头。
         Final 3D shots = 0. No render. No materials. No final CG assets.

Run    : blender -b -P 对账_blender_q2_previs_v1.py
Output : 对账_Q2_previs_v01.blend (same folder as this script)

Notes  : 1) Object names are ASCII ONLY (Windows / Blender console safety).
         2) NO readable text: no hospital name, logo, drug name, dosage,
            form fields or on-screen system UI (compliance, 110).
            Higher image quality = higher risk of readable details.
         3) Dimensions are PLACEHOLDERS (24m x 12m, wall 3m). Re-layout S00
            with the real set dimensions before any camera conclusion is used.
         4) Not executed locally (Blender not installed). AST-validated only.
         5) Blender 4.x; EEVEE engine id has a 4.2 pre/post compatibility fallback.

KB baseline: 2026-09 | doc version: v1 | date: 2026-11-15
"""

import os
import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
OUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "对账_Q2_previs_v01.blend"
)

FLOOR_W, FLOOR_D, WALL_H = 24.0, 12.0, 3.0
CORRIDOR_W = 2.4

GREY = (0.55, 0.55, 0.55, 1.0)
ZONE_ON = (0.20, 0.72, 0.52, 1.0)    # CIRCUIT_EMERGENCY - power during blackout
ZONE_OFF = (0.75, 0.35, 0.35, 1.0)   # CIRCUIT_NORMAL - no power during blackout
COLD_WHITE = (1.0, 1.0, 1.0)
EMERGENCY_GREEN = (0.35, 1.0, 0.55)
DESK_WARM = (1.0, 0.72, 0.42)

# (collection, x0, x1, y0, y1, circuit)
# corridor is centred on y=0; rooms sit on both sides
ROOMS = [
    ("S02_NurseStation", -10.0, -4.0,  1.2,  5.6, "EMERGENCY"),
    ("S03_Pantry",        -3.5, -0.5,  1.2,  4.0, "NORMAL"),
    ("S06_Pharmacy",       0.5,  5.5,  1.2,  5.0, "NORMAL"),
    ("S04_AdminOffice",    6.5, 11.5,  1.2,  5.0, "NORMAL"),
    ("S05_SwitchRoom",    -6.0, -3.0, -4.2, -1.2, "EMERGENCY"),
]

# (name, location, target, scene_no, perspective, note)
CAMERAS = [
    ("CAM_S00_overview",      (0.0, 0.0, 14.0),  (0.0, 0.0, 0.0),   "S00", "overview", "floor plan / blocking"),
    ("CAM_S01_coldopen",     (-11.0, 0.0, 1.65), (2.0, 0.0, 1.40),  "S01", "coldopen", "blackout moment"),
    ("CAM_S01_A_audit",       (-9.0, 0.9, 1.65), (-1.0, 0.0, 1.40), "S01", "A", "Shen Yan walkthrough"),
    ("CAM_S01_B_nurse",       (-3.0,-0.9, 1.60), ( 3.0, 0.0, 1.35), "S01", "B", "Luo Hui walkthrough"),
    ("CAM_S01_C_admin",       (10.5, 0.9, 1.65), ( 1.0, 0.0, 1.40), "S01", "C", "Jiang Pei walkthrough"),
    ("CAM_S22_pantry",        (-2.0, 2.6, 1.55), (-2.0, 3.3, 0.95), "S03", "A+B", "two cups and folder, no plot dialogue"),
    ("CAM_S37_admin",         ( 9.0, 3.1, 1.60), ( 9.0, 3.6, 0.85), "S04", "A+C", "desk lamp and shredder"),
    ("CAM_S31_switchroom",    (-4.5,-2.7, 1.65), (-4.5,-4.0, 1.10), "S05", "A+B+C", "only three-line convergence"),
]

# (label, origin, target) - coarse sightline self-check, NOT a substitute for a lighting test
RAY_CHECKS = [
    ("S01_A_to_admin_door",  (-11.0, 0.0, 1.65), ( 9.0, 1.2, 1.40)),
    ("S22_two_cups",          (-2.0, 2.6, 1.55), (-2.0, 3.3, 0.95)),
    ("S37_desk_lamp",         ( 9.0, 3.1, 1.60), ( 9.0, 3.6, 0.85)),
    ("S31_switch_cabinet",    (-4.5,-2.7, 1.65), (-4.5,-4.0, 1.10)),
]

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def new_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def add_box(col, name, loc, size, color=GREY, circuit=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    ob.color = color
    if circuit:
        ob["circuit"] = circuit
    return ob


def add_area_light(col, name, loc, energy, color, size=(1.2, 1.2), target=None):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.color = color
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    ob = bpy.data.objects.new(name, data)
    col.objects.link(ob)
    ob.location = loc
    if target:
        ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    return ob


def add_camera(col, spec):
    name, loc, target, scene_no, perspective, note = spec
    data = bpy.data.cameras.new(name)
    data.lens = 35
    ob = bpy.data.objects.new(name, data)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    ob["scene_no"] = scene_no
    ob["perspective"] = perspective
    ob["previs_note"] = note + " | placeholder, NOT final shot parameters"
    return ob


def add_stand_marker(col, name, loc, radius=0.28):
    """Empty circle marker for a blocking position. No human geometry."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius, minor_radius=0.02, location=loc
    )
    ob = bpy.context.object
    ob.name = name
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    ob.color = (0.95, 0.75, 0.25, 1.0)
    return ob


def set_state(state):
    """One-click light-state switch. Usage: set_state('NORMAL') / set_state('BLACKOUT')."""
    scene = bpy.context.scene
    on = bpy.data.collections.get("LIGHT_" + state)
    off_name = "LIGHT_BLACKOUT" if state == "NORMAL" else "LIGHT_NORMAL"
    off = bpy.data.collections.get(off_name)
    if on is None or off is None:
        raise RuntimeError("light collections missing")
    for ob in on.objects:
        ob.hide_render = False
        ob.hide_viewport = False
    for ob in off.objects:
        ob.hide_render = True
        ob.hide_viewport = True
    scene["light_state"] = state
    return state


def visibility_check(scene, label, origin, target):
    """Coarse ray cast. Wrapped: API signature differs across Blender versions."""
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        bpy.context.view_layer.update()
        o, t = Vector(origin), Vector(target)
        d = t - o
        dist = d.length
        d.normalize()
        hit = scene.ray_cast(dg, o, d, distance=dist)
        blocker = hit[4] if len(hit) > 4 else None
        if hit[0] and blocker is not None:
            return "%-24s BLOCKED by %s" % (label, blocker.name)
        return "%-24s CLEAR" % label
    except Exception as exc:
        return "%-24s SKIPPED (%s)" % (label, type(exc).__name__)


# ---------------------------------------------------------------------------
# SCENE SETUP
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.users == 0:
        bpy.data.collections.remove(c)

scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
for engine_id in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = engine_id
        break
    except TypeError:
        continue
if scene.world is None:
    scene.world = bpy.data.worlds.new("PrevisWorld")
scene.world.color = (0.05, 0.05, 0.05)

floor = new_collection("S00_Floorplan")
corridor = new_collection("S01_Corridor")
zone_on = new_collection("CIRCUIT_EMERGENCY")
zone_off = new_collection("CIRCUIT_NORMAL")
light_normal = new_collection("LIGHT_NORMAL")
light_blackout = new_collection("LIGHT_BLACKOUT")
cam_col = new_collection("CAM_PREVIS")
props = new_collection("PROPS_KEY")
room_cols = {name: new_collection(name) for name, *_ in ROOMS}

# Floor slab + corridor floor
add_box(floor, "FLOOR_slab", (0, 0, -0.10), (FLOOR_W, FLOOR_D, 0.20))
add_box(corridor, "CORRIDOR_floor", (0, 0, 0.01), (FLOOR_W, CORRIDOR_W, 0.02))

# Corridor walls in segments, leaving door gaps so the blocking route stays readable
for side in (-1, 1):
    y = side * CORRIDOR_W / 2
    for i in range(6):
        x = -10.0 + i * 4.0
        add_box(corridor, "CORRIDOR_wall_%s_%02d" % ("N" if side > 0 else "S", i),
                (x, y, WALL_H / 2), (2.6, 0.12, WALL_H))

# Corner occlusion block: keeps the admin office door out of the switch-room sightline
add_box(floor, "CORNER_occluder", (5.4, 0.0, WALL_H / 2), (1.6, 1.1, WALL_H))

# Rooms: floor + three walls (corridor side left open)
for name, x0, x1, y0, y1, circuit in ROOMS:
    col = room_cols[name]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    tag = name.split("_", 1)[0]
    add_box(col, "%s_floor" % tag, (cx, cy, 0.01), (w, d, 0.02), circuit=circuit)
    add_box(col, "%s_wall_back" % tag, (cx, y1 if cy > 0 else y0, WALL_H / 2),
            (w, 0.12, WALL_H), circuit=circuit)
    add_box(col, "%s_wall_left" % tag, (x0, cy, WALL_H / 2),
            (0.12, d, WALL_H), circuit=circuit)
    add_box(col, "%s_wall_right" % tag, (x1, cy, WALL_H / 2),
            (0.12, d, WALL_H), circuit=circuit)
    zcol = zone_on if circuit == "EMERGENCY" else zone_off
    zcolor = ZONE_ON if circuit == "EMERGENCY" else ZONE_OFF
    add_box(zcol, "ZONE_%s_%s" % (circuit, tag), (cx, cy, 0.035),
            (w - 0.3, d - 0.3, 0.03), color=zcolor, circuit=circuit)

# Key props: pure grey volumes, no readable information
add_box(props, "NS_counter", (-7.0, 2.6, 0.55), (3.2, 0.9, 1.1))
add_box(props, "NS_ledger_table", (-7.0, 3.8, 0.75), (2.0, 1.0, 0.05))
add_box(props, "PANTRY_counter", (-2.0, 3.3, 0.90), (1.8, 0.7, 0.06))
add_box(props, "PANTRY_cup_cold", (-2.5, 3.3, 0.98), (0.10, 0.10, 0.14),
        color=(0.45, 0.60, 0.75, 1.0))
add_box(props, "PANTRY_cup_hot", (-1.5, 3.3, 0.98), (0.10, 0.10, 0.14),
        color=(0.85, 0.45, 0.30, 1.0))
add_box(props, "PANTRY_folder", (-2.0, 3.0, 0.94), (0.32, 0.24, 0.02))
add_box(props, "PANTRY_chair_sweater", (-2.9, 2.4, 0.45), (0.5, 0.5, 0.9))
add_box(props, "ADMIN_desk", (9.0, 3.6, 0.75), (2.4, 1.1, 0.06))
add_box(props, "ADMIN_lamp", (9.9, 3.9, 1.05), (0.18, 0.18, 0.60))
add_box(props, "ADMIN_shredder", (8.1, 3.3, 0.35), (0.35, 0.30, 0.70))
add_box(props, "SWITCH_cabinet", (-4.5, -4.0, 1.10), (2.2, 0.6, 2.2))
add_box(props, "PHARM_shelf", (3.0, 4.6, 1.10), (4.0, 0.5, 2.2))

# Six blocking markers in the switch room (no human geometry)
for i, (dx, dy) in enumerate([(-1.4, -0.5), (-0.7, -0.9), (0.0, -0.5),
                              (0.7, -0.9), (1.4, -0.5), (0.0, 0.2)]):
    add_stand_marker(props, "STAND_S05_%02d" % i, (-4.5 + dx, -2.8 + dy, 0.05))

# ---------------------------------------------------------------------------
# Two light states
# ---------------------------------------------------------------------------
for i in range(5):
    x = -9.0 + i * 4.5
    add_area_light(light_normal, "NORMAL_ceil_%02d" % i, (x, 0, 2.85), 320,
                   COLD_WHITE, size=(1.6, 0.5))
for name, x0, x1, y0, y1, circuit in ROOMS:
    tag = name.split("_", 1)[0]
    add_area_light(light_normal, "NORMAL_%s" % tag,
                   ((x0 + x1) / 2, (y0 + y1) / 2, 2.85), 260,
                   COLD_WHITE, size=(1.2, 1.2))

for i in range(6):
    x = -10.0 + i * 4.0
    add_area_light(light_blackout, "OUT_emergency_%02d" % i, (x, 0.9, 0.35), 45,
                   EMERGENCY_GREEN, size=(0.35, 0.18), target=(x, 0, 1.2))
add_area_light(light_blackout, "OUT_corridor_end", (11.6, 0, 0.45), 70,
               EMERGENCY_GREEN, size=(0.5, 0.3), target=(0, 0, 1.2))
add_area_light(light_blackout, "OUT_nurse_residual", (-7.0, 3.0, 1.1), 30,
               EMERGENCY_GREEN, size=(0.4, 0.2), target=(-7.0, 3.8, 0.9))
add_area_light(light_blackout, "OUT_admin_desk", (9.0, 3.2, 1.25), 22,
               DESK_WARM, size=(0.3, 0.3), target=(9.0, 3.6, 0.8))
add_area_light(light_blackout, "OUT_switchroom", (-4.5, -2.2, 0.55), 35,
               EMERGENCY_GREEN, size=(0.4, 0.2), target=(-4.5, -4.0, 1.2))

set_state("BLACKOUT")

# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------
for spec in CAMERAS:
    add_camera(cam_col, spec)

# ---------------------------------------------------------------------------
# SAVE + REPORT
# ---------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=OUT_FILE)

print("=" * 68)
print("DUIZHANG / Q2 PREVIS GENERATED")
print("output      :", OUT_FILE)
print("engine      :", scene.render.engine)
print("light_state :", scene.get("light_state"))
print("collections :", sorted(c.name for c in scene.collection.children))
print("lights      : NORMAL=%d BLACKOUT=%d" %
      (len(light_normal.objects), len(light_blackout.objects)))
print("cameras     : %d" % len(cam_col.objects))
print("-" * 68)
print("CIRCUIT ZONES (power during the 47-min blackout)")
for name, x0, x1, y0, y1, circuit in ROOMS:
    print("  %-20s %s" % (name, circuit))
print("  %-20s %s" % ("S01_Corridor", "EMERGENCY"))
print("-" * 68)
print("SIGHTLINE SELF-CHECK (coarse; confirm with on-set lighting test)")
for label, origin, target in RAY_CHECKS:
    print("  " + visibility_check(scene, label, origin, target))
print("-" * 68)
print("NEXT: set_state('NORMAL') / set_state('BLACKOUT'), walk the 8 cameras,")
print("      export 2 sign-off tables, then ARCHIVE this .blend. No final shots.")
print("REMINDER: dimensions are placeholders; re-layout S00 with real set size.")
print("          NO readable text anywhere in the model (compliance 110).")
print("=" * 68)
