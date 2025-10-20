import os
import glob
import osmium
import numpy as np
import trimesh


# ----------------------------
# 核心处理函数（可被外部调用）
# ----------------------------
def process_all_osm_files(
        osm_dir="./osm",
        output_xml_dir="./xml",
        output_meshes_dir=None,
        default_height=20.0,
        floor_height=3.0,
        ground_margin=10.0,
        ground_z=-0.1
):
    """
    批量处理指定目录下所有 .osm 文件，生成建筑网格、地面和 Mitsuba XML 场景。

    参数:
        osm_dir (str): 包含 .osm 文件的目录路径（默认 "./osm"）
        output_xml_dir (str): 输出 XML 文件的目录（默认 "./xml"）
        output_meshes_dir (str): 输出 PLY 文件的目录（默认为 "{output_xml_dir}/meshes"）
        default_height (float): 默认建筑高度（米）
        floor_height (float): 每层楼高度（用于 building:levels）
        ground_margin (float): 地面平面在建筑包围盒基础上外扩的边距（米，默认 20.0）
        ground_z (float): 地面 Z 坐标（通常略低于 0）

    返回:
        None
    """
    if output_meshes_dir is None:
        output_meshes_dir = os.path.join(output_xml_dir, "meshes")

    os.makedirs(output_xml_dir, exist_ok=True)
    os.makedirs(output_meshes_dir, exist_ok=True)

    # 投影类（局部定义，避免污染全局）
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
        verts = np.array(vertices_2d)
        if len(verts) < 3:
            return None
        bottom = np.hstack([verts, np.zeros((len(verts), 1))])
        top = np.hstack([verts, np.full((len(verts), 1), height)])
        vertices = np.vstack([bottom, top])
        N = len(verts)
        faces = []
        # Bottom cap
        for i in range(1, N - 1):
            faces.append([0, i + 1, i])
        # Top cap
        for i in range(1, N - 1):
            faces.append([N, N + i, N + i + 1])
        # Side walls
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
        print(f"\n🔧 Processing: {input_osm_path}")

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
            print(f"⚠️  Failed to read {input_osm_path}: {e}")
            return

        if finder.lat is None:
            print(f"❌ No valid location in {input_osm_path}")
            return

        projector = LocalProjector(finder.lat, finder.lon)
        handler = BuildingHandler(projector)
        try:
            handler.apply_file(input_osm_path, locations=True)
        except Exception as e:
            print(f"⚠️  Error parsing buildings in {input_osm_path}: {e}")
            return

        if not handler.buildings:
            print(f"ℹ️  No buildings found in {input_osm_path}")
            return

        basename = os.path.splitext(os.path.basename(input_osm_path))[0]
        building_filename = f"{basename}_buildings.ply"
        ground_filename = f"{basename}_ground.ply"
        xml_filename = f"{basename}.xml"

        # === 建筑网格 ===
        meshes = [polygon_to_mesh(v, h) for v, h in handler.buildings]
        meshes = [m for m in meshes if m is not None]
        if not meshes:
            print(f"⚠️  No valid meshes from {input_osm_path}")
            return

        combined = trimesh.util.concatenate(meshes)
        building_path = os.path.join(output_meshes_dir, building_filename)
        combined.export(building_path)

        # === 地面网格：自动适配建筑范围 + 外扩 margin ===
        all_x = [x for verts, _ in handler.buildings for x, _ in verts]
        all_y = [y for verts, _ in handler.buildings for _, y in verts]

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        # 外扩边距（单位：米）
        margin = ground_margin

        min_x -= margin
        max_x += margin
        min_y -= margin
        max_y += margin

        # 构建地面四顶点（逆时针，确保法向朝上）
        plane_verts = np.array([
            [min_x, min_y, ground_z],
            [max_x, min_y, ground_z],
            [max_x, max_y, ground_z],
            [min_x, max_y, ground_z]
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

<!-- Shapes -->
	<shape type="ply" id="elm__2" name="elm__2">
		<string name="filename" value="meshes/{ground_filename}"/>
		<boolean name="face_normals" value="true"/>
		<ref id="mat-itu_concrete" name="bsdf"/>
	</shape>
	<shape type="ply" id="elm__4" name="elm__4">
		<string name="filename" value="meshes/{building_filename}"/>
		<boolean name="face_normals" value="true"/>
		<ref id="mat-itu_brick" name="bsdf"/>
	</shape>

</scene>'''
        xml_path = os.path.join(output_xml_dir, xml_filename)
        with open(xml_path, 'w') as f:
            f.write(xml_content)

        print(f"✅ Success: {basename}")
        print(f"   🏢 Buildings: {building_path}")
        print(f"   🌍 Ground:    {ground_path}")
        print(f"   📄 Scene XML: {xml_path}")

    # === 主流程 ===
    osm_files = glob.glob(os.path.join(osm_dir, "*.osm"))
    if not osm_files:
        print(f"❌ No .osm files found in {osm_dir}")
        return

    print(f"📁 Found {len(osm_files)} .osm files in {osm_dir}")
    for osm_file in sorted(osm_files):
        process_single_file(osm_file)

    print(f"\n🎉 All done! XMLs in: {output_xml_dir}, Meshes in: {output_meshes_dir}")