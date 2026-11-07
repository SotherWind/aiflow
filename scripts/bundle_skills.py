#!/usr/bin/env python3
"""Generate plugin manifests and self-contained role resources using only stdlib."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE_IDS = {"analyst", "pm", "designer", "architect", "fe", "be", "tester", "operator"}


def inside(root, relative):
    """Resolve a repository-relative file, refusing escapes and symlinks."""
    path = root / relative
    if (Path(relative).is_absolute() or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError(f"Path outside {root}: {relative}")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Linked resource is not portable: {part}")
    return path


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def plan(root=ROOT):
    config = json.loads((root / "aiflow.bundle.json").read_text(encoding="utf-8"))
    if config["schema_version"] != 1 or not isinstance(config["protocol_version"], int):
        raise ValueError("Unsupported bundle schema or protocol")
    roles = config["roles"]
    names = [role["skill"] for role in roles]
    ids = [role["id"] for role in roles]
    if len(roles) != 8 or len(set(names)) != 8 or len(set(ids)) != 8:
        raise ValueError("The bundle must contain eight distinct professional roles")
    if set(ids) != ROLE_IDS:
        raise ValueError("Role IDs must match the aiflow stage protocol")
    if any(not re.fullmatch(r"aiflow-[a-z0-9]+(?:-[a-z0-9]+)*", name) for name in names):
        raise ValueError("Invalid role skill name")
    generated = {}
    for role in roles:
        prefix = f"skills/{role['skill']}"
        for required in ("SKILL.md", "references/aiflow.md"):
            if not inside(root, f"{prefix}/{required}").is_file():
                raise ValueError(f"Missing role source: {prefix}/{required}")
        copied = {}
        for group in role["resources"]:
            for source, target in config["resources"][group].items():
                source_path = inside(root, source)
                target_path = inside(root, f"{prefix}/{target}")
                if not target_path.resolve().is_relative_to((root / prefix).resolve()):
                    raise ValueError(f"Resource outside role: {target}")
                if target in ("SKILL.md", "references/aiflow.md", "role.json"):
                    raise ValueError(f"Resource overwrites role source: {target}")
                if target in copied:
                    raise ValueError(f"Duplicate resource target: {prefix}/{target}")
                data = source_path.read_bytes()
                # Text snapshots are stable across Git's Windows line-ending conversion.
                data = data.replace(b"\r\n", b"\n")
                copied[target] = hashlib.sha256(data).hexdigest()
                generated[f"{prefix}/{target}"] = data
        generated[f"{prefix}/role.json"] = json_bytes({
            "generated_by": "scripts/bundle_skills.py",
            "skill": role["skill"], "role": role["id"],
            "bundle_version": config["version"],
            "protocol_version": config["protocol_version"],
            "resources": copied,
        })

    generated["skills/aiflow/roles.json"] = json_bytes({
        "generated_by": "scripts/bundle_skills.py",
        "bundle_version": config["version"],
        "protocol_version": config["protocol_version"],
        "roles": {role["id"]: role["skill"] for role in roles},
    })
    identity = {"name": config["name"], "version": config["version"],
                "description": config["description"]}
    author = {"name": config["repository"].split("/")[0]}
    generated["plugin.json"] = json_bytes({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        **identity, "license": "MIT", "author": author,
    })
    generated[".claude-plugin/plugin.json"] = json_bytes({
        **identity, "license": "MIT", "author": author,
        "skills": [f"./skills/{name}" for name in ["aiflow", *names]],
    })
    generated[".claude-plugin/marketplace.json"] = json_bytes({
        "name": config["name"], "owner": author,
        "metadata": {"description": config["description"], "version": config["version"]},
        "plugins": [{**identity, "source": "./"}],
    })
    return generated


def stale_resources(root, expected):
    """Identify only previously generated files; never treat role sources as disposable."""
    stale = []
    for metadata in (root / "skills").glob("aiflow-*/role.json"):
        data = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("resources", {}), dict):
            raise ValueError(f"Invalid generated resource manifest: {metadata}")
        if data.get("generated_by") != "scripts/bundle_skills.py":
            continue
        for relative, digest in data.get("resources", {}).items():
            if relative in ("SKILL.md", "references/aiflow.md", "role.json"):
                raise ValueError(f"Role source cannot be a generated resource: {relative}")
            path = inside(metadata.parent, relative)
            key = path.relative_to(root).as_posix()
            if key in expected or not path.exists():
                continue
            content = path.read_bytes().replace(b"\r\n", b"\n")
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError(f"Edited obsolete resource; review it manually: {key}")
            stale.append(path)
    return stale


def build(root=ROOT, check=False):
    expected = plan(root)
    stale = stale_resources(root, expected)
    changed = []
    for relative, content in expected.items():
        path = inside(root, relative)
        actual = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else None
        if actual != content:
            changed.append(relative)
    if check:
        return changed + [str(path.relative_to(root)) + " (obsolete)" for path in stale]
    # All paths and obsolete content were checked before changing any files.
    for path in stale:
        path.unlink()
    for relative in changed:
        path = inside(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected[relative])
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report drift without writing")
    args = parser.parse_args()
    try:
        changed = build(check=args.check)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Bundle error: {error}", file=sys.stderr)
        return 1
    if args.check and changed:
        print("Generated files differ; run python scripts/bundle_skills.py:")
        print("\n".join(changed))
        return 1
    print(f"Bundle {'verified' if args.check else 'updated'}: {len(changed)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
