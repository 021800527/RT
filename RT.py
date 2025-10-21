import os
import numpy as np
import traceback
from pathlib import Path
from PIL import Image, ImageDraw
import sionna.rt as rt

def get_scene_bounds(scene):
    """获取场景的 3D 边界（min_xyz, max_xyz）"""
    min_coords = np.full(3, np.inf)
    max_coords = np.full(3, -np.inf)

    for shape in scene.mi_scene.shapes():
        bbox = shape.bbox()
        bmin = np.array(bbox.min)
        bmax = np.array(bbox.max)
        min_coords = np.minimum(min_coords, bmin)
        max_coords = np.maximum(max_coords, bmax)

    if np.any(np.isinf(min_coords)):
        return np.array([0.0, 0.0, 0.0]), np.array([100.0, 100.0, 50.0])

    return min_coords, max_coords

def world_to_pixel(x, y, x_min, x_max, y_min, y_max, img_width, img_height):
    u = ((x - x_min) / (x_max - x_min)) * img_width
    v = ((y - y_min) / (y_max - y_min)) * img_height
    return int(np.clip(u, 0, img_width - 1)), int(np.clip(v, 0, img_height - 1))

def is_point_in_building(x, y, x_min, x_max, y_min, y_max, building_mask):
    """
    判断世界坐标 (x, y) 是否落在建筑区域内（即对应像素是否为白色）
    """
    H, W = building_mask.shape
    u, v = world_to_pixel(x, y, x_min, x_max, y_min, y_max, W, H)
    return building_mask[v, u]  # 注意：numpy 图像是 (H, W)，v 是行，u 是列

