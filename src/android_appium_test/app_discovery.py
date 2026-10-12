"""从 APK、设备包管理器与真实 UI 层级收集 App 证据。"""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import ConfigError
from .environment import executable, run_command


def parse_badging(output: str) -> tuple[str, str]:
    """解析 aapt 的真实包名与启动 Activity。"""
    package = re.search(r"^package: name='([^']+)'", output, re.MULTILINE)
    activity = re.search(r"^launchable-activity: name='([^']+)'", output, re.MULTILINE)
    if not package or not activity:
        raise ConfigError("APK 未提供可解析的包名和启动 Activity")
    return package.group(1), activity.group(1)


def resolve_installed(adb: str, serial: str, app: str) -> tuple[str, str]:
    """支持包名，或 Android 系统设置这一明确标识；拒绝猜测应用名称。"""
    if app.lower() in {"settings", "android.settings", "系统设置", "设置"}:
        output = run_command([adb, "-s", serial, "shell", "cmd", "package", "resolve-activity", "--brief",
                              "-a", "android.settings.SETTINGS"])
        components = re.findall(r"([\w.]+/[\w.$]+)", output)
        if not components:
            raise ConfigError("设备未返回系统设置的启动组件")
        package, activity = components[-1].split("/", 1)
        return package, activity
    if not re.fullmatch(r"[A-Za-z][\w]*(?:\.[A-Za-z][\w]*)+", app):
        raise ConfigError("已安装 App 请提供真实包名；无法从名称安全推断")
    packages = run_command([adb, "-s", serial, "shell", "pm", "list", "packages", app])
    if f"package:{app}" not in packages.splitlines():
        raise ConfigError(f"设备未安装 App：{app}")
    output = run_command([adb, "-s", serial, "shell", "cmd", "package", "resolve-activity", "--brief",
                          "-c", "android.intent.category.LAUNCHER", "-p", app])
    components = re.findall(r"([\w.]+/[\w.$]+)", output)
    if not components or components[-1].split("/", 1)[0] != app:
        raise ConfigError(f"无法确认 {app} 的启动 Activity；请提供可启动组件")
    return components[-1].split("/", 1)


def discover_app(adb: str, serial: str, app: str, aapt: str | None = None) -> dict:
    candidate = Path(app)
    if candidate.suffix.lower() == ".apk":
        if not candidate.is_file():
            raise ConfigError(f"APK 不存在：{candidate}")
        aapt_cmd = executable("aapt", aapt)
        if not aapt_cmd:
            raise ConfigError("缺少 aapt，无法验证 APK 包名与 Activity")
        package, activity = parse_badging(run_command([aapt_cmd, "dump", "badging", str(candidate)]))
        return {"package": package, "activity": activity, "apk": str(candidate.resolve())}
    package, activity = resolve_installed(adb, serial, app)
    return {"package": package, "activity": activity, "apk": None}


def capture_ui(adb: str, serial: str, evidence_dir: Path, label: str = "current") -> dict:
    """保留原始 XML、截图与属性摘要；定位符必须由这些证据确定。"""
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", label):
        raise ConfigError("UI 证据名称无效")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    remote = f"/sdcard/window-{label}.xml"
    run_command([adb, "-s", serial, "shell", "uiautomator", "dump", remote], timeout=30)
    xml = run_command([adb, "-s", serial, "shell", "cat", remote], timeout=30)
    xml_path = evidence_dir / f"{label}.xml"
    xml_path.write_text(xml, encoding="utf-8")
    screenshot = evidence_dir / f"{label}.png"
    with screenshot.open("wb") as image:
        result = subprocess.run([adb, "-s", serial, "exec-out", "screencap", "-p"],
                                stdout=image, stderr=subprocess.PIPE, timeout=30)
    if result.returncode or screenshot.stat().st_size == 0:
        raise ConfigError("ADB 截图失败")
    nodes = []
    for node in ET.fromstring(xml).iter("node"):
        attrs = {key: node.attrib.get(key, "") for key in
                 ("text", "resource-id", "content-desc", "class", "clickable", "bounds")}
        if any(attrs[key] for key in ("text", "resource-id", "content-desc")):
            nodes.append(attrs)
    summary = {"xml": str(xml_path), "screenshot": str(screenshot), "nodes": nodes}
    (evidence_dir / f"{label}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
