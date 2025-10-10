# radio_map_from_xml.py
import matplotlib.pyplot as plt
from sionna.rt import load_scene, RadioMapSolver

# 1. 加载 XML 场景（必须是 Mitsuba 3 格式）
scene = load_scene("Hongkong.xml")

# 2. 可视化场景几何（可选：确认加载成功）
scene.show()  # 弹出交互式 3D 查看器（需要支持 GUI）

# 3. 创建 RadioMapSolver
solver = RadioMapSolver(scene)

# 4. 计算 Radio Map（路径损耗图）
#    假设在 z=1.5 米高度，覆盖 40m x 40m 区域，分辨率 0.5m
radio_map = solver(
    center=[0, 0, 1.5],
    size=[40, 40],
    cell_size=[0.5, 0.5],
    num_samples=1e6,
    max_depth=8
)

# 5. 绘图
plt.figure(figsize=(8, 6))
im = plt.imshow(
    radio_map.path_loss.numpy(),
    origin="lower",
    extent=[-20, 20, -20, 20],
    cmap="viridis_r"
)
plt.colorbar(im, label="Path Loss [dB]")
plt.xlabel("X [m]")
plt.ylabel("Y [m]")
plt.title("Radio Map from scene.xml")
plt.tight_layout()
plt.show()