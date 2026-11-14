"""Re-pose one prop inside an existing set and re-render its guide passes.

Why this exists: `s002c` asks for the yuanyang pot knocked over, but the depth guide is the
upright pot the set builder made, and the guide wins. The 13 Nov keyframe came back with the
pot still standing on its burner and the broth spilled around its base — a good image of the
wrong action. Depth controls silhouette, so a pose the guide does not contain cannot be
prompted into existence; the geometry has to change.

The set file is opened, never saved: this writes `_posed_` passes beside the originals so
`s002c`'s guide can be regenerated without invalidating `huoguo_set.blend` or its `blend1`.
Note that `huoguo_set.blend` carries no OV_Depth/OV_Normal — those datablocks had no users
when it was saved and were purged (the trap `blender_set_template.py` fixed with
use_fake_user), so the override material is rebuilt here on open.

Usage:
    python win/blender_pose_s002c.py
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SET_BLEND = REPO / "work" / "sets" / "huoguo" / "huoguo_set.blend"
SET_DIR = SET_BLEND.parent
CAMERAS = SET_DIR / "set_huoguo_cameras.json"
SHOT = "s002c"
SOURCE_SHOT = "s002"

BLENDER_SCRIPT = r'''
import json, math, sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
set_dir = Path(argv[0])
width, height, samples = int(argv[1]), int(argv[2]), int(argv[3])
shot, source_shot = argv[4], argv[5]

scene = bpy.context.scene
cameras = json.loads((set_dir / "set_huoguo_cameras.json").read_text(encoding="utf-8"))
spec = cameras["shots"][source_shot]
near, far = spec["depth_near_m"], spec["depth_far_m"]

# ---- render settings (mirrored from blender_set_huoguo.py so the guide matches the set) ----
scene.render.engine = "BLENDER_EEVEE"
for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items:
    if item.identifier == "BLENDER_EEVEE":
        scene.render.engine = item.identifier
        break
scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.film_transparent = False
scene.render.use_compositing = False
for attr, value in (("taa_render_samples", samples), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, attr, value)
    except Exception as exc:
        print(f"WARN eevee.{attr}: {exc}")
beauty_vt = scene.view_settings.view_transform
scene.camera = bpy.data.objects[f"CAM_{source_shot}"]

# ---- rebuild the depth override (purged from this file) ----
def build_depth_mat(near, far):
    m = bpy.data.materials.new("OV_Depth_Posed")
    m.use_fake_user = True
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    cd = nt.nodes.new("ShaderNodeCameraData")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = near
    mr.inputs["From Max"].default_value = far
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    mr.clamp = True
    nt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m

MAT_DEPTH = build_depth_mat(near, far)

# ---- pose: lay the pot on its side on the table, mouth toward camera ----
TABLE_X, TABLE_Y, TABLE_Z = 0.30, 0.50, 0.74
PARTS = ("Pot", "Pot_Rim", "Pot_Divider", "Pot_Handle_-1", "Pot_Handle_1")
GRANNY = ("Pot_Broth",)   # the broth plane is not visible once the pot is empty and over

parts = [bpy.data.objects[n] for n in PARTS if n in bpy.data.objects]
missing = [n for n in PARTS if n not in bpy.data.objects]
if missing:
    print("MISSING", missing)
for n in GRANNY:
    if n in bpy.data.objects:
        bpy.data.objects[n].hide_render = True

# Transform the parts directly rather than parenting them: one matrix per object is
# inspectable in the log, whereas a parent plus parent-inverse chain hides the arithmetic
# (the first attempt parented them and the pot silently left the frame).
pivot = Matrix.Translation((TABLE_X, TABLE_Y, TABLE_Z))
# 80 deg about world X tips the mouth toward -Y, which is where CAM_s002 sits.
R = Matrix.Rotation(math.radians(80.0), 4, "X")
M = pivot @ R @ pivot.inverted()
for ob in parts:
    ob.matrix_world = M @ ob.matrix_world
bpy.context.view_layer.update()


def world_bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    return lo, hi


lo, hi = world_bounds(parts)
print(f"POSE rotated lo=({lo.x:.3f},{lo.y:.3f},{lo.z:.3f}) hi=({hi.x:.3f},{hi.y:.3f},{hi.z:.3f})")

# Settle: rest the lowest point of the posed pot on the tabletop, then nudge it toward the
# camera so it is off its burner rather than balanced on it.
settle = Matrix.Translation((0.0, -0.10, (TABLE_Z + 0.003) - lo.z))
for ob in parts:
    ob.matrix_world = settle @ ob.matrix_world
bpy.context.view_layer.update()

lo, hi = world_bounds(parts)
print(f"POSE settled lo=({lo.x:.3f},{lo.y:.3f},{lo.z:.3f}) hi=({hi.x:.3f},{hi.y:.3f},{hi.z:.3f}) "
      f"tabletop={TABLE_Z:.3f}")

# A pose that leaves the frustum renders an empty table and looks like a guide bug, so say
# where the pot landed on screen instead of discovering it in the PNG.
mid = (lo + hi) / 2.0
ndc = world_to_camera_view(scene, scene.camera, mid)
print(f"POSE screen centre u={ndc.x:.2f} v={ndc.y:.2f} depth={ndc.z:.2f} "
      f"(inside frame = {0.0 <= ndc.x <= 1.0 and 0.0 <= ndc.y <= 1.0})")

# ---- passes ----
fx = [o for o in bpy.data.objects if o.name.startswith("Steam_")]
for o in fx:
    o.hide_render = False
scene.render.film_transparent = False
scene.render.filepath = str(set_dir / f"{shot}_posed_beauty.png")
bpy.ops.render.render(write_still=True)

for o in fx:
    o.hide_render = True
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = True
scene.render.image_settings.color_mode = "RGB"
vl = scene.view_layers[0]
vl.material_override = MAT_DEPTH
scene.render.filepath = str(set_dir / f"{shot}_posed_depth.png")
bpy.ops.render.render(write_still=True)

img = bpy.data.images.load(str(set_dir / f"{shot}_posed_depth.png"))
sd = float(np.array(img.pixels[:], dtype=np.float32).std())
bpy.data.images.remove(img)
print(f"DEPTHSTAT {shot} std={sd:.3f} {'OK' if sd > 0.06 else 'FLAT'}")

# ---- blurred control pass, same radius rule as the set (width/192 = 4 px at 768) ----
radius = max(1, round(width / 192))
src = set_dir / f"{shot}_posed_depth.png"
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
out = set_dir / f"{shot}_depth_ctrl.png"
res = bpy.data.images.new("ctrl", width=w, height=h, alpha=True)
res.pixels.foreach_set(a.ravel())
res.filepath_raw = str(out)
res.file_format = "PNG"
res.save()
print(f"CTRL {shot} radius={radius} -> {out.name}")

vl.material_override = None
scene.view_settings.view_transform = beauty_vt
print("POSE_DONE", shot)
'''


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_blender() -> Path:
    for cand in (
        Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"),
    ):
        if cand.exists():
            return cand
    raise SystemExit("blender.exe not found")


def main() -> int:
    width, height, samples = 768, 1344, 64
    runner = SET_DIR / "._pose_s002c_build.py"
    runner.write_text(BLENDER_SCRIPT, encoding="utf-8")

    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = str(REPO / "work" / ".btmp" / "config")
    env["BLENDER_USER_SCRIPTS"] = str(REPO / "work" / ".btmp" / "scripts")

    before = sha256_file(SET_BLEND)
    try:
        res = subprocess.run(
            [
                str(find_blender()),
                "-b",
                str(SET_BLEND),
                "--python-exit-code",
                "1",
                "--python",
                str(runner),
                "--",
                str(SET_DIR),
                str(width),
                str(height),
                str(samples),
                SHOT,
                SOURCE_SHOT,
            ],
            text=True,
            capture_output=True,
            env=env,
        )
    finally:
        runner.unlink(missing_ok=True)

    if res.returncode != 0:
        print(res.stdout[-4000:])
        print(res.stderr[-4000:], file=sys.stderr)
        return res.returncode

    after = sha256_file(SET_BLEND)
    print(f"set    : {SET_BLEND.name} sha256={after}")
    print(f"set    : {'UNCHANGED' if before == after else 'MODIFIED — this script must not save'}")
    for line in res.stdout.splitlines():
        if line.startswith(("POSE", "DEPTHSTAT", "CTRL", "MISSING", "WARN")):
            print(line)
    for name in (f"{SHOT}_posed_beauty.png", f"{SHOT}_posed_depth.png", f"{SHOT}_depth_ctrl.png"):
        p = SET_DIR / name
        if p.exists():
            print(f"pass   : {p.name} ({p.stat().st_size} bytes) sha256={sha256_file(p)[:16]}")
    return 0 if before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
