"""一键工作流入口；自然语言规格由 Codex Agent 在暂停点补全。"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _profile(path: str | None) -> dict:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("profile 必须是 JSON 对象")
    for dependency in reversed(data.get("dependency_paths", [])):
        if not Path(dependency).is_dir():
            raise ValueError(f"依赖目录不存在：{dependency}")
        sys.path.insert(0, dependency)
    if data.get("allure"):
        os.environ["ALLURE_CLI"] = data["allure"]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), *data.get("dependency_paths", []),
                                                   os.environ.get("PYTHONPATH", "")])
    return data


def _save_config(path: Path, info: dict, app: dict) -> None:
    import yaml
    data = {"server": {"url": info["appium_url"]},
            "devices": {"selected": {"platformName": "Android", "automationName": "UiAutomator2",
                                     "deviceName": info["device_serial"], "udid": info["device_serial"]}},
            "apps": {"target": {"appPackage": app["package"], "appActivity": app["activity"]}},
            "common": {"noReset": True, "newCommandTimeout": 120}}
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _prepare(args: argparse.Namespace, profile: dict) -> Path:
    from android_appium_test.app_discovery import capture_ui, discover_app
    from android_appium_test.case_input import is_structured_spec, read_case_input
    from android_appium_test.environment import prepare_environment, run_command
    from android_appium_test.startup_diagnostics import diagnose_startup

    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_dir.mkdir()
    evidence = run_dir / "evidence"
    info = prepare_environment(profile, evidence)
    app = discover_app(info["adb"], info["device_serial"], args.app, profile.get("aapt"))
    if app["apk"]:
        # 仅在目标尚未安装时安装用户提供的 APK；不覆盖既有安装与数据。
        packages = run_command([info["adb"], "-s", info["device_serial"], "shell", "pm", "list", "packages", app["package"]])
        if f"package:{app['package']}" not in packages.splitlines():
            run_command([info["adb"], "-s", info["device_serial"], "install", app["apk"]], timeout=120)
    run_command([info["adb"], "-s", info["device_serial"], "shell", "am", "start", "-n",
                 f"{app['package']}/{app['activity']}"], timeout=30)
    initial = capture_ui(info["adb"], info["device_serial"], evidence, "initial")
    def target_visible(capture: dict) -> bool:
        # XML 的 package 属性来自设备；不能以截图或启动命令成功推断 App 已在前台。
        return any(node.attrib.get("package") == app["package"]
                   for node in ET.parse(capture["xml"]).iter("node"))

    for attempt in range(2):
        if target_visible(initial):
            break
        time.sleep(3)
        initial = capture_ui(info["adb"], info["device_serial"], evidence, f"startup_wait_{attempt + 1}")
    diagnosis = None
    if not target_visible(initial):
        diagnosis = diagnose_startup(info["adb"], info["device_serial"], app["package"],
                                     evidence / "startup-diagnosis")
    (run_dir / "app.json").write_text(json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8")
    _save_config(run_dir / "config.yaml", info, app)
    case_text = read_case_input(args.cases)
    (run_dir / "cases-source.txt").write_text(case_text, encoding="utf-8")
    manifest = {"app": args.app, "cases": str(Path(args.cases).resolve()), "created_at": datetime.now().astimezone().isoformat(),
                "stage": "needs_agent" if not is_structured_spec(args.cases) else "ready", "device_serial": info["device_serial"]}
    if diagnosis:
        manifest["startup_diagnosis"] = str(evidence / "startup-diagnosis" / "startup-diagnosis.json")
        if diagnosis["classification"] in {"incompatible_android_version", "app_crash", "adb_launch_error"}:
            manifest["stage"] = "startup_blocked"
    (run_dir / "workflow.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def _execute(run_dir: Path, spec: Path, open_report: bool) -> int:
    from android_appium_test.casegen import generate
    from android_appium_test.runner import run_project

    if not (run_dir / "workflow.json").is_file():
        raise ValueError(f"无准备记录：{run_dir}")
    existing = json.loads((run_dir / "workflow.json").read_text(encoding="utf-8"))
    if existing.get("stage") == "startup_blocked":
        raise ValueError(f"ADB 启动诊断已确认阻塞，先解决原因：{existing.get('startup_diagnosis')}")
    attempt = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    project = run_dir / f"generated-project-{attempt}"
    generate(spec, project)
    code, result_dir = run_project(project, run_dir / "config.yaml", "selected", "target", run_dir / "runs")
    workflow = json.loads((run_dir / "workflow.json").read_text(encoding="utf-8"))
    if workflow.get("result_dir") and not workflow.get("attempts"):
        workflow["attempts"] = [{"at": "initial", "spec": workflow.get("spec"),
                                  "result_dir": workflow["result_dir"], "exit_code": workflow.get("exit_code")}]
    workflow.setdefault("attempts", []).append({"at": attempt, "spec": str(spec.resolve()),
                                                   "project": str(project), "result_dir": str(result_dir), "exit_code": code})
    workflow.update({"stage": "executed", "spec": str(spec.resolve()), "result_dir": str(result_dir), "exit_code": code})
    (run_dir / "workflow.json").write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = json.loads((result_dir / "run-summary.json").read_text(encoding="utf-8"))
    print(json.dumps({"run_dir": str(run_dir), "result_dir": str(result_dir), **summary}, ensure_ascii=False, indent=2))
    if open_report and summary["report_generated"]:
        try:
            _open_report(result_dir)
        except OSError as exc:
            print(f"报告已生成但未能自动打开：{exc}", file=sys.stderr)
    return code


def _open_report(result_dir: Path) -> None:
    """本机 HTTP 服务打开 Allure，避免 file:// 下的资源读取限制。"""
    import time
    import urllib.request
    import webbrowser

    report = result_dir / "allure-report"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = (result_dir / "report-server.log").open("ab")
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                                    "--directory", str(report)], stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=flags)
    finally:
        log.close()
    url = f"http://127.0.0.1:{port}/"
    for _ in range(20):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(.2)
    else:
        raise OSError("Allure 报告服务未就绪")
    (result_dir / "report-server.json").write_text(json.dumps({"url": url, "pid": process.pid}, indent=2), encoding="utf-8")
    webbrowser.open(url)
    print(f"Allure 报告已打开：{url}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Android UI 自动化工作流")
    parser.add_argument("--app", help="APK 文件路径、已安装包名或 settings")
    parser.add_argument("--cases", help="自然语言、Markdown、Word、Excel 或结构化规格文件")
    parser.add_argument("--output", default="android-test-runs", help="本次运行根目录")
    parser.add_argument("--profile", help="本机可复用环境路径配置 JSON")
    parser.add_argument("--resume", help="恢复准备阶段生成的运行目录")
    parser.add_argument("--spec", help="由 Agent 核对 UI 证据后写出的规格 JSON/YAML")
    parser.add_argument("--open-report", action="store_true")
    args = parser.parse_args()
    if not args.resume and (not args.app or not args.cases):
        parser.error("首次运行必须提供 --app 和 --cases")
    if args.resume and not args.spec:
        parser.error("恢复执行必须提供 --spec")
    try:
        profile = _profile(args.profile)
        if args.resume:
            return _execute(Path(args.resume).resolve(), Path(args.spec).resolve(), args.open_report)
        run_dir = _prepare(args, profile)
        workflow = json.loads((run_dir / "workflow.json").read_text(encoding="utf-8"))
        if workflow["stage"] == "startup_blocked":
            print(json.dumps({"stage": "startup_blocked", "run_dir": str(run_dir),
                              "startup_diagnosis": workflow["startup_diagnosis"]}, ensure_ascii=False, indent=2))
            return 2
        if args.spec:
            return _execute(run_dir, Path(args.spec).resolve(), args.open_report)
        from android_appium_test.case_input import is_structured_spec
        if is_structured_spec(args.cases):
            return _execute(run_dir, Path(args.cases).resolve(), args.open_report)
        print(json.dumps({"stage": "needs_agent", "run_dir": str(run_dir),
                          "instructions": "Codex 读取 cases-source.txt 与 evidence/initial.xml，按真实页面逐屏取证，写出 spec.json，再以 --resume --spec 执行。"}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"运行中止：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
