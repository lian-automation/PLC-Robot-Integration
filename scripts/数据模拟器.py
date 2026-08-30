# -*- coding: utf-8 -*-
"""
数据模拟器.py —— PLC采集数据模拟 + 实时曲线 + 历史保存 + 报表导出

功能:
    1. 模拟PLC采集的三相电压/电流/温度数据(随机游走+向额定回归+启动冲击+停机窗口)
    2. matplotlib 实时绘制曲线(--plot)
    3. 曲线保存为PNG(--save-fig, 不弹窗口, 可用于生成README配图)
    4. 历史数据滚动保存CSV
    5. 统计报表导出: 均值/峰值/报警次数/可用率(txt)
       状态判定: 启动冲击段(前5点)豁免过流判定, 属正常工艺
    6. 故障注入(--fault): 向指定进度窗口注入扰动, 使"预警/故障"判定
       分支真实可达(用于演示报警统计与联调用例):
         volt_sag     电压跌落(向348V回归, 越过故障阈值353.4V)
         overcurrent  过载(负荷抬升至约38A, 爬升段穿预警带, 平台段越故障限36A)
         overtemp     温升(平衡温度叠加16℃, 越过75℃预警限)

用法:
    python scripts/数据模拟器.py --samples 600 --plot
    python scripts/数据模拟器.py --samples 600 --fault volt_sag,overcurrent,overtemp \
        --save-fig docs/images/监控曲线示例.png --report --output docs/数据示例.csv
    python scripts/数据模拟器.py --samples 600 --interval 1 -o data/plc_log.csv

依赖: 仅标准库即可生成CSV; --plot/--save-fig 需要 matplotlib (pip install matplotlib)
"""

import argparse
import csv
import os
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

CSV_HEADER = ["时间戳", "Uab(V)", "Ubc(V)", "Uca(V)",
              "Ia(A)", "Ib(A)", "Ic(A)", "温度(℃)", "状态"]

# 故障注入场景: 场景名 -> (起始相对进度, 结束相对进度)
# 窗口互相错开且避开停机窗口(0.4~0.55), 便于在曲线上区分观察
FAULT_SCENARIOS = {
    "volt_sag":     (0.15, 0.30),
    "overcurrent":  (0.55, 0.75),
    "overtemp":     (0.80, 0.92),
}


def clamp(value, low, high):
    """限制随机游走值不超出物理合理范围"""
    return max(low, min(high, value))


@dataclass
class SimConfig:
    """仿真参数(按现场整定值填入)"""
    nominal_voltage: float = 380.0     # 额定线电压 V
    nominal_current: float = 20.0      # 额定电流 A
    startup_surge: float = 3.2         # 启动冲击倍数
    ambient_temp: float = 28.0         # 环境温度 ℃
    volt_warn: float = 372.0           # 电压预警限 V
    curr_warn: float = 24.0            # 电流预警限 A
    temp_warn: float = 75.0            # 温度预警限 ℃
    stop_window: tuple = (0.4, 0.55)   # 相对总时长的停机窗口


@dataclass
class Sample:
    """单个采样点"""
    ts: str
    voltages: tuple
    currents: tuple
    temp: float
    status: str

    def as_row(self):
        return [self.ts,
                *(f"{v:.1f}" for v in self.voltages),
                *(f"{i:.1f}" for i in self.currents),
                f"{self.temp:.1f}", self.status]


