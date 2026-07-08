#!/usr/bin/env python3
"""
汇总图：横向分组柱状图
- 每组（成分）内按 R² 从高到低排列
- 所有成分在一张图中
- 配色风格：sci-figure-plotter
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import csv

DARK_BLUE   = '#1A5276'
BG_WHITE    = '#FFFFFF'
FONT_FAMILY = ['Arial Unicode MS', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']

BAR_COLORS = {
    'Raman':    '#AED6F1',
    'IR':       '#5DADE2',
    'UV':       '#2E86C1',
    'Raman_IR': '#2471A3',
    'Raman_UV': '#3498DB',
    'IR_UV':    '#2980B9',
    'all':      '#154360',
}

plt.rcParams['font.family']       = 'sans-serif'
plt.rcParams['font.sans-serif']   = FONT_FAMILY
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.facecolor']  = BG_WHITE
plt.rcParams['savefig.facecolor'] = BG_WHITE
plt.rcParams['axes.linewidth']    = 0.8


def read_csv(csv_path):
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
    return rows, fieldnames


def plot_summary_horizontal(csv_path, out_path='summary.png'):
    rows, fieldnames = read_csv(csv_path)
    substances = fieldnames[1:]          # 4种成分
    modals = [r['modal_name'] for r in rows]  # 7种模态

    bar_h = 0.12        # 柱子更细
    group_gap = 0.10    # 不同成分之间间距小

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(BG_WHITE)

    # 对每种成分，按 R² 从高到低排序模态，计算 y 位置
    y_base = 0
    y_positions = []     # [(y_center, modal_name, color, value)]
    group_centers = []   # 每组中心 y，用于 ytick
    group_labels = []    # 成分名

    for si, substance in enumerate(substances):
        # 该成分的所有 (modal, value)，按 value 降序
        values = [(r['modal_name'], float(r[substance])) for r in rows]
        values.sort(key=lambda x: x[1], reverse=True)

        n = len(values)
        # 该组占据的 y 范围：[y_base, y_base + n*bar_h]
        center_y = y_base + n * bar_h / 2
        group_centers.append(center_y)
        group_labels.append(substance)

        for mi, (modal, val) in enumerate(values):
            y = y_base + mi * bar_h
            color = BAR_COLORS.get(modal, '#AED6F1')
            ax.barh(y, val, height=bar_h * 0.80,
                    color=color, edgecolor=DARK_BLUE,
                    linewidth=0.5, zorder=2)
            # 柱左端标注模态名
            ax.text(0.005, y, modal,
                    ha='left', va='center', fontsize=7.5,
                    color='white' if modal in ['all', 'Raman_IR', 'IR_UV'] else DARK_BLUE,
                    fontweight='bold', zorder=3)
            # 柱右端标注数值
            ax.text(val + 0.005, y, f'{val:.3f}',
                    ha='left', va='center', fontsize=7,
                    color=DARK_BLUE, zorder=3)

        y_base += n * bar_h + group_gap

    # y 轴：成分标签居中于每组
    ax.set_yticks(group_centers)
    ax.set_yticklabels(group_labels, fontsize=11, color=DARK_BLUE, fontweight='bold')
    ax.tick_params(axis='x', colors=DARK_BLUE, length=3)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 1.12)
    ax.set_xlabel(r'$R^2$', fontsize=12, color=DARK_BLUE, fontweight='bold')

    # 坐标轴样式
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color(DARK_BLUE)
        ax.spines[spine].set_linewidth(0.6)

    # 组间分隔虚线
    for si in range(1, len(substances)):
        y_line = si * (len(modals) * bar_h + group_gap) - group_gap / 2
        ax.axhline(y=y_line, color=DARK_BLUE, linestyle='--',
                   linewidth=0.5, alpha=0.4, zorder=0)

    ax.set_facecolor(BG_WHITE)
    ax.grid(False)
    ax.invert_yaxis()   # 上方 = 第一个成分

    # 标题
    ax.set_title('Summary of Prediction Performance (R²)',
                 fontsize=14, color=DARK_BLUE, fontweight='bold', pad=14)

    # 图例
    legend_elements = [
        mpatches.Patch(facecolor=BAR_COLORS['Raman'],    edgecolor=DARK_BLUE, label='Single Modal'),
        mpatches.Patch(facecolor=BAR_COLORS['Raman_IR'], edgecolor=DARK_BLUE, label='Dual Modal'),
        mpatches.Patch(facecolor=BAR_COLORS['all'],      edgecolor=DARK_BLUE, label='All Modal'),
    ]
    ax.legend(handles=legend_elements, loc='upper center',
              bbox_to_anchor=(0.5, -0.06),
              ncol=3, frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches='tight',
                facecolor=BG_WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Figure saved to {out_path}')


if __name__ == '__main__':
    csv_path = r'E:\wu\xidian\Multimodal_Confusion\Project1\ds\Validation\Raman_IR_UV\汇总.csv'
    plot_summary_horizontal(csv_path, out_path='summary.png')
