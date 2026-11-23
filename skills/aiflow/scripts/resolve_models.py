#!/usr/bin/env python3
"""Preview model routing and immutable stage policies; never write files or launch agents."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
ROLE_SKILLS = json.loads((Path(__file__).resolve().parents[1] / "roles.json").read_text(encoding="utf-8"))["roles"]
ROLE_KEYS = (*ROLE_SKILLS, "coordinator", "design_reviewer", "final_reviewer")
ROLE_ALIASES = {skill: role for role, skill in ROLE_SKILLS.items()}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Invalid JSON value: {value}")


def parse_json(text):
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def fingerprint(value):
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def object_fields(value, allowed, label, required=()):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    unknown, missing = set(value) - set(allowed), set(required) - set(value)
    if unknown or missing:
        raise ValueError(f"{label}: unknown fields {sorted(unknown)}, missing fields {sorted(missing)}")


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a nonempty, trimmed string")
    return value


def positive_integer(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def validate_stage(stage):
    if type(stage) is not int or not 0 <= stage <= 11:
        raise ValueError("stage must be an integer from 0 to 11")


def normalize_role(name):
    role = ROLE_ALIASES.get(name, name) if isinstance(name, str) else None
    if role not in ROLE_KEYS:
        raise ValueError(f"Unknown role: {name}")
    return role


def normalize_role_map(value, label):
    """Accept skill names at input boundaries while keeping stored role identities stable."""
    object_fields(value, (*ROLE_KEYS, *ROLE_ALIASES), label)
    result, names = {}, {}
    for name, target in value.items():
        role = normalize_role(name)
        if role in result:
            raise ValueError(f"{label}: duplicate role {role} via {names[role]} and {name}")
        result[role], names[role] = target, name
    return result


def validate_target(target, label):
    object_fields(target, ("model", "reasoning_effort"), label, ("model",))
    nonempty(target["model"], label + ".model")
    if target["model"] == "inherit":
        raise ValueError(f"{label}: use the inherit profile instead of a model named inherit")
    if "reasoning_effort" in target:
        nonempty(target["reasoning_effort"], label + ".reasoning_effort")


def validate_config(config):
    """Return a normalized, host-neutral policy. Model IDs remain opaque host values."""
    object_fields(config, ("schema_version", "default", "profiles", "roles", "stages", "on_unavailable"),
                  "models", ("schema_version",))
    if type(config["schema_version"]) is not int or config["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported models.schema_version")
    result = {"schema_version": SCHEMA_VERSION, "default": "inherit", "profiles": {}, "roles": {},
              "stages": {}, "on_unavailable": "error", **config}
    if result["on_unavailable"] not in ("error", "inherit"):
        raise ValueError("on_unavailable must be error or inherit")
    for key in ("profiles", "roles", "stages"):
        if not isinstance(result[key], dict):
            raise ValueError(f"models.{key} must be an object")
    for name, target in result["profiles"].items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name) or name == "inherit":
            raise ValueError(f"Invalid or reserved profile name: {name}")
        validate_target(target, f"profiles.{name}")

    def profile_ref(value, label):
        if not isinstance(value, str) or (value != "inherit" and value not in result["profiles"]):
            raise ValueError(f"{label}: unknown profile {value!r}")

    def role_map(value, label):
        value = normalize_role_map(value, label)
        for role, profile in value.items():
            profile_ref(profile, f"{label}.{role}")
        return value

    profile_ref(result["default"], "default")
    result["roles"] = role_map(result["roles"], "roles")
    stages = {}
    for stage, policy in result["stages"].items():
        if not re.fullmatch(r"(?:[0-9]|1[01])", stage):
            raise ValueError(f"Invalid stage key: {stage}")
        object_fields(policy, ("default", "roles"), f"stages.{stage}")
        if "default" in policy:
            profile_ref(policy["default"], f"stages.{stage}.default")
        stages[stage] = dict(policy)
        if "roles" in policy:
            stages[stage]["roles"] = role_map(policy["roles"], f"stages.{stage}.roles")
    result["stages"] = stages
    return result


def validate_overrides(overrides, config):
    overrides = normalize_role_map(overrides, "overrides")
    for role, value in overrides.items():
        if isinstance(value, dict):
            validate_target(value, f"overrides.{role}")
        elif not isinstance(value, str) or (value != "inherit" and value not in config["profiles"]):
            raise ValueError(f"overrides.{role}: unknown profile {value!r}")
    return overrides


def select_model(config, stage, role, overrides=None):
    validate_stage(stage)
    if role not in ROLE_KEYS:
        raise ValueError(f"Unknown role: {role}")
    overrides = overrides or {}
    stage_policy = config["stages"].get(str(stage), {})
    candidates = ((overrides, role, f"overrides.{role}"),
                  (stage_policy.get("roles", {}), role, f"stages.{stage}.roles.{role}"),
                  (stage_policy, "default", f"stages.{stage}.default"),
                  (config["roles"], role, f"roles.{role}"),
                  (config, "default", "default"))
    for mapping, key, source in candidates:
        if key in mapping:
            profile = mapping[key]
            target = profile if isinstance(profile, dict) else config["profiles"].get(profile, {})
            return {"profile": "inline" if isinstance(profile, dict) else profile,
                    "model": target.get("model"), "reasoning_effort": target.get("reasoning_effort"),
                    "source": source, "on_unavailable": config["on_unavailable"]}


def create_snapshot(config, stage, execution, config_path=None, overrides=None):
    validate_stage(stage)
    positive_integer(execution, "execution")
    config = validate_config(config)
    overrides = validate_overrides({} if overrides is None else overrides, config)
    snapshot = {"schema_version": SCHEMA_VERSION, "execution": execution, "stage": stage,
                "config_path": str(Path(config_path).resolve()) if config_path is not None else None,
                "config": config, "overrides": overrides}
    # Detach the frozen policy from the caller's mutable configuration.
    snapshot = json.loads(json.dumps(snapshot, ensure_ascii=False))
    return {**snapshot, "fingerprint": fingerprint(snapshot)}


def validate_snapshot(snapshot):
    fields = ("schema_version", "execution", "stage", "config_path", "config", "overrides", "fingerprint")
    object_fields(snapshot, fields, "model snapshot", fields)
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported model snapshot schema_version")
    validate_stage(snapshot["stage"])
    positive_integer(snapshot["execution"], "snapshot.execution")
    if snapshot["config_path"] is not None:
        nonempty(snapshot["config_path"], "snapshot.config_path")
    config = validate_config(snapshot["config"])
    overrides = validate_overrides(snapshot["overrides"], config)
    if fingerprint({key: value for key, value in snapshot.items() if key != "fingerprint"}) != snapshot["fingerprint"]:
        raise ValueError("Model snapshot fingerprint differs")
    # Saved snapshots use the complete normalized shape so all readers resolve identically.
    if snapshot["config"] != config:
        raise ValueError("Model snapshot config is not normalized")
    if snapshot["overrides"] != overrides:
        raise ValueError("Model snapshot overrides are not normalized")
    return snapshot


def validate_capabilities(capabilities):
    object_fields(capabilities, ("model_selection", "models"), "capabilities", ("model_selection",))
    if type(capabilities["model_selection"]) is not bool:
        raise ValueError("capabilities.model_selection must be a boolean")
    if "models" not in capabilities:
        return
    if not isinstance(capabilities["models"], dict):
        raise ValueError("capabilities.models must be an object")
    for model, details in capabilities["models"].items():
        nonempty(model, "capabilities model ID")
        object_fields(details, ("reasoning_efforts",), f"capabilities.models.{model}")
        if "reasoning_efforts" in details:
            efforts = details["reasoning_efforts"]
            if not isinstance(efforts, list):
                raise ValueError("reasoning_efforts must be a list")
            for effort in efforts:
                nonempty(effort, "reasoning effort")


def prepare_dispatch(selection, capabilities=None):
    """Build a portable launch request; capabilities are observations supplied by the host."""
    if capabilities is not None:
        validate_capabilities(capabilities)
    request = {key: selection[key] for key in ("model", "reasoning_effort") if selection[key] is not None}
    if not request:
        return {"availability": "inherit", "launch": {}, "reason": ""}
    if capabilities is None:
        return {"availability": "unverified", "launch": request, "reason": "Host capabilities were not supplied"}
    reason = ""
    if not capabilities["model_selection"]:
        reason = "Host cannot select a model for this agent"
    elif "models" in capabilities:
        if selection["model"] not in capabilities["models"]:
            reason = "Requested model is not in the host's available model catalog"
        else:
            details = capabilities["models"][selection["model"]]
            effort = selection["reasoning_effort"]
            if effort is not None and "reasoning_efforts" in details and effort not in details["reasoning_efforts"]:
                reason = "Requested reasoning effort is not supported by this model"
            elif effort is not None and "reasoning_efforts" not in details:
                return {"availability": "unverified", "launch": request, "reason": "Reasoning support was not reported"}
    else:
        return {"availability": "unverified", "launch": request, "reason": "Available models were not reported"}
    if reason:
        fallback = selection["on_unavailable"] == "inherit"
        return {"availability": "fallback" if fallback else "blocked", "launch": {} if fallback else None,
                "reason": reason}
    return {"availability": "available", "launch": request, "reason": ""}


def resolve_models(project_root, stage, roles=(), *, config_path=None, execution=None, overrides=None,
                   snapshot_path=None, capabilities=None):
    validate_stage(stage)
    if execution is not None:
        positive_integer(execution, "execution")
    roles = list(dict.fromkeys(normalize_role(role) for role in (roles or ROLE_KEYS)))
    if snapshot_path is not None:
        if config_path is not None or overrides:
            raise ValueError("A saved snapshot cannot be combined with config or overrides")
        snapshot = validate_snapshot(read_json(snapshot_path))
        if snapshot["stage"] != stage or (execution is not None and snapshot["execution"] != execution):
            raise ValueError("Saved model snapshot belongs to a different stage or execution")
        config, overrides = snapshot["config"], snapshot["overrides"]
        path, configured = snapshot["config_path"], True
    else:
        path = Path(config_path).expanduser().resolve() if config_path is not None else Path(project_root).resolve() / ".aiflow" / "models.json"
        configured = path.exists() or config_path is not None or bool(overrides)
        config = validate_config(read_json(path) if path.exists() or config_path is not None else {"schema_version": SCHEMA_VERSION})
        path = str(path) if path.exists() or config_path is not None else None
        overrides = validate_overrides({} if overrides is None else overrides, config)
        snapshot = create_snapshot(config, stage, execution, path, overrides) if configured and execution is not None else None
    selections = {}
    for role in roles:
        selection = select_model(config, stage, role, overrides)
        selections[role] = {"skill": ROLE_SKILLS.get(role), **selection, **prepare_dispatch(selection, capabilities)}
    return {"ok": all(value["availability"] != "blocked" for value in selections.values()),
            "configured": configured, "stage": stage, "config_path": path,
            "snapshot_path": str(Path(snapshot_path).resolve()) if snapshot_path is not None else None,
            "snapshot": snapshot, "role_models": selections}


def _assignments(values, label):
    result = {}
    for value in values:
        role, separator, target = value.partition("=")
        if not separator or not target:
            raise ValueError(f"{label} expects a unique role=value assignment: {value}")
        role = normalize_role(role)
        if role in result:
            raise ValueError(f"{label} expects a unique role=value assignment: {value}")
        result[role] = target
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__,
                                     epilog="Role inputs accept full skill names (e.g. aiflow-frontend) or internal keys (fe). Output uses internal keys.")
    parser.add_argument("project", help="Business project root; no .aiflow directory is required")
    parser.add_argument("--stage", required=True, type=int)
    parser.add_argument("--role", action="append", default=[], help="Repeat for dispatched roles; omit to preview all routing keys")
    parser.add_argument("--config", help="Explicit models JSON instead of project .aiflow/models.json")
    parser.add_argument("--execution", type=int, help="Include a policy snapshot for this session_log execution number")
    parser.add_argument("--snapshot", help="Resolve follow-up dispatch from an existing frozen policy")
    parser.add_argument("--override", action="append", default=[], help="Temporary role=profile override")
    parser.add_argument("--model", action="append", default=[], help="Temporary role=model-ID override, also works without a config file")
    parser.add_argument("--reasoning-effort", action="append", default=[], help="role=effort, only together with --model for that role")
    parser.add_argument("--capabilities", help="JSON containing the host's observed model_selection and optional models catalog")
    args = parser.parse_args()
    try:
        overrides = _assignments(args.override, "--override")
        models = _assignments(args.model, "--model")
        efforts = _assignments(args.reasoning_effort, "--reasoning-effort")
        if set(overrides) & set(models) or set(efforts) - set(models):
            raise ValueError("Use either --override or --model per role; --reasoning-effort requires --model")
        for role, model in models.items():
            overrides[role] = {"model": model, **({"reasoning_effort": efforts[role]} if role in efforts else {})}
        result = resolve_models(args.project, args.stage, args.role, config_path=args.config, execution=args.execution,
                                overrides=overrides, snapshot_path=args.snapshot,
                                capabilities=read_json(args.capabilities) if args.capabilities else None)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = {"ok": False, "error": str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
