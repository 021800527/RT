import numpy as np
from scipy.ndimage import zoom
from PIL import Image

def overlay_rss_on_building(rss_data, building_png_path, output_path):
    """
    将多Tx的RSS数据叠加后，插值并叠加到建筑俯视图上。
    - 不平滑、不滤波
    - RSS=0 映射为 100（深灰）
    - 所有非建筑区域灰度 ∈ [100, 255]
    - 建筑区域 = 0（纯黑）
    """
    # Step 1: 合并所有 Tx 的 RSS（线性相加）
    total_rss_linear = np.sum(rss_data, axis=0)  # (H, W)

    # Step 2: 转换为 dBm，避免 log(0)
    total_rss_dbm = 10 * np.log10(np.where(total_rss_linear == 0, 1e-30, total_rss_linear / 1e-3))

    # Step 3: 加载建筑图
    building_img = Image.open(building_png_path).convert("L")
    building_array = np.array(building_img)
    H_bg, W_bg = building_array.shape
    H_rss, W_rss = total_rss_dbm.shape

    # Step 4: 插值放大（保持你用的 order=3）
    scale_y = H_bg / H_rss
    scale_x = W_bg / W_rss
    rss_resized = zoom(total_rss_dbm, (scale_y, scale_x), order=3)
    rss_resized = rss_resized[:H_bg, :W_bg]

    # Step 5: 映射到 [100, 255]
    vmin = -180.0   # 最弱信号
    vmax = -40.0    # 最强信号

    # 线性映射：[vmin, vmax] → [100, 255]
    normalized = (rss_resized - vmin) / (vmax - vmin)
    normalized = np.clip(normalized, 0.0, 1.0)  # 超出范围的截断
    rss_gray = (100 + (255 - 100) * normalized).astype(np.uint8)

    # Step 6: 建筑区域设为纯黑（0）
    building_mask = (building_array == 255)
    final_image = np.where(building_mask, 0, rss_gray)

    # Step 7: 保存
    result_img = Image.fromarray(final_image)
    result_img.save(output_path)
    print(f"✅ RSS 叠加图已保存: {output_path}")