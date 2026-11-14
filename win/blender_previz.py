#!/usr/bin/env python3
"""Build a 9:16 Blender 5.3 pre-viz scene (.blend) and render beauty + depth + normal passes.

Run directly with Python on Windows:
    python win/blender_previz.py --episode ep00_p3_previz --shot-id s001
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

BLENDER_EXE = Path(
    os.environ.get(
        "BLENDER_EXE",
        r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe",
    )
)

BLENDER_SCRIPT = r"""
import math
import sys
from pathlib import Path
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(argv[0])
shot_id = argv[1]
width = int(argv[2])
height = int(argv[3])
out_dir.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.frame_start = 1
scene.frame_end = 1
scene.frame_current = 1

# World ambient
world = bpy.data.worlds.new("NightAlley")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.04, 0.05, 0.08, 1.0)
    bg.inputs[1].default_value = 1.0

def make_mat(name, color, rough=0.6, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        if emit > 0 and "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emit
    return m

# Ground plane
bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "AlleyGround"
ground.data.materials.append(make_mat("WetPavement", (0.08, 0.09, 0.11), rough=0.2))

# Left & right alley walls
for name, x, col in (("WallLeft", -2.2, (0.18, 0.14, 0.13)), ("WallRight", 2.2, (0.15, 0.16, 0.18))):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 2.0, 2.5))
    w = bpy.context.active_object
    w.name = name
    w.scale = (0.4, 12.0, 5.0)
    w.data.materials.append(make_mat(name + "Mat", col, rough=0.85))

# Streetlamp post + glowing bulb
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=3.4, location=(-1.35, 1.2, 1.7))
post = bpy.context.active_object
post.name = "LampPost"
post.data.materials.append(make_mat("Iron", (0.05, 0.05, 0.06), rough=0.35))

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(-1.05, 1.2, 3.15))
bulb = bpy.context.active_object
bulb.name = "LampBulb"
bulb.data.materials.append(make_mat("WarmBulb", (1.0, 0.72, 0.35), rough=0.1, emit=8.0))

# Character proxy (1.68m standing figure blocking)
bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=1.35, location=(0.0, 0.0, 0.675))
body = bpy.context.active_object
body.name = "HeroProxy_Body"
body.data.materials.append(make_mat("NavyCoat", (0.06, 0.10, 0.22), rough=0.55))

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.125, location=(0.0, 0.0, 1.52))
head = bpy.context.active_object
head.name = "HeroProxy_Head"
head.data.materials.append(make_mat("SkinProxy", (0.78, 0.62, 0.54), rough=0.45))

# Key/rim lights
bpy.ops.object.light_add(type="POINT", location=(-1.0, 1.2, 3.0))
lamp = bpy.context.active_object
lamp.data.energy = 280.0
lamp.data.color = (1.0, 0.75, 0.45)

bpy.ops.object.light_add(type="AREA", location=(1.4, -1.8, 2.2))
fill = bpy.context.active_object
fill.data.energy = 80.0
fill.data.color = (0.55, 0.75, 1.0)
fill.rotation_euler = (math.radians(65), 0, math.radians(35))

# 9:16 vertical camera
bpy.ops.object.camera_add(location=(0.15, -3.1, 1.32))
cam = bpy.context.active_object
cam.name = "HeroCam_9x16"
cam.data.lens = 50.0
cam.data.sensor_width = 36.0
direction = bpy.data.objects["HeroProxy_Head"].location - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

# Enable Z + Normal passes and save beauty + depth + normal via compositor
vl = scene.view_layers[0]
vl.use_pass_z = True
vl.use_pass_normal = True

ng = bpy.data.node_groups.new("PrevizPasses", "CompositorNodeTree")
scene.compositing_node_group = ng
rl = ng.nodes.new("CompositorNodeRLayers")

norm = ng.nodes.new("CompositorNodeNormalize")
inv = ng.nodes.new("CompositorNodeInvert")
inv.inputs["Invert Color"].default_value = True
inv.inputs["Invert Alpha"].default_value = False

fo = ng.nodes.new("CompositorNodeOutputFile")
fo.directory = str(out_dir)
fo.file_name = ""
fo.format.media_type = "IMAGE"
fo.format.file_format = "PNG"
fo.format.color_mode = "RGB"
fo.file_output_items.clear()
fo.file_output_items.new("FLOAT", f"{shot_id}_depth")
fo.file_output_items.new("RGBA", f"{shot_id}_normal")

ng.links.new(rl.outputs["Depth"], norm.inputs["Value"])
ng.links.new(norm.outputs[0], inv.inputs["Color"])
ng.links.new(inv.outputs[0], fo.inputs[0])
ng.links.new(rl.outputs["Normal"], fo.inputs[1])

blend_path = out_dir / f"{shot_id}_previz.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

scene.render.filepath = str(out_dir / f"{shot_id}_beauty.png")
bpy.ops.render.render(write_still=True)

for pass_name in ("depth", "normal"):
    framed = out_dir / f"{shot_id}_{pass_name}0001.png"
    target = out_dir / f"{shot_id}_{pass_name}.png"
    if framed.is_file():
        framed.replace(target)
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", default="ep00_p3_previz")
    ap.add_argument("--shot-id", default="s001")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    if not BLENDER_EXE.is_file():
        sys.exit(f"Blender executable not found: {BLENDER_EXE}")

    out_dir = Path(args.out_dir) if args.out_dir else (Path(__file__).resolve().parent.parent / "work" / args.episode)
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = out_dir / f"._{args.shot_id}_blender_gen.py"
    runner.write_text(BLENDER_SCRIPT, encoding="utf-8")

    try:
        res = subprocess.run(
            [
                str(BLENDER_EXE),
                "-b",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(runner),
                "--",
                str(out_dir),
                args.shot_id,
                str(args.width),
                str(args.height),
            ],
            text=True,
            capture_output=True,
        )
    finally:
        runner.unlink(missing_ok=True)

    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        return res.returncode

    blend_path = out_dir / f"{args.shot_id}_previz.blend"
    print(f"blend: {blend_path} sha256={sha256_file(blend_path)}")
    for p in sorted(out_dir.glob(f"{args.shot_id}_*.png")):
        print(f"pass : {p} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
