import os
import numpy as np
import osmium
from shapely.geometry import Polygon
from rasterio.transform import from_origin
from rasterio.features import rasterize
from matplotlib import pyplot as plt
from pathlib import Path


def generate_2d_map(
    osm_file_path=None,  # 默认为 None，表示批量处理目录
    output_dir="./2d",
    ground_z=-0.1,
    map_size=256.0
):
    """
    若 osm_file_path 为 None（默认）：自动处理 ./osm 目录下所有 .osm 文件。
    若 osm_file_path 为字符串：仅处理该 .osm 文件。
    其余参数含义不变。
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- 内部函数：处理单个文件 ---
    def _process_single_file(file_path):
        stem = Path(file_path).stem
        output_path = os.path.join(output_dir, f"{stem}.png")

        class LocalProjector:
            def __init__(self, origin_lat, origin_lon):
                self.origin_lat = origin_lat
                self.origin_lon = origin_lon
                self.scale = np.pi / 180 * 6378137

            def project(self, lat, lon):
                dx = (lon - self.origin_lon) * self.scale * np.cos(np.radians(self.origin_lat))
                dy = (lat - self.origin_lat) * self.scale
                return dx, dy

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
            finder.apply_file(file_path, locations=True)
        except Exception as e:
            print(f"⚠️ 读取 {file_path} 失败: {e}")
            return

        if finder.lat is None:
            print(f"❌ {file_path} 无有效坐标")
            return

        projector = LocalProjector(finder.lat, finder.lon)

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
                        pass

        extractor = BuildingExtractor(projector)
        try:
            extractor.apply_file(file_path, locations=True)
        except Exception as e:
            print(f"⚠️ 解析建筑失败 {file_path}: {e}")
            return

        if not extractor.polygons:
            print(f"ℹ️ {file_path} 无有效建筑")
            return

        all_x = [x for poly in extractor.polygons for x, y in poly.exterior.coords]
        all_y = [y for poly in extractor.polygons for x, y in poly.exterior.coords]
        x_min, y_min = min(all_x), min(all_y)

        translated_polygons = []
        for poly in extractor.polygons:
            translated = Polygon([(x - x_min, y - y_min) for x, y in poly.exterior.coords])
            if translated.is_valid and not translated.is_empty:
                translated_polygons.append(translated)

        if not translated_polygons:
            print(f"⚠️ 平移后无有效建筑: {file_path}")
            return

        transform = from_origin(west=0.0, north=map_size, xsize=1.0, ysize=1.0)
        shapes = [(poly, 1) for poly in translated_polygons]
        img = rasterize(
            shapes,
            out_shape=(int(map_size), int(map_size)),
            transform=transform,
            fill=0,
            dtype=np.uint8
        )
        plt.imsave(output_path, img, cmap='gray', vmin=0, vmax=1)
        print(f"✅ 已保存（或覆盖）图像: {output_path}")

    # --- 主逻辑：判断是批量还是单文件 ---
    if osm_file_path is None:
        # 批量模式
        osm_dir = Path("./osm")
        if not osm_dir.exists() or not any(osm_dir.glob("*.osm")):
            print("请创建 ./osm 文件夹并放入 .osm 文件")
            return
        for osm_file in osm_dir.glob("*.osm"):
            _process_single_file(str(osm_file))
    else:
        # 单文件模式
        _process_single_file(osm_file_path)