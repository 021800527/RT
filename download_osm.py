import os
import math
import requests

def download_osm_tiles(
    min_lat=22.282413,
    max_lat=22.284642,
    min_lon=114.158396,
    max_lon=114.160832,
    output_dir="./osm",
    tile_size_m=256,
    max_retries=3
):
    """
    将指定经纬度范围划分为 tile_size_m × tile_size_m（米）的瓦片，
    从 OSM 官方 API 下载每个瓦片的 .osm 文件，命名为 0001.osm, 0002.osm, ...

    参数:
        min_lat (float): 最小纬度（南边界）
        max_lat (float): 最大纬度（北边界）
        min_lon (float): 最小经度（西边界）
        max_lon (float): 最大经度（东边界）
        output_dir (str): 输出目录，默认 "./osm"
        tile_size_m (int): 每个瓦片的边长（米），默认 256
        max_retries (int): 下载失败时的最大重试次数，默认 3

    返回:
        int: 成功下载的文件数量
    """
    os.makedirs(output_dir, exist_ok=True)

    # 使用区域中心纬度计算经度缩放
    center_lat = (min_lat + max_lat) / 2.0
    # 纬度方向：1度 ≈ 111320 米
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * math.cos(math.radians(center_lat))

    # 计算每个瓦片对应的经纬度跨度
    delta_lat = tile_size_m / meters_per_deg_lat
    delta_lon = tile_size_m / meters_per_deg_lon

    # 计算需要的瓦片数量（向上取整，确保全覆盖）
    n_lat = math.ceil((max_lat - min_lat) / delta_lat)
    n_lon = math.ceil((max_lon - min_lon) / delta_lon)

    tile_count = 0
    success_count = 0

    for i in range(n_lat):
        for j in range(n_lon):
            # 当前瓦片的地理边界
            south = min_lat + i * delta_lat
            north = min(south + delta_lat, max_lat)
            west  = min_lon + j * delta_lon
            east  = min(west + delta_lon, max_lon)

            # 跳过无效区域
            if north <= south or east <= west:
                continue

            tile_count += 1
            filename = os.path.join(output_dir, f"{tile_count:04d}.osm")

            # 跳过已存在的文件
            if os.path.exists(filename):
                success_count += 1
                continue

            # 构造 OSM API URL
            url = f"https://www.openstreetmap.org/api/0.6/map?bbox={west},{south},{east},{north}"

            success = False
            for attempt in range(max_retries):
                try:
                    resp = requests.get(url, timeout=30)
                    if resp.status_code == 200 and b"<osm" in resp.content:
                        with open(filename, "wb") as f:
                            f.write(resp.content)
                        success = True
                        break
                    elif resp.status_code == 400:
                        print(f"❌ BBox 过大: {west:.6f},{south:.6f},{east:.6f},{north:.6f}")
                        break
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"⚠️ 瓦片 {tile_count} 下载失败: {e}")
                    continue

            if success:
                success_count += 1

    print(f"✅ 已下载 {success_count} / {tile_count} 个瓦片到 '{output_dir}'")
    return success_count