#!/usr/bin/env python3
"""Build the 火锅店 (hotpot restaurant) white model for 《老汤》 and render guide passes.

The set is deliberately a *white model*: one grey clay material, real geometry, no
textures. What leaves this script is what the video models actually consume —

    <shot>_beauty.png   clay render, composition reference
    <shot>_depth.png    normalised + inverted Z pass  (near = white)
    <shot>_normal.png   view normals

Depth and normal are the control signals for Z-Image Fun ControlNet and for
Wan 2.2 VACE. Steam is a separate collection and is excluded from both passes,
so the generative model invents its own.

Run with Python on Windows:
    python win/blender_set_huoguo.py --shot-id all
    python win/blender_set_huoguo.py --shot-id s002 --width 768 --height 1344

Blender is auto-detected under Program Files; override with BLENDER_EXE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "work" / "sets" / "huoguo"


def find_blender() -> Path:
    """Highest installed Blender 5.x, unless BLENDER_EXE says otherwise."""
    override = os.environ.get("BLENDER_EXE")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise SystemExit(f"BLENDER_EXE is set but not a file: {p}")

    root = Path(r"C:\Program Files\Blender Foundation")
    candidates: list[tuple[int, ...]] = []
    found: dict[tuple[int, ...], Path] = {}
    if root.is_dir():
        for child in root.iterdir():
            exe = child / "blender.exe"
            if not exe.is_file():
                continue
            nums = tuple(int(n) for n in re.findall(r"\d+", child.name))
            if nums:
                candidates.append(nums)
                found[nums] = exe
    if not candidates:
        raise SystemExit(f"no Blender found under {root}")
    return found[max(candidates)]


BLENDER_SCRIPT = r"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(argv[0])
width = int(argv[1])
height = int(argv[2])
shots_arg = argv[3]
samples = int(argv[4])
ctrl_only = len(argv) > 5 and argv[5] == "ctrl"
ctrl_radius = max(2, round(width / 192))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene

try:
    scene.render.engine = "BLENDER_EEVEE"
except TypeError:
    for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items:
        if "EEVEE" in item.identifier:
            scene.render.engine = item.identifier
            break

scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.film_transparent = False
scene.render.use_compositing = False
scene.frame_start = 1
scene.frame_end = 1

for attr, value in (("taa_render_samples", samples), ("use_raytracing", True)):
    if hasattr(scene.eevee, attr):
        try:
            setattr(scene.eevee, attr, value)
        except (TypeError, AttributeError):
            pass

# ---------------------------------------------------------------- collections
def new_coll(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


C_SET = new_coll("SET")
C_FURN = new_coll("FURNITURE")
C_PROPS = new_coll("PROPS")
C_PROXY = new_coll("PROXY")
C_FX = new_coll("FX_Steam")


def park(obj, coll):
    for other in list(obj.users_collection):
        other.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


# ---------------------------------------------------------------- materials
def find_principled(mat):
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def clay(name, value, rough=0.82, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = find_principled(m)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (value, value, value, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.18
        if emit > 0.0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (value, value * 0.92, value * 0.8, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emit
    return m


M_WHITE = clay("Clay_White", 0.86, 0.85)        # walls, tablecloths, ceramics
M_MID = clay("Clay_Mid", 0.55, 0.8)             # furniture, metal
M_DARK = clay("Clay_Dark", 0.26, 0.65)          # floor slab, grout, fridge
M_POT = clay("Clay_Pot", 0.72, 0.42)            # copper pot
M_GLOW = clay("Clay_Glow", 0.95, 0.4, emit=6.0) # bulbs, window glow, signage
M_STEAM = clay("Clay_Steam", 0.97, 0.55)        # steam wisps (beauty only)
M_PROXY = clay("Clay_Proxy", 0.62, 0.9)         # mannequins

# ---------------------------------------------------------------- primitives
def smooth(obj, angle=math.radians(40)):
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=angle)
    except Exception:
        pass


def bevel(obj, w=0.008, seg=2):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = w
    m.segments = seg
    m.limit_method = "ANGLE"


def cube(name, size, loc, mat, coll, rot=(0.0, 0.0, 0.0), bev=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.data.materials.append(mat)
    if bev:
        bevel(o, bev)
    return park(o, coll)


def cyl(name, r, h, loc, mat, coll, verts=48, rot=(0.0, 0.0, 0.0), do_smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    if do_smooth:
        smooth(o, math.radians(30))
    return park(o, coll)


def cone(name, r1, r2, h, loc, mat, coll, verts=32, rot=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=h, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    smooth(o, math.radians(30))
    return park(o, coll)


def torus(name, major, minor, loc, mat, coll, rot=(0.0, 0.0, 0.0), seg_major=48, seg_minor=8):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major, minor_radius=minor, location=loc, rotation=rot,
        major_segments=seg_major, minor_segments=seg_minor,
    )
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    smooth(o)
    return park(o, coll)


def sphere(name, r, loc, mat, coll, seg=32, rings=16, scale=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=rings)
    o = bpy.context.active_object
    o.name = name
    if scale:
        o.scale = scale
    o.data.materials.append(mat)
    smooth(o)
    return park(o, coll)


def tiled_floor(name, x0, x1, y0, y1, tile=0.6, gap=0.008, z=0.0, mat=M_DARK, coll=C_SET):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    nx = max(1, int(round((x1 - x0) / tile)))
    ny = max(1, int(round((y1 - y0) / tile)))
    for i in range(nx):
        for j in range(ny):
            ax, bx = x0 + i * tile + gap / 2, x0 + (i + 1) * tile - gap / 2
            ay, by = y0 + j * tile + gap / 2, y0 + (j + 1) * tile - gap / 2
            bm.faces.new([
                bm.verts.new((ax, ay, z)),
                bm.verts.new((bx, ay, z)),
                bm.verts.new((bx, by, z)),
                bm.verts.new((ax, by, z)),
            ])
    bm.to_mesh(mesh)
    bm.free()
    o = bpy.data.objects.new(name, mesh)
    o.data.materials.append(mat)
    coll.objects.link(o)
    return o


# ---------------------------------------------------------------- room shell
# x: -4.5 .. 4.5   y: -3.5 .. 3.5   z: 0 .. 3.2   (front wall = street side, y = -3.5)
X0, X1, Y0, Y1, ZH = -4.5, 4.5, -3.5, 3.5, 3.2

cube("Slab", (9.0, 7.0, 0.08), (0, 0, -0.05), M_DARK, C_SET)
tiled_floor("Floor_Tiles", X0, X1, Y0, Y1)
cube("Ceiling", (9.0, 7.0, 0.10), (0, 0, ZH + 0.05), M_WHITE, C_SET)
for i, y in enumerate((-1.3, 1.5)):
    cube(f"Beam_{i}", (9.0, 0.18, 0.20), (0, y, ZH - 0.10), M_MID, C_SET)

# back wall (kitchen pass x -0.85..0.85, z 0.95..1.9)
cube("BackWall_L", (3.65, 0.15, ZH), (-2.675, Y1, ZH / 2), M_WHITE, C_SET)
cube("BackWall_R", (3.65, 0.15, ZH), (2.675, Y1, ZH / 2), M_WHITE, C_SET)
cube("BackWall_Under", (1.70, 0.15, 0.95), (0, Y1, 0.475), M_WHITE, C_SET)
cube("BackWall_Over", (1.70, 0.15, 1.30), (0, Y1, 2.55), M_WHITE, C_SET)
cube("PassFrame_L", (0.06, 0.22, 0.95), (-0.85, Y1, 1.425), M_MID, C_SET)
cube("PassFrame_R", (0.06, 0.22, 0.95), (0.85, Y1, 1.425), M_MID, C_SET)
cube("PassShelf", (1.70, 0.55, 0.05), (0, Y1 - 0.28, 0.95), M_MID, C_SET)
for i, dx in enumerate((-0.55, 0.0, 0.55)):
    cyl(f"PassPot_{i}", 0.15, 0.20, (dx, Y1 - 0.30, 1.075), M_WHITE, C_PROPS, verts=32)
cyl("PassStack", 0.12, 0.16, (0.55, Y1 - 0.30, 1.255), M_MID, C_PROPS, verts=32)

# right wall, solid
cube("RightWall", (0.15, 7.0, ZH), (X1, 0, ZH / 2), M_WHITE, C_SET)

# left wall with window y -2.2..0.4, z 1.0..2.4
cube("LeftWall_Front", (0.15, 1.30, ZH), (X0, -2.85, ZH / 2), M_WHITE, C_SET)
cube("LeftWall_Back", (0.15, 3.10, ZH), (X0, 1.95, ZH / 2), M_WHITE, C_SET)
cube("LeftWall_Under", (0.15, 2.60, 1.00), (X0, -0.90, 0.50), M_WHITE, C_SET)
cube("LeftWall_Over", (0.15, 2.60, 0.80), (X0, -0.90, 2.80), M_WHITE, C_SET)
# window frame + bars
cube("Win_Sill", (0.26, 2.72, 0.06), (X0 + 0.05, -0.90, 0.99), M_MID, C_SET)
cube("Win_Head", (0.26, 2.72, 0.06), (X0 + 0.05, -0.90, 2.41), M_MID, C_SET)
for i in range(5):
    y = -2.2 + i * 0.65
    cube(f"Win_Mullion_{i}", (0.07, 0.05, 1.40), (X0 + 0.05, min(y, 0.40), 1.70), M_MID, C_SET)
cube("Win_Transom", (0.07, 2.60, 0.05), (X0 + 0.05, -0.90, 1.72), M_MID, C_SET)
cube("Win_Night", (0.04, 2.60, 1.36), (X0 - 0.06, -0.90, 1.70), M_GLOW, C_FX)

# front wall with door x 0.25..1.55, z 0..2.1
cube("FrontWall_L", (4.75, 0.15, ZH), (-2.125, Y0, ZH / 2), M_WHITE, C_SET)
cube("FrontWall_R", (2.95, 0.15, ZH), (3.025, Y0, ZH / 2), M_WHITE, C_SET)
cube("FrontWall_Over", (1.30, 0.15, 1.10), (0.90, Y0, 2.65), M_WHITE, C_SET)
cube("DoorFrame_L", (0.07, 0.22, 2.10), (0.25, Y0, 1.05), M_MID, C_SET)
cube("DoorFrame_R", (0.07, 0.22, 2.10), (1.55, Y0, 1.05), M_MID, C_SET)
cube("DoorFrame_T", (1.37, 0.22, 0.07), (0.90, Y0, 2.10), M_MID, C_SET)
for i in range(13):
    x = 0.33 + i * 0.095
    cyl(f"Bead_{i}", 0.011, 1.95, (x, Y0 + 0.10, 1.08), M_WHITE, C_SET, verts=8)

# wall dressing: menu boards, AC unit, wainscot ledge, service bell
cube("Wainscot_Back", (7.00, 0.05, 0.05), (0, Y1 - 0.09, 1.05), M_MID, C_SET)
cube("Wainscot_Right", (0.05, 7.00, 0.05), (X1 - 0.09, 0, 1.05), M_MID, C_SET)
for i, (y, z, w, h) in enumerate(((2.35, 2.30, 0.52, 0.72), (1.65, 2.25, 0.52, 0.62), (2.95, 2.28, 0.40, 0.66))):
    cube(f"Menu_{i}", (0.04, w, h), (X1 - 0.10, y, z), M_DARK, C_PROPS, bev=0.01)
cube("AC_Unit", (0.35, 1.15, 0.30), (X1 - 0.22, -2.60, 2.62), M_WHITE, C_PROPS, bev=0.02)
cube("AC_Grill", (0.06, 0.95, 0.20), (X1 - 0.42, -2.60, 2.55), M_DARK, C_PROPS)

# ---------------------------------------------------------------- counter + fridge
cube("Counter", (0.75, 2.20, 1.05), (3.90, 0.50, 0.525), M_MID, C_FURN, bev=0.01)
cube("Counter_Top", (0.92, 2.32, 0.07), (3.90, 0.50, 1.085), M_WHITE, C_FURN, bev=0.012)
cube("Register", (0.34, 0.42, 0.26), (3.88, -0.10, 1.25), M_DARK, C_PROPS, bev=0.015)
cube("Register_Screen", (0.05, 0.26, 0.16), (3.68, -0.10, 1.33), M_GLOW, C_PROPS)
for i, z in enumerate((1.75, 2.25)):
    cube(f"BarShelf_{i}", (0.30, 2.10, 0.05), (4.30, 0.50, z), M_MID, C_FURN)
    for j, y in enumerate((0.0, 0.35, 0.70, 1.05)):
        cyl(f"Bottle_{i}_{j}", 0.045, 0.24, (4.30, y, z + 0.145), M_WHITE, C_PROPS, verts=16)

cube("Fridge", (0.68, 0.58, 1.85), (4.10, -1.85, 0.925), M_WHITE, C_FURN, bev=0.02)
cube("Fridge_Glass", (0.03, 0.50, 1.55), (3.76, -1.85, 0.98), M_DARK, C_PROPS)
for i, z in enumerate((0.55, 0.95, 1.35)):
    cube(f"Fridge_Shelf_{i}", (0.05, 0.46, 0.03), (3.78, -1.85, z), M_MID, C_PROPS)
    for j, y in enumerate((-2.05, -1.85, -1.65)):
        cyl(f"Can_{i}_{j}", 0.032, 0.11, (3.80, y, z + 0.07), M_WHITE, C_PROPS, verts=12)

# ---------------------------------------------------------------- tables + stools
def round_table(name, cx, cy, r, h=0.74):
    cyl(f"{name}_Top", r, 0.05, (cx, cy, h - 0.025), M_WHITE, C_FURN, verts=64)
    torus(f"{name}_Edge", r - 0.01, 0.012, (cx, cy, h - 0.005), M_WHITE, C_FURN)
    cyl(f"{name}_Column", 0.055, h - 0.08, (cx, cy, (h - 0.05) / 2), M_MID, C_FURN, verts=24)
    cyl(f"{name}_Foot", 0.27, 0.03, (cx, cy, 0.015), M_MID, C_FURN, verts=32)


def stool(name, cx, cy):
    cyl(f"{name}_Seat", 0.17, 0.045, (cx, cy, 0.45), M_WHITE, C_FURN, verts=32)
    torus(f"{name}_Ring", 0.125, 0.012, (cx, cy, 0.17), M_MID, C_FURN)
    for i in range(4):
        a = math.radians(45 + i * 90)
        cyl(f"{name}_Leg_{i}", 0.014, 0.44, (cx + 0.125 * math.cos(a), cy + 0.125 * math.sin(a), 0.22), M_MID, C_FURN, verts=12)


H = (0.30, 0.50)
G = (-2.30, -1.00)
round_table("Table_Hero", *H, 0.50)
round_table("Table_Window", *G, 0.46)
round_table("Table_BackA", 2.55, 2.35, 0.45)
round_table("Table_BackB", 2.40, -1.70, 0.45)

for name, (cx, cy), r, angles in (
    ("Stool_H", H, 0.72, (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)),
    ("Stool_G", G, 0.66, (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)),
    ("Stool_BA", (2.55, 2.35), 0.64, (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)),
    ("Stool_BB", (2.40, -1.70), 0.64, (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)),
):
    for i, a in enumerate(angles):
        stool(f"{name}{i}", cx + r * math.sin(a), cy + r * math.cos(a))

# ---------------------------------------------------------------- hotpot (hero prop)
TX, TY, TZ = H[0], H[1], 0.74
cyl("Hob", 0.145, 0.022, (TX, TY, TZ + 0.011), M_DARK, C_PROPS, verts=48)
torus("Hob_Ring", 0.145, 0.008, (TX, TY, TZ + 0.022), M_MID, C_PROPS)
cyl("Pot", 0.175, 0.130, (TX, TY, TZ + 0.088), M_POT, C_PROPS, verts=64)
torus("Pot_Rim", 0.176, 0.010, (TX, TY, TZ + 0.153), M_POT, C_PROPS, seg_minor=10)
cyl("Pot_Broth", 0.168, 0.006, (TX, TY, TZ + 0.118), M_DARK, C_PROPS, verts=64)
cube("Pot_Divider", (0.33, 0.008, 0.10), (TX, TY, TZ + 0.105), M_POT, C_PROPS, rot=(0, 0, math.radians(38)))
for sgn in (-1, 1):
    cube(f"Pot_Handle_{sgn}", (0.035, 0.026, 0.02), (TX + sgn * 0.195, TY, TZ + 0.115), M_POT, C_PROPS)
cube("Pot_Lid", (0.34, 0.34, 0.01), (TX + 0.42, TY - 0.16, TZ + 0.02), M_POT, C_PROPS, rot=(0, 0, math.radians(12)), bev=0.004)
sphere("Lid_Knob", 0.022, (TX + 0.42, TY - 0.16, TZ + 0.042), M_POT, C_PROPS)

# table setting around the hero pot
for i, (dx, dy) in enumerate(((-0.33, -0.20), (0.33, -0.20), (0.0, 0.34), (-0.36, 0.26))):
    cyl(f"Plate_{i}", 0.105, 0.014, (TX + dx, TY + dy, TZ + 0.007), M_WHITE, C_PROPS, verts=40)
    torus(f"Plate_Rim_{i}", 0.095, 0.007, (TX + dx, TY + dy, TZ + 0.014), M_WHITE, C_PROPS, seg_major=40)
for i, (dx, dy) in enumerate(((-0.30, 0.12), (0.30, 0.12), (0.14, -0.36))):
    cyl(f"Bowl_{i}", 0.052, 0.048, (TX + dx, TY + dy, TZ + 0.024), M_WHITE, C_PROPS, verts=32)
    torus(f"Bowl_Rim_{i}", 0.050, 0.005, (TX + dx, TY + dy, TZ + 0.048), M_WHITE, C_PROPS, seg_major=32, seg_minor=6)
for i, (dx, dy) in enumerate(((-0.14, -0.33), (0.18, 0.33), (-0.40, -0.02))):
    cyl(f"Dip_{i}", 0.036, 0.022, (TX + dx, TY + dy, TZ + 0.011), M_WHITE, C_PROPS, verts=24)
for i, (dx, dy, rz) in enumerate(((-0.20, 0.24, 8), (0.22, 0.26, -6), (0.0, -0.30, 90))):
    for k in (-1, 1):
        cyl(
            f"Chopstick_{i}_{k}", 0.0042, 0.235,
            (TX + dx + k * 0.011 * math.sin(math.radians(rz)), TY + dy + k * 0.011 * math.cos(math.radians(rz)), TZ + 0.008),
            M_DARK, C_PROPS, verts=8, rot=(math.radians(90), 0, math.radians(rz)),
        )
for i, (dx, dy) in enumerate(((0.40, 0.06), (0.30, 0.40))):
    cyl(f"Glass_{i}", 0.033, 0.125, (TX + dx, TY + dy, TZ + 0.062), M_WHITE, C_PROPS, verts=24)
cube("Napkin_Box", (0.15, 0.09, 0.07), (TX - 0.44, TY + 0.10, TZ + 0.035), M_WHITE, C_PROPS, rot=(0, 0, math.radians(-15)), bev=0.008)

# window table setting (顾衍 eats alone)
GX, GY = G
cyl("G_Plate", 0.10, 0.013, (GX, GY, 0.746), M_WHITE, C_PROPS, verts=32)
cyl("G_Bowl", 0.05, 0.045, (GX + 0.16, GY - 0.10, 0.762), M_WHITE, C_PROPS, verts=24)
cyl("G_Glass", 0.032, 0.12, (GX - 0.15, GY + 0.12, 0.792), M_WHITE, C_PROPS, verts=24)
cyl("G_Pot", 0.16, 0.115, (GX, GY, 0.795), M_POT, C_PROPS, verts=48)
torus("G_Pot_Rim", 0.161, 0.009, (GX, GY, 0.856), M_POT, C_PROPS)

# ------------------------------------------------ pendant lamps over the tables
def pendant(name, x, y, z_bulb=2.42):
    cyl(f"{name}_Cable", 0.006, 0.55, (x, y, z_bulb + 0.34), M_DARK, C_PROPS, verts=8)
    cone(f"{name}_Shade", 0.17, 0.055, 0.15, (x, y, z_bulb + 0.10), M_WHITE, C_PROPS, verts=32)
    sphere(f"{name}_Bulb", 0.052, (x, y, z_bulb), M_GLOW, C_PROPS, seg=20, rings=12)
    bpy.ops.object.light_add(type="POINT", location=(x, y, z_bulb))
    lamp = bpy.context.active_object
    lamp.name = f"{name}_Light"
    lamp.data.energy = 28.0
    lamp.data.color = (1.0, 0.80, 0.58)
    lamp.data.shadow_soft_size = 0.06
    park(lamp, C_PROPS)


pendant("Pend_Hero", H[0], H[1] + 0.05)
pendant("Pend_G", GX, GY + 0.02)
pendant("Pend_BA", 2.55, 2.35)
pendant("Pend_BB", 2.40, -1.70)

# ---------------------------------------------------------------- steam (FX only)
def steam(name, ox, oy, height=0.62, drift=0.16, seed=0.0):
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 8
    curve.bevel_depth = 0.012
    curve.bevel_resolution = 3
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(2)
    pts = [
        (ox, oy, TZ + 0.15),
        (ox + drift * 0.5, oy + 0.03 + seed, TZ + 0.15 + height * 0.55),
        (ox + drift, oy - 0.02, TZ + 0.15 + height),
    ]
    for bp, co in zip(spline.bezier_points, pts):
        bp.co = Vector(co)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(M_STEAM)
    C_FX.objects.link(obj)
    return obj


for i, (dx, dy) in enumerate(((-0.07, 0.02), (0.06, -0.03), (0.0, 0.08))):
    pass  # steam geometry intentionally omitted: opaque wisps read as pipes and the
          # video model invents steam better than we can model it. Function kept for FX.

# ---------------------------------------------------------------- mannequins
PROXY_H = 1.13  # head centre height for a seated figure


def mannequin(name, x, y, rot_z=0.0, seated=True, scale=1.0):
    c, s = math.cos(rot_z), math.sin(rot_z)

    def place(dx, dy, dz):
        return (x + (dx * c - dy * s) * scale, y + (dx * s + dy * c) * scale, dz * scale)

    if seated:
        cube(f"{name}_Pelvis", (0.30, 0.28, 0.18), place(0, 0, 0.50), M_PROXY, C_PROXY, rot=(0, 0, rot_z), bev=0.06)
        sphere(f"{name}_Torso", 1.0, place(0, 0.01, 0.80), M_PROXY, C_PROXY, scale=(0.175 * scale, 0.115 * scale, 0.235 * scale))
        sphere(f"{name}_Shoulders", 1.0, place(0, 0.01, 1.00), M_PROXY, C_PROXY, scale=(0.215 * scale, 0.10 * scale, 0.075 * scale))
        for sgn in (-1, 1):
            cube(f"{name}_Thigh_{sgn}", (0.14, 0.42, 0.15), place(sgn * 0.09, -0.21, 0.48), M_PROXY, C_PROXY, rot=(0, 0, rot_z), bev=0.05)
            cube(f"{name}_Shin_{sgn}", (0.12, 0.14, 0.42), place(sgn * 0.10, -0.37, 0.23), M_PROXY, C_PROXY, rot=(0, 0, rot_z), bev=0.05)
            # The arm must bite into the torso, not sit tangent to it. A tangent contact
            # leaves a hairline sliver of far background between arm and body, which the
            # keyframe model paints as a dark hole at the armpit.
            cyl(f"{name}_Arm_{sgn}", 0.055, 0.42, place(sgn * 0.178, -0.01, 0.855), M_PROXY, C_PROXY, verts=20, rot=(0, 0, rot_z))
        head_z = PROXY_H
    else:
        sphere(f"{name}_Hips", 1.0, place(0, 0, 0.97), M_PROXY, C_PROXY, scale=(0.165 * scale, 0.105 * scale, 0.115 * scale))
        sphere(f"{name}_Torso", 1.0, place(0, 0.01, 1.30), M_PROXY, C_PROXY, scale=(0.170 * scale, 0.110 * scale, 0.245 * scale))
        sphere(f"{name}_Shoulders", 1.0, place(0, 0.01, 1.50), M_PROXY, C_PROXY, scale=(0.205 * scale, 0.095 * scale, 0.070 * scale))
        for sgn in (-1, 1):
            cyl(f"{name}_Leg_{sgn}", 0.062, 0.90, place(sgn * 0.085, 0, 0.48), M_PROXY, C_PROXY, verts=20, rot=(0, 0, rot_z))
            cyl(f"{name}_Arm_{sgn}", 0.045, 0.52, place(sgn * 0.205, 0, 1.24), M_PROXY, C_PROXY, verts=20, rot=(0, 0, rot_z))
        head_z = 1.61
    cyl(f"{name}_Neck", 0.045, 0.09, place(0, 0.01, head_z - 0.105), M_PROXY, C_PROXY, verts=16)
    sphere(f"{name}_Head", 0.098 * scale, place(0, 0.01, head_z), M_PROXY, C_PROXY, scale=(1.0, 1.06, 1.10))


mannequin("P_Sunian", H[0], H[1] + 0.72, rot_z=0.0, seated=True)             # facing the pot (toward -Y)
mannequin("P_Shu", H[0], H[1] - 0.80, rot_z=math.pi, seated=False)           # second uncle, standing over the pot
mannequin("P_Gu", GX, GY + 0.66, rot_z=0.0, seated=True)
mannequin("P_Diner_BA", 2.55, 2.35 - 0.64, rot_z=math.pi, seated=True)
mannequin("P_Diner_BB", 2.40, -1.70 + 0.64, rot_z=0.0, seated=True)
mannequin("P_Buyer", 1.05, -4.92, rot_z=math.pi, seated=True, scale=0.98)

# ---------------------------------------------------------------- street strip
cube("Street_Ground", (9.0, 2.7, 0.06), (0, -4.75, -0.03), M_DARK, C_SET)
cube("Street_Curb", (9.0, 0.18, 0.14), (0, -3.55, 0.07), M_MID, C_SET)
cube("Street_OppositeWall", (9.0, 0.20, 3.10), (0, -6.05, 1.55), M_MID, C_SET)
for i, x in enumerate((-4.0, -2.6, 1.9, 3.4)):
    cube(f"Street_Shutter_{i}", (0.9, 0.05, 2.0), (x, -5.92, 1.10), M_DARK, C_SET)

cyl("LampPost", 0.055, 3.40, (-2.60, -4.40, 1.70), M_MID, C_SET, verts=16)
cone("LampHead", 0.19, 0.09, 0.20, (-2.60, -4.40, 3.42), M_MID, C_SET, verts=24)
sphere("LampBulb", 0.075, (-2.60, -4.40, 3.30), M_GLOW, C_FX)
bpy.ops.object.light_add(type="POINT", location=(-2.60, -4.40, 3.30))
sl = bpy.context.active_object
sl.name = "StreetLamp_Light"
sl.data.energy = 260.0
sl.data.color = (1.0, 0.74, 0.44)
sl.data.shadow_soft_size = 0.12
park(sl, C_FX)

# folding stall table (beats 6-7)
SX, SY = 1.20, -4.30
cube("Stall_Top", (0.92, 0.56, 0.04), (SX, SY, 0.72), M_WHITE, C_FURN, bev=0.008)
for i, (dx, dy) in enumerate(((-0.40, -0.24), (0.40, -0.24), (-0.40, 0.24), (0.40, 0.24))):
    cyl(f"Stall_Leg_{i}", 0.016, 0.70, (SX + dx, SY + dy, 0.35), M_MID, C_FURN, verts=10)
cyl("Stall_Pot", 0.150, 0.115, (SX - 0.10, SY, 0.80), M_POT, C_PROPS, verts=48)
torus("Stall_Pot_Rim", 0.151, 0.009, (SX - 0.10, SY, 0.857), M_POT, C_PROPS)
cyl("Stall_Bowl", 0.05, 0.045, (SX + 0.22, SY + 0.02, 0.764), M_WHITE, C_PROPS, verts=24)
cube("Stall_Sign", (0.42, 0.02, 0.30), (SX - 0.52, SY + 0.20, 0.60), M_WHITE, C_FURN, rot=(math.radians(12), 0, 0), bev=0.006)
stool("Stall_Stool0", SX - 0.15, SY - 0.62)
stool("Stall_Stool1", SX + 0.55, SY - 0.50)

# ---------------------------------------------------------------- lighting
def area(name, loc, size, energy, color, rot=(0.0, 0.0, 0.0)):
    bpy.ops.object.light_add(type="AREA", location=loc, rotation=rot)
    lt = bpy.context.active_object
    lt.name = name
    lt.data.shape = "RECTANGLE"
    lt.data.size = size[0]
    lt.data.size_y = size[1]
    lt.data.energy = energy
    lt.data.color = color
    park(lt, C_SET)
    return lt


area("Key_Hero", (H[0] + 0.1, H[1] + 0.1, 2.68), (0.9, 0.9), 240.0, (1.0, 0.83, 0.64))
area("Fill_Ceiling", (1.2, -0.4, 3.05), (3.2, 3.2), 70.0, (0.72, 0.80, 0.95))
area("Window_Cool", (X0 + 0.18, -0.90, 1.70), (2.4, 1.3), 130.0, (0.52, 0.68, 1.0), rot=(0, math.radians(-90), 0))
area("Street_Fill", (2.2, -5.60, 2.60), (3.0, 1.6), 60.0, (0.45, 0.60, 1.0), rot=(math.radians(70), 0, 0))
bpy.ops.object.light_add(type="POINT", location=(-1.1, 2.80, 2.30))
rim = bpy.context.active_object
rim.name = "Rim_Back"
rim.data.energy = 90.0
rim.data.color = (1.0, 0.86, 0.70)
rim.data.shadow_soft_size = 0.3
park(rim, C_SET)

world = bpy.data.worlds.new("SetWorld")
scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
if bg:
    bg.inputs[0].default_value = (0.22, 0.23, 0.26, 1.0)
    bg.inputs[1].default_value = 0.55

# ---------------------------------------------------------------- cameras
SHOTS = {
    "s001": {"loc": (3.55, -3.10, 1.58), "target": (0.00, 0.70, 1.05), "lens": 24.0,
             "note": "establishing, in through the door"},
    "s002": {"loc": (-0.55, -0.65, 1.02), "target": (0.32, 0.52, 0.88), "lens": 35.0,
             "note": "low hero framing on the pot"},
    "s003": {"loc": (2.75, 0.55, 1.22), "target": (0.20, 0.45, 1.10), "lens": 24.0,
             "note": "profile two-shot, 二叔 standing over 苏念"},
    "s004": {"loc": (0.72, -0.60, 1.20), "target": (0.30, 1.18, 1.16), "lens": 50.0,
             "note": "close on 苏念, kitchen pass behind her"},
    "s005": {"loc": (-1.05, -2.15, 1.20), "target": (-2.28, -0.40, 1.14), "lens": 40.0,
             "note": "顾衍 alone at the window table"},
    "s006": {"loc": (3.10, -5.45, 1.52), "target": (1.20, -4.30, 0.95), "lens": 35.0,
             "note": "street stall, two-shot"},
    "s007": {"loc": (3.90, 1.90, 1.58), "target": (-0.20, -0.90, 0.92), "lens": 30.0,
             "note": "reverse wide from behind the counter, tilted down off the ceiling"},
    "s008": {"loc": (2.55, -3.85, 1.32), "target": (1.02, -4.86, 1.00), "lens": 24.0,
             "note": "the first customer behind the folding stall, shutters behind"},
    # --- added 13 Nov, nextblender.md item 2: two of ep01's eight beats name a frame the set
    # could not make, and ep02-03 need two more. Camera only — no geometry changes, so the eight
    # rigs above stay byte-identical and their shipped PNGs stay valid.
    # Target dropped 1.09 -> 1.00 m: the bowl edge was above frame, so the spoon had no geometry
    # under it. Supersedes keyframe 00033, which was rendered against the old target.
    "s009": {"loc": (1.02, -5.62, 1.20), "target": (1.02, -4.90, 1.00), "lens": 85.0,
             "note": "tight CU: 顾衍 tastes one spoonful, then sets it down"},
    "s010": {"loc": (0.30, 0.08, 1.26), "target": (0.30, 1.22, 1.09), "lens": 85.0,
             "note": "tight CU: 苏念's face, the freeze"},
    # Was 3.07 m at 35 mm — a 5.5 m tall frame for a 1.2 m opening, so the hatch disappeared and
    # the model rendered a distant woman in a bright kitchen. The camera was already 0.85 m behind
    # the hatch; the fault was the lens and a target 3 m past it. Now 45 mm with the subject at
    # 1.38 m, so the opening itself is the frame border.
    "s011": {"loc": (0.00, 4.25, 1.42), "target": (0.05, 2.90, 1.15), "lens": 45.0,
             "note": "through the pass-through, 苏念 carrying the pot toward camera"},
    # Target was 2.45 m — 0.85 m above the door head — so the frontage sat in the bottom third
    # under blank wall and a barred fence. Aim at the door, not over it.
    "s012": {"loc": (1.20, -5.90, 1.60), "target": (0.90, -3.45, 1.25), "lens": 30.0,
             "note": "shop front from the street at night, whole frontage"},
}

cams = {}
for shot_id, spec in SHOTS.items():
    bpy.ops.object.camera_add(location=spec["loc"])
    cam = bpy.context.active_object
    cam.name = f"CAM_{shot_id}"
    cam.data.lens = spec["lens"]
    cam.data.sensor_width = 36.0
    cam.data.sensor_fit = "AUTO"
    direction = Vector(spec["target"]) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    park(cam, C_SET)
    cams[shot_id] = cam

# ---------------------------------------------------------------- passes
# Depth and normal are produced with material overrides, not the compositor Z pass:
# the compositor path in 5.2 returns a flat gradient that carries no structure, and a
# guide pass that looks plausible but is empty is worse than no pass at all.
def override_depth():
    m = bpy.data.materials.new("OV_Depth")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    cd = nt.nodes.new("ShaderNodeCameraData")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.60
    mr.inputs["From Max"].default_value = 9.00
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    mr.clamp = True
    nt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def override_normal():
    m = bpy.data.materials.new("OV_Normal")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(geo.outputs["Normal"], sep.inputs["Vector"])
    for i in range(3):
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = -1.0
        mr.inputs["From Max"].default_value = 1.0
        mr.inputs["To Min"].default_value = 0.0
        mr.inputs["To Max"].default_value = 1.0
        nt.links.new(sep.outputs[i], mr.inputs["Value"])
        nt.links.new(mr.outputs[0], comb.inputs[i])
    nt.links.new(comb.outputs["Vector"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


MAT_DEPTH = override_depth()
MAT_NORMAL = override_normal()
# A datablock with no users is purged when the .blend is saved. These two are only ever *view-layer
# overrides*, so they have no object users: the delivered set shipped without them while rendering
# correctly in the build session. Pin them, or every later guide render from the saved file has to
# rebuild the override by hand.
for _m in (MAT_DEPTH, MAT_NORMAL):
    _m.use_fake_user = True

blend_path = out_dir / "huoguo_set.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

# ---------------------------------------------------------------- sightline check
# A camera that is blocked by furniture produces a render that looks broken and costs a
# full debug cycle. Ray-cast every camera at its target and report what is in the way.
depsgraph = bpy.context.evaluated_depsgraph_get()
for shot_id, spec in SHOTS.items():
    origin = Vector(spec["loc"])
    target = Vector(spec["target"])
    direction = (target - origin)
    dist = direction.length
    hit, loc, _nrm, _idx, obj, _mat = scene.ray_cast(depsgraph, origin, direction.normalized(), distance=dist)
    frac = ((loc - origin).length / dist) if hit else 1.0
    tag = "CLEAR" if (not hit or frac > 0.985) else "BLOCKED"
    print(f"SIGHTLINE {shot_id} {tag} frac={frac:.3f} first_hit={obj.name if hit else '-'}")

# Per-shot depth ramp. One fixed range cannot serve both a wide and a close-up: at a 1.3 m
# subject distance the whole frame lands in the top tenth of a 0.6-9.0 m ramp and renders as
# flat grey with no gradient to guide on. Derive near/far from the rig so every frame spans
# subject to backdrop, and record the range beside the shot so it stays reproducible.
def depth_range(spec):
    d = (Vector(spec["target"]) - Vector(spec["loc"])).length
    near = min(max(d * 0.50, 0.35), 4.00)
    far = near + max(d * 1.60, 3.20)
    return round(near, 3), round(far, 3)


(out_dir / "set_huoguo_cameras.json").write_text(
    json.dumps(
        {
            "set": "huoguo",
            "story": "laotang",
            "resolution": [width, height],
            "units": "metres",
            "shots": {
                k: {
                    "loc": v["loc"],
                    "target": v["target"],
                    "lens_mm": v["lens"],
                    "depth_near_m": depth_range(v)[0],
                    "depth_far_m": depth_range(v)[1],
                    "note": v["note"],
                }
                for k, v in SHOTS.items()
            },
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

# The depth override is a single material; its ramp is retuned per shot just before the pass.
def set_depth_range(near, far):
    for n in MAT_DEPTH.node_tree.nodes:
        if n.type == "MAP_RANGE":
            n.inputs["From Min"].default_value = near
            n.inputs["From Max"].default_value = far


# The control pass is the depth pass with a few pixels of blur. A razor-sharp near-white
# silhouette edge is read by the keyframe model as a separate object and painted as a white
# arc above every head; the blur removes the step and keeps every surface boundary that
# matters. Measured, not guessed: sharp 0.85 gives halos, blurred 0.72 loses layout,
# blurred 0.85 gives neither.
def write_depth_ctrl(src, radius):
    img = bpy.data.images.load(str(src))
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    rgb = a[:, :, :3].copy()
    n = 2 * radius + 1
    for axis in (0, 1):
        pad = [(0, 0)] * 3
        pad[axis] = (radius, radius)
        p = np.pad(rgb, pad, mode="edge")
        acc = np.zeros_like(rgb)
        for k in range(n):
            acc += p[k : k + h, :, :] if axis == 0 else p[:, k : k + w, :]
        rgb = acc / n
    a[:, :, :3] = rgb
    bpy.data.images.remove(img)
    out = src.with_name(src.name.replace("_depth.png", "_depth_ctrl.png"))
    res = bpy.data.images.new("ctrl", width=w, height=h, alpha=True)
    res.pixels.foreach_set(a.ravel())
    res.filepath_raw = str(out)
    res.file_format = "PNG"
    res.save()
    bpy.data.images.remove(res)
    return out


fx_objects = [o for o in C_FX.objects]
shot_ids = list(SHOTS) if shots_arg == "all" else [s for s in shots_arg.split(",") if s in SHOTS]
vl = scene.view_layers[0]

# Guide passes must be linear. AgX maps emission 1.0 to about 0.85 and squeezes exactly the
# highlight end where near geometry lives - most of why close-up depth read as flat grey.
beauty_vt = scene.view_settings.view_transform

for shot_id in shot_ids:
    if ctrl_only:
        write_depth_ctrl(out_dir / f"{shot_id}_depth.png", ctrl_radius)
        print(f"CTRL {shot_id} radius={ctrl_radius}")
        continue

    scene.camera = cams[shot_id]

    for o in fx_objects:
        o.hide_render = False
    vl.material_override = None
    scene.render.film_transparent = False
    scene.render.filepath = str(out_dir / f"{shot_id}_beauty.png")
    bpy.ops.render.render(write_still=True)

    for o in fx_objects:
        o.hide_render = True

    scene.view_settings.view_transform = "Standard"
    near, far = depth_range(SHOTS[shot_id])
    set_depth_range(near, far)
    print(f"DEPTH {shot_id} near={near:.2f} far={far:.2f}")

    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGB"

    vl.material_override = MAT_DEPTH
    scene.render.filepath = str(out_dir / f"{shot_id}_depth.png")
    bpy.ops.render.render(write_still=True)

    vl.material_override = MAT_NORMAL
    scene.render.filepath = str(out_dir / f"{shot_id}_normal.png")
    bpy.ops.render.render(write_still=True)

    # A depth pass that renders as one flat grey is a defect this pipeline already shipped
    # once: the guide looks like an image and carries nothing. Measure the spread instead of
    # trusting the eye, and say so loudly.
    img = bpy.data.images.load(str(out_dir / f"{shot_id}_depth.png"))
    sd = float(np.array(img.pixels[:], dtype=np.float32).std())
    bpy.data.images.remove(img)
    print(f"DEPTHSTAT {shot_id} std={sd:.3f} {'OK' if sd > 0.06 else 'FLAT'}")

    write_depth_ctrl(out_dir / f"{shot_id}_depth.png", ctrl_radius)
    print(f"CTRL {shot_id} radius={ctrl_radius}")

    vl.material_override = None
    scene.view_settings.view_transform = beauty_vt

print("RENDERED", shot_ids)
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot-id", default="all", help="all, or a comma list: s002,s004")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--ctrl-only", action="store_true", help="only rebuild the blurred control passes from existing depth PNGs")
    args = ap.parse_args()

    blender = find_blender()
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = out_dir / "._huoguo_set_build.py"
    runner.write_text(BLENDER_SCRIPT, encoding="utf-8")
    try:
        res = subprocess.run(
            [
                str(blender),
                "-b",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(runner),
                "--",
                str(out_dir),
                str(args.width),
                str(args.height),
                args.shot_id,
                str(args.samples),
                "ctrl" if args.ctrl_only else "-",
            ],
            text=True,
            capture_output=True,
        )
    finally:
        runner.unlink(missing_ok=True)

    if res.returncode != 0:
        print(res.stdout[-4000:])
        print(res.stderr[-4000:], file=sys.stderr)
        return res.returncode

    blend_path = out_dir / "huoguo_set.blend"
    print(f"blender: {blender}")
    print(f"blend  : {blend_path} sha256={sha256_file(blend_path)}")
    for line in res.stdout.splitlines():
        if line.startswith(("SIGHTLINE", "DEPTH", "CTRL", "RENDERED")):
            print(line)
    for p in sorted(out_dir.glob("*.png")):
        print(f"pass   : {p.name} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
