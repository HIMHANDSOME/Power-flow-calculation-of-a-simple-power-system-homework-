import pandapower as pp
import numpy as np
import math
import json
import os
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib

print("=== 电力系统潮流计算（某地区电力系统）===")

# ===== 设置中文字体，解决中文显示问题 =====
try:
    # Windows系统常见中文字体路径
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            matplotlib.font_manager.fontManager.addfont(font_path)
            font_name = matplotlib.font_manager.FontProperties(fname=font_path).get_name()
            plt.rcParams['font.sans-serif'] = [font_name]
            plt.rcParams['axes.unicode_minus'] = False
            print(f"已设置中文字体: {font_name}")
            break
    else:
        print("警告: 未找到系统中文字体，图表可能显示乱码")
except Exception as e:
    print(f"字体设置失败: {e}")

# ===== 创建网络 =====
net = pp.create_empty_network()

# ===== 创建母线 =====
# 发电厂机压母线额定电压10kV，但变压器低压侧额定电压为10.5kV，因此母线基准电压设为10.5kV
b1 = pp.create_bus(net, vn_kv=10.5, name="发电厂1母线")
b2 = pp.create_bus(net, vn_kv=10.5, name="发电厂2母线")
b3 = pp.create_bus(net, vn_kv=35, name="风电场母线")

# 220kV主干网母线
b4 = pp.create_bus(net, vn_kv=220, name="母线4")
b5 = pp.create_bus(net, vn_kv=220, name="母线5（变电所1）")
b6 = pp.create_bus(net, vn_kv=220, name="母线6（变电所2）")
b7 = pp.create_bus(net, vn_kv=220, name="母线7")
b8 = pp.create_bus(net, vn_kv=220, name="母线8（变电所3）")
b9 = pp.create_bus(net, vn_kv=220, name="母线9")

# ===== 节点类型说明 =====
print("\n=== 节点类型 ===")
print("母线1 (发电厂1): 平衡节点 (Slack) - 给定电压幅值10.4kV (0.9905 pu)，承担系统功率不平衡")
print("母线2 (发电厂2): PV节点 - 给定有功出力275MW (295MW-20MW机压负荷)，电压幅值10.5kV (1.0 pu)")
print("母线3 (风电场): PQ节点 - 给定有功95MW，功率因数0.98")
print("母线5,6,8: PQ节点 - 负荷节点")
print("母线4,7,9: PQ节点 - 联络节点（无注入）")

# ===== 外部电网（平衡节点）=====
# 发电厂1机端电压10.4kV，基准10.5kV → vm_pu = 10.4/10.5 ≈ 0.9905
pp.create_ext_grid(net, bus=b1, vm_pu=10.4/10.5, name="Slack")

# ===== 发电机（发电厂2）=====
# 发电厂2总有功出力295MW，带有20MW机压负荷，送入电网的功率为275MW
# 机端电压10.5kV，基准10.5kV → vm_pu = 1.0
pp.create_gen(net, bus=b2, p_mw=295-20, vm_pu=1.0, name="Gen2")

# ===== 风电（PQ节点）=====
# 风电场等效电源功率95MW，cosφ=0.98
p_wind = 95
q_wind = p_wind * math.tan(math.acos(0.98))
pp.create_sgen(net, bus=b3, p_mw=p_wind, q_mvar=q_wind, name="Wind")

# ===== 变压器 =====
# 变压器参数根据资料计算
# T1: 发电厂1升压变，两台100MVA并联，总容量200MVA
# 短路损耗245kW/台，总损耗490kW → vkr_percent = (490/200000)*100 = 0.245%
# 阻抗电压10.5%
pp.create_transformer_from_parameters(
    net, hv_bus=b4, lv_bus=b1,
    sn_mva=200,
    vn_hv_kv=220, vn_lv_kv=10.5,
    vk_percent=10.5, vkr_percent=0.245,
    pfe_kw=0, i0_percent=0,
    name="T1"
)

