# -*- coding: utf-8 -*-
"""
真值表复算.py —— 复算 docs/仿真测试用例.md 的期望值与 SCL 代码实际行为是否一致

原理:
    按 src/PLC_Logic.scl 中 FB_ServoCtrl / FB_FaultHandler 的扫描周期逻辑,
    在 Python 中逐行复刻, 对表1(24组互锁真值表 + R1~R3复位过渡步)按文档声明的
    "状态连续"方式链式推演, 对表2(8组故障注入)按行序注入推演, 将复算输出与
    文档期望值逐格比对。文档期望列改动或 SCL 逻辑改动导致不一致时, 本脚本报错。

用法:
    python scripts/真值表复算.py
    退出码: 0 = 全部一致; 1 = 存在不一致(打印差异明细)

依赖: 仅标准库。
注意: 本脚本复刻 src/PLC_Logic.scl 的行为; 若 SCL 逻辑变更,
      请同步修改 servo_scan / fault_scan 两个函数。
"""

import re
import sys
from pathlib import Path

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "仿真测试用例.md"

# 表1期望列在文档表中的列位置(0起): 9个输入列之后的 qEnable/qFwd/qRev/qAlarm
T1_OUT_COLS = (10, 11, 12, 13)


def servo_scan(lock, ins):
    """复刻 FB_ServoCtrl (src/PLC_Logic.scl 63-92行) 一个扫描周期的行为。

    ins = (PowerOn, EStopOK, Ready, Fault, Reset, JogF, JogR, SQ1, SQ2)
    返回 (锁存状态, qEnable, qFwd, qRev, qAlarm)
    """
    p, estop, ready, fault, rst, jf, jr, sq1, sq2 = ins
    # 1) 报警或急停断开立即锁存
    if fault or not estop:
        lock = True
    # 2) 双限位同时压合 = 接线故障, 同样锁存
    if sq1 and sq2:
        lock = True
    # 3) 故障源消失后按复位才解锁
    if rst and not fault and estop and not (sq1 and sq2):
        lock = False
    # 4) 使能综合条件
    q_enable = p and ready and not lock and estop
    # 5) 方向许可: 使能OK + 未压限位 + 双命令互斥
    q_fwd = q_enable and not sq1 and jf and not jr
    q_rev = q_enable and not sq2 and jr and not jf
    # qAlarm 即故障锁存位
    return lock, q_enable, q_fwd, q_rev, lock


# 表2各行的注入状态(F1~F6单故障, F7叠加, F8为F1/F2先后解除后未复位)
T2_INJECT = {
    "F1": {"estop_ok": False},
    "F2": {"door_ok": False},
    "F3": {"servo": True},
    "F4": {"robot": True},
    "F5": {"feed": True},
    "F6": {"hand": True},
    "F7": {"estop_ok": False, "door_ok": False},
    "F8": {},                       # 对应文档"F1、F2先后解除, 未复位" -> 显示首发码
}


def fault_scan(first_lock, first_code, inject):
    """复刻 FB_FaultHandler (src/PLC_Logic.scl 331-358行) 一个扫描周期的行为。

    返回 (首发锁存状态, 首发码, wFaultCode)
    """
    if not inject.get("estop_ok", True):
        cur = 0x0001
    elif not inject.get("door_ok", True):
        cur = 0x0002
    elif inject.get("servo", False):
        cur = 0x0003
    elif inject.get("robot", False):
        cur = 0x0004
    elif inject.get("feed", False):
        cur = 0x0005
    elif inject.get("hand", False):
        cur = 0x0006
    else:
        cur = 0x0000
    # 首发故障锁存: 直到复位前保持不变
    if cur != 0x0000 and not first_lock:
        first_code = cur
        first_lock = True
    if inject.get("reset", False) and cur == 0x0000:
        first_lock = False
        first_code = 0x0000
    # 输出: 有故障显示当前码, 无故障时保留首发码(历史)
    return first_lock, first_code, (cur if cur != 0x0000 else first_code)


def parse_table_rows(text, start_marker, end_marker):
    """截取 start_marker 与 end_marker 之间的 markdown 表格数据行"""
    section = text.split(start_marker, 1)[1].split(end_marker, 1)[0]
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("序号", "用例") \
                or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(cells)
    return rows


def b(cell):
    """表内 1/0 转布尔"""
    if cell not in ("0", "1"):
        raise ValueError(f"非法布尔值: {cell!r}")
    return cell == "1"


def main():
    text = DOC_PATH.read_text(encoding="utf-8")
    failures = []

    # ---------- 表1: FB_ServoCtrl 互锁真值表(状态连续, 链式执行) ----------
    t1_rows = parse_table_rows(text, "## 表1", "## 表2")
    lock = False                     # bFaultLock 初值
    for cells in t1_rows:
        no = cells[0]
        try:
            ins = tuple(b(cells[i]) for i in range(1, 10))
            lock, qe, qf, qr, qa = servo_scan(lock, ins)
            expect = [b(cells[c]) for c in T1_OUT_COLS]
            actual = [int(qe), int(qf), int(qr), int(qa)]
        except (ValueError, IndexError) as exc:
            failures.append(f"表1 {no}: 行解析失败({exc})")
            continue
        if actual != expect:
            diff = [name for name, e, a in
                    zip(("qEnable", "qFwd", "qRev", "qAlarm"), expect, actual)
                    if e != a]
            failures.append(
                f"表1 {no}: 期望={expect} 复算={actual} (不符列: {', '.join(diff)})")

    # ---------- 表2: FB_FaultHandler 故障注入(按行序注入, 首发锁存跨行保持) ----------
    t2_rows = parse_table_rows(text, "## 表2", "## 表3")
    first_lock, first_code = False, 0x0000
    for cells in t2_rows:
        no = cells[0]
        m = re.search(r"16#([0-9A-Fa-f]{4})", cells[2])
        if no not in T2_INJECT or not m:
            failures.append(f"表2 {no}: 行解析失败")
            continue
        first_lock, first_code, code = fault_scan(
            first_lock, first_code, T2_INJECT[no])
        expect = int(m.group(1), 16)
        if code != expect:
            failures.append(
                f"表2 {no}: 期望=16#{expect:04X} 复算=16#{code:04X}")

    # ---------- 汇总 ----------
    total = len(t1_rows) + len(t2_rows)
    print(f"复算范围: 表1 {len(t1_rows)} 行(FB_ServoCtrl, 链式) + "
          f"表2 {len(t2_rows)} 行(FB_FaultHandler, 顺序注入) = {total} 行")
    print(f"对照文档: {DOC_PATH.name}")
    print(f"对照代码: src/PLC_Logic.scl (FB_ServoCtrl / FB_FaultHandler)")
    if failures:
        print(f"\n[不一致] 共 {len(failures)} 处:")
        for item in failures:
            print(f"  - {item}")
        sys.exit(1)
    print("\n[全部一致] 文档期望值与 SCL 代码复算行为逐行吻合")


if __name__ == "__main__":
    main()
