import os
import osmium
import numpy as np
import trimesh
from pyproj import Transformer

# ----------------------------
# 配置
# ----------------------------
INPUT_OSM = "./osm/demo.osm"  # ← 替换为你的 .osm 文件路径
OUTPUT_DIR = "./osm/meshes"
SCENE_XML = "./osm/demo.xml"

DEFAULT_HEIGHT = 20.0      # 默认高度（米）
FLOOR_HEIGHT = 3.0         # 每层楼高（用于 building:levels）
GROUND_SIZE = 300.0
GROUND_Z = -0.1

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------
# 投影工具：WGS84 → 平面坐标（使用局部 ENU 近似）
# ----------------------------
class LocalProjector:
    def __init__(self, origin_lat, origin_lon):
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        # 使用简单 equirectangular 投影（适用于小区域）
        self.scale = np.pi / 180 * 6378137  # Earth radius in meters

    def project(self, lat, lon):
        dx = (lon - self.origin_lon) * self.scale * np.cos(np.radians(self.origin_lat))
        dy = (lat - self.origin_lat) * self.scale
        return dx, dy

# ----------------------------
# 从 OSM 标签解析建筑高度
# ----------------------------
def parse_height(tags):
    # 1. 优先使用 height
    if 'height' in tags:
        try:
            h = float(tags['height'])
            if h > 0:
                return h
        except ValueError:
            pass
    # 2. 尝试 building:levels
    if 'building:levels' in tags:
        try:
            levels = float(tags['building:levels'])
            if levels > 0:
                return levels * FLOOR_HEIGHT
        except ValueError:
            pass
    # 3. 默认
    return DEFAULT_HEIGHT

# ----------------------------
# 将 2D 多边形拉伸为 3D 网格
# ----------------------------
def polygon_to_mesh(vertices_2d, height):
    verts = np.array(vertices_2d)
    if len(verts) < 3:
        return None

    # 底面 (z=0) 和顶面 (z=height)
    bottom = np.hstack([verts, np.zeros((len(verts), 1))])
    top    = np.hstack([verts, np.full((len(verts), 1), height)])

    vertices = np.vstack([bottom, top])
    N = len(verts)
    faces = []

    # 底面（反向，确保法向朝外）
    for i in range(1, N - 1):
        faces.append([0, i + 1, i])
    # 顶面
    for i in range(1, N - 1):
        faces.append([N, N + i, N + i + 1])
    # 侧面
    for i in range(N):
        j = (i + 1) % N
        faces += [[i, j, N + j], [i, N + j, N + i]]

    return trimesh.Trimesh(vertices=vertices, faces=faces)

# ----------------------------
# OSM 建筑处理器
# ----------------------------
class BuildingHandler(osmium.SimpleHandler):
    def __init__(self, projector):
        super().__init__()
        self.projector = projector
        self.buildings = []  # 每项: (vertices_2d, height)

    def way(self, w):
        if 'building' not in w.tags:
            return
        if not w.is_closed():
            return

        # 安全读取节点坐标
        coords_latlon = []
        for n in w.nodes:
            if n.location.valid():
                coords_latlon.append((n.lat, n.lon))
        if len(coords_latlon) < 3:
            return

        # 转为局部平面坐标
        coords_2d = [self.projector.project(lat, lon) for lat, lon in coords_latlon]
        height = parse_height(w.tags)
        self.buildings.append((coords_2d, height))

# ----------------------------
# 主流程
# ----------------------------
def main():
    # 1. 找一个参考点（用于投影）
    class RefPointFinder(osmium.SimpleHandler):
        def __init__(self):
            self.lat = None
            self.lon = None
        def node(self, n):
            if self.lat is None and n.location.valid():
                self.lat = n.lat
                self.lon = n.lon

    finder = RefPointFinder()
    finder.apply_file(INPUT_OSM, locations=True)
    if finder.lat is None:
        raise RuntimeError("No valid location in OSM file!")

    projector = LocalProjector(finder.lat, finder.lon)

    # 2. 提取建筑
    handler = BuildingHandler(projector)
    handler.apply_file(INPUT_OSM, locations=True)
    print(f"✅ Extracted {len(handler.buildings)} buildings")

    if not handler.buildings:
        raise RuntimeError("No buildings found!")

    # 3. 合并所有建筑 mesh
    meshes = []
    for verts_2d, h in handler.buildings:
        mesh = polygon_to_mesh(verts_2d, h)
        if mesh is not None:
            meshes.append(mesh)

    combined = trimesh.util.concatenate(meshes)
    building_path = os.path.join(OUTPUT_DIR, "Hongkong_osm_buildings.ply")
    combined.export(building_path)
    print(f"✅ Saved buildings to {building_path}")

    # 4. 生成地面 Plane（居中）
    all_x = [x for verts, _ in handler.buildings for x, _ in verts]
    all_y = [y for verts, _ in handler.buildings for _, y in verts]
    center_x = (min(all_x) + max(all_x)) / 2
    center_y = (min(all_y) + max(all_y)) / 2

    half = GROUND_SIZE / 2
    plane_verts = np.array([
        [center_x - half, center_y - half, GROUND_Z],
        [center_x + half, center_y - half, GROUND_Z],
        [center_x + half, center_y + half, GROUND_Z],
        [center_x - half, center_y + half, GROUND_Z]
    ])
    plane_faces = [[0, 1, 2], [0, 2, 3]]
    plane_mesh = trimesh.Trimesh(vertices=plane_verts, faces=plane_faces)
    plane_path = os.path.join(OUTPUT_DIR, "Plane.ply")
    plane_mesh.export(plane_path)
    print(f"✅ Saved ground plane to {plane_path}")

    # 5. 写入你指定的 XML 格式
    xml_content = '''<scene version="2.1.0">

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

<!-- Emitters -->


<!-- Shapes -->

	<shape type="ply" id="elm__2" name="elm__2">
		<string name="filename" value="meshes/Plane.ply"/>
		<boolean name="face_normals" value="true"/>
		<ref id="mat-itu_concrete" name="bsdf"/>
	</shape>
	<shape type="ply" id="elm__4" name="elm__4">
		<string name="filename" value="meshes/Hongkong_osm_buildings.ply"/>
		<boolean name="face_normals" value="true"/>
		<ref id="mat-itu_brick" name="bsdf"/>
	</shape>

<!-- Volumes -->

</scene>'''

    with open(SCENE_XML, 'w') as f:
        f.write(xml_content)
    print(f"✅ Mitsuba scene saved to {SCENE_XML}")

if __name__ == "__main__":
    main()