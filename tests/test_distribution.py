#!/usr/bin/env python3
"""Exercise portable role packages, generation and installed-role resolution."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
CONFIG = json.loads((ROOT / "aiflow.bundle.json").read_text(encoding="utf-8"))


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUNDLE = load_module("bundle_skills", ROOT / "scripts" / "bundle_skills.py")
RESOLVER = load_module("resolve_roles", SKILLS / "aiflow" / "scripts" / "resolve_roles.py")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_skill(name, parent):
    target = parent / name
    shutil.copytree(SKILLS / name, target, ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    return target


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aiflow-distribution-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def installed_bundle(self):
        parent = self.root / "relocated" / "skills"
        parent.mkdir(parents=True)
        for name in ["aiflow", *[role["skill"] for role in CONFIG["roles"]]]:
            copy_skill(name, parent)
        return parent

    def source_copy(self):
        for name in ("aiflow.bundle.json", "LICENSE"):
            shutil.copy2(ROOT / name, self.root / name)
        shutil.copytree(ROOT / "shared", self.root / "shared")
        shutil.copytree(SKILLS, self.root / "skills", ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
        return self.root

    def test_generated_files_are_current(self):
        self.assertEqual(BUNDLE.build(check=True), [])

    def test_plugin_and_standalone_discovery_contain_the_same_nine_skills(self):
        expected = {"aiflow", *[role["skill"] for role in CONFIG["roles"]]}
        discovered = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
        plugin = read_json(ROOT / ".claude-plugin" / "plugin.json")
        marketplace = read_json(ROOT / ".claude-plugin" / "marketplace.json")
        portable = read_json(ROOT / "plugin.json")
        self.assertEqual(discovered, expected)
        self.assertEqual({Path(path).name for path in plugin["skills"]}, expected)
        self.assertEqual(len(plugin["skills"]), 9)
        self.assertEqual(plugin["version"], portable["version"])
        self.assertEqual(marketplace["plugins"][0]["source"], "./")
        self.assertEqual(marketplace["plugins"][0]["name"], portable["name"])

    def test_every_role_can_be_copied_alone_with_local_entrypoint_references(self):
        for role in CONFIG["roles"]:
            with self.subTest(role=role["id"]):
                target = copy_skill(role["skill"], self.root)
                text = (target / "SKILL.md").read_text(encoding="utf-8")
                self.assertRegex(text, r"(?m)^name: " + re.escape(role["skill"]) + r"$")
                metadata = read_json(target / "role.json")
                self.assertEqual(metadata["role"], role["id"])
                self.assertFalse((self.root / "aiflow").exists())
                for link in re.findall(r"\]\(([^)]+)\)", text):
                    if "://" not in link:
                        path = (target / link.split("#")[0]).resolve()
                        self.assertTrue(path.is_relative_to(target.resolve()), link)
                        self.assertTrue(path.is_file(), link)
                for relative in metadata["resources"]:
                    self.assertTrue((target / relative).is_file(), relative)

    def test_relocated_complete_bundle_resolves_absolute_paths(self):
        parent = self.installed_bundle()
        result = RESOLVER.resolve_roles(parent / "aiflow")
        self.assertTrue(result["ok"], result)
        self.assertEqual(set(result["role_paths"]), {role["id"] for role in CONFIG["roles"]})
        self.assertTrue(all(Path(path).is_relative_to(parent) for path in result["role_paths"].values()))

    def test_main_only_reports_missing_roles_without_creating_files(self):
        flow = copy_skill("aiflow", self.root)
        before = sorted(str(path) for path in self.root.rglob("*"))
        result = RESOLVER.resolve_roles(flow)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["errors"]), 8)
        self.assertEqual(result["role_paths"], {})
        self.assertEqual(before, sorted(str(path) for path in self.root.rglob("*")))

    def test_host_supplied_extra_root_is_used(self):
        flow = copy_skill("aiflow", self.root / "main")
        extra = self.root / "other-scope"
        copy_skill("aiflow-frontend", extra)
        result = RESOLVER.resolve_roles(flow, extra_roots=[extra], requested=["fe"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["role_paths"]["fe"], str((extra / "aiflow-frontend").resolve()))

    def test_mismatched_version_is_rejected(self):
        parent = self.installed_bundle()
        path = parent / "aiflow-backend" / "role.json"
        metadata = read_json(path)
        metadata["bundle_version"] = "0.0.0"
        write_json(path, metadata)
        result = RESOLVER.resolve_roles(parent / "aiflow")
        self.assertFalse(result["ok"])
        self.assertEqual(set(result["errors"]), {"be"})
        self.assertIn("version", result["errors"]["be"]["candidates"][0]["reason"])

    def test_missing_or_changed_resource_is_rejected(self):
        parent = self.installed_bundle()
        resource = parent / "aiflow-frontend" / "scripts" / "layout-check.js"
        resource.unlink()
        result = RESOLVER.resolve_roles(parent / "aiflow", requested=["fe"])
        self.assertFalse(result["ok"])
        resource.write_text("unexpected content", encoding="utf-8")
        result = RESOLVER.resolve_roles(parent / "aiflow", requested=["fe"])
        self.assertFalse(result["ok"])
        self.assertIn("resource differs", result["errors"]["fe"]["candidates"][0]["reason"])

    def test_malformed_metadata_does_not_crash_cli(self):
        flow = copy_skill("aiflow", self.root)
        role = copy_skill("aiflow-frontend", self.root)
        write_json(role / "role.json", [])
        result = subprocess.run([sys.executable, "-B", str(flow / "scripts" / "resolve_roles.py"),
                                 "--role", "fe"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertNotIn("Traceback", result.stderr)

    def test_unknown_role_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown role"):
            RESOLVER.resolve_roles(requested=["developer"])

    def test_cli_emits_utf8_for_installed_paths_with_non_ascii_characters(self):
        parent = self.root / "项目技能"
        flow = copy_skill("aiflow", parent)
        copy_skill("aiflow-frontend", parent)
        result = subprocess.run([sys.executable, "-B", str(flow / "scripts" / "resolve_roles.py"),
                                 "--role", "fe"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(data["role_paths"]["fe"], str((parent / "aiflow-frontend").resolve()))

    def test_shared_edit_is_detected_and_regenerated_without_rewriting_role_source(self):
        root = self.source_copy()
        BUNDLE.build(root)
        role = root / "skills" / "aiflow-frontend" / "SKILL.md"
        original = role.read_bytes()
        shared = root / "shared" / "role-execution.md"
        shared.write_text(shared.read_text(encoding="utf-8") + "\nUpdated fixture rule.\n", encoding="utf-8")
        changes = BUNDLE.build(root, check=True)
        self.assertIn("skills/aiflow-frontend/references/execution.md", changes)
        self.assertNotIn("skills/aiflow-frontend/SKILL.md", changes)
        BUNDLE.build(root)
        self.assertEqual(BUNDLE.build(root, check=True), [])
        self.assertEqual(role.read_bytes(), original)
        self.assertTrue(RESOLVER.resolve_roles(root / "skills" / "aiflow")["ok"])

    def test_resource_escape_is_rejected_before_any_output_is_written(self):
        root = self.source_copy()
        config = read_json(root / "aiflow.bundle.json")
        config["resources"]["common"]["LICENSE"] = "../../outside.txt"
        write_json(root / "aiflow.bundle.json", config)
        with self.assertRaisesRegex(ValueError, "outside"):
            BUNDLE.build(root)
        self.assertFalse((root / "plugin.json").exists())
        self.assertFalse((root / "skills" / "outside.txt").exists())

    def test_obsolete_generated_resource_is_removed_but_local_edits_are_preserved(self):
        root = self.source_copy()
        config_file = root / "aiflow.bundle.json"
        config = read_json(config_file)
        config["resources"]["extra"] = {"LICENSE": "references/old-license.txt"}
        config["roles"][0]["resources"].append("extra")
        write_json(config_file, config)
        BUNDLE.build(root)
        old = root / "skills" / "aiflow-analyst" / "references" / "old-license.txt"
        original = old.read_bytes()
        config["roles"][0]["resources"].remove("extra")
        write_json(config_file, config)
        old.write_text("hand edited", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Edited obsolete"):
            BUNDLE.build(root)
        self.assertEqual(old.read_text(encoding="utf-8"), "hand edited")
        old.write_bytes(original)
        self.assertTrue(any("obsolete" in line for line in BUNDLE.build(root, check=True)))
        BUNDLE.build(root)
        self.assertFalse(old.exists())

    def test_standalone_product_prototype_builds_without_main_skill(self):
        role = copy_skill("aiflow-product", self.root / "installed")
        prototype = self.root / "deliverable" / "prototype"
        shutil.copytree(role / "templates" / "prototype-kit", prototype)
        source = prototype / "_src" / "index.html"
        source.write_text('<!doctype html><html><head><link rel="stylesheet" href="kit.css">'
                          '</head><body><button class="btn primary">Create</button></body></html>',
                          encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(prototype / "build.py")],
                                capture_output=True, text=True, encoding="utf-8",
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        html = (prototype / "index.html").read_text(encoding="utf-8")
        self.assertIn("<style>", html)
        self.assertNotIn('href="kit.css"', html)
        self.assertFalse((self.root / ".aiflow").exists())


if __name__ == "__main__":
    unittest.main()
