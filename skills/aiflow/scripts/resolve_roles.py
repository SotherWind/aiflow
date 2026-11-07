#!/usr/bin/env python3
"""Locate the installed aiflow roles without installing or executing anything."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FLOW_ROOT = Path(__file__).resolve().parents[1]


def resolve_roles(flow_root=FLOW_ROOT, extra_roots=(), requested=()):
    manifest = json.loads((flow_root / "roles.json").read_text(encoding="utf-8"))
    roles = manifest["roles"]
    if not isinstance(roles, dict) or not roles:
        raise ValueError("Invalid role registry")
    unknown = set(requested) - set(roles)
    if unknown:
        raise ValueError("Unknown role(s): " + ", ".join(sorted(unknown)))
    selected = requested or roles
    roots = list(dict.fromkeys([flow_root.parent.resolve(), *[Path(p).resolve() for p in extra_roots]]))
    paths, errors = {}, {}
    for role in selected:
        name = roles[role]
        if not re.fullmatch(r"aiflow-[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError(f"Invalid role skill name: {name}")
        candidates = []
        for root in roots:
            folder = root / name
            if not folder.exists():
                continue
            try:
                metadata = json.loads((folder / "role.json").read_text(encoding="utf-8"))
                if not isinstance(metadata, dict):
                    raise ValueError("Invalid role metadata")
                if (metadata.get("skill"), metadata.get("role")) != (name, role):
                    raise ValueError("role identity differs")
                if metadata.get("protocol_version") != manifest["protocol_version"]:
                    raise ValueError("protocol version differs")
                if metadata.get("bundle_version") != manifest["bundle_version"]:
                    raise ValueError("bundle version differs")
                skill = folder / "SKILL.md"
                text = skill.read_text(encoding="utf-8-sig")
                if not re.match(r"\A---\r?\n", text):
                    raise ValueError("SKILL.md has no frontmatter")
                frontmatter = text.split("---", 2)[1]
                if not re.search(r"(?m)^name:\s*" + re.escape(name) + r"\s*$", frontmatter):
                    raise ValueError("SKILL.md name differs")
                for required in ("references/execution.md", "references/aiflow.md"):
                    if not (folder / required).is_file():
                        raise ValueError(f"missing {required}")
                resources = metadata.get("resources")
                if not isinstance(resources, dict) or "references/execution.md" not in resources:
                    raise ValueError("Invalid resource manifest")
                for relative, digest in resources.items():
                    resource = folder / relative
                    if not resource.resolve().is_relative_to(folder.resolve()):
                        raise ValueError(f"resource outside role: {relative}")
                    content = resource.read_bytes().replace(b"\r\n", b"\n")
                    if hashlib.sha256(content).hexdigest() != digest:
                        raise ValueError(f"resource differs: {relative}")
                paths[role] = str(folder.resolve())
                break
            except (OSError, ValueError, KeyError) as error:
                candidates.append({"path": str(folder), "reason": str(error)})
        if role not in paths:
            errors[role] = {"skill": name, "candidates": candidates,
                            "reason": "incompatible_or_incomplete" if candidates else "missing"}
    return {"ok": not errors, "bundle_version": manifest["bundle_version"],
            "protocol_version": manifest["protocol_version"], "flow_root": str(flow_root.resolve()),
            "role_paths": paths, "errors": errors}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", action="append", default=[],
                        help="An additional installed-skills parent directory from the host catalog")
    parser.add_argument("--role", action="append", default=[], help="Check only this role key")
    args = parser.parse_args()
    try:
        result = resolve_roles(extra_roots=args.skills_dir, requested=args.role)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"ok": False, "error": str(error)}
    if not result["ok"]:
        result["repair"] = "Install the complete aiflow bundle from the same release, or provide the host's actual skill directories with --skills-dir."
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
