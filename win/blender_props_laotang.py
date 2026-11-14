#!/usr/bin/env python3
"""Build the 旧铜锅 prop library for 《老汤》 — item 3 of nextblender.md.

The series is named after the pot in this file and, until now, the pot did not exist: the set
carried `Stall_Pot`, a plain copper cylinder, and the hero 鸳鸯锅 with its divider — a *different*
pot, the one 苏建国 keeps. 苏念 picks the 旧铜锅 out of the rubbish in beat 5 and 顾衍 recognises
it. It has to be one object, one hash, in three files.

Five props, one collection each, one merged mesh each:

    Prop_Tongguo           0.19 m rim radius, one ear handle, 4 real rim facets, open top
    Prop_Tongguo_Lid       separate, authored already ajar on that rim
    Prop_Sign_Cardboard    0.55 x 0.40 folded board, two flaps, no text
    Prop_Bowl_White        the bowl 顾衍 sets down (held object in s009)
    Prop_Chopsticks_Rest   one pair + rest

**Pot space.** Both the pot and its lid share one origin: the pot's base centre, on the floor, at
world (0, 0, 0). The lid is authored tilted against that rim, so linking it at the pot's location
reproduces the ajar pose with no extra transform. Every other prop also sits with its base at
z = 0, origin at (0, 0, 0), so a set builder can link a prop and place it by position alone.

**Turnaround.** `prop_<name>_turn.png` is one 2048 x 1024 sheet: 8 azimuths in a 4 x 2 grid,
orthographic, 85 mm-equivalent, the object rotated rather than the camera so the lighting is
identical in all eight cells — otherwise two views differing only in shading look like two
different silhouettes. `prop_Tongguo_turn_depth.png` is the same grid through OV_Depth, which is
where the ear handle and the four facets have to read as shape rather than as a smooth cylinder.

Run with Python on Windows (Blender auto-detected; override with BLENDER_EXE):

    python win/blender_props_laotang.py
    python win/blender_props_laotang.py --only Prop_Tongguo
    python win/blender_props_laotang.py --no-render

Output: work/props/props_laotang.blend + prop_<name>_turn.png (+ the pot's depth sheet)
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
DEFAULT_OUT = REPO / "work" / "props"


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
import math
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(argv[0])
cell = int(argv[1])
samples = int(argv[2])
only_arg = argv[3]
ctrl_only = len(argv) > 4 and argv[4] == "ctrl"
if ctrl_only:
    only_arg = "none"

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

scene.render.resolution_x = cell
scene.render.resolution_y = cell
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.film_transparent = False
scene.render.use_compositing = False
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


def park(obj, coll):
    for other in list(obj.users_collection):
        other.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def find_principled(mat):
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def clay(name, value, rough=0.82, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = find_principled(m)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (value, value, value, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metal
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.18
    return m


# Same palette values as the 火锅店 set so a linked prop sits in it without a colour jump.
M_WHITE = clay("Clay_White", 0.86, 0.85)
M_MID = clay("Clay_Mid", 0.55, 0.8)
M_DARK = clay("Clay_Dark", 0.26, 0.65)
M_TONG = clay("Clay_Tong", 0.72, 0.42, metal=0.25)    # tarnished copper
M_CARD = clay("Clay_Card", 0.64, 0.92)


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


def cone(name, r1, r2, h, loc, mat, coll, verts=64, rot=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=h, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    smooth(o, math.radians(30))
    return park(o, coll)


def torus(name, major, minor, loc, mat, coll, rot=(0.0, 0.0, 0.0), seg_major=64, seg_minor=10):
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


def pivot_rotate(obj, pivot, axis, deg):
    # Bake the object's transform from its *properties*, never from matrix_world: matrix_world is
    # the last evaluated matrix, so assigning to it in the same tick as `obj.scale = size`
    # silently discards that scale. That is why the sign board's two flaps first came out as
    # unit cubes (1.351 m across = a 1 x 1 x 1 cube rotated 28 deg) while the unrotated centre
    # panel was correct. Bake, rotate the mesh about a world-space pivot, leave the object at
    # identity.
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


# ================================================================ 1. the 旧铜锅
C_POT = new_coll("Prop_Tongguo")

R_TOP, R_BOT, H = 0.190, 0.155, 0.140
pot = cone("Tongguo_Body", R_BOT, R_TOP, H, (0, 0, H / 2), M_TONG, C_POT, verts=72)

# The mouth: drop the top cap so the pot is actually open, then give the wall real thickness.
# A closed cylinder with a rim torus around it reads as a smooth drum in the depth pass — the
# exact failure this prop exists to avoid.
me = pot.data
bm = bmesh.new()
bm.from_mesh(me)
bm.normal_update()
top_faces = [f for f in bm.faces if f.normal.z > 0.9]
bmesh.ops.delete(bm, geom=top_faces, context="FACES_ONLY")
bm.to_mesh(me)
bm.free()


def dent_rim(obj, centers, depth=0.013, half_width=0.30, z_from=0.42):
    # Four shallow concave facets pressed into the upper wall. Real vertices, not a normal map:
    # the dent has to show up in the depth pass as a change in silhouette.
    me = obj.data
    zs = [v.co.z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    span = max(1e-6, z1 - z0)
    moved = 0
    for v in me.vertices:
        x, y, z = v.co
        r = math.hypot(x, y)
        if r < 1e-5:
            continue
        t = (z - z0) / span
        if t < z_from:
            continue
        wz = ((t - z_from) / (1.0 - z_from)) ** 0.7
        a = math.atan2(y, x)
        disp = 0.0
        for c in centers:
            d = abs((a - c + math.pi) % (2.0 * math.pi) - math.pi)
            if d < half_width:
                disp = max(disp, depth * math.cos(d / half_width * math.pi / 2.0) ** 2)
        if disp > 0.0:
            k = max(0.05, 1.0 - disp * wz / r)
            v.co.x = x * k
            v.co.y = y * k
            moved += 1
    return moved


# Deliberately uneven: four evenly spaced facets are rotationally symmetric and would read as a
# smooth cylinder again in half the turnaround views.
DENT_CENTRES = (0.00, 1.55, 3.05, 4.70)
n_dented = dent_rim(pot, DENT_CENTRES)

bpy.context.view_layer.objects.active = pot
sol = pot.modifiers.new("Wall", "SOLIDIFY")
sol.thickness = 0.006
sol.offset = 0.0
bpy.ops.object.modifier_apply(modifier=sol.name)

# One ear handle. Ring lies in the YZ plane at the rim, half of it buried in the wall so it
# reads as attached rather than glued on.
torus("Tongguo_Ear", 0.032, 0.0085, (R_TOP - 0.004, 0.0, H - 0.028), M_TONG, C_POT,
      rot=(0.0, math.radians(90), 0.0), seg_major=32, seg_minor=10)

# ================================================================ 2. the lid
C_LID = new_coll("Prop_Tongguo_Lid")
R_LID = R_TOP + 0.014
cyl("Lid_Disc", R_LID, 0.010, (0, 0, H + 0.016), M_TONG, C_LID, verts=72)
torus("Lid_Rim", R_LID, 0.006, (0, 0, H + 0.016), M_TONG, C_LID, seg_major=72)
cyl("Lid_Knob_Stem", 0.018, 0.014, (0, 0, H + 0.028), M_TONG, C_LID, verts=24)
sphere("Lid_Knob", 0.020, (0, 0, H + 0.040), M_TONG, C_LID, scale=(1.0, 1.0, 0.72))

# ================================================================ 3. the sign board
C_SIGN = new_coll("Prop_Sign_Cardboard")
SIGN_H = 0.40
cube("Sign_Centre", (0.24, 0.006, SIGN_H), (0, 0, SIGN_H / 2 + 0.001), M_CARD, C_SIGN, bev=0.002)
FLAP_W = 0.155
FLAP_CX = 0.12 + FLAP_W / 2.0     # inner edge on the hinge, not centred on the panel
flap_l = cube("Sign_Flap_L", (FLAP_W, 0.006, SIGN_H), (-FLAP_CX, 0, SIGN_H / 2 + 0.001), M_CARD, C_SIGN, bev=0.002)
flap_r = cube("Sign_Flap_R", (FLAP_W, 0.006, SIGN_H), (FLAP_CX, 0, SIGN_H / 2 + 0.001), M_CARD, C_SIGN, bev=0.002)
# Both wings fold to +Y, giving the self-standing trough a folded cardboard sign has. Total
# stock is 0.24 + 2 x 0.155 = 0.550 m; folded it projects 0.514 x 0.147.
pivot_rotate(flap_l, (-0.12, 0, 0), "Z", -28.0)
pivot_rotate(flap_r, (0.12, 0, 0), "Z", 28.0)

# ================================================================ 4. the bowl
C_BOWL = new_coll("Prop_Bowl_White")
cone("Bowl_Body", 0.038, 0.056, 0.042, (0, 0, 0.027), M_WHITE, C_BOWL, verts=48)
torus("Bowl_Rim", 0.056, 0.0045, (0, 0, 0.048), M_WHITE, C_BOWL, seg_major=48, seg_minor=8)
cyl("Bowl_Foot", 0.030, 0.008, (0, 0, 0.004), M_WHITE, C_BOWL, verts=32)

# ================================================================ 5. chopsticks + rest
C_STICKS = new_coll("Prop_Chopsticks_Rest")
for i, dy in enumerate((-0.011, 0.011)):
    cyl(f"Stick_{i}", 0.0042, 0.235, (0, dy, 0.0062), M_DARK, C_STICKS, verts=10,
        rot=(0.0, math.radians(90), 0.0))
cube("Rest_Block", (0.058, 0.032, 0.010), (0, 0, 0.005), M_WHITE, C_STICKS, bev=0.004)
for i, dy in enumerate((-0.011, 0.011)):
    cyl(f"Rest_Ridge_{i}", 0.0055, 0.062, (0, dy, 0.0115), M_WHITE, C_STICKS, verts=16,
        rot=(0.0, math.radians(90), 0.0))


# ================================================================ merge each prop
def harvest(coll, name):
    objs = [o for o in coll.objects if o.type in {"MESH", "CURVE"}]
    if not objs:
        raise RuntimeError(f"{coll.name} is empty")
    # Bake each part's own transform BEFORE joining. Joining parts that carry different
    # non-uniform object scales bakes shear into the result: the first sign board came out
    # 1.351 m wide instead of 0.550 m for exactly that reason. Baking first leaves every part
    # with an identity transform, so join is a pure mesh merge.
    for o in objs:
        for s in bpy.context.selected_objects:
            s.select_set(False)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for s in bpy.context.selected_objects:
        s.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    obj.data.name = name
    # Every prop ends with its base at z = 0 and its origin at the world origin, so a set
    # builder places it by position alone.
    obj.location = (0.0, 0.0, 0.0)
    return obj


PROPS = {}
PROPS["Prop_Tongguo"] = harvest(C_POT, "Prop_Tongguo")
lid = harvest(C_LID, "Prop_Tongguo_Lid")
# Authored ajar: rotate about the contact edge, not about the pot's axis, so the far edge lifts
# and the near edge stays on the rim.
pivot_rotate(lid, (-R_LID, 0.0, H + 0.016), "Y", 7.5)
PROPS["Prop_Tongguo_Lid"] = lid
PROPS["Prop_Sign_Cardboard"] = harvest(C_SIGN, "Prop_Sign_Cardboard")
PROPS["Prop_Bowl_White"] = harvest(C_BOWL, "Prop_Bowl_White")
PROPS["Prop_Chopsticks_Rest"] = harvest(C_STICKS, "Prop_Chopsticks_Rest")

# ================================================================ overrides
def override_depth():
    m = bpy.data.materials.new("OV_Depth")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    cd = nt.nodes.new("ShaderNodeCameraData")
    mr = nt.nodes.new("ShaderNodeMapRange")
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

# ================================================================ studio
bpy.ops.object.light_add(type="AREA", location=(0.0, -2.2, 2.0))
key = bpy.context.active_object
key.name = "Key_Prop"
key.data.shape = "RECTANGLE"
key.data.size = 2.4
key.data.size_y = 2.4
key.data.energy = 420.0
key.data.color = (1.0, 0.94, 0.86)
for c in list(key.users_collection):
    c.objects.unlink(key)
scene.collection.objects.link(key)

bpy.ops.object.light_add(type="AREA", location=(2.6, -1.4, 1.2))
fill = bpy.context.active_object
fill.name = "Fill_Prop"
fill.data.size = 3.0
fill.data.energy = 160.0
fill.data.color = (0.80, 0.86, 1.0)
for c in list(fill.users_collection):
    c.objects.unlink(fill)
scene.collection.objects.link(fill)

world = bpy.data.worlds.new("PropWorld")
scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
if bg:
    bg.inputs[0].default_value = (0.34, 0.35, 0.38, 1.0)
    bg.inputs[1].default_value = 0.85

bpy.ops.object.camera_add(location=(0.0, -2.0, 0.5))
cam = bpy.context.active_object
cam.name = "CAM_TURN"
cam.data.lens = 85.0
cam.data.sensor_width = 36.0
cam.data.type = "ORTHO"
for c in list(cam.users_collection):
    c.objects.unlink(cam)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def frame_prop(name):
    obj = PROPS[name]
    mw = obj.matrix_world
    pts = [mw @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0
    verts = [mw @ v.co for v in obj.data.vertices]
    radius_xy = max((math.hypot(p.x - cx, p.y - cy) for p in verts), default=0.1)
    half_z = max((abs(p.z - cz) for p in verts), default=0.1)
    extent = max(radius_xy, half_z, 0.02)
    cam.data.ortho_scale = 2.0 * extent * 1.18
    cam.data.clip_start = 0.01
    D = max(2.5, extent * 8.0)
    cam.data.clip_end = D * 3.0
    elev = math.radians(10.0)
    cam.location = (cx, cy - D * math.cos(elev), cz + D * math.sin(elev))
    aim(cam, (cx, cy, cz))
    return extent, (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def sheet(paths, out_path, cols):
    rows = math.ceil(len(paths) / cols)
    big = np.zeros((rows * cell, cols * cell, 4), dtype=np.float32)
    big[:, :, 3] = 1.0
    for i, p in enumerate(paths):
        img = bpy.data.images.load(str(p), check_existing=False)
        img.colorspace_settings.name = "Non-Color"
        a = np.array(img.pixels[:], dtype=np.float32).reshape(cell, cell, 4)
        bpy.data.images.remove(img)
        c = i % cols
        r = i // cols
        y0 = (rows - 1 - r) * cell    # image rows run bottom-up
        big[y0:y0 + cell, c * cell:(c + 1) * cell, :] = a
    out = bpy.data.images.new("sheet", width=cols * cell, height=rows * cell, alpha=True)
    out.colorspace_settings.name = "Non-Color"
    out.pixels.foreach_set(big.ravel())
    out.filepath_raw = str(out_path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    return cols * cell, rows * cell


blend_path = out_dir / "props_laotang.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

print(f"LIB props={','.join(PROPS)} dented_verts={n_dented}")

if only_arg != "none":
    wanted = list(PROPS) if only_arg == "all" else [n for n in only_arg.split(",") if n in PROPS]
    tmp = out_dir / "._turn_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    vl = scene.view_layers[0]
    all_objs = list(PROPS.values())

    for name in wanted:
        obj = PROPS[name]
        for other in all_objs:
            other.hide_render = other is not obj
        extent, dims = frame_prop(name)
        print(f"PROP {name} dims={dims[0]:.3f}x{dims[1]:.3f}x{dims[2]:.3f} "
              f"verts={len(obj.data.vertices)} extent={extent:.3f}")

        base_rot = obj.rotation_euler.copy()
        beauty_paths = []
        depth_paths = []

        for i in range(8):
            obj.rotation_euler = base_rot
            obj.rotation_euler.z = base_rot.z + math.radians(45.0 * i)
            scene.view_settings.view_transform = BEAUTY_VT
            vl.material_override = None
            scene.render.film_transparent = False
            p_beauty = tmp / f"{name}_v{i}_beauty.png"
            scene.render.filepath = str(p_beauty)
            bpy.ops.render.render(write_still=True)
            beauty_paths.append(p_beauty)

            if name != "Prop_Tongguo":
                continue

            # Depth for the named pot only: this is where the ear and the facets must appear as
            # shape. Ramp derived from the framing, as in every other pass in this project.
            scene.view_settings.view_transform = GUIDE_VT
            near = max(0.02, (cam.location - Vector((0, 0, 0))).length - 2.4 * extent)
            far = (cam.location - Vector((0, 0, 0))).length + 2.4 * extent
            for n in MAT_DEPTH.node_tree.nodes:
                if n.type == "MAP_RANGE":
                    n.inputs["From Min"].default_value = near
                    n.inputs["From Max"].default_value = far
            scene.render.film_transparent = True
            vl.material_override = MAT_DEPTH
            p_depth = tmp / f"{name}_v{i}_depth.png"
            scene.render.filepath = str(p_depth)
            bpy.ops.render.render(write_still=True)
            depth_paths.append(p_depth)

        obj.rotation_euler = base_rot
        vl.material_override = None
        scene.view_settings.view_transform = BEAUTY_VT

        w, h = sheet(beauty_paths, out_dir / f"prop_{name.replace('Prop_', '').lower()}_turn.png", 4)
        print(f"TURN {name} views=8 sheet=prop_{name.replace('Prop_', '').lower()}_turn.png {w}x{h}")

        if depth_paths:
            arrs = []
            for p in depth_paths:
                img = bpy.data.images.load(str(p), check_existing=False)
                img.colorspace_settings.name = "Non-Color"
                arrs.append(np.array(img.pixels[:], dtype=np.float32))
                bpy.data.images.remove(img)
            sd = float(arrs[0].std())
            # Compare opposite views by the number of pixels that actually changed, not by the
            # whole-image mean: the background is identical in both, so a mean hides a 4 %-of-
            # frame ear handle completely (measured 0.0057 mean on a pot that is correct).
            d = np.abs(arrs[0] - arrs[4])
            diff = float(d.max())
            frac = float((d > 0.05).mean())
            print(f"DEPTHSTAT {name} std={sd:.3f} {'OK' if sd > 0.06 else 'FLAT'}")
            print(f"DENTCHK {name} view0_vs_view4_max={diff:.3f} frac_changed={frac:.4f} "
                  f"{'ASYMMETRIC' if frac > 0.002 else 'SYMMETRIC-dents-do-not-read'}")
            w2, h2 = sheet(depth_paths, out_dir / "prop_tongguo_turn_depth.png", 4)
            print(f"TURN {name} depth=prop_tongguo_turn_depth.png {w2}x{h2}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("RENDERED", wanted)
else:
    print("RENDERED [] no passes requested")

print("PROPLIB done")
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all", help="all, or a comma list: Prop_Tongguo")
    ap.add_argument("--cell", type=int, default=512, help="pixels per turnaround cell")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--ctrl-only", action="store_true", help="build the .blend only")
    ap.add_argument("--no-render", action="store_true", help="write the .blend, render nothing")
    args = ap.parse_args()

    blender = find_blender()
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = out_dir / "._props_build.py"
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
                str(args.cell),
                str(args.samples),
                "none" if args.no_render else args.only,
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

    blend_path = out_dir / "props_laotang.blend"
    print(f"blender: {blender}")
    print(f"blend  : {blend_path} sha256={sha256_file(blend_path)}")
    for line in res.stdout.splitlines():
        if line.startswith(("LIB", "PROP", "TURN", "DEPTHSTAT", "DENTCHK", "RENDERED", "PROPLIB")):
            print(line)
    for p in sorted(out_dir.glob("*.png")):
        print(f"sheet  : {p.name} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
