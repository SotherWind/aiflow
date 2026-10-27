#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aiflow 漂移与交付门禁检查（仅使用 Python 标准库）。

用法：python check.py <项目目录>
退出码：0 通过 / 1 有阻塞项 / 2 只有警告。阶段收尾只接受 0。
"""
import json
import re
import sys
from pathlib import Path

BLOCK, WARN = [], []
PHASE_ARTIFACTS = {
    0: ["00-intake.md"],
    1: ["01-research.md"],
    2: ["02-prd.md"],
    3: ["03-arch.md", "03-mapping.md"],
    4: ["04-tasks.md"],
    5: ["05-dev-log.md"],
    6: ["06-test-report.md"],
    7: ["07-bugs.md"],
    8: ["08-regression.md"],
    9: ["09-release.md"],
}
OPEN_BUG_STATUSES = {"待修复", "待复测", "打回"}
REGRESSION_MAP = {"通过": "pass", "有条件通过": "conditional", "不通过": "fail"}
RELEASE_MAP = {"计划中": "planned", "已发布待观察": "deployed", "观察完成": "verified", "已回滚": "rolled_back"}


def block(message):
    BLOCK.append(message)


def warn(message):
    WARN.append(message)


def rd(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        block("无法读取 %s：%s" % (path, exc))
        return ""


def clean_md(value):
    return str(value).replace("**", "").replace("`", "").strip()


def strip_comment(raw):
    quote = None
    for index, char in enumerate(raw):
        if char in ("\"", "'"):
            if quote is None:
                quote = char
            elif quote == char:
                if char == "\"" and index > 0 and raw[index - 1] == "\\":
                    continue
                quote = None
        elif char == "#" and quote is None and (index == 0 or raw[index - 1].isspace()):
            return raw[:index].rstrip()
    return raw.rstrip()


def split_inline(value):
    parts, current, quote = [], [], None
    for char in value:
        if char in ("\"", "'"):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        if char == "," and quote is None:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def scalar(value):
    value = value.strip()
    if value == "":
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [scalar(part) for part in split_inline(inner)]
    if value == "{}":
        return {}
    if len(value) >= 2 and value[0] == value[-1] == "\"":
        return json.loads(value)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_state(text):
    """解析本 skill 使用的 YAML 子集：顶层标量、列表和一层字典。"""
    lines = []
    for raw in text.splitlines():
        if "\t" in raw[:len(raw) - len(raw.lstrip())]:
            raise ValueError("state.yaml 缩进不能使用 Tab")
        cleaned = strip_comment(raw)
        if not cleaned.strip() or cleaned.lstrip().startswith("#") or cleaned.strip() == "---":
            continue
        indent = len(cleaned) - len(cleaned.lstrip())
        lines.append((indent, cleaned.strip()))
    result = {}
    index = 0
    while index < len(lines):
        indent, content = lines[index]
        if indent != 0:
            raise ValueError("state.yaml 出现意外的顶层缩进：%s" % content)
        match = re.fullmatch(r"([A-Za-z_][\w-]*):\s*(.*)", content)
        if not match:
            raise ValueError("无法解析 state.yaml 行：%s" % content)
        key, raw_value = match.groups()
        if key in result:
            raise ValueError("state.yaml 字段重复：%s" % key)
        if raw_value:
            result[key] = scalar(raw_value)
            index += 1
            continue
        children = []
        cursor = index + 1
        while cursor < len(lines) and lines[cursor][0] > 0:
            children.append(lines[cursor][1])
            cursor += 1
        if not children:
            result[key] = ""
        elif all(re.match(r"^-\s+", child) for child in children):
            result[key] = [scalar(re.sub(r"^-\s+", "", child)) for child in children]
        else:
            mapping = {}
            for child in children:
                child_match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(.*)", child)
                if not child_match:
                    raise ValueError("只支持一层列表或字典：%s" % child)
                child_key, child_value = child_match.groups()
                if child_key in mapping:
                    raise ValueError("state.yaml 子字段重复：%s.%s" % (key, child_key))
                mapping[child_key] = scalar(child_value)
            result[key] = mapping
        index = cursor
    return result


def required_list(state, key):
    if key not in state:
        block("state.yaml 缺少字段：%s" % key)
        return []
    value = state[key]
    if not isinstance(value, list):
        block("state.yaml.%s 必须是列表" % key)
        return []
    return [str(item) for item in value]


def required_dict(state, key):
    if key not in state:
        block("state.yaml 缺少字段：%s" % key)
        return {}
    value = state[key]
    if not isinstance(value, dict):
        block("state.yaml.%s 必须是字典" % key)
        return {}
    return value


def required_artifacts(stage):
    result = []
    for number in range(stage + 1):
        result.extend(PHASE_ARTIFACTS[number])
    return result


def section(text, heading_keyword):
    headings = list(re.finditer(r"^##\s+.*$", text, re.M))
    for index, heading in enumerate(headings):
        if heading_keyword in heading.group(0):
            start = heading.end()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            return text[start:end]
    return ""


def numbered_section(text, number):
    headings = list(re.finditer(r"^##\s+.*$", text, re.M))
    for index, heading in enumerate(headings):
        title = heading.group(0)
        if re.match(r"^##\s+%s(?:\s|$)" % number, title):
            start = heading.end()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            return text[start:end]
    return ""


def cells(line):
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [clean_md(cell) for cell in stripped.strip("|").split("|")]


def first_table(text):
    groups, current = [], []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        return [], []
    group = groups[0]
    if len(group) < 2:
        return cells(group[0]), []
    header = cells(group[0])
    rows = []
    for line in group[1:]:
        row = cells(line)
        if row and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in row):
            continue
        rows.append(row)
    return header, rows


def row_dict(header, row):
    return {header[index]: row[index] if index < len(row) else "" for index in range(len(header))}


def ids_in(text, prefix):
    found = set(re.findall(r"(?<![A-Za-z0-9])%s\d+(?![A-Za-z0-9])" % prefix, text))
    range_pattern = r"(?<![A-Za-z0-9])%s(\d+)\s*[–—-]\s*(?:%s)?(\d+)(?![A-Za-z0-9])" % (prefix, prefix)
    for start, end in re.findall(range_pattern, text):
        first, last = int(start), int(end)
        if first <= last and last - first <= 100:
            found.update("%s%d" % (prefix, number) for number in range(first, last + 1))
    return found


def bug_ids_in(text):
    return set(re.findall(r"(?<![A-Za-z0-9])BUG-\d+(?![A-Za-z0-9])", text))


def sort_ids(values):
    def key(value):
        match = re.search(r"(\d+)$", value)
        return (re.sub(r"\d+$", "", value), int(match.group(1)) if match else 0)
    return sorted(values, key=key)


def definitions(facts, number, prefix):
    body = numbered_section(facts, number)
    if not body:
        block("facts.md 缺少 %s 章节" % number)
        return set(), set(), []
    header, rows = first_table(body)
    active, retired, active_rows = set(), set(), []
    for row in rows:
        if not row:
            continue
        data = row_dict(header, row)
        first = row[0].replace(" ", "")
        match = re.fullmatch(r"(~~)?(%s\d+)(~~)?" % prefix, first)
        if not match:
            continue
        identifier = match.group(2)
        data["_identifier"] = identifier
        if match.group(1) or match.group(3) or "~~" in "".join(row):
            retired.add(identifier)
        else:
            if identifier in active:
                block("facts.md 重复定义：%s" % identifier)
            active.add(identifier)
            active_rows.append(data)
    for identifier in sorted(active & retired):
        block("facts.md 同一编号同时存在有效与作废定义：%s" % identifier)
    return active, active | retired, active_rows


def detail_section(text, identifier):
    pattern = re.compile(r"^###\s+%s(?=\s|$|·)" % re.escape(identifier), re.M)
    match = pattern.search(text)
    if not match:
        return ""
    next_heading = re.search(r"^###\s+", text[match.end():], re.M)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start():end]


def valid_closed_retest(text):
    for line in text.splitlines():
        normalized = clean_md(line).strip()
        if re.search(r"结论\s*[:：]\s*通过(?:\s*→\s*已关闭)?\s*$", normalized):
            return True
    return False


def regression_conclusion(text):
    body = section(text, "结论")
    conclusions = []
    for line in body.splitlines():
        normalized = clean_md(line)
        match = re.fullmatch(r"(?:结论|回归结论)\s*[:：]\s*(有条件通过|不通过|通过)\s*", normalized)
        if match:
            conclusions.append(match.group(1))
    if len(conclusions) != 1:
        block("08-regression.md 的结论章节必须有且只有一条可解析结论，实际为 %d 条" % len(conclusions))
        return None
    return conclusions[0]


def release_field(text, name):
    for line in text.splitlines():
        normalized = clean_md(line).lstrip("- ").strip()
        match = re.match(r"%s\s*[:：]\s*(.*?)\s*$" % re.escape(name), normalized)
        if match:
            return match.group(1).strip()
    return ""


def missing_value(value):
    return not value or value in ("……", "...", "—") or (value.startswith("<") and value.endswith(">"))


def version_declaration(text, label, pattern):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        block("%s 必须有且只有一条版本声明，实际为 %d 条" % (label, len(matches)))
        return None
    match = matches[0]
    line_number = text[:match.start()].count("\n") + 1
    if line_number > 10:
        block("%s 的版本声明必须位于文件头部" % label)
        return None
    return int(match.group(1))


def finish(root, stage):
    print("\n" + "=" * 56)
    print("项目：%s　当前阶段：%s" % (root.name, stage))
    if BLOCK:
        print("阻塞项 %d 条：" % len(BLOCK))
        for item in BLOCK:
            print("  ✗ %s" % item)
    if WARN:
        print("警告 %d 条：" % len(WARN))
        for item in WARN:
            print("  ! %s" % item)
    if not BLOCK and not WARN:
        print("全部通过，未发现漂移。")
    elif not BLOCK:
        print("无阻塞项，但阶段收尾仍须先清除警告。")
    print("=" * 56)
    return 1 if BLOCK else (2 if WARN else 0)


def main():
    BLOCK.clear()
    WARN.clear()
    if len(sys.argv) != 2:
        print("用法：python check.py <项目目录>")
        return 1
    root = Path(sys.argv[1]).resolve()
    af = root / ".aiflow"
    state_path = af / "state.yaml"
    if not state_path.exists():
        block("找不到 %s；先按 templates/state.yaml 初始化" % state_path)
        return finish(root, 0)
    try:
        state = parse_state(rd(state_path))
    except (ValueError, json.JSONDecodeError) as exc:
        block(str(exc))
        return finish(root, 0)

    stage_value = state.get("stage")
    if not isinstance(stage_value, int) or isinstance(stage_value, bool) or not 0 <= stage_value <= 9:
        block("state.yaml.stage 必须是 0–9 的整数")
        return finish(root, 0)
    stage = stage_value
    if not str(state.get("project", "")).strip():
        block("state.yaml.project 不能为空")
    if "facts_version" not in state or not isinstance(state["facts_version"], int) or isinstance(state["facts_version"], bool):
        block("state.yaml.facts_version 缺失或不是整数")
        state_version = None
    else:
        state_version = state["facts_version"]
    mode = state.get("mode")
    if mode not in (1, 2, 3):
        block("state.yaml.mode 必须为 1 / 2 / 3")
    if mode in (2, 3) and stage >= 5:
        sessions = required_dict(state, "agent_sessions")
        if missing_value(str(sessions.get("developer") or "")):
            block("模式 %d 缺少 agent_sessions.developer" % mode)
        developer = str(sessions.get("developer") or "").strip()
        if stage >= 6:
            tester = str(sessions.get("tester") or "").strip()
            if missing_value(tester):
                block("模式 %d 缺少 agent_sessions.tester" % mode)
            elif developer == tester:
                block("模式 %d 的 developer 与 tester 必须是独立身份" % mode)
        if mode == 3 and stage >= 8:
            reviewer = str(sessions.get("final_reviewer") or "").strip()
            if not re.match(r"^(human|model):\S+", reviewer):
                block("模式 3 缺少独立终验 agent_sessions.final_reviewer（须为 human:<姓名> 或 model:<名称>）")
            elif reviewer in (developer, str(sessions.get("tester") or "").strip()):
                block("模式 3 的 final_reviewer 必须独立于开发和测试")
            if state.get("final_review_result") != "pass":
                block("模式 3 的独立终验尚未通过")
            if missing_value(str(state.get("final_review_evidence") or "")):
                block("模式 3 缺少 final_review_evidence")

    listed = required_list(state, "artifacts")
    open_bugs = set(required_list(state, "open_bugs"))
    pending_decisions = required_list(state, "pending_decisions")
    if len(listed) != len(set(listed)):
        block("state.yaml.artifacts 有重复登记")
    for name in listed:
        if name != Path(name).name or not name.endswith(".md"):
            block("state.yaml.artifacts 含非法文件名：%s" % name)

    art_dir = af / "artifacts"
    paths = sorted(art_dir.glob("*.md")) if art_dir.exists() else []
    texts = {path.name: rd(path) for path in paths}
    actual = set(texts)
    required = required_artifacts(stage)
    for name in sorted(set(listed) - actual):
        block("state.yaml 登记了不存在的产物：%s" % name)
    for name in sorted(actual - set(listed)):
        block("产物存在但未登记进 state.yaml：%s" % name)
    for name in required:
        if name not in actual:
            block("阶段 %d 缺少必需产物：%s" % (stage, name))
        elif not texts[name].strip():
            block("必需产物为空：%s" % name)
    for name in actual:
        match = re.match(r"^(\d{2})-", name)
        if match and int(match.group(1)) > stage and not (stage == 6 and name == "07-bugs.md"):
            warn("存在晚于当前阶段的产物，回退后应作废或移出当前集：%s" % name)

    facts_path = af / "facts.md"
    facts = ""
    facts_version = 0
    ids_r = ids_a = all_r = all_a = set()
    if not facts_path.exists():
        if stage >= 1:
            block("阶段 %d 缺少 facts.md" % stage)
            return finish(root, stage)
    else:
        facts = rd(facts_path)
        declared_version = version_declaration(facts, "facts.md", r"版本\s*[:：]\s*v(\d+)")
        if declared_version is None:
            return finish(root, stage)
        facts_version = declared_version
        if stage >= 1 and facts_version < 1:
            block("阶段 1 起 facts 版本必须至少为 v1")
        if stage >= 1:
            ids_r, all_r, rule_rows = definitions(facts, "02", "R")
            ids_a, all_a, acceptance_rows = definitions(facts, "04", "A")
            if not ids_r:
                block("facts.md 没有当前有效 R 定义")
            if stage >= 2 and not ids_a:
                block("facts.md 没有当前有效 A 定义")
            if stage >= 2:
                for row in rule_rows:
                    if clean_md(row.get("来源", "")) != "已确认":
                        block("业务规则尚未确认，不得进入后续阶段：%s" % row["_identifier"])
                for row in acceptance_rows:
                    testable = row.get("能否写出失败用例")
                    if testable is not None and clean_md(testable) != "能":
                        block("验收标准缺少可失败用例：%s" % row["_identifier"])
            for row in acceptance_rows:
                identifier = row["_identifier"]
                refs = ids_in(row.get("依据规则", row.get("规则", "")), "R")
                if not refs:
                    block("验收标准未引用业务规则：%s" % identifier)
                elif not refs <= ids_r:
                    block("验收标准引用了失效或不存在的 R：%s → %s" % (identifier, ", ".join(sort_ids(refs - ids_r))))
    if state_version is not None and state_version != facts_version:
        block("facts 版本 v%d 与 state.facts_version %s 不一致" % (facts_version, state_version))
    if stage == 0 and facts_version != 0 and not facts:
        facts_version = 0

    if "00-intake.md" in required:
        intake_version = version_declaration(texts.get("00-intake.md", ""), "00-intake.md", r"依据 facts v(\d+)")
        if intake_version is not None and intake_version != 0:
            block("00-intake.md 必须基于 facts v0")
    for name in required:
        if name.startswith("00-"):
            continue
        artifact_version = version_declaration(texts.get(name, ""), name, r"依据 facts v(\d+)")
        if artifact_version is not None and artifact_version != facts_version:
            block("产物版本过期：%s 基于 v%d，当前为 v%d" % (name, artifact_version, facts_version))

    for name in required:
        if name < "02-prd.md":
            continue
        text = texts.get(name, "")
        for identifier in ids_in(text, "R") - all_r:
            block("产物引用了从未定义的编号：%s → %s" % (name, identifier))
        for identifier in ids_in(text, "A") - all_a:
            block("产物引用了从未定义的编号：%s → %s" % (name, identifier))

    task_ids = set()
    mapping_rows = {}
    if stage >= 3 and "03-mapping.md" in actual:
        mapping = texts["03-mapping.md"]
        main_section = section(mapping, "映射表")
        header, rows = first_table(main_section)
        for row in rows:
            data = row_dict(header, row)
            identifier = data.get("验收标准", row[0] if row else "")
            if re.fullmatch(r"A\d+", identifier):
                if identifier in mapping_rows:
                    block("03-mapping.md 重复映射：%s" % identifier)
                    continue
                mapping_rows[identifier] = (header, row)
                for column in ("落在哪", "由哪条约束保证"):
                    if missing_value(data.get(column, "")):
                        block("映射项缺少%s：%s" % (column, identifier))
                if stage == 3 and ids_in(" ".join(row), "T"):
                    block("阶段 3 不得预填尚未产生的 T 编号：%s" % identifier)
                if stage < 6 and ids_in(" ".join(row), "E"):
                    block("阶段 6 前不得预填尚未产生的 E 编号：%s" % identifier)
        for identifier in sorted(ids_a - set(mapping_rows)):
            block("03-mapping.md 主映射表缺少：%s" % identifier)
        unresolved = section(mapping, "无对应项")
        for identifier in sorted(ids_a & ids_in(unresolved, "A")):
            block("映射表仍有「无对应」：%s" % identifier)
        contract = numbered_section(facts, "05")
        contract_header, contract_rows = first_table(contract)
        contract_map = {}
        for row in contract_rows:
            data = row_dict(contract_header, row)
            identifier = data.get("验收标准", row[0] if row else "")
            if re.fullmatch(r"A\d+", identifier):
                if identifier in contract_map:
                    block("facts 05 重复契约映射：%s" % identifier)
                    continue
                contract_map[identifier] = data
        for identifier in sorted(ids_a - set(contract_map)):
            block("facts 05 契约映射缺少：%s" % identifier)
        for identifier in sorted(ids_a & set(contract_map)):
            data = contract_map[identifier]
            for column in ("落点类型", "落点"):
                if missing_value(data.get(column, "")):
                    block("facts 05 契约映射缺少%s：%s" % (column, identifier))

    if stage >= 4 and "04-tasks.md" in actual:
        tasks_text = texts["04-tasks.md"]
        header, rows = first_table(section(tasks_text, "任务总览"))
        dependencies = {}
        for row in rows:
            data = row_dict(header, row)
            identifier = data.get("编号", row[0] if row else "")
            if not re.fullmatch(r"T\d+", identifier):
                continue
            if identifier in task_ids:
                block("任务编号重复：%s" % identifier)
                continue
            task_ids.add(identifier)
            task_type = data.get("类型", "")
            if task_type not in ("FE", "BE", "JOB"):
                block("任务类型必须是 FE/BE/JOB：%s" % identifier)
            dependencies[identifier] = ids_in(data.get("依赖", ""), "T")
            if identifier in dependencies[identifier]:
                block("任务不能依赖自身：%s" % identifier)
        if not task_ids:
            block("04-tasks.md 没有有效任务")
        task_acceptance = {}
        for identifier in sorted(task_ids):
            details = detail_section(tasks_text, identifier)
            if not details:
                block("任务缺少详情：%s" % identifier)
                task_acceptance[identifier] = set()
                continue
            task_acceptance[identifier] = ids_in(details, "A")
            if not task_acceptance[identifier]:
                block("任务详情缺少验收标准：%s" % identifier)
        for identifier, refs in dependencies.items():
            for dependency in refs - task_ids:
                block("任务依赖了不存在的编号：%s → %s" % (identifier, dependency))
        covered_by_details = set().union(*task_acceptance.values()) if task_acceptance else set()
        for identifier in sorted(ids_a - covered_by_details):
            block("04-tasks.md 任务详情未覆盖验收标准：%s" % identifier)

        visiting, visited = set(), set()
        cycle_found = False
        def visit_task(identifier):
            nonlocal cycle_found
            if identifier in visiting:
                if not cycle_found:
                    block("任务依赖存在循环")
                    cycle_found = True
                return
            if identifier in visited:
                return
            visiting.add(identifier)
            for dependency in dependencies.get(identifier, set()) & task_ids:
                visit_task(dependency)
            visiting.remove(identifier)
            visited.add(identifier)
        for identifier in sorted(task_ids):
            visit_task(identifier)

        for identifier, (map_header, map_row) in mapping_rows.items():
            row_text = " ".join(map_row)
            refs = ids_in(row_text, "T")
            if not refs:
                block("阶段 4 未在映射表回填任务：%s" % identifier)
                continue
            if not refs <= task_ids:
                block("映射表引用了不存在的任务：%s → %s" % (identifier, ", ".join(sort_ids(refs - task_ids))))
            for task_id in refs & task_ids:
                if identifier not in task_acceptance.get(task_id, set()):
                    block("映射与任务详情的 A↔T 不一致：%s → %s" % (identifier, task_id))
        for task_id, standards in task_acceptance.items():
            for identifier in standards & ids_a:
                if identifier in mapping_rows and task_id not in ids_in(" ".join(mapping_rows[identifier][1]), "T"):
                    block("任务详情未在映射表对回原任务：%s → %s" % (identifier, task_id))

    if stage >= 5 and "05-dev-log.md" in actual:
        task_status = required_dict(state, "task_status")
        status_keys = set(task_status)
        for identifier in sorted(task_ids - status_keys):
            block("state.task_status 缺少：%s" % identifier)
        for identifier in sorted(status_keys - task_ids):
            block("state.task_status 含未知任务：%s" % identifier)
        for identifier, value in task_status.items():
            normalized = {"完成": "done", "部分完成": "partial", "未开始": "pending"}.get(str(value), str(value).lower())
            if normalized not in ("done", "partial", "pending"):
                block("未知任务状态：%s=%s" % (identifier, value))
            elif normalized != "done":
                block("任务未完成，不得完成阶段 5：%s=%s" % (identifier, value))
        header, rows = first_table(section(texts["05-dev-log.md"], "任务完成情况"))
        dev_status = {}
        for row in rows:
            data = row_dict(header, row)
            identifier = data.get("编号", data.get("任务", row[0] if row else ""))
            task_match = re.search(r"T\d+", identifier)
            if task_match:
                task_id = task_match.group(0)
                if task_id in dev_status:
                    block("05-dev-log.md 重复任务结论：%s" % task_id)
                    continue
                dev_status[task_id] = clean_md(data.get("状态", ""))
        for identifier in sorted(task_ids - set(dev_status)):
            block("05-dev-log.md 缺少任务结论：%s" % identifier)
        for identifier, value in dev_status.items():
            if identifier in task_ids and value != "完成":
                block("开发日志显示任务未完成：%s=%s" % (identifier, value))

    failed_tasks = set()
    acceptance_results = {}
    test_acceptance_results = {}
    test_e_ids = set()
    test_case_acceptance = {}
    if stage >= 6 and "06-test-report.md" in actual:
        test_text = texts["06-test-report.md"]
        header, rows = first_table(section(test_text, "按任务结论"))
        conclusions = {}
        for row in rows:
            data = row_dict(header, row)
            task_cell = data.get("任务", row[0] if row else "")
            match = re.search(r"T\d+", task_cell)
            if match:
                task_id = match.group(0)
                if task_id in conclusions:
                    block("06-test-report.md 重复任务结论：%s" % task_id)
                    continue
                conclusions[task_id] = clean_md(data.get("结论", ""))
        for identifier in sorted(task_ids - set(conclusions)):
            block("06-test-report.md 缺少任务结论：%s" % identifier)
        for identifier, conclusion in conclusions.items():
            if identifier not in task_ids:
                block("测试报告含未知任务：%s" % identifier)
            elif conclusion not in ("通过", "不通过", "部分通过"):
                block("任务没有有效测试结论：%s=%s" % (identifier, conclusion or "空"))
            elif conclusion != "通过":
                failed_tasks.add(identifier)

        coverage_section = section(test_text, "验收标准覆盖")
        header, rows = first_table(coverage_section)
        coverage_rows = {}
        for row in rows:
            data = row_dict(header, row)
            identifier = data.get("验收标准", row[0] if row else "")
            if re.fullmatch(r"A\d+", identifier):
                if identifier in coverage_rows:
                    block("06-test-report.md 重复验收覆盖行：%s" % identifier)
                    continue
                coverage_rows[identifier] = data
                case_refs = ids_in(data.get("对应用例", data.get("用例", "")), "E")
                test_e_ids.update(case_refs)
                for case_id in case_refs:
                    if case_id in test_case_acceptance and identifier not in test_case_acceptance[case_id]:
                        block("同一 E 用例绑定多个验收标准，需拆成独立用例：%s" % case_id)
                    test_case_acceptance.setdefault(case_id, set()).add(identifier)
                result = clean_md(data.get("结果", data.get("覆盖", "")))
                if not case_refs:
                    block("验收标准未绑定 E 用例：%s" % identifier)
                if result == "通过":
                    normalized_result = "pass"
                elif result in ("不通过", "失败", "部分通过"):
                    normalized_result = "fail"
                elif result in ("未覆盖", "否"):
                    normalized_result = "uncovered"
                else:
                    normalized_result = ""
                    block("验收标准测试结果无效：%s=%s" % (identifier, result or "空"))
                test_acceptance_results[identifier] = normalized_result
        for identifier in sorted(ids_a - set(coverage_rows)):
            block("06-test-report.md 未覆盖验收标准：%s" % identifier)

        acceptance_results = required_dict(state, "acceptance_results")
        acceptance_keys = set(acceptance_results)
        for identifier in sorted(ids_a - acceptance_keys):
            block("state.acceptance_results 缺少：%s" % identifier)
        for identifier in sorted(acceptance_keys - ids_a):
            block("state.acceptance_results 含未知或已作废标准：%s" % identifier)
        for identifier, value in acceptance_results.items():
            normalized = str(value).lower()
            if normalized not in ("pass", "fail", "uncovered"):
                block("未知验收执行状态：%s=%s" % (identifier, value))
                continue
            if normalized == "uncovered":
                block("验收标准未执行，不得放行：%s" % identifier)
            documented = test_acceptance_results.get(identifier)
            if documented and documented != normalized:
                block("测试报告与 state 的验收结果不一致：%s 文档=%s，state=%s" % (identifier, documented, normalized))
        for identifier, (map_header, map_row) in mapping_rows.items():
            refs = ids_in(" ".join(map_row), "E")
            if not refs:
                block("阶段 6 未在映射表回填用例：%s" % identifier)
            elif not refs <= test_e_ids:
                block("映射表引用了不存在的用例：%s → %s" % (identifier, ", ".join(sort_ids(refs - test_e_ids))))

    bugs_text = texts.get("07-bugs.md", "")
    bug_summary = {}
    bug_tasks = {}
    bug_acceptance = {}
    if bugs_text:
        header, rows = first_table(section(bugs_text, "汇总"))
        for row in rows:
            data = row_dict(header, row)
            identifier = data.get("编号", row[0] if row else "")
            if not re.fullmatch(r"BUG-\d+", identifier):
                continue
            if identifier in bug_summary:
                block("07-bugs.md 重复缺陷编号：%s" % identifier)
                continue
            status = clean_md(data.get("状态", ""))
            if status not in OPEN_BUG_STATUSES | {"已关闭"}:
                block("缺陷状态无效：%s=%s" % (identifier, status or "空"))
            bug_summary[identifier] = status
            bug_tasks[identifier] = ids_in(data.get("关联任务", ""), "T")
            details = detail_section(bugs_text, identifier)
            bug_acceptance[identifier] = ids_in(details, "A")
            if not details:
                block("缺陷缺少详情：%s" % identifier)
            elif status == "已关闭" and ("复测结论" not in details or not valid_closed_retest(details)):
                block("已关闭缺陷缺少通过复测结论：%s" % identifier)
    summary_open = {identifier for identifier, status in bug_summary.items() if status in OPEN_BUG_STATUSES}
    if open_bugs != summary_open:
        block("state.open_bugs 与 07-bugs.md 不一致：state=%s；缺陷单=%s" % (
            ", ".join(sorted(open_bugs)) or "空", ", ".join(sorted(summary_open)) or "空"))
    if open_bugs and not bugs_text:
        block("state 有未关闭缺陷，但缺少 07-bugs.md")
    for identifier in sorted(failed_tasks):
        if not any(identifier in bug_tasks.get(bug, set()) for bug in bug_summary):
            block("不通过任务没有关联缺陷单：%s" % identifier)
    bug_linked_acceptance = set().union(*bug_acceptance.values()) if bug_acceptance else set()
    for identifier, value in acceptance_results.items():
        if str(value).lower() == "fail" and identifier not in bug_linked_acceptance:
            block("失败验收标准没有在具体缺陷详情中关联：%s" % identifier)
    if stage >= 7:
        if open_bugs or summary_open:
            block("缺陷未清零，不得完成阶段 7：%s" % ", ".join(sorted(open_bugs | summary_open)))
        for identifier, status in bug_summary.items():
            if status != "已关闭":
                block("缺陷单不是已关闭状态：%s=%s" % (identifier, status))

    if stage >= 8 and "08-regression.md" in actual:
        if pending_decisions:
            block("进入回归前仍有待决策：%s" % ", ".join(pending_decisions))
        for identifier, value in acceptance_results.items():
            if str(value).lower() != "pass":
                block("回归完成时验收标准不是 pass：%s=%s" % (identifier, value))
        regression_text = texts["08-regression.md"]
        doc_result = regression_conclusion(regression_text)
        state_result = state.get("regression_result")
        conditions = required_list(state, "regression_conditions")
        confirmed = state.get("regression_user_confirmed")
        if not isinstance(confirmed, bool):
            block("state.regression_user_confirmed 必须是 true/false")
            confirmed = False
        if state_result not in ("pass", "conditional", "fail"):
            block("state.regression_result 缺失或无效")
        if doc_result and state_result in REGRESSION_MAP.values() and REGRESSION_MAP[doc_result] != state_result:
            block("回归结论与 state 不一致：文档=%s，state=%s" % (doc_result, state_result))
        if state_result == "fail" or doc_result == "不通过":
            block("回归不通过，不得上线")
        elif state_result == "conditional" or doc_result == "有条件通过":
            if not conditions:
                block("有条件通过但未记录条件")
            if not confirmed:
                block("有条件通过但未取得用户显式确认")
        elif state_result == "pass" and conditions:
            block("结论为通过时不应仍挂回归条件")
        execution = section(regression_text, "执行结果")
        header, rows = first_table(execution)
        regression_covered = set()
        for row in rows:
            data = row_dict(header, row)
            standards = ids_a & ids_in(" ".join(row), "A")
            if not standards:
                continue
            e_refs = ids_in(data.get("用例", ""), "E")
            result = clean_md(data.get("结果", ""))
            if not e_refs:
                block("回归执行行未绑定 E 用例：%s" % " / ".join(row[:2]))
            unknown_e = e_refs - test_e_ids
            if unknown_e:
                block("回归引用了阶段 6 未定义的用例：%s" % ", ".join(sort_ids(unknown_e)))
            for case_id in e_refs & test_e_ids:
                if not standards <= test_case_acceptance.get(case_id, set()):
                    block("回归用例与验收标准的关联不一致：%s → %s" % (case_id, ", ".join(sorted(standards))))
            if result != "通过":
                block("回归存在未通过的当前验收用例：%s" % " / ".join(row[:2]))
            valid_pairs = all(standards <= test_case_acceptance.get(case_id, set()) for case_id in e_refs)
            if e_refs and not unknown_e and valid_pairs and result == "通过":
                regression_covered.update(standards)
        for identifier in sorted(ids_a - regression_covered):
            block("全量回归未以有效通过用例覆盖验收标准：%s" % identifier)

    if stage >= 9 and "09-release.md" in actual:
        release_status = state.get("release_status")
        if release_status not in ("planned", "deployed", "verified", "rolled_back"):
            block("state.release_status 缺失或无效")
        execution = section(texts["09-release.md"], "执行结果")
        if not execution:
            block("09-release.md 缺少实际执行结果")
        doc_status = release_field(execution, "状态")
        if doc_status not in RELEASE_MAP:
            block("09-release.md 执行状态缺失或无效")
        elif release_status in RELEASE_MAP.values() and RELEASE_MAP[doc_status] != release_status:
            block("发布状态与 state 不一致：文档=%s，state=%s" % (doc_status, release_status))
        if release_status != "verified":
            block("上线尚未完成或已回滚：release_status=%s" % release_status)
        if missing_value(release_field(execution, "证据")):
            block("上线执行结果缺少证据")
        if missing_value(release_field(execution, "观察窗结论")):
            block("上线执行结果缺少观察窗结论")

    print("已检查：状态 / 产物 / 编号 / 覆盖 / 版本 / 缺陷 / 回归 / 发布")
    return finish(root, stage)


if __name__ == "__main__":
    sys.exit(main())
