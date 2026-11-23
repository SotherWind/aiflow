"""Validate model policy references and observed execution records, without changing them."""

import re
from datetime import datetime
from pathlib import Path

from resolve_models import (ROLE_KEYS, SCHEMA_VERSION, nonempty, object_fields, parse_json,
                            positive_integer, read_json, select_model, validate_config,
                            validate_snapshot, validate_stage)


def local_file(af, relative):
    nonempty(relative, "model policy path")
    path = Path(relative)
    if path.is_absolute() or not (af / path).resolve().is_relative_to(af.resolve()):
        raise ValueError("Model policy path must stay inside .aiflow")
    return af / path


def _optional_text(value, label):
    if value is not None:
        nonempty(value, label)


def normalized_session_id(value):
    return value.strip() if isinstance(value, str) else ""


def _validate_record(record, load_snapshot):
    fields = ("schema_version", "execution", "stage", "role", "session_id", "policy", "policy_fingerprint",
              "requested_model", "requested_reasoning_effort", "actual_model", "actual_reasoning_effort",
              "verification", "dispatch_evidence", "model_evidence", "fallback_reason", "created_at")
    object_fields(record, fields, "model run", set(fields) - {"fallback_reason"})
    if type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported model run schema_version")
    positive_integer(record["execution"], "model run execution")
    validate_stage(record["stage"])
    if record["role"] not in ROLE_KEYS:
        raise ValueError("Unknown model run role")
    for key in ("session_id", "dispatch_evidence", "created_at"):
        nonempty(record[key], "model run " + key)
    timestamp = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("model run created_at must include a timezone")
    for key in ("requested_model", "requested_reasoning_effort", "actual_model", "actual_reasoning_effort"):
        _optional_text(record[key], "model run " + key)
    if not isinstance(record.get("fallback_reason", ""), str):
        raise ValueError("model run fallback_reason must be a string")
    if record["verification"] == "verified":
        nonempty(record["actual_model"], "verified actual_model")
        nonempty(record["model_evidence"], "verified model_evidence")
    elif record["verification"] == "unverified":
        if record["actual_model"] is not None or record["actual_reasoning_effort"] is not None:
            raise ValueError("Unverified model runs must keep actual model and effort null")
        if not isinstance(record["model_evidence"], str):
            raise ValueError("model_evidence must be a string")
    else:
        raise ValueError("verification must be verified or unverified")
    snapshot = load_snapshot(record["policy"])
    if (snapshot["fingerprint"], snapshot["execution"], snapshot["stage"]) != (
            record["policy_fingerprint"], record["execution"], record["stage"]):
        raise ValueError("Model run policy fingerprint, stage or execution differs")
    selection = select_model(snapshot["config"], record["stage"], record["role"], snapshot["overrides"])
    if (record["requested_model"], record["requested_reasoning_effort"]) != (
            selection["model"], selection["reasoning_effort"]):
        raise ValueError("Model run requested settings differ from its frozen policy")
    return selection


def _compliance(record, selection):
    if (record["requested_model"], record["requested_reasoning_effort"]) != (
            selection["model"], selection["reasoning_effort"]):
        return "当前策略已改变，须用新会话重新派工"
    fallback = record.get("fallback_reason", "").strip()
    if fallback:
        if selection["on_unavailable"] != "inherit" or selection["model"] is None:
            return "模型回退未经策略允许"
        return None
    if selection["model"] is not None:
        if record["verification"] != "verified":
            return "显式指定的模型尚未核实实际值"
        if record["actual_model"] != selection["model"]:
            return "实际模型与请求模型不一致，须核对宿主覆盖或记录获准的回退"
        if selection["reasoning_effort"] is not None and record["actual_reasoning_effort"] != selection["reasoning_effort"]:
            return "实际推理强度与请求值不一致或尚未核实"
    return None


