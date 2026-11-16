"""
《对账》试播集 · Blender 灰模预演生成器 (blockout / previs)
=============================================================
用途: 前期灰模预演、虚拟勘景、断电两态光位与机位验证。
      不产生任何成片三维镜头 —— 对应工业包 §七「三维镜头数上限 = 0」。

运行:  blender -b -P 对账_blender_blockout_v1.py
输出:  同目录下 对账_blockout_v01.blend

注意: 尺寸为行业通用占位 (24m x 12m 单层)，美术拿到实测场地后须按实尺寸重排。
      模型不得出现院名、标识、药名、单据字段等可读信息（合规约束，见清单 §四）。
      本机未安装 Blender，脚本未运行验证；首次执行请确认无报错。

Blender 版本: 4.x
资源库口径: 2026-09 | 文档版本: v1 | 日期: 2026-11-15
"""

import os
import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "对账_blockout_v01.blend")

FLOOR_W, FLOOR_D, WALL_H = 24.0, 12.0, 3.0
CORRIDOR_W = 2.4

GREY = (0.55, 0.55, 0.55, 1.0)
COLD_WHITE = (1.0, 1.0, 1.0)          # 常态顶灯
EMERGENCY_GREEN = (0.35, 1.0, 0.55)   # 断电应急灯（低位冷青）

# (collection, x0, x1, y0, y1)  走廊居中于 y=0，房间分列两侧
ROOMS = [
    ("S02_NurseStation", -10.0, -4.0,   1.2,  5.6),
    ("S03_Pantry",        -3.5, -0.5,   1.2,  4.0),
    ("S06_Pharmacy",       0.5,  5.5,   1.2,  5.0),
    ("S04_AdminOffice",    6.5, 11.5,   1.2,  5.0),
    ("S05_SwitchRoom",    -6.0, -3.0,  -4.2, -1.2),
]

# (name, location, target, note)  机位号与场次号对应
CAMERAS = [
    ("CAM_S01_coldopen",   (-11.0, 0.0, 1.65), (2.0, 0.0, 1.4),   "冷开场 · 走廊断电"),
    ("CAM_S04_ledgers",    ( -7.0, 3.4, 1.70), (-7.0, 2.4, 0.9),  "第一幕 · 三本账摆上桌"),
    ("CAM_S22_pantry",     ( -2.0, 2.6, 1.55), (-2.0, 3.2, 0.95), "第22场 · 茶水间留白戏"),
    ("CAM_S37_admin",      (  9.0, 3.1, 1.60), ( 9.0, 3.6, 0.85), "第37场 · 删掉那行附注"),
    ("CAM_S31_switchroom", ( -4.5,-2.7, 1.65), (-4.5,-3.4, 1.0),  "第三幕 · 三线唯一合流"),
]

# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def new_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def add_box(col, name, loc, size):
    """单位立方体 -> 指定尺寸，scale 归一，移入目标 collection。"""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    ob.color = GREY
    return ob


def add_area_light(col, name, loc, energy, color, size=(1.2, 1.2), target=None):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.color = color
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    ob = bpy.data.objects.new(name, data)
    col.objects.link(ob)
    ob.location = loc
    if target:
        ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    return ob


def add_camera(col, name, loc, target):
    data = bpy.data.cameras.new(name)
    data.lens = 35
    ob = bpy.data.objects.new(name, data)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    ob["previs_note"] = "占位机位，非成片镜头参数"
    return ob


# ----------------------------------------------------------------------------
# SCENE SETUP
# ----------------------------------------------------------------------------
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.users == 0:
        bpy.data.collections.remove(c)

scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
# EEVEE 引擎标识在 Blender 4.2 前后不同，做兼容回退
for engine_id in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = engine_id
        break
    except TypeError:
        continue
scene.world.color = (0.05, 0.05, 0.05)

floor = new_collection("S00_Floorplan")
corridor = new_collection("S01_Corridor")
light_normal = new_collection("LIGHT_NORMAL")
light_blackout = new_collection("LIGHT_BLACKOUT")
cam_col = new_collection("CAM_PREVIS")
room_cols = {name: new_collection(name) for name, *_ in ROOMS}

# 楼板 / 走廊地面
add_box(floor, "FLOOR_slab", (0, 0, -0.10), (FLOOR_W, FLOOR_D, 0.20))
add_box(corridor, "CORRIDOR_floor", (0, 0, 0.01), (FLOOR_W, CORRIDOR_W, 0.02))

# 走廊两侧墙（留门洞：用分段代替整墙，保证连拍动线可读）
for side in (-1, 1):
    y = side * CORRIDOR_W / 2
    for i in range(6):
        x = -10.0 + i * 4.0
        add_box(corridor, "CORRIDOR_wall_%s_%02d" % ("N" if side > 0 else "S", i),
                (x, y, WALL_H / 2), (2.6, 0.12, WALL_H))

