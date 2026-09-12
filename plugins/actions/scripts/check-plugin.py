#!/usr/bin/env python3
"""Validate the Agent Plugins 1.0 package and marketplace registration."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent.parent
MANIFEST_PATH = PLUGIN_ROOT / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".github/plugin/marketplace.json"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
ALLOWED_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
REQUIRED_SKILLS = {
    "actions-workflow-toolkit",
    "actions-optimization",
    "actions-security-review",
    "actions-architecture-review",
}
NAME = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?$")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"{path.relative_to(REPO_ROOT)}: invalid JSON: {exc}")
    if not isinstance(value, dict):
        sys.exit(f"{path.relative_to(REPO_ROOT)}: root must be an object")
    return value


def validate_manifest() -> dict:
    manifest = load_json(MANIFEST_PATH)
    unknown = set(manifest) - ALLOWED_FIELDS
    if unknown:
        sys.exit(f"plugin.json: unsupported Agent Plugins fields: {sorted(unknown)}")
    if manifest.get("$schema") != SCHEMA:
        sys.exit(f"plugin.json: $schema must be {SCHEMA}")

    name = manifest.get("name")
    if (
        not isinstance(name, str)
        or not NAME.fullmatch(name)
        or "--" in name
        or ".." in name
    ):
        sys.exit("plugin.json: name violates Agent Plugins 1.0 constraints")

    if not isinstance(manifest.get("version"), str):
        sys.exit("plugin.json: version must be a string")
    if not isinstance(manifest.get("description"), str):
        sys.exit("plugin.json: description must be a string")
    if not isinstance(manifest.get("keywords"), list) or not all(
        isinstance(keyword, str) for keyword in manifest["keywords"]
    ):
        sys.exit("plugin.json: keywords must be an array of strings")

    author = manifest.get("author")
    if not isinstance(author, dict) or set(author) - {"name", "email", "url"}:
        sys.exit("plugin.json: author must use only name, email, and url")
    if not all(isinstance(value, str) for value in author.values()):
        sys.exit("plugin.json: author values must be strings")

    print("ok    Agent Plugins 1.0 manifest")
    return manifest


def validate_package_paths() -> None:
    root = PLUGIN_ROOT.resolve()
    symlinks = []
    escapes = []

    for current, directories, files in os.walk(PLUGIN_ROOT, followlinks=False):
        for name in [*directories, *files]:
            path = Path(current) / name
            if path.is_symlink():
                symlinks.append(path.relative_to(PLUGIN_ROOT))
            try:
                path.resolve().relative_to(root)
            except ValueError:
                escapes.append(path.relative_to(PLUGIN_ROOT))

    if escapes:
        sys.exit(f"plugin package paths escape the plugin root: {escapes}")
    if symlinks:
        sys.exit(f"plugin package must use real files, not symlinks: {symlinks}")

    skills = {
        path.parent.name
        for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")
        if path.is_file()
    }
    if skills != REQUIRED_SKILLS:
        sys.exit(
            "plugin skills mismatch: "
            f"expected {sorted(REQUIRED_SKILLS)}, found {sorted(skills)}"
        )

    print("ok    self-contained package paths and four fixed-location skills")


def validate_marketplace(manifest: dict) -> None:
    marketplace = load_json(MARKETPLACE_PATH)
    if marketplace.get("name") != "austenstone":
        sys.exit("marketplace.json: marketplace name must be austenstone")

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        sys.exit("marketplace.json: plugins must be an array")

    matches = [
        plugin
        for plugin in plugins
        if isinstance(plugin, dict) and plugin.get("name") == manifest["name"]
    ]
    if len(matches) != 1:
        sys.exit("marketplace.json: expected exactly one actions plugin entry")

    entry = matches[0]
    if entry.get("source") != "plugins/actions":
        sys.exit("marketplace.json: actions source must be plugins/actions")
    if entry.get("version") != manifest["version"]:
        sys.exit("marketplace.json: actions version must match plugin.json")
    if entry.get("description") != manifest["description"]:
        sys.exit("marketplace.json: actions description must match plugin.json")

    print("ok    marketplace registration matches the plugin manifest")


def main() -> None:
    manifest = validate_manifest()
    validate_package_paths()
    validate_marketplace(manifest)
    print("\nplugin package validation passed")


if __name__ == "__main__":
    main()
