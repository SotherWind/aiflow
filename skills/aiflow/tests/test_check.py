#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aiflow check.py 的正常放行与假绿反例测试。仅使用标准库。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
CHECK = SKILL_ROOT / "scripts" / "check.py"
TEST_PARENT = os.environ.get("AIFLOW_TEST_TMP") or None
NAMES = [
    "00-intake.md", "01-research.md", "02-prd.md", "03-arch.md", "03-mapping.md",
    "04-tasks.md", "05-dev-log.md", "06-test-report.md", "07-bugs.md",
    "08-regression.md", "09-release.md",
]


def yaml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def dump_state(path, state):
    lines = []
    for key, value in state.items():
        if isinstance(value, list):
            if not value:
                lines.append("%s: []" % key)
            else:
                lines.append("%s:" % key)
                lines.extend("  - %s" % yaml_scalar(item) for item in value)
        elif isinstance(value, dict):
            if not value:
                lines.append("%s: {}" % key)
            else:
                lines.append("%s:" % key)
                lines.extend("  %s: %s" % (child, yaml_scalar(value[child])) for child in value)
        else:
            lines.append("%s: %s" % (key, yaml_scalar(value)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiflow-tests-", dir=TEST_PARENT)
        self.root = Path(self.temp.name)
        self.af = self.root / ".aiflow"
        self.arts = self.af / "artifacts"
        self.arts.mkdir(parents=True)
        self.state = None

    def tearDown(self):
        self.temp.cleanup()

    def write_af(self, relative, text):
        path = self.af / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_art(self, name, text):
        self.write_af("artifacts/" + name, text)

    def replace_art(self, name, old, new):
        path = self.arts / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def make_full(self):
        facts = """> 版本：v1

## 02 业务规则
| 编号 | 规则 | 来源 |
|---|---|---|
| R1 | 测试规则 | 已确认 |

## 04 验收标准
| 编号 | 验收标准 | 依据规则 | 能否写出失败用例 |
|---|---|---|---|
| A1 | 标准一 | R1 | 能 |
| A2 | 标准二 | R1 | 能 |

## 05 契约映射
| 验收标准 | 落点类型 | 落点 |
|---|---|---|
| A1 | 校验 | 约束一 |
| A2 | 校验 | 约束二 |
"""
        self.write_af("facts.md", facts)
        self.write_art("00-intake.md", "> 依据 facts v0 生成\n本轮做：测试\n")
        for name in ("01-research.md", "02-prd.md", "03-arch.md"):
            self.write_art(name, "> 依据 facts v1 生成\nA1 A2 R1\n")
        self.write_art("03-mapping.md", """> 依据 facts v1 生成
## 一、映射表
| 验收标准 | 落在哪 | 由哪条约束保证 | 谁实现 | 谁验证 |
|---|---|---|---|---|
| A1 | 约束一 | 数据层 | T1 | E1 |
| A2 | 约束二 | 服务层 | T2 | E2 |
## 二、无对应项
| 验收标准 | 为什么落不下去 | 退回动作 |
|---|---|---|
""")
        self.write_art("04-tasks.md", """> 依据 facts v1 生成
## 任务总览
| 编号 | 任务 | 类型 | 依赖 |
|---|---|---|---|
| T1 | 后端任务 | BE | — |
| T2 | 前端任务 | FE | T1 |
## 任务详情
### T1 · 后端任务
- 验收标准：A1
### T2 · 前端任务
- 验收标准：A2
""")
        self.write_art("05-dev-log.md", """> 依据 facts v1 生成
## 任务完成情况
| 编号 | 类型 | 任务 | 状态 |
|---|---|---|---|
| T1 | BE | 后端任务 | 完成 |
| T2 | FE | 前端任务 | 完成 |
""")
        self.write_art("06-test-report.md", """> 依据 facts v1 生成
## 一、按任务结论
| 任务 | 类型 | 用例数 | 通过 | 失败 | 结论 | 缺陷 |
|---|---|---|---|---|---|---|
| T1 | BE | 1 | 1 | 0 | 通过 | — |
| T2 | FE | 1 | 1 | 0 | 通过 | — |
## 三、验收标准覆盖
| 验收标准 | 对应用例 | 结果 |
|---|---|---|
| A1 | E1 | 通过 |
| A2 | E2 | 通过 |
""")
        self.write_art("07-bugs.md", """> 依据 facts v1 生成
## 汇总
| 编号 | 标题 | 关联任务 | 归属 | 状态 |
|---|---|---|---|---|
""")
        self.write_art("08-regression.md", """> 依据 facts v1 生成
## 二、执行结果
| 用例 | 验收标准 | 类型 | 结果 | 备注 |
|---|---|---|---|---|
| E1 | A1 | 全量验收 | 通过 | |
| E2 | A2 | 全量验收 | 通过 | |
## 四、结论
**结论：通过**
- 条件：无
- 用户确认：不适用
""")
        self.write_art("09-release.md", """> 依据 facts v1 生成
## 六、执行结果
- 状态：观察完成
- 实际执行时间：2026-10-27T09:00:00+08:00
- 证据：release-log-123
- 观察窗结论：指标正常
""")
        self.state = {
            "project": "fixture",
            "stage": 9,
            "expert": "operator",
            "mode": 1,
            "facts_version": 1,
            "artifacts": list(NAMES),
            "open_bugs": [],
            "pending_decisions": [],
            "decision_log": [],
            "task_status": {"T1": "done", "T2": "done"},
            "acceptance_results": {"A1": "pass", "A2": "pass"},
            "regression_result": "pass",
            "regression_conditions": [],
            "regression_user_confirmed": False,
            "release_status": "verified",
            "agent_sessions": {},
        }
        dump_state(self.af / "state.yaml", self.state)

    def run_check(self):
        if self.state is not None:
            dump_state(self.af / "state.yaml", self.state)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, str(CHECK), str(self.root)],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )

    def assert_pass(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_blocked(self, result, text=None):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        if text:
            self.assertIn(text, result.stdout)

    def test_bundled_stage0_templates_pass_without_facts(self):
        self.write_af("state.yaml", (SKILL_ROOT / "templates" / "state.yaml").read_text(encoding="utf-8"))
        self.write_art("00-intake.md", (SKILL_ROOT / "templates" / "intake.md").read_text(encoding="utf-8"))
        self.assert_pass(self.run_check())

    def test_valid_full_project_passes(self):
        self.make_full()
        self.assert_pass(self.run_check())

    def test_failed_regression_is_blocked(self):
        self.make_full()
        self.replace_art("08-regression.md", "**结论：通过**", "**结论：不通过**")
        self.state["regression_result"] = "fail"
        self.assert_blocked(self.run_check(), "回归不通过")

    def test_unconfirmed_conditional_regression_is_blocked(self):
        self.make_full()
        self.replace_art("08-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = False
        self.assert_blocked(self.run_check(), "未取得用户显式确认")

    def test_confirmed_conditional_regression_passes(self):
        self.make_full()
        self.replace_art("08-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = True
        self.assert_pass(self.run_check())

    def test_pending_bug_in_markdown_is_blocked_despite_empty_state(self):
        self.make_full()
        self.replace_art(
            "07-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 待复测 |\n\n### BUG-1 · 示例\n- 现象：失败\n",
        )
        self.assert_blocked(self.run_check(), "缺陷未清零")

    def test_open_bug_yaml_block_list_is_blocked(self):
        self.make_full()
        self.replace_art(
            "07-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 待复测 |\n\n### BUG-1 · 示例\n- 现象：失败\n",
        )
        self.state["open_bugs"] = ["BUG-1"]
        self.assert_blocked(self.run_check(), "缺陷未清零")

    def test_closed_bug_with_real_retest_passes(self):
        self.make_full()
        self.replace_art(
            "07-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 已关闭 |\n\n### BUG-1 · 示例\n**复测结论**\n- 结论：**通过 → 已关闭**\n",
        )
        self.assert_pass(self.run_check())

    def test_unfinished_task_is_blocked(self):
        self.make_full()
        self.state["task_status"]["T2"] = "pending"
        self.replace_art("05-dev-log.md", "| T2 | FE | 前端任务 | 完成 |", "| T2 | FE | 前端任务 | 未开始 |")
        self.assert_blocked(self.run_check(), "任务未完成")

    def test_uncovered_acceptance_is_blocked(self):
        self.make_full()
        self.state["acceptance_results"]["A2"] = "uncovered"
        self.assert_blocked(self.run_check(), "验收标准未执行")

    def test_pending_decision_is_blocked(self):
        self.make_full()
        self.state["pending_decisions"] = ["Q1 待业务确认"]
        self.assert_blocked(self.run_check(), "仍有待决策")

    def test_missing_artifact_is_blocked_not_warning(self):
        self.make_full()
        (self.arts / "06-test-report.md").unlink()
        self.assert_blocked(self.run_check(), "缺少必需产物")

    def test_missing_facts_version_is_blocked(self):
        self.make_full()
        del self.state["facts_version"]
        self.assert_blocked(self.run_check(), "facts_version 缺失")

    def test_stale_artifact_is_blocked(self):
        self.make_full()
        self.write_af("facts.md", (self.af / "facts.md").read_text(encoding="utf-8").replace("版本：v1", "版本：v2"))
        self.state["facts_version"] = 2
        self.assert_blocked(self.run_check(), "产物版本过期")

    def test_invented_acceptance_id_is_blocked(self):
        self.make_full()
        self.write_art("03-arch.md", "> 依据 facts v1 生成\nA1 A2 R1 A99\n")
        self.assert_blocked(self.run_check(), "从未定义")

    def test_mapping_task_backfill_is_required(self):
        self.make_full()
        self.replace_art("03-mapping.md", "| A1 | 约束一 | 数据层 | T1 | E1 |", "| A1 | 约束一 | 数据层 | — | E1 |")
        self.assert_blocked(self.run_check(), "未在映射表回填任务")

    def test_closed_bug_without_retest_is_blocked(self):
        self.make_full()
        self.replace_art(
            "07-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 已关闭 |\n\n### BUG-1 · 示例\n- 现象：失败\n",
        )
        self.assert_blocked(self.run_check(), "缺少通过复测结论")

    def test_failed_regression_row_cannot_be_marked_pass(self):
        self.make_full()
        self.replace_art("08-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "| E2 | A2 | 全量验收 | 失败 | |")
        self.assert_blocked(self.run_check(), "回归存在未通过")

    def test_conditional_regression_requires_conditions(self):
        self.make_full()
        self.replace_art("08-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_user_confirmed"] = True
        self.assert_blocked(self.run_check(), "未记录条件")

    def test_release_requires_evidence(self):
        self.make_full()
        self.replace_art("09-release.md", "证据：release-log-123", "证据：")
        self.assert_blocked(self.run_check(), "缺少证据")

    def test_documented_failed_acceptance_cannot_be_hidden_by_state(self):
        self.make_full()
        self.replace_art("06-test-report.md", "| A2 | E2 | 通过 |", "| A2 | E2 | 失败 |")
        self.assert_blocked(self.run_check(), "验收结果不一致")

    def test_duplicate_bug_cannot_hide_open_status(self):
        self.make_full()
        self.replace_art(
            "07-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 待修复 |\n| BUG-1 | 示例 | T1 | BE | 已关闭 |\n\n### BUG-1 · 示例\n**复测结论**\n- 结论：**通过 → 已关闭**\n",
        )
        self.assert_blocked(self.run_check(), "重复缺陷编号")

    def test_regression_prose_does_not_count_as_execution(self):
        self.make_full()
        self.replace_art("08-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "")
        self.write_art("08-regression.md", (self.arts / "08-regression.md").read_text(encoding="utf-8") + "\n补充说明：A2\n")
        self.assert_blocked(self.run_check(), "未以有效通过用例覆盖")

    def test_unknown_regression_case_is_blocked(self):
        self.make_full()
        self.replace_art("08-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "| E999 | A2 | 全量验收 | 通过 | |")
        self.assert_blocked(self.run_check(), "阶段 6 未定义")

    def test_regression_case_cannot_be_cross_assigned(self):
        self.make_full()
        self.replace_art("08-regression.md", "| E1 | A1 | 全量验收 | 通过 | |", "| E1 | A2 | 全量验收 | 通过 | |")
        self.replace_art("08-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "| E2 | A1 | 全量验收 | 通过 | |")
        self.assert_blocked(self.run_check(), "关联不一致")

    def test_same_agent_cannot_be_developer_and_tester(self):
        self.make_full()
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:same", "tester": "agent:same"}
        self.assert_blocked(self.run_check(), "必须是独立身份")

    def test_stage3_cannot_invent_future_task_or_case(self):
        self.make_full()
        self.state["stage"] = 3
        self.state["artifacts"] = NAMES[:5]
        for name in NAMES[5:]:
            (self.arts / name).unlink()
        self.assert_blocked(self.run_check(), "不得预填")

    def test_unconfirmed_rule_is_blocked(self):
        self.make_full()
        self.replace_art("01-research.md", "A1 A2 R1", "A1 A2 R1")
        path = self.af / "facts.md"
        path.write_text(path.read_text(encoding="utf-8").replace("| R1 | 测试规则 | 已确认 |", "| R1 | 测试规则 | 假设 |"), encoding="utf-8")
        self.assert_blocked(self.run_check(), "业务规则尚未确认")

    def test_non_testable_acceptance_is_blocked(self):
        self.make_full()
        path = self.af / "facts.md"
        path.write_text(path.read_text(encoding="utf-8").replace("| A2 | 标准二 | R1 | 能 |", "| A2 | 标准二 | R1 | 不能 |"), encoding="utf-8")
        self.assert_blocked(self.run_check(), "缺少可失败用例")

    def test_legacy_acceptance_table_without_testable_column_passes(self):
        self.make_full()
        path = self.af / "facts.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("| 编号 | 验收标准 | 依据规则 | 能否写出失败用例 |", "| 编号 | 验收标准 | 依据规则 |")
        text = text.replace("|---|---|---|---|\n| A1", "|---|---|---|\n| A1", 1)
        text = text.replace("| A1 | 标准一 | R1 | 能 |", "| A1 | 标准一 | R1 |")
        text = text.replace("| A2 | 标准二 | R1 | 能 |", "| A2 | 标准二 | R1 |")
        path.write_text(text, encoding="utf-8")
        self.assert_pass(self.run_check())

    def test_conflicting_version_headers_are_blocked(self):
        self.make_full()
        self.replace_art("03-arch.md", "> 依据 facts v1 生成", "> 依据 facts v1 生成\n> 依据 facts v2 生成")
        self.assert_blocked(self.run_check(), "只有一条版本声明")

    def test_historical_conclusion_does_not_override_current(self):
        self.make_full()
        self.replace_art("08-regression.md", "## 四、结论\n", "## 四、结论\n上次结论：不通过\n")
        self.assert_pass(self.run_check())

    def test_task_cycle_is_blocked(self):
        self.make_full()
        self.replace_art("04-tasks.md", "| T1 | 后端任务 | BE | — |", "| T1 | 后端任务 | BE | T2 |")
        self.assert_blocked(self.run_check(), "依赖存在循环")

    def test_failed_acceptance_with_bug_can_complete_stage6(self):
        self.make_full()
        self.state["stage"] = 6
        self.state["artifacts"] = NAMES[:9]
        for name in NAMES[9:]:
            (self.arts / name).unlink()
        self.replace_art("06-test-report.md", "| T2 | FE | 1 | 1 | 0 | 通过 | — |", "| T2 | FE | 1 | 0 | 1 | 不通过 | BUG-1 |")
        self.replace_art("06-test-report.md", "| A2 | E2 | 通过 |", "| A2 | E2 | 失败 |")
        self.replace_art(
            "07-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T2 | FE | 待修复 |\n\n### BUG-1 · 示例\n- 关联验收：A2\n- 现象：失败\n",
        )
        self.state["open_bugs"] = ["BUG-1"]
        self.state["acceptance_results"]["A2"] = "fail"
        self.assert_pass(self.run_check())

    def test_mode3_requires_final_review(self):
        self.make_full()
        self.state["mode"] = 3
        self.state["agent_sessions"] = {"developer": "agent:dev", "tester": "agent:test"}
        self.assert_blocked(self.run_check(), "独立终验")

    def test_mode3_with_final_review_passes(self):
        self.make_full()
        self.state["mode"] = 3
        self.state["agent_sessions"] = {"developer": "agent:dev", "tester": "agent:test", "final_reviewer": "human:reviewer"}
        self.state["final_review_result"] = "pass"
        self.state["final_review_evidence"] = "review-record-123"
        self.assert_pass(self.run_check())

    def test_release_plan_is_not_success(self):
        self.make_full()
        self.state["release_status"] = "planned"
        self.replace_art("09-release.md", "状态：观察完成", "状态：计划中")
        self.assert_blocked(self.run_check(), "上线尚未完成")


if __name__ == "__main__":
    unittest.main(verbosity=2)
