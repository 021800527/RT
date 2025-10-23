import os
import math
import requests
from pathlib import Path
import geopandas as gpd
import shutil


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
    从 OSM 官方 API 下载每个瓦片的 .osm 文件，**从 0000.osm 开始编号**。

    参数:
        min_lat (float): 最小纬度（南边界）
        max_lat (float): 最大纬度（北边界）
        min_lon (float): 最小经度（西边界）
        max_lon (float): 最大经度（东边界）
        output_dir (str): 输出目录，默认 "./osm"
        tile_size_m (int): 每个瓦片的边长（米），默认 256
        max_retries (int): 下载失败时的最大重试次数，默认 3

    返回:
        int: 成功下载的文件数量（包括已存在的）
    """
    os.makedirs(output_dir, exist_ok=True)

    center_lat = (min_lat + max_lat) / 2.0
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * math.cos(math.radians(center_lat))

    delta_lat = tile_size_m / meters_per_deg_lat
    delta_lon = tile_size_m / meters_per_deg_lon

    n_lat = math.ceil((max_lat - min_lat) / delta_lat)
    n_lon = math.ceil((max_lon - min_lon) / delta_lon)

    tile_count = 0
    success_count = 0

    for i in range(n_lat):
        for j in range(n_lon):
            south = min_lat + i * delta_lat
            north = min(south + delta_lat, max_lat)
            west  = min_lon + j * delta_lon
            east  = min(west + delta_lon, max_lon)

            if north <= south or east <= west:
                continue

            # 👇 关键修改：先命名 0000.osm，再递增
            filename = os.path.join(output_dir, f"{tile_count:04d}.osm")
            tile_count += 1

            if os.path.exists(filename):
                success_count += 1
                continue

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
                        print(f"⚠️ 瓦片 {tile_count - 1} 下载失败: {e}")
                    continue

            if success:
                success_count += 1

    print(f"✅ 已下载 {success_count} / {tile_count} 个瓦片到 '{output_dir}'")
    return success_count


def filter_and_renumber_osm_files(osm_dir="./osm"):
    """
    遍历 ./osm/*.osm，检查是否包含有效建筑数据。
    删除无效文件，并将有效文件重命名为连续的 0000.osm, 0001.osm, ...

    返回:
        int: 保留的有效文件数量
    """
    osm_path = Path(osm_dir)
    if not osm_path.exists():
        print("❌ osm 目录不存在")
        return 0

    # 获取所有 .osm 文件，按数字排序
    all_osm = []
    for f in osm_path.glob("*.osm"):
        try:
            stem_int = int(f.stem)
            all_osm.append((stem_int, f))
        except ValueError:
            continue  # 跳过非数字命名的文件（如 demo.osm）
    all_osm.sort(key=lambda x: x[0])
    all_osm = [f for _, f in all_osm]

    valid_files = []
    for f in all_osm:
        try:
            # 快速跳过太小的文件（<1KB）
            if f.stat().st_size < 1024:
                print(f"🗑️  {f.name} 文件太小 (<1KB)，删除")
                f.unlink()
                continue

            # 尝试读取 multipolygons 图层（最多读 20 行加速）
            gdf = gpd.read_file(str(f), layer='multipolygons', rows=20)
            if gdf.empty:
                print(f"🗑️  {f.name} 无 multipolygons 数据，删除")
                f.unlink()
                continue

            # 检查是否有 building 标签且非空
            if 'building' not in gdf.columns or gdf['building'].isnull().all():
                print(f"🗑️  {f.name} 无有效建筑标签，删除")
                f.unlink()
                continue

            valid_files.append(f)

        except Exception as e:
            print(f"🗑️  {f.name} 读取失败或无效，删除: {e}")
            f.unlink()

    # 重命名有效文件为 0000.osm, 0001.osm, ...
    temp_dir = osm_path / "temp_valid"
    temp_dir.mkdir(exist_ok=True)

    for idx, f in enumerate(valid_files):
        new_name = temp_dir / f"{idx:04d}.osm"
        shutil.move(str(f), str(new_name))
        print(f"✅ 保留并重命名: {f.name} → {new_name.name}")

    # 清空原目录中的 .osm 文件
    for f in osm_path.glob("*.osm"):
        if f.is_file():
            f.unlink()

    # 移回重命名后的文件
    for f in temp_dir.glob("*.osm"):
        shutil.move(str(f), str(osm_path / f.name))

    temp_dir.rmdir()

    print(f"🎯 共保留 {len(valid_files)} 个有效 OSM 文件，已重命名为 0000.osm ~ {len(valid_files)-1:04d}.osm")
    return len(valid_files)