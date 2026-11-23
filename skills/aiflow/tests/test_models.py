#!/usr/bin/env python3
"""Model routing, immutable policies and execution evidence. All model IDs here are test fixtures."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from model_records import check_model_execution
from resolve_models import (create_snapshot, parse_json, prepare_dispatch, resolve_models,
                            select_model, validate_config, validate_snapshot)


def config():
    return {"schema_version": 1, "default": "inherit",
            "profiles": {"coding": {"model": "test-code"},
                         "deep": {"model": "test-deep", "reasoning_effort": "high"},
                         "review": {"model": "test-review"}},
            "roles": {"fe": "coding", "be": "deep", "tester": "deep", "final_reviewer": "review"}}


class ModelRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiflow-models-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "项目"
        self.root.mkdir()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "resolve_models.py"), str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_missing_configuration_inherits_without_creating_files(self):
        result = resolve_models(self.root, 0, ["analyst"], execution=1)
        self.assertTrue(result["ok"])
        self.assertFalse(result["configured"])
        self.assertIsNone(result["snapshot"])
        self.assertEqual(result["role_models"]["analyst"]["launch"], {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_all_registered_skill_names_resolve_to_their_existing_role_keys(self):
        skills = json.loads((SCRIPTS.parent / "roles.json").read_text(encoding="utf-8"))["roles"]
        policy = config()
        policy["roles"] = {skill: "coding" for skill in skills.values()}
        self.write(".aiflow/models.json", policy)
        result = resolve_models(self.root, 6, list(skills.values()))
        self.assertEqual(set(result["role_models"]), set(skills))
        for role, skill in skills.items():
            with self.subTest(skill=skill):
                selection = result["role_models"][role]
                self.assertEqual(selection["skill"], skill)
                self.assertEqual(selection["launch"], {"model": "test-code"})
                self.assertEqual(selection["source"], f"roles.{role}")

    def test_skill_names_and_short_keys_share_override_precedence(self):
        policy = config()
        policy["roles"] = {"aiflow-frontend": "coding", "be": "deep"}
        policy["stages"] = {"6": {"default": "deep", "roles": {"fe": "coding", "aiflow-backend": "review"}}}
        self.write(".aiflow/models.json", policy)
        cases = ((5, "aiflow-frontend", "fe", {}, "test-code", "roles.fe"),
                 (5, "aiflow-backend", "be", {}, "test-deep", "roles.be"),
                 (6, "aiflow-frontend", "fe", {}, "test-code", "stages.6.roles.fe"),
                 (6, "be", "be", {}, "test-review", "stages.6.roles.be"),
                 (6, "aiflow-analyst", "analyst", {}, "test-deep", "stages.6.default"),
                 (6, "fe", "fe", {"aiflow-frontend": "review"}, "test-review", "overrides.fe"),
                 (6, "aiflow-backend", "be", {"be": "inherit"}, None, "overrides.be"))
        for stage, name, role, overrides, model, source in cases:
            with self.subTest(stage=stage, name=name, overrides=overrides):
                result = resolve_models(self.root, stage, [name], overrides=overrides)
                selection = result["role_models"][role]
                self.assertEqual((selection["model"], selection["source"]), (model, source))

    def test_duplicate_aliases_are_rejected_within_each_configuration_level(self):
        duplicate = {"fe": "coding", "aiflow-frontend": "coding"}
        policies = ({**config(), "roles": duplicate},
                    {**config(), "stages": {"6": {"roles": duplicate}}})
        for policy in policies:
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "duplicate role fe"):
                create_snapshot(policy, 6, 1)
        with self.assertRaisesRegex(ValueError, "duplicate role fe"):
            create_snapshot(config(), 6, 1, overrides=duplicate)

    def test_skill_named_snapshots_match_legacy_keys_and_support_later_dispatch(self):
        legacy = config()
        legacy["stages"] = {"6": {"roles": {"be": "coding"}}}
        named = json.loads(json.dumps(legacy))
        named["roles"]["aiflow-frontend"] = named["roles"].pop("fe")
        named["stages"]["6"]["roles"] = {"aiflow-backend": "coding"}
        original = json.loads(json.dumps(named))
        overrides = {"aiflow-frontend": {"model": "test-review", "reasoning_effort": "high"}}
        snapshot = create_snapshot(named, 6, 3, overrides=overrides)
        old_snapshot = create_snapshot(legacy, 6, 3, overrides={"fe": overrides["aiflow-frontend"]})
        self.assertEqual(snapshot, old_snapshot)
        self.assertEqual(validate_snapshot(old_snapshot), old_snapshot)
        self.assertEqual(named, original)
        self.assertEqual(set(overrides), {"aiflow-frontend"})
        saved = self.write(".aiflow/model-policies/3.json", snapshot)
        self.write(".aiflow/models.json", {"schema_version": 1})
        result = resolve_models(self.root, 6, ["aiflow-frontend", "fe", "aiflow-backend"], snapshot_path=saved)
        self.assertEqual(set(result["role_models"]), {"fe", "be"})
        self.assertEqual(result["role_models"]["fe"]["launch"], {"model": "test-review", "reasoning_effort": "high"})
        self.assertEqual(result["role_models"]["be"]["launch"], {"model": "test-code"})

    def test_priority_and_explicit_inherit(self):
        policy = config()
        policy["default"] = "review"
        policy["stages"] = {"6": {"default": "deep", "roles": {"fe": "coding"}}}
        self.write(".aiflow/models.json", policy)
        cases = ((5, "analyst", {}, "test-review", "default"),
                 (5, "fe", {}, "test-code", "roles.fe"),
                 (6, "analyst", {}, "test-deep", "stages.6.default"),
                 (6, "fe", {}, "test-code", "stages.6.roles.fe"),
                 (6, "fe", {"fe": "review"}, "test-review", "overrides.fe"),
                 (6, "fe", {"fe": "inherit"}, None, "overrides.fe"))
        for stage, role, overrides, model, source in cases:
            with self.subTest(stage=stage, role=role, overrides=overrides):
                selection = resolve_models(self.root, stage, [role], overrides=overrides)["role_models"][role]
                self.assertEqual((selection["model"], selection["source"]), (model, source))

    def test_profile_replacement_does_not_merge_reasoning_from_lower_priority(self):
        policy = config()
        policy["stages"] = {"9": {"roles": {"be": "coding"}}}
        self.write(".aiflow/models.json", policy)
        selection = resolve_models(self.root, 9, ["be"])["role_models"]["be"]
        self.assertEqual(selection["launch"], {"model": "test-code"})

    def test_coordinator_and_reviewers_have_separate_routing_keys(self):
        policy = config()
        policy["roles"].update(coordinator="coding", designer="deep", design_reviewer="review")
        self.write(".aiflow/models.json", policy)
        result = resolve_models(self.root, 3, ["coordinator", "designer", "design_reviewer", "final_reviewer"])
        self.assertEqual([item["model"] for item in result["role_models"].values()],
                         ["test-code", "test-deep", "test-review", "test-review"])

    def test_invalid_configuration_is_rejected_even_for_unselected_roles(self):
        invalid = ({}, {"schema_version": True}, {"schema_version": 2}, {"schema_version": 1, "typo": {}},
                   {"schema_version": 1, "roles": {"frontend": "inherit"}},
                   {"schema_version": 1, "roles": {"be": "missing"}},
                   {"schema_version": 1, "stages": {"06": {}}},
                   {"schema_version": 1, "stages": {"12": {}}},
                   {"schema_version": 1, "stages": {"9": {"roles": {"be": "missing"}}}},
                   {"schema_version": 1, "profiles": {"inherit": {"model": "test-code"}}},
                   {"schema_version": 1, "profiles": {"bad": {"model": " "}}},
                   {"schema_version": 1, "profiles": {"bad": {"model": "inherit"}}},
                   {"schema_version": 1, "profiles": {"bad": {"model": "test-code", "reasoning_effort": 1}}},
                   {"schema_version": 1, "on_unavailable": "silent"},
                   {"schema_version": 1, "roles": []}, [])
        for value in invalid:
            with self.subTest(value=value):
                self.write(".aiflow/models.json", value)
                with self.assertRaises(ValueError):
                    resolve_models(self.root, 0, ["analyst"])

    def test_unknown_stage_role_and_override_are_rejected(self):
        for stage in (True, -1, 12, "6"):
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                resolve_models(self.root, stage, ["fe"])
        with self.assertRaises(ValueError):
            resolve_models(self.root, 6, ["developer"])
        with self.assertRaises(ValueError):
            resolve_models(self.root, 6, ["fe"], overrides={"be": "missing"})

    def test_duplicate_json_keys_and_non_json_numbers_are_rejected(self):
        for text in ('{"schema_version":1,"schema_version":1}',
                     '{"schema_version":1,"roles":{"fe":"inherit","fe":"missing"}}',
                     '{"schema_version":NaN}', '{"schema_version":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_json(text)

    def test_explicit_missing_config_does_not_fall_back(self):
        with self.assertRaises(OSError):
            resolve_models(self.root, 6, ["fe"], config_path=self.root / "missing.json")

    def test_bom_and_non_ascii_paths_are_supported(self):
        path = self.write("团队配置.json", config())
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        result = self.cli("--stage", "6", "--role", "fe", "--config", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["role_models"]["fe"]["model"], "test-code")

    def test_stage_snapshot_survives_live_config_change_and_late_role_dispatch(self):
        path = self.write(".aiflow/models.json", config())
        result = resolve_models(self.root, 6, ["fe"], execution=3)
        saved = self.write(".aiflow/model-policies/3.json", result["snapshot"])
        path.unlink()
        continued = resolve_models(self.root, 6, ["be"], snapshot_path=saved, execution=3)
        self.assertEqual(continued["role_models"]["be"]["model"], "test-deep")
        self.assertEqual(continued["snapshot_path"], str(saved.resolve()))
        self.assertFalse(path.exists())
        with self.assertRaises(ValueError):
            resolve_models(self.root, 7, ["fe"], snapshot_path=saved)
        with self.assertRaises(ValueError):
            resolve_models(self.root, 6, ["fe"], execution=4, snapshot_path=saved)
        with self.assertRaises(ValueError):
            resolve_models(self.root, 6, ["fe"], overrides={"fe": "inherit"}, snapshot_path=saved)

    def test_snapshots_detach_mutable_input_and_detect_changes(self):
        policy = config()
        snapshot = create_snapshot(policy, 6, 1)
        policy["profiles"]["coding"]["model"] = "changed"
        self.assertEqual(validate_snapshot(snapshot)["config"]["profiles"]["coding"]["model"], "test-code")
        snapshot["config"]["profiles"]["coding"]["model"] = "changed"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            validate_snapshot(snapshot)

    def test_capability_check_distinguishes_unknown_unsupported_and_available(self):
        selection = select_model(validate_config(config()), 6, "be")
        self.assertEqual(prepare_dispatch(selection)["availability"], "unverified")
        self.assertEqual(prepare_dispatch(selection, {"model_selection": True})["availability"], "unverified")
        for capability in ({"model_selection": False}, {"model_selection": True, "models": {}},
                           {"model_selection": True, "models": {"test-deep": {"reasoning_efforts": ["low"]}}}):
            with self.subTest(capability=capability):
                dispatch = prepare_dispatch(selection, capability)
                self.assertEqual(dispatch["availability"], "blocked")
                self.assertIsNone(dispatch["launch"])
        available = prepare_dispatch(selection, {"model_selection": True,
                                                "models": {"test-deep": {"reasoning_efforts": ["high"]}}})
        self.assertEqual(available["availability"], "available")
        self.assertEqual(available["launch"], {"model": "test-deep", "reasoning_effort": "high"})

    def test_fallback_requires_explicit_policy_and_clears_all_launch_overrides(self):
        policy = config()
        policy["on_unavailable"] = "inherit"
        self.write(".aiflow/models.json", policy)
        result = resolve_models(self.root, 6, ["be"], capabilities={"model_selection": False})
        selection = result["role_models"]["be"]
        self.assertTrue(result["ok"])
        self.assertEqual((selection["availability"], selection["launch"]), ("fallback", {}))
        self.assertEqual(selection["model"], "test-deep")
        self.assertTrue(selection["reason"])

    def test_cli_inline_model_override_works_before_project_initialization(self):
        result = self.cli("--stage", "0", "--role", "analyst", "--model", "analyst=test-deep",
                          "--reasoning-effort", "analyst=high", "--execution", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["role_models"]["analyst"]["launch"], {"model": "test-deep", "reasoning_effort": "high"})
        self.assertIsNotNone(data["snapshot"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_accepts_skill_names_in_roles_profiles_models_and_reasoning(self):
        self.write(".aiflow/models.json", config())
        result = self.cli("--stage", "6", "--role", "aiflow-frontend", "--role", "fe", "--role", "aiflow-backend",
                          "--override", "aiflow-frontend=review", "--model", "aiflow-backend=test-deep",
                          "--reasoning-effort", "be=high", "--execution", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data["role_models"]), {"fe", "be"})
        self.assertEqual(data["role_models"]["fe"]["launch"], {"model": "test-review"})
        self.assertEqual(data["role_models"]["be"]["launch"], {"model": "test-deep", "reasoning_effort": "high"})
        self.assertEqual(set(data["snapshot"]["overrides"]), {"fe", "be"})

    def test_cli_aliases_cannot_bypass_duplicate_or_incompatible_assignments(self):
        self.write(".aiflow/models.json", config())
        cases = (("--override", "fe=coding", "--override", "aiflow-frontend=review"),
                 ("--model", "fe=test-code", "--model", "aiflow-frontend=test-deep"),
                 ("--model", "fe=test-deep", "--reasoning-effort", "fe=high", "--reasoning-effort", "aiflow-frontend=low"),
                 ("--model", "aiflow-frontend=test-code", "--override", "fe=deep"),
                 ("--model", "aiflow-frontend=test-code", "--reasoning-effort", "aiflow-backend=high"))
        for options in cases:
            with self.subTest(options=options):
                result = self.cli("--stage", "6", "--role", "aiflow-frontend", *options)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertFalse(json.loads(result.stdout)["ok"])
                self.assertNotIn("Traceback", result.stderr)

    def test_cli_reports_invalid_combinations_and_unavailable_models_without_tracebacks(self):
        self.write(".aiflow/models.json", config())
        caps = self.write("capabilities.json", {"model_selection": False})
        for options in (("--model", "fe=test-code", "--override", "fe=deep"),
                        ("--reasoning-effort", "fe=high"), ("--override", "fe=missing"),
                        ("--capabilities", str(caps)), ("--execution", "0")):
            with self.subTest(options=options):
                result = self.cli("--stage", "6", "--role", "fe", *options)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertFalse(json.loads(result.stdout)["ok"])
                self.assertNotIn("Traceback", result.stderr)


class ModelRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiflow-model-records-")
        self.addCleanup(self.tmp.cleanup)
        self.af = Path(self.tmp.name) / ".aiflow"
        self.af.mkdir()
        self.state = {"mode": 2, "stage": 6, "agent_sessions": {}, "session_log": []}
        self.expected = {}
        self.runs = []
        self.policies = 0

    def policy(self, value=None, execution=1):
        self.policies += 1
        value = config() if value is None else value
        (self.af / "models.json").write_text(json.dumps(value), encoding="utf-8")
        self.snapshot = create_snapshot(value, self.state["stage"], execution, self.af / "models.json")
        self.relative = f"model-policies/{execution}-{self.policies}.json"
        path = self.af / self.relative
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(self.snapshot), encoding="utf-8")
        self.state["model_policy"] = {"snapshot": self.relative, "fingerprint": self.snapshot["fingerprint"]}
        return self.snapshot

    def record(self, role, session, *, actual=None, unverified=False, **extra):
        selection = select_model(self.snapshot["config"], self.snapshot["stage"], role, self.snapshot["overrides"])
        run = {"schema_version": 1, "execution": self.snapshot["execution"], "stage": self.snapshot["stage"],
               "role": role, "session_id": session, "policy": self.relative,
               "policy_fingerprint": self.snapshot["fingerprint"],
               "requested_model": selection["model"], "requested_reasoning_effort": selection["reasoning_effort"],
               "actual_model": None if unverified else actual or selection["model"] or "test-host-default",
               "actual_reasoning_effort": None if unverified else selection["reasoning_effort"],
               "verification": "unverified" if unverified else "verified",
               "dispatch_evidence": "fixture native dispatch result", "model_evidence": "" if unverified else "fixture host metadata",
               "created_at": "2026-11-16T12:00:00+08:00", **extra}
        self.runs.append(run)
        if role != "final_reviewer":
            self.state["agent_sessions"][role] = session
            self.expected[role] = session
            entry = f'{run["execution"]} {run["stage"]} {role} {session}'
            if entry not in self.state["session_log"]:
                self.state["session_log"].append(entry)
        return run

    def check(self):
        (self.af / "model_runs.jsonl").write_text("".join(json.dumps(run) + "\n" for run in self.runs), encoding="utf-8")
        return check_model_execution(self.af, self.state, self.state["stage"], self.expected)

    def assert_error(self, text):
        self.assertIn(text, "\n".join(self.check()))

    def final_review(self):
        self.state["mode"] = 3
        self.state["stage"] = 10
        self.policy()
        self.record("fe", "session-fe")
        self.record("tester", "session-test")
        self.record("final_reviewer", "session-final")
        self.state["agent_sessions"]["final_reviewer"] = "model:test-review"
        self.state["final_review_session"] = "session-final"

    def test_legacy_project_has_no_new_record_requirements(self):
        self.expected = {"fe": "legacy-session"}
        self.assertEqual(self.check(), [])

    def test_configured_project_must_have_policy_and_every_current_session(self):
        self.policy()
        self.record("fe", "session-fe")
        self.expected["be"] = "session-be"
        self.assert_error("缺少本次 be")
        self.record("be", "session-be")
        self.assertEqual(self.check(), [])
        self.state.pop("model_policy")
        self.assert_error("model_policy")

    def test_skill_named_configuration_uses_existing_session_and_model_record_keys(self):
        policy = config()
        policy["roles"] = {"aiflow-frontend": "coding", "aiflow-backend": "deep"}
        self.policy(policy)
        self.record("fe", "session-fe")
        self.record("be", "session-be")
        self.assertEqual(self.check(), [])
        self.runs[-1]["requested_model"] = "test-code"
        self.assert_error("requested settings differ")

    def test_coordinator_and_design_reviewer_are_checked_like_other_dispatched_roles(self):
        self.state["stage"] = 3
        self.policy()
        self.record("designer", "session-designer")
        self.expected.update(coordinator="session-coordinator", design_reviewer="session-reviewer")
        self.assert_error("缺少本次 coordinator")
        self.assert_error("缺少本次 design_reviewer")
        self.record("coordinator", "session-coordinator")
        self.record("design_reviewer", "session-reviewer")
        self.assertEqual(self.check(), [])

    def test_live_config_changes_do_not_change_running_policy(self):
        self.policy()
        self.record("fe", "session-fe")
        (self.af / "models.json").write_text("invalid edited config", encoding="utf-8")
        self.assertEqual(self.check(), [])

    def test_removing_config_and_index_cannot_erase_current_model_policy(self):
        self.policy()
        self.record("fe", "session-fe")
        (self.af / "models.json").unlink()
        self.state["model_policy"] = {}
        self.assert_error("索引缺失")
        # A later execution can explicitly stop using model routing without erasing history.
        self.state["stage"] = 9
        self.state["session_log"].append("2 9 fe new-session")
        self.expected["fe"] = self.state["agent_sessions"]["fe"] = "new-session"
        self.assertEqual(self.check(), [])

    def test_removed_index_detection_accepts_session_log_outer_whitespace(self):
        self.state["stage"] = 5
        self.policy()
        self.record("fe", "history-fe")
        self.state["stage"] = 6
        self.policy(execution=2)
        self.expected.clear()
        self.record("be", "current-be", actual="test-wrong")
        self.state["session_log"][-1] = "  " + self.state["session_log"][-1] + "  "
        self.assert_error("实际模型与请求模型不一致")
        self.state.pop("model_policy")
        (self.af / "models.json").unlink()
        self.assert_error("索引缺失")

    def test_tampered_policy_and_wrong_current_stage_are_blocked(self):
        self.policy()
        self.record("fe", "session-fe")
        self.state["model_policy"]["fingerprint"] = "wrong"
        self.assert_error("指纹或阶段")
        self.state["model_policy"]["fingerprint"] = self.snapshot["fingerprint"]
        self.state["stage"] = 7
        self.assert_error("指纹或阶段")

    def test_snapshot_and_session_log_must_describe_same_execution(self):
        self.policy()
        self.record("fe", "session-fe")
        self.state["session_log"].append("2 6 fe another-session")
        self.assert_error("执行序号与 session_log")

    def test_requested_and_actual_models_cannot_be_conflated(self):
        self.policy()
        run = self.record("fe", "session-fe", actual="test-host-override")
        self.assert_error("实际模型与请求模型不一致")
        run["requested_model"] = "test-host-override"
        self.assert_error("requested settings differ")

    def test_unverified_explicit_model_blocks_but_inherit_is_honest(self):
        self.policy()
        self.record("fe", "session-fe", unverified=True)
        self.assert_error("尚未核实实际值")
        self.runs.clear()
        self.expected.clear()
        self.record("analyst", "session-analyst", unverified=True)
        self.assertEqual(self.check(), [])

    def test_reasoning_must_be_verified_when_requested(self):
        self.policy()
        run = self.record("be", "session-be")
        run["actual_reasoning_effort"] = None
        self.assert_error("实际推理强度")
        run["actual_reasoning_effort"] = "high"
        self.assertEqual(self.check(), [])

    def test_fallback_is_allowed_only_with_policy_and_per_session_reason(self):
        self.policy()
        self.record("fe", "session-fe", actual="test-default", fallback_reason="fixture host rejection")
        self.assert_error("回退未经策略允许")
        policy = config()
        policy["on_unavailable"] = "inherit"
        self.policy(policy)
        self.record("fe", "replacement-fe", actual="test-default", fallback_reason="fixture host rejection")
        self.assertEqual(self.check(), [])

    def test_same_stage_model_change_requires_new_session_and_preserves_unaffected_roles(self):
        self.policy()
        self.record("fe", "session-fe")
        self.record("be", "session-be")
        policy = config()
        policy["roles"]["be"] = "coding"
        self.policy(policy)
        self.assert_error("当前策略已改变")
        replacement = self.record("be", "replacement-be")
        self.assertEqual(self.check(), [])
        replacement["session_id"] = "session-be"
        self.state["agent_sessions"]["be"] = self.expected["be"] = "session-be"
        self.assert_error("须新建会话")

    def test_cross_stage_session_reuse_is_rejected(self):
        self.policy()
        self.record("fe", "session-fe")
        self.state["stage"] = 9
        self.policy(execution=2)
        self.record("fe", "session-fe")
        self.assert_error("须新建会话")

    def test_actual_model_cannot_change_within_same_session(self):
        policy = config()
        policy["roles"]["fe"] = "inherit"
        self.policy(policy)
        self.record("fe", "session-fe", actual="test-one")
        self.record("fe", "session-fe", actual="test-two")
        self.assert_error("不同的实际模型")

    def test_later_observation_can_verify_previously_unknown_model(self):
        self.policy()
        self.record("fe", "session-fe", unverified=True)
        self.record("fe", "session-fe")
        self.assertEqual(self.check(), [])

    def test_verification_requires_host_evidence_and_null_unknown_values(self):
        self.policy()
        run = self.record("fe", "session-fe")
        run["model_evidence"] = ""
        self.assert_error("model_evidence")
        run["verification"] = "unverified"
        self.assert_error("keep actual model and effort null")

    def test_record_schema_rejects_invalid_ids_timestamps_and_escaping_policy_paths(self):
        self.policy()
        run = self.record("fe", "session-fe")
        for key, value in (("execution", True), ("stage", 12), ("role", "developer"), ("session_id", ""),
                           ("created_at", "2026-11-16T10:00:00"), ("policy", "../../outside.json"),
                           ("policy_fingerprint", "wrong"), ("verification", "assumed")):
            with self.subTest(key=key):
                original = run[key]
                run[key] = value
                self.assertTrue(self.check())
                run[key] = original

    def test_malformed_jsonl_is_an_error_not_silently_skipped(self):
        self.policy()
        self.record("fe", "session-fe")
        self.check()
        with (self.af / "model_runs.jsonl").open("a", encoding="utf-8") as stream:
            stream.write('{"execution":')
        errors = check_model_execution(self.af, self.state, 6, self.expected)
        self.assertIn("第 2 行无效", "\n".join(errors))

    def test_mode1_requires_explicit_fallback_for_requested_models(self):
        self.policy()
        self.state["mode"] = 1
        self.expected = {"fe": None}
        self.assert_error("模式 1 无法按角色切换模型")
        policy = config()
        policy["on_unavailable"] = "inherit"
        self.policy(policy)
        self.state["model_policy"]["fallback_reason"] = "fixture host has no independent agents"
        self.assertEqual(self.check(), [])

    def test_skipped_stage_does_not_require_models_and_cannot_carry_old_index(self):
        (self.af / "models.json").write_text(json.dumps(config()), encoding="utf-8")
        self.assertEqual(self.check(), [])
        self.policy()
        for mode in (1, 2, 3):
            with self.subTest(mode=mode):
                self.state["mode"] = mode
                self.assert_error("跳过的阶段须清除")
        self.state["model_policy"] = {}
        self.assertEqual(self.check(), [])

    def test_model_policy_shape_does_not_accept_empty_list_as_legacy(self):
        self.state["model_policy"] = []
        self.assert_error("必须是一层字典")

    def test_different_model_final_review_uses_actual_models_and_real_session(self):
        self.final_review()
        self.assertEqual(self.check(), [])
        final = self.runs[-1]
        final["actual_model"] = "test-code"
        self.state["agent_sessions"]["final_reviewer"] = "model:test-code"
        self.assert_error("使用相同实际模型")
        final["actual_model"] = "test-review"
        self.state["agent_sessions"]["final_reviewer"] = "model:test-review"
        self.state["final_review_session"] = "model:test-review"
        self.assert_error("缺少 final_review_session")

    def test_distinct_requested_models_do_not_prove_distinct_execution_models(self):
        self.final_review()
        policy = config()
        policy["on_unavailable"] = "inherit"
        self.policy(policy)
        self.record("final_reviewer", "fallback-final", actual="test-code", fallback_reason="fixture unavailable model")
        self.state["agent_sessions"]["final_reviewer"] = "model:test-code"
        self.state["final_review_session"] = "fallback-final"
        self.assert_error("使用相同实际模型")

    def test_final_reviewer_cannot_use_a_dispatch_session_from_before_model_logging(self):
        self.state.update(mode=3, stage=10)
        self.state["session_log"].extend(["1 8 tester old-tester", "2 9 coordinator old-coordinator"])
        self.policy(execution=3)
        self.record("tester", "current-tester")
        self.state["agent_sessions"]["final_reviewer"] = "model:test-review"
        for session in ("old-tester", "old-coordinator"):
            with self.subTest(session=session):
                self.record("final_reviewer", session)
                self.state["final_review_session"] = session
                self.assert_error("已在 session_log")
                self.runs.pop()
        self.record("final_reviewer", "independent-reviewer")
        self.state["final_review_session"] = "independent-reviewer"
        self.assertEqual(self.check(), [])

    def test_unknown_execution_model_cannot_prove_different_model_review(self):
        self.final_review()
        run = self.runs[0]
        run.update(verification="unverified", actual_model=None, actual_reasoning_effort=None, model_evidence="")
        self.expected.pop("fe")
        self.assert_error("无法核实执行会话 session-fe")

    def test_human_final_review_needs_no_model_identity(self):
        self.final_review()
        self.runs.pop()
        self.state["agent_sessions"]["final_reviewer"] = "human:reviewer"
        self.state.pop("final_review_session")
        self.assertEqual(self.check(), [])

    def test_stage11_can_reference_valid_stage10_final_review(self):
        self.final_review()
        self.state["stage"] = 11
        self.policy(execution=2)
        self.expected.clear()
        self.record("operator", "session-operator", actual="test-code")
        self.assertEqual(self.check(), [])

    def test_redone_regression_cannot_reuse_previous_final_review(self):
        self.final_review()
        self.policy(execution=2)
        self.expected.clear()
        self.record("tester", "replacement-tester")
        self.assert_error("之前执行的会话")

    def test_release_cannot_reuse_final_review_from_before_redone_regression(self):
        self.final_review()
        self.policy(execution=2)
        self.expected.clear()
        self.record("tester", "replacement-tester")
        self.state["stage"] = 11
        self.policy(execution=3)
        self.expected.clear()
        self.record("operator", "session-operator", actual="test-code")
        self.assert_error("不属于最近一次阶段 10 执行")


if __name__ == "__main__":
    unittest.main()
