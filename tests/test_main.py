"""Basic tests for echo-processor"""
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), '..', 'manifest.json')


def _load_manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def test_manifest_exists():
    """Verify manifest.json exists and is valid"""
    assert os.path.exists(MANIFEST_PATH), "manifest.json must exist"

    manifest = _load_manifest()

    # Check required fields (per spec v1.0)
    assert manifest.get("specVersion") == "1.0"
    assert manifest.get("name") == "echo-processor"
    assert "version" in manifest
    assert "description" in manifest
    assert "actions" in manifest


def test_manifest_name_format():
    """Name must be kebab-case [a-z0-9-]+"""
    import re

    manifest = _load_manifest()
    name = manifest.get("name")
    assert re.match(r'^[a-z0-9-]+$', name), f"Name '{name}' must be kebab-case"


def test_manifest_version_semver():
    """Version must be valid SemVer"""
    import re

    manifest = _load_manifest()
    version = manifest.get("version")
    assert re.match(r'^\d+\.\d+\.\d+$', version), f"Version '{version}' must be SemVer"


def test_manifest_version_is_2_1():
    """Version must be 2.1.0 for actions protocol with callback support"""
    manifest = _load_manifest()
    assert manifest.get("version") == "2.1.0"


def test_manifest_has_execute_action():
    """Manifest must define execute action with required message input"""
    manifest = _load_manifest()
    actions = manifest.get("actions", {})
    assert "execute" in actions, "actions must contain 'execute'"

    execute = actions["execute"]
    assert "description" in execute
    assert "input" in execute

    # execute.input must require 'message'
    execute_input = execute["input"]
    assert "message" in execute_input.get("properties", {}), "execute input must have 'message' property"
    assert "message" in execute_input.get("required", []), "execute input must require 'message'"

    # Must have minRunSeconds property
    assert "minRunSeconds" in execute_input.get("properties", {}), "execute input must have 'minRunSeconds' property"


def test_manifest_has_terminate_action():
    """Manifest must define terminate action with cleaned output"""
    manifest = _load_manifest()
    actions = manifest.get("actions", {})
    assert "terminate" in actions, "actions must contain 'terminate'"

    terminate = actions["terminate"]
    assert "description" in terminate
    assert "input" in terminate
    assert "output" in terminate

    # terminate.output must have 'cleaned' boolean
    terminate_output = terminate["output"]
    assert "cleaned" in terminate_output.get("properties", {}), "terminate output must have 'cleaned' property"


def test_manifest_execute_requires_message():
    """Execute action input must require 'message' field"""
    manifest = _load_manifest()
    execute_input = manifest["actions"]["execute"]["input"]
    assert "message" in execute_input.get("required", [])
