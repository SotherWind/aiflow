#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aiflow check.py 的正常放行与假绿反例测试。仅使用标准库。"""
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
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

RESEARCH_NOTES = """
## 调研记录（按需）
| 阶段 / 关联问题 | 检索主题 / 范围 | 来源与链接 | 查阅日期 / 版本 | 已核实做法及位置 | 局限 / 推断 / 未验证 | 对推荐的影响 |
|---|---|---|---|---|---|---|
| 2 / Q2 | 删除恢复机制 | [示例官方说明](https://example.invalid/recovery) | 2026-11-03 / v1 | 文档描述限时恢复 | 未运行验证 | 推荐 B，仍需用户决定 |
"""


def clarified(stage):
    """夹具已完成本阶段访谈；不是从产物 signoff 自动推断。"""
    return {
        "stage": stage, "status": "confirmed",
        "summary": "本轮范围、约束和默认项已逐项展示，无遗留决策",
        "user_quote": "确认理解一致", "confirmed_at": "2026-11-02T10:00:00+08:00",
    }


DESIGN_SYSTEM = """# 设计规范
- 来源：无，按 Ant Design 默认主题
- 依据：问题台账 Q1
"""

IMAGE_COMPARISON = """
## 图片还原核对
| 页面 | 基准图 | HTML截图 | 核对结论 | 差异与处理 |
|---|---|---|---|---|
| P1 | V1 | design/img/P1.png | 通过 | 无偏差 |
"""


def png_bytes(color):
    """生成有效的 1px 测试位图；这里只模拟图像工具输出，非产品设计产物。"""
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" + bytes(color))) + chunk(b"IEND", b""))

TECH_STACK = """# 技术栈选型与锁定

## 一、约束与现状
没有用户硬性指定；按当前项目和业务需求选择。

## 二、选型清单
| 选型 | 用途 | 技术/框架 | 版本范围 | 来源 | 选择理由 | 备选与取舍 |
|---|---|---|---|---|---|---|
| S1 | 前端 | example-ui | 1.0.0 | 推荐 | 支持本轮交互 | 其他方案增加迁移成本 |
| S2 | 后端 | example-api | 2.0.0 | 沿用项目 | 与现有服务兼容 | 不替换现有框架 |
""" + CONFIRM


def stack_fingerprint(text):
    proposal = text.split("## 用户确认", 1)[0].replace("\r\n", "\n").strip()
    return hashlib.sha256(proposal.encode("utf-8")).hexdigest()


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

SELFCHECK = """
## 五、设计稿自检
- 规范检查：P1 运行 spec-check.js，输出为空
- 版式检查：P1 运行 layout-check.js，输出为空
- 组件库对照：没有用样式预设，没有对照页面，未对照
- 独立评审：另一个会话评审，问题列在下表
- 结论：通过

| 编号 | 来源 | 位置 | 问题 | 处理 | 状态 |
|---|---|---|---|---|---|
| Z1 | 独立评审 | P1 | 空状态缺插图 | 已补 | 已修改 |
"""

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
""" + "".join("| W%d | P1 | 间距 | 要求 %d | 否 |\n" % (n, n) for n in range(3, 10)) + \
    "| W10 | P1 | 版式 | layout-check.js 和 spec-check.js 输出为空 | 是 |\n" + IMAGE_COMPARISON + SELFCHECK + CONFIRM


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
        self.home = self.root / "home"
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

    def record_dispatch(self, *roles):
        """用明确的测试派工/完成事件模拟本阶段执行，不以会话存在代替执行。"""
        stage = self.state["stage"]
        self.state["stage_dispatch"] = {"stage": stage}
        self.state["stage_dispatch"].update({role: "test-call:stage%d-%s; completed:test-result-stage%d-%s" %
                                             (stage, role, stage, role) for role in roles})

    def record_execution(self, strategy="coordinated"):
        """模拟主控按实际交接记录本阶段执行方式。"""
        stage = self.state["stage"]
        if strategy == "coordinated":
            self.state["stage_execution"] = {
                "stage": stage, "strategy": "coordinated", "coordinator": "agent:coordinator-stage%d" % stage,
                "handoff": "test-call:stage%d-coordinator; returned:test-handoff-stage%d" % (stage, stage)}
        else:
            self.state["stage_execution"] = {
                "stage": stage, "strategy": "direct",
                "fallback_reason": "test-limit:native-nesting-unavailable-stage%d" % stage}

    def log_sessions(self, execution, *roles):
        """按实际派工追加会话台账：本阶段协调器和各角色各记一条。"""
        stage = self.state["stage"]
        record = self.state.get("stage_execution")
        entries = self.state.setdefault("session_log", [])
        if isinstance(record, dict) and record.get("coordinator"):
            entries.append("%d %d coordinator %s" % (execution, stage, record["coordinator"]))
        entries.extend("%d %d %s %s" % (execution, stage, role, self.state["agent_sessions"][role]) for role in roles)

    def image_fingerprint_command(self):
        return subprocess.run([sys.executable, str(CHECK), str(self.root), "--design-image-fingerprint"],
                              capture_output=True, text=True, encoding="utf-8")

    def write_design_images(self, pages=("P1",)):
        body = "# 设计图片\n\n## 设计图片\n| 图号 | 覆盖页面 | 图片文件 | 生成方式 | 调用证据 |\n|---|---|---|---|---|\n"
        for index, page in enumerate(pages, 1):
            for relative, color in (("design-images/" + page + ".png", (index, 64, 128)),
                                    ("design/img/" + page + ".png", (index, 65, 128))):
                path = self.af / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png_bytes(color))
            body += "| V%d | %s | design-images/%s.png | 图像生成 | test-only-imagegen-call-%d |\n" % (index, page, page, index)
        self.write_af("design-images.md", body + CONFIRM)

    def confirm_design_images(self, pages=("P1",)):
        self.write_design_images(pages)
        result = self.image_fingerprint_command()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.state["design_image_status"] = "confirmed"
        self.state["design_image_fingerprint"] = result.stdout.strip()

    def write_bug(self, records=(), task="T1", owner="BE", standard="A1", status="已关闭", extra=""):
        rows = "".join("| %d | %s | %s | %s | %s |\n" % row for row in records)
        self.write_art("09-bugs.md", """> 依据 facts v1 生成
## 汇总
| 编号 | 标题 | 关联任务 | 归属 | 状态 |
|---|---|---|---|---|
| BUG-1 | 示例 | %s | %s | %s |

### BUG-1 · 示例
- 关联验收：%s
- 现象：失败
%s
#### 复测记录
| 轮次 | 用例 | 验收标准 | 结果 | 证据 |
|---|---|---|---|---|
%s
#### 复测结论
- 结论：通过 → 已关闭
""" % (task, owner, status, standard, extra, rows))

    def fail_initial_test(self):
        self.replace_art("08-test-report.md", "| T1 | BE | 1 | 1 | 0 | 通过 | — |",
                         "| T1 | BE | 1 | 0 | 1 | 不通过 | BUG-1 |")
        self.replace_art("08-test-report.md", "| A1 | E1 | 通过 |", "| A1 | E1 | 失败 |")
        self.state["acceptance_results"]["A1"] = "fail"

    def write_standards_log(self, rows):
        body = (self.arts / "06-dev-log.md").read_text(encoding="utf-8")
        body += "\n## 开发规范执行\n| 类型 | 规范文件 | 自检结论 | 证据 |\n|---|---|---|---|\n"
        body += "".join("| %s | %s | %s | %s |\n" % row for row in rows)
        self.write_art("06-dev-log.md", body)

    def make_full(self, design=True):
        """阶段 11 的完整项目。design=True 时含原型、设计稿与设计走查。"""
        self.design = design
        self.write_af("facts.md", FACTS)
        self.write_af("questions.md", QUESTIONS)
        self.write_art("00-intake.md", "> 依据 facts v0 生成\n本轮做：测试\n" + CONFIRM)
        self.write_art("01-research.md", "> 依据 facts v1 生成\nA1 A2 R1\n" + CONFIRM)
        self.write_art("02-prd.md", prd_doc(design, design))
        self.write_art("04-arch.md", "> 依据 facts v1 生成\nA1 A2 R1\n")
        self.write_af("tech-stack.md", TECH_STACK)
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
        self.write_art("06-dev-log.md", (self.arts / "06-dev-log.md").read_text(encoding="utf-8") + """
