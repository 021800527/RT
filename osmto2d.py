import os
import numpy as np
import geopandas as gpd
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from matplotlib import pyplot as plt
from pathlib import Path

def generate_2d_map(osm_file_path, output_dir="./2d"):
    """
    从 .osm 文件生成 256x256 二值建筑图。
    - PNG 文件名与 OSM 文件名一致（如 0000.osm → 0000.png）
    - **始终覆盖已存在的 PNG 文件**
    - 假设输入 .osm 已通过有效性筛选（含建筑）
    """
    os.makedirs(output_dir, exist_ok=True)

    stem = Path(osm_file_path).stem
    output_path = os.path.join(output_dir, f"{stem}.png")

    try:
        gdf = gpd.read_file(osm_file_path, layer='multipolygons')
        buildings = gdf[gdf['building'].notnull()] if 'building' in gdf.columns else gdf
        if buildings.empty:
            print(f"⚠️ 警告: {osm_file_path} 无建筑，跳过生成")
            return

        west, south, east, north = buildings.total_bounds
        if west >= east or south >= north:
            raise ValueError("无效地理边界")

        transform = from_bounds(west, south, east, north, 256, 256)
        shapes = [(geom, 1) for geom in buildings.geometry if geom and not geom.is_empty]
        if not shapes:
            raise ValueError("无有效几何图形")

        img = rasterize(
            shapes,
            out_shape=(256, 256),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )
        plt.imsave(output_path, img, cmap='gray', vmin=0, vmax=1)
        print(f"✅ 已保存（或覆盖）图像: {output_path}")

    except Exception as e:
        print(f"⚠️ 处理 {osm_file_path} 时出错: {e}")
        return