# 各房间：地板 + 三面墙（靠走廊一侧留洞）
for name, x0, x1, y0, y1 in ROOMS:
    col = room_cols[name]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    tag = name.split("_", 1)[0]
    add_box(col, "%s_floor" % tag, (cx, cy, 0.01), (w, d, 0.02))
    add_box(col, "%s_wall_back" % tag, (cx, y1 if cy > 0 else y0, WALL_H / 2), (w, 0.12, WALL_H))
    add_box(col, "%s_wall_left" % tag, (x0, cy, WALL_H / 2), (0.12, d, WALL_H))
    add_box(col, "%s_wall_right" % tag, (x1, cy, WALL_H / 2), (0.12, d, WALL_H))

# 关键物件占位（纯灰体量，不含任何可读信息）
add_box(room_cols["S02_NurseStation"], "NS_counter", (-7.0, 2.6, 0.55), (3.2, 0.9, 1.1))
add_box(room_cols["S02_NurseStation"], "NS_ledger_table", (-7.0, 3.8, 0.75), (2.0, 1.0, 0.05))
add_box(room_cols["S03_Pantry"], "PANTRY_counter", (-2.0, 3.3, 0.90), (1.8, 0.7, 0.06))
add_box(room_cols["S03_Pantry"], "PANTRY_chair", (-2.9, 2.4, 0.45), (0.5, 0.5, 0.9))
add_box(room_cols["S04_AdminOffice"], "ADMIN_desk", (9.0, 3.6, 0.75), (2.4, 1.1, 0.06))
add_box(room_cols["S05_SwitchRoom"], "SWITCH_cabinet", (-4.5, -4.0, 1.10), (2.2, 0.6, 2.2))
add_box(room_cols["S06_Pharmacy"], "PHARM_shelf", (3.0, 4.6, 1.10), (4.0, 0.5, 2.2))

# ----------------------------------------------------------------------------
# 两态灯光：常态冷白顶灯 / 断电低位冷青应急灯
# ----------------------------------------------------------------------------
for i in range(5):
    x = -9.0 + i * 4.5
    add_area_light(light_normal, "NORMAL_ceil_%02d" % i, (x, 0, 2.85), 320,
                   COLD_WHITE, size=(1.6, 0.5))
for name, x0, x1, y0, y1 in ROOMS:
    tag = name.split("_", 1)[0]
    add_area_light(light_normal, "NORMAL_%s" % tag,
                   ((x0 + x1) / 2, (y0 + y1) / 2, 2.85), 260, COLD_WHITE, size=(1.2, 1.2))

for i in range(6):
    x = -10.0 + i * 4.0
    add_area_light(light_blackout, "OUT_emergency_%02d" % i, (x, 0.9, 0.35), 45,
                   EMERGENCY_GREEN, size=(0.35, 0.18), target=(x, 0, 1.2))
add_area_light(light_blackout, "OUT_corridor_end", (11.6, 0, 0.45), 70,
               EMERGENCY_GREEN, size=(0.5, 0.3), target=(0, 0, 1.2))
add_area_light(light_blackout, "OUT_nurse_residual", (-7.0, 3.0, 1.1), 30,
               EMERGENCY_GREEN, size=(0.4, 0.2), target=(-7.0, 3.8, 0.9))
add_area_light(light_blackout, "OUT_admin_desk", (9.0, 3.2, 1.25), 22,
               (1.0, 0.72, 0.42), size=(0.3, 0.3), target=(9.0, 3.6, 0.8))
add_area_light(light_blackout, "OUT_switchroom", (-4.5, -2.2, 0.55), 35,
               EMERGENCY_GREEN, size=(0.4, 0.2), target=(-4.5, -4.0, 1.2))

# 默认查看断电态；切到常态时互换两组 hide_render / hide_viewport
for ob in light_normal.objects:
    ob.hide_render = True
    ob.hide_viewport = True
for ob in light_blackout.objects:
    ob.hide_render = False
    ob.hide_viewport = False

# ----------------------------------------------------------------------------
# 机位占位
# ----------------------------------------------------------------------------
for name, loc, target, note in CAMERAS:
    ob = add_camera(cam_col, name, loc, target)
    ob["previs_note"] = note

# ----------------------------------------------------------------------------
# SAVE
# ----------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=OUT_FILE)

print("=" * 62)
print("《对账》blockout 生成完成")
print("输出:", OUT_FILE)
print("Collections:", [c.name for c in scene.collection.children])
print("灯态: LIGHT_BLACKOUT 可见 / LIGHT_NORMAL 隐藏（两态互换 hide_render 即可）")
print("机位:", [c[0] for c in CAMERAS])
print("提醒: 尺寸为占位，须按实测场地重排；模型不得含任何可读信息。")
print("=" * 62)
