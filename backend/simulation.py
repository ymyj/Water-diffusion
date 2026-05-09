import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io
import base64
import warnings

# 设置中文字体和忽略警告
warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class SoilPollutionSimulator:
    def __init__(self, params=None):
        """
        初始化土壤污染模拟器
        :param params: 参数字典
        """
        # 默认参数
        self.default_params = {
            'nx': 400,
            'ny': 400,
            'dx': 2.0,
            'dy': 2.0,
            'dt': 0.05,
            'steps': 6000,
            'decay_rate': 0.0005,
            'source_concentration': 100.0,
            'source_x': 180,
            'source_y': None,  # 自动计算
            'source_radius_x': 25,
            'source_radius_y': 10,
            'pulse_duration': 1000,
            'A_vy': -1.5,
            'A_Dx': 2.0,
            'A_Dy': 5.0,
            'A_porosity': 0.40,
            'A_Kd': 2.0,
            'E_vy': -3.5,
            'E_Dx': 3.0,
            'E_Dy': 10.0,
            'E_porosity': 0.35,
            'E_Kd': 0.2,
            'B_vy': -2.0,
            'B_Dx': 3.0,
            'B_Dy': 10.0,
            'B_porosity': 0.35,
            'B_Kd': 0.5,
            'C_vx': 2.5,
            'C_Dx': 5.0,
            'C_Dy': 0.5,
            'C_porosity': 0.30,
            'C_Kd': 0.5,
        }
        
        # 更新参数
        self.params = self.default_params.copy()
        if params:
            self.params.update(params)
            
        self.setup_grid()
        self.setup_parameters()
        self.c = np.zeros((self.ny, self.nx))
        self.setup_source()
        
    def setup_grid(self):
        """设置网格和地质剖面"""
        self.nx = self.params['nx']
        self.ny = self.params['ny']
        self.dx = self.params['dx']
        self.dy = self.params['dy']
        self.dt = self.params['dt']
        self.steps = self.params['steps']
        self.decay_rate = self.params['decay_rate']
        
        self.x_arr = np.arange(self.nx)
        
        # 生成地质剖面
        self.surface_y = self.generate_smooth_boundary(380, 10, 1.5)
        self.ae_boundary = self.surface_y - 40
        self.eb_boundary = self.generate_smooth_boundary(220, 35, 1.0)
        self.eb_boundary = np.minimum(self.eb_boundary, self.ae_boundary - 30)
        self.bc_boundary = self.generate_smooth_boundary(100, 15, 0.8)
        
        # 构建网格掩码
        X, Y = np.meshgrid(self.x_arr, np.arange(self.ny))
        self.mask_A = (Y <= self.surface_y) & (Y > self.ae_boundary)
        self.mask_E = (Y <= self.ae_boundary) & (Y > self.eb_boundary)
        self.mask_B = (Y <= self.eb_boundary) & (Y > self.bc_boundary)
        self.mask_C = (Y <= self.bc_boundary)
        
        # 计算坡度
        slope_eb = np.gradient(self.eb_boundary)
        self.slope_2d = np.tile(slope_eb, (self.ny, 1))
    
    def generate_smooth_boundary(self, base_y, max_amp, freq_multiplier=1.0):
        """生成平滑的地质边界"""
        y = np.full(self.nx, base_y, dtype=float)
        y += max_amp * 0.6 * np.sin(2 * np.pi * self.x_arr / (300 / freq_multiplier) + np.random.uniform(0, 2 * np.pi))
        y += max_amp * 0.4 * np.sin(2 * np.pi * self.x_arr / (150 / freq_multiplier) + np.random.uniform(0, 2 * np.pi))
        return y
    
    def setup_parameters(self):
        """设置水动力和化学参数"""
        self.vx_matrix = np.zeros((self.ny, self.nx))
        self.vy_matrix = np.zeros((self.ny, self.nx))
        self.Dx_matrix = np.ones((self.ny, self.nx))
        self.Dy_matrix = np.ones((self.ny, self.nx))
        self.porosity = np.ones((self.ny, self.nx))
        self.Kd_matrix = np.zeros((self.ny, self.nx))
        rhob = 1.5
        
        # A层
        self.vx_matrix[self.mask_A] = 0.0
        self.vy_matrix[self.mask_A] = self.params['A_vy']
        self.Dx_matrix[self.mask_A] = self.params['A_Dx']
        self.Dy_matrix[self.mask_A] = self.params['A_Dy']
        self.porosity[self.mask_A] = self.params['A_porosity']
        self.Kd_matrix[self.mask_A] = self.params['A_Kd']
        
        # E层
        self.vx_matrix[self.mask_E] = np.clip(-self.slope_2d[self.mask_E] * 3.0, -2.0, 2.0)
        self.vy_matrix[self.mask_E] = self.params['E_vy']
        self.Dx_matrix[self.mask_E] = self.params['E_Dx']
        self.Dy_matrix[self.mask_E] = self.params['E_Dy']
        self.porosity[self.mask_E] = self.params['E_porosity']
        self.Kd_matrix[self.mask_E] = self.params['E_Kd']
        
        # B层
        self.vx_matrix[self.mask_B] = 0.05
        self.vy_matrix[self.mask_B] = self.params['B_vy']
        self.Dx_matrix[self.mask_B] = self.params['B_Dx']
        self.Dy_matrix[self.mask_B] = self.params['B_Dy']
        self.porosity[self.mask_B] = self.params['B_porosity']
        self.Kd_matrix[self.mask_B] = self.params['B_Kd']
        
        # C层
        self.vx_matrix[self.mask_C] = self.params['C_vx']
        self.vy_matrix[self.mask_C] = 0.0
        self.Dx_matrix[self.mask_C] = self.params['C_Dx']
        self.Dy_matrix[self.mask_C] = self.params['C_Dy']
        self.porosity[self.mask_C] = self.params['C_porosity']
        self.Kd_matrix[self.mask_C] = self.params['C_Kd']
        
        # 计算阻滞因子
        self.retardation = 1 + (rhob * self.Kd_matrix) / self.porosity
    
    def setup_source(self):
        """设置污染源"""
        self.source_concentration = self.params['source_concentration']
        center_x = self.params['source_x']
        if self.params['source_y'] is None:
            center_y = int(np.min(self.surface_y)) - 15
        else:
            center_y = self.params['source_y']
        radius_x = self.params['source_radius_x']
        radius_y = self.params['source_radius_y']
        
        Y_idx, X_idx = np.ogrid[:self.ny, :self.nx]
        self.circle_source_mask = ((X_idx - center_x)**2) / radius_x**2 + ((Y_idx - center_y)**2) / radius_y**2 <= 1
    
    def solve_step(self, c, current_step):
        """执行一步模拟"""
        c_new = c.copy()
        idx2, idy2 = 1.0 / self.dx ** 2, 1.0 / self.dy ** 2
        idx, idy = 1.0 / self.dx, 1.0 / self.dy
        
        diff_x = self.Dx_matrix[1:-1, 1:-1] * (c[1:-1, 2:] - 2 * c[1:-1, 1:-1] + c[1:-1, :-2]) * idx2
        diff_y = self.Dy_matrix[1:-1, 1:-1] * (c[2:, 1:-1] - 2 * c[1:-1, 1:-1] + c[:-2, 1:-1]) * idy2
        
        vx_inner = self.vx_matrix[1:-1, 1:-1]
        adv_x = np.where(vx_inner >= 0, vx_inner * (c[1:-1, :-2] - c[1:-1, 1:-1]) * idx,
                         vx_inner * (c[1:-1, 1:-1] - c[1:-1, 2:]) * idx)
        vy_inner = self.vy_matrix[1:-1, 1:-1]
        adv_y = np.where(vy_inner >= 0, vy_inner * (c[:-2, 1:-1] - c[1:-1, 1:-1]) * idy,
                         vy_inner * (c[1:-1, 1:-1] - c[2:, 1:-1]) * idy)
        
        decay = -self.decay_rate * c[1:-1, 1:-1]
        
        c_new[1:-1, 1:-1] = c[1:-1, 1:-1] + (self.dt / self.retardation[1:-1, 1:-1]) * (diff_x + diff_y + adv_x + adv_y + decay)
        
        # 脉冲泄漏
        if current_step < self.params['pulse_duration']:
            current_src = self.source_concentration * np.exp(-current_step * 0.002)
            update_mask = self.circle_source_mask & (c_new < current_src)
            c_new[update_mask] = current_src
        
        # 边界条件
        c_new[:, -1] = c_new[:, -2]
        c_new[:, 0] = c_new[:, 1]
        c_new[0, :] = c_new[1, :]
        c_new[-1, :] = 0.0
        
        return np.clip(c_new, 0, self.source_concentration)
    
    def render_frame(self, c, step):
        """将当前状态渲染为图片"""
        fig, ax = plt.subplots(figsize=(11, 8), dpi=100)
        
        # 绘制地质背景
        ax.fill_between(self.x_arr, self.ae_boundary, self.surface_y, color='#8FBC8F', alpha=0.3)
        ax.fill_between(self.x_arr, self.eb_boundary, self.ae_boundary, color='#F5DEB3', alpha=0.3)
        ax.fill_between(self.x_arr, self.bc_boundary, self.eb_boundary, color='#CD853F', alpha=0.4)
        ax.fill_between(self.x_arr, 0, self.bc_boundary, color='#708090', alpha=0.3)
        
        # 创建色板
        my_cmap = plt.get_cmap('turbo').copy()
        my_cmap.set_under(color='none')
        
        # 绘制污染羽流
        im = ax.imshow(c, cmap=my_cmap, origin="lower", vmin=1.0, vmax=self.source_concentration / 1.5, interpolation='bilinear')
        
        # 绘制边界线
        ax.plot(self.x_arr, self.surface_y, color='limegreen', linestyle='-', linewidth=2)
        ax.plot(self.x_arr, self.ae_boundary, color='white', linestyle=':', linewidth=1.5, alpha=0.7)
        ax.plot(self.x_arr, self.eb_boundary, color='white', linestyle='--', linewidth=2.5)
        ax.plot(self.x_arr, self.bc_boundary, color='gray', linestyle='-', linewidth=2)
        
        # 标题
        ax.set_title(f"污染物在自然土壤剖面中的运移扩散 (t = {step * self.dt:.0f} 天)", pad=15, fontsize=14)
        
        # 图例
        patch_A = mpatches.Patch(facecolor='#8FBC8F', edgecolor='limegreen', linestyle='-', linewidth=2, label='表土层', alpha=0.6)
        patch_E = mpatches.Patch(facecolor='#F5DEB3', edgecolor='white', linestyle=':', linewidth=1.5, label='淋溶层', alpha=0.6)
        patch_B = mpatches.Patch(facecolor='#CD853F', edgecolor='white', linestyle='--', linewidth=2.5, label='淀积层', alpha=0.6)
        patch_C = mpatches.Patch(facecolor='#708090', edgecolor='gray', linestyle='-', linewidth=2, label='母质层', alpha=0.6)
        ax.legend(handles=[patch_A, patch_E, patch_B, patch_C], loc='upper right', framealpha=0.9, fontsize=10)
        
        ax.set_facecolor('#1a1a1a')
        
        # 转换为base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return img_base64
    
    def reset(self):
        """重置模拟"""
        self.c = np.zeros((self.ny, self.nx))
        self.setup_source()
