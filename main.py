import sionna.rt as rt
import numpy as np

# 加载你的自定义场景
scene = rt.load_scene("Hongkong.xml")  # 注意：用正斜杠或双反斜杠

# 可选：查看场景中有哪些对象
print("Objects in scene:", list(scene.objects.keys()))
print("Transmitters:", list(scene.transmitters.keys()))
print("Receivers:", list(scene.receivers.keys()))

# 创建一个相机视角（你可以调整 position 和 look_at）
camera = rt.Camera(
    position=[500, 500, 300],      # 相机位置 (x, y, z)
    look_at=[0, 0, 50]             # 看向哪个点
)

# 渲染并显示场景（不带无线电地图）
scene.render(camera=camera)