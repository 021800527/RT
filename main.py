import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import zoom
from PIL import Image
import sionna.rt as rt
from osmto2d import generate_2d_map
from RT import generate_radio_maps_from_xmls, get_scene_bounds

# ==============================
# 第一部分: osm文件转换成2D俯视图
# ==============================
osm_dir = Path("./osm")
if osm_dir.exists():
    for osm_file in osm_dir.glob("*.osm"):
        generate_2d_map(str(osm_file))
else:
    print("请创建 ./osm 文件夹并放入 .osm 文件")

generate_radio_maps_from_xmls()

# ==============================
# 第二部分：生成无线电地图（你的原始代码）
# ==============================
def config_scene(num_rows, num_cols):
    scene = rt.load_scene("Hongkong.xml")
    scene.bandwidth = 100e6

    scene.tx_array = rt.PlanarArray(
        num_rows=num_rows,
        num_cols=num_cols,
        pattern="tr38901",
        polarization="V"
    )

    scene.rx_array = rt.PlanarArray(
        num_rows=1,
        num_cols=1,
        pattern="iso",
        polarization="V"
    )

    positions = np.array([
        [-150.3, 21.63, 42.5],
        [-125.1, 9.58, 42.5],
        [-104.5, 54.94, 42.5],
        [-128.6, 66.73, 42.5],
        [172.1, 103.7, 24],
        [232.8, -95.5, 17],
        [80.1, 193.8, 21]
    ])
    look_ats = np.array([
        [-216, -21, 0],
        [-90, -80, 0],
        [-16.5, 75.8, 0],
        [-164, 153.7, 0],
        [247, 92, 0],
        [211, -180, 0],
        [126.3, 194.7, 0]
    ])
    power_dbms = [23] * 7

    for i, position in enumerate(positions):
        scene.add(rt.Transmitter(
            name=f'tx{i}',
            position=position,
            look_at=look_ats[i],
            power_dbm=power_dbms[i]
        ))
    return scene

# 配置并计算无线电地图
num_rows, num_cols = 8, 2
scene = config_scene(num_rows, num_cols)
rm_solver = rt.RadioMapSolver()
rm = rm_solver(
    scene,
    max_depth=5,
    samples_per_tx=10**7,
    cell_size=(1, 1)
)

print("RSS shape:", rm.rss.shape)  # 应为 (7, 440, 600)
print("Sample RSS value:", rm.rss[0][0][0])

# ==============================
# 第二部分：处理 RSS 并叠加到建筑图
# ==============================

# Step 1: 合并所有 Tx 的 RSS（线性相加）
total_rss_linear = np.sum(rm.rss, axis=0)  # shape: (440, 600)

# Step 2: 转换为 dBm（可选但推荐）
# P(dBm) = 10 * log10(P(W) / 1e-3)
total_rss_dbm = 10 * np.log10(total_rss_linear / 1e-3 + 1e-20)  # 避免除零

# Step 3: 加载你的建筑俯视图（请替换为你的实际路径）
building_img = Image.open("osmto2d.png").convert("L")  # 转为灰度图
building_array = np.array(building_img)  # shape: (H_bg, W_bg)，如 (2772, 2506)

H_bg, W_bg = building_array.shape
H_rss, W_rss = total_rss_dbm.shape  # (440, 600)

# Step 4: 将 RSS 图放大到建筑图尺寸（使用双三次插值）
scale_y = H_bg / H_rss  # 2772 / 440 ≈ 6.3
scale_x = W_bg / W_rss  # 2506 / 600 ≈ 4.177

rss_resized = zoom(total_rss_dbm, (scale_y, scale_x), order=3)

# 确保尺寸完全匹配（zoom 可能有 ±1 像素误差）
rss_resized = rss_resized[:H_bg, :W_bg]

# Step 5: 归一化 RSS 到 [0, 255]（信号强 → 白）
rss_norm = (rss_resized - rss_resized.min()) / (rss_resized.max() - rss_resized.min())
rss_gray = (rss_norm * 255).astype(np.uint8)

# Step 6: 叠加：信号图覆盖建筑图（信号区域变亮，其余保留建筑）
# 方法：信号图作为“前景”，建筑图为“背景”
final_image = np.maximum(rss_gray, building_array)  # 信号强的地方更亮

# 或者用加权混合（更柔和）：
# alpha = 0.6
# final_image = (alpha * rss_gray + (1 - alpha) * building_array).astype(np.uint8)

# Step 7: 保存结果
result_img = Image.fromarray(final_image)
result_img.save("rss_overlay_on_building.png")