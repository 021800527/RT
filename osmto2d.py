import geopandas as gpd
import matplotlib.pyplot as plt
import fiona
from shapely.geometry import Polygon, MultiPolygon

# 读取 OSM 文件（geopandas 可直接读 .osm）
# 注意：geopandas 通过 fiona 调用 OSM 驱动，仅读取 "multipolygons" 和 "lines" 等图层
try:
    # 尝试读取 buildings（OSM 中建筑通常在 multipolygons 图层）
    gdf = gpd.read_file("Hongkong.osm", layer='multipolygons')
except Exception as e:
    print("尝试读取 multipolygons 失败，尝试其他图层...")
    # 列出所有图层
    layers = fiona.listlayers("Hongkong.osm")
    print("可用图层:", layers)
    raise e

# 筛选建筑：OSM 中建筑通常有 building=* 标签
if 'building' in gdf.columns:
    buildings = gdf[gdf['building'].notnull()]
else:
    print("警告：未找到 'building' 列，可能需要手动检查属性")
    buildings = gdf  # 或根据其他字段过滤

# 如果没有建筑，提前退出
if buildings.empty:
    raise ValueError("未找到任何建筑！请确认 OSM 文件包含 building=* 的要素")

# 只保留 geometry（多边形）
buildings = buildings[['geometry']]

# 绘图
fig, ax = plt.subplots(figsize=(12, 12))

# 绘制建筑边界（白色线条）
buildings.boundary.plot(
    ax=ax,
    color='white',
    linewidth=2.0  # 可调粗细
)

# 设置黑色背景
ax.set_facecolor('black')

# 去掉坐标轴
ax.set_axis_off()

# 保存为高分辨率 PNG（无白边）
plt.savefig(
    "osmto2d.png",
    dpi=300,
    bbox_inches='tight',
    pad_inches=0,
    facecolor='black'
)

print("✅ 已保存: osmto2d.png")