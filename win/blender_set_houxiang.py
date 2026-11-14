#!/usr/bin/env python3
"""Build the 后巷 (back alley) white model for 《老汤》 — item 1 of nextblender.md.

The third location. `premise_laotang.md` says "no location moves" and names three set pieces: the
interior, the street strip (both in `huoguo_set.blend`) and this alley. It is where beat 5 happens,
where the 旧铜锅 is picked out of the rubbish, and where ep02 opens.

Three rigs, all looking back toward the shop door:

    x001  wide, 24 mm    苏念 out the back door, the pot at the kerb, shop wall at one end
    x002  low, 45 mm     close on the pot in the rubbish — the 捡锅 beat, must read *discarded*
    x003  over-shoulder  back at the shop door, 苏建国 framed in it, lit from inside

Dimensions are load-bearing, not taste:

    2.4 m wide x 11.0 m long, walls 3.2 m   narrow enough that a wide lens sees both walls, so
                                            the depth pass has near-left / near-right anchors.
                                            A wide alley renders as one flat plane.
    back door 1.30 x 2.10 m                 identical to the front door opening in
                                            huoguo_set.blend, or the two sets cannot cut together.

Rubbish is not decoration: three bin bags, a crate, a broken stool and a stack of cardboard. They
are the depth anchors for the lower third of every alley frame — without them the bottom of the
frame is a single grey plane and ControlNet gets nothing. Wet patches, rain and reflections are
deliberately absent: that is the video model's job, same division of labour as the street strip.

The 旧铜锅 is **linked** from `work/props/props_laotang.blend` as a collection instance, never
copied — one object, one hash, three files.

Run with Python on Windows (Blender auto-detected; override with BLENDER_EXE):

    python win/blender_set_houxiang.py                    # build + render all three rigs
    python win/blender_set_houxiang.py --shot-id x002
    python win/blender_set_houxiang.py --shot-id all --ctrl-only

Output: work/sets/houxiang/houxiang_set.blend + set_houxiang_cameras.json + xNNN_* passes
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
DEFAULT_OUT = REPO / "work" / "sets" / "houxiang"
PROPS_BLEND = REPO / "work" / "props" / "props_laotang.blend"


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

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(argv[0])
width = int(argv[1])
height = int(argv[2])
shots_arg = argv[3]
samples = int(argv[4])
ctrl_only = len(argv) > 5 and argv[5] == "ctrl"
props_blend = Path(argv[6])
ctrl_radius = max(2, round(width / 192))

GUIDE_VT = "Standard"
BEAUTY_VT = "AgX"

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
# Blender dithers 8-bit output by default. Two identical builds then produce different bytes for
# the same pixels, which silently makes "the passes are byte-identical" a claim that can never be
# tested by re-rendering. Off, so the guard means what it says.
scene.render.dither_intensity = 0.0
scene.frame_start = 1
scene.frame_end = 1
scene.view_settings.view_transform = BEAUTY_VT

for attr, value in (("taa_render_samples", samples), ("use_raytracing", True)):
    if hasattr(scene.eevee, attr):
        try:
            setattr(scene.eevee, attr, value)
        except (TypeError, AttributeError):
            pass


def new_coll(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


C_SET = new_coll("SET")
C_FURN = new_coll("FURN")
C_PROPS = new_coll("PROPS")
C_FX = new_coll("FX")
C_PROXY = new_coll("PROXY")


def park(obj, coll):
    for other in list(obj.users_collection):
        other.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


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


# Palette values identical to huoguo_set.blend and the prop library, so the sets cut together.
M_WHITE = clay("Clay_White", 0.86, 0.85)
M_MID = clay("Clay_Mid", 0.55, 0.8)
M_DARK = clay("Clay_Dark", 0.26, 0.65)
M_GLOW = clay("Clay_Glow", 0.95, 0.4, emit=6.0)
M_PROXY = clay("Clay_Proxy", 0.62, 0.9)


def smooth(obj, angle=math.radians(40)):
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=angle)
    except Exception:
        pass


def cube(name, size, loc, mat, coll, rot=(0.0, 0.0, 0.0), bev=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.data.materials.append(mat)
    if bev:
        m = o.modifiers.new("Bevel", "BEVEL")
        m.width = bev
        m.segments = 2
        m.limit_method = "ANGLE"
    return park(o, coll)


def cyl(name, r, h, loc, mat, coll, verts=48, rot=(0.0, 0.0, 0.0), do_smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    if do_smooth:
        smooth(o, math.radians(30))
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


def bake_rotate(obj, pivot, axis, deg):
    # Bake the object's own transform from its *properties*, then rotate the mesh about a
    # world-space pivot. Never assign obj.matrix_world for this: it is the last evaluated matrix,
    # so a .scale set in the same tick is silently dropped. That bug turned the prop library's
    # sign flaps into unit cubes.
    M = (Matrix.Translation(obj.location)
         @ obj.rotation_euler.to_matrix().to_4x4()
         @ Matrix.Diagonal(Vector(obj.scale).to_4d()))
    obj.data.transform(M)
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    p = Vector(pivot)
    obj.data.transform(Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p))
    return obj


# ================================================================ the alley shell
# x: -1.2 .. 1.2   y: 3.5 (shop back wall) .. 14.5 (dead end)   z: 0 .. 3.2
X0, X1, Y0, Y1, ZH = -1.2, 1.2, 3.5, 14.5, 3.2
LEN = Y1 - Y0
MIDY = (Y0 + Y1) / 2.0

cube("Alley_Slab", (X1 - X0, LEN, 0.10), (0, MIDY, -0.05), M_DARK, C_SET)
cube("Alley_LeftWall", (0.14, LEN, ZH), (X0 - 0.07, MIDY, ZH / 2), M_WHITE, C_SET)
cube("Alley_RightWall", (0.14, LEN, ZH), (X1 + 0.07, MIDY, ZH / 2), M_MID, C_SET)
cube("Alley_EndWall", (X1 - X0 + 0.28, 0.14, ZH), (0, Y1 + 0.07, ZH / 2), M_WHITE, C_SET)

# Expansion joints in the slab: four thin grooves, so the floor is not one unbroken plane.
for i, y in enumerate((5.4, 7.6, 9.8, 12.0)):
    cube(f"Joint_{i}", (X1 - X0, 0.035, 0.012), (0, y, 0.004), M_DARK, C_SET)
# Drain channel down the middle — a second, longitudinal depth line on the floor.
cube("Drain_Cover", (0.16, LEN, 0.014), (0, MIDY, 0.005), M_MID, C_SET)
for i, y in enumerate((5.0, 6.4, 7.8, 9.2, 10.6, 12.0, 13.4)):
    cube(f"Drain_Slat_{i}", (0.13, 0.02, 0.02), (0, y, 0.008), M_DARK, C_SET)

# Pilasters break each wall into planes. Two long flat walls converge without structure and the
# depth pass cannot tell the difference between them and the sky.
for i, y in enumerate((5.0, 7.6, 10.2, 12.8)):
    cube(f"Pilaster_L{i}", (0.14, 0.55, ZH), (X0 + 0.05, y, ZH / 2), M_WHITE, C_SET, bev=0.006)
    cube(f"Pilaster_R{i}", (0.14, 0.55, ZH), (X1 - 0.05, y, ZH / 2), M_MID, C_SET, bev=0.006)

# Services: two downpipes on the left wall, an AC box and a barred window high on the right.
for i, y in enumerate((6.3, 11.4)):
    cyl(f"Downpipe_{i}", 0.055, ZH, (X0 + 0.10, y, ZH / 2), M_MID, C_SET, verts=16)
    cyl(f"Downpipe_Bracket_{i}", 0.075, 0.05, (X0 + 0.10, y, 1.20), M_DARK, C_SET, verts=16)
cube("AC_Box", (0.34, 0.55, 0.38), (X1 - 0.20, 8.60, 2.55), M_WHITE, C_PROPS, bev=0.02)
cube("AC_Grille", (0.05, 0.44, 0.28), (X1 - 0.38, 8.60, 2.52), M_DARK, C_PROPS)
cube("Win_Recess", (0.05, 0.80, 0.60), (X1 - 0.02, 10.60, 2.20), M_DARK, C_SET)
for i in range(4):
    cube(f"Win_Bar_{i}", (0.09, 0.03, 0.62), (X1 - 0.06, 10.28 + i * 0.21, 2.20), M_MID, C_SET)

# ================================================================ shop back wall + door
# Opening must be 1.30 x 2.10 — the same as the front door in huoguo_set.blend.
DOOR_W, DOOR_H = 1.30, 2.10
half = DOOR_W / 2.0
jamb = (X1 - X0) / 2.0 - half
cube("BackWall_JambL", (jamb, 0.16, ZH), (X0 + jamb / 2.0, Y0, ZH / 2), M_WHITE, C_SET)
cube("BackWall_JambR", (jamb, 0.16, ZH), (X1 - jamb / 2.0, Y0, ZH / 2), M_WHITE, C_SET)
cube("BackWall_Header", (DOOR_W, 0.16, ZH - DOOR_H), (0, Y0, DOOR_H + (ZH - DOOR_H) / 2), M_WHITE, C_SET)
cube("DoorFrame_L", (0.06, 0.22, DOOR_H), (-half, Y0, DOOR_H / 2), M_MID, C_SET)
cube("DoorFrame_R", (0.06, 0.22, DOOR_H), (half, Y0, DOOR_H / 2), M_MID, C_SET)
cube("DoorFrame_T", (DOOR_W + 0.12, 0.22, 0.06), (0, Y0, DOOR_H), M_MID, C_SET)

# Door leaf, propped open into the alley. Rotated about the right-hand hinge, not about its own
# centre, or the leaf floats off the frame.
LEAF_W, LEAF_T, LEAF_H = 1.26, 0.05, 2.06
LEAF_ANG = -62.0
hx, hy = half, Y0 - 0.03
cx = hx - LEAF_W / 2.0
ca, sa = math.cos(math.radians(LEAF_ANG)), math.sin(math.radians(LEAF_ANG))
cube("Door_Leaf", (LEAF_W, LEAF_T, LEAF_H),
     (hx + (cx - hx) * ca, hy + (cx - hx) * sa, LEAF_H / 2), M_WHITE, C_SET,
     rot=(0, 0, math.radians(LEAF_ANG)), bev=0.004)
cube("Door_Sill", (DOOR_W + 0.18, 0.36, 0.11), (0, Y0 + 0.18, 0.055), M_MID, C_SET)
cube("Step_Outside", (DOOR_W + 0.30, 0.42, 0.06), (0, Y0 + 0.42, 0.03), M_DARK, C_SET)

# ================================================================ rubbish (depth anchors)
def lump(name, r, loc, mat, coll, scale, jitter=0.14, seed=0.0):
    o = sphere(name, r, loc, mat, coll, scale=scale)
    for v in o.data.vertices:
        v.co *= 1.0 + jitter * math.sin(v.index * 2.399 + seed)
    return o


# Three bin bags, deliberately different sizes and silhouettes.
lump("Bag_A", 1.0, (-0.94, 6.10, 0.22), M_DARK, C_PROPS, (0.30, 0.27, 0.24), 0.16, 0.4)
lump("Bag_B", 1.0, (-1.00, 6.68, 0.19), M_DARK, C_PROPS, (0.24, 0.23, 0.20), 0.18, 2.1)
lump("Bag_C", 1.0, (-0.84, 7.02, 0.16), M_DARK, C_PROPS, (0.19, 0.20, 0.17), 0.20, 4.7)
for i, (y, z) in enumerate(((6.10, 0.44), (6.68, 0.37), (7.02, 0.31))):
    cyl(f"Bag_Tie_{i}", 0.028, 0.06, (-0.94 + i * 0.05, y, z), M_DARK, C_PROPS, verts=12)

# Crate: four slats with gaps, so it reads as a crate in silhouette and not as a solid box.
cube("Crate_Base", (0.52, 0.42, 0.03), (-0.95, 5.55, 0.015), M_MID, C_PROPS, bev=0.004)
for sx in (-1, 1):
    cube(f"Crate_Side_{sx}", (0.03, 0.42, 0.34), (-0.95 + sx * 0.245, 5.55, 0.185), M_MID, C_PROPS)
for sy in (-1, 1):
    cube(f"Crate_End_{sy}", (0.52, 0.03, 0.34), (-0.95, 5.55 + sy * 0.195, 0.185), M_MID, C_PROPS)
for i in range(3):
    cube(f"Crate_Slat_{i}", (0.52, 0.02, 0.07), (-0.95, 5.55 - 0.20 + i * 0.20, 0.33), M_MID, C_PROPS)

# Broken stool, thrown out and lying on its side. Built upright, then tipped as one rigid group
# about its base: assigning each part's rotation_euler separately would lose the leg orientation
# baked in at creation and leave them standing while the seat fell over.
STOOL_X, STOOL_Y = 0.75, 7.35
seat = cyl("Stool_Seat", 0.17, 0.045, (STOOL_X, STOOL_Y, 0.42), M_WHITE, C_FURN, verts=32)
stool_parts = [seat]
for i, ang in enumerate((45, 135, 225, 315)):
    a = math.radians(ang)
    leg = cyl(f"Stool_Leg_{i}", 0.016, 0.42,
              (STOOL_X + 0.125 * math.cos(a), STOOL_Y + 0.125 * math.sin(a), 0.21),
              M_MID, C_FURN, verts=10)
    if i == 2:
        # One leg snapped short.
        leg.scale = (1.0, 1.0, 0.45)
        leg.location.z = 0.30
    stool_parts.append(leg)
for o in stool_parts:
    bake_rotate(o, (STOOL_X, STOOL_Y, 0.0), "Y", 72.0)

# Cardboard stack leaning on the right wall, each sheet askew.
for i in range(4):
    cube(f"Card_{i}", (0.62, 0.02, 0.44), (1.02 - i * 0.012, 5.15 + i * 0.035, 0.24 + i * 0.03),
         M_WHITE, C_PROPS, rot=(0, math.radians(-76 + i * 2.5), math.radians(-6 + i * 4)), bev=0.003)

# ================================================================ the pot, linked not copied
if not props_blend.is_file():
    raise SystemExit(f"prop library missing: {props_blend} — build item 3 first")
with bpy.data.libraries.load(str(props_blend), link=True) as (data_from, data_to):
    if "Prop_Tongguo" not in data_from.collections:
        raise SystemExit(f"Prop_Tongguo not in {props_blend}")
    data_to.collections = ["Prop_Tongguo"]
linked = data_to.collections[0]

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-0.62, 6.55, 0.0))
pot_inst = bpy.context.active_object
pot_inst.name = "LINK_Prop_Tongguo"
pot_inst.instance_type = "COLLECTION"
pot_inst.instance_collection = linked
# Tipped over, not standing: the beat is that it was thrown out.
pot_inst.rotation_euler = (math.radians(11), math.radians(6), math.radians(68))
pot_inst.empty_display_size = 0.12
park(pot_inst, C_PROPS)

# ================================================================ mannequins
PROXY_H = 1.13


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
            # The arm must bite into the torso, not sit tangent to it: a tangent contact leaves a
            # hairline sliver of far background that the keyframe model paints as an armpit hole.
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


# One 苏念 only. x001 sees her back mid-alley, x003 is over that same shoulder — a second copy of
# her facing the other way would put two of the same character in one frame.
mannequin("P_Sunian", -0.40, 5.05, rot_z=0.0, seated=False)
# 苏建国 framed in the doorway, facing out into the alley, lit from inside the shop.
mannequin("P_Shu", 0.0, 3.62, rot_z=math.pi, seated=False)
# 小满, 12 and about 1.40 m. She runs in from frame left at 56 s and says the line the whole alley
# exists for. The depth pass carries silhouette, not description, so if her *height* is not in the
# guide no prompt will ever produce her — 56–60 s would have nobody to speak.
XIAOMAN_SCALE = 1.40 / 1.72        # the standing proxy is ~1.72 m at scale 1
# 小满 is OFF-SCREEN. The shot list's 56-60 s line reads "小满 (off-screen): 「姐，今晚吃什么？」"
# — her entrance belongs to the alley's sound, not its picture, and x003 frames 苏建国 in the lit
# door. She is still built here so her height exists in the file if the sheet ever moves her into
# frame, but NO rig renders her. Set XIAOMAN_RIGS = ("x003",) to put her back in shot.
XIAOMAN_RIGS: tuple[str, ...] = ()
mannequin("P_Xiaoman", 0.40, 4.30, rot_z=math.pi, seated=False, scale=XIAOMAN_SCALE)
XIAOMAN_OBJS = [o for o in C_PROXY.objects if o.name.startswith("P_Xiaoman")]

# ================================================================ lighting
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


# Wall lamp over the back door.
cyl("Lamp_Box", 0.09, 0.10, (0.0, Y0 + 0.12, 2.72), M_MID, C_PROPS, verts=16)
sphere("Lamp_Bulb", 0.058, (0.0, Y0 + 0.14, 2.66), M_GLOW, C_FX)
bpy.ops.object.light_add(type="POINT", location=(0.0, Y0 + 0.16, 2.62))
lamp = bpy.context.active_object
lamp.name = "Door_Lamp_Light"
lamp.data.energy = 190.0
lamp.data.color = (1.0, 0.78, 0.52)
lamp.data.shadow_soft_size = 0.10
park(lamp, C_FX)

# Spill from inside the shop, through the open door. This is what lights 苏建国 from behind.
area("Door_Spill", (0.0, Y0 - 0.10, 1.15), (1.10, 1.90), 120.0, (1.0, 0.86, 0.66),
     rot=(math.radians(90), 0, 0))
# Cold, weak fill from the dead end so the far wall is not pure black in the beauty pass.
area("End_Fill", (0.0, Y1 - 0.30, 2.70), (2.2, 1.2), 40.0, (0.52, 0.66, 1.0),
     rot=(math.radians(-70), 0, 0))
area("Sky_Fill", (0.0, MIDY, 3.10), (2.0, 9.0), 60.0, (0.42, 0.52, 0.82))

world = bpy.data.worlds.new("AlleyWorld")
scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
if bg:
    bg.inputs[0].default_value = (0.09, 0.11, 0.16, 1.0)
    bg.inputs[1].default_value = 0.35

# ================================================================ rigs
SHOTS = {
    "x001": {"loc": (0.15, 9.90, 1.42), "target": (0.00, 3.56, 1.15), "lens": 24.0,
             "note": "wide establishing, 苏念 out the back door, pot at the kerb"},
    "x002": {"loc": (-0.10, 7.75, 0.34), "target": (-0.62, 6.55, 0.09), "lens": 45.0,
             "note": "low and close on the pot in the rubbish — the 捡锅 beat"},
    "x003": {"loc": (-0.05, 6.60, 1.55), "target": (0.00, 3.56, 1.20), "lens": 35.0,
             "note": "over 苏念's shoulder back at the shop door, 苏建国 framed in it"},
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

# ================================================================ passes
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
for _m in (MAT_DEPTH, MAT_NORMAL):
    _m.use_fake_user = True    # zero-user datablocks are purged on save


def overrides_pinned() -> bool:
    # Check the file on the way out, not the two locals on the way in: a pin that no-ops looks
    # identical to a pin that works, until someone reopens the saved .blend.
    want = {MAT_DEPTH.name, MAT_NORMAL.name}
    have = {m.name for m in bpy.data.materials if m.name.startswith("OV_")}
    ok = want <= have and all(m.use_fake_user for m in bpy.data.materials if m.name in want)
    print(f"OVATTR have={','.join(sorted(have)) or 'none'} pinned={ok}")
    return ok


blend_path = out_dir / "houxiang_set.blend"
if not overrides_pinned():
    raise SystemExit("OVATTR: OV_Depth/OV_Normal missing or unpinned — they will be purged on save")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
try:
    # Keep the prop link portable inside the repo. This needs the file to have a path first, hence
    # save -> relative -> save.
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
except Exception as exc:
    print(f"WARN make_paths_relative failed: {exc}")

bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
for shot_id, spec in SHOTS.items():
    origin = Vector(spec["loc"])
    target = Vector(spec["target"])
    direction = target - origin
    dist = direction.length
    hit, loc, _nrm, _idx, obj, _mat = scene.ray_cast(depsgraph, origin, direction.normalized(), distance=dist)
    frac = ((loc - origin).length / dist) if hit else 1.0
    tag = "CLEAR" if (not hit or frac > 0.985) else "BLOCKED"
    print(f"SIGHTLINE {shot_id} {tag} frac={frac:.3f} first_hit={obj.name if hit else '-'}")

# scene.ray_cast walks the evaluated scene but NOT collection instances, so a linked prop is
# invisible to the guard above: x002 aimed straight at the pot reported CLEAR on a correct set.
# Say so, and cover the prop with a projection test instead.
if any(inst.is_instance for inst in depsgraph.object_instances):
    print("SIGHTLINE NOTE ray_cast ignores collection instances — linked props are not tested; "
          "LINKCHECK below is their guard")
for shot_id, cam in cams.items():
    prop_p = pot_inst.matrix_world.translation + Vector((0.0, 0.0, 0.08))
    co = world_to_camera_view(scene, cam, prop_p)
    in_frame = (0.0 <= co.x <= 1.0) and (0.0 <= co.y <= 1.0) and co.z > 0.0
    print(f"LINKCHECK {shot_id} pot_uv=({co.x:.2f},{co.y:.2f}) in_frame={in_frame}")

# The child is the one proxy whose absence no statistic would catch: 56-60 s would render
# perfectly and simply have nobody in frame to say the line. Project her head into every rig AND
# ray-cast to it — being inside the frame is not the same as being visible, and the first placement
# sat at uv 0.79 with 苏念's body in front of her.
_xm_head = next(o for o in XIAOMAN_OBJS if o.name.endswith("_Head"))
for shot_id, cam in cams.items():
    head = _xm_head.matrix_world.translation
    co = world_to_camera_view(scene, cam, head)
    in_frame = (0.0 <= co.x <= 1.0) and (0.0 <= co.y <= 1.0) and co.z > 0.0
    eye = cam.location
    d = head - eye
    dist = d.length
    hit, _p, _n, _i, ob, _m = scene.ray_cast(depsgraph, eye, d.normalized(), distance=dist * 1.02)
    visible = bool(ob is not None and ob.name.startswith("P_Xiaoman"))
    # rendered_in_rig must read the same flag the render loop uses; a hardcoded 'x003' here said
    # "in shot" for a frame the loop was hiding her in.
    print(f"CHILDCHECK {shot_id} uv=({co.x:.2f},{co.y:.2f}) in_frame={in_frame} "
          f"visible={visible} first_hit={ob.name if hit else '-'} "
          f"rendered_in_rig={shot_id in XIAOMAN_RIGS}")


def depth_range(spec):
    d = (Vector(spec["target"]) - Vector(spec["loc"])).length
    near = min(max(d * 0.50, 0.35), 4.00)
    far = near + max(d * 1.60, 3.20)
    return round(near, 3), round(far, 3)


(out_dir / "set_houxiang_cameras.json").write_text(
    json.dumps(
        {
            "set": "houxiang",
            "story": "laotang",
            "resolution": [width, height],
            "units": "metres",
            "alley": {"width_m": X1 - X0, "length_m": LEN, "wall_height_m": ZH,
                      "door_w_m": DOOR_W, "door_h_m": DOOR_H},
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

print(f"ALLEY width={X1 - X0:.2f} length={LEN:.2f} height={ZH:.2f} door={DOOR_W:.2f}x{DOOR_H:.2f} "
      f"objects={len(bpy.data.objects)} linked={pot_inst.name}")


def set_depth_range(near, far):
    for n in MAT_DEPTH.node_tree.nodes:
        if n.type == "MAP_RANGE":
            n.inputs["From Min"].default_value = near
            n.inputs["From Max"].default_value = far


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
            acc += p[k:k + h, :, :] if axis == 0 else p[:, k:k + w, :]
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
beauty_vt = scene.view_settings.view_transform

for shot_id in shot_ids:
    if ctrl_only:
        write_depth_ctrl(out_dir / f"{shot_id}_depth.png", ctrl_radius)
        print(f"CTRL {shot_id} radius={ctrl_radius}")
        continue

    scene.camera = cams[shot_id]

    # Off-screen per the sheet, so no rig renders her — see XIAOMAN_RIGS. Turning her on for a
    # rig silently invalidates every keyframe rendered from that rig's existing guide.
    for o in XIAOMAN_OBJS:
        o.hide_render = shot_id not in XIAOMAN_RIGS

    for o in fx_objects:
        o.hide_render = False
    vl.material_override = None
    scene.view_settings.view_transform = beauty_vt
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
    vl.material_override = MAT_DEPTH
    scene.render.filepath = str(out_dir / f"{shot_id}_depth.png")
    bpy.ops.render.render(write_still=True)

    vl.material_override = MAT_NORMAL
    scene.render.filepath = str(out_dir / f"{shot_id}_normal.png")
    bpy.ops.render.render(write_still=True)

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
    ap.add_argument("--shot-id", default="all", help="all, or a comma list: x001,x003")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--ctrl-only", action="store_true", help="rebuild only the blurred control passes")
    args = ap.parse_args()

    blender = find_blender()
    if not PROPS_BLEND.is_file():
        print(f"missing prop library: {PROPS_BLEND}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = out_dir / "._houxiang_build.py"
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
                str(PROPS_BLEND),
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

    blend_path = out_dir / "houxiang_set.blend"
    print(f"blender: {blender}")
    print(f"blend  : {blend_path} sha256={sha256_file(blend_path)}")
    for line in res.stdout.splitlines():
        if line.startswith(("ALLEY", "SIGHTLINE", "LINKCHECK", "CHILDCHECK", "DEPTH", "CTRL", "RENDERED")):
            print(line)
    for p in sorted(out_dir.glob("*.png")):
        print(f"pass   : {p.name} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
