from pathlib import Path
from osmto2d import generate_2d_map
from RT import generate_radio_maps_from_xmls

# ==============================
# 第一部分: 将osm文件转换成2D俯视图
# ==============================
osm_dir = Path("./osm")
if osm_dir.exists():
    for osm_file in osm_dir.glob("*.osm"):
        generate_2d_map(str(osm_file))
else:
    print("请创建 ./osm 文件夹并放入 .osm 文件")

# ==============================
# 第二部分: 这部分比较复杂
# 主要做了三件事情
# 1、读入xml文件, 根据入参进行radiomap
# 2、保存RT数组(TX数量*plane的宽*plane的长)到radio_maps，格式为npz
# 3、保存随机生成的TX叠加平面图到with_tx
# 4、保存信号强度灰度图到tx_overlay
# ==============================
generate_radio_maps_from_xmls(
    xml_dir="./xml",
    building_png="./2d/Hongkong.png",
    num_tx=1,
    tx_height=0,
    num_rows=8,
    num_cols=2,
    power_dbm=23,
    max_depth=5,
    samples_per_tx=30**6,
    cell_size=(0.5, 0.5),
    output_dir="./radio_maps",
    overlay_dir="./tx_overlays",
    with_tx_dir="./with_tx"
)