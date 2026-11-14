"""Re-render a set rig's depth and control passes with a ramp that fits the subject.

Why this exists: `depth_range()` in `blender_set_huoguo.py` sizes the ramp from the *camera
distance* — `near = 0.6·d`, `far = near + max(1.6·d, 3.2)`. That is right for a wide shot, where
the background is the point, and wrong for a close-up, where the subject is a 20 cm ellipsoid one
metre away and everything else in frame is behind it.

Measured, not guessed, on `s010` (85 mm, subject at 1.06 m):

    ramp 0.58-3.78      head front 1.061, head back 1.171  ->  6 of 255 levels
    ramp 1.04-1.41      head front 0.954, head back 0.653  -> 76 of 255 levels

Six levels is a silhouette: a flat white disc on black. A depth ControlNet given a disc renders
the disc's outline as an object, which is where the wooden hoop around 苏念's head and the wire
across 顾衍's chest came from — the model explaining an edge it could not otherwise explain.

So the script measures first: it ray-casts a grid through the frame, groups the hits by object
prefix, and takes the largest group — the character — as the subject. The ramp is then sized so the
character spans ~30 % of the range and the near background keeps the rest. The rule is

    near = z_lo - 0.15·(z_hi - z_lo)
    far  = near + (z_hi - z_lo) / 0.30

with z_lo/z_hi the 2nd/98th percentile of the subject's depth. For a wide rig the same formula
degrades gracefully into something close to the builder's own numbers, but it is meant for CUs.

The set file is opened, never saved: the sha256 is asserted unchanged and the script exits non-zero
if it is not. Output is `<shot>_ranged_depth.png` / `<shot>_ranged_depth_ctrl.png`, so the canonical
passes stay byte-identical and the two can be compared side by side.

It prints two checks. `DEPTHSTAT std` is the builder's check and cannot catch this defect — a white
blob on a black background has a healthy standard deviation. `SUBJSTAT` is the spread of values
*inside the subject silhouette*, which is the check that matters; 40/255 is the floor.

Usage:
    python win/blender_depth_rerange.py --shots s009,s010
    python win/blender_depth_rerange.py --shots s010 --span-frac 0.4   # flatter, more background
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SET_BLEND = REPO / "work" / "sets" / "huoguo" / "huoguo_set.blend"
SET_DIR = SET_BLEND.parent

BLENDER_SCRIPT = r'''
import json, math, sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
set_dir = Path(argv[0])
width, height, samples = int(argv[1]), int(argv[2]), int(argv[3])
shots = argv[4].split(",")
span_frac, pad_frac = float(argv[5]), float(argv[6])

scene = bpy.context.scene
cams_json = json.loads((set_dir / "set_huoguo_cameras.json").read_text(encoding="utf-8"))

scene.render.engine = "BLENDER_EEVEE"
for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items:
    if item.identifier == "BLENDER_EEVEE":
        scene.render.engine = item.identifier
        break
scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
# RGBA, because the subject mask has to come from alpha: with an RGB save the empty pixels come
# back as alpha 1.0 and every "inside the silhouette" statistic silently measures the whole frame.
scene.render.image_settings.color_mode = "RGBA"
scene.render.use_compositing = False
for attr, value in (("taa_render_samples", samples), ("use_raytracing", True)):
    try:
        setattr(scene.eevee, attr, value)
    except Exception as exc:
        print(f"WARN eevee.{attr}: {exc}")
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = True

# The saved set carries no OV_Depth (zero users at save time, purged), so build it here.
def build_depth_mat(near, far):
    for old in [m for m in bpy.data.materials if m.name.startswith("OV_Depth_Ranged")]:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new("OV_Depth_Ranged")
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

# Steam is bevelled curves: surface, not structure, so the builder hides it for depth passes.
# The saved file has it visible, and a steam wisp crossing the face would grade as geometry.
fx_coll = bpy.data.collections.get("FX_Steam")
if fx_coll:
    for o in fx_coll.objects:
        o.hide_render = True

vl = scene.view_layers[0]
radius = max(1, round(width / 192))


def render_depth(path, mat):
    vl.material_override = mat
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a, w, h


def keep_two(name):
    parts = name.split("_")
    return "_".join(parts[:2]) if len(parts) > 1 else parts[0]


def measure_subject(cam, grid=24):
    """Ray-cast a grid through the frame and report the depth span of what dominates it.

    A rendered percentile over the whole frame is useless here: on `s010` the foreground table
    sits at 0.45 m and the shelf at 1.62 m, so a 2-98 % band spans 1.2 m of scene and the head is
    lost inside it — the first attempt widened the ramp to 7.8 m and made the guide flatter than
    the one it was replacing. Grouping the hits by object-name prefix and taking the largest group
    measures the character, which is what the ramp has to hug.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    origin = cam.matrix_world.translation
    tr, br, bl, tl = (cam.matrix_world @ p for p in cam.data.view_frame(scene=scene))
    groups = {}
    for i in range(grid):
        for j in range(grid):
            u, v = (i + 0.5) / grid, (j + 0.5) / grid
            p = tl.lerp(tr, u).lerp(bl.lerp(br, u), 1.0 - v)
            hit, loc, _nrm, _idx, ob, _mat = scene.ray_cast(dg, origin, (p - origin).normalized())
            if hit:
                groups.setdefault(keep_two(ob.name), []).append((loc - origin).length)
    if not groups:
        return None, [], []
    name, dists = max(groups.items(), key=lambda kv: len(kv[1]))
    z = np.array(sorted(dists))
    return name, float(np.percentile(z, 2)), float(np.percentile(z, 98))