class PLCDataSimulator:
    """状态化数据源: 电压/电流/温度随机游走 + 启动冲击 + 停机窗口"""

    def __init__(self, cfg: SimConfig, total: int, faults=None):
        self.cfg = cfg
        self.total = max(1, total)
        self.faults = set(faults or ())
        self.va = self.vb = self.vc = cfg.nominal_voltage
        self.ia = self.ib = self.ic = 0.0
        self.temp = cfg.ambient_temp
        self.idx = 0

    def _in_fault_window(self, name) -> bool:
        """当前采样点是否落在指定故障注入场景的进度窗口内"""
        if name not in self.faults:
            return False
        lo, hi = FAULT_SCENARIOS[name]
        return lo <= self.idx / self.total < hi

    def _running(self) -> bool:
        """按相对进度判断当前是否处于停机窗口"""
        frac = self.idx / self.total
        lo, hi = self.cfg.stop_window
        return not (lo <= frac <= hi)

    def _next_voltage(self, prev):
        if self._in_fault_window("volt_sag"):
            # 注入电压跌落: 向348V回归(低于故障阈值353.4V), 使故障分支可达
            return clamp(prev + (348.0 - prev) * 0.3 + random.gauss(0, 0.8),
                         340.0, 400.0)
        return clamp(prev + random.gauss(0, 0.8), 360.0, 400.0)

    def _next_current(self, prev, running):
        cfg = self.cfg
        if not running:
            return 0.0
        if self._in_fault_window("overcurrent"):
            # 注入过载: 负荷抬升至约38A——爬升段穿越24A预警带,
            # 平台段越过36A故障限, 预警/故障分支均真实可达
            pull = (cfg.nominal_current * 1.9 - prev) * 0.15
            return clamp(prev + pull + random.gauss(0, 0.4), 2.0, 40.0)
        if self.idx < 5:  # 启动冲击段
            return clamp(cfg.nominal_current * cfg.startup_surge
                         * random.uniform(0.85, 1.1), 0.0, 80.0)
        if self.idx == 5:  # 冲击结束, 直接回落到额定负荷电流附近
            return clamp(cfg.nominal_current * random.uniform(0.9, 1.1),
                         2.0, 40.0)
        # 随机游走+向额定值回归, 避免无界漂移后长期贴上限误报故障
        pull = (cfg.nominal_current - prev) * 0.08
        return clamp(prev + pull + random.gauss(0, 0.4), 2.0, 40.0)

    def _next_temp(self, prev, current):
        # 热增益1.8: 额定负荷平衡温度约64℃, 相对75℃预警限留足裕量
        target = self.cfg.ambient_temp + current * 1.8
        if self._in_fault_window("overtemp"):
            # 注入温升: 平衡温度叠加16℃, 越过75℃预警限(热惯性缓慢爬升)
            target += 16.0
        return clamp(prev + (target - prev) * 0.05 + random.gauss(0, 0.2),
                     self.cfg.ambient_temp - 2.0, 95.0)

    def _judge(self, startup=False):
        """状态判定: 启动冲击属正常工艺, 该段不做过流/过载判定"""
        cfg = self.cfg
        if min(self.va, self.vb, self.vc) < cfg.volt_warn * 0.95:
            return "故障"
        if startup:
            return "正常"
        if max(self.ia, self.ib, self.ic) > cfg.curr_warn * 1.5:
            return "故障"
        if max(self.ia, self.ib, self.ic) > cfg.curr_warn \
           or self.temp > cfg.temp_warn:
            return "预警"
        return "正常"

    def step(self, clock: datetime) -> Sample:
        running = self._running()
        startup = self.idx < 5           # 启动冲击段(判定豁免用)
        self.va = self._next_voltage(self.va)
        self.vb = self._next_voltage(self.vb)
        self.vc = self._next_voltage(self.vc)
        self.ia = self._next_current(self.ia, running)
        self.ib = self._next_current(self.ib, running)
        self.ic = self._next_current(self.ic, running)
        avg_i = statistics.mean((self.ia, self.ib, self.ic)) if running else 0.0
        self.temp = self._next_temp(self.temp, avg_i)
        ts = clock.strftime("%Y-%m-%d %H:%M:%S")
        sample = Sample(ts, (self.va, self.vb, self.vc),
                        (self.ia, self.ib, self.ic), self.temp,
                        self._judge(startup))
        self.idx += 1
        return sample


class HistoryLogger:
    """CSV历史记录器: 按行写入, 自动建目录, 周期性刷盘"""

    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.fh = open(path, "w", newline="", encoding="utf-8-sig")
        self.writer = csv.writer(self.fh)
        self.writer.writerow(CSV_HEADER)
        self.path = path
        self.count = 0

    def write(self, sample: Sample):
        self.writer.writerow(sample.as_row())
        self.count += 1
        if self.count % 100 == 0:
            self.fh.flush()

    def close(self):
        self.fh.flush()
        self.fh.close()


