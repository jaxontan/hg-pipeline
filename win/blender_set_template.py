#!/usr/bin/env python3
"""Build the 布景模板 (set template) scaffold for 《老汤》 — item 7 of nextblender.md.

Every decision this pipeline already paid for lives in one file, so a new set is *copied*
rather than re-derived:

    collection names   SET / FURN / PROPS / FX / PROXY
    guide passes       Standard view transform, per-rig ramp, blurred control
    beauty pass        AgX
    resolution         768 x 1344
    overrides          OV_Depth + OV_Normal as *materials*, not the compositor Z pass
    guards             SIGHTLINE / DEPTHSTAT / CTRL / LINKCHECK

The two bugs this exists to prevent, both measured in Phase 1:

    AgX on a guide pass      compresses the near-white end and destroys the depth staircase
    un-blurred control       razor-sharp silhouette edges are read as separate objects and
                             painted back as a white halo above every head

Know what each guard is for. **SIGHTLINE is a furniture guard**: it ray-casts the set's own
geometry and says whether anything solid is between camera and target. **LINKCHECK is a prop
guard**: `scene.ray_cast` cannot see collection instances, so every *linked* prop is invisible to
SIGHTLINE and needs its own projection test. **Neither is a composition guard** — a CLEAR line
means nothing was in the ray's way, not that the frame is any good. Nobody has looked at the
beauty until someone has looked at it.

The scaffold ships with one rig, `t000`, looking at three probe boxes. That is not decoration:
an empty scene renders a flat depth pass, `DEPTHSTAT` reports FLAT, and the template would look
broken while proving nothing. `t000` is the self-test — build a new set by deleting the `Probe_*`
objects and replacing `SHOTS`.

Run with Python on Windows (Blender is auto-detected; override with BLENDER_EXE):

    python win/blender_set_template.py                     # build + render the self-test rig
    python win/blender_set_template.py --shot-id t000 --samples 32
    python win/blender_set_template.py --no-render         # scaffold only, no passes

Output: work/sets/_template/set_template.blend + t000_{beauty,depth,normal,depth_ctrl}.png
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
DEFAULT_OUT = REPO / "work" / "sets" / "_template"


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
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(argv[0])
width = int(argv[1])
height = int(argv[2])
shots_arg = argv[3]
samples = int(argv[4])
ctrl_only = len(argv) > 5 and argv[5] == "ctrl"
ctrl_radius = max(2, round(width / 192))

# Guide passes must be linear: AgX maps emission 1.0 to about 0.85 and squeezes exactly the
# highlight end where near geometry lives. Beauty wants AgX so the clay reads as material.
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
scene.frame_start = 1
scene.frame_end = 1
scene.view_settings.view_transform = BEAUTY_VT

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
C_FURN = new_coll("FURN")
C_PROPS = new_coll("PROPS")
C_FX = new_coll("FX")
C_PROXY = new_coll("PROXY")


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


# Same palette as the 火锅店 set: a new set that invents its own greys will not cut with it.
M_WHITE = clay("Clay_White", 0.86, 0.85)
M_MID = clay("Clay_Mid", 0.55, 0.8)
M_DARK = clay("Clay_Dark", 0.26, 0.65)
M_POT = clay("Clay_Pot", 0.72, 0.42)
M_GLOW = clay("Clay_Glow", 0.95, 0.4, emit=6.0)
M_PROXY = clay("Clay_Proxy", 0.62, 0.9)

# ---------------------------------------------------------------- primitives
def smooth(obj, angle=math.radians(40)):
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth(use_auto_smooth=True)
    except Exception:
        try:
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


# ---------------------------------------------------------------- self-test geometry
# Three depths plus two side walls, so the rig sees a real near/mid/far gradient. Delete the
# Probe_* objects when this template is copied for a real set.
X0, X1, Y0, Y1, ZH = -1.6, 1.6, -1.4, 1.9, 2.8

cube("Probe_Floor", (3.2, 3.3, 0.06), (0, 0.25, -0.03), M_DARK, C_SET)
cube("Probe_Wall_Far", (3.2, 0.10, ZH), (0, Y1, ZH / 2), M_WHITE, C_SET)
cube("Probe_Wall_Left", (0.10, 3.3, ZH), (X0, 0.25, ZH / 2), M_WHITE, C_SET)
cube("Probe_Wall_Right", (0.10, 3.3, ZH), (X1, 0.25, ZH / 2), M_MID, C_SET)
cube("Probe_Ceiling", (3.2, 3.3, 0.08), (0, 0.25, ZH), M_WHITE, C_SET)

cube("Probe_Box_Near", (0.46, 0.46, 0.46), (-0.55, -0.55, 0.23), M_POT, C_PROPS, bev=0.012)
cube("Probe_Box_Mid", (0.40, 0.40, 0.40), (0.62, 0.30, 0.20), M_MID, C_FURN, bev=0.012)
cube("Probe_Column", (0.22, 0.22, ZH), (0.95, 1.55, ZH / 2), M_DARK, C_SET)
cube("Probe_Ledge", (1.10, 0.30, 0.08), (-0.75, 1.70, 1.15), M_MID, C_FURN)

bpy.ops.object.light_add(type="AREA", location=(0.4, -1.0, 2.60))
key = bpy.context.active_object
key.name = "Key_Template"
key.data.shape = "RECTANGLE"
key.data.size = 1.6
key.data.size_y = 1.6
key.data.energy = 220.0
key.data.color = (1.0, 0.85, 0.68)
park(key, C_SET)

world = bpy.data.worlds.new("SetWorld")
scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
if bg:
    bg.inputs[0].default_value = (0.22, 0.23, 0.26, 1.0)
    bg.inputs[1].default_value = 0.55

# ---------------------------------------------------------------- rigs
SHOTS = {
    "t000": {"loc": (0.0, -2.90, 1.45), "target": (0.0, 0.35, 1.02), "lens": 35.0,
             "note": "template self-test — delete Probe_* and replace this rig"},
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
# Depth and normal are material overrides, not the compositor Z pass: in 5.2 the compositor
# path returns a flat gradient that carries no structure, and a guide that looks plausible but
# is empty is worse than no guide at all.
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
# A material with no users is purged when the .blend is saved, so the overrides would vanish
# from the file and the next set would silently re-invent them. Pin them.
for _m in (MAT_DEPTH, MAT_NORMAL):
    _m.use_fake_user = True


def overrides_pinned() -> bool:
    # A pin that silently no-ops is worse than no pin. huoguo_set.blend shipped with these
    # materials rendered in memory and absent from the saved file, and nothing complained. Assert
    # on the way out, against what is actually in bpy.data, not against the two locals.
    # NOTE: this file's body lives inside a raw triple-quoted string, so never write a triple
    # double-quote literal down here: it closes the outer string and the whole builder stops
    # parsing. This comment learned that the hard way — do not "fix" it back.
    want = {MAT_DEPTH.name, MAT_NORMAL.name}
    have = {m.name for m in bpy.data.materials if m.name.startswith("OV_")}
    ok = want <= have and all(m.use_fake_user for m in bpy.data.materials if m.name in want)
    print(f"OVATTR have={','.join(sorted(have)) or 'none'} pinned={ok}")
    return ok


# ---------------------------------------------------------------- ramp + guards
def depth_range(spec):
    # Per-rig ramp. A single global range makes close-ups flat grey.
    d = (Vector(spec["target"]) - Vector(spec["loc"])).length
    near = min(max(d * 0.50, 0.35), 4.00)
    far = near + max(d * 1.60, 3.20)
    return round(near, 3), round(far, 3)


def set_depth_range(near, far):
    for n in MAT_DEPTH.node_tree.nodes:
        if n.type == "MAP_RANGE":
            n.inputs["From Min"].default_value = near
            n.inputs["From Max"].default_value = far


def write_depth_ctrl(src, radius):
    # Blur the depth pass: a sharp near-white silhouette is read as a separate object.
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


_first = next(iter(SHOTS))
scene.camera = cams[_first]
# Bake the first rig's ramp into the saved file: opening this .blend and hitting render should
# not produce a flat 0.6-9.0 guide. Every scripted run recomputes the ramp per rig anyway.
set_depth_range(*depth_range(SHOTS[_first]))
blend_path = out_dir / "set_template.blend"
if not overrides_pinned():
    raise SystemExit("OVATTR: OV_Depth/OV_Normal missing or unpinned — they will be purged on save")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

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

# A linked prop is invisible to SIGHTLINE (ray_cast does not walk collection instances). Any set
# that instances a library prop needs this or its prop guard is silently absent.
_insts = [i for i in depsgraph.object_instances if i.is_instance]
if _insts:
    print("SIGHTLINE NOTE ray_cast ignores collection instances — linked props are not tested; "
          "LINKCHECK below is their guard")
for shot_id, cam in cams.items():
    for inst in _insts:
        p = inst.matrix_world.translation
        co = world_to_camera_view(scene, cam, p)
        ok = (0.0 <= co.x <= 1.0) and (0.0 <= co.y <= 1.0) and co.z > 0.0
        print(f"LINKCHECK {shot_id} {inst.object.name} uv=({co.x:.2f},{co.y:.2f}) in_frame={ok}")
else:
    print("LINKCHECK none — no collection instances in this set (that is correct for a scaffold)")

print(
    "TEMPLATE "
    f"guide_vt={GUIDE_VT} beauty_vt={BEAUTY_VT} res={width}x{height} samples={samples} "
    f"ctrl_radius={ctrl_radius} "
    f"collections={','.join(c.name for c in scene.collection.children)} "
    f"overrides=OV_Depth,OV_Normal rigs={len(SHOTS)}"
)

(out_dir / "set_template_cameras.json").write_text(
    json.dumps(
        {
            "set": "_template",
            "story": "laotang",
            "resolution": [width, height],
            "units": "metres",
            "guide_view_transform": GUIDE_VT,
            "beauty_view_transform": BEAUTY_VT,
            "ctrl_blur_radius": ctrl_radius,
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

if not ctrl_only:
    fx_objects = [o for o in C_FX.objects]
    vl = scene.view_layers[0]
    shot_ids = list(SHOTS) if shots_arg == "all" else [s for s in shots_arg.split(",") if s in SHOTS]

    for shot_id in shot_ids:
        scene.camera = cams[shot_id]

        for o in fx_objects:
            o.hide_render = False
        vl.material_override = None
        scene.view_settings.view_transform = BEAUTY_VT
        scene.render.film_transparent = False
        scene.render.filepath = str(out_dir / f"{shot_id}_beauty.png")
        bpy.ops.render.render(write_still=True)

        for o in fx_objects:
            o.hide_render = True

        scene.view_settings.view_transform = GUIDE_VT
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
        scene.view_settings.view_transform = BEAUTY_VT

    print("RENDERED", shot_ids)
else:
    for shot_id in SHOTS:
        write_depth_ctrl(out_dir / f"{shot_id}_depth.png", ctrl_radius)
        print(f"CTRL {shot_id} radius={ctrl_radius}")
    print("RENDERED [] ctrl-only")
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot-id", default="all", help="all, or a comma list: t000")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--ctrl-only", action="store_true", help="rebuild only the blurred control pass")
    ap.add_argument("--no-render", action="store_true", help="write the .blend and json, render nothing")
    args = ap.parse_args()

    blender = find_blender()
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = out_dir / "._template_build.py"
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
                "none" if args.no_render else args.shot_id,
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

    blend_path = out_dir / "set_template.blend"
    print(f"blender: {blender}")
    print(f"blend  : {blend_path} sha256={sha256_file(blend_path)}")
    for line in res.stdout.splitlines():
        if line.startswith(("SIGHTLINE", "DEPTH", "CTRL", "RENDERED", "TEMPLATE")):
            print(line)
    for p in sorted(out_dir.glob("*.png")):
        print(f"pass   : {p.name} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
