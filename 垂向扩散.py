import numpy as np
import matplotlib

matplotlib.use('Agg')  # 后台极速渲染，消除警告
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
import imageio
from PIL import Image

# ===================== 全局与网格设置 =====================
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']
plt.rcParams['axes.unicode_minus'] = False

nx, ny = 400, 400
dx, dy = 2.0, 2.0

# 严格的 CFL 稳定条件步长与总步数
dt = 0.05
steps = 6000
decay_rate = 0.0005  # 全局极弱自然衰减

output_dir = "output_vertical_pedogenesis"
frames_dir = os.path.join(output_dir, "frames")
os.makedirs(frames_dir, exist_ok=True)

# ===================== 1. 随机谐波生成平滑成土剖面 =====================
x_arr = np.arange(nx)


def generate_smooth_boundary(base_y, max_amp, freq_multiplier=1.0):
    y = np.full(nx, base_y, dtype=float)
    y += max_amp * 0.6 * np.sin(2 * np.pi * x_arr / (300 / freq_multiplier) + np.random.uniform(0, 2 * np.pi))
    y += max_amp * 0.4 * np.sin(2 * np.pi * x_arr / (150 / freq_multiplier) + np.random.uniform(0, 2 * np.pi))
    return y


# 地表微起伏
surface_y = generate_smooth_boundary(380, 10, 1.5)
# A层/E层边界 (距地表约 40)
ae_boundary = surface_y - 40
# E层/B层边界 (非常关键的起伏底板，决定了水流汇聚)
eb_boundary = generate_smooth_boundary(220, 35, 1.0)
eb_boundary = np.minimum(eb_boundary, ae_boundary - 30)
# B层/C层边界
bc_boundary = generate_smooth_boundary(100, 15, 0.8)

# 构建网格掩码 (Masks)
X, Y = np.meshgrid(x_arr, np.arange(ny))
mask_A = (Y <= surface_y) & (Y > ae_boundary)
mask_E = (Y <= ae_boundary) & (Y > eb_boundary)
mask_B = (Y <= eb_boundary) & (Y > bc_boundary)
mask_C = (Y <= bc_boundary)

# 计算 E层/B层 边界的局部坡度，用于驱动 E层底部的侧向滑移
slope_eb = np.gradient(eb_boundary)
slope_2d = np.tile(slope_eb, (ny, 1))

# ===================== 2. 水动力与化学参数精细赋值 =====================
vx_matrix = np.zeros((ny, nx))
vy_matrix = np.zeros((ny, nx))
Dx_matrix = np.ones((ny, nx))
Dy_matrix = np.ones((ny, nx))
porosity = np.ones((ny, nx))
Kd_matrix = np.zeros((ny, nx))
rhob = 1.5  # 土壤容重

# 【A层：表层腐殖质】中等下渗，有一定有机质吸附
vx_matrix[mask_A] = 0.0
vy_matrix[mask_A] = -1.5
Dx_matrix[mask_A] = 2.0;
Dy_matrix[mask_A] = 5.0
porosity[mask_A] = 0.40;
Kd_matrix[mask_A] = 2.0

# 【E层：淋溶层】防污漏洞区。高速下渗，毫无吸附力
vx_matrix[mask_E] = np.clip(-slope_2d[mask_E] * 3.0, -2.0, 2.0)  # 受底板影响的微弱侧流
vy_matrix[mask_E] = -3.5  # 极快下渗
Dx_matrix[mask_E] = 3.0;
Dy_matrix[mask_E] = 10.0
porosity[mask_E] = 0.35;
Kd_matrix[mask_E] = 0.2  # 吸附极低！

# # 【B层：淀积层】终极防污屏障！流速骤降，Kd爆表
# vx_matrix[mask_B] = 0.05  # 水流滞留
# vy_matrix[mask_B] = -2.0  # 极难向下渗透
# Dx_matrix[mask_B] = 8.0;
# Dy_matrix[mask_B] = 1.0  # 压迫导致横向摊开
# porosity[mask_B] = 0.25;
# Kd_matrix[mask_B] = 35.0  # 铁铝氧化物死死锁住磷/钾！

# 【B层：淀积层】终极防污屏障！流速骤降，Kd爆表
vx_matrix[mask_B] = 0.05  # 水流滞留
vy_matrix[mask_B] = -2.0  # 极难向下渗透
Dx_matrix[mask_B] = 3.0;
Dy_matrix[mask_B] = 10.0  # 压迫导致横向摊开
porosity[mask_B] = 0.35;
Kd_matrix[mask_B] = 0.5  # 铁铝氧化物死死锁住磷/钾！


# 【C层：母质含水层】假设存在深层横向地下水流
vx_matrix[mask_C] = 2.5
vy_matrix[mask_C] = 0.0
Dx_matrix[mask_C] = 5.0;
Dy_matrix[mask_C] = 0.5
porosity[mask_C] = 0.30;
Kd_matrix[mask_C] = 0.5

