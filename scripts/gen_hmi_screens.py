# -*- coding: utf-8 -*-
"""
gen_hmi_screens.py —— 生成 MCGS 触摸屏画面图（TPC7062Ti，800×480）
=================================================================

用途：`src/HMI_Screenshots/画面说明.md` 原有 ASCII 线框草图（"截图待补"），
本脚本把它渲染为真实 PNG 画面，补齐简历声称的"MCGS 画面设计"交付物。

说明：本脚本生成的是**按 MCGS 组态风格绘制的画面效果图**（用于仓库展示与
     面试演示），不是从真机 MCGS 工程导出的截图——README 已如实标注。
     画面布局、元件类型、权限设计均与 画面说明.md 及 src/PLC_Logic.scl 一致。

用法：python scripts/gen_hmi_screens.py
输出：src/HMI_Screenshots/画面1_主界面.png 等 3 张
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "HMI_Screenshots"

W, H = 800, 480                      # TPC7062Ti 标准分辨率

# MCGS 风格配色（深底 + 高饱和状态色，贴近工业触摸屏观感）
C_BG = (232, 236, 240)
C_TITLE = (32, 78, 140)
C_PANEL = (255, 255, 255)
C_BORDER = (150, 160, 172)
C_TEXT = (30, 34, 40)
C_GREEN = (24, 160, 80)
C_RED = (200, 48, 48)
C_GRAY = (150, 155, 162)
C_AMBER = (222, 150, 20)


def _font(size: int, bold: bool = False):
    """找一个可用的中文字体（Windows 常见字体优先）。"""
    candidates = [
        ("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _panel(draw, box, title=None, f_title=None):
    """画一个带边框的信息面板，可选标题条。"""
    draw.rectangle(box, fill=C_PANEL, outline=C_BORDER, width=2)
    if title:
        x1, y1, x2, _ = box
        draw.rectangle((x1 + 1, y1 + 1, x2 - 1, y1 + 32), fill=(222, 230, 240))
        draw.text((x1 + 10, y1 + 7), title, fill=C_TITLE, font=f_title)


def _status_led(draw, xy, text, on=True, color=None, f=None):
    """画一个指示灯 + 标签。"""
    x, y = xy
    c = color if color else (C_GREEN if on else C_GRAY)
    draw.ellipse((x, y, x + 18, y + 18), fill=c, outline=(90, 96, 104), width=2)
    draw.text((x + 26, y + 1), text, fill=C_TEXT, font=f)


def _button(draw, box, text, f, fill=(236, 242, 250), outline=C_BORDER):
    draw.rectangle(box, fill=fill, outline=outline, width=2)
    tw = draw.textlength(text, font=f)
    x1, y1, x2, y2 = box
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1) / 2 - 11), text,
              fill=C_TEXT, font=f)


def _title_bar(draw, text, page_hint):
    draw.rectangle((0, 0, W, 52), fill=C_TITLE)
    draw.text((16, 12), text, fill=(255, 255, 255), font=_font(22, True))
    tw = draw.textlength(page_hint, font=_font(16))
    draw.text((W - tw - 16, 18), page_hint, fill=(210, 225, 245), font=_font(16))


def screen_main() -> Image.Image:
    """画面1：主界面（索引 0）——运行状态/计数/节拍 + 启动停止复位。"""
    img = Image.new("RGB", (W, H), C_BG)
    d = ImageDraw.Draw(img)
    f14, f16, f18, f20 = _font(14), _font(16), _font(18), _font(20, True)

    _title_bar(d, "PLC-Robot 码垛演示线", "2026-08-16  10:20:35")

    # 状态面板
    _panel(d, (16, 64, 470, 210), "运行状态", f16)
    _status_led(d, (34, 108), "运行状态：自动运行", True, f=f16)
    _status_led(d, (34, 140), "伺服使能：ON", True, f=f16)
    _status_led(d, (34, 172), "机器人：自动", True, f=f16)
    _status_led(d, (250, 108), "夹爪：吸合", True, f=f16)
    _status_led(d, (250, 140), "原点：已到位", True, f=f16)
    _status_led(d, (250, 172), "报警：无", True, C_GREEN, f=f16)

    # 计数面板
    _panel(d, (486, 64, 784, 210), "生产计数", f16)
    d.text((504, 106), "当前计数", fill=C_TEXT, font=f14)
    d.text((660, 100), "24", fill=C_TITLE, font=_font(30, True))
    d.text((716, 112), "件", fill=C_TEXT, font=f14)
    d.text((504, 146), "目标产量", fill=C_TEXT, font=f14)
    d.text((660, 140), "48", fill=C_TITLE, font=_font(30, True))
    d.text((716, 152), "件", fill=C_TEXT, font=f14)
    d.text((504, 182), "当前层数", fill=C_TEXT, font=f14)
    d.text((660, 176), "2 / 4", fill=C_TEXT, font=f18)
    d.text((504, 202), "节拍", fill=C_TEXT, font=f14)
    d.text((660, 196), "18.5 s", fill=C_GREEN, font=f18)

    # 操作按钮
    _button(d, (16, 226, 170, 288), "启  动", f20, fill=(214, 240, 220), outline=C_GREEN)
    _button(d, (186, 226, 340, 288), "停  止", f20, fill=(248, 222, 222), outline=C_RED)
    _button(d, (356, 226, 510, 288), "报警复位", f20)
    _button(d, (526, 226, 680, 288), "清零计数", f20)

    # 跳转
    _panel(d, (16, 306, 784, 380), "画面跳转", f16)
    _button(d, (34, 328, 264, 366), "→ 手动调试（权限≥2）", f16)
    _button(d, (282, 328, 512, 366), "→ 报警中心", f16)
    _button(d, (530, 328, 766, 366), "→ 参数设置", f16)

    # 页脚
    d.rectangle((0, H - 34, W, H), fill=(214, 220, 228))
    d.text((16, H - 27), "设备：TPC7062Ti  |  主界面（索引 0）", fill=C_TEXT, font=f14)
    hint = "按钮为瞬动型，写 M 位由 PLC 逻辑确认"
    tw = d.textlength(hint, font=f14)
    d.text((W - tw - 16, H - 27), hint, fill=(96, 104, 112), font=f14)
    return img


def screen_manual() -> Image.Image:
    """画面2：手动调试界面（索引 1）——需权限，含点动/回原点/信号强制。"""
    img = Image.new("RGB", (W, H), C_BG)
    d = ImageDraw.Draw(img)
    f14, f16 = _font(14), _font(16)

    _title_bar(d, "手动调试", "索引 1  ·  权限 ≥ 2")

    _panel(d, (16, 64, 380, 200), "伺服控制", f16)
    d.text((34, 106), "伺服使能", fill=C_TEXT, font=f16)
    _button(d, (140, 100, 210, 136), "ON", f16, fill=(214, 240, 220), outline=C_GREEN)
    _button(d, (218, 100, 288, 136), "OFF", f16, fill=(248, 222, 222), outline=C_RED)
    _status_led(d, (300, 106), "ON", True, f=f16)
    d.text((34, 150), "伺服点动", fill=C_TEXT, font=f16)
    _button(d, (140, 144, 220, 180), "<< 反转", f16)
    _button(d, (228, 144, 312, 180), "正转 >>", f16)
    d.text((34, 232), "点动速度", fill=C_TEXT, font=f16)
    _button(d, (140, 226, 240, 262), "20 kHz", f16)

    _panel(d, (396, 64, 784, 200), "原点与强制测试", f16)
    d.text((414, 106), "回原点", fill=C_TEXT, font=f16)
    _button(d, (500, 100, 620, 136), "执行回零", f16)
    _status_led(d, (640, 106), "已到位", True, f=f16)
    d.text((414, 150), "信号强制（仅调试）", fill=C_TEXT, font=f14)
    _button(d, (414, 172, 570, 208), "三色灯测试", f16)
    _button(d, (586, 172, 742, 208), "蜂鸣器测试", f16)

    # 警告条
    d.rectangle((16, 300, 784, 344), fill=(252, 240, 214), outline=C_AMBER, width=2)
    d.text((34, 313), "⚠ 手动模式机器人请用手动操纵器，本屏不控制机器人",
           fill=(150, 96, 10), font=f16)

    _button(d, (16, 360, 200, 400), "← 返回主界面", f16)
    d.rectangle((0, H - 34, W, H), fill=(214, 220, 228))
    d.text((16, H - 27), "进入本画面需密码（权限等级≥2），并强制 PLC 切手动",
           fill=C_TEXT, font=f14)
    return img


def screen_alarm() -> Image.Image:
    """画面3：报警中心（索引 2）——实时报警 + 历史 + 复位。"""
    img = Image.new("RGB", (W, H), C_BG)
    d = ImageDraw.Draw(img)
    f13, f14, f16 = _font(13), _font(14), _font(16)

    _title_bar(d, "报警中心", "索引 2")

    _panel(d, (16, 64, 784, 118), "当前报警", f16)
    _status_led(d, (34, 94), "无未复位报警——系统可正常运行", True, C_GREEN, f=f16)

    # 报警历史表
    _panel(d, (16, 130, 784, 344), "报警历史（最近 10 条）", f16)
    cols = [(34, "时间"), (150, "报警内容"), (500, "等级"), (600, "状态")]
    for x, name in cols:
        d.text((x, 172), name, fill=C_TITLE, font=f14)
    d.line((30, 194, 770, 194), fill=C_BORDER, width=2)

    rows = [
        ("10:18:02", "伺服未使能，启动被拒绝", "提示", "已消除"),
        ("10:12:41", "夹爪真空度低，抓取失败", "一般", "已复位"),
        ("09:58:17", "机器人非自动模式，无法启动", "提示", "已消除"),
        ("09:41:33", "计数达到目标 48 件，自动停机", "提示", "已确认"),
        ("09:22:08", "急停按钮被按下", "严重", "已复位"),
    ]
    y = 204
    for t, msg, lvl, st in rows:
        color = C_RED if lvl == "严重" else (C_AMBER if lvl == "一般" else C_GRAY)
        d.text((34, y), t, fill=C_TEXT, font=f13)
        d.text((150, y), msg, fill=C_TEXT, font=f13)
        d.text((500, y), lvl, fill=color, font=f13)
        d.text((600, y), st, fill=C_GREEN, font=f13)
        y += 27

    _button(d, (16, 362, 240, 404), "报警复位", f16, fill=(248, 222, 222), outline=C_RED)
    _button(d, (256, 362, 480, 404), "报警确认", f16)
    _button(d, (496, 362, 720, 404), "清除历史", f16)
    d.text((536, 424), "严重级需现场确认后方可复位", fill=(96, 104, 112), font=f13)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        ("画面1_主界面.png", screen_main()),
        ("画面2_手动调试.png", screen_manual()),
        ("画面3_报警中心.png", screen_alarm()),
    ]
    for name, img in outputs:
        path = OUT_DIR / name
        img.save(path, "PNG", optimize=True)
        print(f"已生成 {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")
    print(f"\n共 {len(outputs)} 张，分辨率 {W}×{H}（TPC7062Ti）")


if __name__ == "__main__":
    main()
