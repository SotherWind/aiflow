#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aiflow check.py 的正常放行与假绿反例测试。仅使用标准库。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
CHECK = SKILL_ROOT / "scripts" / "check.py"
TEST_PARENT = os.environ.get("AIFLOW_TEST_TMP") or None
CORE_NAMES = [
    "00-intake.md", "01-research.md", "02-prd.md", "04-arch.md", "04-mapping.md",
    "05-tasks.md", "06-dev-log.md", "08-test-report.md", "09-bugs.md",
    "10-regression.md", "11-release.md",
]
DESIGN_NAMES = ["02-prototype.md", "03-design.md", "07-walkthrough.md"]


def template(name):
    return (SKILL_ROOT / "templates" / name).read_text(encoding="utf-8")


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


FACTS = """> 版本：v1

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
CONFIRM = """
## 评审记录
| 轮次 | 编号 | 用户反馈（原话） | 处理 | 状态 |
|---|---|---|---|---|
| 1 | F1 | 「示例反馈」 | 已按反馈修改 | 已处理 |

## 用户确认
- 确认结论：已确认
- 用户原话：「确认，往下走」
- 确认时间：2026-11-01T10:00:00+08:00
"""
QUESTIONS = """## 台账
| 编号 | 提出阶段 | 问题 | 影响 | 依赖 | 推荐答案 | 用户答复（原话） | 状态 | 备注 |
|---|---|---|---|---|---|---|---|---|
| Q1 | 0 | 示例问题 | R1 | — | 推荐甲 | 「选甲」 | 已解决 | |
"""

DESIGN_SYSTEM = """# 设计规范
- 来源：无，按 Ant Design 默认主题
- 依据：问题台账 Q1
"""


def prd_doc(prototype, design):
    return """> 依据 facts v1 生成
A1 A2 R1

## 七、交付形态判断
| 交付物 | 是否需要 | 理由 |
|---|---|---|
| 产品原型 | %s | 示例理由 |
| 设计稿 | %s | 示例理由 |
""" % ("需要" if prototype else "不需要", "需要" if design else "不需要") + CONFIRM


PROTOTYPE = """> 依据 facts v1 生成

## 二、页面清单
| 页面 | 名称 | 用途 | 服务的验收标准 | 文件 |
|---|---|---|---|---|
| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |

## 三、页面说明

### P1 · 列表页
- 字段：编号、状态
""" + CONFIRM

DESIGN = """> 依据 facts v1 生成

## 一、页面与设计稿
| 页面 | 名称 | 设计稿 |
|---|---|---|
| P1 | 列表页 | design/P1.html |

## 三、交互标注
| 编号 | 页面 | 触发 | 响应与细节 |
|---|---|---|---|
| I1 | P1 | 点击受理 | loading 后提示已受理 |

## 四、走查点清单（阶段 7 还原度的分母）
| 走查点 | 页面 | 维度 | 设计要求 | 关键项 |
|---|---|---|---|---|
| W1 | P1 | 页面 | 从主流程能到达本页 | 是 |
| W2 | P1 | 交互 | I1 按标注实现 | 是 |
""" + "".join("| W%d | P1 | 间距 | 要求 %d | 否 |\n" % (n, n) for n in range(3, 11)) + CONFIRM


def walkthrough_doc(results, score, conclusion, issues=""):
    """results: [(轮次, 走查点, 结果)]；issues: 问题单表格行与详情。"""
    rows = "".join("| %d | %s | %s | | shots/r%d-%s.png |\n" % (r, w, res, r, w) for r, w, res in results)
    return """> 依据 facts v1 生成
- 走查对象：http://localhost:5173

## 一、走查记录
| 轮次 | 走查点 | 结果 | 偏差说明 | 证据 |
|---|---|---|---|---|
%s
## 二、还原度
- 最终还原度：%s
- 结论：%s

