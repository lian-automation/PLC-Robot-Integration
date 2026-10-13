# -*- coding: utf-8 -*-
"""
tests/test_deliverables.py —— 交付物完整性门禁
=============================================

本仓是"工程交付物型"仓库：除代码外，简历明确声称交付
「MCGS 画面设计」「主回路接线图」等实物。本文件把这些交付物固化为断言，
防止文件被误删或生成脚本失效后仍显示"绿色 CI"：

  1. MCGS 三画面效果图存在且非空（画面说明.md 的渲染产物）；
  2. 主回路接线图 SVG 存在、是合法 SVG、且包含关键元件位号；
  3. 两份生成脚本可被导入/存在（不实际重跑，避免 CI 依赖字体环境）。

依赖：Pillow 仅生成脚本需要；本文件只做存在性与内容断言，用标准库即可。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HMI_DIR = ROOT / "src" / "HMI_Screenshots"
HMI_SCREENS = ["画面1_主界面.png", "画面2_手动调试.png", "画面3_报警中心.png"]
HMI_SPEC = HMI_DIR / "画面说明.md"

SVG_PATH = ROOT / "star_delta_demo" / "电气图纸" / "主回路接线图.svg"
SVG_TEXT_PATH = ROOT / "star_delta_demo" / "电气图纸" / "主回路接线图.txt"

GEN_SCRIPTS = ["scripts/gen_hmi_screens.py", "scripts/gen_wiring_diagram.py"]


# ---------------- MCGS 画面 ----------------

def test_hmi_screens_exist_and_nonempty():
    """三画面效果图必须存在且不是空文件（0 字节 = 生成失败）。"""
    missing = [n for n in HMI_SCREENS if not (HMI_DIR / n).is_file()]
    assert not missing, f"MCGS 画面缺失：{missing}"
    empty = [n for n in HMI_SCREENS if (HMI_DIR / n).stat().st_size < 1024]
    assert not empty, f"MCGS 画面疑似生成失败（<1KB）：{empty}"


def test_hmi_screens_are_valid_png():
    """校验 PNG 魔术字节，防止把占位文本存成 .png。"""
    magic = b"\x89PNG\r\n\x1a\n"
    for name in HMI_SCREENS:
        head = (HMI_DIR / name).read_bytes()[:8]
        assert head == magic, f"{name} 不是合法 PNG（头部 {head!r}）"


def test_hmi_spec_matches_screens():
    """画面说明文档必须覆盖三画面，且不再声称"截图待补"。"""
    assert HMI_SPEC.is_file(), "画面说明.md 缺失"
    txt = HMI_SPEC.read_text(encoding="utf-8")
    assert "待补" not in txt, "画面说明.md 仍标注'待补'，与已生成的效果图不一致"
    for idx in ("画面1", "画面2", "画面3"):
        assert idx in txt, f"画面说明.md 未描述 {idx}"


# ---------------- 主回路接线图 ----------------

def test_wiring_svg_valid_and_complete():
    """SVG 必须存在、结构完整，且含关键位号（防止被简化成空图）。"""
    assert SVG_PATH.is_file(), "主回路接线图.svg 缺失"
    svg = SVG_PATH.read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg"), "不是合法 SVG（缺少 <svg 根元素）"
    assert svg.rstrip().endswith("</svg>"), "SVG 未闭合"
    for tag in ("QF0", "KM1", "FR1", "KM_Y", "KM_D", "E-XD-01"):
        assert tag in svg, f"接线图缺少关键位号/图号：{tag}"


def test_wiring_text_and_svg_share_topology():
    """文本图与 SVG 必须描述同一套拓扑（防止两者口径漂移）。"""
    assert SVG_TEXT_PATH.is_file(), "主回路接线图.txt 缺失"
    txt = SVG_TEXT_PATH.read_text(encoding="utf-8")
    svg = SVG_PATH.read_text(encoding="utf-8")
    for tag in ("QF0", "KM1", "FR1", "KM_Y", "KM_D"):
        assert tag in txt, f"文本图缺少 {tag}"
        assert tag in svg, f"SVG 缺少 {tag}"


def test_wire_numbers_consistent():
    """三角跨接线号（3U/3V/3W）与文档一致。"""
    txt = SVG_TEXT_PATH.read_text(encoding="utf-8")
    for wire in ("3U", "3V", "3W"):
        assert wire in txt, f"文本图缺少线号 {wire}"


# ---------------- 生成脚本 ----------------

def test_generator_scripts_exist():
    """交付物生成脚本必须在仓库内（可复现的前提）。"""
    missing = [s for s in GEN_SCRIPTS if not (ROOT / s).is_file()]
    assert not missing, f"生成脚本缺失：{missing}"


def test_generators_declare_utf8_guard():
    """生成脚本须有控制台编码保护（Windows GBK 下不崩）。"""
    for s in GEN_SCRIPTS:
        src = (ROOT / s).read_text(encoding="utf-8")
        assert re.search(r"reconfigure\(encoding", src), f"{s} 缺少 UTF-8 输出保护"
