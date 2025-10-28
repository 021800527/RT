import os
import glob
import osmium
import numpy as np
import trimesh
from shapely.geometry import Polygon, box


def process_all_osm_files(
        osm_dir="./osm",
        output_xml_dir="./xml",
        output_meshes_dir=None,
        default_height=20.0,
        floor_height=3.0,
        ground_z=-0.1,
        map_size=256.0
):
    """
    批量处理指定目录下所有 .osm 文件，生成建筑网格、地面和 Mitsuba XML 场景。
    所有建筑在平移后会被裁剪到 [0, map_size] × [0, map_size] 米范围内。

    参数:
        osm_dir (str): 包含 .osm 文件的目录路径（默认 "./osm"）
        output_xml_dir (str): 输出 XML 文件的目录（默认 "./xml"）
        output_meshes_dir (str): 输出 PLY 文件的目录（默认为 "{output_xml_dir}/meshes"）
        default_height (float): 默认建筑高度（米）
        floor_height (float): 每层楼高度（用于 building:levels）
        ground_margin (float): 【保留但不再使用】
        ground_z (float): 地面 Z 坐标（通常略低于 0）
        map_size (float): 场景物理尺寸（米），正方形区域 [0, map_size] × [0, map_size]

    返回:
        None
    """
    if output_meshes_dir is None:
        output_meshes_dir = os.path.join(output_xml_dir, "meshes")

    os.makedirs(output_xml_dir, exist_ok=True)
    os.makedirs(output_meshes_dir, exist_ok=True)

    # 投影类
    class LocalProjector:
        def __init__(self, origin_lat, origin_lon):
            self.origin_lat = origin_lat
            self.origin_lon = origin_lon
            self.scale = np.pi / 180 * 6378137  # WGS84 地球半径（米）

        def project(self, lat, lon):
            dx = (lon - self.origin_lon) * self.scale * np.cos(np.radians(self.origin_lat))
            dy = (lat - self.origin_lat) * self.scale
            return dx, dy

    def parse_height(tags):
        """从 OSM 标签中解析建筑高度"""
        if 'height' in tags:
            try:
                h = float(tags['height'])
                if h > 0:
                    return h
            except (ValueError, TypeError):
                pass
        if 'building:levels' in tags:
            try:
                levels = float(tags['building:levels'])
                if levels > 0:
                    return levels * floor_height
            except (ValueError, TypeError):
                pass
        return default_height

    def polygon_to_mesh(vertices_2d, height):
        """将二维多边形拉伸为三维建筑网格"""
        verts = np.array(vertices_2d)
        if len(verts) < 3:
            return None
        bottom = np.hstack([verts, np.zeros((len(verts), 1))])
        top = np.hstack([verts, np.full((len(verts), 1), height)])
        vertices = np.vstack([bottom, top])
        N = len(verts)
        faces = []
        # 底面（逆时针）
        for i in range(1, N - 1):
            faces.append([0, i + 1, i])
        # 顶面（顺时针以保持法向朝上）
        for i in range(1, N - 1):
            faces.append([N, N + i, N + i + 1])
        # 侧面
        for i in range(N):
            j = (i + 1) % N
            faces += [[i, j, N + j], [i, N + j, N + i]]
        return trimesh.Trimesh(vertices=vertices, faces=faces)

    class BuildingHandler(osmium.SimpleHandler):
        def __init__(self, projector):
            super().__init__()
            self.projector = projector
            self.buildings = []

        def way(self, w):
            if 'building' not in w.tags or not w.is_closed():
                return
            coords_latlon = []
            for n in w.nodes:
                if n.location.valid():
                    coords_latlon.append((n.lat, n.lon))
            if len(coords_latlon) < 3:
                return
            coords_2d = [self.projector.project(lat, lon) for lat, lon in coords_latlon]
            height = parse_height(w.tags)
            self.buildings.append((coords_2d, height))

    def process_single_file(input_osm_path):
        print(f"\n🔧 正在处理: {input_osm_path}")

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
            finder.apply_file(input_osm_path, locations=True)
        except Exception as e:
            print(f"读取文件失败 {input_osm_path}: {e}")
            return

        if finder.lat is None:
            print(f"文件中无有效地理坐标: {input_osm_path}")
            return

        projector = LocalProjector(finder.lat, finder.lon)
        handler = BuildingHandler(projector)
        try:
            handler.apply_file(input_osm_path, locations=True)
        except Exception as e:
            print(f"解析建筑数据出错 {input_osm_path}: {e}")
            return

        if not handler.buildings:
            print(f"未找到任何建筑: {input_osm_path}")
            return

        basename = os.path.splitext(os.path.basename(input_osm_path))[0]
        building_filename = f"{basename}_buildings.ply"
        ground_filename = f"{basename}_ground.ply"
        xml_filename = f"{basename}.xml"

        # === 平移：使最左下角为 (0, 0) ===
        all_x = [x for verts, _ in handler.buildings for x, _ in verts]
        all_y = [y for verts, _ in handler.buildings for _, y in verts]
        x_min, y_min = min(all_x), min(all_y)

        translated_buildings = []
        for verts, height in handler.buildings:
            translated_verts = [(x - x_min, y - y_min) for x, y in verts]
            translated_buildings.append((translated_verts, height))

        # === 裁剪到 [0, map_size] × [0, map_size] 米 ===
        clip_window = box(0.0, 0.0, map_size, map_size)
        clipped_buildings = []

        for verts, height in translated_buildings:
            try:
                poly = Polygon(verts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty:
                    continue

                clipped = poly.intersection(clip_window)
                if clipped.is_empty:
                    continue

                if clipped.geom_type == 'Polygon':
                    coords = list(clipped.exterior.coords)[:-1]
                    if len(coords) >= 3:
                        clipped_buildings.append((coords, height))
                elif clipped.geom_type == 'MultiPolygon':
                    for part in clipped.geoms:
                        if not part.is_empty and part.geom_type == 'Polygon':
                            coords = list(part.exterior.coords)[:-1]
                            if len(coords) >= 3:
                                clipped_buildings.append((coords, height))
            except Exception as e:
                print(f"裁剪建筑时出错: {e}")
                continue

        if not clipped_buildings:
            print(f"裁剪后无有效建筑: {input_osm_path}")
            return

        # === 生成 3D 网格（仅裁剪后部分）===
        meshes = [polygon_to_mesh(v, h) for v, h in clipped_buildings]
        meshes = [m for m in meshes if m is not None]
        if not meshes:
            print(f"无法生成有效建筑网格: {input_osm_path}")
            return

        combined = trimesh.util.concatenate(meshes)
        building_path = os.path.join(output_meshes_dir, building_filename)
        combined.export(building_path)

        # === 固定地面：map_size × map_size 米 ===
        plane_verts = np.array([
            [0.0,       0.0,       ground_z],
            [map_size,  0.0,       ground_z],
            [map_size,  map_size,  ground_z],
            [0.0,       map_size,  ground_z]
        ])
        plane_faces = [[0, 1, 2], [0, 2, 3]]
        plane_mesh = trimesh.Trimesh(vertices=plane_verts, faces=plane_faces)
        ground_path = os.path.join(output_meshes_dir, ground_filename)
        plane_mesh.export(ground_path)

        # === Mitsuba XML 场景文件 ===
        xml_content = f'''<scene version="2.1.0">

<!-- Materials -->
	<bsdf type="twosided" id="mat-itu_concrete" name="mat-itu_concrete">
		<bsdf type="diffuse" name="bsdf">
			<rgb value="0.800000 0.800000 0.800000" name="reflectance"/>
		</bsdf>
	</bsdf>
	<bsdf type="twosided" id="mat-itu_brick" name="mat-itu_brick">
		<bsdf type="diffuse" name="bsdf">
			<rgb value="0.073800 0.073800 0.073800" name="reflectance"/>
		</bsdf>
	</bsdf>

<!-- Geometry -->
	<shape type="ply" id="elm__2" name="elm__2">
		<string name="filename" value="meshes/{ground_filename}"/>
		<boolean name="face_normals" value="true"/>
		<ref id="mat-itu_concrete" name="bsdf"/>
	</shape>
	<shape type="ply" id="elm__4" name="elm__4">
		<string name="filename" value="meshes/{building_filename}"/>
		<boolean name="face_normals" value="true"/>
		<ref id="mat-itu_concrete" name="bsdf"/>
	</shape>

</scene>'''
        xml_path = os.path.join(output_xml_dir, xml_filename)
        with open(xml_path, 'w') as f:
            f.write(xml_content)

        print(f"处理成功: {basename}")
        print(f"建筑网格: {building_path}")
        print(f"地面网格: {ground_path}")
        print(f"场景 XML: {xml_path}")

    # === 主流程 ===
    osm_files = glob.glob(os.path.join(osm_dir, "*.osm"))
    if not osm_files:
        print(f"在目录 {osm_dir} 中未找到 .osm 文件")
        return

    print(f"在 {osm_dir} 中找到 {len(osm_files)} 个 .osm 文件")
    for osm_file in sorted(osm_files):
        process_single_file(osm_file)

    print(f"\n全部完成！XML 文件位于: {output_xml_dir}，网格文件位于: {output_meshes_dir}")