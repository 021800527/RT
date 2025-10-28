import os
import numpy as np
import osmium
from shapely.geometry import Polygon
from rasterio.transform import from_origin
from rasterio.features import rasterize
from matplotlib import pyplot as plt
from pathlib import Path


def generate_2d_map(
    osm_file_path,
    output_dir="./2d",
    ground_z=-0.1,  # 保留参数（虽未使用，但保持接口一致）
    map_size=256.0  # 新增参数：物理尺寸（米），同时也是图像分辨率（像素）
):
    """
    从 .osm 文件生成 map_size × map_size 二值建筑图，
    **物理范围固定为 [0, map_size] × [0, map_size] 米**。
    - 坐标系统与 process_all_osm_files 完全一致（LocalProjector + 平移至左下角）
    - 超出范围的建筑部分会被裁剪（不缩放）
    - 不足区域自动填充 0
    - 始终覆盖已存在的 PNG 文件
    - 分辨率：1 米/像素 → 图像尺寸 = (map_size, map_size) 像素
    """
    os.makedirs(output_dir, exist_ok=True)
    stem = Path(osm_file_path).stem
    output_path = os.path.join(output_dir, f"{stem}.png")

    # --- 1. 投影类（与 process_all_osm_files 一致）---
    class LocalProjector:
        def __init__(self, origin_lat, origin_lon):
            self.origin_lat = origin_lat
            self.origin_lon = origin_lon
            self.scale = np.pi / 180 * 6378137  # WGS84 半径（米）

        def project(self, lat, lon):
            dx = (lon - self.origin_lon) * self.scale * np.cos(np.radians(self.origin_lat))
            dy = (lat - self.origin_lat) * self.scale
            return dx, dy

    # --- 2. 找第一个有效节点作为原点 ---
    class RefPointFinder(osmium.SimpleHandler):
        def __init__(self):
            self.lat = None
            self.lon = None

        def node(self, n):
            if self.lat is None and n.location.valid():
                self.lat = n.lat
                self.lon = n.lon

    finder = RefPointFinder()
    try:
        finder.apply_file(osm_file_path, locations=True)
    except Exception as e:
        print(f"⚠️ 读取 {osm_file_path} 失败: {e}")
        return

    if finder.lat is None:
        print(f"❌ {osm_file_path} 无有效坐标")
        return

    projector = LocalProjector(finder.lat, finder.lon)

    # --- 3. 提取建筑多边形（米制，未平移）---
    class BuildingExtractor(osmium.SimpleHandler):
        def __init__(self, projector):
            super().__init__()
            self.projector = projector
            self.polygons = []

        def way(self, w):
            if 'building' not in w.tags or not w.is_closed():
                return
            coords = []
            for n in w.nodes:
                if n.location.valid():
                    x, y = self.projector.project(n.lat, n.lon)
                    coords.append((x, y))
            if len(coords) >= 3:
                try:
                    poly = Polygon(coords)
                    if poly.is_valid and not poly.is_empty:
                        self.polygons.append(poly)
                except Exception:
                    pass  # 无效多边形跳过

    extractor = BuildingExtractor(projector)
    try:
        extractor.apply_file(osm_file_path, locations=True)
    except Exception as e:
        print(f"⚠️ 解析建筑失败 {osm_file_path}: {e}")
        return

    if not extractor.polygons:
        print(f"ℹ️ {osm_file_path} 无有效建筑")
        return

    # --- 4. 平移：使整体左下角为 (0, 0) ---
    all_x = [x for poly in extractor.polygons for x, y in poly.exterior.coords]
    all_y = [y for poly in extractor.polygons for x, y in poly.exterior.coords]
    x_min, y_min = min(all_x), min(all_y)

    translated_polygons = []
    for poly in extractor.polygons:
        translated = Polygon([(x - x_min, y - y_min) for x, y in poly.exterior.coords])
        if translated.is_valid and not translated.is_empty:
            translated_polygons.append(translated)

    if not translated_polygons:
        print(f"⚠️ 平移后无有效建筑: {osm_file_path}")
        return

    # --- 5. 栅格化到 [0, map_size] × [0, map_size] 米，1 米/像素 ---
    # Rasterio: transform 定义图像左上角地理坐标（north = map_size, west = 0）
    transform = from_origin(
        west=0.0,
        north=map_size,   # 图像顶部 y = map_size
        xsize=1.0,        # 像素宽度（米）
        ysize=1.0         # 像素高度（米）
    )

    shapes = [(poly, 1) for poly in translated_polygons]
    img = rasterize(
        shapes,
        out_shape=(int(map_size), int(map_size)),  # (height, width) = (map_size, map_size)
        transform=transform,
        fill=0,
        dtype=np.uint8
    )

    # 保存为灰度图（0=背景，1=建筑）
    plt.imsave(output_path, img, cmap='gray', vmin=0, vmax=1)
    print(f"✅ 已保存（或覆盖）图像: {output_path}")