# 计算阻滞因子 R
retardation = 1 + (rhob * Kd_matrix) / porosity

# # ===================== 3. 污染源设定 =====================
# c = np.zeros((ny, nx))
# source_concentration = 100.0
# # 将源头设在地表略微向下一点，避免和“净雨冲刷”边界冲突
# sx1, sx2 = 160, 200
# sy1, sy2 = int(np.min(surface_y)) - 25, int(np.min(surface_y)) - 5

# ===================== 3. 污染源设定 =====================
c = np.zeros((ny, nx))
source_concentration = 100.0  # 初始浓度

# 【全新设定：圆形污染源】
center_x = 180  # 圆心 X 坐标 (水平位置)
center_y = int(np.min(surface_y)) - 15  # 圆心 Y 坐标 (稍微埋在地表下)
radius = 15     # 圆的半径

# 生成全网格的坐标索引矩阵
Y_idx, X_idx = np.ogrid[:ny, :nx]

# 【核心魔法】：通过圆的方程计算出掩码 (在圆内的网格为 True，圆外为 False)
# circle_source_mask = (X_idx - center_x)**2 + (Y_idx - center_y)**2 <= radius**2

# 如果你想做一个【扁平的椭圆】(例如模拟渗沟泄漏)，可以用下面这个方程替换上面那行：
circle_source_mask = ((X_idx - center_x)**2) / 25**2 + ((Y_idx - center_y)**2) / 10**2 <= 1


# ===================== 4. 向量化极速求解器 =====================
def solve_vertical_transport(c, current_step):
    c_new = c.copy()
    idx2, idy2 = 1.0 / dx ** 2, 1.0 / dy ** 2
    idx, idy = 1.0 / dx, 1.0 / dy

    diff_x = Dx_matrix[1:-1, 1:-1] * (c[1:-1, 2:] - 2 * c[1:-1, 1:-1] + c[1:-1, :-2]) * idx2
    diff_y = Dy_matrix[1:-1, 1:-1] * (c[2:, 1:-1] - 2 * c[1:-1, 1:-1] + c[:-2, 1:-1]) * idy2

    vx_inner = vx_matrix[1:-1, 1:-1]
    adv_x = np.where(vx_inner >= 0, vx_inner * (c[1:-1, :-2] - c[1:-1, 1:-1]) * idx,
                     vx_inner * (c[1:-1, 1:-1] - c[1:-1, 2:]) * idx)
    vy_inner = vy_matrix[1:-1, 1:-1]
    adv_y = np.where(vy_inner >= 0, vy_inner * (c[:-2, 1:-1] - c[1:-1, 1:-1]) * idy,
                     vy_inner * (c[1:-1, 1:-1] - c[2:, 1:-1]) * idy)

    decay = -decay_rate * c[1:-1, 1:-1]

    # R因子发挥威力的地方：(dt / retardation)
    c_new[1:-1, 1:-1] = c[1:-1, 1:-1] + (dt / retardation[1:-1, 1:-1]) * (diff_x + diff_y + adv_x + adv_y + decay)

    # 脉冲泄漏 (前 1000 步排放)
    # if current_step < 1000:
    #     current_src = source_concentration * np.exp(-current_step * 0.002)
    #     mask_src = c_new[sy1:sy2, sx1:sx2] < current_src
    #     c_new[sy1:sy2, sx1:sx2] = np.where(mask_src, current_src, c_new[sy1:sy2, sx1:sx2])
    #     # 脉冲泄漏 (前 1000 步排放)
    if current_step < 1000:
        current_src = source_concentration * np.exp(-current_step * 0.002)

        # 判断“在圆形掩码内”且“浓度尚未达到当前源浓度”的网格
        update_mask = circle_source_mask & (c_new < current_src)

        # 仅对符合条件的网格注入污染物
        c_new[update_mask] = current_src


    # 物理边界条件
    c_new[:, -1] = c_new[:, -2]  # 右出流
    c_new[:, 0] = c_new[:, 1]  # 左出流
    c_new[0, :] = c_new[1, :]  # 下出流
    c_new[-1, :] = 0.0  # 模仿雨水持续入渗

    return np.clip(c_new, 0, source_concentration)

# ===================== 5. 地质可视化 =====================
fig, ax = plt.subplots(figsize=(11, 8), dpi=120)

# 1. 绘制地质背景色带 (铺在底层)
# 选用自然的土壤色系，并设置 alpha 半透明度
ax.fill_between(x_arr, ae_boundary, surface_y, color='#8FBC8F', alpha=0.3)  # A层表土：浅灰绿色
ax.fill_between(x_arr, eb_boundary, ae_boundary, color='#F5DEB3', alpha=0.3)  # E层淋溶：浅砂土黄色
ax.fill_between(x_arr, bc_boundary, eb_boundary, color='#CD853F', alpha=0.4)  # B层淀积：黏土红棕色
ax.fill_between(x_arr, 0, bc_boundary, color='#708090', alpha=0.3)            # C层母质：青灰色砂石