for shot in shots:
    spec = cams_json["shots"][shot]
    cam = bpy.data.objects[f"CAM_{shot}"]
    scene.camera = cam
    d_cam = math.dist(spec["loc"], spec["target"])

    # ---- measure the subject's own depth span, then size the ramp to it ----------------------
    subject, z_lo, z_hi = measure_subject(cam)
    if subject is None:
        print(f"MEASURE {shot} EMPTY — nothing under the camera, refusing to write a guide")
        continue
    depth_extent = max(z_hi - z_lo, 1e-4)

    near = round(max(z_lo - pad_frac * depth_extent, 0.05), 4)
    far = round(near + depth_extent / span_frac, 4)
    # How much of the ramp the subject itself will occupy, which is the number that matters.
    subj_levels = (1.0 - (z_hi - near) / (far - near)) * 255
    print(f"MEASURE {shot} subject={subject} z={z_lo:.3f}..{z_hi:.3f} "
          f"({depth_extent * 100:.1f} cm, camera d={d_cam:.2f} m)")
    print(f"RAMP  {shot} near={near:.3f} far={far:.3f} width={far - near:.3f} "
          f"(builder had {spec['depth_near_m']:.2f}-{spec['depth_far_m']:.2f})")
    print(f"CHRSTAT {shot} {subject} occupies {subj_levels:.0f}/255 levels "
          f"{'OK' if subj_levels > 40 else 'TOO FLAT'}")

    # ---- the real pass ----------------------------------------------------------------------
    depth_path = set_dir / f"{shot}_ranged_depth.png"
    a, w, h = render_depth(depth_path, build_depth_mat(near, far))
    al = a[:, :, 3]
    v = a[:, :, 0]
    subj_mask = al > 0.5
    bg_mask = al <= 0.5
    subj = v[subj_mask]

    sd = float(v.std())
    p05, p50, p95 = (float(np.percentile(subj, q)) for q in (5, 50, 95))
    spread = p95 - p05
    levels = spread * 255
    bg_levels = float(np.percentile(v[bg_mask], 98) - np.percentile(v[bg_mask], 2)) * 255 if bg_mask.any() else 0.0
    print(f"DEPTHSTAT {shot} std={sd:.3f} {'OK' if sd > 0.06 else 'FLAT'}")
    print(f"SUBJSTAT  {shot} cover={subj_mask.mean():.3f} p05={p05:.3f} p50={p50:.3f} p95={p95:.3f} "
          f"spread={spread:.3f} ({levels:.0f}/255 levels) {'OK' if levels > 40 else 'TOO FLAT'}")
    print(f"BGSTAT    {shot} cover={bg_mask.mean():.3f} spread={bg_levels:.0f}/255 levels "
          f"{'OK' if bg_levels > 15 else 'CRUSHED'}")

    # ---- blurred control pass, same radius rule as the set -----------------------------------
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
    out = set_dir / f"{shot}_ranged_depth_ctrl.png"
    res = bpy.data.images.new("ctrl", width=w, height=h, alpha=True)
    res.pixels.foreach_set(a.ravel())
    res.filepath_raw = str(out)
    res.file_format = "PNG"
    res.save()
    bpy.data.images.remove(res)
    print(f"CTRL {shot} radius={radius} -> {out.name}")

vl.material_override = None
print("RERANGE_DONE", shots)
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
    ap.add_argument("--shots", required=True, help="comma list, e.g. s009,s010")
    ap.add_argument("--span-frac", type=float, default=0.30,
                    help="share of the ramp the subject's own depth may occupy (0.3 = 76 levels)")
    ap.add_argument("--pad-frac", type=float, default=0.15,
                    help="ramp left in front of the nearest subject point")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()

    runner = SET_DIR / "._depth_rerange.py"
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
                str(args.width),
                str(args.height),
                str(args.samples),
                args.shots,
                str(args.span_frac),
                str(args.pad_frac),
            ],
            text=True,
            capture_output=True,
            env=env,
        )
    finally:
        runner.unlink(missing_ok=True)

    if res.returncode != 0:
        print(res.stdout[-4000:])
        print(res.stderr[-4000:], file=__import__("sys").stderr)
        return res.returncode

    after = sha256_file(SET_BLEND)
    print(f"set    : {SET_BLEND.name} sha256={after}")
    print(f"set    : {'UNCHANGED' if before == after else 'MODIFIED — this script must not save'}")
    for line in res.stdout.splitlines():
        if line.startswith(("MEASURE", "RAMP", "CHRSTAT", "DEPTHSTAT", "SUBJSTAT", "BGSTAT", "CTRL", "WARN")):
            print(line)
    for shot in args.shots.split(","):
        for suffix in ("_ranged_depth.png", "_ranged_depth_ctrl.png"):
            p = SET_DIR / f"{shot}{suffix}"
            if p.exists():
                print(f"pass   : {p.name} ({p.stat().st_size} bytes)")
    return 0 if before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
