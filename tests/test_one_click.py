"""一键流程的纯逻辑验证，不把模拟结果当作设备验收。"""

from __future__ import annotations

import ast
import json

import pytest

from android_appium_test.app_discovery import parse_badging
from android_appium_test.case_input import is_structured_spec, read_case_input
from android_appium_test.casegen import generate
from android_appium_test.config import ConfigError
from android_appium_test.environment import select_device


def test_device_selection_requires_unambiguous_ready_device():
    assert select_device({"emulator-1": "device"}) == "emulator-1"
    assert select_device({"a": "device", "b": "device"}, "b") == "b"
    with pytest.raises(ConfigError, match="需要指定"):
        select_device({"a": "device", "b": "device"})
    with pytest.raises(ConfigError, match="不可用"):
        select_device({"a": "offline"}, "a")


def test_apk_manifest_parser_never_invents_activity():
    output = "package: name='example.app' versionCode='1'\nlaunchable-activity: name='example.app.Main'\n"
    assert parse_badging(output) == ("example.app", "example.app.Main")
    with pytest.raises(ConfigError, match="启动 Activity"):
        parse_badging("package: name='example.app'\n")


def test_natural_language_is_not_treated_as_structured_spec(tmp_path):
    prose = tmp_path / "case.md"
    prose.write_text("打开设置，进入显示，然后返回并验证首页。", encoding="utf-8")
    assert read_case_input(prose).startswith("打开设置")
    assert not is_structured_spec(prose)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"features": []}), encoding="utf-8")
    assert is_structured_spec(spec)


def test_generated_case_keeps_midflow_assertion(tmp_path):
    spec = {"features": [{"key": "navigation", "name": "导航", "locators": {
        "menu": ["id", "sample:id/menu"], "detail": ["id", "sample:id/detail"]},
        "scenarios": [{"name": "往返", "objective": "进入并返回", "category": "normal", "preconditions": [],
                       "steps": [{"action": "tap", "target": "menu"},
                                 {"action": "assert", "check": "visible", "target": "detail"},
                                 {"action": "back"}],
                       "expected": [{"check": "visible", "target": "menu"}]}]}]}
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    project = tmp_path / "generated"
    generate(source, project)
    test_code = (project / "tests" / "test_navigation.py").read_text(encoding="utf-8")
    ast.parse(test_code)
    assert "elif action == 'assert'" in test_code
    assert "failure-screenshot" in (project / "conftest.py").read_text(encoding="utf-8")
