import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import zoom
from PIL import Image
import sionna.rt as rt
from osmto2d import generate_2d_map
from RT import generate_radio_maps_from_xmls, get_scene_bounds

# ==============================
# 第一部分: osm文件转换成2D俯视图
# ==============================
osm_dir = Path("./osm")
if osm_dir.exists():
    for osm_file in osm_dir.glob("*.osm"):
        generate_2d_map(str(osm_file))
else:
    print("请创建 ./osm 文件夹并放入 .osm 文件")

generate_radio_maps_from_xmls()