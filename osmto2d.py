import geopandas as gpd
import matplotlib.pyplot as plt
import fiona
import os

def generate_2d_map(osm_file_path):
    """
    从指定的 OSM 文件生成二维建筑地图，并保存为 PNG 图片。

    参数:
    - osm_file_path: 字符串，OSM 文件的路径。
    """
    # 提取文件名（不包含扩展名）作为输出文件名的基础
    output_filename = os.path.splitext(os.path.basename(osm_file_path))[0]

    try:
        # 尝试读取 buildings（OSM 中建筑通常在 multipolygons 图层）
        gdf = gpd.read_file(osm_file_path, layer='multipolygons')
    except Exception as e:
        print("尝试读取 multipolygons 失败，尝试其他图层...")
        # 列出所有图层
        layers = fiona.listlayers(osm_file_path)
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

    # 保存为高分辨率 PNG（无白边），文件名为 "文件名.png"
    output_path = "{}.png".format(output_filename)
    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches='tight',
        pad_inches=0,
        facecolor='black'
    )

    print(f"✅ 已保存: {output_path}")

# 示例调用：
# generate_2d_map("xxx/yyy.osm") 会生成 yyy.png