def generate_radio_maps_from_xmls(
    xml_dir="./xml",
    png_dir="./2d",
    num_tx=5,
    tx_height=1.5,
    num_rows=8,
    num_cols=2,
    power_dbm=23,
    max_depth=5,
    samples_per_tx=10**6,
    cell_size=(1, 1),
    output_dir="./radio_maps",
    overlay_dir="./tx_overlays",
    with_tx_dir="./with_tx",
    max_retries=100
):
    xml_path = Path(xml_dir)
    png_path = Path(png_dir)

    if not xml_path.exists():
        raise FileNotFoundError(f"XML 目录不存在: {xml_dir}")
    if not png_path.exists():
        raise FileNotFoundError(f"PNG 目录不存在: {png_dir}")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(overlay_dir, exist_ok=True)
    os.makedirs(with_tx_dir, exist_ok=True)

    xml_files = list(xml_path.glob("*.xml"))
    if not xml_files:
        print(f"⚠️ {xml_dir} 中没有 .xml 文件")
        return

    print(f"🔍 找到 {len(xml_files)} 个 XML 场景，开始处理...")

    for xml_file in xml_files:
        try:
            # ✅ 构造对应的 PNG 路径：./2d/0001.png
            png_file = png_path / f"{xml_file.stem}.png"
            if not png_file.exists():
                print(f"⚠️ 对应 {xml_file.name} 的 PNG 文件不存在: {png_file}")
                continue

            print(f"\n📦 处理场景: {xml_file.name}")
            scene = rt.load_scene(str(xml_file))
            scene.bandwidth = 100e6

            scene.tx_array = rt.PlanarArray(
                num_rows=num_rows,
                num_cols=num_cols,
                pattern="tr38901",
                polarization="V"
            )
            scene.rx_array = rt.PlanarArray(
                num_rows=1,
                num_cols=1,
                pattern="iso",
                polarization="V"
            )

            min_coords, max_coords = get_scene_bounds(scene)
            x_min, y_min, _ = min_coords
            x_max, y_max, _ = max_coords

            print(f"📏 场景边界: x∈[{x_min:.1f}, {x_max:.1f}], y∈[{y_min:.1f}, {y_max:.1f}]")

            # === 加载建筑掩膜 ===
            building_img = Image.open(png_file).convert("L")
            building_array = np.array(building_img)
            building_mask = (building_array == 255)  # 白色=建筑

            # === 生成合法 Tx 位置（避开建筑）===
            tx_positions = []
            for i in range(num_tx):
                for attempt in range(max_retries):
                    x = np.random.uniform(x_min, x_max)
                    y = np.random.uniform(y_min, y_max)
                    if not is_point_in_building(x, y, x_min, x_max, y_min, y_max, building_mask):
                        tx_positions.append([x, y, tx_height])
                        break
                else:
                    non_building_pixels = np.argwhere(~building_mask)
                    if len(non_building_pixels) == 0:
                        raise RuntimeError(f"建筑图 {png_file} 全为白色，无可用 Tx 位置！")
                    v, u = non_building_pixels[np.random.randint(len(non_building_pixels))]
                    x = x_min + (u / building_mask.shape[1]) * (x_max - x_min)
                    y = y_min + (v / building_mask.shape[0]) * (y_max - y_min)
                    tx_positions.append([x, y, tx_height])
                    print(f"⚠️ Tx {i} 使用 fallback 位置")

            tx_xs = np.array([p[0] for p in tx_positions])
            tx_ys = np.array([p[1] for p in tx_positions])
            tx_zs = np.array([p[2] for p in tx_positions])

            center_x = float((x_min + x_max) / 2)
            center_y = float((y_min + y_max) / 2)
            center_z = 0.0

            # 清除旧 Tx
            for name in list(scene.transmitters.keys()):
                scene.remove(name)

            # 添加新 Tx
            for i in range(num_tx):
                position = [float(tx_xs[i]), float(tx_ys[i]), float(tx_zs[i])]
                look_at = [center_x, center_y, center_z]
                scene.add(rt.Transmitter(
                    name=f"tx{i}",
                    position=position,
                    look_at=look_at,
                    power_dbm=power_dbm
                ))

            # === 射线追踪 ===
            print("📡 开始射线追踪...")
            rm_solver = rt.RadioMapSolver()
            rm = rm_solver(
                scene,
                max_depth=max_depth,
                samples_per_tx=samples_per_tx,
                cell_size=cell_size
            )
            rss_data = rm.rss.numpy()  # (num_tx, H, W)
            base_name = xml_file.stem

            # 保存无线电地图
            npz_path = os.path.join(output_dir, f"{base_name}_radio_map.npz")
            np.savez_compressed(
                npz_path,
                rss=rss_data,
                tx_positions=np.stack([tx_xs, tx_ys, tx_zs], axis=1)
            )
            print(f"✅ 无线电地图已保存: {npz_path}")

            # === 生成带红点的 Tx 图（建筑变黑，空地变白）===
            building_img_orig = Image.open(png_file).convert("L")
            building_array_orig = np.array(building_img_orig)
            inverted_array = 255 - building_array_orig
            img = Image.fromarray(inverted_array, mode="L").convert("RGB")
            W, H = img.size
            pixel_coords = [
                world_to_pixel(x, y, x_min, x_max, y_min, y_max, W, H)
                for x, y in zip(tx_xs, tx_ys)
            ]
            draw = ImageDraw.Draw(img)
            radius = max(3, min(W, H) // 100)
            for (u, v) in pixel_coords:
                draw.ellipse(
                    (u - radius, v - radius, u + radius, v + radius),
                    fill="red",
                    outline="white",
                    width=1
                )
            tx_overlay_path = os.path.join(with_tx_dir, f"{base_name}_with_tx.png")
            img.save(tx_overlay_path)
            print(f"✅ 带 Tx 红点的图已保存: {tx_overlay_path}")

            # === 生成 RSS 叠加图 ===
            rss_overlay_path = os.path.join(overlay_dir, f"{base_name}_rss_overlay.png")
            from RSSOverlay import overlay_rss_on_building
            overlay_rss_on_building(rss_data, str(png_file), rss_overlay_path)

        except Exception as e:
            print(f"❌ 处理 {xml_file.name} 时出错: {e}")
            traceback.print_exc()