# T2: 发电厂2升压变，两台240MVA并联，总容量480MVA
# 负载损耗414kW/台，总损耗828kW → vkr_percent = (828/480000)*100 = 0.1725%
# 阻抗电压16.7%
pp.create_transformer_from_parameters(
    net, hv_bus=b7, lv_bus=b2,
    sn_mva=480,
    vn_hv_kv=220, vn_lv_kv=10.5,
    vk_percent=16.7, vkr_percent=0.1725,
    pfe_kw=0, i0_percent=0,
    name="T2"
)

# T3: 风电场升压变，一台180MVA
# 负载损耗285kW → vkr_percent = (285/180000)*100 = 0.1583%
# 阻抗电压13%
pp.create_transformer_from_parameters(
    net, hv_bus=b9, lv_bus=b3,
    sn_mva=180,
    vn_hv_kv=220, vn_lv_kv=35,
    vk_percent=13, vkr_percent=0.1583,
    pfe_kw=0, i0_percent=0,
    name="T3"
)

# ===== 线路参数 =====
# 单位长度：r=0.1 Ω/km, x=0.4 Ω/km, b=2.78e-6 S/km
# 电容计算：b = ωC, ω=2π*50=314.16 → C = b/ω = 2.78e-6/314.16 = 8.85e-9 F/km = 8.85 nF/km
r_ohm_per_km = 0.1
x_ohm_per_km = 0.4
c_nf_per_km = 8.85  # 纳法每公里

def add_line(f, t, length, name):
    pp.create_line_from_parameters(
        net,
        from_bus=f, to_bus=t,
        length_km=length,
        r_ohm_per_km=r_ohm_per_km,
        x_ohm_per_km=x_ohm_per_km,
        c_nf_per_km=c_nf_per_km,
        max_i_ka=1,
        name=name
    )

# 添加线路（距离单位：km）
add_line(b7, b8, 45, "L7-8")
add_line(b8, b9, 50, "L8-9")
add_line(b7, b5, 50, "L7-5")
add_line(b5, b4, 80, "L5-4")
add_line(b6, b4, 55, "L6-4")
add_line(b9, b6, 57, "L9-6")

# ===== 负荷 =====
# 各变电所负荷功率因数均为0.85
def create_load(bus, p_mw, name):
    q_mvar = p_mw * math.tan(math.acos(0.85))
    pp.create_load(net, bus=bus, p_mw=p_mw, q_mvar=q_mvar, name=name)

create_load(b5, 180, "Load5")
create_load(b6, 90, "Load6")
create_load(b8, 150, "Load8")

# ===== 输出网络参数（标幺值前）=====
print("\n=== 网络元件参数（有名值）===")
print("变压器:")
for trafo in net.trafo.itertuples():
    print(f"  {trafo.name}: Sn={trafo.sn_mva} MVA, vk={trafo.vk_percent}%, vkr={trafo.vkr_percent}%")
print("\n线路:")
for line in net.line.itertuples():
    print(f"  {line.name}: length={line.length_km} km, r={line.r_ohm_per_km} Ω/km, x={line.x_ohm_per_km} Ω/km, c={line.c_nf_per_km} nF/km")

# ===== 运行潮流计算 =====
print("\n=== 开始潮流计算 ===")
pp.runpp(net)

# 检查收敛性
if net.converged:
    print("潮流计算收敛。")
else:
    print("警告：潮流计算未收敛！")

# ===== 输出潮流结果 =====
print("\n=== 母线电压结果 ===")
print(net.res_bus[['vm_pu', 'va_degree', 'p_mw', 'q_mvar']])

print("\n=== 线路潮流结果 ===")
print(net.res_line[['p_from_mw', 'q_from_mvar', 'p_to_mw', 'q_to_mvar', 'pl_mw', 'ql_mvar', 'i_from_ka', 'i_to_ka']])

print("\n=== 变压器潮流结果 ===")
print(net.res_trafo[['p_hv_mw', 'q_hv_mvar', 'p_lv_mw', 'q_lv_mvar', 'pl_mw', 'ql_mvar']])

# ===== 提取节点导纳矩阵 Ybus =====
Ybus = net._ppc["internal"]["Ybus"].toarray()
np.set_printoptions(precision=4, suppress=True)
print("\n=== 节点导纳矩阵 Ybus (标幺值) ===")
print(Ybus)