class ReportExporter:
    """统计报表: 从内存样本计算均值/峰值/报警次数/运行率并写txt"""

    def __init__(self, samples):
        self.samples = samples

    def _stats(self):
        volts = [v for s in self.samples for v in s.voltages]
        currs = [i for s in self.samples for i in s.currents]
        temps = [s.temp for s in self.samples]
        n_fault = sum(1 for s in self.samples if s.status == "故障")
        n_warn = sum(1 for s in self.samples if s.status == "预警")
        n_run = sum(1 for s in self.samples if max(s.currents) > 0.5)
        uptime = n_run / max(1, len(self.samples)) * 100.0
        return {
            "样本数": len(self.samples),
            "电压均值(V)": f"{statistics.mean(volts):.1f}",
            "电压最低(V)": f"{min(volts):.1f}",
            "电流峰值(A)": f"{max(currs):.1f}",
            "电流均值(A)": f"{statistics.mean(currs):.1f}",
            "温度最高(℃)": f"{max(temps):.1f}",
            "故障次数": n_fault,
            "预警次数": n_warn,
            "运行率(%)": f"{uptime:.1f}",
        }

    def export(self, prefix="report"):
        stats = self._stats()
        txt_path = f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 46 + "\n")
            f.write("  PLC采集数据统计报表  自动生成\n")
            f.write(f"  生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write("=" * 46 + "\n")
            for key, value in stats.items():
                f.write(f"  {key:<12}: {value}\n")
            f.write("=" * 46 + "\n")
        print(f"报表已导出 -> {txt_path}")
        return txt_path


class LivePlotter:
    """曲线绘制: --plot时逐帧刷新; --save-fig时仅离屏渲染最终曲线"""

    def __init__(self, maxlen=600, interactive=True):
        if not HAS_MPL:
            raise RuntimeError("未安装matplotlib, 请 pip install matplotlib")
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
        plt.rcParams["axes.unicode_minus"] = False
        self.interactive = interactive
        self.maxlen = maxlen
        self.data = {k: [] for k in
                     ("t", "Uab", "Ubc", "Uca", "Ia", "Ib", "Ic", "Temp")}
        self.fig, self.axes = plt.subplots(3, 1, figsize=(9, 7))
        (self.ax_v, self.ax_i, self.ax_t) = self.axes
        try:
            self.fig.canvas.manager.set_window_title("PLC数据实时监控")
        except Exception:
            pass  # 部分后端不支持设置窗口标题
        for ax, title, unit in ((self.ax_v, "线电压", "V"),
                                (self.ax_i, "相电流", "A"),
                                (self.ax_t, "绕组温度", "℃")):
            ax.set_title(title)
            ax.set_ylabel(unit)
            ax.grid(True, ls="--", alpha=0.4)
        self.fig.tight_layout()
        self.line_v, = self.ax_v.plot([], [], label="Uab")
        self.line_i, = self.ax_i.plot([], [], label="Ia")
        self.line_t, = self.ax_t.plot([], [], lw=2, color="r")

    def update(self, sample: Sample):
        d = self.data
        for key, val in zip(("Uab", "Ubc", "Uca"), sample.voltages):
            d[key].append(val)
        for key, val in zip(("Ia", "Ib", "Ic"), sample.currents):
            d[key].append(val)
        d["Temp"].append(sample.temp)
        d["t"].append(len(d["t"]))
        if len(d["t"]) > self.maxlen:      # 滚动窗口
            for key in d:
                d[key].pop(0)
        for line, ax, key in ((self.line_v, self.ax_v, "Uab"),
                              (self.line_i, self.ax_i, "Ia"),
                              (self.line_t, self.ax_t, "Temp")):
            line.set_data(d["t"], d[key])
            ax.relim()
            ax.autoscale_view()
        if self.interactive:
            plt.pause(0.01)
        else:
            self.fig.canvas.draw_idle()

    def save(self, path):
        """将当前曲线保存为PNG(用于README配图等)"""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"曲线图已保存 -> {path}")

    def keep(self):
        plt.show(block=True)


def parse_args():
    p = argparse.ArgumentParser(description="PLC数据模拟器(曲线/历史/报表)")
    p.add_argument("-n", "--samples", type=int, default=600, help="采样点数")
    p.add_argument("-i", "--interval", type=float, default=1.0, help="采样间隔秒")
    p.add_argument("-o", "--output", default="data/plc_log.csv", help="历史CSV路径")
    p.add_argument("--plot", action="store_true", help="显示实时曲线窗口")
    p.add_argument("--save-fig", default=None,
                   help="结束后将曲线保存为PNG(不弹窗口)")
    p.add_argument("--report", action="store_true", help="结束导出统计报表")
    p.add_argument("--fault", default=None,
                   help="故障注入场景, 逗号分隔: volt_sag,overcurrent,overtemp"
                        "(缺省不注入, 即纯正常工况)")
    return p.parse_args()


def parse_faults(spec):
    """解析--fault参数, 校验场景名"""
    if not spec:
        return ()
    names = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [s for s in names if s not in FAULT_SCENARIOS]
    if unknown:
        raise SystemExit(f"未知故障场景: {', '.join(unknown)}; "
                         f"可选: {', '.join(FAULT_SCENARIOS)}")
    return names


def main():
    args = parse_args()
    cfg = SimConfig()
    faults = parse_faults(args.fault)
    sim = PLCDataSimulator(cfg, args.samples, faults=faults)
    logger = HistoryLogger(args.output)
    samples = []
    clock = datetime.now()
    plotter = None
    want_fig = (args.plot or args.save_fig) and HAS_MPL
    if (args.plot or args.save_fig) and not HAS_MPL:
        print("[提示] 未安装matplotlib, 曲线功能跳过, 仅生成CSV")

    try:
        for _ in range(args.samples):
            clock += timedelta(seconds=args.interval)
            sample = sim.step(clock)
            samples.append(sample)
            logger.write(sample)
            if want_fig:
                plotter = plotter or LivePlotter(interactive=args.plot)
                plotter.update(sample)
                if args.plot:
                    time.sleep(min(args.interval, 0.05))  # 演示用加速
    except KeyboardInterrupt:
        print("\n用户中断, 保存已有数据")
    finally:
        logger.close()

    print(f"历史数据已保存 -> {logger.path} (共{logger.count}条)")
    if plotter and args.save_fig:
        plotter.save(args.save_fig)
    if args.report and samples:
        ReportExporter(samples).export()


if __name__ == "__main__":
    main()
