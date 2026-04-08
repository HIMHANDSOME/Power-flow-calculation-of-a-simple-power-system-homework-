#!/usr/bin/env python3
"""
将JSON文件中的节点导纳矩阵转换为Markdown表格格式的脚本
自动获取最新的JSON文件并输出对应的MD表格
"""

import json
import os
import sys
from datetime import datetime

def format_complex(real, imag, precision=4):
    """格式化复数为字符串 a + bj 格式"""
    if abs(imag) < 1e-10:
        return f"{real:.{precision}f}"

    if imag >= 0:
        return f"{real:.{precision}f} + {imag:.{precision}f}j"
    else:
        return f"{real:.{precision}f} - {abs(imag):.{precision}f}j"

def ybus_to_markdown(ybus_data, bus_names=None, precision=4):
    """
    将Ybus矩阵数据转换为Markdown表格

    参数:
    - ybus_data: JSON中的ybus_matrix数据（列表的列表，每个元素为{"real": x, "imag": y}）
    - bus_names: 可选的母线名称列表，用于表头
    - precision: 数值显示精度（小数位数）

    返回:
    - Markdown表格字符串
    """

    n = len(ybus_data)  # 矩阵维度

    # 构建表头
    if bus_names and len(bus_names) == n:
        headers = [f"节点{i}<br>{bus_names[i]}" for i in range(n)]
    else:
        headers = [f"节点{i}" for i in range(n)]

    # Markdown表格表头
    md_lines = []

    # 第一行：表头
    header_row = "| | " + " | ".join(headers) + " |"
    md_lines.append(header_row)

    # 第二行：分隔线
    separator_row = "| --- | " + " | ".join(["---"] * n) + " |"
    md_lines.append(separator_row)

    # 数据行
    for i in range(n):
        row_data = []
        for j in range(n):
            elem = ybus_data[i][j]
            real = elem.get("real", 0.0)
            imag = elem.get("imag", 0.0)
            formatted = format_complex(real, imag, precision)
            row_data.append(formatted)

        # 行表头
        if bus_names and len(bus_names) == n:
            row_header = f"节点{i}<br>{bus_names[i]}"
        else:
            row_header = f"节点{i}"

        row_str = f"| {row_header} | " + " | ".join(row_data) + " |"
        md_lines.append(row_str)

    return "\n".join(md_lines)

def load_bus_names(json_data):
    """从JSON数据中提取母线名称"""
    bus_names = []
    if "bus_results" in json_data:
        # 按bus_id排序
        bus_results = sorted(json_data["bus_results"], key=lambda x: x["bus_id"])
        bus_names = [bus["name"] for bus in bus_results]
    return bus_names

def find_latest_json(directory):
    """在目录中查找最新的power_flow_results_*.json文件"""
    json_files = [f for f in os.listdir(directory)
                  if f.startswith("power_flow_results_") and f.endswith(".json")]

    if not json_files:
        return None

    # 按修改时间排序
    json_files.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
    return os.path.join(directory, json_files[0])

def main():
    # 获取JSON文件路径
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        if not os.path.exists(json_path):
            print(f"错误: 文件不存在: {json_path}")
            return 1
    else:
        # 使用当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = find_latest_json(current_dir)

        if not json_path:
            print("错误: 未找到power_flow_results_*.json文件")
            print("请指定JSON文件路径或确保当前目录下有结果文件")
            return 1

    print(f"正在读取JSON文件: {json_path}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取JSON文件失败: {e}")
        return 1

    # 检查是否包含Ybus矩阵
    if "ybus_matrix" not in data:
        print("错误: JSON文件中未找到ybus_matrix数据")
        return 1

    ybus_data = data["ybus_matrix"]

    if not ybus_data or len(ybus_data) == 0:
        print("错误: Ybus矩阵数据为空")
        return 1

    n = len(ybus_data)
    print(f"Ybus矩阵维度: {n}×{n}")

    # 提取母线名称（可选）
    bus_names = load_bus_names(data)

    if bus_names:
        print(f"已加载{len(bus_names)}个母线名称")
    else:
        print("警告: 未找到母线名称，使用默认节点编号")

    # 生成Markdown表格
    print("正在生成Markdown表格...")
    md_table = ybus_to_markdown(ybus_data, bus_names, precision=4)

    # 添加标题和元信息
    timestamp = data.get("timestamp", datetime.now().isoformat())
    converged = data.get("converged", False)
    num_buses = data.get("network_info", {}).get("num_buses", n)

    title = f"# 节点导纳矩阵 Ybus (标幺值)\n\n"
    info = f"**基本信息**\n"
    info += f"- 生成时间: {timestamp}\n"
    info += f"- 潮流计算收敛: {'是' if converged else '否'}\n"
    info += f"- 系统节点数: {num_buses}\n"
    info += f"- 矩阵维度: {n}×{n}\n\n"

    # 矩阵说明
    explanation = "**矩阵说明**\n"
    explanation += "- 矩阵元素格式: 实部 + 虚部j (或实部 - 虚部j)\n"
    explanation += "- 单位: 标幺值 (基准: 100MVA, 220kV)\n"
    explanation += "- 对角元素: 节点自导纳\n"
    explanation += "- 非对角元素: 节点间互导纳\n\n"

    full_md = title + info + explanation + "## Ybus矩阵\n\n" + md_table

    # 保存到文件
    output_filename = f"ybus_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path = os.path.join(os.path.dirname(json_path), output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_md)

    print(f"Markdown表格已保存到: {output_path}")

    # 同时输出一个简化的纯表格版本（不含说明）
    simple_filename = f"ybus_matrix_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    simple_path = os.path.join(os.path.dirname(json_path), simple_filename)

    with open(simple_path, 'w', encoding='utf-8') as f:
        f.write(md_table)

    print(f"简化版表格已保存到: {simple_path}")

    # 在控制台显示前几行
    print("\n预览 (前3行):")
    lines = md_table.split('\n')
    for i in range(min(5, len(lines))):
        if i < len(lines):
            # 限制行长度
            line = lines[i]
            if len(line) > 120:
                line = line[:117] + "..."
            print(line)

    if len(lines) > 5:
        print("... (完整表格请查看输出文件)")

    return 0

if __name__ == "__main__":
    sys.exit(main())