## 三、走查问题单
| 编号 | 走查点 | 页面 | 关键项 | 状态 |
|---|---|---|---|---|
%s""" % (rows, score, conclusion, issues)


ALL_PASS = [(1, "W%d" % n, "通过") for n in range(1, 11)]


def ux_issue(identifier, point, status, closed=False):
    detail = "\n### %s · 偏差\n- 走查点：%s\n" % (identifier, point)
    if closed:
        detail += "**复查结论**\n- 结论：**通过 → 已关闭**\n"
    return "| %s | %s | P1 | 否 | %s |\n" % (identifier, point, status), detail


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

    def make_full(self, design=True):
        """阶段 11 的完整项目。design=True 时含原型、设计稿与设计走查。"""
        self.design = design
        self.write_af("facts.md", FACTS)
        self.write_af("questions.md", QUESTIONS)
        self.write_art("00-intake.md", "> 依据 facts v0 生成\n本轮做：测试\n" + CONFIRM)
        self.write_art("01-research.md", "> 依据 facts v1 生成\nA1 A2 R1\n" + CONFIRM)
        self.write_art("02-prd.md", prd_doc(design, design))
        self.write_art("04-arch.md", "> 依据 facts v1 生成\nA1 A2 R1\n")
        if design:
            self.write_art("02-prototype.md", PROTOTYPE)
            self.write_art("03-design.md", DESIGN)
            self.write_art("07-walkthrough.md", walkthrough_doc(ALL_PASS, "10/10", "通过"))
            self.write_af("prototype/P1.html", "<html></html>")
            self.write_af("design/P1.html", "<html></html>")
            self.write_af("design-system.md", DESIGN_SYSTEM)
        self.write_art("04-mapping.md", """> 依据 facts v1 生成
## 一、映射表
| 验收标准 | 落在哪 | 由哪条约束保证 | 谁实现 | 谁验证 |
|---|---|---|---|---|
| A1 | 约束一 | 数据层 | T1 | E1 |
| A2 | 约束二 | 服务层 | T2 | E2 |
## 二、无对应项
| 验收标准 | 为什么落不下去 | 退回动作 |
|---|---|---|
""")
        self.write_art("05-tasks.md", """> 依据 facts v1 生成
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
- 页面：P1
""")
        self.write_art("06-dev-log.md", """> 依据 facts v1 生成