## 技术栈核对
- 技术栈指纹：%s
| 选型 | 实际技术/框架 | 实际版本 | 核对结论 | 证据 |
|---|---|---|---|---|
| S1 | example-ui | 1.0.0 | 通过 | frontend-manifest.log |
| S2 | example-api | 2.0.0 | 通过 | backend-manifest.log |
""" % stack_fingerprint(TECH_STACK))
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
            "invalidated_artifacts": [],
            "open_bugs": [], "open_ux_issues": [], "pending_decisions": [],
            "clarification": clarified(4),
            "signoffs": {"scope": "confirmed", "requirement": "confirmed", "prd": "confirmed",
                         "prototype": signoff, "design": signoff},
            "prototype_required": design, "design_required": design,
            "tech_stack_status": "locked", "tech_stack_fingerprint": stack_fingerprint(TECH_STACK),
            "task_status": {"T1": "done", "T2": "done"},
            "walkthrough_result": "pass" if design else "skipped",
            "acceptance_results": {"A1": "pass", "A2": "pass"},
            "regression_result": "pass", "regression_conditions": [], "regression_user_confirmed": False,
            "release_status": "verified", "agent_sessions": {},
            "design_image_status": "skipped", "design_image_fingerprint": "",
        }
        if design:
            self.confirm_design_images()
        dump_state(self.af / "state.yaml", self.state)

    def invalidate_after(self, stage):
        self.state["stage"] = stage
        if stage <= 4:
            self.state["clarification"] = clarified(stage)
        invalid = [name for name in self.state["artifacts"] if int(name[:2]) >= stage]
        self.state["invalidated_artifacts"] = invalid
        for name, key in (("00-intake.md", "scope"), ("01-research.md", "requirement"),
                          ("02-prd.md", "prd"), ("02-prototype.md", "prototype"), ("03-design.md", "design")):
            if name in invalid:
                self.state["signoffs"][key] = "pending"
        if {"05-tasks.md", "06-dev-log.md"} & set(invalid):
            self.state["task_status"] = {}
        if "07-walkthrough.md" in invalid:
            self.state["walkthrough_result"] = "not_run"
        if "08-test-report.md" in invalid:
            self.state["acceptance_results"] = {}
        if "10-regression.md" in invalid:
            self.state.update(regression_result="not_run", regression_conditions=[], regression_user_confirmed=False)
        if "11-release.md" in invalid:
            self.state["release_status"] = "planned"
        if {"08-test-report.md", "10-regression.md"} & set(invalid):
            self.state.update(final_review_result="not_run", final_review_evidence="")

    def replace_acceptance(self):
        facts = FACTS.replace("版本：v1", "版本：v2").replace(
            "| A2 | 标准二 | R1 | 能 |",
            "| ~~A2~~ | ~~标准二~~ | R1 | 能 |\n| A3 | 新标准三 | R1 | 能 |",
        ).replace("| A2 | 校验 | 约束二 |", "| A3 | 校验 | 新约束三 |")
        self.write_af("facts.md", facts)
        self.state["facts_version"] = 2
        self.state["acceptance_results"] = {"A1": "pass", "A3": "pass"}
        for name in self.state["artifacts"]:
            text = (self.arts / name).read_text(encoding="utf-8")
            if not name.startswith("00-"):
                text = text.replace("依据 facts v1", "依据 facts v2")
            self.write_art(name, re.sub(r"\bA2\b", "A3", text))

    def truncate(self, stage):
        """退回到某阶段收尾时的样子：删掉更晚的产物（阶段 8 允许 09-bugs.md 已存在）。"""
        keep = [n for n in self.state["artifacts"] if int(n[:2]) <= stage or (stage == 8 and n == "09-bugs.md")]
        for name in set(self.state["artifacts"]) - set(keep):
            (self.arts / name).unlink()
        self.state["artifacts"] = keep
        self.state["stage"] = stage
        if stage <= 4:
            self.state["clarification"] = clarified(stage)

    def enter_settled_stage(self, stage):
        """生命周期夹具显式模拟新阶段的澄清已完成。"""
        self.state["stage"] = stage
        if stage <= 4:
            self.state["clarification"] = clarified(stage)

    def run_check(self):
        if self.state is not None:
            dump_state(self.af / "state.yaml", self.state)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
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

    def test_bundled_stage0_templates_wait_for_clarification_not_artifacts(self):
        self.write_stage0_templates()
        result = self.run_check()
        self.assert_blocked(result, "澄清尚未收口")
        self.assertNotIn("缺少必需产物", result.stdout)
        self.assertNotIn("缺少 facts.md", result.stdout)
        self.assertEqual(list(self.arts.iterdir()), [])
        self.assertNotIn("无法解析", result.stdout)

    def test_pending_clarification_does_not_require_question_file(self):
        self.write_af("state.yaml", template("state.yaml"))
        before = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        result = self.run_check()
        self.assert_blocked(result, "澄清尚未收口")
        self.assertNotIn("缺少 .aiflow/questions.md", result.stdout)
        self.assertNotIn("缺少必需产物", result.stdout)
        after = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_unrecorded_conversation_does_not_initialize_project(self):
        root = self.root / "conversation"
        root.mkdir()
        result = subprocess.run(
            [sys.executable, str(CHECK), str(root)],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assert_blocked(result)
        self.assertNotIn("先按 templates/state.yaml 初始化", result.stdout)
        self.assertEqual(list(root.iterdir()), [])

    def test_closed_clarification_requires_recorded_questions(self):
        self.make_full(design=False)
        (self.af / "questions.md").unlink()
        self.assert_blocked(self.run_check(), "缺少 .aiflow/questions.md")

    def write_confirmed_stage0(self):
        self.write_stage0_templates()
        path = self.af / "state.yaml"
        text = path.read_text(encoding="utf-8").replace("  scope: pending", "  scope: confirmed")
        text = text.replace("\nartifacts: []\n", "\nartifacts:\n  - 00-intake.md\n")
        text = text.replace("  status: pending", "  status: confirmed")
        text = text.replace('  summary: ""', '  summary: "已展示全部范围和默认项"')
        text = text.replace('  user_quote: ""', '  user_quote: "范围没问题"')
        text = text.replace('  confirmed_at: ""', '  confirmed_at: "2026-11-02T10:00:00+08:00"')
        path.write_text(text, encoding="utf-8")
        self.write_art("00-intake.md", template("intake.md"))
        self.replace_art("00-intake.md", "- 确认结论：<已确认>", "- 确认结论：已确认")
        self.replace_art("00-intake.md", "- 用户原话：<只能来自用户本人的消息>", "- 用户原话：「范围没问题」")
        self.replace_art("00-intake.md", "- 确认时间：<YYYY-MM-DDThh:mm:ss+08:00>", "- 确认时间：2026-11-01T10:00:00+08:00")

    def test_stage0_with_scope_confirmed_passes(self):
        self.write_confirmed_stage0()
        path = self.af / "state.yaml"
        text = path.read_text(encoding="utf-8").replace("agent_sessions: {}", 'agent_sessions:\n  analyst: "agent:analyst"')
        text = text.replace("stage_dispatch:\n  stage: 0", 'stage_dispatch:\n  stage: 0\n  analyst: "test-call:stage0-analyst; completed:test-result-stage0"')
        path.write_text(text, encoding="utf-8")
        self.assert_blocked(self.run_check(), "stage_execution.strategy 未记录")
        text = text.replace('  strategy: ""', "  strategy: coordinated")
        text = text.replace('  coordinator: ""', '  coordinator: "agent:coordinator-stage0"')
        text = text.replace('  handoff: ""', '  handoff: "test-call:stage0-coordinator; returned:test-handoff-stage0"')
        path.write_text(text, encoding="utf-8")
        self.assert_blocked(self.run_check(), "session_log 最新一次执行不是当前阶段 0")
        text = text.replace("session_log: []", 'session_log:\n  - "1 0 coordinator agent:coordinator-stage0"\n  - "1 0 analyst agent:analyst"')
        path.write_text(text, encoding="utf-8")
        self.assert_pass(self.run_check())

    def test_default_delegated_stage0_requires_analyst_after_consensus(self):
        self.write_confirmed_stage0()
        result = self.run_check()
        self.assert_blocked(result, "缺少 agent_sessions.analyst")
        self.assertNotIn("agent_sessions.pm", result.stdout)
        self.assertNotIn("agent_sessions.fe", result.stdout)

    def test_architecture_pending_clarification_does_not_demand_arch_files(self):
        self.make_full()
        self.truncate(3)
        self.state["stage"] = 4
        self.state["clarification"] = {"stage": 4, "status": "pending"}
        (self.af / "tech-stack.md").unlink()
        result = self.run_check()
        self.assert_blocked(result, "澄清尚未收口")
        self.assertNotIn("缺少必需产物", result.stdout)
        self.assertNotIn("缺少技术栈选型文件", result.stdout)
        self.assertEqual(self.state["signoffs"]["design"], "confirmed")

    def test_research_pending_clarification_does_not_require_or_create_facts(self):
        self.make_full()
        self.truncate(0)
        (self.af / "facts.md").unlink()
        self.state["facts_version"] = 0
        self.state["stage"] = 1
        self.state["clarification"] = {"stage": 1, "status": "pending"}
        result = self.run_check()
        self.assert_blocked(result, "澄清尚未收口")
        self.assertNotIn("缺少 facts.md", result.stdout)
        self.assertNotIn("缺少必需产物", result.stdout)
        self.assertFalse((self.af / "facts.md").exists())
        self.assertFalse((self.arts / "01-research.md").exists())

    def test_completed_documents_and_signoffs_cannot_bypass_clarification(self):
        self.make_full()
        self.state["clarification"] = {"stage": 4, "status": "pending"}
        self.assert_blocked(self.run_check(), "澄清尚未收口")

    def test_early_stages_require_current_clarification_record(self):
        for stage in range(5):
            with self.subTest(stage=stage):
                self.make_full()
                self.truncate(stage)
                del self.state["clarification"]
                self.assert_blocked(self.run_check(), "缺少澄清记录")

    def test_previous_stage_clarification_cannot_close_new_stage(self):
        self.make_full()
        self.truncate(4)
        self.state["clarification"] = clarified(3)
        self.assert_blocked(self.run_check(), "澄清记录不属于当前阶段")

    def test_confirmed_clarification_requires_summary_quote_and_time(self):
        for key in ("summary", "user_quote", "confirmed_at"):
            with self.subTest(field=key):
                self.make_full()
                self.truncate(4)
                self.state["clarification"][key] = ""
                self.assert_blocked(self.run_check(), "clarification." + key)

    def test_clarification_confirmation_requires_valid_zoned_timestamp(self):
        for value in (None, True, "2026-11-02", "2026-11-02T10:00:00", "2026-99-99T10:00:00+08:00"):
            with self.subTest(value=value):
                self.make_full()
                self.truncate(4)
                self.state["clarification"]["confirmed_at"] = value
                self.assert_blocked(self.run_check(), "clarification.confirmed_at")

    def test_clarification_record_rejects_invalid_shape_stage_and_status(self):
        for record in ("confirmed", {}, {"stage": True, "status": "confirmed"},
                       {"stage": 12, "status": "confirmed"},
                       {"stage": 4, "status": "done"}):
            with self.subTest(record=record):
                self.make_full()
                self.truncate(4)
                self.state["clarification"] = record
                self.assert_blocked(self.run_check(), "clarification")

    def test_no_new_questions_can_use_existing_explicit_inputs(self):
        self.make_full()
        self.truncate(4)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.state["clarification"] = {
            "stage": 4, "status": "not_needed",
            "summary": "已确认 PRD、部署要求和开发规范覆盖本轮决策，无新增取舍",
        }
        self.assert_pass(self.run_check())

    def test_no_new_questions_still_requires_input_rationale(self):
        self.make_full()
        self.truncate(4)
        self.state["clarification"] = {"stage": 4, "status": "not_needed"}
        self.assert_blocked(self.run_check(), "clarification.summary")

    def test_answered_questions_require_explicit_shared_understanding(self):
        self.make_full()
        self.truncate(4)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.write_af("questions.md", QUESTIONS.replace("| Q1 | 0 |", "| Q1 | 4 |"))
        self.state["clarification"] = {
            "stage": 4, "status": "not_needed", "summary": "Q1 已回答",
        }
        self.assert_blocked(self.run_check(), "本阶段有澄清问题")
        self.state["clarification"] = clarified(4)
        self.assert_pass(self.run_check())

    def test_confirmed_clarification_cannot_hide_unanswered_questions(self):
        self.make_full()
        self.truncate(4)
        self.write_af("questions.md", QUESTIONS.replace("| Q1 | 0 |", "| Q1 | 4 |").replace("已解决", "待答复"))
        self.state["pending_decisions"] = ["Q1"]
        self.assert_blocked(self.run_check(), "问题未解决")

    def test_partial_answers_leave_other_decisions_open(self):
        self.make_full()
        self.truncate(4)
        self.write_af("questions.md", QUESTIONS.replace("| Q1 | 0 |", "| Q1 | 4 |") +
                      "| Q2 | 4 | 独立部署取舍 | 部署 | — | 推荐乙 | | 待答复 | |\n")
        self.state["clarification"] = {"stage": 4, "status": "pending"}
        self.state["pending_decisions"] = ["Q2"]
        result = self.run_check()
        self.assert_blocked(result, "问题未解决，不得完成阶段 4：Q2")
        self.assertNotIn("问题未解决，不得完成阶段 4：Q1", result.stdout)
        self.assertEqual(self.state["pending_decisions"], ["Q2"])

    def test_void_questions_do_not_force_a_new_interview(self):
        self.make_full()
        self.truncate(4)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.write_af("questions.md", QUESTIONS.replace("| Q1 | 0 |", "| Q1 | 4 |").replace(
            "「选甲」 | 已解决 | |", " | 作废 | 已有规范给出明确要求，分叉不成立 |"))
        self.state["clarification"] = {
            "stage": 4, "status": "not_needed", "summary": "已有规范覆盖，不存在新取舍",
        }
        self.assert_pass(self.run_check())

    def test_later_role_reopens_clarification_for_new_decisions(self):
        self.make_full()
        self.state["clarification"] = {"stage": 11, "status": "pending"}
        self.assert_blocked(self.run_check(), "澄清尚未收口")
        self.state["clarification"] = clarified(11)
        self.assert_pass(self.run_check())

    def test_pending_later_stage_does_not_demand_execution_roles(self):
        self.make_full()
        self.state["mode"] = 3
        self.state["clarification"] = {"stage": 11, "status": "pending"}
        result = self.run_check()
        self.assert_blocked(result, "澄清尚未收口")
        self.assertNotIn("agent_sessions.", result.stdout)
        self.assertNotIn("stage_dispatch", result.stdout)
        self.assertNotIn("独立终验尚未通过", result.stdout)

    def test_later_stage_with_questions_cannot_reuse_earlier_consensus(self):
        self.make_full()
        self.write_af("questions.md", QUESTIONS.replace("| Q1 | 0 |", "| Q1 | 11 |"))
        self.assert_blocked(self.run_check(), "澄清记录不属于当前阶段")

    def test_legacy_later_stage_without_new_decisions_does_not_invent_history(self):
        self.make_full()
        del self.state["clarification"]
        self.assert_pass(self.run_check())

    def test_clarification_check_does_not_mutate_project_files(self):
        self.make_full()
        self.truncate(4)
        self.state["clarification"] = {"stage": 4, "status": "pending"}
        dump_state(self.af / "state.yaml", self.state)
        before = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        self.assert_blocked(self.run_check(), "澄清尚未收口")
        after = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        self.assertEqual(after, before)


    def test_valid_full_project_passes(self):
        self.make_full()
        self.assert_pass(self.run_check())

    def test_architecture_requires_tech_stack_record(self):
        self.make_full()
        self.truncate(4)
        (self.af / "tech-stack.md").unlink()
        self.assert_blocked(self.run_check(), "缺少技术栈选型文件")

    def test_tech_stack_must_be_locked(self):
        self.make_full()
        self.state["tech_stack_status"] = "pending"
        self.assert_blocked(self.run_check(), "技术栈尚未确认锁定")

    def test_legacy_project_cannot_skip_tech_stack_confirmation(self):
        self.make_full()
        del self.state["tech_stack_status"]
        del self.state["tech_stack_fingerprint"]
        self.assert_blocked(self.run_check(), "技术栈尚未确认锁定")

    def test_tech_stack_lock_needs_user_confirmation(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK.replace("确认结论：已确认", "确认结论：待确认"))
        self.assert_blocked(self.run_check(), "tech-stack.md 尚未取得用户确认")

    def test_tech_stack_confirmation_needs_user_words(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK.replace("用户原话：「确认，往下走」", "用户原话："))
        self.assert_blocked(self.run_check(), "tech-stack.md 的用户确认缺少用户原话")

    def test_tech_stack_change_invalidates_lock(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK.replace("example-ui", "different-ui"))
        self.assert_blocked(self.run_check(), "技术栈锁定指纹与当前选型不一致")

    def test_tech_stack_choices_need_version_and_reason(self):
        for old, new in (("| 1.0.0 |", "| <待定> |"), ("| 支持本轮交互 |", "| |")):
            with self.subTest(field=old):
                self.make_full()
                changed = TECH_STACK.replace(old, new)
                self.write_af("tech-stack.md", changed)
                self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
                self.assert_blocked(self.run_check(), "技术栈选型缺少")

    def test_tech_stack_recommendation_needs_alternative_tradeoff(self):
        self.make_full()
        changed = TECH_STACK.replace("其他方案增加迁移成本", "")
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.assert_blocked(self.run_check(), "技术栈推荐缺少备选与取舍：S1")

    def test_tech_stack_cannot_lock_latest(self):
        self.make_full()
        changed = TECH_STACK.replace("| 1.0.0 |", "| latest |")
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.assert_blocked(self.run_check(), "技术栈版本范围不可判定：S1")

    def test_tech_stack_choices_cannot_be_empty(self):
        self.make_full()
        self.write_af("tech-stack.md", "# 技术栈\n" + CONFIRM)
        self.assert_blocked(self.run_check(), "技术栈没有有效选型")

    def test_duplicate_tech_stack_choices_are_blocked(self):
        self.make_full()
        row = "| S1 | 前端 | example-ui | 1.0.0 | 推荐 | 支持本轮交互 | 其他方案增加迁移成本 |"
        changed = TECH_STACK.replace(row, row + "\n" + row)
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.assert_blocked(self.run_check(), "重复技术栈选型编号：S1")

    def test_duplicate_tech_stack_selection_sections_are_blocked(self):
        self.make_full()
        changed = TECH_STACK.replace("## 评审记录", "## 选型清单\n\n## 评审记录")
        self.write_af("tech-stack.md", changed)
        self.assert_blocked(self.run_check(), "必须有且只有一个「选型清单」小节")

    def test_duplicate_tech_stack_confirmations_are_blocked(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK + "\n## 用户确认\n- 确认结论：待确认\n")
        self.assert_blocked(self.run_check(), "必须有且只有一个「用户确认」小节")

    def test_tech_stack_confirmation_must_be_last_section(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK + "\n## 另一个方案\n选型已变化。\n")
        self.assert_blocked(self.run_check(), "用户确认必须是最后一个二级小节")

    def test_tech_stack_review_must_be_resolved(self):
        self.make_full()
        changed = TECH_STACK.replace("| 已处理 |", "| 待修改 |")
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.assert_blocked(self.run_check(), "tech-stack.md 评审意见未处理完")

    def test_tech_stack_confirmation_needs_timestamp(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK.replace("确认时间：2026-11-01T10:00:00+08:00", "确认时间："))
        self.assert_blocked(self.run_check(), "tech-stack.md 的用户确认缺少确认时间")

    def test_relocked_tech_stack_invalidates_old_execution_log(self):
        self.make_full()
        changed = TECH_STACK.replace("支持本轮交互", "支持本轮交互和构建约束")
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.assert_blocked(self.run_check(), "技术栈核对仍基于旧选型")

    def test_tech_stack_version_range_can_have_concrete_actual_version(self):
        self.make_full()
        changed = TECH_STACK.replace("| 1.0.0 |", "| ^1.0.0 |")
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.replace_art("06-dev-log.md", stack_fingerprint(TECH_STACK), stack_fingerprint(changed))
        self.replace_art("06-dev-log.md", "frontend-manifest.log", "native-range-check.log：实际版本满足锁定范围")
        self.assert_pass(self.run_check())

    def test_tech_stack_user_and_standards_choices_do_not_need_alternative(self):
        for source in ("用户指定", "开发规范"):
            with self.subTest(source=source):
                self.make_full()
                changed = TECH_STACK.replace("| 推荐 |", "| %s |" % source).replace("其他方案增加迁移成本", "")
                self.write_af("tech-stack.md", changed)
                self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
                self.replace_art("06-dev-log.md", stack_fingerprint(TECH_STACK), stack_fingerprint(changed))
                self.assert_pass(self.run_check())

    def test_tech_stack_actual_framework_must_match_lock(self):
        self.make_full()
        self.replace_art("06-dev-log.md", "| S1 | example-ui |", "| S1 | different-ui |")
        self.assert_blocked(self.run_check(), "实际技术与锁定选型不一致：S1")

    def test_tech_stack_exact_version_must_match_lock(self):
        self.make_full()
        self.replace_art("06-dev-log.md", "| S1 | example-ui | 1.0.0 |", "| S1 | example-ui | 2.0.0 |")
        self.assert_blocked(self.run_check(), "实际版本与锁定的精确版本不一致：S1")

    def test_tech_stack_exact_version_with_prerelease_and_build_metadata(self):
        self.make_full()
        changed = TECH_STACK.replace("| 1.0.0 |", "| 1.0.0-rc.1+build.2 |")
        self.write_af("tech-stack.md", changed)
        self.state["tech_stack_fingerprint"] = stack_fingerprint(changed)
        self.replace_art("06-dev-log.md", stack_fingerprint(TECH_STACK), stack_fingerprint(changed))
        self.assert_blocked(self.run_check(), "实际版本与锁定的精确版本不一致：S1")
        self.replace_art("06-dev-log.md", "| S1 | example-ui | 1.0.0 |", "| S1 | example-ui | 1.0.0-rc.1+build.2 |")
        self.assert_pass(self.run_check())

    def test_tech_stack_execution_needs_every_choice(self):
        self.make_full()
        self.replace_art("06-dev-log.md", "| S2 | example-api | 2.0.0 | 通过 | backend-manifest.log |", "")
        self.assert_blocked(self.run_check(), "缺少技术栈核对记录：S2")

    def test_tech_stack_execution_needs_evidence(self):
        self.make_full()
        self.replace_art("06-dev-log.md", "| frontend-manifest.log |", "| |")
        self.assert_blocked(self.run_check(), "技术栈核对缺少证据：S1")

    def test_tech_stack_execution_must_use_current_fingerprint(self):
        self.make_full()
        self.replace_art("06-dev-log.md", stack_fingerprint(TECH_STACK), "old-fingerprint")
        self.assert_blocked(self.run_check(), "技术栈核对仍基于旧选型")

    def test_duplicate_tech_stack_execution_is_blocked(self):
        self.make_full()
        row = "| S1 | example-ui | 1.0.0 | 通过 | frontend-manifest.log |"
        self.replace_art("06-dev-log.md", row, row + "\n" + row)
        self.assert_blocked(self.run_check(), "重复技术栈核对记录：S1")

    def test_duplicate_tech_stack_execution_sections_are_blocked(self):
        self.make_full()
        path = self.arts / "06-dev-log.md"
        self.write_art("06-dev-log.md", path.read_text(encoding="utf-8") + "\n## 技术栈核对\n核对失败。\n")
        self.assert_blocked(self.run_check(), "开发日志必须有且只有一个「技术栈核对」小节")

    def test_missing_tech_stack_does_not_block_early_stages(self):
        self.make_full(design=False)
        self.truncate(3)
        (self.af / "tech-stack.md").unlink()
        del self.state["tech_stack_status"]
        del self.state["tech_stack_fingerprint"]
        self.assert_pass(self.run_check())

    def test_tech_stack_fingerprint_command_does_not_confirm_or_mutate(self):
        self.make_full()
        self.state["tech_stack_status"] = "pending"
        dump_state(self.af / "state.yaml", self.state)
        before = (self.af / "state.yaml").read_bytes()
        result = subprocess.run(
            [sys.executable, str(CHECK), str(self.root), "--tech-stack-fingerprint"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), stack_fingerprint(TECH_STACK))
        self.assertEqual((self.af / "state.yaml").read_bytes(), before)

    def test_tech_stack_fingerprint_command_rejects_invalid_proposal(self):
        self.make_full()
        self.write_af("tech-stack.md", TECH_STACK.replace("| 1.0.0 |", "| latest |"))
        before = (self.af / "state.yaml").read_bytes()
        result = subprocess.run(
            [sys.executable, str(CHECK), str(self.root), "--tech-stack-fingerprint"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assert_blocked(result, "技术栈版本范围不可判定：S1")
        self.assertEqual((self.af / "state.yaml").read_bytes(), before)

    def test_frontend_standards_require_execution_record(self):
        self.make_full()
        self.write_af("frontend-standards.md", "# 前端开发规范\n组件按业务目录组织。\n")
        self.assert_blocked(self.run_check(), "缺少开发规范执行记录：FE")

    def test_backend_standards_do_not_depend_on_design_required(self):
        self.make_full(design=False)
        self.write_af("backend-standards.md", "# 后端开发规范\n数据库访问放在仓储层。\n")
        self.assert_blocked(self.run_check(), "缺少开发规范执行记录：BE")

    def test_frontend_and_backend_standards_with_evidence_pass(self):
        self.make_full()
        self.write_af("frontend-standards.md", "# 前端开发规范\n组件按业务目录组织。\n")
        self.write_af("backend-standards.md", "# 后端开发规范\n数据库访问放在仓储层。\n")
        self.write_standards_log([
            ("FE", ".aiflow/frontend-standards.md", "通过", "lint-fe.log；已核对组件目录"),
            ("BE", ".aiflow/backend-standards.md", "通过", "lint-be.log；已核对仓储层"),
        ])
        self.assert_pass(self.run_check())

    def test_frontend_standards_can_be_configured_independently(self):
        self.make_full()
        self.state["development_standards"] = {"frontend": "", "backend": ""}
        self.write_af("frontend-standards.md", "# 前端开发规范\n组件按业务目录组织。\n")
        self.write_standards_log([("FE", ".aiflow/frontend-standards.md", "通过", "lint-fe.log")])
        self.assert_pass(self.run_check())

    def test_backend_standards_also_apply_to_jobs(self):
        self.make_full(design=False)
        self.replace_art("05-tasks.md", "| T1 | 后端任务 | BE |", "| T1 | 后端任务 | JOB |")
        self.replace_art("06-dev-log.md", "| T1 | BE |", "| T1 | JOB |")
        self.replace_art("08-test-report.md", "| T1 | BE |", "| T1 | JOB |")
        self.write_af("backend-standards.md", "# 后端开发规范\n定时任务必须幂等。\n")
        self.write_standards_log([("BE", ".aiflow/backend-standards.md", "通过", "job-tests.log")])
        self.assert_pass(self.run_check())

    def test_custom_markdown_standards_path_is_supported(self):
        self.make_full()
        self.write_af("../docs/前端规范 v1.md", "# 现有团队规范\n使用统一请求封装。\n")
        self.state["development_standards"] = {"frontend": "docs/前端规范 v1.md"}
        self.write_standards_log([("FE", "docs/前端规范 v1.md", "通过", "lint-fe.log")])
        self.assert_pass(self.run_check())

    def test_explicit_standards_override_project_default(self):
        self.make_full()
        self.write_af("frontend-standards.md", "# 原有规范\n原有规则。\n")
        self.write_af("../docs/frontend.md", "# 指定规范\n使用统一请求封装。\n")
        self.state["development_standards"] = {"frontend": "docs/frontend.md"}
        self.write_standards_log([("FE", "docs/frontend.md", "通过", "lint-fe.log")])
        self.assert_pass(self.run_check())

    def test_missing_explicit_standards_do_not_fall_back_to_default(self):
        self.make_full()
        self.write_af("frontend-standards.md", "# 原有规范\n原有规则。\n")
        self.state["development_standards"] = {"frontend": "docs/missing.md"}
        self.write_standards_log([("FE", ".aiflow/frontend-standards.md", "通过", "lint-fe.log")])
        self.assert_blocked(self.run_check(), "开发规范文件不存在或不是文件：FE")

    def test_empty_development_standards_are_blocked(self):
        self.make_full()
        self.write_af("frontend-standards.md", " \n")
        self.assert_blocked(self.run_check(), "开发规范文件为空：FE")

    def test_development_standards_must_be_markdown(self):
        self.make_full()
        self.write_af("frontend.txt", "组件按业务目录组织。\n")
        self.state["development_standards"] = {"frontend": ".aiflow/frontend.txt"}
        self.assert_blocked(self.run_check(), "开发规范文件必须为 Markdown：FE")

    def test_development_standards_configuration_is_validated(self):
        for config in ([], {"fronted": "docs/frontend.md"}, {"frontend": False}):
            with self.subTest(config=config):
                self.make_full()
                self.state["development_standards"] = config
                self.assert_blocked(self.run_check(), "development_standards")

    def test_standards_execution_cannot_use_wrong_file(self):
        self.make_full()
        self.write_af("frontend-standards.md", "# 前端开发规范\n组件按业务目录组织。\n")
        self.write_af("other.md", "# 其他文件\n其他规则。\n")
        self.write_standards_log([("FE", ".aiflow/other.md", "通过", "lint-fe.log")])
        self.assert_blocked(self.run_check(), "开发规范执行记录与实际规范不一致：FE")

    def test_standards_execution_requires_pass_and_evidence(self):
        for conclusion, evidence in (("待检查", "lint-fe.log"), ("通过", "")):
            with self.subTest(conclusion=conclusion, evidence=evidence):
                self.make_full()
                self.write_af("frontend-standards.md", "# 前端开发规范\n组件按业务目录组织。\n")
                self.write_standards_log([("FE", ".aiflow/frontend-standards.md", conclusion, evidence)])
                self.assert_blocked(self.run_check(), "开发规范自检")

    def test_duplicate_standards_execution_cannot_hide_failure(self):
        self.make_full()
        self.write_af("frontend-standards.md", "# 前端开发规范\n组件按业务目录组织。\n")
        self.write_standards_log([
            ("FE", ".aiflow/frontend-standards.md", "不通过", "lint-failed.log"),
            ("FE", ".aiflow/frontend-standards.md", "通过", "lint-fe.log"),
        ])
        self.assert_blocked(self.run_check(), "重复开发规范执行记录：FE")

    def test_team_default_standards_are_discovered(self):
        self.make_full()
        self.write_af("../home/.aiflow/frontend-standards.md", "# 团队规范\n使用统一请求封装。\n")
        self.write_standards_log([("FE", "~/.aiflow/frontend-standards.md", "通过", "lint-fe.log")])
        self.assert_pass(self.run_check())

    def test_project_standards_override_team_default(self):
        self.make_full()
        self.write_af("../home/.aiflow/frontend-standards.md", "# 团队规范\n团队规则。\n")
        self.write_af("frontend-standards.md", "# 项目规范\n项目规则。\n")
        self.write_standards_log([("FE", ".aiflow/frontend-standards.md", "通过", "lint-fe.log")])
        self.assert_pass(self.run_check())

    def test_development_standards_are_checked_before_architecture_finishes(self):
        self.make_full(design=False)
        self.truncate(4)
        self.state["development_standards"] = {"backend": "docs/missing.md"}
        self.assert_blocked(self.run_check(), "开发规范文件不存在或不是文件：BE")

    def test_valid_architecture_standards_do_not_require_development_log(self):
        self.make_full(design=False)
        self.truncate(4)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.write_af("backend-standards.md", "# 后端开发规范\n数据库访问放在仓储层。\n")
        self.assert_pass(self.run_check())

    def test_missing_standards_do_not_block_stages_before_architecture(self):
        self.make_full(design=False)
        self.truncate(3)
        self.state["development_standards"] = {"backend": "docs/missing.md"}
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
        self.replace_art("10-regression.md", "- 条件：无", "- 条件：仅允许内网灰度")
        self.write_art("10-regression.md", (self.arts / "10-regression.md").read_text(encoding="utf-8") + CONFIRM)
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = True
        self.assert_pass(self.run_check())

    def test_conditional_regression_boolean_is_not_user_confirmation(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.replace_art("10-regression.md", "- 条件：无", "- 条件：仅允许内网灰度")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = True
        self.assert_blocked(self.run_check(), "10-regression.md 缺少「用户确认」小节")

    def test_conditional_regression_needs_user_words(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.replace_art("10-regression.md", "- 条件：无", "- 条件：仅允许内网灰度")
        confirmation = CONFIRM.replace("- 用户原话：「确认，往下走」", "- 用户原话：")
        self.write_art("10-regression.md", (self.arts / "10-regression.md").read_text(encoding="utf-8") + confirmation)
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = True
        self.assert_blocked(self.run_check(), "10-regression.md 的用户确认缺少用户原话")

    def test_conditional_regression_conditions_must_match_document(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度"]
        self.state["regression_user_confirmed"] = True
        self.write_art("10-regression.md", (self.arts / "10-regression.md").read_text(encoding="utf-8") + CONFIRM)
        self.assert_blocked(self.run_check(), "回归条件与 state 不一致")

    def test_conditional_regression_placeholder_condition_is_blocked(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["<待补条件>"]
        self.state["regression_user_confirmed"] = True
        self.write_art("10-regression.md", (self.arts / "10-regression.md").read_text(encoding="utf-8") + CONFIRM)
        self.assert_blocked(self.run_check(), "回归条件不能为空、占位或「无」")

    def test_confirmed_multiple_regression_conditions_pass(self):
        self.make_full()
        self.replace_art("10-regression.md", "**结论：通过**", "**结论：有条件通过**")
        self.replace_art("10-regression.md", "- 条件：无", "- 条件：仅允许内网灰度\n- 条件：限制为测试账号")
        self.write_art("10-regression.md", (self.arts / "10-regression.md").read_text(encoding="utf-8") + CONFIRM)
        self.state["regression_result"] = "conditional"
        self.state["regression_conditions"] = ["仅允许内网灰度", "限制为测试账号"]
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
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
        self.assert_pass(self.run_check())

    def test_closed_bug_needs_retest_execution_not_just_conclusion(self):
        self.make_full()
        self.write_bug()
        self.assert_blocked(self.run_check(), "已关闭缺陷缺少复测记录：BUG-1")

    def test_closed_bug_latest_retest_must_pass(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1"),
                        (2, "E1", "A1", "不通过", "retest-log-2")])
        self.assert_blocked(self.run_check(), "已关闭缺陷最近一轮复测未通过：BUG-1 → E1")

    def test_retest_can_pass_after_failed_round(self):
        self.make_full()
        self.write_bug([(2, "E1", "A1", "通过", "retest-log-2"),
                        (1, "E1", "A1", "不通过", "retest-log-1")])
        self.assert_pass(self.run_check())

    def test_retest_requires_evidence(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "通过", "")])
        self.assert_blocked(self.run_check(), "复测记录缺少证据：BUG-1 → E1")

    def test_retest_cannot_invent_case(self):
        self.make_full()
        self.write_bug([(1, "E99", "A1", "通过", "retest-log-1")])
        self.assert_blocked(self.run_check(), "复测引用了未定义的用例：BUG-1 → E99")

    def test_retest_case_cannot_be_cross_assigned(self):
        self.make_full()
        self.write_bug([(1, "E2", "A1", "通过", "retest-log-1")])
        self.assert_blocked(self.run_check(), "复测用例与验收标准的关联不一致：BUG-1 → E2/A1")

    def test_retest_cannot_cover_unrelated_acceptance(self):
        self.make_full()
        self.write_bug([(1, "E2", "A2", "通过", "retest-log-1")])
        self.assert_blocked(self.run_check(), "复测标准不在缺陷的关联验收中：BUG-1 → A2")

    def test_duplicate_retest_round_cannot_hide_failure(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "不通过", "retest-log-1"),
                        (1, "E1", "A1", "通过", "retest-log-2")])
        self.assert_blocked(self.run_check(), "同一轮重复复测同一用例：BUG-1 → E1 第 1 轮")

    def test_duplicate_retest_sections_cannot_hide_later_failure(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
        self.write_art("09-bugs.md", (self.arts / "09-bugs.md").read_text(encoding="utf-8") + """
