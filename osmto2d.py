import os
import numpy as np
import geopandas as gpd
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from matplotlib import pyplot as plt

def generate_2d_map(osm_file_path):
    """
    从 .osm 文件生成严格 256x256 像素的二值建筑图（白色建筑，黑色背景）
    假设 .osm 文件覆盖的地理范围正好用于生成 256x256 米区域（1米=1像素）
    """
    os.makedirs("./2D", exist_ok=True)
    base_name = os.path.basename(osm_file_path).replace('.osm', '')
    output_path = f"./2D/{base_name}.png"

    # 读取 multipolygons
    try:
        gdf = gpd.read_file(osm_file_path, layer='multipolygons')
    except Exception as e:
        print(f"❌ 无法读取 {osm_file_path} 的 'multipolygons' 图层。")
        raise e

    if gdf.empty:
        print(f"⚠️ 无数据，生成空白图: {output_path}")
        blank = np.zeros((256, 256), dtype=np.uint8)
        plt.imsave(output_path, blank, cmap='gray', vmin=0, vmax=1)
        return

    # 获取地理边界
    west, south, east, north = gdf.total_bounds

    # 创建 256x256 的变换矩阵（从地理坐标 → 像素坐标）
    transform = from_bounds(west, south, east, north, 256, 256)

    # 筛选建筑
    if 'building' in gdf.columns:
        buildings = gdf[gdf['building'].notnull()]
    else:
        buildings = gdf

    if buildings.empty:
        img = np.zeros((256, 256), dtype=np.uint8)
    else:
        shapes = [(geom, 1) for geom in buildings.geometry if geom is not None and not geom.is_empty]
        img = rasterize(
            shapes,
            out_shape=(256, 256),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )

    # 保存为 PNG
    plt.imsave(output_path, img, cmap='gray', vmin=0, vmax=1)
    print(f"✅ 已保存 256x256 图像: {output_path}")