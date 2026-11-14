"""Render a guide from a camera placement that the saved set does not contain.

`nextblender.md` owns the set and will eventually re-rig `s011` and `s012` in the builder. Until it
does, this renders a *variant* guide from a moved camera, and the set file is never saved — the
sha256 is asserted unchanged and the script exits non-zero if it is not. Output is
`<shot>_retargeted_depth.png` / `_retargeted_depth_ctrl.png`; the new placement is appended to
`work/sets/huoguo/retargets.json` so the numbers can be pasted into `SHOTS` later.

Why not just prompt it: the depth guide decides where the subject is and how big. `s011`'s camera
sits 3.07 m back with a 35 mm lens, which is a 5.5 m tall frame — a standing person is one sixth of
the height, and at that size the keyframe model does not paint a person. It painted a laboratory
still instead. No wording recovers a subject the guide made unreadable.

Two ramp modes:

    builder  near = 0.6·d, far = near + max(1.6·d, 3.2)    — correct for a shot where the room matters
    hug      near/far fit the subject's own depth span      — correct for a close-up

Usage:
    python win/blender_retarget_rig.py --shot s011 --loc 0.30,3.95,1.30 --target 0.30,1.23,1.10 --lens 55
    python win/blender_retarget_rig.py --shot s012 --target 0.90,-3.45,1.30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SET_BLEND = REPO / "work" / "sets" / "huoguo" / "huoguo_set.blend"
SET_DIR = SET_BLEND.parent
RETARGETS = SET_DIR / "retargets.json"

BLENDER_SCRIPT = r'''
import json, math, sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
set_dir = Path(argv[0])
width, height, samples = int(argv[1]), int(argv[2]), int(argv[3])
shot, mode = argv[4], argv[5]
loc = [float(x) for x in argv[6].split(",")]
target = [float(x) for x in argv[7].split(",")]
lens = float(argv[8])
subject_filter = argv[9] if len(argv) > 9 else ""
hide_patterns = [p for p in (argv[10].split(",") if len(argv) > 10 else []) if p]

scene = bpy.context.scene
cam = bpy.data.objects.get(f"CAM_{shot}")
if cam is None:
    # A shot can legitimately have no rig yet (`s002d` is a prop insert the builder never had a
    # camera for). Creating one in memory is the same deal as moving one: nothing is saved.
    data = bpy.data.cameras.new(f"CAM_{shot}")
    cam = bpy.data.objects.new(f"CAM_{shot}", data)
    scene.collection.objects.link(cam)
    before = sorted(o.name for o in bpy.data.objects)
    print(f"RIG   {shot} created — no camera existed in the set")
cam.location = loc
cam.rotation_mode = "QUATERNION"
cam.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")
cam.data.lens = lens
scene.camera = cam
d = (Vector(target) - Vector(loc)).length

# Hidden before anything is measured: a curtain strand or a steam wisp is surface, not structure,
# and on a depth pass it becomes a bright line the keyframe model paints as a cable or a wire.
fx_coll = bpy.data.collections.get("FX_Steam")
if fx_coll:
    for o in fx_coll.objects:
        o.hide_render = True
for pattern in hide_patterns:
    for o in bpy.data.objects:
        if pattern in o.name:
            o.hide_render = True
            print(f"HIDE  {o.name}")

near, far = 0.6 * d, 0.6 * d + max(1.6 * d, 3.2)
if mode == "hug":
    dg = bpy.context.evaluated_depsgraph_get()
    origin = cam.matrix_world.translation
    tr, br, bl, tl = (cam.matrix_world @ p for p in cam.data.view_frame(scene=scene))
    groups = {}
    for i in range(24):
        for j in range(24):
            u, v = (i + 0.5) / 24, (j + 0.5) / 24
            p = tl.lerp(tr, u).lerp(bl.lerp(br, u), 1.0 - v)
            hit, hp, _n, _i, ob, _m = scene.ray_cast(dg, origin, (p - origin).normalized())
            if hit:
                key = "_".join(ob.name.split("_")[:2])
                groups.setdefault(key, []).append((hp - origin).length)
    if groups:
        if subject_filter:
            # "Largest group in frame" is the right default for a person and the wrong one for a
            # prop insert, where the hero object is small and the wall behind it is not.
            groups = {k: v for k, v in groups.items() if subject_filter in k}
        if not groups:
            print(f"MEASURE {shot} no hits matching {subject_filter}")
        else:
            key, dists = max(groups.items(), key=lambda kv: len(kv[1]))
            z = np.array(sorted(dists))
            z_lo, z_hi = (float(np.percentile(z, q)) for q in (2, 98))
            near = max(z_lo - 0.15 * (z_hi - z_lo), 0.05)
            far = near + max(z_hi - z_lo, 1e-4) / 0.30
            print(f"MEASURE {shot} subject={key} z={z_lo:.3f}..{z_hi:.3f}")

print(f"RIG   {shot} loc={loc} target={target} lens={lens:.0f} d={d:.2f}")
print(f"RAMP  {shot} near={near:.3f} far={far:.3f} frame_h@d={d * 63.0 / lens:.2f} m")

scene.render.engine = "BLENDER_EEVEE"
for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items:
    if item.identifier == "BLENDER_EEVEE":
        scene.render.engine = item.identifier
        break
scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.use_compositing = False
for attr, value in (("taa_render_samples", samples), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, attr, value)
    except Exception as exc:
        print(f"WARN eevee.{attr}: {exc}")
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = True

fx_coll = bpy.data.collections.get("FX_Steam")
if fx_coll:
    for o in fx_coll.objects:
        o.hide_render = True

def build_depth_mat(near, far):
    for old in [m for m in bpy.data.materials if m.name.startswith("OV_Depth_Retarget")]:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new("OV_Depth_Retarget")
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

vl = scene.view_layers[0]
vl.material_override = build_depth_mat(near, far)
depth_path = set_dir / f"{shot}_retargeted_depth.png"
scene.render.filepath = str(depth_path)
bpy.ops.render.render(write_still=True)

img = bpy.data.images.load(str(depth_path))
w, h = img.size
a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
bpy.data.images.remove(img)
subj = a[:, :, 0][a[:, :, 3] > 0.5]
p05, p50, p95 = (float(np.percentile(subj, q)) for q in (5, 50, 95)) if subj.size else (0, 0, 0)
print(f"DEPTHSTAT {shot} std={a[:, :, 0].std():.3f} cover={(a[:, :, 3] > 0.5).mean():.3f}")
print(f"SUBJSTAT  {shot} p05={p05:.3f} p50={p50:.3f} p95={p95:.3f} "
      f"spread={(p95 - p05) * 255:.0f}/255 levels")

radius = max(1, round(width / 192))
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
a[:, :, 3] = 1.0
out = set_dir / f"{shot}_retargeted_depth_ctrl.png"
res = bpy.data.images.new("ctrl", width=w, height=h, alpha=True)
res.pixels.foreach_set(a.ravel())
res.filepath_raw = str(out)
res.file_format = "PNG"
res.save()
bpy.data.images.remove(res)
print(f"CTRL {shot} radius={radius} -> {out.name}")

vl.material_override = None
print("RETARGET_DONE", shot, json.dumps({"loc": loc, "target": target, "lens": lens,
      "depth_near_m": round(near, 3), "depth_far_m": round(far, 3), "mode": mode}))
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--loc", default="", help="x,y,z — omit to keep the set's placement")
    ap.add_argument("--target", default="", help="x,y,z")
    ap.add_argument("--lens", type=float, default=0.0, help="omit to keep the set's lens")
    ap.add_argument("--ramp", choices=("builder", "hug"), default="builder")
    ap.add_argument("--subject", default="", help="object-name substring for the hug ramp, e.g. Stall_Pot")
    ap.add_argument("--hide", default="", help="comma list of object-name substrings hidden for the depth pass")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()

    cams = json.loads((SET_DIR / "set_huoguo_cameras.json").read_text(encoding="utf-8"))
    spec = cams["shots"].get(args.shot, {})
    if not spec and not args.loc:
        raise SystemExit(f"{args.shot} has no camera in the set and no --loc was given")
    loc = args.loc or ",".join(str(v) for v in spec["loc"])
    target = args.target or ",".join(str(v) for v in spec["target"])
    lens = args.lens or spec.get("lens_mm", 50.0)

    runner = SET_DIR / "._retarget.py"
    runner.write_text(BLENDER_SCRIPT, encoding="utf-8")
    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = str(REPO / "work" / ".btmp" / "config")
    env["BLENDER_USER_SCRIPTS"] = str(REPO / "work" / ".btmp" / "scripts")

    before = sha256_file(SET_BLEND)
    try:
        res = subprocess.run(
            [str(find_blender()), "-b", str(SET_BLEND), "--python-exit-code", "1",
             "--python", str(runner), "--", str(SET_DIR), str(args.width), str(args.height),
             str(args.samples), args.shot, args.ramp, loc, target, str(lens), args.subject, args.hide],
            text=True, capture_output=True, env=env,
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

    record = {}
    for line in res.stdout.splitlines():
        if line.startswith(("RIG", "RAMP", "MEASURE", "DEPTHSTAT", "SUBJSTAT", "CTRL", "WARN")):
            print(line)
        if line.startswith("RETARGET_DONE"):
            record = json.loads(line.split(" ", 2)[2])

    if record:
        data = json.loads(RETARGETS.read_text(encoding="utf-8")) if RETARGETS.exists() else {}
        data[args.shot] = record
        RETARGETS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"sidecar: {RETARGETS.name} <- {args.shot}")

    for name in (f"{args.shot}_retargeted_depth.png", f"{args.shot}_retargeted_depth_ctrl.png"):
        p = SET_DIR / name
        if p.exists():
            print(f"pass   : {p.name} ({p.stat().st_size} bytes)")
    return 0 if before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
