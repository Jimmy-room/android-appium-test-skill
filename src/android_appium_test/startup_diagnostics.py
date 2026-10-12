"""用 ADB 独立复现 App 启动问题，并保留可核对的设备日志。"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .app_discovery import resolve_installed
from .environment import run_command


def parse_package_requirements(package_dump: str) -> dict:
    """从设备包管理器输出提取版本和最低 Android API。"""
    result: dict = {}
    for key in ("versionCode", "minSdk", "targetSdk"):
        match = re.search(rf"\b{key}=(\d+)", package_dump)
        if match:
            result[key] = int(match.group(1))
    match = re.search(r"\bversionName=([^\s]+)", package_dump)
    if match:
        result["versionName"] = match.group(1)
    return result


def classify_startup(device_api: int, requirements: dict, log: str, foreground: str,
                     package: str, launch_error: str | None = None) -> str:
    """证据优先；前台仅说明状态，不能覆盖已观察到的崩溃。"""
    if requirements.get("minSdk", 0) > device_api:
        return "incompatible_android_version"
    if re.search(r"FATAL EXCEPTION[\s\S]{0,500}Process: " + re.escape(package) + r"\b", log):
        return "app_crash"
    if launch_error:
        return "adb_launch_error"
    if package in foreground:
        return "foreground_unverified"
    return "not_foreground"


def diagnose_startup(adb: str, serial: str, package: str, output_dir: Path,
                     wait_seconds: float = 3) -> dict:
    """不依赖 Appium；不清数据、不重装、不清空 Logcat。"""
    if not re.fullmatch(r"[A-Za-z][\w]*(?:\.[A-Za-z][\w]*)+", package):
        raise ValueError("诊断需要真实 Android 包名")
    output_dir.mkdir(parents=True, exist_ok=True)
    base = [adb, "-s", serial]
    resolved_package, activity = resolve_installed(adb, serial, package)
    device_api = int(run_command(base + ["shell", "getprop", "ro.build.version.sdk"]).strip())
    requirements = parse_package_requirements(run_command(base + ["shell", "dumpsys", "package", package]))
    marker = f"STARTUP_DIAG_{uuid4().hex}"
    run_command(base + ["shell", "log", "-t", "CODEX_STARTUP_DIAG", marker])
    started_at = datetime.now().astimezone().isoformat()
    command = base + ["shell", "am", "start", "-n", f"{resolved_package}/{activity}"]
    launch_error = None
    try:
        launch_output = run_command(command, timeout=30).strip()
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        launch_output = ""
        launch_error = str(exc)
    time.sleep(wait_seconds)
    foreground = run_command(base + ["shell", "dumpsys", "window", "windows"])
    # 保留原始日志，并用唯一标记隔离本次启动；绝不执行 logcat -c。
    raw_log = run_command(base + ["logcat", "-d", "-t", "4000"], timeout=45)
    marker_position = raw_log.rfind(marker)
    launch_log = raw_log[marker_position:] if marker_position >= 0 else raw_log
    log_path = output_dir / "adb-startup-logcat.txt"
    log_path.write_text(launch_log, encoding="utf-8")
    focus_lines = [line.strip() for line in foreground.splitlines()
                   if "mCurrentFocus=" in line or "mFocusedApp=" in line]
    relevant = [line for line in launch_log.splitlines() if any(token in line for token in
                ("FATAL EXCEPTION", "AndroidRuntime", "ActivityManager", "ActivityTaskManager", "CODEX_STARTUP_DIAG"))]
    result = {
        "started_at": started_at, "device_serial": serial, "package": package,
        "resolved_activity": activity, "device_api": device_api,
        "package_requirements": requirements, "adb_command": command,
        "adb_launch_output": launch_output, "adb_launch_error": launch_error,
        "foreground": focus_lines, "log_marker_found": marker_position >= 0,
        "classification": classify_startup(device_api, requirements, launch_log,
                                           "\n".join(focus_lines), package, launch_error),
        "relevant_log_lines": relevant[:100], "logcat_path": str(log_path),
    }
    (output_dir / "startup-diagnosis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
