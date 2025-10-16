import numpy as np
from scipy.ndimage import zoom
from PIL import Image


def overlay_rss_on_building(rss_data, building_png_path, output_path):
    """
    将多Tx的RSS数据线性叠加后，插值并叠加到建筑俯视图上，保存为灰度增强图。

    参数:
    - rss_data: numpy.ndarray, shape (num_tx, H_rss, W_rss)，单位为线性功率（W）
    - building_png_path: str，建筑俯视图路径（如 "osmto2d.png"）
    - output_path: str，输出图像路径（如 "./tx_overlays/Hongkong_rss_overlay.png"）
    """
    # Step 1: 合并所有 Tx 的 RSS（线性相加）
    total_rss_linear = np.sum(rss_data, axis=0)  # (H, W)

    # Step 2: 转换为 dBm
    total_rss_dbm = 10 * np.log10(total_rss_linear / 1e-3 + 1e-20)  # 避免除零

    # Step 3: 加载建筑图（灰度）
    building_img = Image.open(building_png_path).convert("L")
    building_array = np.array(building_img)  # (H_bg, W_bg)

    H_bg, W_bg = building_array.shape
    H_rss, W_rss = total_rss_dbm.shape

    # Step 4: 插值放大到建筑图尺寸
    scale_y = H_bg / H_rss
    scale_x = W_bg / W_rss
    rss_resized = zoom(total_rss_dbm, (scale_y, scale_x), order=3)
    rss_resized = rss_resized[:H_bg, :W_bg]  # 严格对齐尺寸

    # Step 5: 归一化到 [0, 255]
    rss_norm = (rss_resized - rss_resized.min()) / (rss_resized.max() - rss_resized.min() + 1e-12)
    rss_gray = (rss_norm * 255).astype(np.uint8)

    # Step 6: 叠加（信号强的地方更亮）
    final_image = np.maximum(rss_gray, building_array)

    # Step 7: 保存
    result_img = Image.fromarray(final_image)
    result_img.save(output_path)
    print(f"✅ RSS 叠加图已保存: {output_path}")