# -*- coding: utf-8 -*-
"""
模拟数据生成器.py (轻量版, 纯标准库)
模拟PLC采集的三相电压、三相电流、绕组温度数据, 保存为CSV文件。
用途: 为上位机(HMI/Python监控)联调提供离线测试数据, 不占用真实PLC。
与 数据模拟器.py 的区别: 本脚本不依赖matplotlib, 只生成CSV。

用法示例:
    python 模拟数据生成器.py -n 600 -i 1 -o plc_data.csv
"""

import argparse
import csv
import random
import time
from datetime import datetime, timedelta

# ---------- 模拟参数(按现场整定) ----------
NOMINAL_VOLTAGE = 380.0      # 额定线电压 V
NOMINAL_CURRENT = 20.0       # 额定电流 A
STARTUP_SURGE = 3.2          # 启动冲击倍数
AMBIENT_TEMP = 28.0          # 环境温度 ℃
MAX_TEMP = 75.0              # 温度报警限 ℃
VOLT_WARN, CURR_WARN = 372.0, 24.0  # 电压/电流报警限


def clamp(v, low, high):
    """限制随机游走值不超出物理合理范围"""
    return max(low, min(high, v))


def next_voltage(prev):
    """电压: 围绕额定值小幅波动"""
    return clamp(prev + random.gauss(0, 0.8), 360.0, 400.0)


def next_current(prev, sample_idx, running):
    """电流: 停机=0, 前5点启动冲击后回落到额定附近并小幅波动"""
    if not running:
        return 0.0
    if sample_idx < 5:
        return clamp(NOMINAL_CURRENT * STARTUP_SURGE * random.uniform(0.85, 1.1),
                     0.0, 80.0)
    if sample_idx == 5:     # 冲击结束, 直接回落到额定负荷电流附近
        return clamp(NOMINAL_CURRENT * random.uniform(0.9, 1.1), 2.0, 40.0)
    # 随机游走+向额定值回归, 避免无界漂移后长期贴上限误报故障
    pull = (NOMINAL_CURRENT - prev) * 0.08
    return clamp(prev + pull + random.gauss(0, 0.4), 2.0, 40.0)


def next_temp(prev, current):
    """温度: 随电流负荷缓慢爬升; 热增益1.8使额定平衡约64℃, 留足裕量"""
    target = AMBIENT_TEMP + current * 1.8
    return clamp(prev + (target - prev) * 0.05 + random.gauss(0, 0.2),
                 AMBIENT_TEMP - 2.0, 95.0)


def judge_status(voltages, currents, temp, startup=False):
    """根据限值给出综合状态字; 启动冲击属正常工艺, 该段不判过流"""
    if min(voltages) < VOLT_WARN * 0.95:
        return "故障"
    if startup:
        return "正常"
    if max(currents) > CURR_WARN * 1.5:
        return "故障"
    if max(currents) > CURR_WARN or temp > MAX_TEMP:
        return "预警"
    return "正常"


def main():
    parser = argparse.ArgumentParser(description="PLC采集数据模拟生成器(轻量版)")
    parser.add_argument("-n", "--samples", type=int, default=600, help="采样点数")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="采样间隔(秒)")
    parser.add_argument("-o", "--output", type=str, default="plc_data.csv", help="输出CSV文件名")
    parser.add_argument("--offline", action="store_true",
                        help="在40%~60%进度处模拟停机30个采样点")
    args = parser.parse_args()

    random.seed()                      # 每次运行结果不同
    start_time = datetime.now()
    va = vb = vc = NOMINAL_VOLTAGE
    ia = ib = ic = 0.0
    temp = AMBIENT_TEMP
    shutdown_start = random.randint(int(args.samples * 0.4), int(args.samples * 0.6))

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["时间戳", "Uab(V)", "Ubc(V)", "Uca(V)",
                         "Ia(A)", "Ib(A)", "Ic(A)", "绕组温度(℃)", "状态"])
        for idx in range(args.samples):
            ts = (start_time + timedelta(seconds=idx * args.interval)
                  ).strftime("%Y-%m-%d %H:%M:%S")
            # 停机窗口: 电流为0, 温度缓慢回落
            running = not (args.offline and shutdown_start <= idx < shutdown_start + 30)
            va, vb, vc = (next_voltage(va), next_voltage(vb), next_voltage(vc))
            ia = next_current(ia, idx, running)
            ib = next_current(ib, idx, running)
            ic = next_current(ic, idx, running)
            temp = next_temp(temp, (ia + ib + ic) / 3 if running else 0.0)
            status = judge_status((va, vb, vc), (ia, ib, ic), temp,
                                  startup=(idx < 5))
            writer.writerow([ts, f"{va:.1f}", f"{vb:.1f}", f"{vc:.1f}",
                             f"{ia:.1f}", f"{ib:.1f}", f"{ic:.1f}",
                             f"{temp:.1f}", status])
            # 离线生成不等待; 若要模拟实时节拍可取消下一行注释
            # time.sleep(args.interval)

    print(f"已生成 {args.samples} 条记录 -> {args.output}")


if __name__ == "__main__":
    main()
