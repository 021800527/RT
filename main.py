from pathlib import Path
from osmto2d import generate_2d_map
from RT import generate_radio_maps_from_xmls
from osm2xml import process_all_osm_files
from download_osm import download_osm_tiles, filter_and_renumber_osm_files


# ==============================
# 第一部分: 根据经纬度下载需要的osm
# 这里做了个小处理, 为了生成256x256的结果
# 通过换算，近似截取了实际256mx256m的地形图
# 再通过sionna的cell(1, 1)感觉还是比较靠谱的
# 这部分如果是无建筑的地区还会保留
# 不做删除是感觉用不到
# 删了可能会出现争用
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
# 取(最大值x+10)和(最大值y+10)作为平面的长和宽
# 合并所有ply文件
# 合为两个
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
    ground_margin=0.0,
    ground_z=0
)

# ==============================
# 第三部分: 将osm文件转换成2D俯视图
# 这里做了一点点处理
# 如果osm空白或者错误直接略过
# ==============================
osm_dir = Path("./osm")
osm_files = list(osm_dir.glob("*.osm")) or (print("请创建 ./osm 文件夹并放入 .osm 文件") or [])
for osm_file in osm_files:
    generate_2d_map(str(osm_file))


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
    num_tx=3,
    tx_height=0,
    num_rows=8,
    num_cols=2,
    power_dbm=23,
    max_depth=5,
    samples_per_tx=20**6,
    cell_size=(1, 1),
    output_dir="./radio_maps",
    overlay_dir="./tx_overlays",
    with_tx_dir="./with_tx"
)