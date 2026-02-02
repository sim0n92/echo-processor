"""Basic tests for echo-processor"""
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_manifest_exists():
    """Verify manifest.json exists and is valid"""
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'manifest.json')
    assert os.path.exists(manifest_path), "manifest.json must exist"

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Check required fields (per spec v1.0)
    assert manifest.get("specVersion") == "1.0"
    assert manifest.get("name") == "echo-processor"
    assert "version" in manifest
    assert "description" in manifest
    assert "input" in manifest


def test_manifest_name_format():
    """Name must be kebab-case [a-z0-9-]+"""
    import re
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'manifest.json')

    with open(manifest_path) as f:
        manifest = json.load(f)

    name = manifest.get("name")
    assert re.match(r'^[a-z0-9-]+$', name), f"Name '{name}' must be kebab-case"


def test_manifest_version_semver():
    """Version must be valid SemVer"""
    import re
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'manifest.json')

    with open(manifest_path) as f:
        manifest = json.load(f)

    version = manifest.get("version")
    assert re.match(r'^\d+\.\d+\.\d+$', version), f"Version '{version}' must be SemVer"
