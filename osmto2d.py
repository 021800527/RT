import os
import numpy as np
import geopandas as gpd
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from matplotlib import pyplot as plt

def generate_2d_map(osm_file_path, output_dir="./2d"):
    """
    从 .osm 文件生成 256x256 二值建筑图。
    - 每次 Python 进程首次调用时，从 0001.png 开始编号
    - 后续调用自动递增
    - 不删除 .osm 文件
    - 忽略 output_dir 中已存在的 PNG（视为全新任务）
    """
    os.makedirs(output_dir, exist_ok=True)

    # 使用函数属性模拟静态变量：首次调用时初始化为 1
    if not hasattr(generate_2d_map, '_counter'):
        generate_2d_map._counter = 1  # 从 0001 开始！

    current_index = generate_2d_map._counter
    output_path = os.path.join(output_dir, f"{current_index:04d}.png")

    # 读取 OSM
    try:
        gdf = gpd.read_file(osm_file_path, layer='multipolygons')
    except Exception as e:
        print(f"❌ 无法读取 {osm_file_path}: {e}")
        return

    if gdf.empty:
        print(f"⚠️ {osm_file_path} 无数据，跳过")
        return

    buildings = gdf[gdf['building'].notnull()] if 'building' in gdf.columns else gdf
    if buildings.empty:
        print(f"⚠️ {osm_file_path} 无建筑，跳过")
        return

    try:
        west, south, east, north = buildings.total_bounds
        if west >= east or south >= north:
            raise ValueError("边界无效")

        transform = from_bounds(west, south, east, north, 256, 256)
        shapes = [(geom, 1) for geom in buildings.geometry if geom and not geom.is_empty]
        if not shapes:
            raise ValueError("无有效几何")

        img = rasterize(
            shapes,
            out_shape=(256, 256),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )
        plt.imsave(output_path, img, cmap='gray', vmin=0, vmax=1)
        print(f"✅ 已保存 256x256 图像: {output_path}")

        # 成功后递增计数器（仅成功才计数！）
        generate_2d_map._counter += 1

    except Exception as e:
        print(f"⚠️ 处理 {osm_file_path} 出错: {e}")
        return