## 任务完成情况
| 编号 | 类型 | 任务 | 状态 |
|---|---|---|---|
| T1 | BE | 后端任务 | 完成 |
| T2 | FE | 前端任务 | 完成 |
""")
        self.write_art("08-test-report.md", """> 依据 facts v1 生成
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
        self.write_art("09-bugs.md", """> 依据 facts v1 生成
## 汇总
| 编号 | 标题 | 关联任务 | 归属 | 状态 |
|---|---|---|---|---|
""")
        self.write_art("10-regression.md", """> 依据 facts v1 生成
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
        self.write_art("11-release.md", """> 依据 facts v1 生成
## 六、执行结果
- 状态：观察完成
- 实际执行时间：2026-10-27T09:00:00+08:00
- 证据：release-log-123
- 观察窗结论：指标正常
""")
        signoff = "confirmed" if design else "skipped"
        self.state = {
            "flow_version": 2, "project": "fixture", "stage": 11, "expert": "operator", "mode": 1,
            "facts_version": 1, "artifacts": sorted(CORE_NAMES + (DESIGN_NAMES if design else [])),
            "open_bugs": [], "open_ux_issues": [], "pending_decisions": [],
            "signoffs": {"scope": "confirmed", "requirement": "confirmed", "prd": "confirmed",
                         "prototype": signoff, "design": signoff},
            "prototype_required": design, "design_required": design,
            "task_status": {"T1": "done", "T2": "done"},
            "walkthrough_result": "pass" if design else "skipped",
            "acceptance_results": {"A1": "pass", "A2": "pass"},
            "regression_result": "pass", "regression_conditions": [], "regression_user_confirmed": False,
            "release_status": "verified", "agent_sessions": {},
        }
        dump_state(self.af / "state.yaml", self.state)

    def truncate(self, stage):
        """退回到某阶段收尾时的样子：删掉更晚的产物（阶段 8 允许 09-bugs.md 已存在）。"""
        keep = [n for n in self.state["artifacts"] if int(n[:2]) <= stage or (stage == 8 and n == "09-bugs.md")]
        for name in set(self.state["artifacts"]) - set(keep):
            (self.arts / name).unlink()
        self.state["artifacts"] = keep
        self.state["stage"] = stage

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

    def run_raw(self, encoding):
        """不经测试的 UTF-8 设置，模拟中文 Windows 上被管道调用。encoding=None 表示不设 PYTHONIOENCODING。"""
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        if encoding:
            env["PYTHONIOENCODING"] = encoding
        return subprocess.run([sys.executable, str(CHECK), str(self.root)], capture_output=True, env=env)

    def write_stage0_templates(self):
        self.write_af("state.yaml", template("state.yaml"))
        self.write_af("questions.md", template("questions.md"))
        self.write_art("00-intake.md", template("intake.md"))

    def test_bundled_stage0_templates_only_wait_for_scope_signoff(self):
        self.write_stage0_templates()
        result = self.run_check()
        self.assert_blocked(result, "范围 未经用户确认")
        self.assertNotIn("无法解析", result.stdout)

    def test_stage0_with_scope_confirmed_passes(self):
        self.write_stage0_templates()
        path = self.af / "state.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("  scope: pending", "  scope: confirmed"), encoding="utf-8")
        self.replace_art("00-intake.md", "- 确认结论：<已确认>", "- 确认结论：已确认")
        self.replace_art("00-intake.md", "- 用户原话：<只能来自用户本人的消息>", "- 用户原话：「范围没问题」")
        self.replace_art("00-intake.md", "- 确认时间：<YYYY-MM-DDThh:mm:ss+08:00>", "- 确认时间：2026-11-01T10:00:00+08:00")
        self.assert_pass(self.run_check())


    def test_valid_full_project_passes(self):
        self.make_full()
        self.assert_pass(self.run_check())

    def test_failed_regression_is_blocked(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：不通过**")
        self.state["regression_result"] = "fail"
        self.assert_blocked(self.run_check(), "回归不通过")

    def test_unconfirmed_conditional_regression_is_blocked(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = False
        self.assert_blocked(self.run_check(), "未取得用户显式确认")

    def test_confirmed_conditional_regression_passes(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = True
        self.assert_pass(self.run_check())

    def test_pending_bug_in_markdown_is_blocked_despite_empty_state(self):
        self.make_full()
        self.replace_art(
            "09-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 待复测 |\n\n### BUG-1 · 示例\n- 现象：失败\n",
        )
        self.assert_blocked(self.run_check(), "缺陷未清零")

    def test_open_bug_yaml_block_list_is_blocked(self):
        self.make_full()
        self.replace_art(
            "09-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 待复测 |\n\n### BUG-1 · 示例\n- 现象：失败\n",
        )
        self.state["open_bugs"] = ["BUG-1"]
        self.assert_blocked(self.run_check(), "缺陷未清零")

    def test_closed_bug_with_real_retest_passes(self):
        self.make_full()
        self.replace_art(
            "09-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 已关闭 |\n\n### BUG-1 · 示例\n**复测结论**\n- 结论：**通过 → 已关闭**\n",
        )
        self.assert_pass(self.run_check())

    def test_unfinished_task_is_blocked(self):
        self.make_full()
        self.state["task_status"]["T2"] = "pending"
        self.replace_art("06-dev-log.md", "| T2 | FE | 前端任务 | 完成 |", "| T2 | FE | 前端任务 | 未开始 |")
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
        (self.arts / "08-test-report.md").unlink()
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
        self.write_art("04-arch.md", "> 依据 facts v1 生成\nA1 A2 R1 A99\n")
        self.assert_blocked(self.run_check(), "从未定义")

    def test_mapping_task_backfill_is_required(self):
        self.make_full()
        self.replace_art("04-mapping.md", "| A1 | 约束一 | 数据层 | T1 | E1 |", "| A1 | 约束一 | 数据层 | — | E1 |")
        self.assert_blocked(self.run_check(), "未在映射表回填任务")

    def test_closed_bug_without_retest_is_blocked(self):
        self.make_full()
        self.replace_art(
            "09-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 已关闭 |\n\n### BUG-1 · 示例\n- 现象：失败\n",
        )
        self.assert_blocked(self.run_check(), "缺少通过复测结论")

    def test_failed_regression_row_cannot_be_marked_pass(self):
        self.make_full()
        self.replace_art("10-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "| E2 | A2 | 全量验收 | 失败 | |")
        self.assert_blocked(self.run_check(), "回归存在未通过")

    def test_conditional_regression_requires_conditions(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_user_confirmed"] = True
        self.assert_blocked(self.run_check(), "未记录条件")

    def test_release_requires_evidence(self):
        self.make_full()
        self.replace_art("11-release.md", "证据：release-log-123", "证据：")
        self.assert_blocked(self.run_check(), "缺少证据")

    def test_documented_failed_acceptance_cannot_be_hidden_by_state(self):
        self.make_full()
        self.replace_art("08-test-report.md", "| A2 | E2 | 通过 |", "| A2 | E2 | 失败 |")
        self.assert_blocked(self.run_check(), "验收结果不一致")

    def test_duplicate_bug_cannot_hide_open_status(self):
        self.make_full()
        self.replace_art(
            "09-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T1 | BE | 待修复 |\n| BUG-1 | 示例 | T1 | BE | 已关闭 |\n\n### BUG-1 · 示例\n**复测结论**\n- 结论：**通过 → 已关闭**\n",
        )
        self.assert_blocked(self.run_check(), "重复缺陷编号")

    def test_regression_prose_does_not_count_as_execution(self):
        self.make_full()
        self.replace_art("10-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "")
        self.write_art("10-regression.md", (self.arts / "10-regression.md").read_text(encoding="utf-8") + "\n补充说明：A2\n")
        self.assert_blocked(self.run_check(), "未以有效通过用例覆盖")

    def test_unknown_regression_case_is_blocked(self):
        self.make_full()
        self.replace_art("10-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "| E999 | A2 | 全量验收 | 通过 | |")
        self.assert_blocked(self.run_check(), "阶段 8 未定义")

    def test_regression_case_cannot_be_cross_assigned(self):
        self.make_full()
        self.replace_art("10-regression.md", "| E1 | A1 | 全量验收 | 通过 | |", "| E1 | A2 | 全量验收 | 通过 | |")
        self.replace_art("10-regression.md", "| E2 | A2 | 全量验收 | 通过 | |", "| E2 | A1 | 全量验收 | 通过 | |")
        self.assert_blocked(self.run_check(), "关联不一致")

    def test_same_agent_cannot_be_developer_and_tester(self):
        self.make_full()
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:same", "tester": "agent:same"}
        self.assert_blocked(self.run_check(), "必须是独立身份")

    def test_stage4_cannot_invent_future_task_or_case(self):
        self.make_full()
        self.truncate(4)
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
        self.replace_art("04-arch.md", "> 依据 facts v1 生成", "> 依据 facts v1 生成\n> 依据 facts v2 生成")
        self.assert_blocked(self.run_check(), "只有一条版本声明")

    def test_historical_conclusion_does_not_override_current(self):
        self.make_full()
        self.replace_art("10-regression.md", "## 四、结论\n", "## 四、结论\n上次结论：不通过\n")
        self.assert_pass(self.run_check())

    def test_task_cycle_is_blocked(self):
        self.make_full()
        self.replace_art("05-tasks.md", "| T1 | 后端任务 | BE | — |", "| T1 | 后端任务 | BE | T2 |")
        self.assert_blocked(self.run_check(), "依赖存在循环")

    def test_failed_acceptance_with_bug_can_complete_stage8(self):
        self.make_full()
        self.truncate(8)
        self.replace_art("08-test-report.md", "| T2 | FE | 1 | 1 | 0 | 通过 | — |", "| T2 | FE | 1 | 0 | 1 | 不通过 | BUG-1 |")
        self.replace_art("08-test-report.md", "| A2 | E2 | 通过 |", "| A2 | E2 | 失败 |")
        self.replace_art(
            "09-bugs.md", "|---|---|---|---|---|\n",
            "|---|---|---|---|---|\n| BUG-1 | 示例 | T2 | FE | 待修复 |\n\n### BUG-1 · 示例\n- 关联验收：A2\n- 现象：失败\n",
        )
        self.state["open_bugs"] = ["BUG-1"]
        self.state["acceptance_results"]["A2"] = "fail"
        self.assert_pass(self.run_check())

    def test_mode3_requires_final_review(self):
        self.make_full()
        self.state["mode"] = 3
        self.state["agent_sessions"] = {"developer": "agent:dev", "designer": "agent:ux", "tester": "agent:test"}
        self.assert_blocked(self.run_check(), "独立终验")

    def test_mode3_with_final_review_passes(self):
        self.make_full()
        self.state["mode"] = 3
        self.state["agent_sessions"] = {"developer": "agent:dev", "designer": "agent:ux", "tester": "agent:test", "final_reviewer": "human:reviewer"}
        self.state["final_review_result"] = "pass"
        self.state["final_review_evidence"] = "review-record-123"
        self.assert_pass(self.run_check())

    def test_release_plan_is_not_success(self):
        self.make_full()
        self.state["release_status"] = "planned"
        self.replace_art("11-release.md", "状态：观察完成", "状态：计划中")
        self.assert_blocked(self.run_check(), "上线尚未完成")

    def test_project_without_prototype_or_design_passes(self):
        self.make_full(design=False)
        self.assert_pass(self.run_check())

    def test_prd_signoff_pending_is_blocked(self):
        self.make_full()
        self.state["signoffs"]["prd"] = "pending"
        self.assert_blocked(self.run_check(), "PRD 未经用户确认")

    def test_confirmation_without_user_words_is_blocked(self):
        self.make_full()
        self.replace_art("02-prd.md", "- 用户原话：「确认，往下走」", "- 用户原话：")
        self.assert_blocked(self.run_check(), "缺少用户原话")

    def test_unresolved_review_feedback_is_blocked(self):
        self.make_full()
        self.replace_art("03-design.md", "| 已按反馈修改 | 已处理 |", "| 追问中 | 待澄清 |")
        self.assert_blocked(self.run_check(), "评审意见未处理完")

    def test_open_question_is_blocked(self):
        self.make_full()
        self.write_af("questions.md", QUESTIONS + "| Q2 | 2 | 新问题 | A1 | Q1 | 推荐乙 | | 待答复 | |\n")
        self.state["pending_decisions"] = ["Q2"]
        self.assert_blocked(self.run_check(), "问题未解决，不得完成阶段 11：Q2")

    def test_pending_decisions_must_mirror_questions(self):
        self.make_full()
        self.write_af("questions.md", QUESTIONS + "| Q2 | 2 | 新问题 | A1 | Q1 | 推荐乙 | | 待答复 | |\n")
        self.assert_blocked(self.run_check(), "pending_decisions 与 questions.md 不一致")

    def test_resolved_question_needs_user_words(self):
        self.make_full()
        self.write_af("questions.md", QUESTIONS.replace("| 「选甲」 | 已解决 |", "| | 已解决 |"))
        self.assert_blocked(self.run_check(), "没有用户答复原话：Q1")

    def test_delivery_form_must_match_state(self):
        self.make_full()
        self.write_art("02-prd.md", prd_doc(True, False))
        self.assert_blocked(self.run_check(), "交付形态与 state 不一致")

    def test_design_must_cover_every_prototype_page(self):
        self.make_full()
        self.replace_art("02-prototype.md", "| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |",
                         "| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |\n| P2 | 详情页 | 查看详情 | A1 | prototype/P1.html |")
        self.replace_art("02-prototype.md", "- 字段：编号、状态\n", "- 字段：编号、状态\n\n### P2 · 详情页\n- 字段：编号\n")
        result = self.run_check()
        self.assert_blocked(result, "设计稿未覆盖原型页面：P2")
        self.assertIn("页面没有落到任何 FE 任务：P2", result.stdout)

    def write_walkthrough(self, results, score, conclusion, issues=()):
        rows = "".join(row for row, _ in issues) + "".join(detail for _, detail in issues)
        self.write_art("07-walkthrough.md", walkthrough_doc(results, score, conclusion, rows))

    def test_missing_prototype_file_is_blocked(self):
        self.make_full()
        (self.af / "prototype" / "P1.html").unlink()
        self.assert_blocked(self.run_check(), "页面文件不存在：P1")

    def test_walkthrough_below_90_percent_is_blocked(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n in (3, 4) else "通过") for n in range(1, 11)]
        self.write_walkthrough(results, "8/10", "不通过",
                               [ux_issue("UX-1", "W3", "待修复"), ux_issue("UX-2", "W4", "待修复")])
        self.state["walkthrough_result"] = "fail"
        self.state["open_ux_issues"] = ["UX-1", "UX-2"]
        self.assert_blocked(self.run_check(), "设计还原度未达到 90%：8/10")

    def test_walkthrough_at_90_percent_with_leftover_passes(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)]
        self.write_walkthrough(results, "9/10", "通过", [ux_issue("UX-1", "W3", "遗留")])
        self.assert_pass(self.run_check())

    def test_key_checkpoint_failure_blocks_even_at_90_percent(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n == 2 else "通过") for n in range(1, 11)]
        self.write_walkthrough(results, "9/10", "通过", [ux_issue("UX-1", "W2", "遗留")])
        result = self.run_check()
        self.assert_blocked(result, "关键走查点未通过，不得完成阶段 7：W2")
        self.assertIn("关键走查点不能遗留", result.stdout)

    def test_rewalk_uses_latest_round(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)] + [(2, "W3", "通过")]
        self.write_walkthrough(results, "10/10", "通过", [ux_issue("UX-1", "W3", "已关闭", closed=True)])
        self.assert_pass(self.run_check())

    def test_closed_ux_issue_without_recheck_is_blocked(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)] + [(2, "W3", "通过")]
        self.write_walkthrough(results, "10/10", "通过", [ux_issue("UX-1", "W3", "已关闭")])
        self.assert_blocked(self.run_check(), "没有复查通过结论：UX-1")

    def test_open_ux_issue_blocks_stage7(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)]
        self.write_walkthrough(results, "9/10", "通过", [ux_issue("UX-1", "W3", "待复查")])
        self.state["open_ux_issues"] = ["UX-1"]
        self.assert_blocked(self.run_check(), "走查问题单未清零")

    def test_failed_checkpoint_needs_ux_issue(self):
        self.make_full()
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)]
        self.write_walkthrough(results, "9/10", "通过")
        self.assert_blocked(self.run_check(), "未通过的走查点没有走查问题单：W3")

    def test_wrong_declared_score_is_blocked(self):
        self.make_full()
        self.write_walkthrough(ALL_PASS, "9/10", "通过")
        self.assert_blocked(self.run_check(), "最终还原度与走查记录不一致")

    def test_undefined_checkpoint_is_blocked(self):
        self.make_full()
        self.write_walkthrough(ALL_PASS + [(1, "W99", "通过")], "10/10", "通过")
        self.assert_blocked(self.run_check(), "未定义的走查点：W99")

    def test_interaction_without_checkpoint_is_blocked(self):
        self.make_full()
        self.replace_art("03-design.md", "| W2 | P1 | 交互 | I1 按标注实现 | 是 |", "| W2 | P1 | 交互 | 按钮可点击 | 是 |")
        self.assert_blocked(self.run_check(), "交互标注没有被任何走查点覆盖：I1")

    def test_designer_must_differ_from_developer(self):
        self.make_full()
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:dev", "designer": "agent:dev", "tester": "agent:test"}
        self.assert_blocked(self.run_check(), "designer 与 developer 必须是独立身份")

    def test_closed_fe_bug_requires_design_recheck(self):
        self.make_full()
        self.replace_art("09-bugs.md", "|---|---|---|---|---|\n",
                         "|---|---|---|---|---|\n| BUG-1 | 示例 | T2 | FE | 已关闭 |\n\n### BUG-1 · 示例\n**复测结论**\n- 结论：**通过 → 已关闭**\n")
        self.assert_blocked(self.run_check(), "回归缺少通过的「设计还原复核」")
        self.replace_art("10-regression.md", "## 四、结论\n", "## 四、设计还原复核\n- 复核结论：通过\n\n## 五、结论\n")
        self.assert_pass(self.run_check())

    def test_design_artifact_without_design_required_is_blocked(self):
        self.make_full(design=False)
        self.write_art("03-design.md", DESIGN)
        self.state["artifacts"] = sorted(self.state["artifacts"] + ["03-design.md"])
        self.assert_blocked(self.run_check(), "PRD 判断不需要，但存在产物：03-design.md")

    def test_legacy_state_without_flow_version_is_blocked(self):
        self.make_full()
        del self.state["flow_version"]
        self.assert_blocked(self.run_check(), "flow_version 必须为 2")

    def test_rule_source_with_annotation_is_not_confirmed(self):
        self.make_full()
        self.write_af("facts.md", FACTS.replace("| R1 | 测试规则 | 已确认 |", "| R1 | 测试规则 | 已确认（时限可配置） |"))
        self.assert_blocked(self.run_check(), "业务规则尚未确认，不得进入后续阶段：R1")

    def test_legacy_basis_column_name_is_accepted(self):
        self.make_full()
        self.write_af("facts.md", FACTS.replace("| 编号 | 验收标准 | 依据规则 |", "| 编号 | 验收标准 | 依据 |"))
        self.assert_pass(self.run_check())

    def test_blocked_output_survives_gbk_pipe(self):
        self.make_full()
        self.state["signoffs"]["prd"] = "pending"
        dump_state(self.af / "state.yaml", self.state)
        result = self.run_raw("gbk")
        self.assertEqual(result.returncode, 1, result.stderr.decode("gbk", "replace"))
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertIn("PRD 未经用户确认", result.stdout.decode("gbk"))

    def test_blocked_output_defaults_to_utf8_when_piped(self):
        self.make_full()
        self.state["signoffs"]["prd"] = "pending"
        dump_state(self.af / "state.yaml", self.state)
        result = self.run_raw(None)
        self.assertEqual(result.returncode, 1, result.stderr.decode("utf-8", "replace"))
        self.assertIn("✗ PRD 未经用户确认", result.stdout.decode("utf-8"))


    def test_design_system_required_when_prototype_needed(self):
        self.make_full()
        (self.af / "design-system.md").unlink()
        self.assert_blocked(self.run_check(), "缺少 .aiflow/design-system.md")

    def test_design_system_template_source_must_be_filled(self):
        self.make_full()
        self.write_af("design-system.md", template("design-system.md"))
        self.assert_blocked(self.run_check(), "没有写明设计规范的来源")

    def test_design_system_not_needed_without_prototype_or_design(self):
        self.make_full(design=False)
        self.assertFalse((self.af / "design-system.md").exists())
        self.assert_pass(self.run_check())


class PrototypeKitTests(unittest.TestCase):
    """原型样式包：.aiflow/design-system.md 的令牌在构建时覆盖默认样式。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aiflow-kit-", dir=TEST_PARENT)
        self.af = Path(self.temp.name) / ".aiflow"
        self.proto = self.af / "prototype"
        shutil.copytree(SKILL_ROOT / "templates" / "prototype-kit", self.proto)
        shutil.copy(self.proto / "_src" / "_template.html", self.proto / "_src" / "P1-demo.html")

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, str(self.proto / "build.py")],
                                capture_output=True, text=True, encoding="utf-8", env=env)
        page = self.proto / "P1-demo.html"
        return result, page.read_text(encoding="utf-8") if page.exists() else ""

    def write_spec(self, preset=None, **values):
        text = template("design-system.md")
        if preset is not None:
            old = "- 样式预设：<无 / element-plus>"
            self.assertIn(old, text)
            text = text.replace(old, "- 样式预设：%s" % preset)
        for name, value in values.items():
            old = "| `--%s` | 按默认 |" % name
            self.assertIn(old, text)
            text = text.replace(old, "| `--%s` | %s |" % (name, value))
        (self.af / "design-system.md").write_text(text, encoding="utf-8")

    def test_build_without_spec_uses_defaults(self):
        result, page = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("来自 .aiflow/design-system.md", page)
        self.assertNotIn('href="kit.css"', page)

    def test_template_spec_overrides_nothing(self):
        self.write_spec()
        result, page = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("全部按默认", result.stdout)
        self.assertNotIn("来自 .aiflow/design-system.md", page)

    def test_spec_tokens_override_and_derive(self):
        self.write_spec(primary="#722ed1", radius="2px")
        result, page = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        override = page[page.index("来自 .aiflow/design-system.md"):]
        self.assertIn("--primary:#722ed1;", override)
        self.assertIn("--radius:2px;", override)
        self.assertRegex(override, r"--primary-bg:#[0-9a-f]{6};")
        self.assertNotIn("--primary-bg:#e6f4ff;", override)

    def test_unsafe_token_value_is_rejected(self):
        self.write_spec(primary="red;}</style><script>")
        result, _ = self.build()
        self.assertNotEqual(result.returncode, 0)


    def test_inline_color_is_reported(self):
        page = self.proto / "_src" / "P1-demo.html"
        text = page.read_text(encoding="utf-8")
        self.assertIn('<div class="canvas">', text)
        page.write_text(text.replace('<div class="canvas">', '<div class="canvas" style="background:#ffffff">', 1), encoding="utf-8")
        result, _ = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("写死了颜色", result.stdout)

    def test_preset_applies_element_plus(self):
        self.write_spec(preset="element-plus")
        result, page = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("用了样式预设：element-plus", result.stdout)
        self.assertIn("来自样式预设 element-plus", page)
        self.assertIn("--primary:#409eff;", page)
        self.assertIn(".tag.danger", page)

    def test_preset_derives_with_its_own_weights(self):
        self.write_spec(preset="element-plus", primary="#722ed1")
        result, page = self.build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        override = page[page.index("来自 .aiflow/design-system.md"):]
        self.assertIn("--primary-bg:#f1eafa;", override)
        self.assertIn("--primary-bd:#e3d5f6;", override)
        self.assertIn("--primary-text:#722ed1;", override)

    def test_unknown_preset_is_rejected(self):
        self.write_spec(preset="bootstrap")
        result, _ = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("可用的预设", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
