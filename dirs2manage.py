import os
import shutil

def initialize_directories():
    """
    初始化工作目录结构。
    检查并清理或创建以下子目录：
    ./2d, ./osm, ./radio_maps, ./tx_overlay, ./with_tx, ./xml, ./xml/meshes
    若目录存在，则清空其内容（保留目录本身）；
    若不存在，则递归创建。
    """
    dirs_to_manage = [
        './2d',
        './osm',
        './radio_maps',
        './tx_overlays',
        './with_tx',
        './xml',
        './xml/meshes'
    ]

    for d in dirs_to_manage:
        if os.path.exists(d):
            # 清空目录内容
            for item in os.listdir(d):
                item_path = os.path.join(d, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"[警告] 无法删除 {item_path}: {e}")
        else:
            # 创建目录（包括父目录）
            os.makedirs(d, exist_ok=True)