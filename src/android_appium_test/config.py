"""项目配置加载、环境变量展开与启动前校验。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(ValueError):
    """配置缺失或格式错误。"""


def _expand(value: Any) -> Any:
    # 配置文件只保存变量名；凭据由运行环境注入。
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ or not os.environ[name]:
                raise ConfigError(f"缺少环境变量：{name}")
            return os.environ[name]

        return _ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} 必须是映射")
    return value


@dataclass(frozen=True)
class AppConfig:
    """一个被测项目的配置，不包含测试用例。"""

    server_url: str
    devices: Mapping[str, Mapping[str, Any]]
    apps: Mapping[str, Mapping[str, Any]]
    common: Mapping[str, Any]

    def capabilities(self, device_key: str, app_key: str) -> dict[str, Any]:
        # 未知键应在启动前报错，不让 Appium 接收不完整配置。
        if device_key not in self.devices:
            raise ConfigError(f"未知设备：{device_key}")
        if app_key not in self.apps:
            raise ConfigError(f"未知 App：{app_key}")
        sections = [self.common, self.devices[device_key], self.apps[app_key]]
        merged: dict[str, Any] = {}
        for section in sections:
            overlap = merged.keys() & section.keys()
            if overlap:
                raise ConfigError(f"capabilities 重复定义：{', '.join(sorted(overlap))}")
            merged.update(section)
        if merged.get("platformName") != "Android":
            raise ConfigError("仅支持 platformName=Android")
        if merged.get("automationName") != "UiAutomator2":
            raise ConfigError("仅支持 automationName=UiAutomator2")
        if not isinstance(merged.get("deviceName"), str) or not merged["deviceName"].strip():
            raise ConfigError("设备缺少 deviceName")
        has_package = bool(merged.get("appPackage") and merged.get("appActivity"))
        has_apk = bool(merged.get("app"))
        if not (has_package or has_apk):
            raise ConfigError("App 需提供 appPackage + appActivity，或 app 路径")
        return merged


def load_config(path: str | Path) -> AppConfig:
    """读取 YAML 配置，并校验结构与 Appium 服务地址。"""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"配置文件不存在：{config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"配置文件无法读取：{config_path}: {exc}") from exc
    data = _mapping(_expand(raw), "配置根节点")
    server = _mapping(data.get("server"), "server")
    url = server.get("url")
    parsed = urlparse(url) if isinstance(url, str) else None
    if not parsed or parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigError("server.url 必须是完整的 HTTP(S) 地址")
    devices = _mapping(data.get("devices"), "devices")
    apps = _mapping(data.get("apps"), "apps")
    common = _mapping(data.get("common", {}), "common")
    if not devices or not apps:
        raise ConfigError("devices 和 apps 均不能为空")
    for group_name, group in (("devices", devices), ("apps", apps)):
        for key, item in group.items():
            _mapping(item, f"{group_name}.{key}")
    return AppConfig(url, devices, apps, common)