#### 复测记录
| 轮次 | 用例 | 验收标准 | 结果 | 证据 |
|---|---|---|---|---|
| 2 | E1 | A1 | 不通过 | retest-log-2 |
""")
        self.assert_blocked(self.run_check(), "缺陷存在重复的「复测记录」小节：BUG-1")

    def test_duplicate_retest_conclusions_are_blocked(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
        self.write_art("09-bugs.md", (self.arts / "09-bugs.md").read_text(encoding="utf-8") +
                       "\n#### 复测结论\n- 结论：不通过 → 打回\n")
        self.assert_blocked(self.run_check(), "缺陷存在重复的「复测结论」小节：BUG-1")

    def test_retest_round_must_be_positive_integer(self):
        for number in ("0", "-1", "一"):
            with self.subTest(round=number):
                self.make_full()
                self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
                self.replace_art("09-bugs.md", "| 1 | E1 |", "| %s | E1 |" % number)
                self.assert_blocked(self.run_check(), "复测轮次必须是正整数")

    def test_bug_owner_must_match_task_type(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")], owner="FE")
        self.assert_blocked(self.run_check(), "缺陷归属与任务类型不一致：BUG-1")

    def test_bug_cannot_link_unknown_task(self):
        self.make_full()
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")], task="T99")
        self.assert_blocked(self.run_check(), "缺陷关联了不存在的任务：BUG-1 → T99")

    def test_failure_retest_regression_release_preserve_initial_report(self):
        self.make_full(design=False)
        later = {name: (self.arts / name).read_text(encoding="utf-8")
                 for name in ("10-regression.md", "11-release.md")}
        self.truncate(8)
        self.fail_initial_test()
        initial_report = (self.arts / "08-test-report.md").read_text(encoding="utf-8")
        self.write_bug(status="待修复")
        self.state["open_bugs"] = ["BUG-1"]
        self.assert_pass(self.run_check())

        self.state["stage"] = 9
        self.state["open_bugs"] = []
        self.state["acceptance_results"]["A1"] = "pass"
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
        self.assert_pass(self.run_check())
        for stage, name in ((10, "10-regression.md"), (11, "11-release.md")):
            self.state["stage"] = stage
            self.state["artifacts"].append(name)
            self.write_art(name, later[name])
            self.assert_pass(self.run_check())
        self.assertEqual((self.arts / "08-test-report.md").read_text(encoding="utf-8"), initial_report)

    def test_stage9_cannot_promote_acceptance_without_all_case_retests(self):
        self.make_full(design=False)
        self.truncate(9)
        self.fail_initial_test()
        self.replace_art("08-test-report.md", "| A1 | E1 | 失败 |", "| A1 | E1、E3 | 失败 |")
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| T1 | E1、E3 |")
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
        self.state["acceptance_results"]["A1"] = "pass"
        self.assert_blocked(self.run_check(), "阶段 9 验收结果缺少完整复测依据：A1")

    def test_template_execution_result_column_is_accepted(self):
        self.make_full()
        self.replace_art("08-test-report.md", "| 验收标准 | 对应用例 | 结果 |",
                         "| 验收标准 | 对应用例 | 执行结果 |")
        self.assert_pass(self.run_check())

    def test_stage8_mapping_case_cannot_be_cross_assigned(self):
        self.make_full(design=False)
        self.truncate(8)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| T1 | E2 |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| T2 | E1 |")
        self.assert_blocked(self.run_check(), "映射表用例与验收标准的关联不一致")

    def test_regression_must_execute_all_cases_for_current_acceptance(self):
        self.make_full()
        self.replace_art("08-test-report.md", "| A1 | E1 | 通过 |", "| A1 | E1、E3 | 通过 |")
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| T1 | E1、E3 |")
        self.assert_blocked(self.run_check(), "全量回归未执行当前验收用例：E3")

    def test_full_regression_resolves_remaining_cases_without_rewriting_initial_failure(self):
        self.make_full(design=False)
        self.fail_initial_test()
        self.replace_art("08-test-report.md", "| A1 | E1 | 失败 |", "| A1 | E1、E3 | 失败 |")
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| T1 | E1、E3 |")
        self.replace_art("10-regression.md", "| E1 | A1 | 全量验收 | 通过 | |",
                         "| E1 | A1 | 全量验收 | 通过 | |\n| E3 | A1 | 全量验收 | 通过 | |")
        self.write_bug([(1, "E1", "A1", "通过", "retest-log-1")])
        self.state["acceptance_results"]["A1"] = "pass"
        self.assert_pass(self.run_check())

    def test_passed_regression_cannot_keep_documented_condition(self):
        self.make_full()
        self.replace_art("10-regression.md", "- 条件：无", "- 条件：仅允许内网灰度")
        self.assert_blocked(self.run_check(), "结论为通过时不应仍挂回归条件")

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

    def test_invalidated_required_artifact_cannot_be_reused(self):
        self.make_full()
        self.invalidate_after(11)
        self.state["release_status"] = "verified"
        self.assert_blocked(self.run_check(), "必需产物已失效：11-release.md")

    def test_invalidated_future_artifacts_can_remain_for_traceability(self):
        self.make_full()
        self.invalidate_after(3)
        self.enter_settled_stage(2)
        before = {path.name: path.read_bytes() for path in self.arts.glob("*.md")}
        self.assert_pass(self.run_check())
        self.assertEqual({path.name: path.read_bytes() for path in self.arts.glob("*.md")}, before)

    def test_invalidated_confirmation_cannot_stay_confirmed(self):
        self.make_full()
        self.invalidate_after(3)
        self.enter_settled_stage(2)
        self.state["signoffs"]["design"] = "confirmed"
        self.assert_blocked(self.run_check(), "失效产物仍保留用户确认：03-design.md")

    def test_invalidation_requires_resetting_downstream_results(self):
        for field, value, message in (
            ("task_status", {"T1": "done"}, "失效开发产物仍保留任务状态"),
            ("acceptance_results", {"A1": "pass"}, "失效测试报告仍保留验收结果"),
            ("walkthrough_result", "pass", "失效走查仍保留执行结果"),
            ("regression_result", "pass", "失效回归仍保留放行状态"),
            ("regression_conditions", ["旧条件"], "失效回归仍保留放行状态"),
            ("regression_user_confirmed", True, "失效回归仍保留放行状态"),
            ("release_status", "verified", "失效发布仍保留上线状态"),
            ("final_review_result", "pass", "失效验收仍保留独立终验"),
            ("final_review_evidence", "old-review.log", "失效验收仍保留独立终验"),
        ):
            with self.subTest(field=field):
                self.make_full()
                self.invalidate_after(3)
                self.enter_settled_stage(2)
                self.state[field] = value
                self.assert_blocked(self.run_check(), message)

    def test_invalidated_artifact_names_and_list_are_validated(self):
        for value in ("03-design.md", ["../03-design.md"], ["facts.md"], [3], ["03-design.md", "03-design.md"]):
            with self.subTest(value=value):
                self.make_full()
                self.state["invalidated_artifacts"] = value
                self.assert_blocked(self.run_check(), "invalidated_artifacts")

    def test_invalidated_future_artifact_may_already_be_archived(self):
        self.make_full()
        self.invalidate_after(3)
        self.enter_settled_stage(2)
        path = self.arts / "03-design.md"
        self.write_af("history/change-1/artifacts/03-design.md", path.read_text(encoding="utf-8"))
        path.unlink()
        self.state["artifacts"].remove("03-design.md")
        self.assert_pass(self.run_check())

    def test_invalidation_does_not_excuse_unregistered_files(self):
        self.make_full()
        self.invalidate_after(3)
        self.enter_settled_stage(2)
        self.state["artifacts"].remove("03-design.md")
        self.assert_blocked(self.run_check(), "产物存在但未登记进 state.yaml：03-design.md")

    def test_regression_rewind_keeps_current_initial_test_results(self):
        self.make_full()
        self.invalidate_after(10)
        self.state["stage"] = 9
        self.assertEqual(self.state["acceptance_results"], {"A1": "pass", "A2": "pass"})
        self.assert_pass(self.run_check())

    def test_invalidation_keeps_open_bugs_visible_until_migrated(self):
        self.make_full()
        self.write_bug(status="待修复")
        self.state["open_bugs"] = ["BUG-1"]
        self.invalidate_after(8)
        self.state["stage"] = 7
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| T1 | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| T2 | — |")
        self.assert_pass(self.run_check())
        self.assertEqual(self.state["open_bugs"], ["BUG-1"])
        self.state["stage"] = 8
        self.assert_blocked(self.run_check(), "失效缺陷单仍有未迁移的未关闭缺陷")
        self.state["invalidated_artifacts"].remove("08-test-report.md")
        self.state["invalidated_artifacts"].remove("09-bugs.md")
        self.state["acceptance_results"] = {"A1": "pass", "A2": "pass"}
        self.replace_art("04-mapping.md", "| T1 | — |", "| T1 | E1 |")
        self.replace_art("04-mapping.md", "| T2 | — |", "| T2 | E2 |")
        self.assert_pass(self.run_check())
        self.assertEqual(self.state["open_bugs"], ["BUG-1"])

    def test_invalidating_a_bug_report_cannot_erase_unresolved_bugs(self):
        self.make_full()
        self.write_bug(status="待修复")
        self.invalidate_after(8)
        self.state["stage"] = 7
        self.assert_blocked(self.run_check(), "未关闭问题未保留在 state.open_bugs：BUG-1")

    def test_invalidated_ux_issues_are_carried_before_rewalk(self):
        self.make_full()
        row, detail = ux_issue("UX-1", "W3", "待复查")
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)]
        self.write_art("07-walkthrough.md", walkthrough_doc(results, "9/10", "不通过", row + detail))
        self.state["open_ux_issues"] = ["UX-1"]
        self.state["walkthrough_result"] = "fail"
        self.invalidate_after(7)
        self.state["stage"] = 6
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| T1 | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| T2 | — |")
        self.assert_pass(self.run_check())
        self.state["stage"] = 7
        self.assert_blocked(self.run_check(), "失效走查仍有未迁移的未关闭问题：UX-1")
        self.state["stage"] = 6
        self.state["open_ux_issues"] = []
        self.assert_blocked(self.run_check(), "未关闭问题未保留在 state.open_ux_issues：UX-1")

    def test_skipped_artifact_invalidation_still_needs_disposition(self):
        self.make_full(design=False)
        self.state["invalidated_artifacts"] = ["03-design.md"]
        self.assert_blocked(self.run_check(), "失效产物尚未处置：03-design.md")

    def test_legacy_project_without_invalidation_list_still_passes(self):
        self.make_full()
        del self.state["invalidated_artifacts"]
        self.assert_pass(self.run_check())

    def test_retired_acceptance_cannot_remain_in_current_mapping(self):
        self.make_full()
        self.replace_acceptance()
        self.replace_art("04-mapping.md", "| A3 | 约束二 | 服务层 | T2 | E2 |",
                         "| A3 | 约束二 | 服务层 | T2 | E2 |\n| A2 | 旧约束 | 服务层 | T2 | E2 |")
        self.assert_blocked(self.run_check(), "映射表包含失效或不存在的验收标准：A2")

    def test_retired_acceptance_cannot_remain_in_current_contract(self):
        self.make_full()
        self.replace_acceptance()
        self.write_af("facts.md", (self.af / "facts.md").read_text(encoding="utf-8") +
                      "| A2 | 校验 | 旧约束 |")
        self.assert_blocked(self.run_check(), "facts 05 包含失效或不存在的验收标准：A2")

    def test_retired_acceptance_cannot_remain_in_task_acceptance(self):
        self.make_full()
        self.replace_acceptance()
        self.replace_art("05-tasks.md", "- 验收标准：A3", "- 验收标准：A3、A2")
        self.assert_blocked(self.run_check(), "任务引用失效或不存在的验收标准：T2 → A2")

    def test_retired_acceptance_cannot_hide_in_additional_task_field(self):
        self.make_full()
        self.replace_acceptance()
        self.replace_art("05-tasks.md", "- 验收标准：A3", "- 验收标准：A3\n- 验收标准：A2")
        self.assert_blocked(self.run_check(), "任务引用失效或不存在的验收标准：T2 → A2")

    def test_retired_acceptance_cannot_remain_in_current_test_coverage(self):
        self.make_full()
        self.replace_acceptance()
        self.replace_art("08-test-report.md", "| A3 | E2 | 通过 |", "| A3 | E2 | 通过 |\n| A2 | E3 | 通过 |")
        self.assert_blocked(self.run_check(), "测试覆盖表包含失效或不存在的验收标准：A2")

    def test_retired_acceptance_cannot_remain_in_current_regression(self):
        self.make_full()
        self.replace_acceptance()
        self.replace_art("10-regression.md", "| E2 | A3 | 全量验收 | 通过 | |",
                         "| E2 | A3 | 全量验收 | 通过 | |\n| E3 | A2 | 历史标准 | 通过 | |")
        self.assert_blocked(self.run_check(), "回归执行引用失效或不存在的验收标准：A2")

    def test_retired_acceptance_can_be_explained_outside_active_task_field(self):
        self.make_full()
        self.replace_acceptance()
        self.replace_art("05-tasks.md", "- 验收标准：A3", "- 验收标准：A3\n- 变更说明：A2 已作废，由 A3 替代")
        self.assert_pass(self.run_check())

    def test_changed_design_requires_reconfirmation_without_facts_bump(self):
        self.make_full()
        self.invalidate_after(3)
        self.enter_settled_stage(2)
        self.assert_pass(self.run_check())
        self.enter_settled_stage(3)
        self.assert_blocked(self.run_check(), "必需产物已失效：03-design.md")
        revised = DESIGN.replace("loading 后提示已受理", "loading 后展示处理人").replace(
            "确认结论：已确认", "确认结论：待确认")
        self.write_art("03-design.md", revised)
        self.state["invalidated_artifacts"].remove("03-design.md")
        self.state["signoffs"]["design"] = "confirmed"
        self.assert_blocked(self.run_check(), "03-design.md 尚未取得用户确认")
        self.write_art("03-design.md", revised.replace("确认结论：待确认", "确认结论：已确认").replace(
            "用户原话：「确认，往下走」", "用户原话：「确认本轮设计修改」"))
        self.assert_pass(self.run_check())
        self.assertEqual(self.state["facts_version"], 1)

    def test_business_change_rewinds_reconfirms_and_rebuilds_through_release(self):
        self.make_full()
        original = {name: (self.arts / name).read_text(encoding="utf-8") for name in self.state["artifacts"]}
        original_facts = (self.af / "facts.md").read_bytes()
        for name, text in original.items():
            self.write_af("history/change-1/artifacts/" + name, text)
        shutil.copy2(self.af / "facts.md", self.af / "history/change-1/facts.md")
        dump_state(self.af / "history/change-1/state.yaml", self.state)
        self.replace_acceptance()
        revised = {name: (self.arts / name).read_text(encoding="utf-8") for name in self.state["artifacts"]}
        for name, text in original.items():
            if int(name[:2]) >= 2:
                self.write_art(name, text)
        self.invalidate_after(2)
        self.assert_blocked(self.run_check(), "必需产物已失效：02-prd.md")
        self.state["stage"] = 11
        self.assert_blocked(self.run_check(), "必需产物已失效：11-release.md")
        self.enter_settled_stage(2)
        draft = revised["02-prd.md"].replace("确认结论：已确认", "确认结论：待确认")
        self.write_art("02-prd.md", draft)
        self.state["invalidated_artifacts"].remove("02-prd.md")
        self.assert_blocked(self.run_check(), "PRD 未经用户确认")
        self.state["signoffs"]["prd"] = "confirmed"
        self.assert_blocked(self.run_check(), "02-prd.md 尚未取得用户确认")

        def restore(name):
            text = revised[name].replace("用户原话：「确认，往下走」", "用户原话：「确认 v2 的本轮修改」").replace(
                "确认时间：2026-11-01T10:00:00+08:00", "确认时间：2026-11-02T11:00:00+08:00")
            self.write_art(name, text)
            if name in self.state["invalidated_artifacts"]:
                self.state["invalidated_artifacts"].remove(name)

        restore("02-prd.md")
        restore("02-prototype.md")
        self.state["signoffs"]["prototype"] = "confirmed"
        self.assert_pass(self.run_check())
        self.enter_settled_stage(3)
        restore("03-design.md")
        self.state["signoffs"]["design"] = "confirmed"
        self.assert_pass(self.run_check())
        self.enter_settled_stage(4)
        restore("04-arch.md")
        restore("04-mapping.md")
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.assert_pass(self.run_check())
        self.state["stage"] = 5
        restore("05-tasks.md")
        self.replace_art("04-mapping.md", "| A1 | 约束一 | 数据层 | — | — |",
                         "| A1 | 约束一 | 数据层 | T1 | — |")
        self.replace_art("04-mapping.md", "| A3 | 约束二 | 服务层 | — | — |",
                         "| A3 | 约束二 | 服务层 | T2 | — |")
        self.assert_pass(self.run_check())
        self.state["stage"] = 6
        restore("06-dev-log.md")
        self.state["task_status"] = {"T1": "done", "T2": "done"}
        self.assert_pass(self.run_check())
        self.state["stage"] = 7
        restore("07-walkthrough.md")
        self.state["walkthrough_result"] = "pass"
        self.assert_pass(self.run_check())
        self.state["stage"] = 8
        restore("08-test-report.md")
        restore("04-mapping.md")
        self.state["acceptance_results"] = {"A1": "pass", "A3": "pass"}
        self.assert_pass(self.run_check())
        self.state["stage"] = 9
        restore("09-bugs.md")
        self.assert_pass(self.run_check())
        self.state["stage"] = 10
        restore("10-regression.md")
        self.state["regression_result"] = "pass"
        self.assert_pass(self.run_check())
        self.state["stage"] = 11
        self.assert_blocked(self.run_check(), "必需产物已失效：11-release.md")
        restore("11-release.md")
        self.replace_art("11-release.md", "release-log-123", "release-log-v2")
        self.state["release_status"] = "verified"
        self.assert_pass(self.run_check())
        self.assertEqual(self.state["invalidated_artifacts"], [])
        self.assertEqual((self.af / "history/change-1/facts.md").read_bytes(), original_facts)
        for name, text in original.items():
            self.assertEqual((self.af / "history/change-1/artifacts" / name).read_text(encoding="utf-8"), text)
        self.assertEqual((self.af / "tech-stack.md").read_text(encoding="utf-8"), TECH_STACK)

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

    def test_delegated_early_stages_require_current_specialist_only(self):
        for stage, role in ((1, "analyst"), (2, "pm"), (4, "architect"), (5, "architect")):
            with self.subTest(stage=stage):
                self.make_full(design=False)
                self.truncate(stage)
                if stage == 4:
                    self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
                    self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
                elif stage == 5:
                    self.replace_art("04-mapping.md", "| E1 |", "| — |")
                    self.replace_art("04-mapping.md", "| E2 |", "| — |")
                self.state["mode"] = 2
                self.assert_blocked(self.run_check(), "缺少 agent_sessions." + role)
                self.state["agent_sessions"] = {role: "agent:" + role}
                if stage == 4:
                    self.state["agent_sessions"]["tester"] = "agent:trial-reader"
                    self.record_dispatch("architect", "tester")
                else:
                    self.record_dispatch(role)
                self.assert_pass(self.run_check())

    def test_stage1_cannot_reuse_stage0_analyst_identity_as_current_dispatch(self):
        self.make_full(design=False)
        self.truncate(1)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"analyst": "agent:analyst-from-stage0"}
        for dispatch in (None, {"stage": 0, "analyst": "call:stage0-analyst; completed:stage0-result"}):
            with self.subTest(dispatch=dispatch):
                if dispatch is not None:
                    self.state["stage_dispatch"] = dispatch
                self.assert_blocked(self.run_check(), "stage_dispatch")

    def test_stage1_new_analyst_needs_current_completion_evidence(self):
        self.make_full(design=False)
        self.truncate(1)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"analyst": "agent:analyst-stage1"}
        self.state["stage_dispatch"] = {"stage": 1, "analyst": "agent:analyst-stage1"}
        self.assert_blocked(self.run_check(), "不能只填会话 ID")
        self.record_dispatch("analyst")
        self.assert_pass(self.run_check())

    def test_current_dispatch_requires_valid_stage_and_completed_role_record(self):
        self.make_full(design=False)
        self.truncate(1)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"analyst": "agent:a"}
        for stage in (0, 2, True, "1"):
            with self.subTest(stage=stage):
                self.record_dispatch("analyst")
                self.state["stage_dispatch"]["stage"] = stage
                self.assert_blocked(self.run_check(), "stage_dispatch.stage")
        for evidence in ("", "   ", "<dispatch-and-result>", 123, True):
            with self.subTest(evidence=evidence):
                self.state["stage_dispatch"] = {"stage": 1, "analyst": evidence}
                self.assert_blocked(self.run_check(), "缺少本阶段实际派发与完成回报证据")
        self.state["stage_dispatch"] = {"stage": 1}
        self.assert_blocked(self.run_check(), "stage_dispatch.analyst")
        self.record_dispatch("analyst")
        self.assert_pass(self.run_check())

    def test_pm_phase_requires_pm_dispatch_not_analyst_completion(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"analyst": "agent:a", "pm": "agent:p"}
        self.record_dispatch("analyst")
        self.assert_blocked(self.run_check(), "stage_dispatch.pm")
        self.record_dispatch("pm")
        self.assert_pass(self.run_check())

    def test_architecture_needs_current_tester_trial_read(self):
        self.make_full(design=False)
        self.truncate(4)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"architect": "agent:arch", "tester": "agent:test"}
        self.record_dispatch("architect")
        self.assert_blocked(self.run_check(), "stage_dispatch.tester")
        self.record_dispatch("architect", "tester")
        self.assert_pass(self.run_check())

    def test_legacy_developer_identity_does_not_replace_current_fe_be_dispatch(self):
        self.make_full(design=False)
        self.truncate(6)
        self.replace_art("04-mapping.md", "| E1 |", "| — |")
        self.replace_art("04-mapping.md", "| E2 |", "| — |")
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:legacy-dev"}
        self.record_dispatch("developer")
        result = self.run_check()
        self.assert_blocked(result, "stage_dispatch.fe")
        self.assertIn("stage_dispatch.be", result.stdout)
        self.record_dispatch("fe", "be")
        self.assert_blocked(self.run_check(), "缺少 agent_sessions.fe")
        self.state["agent_sessions"].update(fe="agent:legacy-dev", be="agent:legacy-dev")
        self.assert_blocked(self.run_check(), "fe 与 be 必须是独立身份")
        self.state["agent_sessions"]["be"] = "agent:backend"
        self.assert_blocked(self.run_check(), "本阶段的 fe 不能沿用旧 developer 会话")
        self.state["agent_sessions"]["fe"] = "agent:frontend"
        self.assert_pass(self.run_check())

    def test_current_fe_dispatch_requires_new_identity_not_legacy_developer(self):
        self.make_full(design=False)
        self.truncate(6)
        self.replace_art("04-mapping.md", "| E1 |", "| — |")
        self.replace_art("04-mapping.md", "| E2 |", "| — |")
        self.replace_art("05-tasks.md", "| BE |", "| FE |")
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:resumed"}
        self.record_dispatch("fe")
        self.assert_blocked(self.run_check(), "缺少 agent_sessions.fe")
        self.state["agent_sessions"]["fe"] = "agent:resumed"
        self.assert_blocked(self.run_check(), "本阶段的 fe 不能沿用旧 developer 会话")
        self.state["agent_sessions"]["fe"] = "agent:frontend"
        self.assert_pass(self.run_check())

    def test_bug_repair_requires_current_owner_dispatch_and_tester_return(self):
        for owner, task, example, standard, role, absent in (("BE", "T1", "E1", "A1", "be", "fe"),
                                                           ("FE", "T2", "E2", "A2", "fe", "be")):
            with self.subTest(owner=owner):
                self.make_full(design=False)
                self.truncate(9)
                self.write_bug([(1, example, standard, "通过", "test-only-retest-log")], task=task,
                               owner=owner, standard=standard)
                self.state["mode"] = 2
                self.state["agent_sessions"] = {"developer": "agent:dev", "tester": "agent:test"}
                self.record_dispatch("tester")
                result = self.run_check()
                self.assert_blocked(result, "stage_dispatch." + role)
                self.assertNotIn("stage_dispatch." + absent, result.stdout)
                self.record_dispatch(role, "tester")
                self.assert_blocked(self.run_check(), "缺少 agent_sessions." + role)
                self.state["agent_sessions"][role] = "agent:dev"
                self.assert_blocked(self.run_check(), "本阶段的 %s 不能沿用旧 developer 会话" % role)
                self.state["agent_sessions"][role] = "agent:%s-stage9" % role
                self.assert_pass(self.run_check())

    def test_walkthrough_requires_fe_only_when_a_ux_issue_was_closed(self):
        results = [(1, "W%d" % n, "不通过" if n == 3 else "通过") for n in range(1, 11)]
        for status, rows, score in (("遗留", results, "9/10"), ("已关闭", results + [(2, "W3", "通过")], "10/10")):
            with self.subTest(status=status):
                self.make_full()
                self.truncate(7)
                self.replace_art("04-mapping.md", "| E1 |", "| — |")
                self.replace_art("04-mapping.md", "| E2 |", "| — |")
                self.write_walkthrough(rows, score, "通过", [ux_issue("UX-1", "W3", status, closed=status == "已关闭")])
                self.state["mode"] = 2
                self.state["agent_sessions"] = {"designer": "agent:ux-stage7", "fe": "agent:fe-stage7", "be": "agent:be"}
                self.record_dispatch("designer")
                if status == "已关闭":
                    self.assert_blocked(self.run_check(), "stage_dispatch.fe 缺少本阶段实际派发与完成回报证据")
                    self.record_dispatch("designer", "fe")
                self.assert_pass(self.run_check())
        self.record_execution()
        self.state["agent_sessions"]["fe"] = "agent:fe-stage6"
        self.state["session_log"] = ["7 6 fe agent:fe-stage6"]
        self.log_sessions(8, "designer", "fe")
        self.assert_blocked(self.run_check(), "会话 agent:fe-stage6 在 session_log 中出现在多次执行")
        self.state["agent_sessions"]["fe"] = "agent:fe-stage7"
        self.state["session_log"] = ["7 6 fe agent:fe-stage6"]
        self.log_sessions(8, "designer", "fe")
        self.assert_pass(self.run_check())

    def test_fe_bug_listing_walkthrough_points_requires_designer_recheck(self):
        records = [(1, "E2", "A2", "通过", "test-only-retest-log")]
        for label, extra, designer_needed in (
                ("无走查点", "\n**待验点** *（开发填写）*\n\n1. 校验逻辑\n", False),
                ("加粗小节", "\n**待验点** *（开发填写）*\n\n1. 受影响的走查点：W3\n", True),
                ("单行字段", "- 待验点：W3\n", True)):
            with self.subTest(label=label):
                self.make_full()
                self.truncate(9)
                self.write_bug(records, task="T2", owner="FE", standard="A2", extra=extra)
                self.state["mode"] = 2
                self.state["agent_sessions"] = {"designer": "agent:ux-stage9", "fe": "agent:fe-stage9",
                                                "be": "agent:be-stage6", "tester": "agent:test-stage9"}
                self.record_dispatch("tester", "fe")
                if designer_needed:
                    self.assert_blocked(self.run_check(), "stage_dispatch.designer 缺少本阶段实际派发与完成回报证据")
                    self.record_dispatch("tester", "fe", "designer")
                self.assert_pass(self.run_check())
        self.write_bug(records, task="T2", owner="FE", standard="A2", extra="- 待验点：W99\n")
        self.assert_blocked(self.run_check(), "缺陷单待验点引用了未定义的走查点：BUG-1 → W99")
        self.write_bug(records, task="T2", owner="FE", standard="A2", extra="- 待验点：W3\n")
        self.record_execution()
        self.state["agent_sessions"]["designer"] = "agent:ux-stage7"
        self.state["session_log"] = ["7 7 designer agent:ux-stage7"]
        self.log_sessions(9, "tester", "fe", "designer")
        self.assert_blocked(self.run_check(), "会话 agent:ux-stage7 在 session_log 中出现在多次执行")
        self.state["agent_sessions"]["designer"] = "agent:ux-stage9"
        self.state["session_log"] = ["7 7 designer agent:ux-stage7"]
        self.log_sessions(9, "tester", "fe", "designer")
        self.assert_pass(self.run_check())

    def test_delegated_design_requires_separate_author_and_reviewer(self):
        self.make_full()
        self.truncate(3)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"designer": "agent:ux"}
        self.assert_blocked(self.run_check(), "缺少 agent_sessions.design_reviewer")
        self.state["agent_sessions"]["design_reviewer"] = "agent:ux"
        self.assert_blocked(self.run_check(), "必须是独立身份")
        self.state["agent_sessions"]["design_reviewer"] = "agent:review"
        self.record_dispatch("designer", "design_reviewer")
        self.assert_pass(self.run_check())

    def test_delegated_no_design_does_not_require_design_sessions(self):
        self.make_full(design=False)
        self.truncate(3)
        self.state["mode"] = 2
        self.assert_pass(self.run_check())

    def test_stage_execution_absent_stays_legacy_compatible_but_present_must_be_recorded(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"pm": "agent:p"}
        self.record_dispatch("pm")
        self.assert_pass(self.run_check())
        for record in ({"stage": 2, "strategy": ""}, {}, ""):
            with self.subTest(record=record):
                self.state["stage_execution"] = record
                self.assert_blocked(self.run_check(), "stage_execution.strategy 未记录")
        self.state["stage_execution"] = ["coordinated"]
        self.assert_blocked(self.run_check(), "stage_execution 必须是一层字典")
        self.record_execution()
        self.assert_pass(self.run_check())

    def test_coordinated_execution_requires_current_stage_coordinator_and_handoff(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"pm": "agent:p"}
        self.record_dispatch("pm")
        for stage in (0, 1, True, "2", None):
            with self.subTest(stage=stage):
                self.record_execution()
                self.state["stage_execution"]["stage"] = stage
                self.assert_blocked(self.run_check(), "stage_execution.stage")
        for key, message in (("coordinator", "stage_execution.coordinator 必须是本阶段协调器的实际 ID"),
                             ("handoff", "stage_execution.handoff 缺少")):
            for value in ("", "   ", "<协调器 ID>", "……", 123, None):
                with self.subTest(key=key, value=value):
                    self.record_execution()
                    self.state["stage_execution"][key] = value
                    self.assert_blocked(self.run_check(), message)
        for value in ("agent:p", "agent:coordinator-stage2"):
            with self.subTest(handoff=value):
                self.record_execution()
                self.state["stage_execution"]["handoff"] = value
                self.assert_blocked(self.run_check(), "stage_execution.handoff 不能只填会话 ID")
        for strategy in ("parallel", "Coordinated", 1, True):
            with self.subTest(strategy=strategy):
                self.record_execution()
                self.state["stage_execution"]["strategy"] = strategy
                self.assert_blocked(self.run_check(), "必须为 coordinated 或 direct")
        self.record_execution()
        self.assert_pass(self.run_check())

    def test_coordinator_must_differ_from_every_role_and_reviewer(self):
        self.make_full()
        self.truncate(3)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"analyst": "agent:a", "designer": "agent:ux", "design_reviewer": "agent:review"}
        self.record_dispatch("designer", "design_reviewer")
        for identity in self.state["agent_sessions"].values():
            with self.subTest(identity=identity):
                self.record_execution()
                self.state["stage_execution"]["coordinator"] = identity
                self.assert_blocked(self.run_check(), "stage_execution.coordinator 必须独立")
        self.record_execution()
        self.assert_pass(self.run_check())

    def test_direct_fallback_requires_reason_and_cannot_claim_coordinator(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"pm": "agent:p"}
        self.record_dispatch("pm")
        for reason in (None, "", "<实际原生嵌套限制与证据>", 0):
            with self.subTest(reason=reason):
                self.record_execution("direct")
                self.state["stage_execution"]["fallback_reason"] = reason
                self.assert_blocked(self.run_check(), "stage_execution.fallback_reason")
        for key in ("coordinator", "handoff"):
            with self.subTest(key=key):
                self.record_execution("direct")
                self.state["stage_execution"][key] = "agent:coordinator-stage2"
                self.assert_blocked(self.run_check(), "直接派工不存在协调器")
        self.record_execution("direct")
        self.assert_pass(self.run_check())

    def test_skipped_design_stage_cannot_carry_previous_execution_record(self):
        self.make_full(design=False)
        self.truncate(3)
        self.state["mode"] = 2
        self.state["stage_execution"] = {"stage": 2, "strategy": "coordinated",
                                         "coordinator": "agent:coordinator-stage2",
                                         "handoff": "test-call:stage2-coordinator; returned:test-handoff-stage2"}
        self.assert_blocked(self.run_check(), "stage_execution.stage 必须对应当前阶段 3")
        self.state["stage_execution"] = {"stage": 3, "strategy": ""}
        self.assert_pass(self.run_check())

    def test_role_switch_mode_cannot_claim_coordinated_or_direct_execution(self):
        self.make_full(design=False)
        for strategy in ("coordinated", "direct"):
            with self.subTest(strategy=strategy):
                self.record_execution(strategy)
                self.assert_blocked(self.run_check(), "stage_execution.strategy 必须留空")
        self.state["stage_execution"] = {"stage": 11, "strategy": ""}
        self.assert_pass(self.run_check())

    def test_session_log_absent_stays_legacy_compatible_but_present_must_record_current_sessions(self):
        self.make_full(design=False)
        self.truncate(1)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"analyst": "agent:analyst-stage1"}
        self.record_dispatch("analyst")
        self.record_execution()
        self.assert_pass(self.run_check())
        earlier = ["1 0 coordinator agent:coordinator-stage0", "1 0 analyst agent:analyst-stage0"]
        for log in ([], earlier):
            with self.subTest(log=log):
                self.state["session_log"] = list(log)
                self.assert_blocked(self.run_check(), "session_log 最新一次执行不是当前阶段 1")
        self.state["session_log"] = list(earlier)
        self.log_sessions(2)
        self.assert_blocked(self.run_check(), "agent_sessions.analyst 的会话 agent:analyst-stage1 没有记进 session_log 第 2 次执行")
        self.state["session_log"] = earlier + ["2 1 analyst agent:analyst-stage1"]
        self.assert_blocked(self.run_check(), "stage_execution.coordinator 的会话 agent:coordinator-stage1 没有记进")
        self.log_sessions(2)
        self.assert_pass(self.run_check())

    def test_session_log_each_stage_entry_uses_a_new_execution_number(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"pm": "agent:pm-stage2"}
        self.record_dispatch("pm")
        self.record_execution()
        earlier = ["1 0 analyst agent:analyst-stage0", "2 1 analyst agent:analyst-stage1"]
        self.state["session_log"] = list(earlier)
        self.log_sessions(2, "pm")
        self.assert_blocked(self.run_check(), "session_log 第 2 次执行混用了阶段 1、2")
        self.state["session_log"] = list(earlier)
        self.log_sessions(3, "pm")
        self.assert_pass(self.run_check())

    def test_session_log_blocks_carrying_previous_stage_session_into_new_stage(self):
        self.make_full(design=False)
        self.truncate(1)
        self.state["mode"] = 2
        self.record_dispatch("analyst")
        earlier = ["1 0 coordinator agent:coordinator-stage0", "1 0 analyst agent:analyst-stage0"]
        for analyst, coordinator in (("agent:analyst-stage0", "agent:coordinator-stage1"),
                                     ("agent:analyst-stage1", "agent:coordinator-stage0")):
            with self.subTest(analyst=analyst, coordinator=coordinator):
                self.state["agent_sessions"] = {"analyst": analyst}
                self.record_execution()
                self.state["stage_execution"]["coordinator"] = coordinator
                self.state["session_log"] = list(earlier)
                self.log_sessions(2, "analyst")
                self.assert_blocked(self.run_check(), "在 session_log 中出现在多次执行")
        self.state["agent_sessions"] = {"analyst": "agent:analyst-stage1"}
        self.record_execution()
        self.state["session_log"] = list(earlier)
        self.log_sessions(2, "analyst")
        self.assert_pass(self.run_check())

    def test_session_log_rollback_needs_new_execution_and_new_sessions(self):
        self.make_full(design=False)
        self.truncate(4)
        self.replace_art("04-mapping.md", "| T1 | E1 |", "| — | — |")
        self.replace_art("04-mapping.md", "| T2 | E2 |", "| — | — |")
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"architect": "agent:arch-stage4", "tester": "agent:test-stage4"}
        self.record_dispatch("architect", "tester")
        self.record_execution()
        first = ["5 4 coordinator agent:coordinator-stage4", "5 4 architect agent:arch-stage4",
                 "5 4 tester agent:test-stage4", "6 5 architect agent:arch-stage5", "7 6 fe agent:fe-stage6"]
        self.state["session_log"] = list(first)
        self.assert_blocked(self.run_check(), "session_log 最新一次执行不是当前阶段 4")
        self.state["stage_execution"]["coordinator"] = "agent:coordinator-redo4"
        self.log_sessions(8, "architect", "tester")
        self.assert_blocked(self.run_check(), "会话 agent:arch-stage4 在 session_log 中出现在多次执行")
        self.state["agent_sessions"] = {"architect": "agent:arch-redo4", "tester": "agent:test-redo4"}
        self.state["session_log"] = list(first)
        self.log_sessions(8, "architect", "tester")
        self.assert_pass(self.run_check())

    def test_session_log_rejects_malformed_or_shared_entries(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"pm": "agent:pm-stage2"}
        self.record_dispatch("pm")
        self.record_execution()
        for entry in ("3 2 pm", "x 2 pm agent:x", "0 2 pm agent:x", "3 12 pm agent:x",
                      "3 2 boss agent:x", "3 2 developer agent:x", "3 2 pm <会话 ID>", 7):
            with self.subTest(entry=entry):
                self.state["session_log"] = []
                self.log_sessions(3, "pm")
                self.state["session_log"].append(entry)
                self.assert_blocked(self.run_check(), "应写成「执行序号 阶段 角色 会话ID」")
        self.state["session_log"] = "3 2 pm agent:pm-stage2"
        self.assert_blocked(self.run_check(), "session_log 必须是列表")
        self.state["session_log"] = ["1 1 tester agent:pm-stage2"]
        self.log_sessions(3, "pm")
        self.assert_blocked(self.run_check(), "会话 agent:pm-stage2 在 session_log 中出现在多次执行或多个角色")

    def test_session_log_covers_every_role_dispatched_this_stage(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"pm": "agent:pm-stage2", "designer": "agent:ux-stage2"}
        self.record_dispatch("pm", "designer")
        self.record_execution()
        self.state["session_log"] = []
        self.log_sessions(3, "pm")
        self.assert_blocked(self.run_check(), "agent_sessions.designer 的会话 agent:ux-stage2 没有记进 session_log 第 3 次执行")
        self.state["session_log"] = []
        self.log_sessions(3, "pm", "designer")
        self.assert_pass(self.run_check())

    def test_delegated_task_types_select_required_developers(self):
        for kind, role, absent in (("FE", "fe", "be"), ("BE", "be", "fe"), ("JOB", "be", "fe")):
            with self.subTest(kind=kind):
                self.make_full(design=False)
                self.truncate(6)
                self.replace_art("04-mapping.md", "| E1 |", "| — |")
                self.replace_art("04-mapping.md", "| E2 |", "| — |")
                self.replace_art("05-tasks.md", "| BE |", "| " + kind + " |")
                self.replace_art("05-tasks.md", "| FE |", "| " + kind + " |")
                self.state["mode"] = 2
                result = self.run_check()
                self.assert_blocked(result, "缺少 agent_sessions." + role)
                self.assertNotIn("缺少 agent_sessions." + absent, result.stdout)
                self.assertNotIn("缺少 agent_sessions.tester", result.stdout)
                self.state["agent_sessions"] = {role: "agent:" + role}
                self.record_dispatch(role)
                self.assert_pass(self.run_check())

    def test_delegated_mixed_tasks_require_both_developers(self):
        self.make_full(design=False)
        self.truncate(6)
        self.replace_art("04-mapping.md", "| E1 |", "| — |")
        self.replace_art("04-mapping.md", "| E2 |", "| — |")
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"fe": "agent:fe"}
        self.assert_blocked(self.run_check(), "缺少 agent_sessions.be")
        self.state["agent_sessions"]["be"] = "agent:be"
        self.record_dispatch("fe", "be")
        self.assert_pass(self.run_check())

    def test_delegated_roles_cannot_share_context(self):
        self.make_full()
        self.state["mode"] = 2
        sessions = {role: "agent:" + role for role in
                    ("analyst", "pm", "designer", "architect", "fe", "be", "tester", "operator")}
        for first, second in (("analyst", "pm"), ("fe", "be"), ("fe", "tester"),
                              ("be", "designer"), ("architect", "operator")):
            with self.subTest(first=first, second=second):
                self.state["agent_sessions"] = dict(sessions)
                self.state["agent_sessions"][second] = sessions[first]
                self.assert_blocked(self.run_check(), "必须是独立身份")
        self.state["agent_sessions"] = sessions
        self.record_dispatch("operator")
        self.assert_pass(self.run_check())

    def test_delegated_later_stages_require_tester_and_operator_when_due(self):
        for stage, role in ((7, "designer"), (8, "tester"), (9, "tester"), (10, "tester"), (11, "operator")):
            with self.subTest(stage=stage):
                self.make_full()
                self.truncate(stage)
                if stage == 7:
                    self.replace_art("04-mapping.md", "| E1 |", "| — |")
                    self.replace_art("04-mapping.md", "| E2 |", "| — |")
                self.state["mode"] = 2
                sessions = {"fe": "agent:fe", "be": "agent:be", "designer": "agent:ux", "tester": "agent:test"}
                sessions.pop(role, None)
                self.state["agent_sessions"] = sessions
                self.assert_blocked(self.run_check(), "缺少 agent_sessions." + role)
                sessions[role] = "agent:" + role
                self.record_dispatch(role)
                self.assert_pass(self.run_check())

    def test_delegated_legacy_developer_identity_remains_usable(self):
        self.make_full(design=False)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:dev", "tester": "agent:test", "operator": "agent:ops"}
        self.record_dispatch("operator")
        self.assert_pass(self.run_check())
        self.state["agent_sessions"]["fe"] = "agent:dev"
        self.assert_pass(self.run_check())

    def test_delegated_invalid_session_values_are_blocked(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["mode"] = 2
        for value in (True, 123, "<agent-id>", "..."):
            with self.subTest(value=value):
                self.state["agent_sessions"] = {"pm": value}
                self.assert_blocked(self.run_check(), "agent_sessions.pm")

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
        self.state["agent_sessions"] = {"developer": "agent:dev", "designer": "agent:ux", "tester": "agent:test", "operator": "agent:ops", "final_reviewer": "human:reviewer"}
        self.state["final_review_result"] = "pass"
        self.state["final_review_evidence"] = "review-record-123"
        self.record_dispatch("operator")
        self.assert_pass(self.run_check())

    def test_mode3_final_reviewer_must_differ_from_all_recorded_roles(self):
        self.make_full(design=False)
        self.state["mode"] = 3
        self.state["agent_sessions"] = {"fe": "agent:fe", "be": "agent:be", "tester": "agent:test",
                                        "operator": "model:ops", "final_reviewer": "model:ops"}
        self.state["final_review_result"] = "pass"
        self.state["final_review_evidence"] = "review-record-123"
        self.assert_blocked(self.run_check(), "final_reviewer 必须独立于全部执行角色")

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

    def test_research_notes_do_not_change_question_ledger(self):
        self.make_full(design=False)
        questions = QUESTIONS + "| Q2 | 2 | 删除后如何恢复 | A1 | Q1 | 推荐 B | 「选 B」 | 已解决 | 依据见调研记录 |\n"
        self.write_af("questions.md", questions + RESEARCH_NOTES)
        self.assert_pass(self.run_check())

    def test_researched_recommendation_still_needs_user_answer(self):
        self.make_full(design=False)
        questions = QUESTIONS + "| Q2 | 2 | 删除后如何恢复 | A1 | Q1 | 推荐 B | | 按推荐 | 依据见调研记录 |\n"
        self.write_af("questions.md", questions + RESEARCH_NOTES)
        self.assert_blocked(self.run_check(), "没有用户答复原话：Q2")

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
        self.confirm_design_images(("P1", "P2"))
        self.replace_art("02-prototype.md", "| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |",
                         "| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |\n| P2 | 详情页 | 查看详情 | A1 | prototype/P1.html |")
        self.replace_art("02-prototype.md", "- 字段：编号、状态\n", "- 字段：编号、状态\n\n### P2 · 详情页\n- 字段：编号\n")
        result = self.run_check()
        self.assert_blocked(result, "设计稿未覆盖原型页面：P2")
        self.assertIn("页面没有落到任何 FE 任务：P2", result.stdout)

    def test_design_without_selfcheck_is_blocked(self):
        self.make_full()
        self.write_art("03-design.md", DESIGN.replace(SELFCHECK, ""))
        self.assert_blocked(self.run_check(), "缺少「设计稿自检」小节")

    def test_design_selfcheck_needs_independent_review(self):
        self.make_full()
        self.replace_art("03-design.md", "- 独立评审：另一个会话评审，问题列在下表", "- 独立评审：<待评审>")
        self.assert_blocked(self.run_check(), "设计稿自检缺少「独立评审」的结果")

    def test_design_selfcheck_conclusion_must_pass(self):
        self.make_full()
        self.replace_art("03-design.md", "- 结论：通过\n", "- 结论：<待独立评审后填写>\n")
        self.assert_blocked(self.run_check(), "设计稿自检结论不是「通过」")

    def test_design_selfcheck_pass_prefix_is_not_a_pass(self):
        self.make_full()
        self.replace_art("03-design.md", "- 结论：通过\n", "- 结论：通过，但尚未完成独立评审\n")
        self.assert_blocked(self.run_check(), "设计稿自检结论不是「通过」")

    def test_design_selfcheck_open_issue_is_blocked(self):
        self.make_full()
        self.replace_art("03-design.md", "| Z1 | 独立评审 | P1 | 空状态缺插图 | 已补 | 已修改 |", "| Z1 | 独立评审 | P1 | 空状态缺插图 | | 待修改 |")
        self.assert_blocked(self.run_check(), "设计稿自检问题未处理完：Z1=待修改")

    def test_design_selfcheck_not_fixed_needs_reason(self):
        self.make_full()
        self.replace_art("03-design.md", "| Z1 | 独立评审 | P1 | 空状态缺插图 | 已补 | 已修改 |", "| Z1 | 独立评审 | P1 | 空状态缺插图 | | 不改 |")
        self.assert_blocked(self.run_check(), "设计稿自检问题没有写处理：Z1")

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

    def test_interaction_fields_must_be_filled(self):
        for row in (
            "| I1 | P1 | <待填写> | loading 后提示已受理 |",
            "| I1 | P1 | 点击受理 | |",
        ):
            with self.subTest(row=row):
                self.make_full()
                self.replace_art("03-design.md", "| I1 | P1 | 点击受理 | loading 后提示已受理 |", row)
                self.assert_blocked(self.run_check(), "交互标注缺少")

    def test_checkpoint_cannot_invent_interaction(self):
        self.make_full()
        self.replace_art("03-design.md", "I1 按标注实现", "I1、I99 按标注实现")
        self.assert_blocked(self.run_check(), "走查点引用了未定义的交互标注：W2 → I99")

    def test_checkpoint_cannot_cover_another_pages_interaction(self):
        self.make_full()
        self.truncate(3)
        self.write_af("design/P2.html", "<html></html>")
        self.replace_art("03-design.md", "| P1 | 列表页 | design/P1.html |",
                         "| P1 | 列表页 | design/P1.html |\n| P2 | 详情页 | design/P2.html |")
        self.replace_art("03-design.md", "| W2 | P1 | 交互 | I1 按标注实现 | 是 |",
                         "| W2 | P2 | 交互 | I1 按标注实现 | 是 |")
        self.assert_blocked(self.run_check(), "走查点与交互标注页面不一致：W2(P2) → I1(P1)")

    def test_interaction_checkpoint_must_be_key(self):
        self.make_full()
        self.replace_art("03-design.md", "| W2 | P1 | 交互 | I1 按标注实现 | 是 |",
                         "| W2 | P1 | 交互 | I1 按标注实现 | 否 |")
        self.assert_blocked(self.run_check(), "交互走查点必须标为关键项：W2")

    def test_layout_checkpoint_is_required_for_every_page(self):
        self.make_full()
        self.replace_art("03-design.md", "| W10 | P1 | 版式 |", "| W10 | P1 | 间距 |")
        self.assert_blocked(self.run_check(), "页面没有通用版式走查点：P1")

    def test_layout_checkpoint_must_be_key(self):
        self.make_full()
        self.replace_art("03-design.md",
                         "| W10 | P1 | 版式 | layout-check.js 和 spec-check.js 输出为空 | 是 |",
                         "| W10 | P1 | 版式 | layout-check.js 和 spec-check.js 输出为空 | 否 |")
        self.assert_blocked(self.run_check(), "通用版式走查点必须标为关键项：W10")

    def test_second_page_cannot_reuse_first_pages_layout_checkpoint(self):
        self.make_full()
        self.truncate(3)
        self.write_af("design/P2.html", "<html></html>")
        self.replace_art("03-design.md", "| P1 | 列表页 | design/P1.html |",
                         "| P1 | 列表页 | design/P1.html |\n| P2 | 详情页 | design/P2.html |")
        self.replace_art("03-design.md", "| W1 | P1 | 页面 | 从主流程能到达本页 | 是 |",
                         "| W1 | P1 | 页面 | 从主流程能到达本页 | 是 |\n"
                         "| W11 | P2 | 页面 | 从列表页能到达本页 | 是 |")
        self.assert_blocked(self.run_check(), "页面没有通用版式走查点：P2")

    def test_valid_multipage_design_passes(self):
        self.make_full()
        self.truncate(3)
        self.confirm_design_images(("P1", "P2"))
        self.write_af("design/P2.html", "<html></html>")
        self.replace_art("03-design.md", "| P1 | 列表页 | design/P1.html |",
                         "| P1 | 列表页 | design/P1.html |\n| P2 | 详情页 | design/P2.html |")
        self.replace_art("03-design.md", "| W10 | P1 | 版式 | layout-check.js 和 spec-check.js 输出为空 | 是 |",
                         "| W10 | P1 | 版式 | layout-check.js 和 spec-check.js 输出为空 | 是 |\n"
                         "| W11 | P2 | 版式 | layout-check.js 和 spec-check.js 输出为空 | 是 |")
        self.replace_art("03-design.md", "| P1 | V1 | design/img/P1.png | 通过 | 无偏差 |",
                         "| P1 | V1 | design/img/P1.png | 通过 | 无偏差 |\n| P2 | V2 | design/img/P2.png | 通过 | 已核对间距与状态 |")
        self.assert_pass(self.run_check())

    def test_designer_must_differ_from_developer(self):
        self.make_full()
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"developer": "agent:dev", "designer": "agent:dev", "tester": "agent:test"}
        self.assert_blocked(self.run_check(), "designer 与 developer 必须是独立身份")

    def test_image_pending_waits_without_html_or_reviewer_demands(self):
        self.make_full()
        self.truncate(3)
        self.state["mode"] = 2
        self.state["agent_sessions"] = {"designer": "agent:ux"}
        self.state["design_image_status"] = "pending"
        self.state["design_image_fingerprint"] = ""
        self.state["signoffs"]["design"] = "confirmed"
        self.state["artifacts"].remove("03-design.md")
        (self.arts / "03-design.md").unlink()
        (self.af / "design-images.md").unlink()
        dump_state(self.af / "state.yaml", self.state)
        before = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        result = self.run_check()
        self.assert_blocked(result, "先生成图片并请用户确认")
        for message in ("缺少必需产物", "03-design.md", "设计稿自检", "design_reviewer", "stage_dispatch", "signoffs.design"):
            self.assertNotIn(message, result.stdout)
        after = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_stage3_cannot_use_legacy_fields_to_skip_image_review(self):
        self.make_full()
        self.truncate(3)
        for status in (None, "skipped", "done", True):
            with self.subTest(status=status):
                self.state["design_image_status"] = status
                self.assert_blocked(self.run_check(), "design_image_status 必须为 confirmed")
        self.state.pop("design_image_status")
        self.state.pop("design_image_fingerprint")
        self.assert_blocked(self.run_check(), "design_image_status 必须为 confirmed")

    def test_confirmed_image_requires_provenance_and_valid_local_raster(self):
        for issue in ("no-source", "screenshot-source", "missing-file", "invalid-image", "outside-path", "no-manifest"):
            with self.subTest(issue=issue):
                self.make_full()
                self.truncate(3)
                path = self.af / "design-images.md"
                body = path.read_text(encoding="utf-8")
                if issue == "no-source":
                    path.write_text(body.replace("test-only-imagegen-call-1", ""), encoding="utf-8")
                    message = "缺少图像工具调用证据"
                elif issue == "screenshot-source":
                    path.write_text(body.replace("图像生成", "HTML截图"), encoding="utf-8")
                    message = "不能用 HTML 截图"
                elif issue == "missing-file":
                    (self.af / "design-images/P1.png").unlink()
                    message = "已存在的图片文件"
                elif issue == "invalid-image":
                    (self.af / "design-images/P1.png").write_bytes(b"not a raster")
                    message = "不是有效的非空"
                elif issue == "outside-path":
                    (self.root / "outside.png").write_bytes(png_bytes((1, 2, 3)))
                    path.write_text(body.replace("design-images/P1.png", "../outside.png"), encoding="utf-8")
                    message = ".aiflow 内已存在"
                else:
                    path.unlink()
                    message = "缺少设计图片清单"
                self.assert_blocked(self.run_check(), message)

    def test_image_confirmation_requires_user_quote_zoned_time_and_resolved_feedback(self):
        self.make_full()
        self.truncate(3)
        path = self.af / "design-images.md"
        original = path.read_text(encoding="utf-8")
        edits = (("用户原话：「确认，往下走」", "用户原话：", "缺少真实用户原话"),
                 ("2026-11-01T10:00:00+08:00", "2026-11-01", "含时区"),
                 ("2026-11-01T10:00:00+08:00", "2026-02-30T10:00:00+08:00", "含时区"),
                 ("确认结论：已确认", "确认结论：待确认", "尚未取得唯一明确"),
                 ("| 已处理 |", "| 待修改 |", "评审意见未处理完"))
        for old, new, message in edits:
            with self.subTest(new=new):
                path.write_text(original.replace(old, new), encoding="utf-8")
                self.assert_blocked(self.run_check(), message)
        path.write_text(original, encoding="utf-8")
        self.assert_pass(self.run_check())

    def test_image_manifest_rejects_duplicate_ids_and_invalid_coverage(self):
        self.make_full()
        self.truncate(3)
        path = self.af / "design-images.md"
        original = path.read_text(encoding="utf-8")
        row = "| V1 | P1 | design-images/P1.png | 图像生成 | test-only-imagegen-call-1 |"
        for replacement, message in ((row + "\n" + row, "重复设计图片编号"),
                                     (row.replace("| P1 |", "| 首页 |"), "覆盖页面必须列出 P 编号"),
                                     (row.replace("| V1 |", "| first |"), "图片编号必须为 V")):
            with self.subTest(message=message):
                path.write_text(original.replace(row, replacement), encoding="utf-8")
                self.assert_blocked(self.run_check(), message)

    def test_image_replacement_invalidates_approval_even_at_same_filename(self):
        self.make_full()
        self.truncate(3)
        before = self.state["design_image_fingerprint"]
        (self.af / "design-images/P1.png").write_bytes(png_bytes((200, 12, 40)))
        after = self.image_fingerprint_command()
        self.assertEqual(after.returncode, 0, after.stdout)
        self.assertNotEqual(after.stdout.strip(), before)
        self.assert_blocked(self.run_check(), "设计图片确认指纹与当前图片不一致")

    def test_image_fingerprint_binds_manifest_and_ignores_review_text(self):
        self.make_full()
        path = self.af / "design-images.md"
        original = path.read_text(encoding="utf-8")
        baseline = self.image_fingerprint_command().stdout.strip()
        path.write_text(original.replace("示例反馈", "另一条反馈"), encoding="utf-8")
        self.assertEqual(self.image_fingerprint_command().stdout.strip(), baseline)
        path.write_text(original.replace("| P1 |", "| P1 / P2 |"), encoding="utf-8")
        self.assertNotEqual(self.image_fingerprint_command().stdout.strip(), baseline)

    def test_design_image_fingerprint_command_is_read_only_and_does_not_confirm(self):
        self.write_design_images()
        path = self.af / "design-images.md"
        path.write_text(path.read_text(encoding="utf-8").split("## 评审记录", 1)[0], encoding="utf-8")
        before = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        result = self.image_fingerprint_command()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertRegex(result.stdout.strip(), r"^[0-9a-f]{64}$")
        after = {p.relative_to(self.af): p.read_bytes() for p in self.af.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.af / "state.yaml").exists())

    def test_approved_images_unlock_normal_html_and_user_confirmation_gates(self):
        self.make_full()
        self.truncate(3)
        (self.arts / "03-design.md").unlink()
        self.state["artifacts"].remove("03-design.md")
        self.assert_blocked(self.run_check(), "缺少必需产物：03-design.md")
        self.write_art("03-design.md", DESIGN)
        self.state["artifacts"].append("03-design.md")
        self.state["signoffs"]["design"] = "pending"
        self.assert_blocked(self.run_check(), "设计稿 未经用户确认")
        self.state["signoffs"]["design"] = "confirmed"
        self.assert_pass(self.run_check())

    def test_html_image_comparison_requires_coverage_result_and_evidence(self):
        self.make_full()
        self.truncate(3)
        row = "| P1 | V1 | design/img/P1.png | 通过 | 无偏差 |"
        original = (self.arts / "03-design.md").read_text(encoding="utf-8")
        for replacement, message in (("", "缺少图片还原核对"),
                                     (row.replace("| V1 |", "| V9 |"), "基准图未覆盖页面"),
                                     (row.replace("| 通过 |", "| 待核对 |"), "图片还原核对尚未通过"),
                                     (row.replace("无偏差", ""), "缺少差异与处理"),
                                     (row.replace("design/img/P1.png", "design/img/missing.png"), "已存在的图片文件")):
            with self.subTest(message=message):
                self.write_art("03-design.md", original.replace(row, replacement))
                self.assert_blocked(self.run_check(), message)
        self.write_art("03-design.md", original)
        self.assert_pass(self.run_check())

    def test_modern_design_requires_real_nonempty_html_artifact(self):
        self.make_full()
        self.truncate(3)
        original = (self.arts / "03-design.md").read_text(encoding="utf-8")
        (self.af / "design/empty.html").write_text("  \n", encoding="utf-8")
        for target in ("design-images/P1.png", "design", "design/empty.html"):
            with self.subTest(target=target):
                self.write_art("03-design.md", original.replace("design/P1.html", target))
                self.assert_blocked(self.run_check(), "必须是项目内非空 HTML 文件")
        self.write_art("03-design.md", original)
        self.assert_pass(self.run_check())

    def test_html_screenshot_cannot_be_the_approved_baseline(self):
        self.make_full()
        self.truncate(3)
        self.replace_art("03-design.md", "design/img/P1.png", "design-images/P1.png")
        self.assert_blocked(self.run_check(), "不能复用基准图")
        self.replace_art("03-design.md", "design-images/P1.png", "design/img/P1.png")
        (self.af / "design/img/P1.png").write_bytes((self.af / "design-images/P1.png").read_bytes())
        self.assert_blocked(self.run_check(), "相同图片内容")

    def test_html_comparison_allows_viewports_and_blocks_any_failed_viewport(self):
        self.make_full()
        self.truncate(3)
        (self.af / "design/img/P1-mobile.png").write_bytes(png_bytes((230, 70, 50)))
        desktop = "| P1 | V1 | design/img/P1.png | 通过 | 无偏差 |"
        mobile = "| P1 | V1 | design/img/P1-mobile.png | 通过 | 手机布局已核对 |"
        self.replace_art("03-design.md", desktop, desktop + "\n" + mobile)
        self.assert_pass(self.run_check())
        self.replace_art("03-design.md", mobile, mobile.replace("| 通过 |", "| 不通过 |"))
        self.assert_blocked(self.run_check(), "图片还原核对尚未通过：P1")

    def test_html_comparison_cannot_duplicate_screenshot_as_another_viewport(self):
        self.make_full()
        self.truncate(3)
        row = "| P1 | V1 | design/img/P1.png | 通过 | 无偏差 |"
        self.replace_art("03-design.md", row, row + "\n" + row.replace("无偏差", "手机视口已核对"))
        self.assert_blocked(self.run_check(), "重复使用同一页面的 HTML 截图")

    def test_approved_images_must_cover_known_prototype_pages_before_html(self):
        self.make_full()
        self.truncate(3)
        self.replace_art("02-prototype.md", "| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |",
                         "| P1 | 列表页 | 查看与操作 | A1、A2 | prototype/P1.html |\n| P2 | 详情页 | 查看详情 | A1 | prototype/P1.html |")
        result = self.run_check()
        self.assert_blocked(result, "已确认设计图片未覆盖原型页面：P2")
        self.assertNotIn("设计稿未覆盖原型页面", result.stdout)

    def test_no_design_requires_skipped_image_status_for_new_records(self):
        self.make_full(design=False)
        self.truncate(2)
        self.state["design_image_status"] = "pending"
        self.assert_blocked(self.run_check(), "design_image_status 必须为 skipped")
        self.state["design_image_status"] = "skipped"
        self.assert_pass(self.run_check())

    def test_legacy_completed_html_projects_do_not_invent_image_approval(self):
        for design in (True, False):
            with self.subTest(design=design):
                if not design:
                    for name in DESIGN_NAMES:
                        (self.arts / name).unlink(missing_ok=True)
                self.make_full(design=design)
                self.state.pop("design_image_status")
                self.state.pop("design_image_fingerprint")
                if design:
                    (self.af / "design-images.md").unlink()
                    self.replace_art("03-design.md", IMAGE_COMPARISON, "")
                self.assert_pass(self.run_check())

    def test_closed_fe_bug_requires_design_recheck(self):
        self.make_full()
        self.write_bug([(1, "E2", "A2", "通过", "retest-log-1")], task="T2", owner="FE", standard="A2",
                       extra="- 待验点：W3\n")
        self.assert_blocked(self.run_check(), "回归缺少通过的「设计还原复核」")
        self.replace_art("10-regression.md", "## 四、结论\n", "## 四、设计还原复核\n- 复核结论：通过\n\n## 五、结论\n")
        self.assert_pass(self.run_check())

    def test_fe_bug_without_walkthrough_points_does_not_require_design_recheck(self):
        for conclusion in ("", "不适用", "通过"):
            with self.subTest(conclusion=conclusion):
                self.make_full()
                self.write_bug([(1, "E2", "A2", "通过", "retest-log-1")], task="T2", owner="FE", standard="A2",
                               extra="- 待验点：校验逻辑\n")
                if conclusion:
                    self.replace_art("10-regression.md", "## 四、结论\n",
                                     "## 四、设计还原复核\n- 复核结论：%s\n\n## 五、结论\n" % conclusion)
                self.assert_pass(self.run_check())
        self.replace_art("10-regression.md", "- 复核结论：通过\n", "- 复核结论：不通过\n")
        self.assert_blocked(self.run_check(), "回归的「设计还原复核」结论为不通过")

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
