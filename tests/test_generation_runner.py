from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from android_appium_test.casegen import generate
from android_appium_test.config import ConfigError
from android_appium_test.runner import run_project
from test_core import make_config


def make_spec(tmp_path: Path) -> Path:
    spec = {
        "features": [{
            "key": "sign_in", "name": "登录", "locators": {
                "account": ["id", "org.example:id/account"],
                "submit": ["id", "org.example:id/submit"],
                "message": ["id", "org.example:id/message"],
            },
            "scenarios": [
                {"name": "正确输入", "category": "normal", "objective": "完成登录", "preconditions": ["应用已启动"],
                 "steps": [{"action": "type", "target": "account", "value": "demo"}, {"action": "tap", "target": "submit"}],
                 "expected": [{"check": "text_contains", "target": "message", "value": "欢迎"}]},
                {"name": "空输入", "category": "boundary", "objective": "验证必填项", "preconditions": ["应用已启动"],
                 "steps": [{"action": "tap", "target": "submit"}],
                 "expected": [{"check": "visible", "target": "message"}]},
            ],
        }]
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return path


def test_generation_produces_reviewable_unexecuted_cases(tmp_path):
    output = tmp_path / "generated"
    cases = generate(make_spec(tmp_path), output)
    assert [case["id"] for case in cases] == ["SIGN_IN-001", "SIGN_IN-002"]
    assert all(case["status"] == "not_run" and case["actual_result"] is None for case in cases)
    assert cases[0]["expected"][0]["value"] == "欢迎"
    for python_file in output.rglob("*.py"):
        ast.parse(python_file.read_text(encoding="utf-8"), filename=str(python_file))
    with pytest.raises(ConfigError, match="拒绝覆盖"):
        generate(tmp_path / "spec.json", output)


def test_generation_rejects_missing_expected(tmp_path):
    path = make_spec(tmp_path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["features"][0]["scenarios"][0]["expected"] = []
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "invalid"
    with pytest.raises(ConfigError, match="expected"):
        generate(path, output)
    assert not output.exists()


def test_runner_preserves_failure_and_does_not_claim_report(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    config = make_config(tmp_path, monkeypatch)
    monkeypatch.setattr("android_appium_test.runner.importlib.util.find_spec", lambda name: object())
    monkeypatch.setattr("android_appium_test.runner.shutil.which", lambda name: None)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("android_appium_test.runner.subprocess.run", fake_run)
    code, output = run_project(project, config, "local", "demo", tmp_path / "runs")
    summary = json.loads((output / "run-summary.json").read_text(encoding="utf-8"))
    assert code == 1 and summary["pytest_exit_code"] == 1
    assert summary["result_files"] == 0 and summary["report_generated"] is False
    assert len(commands) == 1 and commands[0][2] == "pytest"


def test_runner_only_marks_html_generated_when_file_exists(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    config = make_config(tmp_path, monkeypatch)
    monkeypatch.setattr("android_appium_test.runner.importlib.util.find_spec", lambda name: object())
    monkeypatch.setattr("android_appium_test.runner.shutil.which", lambda name: "allure")

    def fake_run(command, **kwargs):
        if "pytest" in command:
            raw = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--alluredir=")))
            raw.mkdir()
            (raw / "real-result.json").write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("android_appium_test.runner.subprocess.run", fake_run)
    code, output = run_project(project, config, "local", "demo", tmp_path / "runs")
    summary = json.loads((output / "run-summary.json").read_text(encoding="utf-8"))
    assert code == 3 and summary["pytest_exit_code"] == 0 and summary["result_files"] == 1
    assert summary["report_exit_code"] == 0 and summary["report_generated"] is False


def test_runner_maps_only_observed_case_results(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    (project / "case_catalog.json").write_text(json.dumps([
        {"id": "AUTH-001", "status": "not_run", "actual_result": None},
        {"id": "AUTH-002", "status": "not_run", "actual_result": None},
    ]), encoding="utf-8")
    config = make_config(tmp_path, monkeypatch)
    monkeypatch.setattr("android_appium_test.runner.importlib.util.find_spec", lambda name: object())
    monkeypatch.setattr("android_appium_test.runner.shutil.which", lambda name: None)

    def fake_run(command, **kwargs):
        raw = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--alluredir=")))
        raw.mkdir()
        (raw / "observed-result.json").write_text(json.dumps({
            "name": "test_scenario[AUTH-001]", "status": "failed",
            "statusDetails": {"message": "断言失败"},
        }), encoding="utf-8")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("android_appium_test.runner.subprocess.run", fake_run)
    _, output = run_project(project, config, "local", "demo", tmp_path / "runs")
    cases = json.loads((output / "case_results.json").read_text(encoding="utf-8"))
    assert cases[0]["status"] == "failed" and cases[0]["actual_result"]["message"] == "断言失败"
    assert cases[1]["status"] == "not_run" and cases[1]["actual_result"] is None