# ===== 输出标幺值参数（可选）=====
print("\n=== 标幺值参数（基于系统基准100MVA, 220kV）===")
# 基准阻抗 Zb = Ub^2/Sb = 220^2/100 = 484 Ω
Zb = 220**2 / 100
print(f"基准容量 Sb = 100 MVA, 基准电压 Ub = 220 kV, 基准阻抗 Zb = {Zb:.2f} Ω")

# 线路标幺值示例
print("\n线路标幺值参数（每公里）:")
r_pu = r_ohm_per_km / Zb
x_pu = x_ohm_per_km / Zb
# 电纳标幺值：b_pu = b * Zb, b = ωC, C = c_nf_per_km * 1e-9 F/km
b_siemens_per_km = 2 * math.pi * 50 * c_nf_per_km * 1e-9
b_pu = b_siemens_per_km * Zb
print(f"  r_pu = {r_pu:.6f}, x_pu = {x_pu:.6f}, b_pu = {b_pu:.6f}")

# 每条线路的总标幺值参数
print("\n每条线路的总标幺值参数:")
for line in net.line.itertuples():
    R = line.r_ohm_per_km * line.length_km
    X = line.x_ohm_per_km * line.length_km
    # 电容电纳（总充电功率）
    C_total = line.c_nf_per_km * line.length_km * 1e-9  # F
    B_total = 2 * math.pi * 50 * C_total  # S
    R_pu = R / Zb
    X_pu = X / Zb
    B_pu = B_total * Zb  # 电纳标幺值（并联）
    print(f"  {line.name}: R={R:.3f} Ω -> {R_pu:.6f} pu, X={X:.3f} Ω -> {X_pu:.6f} pu, B={B_total:.6e} S -> {B_pu:.6f} pu")

# 变压器标幺值参数（归算到系统基准）
print("\n变压器标幺值参数（归算到系统基准100MVA）:")
Sb = 100  # MVA
for trafo in net.trafo.itertuples():
    # 变压器自身基准下的阻抗标幺值
    zk_pu = trafo.vk_percent / 100  # 短路阻抗标幺值
    rk_pu = trafo.vkr_percent / 100  # 短路电阻标幺值
    # 计算电抗标幺值
    xk_pu = math.sqrt(zk_pu**2 - rk_pu**2) if zk_pu > rk_pu else 0
    # 归算到系统基准容量
    zk_sys = zk_pu * (Sb / trafo.sn_mva)
    rk_sys = rk_pu * (Sb / trafo.sn_mva)
    xk_sys = xk_pu * (Sb / trafo.sn_mva)
    print(f"  {trafo.name}: Zk={zk_pu:.6f} pu (自身基准) -> {zk_sys:.6f} pu (系统基准)")
    print(f"      Rk={rk_pu:.6f} pu -> {rk_sys:.6f} pu, Xk={xk_pu:.6f} pu -> {xk_sys:.6f} pu")

print("\n=== 计算完成 ===")

# ===== 保存结果为JSON文件 =====
print("\n=== 保存结果到JSON文件 ===")

