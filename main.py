from dirs2manage import initialize_directories
from pathlib import Path
from osmto2d import generate_2d_map
from RT import generate_radio_maps_from_xmls
from osm2xml import process_all_osm_files
from download_osm import download_osm_tiles, filter_and_renumber_osm_files


# ==============================
# 第0部分: 初始化工作目录结构
# 检查并清理或创建所需子目录：
# ./2d, ./osm, ./radio_maps, ./tx_overlay, ./with_tx, ./xml, ./xml/meshes
# 若目录存在则清空内容，若不存在则创建
# ==============================
initialize_directories()


# ==============================
# 第一部分: 根据经纬度下载需要的osm
# 这里做了个小处理, 为了生成现实世界256mx256m的结果
# 通过换算，近似截取了实际256mx256m的地形图
# 再通过sionna的cell(1, 1)感觉还是比较靠谱的
# 因为空白的osm对于处理毫无意义
# 所以删除空白osm并对osm重新进行0000开始的编号
# ==============================
download_osm_tiles(
    min_lat=22.282413,
    max_lat=22.294642,
    min_lon=114.158396,
    max_lon=114.170832,
    output_dir="./osm",
    tile_size_m=256,
    max_retries=3
)
filter_and_renumber_osm_files("./osm")

# ==============================
# 第二部分: 将osm文件转换成xml格式并生成meshs
# 这里的逻辑是去读取osm文件
# 取所有建筑的x和y值
# 取256作为平面的长和宽, 目的是为了让坐标系和现实坐标重合
# 比例尺位1米制
# 这里要注意osm特性,如果有超过256的建筑还会保留
# 需要进行裁剪
# 合并所有ply文件
# 一个building
# 一个plane
# 设置所有材质为concrete
# ==============================
process_all_osm_files(
    osm_dir="./osm",
    output_xml_dir="./xml",
    output_meshes_dir=None,
    default_height=20.0,
    floor_height=3.0,
    map_size=256.0,
    ground_z=0
)

# ==============================
# 第三部分: 将osm文件转换成2D俯视图
# 只转换x,y坐标位0-256部分
# ==============================
generate_2d_map(map_size = 256.0)


# ==============================
# 第四部分: 这部分比较复杂
# 主要做了三件事情
# 1、读入xml文件, 根据入参进行radiomap
# 2、保存RT数组(TX数量*plane的宽*plane的长)到radio_maps，格式为npz
# 3、保存随机生成的TX叠加平面图到with_tx
# 4、保存信号强度灰度图到tx_overlay
# ==============================
generate_radio_maps_from_xmls(
    xml_dir="./xml",
    png_dir="./2d",
    num_tx=1,
    tx_height=0,
    num_rows=8,
    num_cols=2,
    power_dbm=23,
    max_depth=8,
    samples_per_tx=25**6,
    cell_size=(1, 1),
    output_dir="./radio_maps",
    overlay_dir="./tx_overlays",
    with_tx_dir="./with_tx",
    map_size=256
)