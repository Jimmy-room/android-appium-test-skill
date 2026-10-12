"""只读检查运行环境；仅启动已有的模拟器和 Appium 服务。"""

from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .config import ConfigError


def executable(name: str, configured: str | None = None) -> str | None:
    """优先使用用户保存的路径，然后检查 PATH。"""
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
    return shutil.which(name)


def run_command(argv: list[str], timeout: int = 30) -> str:
    """参数数组执行命令，不经 shell 插值。"""
    result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    if result.returncode:
        raise ConfigError(f"命令失败 ({result.returncode})：{argv[0]} {result.stderr.strip() or result.stdout.strip()}")
    # 部分 CLI（Appium driver list）把正常列表写入 stderr。
    return result.stdout or result.stderr


def connected_devices(adb: str) -> dict[str, str]:
    """仅接受 ADB 明确报告为 device 的目标。"""
    devices: dict[str, str] = {}
    for line in run_command([adb, "devices"]).splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2:
            devices[fields[0]] = fields[1]
    return devices


def select_device(devices: dict[str, str], preferred: str | None = None) -> str:
    ready = [serial for serial, state in devices.items() if state == "device"]
    if preferred:
        if preferred not in ready:
            raise ConfigError(f"默认设备 {preferred} 当前不可用；ADB 状态：{devices}")
        return preferred
    if len(ready) != 1:
        raise ConfigError(f"需要指定唯一可用设备；ADB 状态：{devices}")
    return ready[0]


def appium_ready(url: str) -> bool:
    """通过 /status 确认服务明确返回 ready。"""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/status", timeout=3) as response:
            payload = json.load(response)
        return bool(payload.get("value", {}).get("ready"))
    except (OSError, ValueError, KeyError):
        return False


def start_appium(command: str, url: str, log_path: Path) -> int:
    """启动已安装的服务，保存 PID 与日志；不修改系统配置。"""
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ConfigError("自动启动 Appium 仅支持本机服务")
    if appium_ready(url):
        return 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = log_path.open("ab")
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen([command, "--address", "127.0.0.1", "--port", str(parsed.port or 4723)],
                                   stdout=stream, stderr=subprocess.STDOUT, creationflags=flags)
    finally:
        stream.close()
    for _ in range(30):
        if appium_ready(url):
            return process.pid
        if process.poll() is not None:
            break
        time.sleep(1)
    raise ConfigError(f"Appium 未能启动；日志：{log_path}")


def prepare_environment(profile: dict, evidence_dir: Path) -> dict:
    """检查依赖、发现设备，必要时启动已有 LDPlayer 和 Appium。"""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    adb = executable("adb", profile.get("adb"))
    appium = executable("appium", profile.get("appium"))
    allure = executable("allure", profile.get("allure"))
    ldconsole = executable("ldconsole", profile.get("ldconsole"))
    if not adb or not appium:
        raise ConfigError(f"缺少必要命令：adb={adb}, appium={appium}；需先安装并配置")
    missing_python = [name for name in ("pytest", "appium", "allure_pytest") if importlib.util.find_spec(name) is None]
    if missing_python:
        raise ConfigError("当前 Python 缺少测试依赖：" + ", ".join(missing_python))
    if not allure:
        raise ConfigError("缺少 Allure CLI，无法生成 HTML 报告")
    devices = connected_devices(adb)
    port = profile.get("adb_tcp_port")
    if port is not None:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ConfigError("adb_tcp_port 必须是有效端口")
    if not any(state == "device" for state in devices.values()) and port:
        try:
            run_command([adb, "connect", f"127.0.0.1:{port}"])
            devices = connected_devices(adb)
        except ConfigError:
            pass
    if not any(state == "device" for state in devices.values()) and ldconsole and profile.get("ldplayer_index") is not None:
        # 只启动指定的已存在实例，不结束进程也不更改模拟器设置。
        run_command([ldconsole, "launch", "--index", str(profile["ldplayer_index"])], timeout=60)
        for _ in range(36):
            if port:
                try:
                    run_command([adb, "connect", f"127.0.0.1:{port}"])
                except ConfigError:
                    pass
            devices = connected_devices(adb)
            if any(state == "device" for state in devices.values()):
                break
            time.sleep(5)
    serial = select_device(devices, profile.get("device_serial"))
    server = profile.get("appium_url", "http://127.0.0.1:4723")
    pid = start_appium(appium, server, evidence_dir / "appium.log")
    drivers = run_command([appium, "driver", "list", "--installed"], timeout=30)
    if "uiautomator2" not in drivers.lower():
        raise ConfigError("Appium 未安装 UiAutomator2 驱动")
    details = {
        "adb": adb, "appium": appium, "allure": allure, "python": sys.executable,
        "python_version": sys.version.split()[0], "device_serial": serial, "adb_devices": devices,
        "appium_url": server, "appium_started_pid": pid,
        "android_version": run_command([adb, "-s", serial, "shell", "getprop", "ro.build.version.release"]).strip(),
        "device_model": run_command([adb, "-s", serial, "shell", "getprop", "ro.product.model"]).strip(),
        "uiautomator2_installed": True,
    }
    (evidence_dir / "environment.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    return details
