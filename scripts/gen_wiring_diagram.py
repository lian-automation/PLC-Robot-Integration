# -*- coding: utf-8 -*-
"""
gen_wiring_diagram.py —— 生成主回路接线图（SVG 矢量图）
=====================================================

用途：`star_delta_demo/电气图纸/主回路接线图.txt` 原为纯文本模拟图
（文中自注"占位 .dwg；实际工程请用 EPLAN/CAD 出图后替换"）。本脚本按
文本图的电气拓扑（元件、端子号、线号、跨接关系）渲染为标准图框的 SVG
原理图，供仓库展示与打印。

拓扑来源（与文本图逐项对应）：QF0 → KM1 → FR1 → 电机 M1 → KM_Y / KM_D 两路换接。
图号 E-XD-01，版本 A1。

用法：python scripts/gen_wiring_diagram.py
输出：star_delta_demo/电气图纸/主回路接线图.svg
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "star_delta_demo" / "电气图纸" / "主回路接线图.svg"

W, H = 1240, 860
FONT = "Microsoft YaHei, SimHei, sans-serif"

# 配色（工程图纸风格：白底黑线 + 相线分色）
C_LINE = "#1a1a1a"
C_L1 = "#c62828"      # L1 红
C_L2 = "#2e7d32"      # L2 绿
C_L3 = "#1565c0"      # L3 蓝
C_PE = "#7cb342"      # PE 黄绿
C_BOX = "#f5f7fa"
C_TITLE = "#204e8c"


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, size=13, fill=C_LINE, anchor="start", weight="normal", rotate=None):
    tr = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{tr}>{esc(s)}</text>')


def line(x1, y1, x2, y2, color=C_LINE, width=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}"{d}/>')


def rect(x, y, w, h, fill=C_BOX, stroke=C_LINE, width=2, rx=3):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')


def circle(x, y, r, fill="white", stroke=C_LINE, width=2):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def term(x, y, label, size=11):
    """端子号圆圈标记。"""
    out = [circle(x, y, 11, fill="white")]
    out.append(text(x, y + 4, label, size, anchor="middle", weight="bold"))
    return "".join(out)


def device(x, y, tag, name, spec, w=132, h=62):
    """器件框：上标位号，下注型号。"""
    out = [rect(x, y, w, h)]
    out.append(text(x + w / 2, y + 24, tag, 17, C_LINE, "middle", "bold"))
    out.append(text(x + w / 2, y + 42, name, 12, "#444", "middle"))
    out.append(text(x + w / 2, y + 57, spec, 11, "#666", "middle"))
    return "".join(out)


def build() -> str:
    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}">')
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')

    # 图框
    s.append(rect(16, 16, W - 32, H - 32, fill="none", stroke=C_TITLE, width=3, rx=0))
    s.append(rect(28, 28, W - 56, H - 56, fill="none", stroke=C_TITLE, width=1, rx=0))

    # 标题栏（右下）
    tw, th = 470, 96
    tx, ty = W - 40 - tw, H - 40 - th
    s.append(rect(tx, ty, tw, th, fill="#eef3fa", stroke=C_TITLE, width=2, rx=0))
    s.append(line(tx, ty + 32, tx + tw, ty + 32, C_TITLE, 1))
    s.append(line(tx, ty + 64, tx + tw, ty + 64, C_TITLE, 1))
    s.append(text(tx + 12, ty + 22, "主回路接线图（星三角启动）", 15, C_TITLE, weight="bold"))
    s.append(text(tx + 12, ty + 54, "图号 E-XD-01", 12))
    s.append(text(tx + 180, ty + 54, "版本 A1", 12))
    s.append(text(tx + 300, ty + 54, "2026-08-16", 12))
    s.append(text(tx + 12, ty + 86, "电机 M1  3~ 11kW  AC380V/50Hz", 12))
    s.append(text(tx + 300, ty + 86, "制图：李安", 12))

    y_top = 96
    xs = [230, 350, 470]                       # 三相竖直干线的 x 坐标
    phases = [("L1", C_L1), ("L2", C_L2), ("L3", C_L3)]

    # 电源母线
    s.append(text(150, 74, "三相四线 AC380V/50Hz", 14, C_LINE, weight="bold"))
    for x, (ph, col) in zip(xs, phases):
        s.append(line(x, y_top, x, H - 210, col, 3))
        s.append(text(x - 6, y_top - 8, ph, 14, col, "end", "bold"))

    # 进线端子 (1)(3)(5)
    for x, num in zip(xs, ["1", "3", "5"]):
        s.append(term(x, y_top + 22, num))
    s.append(text(xs[2] + 26, y_top + 26, "← 进线端子号", 11, "#777"))

    # QF0 塑壳断路器
    qf_y = y_top + 62
    s.append(device(xs[0] - 66, qf_y, "QF0", "塑壳断路器", "NB1-63/3P  32A"))
    for x in xs:
        s.append(line(x, y_top + 34, x, qf_y + 10, C_LINE, 2))
        s.append(line(x, qf_y + 52, x, qf_y + 52, C_LINE, 2))   # 触点占位
    # 断路器三相触点刀开关符号
    for x in xs:
        s.append(line(x, qf_y + 12, x, qf_y + 22, C_LINE, 2))
        s.append(line(x, qf_y + 22, x + 11, qf_y + 41, C_LINE, 2))   # 斜刀
        s.append(line(x, qf_y + 41, x, qf_y + 52, C_LINE, 2))
    # 出线端子 (2)(4)(6)
    s.append(term(xs[0], qf_y + 74, "2"))
    s.append(term(xs[1], qf_y + 74, "4"))
    s.append(term(xs[2], qf_y + 74, "6"))
    s.append(text(xs[2] + 26, qf_y + 78, "← 出线端子号", 11, "#777"))

    # KM1 主接触器
    km_y = qf_y + 108
    s.append(device(xs[0] - 66, km_y, "KM1", "主接触器", "NC1-1810  线圈AC220V"))
    for x in xs:
        s.append(line(x, qf_y + 86, x, km_y + 12, C_LINE, 2))
        s.append(line(x, km_y + 12, x, km_y + 22, C_LINE, 2))
        s.append(line(x, km_y + 22, x + 11, km_y + 41, C_LINE, 2))
        s.append(line(x, km_y + 41, x, km_y + 52, C_LINE, 2))
    s.append(text(xs[0] - 66, km_y + 84, "控制回路见 E-XD-02", 11, "#777"))
    # KM1 主接触器三相触点
    for x, i in zip(xs, range(3)):
        s.append(f'<polyline points="{x-7},{km_y+30} {x-7},{km_y+14}" stroke="{C_LINE}" stroke-width="1.6" fill="none"/>')

    # FR1 热继电器
    fr_y = km_y + 96
    fr_x1, fr_x2 = xs[0] - 20, xs[2] + 20
    s.append(rect(fr_x1, fr_y, fr_x2 - fr_x1, 56))
    s.append(text((fr_x1 + fr_x2) / 2, fr_y + 22, "FR1  热继电器  NR2-25", 13, C_LINE, "middle", "bold"))
    s.append(text((fr_x1 + fr_x2) / 2, fr_y + 42, "整定电流 22A（三极主触点串入）", 12, "#555", "middle"))
    for x in xs:
        s.append(line(x, km_y + 52, x, fr_y, C_LINE, 2))
        # 热元件符号（方框）
        s.append(rect(x - 12, fr_y + 12, 24, 22, fill="#fff", width=1.6, rx=0))
        s.append(line(x, fr_y + 56, x, fr_y + 74, C_LINE, 2))

    # 线号 U1/V1/W1
    ln_y = fr_y + 74
    for x, lab in zip(xs, ["U1", "V1", "W1"]):
        s.append(text(x + 8, ln_y - 4, lab, 12, "#a04000", weight="bold"))

    # 电机 M1
    m_y = ln_y + 18
    m_x = xs[0] - 78
    s.append(circle((xs[0] + xs[2]) / 2, m_y + 52, 42, fill="#fff", width=2.5))
    s.append(text((xs[0] + xs[2]) / 2, m_y + 48, "M1", 22, C_LINE, "middle", "bold"))
    s.append(text((xs[0] + xs[2]) / 2, m_y + 66, "3~", 13, "#555", "middle"))
    s.append(text(m_x, m_y + 6, "电机接线盒（6 端子）", 13, C_LINE, weight="bold"))
    # 上排 U1/V1/W1 → 下排 U2/V2/W2
    for x, lab in zip(xs, ["U1", "V1", "W1"]):
        s.append(term(x, m_y + 30, lab, 10))
        s.append(line(x, m_y + 30, x, m_y + 52, C_LINE, 1.6))
    for x, lab in zip(xs, ["U2", "V2", "W2"]):
        s.append(term(x, m_y + 76, lab, 10))
    s.append(text(xs[2] + 26, m_y + 34, "上排：主回路进线", 11, "#777"))
    s.append(text(xs[2] + 26, m_y + 80, "下排：星/三角换接", 11, "#777"))

    # 星形支路
    sy_y = m_y + 120
    s.append(text(xs[0] - 78, sy_y - 6, "星形支路（Y）", 13, "#1565c0", weight="bold"))
    s.append(device(xs[0] - 78, sy_y, "KM_Y", "星点接触器", "三极短接成星点", w=180, h=54))
    for x in xs:
        s.append(line(x, m_y + 88, x, sy_y - 4, "#1565c0", 1.6))
    s.append(line(xs[0] + 20, sy_y + 27, xs[2] - 20, sy_y + 27, "#1565c0", 2))
    s.append(text(xs[1] + 24, sy_y + 24, "N*（星点）", 11, "#1565c0"))

    # 三角支路（跨接）
    dl_y = sy_y + 78
    s.append(text(xs[0] - 78, dl_y - 6, "三角支路（D，跨接）", 13, "#c62828", weight="bold"))
    cross = [("KM_D极1", "U2 → V1", "3U"), ("KM_D极2", "V2 → W1", "3V"), ("KM_D极3", "W2 → U1", "3W")]
    bx = xs[0] - 78
    for i, (tag, conn, wire) in enumerate(cross):
        x0 = bx + i * 186
        s.append(rect(x0, dl_y, 166, 46, fill="#fdf1f1", stroke="#c62828", width=1.6))
        s.append(text(x0 + 10, dl_y + 20, tag, 12.5, "#c62828", weight="bold"))
        s.append(text(x0 + 10, dl_y + 38, f"{conn}   线号 {wire}", 11.5, "#555"))

    # 元件明细表（右上，填充空白区）
    tb_x, tb_y, tb_w = 640, 100, 552
    s.append(rect(tb_x, tb_y, tb_w, 30, fill="#eef3fa", stroke=C_TITLE, width=1.6, rx=0))
    s.append(text(tb_x + tb_w / 2, tb_y + 21, "元件明细表", 13, C_TITLE, "middle", "bold"))
    heads = [("位号", 12), ("名称", 92), ("型号规格", 250), ("数量", 470)]
    hdr_y = tb_y + 30
    s.append(rect(tb_x, hdr_y, tb_w, 26, fill="#f5f7fa", stroke=C_TITLE, width=1.2, rx=0))
    for name, dx in heads:
        s.append(text(tb_x + dx, hdr_y + 18, name, 11.5, C_TITLE, weight="bold"))
    items = [
        ("QF0", "塑壳断路器", "NB1-63/3P  32A", "1"),
        ("KM1", "主接触器", "NC1-1810  AC220V 线圈", "1"),
        ("KR1", "热继电器", "NR2-25  整定 22A", "1"),
        ("KM_Y", "星点接触器", "三极短接成星点（Y）", "1"),
        ("KM_D", "三角接触器", "三极跨接（D）", "1"),
        ("M1", "三相异步电机", "3~ 11kW  AC380V", "1"),
        ("PE", "保护接地", "4mm² 黄绿线  ≤4Ω", "1"),
        ("—", "主回路导线", "4mm²（控制回路 1.0mm²）", "—"),
    ]
    ry = hdr_y + 26
    for i, (tag, name, spec, qty) in enumerate(items):
        fill = "#ffffff" if i % 2 == 0 else "#fafbfc"
        s.append(rect(tb_x, ry, tb_w, 27, fill=fill, stroke="#c7ced6", width=0.8, rx=0))
        s.append(text(tb_x + 12, ry + 19, tag, 11.5, C_LINE, weight="bold"))
        s.append(text(tb_x + 92, ry + 19, name, 11.5))
        s.append(text(tb_x + 250, ry + 19, spec, 11.5, "#555"))
        s.append(text(tb_x + 470, ry + 19, qty, 11.5, "#555"))
        ry += 27
    s.append(text(tb_x + 12, ry + 20, "注：KM_Y 与 KM_D 辅助常闭触点互串互锁", 11, "#777"))

    # PE 接地
    pe_y = dl_y + 66
    s.append(line(xs[2] + 60, pe_y, xs[2] + 160, pe_y, C_PE, 3))
    s.append(text(xs[2] + 66, pe_y - 6, "电机外壳 PE 端子 ── 4mm² 黄绿线 ── PE 铜排", 12, "#33691e"))
    s.append(text(xs[2] + 66, pe_y + 20, "接地电阻 ≤ 4Ω", 12, "#33691e"))
    # 接地符号
    gx = xs[2] + 260
    s.append(line(gx, pe_y - 2, gx, pe_y + 16, C_PE, 3))
    for i, w in enumerate([22, 14, 6]):
        s.append(line(gx - w / 2, pe_y + 16 + i * 7, gx + w / 2, pe_y + 16 + i * 7, C_PE, 3))

    # 备注与图例（放在底部独立区域，避免与支路框重叠）
    box_top = pe_y + 46
    s.append(line(48, box_top - 14, W - 48, box_top - 14, "#c7ced6", 1))
    notes = [
        "互锁：KM_Y 与 KM_D 辅助常闭触点在控制回路互串（见 E-XD-02）",
        "线径：主回路 4mm² ／ PE 4mm² ／ 控制回路 1.0mm²",
        "接地：接地电阻 ≤ 4Ω；停电作业须验电、放电、挂接地线、挂牌上锁",
        "本图为按文本图拓扑渲染的 SVG 效果图；实际工程请以 EPLAN/CAD 出图替换",
    ]
    ny = box_top + 8
    for i, n in enumerate(notes):
        s.append(text(52, ny + i * 21, f"{i + 1}. {n}", 11.5, "#555"))

    # 图例（右下角，对齐标题栏上方）
    lx = 760
    s.append(text(lx, box_top + 2, "相色图例", 12.5, C_LINE, weight="bold"))
    for i, (ph, col) in enumerate(phases):
        s.append(line(lx, box_top + 20 + i * 20, lx + 30, box_top + 20 + i * 20, col, 3))
        s.append(text(lx + 40, box_top + 24 + i * 20, f"{ph} 相", 11.5, col))
    s.append(line(lx + 104, box_top + 20, lx + 134, box_top + 20, C_PE, 3))
    s.append(text(lx + 144, box_top + 24, "PE 保护接地", 11.5, "#33691e"))

    s.append("</svg>")
    return "\n".join(s)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"已生成 {OUT.relative_to(ROOT)}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