def save_results_to_json(net, Ybus, Zb):
    """保存潮流计算结果到JSON文件"""

    def complex_to_dict(z, precision=6):
        """将复数转换为字典格式"""
        if isinstance(z, complex):
            return {"real": round(z.real, precision), "imag": round(z.imag, precision)}
        elif isinstance(z, (int, float)):
            return {"real": round(float(z), precision), "imag": 0.0}
        else:
            # 尝试转换为复数
            try:
                z_complex = complex(z)
                return {"real": round(z_complex.real, precision), "imag": round(z_complex.imag, precision)}
            except:
                return {"real": 0.0, "imag": 0.0}

    # 处理Ybus矩阵，将复数转换为可序列化格式
    ybus_array = np.asarray(Ybus)
    ybus_serializable = []
    for i in range(ybus_array.shape[0]):
        row = []
        for j in range(ybus_array.shape[1]):
            row.append(complex_to_dict(ybus_array[i, j]))
        ybus_serializable.append(row)

    # 创建结果字典
    results = {
        "timestamp": datetime.now().isoformat(),
        "converged": bool(net.converged),
        "network_info": {
            "num_buses": len(net.bus),
            "num_lines": len(net.line),
            "num_transformers": len(net.trafo),
            "num_loads": len(net.load),
            "num_generators": len(net.gen) + len(net.sgen),
            "base_power_mva": 100,
            "base_voltage_kv": 220
        },
        "bus_results": [],
        "line_results": [],
        "transformer_results": [],
        "load_results": [],
        "generator_results": [],
        "ybus_matrix": ybus_serializable,  # 使用处理后的矩阵
        "per_unit_parameters": {
            "base_impedance_ohm": float(Zb),
            "line_parameters_per_km": {
                "r_pu": float(r_ohm_per_km / Zb),
                "x_pu": float(x_ohm_per_km / Zb),
                "b_pu": float(2 * math.pi * 50 * c_nf_per_km * 1e-9 * Zb)
            }
        }
    }

    # 母线结果
    for idx, bus in net.res_bus.iterrows():
        bus_info = net.bus.loc[idx]
        results["bus_results"].append({
            "bus_id": int(idx),
            "name": str(bus_info.get("name", f"Bus{idx}")),
            "voltage_kv": float(bus_info.get("vn_kv", 0)),
            "vm_pu": float(bus.vm_pu),
            "va_degree": float(bus.va_degree),
            "p_mw": float(bus.p_mw),
            "q_mvar": float(bus.q_mvar)
        })

    # 线路结果
    for idx, line in net.res_line.iterrows():
        line_info = net.line.loc[idx]
        results["line_results"].append({
            "line_id": int(idx),
            "name": str(line_info.get("name", f"Line{idx}")),
            "from_bus": int(line_info.from_bus),
            "to_bus": int(line_info.to_bus),
            "length_km": float(line_info.length_km),
            "p_from_mw": float(line.p_from_mw),
            "q_from_mvar": float(line.q_from_mvar),
            "p_to_mw": float(line.p_to_mw),
            "q_to_mvar": float(line.q_to_mvar),
            "pl_mw": float(line.pl_mw),
            "ql_mvar": float(line.ql_mvar),
            "i_from_ka": float(line.i_from_ka),
            "i_to_ka": float(line.i_to_ka)
        })

    # 变压器结果
    for idx, trafo in net.res_trafo.iterrows():
        trafo_info = net.trafo.loc[idx]
        results["transformer_results"].append({
            "trafo_id": int(idx),
            "name": str(trafo_info.get("name", f"Trafo{idx}")),
            "hv_bus": int(trafo_info.hv_bus),
            "lv_bus": int(trafo_info.lv_bus),
            "sn_mva": float(trafo_info.sn_mva),
            "p_hv_mw": float(trafo.p_hv_mw),
            "q_hv_mvar": float(trafo.q_hv_mvar),
            "p_lv_mw": float(trafo.p_lv_mw),
            "q_lv_mvar": float(trafo.q_lv_mvar),
            "pl_mw": float(trafo.pl_mw),
            "ql_mvar": float(trafo.ql_mvar)
        })

    # 负荷结果
    for idx, load in net.res_load.iterrows():
        load_info = net.load.loc[idx]
        results["load_results"].append({
            "load_id": int(idx),
            "name": str(load_info.get("name", f"Load{idx}")),
            "bus": int(load_info.bus),
            "p_mw": float(load_info.p_mw),
            "q_mvar": float(load_info.q_mvar)
        })

    # 发电机结果
    for idx, gen in net.res_gen.iterrows():
        gen_info = net.gen.loc[idx]
        results["generator_results"].append({
            "gen_id": int(idx),
            "name": str(gen_info.get("name", f"Gen{idx}")),
            "bus": int(gen_info.bus),
            "p_mw": float(gen_info.p_mw),
            "vm_pu": float(gen_info.vm_pu)
        })

    for idx, sgen in net.res_sgen.iterrows():
        sgen_info = net.sgen.loc[idx]
        results["generator_results"].append({
            "sgen_id": int(idx),
            "name": str(sgen_info.get("name", f"SGen{idx}")),
            "bus": int(sgen_info.bus),
            "p_mw": float(sgen_info.p_mw),
            "q_mvar": float(sgen_info.q_mvar)
        })

    # 保存到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"power_flow_results_{timestamp}.json"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {filepath}")
    return filepath

