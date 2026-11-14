"""Shoot the `s002d` copper-pot insert without touching `huoguo_set.blend`.

Why a variant script and not a 13th rig: the shot list had `s002d` on the interior `s002` rig,
but at 82-88 s we are at the street stall, so the insert has to come from the stall. Adding that
camera to the set means rebuilding the file every rig move invalidates guides shot against, which
is exactly the fight nobody wins. So this opens the frozen set, links the library prop, builds its
camera in memory, renders, and exits — the set is never saved, and its `blend1` is untouched.

Two bugs from `blender_pose_s002c.py` are avoided deliberately, both copied as warnings:
  * do not parent posed parts to an empty and settle from the empty's matrix — the parent-inverse
    chain hid the arithmetic and put the pot outside the frustum;
  * `bound_box` corners are LOCAL — multiply by each object's own `matrix_world`, never a parent's,
    or the bounds are computed in the wrong space and the settle step moves the prop nowhere.

The pot here is not posed: it sits on the stall and the shot is an insert. What matters is that
the *library* geometry is what the depth pass sees, so the dent is real silhouette rather than a
prompt clause.

Usage:
    python win/blender_pose_s002d.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SET_BLEND = REPO / "work" / "sets" / "huoguo" / "huoguo_set.blend"
PROPS_BLEND = REPO / "work" / "props" / "props_laotang.blend"
SHOT = "s002d"

BLENDER_SCRIPT = r'''
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
set_dir, props_path, shot = Path(argv[0]), argv[1], argv[2]
width, height, samples = int(argv[3]), int(argv[4]), int(argv[5])

scene = bpy.context.scene

# ---- render settings mirrored from blender_set_huoguo.py so the guide matches the set ----
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.film_transparent = False
scene.render.use_compositing = False
scene.render.dither_intensity = 0.0
for attr, value in (("taa_render_samples", samples), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, attr, value)
    except Exception as exc:
        print(f"WARN eevee.{attr}: {exc}")
beauty_vt = scene.view_settings.view_transform

# ---- the stall, read from the set rather than hardcoded ----
stand_in = bpy.data.objects["Stall_Pot"]
pot = stand_in.matrix_world.translation.copy()
rim = bpy.data.objects.get("Stall_Pot_Rim")
print(f"STALL pot=({pot.x:.3f},{pot.y:.3f},{pot.z:.3f})")

# The clay stand-in must not sit inside the linked prop: hide it for this session only.
for name in ("Stall_Pot", "Stall_Pot_Rim"):
    ob = bpy.data.objects.get(name)
    if ob:
        ob.hide_render = True

# ---- link the library prop (never copy, never append) ----
PROP_COLLECTION = "Prop_Tongguo"
with bpy.data.libraries.load(props_path, link=True) as (data_from, data_to):
    # Exact name, never a substring: "Tongguo" also matches Prop_Tongguo_Lid, and linking the lid
    # rendered a plausible-looking insert with DEPTHSTAT std=0.000 and nobody noticed for a run.
    if PROP_COLLECTION not in data_from.collections:
        raise SystemExit(f"MISSING {PROP_COLLECTION} not in {props_path}: {list(data_from.collections)}")
    data_to.collections = [PROP_COLLECTION]
coll = data_to.collections[0]
print(f"LINK {coll.name} <- {Path(props_path).name}")
# A collection instance is an EMPTY carrying instance_type/instance_collection, not an object with
# collection data: bpy.data.objects.new(name, collection) raises "ID type 'COLLECTION' is not
# valid for an object".
inst = bpy.data.objects.new("LINK_Prop_Tongguo_s002d", None)
inst.instance_type = "COLLECTION"
inst.instance_collection = coll
scene.collection.objects.link(inst)
inst.location = pot
# A small yaw so the dent is not facing away from the lamp. The dent's azimuth is not recorded
# anywhere in the library, so this is a placement choice, not a measurement — confirm it on the
# beauty pass before the keyframe goes out.
inst.rotation_euler = (0.0, 0.0, math.radians(20.0))
bpy.context.view_layer.update()

# ---- camera: low, 0.60 m out, 45 mm ----
pivot = pot + Vector((0.0, 0.0, 0.02))
cam_loc = pot + Vector((0.0, -0.60, 0.07))
cam_data = bpy.data.cameras.new("CAM_s002d_data")
cam_data.lens = 45.0
cam = bpy.data.objects.new("CAM_s002d", cam_data)
scene.collection.objects.link(cam)
cam.location = cam_loc
direction = (pivot - cam_loc).normalized()
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
bpy.context.view_layer.update()

dist = (pivot - cam_loc).length
frame_w = 2 * dist * (18.0 / cam_data.lens)
print(f"CAM {shot} dist={dist:.2f} m lens={cam_data.lens:.0f} mm frame={frame_w:.2f}x{frame_w * height / width:.2f} m")

# ---- depth override, rebuilt because this file was saved without it ----
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

near = min(max(dist * 0.50, 0.35), 4.00)
far = near + max(dist * 1.60, 3.20)
MAT_DEPTH = build_depth_mat(near, far)

# An empty has no bound_box worth reading, so measure the instanced meshes instead: each mesh's
# LOCAL corners multiplied by its own matrix, then by the instance's — never by a parent's.
meshes = [o for o in coll.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("POSE the linked collection holds no meshes")
print(f"MESHES {[o.name for o in meshes]}")


def bounds():
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    for ob in meshes:
        m = inst.matrix_world @ ob.matrix_world
        for c in ob.bound_box:      # local corners, then the object's own matrix, then the instance
            w = m @ Vector(c)
            lo = Vector((min(lo[i], w[i]) for i in range(3)))
            hi = Vector((max(hi[i], w[i]) for i in range(3)))
    return lo, hi


lo, hi = bounds()
# The library pot's origin is not its base, so dropping it at the stand-in's centre left it
# floating above the stall. Rest the lowest point on the surface and re-measure.
STALL_TOP_Z = 0.740                # Stall_Top sits at z 0.72, 0.04 thick
print(f"POSE before settle lo.z={lo.z:.3f}")
inst.location.z += STALL_TOP_Z - lo.z
lo, hi = bounds()
mid = (lo + hi) / 2.0

# Frame from the measurement, not from a guess. The linked pot measured wider than the clay
# stand-in it replaces, so 45 mm at 0.60 m clipped it at both edges — a 0.535 m prop in a 0.48 m
# frame. Solve for distance from the measured span with 18% margin, then rebuild the ramp for the
# new distance so the depth guide is not graded for a camera that no longer exists.
span = max(hi.x - lo.x, hi.y - lo.y)
cam_data.lens = 50.0
d_star = span * 1.18 * cam_data.lens / (2 * 18.0)
frame_w = 2 * d_star * 18.0 / cam_data.lens
print(f"CAM refit span={span:.3f} m dist={d_star:.2f} m lens={cam_data.lens:.0f} mm "
      f"frame_w={frame_w:.2f} m fill={span / frame_w:.0%}")

# The stall has customers standing at it. The straight-ahead camera sat 0.075 m inside
# P_Buyer_Torso, so the guide was a flat near-plane and the pot was never in shot at all.
# A ray to the pot cannot hit it (ray_cast is blind to collection instances), so "clear" means
# nothing intercepts before the pot and whatever is beyond it is past the prop.
dg = bpy.context.evaluated_depsgraph_get()
chosen = None
for dz in (0.07, 0.17, 0.27, 0.37):
    for az_deg in (0, 12, -12, 24, -24, 36, -36, 48, -48, 60, -60, 72, -72, 84, -84):
        az = math.radians(az_deg)
        pos = pivot + Vector((math.sin(az) * d_star, -math.cos(az) * d_star, dz))
        to = pivot - pos
        dist = to.length
        h, hl, _n, _i, hob, _m = scene.ray_cast(dg, pos, to.normalized(), distance=6.0)
        hd = (hl - pos).length if h else -1.0
        # Hitting the clay stand-in is the line being clear: it sits exactly where the linked pot
        # goes and is hidden from render. hide_render does not remove it from the depsgraph that
        # ray_cast reads, so without this the test rejected the one usable angle.
        clear = (not h) or hob.name in ("Stall_Pot", "Stall_Pot_Rim") or hd > dist + 0.25
        print(f"LOS az={az_deg:+3d} dz={dz:.2f} hit={hob.name if h else None} at={hd:.2f} clear={clear}")
        if clear:
            chosen = (pos, az_deg, dz)
            break
    if chosen:
        break
if chosen is None:
    raise SystemExit("CAM no candidate position has a clear line to the pot")
cam.location, az_deg, dz = chosen
cam.rotation_euler = (pivot - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
print(f"CAM placed az={az_deg:+d} dz={dz:.2f} at ({cam.location.x:.2f},{cam.location.y:.2f},{cam.location.z:.2f})")

# The 1.18 margin assumed the pot's widest axis faces the camera. At az=+36 it does not, and the
# insert cropped at both edges. Fit on the projected corners instead of on an axis-aligned span.
for _ in range(8):
    bpy.context.view_layer.update()
    mx = my = 0.0
    for ob in meshes:
        m = inst.matrix_world @ ob.matrix_world
        for c in ob.bound_box:
            nd = world_to_camera_view(scene, cam, m @ Vector(c))
            mx = max(mx, abs(nd.x - 0.5))
            my = max(my, abs(nd.y - 0.5))
    if mx <= 0.38 and my <= 0.40:
        break
    k = max(mx / 0.38, my / 0.40) * 1.02
    d_star *= k
    cam.location = pivot + (cam.location - pivot).normalized() * d_star
print(f"CAM fit half_extent u={mx:.2f} v={my:.2f} dist={d_star:.2f} m")

near = min(max(d_star * 0.50, 0.35), 4.00)
far = near + max(d_star * 1.60, 3.20)
MAT_DEPTH = build_depth_mat(near, far)
print(f"RAMP {shot} near={near:.2f} far={far:.2f}")

ndc = world_to_camera_view(scene, cam, mid)
inside = 0.0 <= ndc.x <= 1.0 and 0.0 <= ndc.y <= 1.0 and ndc.z > 0.0
print(f"POSE pot lo=({lo.x:.3f},{lo.y:.3f},{lo.z:.3f}) hi=({hi.x:.3f},{hi.y:.3f},{hi.z:.3f}) "
      f"size=({hi.x - lo.x:.3f},{hi.y - lo.y:.3f},{hi.z - lo.z:.3f})")
print(f"POSE screen u={ndc.x:.2f} v={ndc.y:.2f} depth={ndc.z:.2f} inside={inside}")
if not inside:
    raise SystemExit("POSE the pot is not in frame — the guide would render an empty stall")

# A uniformly WHITE depth pass means the nearest surface is at the ramp's near plane everywhere.
# A missing instance renders as background, not as a flat near surface, so before blaming the link,
# ask what the camera is actually looking at. If this hits the stall table or the shutter at
# 0.1-0.2 m the camera is buried in geometry and the prop was never visible — same defect class as
# s009/s010, and a stripped repro would have found nothing because there was nothing to find.
dg = bpy.context.evaluated_depsgraph_get()
origin = cam.matrix_world.translation
fwd = (cam.matrix_world @ Vector((0.0, 0.0, -1.0))) - origin
hit, hloc, _hn, _hi, hob, _hm = scene.ray_cast(dg, origin, fwd.normalized(), distance=6.0)
print(f"FIRST_HIT {hob.name if hit else None} dist={(hloc - origin).length if hit else -1.0:.3f} m")

# ---- passes ----
fx = [o for o in bpy.data.objects if o.name.startswith("Steam_")]
for o in fx:
    o.hide_render = False
scene.render.filepath = str(set_dir / f"{shot}_beauty.png")
bpy.ops.render.render(write_still=True)

for o in fx:
    o.hide_render = True
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = True
vl = scene.view_layers[0]
vl.material_override = MAT_DEPTH
scene.render.filepath = str(set_dir / f"{shot}_depth.png")
bpy.ops.render.render(write_still=True)

img = bpy.data.images.load(str(set_dir / f"{shot}_depth.png"))
sd = float(np.array(img.pixels[:], dtype=np.float32).std())
bpy.data.images.remove(img)
print(f"DEPTHSTAT {shot} std={sd:.3f} {'OK' if sd > 0.06 else 'FLAT'}")
if sd <= 0.06:
    raise SystemExit("DEPTHSTAT FLAT — the insert rendered an empty frame, so the guide is unusable")

radius = max(1, round(width / 192))
src = set_dir / f"{shot}_depth.png"
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
    if not PROPS_BLEND.is_file():
        print(f"missing prop library: {PROPS_BLEND}", file=sys.stderr)
        return 2
    width, height, samples = 768, 1344, 64
    set_dir = SET_BLEND.parent
    runner = set_dir / "._pose_s002d_build.py"
    runner.write_text(BLENDER_SCRIPT, encoding="utf-8")

    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = str(REPO / "work" / ".btmp" / "config")
    env["BLENDER_USER_SCRIPTS"] = str(REPO / "work" / ".btmp" / "scripts")

    before = sha256_file(SET_BLEND)
    try:
        res = subprocess.run(
            [
                str(find_blender()), "-b", str(SET_BLEND), "--python-exit-code", "1",
                "--python", str(runner), "--",
                str(set_dir), str(PROPS_BLEND), SHOT,
                str(width), str(height), str(samples),
            ],
            text=True, capture_output=True, env=env,
        )
    finally:
        runner.unlink(missing_ok=True)

    if res.returncode != 0:
        print(res.stdout[-4000:])
        print(res.stderr[-4000:], file=sys.stderr)
        return res.returncode

    after = sha256_file(SET_BLEND)
    print(f"set    : {SET_BLEND.name} sha256={after[:16]}…")
    print(f"set    : {'UNCHANGED' if before == after else 'MODIFIED — this script must not save'}")
    for line in res.stdout.splitlines():
        if line.startswith(("STALL", "MESHES", "CAM", "RAMP", "FIRST_HIT", "POSE", "DEPTHSTAT", "CTRL", "MISSING", "WARN")):
            print(line)
    for name in (f"{SHOT}_beauty.png", f"{SHOT}_depth.png", f"{SHOT}_depth_ctrl.png"):
        p = set_dir / name
        if p.exists():
            print(f"pass   : {p.name} ({p.stat().st_size} bytes) sha256={sha256_file(p)[:16]}")
    return 0 if before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
