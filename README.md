# 土壤污染扩散模拟系统

一个基于 Flask + Vue.js 的交互式土壤污染物运移扩散模拟系统，支持实时参数调节和可视化展示。

## 项目结构

```
water-diffusion/
├── backend/                    # 后端代码
│   ├── app.py                 # Flask 主应用
│   ├── simulation.py          # 模拟核心模块
│   ├── requirements.txt       # Python 依赖
│   └── templates/
│       └── index.html         # 前端界面
├── 垂向扩散.py                # 原始独立模拟脚本
└── README.md                  # 项目说明
```

## 功能特性

- 🎛️ **实时参数调节**：可调整各土层的流速、扩散系数、孔隙度、吸附系数等参数
- 🌍 **四层土壤模型**：表土层(A)、淋溶层(E)、淀积层(B)、母质层(C)
- 📊 **实时可视化**：通过 WebSocket 实时推送模拟进度和图像
- ⏯️ **交互控制**：支持开始、停止、重置模拟
- 📈 **进度展示**：显示当前时间和模拟进度条

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python app.py
```

### 3. 访问界面

在浏览器中打开：`http://localhost:5000`

## 参数说明

### 通用参数
- `steps`：总模拟步数（默认：6000）
- `dt`：时间步长（默认：0.05 天）
- `decay_rate`：污染物自然衰减率

### 污染源参数
- `source_concentration`：污染源初始浓度
- `source_x`：污染源 X 坐标
- `source_radius_x/y`：污染源半径
- `pulse_duration`：脉冲排放持续步数

### 土层参数（A/E/B/C层）
- `*_vy`：垂直流速
- `*_Dx`：水平扩散系数
- `*_Dy`：垂直扩散系数
- `*_porosity`：土壤孔隙度（0-1）
- `*_Kd`：吸附分配系数

## 技术栈

### 后端
- **Flask**：轻量级 Web 框架
- **Flask-SocketIO**：WebSocket 支持
- **NumPy**：数值计算
- **Matplotlib**：图像渲染

### 前端
- **Vue 3**：响应式前端框架
- **Socket.IO**：实时通信
- **原生 CSS**：现代化 UI 设计

## 原始脚本使用

如果只想运行原始的独立模拟脚本：

```bash
python 垂向扩散.py
```

输出将保存在 `output_vertical_pedogenesis/` 目录，包括帧图像和 GIF/MP4 动画。

## 注意事项

1. 模拟计算量较大，建议根据机器性能调整 `steps` 参数
2. 首次运行需要渲染地质剖面，请耐心等待
3. 可以通过浏览器控制台查看运行日志

## 许可证

MIT License
