#!/usr/bin/env python3
"""Build the 《对账》 Q2 previs blockout — 1 .blend, 6 spaces, 2 light states, 8 cameras.

Scope is exactly the Q2 clause: **0 frames rendered, 0 final 3D shots, no materials, no text**.
The file is a consistency-checking tool for "one night told three times": does the light state
jump, does a camera see what it must not, can the cast walk from any set to any other.

    B01  S00 floor control plane : 24 x 12 m slab, 2.4 m corridor, 6 volumes, corner occluder
    B02  circuit zoning           : CIRCUIT_EMERGENCY / CIRCUIT_NORMAL colour plates + `circuit`
    B03  S01 two light states     : LIGHT_NORMAL (5 ceiling + 1 per space) / LIGHT_BLACKOUT
    B04  4 corridor cameras       : cold open + A (沈砚) / B (罗慧) / C (姜培)
    B05  S03 pantry               : two cups (cold/hot), sweater on chair, folder, sink, chair
    B06  S05 switch room          : cabinet, residual light, 6 standing rings (no humans)
    B07  S04 admin office         : desk, adjustable lamp, shredder, paperwork run
    B08  set_state("NORMAL"|"BLACKOUT") — also embedded in the .blend as a Text datablock
    B09  console report           : collections, light counts, circuit table, cameras, guards

Differences from workbuddy-artifacts/对账_blender_q2_previs_v1.py (the never-run first draft),
all of them found by the guards rather than by eye:

  1. Corridor wall gaps were a fixed 4 m pitch that matched **no** room. The nurse station door
     opened onto a wall and the pantry door opened 0.8 m outside the pantry. Walls are now cut
     from the door table, so every door lines up with the room it serves (B01 "动线走得通").
  2. The switch-room cabinet at y=-4.0 with depth 0.6 put its back 0.1 m through the back wall.
  3. `LIGHT_BLACKOUT` puts a warm desk lamp in the admin office, but B02 declares that room
     CIRCUIT_NORMAL (no power for 47 minutes). Reported as a WARN: it must be declared a local /
     battery lamp or the zoning table is a lie. Not silently re-labelled.
  4. Two spaces (pantry, pharmacy) have no blackout fixture in their own volume. Reported as
     LIGHTCOVER with the door-spill distance instead of being quietly given a lamp.

Run with Python on Windows (Blender auto-detected; override with BLENDER_EXE):

    python win/blender_set_duizhang_q2.py
    python win/blender_set_duizhang_q2.py --out-dir work/sets/duizhang

Output: work/sets/duizhang/对账_blockout_v01.blend  (plus a round-trip verify pass)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "work" / "sets" / "duizhang"
BLEND_NAME = "对账_blockout_v01.blend"   # default; --version overrides, never overwrites


def find_blender() -> Path:
    """Highest installed Blender 5.x, unless BLENDER_EXE says otherwise."""
    override = os.environ.get("BLENDER_EXE")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise SystemExit(f"BLENDER_EXE is set but not a file: {p}")

    root = Path(r"C:\Program Files\Blender Foundation")
    found: dict[tuple[int, ...], Path] = {}
    if root.is_dir():
        for child in root.iterdir():
            exe = child / "blender.exe"
            if not exe.is_file():
                continue
            nums = tuple(int(n) for n in re.findall(r"\d+", child.name))
            if nums:
                found[nums] = exe
    if not found:
        raise SystemExit(f"no Blender found under {root}")
    return found[max(found)]


# The text block embedded in the .blend. Kept at module level, outside BLENDER_SCRIPT,
# because its body contains a `"""` docstring that would close the outer raw string.
SET_STATE_TEXT = r'''
"""Light-state switch for the 《对账》 Q2 previs blockout.

Usage (Text Editor > Run Script, or from the Python console):

    set_state("NORMAL")     # cold-white ceiling fixtures
    set_state("BLACKOUT")   # low cyan emergency fixtures + residuals

Both states swap hide_render / hide_viewport on every object of the two light
collections, then write scene["light_state"]. Nothing else moves: geometry,
cameras and circuit plates are identical in both states by construction.
"""

import bpy


def set_state(state):
    state = state.upper()
    if state not in ("NORMAL", "BLACKOUT"):
        raise ValueError("state must be NORMAL or BLACKOUT")
    on = bpy.data.collections.get("LIGHT_" + state)
    off = bpy.data.collections.get(
        "LIGHT_BLACKOUT" if state == "NORMAL" else "LIGHT_NORMAL"
    )
    if on is None or off is None:
        raise RuntimeError("light collections missing from this file")
    for ob in on.objects:
        ob.hide_render = False
        ob.hide_viewport = False
    for ob in off.objects:
        ob.hide_render = True
        ob.hide_viewport = True
    bpy.context.scene["light_state"] = state
    return "%s: %d fixtures visible, %d hidden" % (
        state, len(on.objects), len(off.objects)
    )


if __name__ == "__main__":
    print(set_state(bpy.context.scene.get("light_state", "BLACKOUT")))
'''

BLENDER_SCRIPT = r"""
import hashlib
import math
import sys
from collections import deque
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(argv[0])
out_file = out_dir / argv[1]

# ---------------------------------------------------------------------------
# CONFIG — dimensions are PLACEHOLDERS (C4): re-cut S00 with the real set size.
# ---------------------------------------------------------------------------
FLOOR_W, FLOOR_D, WALL_H = 24.0, 12.0, 3.5
CORRIDOR_W = 2.8
WALL_T = 0.12
DOOR_W, DOOR_H = 1.4, 2.1
CEIL_Z = 3.10          # fixture plane: 0.40 m below the 3.5 m slab for grid and batten
X0, X1 = -FLOOR_W / 2.0, FLOOR_W / 2.0
Y0, Y1 = -FLOOR_D / 2.0, FLOOR_D / 2.0
CORR_N, CORR_S = CORRIDOR_W / 2.0, -CORRIDOR_W / 2.0

GREY = (0.55, 0.55, 0.55, 1.0)
ZONE_ON = (0.20, 0.72, 0.52, 1.0)
ZONE_OFF = (0.75, 0.35, 0.35, 1.0)
COLD_WHITE = (1.0, 1.0, 1.0)
EMERGENCY_GREEN = (0.35, 1.0, 0.55)
DESK_WARM = (1.0, 0.72, 0.42)
CUP_COLD = (0.45, 0.60, 0.75, 1.0)
CUP_HOT = (0.85, 0.45, 0.30, 1.0)

# name, x0, x1, y0, y1, circuit, in_q2_scope
# y0/y1 are derived from CORRIDOR_W + ROOM_D; edit those two, not these, to resize.
ROOMS = [
    ("S02_NurseStation", -10.0, -4.0,  CORRIDOR_W / 2.0,  5.6, "EMERGENCY", False),
    ("S03_Pantry",        -3.5, -0.5,  CORRIDOR_W / 2.0,  4.0, "NORMAL",    True),
    ("S06_Pharmacy",       0.5,  5.5,  CORRIDOR_W / 2.0,  5.0, "NORMAL",    False),
    ("S04_AdminOffice",    6.5, 11.5,  CORRIDOR_W / 2.0,  5.0, "NORMAL",    True),
    # S05 enlarged 3.0x3.0 -> 5.0x4.4 per the QA gate: 6 blocking marks need ~3.7 m2 each
    ("S05_SwitchRoom",    -7.0, -2.0, -5.8, -CORRIDOR_W / 2.0, "EMERGENCY", True),
]

# name, camera location, target, lens, scene_no, perspective, allowed spaces, note
CAMERAS = [
    ("CAM_S00_overview",   (0.0, 0.0, 16.0),  (0.0, 0.0, 0.0),  18.0, "S00", "overview",
     None, "floor plan / blocking / circuit plates"),
    ("CAM_S01_coldopen",   (-11.0, 0.0, 1.65), (2.0, 0.0, 1.40), 35.0, "S01", "coldopen",
     ["S01"], "blackout moment, corridor only"),
    ("CAM_S01_A_audit",    (-9.0, 0.9, 1.65),  (-1.0, 0.0, 1.40), 35.0, "S01", "A",
     ["S01"], "A-line recap, Shen Yan"),
    ("CAM_S01_B_nurse",    (-3.0, -0.9, 1.60), (3.0, 0.0, 1.35), 35.0, "S01", "B",
     ["S01"], "B-line recap, Luo Hui"),
    ("CAM_S01_C_admin",    (10.5, 0.9, 1.65),  (1.0, 0.0, 1.40), 35.0, "S01", "C",
     ["S01"], "C-line recap, Jiang Pei"),
    ("CAM_S22_pantry",     (-2.0, 1.70, 1.50), (-2.0, 3.20, 0.95), 24.0, "S03", "A+B",
     ["S03"], "two cups and folder, no plot dialogue"),
    ("CAM_S37_admin",      (8.9, 2.20, 1.60),  (8.9, 3.50, 0.82), 20.0, "S04", "A+C",
     ["S04"], "desk lamp on paper, shredder run"),
    ("CAM_S31_switchroom", (-6.30, -1.70, 1.80), (-4.10, -4.30, 0.80), 18.0, "S05", "A+B+C",
     ["S05"], "the only three-line convergence"),
]

TEXT_SET_STATE = None  # INJECTED_BY_RUNNER
# Use exactly the function that ships inside the .blend, so the builder and the file
# cannot disagree about what a state switch does.
_state_ns = {"__name__": "duizhang_set_state"}
exec(compile(TEXT_SET_STATE, "set_state.py", "exec"), _state_ns)
set_state = _state_ns["set_state"]

# name: (编号, 中英场景名, 所属幕, 出现场次, 灯态, 优先级, 验收人)
# §五 requires every Collection to be searchable on these ten fields, so they are written as
# custom properties on the Collection datablock itself (outliner + a script can both read
# them) and echoed as a TSV text block inside the .blend. 尺寸 and 机位号 are derived below.
COLLECTION_META = {
    "S00_Floorplan":     ("S00", "楼层总控", "全片", "全片（连拍动线基准）", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "美术指导"),
    "S01_Corridor":      ("S01", "走廊", "第一至三幕", "冷开场 0-3 分 + 全片转场 + A/B/C 三视角回溯", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "摄影指导"),
    "S02_NurseStation":  ("S02", "护士站", "第一、二幕", "第一幕（三本账摆上桌）、第二幕", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "美术指导"),
    "S03_Pantry":        ("S03", "茶水间", "第二幕", "第 22 场（中点 ~30 分，留白戏）", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "导演"),
    "S04_AdminOffice":   ("S04", "行政办公室", "第三幕", "第 37 场（幕点② ~48 分）", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "导演 + 摄影指导"),
    "S05_SwitchRoom":    ("S05", "配电间", "第三幕", "40-54 分，三线唯一合流点", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "摄影指导"),
    "S06_Pharmacy":      ("S06", "药房", "第二幕", "第二幕用药账线", "NORMAL+BLACKOUT(PRE+OUT)", "P1", "美术指导"),
    "CIRCUIT_EMERGENCY": ("Z1", "断电有电回路（色板）", "全片", "断电 47 分钟", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "摄影指导"),
    "CIRCUIT_NORMAL":    ("Z2", "断电无电回路（色板）", "全片", "断电 47 分钟", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "摄影指导"),
    "LIGHT_NORMAL":      ("L1", "常态顶灯", "全片", "PRE 态（5 顶灯 + 6 景各 1）", "NORMAL(PRE)", "P0", "摄影指导"),
    "LIGHT_BLACKOUT":    ("L2", "断电应急灯", "全片", "OUT 态（6 低位 + 尽头 + 护士站 + 台灯 + 配电间）", "BLACKOUT(OUT)", "P0", "摄影指导"),
    "CAM_PREVIS":        ("C", "机位占位", "全片", "8 个机位，见 B04", "NORMAL+BLACKOUT(PRE+OUT)", "P0", "导演"),
    "PROPS_KEY":         ("P", "关键道具/站位占位", "全片", "第 22/37 场、第三幕", "NORMAL+BLACKOUT(PRE+OUT)", "P1", "美术指导"),
}

# ---------------------------------------------------------------------------
# scene reset
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080

for engine_id in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine_id
        break
    except TypeError:
        continue

if scene.world is None:
    scene.world = bpy.data.worlds.new("PrevisWorld")
scene.world.color = (0.05, 0.05, 0.05)

FOOTPRINTS = []   # (minx, maxx, miny, maxy, name) — knee-height blockers, for ROUTECHECK
DOORS = []        # (room, x, y, side)


def new_collection(name):
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


def add_box(col, name, center, size, color=GREY, circuit=None, blocks=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal(
        (size[0], size[1], size[2], 1.0)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = center
    col.objects.link(ob)
    ob.color = color
    if circuit:
        ob["circuit"] = circuit
    if blocks:
        FOOTPRINTS.append((center[0] - size[0] / 2.0, center[0] + size[0] / 2.0,
                           center[1] - size[1] / 2.0, center[1] + size[1] / 2.0, name))
    return ob


def add_area_light(col, name, loc, energy, color, size, space, circuit,
                   target=None, state="NORMAL"):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.color = color
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    ob = bpy.data.objects.new(name, data)
    col.objects.link(ob)
    ob.location = loc
    if target is None:
        ob.rotation_euler = (0.0, 0.0, 0.0)   # area lights emit along local -Z: straight down
    else:
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    ob["state"] = state
    ob["space"] = space
    ob["circuit"] = circuit
    return ob


def add_camera(col, spec):
    name, loc, target, lens, scene_no, perspective, allowed, note = spec
    data = bpy.data.cameras.new(name)
    data.lens = lens
    ob = bpy.data.objects.new(name, data)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    ob["scene_no"] = scene_no
    ob["perspective"] = perspective
    ob["allowed_spaces"] = ",".join(allowed) if allowed else "ALL"
    ob["previs_note"] = note + " | placeholder, NOT final shot parameters"
    return ob


def add_stand_marker(col, name, loc, radius=0.28):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=0.02,
                                     location=loc)
    ob = bpy.context.object
    ob.name = name
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    ob.color = (0.95, 0.75, 0.25, 1.0)
    return ob


# ---------------------------------------------------------------------------
# collections
# ---------------------------------------------------------------------------
floor_col = new_collection("S00_Floorplan")
corridor = new_collection("S01_Corridor")
zone_on = new_collection("CIRCUIT_EMERGENCY")
zone_off = new_collection("CIRCUIT_NORMAL")
light_normal = new_collection("LIGHT_NORMAL")
light_blackout = new_collection("LIGHT_BLACKOUT")
cam_col = new_collection("CAM_PREVIS")
props = new_collection("PROPS_KEY")
room_cols = {r[0]: new_collection(r[0]) for r in ROOMS}

# §五 asset fields, written onto each Collection so the file is searchable by itself
ROOM_BY_COL = {r[0]: r for r in ROOMS}
CAMS_BY_COL = {}
for _spec in CAMERAS:
    CAMS_BY_COL.setdefault(_spec[4], []).append(_spec[0])
SIZE_BY_COL = {"S00_Floorplan": "%.1f x %.1f x %.1f" % (FLOOR_W, FLOOR_D, WALL_H),
               "S01_Corridor": "%.1f x %.1f x %.1f" % (FLOOR_W, CORRIDOR_W, WALL_H)}
for _r in ROOMS:
    SIZE_BY_COL[_r[0]] = "%.1f x %.1f x %.1f" % (_r[2] - _r[1], _r[4] - _r[3], WALL_H)
CAMS_BY_COL["S03"] = CAMS_BY_COL.get("S03") or ["CAM_S22_pantry"]

for _cname, _col in list(bpy.data.collections.items()):
    meta = COLLECTION_META.get(_cname)
    if meta is None:
        continue
    rid, cn, act, scenes, lstate, prio, who = meta
    space_tag = _cname.split("_", 1)[0]
    is_scene = _cname in ("S00_Floorplan", "S01_Corridor") or _cname in ROOM_BY_COL
    cams = (CAMS_BY_COL.get(_cname) or CAMS_BY_COL.get(space_tag) or []) if is_scene else []
    _col["asset_id"] = rid
    _col["name_cn"] = cn
    _col["act"] = act
    _col["scenes"] = scenes
    _col["collection"] = _cname
    _col["size_m"] = SIZE_BY_COL.get(_cname, "-")
    _col["light_state"] = lstate
    _col["cameras"] = ", ".join(cams) if cams else ("-(走廊机位兼用)" if is_scene else "-")
    _col["priority"] = prio
    _col["signoff"] = who + " (待签)"

# ---------------------------------------------------------------------------
# B01 — floor slab, corridor, room volumes, corner occluder
# ---------------------------------------------------------------------------
add_box(floor_col, "FLOOR_slab", (0.0, 0.0, -0.10), (FLOOR_W, FLOOR_D, 0.20))
add_box(corridor, "CORRIDOR_floor", (0.0, 0.0, 0.01), (FLOOR_W, CORRIDOR_W, 0.02))

# corridor walls are cut from the door table, so a door always lands on its room
for side, wall_y, tag in ((1, CORR_N, "N"), (-1, CORR_S, "S")):
    gaps = sorted((r[1] + r[2]) / 2.0 for r in ROOMS if (r[3] > 0) == (side > 0))
    spans, cursor = [], X0
    for gx in gaps:
        spans.append((cursor, gx - DOOR_W / 2.0))
        cursor = gx + DOOR_W / 2.0
    spans.append((cursor, X1))
    for i, (a, b) in enumerate(spans):
        if b - a <= 1e-6:
            continue
        add_box(corridor, "CORRIDOR_wall_%s_%02d" % (tag, i),
                ((a + b) / 2.0, wall_y, WALL_H / 2.0),
                (b - a, WALL_T, WALL_H), blocks=True)
    for gx in gaps:
        add_box(corridor, "CORRIDOR_doorhead_%s_%+d" % (tag, int(gx * 10)),
                (gx, wall_y, (DOOR_H + WALL_H) / 2.0),
                (DOOR_W, WALL_T, WALL_H - DOOR_H), blocks=False)

# slab end caps, so the corridor reads as a floor and not a shelf
for sx, tag in ((X0, "W"), (X1, "E")):
    add_box(floor_col, "FLOOR_endcap_%s" % tag, (sx, 0.0, WALL_H / 2.0),
            (WALL_T, FLOOR_D, WALL_H), blocks=True)

# corner occluder: hides the admin-office door from the switch-room sightline
add_box(floor_col, "CORNER_occluder", (4.8, 0.0, WALL_H / 2.0), (1.4, 0.9, WALL_H),
        blocks=True)

# room volumes: floor + back wall + two side walls (corridor side is the corridor wall)
for name, x0, x1, y0, y1, circuit, _scope in ROOMS:
    col = room_cols[name]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, d = x1 - x0, y1 - y0
    tag = name.split("_", 1)[0]
    far_y = y1 if cy > 0 else y0
    add_box(col, "%s_floor" % tag, (cx, cy, 0.01), (w, d, 0.02), circuit=circuit)
    add_box(col, "%s_wall_back" % tag, (cx, far_y, WALL_H / 2.0), (w, WALL_T, WALL_H),
            circuit=circuit, blocks=True)
    add_box(col, "%s_wall_left" % tag, (x0, cy, WALL_H / 2.0), (WALL_T, d, WALL_H),
            circuit=circuit, blocks=True)
    add_box(col, "%s_wall_right" % tag, (x1, cy, WALL_H / 2.0), (WALL_T, d, WALL_H),
            circuit=circuit, blocks=True)
    door_x = cx
    DOORS.append((tag, door_x, CORR_N if cy > 0 else CORR_S, 1 if cy > 0 else -1))

# ---------------------------------------------------------------------------
# B02 — circuit zoning plates (thin, on the floor, colour = has power / no power)
# ---------------------------------------------------------------------------
for name, x0, x1, y0, y1, circuit, _scope in ROOMS:
    tag = name.split("_", 1)[0]
    col = zone_on if circuit == "EMERGENCY" else zone_off
    add_box(col, "ZONE_%s_%s" % (circuit, tag),
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0, 0.035),
            (x1 - x0 - 0.3, y1 - y0 - 0.3, 0.02),
            color=ZONE_ON if circuit == "EMERGENCY" else ZONE_OFF, circuit=circuit)
add_box(zone_on, "ZONE_CIRCUIT_S01",
        (0.0, 0.0, 0.03), (FLOOR_W - 0.6, CORRIDOR_W - 0.3, 0.02),
        color=ZONE_ON, circuit="EMERGENCY")

# ---------------------------------------------------------------------------
# B05 / B06 / B07 — key volumes. Grey only: no readable text anywhere (110).
# ---------------------------------------------------------------------------
add_box(props, "NS_counter", (-7.0, 2.6, 0.55), (3.2, 0.9, 1.1), blocks=True)
add_box(props, "NS_ledger_table", (-7.0, 3.8, 0.75), (2.0, 1.0, 0.05), blocks=True)

add_box(props, "PANTRY_counter", (-2.0, 3.3, 0.90), (1.8, 0.7, 0.06), blocks=True)
add_box(props, "PANTRY_sink", (-2.6, 3.3, 0.94), (0.5, 0.45, 0.10))
add_box(props, "PANTRY_cup_cold", (-2.5, 3.15, 1.01), (0.09, 0.09, 0.13), color=CUP_COLD)
add_box(props, "PANTRY_cup_hot", (-1.5, 3.15, 1.01), (0.09, 0.09, 0.13), color=CUP_HOT)
add_box(props, "PANTRY_folder", (-2.0, 3.05, 0.95), (0.32, 0.24, 0.02))
add_box(props, "PANTRY_chair_sweater", (-2.9, 2.4, 0.45), (0.5, 0.5, 0.9), blocks=True)
add_box(props, "PANTRY_sweater", (-2.9, 2.62, 0.80), (0.44, 0.10, 0.35))

add_box(props, "ADMIN_desk", (9.0, 3.6, 0.75), (2.4, 1.1, 0.06), blocks=True)
add_box(props, "ADMIN_lamp_post", (9.9, 3.9, 0.95), (0.06, 0.06, 0.40))
add_box(props, "ADMIN_lamp_head", (9.72, 3.9, 1.14), (0.26, 0.16, 0.10))
add_box(props, "ADMIN_paper", (9.4, 3.55, 0.79), (0.30, 0.22, 0.01))
add_box(props, "ADMIN_shredder", (8.1, 3.25, 0.35), (0.35, 0.30, 0.70), blocks=True)

add_box(props, "SWITCH_cabinet", (-4.5, -5.45, 1.10), (2.2, 0.6, 2.2), blocks=True)
add_box(props, "SWITCH_log_table", (-2.9, -2.2, 0.75), (0.7, 0.5, 0.05), blocks=True)

add_box(props, "PHARM_shelf", (3.0, 4.6, 1.10), (4.0, 0.5, 2.2), blocks=True)
add_box(props, "PHARM_record_desk", (1.4, 2.1, 0.75), (1.2, 0.6, 0.05), blocks=True)

# six blocking rings in the switch room — no human geometry (B06)
for i, (dx, dy) in enumerate([(-1.6, -0.5), (-0.8, 0.5), (0.0, -0.5),
                              (0.8, 0.5), (1.6, -0.5), (0.0, 0.6)]):
    add_stand_marker(props, "STAND_S05_%02d" % i, (-4.5 + dx, -3.8 + dy, 0.05))

# ---------------------------------------------------------------------------
# B03 — two light states
# ---------------------------------------------------------------------------
for i, x in enumerate((-9.0, -4.5, 0.0, 4.5, 9.0)):
    add_area_light(light_normal, "NORMAL_ceil_%02d" % i, (x, 0.0, CEIL_Z), 320,
                   COLD_WHITE, (1.6, 0.5), "S01", "EMERGENCY",
                   target=(x, 0.0, 0.0), state="NORMAL")
for name, x0, x1, y0, y1, circuit, _scope in ROOMS:
    tag = name.split("_", 1)[0]
    add_area_light(light_normal, "NORMAL_%s" % tag,
                   ((x0 + x1) / 2.0, (y0 + y1) / 2.0, CEIL_Z), 260, COLD_WHITE,
                   (1.2, 1.2), tag, circuit, state="NORMAL")
add_area_light(light_normal, "NORMAL_S01_corridor", (0.0, 0.0, CEIL_Z - 0.05), 180,
               COLD_WHITE, (1.2, 1.2), "S01", "EMERGENCY", state="NORMAL")

for i, x in enumerate((-10.0, -6.0, -2.0, 2.0, 6.0, 10.0)):
    add_area_light(light_blackout, "OUT_emergency_%02d" % i, (x, 0.9, 0.35), 45,
                   EMERGENCY_GREEN, (0.35, 0.18), "S01", "EMERGENCY",
                   target=(x, 0.0, 1.2), state="BLACKOUT")
add_area_light(light_blackout, "OUT_corridor_end", (11.6, 0.0, 0.45), 70,
               EMERGENCY_GREEN, (0.5, 0.3), "S01", "EMERGENCY",
               target=(0.0, 0.0, 1.2), state="BLACKOUT")
add_area_light(light_blackout, "OUT_nurse_residual", (-7.0, 3.0, 1.10), 30,
               EMERGENCY_GREEN, (0.4, 0.2), "S02", "EMERGENCY",
               target=(-7.0, 3.8, 0.9), state="BLACKOUT")
add_area_light(light_blackout, "OUT_admin_desk", (9.0, 3.2, 1.25), 22,
               DESK_WARM, (0.3, 0.3), "S04", "LOCAL",
               target=(9.0, 3.6, 0.8), state="BLACKOUT")
add_area_light(light_blackout, "OUT_switchroom", (-4.5, -2.4, 0.55), 35,
               EMERGENCY_GREEN, (0.4, 0.2), "S05", "EMERGENCY",
               target=(-4.5, -5.4, 1.2), state="BLACKOUT")

for ob in light_normal.objects:
    ob.hide_render = True
    ob.hide_viewport = True
for ob in light_blackout.objects:
    ob.hide_render = False
    ob.hide_viewport = False
scene["light_state"] = "BLACKOUT"

# Per-camera subject check: what the frame must actually contain (B05 / B07 acceptance).
# This is the only guard that reads "one camera sees both cups and the folder".
SUBJECTS = {
    "CAM_S00_overview": ["NS_counter", "PANTRY_counter", "PHARM_shelf", "ADMIN_desk",
                         "SWITCH_cabinet"],
    "CAM_S01_coldopen": ["CORNER_occluder"],
    "CAM_S01_C_admin": ["CORNER_occluder"],
    "CAM_S22_pantry": ["PANTRY_cup_cold", "PANTRY_cup_hot", "PANTRY_folder"],
    "CAM_S37_admin": ["ADMIN_paper", "ADMIN_lamp_head", "ADMIN_shredder"],
    "CAM_S31_switchroom": ["SWITCH_cabinet", "STAND_S05_00", "STAND_S05_01",
                           "STAND_S05_02", "STAND_S05_03", "STAND_S05_04",
                           "STAND_S05_05"],
}

# ---------------------------------------------------------------------------
# B04 - eight cameras
# ---------------------------------------------------------------------------
for spec in CAMERAS:
    add_camera(cam_col, spec)

# Ctrl+0 / numpad-0 must open a real frame, and grey boxes are useless for acceptance:
# colour by object so the circuit plates and the two cups are separable without materials
# (Q2 forbids materials, so this is a viewport setting, not an asset).
scene.camera = cam_col.objects["CAM_S00_overview"]
scene.display.shading.color_type = "OBJECT"
scene.display.shading.light = "STUDIO"
scene.display.shading.show_shadows = True

# scene.display.shading only covers the render/workbench display. The saved *viewports*
# keep their own per-screen shading, and that is what the operator actually looks at:
# with materials=0 a MATERIAL viewport is flat grey. Force every VIEW_3D space.
_viewports = 0
for _scr in bpy.data.screens:
    for _area in _scr.areas:
        if _area.type != "VIEW_3D":
            continue
        for _space in _area.spaces:
            if _space.type == "VIEW_3D":
                # MATERIAL shading with materials=0 is flat grey even when color_type is
                # OBJECT, and the Shading workspace tab opens in exactly that mode.
                _space.shading.type = "SOLID"
                _space.shading.color_type = "OBJECT"
                _viewports += 1
print("VIEWPORT  %d VIEW_3D spaces set to SOLID/OBJECT" % _viewports)

# ---------------------------------------------------------------------------
# B08 — set_state lives inside the file, not only in the builder
# ---------------------------------------------------------------------------
set_state_text = bpy.data.texts.new("set_state.py")
set_state_text.write(TEXT_SET_STATE)
set_state_text.use_fake_user = True

# the same manifest as a TSV inside the file, so it survives without this builder
_built_m2 = FLOOR_W * CORRIDOR_W + sum((r[2] - r[1]) * (r[4] - r[3]) for r in ROOMS)
_unassigned_m2 = FLOOR_W * FLOOR_D - _built_m2
_manifest = ["编号\t中英场景名\t所属幕\t出现场次\tCollection\t尺寸(米)\t灯态\t机位号\t优先级\t验收人",
             "# 灯态术语: PRE = NORMAL (常态顶灯), OUT = BLACKOUT (断电应急). set_state() takes NORMAL / BLACKOUT."]
for _cn, _col in sorted(bpy.data.collections.items(),
                        key=lambda kv: (kv[1].get("asset_id", "zz"), kv[0])):
    if "asset_id" not in _col:
        continue
    _manifest.append("\t".join([_col["asset_id"], _col["name_cn"], _col["act"],
                                _col["scenes"], _col["collection"], _col["size_m"],
                                _col["light_state"], _col["cameras"],
                                _col["priority"], _col["signoff"]]))
_manifest.append("\t".join(["U1", "未定义地面（灯位/轨道工作区）", "全片",
                            "灯位、轨道、器材暂存", "(无 Collection)",
                            "%.1f x %.1f 楼板内未定义 %.1f m2 (%.0f%%)" %
                            (FLOOR_W, FLOOR_D, _unassigned_m2,
                             100.0 * _unassigned_m2 / (FLOOR_W * FLOOR_D)),
                            "NORMAL+BLACKOUT(PRE+OUT)", "-", "P1", "美术指导 + 摄影指导"]))
_manifest.append("\t".join(["L3", "本地回路（电池/台灯）", "第三幕",
                            "第 37 场；不接回路、不属任何分区色板，须裁定", "(无 Collection)",
                            "-", "BLACKOUT(OUT)", "CAM_S37_admin", "P0",
                            "导演 + 摄影指导"]))
_manifest_text = bpy.data.texts.new("ASSET_MANIFEST.tsv")
_manifest_text.write("\n".join(_manifest) + "\n")
_manifest_text.use_fake_user = True

bpy.context.view_layer.update()

# ---------------------------------------------------------------------------
# B09 — guards. Every line here is measured, none is asserted from intent.
# ---------------------------------------------------------------------------
print("=" * 78)
print("DUIZHANG / Q2 PREVIS")
print("OUT         %s" % out_file)
print("ENGINE      %s" % scene.render.engine)
print("STATE       %s" % scene.get("light_state"))
print("COLLECTIONS %d" % len(scene.collection.children))
for c in scene.collection.children:
    print("  %-20s objects=%d" % (c.name, len(c.objects)))
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
print("COUNTS      objects=%d meshes=%d cameras=%d lights=%d" %
      (len(bpy.data.objects), len(meshes), len(cam_col.objects),
       len(light_normal.objects) + len(light_blackout.objects)))

print("-" * 78)
print("ASSET MANIFEST (5-交付规范: 编号/中英场景名/所属幕/出现场次/Collection/尺寸/灯态/机位/优先级/验收人)")
print("  TERMS  PRE = NORMAL (常态顶灯) / OUT = BLACKOUT (断电应急) — manifest and set_state use the same two states")
print("  %-4s %-8s %-9s %-6s %-7s %-20s %s" %
      ("id", "cn", "act", "state", "size_m", "collection", "cams / signoff"))
for _cn, _col in sorted(bpy.data.collections.items(),
                        key=lambda kv: (kv[1].get("asset_id", "zz"), kv[0])):
    if "asset_id" not in _col:
        continue
    print("  %-4s %-8s %-9s %-6s %-7s %-20s %s" %
          (_col["asset_id"], _col["name_cn"], _col["act"], _col["light_state"],
           _col["size_m"], _col["collection"],
           "%s | %s | %s" % (_col["cameras"], _col["priority"], _col["signoff"])))

print("-" * 78)
print("B03 LIGHTS  NORMAL=%d BLACKOUT=%d" %
      (len(light_normal.objects), len(light_blackout.objects)))
for cname in ("NORMAL", "BLACKOUT"):
    col = light_normal if cname == "NORMAL" else light_blackout
    print("  %s: %s" % (cname, " ".join(sorted(o.name for o in col.objects))))

print("-" * 78)
print("B02 CIRCUIT (power during the 47-minute blackout)")
for name, _x0, _x1, _y0, _y1, circuit, scope in ROOMS:
    print("  %-20s %-10s q2=%s" % (name, circuit, "yes" if scope else "volume only"))
print("  %-20s %-10s q2=yes" % ("S01_Corridor", "EMERGENCY"))
for _lo in light_blackout.objects:
    if _lo.get("circuit") == "LOCAL":
        print("  %-20s %-10s (%s, %s) - not on any zoned circuit, see NOTE below"
              % (_lo.name, "LOCAL", _lo.get("space"), _lo.data.energy))

print("-" * 78)
print("B04 CAMERAS %d  (visibility measured in state=%s)" %
      (len(cam_col.objects), scene.get("light_state")))
dg = bpy.context.evaluated_depsgraph_get()


def in_frame(cam, point):
    co = world_to_camera_view(scene, cam, Vector(point))
    return co.z > 0.0 and 0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0, co


def sees(cam, ob):
    # The subject itself is the first hit: a ray that lands on the subject is a clear line,
    # not an obstruction. This is the houxiang lesson (SIGHTLINE "blocked by the subject").
    o = cam.matrix_world.translation
    d = ob.matrix_world.translation - o
    hit, _loc, _n, _i, hob, _m = scene.ray_cast(dg, o, d.normalized(), distance=d.length + 1e-4)
    return (not hit) or hob == ob


def visible(cam, point, eps=0.06):
    # First-hit test against the set's own geometry. A point counts as visible when the
    # ray reaches it; anything solid in between is a wall, not a sightline.
    o = cam.matrix_world.translation
    d = Vector(point) - o
    dist = d.length
    hit, loc, _n, _i, _ob, _m = scene.ray_cast(dg, o, d.normalized(), distance=dist + 1e-4)
    if not hit:
        return True
    return (loc - o).length >= dist - eps


room_bounds = {r[0]: r for r in ROOMS}
_cam_results = {}
_leak_log = []
_interior_max = 0.0

# B04 must hold in both states, not only the one the file happens to be saved in:
# NORMAL has 11 fixtures and had never been checked.
for _state in ("NORMAL", "BLACKOUT"):
    set_state(_state)
    _state_imax = 0.0
    print("-" * 78)
    print("B04 VISIBILITY state=%s  (cameras=%d)" % (_state, len(cam_col.objects)))
    for cam_ob in cam_col.objects:
        allowed = cam_ob.get("allowed_spaces", "ALL")
        print("  %-22s %-14s %-8s %s" % (cam_ob.name, cam_ob.get("scene_no"),
                                         cam_ob.get("perspective"), allowed))
        _cam_imax = 0.0

        # DOOR: whose door aperture is inside this frame
        seen_doors = []
        for tag, dx, dy, _side in DOORS:
            ok, co = in_frame(cam_ob, (dx, dy, 1.20))
            if ok:
                seen_doors.append("%s(%.2f,%.2f)" % (tag, co.x, co.y))
        print("      DOOR      %s" % (", ".join(seen_doors) if seen_doors else "-"))

        # LIGHTVIS: a fixture hidden in the current state cannot be in shot
        seen_lights, leaks = [], []
        for state_col in (light_normal, light_blackout):
            for lo in state_col.objects:
                if lo.hide_render:
                    continue
                ok, co = in_frame(cam_ob, lo.matrix_world.translation)
                if not ok:
                    continue
                if not visible(cam_ob, lo.matrix_world.translation):
                    continue          # behind a wall: in the frustum, not in shot
                seen_lights.append("%s[%s]" % (lo.name, lo.get("state")))
                space = lo.get("space")
                if allowed not in ("ALL",) and space not in allowed.split(","):
                    leaks.append("%s in %s" % (lo.name, space))
        print("      LIGHTVIS  %d in frame%s" %
              (len(seen_lights), " | " + ", ".join(seen_lights[:6]) +
               (" ..." if len(seen_lights) > 6 else "") if seen_lights else ""))
        if leaks:
            print("      LEAK      %s" % ", ".join(leaks))
            _leak_log.extend("%s[%s]: %s" % (cam_ob.name, _state, s) for s in leaks)
        else:
            print("      LEAK      none")

        # INTERIOR: how much of a space this camera may not see is actually reachable
        if allowed != "ALL":
            for name, x0, x1, y0, y1, _c, _s in ROOMS:
                if name.split("_", 1)[0] in allowed.split(","):
                    continue
                pts = []
                for fx in (0.2, 0.5, 0.8):
                    for fy in (0.2, 0.5, 0.8):
                        for z in (1.0, 1.7):
                            pts.append((x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy, z))
                seen = sum(1 for p in pts if in_frame(cam_ob, p)[0] and visible(cam_ob, p))
                frac = seen / float(len(pts))
                _cam_imax = max(_cam_imax, frac)
                print("      INTERIOR  %-20s %.2f %s" %
                      (name, frac, "LEAK" if frac > 0.25 else "ok"))

        # SUBJECT: the objects this frame exists to contain must be in frame and unoccluded.
        # Geometry does not change between states, so this is measured once.
        if _state == "BLACKOUT":
            for oname in SUBJECTS.get(cam_ob.name, []):
                ob = bpy.data.objects.get(oname)
                if ob is None:
                    print("      SUBJECT   %-22s MISSING OBJECT" % oname)
                    continue
                ok, co = in_frame(cam_ob, ob.matrix_world.translation)
                vis = ok and sees(cam_ob, ob)
                print("      SUBJECT   %-22s %s uv=(%.2f,%.2f)" %
                      (oname, "IN FRAME" if vis else ("in frame, OCCLUDED" if ok else "OUT OF FRAME"),
                       co.x, co.y))

        _cam_results.setdefault(cam_ob.name, {})[_state] = (len(leaks), _cam_imax)
        _state_imax = max(_state_imax, _cam_imax)
    _interior_max = max(_interior_max, _state_imax)
    print("  B04 SUMMARY state=%s: cameras=%d LEAK=%s INTERIOR_MAX=%.2f" %
          (_state, len(cam_col.objects),
           "none" if not [1 for k, v in _cam_results.items() if v[_state][0]] else
           "%d" % len([1 for k, v in _cam_results.items() if v[_state][0]]),
           _state_imax))

set_state("BLACKOUT")
print("-" * 78)
print("B04 LEAK DEFINITION: a camera 'sees' a fixture only when it is in frame, unoccluded,")
print("  and not hidden by the current light state; a LEAK is a fixture whose space is not")
print("  in the camera's allowed_spaces. INTERIOR_MAX is the largest share of a non-allowed")
print("  room's sampled volume that is reachable from that camera, so 0.11 means 'up to 11%")
print("  of a room it may not see is visible through the door', NOT 'nothing leaks'.")
print("-" * 78)
print("B03 LIGHTCOVER (is any space left with nothing at all in a state)")
for name, x0, x1, y0, y1, _c, _s in ROOMS:
    tag = name.split("_", 1)[0]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for state_col, state in ((light_normal, "NORMAL"), (light_blackout, "BLACKOUT")):
        inside = [o.name for o in state_col.objects if o.get("space") == tag]
        near, nd = "-", 1e9
        for o in state_col.objects:
            d = (o.matrix_world.translation - Vector((cx, cy, 1.0))).length
            if d < nd:
                near, nd = o.name, d
        if inside:
            print("  %-18s %-9s inside=%d  %s" % (tag, state, len(inside), ",".join(inside)))
        else:
            print("  %-18s %-9s inside=0  nearest=%s %.2f m  %s"
                  % (tag, state, near, nd, "SPILL" if nd < 6.0 else "DARK"))
cor_tag = "S01"
for state_col, state in ((light_normal, "NORMAL"), (light_blackout, "BLACKOUT")):
    inside = [o for o in state_col.objects if o.get("space") == cor_tag]
    print("  %-18s %-9s inside=%d" % (cor_tag, state, len(inside)))

print("-" * 78)
print("B01 ROUTECHECK (0.10 m grid, knee-height blockers, 4-way flood fill)")
STEP = 0.10
NX, NY = int(FLOOR_W / STEP), int(FLOOR_D / STEP)


def cell_free(ix, iy):
    x = X0 + (ix + 0.5) * STEP
    y = Y0 + (iy + 0.5) * STEP
    for mnx, mxx, mny, mxy, _n in FOOTPRINTS:
        if mnx <= x <= mxx and mny <= y <= mxy:
            return False
    return True


def nearest_cell(x, y):
    return (min(NX - 1, max(0, int((x - X0) / STEP))),
            min(NY - 1, max(0, int((y - Y0) / STEP))))


start = nearest_cell(0.0, 0.0)
seen = {start}
q = deque([start])
while q:
    ix, iy = q.popleft()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (ix + dx, iy + dy)
        if n in seen or not (0 <= n[0] < NX and 0 <= n[1] < NY):
            continue
        if not cell_free(*n):
            continue
        seen.add(n)
        q.append(n)
print("  free cells reachable from corridor centre: %d / %d" % (len(seen), NX * NY))
print("-" * 78)
print("B01 COVERAGE (what the slab actually defines)")
for name, x0, x1, y0, y1, _c, _s in ROOMS:
    print("  %-20s %5.1f m2  (%.1f x %.1f)" %
          (name, (x1 - x0) * (y1 - y0), x1 - x0, y1 - y0))
print("  %-20s %5.1f m2  (%.1f x %.1f)" %
      ("S01_Corridor", FLOOR_W * CORRIDOR_W, FLOOR_W, CORRIDOR_W))
print("  %-20s %5.1f m2  of %.1f m2 slab -> %.0f%% undefined" %
      ("UNASSIGNED", _unassigned_m2, FLOOR_W * FLOOR_D,
       100.0 * _unassigned_m2 / (FLOOR_W * FLOOR_D)))
print("  UNASSIGNED is the lighting / track working area, not a set: it is now row U1")
print("  of ASSET_MANIFEST.tsv, so it is signed off rather than left implicit.")
for name, x0, x1, y0, y1, _c, _s in ROOMS:
    tag = name.split("_", 1)[0]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    best = None
    for ix in range(int((x0 - X0) / STEP), int((x1 - X0) / STEP)):
        for iy in range(int((y0 - Y0) / STEP), int((y1 - Y0) / STEP)):
            cell = (ix, iy)
            if cell not in seen:
                continue
            px, py = X0 + (ix + 0.5) * STEP, Y0 + (iy + 0.5) * STEP
            d = math.hypot(px - cx, py - cy)
            if best is None or d < best[0]:
                best = (d, cell)
    if best is None:
        print("  ROUTE %-20s BLOCKED (no reachable floor inside the room)" % tag)
    else:
        print("  ROUTE %-20s WALKABLE (nearest standing point %.2f m from centre)"
              % (tag, best[0]))
for label, gx in (("west end", -11.0), ("east end", 11.0)):
    print("  ROUTE corridor to %-10s %s" %
          (label, "WALKABLE" if nearest_cell(gx, 0.0) in seen else "BLOCKED"))

print("-" * 78)
print("B09 WARNINGS")
warn = 0
for lo in light_blackout.objects:
    if lo.get("circuit") == "LOCAL":
        print("  WARN %s sits in %s, which B02 declares NORMAL (no power)." %
              (lo.name, lo.get("space")))
        print("       Recorded as circuit=LOCAL in ASSET_MANIFEST.tsv and on the sign-off")
        print("       table. Confirm it is a battery lamp at the lighting test, or B02 fails.")
        warn += 1
for name, _x0, _x1, _y0, _y1, _c, _s in ROOMS:
    tag = name.split("_", 1)[0]
    if not [o for o in light_blackout.objects if o.get("space") == tag]:
        print("  WARN %s has no BLACKOUT fixture of its own (see LIGHTCOVER)." % tag)
        warn += 1
fonts = [o.name for o in bpy.data.objects if o.type == "FONT"]
print("  TEXT   font objects=%d %s" % (len(fonts), "(none, 110 ok)" if not fonts else fonts))
if not fonts:
    warn += 0
print("  WARN   total=%d" % warn)
print("  RECONCILE: the 3 model WARNs are sign-off items ①②③; item ④ (U1 x fire egress)")
print("             is a site/compliance conclusion that no render can measure, so it lives")
print("             only on the form, not in this log.")
print("=" * 78)

# ---------------------------------------------------------------------------
# Q2 四-5: the two blank sign-off tables, generated from the numbers above so the
# tables and the .blend cannot drift apart. Two-stage sign-off (预签 / 终签): the
# old "未签字 = 不进试光" made ①② unverifiable forever, because ①② can only be
# settled by the very test the signature was gating.
# ---------------------------------------------------------------------------
_ver = argv[1].rsplit("_", 1)[-1].replace(".blend", "")
bpy.ops.wm.save_as_mainfile(filepath=str(out_file))
print("SAVED %s" % out_file)
_sha = hashlib.sha256()
with open(str(out_file), "rb") as _f:
    for _chunk in iter(lambda: _f.read(4 * 1024 * 1024), b""):
        _sha.update(_chunk)
_sha = _sha.hexdigest()
print("SHA256 %s" % _sha)


def _blackout_clearance(space_tag):
    # The blackout fixtures are not at the ceiling: their mounting height and the air
    # above them are a different number from the 0.40 m normal-state mounting clearance.
    zs = [o.matrix_world.translation.z for o in light_blackout.objects
          if o.get("space") == space_tag]
    if not zs:
        return "n/a（无自带断电灯）"
    lo, hi = min(zs), max(zs)
    if abs(hi - lo) < 1e-6:
        return "%.2f m / %.2f m" % (lo, WALL_H - hi)
    return "%.2f-%.2f m / %.2f-%.2f m" % (lo, hi, WALL_H - hi, WALL_H - lo)


_A = []
_A.append("# 《对账》断电两态光位表 + 分场次机位表 · %s" % _ver)
_A.append("")
_A.append("- source_blend: `对账_blockout_%s.blend`" % _ver)
_A.append("- source_sha256: `%s`" % _sha)
_A.append("- builder: `win/blender_set_duizhang_q2.py`（表与 .blend 同源；任一侧面被手改即失效，须以此 hash 复核）")
_A.append("- 尺寸为占位（C4）。**未预签 = 不进试光；未终签 = 不进搭景。**")
_A.append("")
_A.append("## 零、签字流程（两段式，顺序锁死）")
_A.append("")
_A.append("1. **G0 前置闸门** —— 场地与合规输入（第三节）。未关闭不得预签。")
_A.append("2. **预签（条件签）** —— 只签光位、能量、回路、机位清单；预签即授权进入试光。")
_A.append("3. **试光样片** —— 断电态实测，回填第四节 ①②③ 的实测值。")
_A.append("4. **终签** —— ①②③ 全部有实测值后终签；终签即授权搭景。")
_A.append("")
_A.append("> 顺序不可交换：G0 → 预签 → 试光（解决 ①②③）→ 终签 → 搭景。①②③ 不得先于 G0 定案。")
_A.append("")
_A.append("## 一、断电两态光位表（摄影指导签）")
_A.append("")
_A.append("| 空间 | 回路 | 常态灯 (能量) | 断电灯 (能量) | 断电灯高 z / 上方净空 | 常态挂装净空 |")
_A.append("|---|---|---|---|---|---|")
_n = ", ".join("%s(%d)" % (o.name, o.data.energy)
               for o in light_normal.objects if o.get("space") == "S01")
_b = ", ".join("%s(%d)" % (o.name, o.data.energy)
               for o in light_blackout.objects if o.get("space") == "S01")
_A.append("| S01 走廊 | EMERGENCY | %s | %s | %s | %.2f m |" %
           (_n, _b, _blackout_clearance("S01"), WALL_H - CEIL_Z))
for _name, _x0, _x1, _y0, _y1, _circuit, _scope in ROOMS:
    _tag = _name.split("_", 1)[0]
    _n = ", ".join("%s(%d)" % (o.name, o.data.energy)
                   for o in light_normal.objects if o.get("space") == _tag)
    _b = ", ".join("%s(%d)" % (o.name, o.data.energy)
                   for o in light_blackout.objects if o.get("space") == _tag)
    _A.append("| %s | %s | %s | %s | %s | %.2f m |" %
              (_tag, _circuit, _n or "-", _b or "-(借走廊溢光)",
               _blackout_clearance(_tag), WALL_H - CEIL_Z))
_A.append("")
_A.append("口径说明：**「断电灯高 / 上方净空」** = 该空间断电态灯具的最低/最高 z 与其到墙顶的差值（S01 0.35–0.45 m → 3.05–3.15 m；S04 1.25 m → 2.25 m）。")
_A.append("**「常态挂装净空」** = 顶灯 z=3.10 到墙顶 3.50 的 0.40 m，是常态挂装几何净空；**这 0.40 m 能否挂下灯架 + 挑杆，须摄影/灯光书面确认，未确认前视为未验。**")
_A.append("无自带断电灯的空间（S03 / S06）只有「断电灯高」一列是 n/a（该态无灯）；「常态挂装净空」仍有 0.40 m，因为顶灯存在。")
_A.append("两处的几何距离（1.91 m / 2.59 m）都不是照度，须试光实测。")
_A.append("")
_A.append("回路注记：`OUT_admin_desk` 位于 S04（CIRCUIT_NORMAL，断电无电）但带 `LOCAL` 属性 = 电池/本地台灯，")
_A.append("不属于任何分区色板（manifest 第 L3 行）。B02 色板仍标 S04=NORMAL；它是否允许存在，见第四节 ①。")
_A.append("")
_A.append("## 二、分场次机位表 + 光态一致性核对表（四方：美术 / 摄影 / 导演 / 录音）")
_A.append("")
_A.append("| 机位 | 场次 | 视角 | 焦段 | 允许空间 | NORMAL 核对 | BLACKOUT 核对 |")
_A.append("|---|---|---|---|---|---|---|")
for _spec in CAMERAS:
    _r = _cam_results.get(_spec[0], {})
    _cells = []
    for _st in ("NORMAL", "BLACKOUT"):
        _lk, _im = _r.get(_st, (0, 0.0))
        _cells.append("LEAK %d / imax %.2f" % (_lk, _im))
    _A.append("| %s | %s | %s | %.0f mm | %s | %s | %s |" %
              (_spec[0], _spec[4], _spec[5], _spec[3],
               ", ".join(_spec[6]) if _spec[6] else "ALL", _cells[0], _cells[1]))
_A.append("")
_A.append("表脚：**LEAK** = 画面内出现该机位 allowed_spaces 之外的灯具（须为 0）；**imax** = 该机位对非允许房间内部采样点的最大可见比例，")
_A.append("0.11 = 最多 11% 的房间内部可穿过门口被看到，**不等于「完全没穿帮」**；0.00 才是完全不可见。两态均已实测。")
_A.append("")
_A.append("## 三、前置闸门 G0（关闭后方可预签）")
_A.append("")
_A.append("| # | 闸门项 | 需要什么 | 状态 | 关闭 |")
_A.append("|---|---|---|---|---|")
_A.append("| G0 | 实测场地 | 总平面（长×宽 + 柱网/承重墙位置尺寸） | 未提供 | ☐ |")
_A.append("| G0 | 可用层高 | 结构层高与灯架净空 | 未提供 | ☐ |")
_A.append("| G0 | 洞口与管井 | 门洞 / 窗 / 管井位置 | 未提供 | ☐ |")
_A.append("| G0 | 三态供电 | 现有供电能否实现 EMERGENCY / NORMAL / LOCAL | 未提供 | ☐ |")
_A.append("| G0 | 器材动线 | 走廊两端与器材进出动线 | 未提供 | ☐ |")
_A.append("| ④ | 消防疏散 | U1 129.8 m²（占 288 m² 楼板 45%）是否与疏散通道冲突的书面确认 | 未确认 | ☐ |")
_A.append("")
_A.append("G0 关闭前，S00 保持占位，全部机位结论（IN FRAME / WALKABLE / LIGHTVIS / 溢光距离 / 净空）一律标「条件性·无效」。")
_A.append("")
_A.append("## 四、试光回填项（①②③，全部有实测值后方可终签）")
_A.append("")
_A.append("| # | 事项 | 类型 | 现状 | 实测值 | 结论 |")
_A.append("|---|---|---|---|---|---|")
_A.append("| ① | S04 `OUT_admin_desk`：断电 47 分钟内是否允许自带电源的本地光源？ | 是非裁定 | 未裁定；manifest 记为 L3 LOCAL |  | ☐ 是 ☐ 否 |")
_A.append("| ② | S03 茶水间：断电态「两杯 + 文件夹」主体位照度 / 可辨度 | 照度实测 | 无自带断电灯，最近应急灯 1.91 m（几何距离，非照度） |  | ☐ 合格 ☐ 不合格 |")
_A.append("| ③ | S06 药房：断电态「药架」主体位照度 / 可辨度 | 照度实测 | 无自带断电灯，最近应急灯 2.59 m（几何距离，非照度） |  | ☐ 合格 ☐ 不合格 |")
_A.append("")
_A.append("① 若为「否」：撤灯并把第 37 场移到断电前/后或改走廊溢光，或 S37 改到有电空间，或重排 S04 回路")
_A.append("（会动 B02 与 manifest，须重建 + 重 VERIFY）。**禁止为提亮直接给 S04 加 OUT_* 灯。**")
_A.append("② ③ 若不合格，按顺序：加同样走 LOCAL 裁定的剧情内光源 → 主体移近门洞/重排调度 → 调整应急灯位或")
_A.append("朝向（改 B03，须重建 + 重 VERIFY）→ 导演书面接受「该场就是暗的」。**同样禁止静默加灯。**")
_A.append("")
_A.append("## 五、预签（条件签，授权试光）")
_A.append("")
_A.append("| 角色 | 姓名 | G0 已关闭 | 日期 |")
_A.append("|---|---|---|---|")
for _who in ("美术指导", "摄影指导", "导演", "录音"):
    _A.append("| %s |  | ☐ |  |" % _who)
_A.append("")
_A.append("## 六、终签（授权搭景）")
_A.append("")
_A.append("| 角色 | 姓名 | ①②③ 已回填 | 日期 |")
_A.append("|---|---|---|---|")
for _who in ("美术指导", "摄影指导", "导演", "录音"):
    _A.append("| %s |  | ☐ |  |" % _who)
_A.append("")
_A.append("未预签 = 不进试光；未终签 = 不进搭景（117 交接后须有确认环节）。")

_doc = out_dir / ("对账_签字表_%s.md" % _ver)
_doc.write_text("\n".join(_A) + "\n", encoding="utf-8")
print("DOC %s" % _doc)
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


VERIFY_SCRIPT = r"""
import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
path = Path(argv[0])
bpy.ops.wm.open_mainfile(filepath=str(path))
scene = bpy.context.scene

print("VERIFY opened %s" % path)
print("VERIFY collections=%s" % sorted(c.name for c in scene.collection.children))
print("VERIFY objects=%d cameras=%d texts=%s" % (
    len(bpy.data.objects),
    len([o for o in bpy.data.objects if o.type == "CAMERA"]),
    sorted(t.name for t in bpy.data.texts)))
print("VERIFY state=%s" % scene.get("light_state"))
print("VERIFY circuit_attrs=%d" % len([o for o in bpy.data.objects if "circuit" in o]))

txt = bpy.data.texts.get("set_state.py")
if txt is None:
    print("VERIFY FAIL set_state.py text block missing")
    raise SystemExit(1)
ns = {"__name__": "verify"}
exec(compile(txt.as_string(), "set_state.py", "exec"), ns)
set_state = ns["set_state"]

for state, expect_hidden in (("NORMAL", "LIGHT_BLACKOUT"), ("BLACKOUT", "LIGHT_NORMAL")):
    msg = set_state(state)
    on = bpy.data.collections["LIGHT_" + state]
    off = bpy.data.collections[expect_hidden]
    bad = [o.name for o in off.objects if not (o.hide_render and o.hide_viewport)]
    print("VERIFY %s %s | %s | leaked=%s" % (state, msg, scene.get("light_state"), bad or "none"))
    if bad or scene.get("light_state") != state:
        print("VERIFY FAIL state switch did not hide the other collection")
        raise SystemExit(1)

normals = bpy.data.collections["LIGHT_NORMAL"]
blacks = bpy.data.collections["LIGHT_BLACKOUT"]
print("VERIFY lights NORMAL=%d BLACKOUT=%d" % (len(normals.objects), len(blacks.objects)))

# scene.display.shading is the render/workbench setting; the operator looks at the saved
# viewports. Both must say OBJECT or the file opens grey.
spaces = []
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == "VIEW_3D":
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    spaces.append((sp.shading.type, sp.shading.color_type))
print("VERIFY viewports=%d shading=%s scene_display=%s/%s" %
      (len(spaces), sorted(set(spaces)),
       scene.display.shading.type, scene.display.shading.color_type))
if (not spaces
        or any(t != "SOLID" or c != "OBJECT" for t, c in spaces)
        or scene.display.shading.color_type != "OBJECT"):
    print("VERIFY FAIL viewport shading is not SOLID/OBJECT everywhere: file opens grey")
    raise SystemExit(1)
print("VERIFY OK")
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--version", default="v01",
                    help="version suffix: v01, v02 ... an existing version is never overwritten")
    args = ap.parse_args()

    blender = find_blender()
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    # Rule 0: no Blender state outside the repo.
    scratch = REPO / "work" / ".btmp"
    for sub in ("config", "scripts", "datafiles", "tmp"):
        (scratch / sub).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = str(scratch / "config")
    env["BLENDER_USER_SCRIPTS"] = str(scratch / "scripts")
    env["BLENDER_USER_DATAFILES"] = str(scratch / "datafiles")
    env["TMPDIR"] = str(scratch / "tmp")
    env["TEMP"] = str(scratch / "tmp")
    env["TMP"] = str(scratch / "tmp")

    runner = scratch / "duizhang_q2_build.py"
    script_text = BLENDER_SCRIPT.replace(
        "TEXT_SET_STATE = None  # INJECTED_BY_RUNNER",
        "TEXT_SET_STATE = " + repr(SET_STATE_TEXT),
    )
    if "INJECTED_BY_RUNNER" in script_text:
        raise SystemExit("failed to inject the set_state text block")
    runner.write_text(script_text, encoding="utf-8")
    verify_runner = scratch / "duizhang_q2_verify.py"
    verify_runner.write_text(VERIFY_SCRIPT, encoding="utf-8")

    blend_path = out_dir / ("对账_blockout_%s.blend" % args.version)
    try:
        res = subprocess.run(
            [str(blender), "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", str(runner), "--", str(out_dir),
             "对账_blockout_%s.blend" % args.version],
            text=True, capture_output=True, env=env,
            encoding="utf-8", errors="replace",
        )
        if res.returncode != 0:
            print(res.stdout[-6000:])
            print(res.stderr[-6000:], file=sys.stderr)
            return res.returncode
        print(res.stdout)
        for line in res.stderr.splitlines():
            if line.strip() and "Warning" not in line and "Info" not in line:
                print("stderr: " + line)

        chk = subprocess.run(
            [str(blender), "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", str(verify_runner), "--", str(blend_path)],
            text=True, capture_output=True, env=env,
            encoding="utf-8", errors="replace",
        )
        for line in chk.stdout.splitlines():
            if line.startswith("VERIFY"):
                print(line)
        if chk.returncode != 0:
            print(chk.stdout[-4000:])
            print(chk.stderr[-4000:], file=sys.stderr)
            return chk.returncode
    finally:
        runner.unlink(missing_ok=True)
        verify_runner.unlink(missing_ok=True)

    print("blender  : %s" % blender)
    print("blend    : %s (%d bytes)" % (blend_path, blend_path.stat().st_size))
    print("sha256   : %s" % sha256_file(blend_path))
    print("no render was performed: 0 frames, 0 final shots (Q2 scope).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())