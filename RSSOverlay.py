import numpy as np
from PIL import Image


def overlay_rss_on_building(rss_data, building_png_path, output_path, map_size):
    """
    将多Tx的RSS数据叠加后，直接截取[0:map_size, 0:map_size]的部分并叠加到建筑俯视图上。
    - 不平滑、不滤波
    - RSS=0 映射为 100（深灰）
    - 所有非建筑区域灰度 ∈ [100, 255]
    - 建筑区域 = 0（纯黑）
    """
    # Step 1: 合并所有 Tx 的 RSS（线性相加）
    total_rss_linear = np.sum(rss_data, axis=0)  # (H, W)

    # Step 2: 截取 [0:map_size, 0:map_size] 区域
    rss_cropped = total_rss_linear[:map_size, :map_size]

    # Step 3: 转换为 dBm，避免 log(0)
    total_rss_dbm = 10 * np.log10(np.where(rss_cropped == 0, 1e-30, rss_cropped / 1e-3))

    # Step 4: 加载建筑图
    building_img = Image.open(building_png_path).convert("L")
    building_array = np.array(building_img)

    # 确保建筑图也是 map_size x map_size
    if building_array.shape != (map_size, map_size):
        raise ValueError(f"建筑图尺寸必须是 {map_size}x{map_size}，当前尺寸为 {building_array.shape}")

    # Step 5: 映射到 [100, 255]
    vmin = -180.0  # 最弱信号
    vmax = -40.0  # 最强信号

    normalized = (total_rss_dbm - vmin) / (vmax - vmin)
    normalized = np.clip(normalized, 0.0, 1.0)  # 超出范围的截断
    rss_gray = (100 + (255 - 100) * normalized).astype(np.uint8)

    # Step 6: 建筑区域设为纯黑（0）
    building_mask = (building_array == 255)
    final_image = np.where(building_mask, 0, rss_gray)

    # Step 7: 保存
    result_img = Image.fromarray(final_image)
    result_img.save(output_path)
    print(f"✅ RSS 叠加图已保存: {output_path}")