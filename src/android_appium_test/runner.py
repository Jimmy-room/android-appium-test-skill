"""Pytest 与 Allure 的执行编排，保留真实退出状态。"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import ConfigError, load_config


def _write_case_results(project: Path, raw: Path, output: Path) -> int:
    """将真实 Allure 状态映射回用例；无结果保持 not_run。"""
    catalog_path = project / "case_catalog.json"
    if not catalog_path.is_file():
        return 0
    cases = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in cases}
    matched = 0
    results = sorted(raw.glob("*-result.json"), key=lambda path: path.stat().st_mtime) if raw.exists() else []
    for path in results:
        result = json.loads(path.read_text(encoding="utf-8"))
        labels = result.get("labels", [])
        case_id = next((label.get("value") for label in labels if label.get("name") == "as_id"), None)
        if case_id not in by_id:
            name = result.get("name", "")
            case_id = next((key for key in by_id if re.search(r"\[" + re.escape(key) + r"\]", name)), None)
        if case_id in by_id:
            status = result.get("status", "unknown")
            by_id[case_id]["status"] = status
            by_id[case_id]["actual_result"] = {
                "status": status,
                "message": result.get("statusDetails", {}).get("message"),
            }
            matched += 1
    (output / "case_results.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return matched


def run_project(
    project_dir: str | Path,
    config_path: str | Path,
    device_key: str,
    app_key: str,
    output_root: str | Path,
) -> tuple[int, Path]:
    """执行真实测试，失败也归档原始结果，并返回 Pytest 退出码。"""
    project = Path(project_dir).resolve()
    if not (project / "tests").is_dir():
        raise ConfigError(f"缺少 tests 目录：{project}")
    config = Path(config_path).resolve()
    loaded = load_config(config)
    loaded.capabilities(device_key, app_key)
    if importlib.util.find_spec("allure_pytest") is None:
        raise ConfigError("当前 Python 缺少 allure-pytest，请先安装 Skill 依赖")
    output = Path(output_root).resolve() / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "allure-results"
    html = output / "allure-report"
    artifacts = output / "artifacts"
    capabilities = loaded.capabilities(device_key, app_key)
    environment = os.environ.copy()
    environment.update({
        "ANDROID_TEST_CONFIG": str(config),
        "ANDROID_TEST_DEVICE": device_key,
        "ANDROID_TEST_APP": app_key,
        "ANDROID_TEST_ARTIFACT_DIR": str(artifacts),
    })
    skill_src = str(Path(__file__).resolve().parents[1])
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(project), skill_src, environment.get("PYTHONPATH", "")) if value
    )
    # 使用参数数组，不经 shell 拼接；Pytest 的真实退出码是运行状态依据。
    command = [sys.executable, "-m", "pytest", "tests", f"--alluredir={raw}", "-v"]
    with (output / "pytest.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=project, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False)
    raw.mkdir(exist_ok=True)
    (raw / "environment.properties").write_text(
        "\n".join(f"{key}={value}" for key, value in {
            "device": capabilities.get("udid", capabilities["deviceName"]),
            "app.package": capabilities.get("appPackage", ""),
            "app.activity": capabilities.get("appActivity", ""),
            "appium.url": loaded.server_url,
            "python": sys.version.split()[0],
        }.items()) + "\n", encoding="utf-8")
    raw_results = list(raw.glob("*-result.json")) if raw.exists() else []
    matched = _write_case_results(project, raw, output)
    configured_allure = os.environ.get("ALLURE_CLI")
    allure = configured_allure if configured_allure and Path(configured_allure).is_file() else shutil.which("allure")
    report_code: int | None = None
    if raw_results and allure:
        with (output / "allure-generate.log").open("w", encoding="utf-8") as log:
            report = subprocess.run(
                [allure, "generate", str(raw), "-o", str(html)],
                cwd=project, stdout=log, stderr=subprocess.STDOUT, check=False,
            )
        report_code = report.returncode
    report_generated = report_code == 0 and (html / "index.html").is_file()
    report_failure = report_code if report_code else (3 if report_code == 0 and not report_generated else 4 if raw_results and not allure else 0)
    overall_code = result.returncode if result.returncode else report_failure
    counts = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "unknown": 0}
    for result_path in raw_results:
        result_data = json.loads(result_path.read_text(encoding="utf-8"))
        state = result_data.get("status", "unknown")
        counts[state if state in counts else "unknown"] += 1
    status = {
        "started_at": datetime.fromtimestamp(output.stat().st_ctime).astimezone().isoformat(),
        "finished_at": datetime.now().astimezone().isoformat(),
        "device": capabilities.get("udid", capabilities["deviceName"]),
        "app_package": capabilities.get("appPackage"),
        "pytest_command": command,
        "counts": counts,
        "pytest_exit_code": result.returncode,
        "overall_exit_code": overall_code,
        "result_files": len(raw_results),
        "matched_case_results": matched,
        "allure_cli_found": bool(allure),
        "report_exit_code": report_code,
        "report_generated": report_generated,
        "raw_results": str(raw),
        "html_report": str(html) if report_generated else None,
    }
    (output / "run-summary.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return overall_code, output