def check_model_execution(af, state, stage, expected_sessions):
    """Return gate errors. Legacy projects without a policy retain their original behavior."""
    errors = []
    index = state.get("model_policy", {})
    if not isinstance(index, dict):
        return ["model_policy 必须是一层字典"]
    config_path = af / "models.json"
    if not index:
        # Removing the config and index must not erase a policy already used in this execution.
        runs_path = af / "model_runs.jsonl"
        if expected_sessions and state.get("mode") in (2, 3) and runs_path.exists():
            try:
                log = state.get("session_log", [])
                numbers = [int(match[1]) for entry in log if isinstance(entry, str)
                           and (match := re.match(r"^([0-9]+)\s", entry.strip()))] if isinstance(log, list) else []
                latest_execution = max(numbers) if numbers else None
                for line in runs_path.read_text(encoding="utf-8-sig").splitlines():
                    if not line.strip():
                        continue
                    record = parse_json(line)
                    if not isinstance(record, dict):
                        raise ValueError("model run must be an object")
                    current = (record.get("execution") == latest_execution if latest_execution is not None else
                               record.get("session_id") in expected_sessions.values())
                    if record.get("stage") == stage and current:
                        return ["本次 model_runs.jsonl 已记录模型策略，但 model_policy 索引缺失；不能按未配置放行"]
            except (OSError, ValueError, TypeError) as error:
                return [f"无法核对既有模型记录：{error}"]
        if not config_path.exists() or not expected_sessions:
            return []
        try:
            config = validate_config(read_json(config_path))
            if state.get("mode") == 1 and all(select_model(config, stage, role)["model"] is None for role in expected_sessions):
                return []
        except (OSError, ValueError, TypeError, KeyError) as error:
            return [f"模型配置无效：{error}"]
        return ["已配置模型但缺少本次 model_policy 快照；派工前解析并由主控落档"]

    if not expected_sessions:
        return ["跳过的阶段须清除当前 model_policy 索引并保留历史快照"]
    cache = {}

    def load_snapshot(relative):
        path = local_file(af, relative).resolve()
        if path not in cache:
            cache[path] = validate_snapshot(read_json(path))
        return cache[path]

    try:
        object_fields(index, ("snapshot", "fingerprint", "fallback_reason"), "model_policy", ("snapshot", "fingerprint"))
        if "fallback_reason" in index and not isinstance(index["fallback_reason"], str):
            raise ValueError("model_policy.fallback_reason 必须是字符串")
        snapshot = load_snapshot(index["snapshot"])
        if snapshot["fingerprint"] != index["fingerprint"] or snapshot["stage"] != stage:
            raise ValueError("model_policy 快照指纹或阶段与当前状态不一致")
        selections = {role: select_model(snapshot["config"], stage, role, snapshot["overrides"])
                      for role in expected_sessions}
        if state.get("mode") == 1:
            explicit = any(selection["model"] is not None for selection in selections.values())
            if explicit and (snapshot["config"]["on_unavailable"] != "inherit" or
                             not isinstance(index.get("fallback_reason"), str) or not index["fallback_reason"].strip()):
                errors.append("模式 1 无法按角色切换模型；须允许 inherit 并记录 model_policy.fallback_reason")
            return errors
        if index.get("fallback_reason"):
            errors.append("模式 2/3 的模型回退须逐会话记录在 model_runs.jsonl")
        session_log = state.get("session_log")
        if not isinstance(session_log, list) or not session_log:
            raise ValueError("启用模型策略须在 session_log 记录本次执行与会话")
        logged = set()
        for entry in session_log:
            match = re.fullmatch(r"([0-9]+)\s+([0-9]+)\s+(\S+)\s+(\S.*)", entry.strip()) if isinstance(entry, str) else None
            if not match:
                raise ValueError("模型策略需要有效的 session_log 条目")
            logged.add((int(match[1]), int(match[2]), match[3], match[4]))
        if max(item[0] for item in logged) != snapshot["execution"]:
            raise ValueError("model_policy 执行序号与 session_log 最新执行不一致")
        lines = (af / "model_runs.jsonl").read_text(encoding="utf-8-sig").splitlines()
    except (OSError, ValueError, TypeError, KeyError) as error:
        return [f"模型执行记录无效：{error}"]

    dispatched_sessions = {session for _, _, _, session in logged}
    latest, known_models = {}, {}
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = parse_json(line)
            _validate_record(record, load_snapshot)
            session = record["session_id"]
            if record["role"] == "final_reviewer":
                if session in dispatched_sessions:
                    raise ValueError(f"终验会话 {session} 已在 session_log 用于执行派工，须另建独立会话")
            elif (record["execution"], record["stage"], record["role"], session) not in logged:
                raise ValueError("Model run session is absent from session_log")
            previous = latest.get(session)
            if previous:
                keys = ("execution", "stage", "role", "requested_model", "requested_reasoning_effort")
                if any(previous[key] != record[key] for key in keys):
                    raise ValueError("换阶段、换角色或换模型须新建会话，不能复用 model run session_id")
            actual = (record["actual_model"], record["actual_reasoning_effort"])
            if record["verification"] == "verified":
                known = known_models.get(session)
                if known and (known[0] != actual[0] or
                              (known[1] is not None and actual[1] is not None and known[1] != actual[1])):
                    raise ValueError("同一会话记录了不同的实际模型或推理强度；换模须新建会话")
                known_models[session] = (actual[0], actual[1] if actual[1] is not None else known[1] if known else None)
            latest[session] = record
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors.append(f"model_runs.jsonl 第 {number} 行无效：{error}")

    for role, session in expected_sessions.items():
        record = latest.get(session)
        if record is None or (record["execution"], record["stage"], record["role"]) != (snapshot["execution"], stage, role):
            errors.append(f"model_runs.jsonl 缺少本次 {role} 的真实会话模型记录")
        else:
            mismatch = _compliance(record, selections[role])
            if mismatch:
                errors.append(f"{role} 模型校验失败：{mismatch}")

    sessions = state.get("agent_sessions", {})
    sessions = sessions if isinstance(sessions, dict) else {}
    reviewer = normalized_session_id(sessions.get("final_reviewer"))
    if state.get("mode") == 3 and stage >= 10 and reviewer.startswith("model:"):
        final_session = state.get("final_review_session")
        final = latest.get(final_session) if isinstance(final_session, str) else None
        if final is None or final["role"] != "final_reviewer" or final["stage"] not in (10, 11) or final["stage"] > stage:
            errors.append("不同模型终验缺少 final_review_session 对应的实际 final_reviewer 模型记录")
        else:
            final_policy = load_snapshot(final["policy"])
            final_selection = select_model(final_policy["config"], final["stage"], "final_reviewer", final_policy["overrides"])
            if stage == 10 or final["stage"] == stage:
                final_selection = select_model(snapshot["config"], stage, "final_reviewer", snapshot["overrides"])
                if final["execution"] != snapshot["execution"]:
                    errors.append("不同模型终验沿用了之前执行的会话，须重新终验")
            else:
                latest_regression = max((item[0] for item in logged if item[1] == 10), default=None)
                if final["execution"] != latest_regression:
                    errors.append("阶段 11 的不同模型终验不属于最近一次阶段 10 执行，须重新终验")
            mismatch = _compliance(final, final_selection)
            if mismatch:
                errors.append(f"final_reviewer 模型校验失败：{mismatch}")
            if final["verification"] != "verified" or final["actual_model"] != reviewer[len("model:"):]:
                errors.append("不同模型终验的实际模型未核实，或与 agent_sessions.final_reviewer 不一致")
            else:
                # Compare observed canonical model IDs, including prior-stage execution sessions.
                execution_sessions = {session for role, value in sessions.items()
                                      if role != "final_reviewer" and (session := normalized_session_id(value))}
                execution_sessions.update(session for session in expected_sessions.values() if isinstance(session, str) and session)
                for session in sorted(execution_sessions):
                    execution = latest.get(session)
                    if session == final_session:
                        errors.append("final_reviewer 必须使用独立于执行角色的真实会话")
                    if execution is None or execution["verification"] != "verified":
                        errors.append(f"无法核实执行会话 {session} 的实际模型，不能证明不同模型终验")
                    elif execution["actual_model"] == final["actual_model"]:
                        errors.append(f"final_reviewer 与执行会话 {session} 使用相同实际模型")
    return errors