# 调用保存函数
json_file = save_results_to_json(net, Ybus, Zb)

# ===== 生成图像 =====
print("\n=== 生成图像 ===")

def generate_plots(net, output_dir):
    """生成潮流计算结果图像"""

    try:
        # 1. 网络拓扑图
        plt.figure(figsize=(12, 10))
        topo_success = False
        topo_file = os.path.join(output_dir, "network_topology.png")

        # 尝试方法1: simple_plot
        try:
            pp.plotting.simple_plot(net, plot_loads=True, plot_gens=True, plot_sgens=True,
                                   bus_size=100, line_width=2)
            plt.title("电力系统网络拓扑图", fontsize=16, fontweight='bold')
            plt.savefig(topo_file, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"网络拓扑图已保存 (simple_plot): {topo_file}")
            topo_success = True
        except Exception as e1:
            print(f"simple_plot失败: {e1}")
            plt.close()

        # 尝试方法2: plot (如果simple_plot失败)
        if not topo_success:
            try:
                plt.figure(figsize=(12, 10))
                pp.plotting.plot(net, plot_loads=True, plot_gens=True, plot_sgens=True,
                               bus_size=100, line_width=2)
                plt.title("电力系统网络拓扑图", fontsize=16, fontweight='bold')
                plt.savefig(topo_file, dpi=300, bbox_inches='tight')
                plt.close()
                print(f"网络拓扑图已保存 (plot): {topo_file}")
                topo_success = True
            except Exception as e2:
                print(f"plot失败: {e2}")
                plt.close()

        # 尝试方法3: 简单的matplotlib绘图 (如果前两种方法都失败)
        if not topo_success:
            try:
                plt.figure(figsize=(12, 10))

                # 创建简单的网络拓扑图
                # 使用圆形布局排列节点
                num_buses = len(net.bus)
                angles = np.linspace(0, 2*np.pi, num_buses, endpoint=False)
                radius = 5
                x = radius * np.cos(angles)
                y = radius * np.sin(angles)

                # 绘制母线节点
                bus_colors = []
                bus_labels = []
                for idx in net.bus.index:
                    bus_name = net.bus.loc[idx].get('name', f'Bus{idx}')
                    bus_labels.append(bus_name)

                    # 根据节点类型设置颜色
                    if idx == b1:  # Slack节点
                        bus_colors.append('gold')
                    elif idx == b2:  # PV节点
                        bus_colors.append('lightgreen')
                    elif idx == b3:  # 风电场
                        bus_colors.append('lightblue')
                    elif idx in [b5, b6, b8]:  # 负荷节点
                        bus_colors.append('lightcoral')
                    else:  # 联络节点
                        bus_colors.append('lightgray')

                # 绘制节点
                for i, (xi, yi, color) in enumerate(zip(x, y, bus_colors)):
                    plt.scatter(xi, yi, s=300, c=color, edgecolors='black', linewidth=2, zorder=3)
                    plt.text(xi, yi+0.3, bus_labels[i], fontsize=10, ha='center', va='bottom', fontweight='bold')

                # 绘制线路
                line_colors = ['blue', 'green', 'red', 'purple', 'orange', 'brown']
                line_idx = 0
                for idx, line in net.line.iterrows():
                    from_bus_idx = list(net.bus.index).index(line.from_bus)
                    to_bus_idx = list(net.bus.index).index(line.to_bus)
                    color = line_colors[line_idx % len(line_colors)]
                    line_name = line.get('name', f'Line{idx}')

                    # 绘制线路
                    plt.plot([x[from_bus_idx], x[to_bus_idx]],
                            [y[from_bus_idx], y[to_bus_idx]],
                            color=color, linewidth=2, alpha=0.7, zorder=2)

                    # 在线路中点添加标签
                    mid_x = (x[from_bus_idx] + x[to_bus_idx]) / 2
                    mid_y = (y[from_bus_idx] + y[to_bus_idx]) / 2
                    plt.text(mid_x, mid_y, line_name, fontsize=9,
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                            ha='center', va='center', zorder=4)

                    line_idx += 1

                # 绘制变压器
                trafo_colors = ['darkred', 'darkgreen', 'darkblue']
                trafo_idx = 0
                for idx, trafo in net.trafo.iterrows():
                    hv_bus_idx = list(net.bus.index).index(trafo.hv_bus)
                    lv_bus_idx = list(net.bus.index).index(trafo.lv_bus)
                    color = trafo_colors[trafo_idx % len(trafo_colors)]
                    trafo_name = trafo.get('name', f'Trafo{idx}')

                    # 绘制变压器连接线（虚线）
                    plt.plot([x[hv_bus_idx], x[lv_bus_idx]],
                            [y[hv_bus_idx], y[lv_bus_idx]],
                            color=color, linewidth=3, linestyle='--', alpha=0.8, zorder=1)

                    # 在变压器中点添加标签
                    mid_x = (x[hv_bus_idx] + x[lv_bus_idx]) / 2
                    mid_y = (y[hv_bus_idx] + y[lv_bus_idx]) / 2
                    plt.text(mid_x, mid_y, trafo_name, fontsize=9,
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8),
                            ha='center', va='center', fontweight='bold', zorder=4)

                    trafo_idx += 1

                # 添加图例
                from matplotlib.patches import Patch
                legend_elements = [
                    Patch(facecolor='gold', edgecolor='black', label='平衡节点 (Slack)'),
                    Patch(facecolor='lightgreen', edgecolor='black', label='PV节点'),
                    Patch(facecolor='lightblue', edgecolor='black', label='风电场 (PQ)'),
                    Patch(facecolor='lightcoral', edgecolor='black', label='负荷节点 (PQ)'),
                    Patch(facecolor='lightgray', edgecolor='black', label='联络节点')
                ]
                plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1), borderaxespad=0)

                plt.title("电力系统网络拓扑图 (简化版)", fontsize=16, fontweight='bold')
                plt.axis('equal')
                plt.axis('off')
                plt.tight_layout()
                plt.savefig(topo_file, dpi=300, bbox_inches='tight')
                plt.close()
                print(f"网络拓扑图已保存 (简化版): {topo_file}")
                topo_success = True
            except Exception as e3:
                print(f"简化版网络拓扑图生成失败: {e3}")
                plt.close()

        if not topo_success:
            print("警告: 无法生成网络拓扑图")

        # 2. 电压分布图
        plt.figure(figsize=(10, 6))
        bus_names = [f"Bus{i}\n{net.bus.loc[i].get('name', '')}" for i in net.res_bus.index]
        voltages = net.res_bus.vm_pu.values

        colors = []
        for v in voltages:
            if v < 0.95:
                colors.append('red')
            elif v > 1.05:
                colors.append('orange')
            else:
                colors.append('green')

        bars = plt.bar(range(len(voltages)), voltages, color=colors, alpha=0.7)
        plt.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='标幺值1.0')
        plt.axhline(y=0.95, color='red', linestyle=':', linewidth=1, label='下限0.95')
        plt.axhline(y=1.05, color='orange', linestyle=':', linewidth=1, label='上限1.05')

        plt.xlabel('母线编号', fontsize=12)
        plt.ylabel('电压幅值 (p.u.)', fontsize=12)
        plt.title('母线电压分布图', fontsize=14, fontweight='bold')
        plt.xticks(range(len(bus_names)), bus_names, rotation=45, ha='right')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        voltage_file = os.path.join(output_dir, "voltage_profile.png")
        plt.savefig(voltage_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"电压分布图已保存: {voltage_file}")

        # 2.1 节点电压详图（电压幅值+相角）
        plt.figure(figsize=(14, 8))

        # 准备数据
        bus_names = [f"Bus{i}\n{net.bus.loc[i].get('name', '')}" for i in net.res_bus.index]
        voltages = net.res_bus.vm_pu.values
        angles = net.res_bus.va_degree.values

        # 子图1：电压幅值
        plt.subplot(1, 2, 1)
        v_colors = []
        for v in voltages:
            if v < 0.95:
                v_colors.append('red')
            elif v > 1.05:
                v_colors.append('orange')
            else:
                v_colors.append('green')

        bars_v = plt.bar(range(len(voltages)), voltages, color=v_colors, alpha=0.7)
        plt.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='标幺值1.0')
        plt.axhline(y=0.95, color='red', linestyle=':', linewidth=1, label='下限0.95')
        plt.axhline(y=1.05, color='orange', linestyle=':', linewidth=1, label='上限1.05')

        # 添加数值标签
        for i, (bar, v) in enumerate(zip(bars_v, voltages)):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.005,
                    f'{v:.4f}', ha='center', va='bottom', fontsize=9, rotation=45)

        plt.xlabel('母线编号', fontsize=12)
        plt.ylabel('电压幅值 (p.u.)', fontsize=12)
        plt.title('母线电压幅值分布', fontsize=14, fontweight='bold')
        plt.xticks(range(len(bus_names)), bus_names, rotation=45, ha='right')
        plt.legend(loc='upper right')
        plt.grid(True, alpha=0.3)

        # 子图2：电压相角
        plt.subplot(1, 2, 2)
        # 相角通常有正有负，使用渐变色表示
        norm = plt.Normalize(angles.min(), angles.max())
        cmap = plt.cm.coolwarm
        a_colors = cmap(norm(angles))

        bars_a = plt.bar(range(len(angles)), angles, color=a_colors, alpha=0.7)

        # 添加数值标签
        for i, (bar, a) in enumerate(zip(bars_a, angles)):
            height = bar.get_height()
            va = 'bottom' if height >= 0 else 'top'
            y_offset = 0.5 if height >= 0 else -0.5
            plt.text(bar.get_x() + bar.get_width()/2., height + y_offset,
                    f'{a:.2f}°', ha='center', va=va, fontsize=9)

        plt.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
        plt.xlabel('母线编号', fontsize=12)
        plt.ylabel('电压相角 (°)', fontsize=12)
        plt.title('母线电压相角分布', fontsize=14, fontweight='bold')
        plt.xticks(range(len(bus_names)), bus_names, rotation=45, ha='right')

        # 添加颜色条说明
        from matplotlib.cm import ScalarMappable
        sm = ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=plt.gca(), pad=0.05)
        cbar.set_label('相角大小 (°)', fontsize=10)

        plt.grid(True, alpha=0.3)

        plt.tight_layout()

        voltage_detail_file = os.path.join(output_dir, "node_voltage_details.png")
        plt.savefig(voltage_detail_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"节点电压详图已保存: {voltage_detail_file}")

        # 3. 线路负载率图（电流百分比）
        if len(net.res_line) > 0:
            plt.figure(figsize=(10, 6))
            line_names = [net.line.loc[i].get('name', f'Line{i}') for i in net.res_line.index]
            # 假设额定电流为1kA（根据线路参数max_i_ka）
            max_currents = net.line.max_i_ka.values
            current_from = net.res_line.i_from_ka.values
            current_to = net.res_line.i_to_ka.values

            # 取较大的电流值
            currents = np.maximum(current_from, current_to)

            # 计算负载率
            loading = []
            for i, curr in enumerate(currents):
                if max_currents[i] > 0:
                    loading.append(curr / max_currents[i] * 100)
                else:
                    loading.append(0)

            colors = []
            for load in loading:
                if load > 100:
                    colors.append('red')
                elif load > 80:
                    colors.append('orange')
                else:
                    colors.append('green')

            bars = plt.bar(range(len(loading)), loading, color=colors, alpha=0.7)
            plt.axhline(y=100, color='red', linestyle='--', linewidth=1, label='100%负载')
            plt.axhline(y=80, color='orange', linestyle=':', linewidth=1, label='80%负载')

            plt.xlabel('线路', fontsize=12)
            plt.ylabel('负载率 (%)', fontsize=12)
            plt.title('线路负载率图', fontsize=14, fontweight='bold')
            plt.xticks(range(len(line_names)), line_names, rotation=45, ha='right')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()

            loading_file = os.path.join(output_dir, "line_loading.png")
            plt.savefig(loading_file, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"线路负载率图已保存: {loading_file}")

        # 4. 功率分布图（有功饼图 + 无功柱状图）
        plt.figure(figsize=(12, 8))

        # 计算各类功率
        total_gen_p = net.res_gen.p_mw.sum() if len(net.res_gen) > 0 else 0
        total_sgen_p = net.res_sgen.p_mw.sum() if len(net.res_sgen) > 0 else 0
        total_load_p = net.res_load.p_mw.sum() if len(net.res_load) > 0 else 0
        total_loss_p = net.res_line.pl_mw.sum() if len(net.res_line) > 0 else 0

        total_gen_q = net.res_gen.q_mvar.sum() if len(net.res_gen) > 0 else 0
        total_sgen_q = net.res_sgen.q_mvar.sum() if len(net.res_sgen) > 0 else 0
        total_load_q = net.res_load.q_mvar.sum() if len(net.res_load) > 0 else 0
        total_loss_q = net.res_line.ql_mvar.sum() if len(net.res_line) > 0 else 0

        # 有功功率分布（饼图）
        plt.subplot(1, 2, 1)
        p_labels = ['火电', '风电', '负荷', '网损']
        p_values = [total_gen_p, total_sgen_p, total_load_p, total_loss_p]
        p_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']

        # 过滤零值
        p_labels_filtered = []
        p_values_filtered = []
        p_colors_filtered = []
        for label, value, color in zip(p_labels, p_values, p_colors):
            if value > 0.1:  # 忽略小于0.1MW的值
                p_labels_filtered.append(f"{label}\n{value:.1f}MW")
                p_values_filtered.append(value)
                p_colors_filtered.append(color)

        if p_values_filtered:
            plt.pie(p_values_filtered, labels=p_labels_filtered, colors=p_colors_filtered,
                   autopct='%1.1f%%', startangle=90)
            plt.title('有功功率分布 (MW)', fontsize=12, fontweight='bold')
        else:
            plt.text(0.5, 0.5, '无有功功率数据', ha='center', va='center')

        # 无功功率分布（柱状图，显示正负值）
        plt.subplot(1, 2, 2)
        q_labels = ['火电无功', '风电无功', '负荷无功', '网损无功']
        q_values = [total_gen_q, total_sgen_q, total_load_q, total_loss_q]
        q_colors = []

        # 根据正负值设置颜色
        for value in q_values:
            if value < 0:
                q_colors.append('#FF9999')  # 红色表示吸收无功
            else:
                q_colors.append('#99CC99')  # 绿色表示发出无功

        x_pos = np.arange(len(q_values))
        bars = plt.bar(x_pos, q_values, color=q_colors, alpha=0.7)

        # 添加数值标签
        for i, (bar, value) in enumerate(zip(bars, q_values)):
            height = bar.get_height()
            if value >= 0:
                va = 'bottom'
                y_offset = 5
            else:
                va = 'top'
                y_offset = -5
            plt.text(bar.get_x() + bar.get_width()/2., height + y_offset,
                    f'{value:.1f}', ha='center', va=va, fontsize=9)

        plt.axhline(y=0, color='black', linewidth=0.8)
        plt.xlabel('无功类型', fontsize=11)
        plt.ylabel('无功功率 (MVar)', fontsize=11)
        plt.title('无功功率分布 (MVar)', fontsize=12, fontweight='bold')
        plt.xticks(x_pos, q_labels, rotation=15, ha='right')
        plt.grid(True, alpha=0.3, axis='y')

        # 添加图例说明颜色含义
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor='#99CC99', alpha=0.7, label='发出无功'),
                          Patch(facecolor='#FF9999', alpha=0.7, label='吸收无功')]
        plt.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()

        power_file = os.path.join(output_dir, "power_distribution.png")
        plt.savefig(power_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"功率分布图已保存: {power_file}")

    except Exception as e:
        print(f"图像生成过程中出现错误: {e}")

# 获取当前脚本目录作为输出目录
output_dir = os.path.dirname(__file__)
generate_plots(net, output_dir)

print("\n=== 所有结果保存完成 ===")