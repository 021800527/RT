import geopandas as gpd
import matplotlib.pyplot as plt
import fiona
import os


def generate_2d_map(osm_file_path):
    """
    从给定的 .osm 文件生成 2D 建筑轮廓图，保存为 ./2D/文件名.png

    参数:
        osm_file_path (str): 输入的 OSM 文件路径，例如 "./osm/Hongkong.osm"
    """
    # 确保输出目录存在
    os.makedirs("./2D", exist_ok=True)

    # 提取基础文件名（不含路径和扩展名）
    filename = os.path.basename(osm_file_path)
    if not filename.lower().endswith('.osm'):
        raise ValueError(f"输入文件必须是 .osm 文件，但得到: {filename}")
    base_name = filename[:-4]  # 去掉 .osm 后缀
    output_path = f"./2D/{base_name}.png"

    # 读取 OSM multipolygons 图层
    try:
        gdf = gpd.read_file(osm_file_path, layer='multipolygons')
    except Exception as e:
        print(f"❌ 无法读取 {osm_file_path} 的 'multipolygons' 图层。")
        try:
            layers = fiona.listlayers(osm_file_path)
            print(f"可用图层: {layers}")
        except Exception:
            pass
        raise e

    # 筛选建筑要素
    if 'building' in gdf.columns:
        buildings = gdf[gdf['building'].notnull()]
    else:
        print(f"⚠️ 警告: {osm_file_path} 中无 'building' 字段，尝试保留所有要素。")
        buildings = gdf

    if buildings.empty:
        print(f"⚠️ 警告: {osm_file_path} 中未找到有效建筑，跳过生成。")
        return

    # 仅保留 geometry 列
    buildings = buildings[['geometry']]

    # 绘图
    fig, ax = plt.subplots(figsize=(12, 12))
    buildings.boundary.plot(ax=ax, color='white', linewidth=2.0)
    ax.set_facecolor('black')
    ax.set_axis_off()

    # 保存图像
    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches='tight',
        pad_inches=0,
        facecolor='black'
    )
    plt.close(fig)  # 防止内存泄漏

    print(f"✅ 已保存: {output_path}")