# 2. 创建背景透明的定制色板
my_cmap = plt.get_cmap('turbo').copy()
my_cmap.set_under(color='none')  # 把低于 vmin 的数值变成完全透明！

# 3. 叠加污染羽图层 (使用定制好的 my_cmap)
im = ax.imshow(c, cmap=my_cmap, origin="lower", vmin=1.0, vmax=source_concentration / 1.5, interpolation='bilinear')
plt.colorbar(im, ax=ax, label="污染物浓度 (mg/L)", fraction=0.046, pad=0.04)

# 4. 绘制地质剖面边界线
ax.plot(x_arr, surface_y, color='limegreen', linestyle='-', linewidth=2)
ax.plot(x_arr, ae_boundary, color='white', linestyle=':', linewidth=1.5, alpha=0.7)
ax.plot(x_arr, eb_boundary, color='white', linestyle='--', linewidth=2.5)
ax.plot(x_arr, bc_boundary, color='gray', linestyle='-', linewidth=2)

# 5. 图例设置
patch_A = mpatches.Patch(facecolor='#8FBC8F', edgecolor='limegreen', linestyle='-', linewidth=2, label='表土层', alpha=0.6)
patch_E = mpatches.Patch(facecolor='#F5DEB3', edgecolor='white', linestyle=':', linewidth=1.5, label='淋溶层 (粉质/砂质土)', alpha=0.6)
patch_B = mpatches.Patch(facecolor='#CD853F', edgecolor='white', linestyle='--', linewidth=2.5, label='淀积层 (黏土/氧化物)', alpha=0.6)
patch_C = mpatches.Patch(facecolor='#708090', edgecolor='gray', linestyle='-', linewidth=2, label='母质层', alpha=0.6)
ax.legend(handles=[patch_A, patch_E, patch_B, patch_C], loc='upper right', framealpha=0.9, fontsize=10)

# 设置背景色为极浅的灰色，防止透明图层外侧发白
ax.set_facecolor('#1a1a1a')

# ===================== 6. 模拟启动 =====================
print("开始模拟污染物的剖面下渗模型...")
for step in range(steps):
    c = solve_vertical_transport(c, step)

    if step % 25 == 0:
        im.set_data(c)
        ax.set_title(f"污染物在自然土壤剖面中的运移扩散 (t = {step * dt:.0f} 天)", pad=15, fontsize=14)
        plt.savefig(os.path.join(frames_dir, f"frame_{step:04d}.png"), dpi=100, bbox_inches='tight')

    if step % 500 == 0:
        print(f"进度: {step}/{steps} 步")

plt.savefig(os.path.join(output_dir, "地下水污染垂向剖面扩散模拟.png"), dpi=300, bbox_inches='tight')
print(f"\n✅ 模拟完成！\n '{output_dir}/frames' ")


# ===================== 7. 动画生成 =====================
def create_animation(frames_dir, output_dir, fps=24, output_format='gif'):
    """
    将帧图片转换为动画
    :param frames_dir: 帧图片所在目录
    :param output_dir: 输出目录
    :param fps: 帧率
    :param output_format: 输出格式 ('gif' 或 'mp4')
    """
    print(f"\n开始生成动画...")
    
    # 获取所有帧图片并按名称排序
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith('frame_') and f.endswith('.png')])
    
    if not frame_files:
        print("未找到帧图片，跳过动画生成")
        return
    
    print(f"找到 {len(frame_files)} 帧图片")
    
    # 读取所有帧
    images = []
    for frame_file in frame_files:
        frame_path = os.path.join(frames_dir, frame_file)
        img = Image.open(frame_path)
        images.append(img)
    
    # 生成动画
    if output_format == 'gif':
        gif_path = os.path.join(output_dir, "地下水污染垂向扩散动画.gif")
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=1000//fps,
            loop=0
        )
        print(f"✅ GIF动画已保存: {gif_path}")
    
    elif output_format == 'mp4':
        try:
            mp4_path = os.path.join(output_dir, "地下水污染垂向扩散动画.mp4")
            imageio.mimsave(mp4_path, images, fps=fps, macro_block_size=1)
            print(f"✅ MP4动画已保存: {mp4_path}")
        except Exception as e:
            print(f"生成MP4时出错: {e}")
            print("尝试生成GIF替代")
            gif_path = os.path.join(output_dir, "地下水污染垂向扩散动画.gif")
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                duration=1000//fps,
                loop=0
            )
            print(f"✅ GIF动画已保存: {gif_path}")


# 生成GIF动画
create_animation(frames_dir, output_dir, fps=24, output_format='gif')
try:
    create_animation(frames_dir, output_dir, fps=24, output_format='mp4')
except:
    print("MP4生成需要额外依赖，已成功生成GIF动画")