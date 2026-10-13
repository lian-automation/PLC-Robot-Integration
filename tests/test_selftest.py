# -*- coding: utf-8 -*-
"""
tests/test_selftest.py —— 把本仓的验证脚本统一收进 pytest 入口
==============================================================

本仓是"PLC + 机器人集成"的工程交付物仓库：核心逻辑在
`src/PLC_Logic.scl`（SCL 源码）与 `docs/仿真测试用例.md`（期望值表），
验证手段是 `scripts/真值表复算.py`——它逐行复算 35 行期待值，
断言"文档期望值 == SCL 代码复算行为"。该脚本同时也是 CI 的唯一测试步骤。

本文件把它包装成 pytest 用例，使 13 个仓具备统一的一键验证入口：

    python -m pytest tests -q

被测命令（与 .github/workflows/ci.yml 同源）：
  scripts/真值表复算.py   表1 27 行(FB_ServoCtrl 链式) + 表2 8 行(FB_FaultHandler)

说明：真值表复算脚本是权威实现，此处只做编排与退出码/关键结论断言，
      不重复实现比对逻辑（避免两处口径漂移）。
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

RECHECK_SCRIPT = "scripts/真值表复算.py"


def _run_recheck():
    return subprocess.run(
        [sys.executable, RECHECK_SCRIPT],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


@pytest.fixture(scope="module")
def recheck_result():
    return _run_recheck()


def test_truth_table_recheck_exit_zero(recheck_result):
    """真值表复算：文档期望值与 SCL 逻辑逐行吻合时退出码为 0。"""
    assert recheck_result.returncode == 0, (
        f"真值表复算失败（exit={recheck_result.returncode}）\n"
        f"--- stdout 尾部 ---\n{recheck_result.stdout[-1500:]}\n"
        f"--- stderr 尾部 ---\n{recheck_result.stderr[-800:]}"
    )


def test_recheck_reports_full_coverage(recheck_result):
    """复算范围必须覆盖两张真值表（27 + 8 = 35 行），防止脚本被改窄。"""
    out = recheck_result.stdout
    assert "35" in out, f"复算输出未见 35 行口径，实际输出：{out[:500]}"
    assert "全部一致" in out, f"复算未报告'全部一致'，实际输出：{out[:500]}"


def test_recheck_script_exists():
    """确保被测脚本与文档引用的路径一致。"""
    assert (ROOT / RECHECK_SCRIPT).is_file(), f"{RECHECK_SCRIPT} 不存在"
    assert (ROOT / "docs" / "仿真测试用例.md").is_file(), "期望值文档缺失"
    assert (ROOT / "src" / "PLC_Logic.scl").is_file(), "SCL 源码缺失"
